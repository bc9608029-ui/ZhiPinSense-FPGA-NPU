# hdmi_ui_v1_1 — HDMI touch UI (pre-deployment)

Independent successor to `hdmi_ui_v1` that completes the pre-deployment
preparation for the FMQL30TAI board: native **1024×600** layout, a
**model-generic ResultFrame V1.1** contract, a connectable/reconnecting Unix
socket data path, and a test suite that runs **now** on the host with only a
Python toolchain (no Qt/C++ compiler).

Nothing outside this directory is modified. `hdmi_ui_v1`, the model, the SDR
adapter, the FPGA/RTL/bitstream, and every other project are left untouched.

## Status

| Item | Status |
|---|---|
| Contract + mock + integrity logic (Qt-free C++) | written, verified via Python mirror |
| QML (1024×600, 10-class, dark/flat) | written, `qmllint` clean |
| Python test suite | **39 passed** (pytest) |
| Mock JSONL replay data | generated (`mock_data/*.jsonl` + `manifest.json`) |
| C++/Qt build (`cmake` + `ctest`) | **`pending-qt-build`** — no C++/cmake toolchain on this machine |
| Board / SDR / model training | **not performed** (out of scope, prohibited) |

> **`pending-qt-build`**, not `ready`: this host has no C++ compiler or `cmake`,
> so the `cmake --build` / `ctest` path could not be executed. The C++ logic is
> verified through a line-for-line Python mirror (`tests/frame_validator_mirror.py`)
> whose assertions are identical to the C++ unit tests. Run section **Build & test**
> below on a machine with Qt 5.15 + CMake to close this out.

## Layout

```
hdmi_ui_v1_1/
├── contracts/              ResultFrame V1.1 (schema.json + Qt-free hpp + README)
├── src/                    Qt-free contract/integrity + data sources
│   ├── data_source.hpp        abstract DataSource (mock / file / socket)
│   ├── frame_validator.hpp    FrameSequenceMonitor + StaleDetector (Qt-free)
│   ├── json_result_frame.*    V1.1 + legacy JSON-Lines parse (Qt5::Core only)
│   ├── jsonlines_data_source.*  FILE replay source
│   ├── line_buffer.hpp        Qt-free byte → line framer (strict size limit)
│   ├── mock_data_source.*     deterministic 10-scenario 10-class MOCK
│   └── unix_socket_data_source.*  live SDR path (QLocalSocket, reconnect)
├── app/                    C++ ↔ QML bridge + source controller + entry point
├── qml/                    QML (Main / Diagnostics / theme / components)
├── config/                 qtquickcontrols2.conf (Basic style)
├── scripts/                generate_mock_data.py + compute_manifest.py
├── tests/                  C++ tests (ctest) + Python mirror tests (pytest)
├── mock_data/              generated replay JSONL (10 scenarios) + manifest.json
├── CMakeLists.txt          Qt 5.15 + C++17, executable + ctest
├── resources.qrc           QML resource bundle
└── sha256_manifest         per-file sha256 of the deliverable
```

## The ResultFrame V1.1 contract

Each line of the JSON-Lines stream is one frame. V1.1 is **model-generic**: a
frame carries its own `class_names` (8..16) and `scores`, so the UI draws
however many classes a frame declares and never hardcodes a list.

```json
{"contract_version":2,"model_id":"mock-10class-v1.1","frame_id":7,
 "timestamp_ns":1700000000000000000,"source":"MOCK",
 "class_names":["AM-DSB","WBFM","2FSK","GFSK","BPSK","QPSK","8PSK","16QAM","64QAM","OFDM"],
 "scores":[0.01,0.01,0.01,0.01,0.01,0.01,0.01,0.9,0.02,0.01],
 "predicted_index":7,"predicted_class":"16QAM","confidence":0.9,
 "snr_db":18.0,"center_frequency_hz":2400000000.0,"sample_rate_hz":128000.0,
 "latency_us":{"sdr_capture":1,"resample_frame":1,"plddr_transfer":1,
               "fpga_process":1,"npu_infer":1,"end_to_end":5},
 "fps":15.0,
 "counters":{"dropped":0,"overflow":0,"duplicate":0,"reorder":0,"timeout":0,"error":0},
 "sdr_status":"ok","fpga_status":"ok","npu_status":"ok"}
```

See `contracts/README.md` and `contracts/result_frame_v1_1.schema.json` for the
full reference. The parser also accepts the legacy 8-class V1 shape
(`schema_version`, `class_id`, `class_name`, `probabilities`) so old replays keep
working.

## Data sources

| Source | Kind | `source` | Behaviour |
|---|---|---|---|
| **Mock** (default) | `mock` | `MOCK` | deterministic 10-class, 10 scenarios |
| **JSONL file** | `file` | `FILE` | replays `mock_data/*.jsonl` |
| **Unix socket** | `unix_socket` | `SDR` | connects/reconnects to the SDR adapter |

The **MOCK** badge is always prominent so simulated data is never mistaken for
live RF. The 10 mock scenarios cover normal, modulation switch, low confidence,
stale (30 healthy frames then silence), out-of-order, drop/overflow, FPGA error,
NPU timeout, SDR disconnect, and recovery.

## Build & test

### Host (this machine — Python only)

```bash
python scripts/generate_mock_data.py    # regenerate mock_data/*.jsonl
python -m pytest tests/ -q              # 39 tests (contract, sequence, stale,
                                        #   line framing, JSON parse, 10-class mock)
# QML static check (Qt 5.15 qmllint, no compile):
#   qmllint -I qml -I qml/components -I qml/theme qml/<file>.qml   (all clean)
```

### Board / Qt host (requires Qt 5.15 + CMake)

```bash
cmake -B build
cmake --build build
ctest --test-dir build          # contract, sequence_monitor, stale, line_buffer,
                                # mock, json_result_frame
./hdmi_ui_v1_1 -platform linuxfb
QT_QUICK_BACKEND=software ./hdmi_ui_v1_1 -platform eglfs
```

The Qt-free tests (`test_contract`, `test_sequence_monitor`, `test_stale`,
`test_line_buffer`, `test_mock`) build with only a C++17 toolchain; only
`test_json_result_frame` needs Qt5::Core.

## Launch

```bash
# board (no GPU on the Zynq-7030 PS)
./hdmi_ui_v1_1 -platform linuxfb
QT_QUICK_BACKEND=software ./hdmi_ui_v1_1 -platform eglfs   # if eglfs is built

# host development
./hdmi_ui_v1_1
```

Deployment, touch calibration, remaining risks and the checklist are in
[`DEPLOY.md`](DEPLOY.md); design rationale in [`DESIGN.md`](DESIGN.md); the test
report and modified-file list in [`REPORT.md`](REPORT.md).
