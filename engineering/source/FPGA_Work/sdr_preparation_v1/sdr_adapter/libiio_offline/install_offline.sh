#!/usr/bin/env bash
# Extract the bundled amd64 libiio sysroot from debs/*.deb (no root needed).
# Host-side helper for the build gate (see ../build_libiio_gate.sh).
#
# Usage:   bash install_offline.sh [dest]
# Default dest: $HOME/iio_work/sysroot

set -e
DEST="${1:-$HOME/iio_work/sysroot}"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DEST"
for f in "$HERE"/debs/*.deb; do
    echo "extracting $(basename "$f")"
    dpkg-deb -x "$f" "$DEST"
done

echo "sysroot ready at: $DEST"
echo "next: cd .. && bash build_libiio_gate.sh   (LIBIIO_SYSROOT=$DEST)"
