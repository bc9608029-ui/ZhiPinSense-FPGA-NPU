# FPGA 特征迁移冻结合同

目标是增加真实 PL 计算量，同时不改变当前 24 类识别输入和 98% 级闭环。

- 输入：two-DC 恢复后的 1024 个 `int16 I/Q`，仅在 `valid && ready` 时接收。
- 逐点特征：`Power=u32`、`LagRe/LagIm=s33`；每帧首点 Lag 固定为 0。
- 帧统计：PL 输出精确 `Energy=sum(Power)`、`Peak=max(Power)` 和计数；CPU 从 Energy 计算 RMS。这样避免为了显示参数加入平方根硬核。
- 原始 I/Q 继续逐字节进入冻结 BF16 模型；本阶段不把 Power/Lag 注入现有模型，不改 two-DC、门限、扫频器或模型。
- 后端必须有 `software|fpga|auto` 三态；`auto` 在超时、帧号、长度、CRC/比对或硬件状态异常时退回软件。

板端验收必须先证明：同一批恢复 IQ 下，软件与 FPGA 的逐点整数特征完全一致，Energy/Peak/计数完全一致，模型输入 SHA 和预测不变。
