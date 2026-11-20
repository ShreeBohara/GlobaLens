"""The data plane's JSON objects: `now.json`, the pass manifest, the hourly manifest and the
per-hour title index (docs/design/p1.md §6.1 and §6.2).

A client that starts cold reads `now.json`, the pass manifest it names, and the hourly manifest
that one names; then the point shards. That is two manifests, never a chain.

- **`now.json`** (`cdn/now.json`, the only object that changes in place): the pass number
  `seq`, when it was written, the pass manifest, and for each stream the newest published
  stamp and when GDELT listed it. The browser ignores a `seq` at or below one it has seen.
- **The pass manifest**: one per pass. `open` lists every published unit in the window that
  the hourly manifest does not cover, each with its point shard (and the shard's two segments
  as `[offset, length]`) and its title shards by H3 base cell. A unit is one stamp and the
  streams published together; a late stream is a unit of its own. `hour` names the hourly
  manifest.
- **The hourly manifest**: one per hourly cut. For each closed hour in the 24-hour window, the
  hour's point compaction, the stamps of each stream it holds, and its title index.
- **The title index** of an hour: the hour's title compactions by cell and its country-level
  title compaction. It is a separate object so that the cold path carries only points: the Lens
  fetches an hour's index the first time it needs that hour's titles. (§6.2 names this as the
  fallback if the per-cell lists made the hourly manifest too large; with 24 hours of up to 60
  cells, they would have, so P1 starts with it.)

Every object key in these files is relative to the data plane's base, which is the `cdn`
bucket: `live/dt=…/shards/{hash}.arrow` is stored at `cdn/live/dt=…/shards/{hash}.arrow`.
The JSON has sorted keys and no spaces, so the same content gives the same bytes.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from gdelt import Stream

__all__ = [
    "VERSION",
    "Hour",
    "HourManifest",
    "Now",
    "PassManifest",
    "Points",
    "Ref",
    "StreamClock",
    "TitleIndex",
    "Unit",
    "dump",
    "read_hour_manifest",
    "read_now",
    "read_pass_manifest",
    "read_title_index",
    "time_text",
    "title_index_bytes",
]

VERSION = 1


def time_text(time: datetime) -> str:
    """A UTC time as the files write it: `2026-11-14T14:00:00Z`."""
    if time.utcoffset() is None:
        raise ValueError(f"a time without a zone: {time!r}")
    return time.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _time(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def dump(value: Mapping[str, Any]) -> bytes:
    """JSON with sorted keys and no spaces, in UTF-8."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True, slots=True)
class Ref:
    """An object a manifest names: its key, its size, and its rows (0 where rows mean
    nothing, as for a title index)."""

    key: str
    bytes: int
    rows: int

    def json(self) -> dict[str, Any]:
        return {"key": self.key, "bytes": self.bytes, "rows": self.rows}

    @staticmethod
    def parse(value: Mapping[str, Any]) -> "Ref":
        return Ref(key=value["key"], bytes=value["bytes"], rows=value["rows"])


@dataclass(frozen=True, slots=True)
class Points:
    """A point shard: the object, and its two segments as (offset, length)."""

    ref: Ref  # rows: the point rows
    points: tuple[int, int]
    areas: tuple[int, int]

    def json(self) -> dict[str, Any]:
        return {
            **self.ref.json(),
            "segments": {"points": list(self.points), "areas": list(self.areas)},
        }

    @staticmethod
    def parse(value: Mapping[str, Any]) -> "Points":
        segments = value["segments"]
        points_start, points_length = segments["points"]
        areas_start, areas_length = segments["areas"]
        return Points(
            ref=Ref.parse(value),
            points=(points_start, points_length),
            areas=(areas_start, areas_length),
        )


@dataclass(frozen=True, slots=True)
class TitleIndex:
    """Title shards by H3 base cell (cells that share an object name the same one), and the
    country-level title shard."""

    cells: Mapping[int, Ref]
    country: Ref | None

    def json(self) -> dict[str, Any]:
        return {
            "cells": {str(cell): ref.json() for cell, ref in self.cells.items()},
            "country": None if self.country is None else self.country.json(),
        }

    @staticmethod
    def parse(value: Mapping[str, Any]) -> "TitleIndex":
        country = value["country"]
        return TitleIndex(
            cells={int(cell): Ref.parse(ref) for cell, ref in value["cells"].items()},
            country=None if country is None else Ref.parse(country),
        )


@dataclass(frozen=True, slots=True)
class Unit:
    """An open entry of the pass manifest: one stamp, the streams published together."""

    stamp: datetime
    streams: tuple[Stream, ...]
    points: Points
    titles: TitleIndex

    def json(self) -> dict[str, Any]:
        return {
            "stamp": time_text(self.stamp),
            "streams": [stream.value for stream in self.streams],
            "points": self.points.json(),
            "titles": self.titles.json(),
        }

    @staticmethod
    def parse(value: Mapping[str, Any]) -> "Unit":
        return Unit(
            stamp=_time(value["stamp"]),
            streams=tuple(Stream(stream) for stream in value["streams"]),
            points=Points.parse(value["points"]),
            titles=TitleIndex.parse(value["titles"]),
        )


@dataclass(frozen=True, slots=True)
class Hour:
    """A closed hour of the hourly manifest: its compaction and the stamps it holds."""

    hour: datetime
    stamps: Mapping[Stream, Sequence[datetime]]
    points: Points
    titles: Ref  # the hour's title index (rows: 0)

    def json(self) -> dict[str, Any]:
        return {
            "hour": time_text(self.hour),
            "stamps": {
                stream.value: [time_text(stamp) for stamp in stamps]
                for stream, stamps in self.stamps.items()
            },
            "points": self.points.json(),
            "titles": self.titles.json(),
        }

    @staticmethod
    def parse(value: Mapping[str, Any]) -> "Hour":
        return Hour(
            hour=_time(value["hour"]),
            stamps={
                Stream(stream): tuple(_time(stamp) for stamp in stamps)
                for stream, stamps in value["stamps"].items()
            },
            points=Points.parse(value["points"]),
            titles=Ref.parse(value["titles"]),
        )


@dataclass(frozen=True, slots=True)
class HourManifest:
    cut: datetime  # the hourly cut it was made at
    hours: Sequence[Hour]

    def bytes(self) -> bytes:
        return dump(
            {"v": VERSION, "cut": time_text(self.cut), "hours": [h.json() for h in self.hours]}
        )


@dataclass(frozen=True, slots=True)
class PassManifest:
    seq: int
    written_at: datetime
    hour: str | None  # the hourly manifest's key, if there is one
    open: Sequence[Unit]

    def bytes(self) -> bytes:
        return dump(
            {
                "v": VERSION,
                "seq": self.seq,
                "written_at": time_text(self.written_at),
                "hour": self.hour,
                "open": [unit.json() for unit in self.open],
            }
        )


@dataclass(frozen=True, slots=True)
class StreamClock:
    """A stream's newest published stamp, and when GDELT listed its file."""

    stamp: datetime
    listed_at: datetime


@dataclass(frozen=True, slots=True)
class Now:
    seq: int
    written_at: datetime
    manifest: str
    streams: Mapping[Stream, StreamClock | None]

    def bytes(self) -> bytes:
        return dump(
            {
                "v": VERSION,
                "seq": self.seq,
                "written_at": time_text(self.written_at),
                "manifest": self.manifest,
                "streams": {
                    stream.value: None
                    if clock is None
                    else {"stamp": time_text(clock.stamp), "listed_at": time_text(clock.listed_at)}
                    for stream, clock in self.streams.items()
                },
            }
        )


def title_index_bytes(hour: datetime, index: TitleIndex) -> bytes:
    """An hour's title index as stored."""
    return dump({"v": VERSION, "hour": time_text(hour), **index.json()})


def _load(data: bytes) -> dict[str, Any]:
    value = json.loads(data)
    if not isinstance(value, dict) or value.get("v") != VERSION:  # pyright: ignore[reportUnknownMemberType]
        raise ValueError(f"not a version {VERSION} data-plane file")
    loaded: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
    return loaded


def read_now(data: bytes) -> Now:
    value = _load(data)
    streams: dict[Stream, StreamClock | None] = {}
    for stream, clock in value["streams"].items():
        streams[Stream(stream)] = (
            None if clock is None else StreamClock(_time(clock["stamp"]), _time(clock["listed_at"]))
        )
    return Now(
        seq=value["seq"],
        written_at=_time(value["written_at"]),
        manifest=value["manifest"],
        streams=streams,
    )


def read_pass_manifest(data: bytes) -> PassManifest:
    value = _load(data)
    return PassManifest(
        seq=value["seq"],
        written_at=_time(value["written_at"]),
        hour=value["hour"],
        open=tuple(Unit.parse(unit) for unit in value["open"]),
    )


def read_hour_manifest(data: bytes) -> HourManifest:
    value = _load(data)
    return HourManifest(cut=_time(value["cut"]), hours=tuple(Hour.parse(h) for h in value["hours"]))


def read_title_index(data: bytes) -> tuple[datetime, TitleIndex]:
    value = _load(data)
    return _time(value["hour"]), TitleIndex.parse(value)
