# M29 / fix10class24-threedomain-pairwise-audit1 — 原始RadioML／兼容生成信号／五轮真实RF 三域两两差异审查

**状态**: `M29-RML24-FIX10CLASS24-THREEDOMAIN-PAIRWISE-AUDIT1-COMPLETE`（纯离线审计；不含板端通道实测，不写 RF_PASS / PROJECT_COMPLETE）
**红线（全部遵守）**: 未连接板端、未操作 SDR、未重新采集、未训练、未改模型／生成器／预处理／恢复器／门限、未按真实标签择优、未把 `snr_db=nan` 解释为确定 SNR、未自动打包部署。

---

## 0. 五个假设，先答（One-shot answers）

| 假设 | 判定 | 一句话依据 |
|---|---|---|
| H1 生成配置差异（A↔B） | **次要贡献** | 聚合 RMS/bw 差很小（0.45% RMS / 0.29% bw99），但脉冲谱形确有差异（谱平坦度比 ~2500×）；最大 RMS/DC 离群类 AM-SSB 在 RF 下**仍分类正确**，说明生成差不是误分类主因 |
| H2 数字处理/恢复偏置（B_source↔B_d2） | **排除（可忽略）** | D2 数字链几乎无损，median nmse 1.8e-4、corr 0.99991 |
| H3 RF 摄动（B_d2↔C） | **首要触发** | 是唯一把「纯净 holdout 24/24」拉到「RF 合并 55/72=76.4%」的那条腿；残差类相关（5e-5…2.0%） |
| H4 多因素 | **采纳（本结论）** | H3 触发 × H1 背景，二者共同塑造「64QAM/128QAM→256QAM 确定性崩塌」这类失败形态 |
| H5 数据不足 | **拒绝** | 58 个恢复张量 + 72 样本分类 + 480 帧原始域基线（并行任务2），证据充分 |

**总体判定**: **H4（多因素），排序 H3 > H1 >> H2；H5 拒绝。**

---

## 1. 目标与域分解

对已采集、已停机的数据做**纯离线**三域两两差异审查，判断五个假设哪个被证据支持。

| 域 | 含义 | 来源 | 采样 |
|---|---|---|---|
| **A** | 原始 RadioML2018.01A（训练/评估分布） | `GOLD_XYZ_OSC.0001_1024.hdf5`（21.4 GiB，sha `e3dd0bef…`） | 每类 400 帧 @ SNR≥20，seed 20261019，确定性 |
| **B_source** | 兼容生成信号（D2 之前） | `clean24_formal12000.hdf5`（sha `8b3efe0b…` 复算一致） | 每类 500 帧（全部 k=0..499） |
| **B_d2** | B_source 经数字 D2（重采样→量化 ci16→恢复，**无 RF**） | `clean24_smoke/recovered_tensor_*.f32`（24 文件，sha 与 manifest 24/24 一致） | 每类 1 帧（holdout k=0） |
| **C** | B 经五轮真实双 SDR TX/RX + 生产 wide-linear 恢复 | full24 `wide_linear_model_input` + repeat3 `model_input` | **58 个恢复张量**（full24_r1=9，run1/2/3=17/15/17） |

三腿分解：**A↔B_source** = 生成配置（H1）；**B_source↔B_d2** = 数字 D2（H2）；**B_d2↔C** = RF 摄动（H3）。这一分解直接对应任务的五个假设判定。

---

## 2. 数据可用性（`data_availability.tsv`）

- A：每类 400 帧（SNR≥20 采样，非冻结测试切分、非全量普查）。
- B_source：每类 500 帧。
- B_d2：每类 1 帧（holdout k=0）。
- C：**58 个恢复张量**，覆盖 round 分布见 `summary.json.domain_counts.C_by_round`。
  - **关键缺口**：rms2048（round 2）磁盘上**无**恢复张量 dump；门内（过门）样本按构造无恢复张量（板上已分类）。故 C 过度代表**门拒**帧。

> `snr_db=nan` 不解释为确定 SNR。C 张量来自已保存的 forced-export `model_input` 文件（只读）。

---

## 3. 两两差异（`pairwise_metrics.tsv` / `summary.json.leg_distances`）

### 3.1 A↔B_source —— 生成配置差（H1）
| 指标 | 值 |
|---|---|
| 平均相对 RMS 差 | **0.00446（0.45%）** |
| 最大相对 RMS 差 | 0.0464（AM-SSB-SC 4.64%） |
| 平均 \|DC\| 差 | 0.0276 |
| 最大 \|DC\| 差 | **0.411（AM-SSB-SC）** |
| 平均 bw99 差 | 0.00287 |
| 谱平坦度比（A→B） | **~2500×**（多数数字类从 ~8.5e-5 → ~3e-8） |

**要点**：聚合 RMS/带宽差很小（生成器按每类 TARGET_RMS 刻意对齐了 RadioML），但**脉冲谱形确有真实差异**——谱平坦度比 ~2500×，与已知口径一致（profile yaml `root-raised-cosine alpha=0.35`（engineering_inferred）vs 生成器 `windowed-sinc fc=0.059`）。此外 GMSK/OQPSK 的 PAPR/带宽明显不同（GMSK PAPR 差 1.66 dB、OQPSK bw99 差 −1.45%）。

### 3.2 B_source↔B_d2 —— 数字 D2（H2）
median **corr 0.99991**、median **nmse 1.79e-4**（max 6.96e-4）。数字 D2 链在张量域**近乎无损**，排除为误分类主因。

### 3.3 B_d2↔C —— RF 摄动（H3）
median **corr 0.99586**、median **nmse 0.00826**、max nmse 0.02045、median gain_mag 0.998。RF+恢复残差在模型输入处**类相关**，跨度 3 个数量级：

| 类 | median nmse | 类 | median nmse |
|---|---|---|---|
| AM-SSB-WC | 5e-5 | OQPSK | 0.0115 |
| AM-SSB-SC | 1.2e-4 | 64QAM | 0.0121 |
| 8ASK | 1.6e-3 | FM | 0.0126 |
| 4ASK | 2.5e-3 | **GMSK** | **0.0205** |
| OOK | 3.9e-3 | 128QAM | 0.0088 |
| BPSK | 7.0e-3 | 256QAM | 0.0103 |

### 3.4 A↔C —— 端到端模型输入偏移
分布级比较见 `pairwise_metrics.tsv`（`A<->C` 行），受 C 每类样本数限制；结论与 3.1+3.3 复合一致。

---

## 4. 焦点类解耦（`summary.json.focus_class_decoupling`）—— 关键证据

| 类 | 生成 RMS 差 | 生成 DC 差 | 生成 PAPR 差(dB) | RF nmse | RF 分类类别（repeat3） |
|---|---|---|---|---|---|
| AM-SSB-SC | **4.64%** | **0.411** | 0.38 | **0.00012** | RECOVERABLE_CORRECT |
| AM-SSB-WC | 1.70% | 0.175 | 0.36 | **0.00005** | ROUND_FLUCTUATION |
| GMSK | 0.26% | 0.021 | **1.66** | **0.0205** | ROUND_FLUCTUATION（始终过门） |
| OQPSK | 0.25% | 0.012 | **1.24** | 0.0115 | ROUND_FLUCTUATION |
| 64QAM | 0.43% | 0.001 | 0.02 | 0.0121 | **PERSISTENT_MISCLASSIFIED（→256QAM）** |
| 128QAM | 0.22% | 0.003 | 0.10 | 0.0088 | **PERSISTENT_MISCLASSIFIED（→256QAM）** |
| 256QAM | 0.17% | 0.002 | 0.08 | 0.0103 | RECOVERABLE_CORRECT |

**两条硬解耦**（直接否定「生成差越大越错」和「RF 残差越大越错」这两个朴素因果）：

1. **生成差大小不预测误分类**：生成 RMS/DC 差**最大**的 AM-SSB-WC/SC 在 RF 下**仍分类正确**；而生成差**最小**的 64QAM/128QAM 却**确定性崩塌**。
2. **RF 残差大小不预测误分类**：RF 残差**最大**的 GMSK（2.0%）过门且大体可恢复；RF 残差相近的 64QAM（1.2%）崩塌、256QAM（1.0%）却正确。注意 256QAM 自身正确、64QAM/128QAM 被「吸入」256QAM，边界**不对称**——与 repeat3 混淆矩阵 `pred_16(256QAM)` 是最大汇聚错误类（13 次）一致。

**结论**：64QAM/128QAM→256QAM 的确定性崩塌是**模型决策边界敏感度 × RF 残差结构**的相互作用（最高阶 QAM 决策边界最密），而非大尺度域偏移。

---

## 5. 并行任务2交叉引用（原始 RadioML 独立测试集准确率）

并行任务 `fix10class24-original-radioml-accuracy1` 的终态（同模型、原始训练域）：

- HOST_BF16 **419/480 = 87.29%**，FP32 424/480 = 88.33%；误差几乎全部在 0 dB 层。
- **GMSK 20/20、OQPSK 20/20**；64QAM 15/20、128QAM 15/20，且错误**全部集中在 0 dB 且分散**到相邻/同族类，**不是** 256QAM 汇聚。
- → RF 链的「64QAM/128QAM→256QAM 持续误分类」与「GMSK/OQPSK 波动」在**原始训练域数据上均不复发**，证明这些误分类**由 B→C（RF/恢复）引入**，而非模型对调制族的固有缺陷。

---

## 6. 交付物（`fix10class24_threedomain_pairwise_audit1_work/`）

```
results/
  provenance.json            # 域身份 + 冻结模型/合同 + 25/25 SHA 复算一致
  data_availability.tsv      # 各域各轮可用性
  preprocessing_contract.tsv # A/B_source/B_d2/C 四阶段处理合同
  pairwise_metrics.tsv       # A<->B / B_source<->B_d2 / B_d2<->C / A<->C 全量两两指标
  matched_rf_samples.tsv     # 58 个 C 样本逐一匹配 B_d2 参考 + 复算 corr/nmse/gain/phase + 记录指标
  findings.tsv               # F1..F7 证据行（含强度标签）
  limitations.md             # 局限
  summary.json               # 判读 + 假设排序 + 焦点类解耦
  figures/                   # rms_dc_A_vs_B.png / psd_B_vs_Bd2_vs_C.png / B_d2_vs_C_nmse_corr.png
scripts/                     # audit_common.py + run_audit.py（可复现，A/B 采样已缓存）
docs/                        # 本报告
```

---

## 7. 结论与不写结论

**已确立（证据内）**：
1. 数字 D2 链（H2）近乎无损（nmse 1.8e-4），排除。
2. 生成配置差（H1）聚合小（0.45% RMS）但谱形有真实差异（平坦度比 ~2500×；GMSK/OQPSK PAPR/带宽、AM-SSB RMS/DC 离群）；这些离群类在 RF 下仍分类正确 → H1 不是误分类主因。
3. RF 摄动（H3）是唯一把「纯净 24/24」拉到「RF 76.4%」的腿，且残差类相关 → H3 是**首要触发**。
4. 64QAM/128QAM→256QAM 崩塌是**模型敏感度 × RF 残差**相互作用（最高阶 QAM 最密边界），非大尺度域偏移；原始域任务2已证明这些类只在 0 dB 分散出错。
5. H5 数据不足拒绝。

**明确不写**：`RF_PASS`、`SMOKE_PASS`、`PROJECT_COMPLETE`、`MODEL_RF_ROBUSTNESS_SUFFICIENT`、`NEW_PRODUCTION_THRESHOLD`、`ROOT_CAUSE_PROVEN`（仅「证据支持」，不称已证明）；不把 Host 参考当板端实测；不据本审查建议放宽 0.100 门——门内误分类（64APSK/GMSK）本已过门，放宽门无法修复。

**遗留待办（需后续/板端）**：rms2048 轮缺恢复张量 dump；是否对最高阶 QAM 的 RF 残差做针对性后处理/重训，属后续决策，本任务不覆盖。
