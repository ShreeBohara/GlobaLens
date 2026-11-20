"""What one poll of one stream enqueues. No database and no network: the listing texts are
passed in, and the master-list read is a function the test supplies."""

from datetime import UTC, datetime, timedelta

import pytest
from gdelt import Stream
from worker import feed, poller, stamps
from worker.ledger.fence import Listing

BASE = "http://data.gdeltproject.org/gdeltv2/"
MD5_A = "a" * 32
MD5_B = "b" * 32
MD5_C = "c" * 32


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


def lastupdate(stamp: str, size: int = 4473397, md5: str = MD5_C) -> str:
    return (
        f"58168 {MD5_A} {BASE}{stamp}.export.CSV.zip\n"
        f"88685 {MD5_B} {BASE}{stamp}.mentions.CSV.zip\n"
        f"{size} {md5} {BASE}{stamp}.gkg.csv.zip\n"
    )


class Tail:
    """Stands in for the Range read of the master list, and records each call."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.calls: list[int] = []

    def __call__(self, nbytes: int) -> str:
        self.calls.append(nbytes)
        return self.text


def url(stamp: str) -> str:
    return f"https://data.gdeltproject.org/gdeltv2/{stamp}.gkg.csv.zip"


NOW = datetime(2026, 11, 20, 1, 19, tzinfo=UTC)  # GDELT lists a file some minutes before its stamp
NEWEST = Listing(Stream.ENGLISH, at(1, 30), url("20261120013000"), 4473397, MD5_C)


def test_the_first_poll_enqueues_the_listed_file_only() -> None:
    tail = Tail()
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), None, tail, now=NOW)
    assert found == [NEWEST]
    assert tail.calls == []


def test_the_same_stamp_again_is_enqueued_again_and_the_insert_ignores_it() -> None:
    tail = Tail()
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), at(1, 30), tail, now=NOW)
    assert found == [NEWEST]
    assert tail.calls == []


def test_the_next_stamp_needs_no_master_list() -> None:
    tail = Tail()
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), at(1, 15), tail, now=NOW)
    assert found == [NEWEST]
    assert tail.calls == []


def test_a_jump_enqueues_every_stamp_in_between_from_one_read_of_the_master_list() -> None:
    tail = Tail(
        f"11 {MD5_A} {BASE}20261120004500.gkg.csv.zip\n"
        f"12 {MD5_B} {BASE}20261120010000.gkg.csv.zip\n"
        f"13 {MD5_A} {BASE}20261120011500.gkg.csv.zip\n"
        f"4473397 {MD5_C} {BASE}20261120013000.gkg.csv.zip\n"
    )
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), at(0, 45), tail, now=NOW)
    assert found == [
        Listing(Stream.ENGLISH, at(1, 0), url("20261120010000"), 12, MD5_B),
        Listing(Stream.ENGLISH, at(1, 15), url("20261120011500"), 13, MD5_A),
        NEWEST,
    ]
    assert len(tail.calls) == 1


def test_a_stamp_the_master_list_does_not_hold_is_enqueued_without_size_or_md5() -> None:
    tail = Tail(f"12 {MD5_B} {BASE}20261120010000.gkg.csv.zip\n")
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), at(0, 45), tail, now=NOW)
    assert found == [
        Listing(Stream.ENGLISH, at(1, 0), url("20261120010000"), 12, MD5_B),
        Listing(Stream.ENGLISH, at(1, 15), url("20261120011500"), None, None),
        NEWEST,
    ]


def test_the_newest_file_takes_its_size_and_md5_from_lastupdate_not_the_master_list() -> None:
    tail = Tail(f"1 {MD5_A} {BASE}20261120013000.gkg.csv.zip\n")
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), at(1, 0), tail, now=NOW)
    assert found[-1] == NEWEST


def test_the_read_is_sized_for_the_number_of_missing_stamps() -> None:
    tail = Tail()
    poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), at(1, 0), tail, now=NOW)
    assert tail.calls == [feed.tail_bytes(2)]

    day_ago = datetime(2026, 11, 19, 1, 30, tzinfo=UTC)
    tail = Tail()
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), day_ago, tail, now=NOW)
    assert len(found) == 96  # 95 stamps in between, and the newest
    assert tail.calls == [feed.tail_bytes(95)]


def test_a_file_older_than_the_last_one_seen_is_enqueued_on_its_own() -> None:
    tail = Tail()
    found = poller.listings(Stream.ENGLISH, lastupdate("20261120013000"), at(3, 0), tail, now=NOW)
    assert found == [NEWEST]
    assert tail.calls == []


def test_the_translated_stream_reads_its_own_lines() -> None:
    text = (
        f"40916 {MD5_A} {BASE}20261120011500.translation.export.CSV.zip\n"
        f"5063415 {MD5_C} {BASE}20261120011500.translation.gkg.csv.zip\n"
    )
    tail = Tail(f"21 {MD5_B} {BASE}20261120010000.translation.gkg.csv.zip\n")
    found = poller.listings(Stream.TRANSLATED, text, at(0, 45), tail, now=NOW)
    base = "https://data.gdeltproject.org/gdeltv2/"
    assert found == [
        Listing(
            Stream.TRANSLATED, at(1, 0), base + "20261120010000.translation.gkg.csv.zip", 21, MD5_B
        ),
        Listing(
            Stream.TRANSLATED,
            at(1, 15),
            base + "20261120011500.translation.gkg.csv.zip",
            5063415,
            MD5_C,
        ),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not a listing\n",
        f"58168 {MD5_A} {BASE}20261120013000.export.CSV.zip\n",  # no GKG line
        f"1 {MD5_A} {BASE}20261120011500.translation.gkg.csv.zip\n",  # the other stream's file
    ],
)
def test_a_lastupdate_without_a_gkg_file_is_an_error(text: str) -> None:
    with pytest.raises(poller.FeedError):
        poller.listings(Stream.ENGLISH, text, at(1, 0), Tail(), now=NOW)


def test_a_stamp_hours_ahead_of_the_clock_is_refused() -> None:
    tail = Tail()
    just_inside = NOW + poller.AHEAD_LIMIT - timedelta(minutes=4)  # 03:15
    assert stamps.on_grid(just_inside)
    text = lastupdate(stamps.format_stamp(just_inside))
    assert len(poller.listings(Stream.ENGLISH, text, None, tail, now=NOW)) == 1

    too_far = just_inside + timedelta(minutes=15)
    with pytest.raises(poller.FeedError):
        poller.listings(
            Stream.ENGLISH, lastupdate(stamps.format_stamp(too_far)), at(1, 0), tail, now=NOW
        )
    with pytest.raises(poller.FeedError):
        poller.listings(Stream.ENGLISH, lastupdate("20991231234500"), at(1, 0), tail, now=NOW)
    assert tail.calls == []  # and no master list is read for it
