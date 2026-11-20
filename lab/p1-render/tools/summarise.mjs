#!/usr/bin/env node
// Prints one line per result file, grouped by label, and for the orbit runs the median of each
// label's p50 values (prereg §5.2: the criterion is met if the median of the five p50 values meets
// the threshold). It reads results/ and changes nothing.
//
//   node tools/summarise.mjs [label-prefix]        e.g.  node tools/summarise.mjs desktop
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const RESULTS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'results');
const prefix = process.argv[2] || '';
const median = (a) => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const f1 = (x) => (typeof x === 'number' ? x.toFixed(1) : '–');

const groups = new Map();
for (const file of readdirSync(RESULTS).filter((f) => f.endsWith('.json')).sort()) {
  const r = JSON.parse(readFileSync(path.join(RESULTS, file), 'utf8'));
  const params = r.state?.params ?? r.params ?? {};
  const label = params.label || '(no label)';
  if (!label.startsWith(prefix)) continue;
  if (!groups.has(label)) groups.set(label, []);
  groups.get(label).push({ file, r, params });
}

for (const [label, runs] of groups) {
  console.log(`\n${label}`);
  const p50s = [];
  for (const { file, r, params } of runs) {
    const host = r.host || {};
    const voids = r.void ? 1 : (r.voidEvents || []).length;
    const tail = [
      `void events ${voids}`,
      `pinned ${host.pinned ?? '–'}`,
      `apps ${host.visibleApplications ?? '–'}`,
      `load ${host.loadAverage ? host.loadAverage[0] : '–'}`,
      `cpu probe ${r.state?.cpuProbe ? r.state.cpuProbe.ms + ' ms' : '–'}`,
      `commit ${r.state?.pageCommit ?? '–'}`
    ].join(' · ');
    let head;
    if (r.void) head = `VOID: ${r.reason}`;
    else if (r.kind === 'orbit') {
      if (!voids) p50s.push(r.fpsP50);
      head = `${f1(r.fpsP50)} fps p50 · interval p50 ${f1(r.intervalMs.p50)} / p95 ${f1(r.intervalMs.p95)} / p99 ${f1(r.intervalMs.p99)} ms · ${r.intervalsOver33ms} of ${r.frames - 1} over 33.3 ms · display ${f1(r.state?.refresh?.hz)} Hz · pixel ratio ${r.state?.mapPixelRatio}`;
    } else if (r.kind === 'picks') head = `${r.correct} of ${r.picksRun} correct · ${r.emptyProbes?.returnedSomething} of ${r.emptyProbes?.run} empty probes returned something · ${r.notIdleWithin15s} not idle within 15 s${r.partial ? ' · PARTIAL' : ''}`;
    else if (r.kind === 'farside') head = `${r.stopsRun} stops · ${r.violations} violations · ${r.controlFailures} control failures${r.partial ? ' · PARTIAL' : ''}`;
    else if (r.kind === 'labels') head = `${r.failures} failures over ${r.cameras?.length} cameras`;
    else if (r.kind === 'projtile') head = (r.cameras || []).map((c) => `z${c.zoom}: max ${f1(c.maxDistancePx)} px, ${c.notFoundWithin8px} not found`).join(' · ');
    else head = r.kind;
    console.log(`  run ${params.run ?? '–'}  ${head}\n         ${tail}\n         ${file}`);
  }
  if (p50s.length) console.log(`  median of ${p50s.length} p50 values (runs with no void event): ${f1(median(p50s))} fps`);
}
if (!groups.size) console.log('no results match');
