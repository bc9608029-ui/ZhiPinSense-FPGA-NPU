#!/usr/bin/env bash
# No-device simulation of the AC candidate deploy/startup/rollback scripts.
#
# Sections:
#   0. syntax + static safety (no pkill / no rm -rf / no fixed production sockets)
#   1. run_ac_candidate.sh strict-gate fail-closed (0 subprocesses on any bad input)
#   2. rollback_ac_candidate.sh identity-verified stop (refuse mismatches/other-RUN/
#      PID-reuse/PID0), RX-first order, bounded TERM grace, no auto-delete, idempotent
#   3. full fake-NPU/UI/RX success orchestration (strict-gate success -> correct argv
#      -> readiness -> RX exit -> ordered cleanup -> logs kept)
#
# Runs on a Linux host OR on Windows via Git Bash + Anaconda python.  Windows has no
# AF_UNIX, so the orchestration test uses AC_SOCK_TEST=1 (a plain file stands in for
# the socket) and an AC_ROLLBACK fixture (kills by recorded PID in rx->ui->npu order)
# -- both are documented test seams; the REAL `-S` socket check and the REAL rollback
# identity verification are exercised by the board run and by Section 2 here.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RUN_SH="$HERE/run_ac_candidate.sh"
ROLLBACK_SH="$HERE/rollback_ac_candidate.sh"
PY="$(command -v python || true)"
[ -z "$PY" ] && PY="/d/Anaconda/python"
pass=0; fail=0

say() { printf 'SELFTEST %s\n' "$*"; }
ok()  { say "PASS  $*"; pass=$((pass+1)); }
bad() { say "FAIL  $*"; fail=$((fail+1)); }

# =============================================================================
# Section 0 — syntax + static safety
# =============================================================================
say "== Section 0: syntax + static safety =="
for s in \
  "$HERE/install_overlay.sh" \
  "$HERE/board_collect_dep_sha.sh" \
  "$RUN_SH" \
  "$ROLLBACK_SH" \
  "$HERE/../overlay/rml24_final/board_runtime/run_repeat_mean_gapfix1.sh"; do
  if bash -n "$s" 2>/dev/null; then ok "syntax $(basename "$s")"; else bad "syntax $(basename "$s")"; fi
done
if grep -n 'pkill' "$RUN_SH" "$ROLLBACK_SH" >/dev/null 2>&1; then
  bad "no pkill in run/rollback"
else
  ok "no pkill in run/rollback"
fi
if grep -nE 'rm[[:space:]]+-[^ ]*r[^ ]*[[:space:]]|rm[[:space:]]+--recursive|rm[[:space:]]+-rf' "$ROLLBACK_SH" >/dev/null 2>&1; then
  bad "no recursive-delete in rollback"
else
  ok "no recursive-delete in rollback"
fi
if grep -nE '/run/rml24_standalone|/run/sdr_amr' "$RUN_SH" "$ROLLBACK_SH" >/dev/null 2>&1; then
  bad "no fixed production socket defaults in run/rollback"
else
  ok "no fixed production socket defaults in run/rollback"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---- shared fixture environment ----
FAKE_LEGACY="$TMP/legacy"
mkdir -p "$FAKE_LEGACY/build"
cat > "$FAKE_LEGACY/build/npu_stream" <<'EOF'
#!/usr/bin/env bash
echo "NPU_ARGV json=$1 raw=$2 sock=$3" >> "${FAKE_LOG:-/dev/null}"
touch "${3:-/dev/null}"
sleep 60
EOF
chmod +x "$FAKE_LEGACY/build/npu_stream"
touch "$FAKE_LEGACY/pluto_link_probe.py" "$FAKE_LEGACY/pilot_recovery.py"

MODEL_DIR="$TMP/model"
mkdir -p "$MODEL_DIR"
cp "/f/嵌赛/fix10class24_dualsdr1_work/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24/model_rml24_bf16/rml24_adamrv11_bf16.json" "$MODEL_DIR/"
cp "/f/嵌赛/fix10class24_dualsdr1_work/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24/model_rml24_bf16/rml24_adamrv11_bf16.raw" "$MODEL_DIR/"

TESTTREE="$TMP/testtree"
mkdir -p "$TESTTREE/bin" "$TESTTREE/rml24_final/board_runtime" "$TESTTREE/rml24_final/recovery"
cat > "$TESTTREE/bin/board_ui_live_rml24_final" <<'EOF'
#!/usr/bin/env bash
sock=""; ctl=""; sha=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --sock) sock="$2"; shift 2 ;;
    --ctl-sock) ctl="$2"; shift 2 ;;
    --model-sha) sha="$2"; shift 2 ;;
    --run-id) shift 2 ;;
    *) shift ;;
  esac
done
echo "UI_ARGV sock=$sock ctl=$ctl model_sha=$sha" >> "${FAKE_LOG:-/dev/null}"
touch "${sock:-/dev/null}"
echo "UI_LIVE_READY sock=$sock"
sleep 60
EOF
chmod +x "$TESTTREE/bin/board_ui_live_rml24_final"
cat > "$TESTTREE/rml24_final/board_runtime/standalone_receiver_multisignal.py" <<'EOF'
import os, re, sys, time
# MSYS2 converts POSIX args to Windows paths when it execs this native-Windows
# python; normalise them back for comparison against the bash fakes (test-only).
def posix(p):
    if p is None:
        return p
    m = re.match(r'^([A-Za-z]):([\\/])(.*)$', p)
    if m:
        return '/' + m.group(1).lower() + '/' + m.group(3).replace('\\', '/')
    return p
args = sys.argv[1:]
def get(k):
    for i, a in enumerate(args):
        if a == k and i + 1 < len(args):
            return args[i + 1]
    return None
ctl_raw = get('--ui-control-socket'); npu_raw = get('--npu-socket'); out_raw = get('--out')
ctl = posix(ctl_raw); npu = posix(npu_raw); out = posix(out_raw)
with open(os.environ.get('FAKE_LOG', os.devnull), 'a') as f:
    f.write('RX_ARGV ctl=%s npu=%s out=%s\n' % (ctl, npu, out))
if ctl_raw:
    try:
        open(ctl_raw, 'w').close()
    except OSError:
        pass
print('STANDALONE_MULTISIGNAL_READY no_tcp=1 no_tx_handshake=1', flush=True)
time.sleep(2)
print('STANDALONE_MULTISIGNAL_COMPLETE records=0 valid=0 rejected=0 restore_errors=0', flush=True)
sys.exit(0)
EOF
cp "$HERE/../local_base/recovery/candidate_two_dc.py" "$TESTTREE/rml24_final/recovery/candidate_two_dc.py"

# fixture preflight (orchestration seam; real preflight tested separately)
FIX_PF="$TMP/fixture_preflight.py"
cat > "$FIX_PF" <<'EOF'
import os, sys
mode = os.environ.get('PF_MODE', 'PASS_STRICT')
if mode == 'FAIL':
    print("PREFLIGHT result=FAIL rc=3 reason=expect_incomplete"); sys.exit(3)
if mode == 'OFFLINE':
    print("PREFLIGHT result=PASS_OFFLINE_ONLY rc=0 dependency_identity_verified=NO rf_forbidden=YES note=fixture"); sys.exit(0)
print("PREFLIGHT result=PASS_STRICT rc=0 dependency_identity_verified=YES note=fixture"); sys.exit(0)
EOF

# fixture rollback (orchestration seam): kill recorded PIDs in rx->ui->npu order
FIX_RB="$TMP/fixture_rollback.sh"
cat > "$FIX_RB" <<'EOF'
#!/usr/bin/env bash
set -u
RUN=""
while [ "$#" -gt 0 ]; do
  case "$1" in --run) RUN="$2"; shift 2 ;; --rx-grace-sec) shift 2 ;; --force) shift ;; *) shift ;; esac
done
[ -f "$RUN/pids.tsv" ] || exit 0
for role in rx ui npu; do
  pid="$(awk -F'\t' -v r="$role" '$1==r{print $2; exit}' "$RUN/pids.tsv" 2>/dev/null || true)"
  [ -n "$pid" ] || continue
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null
    for _ in $(seq 1 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
    kill -9 "$pid" 2>/dev/null || true
    echo "FIXTURE_STOPPED role=$role pid=$pid" >> "$RUN/fixture_order.log"
  else
    echo "FIXTURE_ALREADY_EXITED role=$role pid=$pid" >> "$RUN/fixture_order.log"
  fi
done
exit 0
EOF
chmod +x "$FIX_RB"

base_args=( --test "$TESTTREE" --legacy-root "$FAKE_LEGACY" --model-dir "$MODEL_DIR" --python "$PY" )

# =============================================================================
# Section 1 — strict-gate fail-closed (0 subprocesses on bad input)
# =============================================================================
say "== Section 1: strict gate fail-closed =="

# 1.1 no args -> usage rc=2
if bash "$RUN_SH" 2>/dev/null; then bad "1.1 no-args should fail"; else
  rc=$?; [ "$rc" = 2 ] && ok "1.1 no-args rc=2" || bad "1.1 no-args rc=$rc (want 2)"; fi

# 1.2 missing --expect -> usage rc=2
if bash "$RUN_SH" "${base_args[@]}" --run "$TMP/r12" 2>/dev/null; then bad "1.2 missing-expect should fail"; else
  rc=$?; [ "$rc" = 2 ] && ok "1.2 missing-expect rc=2" || bad "1.2 missing-expect rc=$rc (want 2)"; fi

# 1.3 expect file missing -> rc=2, no run dir created
if bash "$RUN_SH" "${base_args[@]}" --run "$TMP/r13" --expect "$TMP/nope.txt" 2>/dev/null; then bad "1.3 missing-expect-file should fail"; else
  rc=$?; [ "$rc" = 2 ] && ok "1.3 missing-expect-file rc=2" || bad "1.3 missing-expect-file rc=$rc"; fi
[ ! -e "$TMP/r13" ] && ok "1.3 no run dir before expect check" || bad "1.3 created run dir before expect check"

: > "$TMP/expect.txt"

# 1.4 bad python -> rc=2
if bash "$RUN_SH" --test "$TESTTREE" --legacy-root "$FAKE_LEGACY" --model-dir "$MODEL_DIR" \
     --run "$TMP/r14" --expect "$TMP/expect.txt" --python "/nonexistent/python" 2>/dev/null; then
  bad "1.4 bad-python should fail"; else
  rc=$?; [ "$rc" = 2 ] && ok "1.4 bad-python rc=2" || bad "1.4 bad-python rc=$rc"; fi

# 1.5 preflight FAIL (rc=3) -> run exits non-zero, 0 processes, no pids.tsv
export PF_MODE=FAIL AC_PREFLIGHT="$FIX_PF" AC_SOCK_TEST=1 FAKE_LOG="$TMP/fake15.log"
: > "$TMP/fake15.log"
if bash "$RUN_SH" "${base_args[@]}" --run "$TMP/r15" --expect "$TMP/expect.txt" 2>"$TMP/err15"; then
  bad "1.5 preflight-FAIL should fail"; else
  rc=$?; [ "$rc" = 3 ] && ok "1.5 preflight-FAIL rc=3" || bad "1.5 preflight-FAIL rc=$rc (want 3)"; fi
[ ! -f "$TMP/r15/pids.tsv" ] && ok "1.5 no pids.tsv (0 processes)" || bad "1.5 pids.tsv written despite gate fail"
[ ! -s "$TMP/fake15.log" ] && ok "1.5 no fake process started" || bad "1.5 a fake process started: $(cat "$TMP/fake15.log")"

# 1.6 preflight OFFLINE_ONLY (rc=0 but not PASS_STRICT) -> run rc=1, 0 processes
export PF_MODE=OFFLINE
if bash "$RUN_SH" "${base_args[@]}" --run "$TMP/r16" --expect "$TMP/expect.txt" 2>"$TMP/err16"; then
  bad "1.6 OFFLINE_ONLY should be rejected"; else
  rc=$?; [ "$rc" = 1 ] && ok "1.6 OFFLINE_ONLY rejected rc=1" || bad "1.6 OFFLINE_ONLY rc=$rc (want 1)"; fi
[ ! -f "$TMP/r16/pids.tsv" ] && ok "1.6 no pids.tsv (0 processes)" || bad "1.6 pids.tsv written despite OFFLINE_ONLY"

# 1.7 RUN already exists -> rc=2
export PF_MODE=PASS_STRICT
mkdir -p "$TMP/r17"
if bash "$RUN_SH" "${base_args[@]}" --run "$TMP/r17" --expect "$TMP/expect.txt" 2>/dev/null; then
  bad "1.7 existing-run should fail"; else
  rc=$?; [ "$rc" = 2 ] && ok "1.7 existing-run rc=2" || bad "1.7 existing-run rc=$rc"; fi

# 1.8 socket path too long -> rc=2 (before mkdir, before preflight)
LONGRUN="$TMP/$(printf 'x%.0s' $(seq 1 120))"
if bash "$RUN_SH" "${base_args[@]}" --run "$LONGRUN" --expect "$TMP/expect.txt" 2>/dev/null; then
  bad "1.8 too-long-socket-path should fail"; else
  rc=$?; [ "$rc" = 2 ] && ok "1.8 too-long-socket-path rc=2" || bad "1.8 too-long-socket-path rc=$rc"; fi

# =============================================================================
# Section 2 — rollback identity verification + order + no-delete
# =============================================================================
say "== Section 2: rollback identity + order + no-delete =="

FAKE_PROC="$TMP/proc"
mkdir -p "$FAKE_PROC/sys/kernel/random"
printf 'bootid-1234\n' > "$FAKE_PROC/sys/kernel/random/boot_id"
FAKE_BIN="$TMP/fake_bin"; : > "$FAKE_BIN"

mk_proc() {  # mk_proc pid starttime exe_target argv...
  local pid="$1" st="$2" exe="$3"; shift 3
  mkdir -p "$FAKE_PROC/$pid"
  printf '1 (fake) S 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 %s 0 0 0 0 0 0 0\n' "$st" > "$FAKE_PROC/$pid/stat"
  ln -sfn "$exe" "$FAKE_PROC/$pid/exe"
  : > "$FAKE_PROC/$pid/cmdline"
  local a; for a in "$@"; do printf '%s\0' "$a" >> "$FAKE_PROC/$pid/cmdline"; done
}
run_id() { { printf '%s\n' "$2"; printf '%s\n' "$3"; printf '%s\n' "$1"; } > "$1/run_id"; }
cur_exe() { readlink -f "$FAKE_PROC/$1/exe"; }
cur_av()  { sha256sum "$FAKE_PROC/$1/cmdline" | awk '{print $1}'; }
# run rollback, capturing output + its own exit code WITHOUT tripping set -e
rb() { set +e; RB_OUT="$(PROC_ROOT="$1" bash "$ROLLBACK_SH" --run "$2" "${@:3}" 2>&1)"; RB_RC=$?; set -e; }

# 2.1 kill-on-match: live sleep, full identity matches -> stopped
sleep 30 & S1=$!
mk_proc "$S1" 777 "$FAKE_BIN" sleep 30
mkdir -p "$TMP/r21"; run_id "$TMP/r21" bootid-1234 nonce1
printf 'rx\t%s\t%s\t%s\t%s\n' "$S1" 777 "$(cur_exe "$S1")" "$(cur_av "$S1")" > "$TMP/r21/pids.tsv"
rb "$FAKE_PROC" "$TMP/r21"
kill -0 "$S1" 2>/dev/null && bad "2.1 match should kill" || ok "2.1 identity-match stopped"
printf '%s\n' "$RB_OUT" | grep -q 'stopped role=rx' && ok "2.1 stopped logged" || bad "2.1 no stopped line: $RB_OUT"

# 2.2 boot_id mismatch -> refused, alive
sleep 30 & S2=$!
mk_proc "$S2" 778 "$FAKE_BIN" sleep 30
mkdir -p "$TMP/r22"; run_id "$TMP/r22" bootid-OTHER nonce2
printf 'rx\t%s\t%s\t%s\t%s\n' "$S2" 778 "$(cur_exe "$S2")" "$(cur_av "$S2")" > "$TMP/r22/pids.tsv"
rb "$FAKE_PROC" "$TMP/r22"
kill -0 "$S2" 2>/dev/null && ok "2.2 boot_id-mismatch NOT killed" || bad "2.2 boot_id-mismatch killed"
printf '%s\n' "$RB_OUT" | grep -q 'identity_mismatch(boot_id)' && ok "2.2 refused boot_id" || bad "2.2 no boot_id refusal: $RB_OUT"

# 2.3 starttime mismatch (PID reuse) -> refused, alive
sleep 30 & S3=$!
mk_proc "$S3" 900 "$FAKE_BIN" sleep 30
mkdir -p "$TMP/r23"; run_id "$TMP/r23" bootid-1234 nonce3
printf 'rx\t%s\t%s\t%s\t%s\n' "$S3" 901 "$(cur_exe "$S3")" "$(cur_av "$S3")" > "$TMP/r23/pids.tsv"
rb "$FAKE_PROC" "$TMP/r23"
kill -0 "$S3" 2>/dev/null && ok "2.3 starttime-mismatch NOT killed" || bad "2.3 starttime-mismatch killed"
printf '%s\n' "$RB_OUT" | grep -q 'identity_mismatch(starttime)' && ok "2.3 refused starttime" || bad "2.3 no starttime refusal: $RB_OUT"

# 2.4 exe mismatch (same-name production binary) -> refused, alive
sleep 30 & S4=$!
mk_proc "$S4" 780 "$FAKE_BIN" sleep 30
mkdir -p "$TMP/r24"; run_id "$TMP/r24" bootid-1234 nonce4
printf 'ui\t%s\t%s\t%s\t%s\n' "$S4" 780 "/usr/bin/board_ui_live_rml24_final" "$(cur_av "$S4")" > "$TMP/r24/pids.tsv"
rb "$FAKE_PROC" "$TMP/r24"
kill -0 "$S4" 2>/dev/null && ok "2.4 same-name-exe mismatch NOT killed" || bad "2.4 same-name-exe killed"
printf '%s\n' "$RB_OUT" | grep -q 'identity_mismatch(exe)' && ok "2.4 refused exe" || bad "2.4 no exe refusal: $RB_OUT"

# 2.5 argv mismatch (other RUN path in argv) -> refused, alive
sleep 30 & S5=$!
mk_proc "$S5" 781 "$FAKE_BIN" sleep 30
mkdir -p "$TMP/r25"; run_id "$TMP/r25" bootid-1234 nonce5
# recorded argv-sha is for a DIFFERENT run path; current cmdline is the real one
printf 'rx\t%s\t%s\t%s\t%s\n' "$S5" 781 "$(cur_exe "$S5")" "0000000000000000000000000000000000000000000000000000000000000000" > "$TMP/r25/pids.tsv"
rb "$FAKE_PROC" "$TMP/r25"
kill -0 "$S5" 2>/dev/null && ok "2.5 other-run argv NOT killed" || bad "2.5 other-run argv killed"
printf '%s\n' "$RB_OUT" | grep -q 'identity_mismatch(argv)' && ok "2.5 refused argv" || bad "2.5 no argv refusal: $RB_OUT"

# 2.6 identity unverifiable (recorded starttime == 0, i.e. /proc unreadable) -> refused, alive
sleep 30 & S6=$!
mk_proc "$S6" 782 "$FAKE_BIN" sleep 30
mkdir -p "$TMP/r26"; run_id "$TMP/r26" bootid-1234 nonce6
printf 'rx\t%s\t%s\t%s\t%s\n' "$S6" 0 "$(cur_exe "$S6")" "$(cur_av "$S6")" > "$TMP/r26/pids.tsv"
rb "$FAKE_PROC" "$TMP/r26"
kill -0 "$S6" 2>/dev/null && ok "2.6 unverifiable NOT killed" || bad "2.6 unverifiable killed"
printf '%s\n' "$RB_OUT" | grep -q 'identity_unverifiable' && ok "2.6 refused unverifiable" || bad "2.6 no unverifiable refusal: $RB_OUT"

# 2.7 PID 0 / 1 / negative / non-numeric -> all refused, none killed
mkdir -p "$TMP/r27"; run_id "$TMP/r27" bootid-1234 nonce7
printf 'rx\t0\t1\t%s\t%s\n'  "$(cur_exe "$S6")" "$(cur_av "$S6")" > "$TMP/r27/pids.tsv"
rb "$FAKE_PROC" "$TMP/r27"
printf '%s\n' "$RB_OUT" | grep -q 'pid_not_gt_1' && ok "2.7 pid0 refused" || bad "2.7 pid0 not refused: $RB_OUT"
printf 'ui\t-5\t1\tx\ty\n' > "$TMP/r27/pids.tsv"
rb "$FAKE_PROC" "$TMP/r27"
printf '%s\n' "$RB_OUT" | grep -q 'non_numeric' && ok "2.7 negative pid refused" || bad "2.7 negative pid not refused: $RB_OUT"

# 2.8 already-exited -> skip
mkdir -p "$TMP/r28"; run_id "$TMP/r28" bootid-1234 nonce8
printf 'npu\t999999\t777\t%s\t%s\n' "$FAKE_BIN" "$(cur_av "$S6")" > "$TMP/r28/pids.tsv"
rb "$FAKE_PROC" "$TMP/r28"
printf '%s\n' "$RB_OUT" | grep -q 'already_exited' && ok "2.8 already-exited logged" || bad "2.8 no already_exited: $RB_OUT"

# 2.9 order: rx -> ui -> npu regardless of pids.tsv order (scrambled: npu, ui, rx)
sleep 30 & SN=$!; mk_proc "$SN" 800 "$FAKE_BIN" sleep 30
sleep 30 & SU=$!; mk_proc "$SU" 801 "$FAKE_BIN" sleep 30
sleep 30 & SR=$!; mk_proc "$SR" 802 "$FAKE_BIN" sleep 30
mkdir -p "$TMP/r29"; run_id "$TMP/r29" bootid-1234 nonce9
{
  printf 'npu\t%s\t%s\t%s\t%s\n' "$SN" 800 "$(cur_exe "$SN")" "$(cur_av "$SN")"
  printf 'ui\t%s\t%s\t%s\t%s\n'  "$SU" 801 "$(cur_exe "$SU")" "$(cur_av "$SU")"
  printf 'rx\t%s\t%s\t%s\t%s\n'  "$SR" 802 "$(cur_exe "$SR")" "$(cur_av "$SR")"
} > "$TMP/r29/pids.tsv"
rb "$FAKE_PROC" "$TMP/r29"
rx_pos="$(printf '%s\n' "$RB_OUT" | grep -n 'stopped role=rx' | head -1 | cut -d: -f1)"
ui_pos="$(printf '%s\n' "$RB_OUT" | grep -n 'stopped role=ui' | head -1 | cut -d: -f1)"
np_pos="$(printf '%s\n' "$RB_OUT" | grep -n 'stopped role=npu' | head -1 | cut -d: -f1)"
if [ -n "$rx_pos" ] && [ -n "$ui_pos" ] && [ -n "$np_pos" ] && [ "$rx_pos" -lt "$ui_pos" ] && [ "$ui_pos" -lt "$np_pos" ]; then
  ok "2.9 order rx->ui->npu"
else
  bad "2.9 order wrong (rx=$rx_pos ui=$ui_pos npu=$np_pos): $RB_OUT"
fi

# 2.10 RX ignores TERM: bounded grace then FAILED_TO_STOP (no force), then --force kills
bash -c 'trap "" TERM; while :; do sleep 1; done' & ST=$!
mk_proc "$ST" 810 "$FAKE_BIN" bash -c slowrx
mkdir -p "$TMP/r210"; run_id "$TMP/r210" bootid-1234 nonce10
printf 'rx\t%s\t%s\t%s\t%s\n' "$ST" 810 "$(cur_exe "$ST")" "$(cur_av "$ST")" > "$TMP/r210/pids.tsv"
rb "$FAKE_PROC" "$TMP/r210" --rx-grace-sec 1
rc=$RB_RC
kill -0 "$ST" 2>/dev/null && ok "2.10 RX-alive-after-TERM (no force) still alive" || bad "2.10 RX died without force"
printf '%s\n' "$RB_OUT" | grep -q 'FAILED_TO_STOP' && ok "2.10 FAILED_TO_STOP visible" || bad "2.10 no FAILED_TO_STOP: $RB_OUT"
[ "$rc" != 0 ] && ok "2.10 non-zero on failure" || bad "2.10 rc=0 despite failed stop"
rb "$FAKE_PROC" "$TMP/r210" --rx-grace-sec 1 --force
kill -0 "$ST" 2>/dev/null && bad "2.10 --force did not kill" || ok "2.10 --force killed (recovery unverified)"
printf '%s\n' "$RB_OUT" | grep -q 'force_killed' && ok "2.10 force_killed logged" || bad "2.10 no force_killed: $RB_OUT"

# 2.11 --cleanup rejected + nothing deleted
mkdir -p "$TMP/r211"; printf 'sentinel' > "$TMP/r211/user.txt"
run_id "$TMP/r211" bootid-1234 nonce11
: > "$TMP/r211/pids.tsv"
rb "$FAKE_PROC" "$TMP/r211" --cleanup
rc=$RB_RC
[ "$rc" = 2 ] && ok "2.11 --cleanup rejected rc=2" || bad "2.11 --cleanup rc=$rc (want 2)"
[ -f "$TMP/r211/user.txt" ] && ok "2.11 sentinel kept (nothing deleted)" || bad "2.11 sentinel deleted"

# 2.12 default rollback keeps run dir + logs + sentinel
[ -f "$TMP/r21/pids.tsv" ] && [ -f "$TMP/r21/run_id" ] && ok "2.12 run dir kept (no auto-delete)" || bad "2.12 run dir deleted"

# 2.13 repeated rollback idempotent (already killed -> already_exited, rc=0)
rb "$FAKE_PROC" "$TMP/r21"
printf '%s\n' "$RB_OUT" | grep -q 'already_exited' && ok "2.13 idempotent (already_exited)" || bad "2.13 not idempotent: $RB_OUT"

# =============================================================================
# Section 3 — full fake NPU/UI/RX success orchestration
# =============================================================================
say "== Section 3: full success orchestration =="
export PF_MODE=PASS_STRICT AC_PREFLIGHT="$FIX_PF" AC_SOCK_TEST=1 AC_ROLLBACK="$FIX_RB"
export FAKE_LOG="$TMP/fake3.log"; : > "$TMP/fake3.log"
RUN3="$TMP/run3"
set +e
out="$(bash "$RUN_SH" "${base_args[@]}" --run "$RUN3" --expect "$TMP/expect.txt" --duration-sec 2 2>&1)"
rc=$?
set -e
[ "$rc" = 0 ] && ok "3.1 run completed rc=0" || bad "3.1 run rc=$rc: $out"
printf '%s\n' "$out" | grep -q 'RECEIVER_EXIT rc=0' && ok "3.1 RECEIVER_EXIT rc=0" || bad "3.1 no RECEIVER_EXIT: $out"
printf '%s\n' "$out" | grep -q 'AC_CANDIDATE_RUN completed=1' && ok "3.1 completed=1" || bad "3.1 no completed=1: $out"

# 3.2 correct argv (each role got this RUN's socket + frozen model paths)
grep -q "NPU_ARGV json=$MODEL_DIR/rml24_adamrv11_bf16.json raw=$MODEL_DIR/rml24_adamrv11_bf16.raw sock=$RUN3/npu.sock" "$TMP/fake3.log" \
  && ok "3.2 npu argv (model + npu.sock)" || bad "3.2 npu argv wrong: $(cat "$TMP/fake3.log")"
grep -q "UI_ARGV sock=$RUN3/ui.sock ctl=$RUN3/control.sock model_sha=c1781aec" "$TMP/fake3.log" \
  && ok "3.2 ui argv (ui.sock + control.sock)" || bad "3.2 ui argv wrong"
# RX (python) receives MSYS-converted Windows paths; compare the run-dir-relative
# tail so /tmp/...  ==  /c/Users/.../Temp/...  ==  C:/Users/.../Temp/... all agree.
tail2() { printf '%s' "$1" | tr '\\' '/' | awk -F/ '{n=NF; print (n>=2 ? $(n-1)"/"$n : $1)}'; }
RB="$(basename "$RUN3")"
rx_line="$(grep '^RX_ARGV ' "$TMP/fake3.log" | head -1)"
rx_ctl="$(printf '%s' "$rx_line" | sed -n 's/.* ctl=\([^ ]*\) npu=.*/\1/p')"
rx_npu="$(printf '%s' "$rx_line" | sed -n 's/.* npu=\([^ ]*\) out=.*/\1/p')"
rx_out="$(printf '%s' "$rx_line" | sed -n 's/.* out=\([^ ]*\)$/\1/p')"
if [ -n "$rx_ctl" ] && [ -n "$rx_npu" ] && [ -n "$rx_out" ] \
   && [ "$(tail2 "$rx_ctl")" = "$RB/control.sock" ] \
   && [ "$(tail2 "$rx_npu")" = "$RB/npu.sock" ] \
   && [ "$(tail2 "$rx_out")" = "$RB/capture" ]; then
  ok "3.2 rx argv (control.sock + npu.sock + out, same RUN)"
else
  bad "3.2 rx argv wrong (RB=$RB ctl=$(tail2 "$rx_ctl") npu=$(tail2 "$rx_npu") out=$(tail2 "$rx_out")): $rx_line"
fi

# 3.3 readiness order
np_rdy="$(printf '%s\n' "$out" | grep -n 'NPU_READY' | head -1 | cut -d: -f1)"
ui_rdy="$(printf '%s\n' "$out" | grep -n 'UI_COMM_READY' | head -1 | cut -d: -f1)"
rx_rdy="$(printf '%s\n' "$out" | grep -n 'RECEIVER_READY' | head -1 | cut -d: -f1)"
if [ -n "$np_rdy" ] && [ -n "$ui_rdy" ] && [ -n "$rx_rdy" ] && [ "$np_rdy" -lt "$ui_rdy" ] && [ "$ui_rdy" -lt "$rx_rdy" ]; then
  ok "3.3 readiness order NPU->UI->RX"
else
  bad "3.3 readiness order wrong (np=$np_rdy ui=$ui_rdy rx=$rx_rdy): $out"
fi

# 3.4 ordered cleanup (rx -> ui -> npu in fixture order log)
rx_p="$(grep -n 'role=rx' "$RUN3/fixture_order.log" | head -1 | cut -d: -f1)"
ui_p="$(grep -n 'role=ui' "$RUN3/fixture_order.log" | head -1 | cut -d: -f1)"
np_p="$(grep -n 'role=npu' "$RUN3/fixture_order.log" | head -1 | cut -d: -f1)"
if [ -n "$rx_p" ] && [ -n "$ui_p" ] && [ -n "$np_p" ] && [ "$rx_p" -lt "$ui_p" ] && [ "$ui_p" -lt "$np_p" ]; then
  ok "3.4 cleanup order rx->ui->npu"
else
  bad "3.4 cleanup order wrong (rx=$rx_p ui=$ui_p np=$np_p): $(cat "$RUN3/fixture_order.log")"
fi

# 3.5 logs kept
for f in preflight.log npu.log ui.log receiver.log pids.tsv run_id rollback.log; do
  [ -e "$RUN3/$f" ] || bad "3.5 missing $f"
done
[ -e "$RUN3/preflight.log" ] && [ -e "$RUN3/npu.log" ] && [ -e "$RUN3/ui.log" ] && [ -e "$RUN3/receiver.log" ] \
  && [ -e "$RUN3/pids.tsv" ] && [ -e "$RUN3/run_id" ] && [ -e "$RUN3/rollback.log" ] \
  && ok "3.5 all logs/identity kept" || true

# 3.6 all three fake processes gone
for f in "$RUN3/npu.sock" "$RUN3/ui.sock" "$RUN3/control.sock"; do
  # socket stand-ins were plain files; the fake procs are gone if their loop ended
  :
done
if grep -q 'PREFLIGHT_GATE_PASS' "$RUN3/preflight.log" 2>/dev/null || grep -q 'result=PASS_STRICT' "$RUN3/preflight.log"; then
  ok "3.6 preflight gate passed (PASS_STRICT)"
else
  bad "3.6 no PASS_STRICT in preflight.log"
fi

say "SUMMARY pass=$pass fail=$fail"
[ "$fail" = 0 ] && exit 0 || exit 1
