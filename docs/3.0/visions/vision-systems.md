# GlobaLens 3.0 — "Seismograph"
### Vision · Systems & ML depth: a real-time planetary news engine

> **One line:** an open engine that turns every GDELT 15-minute update (~340k articles/day, 60+ languages) into a *measured* model of the world's attention: stories, how each one travels, how loud it is, and where the world goes quiet. It runs with exactly-once effects on one €10 server, replays any moment back to 2016, and publishes its own error bars.

*Numbers marked **[measured]** come from my run over 16 GKG batches (8 EN + 8 translated, 2026-10-27) and both GDELT master file lists. The script ships in `bench/`.*

## 1. Name, tagline, pitch

- **Name:** GlobaLens (kept). Engine codename: **Seismograph**.
- **Tagline:** *"A seismograph for the world's news."* Secondary: *"See beyond the headlines."*

**Pitch.** A seismograph doesn't read the news; it measures the ground moving. GlobaLens 3.0 does that for media attention. Every 15 minutes it ingests all of GDELT's GKG (English and translated) and clusters ~300k unique headlines a day into multilingual stories. From those stories it computes four observables nobody publishes together:

1. **Magnitude `M`:** log₁₀ of the number of independent outlets, after syndication is collapsed.
2. **Wavefront:** when the story reached each country and language, corrected for crawl lag.
3. **Attention field:** H3 cells × time, compared with a seasonal baseline.
4. **Gap:** what physically happened versus how much the world noticed.

The globe and the Lens are the instrument panel. You rotate the planet under the reticle and read measurements with uncertainty, not headlines.

Underneath is the real exhibit: stream processing with *proven* exactly-once effects, an evaluated online clustering engine, one Rust kernel placed where a measurement demanded it, honest backtests, and a public page of its own SLOs and evals.

## 2. Why this is not World Monitor, GDELT Cloud or Ground News

World Monitor aggregates 468 feeds into a dashboard of *what is happening*. GlobaLens computes a dataset of *how the world hears it*: depth on one firehose, and every pixel traceable to a versioned, evaluated computation. Numbers in parentheses refer to the verified white space in digest §0.

| | World Monitor | GDELT Cloud | Ground News | **GlobaLens** |
|---|---|---|---|---|
| Core | Feed aggregation, 59 layer types | AI-coded events/stories, $59+/mo | Partisan bias ratings | **Computes** stories, magnitudes, wavefronts, gaps (2, 3) |
| History | 7-day *local* playback | From Mar 2026 | — | Attention **since 2016 at 15 min**; stories for 2 years (7) |
| Perspective | Country-level grouping, stance empty | — | Left/right | Per-story framing diffs, every claim cited and checked (1) |
| Location | No precision display | — | — | Precision tiers; centroids never drawn as pins (5) |
| Quality | Forecast scores withdrawn under audit | Unpublished | — | Public evals vs published SOTA (6) |
| Agents | MCP behind Pro quotas | Paid MCP | — | Free H3/time/wavefront/gap tools, MCP App globe (4, 9) |
| License | AGPL + Pro | Commercial | Proprietary | Apache-2.0, open Parquet releases |

**Non-goals** (stated in the README): flight, ship and market feeds; bias ratings; opaque instability scores; storing full text; "we predict events".

## 3. Target users and jobs-to-be-done

1. **Data journalists and media researchers.** First niche, recruited by hand from data-journalism communities and media labs. *"I need defensible numbers (reach, lag, framing) and a citable dataset."*
2. **Journalism, IR and Model UN students and teachers.** *"How do other countries frame this? What's under-covered?"*
3. **Humanitarian communicators.** *"I need a method-transparent attention-gap number for a neglected crisis."*
4. **OSINT hobbyists and the curious public.** *"Show me where stories start and how they ripple; let me replay history."*
5. **Agents and developers.** *"Let me query attention by H3 cell × window × language through typed, cited tools."*

Engineers doing a hiring review can audit `/engine`, `/trust` and `/stats`.

## 4. Ranked features

| # | Feature (what the engine computes) | Wow moment | Phase |
|---|---|---|---|
| 1 | **StoryStream:** live multilingual story catalog | Headlines in 30+ languages snap into one story while its magnitude ticks from M 0.9 to 2.4 | 5 |
| 2 | **Wavefront:** how each story travels | Arcs land country by country in arrival order: "Spanish-language media 9 h after Arabic; amplifier: X" | 6 |
| 3 | **Lens 3.0:** a geodesic instrument | Over the Sahel, the readouts settle with error bars: "+2.7σ · 61% centroid-level · 17 languages arriving" | 3 |
| 4 | **Long Exposure:** a decade at 15-minute resolution | Scrub to 24 Feb 2022, 03:00 UTC and watch Europe's attention field erupt | 7 |
| 5 | **Infrared:** attention-gap index | A quake gets two rings: expected M 2.9 (2.5–3.2) as an outline, observed M 1.6 as a fill. The empty ring is the silence | 8 |
| 6 | **Perspectives:** per-story framing diffs | Split a story into Arabic, Russian and English blocs; divergent claims fan out with citation chips | 9 |
| 7 | **Signals and forecasts** with public backtests | Hotspots ranked by surprise, beside a "where we lose to VIEWS" table | 8–9 |
| 8 | **Engine Room and Trust Observatory** | Watch the 06:15 interval traverse seven stages; read live F1, freshness, $/day | 2→ |
| 9 | **Geo-news MCP and MCP App** | Ask Claude "How did X spread?" and a wavefront mini-globe renders inline | 10 |
| 10 | **Open Data Releases and GlobaLens-Bench** | One DuckDB line queries a citable decade of measured attention | 10 |

## 5. Signature interaction: the Lens becomes an instrument

In v1 the Lens was a fixed screen-space circle listing 10 points. In 3.0 it measures:

1. **The aperture is a spherical cap** (25–3,000 km). A GPU shader uniform highlights it. h3-pg converts the cap to H3 cells for the query, so results don't depend on the screen and stay correct at the poles.
2. **Readouts are measurements**, not lists:
   - volume and `M`;
   - surprise in σ against a seasonal baseline band;
   - arrivals by source country and language;
   - city vs centroid precision;
   - gap residual.

   Each number has a "how computed" popover naming the model version and its current eval score.
3. **Time bezel.** Rotate it to scrub. A worker recomputes the readouts from immutable Arrow cubes in under 100 ms.
4. **See-through modes** change what shows inside the ring:
   - **Arrivals:** arcs stream in from the countries covering the place, coloured by their tone.
   - **Languages**, **Tone** or **Precision**.
5. **Pin, Split, Watch.** Split shows the Δ between two lenses. A watch-lens alerts when surprise passes 3σ.
6. **Follow mode.** The lens rides a story's frontier during a Wavefront replay.
7. **One query, three surfaces.** A lens state is a URL (nuqs), an API call and an MCP tool call, all computed by one function.
8. **Drag-free** (WCAG 2.5.7):
   - click to centre, arrow keys, `[ ]` for radius;
   - ⌘K grammar, e.g. `lens khartoum 300km -72h`;
   - the feed list is the screen-reader view, with `aria-live` summaries.

## 6. UX concept

**A "Deep Field" instrument panel.**
- Near-black, matte chrome where only data emits light; a lime `#C3F344` reticle; mono numerals.
- **Uncertainty is visual language:** interval bands, error bars, and low-sample cells that fade to neutral.
- One encoding at a time. The default is *surprise*, because raw volume maps newsrooms.
- Modes: Viewfinder · Long Exposure · Split · Infrared · Tour (narrated auto-tours, a stretch goal).

**Desktop** (around the globe):
- **Left:** Lens readouts and story cards, each with an `M` badge, language count and first-seen time.
- **Right:** a non-modal dossier with tabs: Wavefront · Perspectives · Timeline · Entities · Sources · **Method**.
- **Bottom:** the **Chronoscope**, a tone-stacked seismogram with USGS/GDACS event ticks, a LIVE edge, and zoom from a decade down to 15 minutes.
- **Top:** ⌘K and an honest two-clock badge: *"pipeline +7 min · GDELT crawl lag median 2 h"*.

**Mobile:**
- Full-bleed globe. The Lens is centred in the *unobscured* area.
- A Base UI Drawer with three detents:
  - **peek:** one line, e.g. *"Khartoum · M 2.6 · +2.7σ"*;
  - **half:** stories;
  - **full:** dossier.
- Wavefront plays as a 20-second scrubbable animation.
- Share produces an OG card: a d3-geo SVG globe plus the magnitude.

**`/engine`** draws the pipeline as a living diagram. Each interval is a packet moving through the stages, coloured by latency against budget, alongside queue depths, stories born and merged per hour, and LLM spend against its cap. Clicking a packet opens its trace.

**`/trust`** shows every eval with its release history; a 10-year completeness calendar, where GDELT's silent 17-day gap in June 2025 is a black stripe; SLO burn, $/day, and model, data and license cards.

## 7. Data sources

| Source | Cadence | License | Role |
|---|---|---|---|
| GDELT GKG 2.1, EN + translingual (**files, never APIs**) | 15 min | Free with citation and link | Backbone: titles (99.9%), locations, themes, tone |
| GDELT Events + Mentions | 15 min | Same | CAMEO analytics, mention timing |
| USGS · GDACS · EONET · FIRMS | 1 min – 3 h | Open | Severity field |
| UCDP GED Candidate | Monthly | CC BY 4.0 | Conflict severity; forecast truth |
| VIEWS | Monthly | Unverified, offline only | Forecast baseline |
| Wikipedia pageviews · Wikidata (+ Embedding Project) | Daily / live | CC0 | Public attention; entity IDs; linking candidates |
| Current Events portal | Daily | CC BY-SA | Eval labels |
| GeoNames · Natural Earth · Kontur Population (H3) | Static | CC BY · PD · CC BY | Gazetteer, polygons, per-capita normalization |
| Protomaps PMTiles on R2 | Daily | ODbL | Basemap |
| ~300 publisher RSS feeds | Live | Syndication | `SourceConnector` fallback; ledes ≤200 chars |
| **Tier-1 transient fetch** | On demand | Only where robots.txt, Content-Signal `ai-input` and RSL allow | Derived facts for Perspectives; TTL ≤24 h; never stored |

Not used: ACLED (its terms forbid substitutes), paid news APIs, mobility and market feeds.

## 8. Architecture

### 8.1 Shape

```
GDELT lastupdate.txt ×2 (poll 60 s) ─► fetch 3 files ─► MD5 ─► R2 raw cache (30 d)
     │ ledger row per (stream,type,stamp)     hourly reconciler: Range-read master list ─┘
     ▼ pgmq stage queues (at-least-once) · each write + ledger transition = one txn
 parse ─► MERGE + H3 rollups (same txn) ─► embed (ONNX int8) ─► StoryStream ─► enrich (stories)
     └─ transactional outbox ─► SSE doorbell · cache warm · watch-lens alerts
 PostgreSQL 18 (PostGIS · h3 · pgvector · partman · pgmq) ⇄ DuckLake catalog ⇄ Parquet on R2
 Dagster OSS (batch plane): merge/split · nightly evals · releases · backfills · asset checks
 FastAPI (REST · SSE · Arrow) + MCP ─► Cloudflare (Tunnel · Worker · immutable cache) ─► Next.js
```

### 8.2 Semantics: the depth kernel

- **Exactly-once effects on top of at-least-once delivery.**
  - A GDELT interval's ledger row moves through `listed → fetched → verified → loaded → embedded → clustered → published`.
  - An interval is complete only when all three files pass MD5. Listed files can 404 for minutes, so each file retries on its own.
  - Consumers write their output *and* the ledger transition in one transaction, using natural-key `MERGE` (`GKGRECORDID`, `GLOBALEVENTID`). Redelivery is a no-op.
  - Poison messages go to a dead-letter queue after 5 attempts.
- **Proof, not prose.** A nightly chaos harness SIGKILLs workers 1,000 times over a fixture week. It then asserts that the final state hash (an ordered digest of every derived table) equals the hash from a clean run.
- **Event time vs processing time.**
  - Filename stamps aren't publish times (files appear ~10 min early).
  - StoryStream runs in event-time order behind a 2-hour watermark. Late data is assigned against frozen centroids and flagged, and wavefronts recompute idempotently.
- **Deterministic replay.** Derived state = f(raw log, code version, model versions).
  - API 2026-10-21 rejects `temperature`, so LLM outputs are memoized in `llm_memo`, keyed by (prompt hash, input hash, model). Replays are free and bit-reproducible.
  - Story IDs survive re-clustering through max-overlap matching.
- **Immutable buckets.** A closed 15-minute bucket becomes a content-addressed Arrow file on R2, served `Cache-Control: immutable`, so reads scale at the CDN for $0. If embedding lags, attention cubes still publish and the UI says "stories catching up".

### 8.3 Stack, one line each

| Component | Why it earns its place |
|---|---|
| **PostgreSQL 18**, self-hosted | One ACID store for ledger, models, queues and outbox. ACID makes exactly-once effects cheap |
| PostGIS 3.6 · h3-pg 4.2.3 | Geodesic Lens queries, gazetteer; H3 keys at ingest, cap polyfill, res 2–7 rollups |
| pgvector ≥0.8.7 | Story-level HNSW on binary-quantized halfvec. 0.8.7 is a CVE fix that managed providers lack |
| pg_partman · pgmq | Drop partitions instead of `DELETE`; at-least-once queues with no new infrastructure |
| DuckLake 1.0 + Parquet on R2 · DuckDB 1.5 | Versioned time-travel lake (replay, history, releases) with zero egress; backfills; agent SQL sandbox |
| Python 3.13/uv · ONNX Runtime int8 · LightGBM | ML ecosystem; ~300k CPU embeddings/day; ranker, classifier and quantile models (trees export to Rust) |
| **Rust + PyO3** (`storystream-core`) | The sequential replay loop (§8.4) |
| Dagster OSS 1.13, batch plane only | Partitioned backfills, evals, releases, asset checks → `/trust`. Run status can't join our transactions, so the ledger stays the truth |
| Claude Haiku 5.5 Batch (thinking off) · Sonnet 5.5 judge | Adjudication, synthesis and framing for ~$15/mo; self-hosting saves nothing at this scale |
| Modal | GPU bursts within the $30/mo credits |
| FastAPI 0.162 · MCP Python SDK | REST, native SSE and OTel, with OpenAPI → TS client; agent tools that call the *same* query functions |
| Next.js 16.4 / React 19.3 | Persistent globe layout; SSR story pages and OG images for distribution |
| MapLibre 6.16 (pinned) + deck.gl 9.4.1 `MapLibreOverlay` (WebGL2) | Cartography, globe→Mercator morph, million-point, arc and H3 layers |
| flechette workers · Protomaps on R2 | Arrow decode 2–7× faster than arrow-js, off the main thread; a ~$0 basemap |
| Tailwind 4.3 · shadcn/ui (Base UI) · React Aria · Zustand · TanStack Query · nuqs · uPlot · d3-geo | Design speed; accessible ring; URL-as-state; 60 fps seismogram; SVG OG globes |
| Hetzner CAX21 (EU ARM) · Cloudflare R2/Tunnel/Worker · Vercel Hobby | €10.49 always-on 4 vCPU/8 GB; no open ports; immutable-bucket cache; Next.js previews |
| OpenTofu 1.13 · GitHub Actions · OTel → Grafana Cloud Free + Sentry · pgBackRest → R2 | Everything as code; free arm64 CI; SLOs and LLM traces at $0; tested point-in-time recovery |

### 8.4 Rust: measured in, measured out

- **Rejected by measurement: a Rust GKG parser.**
  - **[measured]** Plain Python runs the full nested parse (locations, themes, persons, tone, Extras, URL canonicalization) at **11.7–13.6k rows/s per laptop core**.
  - The 10-year backfill is **5.67 TB zipped, ~1.4 B rows**, so parsing takes about 30–60 core-hours: hours on a rented 16-vCPU box.
  - The download is the bound, so the ADR says no Rust parser.
- **Adopted behind a trigger: `storystream-core`.**
  - Online clustering is sequential: each assignment moves the centroids the next article sees, so it can't be vectorized.
  - The Python reference is estimated at 0.5–1 ms per article. A 2-year replay (~200 M articles) would take **28–55 h**, and every model upgrade needs one, plus ablations.
  - **Trigger:** a replay over 12 h. **Target:** ~50 µs/article (in-process HNSW, compiled GBDT, deterministic f32) ⇒ ~3 h.
  - It ships as a PyO3 module plus a `storystream replay` CLI.
  - The Python version remains the oracle; differential tests require ≥99.9% assignment agreement.
  - If the trigger doesn't fire, the ADR records the decision and the Rust crate isn't built.
- **Never built:** tile servers, a WASM Lens (haversine over ≤200k points takes milliseconds in JS), C++.

### 8.5 Budget

**RAM (8 GB):** Postgres 3 GB · clusterer 0.7 · Dagster 0.6 · embedder 0.5 · workers 0.5 · API 0.3 · headroom 2.4. Why it fits:
- I **index stories, not articles**, roughly 100× fewer vectors.
- Singleton stories leave the centroid index after 48 h.
- MiniCheck and GLiNER2 load only inside batch jobs.

**Money per month:**

| Item | $/month |
|---|---|
| VM + IPv4 | 12.6 |
| R2, ~350 GB (10-year lean lake est. 210–280 GB; 2-year 128-d embeddings ~50 GB) | ~5.5 |
| Workers Paid | 5 |
| Claude, capped in code | ≤18 |
| Domain | 1 |
| Free tiers and credits | 0 |
| **Total** | **≈ $42** |

One-offs: a backfill burst box (€5–15), and fine-tuning plus 2-year embeddings (~$16–30) covered by Modal credits.

## 9. ML/AI components and evaluation

| Component | Method | Published evaluation | Bar |
|---|---|---|---|
| **GlobaLens-Embed** | Bake-off: harrier-270m (MIT), EmbeddingGemma 2, e5-small, with Qwen3-0.6B as ceiling. Then Matryoshka fine-tune on T8 + Miranda + mined hard negatives ($5–20). 256-d story / 64-d storyline prefixes | SemEval-2022 T8 Pearson (18 language pairs); titles/s on CPU | 0.818 best published |
| Syndication collapse | URL canonicalization, NFKC hash, MinHash LSH | P/R on 500 labeled pairs | **[measured]** 22.8% EN duplicate titles |
| **StoryStream** | ANN over decayed centroids → Miranda features (multi-level cosine, BM25, entity Jaccard, ADM1, Δt with σ = 72 h) → LightGBM ranker + calibrated new-story classifier; hourly merge/split with memoized Haiku | Prequential pairwise + B-cubed F1 with CIs; ablations (time/entity/geo/LLM, titles-only); fragmentation; p95 latency | Miranda 2018: 94.1/97.1/94.2 monolingual, **84.0 cross-lingual** |
| **Wavefront** | Outlet registry (Wikidata P17/P856) + hierarchical per-outlet crawl-lag model fitted on `PAGE_PRECISEPUBTIMESTAMP` | Arrival MAE on masked timestamps; 80% interval coverage | **[measured]** median lag 120 min EN / 82 min TR; timestamps present 58% / 44% |
| Entity linking | GLiNER2-multi → Wikidata Embedding Project + `wbsearchentities` → ranker → Haiku on low-margin cases (story level) | Mewsli-9 + 200 in-domain items | Mewsli-9 baselines |
| Geo + location honesty | `Geo_Type ∈ {3,4}` points, earliest-offset primary, centroid suppression, LLM toponyms → GeoNames | Admin-1 accuracy, median km error (300 items) | **[measured]** 58.5% / 50.9% city-level |
| Attention surprise | Volume-normalized STL + MAD, BOCPD, Chronos-2 quantiles | Weekly precision@k vs UCDP spikes and Current Events | Seasonal-naive |
| **Expected attention → Gap** | LightGBM quantile model of `M` on *severity-only* features. Geography is excluded on purpose, so the residual **is** the geographic bias | Pinball loss; PI coverage on held-out years; Spearman vs CARE/ECHO lists (sanity check) | Coverage within ±5 points |
| Grounded synthesis | Haiku Batch: ≥3 outlets, ≤120 words, verified `source_ids`, 8-gram rejection, no quotes | MiniCheck per sentence; ALCE citation P/R; κ vs 300 labels; $/story | Zero overlap violations |
| Perspectives | Per story × bloc: MFC frames, roles, stance, unique and omitted claims, cited → MiniCheck → distilled XLM-R | 300-item gold (κ); SemEval-23 T3 offline only; cost/quality Pareto | Human κ |
| Forecasts | UCDP country-month, h = 1–3: Chronos-2 with attention covariates + LightGBM | Rolling-origin on as-of vintages: CRPS, MASE, coverage, PIT | No-change, seasonal-naive, VIEWS. **Losses published** |

Golden sets are versioned. promptfoo and pytest gate PRs on fixture slices, and the full suite runs nightly into `evals/history/` → `/trust`. LLM metrics use n ≥ 3 samples with CIs. **GlobaLens-Bench** reaches 1,000 multilingual items with a second annotator (κ), built from GDELT metadata only.

## 10. Platform, CI/CD, observability, SLOs

- **IaC:** OpenTofu stacks `bootstrap · edge · engine · observability · github · web`. State is encrypted in R2, and drift is checked nightly.
- **Runtime:**
  - Compose on the VM. Images are built on native arm64 runners with a Syft SBOM and SLSA L3 provenance; `gh attestation verify` gates each deploy, and rollout is health-gated with auto-rollback.
  - pgBackRest WAL goes to R2, with a nightly restore test.
  - A quarterly DR drill destroys the VM, runs `tofu apply`, restores, and replays 6 h from GDELT. The RTO is published (target under 60 min).
- **CI:** linters and type checks; property tests and Rust↔Python differential tests; GDELT golden-file contract tests (61/16/27 columns, malformed UTF-8); eval gates; Playwright globe visual regression; k6 smoke; oasdiff; a license check; zizmor with SHA-pinned actions (Trivy pinned per the CVE-2026-33634 ADR). One `ci-ok` check, release-please, and an org-owned repo for the merge queue.
- **Observability:** OTel → Grafana Cloud Free, with one trace per interval and a span per stage. Sentry covers errors, and a public status page carries a freshness badge.
- **SLOs:**
  - **Freshness:** 99% of intervals queryable ≤30 min after GDELT publishes.
  - **Completeness:** 99.9% ≤24 h.
  - **API:** 99.5% availability; cache-miss p95 < 300 ms; CDN hit ratio ≥90%.
  - **Quality:** no release if F1 drops >1 point or faithfulness drops >2 points.
  - **Cost:** LLM ≤ $0.60/day; the breaker pauses summaries and the engine keeps running.
  - A burning freshness budget freezes feature work.

## 11. What I deliberately cut

- **Breadth layers** (flights, ships, markets, outages): World Monitor's turf, and several feeds are non-commercial.
- **Kafka, Redpanda, Flink, NATS:** at ~15 msg/s, pgmq plus the outbox already give exactly-once effects. NATS comes in only with ≥3 consumers on separate hosts.
- **Kubernetes:** a timed DR rebuild proves more than a cluster would.
- **ClickHouse, Qdrant, graph databases:** not until a measured trigger fires (~1 B hot rows, or p95 > 2 s).
- **Tile servers, the Rust parser (rejected by measurement), WASM, C++.**
- **Self-hosted LLMs, fine-tuned LLMs, agent frameworks:** one tool registry serves both MCP and the Analyst.
- **Full text, per-article summaries, quotes in AI text, bias scores, prediction claims.**
- **WebGPU as a baseline, three.js/Cesium globes, 3D Tiles, native apps, GraphQL, microservices.**

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| GDELT churn (GDELT 5, listed files that 404, silent gaps) | `SourceConnector` + RSS fallback; contract tests; ledger, reconciler and gap registry; "data as of" banner |
| One person, 11 ML components | Dependency-ordered phases, each shippable; core complete by P6; body-level Perspectives and forecasts cut first |
| VM availability (a fact-check found Cost-Optimized "not available"); repricing | Order in week 1; fit in 8 GB; fallback CAX11/CX33 with a tighter LLM cap; hard caps; public cost panel |
| Real-stream quality below the benchmark (titles only; thin translated metadata) | In-domain Bench; LLM adjudication; publish both numbers with error analysis |
| Validity: attention ≠ reality; EN volume −61% since 2016; crawl lag | Per-source-country normalization; lag model; intervals everywhere; methods pages |
| Legal | Metadata-first; Tier-1 policy engine; synthesis guardrails; EU AI Act Art. 50(4) labels; publisher opt-out |
| Render stack (experimental GlobeView, interleaving) | Week-1 spike; MapLibre native heatmap; Mercator above z10 |
| Owning AI-written code | Hand-written depth kernels (ledger, `storystream-core`, spherical cap); ADRs drafted by me first; explain-back recordings |

## 13. Resume bullets and headline metrics

Bracketed values are filled only from the `/stats` metrics ledger.

- Built an open real-time news engine ingesting every GDELT 15-minute update (~340k articles/day, 60+ languages) with **exactly-once effects on at-least-once delivery** (Postgres ledger, pgmq, idempotent MERGE, outbox). Held **[99.x]%** of intervals fresh within 30 min over **[90]** days, verified by a 1,000-run SIGKILL chaos harness with replay-identical state hashes.
- Designed StoryStream, an online cross-lingual clustering engine, reaching **[x]** cross-lingual pairwise F1 against the published 84.0 (Miranda et al., EMNLP 2018). Ported its sequential loop to **Rust/PyO3** after profiling: a 2-year replay went from **[N] h to [M] h**.
- Fine-tuned a 270M multilingual embedder to **[r]** Pearson on SemEval-2022 Task 8 (best published 0.818) for **$[k]** of GPU time.
- Made architecture decisions by measurement: rejected a Rust parser after benchmarking Python at 12–14k rows/s/core, then backfilled 10 years of GDELT (5.7 TB zipped, ~1.4 B records) to enable 15-minute replay back to 2016.
- Built a crawl-lag-corrected propagation model (median GDELT lag 2 h) with **[c]%** coverage on its 80% intervals.
- Published rolling-origin forecast backtests (CRPS vs VIEWS on as-of vintages), *including the months the model loses*.
- Ran everything for **$[≤45]/month** with public SLOs, OpenTofu, SLSA L3 deploys, and a DR rebuild in **[m] min**.

**Headline:** *"GlobaLens · 340k articles/day · [n] languages · 99% fresh < 30 min · cross-lingual F1 [x] · $[y]/mo · live /stats."*

## 14. Ten phases (~35 weeks part-time)

Each phase ends with a tagged release, a live demo, a GIF and ADRs.

| Phase | Ships | Demo / gate |
|---|---|---|
| **1 Foundations** (wk 1–3) | `v1-hackathon` retrospective; monorepo (pnpm/Turbo, uv, Cargo, mise); OpenTofu; PG18; CI; license check; render spike; globe with live USGS quakes | Real data from day one; `tofu apply` rebuilds everything |
| **2 The ledger** (4–7) | Poller, MD5/retry, ledger, pgmq, parser, MERGE, in-transaction H3 rollups, reconciler, outbox → SSE, immutable cubes, chaos harness, `/engine` | Field updates every 15 min. Gate: 7 days ≥99% fresh |
| **3 Lens 3.0** (8–10) | Spherical cap, uncertain readouts, precision tiers, Chronoscope, nuqs, a11y, mobile sheet, OG cards | Gate: p95 < 300 ms; INP < 200 ms |
| **4 Embeddings and evals** (11–13) | Labeling tool, Bench v0, Miranda/T8 harness, embedder Pareto, MinHash, translingual search, `/trust` | "water shortage" lights up Hindi, Spanish and Arabic coverage |
| **5 StoryStream** (14–17) | Python reference, watermark, Haiku merge/split, stable IDs, `M`, grounded synthesis, story pages | Gate: F1 with CIs; p95 < 1 s |
| **6 Wavefront and entities** (18–20) | Outlet registry, lag model, arrivals and amplifiers, travel-time curve, arcs; entity linking | Watch a story ripple |
| **7 Long Exposure and Rust** (21–24) | Burst backfill from 2016, 2-year embeddings, replay measured → `storystream-core`, completeness calendar | Scrub to 24 Feb 2022; benchmark post |
| **8 Infrared and signals** (25–27) | Severity fusion, gap model, hotspots, watch-lenses and weekly digest (Better Auth) | The empty ring |
| **9 Perspectives and forecasts** (28–31) | Cited bloc framing → distilled classifier; Split; UCDP forecasts; scoreboard | Losses published |
| **10 Agents and launch** (32–35) | MCP server and MCP App; Analyst on the same tools; DR1 (Zenodo DOI); Bench v1; k6 at 10×; DR drill; niche launch → Show HN | Claude renders a wavefront inline |

**Stopping points:** after P5 it is already a live, evaluated multilingual story engine; after P7 it adds propagation and a decade of replay that nothing open offers.

## 15. Size

About **70k LOC (±15k)**, an outcome rather than a goal: web ~20k · Python engine, API and MCP ~20k · Dagster, training and evals ~8k · Rust ~4k · SQL ~2.5k · IaC and CI ~3k · tests and benchmarks ~13k. The résumé quotes measured capabilities, never line counts.
