# 复用／缺口审查 — fix10class24-passive-scan-prep1

审查目标：在实现「单 SDR 接收端扫频」之前，逐项确认既有代码哪些可复用、哪些是缺口、
哪些必须**新写**，以及为什么不能把既有「band_scan / 工作模式」误当成无源频谱检测器。

结论一句话：既有 `band_scan.hpp` / `mode_control.hpp` / `work_mode_engine.hpp` /
`live_rx_gating.hpp` 是 **12/23 类时代的“锁频类锁定 + LO 扫描”机制**，它们扫描的
对象是**已知、受控的训练帧**（知道每步 LO 上会出现哪个类），**不是**无源的能量/频谱
候选检测器。本任务需要的能力（噪声底估计 → 候选提取 → 去重 → 有界 IQ 捕获 → 分类
契约门）在既有代码中**不存在**，必须新写 `passive_scan.hpp`。下面逐项给出证据。

## 1. 复用项（直接或“接口形态”复用）

| 复用对象 | 复用方式 | 说明 |
|---|---|---|
| `sdr_adapter/sha256.hpp` 的 `Sha256::hex` | **直接复用** | 捕获 IQ 的身份 SHA-256（`passive_scan.hpp` 唯一 include 的既有头，iCraft/libiio-free）。 |
| `sdr_adapter/dsp_measure.hpp` 的 1024 点 FFT + PSD + percentile 噪声底 | **概念复用**（板端 producer 用） | 板端 producer 从 RX 帧导出 `PowerSpectrum` 时复用既有的 FFT/PSD 与 percentile 噪声底算法；本头不重复 FFT（接收者拿到现成 PSD）。 |
| `sdr_adapter/pluto_device.hpp` 的 `Device` 抽象（`set_rx_lo/get_rx_lo/set_rx_bw/set_rx_gain/flush_rx/save_params/restore_params` + `FakePlutoDevice`） | **接口形态复用**（后续集成步骤） | 本任务的 `ScanDeviceControl` 是同一语义的**更窄**接口；板端 producer（后续集成，非本任务）用它把 `ScanDeviceControl` 背到 `pluto::Device`，`FakePlutoDevice` 对应 host 测试里的 `FakeDevice`。 |
| `producer_12class.hpp` 的 `DeviceControl`（`set_rx_lo/set_rx_gain`） | **接口形态复用** | 证明既有代码已有“把设备控制抽象成接口、host 可注入 fake”的成熟范式；本任务沿用该范式并补上读回校验 + save/restore + flush。 |
| 冻结 24 类 BF16 模型 `28272abc…`/`c1781aec…` 与 0.100 门、canonical 三组件 | **不触碰** | 本任务**不 include、不修改**这些；分类契约门只是**引用其“契约无法证明成立”这一事实**来 fail-closed。 |

## 2. 缺口项（必须新写）

| 缺口 | 为什么既有代码不满足 | 新写内容 |
|---|---|---|
| **无源能量/频谱候选检测器** | `band_scan.hpp` 是“类锁定 LO 扫描”：它按类把 LO 切到**已知位置**去验证一个**受控训练帧**，不是“在未知频谱里找候选信号”。 | `EnergyDetector`：percentile 噪声底 + 阈值 + DC/边沿守卫 + 连续段提取 + min/max 占用 + min-SNR + 超限 unresolved。 |
| **候选去重与有界化** | 既有扫描没有“同一步多个候选、按峰值取 top-N”的去重与硬上限。 | `max_candidates_per_step` / `max_capture_samples` / `max_history` 三处硬上限（红线要求“候选数量、IQ 保存量、历史列表长度必须有上限”）。 |
| **LO 切频 + 读回校验 + flush + settle 的状态机** | `mode_control.hpp` 只管理 FIXED/AUTO_LOCK/BAND_SCAN 三态与 RUN/STOP，不含“调 LO→读回校验→flush→settle→detect→capture→record”的逐帧时序。 | `PassiveScanStateMachine`：Tuning（写+读回±`lo_tolerance_hz`+flush）→ Settling（丢帧防旧帧串扰）→ Detecting → Capturing → Classifying → Next/Complete/Stopped/Error，fail-closed。 |
| **分类契约门（防伪造）** | 既有 `live_rx_gating.hpp` / `signal_presence.hpp` 只做“信号存在→跑 NPU”的存在门，**默认对存在信号跑 NPU 并出分类**；无源信号无法证明满足冻结模型输入契约，直接出 softmax 会冒充可靠识别。 | `ClassificationContractGate`：**总是 fail-closed 到 `CLASSIFICATION_UNAVAILABLE`**；可选的 raw argmax 只能以显式 `UNVERIFIED_CANDIDATE` 附上，绝不标为可靠识别（红线：“若显示原始 argmax，必须标成未经验证的候选输出”）。 |
| **结果身份（IQ SHA + 记录）** | 既有扫描不记录“捕获了什么、捕获了多少、截断与否”。 | `ScanRecord`（含 `iq_sha256`/`iq_sample_count`/`iq_truncated`/`unresolved`）+ `ScanResultStore`（有界历史、单调 `record_id`）。 |

## 3. 结论

- **直接复用**：仅 `sha256.hpp` 的 `Sha256::hex`（其余为接口形态/概念复用，落到后续集成步骤）。
- **必须新写**：`passive_scan.hpp` 全部内容（配置、覆盖规划、设备接口、能量检测器、
  分类契约门、记录/有界历史、状态机）。
- **不触碰**：冻结模型、0.100 门、恢复器、canonical 组件、TX 链、以及 `band_scan.hpp` /
  `mode_control.hpp` / `work_mode_engine.hpp` / `live_rx_gating.hpp` 等既有头（未 include、未修改）。
- 本头**无任何 TX 路径、无回环、无训练**，仅通过 `ScanDeviceControl` 产生 RX 侧设备效果，
  满足“不得启动 TX 或调用会隐式发射的旧回环流程”的红线。
