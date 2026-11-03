# 模型输入幅度合规性审计（任务 39e5 UI v3 · M2）

> 目的：证明自动幅度管理（`auto_level_control.hpp`）**没有**破坏模型输入契约，且 AUTO 模式
> 满足「禁止逐帧 RMS 归一化」的硬约束。逐条对照冻结契约给出结论。

## 1. 审计对象与冻结契约

| 冻结契约 | 关键条款 |
|----------|----------|
| `contracts/sampling_and_iq_contract.md` | `per_record_rms_normalization = forbidden`；128 kHz / 帧 1024 复数 / 无重叠 |
| `contracts/rx_iq_format_contract.md` §3 | `x_model = count × (1/2048) × receiver_scale`；÷2048 非 ÷32768 |
| `sdr_adapter/receiver_scale.hpp` | `receiver_scale` 全局固定、冻结、不逐帧归一化 |
| `model_12class/MODEL_DEPLOYMENT_CONTRACT.md` | 输入 `iq[1,2,1024]` fp32，训练域 RMS=1.0 |

## 2. 审计结论（逐条）

| # | 条款 | 结论 |
|---|------|------|
| 1 | **禁止逐帧 RMS 归一化** | **满足**。`model_scale` 是单一慢变化全局标量：每 `frames_per_update`（默认 8）帧才更新一次，EMA 平滑，步长 ≤5%，界 [0.25,4.0]。**不是** `x = x / rms(frame)` 这种逐帧操作。 |
| 2 | **训练域 RMS=1.0** | **满足**。AUTO 目标 `target_model_rms=1.0`；FIXED 用冻结 receiver_scale，等价训练标定路径。 |
| 3 | **receiver_scale 冻结** | **满足**。`model_scale` 是**乘在 receiver_scale 之上**的第二标量；FIXED 默认 `model_scale=1.0` 时现网路径逐字节等价，receiver_scale 本身不改。 |
| 4 | **÷2048 非 ÷32768** | **满足**。本模块不碰 12-bit 计数域换算，只作用在 receiver_scale 之后的 fp32 域。 |
| 5 | **输入布局/类别序/量化不变** | **满足**。本模块只缩放 fp32 幅度，不重排 I/Q、不改类别、不重量化。 |
| 6 | **无效帧安全** | **满足**。`valid==false`（NaN/Inf/采集错误）冻结不自适应；削顶只降 RF 增益、不动数字标量。 |

## 3. 关键区别：慢 AGC vs 逐帧归一化

| 维度 | 逐帧归一化（禁止） | 本模块 AUTO（允许） |
|------|--------------------|---------------------|
| 作用频率 | 每帧 | 每 N 帧（默认 8） |
| 变化量 | 无界、瞬时到目标 | 步长 ≤5%、EMA 平滑、有界 |
| 状态 | 无记忆（纯帧内） | 有记忆（EMA + 累计标量） |
| 语义 | 抹掉每帧幅度信息 | 追踪长时幅度趋势（保留帧内/帧间幅度调制特征） |

**为什么慢 AGC 不破坏模型**：模型依赖的是帧内相对幅度结构与跨帧幅度调制（AM-DSB 的包络、
OOK 的开关、衰落轨迹等）。慢 AGC 在 >8 帧尺度上才调整一个全局常数，帧内结构不变、相邻帧相对
幅度不变；逐帧归一化则会抹掉这些特征。

## 4. 上板前待标定（非硬编码）

| 项 | 需板端确认 |
|----|-----------|
| `rf_target_dbfs` / `rf_hysteresis_db` | 用实际 Pluto 增益-ADC RMS 曲线标定，避开噪声底与削顶 |
| `model_scale_min/max` | 结合板端信号动态范围（含 RF 自测同轴回环）确认不追静音/不过驱动 |
| `target_model_rms=1.0` | 与训练 `_normalize_rms` 幅度一致（M0 审计已确认 RMS=1.0） |

## 5. 结论

`auto_level_control.hpp` 的 AUTO 模式是**慢、有界、平滑的全局幅度管理**，与「禁止逐帧 RMS
归一化」兼容；FIXED 模式与冻结 receiver_scale 路径逐字节等价。**未发现破坏模型输入契约的项**。
上板前仅需标定 RF 层阈值（§4），模型输入层默认值与训练契约一致。
