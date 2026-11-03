# receiver_scale 定标方法（§九，非硬编码）

任务 39e5 §九：receiver_scale 必须是**经标定得到的全局固定标量**，禁止硬编码、禁止
逐帧 RMS 归一化。本文给出可重复的定标流程与判据。

---

## 1. 输入域与换算链

十二类模型输入域 = 训练域：**clean-signal RMS == amplitude == 1.0**（`datasets/modulation_generator.py`
的 `_normalize_rms`）。板端把 12-bit ADC 计数（满量程 2048，`iio_channel_convert` 之后）
映射到该域，只用**一个全局固定标量** `receiver_scale`：

```
model_input = (adc_count / 2048) * receiver_scale          （fp32，直接喂 NPU）
```

因此对参考单音（幅度 = RMS = A 计数）：

```
receiver_scale = target_rms * 2048 / adc_rms_counts
```

其中 `target_rms = 1.0`（`chain::kTargetModelRms`）、`adc_rms_counts` 是收到的参考信号
**复数幅度 RMS（计数单位）**。实现 = `chain::calibrate_rec_scale()`（`board_package/chain_common.hpp`）。

> 与第一批（Gate 1–5）`sdr_adapter/receiver_scale.hpp` 的 Q1.15 域（满量程 32768、输出 Q1.15）
> **不是一回事**——十二类链走 fp32 直通、满量程 2048、无 FPGA 反量化。见
> `docs/GATE45_TESTER_CORRECTIONS.md`。

## 2. 定标流程（可重复，数字回环参考）

用**数字回环**作为确定参考（无 RF、无电缆损耗、可精确复现）：`board_calibrate_rec_scale`
发射固定 DAC 幅度的 10 kHz CW 单音（`--tx-amp`，默认 1500 计数），数字回环收回，
测 `adc_rms_counts`，反推 `receiver_scale`。

```
cd <包根>
./scripts/run_calibrate_rec_scale.sh                 # 默认参数
# 或直接:
./bin/board_calibrate_rec_scale --samples=100000 --tone=10000 \
    --rx-gain=10 --tx-amp=1500 --target-rms=1.0 --out=rec_scale.txt
```

输出：

```
REC_SCALE rec_scale=1.365333 adc_rms_counts=1500.0 tone_amp_counts=1499.8 target_rms=1.0
GATE_RESULT gate=calibrate_rec_scale result=PASS ... rec_scale=1.365333 ...
```

`rec_scale.txt` 写为单行 `rec_scale=<value>`，供 `run_gate9.sh` 引用。

## 3. 判据（失败即停，不静默）

定标器 **PASS** 当且仅当全部满足：

| 判据 | 含义 | 失败提示 |
|---|---|---|
| `tone_ratio > 0.3` | 回环确实收到了参考单音（不是噪声/断路） | `(tone_missing)` |
| `adc_peak < 2048` | ADC 未饱和（12-bit 满量程） | `(adc_clipped)` |
| `|adc_rms − tone_amp| / tone_amp < 0.20` | RMS 与 Goertzel 幅度一致（确为干净单音） | `(amp_inconsistent)` |
| `0 < adc_rms < 2048` 且 `0 < rec_scale < 1e3` | 数值在合理范围 | `(out_of_range)` |

## 4. 稳定性要求（多次运行稳定后冻结）

- 连续运行 **≥3 次**，`rec_scale` 相对变化 `< 1%`（数字回环应近乎逐次一致）。
- 记录每次的 `adc_rms_counts / tone_amp_counts / clip_ratio`。
- 稳定后把 `rec_scale` 作为 `--rec-scale` 传给 Gate 9；**不写进代码**。

## 5. RF 回环（可选，仅参考）

数字回环定标得到的是「DAC 幅度 1500 计数 → 模型域 RMS 1.0」的标度。RF 外接回环因电缆
衰减/接头损耗会使收到的 `adc_rms` 变小，从而 `rec_scale` 变大——这是**正确**的：标度目的
就是让「实际到达 ADC 的参考信号」归一化到 RMS 1.0。RF 定标可用同一工具 `--loopback` 外接
（当前工具默认数字回环；RF 需加 `--confirm-safe-rf-path` 语义，属 Gate 4 安全域，见
`docs/GATE45_TESTER_CORRECTIONS.md`，本工具不主动 RF 发射）。
