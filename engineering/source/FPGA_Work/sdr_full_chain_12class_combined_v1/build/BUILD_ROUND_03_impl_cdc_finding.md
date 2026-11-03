# Build Round 03 — 实现/写位流 + CDC 时序发现（smoke_v1 第 2 步）

时间：2026-10-06
工程基座：`fpga/npu_base/fpai_demo_vivado.xpr`（Part=xc7z030ffg676-2）
前置：Round 02 综合成功（synth_1 100%），`m4_impl_bitgen_combined.tcl` 复用该 checkpoint。

## 本轮动作
仅跑 `m4_impl_bitgen_combined.tcl`（实现 + 写位流 + 从同一 routed DCP 出报告）。
RTL/XDC 未改（相对 Round 02）。`-jobs 1`，状态门 `PROGRESS==100%`。

## 磁盘（构建前）
C: 35.6G free；F: 851.2G free（均高于门限）。

## 关键发现：clk_74m25 ↔ clk_out1_clk_wiz_0（gp_clk）被当作相关时钟计时且违规
（来自 `build/diag_clocks.txt` 的 report_clock_interaction，综合后估算）

```
clk_74m25        -> clk_out1_clk_wiz_0   WNS -3.75  TNS -111.39  34 failing   req 0.03  Timed
clk_out1_clk_wiz_0 -> clk_74m25          WNS -4.72  TNS -793.99  290 failing  req 0.03  Partial False Path
```

其余相关对均 Clean/Ignored（异步组已正确隔离 hp_clk 与像素域：`clk_out1_clk_wiz_0 ↔ clk_out1_clk_wiz_core_50`
= Ignored/Asynchronous Groups）。

### 根因
Round 02 把 HDMI 像素时钟链从「200MHz 晶振 → MMCM1(200→27) → MMCM2(27→74.25/371.25)」改为
「gp_clk(100MHz, PS7 PLL) → 单 MMCM → 74.25/371.25」。这使 **像素时钟变成 gp_clk 的生成时钟**，
于是 frame_ctrl（gp_clk 域）↔ 显示（cam_clk 域）的跨域在 Vivado 里从「异步」变成「相关」，
被按 inter-clock 相关路径计时，且 req≈0.03ns 极紧，必然违规。

### 为什么这是约束问题而非真 bug
- frame_ctrl（gp_clk）→ 显示（cam_clk）跨域在 RTL 内**有完整同步器**：
  `bridge_s` / `level_cross` / `pulse_cross_camera`（frame_ctrl.v / bridge_s.v，官方 FMSH RTL），
  与 fb_read_720p 的 buf_sel 2-FF（gp_clk→hp_clk）——功能上本就是异步 CDC。
- 官方两处 XDC 都明确把这跨域当异步裁掉：
  - `hdmi_framebuffer_720p.xdc`：`set_clock_groups -asynchronous`（hp_clk / 74.25 / clk_wiz_0 三组）。
  - `ai7030.xdc`：`set_false_path GP↔cam`（但用了旧层次 `U0_ps_ai_peripheral` + `rx_sdi_inst`，
    在组合设计里无匹配、被静默忽略）。
- 我在 Round 02 改时钟源时让像素时钟与 gp_clk 相关，等于**无意破坏了官方原有的异步隔离**。

## 计划修复（最小、约束级、待 m4 post-route 报告确认后执行）
在 `pl_ddr_integration_v1/cdc_async_groups.xdc` 增补：
```tcl
set_false_path -from [get_clocks clk_out1_clk_wiz_0] -to [get_clocks clk_74m25]
set_false_path -from [get_clocks clk_74m25]        -to [get_clocks clk_out1_clk_wiz_0]
```
- 仅裁 gp_clk↔cam_clk 这一对（报告确认只有这对违规；clk_371m25 无跨回 gp_clk 的计时路径）。
- 用 `set_false_path` 而非 `set_clock_groups -asynchronous`：cam_clk 是 gp_clk 的生成时钟，
  相关时钟之间用 false_path 更规范（`set_clock_groups -asynchronous` 对相关时钟会告警）。
- **不是为 PASS 而放宽**：这是恢复官方 ai7030.xdc / hdmi_framebuffer_720p.xdc 本就声明的
  GP↔cam 异步隔离（因层次名失效未生效）；RTL 同步器已核对存在。
- 属约束级改动，不改 RTL、不重综合，仅重跑 impl_1。

## 下一步
1. 等 m4 完成 → 读 `outputs/smoke_v1/reports/timing_summary_routed.rpt` + `clock_interaction.rpt` +
   `cdc_routed.rpt`（report_cdc）确认 post-route 同样只有 clk_74m25↔gp_clk 违规、且 report_cdc
   无 unhandled CDC。
2. 若 report_cdc 报 CDC-2（缺 ASYNC_REG），再把官方 hdmi_framebuffer_720p.xdc 的 ASYNC_REG 标签
   按组合层次（`u_ps_ai_peripheral/...`）补上（同属约束级）。
3. 应用 set_false_path（+ 如需 ASYNC_REG）→ 重跑 impl_1 → 重新出报告 → 继续 m5 Procise / 打包 / 冻结。
