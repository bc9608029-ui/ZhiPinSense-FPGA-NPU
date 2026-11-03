# FPGA 辅助智能扫频 PREP2 交接

状态：`PRODUCTION_OOC_COMPLETE_PSPL_AND_BITSTREAM_PENDING`。

本包完成了电脑侧可以诚实完成的部分：Golden、固定点合同、窗口和功率 RTL、明确的
Procise FFT 边界、自然序到 fftshift 双缓冲写入模块、极值/短帧反例、四组向量和完整
目标构建/板测/回退顺序。

设计分工冻结为：FPGA 负责窗函数、1024 FFT、幅度平方和双缓冲；CPU 继续负责噪声底、
自适应阈值、bin 合并、频段拼接、目标跟踪和 UI。这能增加 FPGA 的实质计算量，同时不
改变模型输入或现有识别算法。

先运行：

```powershell
python scripts/selftest.py
python scripts/selftest_prep2.py
powershell -ExecutionPolicy Bypass -File scripts/hdl_sim.ps1
```

XSim 2018.3 已通过显式路径找到并重跑；边界测试与 2048-bin 双帧背压测试均通过。
Vivado 2018.3 配合 FMSH ip_patch 5.3.1.8 已实际生成并综合 XFFT 9.1，确认其真实配置为
1024 点、自然序、无缩放、16-bit 复数输入、27-bit 复数输出、64-bit AXI 数据和 XK_INDEX。
因此旧 26/52 位预估已作废，RTL、Golden 和测试统一修正为 27/54 位。

Procise 2025.1.1 已在目标器件 `JFMQL30TAI676H` 上完成“窗函数 + 54-bit 模平方 + 双缓冲写入”
OOC 综合、布局布线和 STA：100 MHz 最差裕量 `+0.1784 ns`，使用 622 LUT、152 Slice Register、
6 CU、0 RAMB。该数字只属于不含 FFT 的内部激励 OOC 外壳，不能冒充完整系统资源或时序。

尚未完成：生产数据通路整体 OOC 已完成（**已完成**，
`SMARTSCAN_PRODUCTION_OOC_RESULT result=PASS`，含 Hann 窗 framer + 迁移 XFFT + u54 模平方 +
fftshift 双缓冲，100 MHz setup +0.154/hold +0.101 ns，3740 LUT/4707 FF，两库均推出一口 1024×64
块 RAM，见 `VERIFICATION_STATUS.md`）。剩余：PS→PL AXI 数据通路、双缓冲回读、自动回退、候选位流
以及板端 A/B/RF 回归。现有正式位流和服务均未修改。

下一位必须严格执行 `BOARDTEST_SMART_SCAN.md`。不得把 Vivado XFFT OOC 或不含 FFT 的 Procise
后级 OOC 数字冒充完整 FMQL30TAI 智能扫频链；不得覆盖旧位流或现有正式服务。
