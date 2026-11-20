"""The fence against a real PostgreSQL 18: leases, and commits that name the lease's token.

Time is passed in (`now`), so nothing here waits for a real lease to run out. The tests that
are about two transactions at the same moment use two connections, and threads where one of
them has to wait.
"""

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from gdelt import Stream
from worker import stamps
from worker.ledger import fence
from worker.ledger.fence import Lease, Listing, State

Connection = psycopg.Connection[tuple[Any, ...]]
Row = dict[str, Any]
ReadRow = Callable[[Stream, datetime], Row]

T0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
QUARTER = timedelta(minutes=15)
EN = Stream.ENGLISH
TR = Stream.TRANSLATED


def listing(
    stream: Stream, stamp: datetime, size: int | None = 10, md5: str | None = "a" * 32
) -> Listing:
    return Listing(stream, stamp, stamps.file_url(stream, stamp), size, md5)


def take(conn: Connection, now: datetime) -> Lease:
    held = fence.lease(conn, now=now)
    assert held is not None
    return held


def with_token(held: Lease, token: Any) -> Lease:
    return Lease(
        held.stream,
        held.stamp,
        held.state,
        token,
        held.url,
        held.size,
        held.md5,
        held.raw_key,
        held.attempts,
        held.overdue,
    )


# --- enlist -------------------------------------------------------------------------------


def test_a_listing_becomes_a_listed_row(conn: Connection, row: ReadRow) -> None:
    assert fence.enlist(conn, [listing(EN, T0, 123, "b" * 32)], now=T0 + MINUTE) == 1
    found = row(EN, T0)
    assert found["state"] == "listed"
    assert (found["size"], found["md5"]) == (123, "b" * 32)
    assert found["listed_at"] == T0 + MINUTE
    assert found["next_attempt_at"] == T0 + MINUTE
    assert found["attempts"] == 0
    assert found["lease_token"] is None


def test_the_same_stamp_listed_twice_is_one_row_and_keeps_its_first_listing(
    conn: Connection, admin: Connection, row: ReadRow
) -> None:
    assert fence.enlist(conn, [listing(EN, T0, 123, "b" * 32)], now=T0) == 1
    assert fence.enlist(conn, [listing(EN, T0, 999, "c" * 32)], now=T0 + QUARTER) == 0
    assert fence.enlist(conn, [listing(EN, T0), listing(TR, T0), listing(EN, T0)], now=T0) == 1
    count = admin.execute("select count(*) from ingest.interval").fetchone()
    assert count == (2,)
    found = row(EN, T0)
    assert (found["size"], found["md5"], found["listed_at"]) == (123, "b" * 32, T0)


def test_listing_again_does_not_touch_a_row_that_has_moved_on(
    conn: Connection, row: ReadRow
) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)
    assert fence.to_fetched(conn, held, "raw/x.zip", now=T0)
    before = row(EN, T0)
    assert fence.enlist(conn, [listing(EN, T0, 999, "c" * 32)], now=T0 + QUARTER) == 0
    assert row(EN, T0) == before


def test_the_newest_stamp_is_per_stream(conn: Connection) -> None:
    assert fence.newest_stamp(conn, EN) is None
    fence.enlist(conn, [listing(EN, T0), listing(EN, T0 + QUARTER), listing(TR, T0)], now=T0)
    assert fence.newest_stamp(conn, EN) == T0 + QUARTER
    assert fence.newest_stamp(conn, TR) == T0


# --- lease --------------------------------------------------------------------------------


def test_a_lease_writes_a_token_and_five_minutes(conn: Connection, row: ReadRow) -> None:
    fence.enlist(conn, [listing(EN, T0, 123, "b" * 32)], now=T0)
    held = take(conn, T0 + MINUTE)
    assert (held.stream, held.stamp, held.state) == (EN, T0, State.LISTED)
    assert (held.size, held.md5, held.raw_key) == (123, "b" * 32, None)
    assert held.attempts == 1
    assert not held.overdue
    found = row(EN, T0)
    assert found["lease_token"] == held.token
    assert found["lease_until"] == T0 + MINUTE + timedelta(minutes=5)
    assert found["attempts"] == 1
    assert found["state"] == "listed"


def test_with_nothing_ready_there_is_no_lease(conn: Connection) -> None:
    assert fence.lease(conn, now=T0) is None
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    take(conn, T0)
    assert fence.lease(conn, now=T0) is None


def test_the_newest_file_is_leased_first(conn: Connection) -> None:
    stamps = [T0 + QUARTER * n for n in (2, 0, 3, 1)]
    fence.enlist(conn, [listing(EN, stamp) for stamp in stamps], now=T0)
    fence.enlist(conn, [listing(TR, T0 + QUARTER * 3)], now=T0)
    order = [(held.stamp, held.stream) for held in (take(conn, T0) for _ in range(5))]
    assert order == [
        (T0 + QUARTER * 3, EN),
        (T0 + QUARTER * 3, TR),
        (T0 + QUARTER * 2, EN),
        (T0 + QUARTER, EN),
        (T0, EN),
    ]


def test_a_held_row_is_not_leased_until_its_lease_has_run_out(conn: Connection) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    first = take(conn, T0)
    assert fence.lease(conn, now=T0 + timedelta(minutes=4, seconds=59)) is None
    assert fence.lease(conn, now=T0 + timedelta(minutes=5)) is None  # until, not past
    second = take(conn, T0 + timedelta(minutes=5, seconds=1))
    assert second.token != first.token
    assert second.attempts == 2


def test_only_rows_that_tier_one_works_on_are_leased(conn: Connection, admin: Connection) -> None:
    states = ["listed", "fetched", "verified", "loaded", "published", "gap", "dead"]
    for index, state in enumerate(states):
        stamp = T0 + QUARTER * index
        fence.enlist(conn, [listing(EN, stamp)], now=T0)
        admin.execute(
            "update ingest.interval set state = %s::ingest.state where stamp = %s", (state, stamp)
        )
    leased = {held.state for held in (take(conn, T0) for _ in range(3))}
    assert leased == {State.LISTED, State.FETCHED, State.VERIFIED}
    assert fence.lease(conn, now=T0) is None


def test_the_time_is_the_databases_when_none_is_passed(
    conn: Connection, admin: Connection, row: ReadRow
) -> None:
    fence.enlist(conn, [listing(EN, T0)])
    before = admin.execute("select now()").fetchone()
    assert before is not None
    held = fence.lease(conn)
    assert held is not None
    found = row(EN, T0)
    # Measured against the database's own clock, not this machine's.
    assert before[0] - timedelta(seconds=5) < found["listed_at"] <= before[0]
    five = timedelta(minutes=5)
    assert before[0] + five <= found["lease_until"] < before[0] + five + timedelta(seconds=5)


def test_the_clock_is_the_databases(conn: Connection, admin: Connection) -> None:
    before = admin.execute("select now()").fetchone()
    assert before is not None
    read = fence.clock(conn)
    assert before[0] <= read < before[0] + timedelta(seconds=5)
    assert read.utcoffset() == timedelta(0)
    assert fence.clock(conn, now=T0) == T0


def test_the_ledger_refuses_a_connection_that_is_not_in_autocommit_mode(
    conn: Connection,
) -> None:
    conn.autocommit = False
    for call in (
        lambda: fence.lease(conn),
        lambda: fence.enlist(conn, []),
        lambda: fence.newest_stamp(conn, EN),
        lambda: fence.clock(conn),
    ):
        with pytest.raises(ValueError):
            call()


# --- two connections never lease the same row ---------------------------------------------


def test_a_second_lease_passes_over_a_row_another_transaction_is_leasing(
    connect: Callable[[], Connection],
) -> None:
    a, b = connect(), connect()
    fence.enlist(a, [listing(EN, T0), listing(EN, T0 + QUARTER)], now=T0)
    with a.transaction():
        first = take(a, T0)  # not committed yet: the row is locked
        assert first.stamp == T0 + QUARTER
        started = time.monotonic()
        second = take(b, T0)  # does not wait for a
        assert time.monotonic() - started < 5
        assert second.stamp == T0
        assert fence.lease(b, now=T0) is None  # and never takes the locked row
    assert fence.lease(b, now=T0) is None  # committed: the row is under a's lease


def test_a_lease_that_was_rolled_back_took_nothing(
    connect: Callable[[], Connection], row: ReadRow
) -> None:
    a, b = connect(), connect()
    fence.enlist(a, [listing(EN, T0)], now=T0)
    with a.transaction():
        take(a, T0)
        raise psycopg.Rollback()
    assert row(EN, T0)["lease_token"] is None
    assert take(b, T0).attempts == 1


def test_many_workers_at_once_never_lease_the_same_row(
    connect: Callable[[], Connection], admin: Connection
) -> None:
    workers, files = 8, 400
    conns = [connect() for _ in range(workers)]
    stamps = [T0 + QUARTER * n for n in range(files // 2)]
    fence.enlist(conns[0], [listing(stream, stamp) for stamp in stamps for stream in (EN, TR)])
    taken: list[list[tuple[Stream, datetime]]] = [[] for _ in range(workers)]
    failures: list[BaseException] = []
    start = threading.Barrier(workers)

    def work(index: int) -> None:
        try:
            start.wait()
            while (held := fence.lease(conns[index])) is not None:
                taken[index].append((held.stream, held.stamp))
        except BaseException as error:  # a thread must not die silently
            failures.append(error)

    threads = [threading.Thread(target=work, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not failures, failures
    everything = [interval for mine in taken for interval in mine]
    assert len(everything) == files
    assert len(set(everything)) == files  # no row twice
    assert sum(1 for mine in taken if mine) > 1  # more than one worker got work
    attempts = admin.execute("select min(attempts), max(attempts) from ingest.interval").fetchone()
    assert attempts == (1, 1)


# --- commits ------------------------------------------------------------------------------


def test_each_transition_commits_with_the_current_token(conn: Connection, row: ReadRow) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)

    assert fence.to_fetched(conn, held, "raw/x.zip", now=T0 + MINUTE)
    found = row(EN, T0)
    assert (found["state"], found["raw_key"]) == ("fetched", "raw/x.zip")
    assert found["lease_token"] == held.token
    assert found["lease_until"] == T0 + MINUTE + timedelta(minutes=5)  # pushed out again

    assert fence.to_verified(conn, held, now=T0 + MINUTE * 2)
    found = row(EN, T0)
    assert found["state"] == "verified"
    assert found["lease_until"] == T0 + MINUTE * 2 + timedelta(minutes=5)

    assert fence.to_loaded(conn, held, "lake/facts/x.parquet", 42, now=T0 + MINUTE * 3)
    found = row(EN, T0)
    assert (found["state"], found["parquet_key"], found["rows"]) == (
        "loaded",
        "lake/facts/x.parquet",
        42,
    )
    assert found["loaded_at"] == T0 + MINUTE * 3
    assert found["lease_token"] is None and found["lease_until"] is None
    assert found["seq"] is None and found["published_at"] is None  # the publisher's, not ours


COMMITS: list[tuple[str, State, Callable[[Connection, Lease], bool]]] = [
    ("to_fetched", State.LISTED, lambda c, h: fence.to_fetched(c, h, "raw/x.zip", now=T0)),
    ("to_verified", State.FETCHED, lambda c, h: fence.to_verified(c, h, now=T0)),
    ("to_loaded", State.VERIFIED, lambda c, h: fence.to_loaded(c, h, "lake/x", 1, now=T0)),
    ("to_dead", State.VERIFIED, lambda c, h: fence.to_dead(c, h, "bad", now=T0)),
    ("to_gap", State.LISTED, lambda c, h: fence.to_gap(c, h, "missing", now=T0)),
    (
        "release from listed",
        State.LISTED,
        lambda c, h: fence.release(c, h, State.LISTED, "404", MINUTE, now=T0),
    ),
    (
        "release from fetched",
        State.FETCHED,
        lambda c, h: fence.release(c, h, State.FETCHED, "md5", MINUTE, now=T0),
    ),
]
ALL_STATES = ["listed", "fetched", "verified", "loaded", "published", "gap", "dead"]


def leased_in(conn: Connection, admin: Connection, state: State) -> Lease:
    """A row put into `state` by hand, under a fresh lease."""
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    admin.execute("update ingest.interval set state = %s::ingest.state", (state.value,))
    return take(conn, T0)


@pytest.mark.parametrize(("name", "was", "commit"), COMMITS, ids=[c[0] for c in COMMITS])
def test_a_commit_with_a_stale_token_changes_nothing(
    conn: Connection,
    admin: Connection,
    row: ReadRow,
    name: str,
    was: State,
    commit: Callable[[Connection, Lease], bool],
) -> None:
    stale = leased_in(conn, admin, was)
    current = take(conn, T0 + timedelta(minutes=6))  # the lease ran out and was taken again
    assert current.token != stale.token
    before = row(EN, T0)
    gaps = admin.execute("select count(*) from ingest.known_gap").fetchone()

    assert commit(conn, stale) is False
    assert commit(conn, with_token(stale, uuid4())) is False  # a token nobody ever held
    assert row(EN, T0) == before
    assert admin.execute("select count(*) from ingest.known_gap").fetchone() == gaps

    assert commit(conn, current) is True  # the row's own lease still commits


@pytest.mark.parametrize(("name", "was", "commit"), COMMITS, ids=[c[0] for c in COMMITS])
def test_a_commit_from_the_wrong_state_changes_nothing(
    conn: Connection,
    admin: Connection,
    row: ReadRow,
    name: str,
    was: State,
    commit: Callable[[Connection, Lease], bool],
) -> None:
    held = leased_in(conn, admin, was)
    for other in ALL_STATES:
        if other == was.value:
            continue
        admin.execute("update ingest.interval set state = %s::ingest.state", (other,))
        before = row(EN, T0)
        assert commit(conn, held) is False, other
        assert row(EN, T0) == before
    assert admin.execute(
        "select count(*) from ingest.known_gap where first_stamp = %s", (T0,)
    ).fetchone() == (0,)


def test_a_commit_after_the_lease_ended_changes_nothing(conn: Connection, row: ReadRow) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)
    assert fence.to_fetched(conn, held, "raw/x.zip", now=T0)
    assert fence.to_verified(conn, held, now=T0)
    assert fence.to_loaded(conn, held, "lake/x", 1, now=T0)
    before = row(EN, T0)
    # The token is cleared, so nothing can change the row with it, not even the same commit.
    assert fence.to_loaded(conn, held, "lake/y", 2, now=T0) is False
    assert fence.to_dead(conn, held, "late", now=T0) is False
    assert row(EN, T0) == before


def test_a_commit_within_the_lease_time_out_needs_no_renewal(conn: Connection) -> None:
    # A lease that has run out but that nobody else has taken still commits: the fence is the
    # token, not the clock.
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)
    assert fence.to_fetched(conn, held, "raw/x.zip", now=T0 + timedelta(hours=1))


def test_a_stale_commit_that_waits_for_the_new_lease_is_rejected_when_it_resumes(
    connect: Callable[[], Connection], row: ReadRow
) -> None:
    """The check and the write are one statement. The old holder's commit arrives while the
    new lease is being written, waits for that transaction, and is then judged against the row
    as the new lease left it."""
    old, new = connect(), connect()
    fence.enlist(old, [listing(EN, T0)], now=T0)
    stale = take(old, T0)
    result: list[bool] = []
    with new.transaction():
        current = take(new, T0 + timedelta(minutes=6))
        waiter = threading.Thread(
            target=lambda: result.append(
                fence.to_fetched(old, stale, "raw/stale.zip", now=T0 + timedelta(minutes=6))
            )
        )
        waiter.start()
        time.sleep(0.5)
        assert waiter.is_alive()  # it is waiting for the row
        assert result == []
    waiter.join(timeout=30)
    assert result == [False]
    found = row(EN, T0)
    assert (found["state"], found["raw_key"], found["lease_token"]) == (
        "listed",
        None,
        current.token,
    )


def test_a_lease_does_not_wait_for_a_commit_in_flight(
    connect: Callable[[], Connection],
) -> None:
    holder, other = connect(), connect()
    fence.enlist(holder, [listing(EN, T0)], now=T0)
    held = take(holder, T0)
    with holder.transaction():
        assert fence.to_fetched(holder, held, "raw/x.zip", now=T0)  # written, not committed
        started = time.monotonic()
        # By the other worker's clock the lease has run out, but the row is locked: skipped.
        assert fence.lease(other, now=T0 + timedelta(minutes=6)) is None
        assert time.monotonic() - started < 5


# --- release with backoff -----------------------------------------------------------------


def test_a_release_ends_the_lease_and_sets_the_next_attempt(conn: Connection, row: ReadRow) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)
    wait = timedelta(minutes=2)
    assert fence.release(conn, held, State.LISTED, "HTTP 404", wait, now=T0 + MINUTE)
    found = row(EN, T0)
    assert found["state"] == "listed"
    assert found["lease_token"] is None and found["lease_until"] is None
    assert found["next_attempt_at"] == T0 + MINUTE + wait
    assert found["last_error"] == "HTTP 404"
    assert found["attempts"] == 1

    # Nothing holds the row while it waits, and nothing leases it before its time.
    assert fence.lease(conn, now=T0 + MINUTE + wait - timedelta(seconds=1)) is None
    again = take(conn, T0 + MINUTE + wait)
    assert again.attempts == 2
    assert again.token != held.token


def test_a_mismatched_file_goes_back_to_listed_without_its_raw_key(
    conn: Connection, row: ReadRow
) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)
    assert fence.to_fetched(conn, held, "raw/wrong.zip", now=T0)
    assert fence.release(conn, held, State.FETCHED, "MD5 differs", MINUTE, now=T0)
    found = row(EN, T0)
    assert (found["state"], found["raw_key"], found["last_error"]) == (
        "listed",
        None,
        "MD5 differs",
    )
    assert found["next_attempt_at"] == T0 + MINUTE


def test_only_listed_and_fetched_rows_are_released(conn: Connection, admin: Connection) -> None:
    held = leased_in(conn, admin, State.VERIFIED)
    with pytest.raises(ValueError):
        fence.release(conn, held, State.VERIFIED, "x", MINUTE, now=T0)


def test_a_waiting_row_does_not_block_the_rows_behind_it(conn: Connection) -> None:
    fence.enlist(conn, [listing(EN, T0), listing(EN, T0 + QUARTER)], now=T0)
    newest = take(conn, T0)
    assert newest.stamp == T0 + QUARTER
    assert fence.release(conn, newest, State.LISTED, "HTTP 404", QUARTER, now=T0)
    assert take(conn, T0).stamp == T0


# --- gap after 7 days, and dead -----------------------------------------------------------


def test_a_file_is_overdue_seven_days_after_it_was_listed(conn: Connection) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    week = timedelta(days=7)
    early = take(conn, T0 + week - timedelta(seconds=1))
    assert not early.overdue
    assert fence.release(conn, early, State.LISTED, "HTTP 404", MINUTE, now=T0)
    late = take(conn, T0 + week)
    assert late.overdue


def test_a_gap_is_recorded_with_its_known_gap_row(
    conn: Connection, admin: Connection, row: ReadRow
) -> None:
    fence.enlist(conn, [listing(TR, T0)], now=T0)
    week = T0 + timedelta(days=7)
    held = take(conn, week)
    assert fence.to_gap(conn, held, "download failed: HTTP 404", now=week)
    found = row(TR, T0)
    assert (found["state"], found["last_error"]) == ("gap", "download failed: HTTP 404")
    assert found["lease_token"] is None and found["lease_until"] is None
    gaps = admin.execute(
        "select stream::text, first_stamp, last_stamp, intervals, reason, recorded_at"
        "  from ingest.known_gap where first_stamp >= timestamptz '2026-01-01'"
    ).fetchall()
    assert gaps == [("translated", T0, T0, 1, "download failed: HTTP 404", week)]
    assert fence.lease(conn, now=week + timedelta(days=30)) is None  # a gap is never leased


def test_a_gap_and_its_known_gap_row_are_one_transaction(
    conn: Connection, admin: Connection, row: ReadRow
) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)
    # Make the second statement fail: the role loses its right to insert the gap row.
    admin.execute("revoke insert on ingest.known_gap from worker")
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            fence.to_gap(conn, held, "missing", now=T0)
    finally:
        admin.execute("grant insert on ingest.known_gap to worker")
    found = row(EN, T0)
    assert (found["state"], found["lease_token"]) == ("listed", held.token)
    assert fence.to_gap(conn, held, "missing", now=T0)


def test_a_dead_file_keeps_its_error_and_is_never_leased(conn: Connection, row: ReadRow) -> None:
    fence.enlist(conn, [listing(EN, T0)], now=T0)
    held = take(conn, T0)
    assert fence.to_fetched(conn, held, "raw/x.zip", now=T0)
    assert fence.to_verified(conn, held, now=T0)
    assert fence.to_dead(conn, held, "cannot be opened: BadZipFile", now=T0)
    found = row(EN, T0)
    assert (found["state"], found["last_error"]) == ("dead", "cannot be opened: BadZipFile")
    assert found["lease_token"] is None
    assert found["raw_key"] == "raw/x.zip"  # the zip stays named, for whoever looks
    assert fence.lease(conn, now=T0 + timedelta(days=30)) is None


# --- the fence is one line ----------------------------------------------------------------


def test_without_the_fence_line_a_stale_commit_goes_through(
    conn: Connection, monkeypatch: pytest.MonkeyPatch, row: ReadRow
) -> None:
    """This is the mutant the property test must catch. Here it is shown directly: take the
    token check out of the commit and the old holder writes over the new one."""
    fenced = fence.COMMIT_WHERE
    unfenced = fenced.replace("   and lease_token = %(token)s\n", "")
    assert unfenced != fenced

    fence.enlist(conn, [listing(EN, T0)], now=T0)
    stale = take(conn, T0)
    current = take(conn, T0 + timedelta(minutes=6))
    assert fence.to_fetched(conn, stale, "raw/stale.zip", now=T0) is False

    monkeypatch.setattr(fence, "COMMIT_WHERE", unfenced)
    assert fence.to_fetched(conn, stale, "raw/stale.zip", now=T0) is True
    found = row(EN, T0)
    assert (found["raw_key"], found["lease_token"]) == ("raw/stale.zip", current.token)
