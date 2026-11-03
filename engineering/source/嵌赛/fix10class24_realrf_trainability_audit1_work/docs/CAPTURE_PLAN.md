# M29-RML24-REALRF-TRAINABILITY-AUDIT1 — 采集计划（taskbook §10）

状态：`…-CAPTURE-PLAN-READY`（纯离线，不碰板；采集由用户串口执行）。

## 1. 为什么需要新采集

现有真实 RF 数据 = 2 个双 SDR 会话 × **同一组 24 个源波形**（`fix1v2-waveform-corrected-24waveforms`，
`source_index=class_index+1`，1 波形/类）。跨会话源波形重叠 **24/24** → 无法形成
train/val/test 独立切分；且同一会话内共享 LO/SDR/温度状态，会话内切分会把该状态泄漏
到 train/val/test。故当前数据只够「探测性」结论，不够最终微调（taskbook §4.2/§6.2/§9.4）。

## 2. 采集合同

| 项 | 值 |
|---|---|
| 独立真实 RF 会话数 | **≥ 5**（train:val:test = 3:1:1，按**会话**切分） |
| 每类独立源实现数 | **≥ 20**（24 类 × 20 = 480 独立源波形） |
| 每帧点数 | 1024（[2,1024] f32 模型输入） |
| 每帧记录 | source_index / class_index / realization_seed / source_sha256 / raw_rx_sha256 / recovered_tensor_sha256 / training_residual_rel / gated / board_pred / forced_logits_sha256 |
| 门拒样本 | **必须**仍导出 recovered tensor + 冻结模型 logits（诊断旁路），**不得**丢弃 |

## 3. 泄漏控制

- 切分单位 = **会话**（一整会话只进 train/val/test 之一）。
- 一个源实现不得出现在多个切分。
- 24 类全部留在 24 分母；不剔除门拒/错误/非有限样本。
- 恢复/DC/尺度参数不得用标签或逐样本源身份选择。

## 4. 停止条件（衔接 §12）

- **进入最终微调**：≥5 会话 + ≥20 实现/类，且接收链残差分布不再系统性越过 0.100 门。
- **不得在接收链修好前微调**：在残差受限的恢复上微调会强化接收链失真。
- **训练需用户显式授权**（站立红线「不训练」）。

## 5. 禁止

禁止复用现有 24 个 `tx_package` 源波形作为唯一实现（它们已作为 2 会话审计集消耗）。
