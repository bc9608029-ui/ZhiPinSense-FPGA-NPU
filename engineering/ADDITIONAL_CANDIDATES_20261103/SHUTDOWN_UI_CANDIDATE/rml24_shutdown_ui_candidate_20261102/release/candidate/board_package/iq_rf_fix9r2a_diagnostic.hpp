#pragma once

// iq_rf_fix9r2a_diagnostic.hpp -- Route F fix9r2a Task B/D: the R8 2-sample
// DIAGNOSTIC sample selector + acceptance gate.
//
// WHY THIS EXISTS (Task A audit conclusion): the fix9r2 runner's existing
// --file-filter matches the ci16 FILE NAME (quantized_d2_2p56m_%06d.ci16), which
// carries NO modulation, and --max-files=2 truncates the FIRST TWO holdout files
// (000000 OOK, 000001 OOK) -- neither can select "1 BPSK + 1 4ASK".  The selector
// here matches the manifest `modulation` column over the HOLD-ONLY subset, leaves
// calibration untouched, and fail-closes when a named class is absent/under-filled.
//
// The diagnostic and 46-sample paths share the same payload-training residual limit
// (corr >= 0.90, residual <= 0.10).  The diagnostic can NEVER carry the regression
// PASS token because it is not a full accuracy run.
//
// iCraft-free and libiio-free: both functions are PURE (operate on plain data) so the
// selection + gate semantics are unit-testable with no device, NPU, or libiio.

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "iq_digital_loopback.hpp"   // iqdloop::FrozenIq
#include "iq_rf_sync_recovery.hpp"   // shared payload-training residual contract

namespace iqrffix9r2a {

// ---- Task B: R8 diagnostic sample selection (pure) ---------------------------
struct DiagnosticSelection {
    bool ok = false;                       // every named class had >= per_class files
    std::string report;                    // per-class have/need summary (empty on ok)
    std::string selected_classes;          // comma-joined, in request order
    std::vector<std::size_t> selected_index;  // indices into the caller's holdout
};

// Select exactly `per_class` HOLD-ONLY files per named modulation (matched on
// FrozenIq::modulation == the manifest `modulation` column -- never the file name).
// Calibration is the caller's to preserve (this only reads `holdout`).  Fail-closed:
// a named class with fewer than `per_class` matches fails the whole selection.
inline DiagnosticSelection select_diagnostic_holdout(
        const std::vector<iqdloop::FrozenIq>& holdout,
        const std::vector<std::string>& classes,
        std::size_t per_class) {
    DiagnosticSelection sel;
    sel.ok = true;
    if (per_class == 0) { sel.ok = false; sel.report = "per_class=0;"; return sel; }
    if (classes.empty()) { sel.ok = false; sel.report = "no-classes;"; return sel; }
    for (const std::string& name : classes) {
        if (!sel.selected_classes.empty()) sel.selected_classes += ",";
        sel.selected_classes += name;
        std::vector<std::size_t> hits;
        for (std::size_t i = 0; i < holdout.size(); ++i)
            if (holdout[i].modulation == name) hits.push_back(i);
        if (hits.size() < per_class) {
            sel.ok = false;
            sel.report += "class:" + name + " have=" + std::to_string(hits.size()) +
                          " need=" + std::to_string(per_class) + ";";
        }
        for (std::size_t k = 0; k < hits.size() && k < per_class; ++k)
            sel.selected_index.push_back(hits[k]);
    }
    return sel;
}

// ---- Task D: R8 diagnostic acceptance gate (pure) ----------------------------
struct DiagnosticGateInput {
    std::string requested_classes;         // e.g. "BPSK,4ASK"
    std::string selected_classes;          // e.g. "BPSK,4ASK" (in request order)
    std::size_t requested_count = 0;       // == classes.size() * per_class
    std::size_t holdout_files = 0;
    std::size_t estimate_computed = 0;
    std::size_t estimate_valid = 0;
    std::size_t frame_layout_match = 0;
    std::size_t training_exact_match = 0;
    std::size_t settling_guard_exact_zero = 0;   // fix9r2g: settling-zero zone all zero
    std::size_t payload_training_exact_match = 0;// fix9r2g: training block exact match
    std::size_t payload_exact_match = 0;
    std::size_t tx_push_ok = 0;
    std::size_t tx_clipped = 0;
    std::size_t rx_clipped = 0;
    double training_corr_min = 0.0;        // min over the selected files
    double payload_training_residual_max = 0.0; // fix9r2g: migrated residual<=0.10 gate
    double payload_scale_error_max = 0.0;  // fix9r2g: R8-only scale-error audit (<= 0.05)
    std::size_t scored = 0;                // fix9r2g: files actually classified
    std::size_t rf_excluded = 0;           // fix9r2g: files excluded for RF distortion
    std::size_t prediction_agreement = 0;  // fix9r2g: rf_pred == frozen_baseline_pred count
    bool restore_ok = false;
};

struct DiagnosticGateResult {
    bool pass = false;
    std::string report;                    // empty on pass
};

inline DiagnosticGateResult evaluate_diagnostic_gate(const DiagnosticGateInput& g) {
    DiagnosticGateResult r;
    std::string why;
    auto fail = [&](const std::string& m) { if (why.empty()) why = m; };
    if (g.selected_classes != g.requested_classes)
        fail("selected_classes=" + g.selected_classes + "!=" + g.requested_classes);
    if (g.holdout_files != g.requested_count)
        fail("holdout_files=" + std::to_string(g.holdout_files) +
             "!=requested=" + std::to_string(g.requested_count));
    if (g.estimate_computed != g.holdout_files)
        fail("estimate_computed=" + std::to_string(g.estimate_computed) + "/" +
             std::to_string(g.holdout_files));
    if (g.estimate_valid != g.holdout_files)
        fail("estimate_valid=" + std::to_string(g.estimate_valid) + "/" +
             std::to_string(g.holdout_files));
    if (g.frame_layout_match != g.holdout_files)
        fail("frame_layout_match=" + std::to_string(g.frame_layout_match) + "/" +
             std::to_string(g.holdout_files));
    if (g.training_exact_match != g.holdout_files)
        fail("training_exact_match=" + std::to_string(g.training_exact_match) + "/" +
             std::to_string(g.holdout_files));
    if (g.settling_guard_exact_zero != g.holdout_files)
        fail("settling_guard_exact_zero=" + std::to_string(g.settling_guard_exact_zero) + "/" +
             std::to_string(g.holdout_files));
    if (g.payload_training_exact_match != g.holdout_files)
        fail("payload_training_exact_match=" + std::to_string(g.payload_training_exact_match) + "/" +
             std::to_string(g.holdout_files));
    if (g.payload_exact_match != g.holdout_files)
        fail("payload_exact_match=" + std::to_string(g.payload_exact_match) + "/" +
             std::to_string(g.holdout_files));
    if (g.tx_push_ok != g.holdout_files)
        fail("tx_push_ok=" + std::to_string(g.tx_push_ok) + "/" +
             std::to_string(g.holdout_files));
    if (g.tx_clipped != 0)
        fail("tx_clipped=" + std::to_string(g.tx_clipped));
    if (g.rx_clipped != 0)
        fail("rx_clipped=" + std::to_string(g.rx_clipped));
    if (g.training_corr_min < 0.90)
        fail("training_corr_min=" + std::to_string(g.training_corr_min) + "<0.90");
    if (g.payload_training_residual_max > iqrfrec::kPayloadTrainingResidualMax)
        fail("payload_training_residual_max=" +
             std::to_string(g.payload_training_residual_max) + ">0.10");
    if (g.payload_scale_error_max > 0.05)
        fail("payload_scale_error_max=" + std::to_string(g.payload_scale_error_max) + ">0.05");
    if (g.scored != g.holdout_files)
        fail("scored=" + std::to_string(g.scored) + "/" + std::to_string(g.holdout_files));
    if (g.rf_excluded != 0)
        fail("rf_excluded=" + std::to_string(g.rf_excluded));
    if (g.prediction_agreement != g.holdout_files)
        fail("prediction_agreement=" + std::to_string(g.prediction_agreement) + "/" +
             std::to_string(g.holdout_files));
    if (!g.restore_ok)
        fail("restore_ok=false");
    r.pass = why.empty();
    r.report = why;
    return r;
}

}  // namespace iqrffix9r2a
