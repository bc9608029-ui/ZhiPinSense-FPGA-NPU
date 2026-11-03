# RadioML2018.01A 严格 24 类训练 + 12/24 共享 OOD 离线框架

新工程 `sdr_amr_rml24_ood_v1`：在 **模型侧 + 离线验证** 的范围内，训练一个严格对应
RadioML2018.01A 的 24 类候选模型，并为 12 类、24 类建立**共享的语义 OOD（Energy）
评测/训练框架**，最终从两者中选一个上板。

> 本工程**不做** UI / 触摸 / FPGA / RTL / 位流 / Gate 1–9 / 板端程序 / iCraft / 上板。
> 上板与 AutoDL 训练由**用户本人**执行；本工程只产出离线可复现的训练包与报告。

---

## 1. 数据与标签（严格冻结）

- 数据：DeepSig **RadioML2018.01A** `GOLD_XYZ_OSC.0001_1024.hdf5`，21,449,148,312 B。
- 样本：`X [2555904, 1024, 2]` float32（I/Q 对），`Y [2555904, 24]` one-hot，`Z` SNR
  `[-20..30]` 步长 2（26 档），每类 106,496 = 24 类 × 26 档 × 4096。
- 每样本已 RMS≈1.0，**不做任何归一化**（与 12 类板端 RMS-1.0 契约一致）。
- 24 类标签顺序（权威，勿重排）：

```
OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK,
16APSK, 32APSK, 64APSK, 128APSK, 16QAM, 32QAM, 64QAM,
128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC, AM-DSB-WC,
AM-DSB-SC, FM, GMSK, OQPSK
```

- 切分：按 `(类别, SNR)` 分层，`split_seed=20261003`，比例 `0.6/0.2/0.2`，train/val/test
  **无交集**，final test 只在最终评估访问一次。

## 2. 模型与 OOD 口径

- 模型：复用 `ADAMRV11Net`，`num_classes=24`；输入 `[B,2,1024]` fp32 planar I/Q；
  输出 **24 个 raw logits（无 Softmax）**——这是 Energy 的前提。
- RadioML 无干净参考信号 → `reconstruction_weight=0.0`（denoiser 仅作特征正则）。
- **语义 OOD**（新调制类 → UNKNOWN）：`ood/` 提供 MSP / Entropy / MaxLogit / **Energy**
  四种分数，Mahalanobis / OpenMax 仅离线对照。
- **Energy 唯一口径**：`E(x) = -T * logsumexp(logits/T)`，`E(x) > threshold → UNKNOWN`。
- OOD 族：`near_12`（仅 24 类有）、`near_24`（2FSK/GFSK/OFDM）、`far`（LFM/CW/MULTITONE/
  PULSE/FHOP）、`ambiguous`（AM-DSB/WBFM/FM/GMSK，不进主指标）。
- 三套隔离：`oe_aux_train` / `ood_validation` / `ood_final_test`（门限只在 validation 锁）。

## 3. 目录结构

```
contracts/   # 冻结契约（24 标签/输入/切分/12 类导入/OOD 语义/PREPROCESS）
data_tools/  # audit_rml2018.py（21GB SHA-256 + 冻结切分落地）
datasets/    # radioml2018_dataset(verbatim) + ood_generator/ood_dataset
models/      # ad_amr_v1_1_net(verbatim) + rml24_net(head=24 封装)
ood/         # scores / energy / metrics / thresholds / calibration
training/    # utils/metrics/loss(verbatim) + rml24_* + oe_energy_loss/oe_trainer
evaluation/  # evaluate_ad_amr_v1_1(verbatim) + evaluate_rml24 + evaluate_ood
channel/     # awgn/fading/impairments/channel_pipeline(verbatim)
v2/          # trainer/pilot/select/formal/results/fake_int8/losses(复用)
scripts/     # run_smoke / run_data_audit / run_train_rml24 / run_ood_baselines /
             # run_oe_energy / run_export / run_final_evaluation / run_tests / package_rml24
tests/       # 离线测试（89 项，无需 GPU/无需 hdf5）
```

## 4. AutoDL 执行顺序（用户本人执行）

先把 `GOLD_XYZ_OSC.0001_1024.hdf5` 拷贝到 `data/radioml2018/`（约 21 GiB），然后：

```bash
# 0) 依赖（GPU torch 由镜像提供；非 torch 依赖按 requirements-lock.txt）
pip install -r requirements-lock.txt

# 1) 数据审计：重算本机 SHA + 生成本机 audit.json / 索引 / manifests（端口不变）
scripts/run_data_audit.sh

# 2) 训练前自检：单 batch 过拟合门禁（失败则禁训）
scripts/run_smoke.sh

# 3) 24 类训练：Optuna TPE(≤12+8) -> select -> formal(3 种子)
scripts/run_train_rml24.sh

# 4) 语义 OOD 基线（MSP/Entropy/MaxLogit/Energy）
scripts/run_ood_baselines.sh runs/rml24_base/checkpoints/<best>.pt

# 5) （仅当 M13 触发条件满足：baseline Energy far-AUROC 不足）OE+Energy 训练
scripts/run_oe_energy.sh

# 6) 导出 ONNX（opset 17，算子白名单 + ORT parity 门禁）
scripts/run_export.sh runs/rml24_base/checkpoints/<best>.pt

# 7) 12 vs 24 离线最终评估 + 模型推荐（只能 RECOMMEND_*/BOTH/INSUFFICIENT）
scripts/run_final_evaluation.sh runs/rml24_base/checkpoints/<best>.pt

# 8) 离线测试（任一台有 CPU + numpy/scipy/torch 的机器）
scripts/run_tests.sh
```

## 5. 12 类模型接入（M0）

`contracts/12class_import_contract.json` 中 `checkpoint_path`/`model_sha256` 目前为
`PENDING_*`（12 类 V2 由另一工程训练）。就绪后填入真实路径 + SHA，导入脚本
`scripts/import_12class_checkpoint.py` 会 **fail-closed** 校验 SHA / 标签序 / 输出维度
（不符即 `BLOCKED_12CLASS_CONTRACT`），通过才写 `runs/12class_import/import_manifest.json`。

## 6. 门禁与状态红线

- 导出：ONNX vs PyTorch argmax ≥ 99.5%、fake-INT8 vs FP32 ≥ 98%；达不到标 `NO_GO`
  （量化项标 `NO_GO_FOR_QUANTIZATION`，保留 FP32 研究结果）。
- 状态红线（**绝不写**）：`FINAL_MODEL_PASS / FINAL_24CLASS_PASS / OOD_PASS /
  HARDWARE_PASS / FULL_CHAIN_PASS`。训练前最高 `READY-FOR-AUTODL-RML24-AND-OOD-TRAINING`，
  离线训练+评估后最高 `READY-FOR-12-VS-24-MODEL-SELECTION`。
- 若 OOD 只在 OE 见过的未知族有效 → 标 `OOD_SEEN-OUTLIER_ONLY`。
- 详细来源与可复现性见 `PROVENANCE.md`；每文件 SHA 见 `SHA256SUMS.txt`（打包时生成）。
