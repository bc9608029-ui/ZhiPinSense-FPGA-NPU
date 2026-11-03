# B 线 m4 续跑 + 三项审计（回应 39e5 审查）

日期 2026-10-29。m4 布线在 Phase 4.2 被杀后，按审查意见：从 placed 检查点续跑，补三项审计；不改 RTL、不放宽约束、不碰 FFT。

## 审计 #1 — 时序口径（THS vs WHS）

- **THS（Total Hold Slack）= 所有失败 hold 路径的负裕量之和**；**WHS（Worst Hold Slack）= 最差单一路径的 hold 裕量**。
- 前次中间态：`THS=-4767.777 ns` 是**总和**，不是某一条路径差 4.7 微秒；当时最差单路径 `WHS=-0.647 ns`。二者不能混用。
- 同样：setup 侧 WNS=最差单路径、TNS=所有失败路径之和。
- **续跑脚本已把四量分离打印**（`M4R_TIMING wns=… tns=… whs=… ths=…`），最终以布线后 `report_timing_summary -delay_type min_max` 为准（`outputs/smartscan_candidate_v1/reports/timing_summary_routed.rpt`）。
- 判定口径：hold 最终须 **WHS ≥ 0**（单路径全部通过）；setup 须 **WNS ≥ 0**。不达标即不宣称 PASS。

## 审计 #2 — DDR 时钟 `CLOCK_DEDICATED_ROUTE=FALSE` + PLCK-23

结论：**继承自已验证基线，非 smartscan 引入**。

证据：
1. 约束来源 = MIG 自身生成的 XDC：`fpga/npu_base/rtl/ip/mig_7series_0/mig_7series_0/user_design/constraints/mig_7series_0.xdc:33`
   `set_property CLOCK_DEDICATED_ROUTE FALSE [get_pins -hierarchical *clk_ref_mmcm_gen.mmcm_i*CLKIN1]`
   —— 这是 DDR3 控制器 IP 自带生成文件，非手工放宽。
2. 告警对象 = DDR3 参考时钟 `u_ddr3_clk_ibuf/diff_input_clk.u_ibufg_sys_clk (IBUFDS.O @ IOB_X1Y124)` → `u_iodelay_ctrl/clk_ref_mmcm_gen.mmcm_i (MMCME2_ADV_X0Y0)`，即 MIG 的 **iodelay_ctrl 校准参考时钟**，非功能数据通路时钟。
3. 基线同样存在：`build/m4_impl_bitgen_combined_r03b.log:867/1180`、`r02.log:869/1191` 与 smartscan `r04.log:868/1178` **逐字同一告警、同一 net、同一 IOB_X1Y124 / MMCME2_ADV_X0Y0**。

影响评估：该参考时钟仅用于 MIG 的 IODELAY 校准；`clk_ref` 走非专用布线会使校准参考插入延迟变长，但由 MIG 自身校准吸收；DDR3 数据通路时序由 MIG 单独分析。基线位流（smoke_v1 `22fec95c`）已板端验证 DDR 正常，故为**已知且已接受**条件。最终仍由布线后 hold/setup 报告确认无真实违规（不因"DRC 零错误"略过）。

## 审计 #3 — 运行保障（续跑不受会话结束影响）

- 续跑脚本 `fpga/m4c_resume_route_smartscan.tcl`：`open_checkpoint placed DCP` → `route_design` → `write_bitstream` → 报告 → 复制位流。**不 reset_run、不 launch_runs**（否则抹掉 placed 检查点）。
- 守护启动 `build/resume_route_smartscan.bat`：由 Windows 计划任务 `smartscan_m4c_resume` 调用，**脱离 Claude Code 会话独立运行**（PID 14540 已在 Task Scheduler 下运行）。
- 完成标记：`build/m4c_resume_route_smartscan.rc`（含 `M4C_DONE_RC`）+ 日志 `M4R_*` 标记；后台监视器在 `.rc` 出现时通知。
- 完成后核验项：布通（M4R_ROUTE_DONE + 位流存在）、时序（WNS/WHS/TNS/THS）、约束覆盖（CDC XDC active + 时钟/例外在报告内）、目标器件（报告头 part=JFMQL30TAI676H）。全部通过才 m5 Procise disable_icap 生成候选位流。

## 红线保持

不碰板 / 不写 Flash / 不发射；`production_bitstream=NO`；不改 FFT / RTL / 约束 / 不放宽时序。
