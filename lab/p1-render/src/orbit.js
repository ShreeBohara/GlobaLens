// Frame rate over the scripted orbit (prereg §5.2).
import { P, hud, idle, quantile, voidWatch } from './core.js';

const LAP_MS = 30000;

// The camera is a function of elapsed time t in seconds:
// centre longitude −180° + 12°·t (one full turn), centre latitude 20°·sin(2π·t/30), zoom fixed.
export function cameraAt(tSeconds, zoom) {
  let lon = -180 + 12 * tSeconds;
  lon = ((lon + 180) % 360 + 360) % 360 - 180;
  const lat = 20 * Math.sin(2 * Math.PI * tSeconds / 30);
  return { center: [lon, lat], zoom };
}

function lap(map, zoom, record) {
  return new Promise((resolve) => {
    const stamps = [];
    let renders = 0;
    const onRender = () => { renders++; };
    map.on('render', onRender);
    let t0 = null;
    const tick = (now) => {
      if (t0 === null) t0 = now;
      const t = now - t0;
      if (record) stamps.push(now);
      if (t >= LAP_MS) {
        map.off('render', onRender);
        resolve({ stamps, renders });
        return;
      }
      // Set from the clock, so a slow frame does not lengthen the run.
      map.jumpTo(cameraAt(t / 1000, zoom));
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

export async function runOrbit(ctx) {
  const { map, overlay, scene, orbit } = ctx;
  overlay.setProps({ layers: scene.layers({ arcs: P.arcs }) });
  if (P.labels) scene.showLabels(true);
  map.jumpTo(cameraAt(0, orbit.zoom));
  await idle(map);

  const watch = voidWatch();
  hud('warm-up lap (untimed)');
  await lap(map, orbit.zoom, false);
  hud('timed lap');
  const errorsBefore = ctx.errors.length;
  const { stamps, renders } = await lap(map, orbit.zoom, true);
  watch.stop();

  const intervals = [];
  for (let i = 1; i < stamps.length; i++) intervals.push(stamps[i] - stamps[i - 1]);
  const sorted = [...intervals].sort((a, b) => a - b);
  const p50 = quantile(sorted, 0.5);
  return {
    scene: { discs: ctx.n, arcs: P.arcs ? scene.arcs.length : 0, labels: P.labels ? scene.labelFeatures.length : 0 },
    gating: !P.arcs && !P.labels,
    lapMs: LAP_MS,
    frames: stamps.length,
    mapRenders: renders,
    fpsP50: p50 ? 1000 / p50 : null,
    intervalMs: {
      p5: quantile(sorted, 0.05), p50, p95: quantile(sorted, 0.95), p99: quantile(sorted, 0.99),
      min: sorted[0], max: sorted[sorted.length - 1]
    },
    intervalsOver33ms: intervals.filter((x) => x > 33.3).length,
    voidEvents: watch.events,
    mapErrorsDuringRun: ctx.errors.slice(errorsBefore),
    intervals: intervals.map((x) => Math.round(x * 100) / 100)
  };
}
