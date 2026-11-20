"""The fence: leases on `ingest.interval`, and commits that name the lease's token.

A row of `ingest.interval` is one 15-minute file of one stream. A worker may change a row only
while it holds the row's lease, and it proves that with the random token the lease wrote into
the row: every later write names that token in its WHERE clause. If another worker has taken
the row since, the token no longer matches, the write changes 0 rows, and the worker stops.
The check and the write are one statement, so there is no moment between them.

A lease and a commit are each one statement, and so one transaction. `to_gap` is two statements
and `enlist` one insert per file, each in one explicit transaction. The connection must be in
autocommit mode: then each call commits on its own, and a caller that wants more work in the
same transaction opens it with `conn.transaction()`.

Time is the database's. Each function takes `now` for tests only; production never passes it.

The walkthrough is WALKTHROUGH.md, beside this file.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, LiteralString
from uuid import UUID

import psycopg
from gdelt import Stream

__all__ = [
    "COMMIT_WHERE",
    "Lease",
    "Listing",
    "State",
    "clock",
    "enlist",
    "lease",
    "newest_stamp",
    "release",
    "to_dead",
    "to_fetched",
    "to_gap",
    "to_loaded",
    "to_verified",
]

Connection = psycopg.Connection[tuple[Any, ...]]


class State(StrEnum):
    """The states of `ingest.state`, in the order a file walks them."""

    LISTED = "listed"
    FETCHED = "fetched"
    VERIFIED = "verified"
    LOADED = "loaded"
    PUBLISHED = "published"  # set by the publisher, not here
    GAP = "gap"
    DEAD = "dead"


@dataclass(frozen=True, slots=True)
class Listing:
    """A file as the poller learned of it. `size` and `md5` are None for a stamp that no
    listing held."""

    stream: Stream
    stamp: datetime
    url: str
    size: int | None
    md5: str | None


@dataclass(frozen=True, slots=True)
class Lease:
    """One worker's right to change one row, and the row as it was when the lease was taken."""

    stream: Stream
    stamp: datetime
    state: State
    token: UUID
    url: str
    size: int | None
    md5: str | None
    raw_key: str | None
    attempts: int  # leases taken on this row so far, this one included
    overdue: bool  # listed 7 days ago or more: one more failure and it is a gap


# The database's clock. A test passes its own time; production passes null.
_NOW: LiteralString = "coalesce(%(now)s::timestamptz, now())"

_CLOCK: LiteralString = f"select {_NOW}"

_ENLIST: LiteralString = f"""
insert into ingest.interval (stream, stamp, url, size, md5, listed_at, next_attempt_at)
values (%(stream)s::ingest.stream, %(stamp)s, %(url)s, %(size)s, %(md5)s, {_NOW}, {_NOW})
on conflict (stream, stamp) do nothing
"""

_NEWEST: LiteralString = """
select max(stamp) from ingest.interval where stream = %(stream)s::ingest.stream
"""

# The inner SELECT picks the newest row that is ready and that nobody holds, and locks it.
# SKIP LOCKED makes a second worker running the same statement at the same moment pass over
# that row instead of waiting for it. The outer UPDATE writes the new token and the time-out.
_LEASE: LiteralString = f"""
update ingest.interval
   set lease_token = gen_random_uuid(),
       lease_until = {_NOW} + interval '5 minutes',
       attempts    = attempts + 1
 where (stream, stamp) = (
         select stream, stamp
           from ingest.interval
          where state in ('listed', 'fetched', 'verified')
            and next_attempt_at <= {_NOW}
            and (lease_until is null or lease_until < {_NOW})
          order by stamp desc, stream
          for update skip locked
          limit 1)
returning stream, stamp, state, lease_token, url, size, md5, raw_key, attempts,
          listed_at <= {_NOW} - interval '7 days'
"""

# The end of every write a lease holder makes. The second line is the fence.
COMMIT_WHERE: LiteralString = """
 where (stream, stamp) = (%(stream)s::ingest.stream, %(stamp)s)
   and lease_token = %(token)s
   and state = %(from)s::ingest.state
"""

# What each transition writes. A step that leaves more work for the same lease pushes the
# time-out out again; a step that ends the walk clears the token.
_FETCHED: LiteralString = f"""
       state = 'fetched', raw_key = %(raw_key)s,
       lease_until = {_NOW} + interval '5 minutes'
"""
_VERIFIED: LiteralString = f"""
       state = 'verified',
       lease_until = {_NOW} + interval '5 minutes'
"""
_LOADED: LiteralString = f"""
       state = 'loaded', parquet_key = %(parquet_key)s, rows = %(rows)s, loaded_at = {_NOW},
       lease_token = null, lease_until = null
"""
_RELEASED: LiteralString = f"""
       state = 'listed', raw_key = null,
       next_attempt_at = {_NOW} + %(delay)s, last_error = %(error)s,
       lease_token = null, lease_until = null
"""
_GAP: LiteralString = """
       state = 'gap', last_error = %(error)s,
       lease_token = null, lease_until = null
"""
_DEAD: LiteralString = """
       state = 'dead', last_error = %(error)s,
       lease_token = null, lease_until = null
"""

# One row for each file that never arrived. A run of missing files is a run of such rows.
_RECORD_GAP: LiteralString = f"""
insert into ingest.known_gap (stream, first_stamp, last_stamp, intervals, reason, recorded_at)
values (%(stream)s::ingest.stream, %(stamp)s, %(stamp)s, 1, %(error)s, {_NOW})
on conflict (stream, first_stamp) do nothing
"""


def _autocommit(conn: Connection) -> None:
    if not conn.autocommit:
        raise ValueError("the ledger needs a connection in autocommit mode")


def clock(conn: Connection, *, now: datetime | None = None) -> datetime:
    """The database's time: the one clock every lease and every listing is measured by."""
    _autocommit(conn)
    row = conn.execute(_CLOCK, {"now": now}).fetchone()
    assert row is not None
    time: datetime = row[0]
    return time


def enlist(conn: Connection, listings: Iterable[Listing], *, now: datetime | None = None) -> int:
    """Add files to the ledger as `listed`. A file that is already there is left exactly as it
    is, whatever its state. Returns the number of rows added."""
    _autocommit(conn)
    added = 0
    with conn.transaction():
        for listing in listings:
            parameters = {
                "stream": listing.stream.value,
                "stamp": listing.stamp,
                "url": listing.url,
                "size": listing.size,
                "md5": listing.md5,
                "now": now,
            }
            added += conn.execute(_ENLIST, parameters).rowcount
    return added


def newest_stamp(conn: Connection, stream: Stream) -> datetime | None:
    """The newest stamp of `stream` in the ledger: the last one the poller saw."""
    _autocommit(conn)
    row = conn.execute(_NEWEST, {"stream": stream.value}).fetchone()
    return None if row is None else row[0]


def lease(conn: Connection, *, now: datetime | None = None) -> Lease | None:
    """Take the newest file that is ready for work, for 5 minutes. None if there is none."""
    _autocommit(conn)
    row = conn.execute(_LEASE, {"now": now}).fetchone()
    if row is None:
        return None
    return Lease(
        stream=Stream(row[0]),
        stamp=row[1],
        state=State(row[2]),
        token=row[3],
        url=row[4],
        size=row[5],
        md5=row[6],
        raw_key=row[7],
        attempts=row[8],
        overdue=row[9],
    )


def _commit(
    conn: Connection,
    held: Lease,
    was: State,
    changes: LiteralString,
    values: dict[str, Any],
    now: datetime | None,
) -> bool:
    """Write `changes` to the row if `held` is still its lease and its state is still `was`.

    False means the row was not touched: a newer lease exists, or the step was already done.
    The caller stops there. It does not look for the reason.
    """
    _autocommit(conn)
    statement = "update ingest.interval set" + changes + COMMIT_WHERE
    parameters = {
        "stream": held.stream.value,
        "stamp": held.stamp,
        "token": held.token,
        "from": was.value,
        "now": now,
        **values,
    }
    return conn.execute(statement, parameters).rowcount == 1


def to_fetched(conn: Connection, held: Lease, raw_key: str, *, now: datetime | None = None) -> bool:
    """`listed` to `fetched`: the zip is in the store under `raw_key`."""
    return _commit(conn, held, State.LISTED, _FETCHED, {"raw_key": raw_key}, now)


def to_verified(conn: Connection, held: Lease, *, now: datetime | None = None) -> bool:
    """`fetched` to `verified`: the stored zip has the listed size and MD5."""
    return _commit(conn, held, State.FETCHED, _VERIFIED, {}, now)


def to_loaded(
    conn: Connection, held: Lease, parquet_key: str, rows: int, *, now: datetime | None = None
) -> bool:
    """`verified` to `loaded`: the lake files are in the store. The lease ends."""
    values = {"parquet_key": parquet_key, "rows": rows}
    return _commit(conn, held, State.VERIFIED, _LOADED, values, now)


def release(
    conn: Connection,
    held: Lease,
    was: State,
    error: str,
    delay: timedelta,
    *,
    now: datetime | None = None,
) -> bool:
    """Back to `listed`, not to be tried again before `delay` has passed. The lease ends, so
    nothing holds the row while it waits."""
    if was not in (State.LISTED, State.FETCHED):
        raise ValueError(f"a {was} row is not released")
    return _commit(conn, held, was, _RELEASED, {"error": error, "delay": delay}, now)


def to_gap(conn: Connection, held: Lease, error: str, *, now: datetime | None = None) -> bool:
    """`listed` to `gap`, with its `known_gap` row, in one transaction. The lease ends."""
    _autocommit(conn)
    with conn.transaction():
        if not _commit(conn, held, State.LISTED, _GAP, {"error": error}, now):
            return False
        parameters = {
            "stream": held.stream.value,
            "stamp": held.stamp,
            "error": error,
            "now": now,
        }
        conn.execute(_RECORD_GAP, parameters)
    return True


def to_dead(conn: Connection, held: Lease, error: str, *, now: datetime | None = None) -> bool:
    """`verified` to `dead`: the file is what GDELT published and it cannot be used."""
    return _commit(conn, held, State.VERIFIED, _DEAD, {"error": error}, now)
