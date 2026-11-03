#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p dist
files=(
  board_package/iq_dual_sdr_coarse_cfo_recovery.hpp
  board_package/iq_pc_tx_board_rx_23class_fix10.hpp
  host_tools/replay_fix10_failed_rx.cpp
  host_tests/build_host_tests.sh
  host_tests/run_tests.sh
  host_tests/test_iq_dual_sdr_23class_fix10.cpp
  docs/M29_RML23_FIX10PREP3_4ASK_RECOVERY_DIAGNOSTIC.md
  scripts/package_4ask_diag.sh
)

out=dist/fix10prep3_4ask_recovery_diagnostic_patch.tar.gz
run1="${out}.run1"
run2="${out}.run2"

make_archive() {
  local target="$1"
  tar --sort=name --mtime='UTC 2020-01-01' --owner=0 --group=0 \
      --numeric-owner -cf - "${files[@]}" | gzip -n > "$target"
}

make_archive "$run1"
make_archive "$run2"
cmp "$run1" "$run2"
mv "$run1" "$out"
rm "$run2"
sha256sum "$out" > "${out%.tar.gz}_SHA256SUMS.txt"

verify_dir="$(mktemp -d)"
trap 'rm -rf "$verify_dir"' EXIT
tar xzf "$out" -C "$verify_dir"
for file in "${files[@]}"; do
  cmp "$file" "$verify_dir/$file"
done

printf 'DETERMINISTIC_PATCH=PASS files=%s bytes=%s\n' \
  "${#files[@]}" "$(wc -c < "$out")"
cat "${out%.tar.gz}_SHA256SUMS.txt"
