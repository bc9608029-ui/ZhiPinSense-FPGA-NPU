# 开源参数模型审计（任务 39e5 UI v3 · M11）

> 状态：**审计完成（只读联网调研，不引入任何外部代码/依赖）**。
> 日期：2026-10-07。范围：十二类调制识别 + 信号参数估计的开源模型与工具。
> 结论类型：**参考/回退调研**，**不改变**本工程 NPU 12 类模型与 M3 轻量 DSP 测量方案。

## 1. 目的

M3 已用轻量 DSP 在板端测量信号参数（RMS/peak/PAPR/clip、dBFS、频谱噪声底/突出度/SNR/占用
bin/BW/质心、模型 RMS）。M11 审计开源界已有的"参数模型"（调制类型分类 + 参数估计），确认：
（a）本项目方案（板端 NPU 12 类模型 + 轻量 DSP）是否有被开源方案替代的必要；
（b）是否存在可借鉴的盲参数估计算法；（c）许可证是否允许在本工程中引用。**本轮只审计，不移植。**

## 2. 开源自动调制分类（AMC）深度学习模型

| 项目 | 架构 | 数据集/性能 | 说明 |
|------|------|------------|------|
| [Hierarchical-Signal-Classification](https://github.com/Suyashkb/Hierarchical-Signal-Classification-using-Deep-Learning) | 分层 CNN / CNN-LSTM（二进制 + 相位 + 非相位三阶段） | 11 类 462k 样本；二进制阶段 >99%，CPU 单条 <1s | 分层思路与本工程 12 类契约可对照，但训练数据/标签不同 |
| [attention_based_AMR](https://github.com/ocatak/attention_based_automatic_modulation_recognition) | CNN-Transformer（baseline/causal/sparse 注意力） | RML2016.10a ≈83.6–85.05% | 展示注意力变体的推理时延权衡 |
| [STF-GCN](https://github.com/WestdoorSad/STF-GCN) | 时空频图卷积网络 | RML2016.10a 64.35% / RML22 70.95% | 低 SNR 更优，但绝对精度低于本工程 0.90 门限 |
| [ASEFEAMC](https://github.com/stu-cjlu-sp/rsrc-for-pub/tree/main/ASEFEAMC) | BiLSTM+Transformer+幅度重标定增广 | RML2016a 94.18% | 增广思路可参考，非即插即用 |
| [ZSAMR-VLM](https://github.com/zhaoyurui/ZSAMR-VLM) / [Sig2text](https://github.com/Na-choneko/sig2text) | 大视觉-语言模型 / 零样本 | 依赖文本提示、时频图 | 推理成本高，不适用板端 NPU 实时链 |
| [MCLDNN](https://relatedrepos.com/gh/wzjialang/MCLDNN)、[IQFormer](https://relatedrepos.com/gh/WestdoorSad/IQFormer)、MAMC(Mamba) | 多路 CNN / Transformer / Mamba | RML 基准 | 精度中等，迁移需重训 |

**与本工程的关系**：上述模型均为 RadioML/RML 系列基准上的研究实现，调制集合与采样率/帧长与本
工程 12 类契约（128 ksps、sps=8、1024 帧）**不一致**，无法直接替换板端已实证的 NPU 模型
（`model_12class.raw` SHA `2ae95275…`，Gate 7 re-arm 后 227/240）。仅作**架构/增广思路参考**。

## 3. 开源信号参数估计（经典 DSP，对应 M3）

参数估计的权威脉络（JPL Descanso 专著 + 多篇论文/学位论文）：

| 参数 | 经典盲估计方法 | 与本工程 M3 对照 |
|------|---------------|-----------------|
| 符号率/符号周期 | 相关滤波器组 + 抛物线插值；频率域互相关峰搜索；qGLRT 联合估计 | M3 未直接测符号率（训练契约固定 16 kHz/sps=8），**无需补** |
| 载波频偏 CFO | 平方/四次方后 FFT 峰；DTFT/FFT 解析插值（CRLB 精度）；EKF | M3 未测 CFO；训练契约 CFO[-1200,1200]Hz 已在分类器鲁棒范围内 |
| SNR | 与速率/格式/定时联合估计（qGLRT） | M3 已有 `power−noise_floor` 估计（增益不变一致性关键） |
| 调制指数/调制度 | AM/WBFM/FSK 的带宽与频偏估计 | M3 占用 BW/质心是跨度估计，未标定绝对值 |
| OFDM 参数 | 自相关求 FFT 长度 + 循环自相关求 CP 长度 → 子载波间隔/符号时间 | M3 单帧 1024 FFT 测占用 BW，未做 OFDM 盲同步 |

- 权威源：[JPL Descanso 专著第 11 章（自主无线电参数联合估计）](https://descanso.jpl.nasa.gov/monograph/series9/Descanso9_11_rev.pdf)、
  TU Graz 相关滤波器组论文、UNSW/CVUT/爱琴海大学学位论文（见 §5 来源）。
- **结论**：M3 已覆盖本工程所需的最小参数集（幅度/SNR/占用/频谱形态）；符号率/CFO/OFDM 盲同步
  因训练契约已固定或已由模型鲁棒性覆盖，**本轮不移植**，仅在文档记录以备后续扩展。

## 4. 最直接可用的 SDR 工具：gr-inspector

- [gr-inspector](https://github.com/gnuradio/gr-inspector)（GNU Radio OOT 模块，KIT 通信工程实验室，
  GSoC 2016 + ESA SoC in Space）：能量检测（手动/自动阈值 + 窄带抑制）→ 信号分离（下变频/滤波/
  抽取/重采样）→ **TensorFlow 单载波 AMC** → **OFDM 参数估计**（自相关求 FFT 长度 + 循环自相关
  求 CP 长度 → 子载波间隔/符号时间）→ 盲 OFDM 同步；GUI 频谱可视化。依赖 GNU Radio 3.8/Qt5/Qwt。
- [GNU Radio qpsk-modulation 主题](https://github.com/topics/qpsk-modulation) 下多个 QPSK 接收机实现
  （匹配滤波/同步/EKF 载波跟踪/符号率跟踪/RRC 脉冲整形 + CFO/相位噪声/IQ 不平衡）。
- **与本工程的关系**：gr-inspector 是通用主机 PC 工具链，依赖完整 GNU Radio + TensorFlow 运行时，
  **不适用 FMQL30TAI 板端 + ZG330 NPU + 12 类契约**；其 OFDM 盲估计的"自相关/循环自相关"思路
  可在后续（若需在板端扩展 OFDM 子参数）时借鉴，本轮不移植。

## 5. 许可证与移植结论

- 本工程**未引入**任何上述开源代码/模型/权重：M3 与 12 类模型均为自研或冻结资产，无许可证风险。
- 若后续引入 gr-inspector（GPL-3.0，因链接 GNU Radio）或上述研究模型（多为研究许可/未声明），
  **需单独评估与商用/竞赛提交的兼容性**，本轮仅记录。
- **审计结论**：板端 NPU 12 类模型（已实证）+ M3 轻量 DSP 参数测量，覆盖本任务所需；开源方案
  是**参考与回退**，**不替换**、**不移植**、**不改位流/Flash/模型**。

## 6. 红线

- 未实机验证只标 `READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST`，不写任何 *_PASS。
- 本审计不引入外部代码/依赖；我禁碰板/禁写 Flash；上板由用户本人执行。
