# 无信号判定契约（任务 39e5 UI v3 · M1 + M14 生产者接线）

> 状态：**生产者接线完成（READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST 的软件里程碑）**，阈值待板端标定。
> 实现：`sdr_adapter/signal_presence.hpp`（纯逻辑、header-only、iCraft-free，与
> `npu_rearm_state.hpp`/`delay_gate.hpp` 同风格）；主机测试 `host_tests/test_signal_presence.cpp`
> + `host_tests/test_producer_12class.cpp`（M14：非 `SIGNAL_PRESENT` 绝不发布 + 信号恢复重新发布）。

## 1. 目的

在 RF 链路噪声/无信号/信号边缘时，给出**确定的状态**，避免把噪声帧喂进 NPU 当成有效分类、
避免在临界点状态抖动。判定结果与 NPU 推理、UI 显示解耦：只有 `SIGNAL_PRESENT` 才发布新分类。

## 2. 状态机

| 状态 | 含义 | 进入/离开 |
|------|------|-----------|
| `NO_SIGNAL` | 初始 / 无信号 | 初始态；`ACQUIRING` 确认前丢帧回落至此 |
| `ACQUIRING` | 检测到信号证据，尚未确认 | 出现 hint 且 `confirm<N` |
| `SIGNAL_PRESENT` | 已确认存在信号 | 连续 `N` 帧 hint |
| `SIGNAL_LOST` | 曾存在，现连续丢失 | `SIGNAL_PRESENT` 后连续 `M` 帧非 hint |
| `INVALID` | 采集/输入故障 | NaN/Inf、capture_error、clip_ratio 超限 |

转移规则（见 `SignalPresence::update`）：

```
fault(nan_inf || capture_error || clip_ratio > max_clip) ──► INVALID（计数器清零）
hint = signal_hint(in, present_now)    // present_now = 当前是否 SIGNAL_PRESENT（迟滞阈值）
hint==true:  丢失计数清零；confirm++；confirm>=N → SIGNAL_PRESENT，否则 ACQUIRING
hint==false: confirm 清零；
             SIGNAL_PRESENT: lost++；lost>=M → SIGNAL_LOST（否则保持，容忍瞬断）
             ACQUIRING:     回 NO_SIGNAL（未确认前单帧丢失即回落）
             其余:           保持
```

## 3. 每帧输入（`PresenceInput`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `power_dbfs` | double | 帧功率 dBFS |
| `noise_floor_dbfs` | double | 估计噪声底 dBFS（未知用 NaN） |
| `snr_est_db` | double | 估计 SNR dB（未知用 NaN） |
| `psd_peak_prominence_db` | double | PSD 峰值突出度 dB（未知用 NaN） |
| `clip_ratio` | double | 削顶样本占比 |
| `occupied_bins` | int | 信号占用 FFT 频点数 |
| `nan_inf` | bool | 原始测量含 NaN/Inf |
| `capture_error` | bool | 溢出/丢帧/相位不连续/短帧 |

## 4. 判定证据（`signal_hint`，联合）

1. **能量（主）**：`power_dbfs >= threshold`；threshold 取**迟滞**值——
   进入用 `enter_power_dbfs`，已 present 用 `exit_power_dbfs`（两者成间隙，防临界抖动）。
2. **SNR（佐证，可选）**：`min_snr_db>0` 时，若 SNR 证据可得（`snr_est_db` 或
   `power_dbfs - noise_floor_dbfs`）且 `< min_snr_db` 则否。SNR 证据**增益不变**
   （功率与噪声底同 shift），是跨 RX 增益一致性的关键。
3. **PSD 峰值突出度（佐证，可选）**：`min_peak_prominence_db>0` 且突出度可得且不足则否。
4. **占用频点（佐证，可选）**：`min_occupied_bins>0` 且占用不足则否。
5. 值为 0 的佐证项=禁用。`nan_inf`/`capture_error` 直接判无 hint（由 §2 fault 先行 INVALID）。

## 5. 配置（`PresenceConfig`，默认值仅起点，须板端标定）

| 项 | 默认 | 说明 |
|----|------|------|
| `enter_power_dbfs` | -55.0 | 进入阈值（绝对 dBFS） |
| `exit_power_dbfs` | -62.0 | 退出阈值（已 present 时生效） |
| `min_snr_db` | 0（禁用） | SNR 佐证下限 |
| `min_peak_prominence_db` | 0（禁用） | 突出度佐证下限 |
| `min_occupied_bins` | 0（禁用） | 占用频点佐证下限 |
| `max_clip_ratio` | 0.05 | 削顶占比上限（超限 INVALID） |
| `confirm_frames` (N) | 3 | 连续 hint 帧数才确认 present |
| `lost_frames` (M) | 5 | 连续丢失帧数才判 lost |

**标定红线**：`enter/exit/min_snr` 等**不是硬编码法**，必须由离线噪声统计与板端空载采集确定；
上板前在 `docs/BOARD_UI_V3_TEST.md` 记录标定过程与最终值。默认值仅用于主机单测与首次上板占位。

## 6. 与 NPU / UI 的衔接（语义契约，M14 已接线）

- **仅 `SIGNAL_PRESENT` 发布新分类**：`NO_SIGNAL/ACQUIRING/SIGNAL_LOST/INVALID` 时
  不得把当前帧 logits 当作有效结果发布，也不得计入历史/准确率统计。M14 由
  `producer_12class.hpp` 每帧 `presence_.update(...)` 判定，非 present 时
  `ProducerDecision.publish=false` / `published_class=-1`，Gate 9 据此不产有效分类。
- **无信号显示**：UI 显示 `NO SIGNAL`（`ACQUIRING`/`SIGNAL_LOST` 分别显示对应提示），
  保留上次 top1/分布但置 `STALE`（灰化 + age），**不显示假的 LIVE**。
- **恢复**：信号重现走 `ACQUIRING → SIGNAL_PRESENT` 后才恢复分类，避免把噪声当作恢复瞬间的类别。
- `INVALID`（clip/NaN/Inf/capture_error）与 `Status::Error` 对齐，UI 显示 ERROR 而非误分类。

## 7. 主机测试（`test_signal_presence.cpp`，14 组）

噪声恒 NoSignal / 噪声底抬升仍 NoSignal / N 帧确认 present / 短突发不确认回落 / 退出迟滞
（-58 dBFS 保持 present）/ M 帧丢失判 lost / lost 后重捕获 / 跳频多信号仍 present /
clip 超限 INVALID / NaN-Inf 与 capture_error INVALID / INVALID 恢复 / SNR 检测增益不变
（同一信号两档增益同状态）/ 突出度与占用频点佐证 / 状态名与 reset。

## 8. 红线

- 不做逐帧 RMS 归一化（训练契约 §3 已禁）；`power_dbfs`/`noise_floor` 等测量基于原始计数域，
  不改变 NPU 输入幅度路径。
- 不把无信号帧当 12 类之一（禁止 label-shift / skip-frame / result-offset 式假 PASS）。
- 阈值可配置、可审计，默认值不冒充板端标定值。
