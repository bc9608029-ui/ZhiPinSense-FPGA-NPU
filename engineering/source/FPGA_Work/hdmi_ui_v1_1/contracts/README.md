# ResultFrame V1.1 contract

The single data contract between the recognition program (FPGA → NPU → SDR
adapter) and the HDMI touch UI. The UI consumes **only** `ResultFrame` objects —
nothing else — so the pipeline, the NPU runtime, and the SDR adapter evolve
independently behind this interface.

## Normative source

- `result_frame_v1_1.schema.json` — JSON Schema (draft-07) of the V1.1 wire
  format. One object per JSON-Lines line.
- `result_frame.hpp` — Qt-free C++ mirror (struct + enums + `validate()`).

The Python tests validate the mock data against the schema, so the schema is the
source of truth for both languages. Cross-field invariants that draft-07 cannot
express (`scores` length == `class_names` length, `predicted_class ==
class_names[predicted_index]`) are enforced by `validate()` and its Python mirror
(`tests/frame_validator_mirror.py`).

## What changed in V1.1

| V1 (`hdmi_ui_v1`) | V1.1 (`hdmi_ui_v1_1`) | Why |
|---|---|---|
| `schema_version: 1` | `contract_version: 2` | explicit versioned contract |
| — | `model_id` (string) | identify which model produced the frame |
| frozen 8-class order in UI | `class_names` carried per frame (8..16) | classes are model-specific and swappable |
| `probabilities` (8) | `scores` (len == `class_names`) | per-class scores, length follows the frame |
| `class_id` | `predicted_index` | index into the frame's own class list |
| `class_name` | `predicted_class` | == `class_names[predicted_index]` |

## Default class order (V1.1 mock)

```
AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM
```

This is the **mock default**, not a contract-wide freeze: the UI draws however
many classes each frame declares (8..16) and never hardcodes the list.

## Backward compatibility (old 8-class replay)

The parser (`src/json_result_frame.cpp`) also accepts the legacy V1 shape:

```
schema_version, class_id, class_name, probabilities (8)
```

over the legacy order `BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM`, and
normalises it into the V1.1 struct (legacy `model_id` is empty, which `validate()`
permits for `contract_version == 1`). Old `mock_data/*.jsonl` therefore replays
unchanged.

## Reused (read-only) from the SDR adapter

| UI field | Reused from | Meaning |
|---|---|---|
| `latency_us.*` keys | `perf::Stage` (`perf_stats.hpp`) | `sdr_capture, resample_frame, plddr_transfer, fpga_process, npu_infer, end_to_end` |
| `counters.dropped/overflow/duplicate/reorder` | `iq::SequenceStats` (`sequence_monitor.hpp`) | consumer-visible anomaly counters |
| `counters.timeout/error` | `pipeline::FailureClass` (`pipeline.hpp`) | `FpgaTimeout/NpuTimeout/FpgaError/NpuError` |
| `source` | `iq::Source` (`iq_frame.hpp`) | MOCK / FILE / SDR |
| framing | `ui::result_line/status_line/metric_line` (`ui_report.hpp`) | flat JSON, one line per event |

No SDR adapter file is modified. **Future sync note:** the SDR adapter's output
must be upgraded to emit the V1.1 shape (`contract_version`, `model_id`,
`class_names`, `scores`, `predicted_index`, `predicted_class`) instead of the V1
shape (`schema_version`, `class_id`, `class_name`, `probabilities`) before the
board hardware path is wired; the UI already accepts both, so this is not a
blocker for the UI itself.

## Field reference

| Field | Type | Notes |
|---|---|---|
| `contract_version` | int | `2` (V1.1); `1` = legacy, accepted for replay |
| `model_id` | string | non-empty for V1.1 |
| `frame_id` | uint64 | monotonic; gaps/repeats/reorders are consumer-detected |
| `timestamp_ns` | uint64 | producer wall-clock |
| `source` | enum | `MOCK` is never presented as real RF |
| `class_names` | string[8..16] | frame's own class list, unique |
| `scores` | float[] | len == `class_names`, each `[0,1]`, finite |
| `predicted_index` | int | argmax index into `class_names` |
| `predicted_class` | string | == `class_names[predicted_index]` |
| `confidence` | float | predicted-class confidence in `[0,1]`, finite |
| `snr_db` | float | estimated SNR |
| `center_frequency_hz` | float | RF center frequency |
| `sample_rate_hz` | float | 128000 per the frozen sampling contract |
| `latency_us` | object | 6 stage latencies (µs) |
| `fps` | float | pipeline frame rate |
| `counters` | object | 6 monotonic counters |
| `sdr_status` / `fpga_status` / `npu_status` | enum | `ok / warning / error / disconnected / unknown` |
| `spectrum_bins` | float[] | optional power spectrum |
| `message` | string | optional human-readable note |

## Validity rules (enforced by `validate()` and the tests)

- `contract_version ∈ {1,2}`; `model_id` non-empty when `2`.
- `class_names` has 8..16 unique, non-empty entries.
- `scores` has the same length as `class_names`; every entry finite in `[0,1]`.
- `predicted_index ∈ [0, len(class_names))` and `predicted_class ==
  class_names[predicted_index]`.
- `confidence` finite in `[0,1]`.
- Every float (`snr_db`, frequencies, `fps`, 6 latencies, `spectrum_bins`) is
  finite; latencies and `fps` are non-negative.
- NaN / Infinity / missing field / wrong enum → frame rejected (or counted as
  `counters.error`) and never drives the UI.
