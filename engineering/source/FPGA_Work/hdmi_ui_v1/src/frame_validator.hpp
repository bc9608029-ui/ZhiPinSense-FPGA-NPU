#pragma once
// Consumer-side integrity checks.  Mirrors iq::SequenceMonitor (read-only) and
// extends it with the UI-level staleness window.  Qt-free so the host tests and
// the Python mirror in tests/ exercise the same logic.
//
// Reused iq::SequenceMonitor semantics (sequence_monitor.hpp):
//   duplicate = frame_id == last_frame_id
//   reorder   = frame_id <  last_frame_id
//   gap       = frame_id >  last_frame_id + 1  -> (jump - 1) dropped frames

#include <cstdint>

#include "contracts/result_frame.hpp"

namespace hdmiui {

struct SequenceStats {
    std::uint64_t seen = 0;
    std::uint64_t duplicate = 0;
    std::uint64_t reorder = 0;
    std::uint64_t gap = 0;        // number of forward jumps observed
    std::uint64_t dropped = 0;    // sum of inferred drops across gaps
    std::uint64_t last_frame_id = 0;
    bool have_last = false;
};

class FrameSequenceMonitor {
public:
    void observe(std::uint64_t frame_id) {
        if (!stats_.have_last) {
            stats_.have_last = true;
            stats_.last_frame_id = frame_id;
            stats_.seen = 1;
            return;
        }
        stats_.seen++;
        if (frame_id == stats_.last_frame_id) {
            stats_.duplicate++;
        } else if (frame_id < stats_.last_frame_id) {
            stats_.reorder++;
            stats_.last_frame_id = frame_id;
        } else {
            const std::uint64_t jump = frame_id - stats_.last_frame_id;
            if (jump > 1) {
                stats_.gap++;
                stats_.dropped += jump - 1;
            }
            stats_.last_frame_id = frame_id;
        }
    }

    const SequenceStats& stats() const { return stats_; }
    void reset() { stats_ = SequenceStats{}; }

private:
    SequenceStats stats_{};
};

// A frame older than timeout_ns is "stale": the UI dims/clears it.
class StaleDetector {
public:
    explicit StaleDetector(std::uint64_t timeout_ns) : timeout_ns_(timeout_ns) {}

    bool is_stale(std::uint64_t timestamp_ns, std::uint64_t now_ns) const {
        return hdmiui::is_stale(timestamp_ns, now_ns, timeout_ns_);
    }

    std::uint64_t timeout_ns() const { return timeout_ns_; }
    void set_timeout_ns(std::uint64_t ns) { timeout_ns_ = ns; }

private:
    std::uint64_t timeout_ns_;
};

}  // namespace hdmiui
