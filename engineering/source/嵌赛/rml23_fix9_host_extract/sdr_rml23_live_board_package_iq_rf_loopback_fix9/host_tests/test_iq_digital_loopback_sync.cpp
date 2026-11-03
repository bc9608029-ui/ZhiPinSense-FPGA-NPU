// test_iq_digital_loopback_sync.cpp -- host tests for Stage H-E / Route E fix6:
// the full-period FFT circular synchronization + scale-independent fidelity in
// board_package/iq_digital_loopback_sync.hpp, the classification-window selection in
// board_package/iq_digital_loopback.hpp, plus the TX DMA payload verify in
// board_package/iq_digital_loopback_transfer.hpp.
//
// fix5 established the full-period FFT circular cross-correlation and the
// scale-independent residual (denominator = RX energy).  fix6 splits "waveform
// fidelity" from "circular-origin uniqueness":
//   * the TX's own circular autocorrelation predicts the cross-correlation
//     sidelobes a clean loopback inherits, so a multi-peak correlation is no longer
//     a fixed peak_ratio >= 2 gate and a repeating/tone TX is AMBIGUOUS_EQUIVALENT
//     (same waveform) rather than distortion; only an UNEXPLAINED competing lobe
//     (a genuinely different waveform) blocks as CIRCULAR_SYNC_AMBIGUOUS;
//   * the classification window is selected by aligning the naive decimated stream
//     against the Route D recovered tensor (which may straddle the zero-guard / cyclic
//     boundary), instead of trusting two naive frames.
//
// These tests verify, in order:
//   * the FFT circular cross-correlation matches a direct O(P^2) reference, with
//     the exact direction/shift convention (rx[j] = tx[(j-d) mod P] => shift==d);
//   * full-period sync at cyclic offsets 0/1/4095/4096/P-1, cross-period, two-period;
//   * complex gain/phase recovery, the 1/16 count-domain scale, IQ swap, conjugate;
//   * the transfer-layer stale-file negative and TX DMA payload SHA pre/post;
//   * corr-low does NOT read as a false low EVM;
//   * fix6: TX autocorrelation normalization; tone -> AMBIGUOUS_EQUIVALENT (not
//     distortion); PRBS unique origin; periodic [A,A] -> equivalent; TX=[A,C] vs
//     RX=[A,A] -> CIRCULAR_SYNC_AMBIGUOUS (unexplained competing lobe);
//   * classification-window selection (delay_offset + SHA equal / not equal);
//   * guard-region (transient/trailing) exclusion; capture-too-short.
//
// iCraft-free and libiio-free.  The transfer-layer tests link ../sdr_adapter/pluto_tx.cpp
// (the real PlutoTx safety state machine) against the scriptable FakePlutoDevice.

#include "../board_package/iq_digital_loopback_sync.hpp"
#include "../board_package/iq_digital_loopback_transfer.hpp"
#include "../board_package/iq_digital_loopback.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

constexpr double kPi = 3.141592653589793238462643383279502884;

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// ---- deterministic waveforms -------------------------------------------------

// ±A pseudo-random I/Q (deterministic LCG, high bits), aperiodic over any P, so
// its circular autocorrelation has a sharp unique peak and I/Q are independent.
std::vector<std::int16_t> make_prbs(std::size_t P, int A, std::uint32_t seed) {
    std::vector<std::int16_t> iq(P * 2);
    std::uint32_t s = seed ? seed : 0x9e3779b9u;
    auto bit = [&s]() -> int {
        s = s * 1664525u + 1013904223u;   // Numerical Recipes LCG
        return static_cast<int>((s >> 24) & 1u);   // high bits: well-distributed
    };
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(bit() ? A : -A);
        iq[k * 2 + 1] = static_cast<std::int16_t>(bit() ? A : -A);
    }
    return iq;
}

// Complex tone with `cycles` integer cycles over P (exact period-P): its circular
// autocorrelation is FLAT, so it is multi-peak-ambiguous by construction.
std::vector<std::int16_t> make_tone(std::size_t P, int A, std::size_t cycles) {
    std::vector<std::int16_t> iq(P * 2);
    const double w = 2.0 * kPi * static_cast<double>(cycles) / static_cast<double>(P);
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(A * std::cos(w * k)));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::llround(A * std::sin(w * k)));
    }
    return iq;
}

// Cyclically shift an interleaved int16 waveform by `d` complex samples.
std::vector<std::int16_t> shift_iq(const std::vector<std::int16_t>& tx, std::size_t d) {
    const std::size_t P = tx.size() / 2;
    std::vector<std::int16_t> out(tx.size());
    for (std::size_t k = 0; k < P; ++k) {
        const std::size_t src = (k + P - (d % P)) % P;
        out[k * 2 + 0] = tx[src * 2 + 0];
        out[k * 2 + 1] = tx[src * 2 + 1];
    }
    return out;
}

// Apply a complex gain g*exp(i*phase) to an interleaved int16 waveform.
std::vector<std::int16_t> apply_gain(const std::vector<std::int16_t>& tx,
                                     double g, double phase_deg) {
    const std::complex<double> a = std::polar(g, phase_deg * kPi / 180.0);
    std::vector<std::int16_t> out(tx.size());
    for (std::size_t k = 0; k + 1 < tx.size(); k += 2) {
        const std::complex<double> y = a * std::complex<double>(tx[k], tx[k + 1]);
        out[k] = static_cast<std::int16_t>(std::llround(y.real()));
        out[k + 1] = static_cast<std::int16_t>(std::llround(y.imag()));
    }
    return out;
}

// Integer-divide (toward zero) every sample -- models the 12-bit DAC taking the
// top 12 bits of a 16-bit word (count-domain 1/16).
std::vector<std::int16_t> divide_iq(const std::vector<std::int16_t>& tx, int div) {
    std::vector<std::int16_t> out(tx.size());
    for (std::size_t k = 0; k < tx.size(); ++k)
        out[k] = static_cast<std::int16_t>(tx[k] / div);
    return out;
}

// Build an interleaved int16 RX capture of `total_complex` samples whose stable
// region (after `transient` garbage samples) is `sig` cyclically shifted by `d`:
//   rx[transient + j] = sig[(j - d) mod P].
// The transient prefix is deterministic NONZERO garbage (it must be discarded).
std::vector<std::int16_t> make_rx(const std::vector<std::int16_t>& sig,
                                  std::size_t d, std::size_t transient,
                                  std::size_t total_complex) {
    const std::size_t P = sig.size() / 2;
    std::vector<std::int16_t> rx(total_complex * 2, 0);
    for (std::size_t j = 0; j < total_complex; ++j) {
        if (j < transient) {
            rx[j * 2 + 0] = static_cast<std::int16_t>((j * 37 + 11) % 2000 - 1000);
            rx[j * 2 + 1] = static_cast<std::int16_t>((j * 53 + 7) % 2000 - 1000);
        } else {
            const std::size_t src = (j - transient + P - (d % P)) % P;
            rx[j * 2 + 0] = sig[src * 2 + 0];
            rx[j * 2 + 1] = sig[src * 2 + 1];
        }
    }
    return rx;
}

// ---- 1. FFT circular cross-correlation reference (single-test-verified) ----
void test_fft_circular_corr_reference() {
    const std::size_t P = 64;
    const std::size_t d = 13;
    const auto tx = make_prbs(P, 500, 1234);
    const auto win = shift_iq(tx, d);   // win[j] = tx[(j-d) mod P]

    std::vector<std::complex<double>> x(P), y(P);
    for (std::size_t j = 0; j < P; ++j) {
        x[j] = std::complex<double>(win[j * 2], win[j * 2 + 1]);
        y[j] = std::complex<double>(tx[j * 2], tx[j * 2 + 1]);
    }

    // Direct O(P^2): c[k] = |sum_j x[j] conj(y[(j-k) mod P])|
    std::vector<double> c_direct(P, 0.0);
    for (std::size_t k = 0; k < P; ++k) {
        std::complex<double> acc(0.0, 0.0);
        for (std::size_t j = 0; j < P; ++j) {
            const std::size_t idx = (j + P - k) % P;
            acc += x[j] * std::conj(y[idx]);
        }
        c_direct[k] = std::abs(acc);
    }
    const auto c_fft = iqdloop_sync::circular_cross_corr(x, y);

    check(c_fft.size() == P, "circular_cross_corr returns P values");
    double max_err = 0.0;
    std::size_t best_direct = 0, best_fft = 0;
    for (std::size_t k = 0; k < P; ++k) {
        max_err = std::max(max_err, std::fabs(c_fft[k] - c_direct[k]));
        if (c_direct[k] > c_direct[best_direct]) best_direct = k;
        if (c_fft[k] > c_fft[best_fft]) best_fft = k;
    }
    check(max_err < 1e-6, "FFT circular corr matches O(P^2) reference (max_err tiny)");
    check(best_direct == d, "direct argmax == d (direction/shift convention)");
    check(best_fft == d, "FFT argmax == d");
}

// ---- 2. full-period sync at cyclic offsets 0/1/4095/4096/P-1 ----
void test_cyclic_offsets() {
    const std::size_t P = 8192;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 900, 5678);
    const std::size_t offsets[] = {0, 1, 4095, 4096, P - 1};
    for (std::size_t d : offsets) {
        const auto rx = make_rx(tx, d, transient, transient + P);
        const auto s = iqdloop_sync::circular_sync(tx, rx, transient);
        const bool ok = (s.circular_shift == d) &&
                        (s.aligned_start == transient + d) &&
                        (s.wrap_count == (transient + d) / P) &&
                        (s.compared_samples == P);
        check(ok, "cyclic offset d=" + std::to_string(d) + " -> circular_shift==" +
                   std::to_string(d));
        if (!ok)
            std::printf("    (got shift=%zu aligned_start=%zu wrap=%zu)\n",
                        s.circular_shift, s.aligned_start, s.wrap_count);
    }
}

// ---- 3. cross-period capture (aligned start wraps past a period boundary) ----
void test_cross_period_capture() {
    const std::size_t P = 128;
    const std::size_t transient = 100;   // force aligned_start to cross P
    const std::size_t d = 50;
    const auto tx = make_prbs(P, 700, 2468);
    const auto rx = make_rx(tx, d, transient, transient + P);
    const auto s = iqdloop_sync::circular_sync(tx, rx, transient);
    check(s.circular_shift == d, "cross-period: circular_shift == d");
    check(s.aligned_start == transient + d, "cross-period: aligned_start == transient + d");
    check(s.wrap_count >= 1, "cross-period: wrap_count >= 1 (delay spans a period)");
}

// ---- 4. two-period capture (>= 2 periods captured; one full period selected) ----
void test_two_period_capture() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const std::size_t d = 777;
    const auto tx = make_prbs(P, 850, 1357);
    const std::size_t total = transient + 2 * P + 7;   // two periods plus a bit
    const auto rx = make_rx(tx, d, transient, total);
    const auto s = iqdloop_sync::circular_sync(tx, rx, transient);
    check(s.circular_shift == d, "two-period: circular_shift == d");
    check(s.compared_samples == P, "two-period: exactly one period compared");
    check(s.aligned_start == transient + d, "two-period: aligned_start == transient + d");
}

// ---- 5. complex gain + phase recovery (LS fit) ----
void test_complex_gain_phase() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const std::size_t d = 42;
    const double g = 0.8, phase = 30.0;
    const auto tx = make_prbs(P, 900, 3141);
    const auto sig = apply_gain(tx, g, phase);
    const auto rx = make_rx(sig, d, transient, transient + P);
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, /*tx_bits=*/16, /*rx_bits=*/16, transient);
    check(m.corr > 0.999, "gain/phase: corr ~ 1");
    check(std::fabs(m.gain_db - 20.0 * std::log10(g)) < 0.1, "gain/phase: gain_db ~ 20log10(g)");
    double dphase = std::fabs(m.phase_deg - phase);
    if (dphase > 180.0) dphase = 360.0 - dphase;
    check(dphase < 2.0, "gain/phase: phase_deg ~ phase");
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) ==
              "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "gain/phase: PRESERVES_IQ (same-domain unity gain)");
}

// ---- 6. count-domain 1/16 (TX16/RX12): count gain -24 dB, normalized ~ 0 dB ----
void test_count_domain_1_16() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const std::size_t d = 3;
    const auto tx = make_prbs(P, 1024, 1111);   // ±1024 -> /16 = ±64 exactly
    const auto sig = divide_iq(tx, 16);
    const auto rx = make_rx(sig, d, transient, transient + P);
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, /*tx_bits=*/16, /*rx_bits=*/12, transient);
    check(std::fabs(m.gain_db - 20.0 * std::log10(1.0 / 16.0)) < 0.2,
          "count-domain: count gain ~ -24.08 dB");
    check(std::fabs(m.gain_normalized_db) < 0.5,
          "count-domain: normalized gain ~ 0 dB (NOT attenuation)");
    check(m.normalized_gain_ok, "count-domain: normalized_gain_ok");
    check(m.corr > 0.999, "count-domain: corr ~ 1");
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) ==
              "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "count-domain: PRESERVES_IQ (the 1/16 is a count-domain scale, not loss)");
}

// ---- 7. IQ swap -> swap-correlation dominates normal-correlation ----
// A genuine I<->Q swap is a DISTINCT signal, so its normal correlation with TX is
// flat (the sync cannot uniquely align it).  The swap detection must therefore be
// shift-invariant: the max swap-correlation over all circular shifts must dominate
// the max normal-correlation.  (The fixed-shift corr_swap metric on the aligned
// window is only meaningful when the sync finds a unique peak, which a swapped
// signal never does.)
void test_iq_swap() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 900, 7777);
    std::vector<std::int16_t> swapped(tx.size());
    for (std::size_t k = 0; k + 1 < tx.size(); k += 2) {
        swapped[k] = tx[k + 1];
        swapped[k + 1] = tx[k];
    }
    const auto rx = make_rx(swapped, 0, transient, transient + P);

    std::vector<std::complex<double>> win(P), txv(P), swv(P);
    for (std::size_t j = 0; j < P; ++j) {
        win[j] = std::complex<double>(rx[(transient + j) * 2], rx[(transient + j) * 2 + 1]);
        txv[j] = std::complex<double>(tx[j * 2], tx[j * 2 + 1]);
        swv[j] = std::complex<double>(swapped[j * 2], swapped[j * 2 + 1]);
    }
    const auto c_norm = iqdloop_sync::circular_cross_corr(win, txv);
    const auto c_swap = iqdloop_sync::circular_cross_corr(win, swv);
    const double mx_norm = *std::max_element(c_norm.begin(), c_norm.end());
    const double mx_swap = *std::max_element(c_swap.begin(), c_swap.end());
    check(mx_swap > mx_norm, "iq-swap: swap-correlation peak dominates normal-correlation");

    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) !=
              "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "iq-swap: NOT PRESERVES_IQ");
}

// ---- 8. conjugate -> conjugate-correlation dominates normal-correlation ----
void test_conjugate() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 900, 8888);
    std::vector<std::int16_t> conj(tx.size());
    for (std::size_t k = 0; k + 1 < tx.size(); k += 2) {
        conj[k] = tx[k];
        conj[k + 1] = static_cast<std::int16_t>(-tx[k + 1]);
    }
    const auto rx = make_rx(conj, 0, transient, transient + P);

    std::vector<std::complex<double>> win(P), txv(P), cjv(P);
    for (std::size_t j = 0; j < P; ++j) {
        win[j] = std::complex<double>(rx[(transient + j) * 2], rx[(transient + j) * 2 + 1]);
        txv[j] = std::complex<double>(tx[j * 2], tx[j * 2 + 1]);
        cjv[j] = std::complex<double>(conj[j * 2], conj[j * 2 + 1]);
    }
    const auto c_norm = iqdloop_sync::circular_cross_corr(win, txv);
    const auto c_conj = iqdloop_sync::circular_cross_corr(win, cjv);
    const double mx_norm = *std::max_element(c_norm.begin(), c_norm.end());
    const double mx_conj = *std::max_element(c_conj.begin(), c_conj.end());
    check(mx_conj > mx_norm, "conjugate: conj-correlation peak dominates normal-correlation");

    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) !=
              "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "conjugate: NOT PRESERVES_IQ");
}

// ---- 11. corr-low does NOT read as a false low EVM ----
void test_corr_low_no_false_evm() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 500, 2020);
    const auto noise = make_prbs(P, 1000, 9999);
    std::vector<std::int16_t> sig(tx.size());
    for (std::size_t k = 0; k < tx.size(); ++k)
        sig[k] = static_cast<std::int16_t>(tx[k] + 2 * noise[k]);
    const auto rx = make_rx(sig, 0, transient, transient + P);
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(m.corr < 0.9, "corr-low: corr < 0.9");
    check(m.evm_pct > 50.0, "corr-low: EVM is LARGE (not a false 6.6%)");
    check(m.nmse_evm_consistent, "corr-low: normalized_residual == 1 - corr^2");
    const std::string v = iqdloop_sync::fidelity_verdict_fix6(m);
    check(v == "DIGITAL_LOOPBACK_DISTORTS_IQ" || v == "CIRCULAR_SYNC_AMBIGUOUS",
          "corr-low: never PRESERVES_IQ");
}

// ---- 12. fix6 requirement 3: TX circular autocorrelation normalization ----
void test_circular_autocorr_norm() {
    const std::size_t P = 1024;
    const auto tone_iq = make_tone(P, 900, 16);
    const auto prbs_iq = make_prbs(P, 900, 999);
    std::vector<std::complex<double>> tone(P), prbs(P);
    for (std::size_t k = 0; k < P; ++k) {
        tone[k] = std::complex<double>(tone_iq[k * 2], tone_iq[k * 2 + 1]);
        prbs[k] = std::complex<double>(prbs_iq[k * 2], prbs_iq[k * 2 + 1]);
    }
    const auto rt = iqdloop_sync::circular_autocorr_norm(tone);
    const auto rp = iqdloop_sync::circular_autocorr_norm(prbs);
    double min_tone = 2.0, max_prbs = -1.0;
    for (std::size_t k = 0; k < P; ++k) min_tone = std::min(min_tone, rt[k]);
    for (std::size_t k = 1; k < P; ++k) max_prbs = std::max(max_prbs, rp[k]);
    check(rt[0] == 1.0, "autocorr: tone r_norm[0] == 1");
    check(rp[0] == 1.0, "autocorr: prbs r_norm[0] == 1");
    check(min_tone > 0.99, "autocorr: tone is FLAT (self-similar at every shift)");
    check(max_prbs < 0.5, "autocorr: prbs has a UNIQUE peak (low sidelobes)");
}

// ---- 13. fix6 requirement 5: tone -> AMBIGUOUS_EQUIVALENT, NOT distortion ----
void test_tone_equivalent_origins() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_tone(P, 900, 16);   // integer cycles -> flat autocorrelation
    const auto rx = make_rx(tx, 0, transient, transient + P);
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(m.corr > 0.999, "tone: corr ~ 1");
    check(m.sync.origin == iqdloop_sync::SyncOrigin::Equivalent,
          "tone: origin == Equivalent (multiple equivalent origins)");
    check(std::string(iqdloop_sync::sync_origin_name(m.sync.origin)) ==
              "AMBIGUOUS_EQUIVALENT",
          "tone: sync_origin == AMBIGUOUS_EQUIVALENT");
    check(m.sync.competing_peaks > 0, "tone: competing_peaks > 0");
    check(m.sync.unexplained_peaks == 0, "tone: unexplained_peaks == 0");
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) ==
              "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "tone: PRESERVES_IQ (equivalent origins are NOT distortion)");
    check(iqdloop_sync::fidelity_gate_ok_fix6(iqdloop_sync::fidelity_verdict_fix6(m)),
          "tone: fidelity gate passes despite a low peak_ratio");
}

// ---- 14. PRBS unique peak (origin == Unique) ----
void test_prbs_unique_peak() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const std::size_t d = 511;
    const auto tx = make_prbs(P, 900, 4242);
    const auto rx = make_rx(tx, d, transient, transient + P);
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(m.sync.circular_shift == d, "prbs: circular_shift == d");
    check(m.sync.origin == iqdloop_sync::SyncOrigin::Unique, "prbs: origin == Unique");
    check(m.corr > 0.999, "prbs: corr ~ 1");
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) ==
              "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "prbs: PRESERVES_IQ");
}

// ---- 15. fix6: repeating (periodic) TX -> AMBIGUOUS_EQUIVALENT ----
void test_periodic_equivalent_origins() {
    const std::size_t L = 512;
    const std::size_t P = 2 * L;
    const auto half = make_prbs(L, 800, 333);
    std::vector<std::int16_t> tx(P * 2);
    for (std::size_t k = 0; k < L; ++k) {
        tx[k * 2] = half[k * 2];               tx[k * 2 + 1] = half[k * 2 + 1];
        tx[(L + k) * 2] = half[k * 2];         tx[(L + k) * 2 + 1] = half[k * 2 + 1];
    }
    const std::size_t transient = 16;
    const auto rx = make_rx(tx, 0, transient, transient + P);
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(m.sync.origin == iqdloop_sync::SyncOrigin::Equivalent,
          "periodic: origin == Equivalent (two identical halves)");
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) ==
              "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "periodic: PRESERVES_IQ");
}

// ---- 16. fix6 requirement 6: different waveforms -> CIRCULAR_SYNC_AMBIGUOUS ----
// TX = [A, C] (two DIFFERENT halves), RX = [A, A] (periodic).  The RX correlates
// equally with TX at shift 0 (matching the A half) and shift L (matching the C half),
// but TX is NOT self-similar at L (A != C), so the L-shift lobe is UNEXPLAINED ->
// the two candidate alignments produce DIFFERENT waveforms and the best alignment
// is undeterminable -> CIRCULAR_SYNC_AMBIGUOUS.
void test_unexplained_competing_peak_ambiguous() {
    const std::size_t L = 512;
    const std::size_t P = 2 * L;
    const auto A = make_prbs(L, 800, 111);
    const auto C = make_prbs(L, 800, 222);
    std::vector<std::int16_t> tx(P * 2), rxsig(P * 2);
    for (std::size_t k = 0; k < L; ++k) {
        tx[k * 2] = A[k * 2];               tx[k * 2 + 1] = A[k * 2 + 1];
        tx[(L + k) * 2] = C[k * 2];         tx[(L + k) * 2 + 1] = C[k * 2 + 1];
        rxsig[k * 2] = A[k * 2];            rxsig[k * 2 + 1] = A[k * 2 + 1];
        rxsig[(L + k) * 2] = A[k * 2];      rxsig[(L + k) * 2 + 1] = A[k * 2 + 1];
    }
    const std::size_t transient = 16;
    const auto rx = make_rx(rxsig, 0, transient, transient + P);
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(m.sync.origin == iqdloop_sync::SyncOrigin::Ambiguous,
          "ambiguous: origin == Ambiguous (unexplained competing lobe)");
    check(m.sync.unexplained_peaks > 0, "ambiguous: unexplained_peaks > 0");
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) ==
              "CIRCULAR_SYNC_AMBIGUOUS",
          "ambiguous: CIRCULAR_SYNC_AMBIGUOUS (different waveforms)");
    check(!iqdloop_sync::fidelity_gate_ok_fix6(iqdloop_sync::fidelity_verdict_fix6(m)),
          "ambiguous: fidelity gate fails");
}

// ---- 17. fix6 requirement 7: classification-window selection (pure logic) ----
std::vector<float> tensor_from_complex(const std::vector<std::complex<double>>& z) {
    const std::size_t N = z.size();
    std::vector<float> t(2 * N);
    for (std::size_t k = 0; k < N; ++k) {
        t[k] = static_cast<float>(z[k].real());
        t[N + k] = static_cast<float>(z[k].imag());
    }
    return t;
}

void test_classification_window_selection() {
    const std::size_t N = 1024;
    const auto ref_iq = make_prbs(N, 500, 77);
    std::vector<std::complex<double>> ref(N);
    for (std::size_t k = 0; k < N; ++k)
        ref[k] = std::complex<double>(ref_iq[k * 2], ref_iq[k * 2 + 1]);
    const std::vector<float> ref_tensor = tensor_from_complex(ref);

    const std::size_t frames = 2;
    const std::size_t total = frames * N;
    auto build_stream = [&](double g) {
        std::vector<std::complex<double>> stream(total, 0.0);
        for (std::size_t k = 0; k < total; ++k)   // low-level guard noise elsewhere
            stream[k] = std::complex<double>((k * 131 + 7) % 200 - 100,
                                             (k * 197 + 3) % 200 - 100);
        const int d = 700;
        for (std::size_t k = 0; k < N; ++k)
            stream[static_cast<std::size_t>(d) + k] = g * ref[k];
        std::vector<float> rec(frames * 2 * N);
        for (std::size_t f = 0; f < frames; ++f)
            for (std::size_t k = 0; k < N; ++k) {
                rec[f * 2 * N + k] = static_cast<float>(stream[f * N + k].real());
                rec[f * 2 * N + N + k] = static_cast<float>(stream[f * N + k].imag());
            }
        return rec;
    };

    // Non-bit-exact (1/16 count-domain gain): window located, scale-invariant metrics.
    const double g = 0.0625;
    const iqdloop::ClassificationWindow cw =
        iqdloop::select_classification_window(build_stream(g), ref_tensor);
    check(cw.valid, "window: valid window selected");
    check(cw.recovered_frames == frames, "window: recovered_frames == 2");
    check(cw.delay_offset == 700, "window: delay_offset == 700 (valid region located)");
    check(cw.tensor_corr > 0.99, "window: tensor_corr ~ 1");
    check(cw.tensor_nmse < 1e-4, "window: tensor_nmse ~ 0 (scale-independent)");
    check(std::fabs(cw.tensor_gain_db - 20.0 * std::log10(g)) < 0.1,
          "window: tensor_gain_db ~ 20log10(1/16)");
    check(!cw.sha_equal, "window: sha_equal false for a non-bit-exact stream");

    // Bit-exact (g = 1): SHA of the aligned window must match the reference byte-for-byte.
    const iqdloop::ClassificationWindow cw2 =
        iqdloop::select_classification_window(build_stream(1.0), ref_tensor);
    check(cw2.sha_equal, "window: sha_equal true for a bit-exact stream");
    check(cw2.aligned_sha256 == cw2.ref_sha256, "window: aligned_sha == ref_sha");
}

// ---- 14. guard-region exclusion (transient + trailing garbage excluded) ----
void test_guard_region_exclusion() {
    const std::size_t P = 1024;
    const std::size_t transient = 32;
    const std::size_t d = 8;
    const auto tx = make_prbs(P, 900, 6060);
    // Transient prefix filled with a LOUD wrong-shift copy (would dominate if not
    // discarded); the stable region holds the correct shift; trailing region is
    // additional garbage.  The sync must discard the transient and compare exactly
    // one period from the stable region.
    const std::size_t total = transient + P + 64;
    std::vector<std::int16_t> rx(total * 2, 0);
    const auto wrong = shift_iq(tx, 300);   // wrong shift, loud
    for (std::size_t j = 0; j < total; ++j) {
        if (j < transient) {
            rx[j * 2 + 0] = wrong[(j % P) * 2 + 0];
            rx[j * 2 + 1] = wrong[(j % P) * 2 + 1];
        } else {
            const std::size_t src = (j - transient + P - (d % P)) % P;
            rx[j * 2 + 0] = tx[src * 2 + 0];
            rx[j * 2 + 1] = tx[src * 2 + 1];
        }
    }
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(m.sync.circular_shift == d, "guard: transient/trailing garbage excluded (shift==d)");
    check(m.corr > 0.999, "guard: corr ~ 1 despite garbage regions");
}

// ---- 15. capture-too-short fail-closed ----
void test_capture_too_short() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 900, 12345);
    const auto rx = make_rx(tx, 0, transient, transient + P - 1);   // one short
    const auto m = iqdloop_sync::measure_fidelity_fix5(
        tx, rx, 2560000, 16, 16, transient);
    check(m.capture_too_short, "capture-too-short: capture_too_short set");
    check(std::string(iqdloop_sync::fidelity_verdict_fix6(m)) == "CAPTURE_TOO_SHORT",
          "capture-too-short: CAPTURE_TOO_SHORT (fail-closed)");
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

std::string write_frozen_file(const std::string& dir, const std::string& name,
                              const std::vector<std::int16_t>& iq) {
    const std::string path = dir + "/" + name;
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
    return path;
}
#endif

// ---- 9. stale previous-file negative (transfer-level flush) ----
void run_stale_previous_file_negative() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_iqdloop_sync_neg");
    const auto a = make_prbs(N, 900, 1);
    const auto b = make_prbs(N, 900, 2);
    const std::string pa = write_frozen_file(dir, "a.ci16", a);
    const std::string pb = write_frozen_file(dir, "b.ci16", b);
    const std::string sha_a = sdr::Sha256::hex(a.data(), a.size() * sizeof(std::int16_t));
    const std::string sha_b = sdr::Sha256::hex(b.data(), b.size() * sizeof(std::int16_t));

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.echo_tx_on_rx = true;              // digital-loopback echo model
    dev.stale_rx_without_recreate = true;  // arm the stale-leak failure model

    // First file A: flush runs, RX echoes A.
    const auto tr_a = iqdloop_run::transfer_one_file(
        dev, pa, N, sha_a, 2400000000ULL, 10.0, -40.0, 256, 0);
    check(tr_a.capture_ok, "stale-neg: file A capture_ok");
    // Second file B (previous file was A): the per-file flush must prevent any
    // leakage of A into B -- B's RX must match B (a non-zero, B-SHA-verified TX).
    const auto tr_b = iqdloop_run::transfer_one_file(
        dev, pb, N, sha_b, 2400000000ULL, 10.0, -40.0, 256, 0);
    check(tr_b.capture_ok, "stale-neg: file B capture_ok (flush prevents stale A)");
    bool b_nonzero = false;
    for (std::int16_t s : tr_b.rx)
        if (s != 0) { b_nonzero = true; break; }
    check(b_nonzero, "stale-neg: file B RX non-zero (no stale-leak)");

    // Device-level negative control: with the stale model armed, a fresh cyclic TX
    // WITHOUT recreate_rx_buffer returns all-zero (the leakage signature).
    dev.tx_start_cyclic(b);
    const iio::RawChunk c0 = dev.read_rx(256, 1000);
    bool all_zero = true;
    for (std::size_t k = 0; k < c0.samples_available; ++k)
        if (c0.samples[k] != 0) { all_zero = false; break; }
    check(all_zero && c0.samples_available > 0,
          "stale-neg: without recreate, read_rx is all-zero (signature present)");

    ::unlink(pa.c_str());
    ::unlink(pb.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 10. TX DMA payload SHA pre/post (identity fake format) ----
void run_dma_payload_sha() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_iqdloop_sync_dma");
    const auto iq = make_prbs(N, 900, 3);
    const std::string path = write_frozen_file(dir, "dma.ci16", iq);
    const std::string sha = sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));

    // Identity TX format (16b/16b shift0 fully-defined) so the fake DMA payload
    // (host -> raw) is byte-identical to the host bytes.
    pluto::DataFormatInfo idfmt;
    idfmt.length_bits = 16; idfmt.bits = 16; idfmt.shift = 0;
    idfmt.is_signed = true; idfmt.is_fully_defined = true;

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.echo_tx_on_rx = true;
    dev.tx_fmt_ = idfmt;

    // Clean: the DMA payload SHA must equal the post-scale (== pre-scale) SHA.
    const auto tr_ok = iqdloop_run::transfer_one_file(
        dev, path, N, sha, 2400000000ULL, 10.0, -40.0, 256, 0, nullptr, 1.0, idfmt, idfmt);
    check(tr_ok.tx_dma_payload_ok, "dma-sha: payload ok for a clean identity-format push");
    check(tr_ok.tx_dma_payload_sha == tr_ok.tx_sha_post_scale,
          "dma-sha: tx_dma_payload_sha == sha_post");
    check(tr_ok.tx_dma_payload_sha == sha, "dma-sha: payload sha == frozen SHA");

    // Corrupt: flip one DMA bit; the payload SHA must now differ (fail-closed).
    dev.corrupt_tx_dma_payload = true;
    const auto tr_bad = iqdloop_run::transfer_one_file(
        dev, path, N, sha, 2400000000ULL, 10.0, -40.0, 256, 0, nullptr, 1.0, idfmt, idfmt);
    check(!tr_bad.tx_dma_payload_ok, "dma-sha: corrupted payload -> !tx_dma_payload_ok");
    check(tr_bad.tx_dma_payload_sha != tr_bad.tx_sha_post_scale,
          "dma-sha: corrupted payload sha != sha_post");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

}  // namespace

int main() {
    std::printf("test_iq_digital_loopback_sync\n");
    test_fft_circular_corr_reference();
    test_cyclic_offsets();
    test_cross_period_capture();
    test_two_period_capture();
    test_complex_gain_phase();
    test_count_domain_1_16();
    test_iq_swap();
    test_conjugate();
    test_corr_low_no_false_evm();
    test_circular_autocorr_norm();
    test_tone_equivalent_origins();
    test_prbs_unique_peak();
    test_periodic_equivalent_origins();
    test_unexplained_competing_peak_ambiguous();
    test_classification_window_selection();
    test_guard_region_exclusion();
    test_capture_too_short();
    run_stale_previous_file_negative();
    run_dma_payload_sha();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
