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
#include <limits>
#include <vector>

namespace iqdual23fix10 {

// ---------------------------------------------------------------------------
// CoarseCfoRecovery -- the fix10 dual-SDR recovery result.
// ---------------------------------------------------------------------------
struct CoarseCfoRecovery {
    iqrfrec::PerFileRecovery rec;              // final recovery (computed on the
                                               // coarse-de-rotated capture)
    double coarse_cfo_hz = 0.0;                // the robust coarse CFO applied
    double fractional_timing_samples = 0.0;    // sub-sample advance applied after
                                               // coarse CFO, in [-0.5, +0.5]
    double fractional_corr_before = 0.0;        // integer-grid ZC correlation
    double fractional_corr_after = 0.0;         // correlation at selected fraction
    // Diagnostic-only payload-training scan.  These fields never participate in
    // recovery or gating; they reveal whether a different, label-free fractional
    // alignment would fit the common payload-training block better.
    double payload_fractional_corr_before = 0.0;
    double payload_fractional_corr_after = 0.0;
    double payload_best_fractional_timing_samples = 0.0;
    double payload_best_fractional_corr = 0.0;
    double payload_best_fractional_preamble_corr = 0.0;
    std::vector<std::complex<double>> payload; // recovered payload (empty if !rec.valid)
};

namespace detail {

constexpr int kFractionalSincRadius = 12;

inline double sinc_pi(double x) {
    if (std::fabs(x) < 1e-12) return 1.0;
    const double px = iqrftrain::kPi * x;
    return std::sin(px) / px;
}

// Band-limited fractional sample used only by the dual-SDR path.  A Lanczos-windowed
// sinc is required here: the broadband ZC occupies the full Nyquist band, so linear
// interpolation can itself depress its correlation.  Integer positions are exact.
inline std::complex<double> sample_fractional(
        const std::vector<std::complex<double>>& x, double at) {
    const long center = static_cast<long>(std::floor(at));
    std::complex<double> sum(0.0, 0.0);
    double weight_sum = 0.0;
    for (long m = center - kFractionalSincRadius + 1;
         m <= center + kFractionalSincRadius; ++m) {
        if (m < 0 || static_cast<std::size_t>(m) >= x.size()) continue;
        const double d = at - static_cast<double>(m);
        if (std::fabs(d) >= static_cast<double>(kFractionalSincRadius)) continue;
        const double w = sinc_pi(d) *
                         sinc_pi(d / static_cast<double>(kFractionalSincRadius));
        sum += x[static_cast<std::size_t>(m)] * w;
        weight_sum += w;
    }
    return std::fabs(weight_sum) > 1e-12 ? sum / weight_sum : sum;
}

inline double fractional_preamble_corr(
        const std::vector<std::complex<double>>& rx, std::size_t integer_start,
        double frac, const std::vector<std::complex<double>>& pre) {
    if (pre.empty() || integer_start >= rx.size()) return 0.0;
    double num_r = 0.0, num_i = 0.0, den_rx = 0.0, den_ref = 0.0;
    for (std::size_t k = 0; k < pre.size(); ++k) {
        const double at = static_cast<double>(integer_start + k) + frac;
        if (at < 0.0 || at > static_cast<double>(rx.size() - 1)) return 0.0;
        const std::complex<double> s = sample_fractional(rx, at);
        const std::complex<double>& p = pre[k];
        num_r += s.real() * p.real() + s.imag() * p.imag();
        num_i += s.imag() * p.real() - s.real() * p.imag();
        den_rx += std::norm(s);
        den_ref += std::norm(p);
    }
    const double den = std::sqrt(den_rx * den_ref);
    return den > 0.0 ? std::sqrt(num_r * num_r + num_i * num_i) / den : 0.0;
}

inline double fractional_reference_corr(
        const std::vector<std::complex<double>>& rx, std::size_t integer_start,
        double frac, const std::vector<std::complex<double>>& ref) {
    if (ref.empty() || integer_start >= rx.size()) return 0.0;
    double num_r = 0.0, num_i = 0.0, den_rx = 0.0, den_ref = 0.0;
    for (std::size_t k = 0; k < ref.size(); ++k) {
        const double at = static_cast<double>(integer_start + k) + frac;
        if (at < 0.0 || at > static_cast<double>(rx.size() - 1)) return 0.0;
        const std::complex<double> s = sample_fractional(rx, at);
        const std::complex<double>& r = ref[k];
        num_r += s.real() * r.real() + s.imag() * r.imag();
        num_i += s.imag() * r.real() - s.real() * r.imag();
        den_rx += std::norm(s);
        den_ref += std::norm(r);
    }
    const double den = std::sqrt(den_rx * den_ref);
    return den > 0.0 ? std::sqrt(num_r * num_r + num_i * num_i) / den : 0.0;
}

struct FractionalTiming {
    double samples = 0.0;
    double corr = 0.0;
};

inline FractionalTiming estimate_fractional_timing(
        const std::vector<std::complex<double>>& rx, std::size_t integer_start) {
    const std::vector<std::complex<double>> pre = iqrftrain::preamble_complex();
    FractionalTiming best;
    best.corr = fractional_preamble_corr(rx, integer_start, 0.0, pre);

    // Deterministic two-stage grid: 1/32 sample across one integer cell, then 1/512
    // around the best coarse point.  No label/payload data participates.
    constexpr int coarse_den = 32;
    for (int q = -coarse_den / 2; q <= coarse_den / 2; ++q) {
        const double f = static_cast<double>(q) / static_cast<double>(coarse_den);
        const double c = fractional_preamble_corr(rx, integer_start, f, pre);
        if (c > best.corr) { best.samples = f; best.corr = c; }
    }
    const double coarse_best = best.samples;
    constexpr int refine_den = 512;
    for (int q = -16; q <= 16; ++q) {
        const double f = coarse_best +
                         static_cast<double>(q) / static_cast<double>(refine_den);
        if (f < -0.5 || f > 0.5) continue;
        const double c = fractional_preamble_corr(rx, integer_start, f, pre);
        if (c > best.corr) { best.samples = f; best.corr = c; }
    }
    return best;
}

inline FractionalTiming estimate_fractional_timing_for_reference(
        const std::vector<std::complex<double>>& rx, std::size_t integer_start,
        const std::vector<std::complex<double>>& ref) {
    FractionalTiming best;
    best.corr = fractional_reference_corr(rx, integer_start, 0.0, ref);
    constexpr int coarse_den = 32;
    for (int q = -coarse_den / 2; q <= coarse_den / 2; ++q) {
        const double f = static_cast<double>(q) / static_cast<double>(coarse_den);
        const double c = fractional_reference_corr(rx, integer_start, f, ref);
        if (c > best.corr) { best.samples = f; best.corr = c; }
    }
    const double coarse_best = best.samples;
    constexpr int refine_den = 512;
    for (int q = -16; q <= 16; ++q) {
        const double f = coarse_best +
                         static_cast<double>(q) / static_cast<double>(refine_den);
        if (f < -0.5 || f > 0.5) continue;
        const double c = fractional_reference_corr(rx, integer_start, f, ref);
        if (c > best.corr) { best.samples = f; best.corr = c; }
    }
    return best;
}

inline std::vector<std::complex<double>> apply_fractional_advance(
        const std::vector<std::complex<double>>& rx, double frac) {
    if (std::fabs(frac) < 1e-12) return rx;
    std::vector<std::complex<double>> out(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double at = static_cast<double>(n) + frac;
        if (at < 0.0 || at > static_cast<double>(rx.size() - 1))
            out[n] = std::complex<double>(0.0, 0.0);
        else
            out[n] = sample_fractional(rx, at);
    }
    return out;
}

}  // namespace detail

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

    // Pass 2: obtain the integer timing anchor after coarse CFO removal.  Independent
    // Pluto sample clocks leave an arbitrary fractional-sample phase; on a full-band
    // ZC, an offset near 0.5 sample can depress the integer-grid correlation to ~0.64
    // even on a clean link while the narrowband payload training remains near 1.0.
    const iqrfrec::PerFileRecovery integer_rec = iqrfrec::estimate(derot, cfg);
    out.fractional_corr_before = integer_rec.training_corr;
    const detail::FractionalTiming ft =
        detail::estimate_fractional_timing(derot, integer_rec.timing_offset);
    out.fractional_timing_samples = ft.samples;
    out.fractional_corr_after = ft.corr;

    // Instrument the common payload-domain training block on the same fractional
    // grid.  This deliberately does NOT alter `ft`, the aligned capture, or any
    // threshold.  A large difference between the preamble-selected and payload-
    // selected fractions is evidence for sequence-dependent group delay / peak
    // selection and gives the next fix an exact target instead of guessing.
    const std::vector<std::complex<double>> payload_training =
        iqrftrain::payload_gain_training_complex();
    const std::size_t payload_training_start =
        integer_rec.timing_offset + iqrftrain::kPayloadTrainingOffset;
    out.payload_fractional_corr_before = detail::fractional_reference_corr(
        derot, payload_training_start, 0.0, payload_training);
    out.payload_fractional_corr_after = detail::fractional_reference_corr(
        derot, payload_training_start, ft.samples, payload_training);
    const detail::FractionalTiming payload_ft =
        detail::estimate_fractional_timing_for_reference(
            derot, payload_training_start, payload_training);
    out.payload_best_fractional_timing_samples = payload_ft.samples;
    out.payload_best_fractional_corr = payload_ft.corr;
    out.payload_best_fractional_preamble_corr = detail::fractional_preamble_corr(
        derot, integer_rec.timing_offset, payload_ft.samples,
        iqrftrain::preamble_complex());

    // Advance the capture by the measured residual fraction, then run the unchanged
    // frozen recovery/gates.  This is timing alignment, not a lowered correlation
    // threshold: final rec.training_corr must still clear cfg.min_corr == 0.9.
    const std::vector<std::complex<double>> aligned =
        detail::apply_fractional_advance(derot, out.fractional_timing_samples);
    out.rec = iqrfrec::estimate(aligned, cfg);
    out.rec.payload_tx_scale = payload_tx_scale;
    if (out.rec.valid)
        out.payload = iqrfrec::apply(aligned, out.rec);
    return out;
}

}  // namespace iqdual23fix10
