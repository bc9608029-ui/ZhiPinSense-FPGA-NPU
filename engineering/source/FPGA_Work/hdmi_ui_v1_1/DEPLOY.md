# Deployment — hdmi_ui_v1_1

Pre-deployment preparation only. Nothing here is board- or SDR-specific beyond
the launch flags; no board flashing, no SDR connection, and no FPGA/RTL/bitstream
changes are part of this deliverable.

## Build (on a Qt 5.15 + CMake host, or cross-compiled for the board)

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build
```

If cross-compiling for the Zynq-7030 PS, pass the sysroot/toolchain file via
`-DCMAKE_TOOLCHAIN_FILE=…`; the CMake target only needs `Qt5::Core Gui Qml Quick
QuickControls2 Network`.

## Deploy commands

Copy the built binary plus the Qt runtime (and platform plugins) to the board,
then launch with a software-rendered platform (no GPU on the PS):

```bash
# primary: Linux framebuffer (no GL)
./hdmi_ui_v1_1 -platform linuxfb

# eglfs fallback, forced software Quick backend (if eglfs is built and a
# framebuffer-backed EGL platform is present)
QT_QUICK_BACKEND=software ./hdmi_ui_v1_1 -platform eglfs
```

Environment notes:

- `QT_QPA_PLATFORM=linuxfb` is equivalent to `-platform linuxfb`.
- For the software QML scene graph, set `QT_QUICK_BACKEND=software` when the
  platform does not provide a GL context (linuxfb may already imply it).
- Set `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS` / `QT_QPA_GENERIC_PLUGINS` only if
  the Qt evdev input plugin needs them for the USB TOUCH device — see below.

## Touch input

The touch device enumerates as an evdev/input device (USB TOUCH). Qt's evdev
touch plugin (`libqevdevtouchplugin` or the evdevtouch generic plugin) drives it:

```bash
# list input devices to find the touch event device
ls -l /dev/input/event*
cat /proc/bus/input/devices | grep -A4 -i touch
```

If the touch coordinates don't map to the screen, add explicit mapping:

```bash
export QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=/dev/input/eventX:rotate=0
./hdmi_ui_v1_1 -platform linuxfb
```

(The `rotate`/`invertx`/`inverty` parameters follow the Qt evdev touch plugin
syntax; adjust `eventX` and `rotate` to the actual device and panel mounting.)

### Touch calibration

Calibration is **board-specific** and must be done on the target:

1. Boot with the panel attached and `./hdmi_ui_v1_1 -platform linuxfb`.
2. Touch each corner of the **MOCK scenario buttons** in the SourceBar; confirm
   the press lands on the button under the finger.
3. If presses are offset, set `rotate=` (0/90/180/270) and `invertx=`/`inverty=`
   in `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS` until corner presses align.
4. Verify a swipe on the ProbabilityBars `Flickable` scrolls, and that the two
   page tabs (Main / Diagnostics) respond without a hover state.

No calibration values are hardcoded — they are environment variables on the
board, so a panel swap is a config change, not a rebuild.

## Pre-flight checklist

- [ ] `cmake --build build` succeeds on the target toolchain.
- [ ] `ctest --test-dir build` → 6/6 tests pass.
- [ ] `./hdmi_ui_v1_1 -platform linuxfb` shows the Main page at 1024×600.
- [ ] MOCK badge is visible and prominent; no blank screen on launch.
- [ ] Switch all 10 mock scenarios; confirm stale/error/reorder/drop states show
      color + shape + text.
- [ ] Touch corners align (calibration above); swipes scroll the bar list.
- [ ] (later, when the SDR adapter is V1.1) connect the Unix socket path and
      confirm a live `SDR` source updates without crashing when the adapter stops.
