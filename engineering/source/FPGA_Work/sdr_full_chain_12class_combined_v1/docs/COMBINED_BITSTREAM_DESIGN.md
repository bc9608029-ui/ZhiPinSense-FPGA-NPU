# 组合位流（NPU + HDMI framebuffer）设计说明 — smoke_v1

状态：**READY-FOR-FIRST-COMBINED-HARDWARE-SMOKE**（待上板验证，未经实机验证绝不写 PASS）

## 1. 目标

在单一位流内同时提供：
- **NPU**（ZG330 AI，`npu=0x40000000`，`dma=0x80000000`，走 `axi://zg330aiu`）；
- **HDMI 720p 帧缓冲显示**（frame_ctrl 寄存器页 `0x40080000`，fb_read_720p 经 HP2_1 读 DDR 帧缓冲 → uihdmitx/TMDS）。

取代此前「NPU-only 位流」与「HDMI-only 位流」互斥的两分状态，使 Gate 9（真 NPU 分类）→ Socket → 实体屏幕实时链路可在单板单次加载下运行。

## 2. 合并架构（最小改动）

基座 = NPU 工程 `pl_ddr_mandatory_core_top`（含 ps_ai_peripheral / AI_Mate / MIG / ps_ai_wrapper 外壳）。改动仅在合并工程内：

| 文件 | 动作 | 说明 |
|---|---|---|
| `rtl/display/fb_read_720p.sv` | 新增 | 720p 帧缓冲读取链路（拷贝自 HDMI 工程） |
| `rtl/display/aq_axi_master.v` | 替换 | 39e5 半字反转修复版（SHA 5a181a79…） |
| `rtl/display/video_define.v` | 替换 | 720p 版（SHA b7582475…） |
| `rtl/ps_ai_peripheral_combined.sv` | 新增 | 官方 `ps_ai_peripheral` 拷贝，`frame_to_ps_largebuf` → `fb_read_720p`，新增 `clk_371m25` 输入 |
| `pl_ddr_integration_v1/rtl/pl_ddr_mandatory_core_top_combined.sv` | 新增 | 顶层拷贝，实例 `ps_ai_peripheral_combined`，插入 HDMI 时钟链 |

- **HP2_1 主接口**：从「写采集帧到 DDR」（frame_to_ps_largebuf）改为「从 DDR 读帧缓冲」（fb_read_720p）。S_AXI_HP2_* 线宽与 fb_read_720p 的 m00_axi 端口 1:1（ARID/AWID/WID[4:0]、ADDR[31:0]、LEN[3:0]、DATA[63:0]、STRB[7:0]）。
- **保留不变**：frame_trans（经 gp0_manager 提供 frame_ctrl 寄存器 `0x40080000`）、vtc、demo_clkrst_wrapper、AI_Mate、MIG、ps_ai_wrapper、clk_wiz_core_50、pl_ddr_mandatory_core_engine。

## 3. 时钟树

| 时钟 | 频率 | 来源 |
|---|---|---|
| gp_clk | 100 MHz | PS7 FCLK_CLK0 (50M) → clk_wiz_0 |
| hp_clk | 100 MHz | MIG ui_clk（nCK_PER_CLK=2） |
| sys_clk_p/n | 200 MHz | 板上晶振 C8/C7（DIFF_SSTL15），只喂 MIG |
| clk_200m → clk_27m | 27 MHz | IBUFDS(200M) → MMCM1(200→27) |
| clk_27m → clk_74m25 | 74.25 MHz | MMCM2(27→74.25)，像素时钟（cam_clk） |
| clk_27m → clk_371m25 | 371.25 MHz | MMCM2(27→371.25)，TMDS ×5 |

fb_read_720p 的 HP AXI 读运行在 hp_clk（100 MHz MIG ui_clk）域，与 74.25 MHz 像素时钟域之间由 fb_read_720p 内部 level_cross/异步 FIFO 做 CDC，AXI 总线上无跨时钟。

## 4. 地址图（互不重叠，4×512K）

| 区域 | 地址 | 用途 |
|---|---|---|
| NPU | 0x40000000 | ZG330 AI（axi://zg330aiu?npu=0x40000000&dma=0x80000000） |
| NPU DMA | 0x80000000 | NPU DMA 描述符/数据 |
| frame_ctrl | 0x40080000 | HDMI 帧缓冲控制（slv_reg3@0x0C=0x20230218 版本） |
| frame_ctrl 缓冲 | 0x80080000 | 帧缓冲（FB0/FB1 双缓冲） |

## 5. 身份检测（最小、软件侧，不加新 RTL）

组合位流判定 = 两条件同时满足：
1. **HDMI 帧缓冲在位**：读 `0x40080000 + 0x0C == 0x20230218`（frame_ctrl 版本寄存器）；
2. **NPU 在位**：NPU 设备 `0x40000000` 可 open/识别（`has_npu=1`）。

据此软件可区分：NPU-only（条件 1 假）、HDMI-only（条件 2 假）、组合（双真）。此检查沿用 ui_v1 已实现的 `0x40080000+0x0C==0x20230218` 启动核对，无需新增 RTL 寄存器（保持最小合并）。若后续需「design_id/has_touch_sw」位流内嵌寄存器，在 smoke_v2 独立版本实现，不覆盖 smoke_v1。

**实现要点**（已落盘）：条件 1 由 `board_ui_live_12class` 的 `DirectFramebufferBackend::init()` 版本门实现（`/dev/mem` 读 `0x40080000+0x0C`，plain g++）。条件 2 由 `board_gate7_12class_npu` / `board_gate9_full_chain_12class` 的 iCraft `Device::Open("axi://zg330aiu?npu=0x40000000&dma=0x80000000")` 实现——**NPU 无法经 `/dev/mem` 检测**（`0x400C0000` 是 ZG330 芯片经 `axi://zg330aiu` 专口的寄存器区，非 PL AXI-Lite 寄存器，必须走 iCraft）。因此身份判定 = C1（`run_gate7.sh`，NPU）+ C2（`run_ui_live.sh`，HDMI）两条件各自 fail-closed，见 `docs/BOARD_SMOKE_TEST_COMBINED.md` §1。

## 6. 构建流程

1. **Vivado 2018.3**（Part=xc7z030ffg676-2，FMSH process_control 钩子自动触发）：
   `m3_synth_combined.tcl`（综合）→ `m4_impl_bitgen_combined.tcl`（实现+写位流+从同一 routed DCP 出报告）。
2. **Procise**（FMSH，非 Vivado）：`m5_procise_disable_icap_combined.tcl`
   `set_device JFMQL30TAI676H` + `increment_bit_cfg_v3 … -disable_icap` → 板载可编程位流。
3. 临时名 `combined_npu_hdmi_disable_icap.bit.tmp` → 全部检查（DRC/时序/CDC/身份/SHA）通过后原子改名为正式 `.bit`。

**器件型号统一（2026-10-06 核对）**：交付位流的目标器件只有一个，下列名称**同指一个器件**，非型号不一致——
- 权威 Vivado part（两个实际 XPR 读得一致）：`xc7z030ffg676-2`
  （`fpga/npu_base/fpai_demo_vivado.xpr` 与 `hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.xpr` 均 `Part=xc7z030ffg676-2`）；
- 最终 implemented design `report_clock_interaction` 报告头 `Device: 7z030-ffg676`（Vivado 在该报告头省略速度级，同一器件）；
- FMSH 实硅名 `JFMQL30TAI676H`（仅 Procise `set_device` 用于 bit_cfg 补丁，非 Vivado part）；
- Xilinx MIG IP 内部 `XC7Z030-FFG676` / `xc7z030-ffg676`（无速度级）为 MIG DDR 控制器的 IP 参考目标字段，非其他型号。
已全工程核对（`docs/`/`build/`/`contracts/`/`scripts/`/`board_package/`/`model_12class/` 全部 `.md`/`.txt`/`.sh`）：除上述等价命名外，**无任何其他器件型号**（如 7z020/7z035/7z045 等一律未出现）。

### 6.x 构建完成记录（2026-10-06，smoke_v1 首次冻结）

- **post-fix 时序**（`reports/timing_summary_routed.rpt`）：WNS **+0.030** / TNS **0** / WHS **+0.029** / THS **0**（setup/hold 全部 0 失败）；WPWS/TPWS **−0.409/−0.479，仅 2 个冻结 1 GHz `clk_out1_AI_CORE_CLK_ST_1` Pulse Width 端点**（AI_Mate 黑盒 PLL，XDC 仅 LOC 无法约束，pre/post 一致，非本轮 CDC 修复范围）。
- **CDC false_path 例外覆盖审计**：9 项全通过，详见 `docs/CDC_FALSE_PATH_EXCEPTION_AUDIT.md`（例外 23/24 = 仅 gp_clk↔cam_clk 一对、共裁 291+34 条、全在 `frame_ctrl_u0`；report_cdc 每条 Critical 均被 False Path / Asynch Clock Groups 覆盖，0 未处理）。
- **DRC**：0 Error（145 条全部 Warning/Advisory，RAMB 异步控制/时钟缓冲等 FMSH IP 既有项）；6 Critical Warning 均为既有（PJTAG_TCK 未用、MIG 时钟覆盖、2 冻结脉冲宽度、FMSH TIMER_CFG 提示）。
- **位流**：raw `combined_npu_hdmi_raw.bit`（5,980,044 B，SHA `bc58f4f1…`）→ Procise `-disable_icap`（`increment_bit_cfg_v3`，`set_device JFMQL30TAI676H`）→ 板载可编程 `combined_npu_hdmi_disable_icap.bit`（**5,980,628 B，SHA `22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9`**）。m5 显式产出与 FMSH `write_bitstream_post` 钩子自动产出字节一致（同 SHA），确定性确认。

## 7. 版本隔离

- `outputs/smoke_v1/`（首次烟测，本版，冻结 SHA 不回改）；
- `outputs/smoke_v2/`（后续触摸/稳定性/身份寄存器等改动，独立目录）；
- `outputs/release_candidate/`（发布级）。
