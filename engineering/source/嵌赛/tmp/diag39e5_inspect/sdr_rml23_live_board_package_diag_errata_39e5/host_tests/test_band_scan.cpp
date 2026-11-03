// test_band_scan.cpp -- host test for the BAND SCAN LO-sweep sequencer +
// per-step accumulator (task 39e5 UI v3 · M10).
//
// iCraft-free / libiio-free.  Built with g++ -std=gnu++17 -O2 -Wall -Wextra -Werror.
// Covers: config validation, sweep schedule (inclusive start..last<=stop, wrap),
// dwell completion exactly at dwell_frames, accumulator best-detection semantics,
// and the reset_lock() composition the board producer uses at each LO step.

#include "../board_package/band_scan.hpp"
#include "../board_package/work_mode_engine.hpp"
#include "../board_package/mode_control.hpp"

#include <cstdio>
#include <cstdint>
#include <stdexcept>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

static void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("FAIL: %s\n", what);
    }
}

template <typename F>
static bool throws(F&& f) {
    try {
        f();
        return false;
    } catch (const std::invalid_argument&) {
        return true;
    } catch (...) {
        return false;
    }
}

int main() {
    using namespace sdr;

    // --- config validation ---------------------------------------------------
    {
        BandScanConfig bad1; bad1.stop_hz = bad1.start_hz - 1;
        check(throws([&] { BandScanSequencer s(bad1); }), "stop < start throws");
        BandScanConfig bad2; bad2.step_hz = 0;
        check(throws([&] { BandScanSequencer s(bad2); }), "step_hz == 0 throws");
        BandScanConfig bad3; bad3.dwell_frames = 0;
        check(throws([&] { BandScanSequencer s(bad3); }), "dwell_frames == 0 throws");
    }

    // --- sweep schedule (exact divide) --------------------------------------
    {
        BandScanConfig c;
        c.start_hz = 2400000000ULL;
        c.stop_hz  = 2500000000ULL;
        c.step_hz  = 10000000ULL;   // 10 MHz
        c.dwell_frames = 32;
        BandScanSequencer s(c);
        check(s.total_steps() == 11, "2400..2500 @10MHz -> 11 steps");
        check(s.current_frequency_hz() == 2400000000ULL, "first LO == start");
        check(s.step_index() == 0 && s.frames_in_step() == 0, "initial step 0 / frames 0");
        check(s.dwell_frames() == 32, "dwell_frames reflected");

        // Walk to the last step via advance_step (without dwell): schedule must be
        // start + step*k.
        bool order_ok = true;
        for (int k = 0; k < 11; ++k) {
            if (s.current_frequency_hz() != 2400000000ULL + static_cast<std::uint64_t>(k) * 10000000ULL)
                order_ok = false;
            if (k < 10) s.advance_step();
        }
        check(order_ok, "LO schedule start..stop inclusive in order");
        check(s.current_frequency_hz() == 2500000000ULL, "last LO == stop");

        s.advance_step();   // wrap
        check(s.step_index() == 0 && s.current_frequency_hz() == 2400000000ULL,
              "advance_step wraps past stop back to start");

        s.reset();
        check(s.step_index() == 0 && s.current_frequency_hz() == 2400000000ULL &&
              s.frames_in_step() == 0, "reset() returns to first step");
    }

    // --- non-exact divide: last step <= stop --------------------------------
    {
        BandScanConfig c;
        c.start_hz = 100; c.stop_hz = 250; c.step_hz = 100; c.dwell_frames = 3;
        BandScanSequencer s(c);
        check(s.total_steps() == 2, "100..250 @100 -> 2 steps (100, 200)");
        check(s.current_frequency_hz() == 100, "first LO 100");
        s.advance_step();
        check(s.current_frequency_hz() == 200, "second LO 200 (<= stop)");
    }

    // --- dwell completion exactly at dwell_frames ---------------------------
    {
        BandScanConfig c;
        c.start_hz = 1000; c.stop_hz = 1000; c.step_hz = 10; c.dwell_frames = 5;
        BandScanSequencer s(c);
        check(s.total_steps() == 1, "single step when start == stop");
        int completions = 0;
        for (int f = 0; f < 5; ++f)
            if (s.on_frame()) ++completions;
        check(completions == 1, "dwell completes exactly once in dwell_frames frames");
        check(s.frames_in_step() == 5, "frames_in_step == dwell after completion");

        s.advance_step();   // wraps (single step -> step 0)
        check(s.frames_in_step() == 0, "advance_step restarts dwell counter");
    }

    // --- accumulator: best-detection semantics ------------------------------
    {
        BandScanConfig c;
        c.start_hz = 0; c.stop_hz = 30; c.step_hz = 10; c.dwell_frames = 4;
        BandScanAccumulator acc(c);
        check(acc.size() == 4, "accumulator sized == total_steps");
        check(!acc.bin(0).has_detection, "empty bin has no detection");

        acc.record(0, 6, 0.3f);   // BPSK @ 0.3
        acc.record(0, 6, 0.9f);   // BPSK @ 0.9 -> best
        acc.record(0, 5, 0.5f);   // GFSK @ 0.5 (lower than 0.9)
        check(acc.bin(0).has_detection, "record sets has_detection");
        check(acc.bin(0).best_class == 6, "best_class == highest-confidence class");
        check(acc.bin(0).best_confidence == 0.9f, "best_confidence == max");
        check(acc.bin(0).frames == 3, "frames counts every record");

        acc.record(0, -1, 0.0f);  // invalid class: must not become best
        check(acc.bin(0).best_class == 6, "invalid class (-1) does not clobber best");

        acc.record(1, 7, 0.7f);
        check(acc.bin(1).best_class == 7, "independent per-bin best");
        check(!acc.bin(2).has_detection, "untouched bin still empty");

        bool threw = false;
        try { acc.record(4, 0, 0.0f); } catch (const std::out_of_range&) { threw = true; }
        check(threw, "out-of-range record throws");

        acc.reset();
        check(!acc.bin(0).has_detection && acc.bin(0).frames == 0,
              "accumulator reset clears bins");
    }

    // --- composition: reset_lock() at each LO step ---------------------------
    {
        WorkModeEngine eng(mode_ctl::ModeKind::BandScan, LevelConfig{}, 5);
        // Lock a class over the window, then confirm reset_lock() clears it.
        eng.update(FrameLevelStats{}, true, 3, true);
        eng.update(FrameLevelStats{}, true, 3, true);
        eng.update(FrameLevelStats{}, true, 3, true);
        eng.update(FrameLevelStats{}, true, 3, true);
        eng.update(FrameLevelStats{}, true, 3, true);
        check(eng.class_locked() && eng.locked_class() == 3, "class locks after window");

        eng.reset_lock();
        check(!eng.class_locked() && eng.locked_class() == -1,
              "reset_lock() clears the held class (for the next LO step)");
    }

    std::printf("test_band_scan: %d pass, %d fail\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
