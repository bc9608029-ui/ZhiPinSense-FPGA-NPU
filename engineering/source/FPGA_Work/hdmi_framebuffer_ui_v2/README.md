# hdmi_framebuffer_ui_v2 — HDMI 动态显示系统（Phase 1B / 1C / 2 / 3）

FMQL30TAI（悟净）/ ZG330 的 **PS DDR → PL 读 → 720p HDMI** 动态显示系统。
本目录是 **v2 双缓冲** 工程：与 v1（`hdmi_framebuffer_ui_v1`，Phase 1A 单缓冲）互补。

> **状态：全部 `READY-FOR-HARDWARE-TEST`，未上板。** 未经实机验证不写 `PASS`/`READY`。

## 一句话说明

- **1B**（双缓冲动态）：PS 渲染后缓冲 → 写 `0x40080050` 原子切读 → 移动竖条无撕裂。
- **1C**（稳定性）：4 种动态图案轮换 ≥10 分钟，程序心跳不卡死。
- **2**（UI）：离屏 RGB565 渲染完整识别 UI（分类行+置信度条+Top-1），双缓冲翻页。
- **3**（触摸）：USB 触摸检测/线性标定/页面切换；无触摸则自动翻页演示。

**1B/1C/2/3 共用同一 v2 双缓冲位流**（RTL 相同，只换 PS 程序）；1A 在 v1（单缓冲位流）。

## 目录

| 路径 | 内容 |
|---|---|
| `fpga/build_phase1b.tcl` | Vivado 2018.3 双缓冲位流构建（已通过，见 `docs/BUILD_RESULTS.md`） |
| `fpga/program_phase1b_jtag.tcl` | Vivado 2020.2 临时 JTAG 加载 `_disable_icap.bit`（volatile，不写 Flash） |
| `fpga/procise_run_disable_icap.tcl` + `call_procise_disable_icap.bat` | Procise 备用（仅当 `_disable_icap.bit` 缺失时） |
| `fpga/vivado_prj/.../impl_1/*.bit` | 构建产物（`.bit` + `_disable_icap.bit`） |
| `sw/phase1b_doublebuf_test.cpp` | Phase 1B PS 程序 |
| `sw/phase1c_dynamic_test.cpp` | Phase 1C PS 程序 |
| `sw/phase2_ui_render.cpp` | Phase 2 PS 程序（识别 UI） |
| `sw/phase3_touch_test.cpp` | Phase 3 PS 程序（触摸） |
| `sw/CMakeLists.txt` + `sw/build_on_board.sh` | 板上多目标构建/运行 |
| `sw/collect_logs.sh` | 板上日志/证据采集 |
| `docs/MASTER_MANUAL.md` | **总操作手册（从断电接线开始，4 个验收门）** |
| `docs/BUILD_RESULTS.md` | 位流时序/DRC/SHA-256（构建结果） |
| `docs/HDMI_WORK_REPORT.md` | **本次 HDMI 工作完整报告（总览）** |
| `docs/PHASE{1B,1C,2,3}_BRINGUP.md` | 各阶段上板指南 |
| `SHA256SUMS.txt` | 全交付物 SHA-256 清单 |

## 快速开始（你本人上板时）

1. 读 `docs/MASTER_MANUAL.md`（接线/JTAG/逐阶段步骤/判据/回滚全在里面）。
2. 按顺序：1A（v1）→ 1B → 1C → 2 → 3，**任一阶段 FAIL 即停**。
3. 每阶段用 `sw/collect_logs.sh` 收集证据。

## 红线（不变）

- 只临时 JTAG 加载（`program_hw_devices`，volatile），**永不写 Flash**；加载 `*_disable_icap.bit` 而非原始 `.bit`。
- 720p 时序 / TMDS 引脚 / 时钟链 / `ps_ai.bd` PS7+DDR3 配置 **冻结复用官方**。
- 完整帧用真实 DDR3（PS DDR，经 `S_AXI_HP2`），BRAM 仅作 FIFO/行缓存。
