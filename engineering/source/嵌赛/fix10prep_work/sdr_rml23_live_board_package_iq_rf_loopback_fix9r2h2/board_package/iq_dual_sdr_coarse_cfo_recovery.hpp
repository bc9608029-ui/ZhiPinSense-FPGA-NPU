#pragma once

// iq_dual_sdr_coarse_cfo_recovery.hpp -- the fix10 dual-SDR recovery sequencing: apply
// a robust COARSE CFO BEFORE the fine timing/CFO estimate.  This is the fix10
// distinction between the single-SDR Route F runner and the two-Pluto dual-SDR runner,
// isolated here (NOT in the heavy runner header) so the host test exercises the exact
// recovery math without the NPU / libiio / chain.
//
// iq_rf_sync_recovery.hpp records `coarse_cfo_hz` (the differential Zadoff-Chu CFO,
// unambiguous over +/-fs/2 == +/-1.28 MHz) but deliberately does NOT apply it --
// same-Pluto fix9r2 has ~0 CFO.  Two free-running Plutos carry a kHz-scale carrier
// offset (each LO locked to its own reference crystal), which the FINE CFO
// (unambiguous over +/-fs/(2*kTailStart) ~ +/-21.7 Hz) cannot measure without
// aliasing.  The sequence is therefore:
//
//   1. estimate(rx)          -> finds the preamble
//   2. robust coarse CFO     -> LS-gain phase difference preamble vs payload-domain
//                               training block (see below), NOT the differential
//   3. de-rotate the WHOLE capture by exp(-j 2*pi*coarse_cfo_hz*n/fs)
//   4. estimate(de-rotated)  -> the FINE cfo_hz is now only the small residual
//   5. rec.payload_tx_scale = payload_tx_scale; apply(de-rotated, rec)
//
// WHY NOT the differential CFO: the single-block differential CFO d[k]=u[k]conj(u[k-1])
// correlates against a reference tone whose phase assumes the ZC starts on an INTEGER
// sample.  In a CYCLIC dual-SDR capture the preamble lands on an arbitrary FRACTIONAL
// sample offset tau (accumulated rx_stream_pos + SRO + CFO-shifted peak), and that
// fractional offset enters the differential as a constant phase -2*pi*tau/N -- i.e. a
// spurious CFO of -tau*fs/N, up to +/-fs/(2N) == +/-1250 Hz.  tau is unknowable from
// one block alone (fractional delay and frequency are coupled over a single block; a
// parabolic correlation-peak fit is itself shifted by the CFO), so the differential
// cannot serve as the coarse CFO.  The preamble-vs-training-block LS-gain phase
// difference instead CANCELS tau: each LS gain absorbs its own block's fractional
// offset, and the CFO phase spread over each 1024-sample block is identical, so the
// phase difference is exactly the CFO over the kPayloadTrainingOffset==2048 baseline.
// That makes it robust to tau; its unambiguous range is
// +/-fs/(2*kPayloadTrainingOffset) == +/-625 Hz, which covers the dual-SDR carrier
// offset the fix10 board test targets (a residual beyond +/-625 Hz is an infra
// failure, not a recoverable offset).
//
// The recovery math (iq_rf_sync_recovery.hpp) is RED-LINE and untouched; this header
// only sequences its estimate()/apply() around the coarse pre-rotation.

#include "iq_rf_sync_recovery.hpp"
#include "iq_rf_training_frame.hpp"

#include <cmath>
#include <complex>
#include <cstddef>
#include <vector>

namespace iqdual23fix10 {

// ---------------------------------------------------------------------------
// CoarseCfoRecovery -- the fix10 dual-SDR recovery result.
// ---------------------------------------------------------------------------
struct CoarseCfoRecovery {
    iqrfrec::PerFileRecovery rec;              // final recovery (computed on the
                                               // coarse-de-rotated capture)
    double coarse_cfo_hz = 0.0;                // the robust coarse CFO applied
    std::vector<std::complex<double>> payload; // recovered payload (empty if !rec.valid)
};

// Apply a robust COARSE CFO before the fine timing/CFO estimate, then return the
// final per-file recovery.  The coarse pre-rotation is anchored at capture sample 0
// (a constant phase vs. the burst-relative apply() anchoring is absorbed by the
// per-file complex gain, exactly as the single-SDR path absorbs the preamble-relative
// CFO anchoring).  The final rec.cfo_hz is therefore only the small residual left
// after the coarse correction.
inline CoarseCfoRecovery recover_payload_with_coarse_cfo(
        const std::vector<std::complex<double>>& rx,
        const iqrfrec::EstimateConfig& cfg,
        double payload_tx_scale) {
    CoarseCfoRecovery out;

    // Pass 1: preamble search only (its timing is the anchor for the coarse CFO; its
    // differential coarse_cfo_hz is deliberately NOT used -- see the header rationale).
    const iqrfrec::PerFileRecovery rec1 = iqrfrec::estimate(rx, cfg);

    // Robust coarse CFO: LS-gain phase difference between the ZC preamble (offset 0)
    // and the payload-domain 16QAM training block (offset kPayloadTrainingOffset).
    // Each LS gain absorbs its own block's fractional-offset phase, and the CFO phase
    // spread over each 1024-sample block cancels in the difference, so this is robust
    // to the arbitrary cyclic-capture fractional offset tau (which the single-block
    // differential CFO cannot survive).  Unambiguous over +/-fs/(2*kPayloadTrainingOffset).
    out.coarse_cfo_hz = 0.0;
    const std::size_t best = rec1.timing_offset;
    if (best + iqrftrain::kPayloadTrainingOffset + iqrftrain::kPayloadTrainingComplex <=
        rx.size()) {
        const std::complex<double> a_pre =
            iqrfrec::detail::ls_gain(rx, best, iqrftrain::preamble_complex());
        const std::complex<double> a_pt = iqrfrec::detail::ls_gain(
            rx, best + iqrftrain::kPayloadTrainingOffset,
            iqrftrain::payload_gain_training_complex());
        const double med =
            std::arg(a_pt * std::conj(a_pre)) * static_cast<double>(iqrftrain::kFs) /
            (2.0 * iqrftrain::kPi * static_cast<double>(iqrftrain::kPayloadTrainingOffset));
        if (std::isfinite(med)) out.coarse_cfo_hz = med;
    }

    // De-rotate the WHOLE capture by -coarse_cfo_hz (a pure per-sample phase ramp).
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * out.coarse_cfo_hz *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }

    // Pass 2: re-estimate on the coarse-de-rotated capture; the fine CFO is now the
    // small residual, and the payload-domain gain/corr/residual are all consistent.
    out.rec = iqrfrec::estimate(derot, cfg);
    out.rec.payload_tx_scale = payload_tx_scale;
    if (out.rec.valid)
        out.payload = iqrfrec::apply(derot, out.rec);
    return out;
}

}  // namespace iqdual23fix10
