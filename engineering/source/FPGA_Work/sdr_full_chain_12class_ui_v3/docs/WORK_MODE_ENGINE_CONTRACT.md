# 工作模式引擎契约（任务 39e5 UI v3 · M7 FIXED + M8 AUTO LOCK + M14 生产者接线）

> 状态：**生产者接线完成（READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST 的软件里程碑）**。
> 纯逻辑：`board_package/work_mode_engine.hpp`（iCraft-free，主机可测）。
> 依赖：`mode_control.hpp`（M6 控制态）+ `sdr_adapter/auto_level_control.hpp`（M2 自动幅度）。
> 主机测试 `host_tests/test_work_mode_engine.cpp`（M7 FIXED + M8 AUTO LOCK，ASan/UBSan 零失败）
> + `host_tests/test_producer_12class.cpp`（M14：引擎 model_scale/RF 增益真实作用于模型输入/设备）。

## 1. 目的

把 M6 反向控制通道的**工作模式状态**（`mode_ctl::ModeKind`）绑定到 M2 的**自动幅度管理**
与**分类发布策略**。板端生产者（Gate 9 / M9 的 gate10）持有一个 `WorkModeEngine`，控制通道
`set_mode()` 切模式，每帧 `update()` 得到 `WorkModeDecision`：如何管幅度 + 是否/发布哪个类。

## 2. 模式语义

| 模式 | 里程碑 | level_mode | 数字标量 | RF 增益 | 分类发布 |
|------|--------|-----------|----------|---------|----------|
| FIXED | M7 | `Fixed` | 恒 `fixed_model_scale`（默认 1.0 恒等，冻结路径不动） | 不自动管理（0.0） | 每个有效有信号帧发布**原始 argmax**，无类锁 |
| AUTO LOCK | M8 | `Auto` | 慢/有界自动（EMA+步长上限） | 自动（削顶降增益） | 仅当 top-1 稳定 `stability_window` 帧后才发布，并**保持** |
| BAND SCAN | M10 | `Auto` | 同上 | 同上 | 同上（M10 补 LO 扫描/驻留时序） |

- `level_mode_for(ModeKind)`：Fixed→`Fixed`；AutoLock/BandScan→`Auto`。
- 红线（沿用 M2）：AUTO 是**慢/有界/平滑**的全局标量，**不是**逐帧 RMS 归一化；无信号或
  `adapt=false` 时冻结，不追噪声；类锁只门控**发布**，绝不改写 NPU argmax/12 类契约。

## 3. `WorkModeDecision`（每帧输出）

| 字段 | 语义 |
|------|------|
| `level_mode` | 本帧应使用的幅度层模式 |
| `model_scale` | 乘在冻结 receiver_scale 之上的数字标量（FIXED=恒等 1.0） |
| `rf_gain_db` | 自动管理的 RF 增益偏移（FIXED=0.0） |
| `publish` | 是否发布本帧分类 |
| `published_class` | 发布时使用的类索引；`publish==false` 时 -1 |
| `class_locked` / `locked_class` | 是否已锁定 + 锁定的类（AUTO LOCK / BAND SCAN） |
| `reason` | 短日志标签（字符串字面量，零分配）：`FIXED`/`FIXED no_signal`/`AUTO locked`/`AUTO acquiring`/`AUTO no_signal` |

## 4. `ClassStabilityLock`（M8）

- 窗口 `window`（默认 5）：top-1 连续 `window` 帧相同才**锁定**（`locked()` true，返回该类）。
- **保持**：锁定后单帧跳到别类不丢锁，继续发布原锁定类（抑制闪烁）；新类也需连续
  `window` 帧才**重锁**（适应真实调制切换）。
- 无效类（<0）不破坏锁；`reset()` 清锁。

## 5. `WorkModeEngine`

- `set_mode()`：切模式时重建自动幅度层 + 清类锁（FIXED→标量重置为 fixed_model_scale）。
- `update(stats, signal_present, argmax_class, adapt)`：
  - FIXED：标量=fixed、RF=0，`publish = valid && signal_present`，发布原始 argmax。
  - AUTO LOCK / BAND SCAN：`level_.update(stats, signal_present && adapt)`；`lock_.feed(argmax)`；
    `publish = valid && signal_present && locked`，发布锁定类。
- 内层 `AutoLevelControl` 恒配置为 Auto（FIXED 由引擎自驱），AUTO 路径才调用它。

## 6. 主机测试（`test_work_mode_engine.cpp`，6 组）

1. `level_mode_for` 三模式映射；2. FIXED 恒等路径（默认 1.0/0.0、有效帧发布原始 argmax、
   无信号/无效不发布、热帧/削顶 40 帧仍不漂移、自定义 fixed scale=2.0 精确应用）；
3. `ClassStabilityLock`（窗口 3 锁定/单帧闪烁保持/新类重锁/无效类保持/reset）；
4. AUTO LOCK（level=Auto、acquiring 不发布、第 3 帧锁定发布、单帧闪烁抑制、新类重锁、
   无信号冻结不发布）；5. AUTO 慢自适应（model_rms=2.0 八帧后标量下降且步长有界≥0.95，
   干净 ADC 无 RF 增量）；6. set_mode 切换与 reset（锁清除、状态重置、FIXED 恢复原始发布）。

## 7. 板端接线（M14 生产者，已真实执行）

`producer_12class.hpp` 的 `Producer12::on_frame()` 在每帧：

- 用**当前** `engine_.model_scale()` 先缩放 base 张量再喂 NPU（AUTO 幅度真实作用于模型输入，
  非仅记数值）；`ProducerDecision.model_scale` = 本帧实际应用的标量；
- 再用 `engine_.rf_gain_db()` 计算 `desired = clamp(base_rf_gain_db + offset, min, max)`，
  变化时经 `DeviceControl::set_rx_gain` 真实写设备（有界、可记录）；
- `level_mode / publish / published_class / class_locked / reason` 全来自 `engine_.update(...)`；
- `work_mode / run_state` 随 `result_frame_v3_line` 下发，UI 由 `map_to_state` 显示，UI 不自改。

`set_mode()` 由反向控制通道（Gate 9 生产者唯一所有者）驱动：`SET_MODE` 成功即
`engine_.set_mode()`（切模式重建自动幅度层 + 清类锁）+ 重置扫频序列。

## 8. 红线

- 工作模式/类锁只影响**幅度管理**与**发布策略**，绝不改类别契约/12 类顺序/位流/Flash。
- 未实机验证只标 `READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST`，不写任何 *_PASS。
- 我禁碰板/禁写 Flash；上板由用户本人执行。
