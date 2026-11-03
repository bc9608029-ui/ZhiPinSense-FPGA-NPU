# M29 / fix10class24-dualsdr-repeat3-audit1 — 三轮真实 RF 分类分析与纯净 NPU 对照

**状态**: `M29-RML24-FIX10CLASS24-DUALSDR-REPEAT3-AUDIT1-COMPLETE`（审计完成；不含板端通道实测，不写 RF_PASS / PROJECT_COMPLETE）
**后端**: 板端门内 = `BOARD_NPU_GATED`；门拒强制分类 = `HOST_BF16_FORCED`（Host 冻结 BF16 诊断旁路）
**合并标记**: `HYBRID_BOARD_GATED_PLUS_HOST_FORCED`（`production_gate_modified=0`, `diagnostic_gate_bypass=1`）
**红线**: 未连接板端、未操作 SDR、未重新采集、未训练、未改模型／恢复器／门限、未打包部署。

---

## 0. 五个问题，先答（One-shot answers）

**Q1 — 纯净 RadioML 板端 NPU 24/24 是否被独立复核？**
是。逐样本重算（非仅信 GATE_RESULT）：`clean_npu_audit.json` 记录 24 个 holdout 样本
`scored=24 / excluded=0 / correct=24 / repeat_deterministic=24 / nan_or_inf=0`，
`label_accuracy=1.0`，模型身份 `model_sha=c1781aec…` 与冻结 BF16 RAW 一致。
**结论：纯净（无 RF）板端 NPU 24/24 独立复核通过**，这是本任务的对照上界。

**Q2 — 三轮双 SDR 采集（每轮 24 样本）是否被核验？**
是。三轮 `dual_bf16_rms2048_run{1,2,3}` 每轮 24 个唯一 `source_index == {0,500,…,11500}`，
`raw24_class` 覆盖 0..23，`file_name`/`modulation` 与冻结 manifest 逐一对齐；
轮内与跨轮均无重复/缺失 source_index。每个门拒样本的 7 文件 dump 齐全且
`SHA256SUMS.txt` 逐字节重算一致（`failed_dump_audit.json`）。
**结论：72 个（round, source_index）键完整、身份一致。**

**Q3 — 门拒样本是否按当前生产恢复链做诊断强制分类（而非旧 scalar 工具）？**
是。49 个门拒样本（17+15+17）经 `replay_fix10class24_force_classify_wl`（wide-linear 修正版，
逐字复用生产 `iqrfrec::apply` 含 wide-linear 分支 + canonical 载荷训练）导出，再经
`icraft-run.exe --backends Host` 冻结 BF16 前向 **≥2 次**。关键自证：
- 自测 `apply_identical/payload_iq_identical/…/wide_linear_apply_identical=1`（与生产逐字节一致）；
- **wide-linear 复算 vs 板端 run.log 交叉核验 49/49 通过**（`scalar_validation_residual` /
  `validation_residual` / `image_ratio` / `enabled` 均 ≤1e-5，`wide_linear_crosscheck.json`）。
**结论：强制分类沿用的就是当前生产 wide-linear 恢复链，非旧 scalar 路径。**

**Q4 — 逐类三轮预测／正确数／过门数；区分“持续误分类”与“轮间波动”？**
见 §4。核心：**24 类中 2 类为持续误分类（0/3 全错且错到同一个 256QAM）**，8 类轮间波动，
14 类持续正确。误分类主导模式仍是“确定性同族升阶”（尤其 QAM 系 → 256QAM）。

**Q5 — 交付物是否落在指定目录？**
是。全部交付物在 `F:\嵌赛\fix10class24_dualsdr_repeat3_audit1_work\`（见 §6）。

---

## 1. 目标与范围

对已采集、已停机的三轮真实 RF 数据做**纯离线**审计与 Host 推理统计，回答：
纯净 NPU 是否 24/24、三轮采集是否完整、门拒样本经当前恢复链强制分类后逐类如何、哪些是持续误分类哪些是轮间波动。

**硬约束（全部遵守）**：
- 不连板、不碰 SDR、不重采、不训练、不改生产模型／恢复器／0.100 门限、不自动打包部署。
- 诊断旁路只解除残差门对载荷导出的阻止（`diagnostic_gate_bypass=1`），`production_gate_modified=0`。
- 使用转储保存的最终捕获，不按真实标签在 scalar / wide-linear / 不同分类窗之间择优。
- 不缩小 24 分母、不把未知预测当误分类、不删被拒样本。
- 未取得板端原始 SHA → 不声称两端哈希一致性核验（`archive_identity.json` 明示 `board_hash_comparison_claimed=false`）。

---

## 2. 基线身份

| 项 | 值 |
|---|---|
| 冻结 BF16 模型 JSON SHA | `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` |
| 冻结 BF16 模型 RAW SHA | `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` |
| 冻结 manifest | `clean24_smoke/route_d2_rf_manifest.tsv`（24 行 holdout，source_index 0..11500 step 500） |
| 冻结 baseline | `baselines/clean24_smoke_raw24_bf16_baseline.tsv` |
| 生产门限 | `kPayloadTrainingResidualMax = 0.100`（未改） |
| Host 推理引擎 | `icraft-run.exe --backends Host`（冻结 BF16，前向 ≥2 次） |

归档双端哈希：**未取得板端原始 SHA**，本机仅存截断前缀（dual `A1FE8B2B…`、clean `6B117052…`），
故本任务**不声称两端一致性核验完成**。

---

## 3. 三口径准确率总览

| 口径 | 数值 | 含义 |
|---|---|---|
| 纯净 NPU（对照上界） | **24/24 = 100.0%** | 无 RF 板端 NPU 独立复核 |
| 板端门内准确率 | **19/23 = 82.6%** | 仅 0.100 门通过样本（板端 NPU） |
| 板端端到端（门拒计 0） | 19/72 = 26.4% | 双 SDR 原始口径 |
| Host 强制分类（门拒子集） | 36/49 = 73.5% | Host BF16 诊断旁路 |
| **合并端到端（混合）** | **55/72 = 76.4%** | 门内板端 + 门拒 Host，`HYBRID_…` |

> 合并 76.4% 是**混合诊断口径**（门内=板端 NPU，门拒=Host BF16），不是单一板端测量；
> 不可当作板端 NPU 在真实 RF 上的准确率，也不可作为放宽 0.100 门的生产依据。

每轮明细（`per_round_summary.tsv`）：

| round | total | gated | gated_correct | forced | forced_correct | merged_correct | e2e |
|---|---|---|---|---|---|---|---|
| run1 | 24 | 7 | 7 | 17 | 12 | 19 | 0.7917 |
| run2 | 24 | 9 | 7 | 15 | 11 | 18 | 0.7500 |
| run3 | 24 | 7 | 5 | 17 | 13 | 18 | 0.7500 |

观察：run1 门内全对（7/7）；run2/run3 各在门内样本出现 2 个确定性误分类（64APSK→更高阶、GMSK→256QAM）。

---

## 4. 逐类三轮：持续误分类 vs 轮间波动

五类划分（互斥，见 `per_class_repeatability.tsv`）：

| 类别 | 类数 | 含义 |
|---|---|---|
| `ALWAYS_GATED_CORRECT` | 3 | 三轮全过门且全对（板上稳健） |
| `RECOVERABLE_CORRECT` | 11 | 三轮全对，但 ≥1 轮需 Host 强制（门拒但可恢复） |
| `ROUND_FLUCTUATION` | 8 | 部分轮对、部分轮错（轮间波动） |
| `PERSISTENT_MISCLASSIFIED_SAME_CLASS` | 2 | 0/3 全错且错到**同一个**错误类（确定性） |
| `PERSISTENT_MISCLASSIFIED_DIVERGENT` | 0 | 0/3 全错但错到不同类（本批无） |

### 4.1 持续误分类（确定性，2 类，0/3 全错）

| 类 | 三轮预测 | 说明 |
|---|---|---|
| 14 = 64QAM | **16, 16, 16** | 三轮全部升阶误判为 256QAM，且全部被 0.100 门拒（gate 0/3） |
| 15 = 128QAM | **16, 16, 16** | 三轮全部升阶误判为 256QAM，且全部被门拒（gate 0/3） |

这两类**既持续误分类、又从未过门**：即便经当前 wide-linear 恢复链强制分类，模型仍确定性地把
最高阶 QAM（64QAM/128QAM）判成 256QAM。与 full24-accuracy1 的“错在确定性同族升阶”结论一致。

### 4.2 轮间波动（8 类，1–2/3 对）

| 类 | 三轮预测 | 正确数 | 过门数 | 波动形态 |
|---|---|---|---|---|
| 1 = 4ASK | 2, 1, 1 | 2/3 | 0/3 | run1 误判 8ASK，run2/3 恢复 |
| 6 = 16PSK | 7, 6, 7 | 1/3 | 0/3 | 偶发升阶 32PSK |
| 10 = 64APSK | 10, 14, 16 | 1/3 | 3/3 | **始终过门**却漂移：64QAM→256QAM |
| 11 = 128APSK | 11, 15, 11 | 2/3 | 0/3 | run2 误判 128QAM |
| 17 = AM-SSB-WC | 17, 18, 17 | 2/3 | 0/3 | run2 与 SC 混淆 |
| 19 = AM-DSB-WC | 19, 19, 20 | 2/3 | 2/3 | run3 与 SC 混淆 |
| 22 = GMSK | 22, 16, 16 | 1/3 | 3/3 | **始终过门**却 run2/3 误判 256QAM |
| 23 = OQPSK | 16, 23, 23 | 2/3 | 0/3 | run1 误判 256QAM |

注意 64APSK 与 GMSK 的特殊性：二者 **三轮全过门（gate 3/3）** 却在后两轮出现确定性误分类，
说明**过门（RF_PRESERVES_IQ）不等于分类正确**——门内误分类是模型/恢复残差问题，非 RF 失真问题。

### 4.3 持续正确（14 类）

- `ALWAYS_GATED_CORRECT`（3）：QPSK(4)、8PSK(5)、32APSK(9) — 板上三轮稳定全对。
- `RECOVERABLE_CORRECT`（11）：OOK(0)、8ASK(2)、BPSK(3)、32PSK(7)、16APSK(8)、16QAM(12)、
  32QAM(13)、256QAM(16)、AM-SSB-SC(18)、AM-DSB-SC(20)、FM(21) — 三轮全对，但其中
  OOK/8ASK/BPSK/32PSK/16APSK/32QAM/256QAM/AM-SSB-SC 为 **NEVER_GATED**（三轮全被门拒，
  靠 Host 强制才恢复），16QAM/AM-DSB-SC/FM 为 MIXED_GATING。

---

## 5. 混淆矩阵要点（`confusion_counts.tsv`）

- 预测列 `pred_16`（256QAM）合计 **13**，是最大的“汇聚错误类”：64QAM(3) + 128QAM(3) +
  GMSK(2) + OQPSK(1) + 64APSK(1) + 256QAM 自身(3) 之外仍有 10 次**误吸**。
- 其余确定性混淆均为同族升阶/相邻类：16PSK→32PSK(2)、4ASK→8ASK(1)、128APSK→128QAM(1)、
  64APSK→64QAM(1)、AM-SSB-WC→SC(1)、AM-DSB-WC→SC(1)。
- **无跨族大翻转**：所有 17 个未决样本（`unresolved_samples.tsv`）的误判都在同调制族内或相邻高阶。

---

## 6. 交付物清单（`fix10class24_dualsdr_repeat3_audit1_work/`）

```
results/
  archive_identity.json          # 归档/模型身份 + 未取得板端哈希声明
  clean_npu_audit.json           # 纯净 NPU 24/24 独立复核
  failed_dump_audit.json         # 49 门拒 dump 7 文件 + SHA 逐字节核验
  inventory.tsv                  # 72 行（round, source_index）板端原始结果
  force_classify_wl_lines.txt    # 49 条 wide-linear 强制分类输出
  wide_linear_crosscheck.json    # 49/49 与板端 run.log WIDE_LINEAR 一致(≤1e-5)
  host_inference/
    per_sample_results.tsv       # 49 门拒 Host BF16 结果(≥2 前向)
    raw24_logits.tsv             # 24 维 logits
    summary.json
  forced_exports/<round>/<sid>/  # model_input_f32le.bin + forced_recovery.json + ...
  per_sample_results.tsv         # 72 合并行（层分辨预测/正确）
  per_round_summary.tsv
  per_class_repeatability.tsv    # 24 类三轮预测/正确/过门 + 五类划分
  confusion_counts.tsv           # 24×24 混淆矩阵
  unresolved_samples.tsv         # 17 个合并后仍未决样本
  summary.json
cpp/                             # replay_fix10class24_force_classify_wl.{hpp,cpp}
                                 #   + build/run 脚本（生产 wide-linear 恢复链逐字复现）
scripts/                         # audit_repeat3_archive.py / classify_repeat3_forced.py
                                 #   / merge_repeat3.py / crosscheck_wl.py
docs/                            # 本报告
```

---

## 7. 结论与不写结论

**已确立的事实**（证据内）：
1. 纯净 NPU 24/24，是真实 RF 上性能下降的对照上界。
2. 三轮 72 样本完整、身份一致；门内 23 + 门拒 49。
3. 门拒 49 经当前 wide-linear 恢复链 + Host BF16 强制分类，36/49 可判对（73.5%），
   且 wide-linear 复算与板端 run.log 49/49 一致 —— 证明诊断旁路没有改用旧 scalar 链。
4. 合并端到端 55/72 = 76.4%（混合口径）。
5. **持续误分类仅 2 类（64QAM/128QAM → 256QAM，0/3 全错且全被门拒）**；
   **轮间波动 8 类**；其中 64APSK、GMSK 三轮全过门却在后两轮确定性误分类，
   直接证明**过门 ≠ 分类正确**。

**明确不写**：`RF_PASS`、`SMOKE_PASS`、`PROJECT_COMPLETE`、`NEW_PRODUCTION_THRESHOLD`、
`MODEL_RF_ROBUSTNESS_SUFFICIENT` 等任何超出本次离线证据的结论；**不**把合并 76.4% 当作板端
真实 RF 准确率；**不**把 Host 强制分类当作板端 NPU 实测；**不**据门内误分类（64APSK/GMSK）
建议放宽 0.100 门——这些误分类样本本就过了门，放宽门无法修复，反而与 full24-accuracy1 的
`EVIDENCE_AGAINST_GATE_RELAXATION` 一致。

**遗留待办（需板端/后续）**：板端原始 SHA 缺失 → 未做两端哈希一致性核验；是否继续保留
0.100 门、是否对 QAM 系升阶做针对性重训/后处理，属后续决策，本任务不覆盖。
