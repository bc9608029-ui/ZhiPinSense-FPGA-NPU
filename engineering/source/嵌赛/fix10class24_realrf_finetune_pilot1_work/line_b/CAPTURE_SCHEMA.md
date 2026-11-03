# 并行线 B — 采集链 32 字段 schema（CAPTURE_SCHEMA）

任务：`M29-RML24-REALRF-FINETUNE-PILOT1` / 线 B `pilot1_capture_chain`

权威字段序 = `contract/shared_contract.py::RESULT_TSV_FIELDS`（32 列）。采集链（板端
RX runner）逐样本输出一行；判读器（`line_c/judge_realrf_pilot.py::CAPTURE_COLS`）逐字
校验表头与列数。**保存动作在门控判断之前**：每个样本无条件先保存，无论门拒与否。

## 1. 逐样本无条件先保存（save-before-gate）

对每个 `source_id`，板端 RX 在**分类门控判断之前**无条件落盘以下产物（缺一判
hard_invalid，但仍占 960 分母）：

| 产物 | 文件 | 字段 | 说明 |
|---|---|---|---|
| 原始捕获 IQ | `<sid>.raw_rx.i16` | `raw_rx_sha256` | 门控前 raw RX（复数 CI16） |
| 恢复 1024 IQ | `<sid>.recovered.i16` | —（辅助） | 生产恢复链输出，1024 复 |
| 模型输入张量 | `<sid>.model_input.bin` | `model_input_sha256` | `[2,1024]` f32 LE，8192 B（`TensorCapture` 原子写） |
| logits | `<sid>.logits.bin` | `logits_sha256` | 24×f32 LE，96 B |
| 双预测 | — | `board_pred1` / `board_pred2` | 2 遍前向 argmax |

门拒样本**仍保存**（这是判级 `DATA_PIPELINE_INVALID` 之外的关键证据来源）；若门拒仍
能形成有限 tensor，可 forced-diagnostic 分类并标 `gate_pass=0` + `failure_token`，不得
伪装生产结果。hard-invalid（无同步/削顶/恢复失败/无 tensor）也仍写行、仍计分母。

## 2. 32 字段逐列说明

> **评审 39e5 Blocker 2（接收端真值隔离）**：下列真值列在板端采集时**一律置空**——
> `class_index` / `class_name` / `dataset_index` / `split` / `source_iq_sha256` / `label`
> （以及 `digital_pred` / `digital_label_correct`，数字基线亦为 Host 侧离线填）。采集结束
> 后由 `line_c/scripts/gt_join.py::backfill_truth()` 按 `source_id` 从主机真值清单
> `line_a/results/source_manifest_960.tsv`（9 列，绝不下发板端）离线回填，并 fail-closed
> 断言板端确实未带回任何真值。板端公共 manifest 为 3 列
> （`session_id`/`source_id`/`tx_payload_sha256`），PC 私有 5 列 manifest 保存
> `tx_payload_file`（板端不可见）。

### 身份（1–6）
| # | 字段 | 含义 |
|---|---|---|
| 1 | `session_id` | S1/S2/S3/S4 |
| 2 | `source_id` | `s{sn}_c{ci:02d}_i{inst:02d}`，全 960 唯一 |
| 3 | `class_index` | 0..23 真值（**板端置空**；主机离线回填，接收端运行时不得读取） |
| 4 | `class_name` | 24 类名（**板端置空**，离线回填） |
| 5 | `dataset_index` | 源 HDF5 行索引（四轮零重叠校验用；**板端置空**，离线回填） |
| 6 | `split` | train / validation / sealed_test（**板端置空**，离线回填） |

### 校验和（7–12）
| # | 字段 | 含义 |
|---|---|---|
| 7 | `source_iq_sha256` | 源 IQ SHA（应与 line_a manifest 一致，判读器查漂移；**板端置空**，离线回填） |
| 8 | `tx_payload_sha256` | TX CI16 payload SHA（板端由 3 列公共 manifest 提供） |
| 9 | `raw_rx_sha256` | 门控前 raw RX SHA |
| 10 | `model_input_sha256` | 送入 NPU 的 `[2,1024]` f32 SHA |
| 11 | `logits_sha256` | 24 logits SHA |
| 12 | `digital_pred` | Host 数字基线预测（**板端置空**，离线按 digital_baseline 回填） |
| 13 | `digital_label_correct` | 数字基线是否正确（**板端置空**，离线回填） |

### 预测（14–16）
| # | 字段 | 含义 |
|---|---|---|
| 14 | `board_pred1` | 板端第 1 遍 argmax（无 tensor 则空） |
| 15 | `board_pred2` | 板端第 2 遍 argmax |
| 16 | `label` | 真值 class_index（**板端置空**，离线回填） |

### 状态（17–22）
| # | 字段 | 含义 |
|---|---|---|
| 17 | `capture_ok` | 0/1，raw RX 捕获与连续性 |
| 18 | `no_sync` | 0/1，前导同步失败 |
| 19 | `rx_clipped` | 0/1，ADC 削顶 |
| 20 | `hard_invalid` | 0/1，硬失败（无 tensor/恢复崩溃） |
| 21 | `gate_pass` | 0/1，0.100 残差门判定 |
| 22 | `failure_token` | 门拒/失败原因 token（如 CFO/corr/clip） |

### 恢复参数（23–32，诊断）
| # | 字段 | 含义 |
|---|---|---|
| 23 | `coarse_cfo_hz` | 粗 CFO 估计（Hz） |
| 24 | `fractional_timing` | 分数定时（样本） |
| 25 | `timing_offset` | 定时偏移（样本） |
| 26 | `corr` | 前导/训练相关 |
| 27 | `training_residual` | 载荷训练块残差（门判据） |
| 28 | `training_residual_rel` | 归一化残差 |
| 29 | `a_real` | 广线性 IQ 补偿系数 a 实部 |
| 30 | `a_imag` | a 虚部 |
| 31 | `b_real` | b 实部 |
| 32 | `b_imag` | b 虚部 |

> 字段序/名以 `shared_contract.py::RESULT_TSV_FIELDS` 为唯一权威。

## 3. 板端实现复用点（rf_adapt prep1 已有，不重写）

- **张量保存**：`capture_hook.hpp::board::TensorCapture`（原子写 `live_rx_tensor_*.f32`，
  返回 SHA）——即 `model_input` 落盘。
- **logits 保存**：`logits_export.hpp`（24 f32 落盘 + SHA）。
- **失败 RX dump**：`iq_fix10class24_failed_rx_dump.hpp`（Phase B 门拒样本 dump）。
- **恢复链**：`iq_pc_tx_board_rx_24class_bf16_fix10.hpp`（生产 coarse-CFO → 分数定时 →
  广线性 iqrfrec → D2 恢复 → 分类窗）。
- **TX 派生 payload**：`line_b/scripts/export_finetune_tx_payload.py`（本任务，960 源 →
  分会话 CI16）。

板端 producer 新增职责：把上述既有保存动作按 §1 的顺序**移到门控判断之前**。身份列
（`session_id`/`source_id`/`tx_payload_sha256`）来自 3 列板端公共 manifest；真值列
（`class_index`/`class_name`/`dataset_index`/`split`/`source_iq_sha256`/`label`）板端
**一律置空**，由主机真值清单离线按 `source_id` 回填（接收端热路径不消费任何真值）。

## 4. 红线

- 接收端不得读取类别/原始载荷 IQ/manifest 真尺度/私有窗口起点/oracle 恢复参数。
- Ethernet 只传整轮启动/停止/状态/文件，不传逐样本恢复真值。
- 960 分母固定，门拒/失败/hard-invalid 不剔除；门拒保存且标诊断旁路。
- 门限 0.100 不改；生产恢复/协议/模型 SHA 不变。
