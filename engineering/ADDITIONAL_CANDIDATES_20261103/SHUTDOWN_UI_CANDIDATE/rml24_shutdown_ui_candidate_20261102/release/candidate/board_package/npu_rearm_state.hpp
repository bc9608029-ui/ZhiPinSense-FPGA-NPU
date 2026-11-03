#pragma once

// npu_rearm_state.hpp — pure-logic, iCraft-free state machine encoding the
// ZG330 persistent-Session re-arm discipline (task 39e5 Gate 7 / Gate 9).
//
// The ZG330 NPU completion state is monotonic per Device and is only re-armed by
// Device Open or Device::reset(1).  A Session created + apply()ed ONCE over a
// persistent Device therefore returns the PREVIOUS frame's output on every
// forward after the first — the "fixed one-frame-delay" artifact that produced
// Gate 7's matched=3/240 (board diagnostic: sample1 repeated sample0's full
// logits; the whole confusion matrix shifted forward one frame; 2880/2880 finite,
// no NaN/Inf).
//
// The fix, proven on board in npu_realtime_v1 (12/12, delay shift 0/10):
//   * Device opened once, Session created + apply() once;
//   * FIRST frame: forward directly (freshly-initialized hardware, no reset);
//   * every frame AFTER the first: exactly one Device::reset(1) before forward,
//     and NEVER re-apply() after reset(1).
//
// This header keeps the *decision* logic free of any iCraft type so the host can
// unit-test it; NpuClassifier12 consults it on the board.  It must NOT be used to
// shift labels, skip comparisons, or weaken the 0.90 match-rate gate.

#include <cstdint>

namespace chain {

class NpuReArmState {
public:
    // Record one Session::apply().  Returns true iff this is the FIRST apply; a
    // second apply is a discipline violation that callers must fail on.
    bool record_apply() {
        ++apply_count_;
        return apply_count_ == 1;
    }

    // Advance to the next frame.  Returns true iff Device::reset(1) must run
    // before this frame's forward.  The first frame returns false (no reset).
    bool begin_frame() {
        const bool first = (frame_count_ == 0);
        ++frame_count_;
        if (!first) ++reset_count_;
        return !first;
    }

    // Record the outcome of this frame's Device::reset(1).  A failed reset
    // poisons the discipline (fail-closed).
    void record_reset(bool ok) {
        if (!ok) reset_failed_ = true;
    }

    // Discipline is clean iff: exactly one apply, no reset failure, and the
    // reset count is exactly frames-1 (the first frame carries no reset).  For a
    // full 240-frame Gate 7 run this means reset_count == 239.
    bool discipline_ok() const {
        if (apply_count_ != 1) return false;
        if (reset_failed_) return false;
        if (frame_count_ == 0) return reset_count_ == 0;
        return reset_count_ == frame_count_ - 1;
    }

    std::uint64_t frame_count() const { return frame_count_; }
    std::uint64_t reset_count() const { return reset_count_; }
    std::uint64_t apply_count() const { return apply_count_; }
    bool reset_failed() const { return reset_failed_; }

private:
    std::uint64_t frame_count_ = 0;
    std::uint64_t reset_count_ = 0;
    std::uint64_t apply_count_ = 0;
    bool reset_failed_ = false;
};

}  // namespace chain
