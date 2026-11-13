# GlobaLens Desk: an open foreign desk for everyone

*GlobaLens 3.0 vision · angle: analyst-grade open-source intelligence · 2026-10-28*

**Tagline:** Know what changed, who's saying it, and what the world is missing.
**Brand line (kept from v1):** See beyond the headlines.

## 1. Pitch

GlobaLens Desk turns the world's multilingual news stream (~340k articles a day from GDELT, two-thirds non-English) into **living, cited case files** for every significant story. You interrogate them with one instrument, the Lens: rotate the planet under the reticle (v1's gesture, kept) and the Desk shows what is happening there, how each language's press frames it, how it spread, which figures are reported by whom, and what the world is under-covering relative to severity. Pin a lens and it becomes a standing watch that alerts you with a computed explanation; a diff-based morning brief tells you only what is new.

Three trust rules hold everywhere. Every AI sentence cites its sources and passes a faithfulness check. Every point shows its true geocode precision. Every early-warning signal is pre-registered in a public transparency log and scored against ground truth, including when it is wrong.

It is Palantir's linked analysis and Dataminr's alerting, rebuilt as an open, honest tool for journalists, researchers and NGOs, running on one EU server.

## 2. Why this is not World Monitor (or Ground News)

World Monitor owns *breadth*: what is happening everywhere right now, across 468 feeds and 59 layers, with an instability index, keyword spikes and Pro digests. GlobaLens Desk owns *depth on a single story*: its evidence, its perspectives, its spread and its history. The unit of analysis is the story and the claim, not the layer or the country. Numbers below refer to the verified white space in the digest (§0).

| | World Monitor | Ground News / Kagi News | **GlobaLens Desk** |
|---|---|---|---|
| Unit | Country, layer, feed | Story on a US partisan axis / daily digest | Versioned story case file with claims, figures and entities |
| Perspective | Headlines about a *country*, grouped by outlet country; stance and translation fields empty (27 Oct 2026) | Lean and ownership; an "International reactions" section | Per-story framing diff by language bloc (frames, roles, emphasis, omissions), every statement cited and verified (#1) |
| Spread | — | — | Animated per-story propagation with lag and amplifier metrics (#2) |
| What's missing | — | Blindspot (partisan) | Real-time attention-vs-severity gap with an open method (#3) |
| Early warning | Keyword spikes vs a 7-day baseline; forecast scores withdrawn under audit | — | Pre-registered, Sigstore-timestamped signal ledger; precision and lead time published nightly (#6) |
| Time | 7-day local playback | — | Bitemporal "as-of" case files plus backfilled replay (#7) |
| Location | Pins | — | Precision tiers; centroids are never drawn as pins (#5) |
| Alerts | Pro digests | — | Free watch-lenses pinned on the globe, explain-why inbox, RSS/webhooks/push (#8) |
| Agents | 99 MCP tools, WebMCP | — | H3/time-bucket, perspective, propagation and gap tools on a free tier (#4) |

Liveuamap maps human-verified conflict incidents; the Desk maps how the world's press covers any story, which is a different object.

**Explicit non-goals:** flight, ship, market and weather layers; an instability index; outlet bias ratings; a free-roaming chat agent; forecasting claims.

## 3. Users and jobs-to-be-done

**Lead persona:** the foreign-desk journalist, plus the journalism students learning that beat. **Second persona:** humanitarian and NGO communications and advocacy staff.

| User | Job to be done | Desk feature |
|---|---|---|
| Foreign-desk journalist, fact-checker | "A story broke abroad. Tell me what's corroborated, how local and foreign press frame it, and which figures are moving, so I can file an accurate backgrounder in an hour." | Case File, Perspectives, Figures, Board export |
| Beat reporter | "Tell me when my region or entity changes, not every headline." | Watch-lenses, the Wire, Morning Brief |
| NGO comms and advocacy | "Show, with evidence, which crises are under-covered relative to severity, and monitor our program regions." | Infrared (Coverage Gap), weekly under-covered brief, embeds |
| Media, political-science or disinformation researcher | "I need reproducible, exportable data on coverage, framing and spread, with methods I can cite." | As-of mode, a "Data" button on every chart, Parquet snapshots, API |
| Curious reader, Model UN student | "Help me understand a story from every side, in my language." | Lens, Split, translated headlines |
| AI agent | "Geo-temporal, perspective-aware news tools that return citations." | MCP server |

Journalists come first because they have a weekly need (their beats), already live in RSS and alerts, and share the tools they use. The first 20–50 users are hand-recruited from journalism programs and humanitarian comms networks before any public launch.

## 4. Core objects: a small ontology

Palantir's lesson is that analysis becomes easy once the objects are right. The Desk has nine linked, permalinked object types:

- **Story** (an event cluster lasting hours to days; related stories over weeks form a **Storyline**)
- **Claim** (an atomic statement with its sources) and **Figure** (a reported number: killed, displaced, arrested)
- **Entity** (a Wikidata QID) and **Place** (H3 cell, ADM1 region or country, with a precision tier)
- **Outlet** (a domain mapped to country, language and owner)
- **Signal** (an anomaly, gap or propagation event; pre-registered and scored)
- **Lens** (a saved space × time × topic query you can watch) and **Board** (a user's investigation)

Every derived object is **bitemporal**: it records when something happened and when we knew it. That one decision powers as-of rewind, honest backtests and reproducible exports.

## 5. Ranked features and wow moments

| # | Feature | Wow moment | Novelty · size |
|---|---|---|---|
| 1 | **Lens 3.0 situation readout** | Settle the reticle over the Horn of Africa. Within 300 ms the rail ranks stories ("14 outlets · 6 languages · ▲3.1σ vs baseline"), with tone mix, top entities, live signals and "61% city-precise · 39% region/country haze" | better · M |
| 2 | **Story case files with as-of rewind** | A cited 120-word brief, a "what changed" timeline, a Figures strip, the cast and every source. Drag the bezel back to hour 6 and the file reverts to what was known then. No hindsight. | novel · L |
| 3 | **Perspective Diff + Split Lens** | Split the lens on a cross-border clash. The inside view (local-language outlets) sits left, the outside view right, shared facts in the middle. Emphasis, blame and omissions fan out to either side. Click any sentence: the globe flies to the cited outlets' countries and their source cards light up. | novel · XL |
| 4 | **Watch-lenses ("Tripod") + the Wire** | Pin a 400 km lens on the Sahel: "surprise > 3σ or a new story with ≥5 outlets". At 03:40 an alert arrives with the baseline chart, the contributing stories and why it fired; route it to Slack via a signed webhook. Pinned lenses stay on the globe as faint rings with live badges. | better · L |
| 5 | **Morning Brief** | At 07:00: "Since yesterday: 2 followed stories changed materially (new displacement figure; Turkish-language press now frames it as security); 1 new signal in your Horn of Africa lens; 1 under-covered crisis." Every line is cited and has an SVG mini-map. | better · M |
| 6 | **Propagation Trace ("Long Exposure")** | A story ignites in one city at 06:15. Arcs pulse to each country as its press picks the story up. The panel reads: "Portuguese-language outlets: +8 h via one amplifier; never reached Arabic-language press." | novel · L |
| 7 | **Infrared: Coverage Gap** | Over-covered regions dim. A flood with a GDACS orange alert and a million people exposed glows, because it gets a fraction of the attention a comparable event got elsewhere. The method is one click away. | novel · L |
| 8 | **Pre-registered signals + public scorecard** | `/signals` lists every signal ever fired: its hash in Sigstore's public log, its explanation and its later outcome. Precision and lead time are recomputed nightly against baselines. | novel · L |
| 9 | **Figures** | "Reported death toll by outlet language over time": a step chart built from GDELT's own extracted counts. Spread and outliers are flagged, and UCDP's later estimate is overlaid where it exists. | novel · M |
| 10 | **Location honesty** | Hover a haze: "Located to country centroid (low precision) · GDELT GKG." | better · S |
| 11 | **Constellation (entity graph)** | Hover an entity and its stories light up worldwide. A badge flags a new edge: two organizations appeared together in 14 stories across 3 languages this week, for the first time. | better · L |
| 12 | **Boards, cited export, Data button** | Export a backgrounder as Markdown with footnoted permalinks, CSV and GeoJSON (with precision tiers), plus a generated methods appendix. Every chart's "Data" button shows its query and as-of time. | table-stakes · M |
| 13 | **Open API + MCP** | In Claude: "Compare Brazilian and Argentine coverage of the summit" returns a cited diff and a permalink that opens the Desk in that exact state. | better · M |

## 6. Signature interaction: Lens 3.0

The v1 gesture stays: you rotate the world under a fixed reticle. What changes is what the reticle *is*.

- **A true geodesic cap, not a screen circle.**
  - The aperture ring sets a radius from 3,000 km down to 25 km. Drag the edge, pinch, or press `[ ]`. At city radii MapLibre's globe morphs into Mercator.
  - On the GPU, a one-uniform deck.gl extension highlights the points inside the cap (`dot(p, c) ≥ cos θ`).
  - On the server, the cap is covered by H3 cells (exact interior cells plus refined boundary cells) and answered from rollups.
- **Time bezel.** Rotate the outer ring to scrub through time; double-click returns to LIVE. In **As-of** mode the bezel moves knowledge time, not just event time.
- **Focus.** Type an entity or topic (`@NATO`, `#displacement`) and everything else desaturates.
- **Five modes, named after camera techniques:**
  - **Viewfinder**: the live readout.
  - **Split**: inside vs outside view, language bloc A vs B, or two rings compared.
  - **Long Exposure**: replay and propagation arcs.
  - **Infrared**: the coverage gap.
  - **Tripod**: the lens stays mounted on a place and keeps watching, with alert rules.
- **Outputs, not just highlights.** Every lens offers *Brief me* (a cited situation summary grounded in story summaries), *Pin* (Tripod), *Snapshot* (`S`: a permalink plus an OG card) and *Add to Board*.
- **Drag-free by design** (WCAG 2.2, 2.5.7). Click a point and it glides into the lens; arrow keys pan; +/− buttons resize. React Aria `useMove` drives the ring and bezel, and the readout list doubles as the screen-reader view with a debounced `aria-live` summary.

## 7. UX concept

The look follows the UX research's "Deep Field" direction (near-black matte panels, glowing data, one phosphor-lime accent, an orange↔azure tone scale with −/+ glyphs; Newsreader, Inter, JetBrains Mono) plus one rule from analyst tools: **density without noise**.

**Desktop: the Desk.**
```
┌ ◉ GlobaLens [⌘K lens kyiv 300km · follow · compare fr de · gaps sahel]  ● LIVE  Wire(3) ┐
├ READOUT / WIRE ────┬─────────── globe ───────────────┬ CASE FILE (non-modal, 440px) ─────┤
│ Sahel · 400 km     │     pinned rings ◌   ◌           │ Overview · Perspectives · Spread  │
│ 38 stories ▲2.4σ   │       ╭──── ◯ ────╮ ← Lens        │ Cast & Places · Sources           │
│ tone ▇▅▂▃▆ · 9 lang │       ╰───────────╯              │ brief [1][2][3] · what changed    │
│ ▣ ranked stories   │ [Viewfinder|Split|Exposure|IR|Tripod] figures ▁▃▅▇ · as-of ◀──●     │
├ CHRONOSCOPE ▁▂▃▅▇█▇▅▃▂ anomaly ticks · brush · ▶ 6h/s ·──────────────────────● LIVE ─────┤
└ data as of 14:15 UTC (7 min ago) · 18,204 stories/24h · 61 languages · GDELT ↗         ┘
```
- **Linked brushing:** selecting a story, hex, timeline bar, entity or citation updates every other view.
- **The Wire is an inbox:** `j/k` to move, `e` to archive, `s` to snooze, `b` to send to a Board. Each alert opens its computed explanation.
- **⌘K is a command grammar** that falls back to search.

**Mobile: the brief is the home screen.** It is a PWA with Web Push: open the brief or an alert, then tap into a single-column case file. The Lens view is a full-bleed globe with a Base UI Drawer (detents at 120 px, 50% and 92%), and the lens centers itself in the unobscured area. Split stacks inside over outside, with a swipe to switch. Analysis happens on desktop; staying informed happens on the phone.

**Accessibility from Phase 1:** a freeze-frame control (WCAG 2.2.2), reduced-motion and reduced-transparency paths, a solid-panels toggle, a table view behind every map, and 32–44 px targets.

## 8. Data sources

All default sources are commercially usable. Every record carries `source, license, attribution, commercial_ok`, a CI check fails if a source lacks a license entry, and the attributions page is generated.

| Source | Role | Terms |
|---|---|---|
| GDELT GKG 2.1, English + translingual (15-min raw files) | The backbone. Provides:<br>• titles (99.9% coverage)<br>• locations with `Geo_Type`<br>• themes, persons, orgs, tone<br>• curated GCAM dimensions<br>• `V2.1Counts` for Figures | Free, including commercial use; cite and link |
| GDELT Mentions (Events in Phase 9) | Significance growth over 24–72 h (NumSources reflects only the first 15 min); typed actor edges | Same |
| ~300 curated publisher RSS feeds | Ledes of ≤200 characters for cluster representatives; real-time fallback | robots.txt and Content-Signal respected |
| Wikidata + Wikidata Embedding Project | Entity QIDs; outlet country, language and owner | CC0 |
| Wikipedia pageviews | Attention signal | CC0 |
| GeoNames dump · Natural Earth · Kontur Population (H3, 400 m) | Gazetteer · admin polygons · exposure normalization | CC BY · public domain · CC BY |
| USGS · GDACS · NASA EONET · NASA FIRMS | Severity for Infrared; signal outcomes | Open / acknowledgement / free key |
| UCDP GED Candidate (monthly) | Conflict severity; ground truth for scorecards and Figures | CC BY 4.0 |
| Protomaps PMTiles on R2 | Basemap | ODbL attribution |

**Not used:** ACLED (its terms forbid substitute products), non-commercial-only feeds, social media, full article text.

**Ingestion rules:** metadata only by default; a transient lede fetch only where robots.txt, Content-Signal (`ai-input`) and RSL allow it; full text never persisted; publisher opt-outs honoured within 72 h.

## 9. Architecture and stack

Writes are tiny: about 1.0–1.2 GB/day, roughly 12 rows/s on average. The hard parts are correctness, read latency, RAM and analysis quality. So the design is one Postgres-centred modular monolith on one EU VM, an immutable Parquet lake on R2, Cloudflare in front and Next.js on Vercel.

Two decisions shape everything:
- **The map buckets by knowledge time** (when the evidence arrived), not publication time. Closed buckets never change, so they are CDN-cacheable and replay stays honest.
- **Watch-lenses are evaluated set-based.** Each lens stores its H3 cell coverage once. Every batch joins new stories and signals to that cell index in one query, so cost scales with new evidence, not with the number of lenses.

```
GDELT EN+TR (15 min) · RSS · hazards · UCDP · pageviews
     │  Dagster sensors + ledger (MD5, idempotent keys, gap registry, per-file retry)
     ▼
R2: raw zips (30 d) + lean Parquet, DuckLake catalog in PG ── replay · backfill · open data
     │  COPY/MERGE per batch
     ▼
PostgreSQL 18 · PostGIS · h3 · pgvector · pg_partman · pgmq
  write: articles, mentions │ derived: stories(+revisions), claims, figures, entities, edges
  read models: H3 rollups · story cards · lens cell index · signal ledger
     │                                   │ outbox → pgmq queues
     ▼                                   ▼
FastAPI (REST · SSE · MCP)       workers: embed · cluster · extract · signals · deliver
     ▲ Cloudflare Tunnel + CDN (immutable Arrow cubes) ▼ Next.js on Vercel
```

| Layer | Choice | Why it earns its place |
|---|---|---|
| Web | Next.js 16.4 with Cache Components | Server-rendered case files and briefs with OG cards. The globe mounts once in a persistent layout, and case files open over it as intercepting-route panels |
| Map | MapLibre GL JS 6.16 (exact pin) | Real cartography, plus the globe→Mercator morph needed for radii from 3,000 km down to 25 km |
| Data layers | deck.gl 9.4.1 `MapLibreOverlay`, interleaved on WebGL2 | Draws 100k–1M points, H3 hexes and great-circle arcs; GPU time filter; custom cap-highlight extension |
| Client data | Arrow IPC decoded by flechette in a Web Worker; h3-js | CDN-cached cubes decode off the main thread into binary attributes; cell math matches the server |
| State | Zustand · TanStack Query · nuqs | Camera state stays outside React renders; server cache; the full analytic state lives in the URL |
| UI kit | Tailwind 4.3, shadcn/ui on Base UI, Motion, cmdk, React Aria `useMove`, TanStack Table v9 + Virtual, uPlot | Accessible primitives and drawer detents; the command grammar; drag-plus-keyboard instruments; 10k-row tables; 60 fps sparklines |
| Graph, share images | d3-force in a worker, rendered with deck.gl OrthographicView; d3-geo SVG mini-globes | An entity graph without a second graphics engine. OG cards and brief maps use SVG because Satori can't run WebGL |
| API | FastAPI 0.162 + @hey-api/openapi-ts | Typed REST, native SSE and OpenTelemetry; shares Python code with the ML pipeline; the generated TS client fails CI if it drifts from the spec |
| Agents | FastMCP mounted inside the API | MCP tools reuse the same read-model functions, auth and rate limits |
| Auth | Better Auth (passkeys, magic links, API keys) in a ~300-line Hono service on the VM; FastAPI verifies its JWTs via JWKS | The best-maintained OSS auth library is TypeScript-only, and Vercel can't reach the private database |
| Database | PostgreSQL 18 | One source of truth. Temporal `WITHOUT OVERLAPS` keys guarantee exactly one version of each case file at any instant |
| Geo | PostGIS 3.6 + h3-pg 4.2.3 | Geodesic caps, admin polygons and gazetteer lookups; H3 rollups at resolutions 2–7 |
| Vectors | pgvector ≥ 0.8.7 (includes the CVE fix) | 256-d `halfvec`, with a binary-quantized HNSW index over ~50k live story centroids rather than 4.8M articles, because RAM is the binding constraint |
| Lifecycle, queues | pg_partman · pgmq + transactional outbox | Daily partitions are dropped, never deleted row by row; retries and dead letters without a broker |
| Lake | Parquet on R2 + DuckLake 1.0 | Replay log, as-of rebuilds, backfills and open data, with zero egress fees |
| Orchestration | Dagster OSS 1.13, self-hosted | 15-min partitioned assets, sensors, asset checks as data-quality gates, backfills |
| Migrations, backups | dbmate (plain SQL) · pgBackRest → R2 | The schema is mostly PostGIS/h3 functions and partitions, which ORMs model poorly; point-in-time recovery for the only stateful store |

**Deliberately absent, each with an ADR trigger:** Kafka/NATS (pgmq handles ~15 msg/s; trigger: ≥3 consumers of one stream at a measured rate), ClickHouse (DuckLake answers history; trigger: p95 > 2 s on 90-day analytics), Qdrant (trigger: >10M hot vectors), Martin (trigger: >50k features per viewport) and Rust (naive Python parses ~23k rows/s against ~4 rows/s of average ingest).

## 10. ML/AI components and how each is evaluated

Principle: **computed first, generated second.** Statistics and retrieval decide what is true and what matters. The LLM only phrases the result, with citations, and every sentence passes a checker before it ships.

| Component | Method | Evaluation (live on `/trust`) |
|---|---|---|
| Dedupe | URL canonicalization, then MinHash LSH on normalized titles | Dedupe ratio; precision on 300 sampled pairs |
| Embeddings | 256-d Matryoshka `halfvec` on CPU. Bake-off: harrier-oss-v1-270m, EmbeddingGemma 2, multilingual-e5-small (ceiling: Qwen3-0.6B). Fine-tune "GlobaLens-Embed" on Modal only if the crosslingual target is missed | SemEval-2022 T8 Pearson (best published ≈0.816–0.818) |
| **StoryStream** | Per article: ANN over time-decayed live centroids → Miranda-style features (cosine at two Matryoshka levels, BM25, entity Jaccard, ADM1 overlap, time deltas) → LightGBM ranker plus a calibrated new-story classifier. An hourly merge/split pass sends borderline merges to Haiku | Miranda et al. 2018 pairwise F1 (published: 94.1/97.1/94.2 monolingual, 84.0 crosslingual) plus B-cubed; ablations; docs/s and p95 latency per article |
| Case-file text | Haiku 5.5 on Batch, thinking off. Produces a ≤120-word brief plus a delta as JSON with `source_ids`. Gate: ≥3 outlets from ≥2 countries. Re-run only on material change | MiniCheck-Flan-T5-L checks every sentence and drops failures. A verbatim match of 8+ words rejects the text. Citation precision/recall (ALCE) on 300 labels; $/story |
| Entities | GLiNER2-multi at story level → candidates from the Wikidata Embedding Project → popularity prior → Haiku adjudicates low-margin cases | A Mewsli-9 subset plus 200 in-house items, reported per language |
| Geo | GDELT `Geo_Type` sets the precision tier. Primary location = the earliest city-level mention. A blocklist catches known centroids, and toponyms are resolved against a GeoNames subset in PostGIS | 300 items: tier correctness and admin-1 accuracy |
| **Perspectives** | 1. Blocs by outlet country (Wikidata, ccTLD fallback) or language; each needs ≥3 articles from ≥2 outlets.<br>2. One Haiku call per story extracts per-bloc frames (Media Frames Corpus, 14 frames), entity roles, and emphasized and absent facts; GCAM affect dimensions add free full-text-derived features.<br>3. Every divergence statement cites each bloc it describes.<br>4. Later, labels are distilled into a small classifier | 150–300 two-annotator gold items (κ); frame F1 against SemEval-2023 T3 offline (research-only, never trained on) to measure what headline+lede input loses vs full text; MiniCheck plus human audit; cost/quality Pareto |
| Figures | `V2.1Counts` (type, number, object, location) per story, reconciled by bloc over knowledge time. The field's 2026 fill rate is unmeasured; a spike checks it first | Precision on 200 samples; comparison with UCDP where matched, always labelled "reported, not verified" |
| Propagation | First-seen time per country and language, taken from the batch stamp or `PAGE_PRECISEPUBTIMESTAMP` (present in 44–58% of records), with ±15 min uncertainty | Order correctness on 50 hand-checked stories |
| Signals | Volume-share series per H3 cell, ADM1 region, entity and theme: STL with robust MAD z-scores, BOCPD change points, and Chronos-2 quantile surprise on the top ~1k series. The explanation is a computed attribution of the contributing stories | Pre-registered ledger; precision@k and lead time against UCDP and GDACS outcomes, next to naive-spike baselines; losses published |
| Coverage Gap | Empirical-Bayes ratio of severity (GDACS, USGS × Kontur exposure, FIRMS fire power, UCDP) to attention (deduped volume, language spread, pageviews); low-evidence cells shrink toward neutral | Rank agreement with the CARE and EU forgotten-crisis lists; weight sensitivity analysis |
| Brief, Explain | The brief is a deterministic assembly of cached deltas. "Brief me" and "Explain" use Claude `search_result` blocks for native citations; Sonnet 5.5 runs only on demand | Pairwise human preference vs a headline-list baseline, with order swapped; judge–human κ; $/brief |

**MLOps:** promptfoo and pytest gate CI on stored golden outputs, with a nightly eval job on top. LLM traces use OpenTelemetry GenAI conventions into Grafana Cloud (its free tier covers 30k generations), so there is no separate tracing vendor. Drift monitors track language mix, novelty, refusal rate and cost per day. API version 2026-10-21 rejects `temperature`, so evals report variance over repeated runs.

**Trust surfaces:** `/trust` (the table above, live), `/signals` (ledger and scorecard with "verify this hash"), `/stats` (freshness, p95, WAU from cookieless daily-salted hashes, $/month), `/methods`, and a CI-generated "What's real" table in the README.

**How pre-registration works:** a scheduled GitHub Actions job attests each day's signal-ledger file with an artifact attestation. Because the repo is public, the attestation lands in Sigstore's public transparency log, the same machinery that signs our builds. The track record therefore can't be edited after outcomes are known, and anyone can verify it with `gh attestation verify`. Cost: $0.

## 11. Platform, infrastructure, CI/CD and cost

- **Topology.** One Hetzner EU VM (4 vCPU, 8 GB) runs Postgres, Dagster, FastAPI, auth and workers under Docker Compose, with no open ports (Cloudflare Tunnel). Cloudflare also provides DNS, WAF, CDN for immutable Arrow cubes, R2 and a PMTiles Worker; live updates use an SSE doorbell with 25 s heartbeats.
- **RAM budget.** Postgres ~2.5 GB; API, auth and workers ~1.5 GB; Dagster ~0.8 GB. The int8 embedder (~0.5 GB) is the only resident model; GLiNER2, MiniCheck and Chronos-2 run as batch jobs that load, process and exit.
- **IaC.** OpenTofu 1.13 in layered stacks (bootstrap, platform, edge, observability, github, vercel), with encrypted state on R2, plan comments on every PR, nightly drift checks and Conftest policies.
- **CI/CD.** GitHub Actions in a free org (for the merge queue) with one required `ci-ok` check: SHA-pinned actions, zizmor, harden-runner, Renovate with a release-age delay, CodeQL, Grype (with an ADR on the Trivy compromise), Docker Hardened Images, Syft SBOMs, SLSA L3 provenance and release-please. Backend PRs replay a golden 6-hour GDELT slice in Testcontainers.
- **Deploys are pull-based, without Kubernetes.** `deploy/prod.lock` lists image digests. A systemd reconciler on the VM verifies each digest's attestation, then runs migrations and restarts.
- **SLOs.** OTel feeds Grafana Cloud Free and errors go to Sentry; a public status page reports these:

  | SLO | Target |
  |---|---|
  | API availability | 99.5% |
  | Lens readout latency | p95 < 300 ms |
  | GDELT windows queryable within 30 min | 99% |
  | Alerts delivered within 10 min of their batch | 95% |
  | Briefs delivered by 07:15 local time | 99% of days |

- **Resilience.** pgBackRest backs up to R2 with point-in-time recovery. A quarterly timed DR drill builds a fresh VM with OpenTofu, restores, and replays missed GDELT intervals from the ledger. A last-good static snapshot keeps the demo alive while the API is down.
- **Guardrails.** An app-enforced daily LLM token budget that degrades gracefully, a Modal GPU-seconds cap, `maximum_bytes_billed` on BigQuery backfills, and a public $/month panel.

| Monthly item | Cost |
|---|---|
| VM: CAX21 at €10.49 + IPv4 if Hetzner's Cost-Optimized line is orderable (marked "currently not available" on 2026-10-28); otherwise CPX32 at €35.99 | ~$13 / ~$41 |
| R2: raw zips, lake, basemap extract, backups | ~$2–3 |
| Claude (hard cap) | ≤ $25 |
| Vercel Hobby, Cloudflare Free, Grafana/Sentry free tiers, Actions on a public repo, Modal credits | $0 |
| Domain | ~$1 |
| **Total** | **~$40 on CAX21; ~$55–60 on CPX32 with a $10 LLM cap** |

The CPX32 fallback runs about 15% over target. The cost ADR says so openly.

## 12. What I deliberately cut

- **Breadth layers** (flights, ships, markets, weather, prediction markets): World Monitor's turf, with licensing and cost risk.
- **Scores without backtests and outlet bias ratings**: opaque, and Ground News already sells ratings.
- **A free-roaming chat agent driving the UI**: bounded, evaluated workflows instead, which also removes the Vercel AI SDK and agent frameworks.
- **Social media and Telegram**: platform terms, personal data, moderation burden.
- **Private individuals**: only notable, Wikidata-linked entities are shown.
- **Full text, per-article summaries, quotes in AI text, publisher images by default.**
- **Kafka, NATS, ClickHouse, Qdrant, Kubernetes, Rust, WebGPU, Google 3D Tiles, self-hosted LLMs**: each fails its measured trigger at this scale.
- **Teams, real-time collaboration, native apps**: single-user boards and a PWA instead.

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Framing from headlines and ledes is thin, and translated documents carry fewer named entities | Minimum evidence per bloc; explicit "insufficient evidence" states; an offline measurement of the headline-only penalty against SemEval-2023 T3 |
| Hallucination or misattribution (the theories in the Perplexity and Cohere suits) | Cited, MiniCheck-gated sentences; verbatim-overlap rejection; no quotes; ≥3 sources; "AI-generated from N sources" label (EU AI Act Art. 50(4)); opt-out and takedown |
| Early warning reads as forecasting | Framed as "attention anomalies"; pre-registration; published baselines and losses. MIRAI agents reach only ~30 F1 on GDELT, so the scorecard itself is the product |
| GDELT degradation: GDELT 5, gaps, files that 404 for minutes | Per-file retry, a ledger, a gap registry, golden-file contract tests, an RSS connector, a freshness banner |
| Solo scope | Phase 4 is already a complete, unique product. Cut order if behind: Constellation → MCP App → Chronos-2 → export formats |
| Misuse as surveillance tooling | No individuals, no social media, no precise locations of people; an abuse contact |
| Single-VM failure | PITR backups, a timed DR drill, a CDN snapshot fallback, an honest 99.5% SLO |
| Being read as a World Monitor clone | Story-first information architecture, no layer menu, a README differentiation table, a distinct visual identity |

## 14. Resume bullets and headline metrics

Bullets are filled only from the measured metrics ledger. **Bold** values are placeholders.

1. Built GlobaLens, an open-source multilingual news-intelligence platform (live, no signup) that turns every 15-minute GDELT update in 60+ languages (~340k articles/day) into cited, versioned story case files; held p95 freshness under **N** min with a self-healing, ledger-based ingester (**99.x%** of windows on time).
2. Designed StoryStream, an online cross-lingual story clusterer. Scored pairwise F1 **X** (monolingual) / **Y** (crosslingual) on the Miranda 2018 benchmark (published: 94.1 / 84.0) at **Z** ms p95 per article on 4 vCPUs.
3. Shipped Perspective Diff, a per-story framing comparison across language blocs where every statement is cited and faithfulness-checked. Built a 300-item, two-annotator gold set (κ = **K**), and cut cost per story **M×** by distilling the LLM labels.
4. Built explainable early-warning signals backed by a pre-registered, Sigstore-timestamped ledger. Precision@k and lead time against UCDP/GDACS are published nightly, beside baselines.
5. Engineered watch-lenses: standing geo-temporal queries evaluated set-based on each batch (p95 **< X s** at 10k lenses), with idempotent push/RSS/webhook delivery (95% of alerts within 10 min).
6. Ran the system for **$X/month** on one EU VM, with OpenTofu, SLSA L3-attested pull-based deploys, OTel SLOs and a timed DR drill (RTO **N** min).
7. Grew to **U** weekly users from journalism programs and humanitarian NGOs.

**Headline metrics:** freshness p95 and windows on time; pairwise/B-cubed F1; MiniCheck pass rate and citation precision; perspective κ; signal precision@k and lead time; alert latency; Lens readout p95; FPS at N points; $/month and $/brief; WAU.

## 15. Ten-phase sketch

Each phase takes ~3 weeks part-time and ships a tagged release, an updated live demo, at least one ADR, an eval delta and a 10-minute explain-back recording.

| # | Phase | Demo at the end | Proof metric |
|---|---|---|---|
| 1 | Honest live map | Real data on the globe with precision tiers; the Lens 1.0 geodesic readout; a freshness badge; v1 tagged with an honest retrospective | Freshness p95, windows on time |
| 2 | Stories, not articles | Dedupe, embedding bake-off, StoryStream v1, ranked lens stories, server-rendered story pages with OG cards, hybrid search | Dedupe ratio, baseline F1 |
| 3 | Case Files | Cited briefs and deltas, entities, Figures, as-of revisions, `/trust` v1 | MiniCheck pass rate, $/story |
| 4 | Perspectives (MLP) | Perspective Diff and Split Lens; StoryStream v2; the first 20 student users | κ, crosslingual F1 |
| 5 | Time | Chronoscope, propagation replay, Arrow cubes on the CDN, backfill of event windows plus the trailing 12 months | Cube p95, FPS, order accuracy |
| 6 | Tripod + Wire | Accounts, watch-lenses, the explain-why inbox, push/Atom/webhook delivery, Signals v1 with the Sigstore ledger | Alert latency, evaluator time |
| 7 | Brief + Boards | Morning Brief, Boards, cited export | $/brief, preference win rate |
| 8 | Infrared | Severity connectors, Coverage Gap, Signals v2, the public scorecard | Precision@k, lead time |
| 9 | Constellation + open data | Temporal entity graph, API keys, MCP tools, Parquet snapshots, embeds | MCP p95, usage |
| 10 | Launch | k6 load test at 10× expected traffic, DR drill, WCAG audit, open benchmark, an extracted OSS package, Show HN | WAU, RTO/RPO, Core Web Vitals |

**Hand-built depth kernels**, each with a blog post: the spherical-cap ∩ H3 coverage behind the Lens, StoryStream's online assignment and merge logic, and the bitemporal revision model.

## 16. Estimated size

About **65k LOC**, as an outcome rather than a goal: web app ~24k, API + MCP + auth ~8k, pipeline and connectors ~12k, ML/eval/annotation tooling ~7k, SQL ~4k, infra and CI ~3k, tests ~9k. The scope through Phase 4 is about 30k LOC and already stands alone as a unique product.
