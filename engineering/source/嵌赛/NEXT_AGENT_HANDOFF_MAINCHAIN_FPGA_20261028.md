# RML24 主链与 FPGA 智能扫频总交接

## 1. 先处理主链冻结候选

入口：`rml24_mainchain_finalize1_20261028/NEXT_AGENT_HANDOFF.md`

包：`rml24_mainchain_finalize1_20261028.zip`

SHA256：`e4670f8610ba968ce9ef80cad01984728079ca90669de364b51af02f32aca460`

真实 RF 固定分母结果：定频原基线 227/240、候选 233/240、漏项 0；扫频原基线
232/240、候选 237/240、漏项 0。逐行严格门为 `PROMOTION_CANDIDATE`。五页 UI2 离线
测试通过，但仍需目标板原生 C++ 构建、24+24 smoke、物理触控和恢复验证。不得直接覆盖
正式服务。

## 2. 再处理 FPGA 辅助智能扫频

入口：`rml24_fpga_smartscan_prep2_20261028/NEXT_AGENT_HANDOFF.md`

包：`rml24_fpga_smartscan_prep2_20261028.zip`

SHA256：`6c25f30be9ab455f7cd0a88dac0f5827a17b066544fe59b5144504834ae83b6a`

电脑侧 Golden、固定点、FFT 后级 u54、fftshift 地址、双缓冲协议、测试向量、测试台和
板测手册已准备。真实 Vivado 2018.3 + FMSH patch 已生成并综合 XFFT 9.1，确认输出为
27 bit，因此旧 26/52 位预估已作废。XSim 边界与 2048-bin 双帧背压仿真通过；Procise
2025.1.1 在 JFMQL30TAI676H 上完成不含 FFT 的后级 OOC P&R/STA，100 MHz slack +0.1784 ns。

当前状态是
`VIVADO_XFFT_SYNTH_AND_POSTFFT_PROCISE_OOC_COMPLETE_FULL_INTEGRATION_PENDING`。官方 FMSH
XFFT DCP→Procise 迁移已实际尝试，但在 `runEco0` 持续报 `Unrecognized character`，无 PASS，
已停止并保留重现脚本与报告。尚未形成完整 XFFT+后级 Procise 工程，也没有 PS/PL 通路、
候选位流或板端 A/B。

2026-10-28 最新暂停点见
`rml24_fpga_smartscan_prep2_20261028/PAUSED_HANDOFF_20261028.md`：已定位失败 `runEco0`
替换 Vivado `xc7k325t.paspd` 的副作用，已备份并恢复 Xilinx 原版；已准备在同一成功综合
会话直接导出 EDIF 的流程。最终干净重建按用户要求中止，所有 Vivado/Procise/XSim 进程
均已停止，恢复时应从脚本重新运行，不得声称已有完整迁移 PASS。

必须先解决官方迁移兼容问题，在 Procise 中完成冻结配置 XFFT 与后级的完整实现，再上板。旧位流、
现有模型、two-DC 和软件扫频始终保留；任何错误由 `auto` 后端回退软件路径。

## 顺序红线

先验收主链，再开展 FPGA 新位流。FPGA 扩展不得阻塞、替换或降低当前主链；不得把旧 XSim
边界测试、Python FFT 或 FMSH catalog 条目写成目标 FFT 已完成。
