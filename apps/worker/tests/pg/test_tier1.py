"""One worker walking files through fetch, verify and load, against a real PostgreSQL 18.

The object store is in memory and the downloads are a dict, so each test says exactly what
GDELT serves. Time is passed in.
"""

import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from gdelt import Stream, parse_gkg
from worker import lake, stamps
from worker.feed import FetchError
from worker.ledger import backoff, fence, keys, tier1
from worker.ledger.fence import Listing, State
from worker.ledger.tier1 import Outcome, Point
from worker.store import MemoryStore

Connection = psycopg.Connection[tuple[Any, ...]]
Row = dict[str, Any]
ReadRow = Callable[[Stream, datetime], Row]
Build = Callable[..., bytes]

T0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
WEEK = timedelta(days=7)
EN = Stream.ENGLISH
TR = Stream.TRANSLATED


class World:
    """What GDELT serves, a store, and a clock the test moves."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}  # URL to bytes; a URL that is not here is a 404
        self.downloads: list[str] = []
        self.store = MemoryStore()
        self.now = T0

    def fetch(self, url: str) -> bytes:
        self.downloads.append(url)
        if url not in self.files:
            raise FetchError("HTTP 404")
        return self.files[url]

    def clock(self) -> datetime:
        return self.now

    def list_file(
        self, conn: Connection, stream: Stream, stamp: datetime, data: bytes, *, serve: bool = True
    ) -> None:
        """Enqueue a file whose listing matches `data`, and serve it unless told not to."""
        url = stamps.file_url(stream, stamp)
        md5 = hashlib.md5(data, usedforsecurity=False).hexdigest()
        fence.enlist(conn, [Listing(stream, stamp, url, len(data), md5)], now=self.now)
        if serve:
            self.files[url] = data

    def walk(self, conn: Connection):
        return tier1.walk(conn, self.store, self.fetch, clock=self.clock)

    def run(self, conn: Connection) -> Outcome:
        steps = self.walk(conn)
        while True:
            try:
                next(steps)
            except StopIteration as done:
                outcome: Outcome = done.value
                return outcome


def expected_objects(stream: Stream, stamp: datetime, zip_bytes: bytes) -> dict[str, bytes]:
    """The objects a loaded file leaves, computed without the ledger."""
    parsed = parse_gkg(tier1.unzip(zip_bytes))
    facts, display = lake.build(parsed.rows, parsed.stats)
    facts_key, display_key = keys.lake_keys(stream, stamp, facts, display)
    return {
        keys.raw_key(stream, stamp, zip_bytes): zip_bytes,
        facts_key: facts,
        display_key: display,
    }


@pytest.fixture
def world() -> World:
    return World()


# --- the walk with no faults --------------------------------------------------------------


def test_a_listed_file_is_fetched_verified_and_loaded_under_one_lease(
    conn: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    data = zipped(gkg_file(TR, T0, 12))
    world.list_file(conn, TR, T0, data)

    points: list[tuple[Point, State | None, State | None]] = []
    steps = world.walk(conn)
    outcome = None
    while outcome is None:
        try:
            at = next(steps)
            points.append((at.point, at.was, at.to))
        except StopIteration as done:
            outcome = done.value
    assert outcome is Outcome.LOADED
    assert points == [
        (Point.LEASED, None, None),
        (Point.DOWNLOADED, None, None),
        (Point.COMMIT, State.LISTED, State.FETCHED),
        (Point.COMMIT, State.FETCHED, State.VERIFIED),
        (Point.STORED, None, None),
        (Point.COMMIT, State.VERIFIED, State.LOADED),
    ]

    expected = expected_objects(TR, T0, data)
    assert world.store.objects == expected
    raw_key, facts_key, _ = expected
    found = row(TR, T0)
    assert found["state"] == "loaded"
    assert (found["raw_key"], found["parquet_key"], found["rows"]) == (raw_key, facts_key, 12)
    assert found["loaded_at"] == T0
    assert found["lease_token"] is None
    assert found["attempts"] == 1
    assert world.downloads == [stamps.file_url(TR, T0)]

    # The one column names both lake files.
    assert keys.display_key(found["parquet_key"]) in world.store.objects
    assert world.run(conn) is Outcome.IDLE


def test_a_second_worker_finds_nothing_to_do_and_repeats_nothing(
    connect: Callable[[], Connection], world: World, gkg_file: Build, zipped: Build
) -> None:
    a, b = connect(), connect()
    for n in range(3):
        stamp = T0 + timedelta(minutes=15 * n)
        world.list_file(a, EN, stamp, zipped(gkg_file(EN, stamp, 4)))
    outcomes = [world.run(a), world.run(b), world.run(a), world.run(b)]
    assert outcomes == [Outcome.LOADED] * 3 + [Outcome.IDLE]
    assert len(world.downloads) == 3
    assert len(world.store.objects) == 9


# --- 404, and release with backoff --------------------------------------------------------


def test_a_file_that_is_not_there_yet_is_put_off_and_loaded_when_it_arrives(
    conn: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    data = zipped(gkg_file(EN, T0, 6))
    world.list_file(conn, EN, T0, data, serve=False)

    assert world.run(conn) is Outcome.RELEASED
    found = row(EN, T0)
    assert (found["state"], found["last_error"]) == ("listed", "download failed: HTTP 404")
    assert found["lease_token"] is None
    assert found["next_attempt_at"] == T0 + backoff.delay(1)
    assert world.store.objects == {}

    assert world.run(conn) is Outcome.IDLE  # not before its time
    world.now = T0 + backoff.delay(1)
    assert world.run(conn) is Outcome.RELEASED
    assert row(EN, T0)["next_attempt_at"] == world.now + backoff.delay(2)

    world.files[stamps.file_url(EN, T0)] = data
    world.now += backoff.delay(2)
    assert world.run(conn) is Outcome.LOADED
    assert row(EN, T0)["attempts"] == 3
    assert world.store.objects == expected_objects(EN, T0, data)


def test_a_file_with_no_listing_is_not_downloaded(
    conn: Connection, world: World, row: ReadRow
) -> None:
    url = stamps.file_url(EN, T0)
    fence.enlist(conn, [Listing(EN, T0, url, None, None)], now=T0)
    world.files[url] = b"whatever is there cannot be checked"
    assert world.run(conn) is Outcome.RELEASED
    assert world.downloads == []
    assert row(EN, T0)["last_error"] == "no size or MD5 is listed"
    assert world.store.objects == {}


# --- a download that is not the listed file ------------------------------------------------


def test_a_download_that_differs_from_the_listing_goes_back_to_listed(
    conn: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    data = zipped(gkg_file(EN, T0, 6))
    world.list_file(conn, EN, T0, data)
    cut = data[: len(data) // 2]
    world.files[stamps.file_url(EN, T0)] = cut

    assert world.run(conn) is Outcome.RELEASED
    found = row(EN, T0)
    assert (found["state"], found["raw_key"]) == ("listed", None)
    assert found["last_error"] == "the size or MD5 of the download differs from the listing"
    assert found["next_attempt_at"] == T0 + backoff.delay(1)
    # What arrived was stored under its own MD5 before it was checked. Nothing names it.
    assert world.store.objects == {keys.raw_key(EN, T0, cut): cut}

    world.files[stamps.file_url(EN, T0)] = data
    world.now = T0 + backoff.delay(1)
    assert world.run(conn) is Outcome.LOADED
    assert world.store.objects == {keys.raw_key(EN, T0, cut): cut} | expected_objects(EN, T0, data)


def test_the_right_size_with_the_wrong_bytes_is_a_mismatch_too(
    conn: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    data = zipped(gkg_file(EN, T0, 6))
    world.list_file(conn, EN, T0, data)
    flipped = bytearray(data)
    flipped[len(data) // 2] ^= 0xFF
    world.files[stamps.file_url(EN, T0)] = bytes(flipped)
    assert world.run(conn) is Outcome.RELEASED
    assert row(EN, T0)["state"] == "listed"


# --- resuming after a worker died -----------------------------------------------------------


@pytest.mark.parametrize("steps_before_death", [1, 2, 3, 4, 5])
def test_a_walk_that_dies_is_resumed_from_its_last_commit(
    connect: Callable[[], Connection],
    world: World,
    row: ReadRow,
    gkg_file: Build,
    zipped: Build,
    steps_before_death: int,
) -> None:
    a, b = connect(), connect()
    data = zipped(gkg_file(TR, T0, 9))
    world.list_file(a, TR, T0, data)

    dying = world.walk(a)
    for _ in range(steps_before_death):
        next(dying)
    state_at_death = row(TR, T0)["state"]
    dying.close()  # the worker is gone; its lease is not

    assert world.run(b) is Outcome.IDLE  # the dead worker's lease still holds the row
    world.now = T0 + timedelta(minutes=5, seconds=1)
    resumed = world.walk(b)
    first = next(resumed)
    assert first.lease.state.value == state_at_death
    assert first.lease.attempts == 2
    resumed.close()

    world.now += timedelta(minutes=6)
    assert world.run(b) is Outcome.LOADED
    assert world.store.objects == expected_objects(TR, T0, data)
    assert row(TR, T0)["state"] == "loaded"
    # The dead walk had downloaded the file unless it died right after its lease. The walk that
    # finished downloads it only if the first never committed `fetched`: after that commit the
    # zip is read back from the store.
    died_with_the_zip = steps_before_death >= 2
    assert len(world.downloads) == died_with_the_zip + (state_at_death == "listed")


def test_a_fetched_row_whose_zip_is_gone_goes_back_to_listed(
    connect: Callable[[], Connection], world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    a, b = connect(), connect()
    data = zipped(gkg_file(EN, T0, 3))
    world.list_file(a, EN, T0, data)
    dying = world.walk(a)
    for _ in range(4):  # past the commit to `fetched`
        next(dying)
    dying.close()
    assert row(EN, T0)["state"] == "fetched"
    world.store.objects.clear()

    world.now = T0 + timedelta(minutes=6)
    assert world.run(b) is Outcome.RELEASED
    assert (row(EN, T0)["state"], row(EN, T0)["raw_key"]) == ("listed", None)


def test_a_verified_row_whose_zip_is_gone_stops_the_walk_loudly(
    connect: Callable[[], Connection], world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    a, b = connect(), connect()
    world.list_file(a, EN, T0, zipped(gkg_file(EN, T0, 3)))
    dying = world.walk(a)
    for _ in range(5):  # past the commit to `verified`
        next(dying)
    dying.close()
    before = row(EN, T0)
    assert before["state"] == "verified"
    world.store.objects.clear()

    world.now = T0 + timedelta(minutes=6)
    with pytest.raises(tier1.MissingObject):
        world.run(b)
    assert row(EN, T0)["state"] == "verified"


# --- the worker that wakes up after its lease -----------------------------------------------


@pytest.mark.parametrize("steps_before_pause", [1, 2, 3, 4, 5, 6])
def test_a_worker_that_pauses_past_its_lease_cannot_commit(
    connect: Callable[[], Connection],
    world: World,
    row: ReadRow,
    gkg_file: Build,
    zipped: Build,
    steps_before_pause: int,
) -> None:
    """The failure the fence exists for. A worker stops mid-walk for six minutes. Another
    takes the file and finishes it. The first wakes up believing it still holds the lease."""
    paused_conn, other = connect(), connect()
    data = zipped(gkg_file(EN, T0, 8))
    world.list_file(paused_conn, EN, T0, data)

    paused = world.walk(paused_conn)
    for _ in range(steps_before_pause):
        next(paused)

    world.now = T0 + timedelta(minutes=6)
    assert world.run(other) is Outcome.LOADED
    loaded = row(EN, T0)
    objects = dict(world.store.objects)

    outcome = None
    while outcome is None:
        try:
            next(paused)
        except StopIteration as done:
            outcome = done.value
    assert outcome is Outcome.FENCED
    assert row(EN, T0) == loaded  # the row is exactly as the second worker left it
    assert world.store.objects == objects  # and whatever the first one PUT was the same bytes
    assert objects == expected_objects(EN, T0, data)


def test_a_paused_worker_cannot_commit_over_a_lease_that_is_still_at_work(
    connect: Callable[[], Connection], world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    paused_conn, other = connect(), connect()
    world.list_file(paused_conn, EN, T0, zipped(gkg_file(EN, T0, 8)))

    paused = world.walk(paused_conn)
    at = next(paused)
    while at.point is not Point.COMMIT:  # stop just before `listed` to `fetched`
        at = next(paused)

    world.now = T0 + timedelta(minutes=6)
    current = world.walk(other)
    held = next(current).lease  # the same row, still `listed`, under a new token
    assert (held.stamp, held.state) == (T0, State.LISTED)
    assert held.token != at.lease.token

    with pytest.raises(StopIteration) as stopped:
        next(paused)  # its commit: right state, wrong token
    assert stopped.value.value is Outcome.FENCED
    found = row(EN, T0)
    assert (found["state"], found["lease_token"]) == ("listed", held.token)

    outcome = None
    while outcome is None:
        try:
            next(current)
        except StopIteration as done:
            outcome = done.value
    assert outcome is Outcome.LOADED


# --- gap after 7 days -----------------------------------------------------------------------


def test_a_file_that_never_appears_is_a_gap_after_seven_days(
    conn: Connection, admin: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    world.list_file(conn, TR, T0, zipped(gkg_file(TR, T0, 2)), serve=False)

    # It is retried, with backoff, for as long as it is less than 7 days old.
    tries = 0
    while world.now < T0 + WEEK - timedelta(minutes=30):
        assert world.run(conn) is Outcome.RELEASED
        tries += 1
        world.now = row(TR, T0)["next_attempt_at"]
    assert tries > 600  # four times an hour, once the backoff has reached its cap
    assert row(TR, T0)["state"] == "listed"

    world.now = T0 + WEEK
    assert world.run(conn) is Outcome.GAP
    found = row(TR, T0)
    assert (found["state"], found["last_error"]) == ("gap", "download failed: HTTP 404")
    gaps = admin.execute(
        "select stream::text, first_stamp, last_stamp, intervals, reason"
        "  from ingest.known_gap where first_stamp = %s",
        (T0,),
    ).fetchall()
    assert gaps == [("translated", T0, T0, 1, "download failed: HTTP 404")]
    assert world.run(conn) is Outcome.IDLE
    assert world.store.objects == {}


def test_a_file_that_arrives_on_the_eighth_day_is_still_loaded(
    conn: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    data = zipped(gkg_file(EN, T0, 2))
    world.list_file(conn, EN, T0, data)
    world.now = T0 + WEEK + timedelta(days=1)
    assert world.run(conn) is Outcome.LOADED
    assert row(EN, T0)["state"] == "loaded"


def test_after_seven_days_a_download_that_is_not_the_listed_file_is_a_gap(
    conn: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    data = zipped(gkg_file(EN, T0, 6))
    world.list_file(conn, EN, T0, data)
    world.files[stamps.file_url(EN, T0)] = data[:-1]
    world.now = T0 + WEEK
    assert world.run(conn) is Outcome.GAP
    assert row(EN, T0)["state"] == "gap"
    assert world.store.objects == {}  # the last try stores nothing


def test_a_file_with_no_listing_is_a_gap_after_seven_days(
    conn: Connection, world: World, row: ReadRow
) -> None:
    fence.enlist(conn, [Listing(EN, T0, stamps.file_url(EN, T0), None, None)], now=T0)
    world.now = T0 + WEEK
    assert world.run(conn) is Outcome.GAP
    assert row(EN, T0)["last_error"] == "no size or MD5 is listed"
    assert world.downloads == []


# --- broken lines, and dead -----------------------------------------------------------------


def test_broken_lines_are_counted_and_the_rest_of_the_file_is_loaded(
    conn: Connection, world: World, row: ReadRow, gkg_file: Build, zipped: Build
) -> None:
    data = zipped(gkg_file(TR, T0, 18, broken=2))  # exactly 10% of the lines
    world.list_file(conn, TR, T0, data)
    assert world.run(conn) is Outcome.LOADED
    found = row(TR, T0)
    assert (found["state"], found["rows"]) == ("loaded", 18)
    assert world.store.objects == expected_objects(TR, T0, data)


def test_a_file_with_more_than_ten_percent_broken_lines_is_parked_as_dead(
    conn: Connection,
    world: World,
    row: ReadRow,
    gkg_file: Build,
    zipped: Build,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = zipped(gkg_file(TR, T0, 17, broken=2))
    world.list_file(conn, TR, T0, data)
    with caplog.at_level(logging.ERROR, logger="worker.ledger.tier1"):
        assert world.run(conn) is Outcome.DEAD
    found = row(TR, T0)
    assert found["state"] == "dead"
    assert found["last_error"] == "2 of 19 lines fail the contract, more than 10% (column_count: 2)"
    assert found["lease_token"] is None
    assert (found["parquet_key"], found["rows"]) == (None, None)
    # The zip is kept; nothing from it reaches the lake.
    assert world.store.objects == {keys.raw_key(TR, T0, data): data}
    assert [record.message for record in caplog.records if "ALARM" in record.message]
    assert world.run(conn) is Outcome.IDLE


def test_a_file_that_cannot_be_opened_is_parked_as_dead(
    conn: Connection, world: World, row: ReadRow
) -> None:
    data = b"this is what GDELT listed, and it is not a zip"
    world.list_file(conn, EN, T0, data)
    assert world.run(conn) is Outcome.DEAD
    found = row(EN, T0)
    assert found["state"] == "dead"
    assert found["last_error"].startswith("cannot be opened: BadZipFile")
    assert world.store.objects == {keys.raw_key(EN, T0, data): data}
