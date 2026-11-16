"""Parse throughput of `packages/gdelt` on one core.

    mise run bench:parse                          # synthetic rows: proves the wiring, not a result
    mise run bench:parse -- PATH [PATH ...]       # real GKG files (.csv, .csv.zip) or folders
    mise run bench:parse -- --ledger metrics/ledger.jsonl PATH ...

What is timed: `gdelt.parse_gkg` over the unzipped bytes of every file, in one process and one
thread, files already in memory. That is the whole path from bytes to lean rows: the 27-column
contract, entity decoding, the sanitizer, NFKC, the title hash, URL canonicalization, every
location and the primary-location rule. Unzipping is timed separately and is not part of the
rate.

Two rates are printed. `rows_per_second` divides by wall-clock time and is the plan's figure
(target: at least 10,000 rows a second on one core). `rows_per_cpu_second` divides by the CPU
time the process used, which stays steadier when other work shares the machine. The load
average before and after the run is recorded so a reader can judge the conditions.

Real GKG files are public and free but never committed: keep them outside the repository.
"""

import argparse
import gc
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gdelt import ParseStats, find_gkg_files, parse_gkg, read_gkg_bytes

TARGET_ROWS_PER_SECOND = 10_000
METRIC = "gkg_parse_rows_per_second_per_core"


def synthetic_file(rows: int) -> bytes:
    """Rows about as wide as real ones (a GCAM column of several kilobytes, a few dozen theme
    mentions, several location mentions, a title of hex references) with invented content.
    Good for checking that the benchmark runs; not a substitute for real files."""
    themes = ";".join(f"TAX_FNCACT_ROLE_{i % 23},{40 + i * 37}" for i in range(40)) + ";"
    locations = ";".join(
        [
            "1#France#FR#FR##46#2#FR#12",
            "4#Lyon, Rhone-Alpes, France#FR#FRB9#69#45.75#4.85#-1445171#58",
            "4#Paris, Ile-De-France, France#FR#FRA8#75#48.8667#2.33333#-1456928#640",
            "1#United States#US#US##39.828175#-98.5795#US#410",
            "3#Austin, Texas, United States#US#USTX#TX453#30.2672#-97.7431#1384879#977",
            "2#Texas, United States#US#USTX##31.106#-97.6475#TX#1120",
            "5#Bayern, Germany#GM#GM02##49#11.5#-1746443#1200",
            "1#Germany#GM#GM##51#9#GM#1320",
        ]
    )
    gcam = "wc:186," + ",".join(f"c{i % 40}.{i % 9}:{i % 7}" for i in range(1100))
    title = "".join(f"&#x{0x4E00 + (i * 97) % 2000:X};" for i in range(22))
    lines: list[bytes] = []
    for i in range(rows):
        translated = i % 3 != 0
        columns = [
            f"20260301120000-{'T' if translated else ''}{i}",
            "20260301120000",
            "1",
            f"outlet-{i % 500}.example",
            f"https://www.outlet-{i % 500}.example/world/2026/03/synthetic-story-{i}",
            "",
            "",
            "TAX_FNCACT;EPU_POLICY",
            themes,
            "1#France#FR#FR#46#2#FR",
            locations,
            "jane example",
            "Jane Example,45",
            "example river authority",
            "Example River Authority,120",
            "-2.41545893719807,1.93236714975845,4.34782608695652,6.28019323671498,21.25,0.48,186",
            "",
            gcam,
            f"https://img.outlet-{i % 500}.example/photo-{i}.jpg",
            "",
            "",
            "",
            "",
            "Jane Example,45;Example River Authority,120",
            "3,days of rain,96;",
            "srclc:zho;eng:GT-ZHO 1.0" if translated else "",
            "<PAGE_LINKS>https://www.outlet.example/a;https://www.outlet.example/b</PAGE_LINKS>"
            "<PAGE_PRECISEPUBTIMESTAMP>20260301113000</PAGE_PRECISEPUBTIMESTAMP>"
            + (
                f"<PAGE_TITLE>{title} {i}</PAGE_TITLE>"
                if translated
                else f"<PAGE_TITLE>Synthetic headline number {i} about the river</PAGE_TITLE>"
            ),
        ]
        lines.append("\t".join(columns).encode())
    return b"\n".join(lines) + b"\n"


def host() -> dict[str, Any]:
    chip = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        probe = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=False,
        )
        chip = probe.stdout.strip() or chip
    return {
        "chip": chip,
        "machine": platform.machine(),
        "system": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


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


def dataset_version(files: list[Path]) -> str:
    """Names and sizes of the input files, hashed: enough to tell two inputs apart."""
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.name):
        digest.update(f"{path.name}\t{path.stat().st_size}\n".encode())
    names = sorted(path.name for path in files)
    return f"gkg:{names[0][:8]}-{names[-1][:8]}:{len(files)}files:sha256:{digest.hexdigest()[:16]}"


def measure(blobs: list[bytes], repeats: int) -> tuple[list[float], list[float], ParseStats]:
    """Parse every blob `repeats` times. Returns wall seconds and CPU seconds per repeat, and
    the counts of one pass."""
    wall: list[float] = []
    cpu: list[float] = []
    stats = ParseStats()
    for repeat in range(repeats):
        gc.collect()
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        results = [parse_gkg(blob) for blob in blobs]
        cpu.append(time.process_time() - cpu_start)
        wall.append(time.perf_counter() - wall_start)
        if repeat == 0:
            for result in results:
                stats.add(result.stats)
        del results
    return wall, cpu, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse throughput of packages/gdelt on one core.")
    parser.add_argument("paths", nargs="*", type=Path, help="GKG files or folders of them")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--limit-files", type=int, default=0, help="use only the first N files")
    parser.add_argument("--synthetic-rows", type=int, default=20_000)
    parser.add_argument("--ledger", type=Path, help="append the result to this ledger file")
    parser.add_argument("--enforce", action="store_true", help="exit 1 below the target")
    args = parser.parse_args(argv)

    files: list[Path] = sorted(find_gkg_files(args.paths), key=lambda p: p.name)
    if args.limit_files:
        files = files[: args.limit_files]
    load_before = os.getloadavg()
    unzip_start = time.perf_counter()
    if files:
        blobs = [read_gkg_bytes(path) for path in files]
        source = "production"
        dataset = dataset_version(files)
    else:
        blobs = [synthetic_file(args.synthetic_rows)]
        source = "synthetic"
        dataset = f"synthetic:{args.synthetic_rows}rows"
    read_seconds = time.perf_counter() - unzip_start

    wall, cpu, stats = measure(blobs, args.repeats)
    load_after = os.getloadavg()
    megabytes = sum(len(blob) for blob in blobs) / 1e6
    rates = sorted(stats.rows / seconds for seconds in wall)
    cpu_rates = sorted(stats.rows / seconds for seconds in cpu)
    median = statistics.median(rates)
    result: dict[str, Any] = {
        "bench": "parse",
        "source": source,
        "dataset_version": dataset,
        "files": len(blobs),
        "megabytes": round(megabytes, 1),
        "rows": stats.rows,
        "quarantined": sum(stats.quarantined.values()),
        "blank_lines": stats.blank_lines,
        "repeats": args.repeats,
        "rows_per_second": {
            "median": round(median),
            "min": round(rates[0]),
            "max": round(rates[-1]),
        },
        "rows_per_cpu_second": {
            "median": round(statistics.median(cpu_rates)),
            "min": round(cpu_rates[0]),
            "max": round(cpu_rates[-1]),
        },
        "megabytes_per_second": round(megabytes / statistics.median(wall), 1),
        "read_and_unzip_seconds": round(read_seconds, 2),
        "target_rows_per_second": TARGET_ROWS_PER_SECOND,
        "meets_target": median >= TARGET_ROWS_PER_SECOND,
        "load_average_before": [round(x, 2) for x in load_before],
        "load_average_after": [round(x, 2) for x in load_after],
        "host": host(),
        "commit": git_commit(),
    }
    print(json.dumps(result, indent=2))

    if args.ledger is not None:
        entry = {
            "metric": METRIC,
            "value": round(median),
            "ci": None,
            "unit": "rows/s",
            "commit": result["commit"],
            "dataset_version": dataset,
            "script": "bench/parse_bench.py",
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "label": "measured",
            "source": source,
            "detail": {
                key: result[key]
                for key in (
                    "rows",
                    "files",
                    "repeats",
                    "rows_per_second",
                    "rows_per_cpu_second",
                    "load_average_before",
                    "load_average_after",
                    "host",
                )
            },
        }
        with args.ledger.open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return 1 if args.enforce and not result["meets_target"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
