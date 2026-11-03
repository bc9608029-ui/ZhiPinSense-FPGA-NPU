// m25_temporal_fusion_replay.cpp -- M25-A offline logits replay tool.
//
// Drives the isolated M25-A TemporalFusion module over a stream of raw 12/24-dim
// NPU logits WITHOUT any board / Gate 9/10 / real model.  Two sources:
//
//   --demo            built-in deterministic 24-class stream (glitch + real switch)
//   --jsonl FILE      JSON-lines, one frame per line:
//       {"frame_id":1,"timestamp_ns":1000000,"model_sha256":"<64 hex>",
//        "mode_id":0,"tuning_generation":0,"lo_freq_hz":2400000000,
//        "logits":[0.0,...,10.0,...],
//        "no_signal":false,"unknown":false,"error":false,
//        "ood_score":0.0,"ood_threshold":0.0}
//
// Per frame it prints raw/fused top-1, raw/fused margin, stability, and the
// change/reset reason.  A final summary reports frame counts, raw-vs-fused
// decision changes, resets-by-reason, and mean per-frame CPU time.
//
// The JSON parser is minimal and dependency-free (numbers/strings/bools/arrays).

#include "../sdr_adapter/m25_temporal_fusion.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

namespace {

const char* kDemoSha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

struct Frame {
  std::vector<float> logits;
  std::uint64_t frame_id = 0;
  std::uint64_t timestamp_ns = 0;
  std::string model_sha256;   // empty -> nullptr
  int mode_id = 0;
  std::uint64_t tuning_generation = 0;
  std::uint64_t lo_freq_hz = 0;
  bool no_signal = false;
  bool unknown = false;
  bool error = false;
  float ood_score = 0.0f;
  float ood_threshold = 0.0f;
};

// ---- minimal JSON (no external deps) ----

std::size_t find_value(const std::string& s, const std::string& key) {
  const std::string pat = "\"" + key + "\"";
  const std::size_t p = s.find(pat);
  if (p == std::string::npos) return std::string::npos;
  const std::size_t q = s.find(':', p + pat.size());
  if (q == std::string::npos) return std::string::npos;
  std::size_t i = q + 1;
  while (i < s.size() && (s[i] == ' ' || s[i] == '\t')) ++i;
  return i;
}

bool parse_string(const std::string& s, std::size_t i, std::string* out) {
  if (i >= s.size() || s[i] != '"') return false;
  const std::size_t j = s.find('"', i + 1);
  if (j == std::string::npos) return false;
  *out = s.substr(i + 1, j - i - 1);
  return true;
}

bool parse_u64(const std::string& s, std::size_t i, std::uint64_t* out) {
  char* end = nullptr;
  const unsigned long long v = std::strtoull(s.c_str() + i, &end, 10);
  if (end == s.c_str() + i) return false;
  *out = static_cast<std::uint64_t>(v);
  return true;
}

bool parse_int(const std::string& s, std::size_t i, int* out) {
  char* end = nullptr;
  const long v = std::strtol(s.c_str() + i, &end, 10);
  if (end == s.c_str() + i) return false;
  *out = static_cast<int>(v);
  return true;
}

bool parse_double(const std::string& s, std::size_t i, double* out) {
  char* end = nullptr;
  const double v = std::strtod(s.c_str() + i, &end);
  if (end == s.c_str() + i) return false;
  *out = v;
  return true;
}

bool parse_bool(const std::string& s, std::size_t i, bool* out) {
  if (s.compare(i, 4, "true") == 0) { *out = true; return true; }
  if (s.compare(i, 5, "false") == 0) { *out = false; return true; }
  return false;
}

bool parse_farray(const std::string& s, std::size_t i, std::vector<float>* out) {
  if (i >= s.size() || s[i] != '[') return false;
  const std::size_t j = s.find(']', i);
  if (j == std::string::npos) return false;
  out->clear();
  std::size_t p = i + 1;
  while (p < j) {
    while (p < j && (s[p] == ' ' || s[p] == '\t' || s[p] == ',' ||
                     s[p] == '\n' || s[p] == '\r'))
      ++p;
    if (p >= j) break;
    char* end = nullptr;
    const double v = std::strtod(s.c_str() + p, &end);
    if (end == s.c_str() + p) return false;
    out->push_back(static_cast<float>(v));
    p = static_cast<std::size_t>(end - s.c_str());
  }
  return true;
}

bool parse_frame(const std::string& line, Frame* f) {
  std::size_t p = find_value(line, "frame_id");
  if (p == std::string::npos || !parse_u64(line, p, &f->frame_id)) return false;
  p = find_value(line, "timestamp_ns");
  if (p == std::string::npos || !parse_u64(line, p, &f->timestamp_ns)) return false;
  p = find_value(line, "model_sha256");
  if (p != std::string::npos) {
    std::string sha;
    if (parse_string(line, p, &sha)) f->model_sha256 = sha;
  }
  p = find_value(line, "mode_id");
  if (p != std::string::npos) parse_int(line, p, &f->mode_id);
  p = find_value(line, "tuning_generation");
  if (p != std::string::npos) parse_u64(line, p, &f->tuning_generation);
  p = find_value(line, "lo_freq_hz");
  if (p != std::string::npos) parse_u64(line, p, &f->lo_freq_hz);
  p = find_value(line, "no_signal");
  if (p != std::string::npos) parse_bool(line, p, &f->no_signal);
  p = find_value(line, "unknown");
  if (p != std::string::npos) parse_bool(line, p, &f->unknown);
  p = find_value(line, "error");
  if (p != std::string::npos) parse_bool(line, p, &f->error);
  p = find_value(line, "ood_score");
  if (p != std::string::npos) { double d = 0.0; parse_double(line, p, &d); f->ood_score = static_cast<float>(d); }
  p = find_value(line, "ood_threshold");
  if (p != std::string::npos) { double d = 0.0; parse_double(line, p, &d); f->ood_threshold = static_cast<float>(d); }
  p = find_value(line, "logits");
  if (p == std::string::npos || !parse_farray(line, p, &f->logits)) return false;
  return true;
}

// ---- built-in demo stream ----

std::vector<Frame> make_demo() {
  const int count = 24;
  std::vector<Frame> frames;
  auto add = [&](int cls, float margin) {
    Frame f;
    f.frame_id = static_cast<std::uint64_t>(frames.size() + 1);
    f.timestamp_ns = 1000000ULL + frames.size() * 1000000ULL;
    f.model_sha256 = kDemoSha;
    f.logits.assign(static_cast<std::size_t>(count), 0.0f);
    const int other = (cls + 1) % count;
    f.logits[static_cast<std::size_t>(cls)] = 10.0f;
    f.logits[static_cast<std::size_t>(other)] = 10.0f - margin;
    frames.push_back(std::move(f));
  };
  for (int i = 0; i < 20; ++i) add(5, 10.0f);   // stable class 5 (clear)
  add(17, 0.3f);                                 // single-frame glitch -> class 17
  for (int i = 0; i < 19; ++i) add(5, 10.0f);   // back to class 5
  for (int i = 0; i < 20; ++i) add(9, 10.0f);   // real switch -> class 9
  return frames;
}

// ---- argument parsing ----

struct Args {
  bool demo = false;
  std::string jsonl;
  bool disabled = false;
  std::string algorithm = "ema_kframe_confirm";
};

m25::FusionAlgorithm parse_algorithm(const std::string& s, bool* ok) {
  *ok = true;
  if (s == "majority_vote") return m25::FusionAlgorithm::MajorityVote;
  if (s == "logits_mean") return m25::FusionAlgorithm::LogitsMean;
  if (s == "logits_ema") return m25::FusionAlgorithm::LogitsEMA;
  if (s == "ema_kframe_confirm") return m25::FusionAlgorithm::EMA_KFrameConfirm;
  if (s == "ema_margin_hysteresis") return m25::FusionAlgorithm::EMA_MarginHysteresis;
  *ok = false;
  return m25::FusionAlgorithm::EMA_KFrameConfirm;
}

void usage(const char* argv0) {
  std::fprintf(stderr,
               "usage: %s (--demo | --jsonl FILE) [--algorithm NAME] [--disabled]\n"
               "  algorithms: majority_vote logits_mean logits_ema\n"
               "              ema_kframe_confirm ema_margin_hysteresis\n",
               argv0);
}

bool parse_args(int argc, char** argv, Args& a) {
  for (int i = 1; i < argc; ++i) {
    const std::string s = argv[i];
    if (s == "--demo") {
      a.demo = true;
    } else if (s == "--jsonl") {
      if (i + 1 >= argc) return false;
      a.jsonl = argv[++i];
    } else if (s == "--algorithm") {
      if (i + 1 >= argc) return false;
      a.algorithm = argv[++i];
    } else if (s == "--disabled") {
      a.disabled = true;
    } else {
      return false;
    }
  }
  return true;
}

m25::TemporalFusionInput to_input(const Frame& f) {
  m25::TemporalFusionInput in;
  in.logits = f.logits.data();
  in.count = f.logits.size();
  in.frame_id = f.frame_id;
  in.timestamp_ns = f.timestamp_ns;
  in.model_sha256 = f.model_sha256.empty() ? nullptr : f.model_sha256.c_str();
  in.mode_id = f.mode_id;
  in.tuning_generation = f.tuning_generation;
  in.lo_freq_hz = f.lo_freq_hz;
  in.no_signal = f.no_signal;
  in.unknown = f.unknown;
  in.error = f.error;
  in.ood_score = f.ood_score;
  in.ood_threshold = f.ood_threshold;
  return in;
}

const char* or_dash(const char* s) { return (s == nullptr || s[0] == '\0') ? "-" : s; }

}  // namespace

int main(int argc, char** argv) {
  Args a;
  if (!parse_args(argc, argv, a) || (!a.demo && a.jsonl.empty())) {
    usage(argv[0]);
    return 2;
  }
  bool algo_ok = false;
  const m25::FusionAlgorithm algo = parse_algorithm(a.algorithm, &algo_ok);
  if (!algo_ok) {
    std::fprintf(stderr, "unknown algorithm: %s\n", a.algorithm.c_str());
    return 2;
  }

  std::vector<Frame> frames;
  if (a.demo) {
    frames = make_demo();
  } else {
    std::ifstream in(a.jsonl);
    if (!in.is_open()) {
      std::fprintf(stderr, "cannot open --jsonl: %s\n", a.jsonl.c_str());
      return 2;
    }
    std::string line;
    std::size_t lineno = 0;
    while (std::getline(in, line)) {
      ++lineno;
      if (line.empty()) continue;
      Frame f;
      if (!parse_frame(line, &f)) {
        std::fprintf(stderr, "line %zu: malformed frame\n", lineno);
        return 2;
      }
      frames.push_back(std::move(f));
    }
  }

  m25::FusionConfig cfg;
  cfg.enabled = !a.disabled;
  cfg.algorithm = algo;
  m25::TemporalFusion tf;
  tf.configure(cfg);

  std::printf("# M25-A temporal fusion replay  (algorithm=%s enabled=%s frames=%zu)\n",
              m25::algorithm_name(algo), cfg.enabled ? "yes" : "no", frames.size());
  std::printf("# f=frame raw=fus top-1 rmar/fmar=margin stab=stability chg/rst=reason\n");

  std::uint64_t raw_changes = 0, fused_changes = 0, overridden = 0;
  int prev_raw = -1, prev_fused = -1;
  double total_us = 0.0;

  for (std::size_t k = 0; k < frames.size(); ++k) {
    const m25::TemporalFusionInput in = to_input(frames[k]);
    const auto t0 = std::chrono::steady_clock::now();
    const m25::TemporalFusionResult r = tf.process(in);
    const auto t1 = std::chrono::steady_clock::now();
    total_us += std::chrono::duration<double, std::micro>(t1 - t0).count();

    if (prev_raw >= 0 && r.raw_class_index != prev_raw) ++raw_changes;
    if (prev_fused >= 0 && r.fused_class_index != prev_fused) ++fused_changes;
    if (r.valid && r.fused_class_index != r.raw_class_index) ++overridden;
    prev_raw = r.raw_class_index;
    prev_fused = r.fused_class_index;

    std::printf("f=%04llu raw=%2d fus=%2d rmar=%7.3f fmar=%7.3f stab=%.2f chg=%d(%s) rst=%d(%s)\n",
                static_cast<unsigned long long>(frames[k].frame_id),
                r.raw_class_index, r.fused_class_index,
                static_cast<double>(r.raw_margin), static_cast<double>(r.fused_margin),
                static_cast<double>(r.stability),
                r.class_changed ? 1 : 0, or_dash(r.change_reason),
                r.reset_occurred ? 1 : 0, or_dash(r.reset_reason));
  }

  const auto& st = tf.stats();
  std::printf("# frames processed       = %zu\n", frames.size());
  std::printf("# raw top1 changes       = %llu\n", static_cast<unsigned long long>(raw_changes));
  std::printf("# fused top1 changes     = %llu\n", static_cast<unsigned long long>(fused_changes));
  std::printf("# frames overridden      = %llu (fused != raw)\n", static_cast<unsigned long long>(overridden));
  std::printf("# resets                 = %llu\n", static_cast<unsigned long long>(st.reset_count));
  for (int i = 0; i < static_cast<int>(m25::ResetReason::Count); ++i) {
    const std::uint64_t n = st.reset_by_reason[i];
    if (n > 0)
      std::printf("#   reset %-22s = %llu\n", m25::reset_reason_name(static_cast<m25::ResetReason>(i)),
                  static_cast<unsigned long long>(n));
  }
  if (frames.size() > 0)
    std::printf("# mean process time      = %.2f us/frame\n", total_us / static_cast<double>(frames.size()));
  return 0;
}
