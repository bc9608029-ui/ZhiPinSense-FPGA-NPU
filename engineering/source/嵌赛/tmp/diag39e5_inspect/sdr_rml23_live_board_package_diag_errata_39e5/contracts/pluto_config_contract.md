# Pluto 配置契约（板端控制单台 ADALM-Pluto / AD9364）

> 本契约描述 FMQL30TAI 板端如何配置并控制单台 ADALM-Pluto（Rev.C，AD9364
> 1T1R，libiio）完成自发自收。可执行形式见 `sdr_adapter/pluto_device_libiio.cpp`
> 与 `sdr_adapter/pluto_tx.hpp`；本文件是规范性文字。数值未实测的标 **TBD**，
> 到板后逐门确认，不臆造。

## 1. 设备身份（libiio 拓扑，实测约定）

> 属性路由已统一并冻结在 `sdr_adapter/iio_attr_routing.hpp`（可执行形式），
> 本节约定其文字规范。**关键点：`sampling_frequency`/`rf_bandwidth`/
> `gain_control_mode`/`hardwaregain` 是 ad9361-phy 控制通道的 CHANNEL 属性，
> 不是设备属性，更不是 cf-ad9361-*-lpc 流通道的属性。**

| libiio 设备 | 名称 | 用途 |
|-------------|------|------|
| phy | `ad9361-phy` | 控制通道承载全部控制属性；`loopback` 是设备 **debug** 属性 |
| RX 流 | `cf-ad9361-lpc` | 仅 RX DMA 数据（`voltage0`/`voltage1` 输出 interleaved I/Q），**无控制属性** |
| TX 流 | `cf-ad9361-dds-core-lpc` | 仅 TX DMA 数据（`voltage0`/`voltage1`），**无控制属性** |

ad9361-phy 控制通道（属性平面）：

| 控制通道 | 定位 | 承载属性 |
|----------|------|----------|
| `voltage0` `output=false` | RX 控制 | `sampling_frequency`、`rf_bandwidth`、`gain_control_mode`、`hardwaregain` |
| `voltage0` `output=true` | TX 控制 | `sampling_frequency`、`rf_bandwidth`、`hardwaregain` |
| `altvoltage0` `output=true` | RX LO | `frequency` |
| `altvoltage1` `output=true` | TX LO | `frequency` |

- RX LO 通道 = phy `altvoltage0`，属性 `frequency`（channel 属性）；
- TX LO 通道 = phy `altvoltage1`，属性 `frequency`（channel 属性）。
- 流设备（`cf-ad9361-lpc` / `cf-ad9361-dds-core-lpc`）只做 DMA：RX `voltage0`+`voltage1`
  （output=false）与 TX `voltage0`+`voltage1`（output=true）**全部使能**，交织 int16 I/Q
  步长 = 2×sizeof(int16) = 4 字节（上板后复核）。

## 2. 采样率（写后读回，禁止静默近似）

- 目标模型采样率 **128000 Hz**（冻结，见 `sampling_and_iq_contract.md`）。
- 板端候选链（**顺序固定**，来自 `sdr_adapter/sample_rate_negotiate.cpp`）：
  1. **2560000 Hz**（首选，AD9364 可接受区间 [2.083M, 61.44M] 内），整数抽取 **×20**；
  2. **3840000 Hz**（AD9364 原生率），整数抽取 **×30**。
- 每个候选：把 `sampling_frequency` **分别**写入 phy RX 控制通道（`voltage0 output=false`）
  与 phy TX 控制通道（`voltage0 output=true`），**分别读回并各自判等**（RX 读回 ≠ 请求 或
  TX 读回 ≠ 请求 → 该候选失败；不臆造 RX/TX 恒等）→ 校验 `fs_in == 128000 * down`
  整数比成立 → 才接受。RX/TX 采样率在 save/restore 中亦**分开**保存恢复。
- **30.72 MHz ×240 不作为板端候选**：单级 ×240 抽取 FIR 数值不稳定（>6000 taps 仍 <57 dB），
  仅作 PC 测试记录（见 `docs/RESAMPLER_DESIGN.md`）。
- 全部候选遍历完仍失败 → 退出，**不猜**。

## 3. LO / 带宽 / 增益 / 衰减 / 回环

> 下表「属性路径」按 §1 的控制通道路由：RX 控制 = phy `voltage0 output=false`；
> TX 控制 = phy `voltage0 output=true`。全部为 **channel** 属性（`iio_channel_attr_*`），
> 唯 `loopback` 是 **debug** 属性（`iio_device_debug_attr_*`）。

| 参数 | 属性路径 | 类型 | 契约值 |
|------|----------|------|--------|
| RX LO | phy `altvoltage0`/`frequency` | longlong | 与 TX LO 对齐（=center_freq_hz） |
| TX LO | phy `altvoltage1`/`frequency` | longlong | 与 RX LO 对齐 |
| RX 带宽 | RX 控制 `voltage0`/`rf_bandwidth` | longlong | 运行时（TBD 上板读回确认） |
| TX 带宽 | TX 控制 `voltage0`/`rf_bandwidth` | longlong | 运行时（TBD） |
| RX 增益模式 | RX 控制 `voltage0`/`gain_control_mode` | string | `manual`（回环自测用，低增益） |
| RX 增益 | RX 控制 `voltage0`/`hardwaregain` | double | 10.0 dB（Gate 3/5 默认低增益）；**Gate 4 = 20.0 dB** |
| TX 衰减 | TX 控制 `voltage0`/`hardwaregain` | double | 负数 = 衰减；安全地板 **-89.75 dB**（先设）；工作衰减 **天花板 -40 dB**（绝不小于） |
| 回环 | phy `/loopback`（**debug** 属性） | longlong | `0`=关(外部射频) `1`=数字 `2`=内部射频 |

- 每次关键属性写入后 **读回**，读回不符契约 → 立即失败退出（`pluto_device_libiio.cpp`
  的 `wr_*` 全部写后读回，`pluto_tx.cpp` 判等）。
- **12-bit 计数域**：AD9364 是 12-bit 转换器（满量程 ±2048），TX 波形振幅与 RX
  数值映射都按 12-bit 计数（÷2048），见 `rx_iq_format_contract.md`。

## 4. 射频安全（强制）

- 外部射频回环（`loopback==0`，信号从天线口发射）**默认禁止**：`pluto_tx.cpp::prepare()`
  在 `loopback==0 && !confirm_safe_rf_path` 时抛异常拒绝。
- 只有显式 `--confirm-safe-rf-path` 才允许外部发射。
- 数字回环（`loopback==1`）与内部射频回环（`loopback==2`）不对外发射，无需该确认。
- **衰减天花板（独立硬限制）**：TX 衰减为负数，值越大（越接近 0）发射功率越强。
  无论是否已 `--confirm-safe-rf-path`，工作衰减**绝不小于 -40 dB**（`kSafeTxCeilingDb`），
  超限 `prepare()` 直接抛异常。启动先设安全地板 **-89.75 dB**，再逐步降到工作衰减，
  绝不跳变到高功率。

## 5. TX 启动顺序（固定，`pluto_tx.cpp::prepare()`）

> 参数快照/恢复**不在 PlutoTx 内**，而是调用方在**任何协商/写参数之前**用
> `DeviceStateGuard` 包裹设备（`sdr_adapter/device_state_guard.hpp`）。构造即
> `save_params()`，析构/`restore()` 用 `restore_params()`（返回 bool，失败报告
> `restore_result=FAIL`）；这样异常/Ctrl+C/提前返回都回到**协商前原状态**，且
> 析构顺序 PlutoTx → guard → device 保证不悬垂引用。

1. `tx_stop()` 确保 TX 关；
2. 设 TX 安全地板 -89.75 dB（读回确认）；
3. RX `manual` + 低增益（Gate 4 = 20 dB）；
4. 对齐 TX/RX LO（读回确认）；
5. 设 `loopback`（读回确认）；
6. （若工作衰减 ≠ 安全地板）降到工作衰减，**且 ≤ -40 dB 天花板**。

`start_cyclic()` 建立 cyclic TX 缓冲并启动；**RX 的启动是调用方最后一步**。
退出/异常/Ctrl+C（SIGINT/SIGTERM，只置 `sig_atomic_t` 标志不跑析构）都必须：
销毁 TX 缓冲（PlutoTx）+ 恢复全部参数（DeviceStateGuard）。

## 6. receiver_scale（全局固定标量）

- 转换链（冻结，见 `sampling_and_iq_contract.md`）：
  `x_model = adc_count * (1/2048) * receiver_scale`；`Q1.15 = clip(lround(x_model*32768))`。
  （12-bit 计数满量程 2048，**非 32768**，见 `rx_iq_format_contract.md`。）
- `receiver_scale` 是**一个全局冻结标量**（默认 1.0），**禁止逐帧 RMS/AGC 归一化**；
  上板后用非盲重放标定并冻结（本批默认 1.0，标定留待实机）。

## 7. NCO 下变频偏移（运行时，不硬编码）

- NCO 频率偏移是运行时参数（Gate 5 用 `--tone` 传），**不写死**。
- 合法性校验：`|offset| + 信号带宽 < fs_in/2`，且避开 DC 保护带（`sdr_adapter/nco.hpp`）。
- 相位累加器为成员，跨 RX buffer 连续（无相位跳变）。

## 8. RX 缓冲容量与逐帧判定（本轮修复的关键契约）

- **RX 缓冲不硬编码 1024**：`pluto_device_libiio.cpp::ensure_rx_buffer(capacity)` 按请求容量
  惰性创建（更大请求时重建），并记录 `rx_buffer_capacity` 与 `rx_refill_count`（`Device`
  接口暴露）。一次 `iio_buffer_refill` 返回的样本在**一个缓冲内是连续**的；**两次 refill
  之间因 DMA 丢样/重同步，块间起始相位不连续**。
- **因此禁止把多次 refill 拼接后当连续流做全长相干检测**（否则干净单音会在块间相位断点
  处相消，产生假 FAIL；板端实测逐帧 ratio≈0.99998 而全长 ratio=0.030）。
- **Gate 3/4 判定逐 1024 点帧独立计算**（每帧 `ratio_pos/ratio_neg`、`dominant_freq_hz`、
  `peak`、`rms`），聚合输出 `frame_count / frame_ratio_min|mean|max / frame_pass_count /
  frame_freq_mean / frame_freq_max_error`；`global_ratio`（全长 Goertzel）**仅诊断不参与 PASS**。
  - 每帧 PASS = `ratio>0.3`（max(pos,neg)）**且** `min(|f-tone|,|f+tone|) <= freq_err_max`；
  - `freq_err_max` 默认 **300 Hz**（10 kHz 的 3%，事先固定，**不因本轮结果放宽**）；
  - `ratio>0.3` 门限**绝不降低**。
- **Gate 5 连续流二选一（选 A）**：为 Gate 5 一次创建足够大的 RX buffer 并**单次 refill**
  得到全部源采样（`collect_raw_contiguous`），用 `rx_refill_count` 增量 ==1 且
  `rx_buffer_capacity>=n_in` 作为连续证据；短 refill / 超时 / overflow / drop / discontinuity
  一律 **fail-closed**，不拼接冒充连续流，**不拿相位断点数据定标 receiver_scale**。

## 9. 状态与归属

- 本批（Gate 1–5）状态只标 **`READY-FOR-PLUTO-SDR-GATE1-5-TEST`**；
- 板端程序由用户本人上板运行，模型/FPGA/NPU/UI（Gate 6–9）不在本批范围。
