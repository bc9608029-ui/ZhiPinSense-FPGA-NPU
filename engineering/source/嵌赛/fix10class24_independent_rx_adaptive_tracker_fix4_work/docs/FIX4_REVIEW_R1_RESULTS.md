# Fix4 REVIEW-R1 结果 — 修正公共参考残差定义后重估

任务：`M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4-REVIEW-R1`
状态：`…-REVIEW-R1-RESULTS-COMPLETE`（纯离线，不碰板/不训练/不发射）

判决 token：`M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4-REVIEW-R1-VERDICT`
（见 `results_r1/fix4_review_r1_verdict.json`）

## 0. 判决

**`MARGINAL_ONLY`**（修正残差定义后，按 §8 阶梯机械判定）。

| 会话 | T0 | C1 | T1–T5 | **T6** | 最优 |
|---|---|---|---|---|---|
| rf_fix2_target | 1/24 | 2/24 | 2/24 | **3/24** | T6 = 3/24 |
| old_rf_session | 1/24 | 2/24 | 2/24 | 2/24 | C1/T1–T6 = 2/24 |

- 24 分母不剔除，门限保持 0.100（需求 8）。
- `digital_no_new_flips_measured = true`（需求 7，实测，非硬编码），但判决阶梯要求
  `board_patch_allowed` 需两会话 best ≥ 12/24，故 `board_patch_allowed = false`。

## 1. 核心结论：修正残差定义并未恢复载荷

旧 R1（块均值当 DC）是 **NO_IMPROVEMENT**（best 2/24 两会话）。修正为逐样本公共参考
残差后：

- 数字域自洽性回归正确：残差锚点 **0.000**（旧块均值在无 RF 时泄漏 ~390）。
- 但真实 RF 上，唯一的「进步」是 **rf_fix2_target 会话的 T6 从 2/24 升到 3/24**，
  **old_rf_session 会话仍 2/24**。这是一帧边缘，未被第二会话复现，属于噪声级涨落，
  不是可恢复的 LO 轨迹。

T6 在 rf_fix2_target 命中的 3 类（见混淆矩阵）= **256QAM、AM-SSB-WC、AM-SSB-SC**。
其中**仅恢复了一个先前错误类别**：sid17 256QAM 在 C1 下被误判为 8ASK，T6 将其纠正
为正确 256QAM；但这只发生在 rf_fix2_target 一轮，old_rf_session 中 T6 对 sid17 仍
误判 8ASK（pred=2），**未复现**，因此不构成稳定恢复。其余两命中类（AM-SSB-WC /
AM-SSB-SC）是贯穿 fix3/fix4 的「易分类判别对」。

这等价于 fix3-R1 的 `STATIC_DC_MARGINAL_NO_RECOVERY` 在修正残差定义下的复现：公共
参考残差定义本身正确了，但可观测性结论不变。

## 2. 数字反例（需求 7）

直接读 24 个 `tx_package/<sid>.burst.i16`，未经 RF：

| 项 | 值 |
|---|---|
| 基线正确 | 23/24 |
| 残差锚点最大值 | **0.000**（参考均值 390.4，frac 0.000） |
| 各 tracker 新增翻转（实测） | **0**（C1/T1–T6 全 0） |

→ 修正后的定义在数字域是精确 no-op，不会引入翻转。`digital_no_new_flips` 为实测值。

## 3. 可观测性（需求 9/10，实测）

| 会话 | nonmono(im) | scatter/|anchor| 中位 | 帧间相关（真实顺序） |
|---|---|---|---|---|
| rf_fix2_target | 24/24 | 0.596 | 0.188 |
| old_rf_session | 24/24 | 0.632 | 0.090 |

- scatter/|anchor| ≈ 0.6：残差锚点围绕常速度 LS 线的偏离与自身幅度同量级，轨迹被
  散点主导，非可恢复相干漂移。
- 帧间 tail→settle 复相关系数在**这两轮、当前采集顺序下**测得 0.188 / 0.090，仅表示
  「这两轮当前顺序下观察到较低帧间相关」，**不**据此推断所有运行状态下 LO 泄漏都帧间
  不相关。

## 4. 边界裁剪敏感性核验（复审追加）

`frac_delay_sinc` 用 circular 索引（半长 16，33 抽头），train/tail 块首尾 16 样本会
wrap 污染残差锚点；实测 fractional_timing ∈ [-0.51, 0.45]。故重跑 `--edge-trim 16/32`
（排除每公共块首尾 16/32 样本后取残差锚点），两会话 × 8 跟踪器完整重估 + BF16 推理。

| 裁剪 | rf_fix2_target 最优 | old_rf_session 最优 | 判决 |
|---|---|---|---|
| trim0（基线） | T6 = 3/24 | C1 = 2/24 | MARGINAL_ONLY |
| **trim16** | C1 = 2/24 | C1 = 2/24 | **NO_IMPROVEMENT** |
| trim32 | T6 = 3/24 | C1 = 2/24 | MARGINAL_ONLY |

- trim16 下 T6 的 sid17 256QAM「恢复」**消失**（T6 只剩 AM-SSB-WC / AM-SSB-SC 两命中）；
  trim32 下该帧又**重现**。即 3/24 对锚点位置敏感，是块边缘 circular wrap 造成的
  伪影/噪声，**不是稳定恢复**。
- 三种裁剪下最优均 **≤ 3/24**，且 trim16（精确排除 wrap 长度 16）直接回到 2/24。
  → **DC 跟踪路线彻底关闭**：公共参考残差跟踪器无稳定收益，继续堆叠同类 tracker
  价值很低。

见 `results_r1_trim16/fix4_trim16_verdict.json`（NO_IMPROVEMENT）与
`results_r1_trim32/fix4_trim32_verdict.json`（MARGINAL_ONLY）。

## 5. 修正参考均值（需求 2/4）

| 公共块 | 参考 | |mean| |
|---|---|---|
| settle / guard | 0 | 0 |
| train（16QAM） | 真实冻结序列 | **390.4** |
| tail（ZC root-3） | 真实冻结序列 | **64.0** |

旧块均值把 train 的 ~390 常数当成 DC，是 R1 的根本错误（已标 `superseded`，未删除）。

## 6. 交付物

```
results_r1/
  fix4_review_r1_verdict.json           判决（MARGINAL_ONLY）
  digital_counterexample_r1.tsv/.json   需求7 数字反例
  reestimate_fix2_target_{comparison,dc_trajectory}.tsv
  reestimate_old_rf_v1v2_{comparison,dc_trajectory}.tsv
  reestimate_fix4_r1_summary.json       两会话 8-tracker 聚合
  fix4_r1_candidate_summary.tsv         两会话逐 tracker 门/精度
  fix4_r1_confusion_matrix.tsv          最优 tracker + T0 的混淆
  fix4_r1_tensor_sha.tsv                最优 tracker 恢复张量 SHA
  observability_*.tsv / observability_fix4_r1_summary.json
results_r1_trim16/                       边界裁剪敏感性（edge-trim 16）
  reestimate_fix2_target_{comparison,dc_trajectory}.tsv
  reestimate_old_rf_v1v2_{comparison,dc_trajectory}.tsv
  reestimate_fix4_r1_summary.json + fix4_trim16_verdict.json  (NO_IMPROVEMENT)
results_r1_trim32/                       边界裁剪敏感性（edge-trim 32）
  ...同上 + fix4_trim32_verdict.json  (MARGINAL_ONLY)
docs/FIX4_REVIEW_R1_METHOD.md
docs/FIX4_REVIEW_R1_OBSERVABILITY.md
docs/FIX4_REVIEW_R1_RESULTS.md          （本文件）
docs/FIX4_REVIEW_R1_LIMITATIONS.md
```

## 7. 红线确认

- 不碰板、不操作 SDR、不发射、不训练、不改模型/公共协议/门限（0.100）。
- 24 分母不剔除；不跳过 M22；不把离线改进称为 RF_PASS。
- 旧 R1 工件全部保留，仅 `fix4_verdict.json` 加 `superseded` 字段。
