# 十二类确定性波形生成契约（任务 39e5 UI v3 · M9 前置）

> 本文件是 M9 `board_package/rf_waveform_12class.hpp/.cpp` 的可执行契约。
> 所有波形参数**必须**引用 `TRAINING_SIGNAL_CONTRACT_AUDIT.md`（M0）；新增参数标
> `NEW_TEST_PARAMETER`，不伪称来源。

## 1. 目标

生成十二类（OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM）
**2.56 MS/s 连续复数基带**，供 Pluto TX 经同轴回环做 RF 自测（Gate 10）。

## 2. 生成链（两段）

```
128 kS/s baseband 合成（RMS=1.0，fp32）  ──×20 polyphase FIR──►  2.56 MS/s 连续流
    （按 M0 §4 逐类规则）                  （复用 resampler.hpp，已验证 72.8 dB）
```

- **baseband 在 128 kS/s 生成**（symbol_rate=16000，sps=8，sample_length=1024/帧）。
- **上采样 ×20** 到 2.56 MS/s：必须用**已验证的插值滤波**（`sdr_adapter/resampler.hpp`
  的 `up=20, down=1` 变体，或等价 polyphase FIR），**不得简单重复采样**（`NEW_TEST_PARAMETER`：
  训练无上采样步骤，故滤波器与通带指标是本任务选择，采用基线已验证 FIR 以保持 72.8 dB）。
- **连续相位**：跨帧/跨块不重置相位；GFSK/2FSK/WBFM 的相位积分、OFDM 的块相位均连续累积，
  **不允许每 1024 点重置相位**。

## 3. 逐类规则（引用 M0 §4，此处只列实现要点）

| 类 | 实现要点 |
|----|----------|
| OOK | 符号 ∈ {0, √2}（等概率），RRC(0.35, span 8) 成形，upfirdn(up=8) |
| 4ASK | 符号 ∈ {-3,-1,1,3}/√5（Gray 序），RRC |
| BPSK/QPSK/8PSK/16QAM/64QAM | 按 `constellation_points`（M0 §4 表）映射 + RRC |
| 2FSK | `tone_separation=16000 Hz`，`modulation_index=1.0`，连续相位 `phase += 2π·(sym·sep/2)/fs` |
| GFSK | 高斯脉成形（`span=4`，`sigma=max(sps/(2π·BT),1.0)`），`BT∈[0.3,0.7]`、`mod_index∈[0.45,0.55]`，连续相位 |
| AM-DSB | `iq = (1 + index·m)`，`index∈[0.35,0.9]`，m = Hann-LPF(129-tap, BW∈[2500,7000]Hz) 带限消息 |
| WBFM | `phase += 2π·dev·m/fs`，`dev∈[10000,22000]Hz`，消息同上 |
| OFDM | **fft=256, CP=64, active=48**，QPSK 子载波，`ifft(freq)·sqrt(256)`，CP 前置，block=320 |

- RRC taps 公式：`root_raised_cosine_taps(sps=8, span=8, beta=0.35)`（单位能量），见 M0 §4。
- 每类随机变量（symbol 序列、timing_offset、BT、index、dev、消息白噪声、子载波数据）取自
  **本模块自己的 RNG**（固定 seed 可复现），类别标签**绝不进入 NPU 输入或推理代码**。

## 4. RNG 与可复现性

- `--seed=<N>` 固定 seed 时，生成输出**字节级可复现**（同 seed 跑两次 SHA 一致）。
- 支持多 seed；RNG 用确定性伪随机（C++ `std::mt19937_64` 或等价，实现内固定算法）。
- RNG 流与黄金集/训练样本 id 无关（避免 `SeedSequence([2026, split_code, epoch, index])` 撞样本）。

## 5. 12-bit TX 安全范围（NEW_TEST_PARAMETER）

- baseband RMS=1.0 → 上采样后 RMS 不变（理想插值）。TX 前乘以全局幅度 `tx_amplitude`
  使 **peak ≤ 0.8×2048 ≈ 1638 计数**（`NEW_TEST_PARAMETER`：留 DAC 裕量、默认不削顶）。
- 输出交织 int16 `[I,Q,I,Q,...]`，**走 `iio_channel_convert_inverse`**（÷2048 12-bit 域），
  不直接写满幅 16-bit（见 `rx_iq_format_contract.md` §2/§3）。
- 每类输出并记录：**RMS、peak、PAPR、频谱中心、占用带宽**（用于自测断言与 12-bit 校验）。

## 6. 输出元数据（每类生成后自报）

```
modulation, seed, sample_rate=2560000, symbol_rate=16000, samples_per_symbol=8,
rms, peak, papr_db, spectral_centroid_hz, occupied_bw_hz, phase_continuous=true,
tx_amplitude, tx_peak_counts
```

## 7. 边界红线

- 不简单重复采样代替上采样；不用 `fake_qf`/Golden 冒充生成波形。
- 峰值不超 12-bit 安全范围；全 finite（NaN/Inf 立即失败）。
- 类别标签只用于**预期标签记录**，不喂 NPU。
- 新增参数（§2 上采样 FIR、§5 tx_amplitude）一律标 `NEW_TEST_PARAMETER`。
