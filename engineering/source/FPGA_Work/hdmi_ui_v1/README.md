# hdmi_ui_v1 — HDMI touch UI for RF modulation recognition

A C++ / Qt Quick (QML) touch UI that displays the recognition program's
per-frame results on an HDMI panel. The target is the **FMQL30TAI** board
(Zynq-7030 PS, **no GPU**), so the UI is designed for a software-rendered
framebuffer and 48 px touch targets.

The UI consumes **only** `ResultFrame` objects (JSON-Lines, one object per
line) — never any internal pipeline type — so the FPGA → NPU pipeline, the NPU
runtime, and the future SDR adapter all evolve independently behind one frozen
contract (`contracts/`).

## Layout

| Path | What |
|---|---|
| `contracts/` | The frozen wire contract: `result_frame.schema.json` (normative) + Qt-free `result_frame.hpp` (C++ mirror + `validate()`) |
| `src/` | Data sources and the consumer-side integrity layer (`data_source.hpp`, `frame_validator.hpp`, mock/file/socket sources, JSON-Lines codec) |
| `app/` | `FrameBridge` (C++↔QML), `SourceController` (source switching), `main.cpp` |
| `qml/` | Theme + components + `Main.qml` (1920×1080 layout) |
| `config/` | `qtquickcontrols2.conf` (Basic style) |
| `mock_data/` | Deterministic replay of all 8 scenarios (`.jsonl` + `manifest.json`) |
| `scripts/` | `generate_mock_data.py` — the deterministic mirror of `MockDataSource` |
| `tests/` | Python pytest suite + Qt-free C++ `test_contract` |

## Build

Requires Qt 5.15 (Core, Gui, Qml, Quick, QuickControls2) and a C++17 toolchain.

```sh
cmake -B build -DCMAKE_PREFIX_PATH=/path/to/Qt/5.15
cmake --build build
ctest --test-dir build          # runs the Qt-free contract test
./build/hdmi_ui_v1              # on a desktop, or on the board:
./build/hdmi_ui_v1 -platform linuxfb
QT_QUICK_BACKEND=software ./build/hdmi_ui_v1 -platform eglfs
```

The app starts with the `normal` mock scenario so the panel is never blank.
Switch sources at runtime from the bottom bar (mock scenario / JSON-Lines file
/ Unix socket stub).

## Data sources

- **Mock** — deterministic live simulation (`source == MOCK`), 8 scenarios.
- **File** — replays `mock_data/*.jsonl` (`source == FILE`).
- **Unix socket** — reserved stub for the SDR adapter (`source == SDR`); fails
  loudly until the hardware path is wired.

The `MOCK` badge is shown whenever a mock feed is active, so simulated data is
never mistaken for real RF.

## Mock scenarios

| Scenario | Behaviour |
|---|---|
| `normal` | one class (16QAM), high confidence, healthy |
| `modulation_switch` | class rotates BPSK → 16QAM → 64QAM → OFDM |
| `low_confidence` | correct class, low confidence (LOW CONF badge) |
| `sdr_disconnect` | SDR → disconnected, stream ends |
| `fpga_error` | FPGA → error, `counters.error` increments |
| `npu_timeout` | NPU → error, `counters.timeout` increments |
| `drop_overflow` | periodic frame-id gaps + overflow |
| `recovery` | normal → fault → recover |

## Tests

```sh
python -m pytest tests -q     # Python: schema, invariants, determinism, semantics
```

`tests/` validates every `mock_data/*.jsonl` line against the JSON schema, checks
the structural invariants and each scenario's semantics, verifies the manifest
hashes, and proves deterministic regeneration. `tests/frame_validator_mirror.py`
mirrors `validate()` / `FrameSequenceMonitor` / `StaleDetector` field-for-field
so the contract stays in lock-step with C++ even without a C++ toolchain.

## Verification status

The Python tests (28) pass on the host. The C++ / Qt code is **not yet
compile-verified** — this host has no C++ compiler — so the first action on a
host or board with a Qt 5.15 + C++17 toolchain must be `cmake -B build &&
cmake --build build && ctest --test-dir build`. See `REPORT.md` for the full
hand-off notes.
