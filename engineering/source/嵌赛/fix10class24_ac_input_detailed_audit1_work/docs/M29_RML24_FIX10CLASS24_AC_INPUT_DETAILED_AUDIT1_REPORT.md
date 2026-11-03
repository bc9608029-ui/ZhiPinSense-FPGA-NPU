# M29 / fix10class24-ac-input-detailed-audit1 — 原始 RadioML(A) ↔ 真实 RF 恢复(C) 直接特征审查

**状态**: `M29-RML24-FIX10CLASS24-AC-INPUT-DETAILED-AUDIT1-COMPLETE`（纯离线；不含板端通道实测，不写 RF_PASS / PROJECT_COMPLETE / SMOKE_PASS / ROOT_CAUSE_PROVEN）

**红线（全部遵守）**: 未连接板端 / 未操作 SDR / 未重新采集 / 未训练 / 未改模型 / 生成器 / 预处理 / 恢复器 / 门限；**本任务是 A↔C 直接特征比较，全程未用 B↔C 残差代替**；`snr_db=nan` 未被解释为确定 SNR、也未被假设为高 SNR 或与某个 A SNR 强行匹配；A 与 C 非同段符号序列 → 无逐点相减 / 跨样本相关 / NMSE-as-channel-recovery；无张量写 `INSUFFICIENT_DATA`；不把「特征不同」写成「特征导致错误」。

---

## 0. 五个问题，先答（One-shot answers）

| # | 问题 | 答案（一句话 + 数字） |
|---|---|---|
| Q1 | C 与原始 RadioML 的主要差异（按证据强度排序）？ | **① 谱洁净度/噪声底（最大）② 连续 99% 占用带宽（小）③ 幅度/相位动态（小）**。三者全部 **跨全部 24 类通用**，无一是「类特定失真」。 |
| Q2 | 各自多大、哪些类、多少样本？ | ① C `peak_to_floor_db≈73 dB` = A 的 SNR20(59 dB)与 SNR30(79 dB)之间、C `flatness≈1.6e-5` 比 A SNR20(2.6e-4) 低约 16×（≈6σ，谱更尖锐/更干净）—— 即「C≈A 在 ~SNR25 的干净高信噪外观」，58/58 张量、全部 24 类一致；② C `bw99_cont≈0.128` vs A 高 SNR `0.126`（**第 73 百分位，分布内**）；③ `amp_roc_mean/phase_inc_std` 略抬升（最佳匹配层 85–92 百分位，分布内）。 |
| Q3 | 哪些差异解释当前误分类、哪些不解释？ | **没有**任何已测得的 A↔C 特征差异能把误分类的 64QAM/128QAM 与正确的 256QAM 分开：最大的三项差异（`bw99_cont`/`bw99`/`peak_to_floor_db`）在错误类与正确类的**排名完全相同**（`shared_with_control=1`），无一差异是误分类类特有。→ 崩塌**不是大尺度、类特定的 A 域特征偏移**，而是对「近分布内小摄动」的决策边界敏感。 |
| Q4 | 旧报告哪些度量/结论需更正？ | ① 旧 `bw99`/`bw20` 是「按功率降序累计的 bin 占比」，**不是**占用带宽；新的连续区间 `bw99_cont` 显示高 SNR 下 A↔C 带宽差**很小**（百分位 0.7），旧 bin 口径的「100 百分位」是定义伪影；② 三域审计用 **B↔C** 残差(nmse 0.0083)判 H3=首要触发，本 **A↔C 直接**审查证明 C 在高信噪等效处与 A **很接近**、且差异通用 —— 误分类是「最高阶 QAM 决策边界对近分布内残差最敏感」，不是「C 离 A 很远」。 |
| Q5 | 仍缺哪些证据？现有数据能/不能做什么？ | 缺：GMSK 仅 1 张 C 张量（full24_r1、正确），其 run2/3 崩塌无张量；QPSK/8PSK **0 张**；C 的 SNR=nan 只能逐 SNR 层对比、不能赋确定 SNR。**能做**：确认「无大尺度 A↔C 特征偏移 + 差异通用」这一负结论；**不能做**：对 GMSK/QPSK/8PSK 的类级特征归因。 |

**总体判定**: **A↔C 直接特征偏移是小尺度、跨类通用的（谱洁净度为主），且不能解释 64QAM/128QAM→256QAM 的确定性崩塌。** 崩塌定性为 **决策边界敏感度 × 近分布内残差结构**（最高阶 QAM 边界最密），而非大尺度域偏移。

---

## 1. 数据与方法

| 域 | 含义 | 来源 | 样本 |
|---|---|---|---|
| **A** | 原始 RadioML2018.01A（训练/评估分布） | `GOLD_XYZ_OSC.0001_1024.hdf5`（sha `e3dd0bef…`，size+mtime 复核一致） | **TEST 切分**，每类每 SNR∈{0,10,20,30} **N=100**，seed=20261019，**逐 SNR 层统计（不混 SNR）**；共 9600 帧，`hdf5_row_index` 冻结于 `a_reference_index.tsv` |
| **C** | 真实双 SDR 恢复的模型输入张量（生产 wide-linear 路径，全部诊断旁路） | full24 `wide_linear_model_input_f32le.bin`(9) + repeat3 `model_input_f32le.bin`(49) | **58 张量**，逐张 SHA/8192B/[2,1024]/有限性核验，枚举与 `matched_rf_samples.tsv` 一致 |

- 输入合同：模型输入 `X[row].T` → [2,1024]（row0=实部/row1=虚部）；特征分析载入同一复信号 `I+jQ = X[:,0]+1j*X[:,1]`（仅转置，无 DC/归一化）。
- 度量：50 个（7 个基线 + 幅度/DC、I/Q 联合、谱、时/相四组），单位 cycles/sample，公式见 `results/metric_definitions.md`。
- 比较方式：每个 C 值对其 A 类分布，**分 4 个 SNR 层各报百分位+z**，从不合并成一个均值；C 的 SNR 永不假设。
- 正确/错误：full24 取 `raw24_logits.tsv` `variant=wide_linear`；repeat3 取 `per_sample_results.tsv` 的 `raw24_pred`；correct = (pred == 真类)。
- 4 级证据：已直接测得 / 与错误相关 / 可能的解释 / 现有证据无法确定。

---

## 2. A↔C 主要差异（按证据强度排序，`ac_difference_by_class.tsv` / `correct_wrong_comparison.tsv`）

### ① 谱洁净度 / 噪声底 —— 最大且唯一的大尺度差异（通用）
| 度量 | C(64QAM) | A SNR20 | A SNR30 | 解读 |
|---|---|---|---|---|
| `peak_to_floor_db` | **73.1 dB** | 59.0 dB | 78.8 dB | C 的谱峰值/噪底 = A 的 SNR20~30 之间 |
| `flatness` | **1.6e-5** | 2.6e-4 | ~3e-6 | 比 A SNR20 低 ~16×（≈6σ，更尖锐/更干净） |

→ C 的谱「异常干净」，等效于 A 在 **~SNR 25** 的外观。这是 **58/58 张量、全部 24 类**都有的通用效应（wrong 的 64QAM/128QAM 与 correct 的 256QAM 的 `peak_to_floor_db` 都是 ~73 dB），因此**不是**误分类的类特定成因。

### ② 连续 99% 占用带宽（修正后的 `bw99_cont`）—— 小（分布内）
C `bw99_cont ≈ 0.1286` vs A SNR20/30 `0.1261`（**第 72–74 百分位**）；SNR10 `0.137`、SNR0 `0.98`（0 dB 噪声填满带）。→ C 的带宽完全落在 A 高 SNR 分布内，且「为什么 C 的 SNR0/10 对比巨大」只是噪声水平差异，不是信号结构差异。

### ③ 幅度/相位动态 —— 小（分布内）
`amp_roc_mean` C 0.111 vs A 0.105（86 百分位）、`phase_inc_std` C 0.356 vs A 0.332（89 百分位）。略抬升但都在 A 高 SNR 的 5–95% 内。

> 注：`correct_wrong_comparison.tsv` 里各焦点类的 top-1/2/3 全部是 `bw99_cont`/`bw99`/`peak_to_floor_db`，且 **`shared_with_control=1`** —— 即 wrong 类与 correct 类的最大差异是**同一个**通用谱洁净度效应。z 值绝对值（126 等）被 A 类内方差极小所放大，**不是可靠的“距离”尺度**；真实尺度应以**百分位**为准（在最佳匹配 SNR 层约 0.7–0.95；跨 4 个 SNR 层可到 0.00/1.00，因 C 的真实 SNR≈25 介于 A 各层之间）。

---

## 3. 焦点类逐类（`fig01..06` + `evidence_table.tsv`）

| 类 | C 样本 | 正确/错误 | 相对 256QAM（混淆类）的偏移 |
|---|---|---|---|
| **64QAM**(14) | 3(3 轮同源) | 0/3 全错 →16 | 最大差异与正确类 256QAM **完全相同**（`bw99_cont`/`bw99`/`peak_to_floor_db`，shared=1）；50 度量「更近自身类 vs 更近 256QAM」= 29/16/5，**无大尺度系统性偏向混淆类** |
| **128QAM**(15) | 3(3 轮同源) | 0/3 全错 →16 | 同 64QAM：最大差异与正确类完全相同（`bw99_cont`/`bw99`/`peak_to_floor_db`，shared=1），无类特定差异 |
| **OQPSK**(23) | 3 | 1 错(run1→16)/2 对 | n=3 轮内波动，无法归因于单一特征 |
| **GMSK**(22) | **1** | 1/1 对(full24_r1) | run2/3 崩塌(→16)**无张量**，`INSUFFICIENT_DATA` |
| 256QAM(16) | 3 | 3/3 对 | 对照：与 64QAM/128QAM **完全相同**的谱洁净度/带宽差异 |
| 4ASK/8ASK | 3/3 | 2/3、3/3 | 对照：同样通用差异 |
| AM-SSB-WC/SC | 4/3 | 3/4、3/3 | 对照：同样通用差异 |

**核心负结论（Q3 的证据）**: 错误类（64QAM/128QAM）与正确类（256QAM/4ASK/8ASK）的 A↔C 差异**排名逐项相同**——最大三项都是 `bw99_cont`/`bw99`/`peak_to_floor_db`（谱洁净度，`shared_with_control=1`），次之都是幅度/相位动态（`amp_roc_mean`/`phase_inc_std`/`ifr`）。即**没有任何一个 A↔C 特征差异是误分类类特有**的。对 64QAM 的 50 度量做「更靠近自身类 vs 更靠近 256QAM」检验：29 个更近自身、16 个更近 256QAM、5 个平手——**不存在把误分类样本大规模推向混淆类的单一特征**。因此「C 的 64QAM 特征已变成 256QAM」这一朴素假说**被证据否定**。

---

## 4. 更正旧报告的度量/结论

1. **旧 `bw99`/`bw20` 口径错误**：旧定义是按 FFT 功率降序累计到 99% 的 **bin 占比**，不是连续占用带宽。新 `bw99_cont`（围绕质心的最小对称区间含 99% 功率的**宽度**）显示高 SNR 下 A↔C 带宽差**很小**（百分位 0.7）。旧 bin 口径在 C 更干净谱上把「峰值/100 以上的 bin 多几个」读成「100 百分位带宽膨胀」，属定义伪影。
2. **「C 离 A 很远」的印象需更正**：三域审计（threedomain）用 B↔C 残差 nmse 0.0083 判 H3=首要触发，但那是对**发射前干净信号 B** 的残差。本 A↔C 直接比较证明：在 C 实际所处的等效高 SNR 处，C 与 A 的**特征级差异小且跨类通用**。所以误分类**不是**「大尺度 A 域偏移」，而是「最高阶 QAM 的决策边界对近分布内残差最敏感」，与 threedomain 的「两条硬解耦」（生成差/RF 残差大小都不预测误分类）在 **A↔C 直接层面**得到印证。

---

## 5. 证据分级（4 级，`evidence_table.tsv`）

| 层级 | 内容 |
|---|---|
| **已直接测得** | ① C 谱洁净度/噪声底（`peak_to_floor_db≈73 dB`、`flatness≈1.6e-5`）= A 的 SNR20~30 之间，58/58 通用；② 连续带宽/幅度/相位动态差异小（最佳匹配层百分位 0.7–0.95）；③ **「无类特定差异」负结论**：错误类(64QAM/128QAM)与正确类(256QAM/4ASK/8ASK)的 A↔C 差异排名逐项相同（top3 全为谱洁净度且 shared=1）。 |
| **与错误相关** | **（空）** —— 50 个度量中无一与 64QAM/128QAM→256QAM 崩塌相关（能分离对/错）。这一「无相关特征」本身是已直接测得的结论。 |
| **可能的解释** | 决策边界敏感度 × 近分布内残差（最高阶 QAM 最密）—— 由上述负结论 + threedomain 先验推断，**本任务未直接测量决策边界**，故降级为「可能的解释」而非已证明。 |
| **现有证据无法确定** | GMSK run2/3 崩塌（无张量）；QPSK/8PSK（0 张）；C 的确定 SNR（只能逐层对比，无法赋唯一值）。 |

---

## 6. 交付物（`fix10class24_ac_input_detailed_audit1_work/`）

```
results/
  input_inventory.tsv            # 58 C 张量身份(SHA/8192B/[2,1024]/有限性)+A/split 身份
  metric_definitions.md          # 50 度量公式/单位/每类样本数/相位低幅 dropout 规则
  a_reference_index.tsv          # 9600 A 参考帧 (class,snr,hdf5_row_index) 冻结
  a_reference_by_class_snr.tsv   # 24×4 层, 每度量 med/q05/q95
  per_sample_features.tsv        # 58 C 样本 × 50 度量 + 正确/门状态
  ac_difference_by_class.tsv     # 2900 (样本,度量) 行: C值+4 SNR 层 A med/q05/q95/百分位/z
  correct_wrong_comparison.tsv   # 450 (类,度量) 行: |z| 排名 + top3 + shared_with_control
  evidence_table.tsv             # 4 级证据
  summary.json                   # 判读 + 身份 + correct/wrong 计数
  figures/fig01..06.png          # 幅度CDF / IQ点云 / PSD叠 / 非圆度 / 自相关 / 相位增量
scripts/  ac_common.py + run_ac_audit.py + selftest_ac_audit.py   # 可复现
docs/     本报告
```

自测 `python -I scripts/selftest_ac_audit.py` → **8/8 PASS**（布局/尺寸、DC/缩放/IQ 相关检测、单音/双音/噪声 PSD 与带宽、旧 bin 口径 vs 连续区间可区分、缺失/NaN/Inf/身份检测、同源重复捕获不独立、无 B↔C 混入、基线 7 字段与 threedomain `audit_common.sample_stats` 一致）。

---

## 7. 结论与不写结论

**已确立（证据内）**：
1. A↔C 最大的、唯一大尺度的特征差异是**谱洁净度/噪声底**（C≈A 在 ~SNR25），且**跨全部 24 类通用**。
2. 其余差异（连续带宽、幅度/相位动态）都是**分布内小差异**（百分位 0.7–0.95）。
3. **50 个度量中无一能提供「误分类类特有」的 A↔C 差异**：错误类(64QAM/128QAM)与正确类(256QAM/4ASK/8ASK)的差异排名逐项相同，最大差异(谱洁净度)跨类通用 → 崩塌不是大尺度、类特定的 A 域特征偏移。
4. 旧 `bw99`/`bw20` bin 口径需更正；「C 离 A 很远」的印象被 A↔C 直接比较更正为「C 接近 A 高 SNR，差异通用而小」。

**明确不写**：`RF_PASS` / `SMOKE_PASS` / `PROJECT_COMPLETE` / `ROOT_CAUSE_PROVEN`（仅「证据支持」）；不把「无大尺度偏移」反推为「RF 链无问题」；不据此建议放宽 0.100 门或微调；不声称已定位单一成因。

**遗留待办（需后续/板端）**：GMSK run2/3、QPSK/8PSK 无张量；若需对「决策边界敏感度」直接验证，需导出误分类样本的 24 维 logits 边距（margin）沿类内分布 —— 属后续任务，本任务不覆盖。
