# UI 方案：多目标列表 + 扫描坐标视图（任务 2/3 的 UI 部分）

实现（离线模型）：`src/ui_model.py`（`SpectrumFrame`、`UiMultiSignalState`）。
本方案是集成蓝图，不直接改 A/B 树。

## 设计原则

1. 冻结九字段目标记录是**数据来源**；UI 额外需要的频谱坐标、调谐时间、后端
   信息放在独立 `SpectrumFrame` 日志里，不污染冻结记录。
2. 单 SDR 顺序扫描 → 所有时间戳是“该频点被顺序调谐到的时间”，UI 不宣称
   “同时识别”。
3. 星座只显示**当前选中目标的有效 IQ**；切换目标立即清空，目标消失自动清空。

## 结果列表（新增）

- 每个 `TargetRecord` 一行：`target_id, center_hz, bw_hz, status, top3,
  confidence, last_seen, backend`。
- 排序：按 `last_seen` 降序（最近重访在上）。
- 选择：点击/方向键选中 → 触发星座重载 + 频谱标记。
- 状态着色：`new/tracking` 正常，`missing` 灰，`expired` 移除前短暂置灰。

## 频谱 / 瀑布（扫描坐标）

- `SpectrumFrame` 以扫描坐标表示：`center_hz(bin) = lo_hz + (bin - 512) * 2500`，
  即 bin 0..1023 映射到以 LO 为中心的 ±1.28 MHz。
- 每帧带 `tune_time_seconds`：调谐时刻标记，用于把“峰出现在哪个调谐点”写进
  列表项的 `last_seen`（顺序扫描语义）。
- 瀑布每行 = 一个 dwell 的 PSD；换 LO 时插入调谐标记行/分隔。
- 目标峰在频谱上以 `center_hz` 为锚标记，不把 256-bin 相对谱（旧 UI）误当
  扫描坐标用。

## 星座（单目标）

- 只渲染 `selected` 目标的 512 点恢复 IQ。
- `select(target_id)`：替换（非累积）星座缓冲；未知名目标 fail-closed 抛错。
- `refresh()`：若选中目标已不在当前记录集（老化/消失），置 `selected=None`
  并清空星座。
- 绝不把不同目标的 IQ 混画。

## 后端显示

- `backend` 字段按合同 §1 三值（software/fpga/auto）显示；真实后端由扫描日志
  提供，UI 只透传不推断。

## 已覆盖测试

`tests/test_ui_model.py`：扫描坐标换算、换目标清空星座、目标消失清空选择、
选中未知目标 fail-closed。
