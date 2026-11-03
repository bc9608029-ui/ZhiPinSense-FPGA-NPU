# M27 通用多帧融合契约（Temporal Fusion Contract）

任务 id="39e5" · M27 §十 · 离线 CPU 框架，namespace `m27`，header-only。

模块：`fusion/m27_temporal_fusion.hpp`（`m27::TemporalFusion`）。

---

## 1. 目的与定位

在逐帧 NPU raw logits 之上做**与类别数无关**的多帧融合，压低单帧误判、把真实换模与瞬时噪声分开。支持 12 类与 24 类两套合同。**默认不改变单帧语义**：未 `configure`（或直接单帧窗口）时输出即单帧 argmax。

本模块是**离线框架**，不接 Gate 9/10 主链、不调用 NPU、不做板端性能声明。

## 2. 输入契约（`m27::FusionInput`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `frame_id` | u64 | 帧号 |
| `timestamp_ns` | u64 | 时间戳 |
| `presence` | `PresenceState` | `NO_SIGNAL` / `SIGNAL_PRESENT` / `UNKNOWN` 严格区分 |
| `n` | int | 类别数（仅 12 或 24） |
| `raw_logits` | `const float*` | 长度 `n` 的原始 logits |
| `probabilities` | `const float*` | 长度 `n`（可空；ProbMean 需要） |
| `ood_score` | float | 独立 OOD 分数 |
| `snr` | float | 信噪比（dB） |
| `signal_power` | float | 信号功率 |
| `model_sha` | `const char*` | 64-hex 或 nullptr |

## 3. 输出契约（`m27::FusionResult`）

| 字段 | 说明 |
|---|---|
| `valid` | 维度不匹配时 false（fail-closed） |
| `fused_class` | `>=0` 类别索引；`-1`=UNKNOWN 直通；`-2`=NO_SIGNAL 直通 |
| `fused_margin` | 融合分数的 top1−top2 |
| `stability` | 窗口内 raw top-1 与融合结果一致的比例 |
| `accumulated_frames` | 当前窗口帧数 |
| `class_changed` | 融合 top-1 相对上一帧是否改变 |
| `reset_occurred` / `reset_reason` | 本帧是否触发复位及原因 |

## 4. 七种算法（`FusionAlgorithm`）

`LogitsMean`（logits 滑动均值）、`ProbMean`（概率均值）、`EMA`（逐类指数滑动平均，`alpha`）、`MajorityVote`（逐帧 top-1 多数票）、`MarginWeighted`（帧权重 = raw margin）、`SnrWeighted`（帧权重 = SNR 映射）、`Hysteresis`（迟滞状态机：新类持续 `hyst_confirm_frames` 帧且 logit 优势 > `hyst_margin` 才切换）。

全部在**原始 logits 域**计算（ProbMean 除外），不引入 Softmax。

## 5. 硬性规则

1. **维度不匹配 fail-closed**：`in.n != cfg.n` → `valid=false`，清空状态。
2. **NO_SIGNAL**：清空融合历史、`accumulated_frames=0`、直通输出 `-2`。
3. **UNKNOWN**（OOD-U 已拒识）：**不被融合覆盖**，直通输出 `-1` 并清历史，避免污染后续帧。
4. **不跨 model_sha 融合**：`model_sha` 变化 → 清空状态（`reset_reason="model_switch"`）。
5. **START/STOP**：首帧/复位后首帧 = START；NO_SIGNAL = STOP。
6. **有界窗口**：`max_window`（默认 8，上限 `kFusionMaxWindow=32`），环形缓冲，稳态零堆分配。
7. **超时清空**：`timeout_ns > 0` 且帧间隔超过它 → 清空（`reset_reason="timeout"`）；时间戳回退 → 清空（`timestamp_regress`）。
8. **突发换类最大响应**：连续 `max_response_frames` 帧 raw top-1 落在另一类 → 立即翻转（`reset_reason="sudden_change"`），保证响应有界。
9. **稳定性确认**：`stability` 输出窗口一致率，供上层路由判断。

## 6. 阈值来源（红线）

`max_response_frames`、`hyst_margin`、`hyst_confirm_frames`、SNR 权重映射**只能由 validation/calibration 数据确定**，本框架给出的是占位默认值，**不得视为板端调优值**。SNR 权重是占位的线性映射（`1 + snr/30` 夹在 `[0.01, 2.0]`），正式映射待 calibration 冻结。

## 7. 状态红线

本模块最高状态 `M27-NPU-MULTIMODEL-OFFLINE-FRAMEWORK-READY`；不得写 `TEMPORAL_FUSION_HARDWARE_PASS / 24CLASS_PASS / OOD_PASS / PERFORMANCE_PASS / PROJECT_COMPLETE`。

## 8. 与 M25-A 的关系

M25-A（`sdr_amr_rml24_ood_m25`）是独立交付的 5 算法融合模块；M27 §十 要求更完整的输入契约（含 `snr`/`signal_power`/`probabilities`/`model_sha`）与 7 算法。两者不互相依赖、不互相修改，均为离线框架。
