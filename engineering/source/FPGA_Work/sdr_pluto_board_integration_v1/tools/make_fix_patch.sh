#!/usr/bin/env bash
# Build the minimal Pluto libiio fix patch: stage the changed/added files into
# pluto_libiio_fix_patch/, generate SHA256SUMS.txt (LF newlines), and tar the
# stage CONTENTS flat (no wrapper dir) so the board side can `tar -xzf ... -C`
# directly over the project tree.
#
# Usage (inside WSL):  bash tools/make_fix_patch.sh
set -euo pipefail
cd "$(dirname "$0")/.."

STAGE="pluto_libiio_fix_patch"
FILES=(
  sdr_adapter/iio_attr_routing.hpp
  sdr_adapter/pluto_device_libiio.cpp
  sdr_adapter/pluto_device.hpp
  sdr_adapter/pluto_libiio.cpp
  board_package/board_detect_pluto.cpp
  host_tests/test_attr_routing.cpp
  host_tests/build_host_tests.sh
  host_tests/run_tests.sh
  host_tests/run_tests_asan.sh
  host_tests/link_libiio_host_check.sh
  contracts/pluto_config_contract.md
  docs/BOARD_PLUTO_BRINGUP.md
)

# Stage sources (README_FIX.md is authored directly into $STAGE).
for f in "${FILES[@]}"; do
  mkdir -p "$STAGE/$(dirname "$f")"
  cp "$f" "$STAGE/$f"
done

# SHA256SUMS.txt: relative ./ paths, LF newlines, excludes the manifest itself.
(
  cd "$STAGE"
  : > SHA256SUMS.txt
  for f in README_FIX.md "${FILES[@]}"; do
    sha256sum "$f" >> SHA256SUMS.txt
  done
)

# Flat tarball of the stage contents.
rm -f pluto_libiio_fix_patch.tar.gz
tar -C "$STAGE" -czf pluto_libiio_fix_patch.tar.gz .

# Self-check: extract to a native-WSL temp dir and verify sha256sum -c.
TMP="$(mktemp -d)"
tar -xzf pluto_libiio_fix_patch.tar.gz -C "$TMP"
( cd "$TMP" && sha256sum -c SHA256SUMS.txt )
rm -rf "$TMP"

echo "made pluto_libiio_fix_patch.tar.gz ($(stat -c%s pluto_libiio_fix_patch.tar.gz) bytes)"
