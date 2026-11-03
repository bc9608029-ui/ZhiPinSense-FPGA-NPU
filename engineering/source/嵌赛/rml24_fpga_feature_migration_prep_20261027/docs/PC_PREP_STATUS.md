# 电脑侧准备状态

已具备：

- 既有 Power/Lag RTL、帧控制、量化与张量打包源码；
- 19 帧、19,456 点冻结向量及 Python/RTL 零差异历史证据；
- 新增 Energy/Peak 统计 sidecar 与 RMS 派生合同；
- 软件/FPGA/自动回退接口合同；
- 分级板测与回退清单。

未声称完成：Procise 综合/P&R/STA、PS→PL 实际适配、板端 A/B、真实 RF 回归、启动固化。目标器件是 FMQL30TAI/Procise，因此本包不生成虚假的 Vivado 工程或时序数据。
