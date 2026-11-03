#pragma once

// radioml_diagnostic_classify.hpp -- task fix10class24-classification-gate-separation1,
// Part B: the board-side diagnostic classification bypass for the single/dual-SDR
// direct/DC runners.
//
// The 0.100 payload-training-residual gate is a FIDELITY gate: it answers "did the RF
// chain preserve the TX signal well enough that the recovered payload is trustworthy".
// Classification is a DIFFERENT question: "given the recovered payload, which class".
// Part B separates the two by adding an OPT-IN, DIAGNOSTIC-ONLY bypass
// (`--diagnostic-force-classify`, default OFF) that classifies a frame whose SOLE
// rejection reason is a moderately-high residual (0.10 < residual <= 0.30) but whose
// alignment and every other validity check still pass.
//
// RED LINES (this header never violates them):
//   * The production 0.100 gate is NEVER rewritten.  The 19-column board_results.tsv
//     is byte-for-byte unchanged: a bypassed frame is still emitted there with
//     gated=0, gate_reject=1, board_pred=-1.  A diagnostic prediction is written to a
//     SEPARATE board_diagnostic_results.tsv and marked classification_layer =
//     NPU_BF16_DIAGNOSTIC / diagnostic_gate_bypass=1 in the per-frame .diag.json.
//   * The frozen recovery math (iq_rf_sync_recovery.hpp apply()/estimate()) is reused
//     VERBATIM.  The ONLY relaxed condition is rec.valid (set true on a local COPY
//     before calling apply()); the apply() safety guards on payload gain and payload
//     TX scale are KEPT and a throw there REFUSES the bypass.
//   * The bypass is fail-closed: any of the explicit conditions below not met, or
//     apply() refusing, means NO diagnostic classification (board_pred stays -1).

#include "iq_dual_sdr_coarse_cfo_recovery.hpp"  // iqrfrec + iqdual23fix10 + iqrftrain

#include <cmath>
#include <complex>
#include <vector>

namespace rml24diag {

// The classification layer that actually produced the prediction recorded for a frame.
constexpr const char* kClassificationLayerProduction   = "NPU_BF16_PRODUCTION";
constexpr const char* kClassificationLayerDiagnostic   = "NPU_BF16_DIAGNOSTIC";
constexpr const char* kClassificationLayerNotApplicable = "NOT_APPLICABLE";

// ---- explicit bypass conditions ---------------------------------------------
// A gate-rejected frame may be diagnostic-classified ONLY when ALL of the following
// hold.  `residual_reject`/`forceable` (computed by the runner) already imply
//   !gated  AND  rec.failure == PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH  AND  residual <= 0.30,
// which in estimate()'s check order further implies the EARLIER checks passed:
// preamble corr >= 0.9, payload-training gain finite/positive, payload-training corr
// >= 0.9.  We ADD the checks the residual gate SHORT-CIRCUITS (CFO/SRO come after the
// residual gate in estimate()) plus the capture-health checks, so that "alignment +
// recovery still pass validity checks" is literally true:
//
//   1. rec.failure == PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH   (sole failure = residual)
//   2. residual strictly exceeds 0.100                     (it actually gate-rejected)
//   3. residual <= hard_invalid_ceiling (0.30)             (not irrecoverable)
//   4. cfo_in_range                                        (coarse + fine CFO valid)
//   5. !rx_clipped                                         (no railed RX sample)
//   6. neg_pass                                            (negative control clean)
//   7. |rec.sro_ppm| <= max_sro_ppm                        (sampling-rate offset sane)
//
// The caller ANDs this with its own `--diagnostic-force-classify` flag (default OFF).
inline bool is_diagnostic_bypassable(
        const iqrfrec::PerFileRecovery& rec,
        double residual,
        bool cfo_in_range,
        bool rx_clipped,
        bool neg_pass,
        double max_sro_ppm,
        double hard_invalid_ceiling) {
    if (rec.failure != iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH) return false;
    if (!(residual > iqrfrec::kPayloadTrainingResidualMax)) return false;
    if (!(residual <= hard_invalid_ceiling)) return false;
    if (!cfo_in_range) return false;
    if (rx_clipped) return false;
    if (!neg_pass) return false;
    if (std::fabs(rec.sro_ppm) > max_sro_ppm) return false;
    return true;
}

// ---- diagnostic re-recovery -------------------------------------------------
// Reconstruct the coarse-CFO-derotated, fractionally-advanced capture that
// recover_payload_with_coarse_cfo() builds internally (its `aligned`), then run the
// EXACT frozen iqrfrec::apply() on it with only the rec.valid condition bypassed.
// Returns false (and leaves out_payload empty) if apply() refuses -- i.e. the payload
// gain or payload TX scale safety guard fired -- in which case the caller MUST NOT
// classify (fail-closed).
inline bool try_diagnostic_apply(
        const std::vector<std::complex<double>>& rx,   // deinterleaved capture (as passed
                                                       // to recover_payload_with_coarse_cfo)
        double coarse_cfo_hz,
        double fractional_timing_samples,
        const iqrfrec::PerFileRecovery& rec,           // residual-rejected recovery
        std::vector<std::complex<double>>& out_payload) {
    // 1) coarse de-rotation (verbatim recover_payload_with_coarse_cfo, lines ~252-258).
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * coarse_cfo_hz *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }
    // 2) fractional advance (the same frozen helper the recovery uses).
    const std::vector<std::complex<double>> aligned =
        iqdual23fix10::detail::apply_fractional_advance(derot, fractional_timing_samples);
    // 3) apply() with ONLY the `!rec.valid` throw bypassed.  The payload-gain and
    //    payload-TX-scale safety guards remain active; a throw here refuses the bypass.
    iqrfrec::PerFileRecovery rec_diag = rec;
    rec_diag.valid = true;
    try {
        out_payload = iqrfrec::apply(aligned, rec_diag);
    } catch (const std::exception&) {
        out_payload.clear();
        return false;
    }
    return true;
}

}  // namespace rml24diag
