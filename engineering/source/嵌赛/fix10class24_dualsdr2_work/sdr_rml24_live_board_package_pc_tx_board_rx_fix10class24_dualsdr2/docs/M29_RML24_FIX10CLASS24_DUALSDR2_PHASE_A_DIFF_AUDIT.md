# M29 RML24 fix10class24-dualsdr2 — Phase A 只读差异审计（逐项对照）

- 任务书：39e5（fix10class24-dualsdr2，诊断 + 最小修复，24 类 BF16 双 SDR 恢复稳定性失败）
- 基线（只读，不改）：`fix10prep3` 树的 23 类双 SDR runner（已过板 PASS 的恢复路径）
- 工作树：`fix10class24_dualsdr2`（24 类 BF16 双 SDR runner）
- 方法：对两份 `board_package/*.hpp` 与 `host_tools/*` 做 SHA-256 字节级比较；差异项再做逐行 diff；恢复参数从源码逐字段核对。
- 结论：**24 类失败不是 23→24 同步缺口**。恢复路径 59 个共享头字节一致，唯一差异是 24 类专属的合同/相位/runner/rml24 头；两 runner 传入的 `EstimateConfig` 与 `recover_payload_with_coarse_cfo` 调用点逐字节一致。**关键缺口**：23 类 runner 携带的 `--dump-failed-rx` 失败样本落盘 + 5 个 payload 分数定时诊断字段，在 24 类 runner 中被丢弃（Phase B 补齐对象）。

---

## 1. 头文件字节级对比结果

### 1.1 共享头（两份树同名文件）—— 59 个「字节一致」，2 个「差异」

**恢复 / 训练 / 帧布局（红线恢复路径，全部字节一致）**

| 头文件 | 结论 |
|---|---|
| `iq_rf_sync_recovery.hpp`（`a8b3b603…`） | 字节一致 |
| `iq_dual_sdr_coarse_cfo_recovery.hpp`（`447f56f7…`） | 字节一致 |
| `iq_rf_training_frame.hpp` | 字节一致 |
| `iq_rf_frame_layout.hpp` | 字节一致 |
| `iq_rf_per_frame_recovery.hpp` | 字节一致 |
| `iq_rf_tx_provenance.hpp` | 字节一致 |
| `iq_rf_fix9r_baseline.hpp` / `iq_rf_fix9r2a_diagnostic.hpp` / `iq_rf_fix9r2b_diagnostic.hpp` / `iq_rf_fix9r2d_diagnostic.hpp` | 字节一致 |

**传输 / 状态机 / 双 SDR（字节一致）**

| 头文件 | 结论 |
|---|---|
| `iq_pc_tx_board_rx_transfer_fix10.hpp`（`f1454bd2…`，TCP 状态机 + `build_tx_burst_from_frozen`） | 字节一致 |
| `iq_pc_tx_board_rx_23class_fix10.hpp`（`2504faa4…`，已过板的 23 类 runner） | 字节一致 |
| `iq_dual_sdr_23class_fix10.hpp` / `iq_dual_sdr_transfer_fix10.hpp` | 字节一致 |
| `iq_rf_loopback_transfer.hpp` / `iq_rf_loopback_transfer_fix9r.hpp` / `iq_digital_loopback_transfer.hpp` | 字节一致 |

**canonical 训练帧（字节一致）**

| 头文件 | 结论 |
|---|---|
| `iq_fix10_canonical_frame.hpp` | 字节一致 |
| `iq_fix10_canonical_frame_data.hpp` | 字节一致 |

**数字回环 / 纯净 IQ / 单 SDR 回环 / NPU / RML / 板端基础设施（其余 40 个，全部字节一致）**

`iq_digital_loopback.hpp`、`iq_digital_loopback_sync.hpp`、`iq_digital_loopback_runner.hpp`、`iq_digital_loopback_sweep.hpp`、`iq_clean_iq_23class_fix10.hpp`、`iq_clean_baseline.hpp`、`iq_rf_loopback.hpp`、`iq_rf_loopback_23class.hpp`、`iq_rf_loopback_23class_fix9r.hpp`、`iq_rf_loopback_ab.hpp`、`iq_rf_loopback_level_sweep.hpp`、`iq_rf_loopback_report.hpp`、`iq_rf_loopback_runner.hpp`、`npu_classifier.hpp`、`npu_classifier24.hpp`、`npu_rearm_state.hpp`、`rml23_merged.hpp`、`logits_export.hpp`、`board_common.hpp`、`band_scan.hpp`、`capture_hook.hpp`、`control_channel.hpp`、`control_client.hpp`、`delay_gate.hpp`、`gate10_settle.hpp`、`live_rx_gating.hpp`、`mode_control.hpp`、`pl_ddr_register_map.hpp`、`producer_12class.hpp`、`result_frame_rml23_parse.hpp`、`result_frame_v2_parse.hpp`、`rf_fix_helpers.hpp`、`synthetic_iq_generator.hpp`、`synthetic_iq_roundtrip.hpp`、`synthetic_iq_runner.hpp`、`touch_evdev.hpp`、`touch_geometry.hpp`、`touch_mode_control.hpp`、`ui_dirty_state.hpp`、`ui_state_map.hpp`、`unix_socket_server.hpp`、`work_mode_engine.hpp`。

**差异（仅 2 个，均为 24 类专属，非恢复路径）**

| 头文件 | 差异性质 | 说明 |
|---|---|---|
| `chain_common.hpp` | `contract_23()` vs `contract_24()` | 24 类契约（无 24→23 合并），恢复无关 |
| `gate9_phase.hpp` | 新增 24 类 phase 枚举 | 24 类 phase 定义，恢复无关 |

**仅存在于 24 类树（4 个，24 类专属新增）**

| 头文件 | 说明 |
|---|---|
| `iq_pc_tx_board_rx_24class_bf16_fix10.hpp`（`edc1a75a…`） | 24 类双 SDR runner（本次诊断/修复对象） |
| `iq_clean_iq_24class_bf16_fix10.hpp` | 24 类 BF16 纯净 IQ（数字直注）路径 |
| `rml24_raw.hpp` | `raw24_predict`（无 AM-SSB 合并） |
| `rml24_bf16_baseline.hpp` | 7 列 raw24 BF16 基线加载 |

### 1.2 host_tools（PC TX 端）—— 全部「字节一致」

`pc_tx_sdr_fix10.py`、`fix10_tx_protocol.py`、`fix10_iio_attr.py`、`fix10_burst_cache.py`、`build_burst_cli.cpp`、`build_burst_cli.sh`、`frame_component_digest.cpp`、`frame_component_digest.sh` —— 均与 fix10prep3 字节一致。PC 端 TX 启动/停止/样本切换流程未变。

---

## 2. 逐项对照表（任务书 Phase A 指定项目）

| # | 项目 | 23 类（已过板） | 24 类 | 结论 |
|---|---|---|---|---|
| 1 | RX 捕获长度 | `iqrflayout::capture_complex(delay_margin)` = 2×59904 + 8192 = 128000 复 | 同 | **字节一致**（同一 `iq_rf_frame_layout.hpp`） |
| 2 | RX refill 次数 | `iqrfloop_run::kRfDiscardRefills` 次 discard + `kRfDiscardComplex` 样本/次 | 同 | **字节一致** |
| 3 | RX 缓冲布局 | `std::vector<int16_t>` 交错 I/Q，`capture_contiguous` + `cont.ok()` 连续性门 | 同 | **字节一致** |
| 4 | negative control → 正式捕获状态转换 | `run_rx_negative_control`（kRfNoiseWindows 窗口、kRfNoiseStableMaxRatio、rail 检查）→ `recreate_rx_buffer` → discard → `capture_contiguous` | 同 | **字节一致**（两 runner 的 `run_rx_negative_control` 逐行相同） |
| 5 | canonical 训练帧 | `fix10canonical::buildTxBurstFromFrozen`（内嵌 preamble/payload_training/tail） | 同 | **字节一致**（`iq_fix10_canonical_frame.hpp` + `_data.hpp` 字节一致） |
| 6 | burst 布局 | `[preamble 1024][settling-zero 1024][payload-training 1024][payload 53760][guard-zero 2048][tail 1024]` = 59904 复 | 同 | **参数一致**（`iq_rf_training_frame.hpp` 常量一致） |
| 7 | coarse CFO 输入 | `iqrftrain::deinterleave(rx_int16)` 全捕获 | 同 | **字节一致** |
| 8 | coarse CFO 输出/去旋转顺序 | `ls_gain` preamble vs payload-training 相位差（±625 Hz 无歧义）→ `derot[n]=rx[n]·exp(-j2π·coarse·n/fs)` → 再 `estimate` | 同 | **字节一致**（`iq_dual_sdr_coarse_cfo_recovery.hpp` 字节一致） |
| 9 | 整数 timing 搜索范围 | `estimate` 全捕获 `[0, rx.size()-kTotalBurstComplex]`（`search_limit=0`） | 同 | **参数一致** |
| 10 | fractional timing 搜索范围 | 两阶段网格：1/32 粗 + 1/512 精（±16/512），Lanczos sinc（r=12） | 同 | **字节一致**（`detail::estimate_fractional_timing`） |
| 11 | payload training 窗口起点 | `timing_offset + kPayloadTrainingOffset`（=2048） | 同 | **参数一致** |
| 12 | gain/phase/fine CFO 估计顺序 | preamble LS gain → tail 重定位 → fine CFO（preamble-vs-tail 相位差，±21.74 Hz）→ de-ramped 复增益 → payload-domain 训练块 gain/corr/residual → 模糊峰检查 → 有效性门 | 同 | **字节一致**（`iq_rf_sync_recovery.hpp::estimate` 字节一致） |
| 13 | residual 定义/归一化分母 | `sqrt(Σ‖err‖² / Σ‖model‖²)`，err=rx−a·ref·exp(jph)，1024 复 payload 训练块，de-ramped（CFO/SRO 建模后） | 同 | **字节一致** |
| 14 | 两 runner 传入的完整 `EstimateConfig` | `min_corr=0.9, max_residual=0.10, max_cfo_hz=fine_cfo_range_hz()(=21.74), max_sro_ppm=30.0, search_limit=0, payload_tx_target_rms=target_rms(=2048)` | 同 | **参数一致**（24 类 runner 第 758–764 行与 23 类 runner 第 806–817 行逐字节一致） |
| 15 | `recover_payload_with_coarse_cfo` 调用 | `iqdual23fix10::recover_payload_with_coarse_cfo(rx, rec_cfg, expected.tx_scale)` | 同 | **字节一致** |
| 16 | PC TX 启动/停止/样本切换 | `send_prepare→recv_prepared→send_start→recv_ready→capture→send_captured→recv_stopped`，`tx_restore` 读回验证，TCP 超时 ≤2s | 同 | **字节一致**（`iq_pc_tx_board_rx_transfer_fix10.hpp` + host_tools 字节一致） |
| 17 | CFO 无歧义范围 | ±625 Hz = fs/(2·2048) | 同 | **参数一致**（`iq_pc_tx_board_rx_transfer_fix10.hpp::coarse_cfo_unambiguous_range_hz`） |
| 18 | fine CFO 范围 | ±21.74 Hz = fs/(2·58880) | 同 | **参数一致** |
| 19 | residual 门限 | `kPayloadTrainingResidualMax = 0.10` | 同 | **参数一致（红线未动）** |

---

## 3. 关键发现（Phase B 的补齐对象）

23 类 runner（`iq_pc_tx_board_rx_23class_fix10.hpp`）存在、但 24 类 runner（`iq_pc_tx_board_rx_24class_bf16_fix10.hpp`）**丢弃**的差异（经逐行 diff 确认）：

1. **`--dump-failed-rx` 标志 + `write_ci16_le` 辅助函数 + 失败样本落盘块**：23 类在 fidelity gate 失败时，将 `rx_int16` 写为 `failed_rx_<source_index>.ci16` + 最小 JSON 元数据（`format/source_index/file_name/modulation/complex_count/byte_count/sha256/failure/coarse_cfo_hz/fine_cfo_hz/fractional_timing_samples/payload_best_* /payload_training_residual`）。24 类完全删除该块。

2. **5 个 payload 分数定时诊断字段的 stdout 打印**：23 类 CFO 日志行额外打印 `payload_fractional_corr_before/after`、`payload_best_fractional_timing_samples`、`payload_best_fractional_corr`、`payload_best_fractional_preamble_corr`；24 类 CFO 日志行删除这 5 个字段。

其余（恢复配置、`buildTxBurstFromFrozen`、capture、negative control、fidelity gate、D2 restore、NPU 推理路径）在结构上对应，差异仅为 24→23 合并 vs raw24 无合并、`deployed_class` vs `raw24_class` 等 24 类专属语义。

---

## 4. 结论

- 24 类 BF16 双 SDR 恢复稳定性失败**不可归因于 23→24 同步缺口**：恢复数学、CFO 序列、fractional 定时、residual 定义、门限、capture/negative-control 状态机、canonical 帧、PC TX 流程全部与已过板的 23 类路径**字节/参数一致**。
- 为定位失败根因，Phase B 必须把 23 类曾有的失败样本落盘能力以**更完整的形式**补回 24 类 runner（`--dump-failed-rx` 全样本产物 + `--dump-recovery-diagnostics` 恢复诊断），Phase C 用离线 C++ 重放器复用生产恢复函数做候选网格诊断。
