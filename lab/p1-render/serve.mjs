#!/usr/bin/env node
// Static server and result collector for the render spike (lab/p1-render/prereg.md §5.1).
// No dependencies. Binds to 127.0.0.1 only; a phone reaches it through `adb reverse`.
//
//   node serve.mjs [--port 5173] [--host-state <file.json>]
//
// GET  /                      index.html
// GET  /dist/*  /vendor/*     the bundled page and MapLibre's own files
// GET  /data/*                the sample (not committed)
// GET  /picks.json            the pick list (§5.3)
// POST /result?name=<name>    writes results/<name>.json, with the host state attached
// POST /shot?name=<name>      writes results/shots/<name>.jpg
// POST /picks                 writes picks.json (only when it does not exist yet)

import { createServer } from 'node:http';
import { createReadStream, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const arg = (name, fallback) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback; };
const PORT = Number(arg('--port', '5173'));
const HOST_STATE = arg('--host-state', null);
const RESULTS = path.join(HERE, 'results');
mkdirSync(RESULTS, { recursive: true });

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.arrow': 'application/vnd.apache.arrow.file',
  '.map': 'application/json; charset=utf-8'
};
const ROOTS = [
  ['/dist/', path.join(HERE, 'dist')],
  ['/vendor/maplibre/', path.join(HERE, 'node_modules', 'maplibre-gl', 'dist')],
  ['/data/', path.join(HERE, 'data')]
];

function sendFile(res, file) {
  if (!existsSync(file) || !statSync(file).isFile()) { res.writeHead(404).end('not found'); return; }
  res.writeHead(200, {
    'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream',
    'Content-Length': statSync(file).size,
    'Cache-Control': 'no-store'
  });
  createReadStream(file).pipe(res);
}

function readBody(req, limit = 64 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = []; let n = 0;
    req.on('data', (c) => { n += c.length; if (n > limit) { reject(new Error('body too large')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const p = decodeURIComponent(url.pathname);
    if (req.method === 'GET') {
      if (p === '/' || p === '/index.html') return sendFile(res, path.join(HERE, 'index.html'));
      if (p === '/picks.json') return sendFile(res, path.join(HERE, 'picks.json'));
      for (const [prefix, root] of ROOTS) {
        if (!p.startsWith(prefix)) continue;
        const file = path.normalize(path.join(root, p.slice(prefix.length)));
        if (!file.startsWith(root + path.sep)) { res.writeHead(403).end('forbidden'); return; }
        return sendFile(res, file);
      }
      res.writeHead(404).end('not found'); return;
    }
    if (req.method === 'POST' && p === '/result') {
      const name = (url.searchParams.get('name') || '').replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 120);
      if (!name) { res.writeHead(400).end('name required'); return; }
      const body = JSON.parse(await readBody(req));
      if (HOST_STATE && existsSync(HOST_STATE)) body.host = JSON.parse(readFileSync(HOST_STATE, 'utf8'));
      body.receivedUtc = new Date().toISOString();
      let file = path.join(RESULTS, `${name}.json`);
      for (let i = 2; existsSync(file); i++) file = path.join(RESULTS, `${name}.${i}.json`); // never overwrite a run
      writeFileSync(file, JSON.stringify(body, null, 1) + '\n');
      console.log(`result -> ${path.relative(HERE, file)}`);
      res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ ok: true, file: path.basename(file) }));
      return;
    }
    if (req.method === 'POST' && p === '/shot') {
      const name = (url.searchParams.get('name') || '').replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 120);
      if (!name) { res.writeHead(400).end('name required'); return; }
      const chunks = [];
      for await (const c of req) chunks.push(c);
      const dir = path.join(RESULTS, 'shots');
      mkdirSync(dir, { recursive: true });
      writeFileSync(path.join(dir, `${name}.jpg`), Buffer.concat(chunks));
      res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"ok":true}');
      return;
    }
    if (req.method === 'POST' && p === '/picks') {
      const file = path.join(HERE, 'picks.json');
      if (existsSync(file)) { res.writeHead(409).end('picks.json exists; the list is made once'); return; }
      writeFileSync(file, await readBody(req));
      console.log('picks.json written');
      res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"ok":true}');
      return;
    }
    res.writeHead(405).end('method not allowed');
  } catch (e) {
    console.error(e);
    res.writeHead(500).end(String(e.message || e));
  }
});

server.listen(PORT, '127.0.0.1', () => console.log(`render spike: http://127.0.0.1:${PORT}/`));
