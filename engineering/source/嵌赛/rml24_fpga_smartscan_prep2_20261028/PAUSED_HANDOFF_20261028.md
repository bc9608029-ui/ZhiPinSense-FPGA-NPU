# FPGA 智能扫频暂停交接（2026-10-28）

状态：`COMBINED_OOC_COMPLETE_PSPL_AND_BITSTREAM_PENDING`。

## 已完成且仍有效

- 既有 Power/Lag、Energy/Peak 资产未修改；
- 27/54-bit Golden、RTL、XSim 边界和 2048-bin 双帧背压测试通过；
- XFFT 9.1 配置已确认：1024 点、16-bit 输入、27-bit 输出、自然序、无缩放、XK_INDEX；
- 不含 FFT 的 Procise 后级 OOC 在 JFMQL30TAI676H、100 MHz 下 P&R/STA 通过，slack +0.1784 ns；
- 主链、模型、two-DC、UI、正式服务和正式位流均未修改。

## 本轮新定位

官方 `fmsh_migration_process` 的 `runEco0` 会把 Vivado 安装目录中的
`xc7k325t.paspd` 从 Xilinx 原版替换为 FMSH 版，之后加载 XFFT netlist 会持续输出
`Unrecognized character`。被替换文件已备份到
`evidence/vivado_database_restore/xc7k325t.after_failed_runEco.fmsh.paspd`，并已使用
FMSH 补丁包自带的 `paspd/xilinx/xc7k325t.paspd` 恢复安装目录。恢复后两者 SHA 一致。

已准备“全新生成并在同一成功综合会话直接导出 EDIF”的流程，避免重新打开 DCP：

- `vivado_fft/build_xfft_1024.tcl`
- `scripts/build_vivado_xfft.ps1`

最终干净重建在 XFFT synthesis 期间被用户要求暂停，两个 Vivado 进程已终止；未生成新的
PASS/FAIL 结论。恢复工作时从上述 PowerShell 脚本重新开始，不要继续临时进程。

## 下一步

1. 复核安装目录 `xc7k325t.paspd` SHA 与补丁包 `paspd/xilinx` 原版一致；
2. 运行 `scripts/build_vivado_xfft.ps1`；  ← **已完成**，两个 PASS 标记均已看到。
3. 必须看到 `XFFT_PROCISE_EXPORT result=PASS` 和 `XFFT_BUILD_RESULT result=PASS`；  ← **已完成**。
4. 再把迁移后的 XFFT 与窗口/u54/双缓冲合成同一 Procise OOC 工程；  ← **已完成**，
   `SMARTSCAN_COMBINED_OOC_RESULT result=PASS`（100 MHz，setup +0.497 ns / hold +0.100 ns）。
5. 接下来：PS→PL 数据通路、双缓冲回读、自动回退、候选位流、板端 A/B/RF 回归。
   在此之前不得生成或加载正式候选位流，不得开始板端 A/B。
