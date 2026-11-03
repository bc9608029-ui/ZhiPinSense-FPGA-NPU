#!/usr/bin/env bash
# test_board_build.sh -- host tests for the board BUILD fixes:
#   (A) dependency fix: Gate 7 config path needs no pkg-config / libiio; explicit
#       LIBIIO_ROOT drives Gate 6 / Gate 9 flags; a broken LIBIIO_ROOT fails
#       closed; paths with spaces stay correctly quoted.
#   (B) directory fix: Gate 7 / Gate 9 build in ISOLATED directories (build_gate7/
#       vs build_gate9/), each successful build auto-installs its binary into the
#       package top-level bin/, and a failed build never deletes the other gate's
#       product nor leaves a stale binary masquerading as success.
#
# Run under WSL/Linux.  No libiio or iCraft toolchain is required: it uses fake
# cmake / make / nproc / g++ stubs.  cmake/make/nproc/g++ record their argv (one
# per line, so arguments with spaces stay unambiguous); fake make also CREATES its
# target file (and can be told to fail via FAKE_MAKE_FAIL) so the build scripts'
# real directory + copy behavior is exercised.
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

cleanup() {
    for d in "${TMPDIRS[@]:-}"; do [ -n "$d" ] && rm -rf "$d"; done
}
trap cleanup EXIT

# ---- fake toolchain: cmake/make/nproc/g++ record argv; make creates its target ----
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
if [ -n "${FAKE_MAKE_FAIL:-}" ]; then
    exit 1
fi
tgt=""
for a in "$@"; do tgt="$a"; done
if [ -n "$tgt" ] && [ "${tgt#-}" = "$tgt" ]; then
    : > "$tgt"
fi
exit 0
EOF
    cat > "$FAKEBIN/g++" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >> "${FAKE_LOG:?}"
exit 0
EOF
    cat > "$FAKEBIN/nproc" <<'EOF'
#!/usr/bin/env bash
echo 4
EOF
    chmod +x "$FAKEBIN/cmake" "$FAKEBIN/make" "$FAKEBIN/g++" "$FAKEBIN/nproc"
    export FAKE_LOG
}

# ---- fake libiio prefix: optionally include/iio.h and/or lib/libiio.so ----
make_libiio() {
    local dir="$1" hdr="${2:-1}" lib="${3:-1}"
    mkdir -p "$dir/include" "$dir/lib"
    [ "$hdr" = "1" ] && : > "$dir/include/iio.h"
    [ "$lib" = "1" ] && : > "$dir/lib/libiio.so"
}

# ---- sandbox copy of board_package + sdr_adapter (scripts cd into board_package) ----
make_sandbox() {
    local s; s="$(mktemp -d)"; TMPDIRS+=("$s")
    mkdir -p "$s/board_package" "$s/sdr_adapter"
    cp "$BP"/*.cpp "$BP"/*.hpp "$BP"/*.sh "$BP"/CMakeLists.txt "$s/board_package/"
    cp "$ROOT/sdr_adapter"/*.hpp "$ROOT/sdr_adapter"/*.cpp "$ROOT/sdr_adapter"/*.h "$s/sdr_adapter/"
    printf '%s\n' "$s"
}

# ---------------------------------------------------------------------------
note "T1: CMakeLists.txt drops the PkgConfig hard dependency"
if grep -Eq 'find_package\(PkgConfig|pkg_check_modules' "$BP/CMakeLists.txt"; then
    bad "CMakeLists.txt still references PkgConfig / pkg_check_modules"
else
    ok "no PkgConfig / pkg_check_modules in CMakeLists.txt"
fi

note "T2: Gate 7 target is defined outside the BUILD_GATE9 libiio guard"
g7=$(grep -n 'add_executable(board_gate7_12class_npu' "$BP/CMakeLists.txt" | head -1 | cut -d: -f1)
gd=$(grep -n 'if(BUILD_GATE9)' "$BP/CMakeLists.txt" | head -1 | cut -d: -f1)
if [ -n "$g7" ] && [ -n "$gd" ] && [ "$g7" -lt "$gd" ]; then
    ok "board_gate7_12class_npu (line $g7) precedes if(BUILD_GATE9) (line $gd)"
else
    bad "unexpected ordering (gate7 line=$g7, guard line=$gd)"
fi

# ---------------------------------------------------------------------------
make_fakebin
S=$(make_sandbox)

note "T3: --gate7-only configures Gate 7 without libiio / pkg-config"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate7-only ) >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && grep -Fxq -- '-DBUILD_GATE9=OFF' "$FAKE_LOG" \
   && grep -Fq -- 'board_gate7_12class_npu' "$FAKE_LOG" \
   && ! grep -q -- '-DLIBIIO_ROOT' "$FAKE_LOG"; then
    ok "--gate7-only: exit 0, cmake got -DBUILD_GATE9=OFF + gate7 target, no -DLIBIIO_ROOT"
else
    bad "--gate7-only: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

note "T4: --gate9 without LIBIIO_ROOT fails closed before cmake"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate9 ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ] && [ ! -s "$FAKE_LOG" ]; then
    ok "--gate9 without LIBIIO_ROOT: non-zero exit, cmake never invoked"
else
    bad "--gate9 without LIBIIO_ROOT: rc=$rc, cmake invoked=$([ -s "$FAKE_LOG" ] && echo yes || echo no)"
fi

note "T5: --gate9 with LIBIIO_ROOT drives cmake args"
iio="$S/libiio"; make_libiio "$iio"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" \
    ./board_package/build_npu_on_board.sh --gate9 ) >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && grep -Fxq -- '-DBUILD_GATE9=ON' "$FAKE_LOG" \
   && grep -Fxq -- "-DLIBIIO_ROOT=$iio" "$FAKE_LOG" \
   && grep -Fq -- 'board_gate9_full_chain_12class' "$FAKE_LOG"; then
    ok "--gate9: cmake got -DBUILD_GATE9=ON + -DLIBIIO_ROOT, make got gate9 target"
else
    bad "--gate9: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

# ---------------------------------------------------------------------------
note "T6: build_on_board.sh explicit LIBIIO_ROOT -> -I/-L/-liio/-rpath"
iio="$S/libiio"; make_libiio "$iio"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" \
    ./board_package/build_on_board.sh "$FAKEBIN/g++" ) >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && grep -Fxq -- "-I$iio/include" "$FAKE_LOG" \
   && grep -Fxq -- "-L$iio/lib" "$FAKE_LOG" \
   && grep -Fxq -- '-liio' "$FAKE_LOG" \
   && grep -Fxq -- "-Wl,-rpath,$iio/lib" "$FAKE_LOG"; then
    ok "build_on_board.sh: g++ got -I<root>/include -L<root>/lib -liio -Wl,-rpath,<root>/lib"
else
    bad "build_on_board.sh: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

note "T7: build_on_board.sh missing header fails closed before compiling"
iio="$S/libiio_hdrless"; make_libiio "$iio" 0 1   # lib only, no iio.h
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" \
    ./board_package/build_on_board.sh "$FAKEBIN/g++" ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ] && [ ! -s "$FAKE_LOG" ]; then
    ok "missing include/iio.h: non-zero exit, g++ never invoked"
else
    bad "missing include/iio.h: rc=$rc, g++ invoked=$([ -s "$FAKE_LOG" ] && echo yes || echo no)"
fi

note "T8: build_on_board.sh missing library fails closed before compiling"
iio="$S/libiio_libless"; make_libiio "$iio" 1 0   # header only, no libiio.so
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" \
    ./board_package/build_on_board.sh "$FAKEBIN/g++" ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ] && [ ! -s "$FAKE_LOG" ]; then
    ok "missing lib/libiio.so: non-zero exit, g++ never invoked"
else
    bad "missing lib/libiio.so: rc=$rc, g++ invoked=$([ -s "$FAKE_LOG" ] && echo yes || echo no)"
fi

# ---------------------------------------------------------------------------
note "T9: require_libiio_runtime fails closed / sets LD_LIBRARY_PATH"
( . "$ROOT/scripts/common.sh"; LIBIIO_ROOT="$S/nope" require_libiio_runtime ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then
    ok "broken LIBIIO_ROOT -> require_libiio_runtime non-zero"
else
    bad "broken LIBIIO_ROOT -> rc=$rc (expected non-zero)"
fi
iio="$S/libiio"; make_libiio "$iio"
out=$( ( . "$ROOT/scripts/common.sh"; LIBIIO_ROOT="$iio" require_libiio_runtime; \
          printf '%s' "$LD_LIBRARY_PATH" ) 2>/dev/null )
if [ "$out" = "$iio/lib" ]; then
    ok "good LIBIIO_ROOT -> LD_LIBRARY_PATH=$iio/lib"
else
    bad "good LIBIIO_ROOT -> LD_LIBRARY_PATH='$out' (expected '$iio/lib')"
fi

note "T10: LIBIIO_ROOT with spaces stays one argument (build_on_board.sh)"
iio="$S/lib iio root"; make_libiio "$iio"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" \
    ./board_package/build_on_board.sh "$FAKEBIN/g++" ) >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && grep -Fxq -- "-I$iio/include" "$FAKE_LOG" \
   && grep -Fxq -- "-Wl,-rpath,$iio/lib" "$FAKE_LOG"; then
    ok "space path: -I/-rpath preserved as single args"
else
    bad "space path: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

# ---------------------------------------------------------------------------
# Directory-isolation + auto-install regression (directory fix).
# ---------------------------------------------------------------------------

note "T11: --gate7-only touches only build_gate7 (not build_gate9/build), installs bin/"
S=$(make_sandbox)
mkdir -p "$S/board_package/build_gate9"; : > "$S/board_package/build_gate9/sentinel"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate7-only ) >"$S/out" 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && [ -f "$S/bin/board_gate7_12class_npu" ] \
   && [ -f "$S/board_package/build_gate9/sentinel" ] \
   && [ -d "$S/board_package/build_gate7" ] \
   && [ ! -e "$S/board_package/build" ] \
   && grep -Fq "NPU_BUILD_RESULT gate=7 result=PASS binary=$S/bin/board_gate7_12class_npu" "$S/out"; then
    ok "--gate7-only: build_gate7 used, build_gate9 untouched, no build/, bin installed, PASS printed"
else
    bad "--gate7-only: rc=$rc; g9sent=$([ -f "$S/board_package/build_gate9/sentinel" ] && echo yes || echo no); bin=$([ -f "$S/bin/board_gate7_12class_npu" ] && echo yes || echo no); out=$(cat "$S/out")"
fi

note "T12: --gate9 touches only build_gate9 (not build_gate7/build), installs bin/"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
mkdir -p "$S/board_package/build_gate7"; : > "$S/board_package/build_gate7/sentinel"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" ./board_package/build_npu_on_board.sh --gate9 ) >"$S/out" 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && [ -f "$S/bin/board_gate9_full_chain_12class" ] \
   && [ -f "$S/board_package/build_gate7/sentinel" ] \
   && [ -d "$S/board_package/build_gate9" ] \
   && [ ! -e "$S/board_package/build" ] \
   && grep -Fq "NPU_BUILD_RESULT gate=9 result=PASS binary=$S/bin/board_gate9_full_chain_12class" "$S/out"; then
    ok "--gate9: build_gate9 used, build_gate7 untouched, no build/, bin installed, PASS printed"
else
    bad "--gate9: rc=$rc; g7sent=$([ -f "$S/board_package/build_gate7/sentinel" ] && echo yes || echo no); bin=$([ -f "$S/bin/board_gate9_full_chain_12class" ] && echo yes || echo no); out=$(cat "$S/out")"
fi

note "T13: Gate 7 then Gate 9 leaves both bin products"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate7-only ) >/dev/null 2>&1
rc1=$?
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" ./board_package/build_npu_on_board.sh --gate9 ) >/dev/null 2>&1
rc2=$?
if [ "$rc1" -eq 0 ] && [ "$rc2" -eq 0 ] \
   && [ -f "$S/bin/board_gate7_12class_npu" ] \
   && [ -f "$S/bin/board_gate9_full_chain_12class" ]; then
    ok "gate7->gate9: both bins present"
else
    bad "gate7->gate9: rc1=$rc1 rc2=$rc2; g7=$([ -f "$S/bin/board_gate7_12class_npu" ] && echo yes || echo no) g9=$([ -f "$S/bin/board_gate9_full_chain_12class" ] && echo yes || echo no)"
fi

note "T14: Gate 9 then Gate 7 leaves both bin products"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" ./board_package/build_npu_on_board.sh --gate9 ) >/dev/null 2>&1
rc1=$?
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate7-only ) >/dev/null 2>&1
rc2=$?
if [ "$rc1" -eq 0 ] && [ "$rc2" -eq 0 ] \
   && [ -f "$S/bin/board_gate9_full_chain_12class" ] \
   && [ -f "$S/bin/board_gate7_12class_npu" ]; then
    ok "gate9->gate7: both bins present"
else
    bad "gate9->gate7: rc1=$rc1 rc2=$rc2; g9=$([ -f "$S/bin/board_gate9_full_chain_12class" ] && echo yes || echo no) g7=$([ -f "$S/bin/board_gate7_12class_npu" ] && echo yes || echo no)"
fi

note "T15: Gate 9 build failure must NOT delete Gate 7 product"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate7-only ) >/dev/null 2>&1
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" FAKE_MAKE_FAIL=1 ./board_package/build_npu_on_board.sh --gate9 ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ] \
   && [ -f "$S/bin/board_gate7_12class_npu" ] \
   && [ ! -f "$S/bin/board_gate9_full_chain_12class" ]; then
    ok "gate9 fail: gate7 bin preserved, gate9 bin absent"
else
    bad "gate9 fail: rc=$rc; g7=$([ -f "$S/bin/board_gate7_12class_npu" ] && echo yes || echo no) g9=$([ -f "$S/bin/board_gate9_full_chain_12class" ] && echo yes || echo no)"
fi

note "T16: Gate 7 build failure must NOT delete Gate 9 product"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" ./board_package/build_npu_on_board.sh --gate9 ) >/dev/null 2>&1
( cd "$S" && PATH="$FAKEBIN:$PATH" FAKE_MAKE_FAIL=1 ./board_package/build_npu_on_board.sh --gate7-only ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ] \
   && [ -f "$S/bin/board_gate9_full_chain_12class" ] \
   && [ ! -f "$S/bin/board_gate7_12class_npu" ]; then
    ok "gate7 fail: gate9 bin preserved, gate7 bin absent"
else
    bad "gate7 fail: rc=$rc; g9=$([ -f "$S/bin/board_gate9_full_chain_12class" ] && echo yes || echo no) g7=$([ -f "$S/bin/board_gate7_12class_npu" ] && echo yes || echo no)"
fi

note "T17: a failed rebuild must NOT leave a stale same-gate binary (no masquerade)"
S=$(make_sandbox)
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate7-only ) >/dev/null 2>&1
if [ ! -f "$S/bin/board_gate7_12class_npu" ]; then
    bad "T17 setup: first gate7 build did not install bin"
else
    ( cd "$S" && PATH="$FAKEBIN:$PATH" FAKE_MAKE_FAIL=1 ./board_package/build_npu_on_board.sh --gate7-only ) >/dev/null 2>&1
    rc=$?
    if [ "$rc" -ne 0 ] && [ ! -f "$S/bin/board_gate7_12class_npu" ]; then
        ok "failed gate7 rebuild: stale bin removed (fail closed)"
    else
        bad "failed gate7 rebuild: rc=$rc; bin still present=$([ -f "$S/bin/board_gate7_12class_npu" ] && echo yes || echo no)"
    fi
fi

note "T18: both success paths print NPU_BUILD_RESULT result=PASS binary=<abs> and return 0"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate7-only ) >"$S/g7.out" 2>&1
rc1=$?
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" ./board_package/build_npu_on_board.sh --gate9 ) >"$S/g9.out" 2>&1
rc2=$?
if [ "$rc1" -eq 0 ] && [ "$rc2" -eq 0 ] \
   && grep -Fq "NPU_BUILD_RESULT gate=7 result=PASS binary=$S/bin/board_gate7_12class_npu" "$S/g7.out" \
   && grep -Fq "NPU_BUILD_RESULT gate=9 result=PASS binary=$S/bin/board_gate9_full_chain_12class" "$S/g9.out"; then
    ok "both success paths print NPU_BUILD_RESULT ... result=PASS with absolute binary path"
else
    bad "success prints: rc1=$rc1 rc2=$rc2"
fi

note "T19: failure paths print result=FAIL and return non-zero"
S=$(make_sandbox)
( cd "$S" && PATH="$FAKEBIN:$PATH" FAKE_MAKE_FAIL=1 ./board_package/build_npu_on_board.sh --gate7-only ) >"$S/f.out" 2>&1
rc=$?
if [ "$rc" -ne 0 ] && grep -Fq "NPU_BUILD_RESULT gate=7 result=FAIL" "$S/f.out"; then
    ok "failure: non-zero exit + NPU_BUILD_RESULT gate=7 result=FAIL"
else
    bad "failure: rc=$rc; out=$(cat "$S/f.out")"
fi

note "T20: --gate9 LIBIIO_ROOT with spaces stays one cmake argument"
S=$(make_sandbox)
iio="$S/lib iio root"; make_libiio "$iio"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" ./board_package/build_npu_on_board.sh --gate9 ) >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ] && grep -Fxq -- "-DLIBIIO_ROOT=$iio" "$FAKE_LOG"; then
    ok "space LIBIIO_ROOT: -DLIBIIO_ROOT passed as single arg (gate9)"
else
    bad "space LIBIIO_ROOT: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

# ---------------------------------------------------------------------------
# Gate 10 (M9): twelve-class RF self-test build wiring.
# ---------------------------------------------------------------------------

note "T21: --gate10 without LIBIIO_ROOT fails closed before cmake"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" ./board_package/build_npu_on_board.sh --gate10 ) >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ] && [ ! -s "$FAKE_LOG" ]; then
    ok "--gate10 without LIBIIO_ROOT: non-zero exit, cmake never invoked"
else
    bad "--gate10 without LIBIIO_ROOT: rc=$rc, cmake invoked=$([ -s "$FAKE_LOG" ] && echo yes || echo no)"
fi

note "T22: --gate10 with LIBIIO_ROOT drives cmake args"
iio="$S/libiio"; make_libiio "$iio"
: > "$FAKE_LOG"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" \
    ./board_package/build_npu_on_board.sh --gate10 ) >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && grep -Fxq -- '-DBUILD_GATE10=ON' "$FAKE_LOG" \
   && grep -Fxq -- "-DLIBIIO_ROOT=$iio" "$FAKE_LOG" \
   && grep -Fq -- 'board_gate10_selftest_12class' "$FAKE_LOG"; then
    ok "--gate10: cmake got -DBUILD_GATE10=ON + -DLIBIIO_ROOT, make got gate10 target"
else
    bad "--gate10: rc=$rc; args=$(tr '\n' ' ' < "$FAKE_LOG")"
fi

note "T23: --gate10 touches only build_gate10 (not build_gate7/build_gate9), installs bin/"
S=$(make_sandbox)
iio="$S/libiio"; make_libiio "$iio"
mkdir -p "$S/board_package/build_gate7";  : > "$S/board_package/build_gate7/sentinel"
mkdir -p "$S/board_package/build_gate9";  : > "$S/board_package/build_gate9/sentinel"
( cd "$S" && PATH="$FAKEBIN:$PATH" LIBIIO_ROOT="$iio" ./board_package/build_npu_on_board.sh --gate10 ) >"$S/out" 2>&1
rc=$?
if [ "$rc" -eq 0 ] \
   && [ -f "$S/bin/board_gate10_selftest_12class" ] \
   && [ -f "$S/board_package/build_gate7/sentinel" ] \
   && [ -f "$S/board_package/build_gate9/sentinel" ] \
   && [ -d "$S/board_package/build_gate10" ] \
   && [ ! -e "$S/board_package/build" ] \
   && grep -Fq "NPU_BUILD_RESULT gate=10 result=PASS binary=$S/bin/board_gate10_selftest_12class" "$S/out"; then
    ok "--gate10: build_gate10 used, gate7/gate9 untouched, no build/, bin installed, PASS printed"
else
    bad "--gate10: rc=$rc; g7sent=$([ -f "$S/board_package/build_gate7/sentinel" ] && echo yes || echo no); g9sent=$([ -f "$S/board_package/build_gate9/sentinel" ] && echo yes || echo no); bin=$([ -f "$S/bin/board_gate10_selftest_12class" ] && echo yes || echo no); out=$(cat "$S/out")"
fi

# ---------------------------------------------------------------------------
echo
echo "test_board_build.sh: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
