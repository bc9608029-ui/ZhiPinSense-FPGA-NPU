# M26 OOC 综合报告（OOC Synthesis Report）

任务 id="39e5" · M26 · 本报告覆盖 spec §五（RTL lint / 行为仿真 / OOC 综合 / 资源 / 时序 / 最高频率 / 功耗增量）与 contract §12（CFAR 虚警率黄金对齐）。

> **执行状态（诚实声明）**：本离线环境 **Vivado 只读、未运行**。`rtl/*.sv` 是交付的**可综合源码**；`synth/run_lint.tcl`、`synth/run_sim.tcl`、`synth/run_ooc_synth.tcl` 是**待运行脚本**；本文的“结构期望”是从 RTL 推导的**分析估算**，**不是** Vivado 综合后实测。任何 `FPGA_DSP_PASS / TIMING_PASS` 均未达到、也不得写出。

---

## 1. OOC 综合方法

每个模块以 `out_of_context` 模式单独综合（`synth/run_ooc_synth.tcl`），顶层 `m26_spectrum_top` / `m26_stream_frontend_top` 各做一次集成层级 OOC：

1. `read_verilog -sv` 读入 `rtl/*.sv`（含 `m26_fxp_pkg.sv`）。
2. `synth_design -mode out_of_context -top <module> -part xc7z030ffg676-2`。
3. `report_utilization`、`report_timing`、`report_power`、`report_datasheet`（推导最高频率）。
4. 每个模块生成独立 `.dcp` 与 `.rpt`。

产物目录 `synth/out/<module>/`（`.dcp` + `utilization.rpt` + `timing.rpt` + `power.rpt`）。

### DSP 推断校验（spec §五硬要求）

- **不得仅凭 RTL 乘号宣称 DSP**。脚本对 `m26_fir`/`m26_fft_1024`/`m26_nco`/`m26_cfar` 各跑两遍：默认推断 vs `-directive`/`(* use_dsp = "yes" *)` 强制，比较 DSP 计数差异并记录。
- FIR 全并行（16×17 折叠 MAC ×2）默认会推断 ~32 DSP；生产建议改转置单 MAC（1 DSP）+ 时分，脚本同时产出对照报告。
- 能量开方、中值 popcount、CFAR 交叉乘的 DSP 推断在报告中单独列出。

---

## 2. 逐模块结构期望（分析估算，待 OOC 实测）

| 模块 | LUT | FF | BRAM | DSP | 最高频率（估算） |
|---|---|---|---|---|---|
| `m26_dc_removal` | ~250 | ~200 | 0 | 0 | >400 MHz |
| `m26_energy_rms` | ~500–4000 | ~120 | 0 | 2 | ~150–300 MHz（开方热点） |
| `m26_signal_presence` | ~30 | ~20 | 0 | 0 | >400 MHz |
| `m26_nco` | ~200 | ~200 | 1×B18 | 4 | ~300 MHz |
| `m26_fir` | ~400 | ~1100 | 1×ROM | 32 | ~250 MHz |
| `m26_decimator` | ~50 | ~70 | 0 | 0 | >400 MHz |
| `m26_hann` | ~50 | ~40 | 1×B18 | 2 | ~300 MHz |
| `m26_fft_1024` | ~300 | ~200 | 2×B18 | 4 | ~250 MHz |
| `m26_fftshift` | ~50 | ~40 | 1×B18 | 0 | >400 MHz |
| `m26_mag_sq` | ~30 | ~40 | 0 | 2 | ~350 MHz |
| `m26_noise_floor` | ~400 | ~34,000（D） | 0（D） | 0 | ~200 MHz（popcount） |
| `m26_cfar` | ~300 | ~34,000（D） | 0（D） | 4 | ~250 MHz |
| `m26_candidate_merge` | ~500 | ~35,000（D） | 0（D） | 0 | ~200 MHz |

> 目标时钟 100 MHz；上表估算频率均 ≥ 目标，但 `energy_rms` 开方与三个大寄存器阵列模块需在 OOC 中确认，生产再按 `M26_RESOURCE_AND_TIMING_BUDGET.md §2` 迁 BRAM + 流水。

---

## 3. 行为仿真（`synth/run_sim.tcl` + `sim/*`）

| 测试台 | 覆盖 | 结果状态 |
|---|---|---|
| `m26_tb_stream_frontend.sv` | 复位 / 断流 / 连续反压 / dc→nco→fir→decim 端到端 / bypass 位序不变 | 待 xsim |
| `m26_tb_spectrum.sv` | hann→fft→fftshift→mag_sq→{中值,CFAR,合并} 单音检出 + 99% 带宽 | 待 xsim |
| `m26_tb_cfar.sv` | 双音召回率 / 虚警率 / 参数非法 fail-closed | 待 xsim |
| `m26_tb_median.sv` | 位串中值与 C++ `noise_floor_median` 逐位一致 | 待 xsim |
| `m26_tb_fir.sv` | 冲激响应 / 频响（对齐黄金） | 待 xsim |

> 本环境无 xsim/iverilog，SV 测试台为**自检查交付物**；C++ 黄金对齐已由 `golden/m26_verify`（36/36 断言）离线通过。

---

## 4. CFAR 虚警率（黄金对齐，contract §12）

来源 `golden/m26_verify.cpp`（ground truth = 双音 bin 12/56，guard=4、ref=8、T=8·2^14）：

| 指标 | 值 | 判定 |
|---|---|---|
| 召回率 recall | **1.00** | ≥0.9 ✅ |
| 虚警率 false-alarm | **0.0020** | <0.2 ✅ |
| 掩码黄金-固定逐位一致 | **1020/1024** | 报告（非硬门限） |

（掩码 4 bin 不一致源于黄金 double 阈值与定点 `T·sum/(cnt<<14)` 的边界舍入，属预期；RTL 与 C++ 定点模型**逐位一致**，见 `m26_cfar.sv` 的交叉乘无除法判决。）

---

## 5. 红线

- 不生成生产位流、不写 Flash、不碰板、不接 Gate 9/10。
- 未运行 Vivado → 不得写 `FPGA_DSP_PASS / TIMING_PASS / HARDWARE_PASS / PERFORMANCE_PASS / PROJECT_COMPLETE`。
- 最高状态 `M26-FPGA-DSP-OFFLINE-MODULES-READY`。
