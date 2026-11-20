"""GDELT's 15-minute grid: stamps, and the file names that follow from them.

A stamp is a UTC time on the quarter hour. GDELT writes it as `YYYYMMDDHHMMSS`, and a file's
name is its stamp and its stream, so every file of a stream can be named without being
listed anywhere.
"""

from datetime import UTC, datetime, timedelta

from gdelt import Stream

__all__ = [
    "INTERVAL",
    "between",
    "day",
    "file_name",
    "file_url",
    "format_stamp",
    "on_grid",
    "parse_stamp",
]

INTERVAL = timedelta(minutes=15)

_FILES = "https://data.gdeltproject.org/gdeltv2/"
_SUFFIX = {Stream.ENGLISH: ".gkg.csv.zip", Stream.TRANSLATED: ".translation.gkg.csv.zip"}


def on_grid(stamp: datetime) -> bool:
    """True for a UTC time that is a whole quarter hour."""
    return (
        stamp.utcoffset() == timedelta(0)
        and stamp.minute % 15 == 0
        and stamp.second == 0
        and stamp.microsecond == 0
    )


def parse_stamp(text: str) -> datetime:
    """The stamp written as `YYYYMMDDHHMMSS`. Raises ValueError for anything else."""
    if len(text) != 14 or not (text.isascii() and text.isdigit()):
        raise ValueError(f"not a stamp: {text!r}")
    stamp = datetime(
        int(text[0:4]),
        int(text[4:6]),
        int(text[6:8]),
        int(text[8:10]),
        int(text[10:12]),
        int(text[12:14]),
        tzinfo=UTC,
    )
    if not on_grid(stamp):
        raise ValueError(f"not on the 15-minute grid: {text!r}")
    return stamp


def format_stamp(stamp: datetime) -> str:
    if not on_grid(stamp):
        raise ValueError(f"not a UTC time on the 15-minute grid: {stamp!r}")
    return stamp.strftime("%Y%m%d%H%M%S")


def between(older: datetime, newer: datetime) -> list[datetime]:
    """Every stamp strictly after `older` and strictly before `newer`, oldest first."""
    found: list[datetime] = []
    stamp = older + INTERVAL
    while stamp < newer:
        found.append(stamp)
        stamp += INTERVAL
    return found


def file_name(stream: Stream, stamp: datetime) -> str:
    return format_stamp(stamp) + _SUFFIX[stream]


def file_url(stream: Stream, stamp: datetime) -> str:
    return _FILES + file_name(stream, stamp)


def day(stamp: datetime) -> str:
    """The stamp's UTC date as `YYYY-MM-DD`, the `dt=` part of an object key."""
    if not on_grid(stamp):
        raise ValueError(f"not a UTC time on the 15-minute grid: {stamp!r}")
    return stamp.strftime("%Y-%m-%d")
