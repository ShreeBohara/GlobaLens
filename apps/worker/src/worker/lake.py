"""The lake's two Parquet files for one GKG file: facts, and display.

Facts hold what an article is and where: IDs, times, outlet, language, the primary location,
tone, themes, every place mentioned, and the hash of the title. Display holds the title and
the URL, the part that may have to be redacted later, keyed by the same `seq`. Row order is
file order in both.

The same rows must give the same bytes on every run, because the object key is a hash of the
bytes (`worker.ledger.keys`). So every writer option is fixed here, pyarrow is pinned to one
exact version (docs/adr/0010), and nothing that varies between runs (a time, a host name, the
order of a set) goes into either file.

Data: the GDELT Project (https://www.gdeltproject.org/).
"""

# pyarrow ships no type information, so its calls are unknown to pyright. This module is the
# only one that touches it; what goes in and what comes out are typed.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import io
import json
from collections.abc import Sequence
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from gdelt import LeanRow, ParseStats

__all__ = ["DISPLAY_SCHEMA", "FACTS_SCHEMA", "build"]

FACTS_SCHEMA = "gkg-facts/1"
DISPLAY_SCHEMA = "gkg-display/1"

_SECONDS = pa.timestamp("s", tz="UTC")
_TONE = (
    "tone",
    "tone_positive",
    "tone_negative",
    "tone_polarity",
    "tone_activity_density",
    "tone_self_group_density",
    "tone_word_count",
)
_LOCATION = pa.struct(
    [
        pa.field("geo_type", pa.uint8(), nullable=False),
        pa.field("name", pa.string(), nullable=False),
        pa.field("country", pa.string(), nullable=False),
        pa.field("adm1", pa.string(), nullable=False),
        pa.field("adm2", pa.string(), nullable=False),
        pa.field("lat", pa.float64()),
        pa.field("lon", pa.float64()),
        pa.field("feature_id", pa.string(), nullable=False),
        pa.field("offset", pa.uint32(), nullable=False),
    ]
)
_FACTS = pa.schema(
    [
        pa.field("seq", pa.uint32(), nullable=False),  # the record number inside the interval
        pa.field("record_id", pa.string(), nullable=False),
        pa.field("stamp", _SECONDS, nullable=False),
        pa.field("published_at", _SECONDS),
        pa.field("outlet", pa.string(), nullable=False),
        pa.field("srclc", pa.string()),  # GDELT's source-language code as given
        pa.field("lang", pa.string()),  # the language table's code; null when not known
        pa.field("translation_info", pa.string(), nullable=False),
        pa.field("title_hash", pa.binary(8)),
        # The primary location. `lat` and `lon` are set for a point (geo_type 3 or 4) only.
        pa.field("geo_type", pa.uint8()),
        pa.field("lat", pa.float64()),
        pa.field("lon", pa.float64()),
        pa.field("country", pa.string()),
        pa.field("adm1", pa.string()),
        pa.field("place", pa.string()),
        pa.field("feature_id", pa.string()),
        pa.field("demoted", pa.bool_()),
        *(pa.field(name, pa.float64()) for name in _TONE),
        pa.field("themes", pa.list_(pa.field("item", pa.string(), nullable=False)), nullable=False),
        pa.field(
            "locations", pa.list_(pa.field("item", _LOCATION, nullable=False)), nullable=False
        ),
    ]
)
_DISPLAY = pa.schema(
    [
        pa.field("seq", pa.uint32(), nullable=False),
        pa.field("title", pa.string()),
        pa.field("url", pa.string()),
    ]
)


def _parse_summary(stats: ParseStats) -> str:
    """The parser's counts as JSON with sorted keys: how many lines were quarantined, and why."""
    summary = {
        "lines": stats.lines,
        "rows": stats.rows,
        "blank_lines": stats.blank_lines,
        "quarantined": dict(stats.quarantined),
        "issues": dict(stats.issues),
        "unknown_srclc": dict(stats.unknown_srclc),
    }
    return json.dumps(summary, sort_keys=True, separators=(",", ":"))


def _write(columns: dict[str, list[Any]], schema: Any, metadata: dict[str, str]) -> bytes:
    table = pa.Table.from_pydict(columns, schema=schema.with_metadata(metadata))
    sink = io.BytesIO()
    pq.write_table(
        table,
        sink,
        version="2.6",
        data_page_version="1.0",
        compression="zstd",
        compression_level=9,
        use_dictionary=True,
        write_statistics=True,
        store_schema=True,
        row_group_size=1 << 20,  # one row group: an interval is a few thousand rows
    )
    return sink.getvalue()


def build(rows: Sequence[LeanRow], stats: ParseStats) -> tuple[bytes, bytes]:
    """The facts file and the display file for one GKG file's rows, as bytes."""
    facts: dict[str, list[Any]] = {name: [] for name in _FACTS.names}
    display: dict[str, list[Any]] = {name: [] for name in _DISPLAY.names}
    for row in rows:
        primary = row.primary
        facts["seq"].append(row.seq)
        facts["record_id"].append(row.record_id)
        facts["stamp"].append(row.stamp)
        facts["published_at"].append(row.published_at)
        facts["outlet"].append(row.outlet)
        facts["srclc"].append(row.srclc)
        facts["lang"].append(None if row.lang is None else row.lang.code)
        facts["translation_info"].append(row.translation_info)
        facts["title_hash"].append(row.title_hash)
        facts["geo_type"].append(None if primary is None else primary.geo_type)
        facts["lat"].append(None if primary is None else primary.lat)
        facts["lon"].append(None if primary is None else primary.lon)
        facts["country"].append(None if primary is None else primary.country)
        facts["adm1"].append(None if primary is None else primary.adm1)
        facts["place"].append(None if primary is None else primary.name)
        facts["feature_id"].append(None if primary is None else primary.feature_id)
        facts["demoted"].append(None if primary is None else primary.demoted)
        for index, name in enumerate(_TONE):
            facts[name].append(None if row.tone is None else row.tone[index])
        facts["themes"].append(list(row.themes))
        facts["locations"].append([location._asdict() for location in row.locations])
        display["seq"].append(row.seq)
        display["title"].append(row.title)
        display["url"].append(row.url)
    return (
        _write(facts, _FACTS, {"gl.schema": FACTS_SCHEMA, "gl.parse": _parse_summary(stats)}),
        _write(display, _DISPLAY, {"gl.schema": DISPLAY_SCHEMA}),
    )
