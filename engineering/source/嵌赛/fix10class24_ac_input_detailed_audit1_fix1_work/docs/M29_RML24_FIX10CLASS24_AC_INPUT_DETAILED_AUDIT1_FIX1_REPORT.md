# M29 / fix10class24-ac-input-detailed-audit1-FIX1 — 更正报告（原始 RadioML(A) ↔ 真实 RF 恢复(C) 直接特征审查）

**状态**: `M29-RML24-FIX10CLASS24-AC-INPUT-DETAILED-AUDIT1-FIX1-COMPLETE`（纯离线；不含板端通道实测，不写 RF_PASS / PROJECT_COMPLETE / ROOT_CAUSE_PROVEN）

**与前版关系**: 本报告**取代** `M29_RML24_FIX10CLASS24_AC_INPUT_DETAILED_AUDIT1_REPORT.md`。独立复核 `REVIEW_2026-10-19.md` 判定前版 `NEEDS_CORRECTION`，列 7 项问题（4 项结论/统计、3 项实现/测试）。本版已修正代码、复算全部结果、撤回 6 条超出证据的结论。

**红线（全部遵守）**: 未连接板端 / 未操作 SDR / 未重新采集 / 未训练 / 未改模型·生成器·预处理·恢复器·0.100 门限；A↔C 直接比较，未用 B↔C 残差代替；`snr_db=nan` 未解释为确定 SNR；A/C 非同段符号序列 → 无逐点相减/跨样本相关/NMSE-as-channel-recovery；无张量写 `INSUFFICIENT_DATA`；不把「特征不同」写成「特征导致错误」。

---

## 0. 撤回结论一览（6 条）

| # | 撤回的旧结论 | 更正后 | 依据（复核问题） |
|---|---|---|---|
| R1 | 「50 个度量中无一与 64QAM/128QAM→256QAM 崩塌相关」 | 未做相关/区分检验；该「零相关」结论撤回。特征差异仅作描述，是否导致误分类 **UNKNOWN**。 | P1-1 |
| R2 | 「排除类特定域差异」「无一是误分类类特有」 | 集合交集/排名重合 ≠ 数值/方向/分布相同；不排除类特定差异。 | P1-1 |
| R3 | 「崩塌定性为决策边界敏感度 × 近分布内残差」 | 因果定性撤回；本审计不足以把误分类归因于任何单一特征。 | P1-1 |
| R4 | 「跨全部 24 类通用」「58/58、24 类一致」 | 实际 22 类（QPSK/8PSK 无张量）；repeat3 三轮回放为同一源重复捕获、非独立源；不作「跨类通用偏移」证明。 | P1-2/P1-3 |
| R5 | 「C≈A 在 ~SNR25 的干净高信噪外观」 | `peak_to_floor_db` 非 SNR；只能描述「该统计量介于 A 的 SNR20/30 参考值之间」，不赋 C 确定 SNR。 | P1-4 |
| R6 | 「其余差异都是分布内小差异（百分位 0.7–0.95）」 | 存在直接反例：128QAM `bw99_cont` pct=0.04、256QAM `amp_roc_mean` pct=0.98 → 差异**非均匀、非全部在分布内**。 | P1-2 |

---

## 1. 五个问题，先答（仅写证据能直接支持的）

| # | 问题 | 答案（描述性，不含因果/SNR 赋值） |
|---|---|---|
| Q1 | C 与原始 RadioML 的主要差异（按证据强度排序）？ | ① **谱洁净度/噪声底**（`peak_to_floor_db` 显著高于 A，`flatness` 显著低于 A）——跨 22 个有张量的类普遍存在；② **连续 99% 占用带宽**（`bw99_cont`）——**方向/幅度随类而异**（64QAM pct 0.73 / 128QAM pct 0.04 / 256QAM pct 0.68）；③ **幅度动态/相位增量**（`amp_roc_mean`/`phase_inc_std`）——同样随类而异。 |
| Q2 | 各自多大、哪些类、多少样本？ | 58 张量覆盖 **22 类**（QPSK/8PSK=0）。`peak_to_floor_db`: 22 类 C 中位数在各自 A SNR20 分布内 **pct 全为 1.00**（C≈73–105 dB vs A20 med≈58–70 dB）；`flatness`: 22 类 pct 全为 0.00（C 更尖锐）；`bw99_cont`: 64QAM 0.1286(pct 0.73)、128QAM 0.1200(**pct 0.04**)、256QAM 0.1285(pct 0.68)；`amp_roc_mean`: 64QAM 0.86、128QAM 0.43、256QAM **0.98**；`phase_inc_std`: 64QAM 0.89、128QAM 0.30、256QAM 0.57。完整逐样本见 `ac_difference_by_class.tsv` / `correct_wrong_comparison.tsv`。 |
| Q3 | 哪些差异解释当前误分类、哪些不解释？ | **无法确定**。本版**未做**相关/区分检验，因此不能声称「无一相关」也不能声称「某特征导致错误」。可确定的只有：谱洁净度/带宽/幅度动态等差异在误分类类(64QAM/128QAM)与正确类(256QAM/4ASK/8ASK)中都出现，量级相近，不能据此分离对/错。 |
| Q4 | 旧报告哪些度量/结论需更正？ | ① 旧 `bw99`/`bw20` 是「按功率降序累计的 bin 占比」，非占用带宽——已在新指标 `bw99_cont`（连续区间宽度）中分离，二者**不混用**；② 复自相关原实现先取实部，违反「相关幅度」定义——已改为 `abs(vdot)/energy`；③ `flatness_floor` 是数值常数、非信号特征，原参与 50 度量排名——已移出度量集并澄清文档；④ 「全部差异小且分布内」「跨类通用」「SNR≈25」「决策边界归因」「50 项零相关」全部撤回（见 §0）。 |
| Q5 | 仍缺哪些证据？现有数据能/不能做什么？ | 缺：GMSK 仅 1 张 C 张量（full24_r1），其 run2/3 崩塌无张量；QPSK/8PSK 0 张；C 的 SNR=nan 只能逐 SNR 层对比、不能赋确定 SNR；repeat3 三轮回放为同源重复、非独立源。**能做**：给出上述描述性差异与明确未知项；**不能做**：对任何特征作「导致误分类」的因果归因，也不足以决定生产补偿/门限/训练方案。 |

**总体判定（可保留）**: A 与这些诊断 C 张量在**部分谱、带宽和时域特征上存在可量化差异；差异随类别、参考 SNR 层而变化**。**尚未确定其中哪些因素导致当前误分类。**

---

## 2. 数据与方法（与前版一致，仅度量与结论层变更）

| 域 | 含义 | 来源 | 样本 |
|---|---|---|---|
| **A** | 原始 RadioML2018.01A | `GOLD_XYZ_OSC.0001_1024.hdf5`（sha `e3dd0bef…`，size+mtime 复核一致） | **TEST 切分**，每类每 SNR∈{0,10,20,30} **N=100**，seed=20261019；共 9600 帧，`a_reference_index.tsv` 冻结（与 FIX1 前逐字节一致） |
| **C** | 真实双 SDR 恢复的模型输入张量（生产 wide-linear，全诊断旁路） | full24 `wide_linear_model_input_f32le.bin`(9) + repeat3 `model_input_f32le.bin`(49) | **58 张量 / 22 类**，逐张 SHA/8192B/[2,1024]/有限性核验 |

- **度量数 49**（原 50：`flatness_floor` 移出——它是数值常数 `1e-12*total`、非信号特征）。
- 修正：复自相关幅度 `|sum conj(x[n])x[n-k]| / sum|x[n]|^2`（分子保持复数到 `abs`）。
- 比较方式：每个 C 值对其 A 类分布，**分 4 个 SNR 层各报百分位+z**，从不合并成一个均值；C 的 SNR 永不假设。

---

## 3. 已直接测得的差异（`evidence_table.tsv`，按证据强度）

| 度量 | 逐类 C 值 / A SNR20 中位数（pct=该 C 值在 A SNR20 分布中的百分位） |
|---|---|
| `peak_to_floor_db` | 4ASK C=87.7(pct 1.00)、8ASK 88.9(1.00)、64QAM 73.1(1.00)、128QAM 73.1(1.00)、256QAM 73.0(1.00)、AM-SSB-WC 105.0(1.00)、AM-SSB-SC 102.0(1.00)、GMSK 74.2(1.00)、OQPSK 75.9(1.00)（22 类全 1.00） |
| `flatness`（无 floor） | 22 类 C 中位数均显著低于 A20 中位数（pct 全 0.00，C 谱更尖锐） |
| `bw99_cont` | 64QAM 0.1286(pct **0.73**)、128QAM 0.1200(pct **0.04**)、256QAM 0.1285(pct 0.68) |
| `amp_roc_mean` | 64QAM 0.111(pct 0.86)、128QAM 0.104(pct 0.43)、256QAM 0.116(pct **0.98**) |
| `phase_inc_std` | 64QAM 0.356(pct 0.89)、128QAM 0.315(pct 0.30)、256QAM 0.334(pct 0.57) |

> 解读：谱洁净度是**大尺度且方向一致**的差异（22 类 C 都比 A SNR20 干净）；而带宽/幅度动态/相位增量的差异**方向与幅度随类而异**（128QAM `bw99_cont` 落在 A 分布的近底端 4%，256QAM `amp_roc_mean` 落在近顶端 98%）。这**否定**「全部差异都是分布内小差异、方向一致」的旧概括，但**不证明**其中任一特征导致误分类。

---

## 4. 证据分级（4 级，`evidence_table.tsv`）

| 层级 | 内容 |
|---|---|
| **已直接测得** | ① 谱洁净度/噪声底（22 类 C 的 `peak_to_floor_db`/`flatness` 均显著偏离 A SNR20）；② 连续带宽/幅度动态/相位增量的差异随类而异（§3 三行）；③ C 覆盖 22 类、repeat3 为同源重复捕获。 |
| **与错误相关** | **（无）** —— 未执行相关/类区分检验；旧「50 项零相关」撤回。特征差异仅描述，是否导致误分类 **UNKNOWN**。 |
| **可能的解释** | **（无断言）** —— 本审计的特征差异不足以把误分类归因于任何单一特征；如需检验模型敏感度须另设受控验证（超出本审计范围）。 |
| **现有证据无法确定** | GMSK run2/3 崩塌（仅 1 张、无 run2/3 张量）；QPSK/8PSK（0 张）；C 确定 SNR（`snr_db=nan`）；repeat3 同源重复（非独立源）。 |

---

## 5. 交付物（`fix10class24_ac_input_detailed_audit1_fix1_work/`）

```
results/
  input_inventory.tsv            # 58 C 张量身份 + A/split 身份
  metric_definitions.md          # 49 度量公式/单位/每类样本数（flatness 无 floor 已澄清）
  a_reference_index.tsv          # 9600 A 参考帧（与 FIX1 前逐字节一致）
  a_reference_by_class_snr.tsv   # 24×4 层, 每度量 med/q05/q95
  per_sample_features.tsv        # 58 C 样本 × 49 度量 + 正确/门状态
  ac_difference_by_class.tsv     # 2842 (样本,度量) 行: C值+4 SNR 层 A med/q05/q95/百分位/z
  correct_wrong_comparison.tsv   # 441 (类,度量) 行: best-matching-SNR 单层 |z| 排名 + 对/错 C 值分列 + n_unique_sources
  evidence_table.tsv             # 4 级证据（含撤回说明）
  summary.json                   # 判读=DESCRIPTIVE_ONLY + correlation_tested=false + retracted_conclusions
  figures/fig01..06.png          # 幅度CDF / IQ点云 / PSD叠 / 非圆度 / 自相关 / 相位增量
scripts/  ac_common.py + run_ac_audit.py + selftest_ac_audit.py   # 可复现（已修正）
docs/    本报告 + FIX1_BEFORE_AFTER.md + FIX1_VERIFICATION.md
```

自测 `python -I scripts/selftest_ac_audit.py` → **12/12 PASS**（原 8 + 复单音 lag1=0.9990234375 + 相位旋转不变性 + flatness_floor 非度量 + 严格 wrong-size）。

---

## 6. 结论与不写结论

**已确立（证据内）**：
1. A 与诊断 C 张量在**谱洁净度/噪声底、连续带宽、幅度动态、相位增量**上存在**可量化差异**。
2. 这些差异的**方向与幅度随类别、随参考 SNR 层而变化**——不是「全部小、方向一致、均在分布内」。
3. 58 张量覆盖 **22 类**；repeat3 为同源重复捕获，非独立源。

**明确不写**：`RF_PASS` / `PROJECT_COMPLETE` / `ROOT_CAUSE_PROVEN`；不把「特征不同」写成「特征导致错误」；不赋 C 确定 SNR；不据此建议放宽 0.100 门或微调；不声称已定位单一成因或已排除类特定差异。

**遗留待办（需后续/板端）**：GMSK run2/3、QPSK/8PSK 无张量；若需直接验证「决策边界敏感度」或任一特征与误分类的关联，须另设受控敏感性验证（导出误分类样本的 24 维 logits 边距沿类内分布），本审计不覆盖、不足以决定生产补偿/门限/训练方案。
