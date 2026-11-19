# P1 render bake-off: note (desktop half measured, no decision)

**Status on 19 November 2026: no decision.** The desktop half was measured on 15–17 November, and every desktop criterion is met on the M3 Pro. The phone half has not started: the reference Android is not chosen, and C2 can only be measured on it. The GO decision waits for the phone (prereg §6). Nothing below is a GO or a no-go.

The pre-registration is `lab/p1-render/prereg.md`; this note reports against it. Every number here comes from a file in `lab/p1-render/results/`, and `node lab/p1-render/tools/summarise.mjs desktop` prints the table again from those files.

## Desktop results, gating

M3 Pro, built-in display at 120 Hz, external display disconnected, mains power, Chrome in full screen with a fresh profile, 300,000 points, 1440 × 900 CSS px.

| Criterion | Threshold | Runs | Result | Met |
|---|---|---|---|---|
| C1 frame rate | ≥ 50 fps p50 over the 30-s orbit | 5 | 119.0 fps p50 in each run; median of the five 119.0 | Yes |
| C3 picks | ≥ 990 of 1,000 correct in every run | 3 | 1,000 of 1,000 in each run | Yes |
| C4 far side, discs | 0 violations | 3 × 24 stops | 0 | Yes |
| C4 far side, arcs | 0 violations | 3 × 24 stops | 0 | Yes |
| C4 far side, labels | 0 violations | 3 × 24 stops | 0 | Yes |
| C5 labels | 0 failures | 3 × 5 cameras | 0 | Yes |

No gating run was void. The renderer string names the M3 Pro's GPU in every run, no tile and no sample load failed, low-power mode was off, and the sample and pick-list hashes match prereg §4.4.

### C1: the median is at the display's limit, the average is not

| Run | fps p50 | Frames per second over the lap | Interval p95 | Interval p99 | Intervals over 33.3 ms |
|---|---|---|---|---|---|
| 1 | 119.0 | 83.6 | 24.4 ms | 32.4 ms | 19 of 2,509 |
| 2 | 119.0 | 82.7 | 24.8 ms | 32.5 ms | 14 of 2,482 |
| 3 | 119.0 | 82.7 | 24.4 ms | 32.9 ms | 22 of 2,481 |
| 4 | 119.0 | 83.1 | 24.6 ms | 32.2 ms | 14 of 2,492 |
| 5 | 119.0 | 83.0 | 24.5 ms | 32.1 ms | 19 of 2,491 |

- **fps p50 is the pre-registered measure** (1000 ÷ the median frame interval, §5.2). The median interval is 8.4 ms, which is one refresh of this display. A result at the refresh rate means "at the limit", not "exactly that fast".
- **The page did not draw 119 frames a second.** It drew about 83 (frames per second over the lap is 1000 ÷ the mean interval). With each interval rounded to the nearest whole number of refreshes (8.33 ms at 120 Hz), 67.9% of the intervals across the five runs were one refresh long, 19.1% two, 10.6% three, 1.9% four and 0.4% five or more. The longest interval in a run was 44.5–52.3 ms.
- Either figure is above the threshold of 50.
- Run on 15 November 2026, 23:58 to 16 November 00:08 UTC. Load average at the start of each run: 2.4–4.6.

### C3: picks

Each run made the 1,000 scripted picks across zooms 10 to 12 and 1,000 empty-space probes. All 1,000 picks were correct in each of the three runs, no empty-space probe returned anything, and no pick had to go on without the map coming to rest. The runs took 630–732 s.

### C4: far side

The three runs gave the same numbers at every stop.

- **Discs.** Every stop had far-side points that would be in view through a transparent globe (1,144 to 166,928 of them). With the horizon test on they drew 0 marker pixels and nothing was picked anywhere in the viewport. Of 1,200 picks per run aimed at where a far-side disc would show, 0 returned one. With the test off the same sets drew 1,272 to 125,599 pixels, so the control shows what a violation looks like. Near-side discs kept all their pixels, and 1,143 of 1,143 near-side picks returned the right disc.
- **Arcs.** 50 far-cap arcs per stop drew 0 pixels and were not picked. With the horizon test off they drew 4,433 to 13,739 pixels. Near-side arcs kept all their pixels. **The check covers arcs 2° to 30° long**, which rise at most 0.078 globe radii.
- **Labels.** 29 to 295 far-side labels per stop drew 0 pixels and none was returned by a query. MapLibre has no switch that shows far-side labels, so the only control is that near-side labels do draw. At one stop of the 24 (zoom 4, centre −135°, −50°) no near-side label was in view, so the control says nothing there.

### C5: labels

The three runs gave the same numbers.

| Camera | Projection | Labels expected on the near side | Returned | Label pixels with no discs / discs beneath / discs above |
|---|---|---|---|---|
| zoom 3 | globe | 209 | 209 | 32,194 / 33,645 / 13,108 |
| zoom 10.5 | morph | 33 | 33 | 1,036 / 1,042 / 791 |
| zoom 11 | morph | 33 | 33 | 1,031 / 1,035 / 846 |
| zoom 11.5 | morph | 33 | 33 | 1,034 / 1,034 / 840 |
| zoom 13 | Mercator | 33 | 33 | 1,044 / 1,047 / 883 |

Labels drawn over the discs keep their pixels, and discs drawn over the labels cover part of them, so the draw order works both ways. **The four close cameras are thin evidence:** their 33 labels all sit on one Washington DC coordinate (finding 5 below).

## Desktop results, reported and not gating

| What | Valid runs | fps p50 | Frames per second over the lap | Interval p99 |
|---|---|---|---|---|
| Pixel ratio 1.5 (the battery tier's) | 5 | 119.0 each | 84.4–85.0 | 27.7–29.2 ms |
| Scene with 200 arcs and 500 labels added | 5 | 119.0 each | 82.1–82.4 | 32.7–34.1 ms |
| Phone stand-in: 100k points, 412 × 915 at pixel ratio 2.625, 6× CPU throttle | 5 | 120.5 each | 113.3–116.4 | 16.7–17.5 ms |

- **The stand-in's throttle was applied.** The page's fixed piece of main-thread work took 74–76 ms under it, against 12.2–13.1 ms in the C1 runs.
- **The stand-in cannot grant C2** (prereg §6). It shows that the main thread is not the limit at 100k points even six times slower. It says nothing about a phone's GPU, memory or heat.
- **`projectTile()` smoke test** (not a GO criterion). A custom GLSL layer followed MapLibre through the transition: the largest distance from MapLibre's own projection was 0.21–0.34 px at zooms 10.5 to 13, with every point found. On the globe at the orbit zoom the mean was 0.18 px and the largest 3.93 px, at one point 66.5° from the centre.

## Where the runs departed from the pre-registration

1. **Other applications were not closed.** §5.7 says they are for gating runs. The host record counts 8 visible applications on 15 November and 10 on 17 November, and the load average at the start of a gating run was between 2.4 and 6.9. Load is not one of the reasons a run is void. Other work competes with the page for the machine, so it is expected to lower a frame rate, not raise it.
2. **The suite was not run in one sitting.** C1 and the first run at pixel ratio 1.5 were on 15–16 November; everything else was on 17 November, 16:46 to 18:04 UTC. Chrome updated itself in between, from 157.0.8103.52 to 157.0.8103.79.
3. **The harness changed after the C1 runs** (prereg §11, amendment 5). The page did not: the results name three commits, `ba391bb`, `232f507` and `68e3f9d`, and the page's source, the collector and the pick list are identical in all three.
4. **The stand-in ran last.** Prereg §6 says it runs first, so that it can show a problem early. It ran on 17 November after every desktop run, so it warned of nothing early. The remaining gating checks also ran before the remaining reported runs; the pre-registration fixes no other order.

## Void runs and runs that gave no result

All are kept in `lab/p1-render/results/`, with the suite logs beside them.

| Run | When (UTC) | What happened |
|---|---|---|
| Pixel ratio 1.5, run 2 | 16 Nov, 00:11 | Void: the tab was hidden and the window lost focus 58.6 s after the page loaded, near the end of the timed lap. Repeated as run 2b |
| Pixel ratio 1.5, run 3 | 16 Nov, 00:12 | No result: the window was hidden, the page stopped drawing, and the suite stopped after 180 s. Repeated as run 3b |
| Far side, first attempt at run 1 | 16 Nov, 00:18 | No result, for the same reason; the suite stopped after 900 s |
| Two development runs with the debugger attached | 16 Nov, 00:38 and 00:40 | No result, for the same reason. They showed the cause |
| Stand-in, runs 1 to 5 | 17 Nov, 17:44–17:53 | Void: "window not focused at start" in each. 120.5 fps p50 each. Repeated as runs 1b to 5b |

**The cause of the first four.** The Mac was in use. Each time Chrome went full screen, another application was brought back to the front within seconds. A hidden page gets no frame callbacks, so it never finishes and never reports.

**The cause of the stand-in's five.** With the debugger attached, Chrome started on a blank page, which puts the keyboard focus in the address bar. The window was in front and visible, and the page still did not have the focus.

## Found while building and running

1. **deck.gl's globe view culls back faces, and that removes arcs.** With the default setting an arc drew 5 marker pixels; with culling off it drew 3,164. Arcs are therefore drawn with culling off and hidden on the far side by a horizon test in the shader. The plan's prior expected "work on arc depth testing"; the work turned out to be culling, and depth testing was not needed.
2. **For discs lying on the surface, the same culling is a horizon test.** A disc faces away from the camera exactly when it is beyond the horizon. The page keeps the plan's horizon test in the vertex shader as well. With both switched off, far-side discs show through the globe, which is what the control in §5.4 needs.
3. **The horizon test must use the disc's centre.** Testing each corner separately tore discs at the limb into streaks.
4. **At zooms 10–12 a far-side point can project inside the viewport.** The map is still a globe there, and MapLibre's `project()` places a point near the antipode inside the view, as if seen through the planet. The label and `projectTile()` checks therefore apply "on the near side" at every zoom, not only on the low-zoom globe.
5. **The labels at the morph and Mercator cameras are one stack.** The densest part of the sample is one coordinate in Washington DC (17,641 of the 300,000 points). The 33 test labels in view at zooms 10.5–13 all sit on it.
6. **A hidden page never reports.** The Chrome driver now watches which application is frontmost during a run. If it is not this Chrome for 4 s, the run is logged as void at once and Chrome is closed.
7. **Long arcs leave the globe's outline.** The scene's own 200 arcs join random pairs of sample points with a height factor of 0.3. In the far-side pictures the long ones loop well outside the globe into the space around it. That is where such an arc is, and it is not a far-side defect, but the gating check does not cover arcs longer than 30°. Whether that look is wanted is a design question for the product.

**Pictures.** Run 1's far-side pictures (24) and label pictures (5) are in `lab/p1-render/results/shots/`. Three were looked at for this note (far side at the orbit zoom and at zoom 4, labels at zoom 3) and showed nothing through the globe. The other 26 have not been looked at.

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

The prior is prereg §3. C2 and the overall prior for GO (about 50%) are scored when the phone has run.

| | Prior | Measured on the desktop | |
|---|---|---|---|
| C1 | 120 fps p50, the display's limit (97% to meet the threshold) | 119.0 fps p50, at the limit. About 83 frames a second averaged over the lap, which the prior did not foresee | Met |
| C3 | 995 of 1,000 (75%) | 1,000 of 1,000, three times | Met |
| C4 discs | 0 violations (93%) | 0 | Met |
| C4 arcs | 0 in the far-cap check after work, first run expected to fail (80%) | 0. The first build's arcs did not draw at all; the work was culling, not depth testing | Met |
| C4 labels | 0 violations (96%) | 0 | Met |
| C5 | Pass (96%) | Pass, with thin evidence at the close cameras | Met |
| Sample size | about 182k points a day; two days needed | 111k, 169k and 178k on the three days; three days needed | Missed: the first day was a Saturday |
| Stand-in | 45 fps p50 | 120.5 fps p50 | Missed by a wide margin: at 100k points the main thread was not the limit, even six times slower |
| `projectTile()` | within 1 px in globe, morph and Mercator (90%) | within 0.34 px in the morph and Mercator; 3.93 px at one point near the limb on the globe | Missed on the globe as written |
| Cost | $0 | $0 | Met |

## What is left

1. **The phone half.** It needs a reference Android to be named (design note Q2). A prior for that device goes into prereg §11 before its first run, and `./run.sh phone` prints the steps.
2. **ADR-0002, the final calibration row, this note's final form and the short post.** All wait for the phone.
3. **Design note Q3** asks whether tasks 13 and 14 may start once "the M3 Pro passes with Chrome's 6× throttle as well". The pre-registration reads that as ≥ 30 fps p50 at 100k under the stand-in, and the stand-in gave 120.5. Q3 is still the owner's to answer.
4. **Upstream.** The arc culling in deck.gl's globe view may be worth a minimal reproduction. Filing one is a public post, so it waits for the owner's OK.
