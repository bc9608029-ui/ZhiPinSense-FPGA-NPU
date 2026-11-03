#!/usr/bin/env bash
# Unpack each RML23 heartbeat/UI/integrated package into a fresh temp dir and
# verify every content file with sha256sum -c.  Exits non-zero on any mismatch.
set -euo pipefail
cd "$(dirname "$0")/.."

V="$(mktemp -d)"
trap 'rm -rf "$V"' EXIT

echo "== 1. heartbeat errata patch =="
tar -xzf "dist/sdr_rml23_live_heartbeat_errata_patch.tar.gz" -C "$V"
(cd "$V/sdr_rml23_live_heartbeat_errata_patch" && sha256sum -c HEARTBEAT_ERRATA_PATCH_SHA256SUMS.txt)

echo "== 2. UI redesign patch =="
tar -xzf "dist/sdr_rml23_live_ui_redesign_patch.tar.gz" -C "$V"
(cd "$V/sdr_rml23_live_ui_redesign_patch" && sha256sum -c UI_REDESIGN_PATCH_SHA256SUMS.txt)

echo "== 3. merged full board package =="
tar -xzf "dist/sdr_rml23_live_board_package_integrated.tar.gz" -C "$V"
(cd "$V/sdr_rml23_live_board_package_integrated" && sha256sum -c SHA256SUMS.txt)

echo "ALL sha256sum -c PASSED"
