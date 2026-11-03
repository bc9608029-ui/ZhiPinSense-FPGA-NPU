# FIX1 — 修正前后对照（before → after）

独立复核 `REVIEW_2026-10-19.md` 判前版 `NEEDS_CORRECTION`，列 7 项问题。本表逐项对照：原主张（before）→ 更正（after）→ 处理状态。

## P1 — 结论与统计证据不相称（4 项 → 撤回 6 条结论）

| 复核问题 | 原主张 (before) | 更正 (after) | 状态 |
|---|---|---|---|
| **P1-1** 未做相关/区分检验却写「50 项无一相关」 | 「50 个度量中无一与 64QAM/128QAM→256QAM 崩塌相关」「这一无相关特征本身是已直接测得」；phase5 用跨 4 SNR 层最大 \|z\| 排名；phase6 用 top3 集合交集写「排名完全相同、无类特定差异」 | 不做相关/区分检验；`correct_wrong_comparison.tsv` 改为 **best-matching-SNR 单层** \|z\| 排名（不再跨层取 max）；`evidence_table.tsv`「与错误相关」=**(无)**，明确 RETRACTED；phase6 删除「universal_rank_equivalence / 0 of 50 correlates / decision_boundary_sensitivity」三条硬编码结论 | 撤回 R1/R2/R3 |
| **P1-2** 用 64QAM 局部结果概括所有类，存在直接反例 | 「amp_roc_mean/phase_inc_std 略抬升（85–92 百分位，分布内）」「全部差异小、方向一致、均在参考分布内」 | 逐类报告：128QAM `bw99_cont` pct=**0.04**、256QAM `amp_roc_mean` pct=**0.98**、256QAM `phase_inc_std` pct=0.57 等，证明差异**非均匀、非全部在分布内** | 撤回 R6 |
| **P1-3** 「全部 24 类通用」覆盖/选择/加权问题 | 「跨全部 24 类通用」「58/58 张量、24 类一致」；`_a_pool_med` 合并 9 类不等量 | 明确 **22 类**（QPSK/8PSK 无张量）；repeat3 三轮回放为**同源重复捕获、非独立源**；不做跨类合并的「通用偏移」证明 | 撤回 R4 |
| **P1-4** 谱峰/带外中位数当 SNR | 「C≈A 在 ~SNR25 的干净高信噪外观」 | `peak_to_floor_db` 仅描述为「该统计量介于 A 的 SNR20/30 参考值之间」，**不赋 C 确定 SNR** | 撤回 R5 |

## P2 — 指标实现与测试缺陷（3 项）

| 复核问题 | 原实现 (before) | 更正 (after) | 状态 |
|---|---|---|---|
| **P2-5** 复自相关先取实部 | `abs(real(vdot(x[k:],x[:-k]))/energy)`；1024 点 0.25 单音 lag1 实测 ≈4.57e-19 | `abs(vdot(x[k:],x[:-k]))/energy`（分子保持复数至 `abs`）；同单音 lag1=**0.9990234375**；58 C 张量 lag1 两定义中位差 ~2.99e-6、最大 0.019042 | 已修+重算 |
| **P2-6** flatness floor 未应用却称 used | `flatness_floor=1e-12*total` 只输出不参与 log/均值；文档称「actually used」；且参与 50 度量排名、在 AM-SSB 对照进 top3 | `flatness` 保持无 floor（与 threedomain `audit_common.sample_stats` 一致）；`flatness_floor` 移出度量集（49 度量）；文档澄清 `SPECTRAL_FLOOR_REL` 为保留常数、未用于 flatness | 已修 |
| **P2-7** 两个异常测试吞掉失败断言 | `try: loader(...); raise AssertionError("did not raise") / except AssertionError: pass`（「did not raise」也被同 except 捕获 → 恒通过） | 改 `try/except AssertionError/else: raise`；新增 `test_wrong_size_raises`（短/长张量严格拒绝） | 已修 |

## 新增测试（4 个）

| 测试 | 覆盖 | 结果 |
|---|---|---|
| `test_complex_acorr_tone` | 1024 点 0.25 单音 lag1=1023/1024=0.9990234375（P2-5 反例） | PASS |
| `test_acorr_phase_rotation_invariant` | \|acorr\| 全局相位旋转不变（旧 real-first 会破坏） | PASS |
| `test_flatness_floor_not_metric` | `flatness_floor` 不在 metric_names/full_metrics（P2-6） | PASS |
| `test_wrong_size_raises` | 短/长张量被 loader 拒绝（P2-7） | PASS |

## 度量/结果口径变化

| 项 | before | after |
|---|---|---|
| 度量数 | 50 | **49**（移除 flatness_floor） |
| selftest | 8/8 | **12/12** |
| phase5 排名统计 | 跨 4 SNR 层最大 \|z\|（`median_worst_abs_z`） | **best-matching-SNR 单层** \|z\|（`median_abs_z_at_best_snr`），对/错 C 值分列 |
| phase5 列 | 含 `shared_with_control` | 移除 `shared_with_control`；新增 `n_unique_sources`/`correct_c_values`/`wrong_c_values` |
| phase6 证据「与错误相关」 | 「0 of 50 correlates…null is a measured result」 | **（无）** + RETRACTED 说明 |
| phase6 证据「可能的解释」 | decision_boundary_sensitivity | **（无断言）** |
| summary verdict | `MEASUREMENT_COMPLETE` | **`AUDIT_COMPLETE_DESCRIPTIVE_ONLY`** + `correlation_tested=false` + `causal_attribution=none` + `retracted_conclusions[6]` |
| A 参考索引 | 9600 帧 seed=20261019 | **逐字节一致**（未重采、未改索引） |
