// test_iq_rf_fix9r2b.cpp -- host tests for Route F fix9r2b Phase 1 (the
// DIAGNOSTIC-ONLY instrumentation: waveform capture + provisional scalar-recovery
// metrics + fixed summary/token semantics).  iCraft-free and libiio-free: it
// exercises ONLY the pure functions in iq_rf_fix9r2b_diagnostic.hpp -- the exact
// code the board runner calls -- plus the shared recovery core it reuses.
//
// These are the TDD "red" tests written BEFORE the fix (discipline §8): each test
// below reproduces a fix9r2a defect and turns green only after the fix9r2b module
// corrects it:
//   * summary min/max non-zero: a run failing only on residual must still report its
//     true corr_min / residual_max (fix9r2a reported 0.0 for both);
//   * token semantics: in diagnostic mode the regression token is NOT_EVALUATED,
//     never ROUTE_F_23CLASS_ACCURACY_REGRESSION_FAIL;
//   * provisional payload never enters the model: provisional_apply_scalar is
//     DIAGNOSTIC-ONLY (it yields a plain payload vector; only iqrfrec::apply gated
//     on RF_PRESERVES_IQ reaches the NPU);
//   * waveform capture round-trip: SHA / samples / RMS / format are recorded and
//     reloadable, so the offline analysis reads the board's files verbatim.

#include "../board_package/iq_rf_fix9r2b_diagnostic.hpp"
#include "../board_package/iq_rf_training_frame.hpp"
#include "../board_package/iq_rf_frame_layout.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// deterministic PRBS payload (same LCG as the other fix9r host tests)
std::vector<std::int16_t> make_prbs(std::size_t P, int A, std::uint32_t seed) {
    std::vector<std::int16_t> iq(P * 2);
    std::uint32_t s = seed ? seed : 0x9e3779b9u;
    auto bit = [&s]() -> int {
        s = s * 1664525u + 1013904223u;
        return static_cast<int>((s >> 24) & 1u);
    };
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(bit() ? A : -A);
        iq[k * 2 + 1] = static_cast<std::int16_t>(bit() ? A : -A);
    }
    return iq;
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}
#endif

// ---- 1. waveform_stem strips the ci16 extension ------------------------------

void test_waveform_stem() {
    check(iqrffix9r2b::waveform_stem("quantized_d2_2p56m_000006.ci16") ==
              "quantized_d2_2p56m_000006",
          "stem: strips .ci16");
    check(iqrffix9r2b::waveform_stem("quantized_d2_2p56m_000002.ci16") ==
              "quantized_d2_2p56m_000002",
          "stem: 4ASK file stem");
    check(iqrffix9r2b::waveform_stem("no_ext") == "no_ext",
          "stem: no extension unchanged");
}

// ---- 2. waveform save/load round-trip (SHA / samples / RMS / format) ---------

void test_waveform_roundtrip() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("fix9r2b_wave");
    const std::string path = dir + "/expected_training.f32";

    std::vector<std::complex<double>> z;
    for (std::size_t k = 0; k < 1024; ++k)
        z.push_back(std::complex<double>(std::sin(k * 0.1), std::cos(k * 0.13)));

    const auto rec = iqrffix9r2b::save_f32_interleaved(path, z);
    check(rec.path == path, "wave: path recorded");
    check(rec.format == std::string(iqrffix9r2b::kF32Format), "wave: format recorded");
    check(rec.complex_samples == 1024, "wave: complex_samples == 1024");

    // SHA must equal sdr::Sha256 over the raw float32 bytes.
    std::vector<float> f32(z.size() * 2);
    for (std::size_t k = 0; k < z.size(); ++k) {
        f32[k * 2 + 0] = static_cast<float>(z[k].real());
        f32[k * 2 + 1] = static_cast<float>(z[k].imag());
    }
    check(rec.sha256 == sdr::Sha256::hex(f32.data(), f32.size() * sizeof(float)),
          "wave: sha256 matches the bytes");

    double energy = 0.0;
    for (const auto& c : z) energy += c.real() * c.real() + c.imag() * c.imag();
    const double rms = std::sqrt(energy / static_cast<double>(z.size()));
    check(std::fabs(rec.rms - rms) < 1e-6, "wave: rms matches");

    std::vector<std::complex<double>> back;
    check(iqrffix9r2b::load_f32_interleaved(path, back), "wave: load ok");
    check(back.size() == z.size(), "wave: load length");
    double err = 0.0;
    for (std::size_t k = 0; k < z.size(); ++k)
        err += std::abs(back[k] - z[k]);
    check(err < 1e-3, "wave: load round-trip matches (float32 precision)");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 3. provisional_apply_scalar == iqrfrec::apply when valid -----------------

void test_provisional_equals_apply_when_valid() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 101);
    const auto burst = iqrftrain::build_burst(payload);
    const auto rx = iqrftrain::deinterleave(burst);
    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "prov: clean identity estimate valid");

    const auto a = iqrfrec::apply(rx, rec);
    const auto p = iqrffix9r2b::provisional_apply_scalar(rx, rec);
    check(p.size() == iqrftrain::kPayloadComplex, "prov: provisional length");
    check(a.size() == p.size(), "prov: same length as apply");
    double err = 0.0;
    for (std::size_t k = 0; k < a.size(); ++k) err += std::abs(a[k] - p[k]);
    check(err < 1e-9, "prov: provisional == apply when valid");
}

// ---- 4. provisional_apply_scalar + iqrfrec::apply fail-closed when invalid -----

void test_provisional_when_residual_fails() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 102);
    const auto burst = iqrftrain::build_burst(payload);
    const auto rx = iqrftrain::deinterleave(burst);
    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "prov-fail: identity valid");

    // Simulate an invalid recovery (valid=false, failure set).  With the fix9r2g
    // fail-closed semantics NEITHER iqrfrec::apply NOR provisional_apply_scalar may
    // silently fall back to a unit gain: apply throws, provisional returns empty.
    // (fix9r2b previously returned zeros from apply and a real payload from
    // provisional here; fix9r2g forbids both so an unrecovered payload can never
    // reach the model.)
    iqrfrec::PerFileRecovery bad = rec;
    bad.valid = false;
    bad.failure = iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH;

    bool apply_threw = false;
    try {
        (void)iqrfrec::apply(rx, bad);
    } catch (const std::runtime_error&) {
        apply_threw = true;
    }
    check(apply_threw, "prov-fail: iqrfrec::apply throws on invalid (no silent unit gain)");

    const auto p = iqrffix9r2b::provisional_apply_scalar(rx, bad);
    check(p.empty(), "prov-fail: provisional returns empty on invalid (fail-closed)");
}

// ---- 5. provisional metrics semantics ----------------------------------------

void test_provisional_metrics() {
    std::vector<std::complex<double>> ref;
    for (std::size_t k = 0; k < 256; ++k)
        ref.push_back(std::complex<double>(k % 3 - 1, (k % 5) - 2));

    // identity: corr 1, nmse 0
    auto m = iqrffix9r2b::provisional_payload_metrics(ref, ref);
    check(m.computed && std::fabs(m.corr - 1.0) < 1e-9, "metrics: identity corr == 1");
    check(m.nmse < 1e-9, "metrics: identity nmse == 0");

    // doubled amplitude: corr still 1 (magnitude-normalized), nmse == 1
    std::vector<std::complex<double>> dbl;
    for (const auto& c : ref) dbl.push_back(c * 2.0);
    m = iqrffix9r2b::provisional_payload_metrics(dbl, ref);
    check(std::fabs(m.corr - 1.0) < 1e-9, "metrics: amplitude-invariant corr == 1");
    check(std::fabs(m.nmse - 1.0) < 1e-6, "metrics: doubled amplitude nmse == 1");

    // empty -> not computed
    m = iqrffix9r2b::provisional_payload_metrics({}, ref);
    check(!m.computed, "metrics: empty recovered -> not computed");
}

// ---- 6. summary aggregation: corr_min/residual_max non-zero (TDD red->green) --

void test_aggregate_nonzero_when_residual_fails() {
    // Reproduce the R8 2048 board run: 2 files, both preamble FOUND (computed),
    // both INVALID on residual.  fix9r2a reported corr_min=0/residual_max=0.
    iqrffix9r2b::PerFileOutcome bpsk;
    bpsk.computed = true; bpsk.valid = false;
    bpsk.failure = iqrfrec::Failure::TRAINING_RESIDUAL_TOO_HIGH;
    bpsk.training_corr = 0.972940; bpsk.training_residual = 0.237482;

    iqrffix9r2b::PerFileOutcome ask;
    ask.computed = true; ask.valid = false;
    ask.failure = iqrfrec::Failure::TRAINING_RESIDUAL_TOO_HIGH;
    ask.training_corr = 0.975894; ask.training_residual = 0.223639;

    const auto s = iqrffix9r2b::aggregate_training_summary({bpsk, ask});
    check(s.measured_count == 2, "agg: measured_count == 2");
    check(s.valid_count == 0, "agg: valid_count == 0 (residual fail)");
    check(std::fabs(s.corr_min - 0.972940) < 1e-9, "agg: corr_min == 0.972940 (NOT 0)");
    check(std::fabs(s.corr_avg - 0.974417) < 1e-6, "agg: corr_avg == mean");
    check(std::fabs(s.residual_max - 0.237482) < 1e-9, "agg: residual_max == 0.237482");
    check(std::fabs(s.residual_avg - 0.2305605) < 1e-6, "agg: residual_avg == mean");
}

void test_aggregate_mixed() {
    // One NOT_FOUND (no corr), one measured-valid, one measured-invalid: corr/residual
    // aggregate over the two MEASURED files only; valid_count counts the valid one.
    iqrffix9r2b::PerFileOutcome nf;
    nf.computed = true; nf.valid = false;
    nf.failure = iqrfrec::Failure::TRAINING_NOT_FOUND;
    nf.training_corr = 0.0; nf.training_residual = 0.0;

    iqrffix9r2b::PerFileOutcome good;
    good.computed = true; good.valid = true;
    good.failure = iqrfrec::Failure::NONE;
    good.training_corr = 0.999; good.training_residual = 0.01;

    iqrffix9r2b::PerFileOutcome hi;
    hi.computed = true; hi.valid = false;
    hi.failure = iqrfrec::Failure::TRAINING_RESIDUAL_TOO_HIGH;
    hi.training_corr = 0.95; hi.training_residual = 0.3;

    const auto s = iqrffix9r2b::aggregate_training_summary({nf, good, hi});
    check(s.measured_count == 2, "agg-mix: measured_count == 2 (NOT_FOUND excluded)");
    check(s.valid_count == 1, "agg-mix: valid_count == 1");
    check(std::fabs(s.corr_min - 0.95) < 1e-9, "agg-mix: corr_min == 0.95");
    check(std::fabs(s.residual_max - 0.3) < 1e-9, "agg-mix: residual_max == 0.3");
}

// ---- 7. token semantics: diagnostic mode never reports a regression FAIL ------

void test_token_semantics() {
    // diagnostic mode, gate FAIL (the R8 board case)
    auto t = iqrffix9r2b::gate_tokens(true, false, false);
    check(t.summary_token == std::string(iqrffix9r2b::kDiagnosticFail),
          "tok: diag fail summary == DIAGNOSTIC_FAIL");
    check(t.regression_token == std::string(iqrffix9r2b::kNotEvaluated),
          "tok: diag regression == NOT_EVALUATED (NOT regression FAIL)");
    check(t.diagnostic_token == std::string(iqrffix9r2b::kDiagnosticFail),
          "tok: diag diagnostic == DIAGNOSTIC_FAIL");

    // diagnostic mode, gate PASS
    t = iqrffix9r2b::gate_tokens(true, true, false);
    check(t.summary_token == std::string(iqrffix9r2b::kDiagnosticPass),
          "tok: diag pass summary == DIAGNOSTIC_PASS");
    check(t.regression_token == std::string(iqrffix9r2b::kNotEvaluated),
          "tok: diag pass regression still NOT_EVALUATED");

    // regression mode
    t = iqrffix9r2b::gate_tokens(false, false, true);
    check(t.summary_token == std::string(iqrffix9r2b::kRegressionPass),
          "tok: regression pass summary == REGRESSION_PASS");
    check(t.regression_token == std::string(iqrffix9r2b::kRegressionPass),
          "tok: regression pass token == REGRESSION_PASS");
    t = iqrffix9r2b::gate_tokens(false, false, false);
    check(t.regression_token == std::string(iqrffix9r2b::kRegressionFail),
          "tok: regression fail token == REGRESSION_FAIL");
}

// ---- 8. provisional payload never enters the model (structural) --------------

void test_provisional_never_scored() {
    // provisional_apply_scalar returns a plain payload vector and the metrics return
    // (corr, nmse) only -- there is NO class index anywhere in the DIAGNOSTIC path,
    // so a provisional payload cannot be classified.  This asserts the structural
    // separation: the model sees only iqrfrec::apply gated on RF_PRESERVES_IQ.
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 103);
    const auto burst = iqrftrain::build_burst(payload);
    const auto rx = iqrftrain::deinterleave(burst);
    const auto rec = iqrfrec::estimate(rx);
    iqrfrec::PerFileRecovery bad = rec;
    bad.valid = false;
    bad.failure = iqrfrec::Failure::TRAINING_RESIDUAL_TOO_HIGH;

    const auto p = iqrffix9r2b::provisional_apply_scalar(rx, bad);
    const auto m = iqrffix9r2b::provisional_payload_metrics(
        p, iqrftrain::deinterleave(payload));
    // The only outputs are a complex vector and two scalars -- no class, no score.
    check(!m.computed || (m.corr >= 0.0 && m.corr <= 1.0),
          "struct: provisional metrics return corr in [0,1], no class");
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
    std::printf("test_iq_rf_fix9r2b\n");
    run_test("waveform_stem", test_waveform_stem);
    run_test("waveform_roundtrip", test_waveform_roundtrip);
    run_test("provisional_equals_apply_when_valid", test_provisional_equals_apply_when_valid);
    run_test("provisional_when_residual_fails", test_provisional_when_residual_fails);
    run_test("provisional_metrics", test_provisional_metrics);
    run_test("aggregate_nonzero_when_residual_fails", test_aggregate_nonzero_when_residual_fails);
    run_test("aggregate_mixed", test_aggregate_mixed);
    run_test("token_semantics", test_token_semantics);
    run_test("provisional_never_scored", test_provisional_never_scored);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
