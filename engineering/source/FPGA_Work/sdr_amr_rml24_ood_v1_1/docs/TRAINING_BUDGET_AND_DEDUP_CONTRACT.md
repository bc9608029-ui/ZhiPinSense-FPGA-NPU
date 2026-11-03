# 24 类训练预算与候选去重契约（V1.1）

本文档冻结 24 类「pilot → 去重/选择 → formal」链路的**训练预算**与**候选身份**
规则，保证离线与 AutoDL 两处对「谁是一个候选」「一共跑几次」的判断完全一致。
实现：`v2/candidate_signature.py`、`training/rml24_select.py`、`training/rml24_formal.py`、
`training/oe_decision.py`、`scripts/run_train_rml24.sh`、`scripts/run_oe_energy.sh`。

---

## 1. 候选身份（canonical candidate signature）

`canonical_candidate_signature(config) -> str`：对一组**精选字段**做 key-sorted JSON
序列化后取 SHA-256（64 hex）。两个 pilot trial 若采样出**完全相同**的训练配置，签名必然相同；
键序、`seed`、trial 号、输出/日志/checkpoint 路径、时间戳、`run_id` **绝不**进入身份。

**必须覆盖的字段**（任一不同即不同候选）：

- 模型结构 `model`、`model_name`、`apply_channel_augmentation`
- 输入形状 `[1,2,1024]`、输出维 `24`、输出 `raw_logits_no_softmax`、`label_order`（冻结 24 类序）
- 归一化 `rms1.0_no_rescale`
- 损失 `loss`、`focal_gamma`、`label_smoothing`、`class_sampling`（类别加权/采样）
- 优化器 `optimizer`、`sgd_momentum`、`learning_rate`、`weight_decay`
- 调度器 `scheduler{type,factor,patience,min_lr}`
- 增广 `augmentation_groups`、课程 `snr_curriculum`
- `batch_size`、`amp`/`amp_dtype`、`gradient_clip_norm`、`reconstruction_weight`、`snr_weighting`

**明确排除**：trial 号、输出目录、日志/checkpoint 路径、时间戳、`run_id`、`seed`、
以及 `epochs` / `minimum_epochs_before_stopping` / `early_stopping_patience` / `min_delta`
（早停不是搜索轴，且 `run_rml24_trial` 会把 `minimum_epochs_before_stopping` 截断到 pilot
epoch 预算，纳入会导致 pilot↔formal 同一候选签名漂移）。

两个派生身份：

- `config_sha256(config)`：只含训练旋钮，**不含**数据来源（每次 checkpoint 都记录，用于检测配置漂移）。
- `canonical_candidate_signature(config)`：`config_sha256` + `dataset_sha256` + `split_sha256`
  + `label_contract_sha256`（去重/正式训练身份）。

数据来源 SHA 从 `contracts/rml2018_data_contract.json`（`sha256`=HDF5、`index_sha256`=切分索引）
注入保留键 `_dataset_sha256` / `_split_sha256` / `_label_contract_sha256`；**缺失即 fail-closed**
（未绑定到数据切分的签名不允许去重）。

---

## 2. 预算（fail-closed）

| 阶段 | 运行数 | 说明 |
| --- | --- | --- |
| pilot | ≤ 12 trial（`n_pilot_trials`） | Optuna TPE，小 epoch 预算（`pilot_epochs=20`） |
| 去重/选择 | 0 | 只按签名分组 + 排序，不训练 |
| formal | **3**（默认） | **1 个候选 × 3 个种子** |
| OOD 基线 | **0** | MSP/Entropy/MaxLogit/Energy 是 frozen checkpoint 上的后验打分，**绝不重训**（`model_training_runs=0`） |
| OE 验证 | 1 | seed 2026 先跑，`OE_DECISION` 门控 |
| OE 追加 | +2 | 仅 `OE_DECISION result=PROMOTE` 时跑 2027/2028 |

- **默认总预算 4 次**（formal 3 + OOD 基线 0 + OE 验证 1）；OE 通过后 **最多 6 次**。
- **冻结 formal 种子**：`[2026, 2027, 2028]`；**冻结 pilot 种子**：`2026`。
- 打印 `FORMAL_PLAN unique_candidates=1 seeds=3 total_runs=3`；不是恰好 3（或经授权的 6）即 fail-closed。
- 超过 6 次需要**显式理由 + 用户授权**，否则直接拒绝。

---

## 3. 选择（去重 → 排序 → 提升）

`training/rml24_select.py` 按以下顺序（全部 validation-only）：

1. `prune`：剔除 NaN/Inf、无收敛、`rated_0_20_accuracy < 0.55` 的 trial。
2. **去重**：按 `canonical_candidate_signature` 分组，组内保留 `rated_0_20_accuracy` 最高者，
   其余记入 `pilot_duplicate_report.json`（`signature / kept_trial / duplicate_trials / reason`）。
3. `rank`：对唯一候选按 `rated_0_20_accuracy` 排序。
4. 提升 top `top_candidates`（默认 **1**）。

**第二个候选**只在 `--allow-second-candidate` 且满足**全部**条件时才提升：

- 签名与第一个不同；
- `|score_delta| ≤ 0.01`；
- 至少一个关键维度更好（`worst_class_recall` / `low_snr_accuracy` / `min_qam_recall`，容差 `1e-4`）；
- 显式理由（`second_candidate_reason`）。默认预算仍 3 次，**不**自动扩到 6 次。

产物：`pilot_unique_candidates.json`（去重+排序+提升后的候选 + `candidate_signature`）、
`pilot_duplicate_report.json`。

---

## 4. formal 去重 / 续跑 / 摘要 / 最终清单

`training/rml24_formal.py`：

- 每个 `(candidate, seed)` 训练**恰一次**；先查已有 checkpoint 的 provenance：
  - 与期望的 `candidate_signature / config_sha256 / dataset_sha256 / split_sha256` **完全一致**
    → `FORMAL_RUN status=REUSED_VERIFIED`（复用已验证 checkpoint，不重训、不覆盖）；
  - 任一不符 → `FORMAL_RUN result=FAIL reason=artifact_mismatch`（fail-closed，不静默覆盖）；
  - 相同 `(signature, seed)` 重复对 → 直接拒绝。
- `formal_summary.json`：每个候选的 3 种子 `best_epoch` / `checkpoint_sha256` / `macro_f1` /
  `rated_0_20_accuracy` / `snr_0_accuracy` / `min_per_class_accuracy` + `mean/std/worst_seed` +
  `candidate_signature`。
- `final_checkpoint_manifest.json`：**唯一**最终 checkpoint 来源，字段
  `candidate_signature / selected_seed / checkpoint_path / checkpoint_sha256 / model_name /
  class_count=24 / label_contract_sha256 / config_sha256 / dataset_sha256 /
  selection_metric=rated_0_20_accuracy / selection_value`。下游（OOD 基线 / 导出 / 最终评估）
  **只读此清单**，禁用 `find|ls|sort|tail` 猜测 checkpoint。

---

## 5. 禁止项

- 禁止用 test 切分调超参 / 选 checkpoint；formal 选择只认 validation `rated_0_20_accuracy`。
- 禁止为过测降低 `selection_metric_below`（0.55）或 OOD/OE 门限。
- 禁止 `ls|sort|tail -n1` / `find … | head -n1` 选择 pilot 目录或 checkpoint。
- 禁止静默复用旧 trial / 覆盖旧 checkpoint / 把 OOD 测试样本加入训练。
