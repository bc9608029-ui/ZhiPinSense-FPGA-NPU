#!/usr/bin/env bash
# Regenerate the frozen SHA256SUMS.txt over the whole first-class source tree.
# Matches the original `HASH *./path` format (sha256sum -b, paths sorted).
#
# Excluded (not part of the frozen source set):
#   * SHA256SUMS.txt itself
#   * transient host-test binaries built in-tree by run_tests.sh (rebuilt on
#     every run; they are NOT source)
# Everything else on disk -- including the fix-patch staging dir and its tarball,
# the golden .bin files, the offline .deb/.tar.gz, and the response .png -- is
# frozen, matching the original manifest's "freeze the whole tree" convention.
#
# Usage (inside WSL):  bash tools/make_sha256sums.sh
set -euo pipefail
cd "$(dirname "$0")/.."

rm -f host_tests/test_all host_tests/test_nco host_tests/test_attr_routing \
      host_tests/test_receiver_scale host_tests/test_rx_format \
      host_tests/test_resampler host_tests/test_sample_rate_negotiate \
      host_tests/test_pluto_tx host_tests/test_device_state_guard \
      host_tests/test_frame_analysis

# build_libiio/build_gate.log is a regenerable gate log (build_libiio_gate.sh),
# not source; drop it and its dir.
rm -rf sdr_adapter/build_libiio

find . -type f ! -path './SHA256SUMS.txt' | sort | xargs sha256sum -b > SHA256SUMS.txt

echo "SHA256SUMS.txt regenerated ($(wc -l < SHA256SUMS.txt) entries)"
