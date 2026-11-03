// test_delay_gate.cpp -- host tests for the Gate 7 fixed-one-frame-delay gate
// (task 39e5 §三).
//
// The old `delay_shift_match == 0` gate mis-reported the board-proven re-arm run
// (delay_shift_match 10/236, aligned 227/240) as a false delay.  The fix is the
// STRONG one-frame-delay signature in delay_gate.hpp:
//   delay_shift_rate = compared>0 ? shift_match/compared : 0
//   delay_detected   = compared>0 && shift_rate>=0.90 && shift_rate>aligned_rate
// and the 8-condition gate7_pass() verdict.  This file unit-tests that pure logic
// with no iCraft type, so it is proven correct on the host before the board.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../board_package/delay_gate.hpp"

#include <cstdio>
#include <set>
#include <vector>

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

// Build a 240-frame two-class alternating ref sequence with exactly 236
// ref-boundaries (3 "stays" at i=79/159/239), and `shift_match` frames whose
// prediction equals the PREVIOUS frame's ref (the stale-output signature).  Every
// other frame predicts its own ref (aligned).  This reproduces the exact shapes of
// the board results: (10, 236) and (230, 236).
chain::DelayGate make_gate(std::size_t shift_match) {
    chain::DelayGate g;
    const std::size_t N = 240;
    std::vector<int> refs(N);
    refs[0] = 0;
    for (std::size_t i = 1; i < N; ++i) {
        refs[i] = refs[i - 1] ^ 1;
        if (i == 79 || i == 159 || i == 239) refs[i] = refs[i - 1];  // 3 stays
    }
    std::vector<int> boundaries;
    for (std::size_t i = 1; i < N; ++i)
        if (refs[i] != refs[i - 1]) boundaries.push_back(static_cast<int>(i));
    // 239 adjacent pairs - 3 stays == 236 boundaries.
    std::set<int> shift_at;
    for (std::size_t k = 0; k < shift_match && k < boundaries.size(); ++k)
        shift_at.insert(boundaries[k]);

    g.on_frame(refs[0], refs[0]);   // first frame seeds prev_ref, no comparison
    for (std::size_t i = 1; i < N; ++i) {
        const int pred = (shift_at.count(static_cast<int>(i)) != 0) ? refs[i - 1]
                                                                    : refs[i];
        g.on_frame(pred, refs[i]);
    }
    return g;
}

// (1)/(2) the two exact board shapes: 10/236 (accidental collisions) vs 230/236
// (true one-frame delay).
void test_delay_signature_thresholds() {
    chain::DelayGate g10 = make_gate(10);
    check(g10.delay_shift_compared() == 236, "10/236: compared == 236");
    check(g10.delay_shift_match() == 10, "10/236: shift_match == 10");
    check(g10.delay_shift_rate() < 0.90, "10/236: shift_rate < 0.90");
    check(!g10.delay_detected(), "10/236 -> delay_detected == false");

    chain::DelayGate g230 = make_gate(230);
    check(g230.delay_shift_compared() == 236, "230/236: compared == 236");
    check(g230.delay_shift_match() == 230, "230/236: shift_match == 230");
    check(g230.delay_shift_rate() >= 0.90, "230/236: shift_rate >= 0.90");
    check(g230.delay_detected(), "230/236 -> delay_detected == true");

    // compared == 0 short-circuits to no-delay.
    chain::DelayGate g0;
    for (int i = 0; i < 50; ++i) g0.on_frame(0, 0);
    check(g0.delay_shift_compared() == 0, "same-ref run: compared == 0");
    check(!g0.delay_detected(), "compared == 0 -> delay_detected == false");

    // aligned_rate / total sanity.
    check(g10.total() == 240, "total == 240");
    check(g10.aligned_match() == 230, "10 shift collisions -> aligned 230");
    check(g230.aligned_match() == 10, "230 shift collisions -> aligned 10");
}

// (3)/(4)/(5) the 8-condition verdict.
void test_gate7_pass_verdict() {
    // (3) high aligned + low shift collision -> PASS.
    {
        chain::DelayGate g = make_gate(10);
        chain::Gate7Inputs in;
        in.processed = 240; in.expected = 240;
        in.match_rate = 230.0 / 240.0;      // 0.9583
        in.min_match_rate = 0.90;
        in.nan_inf = 0;
        in.reset_count = 239; in.frame_count = 240; in.apply_count = 1;
        in.discipline_ok = true;
        in.delay = &g;
        check(chain::gate7_pass(in), "high aligned + low shift -> PASS");
    }

    // (4) low aligned (0.85) + no delay -> FAIL on the 0.90 floor.
    {
        chain::DelayGate g = make_gate(0);
        chain::Gate7Inputs in;
        in.processed = 240; in.expected = 240;
        in.match_rate = 0.85;
        in.min_match_rate = 0.90;
        in.nan_inf = 0;
        in.reset_count = 239; in.frame_count = 240; in.apply_count = 1;
        in.discipline_ok = true;
        in.delay = &g;
        check(!chain::gate7_pass(in), "low aligned (0.85) -> FAIL on 0.90 floor");
    }

    // (5) delay_detected alone blocks PASS, independent of match_rate.
    {
        chain::DelayGate g = make_gate(230);   // delay_detected == true
        chain::Gate7Inputs in;
        in.processed = 240; in.expected = 240;
        in.match_rate = 0.95;   // hypothetical high match
        in.min_match_rate = 0.90;
        in.nan_inf = 0;
        in.reset_count = 239; in.frame_count = 240; in.apply_count = 1;
        in.discipline_ok = true;
        in.delay = &g;
        check(!chain::gate7_pass(in), "delay_detected blocks PASS regardless of match_rate");
    }
}

// Strict per-condition discipline: each of the 8 conditions independently fails the
// verdict, plus null-delay fail-closed and empty-run fail.
void test_gate7_pass_strict() {
    chain::DelayGate clean = make_gate(10);   // no delay
    auto good = [&]() {
        chain::Gate7Inputs in;
        in.processed = 240; in.expected = 240;
        in.match_rate = 0.95; in.min_match_rate = 0.90;
        in.nan_inf = 0;
        in.reset_count = 239; in.frame_count = 240; in.apply_count = 1;
        in.discipline_ok = true;
        in.delay = &clean;
        return in;
    };

    check(chain::gate7_pass(good()), "baseline: all 8 conditions -> PASS");

    { auto in = good(); in.processed = 239;   check(!chain::gate7_pass(in), "processed != expected -> FAIL"); }
    { auto in = good(); in.match_rate = 0.899; check(!chain::gate7_pass(in), "match_rate < floor -> FAIL"); }
    { auto in = good(); in.nan_inf = 1;       check(!chain::gate7_pass(in), "nan_inf > 0 -> FAIL"); }
    { auto in = good(); in.reset_count = 238; check(!chain::gate7_pass(in), "reset_count != expected-1 -> FAIL"); }
    { auto in = good(); in.frame_count = 239; check(!chain::gate7_pass(in), "frame_count != expected -> FAIL"); }
    { auto in = good(); in.apply_count = 2;   check(!chain::gate7_pass(in), "apply_count != 1 -> FAIL"); }
    { auto in = good(); in.discipline_ok = false; check(!chain::gate7_pass(in), "discipline_ok false -> FAIL"); }
    {
        chain::DelayGate d = make_gate(230);
        auto in = good(); in.delay = &d;
        check(!chain::gate7_pass(in), "delay_detected -> FAIL");
    }
    { auto in = good(); in.delay = nullptr;   check(!chain::gate7_pass(in), "null delay -> FAIL (fail-closed)"); }
    {
        auto in = good();
        in.processed = 0; in.expected = 0; in.reset_count = 0; in.frame_count = 0;
        check(!chain::gate7_pass(in), "empty run -> FAIL");
    }
}

}  // namespace

int main() {
    std::printf("test_delay_gate\n");
    test_delay_signature_thresholds();
    test_gate7_pass_verdict();
    test_gate7_pass_strict();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
