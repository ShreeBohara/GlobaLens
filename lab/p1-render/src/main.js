// Render spike page (lab/p1-render/prereg.md). It drives itself from URL parameters,
// computes its own results and shows them as JSON.
//   ?mode=view      look at the scene (no result)
//   ?mode=orbit     frame rate over the scripted orbit (§5.2)
//   ?mode=makepicks build the pick list (§5.3), once
//   ?mode=picks     run the pick list (§5.3)
//   ?mode=farside   far-side checks (§5.4)
//   ?mode=labels    label checks (§5.5)
//   ?mode=projtile  projectTile() smoke test (§5.6)
import {
  P, hud, loadSample, discAttributes, discLayer, arcLayer, createMap, idle, findOrbitZoom,
  measureRefresh, pageState, report, mulberry32, SEED, LABEL_LAYER
} from './core.js';
import { runOrbit } from './orbit.js';
import * as core from './core.js';
window.__lib = core; // for looking at the scene by hand

async function main() {
  hud('measuring the display');
  const refresh = await measureRefresh(1000);
  // A hidden or covered window gets a few frames a second, and a timed run would crawl for minutes and
  // be void anyway (prereg §5.7). Say so at once instead. Found when a suite was started while the Mac was in use.
  if (P.mode !== 'view' && P.mode !== 'makepicks' && (document.visibilityState !== 'visible' || !(refresh.hz >= 20))) {
    const reason = `the window is hidden or covered (visibility: ${document.visibilityState}; ${refresh.hz ? refresh.hz.toFixed(1) : 0} frames a second while idle)`;
    hud(`void: ${reason}`);
    await report(resultName(`void-${P.mode}`), { kind: P.mode, void: true, reason, refresh, dateUtc: new Date().toISOString(), params: { ...P } });
    return;
  }
  hud('loading the sample');
  const sample = await loadSample();
  const n = Math.min(P.n, sample.total);
  const attrs = discAttributes(sample, n);
  hud('loading the map');
  const ctx = await createMap();
  const { map, overlay, w, h } = ctx;
  Object.assign(ctx, { sample, n, attrs, refresh });
  ctx.orbit = findOrbitZoom(map, w, h);
  ctx.scene = buildScene(ctx);
  window.__spike = ctx;

  if (P.mode === 'view') {
    const center = [Number(P_get('lon', 0)), Number(P_get('lat', 0))];
    map.jumpTo({ center, zoom: Number(P_get('zoom', ctx.orbit.zoom)) });
    overlay.setProps({ layers: ctx.scene.layers({ arcs: P.arcs }) });
    if (P.labels) ctx.scene.showLabels(true);
    await idle(map);
    hud(`view · ${n} discs · zoom ${map.getZoom().toFixed(2)} · orbit zoom ${ctx.orbit.zoom}`);
    return;
  }
  if (P.mode === 'orbit') {
    const result = await runOrbit(ctx);
    const state = await pageState(map, sample, { refresh, orbit: ctx.orbit });
    await report(resultName('orbit'), { kind: 'orbit', state, ...result });
    return;
  }
  const mod = await import('./checks.js');
  const result = await mod.run(P.mode, ctx);
  const state = await pageState(map, sample, { refresh, orbit: ctx.orbit });
  if (result) await report(resultName(P.mode), { kind: P.mode, state, ...result });
}

const P_get = (k, fallback) => new URLSearchParams(location.search).get(k) ?? fallback;

function resultName(kind) {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15);
  return [kind, P.label || null, `n${P.n}`, P.run ? `run${P.run}` : null, stamp].filter(Boolean).join('-');
}

// The scene of §5.1: the discs, 200 arcs, 500 labels.
function buildScene(ctx) {
  const { map, sample, n, attrs } = ctx;
  const rand = mulberry32(SEED);
  const arcs = [];
  for (let k = 0; k < 200; k++) {
    const a = Math.floor(rand() * sample.total), b = Math.floor(rand() * sample.total);
    arcs.push({ id: k, from: [sample.lon[a], sample.lat[a]], to: [sample.lon[b], sample.lat[b]] });
  }
  const labelRand = mulberry32(SEED + 1);
  const features = [];
  for (let k = 0; k < 500; k++) {
    const i = Math.floor(labelRand() * sample.total);
    features.push({
      type: 'Feature', id: k,
      properties: { name: `L${String(k).padStart(3, '0')}`, k },
      geometry: { type: 'Point', coordinates: [sample.lon[i], sample.lat[i]] }
    });
  }
  map.addSource('spike-labels', { type: 'geojson', data: { type: 'FeatureCollection', features } });
  map.addLayer({
    id: LABEL_LAYER, type: 'symbol', source: 'spike-labels',
    layout: {
      'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 13,
      'text-allow-overlap': true, 'text-ignore-placement': true, visibility: 'none'
    },
    paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.2 }
  });
  return {
    arcs, labelFeatures: features,
    layers({ arcs: withArcs = false, discsBeforeLabels = true } = {}) {
      const out = [discLayer({ positions: attrs.positions, colors: attrs.colors, n, beforeId: discsBeforeLabels ? LABEL_LAYER : undefined })];
      if (withArcs) out.push(arcLayer({ arcs, beforeId: discsBeforeLabels ? LABEL_LAYER : undefined }));
      return out;
    },
    showLabels(on) { map.setLayoutProperty(LABEL_LAYER, 'visibility', on ? 'visible' : 'none'); }
  };
}

main().catch((e) => {
  console.error(e);
  hud(`error: ${e.message || e}`);
  window.__spikeError = String(e.stack || e);
});
