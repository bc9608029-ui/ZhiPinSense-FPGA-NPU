// test_iq_rf_loopback_ab.cpp -- host tests for Stage H-F / Route F fix8 Task F:
// the D-vs-D2 A/B gate.  Exercises route_f_ab_gate() -- a pure, fail-closed gate
// that REFUSES the physical-RF D-vs-D2 A/B run unless all six preconditions hold.
//
// Covered here (no device, no NPU):
//   * all six gates satisfied -> allowed == true, reason == "", missing == "";
//   * each gate individually unsatisfied -> allowed == false and reason names
//     exactly that gate (fail-closed);
//   * when several gates fail, reason is the FIRST failing gate in the canonical
//     order (Route D audit -> D2 audit -> sweep -> RF_PRESERVES_IQ -> no-clip ->
//     negative-control-stable) while `missing` lists every failing gate;
//   * route_f_ab_gate_lines() emits the same six per-gate booleans as the input.

#include "../board_package/iq_rf_loopback_ab.hpp"

#include <cstdio>
#include <string>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

iqrfloop_ab::RouteFAbGateInput all_ok() {
    iqrfloop_ab::RouteFAbGateInput in;
    in.route_d_audit_ok = true;
    in.d2_audit_ok = true;
    in.sweep_selected = true;
    in.rf_preserves_iq = true;
    in.no_clip = true;
    in.negative_control_stable = true;
    return in;
}

void test_all_pass_allowed() {
    const auto r = iqrfloop_ab::route_f_ab_gate(all_ok());
    check(r.allowed, "gate: all six satisfied -> allowed");
    check(r.reason.empty(), "gate: allowed -> empty reason");
    check(r.missing.empty(), "gate: allowed -> empty missing set");
}

void test_each_gate_fail_closed() {
    const char* names[] = {
        iqrfloop_ab::kGateRouteDAudit, iqrfloop_ab::kGateD2Audit,
        iqrfloop_ab::kGateSweep, iqrfloop_ab::kGatePreservesIq,
        iqrfloop_ab::kGateNoClip, iqrfloop_ab::kGateNegControl,
    };
    for (int i = 0; i < 6; ++i) {
        iqrfloop_ab::RouteFAbGateInput in = all_ok();
        if (i == 0) in.route_d_audit_ok = false;
        if (i == 1) in.d2_audit_ok = false;
        if (i == 2) in.sweep_selected = false;
        if (i == 3) in.rf_preserves_iq = false;
        if (i == 4) in.no_clip = false;
        if (i == 5) in.negative_control_stable = false;
        const auto r = iqrfloop_ab::route_f_ab_gate(in);
        check(!r.allowed, std::string("gate: ") + names[i] + " false -> blocked");
        check(r.reason == names[i],
              std::string("gate: reason names ") + names[i] + " (got " + r.reason + ")");
        check(r.missing == names[i],
              std::string("gate: missing == ") + names[i]);
    }
}

void test_first_failing_gate_named() {
    // Route D audit and no-clip both fail; reason must be the FIRST (Route D audit).
    iqrfloop_ab::RouteFAbGateInput in = all_ok();
    in.route_d_audit_ok = false;
    in.no_clip = false;
    const auto r = iqrfloop_ab::route_f_ab_gate(in);
    check(!r.allowed, "gate: two gates failing -> blocked");
    check(r.reason == iqrfloop_ab::kGateRouteDAudit,
          "gate: reason names the FIRST failing gate (Route D audit)");
    check(r.missing == std::string(iqrfloop_ab::kGateRouteDAudit) + "," +
                       iqrfloop_ab::kGateNoClip,
          "gate: missing lists both failing gates in order");
}

void test_any_gate_blocks() {
    // Exhaustive: flipping exactly one gate off always blocks (fail-closed).
    iqrfloop_ab::RouteFAbGateInput base = all_ok();
    bool* fields[6] = {
        &base.route_d_audit_ok, &base.d2_audit_ok, &base.sweep_selected,
        &base.rf_preserves_iq, &base.no_clip, &base.negative_control_stable,
    };
    int blocked = 0;
    for (int i = 0; i < 6; ++i) {
        iqrfloop_ab::RouteFAbGateInput in = all_ok();
        bool* f = fields[i];
        (void)f;
        // rebind to the corresponding field of `in`
        if (i == 0) in.route_d_audit_ok = false;
        if (i == 1) in.d2_audit_ok = false;
        if (i == 2) in.sweep_selected = false;
        if (i == 3) in.rf_preserves_iq = false;
        if (i == 4) in.no_clip = false;
        if (i == 5) in.negative_control_stable = false;
        if (!iqrfloop_ab::route_f_ab_gate(in).allowed) ++blocked;
    }
    check(blocked == 6, "gate: every single-gate failure blocks the A/B run");
}

void test_gate_lines() {
    iqrfloop_ab::RouteFAbGateInput in = all_ok();
    in.no_clip = false;
    iqrfloop_ab::RouteFAbGateLine lines[6];
    iqrfloop_ab::route_f_ab_gate_lines(in, lines);
    bool ok = true;
    for (int i = 0; i < 6; ++i) {
        const bool want = (i != 4);   // only no-clip is false
        if (lines[i].ok != want) ok = false;
    }
    check(ok, "gate: route_f_ab_gate_lines matches the input booleans");
    check(std::string(lines[0].name) == iqrfloop_ab::kGateRouteDAudit,
          "gate: line 0 name is Route D audit");
    check(std::string(lines[5].name) == iqrfloop_ab::kGateNegControl,
          "gate: line 5 name is negative-control-stable");
}

}  // namespace

int main() {
    std::printf("test_iq_rf_loopback_ab\n");
    test_all_pass_allowed();
    test_each_gate_fail_closed();
    test_first_failing_gate_named();
    test_any_gate_blocks();
    test_gate_lines();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
