// M27 runtime statistics (spec §九): per-model call/inference/DMA counters, queue
// length, timeouts, switches, busy time, CPU overhead, windows/sec, p50/p95/p99
// latency, dropped/backlog frames.  Written to a file, never to per-frame serial.
//
// No hardware counters exist on ZG330 (audit §10), so `busy_time` is an *estimate*
// derived from observed inference durations — the contract forbids labelling it as a
// measured NPU utilization.  header-only, namespace m27.
#ifndef M27_RUNTIME_STATS_HPP
#define M27_RUNTIME_STATS_HPP

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>
#include <algorithm>

namespace m27 {

struct ModelStats {
  std::uint64_t calls = 0;
  std::uint64_t inference_us_total = 0;
  std::uint64_t dma_us_total = 0;
  std::uint64_t timeouts = 0;
  std::uint64_t switches = 0;
};

struct RuntimeStats {
  std::uint64_t windows_processed = 0;
  std::uint64_t dropped_frames = 0;
  std::uint64_t backlog_max = 0;
  std::uint64_t cpu_overhead_us_total = 0;
  std::uint64_t busy_us_total = 0;      // estimate: sum of inference durations
  std::uint64_t queue_len_max = 0;

  // per-slot counters, indexed by SlotId (0..4)
  ModelStats model[5];

  // latency histogram reservoir (bounded, fixed capacity)
  static constexpr std::size_t kLatencyCap = 4096;
  std::vector<std::uint32_t> latency_us;

  void record_latency(std::uint32_t us) {
    if (latency_us.size() < kLatencyCap) latency_us.push_back(us);
  }

  // p50/p95/p99 over the recorded reservoir; -1 if empty.
  std::uint32_t percentile(double q) const {
    if (latency_us.empty()) return 0;
    std::vector<std::uint32_t> s = latency_us;
    std::sort(s.begin(), s.end());
    std::size_t idx = static_cast<std::size_t>(q * (s.size() - 1));
    return s[idx];
  }

  // Serialize the counters to `path` (plain text).  Returns false on open failure.
  bool write_file(const std::string& path) const {
    FILE* f = std::fopen(path.c_str(), "w");
    if (!f) return false;
    std::fprintf(f, "windows_processed=%llu\n",
                 (unsigned long long)windows_processed);
    std::fprintf(f, "dropped_frames=%llu\n", (unsigned long long)dropped_frames);
    std::fprintf(f, "backlog_max=%llu\n", (unsigned long long)backlog_max);
    std::fprintf(f, "queue_len_max=%llu\n", (unsigned long long)queue_len_max);
    std::fprintf(f, "cpu_overhead_us_total=%llu\n",
                 (unsigned long long)cpu_overhead_us_total);
    std::fprintf(f, "busy_us_total_estimated=%llu\n",
                 (unsigned long long)busy_us_total);
    std::fprintf(f, "p50_us=%u p95_us=%u p99_us=%u\n", percentile(0.50),
                 percentile(0.95), percentile(0.99));
    for (int i = 0; i < 5; ++i) {
      const ModelStats& m = model[i];
      std::fprintf(f,
          "slot_%c calls=%llu infer_us=%llu dma_us=%llu timeouts=%llu switches=%llu\n",
          "ABCDE"[i], (unsigned long long)m.calls,
          (unsigned long long)m.inference_us_total,
          (unsigned long long)m.dma_us_total, (unsigned long long)m.timeouts,
          (unsigned long long)m.switches);
    }
    std::fclose(f);
    return true;
  }
};

}  // namespace m27

#endif  // M27_RUNTIME_STATS_HPP
