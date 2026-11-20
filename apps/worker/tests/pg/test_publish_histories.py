"""The publisher's property test: generated histories against a real PostgreSQL 18.

A history is a sequence of small steps chosen by Hypothesis: an interval is loaded, the other
stream of a stamp ends as a gap or dead, the clock moves, a publisher starts, a publisher takes
the next step of its pass, a publisher dies where it stands. A pass is a generator that yields
wherever the world can change under it (`worker.ledger.publish`), so a publisher can die after
its number is taken, between two PUTs, or between `now.json` and its commit.

Two kinds of publisher run. A proper one takes the advisory lock first, and a second proper one
must fail to take it while the first lives. A rogue one skips the lock, as a bug or a second
process with another lock would: the pass number is the fence that has to make it harmless.

Checked after every step, and again once one clean publisher has published everything:

5a. `now.json`'s `seq` never goes down.
5b. A published interval stays published, under the `seq` its commit gave it.
5c. A commit succeeds only while its pass is the newest; a commit that fails changes nothing.
5d. Everything `now.json` reaches is in the store, and every object was written after
    everything it names; an object's key is the hash of its bytes, and no key is ever given
    other bytes.
5e. Every published interval in the window is reachable from `now.json`, and nothing that is
    not published or loaded is.
5f. Every published interval names a pass that finished; numbers are never reused.

At the end, every loaded interval is published exactly once, and the data plane is what a
fresh publisher would build from the final ledger: the same objects under the same keys.

What it does not model: a publisher that stalls between its newest-pass check and the moment
its `now.json` lands (a pause there, or a PUT still in flight). Steps are whole yields, and
there is no yield between the two, so 5a and 5e hold here by construction. That case can put
an older, complete `now.json` back until the next pass: the known limit that
`test_publish.py::test_known_limit_a_now_json_put_that_lands_after_a_newer_pass_goes_back_until_the_next`
shows, and P2's conditional PUT closes.

The last test removes the pass-number fence from the commit and runs the same histories. They
must find a violation: a property test that cannot fail proves nothing.
"""

import json
import logging
import os
import time
from collections import Counter
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import psycopg
import pytest
from gdelt import Stream, parse_gkg
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)
from psycopg.rows import dict_row
from worker import dataplane, lake, manifest
from worker.dataplane import NOW_KEY, DataPlane
from worker.ledger import keys, publish
from worker.ledger.publish import At, Outcome, Point, Result
from worker.store import MemoryStore

Connection = psycopg.Connection[tuple[Any, ...]]
Build = Callable[..., bytes]
Key = tuple[Stream, datetime]

HISTORIES = int(os.environ.get("GL_PUBLISH_HISTORIES", "300"))
SLOTS = 3
T0 = datetime(2026, 11, 14, 13, 40, tzinfo=UTC)
STAMPS = [datetime(2026, 11, 14, 13, 30, tzinfo=UTC) + timedelta(minutes=15 * n) for n in range(6)]
STREAMS = [Stream.ENGLISH, Stream.TRANSLATED]

SOME_STREAM = st.sampled_from(STREAMS)
SOME_STAMP = st.integers(0, len(STAMPS) - 1)
SOME_SLOT = st.integers(0, SLOTS - 1)


class Violation(AssertionError):
    """An invariant of the publisher does not hold."""


def names(data: bytes) -> set[str]:
    """Every stored key a data-plane JSON file names."""
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            items: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
            for key, item in items.items():
                if key in ("key", "hour", "manifest") and isinstance(item, str) and "/" in item:
                    found.add("cdn/" + item)
                else:
                    walk(item)
        elif isinstance(value, list):
            entries: list[Any] = value  # pyright: ignore[reportUnknownVariableType]
            for item in entries:
                walk(item)

    walk(json.loads(data))
    return found


class Store(MemoryStore):
    """Checks every PUT as it lands (5d)."""

    def put(self, key: str, data: bytes) -> None:
        if key != NOW_KEY:
            if not dataplane.is_content_key(key, data):
                raise Violation(f"{key} is not the hash of its bytes")
            if key in self.objects and self.objects[key] != data:
                raise Violation(f"{key} was written again with other bytes")
        if key.endswith(".json"):
            missing = names(data) - set(self.objects)
            if missing:
                raise Violation(f"{key} was written before {sorted(missing)}")
        super().put(key, data)


@dataclass
class Publisher:
    conn: Connection
    plane: DataPlane
    locked: bool
    steps: Generator[At, None, Result] | None = None
    at: At | None = None


@dataclass
class Env:
    admin: Connection
    connect: Callable[[], Connection]
    gkg_file: Build
    lake_files: dict[Key, tuple[str, bytes, str, bytes]] = field(default_factory=dict[Any, Any])
    tally: Counter[str] = field(default_factory=Counter[str])

    def lake(self, stream: Stream, stamp: datetime) -> tuple[str, bytes, str, bytes]:
        if (stream, stamp) not in self.lake_files:
            parsed = parse_gkg(self.gkg_file(stream, stamp, 3))
            facts, display = lake.build(parsed.rows, parsed.stats)
            facts_key, display_key = keys.lake_keys(stream, stamp, facts, display)
            self.lake_files[(stream, stamp)] = (facts_key, facts, display_key, display)
        return self.lake_files[(stream, stamp)]


class Histories(RuleBasedStateMachine):
    env: ClassVar[Env]

    def __init__(self) -> None:
        super().__init__()
        env = self.env
        env.admin.execute("truncate ingest.interval, ingest.publish_pass")
        env.tally["histories"] += 1
        self.now = T0
        self.store = Store()
        self.slots: list[Publisher | None] = [None] * SLOTS
        self.loaded: set[Key] = set()  # rows this history put in as loaded
        self.finished: dict[Key, str] = {}  # rows it put in as gap or dead
        self.committed: dict[
            Key, int
        ] = {}  # what the successful commits published, and with what seq
        self.highest_now = 0
        self.failed = False

    # --- helpers --------------------------------------------------------------------------

    def check(self, holds: bool, message: str) -> None:
        if not holds:
            self.failed = True
            raise Violation(message)

    def clock(self) -> datetime:
        return self.now

    def rows(self) -> dict[Key, dict[str, Any]]:
        with self.env.admin.cursor(row_factory=dict_row) as cursor:
            cursor.execute("select * from ingest.interval")
            return {(Stream(r["stream"]), r["stamp"]): r for r in cursor}

    def newest_pass(self) -> int:
        row = self.env.admin.execute("select max(seq) from ingest.publish_pass").fetchone()
        assert row is not None
        return row[0] or 0

    def close(self, conn: Connection) -> None:
        """Close a publisher's connection and wait until the server has ended its backend:
        only then is its session's lock released, as it is when a process dies."""
        pid = conn.info.backend_pid
        conn.close()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            found = self.env.admin.execute(
                "select count(*) from pg_stat_activity where pid = %s", (pid,)
            ).fetchone()
            if found is not None and found[0] == 0:
                return
            time.sleep(0.005)
        raise AssertionError(f"backend {pid} did not end")

    def live_locked(self) -> list[int]:
        return [i for i, p in enumerate(self.slots) if p is not None and p.locked]

    def start_publisher(self, slot: int, locked: bool) -> None:
        conn = self.env.connect()
        if locked:
            holders = self.live_locked()
            got = publish.lock(conn)
            if got == bool(holders):
                self.close(conn)
                state = "given" if got else "refused"
                self.check(False, f"the lock was {state} with locked publishers in slots {holders}")
            if not got:
                self.env.tally["second publishers refused"] += 1
                self.close(conn)
                return
        else:
            self.env.tally["rogue publishers"] += 1
        self.slots[slot] = Publisher(conn, DataPlane(dataplane.lake_reader(self.store.get)), locked)

    def advance(self, slot: int) -> None:
        publisher = self.slots[slot]
        assert publisher is not None
        if publisher.steps is None:
            publisher.steps = publish.run_pass(
                publisher.conn, self.store, publisher.plane, clock=self.clock
            )
            publisher.at = None
        committing = publisher.at is not None and publisher.at.point is Point.COMMIT
        before = self.rows() if committing else {}
        try:
            publisher.at = next(publisher.steps)
            return
        except StopIteration as done:
            result: Result = done.value
        except Violation:
            self.failed = True
            raise
        publisher.steps = None
        publisher.at = None
        self.env.tally[f"passes {result.outcome}"] += 1
        if committing:
            self.judge(result, before)

    def judge(self, result: Result, before: dict[Key, dict[str, Any]]) -> None:
        assert result.seq is not None
        if result.outcome is Outcome.FENCED:
            self.env.tally["commits rejected"] += 1
            self.check(
                self.rows() == before, f"the rejected commit of pass {result.seq} changed a row"
            )
            return
        # 5c: a commit lands only from the newest pass.
        newest = self.newest_pass()
        self.check(
            result.seq == newest,
            f"pass {result.seq} committed though pass {newest} exists: it was not the newest",
        )
        for interval in result.published:
            key = (interval.stream, interval.stamp)
            self.check(key not in self.committed, f"{key} was published twice")
            self.committed[key] = result.seq
        self.env.tally["commits"] += 1
        self.env.tally["intervals published"] += len(result.published)

    # --- the steps a history is made of ---------------------------------------------------

    @initialize(
        first=st.lists(st.tuples(SOME_STREAM, SOME_STAMP), min_size=1, max_size=4),
        rogue=st.booleans(),
    )
    def opening(self, first: list[tuple[Stream, int]], rogue: bool) -> None:
        """Every history opens with some intervals loaded and a proper publisher running, and
        half of them with a rogue publisher beside it."""
        for stream, index in first:
            self.load(stream, index)
        self.start_publisher(0, locked=True)
        if rogue:
            self.start_publisher(1, locked=False)

    @rule(stream=SOME_STREAM, index=SOME_STAMP)
    def load(self, stream: Stream, index: int) -> None:
        """Tier 1 loads an interval."""
        key = (stream, STAMPS[index])
        if key in self.loaded or key in self.finished:
            return
        facts_key, facts, display_key, display = self.env.lake(*key)
        self.store.objects[facts_key] = facts
        self.store.objects[display_key] = display
        self.env.admin.execute(
            """
            insert into ingest.interval
              (stream, stamp, url, size, md5, state, listed_at, loaded_at, parquet_key, rows)
            values (%s::ingest.stream, %s, 'https://gdelt.test/x', 1, 'x', 'loaded', %s, %s, %s, 3)
            """,
            (stream.value, key[1], key[1] - timedelta(minutes=9), self.now, facts_key),
        )
        self.loaded.add(key)

    @rule(stream=SOME_STREAM, index=SOME_STAMP)
    def load_another(self, stream: Stream, index: int) -> None:
        self.load(stream, index)

    @rule(stream=SOME_STREAM, index=SOME_STAMP, state=st.sampled_from(["gap", "dead"]))
    def end_another_way(self, stream: Stream, index: int, state: str) -> None:
        """An interval ends without loading: its partner need not wait for it."""
        key = (stream, STAMPS[index])
        if key in self.loaded or key in self.finished:
            return
        self.env.admin.execute(
            "insert into ingest.interval (stream, stamp, url, state, listed_at)"
            " values (%s::ingest.stream, %s, 'https://gdelt.test/x', %s::ingest.state, %s)",
            (stream.value, key[1], state, key[1]),
        )
        self.finished[key] = state

    @rule(
        delta=st.sampled_from(
            [
                timedelta(seconds=1),
                timedelta(minutes=2),
                timedelta(minutes=7),
                timedelta(minutes=16),  # past the ready wait
                timedelta(minutes=16),
                timedelta(minutes=61),  # past an hourly cut
            ]
        )
    )
    def tick(self, delta: timedelta) -> None:
        if dataplane.cut_of(self.now + delta) != dataplane.cut_of(self.now):
            self.env.tally["cuts passed"] += 1
        self.now += delta

    @precondition(lambda self: any(p is None for p in self.slots))
    @rule(pick=SOME_SLOT, locked=st.booleans())
    def start(self, pick: int, locked: bool) -> None:
        """A publisher process starts."""
        free = [i for i, p in enumerate(self.slots) if p is None]
        self.start_publisher(free[pick % len(free)], locked)

    def step_one(self, pick: int) -> None:
        busy = [i for i, p in enumerate(self.slots) if p is not None]
        self.advance(busy[pick % len(busy)])

    @precondition(lambda self: any(p is not None for p in self.slots))
    @rule(pick=SOME_SLOT)
    def step(self, pick: int) -> None:
        """A publisher takes the next step of its pass, or starts a pass."""
        self.step_one(pick)

    @precondition(lambda self: any(p is not None for p in self.slots))
    @rule(pick=SOME_SLOT)
    def step_again(self, pick: int) -> None:
        self.step_one(pick)

    @precondition(lambda self: any(p is not None for p in self.slots))
    @rule(pick=SOME_SLOT)
    def step_once_more(self, pick: int) -> None:
        self.step_one(pick)

    def rush_one(self, pick: int) -> None:
        busy = [i for i, p in enumerate(self.slots) if p is not None]
        slot = busy[pick % len(busy)]
        self.advance(slot)
        publisher = self.slots[slot]
        while (
            publisher is not None
            and publisher.steps is not None
            and publisher.at is not None
            and publisher.at.point is not Point.COMMIT
        ):
            self.advance(slot)

    @precondition(lambda self: any(p is not None for p in self.slots))
    @rule(pick=SOME_SLOT)
    def rush(self, pick: int) -> None:
        """A publisher runs its pass on to the commit, and stops just before it."""
        self.rush_one(pick)

    @precondition(lambda self: any(p is not None for p in self.slots))
    @rule(pick=SOME_SLOT)
    def rush_again(self, pick: int) -> None:
        self.rush_one(pick)

    @precondition(lambda self: any(p is not None for p in self.slots))
    @rule(pick=SOME_SLOT)
    def crash(self, pick: int) -> None:
        """A publisher dies where it stands. Its connection, and its lock, go with it."""
        busy = [i for i, p in enumerate(self.slots) if p is not None]
        slot = busy[pick % len(busy)]
        publisher = self.slots[slot]
        assert publisher is not None
        if publisher.at is not None and publisher.at.point is Point.COMMIT:
            self.env.tally["deaths between now.json and the commit"] += 1
        if publisher.steps is not None:
            publisher.steps.close()
        self.close(publisher.conn)
        self.slots[slot] = None
        self.env.tally["deaths"] += 1

    # --- after every step -----------------------------------------------------------------

    @invariant()
    def now_json_never_goes_back(self) -> None:
        data = self.store.objects.get(NOW_KEY)
        if data is None:
            return
        seq = manifest.read_now(data).seq
        self.check(seq >= self.highest_now, f"now.json went back from {self.highest_now} to {seq}")
        self.highest_now = seq

    @invariant()
    def published_stays_published(self) -> None:
        rows = self.rows()
        published = {k: r["seq"] for k, r in rows.items() if r["state"] == "published"}
        self.check(
            published == self.committed,
            f"the ledger publishes {published}, the commits {self.committed}",
        )
        finished = {
            r[0]
            for r in self.env.admin.execute(
                "select seq from ingest.publish_pass where finished_at is not null"
            ).fetchall()
        }
        self.check(set(self.committed.values()) <= finished, "an interval names an unfinished pass")

    @invariant()
    def now_json_reaches_what_is_published(self) -> None:
        if NOW_KEY not in self.store.objects:
            self.check(not self.committed, "intervals are published and there is no now.json")
            return
        try:
            cold = dataplane.cold_start(self.store.get)
        except LookupError as missing:
            self.check(False, f"now.json reaches a missing object: {missing}")
            return
        start = dataplane.window_start(cold.now.written_at)
        shown = {k for k in self.committed if k[1] >= start}
        self.check(
            shown <= cold.intervals,
            f"published and not reachable: {sorted(shown - cold.intervals)}",
        )
        self.check(
            cold.intervals <= self.loaded,
            f"reachable and never loaded: {sorted(cold.intervals - self.loaded)}",
        )

    # --- at the end -----------------------------------------------------------------------

    def finish_cleanly(self, publisher: Publisher) -> None:
        for _ in range(12):
            publisher.steps = None
            publisher.at = None
            self.advance(0)
            while publisher.steps is not None:
                self.advance(0)
            self.now_json_never_goes_back()
            self.published_stays_published()
            self.now_json_reaches_what_is_published()
            if not publish.ready(publisher.conn, now=self.now):
                break
            self.now += timedelta(minutes=1)
        loaded = {k for k, r in self.rows().items() if r["state"] == "loaded"}
        self.check(not loaded, f"still loaded after a clean publisher ran: {sorted(loaded)}")
        self.check(
            set(self.committed) == self.loaded, "not every loaded interval was published once"
        )

        # The data plane is a function of the ledger: from the final ledger, a fresh publisher
        # writes the same pass manifest and the same now.json, byte for byte.
        if NOW_KEY in self.store.objects:
            now = manifest.read_now(self.store.objects[NOW_KEY])
            published = publish.published(publisher.conn, dataplane.window_start(now.written_at))
            fresh = DataPlane(dataplane.lake_reader(self.store.get)).plan(
                seq=now.seq, now=now.written_at, ready=[], published=published
            )
            self.check(
                fresh.now == self.store.objects[NOW_KEY],
                "a fresh publisher builds another data plane from the same ledger",
            )

    def teardown(self) -> None:
        for publisher in self.slots:
            if publisher is not None:
                if publisher.steps is not None:
                    publisher.steps.close()
                self.close(publisher.conn)
        self.slots = [None] * SLOTS
        if self.failed:
            return
        # Later, one proper publisher with nothing going wrong publishes everything.
        self.now += timedelta(minutes=16)
        self.start_publisher(0, locked=True)
        publisher = self.slots[0]
        assert publisher is not None
        try:
            self.finish_cleanly(publisher)
        finally:
            self.close(publisher.conn)
            self.slots[0] = None
        self.env.tally["intervals finished"] += len(self.loaded)


@pytest.fixture(autouse=True)
def quiet() -> Iterator[None]:
    logger = logging.getLogger("worker")
    level = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    yield
    logger.setLevel(level)


@pytest.fixture
def env(admin: Connection, connect: Callable[[], Connection], gkg_file: Build) -> Env:
    return Env(admin=admin, connect=connect, gkg_file=gkg_file)


def _is_invariant(line: str) -> bool:
    return line.startswith(("state.now_json", "state.published_stays"))


def run(env: Env, *, examples: int, derandomize: bool, steps: int = 50) -> None:
    Histories.env = env
    run_state_machine_as_test(
        Histories,
        settings=settings(
            max_examples=examples,
            stateful_step_count=steps,
            deadline=None,
            database=None,  # nothing is written into the repository
            derandomize=derandomize,
            report_multiple_bugs=False,
            print_blob=True,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
        ),
    )


def test_the_histories_keep_every_invariant(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    run(env, examples=HISTORIES, derandomize=False)
    tally = env.tally
    with capsys.disabled():
        print(
            "\npublish histories: " + ", ".join(f"{n} {what}" for what, n in sorted(tally.items()))
        )
    assert tally["histories"] >= HISTORIES
    # The histories did exercise what they are there for.
    assert tally["commits"] > 0
    assert tally["commits rejected"] > 0
    assert tally["deaths between now.json and the commit"] > 0
    assert tally["second publishers refused"] > 0
    assert tally["rogue publishers"] > 0
    assert tally["cuts passed"] > 0


def test_without_the_fence_the_same_histories_find_a_violation(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert "max(seq)" in publish.PUBLISH_WHERE
    monkeypatch.setattr(publish, "PUBLISH_WHERE", "\n")
    with pytest.raises(Violation) as found:
        # Shorter histories: the violation takes about eight steps, and shrinking a long
        # history to it takes minutes.
        run(env, examples=HISTORIES, derandomize=True, steps=30)
    notes: list[str] = getattr(found.value, "__notes__", [])
    shortest = [
        line
        for note in notes
        for line in note.splitlines()
        if line.startswith("state.") and "(self" not in line and not _is_invariant(line)
    ]
    with capsys.disabled():
        print(f"\nwithout the fence: {found.value}\n  " + "\n  ".join(shortest))
    assert "not the newest" in str(found.value)
