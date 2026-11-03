#pragma once

// delay_gate.hpp — pure-logic, iCraft-free "fixed one-frame delay" gate for the
// twelve-class NPU result stream (task 39e5 Gate 7).
//
// The ZG330 fixed-one-frame-delay artifact (now fixed by the persistent-Session
// re-arm in npu_classifier.hpp / npu_rearm_state.hpp) has a STRONG signature:
//   * the per-frame prediction is actually the PREVIOUS frame's expected class,
//   * so `delay_shift_match` (pred == previous ref, only counted where two
//     adjacent inputs have DIFFERENT expected classes) climbs to nearly the whole
//     `delay_shift_compared` set -- ~239/239 for the old bug.
//
// A CLEAN run can still score a SMALL number of delay-shift collisions by pure
// chance when a frame's argmax happens to equal the previous frame's class.  The
// board-proven re-arm result was exactly this: delay_shift_match = 10/236
// (0.04237) alongside a 227/240 aligned match.  Requiring `delay_shift_match == 0`
// therefore produced a false positive.  The correct gate is the STRONG signature:
//
//   delay_shift_rate  = compared>0 ? shift_match/compared : 0
//   delay_detected    = compared>0 && shift_rate>=0.90 && shift_rate>aligned_rate
//
// (frozen per task 39e5 §三).  The `shift_rate > aligned_rate` tiebreak keeps the
// gate silent when a shifted stream is the ONLY explanation (the true one-frame
// delay), while tolerating rare accidental collisions on a high-accuracy run.
//
// This header keeps the *decision* logic free of iCraft and libiio so the host can
// unit-test it; board_gate7_12class_npu.cpp consults it on the board.  It MUST NOT
// be used to move labels, skip comparisons, or weaken the 0.90 match-rate gate.

#include <cstddef>
#include <cstdint>

namespace chain {

class DelayGate {
public:
    // Feed one frame's (prediction, expected).  Every frame is fed (the first
    // frame only seeds prev_ref_ -- it is NOT skipped and NOT shifted).  aligned_
    // counts pred==ref on the SAME frame; shift_match_/shift_compared_ count the
    // stale-output signature (pred == previous ref) only where ref changed.
    void on_frame(int pred, int ref) {
        ++total_;
        if (pred == ref) ++aligned_;
        if (have_prev_) {
            if (ref != prev_ref_) {
                ++shift_compared_;
                if (pred == prev_ref_) ++shift_match_;
            }
        }
        prev_ref_ = ref;
        have_prev_ = true;
    }

    std::size_t total() const { return total_; }
    std::size_t aligned_match() const { return aligned_; }
    std::size_t delay_shift_match() const { return shift_match_; }
    std::size_t delay_shift_compared() const { return shift_compared_; }

    // aligned_match / total (0 when total==0).
    double aligned_match_rate() const {
        return total_ == 0 ? 0.0
                           : static_cast<double>(aligned_) /
                                 static_cast<double>(total_);
    }

    // shift_match / shift_compared (0 when compared==0).  Frozen formula.
    double delay_shift_rate() const {
        return shift_compared_ == 0
                   ? 0.0
                   : static_cast<double>(shift_match_) /
                         static_cast<double>(shift_compared_);
    }

    // Strong fixed-one-frame-delay signature.  Frozen formula.
    bool delay_detected() const {
        if (shift_compared_ == 0) return false;
        const double sr = delay_shift_rate();
        const double ar = aligned_match_rate();
        return sr >= 0.90 && sr > ar;
    }

private:
    std::size_t total_ = 0;
    std::size_t aligned_ = 0;
    std::size_t shift_match_ = 0;
    std::size_t shift_compared_ = 0;
    int prev_ref_ = 0;
    bool have_prev_ = false;
};

// Everything Gate 7 needs for its final verdict, gathered into one plain struct so
// the 8-condition gate is host-testable without iCraft.  `delay` must be non-null.
struct Gate7Inputs {
    std::size_t processed = 0;       // frames actually processed
    std::size_t expected = 0;        // frames requested (== n)
    double match_rate = 0.0;         // matched / processed
    double min_match_rate = 0.90;    // frozen floor (0.90, never lowered)
    std::uint64_t nan_inf = 0;       // non-finite logits seen
    std::uint64_t reset_count = 0;   // NPU re-arm reset(1) count
    std::uint64_t frame_count = 0;   // NPU forward count
    std::uint64_t apply_count = 0;   // NPU Session apply() count
    bool discipline_ok = false;      // npu_rearm_state discipline
    const DelayGate* delay = nullptr;
};

// The 8-condition Gate 7 verdict:
//   1. processed == expected
//   2. match_rate >= min_match_rate
//   3. nan_inf == 0
//   4. reset_count == expected - 1
//   5. frame_count == expected
//   6. apply_count == 1
//   7. discipline_ok
//   8. !delay->delay_detected()
// Conditions 4-6 re-state the re-arm discipline alongside 7 (defense in depth);
// 8 replaces the old `delay_shift_match == 0` with the strong-signature test.
inline bool gate7_pass(const Gate7Inputs& in) {
    if (in.delay == nullptr) return false;   // fail-closed: no delay evidence
    if (in.processed != in.expected) return false;
    if (in.match_rate < in.min_match_rate) return false;
    if (in.nan_inf != 0) return false;
    if (in.expected == 0) return false;                     // empty run
    if (in.reset_count != in.expected - 1) return false;
    if (in.frame_count != in.expected) return false;
    if (in.apply_count != 1) return false;
    if (!in.discipline_ok) return false;
    if (in.delay->delay_detected()) return false;
    return true;
}

}  // namespace chain
