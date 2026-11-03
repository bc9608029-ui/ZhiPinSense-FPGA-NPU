#pragma once

// live_rx_gating.hpp -- M29 Phase F5 Task C: presence-gated classification
// policy for the --phase=live-rx external RX mode.
//
// The board's live-rx loop runs the 24-class NPU ONLY while SignalPresence
// reports SIGNAL_PRESENT; on NO_SIGNAL / ACQUIRING / SIGNAL_LOST / INVALID it
// emits only the periodic state heartbeat (no NPU call, no result frame).  This
// header holds that decision plus the LIVE_RX_DIAG counters so the policy is
// host-testable without the NPU / libiio:
//
//   classify_now(state) -- true iff state == SIGNAL_PRESENT (NPU should run)
//   Gating              -- wraps sdr::SignalPresence + tracks the counters
//                          (accepted_frames / npu_runs / result_sent /
//                          result_dropped).
//
// The board loop (board_gate9_full_chain_rml23.cpp::run_live_rx_phase) drives one
// Gating per run; the host test (host_tests/test_live_rx_gating.cpp) feeds
// synthetic measurement vectors and asserts the presence -> classify ->
// presence-gone -> NO_SIGNAL transition plus the counter invariants.
//
// iCraft-free, libiio-free, header-only.

#include "../sdr_adapter/signal_presence.hpp"

#include <cstdint>

namespace live_rx {

// Should the NPU run for this presence state?  Only a confirmed SIGNAL_PRESENT
// frame is classified; every other state keeps the loop in the NO-SIGNAL
// heartbeat path (no NPU call, no result frame).
inline bool classify_now(sdr::PresenceState s) {
    return s == sdr::PresenceState::SignalPresent;
}

// LIVE_RX_DIAG counters (reported every 100 frames by the board loop).
struct GatingCounters {
    std::uint64_t accepted_frames = 0;  // frames that reached SIGNAL_PRESENT
    std::uint64_t npu_runs = 0;         // NPU inference calls made
    std::uint64_t result_sent = 0;      // rml23-chain-v2 result frames emitted
    std::uint64_t result_dropped = 0;   // accepted frames whose merge fail-closed
};

class Gating {
public:
    explicit Gating(const sdr::PresenceConfig& cfg = {}) : presence_(cfg) {}

    // Feed one frame's presence evidence; returns the resulting presence state.
    sdr::PresenceState update(const sdr::PresenceInput& in) {
        return presence_.update(in);
    }

    sdr::PresenceState state() const { return presence_.state(); }

    // Record one accepted (SIGNAL_PRESENT) frame: the caller will run one NPU
    // inference for it, so accepted_frames and npu_runs advance together.
    void record_accepted() { ++counters_.accepted_frames; ++counters_.npu_runs; }

    // Record the merge outcome of an accepted frame: a clean 24->23 merge emits a
    // result, a fail-closed (non-finite logit) merge drops it.
    void record_merge(bool merged_ok) {
        if (merged_ok) ++counters_.result_sent;
        else ++counters_.result_dropped;
    }

    const GatingCounters& counters() const { return counters_; }

    // Counter invariants the run must uphold (asserted by the host test and the
    // board's final gate): every accepted frame runs the NPU exactly once, and
    // every accepted frame is either sent or dropped exactly once.
    bool invariants_ok() const {
        return counters_.npu_runs == counters_.accepted_frames &&
               counters_.result_sent + counters_.result_dropped ==
                   counters_.accepted_frames;
    }

private:
    sdr::SignalPresence presence_;
    GatingCounters counters_;
};

}  // namespace live_rx
