#!/usr/bin/env bash
# build_m22_ui_errata1_package.sh -- M22.1 errata1 patch (Task A runtime-script
# process-management fix + Task B UI layout/visual refactor).
#
# Versioned ADDITIVE patch: packages ONLY the 16 errata files against the historical
# M22 runtime package + the M19 UI baseline.  It does NOT overwrite the historical
# m22_runtime_fix_patch.tar.gz or any M23/M24 package, does NOT touch the
# project-root SHA256SUMS.txt, and does NOT emit a full board package.
#
# The patch manifest is named M22_UI_ERRATA1_PATCH_SHA256SUMS.txt (NOT the root
# SHA256SUMS.txt) and lists only the 16 content files (never itself, never this
# packager script).
#
# Status ceiling: M22_RUNTIME_HARNESS_ERRATA_READY + M22_UI_LAYOUT_ERRATA_READY_FOR_BOARD_TEST.
# Forbidden here: UI_VISUAL_PASS / UI_HARDWARE_PASS / PROJECT_COMPLETE / FINAL_*.
set -euo pipefail

cd "$(dirname "$0")/.."   # package root: work/pkg

OUT="${M22_UI_ERRATA1_OUT:-dist/m22_runtime_harness_ui_layout_errata1_patch.tar.gz}"
MANIFEST="M22_UI_ERRATA1_PATCH_SHA256SUMS.txt"

# The 16 content files (the packager script itself is intentionally NOT included,
# matching the M23/M24 patch convention).
FILES=(
  scripts/m22_harness.sh
  scripts/run_m22_runtime_baseline.sh
  scripts/run_m22_runtime_regression.sh
  scripts/test_m22_harness_errata.sh
  scripts/gen_m22_ui_errata1_diff.sh
  ui_sw/font_atlas.hpp
  ui_sw/font_atlas.cpp
  ui_sw/ui_layout.hpp
  ui_sw/ui_render.hpp
  ui_sw/ui_render.cpp
  host_tests/test_ui_layout_boundaries.cpp
  host_tests/make_ui_m22_1_snapshots.cpp
  host_tests/build_host_tests.sh
  docs/M22_UI_LAYOUT_ERRATA.md
  docs/M22_BOARD_RETEST.md
  docs/M22_UI_ERRATA1_DIFF.md
)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "build_m22_ui_errata1_package.sh: missing $f" >&2; exit 1; }
  mkdir -p "$STAGE/$(dirname "$f")"
  cp -p "$f" "$STAGE/$f"
done

# Manifest named M22_UI_ERRATA1_PATCH_SHA256SUMS.txt; lists only the 16 content files.
(cd "$STAGE" && sha256sum "${FILES[@]}" > "$MANIFEST")

# Guard: the package must not contain any file named exactly "SHA256SUMS.txt".
if find "$STAGE" -name 'SHA256SUMS.txt' -print -quit | grep -q .; then
  echo "build_m22_ui_errata1_package.sh: found a SHA256SUMS.txt, aborting" >&2
  exit 1
fi

mkdir -p dist
tar -cf - -C "$STAGE" \
    --mtime='2026-10-10 00:00:00 UTC' \
    --owner=0 --group=0 --numeric-owner \
    --sort=name \
    . | gzip -n -9 > "$OUT"

echo "build_m22_ui_errata1_package.sh: OK -> $OUT"
echo "  manifest: $MANIFEST (16 content files, no self-entry)"
echo "  entries: $((${#FILES[@]} + 1)) (16 content + manifest)"
sha256sum "$OUT"
