# GlobaLens Atlas: the agentic globe

*Vision proposal, AI-native angle · 2026-10-28 · builds on research digest §0–§9*

**Name:** GlobaLens 3.0, *Atlas* edition. The product stays GlobaLens; the analyst is called Atlas.
**Tagline:** **Ask the world. Watch the answer.** Secondary: *See how the world sees the world.*

## 1. Pitch

Ask Atlas a question about world news and it answers by **operating the globe**:
- it flies the camera and sets the Lens;
- it splits the Lens to compare how outlets in different countries frame the same story;
- it draws propagation arcs and builds a timeline.

Every sentence streams with a citation, and a verifier model then checks each one. Underneath, Atlas reasons over a temporal graph of multilingual story clusters built from GDELT's ~340k articles a day in 60+ languages.

Each answer is a **Globe Script**: a typed program of camera, lens and time actions tied to cited sentences. You can replay it, fork it from any frame, or share it as a link or an embed. It can also play as a mini-globe inside Claude, via MCP Apps.

The same tools power a public MCP server. Every quality claim is tested in public by **AtlasBench**, an agent benchmark that runs against frozen data snapshots.

World Monitor shows everything happening everywhere. GlobaLens explains how the world sees one story, and shows its work.

## 2. Why this is not World Monitor

World Monitor's Analyst already streams schema-validated actions that move its map. Its WebMCP exposes `set_map_view` and `set_time_range`, and its MCP has bbox/radius filters plus a country-level `get_media_perspective`. So "an AI that moves the map" is not our claim. Our claims sit in the white space the research verified (digest §0):

| §0 white space | World Monitor (Oct 2026) | GlobaLens Atlas |
|---|---|---|
| 1. Per-story cross-lingual framing diffs | Headlines about a *country*, grouped by outlet country; stance fields empty | `perspective.compare(story)`: frames, entity roles, emphasis and omissions per country/language bloc, each claim cited and checked by MiniCheck |
| 2. Propagation | None found | Arcs from the first time each country and language covered a story, with lags and the wire services that carried it |
| 3. Attention vs severity | None found | Infrared mode: severity (UCDP/GDACS/USGS) against attention (GDELT coverage share, Wikipedia pageviews) |
| 4. H3/time-bucket agent tools | bbox/radius filters | `lens.query`, `h3.aggregate`, `kg.query(diff)`, `as_of` on every tool |
| 5. Location honesty | Not shown | Geocode precision shown everywhere; the benchmark penalizes claiming more precision than the data has |
| 6. Public evals | Forecast scores withdrawn under audit | AtlasBench + `/trust`: pass^k, faithfulness, claim-to-view, injection resistance, $/answer |
| 7. Multi-year replay | 7-day local snapshots | Read models that keep history, a 12-month backfill, historic windows |
| 8–9. Multi-lens instrument, narrated tours, MCP Apps | Map moves; no tours | Scrubbable, forkable Globe Scripts; split and pinned lenses; mini-globe MCP App |

Others differ in kind: Ground News compares partisan lean, Liveuamap is a curated conflict map, Kagi News a daily digest, Google Earth AI an earth-observation agent.

**Non-goals:** flights, ships, markets, instability scores, bias ratings, event prediction, full-text storage.

**License:** Apache-2.0 (World Monitor is AGPL, with paid MCP quotas).

## 3. Users and jobs-to-be-done

- **Lead persona: student explainers** in Model UN, debate and journalism. The first niche is 20–50 hand-recruited Model UN delegates.
  - *"I'm assigned Brazil on water security. Show me how Brazilian outlets cover it versus everyone else, with sources I can cite, in ten minutes."*
  - Served by a Delegate Brief template and citation export.
- **Journalists, OSINT hobbyists and newsletter writers.**
  - *"When a story breaks, show me where it started, who carried it, how framing differs by language, and what's being ignored."*
- **AI agents and developers, via MCP.**
  - *"Give my agent grounded, cited, geospatial news tools with a free tier."*
- **Hiring reviewers:** *"Show me AI-engineering judgment, not a wrapper"* (`/trust`, AtlasBench, ADRs).
- **Not served:** enterprise security teams, traders.

## 4. Feature set, ranked

| # | Feature | Wow moment | Novelty · size |
|---|---|---|---|
| 1 | **Atlas live answers (Globe Scripts)** | Ask "Why is everyone talking about lithium?" The camera tours Chile → DRC → China while each sentence lights up its sources. Hovering citation [3] flies a marker to that outlet's country. Scrub back, fork any frame, or ask in Spanish and get a Spanish answer citing Arabic sources | Novel · XL |
| 2 | **Perspective Split** | Ask "How did Indian vs Pakistani outlets cover the dam talks?" The Lens splits, and a chip reading "only Pakistani outlets mention X (5 sources)" turns green once verified | Novel · XL |
| 3 | **Point-and-ask Lens** | Park the Lens on the Sahel and ask "Why is this lit up?" Atlas knows what "this" means. Grab the globe mid-answer and it yields: "Paused. Continue from Gao?" | Novel · L |
| 4 | **Propagation Replay** | A story starts in Nairobi and arcs ripple out: "French-language outlets picked it up 9 h later, mostly via AFP copy" | Novel · L |
| 5 | **MCP server + mini-globe app** | In Claude, "Compare Brazilian and Argentine coverage of the summit" returns a cited comparison, an inline mini-globe playing the answer, and a deep link | Novel · M |
| 6 | **Atlas Briefs (deep research)** | An editable plan becomes a verified, chaptered briefing with a replayable tour and a bibliography export. A daily World Brief uses the same pipeline | Better · L |
| 7 | **AtlasBench + `/trust`** | Live pass^5, faithfulness and injection-resistance scores per model and release, each reproducible from a commit plus a snapshot | Novel · L |
| 8 | **Long Exposure + `as_of`** | Ask "What did we know at 06:00 UTC on 24 Feb 2022?" Atlas uses only data seen by then, and leakage of later data is graded | Better · L |
| 9 | **Infrared + Hotspots + attention forecasts** | Under-covered crises light up. Forecasts show intervals and the model's published backtest skill | Novel · L |

Table stakes are included too: hybrid search across languages, story pages with preview cards, view state in the URL, a freshness badge, and WCAG 2.2 AA.

## 5. Signature interaction: the Lens becomes a shared instrument

v1's gesture stays: you rotate the planet under a reticle. Now the Lens is **state shared between the user and Atlas**.
- **Shape and modes.**
  - A 25–3,000 km circle on the sphere: drag its edge or press `[ ]` to resize.
  - A time bezel and a topic filter.
  - Five modes: Viewfinder (live), Long Exposure (replay), Split (compare), Infrared (gaps) and Tour (script playback).
  - One SQL function, `lens_query(center, radius, window, topic, as_of)`, serves the user, Atlas and MCP clients.
- **Precision-aware.** The display reads "214 stories · 171 city-precise · 43 region-level". Country- or region-level geocodes fill regions and are never drawn as pins.
- **Deixis.** The Lens state travels with every Atlas turn, so "this", "here" and "since then" resolve without typing.
- **Control handoff.** One side drives at a time. Marching dashes and an "Atlas" label show when Atlas drives. Any drag, scroll or key press takes back control and sends Atlas an `interrupted` event.
- **Ghost lenses.** Dashed suggestions from Hotspots (e.g. "French-language coverage of Goma +4.1σ"). Accepting one plays a cached tour.
- **Speculative camera.** A place-name lookup on the question (no LLM) starts the flight in ~300 ms while Atlas thinks.
- **Record and narrate.** Manual exploration is recorded as a script. "Narrate my path" turns it into a tour.
- **No dragging needed (WCAG 2.5.7).** Click to centre, use the arrow keys, or type a ⌘K command (`lens kyiv 300km`, `time -72h`, `compare ar en`) that falls back to asking Atlas.

## 6. UX concept

**Desktop** uses the "Deep Field" system: near-black neutrals, one lime instrument accent, a colour-blind-checked orange↔azure tone scale, and panels at least 90% opaque.

```
┌ ◉ GlobaLens  [⌘K places · stories · or ask Atlas]          ● LIVE · data 7 min old ┐
├ IN THE LENS ──────┬──────────── globe ─────────────┬ ATLAS ───────────────────────┤
│ Sahel · 600 km    │       ╭╌╌╌╌╌ ATLAS ╌╌╌╌╌╮        │ ▸ plan: story → blocs → spread│
│ 214 stories ▲38%  │       ╰╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╯        │ perspective.compare · 4 · 1.4s│
│ story cards …     │   arcs · H3 surprise cells      │ Answer … [1][2]✓ [3]⚠         │
│ (screen-reader    │                    [locator]    │ [CompareTable] [Timeline]     │
│  representation)  │                                 │ Replay · Fork · Share · Report│
├ CHRONOSCOPE ▁▂▃▅▇█▇▅  ◀ ▶ 6h/s  chapters ●───●───●  ───────────────────── LIVE ──┤
```

- **Atlas panel, top to bottom:**
  - plan chips;
  - an operations log with one row per tool call, also written out as text for screen readers;
  - the streamed answer, whose citation chips flip to ✓ or ⚠ as verification finishes;
  - generated cards: CompareTable, PropagationTimeline and LensCard.
- **Chronoscope.** The timeline doubles as the script scrubber, with chapter ticks aligned to paragraphs.
- **Motion budget.**
  - At most one flight per two sentences, each 0.8–2.4 s.
  - A "camera follows Atlas" toggle.
  - Jump cuts under reduced motion.
  - Freeze-frame for autoplay (WCAG 2.2.2).
- **Mobile.**
  - Full-screen globe, with Atlas in a Base UI Drawer (snap points at 120 px, 50% and 92%).
  - The Lens re-centres in the visible area.
  - Scripts play as swipeable chapters.
- **Landing.** No signup. The hourly "World right now" tour autoplays from cache, so it costs nothing extra in LLM calls.

## 7. Data sources

| Source | Role | Terms |
|---|---|---|
| GDELT GKG 2.1, English + translated streams (15-min files; the GDELT APIs are degrading, so they're avoided) | Articles: title (in 99.9% of records), image, locations with Geo_Type, themes, tone, outlet | Free, commercial use included; cite and link |
| GDELT Mentions | Velocity, first-seen times | Same |
| ~300 curated publisher RSS feeds | Ledes (≤200 characters) for grounding; fallback `SourceConnector` | Syndication; link out |
| UCDP GED Candidate | Conflict severity (monthly, ≤1-month lag); eval ground truth | CC BY 4.0; free token |
| GDACS, USGS, NASA EONET/FIRMS | Hazard severity, near real time | Open; attribution required |
| Wikipedia pageviews; Wikidata | Public-attention signal; entity IDs and outlet country/language | CC0 |
| GeoNames dump, Natural Earth, Kontur H3 population | Place lookup, boundary polygons, per-capita normalization | CC BY / public domain / CC BY |
| Protomaps PMTiles (zoom 0–12 extract on R2) | Basemap | ODbL attribution |
| BigQuery `gdelt-bq` (minimal columns, dry runs, byte caps) | 12-month backfill, historic windows | Free tier |
| VIEWS forecasts | External context only, labelled (license unverified) | — |

**Legal posture: a search engine, not a clipping service.**
- **What we keep:** metadata, titles, URLs, embeddings, ≤200-character ledes and derived facts. Full article text is never stored.
- **How AI text is built:** story cards synthesize ≥3 outlets in ≤120 words. Interactive answers state their source count and abstain below two.
- **Guardrails on AI text:** no quotes; any 8+-word overlap with a source is rejected; everything carries an "AI-generated from N sources" label (EU AI Act Art. 50(4)).
- **Publisher controls and provenance:** publishers can opt out. Every row carries `source, license, attribution, commercial_ok`, and CI fails on an unlicensed source.

## 8. Architecture and stack

```
GDELT GKG/Mentions (EN+TR, 15 min) · RSS ledes · UCDP · GDACS/USGS/FIRMS · pageviews
   │ ingest worker: ledger · MD5 · per-file retry · hourly reconciler · gap registry
   ▼                                                 R2: raw zips + Parquet (DuckLake)
PostgreSQL 18 · PostGIS · h3 · pgvector · pgmq  ◄── archive · backfill · eval worlds
   bi-temporal read models · Story Graph · H3 rollups · answers/scripts
   │ pgmq: embed (ONNX CPU) → StoryStream → Haiku Batch (cards, perspectives) → MiniCheck
   ▼
FastAPI monolith: REST + Arrow · SSE · Atlas runtime · MCP (Streamable HTTP, Apps, Tasks)
   │ Cloudflare Tunnel · WAF · cache · Turnstile          Anthropic API (Haiku/Sonnet 5.5)
   ▼
Next.js 16 on Vercel: persistent MapLibre + deck.gl globe · Atlas panel · script player
Claude / VS Code / M365 Copilot ──MCP──► same ToolRegistry ──► mini-globe MCP App
```

| Layer | Choice | Why it earns its place |
|---|---|---|
| App shell | Next.js 16.4 (Cache Components), Vercel Hobby | Keeps the globe mounted across routes; server-renders pages with preview images; serves static chunks from R2 via `assetPrefix`, so the free tier's bandwidth cap only meters HTML |
| Map | MapLibre GL JS 6.16, pinned | Real cartography, a globe that morphs to a flat map on zoom, native heatmap on the globe |
| Data layers | deck.gl 9.4 `MapLibreOverlay`, interleaved WebGL2 | Typed-array points, H3 cells, ArcLayer (`cullMode:'none'`), GPU time filtering |
| Transport | Arrow IPC + flechette in a Web Worker | Closed 15-min buckets are CDN-cacheable; decodes 2–7× faster than arrow-js |
| Agent UI | AI SDK v7 `useChat` (client only), shadcn AI Elements patterns | Typed tool-call states and approvals. Python speaks the stream protocol; fallback is a ~300-LOC SSE client |
| Script player | Own TypeScript reducer (Zustand), nuqs URL state | Deterministic replay, fork and scrub: the core frontend piece |
| Mini-globe | d3-geo orthographic renderer | One renderer for preview images (Satori can't run WebGL), the MCP App, embeds and low-power mode |
| UI kit | Tailwind 4.3, shadcn/ui (Base UI), Motion 14, cmdk, TanStack Query, uPlot, React Aria `useMove` | One library per job: panels, ⌘K, server-state cache, Chronoscope charts, Lens ring |
| API | FastAPI 0.162, Python 3.13, modular monolith | REST/Arrow, SSE, Atlas and MCP in one process, beside the ML and eval code |
| Agent runtime | ~2k LOC on the Anthropic Python SDK; no framework | Needs native citations, prompt caching, effort control, refusal handling and a spend governor; frameworks hide prompts |
| MCP | Official MCP Python SDK, Streamable HTTP, inside FastAPI | Same tool registry as Atlas, so one surface and one eval suite; Apps for the mini-globe, Tasks for briefs |
| Database | PostgreSQL 18 + PostGIS 3.6 + h3-pg 4.2.3 + pgvector ≥0.8.7 + pg_partman + pgmq | Geo, H3, vectors, queues, history-keeping read models and the Story Graph in one engine. pgvector ≥0.8.7 is a CVE fix managed hosts haven't shipped |
| Lake | Parquet on R2 + DuckLake 1.0 (Postgres catalog) + DuckDB | Replay log, history beyond 30 days, eval snapshots; costs nothing idle |
| Pipeline | asyncio ingest worker + pgmq | The ingestion ledger doubles as the partition map. pgmq adds retries without a second scheduler |
| Embeddings | GlobaLens-Embed (256-d Matryoshka `halfvec`), ONNX Runtime int8, CPU | Titles average ~20 tokens, so 4 ARM cores embed 340k/day after dedup. GPUs only for backfills and fine-tuning |
| LLMs | Claude Haiku 5.5 (Batch API for bulk; thinking off/low for interactive); Sonnet 5.5 | Haiku at $0.10/$0.50 per million tokens makes per-story work affordable. Sonnet synthesizes briefs and judges evals |
| Verifier | MiniCheck-Flan-T5-L (0.8B), CPU | Checks each claim against its source (75.0 on LLM-AggreFact) at near-zero cost |
| Signals | STL/MAD + BOCPD; Chronos-2 small | Apache-2.0, and fast enough on CPU for ~4k country/province series |

**Fits on 8 GB:** ~10M hot article rows (~6 GB disk); article vectors kept only 7 days; binary-quantized centroid index <0.2 GB RAM; resident Postgres 2.5 GB, Python ~1 GB, models ~1.2 GB.

### The Atlas runtime

1. **Context.** Each turn carries the cached system prompt and tool schemas (~6k tokens, at $0.01 per million cached tokens), the current Lens state and the conversation.
2. **Twelve tools, capped.**
   - Nine data tools:
     - `story.search`: full-text plus pgvector, fused by Reciprocal Rank Fusion in SQL;
     - `story.get`, `lens.query`, `h3.aggregate`;
     - `perspective.compare`, `propagation.trace`;
     - `kg.query`: neighbors, timeline, diff and path;
     - `attention.gap`, `forecast.attention`.
   - Three instrument tools: `globe.view`, `globe.split`, `globe.overlay`.
   - **Instrument tools are pure functions of state.** The server computes what the new view contains and returns it, so Atlas sees exactly what the user will see, with no browser round trip.
3. **Evidence.**
   - Data tools return Claude `search_result` blocks: outlet, title, lede or derived facts, country, language, time.
   - Computed facts (lags, divergences, gap scores) arrive as blocks linked to a methods page and traceable to their articles.
   - Native citations map back to article and story IDs.
   - Citations can't be combined with structured outputs, so an answer is text plus tool calls.
4. **Script builder.**
   - A stream mapper converts Anthropic events into the AI SDK protocol and records the script, anchoring each action to the sentence it precedes.
   - Scripts are stored under `/a/{id}` with model, API version, prompt hash, tool trace, cost and `as_of`. Forks keep a `parent_id`.
   - API version 2026-10-21 rejects `temperature`, so **stored scripts are the reproducibility mechanism**.
5. **Verification after streaming.**
   - MiniCheck checks each cited sentence; overlap, quote and claim-to-view checks run alongside.
   - Unsupported sentences are struck through.
6. **Spend governor and approvals.**
   - A daily dollar ledger per feature. When budget runs short, features shed in order: briefs first, then interactive answers, leaving cached tours.
   - Session quotas, plus a Turnstile check after N anonymous questions.
   - Refusals are handled explicitly.
   - Side effects (pinning a watch-lens, starting a brief) need the user's approval.
7. **Fixed workflows where the path is predictable; an agent where it isn't.**
   - Tours and Briefs run a fixed sequence: plan, tool calls, one synthesis call, batched where possible.
   - Only interactive questions run the open loop, capped at 8 tool calls.
   - There is a single agent, with no multi-agent orchestration.
8. **Answer cache.** Keyed by question-embedding bucket, Lens hash and GDELT batch. Closed buckets never change, so cache invalidation stays simple.

```json
{"v":1,"as_of":"2026-10-28T14:15Z","steps":[
 {"view":{"center":[39.2,21.5],"zoom":4.1,"lens_km":400,"window":["-72h","now"]}},
 {"say":"Talks in Jeddah lead Gulf and Sudanese coverage [1][2].","cite":["a:91f2","a:77c0"]},
 {"split":{"story":"s:8f3a","by":"language","groups":["ar","en","fr"]}},
 {"overlay":{"arcs":"propagation","story":"s:8f3a"}}]}
```

The script schema is a public contract, generated Pydantic → JSON Schema → TypeScript. CI replays stored scripts on every player build and diffs key frames, so shared links never break.

## 9. ML/AI components and how each is evaluated

| Component | Method | Evaluation (published on `/trust`) |
|---|---|---|
| **StoryStream** (core ML artifact) | Candidates from nearest-neighbour search over 72 h-decayed centroids plus BM25. Features: Matryoshka cosines (64/128/256 dims), entity overlap, shared province, time gaps, source diversity. A LightGBM ranker plus a calibrated new-cluster classifier; an hourly merge/split pass sends borderline cases to Haiku | Miranda 2018 pairwise and B-cubed F1 (published: 94.1/97.1/94.2 monolingual, 84.0 cross-lingual); 1k in-house pairs in 10 languages; docs/s, p95 latency, ablations |
| **GlobaLens-Embed** | Bake-off between harrier-oss-v1-270m, EmbeddingGemma 2 and e5-small (Qwen3-0.6B as ceiling), then a Matryoshka fine-tune on Modal ($5–20) | SemEval-2022 T8 Pearson (best published 0.816–0.818), nDCG@10 on 200 queries, CPU docs/s; weights released only if data terms allow |
| Story cards | Haiku Batch JSON with `source_ids`; needs ≥3 articles from ≥2 outlets; re-summarized only on material change | MiniCheck faithfulness on 300 labelled cards; zero 8+-word overlaps; ALCE citation precision/recall |
| **Perspective engine** | Per bloc: frames (Media Frames Corpus), entity roles, emphasis, unique claims, omissions; Jensen–Shannon divergence | 200 items with a second annotator (κ); claim-support rate; SemEval-2023 T3 offline only |
| Entity linking | Card-call entities matched against a local Wikidata alias table with a popularity prior; Haiku decides low-confidence cases | Accuracy@1 on 200 items; Mewsli-9 subset offline |
| Location honesty | Geo_Type 3/4 as points, 1/2/5 as regions; the earliest city mention is primary | Province-level accuracy on 200 items; over-precision rate in AtlasBench |
| Hotspots | STL + robust z-scores + change-point detection on coverage share | Weekly precision@k vs UCDP spikes and Wikipedia's Current Events portal |
| Attention forecasts | Chronos-2 quantiles on volume-normalized series | CRPS and 50/90% coverage vs no-change and seasonal-naive baselines, using data as it stood at forecast time; losses published |
| Attention gap | Coverage shortfall against a fitted, severity-based expectation | Rank agreement with CARE and EU forgotten-crisis lists; open methods page |

**AtlasBench: serious agent evals.**
- **Frozen data, stochastic agent.** Three 72-hour historic snapshots plus a weekly rolling one are restored into Postgres (Testcontainers in CI).
- **300 tasks in eight categories:**
  - grounded lookup, cross-lingual comparison, temporal and graph questions;
  - propagation, graded with a lag tolerance;
  - instrument operation (split-lens centres within 50 km, time-window overlap ≥0.7);
  - gaps and forecasts, which must state uncertainty;
  - abstention;
  - adversarial cases: injections planted in titles, quote-baiting, requests for full text, centroid-precision traps.
  - The planted titles are the only synthetic data in the project. They are labelled and never shown to users.
- **Programmatic graders:**
  - trajectory rules;
  - *citation validity*: every cited ID was returned by a tool in that run;
  - *claim-to-view consistency*: each cited story's place and time fall inside the Lens and window on screen when its sentence plays;
  - *no future leakage* under `as_of`.
- **Model graders.** MiniCheck per claim, plus a Sonnet 5.5 rubric judge that compares pairs in both orders, calibrated on 200 human labels (Cohen's κ).
- **Reliability and cost.** pass^k with k = 3–5, since temperature can't be pinned; cost per task; p95 time to first action.
- **Gates.**
  - PRs touching agent code, tools or prompts run 40 tasks (≈$0.08). A 3-point drop or any safety regression blocks the merge.
  - The full suite runs weekly.
  - A monthly burst compares Haiku 5.5, Sonnet 5.5 and the open-weights gpt-oss-20b.

## 10. Platform, infrastructure, CI/CD

- **Topology.**
  - One EU ARM VM runs Docker Compose (postgres, api, worker, embedder, cloudflared, Grafana Alloy) behind Cloudflare Tunnel, with no open ports.
  - Vercel hosts the web app.
  - R2 holds the lake, tiles, backups and static chunks.
  - Modal handles GPU bursts.
- **IaC.** OpenTofu manages Hetzner, Cloudflare, GitHub, Grafana and Vercel. State is encrypted in R2, and a nightly drift plan runs.
- **CI.** GitHub Actions, with the repo in a free organization so the merge queue works. Jobs:
  - affected-package lint, types and tests (Turborepo, uv pytest);
  - GDELT parser tests on saved files;
  - PG18 migration tests and an OpenAPI → TypeScript drift check;
  - script replay compatibility and the AtlasBench gate;
  - Playwright + SwiftShader globe screenshots, axe and a k6 smoke test.
- **Supply chain.**
  - SHA-pinned actions, checked with zizmor and harden-runner.
  - Syft SBOMs, scanned with Grype. Trivy is avoided after its March 2026 compromise (CVE-2026-33634).
  - SLSA L3 provenance, verified with `gh attestation verify` before deploy.
  - Renovate with release-age delays, to keep pace with Next.js's monthly security releases.
- **Deploy.** release-please; deploys go over Cloudflare Access SSH, with health checks and automatic rollback. WAL-G sends point-in-time backups to R2, and a restore drill runs weekly.
- **Observability.** OpenTelemetry agent spans go to Grafana Cloud Free (30k LLM generations included); errors go to Sentry. SLOs:
  - 99.5% API availability;
  - p95 Lens query <300 ms;
  - 99% of GDELT windows queryable within 30 min;
  - Atlas p95 time to first action <2.5 s;
  - ≥95% of cited claims verified.

| Steady-state cost | $/month |
|---|---|
| Hetzner CAX21 EU (4 vCPU ARM, 8 GB) + IPv4 | ~12.6 |
| R2 (lake, PMTiles, backups, static) + domain | ~3 |
| Vercel Hobby, Cloudflare Free, Grafana Free, Sentry Developer, GitHub Actions, Modal credits | 0 |
| LLM, capped by the governor: batch cards + perspectives ~15 · interactive ≤8 · tours/briefs ~5 · evals ~6.5 | ≤34.5 |
| **Total** | **≈ $50** |

LLM lines include a 30–40% tokenizer allowance. Bursts: backfill embeddings (Modal credits), monthly model comparison (~$10), Vercel Pro for a launch month.

## 11. Deliberately cut

- **Flights, ships, markets, instability indices, bias ratings.** World Monitor and Ground News already own these.
- **Dagster.** The ingestion ledger already tracks ~6 assets, and ~1 GB of RAM doesn't pay off on an 8 GB box. Revisit past 15 assets.
- **Kafka and NATS.** pgmq plus an SSE "new batch" ping is enough. Add NATS at ≥3 consumers of the same events.
- **ClickHouse, Martin, Kubernetes.** DuckDB over DuckLake, Arrow buckets and one VM cover the measured load.
- **Rust, C++, WASM, a WebGPU lab.** There's no measured hot path, and the BigQuery minimal-column backfill removes the case for a custom parser.
- **Separate vector or graph databases.** Postgres edge tables and the centroid HNSW index suffice.
- **Agent frameworks, multi-agent orchestration, a public SQL sandbox.** Typed tools are safer, cheaper and easier to evaluate.
- **Self-hosted production LLMs, Langfuse, promptfoo, GLiNER2.** Grafana traces; one custom harness; the story-card call already extracts entities.
- **Email digests, per-user memory, voice, comments, Google 3D Tiles.** Watch-lenses get Atom feeds instead of email.
- **WebMCP as a selling point.** It's table stakes, so it stays a ~100-LOC add-on (instrument actions are already typed).

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| "Agent slop": dizzying camera, wrong citations | Motion budget, claim-to-view grader, verification chips, camera toggle, low-motion Brief mode |
| LLM bill blowout | Governor with hard daily caps, cached landing tours, answer cache, Turnstile, sign-in for deep briefs |
| Misattribution or substitutive summaries (cf. the Cohere and Perplexity suits) | Native citations, MiniCheck gate, no quotes, overlap rejection, ≥3-outlet cards, AI labels, Report button, takedowns |
| Prompt injection via titles | Tool outputs are evidence only; side effects need approval; red-team target is zero successes |
| Framing read from headlines and ledes is shallow | Labelled as such, sample sizes shown, abstain below N sources, κ-checked eval set |
| World Monitor ships per-story perspectives | Ship Perspective Split by Phase 4; lead on StoryStream, Globe Scripts, public evals and Apache-2.0 |
| GDELT degrades or GDELT 5 changes formats | `SourceConnector` with RSS fallback, parser tests on saved files, gap registry, last-good banner |
| Hetzner CAX availability or repricing | Fits in 8 GB, and IaC makes switching providers a variable change. The CPX32 fallback (~€36) temporarily breaks the budget |
| API/SDK churn (Claude API, AI SDK stream protocol, AI SDK Elements deprecation) | Pinned versions, thin adapters with contract tests, AI Elements patterns copied into the repo |
| Name collision: OpenAI's "ChatGPT Atlas" browser (from memory, unverified), MongoDB Atlas | Keep "Atlas" internally; have "Meridian" ready as the public name |
| Solo scope creep; "who reviewed this?" | Shippable phases, 12-tool cap, ADR-enforced cuts; hand-written `lens_query`, StoryStream assignment and claim-to-view grader, each with a blog post |

## 13. Resume bullets and headline metrics

Bracketed numbers are targets; published bullets use only measured values from the metrics ledger.
- Built **Atlas**, a map-operating AI analyst that answers as replayable, cited Globe Scripts:
  - **[90%] task success and [0.75] pass^5 on a 300-task public benchmark**;
  - **[$0.002] per answer**, with **[1.8 s]** p95 time to first action.
- Designed **AtlasBench**, frozen-data agent evals with graders for trajectory, citation validity, claim-to-view consistency, future-data leakage and injection, plus a κ-calibrated LLM judge. It gates CI and caught **[N]** regressions before merge.
- Shipped **StoryStream**, online multilingual story clustering over ~340k GDELT articles a day:
  - **[F1] on Miranda 2018** (published: 94.1 English / 84.0 cross-lingual);
  - **[X ms]** p95 assignment time on 4 ARM vCPUs.
- Fine-tuned **GlobaLens-Embed**, a 270M multilingual Matryoshka model, to **[0.80] Pearson on SemEval-2022 T8** (best published 0.818) for under $20 of GPU.
- Built a per-story **cross-lingual framing engine** with every claim cited and verified (**[93%]** claim support, κ-validated). Served through a public **MCP server and MCP App** used by **[N] agents a week**.
- Ran the whole system for **≤$50/month all-in**, with 99% of 15-minute windows queryable within 30 minutes. Public `/stats` and `/trust` pages show the numbers.

**Headline metrics:** AtlasBench success and pass^k, faithfulness, claim-to-view, injection resistance, $/answer, time to first action, Miranda F1, T8 Pearson, freshness, $/month, weekly users, MCP calls.

## 14. Ten-phase sketch (~34 weeks part-time)

| Phase | Ships (demoable) | Proof added |
|---|---|---|
| 1. Honest globe (3 wk) | Monorepo, OpenTofu, VM + PG18; self-healing GKG ingester (EN + translated); H3 rollups and Arrow buckets; MapLibre + deck.gl spike (arcs, picking through the globe-to-flat transition); basic Lens; location honesty; provenance page; `v1-hackathon` tag + retrospective | Live real-data globe; freshness p95 |
| 2. Stories, not headlines (3 wk) | Embedding bake-off; StoryStream v0; minimum-coverage threshold; verified story cards; cross-language search; story pages with preview cards | Miranda baseline; card faithfulness |
| 3. Atlas v0 (4 wk) | Tool registry; agent loop with native citations; stream protocol; instrument tools; record, replay and share scripts; control handoff; governor; AtlasBench v0 (60 tasks) + CI gate | Task success, $/answer, time to first action |
| 4. Perspective Split (3–4 wk) | Outlet registry (Wikidata + curation); RSS ledes; perspective engine + MiniCheck; Split Lens; first Model UN users | Claim-support rate, κ |
| 5. Propagation + Chronoscope (3 wk) | First-seen arcs; wire-copy detection (MinHash); lag metrics; Chronoscope synced to chapters; ghost lenses v0 | Lag accuracy on 50 hand-checked stories |
| 6. Atlas everywhere (3 wk) | MCP server on the shared registry; mini-globe MCP App; API keys (Better Auth, GitHub sign-in); quotas; embeds | External MCP calls; MCP eval subset |
| 7. StoryStream v1 + GlobaLens-Embed (4 wk) | LightGBM ranker; merge/split with Haiku adjudication; Matryoshka fine-tune; ablations; model card; blog post | Miranda F1, T8 Pearson, latency |
| 8. Time machine + Story Graph (4 wk) | `as_of` everywhere; DuckLake; 12-month backfill (BigQuery + Modal); entity linking; `kg.query`; entity pages; historic windows reused as eval snapshots and demo replays | Entity-linking accuracy; zero future leakage |
| 9. Briefs + Infrared (3–4 wk) | Plan → research → verify → publish Briefs; Delegate Brief + citation export; daily World Brief; hourly cached tours; watch-lenses with Atom feeds and "since you last looked" diffs; attention-gap index | Verified-sentence rate; weekly Model UN users |
| 10. Signals, AtlasBench v1, launch (4 wk) | Hotspots + backtested Chronos-2 forecasts; 300-task AtlasBench (κ, model comparison, red team); `/trust`; k6 at 10× load; accessibility audit; Show HN; `@globalens/lens` and `globe-script` open-source packages | Headline metrics frozen into the resume ledger |

Stopping after Phase 3 leaves a novel, evaluated agentic globe; after Phase 6, a differentiated product with an MCP surface.

## 15. Estimated size

| Area | LOC |
|---|---|
| Web app (Atlas panel, pages, ⌘K, Chronoscope, trust/stats) | 11k |
| `@globalens/lens` (instrument, script player, workers) + mini-globe | 6.5k |
| API, Atlas runtime, MCP, governor, verification | 9k |
| Tools (lens, search, perspective, propagation, graph, gap, forecast) + SQL | 7k |
| Ingestion, connectors, rollups, history-keeping writes | 6k |
| ML (StoryStream, embedding fine-tune, extraction, linking, signals) | 5k |
| AtlasBench + StoryStream benchmark harness | 4.5k |
| IaC, Compose, CI | 2.5k |
| Tests (unit, integration, parser fixtures, Playwright, replay compatibility) | 9k |
| **Total** | **≈ 60k** (excluding task specs, prompts, generated clients) |

LOC is an outcome, not a goal. The resume lists measured capabilities, not line counts.
