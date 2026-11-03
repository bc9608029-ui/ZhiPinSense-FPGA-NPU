# 并行线 C — 判读与训练指标合同（METRIC_CONTRACT）

任务：`M29-RML24-REALRF-FINETUNE-PILOT1` / 线 C `pilot1_judge_train`（纯离线）

## 1. 主判读指标（judge_realrf_pilot.py 固定口径）

**分母固定 960**：缺帧、门拒（gate_pass=0）、非有限、无同步（no_sync=1）、削顶
（rx_clipped=1）、hard_invalid=1 一律计入分母，绝不剔除。四个会话 S1/S2/S3/S4 各 240。

| 指标 | 定义 | 分母 |
|---|---|---|
| `coverage` | capture_ok=1 且 hard_invalid=0 且有有限 board_pred1 的帧数 | 960 |
| `gated_accuracy` | gate_pass=1 帧中 board_pred1==label 占比 | gated 数 |
| `forced_diagnostic_accuracy` | 门拒但强制导出 tensor 的帧中正确占比（诊断旁路） | forced 数 |
| `end_to_end_accuracy` | 全体 board_pred1==label（无 pred 一律算错） | **960** |
| `macro_f1` | 24 类 F1 均值（无 pred 计入 fn） | 960 |
| `per_class_accuracy` | 每类正确数 / 40（每类全 4 会话共 40） | 40/类 |
| `digital_agreement` | board_pred1 == 数字基线 digital_pred 的占比 | 有 pred 帧 |

`end_to_end_accuracy` 与 `macro_f1` 是微调判级的一等指标；`gated/forced` 是诊断旁路。

## 2. 判级规则（主线程汇总，六选一）

- `FINETUNE_PROMISING`：E1/E2/E3 中某候选在 S4 上 e2e_acc 与 macro-F1 均显著优于 E0
  冻结基线，且增益跨 ≥3 种子稳定，且无四轮泄漏。
- `FINETUNE_MARGINAL`：S4 有增益但幅度小或种子间不稳。
- `FINETUNE_NO_GENERALIZATION`：S3 有增益但 S4 无（过拟合 S3）。
- `DATA_PIPELINE_INVALID`：采集链/恢复链 32 字段或 960 身份或四轮独立性被证伪。
- `BLOCKED_NO_TRAINABLE_CHECKPOINT`：无原模型可训练 checkpoint（当前已排除，
  线 A 结论 = `TRAINABLE_CHECKPOINT_FOUND`）。
- `READY_FOR_BOARD_CAPTURE`：离线资产全部就绪，待板端采集（当前最终离线态）。

**禁止**写 `RF_PASS` / `PROJECT_COMPLETE` / `FINETUNE_SUCCESS`。

## 3. 训练框架指标（train/evaluate_finetune_pilot.py）

- **E0-E3**：E0 冻结（不训，作基线）、E1 只训分类头、E2 解冻最后一个特征块
  `features[-1]` + 分类头、E3 全模型小 LR。冻结掩码自测已核验：
  E0=0 / E1=15512 / E2=89624 / E3=280584（总 280584 参数）。
- **优化**：交叉熵 + AdamW + 权重衰减 1e-4 + 标签平滑 0.1；backbone LR 1e-5~3e-5、
  head LR 3e-4；每 batch 真实 RF : 原始 RadioML 数字 = 1:1；早停（S3 上无增益
  patience 内停止）；**超参数只据 S3 调，S4 密封到模型/超参确定后**；≥3 随机种子。
- **评估**：evaluate_finetune_pilot.py 在 S4 240 帧（固定分母）上出 per-class / macro-F1 /
  e2e_acc；与 E0 冻结基线 + 数字基线 S4 精度对比。

## 4. 红线

- 采集前不训练（真实训练循环 gated 到板端采集完成；本阶段只 build + self-test）。
- S4 密封：超参数、模型结构、早停决策一律不得使用 S4。
- 数字基线错误不得删除；四轮零重叠；960/240 固定分母不剔。
- 微调从原 PyTorch checkpoint 初始化，不从 NPU JSON/RAW 反推权重。
- Host 候选通过前不转 NPU、不上板、不替换生产恢复链。
