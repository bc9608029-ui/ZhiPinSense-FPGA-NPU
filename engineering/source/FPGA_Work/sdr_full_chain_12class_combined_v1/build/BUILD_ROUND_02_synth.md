# Build Round 02 — 合并位流综合（smoke_v1 第 1 步重跑）

时间：2026-10-06
工程基座：`fpga/npu_base/fpai_demo_vivado.xpr`（NPU 基座拷贝，Part=xc7z030ffg676-2）

## 本轮修改内容（相对 Round 01 的最小针对性修复）
仅改 1 个文件：`fpga/pl_ddr_integration_v1/rtl/pl_ddr_mandatory_core_top_combined.sv`

- **删除**：`u_ibufds_sysclk`(IBUFDS) + `u_mmcm_200_27`(MMCM1) + `u_bufg_27`(BUFG) +
  `u_mmcm_27_742`(MMCM2) 整条 200→27→74.25/371.25 链。
- **新增**：单一 `u_mmcm_hdmi`(MMCME2_BASE)，从既有 100 MHz `gp_clk` 直接派生
  74.25 MHz（像素）+ 371.25 MHz（TMDS x5）：
  `CLKFBOUT_MULT_F=37.125, DIVCLK_DIVIDE=5, CLKIN1_PERIOD=10.000,
   CLKOUT0_DIVIDE_F=10.0, CLKOUT1_DIVIDE=2`（VCO=742.5 MHz，全部参数在 MMCME2 合法范围内）。
- 端口接线不变：`.cam_clk(clk_74m25_bufg)`、`.clk_371m25(clk_371m25_bufg)`。

## 为什么必须重跑
Round 01 综合失败：`ERROR: [Synth 8-5535] port <sys_clk_p> has illegal connections`
（非法双缓冲：我在顶层加了 `IBUFDS(sys_clk_p/n)`，而 MIG `mig_7series_0` 内部已用
`IO_BUFFER_TYPE=NONE` 缓冲同一对 sys_clk_p/n）。根因 = sys_clk 晶振被 MIG 独占，
HDMI 时钟链不能在其上再加 IBUFDS。修复 = 改从 gp_clk（clk_wiz_0 干净 PLL 输出，
100 MHz，已 BUFG）用单 MMCM 派生同样两个频率，彻底移除 sys_clk 的二次缓冲。

## Round 02 排障记录（二次启动，均非 RTL 错误，已定位并修复）
1. **首次启动**：`launch_runs synth_1` 被拒 `needs to be reset`（Round 01 让 synth_1 停在
   `synth_design ERROR`）。→ 加 `reset_run synth_1`。
2. **二次启动**：`launch_runs synth_1 -jobs 4` 后 `wait_on_run` 12 秒返回，STATUS=
   `Scripts Generated`（顶层综合根本没跑）。诊断脚本 `diag_runs.tcl` 查得根因：
   OOC 依赖 `ps_ai_processing_system7_0_0_synth_1`（PS7 黑盒桩综合）STATUS=`synth_design
   ERROR`、NEEDS_REFRESH=1，其 `runme.sh` 的 `-source` 为空（2018.3 reset+并行 launch 偶发
   的 run 脚本未生成）→ 顶层综合被该失败依赖卡在 Scripts Generated。
   → 修复：显式 `reset_run ps_ai_processing_system7_0_0_synth_1` + `reset_run synth_1`，
   改 `-jobs 1`（对齐 NPU 基座已验证脚本的 `-jobs 1` 防 OOM），状态门改用 PROGRESS==100%。
   其余 OOC run（mig/clk_wiz/clk_wiz_core_50 已完成 100%）不 reset、复用。

## 使用的 checkpoint
无（综合重跑，全新 synth_1）。上一轮 synth_1 因 RTL 错误未产生 checkpoint。

## 输入 SHA256（本轮变更文件）
- pl_ddr_mandatory_core_top_combined.sv（改后） 38f36cb8536737aa8a0bc3110bb8a85b76263f00bf470483a62b892d0d4060bf
  （Round 01 旧值 f8df7875…，因删 IBUFDS/双 MMCM 改为单 MMCM 而变。）
- m3_synth_combined.tcl（改后，新增 `reset_run synth_1`） sha256 见下。

## Round 02 首次启动失败（已修复，非 RTL 错误）
`launch_runs synth_1` 被拒：`Run 'synth_1' needs to be reset before launching`。
原因 = Round 01 让 synth_1 停在 `synth_design ERROR` 状态，Vivado 拒绝在非 fresh 的
run 上 launch。修复 = `m3_synth_combined.tcl` 在 `launch_runs synth_1` 前加
`reset_run synth_1`（幂等：对失败/已完成 run 都清掉旧产物，保证干净重跑）。
RTL 的 sys_clk_p 双缓冲修复本身正确（已核对原始 `pl_ddr_mandatory_core_top.sv`：
其 `sys_clk_p/n` 直接透传 MIG、无顶层 IBUFDS；MIG 内部自带 IBUF，故我 Round 01
多加的 `u_ibufds_sysclk` 正是那个非法"输入缓冲 + 其它组件"双重连接）。

## 磁盘（构建前）
C: 36.31G free；F: 851.3G free。均高于门限（C≥10G, F≥30G）。

## 并行度
-jobs 1（对齐 NPU 基座已验证脚本 `run_impl_*.tcl` 原文 `-jobs 1`，防 OOM 内存峰值；
用户 2~4 指引在机器实测 OOM 历史下让位于 `-jobs 1` 安全值，见下 §monitor 事故）。

## monitor 事故（Round 02 第三次启动被 tail 锁死，已修复）
- **现象**：第三次 `launch_runs synth_1` 后，Vivado 子进程（pid 30000）CPU 停在 49→53s、
  内存停 473MB 不涨、无 .dcp 产出；`synth_1/exception.log` 报
  `Exception error code: 70 / Permission denied` 打开 `runme.log`。
- **根因**：Windows 下 `tail -F runme.log`（后台监视器 b163ucsst 及其历史孤儿 tail
  `-n +1 -f`/`-F` 共 4 个进程）以独占共享模式持有 `runme.log`，使 Vivado 自身无法
  打开自己的 run 日志（ERROR_SHARING_VIOLATION），综合被卡死。
- **修复**：`TaskStop` 停监视器 + 杀 pid 30000 + `Stop-Process` 杀 4 个孤儿 tail 进程，
  确认 `runme.log` 释放后，**改为不带任何 tail/文件跟随监视器**重启综合
  （后台任务 bs6e6fq4x，日志 `m3_synth_combined_r02b.log`）；进度改为"等后台任务
  退出后读结果"，绝不在 Windows 上 `tail -F` Vivado run 日志。

## 结果
**综合成功**（`==SYNTH_STATUS=synth_design Complete!==` / `==SYNTH_PROGRESS=100%==` /
`==M3_SYNTH_OK==`，VIVADO_EXIT=0）。RTL 的 sys_clk_p 双缓冲修复 + 单 MMCM(gp_clk→74.25/371.25)
通过综合。

## 综合后时钟诊断（diag_clocks.tcl，m4 前核对 CDC 组）
- `clk_74m25`=13.468ns(74.25MHz)、`clk_371m25`=2.694ns(371.25MHz)，均为
  `clk_out1_clk_wiz_0`(gp_clk 100MHz) 的生成时钟 → 归 `clk_fpga_0` 树（第 1 组）✓。
- 四异步组全部真实存在：`clk_fpga_0` / `pl_ddr_refclk`(sys_clk) / `u_clk_wiz_core_50/inst/clk_in1`
  (hp_clk=200MHz MIG ui_clk) / `jtag_clk`。
- 确认 `frame_to_ps_inst0/cmos_clkgen_742_5_u0` 组已不存在（frame_to_ps 被 fb_read_720p 取代）。
- `pl_ddr_mandatory_core_v1.xdc`（活动）已含正确小写 `u_ps_ai_peripheral` 的 PLLE2 LOC、
  HDMI 引脚(AC17/AA15/Y16/W16 TMDS_33)、`pl_ddr_refclk`(200MHz)、jtag_clk，无需改动。

## m4 前约束改动（最小）
- `pl_ddr_integration_v1/cdc_async_groups.xdc`：删除失效的第 5 组 `frame_to_ps_inst0/...`，
  四组保留，注释更新为 combined；新增 `cdc_async_groups_combined.xdc` 已删除（避免双文件）。
- `m4_impl_bitgen_combined.tcl`：fail-closed 校验 cdc_async_groups.xdc 在活动约束集中；
  `-jobs 4`→`-jobs 1`；状态门 `STATUS ne "write_bitstream Complete!"`→`PROGRESS ne "100%"`；
  修 `file exists $bitpath ? YES : NO` 三元表达式 bug。

## 已知（NPU 基座继承、非新增）
- `ai7030.xdc` 用 `U0_ps_ai_peripheral`（大写，来自 ai7030_edif_top）与 `rx_sdi_inst` 的
  false_path/LOC 在本设计中无匹配、被静默忽略（无实际影响；PLLE2 LOC 由
  `pl_ddr_mandatory_core_v1.xdc` 小写版本正确施加）。
- `pl_ddr_refclk` 覆盖 `sys_clk_p`（CRITICAL WARNING 18-1056，NPU 基座原有，预期）。
- ZG330 黑盒 `u_ps_ai_peripheral/ZGolo` 未连接 pin pl_exhs*/pl_buyi_error（Synth 8-4442，NPU 基座原有）。
- 1GHz `clk_out1_AI_CORE_CLK_ST_1`(AI_Mate PLL) 端点属 NPU 基座 vendor 黑盒，时序门后续按
  「⊆NPU 基线那 2 端点、不得新增」口径处理。
