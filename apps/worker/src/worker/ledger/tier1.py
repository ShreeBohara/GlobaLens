"""One lease walking one file through fetch, verify and load.

`walk` is a generator. It takes a lease, does the next step for the state the row is in,
commits it, and goes on to the step after, until the file is `loaded` or the walk has to stop.
It yields at every point where the world can change under it: after the lease, after the
download, between two PUTs, and before each commit. In production `run_one` simply runs it to
the end. The property tests step several walks by hand, and between two steps of one walk they
may run another, move the clock past the lease, or drop the walk for good.

The order inside each step is always the same: do the effect (a PUT to a key derived from the
content), then commit with the lease's token. A commit that changes no row ends the walk at
once, and whatever it PUT stays where it is, which is harmless.
"""

import hashlib
import io
import logging
import lzma
import zipfile
import zlib
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from gdelt import ParseStats, parse_gkg

from worker import lake
from worker.feed import FetchError
from worker.ledger import backoff, fence, keys
from worker.ledger.fence import Connection, Lease, State
from worker.store import ObjectStore

__all__ = [
    "BROKEN_LIMIT_PERCENT",
    "MAX_UNZIPPED",
    "At",
    "MissingObject",
    "Outcome",
    "Point",
    "Unreadable",
    "run_one",
    "too_broken",
    "unzip",
    "walk",
]

log = logging.getLogger(__name__)

# A file is parked as `dead` when more than this share of its non-blank lines fail the
# 27-column contract. Decided by the owner on 20 November 2026; a design value, not a
# measurement. Below it the failing lines are counted and the rest of the file is loaded.
BROKEN_LIMIT_PERCENT = 10

# A GKG file unpacks to some tens of megabytes. A zip that claims more than this is not opened.
MAX_UNZIPPED = 1024 * 1024 * 1024

_MISMATCH = "the size or MD5 of the download differs from the listing"

# What the zip reader raises for an archive it cannot read: a damaged structure or checksum,
# a compression method it does not have, a password, a file name that is not what it claims.
# A file that fails this way is parked; anything not listed here is a bug, and is not caught.
_UNZIP_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    lzma.LZMAError,
    EOFError,
    NotImplementedError,
    RuntimeError,
    ValueError,
    OSError,
)

Fetch = Callable[[str], bytes]  # a URL to its bytes; raises FetchError
Clock = Callable[[], datetime | None]  # None means the database's own time


class Point(StrEnum):
    """Where a walk can be between two steps."""

    LEASED = "leased"  # the lease is taken and nothing else has happened
    DOWNLOADED = "downloaded"  # the zip is in memory
    STORED = "stored"  # one object is PUT and another PUT follows
    COMMIT = "commit"  # the effects are done; the commit `was` to `to` is next


@dataclass(frozen=True, slots=True)
class At:
    """What a walk yields: where it is, under which lease, and the commit it is about to make."""

    point: Point
    lease: Lease
    was: State | None = None
    to: State | None = None


class Outcome(StrEnum):
    """How a walk ended."""

    IDLE = "idle"  # there was nothing to lease
    LOADED = "loaded"
    RELEASED = "released"  # back to `listed`, to be tried again later
    GAP = "gap"
    DEAD = "dead"
    FENCED = "fenced"  # a commit changed no row: the lease was no longer this walk's


class Unreadable(Exception):
    """A zip that cannot be opened as one GKG file."""


class MissingObject(Exception):
    """The ledger names a raw object that the store does not have."""


def _database_time() -> datetime | None:
    return None


def _as_listed(held: Lease, data: bytes) -> bool:
    """True when `data` has the size and the MD5 that the listing gave for the file."""
    return (
        held.size is not None
        and held.md5 is not None
        and len(data) == held.size
        and hashlib.md5(data, usedforsecurity=False).hexdigest() == held.md5
    )


def unzip(data: bytes) -> bytes:
    """The one file inside a GKG zip. Raises Unreadable if there is no such thing."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) != 1:
                raise Unreadable(f"{len(members)} files in the zip, not one")
            if members[0].file_size > MAX_UNZIPPED:
                raise Unreadable(f"would unpack to {members[0].file_size} bytes")
            return archive.read(members[0])
    except _UNZIP_ERRORS as error:
        raise Unreadable(f"{type(error).__name__}: {error}") from None


def too_broken(stats: ParseStats) -> bool:
    """True when more than BROKEN_LIMIT_PERCENT of the non-blank lines failed the contract."""
    failed = sum(stats.quarantined.values())
    return failed * 100 > BROKEN_LIMIT_PERCENT * (stats.lines - stats.blank_lines)


def _put_off(
    conn: Connection, held: Lease, error: str, clock: Clock
) -> Generator[At, None, Outcome]:
    """A `listed` file could not be fetched. Try again later, or after 7 days call it a gap."""
    if held.overdue:
        yield At(Point.COMMIT, held, State.LISTED, State.GAP)
        if not fence.to_gap(conn, held, error, now=clock()):
            return Outcome.FENCED
        log.warning("%s %s is a gap after 7 days: %s", held.stream, held.stamp, error)
        return Outcome.GAP
    yield At(Point.COMMIT, held, State.LISTED, State.LISTED)
    wait = backoff.delay(held.attempts)
    if not fence.release(conn, held, State.LISTED, error, wait, now=clock()):
        return Outcome.FENCED
    log.info("%s %s put off for %s: %s", held.stream, held.stamp, wait, error)
    return Outcome.RELEASED


def _park(conn: Connection, held: Lease, error: str, clock: Clock) -> Generator[At, None, Outcome]:
    """A verified file cannot be used. Park it as `dead` and raise the alarm."""
    yield At(Point.COMMIT, held, State.VERIFIED, State.DEAD)
    if not fence.to_dead(conn, held, error, now=clock()):
        return Outcome.FENCED
    log.error("ALARM %s %s is parked as dead: %s", held.stream, held.stamp, error)
    return Outcome.DEAD


def walk(
    conn: Connection, store: ObjectStore, fetch: Fetch, *, clock: Clock = _database_time
) -> Generator[At, None, Outcome]:
    """Lease one file and take it as far as it will go. `clock` is for tests only."""
    held = fence.lease(conn, now=clock())
    if held is None:
        return Outcome.IDLE
    yield At(Point.LEASED, held)

    state = held.state
    raw_key = held.raw_key
    data: bytes | None = None  # the zip, once this walk has it in memory

    if state is State.LISTED:
        if held.size is None or held.md5 is None:
            # No listing held this file, so there is nothing to check a download against.
            return (yield from _put_off(conn, held, "no size or MD5 is listed", clock))
        try:
            data = fetch(held.url)
        except FetchError as error:
            return (yield from _put_off(conn, held, f"download failed: {error}", clock))
        yield At(Point.DOWNLOADED, held)
        if held.overdue and not _as_listed(held, data):
            # The last try of a file that has failed for 7 days: do not store it again.
            return (yield from _put_off(conn, held, _MISMATCH, clock))
        raw_key = keys.raw_key(held.stream, held.stamp, data)
        store.put(raw_key, data)
        yield At(Point.COMMIT, held, State.LISTED, State.FETCHED)
        if not fence.to_fetched(conn, held, raw_key, now=clock()):
            return Outcome.FENCED
        state = State.FETCHED

    if state is State.FETCHED:
        if data is None and raw_key is not None:
            data = store.get(raw_key)  # a walk that died after its commit left it there
        if data is None or not _as_listed(held, data):
            yield At(Point.COMMIT, held, State.FETCHED, State.LISTED)
            wait = backoff.delay(held.attempts)
            if not fence.release(conn, held, State.FETCHED, _MISMATCH, wait, now=clock()):
                return Outcome.FENCED
            log.warning("%s %s put off for %s: %s", held.stream, held.stamp, wait, _MISMATCH)
            return Outcome.RELEASED
        yield At(Point.COMMIT, held, State.FETCHED, State.VERIFIED)
        if not fence.to_verified(conn, held, now=clock()):
            return Outcome.FENCED
        state = State.VERIFIED

    # The row is `verified`: the stored zip is the file GDELT listed.
    if data is None:
        data = store.get(raw_key) if raw_key is not None else None
        if data is None:
            raise MissingObject(f"{held.stream} {held.stamp}: {raw_key} is not in the store")
    try:
        parsed = parse_gkg(unzip(data))
    except Unreadable as error:
        return (yield from _park(conn, held, f"cannot be opened: {error}", clock))
    failed = sum(parsed.stats.quarantined.values())
    if too_broken(parsed.stats):
        candidates = parsed.stats.lines - parsed.stats.blank_lines
        reasons = ", ".join(
            f"{reason}: {count}" for reason, count in sorted(parsed.stats.quarantined.items())
        )
        error = (
            f"{failed} of {candidates} lines fail the contract, "
            f"more than {BROKEN_LIMIT_PERCENT}% ({reasons})"
        )
        return (yield from _park(conn, held, error, clock))
    facts, display = lake.build(parsed.rows, parsed.stats)
    facts_key, display_key = keys.lake_keys(held.stream, held.stamp, facts, display)
    store.put(display_key, display)
    yield At(Point.STORED, held)
    store.put(facts_key, facts)
    yield At(Point.COMMIT, held, State.VERIFIED, State.LOADED)
    if not fence.to_loaded(conn, held, facts_key, len(parsed.rows), now=clock()):
        return Outcome.FENCED
    log.info(
        "%s %s loaded: %d rows, %d lines quarantined",
        held.stream,
        held.stamp,
        len(parsed.rows),
        failed,
    )
    return Outcome.LOADED


def run_one(conn: Connection, store: ObjectStore, fetch: Fetch) -> Outcome:
    """Run one walk to its end."""
    steps = walk(conn, store, fetch)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            outcome: Outcome = done.value
            return outcome
