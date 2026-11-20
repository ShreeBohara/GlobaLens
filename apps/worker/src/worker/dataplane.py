"""What a publishing pass writes, worked out from the ledger (docs/design/p1.md §6, §7.5).

`DataPlane.plan` takes the intervals that are ready to publish, the intervals already published
in the window, and the time, and returns every object the pass must PUT, in an order where each
object names only objects before it, and then `now.json`. Everything follows from those rows:

- **Units.** A unit is one stamp and the streams published with it in one pass. Its point shard
  and title shards are built from the lake files of its intervals.
- **The hourly cut.** Every hour, at CUT_AFTER past the hour, the hours that have ended are
  closed. A closed hour is compacted: its point shard and title shards are built again from the
  lake files of every interval of the hour published before the cut (strictly before: one
  published at the cut's very instant waits for the next cut). Its rows keep their `iv`, so a
  compaction is the hour's interval tables concatenated.
- **The window.** The 24 closed hours before the cut's hour, and everything after them.
- **`open`**, in the pass manifest: the units in the window that no compaction covers: those of
  the hours not closed yet, those published after the cut, and this pass's own.

So the data plane is a function of the ledger, and a publisher that starts again writes the
same keys: every object is stored under the hash of its bytes, and the same rows give the same
bytes. `DataPlane` only remembers what it has built and which keys it has seen written, so that
it does not build or PUT them again.

The time is the database's; each pass passes it in. The pass and its commit are the ledger's
(`worker.ledger.publish`); this module writes nothing.
"""

import hashlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from gdelt import Stream

from worker import shards
from worker.ledger.keys import display_key
from worker.manifest import (
    Hour,
    HourManifest,
    Now,
    PassManifest,
    Points,
    Ref,
    StreamClock,
    TitleIndex,
    Unit,
    read_hour_manifest,
    read_now,
    read_pass_manifest,
    title_index_bytes,
)

__all__ = [
    "CUT_AFTER",
    "HOURLY_TITLE_SHARDS",
    "NOW_KEY",
    "WINDOW",
    "ColdStart",
    "DataPlane",
    "Interval",
    "Plan",
    "Put",
    "cold_start",
    "cut_of",
    "floor_hour",
    "is_content_key",
    "lake_reader",
    "window_start",
]

WINDOW = timedelta(hours=24)
"""How far back the manifests reach: the closed hours before the cut's hour."""

CUT_AFTER = timedelta(minutes=15)
"""How long after the hour the hour before it is closed and compacted. A design value: the
hour's last stamp has had that long to be published."""

NOW_KEY = "cdn/now.json"
"""The one object that is written over: always last in a pass."""

HOURLY_TITLE_SHARDS = 59
"""At most this many cell title objects in an hour's compaction. The plan's ceiling for the
hourly writes is 65 (master plan §7, R2 budgets), and a pass at the cut that compacts one hour
also writes the hour's point compaction, its country-level titles, its title index, the hourly
manifest, its own pass manifest and `now.json`: 59 + 6 = 65. An hour holds the cells of four
intervals, so it can reach the unit limit of 60, which would make 66; past 59 the quietest cells
share one object (the plan's coarsening step 2). A cut that compacts more than one hour (late
data, or the first cut after an outage) writes more: see WALKTHROUGH.md, "Known limits"."""

_HOUR = timedelta(hours=1)
_STREAMS = tuple(Stream)

ReadLake = Callable[[str], tuple[bytes, bytes]]
"""From an interval's `parquet_key` to the bytes of its facts and display files."""


def floor_hour(time: datetime) -> datetime:
    return time.replace(minute=0, second=0, microsecond=0)


def cut_of(now: datetime) -> datetime:
    """The latest hourly cut at or before `now`: a whole hour plus CUT_AFTER."""
    return floor_hour(now - CUT_AFTER) + CUT_AFTER


def window_start(now: datetime) -> datetime:
    """The first stamp of the window: intervals before it are not shown."""
    return floor_hour(cut_of(now)) - WINDOW


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32]


def object_key(folder: str, day: datetime, data: bytes, extension: str) -> str:
    """Where an object is stored: under `cdn/live/`, its day, its folder and its hash."""
    return f"cdn/live/dt={day:%Y-%m-%d}/{folder}/{_digest(data)}.{extension}"


def is_content_key(key: str, data: bytes) -> bool:
    """True when `key` ends in the hash of `data`, as every object but `now.json` must."""
    name = key.rsplit("/", 1)[-1]
    return name.split(".", 1)[0] == _digest(data)


def _public(key: str) -> str:
    """A stored key as the manifests write it: relative to the `cdn` bucket."""
    if not key.startswith("cdn/"):
        raise ValueError(f"not a data-plane key: {key!r}")
    return key.removeprefix("cdn/")


def lake_reader(get: Callable[[str], bytes | None]) -> ReadLake:
    """Reads an interval's two lake files from an object store."""

    def read(parquet_key: str) -> tuple[bytes, bytes]:
        facts = get(parquet_key)
        display = get(display_key(parquet_key))
        if facts is None or display is None:
            raise LookupError(f"the lake files of {parquet_key} are not in the store")
        return facts, display

    return read


@dataclass(frozen=True, slots=True)
class Interval:
    """A ledger row as the publisher sees it. `seq` and `published_at` are set once it is
    published."""

    stream: Stream
    stamp: datetime
    parquet_key: str
    listed_at: datetime
    seq: int | None = None
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Put:
    """One object to write: its key (with the bucket), its bytes, and its class in the write
    log."""

    key: str
    data: bytes
    kind: str


@dataclass(frozen=True, slots=True)
class Plan:
    """What one pass writes."""

    puts: tuple[Put, ...]  # each names only objects before it; the pass manifest is last
    now: bytes  # now.json, written to NOW_KEY after every put
    manifest_key: str  # the pass manifest's key, with the bucket
    named: frozenset[str]  # every key `now.json` reaches, the pass manifest's included
    cut: datetime
    open: tuple[Unit, ...]
    hours: tuple[Hour, ...]


@dataclass(slots=True)
class _Built:
    entry: Unit | Hour
    puts: list[Put]
    keys: frozenset[str]


class DataPlane:
    """Builds the pass plans of one publisher, and remembers what it built."""

    def __init__(self, read_lake: ReadLake) -> None:
        self.read_lake = read_lake
        self._built: dict[tuple[object, ...], _Built] = {}
        self._written: frozenset[str] = frozenset()
        self._last_cut: datetime | None = None

    def due(self, now: datetime, ready: Sequence[Interval], published: Sequence[Interval]) -> bool:
        """True when a pass has something to write: intervals are ready, or a cut has passed
        since the last pass and the window holds something."""
        if ready:
            return True
        start = window_start(now)
        return cut_of(now) != self._last_cut and any(i.stamp >= start for i in published)

    def committed(self, plan: Plan) -> None:
        """The pass that wrote `plan` has committed: everything it names exists."""
        self._written = plan.named
        self._last_cut = plan.cut
        for built in self._built.values():
            if built.keys <= plan.named:
                built.puts = []

    def plan(
        self,
        *,
        seq: int,
        now: datetime,
        ready: Sequence[Interval],
        published: Sequence[Interval],
    ) -> Plan:
        """The objects of pass `seq` at time `now`, and its `now.json`."""
        cut = cut_of(now)
        top = floor_hour(cut)
        start = top - WINDOW

        units: dict[tuple[int, datetime], list[Interval]] = {}
        for interval in published:
            if interval.seq is None or interval.published_at is None:
                raise ValueError(f"{interval.stream} {interval.stamp} is not published")
            if interval.stamp >= start:
                units.setdefault((interval.seq, interval.stamp), []).append(interval)
        compacted: dict[datetime, list[Interval]] = {}
        opened: dict[tuple[datetime, int], list[Interval]] = {}
        for (unit_seq, stamp), group in units.items():
            published_at = group[0].published_at
            assert published_at is not None
            if floor_hour(stamp) < top and published_at < cut:
                compacted.setdefault(floor_hour(stamp), []).extend(group)
            else:
                opened[(stamp, unit_seq)] = group
        for interval in ready:
            if interval.stamp >= start:  # an older one is published with no objects
                opened.setdefault((interval.stamp, seq), []).append(interval)
        # Stamp order, then publishing order: this pass's units carry its own number, as they
        # will in the ledger once it commits, so the next pass lists them in the same place.
        open_groups = [opened[unit] for unit in sorted(opened)]

        used: set[tuple[object, ...]] = set()
        built: list[_Built] = []
        for hour in sorted(compacted):
            built.append(self._hour(hour, compacted[hour], used))
        for group in open_groups:
            built.append(self._unit(group, used))
        for signature in list(self._built):
            if signature not in used:
                del self._built[signature]

        puts: dict[str, Put] = {}
        named: set[str] = set()
        for item in built:
            named |= item.keys
            for put in item.puts:
                if put.key not in self._written:
                    puts.setdefault(put.key, put)
        hours = tuple(item.entry for item in built if isinstance(item.entry, Hour))
        unit_entries = tuple(item.entry for item in built if isinstance(item.entry, Unit))

        hour_key = None
        if hours:
            data = HourManifest(cut=cut, hours=hours).bytes()
            hour_key = object_key("manifest", cut, data, "json")
            named.add(hour_key)
            if hour_key not in self._written:
                puts[hour_key] = Put(hour_key, data, "hour-manifest")
        manifest = PassManifest(
            seq=seq,
            written_at=now,
            hour=None if hour_key is None else _public(hour_key),
            open=unit_entries,
        ).bytes()
        manifest_key = object_key("manifest", now, manifest, "json")
        named.add(manifest_key)
        puts[manifest_key] = Put(manifest_key, manifest, "manifest")

        clocks: dict[Stream, StreamClock | None] = dict.fromkeys(_STREAMS)
        for interval in [*published, *ready]:
            if interval.stamp < start:
                continue
            clock = clocks[interval.stream]
            if clock is None or interval.stamp > clock.stamp:
                clocks[interval.stream] = StreamClock(interval.stamp, interval.listed_at)
        now_json = Now(seq=seq, written_at=now, manifest=_public(manifest_key), streams=clocks)

        return Plan(
            puts=tuple(puts.values()),
            now=now_json.bytes(),
            manifest_key=manifest_key,
            named=frozenset(named),
            cut=cut,
            open=unit_entries,
            hours=hours,
        )

    def _articles(self, intervals: Iterable[Interval]) -> list[shards.Article]:
        articles: list[shards.Article] = []
        for interval in sorted(intervals, key=lambda i: (i.stamp, _STREAMS.index(i.stream))):
            facts, display = self.read_lake(interval.parquet_key)
            articles += shards.read_articles(interval.stream, interval.stamp, facts, display)
        return articles

    def _objects(
        self, articles: list[shards.Article], day: datetime, *, hourly: bool
    ) -> tuple[Points, TitleIndex, list[Put]]:
        prefix = "hour-" if hourly else ""
        point = shards.point_shard(articles)
        points_key = object_key("hour" if hourly else "shards", day, point.data, "arrow")
        puts = [Put(points_key, point.data, prefix + "points")]
        cells: dict[int, Ref] = {}
        limit = HOURLY_TITLE_SHARDS if hourly else shards.MAX_TITLE_SHARDS
        title_cells, country = shards.title_shards(articles, limit=limit)
        for shard in title_cells:
            key = object_key("hour" if hourly else "titles", day, shard.data, "arrow")
            puts.append(Put(key, shard.data, prefix + "titles"))
            for cell in shard.cells:
                cells[cell] = Ref(_public(key), len(shard.data), shard.rows)
        country_ref = None
        if country is not None:
            key = object_key("hour" if hourly else "titles", day, country.data, "arrow")
            puts.append(Put(key, country.data, prefix + "country"))
            country_ref = Ref(_public(key), len(country.data), country.rows)
        points = Points(
            ref=Ref(_public(points_key), len(point.data), point.rows),
            points=point.points,
            areas=point.areas,
        )
        return points, TitleIndex(cells=dict(sorted(cells.items())), country=country_ref), puts

    def _unit(self, group: list[Interval], used: set[tuple[object, ...]]) -> _Built:
        stamp = group[0].stamp
        signature: tuple[object, ...] = (
            "unit",
            stamp,
            frozenset((i.stream, i.parquet_key) for i in group),
        )
        used.add(signature)
        cached = self._built.get(signature)
        if cached is None:
            points, titles, puts = self._objects(self._articles(group), stamp, hourly=False)
            streams = tuple(sorted({i.stream for i in group}, key=_STREAMS.index))
            entry = Unit(stamp=stamp, streams=streams, points=points, titles=titles)
            cached = _Built(entry, puts, frozenset(put.key for put in puts))
            self._built[signature] = cached
        return cached

    def _hour(
        self, hour: datetime, intervals: list[Interval], used: set[tuple[object, ...]]
    ) -> _Built:
        signature: tuple[object, ...] = (
            "hour",
            hour,
            frozenset((i.stream, i.stamp, i.parquet_key) for i in intervals),
        )
        used.add(signature)
        cached = self._built.get(signature)
        if cached is None:
            points, titles, puts = self._objects(self._articles(intervals), hour, hourly=True)
            index = title_index_bytes(hour, titles)
            index_key = object_key("hour", hour, index, "json")
            puts.append(Put(index_key, index, "hour-index"))
            stamps: dict[Stream, tuple[datetime, ...]] = {
                stream: tuple(sorted(i.stamp for i in intervals if i.stream is stream))
                for stream in _STREAMS
            }
            entry = Hour(
                hour=hour,
                stamps=stamps,
                points=points,
                titles=Ref(_public(index_key), len(index), 0),
            )
            cached = _Built(entry, puts, frozenset(put.key for put in puts))
            self._built[signature] = cached
        return cached


# --- What a cold client reads --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ColdStart:
    """What a client that starts cold reads before it can draw: `now.json`, two manifests,
    and every point shard they name, newest first."""

    now: Now
    manifest: PassManifest
    hourly: HourManifest | None
    sizes: Mapping[str, int]  # bytes of now.json and of each manifest
    points: tuple[tuple[datetime, Points], ...]  # (stamp or hour, shard), newest first
    intervals: frozenset[tuple[Stream, datetime]]  # every interval it can reach


def cold_start(get: Callable[[str], bytes | None]) -> ColdStart:
    """Follow `now.json` the way a cold client does. Raises LookupError if anything it names
    is missing."""

    def fetch(key: str) -> bytes:
        data = get(key)
        if data is None:
            raise LookupError(f"{key} is named and missing")
        return data

    now_data = fetch(NOW_KEY)
    now = read_now(now_data)
    manifest_data = fetch("cdn/" + now.manifest)
    manifest = read_pass_manifest(manifest_data)
    sizes = {"now": len(now_data), "manifest": len(manifest_data), "hourly": 0}
    hourly = None
    reached: set[tuple[Stream, datetime]] = set()
    points: list[tuple[datetime, Points]] = []
    if manifest.hour is not None:
        hourly_data = fetch("cdn/" + manifest.hour)
        hourly = read_hour_manifest(hourly_data)
        sizes["hourly"] = len(hourly_data)
        for hour in hourly.hours:
            points.append((hour.hour, hour.points))
            for stream, stamps in hour.stamps.items():
                reached |= {(stream, stamp) for stamp in stamps}
    for unit in manifest.open:
        points.append((unit.stamp, unit.points))
        reached |= {(stream, unit.stamp) for stream in unit.streams}
    points.sort(key=lambda item: item[0], reverse=True)
    return ColdStart(
        now=now,
        manifest=manifest,
        hourly=hourly,
        sizes=sizes,
        points=tuple(points),
        intervals=frozenset(reached),
    )
