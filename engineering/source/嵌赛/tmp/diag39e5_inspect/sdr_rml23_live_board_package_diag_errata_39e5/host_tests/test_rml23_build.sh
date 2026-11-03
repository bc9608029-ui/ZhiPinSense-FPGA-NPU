#!/usr/bin/env bash
# test_rml23_build.sh -- host tests for the RML23 (M29 F5) build + package wiring:
#   (A) CMakeLists.txt exposes BUILD_GATE9_RML23 and defines board_gate9_full_chain
#       _rml23 inside that guard (never the 12-class gate9 target);
#   (B) build_npu_on_board.sh --gate9-rml23 fails closed without LIBIIO_ROOT, uses
#       an ISOLATED build_gate9_rml23 dir, installs bin/board_gate9_full_chain_rml23,
#       and prints NPU_BUILD_RESULT gate=9R result=PASS;
#   (C) build_ui_live_rml23.sh builds ONLY board_ui_live_rml23 (never overwriting
#       board_ui_live_12class / board_mode_ctl);
#   (D) common_rml23.sh resolves the frozen model paths + raw SHA, and
#       verify_package.sh rejects a corrupted model (SHA fail-closed).
#
# Run under WSL/Linux.  No libiio or iCraft toolchain is required: it uses fake
# cmake / make / nproc / g++ stubs (recording argv, one per line), exactly like
# test_board_build.sh.
set -u
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
BP="$ROOT/board_package"

pass=0
fail=0
note() { echo "== $* =="; }
ok()   { echo "  ok   $*"; pass=$((pass + 1)); }
bad()  { echo "  FAIL $*"; fail=$((fail + 1)); }

FAKEBIN=""
FAKE_LOG=""
TMPDIRS=()
cleanup() { for d in "${TMPDIRS[@]:-}"; do [ -n "$d" ] && rm -rf "$d"; done; }
trap cleanup EXIT

make_fakebin() {
    FAKEBIN="$(mktemp -d)"; TMPDIRS+=("$FAKEBIN")
    FAKE_LOG="$FAKEBIN/args.log"
    cat > "$FAKEBIN/cmake" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >> "${FAKE_LOG:?}"
exit 0
EOF
    cat > "$FAKEBIN/make" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >> "${FAKE_LOG:?}"
if [ -n "${FAKE_MAKE_FAIL:-}" ]; then exit 1; fi
tgt=""
for a in "$@"; do tgt="$a"; done
if [ -n "$tgt" ] && [ "${tgt#-}" = "$tgt" ]; then : > "$tgt"; fi
exit 0
EOF
    cat > "$FAKEBIN/g++" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >> "${FAKE_LOG:?}"
# Create the -o output so a subsequent `mv` in the build script succeeds.
out=""; prev=""
for a in "$@"; do
    [ "$prev" = "-o" ] && out="$a"
    prev="$a"
done
[ -n "$out" ] && : > "$out"
exit 0
EOF
    cat > "$FAKEBIN/nproc" <<'EOF'
#!/usr/bin/env bash
echo 4
EOF
    chmod +x "$FAKEBIN/cmake" "$FAKEBIN/make" "$FAKEBIN/g++" "$FAKEBIN/nproc"
    export FAKE_LOG
}

make_libiio() {
    local dir="$1"
    mkdir -p "$dir/include" "$dir/lib"
    : > "$dir/include/iio.h"
    : > "$dir/lib/libiio.so"
}

make_sandbox() {
    local s; s="$(mktemp -d)"; TMPDIRS+=("$s")
    mkdir -p "$s/board_package" "$s/sdr_adapter"
    cp "$BP"/*.cpp "$BP"/*.hpp "$BP"/*.sh "$BP"/CMakeLists.txt "$s/board_package/"
    cp "$ROOT/sdr_adapter"/*.hpp "$ROOT/sdr_adapter"/*.cpp "$ROOT/sdr_adapter"/*.h "$s/sdr_adapter/"
    printf '%s\n' "$s"
}

note "T1: CMakeLists.txt exposes BUILD_GATE9_RML23 and guards the RML23 target"
g9r_opt=$(grep -n 'option(BUILD_GATE9_RML23' "$BP/CMakeLists.txt" | head -1 | cut -d: -f1)
g9r_tgt=$(grep -n 'add_executable(board_gate9_full_chain_rml23' "$BP/CMakeLists.txt" | head -1 | cut -d: -f1)
g9r_guard=$(grep -n 'if(BUILD_GATE9_RML23)' "$BP/CMakeLists.txt" | head -1 | cut -d: -f1)
g9_tgt=$(grep -n 'add_executable(board_gate9_full_chain_12class' "$BP/CMakeLists.txt" | head -1 | cut -d: -f1)
if [ -n "$g9r_opt" ] && [ -n "$g9r_tgt" ] && [ -n "$g9r_guard" ] \
   && [ "$g9r_guard" -lt "$g9r_tgt" ] \
   && [ "$g9_tgt" != "$g9r_tgt" ]; then
    ok "BUILD_GATE9_RML23 option (line $g9r_opt); target line $g9r_tgt after guard line $g9r_guard; distinct from 12-class target"
else
    bad "unexpected ordering (opt=$g9r_opt target=$g9r_tgt guard=$g9r_guard g9_tgt=$g9_tgt)"
fi

make_fakebin

note "T2: --gate9-rml23 without LIBIIO_ROOT fails closed before cmake"
S=$(make_sandbox)
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate9-rml23 ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ] && [ ! -s "$FAKE_LOG" ]; then
    ok "--gate9-rml23 without LIBIIO_ROOT: non-zero exit, cmake never invoked"
else
    bad "--gate9-rml23 without LIBIIO_ROOT: rc=$rc, cmake invoked=$([ -s "$FAKE_LOG" ] && echo yes || echo no)"
fi

note "T3: --gate9-rml23 with LIBIIO_ROOT drives cmake args + isolated dir + install"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" \
    ./board_package/build_npu_on_board.sh --gate9-rml23 ) >"$S/out" 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && grep -Fxq -- '-DBUILD_GATE9_RML23=ON' "$FAKE_LOG" \
   && grep -Fxq -- "-DLIBIIO_ROOT=$iio" "$FAKE_LOG" \
   && grep -Fq -- 'board_gate9_full_chain_rml23' "$FAKE_LOG" \
   && [ -f "$S/bin/board_gate9_full_chain_rml23" ] \
   && [ -d "$S/board_package/build_gate9_rml23" ] \
   && [ ! -e "$S/board_package/build_gate9" ] \
   && grep -Fq "NPU_BUILD_RESULT gate=9R result=PASS binary=$S/bin/board_gate9_full_chain_rml23" "$S/out"; then
    ok "--gate9-rml23: cmake -DBUILD_GATE9_RML23=ON, isolated build_gate9_rml23, bin installed, gate=9R PASS printed"
else
    bad "--gate9-rml23: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

note "T4: build_ui_live_rml23.sh builds board_ui_live_rml23 only, installs to bin/"
S=$(make_sandbox)
# Pre-place the 12-class products to prove the RML23 build never touches them.
mkdir -p "$S/bin"; : > "$S/bin/board_ui_live_12class"; : > "$S/bin/board_mode_ctl"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_ui_live_rml23.sh "$FAKEBIN/g++" ) >"$S/out" 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && [ -f "$S/bin/board_ui_live_rml23" ] \
   && [ -f "$S/bin/board_ui_live_12class" ] \
   && [ -f "$S/bin/board_mode_ctl" ] \
   && grep -Fq 'board_ui_live_rml23.cpp' "$FAKE_LOG" \
   && ! grep -Fq 'board_ui_live_12class.cpp' "$FAKE_LOG" \
   && ! grep -Fq 'board_mode_ctl.cpp' "$FAKE_LOG" \
   && grep -Fq "UI_BUILD_RESULT result=PASS binary=$S/bin/board_ui_live_rml23" "$S/out"; then
    ok "build_ui_live_rml23.sh: RML23 target only; 12-class UI + mode_ctl preserved; PASS printed"
else
    bad "build_ui_live_rml23.sh: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

note "T5: common_rml23.sh resolves frozen model paths + raw SHA"
FROZEN_RAW="2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"
out=$( ( . "$ROOT/scripts/common_rml23.sh" >/dev/null 2>&1; \
        printf '%s\n%s\n%s\n' "$MODEL_JSON" "$MODEL_RAW" "$MODEL_RAW_SHA" ) )
mj=$(echo "$out" | sed -n 1p); mr=$(echo "$out" | sed -n 2p); msha=$(echo "$out" | sed -n 3p)
if [ "$msha" = "$FROZEN_RAW" ] \
   && [ "$mj" = "$ROOT/model_rml23/model_24class_ZG.json" ] \
   && [ "$mr" = "$ROOT/model_rml23/model_24class_ZG.raw" ]; then
    ok "common_rml23.sh: MODEL_RAW_SHA=$msha, paths correct"
else
    bad "common_rml23.sh: sha='$msha' json='$mj' raw='$mr'"
fi

note "T7: scripts/build_on_board.sh is the single RML23 build entry (producer + UI)"
BOB="$ROOT/scripts/build_on_board.sh"
if [ -x "$BOB" ] \
   && grep -Fq -- '--gate9-rml23' "$BOB" \
   && grep -Fq 'build_ui_live_rml23.sh' "$BOB" \
   && grep -Fq 'RML23_BUILD_RESULT result=PASS' "$BOB"; then
    ok "build_on_board.sh: drives --gate9-rml23 + build_ui_live_rml23.sh, prints RML23_BUILD_RESULT"
else
    bad "build_on_board.sh: missing or does not drive both RML23 builds"
fi

note "T6: verify_package.sh rejects a corrupted model (fail-closed)"
S=$(make_sandbox)
mkdir -p "$S/model_rml23" "$S/contracts" "$S/scripts"
cp "$ROOT/model_rml23"/model_24class_ZG.json "$ROOT/model_rml23"/model_24class_ZG.raw \
   "$ROOT/model_rml23"/model_rml23.sha256 "$S/model_rml23/"
cp "$ROOT/contracts"/rml23_merged_contract.py "$S/contracts/"
cp "$ROOT/scripts"/verify_package.sh "$ROOT/scripts"/verify_rml23_contract.py "$S/scripts/"
# Corrupt the raw weights: SHA must now mismatch and verify_package.sh must exit non-zero.
printf 'corrupt' >> "$S/model_rml23/model_24class_ZG.raw"
( cd "$S" && bash scripts/verify_package.sh ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then
    ok "verify_package.sh: corrupted model raw -> non-zero exit (SHA rejection)"
else
    bad "verify_package.sh: corrupted model raw -> rc=$rc (expected non-zero)"
fi

echo
echo "test_rml23_build.sh: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
