# 控制链（反向：UI/脚本 → 控制通道 → producer 状态机）

审查口径：反向控制 = UI/外部命令经 AF_UNIX 控制 socket 修改 producer 运行状态。
当前版本只接"模式/启停"两级，设备级参数控制缺失。

## 1. 控制通道载体

- 控制 socket：`/run/sdr_amr_control_rml23.sock`（`common_rml23.sh`）。
- 队列：`CommandQueue`(32) / `AckQueue`(32)；命令 ACK 两段：ACCEPTED → APPLIED。
- request/apply 状态机（producer 侧 apply_pending）。

## 2. 已接命令（仅这些）

`board_package/mode_control.hpp`（注释明示"M7/M8/M10 才消费模式具体行为"）：

| 命令 | 作用 | 状态 |
|---|---|---|
| SET_MODE FIXED | 固定模式 | 接（UI 按钮 + 通道） |
| SET_MODE AUTO_LOCK | 自动电平+类锁 | 状态接；live-rx 未消费（硬编码 FIXED） |
| SET_MODE BAND_SCAN | 扫频 | 状态接；无 LO 扫描（M10 才到） |
| START | 开始 | 接 |
| STOP | 停止（保心跳） | 接 |
| STATUS | 查询 | 接 |

- UI 侧：`touch_mode_control.hpp` 5 个 MODE 页按钮，ACCEPTED/APPLIED/ERR/STATUS 处理。
- 脚本侧：`scripts/mode_ctl.sh`（薄封装 board_mode_ctl）。

## 3. 缺失的命令（设备级）

- 无 SET_FREQ / SET_GAIN / SET_BW（频率/增益/带宽运行时设置）。
- 参数仅能启动时通过 CLI：`--rx-lo`/`--rx-bw`/`--rx-gain`/`--rec-scale`/`--nco-offset`。
- live-rx `apply_pending` 只更新 mode/run/presence 状态，**无设备写入、无读回 fail-closed**。
- UI 无参数编辑页（PARAMETERS 页当前只显示测量标量，非可编辑参数）。

## 4. 状态事件（producer → UI）

- producer 在模式/运行态变化时发 `{"type":"state", ...}`；UI `apply_state_event` 更新
  work_mode/running/presence，不伪造分类。
- 心跳 errata：STOPPED 期间 state 事件保证 UI 显示 STOPPED/NO SIGNAL 而非 STALE。

## 5. 控制链已知缺口（与运行链一致）

- live-rx `level_mode = "FIXED"` 硬编码（`board_gate9_full_chain_rml23.cpp` 1800）→
  AUTO_LOCK/BAND_SCAN 控制到达 UI 与状态机，但不改变采集/分类行为。
- BAND_SCAN 无 LO 扫描（`work_mode_engine.hpp`："the LO sweep / scan sequencer arrives in M10"）。
