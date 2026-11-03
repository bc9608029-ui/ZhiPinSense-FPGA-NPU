#!/bin/bash
set -euo pipefail
for n in $(seq 1 60); do
 [ -c /dev/udmabuf0 ] && [ -c /dev/mem ] && break
 sleep .5
done
[ -c /dev/udmabuf0 ] && [ -c /dev/mem ]
echo '3950201f64f4575755840df2d98879b5d3e44a109372192366d67a90652adaf6  /opt/rml24-system/bin/board_ui_live_rml24_final' | sha256sum -c -
