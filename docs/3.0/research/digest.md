# GlobaLens 3.0 — Research Digest (lead synthesis of 9 reports + 7 fact-checks, 2026-10-28)

Full reports (with inline **[corrected: …]** marks and fact-check tables) live in `research/*.md`. This digest is
what every downstream agent must internalize first. Where the digest and a report disagree, the digest wins (it
already applies the fact-check corrections).

## 0. The finding that changes everything: the generic idea is taken
- **World Monitor** (github.com/koala73/worldmonitor, AGPL-3.0) started as a weekend project in **Jan 2026**, has
  **~89.7k stars, 2M+ claimed users**, WIRED coverage, an experienced founder, and the **same globe.gl/three.js
  stack v1 used**. It has: 3D globe, 468 feeds / 59 layer types (flights, ships, markets…), AI country dossiers with
  citations, a country instability index, ⌘K palette (622 commands), MCP server + SDKs + Tauri desktop app, Pro
  $39.99/mo. In Aug–Oct 2026 it also shipped: **WebMCP** (33 tools incl. set_map_view/set_time_range), an analyst that
  moves the map, MCP **bbox/radius/since_days** filters, **get_media_perspective** (27 Oct 2026 — headlines about a
  *country* grouped by outlet home country; translated titles/stance labels defined but returned empty), keyword
  spike detection vs 7-day baseline, a local 7-day playback slider, an embeddable live map, a public forecast-accuracy
  page (scores withdrawn under audit since 7 Oct). It even calls its site variants "lenses".
- Also crowded: generic "AI summary of the news" (Google News AI pilot paying 400+ publishers, Perplexity Comet Plus,
  Particle, Kagi News with Perspectives/International-reactions sections; OpenAI retired ChatGPT Pulse in Jun 2026).
  Ground News now advertises a "global coverage map" (still a partisan/ownership axis). Third-party "GDELT Cloud"
  sells AI-coded GDELT events + story clustering + MCP ($59+/mo). Perigon's MCP has radius search.
- **Verified still-open white space** (fact-checked against World Monitor, Kagi, Ground News, Perigon, GDELT tools):
  1. **Per-story cross-lingual framing diffs with every claim cited** ("how does each country's/language's media
     frame *this* story": emphasis, who is quoted/blamed, omissions) — nobody does it per story.
  2. **Animated per-story propagation** (first-seen arcs across countries/languages with lag & amplifier metrics).
  3. **Real-time attention-vs-severity index** ("Coverage Gap"/"Silence Map": what the world under-covers relative to
     severity) — only annual reports exist (CARE "Breaking the Silence", EU Forgotten Crisis Assessment).
  4. **H3/time-bucket geospatial agent tools** (MCP exposing lens/H3/time-window/perspective/propagation/gap primitives).
  5. **Location honesty** (never draw country/state centroids as precise pins; show geocode precision) — no consumer
     product does it.
  6. **Public trust/evals page** (citation faithfulness, geocode accuracy, cluster purity, anomaly precision, $/brief).
  7. **Multi-year, backfilled 15-minute world replay** (World Monitor's playback is 7-day local snapshots).
  8. **A draggable, pinnable, multi-lens consumer instrument** (radius queries exist in APIs, not as a consumer UI).
  9. **Narrated auto-generated globe tours** and **MCP Apps mini-globe inside Claude/VS Code/M365** — unverified/likely open.
- Strategic implication (all four product-facing reports converged independently): **compete on depth, provenance and
  narrative intelligence, not breadth.** Proposed repositioning: **"See how the world sees the world"** — a
  perspective, propagation and attention engine for world news — with "See beyond the headlines" as secondary tagline.
  Explicit non-goals: flights/ships/markets breadth, proprietary bias ratings, opaque instability scores, full-text
  scraping, "autonomous forecasting" claims. A README section "How is this different from World Monitor / GDELT /
  Ground News?" is mandatory.

## 1. Data backbone — GDELT facts (measured 2026-10-27/29)
- **Use GKG 2.1 raw 15-minute files, English + translated ("translingual")** as primary; Events/Mentions as secondary.
  Volume/day: ~340k GKG articles, ~193k events, ~457k mentions; ~1.0–1.2 GB/day raw (GKG ~98% of bytes; GCAM is 70–73%
  of GKG bytes). **Translated stream ≈1.9–2.2× English** (English down ~61% from 2016) → multilingual-first, v1 ignored
  most of the signal. A 15-min batch is ~3.6k GKG rows/~45 MB; naive Python parses ~23k rows/s ⇒ **live ingestion is
  not compute-bound; Rust/C++ is not justified for it.** (Rust only defensible for a multi-year backfill benchmark.)
- **PAGE_TITLE present in 99.9% of GKG records, og:image (SharingImage) in 82–88%** ⇒ no HTML scraping needed for cards.
  GDELT also still publishes free GSG doc embeddings (USEv4 512-d) — useful only as a weak baseline.
- **APIs are degrading — keep them out of the data path:** DOC 2.0 heavily/intermittently throttled (429, "one request
  per 5 s… switch to ngrams"), **GEO 2.0 returns 404**, Context 2.0 works; GDELT is migrating to Spanner ahead of an
  unscheduled "GDELT 5"; Global Frontpage Graph has published empty files since Nov 2025; Visual GKG frozen since 2022.
- **Reliability:** a silent ~17-day hole (2025-06-14 → ~07-02, 1,665 intervals) exists; in 2026 only 1/28,921 English
  intervals missing. Files can appear in manifests with MD5 yet 404 for minutes; filename stamps ≠ publish times.
  ⇒ self-healing ingester: poll both lastupdate files every 60 s, per-file retry, MD5 verify, mark an interval done only
  when all files pass, idempotent keys (stream, type, stamp), hourly reconciliation against masterfilelist tail via HTTP
  Range, known-gap registry, freshness SLO + "data as of" banner + last-good fallback; golden-file parser contract tests
  (61/16/27 columns, malformed lines, HTML entities, broken UTF-8).
- **Quality is structural:** 22.8% of English titles in a sample were exact duplicates (iheart.com alone 8.5% of English
  docs; syndication); 11–12% of event rows near-duplicate. **38–45% of events geocode only to country/US-state/ADM1
  centroids** (1,880 events/day on the US centroid in Kansas 39.828175,-98.5795). **Filter points by Geo_Type ∈ {3,4}**
  (US city / world city) — *corrected: FeatureID is NOT blank for types 1/2/5*; aggregate types 1/2/5 into
  country/ADM1 choropleths. Event coverage fields (NumSources etc.) only reflect the first 15 minutes (NumSources=1 for
  ~98%) ⇒ compute importance from Mentions over time. Translated docs have much thinner extraction (persons 35% vs 78%,
  quotations 0%).
- **GDELT measures media attention, not ground truth.** MIRAI (LLM agents forecasting on GDELT) reaches only ~30 F1.
  Honest framing: "media lens" + evaluated signals, never "we predict events".
- **Terms:** unlimited use incl. commercial, redistribution and public API **with citation + link to gdeltproject.org**.
  Article content remains publishers' copyright.
- BigQuery: $6.25/TiB after 1 TiB/mo free; minimal GKG columns ≈85 GB/yr scan (fine for one-off backfills with dry runs,
  `maximum_bytes_billed`, `_PARTITIONTIME` filters); SELECT * full history ≈22 TB (≈$120+).
- No budget-fit commercial article API replaces GDELT (NewsAPI.org $449/mo, NewsAPI.ai $90/mo…). Free fallbacks:
  curated publisher RSS (real-time ledes), CC-NEWS (full HTML, ~4h old; Common Crawl requires indemnity — offline ML
  only). ⇒ a `SourceConnector` abstraction is worthwhile.

## 2. Other data + licensing
- **Free, permissive, high-impact layers:** USGS quakes (GeoJSON, updated every minute), GDACS (no auth), NASA EONET v3,
  NASA FIRMS (free MAP_KEY), NASA GIBS daily imagery (WMTS w/ time), **UCDP GED Candidate (CC BY 4.0, monthly, ≤1-month
  lag, free emailed token, 5k req/day)**, **Wikipedia pageviews (CC0 — a clean "public attention" signal)**, Natural
  Earth (public domain), GeoNames dumps (CC BY), Protomaps PMTiles (ODbL attribution), OpenFreeMap (free, no SLA).
- **ACLED is effectively unusable**: gmail/generic emails get the Open tier (aggregated, no API) and terms forbid
  "secondary products or effective substitutes". Use UCDP + GDELT. VIEWS forecasts usable as an external benchmark.
- **Non-commercial-only feeds** (OK for a portfolio, must be tagged): OpenSky (OAuth2 only now), Open-Meteo free tier,
  Cloudflare Radar (CC BY-NC), Global Fishing Watch, EOX Sentinel-2 cloudless. Every record should carry provenance +
  license metadata (`source, license, attribution, commercial_ok`), with a CI check that fails if a source lacks a license
  entry and an auto-generated attributions page.
- **Identity gates are spreading** (start registrations early): UCDP token (2026), ReliefWeb pre-approved appname (since
  Nov 2025), OpenSky OAuth2, Wikimedia 10 req/min for unidentified clients vs 200/min with compliant User-Agent,
  aisstream bandwidth caps, Copernicus account. Dead legacy endpoints: IMF dataservices (use SDMX at api.imf.org),
  OpenAQ v1/v2, ReliefWeb v1.
- **Legal posture ("search engine, not clipping service"):** store metadata + titles + URLs + embeddings + short derived
  facts; **never persist full text**; transient body fetch (TTL ≤24h) only where robots.txt + Cloudflare Content-Signal
  (`ai-input`) + TDM/RSL allow; identifiable crawler UA with contact URL; never bypass paywalls/bot blocks. Precedents:
  AP v. Meltwater (clipping excerpts incl. lede ≠ fair use; not blocking via robots.txt ≠ license), Cohere and Perplexity
  suits (substitutive summaries, hallucinated quotes, false attribution), Thomson Reuters v. Ross (reportedly affirmed
  Sept 2026: competing non-generative tool ≠ fair use). **AI text must be multi-source syntheses** (≥3 outlets, ≤~120
  words, link out, no quotes, sentence-level grounding, reject ≥8-word verbatim overlap) **labelled "AI-generated from N
  sources"** — EU AI Act Art. 50(4) requires disclosure for public-interest AI text since **2 Aug 2026**. Publisher
  opt-out form + per-domain denylist + takedown process; thumbnails handled conservatively (EU press publishers' right).
  GDPR-lite if accounts (passwordless, export/delete, cookieless analytics); CCPA thresholds not met.

## 3. Frontend / geo-visualization (verified versions)
- **MapLibre GL JS 6.16** (ESM-only, WebGL2-only; adaptive **globe → Mercator morph between zoom 10–12**; sky/atmosphere
  since 6.10/6.11; ships almost weekly ⇒ pin exact versions + visual-regression-gate upgrades) **+ deck.gl 9.4.1 via
  `@deck.gl/maplibre` `MapLibreOverlay` interleaved on WebGL2** = the only open stack with real cartography + an adaptive
  globe + million-point GPU layers.
- Caveats needing a **week-1 spike**: deck.gl GlobeView is experimental; **HeatmapLayer/ContourLayer unsupported on
  globe (use MapLibre's native heatmap, which works on globe)**; ArcLayer arcs get back-face-culled (use `cullMode:'none'`);
  CollisionFilterExtension on globe undocumented; picking/depth across the morph and with terrain unverified.
- **WebGPU: progressive enhancement only.** deck.gl 9.4 ported all layers to WebGPU but calls it not production-ready
  and *no basemap integration supports WebGPU interleaving*. Browser support ~89.5% (Firefox Linux/Android lacking).
  A standalone "WebGPU lab" GlobeView (no basemap) is a legit optional showcase.
- Envelope: ScatterplotLayer ~1M points @60fps (old laptop), 10–20 fps near 10M; Chrome 1 GB allocation cap.
- **Arrow-first data plane:** server emits Arrow IPC (GeoArrow-compatible), Web Worker decodes with **flechette**
  (~16 KB, 2–7× faster than arrow-js), feeds deck.gl binary attributes; time filtering (DataFilterExtension) and Lens
  highlighting on the GPU; H3 aggregates when zoomed out (coarse first, then refine). Matches deck.gl v10 / loaders.gl v5
  Arrow-first roadmaps.
- **App shell: Next.js 16.4 (React 19.3, Cache Components default)** — globe mounted once in a persistent client layout;
  server-rendered story/country/lens pages with `'use cache'` + OG images; parallel/intercepting routes open stories as
  panels over the globe. Next has a formal **monthly security-release program** (React2Shell RCE = CVE-2025-55182, Dec
  2025) ⇒ automate patching (Renovate). TanStack Start 1.0 only went stable 13 Oct 2026 (riskier).
- React 19.3: `<ViewTransition>` stable (does NOT auto-respect reduced motion). OG images via `next/og` (Satori) cannot
  render WebGL and need static (non-variable) fonts ⇒ **d3-geo orthographic SVG mini-globe** for share cards.
- UI kit (verified): Tailwind 4.3, **shadcn/ui on Base UI (default since Jul 2026)**, Motion 14.x, cmdk, Zustand 5,
  TanStack Query 5, **nuqs** (URL state), TanStack Table v9 / Virtual, uPlot (streaming charts), ECharts 6, **Base UI
  Drawer for mobile sheets (Vaul unmaintained)**, React Aria `useMove` for the bespoke Lens ring/bezel.
- Basemap: **self-hosted Protomaps PMTiles on Cloudflare R2** (planet ~120 GB ≈ $1.65/mo; a z0–12 extract ≈15 GB),
  recolored dark; OpenFreeMap for dev; **never Mapbox** (proprietary, bill-shock). Google Photorealistic 3D Tiles: only as a
  click-gated extra (1,000 free root requests/mo).
- Realtime: **SSE "doorbell" + immutable, CDN-cacheable Arrow batches**; WebSockets only for multiplayer; no WebTransport.
- Agent UI: **Vercel AI SDK v7 (7.0.x) typed tool parts** for an agent that visibly drives the UI; **AI SDK Elements is
  deprecated end of Nov 2026 → use shadcn AI Elements patterns**. WASM: cargo + wasm-bindgen (wasm-pack also alive —
  corrected); only after profiling proves a hot path. C++ is not justified for the frontend.

## 4. UX direction (proposal from the UX report — strong starting point, not final)
- **Lens 3.0 = a "magic lens" query instrument over space × time × topic:** geodesic radius ring (3,000 km → 25 km),
  time bezel, topic focus, see-through modes (incoming coverage by Source country, Language, Tone), Split compare (two
  lenses), pinned watch-lenses, agent control. Five modes named after camera techniques: **Viewfinder** (live),
  **Long Exposure** (replay), **Split** (compare), **Infrared** (gaps / under-coverage), **Tour** (briefings).
- **"Deep Field" aesthetic:** near-black cool neutrals, matte UI + glowing data, one phosphor-lime instrument accent
  (#C3F344; ties to v1's neon green — but it collides with amber warning for deuteranopes, ΔE 0.077 → fix), 5-step
  orange↔azure diverging tone scale with −/+ glyphs; Newsreader (editorial serif) + Inter + JetBrains Mono; themes
  generated from 3 inputs (Linear-style) incl. high-contrast and "Paper"; panels nearly opaque (NN/g critique of glass).
- **Default encoding = surprise vs baseline**, not raw volume (raw counts map where newsrooms are — xkcd 1138; Correll &
  Heer 2017); one color encoding at a time (Tone | Surprise | Category | Gap); fade low-sample cells to neutral.
- **Chronoscope** timeline: histogram stacked by tone, brush, playback speeds, LIVE edge + return-to-live pill, anomaly
  ticks, J/K stepping — fed by precomputed hourly H3 aggregates (res 2–4).
- **Accessibility from phase 1** (WCAG 2.2 applies directly to the Lens): Lens operable without dragging (2.5.7: click to
  center, arrow keys, ⌘K), 32–44 px targets, Lens feed list as the screen-reader view with debounced aria-live summaries,
  Table view, global "Freeze frame" pause (2.2.2), reduced-motion/transparency paths, "Solid panels" toggle; Data
  Navigator (CMU) for keyboard traversal of the hex grid is a rare differentiator.
- Full state in URL (nuqs): camera, lens center/radius, time window/live, topic, mode, selection; OG image per permalink;
  "S" snapshot shortcut. Performance UX: adaptive quality tiers, SVG placeholder → WebGL crossfade, pause when hidden.
- Agent ("Analyst"): frontend tools flyTo/setLens/setTime/highlightCells/openStory/compare; tool calls rendered as an
  operations log; claim-level citation chips linked to map + timeline; approval for side effects; undoable actions; a
  labelled on-globe agent cursor any user drag interrupts.

## 5. Backend / data architecture (verified)
- Workload is **small in writes** (~1–1.2 GB/day, ~1M rows/day) — volume justifies no distributed streaming. The hard
  problems: sub-300 ms bbox+time+attribute map queries over tens of millions of points, vectors in RAM, multi-year
  analytics, multilingual text, correct loading (idempotency, gaps, backfills).
- **Core: self-hosted PostgreSQL 18 + PostGIS 3.6 + h3-pg 4.2.3 + pgvector ≥0.8.7 (2026 CVE fix; managed providers lag —
  Neon PG18 ships 0.8.6) + pg_partman + pgmq**, plus an **immutable Parquet lake on R2 cataloged by DuckLake 1.0 (Postgres
  catalog)** that doubles as the replay log and history store. Managed Postgres is unstable on extensions (Neon removed
  ParadeDB pg_search 2026-09; Supabase dropped TimescaleDB on PG17) and a constantly-writing workload never scales to zero.
- **Vector RAM is the binding constraint:** Matryoshka-truncated 256–512-d `halfvec`, HNSW on binary-quantized vectors +
  full-precision re-rank, 14-day hot window partitioned by day (drop partitions, archive vectors to Parquet).
- **Ingestion correctness:** ledger table keyed by GDELT stamp, MD5 checks, natural-key MERGE, auto gap backfill,
  **per-batch H3 rollups in the same transaction as read models (CQRS)**, closed time buckets immutable ⇒ CDN-cacheable.
- **Orchestration: self-hosted Dagster OSS** (partitioned assets, sensors, asset checks, backfills). Never Dagster+
  (~$576/mo at 15-min partitions). Prefect announced acquiring Dagster (2026-07-13, not closed; still Apache-2.0) ⇒ ADR
  with Airflow 3.2 as fallback.
- **Messaging: pgmq + transactional outbox first; NATS JetStream only once ≥3 consumers need the same events.** Kafka /
  Redpanda / Flink / stream processors = padding at ~15 msg/s. Postgres LISTEN/NOTIFY takes a global commit lock — not a
  fan-out backbone.
- **API: FastAPI (0.162; native SSE + OpenTelemetry documented)**; OpenAPI → TS codegen. Litestar 3 unreleased,
  connect-python beta.
- **Tiles/time-scrub:** Martin (off-the-shelf Rust tile server; PostGIS function sources, MLT) + H3 rollups res 2–7 +
  Arrow "time-cubes". **Rust only where it earns it:** (a) a GKG backfill parser (PyO3/maturin) to hit a published
  benchmark (e.g., "10 years of GKG in <24 h on one box"), (b) Martin (bought, not built), (c) optionally a WASM Lens
  kernel after profiling. **Custom C++ = padding.**
- Hybrid search inside Postgres first (FTS + pgvector + Reciprocal Rank Fusion in SQL); Qdrant 1.20 later only on measured
  need. Entity graph as Postgres edge tables with valid-time ranges (Kuzu archived Oct 2025; FalkorDB SSPL; Apache AGE
  optional showcase). ClickHouse (self-hosted) only at ~1B history rows or p95 >2 s for 90+-day analytics; ClickHouse Cloud
  ($66–186/mo) is over budget. Skip TimescaleDB (non-OSI features), Kafka, Bytewax, Kuzu.
- **Safe agent data plane:** MCP typed tools over read models; DuckDB sandbox over DuckLake snapshots (read-only,
  memory/time limits, external access off, SELECT-only validated with sqlglot); read-only Postgres role with
  statement_timeout; audit log.

## 6. AI/ML (verified models, licenses, prices)
- **LLM: Claude Haiku 5.5 (Oct 2026) $0.10/$0.50 per MTok; Batch $0.05/$0.25; cache reads $0.01** (10× cheaper than Haiku
  4.5). Sonnet 5.5 $2/$10 (Batch $1/$5); Opus 5.5 $4/$20. ⇒ 5k story summaries/day ≈ $29–38/mo (2k/day ≈ $12–15); one
  "Ask the Globe" question ≈ $0.0026 on Haiku. **Self-hosting an LLM saves nothing at this scale** (gpt-oss-20b on Modal L4
  ≈ $35–49/mo). Gotchas: Haiku 5.5 uses adaptive thinking by default (bills as output) ⇒ effort 'low'/off for bulk; **API
  version 2026-10-21 rejects temperature/top_p/top_k** (no temp-0 determinism ⇒ evals must handle variance); tokenizer
  ~30% more tokens than Haiku 4.5; explicit refusal handling. Claude **`search_result` content blocks give native
  citations** (GA; cited_text not billed; reportedly not combinable with structured outputs). Significance gate (≥3
  articles from ≥2 outlets) + re-summarize only on material change.
- **Embeddings (CPU, ~270M class, permissive):** bake-off between **Microsoft harrier-oss-v1-270m (MIT, 94 languages)**,
  **EmbeddingGemma 2 (Apache-2.0, released 2026-10-06, Matryoshka 768→128)**, multilingual-e5-small; Qwen3-Embedding-0.6B
  (Apache-2.0) as quality ceiling. Then **fine-tune "GlobaLens-Embed"** (multilingual Matryoshka story similarity; a few
  Modal GPU-hours, ~$5–20) scored on **SemEval-2022 Task 8** (best published Pearson ≈0.816–0.818; Hanley & Durumeric
  ACL 2025 is the blueprint: nested Matryoshka prefixes = story/narrative/theme). Store 256-d halfvec. Embedding 300k
  docs/day ≈ free on CPU; serverless-GPU micro-batches cost more (cold starts) — GPUs only for backfills/fine-tuning
  (Modal Starter: $30/mo free credits ≈ 30+ L4-hours).
- **StoryStream (online multilingual story clustering) = the core ML artifact:** per article, ANN over live time-decayed
  cluster centroids → Miranda-style features (cosine at several Matryoshka levels, BM25, entity Jaccard, ADM1 overlap, time
  deltas) → LightGBM ranker + calibrated new-cluster classifier; hourly merge/split pass with Haiku adjudicating borderline
  merges. **Benchmark: Miranda et al. 2018 (EMNLP) — pairwise F1 94.1/97.1/94.2 monolingual EN/DE/ES, 84.0 crosslingual**
  (note: pairwise, not B-cubed). Report ablations, docs/s, p95 assignment latency.
- **Perspectives (framing engine):** Media Frames Corpus 14 frames (Card et al. 2015), entity roles
  (protagonist/antagonist/innocent), stance, claim divergence per story by source country/language; every divergence
  claim cited + checked (MiniCheck), then distilled to a small classifier with an LLM-vs-classifier cost/quality Pareto.
  **SemEval-2023 T3 / 2025 T10 data are research-only (T10 forbids public-API exposure of trained models) ⇒ offline eval
  only.**
- **Faithfulness:** MiniCheck-Flan-T5-L (0.8B, 75.0 on LLM-AggreFact), Bespoke-MiniCheck-7B (77.4); HHEM-2.1 (English-only).
- **Entities/geo at story level** (60–150× fewer items than articles): GLiNER2 multilingual (Apache-2.0) mentions →
  **Wikidata Embedding Project vector search** (since 2025-10, 100+ languages) + wbsearchentities candidates → context +
  popularity prior + Haiku adjudication; eval on Mewsli-9. Geo: GDELT geocodes + LLM toponyms resolved against a PostGIS
  GeoNames subset; Mordecai3 (English-only, needs Elasticsearch) as offline teacher/eval only.
- **Signals/forecasting:** Hotspots = STL/MAD seasonal baseline + BOCPD change points + **Chronos-2 (Apache-2.0)**
  quantile surprise on volume-normalized signals; country-month fatality forecasts (Chronos-2 + LightGBM) benchmarked vs
  no-change/seasonal-naive and **VIEWS with CRPS + interval coverage on as-of vintages; UCDP as ground truth; publish where
  the model loses.** TimesFM 2.5 is Apache-2.0 (**TimesFM 3.0 weights non-commercial**); Toto 2.0 Apache-2.0; Moirai
  research-only.
- **Avoid:** NLLB (CC-BY-NC), Jina v4/v5 (non-commercial), TimesFM 3.0 weights, Moirai, Microsoft GraphRAG (maintenance
  mode), KuzuDB (archived), ACLED in public UI, self-hosted LLM in prod, separate vector DB early.
- **Agents/MCP:** Vercel AI SDK v7 (ToolLoopAgent, typed UI tool parts) for the web agent; Claude Agent SDK = Claude Code
  harness (offline/batch agents only); Pydantic AI 2.63 / LangGraph 1.2 viable for Python-side agents. **MCP spec
  2026-07-28 (now an LF Projects project) with MCP Apps** (interactive UI in sandboxed iframes — works in Claude, Claude
  Desktop, VS Code Copilot, M365 Copilot, Goose; reference examples include a CesiumJS globe server) ⇒ a GlobaLens
  mini-globe MCP App is near off-the-shelf. LightRAG (MIT, Postgres) / Graphiti (bi-temporal) are optional comparisons.
- **Evals first:** golden sets (Miranda, SemEval-22 T8, ~200 retrieval queries, ~300 faithfulness labels, 100–300
  perspective items, ~200 entity/geo items); promptfoo (now part of OpenAI, MIT) + pytest in CI; nightly evals; traces in
  Langfuse Hobby (now part of ClickHouse, MIT, free 50k units) or Arize Phoenix (self-host); public Model Card / Evals page.

## 7. Platform / DevOps (verified prices, 2026)
- Research split on topology; the verified facts: **Cloud Run free tier** (180k vCPU-s, 360k GiB-s, 2M req/mo) makes
  stateless services + 15-min jobs ≈ $0–5/mo. **Hetzner EU ARM (CAX) is the cheapest always-on compute** after the 2026
  repricing (CAX11 €5.99, CAX21 €10.49/4 vCPU/8 GB, CX33 €8.49; CPX/CCX ×2.1–2.75; **US/Singapore far pricier and with
  1 TB/0.5 TB egress vs 20 TB EU ⇒ EU only**). Neon Free (1 GB/project, scale-to-zero after 5 min) cannot hold a
  constantly-writing 30–90-day hot window; Neon compute at $0.106/CU-h never sleeps under 15-min writes. ClickHouse Cloud
  $66–186/mo (over budget). GKE Autopilot ~$60–75/mo + LB. AWS App Runner closed to new customers (Apr 30 2026); Fly.io,
  Railway, Cloudflare Containers (ephemeral disk, no autoscaling) don't fit stateful workloads.
- **Edge: Cloudflare** — DNS, WAF, R2 (zero egress), Workers (free static assets; API gateway with Durable Object rate
  limits; PMTiles serving). **Web: Vercel** (Hobby is non-commercial and hard-capped — a viral spike pauses the site; Pro
  $20) or OpenNext on Cloudflare (3 MiB Worker limit on Free / 10 MiB Paid; no Node middleware).
- **IaC: OpenTofu** (MPL-2.0, CNCF; v1.13; client-side state encryption; HCL so "Terraform" stays truthful); GCS or R2
  backend; layered root stacks (bootstrap/platform/data/apps/edge/observability/github); manage GitHub, Cloudflare,
  Grafana, Vercel as code; Checkov/Conftest policy gates; nightly drift detection.
- **CI/CD (GitHub Actions — free & unlimited on public repos incl. 4-vCPU arm64 runners):** keyless Workload Identity
  Federation; every action SHA-pinned + **zizmor** + harden-runner; **Trivy itself was compromised Mar 2026
  (CVE-2026-33634; malicious v0.69.4–0.69.6, 76/77 trivy-action tags repointed)** ⇒ pin known-good SHA or use Grype, write
  an ADR; Docker Hardened Images (free); Syft SBOM + `actions/attest-build-provenance` from a reusable workflow (SLSA L3) +
  `gh attestation verify` before deploy; pnpm `minimumReleaseAge` (default 1 day) + Dependabot cooldowns; per-PR previews
  (Vercel preview + tagged no-traffic Cloud Run revision + ephemeral DB); **merge queue requires an org-owned public repo ⇒
  move to a free GitHub org**; release-please manifest mode + Conventional Commits.
- **Monorepo:** pnpm + Turborepo (free Vercel remote cache), uv workspace (Python), Cargo workspace (if Rust), mise for tool
  pinning/tasks, devcontainer, Docker Compose watch + `grafana/otel-lgtm` locally; single required `ci-ok` aggregator check.
- **Observability: OpenTelemetry → Grafana Cloud Free** (10k series; 50 GB logs/traces/profiles; 14-day retention; 500 k6
  VUh; synthetic checks; 50k frontend sessions; 30k LLM generations) **+ Sentry Developer** (free). SLOs: 99.5% API
  availability; p95 <300 ms aggregate/tile queries; **99% of GDELT 15-min windows queryable within 30 min (data-freshness
  SLO)**; burn-rate alerts; public status page + freshness badge.
- **Auth: Better Auth** (MIT; Auth.js folded into it) with passkeys + API Key plugin (or Unkey free). Clerk free gates
  MFA/passkeys.
- **Cost guardrails from first deploy:** GCP spend-cap budget / Pub/Sub kill switch (alerts alone don't cap), Cloud Run
  max-instances, BigQuery QueryUsagePerDay quota + maximum_bytes_billed, app-enforced LLM token budgets, public cost panel.
- **Kubernetes only in a late "staff-level" phase, justified by cost math:** k3s on 3× Hetzner CAX11 (~€18/mo) + Argo CD
  (v3.5) + Helm/Kustomize + Cloudflare Tunnel + SOPS/Sealed Secrets, Chaos Mesh game days, timed DR drill restoring from R2;
  can be destroyed/recreated from code between demos. Progressive delivery (tagged canary + auto-rollback on SLO burn).

## 8. Career / presentation (what makes it hire-worthy)
- 30-second resume screens favor brand-like proof points: **one checkable line** (real weekly users, a launch, a published
  benchmark). Deep-dive interviews reward ownership/judgment: must survive a 30-minute grilling without AI help.
- Hardest-to-fake signals: **live no-signup demo on real data (by end of Phase 1–2, kept alive with uptime checks + cached
  fallback)**, a **public /stats page** (usage, freshness, p95, $/month), **reproducible benchmarks and evals**, **ADRs and
  design docs**. Anthropic's careers page asks candidates to put independent research/blog posts/OSS at the top.
- **Honesty infrastructure** (v1's README over-claimed and the demo ran on synthetic data — the worst signals): claims ledger,
  README status table (Implemented / In progress / Planned) generated from CI, tag `v1-hackathon` with an honest
  retrospective, before→after story.
- **AI-ownership protocol:** user writes first drafts of design docs/ADRs (AI as critic); `docs/ai-workflow.md`; hand-build
  2–3 "depth kernels" (e.g., Lens spherical-cap selection, near-duplicate/story clustering, geocode/entity disambiguation),
  each with a blog post; 10-minute explain-back recording after every phase.
- **Avoid résumé-driven development** (documented anti-pattern): modular monolith + ingestion worker first; K8s, microservices,
  C++, agent frameworks only with an ADR + benchmark proving need. "Agent soup" is a red flag. LOC is cheap with AI and a
  huge solo codebase invites "who reviewed this?" — **optimize for measured capabilities, not LOC** (give LOC estimates as
  an outcome only).
- **Open benchmark:** 500–1,000 hand-labeled multilingual geo-news items (geolocation, story clustering, citation
  faithfulness), second annotator for agreement, CI-gated, published with a model-comparison write-up.
- **Real users before launch:** pick one niche with a weekly need (Model UN/debate or journalism students & teachers, or
  OSINT hobbyists), hand-recruit 20–50 users, retention loops (watchlists, weekly digest, shareable lens permalinks/embeds);
  Show HN only after launch gates (no signup, load-tested, cached fallback, cost cap, analytics/error tracking).
- Per-phase artifact contract: tagged release + changelog, live demo updated, GIF, metrics delta, ≥1 ADR, green CI/evals;
  every 2–3 phases a case-study blog post + refreshed C4 diagrams. Extract one reusable OSS package (Lens React component,
  typed GDELT client, or news-dedupe library). 90-second captioned demo video; a meetup lightning talk.

## 9. Lead's synthesis of tensions (to resolve explicitly)
1. **User wants "extra crazy" + C++/Rust/K8s/Terraform/huge LOC; research says résumé-driven development backfires.**
   Resolution principle: deliver "crazy" through *product depth, visual craft, and measured rigor*; introduce Rust, K8s,
   NATS, ClickHouse etc. only at the phase where a measured trigger fires, each with an ADR + before/after benchmark. The
   *evolution story itself* ("here's the metric that forced each component") is the senior signal.
2. **Topology:** fully serverless (Cloud Run + Neon) vs one EU stateful VM (self-hosted PG18 + extensions). Facts: Neon can't
   hold the hot window cheaply and lags pgvector; Cloud Run is ~free for stateless + jobs. Likely answer: one EU ARM VM for
   stateful (Postgres/Dagster/workers) + Cloud Run or the same VM for the API + Cloudflare edge + Vercel web — decide with
   cost math.
3. **Breadth vs focus:** layers (quakes/fires/UCDP) are cheap context and power the Coverage Gap index; flights/ships/markets
   are World Monitor's turf — non-goals.
4. **Real-time cadence:** GDELT is 15-minute; "live" means ≤30-min freshness, not sub-second. Sell time-travel + trust, not
   latency.
5. **Audience:** curious public (beautiful, viral, mobile) vs analysts/students (dense, keyboard-first). Must pick a lead
   persona and a first niche of real users.
