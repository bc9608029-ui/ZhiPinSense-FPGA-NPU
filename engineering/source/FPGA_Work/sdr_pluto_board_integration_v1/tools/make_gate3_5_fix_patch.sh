#!/usr/bin/env bash
# Build the minimal Gate 3 fix + Gate 4/5 audit patch: stage the changed/added
# files into pluto_gate3_5_fix_patch/, generate a sidecar SHA256SUMS.txt (LF
# newlines), and tar the stage CONTENTS flat (no wrapper dir) so the board side
# can `tar -xzf ... -C` directly over the project tree.
#
# This patch is SELF-CONTAINED: every file is the FULL current version (not a
# diff), so extracting it over the tree brings everything up to date regardless
# of whether the earlier pluto_libiio_fix_patch.tar.gz was already applied.
#
# Usage (inside WSL):  bash tools/make_gate3_5_fix_patch.sh
set -euo pipefail
cd "$(dirname "$0")/.."

STAGE="pluto_gate3_5_fix_patch"
FILES=(
  sdr_adapter/device_state_guard.hpp
  sdr_adapter/pluto_device.hpp
  sdr_adapter/pluto_device_libiio.cpp
  sdr_adapter/pluto_tx.hpp
  sdr_adapter/pluto_tx.cpp
  board_package/board_common.hpp
  board_package/board_detect_pluto.cpp
  board_package/board_rx_only.cpp
  board_package/board_digital_loopback.cpp
  board_package/board_rf_loopback.cpp
  board_package/board_resampler_test.cpp
  host_tests/test_pluto_tx.cpp
  host_tests/test_device_state_guard.cpp
  host_tests/build_host_tests.sh
  host_tests/run_tests.sh
  host_tests/run_tests_asan.sh
  contracts/rx_iq_format_contract.md
  contracts/pluto_config_contract.md
  docs/BOARD_PLUTO_BRINGUP.md
  docs/REPORT.md
)

# Stage sources (README_FIX.md is authored directly into $STAGE).
for f in "${FILES[@]}"; do
  mkdir -p "$STAGE/$(dirname "$f")"
  cp "$f" "$STAGE/$f"
done

# SHA256SUMS.txt: relative paths, LF newlines, excludes the manifest itself.
(
  cd "$STAGE"
  : > SHA256SUMS.txt
  for f in README_FIX.md "${FILES[@]}"; do
    sha256sum "$f" >> SHA256SUMS.txt
  done
)

# Flat tarball of the stage contents.
rm -f pluto_gate3_5_fix_patch.tar.gz
tar -C "$STAGE" -czf pluto_gate3_5_fix_patch.tar.gz .

# Self-check: extract to a native-WSL temp dir and verify sha256sum -c.
TMP="$(mktemp -d)"
tar -xzf pluto_gate3_5_fix_patch.tar.gz -C "$TMP"
( cd "$TMP" && sha256sum -c SHA256SUMS.txt )
rm -rf "$TMP"

echo "made pluto_gate3_5_fix_patch.tar.gz ($(stat -c%s pluto_gate3_5_fix_patch.tar.gz) bytes)"
