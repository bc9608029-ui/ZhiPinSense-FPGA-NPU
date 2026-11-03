# hdmi_ui_v1 — hand-off report

## Scope

Phase 3 of the FPGA contest work: the HDMI touch UI that renders the
recognition program's `ResultFrame` stream. This pass delivered the complete
UI — contract, data sources, C++↔QML bridge, QML scene, deterministic mock
data, tests, build, and docs — as an **offline deliverable**. No board, SDR, or
FPGA was touched, and no training was started.

## What was built

- **Frozen contract** (`contracts/`): JSON Schema (normative) + a Qt-free C++
  mirror with `validate()`. The 8 class names, 6 latency keys, and 6 counter
  names are copied read-only from the SDR adapter (`deployment_contract.yaml`,
  `perf_stats.hpp`, `sequence_monitor.hpp`, `pipeline.hpp`) — no adapter file
  was modified.
- **Data sources** (`src/`): `MockDataSource` (8 deterministic scenarios),
  `JsonLinesDataSource` (FILE replay), `UnixSocketDataSource` (reserved SDR
  stub that fails loudly), plus the consumer-side `FrameSequenceMonitor` and
  `StaleDetector`.
- **Bridge + controller** (`app/`): `FrameBridge` publishes `frame`, `stale`,
  `hasFrame`, and `eventLog` to QML; `SourceController` builds concrete sources
  so the bridge stays generic.
- **QML scene** (`qml/`): 1920×1080 dark theme, flat fills (no gradients —
  no GPU), 48 px touch targets, color+shape+text status coding (never
  color-alone), per-stage latency, counters, live event log, source bar.
- **Deterministic mock mirror** (`scripts/generate_mock_data.py`): byte-exact
  mirror of `MockDataSource` for the same seed (only `timestamp_ns` differs —
  C++ uses wall-clock `now_ns()`, the generator uses a synthetic deterministic
  value).
- **Tests** (`tests/`): 28 Python tests (schema conformance, structural
  invariants, determinism, manifest hashes, scenario semantics) + a Qt-free
  C++ `test_contract`.

## Design decisions worth noting

- **Arrival-based staleness.** The bridge measures staleness against the
  *steady-clock arrival time* of the last frame, not the producer timestamp, so
  FILE replay (whose producer timestamps are synthetic/past) does not dim as
  "stale" on sight.
- **Frozen class order lives only in the contract.** QML never re-declares the
  order; it receives it as the `classNames` context property built from
  `class_names()`, so the two cannot drift.
- **Generic bridge + thin controller.** `FrameBridge` sees only the abstract
  `DataSource`; QML switches concrete sources through `SourceController`.
- **MOCK is never real RF.** `source == MOCK` is surfaced as a persistent badge
  so simulated data cannot be misread as RF.

## Verification status

| Layer | Status |
|---|---|
| Python tests | **Pass** — 28/28 on the host (schema, invariants, determinism, semantics) |
| C++ / Qt build | **Not verified** — this host has no C++ compiler (no g++/gcc/clang/cl) |
| QML runtime | **Not verified** — requires a Qt 5.15 build |

The C++/QML code was written against Qt 5.15.2 APIs (`QTextStream::setCodec`,
versioned QML imports, Basic controls style) and follows the project skills
(flat fills, fixed pixel layout, 48 px targets, explicit-id QML scoping), but
**nothing above the contract layer has been compiled.** The first action on any
host or board with a Qt 5.15 + C++17 toolchain must be:

```sh
cmake -B build -DCMAKE_PREFIX_PATH=/path/to/Qt/5.15
cmake --build build
ctest --test-dir build
```

## Next steps (in order)

1. Build on a machine with a C++17 + Qt 5.15 toolchain; fix any compile errors.
2. Run `ctest` (contract test) and then `./hdmi_ui_v1` against
   `mock_data/normal.jsonl` on the host.
3. On the board, run `-platform linuxfb` (or `eglfs` with
   `QT_QUICK_BACKEND=software`); confirm HDMI output and touch hit-testing.
4. Wire `UnixSocketDataSource` to the real SDR adapter once hardware arrives
   (the contract it consumes is already final).

## Boundaries respected

- No board / SDR / FPGA / RTL / bitstream / NPU project was touched.
- No V2 / V3.x model or threshold was changed; no training was started; no
  final blind data was accessed.
- `timestamp_ns` being synthetic in the generator is an explicit, documented
  implementation assumption, not a claim about the pipeline.
