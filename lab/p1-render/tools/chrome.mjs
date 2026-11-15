#!/usr/bin/env node
// Opens one spike URL in Google Chrome with a fresh profile and waits for the page to finish.
// No dependencies. On Node 20 run it with:  node --experimental-websocket tools/chrome.mjs ...
//
//   --url <url>            the page to open (required)
//   --size <w,h>           window size in CSS px (default 1512,945)
//   --headless             headless Chrome (development only; never a gating run)
//   --fullscreen           start in full screen (kiosk)
//   --foreground           start Chrome through `open`, so its window comes to the front and has focus
//                          (a run whose window is not focused is void, prereg §5.7)
//   --cdp                  attach over the DevTools protocol (needed for the options below)
//   --throttle <rate>      CPU throttling rate, e.g. 6 (the phone stand-in, prereg §6)
//   --screenshot <file>    save a PNG when the page is done
//   --eval <js>            evaluate an expression when the page is done and print it as JSON
//   --wait-file <substr>   instead of asking the page, wait for a result file whose name contains this
//   --timeout <seconds>    give up after this long (default 180)
//
// A gating run uses none of --headless, --cdp, --throttle: Chrome is started plainly and the
// script only watches the results folder, so nothing is attached to the page while it is timed.

import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS = path.resolve(HERE, '..', 'results');
const CHROME = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const opt = (name, fallback = null) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const url = opt('--url');
if (!url) { console.error('--url is required'); process.exit(2); }
const size = opt('--size', '1512,945');
const timeoutMs = Number(opt('--timeout', '180')) * 1000;
const useCdp = flag('--cdp') || flag('--headless') || opt('--throttle') || opt('--screenshot') || opt('--eval');
const waitFile = opt('--wait-file');

const profile = mkdtempSync(path.join(os.tmpdir(), 'p1-render-chrome-'));
const chromeArgs = [
  `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
  `--window-size=${size}`, '--window-position=0,0'
];
if (flag('--headless')) chromeArgs.push('--headless=new', '--hide-scrollbars');
if (flag('--fullscreen')) chromeArgs.push('--kiosk');
if (useCdp) chromeArgs.push('--remote-debugging-port=0');
chromeArgs.push(useCdp ? 'about:blank' : url);

const before = new Set(existsSync(RESULTS) ? readdirSync(RESULTS) : []);
const foreground = flag('--foreground');
const chrome = foreground
  ? spawn('open', ['-n', '-a', 'Google Chrome', '--args', ...chromeArgs], { stdio: 'ignore' })
  : spawn(CHROME, chromeArgs, { stdio: 'ignore' });
let exited = false;
chrome.on('exit', () => { if (!foreground) exited = true; }); // `open` returns at once; Chrome keeps running

function cleanup(code) {
  try {
    if (foreground) spawn('pkill', ['-f', profile], { stdio: 'ignore' }); // only the Chrome started here uses this profile
    else if (!exited) chrome.kill('SIGTERM');
  } catch { /* already gone */ }
  setTimeout(() => {
    try { rmSync(profile, { recursive: true, force: true }); } catch { /* Chrome may still hold files */ }
    process.exit(code);
  }, 800);
}
process.on('SIGINT', () => cleanup(130));

async function connectCdp() {
  const portFile = path.join(profile, 'DevToolsActivePort');
  // A fresh profile's first start can take 15 s or more before the port is written.
  for (let i = 0; i < 600 && !existsSync(portFile); i++) await sleep(100);
  if (!existsSync(portFile)) throw new Error('Chrome did not open its DevTools port within 60 s');
  const port = readFileSync(portFile, 'utf8').split('\n')[0].trim();
  let target = null;
  for (let i = 0; i < 50 && !target; i++) {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    target = list.find((t) => t.type === 'page');
    if (!target) await sleep(100);
  }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const n = ++id;
    pending.set(n, { resolve, reject });
    ws.send(JSON.stringify({ id: n, method, params }));
  });
  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  return { send, evaluate, close: () => ws.close() };
}

const newResultFile = () => (existsSync(RESULTS) ? readdirSync(RESULTS) : [])
  .find((f) => !before.has(f) && (!waitFile || f.includes(waitFile)));

try {
  let cdp = null;
  if (useCdp) {
    cdp = await connectCdp();
    const rate = opt('--throttle');
    if (rate) await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(rate) });
    await cdp.send('Page.navigate', { url });
  }
  const t0 = Date.now();
  let outcome = null;
  while (Date.now() - t0 < timeoutMs && !exited) {
    await sleep(500);
    if (waitFile || !cdp) {
      const f = newResultFile();
      if (f) { outcome = { resultFile: f }; break; }
    } else {
      const s = await cdp.evaluate(`(() => window.__spikeError ? { error: window.__spikeError } : (window.__spikeResult !== undefined ? { done: true } : null))()`).catch(() => null);
      if (s) { outcome = s; break; }
      if (flag('--no-result')) {
        const hudText = await cdp.evaluate(`document.getElementById('hud')?.textContent || ''`).catch(() => '');
        if (/^view ·/.test(hudText)) { outcome = { view: hudText }; break; }
      }
    }
  }
  if (!outcome) outcome = { timeout: true };
  if (cdp) {
    const shot = opt('--screenshot');
    if (shot) {
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' });
      writeFileSync(shot, Buffer.from(data, 'base64'));
    }
    const expr = opt('--eval');
    if (expr) outcome.eval = await cdp.evaluate(expr).catch((e) => ({ evalError: String(e.message || e) }));
    cdp.close();
  }
  console.log(JSON.stringify(outcome, null, 1));
  cleanup(outcome.timeout || outcome.error ? 1 : 0);
} catch (e) {
  console.error(String(e.stack || e));
  cleanup(1);
}
