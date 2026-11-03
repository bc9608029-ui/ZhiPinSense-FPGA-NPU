#!/usr/bin/env bash
set -euo pipefail

usage() { echo "usage: $0 --target STAGE7_ROOT [--apply]" >&2; }
TARGET=""
APPLY=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    *) usage; exit 2 ;;
  esac
done
[ -n "$TARGET" ] || { usage; exit 2; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)

check() {
  local sha="$1" rel="$2"
  [ -f "$TARGET/$rel" ] || { echo "MISSING prerequisite=$rel" >&2; exit 1; }
  echo "$sha  $TARGET/$rel" | sha256sum -c -
}
check cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a runtime/receiver_core.py
check e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a recovery/candidate_two_dc.py
check 46ba0e06f916b47604f25c77a7abfbdf6e850cf4a891348c79499fc5a986a719 board_runtime/rml24_final_receiver.py
check 41c475b040ffa9d69f688cf7e253ddc6746508d20c51e63ff781c273951f9167 runtime/ui_event.py
check c776f993403433740de072fd3092aea7fbf86bec0c64b86a7681941fbddb7b5d board_ui_overlay/board_package/board_ui_live_rml24_final.cpp
check e1e00cb2554dfa00abc85cc5f53534ccf81e7410cb5ec4d1451bf2393300c39f board_ui_overlay/ui_sw/ui_render.cpp
check 0f968379e7aa6f938ef4045af86766b5f217e279dee87b20e515d770f3a81b33 base_ui/board_package/touch_geometry.hpp

if [ "$APPLY" -ne 1 ]; then
  echo "SCAN_OVERLAY_AUDIT result=PASS target=$TARGET action=NONE"
  exit 0
fi

mkdir -p "$TARGET/runtime" "$TARGET/board_runtime" \
  "$TARGET/board_ui_overlay/board_package" "$TARGET/board_ui_overlay/ui_sw"
cp "$ROOT/runtime/scan_runtime.py" "$TARGET/runtime/scan_runtime.py"
cp "$ROOT/runtime/radio_tuning.py" "$TARGET/runtime/radio_tuning.py"
cp "$ROOT/runtime/mode_control_server.py" "$TARGET/runtime/mode_control_server.py"
cp "$ROOT/runtime/ui_event.py" "$TARGET/runtime/ui_event.py"
cp "$ROOT/board_runtime/rml24_dualmode_receiver.py" "$TARGET/board_runtime/rml24_dualmode_receiver.py"
cp "$ROOT/board_runtime/run_dualmode_receiver.sh" "$TARGET/board_runtime/run_dualmode_receiver.sh"
cp "$ROOT/ui_overlay/board_package/touch_geometry.hpp" "$TARGET/board_ui_overlay/board_package/touch_geometry.hpp"
cp "$ROOT/ui_overlay/board_package/board_ui_live_rml24_final.cpp" "$TARGET/board_ui_overlay/board_package/board_ui_live_rml24_final.cpp"
cp "$ROOT/ui_overlay/ui_sw/ui_render.cpp" "$TARGET/board_ui_overlay/ui_sw/ui_render.cpp"
chmod +x "$TARGET/board_runtime/rml24_dualmode_receiver.py" "$TARGET/board_runtime/run_dualmode_receiver.sh"
echo "SCAN_OVERLAY_INSTALL result=PASS target=$TARGET"

