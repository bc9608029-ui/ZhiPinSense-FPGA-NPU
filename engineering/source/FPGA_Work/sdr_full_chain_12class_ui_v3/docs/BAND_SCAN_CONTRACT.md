# BAND SCAN 工作模式契约（任务 39e5 UI v3 · M10 + M14 生产者接线）

> 状态：**生产者接线完成（READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST 的软件里程碑）**。
> 纯逻辑：`board_package/band_scan.hpp`（扫频时序 + 逐点聚合，iCraft-free/libiio-free）。
> 依赖：`work_mode_engine.hpp`（M7/M8 引擎）+ `mode_control.hpp`（M6 模式态）。
> **真实执行**：M14 由 `board_package/producer_12class.hpp` + `board_gate9_full_chain_12class.cpp`
> 真正调用 Pluto `set_rx_lo` 按 start/stop/step/dwell 扫频、每步清类锁、逐帧回报 LO/进度。
> 主机测试 `host_tests/test_band_scan.cpp`（纯逻辑）+ `host_tests/test_producer_12class.cpp`
> （真实 LO 扫频接线：`set_rx_lo` 逐点调用 + 回绕 + `lo_tune_count`/`sweep_advances`）。

## 1. 目的

在 M8 AUTO LOCK 基础上补齐 BAND SCAN 工作模式的**LO 扫频时序**：把一段频带切成若干
驻留点（LO step），每点驻留 `dwell_frames` 帧用 AUTO LOCK 策略判类，累计每点最优检测
（类 + 置信度），扫完自动回绕持续扫。BAND SCAN 只决定**扫频时序与逐点聚合**，幅度管理
与类锁仍复用 M8 引擎。

## 2. 组件

| 组件 | 职责 |
|------|------|
| `BandScanConfig` | 扫频参数：`start_hz` / `stop_hz` / `step_hz` / `dwell_frames`（均有默认值） |
| `BandScanSequencer` | 确定性的 LO 扫频状态机（调度 + 驻留计数 + 回绕） |
| `BandScanAccumulator` | 逐点最优检测聚合（best class + confidence） |
| `WorkModeEngine::reset_lock()` | 每个 LO 点开始时清类锁（新频点=全新信号环境） |

## 3. 扫频时序（`BandScanSequencer`）

- **步数**：`total_steps = floor((stop_hz - start_hz) / step_hz) + 1`（含 start 与最后一个
  `<= stop` 的频点，start==stop 时为 1）。
- **频点**：`frequency_for(step) = min(start_hz + step*step_hz, stop_hz)`，step ∈ [0, total_steps)。
- **驻留**：`on_frame()` 每帧 +1，恰好在第 `dwell_frames` 帧返回 `true`（本步最后一帧）。
- **回绕**：`advance_step()` 走到 `(step_index+1) % total_steps`，驻留计数清零并重算频点；
  扫过 stop 自动回绕到 start，**持续扫不停止**（生产者经 M6 STOP / 退出外部停止）。
- **校验**：`stop_hz < start_hz`、`step_hz == 0`、`dwell_frames <= 0` 均 `throw std::invalid_argument`。

## 4. 逐点聚合（`BandScanAccumulator`）

- 容量 = `total_steps`；每点预填 `step_index` + `frequency_hz`。
- `record(step_index, cls, confidence)`：帧计数 +1；`cls >= 0` 且 `confidence` 高于当前最优时
  替换最优（首条有效类即成为最优）。
- 无效类（`cls < 0`）只计数不参与最优；越界 `throw std::out_of_range`。
- `reset()` 清空所有 bin 的帧计数/最优（供新一轮扫描）。

## 5. 板端接线（M14 生产者，已真实执行）

`producer_12class.hpp` 的 `Producer12` 在 BAND SCAN 模式下按下列时序**真正驱动设备**
（`DeviceControl::set_rx_lo`），不再只是纯逻辑时序：

```
before_capture(): 若 sweep 已步进 -> dev.set_rx_lo(sweep.current_frequency_hz())  // 每步驻留开始前调 LO
for each captured frame {
    ProducerDecision d = prod.on_frame(base, flags, classify);
    // 内部：sweep.on_frame() 驻留计数；engine.update() AUTO LOCK 策略；
    //       scan_results.record(step, class, conf) 逐点最优；
    //       驻留完成 -> engine.reset_lock()（新频点清类锁）-> sweep.advance_step()
    //       并置 band_scan_tuned_=false，下一次 before_capture() 重新调 LO。
}
```

- 每帧 `ProducerDecision` 回报 `scan_lo_hz / scan_step_index / scan_total_steps /
  scan_frames_in_step / scan_dwell_frames`，写入 v3 ResultFrame 扩展供 UI MODE 页展示。
- `sweep_advances()` / `lo_tune_count()` 由 Gate 9 PASS 门禁校验（BAND SCAN 启动时
  `scan_ok = sweep_advances()>0`），扫频不暂停、不写 Flash。

## 6. 主机测试（`test_band_scan.cpp`，5 组 + `test_producer_12class.cpp`）

1. 配置校验（stop<start / step==0 / dwell<=0 抛异常）；
2. 扫频表（2400..2500 @10MHz = 11 步、start 起 stop 止顺序、回绕、reset）；
3. 非整除频点（100..250 @100 = 2 步，末点 <= stop）；
4. 驻留完成（恰在 dwell_frames 帧完成一次、advance_step 清计数）；
5. 聚合语义（best class/confidence 取最大、无效类不覆盖、逐 bin 独立、越界抛、reset）；
6. 组合：`WorkModeEngine` 锁类后 `reset_lock()` 清锁（新 LO 点不携带旧类）。

## 7. 红线

- BAND SCAN 只改**扫频时序与发布/聚合**，绝不改类别契约/12 类顺序/位流/Flash。
- 未实机验证只标 `READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST`，不写任何 *_PASS。
- 我禁碰板/禁写 Flash；上板由用户本人执行。
