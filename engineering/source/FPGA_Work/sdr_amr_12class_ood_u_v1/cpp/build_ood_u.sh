#!/usr/bin/env bash
# Build the CPU-side OOD-U detector, the replay CLI, and the host unit test.
# Runs the unit test (release + ASan/UBSan).  Fail-closed on any error.
# On a host without native g++ (Windows Git Bash), falls back to WSL Ubuntu g++.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"

CXX="${CXX:-g++}"

if ! command -v "$CXX" >/dev/null 2>&1; then
  if command -v wsl >/dev/null 2>&1 && wsl -d Ubuntu -- bash -lc 'command -v g++' >/dev/null 2>&1; then
    drv="$(printf '%s' "$here" | sed -n 's|^/\([a-zA-Z]\)/.*|\1|p' | tr 'A-Z' 'a-z')"
    rest="$(printf '%s' "$here" | sed 's|^/[a-zA-Z]||')"
    exec wsl -d Ubuntu -- bash -lc "cd \"/mnt/${drv}${rest}\" && CXX=g++ bash build_ood_u.sh"
  fi
  echo "build_ood_u.sh: no C++ compiler available (g++ or WSL g++)" >&2
  exit 1
fi

CXXFLAGS="-std=c++17 -O2 -Wall -Wextra -Werror"
CORE="ood_threshold_manifest.cpp ood_u_detector.cpp"

echo "[build_ood_u] building ood_u_replay"
"$CXX" $CXXFLAGS -I. $CORE ood_u_replay_main.cpp -o ood_u_replay

echo "[build_ood_u] building + running test_ood_u_detector (release)"
"$CXX" $CXXFLAGS -I. $CORE test_ood_u_detector.cpp -o test_ood_u_detector
./test_ood_u_detector

echo "[build_ood_u] building + running test_ood_u_detector (ASan/UBSan)"
"$CXX" -std=c++17 -O1 -g -Wall -Wextra -Werror \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    -I. $CORE test_ood_u_detector.cpp -o test_ood_u_detector_san
./test_ood_u_detector_san

echo "[build_ood_u] OK"
