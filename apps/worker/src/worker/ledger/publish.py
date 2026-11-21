"""The publisher: `loaded → published`, in passes (docs/design/p1.md §7.5).

One process publishes. It holds a session-level advisory lock on its connection for as long as
it runs, and a second process that cannot take the lock exits (`worker.publisher`). The lock
decides who publishes; the pass number is the fence.

A pass:

1. Looks at the ledger: is anything ready to publish, or has an hourly cut passed? If not, it
   stops there and takes no number.
2. Takes the next pass number from `ingest.publish_pass`, in a transaction of its own. A pass
   that dies after this burns its number: `seq` has gaps and never repeats.
3. Reads the ledger again, now that it has its number: the intervals that are ready, and those
   already published in the window. A commit that landed before this read is in it; a commit
   after it can only come from a pass with a larger number.
4. PUTs every object of its plan (`worker.dataplane`): shards, compactions, title indexes, the
   hourly manifest, the pass manifest, each after everything it names. Every key must be the
   hash of its bytes; an object already in the store is not PUT again.
5. Checks that it is still the newest pass, then PUTs `now.json`, last.
6. Commits, in one transaction: the ready intervals become `published` with the pass's `seq`
   and `published_at`, and the pass records its manifest and its writes. Both statements name
   the pass number: they change rows only while no later pass exists.

A `loaded` row carries no lease token (`to_loaded` clears it), so the publisher cannot name a
row's token the way tier 1 does. It names its pass number instead, in the same statement as the
write. A pass that is no longer the newest changes 0 rows, rolls back, and the publisher stops.
Taking a number and committing each hold a second advisory lock, SERIAL, for the length of their
transaction, so that no number can be taken while a commit is checking that its own is the
largest: tier 1's check is on the row it writes, which PostgreSQL re-reads under the row lock,
but this one is on another table, which a statement reads as it was when the statement began.
Both transactions run at READ COMMITTED, stated as their first statement, so that the statements
after the lock read what was committed before it was granted.

A crash anywhere leaves the ledger as the last commit made it. Before step 5, `now.json` still
names the last complete pass; between steps 5 and 6, it names this pass, whose objects all
exist, and the intervals are still `loaded`: the next pass publishes them again under a new
number, with the same shard keys.

`now.json` is a plain PUT in P1. A publisher that is paused between its check (step 5) and its
PUT while another pass runs could still write an older `now.json`; the conditional PUT and the
ledger epoch of P2 close that.

Time is the database's. `clock` is for tests only, as in `worker.ledger.tier1`.

The walkthrough is WALKTHROUGH.md, beside this file.
"""

from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, LiteralString

from gdelt import Stream
from psycopg.types.json import Jsonb

from worker.dataplane import NOW_KEY, DataPlane, Interval, Plan, is_content_key, window_start
from worker.ledger import fence
from worker.ledger.fence import Connection
from worker.store import ObjectStore

__all__ = [
    "LOCK",
    "PUBLISH_WHERE",
    "READY_WAIT",
    "SERIAL",
    "At",
    "Outcome",
    "Point",
    "Result",
    "Writes",
    "commit",
    "is_newest",
    "lock",
    "published",
    "ready",
    "run",
    "run_pass",
    "take_seq",
    "unlock",
]

LOCK = 0x474C5042
"""The publisher's advisory lock: one bigint key, the letters GLPB, easy to find in pg_locks."""

SERIAL = LOCK + 1
"""The transaction-level advisory lock that orders taking a number and committing."""

READY_WAIT = timedelta(minutes=15)
"""How long a loaded stream waits for the other stream of its stamp (the plan's resolve rule,
§7 step 5)."""

Clock = Callable[[], datetime | None]  # None means the database's own time

_NOW: LiteralString = "coalesce(%(now)s::timestamptz, now())"

_LOCK: LiteralString = "select pg_try_advisory_lock(%(key)s::bigint)"
_UNLOCK: LiteralString = "select pg_advisory_unlock(%(key)s::bigint)"
_SERIAL: LiteralString = "select pg_advisory_xact_lock(%(serial)s::bigint)"
# The first statement of both transactions below. Under READ COMMITTED each statement reads what
# was committed before it began, so the statements after SERIAL see every number taken before
# the lock was granted. Under REPEATABLE READ they would all read the snapshot of the first
# statement, taken before the wait. Stated here so that no default can change it.
_READ_COMMITTED: LiteralString = "set transaction isolation level read committed"

# Ready: loaded, and either the other stream of the stamp has finished one way or another
# (loaded, published, gap or dead), or this one has waited READY_WAIT for it.
_READY: LiteralString = f"""
select i.stream, i.stamp, i.parquet_key, i.listed_at
  from ingest.interval i
 where i.state = 'loaded'
   and (i.loaded_at <= {_NOW} - %(wait)s
        or exists (select 1
                     from ingest.interval o
                    where o.stamp = i.stamp
                      and o.stream <> i.stream
                      and o.state in ('loaded', 'published', 'gap', 'dead')))
 order by i.stamp, i.stream
"""

_PUBLISHED: LiteralString = """
select stream, stamp, parquet_key, listed_at, seq, published_at
  from ingest.interval
 where state = 'published'
   and stamp >= %(since)s
 order by stamp, stream
"""

# The pass number: one more than any number ever taken. The table is never deleted from, and
# its primary key refuses a number twice, so a number is never taken again.
_TAKE_SEQ: LiteralString = f"""
insert into ingest.publish_pass (seq, started_at)
select coalesce(max(seq), 0) + 1, {_NOW}
  from ingest.publish_pass
returning seq
"""

# The end of both statements of the commit. The pass's number is its fence.
PUBLISH_WHERE: LiteralString = """
   and %(seq)s = (select max(seq) from ingest.publish_pass)
"""

_IS_NEWEST: LiteralString = "select %(seq)s = (select max(seq) from ingest.publish_pass)"

_MARK: LiteralString = f"""
update ingest.interval
   set state = 'published', seq = %(seq)s, published_at = {_NOW}
 where (stream, stamp) in (select * from unnest(%(streams)s::ingest.stream[],
                                                %(stamps)s::timestamptz[]))
   and state = 'loaded'
"""

_FINISH: LiteralString = f"""
update ingest.publish_pass
   set manifest_key = %(manifest)s, finished_at = {_NOW}, objects = %(objects)s
 where seq = %(seq)s
   and finished_at is null
"""


def _autocommit(conn: Connection) -> None:
    if not conn.autocommit:
        raise ValueError("the publisher needs a connection in autocommit mode")


def lock(conn: Connection) -> bool:
    """Take the publisher's lock for this connection's session. False if another holds it."""
    _autocommit(conn)
    row = conn.execute(_LOCK, {"key": LOCK}).fetchone()
    assert row is not None
    return bool(row[0])


def unlock(conn: Connection) -> None:
    """Give the lock back. Closing the connection does the same."""
    _autocommit(conn)
    conn.execute(_UNLOCK, {"key": LOCK})


def ready(conn: Connection, *, now: datetime | None = None) -> list[Interval]:
    """The loaded intervals that may be published now, oldest stamp first."""
    _autocommit(conn)
    rows = conn.execute(_READY, {"now": now, "wait": READY_WAIT}).fetchall()
    return [Interval(Stream(r[0]), r[1], r[2], r[3]) for r in rows]


def published(conn: Connection, since: datetime) -> list[Interval]:
    """The published intervals whose stamp is `since` or later."""
    _autocommit(conn)
    rows = conn.execute(_PUBLISHED, {"since": since}).fetchall()
    return [Interval(Stream(r[0]), r[1], r[2], r[3], seq=r[4], published_at=r[5]) for r in rows]


def take_seq(conn: Connection, *, now: datetime | None = None) -> int:
    """Take the next pass number, in a transaction of its own."""
    _autocommit(conn)
    with conn.transaction():
        conn.execute(_READ_COMMITTED)
        conn.execute(_SERIAL, {"serial": SERIAL})
        row = conn.execute(_TAKE_SEQ, {"now": now}).fetchone()
    assert row is not None
    seq: int = row[0]
    return seq


def is_newest(conn: Connection, seq: int) -> bool:
    """True while no pass has taken a number after `seq`."""
    _autocommit(conn)
    row = conn.execute(_IS_NEWEST, {"seq": seq}).fetchone()
    assert row is not None
    return bool(row[0])


class _Fenced(Exception):
    """Raised inside the commit's transaction to roll it back."""


def commit(
    conn: Connection,
    seq: int,
    intervals: Sequence[Interval],
    manifest_key: str,
    objects: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Mark `intervals` published by pass `seq` and finish the pass, in one transaction.

    False means nothing changed: a later pass exists, or an interval was no longer `loaded`.
    The caller stops there. It does not look for the reason.
    """
    _autocommit(conn)
    values = {
        "serial": SERIAL,
        "seq": seq,
        "streams": [i.stream.value for i in intervals],
        "stamps": [i.stamp for i in intervals],
        "manifest": manifest_key,
        "objects": Jsonb(objects),
        "now": now,
    }
    try:
        with conn.transaction():
            conn.execute(_READ_COMMITTED)
            conn.execute(_SERIAL, values)
            if intervals and conn.execute(_MARK + PUBLISH_WHERE, values).rowcount != len(intervals):
                raise _Fenced
            if conn.execute(_FINISH + PUBLISH_WHERE, values).rowcount != 1:
                raise _Fenced
    except _Fenced:
        return False
    return True


# --- One pass ----------------------------------------------------------------------------


class Point(StrEnum):
    """Where a pass can be between two steps."""

    NUMBERED = "numbered"  # the pass number is taken; nothing is written
    STORED = "stored"  # an object is in the store and more follow
    WRITTEN = "written"  # every object is in the store; the check and now.json are next
    COMMIT = "commit"  # now.json is written; the commit is next


@dataclass(frozen=True, slots=True)
class At:
    """What a pass yields: where it is, its number, and the object it just stored."""

    point: Point
    seq: int
    key: str | None = None


class Outcome(StrEnum):
    """How a pass ended."""

    IDLE = "idle"  # nothing was due; no number was taken
    PUBLISHED = "published"
    FENCED = "fenced"  # a later pass exists, or the commit changed no row


@dataclass(slots=True)
class Writes:
    """What a pass did to the store: PUTs by object class (Class A operations), the HEADs it
    asked first (Class B), and the objects it found already there."""

    heads: int = 0
    skipped: int = 0
    puts: dict[str, list[int]] = field(default_factory=dict[str, list[int]])

    def put(self, kind: str, size: int) -> None:
        count = self.puts.setdefault(kind, [0, 0])
        count[0] += 1
        count[1] += size

    def json(self) -> dict[str, Any]:
        return {
            "heads": self.heads,
            "skipped": self.skipped,
            "puts": {
                kind: {"n": n, "bytes": size} for kind, (n, size) in sorted(self.puts.items())
            },
        }


@dataclass(frozen=True, slots=True)
class Result:
    outcome: Outcome
    seq: int | None = None
    published: tuple[Interval, ...] = ()
    plan: Plan | None = None
    writes: Writes | None = None


def _database_time() -> datetime | None:
    return None


def run_pass(
    conn: Connection, store: ObjectStore, plane: DataPlane, *, clock: Clock = _database_time
) -> Generator[At, None, Result]:
    """One pass, as the module docstring describes it. `clock` is for tests only."""
    now = fence.clock(conn, now=clock())
    if not plane.due(now, ready(conn, now=now), published(conn, window_start(now))):
        return Result(Outcome.IDLE)

    seq = take_seq(conn, now=clock())
    yield At(Point.NUMBERED, seq)

    now = fence.clock(conn, now=clock())
    intervals = ready(conn, now=now)
    plan = plane.plan(
        seq=seq, now=now, ready=intervals, published=published(conn, window_start(now))
    )
    writes = Writes()
    for put in plan.puts:
        if not is_content_key(put.key, put.data):
            raise ValueError(f"{put.key} is not the hash of its bytes")
        writes.heads += 1
        if store.exists(put.key):
            writes.skipped += 1
        else:
            store.put(put.key, put.data)
            writes.put(put.kind, len(put.data))
        yield At(Point.STORED, seq, put.key)
    yield At(Point.WRITTEN, seq)

    # No yield between the check and the PUT: see the module docstring.
    if not is_newest(conn, seq):
        return Result(Outcome.FENCED, seq)
    store.put(NOW_KEY, plan.now)
    writes.put("now", len(plan.now))
    yield At(Point.COMMIT, seq)

    if not commit(conn, seq, intervals, plan.manifest_key, writes.json(), now=clock()):
        return Result(Outcome.FENCED, seq)
    plane.committed(plan)
    return Result(Outcome.PUBLISHED, seq, tuple(intervals), plan, writes)


def run(conn: Connection, store: ObjectStore, plane: DataPlane) -> Result:
    """Run one pass to its end."""
    steps = run_pass(conn, store, plane)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            result: Result = done.value
            return result
