# rml24_dualsdr_rf_dataset_v1 — 双 SDR 真实 RF 域适配数据集合同

机器可读版见同目录 `rml24_dualsdr_rf_dataset_v1.py`（`python -I` 可导入，`dataset_contract_sha256()`
为全合同身份戳）。本文件是字段级的人类可读说明，二者必须一致。

## 1. 目的与边界

为后续「真实双 SDR RF 域微调」准备的**数据合同**。本任务只定义合同/计划/工具，**不采集、不训练、
不量化、不生成生产替换模型**。

- 模型输入必须由**生产链**（raw RX → coarse-CFO → 分数定时 → 广线性 iqrfrec → int16 →
  PreprocessChain → D2 恢复 → 分类窗 → `[2,1024]` fp32）生成；**禁止**用期望 payload 代替、禁止
  NumPy 近似重建、禁止手工修正。
- 无 provenance（原始捕获 SHA + 采集会话 + 门禁状态）的样本**不得进入训练集**。
- clean24_smoke 是**冻结回归集**，永不进入 train/val/test。

## 2. 冻结身份（逐字节不变）

| 字段 | 值 |
|---|---|
| FP32 checkpoint `best.pt` SHA256 | `96cd25f8…`（域适配初始化点） |
| ONNX `rml24_24class_opset17.onnx` SHA256 | `976618a1…` |
| 24 类标签合同 SHA256 | `3e1382d1…` |
| 生产 BF16 json / raw SHA256 | `28272abc…` / `c1781aec…`（**永不被覆盖**） |
| TF32 A/B json / raw SHA256 | `8d00a1c3…` / `f8366a10…`（**永不被覆盖**） |
| 网络名 / I/O | `model_24class` / `[1,2,1024]` fp32 → `[1,24]` fp32 |

## 3. 标签与 source_index

- `source_index = raw24_class_index * 500 + intra_class_offset`，`offset ∈ [0,499]`。
- 24 类原始标签序（`rml24_raw_contract.py::SOURCE_LABEL_ORDER_24`）：
  `OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK, 16APSK, 32APSK, 64APSK, 128APSK,
  16QAM, 32QAM, 64QAM, 128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC, AM-DSB-WC, AM-DSB-SC,
  FM, GMSK, OQPSK`。
- 24→23 合并：仅 AM-SSB-WC(17) 与 AM-SSB-SC(18) 合并为 deployed23=17（AM-SSB），其余 index 顺移。

## 4. 采集计划（Pilot 240 / Formal 720）

| 阶段 | 每类 offset | 每类样本 | 总计 | session 要求 |
|---|---|---|---|---|
| Pilot | 0..9 | 10 | 240 | ≥1 session |
| Formal | 10..39 | 30 | 720 | ≥2 sessions |

Formal 确定性划分（按 offset，无泄漏）：train=10..27（18）、val=28..33（6）、test=34..39（6）。
Pilot 不参与 train/val/test（仅探索真实门禁分布 + 校准采集参数）。

## 5. C4 冻结 RF 采集配置

| 字段 | 值 |
|---|---|
| center_freq_hz | 2400000000 |
| sample_rate_hz | 2560000 |
| rx_gain | 35 |
| rx_bw_hz | 18000000 |
| tx_bw_hz | 18000000 |
| tx_atten_db | -40 |
| tx_target_rms | 2048 |
| rf_path | direct-cable |

单 SDR（`link=single`）用本地 cyclic TX 自发自收；双 SDR（`link=dual`）用 PC-TX/板-RX（TCP 39010）。

## 6. 门禁状态（0.100 残差门，门本身**永不改**）

| 状态 | 含义 | 处置 |
|---|---|---|
| `PASSED` | 残差 ≤ 0.100 | 进入主集 |
| `DIAGNOSTIC_PROVISIONAL` | 门拒（0.10 < 残差 ≤ 上限） | 保留、标注，默认**不进**主训练集 |
| `REJECTED` | 硬失败（clip/CFO/corr 超限） | ≤3 次有界重捕获后仍失败则丢弃并记录 |

## 7. 数据集清单 schema（`MANIFEST_COLUMNS`，29 列）

`sample_id, source_index, raw24_class_index, raw24_label, deployed23_index, deployed23_label,
modulation, intra_class_offset, phase, split_role, link, gate_status, payload_training_residual,
corr, cfo_hz, wide_linear_ratio, capture_attempts, capture_session_id, center_freq_hz,
sample_rate_hz, rx_gain, rx_bw_hz, tx_bw_hz, tx_atten_db, tx_target_rms, rf_path,
raw_rx_iq_sha256, model_input_sha256, frozen_raw24_pred`

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| sample_id | str | `c{raw24:02d}_{offset:03d}`，如 `c00_010` |
| source_index | int | `class*500+offset`，全局唯一 |
| raw24_class_index / label | int/str | 24 类原始标签 |
| deployed23_index / label | int/str | 合并后 23 类标签 |
| modulation | str | 与 raw24_label 相同（调制族） |
| intra_class_offset | int | 0..39 |
| phase | str | `pilot` / `formal` |
| split_role | str | `train`/`val`/`test`/`pilot` |
| link | str | `single` / `dual` |
| gate_status | str | 见 §6 |
| payload_training_residual | float | 归一化残差（门判据） |
| corr / cfo_hz / wide_linear_ratio | float | 恢复质量：相关、CFO、`|b|/|a|` |
| capture_attempts | int | 有界重捕获次数（≤3） |
| capture_session_id | str | 采集会话（formal 必须 ≥2 session） |
| center_freq_hz … rf_path | — | C4 配置逐行冗余（自包含） |
| raw_rx_iq_sha256 | str | 原始捕获 IQ 的 SHA256 |
| model_input_sha256 | str | 生产链 `[2,1024]` fp32 输入的 SHA256 |
| frozen_raw24_pred | int | 冻结 BF16 模型预测（审计基准，非训练标签） |

## 8. 预注册训练规格（Pilot）

`init=FP32 96cd25f8…`；候选 **仅 2**：①classification-head-only ②full-network-low-LR；
AdamW / lr∈{1e-5,3e-5,1e-4} / wd=0.01 / grad_clip=1.0 / cosine / warmup=5% / max_epochs=20 /
patience=4 / seeds∈{17,29,43}；数据混合 ①real-rf-only ②clean+real-RF-balanced（clean 回放池与
clean24_smoke **SHA 不相交**，否则 fail-closed）；每批类均衡；**仅 val 选模，永不 test**。
