#pragma once

// Staged performance statistics for the non-model system layer.
//
// The contest checklist requires per-stage latency: SDR capture, resample /
// framing, PL-DDR transfer, FPGA processing, NPU inference, and end-to-end.
// Each stage is a named key; a RAII PerfStats::Timer records wall-clock time on
// scope exit, and PerfStats::summary() emits one deterministic line.
//
// iCraft-free (uses only <chrono>), so it unit-tests on the host and reuses
// unchanged on the board.

#include <chrono>
#include <cstdint>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>

namespace perf {

// Fixed stage names (single source of truth for the whole pipeline).
struct Stage {
    static constexpr const char* kSdrCapture = "sdr_capture";
    static constexpr const char* kResampleFrame = "resample_frame";
    static constexpr const char* kPlddrTransfer = "plddr_transfer";
    static constexpr const char* kFpgaProcess = "fpga_process";
    static constexpr const char* kNpuInfer = "npu_infer";
    static constexpr const char* kEndToEnd = "end_to_end";
};

struct StageStats {
    std::uint64_t count = 0;
    double total_us = 0.0;
    double min_us = 0.0;
    double max_us = 0.0;
    bool has_min = false;
};

class PerfStats {
public:
    // Record one observation (microseconds) for a named stage.
    void record(const char* stage, double us) {
        StageStats& s = m_[stage];
        ++s.count;
        s.total_us += us;
        if (!s.has_min || us < s.min_us) s.min_us = us;
        if (!s.has_min || us > s.max_us) s.max_us = us;
        s.has_min = true;
    }

    // RAII stopwatch: records its elapsed time on destruction.
    class Timer {
    public:
        Timer(PerfStats& owner, const char* stage)
            : owner_(owner), stage_(stage),
              t0_(std::chrono::steady_clock::now()) {}
        Timer(const Timer&) = delete;
        Timer& operator=(const Timer&) = delete;
        ~Timer() {
            const double us = std::chrono::duration<double, std::micro>(
                                  std::chrono::steady_clock::now() - t0_)
                                  .count();
            owner_.record(stage_, us);
        }

    private:
        PerfStats& owner_;
        const char* stage_;
        std::chrono::steady_clock::time_point t0_;
    };

    double avg_us(const char* stage) const {
        auto it = m_.find(stage);
        if (it == m_.end() || it->second.count == 0) return 0.0;
        return it->second.total_us / static_cast<double>(it->second.count);
    }

    std::uint64_t count(const char* stage) const {
        auto it = m_.find(stage);
        return it == m_.end() ? 0 : it->second.count;
    }

    void reset() { m_.clear(); }

    // One line, deterministic stage order, e.g.
    //   sdr_capture cnt=10 avg_us=.. min_us=.. max_us=.. resample_frame ...
    std::string summary() const {
        static const char* order[] = {
            Stage::kSdrCapture, Stage::kResampleFrame, Stage::kPlddrTransfer,
            Stage::kFpgaProcess, Stage::kNpuInfer, Stage::kEndToEnd};
        std::ostringstream os;
        os << std::fixed << std::setprecision(3);
        bool first = true;
        for (const char* s : order) {
            auto it = m_.find(s);
            if (it == m_.end()) continue;
            if (!first) os << ' ';
            first = false;
            const double avg =
                it->second.count ? it->second.total_us /
                                       static_cast<double>(it->second.count)
                                 : 0.0;
            os << s << " cnt=" << it->second.count << " avg_us=" << avg
               << " min_us=" << it->second.min_us << " max_us=" << it->second.max_us;
        }
        return os.str();
    }

private:
    std::map<std::string, StageStats> m_;
};

}  // namespace perf
