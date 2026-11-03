#pragma once
// m25_temporal_fusion_config.hpp -- M25-A general multi-frame temporal fusion
// configuration. Offline, model-independent (12/24-dim raw logits). Default-OFF:
// an unconfigured instance is a byte-identical single-frame passthrough.
//
// namespace m25; never touches the board / Gate 9/10 / RTL / bitstream.

#include <cstddef>
#include <cstdint>

namespace m25 {

// Fusion algorithms, offline-comparable and runtime-selectable.
enum class FusionAlgorithm {
  MajorityVote = 0,
  LogitsMean = 1,
  LogitsEMA = 2,
  EMA_KFrameConfirm = 3,     // default
  EMA_MarginHysteresis = 4,
};

struct FusionConfig {
  bool enabled = false;                              // default OFF -> single-frame passthrough
  FusionAlgorithm algorithm = FusionAlgorithm::EMA_KFrameConfirm;
  float alpha = 0.3f;                                // EMA mixing coefficient, (0,1]
  unsigned confirm_frames = 2;                       // K-frame confirm (2..3)
  float margin_hysteresis = 0.1f;                    // logit-domain switch band
  unsigned max_window = 32;                          // bounded history (frames)
  unsigned max_latency_frames = 4;                   // latency cap (confirm_frames must be <= this)
  float ood_ema_alpha = 0.3f;                        // independent OOD EWMA (never mixed into class logits)
  float ood_hysteresis = 0.1f;
  std::uint64_t max_frame_gap = 4;                   // frame_id jump beyond this -> reset
  std::uint64_t max_timestamp_gap_ns = 200000000ULL; // 200 ms -> reset
};

// Validate a config; returns false and writes a short message into err (>=128 bytes).
bool config_valid(const FusionConfig& c, char* err);
const char* algorithm_name(FusionAlgorithm a);

}  // namespace m25
