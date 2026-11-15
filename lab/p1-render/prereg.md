# P1 render spike: pre-registration

**Status: written before any measurement.** On the day this file was written no GDELT file had been downloaded for the spike, no sample existed, no spike page existed and no frame had been timed. Written 14 November 2026 Pacific time (15 November UTC), for Phase 1 task 1 of `docs/3.0/master-plan.md` (revision 5). It fills in the outline in `docs/design/p1.md` §8.

**How to read it.**
- Every threshold is the plan's (§11, the P1 row) and is not open. This file may not change one.
- *(research)* keeps the plan's label: a value quoted or measured during research and not yet re-measured by a committed script.
- **Prior** marks an estimate written here before measuring. A prior is a guess to be scored later, not a result.
- **Proposed** marks a method choice made in this file where the plan fixes the goal and leaves the procedure open. §10 lists the ones the owner should look at before the first run.
- "Our arithmetic" marks a sum done here on the plan's numbers. None of it is a measurement.

**Edits after the first measurement.** Two kinds only: filling the blanks in §4.4, and adding dated entries to §11. Everything else stays as committed, and the Git history shows it.

**Amended on 15 November 2026, before any measurement.** The owner named this M3 Pro as the plan's desktop reference device, with every threshold unchanged, and the plan became revision 6. §2, §3.2, §5.2, §5.8, §6 and §10 read as amended. §11 holds the dated entries, their reasons and the wording they replaced. The file as first committed is commit `61cbc48`.

---

## 1. Question, tag and contenders

**Question.** Can the open stack carry the globe on a desktop and on a mid-range phone?

**Tag.** Decision (genuinely uncertain).

**Contenders.**

| | Contender | Built for the spike |
|---|---|---|
| A | MapLibre 6.18 (exact pin) + deck.gl 9.4.1 `MapLibreOverlay`, interleaved, WebGL2 | Yes. Every criterion in §2 is measured on A |
| B | MapLibre + custom GLSL ("Plan B") | **No.** A short `projectTile()` smoke test stands in for it (§5.6). Plan B is built only on a no-go, as an L task that joins Phase 1 |

**Decision rule.** GO for A if every criterion in §2 is met. Otherwise Plan B.

---

## 2. GO criteria

The plan's row, word for word, as it reads in revision 6 (`master-plan.md` §11, P1). The row as first quoted here, from revision 5, is in §11, amendment 1.

> **GO** if: ≥50 fps p50 at 300k points in a 30-s scripted orbit on M3 Pro; ≥30 fps p50 at 100k on the reference Android; ≥99% of 1,000 scripted picks correct across the z10–12 morph; no far-side see-through and no picking through the globe for discs, arcs and labels; symbol labels work. Otherwise Plan B.

| # | Criterion | Threshold | Device | Method |
|---|---|---|---|---|
| C1 | Frame rate, desktop | ≥ 50 fps p50 at 300k points over a 30-second scripted orbit | the M3 Pro | §5.2 |
| C2 | Frame rate, phone | ≥ 30 fps p50 at 100k points | the reference Android | §5.2 |
| C3 | Picking through the morph | ≥ 99% of 1,000 scripted picks correct across the zoom 10–12 globe-to-Mercator morph | both | §5.3 |
| C4 | Far side | No far-side see-through and no picking through the globe, for discs, arcs and labels | both | §5.4 |
| C5 | Labels | Symbol labels work | both | §5.5 |

The plan's row gives C3–C5 no device of their own and lists "M3 Pro and the reference Android" as where the bake-off runs. **Proposed:** C3, C4 and C5 must hold on each device, because shader precision differs between a desktop GPU and a phone's.

---

## 3. Prior

### 3.1 The plan's

GO, with work on arc depth testing.

### 3.2 Claude's, written 14 November 2026

These describe the state at the close of the spike, after the fixes its timebox allows (§5.8), not the first run.

| # | Threshold | Expected result (**Prior**) | Chance the threshold is met | Why |
|---|---|---|---|---|
| C1 | ≥ 50 fps p50, 300k, M3 Pro | **120 fps p50**, which is the limit of the built-in display at 120 Hz (§5.2). If a typical frame takes longer than one refresh, the result falls to 60 fps, which still meets the threshold. Restated for the M3 Pro on 15 November 2026, before any timed run; the prior first written is in §11, amendment 1 | 97% | deck.gl's own documentation puts a scatterplot at about 1M points at 60 fps on a 2015 laptop *(research)*. 300k small discs are well inside that, and only the near hemisphere is filled. At 120 Hz the doubt is main-thread time per frame, not the GPU |
| C2 | ≥ 30 fps p50, 100k, reference Android | **40 fps p50** on a Galaxy A5x-class phone at its own pixel ratio | 80% | The risk is main-thread time per frame (MapLibre's camera update and the basemap's label placement, plus deck.gl), then fill at a pixel ratio near 2.6. The margin is thin and the phone is not chosen yet |
| C3 | ≥ 99% of 1,000 picks | **995 of 1,000 (99.5%)** | 75% | At zoom 10 in mid-latitudes the globe and Mercator pictures differ by about 1 px at the top edge of a 900-px-high view, and by about a quarter of that at zoom 12 (our arithmetic). That is inside the 3 px disc, so the morph itself should cost few picks. A larger error would mean the two libraries disagree about the camera, and that failure is wholesale: the outcome is two-humped, near 100% or far below 99% |
| C4 discs | none | **0 violations**, with a horizon test in the disc layer's vertex shader | 93% | The plan's own mechanism (§5 Geometry). The same shader runs in the picking pass, so drawing and picking should agree |
| C4 arcs | none | **0 violations in the far-cap check**, after work; first run expected to fail | 80% | The plan's prior names arc depth testing as the work. Arcs rise above the surface and span the limb, so a per-vertex test is coarse there |
| C4 labels | none | **0 violations** | 96% | MapLibre's own symbol layers. MapLibre is expected to hide them behind its own globe; not checked |
| C5 | labels work | **Pass**: MapLibre symbol labels in globe, morph and Mercator, in the right draw order with the discs | 96% | The research note sends labels to MapLibre symbol layers because deck.gl's text layer does not render on a globe *(research)* |

**Expected decision: GO, held loosely.** The chances above multiply to about 40% if they were independent (our arithmetic). They are not: most of them turn on one thing, how closely deck.gl 9.4.1's overlay follows MapLibre 6.18's globe. So this prior for GO is **about 50%**. That agrees with the plan's direction and is less sure than its wording. If it is a no-go, the expected cause is, in this order: the phone's frame rate (C2), picking in the morph (C3), arcs (C4).

### 3.3 Priors for the supporting steps

| Step | **Prior** |
|---|---|
| Sample size | One day gives about **182k** points, short of 300k, so two days are needed (about 365k before down-sampling). Our arithmetic on the plan's figures: 117k English articles × 58.5% city-level + 224k translated × 50.9%, all *(research)* |
| 6× CPU throttle stand-in (§6) | **45 fps p50** at 100k on the desktop under 6× throttling. It is expected to flatter the real phone, because throttling slows the main thread and leaves the GPU alone |
| `projectTile()` smoke test (§5.6) | Works in globe, morph and Mercator, within 1 px of MapLibre's own projection (90%). An official example ran on 6.16.0 *(research)* |
| Cost | $0 |

A device-specific prior for the reference Android is added to §11 when the phone is named, before its first run.

---

## 4. The sample (built in task 2, not in this task)

A throwaway lab script builds it. The real parser is task 9, and this script is deleted after the spike.

### 4.1 Recipe

1. **Day.** The most recent complete UTC day (96 intervals, 00:00–23:45) before the day the script first runs. If more than 4 of that day's 192 files are missing, the day before is used.
2. **Files.** That day's `gkg.csv.zip` files for both streams, as GDELT's master file lists name them: `masterfilelist.txt` for the English stream and, by the research note (`docs/3.0/research/data-gdelt.md`), `masterfilelist-translation.txt` for the translated stream. The plan's task names only `masterfilelist.txt`; see §10. Each file is checked against the size and MD5 the list gives. A listed file that still returns 404 after retries is left out and named in §4.4 (listed files can 404 for minutes *(research)*).
3. **Rows.** One point per GKG record that has at least one `Geo_Type` 3 or 4 entry in `V2Locations`: the earliest such entry by character offset, which is the plan's primary-location rule. Records with none are dropped. Selection is on `Geo_Type`, never on FeatureID.
4. **Columns.** Latitude and longitude (float32), language (the `srclc` code from `TranslationInfo`; `eng` for the English stream), and time (the record's 15-minute stamp).
5. **Two days if needed.** If the day gives fewer than 300,000 points, the day before it is added. If two days still fall short, a third is added and recorded in §11, because the plan's recipe stops at two.
6. **Format.** One Arrow IPC file, read in the page with flechette, so the spike uses the real decode path (design note Q26).

### 4.2 Cutting to 300k and 100k

Rows are put in a fixed order (stream, stamp, row order in the file), shuffled with seed `20261114`, and the first 300,000 kept. **The 100k set is the first 100,000 rows of the same file**, so the phone's points are a subset of the desktop's.

### 4.3 What the sample is not

It has no titles, URLs or outlet names. Duplicates are not collapsed, no centroid blocklist is applied, and nothing is sanitized: it is real coordinates at real density and nothing else. **It is not committed.** Task 2 adds the ignore rule for `lab/p1-render/data/` before the script first runs.

### 4.4 Sample record (blank until task 2 builds it)

| Field | Value |
|---|---|
| UTC day or days covered | *to fill* |
| Files listed / downloaded / left out | *to fill* |
| Points before down-sampling, by stream | *to fill* |
| Rows in the sample | 300,000 (*confirm*) |
| Arrow file size, bytes | *to fill* |
| SHA-256 of the sample | *to fill* |
| SHA-256 of the pick list (§5.3) | *to fill* |
| Built on (date), by (script and commit) | *to fill* |

Source files, one per line (URL, bytes and MD5 as the master list gives them):

```
to fill
```

---

## 5. Method

Every number in this section that is not in §2 is a method choice made here (**Proposed**), fixed now so it cannot be tuned after a result is seen. None of them is a plan threshold.

### 5.1 The page and the scene

- A standalone page in `lab/p1-render/` with its own pinned `package.json`: MapLibre 6.18 at an exact patch version, deck.gl 9.4.1, flechette. No monorepo and no CI.
- The basemap is OpenFreeMap's public style and tiles at every zoom, because the project's own basemap file does not exist until task 18. `antialias` is on.
- **Discs (Proposed):** one deck.gl scatterplot layer fed binary attributes, radius 3 CSS px, colour per point from its language, pickable, with a horizon test in its vertex shader. Fill cost grows with disc area, so this size is fixed here; see §10.
- **Arcs:** 200 great-circle arcs between pairs of sample points drawn with seed `20261114`.
- **Labels:** 500 synthetic labels (`L000`–`L499`) at sample coordinates, as a MapLibre symbol layer. No real headline or place name is used.
- The camera has pitch 0 and bearing 0 throughout. The plan gives the product no pitch control.
- The page drives itself from URL parameters, computes its own results and shows them as JSON. The §11 rule asks for one script: `lab/p1-render/run.sh` opens each run and collects the JSON into `lab/p1-render/results/`. On the phone the same URLs are opened over USB debugging or by hand.
- **One build.** A GO needs C1–C5 met by one commit of the page. A criterion passed on one build and another on a different build do not add up.

### 5.2 Frame rate (C1, C2)

- **Scene:** basemap and discs only. A second run with arcs and labels added is reported and does not gate.
- **Orbit:** 30 seconds. The camera is a function of elapsed time `t` in seconds: centre longitude `−180° + 12°·t` (one full turn), centre latitude `20°·sin(2π·t/30)`, zoom fixed. The zoom puts the whole globe in view with its diameter close to 90% of the viewport's shorter side; it is found once per viewport before the first timed run, written into every result and not changed afterwards.
- **Timing:** the camera is set inside a `requestAnimationFrame` callback from `performance.now()`, so a slow frame does not lengthen the run. A frame interval is the gap between two successive callbacks. **fps p50 is 1000 ÷ the median frame interval in milliseconds**, over every interval in the 30 seconds. Also recorded, not gating: p5, p95 and p99 intervals, the frame count, and the count of intervals over 33.3 ms.
- **Limit of the method.** `requestAnimationFrame` cannot run faster than the display, so a result at the refresh rate means "at the limit", not "exactly that fast".
- **Warm-up:** one untimed lap straight after the page loads, then the timed lap.
- **Viewport (Proposed):** desktop, 1440 × 900 CSS px on the built-in display at its own pixel ratio, external displays disconnected. The built-in display stays at the settings read on 15 November 2026, which are 1512 × 982 (pixel ratio 2) at 120 Hz, and the Mac is on mains power (§11, amendment 2). Phone, Chrome's full window in portrait at the phone's own pixel ratio. **The gating run is at the device's own pixel ratio.** Runs at the battery tier's ratio of 1.5 are reported and cannot turn a miss into a pass.
- **Repeats:** five page loads per configuration, 60 seconds apart. **The criterion is met if the median of the five p50 values meets the threshold.** All five are published.

### 5.3 Picks (C3)

- **List:** 1,000 picks drawn with seed `20261114`. Pick `i` (0–999) has zoom `10 + 2·i/999`, so the list covers the morph evenly from 10.0 to 12.0.
- **Target:** a point from the 100k set. The camera is placed so the target sits at a scripted position inside the central 80% of the viewport, not always at the centre.
- **Known answer:** a target is used only if no point with different coordinates lies within 12 CSS px of it at that camera, checked against all 300,000 points. A candidate that fails is skipped and the next is drawn; the number skipped is reported. The same list therefore serves both devices.
- **Probe:** after the map is idle, one single-object pick with radius 0 at the pixel where MapLibre's own projection puts the target. This tests deck.gl against MapLibre: a pick is right only if the two agree to within the disc's 3 px radius.
- **Correct** means the pick returns the target or a point with exactly the target's coordinates.
- **All 1,000 are on-target picks.** Empty-space probes (expected answer: nothing) are run and reported separately, so they cannot dilute the 99%.
- **Repeats:** the list is run three times. **Every run must reach 990 correct.** Misses are published with their zoom and screen position.

### 5.4 Far side (C4)

- **Stops:** 24 camera positions: centre longitudes −135°, −45°, 45°, 135° × centre latitudes −50°, 0°, 50°, each at the orbit zoom and at zoom 4.
- **Oracle, computed by the harness and not by the renderer:** with the camera at distance `d` globe radii from the globe's centre, a surface point at angle `φ` from the map centre is beyond the horizon when `cos φ < 1/d`, which is the plan's horizon test. Three sets per stop:
  - *near:* at least 15° inside the horizon;
  - *limb-far:* 5° to 15° beyond the horizon;
  - *far cap:* 135° or more from the map centre.
- **Marker colour:** the objects under test are drawn opaque in `#FF00FF`; a pixel counts as a marker pixel when red > 200, green < 60 and blue > 200. The framebuffer is read back after the frame.

| Kind | Sets that must be hidden | A violation is |
|---|---|---|
| Discs | every sample point in *limb-far* and *far cap* | any marker pixel; any of those points returned by a pick over the whole viewport; any of them returned by a single-pixel pick at the place it would appear if the globe were transparent (50 seeded probes per stop) |
| Arcs | arcs with both ends in the *far cap*, no longer than 30° and rising no more than 0.1 globe radii | any marker pixel; any of those arcs returned by a pick over the whole viewport |
| Labels | labels anchored in *limb-far* and *far cap* | any marker pixel; any of those labels returned by `queryRenderedFeatures` over the whole viewport |

- **Controls, so that a pass is not an empty picture:**
  - With the hiding mechanism switched off, the hidden sets must show (marker pixels > 0). If no switch can make them show, the note says so and the near set is the only control.
  - With it on, the *near* set must keep at least 90% of the marker pixels it has with it off, and single-pixel picks at 50 near discs must return at least 45 of them. A fix that hides far arcs by swallowing near ones fails here.
- **Threshold: zero violations** at every stop, in each of three runs.
- **Limit of these checks.** Far-cap arcs are hidden by the globe whatever the camera distance (geometry, checked for this file by hand and by a numeric sweep of camera distances; not a measurement of the renderer). Arcs that cross the limb have no such clean answer, because a risen arc can honestly show above the horizon. They are photographed at every stop and judged by eye; that judgement is reported and does not gate.

### 5.5 Labels (C5)

"Work" means all three, in each of three runs:

1. **Present in all three projections.** Over the densest part of the sample, at zooms 3 (globe), 10.5, 11 and 11.5 (morph) and 13 (Mercator), with overlap allowed, at least 99% of the test labels anchored on the near side inside the central 80% of the viewport are returned by `queryRenderedFeatures`, and label pixels are present.
2. **Draw order holds.** With the disc layer inserted beneath the label layer, the labels keep at least 90% of the pixels they have with no discs. With the disc layer above, they have fewer.
3. **Hidden on the far side:** the label row of §5.4.

Reported, not gating: the same stops with MapLibre's default collision on.

### 5.6 `projectTile()` smoke test (stands in for Plan B)

A MapLibre custom layer whose GLSL calls `projectTile()` draws 1,000 sample points at a globe zoom, at zooms 10.5, 11 and 11.5, and at zoom 13. Reported: the largest distance in pixels between each drawn point and MapLibre's own projection of it. This is **not** a GO criterion and says nothing about Plan B's frame rate. It answers one thing: whether the fallback route is open if A fails.

### 5.7 State noted with every run

Device model, chip and RAM; OS version; Chrome version and channel; the WebGL renderer string (`WEBGL_debug_renderer_info`); display resolution, refresh rate and pixel ratio; viewport size in CSS px; power source, battery level, and whether a low-power or battery-saver mode is on; the device's thermal state as the OS reports it (battery temperature on the phone); the page's commit; MapLibre, deck.gl and flechette versions; the sample's SHA-256; date and time. A fresh browser profile, one tab, other apps closed, DevTools closed for gating runs.

**A run is void, and re-run, only for these reasons:** the tab was hidden or lost focus; the renderer string names a software renderer; a tile or the sample failed to load; a battery saver or low-power mode was on; for the stand-in, the throttle was not applied. A void run is logged with its reason and its numbers, and published.

### 5.8 What may change between builds, and what may not

The spike allows work, as the plan's prior expects. **May change,** and is recorded: shaders and layer extensions, the layer order, the arc layer and its height, the basemap style's layers, `antialias`. **May not change:** the point counts, the orbit, the pick list, the stops, the disc radius, the viewport, the desktop's display and its refresh rate, the gating pixel ratio, any threshold. Every timed run of every build is kept in `lab/p1-render/results/` and published, including the ones that miss.

---

## 6. Devices

| Device | Used for | State on 14 November 2026, unless a later date is given |
|---|---|---|
| The M3 Pro (the plan's desktop reference since revision 6) | C1; C3–C5 | **At hand**, read with `system_profiler` on 15 November 2026. MacBook Pro, model identifier `Mac15,6`. Apple M3 Pro: 11 CPU cores (5 performance, 6 efficiency) and 14 GPU cores. 18 GB. macOS 27.0.1. Built-in Liquid Retina XDR display, 3024 × 1964 pixels, set to 1512 × 982 at 120 Hz |
| The reference Android | C2; C3–C5 | **Not chosen** (design note Q2). The plan suggests a borrowed or owned mid-range phone, Galaxy A5x class. Nothing is bought |
| Stand-in for the phone | early warning only | Chrome's 6× CPU throttling on the desktop, with a 412 × 915 CSS px viewport at pixel ratio 2.625 (**Proposed**), 100k points, the §5.2 orbit |

Each device is recorded in `docs/perf/devices.md` (model, SoC, RAM, OS and browser versions) before its first run. That file is task 2's, and the desktop's full record goes there when task 2 creates it.

**The desktop reference is this M3 Pro.** The owner decided it on 15 November 2026, before any timed run, and the plan was amended to say so (revision 6, §17 question 22). Every threshold is unchanged. A pass on this machine meets C1, and every desktop number in the note, the ADR and the calibration row is reported as "M3 Pro". The plan first named a different machine. §11, amendment 1 has that wording, the owner's two answers and what the change costs.

**The display.** Timed desktop runs use the built-in display at the settings in the table, with the external display disconnected (**Proposed**; §5.2 and §11, amendment 2). This Mac usually has an external 3440 × 1440 display at 85 Hz attached. A run on it would be a different test, with another refresh limit and another pixel count.

**The stand-in.** It runs first, as the plan says, and can show a problem early. It cannot grant C2: throttling slows the main thread only, and the GPU, the memory and the thermal limits of a phone are untouched. Design note Q3 asks whether tasks 13 and 14 may start once "the M3 Pro passes with Chrome's 6× throttle as well"; this file reads that as ≥ 30 fps p50 at 100k under the stand-in. Q3 is the owner's to answer and is still open.

**The GO decision waits for the phone.**

---

## 7. Timebox and cost

- **Size L**, the plan's size for the whole bake-off. It closes with Phase 1 at the latest. There is no calendar date; the project runs phase by phase.
- **Inconclusive.** §11 says a bake-off that expires inconclusive counts as "not adopted", and its note records the partial data. This file reads that as: no GO is recorded for A. Phase 1's own definition of done requires the GO criteria on both devices, so the phase cannot close on an inconclusive spike either way.
- **Cost: $0.** No machine is rented, so there is no burst scenario to name. The devices are owned or borrowed, GDELT's files and OpenFreeMap's tiles are free to read, and no new service or account is needed.

---

## 8. Outputs

- `docs/bakeoffs/p1-render.md`: the note, with every run, the misses and the screenshots.
- **ADR-0002:** the decision, GO or Plan B.
- The short post §11 asks for: the ADR-length note, rendered on the blog once the site has one.
- **A row in the Lab's calibration table:** §3 against the measured results, criterion by criterion, and $0 expected against actual.
- **Upstream reproductions** for any renderer bug found, as minimal pages. Filing one is a public post, so each is filed only with the owner's OK.
- `docs/perf/devices.md`, with the devices used.

---

## 9. Not measured here

- The Lens readout time, and anything about the worker kernel (P2).
- Battery drain.
- Any browser other than Chrome on the two devices. Safari, Firefox and iOS are not covered.
- Plan B's own frame rate or picking. It is not built.
- A pitched or rotated camera.
- Country and ADM1 washes, and data arriving while the camera moves (tasks 11 and 13).
- Native-script labels and text shaping (P2). The test labels are Latin letters and digits.
- Load time, memory and Arrow decode time. Decode time is noted if it is cheap to note; it is not a criterion.
- Terrain, and the Press E transition (P3).
- How the picture looks. The visual target is `docs/design/p1/`.

---

## 10. Open points for the owner

None of these stops task 2 from starting on the page and the sample. Point 1 is decided. Points 2, 9 and 10 should be settled before any timed run.

| # | Point | What this file does until told otherwise |
|---|---|---|
| 1 | **The desktop reference.** *Decided by the owner on 15 November 2026:* this M3 Pro, with the plan's thresholds unchanged (§11, amendment 1) | Measures C1 and the desktop half of C3–C5 on the M3 Pro, and reports every desktop number as "M3 Pro" |
| 2 | **Which pixel ratio gates the frame rate.** The plan does not say | Gates at the device's own ratio; reports 1.5 beside it (§5.2) |
| 3 | The reference Android (Q2) | C2 and the GO wait |
| 4 | Whether tasks 13 and 14 may start on the desktop result (Q3) | Records the stand-in result; decides nothing |
| 5 | **Disc size.** 3 CSS px radius, opaque edge, no glow. If the product's discs will be larger or additive, say so before the first run | Uses 3 px |
| 6 | C3–C5 on both devices, not one | Requires both (§2) |
| 7 | The plan's task names `masterfilelist.txt` only; the research note puts the translated stream's history in `masterfilelist-translation.txt` | Reads both lists (§4.1) |
| 8 | "Inconclusive" read as no GO (§7) | As written |
| 9 | **The display for the desktop run** (§11, amendment 2). The built-in display at 1512 × 982 and 120 Hz, with the external display disconnected and the Mac on mains power. Say so if the timed run should be at 60 Hz, or on the external display | Uses the built-in display as set (§5.2) |
| 10 | **Whether the 1440 × 900 CSS px view fits.** The built-in display is 1512 × 982, and a browser window's own bars take some of that height. Not checked | Task 2 checks it before the first timed run. If the view does not fit in a window, the run uses full screen, and that is recorded in §11 |

---

## 11. Amendments

Dated entries only, each with its reason.

### Amendment 1, 15 November 2026: the desktop reference is the M3 Pro

**Made before any timed run.** When this entry was written no sample had been built, no spike page existed and no frame had been timed, on this machine or on any other.

**Reason.** There is no M1 to measure on. This file was first committed (`61cbc48`) with the plan's desktop reference, an M1, and it recorded as open that the Mac at hand is an M3 Pro. The owner then answered two questions on 15 November 2026. The answers are quoted as the Phase 1 design session, which asked them, passed them on:

- Asked whether there is an M1 the spike can run on: "i have mac m3 pro only this mac".
- Asked "Name the M3 Pro as the desktop reference, with the plan's thresholds unchanged?": "Yes, M3 Pro".

**What changed.** The machine that C1 and the desktop half of C3–C5 run on. It is this M3 Pro (§6), in place of an M1.

- The plan changed with it. `docs/3.0/master-plan.md` is now revision 6: the machine is renamed at each of its 16 mentions, and the decision is §17 question 22. `docs/design/p1.md` is changed at its 10 mentions.
- In this file: the quoted row, C1's device and the sentence under the table in §2; the C1 prior in §3.2; §6; §10 point 1.

**What did not change.**

- Every threshold.
- The reference Android and C2.
- The 6× CPU throttling stand-in, and what it can and cannot grant.
- The GO rule: every criterion met by one build, otherwise Plan B, and the GO decision waits for the phone.
- The sample, the orbit, the pick list, the far-side stops and the repeats.

**What it costs.** An M3 Pro is the faster machine. A pass on C1 is therefore weaker evidence for older laptops than the plan intended, and it says nothing about an M1. What the spike can say about low-end hardware now rests on C2, the reference Android. No number was added to make up the difference: there is no handicap factor and no raised point count.

**The wording replaced.**

- The plan's row as first quoted in §2, from revision 5:

  > **GO** if: ≥50 fps p50 at 300k points in a 30-s scripted orbit on M1; ≥30 fps p50 at 100k on the reference Android; ≥99% of 1,000 scripted picks correct across the z10–12 morph; no far-side see-through and no picking through the globe for discs, arcs and labels; symbol labels work. Otherwise Plan B.

- C1's device in §2 was "the M1", and the sentence under the table quoted the plan's "M1 and the reference Android".
- The C1 prior in §3.2, written on 14 November 2026 for an M1, was "**60 fps p50**, which is the display's limit on a 60 Hz panel. On a 120 Hz panel: 110 fps", with a 95% chance that the threshold is met. It is kept here so that the calibration row can show it. The prior now in §3.2 is for the M3 Pro and was written with this entry, before any timed run.
- §6 and §10 point 1 named the M1 as the desktop reference and treated the M3 Pro's numbers as "desktop at hand", unable to meet C1. That rule is withdrawn: a pass on the M3 Pro meets C1.

**The machine's record.** §6 gives its identity as read on 15 November 2026. The full record (model, SoC, RAM, OS and browser versions) goes in `docs/perf/devices.md` when task 2 creates that file, before the first run.

### Amendment 2, 15 November 2026: the display for the desktop run

**Made before any timed run,** together with amendment 1. Unlike amendment 1 this is a method choice made in this file (**Proposed**), not the owner's decision. It is point 9 in §10.

**Reason.** The file as first committed put the desktop run on "the built-in display at its own pixel ratio, external displays disconnected" and did not fix the refresh rate. The frame rate is read from `requestAnimationFrame`, which cannot run faster than the display (§5.2), so the refresh rate sets the highest number a run can report. This Mac usually has an external 3440 × 1440 display at 85 Hz attached, and its built-in display runs at 120 Hz. With the desktop reference named, the display can be named too.

**What changed.** §5.2 fixes the built-in display at the settings read on 15 November 2026 (1512 × 982, which is pixel ratio 2, at 120 Hz) and puts the Mac on mains power. §5.8 adds the display and its refresh rate to what may not change between builds.

**What did not change.** The 1440 × 900 CSS px view, the rule that the gating run is at the device's own pixel ratio, and every threshold. Whether that view fits in a browser window on this display is not checked; it is point 10 in §10.
