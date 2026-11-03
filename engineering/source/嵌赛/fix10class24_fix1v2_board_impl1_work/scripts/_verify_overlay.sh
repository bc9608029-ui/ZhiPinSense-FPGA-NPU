#!/usr/bin/env bash
# _verify_overlay.sh -- clean-base overlay check: apply gate9_wiring.patch to a fresh
# copy of the dc-ab1 baseline board_package/ and confirm it applies cleanly and the
# new phase lands.  Reproducible; run under WSL.
set -euo pipefail
BASE=/mnt/f/嵌赛/fix10class24_original_radioml_dc_ab1_work
PKG=/mnt/f/嵌赛/fix10class24_fix1v2_board_impl1_work
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT
cd "$D"
mkdir -p board_package
cp -r "$BASE/board_package/." ./board_package/
git init -q .
git add -A
git -c user.email=t@t -c user.name=t commit -qm base
git apply --check "$PKG/board_package/gate9_wiring.patch" && echo "GIT_APPLY_CHECK=PASS"
git apply "$PKG/board_package/gate9_wiring.patch" && echo "GIT_APPLY=PASS"
echo "include_count=$(grep -c 'radioml_independent_rx_runner.hpp' board_package/board_gate9_full_chain_rml23.cpp)"
echo "phase_cpp_count=$(grep -c 'radioml-independent-rx-public-protocol-24class-bf16-fix1' board_package/board_gate9_full_chain_rml23.cpp)"
echo "phase_hpp_count=$(grep -c 'radioml-independent-rx-public-protocol-24class-bf16-fix1' board_package/gate9_phase.hpp)"
echo "OVERLAY_VERIFY_DONE"
