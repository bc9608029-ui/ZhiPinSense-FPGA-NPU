#pragma once

// iq_rf_training_frame.hpp -- Route F fix9r Task C: the category-independent
// TRAINING FRAME that brackets each TX burst so the receiver can recover the
// PER-FILE complex gain / phase / timing / CFO / SRO / drift from KNOWN samples,
// never from the payload label or the payload's optimal fit (§7 leak ban).
//
// This is the same-machine-Pluto (fix9r) sibling of the fix10 air-interface frame
// (iq_external_rf_frame.hpp), reduced to what the root cause needs: fix9 collapsed
// one global complex gain across files whose phase is random per TX re-key, so
// fix9r recovers gain/phase/timing PER FILE from a known preamble + tail.  The
// frame is still class-independent and constant-envelope, so the same header and
// recovery (iq_rf_per_frame_recovery.hpp) are reusable for double-SDR (fix10).
//
// Burst layout at 2.56 MSPS (== the D2 payload rate, kPayloadComplex == 53760):
//
//   [preamble 1024][settling-zero 1024][training 1024][payload 53760]
//   [guard-zero 2048][tail 1024]
//
//   * preamble: a length-1024 Zadoff-Chu sequence (root r=1, even N)
//         u[k] = exp(-j*pi*k^2/N),  k = 0..N-1
//     constant envelope, single sharp autocorrelation peak -> timing + LS gain/phase
//     + phase-slope CFO.
//   * settling-zero: 1024 samples of silence isolating the ZC broadband transient
//     from the payload-domain training block (fix9r2g).
//   * training: 1024-sample payload-domain GAIN training block (fix9r2g) -- modulated
//     16QAM, narrowband, deterministic, label-free -- used to estimate the FINAL
//     complex scalar gain that recovers the payload (the preamble gain does NOT apply
//     to the payload: FIXED_SCALE_JUMP).  kPayloadStart == 3072 is unchanged.
//   * guard: 2048 samples of silence isolating payload/tail and absorbing the
//     per-file timing jitter.
//   * tail: the SAME 1024-sample Zadoff-Chu block (root r=3), used to measure the
//     sampling-rate offset (SRO) by re-locating it against its expected position.
//
// iCraft-free and libiio-free: it compiles identically on the host and the board.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqrftrain {

constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr std::uint64_t kFs = 2560000;          // sample rate (== D2 payload rate)

// ---- burst structure (complex samples) --------------------------------------
constexpr std::size_t kPreambleComplex = 1024;  // Zadoff-Chu training block
constexpr std::size_t kGuardComplex = 2048;     // silence either side of the payload
constexpr std::size_t kTailComplex = 1024;      // trailing training block (== preamble)
constexpr std::size_t kPayloadComplex = 53760;  // D2 AC-only payload

// positions relative to burst start (preamble sample 0)
constexpr std::size_t kPayloadStart = kPreambleComplex + kGuardComplex;        // 3072
constexpr std::size_t kTailStart =
    kPayloadStart + kPayloadComplex + kGuardComplex;                           // 58880
constexpr std::size_t kTotalBurstComplex = kTailStart + kTailComplex;          // 59904

constexpr double kTrainAmp = 2048.0;   // preamble/tail int16 amplitude (12-bit FS)
constexpr int kZadoffChuRoot = 1;      // preamble root r (coprime to N)
constexpr int kTailZadoffChuRoot = 3;  // tail root (different from preamble -> disambiguates)

// ---- training-frame identity (Task R3 design audit) ---------------------------
// Every recovery/reference must agree on the EXACT same training frame; a version
// bump breaks any stale reference at the build, not silently at the board.
constexpr int kTrainingVersion = 2;    // fix9r2 (== fix9r: same ZC sequence, same roots)
// The Zadoff-Chu frame is fully deterministic (a closed-form phase ramp), so there
// is NO random seed: kTrainingSeed is recorded as 0 == "not applicable" so the audit
// can assert "seed N/A" explicitly instead of leaving the field unset.
constexpr std::uint64_t kTrainingSeed = 0;   // 0 == N/A (ZC is seed-free)

// SRO estimator search half-width (samples) around the expected tail position.
constexpr std::size_t kTailSearchHalf = 64;

// ---- payload-domain gain training block (fix9r2g) -----------------------------
// A common, deterministic, label-free, narrowband-MODULATED training block placed
// immediately before the payload (at kPayloadTrainingOffset), sharing the payload's
// final TX sample domain / buffer / RF link.  It is used ONLY to estimate the FINAL
// complex scalar gain that recovers the payload; the ZC preamble stays the sync /
// CFO / SRO reference.  32 x 16QAM/sqrt(10) symbols, 32 samples/symbol ~ 80 kHz
// (narrowband, matching the payload's clean-scalar residual), rectangular pulse,
// RMS-normalized to kPayloadTrainingAmp (== kTrainAmp).
constexpr std::size_t kPayloadTrainingComplex = 1024;            // 32 sym x 32 samp
constexpr std::size_t kPayloadTrainingOffset = 2048;             // ZC 1024 + settling-zero 1024
constexpr std::uint64_t kPayloadTrainingSeed = 0x2A9E1B7DULL;    // fixed LCG seed (frozen)
constexpr std::size_t kPayloadTrainingSamplesPerSymbol = 32;
constexpr double kPayloadTrainingAmp = 2048.0;                   // == kTrainAmp

// ---------------------------------------------------------------------------
// Known sequences (deterministic, category-independent).
// ---------------------------------------------------------------------------

// A length-1024 Zadoff-Chu block (unit envelope) for a given root r (coprime to N).
inline std::vector<std::complex<double>> zadoff_chu(int root) {
    std::vector<std::complex<double>> u(kPreambleComplex);
    for (std::size_t k = 0; k < kPreambleComplex; ++k) {
        const double kd = static_cast<double>(k);
        const double ph = -kPi * static_cast<double>(root) * kd * kd /
                          static_cast<double>(kPreambleComplex);
        u[k] = std::complex<double>(std::cos(ph), std::sin(ph));
    }
    return u;
}

// Preamble as interleaved int16 [I0,Q0,...] at amplitude kTrainAmp (TX-side builder).
inline std::vector<std::int16_t> preamble() {
    const std::vector<std::complex<double>> u = zadoff_chu(kZadoffChuRoot);
    std::vector<std::int16_t> out(kPreambleComplex * 2);
    for (std::size_t k = 0; k < kPreambleComplex; ++k) {
        out[k * 2 + 0] = static_cast<std::int16_t>(
            std::lround(kTrainAmp * u[k].real()));
        out[k * 2 + 1] = static_cast<std::int16_t>(
            std::lround(kTrainAmp * u[k].imag()));
    }
    return out;
}

// Tail: the 1024-sample Zadoff-Chu block with a DIFFERENT root, so a preamble
// search can never lock onto it (same-machine and double-SDR alike).
inline std::vector<std::int16_t> tail() {
    const std::vector<std::complex<double>> u = zadoff_chu(kTailZadoffChuRoot);
    std::vector<std::int16_t> out(kTailComplex * 2);
    for (std::size_t k = 0; k < kTailComplex; ++k) {
        out[k * 2 + 0] = static_cast<std::int16_t>(
            std::lround(kTrainAmp * u[k].real()));
        out[k * 2 + 1] = static_cast<std::int16_t>(
            std::lround(kTrainAmp * u[k].imag()));
    }
    return out;
}

// Known references as complex<double> at the SAME amplitude as the TX (kTrainAmp),
// so the LS complex gain a_est == the true per-file RF gain (not scaled by 2048).
inline std::vector<std::complex<double>> preamble_complex() {
    const std::vector<std::complex<double>> u = zadoff_chu(kZadoffChuRoot);
    std::vector<std::complex<double>> out(kPreambleComplex);
    for (std::size_t k = 0; k < kPreambleComplex; ++k) out[k] = u[k] * kTrainAmp;
    return out;
}
inline std::vector<std::complex<double>> tail_complex() {
    const std::vector<std::complex<double>> u = zadoff_chu(kTailZadoffChuRoot);
    std::vector<std::complex<double>> out(kTailComplex);
    for (std::size_t k = 0; k < kTailComplex; ++k) out[k] = u[k] * kTrainAmp;
    return out;
}

// Payload-domain gain training block as interleaved int16 [I0,Q0,...] (the SINGLE
// SOURCE OF TRUTH: the complex reference below is DERIVED from this exact int16
// block, so the TX samples and the RX-side LS reference are bit-identical).  Fixed-
// seed LCG -> 32 x 16QAM/sqrt(10) symbols, rectangular pulse, RMS-normalized to
// kPayloadTrainingAmp, quantized to int16.  No label, no payload dependence.
inline std::vector<std::int16_t> payload_gain_training() {
    constexpr double inv_sqrt10 = 1.0 / std::sqrt(10.0);
    static constexpr int levels[4] = {-3, -1, 1, 3};
    std::uint32_t s = static_cast<std::uint32_t>(kPayloadTrainingSeed & 0xFFFFFFFFu);
    auto draw = [&s]() -> int {
        s = s * 1664525u + 1013904223u;
        return levels[(s >> 30) & 3u];
    };
    const std::size_t n_sym = kPayloadTrainingComplex / kPayloadTrainingSamplesPerSymbol;
    std::vector<std::complex<double>> sym(n_sym);
    for (std::size_t m = 0; m < n_sym; ++m)
        sym[m] = std::complex<double>(static_cast<double>(draw()) * inv_sqrt10,
                                      static_cast<double>(draw()) * inv_sqrt10);
    double energy = 0.0;
    for (const auto& z : sym) energy += z.real() * z.real() + z.imag() * z.imag();
    const double rms = std::sqrt(energy / static_cast<double>(n_sym));
    const double scale = (rms > 0.0) ? (kPayloadTrainingAmp / rms) : 1.0;
    std::vector<std::int16_t> out(kPayloadTrainingComplex * 2);
    for (std::size_t m = 0; m < n_sym; ++m) {
        const std::complex<double> z = sym[m] * scale;
        const double I = std::lround(std::max(-32768.0, std::min(32767.0, z.real())));
        const double Q = std::lround(std::max(-32768.0, std::min(32767.0, z.imag())));
        for (std::size_t j = 0; j < kPayloadTrainingSamplesPerSymbol; ++j) {
            const std::size_t k = m * kPayloadTrainingSamplesPerSymbol + j;
            out[k * 2 + 0] = static_cast<std::int16_t>(I);
            out[k * 2 + 1] = static_cast<std::int16_t>(Q);
        }
    }
    return out;
}

// Complex reference DERIVED from the int16 block (no independent float path): the
// RX-side LS gain compares against the EXACT quantized TX samples.
inline std::vector<std::complex<double>> payload_gain_training_complex() {
    const std::vector<std::int16_t> iq = payload_gain_training();
    std::vector<std::complex<double>> out(kPayloadTrainingComplex);
    for (std::size_t k = 0; k < kPayloadTrainingComplex; ++k)
        out[k] = std::complex<double>(static_cast<double>(iq[k * 2 + 0]),
                                      static_cast<double>(iq[k * 2 + 1]));
    return out;
}

// ---------------------------------------------------------------------------
// Full burst build (TX side + RX-side known-answer reference).
// ---------------------------------------------------------------------------
inline std::vector<std::int16_t> build_burst(
        const std::vector<std::int16_t>& payload_iq) {
    if (payload_iq.size() != kPayloadComplex * 2)
        throw std::runtime_error("iqrftrain: payload must be exactly " +
                                 std::to_string(kPayloadComplex) +
                                 " complex samples");
    std::vector<std::int16_t> b;
    b.reserve(kTotalBurstComplex * 2);
    const std::vector<std::int16_t> pre = preamble();
    b.insert(b.end(), pre.begin(), pre.end());
    // settling-zero zone (kPayloadTrainingOffset - kPreambleComplex == 1024 complex
    // -> 2048 int16 zeros): isolates the ZC broadband transient from the training block.
    b.insert(b.end(), (kPayloadTrainingOffset - kPreambleComplex) * 2, std::int16_t{0});
    const std::vector<std::int16_t> pt = payload_gain_training();
    b.insert(b.end(), pt.begin(), pt.end());
    b.insert(b.end(), payload_iq.begin(), payload_iq.end());
    b.insert(b.end(), kGuardComplex * 2, 0);
    const std::vector<std::int16_t> t = tail();
    b.insert(b.end(), t.begin(), t.end());
    if (b.size() != kTotalBurstComplex * 2)
        throw std::runtime_error("iqrftrain: built burst length mismatch");
    return b;
}

// De-interleave interleaved int16 into complex<double>.
inline std::vector<std::complex<double>> deinterleave(
        const std::vector<std::int16_t>& iq) {
    if (iq.size() % 2 != 0)
        throw std::runtime_error("iqrftrain: odd int16 length");
    std::vector<std::complex<double>> out(iq.size() / 2);
    for (std::size_t k = 0; k < out.size(); ++k)
        out[k] = std::complex<double>(static_cast<double>(iq[k * 2]),
                                      static_cast<double>(iq[k * 2 + 1]));
    return out;
}

}  // namespace iqrftrain
