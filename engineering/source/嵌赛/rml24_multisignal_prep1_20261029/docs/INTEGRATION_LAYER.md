# 多目标真实入口集成层定位（任务 1，如实报告）

纯只读核对 A 线 `rml24_mainchain_finalize1_20261028`、B 线
`rml24_fpga_smartscan_prep2_20261028` 与旧 scan 树 `rml24_scan_final_prep1_20261027`。
本线不改 A/B 树就地；以下为集成补丁的落点结论。

## 真实入口

- 生产扫描循环：`candidate/overlay/rml24_final/board_runtime/standalone_receiver.py`（A 线生产入口，单例）。
- 逐 dwell 检测原语：`scan_runtime.detect_public_training`（**每 capture 只返回一个** `PublicDetection{start, coarse_cfo_hz, score}`，lag-1024 周期相关 + despread-FFT 估 CFO）。
- 扫描配置/步长：`scan_runtime.ScanConfig`（`lo_frequencies()`；步长上限 `int(0.9*fs)=2304000`，无 2500 整数倍限制）。
- 单锁定策略：`scan_lock_policy.LockHysteresis`（单一 `locked` 频率）。
- 控制：`standalone_control.Controller`（单一 mode/fixed/scan 范围/presence；命令 START/STOP/SET_MODE/SET_FIXED_HZ/SET_SCAN_RANGE_HZ；Command.cancelled 即取消）。
- 恢复/分类：`receiver_core.recover_frame` + `candidate_two_dc.recover` + `rml24_dualmode_receiver_centered_v2.infer`（NPU，冻结）。
- UI 事件：`ui_event.build_ui_event`/`build_board_ui_result`（单结果事件 schema：单 prediction、单 256-bin 相对谱、单 512 点星座）。
- UI 渲染：`board_package/ui_state_map.hpp`（`ResultFrame`→`UiState`，单 top1/conf/dist/spectrum/IQ）、`board_ui_live_rml24_final.cpp`、`ui_sw/ui_render.{hpp,cpp}`（五页 UI）。

## 结论：多信号接在哪一层

**接在扫描循环控制层（`standalone_receiver.py`），不在检测/恢复/分类层。**
检测原语 `detect_public_training`、恢复 `recover_frame`、NPU `infer`、UI 事件 schema
全部**不动**。唯一改动是循环控制：把“全扫只留最强 `best` + 单一 `locked`”替换为
**`TargetTracker` 驱动的多目标调度**。

具体三个插入点（本线补丁给主线程合入，不就地改）：
1. BAND_SCAN 扫描段：把 `best=(score, hz)` 单变量改为把每个 `score>=0.10` 的
   dwell 命中 `tracker.observe(center_hz=actual+coarse_cfo_hz, power_db=..., bw_hz=...)`。
2. 锁定段：把单一 `locked` + `LockHysteresis` 改为 tracker 的按目标重访调度
   （每周期对每个 tracking 目标按其 `center_hz` 重调 + 重检测；miss 计入老化）。
3. 结果/UI 段：把单结果 `build_board_ui_result` 改为遍历 `tracker.active_targets()`
   发目标列表事件 + 选中目标星座（本线 `ui_model` 语义）。

## 诚实边界（必须写明，不臆造）

- `detect_public_training` **每 capture 只返回一个命中**，因此**单个 dwell 内只能
  得到一个候选**。多目标列表只能来自**跨 LO dwell 的顺序扫描**（不同频点先后
  命中），与合同 §7“列表时间戳 = 顺序调谐时间，非同时识别”一致。
- **单 dwell 内同时多信号**需要逐 dwell 多峰检测：这在 B 线 FPGA PSD 路径的
  CPU 侧（`noise_floor/adaptive_threshold/bin_merge/band_stitch/target_tracking`，
  见 `smart_scan_contract.json::cpu_v1`）才成立。本线 `src/psd.py` 是该层离线参考，
  **在 FPGA 辅助链验收前不接入当前软件循环**。
- `receiver_core`/`radio_tuning`/`scan_runtime`/`candidate_two_dc`/
  `rml24_dualmode_receiver_centered_v2` 的运行时副本在**板端 legacy root**
  （`--legacy-root`），A 线树内只有 `scan_lock_policy.py`/`ui_event.py`/
  `standalone_control.py`；旧 scan 树有可读的权威副本（本线只读引用）。
- `pilot_recovery`（含 `public.train/tail`）**不在任何可读树中**，在板端 legacy root；
  但 `candidate_two_dc.py` 内含 train/tail 的逐字配方（seed 9011），本线据此离线
  复现并核验占用带宽（见 `docs/OCCUPIED_BW_VERIFICATION.md`）。

## 补丁形态

- `src/scan_adapter.py`：`MultiSignalScanLoop` 适配器（候选队列/分类预算/公平重访/
  全频段周期重扫/过期清理/apply_range 换带清理迁移，复用 `src/tracker.py`/
  `src/psd.py`/`src/scoring.py`，不 import 任何 A/B 树模块）。
- `integration/receiver_entry.py`：**可注入真实入口**（C3 调度 + C5 可注入循环），
  把上述调度器接到 radio/infer/controller/transport。板端与离线测试执行同一份循环。
- `integration/patch_standalone_receiver.diff`：以统一 diff 标明
  `standalone_receiver.py` 的手写循环整体替换为 `ReceiverEntry` 接线（主线程审阅后
  合入；见 `integration/standalone_receiver.multisignal.py` 完整参考文件）。
- `cpp/target_list_rml24_parse.hpp` / `cpp/target_list_state.hpp`：板端 C++
  `rml24_targets` 事件解析 + 列表页状态（host g++ 编译通过，未 aarch64 编译）。
- `reference/`：权威副本的只读快照（`scan_runtime.py`、`ui_event.py`、
  `receiver_core.py`、`candidate_two_dc.py`），供离线回放测试自包含运行。

> 注：本文件早期版本把补丁写成「三处插入点 + TargetTracker 单线程调度」。收口实施
> 阶段（C3/C5）已改为 `ReceiverEntry` 单点入口，旧三插入点描述由本节的
> `receiver_entry.py` 取代；扫描/恢复/分类/UI 事件层仍不动的结论不变。
