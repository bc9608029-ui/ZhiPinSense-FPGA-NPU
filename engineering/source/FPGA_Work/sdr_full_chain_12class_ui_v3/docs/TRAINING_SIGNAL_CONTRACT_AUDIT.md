# 训练信号契约审计（任务 39e5 UI v3 · M0）

> 目的：从已冻结的训练代码/配置/数据生成器/模型契约中提取十二类确定性合成信号的
> 生成规则，作为 M9 波形生成器与 M3 DSP 参数测量的权威依据。
> 状态：**审计完成，全部数值来自冻结训练资产，逐条标注来源；未定义的参数标
> `NEW_TEST_PARAMETER`，不伪称来源于训练配置。**

## 1. 权威来源（冻结，只读）

| 资产 | 路径 | 作用 |
|------|------|------|
| 信号生成器 | `ad_amr_data_v4_12class_robust/datasets/modulation_generator.py` | 十二类 baseband 合成（`generate_iq`） |
| 信道管线 | `ad_amr_data_v4_12class_robust/channel/channel_pipeline.py` | CFO/噪声/衰落/削顶等增强 |
| 损伤算子 | `ad_amr_data_v4_12class_robust/channel/impairments.py` + `awgn.py` | 各增强的具体实现 |
| 数据集 | `ad_amr_data_v4_12class_robust/datasets/ad_amr_dataset.py` | RNG 种子与 I/Q→tensor 拼接 |
| 权威配置 | `ad_amr_data_v4_12class_robust/configs/ad_amr_v1_1.yaml`（→ data_v2 → data_v3_12class 逐层 `_base`） | 信号/信道参数默认与增强范围 |
| 模型契约 | 本工程 `model_12class/MODEL_DEPLOYMENT_CONTRACT.md` | 部署模型身份/输入/输出/类别序 |
| 采样/IQ 契约 | 本工程 `contracts/sampling_and_iq_contract.md` + `rx_iq_format_contract.md` | 采样率/帧结构/12-bit 计数域 |

## 2. 采样率与帧结构（冻结）

| 项 | 值 | 来源 |
|----|----|------|
| 模型端目标采样率 | **128000 Hz** | `sampling_and_iq_contract.md` §1 |
| 符号率 | **16000 Hz**（`samples_per_symbol=8`） | `ad_amr_v1_1.yaml` `signal` |
| 设备原始采样率 | **2560000 Hz**（首选，×20 整数抽取）；备用 3840000 Hz（×30） | `pluto_config_contract.md` §2 |
| 抽取关系 | 2.56 MS/s → 128 kS/s = **20:1**（`resampler.hpp` `up=1,down=20`） | 本工程 `sdr_adapter/resampler.hpp` |
| 每帧复数样本 | **1024**（`sample_length=1024`） | 同上 |
| 帧间跳步 | 1024（无重叠） | `sampling_and_iq_contract.md` §2 |
| 类别顺序 | OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM | `categories.hpp` `target_12()` |

## 3. IQ 数值格式（冻结）

- 模型输入：**单输入 `iq [1,2,1024]` fp32**，channel 0 = **I（real）**，channel 1 = **Q（imag）**，
  布局 C 序（先 1024 个 I，再 1024 个 Q）。来源 `MODEL_DEPLOYMENT_CONTRACT.md` §1/§5。
- 训练域幅度：`generate_iq` 输出经 `_normalize_rms` 归一化到 **RMS = amplitude = 1.0**。
- 数据集拼接：`np.stack((iq.real, iq.imag)).astype(np.float32)` → `[2,1024]`（`ad_amr_dataset.py` `to_tensor`）。
- **禁止逐帧 RMS 归一化**（`sampling_and_iq_contract.md` §3 `per_record_rms_normalization=forbidden`）；
  `receiver_scale` 是全局固定标量（板端标定值 **21.8556709**），作用在 `receiver_scale.hpp`
  `x_model = count × receiver_scale`（12-bit 域 ÷2048 见 `rx_iq_format_contract.md` §3）。
- Pluto RX/TX：AD9364 **12-bit 装入 16-bit 容器**（`shift=4`，MSB 对齐），主机满量程 **±2048**；
  `iio_channel_convert`/`convert_inverse` 做掩码与移位（`rx_iq_format_contract.md` §2）。

## 4. 十二类生成规则（`modulation_generator.py`，`generate_iq`）

公共 `SignalConfig` 默认：`sample_rate=128000, symbol_rate=16000, samples_per_symbol=8,
sample_length=1024, amplitude=1.0, rolloff=0.35, span_symbols=8`。

**脉冲成形（线性调制共用）**：`root_raised_cosine_taps(sps=8, span=8, beta=0.35)`，
单位能量 RRC；`scipy.signal.upfirdn(taps, symbols, up=8)`；裁掉前
`group_delay(=32) + span*sps(=64) + timing_offset` 样本（等价连续流中段裁剪，非零填充 FIR 起始特征）。
`timing_offset = int(rng.integers(0, sps))` ∈ [0,7]。

| 类 | 星座/映射 | 关键参数 | 占用带宽近似 |
|----|-----------|----------|--------------|
| OOK | `{0, √2}`（单位均值符号能量） | RRC 0.35/8 | (1+0.35)·16000 = **21600 Hz** |
| 4ASK | `{-3,-1,1,3}/√5`（Gray 序） | RRC | 21600 Hz |
| BPSK | `{+1,-1}` | RRC | 21600 Hz |
| QPSK | `{1±j, -1±j}/√2` | RRC | 21600 Hz |
| 8PSK | `exp(j·2πk/8)` | RRC | 21600 Hz |
| 16QAM | Gray 4-PAM，单位均值功率 | RRC | 21600 Hz |
| 64QAM | Gray 8-PAM，单位均值功率 | RRC | 21600 Hz |
| 2FSK | `{±1}` 连续相位 | `modulation_index=1.0`，`tone_separation=16000 Hz` | 2·16000 ≈ 32000 Hz（旁瓣外） |
| GFSK | 连续相位 | `BT∈[0.3,0.7]`、`mod_index∈[0.45,0.55]`、`span=4`、`sigma=max(sps/(2π·BT),1.0)` 高斯脉 | (1+mod_index)·16000 |
| AM-DSB | `iq=(1+index·m)` | 消息 BW∈[2500,7000]Hz（firwin 129-tap Hann LPF）、`index∈[0.35,0.9]` | 2·BW |
| WBFM | 相位积分 `exp(j∫2π·dev·m/fs)` | 消息 BW∈[2500,7000]Hz、`dev∈[10000,22000]Hz` | 2·(BW+dev) |
| OFDM | QPSK 子载波 | **`fft_length=256, cyclic_prefix=64, active_subcarriers=48`** | 48·128000/256 = **24000 Hz** |

> **OFDM 关键纠正**：训练配置 `ad_amr_v1_1.yaml` `signal.ofdm` 为
> `{fft_length:256, cyclic_prefix:64, active_subcarriers:48, subcarrier_modulation:QPSK}`，
> **覆盖** `modulation_generator.py` 内 `_generate_ofdm` 的默认 `64/16/48`。M9 生成器必须按
> **256/64/48** 实现（block_length=320，active bins = 24 个负频 + 24 个正频，DC 与两侧空置）。
> IFFT 归一化 `ifft(freq) * sqrt(fft_length)`；CP 取块尾 64 样本前置于块首。

**幅度归一化**：`_normalize_rms(iq, amplitude=1.0)` 使 `sqrt(mean(|iq|²)) = 1.0`（全局，非逐帧）。

**频偏/相位（生成器级）**：`SignalConfig.frequency_offset`/`phase_offset` 默认 **0**；
训练中的 CFO/相位随机来自**信道管线**（见 §5），不在 `generate_iq` 内注入。

## 5. 信道增强范围（`ad_amr_v1_1.yaml` `channel`，`domain_randomization=true`）

| 效应 | 启用概率 | 参数范围 | 说明 |
|------|----------|----------|------|
| AWGN | 1.0 | SNR **[-20, 20] dB** | `add_awgn`，相对期望信号功率，exact_power |
| Rayleigh 衰落 | 0.10 | — | 与 Rician 互斥 |
| Rician 衰落 | 0.10 | K∈[3,10] | |
| 多径 | 0.12 | 抽头 [2,4]，max_delay 10 | |
| **CFO** | 0.55 | **[-1200, 1200] Hz** | `carrier_frequency_offset` 复数旋转 |
| 相位偏移 | 0.65 | [-π, π] rad | |
| 相位噪声 | 0.10 | std [1e-4, 3e-3] rad | 累积高斯 |
| 采样频偏(SFO) | 0.08 | [-60, 60] ppm | 线性漂移时基插值 |
| IQ 失衡 | 0.12 | gain [-1,1] dB，phase [-5,5]° | |
| DC 偏移 | 0.08 | 幅度 [0, 0.05] | |
| 幅度缩放 | 0.5 | scale **[0.7, 1.3]** | 线性 |
| 削顶 | 0.06 | level_rms [1.5, 2.5] | `clip_iq` |
| 窄带/突发干扰 | **false** | — | 训练未启用 |

> v4 robust 配置额外加 CFO tail（prob 0.20，[-2500,2500] Hz）与 cfo_strong 域 [-2500,2500]；
> 但**部署模型的训练基线是 data_v3_12class（`_base` 链 = v1_1 → data_v2 → data_v3_12class）**，
> 故上表（v1_1 值）是部署模型的实际增强范围。

## 6. RNG 与数据集拼接（`ad_amr_dataset.py`）

- 每条样本 `index` 的 RNG：`np.random.default_rng(SeedSequence([seed=2026, split_code, epoch, index]))`；
  `split_code = blake2s(split_string, digest_size=4)` 小端；训练 split `ad_amr_v1_1_train`。
- 标签/SNR（平衡）: `index % (12 × 21)` → `label = comb % 12`、`snr = snr_values[comb // 12]`；
  `snr_values = [-20..20 step 2]`（21 档）。
- 流程：`generate_iq(mod, signal_config, rng)`（RMS=1.0）→ `ChannelPipeline(clean, rng, snr_db)` →
  `np.stack((real, imag)) → [2,1024] fp32`。

## 7. 模型输入/输出（部署 NPU）

- 输入 `iq [1,2,1024]` fp32；输出 `logits [1,12]` fp32；INT8 量化、对称、per-channel、KLD；
  `no_transinput`（输入保持 fp32）。板端程序喂 fp32，读回 fp32 logits（`MODEL_DEPLOYMENT_CONTRACT.md` §5）。

## 8. NEW_TEST_PARAMETER（训练配置未定义，M9/自测需自行选择并标注）

以下参数在冻结训练资产中**没有**权威值，属于本任务的**测试参数选择**，不得宣称来自训练配置：

| 参数 | 说明 | 建议依据 |
|------|------|----------|
| RF 自测 TX 峰值幅度（12-bit 计数） | 训练只定义 baseband RMS=1.0（fp32），未定义 12-bit TX 峰值 | 选 peak ≤ 0.8×2048 ≈ 1638 计数，留 DAC 裕量 |
| RF 自测固定 CFO（同轴回环） | 训练 CFO 是 ±1200 Hz 随机；自测用同 LO 同轴回环，实测 CFO≈0 | 不额外注入，实测为准 |
| 波形生成上采样滤波器（128k→2.56M ×20） | 训练无上采样步骤（生成即 128k） | 复用 `resampler.hpp` 已验证 ×20 polyphase FIR（72.8 dB） |
| 自测 seed 集合 | 训练 seed=2026/2027 | 自测选独立 seed（如 0..N-1），避免与黄金集样本 id 冲突 |
| 每类帧数 | 训练 150/30 重复 | 自测默认每类 20 帧（240 总） |

## 9. 审计结论

1. 十二类生成规则与信道增强范围**全部来自冻结训练资产**，无伪称项；唯一需标注的是 §8 的测试参数。
2. **OFDM 按 256/64/48 实现**（配置覆盖生成器默认，已纠正）。
3. 模型域幅度 = **RMS 1.0**（fp32）；Pluto 12-bit 计数域满量程 **±2048**，两者由 `receiver_scale=21.8556709`
   与 `iio_channel_convert`/`convert_inverse` 桥接，M9 的 TX 路径须走 `convert_inverse`（÷2048 域）。
4. M9 波形生成器在 128 kS/s baseband 生成、RMS=1.0 归一化，再经已验证 ×20 polyphase FIR 上采样到 2.56 MS/s；
   参数一律引用本文 §2/§4，新增参数标 `NEW_TEST_PARAMETER`。
