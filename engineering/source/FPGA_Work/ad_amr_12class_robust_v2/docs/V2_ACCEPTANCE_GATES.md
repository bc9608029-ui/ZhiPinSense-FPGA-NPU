# V2 验收门禁（V2_ACCEPTANCE_GATES）

> 任务：十二类调制识别模型 V2 鲁棒性改进 · 阶段十三（候选门限）
> 生成：2026-10-07。新门限在训练前冻结，并分层：硬门 + 性能门。
> 门限冻结后不得根据最终测试结果反复修改。

## 0. 旧门审计（规格 §十三「先审计旧的 all_focus_ood_improved 门是否过度严格」）

**旧门 `all_focus_ood_improved`（data-v4 鲁棒工程）**：要求每个 focus OOD 子域（cfo_strong / multipath / multi_impairment）都**逐项**相对基线改善。

**审计结论：过度严格，V2 弃用**，理由：

1. OOD 子域难度天然不均，且受样本量与域内 SNR 分布影响大；要求「每个子域都严格变好」等价于惩罚任何不均衡的改进，会系统性地淘汰「总体显著变好、个别子域持平」的合理候选。
2. V1 三个失败域 drop 都很大（cfo_strong 0.127/0.122，multipath 0.121/0.115，multi_impairment 0.133/0.131，均 > 0.08），说明 V1 在这些域本就没有余地；逐项硬提升门会阻断任何单域优先改进。
3. 单 seed 波动即可让某个子域在 ±1% 内翻转结论，逐项「全部改善」判定缺乏统计稳健性。

**替代原则**：性能门用「ID 主指标非回归 + 跨生成器/真实 RF 总体指标改善 + 易混类别不严重退化 + min-class 不跌破下限 + 多 seed 均值与置信区间支持改进」，**不要求每个 OOD 子域逐项严格提高**（规格 §十三原文）。

## 1. 硬门（必须全部通过，缺一即 NO_GO）

| # | 硬门 | 判定 |
|---|------|------|
| H1 | 标签、输入、输出契约不变 | 12 类权威顺序 + `iq[1,2,1024]` fp32 RMS1.0 + 12 logits，从 V1 契约读取比对 |
| H2 | 训练/验证/测试无泄漏 | `check_data_leakage.py` 通过；同 session 不跨 split |
| H3 | 无 NaN/Inf | 训练 loss、权重、ONNX 输出、NPU logits 全程 finite |
| H4 | ONNX 导出成功 | opset 17，算子集 ⊆ V1 已证集（Add/Conv/Gemm/ReduceMean/Relu 等 iCraft 可支持集），`unexpected_operators == 0` |
| H5 | iCraft 编译成功 | ZG330 编译通过，无 unsupported op |
| H6 | NPU 运行纪律正确 | 沿用 npu_rearm 纪律（Device 一次 + Session 持久 + 每帧 reset），无帧偏移 |
| H7 | 部署黄金集匹配率 ≥ 0.90 | 不低于 V1 既有硬门（V1 `match_rate≥0.90`），逐类匹配可查 |
| H8 | 真实板端无帧偏移 | delay_shift 检测不触发（`delay_detected=false`，参照 Gate 7 门禁） |
| H9 | 延迟与模型大小在硬件预算内 | Host 延迟、NPU 延迟（mean/p99/max）、RAW 大小、内存不超预算（沿用 V1 部署契约预算） |

## 2. 性能门（分层，非逐域严格提高）

| # | 性能门 | 判定（基于 validation + 多 seed，绝不 test/final holdout） |
|---|--------|--------------------------------------------------------------|
| P1 | ID 主指标非回归 | `mean_full_macro_f1` / `mean_full_accuracy` 不低于 V1（0.7366 / 0.7367）减容差 |
| P2 | 真实 RF 或跨生成器总体改善 | 同轴真实 RF 或独立生成器 shared-class macro-F1 总体有明确改善（多 seed CI 下限 > V1） |
| P3 | 易混类别不严重退化 | 16QAM/64QAM（及 4ASK/8PSK 等易混对）precision/recall 不出现严重退化（阈值见 §3） |
| P4 | min-class 不跌破下限 | `each_seed_min_rated_class` 不低于预先冻结下限（见 §3） |
| P5 | 多 seed 均值 + CI 支持改进 | 至少 3 formal seed（2026/2027/2028），均值 + bootstrap 95% CI 支持改进结论 |

## 3. 冻结的非回归容差（训练前定，之后不改）

容差依据样本量、bootstrap 置信区间或重复 seed 方差制定，不得训练结束后临时改。

- **ID 主指标容差**：`Δ mean_full_macro_f1 ≥ -0.010`（即不得比 V1 低超过 1 个百分点）。
- **min-class 下限**：`each_seed_min_rated_class_accuracy ≥ 0.75`（沿用 V1 data-v3 的 `each_seed_min_rated_class_accuracy: 0.75`；12 类新 ASK 类另设 `each_seed_new_ask_rated_accuracy ≥ 0.75`）。
- **易混类别退化上限**：16QAM/64QAM 的 recall 较 V1 不下降超过 0.05（绝对值）。
- **总体改善判定**：目标域指标（真实 RF 或独立生成器）的 bootstrap 95% CI **下限 > V1 同指标点估计**，才判为「明确改善」。
- **OOD 单独评价**：OOD 域仍单独报告 drop，**不因合成增强提高就改写为 PASS**（规格 §二十）；V2 不设「OOD 必须全部 PASS」的硬门，只记录 drop 改善方向。

## 4. 状态红线

- 离线 pilot 前最高 = `READY-FOR-AUTODL-12CLASS-V2-PILOT`；无真实 RF = `NEEDS-REAL-RF-DATA`；导入未上板 = `READY-FOR-12CLASS-V2-NPU-HARDWARE-TEST`。
- 未经真实 NPU + 真实 RF 验证，绝不写 `FINAL_MODEL_PASS / ROBUST_MODEL_PASS / REAL_RF_PASS / OOD_PASS / PROJECT_COMPLETE`。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
