# 并行线 A — 数据溯源（DATA PROVENANCE）

任务：`M29-RML24-REALRF-FINETUNE-PILOT1` / 线 A `pilot1_train_data`（纯离线）

## 1. 可训练资产结论

**`TRAINABLE_CHECKPOINT_FOUND`**。冻结模型 `ADAMRV11Net`（24 类）的可训练链完整：

| 资产 | 路径 | 状态 |
|---|---|---|
| 训练 checkpoint（冻结） | `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt` | SHA `96cd25f8…` 已核验，3537312 B |
| 模型结构源码 | `F:\FPGA_Work\sdr_amr_12class_ood_u_v1\models\ad_amr_v1_1_net.py`（`ADAMRV11Net`） | 存在 |
| 训练配置 | `F:\FPGA_Work\sdr_amr_12class_ood_u_v1\configs\rml24_base.yaml` | 存在（LR 1e-3、AdamW、CE、bs256、80 epoch、label_smoothing 0.1） |
| 训练代码 | `F:\FPGA_Work\sdr_amr_12class_ood_u_v1\training\rml24_*.py` + `train_ad_amr_v1_1_data_v2.py` | 存在 |
| 切分索引 | `F:\FPGA_Work\sdr_amr_12class_ood_u_v1\data\radioml2018\rml24_split_indices.npz` | SHA `9a035841…`，seed 20261003，[0.6,0.2,0.2] |

微调从原始 PyTorch checkpoint 初始化（`model_state` + `class_names`），**不从 NPU JSON/RAW 反推权重**。

## 2. 960 源 IQ 选样

- 来源：原始 RadioML2018.01A HDF5 `F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5`（SHA `e3dd0bef…`，2555904 样本）。
- 切分：**test 切分**（seed 20261003，20% = 511680）。
- SNR：**30 dB**（最高、最干净，每类 820 可用）。
- 数量：每类 40 → 24×40=960；每会话每类 10。
- 排除：与既有 480 帧冻结测试集（`frozen_test_selection.tsv` 的 `hdf5_row_index`）**零重叠**（排除 480 行）。
- 分配：每类按 dataset_index 升序取 40，inst 0–9→S1、10–19→S2、20–29→S3、30–39→S4。
- 命名：`source_id = s{sn}_c{ci:02d}_i{inst:02d}`。

## 3. 四轮独立性

- 四轮 dataset_index / source_id / source_iq_sha256 / TX payload SHA 零重叠（自测断言已过）。
- 与既有 480 冻结集不相交。

## 4. 输入合同

- 源 IQ 落盘格式：`[2,1024] f32 LE` planar（行 0=实部、行 1=虚部），8192 字节，逐样本 `source_iq_sha256`。
- 由 `X[i]`（[1024,2] fp32，末维 [I,Q]）→ `np.ascontiguousarray(X[i].T).astype(np.float32)`。
- **无 DC/归一化/重采样/滤波**；RMS 已在训练域匹配。

## 5. 交付物

```
line_a/
  scripts/select_960_sources.py        # 选样脚本（可复现）
  results/source_manifest_960.tsv      # 960 行主清单
  results/S1_manifest.tsv … S4_manifest.tsv
  results/split_contract.json
  inputs/S1/…S4/  （各 240 个 .bin）+ inputs/SHA256SUMS.txt
  trainable_asset_inventory.json
  DATA_PROVENANCE.md
```

## 6. 红线确认

不训练、不碰板、不发射；960 固定分母不剔；四轮零重叠；主指标只用原始 RadioML 实例（不混入 v2 AM 修正波形）；不从 NPU RAW 反推权重；不写 RF_PASS/PROJECT_COMPLETE/FINETUNE_SUCCESS。
