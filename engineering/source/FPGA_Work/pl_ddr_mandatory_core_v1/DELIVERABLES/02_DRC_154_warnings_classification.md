# DRC 154 条 Warning 分类报告

来源：`reports/pl_ddr_mandatory_core_v1/cdc_routed_drc.rpt`（routed DCP 上 `report_drc`，2018.3）
器件：xc7z030ffg676-2，Design State: Fully Routed，**0 Error / 0 Critical Warning**，154 条全部为 Warning/Advisory。

## 结论速览

| 归属 | 条数 | 说明 |
|---|---|---|
| **官方 vendor IP**（shell / MIG / NPU / video） | **90** | FMSH 冻结 IP，非本阶段引入 |
| **本阶段 frozen_core**（6 个 Mandatory Core RTL） | **62** | 用户 DSP 流水线，冻结 |
| meta（CHECK-3 规则上限提示） | **2** | 非真实违例，仅"已达 20 条上限" |
| **本阶段新增逻辑**（CDC FIFO / output_adapter / tensor_writer / MemChunk） | **0** | ✅ 无任何 DRC 违例 |

## 明细（按 rule × 归属）

| Rule | Severity | 描述 | 条数 | 归属 | 位置 |
|---|---|---|---|---|---|
| DPIP-1 | Warning | Input pipelining | 24 | frozen_core | `u_engine/frozen_core/features/product_*` |
| DPOP-1 | Warning | PREG Output pipelining | 16 | frozen_core | 同上 |
| DPOP-2 | Warning | MREG Output pipelining | 22 | frozen_core | 同上 |
| DPIP-1 | Warning | Input pipelining | 2 | NPU | `u_ps_ai_peripheral/ZGolo/u_AI_Mate_top/...` |
| DPOP-1 | Warning | PREG Output pipelining | 2 | NPU | 同上 |
| DPOP-2 | Warning | MREG Output pipelining | 2 | NPU | 同上 |
| REQP-165 | Advisory | writefirst | 4 | NPU | `.../U0_ddr2hp_itcn/...` BRAM SDP |
| REQP-181 | Advisory | writefirst | 28 | NPU | 同上 |
| REQP-1839 | Warning | RAMB36 async control | 20 | NPU | `.../U0_ddr2hp_itcn/...` AXI FIFO |
| REQP-1840 | Warning | RAMB18 async control | 20 | NPU | 同上 |
| PLCK-23 | Warning | Clock Placer | 1 | MIG | `mig_ddr3_u0/.../u_ibufg_sys_clk`（CLOCK_DEDICATED_ROUTE=FALSE） |
| REQP-1709 | Warning | Clock output buffering | 1 | MIG | `.../pll_clk3_out` |
| RTSTAT-10 | Warning | No routable loads | 1 | PS shell | 208 条 PS7 S_AXI_HP* 未用 net |
| REQP-1577 | Warning | Clock output buffering | 1 | video | `frame_to_ps_inst0/cmos_clkgen_742_5` MMCM |
| REQP-1580 | Warning | Phase alignment | 8 | video | `frame_to_ps_inst0/uihdmitx` OSERDESE2 10:1 |
| CHECK-3 | Warning | rule limit reached | 2 | meta | REQP-1839/1840 达上限提示 |

**合计：90（官方）+ 62（frozen_core）+ 2（meta）= 154** ✅

## 逐类定性

1. **DPIP/DPOP（68 条）**：DSP48 输入/输出流水线建议（性能类 Advisory），非功能问题。62 条在用户 frozen_core 的 `features/product_*`（复乘特征提取），6 条在官方 NPU。
2. **REQP-165/181 writefirst（32 条）**：官方 NPU `U0_ddr2hp_itcn` 内 BRAM SDP WRITE_FIRST 模式提示，仅提示"地址冲突时读数据可能损坏，需仿真确认不冲突"。官方 IP 固有。
3. **REQP-1839/1840 RAMB36/18 async control（40 条）**：官方 NPU `U0_ddr2hp_itcn` AXI FIFO 的 RAM 异步控制引脚提示。官方 IP 固有，EN/RST 异步属常见设计。
4. **PLCK-23 / REQP-1577 / REQP-1580 / REQP-1709（11 条）**：官方 MIG / video(HDMI) / CSI 时钟拓扑提示 —— 均为厂商已知（CLOCK_DEDICATED_ROUTE=FALSE、OSERDESE2 10:1、pll_clk3_out），非本阶段引入。
5. **RTSTAT-10（1 条）**：208 条 PS7 未用 AXI HP 端口 net，官方 shell 固有。
6. **CHECK-3（2 条）**：非真实违例，是"REQP-1839/1840 已报满 20 条"的元提示。

## 结论

**154 条中无一条来自本阶段新增逻辑（CDC/适配器/Tensor 写入/MemChunk），且全部为 Warning/Advisory 级（0 Error、0 Critical Warning）。** 官方 vendor IP 贡献 90 条（NPU 78 + MIG 2 + PS shell 1 + video 9），用户 frozen_core（6 Mandatory Core）贡献 62 条。与 1 GHz BUFG Min-Period 违例无关，不构成出 bit 阻塞（bitstream 仅被 DRC Error 阻断）。
