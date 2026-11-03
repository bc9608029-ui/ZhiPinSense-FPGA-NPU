# Design notes — hdmi_ui_v1_1

## Goals

1. Native **1024×600** layout that scales proportionally — no fixed 1920×1080
   coordinates, no clipping, no text overlap, no overflow.
2. **Model-generic** contract: the frame carries its own `class_names`/`scores`;
   the UI draws 8..16 classes and never hardcodes a list.
3. **Touch-first** at ≥48×48 targets, mouse+touch with no hover dependence,
   dark/flat/no-gradient/low-GPU visuals.
4. **Honest status**: stale / error / normal are shown with color + shape + text;
   MOCK is always prominently badged.

## Target and rendering budget

- Screen: HDMI touch, native 1024×600, touch via USB (USB TOUCH), no GPU on the
  Zynq-7030 PS. Software rendering is assumed.
- Qt 5.15 + C++17, `QtQuick.Controls 2.15` **Basic** style
  (`config/qtquickcontrols2.conf`).
- Rendering rules applied throughout: flat fills (`Rectangle`) only — no
  gradients, shadows, blur, `layer`, `ShaderEffect`, or `Canvas`. Fonts use fixed
  pixel sizes (`Theme.*`), which are cheap and predictable at this DPI. No
  animations. Colors are role tokens on a singleton, not raw hex sprinkled in
  components.

## Layout (1024×600)

```
┌──────────────────────────────────────────────────────────────┐
│ TopBar: RF AMR · [MOCK] · [STALE]      RF 2.400 GHz · … · tabs │  56px
├──────────────────────────────────────────────────────────────┤
│ MainPage (StackLayout page 0)                                 │
│  ┌ ClassHeader ─────────────┐ ┌ StatusPanel ──────────────┐  │
│  │ predicted class + conf   │ │ overall status + latency   │  │
│  │ SNR + "N / 10 classes"   │ │ SDR/FPGA/NPU pills         │  │
│  └──────────────────────────┘ └────────────────────────────┘  │
│  ┌ ProbabilityBars ─ Flickable 2-column grid, 8..16 classes ┐ │
│  └ SourceBar: 10 mock scenarios + file/socket + Load/Stop ──┘ │
├──────────────────────────────────────────────────────────────┤
│ DiagnosticsPage (page 1)                                      │
│  ┌ LatencyPanel (6 stages) ┐ ┌ CountersPanel (sequence+prod)┐│
│  └ EventLog ───────────────┘                                │
└──────────────────────────────────────────────────────────────┘
```

- Root `ApplicationWindow` is 1024×600; everything is `ColumnLayout` /
  `RowLayout` / `StackLayout` / `Flickable` so it reflows if the window is
  resized. No hardcoded absolute coordinates.
- `ProbabilityBars` is a `Flickable`-wrapped 2-column `Grid` (delegate reads
  `bridge.frame.scores[index]`), so 8..16 bars stay readable at 1024×600 and
  scroll when they don't fit.
- Theme scale (`qml/theme/Theme.qml`): `display 44, h1 20, body 17, caption 14,
  small 13, touch 48, gap 12, gapSm 8, radius 6`. Touch target `touch=48`
  is applied to buttons and interactive controls.

## Status model (color + shape + text, never color alone)

`Theme.statusColor(name)` / `Theme.statusGlyph(name)` map a status to a color and
a Unicode glyph, and every `StatusPill` prints **glyph + name + status word**:

| Status | Glyph | Color |
|---|---|---|
| ok / normal | ● | green |
| warning | ▲ | amber |
| stale | ■ | amber |
| error | ◆ | red |
| disconnected | ◇ | grey |

The **STALE** badge in the TopBar and the overall status in `StatusPanel` use the
same scheme, so a state is readable even in grayscale / color-blindness.

## Contract & class flow

- `contracts/result_frame.hpp` is the Qt-free source of truth; the schema
  (`result_frame_v1_1.schema.json`) is the JSON-Lines wire form.
- `src/json_result_frame.cpp` normalises both V1.1 and legacy V1 into one
  `ResultFrame`, then `validate()` rejects NaN/Inf, length mismatches,
  `predicted_class != class_names[predicted_index]`, out-of-range indices, and
  wrong enums.
- `app/frame_bridge.cpp` publishes a `QVariantMap frame` (carrying
  `class_names` as a `QStringList` and `scores` as a `QVariantList`) plus
  `sequence`, `stale`, `hasFrame`, `eventLog`. QML never sees the raw contract.
- No frozen `classNames` context property: `main.cpp` seeds nothing, and QML
  renders whatever classes the current frame declares.

## Data sources & the live/finite distinction

`DataSource` has `is_live()`: mock and file are finite (a `nullopt` means EOF);
the Unix socket source is live (a `nullopt` means "no frame right now, keep
polling"). The bridge stops polling a finite source on EOF but keeps polling a
live source.

- **Mock** (`src/mock_data_source.cpp`): deterministic xorshift32 (seed
  `0x20261002`), stable softmax, 10 scenarios. The Python generator
  (`scripts/generate_mock_data.py`) is byte-identical except for `timestamp_ns`
  (the C++ uses wall-clock `now_ns()`).
- **File** (`src/jsonlines_data_source.cpp`): replays `mock_data/*.jsonl`.
- **Socket** (`src/unix_socket_data_source.cpp`): `QLocalSocket` with a
  blocking-but-short connect (`waitForConnected(30 ms)`), 500 ms reconnect
  backoff, and `open()` that never fails — an absent SDR adapter just leaves the
  source disconnected (UI shows "SDR", eventually dims to stale), never a crash.
  `src/line_buffer.hpp` frames bytes into lines with a strict 65536-byte limit so
  a runaway message cannot grow the buffer.

## Sequence & staleness

`FrameSequenceMonitor` (mirrors the adapter's `iq::SequenceMonitor` semantics)
detects duplicate / reorder / gap→dropped. `StaleDetector` dims the frame when
its arrival is older than 1500 ms (configurable via `setStaleTimeoutMs`). The
`stale` mock emits 30 healthy frames then goes silent, exercising exactly this
path.

## Honesty constraints honored

- No model training, no board, no SDR, no FPGA/RTL/bitstream changes.
- The V1.1 contract reuses the SDR adapter's vocabulary (latency keys, counter
  names) **read-only**; the future sync of the adapter to the V1.1 wire shape is
  documented in `contracts/README.md`, not implemented here.
