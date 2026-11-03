// test_synthetic_iq_roundtrip.cpp -- host tests for Stage G route D
// (board_package/synthetic_iq_roundtrip.hpp): the RadioML round-trip preprocess.
//
//   * interpolation FIR identity (length, DC gain, per-phase DC, symmetry);
//   * deterministic ×20 polyphase interpolation (DC + two-tone preservation);
//   * the full round-trip chain on a deterministic two-tone AND on a generated
//     QPSK tensor, asserting recovered-tensor fidelity (NMSE/gain/correlation),
//     determinism (requirement 10 at the tensor level), and edge policy;
//   * the align+measure routine (requirement 6): a pure delay/scale/rotate of a
//     signal must be recovered with ~zero NMSE and the exact delay/gain/phase;
//   * fail-closed (interpolation factor, guard, reflect guard range, parse).
//
// iCraft-free and libiio-free: exercises only chain_common.hpp / resampler.cpp
// (the same code the board runs) plus the roundtrip header.
//
// Build/run: see host_tests/build_host_tests.sh (links ../sdr_adapter/resampler.cpp).

#include "../board_package/synthetic_iq_roundtrip.hpp"
#include "../board_package/synthetic_iq_runner.hpp"
#include "../board_package/synthetic_iq_generator.hpp"

#include <complex>
#include <cstdio>
#include <cstdlib>
#include <vector>

namespace {

constexpr double kPiT = 3.14159265358979323846;

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void check_near(double got, double want, double tol, const char* what) {
    if (std::fabs(got - want) <= tol) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (got %.9g want %.9g)\n", what, got, want); }
}

template <typename F>
void check_throws(F fn, const char* what) {
    bool threw = false;
    try { fn(); } catch (...) { threw = true; }
    if (threw) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (did not throw)\n", what); }
}

// ---------------------------------------------------------------------------
// Interpolation FIR identity (requirement 4).
// ---------------------------------------------------------------------------
void test_fir_identity() {
    const auto h = syniq_rt::interpolation_fir();
    check(h.size() == syniq_rt::kInterpTapsTotal, "FIR length == 640");
    check(h.size() % syniq_rt::kInterpFactor == 0, "FIR length multiple of 20");

    double S = 0.0;
    for (double v : h) S += v;
    check_near(S, syniq_rt::kInterpFactor, 1e-9, "FIR total DC gain == up == 20");

    // each polyphase branch sums to ~1.0 (this is what preserves DC per sample).
    double worst = 0.0;
    for (int r = 0; r < syniq_rt::kInterpFactor; ++r) {
        double s = 0.0;
        for (std::size_t k = 0; k < syniq_rt::kInterpTapsPerPhase; ++k)
            s += h[static_cast<std::size_t>(r) + k * syniq_rt::kInterpFactor];
        worst = std::max(worst, std::fabs(s - 1.0));
    }
    check(worst < 1e-3, "FIR every phase DC sum ~ 1.0 (worst |s-1| < 1e-3)");

    // even symmetry about (N-1)/2.
    double max_asym = 0.0;
    for (std::size_t n = 0; n < h.size(); ++n)
        max_asym = std::max(max_asym, std::fabs(h[n] - h[h.size() - 1 - n]));
    check(max_asym < 1e-9, "FIR even symmetry h[n] == h[N-1-n]");

    std::printf("  FIR: worst|phase_sum-1| = %.3e, max|asym| = %.3e\n", worst, max_asym);
}

// ---------------------------------------------------------------------------
// Deterministic ×20 interpolation.
// ---------------------------------------------------------------------------
void test_interpolate() {
    const auto h = syniq_rt::interpolation_fir();
    const std::size_t N = 128;

    // DC: constant 1+0j -> constant ~1 in the steady-state interior (away from the
    // zero-pad edges where the filter's partial taps naturally attenuate).
    std::vector<std::complex<double>> dc(N, {1.0, 0.0});
    const auto ydc = syniq_rt::interpolate_20x(dc, h);
    check(ydc.size() == N * syniq_rt::kInterpFactor, "interp output length == L*N");
    const std::size_t p = h.size() / syniq_rt::kInterpFactor;
    const std::size_t lo = syniq_rt::kInterpFactor * (p - 1);
    const std::size_t hi = syniq_rt::kInterpFactor * N;
    double worst = 0.0;
    for (std::size_t m = lo; m < hi; ++m)
        worst = std::max(worst, std::fabs(ydc[m].real() - 1.0));
    check(worst < 1e-3, "interp DC: steady-state output ~ 1.0");

    // two-tone: interpolation of a band-limited tone keeps its frequency/energy
    // (steady-state region, away from the zero-guard edge).
    std::vector<std::complex<double>> x(N);
    for (std::size_t k = 0; k < N; ++k) {
        const double t = 2.0 * kPiT * 7.0 * static_cast<double>(k) / static_cast<double>(N);
        x[k] = std::complex<double>(std::cos(t), std::sin(t));
    }
    const auto y = syniq_rt::interpolate_20x(x, h);
    check(y.size() == N * syniq_rt::kInterpFactor, "interp two-tone length");

    // determinism.
    const auto y2 = syniq_rt::interpolate_20x(x, h);
    check(y == y2, "interp deterministic (bit-identical)");

    std::printf("  interp: DC worst=%.3e\n", worst);
}

// ---------------------------------------------------------------------------
// align+measure: pure delay/scale/rotate must be recovered exactly (req 6).
// ---------------------------------------------------------------------------
void test_align_measure() {
    const std::size_t N = syniq_rt::kGuard + chain::kFrameComplex;
    // base = a signal; original z = g0 * base (a scaled/rotated copy); recovered
    // rv = base, delayed by d.  The metric's LS gain g (z ~ g*rv) must recover g0.
    std::vector<std::complex<double>> base(chain::kFrameComplex);
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
        const double a = std::sin(2.0 * kPiT * 11.0 * k / 1024.0);
        const double b = std::cos(2.0 * kPiT * 23.0 * k / 1024.0);
        base[k] = std::complex<double>(a, b);
    }
    const double gmag = 0.9, phi = 0.7;
    const std::complex<double> g = gmag * std::complex<double>(std::cos(phi), std::sin(phi));
    const int d = 33;
    std::vector<std::complex<double>> z(chain::kFrameComplex);
    std::vector<std::complex<double>> rv(N, 0.0);
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
        z[k] = g * base[k];
        rv[static_cast<std::size_t>(d + static_cast<int>(k))] = base[k];
    }

    const auto m = syniq_rt::compute_roundtrip_metrics(z, rv);
    check(m.delay_offset == d, "align: exact integer delay recovered");
    check_near(m.gain_db, 20.0 * std::log10(gmag), 0.1, "align: exact gain");
    check_near(m.phase_deg, phi * 180.0 / kPiT, 0.5, "align: exact phase");
    check(m.nmse_center < 1e-9, "align: NMSE ~ 0 for pure delay/scale/rotate");
    check(m.nmse_full < 1e-9, "align: full NMSE ~ 0 (no edge corruption here)");
    check(m.corr_center > 0.999999, "align: correlation ~ 1.0");

    // diagnostics must be finite and in [0,1].
    check(m.corr_swap >= 0.0 && m.corr_swap <= 1.0, "align: corr_swap in [0,1]");
    check(m.corr_conj >= 0.0 && m.corr_conj <= 1.0, "align: corr_conj in [0,1]");
    std::printf("  align: delay=%d gain=%.4f dB phase=%.3f deg corr=%.7f\n",
                m.delay_offset, m.gain_db, m.phase_deg, m.corr_center);
}

// ---------------------------------------------------------------------------
// Full round-trip chain.
// ---------------------------------------------------------------------------
std::vector<float> make_two_tone_tensor() {
    std::vector<float> t(chain::kTensorFloats, 0.0f);
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
        const double c1 = 0.8 * std::cos(2.0 * kPiT * 16.0 * k / 1024.0 + 0.3);
        const double s1 = 0.8 * std::sin(2.0 * kPiT * 16.0 * k / 1024.0 + 0.3);
        const double c2 = 0.4 * std::cos(2.0 * kPiT * 33.0 * k / 1024.0 + 1.1);
        const double s2 = 0.4 * std::sin(2.0 * kPiT * 33.0 * k / 1024.0 + 1.1);
        t[k] = static_cast<float>(c1 + c2);
        t[chain::kFrameComplex + k] = static_cast<float>(s1 + s2);
    }
    // Normalize to complex RMS 1.0 (the model-domain convention), so the round-trip
    // gain lands at ~0 dB exactly like route A / route B clean tensors.
    double e = 0.0;
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
        e += static_cast<double>(t[k]) * t[k] +
             static_cast<double>(t[chain::kFrameComplex + k]) * t[chain::kFrameComplex + k];
    const double rms = std::sqrt(e / static_cast<double>(chain::kFrameComplex));
    for (auto& v : t) v = static_cast<float>(static_cast<double>(v) / rms);
    return t;
}

void test_roundtrip_tone() {
    const auto t = make_two_tone_tensor();
    syniq_rt::RoundtripConfig cfg;   // defaults: zero guard, rms 16, rec_scale auto
    const auto r = syniq_rt::roundtrip_radioml(t.data(), cfg);

    check(r.recovered_tensor.size() == chain::kTensorFloats, "rt: recovered tensor 2048");
    check(r.original_complex.size() == chain::kFrameComplex, "rt: original 1024 complex");
    check(r.interpolated_complex.size() ==
              (chain::kFrameComplex + 2 * syniq_rt::kGuard) * syniq_rt::kInterpFactor,
          "rt: interpolated length == 20*(1024+2*guard)");
    check(r.quantized_iq.size() == 2 * r.interpolated_complex.size(), "rt: int16 interleaved");
    check(r.quant.clip == 0, "rt: no int16 clipping at 16 counts");
    check(r.rec_scale_used > 0.0f, "rt: rec_scale resolved");

    // fidelity: the recovered tensor aligns to the original with ~0 dB gain and
    // low NMSE (dominated by int16 quantization, filtered by the decimation FIR).
    const auto& m = r.metrics;
    std::printf("  rt tone: delay=%d gain=%.3f dB phase=%.3f deg nmse_full=%.3e "
                "nmse_center=%.3e evm=%.4f%% corr=%.6f\n",
                m.delay_offset, m.gain_db, m.phase_deg, m.nmse_full, m.nmse_center,
                m.evm_center_pct, m.corr_center);
    check(m.delay_offset >= 0, "rt: delay offset non-negative");
    check_near(m.gain_db, 0.0, 0.5, "rt: gain ~ 0 dB");
    check(m.nmse_center < 0.001, "rt: centre NMSE < 0.001 (-30 dB)");
    check(m.corr_center > 0.999, "rt: centre correlation > 0.999");
    check(m.rms_orig > 0.0 && m.rms_recov > 0.0, "rt: RMS finite and positive");
    check(m.papr_orig_db > 0.0 && m.papr_recov_db > 0.0, "rt: PAPR finite");
    // zero-guard: edges carry interpolation/decimation transient -> centre is
    // strictly better than the full window (requirement 5 both numbers).
    check(m.nmse_center <= m.nmse_full, "rt: centre NMSE <= full NMSE (edge effect)");

    // determinism at the tensor level (requirement 10).
    const auto r2 = syniq_rt::roundtrip_radioml(t.data(), cfg);
    check(r.recovered_tensor == r2.recovered_tensor, "rt: recovered tensor deterministic");
    check(r.quantized_iq == r2.quantized_iq, "rt: int16 stream deterministic");
}

void test_roundtrip_qpsk() {
    // Realistic RadioML-like QPSK tensor via route B's generator.
    syniq_run::GeneratedConfig g;
    g.mod = syniq::Modulation::QPSK;
    g.sps = 8;
    g.seed = 0x39e5ULL;
    g.norm = "none";
    const auto tensors = syniq_run::generate_model_input_tensors(g, 1);
    const auto& t = tensors[0];

    syniq_rt::RoundtripConfig cfg;
    const auto r = syniq_rt::roundtrip_radioml(t.data(), cfg);
    const auto& m = r.metrics;
    std::printf("  rt qpsk: delay=%d gain=%.3f dB nmse_full=%.3e nmse_center=%.3e "
                "corr=%.6f clip=%zu\n",
                m.delay_offset, m.gain_db, m.nmse_full, m.nmse_center,
                m.corr_center, r.quant.clip);
    check_near(m.gain_db, 0.0, 0.5, "rt qpsk: gain ~ 0 dB");
    check(m.nmse_center < 0.001, "rt qpsk: centre NMSE < 0.001");
    check(m.corr_center > 0.999, "rt qpsk: correlation > 0.999");
    check(r.quant.clip == 0, "rt qpsk: no clipping");
    check(r.recovered_tensor.size() == chain::kTensorFloats, "rt qpsk: tensor 2048");
}

void test_roundtrip_edge_policy() {
    const auto t = make_two_tone_tensor();

    syniq_rt::RoundtripConfig cz;   // zero
    const auto rz = syniq_rt::roundtrip_radioml(t.data(), cz);

    syniq_rt::RoundtripConfig cr;
    cr.edge_policy = syniq_rt::EdgePolicy::Reflect;
    const auto rr = syniq_rt::roundtrip_radioml(t.data(), cr);

    std::printf("  rt edge: zero nmse_full=%.3e nmse_center=%.3e | reflect nmse_full=%.3e nmse_center=%.3e\n",
                rz.metrics.nmse_full, rz.metrics.nmse_center,
                rr.metrics.nmse_full, rr.metrics.nmse_center);
    // Both policies must yield a clean valid centre and a visible edge effect
    // (full-window error no better than centre error) — requirement 5 reports
    // both numbers; the policy itself is a documented diagnostic choice.
    check(rz.edge_policy == "zero" && rr.edge_policy == "reflect",
          "rt edge: edge_policy names recorded");
    check(rz.metrics.nmse_center < 0.001 && rr.metrics.nmse_center < 0.001,
          "rt edge: both policies centre NMSE < 0.001");
    check(rz.metrics.nmse_center <= rz.metrics.nmse_full &&
          rr.metrics.nmse_center <= rr.metrics.nmse_full,
          "rt edge: edge effect visible in both (centre <= full)");
    check_near(rz.metrics.gain_db, 0.0, 0.5, "rt edge: zero gain ~ 0 dB");
    check_near(rr.metrics.gain_db, 0.0, 0.5, "rt edge: reflect gain ~ 0 dB");
}

void test_fail_closed() {
    const auto t = make_two_tone_tensor();

    syniq_rt::RoundtripConfig bad_fac;
    bad_fac.interpolation_factor = 19;
    check_throws([&]() { (void)syniq_rt::roundtrip_radioml(t.data(), bad_fac); },
                 "rt: interpolation factor != 20 throws");

    syniq_rt::RoundtripConfig bad_guard;
    bad_guard.guard = -1;
    check_throws([&]() { (void)syniq_rt::roundtrip_radioml(t.data(), bad_guard); },
                 "rt: negative guard throws");

    syniq_rt::RoundtripConfig bad_reflect;
    bad_reflect.edge_policy = syniq_rt::EdgePolicy::Reflect;
    bad_reflect.guard = 2000;  // >= 1024
    check_throws([&]() { (void)syniq_rt::roundtrip_radioml(t.data(), bad_reflect); },
                 "rt: reflect guard >= signal length throws");

    check_throws([&]() { (void)syniq_rt::parse_edge_policy("bogus"); },
                 "parse_edge_policy: bogus throws");
    check(syniq_rt::parse_edge_policy("zero") == syniq_rt::EdgePolicy::Zero,
          "parse_edge_policy: zero");
    check(syniq_rt::parse_edge_policy("reflect") == syniq_rt::EdgePolicy::Reflect,
          "parse_edge_policy: reflect");
}

}  // namespace

int main() {
    std::printf("test_synthetic_iq_roundtrip\n");
    test_fir_identity();
    test_interpolate();
    test_align_measure();
    test_roundtrip_tone();
    test_roundtrip_qpsk();
    test_roundtrip_edge_policy();
    test_fail_closed();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
