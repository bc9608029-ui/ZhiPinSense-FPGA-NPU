# RML24 Final Evaluation Protocol Fix（任务 39e5）

只修最终评估协议，**不重新训练、不改 checkpoint、不改标签顺序、不改预处理、不改模型结构**。
本轮仅生成版本化补丁 + AutoDL 覆盖步骤；**未运行真正的 final test，未读取 `test` 或 `ood_final_test`**。
最高状态仅：`RML24-FINAL-EVALUATION-PROTOCOL-READY`。

## 1. 缺陷根因与修复对照

| # | 缺陷 | 根因 | 修复 |
|---|------|------|------|
| 1 | `run_ood_baselines` 用 `id_split="test"` 误读 ID test | `evaluate_ood_rml24(..., id_split="test")` 默认值 | 默认改 `id_split="validation"`（`evaluation/evaluate_ood.py`） |
| 2 | `evaluate_ood.py` 在 baseline 阶段直接生成 `ood_final_test` | `semantic_ood_report` 同时锁阈值 + 评分 final | 拆成 `calibrate_ood_thresholds`（仅 `ood_validation`）与 `score_ood_final`（仅 `ood_final_test`） |
| 3 | Energy 温度用 ID test 标签校准 | `evaluate_ood_rml24` 先读 test 再 `calibrate_temperature` | 校准阶段只用 ID validation logits/labels |
| 4 | `run_final_evaluation` 不读冻结 `ood_threshold_manifest.json` | 直接 `evaluate_ood_rml24(id_split="test")` | 新增 `evaluate_ood_final_rml24`，先 `read_threshold_manifest` |
| 5 | final 重新选阈值 | `semantic_ood_report` 内 `select_thresholds` | `score_ood_final` 只用冻结阈值，不调用 `select_thresholds` |
| 6 | ID test 在同一 final 流程内重复推理 | `evaluate_rml24(split="test")` 一次 + `evaluate_ood_rml24(id_split="test")` 又一次 | `evaluate_rml24(split="test")` 只跑一次，`id_result` 复用到 `evaluate_ood_final_rml24(id_result=…)` |
| 7 | 缺 final-test 一次性访问台账 + 重复访问拒绝 | 无门禁 | 新增 `evaluation/final_test_gate.py` 原子台账 |

## 2. 两阶段协议

### A. 校准阶段（`run_ood_baselines`）

- ID 只用 RadioML **validation**；OOD 只用 **`ood_validation`**。
- 不实例化 `test`，不实例化 `ood_final_test`。
- 比较 MSP / Entropy / MaxLogit / Energy；在 validation 上冻结温度 + 分数方法 + 工作点 + 阈值。
- 写一次 `ood_threshold_manifest.json`（`run_threshold_freeze`，不变）。
- 输出标记：`RML24_OOD_CALIBRATION_OK`。

### B. 最终阶段（`run_final_evaluation`）

- 必须显式传 `<final_checkpoint_manifest.json>` **和** `<ood_threshold_manifest.json>`。
- 校验：checkpoint SHA（`resolve_checkpoint` 复核文件字节 + `verify_final_identity` 交叉校验）、
  dataset SHA、label SHA、分数方法、温度、阈值（`read_threshold_manifest` fail-closed）。
- RadioML `test` 读一次、`ood_final_test` 读一次（`id_result` 复用）。
- 不重新拟合温度/方法/阈值；UNKNOWN 决策只用冻结 manifest 值。

## 3. API 变更

```python
# evaluation/evaluate_ood.py
calibrate_ood_thresholds(model, device, id_logits, id_labels, *, signal_config,
                         ood_seed, count_per_modulation, threshold_family, ...)  # 阶段 A
score_ood_final(model, device, id_logits, id_labels, *, score_method, temperature,
                thresholds, signal_config, ood_seed, count_per_modulation,
                families, ...)                                                  # 阶段 B
evaluate_ood_rml24(config, checkpoint, *, id_split="validation", ...)           # 阶段 A 入口
evaluate_ood_final_rml24(config, checkpoint, threshold_manifest, *, id_result, ...)  # 阶段 B 入口

# evaluation/final_test_gate.py
acquire_gate(path, *, run_id, checkpoint_sha256, threshold_manifest_sha256, dataset_sha256)
complete_gate(path, *, id_test_accessed=True, ood_final_test_accessed=True)

# scripts/run_final_evaluation.py
run_final_evaluation(config, checkpoint_manifest, threshold_manifest, *,
                     twelve_class_config=None, twelve_class_checkpoint=None,
                     output=None, gate_path=None, run_id=None)
verify_final_identity(final_manifest, threshold_manifest)
```

```bash
# scripts/run_final_evaluation.sh（2 参数）
scripts/run_final_evaluation.sh <final_checkpoint_manifest.json> <ood_threshold_manifest.json> \
  [--twelve-class-config C] [--twelve-class-checkpoint CKPT]
```

## 4. 一次性访问台账

`runs/final_evaluation/final_test_access.json` 记录 `run_id / checkpoint_sha256 /
threshold_manifest_sha256 / dataset_sha256 / started_at / completed_at /
id_test_accessed / ood_final_test_accessed / status`。

- `acquire_gate` 用 `os.open(O_CREAT|O_EXCL)` 原子抢占；已存在 `STARTED` 或 `COMPLETE` → `RuntimeError` 拒绝重跑。
- `complete_gate` 用 `os.replace` 原子落盘。
- **不得通过删除旧结果静默重跑**。一次 final 运行中途失败会留下 `STARTED` 台账，需人工显式处理（这是故意的 fail-closed 语义，而非被忽略）。

## 5. 回归测试（11 项，`tests/test_final_evaluation_protocol.py`）

1. calibration 默认 `id_split="validation"` 且从不构造 `test` 切分；
2. calibration 从不构造 `ood_final_test`；
3. final 在阈值 manifest 缺失时 fail-closed（且未抢占门禁）；
4. checkpoint / label / dataset SHA 不匹配 fail-closed（`verify_final_identity`）；
5. final 不得调用 `calibrate_temperature`；
6. final 不得调用 `select_thresholds`；
7. ID test 只推理一次（`evaluate_rml24(split="test")` 计数 == 1 且复用）；
8. `ood_final_test` 每族只评分一次（仅 `ood_final_test` 切分）；
9. 第二次 final 评估被拒绝（STARTED 与 COMPLETE 均拒绝）；
10. final 决策使用冻结阈值（`working_points`/`decisions` 与冻结值一致）；
11. `resolve_checkpoint` 不修改 checkpoint 字节/SHA（只读校验）。

全部离线（无 HDF5 / 无模型 / 无 checkpoint），monkeypatch 模式，与既有测试同风格。
本地 `pytest`：**214 passed, 4 skipped**（4 = optuna 本地未装 `importorskip`）。

## 6. 下游影响（需要知悉）

- **OE 提升门（`training/oe_decision.py`，默认 `RUN_OE=0` 关闭）**：其 `energy_far_metrics` 读
  `families.energy.families.far.ranking.auroc`（原 `ood_final_test` 评分）。校准报告不再含该字段，
  故 OE 门在未另行修订前对 Energy-OOD 增益返回零 → fail-closed 判 `REJECT`（不会误提升、不崩溃）。
  这是本任务「只修最终评估协议」的边界：OE 的 OOD 增益度量需改为在 `ood_validation` 上测量，
  或延后到最终评分后再评估，属于后续独立任务，未在本补丁内改动 `oe_decision.py`。
- `docs/OOD_PROTOCOL_AUDIT_V1_1.md` 提到共享 `semantic_ood_report` 为历史描述；该函数已按两阶段
  拆分，权威口径以本文件为准。

## 7. AutoDL 安全覆盖步骤（用户本人执行）

补丁 `dist/rml24_ood_v1_1_final_evaluation_protocol_fix_patch.tar.gz`（含 `PATCH_SHA256SUMS.txt`，
只列内容文件、不含自身、UTF-8/LF、双空格、不与工程根 `SHA256SUMS.txt` 冲突）。

```bash
# 0) 在 V1.1 工程根，先校验补丁自身
sha256sum rml24_ood_v1_1_final_evaluation_protocol_fix_patch.tar.gz

# 1) 解包到临时目录（不直接覆盖工程）
mkdir -p /tmp/fe_fix && tar -xzf rml24_ood_v1_1_final_evaluation_protocol_fix_patch.tar.gz -C /tmp/fe_fix

# 2) 校验内容文件
(cd /tmp/fe_fix && sha256sum -c PATCH_SHA256SUMS.txt)

# 3) overlay 覆盖工程根（不碰工程根 SHA256SUMS.txt）
cp -r /tmp/fe_fix/* .

# 4) 复测离线套件（确认 214 passed 4 skipped）
scripts/run_tests.sh
```

覆盖后 `autodl_rml24/run_all.sh` 第 14 步自动变为两参数调用：
`scripts/run_final_evaluation.sh "$MANIFEST" "$THRESHOLD_MANIFEST"`。

## 8. 状态红线

- 最高状态：**`RML24-FINAL-EVALUATION-PROTOCOL-READY`**。
- 严禁：`FINAL_MODEL_PASS / FINAL_24CLASS_PASS / OOD_PASS / HARDWARE_PASS / FULL_CHAIN_PASS / PROJECT_COMPLETE`。
- 本轮未运行真正 final test、未读 `test` / `ood_final_test`、未改动 checkpoint / 标签序 / 预处理 / 模型结构。
