# touch/ — USB touchscreen bring-up prep

## Status: hardware UNCONFIRMED

The board has **4× USB2.0 Host** ports (USB3320C ULPI PHY + USB2514 hub, on PS
MIO), each with +5 V. The manuals only mention "USB 鼠标和 USB 键盘" as example
devices — **no touch panel is on either board's feature list**, and no
touchscreen/evdev/HID node exists in the shipped device tree. So a USB touch
screen is *possible* to plug in, but its support is not yet proven.

## Device-tree / driver evidence (from `fmqlmp-verify.dtb`)

- `usb@e0045000` — `dr_mode="otg"`, `status="okay"`, phy `usb-nop-xceiv`
  ("usbphy0"). This is the USB3320C ULPI controller behind the 4-port hub.
- `usb@e0046000` — disabled.
- **No** `input` / `touchscreen` / `hid` node. Generic USB HID devices
  (mice/keyboards/touchscreens) are normally handled by the kernel's generic
  usbhid → hid-multitouch → evdev stack **without** a DT node, so a USB touch
  screen would most likely appear as `/dev/input/eventX` — but the shipped
  kernel `.config` was not provided, so this is unverified.

## What to verify at first boot (script `../scripts/04_verify_touch.sh`)

```sh
cat /proc/bus/input/devices          # look for a touchscreen/input device
ls -l /dev/input/event*              # raw event nodes
# if evtest is present:
evtest /dev/input/event0             # tap and watch ABS_X/ABS_Y/BTN_TOUCH
```

## Integration options (once hardware is confirmed)

1. **Qt evdevtouch** (needs Qt aarch64 — see `../qt/`): Qt's
   `-plugin EvdevTouch` reads `/dev/input/eventX` and injects touch points into
   the QML app; combine with `-platform offscreen`.
2. **Manual evdev** read in the C++ side and forward into the QML
   `FrameBridge`/touch layer, keeping the frozen `hdmi_ui_v1_1` untouched.

## Blocked this round

Cannot confirm touch hardware or the HID kernel config without booting the
board, which is forbidden this round. The script is prepared and will be run
only after the colorbar + UI-mock stages pass.
