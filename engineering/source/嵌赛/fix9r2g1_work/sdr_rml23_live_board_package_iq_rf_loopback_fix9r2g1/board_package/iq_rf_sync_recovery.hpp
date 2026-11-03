#pragma once

// iq_rf_sync_recovery.hpp -- Route F fix9r2 Task R4/R5/R6: the SHARED per-file
// training-frame recovery core.  This replaces the fix9r estimate() (which searched
// only the first 4096 samples of the capture) with the correct fix9r2 semantics:
//
//   * FULL-CAPTURE preamble search (Task R4): the TX is a CYCLIC 59904-sample burst,
//     so the RX capture start is arbitrary; the receiver must search the WHOLE capture
//     for the preamble, never assume the burst starts at sample 0.  The search extent
//     is bounded by (rx.size() - kTotalBurstComplex) so a complete [preamble .. tail]
//     burst always fits -- the caller captures >= 2 periods to guarantee this.
//
//   * the tail-search bounds guard is fixed to `best + d + kTailComplex <= rx.size()`
//     (the fix9r guard used `d + kTailComplex`, which over-reads the capture when the
//     preamble is NOT at offset 0 -- the exact case the board hit).
//
//   * correct processing order (Task R5): format -> DC -> coarse CFO -> timing ->
//     fine CFO -> gain/phase -> drift -> SRO -> payload window.  For same-Pluto fix9r2
//     the CFO is ~0 (shared clock), so the applied CFO is the preamble-vs-tail FINE
//     CFO; the differential COARSE CFO is recorded (reserved for double-SDR fix10) but
//     NOT applied here.  Sign conventions are in iq_rf_frame_layout.hpp.
//
//   * valid semantics (Task R6): `computed` means "the estimator ran and produced
//     numbers"; `valid` means "every validity check passed".  A typed Failure enum
//     names the first check that failed (never "valid=1 because a number came out").
//
// iCraft-free and libiio-free: it compiles identically on the host and the board.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#include "iq_rf_training_frame.hpp"
#include "iq_rf_frame_layout.hpp"

namespace iqrfrec {

// One payload-domain training residual contract for diagnostic and full runs.
// The original ZC residual is instrument-only; this unchanged 0.10 limit was
// explicitly migrated to the new payload-domain training block in fix9r2g.
constexpr double kPayloadTrainingResidualMax = 0.10;
// A capture may be repeated only for the single observed transient failure at the
// unchanged residual gate.  This is a total-attempt bound (initial + retries), not
// a threshold relaxation; all other recovery failures remain immediately final.
constexpr std::size_t kPayloadTrainingCaptureMaxAttempts = 3;

// ---- typed failure reason (Task R6) -----------------------------------------
// The 10 non-NONE tokens + NONE.  estimate() produces the first seven;
// FRAME_LAYOUT_MISMATCH / TX_SUBMITTED_BUFFER_MISMATCH / RX_CLIPPED are produced by
// the TX-side verifier (iq_rf_tx_provenance.hpp) and the runner's infra gates, and
// are listed here so the enum is the single shared vocabulary.
enum class Failure {
    NONE = 0,
    CAPTURE_TOO_SHORT,          // rx.size() < kTotalBurstComplex
    TRAINING_NOT_FOUND,         // no signal: |LS gain| ~ 0
    TRAINING_CORRELATION_TOO_LOW,   // preamble peak corr < min_corr
    TRAINING_RESIDUAL_TOO_HIGH,     // residual after gain/phase/CFO > max_residual
    TRAINING_PEAK_AMBIGUOUS,        // a second distinct preamble peak clears min_corr
    CFO_OUT_OF_RANGE,               // |fine CFO| > max_cfo_hz
    SRO_OUT_OF_RANGE,               // |SRO| > max_sro_ppm
    PAYLOAD_TRAINING_NOT_FOUND,     // payload gain non-finite or <= 1e-12 (unsafe)
    PAYLOAD_TRAINING_CORRELATION_TOO_LOW,   // de-ramped training-block corr < min_corr
    PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH,     // de-ramped training-block residual > max_residual
    PAYLOAD_RMS_GAIN_NOT_FOUND,     // payload RMS / known TX-RMS gain is unsafe
    FRAME_LAYOUT_MISMATCH,          // TX-frame layout/training/payload mismatch (R2)
    TX_SUBMITTED_BUFFER_MISMATCH,   // submitted iio buffer != formatted container (R1)
    RX_CLIPPED,                     // railed RX sample
};

inline bool should_retry_payload_training_capture(Failure failure,
                                                  std::size_t completed_attempts) {
    return failure == Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH &&
           completed_attempts > 0 &&
           completed_attempts < kPayloadTrainingCaptureMaxAttempts;
}

inline const char* failure_token(Failure f) {
    switch (f) {
        case Failure::NONE: return "NONE";
        case Failure::CAPTURE_TOO_SHORT: return "CAPTURE_TOO_SHORT";
        case Failure::TRAINING_NOT_FOUND: return "TRAINING_NOT_FOUND";
        case Failure::TRAINING_CORRELATION_TOO_LOW: return "TRAINING_CORRELATION_TOO_LOW";
        case Failure::TRAINING_RESIDUAL_TOO_HIGH: return "TRAINING_RESIDUAL_TOO_HIGH";
        case Failure::TRAINING_PEAK_AMBIGUOUS: return "TRAINING_PEAK_AMBIGUOUS";
        case Failure::CFO_OUT_OF_RANGE: return "CFO_OUT_OF_RANGE";
        case Failure::SRO_OUT_OF_RANGE: return "SRO_OUT_OF_RANGE";
        case Failure::PAYLOAD_TRAINING_NOT_FOUND: return "PAYLOAD_TRAINING_NOT_FOUND";
        case Failure::PAYLOAD_TRAINING_CORRELATION_TOO_LOW: return "PAYLOAD_TRAINING_CORRELATION_TOO_LOW";
        case Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH: return "PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH";
        case Failure::PAYLOAD_RMS_GAIN_NOT_FOUND: return "PAYLOAD_RMS_GAIN_NOT_FOUND";
        case Failure::FRAME_LAYOUT_MISMATCH: return "FRAME_LAYOUT_MISMATCH";
        case Failure::TX_SUBMITTED_BUFFER_MISMATCH: return "TX_SUBMITTED_BUFFER_MISMATCH";
        case Failure::RX_CLIPPED: return "RX_CLIPPED";
    }
    return "UNKNOWN";
}

// ---- per-file quantities + quality metrics + typed validity ------------------
struct PerFileRecovery {
    bool computed = false;            // estimate() ran (always true on return)
    bool valid = false;               // every validity check passed
    Failure failure = Failure::NONE;  // first check that failed (NONE == valid)
    std::size_t timing_offset = 0;    // complex samples: preamble peak lag in capture
    double coarse_cfo_hz = 0.0;       // differential CFO (recorded; reserved fix10)
    double gain_mag = 1.0;            // |a_i| (linear)
    double phase_deg = 0.0;           // arg(a_i) in degrees
    double cfo_hz = 0.0;              // applied (fine) carrier offset (Hz)
    double sro_ppm = 0.0;             // sampling-rate offset (ppm)
    double phase_drift_deg = 0.0;     // phase accumulated over the preamble->tail span
    double training_corr = 0.0;       // normalized preamble peak correlation [0,1]
    double training_residual = 0.0;   // normalized preamble residual (instrument-only)
    double payload_gain_mag = 0.0;    // training-block LS magnitude (instrument + legacy fallback)
    double payload_rms_gain_mag = 0.0;// label-free magnitude from RX payload RMS / TX-RMS contract
    double payload_phase_deg = 0.0;   // payload-domain training-block phase (deg)
    double payload_tx_scale = 1.0;    // known digital TX payload scale; undone after RF gain
    double payload_training_corr = 0.0;     // de-ramped training-block corr (instrument + gate)
    double payload_training_residual = 0.0; // de-ramped training-block residual (instrument + gate)
};

// ---- estimator configuration (Task R6) ----------------------------------------
// Defaults are the ESTIMATOR sanity bounds (permissive enough to unit-test the
// estimator's range).  The runner passes its own STRICTER same-Pluto bounds.
struct EstimateConfig {
    double min_corr = 0.9;          // preamble peak corr floor
    double max_residual = 0.05;     // residual ceiling (<= -13 dB)
    double max_cfo_hz = 1000.0;     // fine-CFO magnitude ceiling
    double max_sro_ppm = 1000.0;    // SRO magnitude ceiling
    std::size_t search_limit = 0;   // 0 = search the WHOLE capture (fix9r2 default)
    // Component RMS of the final quantized TX payload.  A positive value enables
    // the label-free payload-energy magnitude estimator; zero preserves the
    // training-block magnitude for legacy/unit-test callers.
    double payload_tx_target_rms = 0.0;
};

namespace detail {

inline double norm2(const std::complex<double>& z) {
    return z.real() * z.real() + z.imag() * z.imag();
}

// Cross-correlation of rx over [start, start+ref.size()) with ref, normalized to [0,1].
inline double normalized_corr(const std::vector<std::complex<double>>& rx,
                              std::size_t start,
                              const std::vector<std::complex<double>>& ref) {
    double num_r = 0.0, num_i = 0.0, den_rx = 0.0, den_ref = 0.0;
    for (std::size_t k = 0; k < ref.size(); ++k) {
        const std::complex<double>& x = rx[start + k];
        const std::complex<double>& p = ref[k];
        num_r += x.real() * p.real() + x.imag() * p.imag();
        num_i += x.imag() * p.real() - x.real() * p.imag();
        den_rx += norm2(x);
        den_ref += norm2(p);
    }
    const double num = std::sqrt(num_r * num_r + num_i * num_i);
    const double den = std::sqrt(den_rx * den_ref);
    return den > 0.0 ? num / den : 0.0;
}

// Least-squares complex gain a == sum(rx*conj(ref)) / sum(|ref|^2) over a window.
inline std::complex<double> ls_gain(const std::vector<std::complex<double>>& rx,
                                    std::size_t start,
                                    const std::vector<std::complex<double>>& ref) {
    std::complex<double> num(0.0, 0.0);
    double den = 0.0;
    for (std::size_t k = 0; k < ref.size(); ++k) {
        num += rx[start + k] * std::conj(ref[k]);
        den += norm2(ref[k]);
    }
    return den > 0.0 ? num / den : std::complex<double>(0.0, 0.0);
}

// Differential CFO at the aligned preamble (Task R5 coarse-CFO reservation): the ZC
// differential d[k] = u[k]*conj(u[k-1]) = exp(-j*pi*r*(2k-1)/N) is a pure tone of
// frequency -r/N cycles/sample, so correlating the RX differential against it yields
// phase = 2*pi*f/fs (unambiguous over +/- fs/2 == +/-1.28 MHz).  fix9r2 RECORDS this
// but does NOT apply it (same-Pluto CFO ~ 0); fix10 applies it before fine timing.
inline double differential_cfo_hz(const std::vector<std::complex<double>>& rx,
                                  std::size_t start) {
    const int r = iqrftrain::kZadoffChuRoot;
    const std::size_t N = iqrftrain::kPreambleComplex;
    std::complex<double> acc(0.0, 0.0);
    for (std::size_t k = 1; k < N; ++k) {
        const std::complex<double> d_rx = rx[start + k] * std::conj(rx[start + k - 1]);
        const double ph = -iqrftrain::kPi * static_cast<double>(r) *
                          static_cast<double>(2 * static_cast<int>(k) - 1) /
                          static_cast<double>(N);
        const std::complex<double> d_ref(std::cos(ph), std::sin(ph));
        acc += d_rx * std::conj(d_ref);
    }
    const double phase = std::arg(acc);
    return phase * static_cast<double>(iqrftrain::kFs) / (2.0 * iqrftrain::kPi);
}

}  // namespace detail

// Estimate the per-file recovery from a captured window (complex<double>).  The
// preamble is searched over the WHOLE capture (bounded so a full burst fits); on
// success rec.computed==true and rec.valid==true with rec.timing_offset the preamble
// peak lag (payload region starts at timing_offset + kPayloadStart).  On any failure
// rec.failure names the first check that failed.
inline PerFileRecovery estimate(const std::vector<std::complex<double>>& rx,
                                const EstimateConfig& cfg = EstimateConfig()) {
    PerFileRecovery rec;
    rec.computed = true;
    rec.failure = Failure::CAPTURE_TOO_SHORT;

    const std::vector<std::complex<double>> pre = iqrftrain::preamble_complex();
    const std::vector<std::complex<double>> t = iqrftrain::tail_complex();
    if (rx.size() < iqrftrain::kTotalBurstComplex)
        return rec;   // cannot hold even one burst at offset 0

    // ---- 1. preamble peak -> timing_offset + training_corr --------------------
    // Search the WHOLE capture up to the last offset where the full [preamble..tail]
    // burst fits.  This is the fix9r2 root-cause fix: the capture start is arbitrary
    // (cyclic TX), so a bounded first-4096 search missed the preamble ~93% of the time.
    const std::size_t max_fit = rx.size() - iqrftrain::kTotalBurstComplex;
    std::size_t search_end = max_fit;
    if (cfg.search_limit > 0)
        search_end = std::min(search_end, cfg.search_limit);

    std::size_t best = 0;
    double best_corr = -1.0;
    for (std::size_t s = 0; s <= search_end; ++s) {
        const double c = detail::normalized_corr(rx, s, pre);
        if (c > best_corr) { best_corr = c; best = s; }
    }
    rec.timing_offset = best;
    rec.training_corr = best_corr;

    // ---- 2. LS complex gain over the preamble -> gain_mag + phase_deg ----------
    const std::complex<double> a_pre = detail::ls_gain(rx, best, pre);
    rec.gain_mag = std::abs(a_pre);
    rec.phase_deg = std::arg(a_pre) * 180.0 / iqrftrain::kPi;
    rec.failure = Failure::TRAINING_NOT_FOUND;
    if (rec.gain_mag <= 1e-12) return rec;   // no signal

    // ---- 3. coarse CFO (recorded only; not applied in fix9r2) ------------------
    rec.coarse_cfo_hz = detail::differential_cfo_hz(rx, best);

    // ---- 4. tail re-location -> sro_ppm ----------------------------------------
    // Bounds guard FIXED to `best + d` (the fix9r guard dropped `best`, which
    // over-read the capture when the preamble was not at offset 0).
    const std::size_t expected_tail = iqrftrain::kTailStart;
    const std::size_t lo = (expected_tail >= iqrftrain::kTailSearchHalf)
                               ? expected_tail - iqrftrain::kTailSearchHalf : 0;
    const std::size_t hi = expected_tail + iqrftrain::kTailSearchHalf;
    std::size_t tail_peak = expected_tail;
    double tail_corr = -1.0;
    for (std::size_t d = lo; d <= hi; ++d) {
        if (best + d + iqrftrain::kTailComplex > rx.size()) break;
        const double c = detail::normalized_corr(rx, best + d, t);
        if (c > tail_corr) { tail_corr = c; tail_peak = d; }
    }
    const double delta = static_cast<double>(tail_peak) - static_cast<double>(expected_tail);
    rec.sro_ppm = delta / static_cast<double>(expected_tail) * 1e6;

    // ---- 5. fine CFO + intra-burst phase drift (preamble-vs-tail phase) --------
    // The tail is kTailStart samples after the preamble, so the phase accumulated
    // between the two LS gains is 2*pi*cfo*kTailStart/fs (unambiguous over
    // +/- fs/(2*kTailStart) ~ +/-21.7 Hz -- enough for the same-Pluto residual).
    const std::complex<double> a_tail = detail::ls_gain(rx, best + tail_peak, t);
    const double drift = std::arg(a_tail * std::conj(a_pre));
    rec.phase_drift_deg = drift * 180.0 / iqrftrain::kPi;
    rec.cfo_hz = drift * static_cast<double>(iqrftrain::kFs) /
                 (2.0 * iqrftrain::kPi * static_cast<double>(expected_tail));

    // ---- 6. de-ramped complex gain + normalized residual (gain/phase/CFO/SRO) ----
    // The raw a_pre (step 2) is the LS fit to the UN-de-ramped preamble, so a CFO/SRO
    // phase ramp spreads its phase AND shrinks its magnitude.  Fix: fit the complex
    // gain to the reference DE-RAMPED by the estimated CFO + SRO, so the gain is the
    // true per-file RF gain and the residual is the leftover distortion -- never the
    // legitimate CFO/SRO ramp (keeps TRAINING_RESIDUAL_TOO_HIGH from firing before
    // SRO_OUT_OF_RANGE / CFO_OUT_OF_RANGE, and reports the true RF gain/phase).
    //
    // SRO is modeled as rx[n] == tx[n/(1+s)] (apply()'s exact inverse: TX sample m
    // lands at RX index m*(1+s)).  Because the ZC preamble's instantaneous frequency
    // sweeps the full circle, LINEAR interpolation of it loses real amplitude (chord
    // effect ~ cos of half the step phase), so the reference MUST be built by the SAME
    // linear interpolation the injector and apply() use -- a phase-only SRO ramp
    // (exp(+j 2*pi*sro*k^2/N)) would leave that amplitude loss in the residual and
    // false-flag a clean SRO-stretched preamble.  CFO is a LINEAR phase ramp in k.
    const double sro_frac = rec.sro_ppm * 1e-6;
    auto stretched_pre = [&pre, sro_frac](std::size_t k) -> std::complex<double> {
        const double x = static_cast<double>(k) / (1.0 + sro_frac);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(x));
        const std::size_t i1 = i0 + 1;
        if (i1 < pre.size()) {
            const double fr = x - static_cast<double>(i0);
            return pre[i0] * (1.0 - fr) + pre[i1] * fr;
        }
        return (i0 < pre.size()) ? pre[i0] : std::complex<double>(0.0, 0.0);
    };
    std::complex<double> a_fit(0.0, 0.0);
    {
        double den = 0.0;
        for (std::size_t k = 0; k < iqrftrain::kPreambleComplex; ++k) {
            const std::complex<double> rk = stretched_pre(k);
            const double ph = 2.0 * iqrftrain::kPi * rec.cfo_hz *
                              static_cast<double>(k) /
                              static_cast<double>(iqrftrain::kFs);
            const std::complex<double> derot(std::cos(ph), -std::sin(ph));  // exp(-j ph)
            a_fit += rx[best + k] * std::conj(rk) * derot;
            den += detail::norm2(rk);
        }
        if (den > 0.0) a_fit /= den;
    }
    rec.gain_mag = std::abs(a_fit);
    rec.phase_deg = std::arg(a_fit) * 180.0 / iqrftrain::kPi;
    double num_res = 0.0, den_res = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPreambleComplex; ++k) {
        const std::complex<double> rk = stretched_pre(k);
        const double ph = 2.0 * iqrftrain::kPi * rec.cfo_hz *
                          static_cast<double>(k) /
                          static_cast<double>(iqrftrain::kFs);
        const std::complex<double> rot(std::cos(ph), std::sin(ph));
        const std::complex<double> model = a_fit * rk * rot;
        const std::complex<double> err = rx[best + k] - model;
        num_res += detail::norm2(err);
        den_res += detail::norm2(model);
    }
    rec.training_residual = den_res > 0.0 ? std::sqrt(num_res / den_res) : 0.0;

    // ---- 6.5 de-ramped payload-domain gain + corr + residual (fix9r2g) ----------
    // The preamble gain (step 6) does NOT apply to the payload (FIXED_SCALE_JUMP:
    // constant-envelope ZC preamble -> low gain; modulated payload -> high gain).  Fit
    // the FINAL complex scalar gain against the payload-domain training block (a
    // deterministic, modulated, narrowband block placed immediately before the
    // payload), using the SAME estimated timing/CFO/SRO and the SAME de-ramp mapping
    // as step 6, so corr / gain / residual are consistent (no uncorrected
    // normalized_corr that a CFO/SRO would falsely reject).  The reference is derived
    // from the exact int16 TX samples (bit-identical to what was transmitted).
    const std::vector<std::complex<double>> pt = iqrftrain::payload_gain_training_complex();
    const std::size_t ptoff = iqrftrain::kPayloadTrainingOffset;
    auto stretched_pt = [&pt, ptoff, sro_frac](std::size_t k) -> std::complex<double> {
        // RX index (ptoff + k) <-> TX index (ptoff + k)/(1 + sro), mapped back to
        // ref[(ptoff + k)/(1 + sro) - ptoff].  Clamp x to [0, size-1] (x is ~ -ptoff*sro
        // ~ -0.06 at k=0 for a small positive SRO, i.e. slightly below 0).
        double x = static_cast<double>(ptoff + k) / (1.0 + sro_frac) -
                   static_cast<double>(ptoff);
        if (x < 0.0) x = 0.0;
        if (x > static_cast<double>(pt.size() - 1)) x = static_cast<double>(pt.size() - 1);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(x));
        const std::size_t i1 = i0 + 1;
        if (i1 < pt.size()) {
            const double fr = x - static_cast<double>(i0);
            return pt[i0] * (1.0 - fr) + pt[i1] * fr;
        }
        return pt[i0];
    };
    std::complex<double> num_pt(0.0, 0.0);
    double den_r_pt = 0.0, den_x_pt = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const std::complex<double> rk = stretched_pt(k);
        const double ph = 2.0 * iqrftrain::kPi * rec.cfo_hz *
                          static_cast<double>(ptoff + k) /
                          static_cast<double>(iqrftrain::kFs);
        const std::complex<double> derot(std::cos(ph), -std::sin(ph));  // exp(-j ph)
        const std::complex<double>& x = rx[best + ptoff + k];
        num_pt += x * std::conj(rk) * derot;
        den_r_pt += detail::norm2(rk);
        den_x_pt += detail::norm2(x);
    }
    const std::complex<double> a_pay = (den_r_pt > 0.0)
        ? num_pt / den_r_pt : std::complex<double>(0.0, 0.0);
    rec.payload_gain_mag = std::abs(a_pay);
    rec.payload_phase_deg = std::arg(a_pay) * 180.0 / iqrftrain::kPi;
    rec.payload_training_corr = (den_x_pt > 0.0 && den_r_pt > 0.0)
        ? std::abs(num_pt) / std::sqrt(den_x_pt * den_r_pt) : 0.0;
    double num_res_pt = 0.0, den_res_pt = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const std::complex<double> rk = stretched_pt(k);
        const double ph = 2.0 * iqrftrain::kPi * rec.cfo_hz *
                          static_cast<double>(ptoff + k) /
                          static_cast<double>(iqrftrain::kFs);
        const std::complex<double> rot(std::cos(ph), std::sin(ph));
        const std::complex<double> model = a_pay * rk * rot;
        const std::complex<double> err = rx[best + ptoff + k] - model;
        num_res_pt += detail::norm2(err);
        den_res_pt += detail::norm2(model);
    }
    rec.payload_training_residual =
        den_res_pt > 0.0 ? std::sqrt(num_res_pt / den_res_pt) : 0.0;

    // The training block remains the phase reference and the corr/residual fidelity
    // gate.  Its magnitude is not guaranteed to equal every modulation payload's
    // band-integrated gain.  Every transmitted payload is independently normalized
    // to the public component-RMS contract, so the received payload energy provides
    // a label-free magnitude estimate without using expected payload samples.
    if (cfg.payload_tx_target_rms > 0.0 &&
        std::isfinite(cfg.payload_tx_target_rms)) {
        double payload_energy = 0.0;
        bool payload_in_bounds = true;
        for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
            const double src =
                static_cast<double>(best + iqrftrain::kPayloadStart + k) *
                (1.0 + sro_frac);
            const std::size_t i0 = static_cast<std::size_t>(std::floor(src));
            const std::size_t i1 = i0 + 1;
            std::complex<double> x;
            if (i1 < rx.size()) {
                const double frac = src - static_cast<double>(i0);
                x = rx[i0] * (1.0 - frac) + rx[i1] * frac;
            } else if (i0 < rx.size()) {
                x = rx[i0];
            } else {
                payload_in_bounds = false;
                break;
            }
            payload_energy += detail::norm2(x);
        }
        if (payload_in_bounds && payload_energy > 0.0) {
            const double rx_component_rms = std::sqrt(
                payload_energy /
                (2.0 * static_cast<double>(iqrftrain::kPayloadComplex)));
            rec.payload_rms_gain_mag =
                rx_component_rms / cfg.payload_tx_target_rms;
        }
    }

    // ---- 7. peak ambiguity (a distinct second preamble peak clears min_corr) ----
    // The ZC preamble's NON-cyclic correlation has a broad shoulder (offset by one
    // sample keeps a 1023/1024 overlap, corr ~ 0.9995), so the second-best position
    // must be searched OUTSIDE a +/-kPreambleComplex neighborhood around `best` --
    // otherwise a legitimate timing-offset preamble is falsely flagged ambiguous.
    // A second peak exactly one FRAME PERIOD away is the legitimate cyclic repeat of
    // the SAME preamble (a 2-period capture holds the burst twice), not an ambiguity,
    // so it is exempted.  Any OTHER distinct peak clearing min_corr is a real
    // ambiguous peak (e.g. a multipath echo) and is refused.
    rec.failure = Failure::TRAINING_PEAK_AMBIGUOUS;
    {
        const std::size_t lo_skip = (best >= iqrftrain::kPreambleComplex)
                                        ? best - iqrftrain::kPreambleComplex : 0;
        const std::size_t hi_skip =
            std::min(search_end, best + iqrftrain::kPreambleComplex);
        double best2_corr = -1.0;
        std::size_t best2 = 0;
        for (std::size_t s = 0; s <= search_end; ++s) {
            if (s >= lo_skip && s <= hi_skip) continue;   // main-peak shoulder
            const double c = detail::normalized_corr(rx, s, pre);
            if (c > best2_corr) { best2_corr = c; best2 = s; }
        }
        if (best2_corr >= cfg.min_corr) {
            const std::size_t d = (best2 > best) ? (best2 - best) : (best - best2);
            if (d != iqrflayout::kFramePeriodComplex)
                return rec;   // ambiguous second peak, not the cyclic repeat
        }
    }
    rec.failure = Failure::NONE;

    // ---- 8. validity checks (R6 + fix9r2g) -------------------------------------
    // Sync-stage failures (CAPTURE_TOO_SHORT / TRAINING_NOT_FOUND /
    // TRAINING_CORRELATION_TOO_LOW / TRAINING_PEAK_AMBIGUOUS, some of which early-
    // returned above) are never overwritten here.  Only when the sync stage is clean
    // do we check, in order: preamble corr gate (KEPT: ZC sync validity still requires
    // the original corr gate), payload-training gain finite/non-zero/safe, de-ramped
    // training-block corr, de-ramped training-block residual (the residual<=0.10 gate
    // MIGRATED from the preamble; preamble training_residual is now instrument-only),
    // then CFO and SRO bounds.
    if (rec.failure == Failure::NONE) {
        if (rec.training_corr < cfg.min_corr)
            rec.failure = Failure::TRAINING_CORRELATION_TOO_LOW;
        else if (!std::isfinite(rec.payload_gain_mag) || rec.payload_gain_mag <= 1e-12)
            rec.failure = Failure::PAYLOAD_TRAINING_NOT_FOUND;
        else if (cfg.payload_tx_target_rms > 0.0 &&
                 (!std::isfinite(rec.payload_rms_gain_mag) ||
                  rec.payload_rms_gain_mag <= 1e-12))
            rec.failure = Failure::PAYLOAD_RMS_GAIN_NOT_FOUND;
        else if (rec.payload_training_corr < cfg.min_corr)
            rec.failure = Failure::PAYLOAD_TRAINING_CORRELATION_TOO_LOW;
        else if (rec.payload_training_residual > cfg.max_residual)
            rec.failure = Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH;
        else if (std::fabs(rec.cfo_hz) > cfg.max_cfo_hz)
            rec.failure = Failure::CFO_OUT_OF_RANGE;
        else if (std::fabs(rec.sro_ppm) > cfg.max_sro_ppm)
            rec.failure = Failure::SRO_OUT_OF_RANGE;
    }

    rec.valid = (rec.failure == Failure::NONE);
    return rec;
}

// Backward-compatible overload: search_limit overrides cfg.search_limit (the old
// fix9r call sites passed a sample count; fix9r2 passes 0 == full capture).
inline PerFileRecovery estimate(const std::vector<std::complex<double>>& rx,
                                std::size_t search_limit) {
    EstimateConfig cfg;
    cfg.search_limit = search_limit;
    return estimate(rx, cfg);
}

// Apply the per-file recovery to the captured window and return the corrected payload
// (kPayloadComplex complex samples).  Undoes timing (payload starts at
// timing_offset + kPayloadStart), the FINAL complex gain (magnitude from the public
// TX-RMS contract and received payload energy when enabled; phase from the common
// payload-domain training block), CFO (derotate
// anchored at the preamble peak), and SRO (linear resample).  Fail-closed: a recovery
// that is not valid, or whose payload gain is unsafe, throws -- the runner's fidelity
// gate guarantees this is only called with rec.valid==true, and this assertion is the
// backstop so an unrecovered payload is NEVER silently fed to the model.
inline std::vector<std::complex<double>> apply(
        const std::vector<std::complex<double>>& rx, const PerFileRecovery& rec) {
    if (!rec.valid)
        throw std::runtime_error(std::string("iqrfrec::apply: recovery not valid (failure=") +
                                 failure_token(rec.failure) + ")");
    const double mag = (rec.payload_rms_gain_mag > 1e-12 &&
                        std::isfinite(rec.payload_rms_gain_mag))
                           ? rec.payload_rms_gain_mag : rec.payload_gain_mag;
    const double mag2 = mag * mag;
    if (!std::isfinite(mag) || mag <= 1e-12)
        throw std::runtime_error("iqrfrec::apply: unsafe payload gain");
    if (!std::isfinite(rec.payload_tx_scale) || rec.payload_tx_scale <= 0.0)
        throw std::runtime_error("iqrfrec::apply: unsafe payload TX scale");
    const std::complex<double> a_inv =
        std::complex<double>(mag / mag2, 0.0) *
        std::complex<double>(std::cos(-rec.payload_phase_deg * iqrftrain::kPi / 180.0),
                             std::sin(-rec.payload_phase_deg * iqrftrain::kPi / 180.0)) /
        rec.payload_tx_scale;
    std::vector<std::complex<double>> out(iqrftrain::kPayloadComplex);

    const double sro = rec.sro_ppm * 1e-6;
    const double f = rec.cfo_hz;

    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        // rx[n] == s_tx[n / (1 + s)]: recover TX sample m by reading RX index
        // m*(1+s) -- MULTIPLY, not divide.
        const double src = static_cast<double>(rec.timing_offset + iqrftrain::kPayloadStart + k) *
                           (1.0 + sro);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(src));
        const std::size_t i1 = i0 + 1;
        std::complex<double> x;
        if (i1 < rx.size()) {
            const double frac = src - static_cast<double>(i0);
            x = rx[i0] * (1.0 - frac) + rx[i1] * frac;
        } else if (i0 < rx.size()) {
            x = rx[i0];
        } else {
            x = std::complex<double>(0.0, 0.0);
        }
        x *= a_inv;
        const double ph = -2.0 * iqrftrain::kPi * f *
                          static_cast<double>(iqrftrain::kPayloadStart + k) /
                          static_cast<double>(iqrftrain::kFs);
        const std::complex<double> derot(std::cos(ph), std::sin(ph));
        out[k] = x * derot;
    }
    return out;
}

// Convenience: full recovery chain on interleaved int16 capture -> interleaved int16
// payload (matches the D2 restore input convention).
inline std::vector<std::int16_t> recover_payload_int16(
        const std::vector<std::int16_t>& rx_iq) {
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(rx_iq);
    const PerFileRecovery rec = estimate(rx);
    if (!rec.valid)
        return std::vector<std::int16_t>();
    const std::vector<std::complex<double>> payload = apply(rx, rec);
    std::vector<std::int16_t> out(payload.size() * 2);
    for (std::size_t k = 0; k < payload.size(); ++k) {
        const double I = std::lround(payload[k].real());
        const double Q = std::lround(payload[k].imag());
        out[k * 2 + 0] = static_cast<std::int16_t>(std::max(-32768.0, std::min(32767.0, I)));
        out[k * 2 + 1] = static_cast<std::int16_t>(std::max(-32768.0, std::min(32767.0, Q)));
    }
    return out;
}

}  // namespace iqrfrec
