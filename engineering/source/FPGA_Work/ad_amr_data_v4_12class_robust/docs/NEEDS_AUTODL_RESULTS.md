# AutoDL 结果回来前：本工程所需的确切产物清单

**目的**：v4 鲁棒性增强在 AutoDL 正式结果回来前最高状态只能是
`READY-FOR-AUTODL-RESULT-INGEST`。本文列明从 AutoDL 运行目录
`/root/autodl-tmp/ad_amr_data_v3_12class_ff2b3fb3_run` 需要回传的确切相对路径，
以及每个文件用途；并明确指出基线**不会产出**、但本工程后续分析**需要**的补充产物。

---

## 1. 基线必会产出的文件（相对运行目录）

| 相对路径 | 内容 | 本工程用途 |
|----------|------|-----------|
| `outputs/ad_amr_v1_1_data_v3_12class/formal/acceptance.json` | 双种子正式验收总报告（gates、records、export） | 结果导入主入口 |
| `outputs/ad_amr_v1_1_data_v3_12class/formal/seed2026/checkpoints/best.pt` | 种子 2026 最优 checkpoint | 复核/重评估 |
| `outputs/ad_amr_v1_1_data_v3_12class/formal/seed2027/checkpoints/best.pt` | 种子 2027 最优 checkpoint | 复核/重评估 |
| `outputs/ad_amr_v1_1_data_v3_12class/formal/seed2026/checkpoints/last.pt` | 种子 2026 末轮 checkpoint（含 history） | 训练轨迹审计 |
| `outputs/ad_amr_v1_1_data_v3_12class/formal/seed2027/checkpoints/last.pt` | 种子 2027 末轮 checkpoint（含 history） | 训练轨迹审计 |
| `outputs/ad_amr_v1_1_data_v3_12class/formal/export/onnx/ad_amr_v1_1_opset17.onnx` | 导出 ONNX | 算子白名单/ORT 一致性复核 |
| `outputs/ad_amr_v1_1_data_v3_12class/formal/export/onnx/export_report.json` | ONNX 检查 + ORT parity 报告 | 部署边界复核 |
| `outputs/ad_amr_v1_1_data_v3_12class/pilot/selected_candidate.json` | pilot 选择与 promoted 标记 | 确认 `radioml_pretrained` 被提升 |
| `outputs/ad_amr_v1_1_data_v3_12class/preflight/DATA_V3_12CLASS_PREFLIGHT_DONE.json` | preflight 标记（含 release_input_hash / data_identity / class_contract） | 复算一致性核验 |
| `outputs/ad_amr_v1_1_data_v3_12class/public_pretrain/checkpoints/best.pt` | RadioML 24 类主干预训练 checkpoint | 初始化链审计（只读） |

`acceptance.json` 内部结构（已从基线 `run_ad_amr_v1_1_data_v3_12class_formal.py` 核实）：
顶层含 `release_input_hash / variant / class_contract / records / export / gates / promoted`；
每条 `records[i]` 含 `seed / training / checkpoint / validation / fake_int8 / ood`，其中
`ood` 是 `{domain: evaluation_report}`（domain ∈ cfo_strong / phase_noise / iq_imbalance /
multipath / clipping / multi_impairment）。

---

## 2. 基线**不会**产出、但后续「混淆关系」分析**必需**的补充产物

基线的 `evaluation/evaluate_ad_amr_v1_1.py` 与 `training/ad_amr_v1_1_trainer.py::_summary`
只把**聚合指标**（accuracy / macro_f1 / per_class_accuracy / rated_* / per_snr_*）写入报告；
`training/metrics.py` 虽然计算了 `confusion_matrix`，但**未落盘**，逐样本预测也**未保存**。

因此，为支撑任务书 §四的「具体脆弱类别、混淆关系」分析，需要在 AutoDL 侧**额外采集并回传**
（用 v4 新增工具 `scripts/import_formal_results.py` 之外的一行式采集，或后续新增的采集脚本，
不修改基线训练/评估代码）：

| 需要补充的产物（建议命名，相对运行目录） | 内容 |
|------------------------------------------|------|
| `outputs/ad_amr_v1_1_data_v3_12class/formal/preds/{seed}_{domain}_preds.jsonl` | 逐样本 `{sample_id, label, pred, snr_db}`，覆盖 validation + 每个 OOD 域 + fake_int8 |
| `outputs/ad_amr_v1_1_data_v3_12class/formal/preds/{seed}_{domain}_confusion.csv` | 12×12 混淆矩阵（或等价地由逐样本重算） |

> 若以上补充产物缺失，`scripts/analyze_formal_failures.py` 只能输出「每域 macro-F1 下降、
> 每类准确率、脆弱类排序（基于聚合 per_class_accuracy）」的**部分**结论，并会明确打印
> 「confusion matrix unavailable」——**不会臆造混淆对**。

---

## 3. 回传包一致性要求

- 回传文件必须与 AutoDL 侧 `release_guard_v1_1_data_v3_12class.py` 记录的
  `release_input_hash`、`data_identity`（RadioML dataset_sha256/index_sha256）、
  `class_contract` 一致；`scripts/verify_paired_records.py` 会复核。
- `class_contract` 必须等于冻结十二类顺序
  `OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`。
- 任何文件缺失或哈希不符，导入即失败（fail closed），不进入分析。

---

## 4. 状态

本轮在 AutoDL 结果回来前最高状态：**`READY-FOR-AUTODL-RESULT-INGEST`**。结果回来并导入、
核验、分析通过后，才能进入 pilot/formal 的增强实验（`scripts/run_robust_pilot.sh` /
`scripts/run_robust_formal.sh` 默认拒绝启动，见各脚本头）。
