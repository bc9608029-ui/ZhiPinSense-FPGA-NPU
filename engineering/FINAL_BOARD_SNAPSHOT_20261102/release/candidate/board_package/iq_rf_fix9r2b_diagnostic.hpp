#pragma once

// iq_rf_fix9r2b_diagnostic.hpp -- Route F fix9r2b Phase 1: DIAGNOSTIC-ONLY
// instrumentation, added on top of fix9r2a.  It does NOT change the recovery
// algorithm (no equalizer, no fractional-delay correction): it adds the waveform
// capture, the provisional scalar-recovery metrics, and the fixed summary/token
// semantics needed to quantify the root cause of RF_CHANNEL_DISTORTION_REMAINS
// (R8 board: training_corr ~ 0.974, training_residual ~ 0.23, estimate_valid=0/2).
//
// WHY PHASE 1 IS CAPTURE-ONLY (discipline): the scalar log proves the residual is a
// deterministic, amplitude-independent, LINEAR distortion (CFO/SRO/drift ~ 0, no
// clip, and corr=0.974 <-> residual 0.23 exactly, since (1-corr^2)/corr^2 ==
// residual^2 for a scalar-gain model).  But corr/residual alone cannot tell a
// fractional sampling delay from a frequency-selective amplitude/phase ripple from
// I/Q imbalance from a boundary transient -- that needs the raw aligned training
// waveform.  Phase 1 therefore captures the 5 waveforms + the fixed summary; Phase 2
// (equalizer / fractional-delay / guard) is chosen only after the offline analysis
// names the dominant cause.
//
// iCraft-free and libiio-free: every function is PURE (plain data in/out), so the
// host test exercises the exact code the board runner calls.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>

#include "iq_rf_sync_recovery.hpp"    // iqrfrec::Failure / PerFileRecovery (reuse only)
#include "../sdr_adapter/sha256.hpp"  // sdr::Sha256::hex

namespace iqrffix9r2b {

// ---- token vocabulary (the runner + host test share these exact strings) ------
constexpr const char* kRegressionPass = "ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS";
constexpr const char* kRegressionFail = "ROUTE_F_23CLASS_ACCURACY_REGRESSION_FAIL";
constexpr const char* kDiagnosticPass = "ROUTE_F_FIX9R2_DIAGNOSTIC_PASS";
constexpr const char* kDiagnosticFail = "ROUTE_F_FIX9R2_DIAGNOSTIC_FAIL";
constexpr const char* kNotEvaluated = "NOT_EVALUATED";

// ---------------------------------------------------------------------------
// §2 waveform capture (f32 interleaved little-endian)
// ---------------------------------------------------------------------------
constexpr const char* kF32Format = "f32_interleaved_le";

struct WaveformRecord {
    std::string path;
    std::string sha256;          // SHA-256 of the file bytes (empty == write failed)
    std::size_t complex_samples = 0;
    double rms = 0.0;
    std::string format;          // kF32Format
};

// Write complex<double> as interleaved float32 [I0,Q0,I1,Q1,...].  Returns the
// record (with SHA computed from the exact bytes); on write error the record's
// path and sha are empty (the caller fails closed).
inline WaveformRecord save_f32_interleaved(
        const std::string& path, const std::vector<std::complex<double>>& z) {
    WaveformRecord rec;
    rec.path = path;
    rec.format = kF32Format;
    rec.complex_samples = z.size();
    std::vector<float> f32(z.size() * 2);
    double energy = 0.0;
    for (std::size_t k = 0; k < z.size(); ++k) {
        f32[k * 2 + 0] = static_cast<float>(z[k].real());
        f32[k * 2 + 1] = static_cast<float>(z[k].imag());
        energy += z[k].real() * z[k].real() + z[k].imag() * z[k].imag();
    }
    rec.rms = z.empty() ? 0.0 : std::sqrt(energy / static_cast<double>(z.size()));
    std::FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) { rec.path.clear(); return rec; }
    std::fwrite(f32.data(), sizeof(float), f32.size(), f);
    const bool ok = !std::ferror(f);
    std::fclose(f);
    if (!ok) { rec.path.clear(); return rec; }
    rec.sha256 = sdr::Sha256::hex(f32.data(), f32.size() * sizeof(float));
    return rec;
}

// Load interleaved float32 back to complex<double>.  Returns false on any error.
inline bool load_f32_interleaved(const std::string& path,
                                 std::vector<std::complex<double>>& out) {
    std::FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    std::vector<float> f32;
    float v = 0.0f;
    while (std::fread(&v, sizeof(float), 1, f) == 1) f32.push_back(v);
    const bool ok = !std::ferror(f);
    std::fclose(f);
    if (!ok || (f32.size() % 2) != 0) return false;
    out.resize(f32.size() / 2);
    for (std::size_t k = 0; k < out.size(); ++k)
        out[k] = std::complex<double>(static_cast<double>(f32[k * 2]),
                                      static_cast<double>(f32[k * 2 + 1]));
    return true;
}

// Derive a per-file waveform stem from the ci16 file name (strip ".ci16").
inline std::string waveform_stem(const std::string& file_name) {
    std::string s = file_name;
    const std::string ext = ".ci16";
    if (s.size() >= ext.size() &&
        s.compare(s.size() - ext.size(), ext.size(), ext) == 0)
        s.erase(s.size() - ext.size());
    return s;
}

// ---------------------------------------------------------------------------
// §5 provisional scalar recovery + metrics (DIAGNOSTIC_ONLY)
// ---------------------------------------------------------------------------

// True when the preamble was located (timing_offset is meaningful), even if a later
// validity check (residual/corr/CFO/SRO) failed.
inline bool preamble_found(const iqrfrec::PerFileRecovery& rec) {
    return rec.computed &&
           rec.failure != iqrfrec::Failure::CAPTURE_TOO_SHORT &&
           rec.failure != iqrfrec::Failure::TRAINING_NOT_FOUND;
}

// Scalar-only recovery of the payload (the exact math of iqrfrec::apply: timing +
// FINAL gain magnitude selected by iqrfrec plus training-block phase + CFO + SRO). This
// mirrors iqrfrec::apply so the R8 diagnostic can compute the PROVISIONAL payload for
// gate-passing files.  Fail-closed: returns empty when rec.valid==false or the payload
// gain is unsafe -- NEVER a silent unit-gain fallback.  DIAGNOSTIC-ONLY: the runner
// never feeds this to the model (only iqrfrec::apply, gated on RF_PRESERVES_IQ, reaches
// the NPU).
inline std::vector<std::complex<double>> provisional_apply_scalar(
        const std::vector<std::complex<double>>& rx,
        const iqrfrec::PerFileRecovery& rec) {
    std::vector<std::complex<double>> out;
    if (!rec.valid) return out;
    const double mag = (rec.payload_rms_gain_mag > 1e-12 &&
                        std::isfinite(rec.payload_rms_gain_mag))
                           ? rec.payload_rms_gain_mag : rec.payload_gain_mag;
    const double mag2 = mag * mag;
    if (!std::isfinite(mag) || mag <= 1e-12 ||
        !std::isfinite(rec.payload_tx_scale) || rec.payload_tx_scale <= 0.0)
        return out;   // fail-closed
    out.resize(iqrftrain::kPayloadComplex);

    const std::complex<double> a_inv =
        std::complex<double>(mag / mag2, 0.0) *
        std::complex<double>(std::cos(-rec.payload_phase_deg * iqrftrain::kPi / 180.0),
                             std::sin(-rec.payload_phase_deg * iqrftrain::kPi / 180.0)) /
        rec.payload_tx_scale;
    const double sro = rec.sro_ppm * 1e-6;
    const double f = rec.cfo_hz;

    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        // rx[n] == s_tx[n / (1 + s)]: recover TX sample m by reading RX index
        // m*(1+s) -- MULTIPLY, not divide (same sign convention as iqrfrec::apply).
        const double src = static_cast<double>(rec.timing_offset +
                                               iqrftrain::kPayloadStart + k) *
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

struct ProvisionalMetrics {
    bool computed = false;       // both inputs non-empty and reference non-zero
    double corr = 0.0;           // magnitude-normalized cross-correlation [0,1]
    double nmse = 0.0;           // mean-squared error / mean-squared reference
};

inline ProvisionalMetrics provisional_payload_metrics(
        const std::vector<std::complex<double>>& recovered,
        const std::vector<std::complex<double>>& expected) {
    ProvisionalMetrics m;
    const std::size_t n = (recovered.size() < expected.size())
                              ? recovered.size() : expected.size();
    if (n == 0) return m;
    double num_r = 0.0, num_i = 0.0, den_rx = 0.0, den_ref = 0.0;
    for (std::size_t k = 0; k < n; ++k) {
        const std::complex<double>& x = recovered[k];
        const std::complex<double>& p = expected[k];
        num_r += x.real() * p.real() + x.imag() * p.imag();
        num_i += x.imag() * p.real() - x.real() * p.imag();
        den_rx += x.real() * x.real() + x.imag() * x.imag();
        den_ref += p.real() * p.real() + p.imag() * p.imag();
    }
    if (den_ref <= 0.0) return m;
    m.computed = true;
    m.corr = (den_rx > 0.0)
        ? std::sqrt(num_r * num_r + num_i * num_i) / std::sqrt(den_rx * den_ref)
        : 0.0;
    double mse = 0.0;
    for (std::size_t k = 0; k < n; ++k) {
        const std::complex<double> e = recovered[k] - expected[k];
        mse += e.real() * e.real() + e.imag() * e.imag();
    }
    m.nmse = mse / den_ref;
    return m;
}

// |rms(recovered)/rms(expected) - 1| over the ACTIVE payload region only.  Active is
// |expected[k]| >= 1.0 (D2 zero-padding is exactly 0; modulated payload has |sample| >= 1).
// DIAGNOSTIC-ONLY (fix9r2g R8 audit): it measures the recovered-payload scale error on
// KNOWN samples and never enters the deploy runtime, and never estimates parameters
// from the expected payload.  Returns +inf (fail-closed) on empty/uncomputable input.
inline double payload_scale_error(
        const std::vector<std::complex<double>>& recovered,
        const std::vector<std::complex<double>>& expected) {
    const std::size_t n = (recovered.size() < expected.size())
                              ? recovered.size() : expected.size();
    if (n == 0) return std::numeric_limits<double>::infinity();
    double re2 = 0.0, ex2 = 0.0;
    std::size_t active = 0;
    for (std::size_t k = 0; k < n; ++k) {
        if (std::abs(expected[k]) < 1.0) continue;   // skip zero-padding / inactive
        ++active;
        const double rr = std::abs(recovered[k]);
        const double ee = std::abs(expected[k]);
        re2 += rr * rr;
        ex2 += ee * ee;
    }
    if (active == 0 || ex2 <= 0.0) return std::numeric_limits<double>::infinity();
    const double rms_rec = std::sqrt(re2 / static_cast<double>(active));
    const double rms_exp = std::sqrt(ex2 / static_cast<double>(active));
    return std::fabs(rms_rec / rms_exp - 1.0);
}

// ---------------------------------------------------------------------------
// §6 fixed summary aggregation + token semantics
// ---------------------------------------------------------------------------

struct PerFileOutcome {
    bool computed = false;
    bool valid = false;
    iqrfrec::Failure failure = iqrfrec::Failure::NONE;
    double training_corr = 0.0;
    double training_residual = 0.0;
};

struct TrainingSummary {
    double corr_min = 0.0;
    double corr_avg = 0.0;
    double residual_max = 0.0;
    double residual_avg = 0.0;
    std::size_t measured_count = 0;   // preamble found (corr/residual meaningful)
    std::size_t valid_count = 0;      // rec.valid (every check passed)
};

// Aggregate corr/residual over files where the PREAMBLE WAS FOUND (measured), NOT
// only valid files.  This fixes the fix9r2a defect where a run failing only on
// residual reported corr_min=0 / residual_max=0 despite per-file corr ~ 0.974.
inline TrainingSummary aggregate_training_summary(
        const std::vector<PerFileOutcome>& files) {
    TrainingSummary s;
    double corr_sum = 0.0, res_sum = 0.0;
    for (const PerFileOutcome& f : files) {
        if (f.valid) ++s.valid_count;
        const bool measured = f.computed &&
            f.failure != iqrfrec::Failure::CAPTURE_TOO_SHORT &&
            f.failure != iqrfrec::Failure::TRAINING_NOT_FOUND;
        if (!measured) continue;
        ++s.measured_count;
        corr_sum += f.training_corr;
        res_sum += f.training_residual;
        if (s.measured_count == 1 || f.training_corr < s.corr_min)
            s.corr_min = f.training_corr;
        if (s.measured_count == 1 || f.training_residual > s.residual_max)
            s.residual_max = f.training_residual;
    }
    s.corr_avg = s.measured_count > 0 ? corr_sum / s.measured_count : 0.0;
    s.residual_avg = s.measured_count > 0 ? res_sum / s.measured_count : 0.0;
    return s;
}

struct GateTokens {
    std::string summary_token;      // the run's primary token
    std::string regression_token;   // what the regression line / detail reports
    std::string diagnostic_token;
};

// The token-semantics fix: in diagnostic mode the regression is NOT evaluated, so
// every place that reports a regression token (summary line, detail, GATE_RESULT)
// MUST report NOT_EVALUATED -- never ROUTE_F_23CLASS_ACCURACY_REGRESSION_FAIL.
inline GateTokens gate_tokens(bool diagnostic_mode, bool diagnostic_pass,
                              bool regression_pass) {
    GateTokens t;
    if (diagnostic_mode) {
        t.diagnostic_token = diagnostic_pass ? kDiagnosticPass : kDiagnosticFail;
        t.regression_token = kNotEvaluated;
        t.summary_token = t.diagnostic_token;
    } else {
        t.diagnostic_token = kNotEvaluated;
        t.regression_token = regression_pass ? kRegressionPass : kRegressionFail;
        t.summary_token = t.regression_token;
    }
    return t;
}

}  // namespace iqrffix9r2b
