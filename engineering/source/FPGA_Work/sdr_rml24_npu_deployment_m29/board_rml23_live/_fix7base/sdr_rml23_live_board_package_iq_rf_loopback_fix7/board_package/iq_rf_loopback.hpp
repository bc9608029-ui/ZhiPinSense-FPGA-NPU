#pragma once

// iq_rf_loopback.hpp -- Stage H-F / Route F: ADALM-Pluto PHYSICAL TX->RX self
// loopback (external RF), *pure logic* half (host-testable).
//
// Route F is the physical-RF sibling of Route E's digital loopback.  Instead of
// the AD9361 internal digital loopback (loopback=1), it emits on the TX SMA port
// and receives on the RX SMA port through a 50-ohm coax (loopback=0,
// --rf-path=direct-cable), so the full TX DAC -> attenuator -> RF out -> coax ->
// RF in -> RX gain -> RX ADC chain is exercised.  The RF amplitude/phase is
// unknown a priori, so this half provides:
//
//   * the TX-off NEGATIVE CONTROL: measure the RX noise floor BEFORE any TX, so a
//     later signal can be told apart from noise (SNR) and so a railed RX is
//     detected (noise_clipped).  This is a per-file measurement, never a PASS gate.
//   * the RF fidelity measure: reuse iqdloop_sync::measure_fidelity_fix5 (full-
//     period FFT circular sync, scale-independent residual/EVM/corr/CFO -- NEVER a
//     bounded delay search) on the TX->RX capture, plus the noise-floor SNR.
//   * the RF verdict mapping (observation-only): RF_PATH_NOT_PROVEN / RF_RX_ALL_ZERO
//     / RF_RX_TOO_LOW / RF_RX_CLIPPED / RF_SYNC_NOT_FOUND / RF_DISTORTS_IQ /
//     RF_PRESERVES_IQ.  RF_PRESERVES_IQ requires sync + corr + residual/EVM + no
//     clipping + SNR; the loopback-readback / TX-DMA / negative-control / restore
//     gates are folded in by the runner.
//   * ONE global fixed complex gain (k_mag, k_phase_deg) estimated from an
//     INDEPENDENT calibration subset -- the ONLY amplitude/phase correction the
//     classification path is ever allowed to use.  A per-file best-fit gain is
//     measurement-only and is NEVER fed to the classifier (no oracle).
//
// iCraft-free and libiio-free: it never opens a device and never runs the NPU.

#include "chain_common.hpp"
#include "iq_digital_loopback_sync.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace iqrfloop {

// Observation thresholds (measurement-only; never a PASS gate).  RF-specific:
// unlike the digital loopback, the RF path carries an unknown physical gain, so
// "too low" is judged by SNR against the noise floor (not an absolute count),
// and the count-domain normalized-gain check (normalized_gain_ok) does NOT apply
// (the physical gain legitimately moves gain_normalized_db far from 0 dB).
constexpr double kRfSnrThresholdDb = 6.0;          // below this -> signal ~= noise
constexpr double kRfMaxNormalizedResidual = 0.05;  // <= -13 dB -> preserved
constexpr double kRfSyncCorrThreshold = iqdloop_sync::kSyncCorrThreshold;  // 0.9

constexpr const char* kRfPathNotProven = "RF_PATH_NOT_PROVEN";
constexpr const char* kRfRxAllZero = "RF_RX_ALL_ZERO";
constexpr const char* kRfRxTooLow = "RF_RX_TOO_LOW";
constexpr const char* kRfRxClipped = "RF_RX_CLIPPED";
constexpr const char* kRfSyncNotFound = "RF_SYNC_NOT_FOUND";
constexpr const char* kRfDistortsIq = "RF_DISTORTS_IQ";
constexpr const char* kRfPreservesIq = "RF_PRESERVES_IQ";

// RF fidelity metric bundle: the fix5 sync/fidelity metrics PLUS the TX-off
// negative-control (noise-floor) evidence and the derived SNR.
struct RfFidelityMetrics {
    iqdloop_sync::SyncFidelityMetrics sync;

    // TX-off negative control (noise floor captured BEFORE TX-on).
    bool noise_capture_ok = false;
    std::uint64_t noise_complex = 0;
    bool noise_all_zero = false;
    double noise_floor_rms = 0.0;
    int noise_peak = 0;
    double noise_dc = 0.0;
    bool noise_clipped = false;

    // derived: signal / noise floor, in the SAME logical count domain.
    double snr_db = 0.0;   // +inf when the noise floor is exactly zero
    bool negative_control_ok = false;
};

// Measure the TX-off noise floor (RMS / peak / DC / all-zero / clipped) from the
// negative-control capture.  `noise_capture_ok` is the continuity verdict from the
// transfer (whether the capture was one contiguous refill).
inline RfFidelityMetrics measure_rf_fidelity(
        const std::vector<std::int16_t>& tx, const std::vector<std::int16_t>& rx,
        const std::vector<std::int16_t>& noise, bool noise_capture_ok,
        std::uint64_t fs, int tx_bits, int rx_bits, std::size_t transient_discard) {
    RfFidelityMetrics m;
    m.sync = iqdloop_sync::measure_fidelity_fix5(tx, rx, fs, tx_bits, rx_bits,
                                                 transient_discard);
    m.noise_capture_ok = noise_capture_ok;
    m.noise_complex = noise.size() / 2;

    std::uint64_t nz = 0;
    double e = 0.0;
    int peak = 0;
    double sum_i = 0.0, sum_q = 0.0;
    for (std::size_t k = 0; k + 1 < noise.size(); k += 2) {
        const int i = noise[k];
        const int q = noise[k + 1];
        if (i != 0 || q != 0) ++nz;
        e += static_cast<double>(i) * i + static_cast<double>(q) * q;
        peak = std::max(peak, std::max(std::abs(i), std::abs(q)));
        sum_i += i;
        sum_q += q;
    }
    const std::size_t nc = noise.size() / 2;
    m.noise_all_zero = (nz == 0);
    m.noise_floor_rms = nc > 0 ? std::sqrt(e / static_cast<double>(nc)) : 0.0;
    m.noise_peak = peak;
    m.noise_dc = nc > 0
        ? std::hypot(sum_i, sum_q) / static_cast<double>(nc) : 0.0;
    m.noise_clipped = (peak >= 2047);

    // The negative control "passes" when the TX-off capture was a single contiguous
    // refill AND the RX was not railed with no TX present (a railed noise floor is
    // a hardware fault, not noise).
    m.negative_control_ok = noise_capture_ok && !m.noise_clipped;
    m.snr_db = (m.noise_floor_rms > 0.0)
        ? 20.0 * std::log10(m.sync.rms_rx / m.noise_floor_rms)
        : std::numeric_limits<double>::infinity();
    return m;
}

// RF fidelity verdict (observation-only; the loopback-readback / TX-DMA /
// negative-control / restore gates are folded in by the runner, NOT here).
inline const char* rf_fidelity_verdict(const RfFidelityMetrics& m) {
    if (m.sync.rx_complex < iqdloop_sync::kMinCaptureComplex)
        return "INSUFFICIENT_EVIDENCE";
    if (m.sync.capture_too_short)
        return "RF_CAPTURE_TOO_SHORT";
    if (m.sync.rx_all_zero)
        return kRfRxAllZero;
    if (std::isfinite(m.snr_db) && m.snr_db < kRfSnrThresholdDb)
        return kRfRxTooLow;                      // signal indistinguishable from noise
    if (m.sync.clipped)
        return kRfRxClipped;
    if (m.sync.sync.origin == iqdloop_sync::SyncOrigin::Ambiguous)
        return kRfSyncNotFound;
    if (m.sync.corr < kRfSyncCorrThreshold)
        return kRfDistortsIq;
    if (m.sync.corr >= kRfSyncCorrThreshold &&
        m.sync.normalized_residual <= kRfMaxNormalizedResidual &&
        !m.sync.clipped && m.sync.nmse_evm_consistent)
        return kRfPreservesIq;
    return kRfPathNotProven;
}

// Only RF_PRESERVES_IQ counts as a fidelity PASS.
inline bool rf_fidelity_gate_ok(const char* verdict) {
    return std::string(verdict) == kRfPreservesIq;
}

// ONE global fixed complex gain (the inverse of the RF gain), estimated from an
// independent calibration subset.  k_mag * exp(j k_phase_deg) is the scalar the
// classification path multiplies every recovered tensor by; it is NEVER per-file.
struct RfGlobalGain {
    bool valid = false;
    std::size_t count = 0;   // calibration gains that contributed
    double mag = 1.0;         // |a_global|  (median of the per-file optimal gains)
    double phase_deg = 0.0;   // arg(a_global) (circular mean)
    double k_mag = 1.0;       // 1 / |a_global|
    double k_phase_deg = 0.0; // -arg(a_global)
};

// Estimate the global gain from a set of per-file optimal complex gains
// (a_i = gain_count * exp(j phase_deg), each the LS fit aligned_rx ~= a_i * tx).
// The magnitude is the MEDIAN |a_i| and the phase is the CIRCULAR mean of arg(a_i)
// -- robust to one bad calibration file, and independent of any file's label.
// K = 1 / a_global undoes the RF path for EVERY classification input.
inline RfGlobalGain estimate_global_gain(
        const std::vector<std::complex<double>>& gains) {
    RfGlobalGain g;
    g.count = gains.size();
    std::vector<double> mags, phases;
    for (const auto& a : gains) {
        const double mg = std::abs(a);
        if (mg < 1e-30) continue;
        mags.push_back(mg);
        phases.push_back(std::arg(a));
    }
    if (mags.empty()) return g;
    std::sort(mags.begin(), mags.end());
    const double med = mags[mags.size() / 2];
    double sx = 0.0, sy = 0.0;
    for (double p : phases) { sx += std::cos(p); sy += std::sin(p); }
    const double mp = std::atan2(sy, sx);
    g.valid = true;
    g.mag = med;
    g.phase_deg = mp * 180.0 / iqdloop_sync::kPi;
    g.k_mag = 1.0 / med;
    g.k_phase_deg = -mp * 180.0 / iqdloop_sync::kPi;
    return g;
}

// Apply the complex gain k = k_mag * exp(j k_phase_deg) to a [2, frame_complex]
// fp32 tensor (I plane then Q plane).  Used by the classification path to undo the
// RF gain with the ONE global calibration gain -- never a per-file fit.
inline void apply_complex_gain_to_tensor(float* tensor, std::size_t frame_complex,
                                         double k_mag, double k_phase_deg) {
    const double ph = k_phase_deg * iqdloop_sync::kPi / 180.0;
    const double kr = k_mag * std::cos(ph);
    const double ki = k_mag * std::sin(ph);
    for (std::size_t j = 0; j < frame_complex; ++j) {
        const double I = static_cast<double>(tensor[j]);
        const double Q = static_cast<double>(tensor[frame_complex + j]);
        tensor[j] = static_cast<float>(I * kr - Q * ki);
        tensor[frame_complex + j] = static_cast<float>(I * ki + Q * kr);
    }
}

// Apply the global gain to a concatenated recovered stream of [2, frame_complex]
// fp32 tensors (in place).
inline void apply_global_gain_to_stream(std::vector<float>& stream,
                                        std::size_t frame_complex,
                                        const RfGlobalGain& g) {
    if (!g.valid) return;
    std::size_t off = 0;
    while (off + 2 * frame_complex <= stream.size()) {
        apply_complex_gain_to_tensor(stream.data() + off, frame_complex,
                                     g.k_mag, g.k_phase_deg);
        off += 2 * frame_complex;
    }
}

}  // namespace iqrfloop
