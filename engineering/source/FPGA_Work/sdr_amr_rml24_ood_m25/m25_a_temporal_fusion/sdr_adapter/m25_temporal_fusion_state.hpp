#pragma once
// m25_temporal_fusion_state.hpp -- M25-A internal mutable state + stats.
// All buffers are preallocated once (on first frame / reset); process() only
// indexes into them (no steady-state heap allocation, no unbounded growth).

#include <cstddef>
#include <cstdint>
#include <vector>

namespace m25 {

// Reset triggers, each counted independently in FusionStats.
enum class ResetReason {
  ModelShaChange = 0,
  DimChange,
  ModeChange,
  LoFreqChange,
  TuningGenerationChange,
  Start,
  Stop,
  NoSignal,
  FrameIdRegression,
  FrameIdDuplicate,
  FrameIdGap,
  TimestampRegression,
  TimestampGap,
  NonFinite,
  ExplicitReset,
  Count,  // sentinel
};
const char* reset_reason_name(ResetReason r);

struct FusionStats {
  std::uint64_t total_frames = 0;
  std::uint64_t reset_count = 0;
  std::uint64_t reset_by_reason[static_cast<int>(ResetReason::Count)] = {0};
  float ood_ema = 0.0f;
  bool ood_rejected = false;
  char last_explicit_reason[64] = {0};
};

// Mutable state held by TemporalFusion. Fixed-size, preallocated on first frame.
struct FusionState {
  bool started = false;       // a normal frame has initialized prev-identity
  bool stopped = false;       // STOP latch (set by reset("stop"))

  std::size_t count = 0;      // 12 or 24

  // previous-frame identity for reset detection
  bool have_prev = false;
  std::uint64_t prev_frame_id = 0;
  std::uint64_t prev_timestamp_ns = 0;
  int prev_mode_id = 0;
  std::uint64_t prev_tuning_generation = 0;
  std::uint64_t prev_lo_freq_hz = 0;
  char prev_model_sha[65] = {0};

  // class-fusion buffers
  bool ema_initialized = false;
  std::vector<float> ema_logits;      // count
  std::vector<float> window_logits;   // max_window * count, ring
  std::vector<int> window_top1;       // max_window
  std::vector<float> window_margin;   // max_window
  std::vector<float> mean_scratch;    // count (reused by LogitsMean; no per-frame alloc)
  unsigned window_head = 0;
  unsigned window_len = 0;
  unsigned confirm_counter = 0;
  int fused = -1;

  // independent OOD EWMA (never mixed into class logits)
  bool ood_initialized = false;
  float ood_ema = 0.0f;
};

}  // namespace m25
