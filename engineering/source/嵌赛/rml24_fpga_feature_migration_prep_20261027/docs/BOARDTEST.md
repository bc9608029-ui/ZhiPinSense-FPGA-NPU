# 板端测试顺序（不得跳级）

1. Procise 只导入冻结 RTL，先 elaborate；不接现有正式启动链。
2. 对 `qam_feature_pipeline` 和 `frame_statistics` 做综合、P&R、STA，保存资源、时钟和警告报告。
3. 用冻结 19 帧向量回放，逐点比较 Power/Lag，要求零差异；统计量也要求零差异。
4. 接 PS→PL 缓冲适配器，随机 backpressure、跨帧、复位、超时均须 fail-closed。
5. 用真实 two-DC 恢复后的 IQ 做同帧 A/B：软件和 FPGA 特征全等，模型输入 SHA 全等，预测全等。
6. 先跑 `software`，再跑 `fpga`，最后才允许 `auto`。任一异常必须验证自动回退。
7. 回归定频 240 帧、扫频两个频点各 240 帧，并核对准确率不得出现统计显著退化。

通过第 7 步前，不替换现有 475/480、464/480、472/480 的正式演示版本。
