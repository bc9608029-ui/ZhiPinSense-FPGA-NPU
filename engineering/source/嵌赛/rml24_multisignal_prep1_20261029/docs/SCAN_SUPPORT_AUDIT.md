# 任务 1 结论：现有扫频器与 UI 是否支持多信号

**结论（如实）：现有扫频器与五页 UI 均不支持多信号。** 现有实现是单信号
顺序扫描：全扫后只保留**最强**一个命中，锁定单一频率，UI 每次只显示一个
识别结果。任何“多目标”能力都尚未存在，不能默认已有。

## 证据（主链树 `rml24_mainchain_finalize1_20261028`，只读核对）

| 能力 | 现状 | 证据文件 |
|------|------|----------|
| 多候选队列 | 无。全扫只保留单一 `best`（最强 public score） | `candidate/runtime/…/scan_runtime.py::scan_and_select`（`best: ScanHit`，逐点覆盖，最终返回一个） |
| 逐频锁定 | 单频率锁定 + 有界 miss 后重扫，非逐频多目标 | `board_runtime/standalone_receiver.py`（`locked` 单变量；`LockHysteresis` 只服务一个锁定点） |
| 逐频分类 | 只对锁定/选中的单一原始帧做一次恢复+分类 | `standalone_receiver.py` 主循环：`raw` 单帧 → `recover_frame` → `infer` |
| 结果列表 | 无列表。UI 状态是单一 `top1/conf/dist` | `overlay/board_package/ui_state_map.hpp::map_to_state`（单一 `st.top1`） |
| 去重 | 无（只有一个候选，无去重概念） | 同上 |
| 老化 | 无目标级老化；只有锁定的 miss 预算 | `runtime/scan_lock_policy.py`（`LockHysteresis`，作用于锁定频率而非目标记录） |
| 频谱/瀑布 | 单一结果帧的 256-bin 相对谱，非扫描坐标多目标 | `runtime/ui_event.py::_display_payload`（`spectrum_db_rel_x4`，相对最强 bin） |
| 星座 | 单一结果帧的 512 点 IQ | `ui_event.py`（`iq_i16_interleaved`） |

## 单 SDR 顺序扫描的时间语义

现有 `standalone_receiver.py` 的 `BAND_SCAN` 是**顺序**调谐：每个 LO 点一次
capture，全扫后才能确定最强命中。因此：

- 任何“结果列表”里的时间戳是**该频点被顺序调谐到的时间**，不是多个信号被
  **同时**识别的时刻。
- 不同目标的 `last_seen` 天然相差一个或多个 dwell/重访周期，不能解读为
  “同时锁定”。

这一点已冻结进合同（§7 末句）并在本线所有时间语义里保持一致。

## FPGA 分工（B 线冻结）为多目标留下的接口

FPGA 只做窗/FFT/模平方/双缓冲，输出 1024-bin fftshift PSD；`noise_floor`、
`adaptive_threshold`、`bin_merge`、`band_stitch`、`target_tracking`、`ui`
全部留在 CPU（见 FPGA `contract/smart_scan_contract.json` 的 `cpu_v1`）。因此
多目标的候选提取、去重、老化都是 CPU 侧逻辑，本线的 `src/psd.py` +
`src/tracker.py` 正是这一层的离线参考实现，`backend` 字段可记录
`software`/`fpga`/`auto` 而不改变模型 IQ 或冻结 NPU。
