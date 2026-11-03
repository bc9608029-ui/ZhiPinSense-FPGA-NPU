# M29 RML24 fix10class24-waterfall1 — Integration Notes

Status: `M29-RML24-FIX10CLASS24-WATERFALL-READY-FOR-INTEGRATION` (host-only; API-only;
never RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_*).

These notes tell the board live-loop integrator exactly how to wire the
spectrum + waterfall page into `board_ui_live_rml23` (or its RML24 successor)
without changing any red-line path.  The waterfall is a bypass-read consumer of
the display spectrum: it performs no FFT, no recovery, no classification, and
touches none of the BF16 model / 24→23 merge / 0.100 gate / dual-SDR sync code.

## 1. Build wiring (required)

`ui_render.cpp` now calls `ui::render_spectrum_waterfall()` when
`render_parameters()` receives a non-null `WaterfallHistory*`.  Therefore every
target that links `ui_sw/ui_render.cpp` MUST also link the new TU
`ui_sw/waterfall_render.cpp`.  `host_tests/build_host_tests.sh` already does
this.  Any other build script that links `ui_render.cpp` (e.g. the legacy
`_baseline_ui.sh`, `_ui_redesign.sh`, `_snap_rml23.sh` helpers) must add
`../ui_sw/waterfall_render.cpp` too if it is ever revived.

## 2. Data flow

```
DspMeasure::measure_into(iq, 1024, scratch)
   -> FrameMeasurements.spectrum_dbfs_x4[256] (+ metadata)      [Phase B, no 2nd FFT]
   -> ui_report.hpp serializes 6 optional spectrum fields        [Phase C]
   -> result_frame_v2_parse.hpp parses them fail-closed          [Phase C]
   -> ui_state_map.hpp copies into UiState::meas                 [Phase C]
   -> live loop pushes dbfs_x4 into WaterfallHistory              [Phase D]
   -> render_parameters(canvas, theme, state, &history)          [Phase E]
        -> render_spectrum_waterfall(...)
```

The display spectrum is derived from the SAME 1024-pt FFT power that already
computes noise floor / peak prominence / occupied BW / centroid.  Stop condition:
**no second FFT** — `compute_display_spectrum()` reuses `MeasureScratch::power`.

## 3. Live-loop usage (pseudocode)

```cpp
ui::WaterfallHistory history;   // fixed 128 x 256 x 2 = 64 KiB, no heap growth

// on each new ResultFrame (already parsed fail-closed):
if (waterfall_advance_on_presence(frame.presence_state)) {
    const auto& m = frame.measurements;
    if (m.spectrum_valid) {
        history.push(m.spectrum_dbfs_x4, frame.frame_id, now_ms());
    }
    // else: SIGNAL_PRESENT/NO_SIGNAL with no spectrum -> nothing is faked.
}

// SIGNAL_LOST: do NOT push (keeps the short history, no fake rows).
// INVALID:      do NOT push (the page draws "RX ERROR" with no heatmap).
// STALE:        do NOT push (the page freezes and draws "STALE / DATA TIMEOUT").

// producer reconnect / data socket reopened:
history.clear();

// render (page 1 = PARAMETERS/SPECTRUM):
ui::render_parameters(canvas, theme, state, &history);
```

Rules enforced inside `WaterfallHistory::push()` (all host-tested):
- 10 Hz row-advance cap (100 ms minimum between accepted rows);
- same `frame_id` never advances twice;
- a regressed `frame_id` is rejected (producer reset cannot pollute history);
- values are defensively clamped into [-480, 0] (dBFS x4).

## 4. Spectrum field contract (Phase C)

Optional fields inside the `measurements` object of a v3/rml23/rml24 result line:

| field                     | type   | value                                            |
|---------------------------|--------|--------------------------------------------------|
| `spectrum_valid`          | bool   | true only when a valid 1024-pt display spectrum exists |
| `spectrum_fft_length`     | int    | 1024 (fixed)                                     |
| `spectrum_bin_count`      | int    | 256 (fixed)                                      |
| `spectrum_dbfs_x4`        | int[256] | dBFS x4, integer in [-480, 0] = [-120, 0] dBFS, 0.25 dB resolution, fftshift order (bin 0 = -fs/2, bin 128 = DC, bin 255 = +fs/2) |
| `spectrum_sample_rate_hz` | double | > 0 (e.g. 2560000)                               |
| `spectrum_center_hz`      | double | RF center for labelling                          |

Parse is **fail-closed**: length != 256, any out-of-range/non-integer value,
`bin_count != 256`, `fft_length != 1024`, or missing sample_rate/center while
`spectrum_valid == true` rejects the whole record.  Records with NO spectrum
keys still parse (old messages keep working; `spectrum_valid == false`).

Report label (drawn on the page): "display spectrum; relative dBFS/bin; not
calibrated W/Hz".  The page is a relative power view — it is NOT a calibrated
W/Hz PSD.

## 5. Page behaviour by state (Phase E)

- SIGNAL_PRESENT: advance + display (curve, heatmap, metrics).
- NO_SIGNAL: advance + display the real ambient-noise spectrum; NO stale
  classification is drawn (top1/conf are cleared by ui_state_map).
- ACQUIRING: advance + "ACQUIRING" overlay chip.
- SIGNAL_LOST: keep the short existing history (no fake rows), "SIGNAL LOST" overlay.
- INVALID: stop advancing, "RX ERROR" text in error ink over a surface_alt void
  (no heatmap).
- STALE: freeze, "STALE / DATA TIMEOUT" overlay.

Status is always text + color; color is never used alone for status.

## 6. Layout (fixed geometry, 1280x720)

- spectrum curve top-left (y 116..212), 0 dBFS top / -120 dBFS bottom;
- waterfall heatmap middle-left (y 232..487), 256 cols x 3 px, 128 rows x 2 px,
  oldest top / newest bottom, viridis-like RGB565 LUT (dark violet -> yellow);
- power scale TEXT on the left gutter ("dBFS", "0", "-60", "-120");
- frequency axis TEXT below the heatmap ("-1.28 MHz", "0", "+1.28 MHz" for
  fs = 2.56 MHz);
- side metrics right column: Noise floor, Peak prominence, Occupied BW,
  Centroid, Sample rate, Center freq, plus the W/Hz disclaimer.

## 7. Snapshot harness (Phase F)

`host_tests/make_ui_waterfall_snapshots` renders six pages into
`results/waterfall1/*.ppm` (converted to PNG by `host_tests/ppm_to_png.py`):
four REAL recovered-payload spectra (BPSK/4ASK/64QAM/AM-DSB-WC from the
gate-rejected 24-class captures) and two SYNTHETIC (AWGN noise, two-tone).
Every row goes through the same `DspMeasure` derivation; the expected TX is
never drawn as RX.  `results/waterfall1/performance.json` records render time
and the fixed 64 KiB history footprint.
