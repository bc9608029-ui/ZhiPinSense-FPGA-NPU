// test_work_mode_engine.cpp -- host tests for the work-mode engine (UI v3 M7 FIXED
// + M8 AUTO LOCK): the mode -> level-mode mapping, the FIXED identity path, the
// class-stability lock, and the AUTO LOCK publish/adapt policy.  Pure logic
// (work_mode_engine.hpp + mode_control.hpp + auto_level_control.hpp); no iCraft,
// no libiio.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled -O2 -Wall -Wextra
// -Werror; also run under ASan/UBSan.

#include "../board_package/mode_control.hpp"
#include "../board_package/work_mode_engine.hpp"
#include "../sdr_adapter/auto_level_control.hpp"

#include <cstdio>
#include <string>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

sdr::FrameLevelStats good_stats() {
    sdr::FrameLevelStats s;
    s.adc_rms_dbfs = -12.0;
    s.clip_ratio = 0.0;
    s.model_rms = 1.0;   // at training-domain target
    s.valid = true;
    return s;
}

// ---- M7: mode -> level-mode mapping ----------------------------------------
void test_level_mode_mapping() {
    check(sdr::level_mode_for(mode_ctl::ModeKind::Fixed) == sdr::LevelMode::Fixed,
          "Fixed -> LevelMode::Fixed");
    check(sdr::level_mode_for(mode_ctl::ModeKind::AutoLock) == sdr::LevelMode::Auto,
          "AutoLock -> LevelMode::Auto");
    check(sdr::level_mode_for(mode_ctl::ModeKind::BandScan) == sdr::LevelMode::Auto,
          "BandScan -> LevelMode::Auto");
}

// ---- M7: FIXED mode is the frozen identity path -----------------------------
void test_fixed_mode() {
    sdr::WorkModeEngine e(mode_ctl::ModeKind::Fixed);
    check(e.mode() == mode_ctl::ModeKind::Fixed, "default mode is Fixed");
    check(e.level_mode() == sdr::LevelMode::Fixed, "Fixed engine level mode is Fixed");
    check(e.model_scale() == 1.0f, "Fixed model scale is identity 1.0");
    check(e.rf_gain_db() == 0.0, "Fixed rf gain is 0");

    // Valid + signal-present frame publishes its raw argmax, no lock.
    {
        sdr::WorkModeDecision d = e.update(good_stats(), true, 7);
        check(d.publish, "Fixed valid+present publishes");
        check(d.published_class == 7, "Fixed published_class == raw argmax");
        check(!d.class_locked, "Fixed never class-locks");
        check(d.locked_class == -1, "Fixed locked_class is -1");
        check(std::string(d.reason) == "FIXED", "Fixed reason == FIXED");
        check(d.model_scale == 1.0f && d.rf_gain_db == 0.0, "Fixed decision scale/gain identity");
    }

    // No signal / invalid frame -> no publish.
    {
        sdr::WorkModeDecision d = e.update(good_stats(), false, 7);
        check(!d.publish && d.published_class == -1, "Fixed no-signal does not publish");
        check(std::string(d.reason) == "FIXED no_signal", "Fixed no-signal reason");
    }
    {
        sdr::FrameLevelStats bad = good_stats();
        bad.valid = false;
        sdr::WorkModeDecision d = e.update(bad, true, 7);
        check(!d.publish, "Fixed invalid frame does not publish");
    }

    // FIXED never adapts: a hot/clipped frame leaves scale and gain untouched.
    {
        sdr::FrameLevelStats hot = good_stats();
        hot.clip_ratio = 0.5;
        hot.model_rms = 8.0;
        for (int i = 0; i < 40; ++i) e.update(hot, true, 7);
        check(e.model_scale() == 1.0f, "Fixed model_scale frozen at 1.0 across hot frames");
        check(e.rf_gain_db() == 0.0, "Fixed rf_gain frozen at 0 across clipped frames");
    }

    // A custom fixed scale is applied exactly.
    {
        sdr::LevelConfig cfg;
        cfg.fixed_model_scale = 2.0f;
        sdr::WorkModeEngine e2(mode_ctl::ModeKind::Fixed, cfg);
        check(e2.model_scale() == 2.0f, "Fixed honors fixed_model_scale=2.0");
        sdr::WorkModeDecision d = e2.update(good_stats(), true, 3);
        check(d.model_scale == 2.0f, "Fixed decision carries custom scale");
    }
}

// ---- M8: class-stability lock ----------------------------------------------
void test_class_lock() {
    sdr::ClassStabilityLock lk(3);
    check(!lk.locked(), "lock not locked at start");

    check(lk.feed(5) == -1 && !lk.locked(), "1st frame not yet locked (window 3)");
    check(lk.feed(5) == -1 && !lk.locked(), "2nd frame not yet locked");
    check(lk.feed(5) == 5 && lk.locked(), "3rd identical frame locks");
    check(lk.locked_class() == 5, "locked class == 5");

    // A single flicker does not drop the held class.
    check(lk.feed(9) == 5, "single flicker keeps publishing held class 5");
    check(lk.locked() && lk.locked_class() == 5, "lock still held after flicker");

    // The new class re-locks only after it too is stable for the window.
    check(lk.feed(9) == 5, "2nd flicker frame still held");
    check(lk.feed(9) == 9 && lk.locked_class() == 9, "3rd frame re-locks to 9");

    // Invalid class (-1) keeps the hold.
    check(lk.feed(-1) == 9 && lk.locked_class() == 9, "invalid class keeps hold");

    lk.reset();
    check(!lk.locked() && lk.locked_class() == -1, "reset clears the lock");
}

// ---- M8: AUTO LOCK mode (auto level + class lock) --------------------------
void test_auto_lock_mode() {
    sdr::WorkModeEngine e(mode_ctl::ModeKind::AutoLock, sdr::LevelConfig{}, /*window=*/3);
    check(e.level_mode() == sdr::LevelMode::Auto, "AutoLock engine level mode is Auto");

    // Before a class stabilizes: no publish ("acquiring").
    {
        sdr::WorkModeDecision d = e.update(good_stats(), true, 7);
        check(!d.publish && d.published_class == -1, "AutoLock acquiring -> no publish");
        check(!d.class_locked && std::string(d.reason) == "AUTO acquiring", "AutoLock acquiring reason");
    }
    sdr::WorkModeDecision d2 = e.update(good_stats(), true, 7);
    check(!d2.publish, "AutoLock 2nd identical frame still acquiring");

    // 3rd identical frame locks and publishes the locked class.
    sdr::WorkModeDecision d3 = e.update(good_stats(), true, 7);
    check(d3.publish && d3.published_class == 7, "AutoLock locks on 3rd frame and publishes");
    check(d3.class_locked && d3.locked_class == 7, "AutoLock class_locked == 7");
    check(std::string(d3.reason) == "AUTO locked", "AutoLock locked reason");

    // A single flicker is suppressed (publish held class 7, not the flicker).
    sdr::WorkModeDecision d4 = e.update(good_stats(), true, 2);
    check(d4.publish && d4.published_class == 7, "AutoLock suppresses a 1-frame flicker");

    // A genuinely different class re-locks after the window.
    e.update(good_stats(), true, 2);
    sdr::WorkModeDecision d6 = e.update(good_stats(), true, 2);
    check(d6.publish && d6.published_class == 2 && d6.locked_class == 2,
          "AutoLock re-locks to a stable new class");

    // No signal: no publish, and adaptation is frozen (scale unchanged).
    {
        float before = e.model_scale();
        sdr::FrameLevelStats hot = good_stats();
        hot.model_rms = 8.0;
        for (int i = 0; i < 40; ++i) e.update(hot, false, 2);
        check(e.model_scale() == before, "AutoLock frozen without signal (no scale drift)");
        sdr::WorkModeDecision d = e.update(good_stats(), false, 2);
        check(!d.publish && std::string(d.reason) == "AUTO no_signal", "AutoLock no-signal reason");
    }
}

// ---- M8: AUTO level adaptation (slow + bounded) -----------------------------
void test_auto_adaptation() {
    sdr::WorkModeEngine e(mode_ctl::ModeKind::AutoLock);
    // Feed a signal 2x too hot at the model layer; after one update cadence the
    // scale must step DOWN (bounded, not instant normalization).
    sdr::FrameLevelStats hot = good_stats();
    hot.model_rms = 2.0;   // double the target -> scale should decrease
    for (int i = 0; i < 8; ++i) e.update(hot, true, 4);
    const float after8 = e.model_scale();
    check(after8 < 1.0f, "Auto scale decreases for an over-hot input");
    check(after8 >= 0.95f - 1e-4f, "Auto scale step is bounded (>= 0.95)");
    check(e.rf_gain_db() == 0.0, "no RF delta for a clean (non-clipped) ADC");
}

// ---- mode switching + reset -------------------------------------------------
void test_set_mode_and_reset() {
    sdr::WorkModeEngine e(mode_ctl::ModeKind::Fixed);
    // Lock something in AUTO LOCK, then switch back to FIXED -> lock cleared.
    e.set_mode(mode_ctl::ModeKind::AutoLock);
    for (int i = 0; i < 6; ++i) e.update(good_stats(), true, 5);
    check(e.class_locked(), "AutoLock reaches a lock");
    e.set_mode(mode_ctl::ModeKind::Fixed);
    check(e.level_mode() == sdr::LevelMode::Fixed, "set_mode(Fixed) flips level mode");
    check(!e.class_locked(), "set_mode clears the class lock");
    check(e.model_scale() == 1.0f && e.rf_gain_db() == 0.0, "set_mode(Fixed) resets level state");

    sdr::WorkModeDecision d = e.update(good_stats(), true, 5);
    check(d.publish && d.published_class == 5 && !d.class_locked,
          "after set_mode(Fixed), raw argmax is published");
}

}  // namespace

int main() {
    std::printf("test_work_mode_engine\n");
    test_level_mode_mapping();
    test_fixed_mode();
    test_class_lock();
    test_auto_lock_mode();
    test_auto_adaptation();
    test_set_mode_and_reset();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
