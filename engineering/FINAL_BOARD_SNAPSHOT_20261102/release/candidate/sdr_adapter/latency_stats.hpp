#pragma once

// latency_stats.hpp — fixed-buffer per-stage latency statistics for the M22
// runtime baseline (task 39e5 M22 §三/§四).
//
// The existing perf_stats.hpp tracks count / avg / min / max only.  The M22
// baseline additionally requires mean / P50 / P95 / P99 / max over >= 10000
// frames, so this header adds percentile tracking over a FIXED-CAPACITY ring
// buffer.  The hot-path `record()` path never allocates: it writes one double
// into a preallocated ring and updates running min/max/sum in place.  The
// percentile computation happens exactly ONCE at summary time (it copies the
// ring to a temporary and sorts), which is outside the per-frame loop.
//
// Fixed stage set (indexed, no std::map / no std::string in the hot path) so a
// frame records 9 timestamps with zero heap traffic.  iCraft-free and header-only.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>

namespace m22 {

// One stage's fixed-capacity ring of microsecond samples.
class PercentileStats {
public:
    explicit PercentileStats(std::size_t cap = kDefaultCapacity) : cap_(cap) {
        ring_.resize(cap_, 0.0);
    }

    void record(double us) {
        if (count_ == 0) {
            min_ = us;
            max_ = us;
        } else {
            if (us < min_) min_ = us;
            if (us > max_) max_ = us;
        }
        sum_ += us;
        if (count_ < cap_) {
            ring_[count_] = us;
            ++count_;
        } else {
            // Ring is full: overwrite the oldest sample.  min/max are kept as
            // running extrema over ALL observations, so they remain exact even
            // though the ring only retains the most recent `cap_` samples.
            ring_[head_] = us;
            head_ = (head_ + 1) % cap_;
        }
    }

    std::uint64_t count() const { return count_; }
    double min_us() const { return count_ ? min_ : 0.0; }
    double max_us() const { return count_ ? max_ : 0.0; }
    double mean_us() const { return count_ ? sum_ / static_cast<double>(count_) : 0.0; }

    // q in [0,1].  Uses the linear-interpolation (nearest-rank variant) over the
    // retained samples; empty => 0.0.  Call ONLY at summary time (allocates a
    // temporary copy of the retained samples).
    double percentile(double q) const {
        if (count_ == 0) return 0.0;
        const std::size_t n = count_;
        std::vector<double> v(ring_.begin(), ring_.begin() + static_cast<std::ptrdiff_t>(n));
        std::sort(v.begin(), v.end());
        const double rank = q * static_cast<double>(n - 1);
        const std::size_t lo = static_cast<std::size_t>(std::floor(rank));
        const std::size_t hi = static_cast<std::size_t>(std::ceil(rank));
        if (lo == hi) return v[lo];
        const double frac = rank - static_cast<double>(lo);
        return v[lo] * (1.0 - frac) + v[hi] * frac;
    }

    void reset() {
        count_ = 0;
        head_ = 0;
        sum_ = 0.0;
        min_ = 0.0;
        max_ = 0.0;
    }

private:
    static constexpr std::size_t kDefaultCapacity = 1 << 16;  // 65536 retained samples
    std::size_t cap_;
    std::vector<double> ring_;
    std::size_t count_ = 0;
    std::size_t head_ = 0;
    double sum_ = 0.0;
    double min_ = 0.0;
    double max_ = 0.0;
};

// Fixed stage names (single source of truth; order == StageId index).
enum class StageId : int {
    DeviceOpen = 0,
    ModelLoad,
    RfConfig,
    RxRefill,
    Preprocess,
    NpuInfer,
    Postprocess,
    UiSubmit,
    FrameTotal,
    Count,
};

inline const char* stage_name(StageId id) {
    switch (id) {
        case StageId::DeviceOpen:  return "device_open";
        case StageId::ModelLoad:   return "model_load";
        case StageId::RfConfig:    return "rf_config";
        case StageId::RxRefill:    return "rx_refill";
        case StageId::Preprocess:  return "preprocess";
        case StageId::NpuInfer:    return "npu_infer";
        case StageId::Postprocess: return "postprocess";
        case StageId::UiSubmit:    return "ui_submit";
        case StageId::FrameTotal:  return "frame_total";
        default:                   return "unknown";
    }
}

constexpr int kStageCount = static_cast<int>(StageId::Count);

// All nine stage accumulators, indexed, allocation-free in record().
class StageTiming {
public:
    explicit StageTiming(std::size_t cap = 1 << 16) {
        for (int i = 0; i < kStageCount; ++i)
            stages_[i] = PercentileStats(cap);
    }

    void record(StageId id, double us) { stages_[static_cast<int>(id)].record(us); }
    const PercentileStats& stage(StageId id) const { return stages_[static_cast<int>(id)]; }

    // RAII stopwatch (records elapsed microseconds into a fixed stage).
    class Timer {
    public:
        Timer(StageTiming& owner, StageId id)
            : owner_(owner), id_(id),
              t0_(std::chrono::steady_clock::now()) {}
        Timer(const Timer&) = delete;
        Timer& operator=(const Timer&) = delete;
        ~Timer() {
            const double us = std::chrono::duration<double, std::micro>(
                                  std::chrono::steady_clock::now() - t0_).count();
            owner_.record(id_, us);
        }

    private:
        StageTiming& owner_;
        StageId id_;
        std::chrono::steady_clock::time_point t0_;
    };

    // Deterministic JSON summary: one object with one sub-object per stage.
    // Emitted once at the end of a run (or at each periodic summary), never per
    // frame.  Allocate-safe (outside the hot path).
    std::string json() const {
        std::string out = "{";
        for (int i = 0; i < kStageCount; ++i) {
            if (i) out += ',';
            const PercentileStats& s = stages_[i];
            out += "\"";
            out += stage_name(static_cast<StageId>(i));
            out += "\":{\"count\":";
            out += std::to_string(s.count());
            out += ",\"mean_us\":";
            out += num(s.mean_us());
            out += ",\"p50_us\":";
            out += num(s.percentile(0.50));
            out += ",\"p95_us\":";
            out += num(s.percentile(0.95));
            out += ",\"p99_us\":";
            out += num(s.percentile(0.99));
            out += ",\"max_us\":";
            out += num(s.max_us());
            out += ",\"min_us\":";
            out += num(s.min_us());
            out += '}';
        }
        out += '}';
        return out;
    }

private:
    static std::string num(double v) {
        char b[40];
        std::snprintf(b, sizeof(b), "%.3f", v);
        return std::string(b);
    }

    PercentileStats stages_[kStageCount];
};

}  // namespace m22
