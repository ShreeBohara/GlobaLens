# GlobaLens 3.0: The Living Planet

**Tagline:** *See how the world sees the world.* (Secondary, kept from v1: *See beyond the headlines.*)
**Hero line:** A weather radar for the world's attention. Live every 15 minutes, rewindable to 2015, honest about what it doesn't know.

## 1. Pitch

GDELT publishes metadata for about 340k news articles a day in 60+ languages, in 15-minute batches; translated sources outnumber English about 1.9 to 1. GlobaLens turns that firehose into one instrument instead of one more dashboard: a planet whose attention you can watch move.

Drag the world under the Lens and the place *develops* like a photograph. Counters roll, coverage arcs stream in from every country watching, and a cited 120-word briefing appears in about 2 s. Turn the time bezel and the planet rewinds through a decade of 15-minute frames, shown over that day's satellite imagery. Open a story and watch it cross borders and languages. Flip the lens filter to **Prism** to see how each country's press frames the story, or to **Infrared** to see what nobody covers. Every view is a URL, a share card, a six-second clip, an embed and an RSS feed.

The bar is earth.nullschool's craft. nullschool drew about 1.5M visitors in its first month on $11 of hosting, proof that beauty spreads. The engineering is graphics-grade: 1.5M live points at 60 fps, a past served as static CDN files, and public evals and costs.

**The first five seconds.** An SVG globe paints in under a second, then WebGL crossfades in. The camera starts over the visitor's longitude (inferred from the timezone, no permission prompt) and drifts to the day's fastest-spreading story. The Lens settles, arcs land, and a caption appears: "Right now, 31 countries are covering the floods in ___." Then the planet is yours.

## 2. Positioning: an observatory, not a situation room

World Monitor has about 90k stars and runs on v1's globe stack. It owns breadth: 468 feeds, 59 layer types, dense panels, AI dossiers, an instability index, a 622-command palette, MCP/WebMCP and an analyst that moves the map. Competing on layers would make GlobaLens a clone. It offers **one deep instrument over space, time and perspective** instead, built on the verified white space in digest §0.

| | World Monitor | GlobaLens 3.0 |
|---|---|---|
| Time | Local 7-day playback | A backfilled decade of 15-minute frames, served from the CDN (§0 #7) |
| Stories | Feeds and dossiers | Per-story propagation arcs with lag and amplifier metrics (#2) |
| Perspective | Country-level headline grouping via API; stance fields empty | Per-story framing diff by country bloc, every claim cited (#1) |
| Neglect | Not addressed | Infrared, an attention-vs-severity index (#3) |
| Location | No precision display (per its docs) | Precision shown as optical focus; centroids never drawn as pins (#5) |
| Lens and agents | Radius filters in its MCP; an analyst that moves the map | A pinnable consumer multi-lens (#8); narrated, cited Tours; an MCP App mini-globe with H3, time and gap tools (#4, #9) |
| Sharing | Embeddable live map | Every view is a Shot: card, clip, embed and feed |
| Trust and license | Forecast page (withdrawn); AGPL; Pro tier $39.99/mo | Live /trust and /stats pages (#6); Apache-2.0; no accounts |

Ground News compares coverage on a partisan axis; GlobaLens compares by geography and language, with no bias ratings. Liveuamap curates conflict icons; GlobaLens shows the whole planet's attention and its history. **Non-goals, stated in the README:** flights, ships and markets; risk scores; bias ratings; full article text; forecasting claims; user accounts; dense dashboards.

## 3. Users and jobs-to-be-done

- **Lead persona: the globally curious explainer.** Students, teachers and newsletter writers who need an understanding they can *show* others.
- **First niche: journalism and international-relations classrooms, including Model UN.** Each week, delegates research how "their" country's press frames an issue, and teachers project the daily Tour. Target: 20–50 users recruited by hand before Show HN.
- **Also served:** data journalists who need citable embeds, AI agents via the MCP App, and the HN and graphics crowd at launch.

**Jobs:**

- See where something broke and how far it spread (Viewfinder, arcs).
- Get briefed on an assigned country, and see how its own press and the world's press tell the story (Lens, Prism).
- Paste one accurate artifact anywhere (Shots).
- Watch a past moment unfold (Long Exposure).
- Find severe events nobody is covering (Infrared).

## 4. Ranked features and wow moments

| # | Feature | Wow moment | Novelty | Size |
|---|---|---|---|---|
| 1 | **Lens 3.0**: geodesic aperture 25–3,000 km, time bezel, detent, pins, Split | Slide the Red Sea under the ring: counters roll, arcs arrive from 23 countries, and a cited brief appears | novel (#8) | L |
| 2 | **Living globe**: orbit-to-street, 1.5M points, bokeh honesty, terminator, Satellite Day | Zoom from a dot-matrix planet to Khartoum's streets while imprecise stories stay out of focus | better | L |
| 3 | **Long Exposure**: decade replay, Chronoscope, interpolation, 4K stills | Type `2022-02-24 03:00Z`, press play, and watch the coverage storm form over Ukraine | novel (#7) | XL |
| 4 | **Propagation arcs** (StoryStream) | A story ignites in Lagos and ripples outward: "Spanish-language press +9 h" | novel (#2) | L |
| 5 | **Shots**: permalinks, OG cards, snapshots, 6-s clips, embeds, per-lens RSS | Press R for a vertical clip of arcs landing; the pasted link's card shows the same globe | better | M |
| 6 | **Lens Briefings** (cited, labelled) | Hover a citation and a ghost marker flies to the outlet's country | better | M |
| 7 | **Prism**: framing by country bloc | How Moscow, Kyiv, Delhi and Washington outlets told one summit, side by side, each claim cited | novel (#1) | XL |
| 8 | **Infrared**: attention vs severity | Over-covered capitals go cold while a Sahel flood with three stories glows | novel (#3) | L |
| 9 | **Tours, Director, Globe Cast, projector mode** | "Why is everyone talking about lithium?" flies Chile → DRC → China with cited captions; export as MP4 or project it in class | novel (#9) | L |
| 10 | **MCP App mini-globe** | In Claude, a live mini-globe answers and deep-links to the exact Shot | novel (#4, #9) | M |
| 11 | **/trust and /stats** | Live real-user fps, freshness, faithfulness and this month's bill | novel (#6) | M |

## 5. Signature interaction: the Lens, evolved

In v1 the Lens was a fixed screen circle that listed ten points. In 3.0 it becomes a **magic lens** (Bier et al. 1993) across space, time and perspective.

- **Aperture.** The lens is a true spherical cap. In *auto* mode it keeps its screen size and the km radius follows zoom. `[`/`]`, the edge handle, or typing `lens sahel 800km` *locks* the radius.
- **Time bezel.** An outer ring turns like a watch bezel, with detents at each hour and day. On mobile, a **two-finger twist scrubs time**.
- **Develop on settle.**
  - 0 ms: counters finalize.
  - 150 ms: a magnetic detent eases the lens toward the nearest density peak (one mean-shift step).
  - 300 ms: inbound arcs arrive (width = volume, color = tone).
  - Within 2 s: the briefing appears, or instantly if cached.
- **Modes and filters.** There are five modes named after camera techniques: Viewfinder (live), Long Exposure (replay), Prism (perspective), Infrared (neglect) and Tour (narration). Tone, Languages, Prism and Infrared also work as see-through filters inside the ring only; hold `⌥` to peek. Outside it, the planet desaturates like depth of field.
- **Pins and Split.** Pin up to three lenses, each with a HUD and an RSS feed. Split any two to stack shared stories in the middle and fan divergent coverage outward.
- **Directed state.** When the Director drives, the ring shows marching dashes and a "Director" label; any drag hands control back. All state is a Shot (§8), so undo is a stack of Shots.
- **Drag-free control (WCAG 2.5.7).**
  - Click any point to glide it into the lens; arrow keys pan.
  - ±32 px buttons set the aperture.
  - `,` `.` `J` `K` and Space drive time.
  - `P` pins, `C` compares, `S` takes a snapshot, `R` records a clip.
  - For screen readers the canvas is `aria-hidden`, and the Lens feed is the accessible view, with debounced `aria-live` summaries ("Khartoum, 48 stories, mostly negative, up 120%").

## 6. UX concept

**Deep Field principles.** The planet is the hero. Only information emits light: the UI is matte and the data glows. It is calm by default and loud only for anomalies. The default encoding is **surprise against baseline**, never raw volume, because raw volume mostly maps where newsrooms are. One encoding shows at a time, and low-sample cells fade to neutral.

**Desktop.** The screen holds the planet, the Lens, the HUD and an 88 px Chronoscope: a tone-stacked histogram with a brush, anomaly ticks, a LIVE edge, and a hatched band for GDELT's unpublished 14 Jun–2 Jul 2025. The Lens feed and story sheet are non-modal panels that open on demand. A ~20-verb palette (`lens`, `time`, `prism`, `gaps`, `tour`) falls back to "Ask the Director…".

**Mobile.** The globe is full-bleed; the Lens centers in the area the sheet leaves free. A Base UI Drawer snaps at 120 px, 50% and 92%, and the map stays live at the lower two. A twist scrubs time, Web Share sends clips, and a battery tier caps DPR and point count.

**Visual language.**
- One phosphor-lime accent (`#C3F344`) on near-black. Warnings always pair an icon with text, because deuteranopes can't tell amber from lime.
- A five-step orange↔azure tone scale with −/+ glyphs.
- Newsreader, Inter and JetBrains Mono; Deep Field, Paper and High-contrast themes generated from three OKLCH inputs.
- **Location honesty is optical.** City-level points are bokeh discs sized to their precision. Country-only geocodes (12% of English and 26% of translated articles) tint polygons and are never drawn as pins.

**Accessibility (WCAG 2.2 AA from Phase 2):** a drag-free Lens, targets of at least 32 px, a global Freeze-frame (2.2.2), reduced-motion and reduced-transparency paths, solid panels and a Table view. Hex traversal with Data Navigator is a stretch goal.

**Performance budgets, gated per release:**
- First SVG globe paint under 1 s; LCP ≤ 2.5 s, INP ≤ 200 ms and CLS ≤ 0.1 at p75.
- 60 fps at 1.5M points on an M1-class laptop (a rolling week is about 1.3M city-precise points).
- At least 30 fps at 250k points on a mid-range Android phone.
- Lens query under 4 ms; CDN hit ratio of at least 98%.

CI can't measure GPU frame rates, so each release runs a scripted perf-lab path on reference devices, and /stats publishes real-user frame times from Grafana Faro.

## 7. Data sources

| Source | Role | License |
|---|---|---|
| GDELT GKG 2.1 English + translingual, raw 15-min files | Backbone: titles (99.9%), character-offset locations, tone, language | Free, including commercial use; cite and link |
| GDELT on BigQuery (`gkg_partitioned`) | One-off decade backfill of minimal columns | $6.25/TiB after 1 TiB/month free |
| Curated RSS (~300 outlets) | Ledes for briefings and Prism; fallback `SourceConnector` | ≤200 characters shown, always linked |
| Wikidata, Media Cloud directory | Outlet → country/language | CC0 / research terms |
| Natural Earth, GeoNames, Protomaps PMTiles, NASA GIBS | Polygons, gazetteer, basemap, Satellite Day imagery | PD / CC BY / ODbL / NASA open |
| USGS, GDACS, EONET, FIRMS, UCDP Candidate; Wikipedia pageviews, Kontur population | Infrared severity; attention signal; per-capita normalization | Open; UCDP CC BY 4.0; CC0 / CC BY |

Every record carries `source, license, attribution, commercial_ok`. CI fails on any unlicensed source and generates the attributions page from these fields. ACLED, non-commercial feeds and Google 3D Tiles are excluded. GlobaLens stores **no full text, writes no per-article summaries and shows no publisher thumbnails**: the planet is the imagery.

## 8. Architecture and stack

**Principles.**
1. **Bake the past, stream the present.** A closed 15-minute bucket never changes, so it becomes an immutable, content-hashed Arrow file on R2 behind the CDN. Only "now" is computed, so a Show HN spike lands on the edge, not the VM.
2. **The Shot is the contract.** One versioned Zod schema holds camera, lens, pins, time, mode, encoding, story and a cited caption. URLs encode Shots; cards, embeds and the MCP App render them; Tours sequence them; the Director emits them; visual tests snapshot them.
3. **The client queries what it holds**, in a worker and on the GPU. The server handles search, history and LLM work.
4. **Degrade, don't die.** If the VM is down, history and the last good "now" keep serving. If the LLM budget is spent, briefings fall back to extractive digests.

```
GDELT 15-min files ─► VM pipeline (ledger, MD5, idempotent; H3 rollups in the load txn)
                         ▼
                  Postgres 18 hot window ─► FastAPI + MCP ─► Tunnel ─┐
                         ▼ closed buckets                              ▼
BigQuery backfill ─► DuckDB ─► R2 (cubes, packs, Parquet, PMTiles, now.json) ─► Cloudflare CDN
                                                                       ▼
   Next.js on Vercel: globe (MapLibre + deck.gl + GLSL), flechette worker, Director ─► Claude
```

**Data plane.**
- **Point packs.** 15-minute Arrow packs compact into hourly, then daily, packs. Each point is about 14 bytes, with positions quantized to about 600 m, since GDELT's best precision is a city centroid.
- **Time-cubes.** H3 res 2–5 aggregates: 15-minute frames for the whole decade at res 2–3, hourly at res 4–5. Estimated at about 5 GB, or roughly $0.08/month on R2.
- **Manifest polling.** Clients poll a 300-byte `now.json` every 30 s, with a 10 s edge TTL. 50k concurrent visitors make about 1.7k edge requests/s, nearly all cache hits, so no SSE fan-out or broker is needed.

**Render core.** One WebGL2 context; between frames only uniforms change.
- `LensExtension`, a deck.gl LayerExtension, computes angular distance to the lens center in the vertex shader, so it works in any projection.
- Hex frames interpolate between two cube buffers through a fractional playhead, so hourly data animates at 60 fps.
- Comet arcs (a start-time attribute plus a clock uniform) cost zero CPU. Bokeh discs use a Gaussian falloff scaled by precision.
- A MapLibre custom layer draws the terminator and city lights via `projectTile()`. "Develop" accumulates frames in a float framebuffer to make 4K stills.
- A **deterministic virtual-clock mode** renders both the Globe Cast MP4s and pixel-stable Playwright tests. A quality governor tunes DPR and the point budget from frame times.

| Component | Why it earns its place |
|---|---|
| Next.js 16.4 + React 19.3 | Globe mounted once in a persistent layout; cached SSR permalink and story pages with OG images |
| MapLibre GL JS 6.16 (pinned) | Cartography plus a globe that morphs into Mercator at z10–12, so orbit-to-street is built in |
| deck.gl 9.4.1 with `@deck.gl/maplibre`, interleaved on WebGL2 | Million-point binary attributes, GPU filtering, H3 and arc layers in MapLibre's depth buffer |
| flechette + h3-js 4.5 in workers | Arrow decoding 2–7× faster than arrow-js; cell math that matches the server rollups |
| Zustand 5, nuqs 2.10, TanStack Query 5; Tailwind 4.3, shadcn/ui (Base UI), Motion 14, React Aria `useMove`, uPlot | Camera state outside React renders, Shot ↔ URL, server cache; panels, Drawer, springs, an accessible ring and bezel, a 60 fps histogram |
| WebCodecs + an MP4 muxer; d3-geo as `@globalens/miniglobe` | In-browser clips and Tour export; Satori can't run WebGL, so one SVG/Canvas renderer serves OG cards, embeds and the MCP App |
| Vercel AI SDK v7 (`ToolLoopAgent`) | Typed tool parts let the Director emit validated Shots (shadcn AI Elements patterns) |
| Hetzner CAX21 EU ARM VM + Docker Compose | The cheapest always-on box (4 vCPU / 8 GB) for the only stateful tier |
| PostgreSQL 18 + PostGIS 3.6 + h3-pg 4.2.3 + pgvector ≥0.8.7 + pg_partman | 30-day hot window, rollups in the load transaction, story vectors; ≥0.8.7 for the 2026 CVE fix |
| FastAPI 0.162 + FastMCP | A typed API (OpenAPI → TS client) beside the data and the Python ML; the same functions are exposed as MCP tools |
| DuckDB 1.5 (h3, httpfs) | Backfill transforms and "what was here in 2019" queries over Parquet on R2 |
| Cloudflare R2, CDN, Workers, Tunnel | Zero-egress immutable assets, cached PMTiles, rate limits, no open ports on the VM |
| Claude Haiku 5.5 / Sonnet 5.5 | $0.10/$0.50 per MTok (half on Batch) with native `search_result` citations; Sonnet only for deep answers and judging |

**ADRs:**
- A polled CDN manifest, not SSE or NATS.
- pgvector indexes *stories*, not articles: about 100k vectors.
- Daily compacted Parquet, not DuckLake, since there are no concurrent writers.
- Ledger tasks plus a resumable `glb backfill` CLI, not Dagster, until there are more than five interdependent scheduled assets.

## 9. ML/AI components and evaluation

| Component | Serves | Method | Evaluation (on /trust) |
|---|---|---|---|
| Geo and source contracts | Bokeh, choropleths, arcs, Prism | `Geo_Type ∈ {3,4}` → points, {1,2,5} → polygons; primary location = earliest city mention; domain → country/language via Wikidata, Media Cloud, TLD and `srclc` | ADM1 accuracy on 300 hand labels; ≥90% of volume with a source country |
| Embedding bake-off | Clustering, search | harrier-oss-v1-270m vs EmbeddingGemma 2 vs e5-small, CPU int8, halfvec | SemEval-2022 T8 Pearson (best ≈0.818); Miranda F1; docs/s |
| StoryStream | Stories, arcs, dedup | v1: time-decayed centroids. v2: Miranda features → LightGBM ranker + calibrated new-cluster classifier; Haiku decides borderline merges | Miranda 2018 pairwise and B-cubed F1 (benchmarks: 94.1/97.1/94.2 monolingual, 84.0 crosslingual); p95 latency; ablations |
| Surprise baseline | Default encoding | Robust median/MAD per res-3 cell and hour of the week, with Bayesian shrinkage | Weekly precision@20 vs GDACS/USGS/UCDP events, compared with raw volume |
| Lens Briefings | Develop step | Haiku 5.5 with `search_result` citations; ≤120 words, ≥3 outlets, no quotes; rejects any ≥8-word overlap; quantized cache keys | Citation precision/recall, MiniCheck on 300 labels, $/brief, p95; promptfoo in CI |
| Prism | Perspective | Haiku Batch per country bloc: frames (Media Frames Corpus), entity roles, emphasis, omissions; MiniCheck on cited claims | Cohen's κ on 150–300 gold items; SemEval-2023 T3 offline only |
| Infrared | Neglect | Expected attention from severity, population and normal coverage (LightGBM/Poisson); gap = observed ÷ expected, with intervals | Overlap with CARE's "Breaking the Silence" and EU Forgotten Crisis lists |
| Director | Tours, Q&A | AI SDK v7 agent with about 8 read-only tools that emits Shots | 100-question golden set (place/time, recall@5, valid Shots, citations, $/tour); 30 human-rated tours |

API version 2026-10-21 rejects `temperature`, so evals run N samples and report variance. AI text is labeled "AI-generated from N sources", per EU AI Act Art. 50(4). All tools are read-only: at worst, an injected headline can move the camera.

## 10. Platform, infrastructure and CI/CD

- **Topology:** Vercel for web, Cloudflare (DNS, WAF, R2, CDN, Workers, Tunnel), one Hetzner EU ARM VM, and Anthropic. Modal handles GPU bursts on its free credits. GCP runs only the Phase-1 Cloud Run poller, kept as the fallback writer, and the BigQuery backfill.
- **IaC:** OpenTofu 1.13 for Cloudflare, Hetzner, GitHub, Grafana and Vercel; encrypted state in R2, PR plan comments, nightly drift checks.
- **CI (GitHub Actions, free for public repos):**
  - pnpm, Turborepo, uv and mise, behind one `ci-ok` check.
  - Golden-file GDELT parser tests.
  - Playwright visual regression of about 40 canonical Shots on the deterministic renderer, which also gates weekly MapLibre releases.
  - Lighthouse and bundle budgets on previews; nightly evals.
  - SHA-pinned actions checked with zizmor, Renovate cooldowns, a Syft SBOM with provenance attestations, and Grype (with an ADR on the 2026 Trivy compromise); release-please.
- **Nightly Globe Cast:** a software-GL "World in 60 seconds" render on the virtual clock (~30–60 min), uploaded to R2.
- **Observability:** OpenTelemetry to Grafana Cloud Free (traces, logs, Faro RUM), Sentry Developer, a Better Stack status page, and cookieless Umami for /stats.
- **SLOs:** 99% of GDELT windows visible on the globe within 30 min; p95 under 300 ms for dynamic calls; 99.5% availability.

| Monthly cost (steady state) | USD |
|---|---|
| Hetzner CAX21, including IPv4 | ~12.5 |
| R2: planet tiles (120 GB), cubes, Parquet lake (~250 GB total) | ~3.6 |
| Cloudflare Workers Paid (from launch) + domain | ~6 |
| Anthropic, app-enforced cap of ~$0.65/day | ≤ 20 |
| **Total** (Vercel Hobby, Grafana, Sentry, Actions and Modal credits are free) | **≈ $42** |

**Bursts.** The backfill costs about $10–25 in scan and egress, bounded by dry runs and `maximum_bytes_billed`. Launch month adds Vercel Pro ($20) and a higher LLM cap. During research, Hetzner's cost-optimized line showed "currently not available" in DE/FI. The fallbacks are any 4 vCPU / 8 GB ARM host, or the Cloud Run writer with search and briefings paused.

## 11. Deliberate cuts

- **Flights, ships, markets and instability scores.** That is World Monitor's territory, and it costs money and licensing effort.
- **Kubernetes.** The unit of scale is the immutable file, not the pod; OpenTofu still deploys real infrastructure.
- **Kafka, NATS, SSE fan-out, ClickHouse, DuckLake, Dagster, separate vector or graph DBs.** About 15 messages per second and a 30-day hot window don't need them, and each has a written adoption trigger.
- **Accounts.** Every lens is a URL and an RSS feed: no GDPR surface, no signup wall.
- **Thumbnails, full text and per-article AI summaries.** All carry legal exposure; only multi-source syntheses ship.
- **Forecasting (Chronos-2, VIEWS).** GDELT measures attention, not ground truth.
- **WebGPU in the core, Google 3D Tiles, Rust and C++.** WebGPU can't interleave with a basemap. A WebGPU lab or a WASM Lens kernel ships only if profiling demands it.

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| deck.gl GlobeView is experimental (picking, arc culling, the z10–12 morph) | Week-1 spike with a go/no-go ADR; `cullMode:'none'` arcs; MapLibre-native circles in the morph band; Plan B: MapLibre custom layers in hand-written GLSL; exact pins and visual regression |
| Early-year fields (e.g., `PAGE_TITLE` before 2017) unverified; the 2025 gap | Phase-4 spike samples each year; URL-slug title fallback; gaps drawn as hatched bands, never interpolated |
| Mobile GPU and memory limits | Res-2 aggregates and 24 h of points by default; quality governor; device lab |
| LLM cost spike at launch | Quantized cache keys behind the CDN; a daily $ cap; extractive fallback; Batch for bulk |
| Copyright | Metadata, titles and links only; ≤120-word multi-source syntheses, no quotes; overlap rejection; publisher opt-out within 72 h |
| GDELT decline or a GDELT 5 format change | Raw files, not APIs; a self-healing poller (per-file retry, MD5, hourly reconciliation); contract tests; RSS connector |
| Beautiful but shallow, or misleading | Public benchmarks for StoryStream, Prism and Infrared; method pages and intervals; /trust shows where GlobaLens loses |
| Too much scope for one person | Ranked delivery; Prism, Infrared and Tours are independent and cuttable; the product is complete after Phase 5 |

## 13. Resume bullets and headline metrics

Bullets use only measured numbers from the metrics ledger; brackets mark placeholders.

- Built GlobaLens, an open-source "attention weather" globe that renders [1.5M] live news points at [60] fps (real-user p50) with a custom spherical-cap Lens shader; [N] weekly users.
- Designed a CDN-static time-cube format (Arrow IPC over H3) that replays a backfilled decade of GDELT at 15-minute resolution for [<$4]/month, and absorbed a Show HN spike at [X] req/s with a [99%] edge hit rate.
- Shipped StoryStream, an online multilingual story clusterer ([F1] against Miranda et al.'s 84.0 crosslingual benchmark) that drives per-story propagation arcs across [60+] languages.
- Launched cited AI briefings at [$0.0005] per brief with public evals: citation precision [X%], MiniCheck faithfulness [Y%], and zero verbatim 8-gram overlaps by construction.
- Built a deterministic frame-stepped renderer that serves both nightly narrated MP4 tours and pixel-stable visual regression across MapLibre releases.

**Headline metrics on /stats:** weekly users, real-user fps by device, LCP/INP p75, freshness p95, CDN hit ratio, $/month, StoryStream F1, briefing faithfulness, Infrared overlap.

## 14. Ten-phase sketch (~6–9 months part-time)

| Phase | Ships (demoable) | Exit gate |
|---|---|---|
| 1. First Light | Render spike + ADR; Cloud Run poller writing Arrow packs + `now.json` to R2 (no DB yet); Next.js shell with live 24 h points; CI, OpenTofu, Sentry; `v1-hackathon` tag + retrospective | Public no-signup URL on real data; 60 fps at 300k points |
| 2. The Lens | Cap query, `LensExtension`, detent, HUD, keyboard and screen-reader paths; bokeh and choropleths; title dedup; nuqs permalinks; mobile Drawer | Lens query < 4 ms; blog post #1 |
| 3. Stories | VM + Postgres 18 stack; embedding bake-off; StoryStream v1; source registry; story sheet; propagation arcs; eval harness | Miranda F1 published |
| 4. Long Exposure | BigQuery → DuckDB backfill; time-cubes; Chronoscope, bezel, interpolation, prefetch; surprise encoding; gap bands; Satellite Day | Decade online; blog post #2 |
| 5. Share | Shot schema, short links, OG cards, snapshots, clips, embeds, RSS; cached SSR pages; quality governor, perf lab, Lighthouse budgets | Card + clip + embed for any view; Core Web Vitals green |
| 6. Briefings | Cited Lens Briefings; Batch story summaries; budget guardrails; content-policy ADR, opt-out, attributions; /trust v1; classroom soft launch | Faithfulness published; 20 niche users |
| 7. Prism | Bloc framing extraction, cited divergence claims, globe tinting, split view | κ published |
| 8. Infrared | Severity layers + pageviews; expected-attention model; method page; StoryStream v2 | Expert-list overlap published |
| 9. Tours | Director, Tour engine, projector mode, nightly Globe Cast, MCP server + App | Golden-set score; App live in Claude |
| 10. Launch | SLOs + status page; k6 at 10× load; fallback drill; cost-cap test; 90-s video; Show HN (stretch: WebGPU lab) | Launch gates pass |

Every phase also ships a tagged release, a changelog, at least one ADR, a /stats delta and a private explain-back recording. Three kernels are hand-written first, each with a blog post: Lens selection and shader, the time-cube codec, and propagation metrics.

## 15. Estimated size

About **60k LOC** (range 50–70k), an outcome rather than a target. By area:
- Frontend and GLSL: ~25k
- Shared packages (Shot, miniglobe, cube codec, lens kernel, tokens): ~6k
- API and MCP: ~6k
- Ingestion and backfill: ~6k
- ML and evals: ~8k
- Tests: ~8k
- Infra and CI: ~3k
