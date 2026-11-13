"""Sum zipped GKG/events/mentions bytes per year from GDELT master file lists.
Usage: python3 -I backfill_size.py <masterfilelist.txt> <masterfilelist-translation.txt> <sample gkg zips...>"""
import sys, re, zipfile, os
from collections import defaultdict

def sums(path):
    out = defaultdict(lambda: defaultdict(int))
    pat = re.compile(r"/(\d{4})(\d{2})\d{8}\.(?:translation\.)?(gkg|export|mentions)\.", re.I)
    with open(path, "r", errors="replace") as f:
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

en, tr = sums(sys.argv[1]), sums(sys.argv[2])
# compression ratio and bytes/row from samples
zbytes = rbytes = rows = 0
for p in sys.argv[3:]:
    zbytes += os.path.getsize(p)
    with zipfile.ZipFile(p) as z:
        d = z.read(z.namelist()[0])
    rbytes += len(d); rows += d.count(b"\n")
ratio, bpr = rbytes / zbytes, rbytes / rows
print(f"sample: zip->raw ratio {ratio:.2f}x, {bpr:,.0f} raw bytes/row, {zbytes/rows:,.0f} zipped bytes/row")
def window(start, end):
    tot = defaultdict(int)
    for src in (en, tr):
        for (y, mo), d in src.items():
            if start <= (y, mo) <= end:
                for k, v in d.items():
                    tot[k] += v
    return tot
for label, s, e in [("10y 2016-11..2026-10", ("2016", "11"), ("2026", "10")),
                    ("2y 2024-11..2026-10", ("2024", "11"), ("2026", "10")),
                    ("last 12 mo", ("2025", "11"), ("2026", "10"))]:
    t = window(s, e)
    g = t["gkg"]
    est_rows = g / (zbytes / rows)
    print(f"{label}: GKG zipped {g/1e12:.2f} TB (~{g*ratio/1e12:.1f} TB raw), est {est_rows/1e9:.2f} B rows; events {t['export']/1e9:.0f} GB, mentions {t['mentions']/1e9:.0f} GB zipped")
for y in range(2016, 2027):
    ys = str(y)
    g_en = sum(d["gkg"] for (yy, mo), d in en.items() if yy == ys)
    g_tr = sum(d["gkg"] for (yy, mo), d in tr.items() if yy == ys)
    print(f"  {y}: EN GKG {g_en/1e9:6.0f} GB  TR GKG {g_tr/1e9:6.0f} GB zipped")
