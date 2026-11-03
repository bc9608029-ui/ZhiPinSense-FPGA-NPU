#!/usr/bin/env bash
# M27 host tests — AddressSanitizer (address only), inside WSL.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_WSL="/mnt/$(cd "$HERE/.." && pwd | cut -c2-)"

wsl -e bash -lc "cd '$ROOT_WSL/tests' && g++ -std=gnu++17 -O1 -g -fsanitize=address \
    -fno-omit-frame-pointer \
    -I../runtime -I../registry -I../router -I../fusion \
    test_m27.cpp -o test_m27_asan && ./test_m27_asan"
