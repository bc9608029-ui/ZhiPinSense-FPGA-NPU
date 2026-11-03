# fix10class24-passive-scan-prep1 板测手册（简短 · 两阶段）

本 PATCH 是 **flat 覆盖包**：在已部署四层基线的板端树根解压即可。
最高允许状态 `M29-RML24-FIX10CLASS24-PASSIVE-SCAN-PREP1-READY-FOR-BOARD-TEST`。
禁写 `RF_PASS` / `RUNTIME_INTEGRATED` / “扫频识别已完成”；识别准确率**另行验收**，不与检测通过混为一谈。

## 交付物边界（先读）

- 本任务交付的是**扫描实现 + 控制接口**：`board_package/passive_scan.hpp`（header-only，
  iCraft/libiio-free，纯逻辑状态机 + 能量检测器 + 分类契约门），已由 host 测试
  `host_tests/test_passive_scan.cpp`（44/0）验证。
- **本 PATCH 不含板端 producer/可执行文件**：把 `ScanDeviceControl` 背到 `pluto::Device` 并逐帧喂
  `PowerSpectrum` / 捕获 IQ 是**后续集成步骤**（任务书明确“不碰板、不操作 SDR、不发射”）。
  因此下述两阶段是**板端接入后的验证程序**，先按步骤 1 窄频段通过，再扩展步骤 2。
- 检测（候选信号找到并记录）与识别（调制类别）**是两个概念**：本任务里识别恒为
  `CLASSIFICATION_UNAVAILABLE`（分类契约门 fail-closed），**不会**把 softmax 最高类别当可靠识别。

## 步骤 1 — 窄频段验证（必须先做，通过才进步骤 2）

频段：例如 `--start 2400000000 --stop 2401000000 --step 1000000`（1 段 2 MHz 覆盖，Pluto 范围内）。

逐项核对（每一项都对应状态机的可观察行为）：

1. **切频** — 每步 LO 写入后必须读回，且 `|读回 − 期望| ≤ lo_tolerance_hz`；读回超差 →
   `Error` + `restore_params()`（fail-closed）。核对：LO 显示值 == 步中心，无偏差告警。
2. **settle 丢帧** — 切频 + `flush_rx()` 后丢弃 `settle_frames` 帧再进入检测，**旧频段帧不得串扰**
   新步。核对：切频瞬间的旧频谱峰不被记为新步候选。
3. **检测** — 能量检测器（percentile 噪声底 + 阈值 + DC/边沿守卫）只报**真候选**；同一步多簇
   按峰值取 top-N（`max_candidates_per_step`），超限标 `unresolved`。核对：噪声段 0 候选；有信号段
   ≥1 候选，`snr_db`/`occupied_bins`/`peak_power_dbfs` 与注入信号一致。
4. **停止 / 恢复** — `stop()` 幂等，且**恰好一次** `restore_params()` 把 LO/BW/gain 写回快照；
   `start()` 前 `save_params()` 快照。核对：停止后 LO/BW/gain 回到启动前值，重复 stop 不重复恢复。
5. **结果身份** — 每条记录含 `record_id`（单调）、`step_lo_hz`、`candidate_freq_hz`、`snr_db`、
   `iq_sample_count`、`iq_truncated`、`iq_sha256`（捕获 IQ 字节 SHA-256）、`classification_outcome`
   （恒 `CLASSIFICATION_UNAVAILABLE`）。核对：同一次捕获重复跑，`iq_sha256` 相同（身份稳定）；
   `iq_sample_count ≤ max_capture_samples`；历史长度 `≤ max_history`。

## 步骤 2 — 步骤 1 通过后才扩展扫描范围

- 把 `stop_hz` 逐步放大（例如 2400→2430 MHz），**不改变**检测/停止/恢复/身份逻辑，只验证：
  - 覆盖规划无缝隙（`step_hz ≤ rx_sample_rate × usable_bw_ratio`，默认 1 MHz ≤ 2.048 MHz），
    各步中心 `center_hz(i)` 首尾含端点。
  - 长时间跑不增长内存（候选数、IQ 保存量、历史长度均有硬上限）。
- 若窄频段未通过，**不得**直接上宽频段。

## 记录示例（SYNTHETIC，非真实 RF）

`docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_DEMO_RECORDS.tsv` 与
`docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_RESULT_LIST.md` 是 `make_passive_scan_demo`
 生成的**格式示例**（脚本假设备 + 合成频谱），**不是真实 RF 测量**，也**不含任何调制识别**。

## 安全红线（本任务不越界）

- 纯 RX；**禁启动 TX / 回环 / 发射**；`ScanDeviceControl` 只允许 `set_rx_lo/set_rx_bw/set_rx_gain/
  flush/save/restore`。
- 不放宽 0.100 门、不改冻结 BF16 模型 json `28272abc…`/raw `c1781aec…`、恢复器、canonical、
  分类窗口与预处理链。
- 识别准确率**另行验收**，绝不以“检测通过”冒充“识别完成”。

详见 `docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_AUDIT.md` 与 `docs/reuse_and_gap_review.md`。
