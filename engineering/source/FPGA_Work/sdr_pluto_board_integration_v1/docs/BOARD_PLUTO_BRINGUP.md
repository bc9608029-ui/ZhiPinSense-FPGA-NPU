# 板端 Pluto 逐门 Bring-up 指南（Gate 1–5）

> 本文件是权威上板步骤。**所有板端程序由用户本人上板运行**（本工程作者不碰板、不写 Flash）。
> 逐门执行，**失败即停**，修好再继续，不要跳门。每门通过判定只看
> `GATE_RESULT gate=... result=PASS ...` 一行与退出码。

## 0. 前置：板端编译

```bash
cd /path/to/sdr_pluto_board_integration_v1/board_package
./build_on_board.sh g++        # 用 g++，等效 -O2 -Wall -Wextra -Werror
```

- 需要板端能 `pkg-config` 到 libiio（否则用 `LIBIIO_CFLAGS`/`LIBIIO_LIBS` 覆盖，见脚本头）。
- 产出 5 个可执行文件到 `board_package/bin/`：`board_detect_pluto`、`board_rx_only`、
  `board_digital_loopback`、`board_rf_loopback`、`board_resampler_test`。
- 未编译时脚本以退出码 **125** 提示先编译。

所有逐门脚本会把命令与输出追加到 `logs/` 下对应 `.log`，同时 `tee` 到终端。

## 1. Gate 1 — 枚举与身份读回

```bash
scripts/board_detect_pluto.sh            # 可加 --uri=<iio_uri> 指定设备
```

**判据（PASS）**：
- 退出码 **0**；
- `GATE_RESULT gate=detect_pluto result=PASS`，且 `probe_count=1`（无 `reconnect_detected`）；
- detail 含 `rx_sample_rate=... tx_sample_rate=... rx_lo=... tx_lo=...`
  `rx_data_format="..." tx_data_format="..."` 全部读回成功（RX/TX 采样率与 LO 分开打印，
  数据格式从设备查询打印，不臆造 RX/TX 恒等、不臆造位宽）。

**注意**：
- `probe_count>1` → 判定为 USB 反复断连（warning），退出码 1；
- 读回失败（`readback_error=`）→ FAIL；
- **未找到设备**：最多 3 次探测（间隔 300 ms）后退出码 **2**，绝不回退 Mock、绝不挂起。

## 2. Gate 2 — RX-only 采集（环境噪声）

```bash
scripts/board_rx_only.sh --frames 64 --out rx_only_raw.bin
```

**判据（PASS）**：退出码 0；`GATE_RESULT gate=rx_only result=PASS`；detail 中
`short=0 overflow=0 drop=0 disc=0` 且 `frames>=64`、`saved=rx_only_raw.bin` 保存成功。

- 采样率协商通过（detail 含 `negotiated fs=...`），TX 已停，RX 手动低增益 10 dB。
- 用 PC 复核 `rx_only_raw.bin`：小端交织 int16，4096 字节/帧（1024 复数），
  **12-bit 有效位装入 16-bit 容器、左对齐（shift=4）**（见 `contracts/rx_iq_format_contract.md`，
  满量程 ±2048 非 ±32768）。

## 3. Gate 3 — 数字回环（无射频发射）

```bash
scripts/board_digital_loopback.sh --frames 128
```

**判据（PASS，逐 1024 点帧独立计算）**：退出码 0；`GATE_RESULT gate=digital_loopback result=PASS`；
detail 同时满足（`board_digital_loopback.cpp` → `board_common.hpp::run_loopback`）：
- `frame_count=128` 且 `frame_pass_count=128`（**逐帧** `ratio>0.3` 且频点门通过，共轭/
  I-Q 方向不一致会**报告而非掩盖**）；
- 每帧 `ratio_pos`/`ratio_neg` 独立计算，聚合输出 `frame_ratio_min/mean/max` 与
  `frame_freq_mean/frame_freq_max_error`（每帧频点与 ±10 kHz 最近距离 ≤ `freq_err_max`，
  默认 **300 Hz**，可用 `--freq-err` 覆盖，**不因本轮结果放宽**）；
- `peak<2048`（12-bit ADC 满量程 ±2048，无饱和，detail 中为聚合 `peak`/`rms`）；
- `short=0 overflow=0 drop=0 disc=0 timeouts=0`；
- `global_ratio` **仅诊断**（全长 Goertzel 会因块间相位断点相消到 ~0.03，属预期，
  **不参与 PASS**）。**`ratio>0.3` 门限绝不降低。**

> 为什么逐帧：Pluto 每次 `iio_buffer_refill` 返回 1024 点一个块，块内连续，但块与块之间
> 起始相位不连续（DMA 丢样/重同步）。把 128 块拼接后做一条全长 Goertzel 会让干净单音在
> 相位断点处相消 → 假 FAIL（板端实测逐帧 ratio≈0.99998 而全长 ratio=0.030，`restore_result=PASS`
> 却报 `FINAL FAIL`）。故判定全部落在逐帧，全长只作诊断。

- 走 `loopback=1`（数字回环），**不对外发射射频**，无需安全确认。
- 板端按固定顺序启动：停止 TX → 最大安全衰减 -89.75 dB → RX 低增益 manual → 对齐 TX/RX LO →
  读回确认 → 建立 cyclic TX → 最后启动 RX（`PlutoTx::prepare()`），参数快照/恢复由
  `DeviceStateGuard` 在协商前完成。
- TX 波形振幅是 **12-bit 计数（默认 1500）**：旧版写原始 16-bit 10000 因 12-bit DAC 只取
  高 12 位导致 peak=625（=10000>>4）——本轮已改为 `iio_channel_convert_inverse`，不要用旧
  数值判断。
- 失败自动保存 `digital_loopback_raw.bin` + `_dump.txt`（前 32 个 I/Q + 数据格式元数据），
  无需重跑即可诊断。

## 4. Gate 4 — 外部射频回环（**会发射 RF**）

```bash
scripts/board_rf_loopback.sh --confirm-safe-rf-path --frames 128
```

**判据（PASS）**：退出码 0；`GATE_RESULT gate=rf_loopback result=PASS`；同上（逐帧）
`frame_count=128 / frame_pass_count=128 / 每帧 ratio>0.3 / 频点门 ≤300Hz / peak<2048 /
short=0 overflow=0 drop=0 disc=0`，`global_ratio` 仅诊断。

**安全**：
- 不带 `--confirm-safe-rf-path` → 直接拒绝（退出码 1，`rf_path_not_confirmed`），**不发射**；
- 仅当你已确认天线口接好了电缆/衰减器/天线的合法射频路径，才显式加该 flag；
- 默认工作衰减 = **-40 dB 天花板**，`PlutoTx::prepare()` 先设 -89.75 dB 安全地板读回确认后
  再降到工作衰减，且**绝不高于 -40 dB**（独立硬限制）；RX 手动 **20 dB**；TX/RX LO 对齐；
  异常/Ctrl+C 全恢复。

## 5. Gate 5 — 重采样 + 定标（数字回环多音）

```bash
scripts/board_resampler_test.sh --samples 1024
```

> `--samples` 默认已从 4096 改为 **1024**：Gate 5 现在要求**单次连续 refill**得到全部源
> 采样（见下），而单次 `iio_buffer_refill` 的 DMA 缓冲容量有限，1024 点源采样在一次 refill
> 内取满。要测更长的连续流请先确认 `rx_buffer_capacity` 足够，否则短 refill 会 fail-closed。

**判据（PASS）**：退出码 0；`GATE_RESULT gate=resampler_test result=PASS`；detail 同时满足
（**五个维度严格分离**，见 `board_resampler_test.cpp`）：
- `freq_err_hz` 绝对值 < 10（下变频后单音应落在 ~0 Hz）；
- `dc_ratio > 0.9`（音调**频谱比**，量纲 1，集中度）；
- `tone_amp` 与 `expect_amp` 相对误差 < 20%（**复数幅度/RMS**，`expect_amp = tone_amp_in/2048×scale`）；
- `alias_db < -50`（**混叠抑制比/dB**：100 kHz 带外探针 − 10 kHz NCO = 90 kHz，抽取到
  128 kHz 后混叠到 **−38 kHz**，正负 ±38 kHz 都测）；
- `chunk_len_match=1` 且 `chunk_max_err<1e-4`（分块 vs 一次性重采样，数值误差比较**非** vector==）；
- `q115_sat=0`（Q1.15 无饱和）、`n_frames>=1`、`short=0 overflow=0 drop=0 disc=0`。

**连续流证据（本轮新增，Gate 5 硬门）**：detail 必须含
`single_refill=1` 且 `rx_buffer_capacity >= n_in`（一次 refill 取满全部源采样，`rx_refill_count`
增量 ==1）。**禁止**把多次 refill 拼接冒充连续流（块间相位断点会污染 passband 幅度/频点误差/
混叠抑制，也禁止拿相位断点数据定标 receiver_scale）；短 refill / 超时 / overflow / drop /
discontinuity 一律 **fail-closed**。

- 默认 `--tone 10000 --probe 100000 --tone-amp 1200 --probe-amp 800 --receiver-scale 1.0`
  （振幅是 **12-bit 计数**，`tone_amp + probe_amp < 2048` 防饱和）。
- 使用 `loopback=1`，**不对外发射**。
- 失败自动保存 `resampler_raw.bin`/`resampler_nco.bin`/`resampler_out.bin` 供离线诊断。

## 退出码速查

| 码 | 含义 |
|----|------|
| 0 | 该门 PASS |
| 1 | 该门 FAIL（含协商失败、流异常、读回不符、RF 未确认） |
| 2 | **设备未找到**（真 libiio 无设备，非 Mock 回退） |
| 125 | 可执行文件未编译（先 `build_on_board.sh`） |

## 上板通过后的状态

Gate 1–5 全部 `result=PASS` 后，本批才可从 `READY-FOR-PLUTO-SDR-GATE1-5-TEST`
进入下一阶段（Gate 6–9：离线分类 / FPGA 输入 / NPU 分类 / UI，另行启动）。
在此之前任何自动/离线结论都只保留 `READY-...` 措辞，不写 PASS。
