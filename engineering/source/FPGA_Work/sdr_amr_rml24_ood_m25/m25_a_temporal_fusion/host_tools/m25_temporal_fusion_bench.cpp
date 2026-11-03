// m25_temporal_fusion_bench.cpp -- M25-A unified CPU benchmark + memory check.
//
// Measures the steady-state cost of the TemporalFusion module on a 24-dim raw
// logits stream, with ONE fixed methodology:
//
//   stage 1 : disabled passthrough        (byte-identical single-frame output)
//   stage 2 : EMA_KFrameConfirm (default)  (window ring + EMA + confirm gate)
//
// Fixed parameters: 24 classes, N = 200000 frames, single class with a clear
// margin, release build -O2 (see build_m25_temporal_fusion_bench.sh).  Each
// stage warms up once (buffer sizing) before the timed loop.
//
// The zero-allocator check runs under the scoped global operator new counter:
// after the one-time buffer sizing, process() must perform zero heap allocations
// per frame (all buffers are preallocated and only indexed, never push_back).
//
// Build: host_tools/build_m25_temporal_fusion_bench.sh   Run: ./build/m25/m25_temporal_fusion_bench

#include "../sdr_adapter/m25_temporal_fusion.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#if !defined(M25_SKIP_ALLOC_TEST)
#include <new>
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

namespace {

const char* kSha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
constexpr int kCount = 24;

void print_env() {
  std::printf("== M25-A temporal fusion benchmark ==\n");
  std::printf("compiler      : g++ %d.%d.%d (__VERSION__ %s)\n", __GNUC__, __GNUC_MINOR__,
              __GNUC_PATCHLEVEL__, __VERSION__);
  std::printf("build flags   : -std=gnu++17 -O2 (see build_m25_temporal_fusion_bench.sh)\n");
  FILE* f = std::fopen("/proc/cpuinfo", "r");
  if (f) {
    char line[512];
    std::string model;
    while (std::fgets(line, sizeof(line), f)) {
      const std::string s = line;
      const std::size_t pos = s.find("model name");
      if (pos == std::string::npos) continue;
      const std::size_t colon = s.find(':', pos);
      if (colon == std::string::npos) continue;
      model = s.substr(colon + 1);
      model.erase(0, model.find_first_not_of(" \t"));
      model.erase(model.find_last_not_of(" \t\r\n") + 1);
      break;
    }
    std::fclose(f);
    if (!model.empty()) std::printf("CPU           : %s\n", model.c_str());
  }
  std::printf("parameters    : classes=%d\n", kCount);
}

// time N process() calls after one warm-up frame; returns mean us/frame.
double time_stream(m25::TemporalFusion& tf, std::uint64_t nframes) {
  std::vector<float> logits(kCount, 0.0f);
  logits[7] = 10.0f;  // clear class-7 peak
  m25::TemporalFusionInput in;
  in.logits = logits.data();
  in.count = kCount;
  in.model_sha256 = kSha;
  in.frame_id = 1;
  in.timestamp_ns = 1000000ULL;

  tf.process(in);  // warm-up: one-time buffer sizing
  const auto t0 = std::chrono::steady_clock::now();
  for (std::uint64_t i = 0; i < nframes; ++i) {
    in.frame_id = 2 + i;
    in.timestamp_ns = 1000000ULL * (2 + i);
    tf.process(in);
  }
  const auto t1 = std::chrono::steady_clock::now();
  return std::chrono::duration<double, std::micro>(t1 - t0).count() /
         static_cast<double>(nframes);
}

}  // namespace

int main(int argc, char** argv) {
  std::uint64_t nframes = 200000;
  if (argc > 1) nframes = static_cast<std::uint64_t>(std::strtoull(argv[1], nullptr, 10));
  if (nframes == 0) nframes = 200000;

  print_env();

  double us_off = 0.0, us_on = 0.0;

  {
    m25::TemporalFusion tf;  // unconfigured -> disabled
    us_off = time_stream(tf, nframes);
    std::printf("%-24s : %8.2f us/frame  (N=%llu)\n", "disabled passthrough", us_off,
                static_cast<unsigned long long>(nframes));
  }
  {
    m25::FusionConfig cfg;
    cfg.enabled = true;
    cfg.algorithm = m25::FusionAlgorithm::EMA_KFrameConfirm;  // default
    m25::TemporalFusion tf;
    tf.configure(cfg);
    us_on = time_stream(tf, nframes);
    std::printf("%-24s : %8.2f us/frame  (N=%llu)\n", "EMA_KFrameConfirm", us_on,
                static_cast<unsigned long long>(nframes));
  }

  std::printf("fusion overhead : %.2f us/frame (%.2fx over passthrough)\n",
              us_on - us_off, us_off > 0.0 ? us_on / us_off : 0.0);

#if !defined(M25_SKIP_ALLOC_TEST)
  // zero steady-state heap allocation check
  {
    m25::FusionConfig cfg;
    cfg.enabled = true;
    cfg.algorithm = m25::FusionAlgorithm::EMA_KFrameConfirm;
    m25::TemporalFusion tf;
    tf.configure(cfg);
    std::vector<float> logits(kCount, 0.0f);
    logits[7] = 10.0f;
    m25::TemporalFusionInput in;
    in.logits = logits.data(); in.count = kCount; in.model_sha256 = kSha;
    in.frame_id = 1; in.timestamp_ns = 1000000ULL;
    tf.process(in);  // warm-up

    g_allocs = 0;
    g_counting = true;
    for (int i = 0; i < 1000; ++i) {
      in.frame_id = 2 + i;
      in.timestamp_ns = 1000000ULL * (2 + i);
      tf.process(in);
    }
    g_counting = false;
    std::printf("zero per-frame alloc : %s (1000 steady-state frames)\n",
                g_allocs == 0 ? "PASS" : "FAIL");
    if (g_allocs != 0) {
      std::printf("  ! observed %ld heap allocation(s)\n", g_allocs);
      return 1;
    }
  }
#endif

  std::printf("== benchmark done ==\n");
  return 0;
}
