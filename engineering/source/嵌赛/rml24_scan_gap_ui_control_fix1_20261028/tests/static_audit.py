#!/usr/bin/env python3
"""Static contract audit for the deployable overlay."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "overlay"
receiver = (DEPLOY / "rml24_final/board_runtime/standalone_receiver.py").read_text(encoding="utf-8")
control = (ROOT / "runtime/standalone_control.py").read_text(encoding="utf-8")
ui = (DEPLOY / "ui_sw/ui_render.cpp").read_text(encoding="utf-8")
touch = (DEPLOY / "board_package/touch_mode_control.hpp").read_text(encoding="utf-8")
freq = (DEPLOY / "board_package/frequency_control.hpp").read_text(encoding="utf-8")
live = (DEPLOY / "board_package/board_ui_live_rml24_final.cpp").read_text(encoding="utf-8")
event = (DEPLOY / "rml24_final/runtime/ui_event.py").read_text(encoding="utf-8")
state_map = (DEPLOY / "board_package/ui_state_map.hpp").read_text(encoding="utf-8")
render_hpp = (DEPLOY / "ui_sw/ui_render.hpp").read_text(encoding="utf-8")

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
    "honest_recovered_iq_measurements": all(x in event for x in (
        '"display_measurements"', '"model_rms"', '"occupied_bw_hz"',
        '"spectral_centroid_hz"')),
    "measurements_reach_ui": "st.meas.valid = r.has_measurements" in state_map,
    "no_fake_snr_or_adc_dbfs": "SNR (est)" not in ui and '"dBFS"' not in ui,
    "estimates_are_labelled": '"SPECTRUM ESTIMATES", "EST"' in ui,
    "keypad_below_title": "kKeyY0 = 142" in render_hpp,
    "editor_cancelled_off_page": "freq_state.cancel_editor()" in live,
    "five_page_navigation": '"CLASSIFY", "MEASURE", "WATERFALL", "CONSTELLATION", "TUNING"' in ui,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
if failed:
    raise SystemExit("static audit failed: " + ", ".join(failed))
print(f"static_audit: PASS {len(checks)}/{len(checks)}")
