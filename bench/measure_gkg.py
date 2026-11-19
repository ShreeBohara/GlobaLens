"""Measure GKG properties that drive GlobaLens design decisions.

Usage: python3 -I measure_gkg.py <gkg .csv or .csv.zip> [...]

Reports: precise-pubtimestamp coverage, crawl lag (DATE - PAGE_PRECISEPUBTIMESTAMP),
city-level location share, exact-dup title share, and single-core Python parse throughput
(naive tab split vs full nested-field parse).

This is the research script behind `docs/3.0/research/data-gdelt.md`, moved here from
`docs/3.0/research/scripts/` in P1 task 9. It keeps its own naive parser on purpose, so that
its numbers stay comparable with the research report. `parse_bench.py` measures the real
parser in `packages/gdelt`.
"""

import html
import re
import sys
import time
import unicodedata
import zipfile
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

RE_TITLE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)
RE_PTS = re.compile(r"<PAGE_PRECISEPUBTIMESTAMP>(\d{14})</PAGE_PRECISEPUBTIMESTAMP>")
TRACK = ("utm_", "fbclid", "gclid", "ocid", "cmpid", "ref")

Location = tuple[int, str, str, str, str, float, float, str, int]


def load_lines(path: str) -> tuple[bytes, list[str]]:
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            name = z.namelist()[0]
            data = z.read(name)
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data, data.decode("utf-8", errors="replace").split("\n")


def canon_url(u: str) -> str:
    try:
        s = urlsplit(u)
        q = [(k, v) for k, v in parse_qsl(s.query) if not k.lower().startswith(TRACK)]
        host = s.netloc.lower().removeprefix("www.").removeprefix("m.").removeprefix("amp.")
        return urlunsplit(("https", host, s.path.rstrip("/"), urlencode(q), ""))
    except Exception:
        return u


def full_parse(cols: list[str]) -> dict[str, Any]:
    rec: dict[str, Any] = {}
    rec["id"] = cols[0]
    rec["date"] = datetime.strptime(cols[1], "%Y%m%d%H%M%S")
    rec["src"] = cols[3]
    rec["url"] = canon_url(cols[4])
    themes: list[tuple[str, int]] = []
    for t in cols[8].split(";"):
        if t:
            name, _, off = t.rpartition(",")
            themes.append((name, int(off) if off.isdigit() else -1))
    rec["themes"] = themes
    locs: list[Location] = []
    for entry in cols[10].split(";"):
        if not entry:
            continue
        p = entry.split("#")
        if len(p) < 9:
            continue
        try:
            offset = int(p[8]) if p[8].isdigit() else -1
            locs.append((int(p[0]), p[1], p[2], p[3], p[4], float(p[5]), float(p[6]), p[7], offset))
        except ValueError:
            pass
    rec["locs"] = locs
    city = [x for x in locs if x[0] in (3, 4)]
    rec["primary"] = min(city, key=lambda x: x[8]) if city else None
    rec["persons"] = [p.rpartition(",")[0] for p in cols[12].split(";") if p]
    rec["orgs"] = [p.rpartition(",")[0] for p in cols[14].split(";") if p]
    tone = cols[15].split(",")
    rec["tone"] = [float(x) for x in tone] if len(tone) >= 7 and tone[0] else None
    rec["img"] = cols[18] or None
    ti = cols[25]
    rec["lang"] = ti.split(";")[0].removeprefix("srclc:") if ti.startswith("srclc:") else "eng"
    ex = cols[26]
    m = RE_TITLE.search(ex)
    title = html.unescape(m.group(1)) if m else ""
    rec["title"] = title
    rec["title_norm"] = unicodedata.normalize("NFKC", title).lower().strip()
    m2 = RE_PTS.search(ex)
    rec["pts"] = datetime.strptime(m2.group(1), "%Y%m%d%H%M%S") if m2 else None
    return rec


def quantile(a: list[float], f: float) -> float:
    return a[min(len(a) - 1, int(f * len(a)))]


def main(paths: list[str]) -> None:
    all_rows: list[str] = []
    total_bytes = 0
    for p in paths:
        data, lines = load_lines(p)
        total_bytes += len(data)
        all_rows.extend([line for line in lines if line])
    n = len(all_rows)
    t0 = time.perf_counter()
    split_rows = [r.split("\t") for r in all_rows]
    t_split = time.perf_counter() - t0
    good = [c for c in split_rows if len(c) == 27]
    t0 = time.perf_counter()
    recs = [full_parse(c) for c in good]
    t_full = time.perf_counter() - t0
    mb = total_bytes / 1e6
    print(f"files={len(paths)} rows={n} well_formed={len(good)} bytes={mb:.1f}MB")
    print(f"naive split: {n / t_split:,.0f} rows/s, {mb / t_split:,.0f} MB/s")
    print(
        f"full nested parse (after split): {len(good) / t_full:,.0f} rows/s; "
        f"split+parse: {len(good) / (t_split + t_full):,.0f} rows/s, "
        f"{mb / (t_split + t_full):,.0f} MB/s"
    )
    with_pts = [r for r in recs if r["pts"]]
    print(f"precise pubtimestamp present: {len(with_pts) / len(recs):.1%}")
    lags: list[float] = [(r["date"] - r["pts"]).total_seconds() / 60 for r in with_pts]
    neg = sum(1 for x in lags if x < 0)
    pos = sorted(x for x in lags if x >= 0)
    q = quantile
    print(
        f"crawl lag (min, DATE - precise ts): negative(ts after crawl)={neg / len(lags):.1%}; "
        f"among >=0: p25={q(pos, 0.25):.0f} median={q(pos, 0.5):.0f} p75={q(pos, 0.75):.0f} "
        f"p90={q(pos, 0.9):.0f} p99={q(pos, 0.99):.0f}"
    )
    print(
        f"  share lag<=15min={sum(1 for x in pos if x <= 15) / len(lags):.1%} "
        f"<=60min={sum(1 for x in pos if x <= 60) / len(lags):.1%} "
        f">24h={sum(1 for x in pos if x > 1440) / len(lags):.1%}"
    )
    city = sum(1 for r in recs if r["primary"])
    print(
        f"has city/landmark-level location (Geo_Type 3/4): {city / len(recs):.1%}; "
        f"any location: {sum(1 for r in recs if r['locs']) / len(recs):.1%}"
    )
    titles: list[str] = [r["title_norm"] for r in recs if r["title_norm"]]
    dup = len(titles) - len(set(titles))
    dup_urls = len(recs) - len({r["url"] for r in recs})
    print(
        f"exact-duplicate normalized titles: {dup / len(titles):.1%} of titled docs; "
        f"urls dup after canon: {dup_urls / len(recs):.1%}"
    )
    print(
        f"sharing image: {sum(1 for r in recs if r['img']) / len(recs):.1%}; "
        f"distinct source langs: {len({r['lang'] for r in recs})}; "
        f"distinct domains: {len({r['src'] for r in recs})}"
    )
    langs: dict[str, int] = {}
    for r in recs:
        langs[r["lang"]] = langs.get(r["lang"], 0) + 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:8]
    print("top langs:", ", ".join(f"{k}:{v}" for k, v in top))


if __name__ == "__main__":
    main(sys.argv[1:])
