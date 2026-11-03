# M29 RML24 FIX10CLASS24 — 24 类真实接收前瞻验证方案与自动判读工具准备 (prep1)

**任务**: fix10class24-prospective-validation-prep1 (task 39e5)
**工作目录**: `F:\嵌赛\fix10class24_prospective_validation_prep1_work\`
**状态**: `M29-RML24-FIX10CLASS24-PROSPECTIVE-VALIDATION-PREP-READY`（最高允许状态）
**日期**: 2026-10-18

---

## 1. 目标

在**不碰板、不启动 SDR、不执行真实采集**的前提下，为未来真实板端 RF 采集准备好一套「前瞻验证框架」：
候选门限策略冻结 + 空捕获计划 + 自动判读工具 + 合成自测。采集到来后，把真实结果表交给判读工具即可回答五个问题：

1. 生产 0.100 门限在真实 RF 上的**实际接纳/拒绝率**；
2. 候选门限能否**救回**那些「本来能正确分类却被 0.100 拒掉」的信号；
3. 候选门限是否**误接纳**噪声 / 错同步 / 削顶 / 失真信号；
4. 24 类**覆盖度**；
5. 在**独立样本**上的稳定性。

## 2. 红线（不得违反）

- 不得修改生产门限 `0.100`。
- 不得修改同步、CFO、定时、增益恢复算法。
- 不得修改 24 类 BF16 模型、标签、baseline 或预处理。
- 不得用现有 30 个失败样本同时调参和验证。
- 不得将纯净 IQ 结果冒充真实 RF 结果。
- 不得碰板、启动 SDR 或执行真实采集。
- 不得写 `RF_PASS`、`SMOKE_PASS`、`FINAL_*`。

## 3. 交付物

| 路径 | 说明 |
|---|---|
| `contracts/prospective_validation_v1/clean24_identity.tsv` | 24 类纯净 IQ 源身份（冻结参照） |
| `contracts/prospective_validation_v1/rf_positive_capture_plan.tsv` | 120 行正向捕获计划（24×5） |
| `contracts/prospective_validation_v1/rf_negative_capture_plan.tsv` | 39 行负向捕获计划（13×3） |
| `contracts/prospective_validation_v1/candidate_gate_policy.tsv` | 10 条候选门限策略（冻结） |
| `contracts/prospective_validation_v1/README.md` | 合同口径说明 |
| `scripts/check_fix10class24_prospective_validation.py` | 自动判读工具 |
| `scripts/gen_prospective_self_test.py` | Phase F 合成自测夹具生成器 |
| `host_tests/test_fix10class24_prospective_validation.py` | 13 项 pytest（Phase F） |
| `results/prospective_validation_prep1/self_test/` | 合成自测输出（report.json/tsv/txt + 夹具） |
| `docs/M29_RML24_FIX10CLASS24_PROSPECTIVE_VALIDATION_PLAN.md` | 本文档 |

## 4. Phase 划分

- **Phase A** — 冻结资产盘点：确认 BF16 模型 SHA、24 类纯净 IQ 身份、FROZEN_BASELINE 24/24 正确。→ 完成。
- **Phase B** — 候选门限策略冻结：`candidate_gate_policy.tsv`（生产基线 + 6 条残差放宽 + 3 条联合）。→ 完成。
- **Phase C** — 空捕获计划：正/负两套 TSV，指标列留空待采集回填。→ 完成。
- **Phase D** — 自动判读工具：硬门禁（覆盖/主键/正负不混/有限性/基线身份/WC·SC 独立）+ 每候选统计（接纳率/误拒率/负误接纳率/一致率 + Wilson 95% CI）。→ 完成。
- **Phase E** — 合同文档与口径。→ 完成。
- **Phase F** — 合成自测：13 项 pytest 全过 + 自测工件落盘。→ 完成（13/13 PASS）。

## 5. 硬门禁（判读工具 fail-closed）

| 门禁 | 失败条件 |
|---|---|
| class_coverage | 缺类 / 多类 / 某类重复数 < `--min-repeat`（默认 3） |
| primary_key_unique | capture_id 重复，或 (source_index, repeat_id) 重复 |
| positive_negative_not_mixed | 正负 capture_id 重叠 / 负样本缺类型 / 负类型非法 / 正样本带负类型 |
| all_values_finite | 任一恢复指标 NaN/Inf，或 rx_clipped 非 0/1 |
| baseline_identity_match | baseline_pred ≠ FROZEN_BASELINE[si]，或 raw24_class ≠ 冻结身份 |
| wc_sc_independent | WC(17)/SC(18) 被合并为 AM-SSB |

退出码 0 = 全过硬门禁；1 = 任一失败。

## 6. 每候选统计（信息性，永不建议阈值）

`positive_admit_rate` / `false_reject_rate` / `negative_false_admit_rate` / `admitted_agreement_rate`，
均带 Wilson 95% CI 与样本分母；`no_new_production_threshold=1` 恒定。

## 7. 完成条件

Phase A–F 全部完成，Phase F 合成自测 13/13 PASS，判读工具对合成夹具全过硬门禁。
**完成后暂停，等待未来真实采集。** 真实采集到来后：把真实正/负结果表（按捕获计划回填指标）交给
`check_fix10class24_prospective_validation.py`，即可得到五个问题的答案；任何候选门限的采纳/否决都留待
真实结果裁决，本任务不做预判。
