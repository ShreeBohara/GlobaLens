"""Render the seed rows of db/migrations/0001_ingest.sql from their sources.

The first migration seeds two tables, and neither seed is typed by hand:

- `prov.source` comes from `prov/sources.yml`, the source of truth for upstream datasets.
- `ingest.known_gap` comes from the saved output of the master-list script, one file per stream
  in `db/seeds/known_gap/` (the command that produced them is in the README beside them).

In the migration the rows sit between a `-- seed:begin <table>` line and a `-- seed:end <table>`
line. This script owns the lines in between.

    uv run --no-sync python db/seedgen.py check    # exit 1 if the migration and sources differ
    uv run --no-sync python db/seedgen.py write    # rewrite the rows in the migration
    uv run --no-sync python db/seedgen.py render prov.source
    uv run --no-sync python db/seedgen.py json     # the rows as data, for the SQL tests

Exit status: 0 in step, 1 the migration differs from its sources, 2 a source cannot be read.
"""

from __future__ import annotations

import argparse
import difflib
import io
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import yaml

MIGRATION = Path("db/migrations/0001_ingest.sql")
SOURCES = Path("prov/sources.yml")
GAP_DIR = Path("db/seeds/known_gap")

STREAMS = ("english", "translated")
TABLES = ("ingest.known_gap", "prov.source")  # in the order the migration seeds them

# prov.source's columns, in order, and the keys of an entry that are not columns.
TEXT_COLUMNS = ("source_id", "licence", "attribution_text")
FLAG_COLUMNS = ("redistribute_ok", "share_alike", "nc")
SOURCE_KEYS = frozenset({*TEXT_COLUMNS, *FLAG_COLUMNS, "verified_on"})
OTHER_KEYS = frozenset({"name", "terms_url"})
SOURCE_ID = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")

# The lines of analyze_masterlist.py's output that are read here.
LABEL_LINE = re.compile(r"== (\S+): unparsed lines=\d+")
GKG_FILES_LINE = re.compile(r"gkg: files=\d+ first=\d{14} last=(\d{14})")
GKG_GAPS_HEADING = "Top gaps since 2024 for gkg "
GAP_LINE = re.compile(r"\s*(\d+) intervals \(~[\d.]+ h\) starting (\d{14})")
STEP = timedelta(minutes=15)


class SeedError(Exception):
    """A source of the seed cannot be read, or the migration has lost its markers."""


@dataclass(frozen=True)
class Source:
    source_id: str
    licence: str
    redistribute_ok: bool
    share_alike: bool
    nc: bool
    attribution_text: str
    verified_on: date


@dataclass(frozen=True)
class Gap:
    stream: str
    first_stamp: datetime
    last_stamp: datetime  # the last missing stamp, inclusive
    intervals: int
    reason: str


# --- prov/sources.yml ----------------------------------------------------------------------


def load_sources(path: Path) -> list[Source]:
    try:
        document: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise SeedError(f"{path}: cannot be read as YAML: {error}") from error

    top = mapping(document, str(path))
    if set(top) != {"sources"}:
        raise SeedError(f"{path}: expected one top-level key, `sources`")
    entries = top["sources"]
    if not isinstance(entries, list) or not entries:
        raise SeedError(f"{path}: `sources` must be a list with at least one entry")

    sources: list[Source] = []
    for number, entry in enumerate(cast("list[object]", entries), start=1):
        source = read_source(mapping(entry, f"{path}: entry {number}"), f"{path}: entry {number}")
        if any(source.source_id == earlier.source_id for earlier in sources):
            raise SeedError(f"{path}: source_id {source.source_id!r} appears twice")
        sources.append(source)
    return sources


def mapping(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SeedError(f"{where}: expected a mapping")
    items = cast("dict[object, object]", value)
    for key in items:
        if not isinstance(key, str):
            raise SeedError(f"{where}: key {key!r} is not a string")
    return cast("dict[str, object]", items)


def read_source(entry: dict[str, object], where: str) -> Source:
    missing = sorted((SOURCE_KEYS | OTHER_KEYS) - set(entry))
    unknown = sorted(set(entry) - SOURCE_KEYS - OTHER_KEYS)
    if missing:
        raise SeedError(f"{where}: missing {', '.join(missing)}")
    if unknown:
        raise SeedError(f"{where}: unknown key {', '.join(unknown)}")

    text = {key: text_value(entry[key], f"{where}: {key}") for key in (*TEXT_COLUMNS, *OTHER_KEYS)}
    flags: dict[str, bool] = {}
    for key in FLAG_COLUMNS:
        flag = entry[key]
        if not isinstance(flag, bool):
            raise SeedError(f"{where}: {key} must be true or false, not {flag!r}")
        flags[key] = flag
    verified_on = entry["verified_on"]
    if not isinstance(verified_on, date) or isinstance(verified_on, datetime):
        raise SeedError(f"{where}: verified_on must be a date (YYYY-MM-DD), not {verified_on!r}")
    if not SOURCE_ID.fullmatch(text["source_id"]):
        raise SeedError(
            f"{where}: source_id {text['source_id']!r} must be lower-case letters and digits,"
            " joined by `-` or `.`"
        )
    return Source(
        source_id=text["source_id"],
        licence=text["licence"],
        redistribute_ok=flags["redistribute_ok"],
        share_alike=flags["share_alike"],
        nc=flags["nc"],
        attribution_text=text["attribution_text"],
        verified_on=verified_on,
    )


def text_value(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SeedError(f"{where} must be text and may not be empty")
    if value != value.strip() or any(ord(character) < 32 for character in value):
        raise SeedError(f"{where} has leading or trailing space, or a control character")
    return value


# --- the master-list script's output ---------------------------------------------------------


def load_gaps(folder: Path) -> list[Gap]:
    return [read_gap(folder / f"{stream}.txt", stream) for stream in STREAMS]


def read_gap(path: Path, stream: str) -> Gap:
    """The June 2025 gap of one stream: the longest run of missing gkg files in the output."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SeedError(f"{path}: cannot be read: {error}") from error

    label = LABEL_LINE.fullmatch(lines[0]) if lines else None
    if label is None or label[1] != stream:
        raise SeedError(f"{path}: the first line must be the script's output labelled {stream!r}")
    read_up_to = [found[1] for line in lines if (found := GKG_FILES_LINE.fullmatch(line))]
    if len(read_up_to) != 1:
        raise SeedError(f"{path}: expected one `gkg: files=… last=…` line")

    headings = [index for index, line in enumerate(lines) if line.startswith(GKG_GAPS_HEADING)]
    if len(headings) != 1:
        raise SeedError(f"{path}: expected one {GKG_GAPS_HEADING.strip()!r} block")
    runs: list[tuple[int, datetime]] = []
    for line in lines[headings[0] + 1 :]:
        found = GAP_LINE.fullmatch(line)
        if found is None:
            break
        runs.append((int(found[1]), stamp(found[2], path)))
    if not runs:
        raise SeedError(f"{path}: the gkg block lists no gap")

    intervals, first = max(runs)
    if sum(1 for length, _ in runs if length == intervals) > 1:
        raise SeedError(f"{path}: two gkg gaps share the greatest length, {intervals} intervals")
    if (first.year, first.month) != (2025, 6):
        raise SeedError(
            f"{path}: the longest gkg gap starts {first:%Y-%m-%d %H:%M} UTC, which is not the"
            " June 2025 gap. Read the output before seeding anything from it."
        )
    return Gap(
        stream=stream,
        first_stamp=first,
        last_stamp=first + (intervals - 1) * STEP,
        intervals=intervals,
        reason=(
            "Never published by GDELT: the master file list has no gkg file for these stamps"
            f" (list read up to {stamp(read_up_to[0], path):%Y-%m-%d %H:%M} UTC)"
        ),
    )


def stamp(text: str, path: Path) -> datetime:
    """A GDELT file stamp (YYYYMMDDHHMMSS, UTC), which must be on the 15-minute grid."""
    try:
        value = datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError as error:
        raise SeedError(f"{path}: {text!r} is not a stamp") from error
    if value.minute % 15 or value.second:
        raise SeedError(f"{path}: stamp {text} is not on the 15-minute grid")
    return value


# --- SQL and JSON --------------------------------------------------------------------------------
#
# A row is written out field by field, in the order its class declares them, so the class is
# the one list of a table's seeded columns.


def load_rows(root: Path) -> dict[str, Sequence[Source | Gap]]:
    return {
        "ingest.known_gap": load_gaps(root / GAP_DIR),
        "prov.source": load_sources(root / SOURCES),
    }


def literal(value: object) -> str:
    """A value as an SQL literal. Text was checked for control characters when it was read."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        return f"timestamptz '{value.astimezone(UTC):%Y-%m-%d %H:%M:%S}+00'"
    if isinstance(value, date):
        return f"date '{value.isoformat()}'"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"no SQL literal for {value!r}")


def render(table: str, rows: Sequence[Source | Gap]) -> str:
    columns = [field.name for field in fields(rows[0])]
    values = [
        "  (" + ", ".join(literal(getattr(row, name)) for name in columns) + ")" for row in rows
    ]
    return f"insert into {table}\n  ({', '.join(columns)})\nvalues\n" + ",\n".join(values) + ";\n"


def render_all(root: Path) -> dict[str, str]:
    return {table: render(table, rows) for table, rows in load_rows(root).items()}


def as_data(root: Path) -> dict[str, list[dict[str, object]]]:
    """The rows as JSON-ready data, with times written as PostgreSQL's own JSON writes them."""

    def plain(value: object) -> object:
        return value.isoformat() if isinstance(value, date) else value

    return {
        table: [
            {field.name: plain(getattr(row, field.name)) for field in fields(row)} for row in rows
        ]
        for table, rows in load_rows(root).items()
    }


# --- the blocks in the migration -----------------------------------------------------------------


def block(table: str) -> re.Pattern[str]:
    name = re.escape(table)
    return re.compile(
        rf"^(-- seed:begin {name} [^\n]*\n)(.*?)^(-- seed:end {name}\n)", re.MULTILINE | re.DOTALL
    )


def current_rows(migration: str, table: str, path: Path) -> str:
    found = block(table).findall(migration)
    if len(found) != 1:
        raise SeedError(
            f"{path}: expected one `-- seed:begin {table} …` / `-- seed:end {table}` pair,"
            f" found {len(found)}"
        )
    return cast("tuple[str, str, str]", found[0])[1]


def check(root: Path) -> int:
    path = root / MIGRATION
    migration = path.read_text(encoding="utf-8")
    differing = 0
    for table, wanted in render_all(root).items():
        have = current_rows(migration, table, path)
        if have == wanted:
            continue
        differing += 1
        print(f"{MIGRATION}: the {table} seed differs from its source:", file=sys.stderr)
        sys.stderr.writelines(
            difflib.unified_diff(
                have.splitlines(keepends=True),
                wanted.splitlines(keepends=True),
                fromfile="in the migration",
                tofile="from the source",
            )
        )
    if differing:
        print(
            "If 0001 has not been applied to production, rewrite the rows with"
            " `uv run --no-sync python db/seedgen.py write`."
            " If it has, the change belongs in a new migration (db/README.md).",
            file=sys.stderr,
        )
    return 1 if differing else 0


def write(root: Path) -> int:
    path = root / MIGRATION
    migration = path.read_text(encoding="utf-8")
    updated = migration
    for table, wanted in render_all(root).items():
        current_rows(updated, table, path)  # exactly one block, or an error
        updated = block(table).sub(lambda match, rows=wanted: match[1] + rows + match[3], updated)
    if updated != migration:
        path.write_text(updated, encoding="utf-8")
        print(f"{MIGRATION}: seed rows rewritten")
    else:
        print(f"{MIGRATION}: seed rows already in step")
    return 0


def main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="the repository root (default: the one this file is in)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="exit 1 if the migration's seed differs from its sources")
    commands.add_parser("write", help="rewrite the seed rows in the migration")
    commands.add_parser("json", help="print the rows as JSON")
    one_table = commands.add_parser("render", help="print the SQL for one table")
    one_table.add_argument("table", choices=TABLES)
    options = parser.parse_args(arguments)
    # The credits contain "©": write UTF-8 whatever the locale of the calling shell is.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    root = cast("Path", options.root)
    command = cast("str", options.command)

    try:
        if command == "check":
            return check(root)
        if command == "write":
            return write(root)
        if command == "json":
            print(json.dumps(as_data(root), indent=2, ensure_ascii=False))
            return 0
        print(render_all(root)[cast("str", options.table)], end="")
        return 0
    except SeedError as error:
        print(f"seedgen: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
