# GDELT as the Data Backbone: GlobaLens 3.0 Research

*Status as of 2026-10-29. Confidence tags: [H] high, [M] medium, [L] low.*

**Method.** Most numbers here were **measured directly** rather than quoted:
- Downloaded both GDELT 2.0 master file lists (about 1.2M lines each, Feb 2015 to 2026-10-29 06:00 UTC).
- Downloaded one full weekday (Tue 2026-10-27) of Events and Mentions for both the English and translated streams (96 files each).
- Downloaded 8 GKG files per stream, one Global Similarity Graph (GSG) embedding file and one v5 TOC/ngram burst.
- Probed every GDELT API and read the official codebooks.

Papers were verified through OpenAlex and primary pages. *Caveat: the shared WebSearch budget ran out partway through this task. Later facts were verified by fetching primary pages directly, and the few that could not be verified are flagged.*

## TL;DR
- **Keep GDELT as the backbone, but use the files, not the APIs.** GKG 2.1 (English plus translated) is still the only free, 15-minute, 60+ language, geocoded and themed news-metadata stream. GDELT's own search layer is degrading. DOC 2.0 returned **HTTP 429 on every call** **[corrected: heavily throttled but intermittent. The fact-check got 429 on 2 of 3 calls, after about 11 s, with the same "one every 5 seconds… switch to our ngrams dataset" message. The third call returned HTTP 200 with articles after 23 s.]**, GEO 2.0 returns **404**, and GDELT now steers heavy users to a "temporary" v5 ngram feed.
- **The files are reliable but not perfect.** In 2026 only **1 of 28,921** English 15-minute intervals is missing. But **2025-06-14 18:00 to about 07-02 UTC (≈17.3 days) was never published**, with no public notice. English GKG volume is **down 61% from 2016**, the Frontpage Graph has published empty files since Nov 2025, and Visual GKG froze in Feb 2022.
- **Volume on Tue 2026-10-27:** about 340k GKG articles (≈117k English plus ≈224k translated), 193k events and 457k mentions. That is about 4 GB/day of raw GKG, of which **about 70% is GCAM**.
- **No scraping is needed for map cards.** `PAGE_TITLE` is present in **99.9%** of GKG records and the share image (og:image) in 82–88%.
- **Quality issues are structural, so dedup and geo-precision handling must be core features:**
  - 22.8% of English articles in a sample had an exact-duplicate headline.
  - 22% (English) and 42% (translated) of events are geocoded only to a **country centroid**. One day placed **1,880 events on the US centroid in Kansas**.
- **Licensing:** the terms allow storage, transformation, public apps and public APIs, with citation and a link. Article content remains the publishers' copyright.
- **Product direction:** GDELT measures **media attention, not ground truth**. The translated stream (≈2/3 of articles) is the most defensible differentiator: *how the world's press covers the same story differently*. A third-party "GDELT Cloud" already sells AI-coded events and stories plus an MCP server, so GlobaLens must differentiate.

## (a) What exists, and what is actually alive (probed 2026-10-29)

| Dataset / API | Status and evidence | Role in GlobaLens |
|---|---|---|
| **GKG 2.1** (27 cols) | Live, every 15 min [H] | **Primary**: 1 row per article; themes, locations with char offsets, persons/orgs, tone, GCAM, title, image |
| **Events 2.0** export (61 cols) | Live, every 15 min [H] | Secondary: CAMEO actor/action analytics |
| **Mentions** (16 cols) | Live, every 15 min [H] | Coverage velocity, per-article confidence |
| **Translingual** stream (all 3 tables) | Live; 60 source languages in Mentions on 10-27, 63 in the GKG sample [H] | Cross-language lens |
| **GSG doc embeddings** | Live every 15 min; ~2.5k docs/file; 512-d USEv4 vectors plus title, url, lang (37 languages in one file) [H] | Free baseline embeddings |
| **v5 "weblegacy" ngrams + TOC** (since 2026-06-30) | Live. Files appear in bursts each 15-min cycle. The TOC holds id, date, img, lang, title, url (3,702 docs, 56 languages, 90% with images in one burst). The ngram file holds quadgram counts per doc. GDELT calls it "temporary" [H] | Lightweight article firehose, keyword search |
| DOC 2.0 API | **Throttled**: HTTP 429 after 12–19 s on 3 attempts; the message asks for 1 request per 5 s and points to ngrams [H, from our IP] **[corrected: intermittent, not total. In the 2026-10-29 fact-check, 1 of 3 calls returned HTTP 200 with results (23 s). The other 2 returned 429 after about 11 s, even spaced more than 5 s apart.]** | Keep out of the data path |
| GEO 2.0 API | **HTTP 404** at `/api/v2/geo/geo` [H] | Gone |
| Context 2.0 API | Works; sentence-level hits about 10 min old [H] | Optional enrichment |
| TV 2.0 API | Responds, but rejected a 1-day query with a date error [M] | Out of scope |
| Global Frontpage Graph | **Dead**: hourly files were 234–248 MB (Jan 2024/25), 145 KB (Oct 2025), and 45 bytes from Nov 2025 on [H] | Unusable |
| Visual GKG | **Frozen**: `lastupdate.txt` still points to 2022-02-22 [H] | Unusable |
| GEG, GQG, GGG, GEMG, Web NGrams 3.0, GDG | **Unverified**: my guessed file paths returned 404 for every date, which is inconclusive | Don't plan on them |
| BigQuery `gdelt-bq.gdeltv2` | The data page says tables update every 15 min; not verified this session [M] | One-off backfills |
| "GDELT 5" | The 2026-04-18 post ties it to migrating the API stack from Elasticsearch to Spanner; no dates or schemas [M] | Expect breaking changes |

**Best for a real-time map:** GKG 2.1 (English plus translated) as the article layer, Mentions for growth, Events only for actor-action analytics.

## (b) Cadence, access, volumes

**Access.** Poll `https://data.gdeltproject.org/gdeltv2/lastupdate.txt` and `lastupdate-translation.txt`. Each has 3 lines giving size, MD5 and URL. History lives in `masterfilelist.txt` (129 MB) and `masterfilelist-translation.txt` (141 MB). Plain HTTP returns a 301 to HTTPS, and Range requests are supported.

**Quirks (measured):**
- **Filename stamps are not publish times.** The English file stamped 06:15 was published at 06:04:42. The translated file stamped 06:00 was published at 06:04:30. Both observations were made twice.
- The master lists contain **71 malformed lines** (bare directory URLs).
- GKG titles are HTML-entity-encoded. Translated documents keep their **original-language** title.

**Volumes.** Rows are from 2026-10-27. Zipped sizes are October 2026 daily averages. Raw sizes use the measured unzip ratios.

| Stream | Rows/day (EN / TR) | Unique URLs/day | Zipped/day | Raw/day |
|---|---|---|---|---|
| Events | 119,106 / 74,237 | 23,954 / 30,667 | 6.6 / 5.1 MB | ~41 / ~25 MB |
| Mentions | 318,197 / 138,923 | 51,300 / 52,569 | 9.2 / 6.8 MB | ~58 / ~28 MB |
| GKG | ~117k / ~224k docs | ≈ doc count | 413 / 774 MB (504 / 870 MB on 10-27) | ~1.3 / ~2.5 GB |

That day, 4,099 English and 3,593 translated domains produced events. Only about **55k URLs/day yield events, against about 340k GKG articles**. GKG is the right "all news" layer.

**Trend in zipped MB/day.** English GKG went from 1,103 (2016) to 590 (2023) to 435 (2026 YTD). Translated GKG went from 1,602 to 800. Translated GKG is now **1.9x English**.

**Columns that matter:**
- **GKG:** `DocumentIdentifier`, `SourceCommonName`, `DATE` and `V2Locations`. Each location is `type#name#cc#adm1#adm2#lat#lon#featureID#offset`. Also `V2Themes`, `V2Persons`, `V2Organizations` and `V2Tone` (tone, pos, neg, polarity, densities, word count). Then `SharingImage`, `TranslationInfo` (`srclc:`) and `Extras`. Extras holds `PAGE_TITLE` (99.9%), `PAGE_PRECISEPUBTIMESTAMP` (44–58%), `PAGE_AUTHORS` (~40%) and `PAGE_LINKS` (43–56%).
- **Events:** `GLOBALEVENTID`, `Day`, `DATEADDED`, the Actor1/2 codes, and `EventCode`/`BaseCode`/`RootCode` (store these as strings). Also `QuadClass`, `GoldsteinScale`, `ActionGeo_{Type,Lat,Long,FeatureID}` and `SOURCEURL`.
- **Mentions:** `EventTimeDate`, `MentionTimeDate`, `MentionIdentifier`, `Confidence` and `MentionDocTone`.

## (c) BigQuery

- **Tables:** `gdelt-bq.gdeltv2.{events,eventmentions,gkg}`, plus daily-partitioned `_partitioned` versions keyed on `_PARTITIONTIME` since 2016. `gkg_partitioned` is confirmed by name. In 2016, GKG was 3.6 TB (353M rows), Mentions 104 GB and Events 63 GB.
- **My 2026 size estimate** (from CSV bytes, assuming both streams are loaded): GKG ≈ **22 TB** (8.9 TB English plus 13.6 TB translated), Mentions ≈ 0.6 TB, Events ≈ 0.4 TB [M].
- **The cost trap is GCAM, at 70–73% of GKG bytes.** `V2Themes` is about 9%, `V2Locations` 3–4% and Extras about 3%. A minimal column set (url, source, date, locations, tone, image, lang) is **5–6%** of bytes. A map-useful set (adding themes, persons, orgs and title) is about **19%**.
- **Cost math.** The last 30 days of GKG are about 115 GB raw. One year of minimal columns scans about **85 GB**, and full history about 1.3 TB. All columns over full history is about 22 TB, roughly $130 if on-demand pricing is still $6.25/TiB. That price could not be re-verified this session because the pricing page would not render. **[corrected: verified 2026-10-29 from the pricing page's raw HTML. On-demand is $6.25/TiB, the first 1 TiB/month of queries is free, and the first 10 GiB/month of storage is free. At the 22 TB estimate (about 20 TiB) that is about $125 at list price, or about $119 after the free TiB, slightly under "roughly $130".]**
- **Free tier:** 1 TiB/month of queries. The **sandbox** needs no card and gives 10 GiB lifetime storage, with tables expiring after 60 days and no DML or streaming.
- **Pitfalls:** `SELECT *`; non-partitioned tables (GDELT's own 2-week example scanned 423 GB unpartitioned versus 15 GB partitioned); `LIMIT` does not reduce bytes billed; wrapping `_PARTITIONTIME` in functions disables pruning.
- **Cheap pattern:** dry-run, then set `maximum_bytes_billed`, then query `_partitioned` tables with a `_PARTITIONTIME` range and explicit columns. Write the results to your own Parquet.
- **Verdict:** the free tier works for **any Events/Mentions history**. Downloading the files is even simpler, at about 10 GB zipped per year for both streams. It also works for **1–3 years of minimal GKG columns**. Full GKG including GCAM is not realistic.

## (d) Data quality (measured on 2026-10-27, plus literature)

- **Centroid geocoding.** ActionGeo types 1/2/5 (country, US state, ADM1) carry centroid coordinates and a blank FeatureID, per the codebook. **[corrected: the FeatureID is not blank for these types. The codebook contradicts itself: its Geo_Type note says the field "will be blank", but its Geo_FeatureID note says these types hold a textual FeatureID. The live 2026-10-29 06:15 UTC files (872 events, 10,066 GKG locations) show text codes for types 1/2 (`FR`, `TX`). Type 5 carries signed numeric GNS IDs (e.g. `-1998981`), exactly like cities. Only type 0 (no geo) is blank. Filter on Geo_Type, never on whether FeatureID is present.]** They make up **38% of English and 45% of translated events**. Country-level alone is 21.8% English and 42.4% translated.
  - The top English point is **39.828175, -98.5795**, the US geographic centre in Kansas, with **1,880 events**. Next come the UK (54, -4), Israel, Iran and China.
  - Top translated centroids are Ukraine (49, 32), Sweden and Russia.
- **GKG location precision per article:**

  | Best location | English | Translated |
  |---|---|---|
  | City or landmark | 58.5% | 50.9% |
  | Country only | 12.4% | 26.2% |
  | None | about 21% | about 21% |

  GKG 2.1 includes articles with no location by design.
- **Duplicates and syndication.** GKG 2.1 does not cluster articles (per the codebook).
  - **22.8%** of English and 5.1% of translated titles were exact duplicates within the sample.
  - iheart.com alone was 8.5% of English documents.
  - Big News Network clone sites republish the same stories.
- **Events.** 12.3% (English) and 11.2% (translated) of rows share the key (day, actor1, actor2, EventCode, FeatureID) with another row. English averages about 5 events per URL.
- **Misleading legacy fields.** NumMentions, NumSources, NumArticles, AvgTone and IsRootEvent cover only the **first 15-minute window**, per the codebook. As a result **NumSources = 1 for 97.4% of English and 98.8% of translated events**. Use Mentions instead.
- **Thinner extraction for translated documents.** Persons appear in 35% versus 78% of documents. Quotations appear in **0%** versus 19.6%. Mentions Confidence has a median of 40 for English (only 39.7% at or above 50) versus 100 for translated.
- **CAMEO skew.** 62.9% of events are "verbal cooperation", and "consult" plus "make public statement" make up about 40%. MIRAI dropped 3rd-level codes as noisier.
- **Literature:**
  - Hammond & Weidmann (2014) found a mediocre correlation with hand-coded data and **geographic bias at the subnational level**.
  - Wang et al. (2016, *Science*) raised accuracy and duplication concerns for automated protest coding.
  - Weidmann (2016) documents media reporting bias.
  - Kwak & An (2014) found uneven disaster coverage.
- **URL rot and paywalls** were not measured. Titles in GKG make display independent of the live page.

**Cleaning recipe:**
1. Canonicalize URLs by stripping tracking parameters and AMP/mobile variants (`PAGE_ALTURL_AMP` helps), then dedup.
2. Normalize titles with `html.unescape` and NFKC, lowercase, and strip " - Site" suffixes. Use exact hashes plus MinHash LSH, then multilingual embedding ANN for clusters across languages.
3. Plot points only for geo types 3/4 **[corrected: select `Geo_Type ∈ {3,4}` explicitly. "FeatureID present" does not exclude centroids, because types 1/2/5 also carry FeatureIDs and type-5 IDs are numeric like city IDs.]**. Aggregate types 1/2/5 into choropleths. Block known centroid coordinates. Take the **earliest city-level `V2Locations` entry by char offset** as the primary location.
4. Use events at CAMEO base/root level only, collapsed on (Day, Actor1, Actor2, EventBaseCode, FeatureID). Measure importance as distinct sources in Mentions over 24–72 h, not the legacy fields.

## (e) Terms of use

GDELT's terms declare all datasets free for "unlimited and unrestricted use", whether academic, commercial or governmental. They explicitly allow redistributing, rehosting, republishing and mirroring, on condition of a **citation to the GDELT Project plus a link to gdeltproject.org** [H]. **Storing, transforming, displaying and serving GDELT-derived data through a public app and a public API is permitted.** Put the attribution in the UI, API docs and API responses.

Limits:
- The license covers GDELT's metadata, not publishers' content. Show title, source and link; store no full text; be conservative with thumbnails, which are publishers' og:images.
- Third-party wrappers set their own terms. GDELT Cloud asks you to contact it before redistribution, resale or high-volume public use.
- Media Cloud is research-oriented: it is not designed as a commercial tool, aggregate outputs are shareable, and third-party content is not licensed.
- **Do not reconstruct article text from ngrams.** A 2026 paper (Fronzetti Colladon & Vestrelli) rebuilt articles from Web NGrams 3.0 at up to 95% similarity. Doing that in a public product is a copyright hazard.

## (f) Reliability 2025–2026, and fallbacks

**Evidence:**
- **2026-01-01 to 10-29:** 1 English and 2 translated intervals missing [H].
- **2025-06-14 18:00 UTC: 1,665 consecutive 15-minute intervals (≈17.3 days) were never published**, plus a 2.2-hour gap on 06-12 [H]. The June and July 2025 blog archives show no outage post, and the blog itself was silent from 06-14 to 07-02 [M].
- **2026-10-24, 19:55–23:00 UTC:** a GitHub project saw 404s on every file [M]. Those intervals now exist in the master list, so retry and backfill works. **[corrected: the conclusion holds, since the 10-24 20:00–22:45 files now return HTTP 200 for both streams. The reasoning does not, because a master-list entry does not prove a file downloads. `20261029061500.translation.export.CSV.zip` was listed with size and MD5 in both `lastupdate-translation.txt` and the master list, yet returned 404 for at least 7 min (06:21–06:28 UTC) while its mentions and GKG siblings were live. The gap counts above therefore measure manifest entries, not downloadable files.]**
- **The API layer is degrading:** DOC is throttled, GEO is gone, a "temporary" ngram feed is offered instead, and a Spanner migration and GDELT 5 are pending. Dataset decay (Frontpage Graph, Visual GKG) and the shift of public output toward Gemini/TV experiments suggest **declining investment in the classic web pipeline** [M, inference].

**Verdict:** GDELT is safe as the backbone, because nothing free matches it. It is **not safe as a single point of failure**.

**Fallback and complementary feeds** (official pricing pages, Oct 2026):

| Feed | Free tier | Paid entry | Notes | Role |
|---|---|---|---|---|
| Publisher RSS | Free | – | Real-time; titles and ledes are meant for syndication | **Ledes + fallback** (~300 curated outlets) |
| CC-NEWS (Common Crawl) | Free | – | 8–13 WARCs/day **[corrected: 8–15 per day in Oct 2026, per `warc.paths.gz`]** of about 1.07 GB; newest about 4 h old; full HTML; publishers' copyright | Offline full text for ML training/eval |
| NewsAPI.ai / Event Registry | 2,000 searches | $90/mo | 150k+ outlets, 50+ languages, **event clustering**, token-based | Clustering benchmark; optional |
| GNews | 100 req/day, non-commercial, 12 h delay | €49.99/mo | Full content on paid plans | Small fallback |
| NewsData.io | 200 credits/day, 48 h **[corrected: 48 h is the lookback window, and free-tier data is also delayed 12 h]** | $199.99/mo | – | Skip |
| Webz.io | $5 credits/mo | $0.001 per search call | 170+ languages | Spot checks |
| NewsAPI.org | Dev only: 100/day, 24 h delay, no staging/prod | $449/mo | – | Avoid |
| Media Cloud | Free | – | 1B+ stories, directory of 25k+ sources; research use | Source metadata, validation |
| GDELT Cloud (third party) | 200 calls | Self-serve | AI-coded events; refreshes twice daily or hourly | **Competitor** reference |

## (g) Ingestion design (concrete)

1. **Poller.** Check both lastupdate files every 60 s (about 300 bytes each). On a new stamp, fetch the 3 files over HTTPS and verify size and MD5. Store the raw zip under `raw/gdelt/{stream}/{type}/dt=…/` and enqueue a parse job. Use (stream, type, stamp) as the idempotency key.
2. **Reconciler, hourly.** Fetch the tail of the master list with an HTTP Range request (about 33 KB per stream per day). Diff it against the manifest and backfill with backoff. After 7 days, record the interval as a known gap.
3. **Parse.** One 15-minute batch is about 3.6k GKG rows, or about 45 MB raw. Naive Python split ran at **23k rows/s (about 300 MB/s)** here, so **ingestion needs no C++ or Rust**.
4. **Lean projection.** Drop GCAM (keep a few curated dimensions) and the V1 duplicate columns, which removes about 80% of bytes. At about 300–350k articles/day, that is roughly 10M hot rows per 30 days.
5. **Online dedup and clustering.** MinHash, then ANN over embeddings, producing story clusters with languages, countries, tone spread and velocity.
6. **Text for embeddings.** Titles alone are enough for clustering and search. GSG supplies free USEv4 vectors as a baseline, though it is a 2018-era model; compute your own multilingual title embeddings (300k short strings a day is small). Fetch HTML only for cluster representatives, at most a few thousand a day. Read og:description or the first paragraph, respect robots.txt, and **store 1–2 sentences at most**. RSS `<description>` is the other cheap lede source.
7. **Freshness.** Alert if no new stamp arrives for 45 min. The UI shows "data as of …" and keeps the last good state.
8. **Contract tests.** Use golden files covering malformed lines, HTML entities and 61/16/27 column counts, because GDELT 5 may change formats.

## (h) Derived signals and research

**Signals:**
- `GoldsteinScale`: −10 to +10, fixed per CAMEO code.
- `QuadClass`.
- `AvgTone` and `V2Tone` (tone, polarity, word count).
- **Mentions velocity**: distinct sources per hour per cluster or place.
- `Confidence`.
- Themes, including crisis and World Bank taxonomies.
- **GCAM**: 2,300+ dimensions from 24 packages, with 15 languages assessed natively.

**Research using GDELT:**
- Unrest prediction with hidden Markov models (Qiao 2017) and with ML (Galla & Burke 2018).
- Graph-based detection of political crises (Keneshloo 2014).
- Nowcasting the Global Peace Index from news (Voukelatou 2022).
- Temporal knowledge-graph forecasting benchmarks (RE-NET, Jin 2020).
- **LLM agents (MIRAI, 2024).** After filtering to events with at least 50 daily mentions and 2nd-level CAMEO codes, the best agents scored only **about 30–33 F1**. **[corrected: the ≥50-daily-mentions threshold builds the database; test queries require ≥100 daily mentions and ≥5 downloaded articles. The best second-level F1 was 29.6 on the 705-query test set, and 32.6–32.8 for GPT-4o on a 100-query subset.]**

**Limits:**
- Subnational bias (Hammond & Weidmann 2014) and reporting bias (Weidmann 2016).
- CAMEO is aging. PLOVER/POLECAT (Halterman 2023) replaces it with a transformer-based coder.
- Operational early-warning systems such as ViEWS (Hegre 2019) build on curated UCDP data, not raw news coding.

**Lesson:** present attention **surges with baselines and uncertainty, not predictions**. Benchmark any LLM event extraction against curated ground truth.

## What this should change about GlobaLens (product direction)
1. **Honest claim:** "what the world's media is paying attention to, and how differently", not "what is happening".
2. **Signature feature, a cross-lingual Lens:** for each story, show coverage share, tone and framing by language and country.
3. **Story-first UX:** organize around clusters and situations, not raw articles. At least 1 in 5 English headlines is a duplicate.
4. **Multi-resolution geography:** city points, country/ADM1 choropleths and an "unlocated" stream. Never fake precision.
5. **Visible data health and evaluation pages** as features.
6. **Differentiate from GDELT Cloud** through the Lens UX, openness and cross-lingual comparison.

## Recommendations for GlobaLens 3.0
1. **MUST:** Make GKG 2.1 files (English plus translated) the backbone, with Events/Mentions secondary. Keep the DOC and GEO APIs out of the data path.
2. **MUST:** Build a self-healing ingester: lastupdate poller, master-list reconciler, MD5 checks, idempotent keys, a known-gap registry (June 2025) and a freshness SLO with a UI banner.
3. **MUST:** Make dedup and story clustering a core pipeline stage (URL canonicalization, title MinHash, multilingual embedding ANN).
4. **MUST:** Use geo-precision tiers and suppress centroid artifacts; choose the primary location by char offset.
5. **MUST:** Put GDELT attribution everywhere and store only metadata, titles and URLs. Fetch ledes only where robots.txt allows, and offer publishers an opt-out.
6. **SHOULD:** Use a lean schema that drops GCAM and V1 columns (−80% bytes), with 30–90 hot days and cold daily Parquet.
7. **SHOULD:** Use multilingual title embeddings with GSG as a baseline. Take ledes from RSS or og:description for cluster representatives only.
8. **SHOULD:** Ship the cross-lingual comparison as the flagship feature early (around phase 3–4).
9. **SHOULD:** Build an evaluation harness against UCDP/ACLED/POLECAT, license permitting, plus a calibrated MIRAI-style forecasting demo.
10. **COULD:** Add a `SourceConnector` abstraction covering RSS, CC-NEWS and the NewsAPI.ai free tier, and use the v5 TOC for a live ticker.
11. **COULD:** Use the BigQuery sandbox for one-off backfills of minimal columns, always with a dry run and `maximum_bytes_billed`.
12. **COULD:** Add golden-file contract tests in CI and track GDELT 5 and the Spanner migration.

## Sources
- GDELT terms of use / about: https://www.gdeltproject.org/about.html
- GDELT data page: https://www.gdeltproject.org/data.html
- Live manifests (measured 2026-10-29): https://data.gdeltproject.org/gdeltv2/lastupdate.txt · https://data.gdeltproject.org/gdeltv2/lastupdate-translation.txt · https://data.gdeltproject.org/gdeltv2/masterfilelist.txt · https://data.gdeltproject.org/gdeltv2/masterfilelist-translation.txt
- Event codebook v2.0: http://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf
- GKG codebook v2.1: http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf
- Partitioned BigQuery tables (2016): https://blog.gdeltproject.org/announcing-partitioned-gdelt-bigquery-tables/
- DOC 2.0 API (2017): https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- v5 Web NGrams/TOC (2026-06-30): https://blog.gdeltproject.org/using-the-new-web-ngrams-dataset-to-find-relevant-coverage/
- Spanner migration / GDELT 5 (2026-04-18): https://blog.gdeltproject.org/scaling-gdelt-for-a-new-era-migrating-to-spanner-with-agentic-interactive-gemini/
- Blog archives: https://blog.gdeltproject.org/2025/06/ · https://blog.gdeltproject.org/2025/07/ · https://blog.gdeltproject.org/2026/04/ · https://blog.gdeltproject.org/2026/10/
- APIs probed: https://api.gdeltproject.org/api/v2/doc/doc · https://api.gdeltproject.org/api/v2/geo/geo · https://api.gdeltproject.org/api/v2/context/context · https://api.gdeltproject.org/api/v2/tv/tv
- Dataset probes: https://data.gdeltproject.org/gdeltv3/gsg_docembed/20261028000000.gsg.docembed.json.gz · https://data.gdeltproject.org/gdeltv5/weblegacy/ngrams/20261028120100.toc.json.gz · https://data.gdeltproject.org/gdeltv3/gfg/alpha/lastupdate.txt · https://data.gdeltproject.org/gdeltv2_cloudvision/lastupdate.txt
- Outage report: https://github.com/CarlosPV-77/world-alert-data/pull/6 ; DOC API IP throttling: https://github.com/dk-forge/talent-intelligence-tracker/issues/246
- BigQuery sandbox: https://docs.cloud.google.com/bigquery/docs/sandbox ; pricing (page did not render): https://cloud.google.com/bigquery/pricing
- Feeds: https://newsapi.org/pricing · https://newsapi.ai/plans · https://gnews.io/pricing · https://newsdata.io/pricing · https://webz.io/pricing · https://www.mediacloud.org/ · https://www.mediacloud.org/legal/media-cloud-terms-of-use · https://commoncrawl.org/blog/news-dataset-available · https://data.commoncrawl.org/crawl-data/CC-NEWS/2026/10/warc.paths.gz · https://gdeltcloud.com/ · https://gdeltcloud.com/acceptable-use · https://acleddata.com/terms-of-use/
- Papers: Hammond & Weidmann 2014 https://doi.org/10.1177/2053168014539924 · Wang et al. 2016 https://doi.org/10.1126/science.aaf6758 · Weidmann 2016 https://doi.org/10.1111/ajps.12196 · Kwak & An 2014 https://doi.org/10.1007/978-3-319-13734-6_22 · Qiao et al. 2017 https://doi.org/10.1155/2017/8180272 · Galla & Burke 2018 https://doi.org/10.1007/978-3-319-96133-0_8 · Keneshloo et al. 2014 https://doi.org/10.1145/2615569.2615698 · Voukelatou et al. 2022 https://doi.org/10.1140/epjds/s13688-022-00315-z · Jin et al. 2020 (RE-NET) https://doi.org/10.18653/v1/2020.emnlp-main.541 · Ye et al. 2024 (MIRAI) https://arxiv.org/abs/2407.01231 · Halterman et al. 2023 (PLOVER/POLECAT) https://doi.org/10.31235/osf.io/rm5dw · Hegre et al. 2019 (ViEWS) https://doi.org/10.1177/0022343319823860 · Fronzetti Colladon & Vestrelli 2026 https://doi.org/10.3390/bdcc10020045 · Leetaru & Schrodt 2013 http://data.gdeltproject.org/documentation/ISA.2013.GDELT.pdf

## Fact-check (2026-10-28)

*Independent re-check run 2026-10-28 PDT (2026-10-29 06:19–06:28 UTC; the report's "2026-10-29" stamps are UTC and consistent).*

**Method:**
- Live curl probes from this machine.
- The GDELT Event Codebook V2.0 PDF, GDELT about and blog pages, official pricing and docs pages, arXiv and OpenAlex.
- Downloaded the 06:15 UTC English batch (872 events, 2,695 mentions, 927 GKG docs, 10,066 GKG locations).
- Range-requested the last 26 MB of both master lists, which covers mid-2024 to now.

**Result:** 8 confirmed, 3 partially true, 1 refuted.

| # | Claim | Verdict | Correction | Source |
|---|---|---|---|---|
| 1 | DOC 2.0 returns HTTP 429 on every call; the message asks for 1 request per 5 s and points to ngrams | Partially true | The message is exact: 429 after about 11 s on 2 of 3 calls, even spaced more than 5 s apart. But 1 call returned HTTP 200 with articles after 23 s. Throttling is heavy and intermittent, not total. "Keep it out of the data path" still holds | https://api.gdeltproject.org/api/v2/doc/doc (probed) |
| 2 | GEO 2.0 returns 404; Visual GKG is frozen at 2022-02-22; Frontpage Graph has emitted 45-byte files since Nov 2025 (234–248 MB in Jan 2024/25) | Confirmed | GEO: 404 at `/api/v2/geo/geo`. Visual GKG: cloudvision `lastupdate.txt` points to `20220222160000.imagetags.csv.gz`. Frontpage Graph: 248 MB (2024-01-15), 235 MB (2025-01-15), 45 B for every sampled hour from 2025-10-31 23:00 to 2026-10-29 06:00. A 2025-10-15 00:00 sample was 5 KB, so sizes varied in October rather than being a steady 145 KB. Context 2.0 works (hits about 3 min old) | https://api.gdeltproject.org/api/v2/geo/geo ; https://data.gdeltproject.org/gdeltv2_cloudvision/lastupdate.txt ; https://data.gdeltproject.org/gdeltv3/gfg/alpha/lastupdate.txt |
| 3 | `lastupdate(-translation).txt` holds 3 lines (size, MD5, URL) every 15 min; master lists are 129/141 MB; plain HTTP returns a 301 to HTTPS; Range is supported; files are published before their stamp | Confirmed | Sizes are 128,989,611 and 141,461,762 bytes, with `accept-ranges: bytes`. The 06:15-stamped EN batch was live by 06:04:46, and 06:30 entries were listed by about 06:21. Manifest URLs are `http://` and get a 301 to `https://` | https://data.gdeltproject.org/gdeltv2/lastupdate.txt ; https://data.gdeltproject.org/gdeltv2/masterfilelist.txt |
| 4 | Events have 61 columns, Mentions 16, GKG 27; legacy NumMentions/NumSources/NumArticles/AvgTone cover only the first 15-min window; NumSources = 1 for about 97–99% of events | Confirmed | Every sampled row has 61/16/27 columns. The codebook says "during the 15 minute update in which it was first seen", and IsRootEvent reflects only the first report. NumSources = 1 in 98.5% of the 872-event EN batch | Event Codebook V2.0 (pp. 5–6); sample files |
| 5 | Geo types 1/2/5 have a blank FeatureID, so "FeatureID present" marks point-precise types 3/4 | **Refuted** | Centroid coordinates are correct, but FeatureID is never blank for types 1–5. Types 1/2 hold text codes (`FR`, `TX`); type 5 holds signed numeric GNS IDs like cities. The codebook contradicts itself. Fixed in §d and recipe step 3: filter on `Geo_Type ∈ {3,4}` | Event Codebook V2.0 (Geo_Type vs Geo_FeatureID notes); `20261029061500` export and GKG |
| 6 | 2026 YTD: 1 EN and 2 TR of 28,921 intervals missing. From 2025-06-14 18:00, 1,665 consecutive intervals (about 17.3 days) were never published, plus about 2.2 h on 06-12 | Confirmed | Exact match. EN gap 2025-06-14 18:00 to 07-02 02:00 (1,665 intervals); TR 1,666 from 17:45. The 06-12 gap ran 18:15–20:15 (2.25 h). The 2026 gaps fall at 2026-05-09 23:15–23:30. There were also 7 one-interval gaps from Jan to May 2025. Caveat: these count manifest entries, and a listed file can still 404 (see the §f correction) | https://data.gdeltproject.org/gdeltv2/masterfilelist.txt ; https://data.gdeltproject.org/gdeltv2/masterfilelist-translation.txt |
| 7 | GKG is about 413/774 MB/day zipped in October and 504/870 MB on 10-27; English averages 435 MB/day in 2026 YTD vs 800 translated (1.9x) | Confirmed | Recomputed from master-list sizes: 413.5/776.1 October average; 503.8/870.2 on 10-27; 434.9/799.8 YTD. The ratio is 1.84 YTD and 1.88 in October. Events are 6.5/5.1 and Mentions 9.2/6.8 MB/day | Master-list size column |
| 8 | Terms of use: "unlimited and unrestricted use" including commercial; redistribute, rehost and mirror with a citation plus a link | Confirmed | Verbatim on the about page. The cited ngram-reconstruction paper is real: Fronzetti Colladon & Vestrelli, *BDCC* 10(2):45, 2026-02-02, "up to 95% text similarity" on 2,211 articles | https://www.gdeltproject.org/about.html ; https://doi.org/10.3390/bdcc10020045 |
| 9 | BigQuery on-demand costs $6.25/TiB (flagged unverified) with 1 TiB/month free; the sandbox needs no card and gives 10 GiB lifetime storage, 60-day expiry, no DML or streaming | Confirmed | The price was verified from the pricing page HTML. The sandbox docs say "lifetime limit of 10 GiB of storage", and also rule out streaming, DML and the Data Transfer Service. Full-history GKG at about 20 TiB costs about $119–125 | https://cloud.google.com/bigquery/pricing ; https://docs.cloud.google.com/bigquery/docs/sandbox |
| 10 | v5 "weblegacy" ngrams plus TOC started 2026-06-30 and are called temporary; the GDELT 5 / Elasticsearch-to-Spanner post is dated 2026-04-18 and gives no dates or schemas | Confirmed | The post says "temporarily releasing" and tells users to switch from the search APIs "for the time being". TOC fields are id, date, img, lang, title, url; ngram rows are DOCID, QUADGRAM, COUNT; per-minute files arrive in 15-min bursts. The GDELT 5 rollout starts with the TV News Explorer, then the Online News Explorer | https://blog.gdeltproject.org/using-the-new-web-ngrams-dataset-to-find-relevant-coverage/ ; https://blog.gdeltproject.org/scaling-gdelt-for-a-new-era-migrating-to-spanner-with-agentic-interactive-gemini/ |
| 11 | Fallback feeds: NewsAPI.org dev tier is 100/day, 24 h delay, no staging or prod, $449/mo; NewsAPI.ai has 2,000 free searches, $90/mo; GNews 100/day, 12 h, non-commercial, €49.99/mo; NewsData.io 200 credits/day, $199.99/mo; Webz.io $5 credits/mo, $0.001/call; GDELT Cloud 200 free calls; CC-NEWS 8–13 WARCs/day of about 1.07 GB | Partially true | All prices and limits are confirmed. Fixes: the NewsData.io free tier is delayed 12 h (48 h is the lookback). CC-NEWS had 8–15 WARCs/day in October 2026 (1.07 GB each is confirmed). Webz.io's $0.001 is the Search API call rate; open-web data feeds cost $0.01 per call | https://newsapi.org/pricing ; https://newsapi.ai/plans ; https://gnews.io/pricing ; https://newsdata.io/pricing ; https://webz.io/pricing ; https://gdeltcloud.com/ ; https://data.commoncrawl.org/crawl-data/CC-NEWS/2026/10/warc.paths.gz |
| 12 | MIRAI: after filtering to ≥50 daily mentions, the best agents scored about 30–33 F1 (2nd level) | Partially true | The F1 range is right: 29.6 on the 705-query test set and 32.6–32.8 for GPT-4o on a 100-query subset. The filter description is wrong: ≥50 mentions builds the database, while test queries need ≥100 daily mentions and ≥5 articles | https://arxiv.org/abs/2407.01231 |

**New operational finding, for the ingester design (§g step 1).** A file can be listed with size and MD5 in `lastupdate-translation.txt` and the master list, yet return 404 while its sibling files are live. `20261029061500.translation.export.CSV.zip` was 404 from 06:21 to at least 06:28 UTC. The poller should therefore:
- Retry each file on its own, with backoff.
- Mark an interval complete only after all three files pass the MD5 check.

**Not re-checked; treat as single-day measurements:**
- 22.8% duplicate EN titles.
- 1,880 events on the US centroid.
- About 340k GKG articles and 193k events/day.
- The GKG location-precision table.
- The Mentions Confidence medians.
- The 2026 BigQuery TB estimates.
- The literature claims other than MIRAI.

**Spot-checks on the 06:15 batch were consistent with the report:**
- `PAGE_TITLE` present in 100% of GKG docs.
- `SharingImage` present in 86.8%.
- 10 events on the US centroid (39.828175, -98.5795).
- Countries, US states and ADM1 together are 36% of events.
