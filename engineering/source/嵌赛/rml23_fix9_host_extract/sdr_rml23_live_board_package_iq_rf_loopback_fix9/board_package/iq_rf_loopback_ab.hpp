#pragma once

// iq_rf_loopback_ab.hpp -- Stage H-F / Route F fix8 Task F: the D-vs-D2 A/B gate.
//
// Route F's D-vs-D2 A/B run (physical RF self-loopback, D and D2 recovered
// references interleaved over the SAME capture) is REFUSED unless every
// precondition is satisfied.  The preconditions are, in strict order:
//
//   1. Route D  artifact audit == PASS   (scripts/audit_route_d_artifacts.py)
//   2. Route D2 artifact audit == PASS   (audit_route_d_artifacts.py on the D2 dir)
//   3. RF safe-operating point selected  (--phase=iq-rf-loopback-level-sweep)
//   4. RF_PRESERVES_IQ                   (--phase=iq-rf-loopback fidelity verdict)
//   5. no clipping                       (tx_clipped == 0 && rx_clipped == 0)
//   6. negative control stable           (3-window noise floor agreed)
//
// The gate is PURE and fail-closed: any unsatisfied precondition => allowed ==
// false, `reason` names the FIRST failing gate (in the order above), and the
// runner must NOT emit on the RF port.  This header never opens a device and never
// runs the NPU, so it is fully host-testable.  It never issues a classification or
// accuracy verdict -- the A/B run's classification outcome is measurement-only and
// only ever established on the board.
//
// The A/B run itself additionally holds the SAME physical connection / attenuation
// / gain / global calibration for D and D2 (one global gain from the calibration
// subset, never a per-file oracle), and proceeds per-class small-sample first then
// the full 240.  Those are RUNNER invariants (see iq_rf_loopback_runner.hpp and the
// board-side A/B procedure), not separately checkable gates.

#include <string>

namespace iqrfloop_ab {

// Canonical gate names, in the strict evaluation order.
inline const char* kGateRouteDAudit = "ROUTE_D_ARTIFACT_AUDIT_PASS";
inline const char* kGateD2Audit = "ROUTE_D2_ARTIFACT_AUDIT_PASS";
inline const char* kGateSweep = "RF_SAFE_OPERATING_POINT_SELECTED";
inline const char* kGatePreservesIq = "RF_PRESERVES_IQ";
inline const char* kGateNoClip = "NO_CLIPPING";
inline const char* kGateNegControl = "NEGATIVE_CONTROL_STABLE";

struct RouteFAbGateInput {
    bool route_d_audit_ok = false;   // Route D artifact audit == PASS
    bool d2_audit_ok = false;        // Route D2 artifact audit == PASS
    bool sweep_selected = false;     // RF safe operating point selected
    bool rf_preserves_iq = false;    // RF fidelity == RF_PRESERVES_IQ
    bool no_clip = false;            // tx_clipped == 0 && rx_clipped == 0
    bool negative_control_stable = false;  // 3-window noise floor stable
};

struct RouteFAbGateResult {
    bool allowed = false;
    std::string reason;    // first failing gate name, or "" when allowed
    std::string missing;   // comma-separated names of all failing gates
};

// Evaluate the 6 gates in strict order.  allowed == (all gates satisfied).
inline RouteFAbGateResult route_f_ab_gate(const RouteFAbGateInput& in) {
    struct Gate { const char* name; bool ok; };
    const Gate gates[6] = {
        {kGateRouteDAudit, in.route_d_audit_ok},
        {kGateD2Audit,     in.d2_audit_ok},
        {kGateSweep,       in.sweep_selected},
        {kGatePreservesIq, in.rf_preserves_iq},
        {kGateNoClip,      in.no_clip},
        {kGateNegControl,  in.negative_control_stable},
    };

    RouteFAbGateResult r;
    r.allowed = true;
    std::string missing;
    for (const Gate& g : gates) {
        if (!g.ok) {
            r.allowed = false;
            if (r.reason.empty())
                r.reason = g.name;       // FIRST failing gate, strict order
            if (!missing.empty())
                missing += ",";
            missing += g.name;
        }
    }
    r.missing = missing;
    return r;
}

// Single gate name + boolean for a machine-parseable per-gate line.
struct RouteFAbGateLine {
    const char* name;
    bool ok;
};

inline void route_f_ab_gate_lines(const RouteFAbGateInput& in,
                                  RouteFAbGateLine out[6]) {
    out[0] = {kGateRouteDAudit, in.route_d_audit_ok};
    out[1] = {kGateD2Audit,     in.d2_audit_ok};
    out[2] = {kGateSweep,       in.sweep_selected};
    out[3] = {kGatePreservesIq, in.rf_preserves_iq};
    out[4] = {kGateNoClip,      in.no_clip};
    out[5] = {kGateNegControl,  in.negative_control_stable};
}

}  // namespace iqrfloop_ab
