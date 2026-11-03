# linux/ — display backend on the stock board image

## TL;DR

The FMQL30TAI (悟净) board's HDMI **is not a Linux framebuffer**. The stock
Linux device tree (`fmqlmp-verify.dtb`, shipped with the official `BOOT.bin`)
contains **no DRM/KMS node, no fbdev node, no HDMI/video-output node**, and both
I2C controllers are disabled. Therefore:

- Qt's `linuxfb`, `eglfs`, `wayland`, and `xcb` platform plugins **will not
  work** — there is no `/dev/fb0` and no `/dev/dri/card0`.
- The display is driven entirely from **userspace into a DDR buffer** that the
  **PL reads over AXI and pushes to HDMI as raw TMDS (pHDMI)**.

## Evidence

- Manual (`悟净开发板硬件使用手册` §4.21 / Lite §4.16): "HDMI 输出采用了IO 模
  HDMI 信号" — HDMI is driven by PL I/O as TMDS, not by an external TX chip.
  No ADV7511/SiI9022/TDA19988 anywhere in the manuals.
- Device tree `fmqlmp-verify.dtb`: no `drm`/`fbdev`/`hdmi`/`video` node; the
  only framebuffer-adjacent node is `udmabuf@0` (`ikwzm,u-dma-buf`, device name
  `udmabuf0`); `usb@e0045000` is `otg`/okay; both `i2c@*` are disabled.
- Demo app (`fpai_demo_package_26040701.zip`,
  `deps/modelzoo_utils/include/pipeline/io/output/hdmi_display.hpp`):

```cpp
class RGB565HDMIDisplay {
  // buffer_size_ = frame_width_ * frame_height_ * 2;   // RGB565
  // show(): write RGB565 buffer, then
  //   device_.defaultRegRegion().write(DISPLAY_READ_ADDR, display_chunk_->begin.addr() >> 3);
  // DISPLAY_READ_ADDR = 0x40080054
};
```

## Full data path (PS → DDR → PL → HDMI)

```
PS app writes RGB565 to a DDR buffer
   -> register write 0x40080054 = (buffer_addr >> 3)   [frame_ctrl "camera_rd_addr"]
   -> aq_axi_master reads PS DDR via S_AXI_HP2 (64-bit)
   -> frame_to_ps_largebuf converts RGB565 -> RGB888
   -> uihdmitx / TMDSEncoder (8b/10b) / oserdese2_10to1
   -> HDMI pins AC17/AA15/Y16/W16 (TMDS_33)
```

Register base `0x40080000` (frame_ctrl); display-read-address register
`0x40080054`; framebuffer default address `0x3F000000`; `udmabuf0` is the
userspace mapping that provides a physically-contiguous buffer the PL AXI master
can DMA from.

## What this means for the Qt UI

The Qt/QML UI must **render offscreen into an RGB565 buffer** and hand that
buffer to the PL via the `0x40080054` register — it cannot rely on any Linux
display server or framebuffer. Two concrete routes:

1. **QQuickRenderControl** (recommended): drive the QML scene graph to an
   FBO offscreen, read back, convert RGBA→RGB565, write to `udmabuf0`, poke the
   register.
2. **`-platform offscreen` + `QWidget/QQuickWindow::grabWindow`**: render a
   frame offscreen, grab it, convert, write, poke.

In both cases the write path is the same as the demo's `RGB565HDMIDisplay`, and
the PL bitstream must contain the **frame-read path** (`frame_ctrl`,
`aq_axi_master`, `frame_to_ps_largebuf`) — which is present in the **official**
demo bitstream, but **not** in the minimal colorbar top in `../fpga/` (that one
generates bars internally and is only for proving the HDMI pins/clock).

## What still needs verifying on the real board (blocked this round)

- Which physical address/`udmabuf` the PL AXI master actually reads from in the
  official bitstream (the demo app is the authority; this is to be re-derived
  from the running demo's own display address).
- Whether the shipped Linux kernel enables the generic HID/evdev input stack
  (no `.config` was shipped — see `../touch/`).
