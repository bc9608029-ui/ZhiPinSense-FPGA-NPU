#!/usr/bin/env bash
# M27 host test build (release).  namespace m27 header-only framework.
#
# The Windows host has no native g++; the test binary is a Linux ELF built with
# WSL g++ 15.2.0.  This script therefore routes the compile through WSL,
# mapping the Git Bash path /f/... to the WSL path /mnt/f/...
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_WSL="/mnt/$(cd "$HERE/.." && pwd | cut -c2-)"   # /mnt/f/FPGA_Work/...

wsl -e bash -lc "cd '$ROOT_WSL/tests' && g++ -std=gnu++17 -O2 -Wall -Wextra -Werror \
    -I../runtime -I../registry -I../router -I../fusion \
    test_m27.cpp -o test_m27"

echo "built: tests/test_m27"
