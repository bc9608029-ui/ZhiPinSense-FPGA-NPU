#pragma once

// iq_digital_loopback_sync.hpp — Stage H-E / Route E fix5: full-period FFT
// circular synchronization + scale-independent fidelity for the arbitrary
// modulated-IQ digital loopback.
//
// fix4 left two defects that made every board capture land on
// SYNC_OR_WRAP_INCONCLUSIVE / corr ~ 0..0.095 while NMSE read ~0.004:
//
//   (1) the fix4 alignment used a BOUNDED integer-delay search over [0,
//       delay_margin) -- a few thousand samples.  A cyclic TX whose capture
//       starts at an arbitrary phase inside a 53760-sample period needs the
//       FULL period searched; a +/-4096 window simply cannot find the true
//       delay, so corr collapses to ~0 no matter how clean the loopback is.
//   (2) the NMSE/EVM denominator was the TX energy (sum |x|^2), not the RX
//       energy (sum |y|^2).  When the RX is the TX scaled by the 12/16-bit
//       full-scale factor (1/16 -> energy /256), NMSE = err / sum|x|^2 ~= 0.004
//       even with corr ~ 0.095 -- a low correlation was masked as a low EVM.
//
// fix5 replaces the bounded search with a full-period FFT circular
// cross-correlation over ALL P circular shifts, O(P log P):
//
//     r[k] = IFFT( FFT(rx) * conj(FFT(tx)) ) = sum_j rx[j] * conj(tx[(j-k) mod P])
//
// The peak of |r[k]| at k = circular_shift recovers the cyclic delay:
// rx[j] ~= a * tx[(j - circular_shift) mod P].  The complex gain a is then the
// optimal least-squares fit, and the scale-independent normalized residual
//
//     normalized_residual = ||y - a x||^2 / ||y||^2  =  1 - |corr|^2
//
// makes EVM provably consistent with the correlation, so a corr of 0.095 can
// never again show as EVM ~ 6.6%.
//
// Direction/shift definition (verified by host test test_iq_digital_loopback_sync):
//   rx[j] = tx[(j - d) mod P]  =>  circular_shift == d  =>  aligned[m] = rx[(d+m)
//   mod P] ~= a * tx[m].  The FFT folding c[k] = h[k] + h[nfft - P + k] is
//   cross-checked against a direct O(P^2) reference in that test.
//
// fix6 (this header) splits "waveform fidelity" from "circular-origin
// uniqueness" (requirement 1) and stops treating a low peak_ratio as a
// PRESERVES_IQ prerequisite (requirement 2):
//
//   * the TX's own circular autocorrelation r_norm[k] (requirement 3) PREDICTS the
//     cross-correlation sidelobes a clean loopback inherits: c[k] ~= corr_d *
//     r_norm[(k-d) mod P].  A competing corr lobe that does not exceed that
//     prediction is an EQUIVALENT circular origin (the TX is self-similar there ->
//     the SAME waveform under a different labeled origin), reported separately as
//     sync_origin=AMBIGUOUS_EQUIVALENT -- never as waveform distortion
//     (requirement 5).  A lobe that EXCEEDS the prediction is a genuinely different
//     waveform, and only then is the alignment CIRCULAR_SYNC_AMBIGUOUS
//     (requirement 6).
//   * PRESERVES_IQ (requirement 4) = corr >= 0.9 AND normalized_residual consistent
//     AND no clipping AND DMA payload SHA correct (the DMA SHA gate lives in the
//     runner; the peak_ratio gate is REMOVED here).
//
// iCraft-free and libiio-free.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqdloop_sync {

constexpr double kPi = 3.141592653589793238462643383279502884;

// In-capture transient discard (pipeline guard): the first samples of a capture
// refill can be startup/transient; they are dropped before a full period is chosen.
constexpr std::size_t kTransientDiscardComplex = 4096;

// Observation thresholds (measurement-only; never a PASS gate).
constexpr double kSyncCorrThreshold = 0.9;   // corr < 0.9  -> DISTORTS_IQ
constexpr double kPeakRatioMin = 2.0;        // diagnostic only (fix6: no longer a verdict gate)
constexpr double kCompetingRatio = 0.9;      // a corr lobe within 10% of the main peak competes
constexpr double kPeakExplainAbsMargin = 0.1;// a competing lobe is "unexplained" only if it
                                             // EXCEEDS the TX-autocorrelation prediction by this
constexpr double kNormalizedGainOkDb = 3.0;  // |normalized gain| <= 3 dB
constexpr double kCfoNearZeroHz = 5.0;
constexpr double kRxLowAmplitudeCounts = 2.0;
constexpr std::size_t kMinCaptureComplex = 1024;

// ---- self-contained radix-2 FFT / IFFT (iCraft-free) -------------------------

inline void fft_radix2(std::complex<double>* a, int n, int sign) {
    for (int i = 1, j = 0; i < n; ++i) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (int len = 2; len <= n; len <<= 1) {
        const double ang =
            static_cast<double>(sign) * 2.0 * kPi / static_cast<double>(len);
        const std::complex<double> wlen(std::cos(ang), std::sin(ang));
        for (int i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            for (int k = 0; k < len / 2; ++k) {
                const std::complex<double> u = a[i + k];
                const std::complex<double> v = a[i + k + len / 2] * w;
                a[i + k] = u + v;
                a[i + k + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

inline void ifft_radix2(std::complex<double>* a, int n) {
    for (int i = 0; i < n; ++i) a[i] = std::conj(a[i]);
    fft_radix2(a, n, -1);
    for (int i = 0; i < n; ++i) a[i] = std::conj(a[i]) / static_cast<double>(n);
}

inline int next_pow2(int n) {
    int p = 1;
    while (p < n) p <<= 1;
    return p;
}

// Circular cross-correlation magnitudes c[k] = |sum_j x[j] * conj(y[(j-k) mod P])|,
// k in [0, P).  Computed as the length-nfft (nfft = next_pow2(2P)) linear
// correlation of the zero-padded sequences, then folded back onto period P:
//   c[k] = | h[k] + h[nfft - P + k] |,  h = IFFT( FFT(x) * conj(FFT(y)) )
// This is exact for the period-P circular correlation; P need not be a power of two.
inline std::vector<double> circular_cross_corr(
        const std::vector<std::complex<double>>& x,
        const std::vector<std::complex<double>>& y) {
    const std::size_t P = x.size();
    if (y.size() != P || P == 0)
        throw std::runtime_error("iqdloop-sync: circular_cross_corr length mismatch");
    const int nfft = next_pow2(static_cast<int>(2 * P));
    std::vector<std::complex<double>> X(static_cast<std::size_t>(nfft), 0.0);
    std::vector<std::complex<double>> Y(static_cast<std::size_t>(nfft), 0.0);
    for (std::size_t j = 0; j < P; ++j) { X[j] = x[j]; Y[j] = y[j]; }
    fft_radix2(X.data(), nfft, -1);
    fft_radix2(Y.data(), nfft, -1);
    for (int m = 0; m < nfft; ++m) X[static_cast<std::size_t>(m)] *= std::conj(Y[static_cast<std::size_t>(m)]);
    ifft_radix2(X.data(), nfft);

    std::vector<double> c(P, 0.0);
    for (std::size_t k = 0; k < P; ++k) {
        const std::complex<double> v =
            X[k] + X[static_cast<std::size_t>(nfft - static_cast<int>(P) +
                                              static_cast<int>(k))];
        c[k] = std::abs(v);
    }
    return c;
}

// Normalized TX circular autocorrelation magnitudes (fix6 requirement 3):
//   r_norm[k] = |sum_j tx[j] * conj(tx[(j-k) mod P])| / |sum_j |tx[j]|^2|  in [0,1].
// r_norm[0] == 1.  A value near 1 at shift k means the TX is self-similar under a
// cyclic shift of k -- the "inherent sidelobe" that a clean loopback's cross
// correlation inherits: c[k] ~= corr_peak * r_norm[(k - peak) mod P].  Exposed for
// host tests and for the origin classification inside circular_sync.
inline std::vector<double> circular_autocorr_norm(
        const std::vector<std::complex<double>>& tx) {
    const std::vector<double> r = circular_cross_corr(tx, tx);
    std::vector<double> out(r.size(), 0.0);
    if (!r.empty() && r[0] > 0.0)
        for (std::size_t k = 0; k < r.size(); ++k) out[k] = r[k] / r[0];
    return out;
}

// fix6 requirement 1: circular-origin uniqueness is a conclusion SEPARATE from
// waveform fidelity.  `Equivalent` (multiple origins, same waveform) must never be
// reported as distortion; `Ambiguous` (an unexplained competing lobe -> genuinely
// different waveforms, best alignment undeterminable) is the only blocking case.
enum class SyncOrigin { Unique, Equivalent, Ambiguous };

inline const char* sync_origin_name(SyncOrigin o) {
    switch (o) {
        case SyncOrigin::Unique:     return "UNIQUE";
        case SyncOrigin::Equivalent: return "AMBIGUOUS_EQUIVALENT";
        case SyncOrigin::Ambiguous:  return "CIRCULAR_SYNC_AMBIGUOUS";
    }
    return "UNKNOWN";
}

// Full-period circular synchronization result.
struct CircularSyncResult {
    std::size_t linear_delay = 0;       // aligned_start (offset from capture[0])
    std::size_t circular_shift = 0;     // argmax |r[k]| over k in [0, P)
    std::size_t wrap_count = 0;         // aligned_start / P
    double peak_corr = 0.0;             // |r[peak]| / sqrt(sum|x|^2 * sum|y|^2)
    double second_peak_corr = 0.0;      // same normalization, next-highest lobe
    double peak_ratio = 0.0;            // peak_corr / second_peak_corr (inf if unique)
    std::size_t aligned_start = 0;      // capture index where TX sample 0 lands
    std::size_t compared_samples = 0;   // P (one full period)
    std::size_t transient_discard_samples = 0;

    // ---- fix6: TX self-similarity + circular-origin classification -------------
    // OBSERVATION fields, split from the waveform-fidelity verdict so that "multiple
    // equivalent origins" (a periodic tone, a repeating pattern) is never mistaken
    // for waveform distortion.  origin == Ambiguous (an UNEXPLAINED competing lobe
    // -> different waveforms) is the ONLY case that blocks PRESERVES_IQ.
    double tx_autocorr_second = 0.0;    // max normalized |TX autocorr| outside main lobe
    std::size_t competing_peaks = 0;    // corr lobes >= kCompetingRatio * peak_corr
    std::size_t equivalent_peaks = 0;   // explained by TX autocorrelation (same waveform)
    std::size_t unexplained_peaks = 0;  // exceed the TX-autocorrelation prediction
    double best_unexplained_corr = 0.0; // corr of the strongest unexplained lobe
    SyncOrigin origin = SyncOrigin::Unique;
};

// Discard `transient_discard` samples from the capture start, select ONE full TX
// period P from the stable region, and return the FFT circular cross-correlation
// peak over ALL P shifts.  Requires rx.size()/2 >= transient_discard + P; returns
// a zeroed result (compared_samples == 0) otherwise, so the caller can map the
// short capture to CAPTURE_TOO_SHORT without throwing.
inline CircularSyncResult circular_sync(const std::vector<std::int16_t>& tx,
                                        const std::vector<std::int16_t>& rx,
                                        std::size_t transient_discard) {
    CircularSyncResult s;
    s.transient_discard_samples = transient_discard;
    const std::size_t P = tx.size() / 2;
    const std::size_t R = rx.size() / 2;
    s.compared_samples = P;
    if (P == 0)
        throw std::runtime_error("iqdloop-sync: empty TX waveform");
    if (R < transient_discard + P) {
        s.compared_samples = 0;   // signal "capture too short"
        return s;
    }

    std::vector<std::complex<double>> win(P), txv(P);
    for (std::size_t j = 0; j < P; ++j) {
        const std::size_t rk = transient_discard + j;
        win[j] = std::complex<double>(static_cast<double>(rx[rk * 2 + 0]),
                                      static_cast<double>(rx[rk * 2 + 1]));
        txv[j] = std::complex<double>(static_cast<double>(tx[j * 2 + 0]),
                                      static_cast<double>(tx[j * 2 + 1]));
    }

    const std::vector<double> c = circular_cross_corr(win, txv);

    // energy normalization
    double ex = 0.0, ey = 0.0;
    for (std::size_t j = 0; j < P; ++j) { ex += std::norm(txv[j]); ey += std::norm(win[j]); }

    // peak + second peak (excluding a circular guard band around the peak)
    std::size_t best = 0;
    for (std::size_t k = 1; k < P; ++k)
        if (c[k] > c[best]) best = k;
    const std::size_t guard = std::max<std::size_t>(1, P / 64);
    double second = 0.0;
    for (std::size_t k = 0; k < P; ++k) {
        std::size_t dist = (k >= best) ? (k - best) : (best - k);
        dist = std::min(dist, P - dist);   // circular distance
        if (dist <= guard) continue;
        second = std::max(second, c[k]);
    }

    const double norm = (ex > 0.0 && ey > 0.0) ? std::sqrt(ex * ey) : 0.0;
    s.circular_shift = best;
    s.peak_corr = norm > 0.0 ? c[best] / norm : 0.0;
    s.second_peak_corr = norm > 0.0 ? second / norm : 0.0;
    s.peak_ratio = (second > 0.0)
        ? c[best] / second
        : std::numeric_limits<double>::infinity();
    s.aligned_start = transient_discard + best;
    s.linear_delay = s.aligned_start;
    s.wrap_count = s.aligned_start / P;

    // ---- fix6: TX self-similarity explains inherent cross-correlation sidelobes --
    // For a clean loopback rx[j] ~= a*tx[(j-best) mod P] the cross correlation is
    // c[k] ~= |a| * r_tx[(k-best) mod P], so EVERY sidelobe is predicted by the TX's
    // own circular autocorrelation r_tx.  A competing lobe (corr within 10% of the
    // peak) is an EQUIVALENT circular origin when it does not exceed that prediction
    // (the TX is shift-invariant there -> the SAME waveform under a different labeled
    // origin), and UNEXPLAINED when it exceeds the prediction (a genuinely DIFFERENT
    // waveform also correlates well -> best alignment undeterminable).  peak_ratio is
    // no longer a fidelity gate; it remains a diagnostic.
    const std::vector<double> r_tx = circular_cross_corr(txv, txv);
    const double r0 = r_tx[0];   // == ex (TX energy)
    double r_second = 0.0;
    {
        const std::size_t g0 = std::max<std::size_t>(1, P / 64);
        for (std::size_t k = 0; k < P; ++k) {
            const std::size_t dist0 = std::min(k, P - k);   // circular distance from 0
            if (dist0 <= g0) continue;
            r_second = std::max(r_second, r_tx[k]);
        }
    }
    s.tx_autocorr_second = r0 > 0.0 ? r_second / r0 : 0.0;

    s.competing_peaks = 0;
    s.equivalent_peaks = 0;
    s.unexplained_peaks = 0;
    s.best_unexplained_corr = 0.0;
    for (std::size_t k = 0; k < P; ++k) {
        std::size_t dist = (k >= best) ? (k - best) : (best - k);
        dist = std::min(dist, P - dist);   // circular distance
        if (dist <= guard) continue;
        const double corr_k = norm > 0.0 ? c[k] / norm : 0.0;
        if (corr_k < kCompetingRatio * s.peak_corr) continue;   // not a competing candidate
        ++s.competing_peaks;
        const std::size_t delta = (k >= best) ? (k - best) : (k - best + P);
        const double rn = r0 > 0.0 ? r_tx[delta] / r0 : 0.0;
        const double predicted = s.peak_corr * rn;   // expected sidelobe from TX self-similarity
        if (corr_k > predicted + kPeakExplainAbsMargin) {
            ++s.unexplained_peaks;
            s.best_unexplained_corr = std::max(s.best_unexplained_corr, corr_k);
        } else {
            ++s.equivalent_peaks;
        }
    }
    s.origin = (s.unexplained_peaks > 0) ? SyncOrigin::Ambiguous
             : (s.competing_peaks > 0) ? SyncOrigin::Equivalent
             : SyncOrigin::Unique;
    return s;
}

// fix8 Task A: derive the positive/negative clipping rails from a data-format bit
// width.  pos = 2^(bits-1) - 1, neg = -2^(bits-1).  TX16 -> +32767/-32768,
// RX12 -> +2047/-2048.  A sample at or beyond a rail is clipped.
inline int rail_positive(int bits) {
    return (1 << (bits - 1)) - 1;
}
inline int rail_negative(int bits) {
    return -(1 << (bits - 1));
}

// Full fix5 fidelity metric set.
struct SyncFidelityMetrics {
    std::uint64_t tx_complex = 0;
    std::uint64_t rx_complex = 0;

    CircularSyncResult sync;

    // optimal complex LS fit (count domain): aligned ~= a * tx
    double gain_count = 0.0;        // |a|
    double phase_deg = 0.0;         // arg(a)
    double gain_db = 0.0;           // 20 log10 |a|

    // dual-domain: normalized gain = |a| * 2^(tx_bits-1) / 2^(rx_bits-1)
    double gain_normalized = 0.0;
    double gain_normalized_db = 0.0;
    bool normalized_gain_ok = false;

    // scale-independent residual (denominator = RX energy, NOT TX energy)
    double normalized_residual = 0.0;   // == 1 - |corr|^2 (optimal LS)
    double evm_pct = 0.0;               // 100 * sqrt(normalized_residual)
    double corr = 0.0;                  // |correlation| over the compared full period
    bool nmse_evm_consistent = false;   // |normalized_residual - (1 - corr^2)| tiny

    // RX cyclically rearranged to TX sample 0 (length 2P): aligned_rx[m] ~= a*tx[m].
    // Populated by measure_fidelity_fix5 so the caller (board runner classification)
    // feeds the exact aligned period instead of reading a contiguous rx[d..] window.
    std::vector<std::int16_t> aligned_rx;

    // full-period / active-region / DC-preserved / DC-removed metrics.  The
    // primary verdict uses the DC-PRESERVED full period (never silently drops a
    // meaningful DC); DC-removed and active-region are explicit diagnostics.
    double nmse_full_period = 0.0;
    double nmse_active_region = 0.0;
    double nmse_dc_preserved = 0.0;
    double nmse_dc_removed = 0.0;

    double rms_tx = 0.0, rms_rx = 0.0;
    int tx_peak = 0, rx_peak = 0;      // max |I|,|Q| int16 magnitude
    double dc_tx = 0.0, dc_rx = 0.0;   // |mean|
    double papr_tx_db = 0.0, papr_rx_db = 0.0;
    double cfo_hz = 0.0;
    double phase_drift_deg = 0.0;

    // diagnostics
    double corr_swap = 0.0;
    double corr_conj = 0.0;
    std::uint64_t rx_nonzero = 0;
    double rx_nonzero_rate = 0.0;
    bool rx_all_zero = false;
    // fix8 Task A: TX and RX clipping are SEPARATE and the rails are DERIVED from
    // the data-format bit width (DataFormatInfo.bits), never hardcoded to 2047:
    // TX16 -> +32767/-32768, RX12 -> +2047/-2048.  A sample clips when
    // v >= positive_rail || v <= negative_rail (int16 compare, no abs(INT_MIN)
    // overflow).  tx_clip_count/rx_clip_count are the per-sample clip totals.
    bool tx_clipped = false;
    bool rx_clipped = false;
    std::uint64_t tx_clip_count = 0;
    std::uint64_t rx_clip_count = 0;
    int tx_positive_rail = 0;
    int tx_negative_rail = 0;
    int rx_positive_rail = 0;
    int rx_negative_rail = 0;
    bool capture_too_short = false;
    int tx_bits = 16;
    int rx_bits = 12;
};

// Full measure: circular sync -> cyclically rearrange RX to TX sample 0 -> optimal
// complex LS gain -> dual-domain (count + normalized) -> scale-independent NMSE/EVM
// -> full-period / active-region / DC-preserved / DC-removed.  `tx_bits`/`rx_bits`
// are the DATA-FORMAT bit widths (TX16/RX12 on board), never hardcoded.
inline SyncFidelityMetrics measure_fidelity_fix5(
        const std::vector<std::int16_t>& tx, const std::vector<std::int16_t>& rx,
        std::uint64_t fs, int tx_bits, int rx_bits, std::size_t transient_discard) {
    SyncFidelityMetrics m;
    m.tx_complex = tx.size() / 2;
    m.rx_complex = rx.size() / 2;
    m.tx_bits = tx_bits;
    m.rx_bits = rx_bits;
    m.tx_positive_rail = rail_positive(tx_bits);
    m.tx_negative_rail = rail_negative(tx_bits);
    m.rx_positive_rail = rail_positive(rx_bits);
    m.rx_negative_rail = rail_negative(rx_bits);
    if (m.tx_complex == 0)
        throw std::runtime_error("iqdloop-sync: empty TX waveform");
    if (m.rx_complex == 0)
        throw std::runtime_error("iqdloop-sync: empty RX capture");

    for (std::int16_t v : rx)
        if (v != 0) ++m.rx_nonzero;
    m.rx_nonzero_rate = static_cast<double>(m.rx_nonzero) /
                        static_cast<double>(2 * m.rx_complex);
    m.rx_all_zero = (m.rx_nonzero == 0);

    const std::size_t P = static_cast<std::size_t>(m.tx_complex);
    if (m.rx_complex < transient_discard + P) {
        m.capture_too_short = true;
        return m;
    }

    m.sync = circular_sync(tx, rx, transient_discard);
    // aligned[m] must be the RX CYCLICALLY rearranged to TX sample 0:
    //   rx[transient + j] ~= tx[(j - circular_shift) mod P]
    // => aligned[m] = rx[transient + ((circular_shift + m) mod P)] ~= tx[m].
    // A contiguous rx[start + m] read is wrong whenever start + P would run past
    // the end of the capture (e.g. a capture of exactly transient + P); the mod-P
    // wrap is correct for every capture length >= transient + P.
    const std::size_t cs = m.sync.circular_shift;

    std::vector<std::complex<double>> aligned(P), txv(P);
    m.aligned_rx.resize(2 * P);
    double ex = 0.0, ey = 0.0;
    std::complex<double> cc(0.0, 0.0), cswap(0.0, 0.0), cconj(0.0, 0.0);
    double peak_tx = 0.0, peak_rx = 0.0;
    std::complex<double> sum_tx(0.0, 0.0), sum_rx(0.0, 0.0);
    for (std::size_t mm = 0; mm < P; ++mm) {
        const std::size_t rk = transient_discard + ((cs + mm) % P);
        const std::complex<double> x(static_cast<double>(tx[mm * 2 + 0]),
                                     static_cast<double>(tx[mm * 2 + 1]));
        const std::complex<double> y(static_cast<double>(rx[rk * 2 + 0]),
                                     static_cast<double>(rx[rk * 2 + 1]));
        m.aligned_rx[mm * 2 + 0] = rx[rk * 2 + 0];
        m.aligned_rx[mm * 2 + 1] = rx[rk * 2 + 1];
        txv[mm] = x;
        aligned[mm] = y;
        ex += std::norm(x);
        ey += std::norm(y);
        cc += y * std::conj(x);
        cswap += y * std::conj(std::complex<double>(x.imag(), x.real()));
        cconj += y * std::conj(std::conj(x));
        peak_tx = std::max(peak_tx, std::norm(x));
        peak_rx = std::max(peak_rx, std::norm(y));
        sum_tx += x;
        sum_rx += y;
    }

    // optimal complex gain (LS): a = sum y conj(x) / sum |x|^2
    const std::complex<double> a =
        (ex > 1e-30) ? cc / ex : std::complex<double>(1.0, 0.0);
    m.gain_count = std::abs(a);
    m.phase_deg = std::arg(a) * 180.0 / kPi;
    m.gain_db = 20.0 * std::log10(m.gain_count + 1e-300);

    const double tx_fs = std::ldexp(1.0, tx_bits - 1);
    const double rx_fs = std::ldexp(1.0, rx_bits - 1);
    m.gain_normalized = (rx_fs > 0.0) ? m.gain_count * tx_fs / rx_fs : 0.0;
    m.gain_normalized_db = 20.0 * std::log10(m.gain_normalized + 1e-300);
    m.normalized_gain_ok = std::fabs(m.gain_normalized_db) <= kNormalizedGainOkDb;

    // scale-independent residual over the aligned full period.
    double err = 0.0;
    double err_active = 0.0, ey_active = 0.0;
    std::size_t active = 0;
    const double tx_peak_mag = std::sqrt(peak_tx);
    const double thresh = 0.1 * tx_peak_mag;
    const std::complex<double> dc_aligned = sum_rx / static_cast<double>(P);
    const std::complex<double> dc_txv = sum_tx / static_cast<double>(P);
    double err_dc_removed = 0.0, ey_dc_removed = 0.0;
    for (std::size_t mm = 0; mm < P; ++mm) {
        const std::complex<double> e = aligned[mm] - a * txv[mm];
        err += std::norm(e);
        if (std::abs(txv[mm]) > thresh) {
            err_active += std::norm(e);
            ey_active += std::norm(aligned[mm]);
            ++active;
        }
        const std::complex<double> e2 =
            (aligned[mm] - dc_aligned) - a * (txv[mm] - dc_txv);
        err_dc_removed += std::norm(e2);
        ey_dc_removed += std::norm(aligned[mm] - dc_aligned);
    }
    (void)active;

    m.normalized_residual = (ey > 0.0) ? err / ey : 0.0;
    m.evm_pct = 100.0 * std::sqrt(m.normalized_residual);
    m.corr = (ex * ey > 0.0) ? std::abs(cc) / std::sqrt(ex * ey) : 0.0;
    m.corr_swap = (ex * ey > 0.0) ? std::abs(cswap) / std::sqrt(ex * ey) : 0.0;
    m.corr_conj = (ex * ey > 0.0) ? std::abs(cconj) / std::sqrt(ex * ey) : 0.0;

    // Consistency: normalized_residual must equal 1 - corr^2 for the optimal LS
    // fit.  This is the guard that forbids a low corr from ever reading as a low
    // EVM again.
    const double resid_from_corr = 1.0 - m.corr * m.corr;
    m.nmse_evm_consistent =
        std::fabs(m.normalized_residual - resid_from_corr) <= 1e-6;

    m.nmse_full_period = m.normalized_residual;
    m.nmse_dc_preserved = m.normalized_residual;
    m.nmse_active_region = (ey_active > 0.0) ? err_active / ey_active : 0.0;
    m.nmse_dc_removed = (ey_dc_removed > 0.0) ? err_dc_removed / ey_dc_removed : 0.0;

    m.rms_tx = std::sqrt(ex / static_cast<double>(P));
    m.rms_rx = std::sqrt(ey / static_cast<double>(P));
    m.dc_tx = std::abs(sum_tx) / static_cast<double>(P);
    m.dc_rx = std::abs(sum_rx) / static_cast<double>(P);
    m.papr_tx_db = m.rms_tx > 0.0
        ? 10.0 * std::log10(peak_tx / (m.rms_tx * m.rms_tx)) : 0.0;
    m.papr_rx_db = m.rms_rx > 0.0
        ? 10.0 * std::log10(peak_rx / (m.rms_rx * m.rms_rx)) : 0.0;

    // fix8 Task A: per-sample TX/RX peak (max |I|,|Q|) and clip counts against the
    // DATA-FORMAT rails derived from tx_bits/rx_bits (never hardcoded 2047).  Use
    // long long for the magnitude so abs(INT16_MIN) never overflows.
    long long tx_peak_abs = 0, rx_peak_abs = 0;
    for (std::int16_t v : tx) {
        const long long a = v < 0 ? -static_cast<long long>(v)
                                  : static_cast<long long>(v);
        if (a > tx_peak_abs) tx_peak_abs = a;
        if (v >= m.tx_positive_rail || v <= m.tx_negative_rail) ++m.tx_clip_count;
    }
    for (std::int16_t v : rx) {
        const long long a = v < 0 ? -static_cast<long long>(v)
                                  : static_cast<long long>(v);
        if (a > rx_peak_abs) rx_peak_abs = a;
        if (v >= m.rx_positive_rail || v <= m.rx_negative_rail) ++m.rx_clip_count;
    }
    m.tx_peak = static_cast<int>(tx_peak_abs);
    m.rx_peak = static_cast<int>(rx_peak_abs);
    m.tx_clipped = (m.tx_clip_count > 0);
    m.rx_clipped = (m.rx_clip_count > 0);

    // residual CFO / phase drift over the aligned full period (two halves).
    m.cfo_hz = 0.0;
    m.phase_drift_deg = 0.0;
    if (P >= 2) {
        const std::size_t H = P / 2;
        std::complex<double> c1(0.0, 0.0), c2(0.0, 0.0);
        for (std::size_t mm = 0; mm < H; ++mm)
            c1 += aligned[mm] * std::conj(txv[mm]);
        for (std::size_t mm = H; mm < P; ++mm)
            c2 += aligned[mm] * std::conj(txv[mm]);
        if (std::abs(c1) > 1e-30 && std::abs(c2) > 1e-30) {
            double dtheta = std::arg(c2) - std::arg(c1);
            while (dtheta > kPi) dtheta -= 2.0 * kPi;
            while (dtheta < -kPi) dtheta += 2.0 * kPi;
            m.phase_drift_deg = dtheta * 180.0 / kPi;
            m.cfo_hz = dtheta * static_cast<double>(fs) /
                       (2.0 * kPi * static_cast<double>(H));
        }
    }
    return m;
}

// fix6 verdict mapping (observation-only, never a PASS gate).  Waveform fidelity and
// circular-origin uniqueness are now SEPARATE conclusions: sync_origin is reported
// independently, and only an UNEXPLAINED competing lobe (m.sync.origin == Ambiguous
// -> different waveforms, best alignment undeterminable) fails fidelity as
// CIRCULAR_SYNC_AMBIGUOUS.  AMBIGUOUS_EQUIVALENT (multiple equivalent origins, same
// waveform) does NOT block PRESERVES_IQ.  The fixed peak_ratio >= 2 gate is removed.
inline const char* fidelity_verdict_fix6(const SyncFidelityMetrics& m) {
    if (m.rx_complex < kMinCaptureComplex)
        return "INSUFFICIENT_EVIDENCE";
    if (m.capture_too_short)
        return "CAPTURE_TOO_SHORT";
    if (m.rx_all_zero)
        return "RX_ALL_ZERO";
    if (m.rms_rx < kRxLowAmplitudeCounts)
        return "RX_LOW_AMPLITUDE";
    if (m.sync.origin == SyncOrigin::Ambiguous)
        return "CIRCULAR_SYNC_AMBIGUOUS";
    if (m.corr < kSyncCorrThreshold)
        return "DIGITAL_LOOPBACK_DISTORTS_IQ";
    if (m.corr >= kSyncCorrThreshold && !m.tx_clipped && !m.rx_clipped &&
        m.normalized_gain_ok && m.nmse_evm_consistent)
        return "DIGITAL_LOOPBACK_PRESERVES_IQ";
    return "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN";
}

// Only DIGITAL_LOOPBACK_PRESERVES_IQ counts as a fidelity PASS.
inline bool fidelity_gate_ok_fix6(const char* verdict) {
    return std::string(verdict) == "DIGITAL_LOOPBACK_PRESERVES_IQ";
}

}  // namespace iqdloop_sync
