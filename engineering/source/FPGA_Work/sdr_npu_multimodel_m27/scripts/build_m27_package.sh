#!/usr/bin/env bash
# M27 packaging — deterministic tar.gz of the offline NPU multi-model framework
# sources + manifest.
#
#   m27_npu_multimodel_offline_framework_patch.tar.gz   (content files only)
#   M27_PATCH_SHA256SUMS.txt                            (sha256sum manifest; lists
#                                                        content, NOT itself, no
#                                                        bare SHA256SUMS.txt)
#
# Excludes generated artifacts: compiled test binaries (tests/test_m27{,_asan,
# _ubsan}), __pycache__/, .pytest_cache/, and everything under dist/.  Reproducible:
# staged by name, tar --sort=name + fixed mtime/owner/group, gzip -n.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
STAGE="$DIST/stage"
PKG="$DIST/m27_npu_multimodel_offline_framework_patch.tar.gz"
MANIFEST="$DIST/M27_PATCH_SHA256SUMS.txt"

rm -rf "$STAGE" "$PKG" "$MANIFEST"
mkdir -p "$STAGE"

for d in docs runtime registry router fusion channel_proto expert scripts tests \
         channel_proto/tests expert/tests; do
  mkdir -p "$STAGE/$d"
done

# C++ framework headers + host test source (no compiled ELF binaries)
cp "$ROOT"/docs/*.md                          "$STAGE/docs/"
cp "$ROOT"/runtime/*.hpp                      "$STAGE/runtime/"
cp "$ROOT"/registry/*.hpp                     "$STAGE/registry/"
cp "$ROOT"/router/*.hpp                       "$STAGE/router/"
cp "$ROOT"/fusion/*.hpp                       "$STAGE/fusion/"
cp "$ROOT"/tests/test_m27.cpp                 "$STAGE/tests/"

# Python channel prototype (sources + tests + run scripts)
cp "$ROOT"/channel_proto/*.py                 "$STAGE/channel_proto/"
cp "$ROOT"/channel_proto/*.sh                 "$STAGE/channel_proto/"
cp "$ROOT"/channel_proto/tests/*.py           "$STAGE/channel_proto/tests/"

# Python expert framework (sources + tests)
cp "$ROOT"/expert/*.py                        "$STAGE/expert/"
cp "$ROOT"/expert/tests/*.py                  "$STAGE/expert/tests/"

# scripts
cp "$ROOT"/scripts/*.sh                       "$STAGE/scripts/"

# manifest: sha256sum over content files, relative paths, sorted for determinism.
# Normalise the binary-mode '*' marker and strip the leading './' so lines read
# "<sha256>  <path>" (text mode, sha256sum -c compatible, no bare SHA256SUMS.txt).
( cd "$STAGE" && find . -type f | LC_ALL=C sort | xargs sha256sum ) \
  | sed -E 's#^([0-9a-f]{64}) \*\./#\1  #' > "$MANIFEST"

# deterministic tar + gzip
tar -C "$STAGE" --sort=name --mtime='2026-10-09 00:00:00Z' \
    --owner=0 --group=0 --numeric-owner -czf "$PKG" .

echo "package:        $PKG"
echo "manifest:       $MANIFEST"
echo "files:          $(find "$STAGE" -type f | wc -l)"
echo "manifest-lines: $(wc -l < "$MANIFEST")"
