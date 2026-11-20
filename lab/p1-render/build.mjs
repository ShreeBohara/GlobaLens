#!/usr/bin/env node
// Bundles the spike page: src/main.js + deck.gl + flechette -> dist/app.js.
// MapLibre is not bundled: it is served as shipped (its main module and its worker module),
// and the page reaches it through an import map.
import { build } from 'esbuild';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
let commit = 'unknown';
try {
  commit = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: HERE }).toString().trim();
  const dirty = execFileSync('git', ['status', '--porcelain', '--', 'src', 'index.html', 'package.json', 'package-lock.json', 'build.mjs'], { cwd: HERE }).toString().trim();
  if (dirty) commit += '+uncommitted';
} catch { /* not a git checkout */ }

await build({
  entryPoints: [path.join(HERE, 'src', 'main.js')],
  outfile: path.join(HERE, 'dist', 'app.js'),
  bundle: true,
  format: 'esm',
  target: 'es2022',
  external: ['maplibre-gl'],
  sourcemap: true,
  define: { __PAGE_COMMIT__: JSON.stringify(commit) },
  logLevel: 'info'
});
console.log(`page commit: ${commit}`);
