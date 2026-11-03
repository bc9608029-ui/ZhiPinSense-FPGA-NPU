# M29-RML24-REALRF-TRAINABILITY-AUDIT1 — 数据来源与身份核验

状态：`…-DATA-PROVENANCE-COMPLETE`（纯离线，只读扫描）

本任务只读使用既有数据，不产生新板端采集。数据来源、身份、捕获类型如下。

## 1. 冻结身份（逐字节不变）

| 资产 | SHA | 说明 |
|---|---|---|
| BF16 模型 raw | `c1781aec…` | 24 类 ADAMRV11Net 权重 |
| BF16 模型 json | `28272abc…` | 24 类图定义 |
| checkpoint | `96cd25f8…` | 训练检查点 |
| HDF5 | `e3dd0bef…` | RadioML2018.01A |

## 2. 源波形（发送侧，公共协议 v2）

`fix10class24_waveform_correct_v2_work/tx_package/public_protocol_tx_manifest.tsv`

- 24 个源波形，**1 波形/类**（`source_index = class_index + 1`，1..24）。
- `source_id` 全部 = `fix1v2-waveform-corrected-24waveforms`（单一来源，非独立实现）。
- `conversion_version` = `v2`（统一，无混版本）。
- 每波形有 `burst_sha256` / `payload_ci16_sha256` / `model_input_sha256`。

## 3. 捕获会话（接收侧）

| 会话 | 捕获类型 | 帧数 | 源波形 |
|---|---|---|---|
| `rf_fix2_target` | 真实双 SDR RF | 24 | tx_package 1..24 |
| `rf_independent_v2` | 真实双 SDR RF | 24 | tx_package 1..24 |
| `digital_fix2_v2` | 数字文件回放（无 RF） | 24 | tx_package 1..24 |
| `digital_independent_v2` | 数字文件回放（无 RF） | 24 | tx_package 1..24 |

另有 `full24_accuracy1` 真实 RF 会话（24 帧，`source_index=class_index*500`，即
0,500,…,11500，**另一组源波形**），含门内/门拒/强制分类三态，见 §5。

## 4. 身份核验结论（`results/data_inventory.tsv` + `inventory_verdict.json`）

- 4 个会话各 24 帧、各 24 唯一源波形（tx_package 集合）。
- **跨会话源波形重叠 = 24/24（所有会话对）**：四个会话携带**同一组** 24 源波形。
- 数字会话 recovered tensor 之间 1 个字节级重复（`digital_independent_v2` 中 1 个
  tensor SHA 与前一数字会话相同，属确定性数字回放，非泄漏）。
- `n_unique_source_sha_total` = 24（不是 4×24=96）。

## 5. 附带证据（域对比用）

- A 域（原始 RadioML）：`fix10class24_original_radioml_accuracy1_work/results/summary.json`
  → BF16 `419/480 = 87.29%`（stratified-sample test，非全数据集）。
- C0 域（full24 RF）：`full24_accuracy1_work/…/summary.json` → e2e `10/24`、门内
  `10/15 = 66.7%`、强制 `18/24 = 75%`、覆盖 `0.625`、门限 `0.100`。
