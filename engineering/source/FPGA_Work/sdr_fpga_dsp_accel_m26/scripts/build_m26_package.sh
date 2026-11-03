#!/usr/bin/env bash
# M26 packaging — deterministic tar.gz of the offline DSP module sources + manifest.
#
#   m26_fpga_dsp_offline_modules_patch.tar.gz   (content files only)
#   M26_PATCH_SHA256SUMS.txt                    (sha256sum manifest, lists content,
#                                                NOT itself, no bare SHA256SUMS.txt)
#
# Excludes build artifacts (the compiled golden/m26_verify binary).  Reproducible:
# files are staged by name, tar uses --sort=name and a fixed mtime/owner/group, and
# gzip uses -n (no embedded timestamp/name).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
STAGE="$DIST/stage"
PKG="$DIST/m26_fpga_dsp_offline_modules_patch.tar.gz"
MANIFEST="$DIST/M26_PATCH_SHA256SUMS.txt"

rm -rf "$STAGE" "$PKG" "$MANIFEST"
mkdir -p "$STAGE"

# stage sources only (no compiled binary, no dist, no package script outputs)
for d in docs golden rtl scripts sim synth; do
  mkdir -p "$STAGE/$d"
done
cp "$ROOT"/docs/*.md                     "$STAGE/docs/"
cp "$ROOT"/golden/m26_fixed_model.hpp     "$STAGE/golden/"
cp "$ROOT"/golden/m26_golden.hpp          "$STAGE/golden/"
cp "$ROOT"/golden/m26_verify.cpp          "$STAGE/golden/"
cp "$ROOT"/rtl/*.sv                       "$STAGE/rtl/"
cp "$ROOT"/rtl/*.mem                      "$STAGE/rtl/"
cp "$ROOT"/scripts/gen_m26_roms.py        "$STAGE/scripts/"
cp "$ROOT"/sim/*.sv                       "$STAGE/sim/"
cp "$ROOT"/synth/*.tcl                    "$STAGE/synth/"

# manifest: sha256sum over content files, relative paths, sorted for determinism.
# Normalise the binary-mode '*' marker and strip the leading './' so lines read
# "<sha256>  <path>" (text mode, sha256sum -c compatible, no bare SHA256SUMS.txt).
( cd "$STAGE" && find . -type f | LC_ALL=C sort | xargs sha256sum ) \
  | sed -E 's#^([0-9a-f]{64}) \*\./#\1  #' > "$MANIFEST"

# deterministic tar + gzip
tar -C "$STAGE" --sort=name --mtime='2026-10-09 00:00:00Z' \
    --owner=0 --group=0 --numeric-owner -czf "$PKG" .

echo "package:      $PKG"
echo "manifest:     $MANIFEST"
echo "files:        $(find "$STAGE" -type f | wc -l)"
echo "manifest-lines: $(wc -l < "$MANIFEST")"
