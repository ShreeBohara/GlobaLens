# GlobaLens 3.0: Frontend and Geospatial Visualization Stack (research as of 2026-10-28)

Scope: rendering engine, basemaps, WebGPU, client compute, app framework, UI libraries, real-time transport. Versions were checked against primary sources (GitHub releases, official docs, pricing pages) on 2026-10-28 unless marked otherwise. Confidence: **H** = primary source, **M** = secondary source or inferred, **L** = unverified estimate. Note: the shared web-search budget ran out mid-session. Later checks used direct fetches of known primary URLs, and a few minor libraries are left unversioned on purpose.

---

## TL;DR verdict

| Decision | Pick | Confidence |
|---|---|---|
| Map engine | **MapLibre GL JS 6.16** (adaptive globe that becomes Mercator between z10 and z12) | H |
| Data layers | **deck.gl 9.4** via the new `@deck.gl/maplibre` `MapLibreOverlay`, **interleaved, on WebGL2** | H |
| GPU API | **WebGL2 baseline; WebGPU only as progressive enhancement** ("lab" features) | H |
| App framework | **Next.js 16.4 App Router + Cache Components**. The globe lives in a persistent client layout; story pages are server-rendered with OG images | M-H (close call vs TanStack Start 1.0) |
| Data plane | **Arrow IPC → Web Worker (flechette) → deck.gl binary attributes**. GPU-side time filter and Lens, H3 aggregates | H |
| Basemap | **Self-hosted Protomaps PMTiles on Cloudflare R2** (about $0–7/month); OpenFreeMap Dark for dev | H |
| Realtime | **SSE "doorbell" plus CDN-cacheable Arrow batches over HTTP**; no WebTransport | M-H |
| Drop | react-globe.gl (v1), Mapbox GL JS, CesiumJS as the main engine, R3F v10 alpha, always-on Google 3D Tiles | H |

---

## 1. Engine options compared (questions a–e)

| Option (verified status) | Strengths | Problem for GlobaLens |
|---|---|---|
| **MapLibre GL JS 6.16.0** (25 Oct 2026; BSD; WebGL2-only, ESM) | Real cartography (vector tiles, labels, borders), adaptive globe, terrain, sky/atmosphere, native heatmap on globe, custom GLSL layers on globe | Not built for million-point analytic layers, which is what deck.gl adds |
| **deck.gl 9.4.1** (28 Oct 2026) | Binary attributes; ~1M points at 60 fps; H3, Arc, GreatCircle, Trips layers; GPU filtering | GlobeView is still *experimental*; WebGPU still *experimental*; no basemap of its own |
| **three.js r186 + R3F 9.8.2** | WebGPURenderer + TSL with WebGL2 fallback; cinematic effects and compute | No cartography: tiles, labels, picking and zoom-to-street would all be hand-built |
| **globe.gl** (what v1 used) | Quick to start | three.js WebGL with one object per feature; `pointsMerge` turns off click/hover; no real map |
| **CesiumJS 1.146** (Oct 2026) | Photorealistic 3D Tiles, time-dynamic scenes | Heavy, a separate paradigm; Google tiles cost money |
| **Mapbox GL JS v3** | Polished | Proprietary: "for use only with the relevant Mapbox product(s)"; 50k free loads, then $5/1k |

**What this means for us:** MapLibre handles cartography and the globe, and deck.gl handles data. three.js and Cesium are optional showpieces, never the core. Mapbox is out on license and bill-shock risk: 100k loads/month would cost about $250.

## 2. MapLibre GL JS v6 (a)

- **v6 dropped WebGL1 and moved to ESM** (v6 pre-releases were announced in April 2026). 5.24 was the last v5 release.
- **Cadence is extreme:** six releases in August 2026 alone, and 6.9 to 6.16 between mid-September and 25 October **[corrected: 6.9.0 shipped 9 Sep 2026, so the 6.9→6.16 run covers early September to 25 October; v6.0.0 itself went stable on 22 Jul 2026]**. **Pin exact versions** and gate upgrades behind visual-regression tests.
- **Globe:** the style-spec preset `globe` is defined as `["interpolate",["linear"],["zoom"],10,"vertical-perspective",12,"mercator"]`, so the planet morphs into a flat street map at no extra cost. Recent fixes: sky in globe view (6.10), atmosphere fading with altitude (6.11), pole holes (6.12), globe center can reach the poles (6.13), circle layers during the globe→Mercator transition (6.14).
- **Custom layers on globe:** `render()` receives `shaderData` (`vertexShaderPrelude`, `define`, `variantName`) and `getProjectionData()`. GLSL that calls `projectTile()` works in both projections (official example on 6.16.0).
- **Terrain + globe + native `heatmap` layer work together** (official example on 6.16.0, using a Mapterhorn DEM).
- **Experimental custom projections** (`addProjection`, `identity`, `{bbox}` token, 6.15).
- **MLT tile format:** v1 is stable. v2 is experimental and claims **10–18% smaller than gzipped MVT and 2.3–3.7× faster decode** **[corrected: the 10–18% figure is for gzipped v2; the 2.3–3.7× decode speedup was measured for uncompressed v2 against gzipped MVT]**. The Martin tile server can serve MLT. Watch it, but don't depend on it.

## 3. deck.gl 9.4 (b)

- **Timeline:** 9.2 (7 Oct 2025, WebGPU preview), 9.3 (13 Apr 2026, GlobeController stability), 9.4.0 (5 Sep 2026), 9.4.1 (28 Oct 2026). The **v10 tracker** (opened 16 Sep 2026) lists WebGPU, Arrow-first loaders and GPU compute. Its alpha target date has already passed, and no v10 release exists yet.
- **WebGPU:** 9.4 ported *every* official layer **[corrected: every layer in the core layer packages now has a WebGPU path (some since 9.2/9.3), but the WebGPU guide's matrix still lists the seven `@deck.gl/carto` layers as WebGL-only]**, but the docs still say it is "experimental and is not yet recommended for production." The WebGPU guide says **"No current base map integration path supports WebGPU interleaving."** Most extensions are WebGL-only, PostProcessEffect is unsupported, and TextLayer loses backgrounds and collision on WebGPU. WebGL-only apps can resolve the `visgl:webgl-only` export condition to drop the WebGPU code.
- **MapLibre integration:** the new `@deck.gl/maplibre` package (forked from `@deck.gl/mapbox`) supports MapLibre v4, v5 and v6 **[corrected: v4.5.1 or later; the peer range is `^4.5.1 || ^5.0.0 || ^6.0.0`]**.
  - **Modes:** interleaved (shares MapLibre's WebGL2 context, placed with `beforeId`), overlaid, and reverse-controlled.
  - **Globe:** v9.1 already said `MapboxOverlay` "works with maplibre-gl globe map without additional configuration." Globe rendering goes through the **experimental GlobeView**.
  - **Labels and icons:** with default back-face culling, **TextLayer and non-billboard IconLayer do not render**.
  - **Terrain:** deck layers are **not draped on MapLibre terrain**.
  - **Other limits:** only **one** interleaved overlay per map; `useDevicePixels` is ignored when interleaved; MapLibre defaults to `antialias:false`, so set it to true.
- **GlobeView limits:**
  - No high-precision rendering above z12.
  - **HeatmapLayer and ContourLayer are unsupported**; MaskExtension is unsupported.
  - TileLayer, MVTLayer and Terrain are experimental.
  - 9.4 added pitch/bearing and Tile3DLayer/Terrain on GlobeView.
- **Layers to use:**
  - ScatterplotLayer for events.
  - H3HexagonLayer for aggregates.
  - **GreatCircleLayer** for actor→actor relations (the docs recommend it on globe).
  - TripsLayer for propagation playback.
  - Billboard IconLayer for markers.
  - Heatmaps go to the **MapLibre native heatmap**, and labels go to **MapLibre symbol layers**.
  - A5Layer (new A5 grid, 9.2) is a curiosity, not a need.
- **Performance (official docs):**
  - ScatterplotLayer renders "**up to about 1M** data items" at 60 fps (2015 MacBook Pro), falls to **10–20 fps near 10M**, and crashes somewhere between **10M and 100M** (Chrome's 1 GB allocation cap).
  - Picking handles 16M items per layer and 256 pickable layers; about 100 layers is fine.
  - "**99%**" of update CPU time goes to accessors, so supply typed arrays via `data.attributes` ("maximum performance possible"). Build them in workers, where transfer costs "virtually" nothing.
  - High-DPI screens quadruple fragment work.
- **Arrow:** core has no first-class Arrow support yet; it is a v10 goal. GeoArrow layers live in `geoarrow/deck.gl-geoarrow` (an R wrapper landed on CRAN in July 2026). A v10 prototype showed **1.8 ms vs 31.6 ms** per slider tick at 4M rows when data stays GPU-resident (prototype only, **L-M**).

## 4. three.js / R3F / globe.gl (c)

- **three.js r186** (Sep 2026): `three/webgpu` gives WebGPURenderer with WebGL2 fallback. r185 added WebXR on WebGPU and clustered lighting; r184 runs TSL and node materials on WebGLRenderer through a compatibility layer.
- **R3F:** stable is **9.8.2** (15 Oct 2026; React 19.3-compatible since 9.8.0). **v10.0.0-alpha.6** makes WebGPU the default and moves TSL hooks into `@react-three/tsl`; its own notes say "Consider all features experimental," and its tracking issue reports drei crashes on the WebGPU default.
- **When a custom three.js globe wins:** cinematic scenes with no cartography (scattering atmosphere, bloom, TSL particle compute) and no need for tiles, labels or zoom-to-street. For GlobaLens that means a hero or "lab" route only.

## 5. Cesium, Google 3D Tiles, Mapbox (d, e)

- **Google Photorealistic 3D Tiles** (pricing page updated 2026-10-28):
  - Enterprise SKU with **1,000 free root-tileset requests/month**, then **$6.00/1k** (up to 100k) falling to $2.40/1k (5M+).
  - **10,000 root requests/day**. One root request covers up to a 3-hour session, but **a page refresh starts a new billable root** **[corrected: Google's docs do not say this. They say one root tileset request allows up to three hours of renderer tile requests, and the 10,000/day cap is counted per project. The refresh point is an inference, so treat it as a planning assumption]**.
  - Policy: the Google logo plus aggregated attributions must be on screen; no caching beyond the Agreement; no offline use; overlays must not be derived from the tiles. The policy page names CesiumJS (`showCreditsOnScreen`) but not deck.gl or three.js.
  - Example: 5k sessions/month ≈ $24.
- **Cesium ion Community:** free for non-commercial personal use and includes 1,000 Google root tiles/month. The Commercial plan is $149/month.
- **Mapbox GL JS v2+:** proprietary under the Mapbox TOS, and the license "terminates automatically" without a Mapbox account.

## 6. Basemaps (f)

| Provider | Cost | Dark styles | Terms |
|---|---|---|---|
| **Protomaps PMTiles on R2** | Planet ≈120 GB (z0–15). R2: $0.015/GB-month after 10 GB free, **zero egress**, Class B $0.36/M after 10M free, so the full planet ≈ **$1.65/month**. "Each zoom level roughly doubles" size, so a z0–12 extract is ≈15 GB (≈free, **L** estimate). Optional Worker plan $5/month includes 10M requests | Flavors `light`, `dark`, `white`, `grayscale`, **`black`** (the last three are for data visualization) | ODbL, OSM attribution |
| **OpenFreeMap** | Free, "no limits," no API key | **Dark**, Positron, Fiord, Liberty, Bright, 3D | **No SLA**; donation-funded |
| MapTiler | Free plan (5k sessions) is **non-commercial**; Flex $30/month | Custom | Paid for commercial use |
| Stadia | Free plan (200k credits) is **non-commercial**; Starter $20/month | Not verified | Paid for commercial use |

**Pick:** self-host Protomaps (`black` or `dark`, recolored with `{...namedFlavor('dark'), …}`) behind the Protomaps Worker on a custom domain, so tiles get Cloudflare cache HITs (R2 cache misses can take 500 ms or more). Use OpenFreeMap Dark for local development and as a fallback.

## 7. WebGPU support (g)

| Browser | WebGPU status (gpuweb implementation-status wiki) |
|---|---|
| Chrome/Edge | 113+ on Windows, macOS, ChromeOS **[corrected: Windows x86/x64 only; Windows ARM64 is still behind a flag]**. Android 121+ (Android 12+, ARM/Qualcomm/Intel). Linux partial: 144 (Intel Gen12+), 147 (NVIDIA on Wayland) |
| Firefox | 141 Windows; 145 Apple Silicon (macOS 26+); 147 other Macs **[corrected: 147 extends Apple Silicon support to all macOS versions; Intel ("other") Macs are still Nightly-only]**. **Linux: Nightly only. Android: behind a flag** |
| Safari | **26 on macOS, iOS, iPadOS and visionOS**, enabled by default |
| Global (caniuse) | ≈87.8% including partial support **[corrected: ≈89.5% (85.8% full + 3.7% partial) in the caniuse dataset dated 28–29 Oct 2026]**. caniuse misleadingly lists Firefox as "disabled by default" |

**Fallback strategy:** MapLibre v6 *requires* WebGL2, so WebGL2 is the baseline. Feature-detect `navigator.gpu` plus a successful adapter request for lab features only.

## 8. Client compute (h)

- **Web Workers:** do Arrow decoding, filtering, Lens queries, H3 binning and clustering off the main thread, and transfer typed arrays. **OffscreenCanvas** has 96.8% global support (Safari 17+). Keep map rendering on the main thread, because interleaving needs MapLibre's context; use OffscreenCanvas for worker-side thumbnails and charts.
- **Arrow:** Apache Arrow JS **21.2.0** vs **flechette**. Flechette is ≈16 KB gzipped vs 43 KB, extracts arrays **2–7× faster** and builds row objects 7–11× faster, and decodes GeoArrow WKB. Its limit: it accepts byte buffers only.
- **h3-js 4.5.0** (Jul 2026) handles hex binning at the same resolutions the backend aggregates to. **supercluster 8.x** is for Mercator clustering at high zoom **[corrected: the current release is supercluster 9.1.0 (3 Sep 2026). Its 9.0.0 release (10 Aug 2026) reports 94% less transient allocation and ~23% faster runs on a 1M-point index]**. **loaders.gl 4.5.4** is stable, and **v5.0.0-beta.1** (28 Oct 2026) is Arrow-first with GeoArrow worker batches.
- **WASM:** Rust + **wasm-bindgen 0.2.129** (now in its own org). The rustwasm org was archived in September 2025 and **wasm-pack is slated for archiving**, so build with cargo + `wasm-bindgen-cli` **[corrected: wasm-pack was not archived. It moved to the wasm-bindgen org (github.com/wasm-bindgen/wasm-pack), shipped v0.14.0 (Jan 2026) and v0.15.0 (May 2026), and was still being updated on 27 Oct 2026. cargo + `wasm-bindgen-cli` is still a good lean setup, but wasm-pack remains a supported option]**. Only add WASM when profiling shows a hot path, such as a Lens top-K over more than 5M rows. C++/Emscripten isn't justified.

## 9. App framework (i)

| | Next.js 16.4 | TanStack Start 1.0 | React Router 8.x | Vite SPA |
|---|---|---|---|---|
| Status | 16.4 (6 Oct 2026), React 19.3; Cache Components recommended for all apps, default in `create-next-app`, and the default in Next 17 | Stable 13 Oct 2026 | v8 18 Jun 2026 **[corrected: 8.0.0 was published 17 Jun 2026 (UTC); 8.5.1 on 27 Oct is confirmed]**; 8.5.1 (27 Oct, **M**) | — |
| SEO + OG pages | `'use cache'` shells, `generateMetadata`, `next/og` | Per-route selective SSR; bring your own Satori | SSR/prerender | Needs a separate prerender |
| WebGL app feel | Persistent layouts keep the globe mounted; 16.3 Instant Navigations; React 19.3 `use(browser())` opts components out of SSR | SPA-first ergonomics | Good | Best |
| Solo + AI dev | Versioned `AGENTS.md`, `next upgrade --agent`, Skills | Smaller corpus | Medium | Simple |
| Risk | Critical RSC CVE-2025-66478 (Dec 2025) **[corrected: the canonical ID is CVE-2025-55182 ("React2Shell", CVSS 10.0, disclosed 3 Dec 2025). The CVE program rejected CVE-2025-66478 as a duplicate, though Next.js still uses it as its advisory label]**, then monthly security releases (next on 3 Nov 2026) | Brand new; its creator stopped using RSC on tanstack.com | "Deliberately boring" | No SEO |

**Pick Next.js 16.4**, and enforce four rules:
1. The globe is a `'use client'` component mounted once in `app/(globe)/layout.tsx`. It never unmounts and flies between stories as the URL changes.
2. Story, country, event and daily-brief pages are server-rendered with `'use cache'`. Parallel/intercepting routes open a story as a panel over the globe, and a hard refresh renders the full page.
3. **OG images:** `next/og` runs on Satori + Resvg, which supports flexbox only, **ttf/otf/woff** fonts and a **500 KB** bundle, and cannot render WebGL. Render an **SVG mini-globe** with d3-geo instead (**M**).
4. Automate Renovate for patches and `experimental.agentUpgrade:'security'`. Keep Server Actions minimal; mutations go through a typed API.

Smaller wins: TypeScript 7 (native, ~10× faster) type checking in `next build`; up to 90% less dev memory (16.3); about 22% more SSR throughput (16.3).

## 10. UI libraries (j)

| Need | Pick (verified version) | Notes |
|---|---|---|
| Styling | **Tailwind 4.3.3** (16 Jul 2026) | 4.3 added container-size, scrollbar and zoom utilities |
| Components | **shadcn/ui**, now **Base UI by default** (July 2026); Base UI **1.9.0** | "Radix is not being deprecated"; use `-b radix` if wanted |
| Motion | **Motion 14.6.0** (20 Oct 2026) **[corrected: 14.6.0 shipped 22 Oct 2026; the latest is 14.7.1 (27 Oct 2026)]** | `AnimateView` wraps React 19.3 `<ViewTransition>` (stable) for globe↔story transitions |
| Command palette | **cmdk 1.1.1** via shadcn `Command` | Stable but slow release cadence |
| Server state | **TanStack Query 5.105** | — |
| Client state | **Zustand 5.0.16** | Transient high-frequency map and camera state outside React renders |
| URL state | **nuqs 2.10.2** | Every view (camera, time window, layers, Lens) is a shareable URL; throttle with `limitUrlUpdates` |
| Lists/tables | TanStack Table + Virtual (version not re-checked) **[corrected: TanStack Table is now v9 (9.3.1, 12 Oct 2026); TanStack Virtual is 3.14.23]** | Lens results, event tables |
| Charts | **uPlot 1.6.x** for streams and sparklines; **ECharts 6.1** for dashboards | uPlot: 166,650 points in 25 ms; streams 3,600 points at 60 fps for 10% CPU vs ECharts 70%. Observable Plot (0.6.17) is fine for static story charts but releases slowly |

## 11. Real-time transport and encodings (k)

| | Fit for GlobaLens |
|---|---|
| **SSE** | One-way news push is exactly what SSE is for. **Without HTTP/2 it is capped at 6 connections per browser per domain**; with HTTP/2 streams are negotiated (default 100). It is text-only |
| WebSocket | Only for bidirectional features (shared Lens sessions, watch parties) |
| WebTransport | **Baseline since Safari 26.4** (Mar 2026), but it needs HTTP/3 servers **[corrected: not strictly. WebKit's Safari 26.4 notes say WebTransport can also run over HTTP/2 and TCP as a fallback with the same API]** and buys nothing for a one-way feed |

**Pattern:** SSE sends a tiny `{"batch":"2026-10-28T14:15Z","n":4210}` doorbell, and the client then fetches an **immutable, CDN-cached Arrow IPC batch**. Fan-out costs nothing extra at the edge, and replay and catch-up come free.
**Encodings:** Arrow IPC for points (columnar, maps straight onto GPU attributes), JSON for control messages. Use protobuf only for typed service-to-service RPC; FlatBuffers is not needed.

## 12. Integration pitfalls checklist

1. A deck.gl WebGPU device plus a MapLibre basemap cannot interleave, so **stay on WebGL2**.
2. On globe, TextLayer and non-billboard IconLayer vanish, so use MapLibre symbols or billboard icons.
3. HeatmapLayer is unsupported on GlobeView, so use the MapLibre native heatmap.
4. deck.gl layers are not draped on terrain, so keep terrain subtle or turn it off under data.
5. Interleaving mixes projections around z10–12, so **spike this in Phase 1**.
6. MapLibre `antialias:false` makes lines jagged; set `antialias:true`.
7. Never build a new `data` array on each render. Use `updateTriggers`, binary attributes and the `visible` prop (toggling it is instant).
8. MapLibre and deck.gl must never run during SSR: use a client-only dynamic import or `use(browser())`.
9. Fast MapLibre releases mean exact pins plus Playwright screenshot tests.
10. Google 3D Tiles bill per root request, so hard-cap quotas.
11. Protomaps on `workers.dev` doesn't cache, so use a custom domain.

## 13. Product-direction implications (what GlobaLens should BE)

- **Lens 2.0 as the signature feature:**
  - The reticle defines a *spherical cap* (center plus angular radius).
  - A GPU shader extension highlights points inside the cap; that is one uniform per frame and no buffer re-upload.
  - A worker ranks the top-K stories inside the lens.
  - An AI brief summarizes "what's under the lens, last 24h vs last week."
  - The whole state goes into the URL.
- **Planet to street in one gesture:** the adaptive globe makes "zoom from planet to city block" seamless, which v1 could not do.
- **Stories as URLs:** each story/event cluster gets an SEO page and a mini-globe OG card. That is the distribution engine for a portfolio project.
- **Relationships and time:** GreatCircle arcs between actor countries ("who is acting on whom") plus a Trips-style playback of how a story spreads.
- **Optional wow factor:** "Dive into 3D" with Google tiles, and a WebGPU lab. Both are click-gated and never on the critical path.

## Recommendations for GlobaLens 3.0

1. **MUST:** Core engine is MapLibre GL JS 6.x (pinned) plus deck.gl 9.4 `MapLibreOverlay` interleaved on WebGL2. Phase 1 spike: interleaving across the z10–12 morph, picking, labels, terrain on/off.
2. **MUST:** Arrow-first data plane. The server emits Arrow IPC with GeoArrow-compatible point columns; a worker decodes it with flechette; data goes to deck.gl `data.attributes`. Time filtering and Lens highlighting run on the GPU, and H3 aggregates serve zoomed-out views. This stays forward-compatible with deck.gl v10 and loaders.gl v5.
3. **MUST:** Next.js 16.4 App Router + Cache Components, with the persistent globe layout, server-rendered story pages, and parallel/intercepting routes. Renovate + agentUpgrade handle the security cadence.
4. **MUST:** Self-hosted Protomaps on R2 + Worker (`black`/`dark` brand flavor; evaluate a z0–12/13 extract). OpenFreeMap Dark in dev. Never Mapbox.
5. **SHOULD:** Rebuild the Lens as GPU + worker + AI + URL (section 13). It is the resume headline.
6. **SHOULD:** SSE doorbell + CDN Arrow batches. Add WebSockets only for multiplayer features.
7. **SHOULD:** UI kit of Tailwind 4.3, shadcn/ui (Base UI), Motion 14 with ViewTransition, cmdk, Zustand, TanStack Query, nuqs, and TanStack Table/Virtual. Charts: uPlot + ECharts 6.
8. **SHOULD:** Treat performance as a feature: frame-time budgets in CI, a DPR cap, the `visgl:webgl-only` condition, and a server-rendered SVG globe placeholder that crossfades into WebGL via a View Transition.
9. **COULD:** A WebGPU lab: a deck.gl 9.4 WebGPU device on a standalone GlobeView (no basemap, so interleaving isn't needed), or WebGPU-compute Lens queries with a JS fallback.
10. **COULD:** "Dive into 3D" with Google Photorealistic 3D Tiles (deck.gl Tile3DLayer or a lazy Cesium viewer), with hard quotas and attribution handled.
11. **COULD:** A Rust/WASM module only after profiling (cargo + wasm-bindgen-cli).
12. **COULD:** Late roadmap phase: migrate to deck.gl v10 (Arrow/WebGPU) and MLT tiles once they are stable.

## Sources

- MapLibre GL JS releases: https://github.com/maplibre/maplibre-gl-js/releases
- MapLibre newsletters: https://maplibre.org/news/2026-09-02-maplibre-newsletter-august-2026/ · https://maplibre.org/news/2026-05-02-maplibre-newsletter-april-2026/
- MapLibre style spec (projection types, globe preset): https://maplibre.org/maplibre-style-spec/types/ · https://maplibre.org/maplibre-style-spec/projection/
- MapLibre custom layers on globe: https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/CustomRenderMethodInput/ · https://maplibre.org/maplibre-gl-js/docs/examples/add-a-custom-layer-with-tiles-to-a-globe/
- MapLibre heatmap on globe with terrain: https://maplibre.org/maplibre-gl-js/docs/examples/create-a-heatmap-layer-on-a-globe-with-terrain-elevation/
- MLT spec: https://maplibre.org/maplibre-tile-spec/
- deck.gl: https://github.com/visgl/deck.gl/releases · https://deck.gl/docs/whats-new · https://deck.gl/docs/api-reference/maplibre/overview · https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre · https://deck.gl/docs/api-reference/core/globe-view · https://deck.gl/docs/developer-guide/webgpu · https://deck.gl/docs/developer-guide/performance · https://github.com/visgl/deck.gl/issues/10712
- GeoArrow deck.gl (R wrapper): https://cran.r-project.org/web/packages/deckglgeoarrow/index.html
- three.js: https://github.com/mrdoob/three.js/releases · https://www.utsubo.com/blog/threejs-2026-what-changed (secondary)
- React Three Fiber: https://github.com/pmndrs/react-three-fiber/releases · https://github.com/pmndrs/react-three-fiber/releases/tag/v10.0.0-alpha.6 · https://github.com/pmndrs/react-three-fiber/issues/4026
- globe.gl: https://github.com/vasturiano/globe.gl
- Cesium: https://cesium.com/blog/2026/10/02/cesium-releases-in-october-2026/ · https://cesium.com/platform/cesium-ion/pricing/
- Google Map Tiles API: https://developers.google.com/maps/billing-and-pricing/pricing · https://developers.google.com/maps/documentation/tile/usage-and-billing · https://developers.google.com/maps/documentation/tile/policies
- Mapbox: https://github.com/mapbox/mapbox-gl-js/blob/main/LICENSE.txt · https://www.mapbox.com/pricing
- Protomaps: https://docs.protomaps.com/basemaps/downloads · https://docs.protomaps.com/basemaps/flavors · https://docs.protomaps.com/deploy/cloudflare
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Other basemap providers: https://openfreemap.org · https://www.maptiler.com/cloud/pricing/ · https://stadiamaps.com/pricing
- WebGPU: https://github.com/gpuweb/gpuweb/wiki/Implementation-Status · https://caniuse.com/webgpu
- OffscreenCanvas: https://caniuse.com/offscreencanvas
- Safari 26.4 (WebTransport): https://webkit.org/blog/17862/webkit-features-for-safari-26-4/
- Arrow and data tooling: https://github.com/apache/arrow-js/releases · https://github.com/uwdata/flechette · https://github.com/uber/h3-js/releases · https://github.com/mapbox/supercluster · https://github.com/visgl/loaders.gl/releases
- Rust/WASM: https://blog.rust-lang.org/inside-rust/2025/07/21/sunsetting-the-rustwasm-github-org/ · https://github.com/wasm-bindgen/wasm-bindgen
- Next.js: https://nextjs.org/blog · https://nextjs.org/blog/next-16-3 · https://nextjs.org/blog/next-16-4 · https://nextjs.org/blog/CVE-2025-66478
- React 19.3: https://react.dev/blog/2026/09/09/react-19-3
- Other frameworks: https://tanstack.com/blog/tanstack-start-1-0 · https://www.infoq.com/news/2026/08/react-route-v8/ (secondary) · https://reactrouter.com/changelog
- OG images: https://vercel.com/docs/og-image-generation
- shadcn/ui and Base UI: https://ui.shadcn.com/docs/changelog · https://ui.shadcn.com/docs/changelog/2026-07-base-ui-default · https://github.com/mui/base-ui/releases
- UI libraries: https://github.com/tailwindlabs/tailwindcss/releases · https://motion.dev/changelog · https://github.com/pacocoursey/cmdk/releases · https://github.com/TanStack/query/releases · https://github.com/pmndrs/zustand/releases · https://github.com/47ng/nuqs/releases
- Charts: https://github.com/apache/echarts/releases · https://github.com/leeoniya/uPlot · https://github.com/observablehq/plot/releases
- SSE: https://developer.mozilla.org/en-US/docs/Web/API/EventSource

## Fact-check (2026-10-28)

Method: an independent pass over the 12 claims the build plan leans on most. Each was checked against primary sources: the GitHub releases API, npm registry timestamps, official docs and changelogs, pricing pages, the CVE.org record and the caniuse and web-features datasets. The web-search budget ran out partway through, so later checks fetched known primary URLs directly. Inline fixes are marked **[corrected: …]** above.

| # | Claim | Verdict | Correction | Source |
|---|---|---|---|---|
| 1 | MapLibre GL JS 6.16.0 (25 Oct 2026) is current; v6 is ESM-only and requires WebGL2; 5.24 was the last v5; the `globe` preset interpolates vertical-perspective → mercator between z10 and z12 | Confirmed | Only a date detail: v6.0.0 went stable 22 Jul 2026, and 6.9.0 shipped 9 Sep, not mid-September | GitHub releases API `maplibre/maplibre-gl-js` (v6.0.0 notes); npm `maplibre-gl`; maplibre-style-spec `docs/types.md` |
| 2 | deck.gl 9.4.1 (28 Oct 2026) ships the new `@deck.gl/maplibre` `MapLibreOverlay`: interleaved mode needs WebGL2, one interleaved overlay per map, `useDevicePixels` ignored, no draping on terrain, MapLibre defaults to `antialias:false` | Confirmed | Supported MapLibre range is 4.5.1+, 5 and 6 (not all of v4) | GitHub releases API `visgl/deck.gl`; npm `@deck.gl/maplibre` peerDependencies; deck.gl `docs/api-reference/maplibre/overview.md` |
| 3 | deck.gl WebGPU is "experimental and is not yet recommended for production"; "No current base map integration path supports WebGPU interleaving"; most extensions and PostProcessEffect are WebGL-only; a `visgl:webgl-only` export condition exists | Confirmed | Minor: "every official layer" covers the core layer packages; the guide's matrix still lists the seven `@deck.gl/carto` layers as WebGL-only | deck.gl `docs/whats-new.md` (v9.4) and `docs/developer-guide/webgpu.md` |
| 4 | GlobeView is experimental: HeatmapLayer and ContourLayer don't work, MaskExtension is unsupported, no high precision above z12, TileLayer/MVTLayer/Terrain are experimental, and TextLayer plus non-billboard IconLayer vanish with back-face culling | Confirmed | — | deck.gl `docs/api-reference/core/globe-view.md`; `docs/api-reference/maplibre/overview.md` (Compatibility) |
| 5 | Next.js 16.4 (6 Oct 2026) ships React 19.3; Cache Components are recommended for every app, on by default in `create-next-app` and the default in Next 17; `next upgrade --agent` and `experimental.agentUpgrade:'security'` exist; monthly security releases, with the next on 3 Nov 2026; TanStack Start 1.0 went stable 13 Oct 2026 | Confirmed | Latest patch is 16.4.3 (23 Oct). Out-of-band critical updates also shipped 22 Sep and 14 Oct 2026, which strengthens the Renovate rule | nextjs.org/blog/next-16-4; nextjs.org/blog index (security posts Jul–Oct 2026, "Upcoming Next.js November Security Release"); npm `next`; tanstack.com/blog/tanstack-start-1-0 |
| 6 | "Critical RSC CVE-2025-66478 (Dec 2025)" | Partially true | The incident is real: a CVSS 10.0 RCE disclosed 3 Dec 2025. But CVE.org marks CVE-2025-66478 REJECTED as a duplicate of **CVE-2025-55182**. Cite 55182; Next.js's advisory GHSA-9qr9-h5gf-34mp still uses 66478 | cveawg.mitre.org/api/cve/CVE-2025-66478; nextjs.org/blog/CVE-2025-66478 |
| 7 | Protomaps planet ≈120 GB at z0–15, with each zoom level roughly doubling size; R2 costs $0.015/GB-month after 10 GB free, has zero egress, and charges Class B $0.36/M after 10M free, so the planet costs ≈$1.65/month | Confirmed | — (storage only; Class A is $4.50/M after 1M free) | docs.protomaps.com/basemaps/downloads; developers.cloudflare.com/r2/pricing |
| 8 | Mapbox GL JS v2+ is proprietary ("for use only with the relevant Mapbox product(s)"; the license "terminates automatically" without an account in good standing); 50k free loads, then $5.00/1k, so 100k loads ≈ $250 | Confirmed | — | `mapbox/mapbox-gl-js` LICENSE.txt; mapbox.com/pricing |
| 9 | Google Photorealistic 3D Tiles: Enterprise SKU, 1,000 free per month, $6.00/1k up to 100k falling to $2.40/1k at 5M+, 10,000 root requests/day, 3-hour sessions, and a refresh starts a new billable root; Cesium ion Community is free (non-commercial, 1,000 root tiles/month) and Commercial is $149/month | Partially true | All prices, caps, policy terms and Cesium ion figures match. The "page refresh starts a new billable root" point appears in neither the usage-and-billing nor the policies page; it is an inference | developers.google.com/maps/billing-and-pricing/pricing (updated 2026-10-28); developers.google.com/maps/documentation/tile/usage-and-billing; developers.google.com/maps/documentation/tile/policies; cesium.com/platform/cesium-ion/pricing |
| 10 | WebGPU: Chrome 113+ on Windows/macOS/ChromeOS, Android 121+, Linux 144/147; Firefox 141 on Windows, 145 on Apple Silicon (macOS 26+), 147 on "other Macs"; Safari 26 on by default; caniuse ≈87.8%. WebTransport has been Baseline since Safari 26.4 and needs HTTP/3 | Partially true | Firefox 147 brings **all macOS versions on Apple Silicon**; Intel Macs are Nightly-only. Chrome 113 covers Windows x86/x64 only (ARM64 needs a flag). caniuse shows ≈89.5% (85.8% + 3.66% partial). WebTransport became Baseline (newly available) on 24 Mar 2026, but Safari 26.4 also supports an HTTP/2/TCP fallback | gpuweb wiki Implementation-Status (raw markdown); caniuse `fulldata-json/data-2.0.json`; web-features 3.44.0 `data.json`; webkit.org/blog/17862 |
| 11 | "wasm-pack is slated for archiving", hence cargo + `wasm-bindgen-cli` | Refuted | wasm-pack moved to **github.com/wasm-bindgen/wasm-pack** and was not archived. It shipped v0.14.0 (Jan 2026) and v0.15.0 (May 2026) and was last pushed 27 Oct 2026. Confirmed parts: the rustwasm org's repos are archived, and wasm-bindgen 0.2.129 (25 Sep 2026) lives in its own org | GitHub API `repos/rustwasm/wasm-pack` (resolves to `wasm-bindgen/wasm-pack`) and its releases; `wasm-bindgen/wasm-bindgen` releases; blog.rust-lang.org/inside-rust/2025/07/21/sunsetting-the-rustwasm-github-org |
| 12 | Library versions: Tailwind 4.3.3 (16 Jul); shadcn/ui on Base UI by default (Jul 2026, Radix not deprecated, `-b radix`) with Base UI 1.9.0; Motion 14.6.0 (20 Oct); Zustand 5.0.16; nuqs 2.10.2; TanStack Query 5.105; three r186; R3F 9.8.2 and v10.0.0-alpha.6; h3-js 4.5.0; loaders.gl 4.5.4 and 5.0.0-beta.1; Arrow JS 21.2.0; flechette ≈16 KB vs 43 KB gzipped; CesiumJS 1.146; supercluster 8.x; React Router v8 (18 Jun) | Partially true | All match except: Motion 14.6.0 shipped 22 Oct (latest 14.7.1, 27 Oct); supercluster is **9.1.0** (9.0.0 on 10 Aug 2026); TanStack Table is **v9** (9.3.1); React Router 8.0.0 was 17 Jun | npm registry timestamps; motiondivision/motion CHANGELOG.md; ui.shadcn.com/docs/changelog/2026-07-base-ui-default; uwdata/flechette README; mapbox/supercluster releases; remix-run/react-router releases |

**Net effect on the plan:** none of the core picks change. Those are MapLibre 6.x pinned, deck.gl 9.4 `MapLibreOverlay` on WebGL2, Next.js 16.4 with Cache Components, Protomaps on R2, and no Mapbox. Three edits are needed: (a) pin supercluster 9.x and TanStack Table 9.x; (b) drop the "wasm-pack is being archived" reasoning, since either toolchain is fine; (c) cite CVE-2025-55182 and plan Google 3D Tiles quotas without relying on the refresh-billing assumption.
