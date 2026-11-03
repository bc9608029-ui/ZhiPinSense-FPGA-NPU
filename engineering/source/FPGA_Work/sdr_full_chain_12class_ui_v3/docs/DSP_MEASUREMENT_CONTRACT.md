# 轻量 DSP 参数测量契约（任务 39e5 UI v3 · M3）

> 状态：**生产者接线完成（READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST 的软件里程碑）**。
> 实现：`sdr_adapter/dsp_measure.hpp`（纯逻辑、header-only、iCraft-free，单帧一次 1024 点 radix-2 FFT）。
> 主机测试 `host_tests/test_dsp_measure.cpp`（24 断言）。
> 消费方：`signal_presence.hpp`(M1)、`auto_level_control.hpp`(M2)、PARAMETERS 页(M5)、ResultFrame 测量字段(M4)。

## 1. 目的

每帧从原始复数样本计算**三域参数**，供无信号判定、自动幅度管理、UI 显示与结果帧携带。
全部为**确定性、可审计**的纯函数；不修改样本、不改变 NPU 输入。

## 2. 输入域与约定

- 输入 = 一帧 **1024 个复数样本**，**计数域**（12-bit，主机满量程 `full_scale=2048`，见
  `rx_iq_format_contract.md` §2）。
- 采样率 `sample_rate_hz` 默认 128000（模型端抽取后速率）。
- 模型域 RMS 在此派生：`model_rms = rms_counts / 2048 × receiver_scale`（与 §3 冻结公式一致）。

## 3. 输出参数（`FrameMeasurements`）

### 原始计数域（单遍统计）
| 参数 | 公式 |
|------|------|
| `rms_counts` | `sqrt(mean(|x|²))`（旋转不变复数幅度 RMS） |
| `peak_counts` | `max |x[k]|` |
| `papr_db` | `20·log10(peak/rms)` |
| `clip_ratio` | `count(|x[k]| ≥ clip_level) / N`（默认 clip_level=2048） |

### 幅度 dBFS
| 参数 | 公式 |
|------|------|
| `power_dbfs` | `20·log10(rms_counts / 2048)` |

### 频谱域（1024 点 FFT，`P[k]=|X[k]|²/N²`，`sum P = rms²`）
| 参数 | 公式 |
|------|------|
| `noise_floor_dbfs` | `10·log10(nf/2048²)`；`nf=max(median(P), 1e-12·max P)`（纯音时 median=0 用相对下限） |
| `psd_peak_prominence_db` | `10·log10(max P / nf)` |
| `snr_est_db` | `10·log10((sum P − nf·N) / (nf·N))`（信号功率/噪声功率） |
| `occupied_bins` | `count(P[k] > nf·10^(th/10))`（默认 th=10 dB） |
| `occupied_bw_hz` | `(max_occ_bin − min_occ_bin + 1) · fs/N`（跨度估计） |
| `spectral_centroid_hz` | `Σ f(k)·P[k] / Σ P[k]`，`f(k)=k·fs/N`（k≤N/2）或 `(k−N)·fs/N`（负频） |

### 模型域
| 参数 | 公式 |
|------|------|
| `model_rms` | `rms_counts / 2048 × receiver_scale` |

### 安全标志
| 参数 | 含义 |
|------|------|
| `nan_inf` | 输入含 NaN/Inf |
| `valid` | 空输入为 false |

## 4. FFT 符号约定

- 前向 DFT（负指数），与 `frame_analysis.hpp` 的 Goertzel 一致：正频音 → 正频 bin。
- `frame_analysis.hpp` 是**单频 Goertzel**（ratio/主导频率），本模块是**全谱 FFT**
  （噪声底/突出度/占用/质心/SNR），两者互补，不互相替代。

## 5. 已知边界（不伪称）

- **噪声底为百分位估计**（默认中位数，抗少数峰值）；`noise_percentile`/`occupied_threshold_db`
  可配置。纯 AWGN 的 N 个平坦 bin 最大值天然比中位数高约 `10·log10(ln N / ln 2) ≈ 10 dB`，
  故默认 10 dB 占用阈值在纯噪声下偶见 1 个伪 bin；`signal_presence` 用**多帧 + SNR 佐证**
  消抖，不受单帧伪 bin 影响。
- `occupied_bw_hz` 是最小/最大占用 bin 的**跨度**（非严格 3 dB/6 dB 带宽），仅供显示/诊断。
- `snr_est_db`/`noise_floor_dbfs` 是**相对估计**，绝对校准依赖板端；不冒充已校准 dB 值。
- 非 2 的幂帧长不计算频谱域（原始/模型域仍计算）；实际帧长恒 1024，不受影响。

## 6. 与其它里程碑的关系

| 消费方 | 用到 |
|--------|------|
| `signal_presence`(M1) | `power_dbfs`、`noise_floor_dbfs`、`snr_est_db`、`psd_peak_prominence_db`、`clip_ratio`、`occupied_bins`、`nan_inf` |
| `auto_level_control`(M2) | `power_dbfs`(→RF 层)、`clip_ratio`、`model_rms`、`valid` |
| PARAMETERS 页(M5) | 全部显示 |
| ResultFrame(M4) | `measurements` 字段携带 |

## 7. 主机测试（`test_dsp_measure.cpp`，8 组）

bin 对齐纯音原始/模型不变式 + 精确 dBFS + 模型 RMS / 纯音频谱（质心=16000 Hz、1 占用 bin、
高突出度、高 SNR）/ 双音跨度与质心居中 / 静音安全 / 空输入 invalid / NaN 标志 / 削顶计数 /
AWGN 平坦谱（15 dB 阈值无占用、低 SNR、低突出度）。

## 8. 红线

- 纯测量，**不改样本、不做逐帧 RMS 归一化、不改 receiver_scale、不改 NPU 输入**。
- 绝对值（dBFS/SNR）为**估计**，UI/日志标注为估计值，不冒充已校准值。
- NaN/Inf/空帧 fail-closed（`nan_inf`/`valid` 标志），不产出虚假参数。
