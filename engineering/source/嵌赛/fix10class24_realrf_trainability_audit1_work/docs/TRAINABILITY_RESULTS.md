# M29-RML24-REALRF-TRAINABILITY-AUDIT1 — 可训练性审计结果

状态：`…-TRAINABILITY-RESULTS-COMPLETE`（纯离线，不训练）

## Phase A — 数据盘点与充足性（`inventory_realrf.py`）

- 源波形 24 个，单一 `source_id`、v2、1 波形/类。
- 真实 RF 会话 = 2 个（`rf_fix2_target` + `rf_independent_v2`），另有 1 个 full24 RF 会话
  （不同源波形集）。
- 跨会话源波形重叠 24/24 → `TRAIN_VAL_TEST_SPLIT_IMPOSSIBLE`。
- 判定：**`CURRENT_DATA_INSUFFICIENT_FOR_FINAL_FINETUNING`**（§4.2）。

## Phase B — 三域可分离性（`analyze_three_domains.py`）

- A 87.29% / B 95.83% / C e2e 2.08%（门 23/48）/ C0 强制 18/24。
- Q1 = **PARTIAL**（信息部分保留）；Q2 = **RECEIVE_CHAIN_RESIDUAL_BOTTLENECK**。
- 详见 `DOMAIN_SHIFT_AUDIT.md`。

## Phase C — 训练实验 E0–E3 状态

| 实验 | 内容 | 状态 |
|---|---|---|
| E0 | 冻结模型无训练基线 | **已完成**（A/B/C/C0 精度即基线，见 Phase B） |
| E1 | 冻结特征线性头微调 | **BLOCKED** — 红线「不训练」+ 数据不足（无法会话级切分） |
| E2 | 全模型微调 | **BLOCKED** — 同上 |
| E3 | 从零重训 | **BLOCKED** — 同上，且需 RadioML 规模数据 |

E1–E3 被两件事阻断，二者任一即阻断：
1. **站立红线「不训练」**——需要用户显式授权（本任务书与红线冲突，已保留冲突不自行解除）。
2. **数据不足**——2 会话 × 24 重复源波形，无法形成会话级 train/val/test（§4.2/§6.2）。

且即使授权训练，在「恢复残差系统性越过 0.100 门」的接收链上微调，只会把接收链失真
固化进模型（`do_not_finetune_until` 停止条件）。

## 产出

- `results/data_inventory.tsv` + `inventory_verdict.json`
- `results/three_domain_summary.tsv` + `three_domain_verdict.json`
- `results/capture_plan.json` + `docs/CAPTURE_PLAN.md`
- `docs/DECISION.md`（终态判决）
