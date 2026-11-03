# hdmi_framebuffer_ui_v4_fix — 任务 39e5：HDMI DDR 帧缓冲读取链路修复

FMQL30TAI（悟净）/ xc7z030ffg676-2 的 **PS DDR → PL 读 → 720p HDMI** 动态显示系统。
本目录是 **39e5 独立修复目录**：在 v3 双缓冲位流基础上修复读路径
（`aq_axi_master.v` 64→16 半字反转），**不覆盖 v2 / v3 / 其它工程**。

> **状态：`READY-FOR-HARDWARE-TEST`，未上板。** 未经实机验证不写 `PASS`/`READY`/"显示成功"。

## 一句话说明

- **根因 A（RTL，已修）**：Xilinx 非对称 FIFO（写 64 > 读 16）读侧 MSB-first，DDR 小端写像素，
  原直通导致每 4 像素逆序；修复 = `RD_FIFO_DATA = {RDATA[15:0], [31:16], [47:32], [63:48]}`。
- **根因 B（软件，已修）**：GCC -O2 把 `uint16_t*` 写 u-dma-buf mmap 向量化成 NEON 宽写 → SIGBUS；
  修复 = `volatile std::uint16_t*`。
- **1B/1C/2/3 共用同一 v4_fix 双缓冲位流**（RTL 相同，只换 PS 程序）。

## 唯一有效上板位流

| 用途 | 绝对路径 | 大小 | SHA-256 |
|---|---|---|---|
| **JTAG 临时加载（禁写 Flash）** | `F:/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit` | 5,980,619 B | `df8a0c669812835f7e6698ae0db0bb8524e6681bb211dfd1255bffe4ad1551b7` |

> 只加载 `*_disable_icap.bit`，**绝不加载原始 `.bit`**。FMSH IP patch = `53180205`（已应用，证据 `fpga/logfiles/procise.log`）。
> 此前 `write_bitstream_manual.tcl` 生成的 `0XFFFFFFFF` 位流已作废（`REVOKED_DO_NOT_PROGRAM`），见 `deprecated_manual_no_patch/README.md`。

## 目录

| 路径 | 内容 |
|---|---|
| `fpga/build_phase1b.tcl` | Vivado 2018.3 双缓冲位流构建 |
| `fpga/program_phase1b_jtag.tcl` | Vivado 2020.2 临时 JTAG 加载 `_disable_icap.bit`（volatile，不写 Flash） |
| `fpga/procise_run_disable_icap.tcl` + `call_procise_disable_icap.bat` | Procise 备用（仅当 `_disable_icap.bit` 缺失时） |
| `fpga/logfiles/procise.log` | **FMSH patch 证据**（`IP Patch version: 53180205`） |
| `sw/phase1{b,2,3}*` + `phase1c_dynamic_test.cpp` | Phase 1B/1C/2/3 PS 程序 |
| `sw/CMakeLists.txt` + `build_on_board.sh` + `collect_logs.sh` | 板上多目标构建/运行/证据采集 |
| `docs/BOARD_TEST_39E5.md` | **39e5 上板权威指南（从断电接线到逐阶段 PASS/FAIL）** |
| `docs/FIX_39E5_READ_PATH.md` | 39e5 根因 + 修复 + 仿真 + 构建报告 |
| `docs/BUILD_RESULTS.md` | 时序/DRC/SHA-256/与 v3 差异 |
| `docs/MASTER_MANUAL.md` | 阶段模型与判据参考（39e5 以 BOARD_TEST_39E5.md 为准） |
| `BITSTREAM_RELEASE_MANIFEST.json` | 位流发布清单（版本/器件/patch/哈希/时序/DRC/状态） |
| `deprecated_manual_no_patch/` | 已作废 `0XFFFFFFFF` 位流归档说明 |
| `SHA256SUMS.txt` | 全交付物 SHA-256 清单（`sha256sum -c` 可校验） |

## 快速开始（你本人上板时）

1. 读 **`docs/BOARD_TEST_39E5.md`**（唯一有效位流路径、接线顺序、逐阶段步骤/判据/回滚全在里面）。
2. 按顺序 1A → 1B → 1C → 2 → 3，**任一阶段 FAIL 即停**（每阶段 FAIL 都必须停下定位）。
3. 每阶段用 `sw/collect_logs.sh` 收集证据。

## 红线（不变）

- 只临时 JTAG 加载（`program_hw_devices`，volatile），**永不写 Flash**；加载 `*_disable_icap.bit` 而非原始 `.bit`。
- 720p 时序 / TMDS 引脚 / 时钟链 / `ps_ai.bd` PS7+DDR3 配置 **冻结复用官方**。
- 完整帧用真实 DDR3（PS DDR，经 `S_AXI_HP2`），BRAM 仅作 FIFO/行缓存。
