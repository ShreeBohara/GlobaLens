// The correctness checks of lab/p1-render/prereg.md §5.3–§5.6.
import {
  P, params, hud, idle, settle, afterRender, snapshot, countMarkerPixels, discLayer, arcLayer, mulberry32,
  SEED, MARKER, DEG, LABEL_LAYER, angleBetween, cameraDistance, voidWatch, DISC_RADIUS_PX
} from './core.js';
import { MercatorCoordinate } from 'maplibre-gl';

const LIMIT = params.get('limit') ? Number(params.get('limit')) : null; // development only; marks the result partial

export async function run(mode, ctx) {
  if (mode === 'makepicks') return makePicks(ctx);
  if (mode === 'picks') return runPicks(ctx);
  if (mode === 'farside') return runFarSide(ctx);
  if (mode === 'labels') return runLabels(ctx);
  if (mode === 'projtile') return runProjTile(ctx);
  throw new Error(`unknown mode "${mode}"`);
}

// ---------- shared ----------

// The sample's distinct coordinates, in a grid, for "is another place within N px of this one".
function distinctGrid(sample, cellDeg) {
  const seen = new Map();
  const ulon = [], ulat = [];
  for (let i = 0; i < sample.total; i++) {
    const key = `${sample.lon[i]},${sample.lat[i]}`;
    if (!seen.has(key)) { seen.set(key, ulon.length); ulon.push(sample.lon[i]); ulat.push(sample.lat[i]); }
  }
  const cells = new Map();
  const cellOf = (lon, lat) => Math.floor((lon + 180) / cellDeg) * 100000 + Math.floor((lat + 90) / cellDeg);
  for (let u = 0; u < ulon.length; u++) {
    const k = cellOf(ulon[u], ulat[u]);
    let a = cells.get(k); if (!a) cells.set(k, a = []);
    a.push(u);
  }
  // Smallest screen distance from (lon, lat) to any other distinct coordinate in the 3×3 cells around it.
  function nearestOtherPx(map, lon, lat, px = null) {
    const p = px || map.project([lon, lat]);
    const cx = Math.floor((lon + 180) / cellDeg), cy = Math.floor((lat + 90) / cellDeg);
    let best = Infinity;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      const a = cells.get((cx + dx) * 100000 + (cy + dy));
      if (!a) continue;
      for (const u of a) {
        if (ulon[u] === lon && ulat[u] === lat) continue;
        const q = map.project([ulon[u], ulat[u]]);
        const dist = Math.hypot(q.x - p.x, q.y - p.y);
        if (dist < best) best = dist;
      }
    }
    return best;
  }
  return { ulon, ulat, distinct: ulon.length, nearestOtherPx, cellDeg };
}

// Put (lon, lat) at screen position (X, Y) at this zoom.
function placeTarget(map, lon, lat, zoom, X, Y, w, h) {
  map.jumpTo({ center: [lon, lat], zoom });
  for (let k = 0; k < 5; k++) {
    const p = map.project([lon, lat]);
    const ex = X - p.x, ey = Y - p.y;
    if (Math.hypot(ex, ey) < 0.005) break;
    const c = map.unproject([w / 2 - ex, h / 2 - ey]);
    map.jumpTo({ center: [c.lng, c.lat], zoom });
  }
  return map.project([lon, lat]);
}

const pickAt = async (overlay, x, y, layerIds) => (await Promise.resolve(overlay.pickObject({ x, y, radius: 0, layerIds }))) || null;
const pickAll = async (overlay, w, h, layerIds) => (await Promise.resolve(overlay.pickObjects({ x: 0, y: 0, width: w, height: h, layerIds, maxObjects: 50 }))) || [];

// ---------- §5.3 the pick list ----------

async function makePicks(ctx) {
  const { map, sample, w, h } = ctx;
  const grid = distinctGrid(sample, 0.05);
  const rand = mulberry32(SEED);
  const picks = [];
  const skipped = { neighbourWithin12px: 0, latitudeBeyond80: 0 };
  let tried = 0;
  while (picks.length < 1000) {
    const i = picks.length;
    const zoom = Math.round((10 + 2 * i / 999) * 1e6) / 1e6;
    const target = Math.floor(rand() * 100000);          // a point from the 100k set
    const fx = 0.1 + 0.8 * rand(), fy = 0.1 + 0.8 * rand(); // inside the central 80%
    const angle = 2 * Math.PI * rand();
    tried++;
    const lon = sample.lon[target], lat = sample.lat[target];
    if (Math.abs(lat) > 80) { skipped.latitudeBeyond80++; continue; }
    const p = placeTarget(map, lon, lat, zoom, fx * w, fy * h, w, h);
    const nearest = grid.nearestOtherPx(map, lon, lat, p);
    if (nearest <= 12) { skipped.neighbourWithin12px++; continue; }
    // An empty-space probe 30 px away, if nothing lies within 12 px of it.
    let empty = null;
    for (let k = 0; k < 8 && !empty; k++) {
      const a = angle + k * Math.PI / 4;
      const ex = p.x + 30 * Math.cos(a), ey = p.y + 30 * Math.sin(a);
      const ll = map.unproject([ex, ey]);
      if (grid.nearestOtherPx(map, ll.lng, ll.lat, { x: ex, y: ey }) > 12) empty = [Math.round(30 * Math.cos(a) * 100) / 100, Math.round(30 * Math.sin(a) * 100) / 100];
    }
    picks.push({
      i, zoom, target, fx: Math.round(fx * 1e6) / 1e6, fy: Math.round(fy * 1e6) / 1e6,
      lon, lat, nearestOtherPx: Number.isFinite(nearest) ? Math.round(nearest * 100) / 100 : null, empty
    });
    if (i % 100 === 0) hud(`making the pick list: ${i}/1000`);
  }
  const list = {
    seed: SEED,
    rule: 'prereg §5.3: zoom 10 + 2·i/999; target from the first 100,000 rows; no differently-located point within 12 CSS px',
    viewport: { width: w, height: h },
    sampleSha256: sample.sha256,
    candidatesTried: tried,
    skipped,
    distinctCoordinates: grid.distinct,
    picks
  };
  const body = JSON.stringify(list) + '\n';
  const dry = params.get('dry') === '1';
  const res = dry ? { ok: false, status: 'dry run' } : await fetch('/picks', { method: 'POST', body });
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body));
  const listSha256 = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  return { written: res.ok, status: res.status, listSha256, bytes: body.length, zoomRange: [picks[0].zoom, picks[picks.length - 1].zoom], candidatesTried: tried, skipped, picks: picks.length, withEmptyProbe: picks.filter((p) => p.empty).length };
}

async function runPicks(ctx) {
  const { map, overlay, sample, w, h, scene, n } = ctx;
  const res = await fetch('/picks.json');
  if (!res.ok) throw new Error('picks.json is missing; run mode=makepicks once');
  const text = await res.text();
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  const listSha256 = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  const list = JSON.parse(text);
  if (list.sampleSha256 !== sample.sha256) throw new Error('picks.json was made from a different sample');
  const grid = distinctGrid(sample, 0.05);
  overlay.setProps({ layers: scene.layers() });
  await idle(map);
  const watch = voidWatch();
  const picks = LIMIT ? list.picks.filter((_, k) => k % Math.ceil(list.picks.length / LIMIT) === 0) : list.picks;
  const rows = [];
  let correct = 0, emptyRun = 0, emptyHits = 0, notIdle = 0, precondFail = 0;
  const t0 = performance.now();
  for (const pk of picks) {
    if (pk.target >= n) throw new Error('target outside the loaded points');
    const p = placeTarget(map, pk.lon, pk.lat, pk.zoom, pk.fx * w, pk.fy * h, w, h);
    const ok = await idle(map, 15000);
    if (!ok) notIdle++;
    const nearest = grid.nearestOtherPx(map, pk.lon, pk.lat, p);
    const precond = nearest > 12;
    if (!precond) precondFail++;
    const info = await pickAt(overlay, p.x, p.y, ['discs']);
    const got = info ? info.index : null;
    const good = got !== null && (got === pk.target || (sample.lon[got] === pk.lon && sample.lat[got] === pk.lat));
    if (good) correct++;
    let emptyHit = null;
    if (pk.empty) {
      emptyRun++;
      const e = await pickAt(overlay, p.x + pk.empty[0], p.y + pk.empty[1], ['discs']);
      emptyHit = e ? e.index : null;
      if (e) emptyHits++;
    }
    rows.push({ i: pk.i, zoom: pk.zoom, x: Math.round(p.x * 100) / 100, y: Math.round(p.y * 100) / 100, correct: good, got, idle: ok, precond, emptyHit });
    if (rows.length % 25 === 0) hud(`picks: ${rows.length}/${picks.length} · correct ${correct}`);
  }
  watch.stop();
  return {
    partial: !!LIMIT,
    listSha256,
    picksRun: rows.length,
    correct,
    threshold: 'every run must reach 990 correct of 1,000',
    misses: rows.filter((r) => !r.correct),
    emptyProbes: { run: emptyRun, returnedSomething: emptyHits },
    notIdleWithin15s: notIdle,
    knownAnswerCheckFailedAtRunTime: precondFail,
    elapsedMs: Math.round(performance.now() - t0),
    voidEvents: watch.events,
    mapErrors: ctx.errors.slice(),
    rows
  };
}

// ---------- §5.4 far side ----------

// The harness's own picture of the globe (not the renderer's): the centre is (lon0, lat0), the globe's
// radius is R px and the camera is d radii from its centre. Returns where a point would be drawn if the
// globe were transparent, and the cosine of its angle from the map centre.
function oracle(lon0, lat0, R, d, w, h) {
  const s0 = Math.sin(lat0 * DEG), c0 = Math.cos(lat0 * DEG);
  return (lon, lat) => {
    const s = Math.sin(lat * DEG), c = Math.cos(lat * DEG), dl = (lon - lon0) * DEG;
    const xe = c * Math.sin(dl);
    const yn = c0 * s - s0 * c * Math.cos(dl);
    const z = s0 * s + c0 * c * Math.cos(dl);   // cos φ
    const k = R * (d - 1) / (d - z);
    return { x: w / 2 + k * xe, y: h / 2 - k * yn, cosPhi: z };
  };
}

function subset(sample, idx) {
  const positions = new Float32Array(idx.length * 2);
  for (let k = 0; k < idx.length; k++) { positions[2 * k] = sample.lon[idx[k]]; positions[2 * k + 1] = sample.lat[idx[k]]; }
  return positions;
}

function makeArcs(sample, idx, rand, want, maxDeg = 30, minDeg = 2) {
  const out = [];
  for (let tries = 0; tries < want * 400 && out.length < want && idx.length > 1; tries++) {
    const a = idx[Math.floor(rand() * idx.length)], b = idx[Math.floor(rand() * idx.length)];
    const theta = angleBetween(sample.lon[a], sample.lat[a], sample.lon[b], sample.lat[b]) / DEG;
    if (theta < minDeg || theta > maxDeg) continue;
    out.push({ id: out.length, from: [sample.lon[a], sample.lat[a]], to: [sample.lon[b], sample.lat[b]], thetaDeg: theta, riseRadii: 0.5 * theta * DEG * P.arcHeight });
  }
  return out;
}

async function runFarSide(ctx) {
  const { map, overlay, sample, n, w, h, scene, orbit } = ctx;
  const lowGrid = distinctGrid(sample, 2);
  const stops = [];
  for (const [zoomName, zoom] of [['orbit', orbit.zoom], ['z4', 4]])
    for (const lat of [-50, 0, 50]) for (const lon of [-135, -45, 45, 135]) stops.push({ zoomName, zoom, lon, lat });
  const todo = LIMIT ? stops.filter((_, k) => k % Math.ceil(stops.length / LIMIT) === 0) : stops;
  const labelCoords = scene.labelFeatures.map((f) => f.geometry.coordinates);
  const setLabels = (ids) => {
    map.setFilter(LABEL_LAYER, ['in', ['get', 'k'], ['literal', ids]]);
    map.setLayoutProperty(LABEL_LAYER, 'visibility', ids.length ? 'visible' : 'none');
  };
  map.setPaintProperty(LABEL_LAYER, 'text-color', '#FF00FF');
  map.setPaintProperty(LABEL_LAYER, 'text-halo-width', 0);
  const watch = voidWatch();
  const out = [];
  let violations = 0, controlFailures = 0;
  const count = () => countMarkerPixels(map);
  const show = async (layers) => { overlay.setProps({ layers }); return (await settle(map, count)).value; };

  for (const [si, stop] of todo.entries()) {
    hud(`far side: stop ${si + 1}/${todo.length} · ${stop.zoomName} ${stop.lon},${stop.lat}`);
    map.jumpTo({ center: [stop.lon, stop.lat], zoom: stop.zoom });
    setLabels([]);
    overlay.setProps({ layers: [] });
    await idle(map);
    const { d, R } = cameraDistance(map, h);
    const phiH = Math.acos(1 / d);
    const proj = oracle(stop.lon, stop.lat, R, d, w, h);
    const rand = mulberry32(SEED + 1000 + stops.indexOf(stop));

    // Sets, by the oracle.
    const near = [], limbFar = [], farCap = [];
    const cosNear = Math.cos(phiH - 15 * DEG), cosLimbLo = Math.cos(phiH + 5 * DEG), cosLimbHi = Math.cos(phiH + 15 * DEG), cosCap = Math.cos(135 * DEG);
    for (let i = 0; i < n; i++) {
      const c = Math.cos(angleBetween(stop.lon, stop.lat, sample.lon[i], sample.lat[i]));
      if (c >= cosNear) near.push(i);
      else if (c <= cosLimbLo && c >= cosLimbHi) limbFar.push(i);
      else if (c <= cosCap) farCap.push(i);
    }
    const hidden = limbFar.concat(farCap);

    // How well the oracle's picture agrees with MapLibre's own projection, on near points.
    let oracleMaxDiffPx = 0;
    for (let k = 0; k < Math.min(200, near.length); k++) {
      const i = near[Math.floor(rand() * near.length)];
      const a = proj(sample.lon[i], sample.lat[i]), b = map.project([sample.lon[i], sample.lat[i]]);
      oracleMaxDiffPx = Math.max(oracleMaxDiffPx, Math.hypot(a.x - b.x, a.y - b.y));
    }

    const r = {
      stop, cameraDistanceRadii: d, globeRadiusPx: R, horizonDeg: phiH / DEG, oracleMaxDiffPx,
      sets: { near: near.length, limbFar: limbFar.length, farCap: farCap.length },
      discs: {}, arcs: {}, labels: {}
    };
    r.baselineMarkerPixels = await show([]);

    // --- discs ---
    const hiddenPos = subset(sample, hidden), nearPos = subset(sample, near);
    const disc = (pos, m, hide) => [discLayer({ id: 't-discs', positions: pos, n: m, color: MARKER, hide })];
    r.discs.hiddenPixelsOn = hidden.length ? await show(disc(hiddenPos, hidden.length, true)) : 0;
    r.discs.hiddenPickedOverViewport = hidden.length ? (await pickAll(overlay, w, h, ['t-discs'])).length : 0;
    let probes = 0, probeHits = 0;
    for (let tries = 0; tries < 5000 && probes < 50 && hidden.length; tries++) {
      const i = hidden[Math.floor(rand() * hidden.length)];
      const q = proj(sample.lon[i], sample.lat[i]);
      if (q.x < 1 || q.y < 1 || q.x > w - 1 || q.y > h - 1) continue;
      probes++;
      if (await pickAt(overlay, q.x, q.y, ['t-discs'])) probeHits++;
    }
    r.discs.transparentProbes = probes; r.discs.transparentProbeHits = probeHits;
    r.discs.hiddenPixelsOff = hidden.length ? await show(disc(hiddenPos, hidden.length, false)) : 0;
    r.discs.nearPixelsOn = near.length ? await show(disc(nearPos, near.length, true)) : 0;
    // 50 near discs with no other place within 7 px, picked at their own pixel.
    let nearProbes = 0, nearReturned = 0;
    for (let tries = 0; tries < 20000 && nearProbes < 50 && near.length; tries++) {
      const i = near[Math.floor(rand() * near.length)];
      const p = map.project([sample.lon[i], sample.lat[i]]);
      if (p.x < 4 || p.y < 4 || p.x > w - 4 || p.y > h - 4) continue;
      if (lowGrid.nearestOtherPx(map, sample.lon[i], sample.lat[i], p) <= 2 * DISC_RADIUS_PX + 1) continue;
      nearProbes++;
      const info = await pickAt(overlay, p.x, p.y, ['t-discs']);
      if (info && sample.lon[near[info.index]] === sample.lon[i] && sample.lat[near[info.index]] === sample.lat[i]) nearReturned++;
    }
    r.discs.nearProbes = nearProbes; r.discs.nearReturned = nearReturned;
    r.discs.nearPixelsOff = near.length ? await show(disc(nearPos, near.length, false)) : 0;

    // --- arcs ---
    const farArcs = makeArcs(sample, farCap, rand, 50), nearArcs = makeArcs(sample, near, rand, 50);
    const arc = (arcs, hide) => [arcLayer({ id: 't-arcs', arcs, color: MARKER, hide })];
    r.arcs.farArcs = farArcs.length; r.arcs.nearArcs = nearArcs.length;
    r.arcs.maxRiseRadii = farArcs.reduce((m, a) => Math.max(m, a.riseRadii), 0);
    r.arcs.farPixelsOn = farArcs.length ? await show(arc(farArcs, true)) : 0;
    r.arcs.farPickedOverViewport = farArcs.length ? (await pickAll(overlay, w, h, ['t-arcs'])).length : 0;
    r.arcs.farPixelsOff = farArcs.length ? await show(arc(farArcs, false)) : 0;
    r.arcs.nearPixelsOn = nearArcs.length ? await show(arc(nearArcs, true)) : 0;
    r.arcs.nearPixelsOff = nearArcs.length ? await show(arc(nearArcs, false)) : 0;

    // --- labels ---
    const hiddenLabels = [], nearLabels = [];
    labelCoords.forEach(([lo, la], k) => {
      const c = Math.cos(angleBetween(stop.lon, stop.lat, lo, la));
      if (c >= cosNear) nearLabels.push(k);
      else if ((c <= cosLimbLo && c >= cosLimbHi) || c <= cosCap) hiddenLabels.push(k);
    });
    overlay.setProps({ layers: [] });
    setLabels(hiddenLabels);
    r.labels.hidden = hiddenLabels.length;
    r.labels.hiddenPixels = (await settle(map, count)).value;
    r.labels.hiddenQueried = map.queryRenderedFeatures({ layers: [LABEL_LAYER] }).length;
    setLabels(nearLabels);
    r.labels.near = nearLabels.length;
    r.labels.nearInView = nearLabels.filter((k) => { const q = map.project(labelCoords[k]); return q.x > 20 && q.y > 20 && q.x < w - 20 && q.y < h - 20; }).length;
    r.labels.nearPixels = (await settle(map, count)).value;
    r.labels.nearQueried = new Set(map.queryRenderedFeatures({ layers: [LABEL_LAYER] }).map((f) => f.properties.k)).size;
    setLabels([]);

    // --- the picture for the note: the scene's own arcs over the discs, to be judged by eye ---
    overlay.setProps({ layers: scene.layers({ arcs: true }) });
    await settle(map, () => snapshot(map, `farside-${P.label || 'run'}-${P.run || 0}-${stop.zoomName}-${stop.lon}_${stop.lat}`));

    // --- verdict for this stop ---
    const v = [];
    if (r.baselineMarkerPixels) v.push('baseline has marker pixels');
    if (r.discs.hiddenPixelsOn) v.push('disc pixels');
    if (r.discs.hiddenPickedOverViewport) v.push('disc picked over viewport');
    if (r.discs.transparentProbeHits) v.push('disc picked through the globe');
    if (r.arcs.farPixelsOn) v.push('arc pixels');
    if (r.arcs.farPickedOverViewport) v.push('arc picked over viewport');
    if (r.labels.hiddenPixels) v.push('label pixels');
    if (r.labels.hiddenQueried) v.push('label queried');
    const c = [];
    r.discs.hiddenInViewIfTransparent = hidden.reduce((m, i) => { const q = proj(sample.lon[i], sample.lat[i]); return m + (q.x > 0 && q.y > 0 && q.x < w && q.y < h ? 1 : 0); }, 0);
    if (r.discs.hiddenInViewIfTransparent && !r.discs.hiddenPixelsOff) c.push('discs: hidden set does not show with the mechanism off');
    if (r.discs.nearPixelsOff && r.discs.nearPixelsOn < 0.9 * r.discs.nearPixelsOff) c.push('discs: near set keeps under 90% of its pixels');
    if (nearProbes && nearReturned < 0.9 * nearProbes) c.push('discs: near picks under 45 of 50');
    if (farArcs.length && !r.arcs.farPixelsOff) c.push('arcs: far set does not show with the mechanism off');
    if (r.arcs.nearPixelsOff && r.arcs.nearPixelsOn < 0.9 * r.arcs.nearPixelsOff) c.push('arcs: near set keeps under 90% of its pixels');
    if (r.labels.nearInView && !r.labels.nearPixels) c.push('labels: near set has no pixels');
    r.violations = v; r.controlFailures = c;
    violations += v.length; controlFailures += c.length;
    out.push(r);
  }
  watch.stop();
  overlay.setProps({ layers: [] });
  return {
    partial: !!LIMIT,
    stopsRun: out.length,
    violations,
    controlFailures,
    threshold: 'zero violations at every stop, in each of three runs; controls must hold',
    arcHeight: P.arcHeight,
    labelControl: 'MapLibre offers no switch that shows far-side labels; the near set is the only control',
    voidEvents: watch.events,
    mapErrors: ctx.errors.slice(),
    stops: out
  };
}

// ---------- §5.5 labels ----------

// The densest part of the sample: the busiest 0.1° cell, and the most common coordinate inside it.
function densestPoint(sample, n) {
  const cells = new Map();
  for (let i = 0; i < n; i++) {
    const k = Math.floor((sample.lon[i] + 180) * 10) * 10000 + Math.floor((sample.lat[i] + 90) * 10);
    cells.set(k, (cells.get(k) || 0) + 1);
  }
  let bestK = null, best = 0;
  for (const [k, c] of cells) if (c > best) { best = c; bestK = k; }
  const coords = new Map();
  for (let i = 0; i < n; i++) {
    const k = Math.floor((sample.lon[i] + 180) * 10) * 10000 + Math.floor((sample.lat[i] + 90) * 10);
    if (k !== bestK) continue;
    const key = `${sample.lon[i]},${sample.lat[i]}`;
    coords.set(key, (coords.get(key) || 0) + 1);
  }
  let top = null, topC = 0;
  for (const [key, c] of coords) if (c > topC) { topC = c; top = key; }
  const [lon, lat] = top.split(',').map(Number);
  return { lon, lat, pointsInCell: best, pointsAtCoordinate: topC };
}

async function runLabels(ctx) {
  const { map, overlay, sample, n, w, h, scene } = ctx;
  const dense = densestPoint(sample, sample.total);
  const labelCoords = scene.labelFeatures.map((f) => f.geometry.coordinates);
  map.setPaintProperty(LABEL_LAYER, 'text-color', '#FF00FF');
  map.setPaintProperty(LABEL_LAYER, 'text-halo-width', 0);
  map.setFilter(LABEL_LAYER, null);
  const count = () => countMarkerPixels(map);
  const watch = voidWatch();
  const cams = [];
  let failures = 0;
  for (const zoom of [3, 10.5, 11, 11.5, 13]) {
    hud(`labels: zoom ${zoom}`);
    map.jumpTo({ center: [dense.lon, dense.lat], zoom });
    overlay.setProps({ layers: [] });
    scene.showLabels(true);
    map.setLayoutProperty(LABEL_LAYER, 'text-allow-overlap', true);
    map.setLayoutProperty(LABEL_LAYER, 'text-ignore-placement', true);
    const first = await settle(map, count);
    // The test labels: anchored on the near side, inside the central 80% of the viewport.
    // "Anchored on the near side" is applied at every zoom. At zooms 10–12 the map is still a globe, and a
    // point far beyond the horizon can project inside the viewport as if seen through it (found in development).
    const cosHorizon = 1 / cameraDistance(map, h).d;
    const expected = [];
    labelCoords.forEach(([lo, la], k) => {
      if (Math.cos(angleBetween(dense.lon, dense.lat, lo, la)) <= cosHorizon) return;
      const p = map.project([lo, la]);
      if (p.x >= 0.1 * w && p.x <= 0.9 * w && p.y >= 0.1 * h && p.y <= 0.9 * h) expected.push(k);
    });
    const got = new Set(map.queryRenderedFeatures({ layers: [LABEL_LAYER] }).map((f) => f.properties.k));
    const returned = expected.filter((k) => got.has(k)).length;
    const pixelsNoDiscs = first.value;
    // Draw order: discs beneath the labels, then above them.
    overlay.setProps({ layers: scene.layers({ discsBeforeLabels: true }) });
    const pixelsDiscsBeneath = (await settle(map, count)).value;
    await snapshot(map, `labels-${P.label || 'run'}-${P.run || 0}-z${zoom}-beneath`);
    overlay.setProps({ layers: scene.layers({ discsBeforeLabels: false }) });
    const pixelsDiscsAbove = (await settle(map, count)).value;
    // Reported, not gating: MapLibre's default collision on.
    overlay.setProps({ layers: [] });
    map.setLayoutProperty(LABEL_LAYER, 'text-allow-overlap', false);
    map.setLayoutProperty(LABEL_LAYER, 'text-ignore-placement', false);
    const coll = await settle(map, count);
    const collisionQueried = new Set(map.queryRenderedFeatures({ layers: [LABEL_LAYER] }).map((f) => f.properties.k)).size;

    const c = {
      zoom, projection: zoom < 10 ? 'globe' : zoom < 12 ? 'morph' : 'mercator',
      expectedLabels: expected.length, returned,
      returnedShare: expected.length ? returned / expected.length : null,
      pixelsNoDiscs, pixelsDiscsBeneath, pixelsDiscsAbove,
      keptWithDiscsBeneath: pixelsNoDiscs ? pixelsDiscsBeneath / pixelsNoDiscs : null,
      withDefaultCollision: { pixels: coll.value, queried: collisionQueried }
    };
    const f = [];
    if (!expected.length) f.push('no test label in the central 80% at this camera');
    else if (returned < 0.99 * expected.length) f.push('under 99% of the test labels returned');
    if (!pixelsNoDiscs) f.push('no label pixels');
    if (pixelsNoDiscs && pixelsDiscsBeneath < 0.9 * pixelsNoDiscs) f.push('labels keep under 90% of their pixels with discs beneath');
    if (pixelsNoDiscs && !(pixelsDiscsAbove < pixelsNoDiscs)) f.push('labels do not lose pixels with discs above');
    c.failures = f; failures += f.length;
    cams.push(c);
  }
  watch.stop();
  scene.showLabels(false);
  return {
    densest: dense,
    failures,
    threshold: 'all of §5.5 items 1 and 2 at every camera, in each of three runs; item 3 is the label row of the far-side check',
    voidEvents: watch.events,
    mapErrors: ctx.errors.slice(),
    cameras: cams
  };
}

// ---------- §5.6 projectTile() smoke test ----------

function projTileLayer(mercator, pointPx) {
  return {
    id: 'projtile', type: 'custom', renderingMode: '2d',
    programs: new Map(),
    onAdd(map, gl) {
      this.vao = gl.createVertexArray();
      this.buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
      gl.bufferData(gl.ARRAY_BUFFER, mercator, gl.STATIC_DRAW);
    },
    program(gl, shaderData) {
      let prog = this.programs.get(shaderData.variantName);
      if (prog) return prog;
      const vs = `#version 300 es
${shaderData.vertexShaderPrelude}
${shaderData.define}
in vec2 a_pos;
void main() {
  gl_Position = projectTile(a_pos);
  gl_PointSize = ${pointPx.toFixed(1)};
}`;
      const fs = `#version 300 es
precision highp float;
out vec4 fragColor;
void main() { fragColor = vec4(1.0, 0.0, 1.0, 1.0); }`;
      const compile = (type, src) => {
        const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(`projtile shader: ${gl.getShaderInfoLog(s)}`);
        return s;
      };
      prog = gl.createProgram();
      gl.attachShader(prog, compile(gl.VERTEX_SHADER, vs));
      gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, fs));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(`projtile link: ${gl.getProgramInfoLog(prog)}`);
      this.programs.set(shaderData.variantName, prog);
      this.variants = [...this.programs.keys()];
      return prog;
    },
    render(gl, args) {
      const prog = this.program(gl, args.shaderData);
      const pd = args.defaultProjectionData;
      gl.useProgram(prog);
      const u = (name) => gl.getUniformLocation(prog, name);
      gl.uniformMatrix4fv(u('u_projection_matrix'), false, pd.mainMatrix);
      gl.uniformMatrix4fv(u('u_projection_fallback_matrix'), false, pd.fallbackMatrix);
      gl.uniform4f(u('u_projection_tile_mercator_coords'), ...pd.tileMercatorCoords);
      gl.uniform4f(u('u_projection_clipping_plane'), ...pd.clippingPlane);
      gl.uniform1f(u('u_projection_transition'), pd.projectionTransition);
      gl.bindVertexArray(this.vao);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
      const loc = gl.getAttribLocation(prog, 'a_pos');
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      gl.disable(gl.DEPTH_TEST);
      gl.disable(gl.BLEND);
      gl.drawArrays(gl.POINTS, 0, mercator.length / 2);
      gl.bindVertexArray(null);
      this.lastTransition = pd.projectionTransition;
    }
  };
}

async function runProjTile(ctx) {
  const { map, overlay, sample, w, h, orbit } = ctx;
  overlay.setProps({ layers: [] });
  const dense = densestPoint(sample, sample.total);
  const grid = distinctGrid(sample, 0.05);
  // 1,000 distinct sample coordinates: 500 drawn across the whole sample, 500 nearest the densest point.
  const rand = mulberry32(SEED + 2);
  const chosen = new Set();
  while (chosen.size < 500) chosen.add(Math.floor(rand() * grid.distinct));
  const byDistance = [...Array(grid.distinct).keys()]
    .sort((a, b) => angleBetween(dense.lon, dense.lat, grid.ulon[a], grid.ulat[a]) - angleBetween(dense.lon, dense.lat, grid.ulon[b], grid.ulat[b]));
  for (const u of byDistance) { if (chosen.size >= 1000) break; chosen.add(u); }
  const pts = [...chosen].map((u) => [grid.ulon[u], grid.ulat[u]]);
  const mercator = new Float32Array(pts.length * 2);
  pts.forEach(([lo, la], k) => {
    const m = MercatorCoordinate.fromLngLat([lo, la]);
    mercator[2 * k] = m.x; mercator[2 * k + 1] = m.y;
  });
  const ratio = map.getPixelRatio();
  const layer = projTileLayer(mercator, 5 * ratio);
  map.addLayer(layer);
  const gl = map.getCanvas().getContext('webgl2');
  const cams = [];
  for (const [name, zoom] of [['globe', orbit.zoom], ['morph 10.5', 10.5], ['morph 11', 11], ['morph 11.5', 11.5], ['mercator 13', 13]]) {
    hud(`projectTile(): ${name}`);
    map.jumpTo({ center: [dense.lon, dense.lat], zoom });
    // Near side only, with a margin inside the horizon; see the note in runLabels.
    const dCam = cameraDistance(map, h).d;
    const cosHorizon = Math.min(1 / dCam + 0.05, 1 - 0.5 * (1 - 1 / dCam));
    const frame = (await settle(map, () => {
      const bw = gl.drawingBufferWidth, bh = gl.drawingBufferHeight;
      const px = new Uint8Array(bw * bh * 4);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.readPixels(0, 0, bw, bh, gl.RGBA, gl.UNSIGNED_BYTE, px);
      return { px, bw, bh };
    })).value;
    // Points in view, on the near side, with no other test point within 16 px.
    const proj = pts.map(([lo, la]) => {
      if (Math.cos(angleBetween(dense.lon, dense.lat, lo, la)) <= cosHorizon) return null;
      const p = map.project([lo, la]);
      return (p.x >= 10 && p.y >= 10 && p.x <= w - 10 && p.y <= h - 10) ? p : null;
    });
    const inView = proj.map((p, k) => p ? k : -1).filter((k) => k >= 0);
    let measured = 0, missing = 0, maxDist = 0, sum = 0, worst = null;
    for (const k of inView) {
      const p = proj[k];
      if (inView.some((j) => j !== k && Math.hypot(proj[j].x - p.x, proj[j].y - p.y) < 16)) continue;
      // Centroid of marker pixels within 8 CSS px of where MapLibre's own projection puts the point.
      const cx = p.x * ratio, cy = frame.bh - p.y * ratio, rad = Math.ceil(8 * ratio);
      let sx = 0, sy = 0, cnt = 0;
      for (let y = Math.max(0, Math.floor(cy - rad)); y <= Math.min(frame.bh - 1, Math.ceil(cy + rad)); y++) {
        for (let x = Math.max(0, Math.floor(cx - rad)); x <= Math.min(frame.bw - 1, Math.ceil(cx + rad)); x++) {
          const o = (y * frame.bw + x) * 4;
          if (frame.px[o] > 200 && frame.px[o + 1] < 60 && frame.px[o + 2] > 200) { sx += x + 0.5; sy += y + 0.5; cnt++; }
        }
      }
      if (!cnt) { missing++; continue; }
      const dist = Math.hypot(sx / cnt - cx, sy / cnt - cy) / ratio;
      measured++; sum += dist;
      if (dist > maxDist) { maxDist = dist; worst = { lon: pts[k][0], lat: pts[k][1], x: Math.round(p.x * 10) / 10, y: Math.round(p.y * 10) / 10, markerPixels: cnt, angleFromCentreDeg: Math.round(angleBetween(dense.lon, dense.lat, pts[k][0], pts[k][1]) / DEG * 100) / 100 }; }
    }
    cams.push({
      camera: name, zoom, projectionTransition: layer.lastTransition,
      pointsInView: inView.length, measured, notFoundWithin8px: missing,
      maxDistancePx: measured ? Math.round(maxDist * 1000) / 1000 : null,
      meanDistancePx: measured ? Math.round(sum / measured * 1000) / 1000 : null,
      worst
    });
  }
  map.removeLayer('projtile');
  return {
    note: 'not a GO criterion; says only whether a custom GLSL layer can follow MapLibre through globe, morph and Mercator',
    pointsDrawn: pts.length,
    shaderVariantsCompiled: layer.variants,
    densest: dense,
    mapErrors: ctx.errors.slice(),
    cameras: cams
  };
}
