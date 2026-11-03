# RX IQ 数据格式契约（Pluto / AD9364 原始 RX 样本）

> 可执行形式：`sdr_adapter/rx_format.hpp`（`sdr::RxFormat` + `canonical_rx_format()`）
> 与 `sdr_adapter/pluto_device.hpp`（`pluto::DataFormatInfo` + `describe_data_format()`）。
> 本文件是规范性文字。**数据格式一律从设备 `iio_channel_get_data_format` 实测查询，
> 绝不臆造**：板端 Gate 1 打印 `rx_data_format`/`tx_data_format`（length/bits/shift/
> is_signed/is_be/repeat），Gate 3 依此按位解包。下表「状态=实测」指 PC 侧已按
> libiio 0.26 源码确认的语义，板端查询值若有出入以板端打印为准并**停下来报告**。

## 1. 容器与通道布局

| 字段 | 值 | 状态 |
|------|----|----|
| 交织方式 | `interleaved`（`[I0,Q0,I1,Q1,...]`） | 查询 |
| Q 相对 I 的偏移 | 1 个 int16 槽 | 查询 |
| 通道数 | 2（I、Q 各为 AD9361 独立通道） | 查询 |
| 复基带方向 | `z = I + jQ`；正频率 = `cos + j·sin`，**无谱翻转** | 实测（PC 数字回环 ratio 0.9999） |

## 2. 数值精度（关键修正）

AD9364 是 **12-bit 转换器装入 16-bit 有符号容器**，12 个有效位在**高 12 位**
（`shift=4`，左对齐/MSB-aligned），低 4 位为 0——**不是**右对齐/LSB-aligned。
`iio_channel_convert`（libiio 0.26 `channel.c` 源码确认）先右移 `shift` 位再按符号
扩展（当 `is_fully_defined=false`），因此**主机 int16 满量程是 ±2048（2¹¹），
不是 ±32768**。这就是 Gate 3 老代码 peak=625 的根因：旧的 TX 不经过
`iio_channel_convert_inverse` 直接写原始 16-bit 10000，12-bit DAC 只取高 12 位 →
10000>>4 = 625。

| 字段 | 值 | 状态 |
|------|----|----|
| 容器位宽 | 16 bit（int16） | 查询 |
| 有效位宽 | 12 bit | 查询 |
| 对齐 | 左对齐（MSB-aligned），`shift=4` | 查询（AD9364 典型值） |
| 符号扩展 | `is_fully_defined=false` → 转换时符号扩展到 16 bit | 查询 |
| 主机满量程 | ±2048（**非 ±32768**） | 由 12-bit + shift 推导 |
| 字节序 | 小端（LE） | 实测（与 aarch64 / 冻结 IQ 一致） |

## 3. 数值映射（连接 receiver_scale）

- 主机 int16 样本 = 已 `iio_channel_convert` 的 12-bit 计数（满量程 2048）；
  `x_model = count * (1/2048) * receiver_scale`（冻结，**÷2048 非 ÷32768**）。
- TX 方向对称：`iio_channel_convert_inverse` 把 int16 掩码到低 12 位再左移 4 位。
- `receiver_scale` 全局固定标量（默认 1.0），不做逐帧归一化。
- 每复数样本 = 2 个 int16 槽 = 4 字节（`bytes_per_complex == 4`）。

## 4. 缓冲语义（`iio::RawChunk`，复用 `iio_backend.hpp`）

每次 RX 读返回：

| 字段 | 含义 | 板端判据（Gate 2–5） |
|------|------|----------------------|
| `samples_available` | 本次实际样本数（复数） | 累加直到目标帧数 |
| `samples` | 交织 int16 指针 | 直接 `to_complex` |
| `overflow` | 缓冲溢出 | 必须为 0 |
| `dropped` | 丢样本 | 必须为 0 |
| `discontinuity` | 流不连续 | 必须为 0 |
| `timed_out` | 读超时 | 有界重试，计数报告 |
| `broken` | 设备/流失效 | 立即失败退出 |
| `eos` | 流结束 | 短帧计数 |

- 短读（`short_block`）会在 `board::collect_raw` 中有界重试，超过 100 次空/超时轮询
  标记 `short_block` 并返回，不无限自旋。

## 5. 帧化（冻结）

- 每帧 **1024 个复数样本**（= 2048 个 int16 = 4096 字节），见 `sampling_and_iq_contract.md`。
- 尾部不足 1024 复数 **明确丢弃并计数**，不补零冒充。

## 6. 未确认项（上板 Gate 1–5 时逐门确认）

- 板端 `iio_channel_get_data_format` 查询返回的 **精确** shift/bits/length（预期
  shift=4、12-bit-in-16，但以板端打印为准；不符即停并报告，不覆盖）；
- RX/TX 带宽的实际读回值；
- 数字回环通带增益（预期 ≈1.0，PC 实测 ratio 0.9999）。
