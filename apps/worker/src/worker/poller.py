"""The poller: both `lastupdate` files every 60 seconds, into the ledger.

Each poll reads a stream's `lastupdate` file and enqueues the GKG file it lists. The insert
ignores a file that is already in the ledger, so a poll can repeat as often as it likes.

When the listed stamp is more than 15 minutes after the newest one in the ledger, the stamps
in between were missed (the poller was down, or GDELT skipped ahead). File names follow from
the stamp, so every one of them is enqueued, and their sizes and MD5s come from one Range read
of the end of the master list. A stamp that the master list does not hold is enqueued with no
size and no MD5: nothing can be verified against, so it is retried until a listing can exist
and becomes a gap after 7 days. This stands in for the hourly reconciler of Phase 3.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from gdelt import Stream

from worker import feed, stamps
from worker.ledger import fence
from worker.ledger.fence import Connection, Listing

__all__ = ["AHEAD_LIMIT", "PERIOD_SECONDS", "FeedError", "listings", "poll_once", "run"]

log = logging.getLogger(__name__)

PERIOD_SECONDS = 60.0
AHEAD_LIMIT = timedelta(hours=2)

Get = Callable[..., bytes]  # feed.http_get, or a test's stand-in


class FeedError(Exception):
    """A `lastupdate` file that lists no GKG file of its stream."""


def listings(
    stream: Stream,
    lastupdate: str,
    last_seen: datetime | None,
    read_tail: Callable[[int], str],
    *,
    now: datetime,
) -> list[Listing]:
    """What one poll of `stream` enqueues, oldest first.

    `lastupdate` is the text of the stream's lastupdate file, `last_seen` the newest stamp the
    ledger holds for the stream, and `read_tail(n)` returns the last `n` bytes of the stream's
    master list. It is called at most once, and only when stamps were missed.

    A stamp more than AHEAD_LIMIT after `now` is refused. GDELT publishes a file some minutes
    before its stamp, never hours; and one far-off stamp in the ledger would be "the last one
    seen" for good, so no later jump would ever be noticed.
    """
    listed = feed.parse_listing(lastupdate, stream)
    if not listed:
        raise FeedError(f"the {stream.value} lastupdate file lists no GKG file")
    newest = listed[max(listed)]
    if newest.stamp > now + AHEAD_LIMIT:
        raise FeedError(
            f"the {stream.value} lastupdate file lists {stamps.format_stamp(newest.stamp)}, "
            f"more than {AHEAD_LIMIT} ahead of the clock"
        )
    found: list[Listing] = []
    missed = stamps.between(last_seen, newest.stamp) if last_seen is not None else []
    if missed:
        known = feed.parse_listing(read_tail(feed.tail_bytes(len(missed))), stream)
        for stamp in missed:
            entry = known.get(stamp)
            found.append(
                Listing(
                    stream,
                    stamp,
                    stamps.file_url(stream, stamp),
                    None if entry is None else entry.size,
                    None if entry is None else entry.md5,
                )
            )
    found.append(
        Listing(
            stream, newest.stamp, stamps.file_url(stream, newest.stamp), newest.size, newest.md5
        )
    )
    return found


def poll_once(conn: Connection, get: Get = feed.http_get, *, now: datetime | None = None) -> int:
    """Poll both streams once. Returns the number of files added to the ledger.

    One stream failing does not stop the other. A stream whose lastupdate file or master list
    cannot be read enqueues nothing in this poll, not even its newest file: the jump is then
    still there for the next poll to fill. `now` is for tests only.
    """
    added = 0
    for stream in (Stream.ENGLISH, Stream.TRANSLATED):

        def read_tail(nbytes: int, stream: Stream = stream) -> str:
            return get(feed.MASTERLIST_URL[stream], tail=nbytes).decode("ascii", "replace")

        try:
            text = get(feed.LASTUPDATE_URL[stream]).decode("ascii", "replace")
            found = listings(
                stream,
                text,
                fence.newest_stamp(conn, stream),
                read_tail,
                now=fence.clock(conn, now=now),
            )
        except (feed.FetchError, FeedError) as error:
            log.warning("poll of %s failed: %s", stream.value, error)
            continue
        new = fence.enlist(conn, found, now=now)
        if new:
            log.info(
                "%s: listed %d new file(s), newest %s",
                stream.value,
                new,
                stamps.format_stamp(found[-1].stamp),
            )
        added += new
    return added


def run(conn: Connection, stop: threading.Event, get: Get = feed.http_get) -> None:
    """Poll every PERIOD_SECONDS until `stop` is set."""
    while not stop.is_set():
        poll_once(conn, get)
        stop.wait(PERIOD_SECONDS)
