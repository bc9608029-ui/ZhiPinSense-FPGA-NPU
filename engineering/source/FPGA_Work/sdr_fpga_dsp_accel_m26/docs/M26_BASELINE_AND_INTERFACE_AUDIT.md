# M26 基线与时序/接口审计（Baseline & Interface Audit）

任务 id="39e5" · M26 · 只读审计，未修改任何工程/代码/位流/模型/交付包。

**来源类别图例**（全文统一）：
`契约文档`＝`sdr_full_chain_spectrum_monitor_m22_m24/work/pkg/` 下 .md/.hpp 契约；
`Vivado报告`＝Vivado utilization/timing/power .rpt（引自 M21-0 审计，Device 7z030ffg676-2，Vivado 2018.3）；
`实测`＝板端日志/用户转录实测值；`代码常数`＝源码 .hpp/.cpp 常量；
`无证据`＝审计范围内无该证据，不猜测（标 UNKNOWN）。

---

## 0. 结论摘要（TL;DR）

| # | 审计项 | 结论 |
|---|---|---|
| 1 | IQ 接口位宽/符号/采样率/时钟 | **已明确**：interleaved int16 Q1.15，模型端 128 kHz 冻结，原始率 2.56M/3.84M |
| 2 | 流接口契约 | 现有链是 **PL-DDR Mandatory Core 寄存器图**（0x400C0000），非逐信号 AXI-Stream 契约 |
| 3 | tvalid/tready/tlast | **不明确**：握手 RTL 在外部 `pl_ddr_mandatory_core_v1`，不在本工程树 |
| 4 | 跨时钟域结构 | 时钟域清单已知；CDC 结构 RTL 在外部，本工程树**无证据** |
| 5 | DSP/BRAM/LUT/FF 利用率 | **DSP 6.0% 近空**（376/400 空闲）；Slice 打包 98.19% 近满 |
| 6 | WNS/TNS/CDC/DRC/时钟 | WNS **+0.030ns**（Setup）；仅 2 处 1GHz Pulse Width 违例（冻结已知） |
| 7 | 数据链反压 | **不明确**：现链为固定流，AXI-Stream ready 语义无证据 |
| 8 | 帧长/DMA/组帧 | **已明确**：1024 复数/帧；NPU 输入 [1,2,1024]+[1,3,1024]；PL DDR 64-bit MIG |
| 9 | 滤波/能量/FFT 是否已在 RTL | **否**：本工程树 0 个可综合 RTL；DSP 全为 C++ host；唯一 RTL（物理前端+int8 量化）在外部 |
| 10 | +0.030ns 余量证据 | **Vivado 时序报告**（post-fix，Setup WNS +0.030ns，0 失败端点） |

**核心结论**：当前生产链在 `sdr_full_chain_spectrum_monitor_m22_m24` 工程树内**不含任何可综合 DSP RTL**——FIR/FFT/NCO/能量检测/信号存在/CFAR 全部只是 C++ host 代码；CFAR 更是在 RTL 与 C++ 中**都不存在**。唯一的 FPGA RTL（physical 前端 `power=32bit / lag1=33bit` + int8 量化器）位于外部冻结工程 `pl_ddr_mandatory_core_v1`，本工程只以 C++ float 参考与数值契约形式引用。因此 M26 的 RTL 模块是**真正的新建**，不修改现有生产 RTL；但握手/CDC/反压语义因 RTL 不在本树而**不明确**，按 spec §二「任何接口不明确时必须保持模块独立，不得猜测并接入主链」执行。

---

## 1. IQ 接口位宽、符号格式、采样率、时钟频率（审计项 1）

| 项 | 值 | 来源 |
|---|---|---|
| IQ 布局 | `interleaved_iq`，字序 `[I, Q]` | 契约文档 `sampling_and_iq_contract.md` §3 |
| 标量类型 | `signed_int16`，小端 | 契约文档（与 aarch64 / 冻结 iq_input.bin 一致） |
| 二进制点 | **15（Q1.15）** | 契约文档 §3 |
| AXI-Stream tdata 位宽 | **32** | 契约文档 §3 |
| 模型端目标采样率 | **128000 Hz**（冻结） | 契约文档 §1 |
| 符号率 | 16000 Hz（`samples_per_symbol=8`） | 契约文档 §1 |
| SDR 原始采样率 | 2.56 Msps（×20，FIR 601 taps）首选 / 3.84 Msps（×30，903 taps）回退 | 代码常数 `fir_coeffs.h` + 契约文档 |
| 射频前端 | 外接 Pluto SDR（AD9364），12-bit 有效位入 16-bit 容器，MSB 对齐 shift=4，主机满量程 **±2048**（非 ±32768） | 契约文档 `rx_iq_format_contract.md` §2 |
| 时钟域 | 50 / 100 / 74.25 / 371.25 / 200 / 400 / 800 MHz + 1GHz NPU 核 | Vivado报告（时钟摘要） |

**审计结论**：接口数值契约明确、已冻结；M26 前端模块的**输入位宽基准 = 16-bit signed，Q1.15，interleaved [I,Q]**。

---

## 2. AXI-Stream / 现有流接口契约（审计项 2）

现有生产链的“流接口”**不是**逐信号 AXI-Stream 契约，而是 **PL-DDR Mandatory Core 的寄存器映射**（`board_package/pl_ddr_register_map.hpp`，`VERSION_VALUE=0x20260929`，User_Reg 基址 **0x400C0000**）：

| 偏移 | 寄存器 | 含义 |
|---|---|---|
| 0x00 | VERSION | 版本（0x20260929） |
| 0x04 | CONTROL | `START=bit0`、`CLEAR=bit1` |
| 0x08 | STATUS | `BUSY=bit0`、`DONE=bit1`、`ERROR=bit2` |
| 0x0c/0x10 | IQ_BASE / IQ_BYTES | 输入 IQ 缓冲基址/字节数 |
| 0x14/0x18 | TENSOR_BASE / TENSOR_BYTES | 输出 Tensor 缓冲基址/字节数 |
| 0x1c | FRAME_COUNT | 帧计数 |
| 0x20/0x24 | IQ_ACCEPTED / TENSOR_ACCEPTED | 接收计数 |
| 0x28 | ERROR_CODE | 错误码 |

NPU DMA 走 **PL DDR 64-bit MIG**，设备 URL `axi://zg330aiu?npu=0x40000000&dma=0x80000000`（代码常数）。

**审计结论**：现有接口是**寄存器图 + 内存缓冲**（PS 写 IQ 到 PL DDR → 触发 Mandatory Core → 回读 Tensor），而非可供 M26 直接挂接的逐样本 AXI-Stream 流。M26 模块采用**独立 AXI-Stream**（tvalid/tready/tlast），与本生产链解耦。

---

## 3. tvalid/tready/tlast 行为（审计项 3）

**审计结论：不明确（无证据）。** 生产 Mandatory Core 的 AXI-Stream 握手实现（tvalid/tready/tlast 的具体行为、burst 长度、last 断言时机）位于外部 `pl_ddr_mandatory_core_v1` 工程的 `pl_ddr_mandatory_core_regs.sv` 等 RTL 中，**不在本工程树内**（全树递归搜索 `*.v/*.sv/*.vhd/*.xci/*.ip` 为 0 文件）。本工程只有 `.hpp` 寄存器图引用，无法逐信号核对握手语义。

按 spec §二红线：接口不明确 → M26 模块保持独立，**不猜测 tvalid/tready/tlast 细节去接入主链**；M26 自己定义并自洽实现标准 AXI-Stream 握手（详见 `M26_INTEGRATION_INTERFACE.md`）。

---

## 4. 跨时钟域结构（审计项 4）

已知时钟域清单（Vivado报告时钟摘要）：

| 时钟 | 频率 | 用途 |
|---|---|---|
| clk_fpga_0 | 50 MHz | PS 总线 |
| gp_clk (clk_out1_clk_wiz_0) | 100 MHz | 通用/控制 |
| clk_74m25 / clk_371m25 | 74.25 / 371.25 MHz | HDMI |
| pl_ddr_refclk / clk_ref_mmcm_400_1 / freq_refclk_1 | 200 / 400 / 800 MHz | PL DDR |
| NPU 核 | 1 GHz | AI 核（AI_Mate.edif PLLE2 倍频） |

**审计结论**：时钟域**清单已知**，但具体 CDC 结构（异步 FIFO / 同步器 / 握手的实现）位于外部 Mandatory Core RTL，本工程树**无证据**。M26 新模块若有跨时钟需求，按 spec §五「跨时钟域使用异步 FIFO 或合格同步结构」自建，不依赖本工程树内不存在的 CDC 结构。

---

## 5. DSP / BRAM / LUT / FF 利用率（审计项 5）

来源：Vivado utilization 报告（`ps_pl_ctrl_smoke_top`，Routed，smoke_v1 合并位流，Device 7z030ffg676-2）。

| 资源 | Used | Available | 利用率 |
|---|---|---|---|
| Slice LUTs | 41,361 | 78,600 | **52.62%** |
| LUT as Logic | 35,735 | 78,600 | 45.46% |
| LUT as Memory | 5,626 | 26,600 | 21.15% |
| Slice Registers (FF) | 71,138 | 157,200 | **45.25%** |
| Slice（打包） | 19,295 | 19,650 | **98.19%** |
| Block RAM Tile | 141.5 | 265 | **53.40%** |
| RAMB36/FIFO | 137 | 265 | 51.70% |
| RAMB18 | 9 | 530 | 1.70% |
| **DSP48E1** | **24** | **400** | **6.00%** |
| BUFGCTRL | 12 | 32 | 37.50% |
| MMCME2_ADV | 4 | 5 | 80.00% |
| PLLE2_ADV | 3 | 5 | 60.00% |
| GTXE2_CHANNEL | 0 | 4 | 0% |
| Bonded IOB | 132 | 250 | 52.80% |

**审计结论**：FPGA 最大余量在 **DSP（94% 空闲，376/400）**，足以承载 FFT/能量检测/频谱处理；BRAM 约半空；LUT/FF 各约 50% 但 **Slice 打包 98.19% 近满**——新增显著组合逻辑需同时评估布线拥塞；MMCM/PLLE 已用 60–80%，时钟资源是后续新增时钟域的主要约束。

---

## 6. WNS / TNS / CDC / DRC / 时钟报告（审计项 6）

来源：Vivado 时序报告（post-fix）。

| 指标 | 数值 | 来源 |
|---|---|---|
| WNS / TNS（Setup） | **+0.030ns / 0.000ns**（0 失败端点） | Vivado报告 |
| WHS / THS（Hold） | +0.029ns / 0.000ns（0 失败端点） | Vivado报告 |
| WPWS / TPWS（Pulse Width） | **−0.409ns / −0.479ns（2 失败端点）** | Vivado报告 |
| DRC | 无专门 DRC 报告落入审计源；**无证据** | 无证据 |
| CDC 静态检查 | 无 CDC 静态检查报告落入审计源；**无证据** | 无证据 |

**审计结论**：Setup/Hold 全过，Setup 余量仅 **+0.030ns**（近零），新增组合逻辑不得放入现有关键路径；仅剩 2 处 1GHz PLLE2 域 Pulse Width 违例（**冻结已知项**，不阻塞功能）。CDC/DRC 无独立报告，M26 自行运行（spec §五要求「CDC 检查通过」）。

---

## 7. 当前数据链是否允许反压（审计项 7）

**审计结论：不明确（无证据）。** 现有链为固定流：`capture_contiguous` 单 refill → FIR 重采样/NCO → 帧切分 1024 复数 → producer 逐帧 → NPU。AXI-Stream 的 tready 反压语义位于外部 Mandatory Core RTL，本工程树无证据；host 侧缓冲语义由 `rx_iq_format_contract.md` §4 描述（overflow/dropped/discontinuity 必须为 0，短读有界重试），是**软件层**的溢出/丢样本处理，不是逐样本 AXI 反压。

M26 模块按 spec §三要求「支持连续流、间断流和反压」**自含 AXI-Stream tready 反压**，与现有链解耦。

---

## 8. 帧长、DMA 格式与 [2,1024] 组帧方式（审计项 8）

| 项 | 值 | 来源 |
|---|---|---|
| 帧长 | **1024 复数样本** = 2048 int16 = 4096 字节（RX 侧） | 契约文档 `rx_iq_format_contract.md` §5 |
| 帧间跳步 | 1024 样本（无重叠） | 契约文档 `sampling_and_iq_contract.md` §2 |
| NPU 输入 1 | `iq` `[1,2,1024]`（planar I/Q，2048 int8） | 契约文档 §5 |
| NPU 输入 2 | `physical_features` `[1,3,1024]`（power/lag1_re/lag1_imag，3072 int8） | 契约文档 §5 |
| NPU 输出 | `logits` `[1,8]`（冻结）→ 当前 10 / 目标 12 | 契约文档 §5 |
| DMA | PL DDR 64-bit MIG，`dma=0x80000000`；TENSOR_BASE/TENSOR_BYTES | 代码常数 |
| int8 尺度 | iq = 1/127，physical = 2/127；饱和 ±127，round ties-away | 契约文档 §5 |

**审计结论**：`[2,1024]` 即 **2 平面（I、Q）planar × 1024**，batch=1（`[1,2,1024]`）；M26 的 FFT 输入即为这 1024 复数样本/帧，与模型端 128 kHz 采样一致。

---

## 9. 现有滤波 / 能量检测 / FFT 是否已在 RTL 中存在（审计项 9）

**审计结论：不存在。** 对 `sdr_full_chain_spectrum_monitor_m22_m24` 全树递归搜索 `*.v, *.vh, *.sv, *.svh, *.vhd, *.xci, *.ip` **返回 0 文件**。所有 DSP 构建块都只是 C++ host 代码（header-only / iCraft、libiio-free）：

| 块 | 是否存在 RTL | 实际形态（C++） |
|---|---|---|
| FFT | **否** | `m24_fft.hpp`（radix-2 DIT，double，黄金参考）、`dsp_measure.hpp::fft_radix2` |
| FIR | **否** | `resampler.hpp`（polyphase）+ `fir_coeffs.h`（601/903 taps） |
| 抽取 | **否** | polyphase resampler（up=1, down=D） |
| NCO / DDC | **否** | `nco.hpp` |
| 能量/功率 | **否** | `dsp_measure.hpp`、`preprocess.hpp::physical_frontend`（float 参考） |
| 信号存在 | **否** | `signal_presence.hpp`（状态机，C++ only） |
| Hann 窗 | **否** | `m24_fft.hpp::hann_window`（仅 Hann） |
| 复模方 \|X\|² | **否** | 内联 `std::norm` / `I²+Q²` |
| **CFAR** | **否** | **RTL 与 C++ 都不存在**（最近似为固定门限峰值/占用检测） |
| Xilinx FFT IP / radix-4 / pipelined FFT | **否** | 无 XFFT、无 xci 引用 |

唯一真实 RTL：**physical 前端**（`power=I·I+Q·Q` 32bit 无符号、`lag1_real/lag1_imag` 33bit 有符号）+ **int8 量化器**，位于外部 `pl_ddr_mandatory_core_v1`；本工程仅以 C++ float 参考（`preprocess.hpp`）与数值契约引用。

冻结初始划分（契约文档 §6）：`dc_removal_in_amr_path=bypass`、`fir_in_amr_path=bypass`、`fft_in_amr_path=false`（FFT 仅用于可选监控 PSD/能量检测）。

**审计结论**：M26 的 RTL（DC 消除/能量/RMS/信号存在/NCO/FIR/抽取/Hann/FFT/fftshift/|·|²/噪声底/CFAR）是**全新实现**，不修改、不覆盖现有生产 RTL；CPU 侧 `m24_fft.hpp` 继续作为黄金参考与回退路径（spec §三 M26-B）。

---

## 10. +0.030 ns 时序余量的证据来源（审计项 10）

**来源：Vivado 时序报告（post-fix，Setup）。** 具体为合并位流 `pl_ddr_mandatory_core_top_combined`（Device 7z030ffg676-2，Vivado 2018.3）综合后布线时序报告的 Setup 路径：WNS = **+0.030ns**，TNS = 0.000ns，0 失败端点（引自 M21-0 `M21_0_RESOURCE_ALLOCATION.md` §1，Vivado 时序报告）。同一报告 Hold：WHS +0.029ns / THS 0.000ns（0 失败端点）；Pulse Width：WPWS −0.409ns / TPWS −0.479ns（2 失败端点，1GHz PLLE2 域，冻结已知）。

**审计结论**：+0.030ns 为**综合后（post-fix）Setup WNS 实测报告值**，非估算；其含义是 Setup 余量已接近零，M26 新逻辑不得并入现有关键路径（spec §五）。

---

## 附：审计项小结与 M26 落地约束

1. **输入位宽基准**：16-bit signed interleaved [I,Q]，Q1.15，128 kHz（模型端）。
2. **接口解耦**：M26 用独立 AXI-Stream（tvalid/tready/tlast）自洽实现；不猜测生产 Mandatory Core 握手细节。
3. **资源预算**：DSP 富余（94% 空）→ FFT/能量/CFAR 走 DSP；Slice 打包近满 → 注意布线；MMCM/PLLE 紧张 → 谨慎新增时钟域。
4. **时序红线**：Setup 仅 +0.030ns → 不碰现有关键路径；新模块 OOC 综合独立收敛。
5. **功能红线**：CFAR 全新实现；99% 功率带宽（禁止 M23「最左到最右谱线跨度」）；CPU `m24_fft.hpp` 保持黄金参考。
6. **最高状态**：`M26-FPGA-DSP-OFFLINE-MODULES-READY`；不得写 `FPGA_DSP_PASS / TIMING_PASS / HARDWARE_PASS / PROJECT_COMPLETE`。
