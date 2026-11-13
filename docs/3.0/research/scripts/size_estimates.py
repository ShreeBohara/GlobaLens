"""Estimate raw (uncompressed) sizes and per-column byte shares for GDELT tables.

Usage: python3 -I size_estimates.py <masterfilelist.txt> <masterfilelist-translation.txt> <en_day_dir> <tr_day_dir>
"""
import sys
import os
import io
import re
import zipfile
from collections import defaultdict

ml_en, ml_tr, en_dir, tr_dir = sys.argv[1:5]
pat = re.compile(r"^(\d+)\s+\S+\s+\S*/(\d{14})\.(?:translation\.)?(export|mentions|gkg)\.(?:CSV|csv)\.zip\s*$")

def totals(path):
    tot = defaultdict(int)
    last30 = defaultdict(int)
    for line in open(path, errors="replace"):
        m = pat.match(line.strip())
        if not m:
            continue
        size, ts, typ = int(m.group(1)), m.group(2), m.group(3)
        tot[typ] += size
        if ts >= "20260929":
            last30[typ] += size
    return tot, last30

def ratio(d, kind):
    z = u = 0
    for f in os.listdir(d):
        if kind in f:
            p = os.path.join(d, f)
            z += os.path.getsize(p)
            with zipfile.ZipFile(p) as zf:
                u += sum(i.file_size for i in zf.infolist())
    return u / z if z else float("nan")

GKG_COLS = ["GKGRECORDID", "DATE", "SourceCollectionIdentifier", "SourceCommonName", "DocumentIdentifier",
            "Counts", "V2Counts", "Themes", "V2Themes", "Locations", "V2Locations", "Persons", "V2Persons",
            "Organizations", "V2Organizations", "V2Tone", "Dates", "GCAM", "SharingImage", "RelatedImages",
            "SocialImageEmbeds", "SocialVideoEmbeds", "Quotations", "AllNames", "Amounts", "TranslationInfo", "Extras"]

def col_share(d):
    sums = [0] * 27
    for f in os.listdir(d):
        if not f.endswith(".gkg.csv.zip"):
            continue
        with zipfile.ZipFile(os.path.join(d, f)) as zf:
            with zf.open(zf.namelist()[0]) as fh:
                for raw in io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="\n"):
                    r = raw.rstrip("\n").split("\t")
                    if len(r) < 27:
                        continue
                    for i in range(27):
                        sums[i] += len(r[i].encode("utf-8", "replace"))
    tot = sum(sums)
    return {GKG_COLS[i]: sums[i] / tot for i in range(27)}

for label, ml, dd in (("EN", ml_en, en_dir), ("TR", ml_tr, tr_dir)):
    tot, last30 = totals(ml)
    print(f"== {label}")
    for typ, kind in (("export", ".export.CSV.zip"), ("mentions", ".mentions.CSV.zip"), ("gkg", ".gkg.csv.zip")):
        r = ratio(dd, kind)
        print(f"  {typ}: total zipped since 2015 = {tot[typ]/1e12:.3f} TB; unzip ratio(sample)={r:.2f} -> est raw = {tot[typ]*r/1e12:.2f} TB; "
              f"last-30-days zipped={last30[typ]/1e9:.1f} GB -> raw {last30[typ]*r/1e9:.1f} GB")
    shares = col_share(dd)
    top = sorted(shares.items(), key=lambda kv: -kv[1])
    print("  GKG column byte shares:", ", ".join(f"{k}={v*100:.1f}%" for k, v in top[:14]))
    sel = ["DocumentIdentifier", "SourceCommonName", "DATE", "V2Themes", "V2Locations", "V2Persons", "V2Organizations", "V2Tone", "SharingImage", "Extras", "TranslationInfo"]
    print(f"  'map-useful' column subset share (no GCAM/AllNames/Counts/V1 dupes): {sum(shares[c] for c in sel)*100:.1f}%")
    sel2 = ["DocumentIdentifier", "SourceCommonName", "DATE", "V2Locations", "V2Tone", "SharingImage", "TranslationInfo"]
    print(f"  'minimal' subset share (url, source, date, locations, tone, image, lang): {sum(shares[c] for c in sel2)*100:.1f}%")
