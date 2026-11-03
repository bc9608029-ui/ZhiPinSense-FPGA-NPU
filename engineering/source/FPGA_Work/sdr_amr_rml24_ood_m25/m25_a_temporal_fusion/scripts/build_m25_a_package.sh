#!/usr/bin/env bash
# build_m25_a_package.sh -- M25-A general multi-frame temporal fusion offline patch.
#
# Packages ONLY the newly-added M25-A files as a standalone offline patch.  It
# does NOT include or overwrite any M22/M23/M24 deliverable, does NOT touch the
# project-root SHA256SUMS.txt, and does NOT emit a full board package.
#
# The patch manifest is named M25_A_PATCH_SHA256SUMS.txt (NOT the root
# SHA256SUMS.txt) and lists only the content files (never itself, never the
# packager script).
#
# Status ceiling: M25-A-OFFLINE-MODULES-READY (never *_HARDWARE_PASS).
set -euo pipefail

cd "$(dirname "$0")/.."   # package root: m25_a_temporal_fusion

OUT="${M25_A_OUT:-dist/m25_a_temporal_fusion_offline_patch.tar.gz}"
MANIFEST="M25_A_PATCH_SHA256SUMS.txt"

# The content files (the packager script itself is intentionally NOT included,
# matching the M24-A patch convention).
FILES=(
  sdr_adapter/m25_temporal_fusion_config.hpp
  sdr_adapter/m25_temporal_fusion_state.hpp
  sdr_adapter/m25_temporal_fusion.hpp
  sdr_adapter/m25_temporal_fusion.cpp
  host_tests/test_m25_a.cpp
  host_tests/build_m25_a.sh
  host_tests/run_m25_a.sh
  host_tests/run_m25_a_asan.sh
  host_tests/run_m25_a_ubsan.sh
  host_tools/m25_temporal_fusion_replay.cpp
  host_tools/build_m25_temporal_fusion_replay.sh
  host_tools/m25_temporal_fusion_bench.cpp
  host_tools/build_m25_temporal_fusion_bench.sh
  scripts/run_m25_temporal_fusion_replay.sh
  scripts/test_m25_temporal_fusion.sh
  docs/M25_A_DELIVERY_REPORT.md
  docs/M25_A_INTEGRATION_INTERFACE.md
)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "build_m25_a_package.sh: missing $f" >&2; exit 1; }
  mkdir -p "$STAGE/$(dirname "$f")"
  cp -p "$f" "$STAGE/$f"
done

# Manifest named M25_A_PATCH_SHA256SUMS.txt; lists only the content files.
(cd "$STAGE" && sha256sum "${FILES[@]}" > "$MANIFEST")

# Guard: the package must not contain any file named exactly "SHA256SUMS.txt".
if find "$STAGE" -name 'SHA256SUMS.txt' -print -quit | grep -q .; then
  echo "build_m25_a_package.sh: found a SHA256SUMS.txt, aborting" >&2
  exit 1
fi

mkdir -p dist
tar -cf - -C "$STAGE" \
    --mtime='2026-10-09 00:00:00 UTC' \
    --owner=0 --group=0 --numeric-owner \
    --sort=name \
    . | gzip -n -9 > "$OUT"

echo "build_m25_a_package.sh: OK -> $OUT"
echo "  manifest: $MANIFEST (${#FILES[@]} content files, no self-entry)"
echo "  entries: $((${#FILES[@]} + 1)) (${#FILES[@]} content + manifest)"
sha256sum "$OUT"
