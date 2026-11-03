# Procise 上板前集成计划

## 1. 范围、来源与冻结边界

本计划只整理当前仓库，不重新设计算法，不生成未经确认的 Procise IP。Baseline V1、
Representation Ablation V1、QAM-Aware V2/TimePowerPhase、正式训练结果和现有
Golden 数值契约保持冻结；Advanced Wideband 仍停留在 Python Golden/接口设计。

资料使用分为三层：Lite 手册和竞赛差异表决定实际焊接资源；完整版手册用于两版共用
的 FMQL30TAI 芯片资源、PS-PL 架构和未裁剪电路；Icraft/runtime/参考实现用于软件与
数据搬运模式参考。完整版中明确列为 Lite 未焊接的接口不会进入 `top_lite` 或约束。
详细来源规则见 `docs/board_lite_contract.md`，已有全资料审计见
`docs/hardware_document_audit/README.md`。

状态定义：

- **已完成**：源码/文档存在且已有软件或 RTL 仿真证据；
- **待上板验证**：逻辑已准备，但尚无 Procise 综合、STA 或实板证据；
- **尚未实现**：当前只有边界/TODO，不能当作已存在硬件功能。

## 2. 仓库实现清单

### 2.1 RTL

| 文件 | 内容 | 状态 |
|---|---|---|
| `hardware/fpga/rtl/common/iq_stream_fifo.sv` | 同时钟 IQ 弹性 FIFO、显式丢样计数 | 已完成仿真；待 Procise 推断/上板验证 |
| `hardware/fpga/rtl/framing/iq_frame_controller.sv` | 1024 点索引、frame ID、start/end、帧内错误粘滞 | 已完成仿真；待上板验证 |
| `hardware/fpga/rtl/features/qam_feature_pipeline.sv` | u32 Power、s33 LagRe/LagIm，2 级 II=1 流水 | 已完成逐点零差异；待综合时序/资源验证 |
| `hardware/fpga/rtl/quantization/feature_quantizer.sv` | multiplier/shift、ties-away rounding、INT8 饱和/计数 | 已完成逐点零差异；待综合时序/资源验证 |
| `hardware/fpga/rtl/tensor/tensor_packer.sv` | IQ `[2,L]`、Physical `[3,L]` 通道优先地址和 ping-pong ownership | 已完成仿真；待真实存储适配器验证 |
| `hardware/fpga/rtl/common/mandatory_core_path.sv` | FIFO→framing→Power/Lag→量化→tensor 的平面端口集成 | 已完成 Verilator 集成验证；待 Procise/上板 |
| `hardware/fpga/rtl/interfaces/iq_stream_if.sv` | IQ 抽象 interface/modport | 已完成接口定义；Procise 支持性待确认，首版顶层不依赖 |
| `hardware/fpga/rtl/interfaces/tensor_buffer_write_if.sv` | 张量写抽象 interface/modport | 已完成接口定义；首版顶层使用等价平面端口 |
| `hardware/fpga/rtl/interfaces/buffer_transfer_if.sv` | 通用 buffer request/done/IRQ 抽象 | 已完成契约；实际 DMA/DDR adapter 尚未实现 |
| `hardware/fpga/rtl/top/top_lite.sv` | Lite 时钟/按键复位、4 个状态 LED、Mandatory Core 封装 | 已完成保守骨架；待 pin/clock 约束、Procise 综合和上板 |
| `hardware/fpga/rtl/wideband/README.md` | 明确 Advanced Wideband RTL 缺口 | FFT/PFB/PSD/检测/DDC/FIR/重采样 RTL 尚未实现 |

### 2.2 SystemVerilog Testbench

| 文件 | 覆盖 | 状态 |
|---|---|---|
| `tb/unit/tb_iq_stream_fifo.sv` | 顺序、满/空、backpressure 与显式 overflow | 已完成 |
| `tb/unit/tb_iq_frame_controller.sv` | frame index/ID/boundary/sticky error/stall | 已完成 |
| `tb/unit/tb_feature_quantizer.sv` | 正负 rounding、阈值、饱和计数 | 已完成 |
| `tb/unit/tb_tensor_packer.sv` | 地址平面、buffer 轮换、IRQ | 已完成 |
| `tb/integration/tb_qam_feature_vectors.sv` | 19 帧 raw Power/Lag CSV | 已完成，Python 零差异 |
| `tb/integration/tb_mandatory_core.sv` | 完整核心、INT8、地址、边界、frame_valid | 已完成，Python 零差异 |
| `tb/integration/tb_top_lite.sv` | 新顶层复位释放、平面端口、边界/IRQ smoke | 已完成源码；需持续回归 |
| `tb/run_rtl_compare.py` | Icarus 执行与 Python CSV 对比 | 已完成；无 Icarus 时明确 SKIPPED |

### 2.3 Python Golden 与向量

| 文件 | 内容 | 状态 |
|---|---|---|
| `deployment/fixed_point_frontend.py` | int16 Power/Lag 精确参考 | 已完成、冻结依赖 |
| `hardware/fpga/python/rtl_reference.py` | Mandatory Core 量化/地址 bit-exact 参考 | 已完成 |
| `hardware/fpga/vectors/generate_vectors.py` | 19 帧确定性测试集生成器 | 已完成 |
| `hardware/fpga/vectors/iq_input.hex` | 19,456 个固定 `{Q,I}` 输入字 | 已完成、哈希冻结 |
| `hardware/fpga/vectors/expected_core.csv` | Power/Lag/五通道 INT8/地址期望 | 已完成、哈希冻结 |
| `hardware/fpga/vectors/manifest.json`、`vector_params.svh` | case、seed、量化器和 TB 参数 | 已完成 |
| `hardware/fpga/board_validation/*` | 上板 capture 规则、哈希、自动逐元素比对 | 已完成软件包；待板上 capture 验证 |
| `dsp/wideband_discovery.py` | FFT、PSD、噪底、检测、bin 合并的浮点 Golden | 已完成软件参考；宽带 RTL 尚未实现 |
| `hardware/fpga/python/wideband_reference.py` | candidate/DDC/FIR/resample/AMR frame 编排 | 已完成软件参考；待真实 RF/板卡验证 |
| `hardware/fpga/python/wideband_fixed_point.py` | Q1.15 window、32-bit NCO/Q1.15 DDC 参考 | 已完成软件参考；尚无 RTL |
| `dsp/fft.py`、`fir.py`、`stft.py`、`normalization.py`、`golden_reference.py` | 通用 DSP/软件 Golden | 已完成 PC 参考；不等于板上实现 |

### 2.4 AI 模型与部署包装

| 文件 | 内容 | 状态 |
|---|---|---|
| `models/baseline_cnn.py` | Baseline V1 CNN | 已完成并冻结；不修改/不重训 |
| `models/dual_domain_rfnet.py` | TimeOnly/FrequencyOnly/TimeOnlyWide/DualDomain | 已完成并冻结；不重训 |
| `models/qam_aware_rfnet.py` | TimePower/TimePhase/TimePowerPhase | 已完成并冻结；TimePowerPhase 为当前候选 |
| `deployment/time_power_phase_partition.py` | 外部 FPGA 特征与 NPU 图分区包装 | 已完成软件等价验证；待 Icraft/NPU 编译和上板 |
| `deployment/numerical_contract.py` | SDR int16→模型数值契约 | 已完成；待真实 ADC/SDR scale 校准 |

### 2.5 文档

| 文件/组 | 状态 |
|---|---|
| `hardware/fpga/README.md` | 已完成：FPGA 子工程入口与边界 |
| `hardware/fpga/docs/system_partition.md` | 已完成：FPGA/NPU/CPU 分工 |
| `mandatory_core.md`、`hardware_abstraction.md` | 已完成：数学、握手、存储抽象契约 |
| `verification.md`、`implementation_status.md`、`pre_board_closure.md` | 已完成：仿真证据、收口状态与未完成项 |
| `development_roadmap.md` | 已完成：阶段顺序；后续阶段尚未执行 |
| `wideband_architecture.md`、`wideband_interface.md`、`wideband_golden_audit.md`、`wideband_fixed_point_contract.md` | 已完成设计/Golden；Advanced RTL 尚未实现 |
| `docs/fpga_interface.md` | 已完成：早期 FPGA 数据格式规划 |
| `docs/system_consistency_audit/{README,numerical_contract,channel_impairment_audit,sdr_transport,wideband_discovery}.md` | 已完成软件/系统一致性审计；硬件实测待完成 |
| `docs/system_deployment/{README,algorithm_diagnosis,competition_technical_route,fpga_datapath,npu_deployment,rtl_plan}.md` | 已完成部署路线；板级接口/性能待验证 |
| `docs/hardware_document_audit/{README,file_inventory}.md` | 已完成已有资料审计；缺失项仍需补齐 |
| `docs/board_lite_contract.md` | 本轮新增：仅 Lite 手册事实与未知项 |
| `docs/procise_integration_plan.md` | 本轮新增：Procise 集成边界与操作顺序 |

此外，`datasets/`、`channel/`、`training/`、`evaluation/` 与 `configs/` 中的冻结
训练/评价协议仍在仓库中，但本轮没有读取 final blind 样本、没有执行预测，也没有修改
模型或训练结果。`outputs/` 为忽略目录，不纳入 Procise 工程。

## 3. 现有 RTL 综合可行性审计

### 3.1 结论

现有 Mandatory Core 使用寄存器、数组、乘加、比较、移位和 ready/valid；没有
`#delay`、`initial`、文件 IO、force 或 testbench system task 混入设计 RTL。就通用
SystemVerilog 而言可综合，模块依赖闭合。本轮未发现需要改变算法行为的明确功能 bug，
所以未修改原六个核心 RTL。

### 3.2 依赖顺序

```text
top_lite
└─ mandatory_core_path
   ├─ iq_stream_fifo
   ├─ iq_frame_controller
   ├─ qam_feature_pipeline
   ├─ feature_quantizer ×5
   └─ tensor_packer
```

三个 `rtl/interfaces/*.sv` 是协议说明，不是上述层次的编译依赖。若 Procise 对
SystemVerilog `interface/modport` 支持不完整，可不加入首版工程，不影响平面端口顶层。

### 3.3 审计项

| 项目 | 结果 | 上板前动作 |
|---|---|---|
| 位宽 | Power=u32；LagRe/LagIm=s33；量化乘积最大 65 bit；1024 点地址宽度匹配 | 综合后检查所有乘法器/加法器位宽和截断报告 |
| signed/unsigned | IQ/Lag 显式 signed；Power 以 u32 进入无符号量化；平方的补码位型转 u32 | 检查 Procise elaboration/netlist，不接受隐式缩位 warning |
| reset | 核心均为低有效异步 assert；`top_lite` 将高有效 PL_KEY1 请求转换为异步 assert、两拍同步 release | 板上必须在配置后施加一次有效复位；正式 reset source/约束待确认 |
| ready/valid | payload 在 valid 且 downstream stall 时由各弹性级保持；只在 handshake 更新 frame state | PS/DDR adapter 必须遵守稳定性；增加板级随机 stall capture |
| FIFO | 同时钟、深度 16、支持非 2 次幂指针回绕；backpressure 不计 overflow | 数组为异步读，可能推成 LUT/寄存器而非 BRAM；若改用厂商 FIFO，需重新 bit-exact/握手验证 |
| frame boundary | accepted sample 0/1023 产生 start/end；Lag 第一项为 0；帧内 error 粘滞 | 丢样 adapter 必须置 error/drop；板上检查跨帧状态不泄漏 |
| tensor boundary | 五通道 channel-major 地址；frame_done 为 valid-qualified sideband，IRQ 为被接受的末拍完成事件 | capture/adapter 只在 `m_write_valid && m_write_ready` 写入 |
| CDC | 核心内部没有 CDC，全部属于一个 `pl_clk` 域 | PS、DDR、FFT、DMA 或其他时钟域必须在核心外使用已确认的异步 FIFO/CDC IP |
| 可综合语法 | 核心不含仿真专用语法；使用 `$clog2`、参数化 sized cast、SystemVerilog signed array | 先做 Procise elaborate；若工具不支持语法，只允许等价语法兼容改写并重新回归 |
| 资源/时序风险 | 6 个 16x16 feature 乘法 + 5 个最大 33x32 可配置量化乘法；variable shift 可能成为大 barrel shifter | 仅以 Procise synth/P&R/STA 为准；当前不声称 DSP、频率或吞吐实测 |

## 4. 直接导入、厂商生成和待确认三类边界

### 4.1 我们编写并可直接导入 Procise

首版文件集：

```text
hardware/fpga/rtl/common/iq_stream_fifo.sv
hardware/fpga/rtl/framing/iq_frame_controller.sv
hardware/fpga/rtl/features/qam_feature_pipeline.sv
hardware/fpga/rtl/quantization/feature_quantizer.sv
hardware/fpga/rtl/tensor/tensor_packer.sv
hardware/fpga/rtl/common/mandatory_core_path.sv
hardware/fpga/rtl/top/top_lite.sv
```

首版不必导入 `rtl/interfaces/*.sv`，避免在厂商工具支持尚未确认时增加 interface
语法依赖。所有 TB、Python、CSV/HEX、AI 文件和 docs 都不能作为综合源。

### 4.2 必须由 Procise/厂商 IP 或官方生成流程提供

- JFMQL30TAI676H 器件/封装数据库；
- PS block/configuration 与 PS 启动初始化；
- PL DDR3 controller/PHY、校准逻辑和板级参数；
- PLL/MMCM/clock/reset（若需要频率变换或 DDR 参考时钟）；
- PS-PL interconnect、时钟转换、异步 FIFO；
- DMA 或厂商推荐的等价 memory mover；
- FFT IP（Advanced Path 开始后才使用）；
- 片上逻辑分析/调试 IP（若 Procise 提供且验证包需要）；
- bitstream、QSPI/SD 固化与 JTAG programming flow。

不得在仓库中伪造这些模块或端口。

### 4.3 已有芯片基础但必须等 BSP/官方示例确认

完整版芯片资源表已经确认：2 个主 AXI 32/64-bit、2 个从 AXI 32/64-bit、4 个高性能
AXI 64-bit、16 个中断和 8 个芯片 DMA 通道。这些信息证明规划的数据链具有芯片基础，
但没有给出实际工程中的 IP 名称、端口、地址和软件接口，因此以下事项仍需确认：

- Procise/PS 配置中各主从/高性能 AXI 端口的实例名、启用方式、地址图和时钟域；
- PS DDR 与 PL DDR 的可见性、物理地址、缓存一致性、buffer ownership；
- 8 个芯片 DMA 通道的用途，以及是否另有通用 PL memory mover；MM2S/S2MM、
  descriptor、burst、IRQ 的实际接口；
- Linux 驱动、reserved-memory、Device Tree 和用户态映射方式；
- NPU 如何取得 tensor：共享 DDR、copy、runtime API、layout/alignment/scale；
- USB SDR/GigE SDR 驱动的持续吞吐和 DDR replay buffer 策略；
- Procise 支持的约束格式、时钟声明、IO 标准和编程器连接。

## 5. Procise 新建工程后的人工步骤

1. 在 Procise 器件数据库中确认完整 part 为 JFMQL30TAI676H；记录 package、speed
   grade 和工具版本，不凭近似型号继续。
2. 新建空 RTL 工程，不导入旧完整版板工程；按 4.1 的顺序加入 7 个设计源并将
   `top_lite` 设为 top。
3. 先只执行 analyze/elaborate，处理 unsupported syntax 或位宽 warning；任何兼容
   改写都必须保持 Golden 零差异。
4. 从 Lite 完整原理图/官方 example 导入或手工核对用户 PL 时钟、PL_KEY1 和
   PL_LED1..4 约束；不得把 PL DDR 200 MHz 参考时钟当普通用户时钟。
5. 在尚无 PS/DDR adapter 时，用确认的调试/测试源驱动抽象 IQ 入口；保持所有信号
   与 `pl_clk` 同域。
6. 执行 synth、P&R、STA；保存 inferred multiplier/RAM、关键路径、时钟和 warning
   报告。失败时先定位兼容/时序原因，不改变算法常量来“过综合”。
7. 用 PL JTAG U19 下载临时 bitstream，按 `board_validation/README.md` 重放固定向量，
   导出 accepted transfer CSV 并运行零容差比较。
8. 核心通过后，再从官方 PS/BSP 示例建立 PS-PL、DDR、DMA/等价 mover 与 IRQ
   adapter；每加一层都重复回归与板上 capture。
9. 最后才接 NPU runtime 与 USB/GigE SDR。Advanced Wideband RTL 另立阶段，不在
   本次 Procise 收口中混入。

## 6. 风险清单

1. **P0—资料缺口**：芯片级 AXI/DMA 数量已知，但仍缺 Lite 完整原理图、官方约束、
   BSP、地址图和 PS-PL/DDR/DMA 示例。
2. **P0—时钟歧义**：手册汇总表“PL 200 MHz”与详细章节“100 MHz 用户晶振 +
   200 MHz DDR 时钟”不能混用。
3. **P0—数据搬运**：USB/GigE 在 PS；持续 IQ 从 PS DDR 到 PL 的官方通道尚未确认。
4. **P1—DDR/NPU coherency**：buffer 地址、cache flush/invalidate、alignment 和 NPU
   ownership 尚未知。
5. **P1—综合资源**：可配置宽乘法器和 variable shift 可能消耗较多 DSP/LUT 或成为
   关键路径；只有真实综合/STA 能定量。
6. **P1—FIFO 映射**：当前小 FIFO 异步读不保证推成 BRAM；功能正确但资源实现待审。
7. **P1—CDC/reset**：板级 adapter 未实现前，任何跨 PS/DDR/PL 时钟连接都不安全。
8. **P2—工具兼容**：Procise 对 SystemVerilog sized cast、signed array 和 interface 的
   支持需实际 elaborate；核心首版已避免依赖 interface 文件。
9. **P2—验证可观察性**：板上如何导出 raw Power/Lag 需 ILA/BRAM dump/PS utility
   三选一，等待官方调试 IP/BSP。
