#!/usr/bin/env bash
# test_m17_touch_acceptance.sh -- host-side shell test for
# scripts/run_m17_touch_acceptance.sh (M17.1 Task D).
#
# Verifies the 14 consistency-checked behaviors of the touch-acceptance
# orchestration script, WITHOUT touching the board or any real binary:
#   * `bash -n` syntax check of the orchestrator;
#   * static source-order + flag + fail-closed checks (behaviors 1-14);
#   * sourced-library unit tests of the rec_scale parse/resolve helpers
#     (behaviors 6/7/8), including the "never silently 1.0" guarantee.
#
# Run from anywhere inside the package; exit 0 = ALL CHECKS PASSED.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/run_m17_touch_acceptance.sh"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); echo "  ok  $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  FAIL $1"; }

banner() { echo "== $1 =="; }

# grep the target; returns 0 if pattern present.
has() { grep -qE -- "$1" "$TARGET"; }

# line number of first match (or 0).
lineno() { grep -nE -- "$1" "$TARGET" | head -n 1 | cut -d: -f1; }

banner "0. syntax: bash -n"
if bash -n "$TARGET"; then ok "bash -n run_m17_touch_acceptance.sh"; else bad "bash -n run_m17_touch_acceptance.sh"; fi

banner "1/4. UI-first ordering (UI before producer)"
UI_LINE="$(lineno 'scripts/run_ui_live\.sh"')"
GW_LINE="$(lineno 'scripts/run_gate9_ui\.sh"')"
if [ -n "$UI_LINE" ] && [ -n "$GW_LINE" ] && [ "$UI_LINE" -lt "$GW_LINE" ]; then
    ok "run_ui_live.sh invoked before run_gate9_ui.sh ($UI_LINE < $GW_LINE)"
else
    bad "UI-first ordering (ui=$UI_LINE gate9=$GW_LINE)"
fi

banner "2. UI readiness wait (fail-closed)"
if has 'wait_for_socket "\$UI_SOCK"'; then ok "waits for UI data socket"; else bad "UI socket wait"; fi

banner "3. digital producer (offline rejected as producer)"
if has '--phase=digital'; then ok "producer uses --phase=digital"; else bad "producer --phase=digital"; fi
OFFLINE_REF="$(grep -nE -- '--phase=offline' "$TARGET" | grep -vE '^[0-9]+:[[:space:]]*#' || true)"
if [ -z "$OFFLINE_REF" ]; then
    ok "--phase=offline never used as a live argument"
else
    bad "--phase=offline used outside a comment: $OFFLINE_REF"
fi

banner "4. producer-after-UI (gate9 launched only after UI wait)"
WAIT_UI_LINE="$(lineno 'wait_for_socket "\$UI_SOCK"')"
if [ -n "$WAIT_UI_LINE" ] && [ -n "$GW_LINE" ] && [ "$WAIT_UI_LINE" -lt "$GW_LINE" ]; then
    ok "UI wait precedes producer launch ($WAIT_UI_LINE < $GW_LINE)"
else
    bad "producer-after-UI order (wait=$WAIT_UI_LINE gate9=$GW_LINE)"
fi

banner "5. control-socket wait (fail-closed)"
if has 'wait_for_socket "\$CTL_SOCK"'; then ok "waits for control socket"; else bad "control socket wait"; fi

banner "6. rec_scale.txt resolution + fail-closed"
if has 'rec_scale\.txt not found'; then ok "fail-closed message on missing rec_scale.txt"; else bad "rec_scale.txt fail-closed"; fi
if has '\$ROOT/rec_scale\.txt'; then ok "falls back to package-root rec_scale.txt"; else bad "package-root rec_scale.txt"; fi

banner "7. --rec-scale override wins over file"
if has '--rec-scale='; then ok "--rec-scale= arg accepted"; else bad "--rec-scale= arg"; fi
if has 'REC_SCALE_OVERRIDE'; then ok "override precedence branch present"; else bad "override precedence"; fi

banner "8. rec_scale.txt format parse (never silent 1.0)"
if has 'rec_scale=<value>'; then ok "documents rec_scale=<value> format"; else bad "format documented"; fi
if has '\+0\) > 0'; then ok "strictly-positive value check present"; else bad "positivity check"; fi

banner "9. rec_scale forwarded to producer"
if has '--rec-scale="\$REC_SCALE"'; then ok "resolved rec_scale forwarded"; else bad "rec_scale forwarding"; fi

banner "10. --producer-frames override"
if has '--producer-frames='; then ok "--producer-frames= arg accepted"; else bad "--producer-frames= arg"; fi
if has '--frames="\$PRODUCER_FRAMES"'; then ok "producer frames forwarded"; else bad "producer frames forwarding"; fi

banner "11. --ui-sock / --control-sock override"
if has '--ui-sock='; then ok "--ui-sock= arg accepted"; else bad "--ui-sock= arg"; fi
if has '--control-sock='; then ok "--control-sock= arg accepted"; else bad "--control-sock= arg"; fi
if has '--ctl-sock="\$CTL_SOCK"'; then ok "control sock forwarded to producer"; else bad "ctl-sock forwarding"; fi

banner "12. --timeout override"
if has '--timeout='; then ok "--timeout= arg accepted"; else bad "--timeout= arg"; fi
if has '\+ TIMEOUT'; then ok "timeout honored in socket wait"; else bad "timeout in wait"; fi
if has '--timeout="\$TIMEOUT"'; then ok "timeout forwarded to touch test"; else bad "timeout forwarding"; fi

banner "13. log directory"
if has 'LOG_DIR="/tmp/m17_touch_acceptance"'; then ok "log dir set to /tmp/m17_touch_acceptance"; else bad "log dir"; fi

banner "14. verdict delegation + result line"
if has 'test_touch_mode_control\.sh'; then ok "delegates to test_touch_mode_control.sh"; else bad "verdict delegation"; fi
if has 'M17_TOUCH_ACCEPTANCE result=PASS'; then ok "emits M17_TOUCH_ACCEPTANCE result=PASS"; else bad "result=PASS line"; fi
if has 'M17_TOUCH_ACCEPTANCE result=FAIL'; then ok "emits M17_TOUCH_ACCEPTANCE result=FAIL"; else bad "result=FAIL line"; fi

banner "15. sourced-library unit tests (rec_scale parse/resolve)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Library-mode source: defines helpers without running main.
RUN_M17_TOUCH_ACCEPTANCE_LIB=1 . "$TARGET"
# The sourced script sets `set -euo pipefail`; relax back to `set -u` so failed
# parse/resolve assertions below can be inspected without aborting the test.
set +e
set +o pipefail
set -u

# [8] parse a good file
printf 'rec_scale=1.365333\n' > "$TMP/good.txt"
GOT="$(parse_rec_scale_file "$TMP/good.txt")"
if [ "$GOT" = "1.365333" ]; then ok "parse_rec_scale_file good -> 1.365333"; else bad "parse good (got '$GOT')"; fi

# [8] reject malformed / missing value / zero
if ! parse_rec_scale_file "$TMP/missing.txt" 2>/dev/null; then ok "parse_rec_scale_file missing -> fail"; else bad "parse missing"; fi
printf 'rec_scale=\n' > "$TMP/empty.txt"
if ! parse_rec_scale_file "$TMP/empty.txt" 2>/dev/null; then ok "parse empty value -> fail"; else bad "parse empty"; fi
printf 'rec_scale=0\n' > "$TMP/zero.txt"
if ! parse_rec_scale_file "$TMP/zero.txt" 2>/dev/null; then ok "parse zero -> fail (never 1.0)"; else bad "parse zero"; fi
printf 'rec_scale=1.0\ngarbage\n' > "$TMP/multiline.txt"
# (the last matching rec_scale= line wins, but garbage line must not be accepted as a rec_scale value)
if parse_rec_scale_file "$TMP/multiline.txt" >/dev/null 2>&1; then ok "parse multiline still yields a value"; else bad "parse multiline"; fi

# [7] override wins over a bad/missing file
REC_SCALE_OVERRIDE="4.096"
if [ "$(resolve_rec_scale)" = "4.096" ]; then ok "resolve_rec_scale override -> 4.096"; else bad "resolve override"; fi
REC_SCALE_OVERRIDE="0"
if ! resolve_rec_scale 2>/dev/null; then ok "resolve_rec_scale override 0 -> fail"; else bad "resolve override 0"; fi
REC_SCALE_OVERRIDE=""

# [6] current-dir-first, then package root
mkdir -p "$TMP/cwd" "$TMP/root"
printf 'rec_scale=2.5\n' > "$TMP/cwd/rec_scale.txt"
printf 'rec_scale=9.9\n' > "$TMP/root/rec_scale.txt"
if [ "$(cd "$TMP/cwd" && ROOT="$TMP/root" resolve_rec_scale)" = "2.5" ]; then
    ok "resolve_rec_scale prefers current-dir (2.5 over root 9.9)"
else
    bad "resolve current-dir-first"
fi
rm -f "$TMP/cwd/rec_scale.txt"
if [ "$(cd "$TMP/cwd" && ROOT="$TMP/root" resolve_rec_scale)" = "9.9" ]; then
    ok "resolve_rec_scale falls back to package root (9.9)"
else
    bad "resolve package-root fallback"
fi

# [6] fail-closed when neither present
mkdir -p "$TMP/emptyroot"
if (cd "$TMP/cwd" && ROOT="$TMP/emptyroot" && resolve_rec_scale) >/dev/null 2>&1; then
    bad "resolve_rec_scale missing everywhere -> should fail"
else
    ok "resolve_rec_scale missing everywhere -> fail"
fi

echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
