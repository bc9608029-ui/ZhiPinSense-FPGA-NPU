# 任务 39e5 第一批交付报告：单台 Pluto 板端自发自收（Gate 1–5）

**状态：`READY-FOR-PLUTO-SDR-GATE1-5-TEST`**（离线验证完成，待用户本人上板逐门复测；
在板端 Gate 1–5 全 PASS 前，不写任何 PASS / READY 措辞）。

## 0. 范围与归属

- 本批只覆盖 **Gate 1–5**（枚举 / RX-only / 数字回环 / 射频回环 / 重采样+定标）。
- **不含** FPGA / NPU / UI（Gate 6–9），也不接十类模型。现存 8 类 `rfnet_npu` 模型仅作
  资产审计记录，**本批不接入、不冒充十类**；十类 NPU 编译产物不存在，留待后续。
- 板端程序**全部由用户本人上板运行**；作者不碰板、不写 Flash。
- 射频外部发射默认禁止，仅显式 `--confirm-safe-rf-path` 启用。

## 1. 交付内容（对应交付清单 1–13）

1. 新工程绝对路径：`F:\FPGA_Work\sdr_pluto_board_integration_v1\`。
2. 新建/修改文件清单：见本报告 §4（相对路径 + SHA，SHA 见 `SHA256SUMS.txt`）。
3. 复用文件清单 + 冻结 SHA：见 §5（证明 `sdr_preparation_v1/v2_latency_fix/v3_logging_fix`
   及 UI/模型/RTL/XDC/位流原工程**未改动**）。
4. `contracts/pluto_config_contract.md`：Pluto 配置契约（设备身份 / 采样率协商 / LO/带宽/
   增益/衰减/回环属性映射 / 射频安全 / TX 启动顺序 / receiver_scale / NCO offset）。
5. `docs/RESAMPLER_DESIGN.md`（含 `docs/resampler_response.png` 频率响应与混叠抑制图）。
6. 重采样 Golden 测试结果：见 §2。
7. TX 安全状态机说明：见 §3 与 `contracts/pluto_config_contract.md` §4–5。
8. `contracts/rx_iq_format_contract.md`：RX IQ 数据格式契约。
9. receiver_scale 标定方法：见 §3 与 `tools/receiver_scale_golden.py`。
10. 逐门命令 + 判据：`docs/BOARD_PLUTO_BRINGUP.md`（Gate 1–5）。
11. 完整 SHA 清单：`SHA256SUMS.txt`（`sha256sum -c` 自校验）。
12. 板端软件包：`sdr_pluto_gate1_5_board_package.tar.gz` + SHA-256。
13. 本文件 `docs/REPORT.md`。

## 2. 主机测试与 Golden 验证（PC，WSL g++ 15.2 -O2 -Werror）

- `host_tests/build_host_tests.sh` 编译 9 套：`test_all`、`test_nco`、`test_attr_routing`、
  `test_receiver_scale`、`test_rx_format`、`test_resampler`、
  `test_sample_rate_negotiate`、`test_pluto_tx`、`test_device_state_guard`；
  **-Wall -Wextra -Werror 零告警**。
- `host_tests/run_tests.sh` 全跑 **413/0**（无失败）：
  - `test_all`（复用回归，类别契约/ResultFrame/UnixSocket/配置/Pluto 分帧等）212/0；
  - `test_attr_routing` 35/0（属性路由表锁定，见 §8）、`test_nco` 9/0、
    `test_receiver_scale` 25/0、`test_rx_format` 17/0、`test_resampler` 30/0、
    `test_sample_rate_negotiate` 20/0、`test_pluto_tx` 45/0、`test_device_state_guard` 20/0。
- `host_tests/run_tests_asan.sh`：9 套在 **ASan+UBSan** 下全 PASS（零泄漏/零 UB）。
- `host_tests/link_libiio_host_check.sh`：5 个板端门程序对**真实 libiio 0.26**（x86_64
  sysroot）**编译+链接**全通过。
- Golden 一致（C++ vs Python 参考）：
  - `tools/resampler_golden.py`：polyphase 恒等式 float64 参考，C++ `test_resampler`
    逐样本比对通过（Golden2p56M / Golden3p84M / BruteForceMatch / ChunkInvariance /
    AntiAlias 全 PASS）。
  - `tools/nco_golden.py`、`tools/receiver_scale_golden.py`：自校验通过（下变频到 DC、
    相位连续、reset；Q1.15 饱和/一致性）。
  - FIR 系数 **C++ 与 PC 参考共用同一套**（`fir_coeffs.h` ≡ `fir_coeffs.json`），
    阻带衰减实测 2.56M→**72.8 dB**、3.84M→**73.0 dB**（`docs/resampler_response.png`）。
- 板端程序 5 个门程序：主机侧 **-fsyntax-only 全过** + 对真 libiio（x86_64 sysroot）
  **编译+链接通过**；无设备时快速失败（退出码 2，"device not found"，3 次探测，无 Mock
  回退、无挂起）。

## 3. 关键机制说明

- **采样率协商**：板端候选链固定 `2.56M(×20) → 3.84M(×30)`，写后读回判等、校验
  `fs_in==128000×down` 整数成立才接受；**30.72M(×240) 不作为板端候选**（单级 ×240 抽取
  FIR 数值不稳定），仅 PC 测试记录。全部失败即退出，不猜。
- **TX 安全状态机（`pluto_tx.cpp`）**：启动顺序固定 —— 保存原参数 → 停止 TX → 最大安全
  衰减 -89.75 dB → RX 低增益 manual → 对齐 TX/RX LO → **读回确认** → 建立 cyclic TX →
  **最后启动 RX**；退出/异常/Ctrl+C（SIGINT/SIGTERM）由 RAII 析构销毁 TX buffer 并恢复
  全部参数。
- **receiver_scale**：全局固定标量（默认 1.0），转换链 `x=count·(1/32768)·scale`，
  `Q1.15=clip(lround(x·32768))`；**禁止逐帧 RMS/AGC 归一化**；上板后非盲标定冻结（标定
  流程：已知单音/RMS 波形 → 测 ADC RMS/peak/clipping/noise-floor → 反推 scale → 记录
  SNR、Q1.15 饱和比 → 稳定后冻结）。

## 4. 新建/修改文件清单（本工程内，SHA 见 `SHA256SUMS.txt`）

```
sdr_adapter/resampler.hpp/.cpp         流式有理数重采样器（polyphase FIR）
sdr_adapter/fir_coeffs.h               编译期 FIR 系数（2.56M/3.84M）
sdr_adapter/nco.hpp                    数字下变频 NCO（跨 buffer 相位连续）
sdr_adapter/receiver_scale.hpp/.cpp    receiver_scale 定标 + Q1.15
sdr_adapter/pluto_tx.hpp/.cpp          PlutoTx 安全状态机（RAII 恢复）
sdr_adapter/device_state_guard.hpp     DeviceStateGuard（参数快照/恢复 RAII，restore 返回 bool）
sdr_adapter/pluto_device.hpp/.cpp      Device 抽象 + 真 libiio 实现（数据格式查询/参数/cyclic TX/convert）
sdr_adapter/sample_rate_negotiate.hpp/.cpp  采样率协商
sdr_adapter/rx_format.hpp              RX 数据格式契约
board_package/board_detect_pluto.cpp   Gate 1
board_package/board_rx_only.cpp        Gate 2
board_package/board_digital_loopback.cpp  Gate 3
board_package/board_rf_loopback.cpp    Gate 4
board_package/board_resampler_test.cpp Gate 5
board_package/board_common.hpp         门程序共享助手（Goertzel/采集/结果）
board_package/build_on_board.sh        板端原生编译
board_package/CMakeLists.txt           CMake 备选构建
host_tests/test_{resampler,nco,receiver_scale,pluto_tx,sample_rate_negotiate,rx_format}.cpp
host_tests/test_all.cpp                扩展回归（复用 v1 29 组框架）
host_tests/test_attr_routing.cpp       属性路由表单测（Gate 1 修复，见 §8）
host_tests/test_device_state_guard.cpp 状态快照/恢复单测（见 §9）
host_tests/build_host_tests.sh / run_tests.sh
host_tests/run_tests_asan.sh           ASan+UBSan 全量回归
host_tests/link_libiio_host_check.sh   主机对真 libiio 的编译+链接门
sdr_adapter/iio_attr_routing.hpp       冻结的 AD9361 属性路由表（见 §8）
tools/gen_fir_coeffs.py                FIR 系数生成（remez）
tools/resampler_golden.py / nco_golden.py / receiver_scale_golden.py
tools/plot_resampler_response.py       频率响应/混叠抑制图
tools/make_fix_patch.sh                Gate 1 修复补丁打包
tools/make_sha256sums.sh               SHA 清单再生成
pluto_libiio_fix_patch.tar.gz          Gate 1 修复补丁（含 README_FIX.md + 自校验 SHA）
scripts/board_{detect_pluto,rx_only,digital_loopback,rf_loopback,resampler_test}.sh
contracts/pluto_config_contract.md / rx_iq_format_contract.md
docs/REPORT.md / BOARD_PLUTO_BRINGUP.md / RESAMPLER_DESIGN.md
```

## 5. 复用文件清单 + 冻结 SHA

复用自 `sdr_preparation_v1/sdr_adapter/`（复制后逐字节一致）：`iq_frame.hpp`、
`iio_backend.hpp`、`pluto.hpp`、`pluto_libiio.cpp`、`mock_iio.hpp`、`categories.hpp`、
`config.hpp`、`result_frame.hpp`、`unix_socket_sink.hpp`、`logging.hpp`、
`sequence_monitor.hpp`、`preprocess.hpp`、`classify.hpp`、`pipeline.hpp`、
`perf_stats.hpp`、`offline_chain.hpp`、`ui_report.hpp`、`iq_source.cpp`。

冻结 SHA 已并入 `SHA256SUMS.txt`；原工程 `sdr_preparation_v1/v2_latency_fix/v3_logging_fix`
与 `hdmi_framebuffer_ui_v5_visual`、模型训练工程 **均未修改**。

## 6. 验证结论

| 验证项 | 结果 |
|--------|------|
| 主机 9 套测试（-Werror 零告警） | 413/0 全 PASS |
| ASan+UBSan 9 套 | 全 PASS（零泄漏/零 UB） |
| 属性路由表单测 `test_attr_routing` | 35/0 |
| 重采样 C++ vs Python Golden 一致 | PASS |
| NCO / receiver_scale Golden | PASS |
| FIR 阻带衰减（2.56M/3.84M） | 72.8 / 73.0 dB |
| 板端门程序对真 libiio 编译+链接 | PASS（无设备 exit 2 快速失败） |
| 冻结一致（复用文件 SHA 逐字节一致） | PASS |
| 打包自校验 `sha256sum -c` | PASS（主清单 107 文件 + 补丁 13 文件） |
| **板端 Gate 1–5** | **待用户本人上板**（`BOARD_PLUTO_BRINGUP.md`） |

## 7. 后续（本批不做）

Gate 1–5 板端 PASS 后启动 Gate 6–9；分类器走 `classify::Classifier` 抽象，用 8 类冻结
模型验证通路、标 `NPU_10CLASS_ARTIFACT_MISSING`，十类 NPU 产物由训练侧编译后替换。

## 8. Gate 1 上板失败 → Pluto libiio 属性路由修复（本轮）

用户上板 Gate 1 实测失败：`GATE_RESULT gate=detect_pluto result=FAIL
readback_error=pluto: read sampling_frequency failed`（枚举成功，读回失败）。

**根因**：`pluto_device_libiio.cpp` 用 `iio_device_attr_read_longlong(phy_,
"sampling_frequency", …)` 读采样率，并把 `rf_bandwidth`/`gain_control_mode`/`hardwaregain`
写到 `cf-ad9361-lpc` 流通道、把 `loopback` 当普通设备属性。AD9361/Pluto 的正确映射是：

- `sampling_frequency` / `rf_bandwidth` / `gain_control_mode` / `hardwaregain` 是
  `ad9361-phy` **控制通道**（RX=`voltage0 output=false`，TX=`voltage0 output=true`）的
  **channel 属性**，**绝不**用 `iio_device_attr_*`、**绝不**写到流通道。
- `loopback` 是 `ad9361-phy` 的 **debug 属性**（`iio_device_debug_attr_*`）。
- 流设备 `cf-ad9361-lpc` / `cf-ad9361-dds-core-lpc` **只做 DMA**，无控制属性。

**修复**（全部离线完成并验证，未上板）：

1. 新增 `sdr_adapter/iio_attr_routing.hpp`：把上述映射冻结为**纯、可测**的路由表
   （`route_ad9361_attr(name, dir) -> {target, api}`），真实后端据此解析到具体句柄。
2. 重写 `sdr_adapter/pluto_device_libiio.cpp`：控制通道/流通道/debug 属性正确路由；
   RX/TX 采样率**分开**读写保存恢复（不臆造恒等）；RX 缓冲**惰性创建**（先配置后建，
   规避 EBUSY）；`read_rx` 用 `iio_context_set_timeout` + `iio_buffer_refill` 映射
   `-ETIMEDOUT`→`timed_out`，无法设置超时则 fail-closed（不静默忽略 `timeout_ms`）；
   `open()` 校验 interleaved int16 步长 == 2×sizeof(int16) 并 `verify_routing()`。
3. 修 `sdr_adapter/pluto_libiio.cpp` 同源 bug（RX-only 后端）：`phy_rx_ch_` 发现 +
   属性改走 channel 属性 + `try_attr` 打印 errno 码 + 字符串。
4. `board_package/board_detect_pluto.cpp`：Gate 1 分开打印 `rx_sample_rate=` /
   `tx_sample_rate=` / `rx_lo=` / `tx_lo=` / `format=`；读回失败打印 libiio errno 码+字符串。
5. 单测：`host_tests/test_attr_routing.cpp`（35 断言，锁定 10 路由 + 反向用例 + 断言无
   `kDevice` 路由）；`FakePlutoDevice` 同步拆分为 RX/TX 采样率。
6. 验证：8 套主机测试 **384/0**（-Werror 零告警）、ASan+UBSan 全 PASS、两个 libiio
   后端对 libiio 0.26 头编译通过、5 个板端门程序对真 libiio 链接通过、既有
   `build_libiio_gate.sh` 仍 PASS（无设备 `device not found` 快速失败）。
7. 交付补丁 `pluto_libiio_fix_patch.tar.gz`（含 `README_FIX.md` + 自校验 SHA256SUMS，13
   文件 `sha256sum -c` 全 OK）；上板步骤：解包覆盖 → `./build_on_board.sh g++` →
   `scripts/board_detect_pluto.sh` → 逐门 Gate 2–5。

**归属**：本修复只改软件（属性路由/单测/文档），**不碰** RTL / bitstream / 模型 / UI；
板端程序仍由**用户本人**上板运行。状态仍为 **`READY-FOR-PLUTO-SDR-GATE1-5-TEST`**，
Gate 1–5 板端全 PASS 前不写 PASS。

## 9. Gate 3 上板失败 → 12-bit 数据格式 + TX convert + 状态恢复修复（本轮）

用户上板 Gate 1（PASS）、Gate 2（RX-only PASS）后，Gate 3 实测失败：
`GATE_RESULT gate=digital_loopback result=FAIL ratio=0.017670 peak=625
short=0 overflow=0 drop=0 disc=0 timeouts=0 (tone_not_detected)`（exit 1）。据此逐项审计
Gate 3，并**完整审计 Gate 4、Gate 5**，一次性修复，避免逐门再犯基础错误。

### 根因（经 libiio 0.26 `channel.c` 源码确认，非猜测）

1. **12-bit-in-16-bit + shift=4**：AD9364 是 12-bit 转换器，有效位在 16-bit 容器的
   **高 12 位**（`shift=4`，左对齐）。`iio_channel_convert` 右移 4 位后按符号扩展
   （`is_fully_defined=false`），主机 int16 满量程是 **±2048（2¹¹），不是 ±32768**。
2. **旧 TX 不走 `iio_channel_convert_inverse`**：旧代码直接写原始 16-bit 振幅 10000，
   12-bit DAC 只取高 12 位 → `10000 >> 4 = 625`。这就是 `peak=625` 的来源：**TX 发的是
   625 而不是 10000**，回环后 RX 收到的单音幅度 ~625、能量被噪声淹没，ratio=0.0177 判
   `tone_not_detected`。
3. **状态恢复的悬垂/顺序问题**：旧代码在「删 Device 前仍被 TX 引用」的顺序下析构，
   存在 use-after-free 风险；参数快照/恢复散落在 PlutoTx 里，异常/Ctrl+C 路径不可靠。

### 修复（全部离线完成并验证，未上板）

1. **数据格式查询 + 按位解包**：`pluto_device.hpp` 新增 `DataFormatInfo`
   （length/bits/shift/is_signed/is_fully_defined/is_be/repeat），`query_fmt` 从
   `iio_channel_get_data_format` 实测读取；Gate 1 打印 `rx_data_format`/`tx_data_format`；
   `read_rx` 用 `iio_channel_convert`、`tx_start_cyclic` 用 `iio_channel_convert_inverse`，
   步长用每通道真实 `buffer_first`+`step`。TX 波形振幅改用 12-bit 计数（默认 1500）。
2. **数值映射 ÷2048**：`to_complex`、`receiver_scale` 契约、单测全部从 ÷32768 改 ÷2048。
3. **状态恢复 `DeviceStateGuard`**：新增 `sdr_adapter/device_state_guard.hpp`
   （构造即 `save_params()`，`restore()` 幂等返回 bool，析构自动恢复）；5 个门程序统一
   用 `unique_ptr<Device>` + `unique_ptr<DeviceStateGuard>` 外层持有，保证析构顺序
   PlutoTx → guard → device，**禁止删 Device 而 TX 仍引用**；恢复后读回并打印
   `restore_result=PASS|FAIL` + 全部参数。SIGINT/SIGTERM 只置 `sig_atomic_t` 标志，不跑析构。
4. **Gate 3 判据收紧**：单音检测同时算 `ratio_pos`/`ratio_neg`（共轭/I-Q 方向不一致会
   **报告而非掩盖**）；`peak<2048`（12-bit 满量程，非旧 32000）；失败自动保存
   `digital_loopback_raw.bin` + `_dump.txt`（前 32 个 I/Q + 数据格式元数据）。
5. **Gate 4 射频安全审计**：默认 `loopback=0` 仍须 `--confirm-safe-rf-path`；新增**独立
   衰减天花板 `kSafeTxCeilingDb=-40 dB`**（无论是否已确认，工作衰减绝不高于 -40 dB，超限
   `prepare()` 抛异常）；默认 RX 手动 20 dB、TX 衰减 -40 dB；先设 -89.75 dB 安全地板读回
   确认后再降到工作衰减，绝不跳变到高功率。
6. **Gate 5 指标维度分离审计**：严格分离 **音调频谱比**（`dc_ratio`，量纲 1）、**复数
   幅度/RMS**（`tone_amp` vs `expect_amp=a_in/2048×scale`）、**混叠抑制比/dB**
   （`alias_db<−50`，±38 kHz 都测）、**频率误差**（`dominant_freq_hz`）、**分块 vs 一次性
   数值误差**（`chunk_max_err<1e-4`，非 `vector==`）、**receiver_scale 统计**
   （input RMS/scale/output RMS/Q1.15 peak/饱和数）；NCO 旋转方向 `exp(-j·phase)`；失败
   保存 `resampler_raw.bin`/`resampler_nco.bin`/`resampler_out.bin`。
7. **单测补齐**（Section 五要求）：`test_pluto_tx.cpp` 增至 45 断言（数据格式/±频、
   `-40 dB` 天花板拒绝、`--confirm-safe-rf-path` 拒绝、状态恢复、12-bit 振幅安全）；
   新增 `test_device_state_guard.cpp`（快照/恢复往返、幂等、RAII、`restore_ok=false`
   fail 钩子、提前 return 仍恢复）。
8. **验证**：9 套主机测试 **413/0**（-Werror 零告警）、ASan+UBSan 全 PASS、5 个板端
   门程序对真 libiio 0.26 **编译+链接**通过、契约/上板文档同步（12-bit ÷2048、I-Q 方向、
   -40 dB 天花板、Gate 5 指标维度）。
9. **交付补丁** `pluto_gate3_5_fix_patch.tar.gz`（含 `README_FIX.md` + 自校验 SHA256SUMS）；
   上板步骤：解包覆盖 → `./build_on_board.sh g++` → 严格按 Gate 1→5 顺序复测。

**归属**：本修复只改软件（数据格式/数值映射/状态机/单测/文档），**不碰** RTL / bitstream
/ 模型 / UI / FPGA-NPU。板端程序仍由**用户本人**上板运行。状态仍为
**`READY-FOR-PLUTO-SDR-GATE1-5-RETEST`**，Gate 1–5 板端全 PASS 前不写 PASS。

## 10. Gate 3 自动判定假 FAIL → 逐帧判定 + Gate 5 单次连续 refill 修复（本轮）

用户上板复测 Gate 3，程序报 `FINAL result=FAIL`，但 detail 显示 `ratio_pos=0.030062
ratio_neg=0 peak=94 rms=0.045755 dominant_freq_hz=10341.86 short/overflow/drop/disc/
timeouts 全 0 restore_result=PASS`。离线对 `digital_loopback_raw.bin`（131072 复数 =
128×1024）**逐帧**分析：`frames=128`、逐帧 `ratio≈0.999983857…`、`ratio_pass_count=128`、
`freq_mean_hz=9998.83`。

**结论（记录为事实）**：
- `GATE3_SIGNAL_PATH_CONFIRMED`：Pluto 数字回环、I/Q 格式、TX/RX、频率**全部正常**；
- `GATE3_AUTOMATED_VERDICT_FALSE_FAIL`：程序把 128 个**独立** 1024 点 RX 缓冲块拼接后跑
  **一条全长 Goertzel**，块间起始相位不连续 → 全长相干累加在相位断点处**相消** →
  `ratio=0.030` 假 FAIL。信号本身没问题，是**判定方法**错。
- **禁止降低 `ratio>0.3` 门限**：问题不在门限，而在全长拼接，故保持 0.3 不变。

### 根因

`pluto_device_libiio.cpp` 把 RX 缓冲固定为 1024 点，`collect_raw` 把 128 次 `refill` 拼接
成一条长序列，再对它做全长相干检测。一次 `iio_buffer_refill` 内部连续，但**两次 refill 之间
起始相位不连续**（DMA 丢样/重同步）。拼接后做全长 Goertzel，干净单音在断点处相消。

### 修复（全部离线完成并验证，未上板；对应 7 点要求）

1. **Gate 3/4 逐帧判定**：新增 `sdr_adapter/frame_analysis.hpp`（纯、无 libiio、板端与主机
   测试共用）。每 1024 点帧独立计算 `ratio_pos/ratio_neg/dominant_freq_hz/peak/rms`；聚合
   输出 `frame_count / frame_ratio_min|mean|max / frame_pass_count / frame_freq_mean /
   frame_freq_max_error / global_ratio`。每帧 PASS = `ratio>0.3` **且** 频点距 ±10 kHz ≤
   `freq_err_max`（默认 **300 Hz**，3% 的 10 kHz，**事先固定，不因本轮结果放宽**）。
   `global_ratio`（全长 Goertzel）**仅诊断，不参与 PASS**。
2. **门限不放松**：`ratio>0.3` 硬门不变；新增频点门而非放宽比值门。
3. **Gate 4** 复用同一逐帧判定，**不再跑全长 Goertzel**；保留 `--confirm-safe-rf-path`、
   最大衰减启动、-40 dB TX 天花板、RX 手动 20 dB、状态恢复，全部不动。
4. **Gate 5 连续性重审计（选 A：大容量单次 refill）**：`board_common.hpp` 新增
   `collect_raw_contiguous`（单次 refill 取满全部源采样，短 refill/超时/overflow/drop/
   discontinuity 一律 **fail-closed**）；证据 = `rx_refill_count` 增量 ==1 且
   `rx_buffer_capacity>=n_in`，detail 打印 `single_refill=1`。**不再**把多块拼接冒充连续流，
   也**不拿相位断点数据定标 receiver_scale**。
5. **RX 缓冲容量去硬编码**：`Device` 接口新增 `rx_buffer_capacity()/rx_refill_count()`；
   `pluto_device_libiio.cpp::ensure_rx_buffer(capacity)` 按请求容量惰性创建/重建，记录
   `rx_buffer_capacity`/`rx_refill_count`；`board_resampler_test.cpp --samples` 默认 4096→1024
   （单次 refill 的 DMA 缓冲容量约束），detail 打印 `rx_buffer_capacity`/`rx_refill_count`/
   `single_refill`。
6. **主机回归测试**：新增 `host_tests/test_frame_analysis.cpp`（7 用例 30 断言）——随机逐帧
   相位 128 帧纯 10 kHz 全长 ratio 低、逐帧全 ~1 且 PASS；真连续流被检测为相位连续；缺帧
   FAIL；单帧错频（8 kHz）FAIL；单帧低比值（噪声）FAIL；短 refill fail-closed；满 refill
   成功且 `rx_refill_count` 恰 +1。
7. **验证**：10 套主机测试 **443/0**（=413+30，-Werror 零告警）、ASan+UBSan 全 PASS、
   5 个板端门程序对真 libiio 0.26 编译+链接通过、契约/上板文档同步（逐帧判定、频点门 300Hz、
   Gate 5 单次 refill、`--samples 1024`）。
8. **交付补丁** `pluto_gate3_5_fix_patch_v2.tar.gz`（含 `README_FIX.md` + 自校验 SHA256SUMS，
   `sha256sum -c` 全 OK）；上板步骤见下方「复测命令」。

### 复测命令（修正后，严格按序）

```bash
cd /path/to/sdr_pluto_board_integration_v1
scripts/board_detect_pluto.sh                            # Gate 1
scripts/board_rx_only.sh --frames 64 --out rx_only_raw.bin   # Gate 2
scripts/board_digital_loopback.sh --frames 128           # Gate 3（逐帧判定）
scripts/board_rf_loopback.sh --confirm-safe-rf-path --frames 128   # Gate 4
scripts/board_resampler_test.sh --samples 1024           # Gate 5（单次连续 refill）
```

**归属**：本修复只改软件（逐帧分析/缓冲容量/单测/文档），**不碰** RTL / bitstream / 模型 /
UI / FPGA-NPU，**不写 Flash**。板端程序仍由**用户本人**上板运行。状态仍为
**`READY-FOR-PLUTO-SDR-GATE1-5-RETEST`**：**`GATE3_SIGNAL_PATH_CONFIRMED`** 与
**`GATE3_AUTOMATED_VERDICT_FALSE_FAIL`** 已记录，但 **`GATE3=PASS` 仅在逐帧判定补丁上板
返回退出码 0 后**才标，现在**不写 PASS**。
