"""The data plane's bytes and R2 writes, measured against the Phase 1 budgets.

    mise run bench:data-plane -- measure STORE --dsn DSN [--write-log FILE] --dataset NAME
    mise run bench:data-plane -- replay FIXTURES DAY STORE --dsn DSN
    ... --ledger metrics/ledger.jsonl     to append the results as ledger entries

`measure` reads a data plane that the publisher wrote into a folder store, and the database it
published from. `replay` makes one first: it takes one day of the fixture week through the
tier-1 walk and the publisher on a simulated clock, then measures it. The simulation lists each
file 9 minutes before its stamp, loads it at once, and runs a pass every 5 minutes; the clock
is passed to the ledger the way its tests pass it. The replay needs an empty database of its own,
migrated, and a store folder that does not exist yet.

What is measured (docs/design/p1.md §6.5, §6.6, §10 "Bytes", §11):

- **Cold start**: `now.json`, the pass manifest, the hourly manifest and every point shard they
  name, which is what a client reads before it can draw. Also the same newest first, cut at the
  render budgets (100,000 points on a phone, 300,000 on a desktop), against the 1.5 MB
  first-load budget on mobile. And what the hourly manifest would weigh with the per-cell title
  lists inline instead of in per-hour title indexes.
- **Per update**: what a client that is already running fetches after a pass: `now.json`, the
  pass manifest, the new point shards, and the hourly manifest when it changed. Budget 150 KB.
- **Title shards**: the size of every title object, by class.
- **Compression**: every point and title object as written (each buffer zstd-compressed, §6.5's
  path), against the same table written uncompressed, and against the uncompressed bytes
  zstd-compressed whole, which stands in for an edge compressor. The Compression Rule itself
  needs a domain and is not measured.
- **Writes**: R2 Class A operations per interval (tier 1's raw zips and lake files from the
  write log, the publisher's PUTs from `ingest.publish_pass`), against the plan's ceilings of 72
  per interval and 65 per hour, and the month at that rate. An interval is one stamp: when its
  two streams are published in different passes, the writes of both count against it.

Every number is a local-store measurement: the size of each object as stored in a folder, with
no HTTP, no edge and no cache. Measurements on the `r2.dev` address wait for R2. Nothing printed
or written here holds a title: only sizes, counts, keys and stamps.
"""

# pyarrow ships no type information, so its calls are unknown to pyright.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import pyarrow as pa
from gdelt import Stream
from worker import dataplane, manifest, shards, stamps
from worker.db import connect
from worker.feed import FetchError
from worker.ledger import fence, publish, tier1
from worker.ledger.fence import Listing
from worker.store import FolderStore, LoggingStore

SCRIPT = "bench/data_plane.py"
FIRST_LOAD_BUDGET = 1_500_000  # bytes of data on mobile (plan §10 Phase 1, definition of done)
UPDATE_BUDGET = 150_000  # bytes per update
RENDER_BUDGETS = {"mobile": 100_000, "desktop": 300_000}  # points (plan §9, design note §15)
WRITES_PER_INTERVAL = 72  # the plan's ceiling (§7, R2 budgets)
WRITES_PER_HOUR = 65
INTERVALS_A_MONTH = 2_976
HOURS_A_MONTH = 744
PLAN_MONTH = {"per interval": 214_000, "hourly": 48_000}  # the plan's two lines, writes a month
TIER1_PREFIXES = ("raw/", "lake/")
UPDATE_KINDS = ("points", "manifest", "now", "hour-manifest")
STORE_NOTE = (
    "local folder store: object sizes as stored, no HTTP overhead, no edge, no cache; "
    "r2.dev measurements wait for R2"
)


# --- Reading what was written ----------------------------------------------------------------


def percentile(values: Sequence[float], share: float) -> float:
    """The nearest-rank percentile: the smallest value with at least `share` of them at or
    below it."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def spread(values: Sequence[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "p50": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
        "max": max(values, default=0),
    }


def cold_start(store: FolderStore) -> dict[str, Any]:
    cold = dataplane.cold_start(store.get)
    fixed = cold.sizes["now"] + cold.sizes["manifest"] + cold.sizes["hourly"]
    points = sum(ref.ref.bytes for _, ref in cold.points)
    budgets: dict[str, dict[str, Any]] = {}
    for device, cap in RENDER_BUDGETS.items():
        size, rows, oldest = fixed, 0, None
        for when, ref in cold.points:  # newest first
            if rows >= cap:
                break
            size += ref.ref.bytes
            rows += ref.ref.rows
            oldest = when
        budgets[device] = {
            "bytes": size,
            "points": rows,
            "oldest": None if oldest is None else manifest.time_text(oldest),
        }
    indexes = 0
    if cold.hourly is not None:
        for hour in cold.hourly.hours:
            indexes += hour.titles.bytes
    # Rows whose record ID GDELT gave to an earlier row of the same file (the repeat bit).
    repeats = 0
    for _, ref in cold.points:
        data = store.get("cdn/" + ref.ref.key)
        assert data is not None
        repeats += sum(
            1 for row in shards.read_points(data, ref.points) if shards.is_repeat(row.key)
        )
    newest = cold.points[0][0] if cold.points else None
    oldest_all = cold.points[-1][0] if cold.points else None
    return {
        "bytes": fixed + points,
        "now": cold.sizes["now"],
        "pass_manifest": cold.sizes["manifest"],
        "hourly_manifest": cold.sizes["hourly"],
        "point_bytes": points,
        "point_objects": len(cold.points),
        "point_rows": sum(ref.ref.rows for _, ref in cold.points),
        "closed_hours": 0 if cold.hourly is None else len(cold.hourly.hours),
        "open_units": len(cold.manifest.open),
        "intervals": len(cold.intervals),
        "newest": None if newest is None else manifest.time_text(newest),
        "oldest": None if oldest_all is None else manifest.time_text(oldest_all),
        "by_render_budget": budgets,
        "hourly_manifest_with_inline_titles_about": cold.sizes["hourly"] + indexes,
        "point_rows_with_the_repeat_bit": repeats,
    }


@dataclass(frozen=True)
class Stored:
    key: str
    size: int
    schema: str  # the first stream's schema name, or "json"
    folder: str  # shards, titles, hour, manifest


def stored_objects(root: Path) -> list[Stored]:
    found: list[Stored] = []
    live = root / "cdn" / "live"
    if not live.exists():
        return found
    for path in sorted(live.rglob("*")):
        if not path.is_file() or path.name.startswith(".put-"):
            continue
        key = path.relative_to(root).as_posix()
        folder = path.parent.name
        if path.suffix == ".json":
            found.append(Stored(key, path.stat().st_size, "json", folder))
            continue
        schema = shards.schema_metadata(path.read_bytes())["gl.schema"]
        found.append(Stored(key, path.stat().st_size, schema, folder))
    return found


def title_shards(objects: Iterable[Stored]) -> dict[str, dict[str, float]]:
    classes: dict[str, list[float]] = {}
    for item in objects:
        if item.schema in ("titles/1", "country-titles/1"):
            where = "interval" if item.folder == "titles" else "hour"
            kind = "cell" if item.schema == "titles/1" else "country"
            classes.setdefault(f"{where} {kind}", []).append(item.size)
    return {name: spread(sizes) for name, sizes in sorted(classes.items())}


def _uncompressed(data: bytes) -> bytes:
    table = pa.ipc.open_stream(pa.py_buffer(data)).read_all()
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def compression(store: FolderStore) -> dict[str, dict[str, int | float]]:
    """Every object the cold start reaches, and the title objects its manifests name."""
    cold = dataplane.cold_start(store.get)
    whole = pa.Codec("zstd", compression_level=shards.ZSTD_LEVEL)
    segments: list[tuple[str, bytes]] = []

    def take(kind: str, key: str, ranges: Sequence[tuple[int, int]] | None = None) -> None:
        data = store.get("cdn/" + key)
        assert data is not None
        if ranges is None:
            segments.append((kind, data))
        else:
            segments.extend((kind, data[start : start + length]) for start, length in ranges)

    seen: set[str] = set()
    for _, ref in cold.points:
        take("points", ref.ref.key, [ref.points, ref.areas])
    title_refs: list[manifest.Ref] = []
    for unit in cold.manifest.open:
        title_refs += list(unit.titles.cells.values())
        if unit.titles.country is not None:
            title_refs.append(unit.titles.country)
    if cold.hourly is not None:
        for hour in cold.hourly.hours:
            data = store.get("cdn/" + hour.titles.key)
            assert data is not None
            _, index = manifest.read_title_index(data)
            title_refs += list(index.cells.values())
            if index.country is not None:
                title_refs.append(index.country)
    for ref in title_refs:
        if ref.key not in seen:
            seen.add(ref.key)
            take("titles", ref.key)
    totals: dict[str, Counter[str]] = {}
    for kind, data in segments:
        plain = _uncompressed(data)
        count = totals.setdefault(kind, Counter())
        count["streams"] += 1
        count["as_written_zstd_buffers"] += len(data)
        count["uncompressed"] += len(plain)
        count["uncompressed_then_zstd_whole"] += len(whole.compress(plain))
    report: dict[str, dict[str, int | float]] = {}
    for kind, count in totals.items():
        report[kind] = {
            **dict(count),
            "ratio_as_written": round(count["as_written_zstd_buffers"] / count["uncompressed"], 4),
            "ratio_whole": round(count["uncompressed_then_zstd_whole"] / count["uncompressed"], 4),
        }
    return report


def passes(conn: psycopg.Connection[tuple[Any, ...]]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select p.seq, p.objects,
               (select count(*) from ingest.interval i where i.seq = p.seq) as intervals,
               (select coalesce(array_agg(distinct i.stamp), '{}') from ingest.interval i
                 where i.seq = p.seq) as stamps
        from ingest.publish_pass p
        where p.finished_at is not null
        order by p.seq
        """
    ).fetchall()
    found: list[dict[str, Any]] = []
    for seq, objects, intervals, stamps_ in rows:
        puts: dict[str, dict[str, int]] = objects.get("puts", {})
        found.append(
            {
                "seq": seq,
                "intervals": intervals,
                "stamps": sorted(stamps_),
                "hourly": any(kind.startswith("hour-") for kind in puts),
                "writes": sum(kind["n"] for kind in puts.values()),
                "update_bytes": sum(puts[k]["bytes"] for k in UPDATE_KINDS if k in puts),
                "puts": puts,
                "heads": objects.get("heads", 0),
                "skipped": objects.get("skipped", 0),
            }
        )
    return found


def updates(found: Sequence[dict[str, Any]]) -> dict[str, Any]:
    units = [p["update_bytes"] for p in found if p["intervals"]]
    cuts = [p["update_bytes"] for p in found if not p["intervals"]]
    return {
        "passes_with_intervals": spread(units),
        "passes_without_intervals": spread(cuts),
        "budget": UPDATE_BUDGET,
        "passes_over_budget": sum(1 for size in units + cuts if size > UPDATE_BUDGET),
    }


def writes(found: Sequence[dict[str, Any]], write_log: Path | None) -> dict[str, Any]:
    # A stamp whose two streams were published in different passes (one stream was late) is
    # still one interval of time: it is counted once, and its writes from both passes count.
    stamps_published = len({stamp for p in found for stamp in p["stamps"]})
    stamps_split = sum(len(p["stamps"]) for p in found) - stamps_published
    publisher_unit = sum(p["writes"] for p in found if not p["hourly"])
    hourly = [p for p in found if p["hourly"]]
    by_kind: Counter[str] = Counter()
    for p in found:
        for kind, count in p["puts"].items():
            by_kind[kind] += count["n"]
    tier1: Counter[str] = Counter()
    if write_log is not None and write_log.exists():
        for line in write_log.read_text(encoding="utf-8").splitlines():
            key = json.loads(line)["key"]
            if key.startswith(TIER1_PREFIXES):
                tier1[key.split("/", 2)[0] + "/" + key.split("/", 2)[1]] += 1
    tier1_total = sum(tier1.values())
    per_interval = (
        (publisher_unit + tier1_total) / stamps_published if stamps_published else float("nan")
    )
    per_hour = sum(p["writes"] for p in hourly) / len(hourly) if hourly else float("nan")
    unit_passes = [p for p in found if p["intervals"] and not p["hourly"]]
    month = {
        "per interval": round(per_interval * INTERVALS_A_MONTH) if stamps_published else None,
        "hourly": round(per_hour * HOURS_A_MONTH) if hourly else None,
    }
    return {
        "stamps_published": stamps_published,
        "stamps_split": stamps_split,
        "per_interval": round(per_interval, 2),
        "per_interval_ceiling": WRITES_PER_INTERVAL,
        "per_hourly_pass": round(per_hour, 2),
        "per_hour_ceiling": WRITES_PER_HOUR,
        "max_in_one_pass": max((p["writes"] for p in found), default=0),
        "title_objects_per_unit_pass": spread(
            [p["puts"].get("titles", {}).get("n", 0) for p in unit_passes]
        ),
        "publisher_by_kind": dict(sorted(by_kind.items())),
        "tier1_by_prefix": dict(sorted(tier1.items())),
        "heads": sum(p["heads"] for p in found),
        "skipped_existing": sum(p["skipped"] for p in found),
        "month_at_this_rate": month,
        "plan_month": PLAN_MONTH,
        "write_log": write_log is not None and write_log.exists(),
    }


# --- The ledger --------------------------------------------------------------------------------


def git_commit() -> str:
    root = Path(__file__).resolve().parent.parent
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return f"{head or 'unknown'}{'+dirty' if dirty else ''}"


def source_digest() -> str:
    """A hash of the Python sources that wrote the data plane, so a dirty run can be matched to
    a commit later."""
    root = Path(__file__).resolve().parent.parent
    digest = hashlib.sha256()
    for folder in ("apps/worker/src", "packages/gdelt/src", "packages/glcore/src"):
        for path in sorted((root / folder).rglob("*.py")):
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def host() -> dict[str, Any]:
    return {
        "machine": platform.machine(),
        "system": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
    }


def entries(result: dict[str, Any], dataset: str) -> list[dict[str, Any]]:
    """The ledger lines for one measurement."""
    base = {
        "ci": None,
        "commit": git_commit(),
        "dataset_version": dataset,
        "script": SCRIPT,
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "label": "measured",
        "source": "production",
    }
    cold, update, write = result["cold_start"], result["updates"], result["writes"]
    common = {"store": STORE_NOTE, "source_digest": result["source_digest"], "host": host()}
    lines = [
        ("data_plane_cold_start_bytes", cold["bytes"], "bytes", {**common, **cold}),
        (
            "data_plane_cold_start_bytes_mobile",
            cold["by_render_budget"]["mobile"]["bytes"],
            "bytes",
            {**common, "budget": FIRST_LOAD_BUDGET, **cold["by_render_budget"]["mobile"]},
        ),
        (
            "data_plane_update_bytes_p95",
            update["passes_with_intervals"]["p95"],
            "bytes",
            {**common, **update},
        ),
        (
            "data_plane_title_shard_bytes_p95",
            result["title_shards"].get("interval cell", {}).get("p95", 0),
            "bytes",
            {**common, "by_class": result["title_shards"]},
        ),
        (
            "data_plane_zstd_ratio_points",
            result["compression"].get("points", {}).get("ratio_as_written", 0),
            "ratio",
            {**common, "by_kind": result["compression"]},
        ),
        ("r2_writes_per_interval", write["per_interval"], "writes", {**common, **write}),
    ]
    return [
        {"metric": metric, "value": value, "unit": unit, **base, "detail": detail}
        for metric, value, unit, detail in lines
    ]


def measure(
    root: Path, dsn: str, write_log: Path | None, source: str | None = None
) -> dict[str, Any]:
    store = FolderStore(root)
    with connect(dsn) as conn:
        found = passes(conn)
    objects = stored_objects(root)
    return {
        "cold_start": cold_start(store),
        "updates": updates(found),
        "title_shards": title_shards(objects),
        "compression": compression(store),
        "writes": writes(found, write_log),
        "passes": len(found),
        "objects": dict(Counter(f"{o.folder} {o.schema}" for o in objects)),
        "source_digest": source or source_digest(),
    }


# --- The replay ----------------------------------------------------------------------------------

LIST_BEFORE = timedelta(minutes=9)  # GDELT lists a file about ten minutes before its stamp
TICK = timedelta(minutes=5)


class Clock:
    """The replay's simulated time, passed to the ledger the way its tests pass theirs."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def replay(fixtures: Path, day: str, root: Path, dsn: str) -> tuple[Path, str]:
    """Publish one fixture day into `root`. Returns the write log and the dataset's name."""
    files: dict[tuple[Stream, datetime], Path] = {}
    for path in sorted(fixtures.glob(f"{day}*.zip")):
        stream = Stream.TRANSLATED if ".translation." in path.name else Stream.ENGLISH
        files[(stream, stamps.parse_stamp(path.name[:14]))] = path
    if not files:
        raise SystemExit(f"no fixture files for {day} in {fixtures}")
    if root.exists():
        raise SystemExit(f"{root} exists: the replay writes into a new folder")
    root.mkdir(parents=True)
    write_log = root.parent / (root.name + "-writes.jsonl")
    store = LoggingStore(FolderStore(root), write_log)
    by_url = {stamps.file_url(stream, stamp): path for (stream, stamp), path in files.items()}

    def fetch(url: str) -> bytes:
        path = by_url.get(url)
        if path is None:
            raise FetchError("HTTP 404")
        return path.read_bytes()

    digest = hashlib.sha256()
    for path in sorted(files.values(), key=lambda p: p.name):
        digest.update(f"{path.name}\t{path.stat().st_size}\n".encode())
    dataset = f"gkg-week:{day}:{len(files)}files:sha256:{digest.hexdigest()[:16]}"

    with connect(dsn) as conn:
        counted = conn.execute(
            "select (select count(*) from ingest.interval)"
            " + (select count(*) from ingest.publish_pass)"
        ).fetchone()
        if counted is None or counted[0] != 0:
            raise SystemExit(
                "the replay needs an empty ledger: create and migrate a database for it"
            )
        if not publish.lock(conn):
            raise SystemExit("another publisher holds the lock on this database")
        plane = dataplane.DataPlane(dataplane.lake_reader(store.get))
        first = min(stamp for _, stamp in files)
        last = max(stamp for _, stamp in files)
        clock = Clock(first - LIST_BEFORE)
        end = last + timedelta(hours=1, minutes=25)  # past the cut that closes the last hour
        listed: set[tuple[Stream, datetime]] = set()
        while clock.now <= end:
            now = clock.now
            due = [key for key in files if key not in listed and key[1] - LIST_BEFORE <= now]
            listings = []
            for stream, stamp in due:
                data = files[(stream, stamp)].read_bytes()
                md5 = hashlib.md5(data, usedforsecurity=False).hexdigest()
                url = stamps.file_url(stream, stamp)
                listings.append(Listing(stream, stamp, url, len(data), md5))
            fence.enlist(conn, listings, now=now)
            listed.update(due)
            while _walk(conn, store, fetch, clock) is not tier1.Outcome.IDLE:
                pass
            _publish(conn, store, plane, clock)
            clock.now += TICK
    return write_log, dataset


def _walk(
    conn: psycopg.Connection[tuple[Any, ...]],
    store: LoggingStore,
    fetch: Callable[[str], bytes],
    clock: Callable[[], datetime],
) -> tier1.Outcome:
    steps = tier1.walk(conn, store, fetch, clock=clock)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            outcome: tier1.Outcome = done.value
            return outcome


def _publish(
    conn: psycopg.Connection[tuple[Any, ...]],
    store: LoggingStore,
    plane: dataplane.DataPlane,
    clock: Callable[[], datetime],
) -> publish.Result:
    steps = publish.run_pass(conn, store, plane, clock=clock)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            result: publish.Result = done.value
            break
    if result.outcome is publish.Outcome.FENCED:
        raise SystemExit("a replay pass was fenced: is another publisher running?")
    return result


# --- The command line ----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("measure", help="measure a data plane in a folder store")
    one.add_argument("store", type=Path)
    one.add_argument("--dsn", required=True)
    one.add_argument("--write-log", type=Path)
    one.add_argument("--dataset", required=True, help="what the data plane was made from")
    one.add_argument("--source-digest", help="the digest of the code that wrote it, if not this")
    one.add_argument("--ledger", type=Path)
    two = sub.add_parser("replay", help="publish one fixture day, then measure it")
    two.add_argument("fixtures", type=Path)
    two.add_argument("day", help="YYYYMMDD")
    two.add_argument("store", type=Path, help="a folder that does not exist yet")
    two.add_argument("--dsn", required=True)
    two.add_argument("--ledger", type=Path)
    args = parser.parse_args(argv)

    if args.command == "replay":
        write_log, dataset = replay(args.fixtures, args.day, args.store, args.dsn)
        result = measure(args.store, args.dsn, write_log)
    else:
        dataset = args.dataset
        result = measure(args.store, args.dsn, args.write_log, args.source_digest)
    result["dataset_version"] = dataset
    result["commit"] = git_commit()
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.ledger is not None:
        with args.ledger.open("a", encoding="utf-8") as ledger:
            for entry in entries(result, dataset):
                ledger.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
