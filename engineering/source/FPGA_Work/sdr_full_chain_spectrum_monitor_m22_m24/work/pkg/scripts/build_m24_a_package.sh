#!/usr/bin/env bash
# build_m24_a_package.sh -- M24-A P1 model-independent offline module patch (errata1).
#
# Packages ONLY the 19 newly-added M24-A files (7 module headers + 4 test scripts +
# test + 2 host_tools cpp + 2 host_tools build scripts + 3 docs) as a patch against
# the M22/M23 baseline.  It does NOT include or overwrite any M22/M23 deliverable,
# does NOT touch the project-root SHA256SUMS.txt, and does NOT emit a full board
# package.
#
# errata1 is a VERSIONED ADDITION that supersedes the b20f8bc... package for the
# test/tooling/doc layer only: the 7 module headers are byte-identical, and the
# only changes are the extended FFT tests, a unified benchmark, and the split of
# ASan/UBSan into separate run scripts.  The b20f8bc... package is NOT overwritten.
#
# The patch manifest is named M24_A_PATCH_SHA256SUMS.txt (NOT the root SHA256SUMS.txt)
# and lists only the 19 content files (never itself, never the packager script).
#
# Status ceiling unchanged: M24-P1-OFFLINE-MODULES-READY / 24CLASS_MODEL_NOT_READY.
set -euo pipefail

cd "$(dirname "$0")/.."   # package root: work/pkg

OUT="${M24_A_OUT:-dist/sdr_full_chain_spectrum_monitor_m22_m24_m24_a_offline_patch_errata1.tar.gz}"
MANIFEST="M24_A_PATCH_SHA256SUMS.txt"

# The 19 content files (the packager script itself is intentionally NOT included,
# matching the M23 P0 patch convention).
FILES=(
  sdr_adapter/m24_fft.hpp
  sdr_adapter/m24_waterfall.hpp
  sdr_adapter/m24_ui_scheduler.hpp
  sdr_adapter/m24_patrol.hpp
  sdr_adapter/m24_event.hpp
  sdr_adapter/m24_class24_contract.hpp
  sdr_adapter/m24_class24_stub.hpp
  host_tests/test_m24_a.cpp
  host_tests/build_m24_a.sh
  host_tests/run_m24_a.sh
  host_tests/run_m24_a_asan.sh
  host_tests/run_m24_a_ubsan.sh
  host_tools/m24_replay.cpp
  host_tools/build_m24_replay.sh
  host_tools/m24_bench.cpp
  host_tools/build_m24_bench.sh
  docs/M24_A_INTEGRATION_INTERFACE.md
  docs/M24_A_CLASS24_TODO.md
  docs/M24_A_DELIVERY_REPORT.md
)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "build_m24_a_package.sh: missing $f" >&2; exit 1; }
  mkdir -p "$STAGE/$(dirname "$f")"
  cp -p "$f" "$STAGE/$f"
done

# Manifest named M24_A_PATCH_SHA256SUMS.txt; lists only the 19 content files.
(cd "$STAGE" && sha256sum "${FILES[@]}" > "$MANIFEST")

# Guard: the package must not contain any file named exactly "SHA256SUMS.txt".
if find "$STAGE" -name 'SHA256SUMS.txt' -print -quit | grep -q .; then
  echo "build_m24_a_package.sh: found a SHA256SUMS.txt, aborting" >&2
  exit 1
fi

mkdir -p dist
tar -cf - -C "$STAGE" \
    --mtime='2026-10-09 00:00:00 UTC' \
    --owner=0 --group=0 --numeric-owner \
    --sort=name \
    . | gzip -n -9 > "$OUT"

echo "build_m24_a_package.sh: OK -> $OUT"
echo "  manifest: $MANIFEST (19 content files, no self-entry)"
echo "  entries: $((${#FILES[@]} + 1)) (19 content + manifest)"
sha256sum "$OUT"
