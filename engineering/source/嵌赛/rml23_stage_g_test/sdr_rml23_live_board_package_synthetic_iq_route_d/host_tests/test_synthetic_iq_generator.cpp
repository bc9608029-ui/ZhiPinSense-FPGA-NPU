// test_synthetic_iq_generator.cpp -- host tests for the Stage G synthetic-IQ
// generator (board_package/synthetic_iq_generator.hpp) and the B-vs-C waveform
// fidelity proof: does the production 2.56 MSPS -> 128 kSPS decimation chain
// (chain::PreprocessChain) reproduce the directly-synthesized 128 kSPS waveform?
//
// iCraft-free and libiio-free: exercises the exact chain_common.hpp /
// resampler.cpp code the board runs (fs_in = 2.56 MHz, up=1/down=20, 601-tap FIR),
// so route C's fidelity is proven BEFORE the board run.
//
// Build/run: see host_tests/build_host_tests.sh (links ../sdr_adapter/resampler.cpp).

#include "../board_package/synthetic_iq_generator.hpp"
#include "../board_package/chain_common.hpp"

#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdint>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void check_near(double got, double want, double tol, const char* what) {
    const bool ok = std::fabs(got - want) <= tol;
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (got %.9g want %.9g)\n", what, got, want); }
}

template <typename F>
void check_throws(F fn, const char* what) {
    bool threw = false;
    try { fn(); } catch (...) { threw = true; }
    if (threw) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (did not throw)\n", what); }
}

// --- generator primitives ----------------------------------------------------

void test_rrc_properties() {
    const double beta = 0.35;
    for (int sps : {8, 160}) {
        std::vector<double> h = syniq::rrc_coeffs(sps, beta, 8);
        check(static_cast<int>(h.size()) == 8 * sps + 1, "rrc_coeffs length == span*sps+1");
        double e = 0.0;
        for (double v : h) e += v * v;
        check_near(e, static_cast<double>(sps), sps * 1e-6, "rrc_coeffs sum(h^2) == sps");
        // linear-phase symmetry
        bool sym = true;
        for (int i = 0; i < static_cast<int>(h.size()); ++i)
            if (std::fabs(h[i] - h[h.size() - 1 - i]) > 1e-12) sym = false;
        check(sym, "rrc_coeffs symmetric (linear phase)");
    }
}

void test_map_symbol_unit_power() {
    for (syniq::Modulation m : {syniq::Modulation::BPSK, syniq::Modulation::QPSK,
                                syniq::Modulation::ASK4, syniq::Modulation::QAM16}) {
        const int n = syniq::constellation_size(m);
        double e = 0.0;
        for (int i = 0; i < n; ++i) e += std::norm(syniq::map_symbol(m, i));
        check_near(e / n, 1.0, 1e-12, "map_symbol unit average power");
    }
    // deterministic: same index -> same point
    check(syniq::map_symbol(syniq::Modulation::QAM16, 5) ==
          syniq::map_symbol(syniq::Modulation::QAM16, 5), "map_symbol deterministic");
}

void test_symbol_indices_determinism() {
    const auto a = syniq::symbol_indices(syniq::Modulation::QPSK, 12345ULL, 1000);
    const auto b = syniq::symbol_indices(syniq::Modulation::QPSK, 12345ULL, 1000);
    check(a == b, "symbol_indices same seed -> identical stream");
    const auto c = syniq::symbol_indices(syniq::Modulation::QPSK, 99999ULL, 1000);
    bool differ = false;
    for (std::size_t i = 0; i < a.size(); ++i)
        if (a[i] != c[i]) { differ = true; break; }
    check(differ, "symbol_indices different seed -> different stream");
    // indices stay in [0, constellation_size)
    bool in_range = true;
    for (int v : a) if (v < 0 || v >= syniq::constellation_size(syniq::Modulation::QPSK)) in_range = false;
    check(in_range, "symbol_indices values in [0, M)");
}

void test_pulse_shape_geometry() {
    const int n_sym = 256, sps = 8, span = 8;
    const auto sym = syniq::symbol_indices(syniq::Modulation::QPSK, 7ULL, n_sym);
    const auto y = syniq::pulse_shape(sym, syniq::Modulation::QPSK, sps, 0.35, span);
    check(static_cast<int>(y.size()) == (n_sym - span) * sps,
          "pulse_shape length == (n_sym - span) * sps");

    // steady-state RMS ~ 1.0 (unit-power symbols, unit-energy RRC)
    double e = 0.0;
    for (const auto& v : y) e += std::norm(v);
    const double rms = std::sqrt(e / y.size());
    check_near(rms, 1.0, 0.05, "pulse_shape steady-state RMS ~ 1.0");

    // startup/end transient is discarded: the returned block must be steady-state
    // (its mean |x|^2 has no rising edge).  Compare first/last 128-sample power.
    double head = 0.0, mid = 0.0;
    for (int i = 0; i < 128; ++i) head += std::norm(y[i]);
    for (int i = 1024; i < 1024 + 128; ++i) mid += std::norm(y[i]);
    check_near(head / 128.0, mid / 128.0, 0.15, "no startup transient (head power == mid power)");

    // fail-closed: too few symbols for the RRC span
    const auto few = syniq::symbol_indices(syniq::Modulation::QPSK, 7ULL, span);
    check_throws([&]() { (void)syniq::pulse_shape(few, syniq::Modulation::QPSK, sps, 0.35, span); },
                 "pulse_shape throws when n_sym <= span");
}

void test_normalization() {
    const auto sym = syniq::symbol_indices(syniq::Modulation::QPSK, 9ULL, 256);
    auto x = syniq::pulse_shape(sym, syniq::Modulation::QPSK, 8, 0.35, 8);
    auto copy = x;
    syniq::apply_normalization(copy, "none");
    check(copy == x, "normalization 'none' leaves waveform unchanged");

    auto xr = x;
    syniq::apply_normalization(xr, "complex-rms-1");
    double e = 0.0;
    for (const auto& v : xr) e += std::norm(v);
    check_near(std::sqrt(e / xr.size()), 1.0, 1e-12, "complex-rms-1 sets RMS == 1.0 exactly");

    check_throws([&]() { syniq::apply_normalization(x, "per-class"); },
                 "unknown normalization strategy throws (fail-closed)");
}

void test_quantize_int16() {
    const auto sym = syniq::symbol_indices(syniq::Modulation::QPSK, 11ULL, 512);
    const auto x = syniq::pulse_shape(sym, syniq::Modulation::QPSK, 8, 0.35, 8);
    syniq::QuantStats st;
    const auto iq = syniq::quantize_int16(x, 16.0, st);
    check(iq.size() == x.size() * 2, "quantize_int16 output == 2*N int16");
    check_near(st.rms_counts, 16.0, 1.0, "quantize_int16 records RMS ~ requested (16 counts)");
    check(st.peak_counts < 32768.0, "quantize_int16 peak within int16 range");
    check(st.clip == 0, "quantize_int16 no clipping at 16 counts for unit-power waveform");

    // deterministic
    syniq::QuantStats st2;
    const auto iq2 = syniq::quantize_int16(x, 16.0, st2);
    check(iq == iq2, "quantize_int16 deterministic");
}

void test_parse_modulation() {
    check(syniq::parse_modulation("BPSK") == syniq::Modulation::BPSK, "parse BPSK");
    check(syniq::parse_modulation("QPSK") == syniq::Modulation::QPSK, "parse QPSK");
    check(syniq::parse_modulation("4ASK") == syniq::Modulation::ASK4, "parse 4ASK");
    check(syniq::parse_modulation("16QAM") == syniq::Modulation::QAM16, "parse 16QAM");
    check_throws([&]() { (void)syniq::parse_modulation("64QAM"); }, "parse unknown -> throw");
}

// --- B-vs-C fidelity through the production decimation chain ------------------

// Convert the chain's [2,1024] planar fp32 tensors back to interleaved complex.
std::vector<std::complex<double>> chain_complex_output(chain::PreprocessChain& c) {
    std::vector<std::complex<double>> out;
    std::vector<float> t(chain::kTensorFloats);
    while (c.ready() > 0) {
        c.pull_tensor(t.data());
        for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
            out.emplace_back(static_cast<double>(t[k]),
                             static_cast<double>(t[chain::kFrameComplex + k]));
    }
    return out;
}

struct AlignResult { double nmse; double evm; int offset; double gain_db; };

// Align meas to ref: ref[i] ~ g * meas[i + offset].  The offset may be either
// sign (the decimation chain's transient discard makes its output ADVANCED, not
// delayed, relative to the directly-synthesized reference), so search a symmetric
// window [-max_offset, +max_offset] and take the least-squares best over every
// offset with enough overlap.
AlignResult align_nmse(const std::vector<std::complex<double>>& ref,
                       const std::vector<std::complex<double>>& meas,
                       int max_offset) {
    const std::size_t Lr = ref.size(), Lm = meas.size();
    const int min_overlap = 1024;
    double best = 1e300;
    int best_o = 0;
    double best_g = 0.0;
    for (int o = -max_offset; o <= max_offset; ++o) {
        const int lo = std::max(0, -o);
        const int hi = static_cast<int>(std::min(
            static_cast<long long>(Lr),
            static_cast<long long>(Lm) - static_cast<long long>(o)));
        if (hi - lo < min_overlap) continue;
        std::complex<double> num(0.0, 0.0), den(0.0, 0.0);
        for (int i = lo; i < hi; ++i) {
            const std::complex<double>& r = ref[static_cast<std::size_t>(i)];
            const std::complex<double>& m = meas[static_cast<std::size_t>(i + o)];
            num += r * std::conj(m);
            den += m * std::conj(m);
        }
        if (std::abs(den) < 1e-30) continue;
        const std::complex<double> g = num / den;
        double err = 0.0, refl = 0.0;
        for (int i = lo; i < hi; ++i) {
            const std::complex<double> e =
                ref[static_cast<std::size_t>(i)] -
                g * meas[static_cast<std::size_t>(i + o)];
            err += std::norm(e);
            refl += std::norm(ref[static_cast<std::size_t>(i)]);
        }
        const double nmse = err / refl;
        if (nmse < best) { best = nmse; best_o = o; best_g = std::abs(g); }
    }
    AlignResult r;
    r.nmse = best;
    r.evm = std::sqrt(best);
    r.offset = best_o;
    r.gain_db = 20.0 * std::log10(best_g);
    return r;
}

void test_bc_fidelity_one(syniq::Modulation m, const char* name) {
    const std::uint64_t seed = 0x39e5ULL;
    const int n_sym_b = 1024;   // B reference: 128 kSPS, 8 sps
    const int n_sym_c = 1536;   // C route:   2.56 MSPS, 160 sps (longer -> covers B)

    // B: directly synthesized 128 kSPS steady-state waveform.
    const auto sym_b = syniq::symbol_indices(m, seed, n_sym_b);
    const std::vector<std::complex<double>> b =
        syniq::pulse_shape(sym_b, m, 8, 0.35, 8);

    // C: same seed/symbol stream, 2.56 MSPS, quantized to int16, through the
    // REAL production PreprocessChain (NCO off, rec_scale 1 -> gain absorbed by
    // the alignment).
    const auto sym_c = syniq::symbol_indices(m, seed, n_sym_c);
    const std::vector<std::complex<double>> c =
        syniq::pulse_shape(sym_c, m, 160, 0.35, 8);
    syniq::QuantStats st;
    const std::vector<std::int16_t> iq = syniq::quantize_int16(c, 16.0, st);

    chain::PreprocessChain chain(2560000u, 0.0, 1.0f);
    chain.push_int16(iq.data(), iq.size() / 2);
    const std::vector<std::complex<double>> c_out = chain_complex_output(chain);
    check(c_out.size() >= b.size(), "route C output long enough to cover B reference");

    const AlignResult r = align_nmse(b, c_out, 2048);
    std::printf("  %-6s: nmse=%.3e (%.1f dB)  evm=%.4f%%  offset=%d  gain=%.3f dB\n",
                name, r.nmse, 10.0 * std::log10(r.nmse), r.evm * 100.0, r.offset, r.gain_db);
    check(r.offset >= -2048 && r.offset <= 2048, "route C alignment offset found");
    check(r.nmse < 0.005, "route B vs C (after decimation) NMSE < 0.005");
    check(r.evm < 0.07, "route B vs C EVM < 7%");
}

void test_bc_fidelity() {
    std::printf("  B-vs-C fidelity (2.56M -> 128k decimation chain):\n");
    test_bc_fidelity_one(syniq::Modulation::BPSK, "BPSK");
    test_bc_fidelity_one(syniq::Modulation::QPSK, "QPSK");
    test_bc_fidelity_one(syniq::Modulation::ASK4, "4ASK");
    test_bc_fidelity_one(syniq::Modulation::QAM16, "16QAM");
}

}  // namespace

int main() {
    std::printf("test_synthetic_iq_generator\n");
    test_rrc_properties();
    test_map_symbol_unit_power();
    test_symbol_indices_determinism();
    test_pulse_shape_geometry();
    test_normalization();
    test_quantize_int16();
    test_parse_modulation();
    test_bc_fidelity();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
