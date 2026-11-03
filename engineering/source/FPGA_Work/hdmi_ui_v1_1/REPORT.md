# Test report & delivery notes — hdmi_ui_v1_1

## What actually ran (this machine)

This host has **Python 3.13.5 + pytest 8.3.4 + jsonschema 4.23.0** and a
Qt 5.15.2 **qmake/qmllint** (at `D:\Anaconda\Library\bin`), but **no C++ compiler
and no cmake**. The following ran for real, with real results:

| Check | Command | Result |
|---|---|---|
| Mock data generation | `python scripts/generate_mock_data.py` | 10 files + `manifest.json` written |
| Python mirror test suite | `python -m pytest tests/ -q` | **39 passed** |
| QML static check | `qmllint -I qml -I qml/components -I qml/theme qml/*.qml …` | **clean** (no warnings/errors on all 18 files) |

### Python tests (39) — what they assert

- `test_frame_validator_mirror.py` — `validate()` (contract_version, model_id,
  class count 8..16, duplicate/empty class names, scores length + range,
  predicted_class consistency, confidence range, NaN snr, fps, latencies),
  `FrameSequenceMonitor` (duplicate/reorder/gap/dropped), `StaleDetector`
  boundaries, and `LineBuffer` framing (split push, CRLF, oversized complete +
  partial).
- `test_json_result_frame.py` — V1.1 and legacy parse shapes, malformed JSON,
  non-object root, missing version, round-trip.
- `test_mock_data.py` — all 10 mock scenarios produce valid 10-class frames;
  normal monotonic; reorder `frame_id == step-2` at `step%40==20`; drop/overflow
  counters at `step%50==0`; stale = 30 frames; sdr_disconnect = 31 frames with a
  disconnected last frame; determinism; committed `mock_data/*.jsonl` all
  validate.

These assertions are the **line-for-line Python twin** of the C++ unit tests
(`tests/test_contract.cpp`, `test_sequence_monitor.cpp`, `test_stale.cpp`,
`test_line_buffer.cpp`, `test_mock.cpp`, `test_json_result_frame.cpp`), so a
passing pytest run is evidence for the same logic the C++ tests exercise.

## What could NOT run: C++/Qt build → `pending-qt-build`

```bash
cmake -B build && cmake --build build && ctest --test-dir build
```

requires a C++17 compiler and CMake, which are not present here. Per the delivery
requirement, the status is **`pending-qt-build`, not `ready`**. The `CMakeLists.txt`
builds the executable and six ctest targets; run the block above on any Qt 5.15 +
CMake host to promote the status to `ready`.

The board's own binary (`./hdmi_ui_v1_1 -platform linuxfb` /
`QT_QUICK_BACKEND=software ./hdmi_ui_v1_1 -platform eglfs`) also cannot be
exercised here, and the 1024×600 render check is therefore deferred to the board
(no Qt runtime on this host).

## Remaining risks

1. **`pending-qt-build`.** The C++ build/ctest and the real 1024×600 render have
   not been executed on this host; only the Python mirror + `qmllint` ran.
2. **Unix-socket path is unexercised end-to-end.** The framing/parse logic is
   unit-tested, but no live SDR adapter has streamed over a real socket here.
   `open()` never fails and reconnect is bounded, so the failure mode is benign,
   but the happy path is unverified against the actual adapter.
3. **SDR adapter still emits the V1 shape.** The UI accepts both shapes, but the
   adapter must be upgraded to V1.1 before the board hardware path is wired
   (documented in `contracts/README.md`; not done here, adapter is read-only).
4. **Touch calibration is board-specific** and must be done on the target (see
   `DEPLOY.md`).
5. **Font rendering on the board** depends on the deployed font set; the fixed
   pixel sizes were chosen for 1024×600 but were not visually verified there.

## Modified-file list

`hdmi_ui_v1_1/` is a **new, independent directory**. No file outside it was
changed — in particular `hdmi_ui_v1/`, the model, the SDR adapter, and all
FPGA/RTL/bitstream artifacts are untouched.

Files in the deliverable (relative to `hdmi_ui_v1_1/`):

```
CMakeLists.txt                          resources.qrc
conftest.py                             config/qtquickcontrols2.conf
contracts/result_frame.hpp              contracts/result_frame_v1_1.schema.json
contracts/README.md
src/data_source.hpp                     src/frame_validator.hpp
src/json_result_frame.hpp               src/json_result_frame.cpp
src/jsonlines_data_source.hpp           src/jsonlines_data_source.cpp
src/line_buffer.hpp                     src/mock_data_source.hpp
src/mock_data_source.cpp                src/unix_socket_data_source.hpp
src/unix_socket_data_source.cpp
app/main.cpp                            app/frame_bridge.hpp
app/frame_bridge.cpp                    app/source_controller.hpp
app/source_controller.cpp
qml/Main.qml                            qml/MainPage.qml
qml/DiagnosticsPage.qml                 qml/theme/Theme.qml
qml/theme/qmldir
qml/components/{TopBar,TabButton,PanelFrame,ActionButton,StatusPill,StatusPanel,
               ClassHeader,ProbabilityBars,LatencyPanel,CountersPanel,EventLog,
               SourceBar}.qml
scripts/generate_mock_data.py           scripts/compute_manifest.py
tests/{test_contract,test_sequence_monitor,test_stale,test_line_buffer,
       test_mock,test_json_result_frame}.cpp
tests/frame_validator_mirror.py         tests/test_frame_validator_mirror.py
tests/test_json_result_frame.py         tests/test_mock_data.py
mock_data/{normal,modulation_switch,low_confidence,stale,reorder,drop_overflow,
           fpga_error,npu_timeout,sdr_disconnect,recovery}.jsonl
mock_data/manifest.json
README.md                               DESIGN.md
REPORT.md                               DEPLOY.md
sha256_manifest
```

Per-file sha256 is in `sha256_manifest` (regenerated by
`scripts/compute_manifest.py`).
