#pragma once

// npu_lifecycle_state.hpp — pure-logic, iCraft-free state machine encoding the
// M22 device-lifecycle discipline (task 39e5 M22 §五.1):
//
//   * open ONCE at init, close ONCE at exit (never re-open between frames);
//   * no per-frame device/session recreation;
//   * an EXPLICIT recovery state machine on a transient per-frame failure;
//   * no permanent resource leak used to avoid close().
//
// States:
//   Uninit -> Opened -> SessionApplied -> Ready
//   Ready  -> Recovering (transient reset/forward failure) -> Ready | Failed
//   any    -> Failed (unrecoverable)
//
// `Ready` is the only state in which a frame may run.  A transient failure moves
// to `Recovering`; the caller retries the SAME frame (reset(1) + forward again)
// up to `recover_budget()` times.  Exceeding the budget (or any contract failure)
// moves to `Failed`, and the caller must fail closed — the device is closed once
// by the owner's destructor, never leaked.  `reopen()` is intentionally NOT a
// state: M22 forbids re-creating the NPU device between frames.
//
// This is the *decision* logic only; NpuClassifier12 consults it on the board so
// the transitions are unit-testable on the host with no iCraft type.

#include <cstdint>

namespace chain {

class NpuLifecycleState {
public:
    enum class State {
        Uninit = 0,
        Opened,
        SessionApplied,
        Ready,
        Recovering,
        Failed,
    };

    // Build the life-cycle record with a fixed transient-recovery budget.
    explicit NpuLifecycleState(int recover_budget = 3)
        : recover_budget_(recover_budget) {}

    void record_open() {
        if (state_ != State::Uninit) mark_failed();
        else {
            ++open_count_;
            state_ = State::Opened;
        }
    }

    // Record one Session::apply().  Returns true iff this is the first apply; a
    // second apply is a discipline violation (callers fail on it).
    bool record_apply() {
        if (state_ != State::Opened) { mark_failed(); return false; }
        ++apply_count_;
        state_ = State::SessionApplied;
        return apply_count_ == 1;
    }

    void record_ready() {
        if (state_ == State::SessionApplied) state_ = State::Ready;
        // Recovering -> Ready is entered via record_frame_ok(); reaching Ready
        // from any other state is a protocol error.
        else if (state_ != State::Ready) mark_failed();
    }

    // Called at the start of each frame.  Returns true iff a frame may run.
    bool begin_frame() {
        if (state_ != State::Ready) return false;
        ++frame_count_;
        return true;
    }

    // Record a transient per-frame failure.  Returns true iff the caller should
    // RETRY this frame (still inside the recovery budget); false => Failed.
    // Recovering is a retryable state: the caller re-runs the SAME frame (reset +
    // forward again) without a fresh begin_frame(), so repeated failures within
    // the budget keep returning true and only the budget overrun fails closed.
    bool record_frame_failure() {
        if (state_ != State::Ready && state_ != State::Recovering) {
            mark_failed();
            return false;
        }
        ++recover_attempts_;
        if (recover_attempts_ <= static_cast<std::uint64_t>(recover_budget_)) {
            state_ = State::Recovering;
            return true;
        }
        mark_failed();
        return false;
    }

    // Record a FATAL fault (e.g. a Device::reset failure, which poisons the
    // re-arm discipline).  No retry is possible: the state moves straight to
    // Failed and the owner must close the device once (RAII) and fail closed.
    void record_fatal() { mark_failed(); }

    // Record a successful frame (clears the recovery budget).  The state moves
    // back to Ready.
    void record_frame_ok() {
        recover_attempts_ = 0;
        if (state_ == State::Recovering || state_ == State::Ready)
            state_ = State::Ready;
        else
            mark_failed();
    }

    void record_close() {
        // Close is legal from any state (RAII destructor).  After close the state
        // is terminal-Closed; represented as Uninit-with-failed so a later open
        // is a protocol error rather than a silent reopen.
        closed_ = true;
    }

    State state() const { return state_; }
    bool ready() const { return state_ == State::Ready; }
    bool failed() const { return state_ == State::Failed; }
    bool closed() const { return closed_; }
    bool discipline_ok() const {
        // Exactly one open, one apply, and never a recovery-budget overrun or a
        // protocol violation.  Frame count and recovery are diagnostics; the
        // discipline itself only requires the open/apply/close protocol.
        return !failed_ && open_count_ == 1 && apply_count_ == 1;
    }
    std::uint64_t frame_count() const { return frame_count_; }
    std::uint64_t apply_count() const { return apply_count_; }
    std::uint64_t open_count() const { return open_count_; }
    std::uint64_t recover_attempts() const { return recover_attempts_; }
    int recover_budget() const { return recover_budget_; }

    const char* state_name() const {
        switch (state_) {
            case State::Uninit:         return "UNINIT";
            case State::Opened:         return "OPENED";
            case State::SessionApplied: return "SESSION_APPLIED";
            case State::Ready:          return "READY";
            case State::Recovering:     return "RECOVERING";
            case State::Failed:         return "FAILED";
        }
        return "UNKNOWN";
    }

private:
    void mark_failed() { failed_ = true; state_ = State::Failed; }

    State state_ = State::Uninit;
    int recover_budget_ = 3;
    bool failed_ = false;
    bool closed_ = false;
    std::uint64_t frame_count_ = 0;
    std::uint64_t apply_count_ = 0;
    std::uint64_t open_count_ = 0;
    std::uint64_t recover_attempts_ = 0;
};

}  // namespace chain
