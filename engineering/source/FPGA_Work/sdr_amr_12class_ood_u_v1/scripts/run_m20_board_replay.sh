#!/usr/bin/env bash
# M20 board replay: build the C++ detector and verify Python-C++ decision parity.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python -m scripts.m20_board_replay "$@"
