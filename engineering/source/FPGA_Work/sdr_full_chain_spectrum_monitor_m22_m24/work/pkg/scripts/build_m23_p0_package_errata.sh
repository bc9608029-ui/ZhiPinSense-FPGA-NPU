#!/usr/bin/env bash
# M23 P0 patch PACKAGING ERRATA (does NOT modify any of the 21 existing files).
#
# Changes vs the original build_m23_p0_package.sh:
#   - versioned new output (does not overwrite the c70eb729... deliverable)
#   - the root manifest is renamed SHA256SUMS.txt -> M23_P0_PATCH_SHA256SUMS.txt
#   - the manifest lists only the 20 content files (never itself)
#   - no file named exactly "SHA256SUMS.txt" exists anywhere in the package
# The 20 content files are staged byte-for-byte from the repo and are therefore
# identical to the original c70eb729... patch (verified by cmp in the release).
#
# Status ceiling unchanged: M23-P0-OFFLINE-MODULES-READY.
set -euo pipefail

cd "$(dirname "$0")/.."   # package root: work/pkg

OUT="${M23_P0_ERRATA_OUT:-dist/sdr_full_chain_spectrum_monitor_m22_m24_m23_p0_offline_patch_errata1.tar.gz}"
MANIFEST="M23_P0_PATCH_SHA256SUMS.txt"

# The 20 content files (identical set to the original patch; the packager script
# itself, scripts/build_m23_p0_package.sh, is intentionally NOT included).
FILES=(
  sdr_adapter/m23_contract.hpp
  sdr_adapter/m23_cfo.hpp
  sdr_adapter/m23_params.hpp
  sdr_adapter/m23_verdict.hpp
  sdr_adapter/m23_ood_u_switch.hpp
  sdr_adapter/m23_iq_synth.hpp
  sdr_adapter/ood_u_contract.hpp
  sdr_adapter/ood_u_detector.hpp
  sdr_adapter/ood_u_detector.cpp
  sdr_adapter/ood_threshold_manifest.hpp
  sdr_adapter/ood_threshold_manifest.cpp
  sdr_adapter/minijson.hpp
  host_tests/test_m23_p0.cpp
  host_tests/build_m23_p0.sh
  host_tests/run_m23_p0.sh
  host_tools/m23_iq_replay.cpp
  host_tools/build_m23_iq_replay.sh
  docs/M23_P0_PARAMETER_ESTIMATION_CONTRACT.md
  docs/M23_P0_INTEGRATION_INTERFACE.md
  docs/M23_P0_DELIVERY_REPORT.md
)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "build_m23_p0_package_errata.sh: missing $f" >&2; exit 1; }
  mkdir -p "$STAGE/$(dirname "$f")"
  cp -p "$f" "$STAGE/$f"
done

# Manifest named M23_P0_PATCH_SHA256SUMS.txt; lists only the 20 content files.
(cd "$STAGE" && sha256sum "${FILES[@]}" > "$MANIFEST")

# Guard: the package must not contain any file named exactly "SHA256SUMS.txt".
if find "$STAGE" -name 'SHA256SUMS.txt' -print -quit | grep -q .; then
  echo "build_m23_p0_package_errata.sh: found a SHA256SUMS.txt, aborting" >&2
  exit 1
fi

mkdir -p dist
tar -cf - -C "$STAGE" \
    --mtime='2026-10-09 00:00:00 UTC' \
    --owner=0 --group=0 --numeric-owner \
    --sort=name \
    . | gzip -n -9 > "$OUT"

echo "build_m23_p0_package_errata.sh: OK -> $OUT"
echo "  manifest: $MANIFEST (20 content files, no self-entry)"
echo "  entries: $((${#FILES[@]} + 1)) (20 content + manifest)"
sha256sum "$OUT"
