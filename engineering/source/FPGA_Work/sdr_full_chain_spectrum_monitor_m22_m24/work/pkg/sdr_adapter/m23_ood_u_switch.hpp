#pragma once

// m23_ood_u_switch.hpp -- switchable OOD-U interface (M23 P0, priority "C").
//
// Wraps the frozen M20 CPU-side OOD-U detector (ood_u_detector.hpp/.cpp) behind
// an explicit on/off switch.  The switch is OFF by default and, while OFF,
// classify() is a plain argmax -- BYTE-IDENTICAL to the M22 producer path, so
// enabling the interface is a pure increment that never changes existing output.
//
// When ON, the frozen manifest drives score method / temperature / threshold
// (logit_margin, higher_is_ood), and a rejected frame is labelled
// UNKNOWN_EXPERIMENTAL -- never the plain UNKNOWN of the M20 module, and never a
// claim of reliability (near/far rejection is ~6.03%/10.33% on the frozen model,
// i.e. experimental).
//
// Two independent "off" layers exist, matching the integration-baseline audit:
//   1. switch disabled          -- OOD-U is not consulted at all (plain argmax)
//   2. switch ON + threshold    -- a +1e30 threshold can never fire the reject
//      (+1e30)                     branch, reproducing the plain argmax exactly
//
// iCraft-free.  The detector is constructed only when enabled (std::optional),
// so the disabled path performs no manifest load and no extra work.

#include <optional>

#include "m23_contract.hpp"
#include "ood_u_contract.hpp"
#include "ood_u_detector.hpp"
#include "ood_threshold_manifest.hpp"

namespace m23 {

struct OodSwitchResult {
    bool enabled = false;    // OOD-U was consulted for this frame
    bool rejected = false;   // -> UNKNOWN_EXPERIMENTAL
    bool error = false;      // -> ERROR (non-finite logits)
    int class_index = -1;    // argmax 0..11 when accepted
    double score = 0.0;      // OOD-U anomaly score (higher = more OOD)
};

class M23OodSwitch {
public:
    M23OodSwitch() = default;  // disabled

    void enable(const OodThresholdManifest& manifest) { detector_.emplace(manifest); }
    void disable() { detector_.reset(); }
    bool enabled() const { return detector_.has_value(); }

    // Classify one 12-d raw (pre-softmax) logit vector.  While disabled this is
    // exactly the M22 argmax loop (no non-finite guard, ties keep the lower
    // index) so the output is byte-identical to the baseline.
    OodSwitchResult classify(const double* logits, int dim) const {
        if (!detector_.has_value()) {
            return OodSwitchResult{false, false, false,
                                   plain_argmax(logits, dim), 0.0};
        }
        const OodDecision d = detector_->classify_or_reject(logits, dim);
        OodSwitchResult r;
        r.enabled = true;
        r.score = d.score;
        if (!d.valid) {                       // non-finite logits -> ERROR
            r.error = true;
            r.rejected = false;
            r.class_index = -1;
        } else if (d.known) {                 // accepted known class
            r.error = false;
            r.rejected = false;
            r.class_index = d.class_index;
        } else {                              // rejected -> UNKNOWN_EXPERIMENTAL
            r.error = false;
            r.rejected = true;
            r.class_index = -1;
        }
        return r;
    }

    // Convenience overload for float logits (the real NPU path is fp32).  The
    // frozen model always yields exactly OUTPUT_DIM logits, so anything shorter
    // is zero-padded and anything longer is truncated to the contract width.
    OodSwitchResult classify(const float* logits, int dim) const {
        double tmp[ood_u_contract::OUTPUT_DIM];
        const int n = dim < ood_u_contract::OUTPUT_DIM ? dim : ood_u_contract::OUTPUT_DIM;
        for (int i = 0; i < n; ++i) tmp[i] = static_cast<double>(logits[i]);
        for (int i = n; i < ood_u_contract::OUTPUT_DIM; ++i) tmp[i] = 0.0;
        return classify(tmp, ood_u_contract::OUTPUT_DIM);
    }

private:
    static int plain_argmax(const double* logits, int dim) {
        int argmax = 0;
        for (int i = 1; i < dim; ++i) {
            if (logits[i] > logits[argmax]) argmax = i;
        }
        return argmax;
    }

    std::optional<OodUDetector> detector_;
};

}  // namespace m23
