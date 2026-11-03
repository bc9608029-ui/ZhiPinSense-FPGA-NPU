// test_fix10class24_failed_rx_force_classify.cpp -- host tests for the Phase B/C/E
// diagnostic core (host_tools/replay_fix10class24_failed_rx_force_classify.hpp).
//
// Covers, in-process and iCraft/libiio/NPU-free:
//   Phase B  apply_provisional fail-closed (unsafe gain / unsafe TX scale) and the
//            valid-gate bypass semantics (production apply throws on !valid, the
//            diagnostic apply_provisional does not); build_provisional_rec keeps
//            valid=false + the original failure (NOT disguised as valid).
//   Phase C  apply_provisional == iqrfrec::apply on a valid PASS fixture (byte-equal),
//            plus the full 5-stage equivalence HARD GATE with per-stage SHAs.
//   Phase E  solve_real / complex_lstsq exactness (wide-linear image ratio), the legal
//            attribution-token set, and (when the real board dump is present) the
//            decompose_residual structure: 4 fixed candidates, reconstruction_consistent,
//            a legal attribution token, and finite improvement ratios.
//
// argv[1] = clean24 (D2 sidecar) dir   (default ../clean24_smoke)
// argv[2] = a real failed-RX dump dir  (default ../../board_capture_extracted/.../failed_rx/1500)
// The real-dump and clean24-dependent tests SKIP (not fail) when their inputs are absent.

#include "../host_tools/replay_fix10class24_failed_rx_force_classify.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <functional>
#include <set>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

bool file_exists(const std::string& p) {
    std::ifstream f(p, std::ios::binary);
    return static_cast<bool>(f);
}

// Deterministic clean single-burst capture + its production (valid=true) recovery.
struct Synthetic {
    std::vector<std::int16_t> payload;
    std::vector<std::int16_t> burst;
    std::vector<std::complex<double>> rx;
    iqrfrec::EstimateConfig cfg;
    iqdual23fix10::CoarseCfoRecovery ccr;
    replay24force::AlignedFin af;
};

Synthetic make_synthetic() {
    Synthetic s;
    s.payload.assign(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 41) / 41.0;
        s.payload[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1150.0 * std::cos(ph)));
        s.payload[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1150.0 * std::sin(ph)));
    }
    s.burst = iqrftrain::build_burst(s.payload);
    s.rx = iqrftrain::deinterleave(s.burst);
    s.cfg = replay24::config(2048.0);
    s.ccr = iqdual23fix10::recover_payload_with_coarse_cfo(s.rx, s.cfg, 1.0);
    s.af = replay24force::rebuild_aligned_fin(s.rx, s.ccr.coarse_cfo_hz,
                                             s.ccr.fractional_timing_samples, s.cfg);
    return s;
}

const std::set<std::string> kLegalTokens = {
    "DOMINANT_RESIDUAL_PHASE_DRIFT",
    "DOMINANT_RESIDUAL_IQ_IMBALANCE",
    "DOMINANT_RESIDUAL_FREQUENCY_SELECTIVE",
    "DOMINANT_RESIDUAL_RANDOM_NOISE",
    "MIXED_OR_NOT_IDENTIFIED",
};

// ---- Phase E: solve_real (Gauss-Jordan, small dense) ------------------------------
void test_solve_real() {
    // [2 1; 1 3] x = [5; 6]  ->  x = [9/5, 7/5].
    std::vector<std::vector<double>> A = {{2.0, 1.0}, {1.0, 3.0}};
    std::vector<double> b = {5.0, 6.0};
    const std::vector<double> z = replay24force::solve_real(A, b);
    check(z.size() == 2, "solve_real returns 2 unknowns");
    check(std::fabs(z[0] - 9.0 / 5.0) < 1e-12 && std::fabs(z[1] - 7.0 / 5.0) < 1e-12,
          "solve_real solves 2x2 system exactly");

    bool threw = false;
    try { replay24force::solve_real({{0.0, 0.0}, {0.0, 0.0}}, {1.0, 1.0}); }
    catch (...) { threw = true; }
    check(threw, "solve_real throws on singular normal matrix");
}

// ---- Phase E: complex_lstsq recovers a,b of x = a*m + b*conj(m) exactly -----------
void test_complex_lstsq_wide_linear() {
    const std::size_t N = 64;
    const std::complex<double> a(1.3, 0.4), b(0.2, -0.1);
    std::vector<std::complex<double>> m(N), x(N);
    for (std::size_t k = 0; k < N; ++k) {
        m[k] = std::complex<double>(std::cos(0.7 * k) + 0.5, std::sin(0.3 * k) + 0.2);
        x[k] = a * m[k] + b * std::conj(m[k]);
    }
    std::vector<std::vector<std::complex<double>>> Phi(2,
        std::vector<std::complex<double>>(N));
    for (std::size_t k = 0; k < N; ++k) { Phi[0][k] = m[k]; Phi[1][k] = std::conj(m[k]); }
    const std::vector<std::complex<double>> th = replay24force::complex_lstsq(x, Phi, 0.0);
    check(th.size() == 2, "complex_lstsq returns 2 params");
    check(std::abs(th[0] - a) < 1e-12, "complex_lstsq recovers a exactly");
    check(std::abs(th[1] - b) < 1e-12, "complex_lstsq recovers b (image) exactly");
    const double image_ratio = std::abs(th[1]) / std::abs(th[0]);
    const double expect = std::abs(b) / std::abs(a);
    check(std::fabs(image_ratio - expect) < 1e-12, "wide-linear image ratio |b|/|a|");
}

// ---- Phase B: apply_provisional keeps the fail-closed safety guards -----------------
void test_apply_provisional_fail_closed() {
    const Synthetic s = make_synthetic();
    check(s.ccr.rec.valid, "synthetic recovery valid (precondition)");

    // unsafe payload gain (both gain fields <= 1e-12).
    {
        iqrfrec::PerFileRecovery rec = s.ccr.rec;
        rec.payload_rms_gain_mag = 0.0;
        rec.payload_gain_mag = 0.0;
        bool threw = false;
        try { replay24force::apply_provisional(s.af.aligned, rec); } catch (...) { threw = true; }
        check(threw, "apply_provisional throws on unsafe (zero) payload gain");
    }
    // NaN gain.
    {
        iqrfrec::PerFileRecovery rec = s.ccr.rec;
        rec.payload_rms_gain_mag = std::nan("");
        rec.payload_gain_mag = std::nan("");
        bool threw = false;
        try { replay24force::apply_provisional(s.af.aligned, rec); } catch (...) { threw = true; }
        check(threw, "apply_provisional throws on NaN payload gain");
    }
    // unsafe TX scale (0 and negative).
    for (double ts : {0.0, -1.0}) {
        iqrfrec::PerFileRecovery rec = s.ccr.rec;
        rec.payload_tx_scale = ts;
        bool threw = false;
        try { replay24force::apply_provisional(s.af.aligned, rec); } catch (...) { threw = true; }
        check(threw, "apply_provisional throws on unsafe TX scale");
    }
    // valid rec proceeds and yields the full payload.
    {
        const std::vector<std::complex<double>> out =
            replay24force::apply_provisional(s.af.aligned, s.ccr.rec);
        check(out.size() == iqrftrain::kPayloadComplex,
              "apply_provisional returns kPayloadComplex samples on a valid rec");
    }
}

// ---- Phase B: build_provisional_rec does NOT disguise the failure as valid ----------
void test_build_provisional_rec() {
    const Synthetic s = make_synthetic();
    const iqrfrec::PerFileRecovery rec =
        replay24force::build_provisional_rec(s.ccr.rec, 2.5, 45.0, 1.0);
    check(rec.computed, "provisional rec computed==true");
    check(!rec.valid, "provisional rec valid==false (NOT disguised)");
    check(rec.failure == iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH,
          "provisional rec failure preserved == PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH");
    check(rec.timing_offset == s.ccr.rec.timing_offset, "provisional rec timing copied");
    check(rec.cfo_hz == s.ccr.rec.cfo_hz, "provisional rec fine CFO copied");
    check(rec.sro_ppm == s.ccr.rec.sro_ppm, "provisional rec SRO copied");
    check(rec.payload_gain_mag == 2.5, "provisional rec canonical gain copied");
    check(rec.payload_phase_deg == 45.0, "provisional rec canonical phase copied");
    check(rec.payload_tx_scale == 1.0, "provisional rec TX scale copied");
}

// ---- Phase B: production apply refuses the provisional rec; diagnostic proceeds ----
void test_provisional_valid_gate_bipass() {
    const Synthetic s = make_synthetic();
    const iqrfrec::PerFileRecovery rec = replay24force::build_provisional_rec(
        s.ccr.rec, s.ccr.rec.payload_gain_mag, s.ccr.rec.payload_phase_deg, 1.0);

    bool prod_threw = false;
    try { iqrfrec::apply(s.af.aligned, rec); } catch (...) { prod_threw = true; }
    check(prod_threw, "production iqrfrec::apply throws on invalid rec (gate KEPT)");

    bool diag_threw = false;
    try {
        const std::vector<std::complex<double>> out =
            replay24force::apply_provisional(s.af.aligned, rec);
        check(out.size() == iqrftrain::kPayloadComplex,
              "apply_provisional bypasses valid gate only, still produces payload");
    } catch (...) { diag_threw = true; }
    check(!diag_threw, "apply_provisional does NOT throw on invalid rec (diagnostic only)");
}

// ---- Phase C: apply_provisional == production apply on a valid rec (byte-equal) -----
void test_apply_provisional_equals_production() {
    const Synthetic s = make_synthetic();
    const std::vector<std::complex<double>> prod = iqrfrec::apply(s.af.aligned, s.ccr.rec);
    const std::vector<std::complex<double>> diag =
        replay24force::apply_provisional(s.af.aligned, s.ccr.rec);
    check(prod.size() == diag.size(), "apply vs apply_provisional same length");
    const bool byte_equal = std::equal(prod.begin(), prod.end(), diag.begin(),
        [](const std::complex<double>& a, const std::complex<double>& b) {
            return a.real() == b.real() && a.imag() == b.imag();
        });
    check(byte_equal, "apply_provisional == iqrfrec::apply (byte-equal on valid rec)");
}

// ---- Phase C: full 5-stage equivalence HARD GATE + per-stage SHAs -------------------
void test_pass_fixture_equivalence(const std::string& clean24_dir) {
    if (!file_exists(clean24_dir + "/route_d2_rf_manifest.tsv")) {
        std::printf("  SKIP 5-stage equivalence (clean24 sidecar absent at '%s')\n",
                    clean24_dir.c_str());
        return;
    }
    const replay24force::EquivalenceResult e =
        replay24force::run_pass_fixture_equivalence(clean24_dir, 1500);
    check(e.apply_identical, "Phase C: apply == apply_provisional (byte-identical)");
    check(e.payload_iq_identical, "Phase C: payload_iq byte-identical");
    check(e.recovered_stream_identical, "Phase C: recovered_stream byte-identical");
    check(e.classification_window_identical, "Phase C: classification_window byte-identical");
    check(e.model_input_identical, "Phase C: model_input byte-identical");
    for (const auto& s : {e.payload_sha, e.payload_iq_sha, e.stream_sha, e.window_sha,
                          e.model_input_sha}) {
        check(s.size() == 64, "Phase C: stage SHA is 64 hex chars");
    }
    check(e.window_sha == e.model_input_sha,
          "Phase C: classification_window SHA == model_input SHA (same [2,1024] tensor)");
}

// ---- Phase E: legal attribution-token set -------------------------------------------
void test_attribution_token() {
    check(kLegalTokens.size() == 5, "exactly 5 legal attribution tokens");
    for (const auto& t : kLegalTokens) {
        check(!t.empty() && t.find(' ') == std::string::npos,
              "legal token non-empty, no spaces: " + t);
    }
    check(kLegalTokens.count("MIXED_OR_NOT_IDENTIFIED") == 1,
          "MIXED_OR_NOT_IDENTIFIED is a legal token");
}

// ---- Phase E: decompose_residual on a real dump (SKIP when absent) ------------------
void test_decompose_real(const std::string& dump) {
    if (dump.empty() || !file_exists(dump + "/raw_rx_ci16le.bin") ||
        !file_exists(dump + "/recovery_diagnostics.json")) {
        std::printf("  SKIP real-dump residual decomposition (dump absent at '%s')\n",
                    dump.c_str());
        return;
    }
    const replay24force::ResidualDecomposition r =
        replay24force::decompose_residual(dump, "test_capture", 1500);
    check(r.reconstruction_consistent,
          "decompose: reconstruction consistent with canonical replay");
    check(r.candidates.size() == 4, "decompose: exactly 4 fixed candidates");
    check(r.residual_before > 0.10, "decompose: residual_before > 0.10 (board failure)");
    const std::vector<std::string> names = {"const_phase", "residual_cfo", "wide_linear", "fir5"};
    for (std::size_t i = 0; i < names.size(); ++i) {
        check(r.candidates[i].name == names[i],
              "decompose: candidate #" + std::to_string(i) + " is " + names[i]);
    }
    for (const auto& c : r.candidates) {
        check(std::isfinite(c.residual_after_validation) && c.residual_after_validation >= 0.0,
              "decompose: validation residual finite/non-negative for " + c.name);
        check(std::isfinite(c.improvement_ratio) && c.improvement_ratio >= 0.0,
              "decompose: improvement_ratio finite/non-negative for " + c.name);
    }
    check(std::isfinite(r.wide_linear_image_ratio),
          "decompose: wide-linear image ratio finite");
    check(kLegalTokens.count(r.attribution) == 1,
          "decompose: attribution is a legal token (got " + r.attribution + ")");
}

}  // namespace

void run_test(const char* name, const std::function<void()>& fn) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main(int argc, char** argv) {
    std::printf("test_fix10class24_failed_rx_force_classify\n");
    const std::string clean24 = (argc > 1) ? std::string(argv[1]) : std::string("../clean24_smoke");
    const std::string dump = (argc > 2) ? std::string(argv[2])
        : std::string("../../board_capture_extracted/rml24_rxbw_10000000_run1_1773377032/failed_rx/1500");

    run_test("solve_real", test_solve_real);
    run_test("complex_lstsq_wide_linear", test_complex_lstsq_wide_linear);
    run_test("apply_provisional_fail_closed", test_apply_provisional_fail_closed);
    run_test("build_provisional_rec", test_build_provisional_rec);
    run_test("provisional_valid_gate_bipass", test_provisional_valid_gate_bipass);
    run_test("apply_provisional_equals_production", test_apply_provisional_equals_production);
    run_test("pass_fixture_equivalence", [&] { test_pass_fixture_equivalence(clean24); });
    run_test("attribution_token", test_attribution_token);
    run_test("decompose_real", [&] { test_decompose_real(dump); });

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
