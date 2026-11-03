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
| RX 增益 | RX 控制 `voltage0`/`hardwaregain` | double | 10.0 dB（默认低增益） |
| TX 衰减 | TX 控制 `voltage0`/`hardwaregain` | double | 负数 = 衰减；默认 **-89.75 dB**（最大安全） |
| 回环 | phy `/loopback`（**debug** 属性） | longlong | `0`=关(外部射频) `1`=数字 `2`=内部射频 |

- 每次关键属性写入后 **读回**，读回不符契约 → 立即失败退出（`pluto_device_libiio.cpp`
  的 `wr_*` 全部写后读回，`pluto_tx.cpp` 判等）。

## 4. 射频安全（强制）

- 外部射频回环（`loopback==0`，信号从天线口发射）**默认禁止**：`pluto_tx.cpp::prepare()`
  在 `loopback==0 && !confirm_safe_rf_path` 时抛异常拒绝。
- 只有显式 `--confirm-safe-rf-path` 才允许外部发射。
- 数字回环（`loopback==1`）与内部射频回环（`loopback==2`）不对外发射，无需该确认。

## 5. TX 启动顺序（固定，`pluto_tx.cpp::prepare()`）

1. `save_params()` 快照原参数；
2. `tx_stop()` 确保 TX 关；
3. 设 TX 最大安全衰减 -89.75 dB（读回确认）；
4. RX 低增益 + `manual`；
5. 对齐 TX/RX LO；
6. **读回确认**每个关键值（不符 → 抛异常）；
7. 设 `loopback`；
8. （若工作衰减 ≠ 安全衰减）降到工作衰减。

`start_cyclic()` 建立 cyclic TX 缓冲并启动；**RX 的启动是调用方最后一步**。
退出/异常/Ctrl+C（SIGINT/SIGTERM）都必须：销毁 TX 缓冲 + 恢复全部参数（RAII 析构）。

## 6. receiver_scale（全局固定标量）

- 转换链（冻结，见 `sampling_and_iq_contract.md`）：
  `x_model = adc_count * (1/32768) * receiver_scale`；`Q1.15 = clip(lround(x_model*32768))`。
- `receiver_scale` 是**一个全局冻结标量**（默认 1.0），**禁止逐帧 RMS/AGC 归一化**；
  上板后用非盲重放标定并冻结（本批默认 1.0，标定留待实机）。

## 7. NCO 下变频偏移（运行时，不硬编码）

- NCO 频率偏移是运行时参数（Gate 5 用 `--tone` 传），**不写死**。
- 合法性校验：`|offset| + 信号带宽 < fs_in/2`，且避开 DC 保护带（`sdr_adapter/nco.hpp`）。
- 相位累加器为成员，跨 RX buffer 连续（无相位跳变）。

## 8. 状态与归属

- 本批（Gate 1–5）状态只标 **`READY-FOR-PLUTO-SDR-GATE1-5-TEST`**；
- 板端程序由用户本人上板运行，模型/FPGA/NPU/UI（Gate 6–9）不在本批范围。
