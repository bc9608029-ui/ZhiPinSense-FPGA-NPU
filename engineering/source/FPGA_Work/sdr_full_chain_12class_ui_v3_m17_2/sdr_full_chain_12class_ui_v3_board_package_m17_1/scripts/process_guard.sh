#!/usr/bin/env bash
# process_guard.sh -- M17.2 acceptance-process safety helpers (source-only).
#
# Pure shell functions used by run_m17_touch_acceptance.sh and
# test_touch_mode_control.sh to make the acceptance fail-closed and honest:
#
#   * PID liveness + identity (is a PID alive, and is it the RIGHT executable --
#     never trust a stale/reused PID file);
#   * socket liveness (is a filesystem socket node actually SERVED by a live
#     process, or is it a stale node left behind by a dead process);
#   * byte-offset log tailing (only look at log lines appended AFTER a recorded
#     offset -- so an old TOUCH_CONTROL_RESULT from a previous run can never
#     produce a false PASS);
#   * unique run ids;
#   * best-effort process stopping (SIGTERM, then SIGKILL after a grace).
#
# These functions must NOT depend on `lsof`/`fuser`/`pgrep` (which may be absent
# on the board); they use only `/proc` + coreutils (`readlink`, `wc`, `tail`,
# `grep`, `kill`).
#
# Sourced (never executed directly).  Library guard:
#   PROCESS_GUARD_LIB=1 . scripts/process_guard.sh   # define helpers only
#
# NOTE: do not add `set -e`/`set -u` here -- callers manage their own strictness.
# All helpers below are `set -u`-safe (defaulted expansions).

pid_alive() {
    kill -0 "$1" 2>/dev/null
}

# pid_exe <pid> -> prints the executable path for a live PID (empty if gone/zombie).
pid_exe() {
    readlink "/proc/$1/exe" 2>/dev/null || true
}

# pid_matches_bin <pid> <binpath> -> 0 iff the PID is alive AND its executable is
# exactly <binpath>.  Rejects stale PIDs, reused PIDs, and wrong binaries.
pid_matches_bin() {
    local p="$1" bin="$2" exe
    pid_alive "$p" || return 1
    exe="$(pid_exe "$p")"
    [ -n "$exe" ] && [ "$exe" = "$bin" ]
}

# find_pids_named <exe-basename> -> prints one PID per line whose executable
# basename equals <exe-basename>.  Scans /proc directly (no pgrep dependency).
find_pids_named() {
    local base="$1" exe b p
    for p in /proc/[0-9]*; do
        [ -d "$p" ] || continue
        exe="$(readlink "$p/exe" 2>/dev/null || true)"
        [ -n "$exe" ] || continue
        b="$(basename "$exe")"
        [ "$b" = "$base" ] && printf '%s\n' "${p#/proc/}"
    done
    return 0
}

# socket_served <sockpath> -> 0 iff the socket node exists AND a live process has
# it bound (visible in /proc/net/unix).  A stale node left by a dead process
# passes `-S` but is NOT listed in /proc/net/unix, so this returns non-zero.
socket_served() {
    local sock="$1"
    [ -S "$sock" ] || return 1
    grep -qF "$sock" /proc/net/unix 2>/dev/null
}

# socket_inode <sockpath> -> prints the inode of the served socket (empty if none).
socket_inode() {
    local sock="$1"
    awk -v p="$sock" '$0 !~ /^Num/ && $NF == p { print $(NF-1) }' /proc/net/unix 2>/dev/null | head -n 1
}

# socket_served_by <sockpath> <pid> -> 0 iff the socket node is served AND that
# serving socket is held by <pid> (matches the inode against /proc/<pid>/fd/*).
# This is the "socket ownership" check: a live-but-wrong-owner socket fails.
socket_served_by() {
    local sock="$1" p="$2" ino fd
    [ -S "$sock" ] || return 1
    pid_alive "$p" || return 1
    ino="$(socket_inode "$sock")"
    [ -n "$ino" ] || return 1
    for fd in /proc/$p/fd/*; do
        [ -e "$fd" ] || continue
        if [ "$(readlink "$fd" 2>/dev/null)" = "socket:[$ino]" ]; then
            return 0
        fi
    done
    return 1
}

# stop_pid <pid> -> best-effort stop: SIGTERM, grace, then SIGKILL.  Returns 0
# even if the PID is already gone.  Never touches a PID that is not alive.
stop_pid() {
    local p="$1" i=0
    [ -n "$p" ] || return 0
    pid_alive "$p" || return 0
    kill "$p" 2>/dev/null || true
    while pid_alive "$p" && [ "$i" -lt 50 ]; do
        sleep 0.1
        i=$((i + 1))
    done
    if pid_alive "$p"; then
        kill -9 "$p" 2>/dev/null || true
    fi
    return 0
}

# log_offset_of <file> -> prints the current byte size (0 if absent).
log_offset_of() {
    local f="$1"
    if [ -f "$f" ]; then
        wc -c < "$f" | tr -d ' '
    else
        echo 0
    fi
}

# tail_since <file> <offset> -> prints bytes from <offset>+1 onward (i.e. only
# content appended AFTER the recorded offset); the whole file if offset is 0.
tail_since() {
    local f="$1" off="${2:-0}"
    if [ "$off" -gt 0 ]; then
        tail -c +$((off + 1)) "$f" 2>/dev/null || true
    else
        cat "$f" 2>/dev/null || true
    fi
}

# run_id_new -> prints a fresh, monotonic, per-invocation-unique run id.
run_id_new() {
    _RUN_ID_SEQ=$(( ${_RUN_ID_SEQ:-0} + 1 ))
    printf 'm17_%s_%s_%s_%s\n' "$(date +%s)" "$$" "$_RUN_ID_SEQ" "$RANDOM"
}
