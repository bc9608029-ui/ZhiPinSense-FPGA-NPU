#!/usr/bin/env bash
set -euo pipefail

usage() { echo "usage: $0 --source DIR --install-root DIR" >&2; }
SOURCE=""
INSTALL_ROOT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done
[ -n "$SOURCE" ] && [ -n "$INSTALL_ROOT" ] || { usage; exit 2; }
[ -f "$SOURCE/contract/final_system_contract.json" ] || { echo "bad source tree" >&2; exit 2; }
[ ! -e "$INSTALL_ROOT" ] || { echo "install root already exists: $INSTALL_ROOT" >&2; exit 2; }

mkdir -p "$INSTALL_ROOT"
for directory in board_runtime contract recovery runtime scripts docs evidence; do
  if [ -d "$SOURCE/$directory" ]; then
    cp -a "$SOURCE/$directory" "$INSTALL_ROOT/"
  fi
done
cp "$SOURCE/README.md" "$INSTALL_ROOT/README.md"

echo 'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a  '"$INSTALL_ROOT/recovery/candidate_two_dc.py" | sha256sum -c -
echo "RML24_FINAL_INSTALL result=PASS install_root=$INSTALL_ROOT"

