// test_live_rx_gating.cpp -- host tests for the live-rx presence-gated
// classification policy (M29 Phase F5 Task C).
//
// The board's --phase=live-rx runs the NPU ONLY while SignalPresence reports
// SIGNAL_PRESENT; on any other state it emits only the periodic state heartbeat.
// This test drives the live_rx::Gating policy with synthetic measurement vectors
// and proves the presence -> classify -> presence-gone -> NO_SIGNAL transition
// plus the LIVE_RX_DIAG counter invariants, WITHOUT the NPU or libiio.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../board_package/live_rx_gating.hpp"

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

bool is(sdr::PresenceState a, sdr::PresenceState b) { return a == b; }

// (1) classify_now is true ONLY for SIGNAL_PRESENT.
void test_classify_now_gate() {
    check(!live_rx::classify_now(sdr::PresenceState::NoSignal),
          "NO_SIGNAL -> no classify");
    check(!live_rx::classify_now(sdr::PresenceState::Acquiring),
          "ACQUIRING -> no classify");
    check(live_rx::classify_now(sdr::PresenceState::SignalPresent),
          "SIGNAL_PRESENT -> classify");
    check(!live_rx::classify_now(sdr::PresenceState::SignalLost),
          "SIGNAL_LOST -> no classify");
    check(!live_rx::classify_now(sdr::PresenceState::Invalid),
          "INVALID -> no classify");
}

// (2) a pure-noise stretch stays NO_SIGNAL: no accepted frames, no NPU runs.
void test_no_signal_no_npu() {
    live_rx::Gating g;
    for (int i = 0; i < 20; ++i) {
        const sdr::PresenceState s = g.update(mk(-80.0));
        if (live_rx::classify_now(s)) g.record_accepted();
    }
    check(is(g.state(), sdr::PresenceState::NoSignal), "noise -> NO_SIGNAL");
    check(g.counters().accepted_frames == 0, "noise -> accepted_frames 0");
    check(g.counters().npu_runs == 0, "noise -> npu_runs 0");
    check(g.invariants_ok(), "noise -> invariants hold");
}

// (3) presence -> continuous classification while present, counters consistent.
void test_present_continuous_classify() {
    live_rx::Gating g;
    // Frames 1..2 ACQUIRING, frame 3 confirms SIGNAL_PRESENT.
    for (int i = 0; i < 3; ++i) {
        const sdr::PresenceState s = g.update(mk(-40.0));
        if (live_rx::classify_now(s)) { g.record_accepted(); g.record_merge(true); }
    }
    check(is(g.state(), sdr::PresenceState::SignalPresent),
          "signal -> SIGNAL_PRESENT");
    // 10 more strong frames: every one classifies and emits a result.
    for (int i = 0; i < 10; ++i) {
        const sdr::PresenceState s = g.update(mk(-40.0));
        check(live_rx::classify_now(s), "present frame -> classify");
        if (live_rx::classify_now(s)) { g.record_accepted(); g.record_merge(true); }
    }
    check(g.counters().accepted_frames == 11, "accepted_frames == 11");
    check(g.counters().npu_runs == 11, "npu_runs == accepted");
    check(g.counters().result_sent == 11, "result_sent == accepted");
    check(g.counters().result_dropped == 0, "clean merge -> no drops");
    check(g.invariants_ok(), "invariants hold while present");
}

// (4) signal gone -> stop classifying, resume the NO_SIGNAL heartbeat path.
void test_signal_gone_stops_classify() {
    live_rx::Gating g;
    for (int i = 0; i < 3; ++i) {
        const sdr::PresenceState s = g.update(mk(-40.0));
        if (live_rx::classify_now(s)) { g.record_accepted(); g.record_merge(true); }
    }
    check(is(g.state(), sdr::PresenceState::SignalPresent), "present");
    // 5 consecutive losses -> SIGNAL_LOST (classify_now false from the 5th loss).
    for (int i = 0; i < 5; ++i) {
        const sdr::PresenceState s = g.update(mk(-120.0));
        if (i < 4) check(live_rx::classify_now(s), "still present (loss tolerant)");
        if (live_rx::classify_now(s)) { g.record_accepted(); g.record_merge(true); }
    }
    check(is(g.state(), sdr::PresenceState::SignalLost),
          "signal gone -> SIGNAL_LOST");
    // Further noise: never classifies again.
    for (int i = 0; i < 10; ++i) {
        const sdr::PresenceState s = g.update(mk(-120.0));
        check(!live_rx::classify_now(s), "no signal -> no classify");
    }
    check(g.invariants_ok(), "invariants hold across the whole transition");
}

// (5) a fail-closed merge (non-finite logit) is recorded as dropped, not sent.
void test_merge_fail_dropped() {
    live_rx::Gating g;
    for (int i = 0; i < 3; ++i) {
        const sdr::PresenceState s = g.update(mk(-40.0));
        // frame 3 (i==2) is the only SIGNAL_PRESENT frame; mark its merge as
        // fail-closed so it must be counted dropped, not sent.
        if (live_rx::classify_now(s)) { g.record_accepted(); g.record_merge(i != 2); }
    }
    check(g.counters().accepted_frames == 1, "one accepted frame");
    check(g.counters().npu_runs == 1, "one NPU run");
    check(g.counters().result_sent == 0, "fail-closed merge -> not sent");
    check(g.counters().result_dropped == 1, "fail-closed merge -> dropped");
    check(g.invariants_ok(), "invariants hold (sent + dropped == accepted)");
}

// (6) reacquire after SIGNAL_LOST: ACQUIRING then SIGNAL_PRESENT again.
void test_reacquire_after_lost() {
    live_rx::Gating g;
    for (int i = 0; i < 3; ++i) {
        const sdr::PresenceState s = g.update(mk(-40.0));
        if (live_rx::classify_now(s)) { g.record_accepted(); g.record_merge(true); }
    }
    for (int i = 0; i < 5; ++i) g.update(mk(-120.0));
    check(is(g.state(), sdr::PresenceState::SignalLost), "SIGNAL_LOST");
    const sdr::PresenceState r1 = g.update(mk(-40.0));
    check(is(r1, sdr::PresenceState::Acquiring), "reappear -> ACQUIRING");
    g.update(mk(-40.0));
    const sdr::PresenceState r3 = g.update(mk(-40.0));
    check(is(r3, sdr::PresenceState::SignalPresent), "re-confirmed -> SIGNAL_PRESENT");
    check(live_rx::classify_now(r3), "re-confirmed -> classify again");
}

}  // namespace

int main() {
    std::printf("test_live_rx_gating\n");
    test_classify_now_gate();
    test_no_signal_no_npu();
    test_present_continuous_classify();
    test_signal_gone_stops_classify();
    test_merge_fail_dropped();
    test_reacquire_after_lost();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
