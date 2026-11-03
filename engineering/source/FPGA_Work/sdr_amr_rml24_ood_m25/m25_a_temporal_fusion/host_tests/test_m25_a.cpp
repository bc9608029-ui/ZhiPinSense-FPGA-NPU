// test_m25_a.cpp -- M25-A temporal fusion host test.
// Verifies config validation, default-OFF single-frame passthrough, fail-closed
// NaN/Inf/dim/null handling, the five fusion algorithms, all reset conditions,
// special handling (NO_SIGNAL / UNKNOWN / ERROR / OOD independence), bounded
// window, and (in release) zero steady-state heap allocation.

#include <cstdio>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <utility>
#include <vector>

#include "../sdr_adapter/m25_temporal_fusion.hpp"

namespace {
int g_pass = 0;
int g_fail = 0;
void check(bool ok, const char* what) {
  if (ok) { ++g_pass; }
  else { ++g_fail; std::printf("FAIL: %s\n", what); }
}

const char* SHA_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const char* SHA_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

std::vector<float> one_cls(int count, int cls, float top = 10.0f) {
  std::vector<float> v(count, 0.0f);
  v[cls] = top;
  return v;
}

std::vector<float> two_cls(int count, int a, int b, float va, float vb) {
  std::vector<float> v(count, 0.0f);
  v[a] = va;
  v[b] = vb;
  return v;
}

// feed a sequence of single-class logits; returns true if class_changed was
// observed at least once, and fills *last with the final result. fid/ts are
// advanced across calls so consecutive run_stream calls form one stream.
bool run_stream(m25::TemporalFusion& tf, const std::vector<int>& classes,
                int count, const char* sha, std::uint64_t& fid, std::uint64_t& ts,
                m25::TemporalFusionResult* last) {
  bool changed_any = false;
  for (std::size_t i = 0; i < classes.size(); ++i) {
    auto v = one_cls(count, classes[i]);
    m25::TemporalFusionInput in;
    in.logits = v.data();
    in.count = count;
    in.frame_id = fid++;
    in.timestamp_ns = ts;
    ts += 1000000;
    in.model_sha256 = sha;
    m25::TemporalFusionResult r = tf.process(in);
    if (r.class_changed) changed_any = true;
    *last = r;
  }
  return changed_any;
}

// seed two baseline frames with a fixed identity (class 2 logits).
void seed_baseline(m25::TemporalFusion& tf, const char* sha, int count, int mode,
                   std::uint64_t tuning, std::uint64_t lo) {
  auto v = one_cls(count, 2);
  m25::TemporalFusionInput in;
  in.logits = v.data(); in.count = count; in.frame_id = 1; in.timestamp_ns = 1000000;
  in.model_sha256 = sha; in.mode_id = mode; in.tuning_generation = tuning; in.lo_freq_hz = lo;
  tf.process(in);
  in.frame_id = 2; in.timestamp_ns = 2000000;
  tf.process(in);
}

}  // namespace

#if !defined(M25_SKIP_ALLOC_TEST)
// Release-only zero-allocation check: a scoped global-new counter. Disabled
// under ASan/UBSan (their runtimes provide their own operator new).
#include <new>
#include <cstdlib>
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmismatched-new-delete"
static long g_allocs = 0;
static bool g_counting = false;
void* operator new(std::size_t n) {
  if (g_counting) ++g_allocs;
  if (void* p = std::malloc(n)) return p;
  throw std::bad_alloc();
}
void* operator new[](std::size_t n) {
  if (g_counting) ++g_allocs;
  if (void* p = std::malloc(n)) return p;
  throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }
#pragma GCC diagnostic pop
#endif

int main() {
  std::printf("== M25-A temporal fusion offline module tests ==\n");

  // ---- 1. config validation ----
  {
    char err[128] = {0};
    m25::FusionConfig def;
    check(m25::config_valid(def, err), "1: default config valid");
    m25::FusionConfig bad = def; bad.alpha = 0.0f;
    check(!m25::config_valid(bad, err), "1: alpha=0 invalid");
    bad = def; bad.alpha = 1.5f;
    check(!m25::config_valid(bad, err), "1: alpha>1 invalid");
    bad = def; bad.confirm_frames = 5; bad.max_latency_frames = 4;
    check(!m25::config_valid(bad, err), "1: confirm>latency invalid");
    bad = def; bad.max_window = 1; bad.confirm_frames = 2;
    check(!m25::config_valid(bad, err), "1: window<confirm invalid");
    check(std::strcmp(m25::algorithm_name(m25::FusionAlgorithm::EMA_KFrameConfirm),
                      "ema_kframe_confirm") == 0, "1: algorithm_name default");
  }

  // ---- 2. default-OFF single-frame passthrough (byte-identical) ----
  {
    m25::TemporalFusion tf;  // never configured
    check(!tf.enabled(), "2: unconfigured is disabled");
    auto v = two_cls(12, 3, 7, 8.0f, 3.0f);
    m25::TemporalFusionInput in;
    in.logits = v.data(); in.count = 12; in.frame_id = 1; in.timestamp_ns = 1000;
    m25::TemporalFusionResult r = tf.process(in);
    check(r.valid, "2: disabled result valid");
    check(r.raw_class_index == 3 && r.fused_class_index == 3, "2: fused==raw class");
    check(r.raw_margin == r.fused_margin, "2: fused==raw margin");
    check(!r.class_changed, "2: no class_changed when disabled");
    check(std::strcmp(r.change_reason, "disabled") == 0, "2: change_reason disabled");
    check(r.accumulated_frames == 0, "2: accumulated_frames 0 when disabled");

    // explicit disabled config behaves the same
    m25::FusionConfig c;
    c.enabled = false;
    tf.configure(c);
    r = tf.process(in);
    check(r.valid && r.fused_class_index == r.raw_class_index, "2: explicit disabled passthrough");
  }

  // ---- 3. fail-closed ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    tf.configure(c);
    std::vector<float> v12 = one_cls(12, 2);
    m25::TemporalFusionInput in;

    in.logits = v12.data(); in.count = 13; in.frame_id = 1; in.timestamp_ns = 1000;
    m25::TemporalFusionResult r = tf.process(in);
    check(!r.valid && std::strcmp(r.change_reason, "invalid_dim") == 0, "3: invalid dim fail-closed");

    in.count = 12; in.logits = nullptr;
    r = tf.process(in);
    check(!r.valid && std::strcmp(r.change_reason, "null_logits") == 0, "3: null logits fail-closed");

    std::vector<float> vnan = one_cls(12, 2);
    vnan[4] = std::nanf("");
    in.logits = vnan.data(); in.count = 12; in.frame_id = 1; in.timestamp_ns = 1000;
    r = tf.process(in);
    check(!r.valid && std::strcmp(r.change_reason, "non_finite") == 0, "3: NaN fail-closed");

    std::vector<float> vinf = one_cls(12, 2);
    vinf[4] = INFINITY;
    in.logits = vinf.data();
    r = tf.process(in);
    check(!r.valid && std::strcmp(r.change_reason, "non_finite") == 0, "3: Inf fail-closed");
  }

  // ---- 4a. MajorityVote ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::MajorityVote; c.max_window = 4; c.confirm_frames = 1;
    tf.configure(c);
    m25::TemporalFusionResult r;
    std::uint64_t fid = 1, ts = 1000000;
    run_stream(tf, {0, 0, 0, 0, 0}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 0, "4a: majority converges to 0");
    check(r.stability == 1.0f, "4a: stability 1.0 on unanimous window");
    bool changed = run_stream(tf, {1, 1, 1, 1, 1, 1}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 1, "4a: majority flips to 1");
    check(changed, "4a: majority observed a class change");
  }

  // ---- 4b. LogitsMean ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::LogitsMean; c.max_window = 4; c.confirm_frames = 1;
    tf.configure(c);
    m25::TemporalFusionResult r;
    std::uint64_t fid = 1, ts = 1000000;
    run_stream(tf, {0, 0, 0, 0, 0}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 0, "4b: mean converges to 0");
    bool changed = run_stream(tf, {1, 1, 1, 1, 1, 1}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 1, "4b: mean flips to 1");
    check(changed, "4b: mean observed a class change");
  }

  // ---- 4c. LogitsEMA ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::LogitsEMA; c.alpha = 0.3f;
    tf.configure(c);
    m25::TemporalFusionResult r;
    std::uint64_t fid = 1, ts = 1000000;
    run_stream(tf, {0, 0, 0, 0, 0}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 0, "4c: EMA converges to 0");
    run_stream(tf, {1, 1, 1, 1, 1, 1, 1, 1}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 1, "4c: EMA eventually flips to 1");
  }

  // ---- 4d. EMA_KFrameConfirm (default): fast switch + confirm gating ----
  {
    // fast switch on a clear single-frame peak
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::EMA_KFrameConfirm;
    c.alpha = 1.0f; c.confirm_frames = 3; c.margin_hysteresis = 1.0f;
    tf.configure(c);
    m25::TemporalFusionResult r;
    std::uint64_t fid = 1, ts = 1000000;
    run_stream(tf, {0, 0, 0}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 0, "4d: confirm seeded to 0");
    // one clear frame of class 1 (margin 100 >= hysteresis) -> fast switch
    auto v = one_cls(12, 1, 100.0f);
    m25::TemporalFusionInput in;
    in.logits = v.data(); in.count = 12; in.frame_id = fid++; in.timestamp_ns = ts;
    ts += 1000000;
    in.model_sha256 = SHA_A;
    r = tf.process(in);
    check(r.class_changed && r.fused_class_index == 1, "4d: fast switch on clear peak");
    check(std::strcmp(r.change_reason, "fast_switch") == 0, "4d: fast_switch reason");

    // confirm gating on a non-clear candidate (alpha=1.0 -> EMA==raw)
    m25::TemporalFusion tf2;
    tf2.configure(c);
    m25::TemporalFusionResult r2;
    std::uint64_t fid2 = 1, ts2 = 1000000;
    run_stream(tf2, {0}, 12, SHA_A, fid2, ts2, &r2);
    check(r2.fused_class_index == 0, "4d: confirm gate seeded to 0");
    // non-clear switch to class 1 (margin 0.2 < 1.0): needs 3 consecutive frames
    auto weak = two_cls(12, 1, 0, 10.2f, 10.0f);
    in.logits = weak.data(); in.count = 12; in.frame_id = fid2++; in.timestamp_ns = ts2;
    ts2 += 1000000; in.model_sha256 = SHA_A;
    r2 = tf2.process(in);  // confirm 1
    check(r2.fused_class_index == 0, "4d: confirm gate holds (frame 1)");
    in.frame_id = fid2++; in.timestamp_ns = ts2; ts2 += 1000000;
    r2 = tf2.process(in);  // confirm 2
    check(r2.fused_class_index == 0, "4d: confirm gate holds (frame 2)");
    in.frame_id = fid2++; in.timestamp_ns = ts2; ts2 += 1000000;
    r2 = tf2.process(in);  // confirm 3 -> switch
    check(r2.class_changed && r2.fused_class_index == 1, "4d: confirm gate switches at K frames");
    check(std::strcmp(r2.change_reason, "ema_confirm") == 0, "4d: ema_confirm reason");
  }

  // ---- 4e. EMA_MarginHysteresis ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::EMA_MarginHysteresis;
    c.alpha = 1.0f; c.margin_hysteresis = 1.0f;
    tf.configure(c);
    m25::TemporalFusionResult r;
    std::uint64_t fid = 1, ts = 1000000;
    run_stream(tf, {0}, 12, SHA_A, fid, ts, &r);
    check(r.fused_class_index == 0, "4e: hysteresis seeded to 0");
    // gap 0.5 <= hysteresis: hold
    auto small = two_cls(12, 1, 0, 10.5f, 10.0f);
    m25::TemporalFusionInput in;
    in.logits = small.data(); in.count = 12; in.frame_id = fid++; in.timestamp_ns = ts;
    ts += 1000000;
    in.model_sha256 = SHA_A;
    r = tf.process(in);
    check(r.fused_class_index == 0, "4e: hysteresis holds below band");
    // gap 1.5 > hysteresis: switch
    auto big = two_cls(12, 1, 0, 11.5f, 10.0f);
    in.logits = big.data(); in.frame_id = fid++; in.timestamp_ns = ts; ts += 1000000;
    r = tf.process(in);
    check(r.class_changed && r.fused_class_index == 1, "4e: hysteresis switches past band");
    check(std::strcmp(r.change_reason, "margin_hysteresis") == 0, "4e: margin_hysteresis reason");
  }

  // ---- 5. reset conditions (each isolated on a fresh fusion) ----
  {
    auto make = []() {
      m25::TemporalFusion tf;
      m25::FusionConfig c; c.enabled = true;
      c.algorithm = m25::FusionAlgorithm::EMA_KFrameConfirm; c.alpha = 1.0f;
      tf.configure(c);
      return tf;
    };
    // frame 3 carrying a possibly-different identity vs. the two baseline frames.
    // Returns the logits storage together with the input so the pointer stays valid.
    auto frame3 = [](const char* sha, int count, int mode, std::uint64_t tuning,
                     std::uint64_t lo, std::uint64_t fid, std::uint64_t ts)
        -> std::pair<std::vector<float>, m25::TemporalFusionInput> {
      auto v = one_cls(count, 2);
      m25::TemporalFusionInput in;
      in.logits = v.data(); in.count = count; in.frame_id = fid; in.timestamp_ns = ts;
      in.model_sha256 = sha; in.mode_id = mode; in.tuning_generation = tuning;
      in.lo_freq_hz = lo;
      return {std::move(v), in};
    };
    auto expect_reset = [](const m25::TemporalFusionResult& r, const char* reason) {
      return r.reset_occurred && std::strcmp(r.reset_reason, reason) == 0;
    };

    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_B, 12, 0, 7, 2400000000ULL, 3, 3000000);
      check(expect_reset(tf.process(f.second), "model_sha"), "5: model_sha reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 24, 0, 7, 2400000000ULL, 3, 3000000);
      check(expect_reset(tf.process(f.second), "dim"), "5: dim reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 1, 7, 2400000000ULL, 3, 3000000);
      check(expect_reset(tf.process(f.second), "mode"), "5: mode reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 0, 7, 2410000000ULL, 3, 3000000);
      check(expect_reset(tf.process(f.second), "lo_freq"), "5: lo_freq reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 0, 8, 2400000000ULL, 3, 3000000);
      check(expect_reset(tf.process(f.second), "tuning_generation"), "5: tuning_generation reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 0, 7, 2400000000ULL, 1, 3000000);
      check(expect_reset(tf.process(f.second), "frame_id_regression"), "5: frame_id regression reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 0, 7, 2400000000ULL, 2, 3000000);
      check(expect_reset(tf.process(f.second), "frame_id_duplicate"), "5: frame_id duplicate reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 0, 7, 2400000000ULL, 100, 3000000);
      check(expect_reset(tf.process(f.second), "frame_id_gap"), "5: frame_id gap reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 0, 7, 2400000000ULL, 3, 5000);
      check(expect_reset(tf.process(f.second), "timestamp_regression"), "5: timestamp regression reset"); }
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      auto f = frame3(SHA_A, 12, 0, 7, 2400000000ULL, 3, 1000000000ULL);
      check(expect_reset(tf.process(f.second), "timestamp_gap"), "5: timestamp gap reset"); }

    // STOP latch then START (restart after stop must report a start reset)
    { auto tf = make(); seed_baseline(tf, SHA_A, 12, 0, 7, 2400000000ULL);
      tf.reset("stop");
      check(tf.stats().reset_by_reason[static_cast<int>(m25::ResetReason::Stop)] >= 1, "5: STOP counted");
      auto f = frame3(SHA_A, 12, 0, 7, 2400000000ULL, 3, 3000000);
      check(expect_reset(tf.process(f.second), "start"), "5: start after stop");
      check(tf.stats().reset_by_reason[static_cast<int>(m25::ResetReason::Start)] >= 1, "5: START counted"); }

    // explicit reset
    { auto tf = make();
      tf.reset("test_reset");
      check(tf.stats().reset_by_reason[static_cast<int>(m25::ResetReason::ExplicitReset)] >= 1, "5: explicit reset counted");
      check(tf.stats().reset_count >= 1, "5: reset_count incremented"); }
  }

  // ---- 6. special handling ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::EMA_KFrameConfirm; c.alpha = 0.5f;
    tf.configure(c);

    auto v = one_cls(12, 5);
    m25::TemporalFusionInput in;
    in.logits = v.data(); in.count = 12; in.frame_id = 1; in.timestamp_ns = 1000000;
    in.model_sha256 = SHA_A;
    tf.process(in);
    in.frame_id = 2; in.timestamp_ns = 2000000;
    tf.process(in);

    // NO_SIGNAL clears history
    in.frame_id = 3; in.timestamp_ns = 3000000; in.no_signal = true;
    m25::TemporalFusionResult r = tf.process(in);
    check(r.reset_occurred && std::strcmp(r.reset_reason, "no_signal") == 0, "6: no_signal clears history");
    check(r.accumulated_frames == 0, "6: no_signal zeroes accumulated_frames");
    in.no_signal = false;

    // UNKNOWN not overridden by vote
    in.frame_id = 4; in.timestamp_ns = 4000000; in.unknown = true;
    r = tf.process(in);
    check(r.fused_class_index == r.raw_class_index, "6: unknown passes through raw");
    check(std::strcmp(r.change_reason, "unknown_passthrough") == 0, "6: unknown_passthrough reason");
    in.unknown = false;

    // ERROR bypasses immediately
    in.frame_id = 5; in.timestamp_ns = 5000000; in.error = true;
    r = tf.process(in);
    check(std::strcmp(r.change_reason, "error_bypass") == 0, "6: error bypass reason");
    check(r.fused_class_index == r.raw_class_index, "6: error passes through raw");
    in.error = false;

    // OOD independent EWMA tracked, does not change class fusion
    in.frame_id = 6; in.timestamp_ns = 6000000; in.ood_score = 10.0f; in.ood_threshold = 1.0f;
    r = tf.process(in);
    check(r.fused_class_index == 5, "6: OOD score does not perturb class fusion");
    check(tf.stats().ood_rejected, "6: OOD EWMA reject latched");
  }

  // ---- 7. bounded window (no unbounded growth) + dim switch reuse ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::LogitsEMA; c.alpha = 0.3f; c.max_window = 32;
    tf.configure(c);
    auto v = one_cls(12, 0);
    m25::TemporalFusionInput in;
    in.logits = v.data(); in.count = 12; in.frame_id = 1; in.timestamp_ns = 1000000;
    in.model_sha256 = SHA_A;
    for (int i = 0; i < 1000; ++i) {
      in.frame_id = 1 + i; in.timestamp_ns = 1000000ULL * (1 + i);
      tf.process(in);
    }
    check(tf.stats().total_frames == 1000, "7: 1000 frames processed");
    check(tf.stats().reset_count == 0, "7: no spurious resets over contiguous stream");
    // process a 24-dim frame -> dim reset, then continue 24-dim
    auto v24 = one_cls(24, 3);
    in.logits = v24.data(); in.count = 24; in.frame_id = 1001; in.timestamp_ns = 2000000000ULL;
    m25::TemporalFusionResult r = tf.process(in);
    check(r.reset_occurred && std::strcmp(r.reset_reason, "dim") == 0, "7: 12->24 dim reset");
    check(tf.stats().reset_by_reason[static_cast<int>(m25::ResetReason::DimChange)] == 1, "7: dim reset counted once");
  }

#if !defined(M25_SKIP_ALLOC_TEST)
  // ---- 8. zero steady-state heap allocation (release only) ----
  {
    m25::TemporalFusion tf;
    m25::FusionConfig c; c.enabled = true;
    c.algorithm = m25::FusionAlgorithm::EMA_KFrameConfirm;
    tf.configure(c);
    auto v = one_cls(24, 7);
    m25::TemporalFusionInput in;
    in.logits = v.data(); in.count = 24; in.frame_id = 1; in.timestamp_ns = 1000000;
    in.model_sha256 = SHA_A;
    tf.process(in);  // warm-up (one-time buffer sizing)
    g_allocs = 0;
    g_counting = true;
    for (int i = 0; i < 1000; ++i) {
      in.frame_id = 2 + i; in.timestamp_ns = 1000000ULL * (2 + i);
      tf.process(in);
    }
    g_counting = false;
    check(g_allocs == 0, "8: zero steady-state heap allocation (release)");
  }
#endif

  std::printf("== result: assertions=%d passed=%d failed=%d ==\n",
              g_pass + g_fail, g_pass, g_fail);
  return g_fail == 0 ? 0 : 1;
}
