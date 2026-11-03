#!/usr/bin/env bash
# M27 host tests — release build + run (inside WSL).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_WSL="/mnt/$(cd "$HERE/.." && pwd | cut -c2-)"

wsl -e bash -lc "cd '$ROOT_WSL/tests' && g++ -std=gnu++17 -O2 -Wall -Wextra -Werror \
    -I../runtime -I../registry -I../router -I../fusion \
    test_m27.cpp -o test_m27 && ./test_m27"
