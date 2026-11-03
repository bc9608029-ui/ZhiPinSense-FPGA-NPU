#!/usr/bin/env bash
# build_m25_b_package.sh -- M25-B 24-class OE framework offline patch.
#
# Packages ONLY the newly-added M25-B framework files as a standalone offline
# patch.  It does NOT include any checkpoint/model, does NOT overwrite the 12-class
# production model or the 24-class pilot tree, and does NOT emit a full board
# package.  No OE training is run; the framework is delivered in the
# 24CLASS_BASELINE_NOT_FROZEN / 24CLASS_OE_MODEL_NOT_TRAINED state.
#
# The patch manifest is named M25_B_PATCH_SHA256SUMS.txt (NOT the root
# SHA256SUMS.txt) and lists only the content files (never itself, never the
# packager script).
set -euo pipefail

cd "$(dirname "$0")/.."   # package root: m25_b_24class_oe_framework

OUT="${M25_B_OUT:-dist/m25_b_24class_oe_framework_patch.tar.gz}"
MANIFEST="M25_B_PATCH_SHA256SUMS.txt"

FILES=(
  conftest.py
  contracts/__init__.py
  contracts/m25b_24class_contract.py
  contracts/m25b_oe_data_protocol.py
  datasets/__init__.py
  datasets/m25b_generator_manifest.py
  datasets/m25b_ood_generator.py
  audit/__init__.py
  audit/m25b_isolation_audit.py
  audit/m25b_shortcut_audit.py
  npu_boundary/__init__.py
  npu_boundary/m25b_npu_boundary.py
  ood/__init__.py
  ood/m25b_metrics.py
  ood/m25b_scores.py
  ood/m25b_threshold_manifest.py
  ood/m25b_thresholds.py
  training/__init__.py
  training/m25b_baseline_gate.py
  training/m25b_budget.py
  training/m25b_oe_controls.py
  training/m25b_oe_energy_loss.py
  scripts/run_24class_oe_calibration.sh
  scripts/run_24class_oe_data_audit.sh
  scripts/run_24class_oe_decision.sh
  scripts/run_24class_oe_extra_seeds.sh
  scripts/run_24class_oe_final_blind.sh
  scripts/run_24class_oe_seed2026.sh
  scripts/run_24class_oe_shortcut_audit.sh
  scripts/test_24class_oe_framework.sh
  tests/test_m25b_01_contract.py
  tests/test_m25b_02_oe_data_protocol.py
  tests/test_m25b_03_ood_generator.py
  tests/test_m25b_04_generator_manifest.py
  tests/test_m25b_05_isolation_audit.py
  tests/test_m25b_06_shortcut_audit.py
  tests/test_m25b_07_scores.py
  tests/test_m25b_08_thresholds.py
  tests/test_m25b_09_threshold_manifest.py
  tests/test_m25b_10_metrics.py
  tests/test_m25b_11_oe_energy_loss.py
  tests/test_m25b_12_oe_controls.py
  tests/test_m25b_13_budget.py
  tests/test_m25b_14_baseline_gate.py
  tests/test_m25b_15_npu_boundary.py
  tests/test_m25b_16_mock_model_flow.py
  tests/test_m25b_17_mock_oe_train.py
  tests/test_m25b_18_mock_calibration.py
  tests/test_m25b_19_mock_final_blind.py
  tests/test_m25b_20_status_redlines.py
  tests/test_m25b_21_self_contained.py
  docs/M25_24CLASS_KNOWN_SET_AUDIT.md
  docs/M25_B_24CLASS_OE_DELIVERY_REPORT.md
)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "build_m25_b_package.sh: missing $f" >&2; exit 1; }
  mkdir -p "$STAGE/$(dirname "$f")"
  cp -p "$f" "$STAGE/$f"
done

(cd "$STAGE" && sha256sum "${FILES[@]}" > "$MANIFEST")

if find "$STAGE" -name 'SHA256SUMS.txt' -print -quit | grep -q .; then
  echo "build_m25_b_package.sh: found a SHA256SUMS.txt, aborting" >&2
  exit 1
fi

mkdir -p dist
tar -cf - -C "$STAGE" \
    --mtime='2026-10-09 00:00:00 UTC' \
    --owner=0 --group=0 --numeric-owner \
    --sort=name \
    . | gzip -n -9 > "$OUT"

echo "build_m25_b_package.sh: OK -> $OUT"
echo "  manifest: $MANIFEST (${#FILES[@]} content files, no self-entry)"
echo "  entries: $((${#FILES[@]} + 1)) (${#FILES[@]} content + manifest)"
sha256sum "$OUT"
