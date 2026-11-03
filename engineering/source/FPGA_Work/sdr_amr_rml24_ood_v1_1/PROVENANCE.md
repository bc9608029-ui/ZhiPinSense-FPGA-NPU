# PROVENANCE — sdr_amr_rml24_ood_v1_1

生成时间：2026-10-08。本文件记录本工程的来源复用、数据身份、构建验证与状态，
保证训练包可复现、可审计。V1.1 在 V1（`sdr_amr_rml24_ood_v1`）基础上新增训练预算 +
候选去重 + OE 提升门，见 `docs/TRAINING_BUDGET_AND_DEDUP_CONTRACT.md`、
`docs/OE_PROMOTION_CONTRACT.md`。

## 1. 复用来源（只读，不修改）

verbatim 拷贝自 12 类鲁棒工程 `F:\FPGA_Work\ad_amr_12class_robust_v2\autodl_v2\`：

| 目标（本工程） | 说明 |
| --- | --- |
| `models/ad_amr_v1_1_net.py` | ADAMRV11Net，`build_ad_amr_v1_1_model(num_classes, **cfg)` |
| `datasets/radioml2018_dataset.py` | fail-closed loader + `OFFICIAL_CLASS_ORDER` |
| `data/radioml2018/classes.txt` | 24 类标签名单 |
| `channel/awgn.py` `fading.py` `impairments.py` `channel_pipeline.py` | 信道增强 |
| `training/utils.py` `metrics.py` `ad_amr_v1_1_loss.py` | 训练基础设施 |
| `evaluation/evaluate_ad_amr_v1_1.py` | 12/24 通用评估 |
| `scripts/export_ad_amr_v1_1_onnx.py` | ALLOWED_OPS / opset17 / parity（24 类导出复用） |
| `v2/fake_int8.py` `losses.py` `augmentation.py` | 量化/损失/增广 |
| `v2/trainer.py` `pilot.py` `select.py` `formal.py` `results.py` 等 | V2 训练框架（按 `num_classes` 参数化复用） |

> 上述文件在源工程冻结，本工程内只读不覆盖。每个文件在本工程内的 SHA-256 冻结于
> `SHA256SUMS.txt`（打包时生成），任何改动都会导致 SHA 漂移。

## 2. 本工程净新增

- `contracts/` — 冻结契约（24 标签、输入、切分、12 类导入、标签语义、预处理）。
- `ood/` — 语义 OOD 框架（scores / energy / metrics / thresholds / calibration）。
- `manifests/` — 冻结切分 TSV（由审计脚本生成，落盘冻结）。
- `models/rml24_net.py` — 24 类 head 封装。
- `datasets/ood_generator.py` `ood_dataset.py` — 合成 OOD 族（近/远/ambiguous + 三套隔离）。
- `training/rml24_trainer.py` `rml24_run.py` `rml24_pilot.py` `rml24_formal.py`
  `rml24_select.py` `oe_energy_loss.py` `oe_trainer.py` `oe_run.py` `oe_decision.py`。
- `v2/candidate_signature.py` — 候选身份（`config_sha256` /
  `canonical_candidate_signature`）+ checkpoint 溯源。
- `evaluation/evaluate_rml24.py` `evaluate_ood.py`。
- `docs/TRAINING_BUDGET_AND_DEDUP_CONTRACT.md` `docs/OE_PROMOTION_CONTRACT.md`。
- `configs/`、`tests/`（离线测试）、`scripts/run_*.sh` 与净新增 `scripts/*.py`、
  `reports/`、本文档与 `README_AUTODL.md`、`requirements-lock.txt`。

## 3. 数据身份（跨机不变量）

- HDF5 SHA-256：`e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38`
- 大小：`21449148312` B；样本数 `2555904`；24 类 × 26 SNR = 624 层。
- 切分种子：`20261003`；比例 `[0.6, 0.2, 0.2]`；
  split_counts `{train:1533168, validation:511056, test:511680}`；重叠 0/0/0。
- 索引 SHA-256：`9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335`。
- 机器本地（AutoDL 上由 `run_data_audit.sh` 重生成，不冻结）：hdf5 路径、mtime_ns、
  绝对 index_path、`data/radioml2018/audit.json`、`rml24_split_indices.npz`、`manifests/`。

## 4. 构建与验证记录（本地 Windows CPU）

- `python -m compileall`：`contracts data_tools datasets models ood training evaluation v2 channel scripts tests` 全部通过。
- `bash -n scripts/*.sh`：全部通过。
- `python -m pytest tests/ -q`：**143 passed**（V1 的 89 项 + V1.1 新增：候选签名确定性 /
  键序无关 / 参数/损失变化 / 排除字段稳定 / epoch 预算稳定 / 缺失 SHA fail-closed /
  正式预算 1×3 默认 / 第二候选授权门 / 去重保最优 / seed 复用 REUSED_VERIFIED /
  artifact_mismatch fail-closed / duplicate 拒绝 / formal_summary 三值 / final manifest /
  OOD 基线 model_training_runs=0 / OE 提升/拒绝门）。
- 单 batch 过拟合探针（`overfit_probe_rml24`，本地 hdf5）：400 步，loss
  `3.203 → 0.000245`，final_accuracy `1.0`，finite_gradients `true`。
- 本地依赖版本：numpy 2.1.3 / scipy 1.16.3 / pyyaml 6.0.2 / h5py 3.12.1 /
  scikit-learn 1.6.1 / onnx 1.23.1 / onnxruntime 1.30.0 / pytest 8.3.4 / torch 2.12.0+cpu。
  optuna（仅 AutoDL 调参用）未在本地验证，见 `requirements-lock.txt`。

## 5. 可复现种子

- 24 类闭集 formal 种子：**`2026 / 2027 / 2028`**（V1.1 冻结，替换 V1 的 `3407/2026/39`）；
  调参 pilot 种子：`2026`。OE 验证种子：`2026`；OE 追加种子：`2027 / 2028`。
- OOD 合成：`SeedSequence([seed, split_code, family_code])`，family_code 由
  `OOD_FAMILIES` 枚举顺序决定；同种子字节级复现。

## 6. 状态

`READY-FOR-AUTODL-RML24-OOD-V1.1-CUDA-PREFLIGHT`（离线训练/评估尚未执行，最高允许状态）。
未写任何 `FINAL_*/OOD_PASS/HARDWARE_PASS`。
