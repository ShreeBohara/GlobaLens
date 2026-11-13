# GlobaLens 3.0: Complementary Data Layers and News-Content Legal Guardrails

Research date: 2026-10-28. Scope: (1) open data layers to fuse with news into a "living planet" view; (2) copyright, crawling norms and privacy for a public portfolio project.

**Confidence tags:** **[V]** checked this session against a primary page (official docs, terms, statute text). **[S]** secondary source (Wikipedia, third-party docs, community reports). **[M]** from memory, *not* re-checked this session. **Method note:** the shared WebSearch budget ran out partway through. After that I only fetched official pages directly. IODA's site failed TLS. HDX HAPI docs and OpenSky's terms page returned 403. Those rows are marked accordingly.

---

## TL;DR

- **GDELT stays the backbone, and the legal case for it is clean.** Its terms allow unlimited use, including commercial use and redistribution, as long as you cite and link [V].
- **ACLED is effectively unavailable to a solo developer on gmail.** Generic emails get the *Open* tier, which has **no API**, and the terms restrict "secondary products or effective substitutes" [V]. **Use UCDP instead**: CC BY 4.0, monthly candidate events with ≤1-month lag, 5,000 requests a day with a free token [V].
- **Layers with high impact and no key (or a free key):** USGS (updated every minute), GDACS, EONET, FIRMS, NASA GIBS daily imagery, Wikipedia pageviews (CC0). Ship them early.
- **Non-commercial-only feeds:** OpenSky, the Open-Meteo free tier, Cloudflare Radar (CC BY-NC), Global Fishing Watch, EOX cloudless. Fine for a portfolio, but build a **license-aware pipeline** that can switch them off.
- **Legal posture: be a search engine, not a clipping service.** Store metadata, embeddings and short derived facts, never full text. Write AI syntheses **per event, across multiple sources**, with citations and outbound links. Respect robots.txt and AI opt-outs. Never get around paywalls or bot blocks. Keep attribution visible.
- **EU AI Act Art. 50(4)** has applied since 2 Aug 2026: label AI-generated public-interest text [V].
- **Product direction:** build a **"Coverage Gap" engine** that compares severity (hazards, fatalities, outages) with attention (GDELT volume, Wikipedia pageviews). It makes "See beyond the headlines" measurable.

---

## Part 1: "Living planet" layers

### 1.1 Hazards and environment

| Source | Provides | Freshness | Access / limits | License / terms | In GlobaLens | Verdict |
|---|---|---|---|---|---|---|
| **USGS Earthquakes** | GeoJSON feeds for the past hour/day/7d/30d × (significant, M4.5+, M2.5+, M1+, all) | "Updated every minute" [V] | No key | Data from the US Government, open [M] | Pulsing rings sized by magnitude. Auto-links to news clusters within a radius and time window | **Must, early** |
| **GDACS** (UN + EC) | Multi-hazard alerts (EQ, TC, FL, VO, DR, WF) with green/orange/red levels | Near-real-time | No auth. SEARCH returns ≤100 events per call [S] | Free with acknowledgement "Global Disaster Alert and Coordination System, GDACS". Automated alerts are *not human-reviewed*, provided "as is" [S] | **Severity spine** for the Coverage Gap index. Cyclone cones | **Must, early** |
| **NASA EONET v3** | Curated natural events in 13 categories (wildfires, severeStorms, volcanoes, floods, seaLakeIce, …) [V] | Near-real-time | No key. Filter by status, days, bbox, category [S] | NASA open data [M] | Event markers with tracks (storms) | **Must, early** |
| **NASA FIRMS** | Active fire hotspots from VIIRS (SNPP/NOAA-20/NOAA-21), MODIS and Landsat (US/Canada) [V] | NRT, about 3 h after overpass [M] | Free MAP_KEY. **5,000 transactions per 10 min**. Area endpoint covers **1–5 days** per query, CSV, bbox or "world" [V] | NASA open data, cite FIRMS [M] | H3 hexbin heat layer. Fire radiative power feeds severity | **Must** |
| **NWS alerts** (US only) | Watches and warnings as GeoJSON/CAP | Live | **User-Agent with contact required**. An API key is planned. Rate limit undisclosed but "generous" [V] | "Intended to be open data, free to use for any purpose" [V] | US alert polygons. Optional, since GDACS covers the globe | Could |
| **Open-Meteo** | Forecasts, historical weather, air quality | Hourly | Free tier: **<10k calls/day, 5k/h, 600/min, non-commercial only** [V] | Data CC BY 4.0, "Weather data by Open-Meteo.com" [V] | On-demand weather context in the event drawer, cached. Not a global layer | Should |
| **NASA GIBS** | 1,000+ daily imagery layers (MODIS/VIIRS true color, aerosols, …) via WMTS/WMS/XYZ in EPSG:4326 and 3857, with a time dimension (`YYYY-MM-DD`) [V] | Daily. Current day may be incomplete [V] | Docs mention no key requirement [V] | NASA open data [M] | **"Satellite day" time scrubber.** See the smoke plume on the day of the news | **Must** (wow per line of code) |
| **Copernicus Data Space (Sentinel-1/2/3/5P)** | Raw and processed EO, STAC, OData, Sentinel Hub | Days (revisit) | Free: **10k Sentinel Hub requests and 10k processing units per month**, 300 requests/min and 300 PU/min [V]. **[corrected: the quota table lists no Sentinel Hub concurrency cap. The "2 concurrent" limit belongs to openEO API requests and openEO/Data Workspace processing]**. S3/OData/STAC: 2,000 req/min, 4 concurrent connections, 20 MB/s per connection, 12 TB per rolling 30 days [V] | Free, full and open. Credit "Contains modified Copernicus Sentinel data [year]" [M] | On-demand **before/after chips** for the top events, cached in object storage | Later |
| **EOX Sentinel-2 cloudless** | Beautiful cloud-free mosaics | Yearly | WMTS | **CC BY-NC-SA 4.0 for non-commercial use. Commercial use needs a paid EOX license** [V] | Base imagery only if the project stays non-commercial | Avoid. Use GIBS or Blue Marble |
| **OpenAQ v3** | Air quality stations | Near-real-time | v1/v2 **retired 31 Jan 2025** (410 Gone) [V]. Key and limits not verified | Per-provider terms apply [V] | Pollution context | Could |

### 1.2 Conflict and humanitarian

| Source | Access reality (2025–2026) | License / terms | GlobaLens use | Verdict |
|---|---|---|---|---|
| **ACLED** | myACLED tiers: Open / Research / Partner / Enterprise, assigned **by email domain**. **Generic emails such as gmail get Open, which has no API** [V]. Research adds API access and aggregated data, with event data **lagged 12 months** [S] *(fact-check: the FAQ confirms API access and time-lagged event data for Research, but gives no lag length, so "12 months" is unverified)*. Key-based API ended 15 Sep 2025 and was replaced by OAuth tokens [V]. Community reports say generic domains can't get extended access [S] | Restricts "monetizing products" and "generating secondary products or effective substitutes". Strict attribution [V] | A live ACLED layer is basically impossible for a solo developer, and a substitute-style map breaches its terms | **Avoid**. At most, use country-month aggregates via HDX for context after reading the terms |
| **UCDP** (Uppsala) | Free API. **Token by email, introduced Feb 2026** [S] *(fact-check: the API docs confirm the token requirement but give no start date)*. **5,000 req/day**, and errors count toward it [V]. Versioned endpoints (GED 26.1, Candidate 26.0.9) [V] | **CC BY 4.0**. Cite the dataset papers [V] | **Conflict layer**: GED Candidate is monthly with ≤1-month lag [V]. Also **ground truth to evaluate** event detection on GDELT | **Must (conflict)** |
| **GDELT 2.0** (Events, GKG, DOC/GEO APIs) | 15-minute updates, BigQuery public dataset [M] | Unlimited use, including commercial and redistribution. Cite and link [V] | Backbone: daily conflict and protest *signals* | **Must** |
| **ReliefWeb (OCHA)** | v2 API. **Pre-approved appname required since 1 Nov 2025**. Unapproved names get 403 [V/S]. v1 decommissioned [S] | Reports may contain material owned by the original source, and users must respect those rights [V] | Link out to situation reports. Store metadata only | Should |
| **HDX HAPI** | Beta. Standardised humanitarian indicators at admin0/1/2 [V]. Endpoint detail not verified (docs returned 403) | HAPI Terms of Use, plus each source's license [V] | Country dossiers (displacement, food security, funding) | Should (verify endpoints) |

### 1.3 Mobility and infrastructure

| Source | Access / limits | License / terms | GlobaLens use | Verdict |
|---|---|---|---|---|
| **OpenSky Network** | **OAuth2 client credentials only. Basic auth "no longer accepted"** [V] (retired around March 2026 [S]). Credits per day: anonymous 400, standard 4,000, feeder 8,000. Licensed users get 14,400/hour. `/states/all` costs 1–4 credits by bbox area. 5 s resolution. 1 h history [V] | Licensed for **non-profit research, education, government and commercial internal testing** [S, possibly outdated copy] | Global snapshot about every 86 s on a standard account (4,000 ÷ 4) | Could (non-commercial). Prefer adsb.lol for public display |
| **adsb.lol** | No key today. **A key is "required in the future"**, earned by feeding. Drop-in replacement for the ADSBx RapidAPI. Load-based limits [V] | Data ODbL per community sources [S]. Code BSD-3 [V]. Annual history dumps on GitHub [S] | Airspace closures over conflict zones. Stretch: **GPS-jamming hex map** from the NIC/NACp fields (readsb format [M]) | Should (Phase 7–8) |
| **airplanes.live** | No SLA | **Non-commercial** [S] | n/a | Avoid |
| **aisstream.io** | WebSocket. **Server-side only** (no browser connections). **3 subscribed connections per account and 3 per IP**. ≤200 MMSI filters per subscription. **[corrected: the docs set no bbox cap, but they don't promise "unlimited" either. At least one bbox is required per subscription]**. **No SLA, no replay**. From **Sep 2026, uncompressed connections get per-user bandwidth caps**, so use permessage-deflate [V] | Data-use terms not stated on the docs page [V] | **"Chokepoint Watch"**: ship counts and anomalies through Hormuz, Bab-el-Mandeb, Suez, Malacca, Panama, Bosporus and the Taiwan Strait | Should (Phase 7) |
| **Global Fishing Watch** | API (events such as fishing, encounters, AIS gaps, port visits) | **Non-commercial only. No public commercial terms** [V] | "Dark vessel" gap events near conflict or EEZ hotspots | Could |
| **Cloudflare Radar** | API is "free" [V]. Token required, with the Account > Radar > Read permission [V, fact-check] | **CC BY-NC 4.0** [V] | **Internet blackout layer**. Shutdowns line up with protests, coups and elections | **Should** |
| **IODA** (Georgia Tech) | Public dashboard and API with BGP, active-probing and telescope signals [M] | Unverified (TLS failure) | Cross-check for Radar | Could (verify terms) |

### 1.4 Knowledge, attention and geography

| Source | Access / limits | License | GlobaLens use | Verdict |
|---|---|---|---|---|
| **Wikimedia APIs** (2026 global limits) | **10 req/min unidentified. 200/min with a compliant User-Agent** (contact email or URL). 2,000/min for established editors. Bots and WMCS exempt. Respect 429 and Retry-After [V]. Rollout finished June 2026 [S, confirmed by Tech News 2026-25]. Also keep **≤3 concurrent requests**. The limits are labelled new in 2026 and subject to change. Automated dumps downloads (e.g., pageview files) need a valid User-Agent from end of June 2026 [V, fact-check] | n/a | Always send `User-Agent: GlobaLens/3.0 (+url; email)` | Constraint |
| **Wikipedia pageviews** | Per-article and top-1000 per day. 1–2 day lag [S] | **CC0** ("All Analytics datasets… CC0") [V] | **Attention signal**, one input to the Coverage Gap index. Trending entities | **Must** |
| **Wikidata** | SPARQL. **Graph split on 9 May 2025**: scholarly content now lives at query-scholarly. Blazegraph backend unmaintained since 2017 [S] | CC0 [M] | Canonical **entity IDs (QIDs)** for entity linking. Use dumps or the entity API, not heavy SPARQL | **Must** |
| **Current Events portal** | Daily curated wiki pages, parsed via the API | CC BY-SA 4.0 [M] | **Labelled evaluation set** for event clustering, plus an "editor-curated" layer that only links out | Should |
| **Wikimedia Enterprise** | Free: **50k on-demand requests per month**, monthly snapshots, no realtime [V] | Per-response license metadata | Clean article and abstract retrieval for entity cards | Could |
| **GeoNames** | API: **10k credits/day, 1k/hour**, username required. **Daily dumps** (allCountries.zip) [V] | CC BY (version not stated on the page). Commercial OK [V] | **Offline gazetteer**. The API quota can't keep up with news volume, so use the dump | **Must (dump)** |
| **Natural Earth** | Downloads | **Public domain. Attribution "unnecessary"** [V] | Country and admin-1 polygons at low zoom. Choropleths | **Must** |
| **Overture Maps** | GeoParquet. Monthly releases [M] | Divisions, base, buildings and transportation are **ODbL**. Places are **CDLA-Permissive 2.0** (Foursquare Apache-2.0) [V] | Admin hierarchy and GERS IDs for geocoding enrichment | Later. Watch **ODbL share-alike** if you publish derived databases |
| **Protomaps** | Daily planet PMTiles builds, about **120 GB** at z0–15. `pmtiles extract --maxzoom` for cutouts. Hotlinking discouraged [V] | ODbL Produced Work. OSM attribution required [V] | Self-host a z0–8 extract on R2/S3. One static file, no tile server | **Must (pick this or OpenFreeMap)** |
| **OpenFreeMap** | **No keys, no limits, commercial OK**, weekly planet, MIT-licensed stack. Donation-funded, no SLA [V] | "OpenFreeMap © OpenMapTiles Data from OpenStreetMap" [V] | Zero-ops vector basemap for MapLibre | Good default, with Protomaps as fallback |

### 1.5 Economics, markets and expectations

| Source | Access / limits | Terms | GlobaLens use |
|---|---|---|---|
| **World Bank Indicators** | No key [S] | CC BY 4.0 default [V] | Country dossier (GDP, population) |
| **IMF** | New SDMX 2.1/3.0 API at api.imf.org, no key [S]. **Legacy dataservices.imf.org retired around Nov 2025** [S, single source]. IFS split into thematic flows [S] | IMF terms [M] | WEO forecasts in dossiers. Don't copy old tutorials |
| **Our World in Data** | Append `.csv`, `.metadata.json` or `.zip` to any grapher URL [V] | CC BY 4.0 [V] | Long-run context charts |
| **FRED** | Free key. Must show "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis". **Third-party copyrighted series need the owner's permission beyond personal use**. No apps that "replicate FRED" [V] | Restrictive | Macro sparklines. Skip copyrighted series |
| **Frankfurter** | **No key, no quotas** (rate-limited). Daily rates from 106 central banks [V] | Blended rates free for commercial use [V] | FX shocks (e.g., currency collapse with protest news) |
| **CoinGecko Demo** | **100 calls/min, 10k/month**, attribution required. Basic plan $35/mo [V] | Attribution | Crypto as a sanctions or capital-flight signal (batch and cache) |
| **Alpha Vantage** | **25 requests/day** free. $49.99/mo for 75/min [V] | Personal-use limits on some feeds [V] | Too small for live use. End-of-day only |
| **Polymarket** | Gamma: `/markets` 300 req/10 s, `/events` 500/10 s. CLOB `/prices-history` 1,000/10 s. IP-based and throttled rather than rejected [V]. Public reads need no auth [M] | Check the ToS before launch [M] | **"Market-implied odds" chips** on story clusters, with probability timelines next to news volume |
| **Kalshi** | **Public endpoints need no key** (series, markets, events, orderbook) at `external-api.kalshi.com/trade-api/v2`. WebSocket needs auth [V] | Check the ToS [M] | Same as Polymarket. A CFTC-regulated contrast |
| **Manifold** | Reads need no auth. **500 req/min per IP**. WebSocket. API is alpha [V] | **Commercial AI/ML training on API data needs a license** [V] | Play-money long-tail questions |

Take care with framing: present prediction markets as "crowd expectations", not betting. Never add affiliate or trading links.

### 1.6 Capacity math: what the free tiers actually buy

- **OpenSky:** a global snapshot costs 4 credits, so 4,000/day gives one every ~86 s (anonymous: every ~14 min) [V-derived].
- **FIRMS:** 5,000 transactions per 10 min is plenty. Poll every 15–30 min to match NRT latency.
- **GeoNames API:** 10k/day can't keep up with GDELT's volume. GDELT already ships GeoNames/GNS-coded locations, so use the **dump**.
- **CoinGecko:** 10k/month is about 333 calls a day. One batched call every 5 min fits.
- **Copernicus:** about 1 PU per 512² chip [M], so thousands of cached before/after chips a month.
- **AIS:** one compressed connection can cover about 8 chokepoint bboxes, within the 3-connection cap.

### 1.7 What this should change about the product

1. **Coverage Gap Index (signature analytic).** Score each region per day: *severity* (GDACS level, UCDP fatalities, FIRMS fire radiative power, Radar outage magnitude, ReliefWeb report volume) divided by *attention* (GDELT article count, cross-language spread, Wikipedia pageviews). The Lens lights up "neglected crises". It is legally clean (metadata only), ML-heavy (normalisation, anomaly baselines) and literally "beyond the headlines".
2. **Event fusion engine.** Join sensor events (quake, fire cluster, outage, AIS anomaly, market jump) to news clusters by H3 cell × time window. Measure **lead/lag**, meaning which signals precede coverage.
3. **License-aware provenance.** Every record carries `source`, `license`, `attribution` and `commercial_ok`. The UI generates the attribution footer automatically. A `COMMERCIAL_MODE` flag drops NC sources. A CI test fails if a new source lacks a license entry. This is rare, senior-level polish.
4. **Ground-truth evaluation.** Use UCDP Candidate events and Current Events portal entries as labelled data. Publish event-detection precision and recall in the README.

---

## Part 2: Legal

### 2.1 Cases that shape the design

| Case | Status | Lesson for GlobaLens |
|---|---|---|
| **AP v. Meltwater** (SDNY 2013) | A clipping service excerpting 4.5–60% of articles, including the lede, was **not fair use**. It substituted for reading the articles and was closed to the public. **Not blocking via robots.txt ≠ implied license** [S] | Don't serve excerpts that substitute for the article. robots.txt "allow" is not permission to republish |
| **NYT v. Microsoft & OpenAI** (SDNY MDL, Judge Stein) | Motion to dismiss largely denied Mar/Apr 2025. Claims narrowed. Several publisher suits consolidated. No merits ruling found [S] | Full-text storage and regurgitation are the core theory |
| **Advance Local / Condé Nast et al. v. Cohere** (SDNY) | Filed Feb 2025 by 14 publishers over training and **displaying substantial portions or entire articles** [S]. Nov 2025 ruling let claims over **"substitutive summaries"** and false attribution proceed [M] | **AI summaries can infringe** when they track the article's expression |
| **Perplexity suits** | Dow Jones/NY Post (2024; includes *hallucinated quotes* and brand harm). Britannica (Sep 2025; Sept 2026 discovery orders on its RAG system). **Reddit (Oct 2025; July 2026 motions to dismiss largely denied, DMCA and conspiracy claims proceed)**. **CNN (May 2026; 17,000 works and false attribution)**. Yomiuri, Asahi, Nikkei (Aug 2025) [S] | RAG answers, scraping workarounds and **misattribution (trademark)** are all live theories |
| **Thomson Reuters v. Ross** | Feb 2025: copying for a *non-generative* competing tool was not fair use. **Third Circuit affirmed, Sept 2026** [S, single source] | "It's only for search or embeddings" is no shield when the product competes with the source |
| **Bartz v. Anthropic / Kadrey v. Meta** (N.D. Cal., June 2025) | Training on lawfully acquired books was fair use. Pirated copies were not. Settlement of $1.5B, approved July 2026. Meta won narrowly on lack of market-harm evidence [S] | How you acquire content matters. Never use pirated or paywall-bypassed copies |
| **GEMA v. OpenAI** (Munich, 11 Nov 2025) | Memorised lyrics reproduced in outputs infringed [S] | Outputs must not reproduce source text |
| **The Intercept v. OpenAI** (SDNY, Nov 2024) | DMCA §1202 claim for **removing copyright management info** survived [M] | Keep bylines, publisher names and links on every item |

The background rules are stable [M]: facts are not copyrightable (*Feist*), short phrases and headlines generally aren't either (37 CFR 202.1(a)), and *Authors Guild v. Google* (2d Cir. 2015) blessed full-text indexing plus snippets plus links for search. *Barclays v. TheFlyOnTheWall* (2d Cir. 2011) narrowed "hot news" misappropriation.

### 2.2 Crawling and AI-preference norms, 2025–2026

- **robots.txt (RFC 9309)** governs *access* only [M]. Disobeying it is not illegal by itself, but it is evidence of bad faith and triggers blocks.
- **Cloudflare** has blocked AI crawlers by default since **1 Jul 2025** ("Content Independence Day"). **[corrected: the post gives no crawl-to-referral ratios. Its 750 (OpenAI) and 30,000 (Anthropic) figures say how many times harder it is to get traffic than it was from Google a decade ago]** [V]. Expect many publisher sites to block unknown bots.
- **Content Signals Policy** (Cloudflare, 24 Sep 2025) adds `Content-Signal: search=yes, ai-input=…, ai-train=no` in robots.txt. Over 3.8M managed domains default to `search=yes, ai-train=no` with **ai-input left unset**. It is framed as an **EU DSM Art. 4 reservation of rights** [V]. GlobaLens's LLM summarisation counts as **ai-input**.
- **IETF AIPREF**: `draft-ietf-aipref-vocab-08` (13 Sep 2026) and `-attach-05` (18 Aug 2026) are still Internet-Drafts, not RFCs [V]. Build the parser to be pluggable.
- **RSL 1.0** ("Really Simple Licensing") is backed by Cloudflare, Akamai, Fastly, Reddit, Yahoo, Ziff Davis and People Inc. It lets sites declare free, attribution, pay-per-crawl or pay-per-inference terms [V]. Honor `free`/`attribution` and skip paid terms.
- **EU DSM Art. 4** text-and-data-mining exception yields to machine-readable opt-outs. **Art. 15** press publishers' right exempts only "individual words or very short extracts" and hyperlinks [M].
- **Common Crawl / CC-NEWS** grants **no rights in the underlying content**, and users indemnify Common Crawl, explicitly including AI training [V]. It is not a licensing shortcut.

### 2.3 Risk ladder for content practices

| Practice | Risk | Rule |
|---|---|---|
| Store URL, headline, publisher, time, language, GDELT GKG themes, entities, tone, locations | **Low** | Default storage model |
| Publisher-supplied RSS/OG description, ≤~200 characters, with link | Low–moderate | Show it, never extend it |
| Fetch body text → compute embeddings and entities → **discard text** (TTL ≤24 h) | Unsettled, moderate | Only where robots.txt and Content-Signal allow, and `ai-input` is not "no". Never behind a paywall |
| Persist full article text | **High** | **Never** |
| Per-article AI summary shown publicly | **Moderate–high** (Cohere, Perplexity) | **Don't** |
| Multi-source **event** synthesis: factual, ≤120 words, cites 3+ outlets, links out | Low–moderate | Allowed, with guardrails (2.5) |
| Quotes attributed to outlets in AI text | **High** (false attribution) | **No quotes** in AI output |
| Bypass paywalls, rotate IPs or spoof user agents | **High** (DMCA §1201, Reddit v. Perplexity) | **Never** |
| Strip bylines or copyright notices | Moderate (DMCA §1202) | Always attribute |

### 2.4 EU AI Act transparency

**Art. 50(4)** applies from **2 Aug 2026**. Deployers publishing AI-generated text "with the purpose of informing the public on matters of public interest" must disclose that it is AI-generated. The exception is human review or editorial control *plus* someone holding editorial responsibility [V]. Art. 50(2) machine-readable marking gives pre-existing generative systems until **2 Dec 2026** [V]. *(Fact-check: that date comes from Art. 111(4), inserted by Regulation (EU) 2026/1744, the Digital Omnibus on AI, published in the OJ on 24 Jul 2026.)* A personal, non-professional activity carve-out may apply to a hobby site [M], but labelling costs nothing. Ship an **"AI-generated from N sources" badge** and a methods page.

### 2.5 Content policy to encode in the pipeline (Phase 1 ADR)

1. **Crawler identity:** `GlobaLensBot/3.0 (+https://…/bot; email)`. Rate limit per host. Cache robots.txt for 24 h. Parse Content-Signal, TDM-Rep and RSL. Default to **deny on ambiguity**.
2. **Ingestion tiers:** Tier 0 is metadata only (GDELT, RSS). Tier 1 is a transient fetch for embeddings and NER, only where allowed. Tier 2, full-text retention, does not exist.
3. **AI guardrails:** event-level only. Every sentence grounded in ≥1 cited source. **Automatic n-gram overlap check** (reject if an 8-word or longer span matches a source). No quotes. Mandatory source chips and "read the original" links. Show an uncertainty flag when sources disagree.
4. **Publisher controls page:** opt-out form and email, honored within 72 h, with a per-domain denylist in config. A DMCA-style takedown process. If user-generated content is ever added, register a DMCA §512 agent [M].
5. **Attribution and licenses page**, generated from the provenance table. Examples: "Contains modified Copernicus Sentinel data 2026", "© OpenStreetMap contributors", the FRED notice, "Weather data by Open-Meteo.com", "UCDP (CC BY 4.0)", "GDELT Project".
6. **Disclaimer:** not a news publisher, no warranty, hazard data "as is" (GDACS terms). Not for safety-of-life decisions.

### 2.6 Data protection if accounts are added

- **Applicability:** GDPR reaches non-EU sites that serve people in the EU [M]. CCPA applies only above **$26.625M revenue (from 1 Jan 2025)**, 100k California consumers, or ≥50% of revenue from selling data [V]. GlobaLens is far below all three, but follow the spirit.
- **Minimise:** passwordless or OAuth sign-in. Store only email, watchlists and alert rules. No precise location.
- **AI chat logs are personal data:** 30-day retention, user deletion, no training on them, LLM sub-processors disclosed [M].
- **Rights as features:** one-click JSON **export** and **hard delete**. Honor Global Privacy Control.
- **Cookies and security:** cookieless analytics (Umami or Plausible) avoid a consent banner [M]. Row-level security, a 72-hour breach runbook, an age gate at 16+, and double opt-in with one-click unsubscribe for email alerts.

---

## Recommendations for GlobaLens 3.0

Phases assume a 10-phase arc: P1 foundations, P2 ingestion, P3 globe/Lens, P4 search, P5 events+AI, P6 layer fusion and time, P7 streaming, P8 ML and analytics, P9 accounts, alerts and agent, P10 scale and launch. Remap if the master plan differs.

1. **(Must, P1) A content and data policy ADR plus a provenance schema** (`source`, `license`, `attribution`, `commercial_ok`, `ingest_tier`) before any ingestion code. A CI check blocks unlicensed sources.
2. **(Must, P2) GDELT plus RSS metadata as the only article inputs.** No full-text persistence. GeoNames dump, Natural Earth and Wikidata QIDs for geo and entity resolution.
3. **(Must, P3) Launch the "living planet" with USGS, GDACS, EONET and FIRMS.** Basemap from OpenFreeMap or a self-hosted Protomaps extract.
4. **(Must, P5) UCDP GED Candidate instead of ACLED** for conflict, plus GDELT for daily signals. UCDP and the Current Events portal double as the **evaluation set**.
5. **(Must, P5) AI syntheses per event only:** citations, n-gram overlap rejection, no quotes, "AI-generated" label.
6. **(Should, P6) GIBS time scrubber, Open-Meteo context, ReliefWeb links** (apply for an appname early, since approval is manual), and HDX, World Bank, IMF and OWID dossiers.
7. **(Should, P7) Streaming:** aisstream Chokepoint Watch, adsb.lol airspace, Cloudflare Radar outages, prediction-market odds on clusters.
8. **(Should, P8) Coverage Gap Index and lead/lag fusion** as the flagship ML feature, plus FRED, Frankfurter and CoinGecko market sparklines.
9. **(Should, P9) Privacy by design for accounts** (2.6).
10. **(Could, P10) Copernicus before/after chips, Overture enrichment** (mind ODbL), a publisher controls page and a generated licenses page.
11. **Avoid:** ACLED event data, EOX cloudless, airplanes.live, Alpha Vantage for live use, scraping finance or social sites, any paywall or bot-block workaround.

---

## Sources

**Hazards and environment:** https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php · https://data.gdacs.org/Documents/2025/GDACS_API_quickstart_v1.pdf · https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf · https://www.gdacs.org/Alerts · https://eonet.gsfc.nasa.gov/docs/v3 · https://eonet.gsfc.nasa.gov/api/v3/categories · https://firms.modaps.eosdis.nasa.gov/api/area/ · https://firms.modaps.eosdis.nasa.gov/api/ · https://appliedsciences.nasa.gov/sites/default/files/2025-05/Part%203%20FIRMS%202025%20Q&A%20Session.docx.pdf · https://www.weather.gov/documentation/services-web-api · https://open-meteo.com/en/terms · https://open-meteo.com/ · https://nasa-gibs.github.io/gibs-api-docs/access-basics/ · https://documentation.dataspace.copernicus.eu/Quotas.html · https://cloudless.eox.at/documentation/license · https://docs.openaq.org/about/about

**Conflict and humanitarian:** https://acleddata.com/myacled-faqs · https://acleddata.com/api-documentation/getting-started · https://acleddata.com/attributionpolicy · https://github.com/koala73/worldmonitor/issues/290 · https://ucdp.uu.se/apidocs/ · https://ucdp.uu.se/downloads/ · https://hdx-hapi.readthedocs.io/en/latest/ · https://docs.humdata.org/about/hdx-signals/datasets/armed-conflict · https://apidoc.reliefweb.int/ · https://apidoc.reliefweb.int/parameters · https://groups.google.com/g/rw-api-dev/c/9gHsMK4HF6M · https://www.gdeltproject.org/about.html

**Mobility and infrastructure:** https://openskynetwork.github.io/opensky-api/rest.html · https://zenodo.org/records/6325961/files/LICENSE.txt?download=1 · https://github.com/mp3pintyo/Crucix/pull/11 · https://github.com/adsblol/api · https://flyitalyadsb.com/en/dati/confronto/ · https://aisstream.io/documentation · https://globalfishingwatch.org/faqs/can-i-use-global-fishing-watch-apis-for-commercial-purposes/ · https://developers.cloudflare.com/radar/

**Knowledge and geography:** https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits · https://diff.wikimedia.org/2026/06/15/tech-news-2026-issue-25/ · https://dumps.wikimedia.org/other/pageviews/readme.html · https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/WDQS_graph_split · https://enterprise.wikimedia.com/pricing/ · https://www.geonames.org/export/ · https://www.naturalearthdata.com/about/terms-of-use/ · https://docs.overturemaps.org/attribution/ · https://docs.protomaps.com/basemaps/downloads · https://openfreemap.org/

**Economics and markets:** https://datacatalog.worldbank.org/dataset/atlas-sustainable-development-goals-2018-world-development-indicators · https://betadata.imf.org/en/Resource-Pages/IMF-API · https://stockmarketstack.com/tools/imf-data · https://owid-docs.readthedocs.io/projects/etl/api/chart-api/ · https://fred.stlouisfed.org/docs/api/terms_of_use.html · https://frankfurter.dev/ · https://www.coingecko.com/en/api/pricing · https://www.alphavantage.co/premium/ · https://docs.polymarket.com/quickstart/introduction/rate-limits · https://docs.kalshi.com/getting_started/quick_start_market_data · https://docs.manifold.markets/api

**News corpora:** https://commoncrawl.org/terms-of-use · https://www.mediacloud.org/

**Legal and policy:** https://en.wikipedia.org/wiki/Associated_Press_v._Meltwater_U.S._Holdings,_Inc. · https://en.wikipedia.org/wiki/Artificial_intelligence_and_copyright · https://en.wikipedia.org/wiki/Bartz_v._Anthropic · https://en.wikipedia.org/wiki/Perplexity_AI · https://en.wikipedia.org/wiki/Cohere · https://en.wikipedia.org/wiki/OpenAI · https://artificialintelligenceact.eu/article/50/ · https://artificialintelligenceact.eu/implementation-timeline/ · https://datatracker.ietf.org/wg/aipref/documents/ · https://blog.cloudflare.com/content-signals-policy/ · https://blog.cloudflare.com/content-independence-day-no-ai-crawl-without-compensation/ · https://rslstandard.org/ · https://cppa.ca.gov/faq.html

---

## Fact-check (2026-10-28)

**Method.** I tried to refute each claim against its primary page using WebFetch. The shared WebSearch budget was already used up, so no search-engine results were used. EUR-Lex returned an empty page, so the amended AI Act wording comes from the AI Act Explorer and the adoption status from the European Parliament's Legislative Observatory. Partially true items are corrected inline above with **[corrected: ...]**. Inline *(fact-check: ...)* notes add detail without changing the claim.

| # | Claim | Verdict | Correction / note | Source |
|---|---|---|---|---|
| 1 | GDELT allows unlimited use, including commercial use and redistribution, if you cite and link | **Confirmed** | None. Any use or redistribution must cite the GDELT Project and link to gdeltproject.org | https://www.gdeltproject.org/about.html |
| 2 | ACLED: generic emails (gmail) get Open myACLED, which has no API. Key-based API ended 15 Sep 2025, replaced by OAuth tokens | **Confirmed** | None. Cookie auth is also offered for browser access. Research gets API access and *lagged* event data, but the FAQ gives no lag length, so "12 months" is unverified | https://acleddata.com/myacled-faqs |
| 3 | UCDP: CC BY 4.0. Free API with a token, 5,000 req/day. GED 26.1 and Candidate 26.0.9. Candidate is released monthly with ≤1-month lag | **Confirmed** | None. Errors count toward the daily limit. Quarterly candidate builds (e.g., 26.01.26.09) also exist. The "Feb 2026" token start date is not on the docs page | https://ucdp.uu.se/apidocs/ · https://ucdp.uu.se/downloads/ |
| 4 | NASA FIRMS: free MAP_KEY with 5,000 transactions per 10 min. Area API takes 1–5 days per query, as CSV | **Confirmed** | None. Requests that span more days can count as several transactions | https://firms.modaps.eosdis.nasa.gov/api/area/ |
| 5 | Non-commercial feeds: the Open-Meteo free tier (<10k/day, 5k/h, 600/min, non-commercial only, CC BY 4.0) and Cloudflare Radar (free API, data CC BY-NC 4.0) | **Confirmed** | None. Open-Meteo requires a "Weather data by Open-Meteo.com" link wherever its data appears. Radar needs an API token with Account > Radar > Read (this was [M] before) | https://open-meteo.com/en/terms · https://open-meteo.com/en/licence · https://developers.cloudflare.com/radar/ · https://developers.cloudflare.com/radar/get-started/first-request/ |
| 6 | OpenSky: OAuth2 client credentials only, Basic auth no longer accepted. Daily credits: 400 anonymous, 4,000 standard, 8,000 feeder. Licensed users get 14,400 per hour. `/states/all` costs 1–4 credits by bbox area. Authenticated users get 5 s resolution and 1 h of history | **Confirmed** | None. Anonymous users get 10 s resolution and only the latest state vectors. States, tracks and flights each have separate quotas. Tokens expire after 30 min | https://openskynetwork.github.io/opensky-api/rest.html |
| 7 | aisstream.io: server-side only. 3 subscribed connections per account and 3 per IP. ≤200 MMSI. No SLA or replay. Bandwidth caps on uncompressed connections from Sep 2026. "Unlimited bboxes" | **Partially true** | The docs set no bbox cap, but they don't promise "unlimited" either. A bbox is required on every subscription. Everything else is confirmed | https://aisstream.io/documentation |
| 8 | Wikimedia API limits (2026): 10/min unidentified, 200/min with a compliant User-Agent, 2,000/min for established editors, bots and WMCS exempt. Rollout finished June 2026 | **Confirmed** | None. Also keep ≤3 concurrent requests. The limits are labelled new in 2026 and subject to change. Automated dumps downloads need a valid UA from end of June 2026 | https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits · https://diff.wikimedia.org/2026/06/15/tech-news-2026-issue-25/ |
| 9 | Basemaps: OpenFreeMap needs no keys, has no limits, allows commercial use, uses an MIT stack, updates the planet weekly and has no SLA. The Protomaps planet is about 120 GB at z0–15, with daily builds. Hotlinking is discouraged. ODbL Produced Work | **Confirmed** | None. Each extra Protomaps zoom level roughly doubles the file size | https://openfreemap.org/ · https://docs.protomaps.com/basemaps/downloads |
| 10 | EU AI Act: Art. 50(4) disclosure applies from 2 Aug 2026, unless there is human review plus editorial responsibility. Art. 50(2) marking for systems already on the market is due by 2 Dec 2026 | **Confirmed** | None. The 2 Dec 2026 date is in Art. 111(4), inserted by Regulation (EU) 2026/1744 (Digital Omnibus on AI). The procedure is complete: signed 8 Jul 2026, published in the OJ 24 Jul 2026 | https://artificialintelligenceact.eu/article/50/ · https://artificialintelligenceact.eu/article/111/ · https://artificialintelligenceact.eu/implementation-timeline/ · https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/0359(COD) |
| 11 | Copernicus Data Space free quota: 10k Sentinel Hub requests and 10k PU per month, 300/min, **2 concurrent**. S3 2,000 req/min | **Partially true** | No Sentinel Hub concurrency cap is listed. "2 concurrent" applies to openEO API requests and openEO/Data Workspace processing. S3/OData/STAC adds 4 concurrent connections, 20 MB/s each and 12 TB per rolling 30 days. Sentinel Hub also caps PU at 300/min | https://documentation.dataspace.copernicus.eu/Quotas.html |
| 12 | Cloudflare has blocked AI crawlers by default since 1 Jul 2025, and reports crawl-to-referral ratios of about 750:1 (OpenAI) and 30,000:1 (Anthropic) | **Partially true** | The 1 Jul 2025 date is right. The 750 and 30,000 figures say how many times harder it is to get traffic than from Google a decade ago. They are not crawl-to-referral ratios, so don't cite them as such | https://blog.cloudflare.com/content-independence-day-no-ai-crawl-without-compensation/ |

**Also spot-checked against primary pages, all confirmed:**

- **GeoNames:** 10k credits a day and 1k an hour per username, CC BY, daily allCountries.zip.
- **Wikimedia Enterprise free tier:** 50k on-demand requests a month, monthly snapshots, no Realtime.
- **CoinGecko Demo:** 100 calls/min, 10k a month, attribution required. Basic costs $35/mo.
- **Frankfurter:** no key, no quotas, 228 currencies from 106 central banks and official sources. Blended rates are free to use.
- **Kalshi:** keyless public market data at `external-api.kalshi.com/trade-api/v2`. WebSocket needs auth.
- **Polymarket:** Gamma `/markets` 300/10 s and `/events` 500/10 s, CLOB `/prices-history` 1,000/10 s. Limits are IP-based and throttle rather than reject.
- **Manifold:** 500 req/min per IP, API in alpha. Commercial AI/ML training needs a data license.
- **OpenAQ:** v1 and v2 retired 31 Jan 2025 and return 410.
- **IETF AIPREF:** vocab-08 (13 Sep 2026) and attach-05 (18 Aug 2026) are still Internet-Drafts.
- **Cloudflare Content Signals:** published 24 Sep 2025, 3.8M+ managed domains, ai-input left unset, framed as a DSM Art. 4 reservation.
- **ReliefWeb:** a pre-approved appname is required. The 1 Nov 2025 start date is not on the docs page.

**Not re-checked (search budget exhausted):** OpenSky licence wording, adsb.lol and airplanes.live terms, Global Fishing Watch, GDACS terms, the IMF legacy API retirement, and the court-case statuses in 2.1 (e.g., the Third Circuit's *Thomson Reuters v. Ross* affirmance and approval of the *Bartz* settlement). Treat them as [S] until confirmed.
