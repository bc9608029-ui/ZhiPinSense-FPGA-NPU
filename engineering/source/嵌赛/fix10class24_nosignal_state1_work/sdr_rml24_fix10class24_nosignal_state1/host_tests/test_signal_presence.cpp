// test_signal_presence.cpp -- host tests for the signal presence/absence state
// machine (39e5 UI v3 M1).
//
// The detector maps a per-frame measurement vector onto
// NO_SIGNAL / ACQUIRING / SIGNAL_PRESENT / SIGNAL_LOST / INVALID using joint
// evidence (energy vs a hysteretic threshold, SNR, PSD prominence, occupied
// bins) plus frame-count hysteresis and clip/NaN/Inf/capture-error guards.
// signal_presence.hpp is iCraft-free and header-only, so the state machine is
// proven correct on the host before it touches the board.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../sdr_adapter/signal_presence.hpp"

#include <cstdio>
#include <string>

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

sdr::PresenceInput mk(double power) {
    sdr::PresenceInput in;
    in.power_dbfs = power;
    in.noise_floor_dbfs = -120.0;
    return in;
}

bool is(const sdr::SignalPresence& sp, sdr::PresenceState s) {
    return sp.state() == s;
}

// (1) pure noise below threshold stays NO_SIGNAL forever.
void test_noise_stays_no_signal() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 20; ++i)
        sp.update(mk(-80.0));
    check(is(sp, sdr::PresenceState::NoSignal), "noise(-80 dBFS) -> NO_SIGNAL");
    check(sp.confirm_count() == 0, "noise -> confirm_count 0");
}

// (2) noise floor change (still below threshold) does not trigger anything.
void test_noise_floor_change_still_no_signal() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 5; ++i) sp.update(mk(-80.0));
    for (int i = 0; i < 5; ++i) sp.update(mk(-70.0));  // floor rises, still < -55
    check(is(sp, sdr::PresenceState::NoSignal), "floor change -> still NO_SIGNAL");
}

// (3) signal above threshold: ACQUIRING then SIGNAL_PRESENT after N frames.
void test_signal_confirms_after_n_frames() {
    sdr::SignalPresence sp;
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::Acquiring), "frame1 -> ACQUIRING");
    check(sp.confirm_count() == 1, "confirm_count 1");
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::Acquiring), "frame2 -> ACQUIRING");
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "frame3 (N=3) -> SIGNAL_PRESENT");
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "frame4 -> stays SIGNAL_PRESENT");
}

// (4) burst shorter than N never confirms, reverts to NO_SIGNAL.
void test_short_burst_never_confirms() {
    sdr::SignalPresence sp;
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::Acquiring), "burst frame1 -> ACQUIRING");
    sp.update(mk(-40.0));
    sp.update(mk(-80.0));  // dropout before confirm
    check(is(sp, sdr::PresenceState::NoSignal), "burst dropped -> NO_SIGNAL");
    check(sp.confirm_count() == 0, "confirm_count reset on dropout");
}

// (5) enter/exit threshold hysteresis: once present, a -58 dBFS signal (below
// the -55 enter threshold) still holds the state because the -62 exit applies.
void test_exit_threshold_hysteresis() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 3; ++i) sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "present at -40 dBFS");
    for (int i = 0; i < 5; ++i) sp.update(mk(-58.0));  // -58 < -55 enter but > -62 exit
    check(is(sp, sdr::PresenceState::SignalPresent),
          "-58 dBFS keeps SIGNAL_PRESENT (exit hysteresis)");
}

// (6) signal disappears: M consecutive losses -> SIGNAL_LOST.
void test_signal_lost_after_m_losses() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 3; ++i) sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "present");
    for (int i = 0; i < 4; ++i) sp.update(mk(-120.0));
    check(is(sp, sdr::PresenceState::SignalPresent),
          "4 losses < M=5 -> still SIGNAL_PRESENT (tolerant)");
    sp.update(mk(-120.0));
    check(is(sp, sdr::PresenceState::SignalLost), "5th loss -> SIGNAL_LOST");
    check(sp.lost_count() == 5, "lost_count 5");
}

// (7) reappear after SIGNAL_LOST: ACQUIRING then SIGNAL_PRESENT.
void test_reacquire_after_lost() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 3; ++i) sp.update(mk(-40.0));
    for (int i = 0; i < 5; ++i) sp.update(mk(-120.0));
    check(is(sp, sdr::PresenceState::SignalLost), "SIGNAL_LOST");
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::Acquiring), "reappear -> ACQUIRING");
    sp.update(mk(-40.0));
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "re-confirmed -> SIGNAL_PRESENT");
}

// (8) multi-signal / frequency hop (energy stays high) -> remains present.
void test_multi_signal_stays_present() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 3; ++i) sp.update(mk(-40.0));
    for (int i = 0; i < 10; ++i) sp.update(mk(-35.0));  // different tone, still strong
    check(is(sp, sdr::PresenceState::SignalPresent), "frequency hop -> still SIGNAL_PRESENT");
}

// (9) clip above max_clip_ratio forces INVALID.
void test_clip_forces_invalid() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 3; ++i) sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "present before clip");
    sdr::PresenceInput in = mk(-40.0);
    in.clip_ratio = 0.10;  // > 0.05
    sp.update(in);
    check(is(sp, sdr::PresenceState::Invalid), "clip -> INVALID");
}

// (10) NaN/Inf and capture_error force INVALID.
void test_nan_inf_and_capture_error_invalid() {
    sdr::SignalPresence sp;
    sdr::PresenceInput nan = mk(-40.0);
    nan.nan_inf = true;
    sp.update(nan);
    check(is(sp, sdr::PresenceState::Invalid), "nan_inf -> INVALID");

    sdr::SignalPresence sp2;
    sdr::PresenceInput ce = mk(-40.0);
    ce.capture_error = true;
    sp2.update(ce);
    check(is(sp2, sdr::PresenceState::Invalid), "capture_error -> INVALID");
}

// (11) recovery from INVALID once the fault clears.
void test_recover_from_invalid() {
    sdr::SignalPresence sp;
    sdr::PresenceInput nan = mk(-40.0);
    nan.nan_inf = true;
    sp.update(nan);
    check(is(sp, sdr::PresenceState::Invalid), "INVALID");
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::Acquiring), "fault cleared -> ACQUIRING again");
    sp.update(mk(-40.0));
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "recovered -> SIGNAL_PRESENT");
}

// (12) SNR-based detection is gain-invariant: the same signal at two RX gains
// yields the same snr (power - noise floor) and therefore the same state.
void test_snr_based_detection_gain_invariant() {
    sdr::PresenceConfig c;
    c.enter_power_dbfs = -200.0;   // disable absolute-power gate
    c.exit_power_dbfs = -200.0;
    c.min_snr_db = 10.0;           // only SNR matters

    sdr::SignalPresence low;
    low = sdr::SignalPresence(c);
    sdr::PresenceInput a;
    a.power_dbfs = -88.0; a.noise_floor_dbfs = -100.0;  // snr 12
    for (int i = 0; i < 3; ++i) low.update(a);
    check(is(low, sdr::PresenceState::SignalPresent), "low gain: snr 12 -> SIGNAL_PRESENT");

    sdr::SignalPresence high;
    high = sdr::SignalPresence(c);
    sdr::PresenceInput b;
    b.power_dbfs = -58.0; b.noise_floor_dbfs = -70.0;   // +30 dB gain, snr still 12
    for (int i = 0; i < 3; ++i) high.update(b);
    check(is(high, sdr::PresenceState::SignalPresent),
          "high gain (+30 dB): snr 12 -> SIGNAL_PRESENT (gain-invariant)");

    // A weak signal below the SNR floor is rejected even though power is high.
    sdr::SignalPresence weak;
    weak = sdr::SignalPresence(c);
    sdr::PresenceInput w;
    w.power_dbfs = -92.0; w.noise_floor_dbfs = -100.0;  // snr 8 < 10
    for (int i = 0; i < 3; ++i) weak.update(w);
    check(is(weak, sdr::PresenceState::NoSignal), "snr 8 < 10 -> NO_SIGNAL");
}

// (13) PSD prominence and occupied-bin gates corroborate energy.
void test_prominence_and_occupied_bins() {
    sdr::PresenceConfig pc;
    pc.min_peak_prominence_db = 8.0;
    sdr::SignalPresence pp;
    pp = sdr::SignalPresence(pc);
    sdr::PresenceInput lo = mk(-40.0);
    lo.psd_peak_prominence_db = 3.0;
    for (int i = 0; i < 3; ++i) pp.update(lo);
    check(is(pp, sdr::PresenceState::NoSignal), "prominence 3 < 8 -> NO_SIGNAL");
    sdr::PresenceInput hi = mk(-40.0);
    hi.psd_peak_prominence_db = 10.0;
    for (int i = 0; i < 3; ++i) pp.update(hi);
    check(is(pp, sdr::PresenceState::SignalPresent), "prominence 10 >= 8 -> SIGNAL_PRESENT");

    sdr::PresenceConfig oc;
    oc.min_occupied_bins = 5;
    sdr::SignalPresence ob;
    ob = sdr::SignalPresence(oc);
    sdr::PresenceInput few = mk(-40.0);
    few.occupied_bins = 2;
    for (int i = 0; i < 3; ++i) ob.update(few);
    check(is(ob, sdr::PresenceState::NoSignal), "occupied 2 < 5 -> NO_SIGNAL");
    sdr::PresenceInput many = mk(-40.0);
    many.occupied_bins = 6;
    for (int i = 0; i < 3; ++i) ob.update(many);
    check(is(ob, sdr::PresenceState::SignalPresent), "occupied 6 >= 5 -> SIGNAL_PRESENT");
}

// (14) state names and reset() behave.
void test_names_and_reset() {
    check(std::string(presence_state_name(sdr::PresenceState::SignalLost)) ==
              "SIGNAL_LOST",
          "presence_state_name(SIGNAL_LOST)");
    sdr::SignalPresence sp;
    for (int i = 0; i < 3; ++i) sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "present before reset");
    sp.reset();
    check(is(sp, sdr::PresenceState::NoSignal), "reset -> NO_SIGNAL");
    check(sp.confirm_count() == 0 && sp.lost_count() == 0, "reset clears counters");
}

// (15) SIGNAL_LOST resolves to NO_SIGNAL on the next no-signal frame (it never
// lingers in SIGNAL_LOST).  Re-acquiring still requires confirm_frames hints
// (covered by test_reacquire_after_lost).
void test_signal_lost_resolves_to_no_signal() {
    sdr::SignalPresence sp;
    for (int i = 0; i < 3; ++i) sp.update(mk(-40.0));
    for (int i = 0; i < 5; ++i) sp.update(mk(-120.0));
    check(is(sp, sdr::PresenceState::SignalLost), "5 losses -> SIGNAL_LOST");
    sp.update(mk(-120.0));  // one more no-signal frame
    check(is(sp, sdr::PresenceState::NoSignal),
          "SIGNAL_LOST + no-signal frame -> NO_SIGNAL (never lingers)");
    check(sp.lost_count() == 0, "lost_count reset on resolve to NO_SIGNAL");
}

// (16) INVALID resolves to NO_SIGNAL on a fault-free no-signal frame; a
// fault-free SIGNAL frame still re-enters via ACQUIRING (test 11 covers that).
void test_invalid_resolves_to_no_signal() {
    sdr::SignalPresence sp;
    sdr::PresenceInput nan = mk(-40.0);
    nan.nan_inf = true;
    sp.update(nan);
    check(is(sp, sdr::PresenceState::Invalid), "nan_inf -> INVALID");
    sp.update(mk(-120.0));  // fault cleared, still no signal
    check(is(sp, sdr::PresenceState::NoSignal),
          "INVALID + fault-free no-signal -> NO_SIGNAL");
}

// (17) full presence lifecycle: NO_SIGNAL -> ACQUIRING -> SIGNAL_PRESENT ->
// SIGNAL_LOST -> NO_SIGNAL (the state machine is class-count-independent).
void test_full_cycle() {
    sdr::SignalPresence sp;
    check(is(sp, sdr::PresenceState::NoSignal), "start -> NO_SIGNAL");
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::Acquiring), "signal frame1 -> ACQUIRING");
    sp.update(mk(-40.0));
    sp.update(mk(-40.0));
    check(is(sp, sdr::PresenceState::SignalPresent), "signal frame3 -> SIGNAL_PRESENT");
    for (int i = 0; i < 5; ++i) sp.update(mk(-120.0));
    check(is(sp, sdr::PresenceState::SignalLost), "5 no-signal frames -> SIGNAL_LOST");
    sp.update(mk(-120.0));
    check(is(sp, sdr::PresenceState::NoSignal), "next no-signal frame -> NO_SIGNAL");
}

}  // namespace

int main() {
    std::printf("test_signal_presence\n");
    test_noise_stays_no_signal();
    test_noise_floor_change_still_no_signal();
    test_signal_confirms_after_n_frames();
    test_short_burst_never_confirms();
    test_exit_threshold_hysteresis();
    test_signal_lost_after_m_losses();
    test_reacquire_after_lost();
    test_multi_signal_stays_present();
    test_clip_forces_invalid();
    test_nan_inf_and_capture_error_invalid();
    test_recover_from_invalid();
    test_snr_based_detection_gain_invariant();
    test_prominence_and_occupied_bins();
    test_names_and_reset();
    test_signal_lost_resolves_to_no_signal();
    test_invalid_resolves_to_no_signal();
    test_full_cycle();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
