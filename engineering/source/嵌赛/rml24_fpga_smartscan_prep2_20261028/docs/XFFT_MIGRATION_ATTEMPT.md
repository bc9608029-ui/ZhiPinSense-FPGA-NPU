# XFFT 官方迁移尝试记录

## 已完成

- Vivado 2018.3 + FMSH ip_patch 5.3.1.8 实际生成并综合 XFFT 9.1；
- 生成物冻结为 1024 点、16-bit 复数输入、27-bit 复数输出、自然序、无缩放、XK_INDEX；
- 建立 `smartscan_fft_migration_top.v`，完成顶层 `synth_1` 后调用官方
  `fmsh_migration_process.tcl`；
- 迁移命令和重现入口已保留在 `scripts/migrate_xfft_to_procise.ps1`。

## 本次停止点

官方迁移脚本在打开 XFFT DCP 后进入 FMSH IP patch 的 `runEco0`，随后从
`INFO: [Project 1-570] Preparing netlist for logic optimization` 开始持续输出
`Unrecognized character`。日志增长到约 5 MB 且没有阶段完成标记，已主动终止，避免把
挂起过程写成成功。进一步确认 `runEco0` 把 Vivado 安装目录的 `xc7k325t.paspd`
替换成 FMSH 版本，使后续全新工程也出现同样错误。该文件已备份并恢复为补丁包自带的
Xilinx 原版。原始日志留在工作目录
`vivado_fft/migration_result/migration_console.log`，因体积和重复内容不放入交接 ZIP。

这不是 XFFT RTL 综合失败，也不是后级 Procise OOC 失败；它说明官方重复 ECO/DCP 重开路径
在当前安装组合下尚未收口。已准备同一成功综合会话直接导出 EDIF 的替代流程，但最后一次
干净重建按用户要求暂停，尚无最终 PASS。不得用空 FFT 或 Python FFT 冒充迁移成功。

## 2026-10-28 干净重建成功（替代流程收口）

重新运行 `scripts/build_vivado_xfft.ps1`，全程在**同一成功综合会话**内完成
`write_edif` + 直接 `translate_file_vvd_to_fmsh`，不再重开 DCP，因此不再触发
`runEco0` 的 `Unrecognized character`。结果：

- `XFFT_PROCISE_EXPORT result=PASS mode=same_synthesis_session production_bitstream=NO`
- `XFFT_BUILD_RESULT result=PASS ip=xilinx.com:ip:xfft:9.1 patched=YES production_bitstream=NO`
- 综合 0 errors / 0 critical warnings（1066 普通 warning，均为 IP 子层未接端口类）。

迁移产物（权威）：
- 净表 `vivado_fft/latest_result/migrated_procise/smartscan_fft_1024.edif`
  （已 `dsp_version_flag 13`，顶层 cell `smartscan_fft_1024`）。
- 约束 `.../smartscan_fft_1024.fdc`（仅 `create_clock aclk`，组合工程不引用）。

XFFT 独立综合资源（xc7k325tffg900-2，Vivado 口径）：2652 LUT、4411 FF、
4 Block RAM tile（8×RAMB18）、13 DSP48E1。合成/布线的关键固化参数在综合日志确认：
`C_OUTPUT_WIDTH=27`、`C_M_AXIS_DATA_TUSER_WIDTH=16`、`C_HAS_XK_INDEX=1`、
`C_HAS_NFFT=0`、`C_HAS_NATURAL_OUTPUT=1`、`C_HAS_SCALING=0`、`C_THROTTLE_SCHEME=0`。

下游 RTL 按 `.veo`/demo TB 定死位序（非猜测）：实部 `m_axis_data_tdata[26:0]`、
虚部 `m_axis_data_tdata[58:32]`、索引 `m_axis_data_tuser[9:0]`。

## 2026-10-28 组合 OOC 成功（迁移净表 + 窗口 + u54 + 双缓冲同工程）

把迁移后的 `smartscan_fft_1024.edif` 与 `window_mul_q15`、`fft_vendor_ip_adapter`、
`fft_psd_stream_writer` 合成同一 Procise 工程（`run_combined_ooc.tcl`），目标器件
`JFMQL30TAI676H`、100 MHz。首次失败在 `launch_run -stage synthesis` 的
`ERROR(SFE-E-311): The instanced module "smartscan_fft_1024" is unknown` ——
Procise 的 Verilog 细化器不会从 EDIF 净表解析被 Verilog 例化的模块名。

修复：新增 `(* black_box *)module smartscan_fft_1024(...); endmodule` 空体声明
（`smartscan_fft_1024_blackbox.v`，17 端口逐字节对齐 `.veo`），与 EDIF 一并加入工程。
这是 FMSH 自身流程为被例化 IP 生成 `_synth_stub.v` 的同一做法（其
`fmsh_source/DSP48P_bbox.v` 等即用 `(* black_box *)` 属性）。随后日志
`read_edif ...smartscan_fft_1024.edif` → `bind_design` → `uniquify` 证明净表真正被绑定。

结果 `SMARTSCAN_COMBINED_OOC_RESULT result=PASS includes_fft=YES production_bitstream=NO`：
- 综合资源：3149 LUT、4594 FF、19 CU48E1（13 = XFFT DSP48E1 + 6 = 窗口乘法器）、
  8 RAMH18E1、4 RAMH36E1(RAM/FIFO)、69 IO。
- STA 100 MHz：setup slack +0.497 ns、hold slack +0.100 ns，均 MET。
- 关键路径在窗口乘法器（20 级逻辑），不在 FFT 净表。

注意：该外壳使用 LFSR 内部激励和单位窗（`s_w=16'sd16384`），仅证明「迁移净表 + 后级」
在目标器件上可综合/布局/布线/时序收敛；它不是生产数据通路，未生成候选位流，也未做
PS→PL 通路、回读、自动回退或板端 A/B/RF。

