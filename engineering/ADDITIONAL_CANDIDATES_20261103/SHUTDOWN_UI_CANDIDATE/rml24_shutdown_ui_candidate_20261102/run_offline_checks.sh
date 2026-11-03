#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build previews/candidate previews/baseline
CXX="${CXX:-g++}"
COMMON=(-std=gnu++17 -O2 -Wall -Wextra -Werror)
"$CXX" "${COMMON[@]}" test_shutdown_ui.cpp -o build/test_shutdown_ui
"$CXX" "${COMMON[@]}" test_shutdown_action.cpp -o build/test_shutdown_action
build/test_shutdown_ui
build/test_shutdown_action
"$CXX" "${COMMON[@]}" -DSHUTDOWN_TEST_NO_CLOSE_RANGE test_shutdown_action.cpp -o build/test_shutdown_action_legacy_kernel
build/test_shutdown_action_legacy_kernel
SRC=(font_atlas.cpp font_atlas_data.cpp ui_render.cpp waterfall_render.cpp)
for kind in candidate baseline; do
  if [ "$kind" = candidate ]; then
    UI=release/candidate/ui_sw
    EXTRA=(-DSHUTDOWN_CANDIDATE)
  else
    UI=baseline_ui
    EXTRA=()
  fi
  FILES=()
  for source in "${SRC[@]}"; do FILES+=("$UI/$source"); done
  "$CXX" "${COMMON[@]}" "${EXTRA[@]}" -I"$UI" render_shutdown.cpp "${FILES[@]}" -o "build/render_$kind"
  "build/render_$kind" "previews/$kind"
done
"$CXX" "${COMMON[@]}" -Irelease/candidate/board_package -Irelease/candidate/sdr_adapter \
  -Irelease/candidate/ui_sw release/candidate/board_package/board_ui_live_rml24_final.cpp \
  release/candidate/ui_sw/direct_framebuffer_backend.cpp \
  release/candidate/ui_sw/font_atlas.cpp release/candidate/ui_sw/font_atlas_data.cpp \
  release/candidate/ui_sw/ui_render.cpp release/candidate/ui_sw/waterfall_render.cpp \
  -o build/board_ui_host
echo SHUTDOWN_OFFLINE_COMPILE_AND_TEST_PASS
