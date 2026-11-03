// test_auto_level_control.cpp -- host tests for automatic amplitude management
// (39e5 UI v3 M2): RF/ADC layer + model input layer, FIXED/AUTO modes.
//
// auto_level_control.hpp is iCraft-free, header-only pure decision logic: it
// emits a bounded RF gain delta and a slow bounded digital scalar, and the
// device layer applies them.  The critical property under test is that AUTO
// mode is SLOW/BOUNDED/SMOOTHED (never per-frame RMS normalization) and that
// FIXED mode is byte-for-byte the frozen receiver_scale path.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../sdr_adapter/auto_level_control.hpp"

#include <cmath>
#include <cstdio>

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s\n", what);
    }
}

bool near(double a, double b, double eps = 1e-4) {
    return std::fabs(a - b) <= eps;
}

sdr::FrameLevelStats mk(double rms_dbfs = -12.0, double model_rms = 1.0) {
    sdr::FrameLevelStats s;
    s.adc_rms_dbfs = rms_dbfs;
    s.model_rms = model_rms;
    return s;
}

sdr::LevelConfig auto_cfg() {
    sdr::LevelConfig c;
    c.mode = sdr::LevelMode::Auto;
    return c;
}

// (1) FIXED mode: model scale is exactly the fixed value, RF never adapts.
void test_fixed_mode_untouched() {
    sdr::LevelConfig c;
    c.mode = sdr::LevelMode::Fixed;
    c.fixed_model_scale = 2.0f;
    sdr::AutoLevelControl alc(c);
    check(near(alc.model_scale(), 2.0), "FIXED: scale == fixed_model_scale at construction");

    sdr::FrameLevelStats hot = mk(-6.0);   // would trigger -3 in AUTO
    hot.clip_ratio = 0.5;
    for (int i = 0; i < 10; ++i)
        check(near(alc.update(hot), 0.0), "FIXED: no RF delta even when clipping");
    check(near(alc.model_scale(), 2.0), "FIXED: scale stays fixed");
    check(near(alc.rf_gain_db(), 0.0), "FIXED: rf gain stays 0");
}

// (2) AUTO RF layer: too quiet -> +step, too hot -> -step, dead zone -> 0.
void test_rf_layer_direction_and_deadzone() {
    sdr::AutoLevelControl alc(auto_cfg());
    check(near(alc.update(mk(-30.0)), +3.0), "quiet -> +3 dB");
    check(near(alc.update(mk(-30.0)), +3.0), "quiet -> +3 dB again");
    check(near(alc.rf_gain_db(), 6.0), "gain accumulated to 6");

    check(near(alc.update(mk(-6.0)), -3.0), "hot -> -3 dB");
    check(near(alc.update(mk(-12.0)), 0.0), "inside dead zone -> 0 dB");
}

// (3) AUTO RF layer: gain clamped to [min,max]; delta reports only the applied part.
void test_rf_layer_clamped() {
    sdr::LevelConfig c = auto_cfg();
    c.rf_gain_max_db = 10.0;
    sdr::AutoLevelControl alc(c);
    for (int i = 0; i < 4; ++i) alc.update(mk(-30.0));  // 0->3->6->9->10
    check(near(alc.rf_gain_db(), 10.0), "gain clamped at 10");
    check(near(alc.update(mk(-30.0)), 0.0), "past clamp -> 0 delta (no overshoot)");
    check(near(alc.rf_gain_db(), 10.0), "gain stays at max");
}

// (4) AUTO RF layer: clip forces immediate gain reduction.
void test_rf_layer_clip_reduction() {
    sdr::AutoLevelControl alc(auto_cfg());
    alc.set_rf_gain_db(20.0);
    sdr::FrameLevelStats s = mk(-12.0);  // neutral RMS
    s.clip_ratio = 0.05;                 // > max_clip_ratio 0.01
    check(near(alc.update(s), -3.0), "clip -> immediate -3 dB");
    check(near(alc.rf_gain_db(), 17.0), "gain reduced to 17");
}

// (5) AUTO model layer: slow, step-capped adaptation toward target RMS.
void test_model_layer_slow_bounded() {
    sdr::LevelConfig c = auto_cfg();
    c.frames_per_update = 4;
    sdr::AutoLevelControl alc(c);

    // model_rms = 2.0 -> target 1.0 -> desired scale 0.5, but step-capped at 0.95.
    for (int i = 0; i < 3; ++i) alc.update(mk(-12.0, 2.0));
    check(near(alc.model_scale(), 1.0), "no model update before cadence (frames 1-3)");
    alc.update(mk(-12.0, 2.0));  // frame 4 -> first model update
    check(near(alc.model_scale(), 0.95, 1e-3), "frame 4: scale step-capped to ~0.95");
    check(alc.updates() == 1, "one model update");

    // Keep feeding; scale decreases monotonically but stays above the 0.5 target.
    double prev = 0.95;
    for (int i = 0; i < 12; ++i) {
        alc.update(mk(-12.0, 2.0));
        const double s = alc.model_scale();
        check(s <= prev + 1e-9, "scale monotonic non-increasing");
        check(s >= 0.5 - 1e-3, "scale never overshoots below target");
        prev = s;
    }
    check(alc.model_scale() > 0.5, "step cap keeps scale above natural target");
}

// (6) AUTO model layer: too-quiet signal -> scale increases, bounded by max.
void test_model_layer_increases_and_bounds() {
    sdr::LevelConfig c = auto_cfg();
    c.frames_per_update = 2;
    c.model_scale_max = 4.0f;
    sdr::AutoLevelControl alc(c);

    // model_rms = 0.05 -> desired 20.0, far above max: scale climbs toward 4 and clamps.
    for (int i = 0; i < 200; ++i) alc.update(mk(-12.0, 0.05));
    check(alc.model_scale() <= 4.0f + 1e-3f, "model scale clamped at max 4.0");
    check(alc.model_scale() > 1.0f, "model scale increased from 1.0");
}

// (7) invalid frame freezes both layers.
void test_invalid_freezes() {
    sdr::AutoLevelControl alc(auto_cfg());
    alc.update(mk(-30.0));  // gain 0->3
    sdr::FrameLevelStats bad = mk(-30.0, 0.1);
    bad.valid = false;
    check(near(alc.update(bad), 0.0), "invalid frame -> no RF delta");
    check(near(alc.rf_gain_db(), 3.0), "gain frozen on invalid");
    const float scale_before = alc.model_scale();
    check(near(alc.update(bad), 0.0), "invalid frame -> no adaptation");
    check(near(alc.model_scale(), scale_before), "scale frozen on invalid");
}

// (8) adapt=false (e.g. held by signal-presence) freezes both layers.
void test_hold_freezes() {
    sdr::AutoLevelControl alc(auto_cfg());
    alc.update(mk(-30.0));  // gain -> 3
    const float scale_before = alc.model_scale();
    check(near(alc.update(mk(-30.0, 0.1), /*adapt=*/false), 0.0), "held -> no RF delta");
    check(near(alc.rf_gain_db(), 3.0), "gain frozen when held");
    check(near(alc.model_scale(), scale_before), "scale frozen when held");
}

// (9) reset restores initial state.
void test_reset() {
    sdr::AutoLevelControl alc(auto_cfg());
    for (int i = 0; i < 40; ++i) alc.update(mk(-30.0, 0.5));
    alc.set_rf_gain_db(21.0);
    alc.reset();
    check(near(alc.model_scale(), 1.0), "reset -> model scale 1.0");
    check(near(alc.rf_gain_db(), 0.0), "reset -> rf gain 0.0");
    check(alc.frames() == 0 && alc.updates() == 0, "reset -> counters 0");
}

}  // namespace

int main() {
    std::printf("test_auto_level_control\n");
    test_fixed_mode_untouched();
    test_rf_layer_direction_and_deadzone();
    test_rf_layer_clamped();
    test_rf_layer_clip_reduction();
    test_model_layer_slow_bounded();
    test_model_layer_increases_and_bounds();
    test_invalid_freezes();
    test_hold_freezes();
    test_reset();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
