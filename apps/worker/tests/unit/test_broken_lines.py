"""When a file is loaded and when it is parked as `dead`.

The owner's decision of 20 November 2026: lines that fail the 27-column contract are
quarantined and counted and the rest of the file is loaded. A file is parked only when it
cannot be opened, or when more than 10% of its non-blank lines fail.
"""

import io
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from gdelt import ParseStats, Stream, parse_gkg
from worker.ledger import tier1

STAMP = datetime(2026, 11, 20, 1, 30, tzinfo=UTC)


def stats(rows: int, broken: int, blank: int = 0) -> ParseStats:
    counted = ParseStats(lines=rows + broken + blank, rows=rows, blank_lines=blank)
    if broken:
        counted.quarantined["column_count"] = broken
    return counted


@pytest.mark.parametrize(
    ("rows", "broken", "parked"),
    [
        (10, 0, False),
        (970, 30, False),  # 3%: far from the limit
        (999, 1, False),  # 0.1%: the design note's first reading parked this file
        (9, 1, False),  # exactly 10% is not more than 10%
        (90, 10, False),
        (899, 101, True),  # 10.1%
        (89, 11, True),
        (8, 1, True),  # 11.1%
        (0, 1, True),  # nothing but broken lines
        (0, 500, True),
    ],
)
def test_a_file_is_parked_only_above_ten_percent(rows: int, broken: int, parked: bool) -> None:
    assert tier1.too_broken(stats(rows, broken)) is parked


def test_blank_lines_count_neither_for_nor_against_a_file() -> None:
    assert not tier1.too_broken(stats(9, 1, blank=0))
    assert not tier1.too_broken(stats(9, 1, blank=1_000))
    assert tier1.too_broken(stats(8, 1, blank=1_000))


def test_an_empty_file_is_not_broken() -> None:
    assert not tier1.too_broken(stats(0, 0))
    assert not tier1.too_broken(stats(0, 0, blank=3))


def test_the_rule_reads_every_reason_a_line_can_fail_for() -> None:
    counted = ParseStats(lines=20, rows=17)
    counted.quarantined.update({"column_count": 1, "bad_record_id": 1, "bad_utf8": 1})
    assert tier1.too_broken(counted)  # 3 of 20
    counted = ParseStats(lines=30, rows=27)
    counted.quarantined.update({"column_count": 1, "bad_record_id": 1, "bad_utf8": 1})
    assert not tier1.too_broken(counted)  # 3 of 30


def test_the_rule_on_parsed_files(gkg_file: Callable[..., bytes]) -> None:
    kept = parse_gkg(gkg_file(Stream.TRANSLATED, STAMP, 18, broken=2))
    assert kept.stats.rows == 18
    assert len(kept.quarantined) == 2
    assert not tier1.too_broken(kept.stats)

    parked = parse_gkg(gkg_file(Stream.TRANSLATED, STAMP, 17, broken=2))
    assert tier1.too_broken(parked.stats)


def test_a_zip_with_one_file_opens(
    gkg_file: Callable[..., bytes], zipped: Callable[..., bytes]
) -> None:
    data = gkg_file(Stream.ENGLISH, STAMP, 3)
    assert tier1.unzip(zipped(data)) == data


def test_bytes_that_are_not_a_zip_cannot_be_opened() -> None:
    for data in (b"", b"not a zip", b"PK\x03\x04 and then nothing a zip reader can use"):
        with pytest.raises(tier1.Unreadable):
            tier1.unzip(data)


def test_a_zip_must_hold_exactly_one_file(
    gkg_file: Callable[..., bytes], zipped: Callable[..., bytes]
) -> None:
    data = gkg_file(Stream.ENGLISH, STAMP, 3)
    with pytest.raises(tier1.Unreadable):
        tier1.unzip(zipped(data, members=2))
    with pytest.raises(tier1.Unreadable):
        tier1.unzip(zipped(data, members=0))


def test_a_cut_or_damaged_zip_cannot_be_opened(
    gkg_file: Callable[..., bytes], zipped: Callable[..., bytes]
) -> None:
    whole = zipped(gkg_file(Stream.ENGLISH, STAMP, 200))
    with pytest.raises(tier1.Unreadable):
        tier1.unzip(whole[: len(whole) // 2])
    # Flip one byte inside the compressed data: the zip's own checksum catches it.
    damaged = bytearray(whole)
    damaged[len(whole) // 2] ^= 0xFF
    with pytest.raises(tier1.Unreadable):
        tier1.unzip(bytes(damaged))


def test_a_zip_the_reader_chokes_on_cannot_be_opened(gkg_file: Callable[..., bytes]) -> None:
    data = gkg_file(Stream.ENGLISH, STAMP, 50)

    # A file name flagged as UTF-8 that is not UTF-8: the reader raises UnicodeDecodeError.
    sink = io.BytesIO()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("\N{LATIN SMALL LETTER E WITH ACUTE}.gkg.csv", data)
    name = "\N{LATIN SMALL LETTER E WITH ACUTE}".encode()
    assert sink.getvalue().count(name) == 2  # the local header and the directory
    with pytest.raises(tier1.Unreadable, match="UnicodeDecodeError"):
        tier1.unzip(sink.getvalue().replace(name, b"\xff\xfe"))

    # Another compression method, damaged: the error is not zlib's.
    sink = io.BytesIO()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_LZMA) as archive:
        archive.writestr("x.gkg.csv", data)
    assert tier1.unzip(sink.getvalue()) == data
    damaged = bytearray(sink.getvalue())
    for index in range(len(damaged) // 3, len(damaged) // 3 + 40):
        damaged[index] ^= 0xFF
    with pytest.raises(tier1.Unreadable):
        tier1.unzip(bytes(damaged))


def test_a_file_that_would_unpack_too_large_is_not_opened(
    zipped: Callable[..., bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tier1, "MAX_UNZIPPED", 1_000)
    assert tier1.unzip(zipped(b"\x00" * 1_000)) == b"\x00" * 1_000
    with pytest.raises(tier1.Unreadable):
        tier1.unzip(zipped(b"\x00" * 1_001))
