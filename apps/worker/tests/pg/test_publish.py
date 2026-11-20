"""The publisher against a real PostgreSQL 18: the lock, the pass number, the ready rule, the
order of the PUTs, and the commit that names the pass.

Rows are put into the ledger as `loaded` by the superuser, with lake files built from synthetic
GKG files (`.example` outlets and links) in an in-memory store. Time is passed in.
"""

import threading
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from gdelt import Stream, parse_gkg
from psycopg.rows import dict_row
from worker import dataplane, lake, manifest, publisher
from worker.dataplane import NOW_KEY, DataPlane, Interval, Plan, Put
from worker.ledger import keys, publish
from worker.ledger.publish import Outcome, Point
from worker.store import MemoryStore

Connection = psycopg.Connection[tuple[Any, ...]]
Row = dict[str, Any]
ReadRow = Callable[[Stream, datetime], Row]
Build = Callable[..., bytes]

HOUR = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
Q = timedelta(minutes=15)
MINUTE = timedelta(minutes=1)
EN = Stream.ENGLISH
TR = Stream.TRANSLATED


class RecordingStore(MemoryStore):
    """Remembers the order of the PUTs, and what was in the store at each one."""

    def __init__(self) -> None:
        super().__init__()
        self.puts: list[str] = []

    def put(self, key: str, data: bytes) -> None:
        self.puts.append(key)
        super().put(key, data)


class World:
    """A store with lake files in it, a clock, and a way to put loaded rows in the ledger."""

    def __init__(self, admin: Connection, gkg_file: Build) -> None:
        self.admin = admin
        self.gkg_file = gkg_file
        self.store = RecordingStore()
        self.now = HOUR

    def clock(self) -> datetime:
        return self.now

    def load(
        self, stream: Stream, stamp: datetime, *, at: datetime | None = None, rows: int = 6
    ) -> Interval:
        """A row in state `loaded`, its lake files in the store, loaded at `at` (default now)."""
        parsed = parse_gkg(self.gkg_file(stream, stamp, rows))
        facts, display = lake.build(parsed.rows, parsed.stats)
        facts_key, display_key = keys.lake_keys(stream, stamp, facts, display)
        self.store.objects[facts_key] = facts  # not a PUT the publisher made
        self.store.objects[display_key] = display
        listed_at = stamp - timedelta(minutes=9)
        self.admin.execute(
            """
            insert into ingest.interval
              (stream, stamp, url, size, md5, state, listed_at, loaded_at, parquet_key, rows)
            values (%s::ingest.stream, %s, %s, 1, 'x', 'loaded', %s, %s, %s, %s)
            """,
            (stream.value, stamp, f"https://gdelt.test/{stream.value}/{stamp:%H%M}", listed_at,
             at or self.now, facts_key, rows),
        )  # fmt: skip
        return Interval(stream, stamp, facts_key, listed_at)

    def set_state(self, stream: Stream, stamp: datetime, state: str) -> None:
        self.admin.execute(
            "insert into ingest.interval (stream, stamp, url, state, listed_at)"
            " values (%s::ingest.stream, %s, 'https://gdelt.test/x', %s::ingest.state, %s)",
            (stream.value, stamp, state, stamp),
        )

    def passes(self) -> list[Row]:
        with self.admin.cursor(row_factory=dict_row) as cursor:
            cursor.execute("select * from ingest.publish_pass order by seq")
            return cursor.fetchall()

    def plane(self) -> DataPlane:
        return DataPlane(dataplane.lake_reader(self.store.get))

    def run(self, conn: Connection, plane: DataPlane | None = None) -> publish.Result:
        steps = publish.run_pass(conn, self.store, plane or self.plane(), clock=self.clock)
        while True:
            try:
                next(steps)
            except StopIteration as done:
                result: publish.Result = done.value
                return result


@pytest.fixture(autouse=True)
def no_passes(admin: Connection) -> None:
    """Every test starts with no pass. Only the superuser may empty the table."""
    admin.execute("truncate ingest.publish_pass")


@pytest.fixture
def world(admin: Connection, gkg_file: Build) -> World:
    return World(admin, gkg_file)


def step_to(steps: Any, point: Point) -> publish.At:
    while True:
        at: publish.At = next(steps)
        if at.point is point:
            return at


# --- The lock ------------------------------------------------------------------------------


def close_and_wait(conn: Connection, admin: Connection) -> None:
    """Close a connection and wait until the server has ended its backend: only then are its
    session's locks released."""
    pid = conn.info.backend_pid
    conn.close()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        row = admin.execute("select count(*) from pg_stat_activity where pid = %s", (pid,))
        found = row.fetchone()
        if found is not None and found[0] == 0:
            return
        time.sleep(0.01)
    raise AssertionError(f"backend {pid} did not end")


def test_a_second_publisher_does_not_get_the_lock(
    connect: Callable[[], Connection], admin: Connection
) -> None:
    first, second = connect(), connect()
    assert publish.lock(first)
    assert not publish.lock(second)
    assert publish.lock(first)  # the holder may ask again; it still holds it
    close_and_wait(first, admin)  # a publisher that dies gives the lock back with its connection
    assert publish.lock(second)
    third = connect()
    assert not publish.lock(third)
    publish.unlock(second)
    publish.unlock(second)
    assert publish.lock(third)


# --- The pass number -----------------------------------------------------------------------


def test_a_burned_seq_is_never_taken_again(conn: Connection, world: World) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    steps = publish.run_pass(conn, world.store, world.plane(), clock=world.clock)
    assert step_to(steps, Point.NUMBERED).seq == 1
    steps.close()  # the pass dies with number 1 taken
    assert publish.take_seq(conn) == 2
    assert publish.take_seq(conn) == 3
    result = world.run(conn)
    assert result.outcome is Outcome.PUBLISHED and result.seq == 4
    seqs = [(p["seq"], p["finished_at"] is not None) for p in world.passes()]
    assert seqs == [(1, False), (2, False), (3, False), (4, True)]


def test_two_connections_never_take_the_same_number(connect: Callable[[], Connection]) -> None:
    a, b = connect(), connect()
    taken = [publish.take_seq(a), publish.take_seq(b), publish.take_seq(a), publish.take_seq(b)]
    assert taken == [1, 2, 3, 4]


def test_no_number_is_taken_while_a_commit_is_checking(
    connect: Callable[[], Connection],
) -> None:
    """A commit holds SERIAL for its transaction, so its check that its number is the largest
    cannot race a number being taken."""
    committing, taker = connect(), connect()
    taken: list[int] = []
    with committing.transaction():
        committing.execute("select pg_advisory_xact_lock(%s)", (publish.SERIAL,))
        thread = threading.Thread(target=lambda: taken.append(publish.take_seq(taker)))
        thread.start()
        thread.join(timeout=1.0)
        assert thread.is_alive() and taken == []  # waiting for the commit's transaction
    thread.join(timeout=10.0)
    assert taken == [1]


def test_the_fence_holds_on_a_connection_whose_default_is_repeatable_read(
    connect: Callable[[], Connection], world: World, row: ReadRow
) -> None:
    """A commit waits for SERIAL while another session takes the next number. Its checks must
    see that number: they would not if the commit's transaction ran at REPEATABLE READ, with its
    snapshot taken before the wait. The commit states READ COMMITTED itself."""
    interval = world.load(EN, HOUR)
    committing, taker = connect(), connect()
    committing.execute("set default_transaction_isolation = 'repeatable read'")
    seq = publish.take_seq(committing)
    results: list[bool] = []
    with taker.transaction():
        taker.execute("select pg_advisory_xact_lock(%s)", (publish.SERIAL,))
        thread = threading.Thread(
            target=lambda: results.append(
                publish.commit(committing, seq, [interval], "cdn/live/m.json", {})
            )
        )
        thread.start()
        thread.join(timeout=1.0)
        assert thread.is_alive()  # the commit waits for SERIAL
        taker.execute(
            "insert into ingest.publish_pass (seq) select max(seq) + 1 from ingest.publish_pass"
        )
    thread.join(timeout=10.0)
    assert results == [False]  # it saw the later number
    assert row(EN, HOUR)["state"] == "loaded"


def test_with_nothing_due_a_pass_takes_no_number(conn: Connection, world: World) -> None:
    assert world.run(conn).outcome is Outcome.IDLE
    world.load(EN, HOUR)  # alone, and loaded just now: not ready for 15 minutes
    assert world.run(conn).outcome is Outcome.IDLE
    assert world.passes() == []


# --- The ready rule ------------------------------------------------------------------------


def stamps_ready(conn: Connection, world: World) -> list[tuple[Stream, datetime]]:
    return [(i.stream, i.stamp) for i in publish.ready(conn, now=world.now)]


def test_a_stamp_is_ready_when_both_streams_are_loaded(conn: Connection, world: World) -> None:
    world.load(EN, HOUR)
    assert stamps_ready(conn, world) == []
    world.load(TR, HOUR)
    assert stamps_ready(conn, world) == [(EN, HOUR), (TR, HOUR)]


def test_a_lone_stream_is_ready_15_minutes_after_it_loaded(conn: Connection, world: World) -> None:
    world.load(EN, HOUR, at=HOUR)
    world.set_state(TR, HOUR, "verified")  # still on its way
    world.now = HOUR + 15 * MINUTE - timedelta(seconds=1)
    assert stamps_ready(conn, world) == []
    world.now = HOUR + 15 * MINUTE
    assert stamps_ready(conn, world) == [(EN, HOUR)]
    assert publish.READY_WAIT == 15 * MINUTE


def test_a_stream_whose_partner_has_finished_another_way_is_ready_at_once(
    conn: Connection, world: World
) -> None:
    for n, partner in enumerate(["gap", "dead", "published"]):
        stamp = HOUR + n * Q
        world.load(EN, stamp)
        world.set_state(TR, stamp, partner)
    assert stamps_ready(conn, world) == [(EN, HOUR + n * Q) for n in range(3)]


def test_published_and_unfinished_rows_are_never_ready(conn: Connection, world: World) -> None:
    states = ["listed", "fetched", "verified", "published", "gap", "dead"]
    for n, state in enumerate(states):
        world.set_state(EN, HOUR + n * Q, state)
        world.set_state(TR, HOUR + n * Q, state)
    world.now = HOUR + timedelta(days=1)
    assert stamps_ready(conn, world) == []


# --- A whole pass --------------------------------------------------------------------------


def test_now_json_is_the_last_put_and_what_it_names_is_already_there(
    conn: Connection, world: World
) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    result = world.run(conn)
    assert result.outcome is Outcome.PUBLISHED
    assert world.store.puts[-1] == NOW_KEY
    assert world.store.puts.count(NOW_KEY) == 1
    assert all(dataplane.is_content_key(k, world.store.objects[k]) for k in world.store.puts[:-1])
    cold = dataplane.cold_start(world.store.get)  # raises if anything named is missing
    assert cold.intervals == {(EN, HOUR), (TR, HOUR)}
    assert cold.now.seq == result.seq == 1


def test_a_pass_marks_its_intervals_published_with_its_seq(
    conn: Connection, world: World, row: ReadRow
) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    world.run(conn)
    for stream in Stream:
        found = row(stream, HOUR)
        assert (found["state"], found["seq"], found["published_at"]) == ("published", 1, world.now)
        assert found["lease_token"] is None


def test_a_pass_records_its_manifest_and_its_writes(conn: Connection, world: World) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    result = world.run(conn)
    assert result.plan is not None
    (record,) = world.passes()
    assert record["manifest_key"] == result.plan.manifest_key
    assert record["started_at"] == record["finished_at"] == world.now
    objects = record["objects"]
    puts = objects["puts"]
    assert objects["heads"] == len(result.plan.puts) and objects["skipped"] == 0
    assert sum(kind["n"] for kind in puts.values()) == len(world.store.puts)
    assert puts["now"]["n"] == 1 and puts["manifest"]["n"] == 1 and puts["points"]["n"] == 1
    assert puts["now"]["bytes"] == len(world.store.objects[NOW_KEY])
    sizes = sum(len(world.store.objects[k]) for k in set(world.store.puts))
    assert sum(kind["bytes"] for kind in puts.values()) == sizes


def test_a_crash_between_now_json_and_the_commit_is_published_again_under_the_next_seq(
    conn: Connection, world: World, row: ReadRow
) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    steps = publish.run_pass(conn, world.store, world.plane(), clock=world.clock)
    step_to(steps, Point.COMMIT)  # now.json is written
    steps.close()  # and the publisher dies before its commit
    crashed = manifest.read_now(world.store.objects[NOW_KEY])
    shard_keys = {k for k in world.store.puts if "/shards/" in k or "/titles/" in k}
    assert crashed.seq == 1 and shard_keys
    assert row(EN, HOUR)["state"] == "loaded"

    world.now += MINUTE
    world.store.puts.clear()
    result = world.run(conn)  # a new publisher, with nothing in memory
    assert result.outcome is Outcome.PUBLISHED and result.seq == 2
    assert {(i.stream, i.stamp) for i in result.published} == {(EN, HOUR), (TR, HOUR)}
    assert row(EN, HOUR)["seq"] == row(TR, HOUR)["seq"] == 2
    again = dataplane.cold_start(world.store.get)
    unit = again.manifest.open[0]
    named = {"cdn/" + unit.points.ref.key} | {"cdn/" + r.key for r in unit.titles.cells.values()}
    assert named <= shard_keys  # the same shard keys
    # Nothing that was already there was written again: only the manifest and now.json.
    assert result.plan is not None
    assert world.store.puts == [result.plan.manifest_key, NOW_KEY]
    assert [(p["seq"], p["finished_at"] is not None) for p in world.passes()] == [
        (1, False),
        (2, True),
    ]


def test_a_crash_before_now_json_leaves_the_old_one(conn: Connection, world: World) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    assert world.run(conn).outcome is Outcome.PUBLISHED
    first = world.store.objects[NOW_KEY]
    world.load(EN, HOUR + Q)
    world.load(TR, HOUR + Q)
    world.now = HOUR + Q + 8 * MINUTE
    steps = publish.run_pass(conn, world.store, world.plane(), clock=world.clock)
    step_to(steps, Point.WRITTEN)
    steps.close()
    assert world.store.objects[NOW_KEY] == first
    assert dataplane.cold_start(world.store.get).intervals == {(EN, HOUR), (TR, HOUR)}


# --- The fence -----------------------------------------------------------------------------


def test_a_commit_from_a_pass_that_is_no_longer_the_newest_changes_nothing(
    conn: Connection, world: World, row: ReadRow
) -> None:
    interval = world.load(EN, HOUR)
    old = publish.take_seq(conn)
    publish.take_seq(conn)
    assert not publish.is_newest(conn, old)
    assert not publish.commit(conn, old, [interval], "cdn/live/m.json", {})
    assert row(EN, HOUR)["state"] == "loaded" and row(EN, HOUR)["seq"] is None
    assert all(p["finished_at"] is None for p in world.passes())


def test_a_commit_naming_a_row_that_is_not_loaded_changes_nothing(
    conn: Connection, world: World, row: ReadRow
) -> None:
    good = world.load(EN, HOUR)
    world.set_state(TR, HOUR, "verified")
    stale = Interval(TR, HOUR, "lake/facts/gkg/v1/x.parquet", HOUR)
    seq = publish.take_seq(conn)
    assert not publish.commit(conn, seq, [good, stale], "cdn/live/m.json", {})
    assert row(EN, HOUR)["state"] == "loaded"  # rolled back with the rest
    assert world.passes()[0]["finished_at"] is None
    assert publish.commit(conn, seq, [good], "cdn/live/m.json", {"puts": {}})
    assert row(EN, HOUR)["state"] == "published"
    assert not publish.commit(conn, seq, [good], "cdn/live/m.json", {})  # not twice


def test_a_pass_that_is_overtaken_writes_no_now_json(conn: Connection, world: World) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    steps = publish.run_pass(conn, world.store, world.plane(), clock=world.clock)
    step_to(steps, Point.WRITTEN)
    publish.take_seq(conn)  # another pass takes a number
    with pytest.raises(StopIteration) as done:
        next(steps)
    assert done.value.value.outcome is Outcome.FENCED
    assert NOW_KEY not in world.store.objects


def test_a_pass_overtaken_after_now_json_does_not_commit(
    conn: Connection, world: World, row: ReadRow
) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    steps = publish.run_pass(conn, world.store, world.plane(), clock=world.clock)
    step_to(steps, Point.COMMIT)
    publish.take_seq(conn)
    with pytest.raises(StopIteration) as done:
        next(steps)
    assert done.value.value.outcome is Outcome.FENCED
    assert row(EN, HOUR)["state"] == "loaded"


# The known limit (WALKTHROUGH.md, "Known limits"). The pass number fences a stalled publisher's
# commit, not its PUT of now.json. This test shows the one case that gets through, so that the
# day P2's conditional PUT closes it, the test changes with it.


class LandsLate(RecordingStore):
    """A store whose next PUT of now.json is held back: before it lands, `meanwhile` runs. That
    is a publisher paused between its check and its PUT, or a PUT still in flight while another
    pass runs."""

    def __init__(self) -> None:
        super().__init__()
        self.meanwhile: Callable[[], None] | None = None

    def put(self, key: str, data: bytes) -> None:
        if key == NOW_KEY and self.meanwhile is not None:
            meanwhile, self.meanwhile = self.meanwhile, None
            meanwhile()
        super().put(key, data)


def test_known_limit_a_now_json_put_that_lands_after_a_newer_pass_goes_back_until_the_next(
    connect: Callable[[], Connection], world: World, row: ReadRow
) -> None:
    store = LandsLate()
    store.objects = world.store.objects
    world.store = store
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE
    stalled, newer = connect(), connect()

    def newer_pass() -> None:
        world.load(EN, HOUR + Q)  # more data arrives, and a newer pass publishes it all
        world.load(TR, HOUR + Q)
        result = world.run(newer)
        assert result.outcome is Outcome.PUBLISHED and result.seq == 2

    store.meanwhile = newer_pass
    result = world.run(stalled)  # pass 1 checks it is the newest; pass 2 runs; pass 1's PUT lands

    # The database refused the stalled pass's commit: the fence did its part.
    assert result.outcome is Outcome.FENCED and result.seq == 1
    assert row(EN, HOUR)["seq"] == row(EN, HOUR + Q)["seq"] == 2
    # Its now.json went in all the same: pass 1's, older than pass 2's, though complete.
    went_back = dataplane.cold_start(world.store.get)  # raises if it named a missing object
    assert went_back.now.seq == 1
    assert went_back.intervals == {(EN, HOUR), (TR, HOUR)}  # without HOUR + Q, published by 2
    # It stays until the next pass, which writes the newest state again.
    world.load(EN, HOUR + 2 * Q)
    world.load(TR, HOUR + 2 * Q)
    world.now = HOUR + 2 * Q + 8 * MINUTE
    assert world.run(newer).outcome is Outcome.PUBLISHED
    after = dataplane.cold_start(world.store.get)
    assert after.now.seq == 3
    assert after.intervals == {(s, HOUR + n * Q) for s in Stream for n in range(3)}


def test_an_object_whose_key_is_not_the_hash_of_its_bytes_is_refused(
    conn: Connection, world: World
) -> None:
    world.load(EN, HOUR)
    world.load(TR, HOUR)
    world.now = HOUR + 8 * MINUTE

    class Forger(DataPlane):
        def plan(
            self,
            *,
            seq: int,
            now: datetime,
            ready: Sequence[Interval],
            published: Sequence[Interval],
        ) -> Plan:
            real = super().plan(seq=seq, now=now, ready=ready, published=published)
            bad = Put("cdn/live/dt=2026-11-14/shards/" + "0" * 32 + ".arrow", b"x", "points")
            return Plan(
                (bad, *real.puts), real.now, real.manifest_key, real.named, real.cut, (), ()
            )

    plane = Forger(dataplane.lake_reader(world.store.get))
    with pytest.raises(ValueError, match="not the hash"):
        world.run(conn, plane)
    assert world.store.puts == []


# --- Over time -----------------------------------------------------------------------------


def test_the_hourly_cut_makes_a_pass_that_compacts_the_hour(conn: Connection, world: World) -> None:
    plane = world.plane()  # one publisher, running throughout
    for n in range(4):
        world.load(EN, HOUR + n * Q, at=HOUR + n * Q + 2 * MINUTE)
        world.load(TR, HOUR + n * Q, at=HOUR + n * Q + 3 * MINUTE)
        world.now = HOUR + n * Q + 4 * MINUTE
        assert world.run(conn, plane).outcome is Outcome.PUBLISHED
        world.now += MINUTE
        assert world.run(conn, plane).outcome is Outcome.IDLE
    world.now = HOUR + timedelta(hours=1, minutes=14)
    assert world.run(conn, plane).outcome is Outcome.IDLE
    world.now = HOUR + timedelta(hours=1, minutes=15)
    result = world.run(conn, plane)
    assert result.outcome is Outcome.PUBLISHED and result.published == ()
    cold = dataplane.cold_start(world.store.get)
    assert cold.manifest.open == ()
    assert cold.hourly is not None and [h.hour for h in cold.hourly.hours] == [HOUR]
    assert len(cold.intervals) == 8
    world.now += MINUTE
    assert world.run(conn, plane).outcome is Outcome.IDLE


def test_an_interval_older_than_the_window_is_published_with_no_objects(
    conn: Connection, world: World, row: ReadRow
) -> None:
    old = HOUR - timedelta(hours=30)
    world.load(EN, old)
    world.load(TR, old)
    world.now = HOUR + 20 * MINUTE
    result = world.run(conn)
    assert result.outcome is Outcome.PUBLISHED
    assert row(EN, old)["state"] == "published"
    assert not any("/shards/" in k or "/titles/" in k for k in world.store.puts)
    assert dataplane.cold_start(world.store.get).intervals == frozenset()


def test_a_late_stream_is_published_on_its_own_in_a_later_pass(
    conn: Connection, world: World, row: ReadRow
) -> None:
    world.load(EN, HOUR, at=HOUR)
    world.set_state(TR, HOUR, "listed")
    world.now = HOUR + 15 * MINUTE
    assert world.run(conn).outcome is Outcome.PUBLISHED
    world.admin.execute("delete from ingest.interval where stream = 'translated'")
    world.load(TR, HOUR, at=HOUR + 20 * MINUTE)
    world.now = HOUR + 20 * MINUTE
    result = world.run(conn)
    assert [(i.stream, i.stamp) for i in result.published] == [(TR, HOUR)]
    assert (row(EN, HOUR)["seq"], row(TR, HOUR)["seq"]) == (1, 2)
    cold = dataplane.cold_start(world.store.get)
    assert [(u.stamp, u.streams) for u in cold.manifest.open] == [(HOUR, (EN,)), (HOUR, (TR,))]


# --- The process ---------------------------------------------------------------------------


def test_a_second_publisher_process_exits_with_its_own_status(
    connect: Callable[[], Connection], world: World
) -> None:
    holder = connect()
    assert publish.lock(holder)
    stop = threading.Event()
    status = publisher.serve(connect(), world.store, stop, pass_seconds=0.01)
    assert status == publisher.EXIT_LOCKED


def test_the_process_publishes_pings_after_each_commit_and_stops_when_told(
    connect: Callable[[], Connection], world: World, row: ReadRow
) -> None:
    world.load(EN, HOUR, at=HOUR - timedelta(hours=1))  # long since loaded: ready on its own
    stop = threading.Event()
    pings: list[str | None] = []

    def pinger(url: str | None) -> bool:
        pings.append(url)
        stop.set()  # one pass is enough
        return True

    status = publisher.serve(
        connect(), world.store, stop, healthcheck_url="https://hc.test/x", pinger=pinger
    )
    assert status == 0
    assert pings == ["https://hc.test/x"]
    assert row(EN, HOUR)["state"] == "published"
    assert NOW_KEY in world.store.objects


def test_the_process_stops_when_another_publisher_overtakes_it(
    connect: Callable[[], Connection], world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    world.load(EN, HOUR, at=HOUR - timedelta(hours=1))
    rogue = connect()
    real_take = publish.take_seq

    def take_then_overtaken(conn: Connection, *, now: datetime | None = None) -> int:
        seq = real_take(conn, now=now)
        real_take(rogue)  # a publisher without the lock takes the next number at once
        return seq

    monkeypatch.setattr(publish, "take_seq", take_then_overtaken)
    status = publisher.serve(connect(), world.store, threading.Event(), pass_seconds=0.01)
    assert status == publisher.EXIT_FENCED
    assert NOW_KEY not in world.store.objects
