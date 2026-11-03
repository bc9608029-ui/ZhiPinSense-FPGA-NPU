# Gate 4/5 测试器修正（§十）

任务 39e5 §十要求记录第一批（Gate 1–5，`sdr_pluto_board_integration_v1`）的 Gate 4（RF
回环）与 Gate 5（重采样+定标）测试器在本十二类链中**继承的修正**，以及十二类链对它们的
**有意分歧**。本工程**只读**第一批源码（SHA 冻结于 `SOURCE_PROVENANCE_SHA256.txt §G`），
未改动任何上游文件。

---

## 1. 继承的修正（第一批已修，十二类链原样复用）

十二类链复用第一批的 `board_common.hpp` / `pluto_tx` / `sample_rate_negotiate` /
`resampler` / `rx_format` / `frame_analysis`，因此以下修正**自动生效**：

| 项 | 修正内容 | 出处 |
|---|---|---|
| 12-bit 数据格式 | AD9364 12-bit 装入 16-bit 容器高 12 位（shift=4），满量程 = ±2048 非 ±32768；`to_complex` 默认 `full_scale=2048` | `frame_analysis.hpp`、`pluto_tx.hpp kDacFullScale` |
| TX convert | TX 用 `iio_channel_convert_inverse` 把 16-bit 域转 12-bit DAC（旧代码直写 16-bit 10000 → DAC 取高 12 位 → peak=625 的 bug） | `pluto_tx.cpp` |
| 状态恢复 | `DeviceStateGuard` save/restore bool/RAII，防 use-after-free，参数恢复幂等 | `device_state_guard.hpp` |
| RF 安全天花板 | TX 衰减上限 **-40 dB**（`kSafeTxCeilingDb`），默认最大安全衰减 -89.75 dB，外接 RF 必须 `--confirm-safe-rf-path` | `pluto_tx.hpp` |
| 连续采集诚实化 | `collect_raw_contiguous` 单次 refill 判定连续，不循环拼接伪造连续流 | `board_common.hpp` |
| 逐帧分析 | 每 1024 点独立 Goertzel，不把 phase-broken 的多块拼成一条做全长 Goertzel（旧误报：全长 ratio 0.030 vs 逐帧 0.99998） | `frame_analysis.hpp analyze_frames` |

## 2. 十二类链的有意分歧（不是 bug，是域不同）

| 维度 | 第一批 Gate 5（8 类 FPGA/NPU 链） | 十二类链（本工程） |
|---|---|---|
| 输入容器 | int16 → float `count/32768` | int16 → float `count/2048` |
| 输出域 | **Q1.15** `clip(lround(count*scale))`，交 FPGA Mandatory Core 反量化 | **fp32 [2,1024]** 直通 NPU，无反量化 |
| receiver_scale | `sdr::ReceiverScale::calibrate_scale`（目标 Q1.15 RMS，如 8192） | `chain::calibrate_rec_scale`（目标 RMS=1.0，`target*2048/rms`） |
| 归一化 | 全局固定标量（同） | 全局固定标量（同，禁逐帧 RMS） |

**结论**：第一批 `receiver_scale.hpp` 的 `ReceiverScale`（Q1.15、满量程 32768）**不用于**
十二类链；十二类链改用 `chain_common.hpp` 的 `calibrate_rec_scale`（fp32、满量程 2048）。
两者公式不同（除以 2048 vs 32768；目标 RMS 1.0 vs Q1.15），**不可混用**。十二类链的定标
流程见 `docs/RECEIVER_SCALE_CALIBRATION.md`。

## 3. 逐门对应

| 十二类 Gate | 复用第一批哪些测试器逻辑 | 修正点 |
|---|---|---|
| Gate 6（SDR 预处理） | Gate 2 RX-only + Gate 5 重采样 | 用 `PreprocessChain`（fp32 直通）替代 Q1.15 定标；Goertzel 判据尺度无关 |
| Gate 7（NPU） | 无（NPU-only，参照 npu_stage_v1） | — |
| Gate 8（UI） | 无（格式化） | — |
| Gate 9（全链） | Gate 3/4 回环 + Gate 5 重采样 | 回环仅证「链活性」，不判分类正确；RF 需 `--confirm-safe-rf-path` |
