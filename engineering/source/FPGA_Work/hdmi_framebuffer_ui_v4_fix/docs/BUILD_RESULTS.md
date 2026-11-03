# v4_fix 位流 · 构建结果（任务 39e5：HDMI DDR 帧缓冲读取链路修复）

> 构建时间：2026-10-04（Vivado 2018.3，`build_phase1b.tcl` + 手动单进程 write_bitstream 以规避 360 U盘保镖对 exFAT F 盘的并发拦截）。
> **状态：`READY-FOR-HARDWARE-TEST`（构建已通过，未上板）。**

## 0. 本轮修复（39e5）一句话

`aq_axi_master.v` 读路径半字反转：Xilinx 非对称 FIFO（写 64 > 读 16）读侧 MSB-first，
而 DDR 小端写像素，原直通导致每 4 像素逆序。修复见 `docs/FIX_39E5_READ_PATH.md`，
仿真 RED/GREEN 实证（mismatch 28800 → 0）。

## 1. 时序门（全过）

| 指标 | 值 | 门限 | 结论 |
|---|---|---|---|
| WNS（setup 最差余量） | **+2.308 ns** | ≥ 0 | ✅ PASS |
| WHS（hold 最差余量） | **+0.084 ns** | ≥ 0 | ✅ PASS |
| TNS | 0.000 | = 0 | ✅ PASS |
| THS | 0.000 | = 0 | ✅ PASS |
| WPWS（最差脉冲宽度） | +1.100 ns | ≥ 0 | ✅ PASS |

> 最差 setup 在 `clk_100m` 域；`All user specified timing constraints are met.`

## 2. DRC 门（0 Error，25 Warning 逐类说明）

> 25 条 Warning 共 5 类，逐类给出「来源规则 / 条数 / 为何不影响本设计」，而非笼统"无害"。
> 每条均来自 `fpga/reports/routed_drc.rpt`；本设计为**只读显示路径**（PS DDR → PL 读 → HDMI），
> 相机写侧与 NPU 侧全部 tie-off。

| # | 规则（Rule） | 条数 | 来源（哪个单元 / net） | 为何不影响本设计 |
|---|---|---|---|---|
| 1 | REQP-1839（RAMB36 async control set/reset） | 20 | 复用官方 `video_rect_read_data.v` 读 FIFO 的 `read_en_r_reg`（RAMB36 异步复位） | 该异步复位仅在配置/启动瞬间作用于读使能寄存器，正常工作期不复位；属官方视频读模块固有结构，Phase 1A/1B/1C 同源，历史无功能影响。本轮 39e5 只改读数据线重排（`aq_axi_master.v` 的 `RD_FIFO_DATA`），未触及该复位路径。 |
| 2 | PORTPROP-2（selectio_diff_term ignored） | 2 | `sys_clk_p/n` 差分时钟输入，`DIFF_TERM` 属性被忽略 | 时钟输入非 LVDS 真差分终端场景，`DIFF_TERM` 不生效属预期；与 Phase 1A 同源，不影响时钟质量/时序（WNS/WHS 全过）。 |
| 3 | RTSTAT-10（no routable loads） | 1 | 相机写路径 tie-off 后写侧数据/net 无负载；PS7 `S_AXI_HP2_BRESP/RRESP` 未接 | 本设计只读（无相机写、无 AXI 写响应），该 net 无负载正是设计意图，非遗漏。 |
| 4 | CHECK-1（report rule limit） | 1 | DRC 报表条数上限提示 | 仅提示"报告因条数上限截断"，非违规；已确认无 Error 行。 |
| 5 | CHECK-3（report rule limit） | 1 | DRC 报表条数上限提示（另一子项） | 同上，报表统计提示，非违规。 |

**合计 20 + 2 + 1 + 1 + 1 = 25 条 Warning，0 条 Error。**

**结论：DRC 0 Error；25 条 Warning 均为已知、可解释、不影响本设计。**

## 3. CDC / methodology

复用 v3 的 CDC 修正（1-bit 双触发缓冲选择同步、22 个同步器 ASYNC_REG 打标），
本轮 39e5 的 RTL 改动（`aq_axi_master.v` 读数据半字反转）为纯数据线重排，**不新增任何 CDC 或时序路径**。
详细豁免见 `docs/CDC_WAIVERS.md`。

## 4. 位流产物与 SHA-256

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `hdmi_framebuffer_720p_top.bit`（原始，不上板） | 5,980,035 B | `9282f98ae785131e29f38ecb85762400fc2096cb2de604b7a4e4e094390eecd3` |
| `hdmi_framebuffer_720p_top_disable_icap.bit`（**JTAG 加载目标**） | 5,980,619 B | `df8a0c669812835f7e6698ae0db0bb8524e6681bb211dfd1255bffe4ad1551b7` |

路径：`fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/`。

> **FMSH IP patch 已应用**：write_bitstream 经 run 步骤执行（含 `write_bitstream_pre/post.tcl`），
> Procise 检测 `IP Patch version: 53180205`（与 v2 **文件大小一致、FMSH patch 版本一致**，但
> 本轮 39e5 已改读路径 RTL，二进制与 v2 **必然不同，不宣称与 v2 完全一致**；且不再是 `0XFFFFFFFF`）。
> `_disable_icap.bit` 由 `increment_bit_cfg_v3 -disable_icap` 生成（FMSH 补丁自动产出
> `vivado_prj/call_procise_disable_icap.bat`，运行后得到）。

## 5. 本次 RTL 改动（相对 v3）

`fpga/rtl/display/aq_axi_master.v`（只改读路径一行）：

```verilog
assign RD_FIFO_DATA[63:0] = {M_AXI_RDATA[15:0], M_AXI_RDATA[31:16],
                             M_AXI_RDATA[47:32], M_AXI_RDATA[63:48]};
```

写路径（`WR_FIFO_DATA`→`M_AXI_WDATA`）与读控制 FSM 不动。

## 6. 与 v3 构建差异说明

- WNS 由 v3 的 +3.427 变为 +2.308：v4_fix 为独立目录**全新 create_project + 重新综合/布局布线**（不同 seed），余量仍充裕（≥ 0）。
- DRC 由 24 → 25 Warning：多出 1 条 CHECK-1（报表条数上限提示），非违规，0 Error。
