# 流式重采样器设计与采样率转换说明

## 1. 为什么需要重采样

模型端采样率 **128000 Hz 已冻结**（`contracts/sampling_and_iq_contract.md`）。ADALM-Pluto
（AD9364）的可编程采样率下限约 2.083 MHz，**无法直接输出 128 kHz**。因此 SDR 适配层必须
把板端采样率转换到 128 kHz 后再帧化。该转换只属于 SDR 适配层，不改冻结 Core、不改模型。

## 2. 采样率选择（整数抽取优先）

| 候选 | fs_in | 抽取比 | 说明 |
|------|-------|--------|------|
| **2p56M（首选）** | 2 560 000 Hz | **×20** | 整数；AD9364 可接受区间 [2.083M, 61.44M] 内 |
| 3p84M（回退） | 3 840 000 Hz | **×30** | 整数；AD9364 原生率 |
| 30.72M | 30 720 000 Hz | ×240 | **不作为板端候选**（见 §5），仅 PC 测试记录 |

- 协商过程（`sdr_adapter/sample_rate_negotiate.cpp`）：写采样率 → 读回 → **判等** →
  校验 `fs_in == 128000 × down` 整数成立 → 才接受。禁止静默近似，遍历失败即退出。
- `fs_out = fs_in / down = 128000 Hz` 严格成立。

## 3. 流式有理数重采样器（`sdr_adapter/resampler.{hpp,cpp}`）

整数抽取是 `up=1, down=D` 的特例。实现采用 **polyphase FIR 恒等式**：

```
y[m] = Σ_k h[r + k·up] · x[i − k]
      i = ⌊m·down / up⌋,   r = (m·down) mod up
```

- 输入连续复数 float IQ（fs_in），输出连续复数 float IQ（fs_out）。
- FIR 延迟线 + polyphase 指针跨 `push()` 保留 → 输出与调用方如何分块**无关**
  （`test_resampler.cpp::ChunkInvariance` 逐位一致）。
- API：`push(complex*, n)` / `available()` / `pull(complex*, max)` / `reset()`；
  计数 `in_count/out_count/discarded_transient()` 严格可预测。
- 启动暂态：丢弃前 `(N−1)` 个输出（N = 总 taps），并计数。

## 4. 抗混叠 FIR 设计（`tools/gen_fir_coeffs.py`）

- 方法：scipy `remez`（equiripple）低通。
- 通带 **50 kHz**（模型信号 ~25 kHz 远在其内）、阻带 **64 kHz**（= fs_out/2），
  阻带衰减 **≥70 dB**，DC 增益归一化为 1。
- 系数生成一次，同时产出 `fir_coeffs.h`（C++ 编译期）与 `fir_coeffs.json`/`.bin`
  （Python 参考），**C++ 与 PC 参考共用同一套系数**，保证 Golden 一致。

| 候选 | taps | 阻带衰减（实测） |
|------|------|------------------|
| 2p56M（×20） | 601 | **72.8 dB** |
| 3p84M（×30） | 903 | **73.0 dB** |

频率响应与混叠抑制曲线见 `docs/resampler_response.png`（由
`tools/plot_resampler_response.py` 生成）：左栏为 `|H(f)|`，右栏为每个输出 bin
`f_out∈[0,64 kHz]` 的最坏带外混叠泄漏（仅统计 k≥1 的折叠镜像，带内 k=0 本应通过）。

## 5. 30.72 MHz 为何不作为板端候选

单级 ×240 抽取的归一化过渡带极窄（50k/64k 相对于 30.72M 的归一化频率），remez 需
>6000 taps 仍 <57 dB，数值不稳定且非实时。因此 30.72 MHz 仅作 PC 测试记录，板端只用
2.56M / 3.84M 整数抽取。

## 6. Golden 验证（C++ vs Python）

- `tools/resampler_golden.py`：numpy float64 参考（polyphase 恒等式），生成确定性输入
  （带内双音 + 带外混叠探针）与参考输出。
- `host_tests/test_resampler.cpp`：加载同一输入，运行流式重采样，与参考逐样本比对
  （误差 < 预置门限），并自含直接卷积参考、分块不变性、计数不变式、混叠抑制五组。
- 实测：**Golden2p56M / Golden3p84M / BruteForceMatch / ChunkInvariance / AntiAlias
  全 PASS（30/0）**。

## 7. 帧化

- 重采样后累积到 1024 复数 → 输出一帧；**不补零冒充**，尾部不足 1024 明确丢弃并计数
  （`board_resampler_test.cpp`）。
