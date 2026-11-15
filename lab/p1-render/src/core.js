// Shared pieces of the render spike page: parameters, the sample, the map and overlay,
// small maths, and reporting. See lab/p1-render/prereg.md §5.
import { Map as MapLibreMap, getVersion as maplibreVersion } from 'maplibre-gl';
import { VERSION as DECK_VERSION, LayerExtension } from '@deck.gl/core';
import { ArcLayer, ScatterplotLayer } from '@deck.gl/layers';
import { MapLibreOverlay } from '@deck.gl/maplibre';
import { tableFromIPC } from '@uwdata/flechette';

export { ArcLayer, ScatterplotLayer };
export const SEED = 20261114;
export const DISC_RADIUS_PX = 3;
export const MARKER = [255, 0, 255, 255]; // #FF00FF, prereg §5.4
export const DEG = Math.PI / 180;
export const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';
export const LABEL_LAYER = 'spike-labels';

export const params = new URLSearchParams(location.search);
export const P = {
  mode: params.get('mode') || 'view',
  n: Number(params.get('n') || 300000),
  w: params.get('w') ? Number(params.get('w')) : null,
  h: params.get('h') ? Number(params.get('h')) : null,
  dpr: params.get('dpr') ? Number(params.get('dpr')) : null,   // null = the device's own pixel ratio
  hide: params.get('hide') !== 'off',                           // the far-side hiding mechanism
  billboard: params.get('billboard') === '1',
  arcs: params.get('arcs') === '1',
  labels: params.get('labels') === '1',
  arcHeight: Number(params.get('arcHeight') || 0.3),
  discDepth: params.get('discDepth') === '1',                   // depth-test discs against the basemap
  arcDepth: params.get('arcDepth') === '1',                     // depth-test arcs against the basemap
  run: params.get('run') || '',
  label: params.get('label') || '',
  standin: params.get('standin') === '1',
  post: params.get('post') !== '0'
};

export const hud = (text) => { document.getElementById('hud').textContent = text; };
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const nextFrame = () => new Promise((r) => requestAnimationFrame(r));

// mulberry32: the one seeded generator used for every scripted list.
export function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function quantile(sorted, q) {
  if (!sorted.length) return null;
  const i = (sorted.length - 1) * q, lo = Math.floor(i), hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}

// Angle in radians between two points given in degrees.
export function angleBetween(lon1, lat1, lon2, lat2) {
  const a = lat1 * DEG, b = lat2 * DEG, dl = (lon2 - lon1) * DEG;
  const c = Math.sin(a) * Math.sin(b) + Math.cos(a) * Math.cos(b) * Math.cos(dl);
  return Math.acos(Math.max(-1, Math.min(1, c)));
}

// ---------- sample ----------

export async function loadSample() {
  const res = await fetch('/data/sample-300k.arrow');
  if (!res.ok) throw new Error(`sample: HTTP ${res.status}`);
  const buf = await res.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buf);
  const sha256 = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  const t0 = performance.now();
  const table = tableFromIPC(new Uint8Array(buf));
  const lat = table.getChild('lat').toArray();
  const lon = table.getChild('lon').toArray();
  const langs = table.getChild('lang').toArray();
  const decodeMs = performance.now() - t0;
  const total = table.numRows;
  const langIndex = new Map();
  const lang = new Uint16Array(total);
  for (let i = 0; i < total; i++) {
    let k = langIndex.get(langs[i]);
    if (k === undefined) { k = langIndex.size; langIndex.set(langs[i], k); }
    lang[i] = k;
  }
  return { lat, lon, lang, total, sha256, bytes: buf.byteLength, decodeMs, languages: langIndex.size };
}

// A fixed palette; a point's colour comes from its language.
const PALETTE = [
  [78, 168, 222], [240, 138, 93], [106, 190, 131], [205, 121, 196], [229, 196, 90], [120, 132, 230],
  [222, 99, 110], [84, 196, 196], [171, 148, 110], [150, 205, 80], [235, 150, 190], [140, 160, 175]
];

export function discAttributes(sample, n) {
  const positions = new Float32Array(n * 2);
  const colors = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    positions[2 * i] = sample.lon[i];
    positions[2 * i + 1] = sample.lat[i];
    const c = PALETTE[sample.lang[i] % PALETTE.length];
    colors[4 * i] = c[0]; colors[4 * i + 1] = c[1]; colors[4 * i + 2] = c[2]; colors[4 * i + 3] = 255;
  }
  return { positions, colors };
}

// ---------- the horizon test (plan §5 Geometry) ----------
// In deck.gl's globe view, common space is a sphere of radius GLOBE_RADIUS centred on the origin.
// A surface point p is beyond the horizon when dot(p̂, ĉam) < 1/|cam| in globe radii,
// which is dot(p, cam) < R². The vertex is then moved outside clip space, in drawing and in picking.
export class HorizonTest extends LayerExtension {
  static extensionName = 'HorizonTest';
  getShaders() {
    return {
      inject: {
        // The test is on the disc's centre, so all four corners of a disc agree.
        'vs:DECKGL_FILTER_GL_POSITION': `
          if (project.projectionMode == PROJECTION_MODE_GLOBE) {
            vec3 htCentre = project_globe_(vec3(geometry.worldPosition.xy, 0.0));
            if (dot(htCentre, project.cameraPosition) < GLOBE_RADIUS * GLOBE_RADIUS) {
              position = vec4(2.0, 2.0, 2.0, 1.0);
            }
          }
        `
      }
    };
  }
}

// The same test for geometry that rises above the surface (arcs). A point P outside the sphere is
// hidden by it when it lies beyond the horizon plane, dot(P, cam) < R², and inside the cone of
// directions that hit the globe. For a surface point this reduces to the test above.
// The flag is interpolated along the arc and the fragment is discarded, so a hidden vertex does not
// drag a visible segment across the screen. It runs in the picking pass as well.
export class HorizonCone extends LayerExtension {
  static extensionName = 'HorizonCone';
  getShaders() {
    return {
      inject: {
        'vs:#decl': 'out float horizonHidden;',
        'vs:DECKGL_FILTER_GL_POSITION': `
          horizonHidden = 0.0;
          if (project.projectionMode == PROJECTION_MODE_GLOBE) {
            vec3 hcP = geometry.position.xyz;
            vec3 hcC = project.cameraPosition;
            float hcR2 = GLOBE_RADIUS * GLOBE_RADIUS;
            vec3 hcV = hcP - hcC;
            float hcAlong = dot(hcV, -hcC);
            if (dot(hcP, hcC) < hcR2 && hcAlong > 0.0 && hcAlong * hcAlong > dot(hcV, hcV) * (dot(hcC, hcC) - hcR2)) {
              horizonHidden = 1.0;
            }
          }
        `,
        'fs:#decl': 'in float horizonHidden;',
        'fs:DECKGL_FILTER_COLOR': 'if (horizonHidden > 0.5) discard;'
      }
    };
  }
}

// ---------- layers ----------

// deck.gl's globe view culls back faces by default. For a disc lying on the surface that is itself a
// horizon test (the disc faces away exactly when it is beyond the horizon). For arcs it removes the
// near side too (found in development: an arc drew 5 pixels with culling and 3,164 without), so arcs
// are drawn with culling off and hidden by the horizon cone alone.
const NO_DEPTH = { depthCompare: 'always', depthWriteEnabled: false };
const NO_CULL = { cullMode: 'none' };

export function discLayer({ id = 'discs', positions, colors, n, color = null, visible = true, pickable = true, beforeId, hide = P.hide }) {
  const attributes = { getPosition: { value: positions, size: 2 } };
  if (!color) attributes.getFillColor = { value: colors, size: 4, normalized: true };
  return new ScatterplotLayer({
    id,
    data: { length: n, attributes },
    ...(color ? { getFillColor: color } : {}),
    radiusUnits: 'pixels',
    getRadius: DISC_RADIUS_PX,
    stroked: false,
    filled: true,
    billboard: P.billboard,
    pickable,
    visible,
    beforeId,
    extensions: hide ? [new HorizonTest()] : [],
    // Mechanism off (the control of prereg §5.4): no horizon test, no culling, no depth test.
    parameters: hide ? (P.discDepth ? {} : NO_DEPTH) : { ...NO_DEPTH, ...NO_CULL }
  });
}

export function arcLayer({ id = 'arcs', arcs, color = [255, 255, 255, 200], visible = true, pickable = true, beforeId, hide = P.hide }) {
  return new ArcLayer({
    id,
    data: arcs,
    getSourcePosition: (d) => d.from,
    getTargetPosition: (d) => d.to,
    getSourceColor: color,
    getTargetColor: color,
    getWidth: 2,
    widthUnits: 'pixels',
    greatCircle: true,
    getHeight: P.arcHeight,
    numSegments: 64,
    pickable,
    visible,
    beforeId,
    extensions: hide ? [new HorizonCone()] : [],
    parameters: hide && P.arcDepth ? NO_CULL : { ...NO_DEPTH, ...NO_CULL }
  });
}

// ---------- map ----------

export function containerSize() {
  const w = P.w || window.innerWidth, h = P.h || window.innerHeight;
  return { w, h, clipped: w > window.innerWidth || h > window.innerHeight };
}

export async function createMap({ center = [0, 0], zoom = 2 } = {}) {
  const { w, h } = containerSize();
  const el = document.getElementById('map');
  el.style.width = `${w}px`; el.style.height = `${h}px`;
  const errors = [];
  const map = new MapLibreMap({
    container: el,
    style: STYLE_URL,
    center, zoom, pitch: 0, bearing: 0,
    interactive: false,
    canvasContextAttributes: { antialias: true },
    ...(P.dpr ? { pixelRatio: P.dpr } : {})
  });
  map.on('error', (e) => errors.push(String(e?.error?.message || e?.error || e)));
  await new Promise((resolve) => map.once('style.load', resolve));
  map.setProjection({ type: 'globe' });
  const overlay = new MapLibreOverlay({ interleaved: true, layers: [] });
  map.addControl(overlay);
  await idle(map);
  return { map, overlay, errors, w, h };
}

export function idle(map, timeoutMs = 20000) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (ok) => { if (!done) { done = true; resolve(ok); } };
    map.once('idle', () => finish(true));
    map.triggerRepaint();
    setTimeout(() => finish(false), timeoutMs);
  });
}

// Wait for one rendered frame, then call fn while the frame is still in the drawing buffer.
export function afterRender(map, fn) {
  return new Promise((resolve) => {
    map.once('render', () => resolve(fn ? fn() : undefined));
    map.triggerRepaint();
  });
}

// Let deck.gl take new layers and the map come to rest, then run fn on a freshly drawn frame.
export async function settle(map, fn) {
  await nextFrame(); await nextFrame();
  const ok = await idle(map);
  const value = await afterRender(map, fn);
  return { idle: ok, value };
}

// A half-size JPEG of the frame just drawn, posted to the collector (not gating; for the note).
export function snapshot(map, name) {
  if (!P.post) return null;
  const src = map.getCanvas();
  const c = document.createElement('canvas');
  const scale = Math.min(1, 1440 / src.width);
  c.width = Math.round(src.width * scale); c.height = Math.round(src.height * scale);
  c.getContext('2d').drawImage(src, 0, 0, c.width, c.height);
  return new Promise((resolve) => c.toBlob(async (blob) => {
    try { await fetch(`/shot?name=${encodeURIComponent(name)}`, { method: 'POST', body: blob }); } catch { /* the note does without it */ }
    resolve(true);
  }, 'image/jpeg', 0.8));
}

// ---------- camera geometry, from MapLibre's own transform ----------

// Pixels per radian of arc at the map centre: the globe's radius in CSS px at this camera.
export function globeRadiusPx(map) {
  const c = map.getCenter();
  const d = 0.02; // degrees
  const a = map.project([c.lng, c.lat - d]);
  const b = map.project([c.lng, c.lat + d]);
  return Math.hypot(b.x - a.x, b.y - a.y) / (2 * d * DEG);
}

// Camera distance from the globe's centre, in globe radii: 1 + f/R,
// where f is the camera's distance from the centre point in CSS px.
export function cameraDistance(map, h) {
  const f = 0.5 * h / Math.tan(0.5 * map.getVerticalFieldOfView() * DEG);
  const R = globeRadiusPx(map);
  return { d: 1 + f / R, f, R };
}

// The limb's diameter on screen, in CSS px, for a globe of radius R seen from f above its surface.
export const limbDiameter = (f, R) => 2 * f * R / Math.sqrt(f * f + 2 * f * R);

// The orbit zoom (prereg §5.2): the whole globe in view, its diameter 90% of the viewport's shorter side.
// Found by bisection at latitude 0 from MapLibre's own projection; a pure function of the viewport.
export function findOrbitZoom(map, w, h) {
  const target = 0.9 * Math.min(w, h);
  const saved = { center: map.getCenter(), zoom: map.getZoom() };
  let lo = 0, hi = 8;
  for (let i = 0; i < 40; i++) {
    const z = 0.5 * (lo + hi);
    map.jumpTo({ center: [0, 0], zoom: z });
    const { f, R } = cameraDistance(map, h);
    if (limbDiameter(f, R) < target) lo = z; else hi = z;
  }
  const zoom = Math.round(0.5 * (lo + hi) * 1e4) / 1e4;
  map.jumpTo({ center: [0, 0], zoom });
  const { f, R, d } = cameraDistance(map, h);
  const out = { zoom, targetDiameterPx: target, limbDiameterPx: limbDiameter(f, R), globeRadiusPx: R, cameraDistanceRadii: d };
  map.jumpTo(saved);
  return out;
}

// ---------- pixels ----------

// Count marker pixels (#FF00FF: red > 200, green < 60, blue > 200) in the frame just drawn.
export function countMarkerPixels(map) {
  const gl = map.getCanvas().getContext('webgl2');
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
  const px = new Uint8Array(w * h * 4);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
  let n = 0;
  for (let i = 0; i < px.length; i += 4) if (px[i] > 200 && px[i + 1] < 60 && px[i + 2] > 200) n++;
  return n;
}

// ---------- state and reporting ----------

export async function measureRefresh(ms = 1000) {
  const stamps = [];
  const t0 = performance.now();
  while (performance.now() - t0 < ms) stamps.push(await nextFrame());
  const gaps = stamps.slice(1).map((t, i) => t - stamps[i]).sort((a, b) => a - b);
  const med = quantile(gaps, 0.5);
  return { medianIntervalMs: med, hz: med ? 1000 / med : null, frames: stamps.length };
}

// A fixed piece of main-thread work, timed. It shows whether CPU throttling was applied (the stand-in,
// prereg §5.7): under a 6× throttle it takes about six times as long as without one.
export function cpuProbe() {
  const t0 = performance.now();
  let x = 0;
  for (let i = 1; i <= 20_000_000; i++) x += Math.sqrt(i);
  return { ms: Math.round((performance.now() - t0) * 10) / 10, check: Math.round(x) };
}

export async function pageState(map, sample, extra = {}) {
  const gl = map.getCanvas().getContext('webgl2');
  const dbg = gl.getExtension('WEBGL_debug_renderer_info');
  let battery = null;
  try {
    const b = await navigator.getBattery?.();
    if (b) battery = { charging: b.charging, level: b.level };
  } catch { /* not available */ }
  const size = containerSize();
  return {
    pageCommit: __PAGE_COMMIT__,
    url: location.href,
    dateUtc: new Date().toISOString(),
    versions: { maplibre: maplibreVersion(), deck: DECK_VERSION, flechette: '2.8.0' },
    userAgent: navigator.userAgent,
    webglRenderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null,
    webglVendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : null,
    devicePixelRatio: window.devicePixelRatio,
    mapPixelRatio: map.getPixelRatio(),
    screen: { width: screen.width, height: screen.height },
    window: { innerWidth: window.innerWidth, innerHeight: window.innerHeight },
    viewport: { width: size.w, height: size.h, clipped: size.clipped },
    drawingBuffer: { width: gl.drawingBufferWidth, height: gl.drawingBufferHeight },
    antialias: gl.getContextAttributes().antialias,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory ?? null,
    battery,
    sample: { sha256: sample.sha256, bytes: sample.bytes, rows: sample.total, languages: sample.languages, decodeMs: sample.decodeMs },
    params: { ...P },
    cpuProbe: cpuProbe(),
    ...extra
  };
}

// Watches for the reasons a run is void that the page can see (prereg §5.7).
export function voidWatch() {
  const events = [];
  const onVis = () => { if (document.visibilityState !== 'visible') events.push({ t: performance.now(), what: 'tab hidden' }); };
  const onBlur = () => events.push({ t: performance.now(), what: 'window lost focus' });
  document.addEventListener('visibilitychange', onVis);
  window.addEventListener('blur', onBlur);
  if (document.visibilityState !== 'visible') events.push({ t: performance.now(), what: 'tab hidden at start' });
  if (!document.hasFocus()) events.push({ t: performance.now(), what: 'window not focused at start' });
  return { events, stop() { document.removeEventListener('visibilitychange', onVis); window.removeEventListener('blur', onBlur); } };
}

export async function report(name, result) {
  const el = document.getElementById('result');
  el.textContent = JSON.stringify(result, null, 1);
  el.style.display = 'block';
  document.title = `done: ${name}`;
  window.__spikeResult = result;
  if (!P.post) return;
  try {
    const res = await fetch(`/result?name=${encodeURIComponent(name)}`, { method: 'POST', body: JSON.stringify(result) });
    window.__spikePosted = res.ok;
  } catch (e) {
    window.__spikePosted = false;
  }
}
