#!/usr/bin/env bash
# Build the M23 P0 offline PATCH package (NOT a full board package).
#
# The M23 P0 deliverable is a PATCH only: isolated source modules, host tests,
# the IQ replay tool, and the three docs.  It must NOT be a full board package
# and must NOT be mistaken for a board-acceptance package.  It adds files only;
# it never modifies M22 deliverables.  Deterministic output (GZIP=-n, fixed
# mtime, numeric owner/group 0) so re-runs are byte-identical.
#
# Status ceiling: M23-P0-OFFLINE-MODULES-READY.  Never M23_P0_PASS / HARDWARE_PASS.
set -euo pipefail

cd "$(dirname "$0")/.."   # package root: work/pkg

OUT="${M23_P0_OUT:-dist/sdr_full_chain_spectrum_monitor_m22_m24_m23_p0_offline_patch.tar.gz}"

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

# Fail-closed if any deliverable is missing.
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "build_m23_p0_package.sh: missing $f" >&2; exit 1; }
done

# Stage files preserving relative paths, then write SHA256SUMS.txt (relative).
for f in "${FILES[@]}"; do
  mkdir -p "$STAGE/$(dirname "$f")"
  cp -p "$f" "$STAGE/$f"
done

(cd "$STAGE" && sha256sum "${FILES[@]}" > SHA256SUMS.txt)

mkdir -p dist
# Deterministic tarball: fixed mtime, numeric owner/group 0, gzip -n.
tar -cf - -C "$STAGE" \
    --mtime='2026-10-09 00:00:00 UTC' \
    --owner=0 --group=0 --numeric-owner \
    --sort=name \
    . | gzip -n -9 > "$OUT"

echo "build_m23_p0_package.sh: OK -> $OUT"
echo "  files: $((${#FILES[@]} + 1)) (${#FILES[@]} content + SHA256SUMS.txt)"
sha256sum "$OUT"
