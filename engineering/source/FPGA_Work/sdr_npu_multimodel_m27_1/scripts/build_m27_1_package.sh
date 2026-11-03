#!/usr/bin/env bash
# Build the versioned M27.1 offline patch package + SHA256 manifest.
# Deterministic tar (sorted names, fixed mtime/owner) + gzip -n; manifest lists
# content files only (relative paths), never itself, no bare SHA256SUMS.txt guard.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
DIST="$ROOT/dist"
STAGE="$DIST/stage"
PKG="m27_1_multimodel_probe_patch.tar.gz"

# Content files (relative to project root).  The package script and dist/ are
# excluded; the manifest is generated alongside the tar, not inside it.
FILES=(
  docs/M27_1_SDK_MULTI_MODEL_AUDIT.md
  docs/M27_1_MODEL_SELECTION.md
  docs/M27_1_PROBE_PLAN.md
  docs/M27_1_DELIVERY_REPORT.md
  probes/m27_1_metrics.hpp
  probes/probe_common.hpp
  probes/probe_single_model.cpp
  probes/probe_two_networks.cpp
  probes/probe_sequential_inference.cpp
  probes/probe_concurrent_inference.cpp
  probes/probe_unload_reload.cpp
  probes/CMakeLists.txt
  probes/build_on_board.sh
  board_scripts/run_m27_1_board_probes.sh
  host_tests/test_m27_1_metrics.cpp
  host_tests/build_host_tests.sh
  host_tests/run_host_tests.sh
  host_tests/run_host_tests_asan.sh
  host_tests/run_host_tests_ubsan.sh
  results/M27_1_RESULT_TEMPLATE.json
  M27_1_DIFF_LIST.txt
)

rm -rf "$STAGE" && mkdir -p "$STAGE"
for f in "${FILES[@]}"; do
  mkdir -p "$STAGE/$(dirname "$f")"
  cp "$f" "$STAGE/$f"
done

# Deterministic tar (content under stage/, flat relative paths) + deterministic gzip.
# Fixed mtime year-2000 (Windows-extractable, still deterministic) + fixed owner.
tar --sort=name --mtime='UTC 2000-01-01' --owner=0 --group=0 --numeric-owner \
    -C "$STAGE" -cf - . | gzip -n > "$DIST/$PKG"

# Manifest: one line per content file, relative path, no self, no bare guard.
: > "$DIST/M27_1_PATCH_SHA256SUMS.txt"
for f in "${FILES[@]}"; do
  ( cd "$ROOT" && sha256sum "$f" ) >> "$DIST/M27_1_PATCH_SHA256SUMS.txt"
done

echo "Package: $DIST/$PKG"
echo "Manifest: $DIST/M27_1_PATCH_SHA256SUMS.txt"
echo "content files: ${#FILES[@]}"
echo "tar SHA256: $(sha256sum "$DIST/$PKG" | awk '{print $1}')"
echo "manifest lines: $(wc -l < "$DIST/M27_1_PATCH_SHA256SUMS.txt")"

rm -rf "$STAGE"
