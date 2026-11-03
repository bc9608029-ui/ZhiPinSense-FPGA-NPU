# ResultFrame contract

The single data contract between the recognition program (FPGA → NPU) and the
HDMI touch UI. The UI consumes **only** `ResultFrame` objects — nothing else —
so the pipeline, the NPU runtime, and the future SDR source can evolve
independently behind this interface.

## Normative source

- `result_frame.schema.json` — JSON Schema (draft-07) of the wire format. One
  object per JSON-Lines line, produced by the recognition program and consumed
  by `JsonLinesDataSource`.
- `result_frame.hpp` — Qt-free C++ mirror (struct + enums + `validate()` +
  class order). Reused unchanged on host tests and on the board.

The Python tests in `tests/` validate the schema against `mock_data/`, so the
schema is the source of truth for both languages.

## Reused (read-only) from the SDR adapter

| UI field | Reused from | Meaning |
|---|---|---|
| class order (8) | `deployment_contract.yaml` | `BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM` |
| `latency_us.*` keys | `perf::Stage` (`perf_stats.hpp`) | `sdr_capture, resample_frame, plddr_transfer, fpga_process, npu_infer, end_to_end` |
| `counters.dropped/overflow/duplicate/reorder` | `iq::SequenceStats` (`sequence_monitor.hpp`) | consumer-visible anomaly counters |
| `counters.timeout/error` | `pipeline::FailureClass` (`pipeline.hpp`) | `FpgaTimeout/NpuTimeout/FpgaError/NpuError` |
| `source` | `iq::Source` (`iq_frame.hpp`) | MOCK / FILE / SDR |
| framing | `ui::result_line/status_line/metric_line` (`ui_report.hpp`) | flat JSON, one line per event |

No SDR adapter file is modified; the names are copied into this contract so the
future SDR→UI bridge can map 1:1 without inventing a conflicting interface.

## Field reference

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | must equal `1`; bump = incompatible change |
| `frame_id` | uint64 | monotonic; gaps/repeats/reorders are consumer-detected |
| `timestamp_ns` | uint64 | producer wall-clock; drives staleness |
| `source` | enum | `MOCK` is never presented as real RF |
| `class_id` | 0..7 | index into the frozen class order |
| `class_name` | string | must match `class_id` |
| `confidence` | float | top-1 confidence in `[0,1]`, finite |
| `probabilities` | float[8] | per-class, each `[0,1]`, finite |
| `snr_db` | float | estimated SNR |
| `center_frequency_hz` | float | RF center frequency |
| `sample_rate_hz` | float | 128000 per the frozen sampling contract |
| `latency_us` | object | 6 stage latencies (µs) |
| `fps` | float | pipeline frame rate |
| `counters` | object | 6 monotonic counters |
| `sdr_status` / `fpga_status` / `npu_status` | enum | `ok / warning / error / disconnected / unknown` |
| `spectrum_bins` | float[] | optional power spectrum (may be empty) |
| `message` | string | optional human-readable note |

## Validity rules (enforced by `validate()` and the tests)

- `schema_version` must be `1`.
- `class_id ∈ [0,7]` and `class_name == class_names()[class_id]`.
- `confidence` and every `probabilities[i]` are finite and in `[0,1]`.
- `probabilities` has exactly 8 entries.
- Every float (`snr_db`, frequencies, fps, 6 latencies, `spectrum_bins`) is
  finite; latencies and fps are non-negative.
- NaN / Infinity / missing field / wrong enum → frame is rejected (or counted
  as `counters.error`) and never drives the UI.
