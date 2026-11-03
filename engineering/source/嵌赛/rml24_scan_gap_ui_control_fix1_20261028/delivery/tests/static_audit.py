#!/usr/bin/env python3
"""Static contract audit for the deployable overlay."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
receiver = (ROOT / "board_runtime/standalone_receiver_gapfix.py").read_text(encoding="utf-8")
control = (ROOT / "runtime/standalone_control.py").read_text(encoding="utf-8")
ui = (ROOT / "ui_sw/ui_render.cpp").read_text(encoding="utf-8")
touch = (ROOT / "board_package/touch_mode_control.hpp").read_text(encoding="utf-8")
freq = (ROOT / "board_package/frequency_control.hpp").read_text(encoding="utf-8")
live = (ROOT / "board_package/board_ui_live_rml24_final.cpp").read_text(encoding="utf-8")

checks = {
    "bounded_miss_hysteresis": ("default=5" in receiver and
                                 "default=1.0" in receiver and
                                 "LockHysteresis" in receiver),
    "only_two_public_modes": "['FIXED', 'BAND_SCAN']" in control,
    "autolock_not_touch_mode": '"AUTO_LOCK"' not in touch,
    "ui_has_two_mode_buttons": 'const char* names[2]' in ui and 'i < 2' in ui,
    "four_frequency_fields": "for(int i=0;i<4;++i)" in ui,
    "fixed_frequency_command": "SET_FIXED_HZ " in freq,
    "scan_range_command": "SET_SCAN_RANGE_HZ " in freq,
    "producer_readback_sync": "GET_TUNING" in live and "on_reply" in live,
    "no_direct_sdr_write_in_editor": all(x not in freq for x in ("iio_", "tune(", "ad9361")),
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
if failed:
    raise SystemExit("static audit failed: " + ", ".join(failed))
print(f"static_audit: PASS {len(checks)}/{len(checks)}")
