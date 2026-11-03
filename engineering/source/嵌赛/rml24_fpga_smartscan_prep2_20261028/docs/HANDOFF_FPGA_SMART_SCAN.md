# FPGA智能扫频电脑侧交接

本包完成 Golden、固定点窗、检测参考、极值位宽修正、RTL 边界模块、测试向量生成和
Procise 接线合同。Vivado 已实际生成/综合 XFFT 9.1；Procise 已完成不含 FFT 的后级 OOC
综合、布局布线和 100 MHz STA（裕量 +0.1784 ns）。它仍不是完整综合位流。

先运行：`python scripts/selftest.py`。随后解决 `XFFT_MIGRATION_ATTEMPT.md` 记录的官方迁移
兼容问题，再在 Procise 独立工程中连接 `window_mul_q15.sv`、迁移后的 XFFT 9.1 及
`fft_magnitude_square_u54.sv`。CPU V1 继续承担噪声底、门限、bin 合并、频段拼接和目标跟踪。

旧26/52位规划已被真实 XFFT 9.1 生成结果纠正为27/54位。不得拿Vivado资源估计冒充FMQL30TAI/Procise结果。
