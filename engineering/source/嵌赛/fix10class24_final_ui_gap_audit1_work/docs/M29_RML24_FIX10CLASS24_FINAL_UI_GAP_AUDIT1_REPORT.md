# M29 RML24 fix10class24 — 最终系统 UI 与操作功能缺口审查

任务：`fix10class24-final-ui-gap-audit1`（纯离线只读审查）
状态：`M29-RML24-FIX10CLASS24-FINAL-UI-GAP-AUDIT1-COMPLETE`（仅表示审查完成；不表示 UI/运行时集成或项目完成）
基线树：`F:\嵌赛\fix10class24_tx_rms_sweep1_work\sdr_rml24_fix10class24_tx_rms_sweep1`
审查日期：2026-10-19

红线遵守声明：未碰板、未操作 SDR、未训练、未改生产代码、未生成功能补丁；并行任务工作树
（original_radioml_npu_ab1 / ac_input_detailed_audit / passive_scan_prep）只读或完全避开。环境不具备处直接标"未验证"。

---

## 结论摘要（三张清单）

### ① 已有且当前证据支持可用

- START/STOP 控制 + 状态心跳：UI 显示 STOPPED 而非 STALE；ACCEPTED→APPLIED 两段 ACK。
- 顶部状态栏 + info 条（SNR/LATENCY/FRAME/SOURCE）+ staleness（默认 5000ms）+ producer 退出→STALE 检测。
- NO_SIGNAL / ACQUIRING 状态徽章；Error 处理（overflow/dropped/discontinuity/short_frame）。
- 非阻塞 UI socket（满缓冲丢弃、不阻塞分类/捕获）；队列有界（Command/Ack 各 32）。
- 23 类合并链（expA + `rml23-chain-v2` + `merge_logits_23`）：Host 验证 + 部分板端验证。
- 冻结 BF16 24 类模型资产与 `raw24_predict` 判读：板测 phase 证据（`rml24-chain-v1`，写 TSV）。
- 运维脚本（verify_package / rollback / stop_* / mode_ctl / check_live_result）与结果日志 JSONL / 诊断 TSV。

### ② 已准备但未接入或未上板验证

- 冻结 BF16 24 类 raw24 → LIVE/UI 链：仅存在于 board-test phase；UI server 无法解析 `rml24-chain-v1`。
- 缺陷修复 B1（SIGNAL_LOST/INVALID 卡死）与 B2（NO_SIGNAL 残留旧分类）：修复在 nosignal 树，未并入基线。
- 瀑布图：waterfall 树 host-only，`READY-FOR-INTEGRATION`，未并入最新板基线。
- 实时频谱曲线：仅标量卡片；曲线在 waterfall 树未集成。
- 星座·IQ 点云：离线 FileIqFrameSource 桌面验证通过，无实时帧源、无板端集成。
- AUTO_LOCK / BAND_SCAN 消费：模式状态机与 UI 按钮已接，但 live-rx 硬编码 FIXED，未真正生效。
- passive_scan（并行任务）：prepare-only，未接入 board_gate9/CMake（红线：不合并并行任务）。

### ③ 确实缺失

- 运行时频率/增益/带宽设置命令（控制通道仅 SET_MODE/START/STOP/STATUS，无 SET_FREQ/SET_GAIN/SET_BW）。
- BAND_SCAN LO 扫描（sequencer 纯逻辑未 compose）+ 扫频列表 UI 页。
- UI 参数编辑页（PARAMETERS 页仅显示测量标量，非可编辑参数）。
- 中文字形（字符集 ASCII 32..126）。
- 7 英寸目标屏分辨率适配证据（当前固定 1280x720，待确认目标屏实际分辨率）。

---

## 最小缺口闭合计划

### P0 — 正确性 / 控制 / 结果真值（先做，涉及"模型与 UI 结果是否真实"）

1. **24 类 raw24 进入 LIVE/UI 链，停止默认 23 类合并**
   - 依赖：冻结 BF16 模型（json `28272abc…`/raw `c1781aec…`，已就位）、`rml24_raw.hpp::raw24_predict`、`chain_common.hpp::fill_result_rml24`。
   - 最小改动：`run_live_rx_phase` 换 `raw24_predict` + `fill_result_rml24`；移除该链上的 `merge_logits_23`；
     UI server 增加 `parse_result_frame_rml24`（`rml24-chain-v1`）分派并切 `classes_24()`/`class_count=24`；
     一键脚本指向 `model_rml24_bf16`。
   - 验收：live-rx 输出 24 类帧、UI 显示 24 类标签且 AM-SSB WC/SC 独立；Host 帧级回放 + 板端 live-rx 各跑一次对照。
2. **合并 nosignal 树的 B1/B2 缺陷修复**
   - 依赖：nosignal 树 `signal_presence.hpp`（2ec93753）、`ui_state_map.hpp`（1ab851e0）。
   - 最小改动：将 SIGNAL_LOST/INVALID 时限恢复 + NO_SIGNAL 隐藏残留分类两处并入基线对应文件。
   - 验收：复用 nosignal 树 Host 测试（test_signal_presence / test_ui_nosignal_state）在合并后基线跑通。

### P1 — 基本操作 / 显示 / 维护

3. **live-rx 真正消费工作模式**
   - 依赖：`work_mode_engine.hpp`、控制通道 state 事件。
   - 最小改动：live-rx 去掉硬编码 `level_mode="FIXED"`，接入 WorkModeEngine；AUTO_LOCK 生效类锁/电平。
   - 验收：Host 状态机测试 + 板端模式切换观察到采集/分类行为变化。
4. **运行时频率/增益/带宽控制**
   - 依赖：libiio 属性写接口、控制通道命令框架。
   - 最小改动：控制通道加 SET_FREQ/SET_GAIN/SET_BW，producer apply 时写设备并读回 fail-closed。
   - 验收：Host 命令协议测试 + 板端写读回一致。
5. **BAND_SCAN LO 扫描 + 瀑布图并入板端 UI**
   - 依赖：`band_scan.hpp` sequencer（纯逻辑已测）、waterfall 树 `waterfall_history.hpp`（host-only API）。
   - 最小改动：sequencer compose 进 producer；waterfall API 按 integrator 文档接入 `board_ui_live_rml23`。
   - 验收：Host 逻辑/渲染测试 + 板端显示扫描进度与瀑布。

### P2 — 打磨

6. 实时频谱曲线渲染（复用 waterfall FFT 的 256-bin 谱，替换 PARAMETERS 标量卡片）。
7. 星座实时源（UnixSocket/SharedMemory）或板端 framebuffer 星座渲染。
8. 扫频列表 UI 页（依赖 P1-5 先产出 scan 结果帧字段）。
9. 中文/7 英寸屏适配（需求确认后；当前无中文字形、固定 1280x720）。
10. 板端 FPS 实测（Host 无法替代，需上板）。

---

## 关键证据与发散事实

- 主入口默认 `--phase offline` + expA 模型 + `contract_23()`（`board_gate9_full_chain_rml23.cpp` 3656-3688）。
- UI server 硬编码 23 类并拒绝非 `rml23-chain-v2` 帧（`board_ui_live_rml23.cpp` 388-390/532-534/560；
  `result_frame_rml23_parse.hpp`）。
- 三棵工作树发散（SHA256 前缀）：`ui_state_map.hpp` tx_rms `3e8259ec` / waterfall `81674aea` / nosignal `1ab851e0`；
  `signal_presence.hpp` tx_rms=waterfall `44ac2e49`（旧）/ nosignal `2ec93753`（已修）；
  `board_ui_live_rml23.cpp` tx_rms=waterfall `b192254c` / nosignal `c94c42ab`。
  → nosignal 与 waterfall 均未并入最新基线 tx_rms_sweep1。

完整逐项状态见 `results/feature_status.tsv`；证据见 `results/evidence_index.tsv`；
运行链见 `results/runtime_paths.md`；控制链见 `results/control_paths.md`；缺口见 `results/missing_or_unverified.tsv`。

---

## 边界声明

本审查**未完成任何 UI/集成工作**，也未对任何"待确认/未上板验证"项补造通过结果。
最高状态仅表示离线审查完成。
