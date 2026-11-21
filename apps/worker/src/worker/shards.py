"""The data plane's Arrow objects: the point shard and the title shards.

docs/design/p1.md §6.3 and §6.4. Each table is one Arrow IPC stream (the streaming format: a
schema message, one record batch, the end marker) with every buffer compressed with zstd, the
path §6.5 ships in P1. The browser reads them with flechette and a zstd codec.

**Point shard.** Two streams back to back in one object, `points` then `areas`. The manifest
gives each one's offset and length; the page fetches the object whole and slices it.

`points`, one row per city-level article (the primary location's Geo_Type is 3 or 4):

    x, y, z   int16   the unit vector times 32767, rounded: x towards 0°N 0°E, y towards
                      0°N 90°E, z towards the North Pole. The wire format only: the page divides
                      by 32767 and normalizes each row in double precision (§6.3.1)
    prec      uint8   Geo_Type: 3 (US city) or 4 (world city)
    cell      uint8   the H3 base cell, 0 to 121: which title shard holds the row's title
    lang      uint8   the row's index in gdelt.LANGS; 255 when the language is not known
    outlet    uint32  the first four bytes of SHA-256 over the outlet's domain, big-endian
    t         int32   minutes since 1970: the precise publication time if GDELT gives one,
                      otherwise the stamp
    iv        uint32  the stamp as a count of 15-minute intervals since 1970
    key       uint32  bit 31: the stream (1 for translated); bit 30: the repeat bit; bits 0 to
                      29: the record number, which holds every number the contract allows

The row's identity is (`iv`, `key`), and it rebuilds the GKG record ID (`record_id`). The
repeat bit exists because a record ID is not always unique: GDELT sometimes writes two batches
into one translated file, and the second batch's record numbers start again from 0, each naming
a different article. The second row of a file with the same key has the repeat bit set, so
(`iv`, `key`) stays unique and both rows keep the record ID GDELT gave them. No third such row
has been seen; one would be left out of the shards, with a warning in the log. `read_articles`
says what else it does so that no row the parser kept can stop a pass.

`areas`, counts and never rows: one row per (kind, code, lang) with at least one article.

    kind      uint8   0 no location, 1 country, 2 US state, 5 ADM1
    code      dictionary<int32, utf8>  GDELT's FIPS country code (kind 1) or ADM1 code (2, 5);
                      empty for kind 0
    lang      uint8
    n         uint32  articles

**Title shards.** One object per H3 base cell with titled city-level rows, and one for the
titled country-level rows (kinds 1, 2 and 5). Unlocated rows and rows without a title have no
title row. Columns: `iv`, `key`, `lang`, `t` as above; `title` (utf8), `url` (utf8, null when
GDELT's identifier is not an http(s) link), `outlet` (dictionary<int32, utf8>, the domain as
GDELT gives it), `title_hash` (fixed_size_binary(8)); the country-level shard adds `kind` and
`code`. When more than MAX_TITLE_SHARDS cells have titles, the quietest share one object, so
a pass never writes more title objects than the write budget plans for (master plan §7,
coarsening step 2).

Rows are in (`iv`, `key`) order, and nothing that varies between runs goes into an object, so
the same articles give the same bytes on every run: the objects are stored under the hash of
their bytes.

Data: the GDELT Project (https://www.gdeltproject.org/).
"""

# pyarrow ships no type information, so its calls are unknown to pyright. This module and
# worker.lake are the only ones that touch it; what goes in and what comes out are typed.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import hashlib
import io
import logging
import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

import pyarrow as pa
import pyarrow.parquet as pq
from gdelt import BLOCKLISTED_CENTROIDS, LANG_TABLE_VERSION, LANGS, Stream

from worker import lake
from worker.cells import base_cell
from worker.stamps import format_stamp, on_grid

__all__ = [
    "LANG_TABLE_VERSION",
    "MAX_TITLE_SHARDS",
    "SCALE",
    "UNKNOWN_LANG",
    "ZSTD_LEVEL",
    "AreaRow",
    "Article",
    "PointRow",
    "PointShard",
    "TitleRow",
    "TitleShard",
    "interval_index",
    "is_repeat",
    "make_key",
    "minutes",
    "outlet_hash",
    "point_shard",
    "quantize",
    "read_areas",
    "read_articles",
    "read_points",
    "read_titles",
    "record_id",
    "schema_metadata",
    "stamp_of",
    "title_shards",
]

SCALE = 32767
"""A unit vector's components are stored as round(component × SCALE)."""

UNKNOWN_LANG = 255
"""The `lang` of a row whose language is not in the table."""

MAX_TITLE_SHARDS = 60
"""At most this many title objects for the cells of one unit (master plan §7: title shards for
the res-0 cells with coverage, at most 60). A compaction is given a lower limit: see
worker.dataplane."""

ZSTD_LEVEL = 19
"""The zstd level of every buffer. A design value: decoding speed does not depend on it."""

log = logging.getLogger(__name__)

_INTERVAL = timedelta(minutes=15)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_TRANSLATED_BIT = 1 << 31
_REPEAT_BIT = 1 << 30
_T_MIN, _T_MAX = -(1 << 31), (1 << 31) - 1  # what the int32 `t` column holds
_POINT_KINDS = (3, 4)
_AREA_KINDS = (0, 1, 2, 5)
_TITLED_AREA_KINDS = (1, 2, 5)
_LANG_INDEX = {lang.code: lang.index for lang in LANGS}

_METADATA = {"gl.langs": str(LANG_TABLE_VERSION)}
_POINTS = pa.schema(
    [
        pa.field("x", pa.int16(), nullable=False),
        pa.field("y", pa.int16(), nullable=False),
        pa.field("z", pa.int16(), nullable=False),
        pa.field("prec", pa.uint8(), nullable=False),
        pa.field("cell", pa.uint8(), nullable=False),
        pa.field("lang", pa.uint8(), nullable=False),
        pa.field("outlet", pa.uint32(), nullable=False),
        pa.field("t", pa.int32(), nullable=False),
        pa.field("iv", pa.uint32(), nullable=False),
        pa.field("key", pa.uint32(), nullable=False),
    ],
    metadata={"gl.schema": "points/1", **_METADATA},
)
_DICTIONARY = pa.dictionary(pa.int32(), pa.string())
_AREAS = pa.schema(
    [
        pa.field("kind", pa.uint8(), nullable=False),
        pa.field("code", _DICTIONARY, nullable=False),
        pa.field("lang", pa.uint8(), nullable=False),
        pa.field("n", pa.uint32(), nullable=False),
    ],
    metadata={"gl.schema": "areas/1", **_METADATA},
)
_TITLE_FIELDS = [
    pa.field("iv", pa.uint32(), nullable=False),
    pa.field("key", pa.uint32(), nullable=False),
    pa.field("lang", pa.uint8(), nullable=False),
    pa.field("t", pa.int32(), nullable=False),
    pa.field("title", pa.string(), nullable=False),
    pa.field("url", pa.string()),
    pa.field("outlet", _DICTIONARY, nullable=False),
    pa.field("title_hash", pa.binary(8), nullable=False),
]
_TITLES = pa.schema(_TITLE_FIELDS, metadata={"gl.schema": "titles/1", **_METADATA})
_COUNTRY_TITLES = pa.schema(
    [
        *_TITLE_FIELDS,
        pa.field("kind", pa.uint8(), nullable=False),
        pa.field("code", _DICTIONARY, nullable=False),
    ],
    metadata={"gl.schema": "country-titles/1", **_METADATA},
)
_IPC = pa.ipc.IpcWriteOptions(
    compression=pa.Codec("zstd", compression_level=ZSTD_LEVEL), use_threads=False
)


# --- Identity ----------------------------------------------------------------------------


def interval_index(stamp: datetime) -> int:
    """The stamp as a count of 15-minute intervals since 1970: the `iv` column."""
    if not on_grid(stamp):
        raise ValueError(f"not a UTC time on the 15-minute grid: {stamp!r}")
    return (stamp - _EPOCH) // _INTERVAL


def stamp_of(iv: int) -> datetime:
    """The stamp of interval number `iv`."""
    return _EPOCH + iv * _INTERVAL


def minutes(time: datetime) -> int:
    """Whole minutes since 1970: the `t` column."""
    return (time - _EPOCH) // timedelta(minutes=1)


def make_key(stream: Stream, record: int, *, repeat: bool = False) -> int:
    """The `key` column: the stream, the repeat bit, the record number."""
    if not 0 <= record < _REPEAT_BIT:
        raise ValueError(f"a record number must fit in 30 bits: {record}")
    stream_bit = _TRANSLATED_BIT if stream is Stream.TRANSLATED else 0
    return record | stream_bit | (_REPEAT_BIT if repeat else 0)


def is_repeat(key: int) -> bool:
    """True for the second row of a file with the same record ID."""
    return bool(key & _REPEAT_BIT)


def record_id(iv: int, key: int) -> str:
    """The GKG record ID that (`iv`, `key`) stands for. Two rows can share it: see the repeat
    bit."""
    translated = "T" if key & _TRANSLATED_BIT else ""
    return f"{format_stamp(stamp_of(iv))}-{translated}{key & (_REPEAT_BIT - 1)}"


def quantize(lat: float, lon: float) -> tuple[int, int, int]:
    """The unit vector of a point, each component times SCALE and rounded."""
    phi, lam = math.radians(lat), math.radians(lon)
    across = math.cos(phi)
    return (
        round(across * math.cos(lam) * SCALE),
        round(across * math.sin(lam) * SCALE),
        round(math.sin(phi) * SCALE),
    )


def outlet_hash(outlet: str) -> int:
    """The `outlet` column of the point shard: enough to count distinct outlets."""
    return int.from_bytes(hashlib.sha256(outlet.encode("utf-8")).digest()[:4], "big")


# --- Articles, from the lake ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Article:
    """One article as the publisher uses it."""

    iv: int
    key: int
    lang: int  # index in gdelt.LANGS, or UNKNOWN_LANG
    t: int  # minutes since 1970
    outlet: str
    kind: int  # the primary location's Geo_Type, 0 for none
    code: str  # the country (kind 1) or ADM1 (kinds 2 and 5) code; empty otherwise
    lat: float | None  # set for kinds 3 and 4 only
    lon: float | None
    title: str | None
    url: str | None
    title_hash: bytes | None


_FACTS_COLUMNS = [
    "seq",
    "record_id",
    "published_at",
    "outlet",
    "lang",
    "title_hash",
    "geo_type",
    "lat",
    "lon",
    "country",
    "adm1",
]


def _parquet(data: bytes, columns: list[str], schema: str) -> dict[str, list[Any]]:
    table = pq.read_table(io.BytesIO(data), columns=columns)
    metadata = table.schema.metadata or {}
    found = metadata.get(b"gl.schema", b"").decode()
    if found != schema:
        raise ValueError(f"expected a {schema} file, found {found or 'no schema name'}")
    return {name: table.column(name).to_pylist() for name in columns}


def read_articles(stream: Stream, stamp: datetime, facts: bytes, display: bytes) -> list[Article]:
    """The articles of one interval's lake files (`worker.lake`), in file order.

    Every row the parser kept becomes an article, so no row can stop a pass:

    - `iv` is the interval's own stamp. GDELT's record IDs start with it (every row of the
      fixture week does); a row whose record ID names another time stays in its interval.
    - The repeat bit goes to the second row of the file with the same key, whatever made the
      key the same: a second batch numbered from 0 again, a record number written with a
      leading zero, a `T` that does not match the file's stream. A third such row is left out,
      with a warning.
    - A publication time that the `t` column cannot hold falls back to the stamp.
    - A city-level row on a blocklisted centroid counts as country-level, as the parser
      counts it; one without coordinates counts as unlocated. Neither is expected: the parser
      does not write such rows.
    - A language code that is no longer in the table is unknown (255).
    """
    fact = _parquet(facts, _FACTS_COLUMNS, lake.FACTS_SCHEMA)
    shown = _parquet(display, ["seq", "title", "url"], lake.DISPLAY_SCHEMA)
    if fact["seq"] != shown["seq"]:
        raise ValueError("the facts and display files do not hold the same rows")
    iv = interval_index(stamp)
    stamp_minutes = minutes(stamp)
    articles: list[Article] = []
    seen: Counter[int] = Counter()
    for index, seq in enumerate(fact["seq"]):
        key = make_key(stream, seq)
        seen[key] += 1
        if seen[key] > 2:
            log.warning(
                "%s appears %d times in its file; this row is left out",
                fact["record_id"][index],
                seen[key],
            )
            continue
        kind: int = fact["geo_type"][index] or 0
        lat: float | None = fact["lat"][index]
        lon: float | None = fact["lon"][index]
        if kind in _POINT_KINDS:
            if lat is None or lon is None:
                log.warning("%s is city-level with no coordinates", fact["record_id"][index])
                kind = 0
            elif (lat, lon) in BLOCKLISTED_CENTROIDS:
                log.warning("%s sits on a blocklisted centroid", fact["record_id"][index])
                kind = 1
        code = ""
        if kind == 1:
            code = fact["country"][index] or ""
        elif kind in (2, 5):
            code = fact["adm1"][index] or ""
        point = kind in _POINT_KINDS
        lang_code: str | None = fact["lang"][index]
        published: datetime | None = fact["published_at"][index]
        t = stamp_minutes if published is None else minutes(published)
        if not _T_MIN <= t <= _T_MAX:
            t = stamp_minutes
        articles.append(
            Article(
                iv=iv,
                key=key | (_REPEAT_BIT if seen[key] == 2 else 0),
                lang=UNKNOWN_LANG
                if lang_code is None
                else _LANG_INDEX.get(lang_code, UNKNOWN_LANG),
                t=t,
                outlet=fact["outlet"][index],
                kind=kind,
                code=code,
                lat=lat if point else None,
                lon=lon if point else None,
                title=shown["title"][index],
                url=shown["url"][index],
                title_hash=fact["title_hash"][index],
            )
        )
    return articles


# --- Writing ---------------------------------------------------------------------------------


def _stream(columns: dict[str, list[Any]], schema: Any) -> bytes:
    arrays = []
    for field in schema:
        values = columns[field.name]
        if pa.types.is_dictionary(field.type):
            arrays.append(pa.array(values, pa.string()).dictionary_encode())
        else:
            arrays.append(pa.array(values, field.type))
    table = pa.Table.from_arrays(arrays, schema=schema)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, schema, options=_IPC) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _ordered(articles: Iterable[Article]) -> list[Article]:
    ordered = sorted(articles, key=lambda a: (a.iv, a.key))
    for before, after in zip(ordered, ordered[1:], strict=False):
        if (before.iv, before.key) == (after.iv, after.key):
            raise ValueError(f"two articles are {record_id(after.iv, after.key)}")
    return ordered


@dataclass(frozen=True, slots=True)
class PointShard:
    """A point shard's bytes, its two segments as (offset, length), and its point rows."""

    data: bytes
    points: tuple[int, int]
    areas: tuple[int, int]
    rows: int


def point_shard(articles: Iterable[Article]) -> PointShard:
    """The point shard of these articles: city-level ones as rows, the rest as counts."""
    columns: dict[str, list[Any]] = {name: [] for name in _POINTS.names}
    counts: Counter[tuple[int, str, int]] = Counter()
    for a in _ordered(articles):
        if a.kind not in _POINT_KINDS:
            if a.kind not in _AREA_KINDS:
                raise ValueError(f"{record_id(a.iv, a.key)} has Geo_Type {a.kind}")
            counts[(a.kind, a.code, a.lang)] += 1
            continue
        if a.lat is None or a.lon is None:
            raise ValueError(f"{record_id(a.iv, a.key)} is city-level and has no coordinates")
        if (a.lat, a.lon) in BLOCKLISTED_CENTROIDS:
            raise ValueError(f"{record_id(a.iv, a.key)} sits on a blocklisted centroid")
        x, y, z = quantize(a.lat, a.lon)
        columns["x"].append(x)
        columns["y"].append(y)
        columns["z"].append(z)
        columns["prec"].append(a.kind)
        columns["cell"].append(base_cell(a.lat, a.lon))
        columns["lang"].append(a.lang)
        columns["outlet"].append(outlet_hash(a.outlet))
        columns["t"].append(a.t)
        columns["iv"].append(a.iv)
        columns["key"].append(a.key)
    areas: dict[str, list[Any]] = {"kind": [], "code": [], "lang": [], "n": []}
    for (kind, code, lang), n in sorted(counts.items()):
        areas["kind"].append(kind)
        areas["code"].append(code)
        areas["lang"].append(lang)
        areas["n"].append(n)
    points = _stream(columns, _POINTS)
    counted = _stream(areas, _AREAS)
    return PointShard(
        data=points + counted,
        points=(0, len(points)),
        areas=(len(points), len(counted)),
        rows=len(columns["key"]),
    )


@dataclass(frozen=True, slots=True)
class TitleShard:
    """A title shard's bytes, its rows, and the cells whose titles it holds (none for the
    country-level shard)."""

    data: bytes
    rows: int
    cells: tuple[int, ...]


def _title_columns(articles: list[Article], *, country: bool) -> dict[str, list[Any]]:
    schema = _COUNTRY_TITLES if country else _TITLES
    columns: dict[str, list[Any]] = {name: [] for name in schema.names}
    for a in articles:
        columns["iv"].append(a.iv)
        columns["key"].append(a.key)
        columns["lang"].append(a.lang)
        columns["t"].append(a.t)
        columns["title"].append(a.title)
        columns["url"].append(a.url)
        columns["outlet"].append(a.outlet)
        columns["title_hash"].append(a.title_hash)
        if country:
            columns["kind"].append(a.kind)
            columns["code"].append(a.code)
    return columns


def title_shards(
    articles: Iterable[Article], *, limit: int = MAX_TITLE_SHARDS
) -> tuple[list[TitleShard], TitleShard | None]:
    """The cell title shards of these articles, in cell order, and the country-level one. At
    most `limit` cell shards: past it, the quietest cells share the last one."""
    if limit < 1:
        raise ValueError(f"at least one title shard is needed, not {limit}")
    by_cell: dict[int, list[Article]] = {}
    country: list[Article] = []
    for a in _ordered(articles):
        if a.title is None or a.title_hash is None:
            continue  # the parser always hashes a title it keeps
        if a.kind in _POINT_KINDS:
            assert a.lat is not None and a.lon is not None
            by_cell.setdefault(base_cell(a.lat, a.lon), []).append(a)
        elif a.kind in _TITLED_AREA_KINDS:
            country.append(a)

    # Busiest first; past the limit, the quietest cells share the last object.
    ranked = sorted(by_cell, key=lambda cell: (-len(by_cell[cell]), cell))
    groups = [(cell,) for cell in ranked]
    if len(groups) > limit:
        groups = groups[: limit - 1] + [tuple(ranked[limit - 1 :])]
    cells: list[TitleShard] = []
    for group in sorted(tuple(sorted(g)) for g in groups):
        rows = _ordered(a for cell in group for a in by_cell[cell])
        data = _stream(_title_columns(rows, country=False), _TITLES)
        cells.append(TitleShard(data=data, rows=len(rows), cells=group))
    country_shard = None
    if country:
        data = _stream(_title_columns(country, country=True), _COUNTRY_TITLES)
        country_shard = TitleShard(data=data, rows=len(country), cells=())
    return cells, country_shard


# --- Reading ---------------------------------------------------------------------------------


def _read(data: bytes, segment: tuple[int, int] | None = None) -> Any:
    start, length = segment if segment is not None else (0, len(data))
    if start < 0 or length < 0 or start + length > len(data):
        raise ValueError(f"segment {segment} is outside an object of {len(data)} bytes")
    return pa.ipc.open_stream(pa.py_buffer(data[start : start + length])).read_all()


def schema_metadata(data: bytes, segment: tuple[int, int] | None = None) -> dict[str, str]:
    """The key-value metadata of a stream's schema."""
    metadata = _read(data, segment).schema.metadata or {}
    return {key.decode(): value.decode() for key, value in metadata.items()}


class PointRow(NamedTuple):
    x: int
    y: int
    z: int
    prec: int
    cell: int
    lang: int
    outlet: int
    t: int
    iv: int
    key: int


class AreaRow(NamedTuple):
    kind: int
    code: str
    lang: int
    n: int


class TitleRow(NamedTuple):
    iv: int
    key: int
    lang: int
    t: int
    title: str
    url: str | None
    outlet: str
    title_hash: bytes
    kind: int | None  # the country-level shard only
    code: str | None


def _rows(table: Any, names: list[str]) -> list[list[Any]]:
    columns = [table.column(name).to_pylist() for name in names]
    return [list(row) for row in zip(*columns, strict=True)] if columns else []


def read_points(data: bytes, segment: tuple[int, int]) -> list[PointRow]:
    """The `points` segment of a point shard, row by row."""
    table = _read(data, segment)
    return [PointRow._make(row) for row in _rows(table, list(PointRow._fields))]


def read_areas(data: bytes, segment: tuple[int, int]) -> list[AreaRow]:
    """The `areas` segment of a point shard, row by row."""
    table = _read(data, segment)
    return [AreaRow._make(row) for row in _rows(table, list(AreaRow._fields))]


def read_titles(data: bytes) -> list[TitleRow]:
    """A title shard, row by row. `kind` and `code` are None in a cell shard."""
    table = _read(data)
    names = list(TitleRow._fields)
    country = "kind" in table.schema.names
    rows = _rows(table, names if country else names[:-2])
    return [TitleRow._make(row if country else [*row, None, None]) for row in rows]
