# hdmi_board_bringup_v1 — 上板前准备报告 (FMQL30TAI 悟净)

**最终状态：`pending-vivado-build` + `pending-qt-build`**

> 本包是"上板前全部准备"。**本轮未连接、未烧录、未操作开发板**。位流尚未综合
> (pending-vivado-build)，Qt 板端 C++ 尚未能交叉编译 (pending-qt-build)。包内脚本
> 可直接执行，但所有"上板"动作都停在安全门之后，等待你确认。

---

## 1. 硬件 / 官方工程审计（含文件+行号证据）

**芯片/板卡**
- FMQL30TAI (JFMQL30TAI676H)，复旦微 FPAI 系列，四核 ARM Cortex-A53 + NPU + PL；
  **对标 Xilinx XC7Z030FFG676-2I**（`悟净开发板Lite（轻量版）硬件使用手册V1.0.docx`）。
- Vivado 工程器件 = `xc7z030ffg676-2`（`F:\嵌赛\2026嵌赛FPGA开发\复微...VIVADO开发流程_V1.1.pdf` §2.1 表格）。

**HDMI = PL 侧 "IO 模" pHDMI，无外置 TX 芯片**
- 手册原文（完整版 p39 §4.21 / Lite p25 §4.16）："HDMI 输出采用了IO 模HDMI 信号，输出
  可以达到720P@60HZ 高清传输。实测1080P@60HZ…HR 的bank 的时钟运行在748.5M 的TMDS
  速率，超出了…最高710M 的速率要求"。→ **720p@60 可靠；1080p 会闪屏**。
- 手册里没有 ADV7511/SiI9022/TDA19988 等外置 HDMI TX 芯片。

**HDMI 引脚/电气标准来自官方 demo 约束，不在手册**
`tmp_official_fpga_audit/fpai_demo_fpga/constrs_1/impl_constraints.xdc`：
- L2–7：`AC17=HDMI_CLK_P`、`AA15/Y16/W16=HDMI_TX_P[0..2]`，`IOSTANDARD TMDS_33`（仅 _P，_N 自动配对）。
- L10–11：`F8=sys_rst`，`LVCMOS15`（高有效）。
- L16–20：`J1/M6=led[0..1]`，`LVCMOS15`。
- L22–26：`C8/C7=sys_clk_p/n`，`DIFF_SSTL15`，`create_clock -period 5.000`（200 MHz）。

**HDMI 数据通路（官方 demo 源码）**
`.../rtl/display/`：
- `color_bar.v` L34–45 = `VIDEO_1280_720` 时序块（1280/110/40/220 × 720/5/5/20，HS/VS 正极性）。
- `uihdmitx.v` L25/L27/L30–41 = 模块端口；L133 `FAMILY=="7FAMILY"` 走 `oserdese2_10to1`。
- `oserdese2_10to1.v` L23–30 端口；L93 `.CLK(clkdiv2)` = 5× 时钟、L94 `.CLKDIV(pclk)` = 像素时钟。
- 软件侧 `.../pipeline/io/output/hdmi_display.hpp`：`RGB565HDMIDisplay`，`buffer_size_ = w*h*2`（RGB565），
  `show()` 写缓冲后 `write(DISPLAY_READ_ADDR, begin.addr()>>3)`，`DISPLAY_READ_ADDR = 0x40080054`（L88）。

**完整通路**：PS 写 RGB565 → 写寄存器 `0x40080054`(=addr>>3) → `aq_axi_master` 经 S_AXI_HP2 读 PS DDR →
`frame_to_ps_largebuf` RGB565→RGB888 → `uihdmitx`/`TMDSEncoder`(8b/10b)/`oserdese2_10to1` → HDMI。

**工具链（重要修正）**
- 官方流程 = **Vivado 2018.3 + 复旦器件补丁 + Procise 2025.1**（`复微...VIVADO开发流程.pdf`、
  `30TAI使用教程.pdf` p5）。补丁两步：`source $::env(JFM_PATH)/ip_patch/run.tcl` + `add_hook_tcl_to_prj`
  （`F:\嵌赛\Vivado_IP_PATCH指令.txt`）。
- 本机实际安装 **Vivado 2020.2**（`D:\Xilinx\Vivado\2020.2`），且用户既有
  `ps_pl_ctrl_smoke` / `mandatory_core_board_validation` 已用同流程在本机产出过位流 → 2020.2 可用。
- `JFM_PATH = D:\FMSH\JFM_Kits`（含 `ip_patch/run.tcl`）。
- 位流后处理：Procise `set_device JFMQL30TAI676H` + `increment_bit_cfg_v3 <in> <out> -disable_icap`
  （`mandatory_core_board_validation/procise_run_disable_icap.tcl`）。

---

## 2. HDMI 最小测试工程（720p 色条）

`fpga/` 内为一套**自包含**的最小 pHDMI 色条工程，复用官方 RTL（只读拷贝），新增顶层与 720p 选择：

| 文件 | 来源 |
|---|---|
| `fpga/rtl/color_bar.v` `uihdmitx.v` `TMDSEncoder.vhd` `oserdese2_10to1.v` | 官方 demo，未改动 |
| `fpga/rtl/video_define.v` | 新增，选 `VIDEO_1280_720` |
| `fpga/rtl/hdmi_colorbar_720p_top.v` | 新增，两级 MMCM |
| `fpga/constrs/hdmi_colorbar_720p.xdc` | 新增，HDMI/时钟/复位/LED（抄自官方 XDC） |
| `fpga/build_hdmi_colorbar_720p.tcl` | 新增，synth→impl→DRC→时序门→bit |

**时钟方案（唯一难点，已解决）**：板上唯一振荡器是 200 MHz；200 MHz 无法在单个 MMCM 里
产生 74.25/371.25 MHz（需 M=297>64）。故用两级 MMCM，复用官方 demo 的 200→27 MHz 思路：
`200→27 MHz（VCO 1080=/40）→ 742.5 MHz（VCO=27*55/2）→ 74.25(/10)+371.25(/2)`。
无需外置振荡器/FMC 时钟。

**状态**：位流**尚未综合**，属 `pending-vivado-build`。构建命令见 §9；已知风险（371.25 MHz 走
BUFG 可能需换 BUFIO）在 `fpga/README.md` 注明。

---

## 3. Linux / 显示后端

**关键结论：板上 Linux 没有 framebuffer/DRM。** `fmqlmp-verify.dtb`（官方 BOOT.bin 携带）中
**无** DRM/KMS/fbdev/HDMI 节点，两个 I2C 控制器均 disabled，无 input/touchscreen/HID 节点。
显示由 PS 写 DDR 缓冲 → PL 经 AXI 读 → pHDMI 输出，用户态缓冲是 `udmabuf0`（ikwzm u-dma-buf）。

→ Qt 的 `linuxfb`/`eglfs`/`wayland`/`xcb` 全部不适用；必须 **offscreen 渲染成 RGB565 → 写
DDR 缓冲 → 写寄存器 `0x40080054`**（即官方 `RGB565HDMIDisplay` 通路）。详见
`linux/display_backend.md`。

---

## 4. Qt / C++ 编译 + ctest + QML offscreen 渲染

- **主机**：Anaconda Qt 5.15.2 仅运行时（qmlscene/qmllint），无 C++ 头文件、无 MSVC/MinGW/gcc。
- **交叉环境**：`07_交叉编译环境/02_Docker镜像` 只有 `aarch64-linux-gnu-` gcc 9，**无 Qt 头/qmake/平台插件**。
- → 板端 Qt C++ 交叉编译**当前不可行**：`pending-qt-build`。
- **可做（主机侧）**：QML offscreen 渲染冒烟测试（`qt/offscreen_render_check.md`）：`qmllint` +
  `QT_QPA_PLATFORM=offscreen qmlscene`，证明场景图能离线构建并绘制一帧。
- `hdmi_ui_v1_1`（冻结资产）的 6 个 ctest 目标、`ResultFrame` V1.1 契约、DataSource/FrameBridge
  保持不变；新增的显示 sink 放独立目录，不碰冻结 UI。

---

## 5. USB 触摸准备

- 板载 **4× USB2.0 Host**（USB3320C ULPI + USB2514 hub，PS MIO，每口 +5V）。
- **硬件未确认**：手册只提"USB 鼠标/键盘"示例，特性表无触摸屏；DT 无 HID/touch 节点。
- 通用 USB HID 触摸屏通常经 usbhid→hid-multitouch→evdev 出现为 `/dev/input/eventX`，但未提供
  kernel `.config`，故**未验证**。首启时用 `04_verify_touch.sh` 查 `/proc/bus/input/devices`。
- 集成路线（确认后）：Qt evdevtouch 插件，或 C++ 手动读 evdev 注入 `FrameBridge`。详见 `touch/README.md`。

---

## 6. 分阶段脚本 00–07

| 脚本 | 运行位置 | 作用 | 状态 |
|---|---|---|---|
| `00_host_verify.sh` | 主机 | 校验 Vivado/JFM/Procise/Qt/资产 | 可直接跑 |
| `01_program_hdmi_test.sh` + `program_jtag_temp.tcl` | 主机 | **临时** JTAG 加载色条位流（禁永久写） | 待位流 |
| `02_verify_colorbar.sh` | 主机/人工 | 确认 720p 8 色条可见、LED[0] 亮 | 待上板 |
| `03_boot_linux_verify.sh` | 板 | 确认无 fb/DRM、有 udmabuf0/usb | 待上板 |
| `04_verify_touch.sh` | 板 | 查触摸输入设备 | 待上板 |
| `05_run_ui_mock.sh` | 板 | Mock 数据 → offscreen → RGB565 → HDMI | 待 Qt 交叉编译 |
| `06_collect_diagnostics.sh` | 板 | 收集 dmesg/寄存器/输入诊断 | 待上板 |
| `07_restore_or_recover.sh` | 主机 | 回滚到官方 BOOT.bin/整盘镜像 | 备而不用 |

---

## 7. 安全门（`SAFETY_GATE.md`）

G0 资产完整（本包 XDC 核对、TOP/PART 正确、WNS/WHS≥0、用 `*_disable_icap.bit`）→
G1 硬件状态（正确区分 HDMI OUT / PS UART / PL JTAG U19 / PS JTAG U18 / USB HOST）→
G2 **首次仅可恢复临时加载，禁自动写永久存储** → G3 发热/焦味/异常电流/线缆发烫立即断电 →
G4 逐阶段放行。

---

## 8. 不触碰范围（冻结资产，全程只读）

- 官方 demo 工程与 RTL（`fpai_demo_fpga`）、官方 bitstream / BOOT.bin / iCraft / EDIF / NPU 工程。
- `hdmi_ui_v1_1`（不修改）；V1.1/V1.2/V2/V3.x 模型训练；final blind 数据；SDR adapter。
- 本包内四个官方 RTL（`color_bar.v` 等）为**只读拷贝**；新增 RTL/工程一律在
  `hdmi_board_bringup_v1/` 独立目录，不覆盖任何冻结资产，不删除任何已有文件。

---

## 9. 命令序列 / 回滚 / SHA-256

**构建位流（Vivado 2020.2，本机）**
```tcl
source F:/FPGA_Work/hdmi_board_bringup_v1/fpga/build_hdmi_colorbar_720p.tcl
```
**后处理（Procise）**
```tcl
set_device JFMQL30TAI676H
increment_bit_cfg_v3 <impl>/hdmi_colorbar_720p_top.bit <impl>/hdmi_colorbar_720p_top_disable_icap.bit -disable_icap
```
**临时上板（仅 JTAG 易失加载）**：`01_program_hdmi_test.sh` → `02_verify_colorbar.sh`。
**回滚**：色条为易失加载，断电即回退；永久恢复用 `07_restore_or_recover.sh`。

**文件清单 + SHA-256**：见 `SHA256SUMS.txt`（本包生成时对每个文件计算）。

**待你确认后（下一轮）才做**：真正跑 Vivado 综合、跑 Procise、连接开发板做色条测试。本轮到此为止。
