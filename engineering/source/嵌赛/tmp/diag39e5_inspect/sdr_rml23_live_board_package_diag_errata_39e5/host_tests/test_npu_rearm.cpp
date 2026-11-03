// test_npu_rearm.cpp -- host tests for the ZG330 persistent-Session re-arm state
// machine (39e5 Gate 7: the fixed one-frame-delay fix).
//
// The ZG330 returns the previous frame's output on every forward after the first
// unless Device::reset(1) re-arms its monotonic FPGA completion state between
// frames.  The discipline, encoded in npu_rearm_state.hpp (and used on the board
// by NpuClassifier12), is:
//   * Device opened once, Session created + apply()ed once;
//   * FIRST frame: forward directly, no reset;
//   * every later frame: exactly one Device::reset(1), and NEVER re-apply();
//   * a failed reset is fatal (fail-closed).
// This file unit-tests that pure logic with no iCraft type, so the state machine
// is proven correct on the host before it touches the board.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../board_package/npu_rearm_state.hpp"

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

// (1) first frame carries no reset; every later frame carries exactly one.
void test_first_frame_no_reset_then_one_each() {
    chain::NpuReArmState s;
    check(!s.begin_frame(), "frame 1: no reset (begin_frame == false)");
    for (int i = 2; i <= 240; ++i) {
        const std::uint64_t before = s.reset_count();
        check(s.begin_frame(), "later frame: reset required (begin_frame == true)");
        check(s.reset_count() == before + 1, "exactly one reset per later frame");
    }
    check(s.frame_count() == 240, "240 frames -> frame_count 240");
    check(s.reset_count() == 239, "240 frames -> reset_count 239");
}

// (2) exactly one apply; a second apply is a violation.
void test_apply_exactly_once() {
    chain::NpuReArmState s;
    check(s.record_apply(), "first apply accepted");
    check(!s.record_apply(), "second apply rejected (violation)");
    check(s.apply_count() == 2, "apply_count reflects the double apply");
    check(!s.discipline_ok(), "double apply poisons discipline");
}

// (3) a failed reset is fatal (fail-closed).
void test_reset_failure_fails_closed() {
    chain::NpuReArmState s;
    check(s.record_apply(), "apply once");
    s.begin_frame();                  // frame 1, no reset
    check(s.begin_frame(), "frame 2 needs reset");
    s.record_reset(false);            // model Device::reset(1) throwing
    check(s.reset_failed(), "reset failure recorded");
    check(!s.discipline_ok(), "reset failure -> discipline FAIL");
}

// (4) full clean 240-frame run: apply once, no reset failure, 239 resets.
void test_full_240_run_discipline_ok() {
    chain::NpuReArmState s;
    check(s.record_apply(), "apply once");
    for (int i = 0; i < 240; ++i) {
        const bool need = s.begin_frame();
        if (need) s.record_reset(true);   // model a successful reset(1)
    }
    check(s.frame_count() == 240, "240 frames");
    check(s.reset_count() == 239, "239 resets");
    check(s.apply_count() == 1, "1 apply");
    check(!s.reset_failed(), "no reset failure");
    check(s.discipline_ok(), "clean 240-frame run -> discipline OK");
}

// (5) fresh/empty state invariants.
void test_empty_run() {
    chain::NpuReArmState s;
    check(s.frame_count() == 0, "fresh state frame_count 0");
    check(s.reset_count() == 0, "fresh state reset_count 0");
    check(!s.discipline_ok(), "no apply yet -> discipline NOT ok (apply_count 0)");

    chain::NpuReArmState s2;
    check(s2.record_apply(), "single apply on fresh state accepted");
    check(s2.discipline_ok(), "apply-once, zero frames -> discipline OK");
}

}  // namespace

int main() {
    std::printf("test_npu_rearm\n");
    test_first_frame_no_reset_then_one_each();
    test_apply_exactly_once();
    test_reset_failure_fails_closed();
    test_full_240_run_discipline_ok();
    test_empty_run();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
