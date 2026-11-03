# M29 RML24 fix10class24-waterfall1 — Host Audit

Date: 2026-10-18
Status: **`M29-RML24-FIX10CLASS24-WATERFALL-READY-FOR-INTEGRATION`**

Forbidden by ceiling: RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_* /
RUNTIME-INTEGRATED.  Host-only, API-only.  The board was never touched; no SDR
was opened; the board NIC was never disabled.

## 1. Scope

Add a real-time spectrum + waterfall UI component (page 1 = PARAMETERS/SPECTRUM)
on top of the existing 1024-pt FFT in `dsp_measure.hpp`, with a bounded ring
history and a board-lightweight RGB565 renderer.  The waterfall is a
**bypass-read** consumer of the spectrum: it performs no FFT of its own, no
recovery, no classification, and touches no red-line path.

Work tree: `F:\嵌赛\fix10class24_waterfall1_work\sdr_rml24_fix10class24_waterfall1`.
Baseline (`fix10class24_rxresidual_audit1_work`), nosignal and dualsdr trees
were not touched.

## 2. Phases delivered

- **Phase A (freeze):** pinned the existing DSP/FFT inputs — 1024-pt FFT,
  2.56 MHz sample rate, 1280x720 canvas, full-scale 2048 counts.  Defined the
  six optional spectrum fields (below).
- **Phase B (derive):** `sdr_adapter/dsp_measure.hpp::compute_display_spectrum`
  derives the 256-bin display spectrum from the SAME 1024-pt FFT power
  (`MeasureScratch::power`): fftshift -> group-of-4 MAX (not average) ->
  `10*log10(max_power / full_scale^2)` -> clamp [-120,0] dBFS -> x4 integer.
  **No second FFT.**  The existing noise_floor_dbfs / psd_peak_prominence_db /
  occupied_bins / occupied_bw_hz / spectral_centroid_hz are untouched (the
  display derivation runs strictly after them).
- **Phase C (protocol):** `sdr_adapter/ui_report.hpp` serialises the six fields;
  `board_package/result_frame_v2_parse.hpp` parses them fail-closed (length,
  range, integer, metadata, fft=1024, bins=256); `ui_state_map.hpp` copies them
  into `UiState::meas`; `ui_dirty_state.hpp` diffs them.  Legacy records with no
  spectrum keys still parse (spectrum_valid=false).
- **Phase D (history):** `ui_sw/waterfall_history.hpp` — fixed 128 x 256 x 2 =
  64 KiB ring (no heap, no growth), 10 Hz advance cap, same-frame_id dedup,
  frame-id regression rejection, `clear()` for reconnect, defensive clamp.
- **Phase E (render):** `ui_sw/waterfall_render.{hpp,cpp}` + `ui_render.cpp`
  `render_parameters(..., const WaterfallHistory*)`.  Spectrum curve top-left,
  waterfall heatmap middle-left (viridis-like RGB565 LUT, dark violet -> yellow),
  side metrics, power scale TEXT (dBFS) and frequency axis TEXT (MHz).  Status
  is text-first: INVALID -> "RX ERROR" (no heatmap), STALE -> "STALE / DATA
  TIMEOUT", ACQUIRING -> "ACQUIRING", SIGNAL_LOST -> "SIGNAL LOST".
- **Phase F (snapshots):** `host_tests/make_ui_waterfall_snapshots` renders six
  pages from real recovered-payload IQ (BPSK/4ASK/64QAM/AM-DSB-WC) plus two
  synthetic cases, all through the same `DspMeasure` derivation.

## 3. Spectrum field contract

`spectrum_valid` (bool), `spectrum_fft_length` (1024), `spectrum_bin_count`
(256), `spectrum_dbfs_x4[256]` (int, [-480,0] = [-120,0] dBFS, 0.25 dB,
fftshift order), `spectrum_sample_rate_hz` (>0), `spectrum_center_hz`.
Optional; old messages keep working.  Report label: "display spectrum; relative
dBFS/bin; not calibrated W/Hz".

## 4. Files changed / added (red-line diff, intended only)

Changed (vs `fix10class24_rxresidual_audit1_work`):
- `sdr_adapter/dsp_measure.hpp` (Phase B)
- `sdr_adapter/ui_report.hpp` (Phase C)
- `board_package/result_frame_v2_parse.hpp` (Phase C)
- `board_package/ui_state_map.hpp` (Phase C)
- `board_package/ui_dirty_state.hpp` (Phase C)
- `ui_sw/ui_render.hpp` (Phase E hook)
- `ui_sw/ui_render.cpp` (Phase E delegation)
- `host_tests/build_host_tests.sh` (link `waterfall_render.cpp` + register tests)
- `host_tests/run_tests.sh` (register tests + snapshots + PPM->PNG)
- `host_tests/make_ui_m19_snapshots.cpp` (wrap `render_parameters` in a 3-arg
  lambda — its address was taken as a 3-arg function pointer)
- `host_tests/make_ui_rml23_snapshots.cpp` (same wrap)

Added:
- `ui_sw/waterfall_history.hpp`, `ui_sw/waterfall_render.hpp`,
  `ui_sw/waterfall_render.cpp`
- `host_tests/test_waterfall_spectrum.cpp`, `test_waterfall_history.cpp`,
  `test_waterfall_protocol.cpp`, `test_waterfall_render.cpp`
- `host_tests/make_ui_waterfall_snapshots.cpp` (rewritten; replaces the prior
  partial-work version that used the deleted `ui_waterfall.hpp` API)
- `host_tests/ppm_to_png.py` (PPM -> PNG, PIL)
- `results/waterfall1/` (6 PNG + performance.json)
- `docs/M29_RML24_FIX10CLASS24_WATERFALL1_AUDIT.md`,
  `docs/M29_RML24_FIX10CLASS24_WATERFALL1_INTEGRATION.md`

Removed (prior partial work that deviated from spec): `ui_sw/ui_waterfall.hpp`,
`host_tests/test_waterfall_bins.cpp`, `test_waterfall_ring.cpp`,
`test_waterfall_state.cpp`, `test_waterfall_viridis.cpp` (and their build/run
registrations).

`diff -rq` (excluding bin/__pycache__/.pytest_cache/results/waterfall1) shows
ONLY the files above.  No red-line file (BF16 model JSON/RAW, label order,
24->23 merge, 0.100 gate, dual-SDR sync/CFO/gain/IQ recovery, canonical frames,
TX -40 dB cap, classification window/model input, NPU inference,
training/quantization, FPGA RTL) was modified.

## 5. Test results

Waterfall test files (g++ -O2 -Wall -Wextra -Werror):

| file                        | pass / fail |
|-----------------------------|-------------|
| test_waterfall_spectrum     | 13 / 0      |
| test_waterfall_history      | 31 / 0      |
| test_waterfall_protocol     | 17 / 0      |
| test_waterfall_render       | 13 / 0      |

Covered behaviours (spec's required cases, plus extras):
- spectrum: metadata, [-480,0] range, exact fftshift+group-MAX reference (tone
  and AWGN), fftshift direction (positive/negative tone), MAX-not-average,
  non-1024 fail-closed.
- history: bounded 128, fixed ~64 KiB memory, 10 Hz cap, same-frame dedup,
  frame regression, clear(), ring ordering, clamping, presence advance policy.
- protocol: round-trip, legacy compatible, fail length 255, fail out-of-range,
  fail non-integer, fail missing metadata, fail bin_count 255, fail fft_length
  512, message size (< 4 KiB; measured 2165 bytes).
- render: full-page pixel content, viridis LUT endpoints (dark->bright),
  INVALID "RX ERROR" (no heatmap), STALE/ACQUIRING overlay text, power-scale
  text, frequency-axis text, metrics text.

## 6. Snapshots (Phase F)

`results/waterfall1/`:
- `bpsk_waterfall.png` — REAL RX (source_index 1500, class 3 BPSK)
- `4ask_waterfall.png` — REAL RX (source_index 500, class 1 4ASK)
- `qam_waterfall.png`  — REAL RX (source_index 7000, class 14 64QAM)
- `am_waterfall.png`   — REAL RX (source_index 9500, class 19 AM-DSB-WC)
- `noise_waterfall.png` — SYNTHETIC AWGN (host-generated)
- `dual_tone_waterfall.png` — SYNTHETIC two-tone (host-generated)

`performance.json`: 6 images; render_total_us 4831; render_max_us 2073
(2.1 ms worst full-page render); history 65584 bytes fixed (128x256x2 + ring
meta); real RX = 52 consecutive 1024-sample windows per image; synthetic =
128 rows (full ring).

Honest substitution note: the four "real RX" images use the board's RECOVERED
payload f32 (counts domain, full-scale 2048) from the gate-rejected 24-class
captures (`PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`, 0.10 gate).  They are real RX
spectra, but they are the rejected captures — the expected TX is never drawn as
RX.  Noise and dual-tone are synthetic host IQ through the same derivation.
The top-1 class label is intentionally left empty in every snapshot (no
classification is presented for gate-rejected or synthetic input).

## 7. Stop conditions

1. no second FFT — confirmed (compute_display_spectrum reuses s.power).
2. 256-pt direction matches Python reference — confirmed (exact reference test).
3. real RX continuous waterfall — confirmed (52 real windows per image).
4. bounded history, no growth — confirmed (fixed 64 KiB, 128-row cap test).
5. old/no-spectrum messages compatible — confirmed (legacy round-trip).
6. no-signal/lost/error/STALE never fake data — confirmed (history policy +
   render overlay tests; status is text-first).
7. classification/model-input byte-identical — confirmed (no change to model
   input path, NPU calls, or classification window; display derivation is
   additive after existing measurements).
8. full host regression passes — see §5 / final line below.
9. no red-line files modified — confirmed (§4 diff).
10. integration notes complete — `..._WATERFALL1_INTEGRATION.md`.

## 8. Full host regression

BUILD_RC=0, RUN_RC=0, "ALL HOST TESTS PASSED" (full `build_host_tests.sh &&
run_tests.sh`, plus the six snapshot PNGs and `results/waterfall1/performance.json`).
