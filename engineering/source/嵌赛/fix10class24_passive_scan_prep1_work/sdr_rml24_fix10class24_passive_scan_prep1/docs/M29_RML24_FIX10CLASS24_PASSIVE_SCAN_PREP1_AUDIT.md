# M29 RML24 fix10class24-passive-scan-prep1 — 接收端扫频功能准备审计

任务：准备**单 SDR 接收端无源扫频**功能（用户设频段 → 调 RX LO → settle/flush → 检测候选 →
驻留捕获 → **仅当输入契约成立才尝试分类** → 记录 → 继续）。纯 RX，不发射、不训练、不碰板。
最高允许状态 `M29-RML24-FIX10CLASS24-PASSIVE-SCAN-PREP1-READY-FOR-BOARD-TEST`。

## 实现（✅ 完成）

- `board_package/passive_scan.hpp`（header-only，iCraft/libiio-free，唯一 include 是
  `sdr_adapter/sha256.hpp`）：
  - `PassiveScanConfig` + `CoveragePlan`（band ⊆ 325..3800 MHz；`step_hz ≤ rx_sample_rate ×
    usable_bw_ratio` 无缝隙 fail-closed；`center_hz(i)` 首尾含端点）。
  - `ScanDeviceControl`（**唯一设备效果**：`set_rx_lo` 读回 / `get_rx_lo` / `set_rx_bw` /
    `set_rx_gain` / `save_params` / `restore_params` / `flush_rx`）。
  - `EnergyDetector`：percentile 噪声底 + `threshold_dbfs` + DC/边沿守卫 + 连续段提取 +
    `min/max_occupied_bins` + `min_snr_db` + 超限 unresolved（top-N 有界）。
  - `ClassificationContractGate`：**恒 fail-closed 到 `CLASSIFICATION_UNAVAILABLE`**；可选 raw
    argmax 只能以显式 `UNVERIFIED_CANDIDATE` 附上（`verified=false` 恒成立，绝不冒充可靠识别）。
  - `ScanRecord` + `ScanResultStore`（`max_capture_samples` / `max_candidates_per_step` /
    `max_history` 三处硬上限；单调 `record_id`；IQ SHA-256 身份）。
  - `PassiveScanStateMachine`：`start()` 快照 → Tuning（写+读回±`lo_tolerance_hz`+flush）→
    Settling（丢帧防旧帧串扰）→ Detecting → Capturing（有界截断）→ Classifying（建记录+append）→
    Next/Complete/Stopped/Error；`stop()` 幂等 + 恰好一次 restore；LO 读回超差 → `Error` + restore。

## Host 测试（✅ 44/0）

`host_tests/test_passive_scan.cpp`（已接入 `build_host_tests.sh` + `run_tests.sh`，g++
`-std=gnu++17 -O2 -Wall -Wextra -Werror`，WSL Ubuntu g++ 15.2.0 编译通过、运行 **44 pass / 0 fail**）。

覆盖：配置校验（stop<start / band 越界 / step==0 / step>覆盖宽 / detect_frames==0 /
min_occupied_bins==0）；覆盖规划（4 步、首尾含端点、overlap≥0）；能量检测器（纯噪声无候选、单音、
DC 守卫、边沿守卫、低于 min_snr、双音、超限 unresolved 有界）；分类门 fail-closed（`CONTRACT_HELD`
永不出现；可选 UNVERIFIED 显式标注）；状态机端到端（调 LO+读回+flush、settle×2、detect→capture→
classify→record、无候选步→Complete+restore）；settle 丢帧；LO 读回超差→Error+restore；stop 幂等；
捕获截断（`max_capture_samples=8`）与有界历史（`max_history=2` 丢最旧、record_id 单调 2/3）。

## 模拟扫描记录 + 结果列表示例（✅ 已生成，显式标注 SYNTHETIC）

`host_tests/make_passive_scan_demo.cpp`（build-only 生成器，不接入 run_tests）跑完整状态机 +
脚本假设备 + 合成频谱，生成：

- `docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_DEMO_RECORDS.tsv`（5 条候选记录，9 步频段
  2400.000–2408.000 MHz，含 `iq_sha256`、`classification_outcome=CLASSIFICATION_UNAVAILABLE`）。
- `docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_RESULT_LIST.md`（结果列表格式示例）。

两件均以醒目文字标注 **SYNTHETIC / NOT REAL RF / 无调制识别**（红线：“合成或回放测试必须标明
来源，不能称为真实 RF 验证”）。

## 复用／缺口审查（✅ 见 `docs/reuse_and_gap_review.md`）

直接复用仅 `sha256.hpp`；`dsp_measure.hpp` / `pluto_device.hpp` / `producer_12class.hpp` 为接口形态
/概念复用（落到后续集成）；`band_scan.hpp` / `mode_control.hpp` / `work_mode_engine.hpp` /
`live_rx_gating.hpp` 是 12/23 类“锁频类锁定 + LO 扫描”，**不是**无源能量检测器 → 新写
`passive_scan.hpp`。冻结模型 / 0.100 门 / 恢复器 / canonical / TX 链**未触碰**。

## 红线合规（本任务逐条满足）

- 不碰板、不操作 SDR、不发射、不训练；无 TX 路径、无回环。
- 未写 `RF_PASS` / `RUNTIME_INTEGRATED` / “扫频识别已完成”。
- 未修改原始 RadioML NPU 对照任务、A↔C 审查任务、既有单/双 SDR 验证树、瀑布/星座等工作树；
  不合并其他任务补丁。
- 不伪造同步/训练相关性/residual；不放宽 0.100 门；不把 softmax 最高类别当可靠识别；可选 argmax
  显式标 `UNVERIFIED_CANDIDATE`。
- 候选数 / IQ 保存量 / 历史长度均有硬上限（`max_candidates_per_step` / `max_capture_samples` /
  `max_history`）。
- 合成示例显式标注来源，不称真实 RF。

## 待板端执行（后续集成步骤，非本任务）

板端两阶段验证程序见 `docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_BOARDTEST.md`：
步骤 1 窄频段（切频 / 检测 / 停止 / 恢复 / 结果身份）通过后，才扩展步骤 2 扫描范围；
识别准确率另行验收。
