// M27 host test harness — offline CPU framework.  Exercises model registry + SHA
// binding, single-model residency, buffer pool ownership/bounds, scheduler routing,
// timeout, priority, generic 12/24-class fusion, model-switch clear, and
// UNKNOWN-vs-NO_SIGNAL distinction.  Compile (single line):
//   g++ -std=gnu++17 -O2 -Wall -Wextra -Werror -I../runtime -I../registry
//       -I../router -I../fusion test_m27.cpp -o test_m27
#include <cstdio>
#include <cstring>
#include <cmath>
#include <string>
#include "m27_contract.hpp"
#include "m27_model_registry.hpp"
#include "m27_buffer_pool.hpp"
#include "m27_npu_backend_stub.hpp"
#include "m27_runtime_stats.hpp"
#include "m27_conditional_router.hpp"
#include "m27_temporal_fusion.hpp"

using namespace m27;

static int g_pass = 0, g_fail = 0;

static void check(bool ok, const char* what) {
  if (ok) { g_pass++; }
  else { g_fail++; std::printf("FAIL: %s\n", what); }
}

// logits peaked at class k (value 3.0), others small noise
static void make_logits(float* v, int n, int k) {
  for (int i = 0; i < n; ++i) v[i] = (i == k) ? 3.0f : 0.1f;
}

// softmax of v into p (for probability-based fusion)
static void softmax(const float* v, int n, float* p) {
  float m = v[0];
  for (int i = 1; i < n; ++i) if (v[i] > m) m = v[i];
  float s = 0.0f;
  for (int i = 0; i < n; ++i) { p[i] = std::exp(v[i] - m); s += p[i]; }
  for (int i = 0; i < n; ++i) p[i] /= s;
}

static void test_registry_and_residency() {
  ModelRegistry reg;
  std::string why;
  check(reg.validate(&why), "registry.validate() default OK");

  // frozen 12-class SHA binding
  check(reg.slot(SlotId::A).model_sha256 == kFrozen12ClassSha256,
        "slot A SHA == frozen 12-class SHA");
  check((int)reg.slot(SlotId::A).label_order.size() == kClassCount12,
        "slot A has 12 labels");
  check(reg.slot(SlotId::A).enabled && !reg.slot(SlotId::A).experimental,
        "slot A enabled + production");

  // default-off experimentals
  check(!reg.slot(SlotId::B).enabled && reg.slot(SlotId::B).experimental,
        "slot B disabled + experimental");
  check(!reg.slot(SlotId::C).enabled && reg.slot(SlotId::C).experimental,
        "slot C disabled + experimental");
  check(!reg.slot(SlotId::D).enabled && reg.slot(SlotId::D).experimental,
        "slot D disabled + experimental");
  check(!reg.slot(SlotId::E).enabled && reg.slot(SlotId::E).experimental,
        "slot E disabled + experimental");

  // tampering with the frozen SHA fails validation
  ModelRegistry bad;
  bad.slot(SlotId::A).model_sha256 = std::string(64, '0');
  check(!bad.validate(&why), "tampered slot A SHA -> validate false");

  // single-model residency
  NpuBackendStub backend;
  check(reg.load_resident(backend) == NpuStatus::OK, "load_resident loads slot A");
  check(backend.loaded() && backend.resident_n() == 12,
        "resident model is 12-class");
  check(reg.loaded_slot() == SlotId::A, "loaded_slot()==A");

  // loading a *different* model while A is resident -> unsupported
  ModelSlot b = reg.slot(SlotId::B);
  b.enabled = true; b.model_name = "24class_stub"; b.model_sha256 = std::string(64, 'b');
  b.label_order.assign(24, "X");
  check(backend.load(b, b.model_sha256) ==
            NpuStatus::MULTI_MODEL_RESIDENCY_UNSUPPORTED,
        "second-model load -> MULTI_MODEL_RESIDENCY_UNSUPPORTED");

  // SHA mismatch fails closed
  NpuBackendStub backend2;
  ModelSlot a = reg.slot(SlotId::A);
  a.model_sha256 = std::string(64, 'c');
  check(backend2.load(a, kFrozen12ClassSha256) == NpuStatus::SHA_MISMATCH,
        "SHA mismatch -> SHA_MISMATCH");

  // infer before load -> NOT_LOADED; timeout -> TIMEOUT
  NpuBackendStub backend3;
  float x[12], y[12];
  make_logits(x, 12, 0);
  check(backend3.infer(x, 12, y) == NpuStatus::NOT_LOADED, "infer before load");
  check(reg.load_resident(backend3) == NpuStatus::OK, "load backend3");
  check(backend3.infer(x, 12, y, true) == NpuStatus::TIMEOUT, "infer timeout");
  check(backend3.infer(x, 12, y) == NpuStatus::OK && y[0] == 3.0f,
        "infer identity passthrough");
}

static void test_buffer_pool() {
  BufferPool pool;
  check(pool.init(3, 16), "pool.init");
  check(pool.count() == 3 && pool.slot_bytes() == 16, "pool dims");

  int a = pool.acquire(1);
  int b = pool.acquire(2);
  int c = pool.acquire(3);
  check(a == 0 && b == 1 && c == 2, "acquire 3 slots");
  check(pool.acquire(4) == -1, "acquire 4th -> exhausted (-1)");

  // bounds + ownership
  check(!pool.release(3, 1), "release out-of-range -> false");
  check(!pool.release(0, 2), "release wrong owner -> false");
  check(pool.release(0, 1), "release correct owner");
  check(!pool.release(0, 1), "double release -> false");

  // reuse
  int d = pool.acquire(5);
  check(d == 0, "freed slot reused");
  check(pool.buffer(0, 5) != nullptr && pool.buffer(0, 1) == nullptr,
        "buffer ownership enforced");
  check(pool.owner(0) == 5, "owner id reported");
}

static void test_router() {
  ConditionalRouter router;
  RouterConfig cfg;
  router.configure(cfg);
  RuntimeStats stats;

  float logits[12]; make_logits(logits, 12, 0);

  RouteInput hi; hi.n = 12; hi.raw_logits = logits;
  hi.margin = 3.0f; hi.entropy = 0.1f; hi.ood_score = 0.0f;
  hi.impairment_severe = false; hi.error = false; hi.stable_frames = 0;
  check(router.route(hi, stats, 670).action == RouteAction::DIRECT,
        "high margin -> DIRECT");

  RouteInput low = hi; low.margin = 0.1f;
  check(router.route(low, stats, 670).action == RouteAction::EXPERT,
        "low margin -> EXPERT");

  RouteInput ent = hi; ent.entropy = 2.5f;
  check(router.route(ent, stats, 670).action == RouteAction::EXPERT,
        "high entropy -> EXPERT");

  RouteInput ood = hi; ood.ood_score = 0.9f;
  check(router.route(ood, stats, 670).action == RouteAction::OOD,
        "ood_suspect -> OOD");

  RouteInput imp = hi; imp.impairment_severe = true;
  check(router.route(imp, stats, 670).action == RouteAction::CHANNEL,
        "severe impairment -> CHANNEL");

  RouteInput err = hi; err.error = true;
  check(router.route(err, stats, 670).action == RouteAction::ERROR,
        "NPU error -> ERROR fail-closed");

  // stable suppression: after stability_frames, expert calls are throttled
  int expert_before = (int)stats.model[(int)SlotId::C].calls;
  RouteInput st = low; st.stable_frames = cfg.stability_frames;
  RouteDecision d = router.route(st, stats, 670);
  check(d.action == RouteAction::DIRECT, "stable -> expert suppressed (DIRECT)");
  check((int)stats.model[(int)SlotId::C].calls == expert_before,
        "suppressed frame does not call expert");
  check(stats.windows_processed == 7, "stats count windows");

  // stats file write
  stats.record_latency(500); stats.record_latency(700); stats.record_latency(900);
  check(stats.write_file("/tmp/m27_stats.txt"), "stats write_file");
}

static void test_fusion_12() {
  FusionConfig cfg; cfg.n = 12; cfg.algo = FusionAlgorithm::LogitsMean;
  cfg.max_window = 8; cfg.max_response_frames = 3;

  float logits[12], prob[12];
  make_logits(logits, 12, 4);
  softmax(logits, 12, prob);

  FusionInput in;
  in.frame_id = 0; in.timestamp_ns = 0; in.presence = PresenceState::SIGNAL_PRESENT;
  in.n = 12; in.raw_logits = logits; in.probabilities = prob;
  in.ood_score = 0.0f; in.snr = 20.0f; in.signal_power = 1.0f;
  in.model_sha = "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c";

  {
    TemporalFusion f; f.configure(cfg);
    for (int i = 0; i < 5; ++i) {
      in.frame_id = (std::uint64_t)i; in.timestamp_ns = (std::uint64_t)i * 1000;
      FusionResult r = f.process(in);
      check(r.valid && r.fused_class == 4, "fusion n=12 -> class 4");
    }
  }

  // dimension mismatch -> fail-closed
  {
    FusionConfig cfg24; cfg24.n = 24;
    TemporalFusion f24; f24.configure(cfg24);
    FusionResult rm = f24.process(in);   // in.n == 12 != 24
    check(!rm.valid && rm.reset_reason &&
          std::strcmp(rm.reset_reason, "dimension_mismatch") == 0,
          "dimension mismatch -> fail-closed");
  }

  // model switch clears state (fresh instance: establish sha A, then sha B)
  {
    TemporalFusion fs; fs.configure(cfg);
    FusionInput s1 = in; s1.model_sha =
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    s1.frame_id = 0; s1.timestamp_ns = 0;
    fs.process(s1);
    FusionInput s2 = in; s2.model_sha =
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    s2.frame_id = 1; s2.timestamp_ns = 1000;
    FusionResult rsw = fs.process(s2);
    check(rsw.reset_occurred &&
          std::strcmp(rsw.reset_reason, "model_switch") == 0,
          "model switch -> reset");
  }

  // UNKNOWN vs NO_SIGNAL distinction (fresh instance)
  {
    TemporalFusion fp; fp.configure(cfg);
    FusionInput nu = in; nu.presence = PresenceState::UNKNOWN; nu.model_sha = nullptr;
    check(fp.process(nu).fused_class == kFusedUnknown, "UNKNOWN passthrough -> -1");
    FusionInput ns = in; ns.presence = PresenceState::NO_SIGNAL;
    check(fp.process(ns).fused_class == kFusedNoSignal, "NO_SIGNAL passthrough -> -2");
  }

  // sudden change: switch to class 9, must flip within max_response_frames
  {
    TemporalFusion fc; fc.configure(cfg);
    FusionInput base = in; base.model_sha = nullptr;   // class 4
    for (int i = 0; i < 6; ++i) {
      base.frame_id = (std::uint64_t)i; base.timestamp_ns = (std::uint64_t)i * 1000;
      fc.process(base);
    }
    float logits9[12]; make_logits(logits9, 12, 9);
    softmax(logits9, 12, prob);
    FusionInput sw = base; sw.raw_logits = logits9;
    bool flipped = false;
    for (int i = 0; i < 8; ++i) {
      sw.frame_id = 100 + (std::uint64_t)i;
      sw.timestamp_ns = 100000 + (std::uint64_t)i * 1000;
      FusionResult r = fc.process(sw);
      if (r.valid && r.fused_class == 9) { flipped = true; break; }
    }
    check(flipped, "sudden change flips within bounded frames");
  }
}

static void test_fusion_24() {
  FusionConfig cfg; cfg.n = 24; cfg.algo = FusionAlgorithm::MajorityVote;
  cfg.max_window = 8; cfg.max_response_frames = 3;
  TemporalFusion f; f.configure(cfg);

  float logits[24], prob[24];
  make_logits(logits, 24, 20);
  softmax(logits, 24, prob);

  FusionInput in;
  in.frame_id = 0; in.timestamp_ns = 0; in.presence = PresenceState::SIGNAL_PRESENT;
  in.n = 24; in.raw_logits = logits; in.probabilities = prob;
  in.ood_score = 0.0f; in.snr = 15.0f; in.signal_power = 0.5f; in.model_sha = nullptr;

  for (int i = 0; i < 6; ++i) {
    in.frame_id = (std::uint64_t)i; in.timestamp_ns = (std::uint64_t)i * 1000;
    FusionResult r = f.process(in);
    check(r.valid && r.fused_class == 20, "fusion n=24 (majority) -> class 20");
  }
}

static void test_fusion_algorithms() {
  // Each of the 7 algorithms must converge to the same peaked class.
  const int algos[7] = {0, 1, 2, 3, 4, 5, 6};
  for (int ai = 0; ai < 7; ++ai) {
    FusionConfig cfg; cfg.n = 12; cfg.algo = (FusionAlgorithm)algos[ai];
    cfg.max_window = 8; cfg.max_response_frames = 3;
    TemporalFusion f; f.configure(cfg);

    float logits[12], prob[12];
    make_logits(logits, 12, 7);
    softmax(logits, 12, prob);

    FusionInput in;
    in.frame_id = 0; in.timestamp_ns = 0; in.presence = PresenceState::SIGNAL_PRESENT;
    in.n = 12; in.raw_logits = logits; in.probabilities = prob;
    in.ood_score = 0.0f; in.snr = 20.0f; in.signal_power = 1.0f; in.model_sha = nullptr;

    bool ok = true;
    for (int i = 0; i < 10 && ok; ++i) {
      in.frame_id = (std::uint64_t)i; in.timestamp_ns = (std::uint64_t)i * 1000;
      FusionResult r = f.process(in);
      if (i >= 3 && (!r.valid || r.fused_class != 7)) ok = false;
    }
    char msg[64];
    std::snprintf(msg, sizeof(msg), "algorithm %d converges to class 7", algos[ai]);
    check(ok, msg);
  }
}

int main() {
  test_registry_and_residency();
  test_buffer_pool();
  test_router();
  test_fusion_12();
  test_fusion_24();
  test_fusion_algorithms();

  std::printf("== result: assertions=%d passed=%d failed=%d ==\n",
              g_pass + g_fail, g_pass, g_fail);
  return g_fail == 0 ? 0 : 1;
}
