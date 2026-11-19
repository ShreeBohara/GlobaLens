"""Sum zipped GKG/events/mentions bytes per year from GDELT master file lists.

Usage: python3 -I backfill_size.py <masterfilelist.txt> <masterfilelist-translation.txt>
           <sample gkg zips...>

Research script, moved here from `docs/3.0/research/scripts/` in P1 task 9.
"""

import os
import re
import sys
import zipfile
from collections import defaultdict

Sums = defaultdict[tuple[str, str], defaultdict[str, int]]


def _by_kind() -> defaultdict[str, int]:
    return defaultdict(int)


def sums(path: str) -> Sums:
    out: Sums = defaultdict(_by_kind)
    pat = re.compile(r"/(\d{4})(\d{2})\d{8}\.(?:translation\.)?(gkg|export|mentions)\.", re.I)
    with open(path, errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) != 3 or not parts[0].isdigit():
                continue
            m = pat.search(parts[2])
            if not m:
                continue
            y, mo, kind = m.group(1), m.group(2), m.group(3).lower()
            out[(y, mo)][kind] += int(parts[0])
    return out


def window(
    sources: tuple[Sums, Sums], start: tuple[str, str], end: tuple[str, str]
) -> defaultdict[str, int]:
    tot: defaultdict[str, int] = defaultdict(int)
    for src in sources:
        for (y, mo), d in src.items():
            if start <= (y, mo) <= end:
                for k, v in d.items():
                    tot[k] += v
    return tot


def main(argv: list[str]) -> None:
    en, tr = sums(argv[1]), sums(argv[2])
    # compression ratio and bytes/row from samples
    zbytes = rbytes = rows = 0
    for p in argv[3:]:
        zbytes += os.path.getsize(p)
        with zipfile.ZipFile(p) as z:
            d = z.read(z.namelist()[0])
        rbytes += len(d)
        rows += d.count(b"\n")
    ratio, bpr = rbytes / zbytes, rbytes / rows
    print(
        f"sample: zip->raw ratio {ratio:.2f}x, {bpr:,.0f} raw bytes/row, "
        f"{zbytes / rows:,.0f} zipped bytes/row"
    )
    for label, s, e in [
        ("10y 2016-11..2026-10", ("2016", "11"), ("2026", "10")),
        ("2y 2024-11..2026-10", ("2024", "11"), ("2026", "10")),
        ("last 12 mo", ("2025", "11"), ("2026", "10")),
    ]:
        t = window((en, tr), s, e)
        g = t["gkg"]
        est_rows = g / (zbytes / rows)
        print(
            f"{label}: GKG zipped {g / 1e12:.2f} TB (~{g * ratio / 1e12:.1f} TB raw), "
            f"est {est_rows / 1e9:.2f} B rows; events {t['export'] / 1e9:.0f} GB, "
            f"mentions {t['mentions'] / 1e9:.0f} GB zipped"
        )
    for y in range(2016, 2027):
        ys = str(y)
        g_en = sum(d["gkg"] for (yy, _mo), d in en.items() if yy == ys)
        g_tr = sum(d["gkg"] for (yy, _mo), d in tr.items() if yy == ys)
        print(f"  {y}: EN GKG {g_en / 1e9:6.0f} GB  TR GKG {g_tr / 1e9:6.0f} GB zipped")


if __name__ == "__main__":
    main(sys.argv)
