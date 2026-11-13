# GlobaLens 3.0: Underexposed

**Contrarian vision · 2026-10-28**

**Tagline:** *See beyond the headlines: a live instrument for where the world isn't looking.*

## 0. The premise this vision rejects

The research converged on one direction, "see how the world sees the world": five Lens modes, per-story framing diffs, propagation replay, a Silence Map, a time machine, an analyst and an MCP server. It is a strong plan, but it rests on three premises that I think are wrong for one developer in late 2026.

1. **"Help people read the news better."** This is the most crowded job online. Google pays 400+ publications for AI overviews; Particle, Kagi, Perplexity and Ground News polish story pages; World Monitor claims 2M+ users. Nobody is short of ways to read what gets covered. What's scarce is knowing what doesn't.
2. **"Depth means more AI on article text."** Summaries and framing diffs carry the most legal risk (the Cohere and Perplexity suits target substitutive summaries and false attribution), cost the most per story, and are the hardest to evaluate: frame labels are subjective, and the SemEval framing data is licensed for research only. On 27 Oct, World Monitor shipped `get_media_perspective` with stance fields defined but still empty. The incumbent is moving into that lane.
3. **"Live is the product."** GDELT updates every 15 minutes and its APIs are decaying: DOC is throttled, GEO returns 404, and 17 days of 2025 are missing without notice. World Monitor already owns "live". The bias worth measuring is structural and slow, and the people who act on it plan week by week.

The decisive argument is the research's own biggest caveat: **GDELT measures media attention, not ground truth.** Every other vision has to apologize for that; this one is built on it. Free sensors and curated datasets (USGS, GDACS, FIRMS, UCDP, Kontur population) measure severity, and the **gap** between severity and attention is measurable, yet nobody publishes it in real time. Only annual reports exist (CARE's *Breaking the Silence*, the EU's Forgotten Crisis Assessment), and Jigsaw's Unfiltered.News is gone. The gap has consequences: Eisensee & Strömberg (*QJE* 2007) found that US disaster relief follows news coverage, and that coverage falls when a disaster coincides with other big news such as the Olympics.

**GlobaLens Underexposed answers one question superbly: where is the world looking away, in which languages, and why?**

## 1. Pitch

A dark globe, lit only by the world's news attention, measured every 15 minutes in English plus the ~65 languages GDELT translates. Press **E** and the light redistributes: over-covered places dim, and severe but unseen crises begin to glow. Severity means people affected and killed, taken from sensors and curated datasets, never from the news. The Lens becomes a **light meter**: rotate the planet under it and it reads exposure in photographic **stops** (an illustrative readout: "−4.6 stops in English-language media, −1.9 in Arabic"). Every number links to its inputs, its uncertainty and a reproducible method. Every Monday GlobaLens publishes an open, hashed, recomputable **Underexposed Report**: CARE's annual report made weekly, per language and auditable.

**Why it wins with each judge:**
- **Staff engineer at an AI lab:** measurement-grade ML. Multilingual open-set linking, quantification with calibrated intervals, a glass-box counterfactual, a pre-registered causal study and as-of external validation. The LLM is used only where an ablation shows it helps.
- **Principal engineer:** the smallest system that answers the question. One VM, no vector database, no crawler, no message broker, about $20–37/month, and a Postgres that can be rebuilt from the lake.
- **Product/design leader:** one question, one gesture (E), one unit (stops), one ritual (Monday), and a visual signature nobody else has: inverted light, eight language globes, attention weather.

**How it differs** (verified white space from the digest: #3, real-time attention vs. severity, is the core; #4–#9 support it; #1–#2, framing diffs and per-story propagation, are left to other visions):

| Product | The question it answers | Underexposed instead |
|---|---|---|
| World Monitor | What is happening everywhere right now? (468 feeds, instability index for 31 countries, keyword spikes, headlines grouped by outlet country) | What is happening that the media is *not* covering, in which language, and why: the negative space, with a published method, and no layer race |
| Ground News Blindspot | Which stories one side of US politics ignores | Which crises the world ignores relative to their severity, worldwide and per language |
| Liveuamap | Curated incidents on a map | Measures attention instead of reporting incidents |
| CARE / ECHO reports | Annual, expert, partly qualitative | Weekly, subnational, per language and reproducible, and validated against those same lists |

## 2. Users and jobs-to-be-done

The lead persona is the **attention allocator**: someone whose job is deciding what other people look at.

| User | Job to be done | Primary surface |
|---|---|---|
| NGO communications or advocacy officer | "When I pitch editors or donors, I need current, defensible evidence that my crisis gets too little coverage for its severity." | Crisis Ledger permalink, press-kit export, live badge, watch-lens alert |
| Foreign editor; journalism instructor or student | "When we plan coverage, show us what our language's press is missing, compared with severity and with other languages." | Language filter, weekly report, "missed in Spanish" view |
| Researcher (media studies, humanitarian policy) | "I need an open, longitudinal attention-vs-severity dataset with a documented method." | Parquet downloads, methods paper, API/MCP, `make reproduce` |
| Philanthropy / effective-altruism analyst | "Neglectedness is one of my criteria, and I want it measured rather than guessed." | Exposure ranking with intervals, funding context |
| Curious public (secondary) | "Show me what I'm not hearing about." | Weekly report, share cards, daily quiz |

The first niche, recruited by hand (20–50 people), is NGO communications staff and journalism instructors. Both groups have a weekly ritual (planning meetings, story pitches) and a reason to share what they find.

## 3. Features, ranked

| # | Feature | Wow moment | Novelty | Size |
|---|---|---|---|---|
| 1 | **Exposure Globe + Light-Meter Lens** (Visible / Infrared / Exposure modes) | Press E: light drains away from the world's media centres and pools over crises nobody covers. The reticle reads "−4.6 stops ±0.7" | Novel | L |
| 2 | **Filter wheel and Eight Globes** | Eight mini-globes side by side, each lit by one language's attention: every language sees a different planet | Novel | M |
| 3 | **Crisis Ledger** (a server-rendered permalink per crisis) | An NGO pastes the link; the card shows a mini-globe and "−4.1 stops in English media"; the page holds per-language severity vs attention, the forgetting curve, linked headlines and every source | Better | M |
| 4 | **Weekly Underexposed Report + open data** | `make reproduce WEEK=2026-W44` recomputes the published index bit for bit | Novel | M |
| 5 | **Long Exposure** (2016–2026 replay, forgetting curves) | Scrub through a decade and compare how fast attention faded for disasters with similar death tolls | Novel | L |
| 6 | **Expected attention + bias decomposition** | "Of −4.6 stops, about −2 comes from distance to media markets, −1.3 from language, −0.8 from news pressure" (illustrative numbers) | Novel | L |
| 7 | **Attention Weather + crowd-out study** | earth.nullschool-style particles stream from newsrooms toward a mega-story while crisis regions go dark: "this week's news pressure cost an estimated X% of crisis coverage" | Novel | XL |
| 8 | **Watch-lenses + live badges** (Atom/webhook, no accounts) | An NGO's website badge updates itself; an "attention cliff" alert fires when the world looks away | Better | M |
| 9 | **Explainers, numeric Analyst, MCP server + MCP App** | Ask Claude "What is Spanish-language media ignoring this month?": a cited answer plus an interactive mini-globe | Better | L |
| 10 | **If it were here** | Drag a crisis's affected population onto your city: H3 rings grow until they hold as many people | Better | S |
| 11 | **Daily Calibration** | "Which crisis got more coverage this week?" Intuition vs measurement (active mass-casualty events excluded) | Better | S |
| 12 | **AI Echo** (research) | "Media silence becomes model silence": LLM accuracy on crisis facts vs exposure | Novel | M |

Table stakes built in from Phase 1:
- Location honesty: centroid geocodes are never drawn as pins.
- A Lens that works without dragging, per WCAG 2.2.
- URL-as-state.
- `/trust`, `/stats` and an attribution page.

## 4. Signature interaction: the Lens becomes a light meter

In v1 you rotated the planet under a reticle to list what fell inside it. The v1 essence survives intact: world news on a 3D globe, AI that reads ~340k articles a day well enough to know which crisis each one concerns, and the Lens gesture. What changes is what the reticle measures.

- **Meter.** The ring splits into two arcs, heat (severity) on the left and light (attention) on the right. The centre shows **exposure in stops**, `log2(share of crisis attention ÷ share of severity)`, with an interval. 0 is proportionate and each stop is a factor of two; attention spans five orders of magnitude, so a log unit is the honest choice, and photographers already read it. "Proportionate" is a reference line, not a claim about what coverage a crisis *should* get.
- **Aperture.** A geodesic radius from 25 to 3,000 km: a spherical cap filled with H3 cells, not a circle of screen pixels.
- **Shutter.** A time bezel (24 h / 7 d / 30 d / custom); double-click returns to live.
- **Filter wheel.** Language filters (All, EN, AR, ES, FR, RU, ZH, HI, PT, …) on an outer bezel. Rotating it (or pressing 1–9) re-lights the planet with that language's attention.
- **Split ring.** Two half-rings over one place, one per language ("English vs Arabic"). By design it compares languages, never crisis against crisis.
- **Detent.** The Lens snaps to crisis centroids, and arcs stream in from the countries whose outlets cover the place. If none arrive, the silence is the finding.
- **Honesty readout.** "31% of this attention is allocated from country-level geocodes (by population)."
- **Pin, Transpose, Explain** (`P`, `T`, `X`). An agent-driven Lens is drawn with marching dashes; any drag interrupts it.
- **Accessibility.** Click to centre, arrow keys, `[ ]` for radius. The "In the Lens" list is the screen-reader view, with debounced live-region summaries ("Darfur: severity very high; English attention one twenty-fourth of proportionate; minus 4.6 stops").

**Depth kernel:** the Lens runs entirely in the browser. A Web Worker decodes a 1–3 MB Arrow "exposure cube" (H3 res 3/4 × language × window) with flechette, fills the cap with h3-js and sums it (target: under 16 ms); the GPU highlights the cap with one uniform. The server never sees a Lens query, so a viral spike costs nothing.

## 5. UX concept

**Aesthetic.** The UX report's "Deep Field" system (near-black neutrals, matte panels, glowing data, a lime `#C3F344` instrument accent, Newsreader / Inter / JetBrains Mono), plus one rule: **light means attention.** Visible mode glows like city lights on the night side; Infrared shows severity as heat; Exposure is bivariate, with luminance for severity and hue from azure (under-exposed) to orange (over-exposed), checked for colour blindness and paired with −/+ glyphs. One encoding at a time.

**Desktop.** Top bar: ⌘K (crises, places, languages), a V / I / E / W mode switch, the time window and a freshness badge ("attention as of 14:15 UTC · severity as of 27 Oct"). Left: "In the Lens", the crises inside the cap ranked by stops, with sparklines. Centre: the globe. Right: the Ledger in a non-blocking sheet. Bottom: the Chronoscope, with a severity area, one attention line per language, news-pressure shading and mega-event markers, stepped with J/K.

**Mobile.** A full-bleed globe with the Lens centred in the area the sheet leaves free. The filter wheel becomes a chip row. A Base UI Drawer snaps from list to Ledger card to full Ledger. The weekly report is a mobile-first article, since most traffic arrives through shared cards.

**Tone.** No leaderboards of suffering. Copy says "coverage", never "worth". Every view states what it measures and what it doesn't.

## 6. Data sources

| Source | Role | Terms | Cadence |
|---|---|---|---|
| GDELT GKG 2.1 raw files, English + translated | Attention by place, language and outlet; only titles and URLs are kept | Free; cite and link | 15 min |
| Wikipedia pageviews (per language edition) | Independent signal of public attention | CC0; compliant User-Agent | Daily |
| ReliefWeb v2 | Disaster registry (GLIDE numbers); report counts as humanitarian-sector attention | Approved appname; metadata only | Daily |
| Wikidata | Crisis names in 100+ languages; outlet → country/language | CC0 | Weekly |
| UCDP GED 26.1 + Candidate | Conflict fatalities and history | CC BY 4.0; token | Monthly |
| GDACS, USGS, NASA EONET, NASA FIRMS | Hazard alerts, footprints, magnitudes, fire radiative power | Open, with acknowledgement or a free key | 1 min – 3 h |
| Kontur Population (H3, 400 m) | People exposed | CC BY | Static (2023) |
| HDX HAPI | Displacement, food security, funding context | HAPI terms + source licences (endpoints to verify) | Weekly |
| Natural Earth, GeoNames dump, Protomaps PMTiles | Admin polygons, gazetteer, dark basemap | Public domain / CC BY / ODbL | Static |
| BigQuery `gdelt-bq.gdeltv2.gkg_partitioned` | One-off 2016–2026 backfill aggregates | $6.25/TiB after 1 TiB free | Once |
| CARE and ECHO forgotten-crisis lists | Labels for external validation (crisis names only) | Facts | Annual |

The rule: **severity never uses signals derived from news.** The one exception is UCDP, which is coded from reports. It is flagged as such, and an index variant built only on sensor data is published next to the main one. Not used: ACLED (its terms), article HTML of any kind, and non-commercial feeds.

## 7. Architecture and stack

```
GDELT EN+TR (15 min)      USGS · GDACS · EONET · FIRMS · UCDP · HAPI · ReliefWeb · Wikidata · pageviews
        └────────────┬─────────────┘
          Python worker / Dagster assets (ledger, MD5, retries, gap registry) ──► R2 Parquet lake (bitemporal) ◄── DuckDB · BigQuery backfill
                     ▼
   collapse syndication → candidate filter → CPU embeddings → LightGBM → Haiku adjudication → quantify
                     ▼
   PostgreSQL 18 + PostGIS + h3-pg  (registry · 14-day links · aggregates · exposure)
          ├─► Arrow exposure cubes + weekly snapshots ─► R2 + Cloudflare CDN ─┐
          └─► FastAPI (ledgers, MCP, Atom/webhooks) via cloudflared ──────────┤
                                                                               ▼
                   Next.js 16.4 (SSR ledgers/reports, OG) + MapLibre 6.16 + deck.gl 9.4 + Worker Lens
```

| Component | Choice | Why it earns its place |
|---|---|---|
| Ingest + orchestration | Python 3.13 (uv): a plain worker with a ledger in Phases 1–2, Dagster OSS from Phase 3 | A real multi-cadence asset graph (15 min to monthly) with backfills and asset checks; lineage makes reproducibility visible |
| Core store | PostgreSQL 18 + PostGIS 3.6 + h3-pg 4.2.3, self-hosted | Crisis footprints are polygons and the joins are spatial; aggregates are relational; one engine |
| *No vector database* | Embeddings computed, used, discarded | No open-ended retrieval: linking compares against ~5k crisis descriptions in memory, removing the RAM limit the research calls binding |
| Lake | Lean Parquet on R2 with `valid_time` / `ingested_at` columns + DuckDB; raw zips kept 30 days (GDELT archives them) | Egress-free history; "as-of" queries for honest backtests; Postgres becomes a rebuildable cache |
| Backfill | BigQuery on GDELT's partitioned tables, with quotas and `maximum_bytes_billed` | ~3 TiB scanned for ten years of aggregates, ≈$0–25 spread across months; an ADR records the rejected Rust parser |
| Embeddings | EmbeddingGemma 2 vs harrier-270m vs e5-small bake-off, ONNX Runtime on CPU | Multilingual, permissive, effectively free; only crisis candidates and a small daily sample are embedded |
| Linker | LightGBM + isotonic calibration | Fast, inspectable, distilled from LLM adjudications |
| LLM | Claude Haiku 5.5 Batch (thinking off); Sonnet 5.5 as sampled judge | Adjudication and explainers for ≈$5–15/month; outputs stored, since API 2026-10-21 removed temperature control |
| Counterfactual + causal | Explainable Boosting Machine (InterpretML); statsmodels event studies | Explanatory claims need a glass-box model (shape functions published); crowd-out is regression, not deep learning |
| API | FastAPI, OpenAPI → TS client, MCP Python SDK | One typed contract for the web app and agent tools |
| Web | Next.js 16.4 (App Router, Cache Components) | Server-rendered Ledger and report permalinks with OG cards are how the project spreads |
| Globe | MapLibre 6.16 (pinned) + deck.gl 9.4.1 `MapLibreOverlay` on WebGL2 | Real cartography, adaptive globe, GPU H3/scatter/arc layers; particles as a MapLibre custom layer (`projectTile` works on the globe) |
| Lens compute | Web Worker + flechette + h3-js | Cap queries over Arrow cubes in the browser; no server load per interaction |
| Mini-globes / OG cards | d3-geo orthographic SVG | Eight WebGL contexts would be wasteful, and Satori can't render WebGL |
| Charts / UI | uPlot; Tailwind 4.3, shadcn/ui (Base UI), Motion, nuqs, cmdk, React Aria `useMove` | 60 fps time series; every view in the URL; precise instrument controls |
| Edge | Cloudflare DNS, WAF, CDN, R2, `cloudflared` tunnel | Immutable cubes cached at the edge; no open ports at the origin |
| Compute | One Hetzner EU ARM VM (CAX21, 4 vCPU / 8 GB), Docker Compose | Small, constant workload; scale-to-zero buys nothing when GDELT writes every 15 minutes |

## 8. ML/AI components and how each is evaluated

| Component | What it does | Evaluation |
|---|---|---|
| Syndication collapse | URL canonicalization + MinHash LSH on normalized titles, so it counts distinct stories per outlet group rather than reposts (22.8% of English titles were duplicates in one sample) | Pairwise precision/recall on 500 labelled pairs; reports how much reposting inflates attention in each language |
| Outlet geography | Domain → country/language, from Wikidata, top-level domains and manual overrides | Accuracy on 500 hand-checked domains; share of article volume resolved |
| Crisis linker (cascade) | Candidates from geography, themes and crisis names → embeddings + LightGBM with an open-set "none" class → Haiku for low-margin cases | 1,500-item gold set in ≥12 languages, 20% double-annotated (κ): macro-F1 per language, open-set precision, ECE, per-stage ablation, LLM-vs-distilled cost/quality Pareto |
| Attention quantifier | Adjusted and probabilistic classify-and-count, with bootstrap intervals. The index needs accurate *totals*, not accuracy on each article | Absolute error of estimated totals on held-out labelled days; whether 90% intervals contain the truth 90% of the time |
| Severity S-v1 | People affected, on a ratio scale (fatalities as an alternative denominator), with ranges | Validity checked against independent proxies (ReliefWeb report volume, HAPI funding requirements); rank stability (Kendall τ) under perturbed assumptions (exposure thresholds, source choice) |
| Expected-attention EBM | Predicts attention from severity, crisis type, recency, country covariates, language–country ties and news pressure. Gives a conditional exposure and a per-crisis decomposition | Temporal holdout (train ≤2023, test 2024–26) against severity-only and no-change baselines; interval calibration; **as-of precision@10 and recall against the ECHO and CARE lists** |
| News pressure + crowd-out | News pressure is the daily share of a language's coverage taken by its top three story clusters (HDBSCAN on a daily sample of ~5k titles per major language). An event study around pre-scheduled mega-events (Olympics, World Cups) estimates crowd-out | Analysis plan committed before any run; placebo dates; robustness per language; null results published |
| Explainers | Haiku writes the words; every number is a template slot filled from SQL | Automated number check on 100% of outputs; MiniCheck-Flan-T5-L (0.8B, CPU) on claims; quarterly human rating of 100 explainers (κ) |
| Analyst + MCP | Typed tools: `exposure`, `underexposed`, `timeseries`, `news_pressure`, `crisis_lookup`, `forgetting_curve`, `flyTo`, `setFilter` | 150 questions with gold tool traces and numeric answers: tool accuracy, exact match on numbers, cost per question |
| AI Echo | Monthly templated factual questions about 100 crises, put to 2–3 models | Accuracy vs exposure, controlling for severity and for how old each crisis is relative to the model's training cutoff |

## 9. Platform, infrastructure, CI/CD

**Topology and cost.** One EU ARM VM runs Postgres, the worker/Dagster, FastAPI and `cloudflared` under Docker Compose. Everything public is either static on R2 behind the CDN or server-rendered on Vercel Hobby (non-commercial; a static-export fallback on R2 covers its hard cap). Monthly: VM ≈$13, R2 ≈$1–3, LLM ≈$5–15, domain ≈$1, optional Workers Paid $5, so **≈$20–37 in total**. BigQuery and Modal (optional classifier experiments) stay within free tiers under hard quotas.

**Fallback.** One research report found Hetzner's Cost-Optimized line marked "currently not available". If a CAX can't be ordered, a CPX32 (€35.99 with IPv4) brings the total to ≈$45–50; alternatively Postgres moves to Neon with hourly writes so its compute can sleep.

**Infrastructure as code.** OpenTofu 1.13 manages Hetzner, Cloudflare, GitHub (org, rulesets), Grafana and Vercel, with encrypted state, plan comments on every PR and nightly drift checks.

**CI/CD.** A public org-owned repo on GitHub Actions: free arm64 runners build ARM images natively; actions are SHA-pinned and audited with zizmor; Docker Hardened Images with a Syft SBOM and build-provenance attestations verified before deploy; Renovate with a release-age delay, release-please, and a merge queue behind one `ci-ok` check.

**Tests:** golden-file contracts for GDELT's formats; Testcontainers for the PostGIS/h3 SQL; promptfoo + pytest eval suites nightly and on any model-touching PR; Playwright visual regression of the globe (SwiftShader, fixed seed and clock); a k6 smoke test.

**Reproducibility gate.** Every night the last published week is recomputed from the lake; a hash mismatch blocks the next publication.

**Observability.** OpenTelemetry into Grafana Cloud Free (including LLM generations) plus Sentry; public `/status`, `/stats` ($/month, freshness) and `/trust` (eval scores). SLOs: 99% of GDELT windows ingested within 30 minutes; report out by Monday 06:00 UTC; Ledger p95 under 300 ms at the origin; Lens INP p75 under 200 ms.

**Disaster recovery.** Postgres is a cache of the lake, so the drill rebuilds it from R2 on a fresh OpenTofu-built VM and publishes the measured recovery time.

## 10. What I deliberately cut, and what is lost

**Cut:**
- A general news feed or "what's happening now" reader.
- Per-story framing diffs, stance labels and article summaries.
- Any crawler or HTML fetching. Only GDELT titles, URLs and metadata are stored: no article ledes, and no parsing of robots.txt or Content-Signal headers.
- A vector database and a story-clustering benchmark (StoryStream / Miranda).
- SSE, NATS and Kafka. The browser polls a 2 KB JSON file on the CDN every 60 s, and the data only changes every 15 minutes.
- Cloud Run, Kubernetes, ClickHouse, Rust and C++. None of their triggers fires at this volume, and the ADR log records each one as "considered, not triggered".
- Accounts and personal data. Watch-lenses are URLs with Atom feeds and webhooks, and the newsletter runs on an outside platform.
- Forecasting; flights, ships and markets; prediction markets.

**Lost, honestly:**
- **Daily-habit consumer appeal.** Nobody opens Underexposed to read today's news. The audience is smaller, and reach depends on the weekly report, cards, embeds and citations.
- **The flashiest LLM features** (framing diffs, open chat over all news). I'm betting that measurement-grade ML reads as rarer at an AI lab, but it is a bet.
- **The breaking-news feel.** Hazards and attention refresh every 15 minutes, but the product's heartbeat is weekly.
- **Story-level depth.** We know *how much* each language covered a crisis, not *how* it framed it.
- **Moral exposure.** Putting numbers on attention per unit of severity invites hard questions, and the product has to be built with humility.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Ranking crises reads as ranking lives, and politicized conflicts invite accusations of bias | Compare languages by default, never crisis against crisis; switchable severity definitions; intervals everywhere; an ethics statement; 2–3 humanitarian and journalism reviewers before launch |
| Severity data are sparse, lagged and partly derived from news, which risks circularity and misses the most neglected crises | A sensor-only variant and staleness stamps, both published; the index is described as conservative |
| Attention is biased: GDELT's source mix shifts (English volume −61% since 2016), stories are syndicated, and the linker makes errors | Per-language share of voice; syndication collapse; quantification intervals; pageviews and ReliefWeb as independent attention series |
| A GDELT outage, or a format change in "GDELT 5" | Self-healing ingester, a registry of known gaps, golden-file contract tests and a `SourceConnector` abstraction; pageviews keep a degraded index alive |
| Over-reaching causal claims in the crowd-out study | Pre-registration and placebo tests; results described as associations unless the identification holds; null results published |
| Explainers that hallucinate | Numbers only come from SQL; MiniCheck; a human reviews every report, which is labelled AI-generated regardless (EU AI Act Art. 50) |
| A small audience | Hand-recruit NGOs and instructors first; citable permalinks and badges; launch with a report rather than a dashboard |
| Scope creep back toward a news app | Non-goals listed in the README; every feature must move an exposure metric or a validation metric |

## 12. Resume bullets and headline metrics

Values in brackets are filled in only from the metrics ledger.
- Built **GlobaLens**, an open, live instrument measuring the world's news attention against crisis severity in [N] languages from [9] fused open datasets; weekly index cited by [N] NGOs and outlets; [U] weekly users.
- Designed a multilingual crisis-linking cascade (geo/theme filter → CPU embeddings + LightGBM → Claude Haiku adjudication) over ~340k articles/day: macro-F1 [X] across [12] languages on a 1,500-item double-annotated benchmark (κ = [Y]); quantification cut the error in estimated totals from [A]% to [B]%.
- Trained a glass-box counterfactual attention model on ten years of backfilled GDELT (BigQuery, $[C] one-off). Computed as-of, with no look-ahead, the index's top 10 recovered [P]% of the crises on the EU Forgotten Crisis Assessment and CARE lists.
- Ran a pre-registered event study of news crowd-out around [N] scheduled mega-events: [X]% (95% CI [..]) less crisis coverage per +10 percentage points of news pressure.
- Shipped a WebGL2 globe whose Lens computes spherical-cap aggregates in the browser from Arrow cubes (INP p75 [X] ms, [Y] fps on a mid-range laptop); 99% of requests served from the CDN.
- Ran it for $[Z]/month with OpenTofu, attested CI/CD, a 99% freshness SLO and a weekly index that anyone can reproduce bit for bit.

**Headline metrics** (on `/stats` and `/trust`): linking macro-F1 per language; error in estimated totals and interval coverage; as-of precision@10 against ECHO/CARE; EBM holdout error vs baselines; the crowd-out estimate with its CI; freshness SLO and reproducibility hash matches; Lens INP/FPS; $/month; weekly users, embeds and citations.

## 13. Ten-phase sketch (about 3 weeks each, part-time; every phase goes live)

| Phase | Ships | Depth added |
|---|---|---|
| 1 Light | Week 0: v1 tagged `v1-hackathon` with an honest retrospective, org repo and CI, ADR-000 (this thesis), UCDP/ReliefWeb/FIRMS access requested, Hetzner CAX confirmed; spike deck.gl interleaving and custom-layer particles on the globe. Ships: self-healing GDELT ingester (English + translated) → attention by place and language; attention-lit globe; Lens v1 meter on a browser-side cube; Eight Globes; location honesty; live URL | Ingestion correctness; spherical-cap kernel; honesty infrastructure |
| 2 Heat | USGS, GDACS, EONET, FIRMS, UCDP and Kontur exposure; provenance/licence schema with a CI check; Infrared mode; place-level exposure in stops | Fusing many sources on H3 |
| 3 Registry | Crisis registry (GDACS, UCDP and ReliefWeb, plus Wikidata names); linker v1; gold set v1 (500 items) and `/trust`; server-rendered Crisis Ledgers with OG cards; Dagster adopted | Multilingual open-set linking with evals |
| 4 Exposure | Crisis-level exposure with intervals; bivariate Exposure mode; first human-reviewed Underexposed Report with a snapshot hash; first 20 hand-recruited users | Quantification |
| 5 Long Exposure | BigQuery backfill for 2016–26; pageview history; decade replay; forgetting curves | Bitemporal lake, as-of queries |
| 6 Counterfactual | EBM and decomposition; as-of validation against ECHO and CARE; methods paper v1; gold set grows to 1,500 | Glass-box ML, external validity |
| 7 Share | Watch-lenses (Atom/webhook), live badges, press kit, Transpose, Daily Calibration; launch checklist, then Show HN | Product loops |
| 8 Explain | Explainers checked with MiniCheck; numeric Analyst that drives the Lens; MCP server and MCP App mini-globe; agent eval | Evaluated agents |
| 9 Weather | News-pressure index; Attention Weather; crowd-out study published | Causal inference; GPU particles |
| 10 Harden | Reproducibility gate in CI; disaster-recovery rebuild drill; load tests; keyboard traversal of the hex grid (Data Navigator); AI Echo study; case studies and a talk | Operational maturity; research |

## 14. Estimated size

About **48k LOC** (range 40–60k):

| Area | LOC |
|---|---|
| Frontend (TypeScript) | ~16k |
| ML, evals and analysis | ~9k |
| Tests | ~8k |
| Ingestion and connectors (Python) | ~6k |
| API and MCP | ~4k |
| Infra and CI | ~3k |
| SQL | ~2k |

Size is an outcome, not a goal. The README leads with measured capabilities.
