# prospective_validation_v1 — 前瞻验证合同 (task 39e5 prep1)

本目录是 **fix10class24-prospective-validation-prep1** 的只读合同资产，为**未来真实板端 RF 采集**准备好
「自动判读 + 候选门限评估」所需的冻结参照与空捕获计划。**本目录不驱动任何采集，不含真实 RF 数据**。

## 文件

| 文件 | 说明 | 是否可改 |
|---|---|---|
| `clean24_identity.tsv` | 24 类纯净 IQ 源身份（source_index→类/调制/文件 SHA/冻结预测），作为「baseline 身份匹配」的冻结参照 | 冻结，禁改 |
| `candidate_gate_policy.tsv` | 10 条候选门限策略（含生产基线 `baseline_0100` 的逐字段复刻） | 冻结，禁改 |
| `rf_positive_capture_plan.tsv` | 120 行 = 24 类 × 5 重复的**未来**正向捕获计划（指标列留空，采集时回填） | 计划模板 |
| `rf_negative_capture_plan.tsv` | 39 行 = 13 类负样本 × 3 重复的**未来**负向捕获计划 | 计划模板 |

## 关键口径

- **WC/SC 独立**：`raw24_class=17`(AM-SSB-WC) 与 `18`(AM-SSB-SC) 在本任务内**不合并**为 deployed23=17。
  判读工具会校验两者都以各自标签出现，任何「合并成 AM-SSB」都会触发 `wc_sc_independent` 硬门禁失败。
- **候选门限语义**：每条候选策略**完整保留生产有效性门**（payload_training_corr≥0.9 且 training_corr≥0.9
  且 |cfo|≤21.739 且未削顶），**仅放宽残差上界**（0.110→0.160）；联合候选额外把 payload_training_corr 收紧到 0.99。
  因此 no_signal/错同步等低相关负样本会被**每一条候选**拒绝，而残差略超 0.100 的错窗口负样本才是
  「误接纳」的有意义测试点。
- **生产门限 0.100 永不修改**：判读工具只输出「候选会怎么表现」，`no_new_production_threshold=1`，
  不产生任何阈值建议。

## 冻结模型与基线

- BF16 模型 SHA：`28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42`
- 24 类纯净 IQ 冻结预测 24/24 正确（`FROZEN_BASELINE` 内嵌于判读工具）。

## 判读工具

`scripts/check_fix10class24_prospective_validation.py` 读取（未来）真实正/负结果表，输出硬门禁 + 每候选统计：

```
python scripts/check_fix10class24_prospective_validation.py \
  --positive-results <real_positive.tsv> \
  --negative-results <real_negative.tsv> \
  --policy contracts/prospective_validation_v1/candidate_gate_policy.tsv \
  --identity contracts/prospective_validation_v1/clean24_identity.tsv \
  --out-dir <out>
```

硬门禁：24 类覆盖 / 主键唯一 / 正负不混 / 全指标有限 / 基线身份匹配 / WC·SC 独立。
退出码 0 = 全过硬门禁；1 = 任一硬门禁失败（fail-closed）。
