# FMSH 技术支持确认请求：1 GHz AI Core 时钟 BUFG Min-Period 违例

**状态**：唯一 P0 阻塞项，等待 FMSH FAE 书面确认后进入出位流阶段。
**我方立场**：暂不 waive、不降频、不生成 bitstream。

---

## 一、环境

- Vivado **2018.3**（D:\Xilinx2018.3\Vivado\2018.3）
- 器件 **xc7z030ffg676-2**（FMQL30TAI 悟净开发板）
- 工程：官方 `fpai_demo_fpga` + FMSH `ip_patch`（`run.tcl` + `process_control/*.tcl` 钩子）
- 实现策略：Performance_NetDelay_high（官方默认）

## 二、违例事实（实测 report_pulse_width -verbose）

时钟 `clk_out1_AI_CORE_CLK_ST_1`：

| Check Type | Lib Pin | Required | Actual | Slack | Location | Pin |
|---|---|---|---|---|---|---|
| **Min Period** | **BUFG/I** | **1.409 ns** | **1.000 ns** | **−0.409 ns** | BUFGCTRL_X0Y20 | …/AI_CORE_CLK/inst/clkout1_buf/I |
| Max Period | PLLE2_ADV/CLKOUT0 | 160.000 | 1.000 | +159.000 | PLLE2_ADV_X1Y3 | …/plle2_adv_inst/CLKOUT0 |
| Low Pulse Width | FDRE/C | 0.350 | 0.500 | +0.150 | SLICE_X110Y0 | …/ai_core_clk_locked_reg/C |
| High Pulse Width | FDRE/C | 0.350 | 0.500 | +0.150 | SLICE_X110Y0 | …/ai_core_clk_locked_reg/C |

**结论**：唯一违例是 BUFG 最小周期检查 —— 1 GHz（1.000 ns）进入 7 系列全局时钟缓冲 BUFG，而该 BUFG 的器件最小输入周期为 **1.409 ns**（约 709.7 MHz），slack −0.409 ns。FD 本身的低/高脉宽（+0.150 ns）与 Max Period（+159 ns）均满足。

该时钟当前仅驱动 1 个寄存器：`ai_core_clk_locked_reg`（lock 指示），无实际 NPU 逻辑负载。

## 三、时钟来源链

```
pl_ddr_refclk (200 MHz, create_clock -period 5.000)
  └─ clk_pll_i_1 (200 MHz)  ← MIG DDR3 infrastructure MMCM
       └─ PLLE2_ADV "AI_CORE_CLK"  @ PLLE2_ADV_X1Y3
            CLKFBOUT_MULT=5, CLKOUT0_DIVIDE=1, DIVCLK_DIVIDE=1
            └─ clk_out1_AI_CORE_CLK_ST_1 (200 MHz × 5 = 1 GHz)
```

PLL 参数来自 `rtl/edif/AI_Mate.edif` 与 `AI_Mate_no_detpost.edif`（两文件参数逐字节一致），非本阶段新增，为官方 NPU 标称主频 1 GHz（见 `docs/hardware_document_audit/README.md`）。

## 四、官方 hook 排查结果（已逐份通读）

`ip_patch/process_control/` 全部 6 个 hook + `run.tcl`，**均无**针对 `clk_out1_AI_CORE_CLK_ST_1` 或 BUFG Min-Period 的 waiver。它们只处理：

- JDY_ip_top_0_route.dcp 锁定 / pblock / PROHIBIT
- bh_mig_oserdes ECO、MIG PLL CLKOUT5 false_path
- DDR PHY CTSBUS/DTSBUS false_path（PHASER_OUT）
- DRC REQP-44/46/52/56 disable
- bitstream USERID 32'h00000529

`all_src_files.tcl`（1294 行）与 `top.tcl` 为 XOR 加密专有内容，无法逐行排除内部含 1 GHz 豁免（但作用域为 JDY/MIG/板级基础设施，且该违例本不阻断位流）。

## 五、官方 bitstream 证据

- 官方预编译位流：`04_ICraft/v3.36.1/FMQL30TAI参考实现/悟净开发板/位流/.../ai7030_top_disable_icap.bit`
- 官方设计 PLL 参数与本工程一致 → 违例为确定性复现，非本阶段引入。
- Vivado `write_bitstream` 仅被 DRC ERROR 阻断，**时序（pulse-width）违例不阻断位流生成** —— 这解释了官方在无 waiver 情况下仍产出位流。

## 六、需 FMSH 确认的三个问题

1. 官方参考工程的实际 timing summary 中，`clk_out1_AI_CORE_CLK_ST_1` 的 BUFG Min-Period 是否同样为 −0.409 ns？官方是否**在存在该违例时仍正常生成 bitstream**？
2. 官方是否有针对该 1 GHz 时钟的内部 waiver / 特殊处理（含加密 `all_src_files.tcl`/`top.tcl` 内部），或明确"BUFG 超频至 1 GHz 为 NPU 标称配置、该 Min-Period 违例可接受"的书面说明？
3. 若不可接受，官方推荐的正确做法（标称频率 / 时钟结构 / 是否应绕过 BUFG）是什么？

---

*生成日期：2026-09-30*
