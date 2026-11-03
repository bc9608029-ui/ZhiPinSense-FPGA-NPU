# fpga/ — minimal 720p HDMI colorbar build package (FMQL30TAI 悟净)

This directory contains a **minimal, self-contained** PL-side pHDMI colorbar
test design for first board bring-up, plus the exact build commands. It does
**not** contain a prebuilt bitstream — this is a `pending-vivado-build` package.

## What it does

Generates the standard 8-colour bar (`color_bar` official IP) at **1280×720@60**
and drives the HDMI connector through the official `uihdmitx` TMDS transmitter.

This is the **fixed test pattern** stage of the staged bring-up. It proves the
HDMI pins, the pHDMI data path and the pixel clock chain work **before** any Qt
UI / DDR frame buffer is involved.

## Files

| File | Origin | Notes |
|------|--------|-------|
| `rtl/color_bar.v` | official demo (unmodified copy) | contains the `VIDEO_1280_720` timing block |
| `rtl/uihdmitx.v` | official demo (unmodified copy) | TMDS encoder + serializer, 7FAMILY path |
| `rtl/TMDSEncoder.vhd` | official demo (unmodified copy) | 8b/10b DVI encoder |
| `rtl/oserdese2_10to1.v` | official demo (unmodified copy) | OSERDESE2 10:1 DDR serializer |
| `rtl/video_define.v` | **new** | selects `VIDEO_1280_720` (official ships 1080p) |
| `rtl/hdmi_colorbar_720p_top.v` | **new** | the minimal top (2 cascaded MMCMs) |
| `constrs/hdmi_colorbar_720p.xdc` | **new** | HDMI/sys_clk/sys_rst/LED pins (from official XDC) |
| `build_hdmi_colorbar_720p.tcl` | **new** | full build (synth→impl→DRC→timing gate→bit) |

The four official IP files are **read-only copies**; they are never modified and
the frozen official assets remain untouched.

## Clock scheme (the only non-trivial part)

The board's only onboard oscillator is **sys_clk 200 MHz** (C8/C7). 200 MHz
cannot cleanly generate the 720p pixel clock (74.25 MHz) or its 5× TMDS clock
(371.25 MHz) in a single MMCM (VCO would need M=297 > 64). The design therefore
uses two cascaded MMCMs, mirroring the demo's own 200→27 MHz `sys_clk` IP:

```
sys_clk 200 MHz ──MMCM1──> 27 MHz ──MMCM2──> VCO 742.5 MHz
        (VCO 1080 = 200*27/5, /40)          (VCO 742.5 = 27*55/2)
                                              ├─ /10 ─> 74.25 MHz  (pixel)
                                              └─  /2 ─> 371.25 MHz (5× TMDS)
```

No external oscillator or FMC clock is required.

## How to build (not yet run)

**Prerequisite:** Vivado (this machine: `D:/Xilinx/Vivado/2020.2`) + FMSH JFM
kit (`D:/FMSH/JFM_Kits`). The official FMSH flow is documented for Vivado
2018.3; the identical build below was proven on this machine by
`ps_pl_ctrl_smoke`.

```tcl
# Vivado Tcl console:
source F:/FPGA_Work/hdmi_board_bringup_v1/fpga/build_hdmi_colorbar_720p.tcl
```

Or batch:
```
D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode batch -source F:/FPGA_Work/hdmi_board_bringup_v1/fpga/build_hdmi_colorbar_720p.tcl
```

On success it prints `HDMI_COLORBAR_720P_BUILD_PASS` and writes
`reports/build_summary.txt` with the WNS/WHS gate results.

## Then: Procise (produce the flashable bitstream)

The `.bit` from Vivado is **not** directly flashable on the FMQL device. Produce
the `*_disable_icap.bit` in Procise (mirrors the user's
`procise_run_disable_icap.tcl`):

```tcl
set_device JFMQL30TAI676H
increment_bit_cfg_v3 <impl_dir>/hdmi_colorbar_720p_top.bit <impl_dir>/hdmi_colorbar_720p_top_disable_icap.bit -disable_icap
```

## Known risks (will be checked at first build)

1. **371.25 MHz on BUFG.** The 5× TMDS clock ideally routes through a BUFIO in
   the HDMI IO bank (the demo uses a clk_wiz). If the timing gate reports WNS<0
   on the 371.25 MHz path, switch that clock to a BUFIO — a documented, small
   change, not a redesign.
2. **HDMI `_N` pins.** Constrained only via the `_P` LOCs (exactly as the
   official XDC does); Vivado auto-pairs the differential partners.
3. **Vivado 2018.3 vs 2020.2.** Official docs cite 2018.3; the installed 2020.2
   already produced the smoke bitstream, so it is expected to work here too.
