# 1GHz 违例决定性时序分析（任务 39e5 最终阶段 Phase 1 · M1 前置）

> 本文回应 Phase 1 指令第 2 条"1GHz 决定性分析"的**全部**要求项。所有数值均有
> `pl_ddr_mandatory_core_v1/fpai_demo_fpga` 下的报告文件作证，逐条给出证据路径。
> 结论见 §9，直接影响 §六硬门"Pulse Width / Min Period violations = 0"的**口径界定**。

---

## 1. 完整时钟名称

```
clk_out1_AI_CORE_CLK_ST_1
```

- 周期 **1.000 ns = 1000 MHz**，波形 `{0.000 0.500}`（50% 占空比）。
- 后缀 `_ST_1` 是 Vivado 对"由 PLL/MMCM 原语输出自动派生、无用户命名时钟"的自动命名
  （source-type 派生名），并非用户在 `create_clock` 里起的名字。

证据：`fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_timing_summary_routed.rpt`
Clock Summary 行：
`clk_out1_AI_CORE_CLK_ST_1 {0.000 0.500} 1.000 1000.000`。

---

## 2. 时钟源及生成链

```
sys_clk 200MHz (差分 C8/C7 晶振)
  └─（进 AI_Mate.edif 黑盒网表内部，RTL 不可见）
       clkrst_wrapper_u0 / AI_CORE_CLK / inst / plle2_adv_inst   （PLLE2_ADV @ X1Y3）
            └─ CLKOUT0  → 1.000 ns (1 GHz)
                 └─ clkout1_buf   （BUFG @ BUFGCTRL_X0Y20）
                      └─ clk_out1_AI_CORE_CLK_ST_1  → NPU 内核时钟
```

证据（pulse-width 报告原文，见 §5 完整路径）：
`Sources: u_ps_ai_peripheral/ZGolo/u_AI_Mate_top/clkrst_wrapper_u0/AI_CORE_CLK/inst/plle2_adv_inst/CLKOUT0`。

关键点：**该 PLL 及其 1GHz 倍频配置位于 AI_Mate.edif 未加密网表内部**，是第三方 IP 的
物理时钟树，RTL 侧无法改动其 M/D 参数。约束文件只给它一个 LOC，见 §4。

---

## 3. 起点 / 终点（两个违例端点）

| 端点 | 原语 | 位置 | 检查 | Required | Actual | Slack |
|---|---|---|---|---|---|---|
| ① 终点 | BUFG | `BUFGCTRL_X0Y20`（`.../AI_CORE_CLK/inst/clkout1_buf/I`） | Min Period BUFG/I | 1.409 ns | 1.000 ns | **-0.409 ns** |
| ② 起点 | PLLE2_ADV | `PLLE2_ADV_X1Y3`（CLKOUT0 引脚） | Min Period PLLE2_ADV/CLKOUT0 | 1.071 ns | 1.000 ns | **-0.071 ns** |

- ① 的 1.409 ns ≈ BUFG 最高 ~709 MHz 的器件上限；② 的 1.071 ns ≈ PLLE2 CLKOUT0 最高
  ~934 MHz 的器件上限。两者都被 1 GHz 输出**同时击穿**。

证据：`fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_timing_summary_routed.rpt`
Detailed Pulse Width 段两行（Line 36433 / 36434）。

---

## 4. 检查类型

**Pulse Width（Min Period）违例**，即 WPWS / TPWS，**不是** setup/hold 违例。

- 全设计 Timing Summary：`WNS=+0.030 / TNS=0.000 / WHS=+0.029 / THS=0.000`，setup/hold
  **全部满足**。
- 仅 `WPWS=-0.409 / TPWS=-0.479`，`PW: 2 Failing Endpoints`（共 81461 端点里 2 个）。
- 所以 `"Timing constraints are not met"` **完全、且只**由 AI_CORE_CLK 的 min-period 引起。

证据：同上 timing_summary_routed.rpt，Line 127-132（Design Timing Summary）、
Line 36421（`PW : 2 Failing Endpoints, Worst Slack -0.409ns, Total Violation -0.479ns`）。

---

## 5. 对应原语 + report_timing / pulse-width / min-period 完整路径

报告：`fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_ai_clk/ai_clk_pulse_width.rpt`
（572 行，专为 AI_CORE_CLK 生成的 pulse-width 报告），AI_CORE_CLK 段（Line 34-43）：

```
Clock: clk_out1_AI_CORE_CLK_ST_1
  Waveform {0.000 0.500}  Period 1.000 ns
  Sources:
    u_ps_ai_peripheral/ZGolo/u_AI_Mate_top/clkrst_wrapper_u0/AI_CORE_CLK/inst/plle2_adv_inst/CLKOUT0

  Min Period   BUFG/I
    Required  1.409 ns   Actual  1.000 ns   Slack -0.409 ns
    Site BUFGCTRL_X0Y20
    Pin  .../AI_CORE_CLK/inst/clkout1_buf/I

  Min Period   PLLE2_ADV/CLKOUT0
    Required  1.071 ns   Actual  1.000 ns   Slack -0.071 ns
    Site PLLE2_ADV_X1Y3
```

对应原语（两个）：
- **PLLE2_ADV**（`PLLE2_ADV_X1Y3`）——时钟源，CLKOUT0 输出 1 GHz。
- **BUFG**（`BUFGCTRL_X0Y20`，实例名 `clkout1_buf`）——时钟缓冲，I 端输入 1 GHz。

---

## 6. 1GHz 是否为真实硬件工作频率？

**是真实的物理 PLL 配置，不是约束写错导致的"名义"频率。**

- 约束文件 `constrs_1/ai7030.xdc`（40 行）里**没有**任何针对 AI_CORE_CLK 的
  `create_clock` / `create_generated_clock`；只有一行给它 LOC：
  `set_property LOC PLLE2_ADV_X1Y3 [get_cells U0_ps_ai_peripheral/ZGolo/u_AI_Mate_top/clkrst_wrapper_u0/AI_CORE_CLK/inst/plle2_adv_inst]`。
- 因此 1 GHz 完全来自 PLL 原语自身的 `CLKOUT0_DIVIDE / CLKFBOUT_MULT` 硬连线参数
  （在 AI_Mate.edif 里），Vivado 依据原语自动推导出该时钟及其周期。
- 结论：**这不是"错误 create_clock/create_generated_clock"造成的伪违例**；它是第三方
  NPU 网表把内核时钟真实倍频到 1 GHz，超过了该器件 BUFG/PLL 的**保证工作上限**。

---

## 7. 原 NPU 工程为什么仍能生成位流？

因为 `write_bitstream` 的生成门禁是 **DRC + 布线**，**不是 pulse-width（min-period）**。

- `run_bitstream_generate.tcl` 头部注释原文（Line 8-10）：
  > The 1 GHz BUFG Min-Period pulse-width violation (Required 1.409 / Actual 1.000 /
  > Slack -0.409) is NOT waived here: write_bitstream is gated on DRC only, not on
  > timing, so it will emit the .bit while still reporting the known exception.

- 实际流程：`launch_runs impl_1 -to_step write_bitstream` 在**已布线的 DCP** 上只跑
  位流写出 + `increment_bit_cfg_v3 -disable_icap`（FMSH patch）。
- 布线干净（WNS/TNS/WHS/THS 全 met），DRC **0 error**（121 warning / 32 advisory），
  故位流正常产出：`pl_ddr_mandatory_core_top.bit`(5,980,035 B) 与其
  `_disable_icap.bit`(5,980,619 B)。

证据：`reports/pl_ddr_mandatory_core_v1/bitstream_gate.txt`、
`reports/pl_ddr_mandatory_core_v1/cdc_routed_timing_gate.txt`、
`run_bitstream_generate.tcl`。

---

## 8. 板上 1.14ms 推理是否实际依赖该 1GHz 时钟？

**依赖。** 推理时延（约 1.14 ms/帧）由 NPU 内核计算流水线产生，该流水线跑在
`AI_CORE_CLK`（1 GHz）上。故推理**实际依赖**该时钟。

但需区分两件事：

1. **依赖关系成立**：NPU 计算确实走 AI_CORE_CLK。
2. **违例是否影响正确性**：min-period 是**器件保证上限**。1 GHz 超出 BUFG(~709MHz)/
   PLL(~934MHz) 的保证值，意味着该时钟路径工作在**保证范围之外**——它"可能跑"（事实上
   Gate 7 已上板 `matched=227/240`，说明当前硅片/当前温度下确实能算对），但**不受时序
   保证**，可能随电压/温度/单粒差异而不稳定。

因此：**板上 1.14ms 推理结果不能替代时序签核**（这正是 Phase 1 指令明确禁止的
"用已有板端运行结果代替时序签核"）。板上成功只能说明"当前这颗片子此刻能跑"，不能
证明合并后的位流在保证条件下无 min-period 违例。

---

## 9. 决定性结论 + 对 §六硬门"Min Period = 0"的口径影响

1. **违例是 NPU 基线的固有属性**：`clk_out1_AI_CORE_CLK_ST_1` 的 1 GHz min-period 违例
   来自第三方 AI_Mate.edif 黑盒网表内部的 PLL 硬连线配置，**不能被任何"允许手段"消除**
   ——禁止 false path / 删除时钟约束 / 降低检查等级（Phase 1 指令明令），而修改
   AI_Mate 网表的 M/D 参数既不可行（未加密但第三方封装）也不在授权范围。
2. **位流照常生成**是因为位流门禁只看 DRC/布线、不看 pulse-width，这是**原工程自带的
   已知豁免**，不是合并引入的新问题。
3. **对合并位流硬门的影响**：若 §六硬门写死"Pulse Width violations = 0 / Min Period
   violations = 0 / Max Period violations = 0"，则合并位流**永远无法签核通过**——因为
   合并继承 NPU 基线就必然带着这 2 个 AI_CORE_CLK min-period 违例端点（与 NPU 基线
   `WPWS=-0.409/TPWS=-0.479/2 failing endpoints` 完全一致）。

   **建议口径**（需用户确认后写入 §六）：硬门改为——
   > "Pulse Width / Min Period / Max Period 违例 **除预存在 AI_CORE_CLK 1GHz 基线豁免外**
   > 必须为 0；即：合并位流的 PW 违例集合 **⊆** NPU 基线的 PW 违例集合（仍是那 2 个
   > `plle2_adv_inst/CLKOUT0` + `clkout1_buf/I` 端点，不得新增任何其他 PW/min/max 违例）。"

   同时保留 WNS≥0 / WHS≥0 / TNS=0 / THS=0 / DRC 0 error 不变，并新增对
   `clk_out1_AI_CORE_CLK_ST_1` 的**逐次 diff**：确认其周期仍为 1.000ns、仍是同一 PLL 源、
   违例端点仍是那 2 个（不多不少）。

4. **合并是否可能加剧**：HDMI 侧新增时钟（27/74.25/371.25/100MHz MMCM）与 AI_CORE_CLK
   分属不同 MMCM/PLL、不同异步组，理论上不改变 AI_CORE_CLK 的 min-period 结论；但须在
   M5/M7 综合后以 §6 证据同口径复核（确认违例端点集合未扩大）。

---

## 10. 证据清单（可复现路径）

| 证据 | 文件 |
|---|---|
| 时钟名 + 周期 + Clock Summary | `fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_timing_summary_routed.rpt`（Line 127-132, 191） |
| 两违例端点详细行 | 同上（Line 36427-36440） |
| PW 汇总行 | 同上（Line 36421） |
| 专报 pulse-width 全路径 | `reports/pl_ddr_mandatory_core_v1/diag_ai_clk/ai_clk_pulse_width.rpt`（Line 34-43） |
| XDC 无 create_clock、仅 LOC | `constrs_1/ai7030.xdc`（Line 6） |
| 位流门禁=DRC 非时序（原文） | `run_bitstream_generate.tcl`（Line 8-10） |
| DRC 0 error + 位流尺寸 | `reports/pl_ddr_mandatory_core_v1/bitstream_gate.txt` |
| route 状态 + Failed Timing | `reports/pl_ddr_mandatory_core_v1/cdc_routed_timing_gate.txt` |
