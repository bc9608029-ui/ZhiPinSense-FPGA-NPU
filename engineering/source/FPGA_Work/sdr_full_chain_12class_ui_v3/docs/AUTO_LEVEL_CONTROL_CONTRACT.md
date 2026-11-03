# 自动幅度管理契约（任务 39e5 UI v3 · M2）

> 状态：**生产者接线完成（READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST 的软件里程碑）**。
> 实现：`sdr_adapter/auto_level_control.hpp`（纯逻辑、header-only、iCraft-free，决策层；
> 设备层负责真正施加 RF 增益/数字标量）。主机测试 `host_tests/test_auto_level_control.cpp`（63 断言）。
> 模型输入合规性审计见 `docs/AUTO_LEVEL_MODEL_INPUT_AUDIT.md`。

## 1. 目的

在 RF 链路增益/幅度变化时，自动把信号幅度维持在模型训练域（RMS≈1.0）与 ADC 健康区间内，
**且不违反「禁止逐帧 RMS 归一化」**。提供 `FIXED`（冻结）与 `AUTO`（自适应）两种模式。

## 2. 两层结构

| 层 | 作用域 | 输出 | 时间尺度 |
|----|--------|------|----------|
| **RF/ADC 层** | 模拟前端（ADC 之前） | 每步增益增量 `delta(dB)`，由设备层经 Pluto `hardwaregain` 施加 | 慢（逐帧判，但增量有界） |
| **模型输入层** | 数字域（ADC 之后、receiver_scale 之上） | 数字标量 `model_scale`（乘在冻结 receiver_scale 之上） | 慢（每 `frames_per_update` 帧） |

## 3. 每帧输入（`FrameLevelStats`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `adc_rms_dbfs` | double | ADC 计数域 RMS（dBFS） |
| `clip_ratio` | double | ADC 削顶样本占比 |
| `model_rms` | double | 模型域 RMS（**已乘 receiver_scale，未乘本模块标量**） |
| `valid` | bool | false=NaN/Inf/采集错误（冻结，不自适应） |

## 4. 配置（`LevelConfig`）

| 项 | 默认 | 说明 |
|----|------|------|
| `mode` | `Fixed` | `Fixed`=冻结；`Auto`=自适应 |
| `fixed_model_scale` | 1.0 | FIXED 模式精确标量（默认恒等 → 冻结路径不变） |
| `target_model_rms` | 1.0 | AUTO 模型域目标 RMS（=训练 RMS） |
| `model_scale_min/max` | 0.25 / 4.0 | AUTO 数字标量边界（防追静音/过驱动） |
| `model_step_max` | 0.05 | AUTO 每步相对变化上限（5%） |
| `frames_per_update` | 8 | AUTO 模型层更新节奏（慢） |
| `rf_target_dbfs` | -12.0 | AUTO ADC RMS 目标 |
| `rf_hysteresis_db` | 3.0 | RF 死区（避免在阈值附近抖动） |
| `rf_gain_min/max_db` | 0 / 50 | RF 增益安全边界 |
| `rf_gain_step_db` | 3.0 | RF 每步最大增益变化 |
| `max_clip_ratio` | 0.01 | 削顶超限立即降增益 |

## 5. 行为（`update`）

- **FIXED 模式**：`model_scale` 恒等于 `fixed_model_scale`（默认 1.0，即冻结 receiver_scale 路径
  一字不改）；RF 层**从不**自适应（返回 0），削顶/幅度异常只由用户/上层处理。
- **AUTO 模式**：
  - **模型输入层**：每 `frames_per_update` 帧用 EMA（α=0.1）平滑 `model_rms`，目标标量
    `desired = target_model_rms / ema`；相对变化被 `[1−step_max, 1+step_max]` 截断，最终标量
    截断到 `[min, max]`。→ **慢、有界、平滑，绝非逐帧归一化**。
  - **RF/ADC 层**：削顶超限 → 立即 `-step`；`adc_rms_dbfs` 高于/低于 `target±hysteresis` →
    `-step`/`+step`；死区内 0；最终增益截断到 `[min,max]`，只报告实际施加的增量（不越界）。
- **冻结条件**：`valid==false`（NaN/Inf/采集错误）或 `adapt==false`（外部门控，如
  `signal_presence` 非 `SIGNAL_PRESENT` 时冻结，不追噪声）→ 两层都**不**自适应。

## 6. 与既有冻结契约的关系

- `receiver_scale=21.8556709`（板端标定）**保持冻结**：`model_scale` 是乘在其上的第二标量，
  FIXED 模式 `model_scale=1.0` 时与现网**逐字节等价**。
- `x_model = count × (1/2048) × receiver_scale × model_scale`（12-bit 域 ÷2048，见
  `rx_iq_format_contract.md` §3）。
- **不改变 NPU 输入布局/类别序/量化**，只缩放 fp32 幅度，且缩放是慢变化全局标量。

## 7. 主机测试（`test_auto_level_control.cpp`，9 组）

FIXED 冻结不变 / RF 方向与死区 / RF 增益截断（越界时 delta 只报实际施加部分）/
削顶立即降增益 / 模型层慢且有步长上限 / 模型层上行有界 / invalid 冻结 / adapt=false 冻结 / reset。

## 8. 红线

- AUTO 模式是**慢、有界、平滑的全局标量**，逐帧测量但**绝不逐帧归一化**；违反即回退 FIXED。
- 削顶是唯一允许的「快」反应（安全动作），且只降 RF 增益、不动数字标量。
- FIXED 模式必须与冻结 receiver_scale 路径**逐字节等价**（默认 `fixed_model_scale=1.0`）。
- 阈值/边界为**可配置默认值**，须板端标定，不冒充标定值。
