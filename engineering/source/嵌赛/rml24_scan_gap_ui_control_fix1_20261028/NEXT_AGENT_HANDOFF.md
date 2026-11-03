# 下一位唯一交接入口（2026-10-28）

请先完整阅读：

1. `F:\嵌赛\rml24_scan_gap_ui_control_fix1_20261028\HANDOFF_SCAN_GAP_UI_FIX1.md`
2. `F:\嵌赛\rml24_scan_gap_ui_control_fix1_20261028\docs\BOARDTEST.md`
3. `F:\rml24_repeat_mean_validation_20261028\HANDOFF_RF_VALIDATION.md`

## 当前真实状态

- 已冻结八段重复载荷相干平均候选：定频 235/240，missing=0；扫频 230/240，missing=4。
- 上轮判决仍是 `DO_NOT_PROMOTE`，正式服务和自启动入口未替换。
- 四个扫频缺项与两段约 20.88 秒的全频段重扫停顿严格对齐。
- 新的电脑侧候选已经准备完成，但尚未进行板端 C++ 构建、实屏和 RF 回归。
- 原模型、two-DC、公共帧、门限、FPGA 位流和正式 systemd 均未修改。

## 本轮已经完成的修改

1. 扫频丢锁策略改为双条件：连续漏检至少 5 次，且持续至少 1.0 秒，才允许全频段重扫；命中一次立即清零。
2. 第五页 UI 只保留 `FIXED` 和 `BAND SCAN`。
3. 删除用户层 AutoLock。自动锁定/重捕获仍是 BAND SCAN 内部行为，显示为 `SCANNING / LOCKED / REACQUIRING`。
4. UI 可输入定频频率、扫频起点、终点和步进，单位 MHz。
5. 参数通过既有控制 socket 发送；生产者校验、应用、SDR readback 后 UI 才显示 APPLIED。
6. 后端明确拒绝 `SET_MODE AUTO_LOCK`，非法频率、范围、步进和过多扫频点均 fail-closed。

完整交付包：

`F:\嵌赛\rml24_scan_gap_ui_control_fix1_20261028.zip`

SHA256：

`dd6ced609b93c9eceadfb706cac47f047fe2641664930818d975a7bc9cd464a0`

离线验证：Python 编译 PASS、滞回测试 PASS、控制合同 PASS、静态审计 9/9、ZIP 内 22 文件校验 PASS。没有 Windows C++ 工具链，因此不能声称 UI 已编译；必须在板端 aarch64 构建。

## 下一步严格顺序

1. 上传交付包，解压到独立目录。
2. 使用 `scripts/install_overlay.sh` 从冻结候选复制出新的测试树，禁止覆盖原树。
3. 板端 `build_ui_live_rml24_final.sh` 构建；失败即停止。
4. 无 RF 实屏测试：两个模式、四个频率字段、数字键盘、合法/非法参数、ACK/readback。
5. 定频 240 项回归：固定分母、missing=0，要求不低于 235/240。
6. 扫频 240 项回归：固定分母、missing=0，要求不低于旧正式基线 232/240。
7. 两轮通过后才冻结主链、自启动和现场演示版本。
8. 最后再独立接入 FPGA 扩展，先软件/FPGA A/B，再考虑正式启用；必须保留软件回退。

## FPGA 扩展边界

- FPGA 扩展放在主链冻结之后。
- 优先 Energy、Peak、RMS、Power、LagRe/LagIm 与 FPGA 辅助智能扫频。
- 智能扫频应提供能量检测、候选频点筛选、静默频点跳过，并量化资源、延迟、扫描时间和 CPU 卸载。
- 不要在最后阶段迁移整个识别模型或改模型输入合同。
- 不要加载新位流后直接覆盖稳定版本。

## 电脑发射控制台建议

现场演示应准备一页式电脑 TX 控制台：24 类选择、中心频率、TX 衰减、消息种子、单次/连续发射、停止、Pluto 状态/readback、波形 SHA 和日志。

硬隔离规则：电脑只能控制 TX Pluto。接收端只能经 RF 获得信号，不得通过网线接收类别、样本 ID、真实频点或发射开始时刻。推荐演示时先隐藏 TX 真值，板端识别后再揭示类别。

## 暂时不要做

- 不增加第六页 UI 或新调制类别。
- 不重新训练模型。
- 不删除失败项或按“已收到信号”改分母。
- 不把准备完成写成 RF PASS。
- 不提前替换 systemd 或开机默认。
- 不同时运行原接收器和候选，避免争用 Pluto/NPU/UI 帧缓冲。

## 给下一位的直接指令

请完整阅读上述三份交接文件，从独立板端构建开始。先完成扫频缺项修复和新 UI 的实屏/定频/扫频回归；未经新 RF 证据，不得宣称修复通过。主链通过并冻结后，再测试 FPGA 扩展。任何测试都保留固定 240 分母、完整失败项和原始日志。
