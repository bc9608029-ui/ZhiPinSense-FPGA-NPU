# M23 P0 — 后续接入 M22 的接口说明（Integration Interface）

> 状态：`M23-P0-OFFLINE-MODULES-READY`。本文描述**将来**如何把 M23 P0 模块接入 M22（Gate 9/Gate 10）正式主链。**本轮不执行接入**；本文只写接口约定，供 M22 板测通过后参考。

## 1. 接入原则（红线）

- M23 主链集成**必须等 M22 板测通过**（阶段门禁），在此之前不得接线到 Gate 9/Gate 10。
- 接入时**不修改** M22 交付物、12 类模型、标签顺序、预处理、UI 主布局、RTL/XDC/位流。
- 接入后默认行为必须**与 M22 逐字节一致**：OOD-U 关闭、不逐帧串口刷日志。
- 本接口是纯 CPU 参考实现，不承担实时性承诺；是否上 NPU 是后续独立决策。

## 2. 模块依赖图（只新增，不改 M22）

```
IQ 帧 (每帧 1024 complex<float>)
   │
   ├─ sdr::SignalPresence  (复用, 不修改)  ──▶ PresenceState
   ├─ m23::estimate_params  (新, m23_params.hpp + m23_cfo.hpp)
   │      └─ sdr::DspMeasure (复用, 不修改) + m23::estimate_cfo (新)
   │           ──▶ M23Params{center_freq, power, rms, snr, occupied_bw, cfo}
   ├─ m23::M23OodSwitch    (新, 可关闭)     ──▶ OodSwitchResult{enabled,rejected,error,class_index,score}
   └─ m23::compose         (新, m23_verdict.hpp)
            ──▶ Verdict{NoSignal, SignalPresent, UnknownExperimental, Error}
```

- 复用 `sdr::DspMeasure` / `sdr::SignalPresence` / `sdr::MeasureScratch`（`sdr_adapter/dsp_measure.hpp`、`signal_presence.hpp`），**不改其源码**。
- 新模块全部 `sdr_adapter/m23_*.hpp`（header-only，iCraft/libiio 无关）+ `ood_u_*.{hpp,cpp}`（自 M20 逐字节拷贝，见交付报告）。

## 3. 四态裁决（`m23::compose`）

| 输入 | 输出 Verdict |
|---|---|
| `PresenceState::Invalid`（削波/捕获错误） | `Error` |
| `PresenceState::SignalPresent` 且 OOD-U **启用且拒识**（`rejected==true`） | `UnknownExperimental` |
| `PresenceState::SignalPresent` 且 OOD-U **启用且检测错误**（`error==true`） | `Error` |
| `PresenceState::SignalPresent` | `SignalPresent` |
| 其它（NoSignal / Acquiring / SignalLost） | `NoSignal` |

- 四态严格分离，`NO_SIGNAL` / `SIGNAL_PRESENT` / `UNKNOWN_EXPERIMENTAL` / `ERROR` 语义不混用（token 冻结于 `m23_contract.hpp`）。
- OOD-U **默认关闭**：`M23OodSwitch` 未 `enable()` 时 `enabled=false`，`compose` 走纯 `SignalPresent`/`NoSignal` 路径，**绝不产生 `UNKNOWN_EXPERIMENTAL`** —— 与 M22 一致。

## 4. OOD-U 可关闭接线（任务 C）

- `M23OodSwitch::enable(const OodThresholdManifest&)` 加载 M20 冻结阈值（fail-closed：SHA 不符/字段缺失抛异常，调用方决定拒收）。
- `M23OodSwitch::disable()` / `enabled()` 显式开关。
- `M23OodSwitch::classify(logits, dim)` 返回 `OodSwitchResult`：
  - 禁用路径：纯 argmax（`class_index` 为 top-1，`rejected=false`）。
  - 启用路径：调 `OodUDetector::classify_or_reject`，按 `logit_margin` 阈值判定拒识。
- **口径红线**：M20 near/far 拒识率约 6.03%/10.33%，为**实验性**功能。UI 上只显示 `UNKNOWN_EXPERIMENTAL`，**不得宣传为可靠功能**；阈值仍 `OOD_U_FROZEN_THRESHOLD_LOGIT_MARGIN = -0.15274411201477073`（参考只读值，真值以 M20 manifest 为准）。

## 5. 串口日志纪律（不逐帧刷日志）

- 板端生产者**禁止**在每帧打印参数/裁决（回放工具的单帧打印是主机调试辅助）。
- 允许的串口输出：启动就绪一行、异常/错误一行、显式统计间隔（`--stats-interval`）的汇总行。
- 状态变化（存在/失去/UNKNOWN）可用**跳变沿**打一行，稳定期间静默。

## 6. 接入后生产者最小接线（伪码，供参考）

```cpp
// 每帧：复用 M22 现有 IQ 缓冲，只追加读取，不改变 M22 帧流。
m23::M23ParamConfig cfg;
cfg.sample_rate_hz = 128000.0;
cfg.cfo_reference_hz = rx_center_hz;   // 接收机标称中心
cfg.cfo_reference_set = true;
cfg.cfo_order = order_for(mod_type);    // tone=1 / BPSK=2 / QPSK=4

sdr::SignalPresence presence;          // 复用，不动
sdr::MeasureScratch meas;              // 复用，不动
m23::CfoScratch cfo_scratch;
m23::M23ParamState param_state;
m23::M23OodSwitch ood;                 // 默认关闭；显式 enable(manifest) 才开

// 每帧：
auto p = m23::estimate_params(frame, 1024, cfg, meas, cfo_scratch);
auto st = presence.update(...);
auto r  = ood.enabled() ? ood.classify(logits, 24) : OodSwitchResult{};
auto v  = m23::compose(st, r.enabled, r.rejected, r.error);
param_state.refresh(frame_idx, p);
bool stale = param_state.stale(frame_idx);
// UI 显示 render_param(p.center_freq_hz, stale) 等；无效/stale 显示 "--"。
```

## 7. 不做的接线（本轮明确排除）

- 不接入 Gate 9/Gate 10 正式主链，不生成冒充可上板验收的全量包。
- 不修改 RTL/XDC/位流，不写 Flash，不上板。
- 不改变 12 类模型/标签顺序/预处理/UI 主布局。
- 不提前打 `M23_P0_PASS` / `HARDWARE_PASS`。
