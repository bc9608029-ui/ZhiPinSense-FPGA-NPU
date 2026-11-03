# Stage B — RadioML 合成 QPSK 与真实外部 QPSK 同域对比

**绑定指令** 39e5 · **日期** 2026-10-11 · **输出目录** `diagnostic_qpsk_39e5_stage_abc/`
**约束**：同一 FP32 ONNX、同一 24 类标签序、**零权重改动**、零预处理改动。

---

## 0. 一句话结论

两域在**一阶统计上几乎相同**（complex RMS 差 2.4%、四象限各 25%、DC≈0、I/Q 相关≈0），
但在**谱结构与脉冲成形**上存在**系统性差异**：真实 QPSK 带宽更宽（−3 dB 8.0 vs 6.75 kHz，
−20 dB 18.9 vs 16.25 kHz）、包络平方谱在 **16 kHz 处有一条干净的单根符号率谱线**
（prominence 2.79），而 RadioML QPSK 的包络平方谱是**抹平的**（prominence 1.01、无干净谱线）、
PAPR 更高（4.39 vs 3.57 dB）。

这一结构差异穿过**无归一化层**的 ADAMRV11Net，使真实信号的逐层激活 RMS 系统性放大约
**1.26×（均值，深残差块最高 1.85×）**，最终把真实 QPSK 的 logits 推离 QPSK 区、折叠进
16/64/128/256-QAM。**模型域泛化失败由此量化定位**。

---

## 1. 样本与身份

| 项 | RadioML 合成域 | 真实捕获域 |
|---|---|---|
| 来源 | RadioML2018.01A test split, class=QPSK (label 4), SNR=30 dB | 78 帧 `live_rx_tensor_*.f32`（外部射频 QPSK） |
| 数量（统计 / logits） | 300 / 200 | 78 / 78 |
| 输入张量 | `[2,1024]` fp32 planar（I/Q），`raw.T`，**无归一化** | 同（模型最终输入，逐字节） |
| FP32 ONNX SHA | `976618a1…`（两者共用） | 同 |
| 每帧 SHA256 | `radioml_indices_used`（HDF5 索引） | `input_sha256`（78 个，逐字节） |

---

## 2. 一阶统计对比（每域聚合 mean±std）

| 指标 | RadioML QPSK@30dB | 真实 QPSK | 差异判定 |
|---|---|---|---|
| complex RMS | 1.00244 | 1.02670 | **+2.4%**（非主因） |
| I RMS / Q RMS | 0.70775 / 0.70906 | 0.72787 / 0.72359 | +2.8% / +2.0% |
| peak | （见 JSON） | （见 JSON） | 略高 |
| **PAPR (dB)** | **4.387** | **3.569** | **−0.82 dB（脉冲成形不同）** |
| DC I mean / Q mean | −0.0012 / +0.0010 | +0.0044 / +0.0070 | 均≈0（无显著 DC 偏置） |
| I/Q 相关系数 | −0.0037 | −0.0146 | 均≈0（正交完好） |
| 四象限占用 | 0.248/0.252/0.249/0.250 | 0.247/0.254/0.246/0.252 | **各≈25%（确为 QPSK）** |
| 相邻样本相位增量 (deg) | −0.068 | +0.115 | 均≈0 |
| 瞬时频率 (Hz) | −24.3（mean） | +40.9（mean） | 均≈0（无强瞬时偏频） |
| CFO（4 次方谱估计，Hz） | −13 | −188 | 真实域有轻微 CFO（与独立复核 −250 Hz 量级一致） |

**判读**：真实信号在幅度/相位/正交/象限层面**就是干净的 QPSK**，没有任何“其实不是 QPSK”的
信号学证据；它与 RadioML QPSK 的差异不在这些一阶量，而在下面的谱结构。

> **勘误补充（DC）**：上表“DC I/Q mean”是**跨样本平均**（≈0，说明无系统性 DC 偏置）。但**每样本
> |DC mean| 幅值**不可忽略：RadioML = **0.086 ± 0.046**、真实 = **0.072 ± 0.045**（均 ~7–9% RMS，
> 两域相近）。Stage C 进一步证：去除该每样本 DC 使模型对**自身训练域** golden 从 200/200 崩到
> 111/200（66 帧翻成 32PSK）——无归一化层模型把绝对 DC 电平当成分类特征，是合成域过拟合印记。

---

## 3. 谱结构对比（关键差异）

| 指标 | RadioML QPSK | 真实 QPSK | 含义 |
|---|---|---|---|
| PSD −3 dB 带宽 | **6.75 kHz** | **8.00 kHz** | 真实域宽 **+18.5%** |
| PSD −20 dB 带宽 | 16.25 kHz | 18.875 kHz | 真实域宽 **+16.2%** |
| OBW 90/95/99% (Hz) | 12500/13750/16125 | 14875/16375/18875 | 真实域整体右移更宽 |
| 包络平方谱顶峰 | 7125 Hz（顶/次=**1.01**，抹平） | **16000 Hz**（顶/次=**2.79**，单根干净谱线） | 真实域有干净的 **16 kHz 符号率**（sps=8）；RadioML 包络平方谱**无干净 cyclostationary 谱线** |

**关键判读**：真实 QPSK 是**教科书式 RRC/近似矩形脉冲成形**的 16 kBaud、8 sps 信号，其
`|x|²` 在符号率 16 kHz 处有一根明显谱线（cyclostationary 特征）。RadioML2018.01A 的合成
QPSK 则被其生成器滤波器把包络谱抹平，**没有干净的符号率谱线**，且 −3 dB 带宽更窄。这正是
模型在训练时“记住”的合成域谱纹理与真实域不匹配的地方。

---

## 4. 模型逐层激活对比（同一 FP32 ONNX，66 个中间张量）

对 66 个中间激活张量（28 Conv + 24 ReLU + 12 Add + 1 ReduceMean + 1 Gemm，不含最终 logits）
统计 RMS：

| 层 | RadioML RMS | 真实 RMS | 真实/合成 |
|---|---|---|---|
| `denoiser/stem/stem.0/Conv`（首层） | 0.466 | 0.517 | 1.11 |
| `denoiser/correction/Conv` | 0.108 | 0.199 | **1.85** |
| `features/features.3/Add` | 1.280 | 1.917 | 1.50 |
| `features/features.6/Add` | 1.101 | 1.646 | 1.49 |
| `features/features.7/conv2/Conv` | 1.029 | 1.903 | **1.85** |
| `features/features.7/Add` | 1.505 | 2.554 | **1.70** |
| `classifier/classifier.1/Relu`（末层） | 1.840 | 2.681 | 1.46 |
| **66 层整体** | — | — | **均值 1.260 / 中位 1.202 / 最小 1.016 / 最大 1.850** |

**判读**：输入只差 2.4%，但经过无 BatchNorm 的深网络后，真实信号的激活 RMS 被系统性放大约
**26%（均值）**，最深残差块（features.7）放大到 **1.85×**。这种系统性放大把最终 24 维 logits
推向 QAM 区（见 §5），而非“某单层偶然饱和”。饱和度量（`zero_frac`/`max_abs`）见 JSON。

---

## 5. 最终 logits 与 top-k（决定性）

| 指标 | RadioML QPSK@30dB (200) | 真实 QPSK (78) |
|---|---|---|
| FP32 top-1 | **200/200 = QPSK（100%）** | **0/78 = QPSK（0%）** |
| top-1 分布 | `{QPSK: 200}` | `{16QAM: 21, 64QAM: 15, 128QAM: 5, 256QAM: 37}` |
| QPSK 平均 logit | **+11.35** | **−38.24** |
| QPSK 平均 softmax 概率 | **1.0000** | **0.0000** |
| top-5 例（首帧） | 见 JSON `topk_example` | 见 JSON `topk_example` |

真实 QPSK 被判为 **16/64/128/256-QAM**（合计 78/78），与上一轮三后端判责
（`MODEL_DOMAIN_GENERALIZATION`）完全一致——**板端 NPU 与 Host 量化逐位一致地忠实复现了
FP32 模型的这一错误**。

---

## 6. 对 Stage C / 最终判责的意义

1. **非缩放问题**：complex RMS 仅差 2.4%，且方向是真实域更高——单纯按 RadioML 分布做 RMS
   归一化**无法**把真实域“拉回”QPSK（真实域本来就接近 1.0）。这排除了“缩放失配”作为主因。
2. **非相位/正交问题**：I/Q 相关≈0、象限各 25%、DC≈0，排除了 IQ 交换、共轭、DC 偏置、
   正交失衡作为主因（Stage C 仍会对这些做合法消融以取证，但预期不改变判类）。
3. **谱结构/脉冲成形失配是主因候选**：带宽 +16~18%、包络平方谱“干净谱线 vs 抹平”、
   PAPR −0.82 dB，三者共同指向**脉冲成形/谱纹理的域差异**。Stage C 将据此检验：
   合法重采样/符号率对齐、估计 CFO 校正、以及“精确复刻训练加载器预处理”能否救回判类——
   若均不能，则判责收敛为 `MODEL_DOMAIN_GENERALIZATION_REQUIRES_REAL_DOMAIN_FINETUNING`。

---

## 7. 产物

- `out/domain_comparison.json` — 全部统计 + 66 层激活 + 78 帧输入 SHA256（权威机读结果）。
- `out/fig_psd.png` / `fig_constellation.png` / `fig_amp_hist.png` / `fig_phase_hist.png` /
  `fig_inst_freq.png` / `fig_env_sq_spec.png` / `fig_autocorr.png` — 图表。
- `stage_b_domain_comparison.py` / `stage_b_charts.py` — 可复现脚本。

**红线遵守**：未改模型/标签/golden/预处理/RTL/位流/Flash；未训练；未写 `*_PASS` /
`PROJECT_COMPLETE`；所有产物在新目录，不覆盖历史工件。
