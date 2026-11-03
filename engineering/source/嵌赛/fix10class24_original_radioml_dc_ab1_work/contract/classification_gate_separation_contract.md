# 分类门与保真门分离 — 行为契约 (Part B 诊断旁路 + 统一判定器)

**任务** `fix10class24-classification-gate-separation1`
**状态 token** `M29-RML24-FIX10CLASS24-CLASSIFICATION-GATE-SEPARATION1-READY-FOR-BOARD-TEST`
**性质** 纯离线 BOARD-PREP。禁 `RF_PASS` / 发射 / 训练。板端 C++ **未在本环境编译**
(无 aarch64 g++)，本任务报 READY-FOR-BOARD-TEST，不声称"已测过"。

---

## 1. 要分离的两个门

| 门 | 问题 | 判据 | 失败结果 |
|---|---|---|---|
| **保真门** (fidelity gate) | RF 链是否把 TX 信号保真到可信任 | `payload_training_residual <= 0.100` (`iqrfrec::kPayloadTrainingResidualMax`) | `gated=0`, `gate_reject=1`, `board_pred=-1` |
| **分类门** (classification gate) | 给定恢复后 payload，属于哪一类 | NPU24 BF16 `raw24_predict` argmax | `board_pred = raw_24_top1` |

现有生产行为把二者**耦合**：保真门不通过就不分类。本任务**不改变生产行为**，而是
新增一条**显式、默认关闭、仅诊断**的旁路，把"保真不够好但对齐/恢复仍有效"的帧也
分类一次，记录为诊断层——从而回答"分类门到底是不是被保真门拖累"。

---

## 2. Part B — `--diagnostic-force-classify`（默认 OFF）

两个 runner（`radioml_singlesdr_ab_runner.hpp` / `radioml_dualsdr_ab_runner.hpp`）都新增
布尔参数 `--diagnostic-force-classify`，**默认 OFF**。ON 时，对**仅因残差超 0.100 被拒**
（`rec.failure == PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`）的捕获，若其对齐与恢复仍通过有效
性检查，则继续做诊断分类。

### 2.1 显式旁路条件（全 AND，缺一即拒绝，fail-closed）

`is_diagnostic_bypassable()`（`radioml_diagnostic_classify.hpp`，单一权威实现）：

1. `rec.failure == PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`（唯一失败 = 残差门）
2. `residual > 0.100`（确实被门拒，而非恰好通过）
3. `residual <= 0.30`（`kHardInvalidResidualCeiling`，非不可恢复）
4. `cfo_in_range`（coarse + fine CFO 有效；该检查在 estimate() 中**残差门之后**，故生产短路的检查在此显式补上）
5. `!rx_clipped`（无削顶 RX 样本）
6. `neg_pass`（负控干净）
7. `|rec.sro_ppm| <= max_sro_ppm`（采样率偏移正常）

`forceable`（runner 已算）= `!gated && failure==RESIDUAL && residual<=0.30` 是**必要条件**，
旁路条件在其上叠加 `cfo_in_range && !rx_clipped && neg_pass && |sro_ppm|<=max`。

### 2.2 诊断再恢复 `try_diagnostic_apply()`

残差被拒帧的 `ccr.payload` 为空（`recover_payload_with_coarse_cfo` 仅在 `rec.valid` 时填充），
故用暴露的 `coarse_cfo_hz` + `fractional_timing_samples` 重建内部 `aligned` 捕获：

```
derot[n] = rx[n] * exp(-j 2π coarse_cfo_hz n / kFs)
aligned  = iqdual23fix10::detail::apply_fractional_advance(derot, fractional_timing_samples)
rec_diag = rec;  rec_diag.valid = true;   // 仅旁路 valid 条件
out_payload = iqrfrec::apply(aligned, rec_diag);  // try/catch
```

**红线**：冻结的 `iqrfrec::apply()` 逐字复用；**唯一**放宽的是本地副本的 `rec.valid`；
`apply()` 对 payload 增益与 payload TX 尺度的安全 guard **保留**，其抛异常即**拒绝旁路**
（`diagnostic_bypass_apply_failed++`，不分类）。

### 2.3 标记（绝不改写生产门）

- 生产 `board_results.tsv`（19 列）**逐字节不变**：被旁路帧仍 `gated=0, gate_reject=1,
  board_pred=-1`。
- 诊断预测写**独立** `board_diagnostic_results.tsv`（12 列，见 §3），每行
  `diagnostic_gate_bypass=1`, `classification_layer=NPU_BF16_DIAGNOSTIC`。
- 每帧 `.diag.json` 增加 `diagnostic_gate_bypass` 与 `classification_layer`：
  `NPU_BF16_DIAGNOSTIC`（旁路）/ `NPU_BF16_PRODUCTION`（gated）/ `NOT_APPLICABLE`（其余）。
- 诊断分类判定 `hard_invalid` 帧**绝不**强制为成功；`hard_invalid` 语义不变。

---

## 3. `board_diagnostic_results.tsv`（12 列，Part B 输出）

```
selection_id  hdf5_row_index  raw24_class  dataset_snr_db  residual  corr
board_pred_diag  finite_diag  repeat_deterministic  classification_layer
diagnostic_gate_bypass  label_correct
```

仅当 `--diagnostic-force-classify` ON 且帧通过全部旁路条件且 `try_diagnostic_apply()`
成功时写一行。`board_pred_diag` = 诊断 argmax（非有限则 -1）；`finite_diag` = 两次
NPU 推断都有限；`repeat_deterministic` = 两次推断一致；`label_correct` = 与源标签一致。

---

## 4. 六项统计（runner 汇总 + summary JSON + stdout）

| 统计 | 含义 |
|---|---|
| `diagnostic_bypass_total` | 满足全部旁路条件的帧数 |
| `diagnostic_bypass_classified` | 其中产生有限分类的帧数 |
| `diagnostic_bypass_correct` | 其中预测 == 源标签 |
| `diagnostic_bypass_accuracy` | 派生 = correct/classified（classified=0 则 NaN） |
| `diagnostic_bypass_repeat_deterministic` | 其中两次推断一致（x2 确定性） |
| `diagnostic_bypass_refused` | `forceable` 但**未**旁路（CFO/SRO/clip/neg 无效） |

第 7 个防御性计数 `diagnostic_bypass_apply_failed` = 旁路条件满足但 `apply()` 安全 guard
拒绝。六项统计在 `summary.json`、`ROUTE_F_*` stdout、判定器三处口径一致。

---

## 5. 统一判定器 `judge_radioml_gate_separation.py`

每臂 `{single,dual} × {direct,dc-transport}` 读三类结果，比较生产门 / 诊断旁路 / 盲分类
（Part A）的覆盖率与准确率：

| 输入 | 文件 | 语义 |
|---|---|---|
| 生产 | `board_results.tsv`（19 列） | 保真门内分类（不变） |
| 诊断 | `board_diagnostic_results.tsv`（12 列） | Part B 旁路分类 |
| 盲 | Part A 盲 RX `board_results.tsv`（19 列，residual/corr/cfo = `NA`） | 无保真门分类 |

统一口径：`gate_reject` 记端到端失败（分母不剔除）；`hard_invalid` 绝不强制成功；缺失
输入 = `PENDING` 绝不 auto-success；`dataset_snr_db` 是标称 SNR 非真实 RX SNR。

---

## 6. 冻结红线（本任务永不违反）

1. 生产 0.100 残差门 / 19 列 `board_results.tsv` / `board_pred` / `gated` / `gate_reject` 语义**不变**。
2. `hard_invalid` 帧绝不强制为成功。
3. 冻结恢复数学 `iq_rf_sync_recovery.hpp` / `iq_dual_sdr_coarse_cfo_recovery.hpp` 逐字复用；唯一放宽 = 本地副本 `rec.valid`。
4. 冻结 BF16 模型 SHA、24 类标签序、480 帧选择、传输契约、`unscale`、`lround` 半远离零不变。
5. 不训练 / 不调参 / 不换模型 / 不按类选择恢复或捕获。
6. 分类预处理与模型窗口 = 恢复后 payload 前 1024 复样本 `* unscale`（direct）/ `reconstruct_dc_window`（dc-transport），与 gated 路径同分支。
