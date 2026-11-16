"""The seed rows inside db/migrations/0001_ingest.sql are generated, never typed.

`db/seedgen.py` renders them from `prov/sources.yml` and from the saved output of the master-list
script. These tests run the generator the way a person does, as a command, against the
repository and against altered copies of it. They need no database, so they run under
`mise run check`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[3]
SEEDGEN = ROOT / "db" / "seedgen.py"
MIGRATION = Path("db/migrations/0001_ingest.sql")
SOURCES = Path("prov/sources.yml")
GAP_DIR = Path("db/seeds/known_gap")

PHASE_1_SOURCES = ["gdelt-gkg-2.1", "natural-earth", "protomaps-basemap", "openfreemap"]
SOURCE_COLUMNS = {
    "source_id",
    "licence",
    "redistribute_ok",
    "share_alike",
    "nc",
    "attribution_text",
    "verified_on",
}

# What analyze_masterlist.py prints, cut down to the lines the generator reads. The stamps are
# invented: a 5-interval gap that starts in June 2025 and a shorter one.
SAMPLE_OUTPUT = """== {label}: unparsed lines=0
export: files=10 first=20150218230000 last=20260101000000
mentions: files=10 first=20150218230000 last=20260101000000
gkg: files=10 first=20150218230000 last=20260101003000

Top gaps since 2024 for export (count of consecutive missing 15-min files, start):
     99 intervals (~24.8 h) starting 20240101000000
  missing intervals by month: {{'202401': 99}}

Top gaps since 2024 for gkg (count of consecutive missing 15-min files, start):
      5 intervals (~1.2 h) starting {start}
      2 intervals (~0.5 h) starting 20250612181500
  missing intervals by month: {{'202506': 7}}

-- Suspiciously small files since 2025 (below 20% of that month's median) --
"""

SAMPLE_SOURCES = """sources:
  - source_id: test-source
    name: A test source
    terms_url: https://example.org/terms
    licence: Test licence
    redistribute_ok: true
    share_alike: false
    nc: false
    attribution_text: "It's a test"
    verified_on: 2026-01-02
"""


def seedgen(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SEEDGEN), "--root", str(root), *args],
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )


def seed_json(root: Path = ROOT) -> dict[str, list[dict[str, Any]]]:
    result = seedgen("json", root=root)
    assert result.returncode == 0, result.stderr
    return cast("dict[str, list[dict[str, Any]]]", json.loads(result.stdout))


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    """A copy of the files the generator reads and writes, free to alter."""
    for relative in (MIGRATION, SOURCES):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, target)
    shutil.copytree(ROOT / GAP_DIR, tmp_path / GAP_DIR)
    return tmp_path


def replace_in(path: Path, old: str, new: str, *, every: bool = False) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {path}"
    path.write_text(text.replace(old, new, -1 if every else 1), encoding="utf-8")


def write_sample_gaps(root: Path, *, english_start: str = "20250614180000") -> None:
    (root / GAP_DIR / "english.txt").write_text(
        SAMPLE_OUTPUT.format(label="english", start=english_start), encoding="utf-8"
    )
    (root / GAP_DIR / "translated.txt").write_text(
        SAMPLE_OUTPUT.format(label="translated", start="20250614174500"), encoding="utf-8"
    )


# --- the repository as it stands -----------------------------------------------------------


def test_the_migration_seed_matches_its_sources() -> None:
    result = seedgen("check")
    assert result.returncode == 0, result.stderr


def test_sources_yml_has_the_four_phase_1_rows_with_every_field() -> None:
    rows = seed_json()["prov.source"]
    assert [row["source_id"] for row in rows] == PHASE_1_SOURCES
    for row in rows:
        assert set(row) == SOURCE_COLUMNS
        assert row["licence"].strip()
        assert row["attribution_text"].strip()
        for flag in ("redistribute_ok", "share_alike", "nc"):
            assert isinstance(row[flag], bool)
        assert date.fromisoformat(row["verified_on"]) <= datetime.now(UTC).date()


def test_the_gap_seed_has_one_june_2025_row_per_stream() -> None:
    rows = seed_json()["ingest.known_gap"]
    assert [row["stream"] for row in rows] == ["english", "translated"]
    for row in rows:
        first = datetime.fromisoformat(row["first_stamp"])
        last = datetime.fromisoformat(row["last_stamp"])
        assert (first.year, first.month) == (2025, 6)
        assert first.utcoffset() is not None and last.utcoffset() is not None
        # The count and the two ends agree: `last_stamp` is the last missing stamp, inclusive.
        assert (last - first).total_seconds() == (row["intervals"] - 1) * 900
        assert row["reason"].strip()


# --- drift is caught ------------------------------------------------------------------------


def test_check_fails_when_sources_yml_changes(copy: Path) -> None:
    replace_in(copy / SOURCES, "redistribute_ok: true", "redistribute_ok: false")
    result = seedgen("check", root=copy)
    assert result.returncode == 1
    assert "prov.source" in result.stderr


def test_check_fails_when_the_script_output_changes(copy: Path) -> None:
    # The count appears once for export and once for gkg; the generator reads gkg.
    replace_in(copy / GAP_DIR / "english.txt", "1665 intervals", "1664 intervals", every=True)
    result = seedgen("check", root=copy)
    assert result.returncode == 1
    assert "ingest.known_gap" in result.stderr


def test_check_fails_when_the_seed_is_edited_by_hand(copy: Path) -> None:
    replace_in(copy / MIGRATION, "'natural-earth'", "'natural-earth-2'")
    result = seedgen("check", root=copy)
    assert result.returncode == 1
    assert "prov.source" in result.stderr


def test_write_repairs_a_changed_seed_and_then_changes_nothing(copy: Path) -> None:
    migration = copy / MIGRATION
    original = migration.read_bytes()
    replace_in(migration, "'natural-earth'", "'natural-earth-2'")

    assert seedgen("write", root=copy).returncode == 0
    assert migration.read_bytes() == original
    assert seedgen("write", root=copy).returncode == 0
    assert migration.read_bytes() == original
    assert seedgen("check", root=copy).returncode == 0


def test_write_keeps_everything_outside_the_seed_blocks(copy: Path) -> None:
    write_sample_gaps(copy)
    (copy / SOURCES).write_text(SAMPLE_SOURCES, encoding="utf-8")
    before = (copy / MIGRATION).read_text(encoding="utf-8")

    assert seedgen("write", root=copy).returncode == 0
    after = (copy / MIGRATION).read_text(encoding="utf-8")

    assert after != before
    assert "'test-source'" in after and "'natural-earth'" not in after
    assert outside_seed_blocks(after) == outside_seed_blocks(before)


def outside_seed_blocks(text: str) -> list[str]:
    kept: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("-- seed:begin "):
            inside = True
            kept.append(line)
        elif line.startswith("-- seed:end "):
            inside = False
        if not inside:
            kept.append(line)
    return kept


# --- reading the master-list script's output -----------------------------------------------


def test_the_longest_gkg_gap_becomes_the_row(copy: Path) -> None:
    write_sample_gaps(copy)
    english, translated = seed_json(copy)["ingest.known_gap"]
    assert english == {
        "stream": "english",
        "first_stamp": "2025-06-14T18:00:00+00:00",
        "last_stamp": "2025-06-14T19:00:00+00:00",
        "intervals": 5,
        "reason": english["reason"],
    }
    assert translated["first_stamp"] == "2025-06-14T17:45:00+00:00"
    assert translated["last_stamp"] == "2025-06-14T18:45:00+00:00"
    # The reason says how far the list had been read: the last gkg stamp in the output.
    assert "2026-01-01 00:30 UTC" in english["reason"]


def test_the_export_block_is_not_mistaken_for_gkg(copy: Path) -> None:
    write_sample_gaps(copy)
    assert all(row["intervals"] == 5 for row in seed_json(copy)["ingest.known_gap"])


def test_a_longest_gap_outside_june_2025_is_an_error_not_a_seed(copy: Path) -> None:
    write_sample_gaps(copy, english_start="20240901231500")
    result = seedgen("json", root=copy)
    assert result.returncode == 2
    assert "June 2025" in result.stderr


def test_output_saved_under_the_wrong_stream_is_an_error(copy: Path) -> None:
    write_sample_gaps(copy)
    shutil.copy(copy / GAP_DIR / "translated.txt", copy / GAP_DIR / "english.txt")
    result = seedgen("json", root=copy)
    assert result.returncode == 2
    assert "english" in result.stderr


def test_output_without_a_gkg_block_is_an_error(copy: Path) -> None:
    write_sample_gaps(copy)
    replace_in(copy / GAP_DIR / "english.txt", "Top gaps since 2024 for gkg", "Top gaps for gkg")
    result = seedgen("json", root=copy)
    assert result.returncode == 2
    assert "english.txt" in result.stderr


# --- reading prov/sources.yml ----------------------------------------------------------------


def test_text_is_quoted_for_sql(copy: Path) -> None:
    (copy / SOURCES).write_text(SAMPLE_SOURCES, encoding="utf-8")
    result = seedgen("render", "prov.source", root=copy)
    assert result.returncode == 0, result.stderr
    assert "'It''s a test'" in result.stdout
    assert "date '2026-01-02'" in result.stdout


@pytest.mark.parametrize(
    ("old", "new", "complaint"),
    [
        ("    nc: false\n", "", "nc"),
        ("    nc: false\n", "    nc: no thanks\n", "nc"),
        ("    nc: false\n", "    nc: false\n    colour: blue\n", "colour"),
        ("verified_on: 2026-01-02", "verified_on: last week", "verified_on"),
        ("source_id: test-source", "source_id: Test Source", "source_id"),
        ('attribution_text: "It\'s a test"', 'attribution_text: ""', "attribution_text"),
    ],
)
def test_a_malformed_source_is_an_error(copy: Path, old: str, new: str, complaint: str) -> None:
    (copy / SOURCES).write_text(SAMPLE_SOURCES, encoding="utf-8")
    replace_in(copy / SOURCES, old, new)
    result = seedgen("json", root=copy)
    assert result.returncode == 2
    assert complaint in result.stderr


def test_a_repeated_source_id_is_an_error(copy: Path) -> None:
    entry = SAMPLE_SOURCES.split("sources:\n", 1)[1]
    (copy / SOURCES).write_text(SAMPLE_SOURCES + entry, encoding="utf-8")
    result = seedgen("json", root=copy)
    assert result.returncode == 2
    assert "test-source" in result.stderr
