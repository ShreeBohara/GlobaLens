"""The ledger's property test: 1,000 generated histories against a real PostgreSQL 18.

A history is a sequence of small steps chosen by Hypothesis: a file is listed (or listed
again), a free worker asks for work, a worker in the middle of a walk takes its next step, a
worker is killed, the clock moves. Three workers share the ledger, each on its own
connection. A walk is a generator that yields wherever the world can change under it
(`worker.ledger.tier1`), so between two steps of one worker the others can do anything, and
the clock can move past its lease: that is a paused worker.

What GDELT serves is fixed per file by its `Kind`, so every file has one right ending. The
invariants of the design note (§7.7) are checked after every step and again at the end:

1. Every listed file ends in exactly one terminal state, and it is the right one.
2. The successful commits of a file form one chain: each starts from the state the one before
   it left, so no transition is committed twice and none is skipped.
3. A commit whose token is not the row's current token never succeeds; and a commit with the
   current token and the expected state always does.
4. The object store holds what one worker with no faults would have written: the same keys
   with the same bytes, plus at most the downloads that differed from their listing, each
   under its own MD5.

Invariant 5 is about `now.json` and belongs to the publisher (task 11).

The last test removes the fence line from the commit and runs the same histories. They must
find a violation: a property test that cannot fail proves nothing.
"""

import hashlib
import logging
import os
from collections import Counter
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
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
from worker import lake, stamps
from worker.feed import FetchError
from worker.ledger import fence, keys, tier1
from worker.ledger.fence import Listing, State
from worker.ledger.tier1 import At, Outcome, Point
from worker.store import MemoryStore

Connection = psycopg.Connection[tuple[Any, ...]]
Build = Callable[..., bytes]
Interval = tuple[Stream, datetime]

HISTORIES = int(os.environ.get("GL_LEDGER_HISTORIES", "1000"))
WORKERS = 3
T0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
STAMPS = [T0 + timedelta(minutes=15 * n) for n in range(3)]
STREAMS = [Stream.ENGLISH, Stream.TRANSLATED]
SETTLE = timedelta(minutes=20)  # how long a LATE or GARBLED file misbehaves after its listing
TERMINAL = {State.LOADED, State.GAP, State.DEAD}
LEASABLE = {State.LISTED, State.FETCHED, State.VERIFIED}


SOME_STREAM = st.sampled_from(STREAMS)
SOME_STAMP = st.integers(0, len(STAMPS) - 1)
SOME_WORKER = st.integers(0, WORKERS - 1)


class Violation(AssertionError):
    """An invariant of the ledger does not hold."""


class Kind(Enum):
    GOOD = "good"  # served from the start
    LATE = "late"  # listed, but 404 for its first 20 minutes
    GARBLED = "garbled"  # the wrong bytes for its first 20 minutes
    BROKEN = "broken"  # more than 10% of its lines are broken
    MISSING = "missing"  # listed and never served
    WRONG = "wrong"  # always served with bytes that differ from the listing
    UNLISTED = "unlisted"  # enqueued with no size and no MD5


@dataclass(frozen=True)
class File:
    """One file of the generated world: its listing, what is served for it, how it must end."""

    kind: Kind
    listing: Listing
    payload: bytes  # the bytes the listing describes
    other: bytes  # the wrong bytes a GARBLED or WRONG file serves
    terminal: State
    required: dict[str, bytes]  # what one worker with no faults leaves in the store
    orphans: dict[str, bytes]  # what else may be there: a mismatched download, under its MD5
    raw_key: str | None  # what the finished row names
    parquet_key: str | None
    rows: int | None

    def served(self, age: timedelta) -> bytes | None:
        """The bytes a download gets `age` after the file was first listed. None is a 404."""
        if self.kind is Kind.MISSING or (self.kind is Kind.LATE and age < SETTLE):
            return None
        if self.kind is Kind.WRONG or (self.kind is Kind.GARBLED and age < SETTLE):
            return self.other
        return self.payload


SOME_KIND = st.sampled_from([Kind.GOOD, Kind.GOOD, Kind.GOOD, *Kind])


def make_file(stream: Stream, stamp: datetime, kind: Kind, gkg_file: Build, zipped: Build) -> File:
    broken = 2 if kind is Kind.BROKEN else 0
    payload = zipped(gkg_file(stream, stamp, 3, broken=broken))
    other = payload[:-9]
    md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    listed = kind is not Kind.UNLISTED
    listing = Listing(
        stream,
        stamp,
        stamps.file_url(stream, stamp),
        len(payload) if listed else None,
        md5 if listed else None,
    )
    raw = keys.raw_key(stream, stamp, payload)
    orphan = {keys.raw_key(stream, stamp, other): other}
    if kind in (Kind.GOOD, Kind.LATE, Kind.GARBLED):
        parsed = parse_gkg(tier1.unzip(payload))
        facts, display = lake.build(parsed.rows, parsed.stats)
        facts_key, display_key = keys.lake_keys(stream, stamp, facts, display)
        required = {raw: payload, facts_key: facts, display_key: display}
        orphans = orphan if kind is Kind.GARBLED else {}
        return File(
            kind, listing, payload, other, State.LOADED, required, orphans, raw, facts_key, 3
        )
    if kind is Kind.BROKEN:
        return File(kind, listing, payload, other, State.DEAD, {raw: payload}, {}, raw, None, None)
    orphans = orphan if kind is Kind.WRONG else {}
    return File(kind, listing, payload, other, State.GAP, {}, orphans, None, None, None)


class RecordingStore(MemoryStore):
    """Remembers every PUT, and fails the history if a key is ever given different bytes."""

    def __init__(self) -> None:
        super().__init__()
        self.puts: list[str] = []

    def put(self, key: str, data: bytes) -> None:
        self.puts.append(key)
        if key in self.objects and self.objects[key] != data:
            raise Violation(f"{key} was written again with different bytes")
        super().put(key, data)


@dataclass
class Env:
    """What every history shares: the connections, the file builders, and a running tally."""

    admin: Connection
    workers: list[Connection]
    poller: Connection
    gkg_file: Build
    zipped: Build
    files: dict[tuple[Stream, datetime, Kind], File] = field(default_factory=dict[Any, File])
    tally: Counter[str] = field(default_factory=Counter[str])

    def file(self, stream: Stream, stamp: datetime, kind: Kind) -> File:
        key = (stream, stamp, kind)
        if key not in self.files:
            self.files[key] = make_file(stream, stamp, kind, self.gkg_file, self.zipped)
        return self.files[key]


class Histories(RuleBasedStateMachine):
    env: ClassVar[Env]

    def __init__(self) -> None:
        super().__init__()
        env = self.env
        env.admin.execute("truncate ingest.interval")
        env.admin.execute(
            "delete from ingest.known_gap where first_stamp >= timestamptz '2026-01-01'"
        )
        env.tally["histories"] += 1
        self.now = T0
        self.store = RecordingStore()
        self.world: dict[Interval, File] = {}
        self.first_listed: dict[Interval, datetime] = {}
        # The state each file is in according to the commits that succeeded, and nothing else.
        self.model: dict[Interval, State] = {}
        self.endings: Counter[Interval] = Counter()
        self.walks: list[Generator[At, None, Outcome] | None] = [None] * WORKERS
        self.at: list[At | None] = [None] * WORKERS
        self.failed = False

    # --- helpers --------------------------------------------------------------------------

    def check(self, holds: bool, message: str) -> None:
        if not holds:
            self.failed = True
            raise Violation(message)

    def fetch(self, url: str) -> bytes:
        for interval, file in self.world.items():
            if file.listing.url == url:
                data = file.served(self.now - self.first_listed[interval])
                if data is None:
                    raise FetchError("HTTP 404")
                return data
        raise AssertionError(f"a walk asked for a file nobody listed: {url}")

    def rows(self) -> dict[Interval, dict[str, Any]]:
        with self.env.admin.cursor(row_factory=dict_row) as cursor:
            cursor.execute("select * from ingest.interval")
            return {(Stream(found["stream"]), found["stamp"]): found for found in cursor}

    def next_lease(self) -> Interval | None:
        """The row the lease statement must pick now: the newest that is ready and not held."""
        ready = [
            interval
            for interval, found in self.rows().items()
            if State(found["state"]) in LEASABLE
            and found["next_attempt_at"] <= self.now
            and (found["lease_until"] is None or found["lease_until"] < self.now)
        ]
        return min(ready, key=lambda i: (-i[1].timestamp(), STREAMS.index(i[0])), default=None)

    def advance(self, worker: int) -> Outcome | None:
        """Let one worker take its next step, and judge the step if it was a commit."""
        walk = self.walks[worker]
        assert walk is not None
        at = self.at[worker]
        committing = at is not None and at.point is Point.COMMIT
        before = self.rows() if committing else {}
        outcome: Outcome | None = None
        try:
            self.at[worker] = next(walk)
        except StopIteration as done:
            outcome = done.value
            self.walks[worker] = None
            self.at[worker] = None
        if at is not None and committing:
            self.judge(at, before, rejected=outcome is Outcome.FENCED)
        return outcome

    def judge(self, at: At, before: dict[Interval, dict[str, Any]], *, rejected: bool) -> None:
        assert at.was is not None and at.to is not None
        interval = (at.lease.stream, at.lease.stamp)
        row = before[interval]
        current = row["lease_token"] == at.lease.token
        expected = State(row["state"]) is at.was
        what = f"{at.was} to {at.to} of {interval[0]} {interval[1]:%H:%M}"
        if rejected:
            self.env.tally["commits rejected"] += 1
            if not current:
                self.env.tally["stale-token commits rejected"] += 1
            self.check(self.rows() == before, f"the rejected commit {what} changed a row")
            self.check(
                not (current and expected),
                f"the commit {what} was rejected though it held the row's token and state",
            )
            return
        self.env.tally["commits"] += 1
        # Invariant 3.
        self.check(
            current, f"the commit {what} succeeded with a token that is not the row's current token"
        )
        # Invariant 2: one chain of commits per file.
        self.check(
            self.model[interval] is at.was,
            f"the commit {what} succeeded, but the commits before it left {self.model[interval]}",
        )
        self.model[interval] = at.to
        if at.to in TERMINAL:
            self.endings[interval] += 1

    # --- the steps a history is made of ---------------------------------------------------
    #
    # Hypothesis picks the next rule evenly among those that may run, so a step that should
    # happen more often than the others is written as more than one rule.

    def list_one(self, stream: Stream, index: int, kind: Kind) -> None:
        interval = (stream, STAMPS[index])
        new = interval not in self.world
        if new:
            self.world[interval] = self.env.file(stream, STAMPS[index], kind)
            self.first_listed[interval] = self.now
            self.model[interval] = State.LISTED
        else:
            self.env.tally["duplicate listings"] += 1
        added = fence.enlist(self.env.poller, [self.world[interval].listing], now=self.now)
        self.check(added == (1 if new else 0), f"listing {interval} added {added} rows")

    @initialize(
        first=st.lists(st.tuples(SOME_STREAM, SOME_STAMP, SOME_KIND), min_size=1, max_size=4)
    )
    def first_listings(self, first: list[tuple[Stream, int, Kind]]) -> None:
        """Every history opens with some files already listed."""
        for stream, index, kind in first:
            self.list_one(stream, index, kind)

    @rule(stream=SOME_STREAM, index=SOME_STAMP, kind=SOME_KIND)
    def list_file(self, stream: Stream, index: int, kind: Kind) -> None:
        """The poller lists a file. Listing it again must change nothing."""
        self.list_one(stream, index, kind)

    def start_one(self, pick: int) -> None:
        free = [index for index, walk in enumerate(self.walks) if walk is None]
        worker = free[pick % len(free)]
        due = self.next_lease()
        self.walks[worker] = tier1.walk(
            self.env.workers[worker], self.store, self.fetch, clock=lambda: self.now
        )
        outcome = self.advance(worker)
        at = self.at[worker]
        if due is None:
            self.check(outcome is Outcome.IDLE, "a lease was given with no row ready")
            return
        self.check(at is not None and at.point is Point.LEASED, "a ready row was not leased")
        assert at is not None
        self.env.tally["leases"] += 1
        held = at.lease
        self.check((held.stream, held.stamp) == due, f"leased {held.stamp}, not the newest ready")
        self.check(held.state is self.model[due], "the lease saw a state no commit had written")

    def step_one(self, pick: int) -> None:
        busy = [index for index, walk in enumerate(self.walks) if walk is not None]
        self.advance(busy[pick % len(busy)])

    @precondition(lambda self: any(walk is None for walk in self.walks))
    @rule(pick=SOME_WORKER)
    def start(self, pick: int) -> None:
        """A free worker asks the ledger for work."""
        self.start_one(pick)

    @precondition(lambda self: any(walk is None for walk in self.walks))
    @rule(pick=SOME_WORKER)
    def start_another(self, pick: int) -> None:
        self.start_one(pick)

    @precondition(lambda self: any(walk is not None for walk in self.walks))
    @rule(pick=SOME_WORKER)
    def step(self, pick: int) -> None:
        """A worker in the middle of a walk does its next thing."""
        self.step_one(pick)

    @precondition(lambda self: any(walk is not None for walk in self.walks))
    @rule(pick=SOME_WORKER)
    def step_again(self, pick: int) -> None:
        self.step_one(pick)

    @precondition(lambda self: any(walk is not None for walk in self.walks))
    @rule(pick=SOME_WORKER)
    def step_once_more(self, pick: int) -> None:
        self.step_one(pick)

    @precondition(lambda self: any(walk is not None for walk in self.walks))
    @rule(pick=SOME_WORKER)
    def kill(self, pick: int) -> None:
        """A worker dies where it stands. Its lease stays until it runs out."""
        busy = [index for index, walk in enumerate(self.walks) if walk is not None]
        worker = busy[pick % len(busy)]
        walk = self.walks[worker]
        assert walk is not None
        walk.close()
        self.walks[worker] = None
        self.at[worker] = None
        self.env.tally["kills"] += 1

    @rule(
        delta=st.sampled_from(
            [
                timedelta(seconds=1),
                timedelta(minutes=2),
                timedelta(minutes=6),  # past a lease: whoever is mid-walk has been paused
                timedelta(minutes=6),
                timedelta(minutes=6),
                timedelta(minutes=20),  # past any backoff
                timedelta(days=7),  # everything still waiting is overdue
            ]
        )
    )
    def tick(self, delta: timedelta) -> None:
        self.now += delta
        if delta > timedelta(minutes=5) and any(walk is not None for walk in self.walks):
            self.env.tally["pauses past a lease"] += 1

    # --- after every step -----------------------------------------------------------------

    @invariant()
    def the_ledger_is_what_the_commits_made_it(self) -> None:
        rows = self.rows()
        self.check(set(rows) == set(self.world), "the ledger's rows are not the listed files")
        for interval, row in rows.items():
            state = State(row["state"])
            self.check(
                state is self.model[interval],
                f"{interval} is {state}, but its commits add up to {self.model[interval]}",
            )
            if state in TERMINAL:
                self.check(row["lease_token"] is None, f"{interval} is {state} and still leased")
                self.check(self.endings[interval] == 1, f"{interval} ended more than once")

    @invariant()
    def the_store_holds_only_what_a_faultless_run_would_write(self) -> None:
        allowed: dict[str, bytes] = {}
        for file in self.world.values():
            allowed |= file.required | file.orphans
        for key, data in self.store.objects.items():
            self.check(key in allowed, f"{key} is not an object a faultless run writes")
            self.check(data == allowed[key], f"{key} holds the wrong bytes")
        for interval, file in self.world.items():
            if self.model[interval] in (State.LOADED, State.DEAD):
                missing = set(file.required) - set(self.store.objects)
                self.check(not missing, f"{interval} is finished without {sorted(missing)}")

    # --- at the end -----------------------------------------------------------------------

    def teardown(self) -> None:
        for walk in self.walks:
            if walk is not None:
                walk.close()  # whoever is still mid-walk never comes back
        if self.failed:
            return
        # A week later, one worker with nothing going wrong finishes every file.
        self.walks = [None] * WORKERS
        self.at = [None] * WORKERS
        self.now += timedelta(days=7, minutes=10)
        for _ in range(8 * len(STAMPS) * len(STREAMS) + 8):
            self.walks[0] = tier1.walk(
                self.env.workers[0], self.store, self.fetch, clock=lambda: self.now
            )
            outcome = self.advance(0)
            while outcome is None:  # None while the walk has more steps
                outcome = self.advance(0)
            if outcome is Outcome.IDLE:
                if all(state in TERMINAL for state in self.model.values()):
                    break
                self.now += timedelta(minutes=16)  # a released file is waiting out its backoff
        self.the_ledger_is_what_the_commits_made_it()
        self.the_store_holds_only_what_a_faultless_run_would_write()

        rows = self.rows()
        required: dict[str, bytes] = {}
        orphans: dict[str, bytes] = {}
        for interval, file in self.world.items():
            row = rows[interval]
            # Invariant 1.
            self.check(
                self.model[interval] is file.terminal,
                f"the {file.kind.value} file {interval} ended {self.model[interval]}, "
                f"not {file.terminal}",
            )
            named = (row["raw_key"], row["parquet_key"], row["rows"])
            self.check(
                named == (file.raw_key, file.parquet_key, file.rows),
                f"{interval} names {named}",
            )
            required |= file.required
            orphans |= file.orphans
        # Invariant 4.
        stored = set(self.store.objects)
        self.check(set(required) <= stored, f"missing objects: {sorted(set(required) - stored)}")
        self.check(
            stored <= set(required) | set(orphans),
            f"objects no faultless run writes: {sorted(stored - set(required) - set(orphans))}",
        )
        gaps = self.env.admin.execute(
            "select stream::text, first_stamp, last_stamp, intervals from ingest.known_gap"
            " where first_stamp >= timestamptz '2026-01-01' order by 1, 2"
        ).fetchall()
        expected = sorted(
            (stream.value, stamp, stamp, 1)
            for (stream, stamp), state in self.model.items()
            if state is State.GAP
        )
        self.check(gaps == expected, f"the known gaps are {gaps}")
        self.env.tally["files finished"] += len(self.world)


@pytest.fixture(autouse=True)
def quiet_walks() -> Iterator[None]:
    """Thousands of walks log their releases, gaps and alarms. Nobody reads them here."""
    logger = logging.getLogger("worker.ledger.tier1")
    level = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    yield
    logger.setLevel(level)


@pytest.fixture
def env(
    admin: Connection, connect: Callable[[], Connection], gkg_file: Build, zipped: Build
) -> Env:
    return Env(
        admin=admin,
        workers=[connect() for _ in range(WORKERS)],
        poller=connect(),
        gkg_file=gkg_file,
        zipped=zipped,
    )


def _is_invariant(line: str) -> bool:
    return line.startswith(("state.the_ledger_is", "state.the_store_holds"))


def run(env: Env, *, examples: int, derandomize: bool) -> None:
    Histories.env = env
    run_state_machine_as_test(
        Histories,
        settings=settings(
            max_examples=examples,
            stateful_step_count=60,
            deadline=None,
            database=None,  # nothing is written into the repository
            derandomize=derandomize,
            report_multiple_bugs=False,
            print_blob=True,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
        ),
    )


def test_a_thousand_histories_keep_every_invariant(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    run(env, examples=HISTORIES, derandomize=False)
    tally = env.tally
    with capsys.disabled():
        print(
            "\nledger histories: " + ", ".join(f"{n} {what}" for what, n in sorted(tally.items()))
        )
    assert tally["histories"] >= HISTORIES
    # The histories did exercise what they are there for.
    assert tally["stale-token commits rejected"] > 0
    assert tally["kills"] > 0
    assert tally["pauses past a lease"] > 0
    assert tally["duplicate listings"] > 0


def test_without_the_fence_the_same_histories_find_a_violation(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fenced = fence.COMMIT_WHERE
    unfenced = fenced.replace("   and lease_token = %(token)s\n", "")
    assert unfenced != fenced and "lease_token" not in unfenced
    monkeypatch.setattr(fence, "COMMIT_WHERE", unfenced)
    with pytest.raises(Violation) as found:
        run(env, examples=HISTORIES, derandomize=True)
    # Hypothesis attaches the shortest history that fails to the error, as notes. Shown without
    # the invariant checks it lists after every step.
    notes: list[str] = getattr(found.value, "__notes__", [])
    shortest = [
        line
        for note in notes
        for line in note.splitlines()
        if line.startswith("state.") and "(self" not in line and not _is_invariant(line)
    ]
    with capsys.disabled():
        print(f"\nwithout the fence: {found.value}\n  " + "\n  ".join(shortest))
    assert shortest and shortest[-1] == "state.teardown()"
    assert "not the row's current token" in str(found.value)
