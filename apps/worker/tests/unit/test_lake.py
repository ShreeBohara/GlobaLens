"""The lake's two Parquet files. The same rows must give the same bytes, every time, or a
content-hash key stops being the same key on a repeat."""

# pyarrow ships no type information, so its calls are unknown to pyright.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import hashlib
import io
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime

import pyarrow.parquet as pq
from gdelt import Stream, parse_gkg
from worker import lake

STAMP = datetime(2026, 11, 20, 1, 30, tzinfo=UTC)

DIGESTS = """
import hashlib, sys
from gdelt import parse_gkg
from worker import lake
parsed = parse_gkg(sys.stdin.buffer.read())
facts, display = lake.build(parsed.rows, parsed.stats)
print(hashlib.sha256(facts).hexdigest(), hashlib.sha256(display).hexdigest())
"""


def build(data: bytes) -> tuple[bytes, bytes]:
    parsed = parse_gkg(data)
    return lake.build(parsed.rows, parsed.stats)


def test_the_same_input_gives_the_same_bytes(gkg_file: Callable[..., bytes]) -> None:
    data = gkg_file(Stream.TRANSLATED, STAMP, 40, broken=3)
    first = build(data)
    assert build(data) == first
    assert build(bytes(data)) == first


def test_another_process_with_another_hash_seed_gives_the_same_bytes(
    gkg_file: Callable[..., bytes],
) -> None:
    data = gkg_file(Stream.TRANSLATED, STAMP, 40, broken=3)
    facts, display = build(data)
    here = f"{hashlib.sha256(facts).hexdigest()} {hashlib.sha256(display).hexdigest()}"
    for seed in ("1", "2"):
        other = subprocess.run(
            [sys.executable, "-c", DIGESTS],
            input=data,
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
            timeout=120,
            check=False,
        )
        assert other.returncode == 0, other.stderr.decode()
        assert other.stdout.decode().strip() == here


def test_different_rows_give_different_bytes(gkg_file: Callable[..., bytes]) -> None:
    one = build(gkg_file(Stream.ENGLISH, STAMP, 5))
    two = build(gkg_file(Stream.ENGLISH, STAMP, 6))
    assert one[0] != two[0]
    assert one[1] != two[1]


def test_titles_and_urls_are_in_the_display_file_and_nowhere_in_the_facts_file(
    gkg_file: Callable[..., bytes],
) -> None:
    data = gkg_file(Stream.TRANSLATED, STAMP, 7)
    parsed = parse_gkg(data)
    facts_bytes, display_bytes = lake.build(parsed.rows, parsed.stats)

    facts = pq.read_table(io.BytesIO(facts_bytes))
    display = pq.read_table(io.BytesIO(display_bytes))
    assert facts.num_rows == display.num_rows == 7
    assert display.column_names == ["seq", "title", "url"]
    assert "title" not in facts.column_names
    assert "url" not in facts.column_names

    # Every row keeps its place and its identity in both files.
    assert facts.column("seq").to_pylist() == [row.seq for row in parsed.rows]
    assert display.column("seq").to_pylist() == [row.seq for row in parsed.rows]
    assert display.column("title").to_pylist() == [row.title for row in parsed.rows]
    assert display.column("url").to_pylist() == [row.url for row in parsed.rows]
    assert facts.column("record_id").to_pylist() == [row.record_id for row in parsed.rows]
    assert facts.column("title_hash").to_pylist() == [row.title_hash for row in parsed.rows]
    assert facts.column("outlet").to_pylist() == [row.outlet for row in parsed.rows]
    assert facts.column("lang").to_pylist() == ["fra"] * 7
    assert facts.column("geo_type").to_pylist() == [4] * 7
    assert facts.column("lat").to_pylist() == [45.75] * 7
    assert facts.column("stamp").to_pylist() == [STAMP] * 7

    # No headline text hides in the facts file under another name.
    for row in parsed.rows:
        assert row.title is not None
        assert row.title.encode() not in facts_bytes
        assert row.title.encode() in display_bytes or len(display_bytes) > 0
    for column in facts.column_names:
        for value in facts.column(column).to_pylist():
            assert "Synthetic headline" not in str(value)


def test_the_facts_file_carries_the_count_of_quarantined_lines(
    gkg_file: Callable[..., bytes],
) -> None:
    parsed = parse_gkg(gkg_file(Stream.ENGLISH, STAMP, 30, broken=2))
    facts_bytes, _ = lake.build(parsed.rows, parsed.stats)
    metadata = pq.read_schema(io.BytesIO(facts_bytes)).metadata
    assert metadata[b"gl.schema"] == b"gkg-facts/1"
    assert json.loads(metadata[b"gl.parse"]) == {
        "blank_lines": 0,
        "issues": {},
        "lines": 32,
        "quarantined": {"column_count": 2},
        "rows": 30,
        "unknown_srclc": {},
    }


def test_a_file_with_no_rows_still_gives_two_files(gkg_file: Callable[..., bytes]) -> None:
    facts_bytes, display_bytes = build(gkg_file(Stream.ENGLISH, STAMP, 0))
    assert pq.read_table(io.BytesIO(facts_bytes)).num_rows == 0
    assert pq.read_table(io.BytesIO(display_bytes)).num_rows == 0
    assert build(gkg_file(Stream.ENGLISH, STAMP, 0)) == (facts_bytes, display_bytes)
    assert pq.read_table(io.BytesIO(build(b"")[0])).num_rows == 0
