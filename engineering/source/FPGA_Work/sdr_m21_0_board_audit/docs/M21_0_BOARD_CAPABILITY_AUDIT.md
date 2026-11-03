# M21-0 板卡能力审计（Board Capability Audit）

任务 id="39e5" · M21-0 · 只读审计，未修改任何工程/代码/位流/模型/交付包。

**来源类别图例**（全文统一）：`实测`＝板端日志/用户转录实测值；`Vivado报告`＝Vivado utilization/timing/power .rpt；`NPU编译报告`＝iCraft/ONNX 导出与模型契约；`硬件手册`＝官方赛题指南/硬件手册/设备树 dtb；`代码常数`＝源码 .py/.hpp/.cpp 常量；`契约文档`＝工程内 .md/.json 契约；`推导`＝由源码精确算术推出（已与实测交叉验证）；`尚待验证`／`无证据`＝缺证据，不猜测（UNKNOWN）。

---

## 0. 结论摘要（TL;DR）

| 维度 | 结论 | 关键数字（来源） |
|---|---|---|
| 板卡身份 | 复旦微 **FMQL30TAI**（Lite 版 JFMQL30TAI676H），单芯片 PS+NPU+PL 异构 SoC | 对标 XC7Z030FFG676-2I（硬件手册） |
| CPU | 4× Cortex-A53，约 1GHz，ARMv8 | NEON/VFP 未明示（硬件手册/设备树） |
| NPU | 片上 **ZG330 iCore**，8 TOPS@INT8，推理 ~1ms/帧量级 | 官方指南（硬件手册）；时延见 §9 |
| FPGA | 设计规模中等：LUT 52.6% / FF 45.3% / BRAM 53.4%，**DSP 仅 6.0%** | Vivado 报告 |
| 时序 | Setup/Hold 全过，仅 2 处 1GHz Pulse Width 违例（冻结已知） | Vivado 报告 |
| DDR | PS 1GB + 独立 PL 2GB；PL 侧实际跑 ~800MT/s（手册写 1600MHz，口径待核） | 硬件手册 + Vivado 时序报告 |
| 功耗 | PL 侧估算 3.679W，结温 32.1℃（Vivado 估算，非实测） | Vivado power 报告 |
| 核心判断 | **计算资源全面过剩、DSP/NPU 近乎空转**；瓶颈在 Device 生命周期与周期性尖峰，不在计算 | §9 / 详见资源分配文档 |

---

## 1. 当前系统基线（任务书 §一）

| # | 组成 | 现状（来源） |
|---|---|---|
| 1 | SDR 射频收发与采样 | 外接 Pluto SDR（AD9364，12-bit 有效位）；模型端 128kHz，原始率 2.56M×20 / 3.84M×30（代码常数/契约文档） |
| 2 | FPGA 数据通路 | FIR 重采样(601/903 taps)+NCO+receiver_scale 预处理链 + DMA + framebuffer（代码常数） |
| 3 | 当前正式 12 类 NPU 模型 | ADAMRV11Net num_classes=12，279,036 参数 / 46,544,384 MAC（NPU编译报告） |
| 4 | 模型 SHA256 | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`（契约文档） |
| 5 | 输入契约 | `[N,2,1024]` fp32 planar I/Q，RMS≈1.0（契约文档） |
| 6 | 12 类标签 | OOK、4ASK、AM-DSB、WBFM、2FSK、GFSK、BPSK、QPSK、8PSK、16QAM、64QAM、OFDM（契约文档） |
| 7 | 工作模式 | FIXED / AUTO LOCK / BAND SCAN（契约文档） |
| 8 | 触摸控制与本地 UI | AF_UNIX server + 触摸 evdev + 720P 帧缓冲（代码常数） |
| 9 | M20 CPU 侧 OOD-U 模块 | logit_margin 评分，threshold=-0.152744，near 拒识 6.03% / far 10.33%（契约文档/结果JSON） |
| 10 | 24 类模型训练工程 | ADAMRV11Net num_classes=24，**未训练**（只离线构建，最高 READY-FOR-AUTODL-…-PREFLIGHT）（契约文档） |
| 11 | 单次分类 ~1ms | **需从实际日志核实**：文档记载 12 类 ~1.14ms/帧；8 类实测 avg 0.67ms；12 类精确 infer_us 无落盘（实测/文档/尚待验证） |

---

## 2. 板卡身份与 SoC（任务书 §二.1/2/3）

| 项 | 数值 | 来源 |
|---|---|---|
| SoC 型号 | FMQL30TAI（完整版）；Lite 板 JFMQL30TAI676H | 硬件手册 |
| 对标器件 | Xilinx XC7Z030FFG676-2I（封装 FFG676、速度 -2、工业级 I） | 硬件手册 + Vivado 报告(Device=7z030ffg676-2) |
| 家族 | 复旦微 FPAI 异构融合（PS+NPU+PL+VPU 单芯片） | 官方赛题指南 |
| CPU | **4 核 ARM Cortex-A53**，约 1GHz（精确 MHz 无文档） | 硬件手册 |
| 指令集 | ARMv8（arm,armv8 / arm,armv8-timer，dtb 证实）；NEON/VFP **未明示**（A53 标配属推断） | 设备树 dtb |
| 硬核外设 | 2×千兆 MAC、2×USB2.0 OTG、2×SD/MMC、2×UART、2×CAN(SJA1000 经典)、QSPI、2×I2C、4×GPIO bank、NAND、TTC、WDT、DMA | 设备树 dtb + 硬件手册 |
| GPU/其它硬核 | Mali-bifrost GPU、SMMU(arm,mmu-500)、CCI(arm,cci-500)、GIC-400 | 设备树 dtb |

**NPU（片上集成，非外接）**

| 项 | 数值 | 来源 |
|---|---|---|
| 型号/厂商 | ZG330 iCore（诸葛架构，复旦微） | 官方赛题指南 |
| 理论算力 | 8 TOPS@INT8 / 4 TFLOPS@BF16/FP16 / 2 TFLOPS@TF32 | 官方赛题指南 |
| 支持网络 | CNN / RNN / Transformer | 官方赛题指南 |
| NPU 核时钟 | 1GHz（clk_out1_AI_CORE_CLK_ST_1=1000MHz，200MHz 差分晶振经 AI_Mate.edif 内 PLLE2 倍频） | 实测/项目文档 |
| 片上 SRAM/cache 容量 | **UNKNOWN（无证据）**（9.3Mb Block RAM 是 PL/FPGA 侧资源，非 NPU 片上 SRAM） | 无证据 |
| 完整算子白名单 | **UNKNOWN（无证据）**；仅知本工程模型只用 {Add, BN, Conv, Gemm, ReduceMean, Relu} | NPU编译报告/代码常数 |

---

## 3. FPGA 可编程逻辑资源（任务书 §二.4）

**资源总量**（Vivado 报告，Device 7z030ffg676-2，`ps_pl_ctrl_smoke_top_utilization_placed.rpt`）：

| 资源 | Available | 来源 |
|---|---|---|
| Slice LUTs | 78,600（LUT as Memory 26,600） | Vivado报告 |
| Slice Registers(FF) | 157,200（Slices 19,650） | Vivado报告 |
| DSP | **400** | Vivado报告 |
| BRAM | RAMB36/FIFO **265**、RAMB18 530（=9.3Mb） | Vivado报告 |
| URAM | 无（器件无 URAM） | Vivado报告 |
| GT 收发器 | GTXE2_CHANNEL 4 路 | Vivado报告 |
| 逻辑单元（官方口径） | ~125K Logic Cells | 官方赛题指南 |

---

## 4. DDR 内存（任务书 §二.5）

| 项 | 数值 | 来源 |
|---|---|---|
| PS DDR | 1GB DDR3；单片 4Gb×16bit；手册称 1600MHz×32bit ≈6.4GB/s | 硬件手册 |
| PL DDR | **2GB DDR3，独立**；手册称 1600MHz×64bit ≈12.8GB/s | 硬件手册 |
| PL DDR 实际速率 | 时序报告显示 PL DDR 参考 800MHz（freq_refclk_1=800MHz）/400MHz（iserdes_clkdiv）→ 若为 DDR3-800 则 ≈6.4GB/s | Vivado 时序报告 |
| 口径疑点 | 手册「1600MHz」与官方 FSBL 名「ddr400_demo」可能矛盾（1600MT/s vs 400MHz 时钟/800MT/s），**尚待验证** | 硬件手册/推导 |

---

## 5. 射频前端与采样（任务书 §二.6）

| 项 | 数值 | 来源 |
|---|---|---|
| 板载 ADC | **无 AD936x**。板载 XADC：12bit/1MSPS/5 路（1×VP/VN+2×VAUX+2×片内电源监测） | 硬件手册 |
| 板载 SDI | LMH0344/LMH0302，125Mbps–2.97Gbps | 硬件手册 |
| 外接 ADC 模块 | AD9226：12bit、65MSPS（±5V/10Vpp） | 外接模块资料 |
| 外接 DAC 模块 | DAC904：14bit、165MSPS（±3.2V/6.4Vpp） | 外接模块资料 |
| 实际射频前端 | 外接 **Pluto SDR（AD9364）**，12-bit 有效位，I/Q 交织 int16 小端容器（4 字节/复数） | 代码常数/契约文档 |
| 采样率链 | 模型端 128kHz 冻结；原始率 2.56MHz→×20（FIR 601 taps）首选、3.84MHz→×30（903 taps）回退 | 代码常数 |
| 满量程 | 12-bit 满量程 ±2048（RMS/裁剪域）；16-bit 域 adc_lsb=1/32768 并存 | 代码常数/契约文档 |
| 数据格式疑点 | 12-bit 对齐方式（右对齐/符号扩展）标注 `verified=false`，**尚待上板确认** | 代码常数 |

---

## 6. HDMI / 显示（任务书 §二.7）

| 项 | 数值 | 来源 |
|---|---|---|
| 分辨率/刷新率 | **720P@60Hz 稳定**；1080P@60Hz 实测不稳（TMDS 748.5M 超 HR bank IO 上限 710M） | 硬件手册 |
| 帧缓冲接口 | PL frame_ctrl（AXI-Lite 基址 0x40080000，version=0x20230218）+ fb_read_720p；1280×720 RGB565 双缓冲 | 代码常数/项目源码 |
| 单帧数据量 | 1280×720×2 = 1,843,200 B；双缓冲 3,686,400 B | 代码常数/契约文档 |
| 像素时钟 | cam_clk 74.25MHz；gp_clk 100MHz（PS FCLK 50MHz→clk_wiz 100MHz） | 代码常数/项目源码 |

---

## 7. 功耗与温度（任务书 §二.8）

| 项 | 数值 | 来源 |
|---|---|---|
| 供电 | AC220V→DC-12V；TPS259824 电子保险丝（UVLO 9.6V、限流 6A、PG） | 硬件手册 |
| 电源轨 | RSHF84644A：1.5V/4A(PS)、1.5V/8A(PL)、1.8V/4A、3.3V/4A；TPS51200×2 为 DDR VREF/VTT | 硬件手册 |
| PL 侧功耗估算 | Total On-Chip **3.679W**（动态 3.528W+静态 0.151W）；结温 32.1℃@25℃ 环境；Max Ambient 77.9℃ | Vivado power 报告（估算） |
| SoC TDP/功耗等级 | **无证据**（手册未给器件 TDP） | 无证据 |
| 散热片/风扇 | **无证据**（手册未提及） | 无证据 |
| 注意 | 3.679W 仅为 **PL/FPGA 侧** Vivado 估算，**不含 PS 4×A53、片上 NPU、外接 DDR 与 Pluto**；整板功耗无实测 | 推导/无证据 |

---

## 8. 位流与工具链版本（任务书 §二.9）

| 项 | 数值 | 来源 |
|---|---|---|
| FPGA 工具链 | Vivado v2018.3 (win64) | Vivado报告 |
| NPU 工具链 | iCraft CLI v3.39.0（另有 v3.36.1）；icraft_xir_version 3.39.0.0 | NPU编译报告/安装清单 |
| NPU 运行时组件 | icraft-zg330backend / hostbackend / xir / xrt；设备 axizg330aiudevice（另有 mock/socket 设备） | 安装清单 |
| 设备 URL | `axi://zg330aiu?npu=0x40000000&dma=0x80000000`（NPU 走 PL DDR 64-bit MIG） | 代码常数 |
| 当前合并位流 | pl_ddr_mandatory_core_top_combined（含 NPU+HDMI+frame_ctrl）；`_disable_icap.bit` SHA `22fec95c…` | Vivado报告/契约文档 |
| 时钟域 | 50 / 100 / 74.25 / 371.25 / 200 / 400 / 800 MHz + 1GHz NPU 核 | Vivado 时序报告 |

---

## 9. 多模型驻留/并行/流水推理（任务书 §二.10）

| 项 | 结论 | 来源 |
|---|---|---|
| 多模型驻留 | **UNKNOWN（无证据）**。代码仅单模型、单持久 Session（Device 一次 + Session.apply 一次 + 每帧 reset(1)） | 代码常数 |
| 并行推理 | **UNKNOWN（无证据）** | 无证据 |
| 流水推理 | **UNKNOWN（无证据）**；现有 Capture→Fpga→Npu→Result 是**软件层**流水线，非 NPU 多模型/流水 | 代码常数 |

**单帧推理时延核实（任务书 §一.11 要求「从实际日志核实 ~1ms」）**

| 项 | 数值 | 来源 |
|---|---|---|
| 12 类单帧推理 | 文档记载 ~1.14ms/帧（TIMING_1GHZ_DECISIVE_ANALYSIS.md / DDR_BANDWIDTH_AUDIT.md） | 文档记载 |
| 12 类精确 infer_us mean/p99/max | **UNKNOWN（无落盘数值）**。测量代码已就绪（board_gate7_12class_npu.cpp 输出 mean/p99/max），但板端模板为空白，待上板跑 Gate7 回填 | 尚待验证 |
| 8 类参照（不同模型，双输入） | forward avg 0.666–0.673ms / max 1.052–1.059ms（三次 100 帧连续跑） | 实测（BOARD_RESULTS） |
| 8 类 reopen 基线 | ~263ms/帧（每帧重开 Device） | 实测 |
| 结论 | 「~1ms」**数量级正确**：12 类口径 ~1.14ms；8 类均值 ~0.67ms。但存在**周期性尖峰**（forward=425/604/937ms，cycle58 起每 6 cycle 落在每轮第一 NPU 帧），根因未确认，是真正实时性隐患（见资源分配文档） | 实测（用户日志转录）/尚待验证 |

---

## 10. 统一资源表（任务书 §三要求：资源总量 / 当前占用 / 峰值利用率 / 平均利用率 / 主要瓶颈 / 可用余量）

来源均为：`Vivado报告`（FPGA 占用/时序/功耗）、`推导`（NPU 利用率）、`实测`（CPU/DDR 流量，部分为用户转录）、`无证据`（无实测处）。

| 资源 | 资源总量 | 当前占用 | 峰值利用率 | 平均利用率 | 主要瓶颈 | 可用余量 |
|---|---|---|---|---|---|---|
| FPGA Slice LUT | 78,600 | 41,361 | **52.62%** | 无运行时实测（UNKNOWN） | 时序已收敛，非瓶颈 | ~47%（37,239 LUT） |
| FPGA Slice FF | 157,200 | 71,138 | **45.25%** | UNKNOWN | 同上 | ~55%（86,062 FF） |
| FPGA Slice（打包） | 19,650 | 19,295 | **98.19%** | UNKNOWN | 打包已近满，新增逻辑需注意布线 | ~2%（355 slice） |
| FPGA DSP | 400 | 24 | **6.00%** | UNKNOWN | 未利用 | **94%（376 DSP）** |
| FPGA BRAM36 | 265 | 137 | **51.70%** | UNKNOWN | 未利用过半 | ~48%（128 tile） |
| FPGA GTXE2 | 4 | 0 | 0% | — | 未利用 | 4 路 |
| NPU 算力 | 8 TOPS@INT8 | 46.5M MAC/帧 | 推导 ~1% | 推导 ~1% | Device 生命周期/尖峰，非算力 | **~99%（推导）** |
| CPU | 4×A53 | ~2 进程/~3 线程 | 单核 ~32%(M16 旧版实测) | 修复后 ~0–2%(期望,待验) | UI 空转(已修)+无绑核 | **~3 核空闲** |
| PS DDR | 1GB（≈6.4GB/s 手册） | Linux+帧缓冲+日志 | 低（无实测） | 低 | 无 | 富余 |
| PL DDR | 2GB（实际 ~800MT/s≈6.4GB/s） | NPU DMA+帧缓冲 | framebuffer ~110MB/s@60Hz | 低 | 无 | **带宽富余** |

**关键读数**：
1. **DSP 94% 空闲**是 FPGA 侧最大余量——FFT/能量检测/频谱/多信号处理有充分算力空间。
2. **NPU ~99% 空闲（推导）**：模型仅 46.5M MAC/帧，即使 1000fps 连续也仅 ~0.5–1% 峰值；NPU 利用率**无运行时实测**（UNKNOWN），上述为推导值，标 `尚待验证`。
3. **CPU 4 核中约 3 核空闲**：UI 单线程 + producer 主线程+1 控制线程，无绑核/nice 证据；M16 实测单核 ~32% 空闲自旋已由 M17 FlipScheduler 修复（修复后值尚待实测）。
4. **Slice 打包 98.19%** 是唯一接近满的资源，但 LUT/FF 各自仅 ~50%——典型「逻辑散布广、单 slice 未填满」，新增显著逻辑需同时看布线拥塞，不宜简单按 LUT/FF 余量推断。
5. **功耗/温度**：PL 侧估算仅 3.679W、结温 32.1℃，散热不是当前约束（整板含 PS/NPU/DDR 无实测，`尚待验证`）。

---

## 11. 证据缺口清单（UNKNOWN，不猜测）

1. NPU 片上 SRAM/cache 容量；完整算子白名单；多模型驻留/并行/流水支持 —— 均无证据。
2. 12 类单帧精确 infer_us mean/p99/max；端到端 9 阶段分段延迟实测 —— 待上板 Gate7/latency 回传。
3. NPU 利用率、CPU% 修复后实测、DDR 峰值/持续带宽 —— 无运行时仪器实测（仅推导/文档估算）。
4. SoC TDP/整板功耗/散热 —— 无证据；3.679W 仅为 PL 侧 Vivado 估算。
5. DDR 实际速率口径（手册 1600MHz vs 时序报告 800MHz）—— 尚待验证。
6. 12-bit 射频数据对齐方式（右对齐/符号扩展）—— `verified=false`，待上板确认。
7. CPU 精确标称频率、NEON/VFP 版本 —— 仅「约1GHz」与推断。

---

*本文档为 M21-0 调研四件之一。相关：`M21_0_FEATURE_ROADMAP.md`（功能调研+评分+路线）、`M21_0_RESOURCE_ALLOCATION.md`（利用率审计+硬件任务分配）、`M21_0_FINAL_RECOMMENDATION.md`（组合判断+12 问+框图）。*
