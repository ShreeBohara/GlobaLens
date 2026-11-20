"""Builders shared by the unit and the database tests: synthetic GKG files.

Every title, URL and outlet name made here is invented (`.example` domains). The tests take the
builders as fixtures, because a test module cannot import a helper module under pytest's
importlib mode.
"""

import io
import zipfile
from collections.abc import Callable
from datetime import datetime

import pytest
from gdelt import Stream

GkgFile = Callable[..., bytes]
Zipped = Callable[..., bytes]


def _line(stream: Stream, stamp: datetime, number: int) -> bytes:
    """One valid GKG 2.1 line: 27 tab-separated columns, most of them empty."""
    text = stamp.strftime("%Y%m%d%H%M%S")
    translated = stream is Stream.TRANSLATED
    columns = [""] * 27
    columns[0] = f"{text}-{'T' if translated else ''}{number}"
    columns[1] = text
    columns[2] = "1"
    columns[3] = f"outlet-{number % 3}.example"
    columns[4] = f"https://outlet-{number % 3}.example/{stream.value}/{text}/{number}"
    columns[8] = "TAX_FNCACT_MAYOR,12;WB_137_WATER,40;"
    columns[10] = "4#Lyon, Rhone-Alpes, France#FR#FRB9#69#45.75#4.85#-1445171#58"
    columns[15] = "-2.5,1.5,4,5.5,20,0.5,310"
    columns[25] = "srclc:fra;eng:GT-FRA 1.0" if translated else ""
    columns[26] = f"<PAGE_TITLE>Synthetic headline {number} of {text}</PAGE_TITLE>"
    return "\t".join(columns).encode()


def _gkg_file(stream: Stream, stamp: datetime, rows: int, *, broken: int = 0) -> bytes:
    """An unzipped GKG file with `rows` valid lines and `broken` one-column lines, the shape a
    record takes when a line break cuts it."""
    lines = [_line(stream, stamp, number) for number in range(rows)]
    lines += [
        f"piece {number} of a record cut by a line break".encode() for number in range(broken)
    ]
    return b"\n".join(lines) + b"\n"


def _zipped(data: bytes, *, members: int = 1) -> bytes:
    """A zip of `data`, byte for byte the same on every call."""
    sink = io.BytesIO()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED) as archive:
        for index in range(members):
            info = zipfile.ZipInfo(f"synthetic-{index}.gkg.csv", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return sink.getvalue()


@pytest.fixture(scope="session")
def gkg_file() -> GkgFile:
    return _gkg_file


@pytest.fixture(scope="session")
def zipped() -> Zipped:
    return _zipped
