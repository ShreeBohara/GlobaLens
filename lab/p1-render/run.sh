#!/usr/bin/env bash
# Runs the render spike and collects its results into results/ (lab/p1-render/prereg.md §5.1; plan §11:
# "runs from lab/<id>/run.sh"). macOS + Google Chrome. Needs Node 20 or later.
#
#   ./run.sh build        install the pinned packages and bundle the page
#   ./run.sh sample       build the point sample (downloads GDELT files; about 3.3 GB under data/)
#   ./run.sh picks-list   make the pick list (once; refuses to overwrite picks.json)
#   ./run.sh desktop      the desktop half: C1 (orbit), C3 (picks), C4 (far side), C5 (labels)
#   ./run.sh standin      the phone stand-in: 100k points, 412 × 915 at pixel ratio 2.625, 6× CPU throttle
#   ./run.sh projtile     the projectTile() smoke test (§5.6)
#   ./run.sh preview      one full pass of every check, in any machine state; never a gating run
#   ./run.sh rehearsal    one short run of each kind, in any machine state; never a gating run
#   ./run.sh phone        how to run the phone half
#
# The desktop suite is the gating one. It refuses to start unless the machine is in the state the
# pre-registration fixes (§5.2, §5.7): external display disconnected, mains power, low-power mode off.
# Close other applications first; the script cannot do that for you. Chrome opens in full screen on
# the built-in display and must be left alone until the suite ends (about 1 h 45 min).
# Set SPIKE_ALLOW_UNPINNED=1 to run it anyway; every result is then labelled "unpinned" and does not gate.

set -euo pipefail
cd "$(dirname "$0")"
PORT="${SPIKE_PORT:-5173}"
BASE="http://127.0.0.1:${PORT}"
STATE="$(mktemp -t p1-render-host-state).json"
NODE="node --experimental-websocket"
SERVER_PID=""

die() { echo "run.sh: $*" >&2; exit 1; }
cleanup() { [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true; rm -f "$STATE"; }
trap cleanup EXIT

start_server() {
  [ -f dist/app.js ] || die "the page is not built; run ./run.sh build"
  [ -f data/sample-300k.arrow ] || die "the sample is missing; run ./run.sh sample"
  if curl -s -o /dev/null "${BASE}/"; then die "something is already listening on port ${PORT}; stop it or set SPIKE_PORT"; fi
  node serve.mjs --port "$PORT" --host-state "$STATE" > data/.server.log 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 50); do curl -s -o /dev/null "${BASE}/" && return 0; sleep 0.1; done
  die "the server did not start"
}

# open_page <label> <token> <query> [chrome.mjs options...]
# Notes the host state, opens the page and waits for its result file.
open_page() {
  local label="$1" token="$2" query="$3"; shift 3
  node tools/host-state.mjs "$STATE" --label "$label" > /dev/null
  echo "$(date -u +%H:%M:%S) ${label} run ${token}: ${query}"
  $NODE tools/chrome.mjs --url "${BASE}/?${query}&label=${label}&run=${token}" --wait-file "run${token}-" "$@" \
    | tr '\n' ' '; echo
}

orbit_five() { # <label> <query> [options...]: five page loads, 60 s apart (§5.2)
  local label="$1" query="$2"; shift 2
  for k in 1 2 3 4 5; do
    open_page "$label" "$k" "mode=orbit&${query}" --timeout 180 "$@"
    [ "$k" = 5 ] || sleep 60
  done
}

GATING=(--foreground --fullscreen)   # plain Chrome, fresh profile, nothing attached to the page
DESK="w=1440&h=900"
STANDIN="n=100000&w=412&h=915&dpr=2.625&standin=1"

is_pinned() { node tools/host-state.mjs "$STATE" --label preflight > /dev/null; node -e "process.exit(JSON.parse(require('fs').readFileSync('$STATE','utf8')).pinned ? 0 : 1)"; }
build_clean() { # the page is rebuilt from the checked-out commit, and that commit is in every result (§5.1)
  local out; out="$(node build.mjs 2>&1 | tail -1)"; echo "$out"
  case "$out" in *uncommitted*) die "the page has uncommitted changes; commit them first, so the results name one commit" ;; esac
}

case "${1:-}" in
  build)
    npm ci --ignore-scripts --no-audit --no-fund
    node build.mjs
    ;;
  sample)
    node sample/build-sample.mjs
    ;;
  picks-list)
    [ ! -f picks.json ] || die "picks.json exists; the list is made once"
    start_server
    open_page make 0 "mode=makepicks&n=300000&${DESK}" --headless --size 1440,987 --timeout 180
    shasum -a 256 picks.json
    ;;
  desktop)
    LABEL=desktop
    if ! is_pinned; then
      [ "${SPIKE_ALLOW_UNPINNED:-0}" = 1 ] || die "not in the pinned state (external display attached, not on mains power, or low-power mode on). See the top of this file."
      LABEL=unpinned
      echo "run.sh: NOT in the pinned state; results are labelled 'unpinned' and do not gate" >&2
    fi
    [ -f picks.json ] || die "picks.json is missing; run ./run.sh picks-list"
    build_clean
    start_server
    # C1: basemap and discs, 300k, at the device's own pixel ratio. This is the gating run.
    orbit_five "${LABEL}-c1" "n=300000&${DESK}" "${GATING[@]}"
    # Reported, not gating: the battery tier's pixel ratio, and the scene with arcs and labels.
    orbit_five "${LABEL}-dpr1.5" "n=300000&${DESK}&dpr=1.5" "${GATING[@]}"
    orbit_five "${LABEL}-arcs-labels" "n=300000&${DESK}&arcs=1&labels=1" "${GATING[@]}"
    # C4 and C5, three runs each.
    for k in 1 2 3; do open_page "${LABEL}-c4" "$k" "mode=farside&n=300000&${DESK}" --timeout 900 "${GATING[@]}"; done
    for k in 1 2 3; do open_page "${LABEL}-c5" "$k" "mode=labels&n=300000&${DESK}" --timeout 600 "${GATING[@]}"; done
    # C3: the pick list, three runs.
    for k in 1 2 3; do open_page "${LABEL}-c3" "$k" "mode=picks&n=300000&${DESK}" --timeout 3600 "${GATING[@]}"; done
    echo "desktop suite finished; results are in results/"
    ;;
  standin)
    LABEL=standin-6x; is_pinned || LABEL=standin-6x-unpinned
    build_clean
    start_server
    # CPU throttling needs the DevTools protocol attached; this is the stand-in, never a gating run.
    orbit_five "$LABEL" "$STANDIN" --foreground --fullscreen --cdp --throttle 6
    ;;
  projtile)
    LABEL=projtile; is_pinned || LABEL=projtile-unpinned
    build_clean
    start_server
    open_page "$LABEL" 1 "mode=projtile&n=300000&${DESK}" --timeout 600 "${GATING[@]}"
    ;;
  preview)
    # One pass of everything, in whatever state the machine is in. It tells early whether a criterion
    # is in trouble and proves the harness end to end. It never gates, whatever the state.
    LABEL=preview; is_pinned || LABEL=preview-unpinned
    [ -f picks.json ] || die "picks.json is missing; run ./run.sh picks-list"
    build_clean
    start_server
    orbit_five "${LABEL}-standin-6x" "$STANDIN" --foreground --fullscreen --cdp --throttle 6
    orbit_five "${LABEL}-c1" "n=300000&${DESK}" "${GATING[@]}"
    open_page "${LABEL}-c4" 1 "mode=farside&n=300000&${DESK}" --timeout 900 "${GATING[@]}"
    open_page "${LABEL}-c5" 1 "mode=labels&n=300000&${DESK}" --timeout 600 "${GATING[@]}"
    open_page "${LABEL}-c3" 1 "mode=picks&n=300000&${DESK}" --timeout 3600 "${GATING[@]}"
    open_page "${LABEL}-projtile" 1 "mode=projtile&n=300000&${DESK}" --timeout 600 "${GATING[@]}"
    echo "preview finished; results are in results/"
    ;;
  rehearsal)
    start_server
    open_page rehearsal 1 "mode=orbit&n=300000&${DESK}" --timeout 180 "${GATING[@]}"
    open_page rehearsal 1 "mode=farside&n=300000&${DESK}&limit=4" --timeout 600 "${GATING[@]}"
    open_page rehearsal 1 "mode=labels&n=300000&${DESK}" --timeout 600 "${GATING[@]}"
    open_page rehearsal 1 "mode=picks&n=300000&${DESK}&limit=40" --timeout 900 "${GATING[@]}"
    open_page rehearsal 1 "mode=projtile&n=300000&${DESK}" --timeout 600 "${GATING[@]}"
    ;;
  phone)
    cat <<EOF
The phone half (C2, and C3–C5 on the phone), once a reference Android is named in docs/perf/devices.md:
  1. Enable USB debugging on the phone, connect it, and run:   adb reverse tcp:${PORT} tcp:${PORT}
  2. On this machine:                                          node serve.mjs --port ${PORT}
  3. In Chrome on the phone, in portrait, open each URL and wait for the JSON to appear:
       ${BASE}/?mode=orbit&n=100000&label=phone-c2&run=1        (five times, 60 s apart; run=1..5)
       ${BASE}/?mode=farside&n=100000&label=phone-c4&run=1      (three times)
       ${BASE}/?mode=labels&n=100000&label=phone-c5&run=1       (three times)
       ${BASE}/?mode=picks&n=100000&label=phone-c3&run=1        (three times)
  Note the phone's state by hand with each run (§5.7): battery level and temperature, battery saver off.
EOF
    ;;
  *)
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
