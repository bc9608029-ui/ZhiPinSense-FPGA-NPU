# FMQL30TAI 悟净板卡资料审计

审计日期：2026-09-09
范围：`F:\嵌赛` 中现有板卡、芯片、工具链、系统镜像和示例工程。
约束：本报告只引用当前文件证据；没有编写 RTL，没有运行板卡，没有修改模型、checkpoint 或训练结果。

## 结论摘要

当前资料足以确认 FMQL30TAI 的异构计算资源、PS/PL DDR、PS↔PL AXI 端口、片上 DMA 数量、NPU 型号/峰值算力，以及 USB 2.0 Host、千兆网和部分高速接口的板级连接。资料也提供了 Icraft 3.36.1/3.39.0、Ubuntu 20.04 aarch64 镜像、Procise 安装包和两套 30TAI 视频参考实现。

当前资料**不足以直接进入最终板级 RTL**：没有独立 FMQL30TAI 芯片数据手册、没有可检索的完整原理图/PCB 源文件、没有 BSP/内核/设备树源码、没有通用 AXI DMA IP 手册或 RF/ADC 参考工程。Procise RAR 已由用户解压为单个安装程序，但安装程序尚未运行，当前仍没有可直接审计的器件库/IP/示例工程。Icraft 示例证明 ZG330 的 AXI/DMA 运行时路径存在，但它是视频 PLIN/VPU 工程，不等价于已验证的 RF DMA 通路。

最关键的板型差异是：竞赛资料明确指出 Lite 版与完整版共用 PCB，但 Lite 未焊接 **PL 千兆网、PS QSPI1、PL eMMC、CAN、RTC、SMA、SFP1、SDI 输入 3/4、SDI 输出、EEPROM、可调 GT 时钟和电流监控**。因此本项目不能把 PL 千兆网或 SMA 当作竞赛板默认入口。[S2]

## A. 已有硬件资料清单

逐文件清单见 [file_inventory.md](file_inventory.md)。按内容分为：

- 板卡/赛事：硬件手册两份二进制版本、竞赛平台说明一份；两份硬件手册提取文本一致，但二进制 SHA-256 不同。
- NPU 工具链：Icraft 3.36.1 和 3.39.0 的 Windows、Ubuntu amd64、Ubuntu aarch64/on-chip 安装包、Python 3.8 wheel、CustomOp 与组件版本清单。
- 参考实现：30TAI `PLIN+HDMI` 和 `PLIN+VPU/MIG AXI` 的 runtime 包与 BOOT 包；两个 runtime ZIP 的随附 MD5 均实测通过。
- FPGA 工具：RAR 已解出 `Procise 2025.1.1 temp` Inno Setup 安装程序。PE/版本信息可读，但安装器未执行，器件库、IP 和示例工程内容仍未展开。
- 系统/交叉编译：Ubuntu 20.04 aarch64 SD 镜像、Ubuntu 20.04 Docker 容器、烧写工具与说明。
- AI 示例：PyTorch 2.0.1/Python 3.8 环境包、ResNet18 的 PyTorch/TorchScript/ONNX 示例与 Icraft 输入数据准备脚本。
- 第三方工具：串口驱动、MobaXterm、Netron、CMake；其中 CMake aarch64 包旁注明只用于 400TAI，不应作为 30TAI 必需组件。

未发现：独立原理图文件、PCB/Gerber、FMQL30TAI 完整芯片数据手册、BSP/Bootloader/Linux kernel/device-tree 源码、Vivado/Vitis 工程、Procise 可读工程源码、通用 AXI DMA 例程、RF ADC/AD936x 工程、NPU 最大模型大小说明。

Procise 安装程序补充审计：`FMSH_Procise_2025.1.1_temp_202603201420_32494.exe`，804,604,651 bytes，PE32 `0x014C`，文件元数据为 `CompanyName=Fudan Micro`、`ProductName=Procise`、`ProductVersion=2025.1.1 temp`、`Description=Procise Setup`，可识别为 Inno Setup；SHA-256 为 `BF04E66431EAA59EAB860BC56D9D97E0993F84011527FEE707F3450A7B8FA8F6`。Windows Authenticode 状态为 `NotSigned`，因此实际安装前应先用赛事方公布哈希或可信渠道重新校验。未运行安装程序，不据此推断器件/IP能力。

## B. 已确认硬件参数

### FPGA/PL

| 项目 | 文件证据确认值 | 审计判断 |
|---|---|---|
| 芯片 | FMQL30TAI，FPAI 单芯片集成 PS、ZG330 NPU、PL、GPU/VPU | 已确认 [S1][S2] |
| 逻辑资源 | 125K programmable logic / logic cells | 已确认；资料没有给出精确 LUT/FF 数，不能把 125K 直接写成 125K LUT [S1][S2] |
| DSP | 400 个，表中描述为 18×25 MAC | 已确认 [S1] |
| BRAM | 9.3 Mb，表中注明 36 Kb blocks | 总容量已确认；精确 block 数未列出 [S1] |
| GT | 4 个高速串行收发器，最高 12.5 Gbps | 芯片能力已确认 [S1] |
| 时钟 | 板上 PS 50 MHz、PL 200 MHz；另有 125 MHz、100 MHz、DDR 外部 200 MHz、GT 选择时钟和 SMA 预留 | 已确认；PLL/MMCM 数量和规格未确认 [S1] |
| PS↔PL AXI | 2×主 AXI 32/64-bit、2×从 AXI 32/64-bit、4×高速 AXI 64-bit、16×中断 | 已确认 [S1] |
| DMA | 芯片表列 8 个 DMA 通道；USB/GbE 高速外设带内置 DMA | 已确认到芯片级；通用 PL AXI-DMA IP、地址映射、缓存一致性仍未确认 [S1] |
| PS DDR | 1 GB DDR3，32-bit，手册写 1600 MHz | 已确认 [S1] |
| PL DDR | 2 GB DDR3，64-bit，手册写 1600 MHz | 完整板已确认；Lite 差异表未列其为删减项，但仍需到板核对 [S1][S2] |
| PCIe | 芯片硬核 Gen2×4；开发板连接器为 PCIe×1，且与 SFP/SDI/SMA 共享 Bank112 GT MUX | 必须区分芯片能力与板级连接 [S1] |
| AXI4-Stream | 当前资料未明确列出 AXI4-Stream IP/端口 | 内部数据流可采用 AXIS 设计习惯，但不能宣称厂商 IP 已确认 |

### NPU

| 项目 | 文件证据确认值 | 审计判断 |
|---|---|---|
| 型号 | ZG330 iCore，矩阵引擎 2×4，主频表列 1 GHz | 已确认 [S1][S2] |
| 峰值算力 | 8 TOPS INT8、4 TFLOPS FP16/BF16、2 TFLOPS TF32 | 厂商标称峰值，非本项目实测 [S1][S2] |
| 网络类型 | 资料写支持 CNN、RNN、Transformer | 已确认到厂商能力描述 [S2] |
| 工具链 | Icraft；现有版本 3.36.1 与 3.39.0 | 已确认 [S4][S5] |
| 框架/导入 | Icraft 组件清单含 `icraft-onnxparser` 与 `icraft-pytorchparser`；示例编译产物标记 `framework_kind=PYTORCH` | ONNX/PyTorch parser 存在；TimePowerPhase opset 17 是否全支持必须实际编译 [S6][S8] |
| INT8 | 硬件指标明确支持；30TAI 编译模型示例内部 storage dtype 为 signed INT8 | 可进行 INT8 部署验证，不代表当前 RF 模型已量化通过 [S1][S8] |
| 输入 layout | 现有图像示例外部模型输入是 NHWC/uint8，Icraft 校准脚本也要求 NCHW 数据转 NHWC 写入 ftmp | 这是示例模型契约，不是 RF 模型固定契约；RF 模型必须以编译后 XIR JSON 为准 [S8][S10] |
| 运行时模型 | 30TAI 示例使用 `.json + .raw`，设备 URL 为 `axi://zg330aiu?npu=0x40000000&dma=0x80000000` | 已确认 Icraft AXI/DMA runtime 路径 [S8] |
| 最大模型大小 | 未在现有资料中找到 | 未确认；不能以 DDR 容量代替编译器/NPU限制 |
| SDK/API | runtime 包含 XRT/XIR、ZG330 backend、Tensor/Session、BufferManager、Actor/Queue API | 已确认；RF 接入需基于这些 API 新建输入 Actor [S8] |

### CPU/PS 与板级存储/接口

| 项目 | 文件证据确认值 | 审计判断 |
|---|---|---|
| CPU | 4 核，最高/约 1 GHz；每核 32 KB 指令 + 32 KB 数据 L1，1 MB L2，256 KB 片上存储 | 已确认；CPU 内核具体型号未写明，不猜测 [S1][S2] |
| 架构/OS | 板载 Ubuntu 20.04，提供 aarch64 环境与镜像 | aarch64 软件环境已确认；精确 kernel/BSP 版本未确认 [S2][S3] |
| RAM | PS 1 GB DDR3；PL 2 GB DDR3 | 已确认见上 [S1] |
| 启动/存储 | 两片 256 Mbit QSPI、32 GB eMMC、TF/SD；支持 JTAG/QSPI/SD 启动 | 完整板已确认；Lite 少焊 PS QSPI1 和 PL eMMC [S1][S2] |
| USB | 4×USB 2.0 Host，经 USB3320C ULPI + USB2514 Hub 接 PS Bank501 | USB SDR 必须经过 PS USB/驱动/DDR；不是 PL 直入 [S1] |
| 网络 | 完整板 2×10/100/1000 Ethernet，YT8521 分别接 PS 与 PL，RGMII | Lite 未焊 PL 千兆网，因此竞赛 Lite 默认只有 PS 千兆网路径 [S1][S2] |
| GPIO/Header | 14×2 header 含 4×3.3 V GPIO、12×1.8 V GPIO | 电气/时序/差分能力不足以据此确认高速 RF 数字口 [S1] |
| XADC | 芯片表列 2×1 MSPS ADC，板表列 5 路 XADC 接口 | 不满足 5/10/20 MS/s 宽带 IQ 采集目标 [S1] |
| Linux 驱动/BSP | 当前只有系统镜像、环境指导和应用 runtime；没有源码清单 | USB SDR、网卡零拷贝、DMA、UIO、中断驱动必须上板核验 |

## C. 当前系统架构需要修改的地方

### 1. SDR 接口必须从“抽象 AXIS 入口”改为板型分支

#### USB SDR：竞赛 Lite 上最现实的首选验证路径

```text
USB SDR
  → 板载 USB2.0 Host（PS）
  → Linux SDR 驱动/libusb
  → PS DDR 环形缓冲
  → PS/PL 高速 AXI + DMA/共享缓冲
  → PL 1024 点 framing + Power/Lag
  → DDR NPU tensor buffers
  → Icraft ZG330 session
```

USB2.0 只有 480 Mbit/s 标称线速。int16 I + int16 Q 的原始数据率是：5 MS/s = 160 Mbit/s，10 MS/s = 320 Mbit/s，20 MS/s = 640 Mbit/s。故 5 MS/s 有条件可行，10 MS/s 必须做持续吞吐/丢包压力测试，20 MS/s 原始格式超过 USB2.0 标称线速。PS 必须参与 IQ transport，不能描述成“CPU 只控制”。[S1]

#### Ethernet SDR：Lite 只能确认 PS 千兆网路径

```text
Ethernet SDR
  → PS YT8521/RGMII 千兆网
  → Linux UDP/driver + PS DMA descriptors
  → PS DDR packet/IQ ring
  → DMA/AXI 到 PL
  → Power/Lag + tensor buffer
  → NPU
```

1 GbE 对 5/10 MS/s 有较好名义余量；20 MS/s 原始 640 Mbit/s 已占线速 64%，加入 Ethernet/IP/UDP、包间隔和 DDR/NPU 竞争后只可列为“条件可行”。完整版板可研究 PL 千兆网直入，但 Lite 的 PL PHY 未焊，不能作为默认方案。[S1][S2]

#### 直接数字 RF 前端：当前板级连接未确认

```text
ADC/RF transceiver digital interface
  → 尚未确认的兼容扩展板/载板接口
  → PL capture/CDC FIFO
  → DDC/FIR/抽取（按真实采样率）
  → framing + Power/Lag
  → DDR/NPU
```

Lite 不带 SMA；14×2 header 只有 16 路 GPIO且电平混合；XADC 只有 1 MSPS 级。现有资料不能证明它能直连 AD936x/LVDS/JESD 或承载 5–20 MS/s int16 IQ。此路径需要厂商给出扩展接口、原理图/Bank 约束或外接桥接板后再定。

### 2. FPGA→NPU 接口采用 DDR 缓冲，而不是假设直连 AXI Stream

现有 Icraft 示例证明的是 AXI/DMA runtime 和 DDR Tensor/Session；没有文件证明 NPU 暴露可由自定义 PL 直接驱动的 AXI4-Stream 输入。因此第一版应为：

```text
PL feature stream
  → tensor packer
  → AXI memory-mapped write/DMA
  → DDR ping-pong buffers + descriptor/frame_id
  → CPU/Icraft submit
  → ZG330 NPU
```

CPU 负责 buffer ownership、缓存维护、session enqueue、超时/错误、8 类 logits 后处理和 UI；数据面避免 CPU 再复制。能否真正零拷贝取决于 BSP 的物理连续内存、MMU/coherency 与 XRT Tensor API，必须板上验证。[S8]

### 3. NPU 输入不能预先写死为 NCL INT8

逻辑契约仍是：

- `iq`: `[1,2,1024]`
- `physical_features`: `[1,3,1024]`，顺序 `[power, lag1_real, lag1_imag]`
- 输出：`logits [1,8]`

但 Icraft 的物理 layout、dtype、对齐、scale、zero-point 和双输入映射必须由 TimePowerPhase 实际编译产物确定。现有图像例子只证明 NHWC/uint8 和内部 signed INT8 的一种组合。保留两输入有利于 IQ 与物理特征独立量化；如果 Icraft 多输入/Conv1D 不支持，可加**部署包装层**将输入表示为 `[1,5,1,1024]` 并在图内切分/reshape，但这必须先做 logits parity，不能改变冻结权重或训练结果。

### 4. FIR/FFT 的角色需保持与冻结模型一致

TimePowerPhase 的 AMR 输入主链当前没有额外硬件 FIR/DC-removal/FFT。为保证部署等价，第一版 Power/Lag 前不得擅自插入会改变分布的处理。FFT/PFB/CFAR 属于宽带发现旁路；若从宽带流中抽取单信号，则 DDC、低通和抽取是必要的，但其输出必须重新做 PC replay/Sim-to-Real 校准后才接 1024 点 AMR。

### 5. TimePowerPhase 在该板上的映射

### 可运行性判断

**条件可行，不等于已经可运行。** 模型参数量约 71K，输入帧极小：FP32 IQ 8 KiB + physical 12 KiB；计划 INT8 为 2 KiB + 3 KiB。相对于 1 GB PS DDR/2 GB PL DDR，容量不是瓶颈。ZG330 明确支持 INT8 CNN，Icraft 包含 PyTorch/ONNX parser，模型算子以 Conv/ReLU/BN/Pooling/Linear/elementwise 为主，适合先做编译验证。但 Conv1D、Adaptive pooling、双输入、具体 opset 17 与量化规则仍须 Icraft 3.39 实编译确认。[S1][S5][S6][S8]

### 推荐实际数据搬运路径

```text
SDR ingress
→ PS DDR（USB/PS-Ethernet）或 PL FIFO（未来直接数字口）
→ PL 1024-sample frame
→ Power/Lag exact integer pipeline
→ calibrated round/shift/saturate
→ IQ INT8 buffer + Physical INT8 buffer
→ AXI MM/DMA 写 DDR ping-pong
→ descriptor {frame_id, timestamp, addresses, scale_id, overflow/saturation}
→ CPU Icraft/XRT Tensor 绑定并提交 ZG330
→ logits[8]
→ CPU argmax/softmax、时序平滑、日志、UI
```

物理特征的精确乘法为 FPGA-friendly：Power 每点 2 乘 1 加；Lag-1 每点 4 乘 2 加，帧首相关固定为零。可选择 6 路乘法器一拍/样本，或依据采样率时分复用 DSP。400 DSP 的总资源充足性不能仅凭算术量宣称，仍需 Procise 综合后报告时序与利用率。[S1]

### FPGA、NPU、CPU 分工

| 域 | 第一版职责 | 当前证据状态 |
|---|---|---|
| FPGA/PL | 输入适配、CDC FIFO、1024 framing、Power/Lag、定点量化、tensor packing、DMA 写入、计数/中断；宽带 FFT/PFB/CFAR 旁路后续接入 | 结构可设计；端口/IP/地址/时钟待 BSP/Procise/板卡 |
| NPU | Time encoder、physical encoder、融合分类器，输出 8 logits | 算力和 runtime 已有证据；本模型编译/量化未验证 |
| CPU/PS | USB/网络 transport、buffer ownership、Icraft session、metadata、后处理、UI、控制与异常恢复 | Ubuntu/Icraft 环境存在；驱动与性能待板上验证 |

## D. 可以现在提前开发的软件部分

1. 用 Icraft 3.39 在 Windows/Ubuntu amd64 对冻结 ONNX 做转换、量化、仿真；记录每个 op 的 target/fallback、输入 layout/scale、`.json/.raw` 大小。
2. 使用训练分布而非 development/final blind 构建固定校准集；导出 IQ 与 Power/Lag 的 float、int16、INT8 replay vectors。
3. 开发不依赖真实板的 C++ `RFInputActor`/descriptor schema/queue 状态机，并用普通内存模拟 `BufferManager` 所有权。
4. 固化 tensor header：magic/version/frame_id/timestamp/tensor shape/dtype/stride/scale-id/saturation/overflow/CRC；metadata 不进入模型特征。
5. 为 USB/UDP 输入写 PC replay backend；把 transport 与算法入口隔离，以便到板后只替换设备适配层。
6. 建立 Procise 工程清单和约束模板，但在得到芯片 part、BSP 地址表和板型后再生成最终工程；当前不写板级 RTL。
7. 设计板上测试矩阵：DDR loopback、DMA sustained throughput、cache coherency、NPU standalone、PL→DDR→NPU parity、USB/UDP 长时丢包、温度/功耗。

## E. 必须等板子或补充资料才能验证

- 实际收到的是 Lite 还是完整版，以及未焊器件/跳线/Bank 电压的最终 BOM。
- 安装并审计 Procise 后才能确认的准确 device/part、PLL/MMCM/BUFG 数量、IP catalog、时钟约束与真实综合资源。
- PL 高速 AXI 端口名称、地址宽度、突发限制、coherency、DDR controller/MIG 配置、DMA IP 和中断号。
- Ubuntu kernel、设备树、CMA/UIO/VFIO/XRT 驱动、物理连续 buffer 与缓存维护 API。
- Icraft 3.39 对 TimePowerPhase ONNX opset 17、Conv1D、Adaptive pooling、双输入和 INT8 per-input/per-channel scale 的真实支持。
- NPU 最大模型/工作区、实际延迟/吞吐/功耗/温度；不能用 8 TOPS 换算项目推理时间。
- USB SDR 的 aarch64 驱动与 USB2 sustained throughput；PS 千兆网 UDP 丢包和零拷贝能力。
- 直接数字 RF 接口的电平、引脚、lane、时钟/参考时钟、同步触发以及扩展板可获得性。
- FPGA Power/Lag 的 bit-exact 输出、定点量化误差、DMA 与 NPU logits parity。
- 真实 RF 下 AGC、满量程、DC/IQ imbalance、采样时钟/CFO、失真和 Sim-to-Real 泛化。

## 采购/索资硬约束

在选 SDR 或开 RTL 前，应向厂商/赛事方索取：

1. Lite 版最终原理图、BOM/DNP 表、PCB pinout/Bank 电压与 FMQL30TAI datasheet。
2. Procise 30TAI board project、约束文件、PS 配置、PL DDR MIG 示例和通用 AXI DMA loopback；安装器本身不包含可见的这些资料。
3. Ubuntu BSP 源码/版本、设备树、kernel config、XRT/Icraft runtime API 文档。
4. Icraft 3.39 完整文档、支持算子/ONNX opset/量化/layout 表、ZG330 模型容量限制。
5. 竞赛 Lite 的 USB2 sustained 实测、PS GbE/PL GbE实际装配状态、可用扩展接口和推荐 RF 前端。

## 文件证据索引

- **[S1]** `F:\嵌赛\03_FMQL30TAI-悟净开发板手册\悟净开发板硬件使用手册V1.0_嵌赛.pdf`，41 页；硬件配置、芯片资源、DDR、时钟、以太网、USB、GT/PCIe/SFP/SMA、header。
- **[S2]** `F:\嵌赛\de2aca5a-535d-4288-aecd-aed3d0cf5841.pdf`，8 页；2026 竞赛平台、Lite 裁剪表、异构任务要求。
- **[S3]** `F:\嵌赛\08_FMQL30TAI开发教程资料\02_深度学习环境搭建\深度学习环境搭建指导手册.pdf`，13 页；Ubuntu 20.04 aarch64、Python 3.8、PyTorch 2.0.1、板载 Icraft 安装。
- **[S4]** `F:\嵌赛\04_ICraft\v3.36.1\ICraft_V3.36.1安装包\readme.md`；平台安装包和 cp38 API。
- **[S5]** `F:\嵌赛\04_ICraft\v3.39\icraft_v3.39.0\readme.md`；3.39.0 的 30TAI/100TAI amd64/on-chip/cp38 包。
- **[S6]** `F:\嵌赛\04_ICraft\v3.39\icraft_v3.39.0\commit_id.ini`；包含 onnxparser、pytorchparser、quantizer、ZG330 backend、XIR/XRT 等组件版本。
- **[S7]** `fpai_demo_package_26040701.zip/.txt`；30TAI PLIN+HDMI/VPU 示例结构，Icraft 3.36.0、AI-Mate 25122301。
- **[S8]** `fpai_demo_package_26040702.zip/.txt`；30TAI PLIN+VPU、MIG AXI、ZG330 runtime、BufferManager/Tensor/Session 和 `.json+.raw` 模型。
- **[S9]** `F:\嵌赛\06_板载Linux系统镜像\icraft_v3_ubuntu20.04_aarch64_sd_image.7z`；内部为单个 SD `.bin` 镜像。
- **[S10]** `F:\嵌赛\08_FMQL30TAI开发教程资料\03_图像分类部署示例工程\image_cls_resnet18.zip`；PyTorch/TorchScript/ONNX 示例及 NHWC ftmp 准备脚本。

## 审计边界

- 未访问或运行 `final_blind_test`。
- 未修改 Baseline V1、Representation Ablation V1、QAM-Aware V2 模型、配置、checkpoint 或正式结果。
- 未编写 RTL，未运行 Procise 安装器，未烧写镜像，未声称 FPGA/NPU/SDR 实测性能。
- `tmp/hardware_audit` 仅含 PDF 文本提取和页面渲染，用于本次只读审计；不会提交为产品源代码。
