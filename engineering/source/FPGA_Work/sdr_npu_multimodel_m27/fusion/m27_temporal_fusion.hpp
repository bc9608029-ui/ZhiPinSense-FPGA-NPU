// M27 generic temporal fusion (spec §十): class-count-agnostic (12 or 24), model
// agnostic, offline CPU framework.  Seven comparable algorithms, strict
// SIGNAL_PRESENT / NO_SIGNAL / UNKNOWN distinction, START/STOP, stability confirm,
// bounded window, timeout clear, model-switch clear, no cross-model_sha fusion, and a
// bounded maximum response on a sudden class change.  header-only, namespace m27.
//
// All scores are computed in the raw-logit domain (except ProbMean, which averages
// caller-supplied probabilities); no Softmax is introduced.  The window is a bounded
// fixed ring (kFusionMaxWindow x kMaxLogits), and process() performs no heap
// allocation in steady state.
#ifndef M27_TEMPORAL_FUSION_HPP
#define M27_TEMPORAL_FUSION_HPP

#include <cstdint>
#include <cstring>
#include <string>
#include "m27_contract.hpp"

namespace m27 {

constexpr int kFusionMaxWindow = 32;     // bounded window (never grows unbounded)
constexpr int kFusedUnknown  = -1;       // OOD-U rejected this frame
constexpr int kFusedNoSignal = -2;       // NO_SIGNAL passthrough

enum class FusionAlgorithm : int {
  LogitsMean = 0,     // sliding mean of raw logits
  ProbMean   = 1,     // sliding mean of probabilities
  EMA        = 2,     // per-class exponential moving average
  MajorityVote = 3,   // per-frame top-1 majority vote
  MarginWeighted = 4, // frame weight = raw top-1 margin
  SnrWeighted = 5,    // frame weight = mapped SNR
  Hysteresis = 6      // switch only after a new class persists
};

struct FusionConfig {
  int n = 12;                      // class count (12 or 24; fail-closed on mismatch)
  FusionAlgorithm algo = FusionAlgorithm::LogitsMean;
  int max_window = 8;              // bounded window length (1..kFusionMaxWindow)
  float alpha = 0.5f;              // EMA coefficient
  int max_response_frames = 3;     // sudden-change max response (frames)
  std::uint64_t timeout_ns = 0;    // clear on gap > this (0 = disabled)
  int hyst_confirm_frames = 2;     // hysteresis: frames to confirm a switch
  float hyst_margin = 0.5f;        // hysteresis: required logit advantage to switch
};

struct FusionResult {
  bool valid = false;              // fail-closed: dimension mismatch => false
  int fused_class = kFusedNoSignal; // >=0 class; -1 UNKNOWN; -2 NO_SIGNAL
  float fused_margin = 0.0f;       // top1 - top2 of the fused score
  float stability = 0.0f;          // fraction of window agreeing with fused top-1
  unsigned accumulated_frames = 0;
  bool class_changed = false;
  bool reset_occurred = false;
  const char* reset_reason = nullptr;
};

class TemporalFusion {
 public:
  TemporalFusion() : cfg_() {}

  void configure(const FusionConfig& c) {
    cfg_ = c;
    if (cfg_.max_window < 1) cfg_.max_window = 1;
    if (cfg_.max_window > kFusionMaxWindow) cfg_.max_window = kFusionMaxWindow;
    reset_state("configure");
  }

  int n() const { return cfg_.n; }

  void reset(const char* reason) { reset_state(reason); }

  FusionResult process(const FusionInput& in) {
    FusionResult r;
    r.reset_reason = nullptr;

    // ---- dimension mismatch -> fail-closed (spec §十) ----
    if (in.n != cfg_.n) {
      reset_state("dimension_mismatch");
      r.valid = false; r.reset_occurred = true; r.reset_reason = "dimension_mismatch";
      return r;
    }

    // ---- model SHA: fusion never crosses model_sha (spec §十) ----
    if (in.model_sha != nullptr) {
      std::string s(in.model_sha);
      if (!sha_.empty() && sha_ != s) {
        reset_state("model_switch");
        r.reset_occurred = true; r.reset_reason = "model_switch";
      }
      sha_ = s;
    }

    // ---- strict presence distinction ----
    if (in.presence == PresenceState::NO_SIGNAL) {
      reset_state("no_signal");
      r.valid = true; r.fused_class = kFusedNoSignal;
      r.accumulated_frames = 0; r.reset_occurred = true; r.reset_reason = "no_signal";
      prev_fused_ = kFusedNoSignal;
      return r;
    }
    if (in.presence == PresenceState::UNKNOWN) {
      // OOD-U already rejected: fusion must not override (spec §十).  Clear the
      // window so the unreliable frame cannot pollute later fusion.
      reset_state("unknown_passthrough");
      r.valid = true; r.fused_class = kFusedUnknown;
      r.accumulated_frames = 0; r.reset_occurred = true;
      r.reset_reason = "unknown_passthrough";
      prev_fused_ = kFusedUnknown;
      return r;
    }

    // ---- timeout / timestamp-regression clear ----
    if (count_ > 0) {
      if (in.timestamp_ns < last_ts_) {
        reset_state("timestamp_regress");
        r.reset_occurred = true; r.reset_reason = "timestamp_regress";
      } else if (cfg_.timeout_ns > 0 && in.timestamp_ns - last_ts_ > cfg_.timeout_ns) {
        reset_state("timeout");
        r.reset_occurred = true; r.reset_reason = "timeout";
      }
    }
    last_ts_ = in.timestamp_ns;

    // ---- append this frame to the bounded ring ----
    append(in);

    int raw = argmax(in.raw_logits, cfg_.n);

    // ---- sudden-change max response (spec §十) ----
    if (raw == run_class_) run_count_++;
    else { run_class_ = raw; run_count_ = 1; }
    if (run_count_ >= cfg_.max_response_frames && prev_fused_ >= 0 &&
        raw != prev_fused_) {
      reset_state("sudden_change");
      r.reset_occurred = true; r.reset_reason = "sudden_change";
      append(in);                          // re-seed window with the new class
      run_class_ = raw; run_count_ = cfg_.max_response_frames;
    }

    // ---- fuse ----
    int fused = -1;
    float margin = 0.0f;
    float stability = 0.0f;
    fuse(fused, margin, stability);

    r.valid = true;
    r.fused_class = fused;
    r.fused_margin = margin;
    r.stability = stability;
    r.accumulated_frames = static_cast<unsigned>(count_);
    r.class_changed = (fused != prev_fused_);
    prev_fused_ = fused;
    return r;
  }

 private:
  // ---- ring storage ----
  float win_[kFusionMaxWindow][kMaxLogits];
  float pwin_[kFusionMaxWindow][kMaxLogits];
  float wsnr_[kFusionMaxWindow];
  float wsp_[kFusionMaxWindow];
  int head_ = 0;       // index of the oldest frame
  int count_ = 0;      // valid frames (0..max_window)

  float ema_[kMaxLogits];
  bool ema_init_ = false;

  int hyst_class_ = -1;   // hysteresis current class
  int hyst_count_ = 0;    // consecutive confirm frames for a candidate

  std::string sha_;
  std::uint64_t last_ts_ = 0;
  int run_class_ = -1;
  int run_count_ = 0;
  int prev_fused_ = -3;

  FusionConfig cfg_;

  static int argmax(const float* v, int n) {
    int best = 0;
    for (int i = 1; i < n; ++i) if (v[i] > v[best]) best = i;
    return best;
  }

  // top-1 and top-2 indices (ties break toward lower index)
  static void top2(const float* v, int n, int& i1, int& i2) {
    i1 = 0; i2 = -1;
    for (int i = 1; i < n; ++i) {
      if (v[i] > v[i1]) { i2 = i1; i1 = i; }
      else if (i2 < 0 || v[i] > v[i2]) { if (i != i1) i2 = i; }
    }
    if (i2 < 0) i2 = i1;
  }

  float* row(int i) { return win_[(head_ + i) % kFusionMaxWindow]; }
  const float* row(int i) const { return win_[(head_ + i) % kFusionMaxWindow]; }
  const float* prow(int i) const { return pwin_[(head_ + i) % kFusionMaxWindow]; }

  void reset_state(const char* /*reason*/) {
    head_ = 0; count_ = 0;
    std::memset(win_, 0, sizeof(win_));
    std::memset(pwin_, 0, sizeof(pwin_));
    std::memset(wsnr_, 0, sizeof(wsnr_));
    std::memset(wsp_, 0, sizeof(wsp_));
    ema_init_ = false;
    std::memset(ema_, 0, sizeof(ema_));
    hyst_class_ = -1; hyst_count_ = 0;
    run_class_ = -1; run_count_ = 0;
    sha_.clear();
  }

  void append(const FusionInput& in) {
    int idx = (head_ + count_) % kFusionMaxWindow;
    std::memcpy(win_[idx], in.raw_logits,
                static_cast<std::size_t>(cfg_.n) * sizeof(float));
    if (in.probabilities != nullptr) {
      std::memcpy(pwin_[idx], in.probabilities,
                  static_cast<std::size_t>(cfg_.n) * sizeof(float));
    } else {
      std::memset(pwin_[idx], 0, static_cast<std::size_t>(cfg_.n) * sizeof(float));
    }
    wsnr_[idx] = in.snr;
    wsp_[idx] = in.signal_power;
    if (count_ < cfg_.max_window) count_++;
    else head_ = (head_ + 1) % kFusionMaxWindow;
  }

  void fuse(int& fused, float& margin, float& stability) {
    if (count_ == 0) { fused = -1; margin = 0; stability = 0; return; }

    float score[kMaxLogits];
    std::memset(score, 0, sizeof(score));

    switch (cfg_.algo) {
      case FusionAlgorithm::LogitsMean: {
        for (int i = 0; i < count_; ++i) {
          const float* r = row(i);
          for (int c = 0; c < cfg_.n; ++c) score[c] += r[c];
        }
        break;
      }
      case FusionAlgorithm::ProbMean: {
        for (int i = 0; i < count_; ++i) {
          const float* p = prow(i);
          for (int c = 0; c < cfg_.n; ++c) score[c] += p[c];
        }
        break;
      }
      case FusionAlgorithm::EMA: {
        // EMA is a running state, updated once per frame (not re-derived).
        break;   // handled after the switch
      }
      case FusionAlgorithm::MajorityVote: {
        for (int i = 0; i < count_; ++i) {
          int c = argmax(row(i), cfg_.n);
          score[c] += 1.0f;
        }
        break;
      }
      case FusionAlgorithm::MarginWeighted: {
        for (int i = 0; i < count_; ++i) {
          const float* r = row(i);
          int a, b; top2(r, cfg_.n, a, b);
          float w = r[a] - r[b];
          if (w < 0.0f) w = 0.0f;
          for (int c = 0; c < cfg_.n; ++c) score[c] += w * r[c];
        }
        break;
      }
      case FusionAlgorithm::SnrWeighted: {
        for (int i = 0; i < count_; ++i) {
          const float* r = row(i);
          float w = snr_weight(wsnr_[i]);
          for (int c = 0; c < cfg_.n; ++c) score[c] += w * r[c];
        }
        break;
      }
      case FusionAlgorithm::Hysteresis: {
        // State machine over the *raw* top-1 sequence, not an aggregation.
        int raw = argmax(row(count_ - 1), cfg_.n);
        if (hyst_class_ < 0) {
          hyst_class_ = raw; hyst_count_ = 0;
        }
        if (raw == hyst_class_) {
          hyst_count_ = 0;
        } else {
          hyst_count_++;
          const float* r = row(count_ - 1);
          if (hyst_count_ >= cfg_.hyst_confirm_frames &&
              r[raw] - r[hyst_class_] > cfg_.hyst_margin) {
            hyst_class_ = raw; hyst_count_ = 0;
          }
        }
        score[hyst_class_] = 1.0f;
        break;
      }
      default:
        break;
    }

    if (cfg_.algo == FusionAlgorithm::EMA) {
      if (!ema_init_) {
        std::memcpy(ema_, row(count_ - 1),
                    static_cast<std::size_t>(cfg_.n) * sizeof(float));
        ema_init_ = true;
      } else {
        const float* r = row(count_ - 1);
        for (int c = 0; c < cfg_.n; ++c)
          ema_[c] = cfg_.alpha * r[c] + (1.0f - cfg_.alpha) * ema_[c];
      }
      std::memcpy(score, ema_, static_cast<std::size_t>(cfg_.n) * sizeof(float));
    }

    int a, b; top2(score, cfg_.n, a, b);
    fused = a;
    margin = score[a] - score[b];

    // stability = fraction of frames whose raw top-1 == fused
    int agree = 0;
    for (int i = 0; i < count_; ++i)
      if (argmax(row(i), cfg_.n) == fused) agree++;
    stability = static_cast<float>(agree) / static_cast<float>(count_);
  }

  // Placeholder SNR -> positive weight (linear-ish map, clamped).  The real mapping
  // must be fixed from validation/calibration data (spec §九/§十); this is not a
  // board-tuned value.
  static float snr_weight(float snr) {
    float w = 1.0f + snr / 30.0f;
    if (w < 0.01f) w = 0.01f;
    if (w > 2.0f) w = 2.0f;
    return w;
  }
};

}  // namespace m27

#endif  // M27_TEMPORAL_FUSION_HPP
