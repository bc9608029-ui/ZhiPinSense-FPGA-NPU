# 悟净 Lite 板级与共用芯片事实契约

## 1. 来源层级与使用规则

当前资料并不是只有 Lite 手册。完整版与 Lite 使用同一颗 FMQL30TAI 系列芯片，竞赛
平台说明还明确写明两者共用同一套 PCB，Lite 通过不焊接部分冗余器件进行裁剪。因此
本文件采用分级证据，而不是排除完整版资料：

| 层级 | 资料 | 可用于确认的内容 |
|---|---|---|
| P0 | `F:\嵌赛\悟净开发板Lite（轻量版）硬件使用手册V1.0.docx` | Lite 实际焊接资源、接口数量、管脚、时钟与电源 |
| P0 | `F:\嵌赛\de2aca5a-535d-4288-aecd-aed3d0cf5841.pdf` | 竞赛平台、芯片能力、Lite/完整版同 PCB 关系和未焊器件差异表 |
| P1 | `F:\嵌赛\03_FMQL30TAI-悟净开发板手册\悟净开发板硬件使用手册V1.0_嵌赛.pdf` | 两版共用的芯片架构、PS-PL 资源、NPU/PL 能力，以及未被裁剪部分的电路理解 |
| P1 | `docs/hardware_document_audit/README.md` 和 `file_inventory.md` | 已完成的 Icraft、runtime、Linux、参考实现和板卡资料交叉审计 |

使用规则如下：

1. 芯片内部资源、PS-PL 架构、NPU、PL 逻辑资源可以引用完整版手册和竞赛说明。
2. 同 PCB 且不在“Lite 未焊接表”中的电路，可以用完整版资料辅助理解，但实际接口、
   位号、管脚和时钟仍需与 Lite 手册或实板核对。
3. 完整版独有/未焊器件不能出现在 Lite 的可用资源或 Procise 约束中。
4. 未确认的 Procise IP 端口、BSP 地址、DMA descriptor 和板级时序不能从架构表猜测。

Lite 手册末尾要求参考 `JFMQL30TAI_V02_原理图.pdf`，但当前资料中没有该完整原理图，
因此所有尚无正式约束的时钟引脚、电气标准、DDR 引脚仍保持 `TODO-HARDWARE`。

## 2. 已确认板载资源

| 类别 | Lite 手册中的事实 | 本工程约束 |
|---|---|---|
| 主芯片 | Lite 手册料号为 `JFMQL30TAI676H`；竞赛说明和完整版手册确认 FMQL30TAI 单芯片集成 PS、ZG330 NPU、PL、GPU/VPU | Procise 工程器件必须选择与 Lite 完整料号一致的 part/package |
| PS DDR3 | 1 GB；手册描述为 2 颗 4 Gb、单颗 x16、总线 x32、Fly-By，并写明 1600 MHz | 由 PS 配置/BSP 管理；本阶段不直接实例化控制器 |
| PL DDR3 | 2 GB；手册描述为 4 颗 4 Gb、单颗 x16、总线 x64、Fly-By，并写明 1600 MHz | 必须由已确认的 Procise/厂商 DDR IP、板级参数和约束生成 |
| QSPI | PS 侧一片 `EFM25QL256-E16`，256 Mbit，支持 x1/x2/x4 | 可用于启动镜像/用户数据；烧录流程等待官方示例确认 |
| SD | Micro SD/TF，连接 PS，可存放 BOOT、Linux 内核、文件系统和用户数据 | 属于 PS/Linux 路径，不直接接 Mandatory Core |
| Ethernet | 1 路 PS 端 10/100/1000 Mbps，PHY 为 YT8521，RGMII | SDR GigE 数据必须先进入 PS，再经 DDR/已确认的 PS-PL 通道送 PL |
| USB Host | 4 路 USB 2.0 Type-A Host；PS ULPI 接 USB3320C，经 USB2514 Hub 扩展；每口提供 +5 V | USB SDR 由 PS/Linux 驱动，不假设直连 PL |
| USB UART | 1 路 PS UART，经 MINI USB 接 PC | 仅串口日志/控制；不是 JTAG |
| JTAG | PS `U18` 与 PL `U19`，均为 20-pin；手册说明可配合 J-Link/I-Jet 和转接板 | PL 下载连接 U19；线序、电压、适配器型号必须按随板配件/厂商说明确认 |
| LED | 1 路 PS MIO LED；4 路 PL LED，芯片管脚分别为 `J1/M6/H7/J8` | `top_lite.pl_led[0..3]`逻辑对应 PL_LED1..4；约束仍需人工录入/核对 |
| 按键 | 1 路复位、1 路 PS MIO、2 路 PL；PL_KEY1=`F8`，PL_KEY2=`E7` | Lite 手册电路显示 PL 键空闲低、按下高；骨架使用 PL_KEY1 作为高有效复位请求 |
| HDMI | 1 路 PL 侧 HDMI 输出；手册给出 720p@60 Hz，且提示 1080p@60 Hz 可能闪屏 | 与当前 AMR 主链无直接关系，不作为首版依赖 |
| SFP | 1 路，手册注明 SFP0 可用 | 不等同于已存在 SDR 或 Ethernet MAC 数据通路 |
| PCIe | 1 路 PCIe x1 金手指 | 当前系统不依赖；需厂商 IP/BSP 后才能评估 |
| SDI | 2 路 SDI 输入 | 不是通用 RF ADC 接口，不纳入 IQ 接入假设 |
| MIPI | J16，2 data lane + 1 clock lane，PL Bank12，1.8 V | 与当前 RF 主链无关 |
| XADC | 片内 12-bit、1 MSPS；板上引出专用/辅助/电源监测通道 | 带宽和接口均不满足本项目宽带 SDR 主链 |
| GPIO Header | 14x2、2.54 mm；手册称含 4 路 3.3 V GPIO 和 12 路 1.8 V GPIO | 外接前必须核对电平、Bank 和完整原理图，不作高速 IQ 默认入口 |
| 电源 | 12 V 经 J37、SW8、D25、TPS259824；欠压阈值 9.6 V，电流限制 6 A；板内多路 DC-DC | 使用配套/合规 12 V 电源；禁止从 USB 反向假设整板供电能力 |

## 3. 两版共用的芯片级资源

以下内容来自完整版手册的 FMQL30TAI 芯片资源表，并由竞赛 Lite 平台说明交叉确认。
它们描述芯片能力，不能直接替代 Procise 器件数据库、BSP 或板级约束：

| 芯片资源 | 已确认值 | 对当前项目的意义 |
|---|---:|---|
| CPU/PS | 4 核，最高约 1 GHz；每核 32 KB 指令 + 32 KB 数据 L1；1 MB L2；256 KB 片上存储 | CPU 调度、SDR transport、buffer ownership、UI |
| NPU | ZG330 iCore；厂商标称 8 TOPS INT8、4 TFLOPS FP16/BF16、2 TFLOPS TF32 | TimePowerPhase 候选部署目标；不是本项目实测性能 |
| PL | 约 125K programmable logic/logic cells | Mandatory Core 和后续宽带 DSP 的逻辑资源 |
| DSP | 400 个，资源表描述为 18x25 MAC | Power/Lag、DDC、FIR、FFT 的候选乘法资源；实际映射看 Procise |
| Block RAM | 总计 9.3 Mb，资源表注明 36 Kb blocks | FIFO、ping-pong tensor、FFT缓冲；精确 block 数仍需器件库 |
| PS-PL接口 | 2 个主 AXI 32/64-bit、2 个从 AXI 32/64-bit、4 个高性能 AXI 64-bit、16 个中断 | 证明 PS/PL 互联有芯片基础；不代表地址图和驱动已知 |
| DMA | 芯片资源表列出 8 个 DMA 通道；USB/GbE 属于带内置 DMA 的高速外设 | 不等于已确认存在可直接实例化的通用 PL AXI DMA IP |
| 高速收发器 | 4 个，最高 12.5 Gbps；封装表为 FCBGA676、27x27 mm | 芯片能力；Lite 实际可用连接仍受未焊器件和 GT MUX 约束 |
| PCIe/XADC | PCIe Gen2 x4 硬核；2x 1 MSPS ADC | 板上 PCIe 接口是 x1；XADC 不满足宽带 SDR 主链 |

完整版手册中的 VPU、GPU 和视频接口信息可以用于理解芯片，但当前 RF Mandatory Core
不依赖这些单元。

## 4. Lite 未焊接资源

竞赛平台差异表明确列出 Lite 未焊接以下器件：

1. PL 端千兆网；
2. PS QSPI1；
3. PL eMMC；
4. CAN；
5. RTC；
6. SMA 及相应接口；
7. SFP1；
8. SDI 输入 3；
9. SDI 输入 4；
10. SDI 输出；
11. EEPROM；
12. 可调 GT 时钟；
13. 电流监控器件。

因此完整版手册关于上述接口的原理、引脚和示例只能作为芯片/PCB背景，不能写入 Lite
首版工程。Lite 仍保留 PS 千兆网、QSPI0、SFP0、两路 SDI 输入等资源，以 Lite 手册为准。

## 5. 时钟契约与手册歧义

Lite 手册的汇总表写“PS 侧 50 MHz、PL 侧 200 MHz”；详细“时钟管理”章节则列出：

- PS 主时钟 50 MHz，并特别说明不能用 33.333 MHz；
- 固定 100 MHz 晶振；
- PL DDR 外部 200 MHz 时钟；
- 另有时钟源原理图，但当前缺少可直接导入的官方约束文件。

因此不能把“200 MHz”直接认作 Mandatory Core 的普通 PL 用户时钟。`top_lite.sv`
只使用抽象 `pl_clk`，不写入频率、管脚或 PLL。Procise 工程必须用完整原理图/官方
示例确认 100 MHz 用户时钟与 200 MHz DDR 参考时钟的具体引脚、差分属性、IO
标准和约束后再绑定。

## 6. 启动、调试和接口边界

手册确认支持 JTAG、QSPI Flash 和 SD 卡加载；启动模式由 MIO2~MIO8 跳帽组合决定。
切换跳帽前必须断电，并按 Lite 手册的模式表操作。当前仓库不固化跳帽组合，也不
生成烧录脚本。

首版真实数据路径保持：

```text
USB/GigE SDR -> PS/Linux -> PS DDR -> 已确认的 PS-PL/搬运适配器
             -> top_lite 的抽象 IQ ready/valid 入口
             -> Mandatory Core -> 抽象 tensor write
             -> 已确认的 DDR/NPU 适配器 -> NPU/CPU
```

完整版芯片资源表确认存在 PS-PL AXI、DMA和中断基础，但 Lite 手册没有给出其地址图、
端口实例名、Linux 驱动、DMA descriptor、NPU runtime 或缓存一致性的编程模型。上述
集成部分仍为 `TODO-HARDWARE`，不得用芯片资源数量代替厂商 IP/BSP。

## 7. 仍需补齐的板级资料

1. `JFMQL30TAI_V02_原理图.pdf` 和官方 Lite 版 pin/时序约束。
2. Procise 对 JFMQL30TAI676H 的准确器件名称、speed grade 与 package 数据库。
3. 官方 PS 配置、PS-PL interconnect、PL DDR、DMA/等价搬运、IRQ 示例。
4. 100 MHz 用户时钟、200 MHz DDR 参考时钟和复位源的正式约束。
5. JTAG 转接板线序、推荐下载器和 QSPI/SD 固化步骤。
6. NPU runtime、张量内存、缓存维护和 DDR 共享缓冲区接口。
