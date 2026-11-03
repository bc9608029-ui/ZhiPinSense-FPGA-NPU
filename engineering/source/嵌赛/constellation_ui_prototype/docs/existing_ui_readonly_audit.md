# Existing UI — Read-Only Audit (Phase 0)

Audit date: 2026-10-16. All paths below were READ ONLY; nothing in the reference
trees was modified. This audit answers the 8 Phase-0 questions for the UI that is
actually deployed on the M29 RML23 board, and distinguishes it from the older
Qt-based UI that predates it.

## 1. Qt 5 or Qt 6?

**The current M29 RML23 board UI uses NO Qt at all.** It is a hand-written
direct-framebuffer renderer in C++ (`ui_sw/`), drawing into an ordinary RGB565
buffer and submitting it via a `DirectFramebufferBackend` (`ui_sw/direct_framebuffer_backend.hpp`).

- `ui_sw/ui_render.hpp` — "This module is device-independent: it only draws into a
  `ui::Canvas` (an ordinary RGB565 buffer). The board programs render into the
  staging framebuffer and submit via `DirectFramebufferBackend::submit_frame()`."
- `ui_sw/font_atlas.hpp` — "The board does NO FreeType: `draw_text()` here only
  performs RGB565 integer alpha blend."

The *historical* Qt UI (the project's earlier HDMI UI, superseded on this board) is
**Qt 5.15**:

- `F:\FPGA_Work\hdmi_ui_v1_1\CMakeLists.txt` line 13:
  `find_package(Qt5 5.15 COMPONENTS Core Gui Qml Quick QuickControls2 Network REQUIRED)`

**Decision for this prototype (recorded, not silently assumed):** the task says to
prefer the same Qt major version as the existing board UI. The existing *board* UI
has no Qt version to copy, so this prototype targets **Qt 5.15** to match (a) the
project's historical Qt UI (`hdmi_ui_v1_1`, Qt 5.15 QML) and (b) the only Qt
available in this build environment (`D:\Anaconda\Library`, Qt 5.15.2).

## 2. QML, QWidget, or mixed?

- Current M29 board UI: **neither** — custom C++ `ui::Canvas` (RGB565) renderer.
- Historical UI: **QML** (`hdmi_ui_v1_1/qml/Main.qml`, `MainPage.qml`,
  `DiagnosticsPage.qml`, components under `qml/components/`), no QWidget.
- This prototype: **QML** (pages, panels, controls) + a **C++ QQuickItem** scatter
  render component for the high-frequency constellation points.

## 3. CMake or qmake build?

- Board UI: **CMake** (cross-compiled against the iCraft SDK; the board CMakeLists
  link NPU backends + libiio, no Qt). Example:
  `F:\FPGA_Work\sdr_full_chain_12class_ui_v3_m19\work\pkg\board_package\CMakeLists.txt`
  (no `find_package(Qt...)` at all — the UI is not Qt).
- Historical Qt UI: **CMake** (`hdmi_ui_v1_1/CMakeLists.txt`, `find_package(Qt5...)`).
- This prototype: **CMake** (primary) with the same Qt5 package names; the Qt-free
  test target also builds under plain `g++` via a minimal Makefile path (documented
  in README).

## 4. Board screen resolution

**1280×720** (logical), confirmed by:

- `ui_sw/ui_layout.hpp`:
  `constexpr int kScreenW = 1280; constexpr int kScreenH = 720;`
- `ui_sw/ui_render.hpp` touch mapping comment:
  `mapping_x = "raw_x*1280/4095"`, `mapping_y = "raw_y*720/4095"`.

The same file also records the frozen layout bands: top status bar y=0..71, info
strip y=558..624, bottom nav y=630..719 (nav band >=64 px touch targets).

## 5. Current UI socket message structure

The board system emits **one JSON object per line** over an **AF_UNIX SOCK_STREAM**
socket (path per the task: `/run/sdr_amr_ui_rml23.sock`). Authoritative files:

- `sdr_adapter/ui_report.hpp` (record serializers) and
  `sdr_adapter/unix_socket_sink.hpp` (non-blocking, never-stall JSON-lines socket).

Record kinds (field `"type"`):
- `result` — one inference. For RML23 the serializer is `result_frame_rml23_line()`
  with schema tag `"version":"rml23-chain-v2"`. Fields (all flat): `type`,
  `version`, `frame_id`, `timestamp_us`, `model_mode` (`RML23-AMSSB-MERGED`),
  `class_count`, `argmax_idx`, `argmax_class`, `confidence`, `merged_23_top1`,
  `raw_24_top1`, `deployment_mode`, `expert_enabled`, `expert_result`,
  `probabilities[]`, `snr_db`, `quality`, `model_sha`, `mock`, `source`, `e2e_us`,
  `preprocess_us`, `classify_us`, `overflow`, `dropped`, `discontinuity`,
  `short_frame`, `presence_state`, `level_mode`, `model_scale`, `rf_gain_db`,
  `work_mode`, `run_state`, and a nested `measurements{}` object (M3 DSP: rms/peak/
  papr/power/noise_floor/snr_est/occupied_bins/spectral_centroid/occupied_bw/
  model_rms).
- `status` — state transition (`state`, `detail`).
- `metric` — scalar (`name`, `value`, `unit`).
- `state` — work-mode / run-state / presence heartbeat (M6 control).

**Red line honored:** this phase does NOT modify or implement against that socket
protocol; the future live-integration interface doc only *defines* the abstract
`IqFrameSource` boundary.

## 6. GPU / OpenGL

**No GPU.** The board UI is software RGB565 framebuffer rendering
(`DirectFramebufferBackend`). The historical Qt UI confirms this explicitly:

- `hdmi_ui_v1_1/CMakeLists.txt` lines 9-12: "The UI has no GPU on the FMQL30TAI,
  so run the board binary with a software-rendered platform:
  `./hdmi_ui_v1_1 -platform linuxfb`, `QT_QUICK_BACKEND=software ... -platform eglfs`."

For this **desktop** offline prototype the render budget assumes a software /
compositing OpenGL path is acceptable, but the scatter component is written as a
QSG geometry node (no QML JS per point, no Canvas). The audit for the board
fallback is recorded in the main prototype audit (`docs/M29_RML23_UI_CONSTELLATION_OFFLINE_PROTOTYPE_AUDIT.md`).

## 7. Chinese font + theme

- Theme: `ui_sw/ui_theme.hpp` — "Style A (modern scientific instrument)" semantic
  RGB565 tokens on a **dark, high-contrast** palette:
  background `#0F141B`, surface `#1A212B`, surface_alt `#121A24`, outline `#2A3542`,
  text_primary `#E7ECF2`, text_secondary `#8B98A8`, interactive/selected `#4A90E2`,
  success `#3DDC84`, warning `#E8A93C`, error `#E5605F`, disabled `#5A6672`.
  Contrast ratios (>=4.5:1) are asserted in `host_tests/test_ui_layout_m19.cpp`.
- Font: `ui_sw/font_atlas.hpp` — pre-rasterized **DejaVu Sans**, **charset =
  printable ASCII 32..126 only (95 glyphs)**. **The board UI has no Chinese glyphs;
  all board UI text is ASCII/English.**

Implication for this prototype: it must supply its own Simplified-Chinese rendering.
The desktop Qt prototype uses the platform font stack (which provides CJK glyphs)
with all user-visible strings wrapped in `qsTr()` (Simplified Chinese as the
source-string fallback). The Style A semantic palette is reused as the QML theme so
the prototype visually matches the board's dark instrument theme.

## 8. Where classification / confidence / CFO / SRO enter the UI

- **Classification + confidence** enter the UI from `rf::ResultFrame`
  (`sdr_adapter/result_frame.hpp`): `argmax_class`, `confidence`,
  `merged_23_top1`, `raw_24_top1`, serialized by `result_frame_rml23_line()`
  (`sdr_adapter/ui_report.hpp`) and delivered over the JSON-lines socket. The board
  renderer consumes them through `ui_state_map.hpp` into `ui::UiState`
  (`ui_sw/ui_render.hpp`: `top1`, `conf`, `dist`, `model_mode`, `class_count`).
- **CFO / SRO / gain** are NOT in the board UI result record. They are recovery
  metrics computed in the sync/recovery layer, `board_package/iq_rf_sync_recovery.hpp`
  (`struct PerFileRecovery { coarse_cfo_hz, gain_mag, phase_deg, cfo_hz, sro_ppm,
  phase_drift_deg, training_corr, training_residual, payload_gain_mag,
  payload_rms_gain_mag, ... }`; also `iq_dual_sdr_coarse_cfo_recovery.hpp`), and are
  not rendered by the current board UI. In this prototype they arrive as fields of
  the offline JSON sidecar (see `docs/data_format.md`).

## Source files this audit is grounded in (all read-only)

- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\ui_sw\ui_render.hpp`
- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\ui_sw\ui_theme.hpp`
- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\ui_sw\ui_layout.hpp`
- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\ui_sw\font_atlas.hpp`
- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\ui_sw\direct_framebuffer_backend.hpp`
- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\sdr_adapter\ui_report.hpp`
- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\sdr_adapter\unix_socket_sink.hpp`
- `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\sdr_adapter\result_frame.hpp`
- `F:\FPGA_Work\hdmi_ui_v1_1\CMakeLists.txt` (Qt 5.15, QML, software rendering)
- `F:\FPGA_Work\sdr_full_chain_12class_ui_v3_m19\work\pkg\board_package\CMakeLists.txt` (board CMake, no Qt)
