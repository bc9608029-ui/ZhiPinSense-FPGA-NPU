#!/usr/bin/env bash
# AC-integration candidate startup: NPU -> UI -> receiver (multi-signal entry),
# STRICT-GATED (see preflight_deploy.py --expect).
#
# Order of operations (fail-closed):
#   1. parse + validate args (--expect is mandatory, --python chooses the interpreter)
#   2. verify the Python interpreter actually runs (rejects the WindowsApps stub)
#   3. RUN must be an absolute, not-yet-existing path (exclusive create)
#   4. all three sockets live under $RUN; their path length is checked up front
#   5. prerequisite paths exist (npu_stream / pluto / pilot / model / UI / entry / two-DC)
#   6. frozen model + two-DC SHA gate
#   7. mkdir $RUN (exclusive)
#   8. run preflight_deploy.py in STRICT mode against the REAL test tree; only
#      rc=0 AND result=PASS_STRICT may start ANY subprocess
#   9. write run_id + pids.tsv, then start NPU -> UI -> receiver, recording each
#      child's full process identity (boot_id / starttime / exe / argv-sha)
#
# On exit or INT/TERM it stops THIS round's processes via
# scripts/rollback_ac_candidate.sh (RX -> UI -> NPU order, identity-verified).
# It never installs anything, never touches the base tree, and never starts a
# production service.  Socket/rollback/preflight are overridable via env for the
# offline no-device test ONLY; the defaults are the real strict gate + real
# rollback + real AF_UNIX socket check and are never weakened in production.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PREFLIGHT="${AC_PREFLIGHT:-$HERE/preflight_deploy.py}"
ROLLBACK="${AC_ROLLBACK:-$HERE/rollback_ac_candidate.sh}"
PROC_ROOT="${PROC_ROOT:-/proc}"

# Offline no-device test seam (Windows has no AF_UNIX): when AC_SOCK_TEST=1 a
# plain file at the socket path counts as "ready".  On the board this is NEVER
# set and the check remains a real `-S` socket test.
sock_ready() { if [ "${AC_SOCK_TEST:-0}" = 1 ]; then [ -e "$1" ]; else [ -S "$1" ]; fi; }

usage() {
  echo "usage: $0 --test TEST_TREE --legacy-root DIR --model-dir DIR --run DIR --expect FILE" >&2
  echo "         [--python PY] [--initial-mode FIXED|BAND_SCAN] [--duration-sec N]" >&2
  echo "         [--scan-start-hz HZ] [--scan-stop-hz HZ] [--scan-step-hz HZ] [--save]" >&2
  echo "         [--rx-grace-sec N]" >&2
}

# ---- all variables defined before use (set -u enforces no undefined refs) ----
RUN=""
TEST_TREE=""
LEGACY_ROOT=""
MODEL_DIR=""
EXPECT=""
PYTHON="python3"
INITIAL_MODE="FIXED"
DURATION_SEC="60"
SCAN_START="2395000000"
SCAN_STOP="2405000000"
SCAN_STEP="1000000"
RX_GRACE_SEC="30"
SAVE_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --test) TEST_TREE="$2"; shift 2 ;;
    --legacy-root) LEGACY_ROOT="$2"; shift 2 ;;
    --model-dir) MODEL_DIR="$2"; shift 2 ;;
    --run) RUN="$2"; shift 2 ;;
    --expect) EXPECT="$2"; shift 2 ;;
    --python) PYTHON="$2"; shift 2 ;;
    --initial-mode) INITIAL_MODE="$2"; shift 2 ;;
    --duration-sec) DURATION_SEC="$2"; shift 2 ;;
    --scan-start-hz) SCAN_START="$2"; shift 2 ;;
    --scan-stop-hz) SCAN_STOP="$2"; shift 2 ;;
    --scan-step-hz) SCAN_STEP="$2"; shift 2 ;;
    --rx-grace-sec) RX_GRACE_SEC="$2"; shift 2 ;;
    --save) SAVE_ARGS=(--save-captures); shift ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$RUN" ] && [ -n "$TEST_TREE" ] && [ -n "$LEGACY_ROOT" ] && [ -n "$MODEL_DIR" ] && [ -n "$EXPECT" ] \
  || { usage; exit 2; }
[ "$INITIAL_MODE" = FIXED ] || [ "$INITIAL_MODE" = BAND_SCAN ] || { usage; exit 2; }
[ -f "$EXPECT" ] || { echo "expect file missing: $EXPECT" >&2; exit 2; }
[ -f "$PREFLIGHT" ] || { echo "preflight script missing: $PREFLIGHT" >&2; exit 2; }
[ -f "$ROLLBACK" ] || { echo "rollback script missing: $ROLLBACK" >&2; exit 2; }
case "$RX_GRACE_SEC" in ''|*[!0-9]*) echo "invalid --rx-grace-sec: $RX_GRACE_SEC" >&2; exit 2;; esac
[ "$RX_GRACE_SEC" -gt 0 ] || { echo "invalid --rx-grace-sec (must be >0): $RX_GRACE_SEC" >&2; exit 2; }

# ---- 2. Python interpreter must exist AND actually run (not the WindowsApps stub) ----
command -v "$PYTHON" >/dev/null 2>&1 || { echo "python interpreter not found: $PYTHON" >&2; exit 2; }
if ! "$PYTHON" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then
  echo "python interpreter self-check failed (not a working interpreter): $PYTHON" >&2; exit 2
fi

# ---- 3. RUN must be absolute + not already present (exclusive create, no symlink alias) ----
case "$RUN" in
  /*) ;;
  *) echo "run dir must be an absolute path: $RUN" >&2; exit 2 ;;
esac
if [ -e "$RUN" ] || [ -L "$RUN" ]; then
  echo "run directory already exists (exclusive create): $RUN" >&2; exit 2
fi

# ---- 4. sockets under $RUN + path-length check (Unix sun_path is 108 bytes) ----
NPU_SOCK="$RUN/npu.sock"
UI_SOCK="$RUN/ui.sock"
UI_CTL_SOCK="$RUN/control.sock"
for s in "$NPU_SOCK" "$UI_SOCK" "$UI_CTL_SOCK"; do
  if [ "${#s}" -gt 100 ]; then
    echo "socket path too long (${#s} bytes > 100): $s" >&2; exit 2
  fi
done

# ---- 5. prerequisite paths (checked BEFORE preflight / any process) ----
[ -x "$LEGACY_ROOT/build/npu_stream" ] || { echo "missing npu_stream: $LEGACY_ROOT/build/npu_stream" >&2; exit 2; }
[ -f "$LEGACY_ROOT/pluto_link_probe.py" ] || { echo "missing pluto_link_probe.py in --legacy-root" >&2; exit 2; }
[ -f "$LEGACY_ROOT/pilot_recovery.py" ] || { echo "missing pilot_recovery.py in --legacy-root" >&2; exit 2; }
[ -f "$MODEL_DIR/rml24_adamrv11_bf16.json" ] || { echo "missing model json" >&2; exit 2; }
[ -f "$MODEL_DIR/rml24_adamrv11_bf16.raw" ] || { echo "missing model raw" >&2; exit 2; }
[ -x "$TEST_TREE/bin/board_ui_live_rml24_final" ] || { echo "missing board_ui_live_rml24_final (build first): $TEST_TREE/bin/board_ui_live_rml24_final" >&2; exit 2; }
RECEIVER="$TEST_TREE/rml24_final/board_runtime/standalone_receiver_multisignal.py"
[ -f "$RECEIVER" ] || { echo "missing candidate entry: $RECEIVER" >&2; exit 2; }
TWO_DC="$TEST_TREE/rml24_final/recovery/candidate_two_dc.py"
[ -f "$TWO_DC" ] || { echo "missing candidate_two_dc.py: $TWO_DC" >&2; exit 2; }

# ---- 6. frozen identity gates (fail-closed, same SHAs as the A-line runner) ----
MODEL_JSON_SHA="28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
TWO_DC_SHA="e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a"
if ! echo "$MODEL_JSON_SHA  $MODEL_DIR/rml24_adamrv11_bf16.json" | sha256sum -c - >/dev/null 2>&1; then
  echo "model json SHA mismatch (gate): $MODEL_DIR/rml24_adamrv11_bf16.json" >&2; exit 2
fi
if ! echo "$MODEL_RAW_SHA  $MODEL_DIR/rml24_adamrv11_bf16.raw" | sha256sum -c - >/dev/null 2>&1; then
  echo "model raw SHA mismatch (gate): $MODEL_DIR/rml24_adamrv11_bf16.raw" >&2; exit 2
fi
if ! echo "$TWO_DC_SHA  $TWO_DC" | sha256sum -c - >/dev/null 2>&1; then
  echo "two-DC SHA mismatch (gate): $TWO_DC" >&2; exit 2
fi

# ---- 7. exclusive create of the run dir ----
mkdir "$RUN"

# ---- 8. strict preflight gate (BEFORE any process) ----
"$PYTHON" "$PREFLIGHT" --tree "$TEST_TREE" --expect "$EXPECT" > "$RUN/preflight.log" 2>&1
PF_RC=$?
if [ "$PF_RC" != 0 ]; then
  echo "PREFLIGHT_GATE_FAIL rc=$PF_RC (strict --expect; see $RUN/preflight.log)" >&2
  tail -n 40 "$RUN/preflight.log" >&2 || true
  exit "$PF_RC"
fi
if ! grep -q 'result=PASS_STRICT' "$RUN/preflight.log"; then
  echo "PREFLIGHT_GATE_FAIL rc=0 result_not_PASS_STRICT (PASS_OFFLINE_ONLY is NOT accepted)" >&2
  tail -n 40 "$RUN/preflight.log" >&2 || true
  exit 1
fi
echo "PREFLIGHT_GATE_PASS result=PASS_STRICT tree=$TEST_TREE expect=$EXPECT"

# ---- 9. run identity + pid table (boot_id / nonce / canonical run) ----
boot_id_now() { cat "$PROC_ROOT/sys/kernel/random/boot_id" 2>/dev/null || echo UNKNOWN; }
BOOT_ID="$(boot_id_now)"
NONCE="$(cat "$PROC_ROOT/sys/kernel/random/uuid" 2>/dev/null || echo "$(date +%s%N)-$$")"
{
  printf '%s\n' "$BOOT_ID"
  printf '%s\n' "$NONCE"
  printf '%s\n' "$RUN"
} > "$RUN/run_id"
PIDFILE="$RUN/pids.tsv"
: > "$PIDFILE"

# full process identity capture (boot_id/starttime/exe/argv-sha), retrying until
# the child's cmdline stabilises after exec so the recorded argv is the real one.
starttime_of() { awk '{print $22}' "$PROC_ROOT/$1/stat" 2>/dev/null || echo 0; }
exe_of() { readlink -f "$PROC_ROOT/$1/exe" 2>/dev/null || echo UNKNOWN; }
argv_sha_of() { sha256sum "$PROC_ROOT/$1/cmdline" 2>/dev/null | awk '{print $1}' || echo UNKNOWN; }
EMPTY_SHA="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
record_identity() {
  local role="$1" pid="$2" st ex av i
  av=""
  for i in $(seq 1 40); do
    av="$(argv_sha_of "$pid")"
    [ -n "$av" ] && [ "$av" != UNKNOWN ] && [ "$av" != "$EMPTY_SHA" ] && break
    sleep 0.05
  done
  st="$(starttime_of "$pid")"
  ex="$(exe_of "$pid")"
  printf '%s\t%s\t%s\t%s\t%s\n' "$role" "$pid" "$st" "$ex" "$av" >> "$PIDFILE"
}

# ---- 10. traps: idempotent cleanup, preserves original exit code, no masking ----
cleanup() {
  local rc=$?
  set +e
  "$ROLLBACK" --run "$RUN" --rx-grace-sec "$RX_GRACE_SEC" > "$RUN/rollback.log" 2>&1
  local s=$?
  set -e
  if [ "$s" -ne 0 ]; then
    echo "AC_CANDIDATE_CLEANUP_FAILED rollback_rc=$s original_exit=$rc see=$RUN/rollback.log" >&2
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# ---- 11. NPU stream (record full identity, then wait socket+alive) ----
"$LEGACY_ROOT/build/npu_stream" \
  "$MODEL_DIR/rml24_adamrv11_bf16.json" \
  "$MODEL_DIR/rml24_adamrv11_bf16.raw" \
  "$NPU_SOCK" > "$RUN/npu.log" 2>&1 &
NPU_PID=$!
record_identity npu "$NPU_PID"
NPU_READY=0
for _ in $(seq 1 100); do
  if sock_ready "$NPU_SOCK" && kill -0 "$NPU_PID" 2>/dev/null; then NPU_READY=1; break; fi
  kill -0 "$NPU_PID" 2>/dev/null || break
  sleep 0.1
done
if [ "$NPU_READY" != 1 ]; then
  echo "NPU_NOT_READY pid=$NPU_PID sock=$NPU_SOCK" >&2
  tail -n 20 "$RUN/npu.log" >&2 || true
  exit 1
fi
echo "NPU_READY pid=$NPU_PID sock=$NPU_SOCK"

# ---- 12. UI binary (record identity; readiness = alive + socket + UI_LIVE_READY) ----
"$TEST_TREE/bin/board_ui_live_rml24_final" \
  --sock "$UI_SOCK" --ctl-sock "$UI_CTL_SOCK" \
  --model-sha "$MODEL_RAW_SHA" --run-id "ac_candidate_$(date +%s)" \
  > "$RUN/ui.log" 2>&1 &
UI_PID=$!
record_identity ui "$UI_PID"
UI_READY=0
for _ in $(seq 1 100); do
  if sock_ready "$UI_SOCK" && kill -0 "$UI_PID" 2>/dev/null \
     && grep -aq 'UI_LIVE_READY' "$RUN/ui.log" 2>/dev/null; then UI_READY=1; break; fi
  kill -0 "$UI_PID" 2>/dev/null || break
  sleep 0.1
done
if [ "$UI_READY" != 1 ]; then
  echo "UI_NOT_READY pid=$UI_PID sock=$UI_SOCK (process-comm readiness only; physical screen needs UI_FB_READY)" >&2
  tail -n 20 "$RUN/ui.log" >&2 || true
  exit 1
fi
echo "UI_COMM_READY pid=$UI_PID sock=$UI_SOCK (physical screen acceptance is separate: UI_FB_READY)"

# ---- 13. Receiver (record identity; readiness = alive + READY marker + control sock) ----
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  "$PYTHON" "$RECEIVER" \
    --legacy-root "$LEGACY_ROOT" --npu-socket "$NPU_SOCK" \
    --ui-socket "$UI_SOCK" --ui-control-socket "$UI_CTL_SOCK" \
    --out "$RUN/capture" --initial-mode "$INITIAL_MODE" --duration-sec "$DURATION_SEC" \
    --scan-start-hz "$SCAN_START" --scan-stop-hz "$SCAN_STOP" --scan-step-hz "$SCAN_STEP" \
    "${SAVE_ARGS[@]}" > "$RUN/receiver.log" 2>&1 &
RX_PID=$!
record_identity rx "$RX_PID"
RX_READY=0
for _ in $(seq 1 600); do
  if kill -0 "$RX_PID" 2>/dev/null \
     && grep -aq 'STANDALONE_MULTISIGNAL_READY' "$RUN/receiver.log" 2>/dev/null \
     && sock_ready "$UI_CTL_SOCK"; then RX_READY=1; break; fi
  kill -0 "$RX_PID" 2>/dev/null || break
  sleep 0.1
done
if [ "$RX_READY" != 1 ]; then
  echo "RECEIVER_NOT_READY pid=$RX_PID (no STANDALONE_MULTISIGNAL_READY / control sock within 60s)" >&2
  tail -n 30 "$RUN/receiver.log" >&2 || true
  exit 1
fi
echo "RECEIVER_READY pid=$RX_PID"

# ---- wait for the receiver; the EXIT trap performs ordered cleanup (RX->UI->NPU) ----
set +e
wait "$RX_PID"
RX_RC=$?
set -e
echo "RECEIVER_EXIT rc=$RX_RC"
grep -ao 'STANDALONE_MULTISIGNAL_COMPLETE[^[:cntrl:]]*' "$RUN/receiver.log" 2>/dev/null || true
echo "AC_CANDIDATE_RUN completed=1 initial_mode=$INITIAL_MODE run=$RUN rc=$RX_RC"
exit "$RX_RC"
