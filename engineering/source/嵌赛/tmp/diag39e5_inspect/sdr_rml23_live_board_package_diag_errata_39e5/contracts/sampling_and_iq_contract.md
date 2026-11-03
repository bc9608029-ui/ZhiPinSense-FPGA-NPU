# 采样率与 IQ 数值契约（正式）

> 来源：`rf_cognitive_system/configs/deployment_contract.yaml`（FPGA 侧）、
> `rf_cognitive_system/configs/deployment_numerical_contract.yaml`（训练/换算侧）。
> 两份均为**冻结基线**，本文件只做整理与标注，不改变任何数值。
>
> 标注规则：
> - **冻结** = 不得修改（模型/FPGA 数值契约，本层只能遵守）；
> - **TBD** = 需 SDR 到货后确定（本层负责补齐，但**到货前不猜**）。

## 1. 两种采样率（必须区分）

| 项目 | 值 | 状态 | 归属 |
|------|----|----|------|
| 模型端目标采样率 | **128000 Hz**（`sample_rate_hz_reference: 128000`） | **冻结** | 模型/冻结 IQ/冻结 Tensor 已按此生成 |
| 符号率 | 16000 Hz（`samples_per_symbol = 8`） | 冻结 | 训练合成 |
| SDR 原始采样率 | 未指定 | **TBD** | 设备到货后确定 |

- 模型端 **128 ksps 已冻结**（写入本契约作为正式依据）。
- 若 SDR 原始采样率 ≠ 128 ksps，**必须**在 SDR 适配层做采样率转换到 128 ksps
  后再帧化；该转换只属于 SDR 适配层，不改冻结 Core、不改模型。
- 本地材料给出的候选能力边界（`sdr_transport.md`）：USB SDR 5 MS/s 可行 /
  10 MS/s 边缘 / 20 MS/s 超 USB2 480 Mbit/s；以太网 SDR 5/10 MS/s 有余量 /
  20 MS/s 在 1 GbE 下有条件；直接射频前端（AD936x 类）。板载 4×USB2.0 + 1×GigE。

## 2. 帧结构（冻结）

- 每帧 **1024 个复数样本**（`complex_samples: 1024`）；
- 帧间跳步 **1024 样本**（`hop_samples_initial: 1024`，无重叠）；
- 类别顺序（冻结）：BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM。
  > 这是**部署 Mandatory Core 的冻结输出顺序**（对应冻结 `model.raw` /
  > `reference_argmax.txt`）。它与模型侧的「当前 10 类 / 目标 12 类」是**三层关系**，
  > 见 §9。系统层（`sdr_adapter`）不写死 8 类，分类宽度由类别契约携带。

## 3. FPGA 输入 IQ 数值契约（冻结）

`deployment_contract.yaml#fpga_input`：

| 项 | 值 |
|----|----|
| 布局 | `interleaved_iq`，字序 `[I, Q]` |
| 标量类型 | `signed_int16`（小端，与 aarch64/冻结 iq_input.bin 一致） |
| 二进制点 | 15（Q1.15） |
| AXI-Stream tdata 位宽 | 32 |

`deployment_numerical_contract.yaml#sdr_reference_conversion`（SDR 适配层换算公式）：

```
x_model[n] = adc_count[n] * adc_lsb * receiver_scale
adc_lsb_reference      = 0.000030517578125   (= 1/32768)
receiver_scale_reference = 1.0                (全局冻结标量 s_adc)
per_record_rms_normalization = forbidden       (禁止逐帧 RMS 归一化)
```

- `receiver_scale` 是**一个全局冻结标量**，不是逐帧值；需用非盲重放数据标定并
  冻结（`note: receiver_scale must be calibrated and frozen using non-blind
  replay data`）。
- 量化器本体（`multiplier=127/shift=15`，IQ；`127/shift=31`，physical）保存在
  **冻结 Mandatory Core 内部**，本层不得修改；SDR 适配层只负责把真实 ADC 样本
  映射到「等价于冻结 IQ」的 int16 尺度。

## 4. physical 前端三平面（冻结）

`deployment_contract.yaml#fpga_features` + `deployment_numerical_contract.yaml#physical_frontend`：

| 平面 | 公式 | 位宽 |
|------|------|------|
| power | `I·I + Q·Q` | 32（无符号） |
| lag1_real | `I[n]·I[n-1] + Q[n]·Q[n-1]` | 33（有符号） |
| lag1_imag | `Q[n]·I[n-1] - I[n]·Q[n-1]` | 33（有符号） |

- 首样本 lag = **确定性 0**（`first_lag_sample: zero` / `lag1_first_sample:
  deterministic_zero`）。
- 量化方式：`calibrated_symmetric_saturating_round_to_nearest`。

## 5. int8 参考尺度与 NPU 输入输出（冻结，归属模型）

`deployment_numerical_contract.yaml#int8_reference_test_scales`：

| 张量 | int8 尺度 | 反量化 |
|------|-----------|--------|
| iq | 0.007874015748031496 (= 1/127) | `iq × 1/127` |
| power / lag_real / lag_imag | 0.015748031496062992 (= 2/127) | `× 2/127` |

- 饱和 `[-127, 127]`，round `nearest_ties_away_from_zero`，zero point 全为 0。
- NPU 输入：`iq` `[1,2,1024]`、`physical_features` `[1,3,1024]`（NCL，
  reference float32 → planned int8）；输出 `logits` `[1,8]`。
- 注意：这些是 **reference-test** 尺度；最终 NPU 尺度来自训练分布标定（`note:
  Final NPU scales must come from training-distribution calibration`）——属于
  **模型侧**，本层不触碰。
- 输出 `logits` 宽度随模型变化：**冻结 8**（部署）/ **当前 10**（V1.1）/ **目标 12**
  （预留，见 §9）。系统层（`sdr_adapter`）通过 `cat::Contract` 携带宽度，**不写死 8 类**。

## 6. 初始划分（冻结）

`deployment_contract.yaml#initial_partition`：
- `dc_removal_in_amr_path = bypass`（AMR 路径不做 DC 去除）；
- `fir_in_amr_path = bypass`（AMR 路径不做 FIR）；
- `fft_in_amr_path = false`（FFT 仅用于可选监控 PSD/能量检测）。

## 7. 待确认（TBD，本层负责在 SDR 到货后补齐）

- SDR 物理接口与采样时钟（`todo_hardware: Confirm SDR physical interface and
  sample clock`）；
- SDR 原始采样率（决定是否/如何重采样到 128 ksps）；
- 若存在采样率转换：转换算法、抗混叠、组延迟，均只落在 SDR 适配层。

## 8. 边界（禁止）

- 不修改 `deployment_contract.yaml` / `deployment_numerical_contract.yaml` 的任何
  冻结数值；
- 不做逐帧 DC/CFO/IQ 不平衡补偿、不做逐帧 RMS/AGC 归一化（与冻结训练分布冲突）；
- 不猜 SDR 驱动 API / VID:PID / 采样格式（float32/int12/int16），到货前不实现
  `SdrIqSource`（现改为：已知设备 ADALM-Pluto，用**运行时配置**承载参数、用
  **mock IIO 后端**离线验证，真实 libiio 后端**可选编译**，见 §10）。

## 9. 类别契约（三层：冻结 8 / 当前 10 / 目标 12）

分类输出宽度**不在系统层写死**，由 `sdr_adapter/categories.hpp` 的 `cat::Contract`
携带（合法范围 `[8,16]`，`cat::is_valid` 校验）。三层各自有 provenance 标注，禁止
混淆：

| 契约 | 宽度 | 顺序（= logits 索引顺序） | 状态 |
|------|------|---------------------------|------|
| `cat::frozen_8()` | 8 | BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM | **冻结**（部署 Mandatory Core；对应 `model.raw`/`reference_argmax.txt`，不改） |
| `cat::current_10()` | 10 | AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM | 当前（V1.1 AMR 模型） |
| `cat::target_12()` | 12 | OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM | **预留**（未来模型，非当前输出） |

- 权威顺序：**12 类**已统一固定为 OOK, 4ASK, AM-DSB, WBFM, 2FSK, **GFSK**, BPSK,
  QPSK, 8PSK, 16QAM, 64QAM, OFDM（2026-10-05，见 `sdr_adapter/categories.hpp`
  `cat::target_12()`）；**10 类**为 V1.1 AMR 模型顺序（`cat::current_10()`）；
  **8 类**来自 `board_package/continuous_joint_stress.cpp` 与本文 §2。
- `hdmi_framebuffer_ui_v3` 是**已废弃历史版本**，其 `model_contract.cpp` 的
  `contract_target_12()` 旧 `GFSK/GMSK` 契约**已失效**，不再作为 12 类顺序的权威
  来源；本工程不再引用该源码。
- **冻结 8 与模型侧 10/12 是两套独立顺序**，勿按名称拼接、勿互相替换。板级压测
  （`continuous_joint_stress.cpp`）仍绑定冻结 8；系统层的分类接口按运行时契约宽度
  输出 N 类。

## 10. ADALM-Pluto（libiio）接口层（可选编译）

已知 SDR 设备为 **ADALM-Pluto（AD9363，libiio，USB）**。接口层
`pluto::PlutoIqSource`（`sdr_adapter/pluto.hpp`）：

- **运行时配置** `pluto::Config` 承载 8 项参数，**0 / "" = 未指定**，不臆造实测值：
  `uri`、`center_freq_hz`、`sample_rate_hz`、`rf_bandwidth_hz`、`gain_mode`、
  `gain_db`、`buffer_length`、`timeout_ms`（与 `cfg::Config` 的 `pluto_*` 字段对应）。
- **可选编译**：默认（无 libiio）`make_backend()` 返回 mock 后端供离线测试；定义
  `SDR_ADAPTER_HAVE_LIBIIO` 时链接真实 libiio 后端（`pluto_libiio.cpp`）后才谈真设备。
- **离线验证**（无 Pluto）用 `iio::MockBackend`（`sdr_adapter/mock_iio.hpp`）覆盖：
  连续缓冲、短读、超时、overflow、discontinuity、frame_id 连续性、断流恢复、背压。
- 设备参数与 `receiver_scale` 标定值仍是**到货后非盲重放确定**，本层不猜。
