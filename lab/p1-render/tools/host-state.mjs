#!/usr/bin/env node
// Writes what prereg §5.7 asks to be noted with every run and the page cannot see:
// the machine, the OS, Chrome, the displays, the power source, the thermal state and the load average.
// It records no serial number, no user name and no names of other applications.
//
//   node tools/host-state.mjs <out.json> [--label <text>]
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import os from 'node:os';

const sh = (cmd, args) => { try { return execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); } catch { return ''; } };
const pick = (text, re) => (re.exec(text) || [])[1]?.trim() ?? null;
const out = process.argv[2];
const li = process.argv.indexOf('--label');
if (!out) { console.error('usage: host-state.mjs <out.json> [--label text]'); process.exit(2); }

const hw = sh('system_profiler', ['SPHardwareDataType']);
let displays = [];
try {
  const d = JSON.parse(sh('system_profiler', ['SPDisplaysDataType', '-json']));
  for (const gpu of d.SPDisplaysDataType || []) for (const x of gpu.spdisplays_ndrvs || []) {
    displays.push({
      builtIn: x.spdisplays_connection_type === 'spdisplays_internal',
      pixels: x._spdisplays_pixels || null,
      resolution: x._spdisplays_resolution || null,
      main: x.spdisplays_main === 'spdisplays_yes',
      online: x.spdisplays_online === 'spdisplays_yes' || x.spdisplays_online === undefined
    });
  }
} catch { /* leave empty */ }
const batt = sh('pmset', ['-g', 'batt']);
const therm = sh('pmset', ['-g', 'therm']);
const pm = sh('pmset', ['-g']);
const chrome = sh('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--version']).trim();
const visibleApps = sh('lsappinfo', ['visibleProcessList']).split(/\s+/).filter((x) => x.startsWith('ASN:')).length;

const state = {
  label: li >= 0 ? process.argv[li + 1] : null,
  notedUtc: new Date().toISOString(),
  model: pick(hw, /Model Name: (.*)/), modelIdentifier: pick(hw, /Model Identifier: (.*)/),
  chip: pick(hw, /Chip: (.*)/), cores: pick(hw, /Total Number of Cores: (.*)/), memory: pick(hw, /Memory: (.*)/),
  os: `${sh('sw_vers', ['-productName']).trim()} ${sh('sw_vers', ['-productVersion']).trim()} (${sh('sw_vers', ['-buildVersion']).trim()})`,
  chrome,
  displays,
  externalDisplayAttached: displays.some((d) => !d.builtIn && d.online),
  powerSource: pick(batt, /Now drawing from '([^']*)'/),
  batteryPercent: Number(pick(batt, /(\d+)%/)),
  lowPowerMode: pick(pm, /lowpowermode\s+(\d)/) === '1',
  thermal: {
    cpuSpeedLimit: pick(therm, /CPU_Speed_Limit\s*=\s*(\d+)/),
    schedulerLimit: pick(therm, /CPU_Scheduler_Limit\s*=\s*(\d+)/),
    noThermalWarning: /No thermal warning level has been recorded/.test(therm)
  },
  visibleApplications: visibleApps || null,
  // 1, 5 and 15 minute load averages: other work on the machine shows here (§5.7, "other apps closed").
  loadAverage: os.loadavg().map((x) => Math.round(x * 100) / 100)
};
state.pinned = !state.externalDisplayAttached && state.powerSource === 'AC Power' && !state.lowPowerMode;
writeFileSync(out, JSON.stringify(state, null, 1) + '\n');
console.log(JSON.stringify(state));
