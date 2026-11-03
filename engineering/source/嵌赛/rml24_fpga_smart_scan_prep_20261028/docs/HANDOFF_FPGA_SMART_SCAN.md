# FPGA智能扫频电脑侧交接

本包完成Golden、固定点窗、检测参考、极值位宽修正、RTL边界模块、测试向量生成和Procise接线合同。它不是已综合位流。

先运行：`python scripts/selftest.py`。随后在Procise独立工程中导入`window_mul_q15.sv`、厂商FFT及`fft_magnitude_square_u52.sv`。CPU V1继续承担噪声底、门限、bin合并、频段拼接和目标跟踪。

旧51位模平方规划已被本包52位合同取代。不得拿Vivado资源估计冒充FMQL30TAI/Procise结果。
