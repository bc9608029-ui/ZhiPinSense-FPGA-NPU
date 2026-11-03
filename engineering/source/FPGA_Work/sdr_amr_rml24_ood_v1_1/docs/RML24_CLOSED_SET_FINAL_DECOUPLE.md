# RML24 Closed-Set Final Evaluation Decoupling（任务 39e5）

把 24 类**闭集**最终测试与尚未 ready 的 OOD-U 最终测试解耦：24 类模型可对 RadioML
`test` 一次性完成闭集评估，而**绝不**触碰 `ood_final_test`。

只新增/改动解耦路径。**不运行真正 final test，不改 checkpoint / 标签序 / 预处理 /
模型结构。** 最高状态仅 `RML24-CLOSED-SET-FINAL-PROTOCOL-READY`。

## 1. 动机

24 类闭集模型（`runs/rml24_base/formal/t002_losscross_entropy_optadamw/seed2027/checkpoints/best.pt`，
SHA `96cd25f8…`）已 ready 可做一次闭集 `test`；但后置 OOD-U（entropy 平衡 ID FRR≈60%、
energy AUROC≈0.709）不足以部署。原 `run_final_evaluation` 把闭集 test 与
`ood_final_test` 绑在同一条 one-time ledger 上——闭集评估一次必然消耗掉 OOD 最终测试的
唯一一次访问权，且强制要求冻结的 `ood_threshold_manifest.json`。解耦后两者互不消耗。

## 2. 改动内容（diff 清单）

| 文件 | 变更 |
|------|------|
| `evaluation/closed_set_gate.py` | **新增**：闭集 test 独立 one-time ledger（`os.open(O_CREAT\|O_EXCL)` 原子占用 + `os.replace` 完成；STARTED/COMPLETE 均拒绝重复；`ood_final_test_accessed` 恒 `false`） |
| `scripts/run_final_evaluation.py` | **新增** `_verify_closed_set_identity` / `build_closed_set_report` / `_write_closed_set_report_md` / `run_closed_set_final_evaluation`；`main()` 增加 `--closed-set-only` 分支；`--threshold-manifest` 由 required 改为仅非 closed-set 时 required |
| `scripts/run_final_evaluation.sh` | **改写**：支持 `<manifest> --closed-set-only`；closed-set 分支不要求 threshold manifest，尾标 `RML24_CLOSED_SET_FINAL_OK`；原路径尾标不变 |
| `tests/test_closed_set_final_decouple.py` | **新增** 13 项离线回归（见 §5） |
| `docs/RML24_CLOSED_SET_FINAL_DECOUPLE.md` | 本文档 |

原 OOD 冻结流程（`run_final_evaluation` / `read_threshold_manifest` /
`calibrate_ood_thresholds` / `score_ood_final` / `run_threshold_freeze` /
`ood_validation` / `ood_final_test`）**一字未改**，行为不退化。

## 3. `--closed-set-only` 行为契约

1. 只调用一次 `evaluate_rml24(config, checkpoint_path, split="test")`。
2. **绝不**调用 `evaluate_ood_rml24` / `score_ood_final` / `calibrate_ood_thresholds` /
   `generate_ood_records` / `ood_validation` / `ood_final_test` / `run_threshold_freeze`。
3. **不**要求、也**不**读取 `ood_threshold_manifest.json`（函数签名无 threshold 参数）。
4. 只读 `final_checkpoint_manifest.json` + 冻结 RadioML `test` + seed2027 checkpoint。
5. fail-closed 链：checkpoint 文件 SHA 由 `resolve_checkpoint` 校验；dataset / label /
   config SHA 必须是 64-hex；`label_contract_sha256` 必须等于冻结 24 类契约
   `label_contract_sha256()`。
6. ID `test` 访问由独立 ledger
   `runs/final_evaluation/rml24_closed_set_test_access.json` 守护，与 OOD final ledger
   （`final_test_access.json`）完全独立，互不创建/互不消耗。

## 4. 输出

- `runs/final_evaluation/rml24_closed_set_final.json` + `runs/final_evaluation/RML24_CLOSED_SET_FINAL_REPORT.md`：
  含 overall accuracy / macro-F1 / `rated_0_20_accuracy` / `high_10_20_accuracy` /
  `snr_0_accuracy` / `min_per_class_accuracy` / per-SNR / per-class（真实 24 类标签）/
  24×24 混淆矩阵 / 每类最主要混淆对象 / Top-5 最弱类 / checkpoint+dataset+label+config
  SHA / split 名+样本数 / `final_blind_test_accessed=true` / `ood_final_test_accessed=false`。
- **不输出** `OOD_PASS` / `HARDWARE_PASS` / `NPU_PASS` / `PROJECT_COMPLETE`。
- ledger 记录 `schema_version` / `run_id` / `mode=closed_set_only` / checkpoint·dataset·
  label·config 四个 SHA / `started_at` / `completed_at` / `id_test_accessed` /
  `ood_final_test_accessed=false` / `status` / `output_sha256`。

## 5. 新增回归测试（13 项，全离线）

1. closed-set-only 只调用一次 `evaluate_rml24(test)`；
2. 不调用任何 OOD 函数（对 `evaluate_ood_final_rml24` / `calibrate_ood_thresholds` /
   `score_ood_final` / `acquire_gate` / `complete_gate` / `read_threshold_manifest` 等打
   boom 桩，运行不得触发）；
3. 不生成 `ood_final_test`（且函数签名无 threshold-manifest 参数）；
4. 不读取 OOD threshold manifest（签名审计）；
5. 缺 checkpoint manifest → `FileNotFoundError` fail-closed，且不落 ledger；
6. checkpoint SHA 不匹配 → `RuntimeError` fail-closed（真实 `resolve_checkpoint`），且不落 ledger；
7. ID test 第二次访问被拒绝（COMPLETE ledger 拒绝重复 acquire）；
8. STARTED 状态也拒绝重复 acquire；
9. OOD final ledger 保持不存在（`acquire_gate` 打 boom 桩仍通过）；
10. 报告含 24 类真实标签（`per_class` / `top_confusions` / `top5_weakest` 全用 `LABEL_ORDER_24`）；
11. 混淆矩阵为 24×24 且行和=每类真实样本数；
12. 输出明确 `ood_final_test_accessed=false`、`final_blind_test_accessed=true`、ledger
    `output_sha256` 与落盘报告一致；
13. 原有非 closed-set 模式测试不退化（原 `tests/test_final_evaluation_protocol.py` 等仍全绿）。

## 6. 离线验证结果（本轮执行）

- `python -m pytest tests/ -q`：**237 passed, 4 skipped**（原 224+4，新增 13 全绿）。
- `python -m compileall -q evaluation/closed_set_gate.py scripts/run_final_evaluation.py tests/test_closed_set_final_decouple.py`：OK。
- `bash -n scripts/run_final_evaluation.sh`：OK。
- 未运行真正 final test、未读 `test` / `ood_final_test`、未碰 checkpoint。

## 7. AutoDL 覆盖步骤（用户本人执行）

```bash
# 0) 校验补丁自身
sha256sum rml24_ood_v1_1_closed_set_final_decouple_patch.tar.gz

# 1) 解包到临时目录（不直接覆盖工程）
mkdir -p /tmp/cs_decouple && tar -xzf rml24_ood_v1_1_closed_set_final_decouple_patch.tar.gz -C /tmp/cs_decouple

# 2) 校验内容文件
(cd /tmp/cs_decouple && sha256sum -c RML24_CLOSED_SET_FINAL_DECOUPLE_PATCH_SHA256SUMS.txt)

# 3) overlay 覆盖工程根（不碰工程根 SHA256SUMS.txt）
cp -r /tmp/cs_decouple/* .

# 4) 复测离线套件（确认 237 passed 4 skipped）
scripts/run_tests.sh

# 5) 用户本人执行一次性闭集最终测试（读一次 RadioML test，永不碰 ood_final_test）
scripts/run_final_evaluation.sh \
  runs/rml24_base/formal/final_checkpoint_manifest.json \
  --closed-set-only
```

## 8. 状态红线

- 最高状态：**`RML24-CLOSED-SET-FINAL-PROTOCOL-READY`**。
- 严禁：`FINAL_MODEL_PASS / FINAL_24CLASS_PASS / OOD_PASS / HARDWARE_PASS / FULL_CHAIN_PASS /
  PROJECT_COMPLETE / NPU_PASS`。
- 本轮未由 API 运行真正 test、未读 `test` / `ood_final_test`；一次性闭集最终测试由用户在
  AutoDL 上亲自执行。
