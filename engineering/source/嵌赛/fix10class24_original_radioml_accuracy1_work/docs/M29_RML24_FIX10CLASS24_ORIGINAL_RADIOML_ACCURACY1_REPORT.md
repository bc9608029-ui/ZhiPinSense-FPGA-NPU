# M29 / fix10class24-original-radioml-accuracy1 — 冻结 24 类模型在原始 RadioML 独立测试集上的准确率

**状态**: `M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-ACCURACY1-COMPLETE`
**后端**: `HOST_BF16`（主）+ `HOST_FP32_REFERENCE`（对照）——**均非板端 NPU**
**数据**: RadioML2018.01A **原始** HDF5 独立 TEST 划分（非 clean24/generated 数据）
**红线**: 完全离线；不连板、不碰 SDR、不训练、不改模型/预处理/门限；不写 RF_PASS / PROJECT_COMPLETE。

---

## 0. 先答（One-shot）

**Q1 — 测的是原始 RadioML 独立测试集吗？**
是。帧来自 `GOLD_XYZ_OSC.0001_1024.hdf5` 原始 X 数组（audit sha `e3dd0bef…`，
size 21449148312 + mtime_ns 匹配），行索引取自冻结 `rml24_split_indices.npz`
（sha `9a035841…`）的 `test_indices`。已核验 `test ∩ train = ∅`、`test ∩ validation = ∅`。
**未**使用 clean24_smoke、clean24_formal12000 或任何兼容生成数据；**未**把
source_index=0,500,… 当作测试索引。

**Q2 — 480 帧怎么选的？**
确定性分层抽样：SNR {0,10,20,30} dB × 24 类 × 5 帧 = 480，随机种子 `20261019`，
从 test split 每个 (class,snr) 层内 `np.random.default_rng(seed).permutation` 取前 5，
记录**原始 HDF5 行索引**。选择冻结于推理前（`frozen_test_selection.tsv`，
SHA `35b3a32c…`）。逐样本 HDF5 Y/Z 交叉核验通过（Y argmax == 选择类、Z == 选择 SNR）。

**Q3 — 预处理合同是什么？**
`X[row] [1024,2] float32` → `np.ascontiguousarray(X[row].T)` → `[2,1024]` fp32
（前 1024 实部、后 1024 虚部，小端）= 8192 字节。**无**去直流、归一化、重采样、
滤波、增广（`apply_channel_augmentation=false`）。与训练 `__getitem__` 逐字节一致，
见 `results/training_input_contract.json`。

**Q4 — 结果可否当“整个 RadioML 准确率”或板端实测？**
不可。480 帧结果只叫 **分层抽样测试准确率（stratified-sample test accuracy）**；
后端为 Host BF16/FP32 参考，**不是板端 NPU**。

**Q5 — 有无静默跳过推理失败？**
无。480/480 有限值、480/480 两次前向 argmax 一致、480/480 两次前向 logits 逐字节一致。

---

## 1. 基线身份

| 项 | 值 |
|---|---|
| HDF5 | `F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5` sha `e3dd0bef…` |
| 划分索引 | `rml24_split_indices.npz` sha `9a035841…`（seed 20261003，test=511680） |
| 冻结 BF16 模型 JSON | `28272abc…` |
| 冻结 BF16 模型 RAW | `c1781aec…` |
| FP32 checkpoint | `rml24_seed2027_best.pt` sha `96cd25f8…`（epoch 50） |
| Host 推理 | `icraft-run.exe --backends Host`（BF16，前向 ×2）/ torch FP32 |
| 输入 | `[1,2,1024]` fp32，8192 字节 |

---

## 2. 分层抽样测试准确率（总览）

| 后端 | 正确 | 总数 | 准确率 |
|---|---|---|---|
| **HOST_BF16（主）** | **419** | 480 | **87.29%** |
| HOST_FP32_REFERENCE（对照） | 424 | 480 | 88.33% |
| BF16↔FP32 argmax 分歧 | 11 | 480 | 全部发生在 0 dB |

> 口径：**STRATIFIED-SAMPLE TEST ACCURACY**，不是整个 RadioML 准确率，不是板端实测。

### 2.1 按 SNR（`accuracy_by_snr.tsv`）

| SNR dB | 帧数 | BF16 正确 | BF16 准确率 | FP32 准确率 |
|---|---|---|---|---|
| 0 | 120 | 68 | **56.67%** | 60.83% |
| 10 | 120 | 118 | 98.33% | 98.33% |
| 20 | 120 | 117 | 97.50% | 97.50% |
| 30 | 120 | 116 | 96.67% | 96.67% |
| ALL | 480 | 419 | 87.29% | 88.33% |

准确率几乎全部来自 0 dB 层（120 帧里只对 68 帧）；10/20/30 dB 均 ≥96.7%。
BF16 与 FP32 的唯一差异也集中在 0 dB（11 处分歧全在 0 dB，logit margin 极薄
0.02–0.27），这是 BF16 量化在极低 SNR 下翻转 argmax 的预期表现。

---

## 3. 逐类结果（BF16，每类 20 帧 = 4 SNR × 5）

| 全对 (20/20) | 类 |
|---|---|
| OOK、BPSK、FM、**GMSK**、**OQPSK** | 5 类 |

| 19/20 | 类 |
|---|---|
| QPSK、16APSK、256QAM、AM-DSB-WC | 4 类 |

| 15–18/20 | 类 |
|---|---|
| 4ASK(17)、8ASK(18)、8PSK(18)、16PSK(16)、32PSK(17)、32APSK(17)、64APSK(15)、128APSK(15)、16QAM(16)、32QAM(16)、**64QAM(15)**、**128QAM(15)**、AM-SSB-WC(16)、AM-SSB-SC(16)、AM-DSB-SC(16) | 15 类 |

完整 24 类见 `results/accuracy_by_class_snr.tsv` 与 `results/summary.json` 的 `per_class_bf16`。

---

## 4. 关键对照：RF 审计中的持续/波动误分类在此**不复发**

本任务与并行任务 `dualsdr-repeat3-audit1`（真实双 SDR RF 链）逐类对照：

| 类 | RF 链（repeat3，3 轮各 1 帧） | 原始 RadioML（本任务，20 帧） |
|---|---|---|
| 64QAM(14) | **0/3 全错→256QAM**（持续，0/3 过门） | **15/20 对**；错误分散于 0 dB：→16APSK/128APSK/16QAM/128QAM/256QAM 各 1 |
| 128QAM(15) | **0/3 全错→256QAM**（持续，0/3 过门） | **15/20 对**；错误分散：→32APSK(1)/16QAM(3)/256QAM(1) |
| GMSK(22) | 1/3，后两轮→256QAM（波动，3/3 过门） | **20/20 全对** |
| OQPSK(23) | 2/3，run1→256QAM（波动） | **20/20 全对** |

**结论**：RF 链中观察到的“64QAM/128QAM 确定性升阶到 256QAM”与“GMSK/OQPSK 波动”在
**原始训练域数据上均不复发**。原始数据上 GMSK/OQPSK 100% 正确；64QAM/128QAM 的剩余
错误全部集中在 0 dB 且**分散**到相邻/同族类，而非 RF 链那种确定性 256QAM 汇聚。
这直接支持“这些特定误分类由真实 RF/恢复链（B→C）引入，而非模型对该调制族的固有
缺陷”——是并行三域审查（A↔B↔C）的关键输入。

---

## 5. BF16↔FP32 分歧（`bf16_fp32_disagreements.tsv`）

11 处分歧，全部在 SNR=0 dB：
- 6 处 FP32 对而 BF16 错、4 处两者皆错、1 处 BF16 对而 FP32 错。
- 净差 = 6 − 1 = 5 帧，正好解释 419 vs 424。
- 分歧样本的 margin 均在 0.02–0.27（BF16）量级，属极低 SNR 下 logit 紧邻类的量化翻转。

无任何 10/20/30 dB 分歧，说明 BF16 在高 SNR 层与 FP32 逐帧一致。

---

## 6. 交付物清单（`fix10class24_original_radioml_accuracy1_work/`）

```
results/
  dataset_identity.json            # HDF5/划分/checkpoint/模型 SHA 与身份
  training_input_contract.json     # [1024,2]->[2,1024] 预处理合同（零处理）
  frozen_test_selection.tsv(+sha)  # 480 帧冻结选择（seed 20261019，含原始行索引）
  host_inference/
    per_sample_results.tsv         # 480 BF16 结果（2 前向）
    raw24_logits.tsv               # 24 维 BF16 logits
    fp32_per_sample.tsv            # 480 FP32 结果
    fp32_logits.tsv                # 24 维 FP32 logits
    summary.json / fp32_summary.json
    partial.jsonl                  # 可恢复中间态
  accuracy_by_snr.tsv              # 4 SNR + ALL
  accuracy_by_class_snr.tsv        # 24 类 × 4 SNR
  confusion_counts.tsv             # 24×24（BF16）
  bf16_fp32_disagreements.tsv      # 11 处分歧
  summary.json                     # 任务总摘要（含状态）
scripts/                           # phase_ab_prepare / phase_c_infer /
                                   #   phase_d_fp32_reference / phase_d_aggregate
docs/                              # 本报告
```

---

## 7. 结论与不写结论

**已确立（证据内）**：
1. 冻结 BF16 模型在原始 RadioML 独立测试集上的**分层抽样测试准确率 = 419/480 =
   87.29%**（FP32 对照 424/480 = 88.33%）。
2. 误差几乎全部集中在 0 dB（56.67%），10/20/30 dB 均 ≥96.7%。
3. BF16↔FP32 分歧 11 处、全部在 0 dB，属极低 SNR 量化翻转；高 SNR 层逐帧一致。
4. **GMSK、OQPSK 原始数据 20/20；64QAM/128QAM 的 RF 链“→256QAM 汇聚”在原始数据上
   不复发**（15/20 且错误分散在 0 dB）。

**明确不写**：`RF_PASS`、`PROJECT_COMPLETE`、`MODEL_RF_ROBUSTNESS_SUFFICIENT`；
不把 87.29% 称作“整个 RadioML 准确率”或“板端 NPU 准确率”；不据本结果修改 0.100 门
或任何生产配置；不把 Host 结果冒充板端实测。

**给并行三域审查的输入**：本任务的 `dataset_identity.json`（HDF5/划分/checkpoint 身份）
与 `training_input_contract.json`（[1024,2]→[2,1024] 零处理合同）可直接复用，且
本报告的 §4 提供了“原始训练域上 RF 链特定误分类不复发”的量化证据。
