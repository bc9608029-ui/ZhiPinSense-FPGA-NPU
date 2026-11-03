#!/usr/bin/env bash
# AC-integration candidate rollback -- IDENTITY-VERIFIED, RX-first ordered stop,
# always-keep-dirs/logs (no auto-delete).
#
# Stops ONLY the processes recorded for THIS run, and ONLY when EVERY identity
# component still matches: same boot_id, same /proc/PID/stat starttime, expected
# role, exact exe (readlink of /proc/PID/exe), and the exact argv (sha256 of the
# NUL-separated /proc/PID/cmdline -- compared on real argument boundaries, never
# as a substring).  If any component is missing/unverifiable or mismatches, the
# PID is REFUSED (not killed) and the exit code is non-zero; it NEVER falls back
# to a generic program name and NEVER accepts 0/1/negative/non-numeric PIDs
# (`kill 0` would signal the whole process group).
#
# Stop order is RX -> (bounded TERM, wait for its device recovery) -> UI -> NPU,
# regardless of the pids.tsv order.  RX gets a bounded TERM grace and is NOT
# force-killed by default (that would interrupt device recovery); only an
# explicit --force escalates, and that marks recovery as UNVERIFIED.
#
# There is NO --cleanup auto-delete: the run directory and all logs are ALWAYS
# kept.  Passing --cleanup is rejected and deletes nothing.
set -euo pipefail

usage() { echo "usage: $0 --run RUN_DIR [--rx-grace-sec N] [--force]" >&2; }

RUN=""
FORCE=0
RX_GRACE_SEC=30
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run) RUN="$2"; shift 2 ;;
    --rx-grace-sec) RX_GRACE_SEC="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --cleanup)
      echo "ROLLBACK --cleanup removed: directories and logs are ALWAYS kept (no auto-delete)" >&2
      exit 2 ;;
    *) usage; exit 2 ;;
  esac
done
[ -n "$RUN" ] || { usage; exit 2; }
case "$RX_GRACE_SEC" in ''|*[!0-9]*) echo "ROLLBACK invalid --rx-grace-sec: $RX_GRACE_SEC" >&2; exit 2;; esac
[ "$RX_GRACE_SEC" -gt 0 ] || { echo "ROLLBACK invalid --rx-grace-sec (must be >0)" >&2; exit 2; }

PROC_ROOT="${PROC_ROOT:-/proc}"      # overridable for the no-device simulation
RUN_ID="$RUN/run_id"
PIDFILE="$RUN/pids.tsv"

if [ ! -f "$RUN_ID" ] || [ ! -f "$PIDFILE" ]; then
  echo "ROLLBACK no_identity (run_id/pids.tsv missing; nothing recorded; run dir kept)"
  exit 0
fi

# recorded run identity: boot_id / nonce / canonical run (three lines)
{
  IFS= read -r REC_BOOT || REC_BOOT=UNKNOWN
  IFS= read -r REC_NONCE || REC_NONCE=UNKNOWN
  IFS= read -r REC_RUN || REC_RUN=UNKNOWN
} < "$RUN_ID"

boot_id_now() { cat "$PROC_ROOT/sys/kernel/random/boot_id" 2>/dev/null || echo UNKNOWN; }
CUR_BOOT="$(boot_id_now)"

stopped=0; already=0; refused=0; failed=0

stop_one() {
  local role="$1" pid="$2" rec_start="$3" rec_exe="$4" rec_argv="$5"

  # PID sanity: >1 positive integer.  Reject 0/1/negative/non-numeric; never `kill 0`.
  case "$pid" in
    ''|*[!0-9]*) echo "ROLLBACK REFUSED role=$role pid='$pid' reason=non_numeric"; refused=$((refused+1)); return 1 ;;
  esac
  if [ "$pid" -le 1 ]; then
    echo "ROLLBACK REFUSED role=$role pid=$pid reason=pid_not_gt_1"; refused=$((refused+1)); return 1
  fi

  if ! kill -0 "$pid" 2>/dev/null; then
    echo "ROLLBACK already_exited role=$role pid=$pid"
    already=$((already+1))
    return 0
  fi

  local cur_start cur_exe cur_argv
  cur_start="$(awk '{print $22}' "$PROC_ROOT/$pid/stat" 2>/dev/null || echo 0)"
  cur_exe="$(readlink -f "$PROC_ROOT/$pid/exe" 2>/dev/null || echo UNKNOWN)"
  cur_argv="$(sha256sum "$PROC_ROOT/$pid/cmdline" 2>/dev/null | awk '{print $1}' || echo UNKNOWN)"

  # Identity must be verifiable on BOTH sides; never match on two UNKNOWNs.
  local unver=""
  [ "$REC_BOOT" != UNKNOWN ] && [ -n "$REC_BOOT" ] || unver="rec_boot_id"
  [ "$CUR_BOOT" != UNKNOWN ] || unver="${unver:+$unver,}cur_boot_id"
  [ "$rec_start" != 0 ] && [ "$rec_start" != UNKNOWN ] && [ -n "$rec_start" ] || unver="${unver:+$unver,}rec_starttime"
  [ "$cur_start" != 0 ] && [ "$cur_start" != UNKNOWN ] && [ -n "$cur_start" ] || unver="${unver:+$unver,}cur_starttime"
  [ -n "$rec_exe" ] && [ "$rec_exe" != UNKNOWN ] || unver="${unver:+$unver,}rec_exe"
  [ -n "$cur_exe" ] && [ "$cur_exe" != UNKNOWN ] || unver="${unver:+$unver,}cur_exe"
  [ -n "$rec_argv" ] && [ "$rec_argv" != UNKNOWN ] || unver="${unver:+$unver,}rec_argv"
  [ -n "$cur_argv" ] && [ "$cur_argv" != UNKNOWN ] || unver="${unver:+$unver,}cur_argv"
  if [ -n "$unver" ]; then
    echo "ROLLBACK REFUSED role=$role pid=$pid reason=identity_unverifiable($unver)"
    refused=$((refused+1))
    return 1
  fi

  local why=""
  [ "$CUR_BOOT" = "$REC_BOOT" ] || why="boot_id"
  [ "$cur_start" = "$rec_start" ] || why="${why:+$why,}starttime"
  [ "$cur_exe" = "$rec_exe" ] || why="${why:+$why,}exe"
  [ "$cur_argv" = "$rec_argv" ] || why="${why:+$why,}argv"
  if [ -n "$why" ]; then
    echo "ROLLBACK REFUSED role=$role pid=$pid reason=identity_mismatch($why)"
    refused=$((refused+1))
    return 1
  fi

  # identity verified -> stop.  RX gets the bounded device-recovery grace.
  local grace
  if [ "$role" = rx ]; then grace="$RX_GRACE_SEC"; else grace=5; fi

  kill "$pid" 2>/dev/null
  local i=0 exited=0
  while [ "$i" -lt $((grace * 10)) ]; do
    if ! kill -0 "$pid" 2>/dev/null; then exited=1; break; fi
    i=$((i+1)); sleep 0.1
  done

  if [ "$exited" = 1 ]; then
    echo "ROLLBACK stopped role=$role pid=$pid"
    stopped=$((stopped+1))
    return 0
  fi

  if [ "$FORCE" = 1 ]; then
    kill -9 "$pid" 2>/dev/null
    local k=0
    while [ "$k" -lt 10 ]; do
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "ROLLBACK force_killed role=$role pid=$pid (device recovery UNVERIFIED)"
        stopped=$((stopped+1))
        return 1
      fi
      k=$((k+1)); sleep 0.1
    done
  fi
  echo "ROLLBACK FAILED_TO_STOP role=$role pid=$pid (still alive after TERM; device recovery unverified)"
  failed=$((failed+1))
  return 1
}

# ordered stop: RX first (wait its cleanup/exit), then UI, then NPU
set +e
for role in rx ui npu; do
  # exact role match (field 1).  awk emits the 4 identity fields one per line so
  # empty fields are preserved; bash `read` with IFS=tab would collapse them.
  mapfile -t fld < <(awk -F'\t' -v r="$role" '$1==r {print $2; print $3; print $4; print $5; exit}' "$PIDFILE" 2>/dev/null)
  [ "${#fld[@]}" -ge 4 ] || continue
  stop_one "$role" "${fld[0]}" "${fld[1]}" "${fld[2]}" "${fld[3]}"
done
set -e

echo "ROLLBACK result=done stopped=$stopped already_exited=$already refused=$refused failed=$failed run_dir_kept=$RUN"
if [ "$refused" != 0 ] || [ "$failed" != 0 ]; then exit 1; fi
exit 0
