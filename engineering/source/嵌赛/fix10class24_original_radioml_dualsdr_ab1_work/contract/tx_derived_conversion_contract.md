# TX 派生转换契约 — fix10class24-original-radioml-dualsdr-ab1（权威，供 singlesdr fork 复用）

**Token** `M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DUALSDR-AB1-TX-DERIVED-CONVERSION-CONTRACT`

本文件固化 Phase A 的「输入与传输契约」结论，是 **singlesdr-ab1** 与 **dualsdr-ab1** 两个板端
loader/runner 的**单一权威**。机器可读版在同目录 `tx_derived_conversion_contract.json`；可执行
单一来源是 `scripts/radioml_dualsdr_common.py`（适配/量化/选取）与
`scripts/radioml_dualsdr_burst.py`（训练帧 burst 逐字重实现）。

## 1. 根本不兼容与适配结论（Phase A）

原始 RadioML 输入是训练契约逐字的 `[2,1024]` f32（1024 复样本），而生产 RF payload 冻结为
`kPayloadComplex = 53760` 复样本。二者**不可直接兼容**。本任务**不修改**生产恢复/训练帧/窗口规则，
改用**确定性、类无关**的适配：

| 环节 | 规则 |
|---|---|
| **duplication 循环铺排** | `payload[k] = iq[k mod 1024]`, `k=0..53759`（52 整周期 + 第 53 周期的前 512） |
| **scaling 缩放** | `scale = 2048 / native_rms(original_1024)`，量化到 CI16 |
| **quantize 量化** | 交错 int16 `[I0,Q0,…] = lround(tiled·scale)`，clamp `[-32768,32767]` |
| **resampling 重采样** | **无**（速率不变 2.56 Msps；无重采样/滤波/归一化） |
| **model window 模型窗口** | 恢复后 payload 的**前 1024 复样本** |
| **unscale 反缩放** | `native_rms(original_1024) / 2048`（counts → 原始 f32 域） |

### 舍入语义（byte-exact，红线）

量化用 **`lround`（四舍五入到最近、平局远离零）**，逐字匹配 C++ `std::lround`/`std::llround`；
**不是** `numpy.rint`（平局到偶）。`scripts/radioml_dualsdr_common.py::lround` 已实现。板端 loader
一律从 `SHA256SUMS.txt` 取 `payload_sha_pre`，**不要**用 Python 重推导。

## 2. 训练帧 burst（canonical burst SHA/scale）

板端 `iq_rf_training_frame.hpp::build_burst` 的逐字重实现见
`scripts/radioml_dualsdr_burst.py`。布局（复样本，共 59904 = 119808 int16）：

```
[preamble ZC(root=1) 1024][settling-zero 1024][payload-training 16QAM 1024]
[payload 53760][guard-zero 2048][tail ZC(root=3) 1024]
```

冻结常量：`kPayloadStart=3072`、`kTailStart=58880`、`kTrainAmp=2048.0`、
`kPayloadTrainingAmp=2896.309375740099`、`kPayloadTrainingSeed=0x2A9E1B7D`。

### payload 无关的确定性包装块 SHA

| 块 | 长度(复) | SHA256 |
|---|---|---|
| preamble (ZC root=1, amp 2048) | 1024 | `d4b4bb3af9ad57836f4de7dfd9046898983c66f949d33aad35ed8dc434ccc97f` |
| settling-zero | 1024 | `ad7facb2586fc6e966c004d7d1d16b024f5805ff7cb47c7a85dabd8b48892ca7` |
| payload-training (16QAM LCG) | 1024 | `f06e9b3de0f51594d8db0501a03918350072d4bc0e5a56f955053bafa35663ca` |
| guard-zero | 2048 | `9f1dcbc35c350d6027f98be0f5c8b43b42ca52b7604459c0c42be3aa88913d47` |
| tail (ZC root=3, amp 2048) | 1024 | `ccddabe154b62a4cbae7d628f410d89ef9bfd54ebbaf79d83139417a36666a8e` |

### per-payload SHA/scale 公式

- `payload_sha_pre` = `sha256(<sid>.i16 字节)`（导出产物）
- `payload_sha_post` = `sha256(clip(lround(i16 · tx_scale)))`，其中 `tx_scale = 2048 / native_rms(i16 counts)`
- `burst_sha` = `sha256(build_burst(缩放后 payload_i16))`
- 当 `.i16` 已处于 RMS 2048 时 `tx_scale == 1.0`

> 诚实边界：`radioml_dualsdr_burst.py` 是**规范重实现**（逐字对照 C++ 常量/舍入），不是 C++ 二进制的
> 等效物。burst_sha 的最终仲裁是板端 C++ `build_burst`（板端独立重建并比对 SHA）；本模块仅用于板测前
> 主机预演，不一致即失败关闭。

## 3. short24 固定选取规则

```
对每个 raw24_class c ∈ 0..23:
    取该类别中 dataset_snr_db == 30 且 selection_id 最小的那一帧
要求每类恰好 1 帧 30 dB 层，否则 fail-closed（missing 列表抛出）
```

- 数量 **24**，用途 = 板测烟测（验证传输/身份/输出完整性），**不是**准确率测量。
- 标签/SNR **绝不**用于恢复或预测；short24 用标签仅是为了每类挑 1 帧做身份/烟测通过。

## 4. 板端结果 TSV 契约（19 列）

```
selection_id  hdf5_row_index  raw24_class  dataset_snr_db  gated  board_pred  finite
residual  corr  coarse_cfo_hz  fine_cfo_hz  total_cfo_hz  fractional_timing_samples  clip
capture_attempts  gate_reject  hard_invalid  tx_stop_ok  rx_restore_ok
```

| 字段 | 语义 |
|---|---|
| `gated` | `1` iff 残差 ≤ 0.100 门通过 |
| `finite` | `1` iff `board_pred` 是有效 0..23 argmax |
| `hard_invalid` | `1` iff 不可恢复（clip / 残差 > 0.30）；**绝不**强制为成功 |
| `board_pred` | raw24 类别索引 0..23，`finite==0` 时 sentinel `-1` |
| `tx_stop_ok / rx_restore_ok` | 双 SDR TX/RX 恢复标志（单 SDR 侧 TX 标志为 N/A 或 1） |

## 5. 板端 phase 命名（两 fork 必须共存）

| fork | phase |
|---|---|
| singlesdr-ab1 | `radioml-original-singlesdr-ab-24class-bf16-fix10` |
| dualsdr-ab1（本任务） | `radioml-original-dualsdr-ab-24class-bf16-fix10` |

合并两个 PATCH 到 rxrecovery1/npu-ab1 基线时，上述两个 phase 名必须在
`gate9_phase.hpp::valid_phase()` 与 `board_gate9_full_chain_rml23.cpp::main()` 中**同时存在**，互不冲突。

## 6. 冻结身份（逐字节不变）

- 模型 JSON `28272abc…` / RAW `c1781aec…` / CKPT `96cd25f8…`
- 24 类标签序 `rml24::kLabelOrder24`（AM-SSB WC=17 / SC=18 独立）
- 480 帧选择 / 类 / SNR / `hdf5_row_index` / `model_input_sha256` 与 npu-ab1 逐字节一致
- 生产 coarse-CFO + 分数定时 + 广线性恢复；0.100 门 + 至多 3 次重捕 + 末次选择
- RMS2048 上限、TX 衰减 ≤ −40 dB、RX 手动 35 dB、中心 2.4 GHz、速率 2.56 Msps、RX/TX 带宽 18 MHz
- 不训练 / 不调参 / 不换模型 / 不按类选择恢复或捕获
