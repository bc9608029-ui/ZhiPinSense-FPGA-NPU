#!/usr/bin/env bash
# build_m22_package.sh -- assemble the M22 runtime-fix deliverables, versioned and
# WITHOUT touching the M19 package (or any earlier M14..M19 package).
#
# Produces (deterministically: GZIP=-n + fixed mtime + numeric owner):
#   <project>/dist/
#     m22_runtime_fix_patch.tar.gz                                     (flat, overlay onto M19)
#     sdr_full_chain_spectrum_monitor_m22_m24_m22_board_package.tar.gz (full package)
#
# Source of truth = work/pkg/ (the M22 tree).  The full package is M19 full package
# unpacked + the M22 patch files copied over it; the patch is built from that staged
# tree.  No file is deleted relative to M19 (M22 is pure add/modify).
#
# Verification:
#   * pre-flight: bash -n on the changed shell scripts + assert every patch file
#     exists in work/pkg;
#   * full package: unpack -> sha256sum -c SHA256SUMS.txt -> all OK;
#   * patch(over M19) is byte-identical to the full package (diff -rq zero).
#
# NOTE: the C++ host-test regression (g++ -Wall -Wextra -Werror, all tests green) is
# run separately in WSL (host_tests/build_host_tests.sh + host_tests/run_tests.sh);
# this script only assembles/verifies the byte-identical deliverables.
#
# Usage (Git Bash: F: = /f ; WSL: F: = /mnt/f):
#   bash build_m22_package.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
M19_ROOT="$(dirname "$ROOT")/sdr_full_chain_12class_ui_v3_m19"
BASE_TAR="$M19_ROOT/dist/sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package.tar.gz"
BASE_NAME=sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package
WORK="$ROOT/work/pkg"
PKG_NAME=sdr_full_chain_spectrum_monitor_m22_m24_m22_board_package
PATCH_NAME=m22_runtime_fix_patch
DIST="$ROOT/dist"
MTIME='UTC 2026-10-09'

# 23 files: 10 modified + 10 added + README.md + PROVENANCE.md + SHA256SUMS.txt.
PATCH_FILES=(
  SHA256SUMS.txt
  PROVENANCE.md
  README.md
  board_package/board_gate9_full_chain_12class.cpp
  board_package/chain_common.hpp
  board_package/npu_classifier.hpp
  board_package/producer_12class.hpp
  host_tests/build_host_tests.sh
  host_tests/run_tests.sh
  sdr_adapter/classify.hpp
  sdr_adapter/dsp_measure.hpp
  sdr_adapter/ui_report.hpp
  sdr_adapter/unix_socket_sink.hpp
  docs/M22_LATENCY_ROOT_CAUSE.md
  docs/M22_RUNTIME_BASELINE.md
  host_tests/test_m22_runtime.cpp
  scripts/m22_harness.sh
  scripts/run_m22_runtime_baseline.sh
  scripts/run_m22_runtime_regression.sh
  scripts/test_m22_m24.sh
  sdr_adapter/latency_stats.hpp
  sdr_adapter/npu_lifecycle_state.hpp
  sdr_adapter/resource_snapshot.hpp
)

echo "== pre-flight: baseline present =="
[ -f "$BASE_TAR" ] || { echo "   MISSING base tar: $BASE_TAR" >&2; exit 1; }
echo "   base: $BASE_TAR"

echo "== pre-flight: patch files present in work/pkg (source of truth) =="
for f in "${PATCH_FILES[@]}"; do
  [ "$f" = "SHA256SUMS.txt" ] && continue
  if [ ! -f "$WORK/$f" ]; then
    echo "   MISSING work/pkg/$f" >&2
    exit 1
  fi
done
echo "   all ${#PATCH_FILES[@]} patch entries present (SHA256SUMS.txt regenerated below)"

echo "== pre-flight: bash -n on changed shell scripts =="
for s in \
  host_tests/build_host_tests.sh \
  host_tests/run_tests.sh \
  scripts/m22_harness.sh \
  scripts/run_m22_runtime_baseline.sh \
  scripts/run_m22_runtime_regression.sh \
  scripts/test_m22_m24.sh; do
  bash -n "$WORK/$s"
done
echo "   bash -n OK"

echo "== stage full package (unpack M19 + copy M22 patch files) =="
rm -rf "$DIST/$PKG_NAME" "$DIST/$PKG_NAME.tar.gz" "$DIST/$PATCH_NAME.tar.gz"
mkdir -p "$DIST"
tar -xzf "$BASE_TAR" -C "$DIST"
mv "$DIST/$BASE_NAME" "$DIST/$PKG_NAME"
for f in "${PATCH_FILES[@]}"; do
  [ "$f" = "SHA256SUMS.txt" ] && continue
  mkdir -p "$DIST/$PKG_NAME/$(dirname "$f")"
  cp "$WORK/$f" "$DIST/$PKG_NAME/$f"
done
rm -rf "$DIST/$PKG_NAME/bin" "$DIST/$PKG_NAME/host_tests/bin"

echo "== regenerate SHA256SUMS.txt (relative, excludes itself) =="
( cd "$DIST/$PKG_NAME" && find . -type f ! -name SHA256SUMS.txt -printf '%P\0' \
    | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )

STAGED_FILES="$(find "$DIST/$PKG_NAME" -type f | wc -l)"
MANIFEST_LINES="$(wc -l < "$DIST/$PKG_NAME/SHA256SUMS.txt")"
echo "   staged files (incl manifest): $STAGED_FILES ; manifest lines: $MANIFEST_LINES"

echo "== build full package tarball (deterministic) =="
GZIP=-n tar -czf "$DIST/$PKG_NAME.tar.gz" -C "$DIST" "$PKG_NAME" \
  --mtime="$MTIME" --owner=0 --group=0 --numeric-owner

echo "== build patch tarball (flat, overlay onto M19) =="
GZIP=-n tar -czf "$DIST/$PATCH_NAME.tar.gz" -C "$DIST/$PKG_NAME" "${PATCH_FILES[@]}" \
  --mtime="$MTIME" --owner=0 --group=0 --numeric-owner

echo "== verify full package: unpack + sha256sum -c =="
V1="$(mktemp -d)"
tar -xzf "$DIST/$PKG_NAME.tar.gz" -C "$V1"
( cd "$V1/$PKG_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
echo "   full package: sha256sum -c -> all OK ($(find "$V1/$PKG_NAME" -type f | wc -l) files)"

echo "== verify patch(over M19) == full package (diff -rq) =="
V2="$(mktemp -d)"
tar -xzf "$BASE_TAR" -C "$V2"
tar -xzf "$DIST/$PATCH_NAME.tar.gz" -C "$V2/$BASE_NAME"
( cd "$V2/$BASE_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
if diff -rq "$V2/$BASE_NAME" "$V1/$PKG_NAME"; then
  echo "   diff -rq: ZERO differences (patch + M19 == full package)"
else
  echo "   diff -rq: DIFFERENCES FOUND (see above)" >&2
  exit 1
fi

echo
echo "===== RESULTS ====="
echo "full package : $DIST/$PKG_NAME.tar.gz"
echo "  sha256     : $(sha256sum -b "$DIST/$PKG_NAME.tar.gz" | awk '{print $1}')"
echo "  bytes      : $(stat -c %s "$DIST/$PKG_NAME.tar.gz")"
echo "  files      : $STAGED_FILES (incl SHA256SUMS.txt)"
echo "  manifest   : $MANIFEST_LINES lines"
echo "patch        : $DIST/$PATCH_NAME.tar.gz"
echo "  sha256     : $(sha256sum -b "$DIST/$PATCH_NAME.tar.gz" | awk '{print $1}')"
echo "  bytes      : $(stat -c %s "$DIST/$PATCH_NAME.tar.gz")"
echo "  files      : $(tar -tzf "$DIST/$PATCH_NAME.tar.gz" | grep -v '/$' | wc -l)"

rm -rf "$V1" "$V2"
echo "done"
