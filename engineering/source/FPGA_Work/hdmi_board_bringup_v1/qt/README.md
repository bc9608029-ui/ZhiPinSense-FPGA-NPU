# qt/ — Qt/C++ display backend for the 悟净 board

## Status: `pending-qt-build`

The host (Windows) has Qt 5.15.2 **runtime only** (Anaconda: `qmlscene.exe`,
`qmllint.exe`) — no C++ headers, no MSVC/MinGW/gcc on the host. The provided
cross-compile environment (`F:\嵌赛\07_交叉编译环境\02_Docker镜像`,
`aarch64-linux-gnu-` gcc 9) contains **no Qt headers, no qmake, and no Qt
platform plugins** (no eglfs/linuxfb/offscreen). So a Qt **C++** build for the
board cannot be produced with what is currently installed — it needs either
(a) a Qt 5.15 source build for aarch64, or (b) Qt aarch64 dev packages added to
the Docker image.

## Two facts that shape the design

1. **There is no framebuffer/DRM on the board** (see `../linux/display_backend.md`).
   The UI must render **offscreen** and write RGB565 to a DDR buffer, then poke
   register `0x40080054` (the demo's `RGB565HDMIDisplay` path). So the target
   Qt platform is **`offscreen`**, not `linuxfb`/`eglfs`.
2. The existing `hdmi_ui_v1_1` QML app (Mock/JSONL/Unix-socket data sources,
   10-class AMC, `ResultFrame` V1.1 contract) is the UI to bring up. It is
   frozen — do not modify it; wrap/adapt around it.

## What can be verified on the host right now (no board, no compiler)

The QML layer can be render-checked offscreen using the Anaconda Qt runtime:

```
# 1. syntax/lint the QML
<anaconda>/Library/bin/qmllint.exe  F:/FPGA_Work/hdmi_ui_v1_1/app/qml/Main.qml

# 2. offscreen render smoke test (no display): confirms the scene graph builds
#    and paints a frame without a GPU/screen.
QT_QPA_PLATFORM=offscreen <anaconda>/Library/bin/qmlscene.exe \
    F:/FPGA_Work/hdmi_ui_v1_1/app/qml/Main.qml
```

See `offscreen_render_check.md` for the full host checklist. This proves the QML
layer is sound; the missing piece is only the C++ side (offscreen RGB565 export +
register write), which is `pending-qt-build`.

## Target architecture (once Qt aarch64 is available)

```
QML (hdmi_ui_v1_1)  --QQuickRenderControl-->  offscreen FBO (RGBA)
      --> convert RGBA->RGB565  -->  write to udmabuf0 (contiguous DDR)
      --> write 0x40080054 = (buf_addr >> 3)  --> PL aq_axi_master -> HDMI
```

The `ResultFrame`/`DataSource`/`FrameBridge` contract in `hdmi_ui_v1_1` is
unchanged; only a new display sink (offscreen render + RGB565 + register write)
is added, in a **separate** directory so the frozen `hdmi_ui_v1_1` is untouched.

## Concrete next step (host-side, non-board)

- Add a Qt aarch64 toolchain (or Qt source build) to the Docker image, then
  cross-build `hdmi_ui_v1_1` with `-DQT_QPA_PLATFORM=offscreen`.
- Until then, the UI is validated on the host via the offscreen QML render
  check above; no board, no flashing.
