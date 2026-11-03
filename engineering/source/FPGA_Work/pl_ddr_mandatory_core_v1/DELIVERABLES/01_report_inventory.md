# 任务1：已保存的 routed DCP 与报告清单

均以 **routed DCP** 为准（`hold 修复 + -include_generated_clocks` 之后的最终实现）。

## Routed DCP

| 文件 | 大小 |
|---|---|
| `fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_routed.dcp` | 55.5 MB |
| （同目录 placed / opt DCP 也保留：placed 45.6 MB，opt 27.7 MB） | |

## 关键报告（`reports/pl_ddr_mandatory_core_v1/`）

| 报告 | 结论 |
|---|---|
| `cdc_routed_timing_gate.txt` | **WNS=0.030，WHS=0.029**（hold 已修复），route_design Complete / Failed Timing! |
| `cdc_routed_timing_summary.rpt` | STA 时序汇总 |
| `cdc_routed_route_status.rpt` | **Routing Error = 0**（107383 条 routable net 全部 fully routed） |
| `cdc_routed_drc.rpt` | **DRC 0 Error / 0 Critical Warning，154 Warning/Advisory**（见 02 分类） |
| `cdc_routed_methodology.rpt` | Methodology DRC |
| `cdc_routed_cdc.rpt` | CDC 静态分析（见下方注） |
| `cdc_routed_clock_interaction.rpt` | 跨时钟域交互 |
| `cdc_routed_check_timing.rpt` | check_timing：**0 无时钟寄存器、0 组合环、0 未约束内部端点**（10 input/6 output 端口无 IO delay，HIGH，官方 shell 固有） |
| `cdc_routed_utilization_hier.rpt` | 利用率（见下） |
| `diag_ai_clk/ai_clk_pulse_width.rpt` | **pulse-width：clk_out1_AI_CORE_CLK_ST_1 的 BUFG Min-Period −0.409 ns（唯一 P0）** |

## 利用率（top-level）

LUT 42167 / FF 72070 / RAMB36 151 / RAMB18 11 / DSP48 24。
本阶段新增 `u_engine` 仅占 LUT 7508、FF 23196、DSP 22（frozen_core 854 LUT / 915 FF / 22 DSP），其余为官方 shell/MIG/NPU。

## impl_1 原生报告（runs/impl_1/）

`drc_routed.rpt`、`methodology_drc_routed.rpt`、`timing_summary_routed.rpt`、`route_status.rpt`、`utilization_placed.rpt`、`clock_utilization_routed.rpt`、`bus_skew_routed.rpt`、`power_routed.rpt`、`io_placed.rpt`、`control_sets_placed.rpt`。

## 注：CDC 静态报告（`cdc_routed_cdc.rpt`）

`report_cdc` 是独立静态引擎，不计入 bitstream 门控。共 7164 条（CDC-1 Critical 6710、CDC-13 Critical 327、CDC-10/11 Critical 46 等），**几乎全部落在官方 obfuscated NPU/MIG/shell 内部**（vendor 自带同步结构无法被静态引擎识别，CDC-1「unknown CDC circuitry」即此特征）。这些是 pre-existing，非本阶段新增；时序侧已由 `set_clock_groups -asynchronous -include_generated_clocks` 正确处理（WHS +0.029）。是否需要向 FMSH 索取 CDC waiver 一并列入 FAE 确认范围（可选，不属 bit 硬门控）。

## 门控结论（bitstream 前必须全满足，当前状态）

| 项 | 状态 |
|---|---|
| WNS ≥ 0 / TNS = 0 | ✅ +0.030 / 0 |
| WHS ≥ 0 / THS = 0 | ✅ +0.029 / 0 |
| Routing Error = 0 | ✅ |
| DRC 0 Error / 0 未处理 Critical | ✅（154 Warning/Advisory，0 Error） |
| check_timing 无未约束内部路径 | ✅ |
| 1 GHz BUFG Min-Period | ❌ **唯一 P0，待 FMSH 确认** |
