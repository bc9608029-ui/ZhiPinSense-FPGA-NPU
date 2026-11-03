// test_dual_sdr_wide_linear.cpp -- host tests for fix10class24-dualsdr-rxrecovery1:
// the gated wide-linear IQ compensation in iqrfrec (iq_rf_sync_recovery.hpp) and the
// bounded payload-training recapture primitive it shares with the fix9r2h3 runner.
//
// iCraft-free / libiio-free / NPU-free.  Exercises the exact production header the board
// runs (iq_dual_sdr_coarse_cfo_recovery.hpp -> iqrfrec::estimate/apply), never the
// board runner.  Red-line checks: the 0.10 residual gate, the scalar recovery path, and
// every existing validity gate are untouched -- proven by the clean-capture assertions
// (wide-linear disabled, scalar path byte-identical output scale) and by the untouched
// should_retry_payload_training_capture primitive.

#include "../board_package/iq_dual_sdr_coarse_cfo_recovery.hpp"

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

double nresid(const std::vector<std::complex<double>>& a,
              const std::vector<std::complex<double>>& b) {
    double num = 0.0, den = 0.0;
    for (std::size_t k = 0; k < a.size(); ++k) {
        num += std::norm(a[k] - b[k]);
        den += std::norm(b[k]);
    }
    return den > 0.0 ? std::sqrt(num / den) : 0.0;
}

// Deterministic payload (single tone) -> clean int16 burst.
std::vector<std::int16_t> make_payload() {
    std::vector<std::int16_t> p(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 41) / 41.0;
        p[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1150.0 * std::cos(ph)));
        p[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1150.0 * std::sin(ph)));
    }
    return p;
}

// Apply a wide-linear mixer model y = A*x + B*conj(x) to the whole capture.
std::vector<std::complex<double>> distort(const std::vector<std::complex<double>>& x,
                                          std::complex<double> A, std::complex<double> B) {
    std::vector<std::complex<double>> y(x.size());
    for (std::size_t k = 0; k < x.size(); ++k)
        y[k] = A * x[k] + B * std::conj(x[k]);
    return y;
}

// Rebuild the coarse-de-rotated + fractional-advanced capture (mirrors the production
// recover_payload_with_coarse_cfo, so we can call iqrfrec::apply again with a modified
// rec for the scalar-vs-wide-linear comparison).
std::vector<std::complex<double>> rebuild_aligned(const std::vector<std::complex<double>>& rx,
                                                  double coarse_cfo_hz, double frac) {
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * coarse_cfo_hz *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }
    return iqdual23fix10::detail::apply_fractional_advance(derot, frac);
}

iqrfrec::EstimateConfig make_cfg() {
    iqrfrec::EstimateConfig cfg;
    cfg.min_corr = 0.9;
    cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;   // 0.10 (red line, unchanged)
    cfg.max_cfo_hz = 1000.0;
    cfg.max_sro_ppm = 1000.0;
    cfg.search_limit = 0;
    cfg.payload_tx_target_rms = 2048.0;
    return cfg;
}

// ---- (a) wide_linear_fit recovers a known (a, b) exactly -------------------------
void test_wide_linear_fit_exact() {
    const std::size_t N = 64;
    const std::complex<double> a(1.3, 0.4), b(0.2, -0.1);
    std::vector<std::complex<double>> basis(N), observed(N);
    for (std::size_t k = 0; k < N; ++k) {
        basis[k] = std::complex<double>(std::cos(0.7 * k) + 0.5, std::sin(0.3 * k) + 0.2);
        observed[k] = a * basis[k] + b * std::conj(basis[k]);
    }
    const iqrfrec::detail::WideLinearCoeffs wl =
        iqrfrec::detail::wide_linear_fit(basis, observed, 0, N);
    check(std::abs(wl.a - a) < 1e-12, "wide_linear_fit recovers a exactly");
    check(std::abs(wl.b - b) < 1e-12, "wide_linear_fit recovers b (image) exactly");

    // A singular basis (zero norm) returns the zero pair -> fail-closed.
    std::vector<std::complex<double>> z(4, std::complex<double>(0.0, 0.0));
    const iqrfrec::detail::WideLinearCoeffs wlz =
        iqrfrec::detail::wide_linear_fit(z, z, 0, 4);
    check(wlz.a == std::complex<double>(0.0, 0.0) && wlz.b == std::complex<double>(0.0, 0.0),
          "wide_linear_fit returns zero pair on singular basis (fail-closed)");
}

// ---- (b) clean capture -> wide-linear rejected (fail-closed), scalar path kept -----
void test_clean_capture_rejects_wide_linear() {
    const std::vector<std::int16_t> p = make_payload();
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(p);
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(burst);
    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, make_cfg(), 1.0);
    check(ccr.rec.valid, "clean capture recovery valid (precondition)");
    check(!ccr.rec.wide_linear_enabled,
          "clean capture: wide-linear compensation REJECTED (no image to undo)");
    check(ccr.rec.wide_linear_image_ratio < 1e-3,
          "clean capture: image ratio negligible");
    // The recovered payload comes from the SCALAR path (wide-linear disabled): re-applying
    // with the same rec on a rebuilt aligned capture reproduces it byte-identically.
    const std::vector<std::complex<double>> aligned =
        rebuild_aligned(rx, ccr.coarse_cfo_hz, ccr.fractional_timing_samples);
    const std::vector<std::complex<double>> scalar_payload = iqrfrec::apply(aligned, ccr.rec);
    const bool byte_equal = std::equal(ccr.payload.begin(), ccr.payload.end(),
        scalar_payload.begin(),
        [](const std::complex<double>& a, const std::complex<double>& b) {
            return a.real() == b.real() && a.imag() == b.imag();
        });
    check(byte_equal, "clean capture: recovered payload is the scalar path (byte-identical)");
}

// ---- (c) distorted capture -> wide-linear accepted, improves the recovery ----------
void test_distorted_capture_enables_wide_linear() {
    const std::vector<std::int16_t> p = make_payload();
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(p);
    const std::vector<std::complex<double>> rx_clean = iqrftrain::deinterleave(burst);
    const std::complex<double> A(1.0, 0.0), B(0.06, -0.04);   // image ratio ~0.072
    const std::vector<std::complex<double>> distorted = distort(rx_clean, A, B);

    // Ground-truth recovered payload: the CLEAN capture through the same recovery path.
    // This is scale-correct (both distorted and clean recover to payload_tx_target_rms),
    // so it removes the arbitrary int16/RF scale instead of comparing to deinterleave(p).
    const iqdual23fix10::CoarseCfoRecovery ccr_clean =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx_clean, make_cfg(), 1.0);
    check(ccr_clean.rec.valid, "clean capture recovery valid (reference)");

    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(distorted, make_cfg(), 1.0);
    check(ccr.rec.valid, "distorted capture still passes the 0.10 gate (mild image)");
    check(ccr.rec.wide_linear_enabled,
          "distorted capture: wide-linear compensation ENABLED (validation improved)");
    const double image_ratio = std::abs(B) / std::abs(A);
    check(std::fabs(ccr.rec.wide_linear_image_ratio - image_ratio) < 0.02,
          "distorted capture: measured image ratio ~= |B|/|A|");

    // Wide-linear recovery beats the scalar recovery on the SAME aligned capture.
    const std::vector<std::complex<double>> aligned =
        rebuild_aligned(distorted, ccr.coarse_cfo_hz, ccr.fractional_timing_samples);
    iqrfrec::PerFileRecovery rec_scalar = ccr.rec;
    rec_scalar.wide_linear_enabled = false;
    const std::vector<std::complex<double>> scalar_payload =
        iqrfrec::apply(aligned, rec_scalar);

    const double wide_resid = nresid(ccr.payload, ccr_clean.payload);
    const double scalar_resid = nresid(scalar_payload, ccr_clean.payload);
    check(wide_resid < scalar_resid * 0.5,
          "wide-linear recovery residual < 50% of the scalar recovery residual");
    check(ccr.rec.wide_linear_validation_residual <
              ccr.rec.wide_linear_scalar_validation_residual,
          "second-half validation residual improved (recorded)");
}

// ---- (d) bounded recapture primitive: only residual-too-high, capped at 3 ----------
void test_should_retry_payload_training_capture() {
    check(iqrfrec::kPayloadTrainingCaptureMaxAttempts == 3,
          "kPayloadTrainingCaptureMaxAttempts == 3");
    // Only PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH is retryable.
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::TRAINING_RESIDUAL_TOO_HIGH, 1),
          "TRAINING_RESIDUAL_TOO_HIGH is NOT retryable");
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::TRAINING_CORRELATION_TOO_LOW, 1),
          "TRAINING_CORRELATION_TOO_LOW is NOT retryable");
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::PAYLOAD_TRAINING_CORRELATION_TOO_LOW, 1),
          "PAYLOAD_TRAINING_CORRELATION_TOO_LOW is NOT retryable");
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::CFO_OUT_OF_RANGE, 1),
          "CFO_OUT_OF_RANGE is NOT retryable");
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::SRO_OUT_OF_RANGE, 1),
          "SRO_OUT_OF_RANGE is NOT retryable");
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::NONE, 1),
          "NONE is NOT retryable");
    // Attempt bound: retryable after attempts 1 and 2, NOT after 0 or 3.
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH, 0),
          "attempt 0 (initial capture) is NOT a retry");
    check(iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH, 1),
          "attempt 1 is retryable");
    check(iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH, 2),
          "attempt 2 is retryable");
    check(!iqrfrec::should_retry_payload_training_capture(
              iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH, 3),
          "attempt 3 (== max) is NOT retryable (cap reached)");
}

// ---- (e) red line: the 0.10 residual gate is unchanged ------------------------------
void test_residual_gate_unchanged() {
    check(iqrfrec::kPayloadTrainingResidualMax == 0.10,
          "0.10 payload-training residual gate is unchanged (red line)");
}

}  // namespace

void run_test(const char* name, void (*fn)()) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main() {
    std::printf("test_dual_sdr_wide_linear\n");
    run_test("wide_linear_fit_exact", test_wide_linear_fit_exact);
    run_test("clean_capture_rejects_wide_linear", test_clean_capture_rejects_wide_linear);
    run_test("distorted_capture_enables_wide_linear", test_distorted_capture_enables_wide_linear);
    run_test("should_retry_payload_training_capture", test_should_retry_payload_training_capture);
    run_test("residual_gate_unchanged", test_residual_gate_unchanged);

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
