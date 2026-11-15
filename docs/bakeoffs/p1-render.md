# P1 render bake-off: note (in progress)

**Status on 15 November 2026: no decision.** The page, the sample and the harness are built and rehearsed. No gating run has been made on the desktop, and the reference Android is not chosen. Nothing below is a GO or a no-go.

The pre-registration is `lab/p1-render/prereg.md`; this note reports against it. Every number here comes from a file in `lab/p1-render/results/`.

## What exists

- **Sample.** 300,000 points from GDELT's `gkg.csv.zip` files for 12–14 November 2026, both streams, 576 files, none left out. The record is prereg §4.4.
- **Page.** `lab/p1-render/`: MapLibre GL JS 6.18.0, deck.gl 9.4.1 (`@deck.gl/maplibre`, interleaved), flechette 2.8.0, bundled with esbuild 0.28.2. Those exact versions were on npm on 15 November 2026.
- **Harness.** `lab/p1-render/run.sh`. It opens each run in Chrome with a fresh profile, notes the machine's state, and collects the page's JSON. The gating suite refuses to start unless the external display is disconnected and the Mac is on mains power.
- **Pick list.** `lab/p1-render/picks.json`, made once.

## Runs so far: development and rehearsal only

None of these gates. They are kept because the pre-registration keeps every timed run.

| Run | Where | Result |
|---|---|---|
| Orbit, 300k, `dev-headless` | headless Chrome, pixel ratio 1, 60 Hz | 59.9 fps p50, which is that display's limit |
| Orbit, 300k, `rehearsal` | Chrome full screen on the built-in display at 120 Hz, pixel ratio 2; **external display attached, 12 applications open** | 109.9 fps p50 (median interval 9.1 ms); p95 36.0 ms, p99 46.9 ms; 127 of 2,046 intervals over 33.3 ms |
| Far side, 4 of 24 stops, `rehearsal` | as above | 0 violations, 0 control failures |
| Labels, `rehearsal` | as above | 0 failures at the five cameras |
| Picks, 40 of 1,000, `rehearsal` | as above | 40 correct; 0 of 40 empty-space probes returned anything |
| `projectTile()`, `rehearsal` | as above | Largest distance 0.21–0.34 px in the morph and in Mercator; 3.93 px on the globe, at a point 66.5° from the centre |

## Found while building

1. **deck.gl's globe view culls back faces, and that removes arcs.** With the default setting an arc drew 5 marker pixels; with culling off it drew 3,164. Arcs are therefore drawn with culling off and hidden on the far side by a horizon test in the shader. The plan's prior expected "work on arc depth testing"; the work turned out to be culling, and depth testing was not needed.
2. **For discs lying on the surface, the same culling is a horizon test.** A disc faces away from the camera exactly when it is beyond the horizon. The page keeps the plan's horizon test in the vertex shader as well. With both switched off, far-side discs show through the globe, which is what the control in §5.4 needs.
3. **The horizon test must use the disc's centre.** Testing each corner separately tore discs at the limb into streaks.
4. **At zooms 10–12 a far-side point can project inside the viewport.** The map is still a globe there, and MapLibre's `project()` places a point near the antipode inside the view, as if seen through the planet. The label and `projectTile()` checks therefore apply "on the near side" at every zoom, not only on the low-zoom globe.
5. **The labels at the morph and Mercator cameras are one stack.** The densest part of the sample is one coordinate in Washington DC (17,641 of the 300,000 points). The 33 test labels in view at zooms 10.5–13 all sit on it. The check passes as written and is thin evidence there; at zoom 3 it covers 209 labels.

## Choices the pre-registration left open

Fixed before any gating run, and listed so they can be checked:

- Discs lie on the surface (not billboards) and are drawn without a depth test. Arc height factor 0.3.
- The 500 labels and the 200 arcs are drawn from the sample with seeds 20261115 and 20261114.
- A pick's target is placed at a seeded position inside the central 80% of the view. Its empty-space probe is 30 px away.
- Far side: 50 arcs per set per stop, each between 2° and 30° long; near discs for the pick control have no other place within 7 px; "mechanism off" means no horizon test, no culling and no depth test.
- Labels: "the densest part" is the busiest 0.1° cell and the most common coordinate in it.
- `projectTile()`: 500 coordinates drawn across the sample and the 500 nearest the densest point, drawn as 5 px squares; a point's position is the centroid of its pixels within 8 px.
- The orbit zoom for a 1440 × 900 view is 2.7398.

## Calibration so far

| | Prior (prereg §3.3) | Measured |
|---|---|---|
| Sample size | about 182k points a day; two days needed | 111k, 169k and 178k on the three days; **three** days needed. The prior missed: the first day was a Saturday |
| Exact package versions on npm | not checked when the prereg was written | present |
| Cost | $0 | $0 |

The criteria themselves are scored when the gating runs exist.

## What is left

1. The desktop gating runs: `./run.sh desktop` with the external display disconnected, other applications closed, on mains power. About 1 h 45 min, during which the Mac is left alone.
2. The stand-in and the smoke test: `./run.sh standin` and `./run.sh projtile`.
3. The phone half, when a reference Android is named (`./run.sh phone` prints the steps).
4. ADR-0002, the calibration row and this note's final form.
