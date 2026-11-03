#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ $(uname -m) == aarch64 ]] || { echo 'board aarch64 required'; exit 2; }
ICRAFT_INCLUDE=${ICRAFT_INCLUDE:-/usr/include}
ICRAFT_LIB=${ICRAFT_LIB:-/usr/lib/aarch64-linux-gnu}
[[ -f "$ICRAFT_INCLUDE/icraft-xrt/core/session.h" && ! -e scan_xrt ]] || exit 2
g++ -std=gnu++17 -O2 -Wall -Wextra -Werror test_protocol.cpp -o test_protocol
./test_protocol
INCLUDES=()
# /usr/include is already a GCC system directory. Explicit -isystem here
# moves it before libstdc++ on GCC9 and breaks cstdlib's include_next.
[[ $(readlink -f "$ICRAFT_INCLUDE") == /usr/include ]] || INCLUDES=(-isystem "$ICRAFT_INCLUDE")
g++ -std=gnu++17 -O2 -Wall -Wextra -Werror "${INCLUDES[@]}" scan_xrt.cpp \
 -L"$ICRAFT_LIB" -Wl,-rpath,"$ICRAFT_LIB" -licraft_zg330backend -licraft_hostbackend \
 -licraft_xrt -licraft_xir -licraft_utils -lpthread -ldl -lrt -o scan_xrt
echo 'SMARTSCAN_BOARD_BUILD PASS'
