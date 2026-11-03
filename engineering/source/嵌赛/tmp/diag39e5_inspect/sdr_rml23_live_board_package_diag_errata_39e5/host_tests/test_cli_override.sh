#!/usr/bin/env bash
# test_cli_override.sh -- end-to-end proof that the run scripts' --key=value
# defaults are OVERRIDDEN by a user's post-script args (the "later occurrence
# wins" rule), and that malformed values fail closed (non-zero exit).
#
# It builds test_cli_harness (a stand-in gate binary that echoes parsed args),
# then (a) exercises the parser directly, and (b) runs scripts/run_gate6.sh with
# BIN_DIR pointed at the harness to prove the override on a real script.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter"
mkdir -p bin

echo "== build test_cli_harness =="
$CXX $FLAGS test_cli_harness.cpp -o bin/test_cli_harness

fails=0

# (1) --key=value and --key value parse to the SAME result.
eq_out="$(./bin/test_cli_harness --loopback=1 --frames=32)"
sp_out="$(./bin/test_cli_harness --loopback 1 --frames 32)"
if [ "$eq_out" != "$sp_out" ]; then
    echo "FAIL: --key=value and --key value differ" >&2
    echo "  eq: $eq_out" >&2
    echo "  sp: $sp_out" >&2
    fails=1
fi

# (2) Later occurrence overrides an earlier one.
ov_out="$(./bin/test_cli_harness --loopback=0 --loopback=1)"
case "$ov_out" in
    *"loopback=1"*) ;;
    *) echo "FAIL: later --loopback=1 did not override earlier --loopback=0" >&2; fails=1;;
esac

# (3) Fail-closed: missing / empty / invalid values must exit non-zero.
if ./bin/test_cli_harness --frames >/dev/null 2>&1; then
    echo "FAIL: missing value (--frames at end) should exit non-zero" >&2; fails=1
fi
if ./bin/test_cli_harness --frames --loopback=1 >/dev/null 2>&1; then
    echo "FAIL: missing value (--frames then --flag) should exit non-zero" >&2; fails=1
fi
if ./bin/test_cli_harness --frames= >/dev/null 2>&1; then
    echo "FAIL: empty value (--frames=) should exit non-zero" >&2; fails=1
fi
if ./bin/test_cli_harness --frames=abc >/dev/null 2>&1; then
    echo "FAIL: invalid integer (--frames=abc) should exit non-zero" >&2; fails=1
fi
if ./bin/test_cli_harness --rec-scale=nope >/dev/null 2>&1; then
    echo "FAIL: invalid float (--rec-scale=nope) should exit non-zero" >&2; fails=1
fi

# (4) End-to-end: user args override the run_gate6.sh script defaults.
tmpdir="$(mktemp -d)"
cp bin/test_cli_harness "$tmpdir/board_gate6_sdr_preprocess"
out="$(BIN_DIR="$tmpdir" ../scripts/run_gate6.sh --loopback=1 --frames=32 2>&1 || true)"
case "$out" in
    *"loopback=1"*"frames=32"*)
        ;;
    *)
        echo "FAIL: user args did not override run_gate6.sh defaults" >&2
        echo "$out" >&2
        fails=1
        ;;
esac
rm -rf "$tmpdir"

if [ "$fails" -eq 0 ]; then
    echo "test_cli_override.sh: PASSED"
    exit 0
else
    echo "test_cli_override.sh: FAILED" >&2
    exit 1
fi
