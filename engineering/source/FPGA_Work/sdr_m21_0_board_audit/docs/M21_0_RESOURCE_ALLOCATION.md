# M21-0 资源利用率审计与分配建议（Resource Allocation）

任务 id="39e5" · M21-0 · 只读审计，未修改任何工程/代码/位流/模型/交付包。

来源类别图例同 `M21_0_BOARD_CAPABILITY_AUDIT.md`。本文件逐项审计 FPGA / NPU / CPU / DDR / 实时链路（任务书 §三），并给出硬件任务分配与资源预算（§五）。

---

## 1. FPGA 利用率审计（任务书 §三.1）

**当前合并位流** `pl_ddr_mandatory_core_top_combined`（Device 7z030ffg676-2，Routed，smoke_v1）。

| 资源 | Used | Available | Util% | 来源 |
|---|---|---|---|---|
| Slice LUTs | 41,361 | 78,600 | 52.62% | Vivado报告 |
| LUT as Logic | 35,735 | 78,600 | 45.46% | Vivado报告 |
| LUT as Memory | 5,626 | 26,600 | 21.15% | Vivado报告 |
| Slice Registers(FF) | 71,138 | 157,200 | 45.25% | Vivado报告 |
| Slice（打包） | 19,295 | 19,650 | 98.19% | Vivado报告 |
| Block RAM Tile | 141.5 | 265 | 53.40% | Vivado报告 |
| RAMB36/FIFO | 137 | 265 | 51.70% | Vivado报告 |
| RAMB18 | 9 | 530 | 1.70% | Vivado报告 |
| **DSP48E1** | **24** | **400** | **6.00%** | Vivado报告 |
| BUFGCTRL | 12 | 32 | 37.50% | Vivado报告 |
| MMCME2_ADV | 4 | 5 | 80.00% | Vivado报告 |
| PLLE2_ADV | 3 | 5 | 60.00% | Vivado报告 |
| GTXE2_CHANNEL | 0 | 4 | 0% | Vivado报告 |
| Bonded IOB | 132 | 250 | 52.80% | Vivado报告 |

**时钟频率**（Vivado 时序报告 Clock Summary）：clk_fpga_0=50MHz；clk_out1_clk_wiz_0(gp_clk)=100MHz；clk_74m25=74.25MHz / clk_371m25=371.25MHz（HDMI）；pl_ddr_refclk=200MHz / clk_ref_mmcm_400_1=400MHz / freq_refclk_1=800MHz（PL DDR）；+ NPU 核 1GHz。

**时序 WNS/TNS**（Vivado 时序报告，post-fix）：

| 指标 | 数值 | 来源 |
|---|---|---|
| WNS / TNS（Setup） | +0.030ns / 0.000ns（0 失败端点） | Vivado报告 |
| WHS / THS（Hold） | +0.029ns / 0.000ns（0 失败端点） | Vivado报告 |
| WPWS / TPWS（Pulse Width） | **−0.409ns / −0.479ns（2 失败端点）** | Vivado报告 |
| 结论 | Setup/Hold 全过；仅剩 2 处 1GHz PLLE2 域 Pulse Width 违例（**冻结已知项**，不阻塞功能） | Vivado报告 |

**DMA/显示/RF 链路占用**：
- NPU DMA 走 PL DDR 64-bit MIG（`dma=0x80000000`），与 PS DDR 物理隔离（代码常数/契约文档）。
- 显示帧缓冲 1280×720 RGB565 双缓冲，@60Hz 读带宽 ≈110MB/s、@30Hz ≈55MB/s（代码常数/契约文档）。
- RF 链路为外接 Pluto（USB），原始率 2.56M/3.84M，经 FIR 抽取到 128kHz（代码常数）。

**未使用的资源**：**DSP 376/400 空闲（94%）**；BRAM ~128 tile 空闲；GTXE2 4 路全空闲；MMCM/PLLE 已用到 60–80%（时钟资源是后续新增时钟域的主要约束）。

**结论**：FPGA 最大余量在 **DSP（94% 空）**，足以承载 FFT/能量检测/频谱/多信号处理；BRAM ~半空；LUT/FF ~半空但 **Slice 打包 98.19% 近满**，新增显著组合逻辑需同时评估布线拥塞；时钟资源（MMCM/PLLE）较紧张，新增高频时钟域需谨慎。

---

## 2. NPU 利用率审计（任务书 §三.2）

| 项 | 数值 | 来源 |
|---|---|---|
| 模型参数量 / MAC | 279,036 / 46,544,384（12 类）；24 类 280,584 / 46,545,920 | NPU编译报告/推导 |
| 单帧推理时间 | 12 类 ~1.14ms/帧（文档）；8 类参照 avg 0.67ms；12 类精确 infer_us **UNKNOWN** | 文档/实测/尚待验证 |
| 推理吞吐率 | **UNKNOWN（无直接实测）**；推导：8 类 ~0.67ms/帧 ≈1490 帧/s 计算上限；若每帧 reopen 则 ~263ms ≈3.8 帧/s | 推导 |
| NPU 利用率 | **无运行时实测（UNKNOWN）**；推导：46.5M MAC/1.14ms ≈41 GMAC/s ≈ 0.5–1% 的 8 TOPS 峰值（TOPS 与 MAC 口径不同，属 `尚待验证`） | 推导 |
| 模型加载时间 | **UNKNOWN（无证据）**；模型 raw 2,851,472 字节，lazyLoadParamsFromFile | 无证据/代码常数 |
| DDR↔NPU 搬运时间 | 无单独隔离测量；参照：8 类 per-frame setup（张量分配+写入+reset）avg 0.045ms / max 0.116–0.123ms | 实测 |
| 是否数据准备而非 NPU 计算限制 | **是**。瓶颈不在 NPU 计算（~1ms），而在 **Device 生命周期管理**：每帧 reopen ≈263ms 是 NPU forward 的 ~200–400 倍；持久 Session+每帧 reset(1) 后 forward 才降至毫秒级 | 实测/代码常数 |

**结论**：NPU 算力（8 TOPS）对当前 46.5M MAC 模型而言**近乎空转（推导 ~1%）**；真正的开销陷阱是 Device 生命周期（已修复但需上板复测）与周期性尖峰（见 §5）。NPU 有充分余量承载 24 类、OE 模型甚至多头/多模型——**前提是运行时支持多模型驻留/并行（当前 UNKNOWN）**。

---

## 3. CPU 利用率审计（任务书 §三.3）

| 项 | 结论 | 来源 |
|---|---|---|
| UI/触摸/控制 | UI 进程单线程 poll(2)，`--display-refresh-hz 30`→tick 33ms；触摸 evdev `O_NONBLOCK`、控制 client `O_NONBLOCK`+`poll(0)`，均不阻塞渲染 | 代码常数 |
| 预处理/OOD 评分 CPU 开销 | 预处理在 producer 主线程；OOD logit_margin 仅两次 O(12) 线性扫描+O(12) all_finite（double，无超越函数），每次判决 ~36 次比较，**可忽略** | 代码常数 |
| 单核/多核 | UI=1 线程；Gate9 producer=主线程+1 个 `std::thread` 控制线程（仅控制 socket/ack）；两进程 AF_UNIX 通信；**无绑核/nice 证据** | 代码常数 |
| 空闲核 | 4 核中约 **3 核空闲**（仅 ~3 个线程，无绑定） | 推导 |
| 轮询/无效唤醒 | M16 旧版每 33ms tick 无条件渲染→拷贝→msync→翻转，静止帧纯空转，**实测单核 ~32% 空闲 CPU**（持续 ~1min55s）；M17 FlipScheduler 事件驱动翻转已消除空转，修复后期望 ~0–2%（**尚待验证**） | 实测（用户转录）/契约文档 |
| 无 top//proc 原始数据 | 除 ~32% 转录外，**无其它 CPU% 实测** | 无证据 |

**结论**：CPU 富余巨大（~3 核空闲），且存在过一个「UI 空转」问题（已修）。后续 UNKNOWN 拒识、多帧融合、扫频控制、事件记录、触摸 UI 均可落 CPU 且有余量，无需新核；若做 E（多信号并行分类协调）或 L（记录回放）才需考虑多线程/绑核。

---

## 4. DDR 与总线审计（任务书 §三.4）

| 项 | 结论 | 来源 |
|---|---|---|
| 拓扑 | PS DDR 1GB（32-bit）承载 Linux+帧缓冲+日志；PL DDR 2GB（64-bit MIG）承载 NPU DMA+帧缓冲，二者物理独立 | 契约文档/代码常数 |
| IQ 输入带宽 | 原始 2.56M×4B=10.24MB/s（16-bit I/Q），极小 | 推导 |
| NPU 输入带宽 | 2048 float×4B=8KB/帧；@1000fps=8MB/s，极小 | 推导 |
| framebuffer 带宽 | 1,843,200B/帧；@60Hz≈110MB/s、@30Hz≈55MB/s（文档估算） | 契约文档/推导 |
| 重复内存复制 | **存在且未优化**：producer 每帧 fresh `vector<float> scaled(2048)`+复帧 cf；NPU 输入每帧 `Tensor.mallocOn(host)`+write+新建 vector<Tensor>；NPU 输出每帧 bytes+to(Host)+memcpy。12 类热路径**仍每帧 fresh 分配，无 staging 预分配**；仅 joint-stress `fixed` 诊断程序实现 input_allocations==2 复用（未上板） | 代码常数 |
| 缓存同步瓶颈 | 无明确证据；framebuffer 用标量 volatile 16-bit 写 + msync/sync_for_device（已规避 SIGBUS） | 代码常数 |
| 峰值/持续带宽 | PL DDR 实际 ~800MT/s（时序报告），手册称 1600MHz（口径待核）；即使按 6.4GB/s，当前总流量（framebuffer 110MB/s + NPU 8MB/s + IQ 10MB/s）也远低于带宽 | Vivado报告/推导 |

**结论**：DDR 带宽富余极大；真正的问题是**每帧重复内存分配/拷贝**（producer/NPU 输入/输出均为 fresh 分配），属潜在尖峰嫌疑，应作为优化项（复用/预分配），但并非当前瓶颈。

---

## 5. 实时链路延迟审计（任务书 §三.5）

链路：RF 采集(capture_contiguous 单 refill) → FIR 重采样/NCO/receiver_scale 预处理 → 帧切分 1024 复数 → producer 逐帧 RMS+presence+scaled tensor → NPU 推理 → argmax → UI(socket→渲染→submit_frame 翻转)。OOD 判决**尚未接线**到板端链。

| 环节 | 数值 | 来源 |
|---|---|---|
| NPU forward（正常） | ~0.65–1.0ms | 实测（用户日志转录） |
| **周期性尖峰** | forward=425/604/937ms，cycle58 起每 6 cycle 落在每轮第一 NPU 帧 frame=7；两次运行位置一致 | 实测（用户日志转录，根因未确认） |
| 端到端 9 阶段分段（reset/dequantize/input_prepare/forward_submit/wait_ready/output_to_host/output_read/forward_legacy/total_inference） | 硬门已定义（gt_100ms==0、p99≤5ms、max≤10ms、gt_10ms==0），**实际板端数值 UNKNOWN**（待上板回传） | 代码常数/尚待验证 |
| UI 诊断页延迟表 | render 4.2/copy 0.8/sync+flip 1.1/capture 5.6/total 12.4ms —— **硬编码展示字符串，非实测** | 代码常数 |
| 每帧 setup（张量+reset） | 8 类 avg 0.045ms / max 0.116–0.123ms | 实测 |

**结论**：
1. 正常路径 NPU forward ~1ms，满足实时。
2. **周期性 425–937ms 尖峰是真正的实时性隐患**，根因未确认（v2/v3 均为 READY-FOR-HARDWARE-LATENCY-RETEST，需用户上板复测）。**在尖峰根因确认前，任何依赖严格实时/低延迟的功能（E 多信号、J 多任务）都不应上**。
3. 端到端精确分段延迟 = UNKNOWN，待 latency 复测回传。

---

## 6. 硬件任务分配与资源预算（任务书 §五）

**分配原则**：FPGA=高速/固定流程/强并行数据通路；NPU=卷积/矩阵/网络推理；CPU=控制/OOD 评分/状态机/记录/UI；DDR=帧缓存/IQ 环形缓冲/事件回放。**不把适合 FPGA 的高速逐样本任务推给 CPU，也不为用 NPU 而把简单阈值判断改成神经网络。**

### 6.1 各路线资源预算

| 资源 | 路线 A（最小风险） | 路线 B（平衡版） | 路线 C（最大展示） |
|---|---|---|---|
| FPGA DSP | 复用现有 FFT（≈0 新增） | +FFT/峰值保持（瀑布图，DSP 富余可容纳） | +CFAR/峰值聚类/多通道（需评估布线+时钟） |
| FPGA BRAM | ≈0 | +瀑布历史帧/占用统计 | +多信号分段缓冲 |
| NPU | 换 24 类（+1.5KB int8 权重） | 同 A | +逐信道分类/多头（多模型驻留 UNKNOWN） |
| CPU 核 | 仍 ~2 线程 | +扫频状态机+事件索引（可落空闲核） | +多信号协调/指纹库（需多线程/绑核） |
| PL DDR | framebuffer+NPU（富余） | +瀑布历史+IQ 环形缓冲 | +多信号分段+指纹库 |
| 关键风险 | 24 类训练/int8 | 显示带宽实测、扫频联动 | 尖峰未解、多模型驻留、数据采集 |

### 6.2 逐功能分配（详见 `M21_0_FEATURE_ROADMAP.md` §2 表）

核心结论：**D（信号存在）/H（参数估计）落 FPGA（复用现有 FFT/能量检测），勿改造成 NPU 网络**；**C（OOD-U）当前落 CPU（logit_margin 后处理），根本改善走 NPU 上 OE 训练模型**；**E（多信号）的 FFT/CFAR 落 FPGA、分类落 NPU、协调落 CPU**——但受「尖峰未解 + 多模型驻留 UNKNOWN」约束，属远期。

---

*相关：`M21_0_BOARD_CAPABILITY_AUDIT.md`（板卡能力+统一资源表）、`M21_0_FEATURE_ROADMAP.md`（功能调研+评分+三路线）、`M21_0_FINAL_RECOMMENDATION.md`（组合判断+12 问+框图）。*
