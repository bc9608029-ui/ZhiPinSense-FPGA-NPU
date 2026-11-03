#pragma once

// Frame-sequence integrity monitor for the non-model system layer.
//
// Detects, per IQ stream, the anomalies the contest checklist requires:
//   overflow       -- producer-flagged (iq::Frame::overflow)
//   dropped        -- producer-flagged (iq::Frame::dropped) PLUS inferred from
//                     a frame_id gap
//   duplicate      -- same frame_id observed twice in a row
//   reorder        -- frame_id went backwards (covers out-of-order repeats)
//   discontinuity  -- producer-flagged (iq::Frame::discontinuity)
//   short_frame    -- fewer than 1024 samples
//
// Definition of terms (keep in sync with REPORT.md section E):
//   * `duplicate` = consecutive repeated frame_id (id == last).
//   * `reorder`   = any id < last (an out-of-order repeat therefore counts as
//                   reorder, not duplicate).
//   * `gap`       = a forward jump of more than 1 => (id - last - 1) frames are
//                   inferred dropped, added to `dropped` and `gap`.
//
// frame_id is treated as a monotonic counter WITHOUT wrap.  FileIqSource and
// SyntheticIqSource satisfy this by construction.  SDR hardware-counter wrap is
// TBD (see contracts/sampling_and_iq_contract.md) and is deliberately not
// handled here -- wrapping a raw hardware counter would require knowing its
// width, which is device-specific and unspecified.

#include "iq_frame.hpp"

#include <cstdint>

namespace iq {

struct SequenceStats {
    std::uint64_t total = 0;          // frames observed
    std::uint64_t overflow = 0;       // producer-flagged
    std::uint64_t dropped = 0;        // producer-flagged + inferred (gap)
    std::uint64_t duplicate = 0;      // consecutive repeated id
    std::uint64_t reorder = 0;        // id went backwards
    std::uint64_t discontinuity = 0;  // producer-flagged
    std::uint64_t gap = 0;            // inferred drops from id jumps
    std::uint64_t short_frame = 0;    // fewer than 1024 samples
    std::int64_t last_frame_id = -1;
    bool seen = false;
};

class SequenceMonitor {
public:
    void observe(const Frame& f) {
        ++s_.total;
        if (f.overflow) ++s_.overflow;
        if (f.dropped) ++s_.dropped;
        if (f.discontinuity) ++s_.discontinuity;
        if (f.short_frame) ++s_.short_frame;

        const std::int64_t id = static_cast<std::int64_t>(f.frame_id);
        if (!s_.seen) {
            s_.seen = true;
            s_.last_frame_id = id;
            return;
        }
        if (id == s_.last_frame_id) {
            ++s_.duplicate;
        } else if (id < s_.last_frame_id) {
            ++s_.reorder;
        } else {
            const std::int64_t jump = id - s_.last_frame_id - 1;
            if (jump > 0) {
                s_.gap += static_cast<std::uint64_t>(jump);
                s_.dropped += static_cast<std::uint64_t>(jump);
            }
            s_.last_frame_id = id;
        }
    }

    // True when no anomaly of any kind has been seen.
    bool healthy() const {
        return s_.duplicate == 0 && s_.reorder == 0 && s_.gap == 0 &&
               s_.overflow == 0 && s_.dropped == 0 && s_.discontinuity == 0 &&
               s_.short_frame == 0;
    }

    const SequenceStats& stats() const { return s_; }
    void reset() { s_ = SequenceStats(); }

private:
    SequenceStats s_;
};

}  // namespace iq
