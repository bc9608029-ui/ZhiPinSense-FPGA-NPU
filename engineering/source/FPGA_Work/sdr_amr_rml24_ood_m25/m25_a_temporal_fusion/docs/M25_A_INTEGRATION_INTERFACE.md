# M25-A 通用多帧时序融合 — 集成接口

## 一句话

在 NPU 逐帧 raw logits 之后、argmax/分类展示之前，插入一个**默认关闭**的时序融合层，
把瞬时误判与真实换模分开；默认关闭时输出与单帧字节一致。

## 立即可接（离线已验证）

- **纯 CPU、模型无关**：仅消费 12/24 维 `const float*` raw logits，不做任何新推理、不新增
  NPU 算子、不改数据通路、不改标签顺序、不改预处理。
- **默认关闭 = 无侵入**：不调用 `configure`（或 `enabled=false`）时，行为与现有单帧 argmax
  完全一致，可先行合入作为旁路。
- **独立 OOD 通道**：`ood_score` / `ood_threshold` 走独立 EWMA+滞回，不污染类 logits，可
  与现有 OOD-U 判定并行观察。

## 接口

```cpp
#include "sdr_adapter/m25_temporal_fusion.hpp"

m25::FusionConfig cfg;                 // 默认 enabled=false
cfg.enabled = true;                    // 显式开启
cfg.algorithm = m25::FusionAlgorithm::EMA_KFrameConfirm;
m25::TemporalFusion tf;
tf.configure(cfg);

m25::TemporalFusionInput in;
in.logits = npu_logits;                // 12 或 24 维 raw（未 softmax）
in.count  = 24;
in.frame_id = seq;                     // 单调帧号
in.timestamp_ns = mono_ns;             // 单调时间戳
in.model_sha256 = sha;                 // 64-hex，模型换模即触发复位
in.mode_id = mode;
in.tuning_generation = tuning;
in.lo_freq_hz = lo_hz;
in.no_signal = ...;                    // NO_SIGNAL -> 清融合历史
in.unknown  = ...;                     // OOD-U 已判 UNKNOWN -> 不被投票覆盖
in.error    = ...;                     // NPU ERROR -> 立即直通
in.ood_score = ...; in.ood_threshold = ...;

m25::TemporalFusionResult r = tf.process(in);
// r.fused_class_index: 融合后 top-1（默认关闭时 == raw_class_index）
// r.fused_margin / r.stability / r.class_changed / r.change_reason
// r.reset_occurred / r.reset_reason
```

## 复位触发（任一变化即清融合历史，重新开始）

`model_sha256`（含 nullptr↔非空）、`count` 12↔24、`mode_id`、`lo_freq_hz`、
`tuning_generation`、`frame_id` 回退/重复/跳号（> `max_frame_gap`）、`timestamp_ns`
回退/超间隔（> `max_timestamp_gap_ns`）、NO_SIGNAL、STOP、显式 `reset("stop")`。

## 等 24 类正式 baseline 冻结后再做

- 用真实 24 类 logits 重新标定 `alpha` / `margin_hysteresis` / `confirm_frames`。
- 用真实 NPU 数据验证 12↔24 换模的 `model_sha` 复位语义。
- 测量真实换模平均/最大延迟，确认 `max_latency_frames` 预算。
- 与 OOD-U 拒识的 UNKNOWN 语义对齐（是否共用同一"不被覆盖"通道）。

## 红线（禁止）

- 不接 Gate 9/10 正式主链、不启 Vivado、不碰板、不写 Flash。
- 不修改 12 类正式模型 / 24 类 pilot / M22/M23/M24 交付物 / RTL/XDC/位流 / 数据通路 /
  标签顺序 / 预处理。
- 真实 NPU 对齐前，不得书写 `TEMPORAL_FUSION_HARDWARE_PASS` / `OOD_PASS` /
  `PERFORMANCE_PASS` / `PROJECT_COMPLETE` 及 FINAL_* 族。
