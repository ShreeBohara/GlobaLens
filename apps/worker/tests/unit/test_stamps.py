"""Stamp and file-name arithmetic: GDELT's 15-minute grid."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from gdelt import Stream
from worker import stamps


def at(hour: int, minute: int, day: int = 20) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def test_a_stamp_round_trips_through_its_text() -> None:
    assert stamps.parse_stamp("20261120013000") == at(1, 30)
    assert stamps.format_stamp(at(1, 30)) == "20261120013000"
    assert stamps.parse_stamp(stamps.format_stamp(at(23, 45))) == at(23, 45)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2026112001300",  # 13 digits
        "202611200130000",  # 15 digits
        "20261120013001",  # a second past the grid
        "20261120010700",  # 01:07 is not a 15-minute stamp
        "20261320013000",  # month 13
        "20260230000000",  # 30 February
        "2026112001300x",
        "20261120 13000",
        "-0261120013000",
    ],
)
def test_text_that_is_not_a_stamp_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        stamps.parse_stamp(text)


def test_only_utc_times_on_the_grid_are_stamps() -> None:
    assert stamps.on_grid(at(1, 30))
    assert not stamps.on_grid(at(1, 7))
    assert not stamps.on_grid(at(1, 30).replace(second=1))
    assert not stamps.on_grid(at(1, 30).replace(microsecond=1))
    assert not stamps.on_grid(datetime(2026, 11, 20, 1, 30))  # no time zone
    assert not stamps.on_grid(datetime(2026, 11, 20, 1, 30, tzinfo=timezone(timedelta(hours=1))))
    with pytest.raises(ValueError):
        stamps.format_stamp(at(1, 7))
    with pytest.raises(ValueError):
        stamps.format_stamp(datetime(2026, 11, 20, 1, 30))


def test_file_names_and_urls_are_built_from_the_stream_and_the_stamp() -> None:
    assert stamps.file_name(Stream.ENGLISH, at(1, 30)) == "20261120013000.gkg.csv.zip"
    assert (
        stamps.file_name(Stream.TRANSLATED, at(1, 15)) == "20261120011500.translation.gkg.csv.zip"
    )
    assert (
        stamps.file_url(Stream.ENGLISH, at(1, 30))
        == "https://data.gdeltproject.org/gdeltv2/20261120013000.gkg.csv.zip"
    )
    assert (
        stamps.file_url(Stream.TRANSLATED, at(1, 15))
        == "https://data.gdeltproject.org/gdeltv2/20261120011500.translation.gkg.csv.zip"
    )


def test_between_lists_every_stamp_strictly_between_two_others() -> None:
    assert stamps.between(at(1, 0), at(2, 0)) == [at(1, 15), at(1, 30), at(1, 45)]
    assert stamps.between(at(1, 0), at(1, 30)) == [at(1, 15)]
    assert stamps.between(at(1, 0), at(1, 15)) == []
    assert stamps.between(at(1, 0), at(1, 0)) == []
    assert stamps.between(at(2, 0), at(1, 0)) == []


def test_between_crosses_midnight_and_the_year() -> None:
    assert stamps.between(at(23, 30), at(0, 15, day=21)) == [at(23, 45), at(0, 0, day=21)]
    last = datetime(2026, 12, 31, 23, 45, tzinfo=UTC)
    first = datetime(2027, 1, 1, 0, 15, tzinfo=UTC)
    assert stamps.between(last, first) == [datetime(2027, 1, 1, 0, 0, tzinfo=UTC)]


def test_between_counts_a_week_of_stamps() -> None:
    week = stamps.between(at(0, 0, day=1), at(0, 0, day=8))
    assert len(week) == 7 * 96 - 1
    assert all(stamps.on_grid(stamp) for stamp in week)
    assert week == sorted(set(week))


def test_the_day_of_a_stamp_is_its_utc_date() -> None:
    assert stamps.day(at(23, 45)) == "2026-11-20"
    assert stamps.day(at(0, 0, day=1)) == "2026-11-01"
