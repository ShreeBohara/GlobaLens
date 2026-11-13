"""Profile one day of GDELT 2.0 events/mentions (all 96 files) + sampled GKG files.

Usage: python3 -I profile_day.py <dir_with_zips> <label>
"""
import sys
import os
import io
import re
import zipfile
import statistics
from collections import Counter, defaultdict
from urllib.parse import urlparse

d, label = sys.argv[1], sys.argv[2]
files = sorted(os.listdir(d))

def rows(zpath):
    with zipfile.ZipFile(zpath) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            for raw in io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="\n"):
                raw = raw.rstrip("\n").rstrip("\r")
                if raw:
                    yield raw.split("\t")

def domain(u):
    try:
        h = urlparse(u).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""

print(f"=================== {label} ===================")
# ---------------- EVENTS ----------------
ev_files = [f for f in files if ".export.CSV.zip" in f]
mn_files = [f for f in files if ".mentions.CSV.zip" in f]
gkg_files = [f for f in files if ".gkg.csv.zip" in f]
print(f"files: export={len(ev_files)} mentions={len(mn_files)} gkg(sample)={len(gkg_files)}")

n = 0
ids = set()
urls = set()
doms = Counter()
geo_type = Counter()
root = Counter()
quad = Counter()
rootcode = Counter()
nm, ns, na, tone, gold = [], [], [], [], []
ncols = Counter()
olddate = 0
dupkey = Counter()
actor_empty = 0
fullname_country_only = 0
cent = Counter()  # lat/long pairs for country-level
for f in ev_files:
    for r in rows(os.path.join(d, f)):
        ncols[len(r)] += 1
        if len(r) < 61:
            continue
        n += 1
        ids.add(r[0])
        urls.add(r[60])
        doms[domain(r[60])] += 1
        geo_type[r[51]] += 1
        root[r[25]] += 1
        quad[r[29]] += 1
        rootcode[r[28]] += 1
        try:
            nm.append(int(r[31])); ns.append(int(r[32])); na.append(int(r[33]))
            tone.append(float(r[34])); gold.append(float(r[30]) if r[30] else 0.0)
        except ValueError:
            pass
        if r[1][:8] != r[59][:8]:
            olddate += 1
        dupkey[(r[1], r[5], r[15], r[26], r[58])] += 1
        if not r[5] and not r[15]:
            actor_empty += 1
        if r[51] == "1":
            cent[(r[56], r[57])] += 1

print(f"\n-- EVENTS (export) --\nrows={n} unique_ids={len(ids)} unique_sourceurls={len(urls)} unique_domains={len(doms)} col_counts={dict(ncols)}")
print("ActionGeo_Type:", {k: f"{v} ({100*v/n:.1f}%)" for k, v in sorted(geo_type.items())})
print("IsRootEvent:", dict(root))
print("QuadClass:", {k: f"{100*v/n:.1f}%" for k, v in sorted(quad.items())})
print("Top EventRootCode:", [(k, f"{100*v/n:.1f}%") for k, v in rootcode.most_common(8)])
print(f"NumMentions median={statistics.median(nm)} mean={statistics.mean(nm):.2f} p99={sorted(nm)[int(.99*len(nm))]}")
print(f"NumSources median={statistics.median(ns)} mean={statistics.mean(ns):.2f}; share NumSources==1: {100*sum(1 for x in ns if x==1)/len(ns):.1f}%")
print(f"NumArticles median={statistics.median(na)} mean={statistics.mean(na):.2f}")
print(f"AvgTone mean={statistics.mean(tone):.2f} median={statistics.median(tone):.2f}")
print(f"Goldstein mean={statistics.mean(gold):.2f}")
print(f"Event SQLDATE != DATEADDED date: {olddate} ({100*olddate/n:.1f}%)")
dups = sum(c - 1 for c in dupkey.values() if c > 1)
print(f"Near-duplicate rows on key (day,actor1,actor2,eventcode,actiongeo_featureid): {dups} ({100*dups/n:.1f}%); distinct keys={len(dupkey)}")
print(f"Rows with both actor codes empty: {actor_empty} ({100*actor_empty/n:.1f}%)")
print("Top country-centroid coordinates for ActionGeo_Type=1:", cent.most_common(5))
print("Events per unique URL:", f"{n/len(urls):.2f}")
print("Top domains:", doms.most_common(10))

# ---------------- MENTIONS ----------------
m = 0
murls = set()
mtype = Counter()
older = 0
conf = []
mdom = Counter()
lang = Counter()
mevids = set()
for f in mn_files:
    for r in rows(os.path.join(d, f)):
        if len(r) < 15:
            continue
        m += 1
        murls.add(r[5])
        mtype[r[3]] += 1
        mevids.add(r[0])
        mdom[r[4]] += 1
        if r[1][:8] != r[2][:8]:
            older += 1
        try:
            conf.append(int(r[11]))
        except ValueError:
            pass
        ti = r[14]
        mm = re.search(r"srclc:([a-z]{3})", ti)
        lang[mm.group(1) if mm else "eng(none)"] += 1
print(f"\n-- MENTIONS --\nrows={m} unique_mention_urls={len(murls)} unique_events_mentioned={len(mevids)} unique_sources={len(mdom)}")
print("MentionType:", dict(mtype))
print(f"Mentions where EventTimeDate day != MentionTimeDate day (re-mentions of older events): {older} ({100*older/m:.1f}%)")
print(f"Confidence median={statistics.median(conf)}; share >=50: {100*sum(1 for c in conf if c>=50)/len(conf):.1f}%")
print("Top translation source languages (mentions):", lang.most_common(15), "distinct:", len(lang))

# ---------------- GKG (sampled) ----------------
g = 0
gdocs = set()
coll = Counter()
has = Counter()
extras_tags = Counter()
title_len = []
loc_types = Counter()
gdom = Counter()
glang = Counter()
engines = Counter()
wc = []
themes_n = []
bytes_raw = 0
for f in gkg_files:
    for r in rows(os.path.join(d, f)):
        if len(r) < 27:
            has["_short_rows"] += 1
            continue
        g += 1
        bytes_raw += sum(len(x) for x in r) + 26
        gdocs.add(r[4])
        coll[r[2]] += 1
        gdom[r[3]] += 1
        if r[8]: has["V2Themes"] += 1
        if r[10]: has["V2Locations"] += 1
        if r[12]: has["V2Persons"] += 1
        if r[14]: has["V2Orgs"] += 1
        if r[17]: has["GCAM"] += 1
        if r[18]: has["SharingImage"] += 1
        if r[19]: has["RelatedImages"] += 1
        if r[22]: has["Quotations"] += 1
        if r[23]: has["AllNames"] += 1
        if r[24]: has["Amounts"] += 1
        if r[16]: has["Dates"] += 1
        for t in set(re.findall(r"<([A-Z_]+)>", r[26])):
            extras_tags[t] += 1
        mt = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", r[26])
        if mt and mt.group(1).strip():
            has["PAGE_TITLE_nonempty"] += 1
            title_len.append(len(mt.group(1)))
        for loc in r[10].split(";"):
            if loc:
                loc_types[loc.split("#")[0]] += 1
        mm = re.search(r"srclc:([a-z]{3})", r[25])
        glang[mm.group(1) if mm else "eng(none)"] += 1
        me = re.search(r"eng:([^;]+)", r[25])
        if me:
            engines[me.group(1)] += 1
        mw = re.search(r"(?:^|,)wc:(\d+)", r[17])
        if mw:
            wc.append(int(mw.group(1)))
        themes_n.append(len([t for t in r[8].split(";") if t]))
gz = sum(os.path.getsize(os.path.join(d, f)) for f in gkg_files)
print(f"\n-- GKG (sample of {len(gkg_files)} x 15-min files) --")
print(f"records={g} per_file_avg={g/len(gkg_files):.0f} unique_docs={len(gdocs)} unique_source_names={len(gdom)}")
print(f"zipped bytes/record={gz/g:.0f}; raw bytes/record={bytes_raw/g:.0f}")
print("SourceCollectionIdentifier:", dict(coll))
print("Field presence:", {k: f"{100*v/g:.1f}%" for k, v in sorted(has.items())})
print("Extras XML tags (share of records):", [(k, f"{100*v/g:.1f}%") for k, v in extras_tags.most_common(20)])
if title_len:
    print(f"PAGE_TITLE length median={statistics.median(title_len)}")
print("V2Locations type counts (1=country,2=US state,3=US city,4=world city,5=world ADM1):", dict(loc_types))
print(f"GCAM wc (article word count) median={statistics.median(wc) if wc else 'n/a'}")
print(f"Themes per record median={statistics.median(themes_n)}")
print("Top languages (GKG):", glang.most_common(20), "distinct:", len(glang))
print("Translation engines:", engines.most_common(5))
print("Top source names:", gdom.most_common(10))
