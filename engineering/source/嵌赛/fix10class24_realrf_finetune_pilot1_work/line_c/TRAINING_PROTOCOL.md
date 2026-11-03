# 并行线 C — 微调训练协议（TRAINING_PROTOCOL）

任务：`M29-RML24-REALRF-FINETUNE-PILOT1` / 线 C `pilot1_judge_train`（纯离线）

本协议定义「板端采集完成后」才允许执行的正式微调流程；当前阶段（采集前）只交付
框架 + 自测，**不跑真实训练**（红线：采集前不训练）。

## 1. 数据拆分（四轮独立性）

| 会话 | 帧数 | 角色 |
|---|---|---|
| S1 | 240 | Train |
| S2 | 240 | Train |
| S3 | 240 | Validation（超参选择/早停） |
| S4 | 240 | **Sealed Test**（模型/超参确定前不接触） |

每类每会话 10 帧；四轮 dataset_index/source_id/source_iq_sha256/TX payload SHA 零重叠；
与既有 480 帧冻结测试集零重叠。

## 2. 训练数据构成

- **真实 RF**：S1+S2 板端恢复 IQ 张量（480 帧，[2,1024] f32 LE，走生产 wide-linear
  恢复链保存于门禁之前的 `model_input`）。逐帧校验 `model_input_sha256`，门拒/缺帧
  不剔除（按红线，诊断旁路才导出张量）。**label/class_index 不在板端采集 TSV 里**
  （评审 39e5 Blocker 2），由 `gt_join.py` 按 source_id 从主机真值清单
  `line_a/results/source_manifest_960.tsv` 离线回填。
- **原始 RadioML 数字**：S1+S2 的源 IQ（480 帧，`line_a/inputs/`）。用于 1:1 混合，
  防止灾难性遗忘 + 稳定梯度。可补充原 RadioML train 切分的 SNR≥20 子集以平衡类别，
  但**主判级只用 S4 真实 RF**，不把数字样本正确率计入微调成效。

每 batch：真实 RF 与数字样本 1:1；类别平衡采样；batch 256（或 128，显存不足时）。

## 3. E0-E3 冻结策略

- **E0**：全冻结，不训练（复现原模型在 S4 上的分数 = 基线）。
- **E1**：冻结 denoiser + features，只训 `classifier` 头。LR 3e-4。
- **E2**：冻结 denoiser + features[:-1]，解冻 `features[-1]`（最后一个特征块）+ 头。
  backbone LR 1e-5、head LR 3e-4。
- **E3**：全模型小 LR（1e-5~3e-5），可能过拟合 → 需 S3 早停 + 强 weight_decay 1e-4。

`train_finetune_pilot.py::freeze_for_experiment()` 是冻结掩码唯一权威，自测已核验
E0=0 / E1=15512 / E2=89624 / E3=280584。

## 4. 训练超参与搜索

- 优化器：AdamW，weight_decay 1e-4；损失：cross_entropy + label_smoothing 0.1。
- LR 搜索：head ∈ {3e-4, 1e-3}，backbone ∈ {1e-5, 3e-5}，小网格（≤6 组合）。
- 早停：S3 e2e_acc 在 patience（10 epoch）内不提升即停，回滚最佳。
- 种子：≥3（2027/2028/2029），报告均值 ± 标准差，不得挑最好种子。
- **S4 密封**：上述所有决策只用 S3；S4 只在最终评估阶段解封一次。

## 5. 评估与判级

`evaluate_finetune_pilot.py` 在 S4 240 帧上对每个 E0-E3 最佳 checkpoint 出
per-class accuracy / macro-F1 / e2e_acc（固定 240 分母，门拒/缺帧不剔除）。

判级由 `judge_realrf_pilot.py` 汇总（见 METRIC_CONTRACT §2）：
E1/E2/E3 vs E0 冻结基线的 S4 增益方向、幅度、跨种子稳定性决定
PROMISING / MARGINAL / NO_GENERALIZATION；泄漏或身份问题 → DATA_PIPELINE_INVALID。

## 6. 交付物与门禁

- 产物：每实验每种子 `checkpoints/best.pt` + 训练曲线 + 配置 + SHA；评估 JSON。
- 门禁：Host PyTorch 候选在 S4 上显著优于 E0 之前，**不转 NPU、不上板、不替换生产链**。
- 全程不写 RF_PASS / PROJECT_COMPLETE / FINETUNE_SUCCESS。
