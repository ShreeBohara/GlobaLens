#!/usr/bin/env node
// Throwaway lab script: builds the render spike's point sample.
// It follows lab/p1-render/prereg.md §4 and is deleted after the spike.
// The real GDELT parser is Phase 1 task 9; nothing here is reused.
//
// Usage: node sample/build-sample.mjs
// Output (all under data/, which is not committed):
//   data/raw/<file>.zip          the GDELT files as downloaded
//   data/sample-300k.arrow       the sample (Arrow IPC file)
//   data/sample-record.json      what prereg §4.4 asks for
//   data/sources.txt             one source file per line: URL, bytes, MD5
//
// The sample is pinned. sample/pinned.json holds the first run's UTC time, the days used and the
// sample's SHA-256, and ../sample-sources.txt lists every source file with its size and MD5 in the
// order they were read (both committed; prereg §4.4). With the pins present the script reads
// exactly those files instead of GDELT's master lists, and it fails if the result differs, so a
// fresh checkout rebuilds the sample the committed pick list was made on.
// SAMPLE_FROM_LISTS=1 ignores the pins and follows the recipe from the master lists.

import { createHash } from 'node:crypto';
import { execFileSync, spawn } from 'node:child_process';
import {
  createReadStream, createWriteStream, existsSync, mkdirSync, readFileSync,
  renameSync, statSync, unlinkSync, writeFileSync
} from 'node:fs';
import { createInterface } from 'node:readline';
import { pipeline } from 'node:stream/promises';
import { Readable } from 'node:stream';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { dictionary, tableFromArrays, tableToIPC, utf8 } from '@uwdata/flechette';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.resolve(HERE, '..', 'data');
const RAW = path.join(DATA, 'raw');
const BASE = 'https://data.gdeltproject.org/gdeltv2/';
const STREAMS = [
  { name: 'english', list: 'masterfilelist.txt', suffix: '.gkg.csv.zip' },
  { name: 'translation', list: 'masterfilelist-translation.txt', suffix: '.translation.gkg.csv.zip' }
];
const SEED = 20261114;        // prereg §4.2
const TARGET = 300_000;       // prereg §4.2
const MAX_MISSING = 4;        // prereg §4.1 step 1
const LIST_TAIL_BYTES = 6_000_000; // the lists are chronological; recent days are at the end
const UA = 'globalens-lab-sample/0.1';

mkdirSync(RAW, { recursive: true });
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- days ----------

const ymd = (d) => d.toISOString().slice(0, 10).replaceAll('-', '');
function dayBefore(day) {
  const d = new Date(Date.UTC(+day.slice(0, 4), +day.slice(4, 6) - 1, +day.slice(6, 8)));
  d.setUTCDate(d.getUTCDate() - 1);
  return ymd(d);
}
function stampsOf(day) {
  const out = [];
  for (let h = 0; h < 24; h++) for (const m of ['00', '15', '30', '45']) out.push(`${day}${String(h).padStart(2, '0')}${m}00`);
  return out;
}

// The pins (see the top of this file). They are used whenever sample/pinned.json is there, unless
// SAMPLE_FROM_LISTS=1; the source list it names must then be there too.
const PINNED = path.join(HERE, 'pinned.json');
const pins = !process.env.SAMPLE_FROM_LISTS && existsSync(PINNED) ? JSON.parse(readFileSync(PINNED, 'utf8')) : null;
const PINNED_SOURCES = pins ? path.resolve(HERE, '..', pins.sources) : null;
if (pins && !existsSync(PINNED_SOURCES)) throw new Error(`${PINNED_SOURCES} is missing; set SAMPLE_FROM_LISTS=1 to build from the master lists`);

// "The most recent complete UTC day before the day the script first runs."
// The first run's UTC date is kept, so a re-run rebuilds the same sample. The pinned date wins.
const firstRunPath = path.join(DATA, 'first-run.json');
let firstRun;
if (pins) firstRun = { firstRunUtc: pins.firstRunUtc };
else if (existsSync(firstRunPath)) firstRun = JSON.parse(readFileSync(firstRunPath, 'utf8'));
else {
  firstRun = { firstRunUtc: new Date().toISOString() };
  writeFileSync(firstRunPath, JSON.stringify(firstRun, null, 2) + '\n');
}
const firstRunDay = firstRun.firstRunUtc.slice(0, 10).replaceAll('-', '');

// ---------- master lists ----------

async function fetchListTail(listName) {
  const url = BASE + listName;
  const res = await fetch(url, { headers: { Range: `bytes=-${LIST_TAIL_BYTES}`, 'User-Agent': UA } });
  if (res.status !== 206 && res.status !== 200) throw new Error(`${listName}: HTTP ${res.status}`);
  const text = await res.text();
  const lines = text.split('\n');
  if (res.status === 206) lines.shift(); // the first line of a ranged read is cut
  const entries = new Map(); // file name -> { url, bytes, md5 }
  for (const line of lines) {
    const p = line.trim().split(/\s+/);
    if (p.length !== 3) continue;
    const name = p[2].slice(p[2].lastIndexOf('/') + 1);
    entries.set(name, { listedUrl: p[2], bytes: +p[0], md5: p[1] });
  }
  log(`${listName}: HTTP ${res.status}, ${text.length} bytes read, ${entries.size} entries`);
  return entries;
}

// The pinned source list in place of the master lists: one line per file, "URL bytes MD5".
function listsFromPinnedSources(file, expectedSha256) {
  const text = readFileSync(file, 'utf8');
  const sha = createHash('sha256').update(text).digest('hex');
  if (sha !== expectedSha256) throw new Error(`${file}: SHA-256 ${sha}, but pinned.json expects ${expectedSha256}`);
  const lists = STREAMS.map(() => new Map());
  for (const line of text.split('\n')) {
    const p = line.trim().split(/\s+/);
    if (p.length !== 3) continue;
    const name = p[0].slice(p[0].lastIndexOf('/') + 1);
    // The translated stream's suffix also ends in ".gkg.csv.zip", so it is tested first.
    const si = name.endsWith(STREAMS[1].suffix) ? 1 : name.endsWith(STREAMS[0].suffix) ? 0 : -1;
    if (si < 0) throw new Error(`${file}: not a GKG file: ${name}`);
    lists[si].set(name, { listedUrl: p[0], bytes: +p[1], md5: p[2] });
  }
  log(`${path.basename(file)}: ${lists[0].size} English and ${lists[1].size} translated files, pinned`);
  return lists;
}

// ---------- download ----------

const md5OfFile = (file) => new Promise((resolve, reject) => {
  const h = createHash('md5');
  createReadStream(file).on('data', (c) => h.update(c)).on('end', () => resolve(h.digest('hex'))).on('error', reject);
});

async function fetchOne(entry, name) {
  const dest = path.join(RAW, name);
  const ok = async () => existsSync(dest) && statSync(dest).size === entry.bytes && (await md5OfFile(dest)) === entry.md5;
  if (await ok()) return { name, status: 'ok', cached: true };
  const url = BASE + name;
  const waits = [0, 2000, 5000, 10000, 20000, 40000];
  let last = '';
  for (const w of waits) {
    if (w) await sleep(w);
    try {
      const res = await fetch(url, { headers: { 'User-Agent': UA } });
      if (!res.ok) { last = `HTTP ${res.status}`; continue; }
      const tmp = dest + '.part';
      await pipeline(Readable.fromWeb(res.body), createWriteStream(tmp));
      renameSync(tmp, dest);
      if (await ok()) return { name, status: 'ok', cached: false };
      last = `size or MD5 differs from the list (got ${statSync(dest).size} bytes)`;
      unlinkSync(dest);
    } catch (e) { last = String(e.message || e); }
  }
  return { name, status: 'left out', reason: last };
}

async function pool(items, n, fn) {
  const out = new Array(items.length);
  let next = 0;
  await Promise.all(Array.from({ length: n }, async () => {
    while (next < items.length) { const i = next++; out[i] = await fn(items[i], i); }
  }));
  return out;
}

// ---------- parse ----------

// GKG 2.1 is tab-separated with 27 columns. Used here, 0-based:
//   1 DATE (YYYYMMDDHHMMSS), 10 V2Locations, 25 TranslationInfo.
// A V2Locations entry is type#name#cc#adm1#adm2#lat#lon#featureID#offset; entries are ';'-separated.
function parseLine(line, streamName, counters) {
  const cut = new Array(26); // positions of the first 26 tabs
  let pos = -1;
  for (let i = 0; i < 26; i++) {
    pos = line.indexOf('\t', pos + 1);
    if (pos < 0) { counters.malformed++; return null; }
    cut[i] = pos;
  }
  counters.records++;
  const locs = line.slice(cut[9] + 1, cut[10]);
  if (!locs) return null;
  let best = null, bestOffset = Infinity;
  for (const entry of locs.split(';')) {
    const c = entry.charCodeAt(0);
    if (c !== 51 && c !== 52) continue; // '3' or '4': selection is on Geo_Type only
    const p = entry.split('#');
    if (p.length < 9 || (p[0] !== '3' && p[0] !== '4')) continue;
    const lat = Number(p[5]), lon = Number(p[6]), off = Number(p[8]);
    if (p[5] === '' || p[6] === '' || !Number.isFinite(lat) || !Number.isFinite(lon) ||
        Math.abs(lat) > 90 || Math.abs(lon) > 180) { counters.badCoords++; continue; }
    const o = Number.isFinite(off) ? off : Infinity;
    if (best === null || o < bestOffset) { best = [lat, lon]; bestOffset = o; }
  }
  if (!best) return null;
  let lang = 'eng';
  if (streamName === 'translation') {
    const info = line.slice(cut[24] + 1, cut[25]);
    const m = /srclc:([A-Za-z]+)/.exec(info);
    lang = m ? m[1] : 'und';
  }
  const d = line.slice(cut[0] + 1, cut[1]);
  const t = Date.UTC(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8), +d.slice(8, 10), +d.slice(10, 12), +d.slice(12, 14)) / 1000;
  if (!Number.isFinite(t)) { counters.malformed++; return null; }
  return { lat: best[0], lon: best[1], lang, t };
}

function parseFile(file, streamName, rows, counters) {
  return new Promise((resolve, reject) => {
    const child = spawn('unzip', ['-p', file], { stdio: ['ignore', 'pipe', 'inherit'] });
    child.stdout.setEncoding('latin1'); // tabs, '#', ';' and digits are ASCII; names are not used
    const rl = createInterface({ input: child.stdout, crlfDelay: Infinity });
    rl.on('line', (line) => {
      if (!line) return;
      const r = parseLine(line, streamName, counters);
      if (r) { rows.lat.push(r.lat); rows.lon.push(r.lon); rows.lang.push(r.lang); rows.t.push(r.t); }
    });
    child.on('error', reject);
    child.on('close', (code) => code === 0 ? resolve() : reject(new Error(`unzip ${path.basename(file)}: exit ${code}`)));
  });
}

// ---------- one day ----------

async function loadDay(day, lists, rows) {
  const record = { day, listed: 0, downloaded: 0, leftOut: [], notListed: [], points: {}, records: {}, sources: [] };
  const counters = { records: 0, malformed: 0, badCoords: 0 };
  const jobs = [];
  for (const [si, s] of STREAMS.entries()) {
    for (const stamp of stampsOf(day)) {
      const name = stamp + s.suffix;
      const entry = lists[si].get(name);
      if (!entry) { record.notListed.push(name); continue; }
      record.listed++;
      jobs.push({ s, name, entry });
    }
  }
  log(`${day}: ${record.listed} of 192 files listed; downloading`);
  let done = 0;
  const results = await pool(jobs, 4, async (j) => {
    const r = await fetchOne(j.entry, j.name);
    if (++done % 24 === 0) log(`${day}: ${done}/${jobs.length} files`);
    return r;
  });
  const missing = record.notListed.length + results.filter((r) => r.status !== 'ok').length;
  record.missing = missing;
  for (const r of results) if (r.status !== 'ok') record.leftOut.push({ name: r.name, reason: r.reason });
  if (missing > MAX_MISSING) return { record, tooManyMissing: true };

  // Fixed order: stream, stamp, row order in the file (prereg §4.2).
  for (const s of STREAMS) {
    const before = rows.lat.length, recBefore = counters.records;
    for (const [i, j] of jobs.entries()) {
      if (j.s !== s || results[i].status !== 'ok') continue;
      await parseFile(path.join(RAW, j.name), s.name, rows, counters);
      record.downloaded++;
      record.sources.push(`${j.entry.listedUrl} ${j.entry.bytes} ${j.entry.md5}`);
    }
    record.points[s.name] = rows.lat.length - before;
    record.records[s.name] = counters.records - recBefore;
    log(`${day} ${s.name}: ${record.records[s.name]} records, ${record.points[s.name]} points`);
  }
  record.malformedLines = counters.malformed;
  record.badCoordinateEntries = counters.badCoords;
  return { record, tooManyMissing: false };
}

// ---------- shuffle ----------

// mulberry32, then Fisher–Yates from the end. Both are fixed here so the sample can be rebuilt.
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- main ----------

const lists = pins ? listsFromPinnedSources(PINNED_SOURCES, pins.sourcesSha256) : [];
if (!pins) for (const s of STREAMS) lists.push(await fetchListTail(s.list));

const rows = { lat: [], lon: [], lang: [], t: [] };
const days = [];
const skippedDays = [];
let day = dayBefore(firstRunDay);
while (rows.lat.length < TARGET && days.length < 3) {
  const { record, tooManyMissing } = await loadDay(day, lists, rows);
  if (tooManyMissing) {
    log(`${day}: ${record.missing} of 192 files missing, more than ${MAX_MISSING}; using the day before`);
    skippedDays.push({ day, missing: record.missing, notListed: record.notListed, leftOut: record.leftOut });
    if (skippedDays.length > 5) throw new Error('six days in a row with too many missing files; stopping');
  } else {
    days.push(record);
    log(`${day}: total so far ${rows.lat.length} points`);
  }
  day = dayBefore(day);
}
const total = rows.lat.length;
if (total < TARGET) throw new Error(`only ${total} points after ${days.length} days; the recipe stops here`);

const order = new Uint32Array(total);
for (let i = 0; i < total; i++) order[i] = i;
const rand = mulberry32(SEED);
for (let i = total - 1; i > 0; i--) {
  const j = Math.floor(rand() * (i + 1));
  const tmp = order[i]; order[i] = order[j]; order[j] = tmp;
}
const lat = new Float32Array(TARGET), lon = new Float32Array(TARGET), t = new Uint32Array(TARGET), lang = new Array(TARGET);
for (let k = 0; k < TARGET; k++) {
  const i = order[k];
  lat[k] = rows.lat[i]; lon[k] = rows.lon[i]; t[k] = rows.t[i]; lang[k] = rows.lang[i];
}

const table = tableFromArrays({ lat, lon, lang, t }, { types: { lang: dictionary(utf8()) } });
const bytes = tableToIPC(table, { format: 'file' });
const out = path.join(DATA, 'sample-300k.arrow');
writeFileSync(out, bytes);
const sha256 = createHash('sha256').update(bytes).digest('hex');

const langCounts = {};
for (const l of lang) langCounts[l] = (langCounts[l] || 0) + 1;
let commit = 'unknown';
try {
  commit = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: HERE }).toString().trim();
  if (execFileSync('git', ['status', '--porcelain', '--', '.'], { cwd: path.resolve(HERE, '..') }).toString().trim()) commit += ' + uncommitted changes';
} catch { /* not a git checkout */ }

const record = {
  firstRunUtc: firstRun.firstRunUtc,
  pinned: Boolean(pins),
  builtUtc: new Date().toISOString(),
  script: 'lab/p1-render/sample/build-sample.mjs',
  commit,
  seed: SEED,
  shuffle: 'mulberry32(seed), Fisher-Yates from the end, first 300,000 kept',
  daysUsed: days.map((d) => d.day),
  daysSkipped: skippedDays,
  files: {
    listed: days.reduce((a, d) => a + d.listed, 0),
    downloaded: days.reduce((a, d) => a + d.downloaded, 0),
    notListed: days.flatMap((d) => d.notListed),
    leftOut: days.flatMap((d) => d.leftOut)
  },
  perDay: days.map(({ sources, ...rest }) => rest),
  pointsBeforeDownSampling: total,
  rows: TARGET,
  arrowBytes: bytes.length,
  sha256,
  columns: { lat: 'float32', lon: 'float32', lang: 'dictionary<utf8>', t: 'uint32, Unix seconds of the 15-minute stamp' },
  languages: Object.keys(langCounts).length,
  topLanguages: Object.entries(langCounts).sort((a, b) => b[1] - a[1]).slice(0, 12)
};
writeFileSync(path.join(DATA, 'sample-record.json'), JSON.stringify(record, null, 2) + '\n');
writeFileSync(path.join(DATA, 'sources.txt'), days.flatMap((d) => d.sources).join('\n') + '\n');
log(`wrote ${out}: ${TARGET} rows, ${bytes.length} bytes, sha256 ${sha256}`);
log(`points before down-sampling: ${total}; days: ${record.daysUsed.join(', ')}`);
if (pins) {
  const sameDays = record.daysUsed.join(',') === pins.daysUsed.join(',');
  if (!sameDays || sha256 !== pins.sha256) {
    console.error(`the rebuilt sample differs from the pinned one (days ${record.daysUsed.join(', ')} against ${pins.daysUsed.join(', ')}; ` +
      `SHA-256 ${sha256} against ${pins.sha256}). The committed pick list will not match it.`);
    process.exit(1);
  }
  log('matches the pinned sample (sample/pinned.json), so the committed pick list matches it');
}
