#!/usr/bin/env bash
# test_serial_silence.sh -- M18-SW1.1 host-side test for Task B serial silence.
#
# Proves, with REAL background-subprocess file descriptors (not a mock, not just
# bash -n), that scripts/run_ui_live.sh redirects the UI server's stdin -> /dev/null
# and stdout+stderr -> the log file, so the control serial console sees at most the
# single UI_LIVE_READY line -- never the server's periodic UI_STATS / UI_CTL /
# TOUCH_CONTROL_STATS output.
#
# How: it installs a FAKE board_ui_live_12class (a shell stub that prints the same
# UI_LIVE_READY + periodic stats lines the real server prints, on both stdout and
# stderr), points the REAL run_ui_live.sh at it via BIN_DIR + UI_RUN_DIR, launches
# run_ui_live.sh, and then reads the live subprocess's /proc/<pid>/fd/{0,1,2}
# targets.  It also asserts the launcher's own stdout/stderr carry NONE of the
# periodic lines while the log file carries ALL of them (including a stderr-only
# marker, proving 2>&1 merged stderr into the log).
#
# Requires a real Linux /proc (WSL, Linux, or the board).  On a host without
# /proc/PID/fd (e.g. Git Bash on Windows) the fd checks FAIL CLOSED so this test is
# never mistaken for a real verification.
#
# Run from the package root:  bash scripts/test_serial_silence.sh
# Exit 0 = ALL CHECKS PASSED.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_LIVE="$SCRIPT_DIR/run_ui_live.sh"
GUARD="$SCRIPT_DIR/process_guard.sh"
PASS=0
FAIL=0

ok()  { PASS=$((PASS+1)); echo "  ok  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $1"; }
section() { echo "== $1 =="; }

TMP="$(mktemp -d)"
SERVER_PID=""
LAUNCH_PID=""
cleanup() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then kill "$SERVER_PID" 2>/dev/null || true; fi
    if [ -n "$LAUNCH_PID" ] && kill -0 "$LAUNCH_PID" 2>/dev/null; then kill "$LAUNCH_PID" 2>/dev/null || true; fi
    rm -rf "$TMP"
}
trap cleanup EXIT

FAKE_BIN="$TMP/bin/board_ui_live_12class"
RUN_DIR="$TMP/run"
LOG_FILE="$RUN_DIR/ui_live.log"
PID_FILE="$RUN_DIR/ui_live.pid"
LAUNCH_OUT="$TMP/launcher.out"

# ---- fake server (mirrors the real server's stdout/stderr contract) -----------
mkdir -p "$TMP/bin"
cat > "$FAKE_BIN" <<'FAKE'
#!/usr/bin/env bash
# Fake board_ui_live_12class: prints the same lines the real server prints, on
# stdout and stderr, and keeps running until SIGTERM.  It creates no socket and
# holds no framebuffer -- it exists only so the test can inspect the live
# subprocess's redirected file descriptors.
trap 'exit 0' TERM INT
echo "UI_LIVE_READY sock=fake"
while true; do
    echo "UI_STATS received=1 valid=1 rejected=0 rendered=1 coalesced=0 last_frame_id=1"
    echo "UI_CTL status=CONNECTED sock=/run/sdr_amr_control.sock"
    echo "TOUCH_CONTROL_STATS control_taps=0 commands_sent=0 commands_applied=0 commands_rejected=0 commands_timeout=0 duplicate_commands=0 connected=1"
    echo "FAKE_STDERR_MARKER this-must-go-to-log" >&2
    sleep 0.1
done
FAKE
chmod +x "$FAKE_BIN"

section "0. syntax: bash -n"
for f in "$UI_LIVE" "$GUARD"; do
    if bash -n "$f"; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")"; fi
done

section "1. /proc/PID/fd availability (required for a REAL fd check)"
if [ -d /proc ] && [ -d "/proc/$$/fd" ] && [ -L "/proc/$$/fd/1" ]; then
    ok "/proc/PID/fd available (Linux/WSL/board)"
    HAVE_PROC=1
else
    bad "/proc/PID/fd not available -- serial-silence fd verification requires Linux (WSL or board)"
    HAVE_PROC=0
fi

if [ "$HAVE_PROC" = "1" ]; then
    section "2. launch the REAL run_ui_live.sh with a fake server"
    BIN_DIR="$TMP/bin" UI_RUN_DIR="$RUN_DIR" \
        "$UI_LIVE" --sock="$TMP/ui.sock" >"$LAUNCH_OUT" 2>&1 &
    LAUNCH_PID=$!

    # run_ui_live.sh writes the PID file right after the nohup launch.
    i=0
    while [ ! -f "$PID_FILE" ] && [ "$i" -lt 50 ]; do
        sleep 0.1
        i=$((i+1))
    done
    if [ -f "$PID_FILE" ]; then
        SERVER_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
        ok "launcher wrote PID file (pid=$SERVER_PID)"
    else
        bad "launcher never wrote PID file"
    fi

    section "3. REAL fd targets of the live background server"
    if [ -n "$SERVER_PID" ] && [ -d "/proc/$SERVER_PID/fd" ]; then
        FD0="$(readlink "/proc/$SERVER_PID/fd/0" 2>/dev/null || true)"
        FD1="$(readlink "/proc/$SERVER_PID/fd/1" 2>/dev/null || true)"
        FD2="$(readlink "/proc/$SERVER_PID/fd/2" 2>/dev/null || true)"
        if [ "$FD0" = "/dev/null" ]; then ok "stdin (fd/0) -> /dev/null"; else bad "stdin (fd/0) = '$FD0', want /dev/null"; fi
        if [ "$FD1" = "$LOG_FILE" ]; then ok "stdout (fd/1) -> log file"; else bad "stdout (fd/1) = '$FD1', want $LOG_FILE"; fi
        if [ "$FD2" = "$LOG_FILE" ]; then ok "stderr (fd/2) -> log file"; else bad "stderr (fd/2) = '$FD2', want $LOG_FILE"; fi
    else
        bad "could not read /proc/$SERVER_PID/fd (PID file '$SERVER_PID')"
    fi

    # Let the fake emit several periodic lines into the log.
    sleep 0.6

    section "4. terminal silence vs log capture"
    # The launcher's own stdout/stderr must carry NONE of the periodic server lines.
    for pat in 'UI_STATS' 'UI_CTL status=' 'TOUCH_CONTROL_STATS' 'FAKE_STDERR_MARKER'; do
        if grep -qF -- "$pat" "$LAUNCH_OUT"; then bad "launcher stdout leaked '$pat' to the terminal"; else ok "launcher stdout silent for '$pat'"; fi
    done
    # The log file must carry the periodic server lines (stdout AND stderr merged).
    for pat in 'UI_LIVE_READY' 'UI_STATS' 'UI_CTL status=' 'TOUCH_CONTROL_STATS' 'FAKE_STDERR_MARKER'; do
        if grep -qF -- "$pat" "$LOG_FILE"; then ok "log captured '$pat'"; else bad "log missing '$pat'"; fi
    done

    section "5. at most one UI_LIVE_READY on the terminal (smoke)"
    # run_ui_live.sh echoes UI_LIVE_READY at most once (success path).  With a
    # socketless fake it never reaches that path, so it must print 0 (never a
    # periodic/duplicate UI_LIVE_READY).  The authoritative "at most one" is by
    # code inspection: board_ui_live_12class.cpp:346 (print once, before the loop)
    # + run_ui_live.sh:51 (echo once, then exit 0).
    NL="$(grep -c '^UI_LIVE_READY' "$LAUNCH_OUT" 2>/dev/null || true)"
    if [ "$NL" -le 1 ]; then ok "launcher printed <=1 UI_LIVE_READY ($NL)"; else bad "launcher printed $NL UI_LIVE_READY lines"; fi

    # ---- ordered shutdown: stop the fake server first, then the launcher ----
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    sleep 0.5
    if [ -n "$LAUNCH_PID" ] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
        kill "$LAUNCH_PID" 2>/dev/null || true
    fi
    wait "$LAUNCH_PID" 2>/dev/null || true
fi

echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
