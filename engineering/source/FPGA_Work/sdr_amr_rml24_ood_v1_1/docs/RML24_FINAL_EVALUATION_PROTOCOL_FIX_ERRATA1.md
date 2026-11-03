# RML24 Final Evaluation Protocol Fix — Errata 1（任务 39e5）

「Validation-only OOD 方法比较补齐」：让校准阶段为 MSP / Entropy / MaxLogit / Energy 各
报告完整验证指标，并给出可审计的、仅基于 validation 的分数方法推荐。

只改校准阶段。**不运行真正 final test，不改 checkpoint / 标签序 / 预处理 / 模型结构。**
最高状态仍仅 `RML24-FINAL-EVALUATION-PROTOCOL-READY`。

## 1. 现状缺陷

协议拆成 calibration / final 后，`runs/ood_baselines/ood_baselines.json` 的每个方法只有
`thresholds`，没有 AUROC / AUPR-IN / AUPR-OUT / FPR@95TPR / OSCR，因此无法依据 validation
在四种分数方法里选型；`run_threshold_freeze.py` 直接默认 `energy`，没有证据支撑。

## 2. 改动内容

| 文件 | 变更 |
|------|------|
| `ood/method_selection.py` | **新增**：validation-only 方法排序 + 完整性门禁 |
| `evaluation/evaluate_ood.py` | `calibrate_ood_thresholds` 每个方法补全 ranking / CI / OSCR / 工作点，并输出 `recommended_score_method` + `method_selection` |
| `ood/threshold_manifest.py` | `build_threshold_manifest` 新增可选 `method_selection_evidence`（写入冻结 manifest，读回不破坏旧 manifest） |
| `scripts/run_threshold_freeze.py` | `score_method` 默认改为**推荐方法**；确认指标完整；证据写入 manifest；仍不覆盖已有 manifest |
| `tests/test_ood_method_selection.py` | **新增** 10 项离线回归 |
| `tests/test_threshold_freeze_runner.py` | 适配新报告结构（方法节点需完整指标；未知方法由 `KeyError` 改为 `ValueError`） |

## 3. 校准阶段每个方法的输出（`families[method]`）

仅 ID RadioML validation + `ood_validation`（threshold family `far`），绝不触碰 `test` / `ood_final_test`：

- `ranking`：`auroc` / `aupr_in` / `aupr_out` / `fpr95`（FPR@95%TPR，方向 `higher_is_ood`）；
- `auroc_ci` / `fpr95_ci`：bootstrap 95% CI（`estimate/lower/upper/n_boot`，seed=ood_seed 可复现）；
- `oscr`：`auc_ccr_fpr`；
- `working_points`（conservative / balanced / strict）：`threshold` / `id_frr` / `id_accept_rate` /
  `ood_far` / `ood_rejected_fraction`；
- `thresholds`：三工作点冻结阈值（供 `run_threshold_freeze` 提升为 manifest）；
- `calibration_samples`：`{id, ood}`。

## 4. Validation-only 方法排序规则

`ood.method_selection.select_score_method(families, target_operating_point="balanced")`：

- **不是只看 AUROC**。对五个指标做 Borda 计数（每项按方向给 0..3 分，累加）：
  1. AUROC（越高越好）；
  2. FPR@95TPR（越低越好）；
  3. OSCR `auc_ccr_fpr`（越高越好）；
  4. ID 误拒率 `id_frr`（越低越好）；
  5. OOD 拒识率 `ood_rejected_fraction`（越高越好）。
- 方向与得分绑定确定性：方法名排序、稳定排序、同分按方法名字典序打破平局，**纯函数**，与插入顺序无关。
- 任一方法缺指标或指标非有限 → `ValueError` fail-closed（不许在不完整比较上做推荐）。
- **不读 final 结果**：函数只接受 `families`（校准指标），无任何文件/网络 I/O，签名无 final 参数。

输出：`recommended_score_method` + `selection_rule` + `target_operating_point` +
`validation_only: true` + `final_data_used: false` + 完整 `ranking` + `rationale`。

## 5. `run_threshold_freeze.py` 行为变化

1. 从 `families` 重算推荐方法（`select_score_method`）。
2. 确认推荐方法指标完整（fail-closed）。
3. 解析冻结方法：`score_method=None` → 推荐方法；显式指定则必须是四法之一、且指标完整
   （与推荐不一致时允许，但会在证据里标记 `frozen_score_method_matches_recommended=false`）。
4. 把方法选择证据摘要写入冻结 manifest（`method_selection_evidence`，含 ranking / rationale /
   `final_data_used=false`）。
5. `write_threshold_manifest` 仍拒绝覆盖（`overwrite=True` 为显式逃生口）。

CLI：`--score-method` 默认 `None`（= 推荐方法）；`autodl_rml24/run_all.sh` 第 13 步不再硬编码
energy，改用推荐方法。

## 6. 新增回归测试（`tests/test_ood_method_selection.py`，10 项，全离线）

1. 校准阶段四方法指标齐全且有限（ranking / CI / OSCR / 工作点）；
2. 校准阶段从不构造 `test` / `ood_final_test`（仅 `ood_validation`）；
3. 指标方向正确（`higher_is_ood`：ID 低分 / OOD 高分 → AUROC≈1、FPR95≈0；角色互换 → AUROC≈0）；
4. 方法排序确定性（与字典插入顺序无关）；
5. 明显最优方法被选中（构造 energy 分离度最大 → 推荐 energy）；
6. 缺指标禁止排序（`require_complete_method_metrics` / `select_score_method` 抛 ValueError）；
7. freeze 默认采用推荐方法并写证据（`score_method`==推荐，证据 `final_data_used=false`）；
8. 显式指定非推荐方法也写证据（`frozen_score_method_matches_recommended=false`）；
9. 推荐方法缺指标禁止 freeze（不落盘）；
10. final 数据不影响推荐（签名无 final 参数；磁盘上存在 final 文件也不改变结果）。

## 7. AutoDL 覆盖步骤（用户本人执行）

本补丁是**在 Errata 之前已覆盖的协议补丁之上**的增量 overlay；两份补丁都校验内容 SHA 后覆盖。

```bash
# 0) 在 V1.1 工程根，先校验补丁自身
sha256sum rml24_ood_v1_1_final_evaluation_protocol_fix_errata1_patch.tar.gz

# 1) 解包到临时目录（不直接覆盖工程）
mkdir -p /tmp/fe_errata1 && tar -xzf rml24_ood_v1_1_final_evaluation_protocol_fix_errata1_patch.tar.gz -C /tmp/fe_errata1

# 2) 校验内容文件
(cd /tmp/fe_errata1 && sha256sum -c ERRATA1_PATCH_SHA256SUMS.txt)

# 3) overlay 覆盖工程根（不碰工程根 SHA256SUMS.txt）
cp -r /tmp/fe_errata1/* .

# 4) 复测离线套件（确认 224 passed 4 skipped）
scripts/run_tests.sh
```

覆盖后 `run_all.sh` 第 13 步（threshold freeze）自动改为采用 validation 推荐方法，并把
方法选择证据写入 `runs/ood_baselines/ood_threshold_manifest.json`。

## 8. 状态红线

- 最高状态：**`RML24-FINAL-EVALUATION-PROTOCOL-READY`**。
- 严禁：`FINAL_MODEL_PASS / FINAL_24CLASS_PASS / OOD_PASS / HARDWARE_PASS / FULL_CHAIN_PASS / PROJECT_COMPLETE`。
- 本轮未运行真正 final test、未读 `test` / `ood_final_test`、未改动 checkpoint / 标签序 / 预处理 / 模型结构。
