#pragma once

// work_mode_engine.hpp -- binds the M6 work-mode control state to the M2 level
// control and to the classification publish policy (task 39e5 UI v3 M7/M8).
//
// Pure-logic, iCraft-free, header-only.  The board producer (Gate 9 / the M9
// self-test gate10) owns a WorkModeEngine; the M6 reverse control channel sets its
// mode via set_mode(), and every captured frame is fed through update() to get a
// WorkModeDecision that says how to level-manage the input and whether/what class
// to publish.
//
//   FIXED      (M7)  -- fixed gain + fixed scale.  level_mode()==Fixed, the
//                       digital scalar is exactly fixed_model_scale (identity by
//                       default -> the frozen path is untouched), RF gain is NOT
//                       auto-managed, and every valid signal-present frame is
//                       published with its raw argmax class (no class lock).
//   AUTO LOCK  (M8)  -- slow bounded auto level (AutoLevelControl) + a class
//                       stability lock: a top-1 class is published only after it
//                       has been stable for `stability_window` consecutive frames,
//                       and is then HELD (a single-flicker to another class is
//                       suppressed; a genuinely different class re-locks only after
//                       it too is stable for the window).  Level adaptation is
//                       frozen when there is no signal or `adapt==false`, so it
//                       never chases noise.
//   BAND SCAN  (M10) -- same auto level + class lock for now; the LO sweep /
//                       scan sequencer arrives in M10 and consumes this state.
//
// Red lines (unchanged from M2): auto level is SLOW, BOUNDED and SMOOTHED -- it is
// NOT per-frame RMS normalization; the class lock only gates what is PUBLISHED, it
// never rewrites the NPU's argmax or the 12-class contract.

#include <cstdint>
#include <string>

#include "mode_control.hpp"
#include "../sdr_adapter/auto_level_control.hpp"

namespace sdr {

// The level layer a work mode drives (FIXED -> Fixed identity, others -> Auto).
inline LevelMode level_mode_for(mode_ctl::ModeKind m) {
    switch (m) {
        case mode_ctl::ModeKind::AutoLock:
        case mode_ctl::ModeKind::BandScan: return LevelMode::Auto;
        case mode_ctl::ModeKind::Fixed:
        default:                           return LevelMode::Fixed;
    }
}

// Class-stability lock (AUTO LOCK / BAND SCAN).  A top-1 class is HELD once it has
// been stable for `window` consecutive frames; a differing frame starts a new
// candidate run and the previous held class keeps being published until the new
// class proves stable (suppressing single-frame flicker while still adapting to a
// real modulation change).
class ClassStabilityLock {
public:
    explicit ClassStabilityLock(int window = 5) : window_(window > 0 ? window : 1) {}

    // Feed the raw top-1 class index.  Returns the class to PUBLISH: the held
    // stable class, or -1 before any class has stabilized.
    int feed(int cls) {
        if (cls < 0) { candidate_run_ = 0; return held_; }   // invalid: keep held
        if (cls == candidate_) {
            ++candidate_run_;
        } else {
            candidate_ = cls;
            candidate_run_ = 1;
        }
        if (candidate_run_ >= window_) held_ = candidate_;
        return held_;
    }

    bool locked() const { return held_ >= 0; }
    int locked_class() const { return held_; }
    int run() const { return candidate_run_; }
    void reset() { candidate_ = -1; candidate_run_ = 0; held_ = -1; }

private:
    int window_;
    int candidate_ = -1;
    int candidate_run_ = 0;
    int held_ = -1;
};

// Per-frame decision from the work-mode engine.
struct WorkModeDecision {
    LevelMode level_mode = LevelMode::Fixed;
    float model_scale = 1.0f;       // digital scalar to apply on top of receiver_scale
    double rf_gain_db = 0.0;        // auto-managed RF gain offset (0 in FIXED)
    bool publish = true;            // emit this frame's classification
    int published_class = -1;       // class to emit when publish; -1 = none
    bool class_locked = false;      // a stable class is held (AUTO LOCK / BAND SCAN)
    int locked_class = -1;          // held stable class, or -1
    const char* reason = "";        // short log tag (string literal, no allocation)
};

class WorkModeEngine {
public:
    WorkModeEngine(mode_ctl::ModeKind mode = mode_ctl::ModeKind::Fixed,
                   const LevelConfig& cfg = {}, int stability_window = 5)
        : mode_(mode), cfg_(cfg), level_(auto_cfg(cfg)),
          lock_(stability_window) {
        model_scale_ = (level_mode() == LevelMode::Fixed) ? cfg_.fixed_model_scale : 1.0f;
    }

    mode_ctl::ModeKind mode() const { return mode_; }
    LevelMode level_mode() const { return level_mode_for(mode_); }
    float model_scale() const { return model_scale_; }
    double rf_gain_db() const { return rf_gain_db_; }
    bool class_locked() const { return lock_.locked(); }
    int locked_class() const { return lock_.locked_class(); }

    // Switch work mode (from the M6 control channel).  Rebuilds the auto-level
    // layer for the new mode and clears the class lock.
    void set_mode(mode_ctl::ModeKind m) {
        if (m == mode_) return;
        mode_ = m;
        level_ = AutoLevelControl(auto_cfg(cfg_));
        lock_.reset();
        model_scale_ = (level_mode() == LevelMode::Fixed) ? cfg_.fixed_model_scale : 1.0f;
        rf_gain_db_ = 0.0;
    }

    // Feed one captured frame.  `signal_present` is the M1 presence verdict (a
    // missing signal freezes AUTO adaptation); `argmax_class` is the NPU's raw
    // top-1; `adapt` false holds the level layers externally.  Returns the
    // decision.  Never throws.
    WorkModeDecision update(const FrameLevelStats& stats, bool signal_present,
                            int argmax_class, bool adapt = true) {
        WorkModeDecision d;
        d.level_mode = level_mode_for(mode_);

        if (d.level_mode == LevelMode::Fixed) {
            // FIXED (M7): fixed gain + fixed scale -- no auto management.
            model_scale_ = cfg_.fixed_model_scale;
            rf_gain_db_ = 0.0;
        } else {
            // AUTO (M8 / M10): slow bounded auto level, frozen without signal.
            level_.update(stats, signal_present && adapt);
            model_scale_ = level_.model_scale();
            rf_gain_db_ = level_.rf_gain_db();
        }
        d.model_scale = model_scale_;
        d.rf_gain_db = rf_gain_db_;

        const bool usable = stats.valid && signal_present;

        if (mode_ == mode_ctl::ModeKind::Fixed) {
            d.publish = usable;
            d.published_class = usable ? argmax_class : -1;
            d.reason = usable ? "FIXED" : "FIXED no_signal";
        } else {
            // AUTO LOCK (M8) and BAND SCAN (M10): lock onto a stable class.
            lock_.feed(argmax_class);
            d.class_locked = lock_.locked();
            d.locked_class = lock_.locked_class();
            d.publish = usable && d.class_locked;
            d.published_class = d.publish ? d.locked_class : -1;
            d.reason = !usable ? "AUTO no_signal"
                     : d.class_locked ? "AUTO locked"
                     : "AUTO acquiring";
        }
        return d;
    }

    void reset() {
        level_ = AutoLevelControl(auto_cfg(cfg_));
        lock_.reset();
        model_scale_ = (level_mode() == LevelMode::Fixed) ? cfg_.fixed_model_scale : 1.0f;
        rf_gain_db_ = 0.0;
    }

    // Clear only the class-stability lock (BAND SCAN calls this at each LO step:
    // a new frequency is a fresh signal environment, so the held class must not
    // carry over).  The auto-level layer is left untouched (continuous).
    void reset_lock() { lock_.reset(); }

private:
    // The engine drives FIXED mode itself, so the inner AutoLevelControl is always
    // configured for Auto and only consulted by the AUTO paths.
    static LevelConfig auto_cfg(const LevelConfig& c) {
        LevelConfig a = c;
        a.mode = LevelMode::Auto;
        return a;
    }

    mode_ctl::ModeKind mode_;
    LevelConfig cfg_;
    AutoLevelControl level_;
    ClassStabilityLock lock_;
    float model_scale_ = 1.0f;
    double rf_gain_db_ = 0.0;
};

}  // namespace sdr
