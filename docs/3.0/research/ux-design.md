# GlobaLens 3.0: UX & Visual Design Direction (research, 2026-10-28)

> Confidence: **H** = primary source checked this session · **M** = secondary or partial source · **L** = from memory, not re-verified.
> The shared web-search budget ran out partway through this session. After that, facts were checked by fetching primary URLs directly; anything unverified is flagged.
> Palette figures were computed by `scripts/palette_check.py` (OKLCH→sRGB, WCAG contrast, Machado-2009 colour-blindness simulation).

## TL;DR
- **The "real-time OSINT dashboard on a globe" niche is taken.** World Monitor (AGPL) has 2M+ users, 468 feeds, 59 layer types, a ⌘K palette with 622 commands, cited AI country dossiers, MCP tools and desktop apps [S1,S2]. GlobaLens should not compete on layer count. It should compete on **one deep instrument (the Lens)**, on **narrative intelligence** (who covers a place, how framing differs, what goes unreported), and on **craft**.
- **Make the Lens a "magic lens" query instrument:** geodesic radius, time bezel, topic focus, see-through modes, split comparison, agent control.
- **Aesthetic: "Deep Field".** Near-black cool neutrals, one phosphor-lime instrument accent `#C3F344`, an orange↔azure tone scale checked for colour blindness, serif headlines × grotesk UI × mono telemetry.
- **Stack implications:**
  - MapLibre globe + deck.gl 9.4 (interleaved)
  - React 19.3 View Transitions (now stable)
  - Base UI Drawer (Vaul is unmaintained)
  - nuqs URL state
  - AI SDK v7 typed tool parts
  - shadcn "AI Elements" (AI SDK Elements is slated for deprecation at the end of Nov 2026)
- **Accessibility can set GlobaLens apart.** WCAG 2.2's 2.5.7 Dragging Movements applies directly to the drag-the-globe Lens.

## 1. Best-in-class teardown

| Product | What makes it great (specifics) | Steal | Avoid |
|---|---|---|---|
| **World Monitor** (2026 breakout) | 59 layer types, about 9 on by default. ⌘K with 622 commands. Country dossier: cited AI brief + 7-day timeline. Alerts gated by severity, 15-min age, 30-min dup-hold, 60 s cooldown. globe.gl *and* deck.gl/MapLibre engines [S1,S2] **H** | Off-by-default layers; alert rules; cited dossiers | Two map engines; sprawl; competing head-on |
| **Flightradar24** | Entity panel with large photo, tooltips, unit conversions, faster load; 2026 airport panel with delays, runway stats, boards [S8] **M** | Hero media + dense stats panel | — |
| **Windy** | One overlay at a time, timeline playback, particle wind, picker readout synced to layer [S7] **M** | Single-encoding rule; timeline as primary control | Particle decay tied to frame rate [S7] |
| **earth.nullschool** | Minimal chrome; fully keyboard-driven (`e` menu, `J/K` time, `P` animate, `N` now, `D/X` zoom, `W/Z`+`A/S` rotate) [S5]. ~1.5M uniques in month one at ~$11 cost [S6] **H/M** | Keyboard grammar; beauty as distribution | Hidden-menu discoverability |
| **Liveuamap** | Map + chronological feed + timeline + archive; AI crawl, analyst verification [S9] **M** | Feed↔map link; verification labels | Ads, icon soup |
| **Bloomberg Terminal** | "We're hiding complexity"; colour-coded keys; users resisted visual change, so changes were toned down [S10] **M** | Mnemonics, density, careful change management | Expert-only learnability |
| **Linear** | Themes from 3 inputs (base, accent, contrast) instead of 98 variables; LCH; Inter Display headings; goals: less visual noise, more navigation hierarchy and density [S12] **H** | 3-input OKLCH theme generator → auto high-contrast | — |
| **Vercel Geist / Palantir Blueprint** | Swiss-minimal Sans/Mono/Pixel (OFL) [S13]; dense desktop components, dark theme that must reach portals [S11] **H/M** | Mono telemetry; tokens that reach portals | Vercel-clone look |
| **Stripe globe** | 60k Fibonacci dots masked to ~20k; Bézier tube arcs drawn over 2.5 s; antialias off; stops off-screen; 60 fps target [S4] **H** | Dot-matrix sphere; off-screen pause | — |
| **GitHub globe** | No textures (4 lights, ~12k instanced dots), halo shader, ring pulse on arc landing, initial rotation from timezone, SVG placeholder crossfade 600 ms, 4 quality tiers when FPS <55.5 over 50 frames [S3] **H** | All of it | — |
| **Apple Maps / iOS 26** | Sheet detents. Liquid Glass hurt legibility, contrast and predictability (NN/g); iOS 26.1 added a higher-opacity "Tinted" option [S14,S15] **H** | Detented sheets | Translucent text over busy content |
| **Google Earth AI** | Gemini geospatial-reasoning agent in Earth (Oct 2025), results feed the time slider; access widened in 2026 [S16] **M** | Agent + globe + time | Generic chat with no citations |
| **Ground News** | Blindspot: picks stories whose outlet-bias mean/SD is skewed; 7-point bias bar [S17] **H** | Coverage imbalance as a view | US-centric ratings [S17] |
| **Graphics desks** | Chapters bound to camera (center/zoom/pitch/bearing), layer fades on enter/exit (Mapbox storytelling + Scrollama) [S18] **H** | Story mode | Scroll-jacking; no reduced-motion path |
| **Radio Garden** | Rotate the globe to tune stations, a precedent for v1's Lens. Reticle detail from memory; Wikipedia confirms only globe browsing [S57] **L** | Confirms the delight | The Lens alone isn't novel; its depth must be |

## 2. Product-direction flags (what GlobaLens should *be*)
1. **Not "World Monitor with fewer layers."** Position: *"See how the world sees any place."* That means inbound coverage, framing divergence across countries and languages, under-coverage, and how stories propagate over time.
2. **Information architecture = five modes named after camera techniques:** Viewfinder (Live) · Long Exposure (Replay) · Split (Compare) · Infrared (Gaps) · Tour (AI briefings).
3. **Map surprise, not volume.** Raw counts mostly map where newsrooms are (xkcd "Heatmap" [S28]). Bayesian surprise maps de-bias thematic maps [S27] **H**. Make anomaly-vs-baseline the default.
4. **Lenses are the core object.** You can save them, share them by URL, watch them with alerts, compare them, and record them as Tours.
5. **Ship an MCP App.** The spec has been stable since 2026-01-26, with hosts including ChatGPT, Claude, VS Code and Goose [S54] **H**. A live mini-Lens inside Claude/ChatGPT beats World Monitor's Pro-only tools [S1].

## 3. Interaction patterns: decisions

| Pattern | Decision | Reference |
|---|---|---|
| Time scrubbing | **Chronoscope**: tone-stacked histogram, brush, play at 1h/6h/1d per second, LIVE edge with "Return to live" pill, anomaly ticks, `J/K` stepping | Windy, nullschool [S5,S7] |
| Command palette | A grammar, not toggles: `lens kyiv 300km`, `time -72h`, `compare fr de`, `gaps sahel`; falls back to "Ask Analyst…" | cmdk (latest release v1.1.1) [S49] **M** |
| Keyboard-first | `WASD`/arrows pan under Lens, `[ ]` radius, `, .` time, `Space` play, `L` lock, `P` pin, `C` compare, `?` cheat sheet | nullschool [S5] |
| Focus + context | Lens = focus; off-topic hexes desaturate (no blur) | Magic lenses [S58] **L** |
| Linked brushing | One store: story ↔ hex ↔ timeline bar ↔ citation | — |
| Progressive disclosure | One encoding + four controls by default; "Instruments" drawer; Compact/Comfortable density | [S1] |
| Sheets vs modals | Non-modal resizable right sheet with breadcrumbs; modals only for sign-in or destructive actions (replaces v1's blocking modal) | — |
| Mini-map | Orthographic locator inset past z≈5 | — |
| Story mode | **Tour** chapters = camera + Lens + time window + cited stories; jump instead of fly under reduced motion | Mapbox storytelling [S18] **H** |
| Onboarding | 3 non-blocking coach marks + example gallery | Shape of AI "Wayfinders" [S55] **H** |
| URL-as-state | Camera, Lens center/km, time or live, topic, mode, selection; short links | nuqs v2 (Next ≥14.2, React Router, TanStack) [S48] **H** |
| Share / OG | Per-permalink `opengraph-image.tsx`. The server can't run WebGL, so draw a d3-geo orthographic SVG inside `ImageResponse`. User snapshots use canvas capture | 1200×630, 500 KB cap; Satori renders variable fonts only at their default instance → ship static weights [S47] **H** |

## 4. Data-viz on the map

| Zoom band | H3 res | Avg cell [S25] **H** | Cells |
|---|---|---|---|
| Orbit z0–2 | 2 | 86,802 km² | 5,882 globally (ship all) |
| Continent z2–4 | 3 | 12,393 km² | 41,162 globally |
| Region z4–6 | 4 | 1,770 km² | viewport only |
| Metro z6–8 | 5 | 253 km² | viewport only |
| City z8+ | 6–7 / clustered points | 36–5 km² | viewport only |

- **One colour encoding at a time** (Tone / Surprise / Category / Gap) with a legend chip. Luminance = log volume.
- **Tone scale (5 classes, OKLCH, checked by script):** `#FE9879 · #CB836D · #767B81 · #5AA1CB · #59C3FE` (negative → positive).
  - Dim neutral, bright extremes, in the style of Crameri's "berlin" (Crameri maps are uniform and colour-blind-friendly) [S29] **M**.
  - Adjacent steps have OKLab ΔE ≥0.079 under simulated protan/deutan/tritan vision.
  - Every step has ≥4.19:1 contrast against land.
  - Redundant cue: a −/+ glyph plus a 5-cell mini-bar.
- **Uncertainty:** low-sample cells fade toward neutral (value-suppressing palettes, Correll et al. CHI 2018 — not re-checked) **L**.
- **Categories:** at most 6 hues, Okabe–Ito adapted for dark mode, always paired with a glyph. The script flags sky vs bluish-green as nearly identical under tritanopia.
- **Flows:**
  - ArcLayer with `greatCircle:true`. On GlobeView set `parameters:{cullMode:'none'}`, or arcs vanish at some angles [S24] **H**.
  - flowmap.gl for aggregated origin–destination flows (paired with DuckDB at FOSDEM 2026) [S26] **M**.
  - TripsLayer for "long exposure" trails.
- **Labels:**
  - MapLibre handles basemap collision.
  - Data labels use CollisionFilterExtension: GPU-based, priority −1000…1000, approximate point-in-polygon test, no CPU aggregation layers. **GlobeView support is unconfirmed — spike this early** [S23] **H**.
  - Label only the top N.
- **One engine:** MapLibre globe plus deck.gl 9.4 interleaved [S19–S22] **H**. A 3,000→25 km Lens needs continuous orbit-to-street zoom.
  - MapLibre: globe since v5.0 (Jan 2025); atmosphere via `sky`; v6.0 (Jul 2026) is ESM-only and requires WebGL2.
  - deck.gl 9.4: supports MapLibre v4.5.1, v5 and v6; all layers are ported to WebGPU (experimental).

## 5. Design system: "Deep Field"
Principles:
- The planet is the hero; chrome recedes.
- **Only information emits light** (matte UI, glowing data).
- Instrument precision: ticks, graticules, mono numerals.
- Calm by default; loud only on anomalies.
- Every pixel traces to a source.

| Token | Hex | Role | WCAG check |
|---|---|---|---|
| void / canvas | `#030509` / `#070A10` | space / app background | — |
| surface-1/2/3 | `#0D1219` / `#141A22` / `#1C232C` | panels / cards / popovers | elevation = lightness, not shadow |
| border-subtle / strong | `#272E38` / `#38404B` | decorative separators | exempt |
| border-control | `#676F7A` | input/control outlines | ≥3.12:1 on all surfaces |
| text-primary/secondary/tertiary | `#EBEFF4` / `#B4BBC5` / `#8A939F` | text | tertiary ≥5.09:1 everywhere |
| **lens-500** | `#C3F344` | reticle, focus ring, selection | 14.5:1 on surface-1; dark text on it 15.8:1 |
| lens-300/700/900 | `#DEFF87` / `#759B21` / `#233407` | hover / strokes / selected tint | — |
| danger / warning | `#FB575D` / `#FCB442` | UI status only | warning≈lime for deuteranopes (ΔE 0.077) → icon + text |
| ocean / land / coast | `#030910` / `#11181F` / `#2C3742` | basemap | — |
| atmosphere / city-lights | `#478CC4` / `#F9BE78` | rim glow / night side | — |

Generate themes the Linear way, from three inputs, to get high-contrast and light "Paper" themes (for briefings and print) [S12]. Easter egg: a **"Terminal"** theme, amber on black, all mono.

**Type (all OFL):**
- **Inter 4.x** for UI: its opsz axis = Inter Display; tabular figures [S31] **H**.
- **Newsreader** for headlines: Production Type, made for on-screen reading, variable [S32] **H**.
- **JetBrains Mono** for telemetry (licence from memory) **L**.
- Noto fallbacks (Arabic, Devanagari, CJK, Hebrew) via `unicode-range`.

| Token | Face | Desktop | Mobile | Use |
|---|---|---|---|---|
| micro | Mono 500 caps +4% | 11/14 | 11/14 | HUD labels, legends, kbd |
| data | Mono 450 tnum | 12/16 | 12/16 | coords, times, counts |
| caption | Inter 450 | 12/16 | 13/18 | source · time |
| ui | Inter 450/550 | 13/18 | 15/20 | dense default UI |
| body | Inter 400 | 14/21 | 16/24 | summaries, chat (iOS inputs ≥16 px) |
| title-sm | Inter 600 | 15/20 | 16/22 | panel titles |
| headline-sm | Newsreader 550 | 17/22 | 18/24 | story cards |
| headline | Newsreader 500 | 22/28 | 22/28 | dossier header |
| display | Newsreader 450 | 32/36 | 28/32 | briefings |
| hero | Inter Display 600 −2% | 56/56 | 40/42 | landing, Tour chapters |

**Glass, sparingly.** NN/g found that translucency over busy content hurt legibility and predictability [S14], and Apple added a higher-opacity option within weeks [S15].
- Panels at least 90% opaque, blur ≤12 px, 1 px top highlight.
- No text directly on the moving globe without a scrim.
- `backdrop-filter` over a 60 fps canvas re-blurs every frame. This is engineering judgment; profile it.
- Honour `prefers-reduced-transparency` (not yet Baseline [S35]) **and** provide a "Solid panels" toggle.

**Motion** exists for orientation, feedback and causality.
- Durations: 120 ms press/hover, 180 ms popover, 280 ms sheet; camera flights 0.8–2.4 s, scaled by distance.
- Springs via Motion (`motion/react`, v12) [S33].
- Shared-element morphs via React 19.3 `<ViewTransition>` (stable since Sep 2026). React does **not** disable them for reduced motion, so gate them in CSS [S45] **H**.
- MapLibre `flyTo` already falls back to `jumpTo` under reduced motion unless `essential:true` [S21] **H**.

**Sound:** off by default, master mute, 50–200 ms Web Audio ticks, never the only feedback channel [S34] **M**.

## 6. Layout
```
┌ ◉ GlobaLens  [⌘K  places · stories · entities · or ask]      ● LIVE  24h▾  🔔 ┐ 44px
├ IN THE LENS ─────┬──────────── globe canvas ────────────┬ DOSSIER / ANALYST ┤
│ Kyiv · 380 km    │                                       │ non-modal sheet   │
│ 214 stories ▲38% │        ╭─────── ◯ ───────╮  ← Lens     │ 420px, resizable  │
│ tone ▇▅▂▃▆       │        ╰─────────────────╯             │ breadcrumb stack  │
│ ▣ story cards…   │ [Tone ▾]               [+][−][⌖][2D/3D]│                   │
│ 360px · J/K nav  │                         [locator inset]│                   │
├ CHRONOSCOPE ▁▂▃▅▇█▇▅▃▂▁▂▅▇█  [◀ ▶ ▶▶ 6h/s]  ⟦brush⟧ ──────────● LIVE ────────┤ 88px
└ Updated 42 s ago · 18,204 stories/24 h · 61 languages                       ┘
```
**Mobile:**
- Full-bleed globe with a floating search pill.
- **The Lens is centred in the unobscured area**: camera padding tracks the sheet height.
- A mini-scrubber sits above a Base UI Drawer with snap points at 120 px → 0.5 → 0.92 [S41] **H**.
- The map stays interactive at the two lower snap points.
- The canvas uses `touch-action:none`; the sheet drags only from its grabber.
- In landscape the bottom sheet becomes a side sheet.
- Vaul's README says "This repo is unmaintained" [S42] **H**.

## 7. Signature interaction: Lens 3.0
- **Aperture ring:** a geodesic radius from 25 to 3,000 km. Drag the edge, pinch, or press `[ ]`. The query covers the H3 cells in a spherical cap, not a circle of screen pixels.
- **Time bezel:** an outer ring you rotate, like a watch bezel, to scrub time. Ticks mark hours or days; double-click returns to LIVE.
- **Focus:** type a topic or entity; everything else desaturates, like depth of field.
- **See-through modes (magic lens [S58]):** the area inside the ring shows a *different* encoding:
  - **Sources:** arcs coming in from the countries covering this place.
  - Languages, Tone or Entities.

  This puts "See beyond the headlines" on the screen.
- **HUD:** place, count, Δ vs baseline, 5-cell tone bar, top 3 entities, language count. Tabular mono numerals, so nothing shifts as values change.
- **States:**
  - idle: 1.5 px lime ring
  - dragging: sonar ring
  - settling: 150 ms magnetic snap to the densest cluster
  - locked
  - pinned: a watch with an alert threshold
  - **agent-driven:** marching dashes and an "Analyst" label
  - split: two rings joined by a Δ-tone label
- **Drag-free equivalents** (WCAG 2.5.7/2.5.8) [S36,S39] **H**:
  - Click any point and it glides into the Lens.
  - Arrow keys pan.
  - +/− buttons are ≥32 px.
  - Build the ring and bezel on React Aria `useMove`, which handles mouse, touch and keyboard arrows.

## 8. Wow micro-interactions
1. **Inbound coverage arcs:** when the Lens settles, arcs stream in from every country covering the place. Width = volume, colour = that country's tone. This is the hero moment.
2. **Propagation replay:** opening a story fires arcs, in chronological order, to each country that picked it up, with ring pulses on landing [S3].
3. **Dot-matrix dissolve:** at orbit zoom the globe is 60k Fibonacci dots [S4]; it crossfades to vector coastlines past z≈3.
4. **Live terminator:** real-time day/night shading, with city lights on the night side.
5. **Bezel scrub with inertia:** the hexes breathe through time while the histogram cursor moves in lockstep.
6. **Magnetic detent:** the Lens snaps to clusters, with an optional tick sound and haptics where supported.
7. **Headline glide:** a feed card morphs into the dossier header (`<ViewTransition>`) [S45].
8. **Citation hydration:** streamed claims get numbered chips. Hovering one flies a ghost marker to the source's location and lights its timeline bar.
9. **Constellation hover:** hovering an entity lights up its stories worldwide, joined by faint lines.
10. **Rolling tabular counters** with no layout shift.
11. **Anomaly breath:** a 4 s halo plus a ▲ glyph when z > 3. Never more than 3 flashes per second.
12. **Return-to-live pill** that winds the bezel back forward.
13. **Agent cursor:** a labelled, Figma-style cursor while the Analyst flies the camera. Any user drag interrupts it.
14. **Snapshot (`S`)** produces a permalink and a generated OG card [S47].
15. **Palette geo-preview:** ⌘K results light up a mini-globe before you commit.
16. **Split-lens diff:** shared entities stack in the middle; divergent framings fan out to either side.

## 9. Accessibility (WCAG 2.2 AA)
WCAG 3 is still a draft; Candidate Recommendation is not expected before roughly 2027 [S37] **M**.
- **WCAG 2.2 criteria that apply** [S36] **H**:
  - 2.5.7: the Lens must work without dragging.
  - 2.5.8: targets ≥24 px (use 32–44).
  - 2.4.11: sheets and the timeline must not obscure focus.
  - 1.4.11: 3:1 contrast for the ring and handles (lens-500 >12:1).
- **2.2.2 Pause, Stop, Hide** applies to auto-rotation, the live ticker and ambient arcs. A "Freeze frame" control covers it and also helps reading.
- **Screen readers:** the canvas is `aria-hidden`; **the Lens feed list is the accessible representation**.
  - A debounced `aria-live` summary fires after movement ("Khartoum, 48 stories, mostly negative, up 120%").
  - A Table-view toggle.
  - This follows guidance to offer text alternatives and announce pan/zoom [S40] **M**.
- **Stretch:** cell-to-cell navigation of the hex grid by keyboard and screen reader, using **Data Navigator**. It puts a semantic HTML layer over WebGL, supports spatial relations, and is MIT-licensed [S38] **H**.

## 10. Perceived performance
- SSR shell + SVG globe placeholder crossfading to WebGL over 600 ms [S3], plus a skeleton feed.
- Load all 5,882 res-2 cells first, then refine to res 3/4 around the Lens [S25].
- Adaptive quality tiers (DPR cap 1.5, fewer arcs, sparser dots) when FPS stays below 55.5 [S3]. Pause rendering when hidden or off-screen [S4].
- Loading indicators per NN/g: nothing under 1 s; under 10 s, a skeleton for the page or a spinner for a module; over 10 s, a progress bar [S44] **H**.
- Next 16 Cache Components streaming [S46], optimistic pin/save, prefetch the dossier on hover.

## 11. AI "Analyst" UX
- **Ops log.** AI SDK v7 (npm `ai` 7.0.156) gives typed `tool-<name>` parts with states `input-streaming → input-available → output-available | output-error`, plus `approval-requested`/`output-denied` and `step-start` dividers [S50] **H**. Render each part as a mono row: `search_stories · Sudan · 72h · 1.2 s · 148 hits`.
- **The agent drives the instrument** through frontend tools: `flyTo`, `setLens`, `setTime`, `highlightCells`, `openStory`, `compare`.
  - Implement them with AI SDK client tools (`onToolCall` + `addToolOutput`) [S50], or with CopilotKit v2 `useFrontendTool` over AG-UI (shared-state diffs, frontend tools, interrupts) [S52,S53] **H**.
  - Every agent action is announced and undoable.
- **Approval** for side effects such as creating watch-lenses or sending digests [S50].
- **Claim-level citations, an action plan, footprints and disclosure** (Shape of AI governors and trust builders) [S55] **H**.
- **Generative UI:** tool outputs render as LensCard, CompareTable, ToneSparkline, TimelineSnippet or MapInset, not walls of text.
- **Components:** shadcn AI Elements, copied into the project rather than installed. AI SDK Elements is being deprecated at the end of November 2026 [S43,S51] **H**.

## Recommendations for GlobaLens 3.0
1. **MUST** — Reposition around the Lens as a magic-lens instrument with five modes; don't chase layer counts.
2. **MUST** — Adopt the Deep Field tokens (OKLCH, three-input generator, contrast-verified) in Tailwind v4 `@theme`. Use shadcn on Base UI, plus React Aria hooks for the custom instruments.
3. **MUST** — One engine: MapLibre globe + deck.gl 9.4 interleaved. In week 1, spike CollisionFilterExtension and ArcLayer on the globe.
4. **MUST** — Accessibility architecture from phase 1: drag-free Lens, the feed as the screen-reader representation, a pause control, reduced motion and reduced transparency.
5. **MUST** — URL-as-state (nuqs) and an OG card for every Lens; this is the sharing loop.
6. **SHOULD** — Chronoscope and Replay on pre-binned hourly H3 aggregates.
7. **SHOULD** — Surprise as the default encoding; the 5-class tone scale.
8. **SHOULD** — The Analyst with frontend tools, an ops log, claim-level citations and undo.
9. **SHOULD** — A performance budget: 60 fps with adaptive tiers, the placeholder crossfade, NN/g loading thresholds.
10. **COULD** — An MCP App mini-Lens, Tours, Terminal/Paper themes, Data Navigator hex navigation, opt-in sound.

## Sources
- S1 World Monitor — https://www.worldmonitor.app/
- S2 World Monitor README — https://github.com/koala73/worldmonitor/blob/main/README.md
- S3 GitHub globe — https://github.blog/engineering/user-experience/how-we-built-the-github-globe/
- S4 Stripe globe — https://stripe.com/blog/globe
- S5 earth.nullschool about — https://earth.nullschool.net/about
- S6 nullschool background — https://bellingcat.gitbook.io/toolkit/more/all-tools/nullschool-earth-map · https://lists-archive.okfn.org/pipermail/open-science/2015-April/008586.html
- S7 Windy community (picker/playback/particles) — https://community.windy.com/topic/31261/error-with-particles-animation-when-using-playback-function · https://community.windy.com/topic/34325/particles-animation-by-framerate
- S8 Flightradar24 — https://www.flightradar24.com/blog/inside-flightradar24/an-overview-of-the-updated-flight-information-panel-on-flightradar24-com/ · https://scout.appaloosa.io/en/apps/ios/se.resenatverket.FlightRadar24-Free/history?lang=en
- S9 Liveuamap (EU data portal) — https://data.europa.eu/en/news/live-universal-awareness-map-displays-events-related-russias-invasion-ukraine
- S10 Bloomberg, concealing complexity — https://www.bloomberg.com/company/stories/how-bloomberg-terminal-ux-designers-conceal-complexity (fetch returned 403; content taken from a search summary)
- S11 Blueprint — https://blog.palantir.com/scaling-product-design-with-blueprint-25492827bb4a · https://open-design.ai/design-system/palantir-blueprint/
- S12 Linear redesign — https://linear.app/now/how-we-redesigned-the-linear-ui
- S13 Geist — https://vercel.com/geist · https://vercel.com/font · https://github.com/vercel/geist-font
- S14 NN/g Liquid Glass — https://www.nngroup.com/articles/liquid-glass/
- S15 iOS 26.1 Tinted — https://tidbits.com/2025/10/21/ios-26-1-to-add-optional-opacity-to-liquid-glass/
- S16 Google Earth AI — https://research.google/blog/putting-earth-ai-to-work-geospatial-agents-for-our-planets-biggest-challenges/ · https://winbuzzer.com/2025/10/23/gemini-now-supercharges-google-earth-turning-maps-into-a-conversational-ai-xcxwbn/
- S17 Ground News Blindspot — https://about.ground.news/blindspot
- S18 Mapbox storytelling — https://github.com/mapbox/storytelling
- S19 MapLibre globe/atmosphere — https://maplibre.org/maplibre-gl-js/docs/examples/display-a-globe-with-an-atmosphere/ · https://maplibre.org/roadmap/maplibre-gl-js/globe-view
- S20 MapLibre v6 — https://maplibre.org/news/2026-08-02-maplibre-newsletter-july-2026/ · https://geo.malagis.com/maplibre-gl-js-v6-mandatory-webgl-and-esm-only.html
- S21 MapLibre Map API — https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/
- S22 deck.gl What's New / releases — https://deck.gl/docs/whats-new · https://github.com/visgl/deck.gl/releases
- S23 CollisionFilterExtension — https://deck.gl/docs/api-reference/extensions/collision-filter-extension
- S24 ArcLayer — https://deck.gl/docs/api-reference/layers/arc-layer
- S25 H3 resolution table — https://h3geo.org/docs/core-library/restable
- S26 flowmap.gl — https://www.npmjs.com/package/flowmap.gl · https://fosdem.org/schedule/event/DC9M73-sqlrooms-flowmap
- S27 Correll & Heer, Surprise Maps — https://idl.uw.edu/papers/surprise-maps
- S28 xkcd 1138 — https://xkcd.com/1138/
- S29 Crameri colour maps — https://tesselle.r-universe.dev/khroma/doc/crameri.html
- S30 Radix 12-step scale (token semantics) — https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale
- S31 Inter — https://github.com/rsms/inter/releases · https://en.wikipedia.org/wiki/Inter_(typeface)
- S32 Newsreader — https://github.com/productiontype/Newsreader
- S33 Motion — https://motion.dev/docs/react-upgrade-guide
- S34 Web audio for UI — https://www.freecodecamp.org/news/web-audio-for-the-user-interface-1592687f898c
- S35 MDN prefers-reduced-transparency — https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-transparency
- S36 WCAG 2.2 new criteria — https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- S37 WCAG 3 status — https://abilitynet.org.uk/resources/digital-accessibility/what-expect-wcag-30-web-content-accessibility-guidelines
- S38 Data Navigator — https://dig.cmu.edu/data-navigator/ · https://github.com/cmudig/data-navigator
- S39 React Aria useMove — https://react-aria.adobe.com/useMove
- S40 Map accessibility — https://learn.microsoft.com/en-au/azure/azure-maps/map-accessibility · https://www.boia.org/blog/interactive-maps-and-accessibility-4-tips
- S41 Base UI Drawer — https://base-ui.com/react/components/drawer · https://ui.shadcn.com/docs/components/base/drawer
- S42 Vaul — https://github.com/emilkowalski/vaul
- S43 shadcn changelog — https://ui.shadcn.com/docs/changelog
- S44 NN/g skeleton screens — https://www.nngroup.com/articles/skeleton-screens/
- S45 React 19.3 / ViewTransition — https://react.dev/blog/2026/09/09/react-19-3 · https://react.dev/reference/react/ViewTransition
- S46 Next.js 16 — https://nextjs.org/blog/next-16
- S47 ImageResponse / Satori — https://nextjs.org/docs/app/api-reference/functions/image-response · https://github.com/vercel/satori
- S48 nuqs v2 — https://nuqs.47ng.com/docs/migrations/v2
- S49 cmdk releases — https://github.com/pacocoursey/cmdk/releases
- S50 AI SDK tool usage / npm — https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage · https://registry.npmjs.org/ai/latest
- S51 AI SDK Elements (deprecation banner) — https://elements.ai-sdk.dev/
- S52 AG-UI — https://docs.ag-ui.com/introduction
- S53 CopilotKit frontend tools — https://docs.copilotkit.ai/frontend-tools
- S54 MCP Apps — https://github.com/modelcontextprotocol/ext-apps
- S55 Shape of AI — https://www.shapeof.ai/
- S56 Base UI 1.0 / shadcn default (secondary) — https://blog.openreplay.com/shadcn-ui-radix-base-ui-switch/
- S57 Radio Garden — https://en.wikipedia.org/wiki/Radio_Garden
- S58 Bier et al., "Toolglass and Magic Lenses" (SIGGRAPH 1993) — https://dl.acm.org/doi/10.1145/166117.166126 (fetch returned 403; not re-verified)
