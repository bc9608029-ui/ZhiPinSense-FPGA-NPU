// test_iq_rf_loopback_24class_bf16_scalarwl_diag.cpp -- host tests for
// fix10class24-scalarwl-4way (task 39e5): the iCraft-free CORE of the minimal
// single-SDR scalar/WL diagnostic.
//
// iCraft-free / libiio-free / NPU-free.  Exercises the exact production headers the
// board runs (iq_rf_loopback_24class_bf16_scalarwl_core.hpp -> iqrfrec /
// iqdual23fix10::recover_payload_with_coarse_cfo), never the board runner:
//
//   1. the new --phase=iq-rf-loopback-24class-bf16-scalarwl dispatch is valid (and the
//      near-misses + old phases behave as before);
//   2. iqdiagswl::reconstruct_aligned() reproduces the recovery core's LOCAL `aligned`
//      capture byte-for-byte -- proven by re-applying iqrfrec::apply(aligned, rec) and
//      matching the production ccr.payload EXACTLY (this is the foundation of the whole
//      four-way comparison: if `aligned` diverged, the scalar/WL inputs would diverge);
//   3. iqdiagswl::recompute_wide_linear_coeffs() byte-replicates estimate()'s step 6.6,
//      returning the SAME (a, b) the production recovery recorded on a distorted
//      capture (so the WL model input the diagnostic builds when estimate() DISABLED
//      wide-linear is the exact production compensation, never a NumPy re-fit), and
//      returns the zero pair (fail-closed) when the training block would over-read.
//
// Red line: the 0.10 residual gate is unchanged.

#include "../board_package/iq_rf_loopback_24class_bf16_scalarwl_core.hpp"
#include "../board_package/gate9_phase.hpp"

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// Deterministic payload (single tone) -> clean int16 burst (same fixture as
// test_dual_sdr_wide_linear.cpp).
std::vector<std::int16_t> make_payload() {
    std::vector<std::int16_t> p(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 41) / 41.0;
        p[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1150.0 * std::cos(ph)));
        p[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1150.0 * std::sin(ph)));
    }
    return p;
}

// Wide-linear mixer model y = A*x + B*conj(x).
std::vector<std::complex<double>> distort(const std::vector<std::complex<double>>& x,
                                          std::complex<double> A, std::complex<double> B) {
    std::vector<std::complex<double>> y(x.size());
    for (std::size_t k = 0; k < x.size(); ++k)
        y[k] = A * x[k] + B * std::conj(x[k]);
    return y;
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

// ---- 1. phase surface --------------------------------------------------------

void test_phase_surface() {
    check(gate9::valid_phase("iq-rf-loopback-24class-bf16-scalarwl"),
          "phase: valid_phase accepts iq-rf-loopback-24class-bf16-scalarwl");
    check(!gate9::valid_phase("iq-rf-loopback-24class-bf16-scalarwlx"),
          "phase: valid_phase rejects trailing-x near-miss");
    check(!gate9::valid_phase("iq-rf-loopback-24class-bf16-scalarw"),
          "phase: valid_phase rejects truncated near-miss");
    check(!gate9::valid_phase(""),
          "phase: valid_phase rejects empty");
    check(gate9::valid_phase("iq-rf-loopback-24class-bf16-fix10"),
          "phase: valid_phase still accepts the sibling single-SDR A/B phase");
    check(gate9::valid_phase("iq-pc-tx-board-rx-24class-bf16-fix10"),
          "phase: valid_phase still accepts the dual-SDR 24-class phase");
    check(gate9::valid_phase("iq-rf-loopback-23class-fix9r"),
          "phase: valid_phase still accepts the historical 23-class single-SDR phase");
}

// ---- 2. reconstruct_aligned == the recovery core's LOCAL aligned (byte-exact) --

void test_reconstruct_aligned_byte_exact() {
    const std::vector<std::int16_t> p = make_payload();
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(p);
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(burst);
    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, make_cfg(), 1.0);
    check(ccr.rec.valid, "clean capture recovery valid (precondition)");
    check(!ccr.rec.wide_linear_enabled, "clean capture: wide-linear REJECTED (precondition)");

    // The diagnostic reconstructs the LOCAL `aligned` and re-applies with the SAME rec;
    // on a clean capture (scalar path) this must reproduce ccr.payload byte-for-byte,
    // which proves reconstruct_aligned() is byte-identical to the core's internal vector.
    const std::vector<std::complex<double>> aligned =
        iqdiagswl::reconstruct_aligned(rx, ccr);
    const std::vector<std::complex<double>> scalar_payload =
        iqrfrec::apply(aligned, ccr.rec);
    const bool byte_equal = std::equal(ccr.payload.begin(), ccr.payload.end(),
        scalar_payload.begin(),
        [](const std::complex<double>& a, const std::complex<double>& b) {
            return a.real() == b.real() && a.imag() == b.imag();
        });
    check(byte_equal,
          "reconstruct_aligned: re-applied scalar payload == production ccr.payload "
          "(byte-exact aligned)");
}

// ---- 3a. recompute_wide_linear_coeffs == estimate()'s recorded (a, b) ----------

void test_recompute_wide_linear_coeffs_matches_estimate() {
    const std::vector<std::int16_t> p = make_payload();
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(p);
    const std::vector<std::complex<double>> rx_clean = iqrftrain::deinterleave(burst);
    const std::complex<double> A(1.0, 0.0), B(0.06, -0.04);   // image ratio ~0.072
    const std::vector<std::complex<double>> distorted = distort(rx_clean, A, B);

    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(distorted, make_cfg(), 1.0);
    check(ccr.rec.valid, "distorted capture still passes the 0.10 gate (mild image)");
    check(ccr.rec.wide_linear_enabled,
          "distorted capture: wide-linear ENABLED (precondition for the comparison)");

    const std::vector<std::complex<double>> aligned =
        iqdiagswl::reconstruct_aligned(distorted, ccr);
    const iqrfrec::detail::WideLinearCoeffs wc =
        iqdiagswl::recompute_wide_linear_coeffs(aligned, ccr.rec);

    // estimate() recorded (a, b) from the SAME aligned vector via the SAME step-6.6
    // math, so recompute_wide_linear_coeffs must return them to machine precision.
    check(std::abs(wc.a - ccr.rec.wide_linear_direct) < 1e-12,
          "recompute_wide_linear_coeffs: a == estimate()'s wide_linear_direct");
    check(std::abs(wc.b - ccr.rec.wide_linear_image) < 1e-12,
          "recompute_wide_linear_coeffs: b == estimate()'s wide_linear_image");
    check(wc.a != std::complex<double>(0.0, 0.0) && wc.b != std::complex<double>(0.0, 0.0),
          "recompute_wide_linear_coeffs: (a, b) are non-zero (real image present)");
}

// ---- 3b. recompute_wide_linear_coeffs fails closed on over-read -----------------

void test_recompute_wide_linear_coeffs_fail_closed() {
    // A capture too short to hold the payload-training block returns the zero pair.
    const std::vector<std::complex<double>> tiny(8, std::complex<double>(1.0, 0.0));
    iqrfrec::PerFileRecovery rec;
    rec.timing_offset = 0;
    rec.sro_ppm = 0.0;
    rec.cfo_hz = 0.0;
    const iqrfrec::detail::WideLinearCoeffs wc =
        iqdiagswl::recompute_wide_linear_coeffs(tiny, rec);
    check(wc.a == std::complex<double>(0.0, 0.0) && wc.b == std::complex<double>(0.0, 0.0),
          "recompute_wide_linear_coeffs: zero pair on over-read (fail-closed)");
}

// ---- 4. red line: the 0.10 residual gate is unchanged --------------------------

void test_residual_gate_unchanged() {
    check(iqrfrec::kPayloadTrainingResidualMax == 0.10,
          "0.10 payload-training residual gate is unchanged (red line)");
}

// ---- 5. baseline identity uses source hash, never quantized CI16 hash ------------

void test_baseline_identity_uses_original_hash() {
    rml24bf16::BaselineRow baseline;
    baseline.original_sha256 = std::string(64, 'a');
    baseline.raw24_class = 23;
    baseline.modulation = "OQPSK";
    baseline.split_role = "holdout";

    iqdloop::FrozenIq frozen;
    frozen.original_sha256 = std::string(64, 'a');
    frozen.sha256 = std::string(64, 'b');  // CI16 artifact hash is intentionally distinct
    frozen.source_class = 23;
    frozen.modulation = "OQPSK";
    frozen.split_role = "holdout";

    check(iqdiagswl::baseline_identity_matches(baseline, frozen),
          "baseline identity matches source original_sha256 when CI16 hash differs");
    frozen.original_sha256 = std::string(64, 'c');
    check(!iqdiagswl::baseline_identity_matches(baseline, frozen),
          "baseline identity rejects a different source original_sha256");
}

// ---- 6. source-index selection is class-agnostic and fail-closed ---------------

void test_source_index_selection_is_not_oqpsk_only() {
    std::vector<iqdloop::FrozenIq> frozen(2);
    frozen[0].source_index = 0;
    frozen[0].source_class = 0;
    frozen[0].modulation = "OOK";
    frozen[1].source_index = 11500;
    frozen[1].source_class = 23;
    frozen[1].modulation = "OQPSK";

    const auto* ook = iqdiagswl::find_frozen_by_source_index(frozen, 0);
    check(ook != nullptr && ook->modulation == "OOK" && ook->source_class == 0,
          "source-index selection accepts non-OQPSK class 0");
    check(iqdiagswl::find_frozen_by_source_index(frozen, 500) == nullptr,
          "source-index selection reports a missing manifest key");

    frozen.push_back(frozen[0]);
    bool duplicate_rejected = false;
    try {
        (void)iqdiagswl::find_frozen_by_source_index(frozen, 0);
    } catch (const std::runtime_error&) {
        duplicate_rejected = true;
    }
    check(duplicate_rejected,
          "source-index selection rejects duplicate manifest identities");
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
    std::printf("test_iq_rf_loopback_24class_bf16_scalarwl_diag\n");
    run_test("phase_surface", test_phase_surface);
    run_test("reconstruct_aligned_byte_exact", test_reconstruct_aligned_byte_exact);
    run_test("recompute_wide_linear_coeffs_matches_estimate",
             test_recompute_wide_linear_coeffs_matches_estimate);
    run_test("recompute_wide_linear_coeffs_fail_closed",
             test_recompute_wide_linear_coeffs_fail_closed);
    run_test("residual_gate_unchanged", test_residual_gate_unchanged);
    run_test("baseline_identity_uses_original_hash",
             test_baseline_identity_uses_original_hash);
    run_test("source_index_selection_is_not_oqpsk_only",
             test_source_index_selection_is_not_oqpsk_only);

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
