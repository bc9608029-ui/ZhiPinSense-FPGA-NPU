# 现有信道增强静态审计（十二类鲁棒性增强）

**状态：静态审计，只读基线，不调参。** 本文件描述基线 `channel/*` 的**现状**，并把它与
OOD 六域做数值对照，**不修改任何参数、不锁定任何新范围、不写根因**。增强参数是否可
修复由 AutoDL 结果决定。

---

## 1. 文件清单（逐文件）

| 文件 | 作用 |
|------|------|
| `channel/__init__.py` | 包标记（仅 docstring） |
| `channel/awgn.py` | `add_awgn`（exact_power，测后 SNR 元数据）、`measure_snr_db` |
| `channel/impairments.py` | 组合式损伤原语：`carrier_frequency_offset`、`random_phase_offset`、`phase_noise`、`sampling_frequency_offset`、`iq_imbalance`、`add_dc_offset`、`amplitude_scale`、`clip_iq`、`narrowband_interference`、`burst_interference` |
| `channel/fading.py` | `rayleigh_fading`、`rician_fading`、`multipath_fading`（scipy `lfilter` 因果 FIR） |
| `channel/channel_pipeline.py` | `ChannelPipeline`：按固定顺序编排各效果 + 域随机 + 元数据 |

---

## 2. 增强链顺序（冻结）

`ChannelPipeline.__call__` 的固定顺序：

```
rayleigh/rician（互斥） → multipath → cfo → phase_offset → phase_noise → sfo
→ iq_imbalance → dc_offset → amplitude_scaling → clipping
→ （冻结 desired_signal_power） → narrowband_interference → burst_interference → awgn
```

- `rayleigh` 与 `rician` 在同时被采样时互斥（`if/elif`）。
- 干扰与 AWGN 之前记录 `desired_signal_power_before_interference_noise`，使 SNR/SIR 相对
  期望信号分量有意义，不随衰落/多径/缩放导致的绝对功率漂移。
- AWGN 语义：`__call__` 传入 `snr_db` 时**无条件加噪**（不受 `enabled/probability` 影响）；
  否则按 `awgn.enabled` + 域随机概率决定。

---

## 3. 训练域随机范围 vs OOD 域范围（数值对照）

训练范围来自 `configs/ad_amr_v1_1.yaml::channel`（十二类经 `_base` 链继承，未覆盖 channel）。

### 3.1 CFO（关键）

| 场景 | 范围 | 概率 |
|------|------|------|
| 训练域随机 | `hz [-1200.0, 1200.0]` | 0.55 |
| OOD `cfo_strong` | `hz [-2500.0, 2500.0]` | 1.0 |

**观察**：OOD 强 CFO 把频偏推到训练范围的 **±1300 Hz 之外**（每侧超出 1300 Hz），是训练
分布外推。`sample_rate=128000`，±2500 Hz 相对载波是小频偏，但对 1024 点记录仍是缓慢相位
斜坡；该域直接命中失败的 `cfo_strong`。

### 3.2 多径（关键）

| 场景 | num_taps | max_delay | 概率 |
|------|----------|-----------|------|
| 训练域随机 | `[2, 4]` | `10` | 0.12 |
| OOD `multipath` | `[3, 6]` | `20` | 1.0 |

**观察**：OOD 多径的抽头数上限（6 > 4）与最大时延（20 > 10）都超出训练范围，且
`multipath_fading` 抽头归一化为单位能量、首抽头延迟固定为 0、幅度按 `exp(-delay/(max_delay/3))`
衰减——训练时只见过更浅、更短的多径。命中失败的 `multipath`。

### 3.3 复合损伤（关键）

`multi_impairment` 同时叠加 4 类：

| 效果 | OOD 范围 | 训练范围 | 是否超出训练 |
|------|----------|----------|-------------|
| cfo | `[-1800, 1800]` | `[-1200, 1200]` | **是（每侧 +600 Hz）** |
| phase_noise | `[0.002, 0.008]` | `[0.0001, 0.003]` | **是（上限 0.008 > 0.003）** |
| iq_imbalance | `[-1.5, 1.5] dB / [-8, 8] deg` | `[-1, 1] dB / [-5, 5] deg` | **是（幅度/相位都更大）** |
| multipath | `num_taps [2,5]` `max_delay 16` | `num_taps [2,4]` `max_delay 10` | **是** |

**观察**：复合域每个分量都等于或略超训练单域范围，且四类同时叠加，联合分布远在训练
单域随机之外。命中失败的 `multi_impairment`。

### 3.4 其它 OOD 域（用户确认通过，仅对照记录）

| 域 | OOD 范围 | 训练范围 | 关系 |
|----|----------|----------|------|
| `phase_noise` | `[0.004, 0.012]` | `[0.0001, 0.003]` | 超出 |
| `iq_imbalance` | `[-2,2] dB / [-10,10] deg` | `[-1,1] dB / [-5,5] deg` | 超出 |
| `clipping` | `[0.8, 1.4]` | `[1.5, 2.5]` | OOD 更浅（更易削波） |

> 注：`phase_noise` 单域 OOD 与 `iq_imbalance` 单域 OOD 也超出训练范围，但用户确认
> 正式评估的**失败大类只有** `cfo_strong / multipath / multi_impairment`；本表保留全部
> 六域对照仅作完整性，不据此推断任何类别脆弱性。

---

## 4. 归一化与功率语义（现状）

- 归一化点：`generate_iq` 末尾 `_normalize_rms(iq, amplitude=1.0)`（信道前，逐记录）。
- 信道内：`ChannelPipeline` 不二次 RMS 归一化；`clip_iq` 以当前 RMS 为基准、`level_rms`
  是相对 RMS 的削波限；`add_awgn` 用 `reference_power`（期望分量功率）计算噪声。
- 结论：符合「信道增强后禁止逐帧 RMS 归一化」的约束；v4 增强沿用同一语义。

---

## 5. 静态审计结论

- 基线增强链完整覆盖常规单域损伤 + 训练域随机，但**训练分布对 `cfo_strong`、`multipath`、
  `multi_impairment` 三个失败域存在系统性外推缺口**（§3.1–3.3），方向与用户已定位的失败
  大类一致。
- OOD 域规格**硬编码在 `evaluation/evaluate_ad_amr_v1_1.py::ood_channels`**，不在 YAML。
  v4 已新增 `channel/robust_augment.py::RobustChannelPipeline`（核心 + tail + composite，
  全参数在 `robust.train_channel` YAML，向后兼容），详见 `docs/ROBUST_PILOT_FORMAL_PLAN.md`；
  冻结验证/OOD 仍走原 `ChannelPipeline`，不改评估侧硬编码。
- 本审计**不调参、不锁定新 CFO/多径/复合范围**，不宣称某增强参数「一定可修复」；一切
  等 AutoDL pilot/formal 结果包（`robust` 候选 A/B/C 的 tail/composite 数值仍是候选，
  未锁定）。
