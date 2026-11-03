// m25_temporal_fusion.cpp -- M25-A implementation. Offline, model-independent.
// All five fusion algorithms + the reset-condition table live here (not inline).

#include "m25_temporal_fusion.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace m25 {

namespace {

const char* kInvalidDim = "invalid_dim";
const char* kNullLogits = "null_logits";
const char* kNonFinite = "non_finite";
const char* kDisabled = "disabled";
const char* kErrorBypass = "error_bypass";
const char* kNoSignal = "no_signal";
const char* kUnknownPassthrough = "unknown_passthrough";

// argmax + top1-top2 margin (strict > keeps the lower index on ties).
// Returns false if any element is non-finite.
bool argmax_top2(const float* x, std::size_t n, int* top1, float* margin) {
  if (x == nullptr || n == 0) return false;
  int i1 = -1;
  float m1 = -INFINITY, m2 = -INFINITY;
  for (std::size_t i = 0; i < n; ++i) {
    float v = x[i];
    if (!std::isfinite(v)) return false;
    if (v > m1) {
      m2 = m1;
      m1 = v;
      i1 = static_cast<int>(i);
    } else if (v > m2) {
      m2 = v;
    }
  }
  *top1 = i1;
  *margin = (n >= 2) ? (m1 - m2) : m1;
  return true;
}

}  // namespace

const char* algorithm_name(FusionAlgorithm a) {
  switch (a) {
    case FusionAlgorithm::MajorityVote: return "majority_vote";
    case FusionAlgorithm::LogitsMean: return "logits_mean";
    case FusionAlgorithm::LogitsEMA: return "logits_ema";
    case FusionAlgorithm::EMA_KFrameConfirm: return "ema_kframe_confirm";
    case FusionAlgorithm::EMA_MarginHysteresis: return "ema_margin_hysteresis";
  }
  return "unknown";
}

const char* reset_reason_name(ResetReason r) {
  switch (r) {
    case ResetReason::ModelShaChange: return "model_sha";
    case ResetReason::DimChange: return "dim";
    case ResetReason::ModeChange: return "mode";
    case ResetReason::LoFreqChange: return "lo_freq";
    case ResetReason::TuningGenerationChange: return "tuning_generation";
    case ResetReason::Start: return "start";
    case ResetReason::Stop: return "stop";
    case ResetReason::NoSignal: return "no_signal";
    case ResetReason::FrameIdRegression: return "frame_id_regression";
    case ResetReason::FrameIdDuplicate: return "frame_id_duplicate";
    case ResetReason::FrameIdGap: return "frame_id_gap";
    case ResetReason::TimestampRegression: return "timestamp_regression";
    case ResetReason::TimestampGap: return "timestamp_gap";
    case ResetReason::NonFinite: return "non_finite";
    case ResetReason::ExplicitReset: return "explicit_reset";
    case ResetReason::Count: return "count";
  }
  return "unknown";
}

bool config_valid(const FusionConfig& c, char* err) {
  if (err == nullptr) return false;
  if (!(c.alpha > 0.0f && c.alpha <= 1.0f)) {
    std::snprintf(err, 128, "alpha must be in (0,1], got %g", static_cast<double>(c.alpha));
    return false;
  }
  if (c.confirm_frames < 1) { std::snprintf(err, 128, "confirm_frames must be >= 1"); return false; }
  if (c.confirm_frames > c.max_latency_frames) {
    std::snprintf(err, 128, "confirm_frames %u exceeds max_latency_frames %u",
                  c.confirm_frames, c.max_latency_frames);
    return false;
  }
  if (c.max_window < c.confirm_frames) {
    std::snprintf(err, 128, "max_window %u must be >= confirm_frames %u",
                  c.max_window, c.confirm_frames);
    return false;
  }
  if (c.max_window < 1) { std::snprintf(err, 128, "max_window must be >= 1"); return false; }
  if (!(c.ood_ema_alpha > 0.0f && c.ood_ema_alpha <= 1.0f)) {
    std::snprintf(err, 128, "ood_ema_alpha must be in (0,1]"); return false;
  }
  if (!(c.margin_hysteresis >= 0.0f) || !(c.ood_hysteresis >= 0.0f)) {
    std::snprintf(err, 128, "hysteresis values must be >= 0"); return false;
  }
  return true;
}

void TemporalFusion::configure(const FusionConfig& cfg) {
  char err[128] = {0};
  if (!config_valid(cfg, err)) {
    // fail-closed: leave disabled rather than accepting a broken config.
    cfg_ = FusionConfig{};
    cfg_.enabled = false;
    return;
  }
  cfg_ = cfg;
  st_ = FusionState{};
  stats_ = FusionStats{};
}

void TemporalFusion::reset(const char* reason) {
  clear_history();
  ++stats_.reset_count;
  ++stats_.reset_by_reason[static_cast<int>(ResetReason::ExplicitReset)];
  std::snprintf(stats_.last_explicit_reason, sizeof(stats_.last_explicit_reason), "%s",
                reason != nullptr ? reason : "");
  if (reason != nullptr && std::strcmp(reason, "stop") == 0) {
    ++stats_.reset_by_reason[static_cast<int>(ResetReason::Stop)];
    st_.stopped = true;
  }
  st_.started = false;
  st_.have_prev = false;
}

// (Re)size all fixed buffers to `count` dims. Only called on first frame / reset.
void TemporalFusion::size_buffers(std::size_t count) {
  st_.count = count;
  st_.ema_logits.assign(count, 0.0f);
  st_.window_logits.assign(static_cast<std::size_t>(cfg_.max_window) * count, 0.0f);
  st_.window_top1.assign(cfg_.max_window, -1);
  st_.window_margin.assign(cfg_.max_window, 0.0f);
  st_.mean_scratch.assign(count, 0.0f);
}

void TemporalFusion::clear_history() {
  st_.ema_initialized = false;
  if (st_.ema_logits.size() != st_.count) st_.ema_logits.assign(st_.count, 0.0f);
  else std::fill(st_.ema_logits.begin(), st_.ema_logits.end(), 0.0f);
  st_.window_head = 0;
  st_.window_len = 0;
  st_.confirm_counter = 0;
  st_.fused = -1;
  st_.ood_initialized = false;
  st_.ood_ema = 0.0f;
}

// Detects identity/sequence resets against the previous normal frame.
bool TemporalFusion::detect_reset(const TemporalFusionInput& in, ResetReason* out) {
  if (!st_.started) {
    *out = ResetReason::Start;
    return true;  // first frame / after STOP: initialize prev-identity
  }

  bool cur_has_sha = (in.model_sha256 != nullptr);
  bool prev_has_sha = (st_.prev_model_sha[0] != '\0');
  if (cur_has_sha != prev_has_sha) { *out = ResetReason::ModelShaChange; return true; }
  if (cur_has_sha && prev_has_sha &&
      std::strncmp(in.model_sha256, st_.prev_model_sha, 64) != 0) {
    *out = ResetReason::ModelShaChange; return true;
  }

  if (in.count != st_.count) { *out = ResetReason::DimChange; return true; }

  if (in.mode_id != st_.prev_mode_id) { *out = ResetReason::ModeChange; return true; }
  if (in.lo_freq_hz != st_.prev_lo_freq_hz) { *out = ResetReason::LoFreqChange; return true; }
  if (in.tuning_generation != st_.prev_tuning_generation) {
    *out = ResetReason::TuningGenerationChange; return true;
  }

  if (in.frame_id < st_.prev_frame_id) { *out = ResetReason::FrameIdRegression; return true; }
  if (in.frame_id == st_.prev_frame_id) { *out = ResetReason::FrameIdDuplicate; return true; }
  if (in.frame_id > st_.prev_frame_id + cfg_.max_frame_gap) {
    *out = ResetReason::FrameIdGap; return true;
  }

  if (in.timestamp_ns < st_.prev_timestamp_ns) { *out = ResetReason::TimestampRegression; return true; }
  if (in.timestamp_ns > st_.prev_timestamp_ns + cfg_.max_timestamp_gap_ns) {
    *out = ResetReason::TimestampGap; return true;
  }

  return false;
}

void TemporalFusion::note_reset(ResetReason r, TemporalFusionResult* out) {
  clear_history();
  ++stats_.reset_count;
  ++stats_.reset_by_reason[static_cast<int>(r)];
  out->reset_occurred = true;
  out->reset_reason = reset_reason_name(r);
}

void TemporalFusion::store_prev_identity(const TemporalFusionInput& in) {
  std::strncpy(st_.prev_model_sha, in.model_sha256 != nullptr ? in.model_sha256 : "", 64);
  st_.prev_model_sha[64] = '\0';
  st_.prev_frame_id = in.frame_id;
  st_.prev_timestamp_ns = in.timestamp_ns;
  st_.prev_mode_id = in.mode_id;
  st_.prev_tuning_generation = in.tuning_generation;
  st_.prev_lo_freq_hz = in.lo_freq_hz;
  st_.have_prev = true;
}

void TemporalFusion::push_frame(const float* logits, int top1, float margin) {
  std::size_t base = static_cast<std::size_t>(st_.window_head) * st_.count;
  for (std::size_t i = 0; i < st_.count; ++i) st_.window_logits[base + i] = logits[i];
  st_.window_top1[st_.window_head] = top1;
  st_.window_margin[st_.window_head] = margin;
  st_.window_head = (st_.window_head + 1) % cfg_.max_window;
  if (st_.window_len < cfg_.max_window) ++st_.window_len;
}

void TemporalFusion::update_ema(const float* logits) {
  if (!st_.ema_initialized) {
    for (std::size_t i = 0; i < st_.count; ++i) st_.ema_logits[i] = logits[i];
    st_.ema_initialized = true;
  } else {
    for (std::size_t i = 0; i < st_.count; ++i)
      st_.ema_logits[i] = cfg_.alpha * logits[i] + (1.0f - cfg_.alpha) * st_.ema_logits[i];
  }
}

int TemporalFusion::compute_fused(int raw_class, float raw_margin, bool* changed,
                                  const char** reason) {
  *changed = false;
  *reason = "";

  switch (cfg_.algorithm) {
    case FusionAlgorithm::MajorityVote: {
      int best = -1;
      unsigned best_count = 0;
      for (std::size_t w = 0; w < st_.window_len; ++w) {
        int c = st_.window_top1[w];
        unsigned cnt = 0;
        for (std::size_t k = 0; k < st_.window_len; ++k)
          if (st_.window_top1[k] == c) ++cnt;
        if (cnt > best_count) { best = c; best_count = cnt; }
      }
      if (best != st_.fused && st_.fused >= 0) { *changed = true; *reason = "majority_vote"; }
      return best;
    }

    case FusionAlgorithm::LogitsMean: {
      std::fill(st_.mean_scratch.begin(), st_.mean_scratch.end(), 0.0f);
      for (std::size_t w = 0; w < st_.window_len; ++w) {
        const float* row = &st_.window_logits[static_cast<std::size_t>(w) * st_.count];
        for (std::size_t i = 0; i < st_.count; ++i) st_.mean_scratch[i] += row[i];
      }
      if (st_.window_len > 0)
        for (std::size_t i = 0; i < st_.count; ++i)
          st_.mean_scratch[i] /= static_cast<float>(st_.window_len);
      int fused = -1; float m = 0.0f;
      argmax_top2(st_.mean_scratch.data(), st_.count, &fused, &m);
      if (fused != st_.fused && st_.fused >= 0) { *changed = true; *reason = "logits_mean"; }
      return fused;
    }

    case FusionAlgorithm::LogitsEMA: {
      int fused = -1; float m = 0.0f;
      argmax_top2(st_.ema_logits.data(), st_.count, &fused, &m);
      if (fused != st_.fused && st_.fused >= 0) { *changed = true; *reason = "logits_ema"; }
      return fused;
    }

    case FusionAlgorithm::EMA_KFrameConfirm: {
      int candidate = -1; float m = 0.0f;
      argmax_top2(st_.ema_logits.data(), st_.count, &candidate, &m);
      if (st_.fused < 0) return candidate;  // first fused frame
      if (candidate == st_.fused) { st_.confirm_counter = 0; return st_.fused; }
      // fast switch on a clear single-frame peak (clear failure of current class)
      if (raw_class == candidate && raw_margin >= cfg_.margin_hysteresis) {
        st_.confirm_counter = 0;
        *changed = true;
        *reason = "fast_switch";
        return candidate;
      }
      ++st_.confirm_counter;
      if (st_.confirm_counter >= cfg_.confirm_frames) {
        st_.confirm_counter = 0;
        *changed = true;
        *reason = "ema_confirm";
        return candidate;
      }
      return st_.fused;
    }

    case FusionAlgorithm::EMA_MarginHysteresis: {
      int candidate = -1; float m = 0.0f;
      argmax_top2(st_.ema_logits.data(), st_.count, &candidate, &m);
      if (st_.fused < 0) return candidate;  // first fused frame
      if (candidate == st_.fused) return st_.fused;
      if (st_.ema_logits[static_cast<std::size_t>(candidate)] -
              st_.ema_logits[static_cast<std::size_t>(st_.fused)] >
          cfg_.margin_hysteresis) {
        *changed = true;
        *reason = "margin_hysteresis";
        return candidate;
      }
      return st_.fused;
    }
  }

  return raw_class;
}

float TemporalFusion::current_stability() const {
  if (st_.window_len == 0 || st_.fused < 0) return 0.0f;
  unsigned agree = 0;
  for (std::size_t w = 0; w < st_.window_len; ++w)
    if (st_.window_top1[w] == st_.fused) ++agree;
  return static_cast<float>(agree) / static_cast<float>(st_.window_len);
}

TemporalFusionResult TemporalFusion::process(const TemporalFusionInput& in) {
  ++stats_.total_frames;
  TemporalFusionResult r;

  if (in.count != 12 && in.count != 24) {
    r.valid = false;
    r.change_reason = kInvalidDim;
    return r;
  }
  if (in.logits == nullptr) {
    r.valid = false;
    r.change_reason = kNullLogits;
    return r;
  }

  int raw_class = -1;
  float raw_margin = 0.0f;
  if (!argmax_top2(in.logits, in.count, &raw_class, &raw_margin)) {
    r.valid = false;
    r.change_reason = kNonFinite;
    note_reset(ResetReason::NonFinite, &r);
    return r;
  }
  r.raw_class_index = raw_class;
  r.raw_margin = raw_margin;
  r.valid = true;

  if (!cfg_.enabled) {
    r.fused_class_index = raw_class;
    r.fused_margin = raw_margin;
    r.stability = 1.0f;
    r.accumulated_frames = 0;
    r.class_changed = false;
    r.change_reason = kDisabled;
    return r;
  }

  // independent OOD EWMA (never mixed into class logits)
  if (!st_.ood_initialized) {
    st_.ood_ema = in.ood_score;
    st_.ood_initialized = true;
  } else {
    st_.ood_ema = cfg_.ood_ema_alpha * in.ood_score + (1.0f - cfg_.ood_ema_alpha) * st_.ood_ema;
  }
  stats_.ood_ema = st_.ood_ema;
  stats_.ood_rejected = (in.ood_threshold > 0.0f) ? (st_.ood_ema > in.ood_threshold) : false;

  // ERROR bypasses immediately (no history update).
  if (in.error) {
    r.fused_class_index = raw_class;
    r.fused_margin = raw_margin;
    r.stability = current_stability();
    r.accumulated_frames = st_.window_len;
    r.class_changed = false;
    r.change_reason = kErrorBypass;
    return r;
  }

  // NO_SIGNAL clears fusion history, passthrough.
  if (in.no_signal) {
    note_reset(ResetReason::NoSignal, &r);
    r.fused_class_index = raw_class;
    r.fused_margin = raw_margin;
    r.stability = 0.0f;
    r.accumulated_frames = 0;
    r.class_changed = false;
    r.change_reason = kNoSignal;
    return r;
  }

  // identity/sequence reset detection + buffer sizing + prev-identity update.
  ResetReason rr = ResetReason::Count;
  if (detect_reset(in, &rr)) {
    size_buffers(in.count);
    if (st_.started) {
      note_reset(rr, &r);                 // mid-stream reset (sha/dim/mode/lo/tuning/seq)
    } else if (st_.stopped) {
      st_.stopped = false;
      note_reset(ResetReason::Start, &r); // restart after STOP
    } else {
      clear_history();                    // very first frame: init, no reset flag
      ++stats_.reset_by_reason[static_cast<int>(ResetReason::Start)];
    }
    st_.started = true;
    store_prev_identity(in);
  } else {
    store_prev_identity(in);
  }

  // UNKNOWN (OOD-U already rejected): never overridden by vote, no history update.
  if (in.unknown) {
    r.fused_class_index = raw_class;
    r.fused_margin = raw_margin;
    r.stability = current_stability();
    r.accumulated_frames = st_.window_len;
    r.class_changed = false;
    r.change_reason = kUnknownPassthrough;
    return r;
  }

  push_frame(in.logits, raw_class, raw_margin);
  update_ema(in.logits);

  bool changed = false;
  const char* reason = "";
  int fused = compute_fused(raw_class, raw_margin, &changed, &reason);
  if (changed) { r.class_changed = true; r.change_reason = reason; }
  st_.fused = fused;

  r.fused_class_index = fused;
  {
    int t = -1; float m = 0.0f;
    argmax_top2(st_.ema_logits.data(), st_.count, &t, &m);
    r.fused_margin = m;
  }
  r.stability = current_stability();
  r.accumulated_frames = st_.window_len;
  return r;
}

}  // namespace m25
