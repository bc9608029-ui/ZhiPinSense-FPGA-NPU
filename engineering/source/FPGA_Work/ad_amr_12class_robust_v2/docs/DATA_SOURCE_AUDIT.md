# 数据源审计（DATA_SOURCE_AUDIT）

> 任务：十二类调制识别模型 V2 鲁棒性改进 · 阶段五（数据策略）
> 生成：2026-10-07。只读冻结上游资产，本文件只记录事实，不改任何来源数据/生成器。
> 上游唯一事实来源：`F:\嵌赛\model_ad_amr_v1_2`（V1 冻结源，只读）。

## 0. 目的

按规格 §五「禁止只用一种数据源」，V2 最终数据分为四个域（D1–D4）。本审计逐域核对：

1. 该域在 V1 基线的**真实状态**（有没有、从哪来、怎么生成、有没有落盘）；
2. V2 要**新增/复用**什么；
3. 每域的**防泄漏与确定性**边界。

审计只基于 V1 冻结源的实际代码与配置，不臆造。

## 1. 域总览

| 域 | 内容 | V1 基线状态 | V2 目标 | 优先级 |
|----|------|-------------|---------|--------|
| D1 | 本项目合成训练域 | ✅ 程序化在线生成（不落盘） | 复用 + 增广消融（A/B/C/D 组） | 高 |
| D2 | 冻结合成测试域 | ⚠️ 程序化（未独立冻结落盘） | 一次性冻结 `synthetic_test_v2` | 高 |
| D3 | 公开数据交叉验证域 | ✅ RadioML2018.01A（trunk 预训练） | 复用 + shared-subset 跨域指标 | 中 |
| D4 | 真实 Pluto 采集域 | ❌ 无（V1 纯合成+公开，未实机 RF） | 新增 SigMF 采集 + 导入 | 高（最终评价关键） |

## 2. D1：本项目合成训练域（程序化，食谱冻结）

**V1 事实**（来源 `datasets/modulation_generator.py` + `channel/channel_pipeline.py` + 三个 yaml）：

- 生成器 `generate_iq()`：先 `_normalize_rms(amplitude=1.0)` 归一到 RMS=1.0，再按 `frequency_offset`/`phase_offset`（V1 均为 0）施加频偏/相偏，输出 `complex64`。
- 波形食谱：见 `docs/SYNTHETIC_GENERATOR_CONTRACT.md`（RRC rolloff 0.35 span 8；GFSK BT[0.3,0.7] h[0.45,0.55]；AM-DSB index[0.35,0.9] BW[2500,7000]；WBFM dev[10000,22000]；OFDM 256/64/48 QPSK）。
- 信道域随机化 `ChannelPipeline`：逐效应独立 `probability` 采样（`domain_randomization=true`）；Rayleigh/Rician 互斥；先冻结 `desired_signal_power` 再加干扰与 AWGN，保证 SNR 与 SIR 独立。
- 规模：`train_samples=37800` = 21 SNR × 12 类 × 150；`val_samples=7560` = 21 × 12 × 30。
- 存储：**不落盘**。每 epoch 程序化即时生成；`ADAMRPairDataset.__getitem__` 用 `SeedSequence([seed, split_code, epoch, index])` 保证确定性（见 `docs/DATA_LEAKAGE_AUDIT.md`）。

**V2 增量**：

- 复用同一权威生成器；D1 训练参数覆盖规格 §五列出的多符号率/多初始相位/多幅度/CFO/SRO/AWGN/衰落/多径/IQ 不平衡/DC 偏置/非线性/ADC 量化/增益变化/滤波器变化/脉冲噪声/邻道干扰/时移帧起点。
- 增广新增项必须走消融（`docs/AUGMENTATION_ABLATION.md`），不得一次堆入。
- TorchSig 作为**第二套独立合成/损伤实现参考**，接入前核对每类定义与许可证，不直接替代本项目生成器。

## 3. D2：冻结合成测试域（V2 新增 `synthetic_test_v2`）

**V1 事实**：V1 的 ID 验证集 / OOD 验证集 / fake-int8 验证集均为程序化生成，**没有一次性冻结落盘**。这符合 V1 的确定性设计（`SeedSequence` 可复现），但不符合规格 §五 D2「文件哈希冻结、测试时禁止再生成或替换、尽可能不同生成器交叉验证」。

**V2 目标**（一次性冻结，不可再生成/替换）：

- 名称 `synthetic_test_v2`，独立 seed（与训练 `split_code` 完全不相交，见泄漏审计）。
- 参数组合与训练不同；含 ID / 边界条件 / 超范围压力条件；每类每 SNR 平衡。
- 文件哈希冻结，写入 manifest；测试时只读。
- 尽可能用不同生成器实现（例如 TorchSig 独立实现）做交叉验证，避免「同一生成器缺陷被测试集复刻」。

## 4. D3：公开数据交叉验证域（RadioML2018.01A）

**V1 事实**（来源 `datasets/radioml2018_dataset.py` + `configs/ad_amr_v1_1_data_v2.yaml`）：

- 用途：**trunk 预训练**（`public_pretraining` 30 epoch），不是目标头直接训练/测试源。
- 24 类（`data/radioml2018/classes.txt`），fail-closed 校验（必须 24 唯一类且顺序等于 `OFFICIAL_CLASS_ORDER`）。
- HDF5 `GOLD_XYZ_OSC.0001_1024.hdf5`，`expected_samples=2555904`，`expected_per_stratum=4096`。
- 切分：`split_seed=20261003`，`split_ratios=[0.60,0.20,0.20]`，由 `audit_radioml2018.py` 生成 `split_indices.npz` + `audit.json`（含 HDF5 size/mtime/index SHA，fail-closed）。
- `allowed_snrs=[-20..20]`（步 2）。
- 目标头（12 类）**全新初始化**后微调，不直接复用 trunk 24 类标签。

**V2 增量**：建立逐类标签映射（`docs/PUBLIC_DATASET_LABEL_MAPPING.md`），只对真实重叠类别报 shared-subset 指标，**不**用公开数据直接算完整十二类总分；公开数据缺的类别（2FSK/GFSK/WBFM/AM-DSB/OFDM）不填造。

## 5. D4：真实 Pluto 采集域（V2 新增）

**V1 事实**：V1 **无**真实 RF 数据（纯合成 + 公开预训练，未经实机）。这是 V1 三个 OOD 失败域（cfo_strong/multipath/multi_impairment）之外，规格认定的**最终部署评价关键缺口**。

**V2 目标**：用 UI v3 / Gate 10 十二类信号发生器采集真实 RF，SigMF 格式（`*.sigmf-data` + `*.sigmf-meta`），至少记录类别/seed/中心频率/采样率/TX 衰减/RX gain/rec_scale/SDR 序列号/同轴或天线/距离/时间/位流 SHA/软件版本/模型 SHA/波形参数/标签来源。工具链见 `scripts/capture_real_rf_12class.sh` + `tools/*`，协议见 `docs/REAL_RF_CAPTURE_PROTOCOL.md`。

- API 只生成采集脚本、校验器、manifest 与用户操作命令，**不接触板卡**。
- 采集由用户本人执行（我禁碰板）。

## 6. 状态红线

- 本审计只记录事实，不据此改上游数据/生成器。
- 真实 RF（D4）导入前，最高状态 = `NEEDS-REAL-RF-DATA`。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
- 未经实机验证绝不写 `REAL_RF_PASS / FINAL_MODEL_PASS / OOD_PASS`。
