"""Analyze GDELT 2.0 masterfilelist(s): volume trends and missing 15-minute intervals.

Usage: python3 -I analyze_masterlist.py <masterfilelist.txt> <label>
Lines look like: "<size> <md5> http://data.gdeltproject.org/gdeltv2/<YYYYMMDDHHMMSS>.<type>.CSV.zip"
"""
import sys
import re
from collections import defaultdict
from datetime import datetime, timedelta

path, label = sys.argv[1], sys.argv[2]
pat = re.compile(r"^(\d+)\s+(\S+)\s+\S*/(\d{14})\.(?:translation\.)?(export|mentions|gkg)\.(?:CSV|csv)\.zip\s*$")

sizes = defaultdict(dict)  # type -> {ts: size}
bad = 0
for line in open(path, "r", errors="replace"):
    m = pat.match(line.strip())
    if not m:
        bad += 1
        continue
    size, _md5, ts, typ = m.groups()
    sizes[typ][ts] = int(size)

print(f"== {label}: unparsed lines={bad}")
for typ in ("export", "mentions", "gkg"):
    d = sizes[typ]
    keys = sorted(d)
    print(f"{typ}: files={len(keys)} first={keys[0]} last={keys[-1]}")

# Yearly / recent monthly avg daily zipped MB and avg file size, per type
def ym(ts):
    return ts[:6]

def yr(ts):
    return ts[:4]

print("\n-- Avg zipped MB per FULL day (sum of 96 files) by year (computed as mean file size * 96) --")
for typ in ("export", "mentions", "gkg"):
    agg = defaultdict(list)
    for ts, s in sizes[typ].items():
        agg[yr(ts)].append(s)
    row = []
    for y in sorted(agg):
        v = agg[y]
        row.append(f"{y}:{(sum(v)/len(v))*96/1e6:.1f}")
    print(f"{typ}: " + "  ".join(row))

print("\n-- Monthly (2024-01..now) avg zipped MB/day --")
months = sorted({ym(ts) for ts in sizes["gkg"] if ts >= "202401"})
print("month   export  mentions  gkg   (files: export/mentions/gkg)")
for mo in months:
    vals = []
    cnts = []
    for typ in ("export", "mentions", "gkg"):
        v = [s for ts, s in sizes[typ].items() if ts.startswith(mo)]
        vals.append((sum(v) / len(v)) * 96 / 1e6 if v else 0)
        cnts.append(len(v))
    print(f"{mo}  {vals[0]:6.2f}  {vals[1]:7.2f}  {vals[2]:7.1f}   ({cnts[0]}/{cnts[1]}/{cnts[2]})")

# Missing intervals since 2024-01-01 for each type
print("\n-- Missing 15-min intervals (expected grid) --")
def grid(start, end):
    t = start
    while t <= end:
        yield t.strftime("%Y%m%d%H%M%S")
        t += timedelta(minutes=15)

for since in ("20240101000000", "20250101000000", "20260101000000"):
    last = max(sizes["export"])
    start = datetime.strptime(since, "%Y%m%d%H%M%S")
    end = datetime.strptime(last, "%Y%m%d%H%M%S")
    expected = list(grid(start, end))
    for typ in ("export", "mentions", "gkg"):
        present = sizes[typ]
        missing = [t for t in expected if t not in present]
        print(f"since {since[:8]} {typ}: expected={len(expected)} missing={len(missing)} ({100*len(missing)/len(expected):.2f}%)")

# Longest gaps (consecutive missing) since 2024 for export
def gaps(typ, since):
    start = datetime.strptime(since, "%Y%m%d%H%M%S")
    end = datetime.strptime(max(sizes[typ]), "%Y%m%d%H%M%S")
    present = sizes[typ]
    out = []
    run_start = None
    run_len = 0
    for t in grid(start, end):
        if t not in present:
            if run_start is None:
                run_start = t
                run_len = 0
            run_len += 1
        else:
            if run_start is not None:
                out.append((run_len, run_start))
                run_start = None
    if run_start is not None:
        out.append((run_len, run_start))
    return out

for typ in ("export", "gkg"):
    g = gaps(typ, "20240101000000")
    g_sorted = sorted(g, reverse=True)[:15]
    print(f"\nTop gaps since 2024 for {typ} (count of consecutive missing 15-min files, start):")
    for n, s in g_sorted:
        print(f"  {n:5d} intervals (~{n*15/60:.1f} h) starting {s}")
    # Monthly count of missing intervals
    bymo = defaultdict(int)
    for n, s in g:
        bymo[s[:6]] += n
    print("  missing intervals by month:", dict(sorted(bymo.items())))

# Small/near-empty files (possible degraded output) since 2025
print("\n-- Suspiciously small files since 2025 (below 20% of that month's median) --")
import statistics
for typ in ("export", "gkg"):
    bymo = defaultdict(list)
    for ts, s in sizes[typ].items():
        if ts >= "20250101":
            bymo[ts[:6]].append((ts, s))
    total_small = 0
    examples = []
    for mo, lst in sorted(bymo.items()):
        med = statistics.median([s for _, s in lst])
        small = [(ts, s) for ts, s in lst if s < 0.2 * med]
        total_small += len(small)
        examples += small[:2]
    print(f"{typ}: small files={total_small}; examples={examples[:8]}")
