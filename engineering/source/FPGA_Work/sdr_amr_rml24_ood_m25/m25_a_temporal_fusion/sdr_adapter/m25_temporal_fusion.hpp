#pragma once
// m25_temporal_fusion.hpp -- M25-A general multi-frame temporal fusion of raw
// NPU logits (12/24-dim). Model-independent. Default-OFF: byte-identical
// single-frame output. Fail-closed on illegal/NaN/Inf input.
//
// namespace m25; never touches the board / Gate 9/10 / RTL / bitstream.

#include <cstddef>
#include <cstdint>

#include "m25_temporal_fusion_config.hpp"
#include "m25_temporal_fusion_state.hpp"

namespace m25 {

struct TemporalFusionInput {
  const float* logits = nullptr;        // raw (pre-softmax) logits
  std::size_t count = 0;                // 12 or 24 only
  std::uint64_t frame_id = 0;
  std::uint64_t timestamp_ns = 0;
  const char* model_sha256 = nullptr;   // 64-hex, or nullptr
  int mode_id = 0;
  std::uint64_t tuning_generation = 0;
  std::uint64_t lo_freq_hz = 0;         // LO/freq change is an independent reset trigger
  bool no_signal = false;               // NO_SIGNAL -> clears fusion history
  bool unknown = false;                 // OOD-U already rejected -> never overridden by vote
  bool error = false;                   // NPU error -> bypass immediately
  float ood_score = 0.0f;               // independent OOD score (EWMA+hysteresis)
  float ood_threshold = 0.0f;           // <=0 disables OOD reject
};

struct TemporalFusionResult {
  bool valid = false;
  int raw_class_index = -1;             // single-frame argmax
  int fused_class_index = -1;           // fused top-1
  float raw_margin = 0.0f;              // top1 - top2 (logit domain)
  float fused_margin = 0.0f;
  float stability = 0.0f;               // recent-window top-1 agreement fraction
  unsigned accumulated_frames = 0;
  bool class_changed = false;
  const char* change_reason = "";       // static string literal
  bool reset_occurred = false;
  const char* reset_reason = "";        // static string literal
};

class TemporalFusion {
 public:
  void configure(const FusionConfig& cfg);
  TemporalFusionResult process(const TemporalFusionInput& in);
  void reset(const char* reason);       // explicit reset; "stop" latches a STOP

  bool enabled() const { return cfg_.enabled; }
  const FusionStats& stats() const { return stats_; }
  int fused_class() const { return st_.fused; }

 private:
  void size_buffers(std::size_t count);
  void clear_history();
  bool detect_reset(const TemporalFusionInput& in, ResetReason* out);
  void note_reset(ResetReason r, TemporalFusionResult* out);
  void store_prev_identity(const TemporalFusionInput& in);
  void push_frame(const float* logits, int top1, float margin);
  void update_ema(const float* logits);
  int compute_fused(int raw_class, float raw_margin, bool* changed, const char** reason);
  float current_stability() const;

  FusionConfig cfg_;
  FusionState st_;
  FusionStats stats_;
};

}  // namespace m25
