# 合成生成器契约（SYNTHETIC_GENERATOR_CONTRACT）

> 任务：十二类调制识别模型 V2 鲁棒性改进 · 阶段五 D1/D2
> 生成：2026-10-07。基于 V1 冻结源 `F:\嵌赛\model_ad_amr_v1_2` 的**实际实现**逐条记录，作为 V2 复用与新增增广的权威契约。
> 只读冻结：V2 不修改 V1 生成器；新增生成器/增广在 V2 工程内独立实现。

## 0. 输入/输出契约（与 NPU 部署一致，绝不改）

- 输入：1024 个复数 I/Q 点；I/Q 排列、数据类型、归一化必须从 V1 契约读取。
- 落盘/张量化：`iq[2,1024]`，`float32`，第 0 维 = 实部，第 1 维 = 虚部（`torch.from_numpy(np.stack((iq.real, iq.imag)).astype(np.float32))`）。
- 归一化：生成器 `_normalize_rms(iq, amplitude=1.0)` → 记录 RMS = 1.0。
- 输出：12 类 logits；训练时 label 为 0..11 的 int，顺序见下表。

## 1. 冻结的十二类标签（权威顺序）

```
0 OOK  1 4ASK  2 AM-DSB  3 WBFM  4 2FSK  5 GFSK
6 BPSK  7 QPSK  8 8PSK  9 16QAM  10 64QAM  11 OFDM
```

## 2. 信号参数（`signal`，V1 冻结值）

| 参数 | 值 | 说明 |
|------|-----|------|
| sample_rate | 128000.0 Hz | 采样率 |
| symbol_rate | 16000.0 | 符号率 |
| samples_per_symbol | 8 | 每符号采样 |
| sample_length | 1024 | 记录长度 |
| amplitude | 1.0 | RMS 归一到 1.0 |
| frequency_offset | 0.0 | 生成器内固定频偏（V1=0；CFO 由信道层施加） |
| phase_offset | 0.0 | 生成器内固定相偏（V1=0） |
| pulse_shape | rrc, rolloff=0.35, span=8 | 线性调制根升余弦 |

一致性硬约束（`generate_iq` 内断言）：`sample_rate == symbol_rate * samples_per_symbol`。

### 2.1 各调制实现要点（来自 `modulation_generator.py`，冻结）

- **线性调制**（OOK/4ASK/BPSK/QPSK/8PSK/16QAM/64QAM）：Gray 映射星座 → RRC 脉冲成形 → 跳过整段滤波器跨度裁剪（`start = group_delay + span*sps + timing_offset`），记录边界是连续流裁剪而非零填充 FIR 启动签名（防分类器利用边缘特征）。`timing_offset ∈ [0, sps)` 随机。
  - 星座（单位均值能量）：OOK `[0, √2]`；4ASK `[-3,-1,1,3]/√5`；BPSK `[±1]`；QPSK `[±1±j]/√2`；8PSK 单位圆 8 点；16QAM/64QAM Gray PAM 归一化。
- **2FSK**：连续相位二进制 FSK，`modulation_index=1.0`，`tone_separation = 1.0*symbol_rate`。
- **GFSK**：高斯频率脉冲成形，`BT∈[0.3,0.7]`、`modulation_index∈[0.45,0.55]`、`span_symbols=4`；sigma 映射 = `sps/(2π·BT)`（记录为实现假设）；随机 BT 防固定滤波器指纹成为标签捷径。
- **AM-DSB**：`(1 + index·m)`，`index∈[0.35,0.9]`，消息带宽 `∈[2500,7000]Hz`（带限零均值单位峰消息，加 256 guard 防边缘线索）。
- **WBFM**：`dev∈[10000,22000]Hz`，消息带宽 `∈[2500,7000]Hz`，随机初始相位，相位积分 FM。
- **OFDM**：`fft_length=256`、`cyclic_prefix=64`、`active_subcarriers=48`（偶数、非零对称 bin）、`QPSK`；块内 `record_offset ∈ [0, block_length)` 随机；`ifft * √fft_length`。

## 3. 信道层（`channel`，V1 冻结概率/范围）

域随机化 `domain_randomization=true`，逐效应独立按 `probability` 采样；Rayleigh/Rician 互斥。

| 效应 | enabled | probability | 范围 |
|------|---------|-------------|------|
| awgn | true | 1.0 | snr_db ∈ [-20, 20] |
| rayleigh | true | 0.10 | 平坦衰落系数 |
| rician | true | 0.10 | k_factor ∈ [3, 10] |
| multipath | true | 0.12 | taps ∈ [2, 4]，max_delay=10 |
| cfo | true | 0.55 | hz ∈ [-1200, 1200] |
| phase_offset | true | 0.65 | radians ∈ [-π, π] |
| phase_noise | true | 0.10 | std_rad ∈ [0.0001, 0.003] |
| sfo | true | 0.08 | ppm ∈ [-60, 60] |
| iq_imbalance | true | 0.12 | gain_db ∈ [-1, 1]，phase_deg ∈ [-5, 5] |
| dc_offset | true | 0.08 | magnitude ∈ [0, 0.05] |
| amplitude_scaling | true | 0.5 | scale ∈ [0.7, 1.3] |
| clipping | true | 0.06 | level_rms ∈ [1.5, 2.5] |
| narrowband_interference | **false** | 0.0 | sir_db ∈ [8, 25]（V1 关闭） |
| burst_interference | **false** | 0.0 | sir_db ∈ [5, 20]，duty ∈ [0.05, 0.2]（V1 关闭） |

关键实现细节（V2 复用与增广必须遵守）：

- AWGN 参考功率 = 施加干扰/衰落/缩放**之前**的 `desired_signal_power`，保证 SNR 与 SIR 独立、SNR 语义在信道后仍可解释。
- SFO 用线性漂移时间基 + `np.interp` 近似重采样。
- IQ 不平衡：`i'=i·g`，`q'=q/g`，再 ±θ/2 混合。
- 削顶 `clip_iq`：`level_rms × RMS` 为限幅，逐点 `min(1, limit/|iq|)` 软削顶。

## 4. 数据集切分与确定性（见 `DATA_LEAKAGE_AUDIT.md`）

- RNG：`np.random.default_rng(SeedSequence([seed, split_code, epoch, index]))`。
- `split_code = int.from_bytes(blake2s(split_string, digest_size=4).digest(), "little")`。
- `sample_id_base = split_code * 1_000_000`（跨 split 样本 id 不重叠）。
- 训练 epoch 参与 seed（`epoch` 项），验证/测试 epoch 固定为 0。

## 5. V2 增广契约（新增，独立于 V1）

- 规格 §八 A/B/C/D 组增广（几何时序/信道/硬件/干扰）**逐项消融**，不得一次堆入。
- 任何增广**不得改变真实标签**；旋转/翻转等在 AM、FSK、非对称调制（OOK/4ASK/AM-DSB）上必须逐类验证（规格 §八 红线）。
- 新增增广若改变 SNR/功率语义，必须沿用 V1「先冻结 desired signal power 再加噪」的约定，或显式记录偏离理由。
- 新增生成器实现（如 TorchSig 交叉验证）必须输出与本节一致的最小元数据（类别/seed/SNR/效应列表），便于 `check_data_leakage.py` 与 manifest 校验。
