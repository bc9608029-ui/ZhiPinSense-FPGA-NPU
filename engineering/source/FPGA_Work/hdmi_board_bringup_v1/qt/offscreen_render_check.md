# qt/offscreen_render_check.md — host-side QML offscreen render verification

The only Qt verification possible on the host today (no C++ compiler, no board)
is a **QML offscreen render smoke test** using the Anaconda Qt 5.15 runtime.
This proves the `hdmi_ui_v1_1` scene graph constructs and paints a frame without
any display — a necessary (not sufficient) check before the cross-built app is
put on the board.

## Prereqs (all host-side)

- Anaconda Qt runtime: `qmlscene.exe` and `qmllint.exe` (Qt 5.15.2).
- The frozen UI: `F:\FPGA_Work\hdmi_ui_v1_1\app\qml\Main.qml`.

## Steps

```sh
# 1. Lint the QML (syntax + basic semantic checks).
qmllint.exe F:/FPGA_Work/hdmi_ui_v1_1/app/qml/Main.qml

# 2. Offscreen render smoke test: build the scene graph and paint one frame
#    with no windowing system.  A clean exit (no QML error) is the pass signal.
QT_QPA_PLATFORM=offscreen \
  qmlscene.exe F:/FPGA_Work/hdmi_ui_v1_1/app/qml/Main.qml

# 3. (optional) force the Mock data source and confirm a frame path runs.
QT_QPA_PLATFORM=offscreen \
  qmlscene.exe F:/FPGA_Work/hdmi_ui_v1_1/app/qml/Main.qml --source mock
```

## Pass / fail

- **Pass:** `qmllint` reports no errors; `qmlscene` exits without a QML runtime
  error under `offscreen`.
- **Fail:** any `qmllint` error, or `qmlscene` aborts (missing import, broken
  reference, etc.). Fix the QML layer before proceeding.

This does **not** exercise the C++ RGB565 export or the `0x40080054` register
write — those are the `pending-qt-build` pieces and need the aarch64 Qt toolchain
(see `README.md`).
