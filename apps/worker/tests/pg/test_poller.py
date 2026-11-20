"""The poller against a real PostgreSQL 18. GDELT is a dict of URL to text: no network."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from gdelt import Stream
from worker import feed, poller, stamps
from worker.ledger import fence

Connection = psycopg.Connection[tuple[Any, ...]]
Row = dict[str, Any]
ReadRow = Callable[[Stream, datetime], Row]

T0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
QUARTER = timedelta(minutes=15)
EN = Stream.ENGLISH
TR = Stream.TRANSLATED
BASE = "http://data.gdeltproject.org/gdeltv2/"


def line(stream: Stream, stamp: datetime, size: int, md5: str) -> str:
    return f"{size} {md5} {BASE}{stamps.file_name(stream, stamp)}\n"


class Gdelt:
    """Serves listing files from a dict and records what was asked for."""

    def __init__(self) -> None:
        self.pages: dict[str, str] = {}
        self.requests: list[tuple[str, int | None]] = []

    def get(self, url: str, *, tail: int | None = None) -> bytes:
        self.requests.append((url, tail))
        if url not in self.pages:
            raise feed.FetchError("HTTP 503")
        return self.pages[url].encode()

    def lastupdate(self, stream: Stream, stamp: datetime, size: int, md5: str) -> None:
        self.pages[feed.LASTUPDATE_URL[stream]] = line(stream, stamp, size, md5)


def count(admin: Connection) -> int:
    found = admin.execute("select count(*) from ingest.interval").fetchone()
    assert found is not None
    return int(found[0])


def test_a_poll_lists_the_newest_file_of_each_stream(
    conn: Connection, admin: Connection, row: ReadRow
) -> None:
    gdelt = Gdelt()
    gdelt.lastupdate(EN, T0 + QUARTER, 11, "a" * 32)
    gdelt.lastupdate(TR, T0, 22, "b" * 32)

    assert poller.poll_once(conn, gdelt.get, now=T0) == 2
    english = row(EN, T0 + QUARTER)
    assert (english["state"], english["size"], english["md5"]) == ("listed", 11, "a" * 32)
    assert english["url"] == stamps.file_url(EN, T0 + QUARTER)  # https, built from the stamp
    assert english["listed_at"] == T0
    translated = row(TR, T0)
    assert (translated["size"], translated["md5"]) == (22, "b" * 32)
    assert [tail for _, tail in gdelt.requests] == [None, None]  # no master list was read

    # A minute later nothing is new: the insert ignores what is already there.
    assert poller.poll_once(conn, gdelt.get, now=T0 + timedelta(minutes=1)) == 0
    assert count(admin) == 2
    assert row(EN, T0 + QUARTER) == english


def test_a_jump_lists_every_stamp_in_between_from_one_read_of_the_master_list(
    conn: Connection, admin: Connection, row: ReadRow
) -> None:
    gdelt = Gdelt()
    gdelt.lastupdate(EN, T0, 10, "a" * 32)
    gdelt.lastupdate(TR, T0, 20, "b" * 32)
    assert poller.poll_once(conn, gdelt.get, now=T0) == 2

    # The poller is away for an hour. On return the English stream is four stamps on.
    gdelt.requests.clear()
    gdelt.lastupdate(EN, T0 + QUARTER * 4, 14, "e" * 32)
    gdelt.pages[feed.MASTERLIST_URL[EN]] = (
        "cut-first-line.zip\n"
        + line(EN, T0 + QUARTER, 11, "b" * 32)
        + line(EN, T0 + QUARTER * 2, 12, "c" * 32)
        # the third is not in the master list
        + line(EN, T0 + QUARTER * 4, 99, "f" * 32)
    )
    later = T0 + timedelta(hours=1)
    assert poller.poll_once(conn, gdelt.get, now=later) == 4

    assert [
        (row(EN, T0 + QUARTER * n)["size"], row(EN, T0 + QUARTER * n)["md5"]) for n in range(5)
    ] == [
        (10, "a" * 32),
        (11, "b" * 32),
        (12, "c" * 32),
        (None, None),
        (14, "e" * 32),  # from lastupdate, not from the master list
    ]
    assert all(row(EN, T0 + QUARTER * n)["listed_at"] == later for n in range(1, 5))
    master_reads = [request for request in gdelt.requests if request[1] is not None]
    assert master_reads == [(feed.MASTERLIST_URL[EN], feed.tail_bytes(3))]
    assert count(admin) == 6

    # The newest file is leased first, so the backlog drains behind the live edge.
    held = fence.lease(conn, now=later)
    assert held is not None and held.stamp == T0 + QUARTER * 4


def test_one_stream_failing_does_not_stop_the_other(conn: Connection, admin: Connection) -> None:
    gdelt = Gdelt()
    gdelt.lastupdate(TR, T0, 20, "b" * 32)  # the English lastupdate answers 503
    assert poller.poll_once(conn, gdelt.get, now=T0) == 1
    assert count(admin) == 1

    gdelt.pages[feed.LASTUPDATE_URL[EN]] = "not a listing\n"
    assert poller.poll_once(conn, gdelt.get, now=T0) == 0
    assert count(admin) == 1


def test_a_jump_whose_master_list_cannot_be_read_lists_nothing_and_is_retried(
    conn: Connection, admin: Connection
) -> None:
    gdelt = Gdelt()
    gdelt.lastupdate(EN, T0, 10, "a" * 32)
    assert poller.poll_once(conn, gdelt.get, now=T0) == 1
    gdelt.lastupdate(EN, T0 + QUARTER * 3, 13, "d" * 32)
    # The master list answers 503: nothing is listed, so the jump is still there next minute.
    assert poller.poll_once(conn, gdelt.get, now=T0) == 0
    assert count(admin) == 1
    gdelt.pages[feed.MASTERLIST_URL[EN]] = line(EN, T0 + QUARTER, 11, "b" * 32)
    assert poller.poll_once(conn, gdelt.get, now=T0) == 3
    assert count(admin) == 4
