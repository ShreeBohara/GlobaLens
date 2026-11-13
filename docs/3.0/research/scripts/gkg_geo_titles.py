"""GKG follow-up: per-article best geo precision, title language samples, syndication/dup titles.

Usage: python3 -I gkg_geo_titles.py <dir_with_gkg_zips> <label>
"""
import sys
import os
import io
import re
import zipfile
from collections import Counter

d, label = sys.argv[1], sys.argv[2]
files = sorted(f for f in os.listdir(d) if f.endswith(".gkg.csv.zip"))

def rows(zpath):
    with zipfile.ZipFile(zpath) as z:
        with z.open(z.namelist()[0]) as f:
            for raw in io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="\n"):
                raw = raw.rstrip("\n").rstrip("\r")
                if raw:
                    yield raw.split("\t")

best = Counter()
titles = Counter()
samples = []
n = 0
tone_vals = []
for f in files:
    for r in rows(os.path.join(d, f)):
        if len(r) < 27:
            continue
        n += 1
        types = {loc.split("#")[0] for loc in r[10].split(";") if loc}
        if types & {"3", "4"}:
            best["city"] += 1
        elif types & {"2", "5"}:
            best["adm1/state"] += 1
        elif "1" in types:
            best["country-only"] += 1
        else:
            best["none"] += 1
        mt = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", r[26])
        t = mt.group(1).strip() if mt else ""
        titles[t.lower()] += 1
        if len(samples) < 12 and n % 997 == 0:
            ti = r[25]
            samples.append((ti[:20], t[:110], r[4][:90]))
dupt = sum(c - 1 for t, c in titles.items() if c > 1 and t)
print(f"== {label}: records={n}")
print("Best location precision per article:", {k: f"{100*v/n:.1f}%" for k, v in best.items()})
print(f"Exact-duplicate titles (case-insensitive) within sample: {dupt} ({100*dupt/n:.1f}%)")
print("Most repeated titles:", [(t[:70], c) for t, c in titles.most_common(6)])
print("Samples (translationinfo, title, url):")
for s in samples:
    print("  ", s)
