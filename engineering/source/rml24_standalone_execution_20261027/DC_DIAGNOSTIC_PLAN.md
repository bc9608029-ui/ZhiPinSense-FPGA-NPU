# 独立 DC 跟踪对照（计划；运行前不得称通过）

**最新状态：没有执行，暂缓该假设。** 随后直接检查了10个AM-DSB-WC源波形：主峰在第32个FFT bin，即80 kHz，而非DC；均值/RMS仅约0.00014–0.00135。因此，虽然芯片近DC校正机制确实存在，但不能据此解释本轮该类混淆。
准备的shim与diagnostic_tx均未部署、未运行，不能说关闭跟踪有效，也未修改Pluto跟踪开关。保留以下计划仅作为排查历史。

正式回归：模型、two-DC、样本、帧结构及 RF 配置保持冻结。
正式定频结果 227/240，其中8起错误是AM-DSB-WC→AM-DSB-SC；同一持续发射项的后续捕获也可出现类别变化。
完整有效帧中恢复所得 CFO 约为 -97 至 -70 Hz。它们是测得值，不是根因证明。

ADI 官方资料说明 AD936x 有 RF/BB 两级 DC 校正，接近DC的信号可能影响校正；BB跟踪使用高通环路。
来源：
- https://ez.analog.com/rf/wide-band-rf-transceivers/design-support/a/documents/DO26515/ad936x_dcoffset_issue
- https://www.analog.com/media/en/technical-documentation/user-guides/AD9361_Reference_Manual_UG-570.pdf

待证伪假设：当前 Plutο 的 DC 跟踪损伤了期望载波，而不是模型文件被修改。
不能仅凭混淆表认定这一原因，也不能未经对照就把关闭跟踪作为正式修复。

对照在完整正式回归结束后进行：

1. DEFAULT：保持实际原有DC跟踪，记录BB/RF开关读回。
2. BB_OFF：仅本次关闭BB跟踪；其余条件不变。
3. 如前两臂未能说明问题，再运行BOTH_OFF探索臂；这是不同条件，不替代原正式结果。

每臂使用原240集合中全部10个AM-DSB-WC波形，每项6秒，间隔0.25秒，前后静默8秒。
沿用固定时间窗第一捕获计分。类别、文件名和发射时间真值只在电脑，不传入接收器。
这是针对已观察错误类的诊断，不能当作24类泛化准确率或测试集上调参后的独立验证。

`pluto_dc_diagnostic_shim.py` 仅安装到独立 `dc_diagnostic_legacy`，不改原legacy文件，也不改冻结接收器/模型。
通过原Radio的属性保存/恢复机制回退，并检查应用读回；每臂后再独立读取开关确认恢复。
本轮不会因诊断看起来改善就覆盖原正式版本。
