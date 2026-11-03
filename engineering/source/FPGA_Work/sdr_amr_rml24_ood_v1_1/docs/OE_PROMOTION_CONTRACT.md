# OE+Energy 提升契约（1 + 2 种子策略）

Outlier Exposure + Energy 训练昂贵且可能**退化闭集 ID 精度**，因此不无条件跑满 3 种子，
而是用一个**提升门**在「保留 Energy 基线」与「投入 2 个额外种子」之间做显式决策。
实现：`training/oe_decision.py`、`scripts/run_oe_energy.sh`。

---

## 1. 流程

1. 用冻结第一种子 **2026** 训练 OE 模型（`RML2018_24_ROBUST_CANDIDATE`）——**验证跑**。
2. 与冻结基线模型（`final_checkpoint_manifest.json` 的 `RML2018_24_BENCHMARK`）比较：
   - **ID 精度**：`macro_f1`、`rated_0_20_accuracy`（均 validation，同口径）；
   - **Energy OOD**：`far` 族的 `auroc`、`fpr95`（FPR@95TPR）、`oscr`（`auc_ccr_fpr`）。
3. 按第 2 节条件输出 `OE_DECISION result=REJECT | PROMOTE`。
4. 只有 `PROMOTE` 才训练 2027、2028；否则保留 Energy 基线，**不掩盖 ID 退化**。

---

## 2. 提升条件（全部满足才 PROMOTE）

ID 退化同时满足（≤ 0.01）：

- `macro_f1` 下降 ≤ `0.01`；
- `rated_0_20_accuracy` 下降 ≤ `0.01`。

**且** OOD 至少一项提升：

- Energy `far` AUROC 提升 ≥ `+0.02`；或
- FPR@95TPR 下降 ≥ `0.05`（记为正增益）；或
- OSCR（`auc_ccr_fpr`）提升 ≥ `+0.02`。

任一 ID 退化超限、或三项 OOD 均未达标 → `REJECT`（fail-closed 偏向拒绝）。

---

## 3. 产物与状态行

- `oe_pilot_seed2026_report.json`：`oe_seed / baseline_id / oe_id /
  baseline_ood_energy_far / oe_ood_energy_far / tolerances / decision / id_degradation /
  ood_gain / improved / reasons`。
- 状态行：`OE_DECISION result=PROMOTE`（随后 `OE_DECISION extra_seeds=2027,2028 trained`）
  或 `OE_DECISION result=REJECT`。
- 预算：验证跑 1 次；PROMOTE 追加 2 次 → OE 阶段至多 3 次，与 formal 3 次合计 6 次（封顶）。
  超过 6 次需显式理由 + 用户授权。

---

## 4. 隔离与红线

- OE 辅助族（`oe_family`）与最终 OOD 测试族（`far`）保持 leave-one-family-out 隔离；
  阈值只在 `ood_validation` 锁定，最终评分只认 `ood_final_test`。
- OE 是否提升**不改**闭集选择指标（仍 `rated_0_20_accuracy`）与 24 类标签序/阈值。
- 未实机验证前**绝不写** `FINAL_MODEL_PASS / OOD_PASS / HARDWARE_PASS`。
