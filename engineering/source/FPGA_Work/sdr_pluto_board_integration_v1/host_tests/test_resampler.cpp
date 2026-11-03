// test_resampler.cpp -- host tests for sdr::StreamResampler.
//
//   1. Golden comparison: loads tools/resampler_golden.py reference input+output
//      (same FIR coeffs, numpy float64), runs the streaming resampler, compares.
//   2. Brute-force direct-convolution reference vs streaming (self-contained).
//   3. Chunk-size invariance: chunked push/pull == single-shot, bit-identical.
//   4. Count/transient invariants.
//   5. Anti-aliasing: an out-of-band probe must be suppressed after decimation.
//
// Build: g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter
//        test_resampler.cpp ../sdr_adapter/resampler.cpp

#include "resampler.hpp"
#include "fir_coeffs.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

static constexpr double kPi = 3.141592653589793238462643383279502884;

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond)                                                    \
    do {                                                               \
        if (cond) {                                                    \
            ++g_pass;                                                  \
        } else {                                                       \
            ++g_fail;                                                  \
            std::fprintf(stderr, "FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
        }                                                              \
    } while (0)

template <typename F>
static void run_case(const char* name, F f) {
    std::fprintf(stderr, "-- %s\n", name);
    try {
        f();
    } catch (const std::exception& e) {
        ++g_fail;
        std::fprintf(stderr, "EXCEPTION in %s: %s\n", name, e.what());
    }
}

static std::vector<double> coeff_vec(const sdr::FirSpec& s) {
    return std::vector<double>(s.coeffs, s.coeffs + s.n);
}

static const sdr::FirSpec* find_spec(std::uint32_t fs_in) {
    for (std::size_t i = 0; i < sdr::kFirSpecCount; ++i) {
        if (sdr::kFirSpecs[i].fs_in_hz == fs_in) return &sdr::kFirSpecs[i];
    }
    return nullptr;
}

static std::vector<std::complex<double>> load_cd(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open " + path);
    in.seekg(0, std::ios::end);
    const std::streamoff sz = in.tellg();
    in.seekg(0, std::ios::beg);
    if (sz < 0 || sz % 16 != 0) throw std::runtime_error("bad size " + path);
    const std::size_t n = static_cast<std::size_t>(sz) / 16;
    std::vector<std::complex<double>> v(n);
    double re = 0.0, im = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        in.read(reinterpret_cast<char*>(&re), 8);
        in.read(reinterpret_cast<char*>(&im), 8);
        v[i] = std::complex<double>(re, im);
    }
    return v;
}

static std::vector<std::complex<float>> to_f(const std::vector<std::complex<double>>& x) {
    std::vector<std::complex<float>> v(x.size());
    for (std::size_t i = 0; i < x.size(); ++i)
        v[i] = std::complex<float>(static_cast<float>(x[i].real()),
                                   static_cast<float>(x[i].imag()));
    return v;
}

// brute-force direct-convolution reference (independent of the streaming state).
static std::vector<std::complex<float>> brute_resample(
    const std::vector<std::complex<float>>& x, std::uint32_t up, std::uint32_t down,
    const std::vector<double>& h) {
    const std::size_t n = h.size();
    const std::size_t p = n / up;
    const std::uint64_t m_count = (static_cast<std::uint64_t>(x.size()) * up - 1) / down + 1;
    std::vector<std::complex<float>> y;
    y.reserve(static_cast<std::size_t>(m_count));
    for (std::uint64_t m = 0; m < m_count; ++m) {
        const std::uint64_t i = (m * down) / up;
        const std::uint32_t r = static_cast<std::uint32_t>((m * down) % up);
        std::complex<double> acc(0.0, 0.0);
        for (std::size_t k = 0; k < p; ++k) {
            const double c = h[static_cast<std::size_t>(r) + k * static_cast<std::size_t>(up)];
            const std::int64_t idx = static_cast<std::int64_t>(i) - static_cast<std::int64_t>(k);
            double xr = 0.0, xi = 0.0;
            if (idx >= 0 && idx < static_cast<std::int64_t>(x.size())) {
                xr = x[static_cast<std::size_t>(idx)].real();
                xi = x[static_cast<std::size_t>(idx)].imag();
            }
            acc = std::complex<double>(acc.real() + c * xr, acc.imag() + c * xi);
        }
        if (m >= n - 1)  // discard N-1 transient (same convention)
            y.push_back(std::complex<float>(static_cast<float>(acc.real()),
                                            static_cast<float>(acc.imag())));
    }
    return y;
}

static double goertzel_ratio(const std::vector<std::complex<float>>& x,
                             double f, double fs) {
    const std::size_t n = x.size();
    std::complex<double> acc(0.0, 0.0);
    double total = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        const double ph = 2.0 * kPi * f / fs * static_cast<double>(i);
        const std::complex<double> ref(std::cos(ph), -std::sin(ph));
        const std::complex<double> s(x[i].real(), x[i].imag());
        acc += s * ref;
        total += std::abs(s);
    }
    return std::abs(acc) / (total + 1e-12);
}

// ---- Golden comparison (2.56M + 3.84M) -------------------------------------

static void run_golden_case(std::uint32_t fs_in, const std::string& name,
                            const std::string& dir) {
    const sdr::FirSpec* spec = find_spec(fs_in);
    CHECK(spec != nullptr);
    if (!spec) return;
    auto in_cd = load_cd(dir + "/resampler_" + name + "_input.bin");
    auto out_cd = load_cd(dir + "/resampler_" + name + "_output.bin");
    auto in = to_f(in_cd);

    sdr::StreamResampler rs(spec->up, spec->down, coeff_vec(*spec));
    rs.push(in.data(), in.size());
    const std::size_t n_out = rs.available();
    CHECK(n_out == out_cd.size());

    std::vector<std::complex<float>> out(n_out);
    const std::size_t got = rs.pull(out.data(), n_out);
    CHECK(got == n_out);

    double maxerr = 0.0, sum = 0.0;
    for (std::size_t i = 0; i < n_out; ++i) {
        const double e = std::abs(std::complex<double>(out[i].real(), out[i].imag()) - out_cd[i]);
        sum += e;
        if (e > maxerr) maxerr = e;
    }
    const double meanerr = n_out ? sum / n_out : 0.0;
    CHECK(meanerr < 1e-4);
    CHECK(maxerr < 1e-3);

    CHECK(rs.in_count() == in.size());
    CHECK(rs.out_count() == n_out);
    CHECK(rs.discarded_transient() == spec->n - 1);
}

static void test_golden_2p56M() { run_golden_case(2560000, "2p56M", "golden"); }
static void test_golden_3p84M() { run_golden_case(3840000, "3p84M", "golden"); }

// ---- Brute-force vs streaming ----------------------------------------------

static std::vector<std::complex<float>> make_signal(std::size_t n) {
    std::vector<std::complex<float>> v(n);
    std::uint32_t s = 0x12345678u;
    for (std::size_t i = 0; i < n; ++i) {
        s ^= s << 13; s ^= s >> 17; s ^= s << 5;
        const float noise = (static_cast<float>(s & 0xffff) / 32768.0f - 1.0f) * 0.05f;
        const double t = static_cast<double>(i);
        const double re = 0.5 * std::cos(2.0 * kPi * 10000.0 / 2560000.0 * t) + noise;
        const double im = 0.5 * std::sin(2.0 * kPi * 10000.0 / 2560000.0 * t) - noise;
        v[i] = std::complex<float>(static_cast<float>(re), static_cast<float>(im));
    }
    return v;
}

static void test_brute_force_match() {
    const sdr::FirSpec* spec = find_spec(2560000);
    CHECK(spec != nullptr);
    if (!spec) return;
    auto x = make_signal(40000);
    auto ref = brute_resample(x, spec->up, spec->down, coeff_vec(*spec));

    sdr::StreamResampler rs(spec->up, spec->down, coeff_vec(*spec));
    rs.push(x.data(), x.size());
    CHECK(rs.available() == ref.size());
    std::vector<std::complex<float>> out(ref.size());
    const std::size_t got = rs.pull(out.data(), out.size());
    CHECK(got == ref.size());

    double maxerr = 0.0;
    for (std::size_t i = 0; i < ref.size(); ++i) {
        const double e = std::abs(out[i] - ref[i]);
        if (e > maxerr) maxerr = e;
    }
    CHECK(maxerr < 1e-4);
}

// ---- Chunk-size invariance --------------------------------------------------

static void test_chunk_invariance() {
    const sdr::FirSpec* spec = find_spec(2560000);
    CHECK(spec != nullptr);
    if (!spec) return;
    auto x = make_signal(50000);

    // single-shot
    sdr::StreamResampler r1(spec->up, spec->down, coeff_vec(*spec));
    r1.push(x.data(), x.size());
    std::vector<std::complex<float>> full(r1.available());
    const std::size_t n_full = r1.pull(full.data(), full.size());
    CHECK(n_full == full.size());

    // chunked push/pull
    sdr::StreamResampler r2(spec->up, spec->down, coeff_vec(*spec));
    std::vector<std::complex<float>> chunked;
    chunked.reserve(full.size());
    const std::size_t push_chunks[] = {1, 3, 7, 13, 5, 97, 1000, 2, 11};
    std::size_t pos = 0;
    std::size_t ci = 0;
    std::vector<std::complex<float>> tmp(4096);
    while (pos < x.size()) {
        const std::size_t c = push_chunks[ci++ % (sizeof(push_chunks) / sizeof(push_chunks[0]))];
        const std::size_t take = std::min(c, x.size() - pos);
        r2.push(x.data() + pos, take);
        pos += take;
        std::size_t avail = r2.available();
        while (avail > 0) {
            const std::size_t want = std::min<std::size_t>(avail, tmp.size());
            const std::size_t got = r2.pull(tmp.data(), want);
            chunked.insert(chunked.end(), tmp.begin(), tmp.begin() + got);
            avail = r2.available();
        }
    }
    CHECK(chunked.size() == full.size());
    CHECK(chunked == full);  // bit-identical
    CHECK(r2.out_count() == full.size());
    CHECK(r2.discarded_transient() == spec->n - 1);
}

// ---- Anti-aliasing ----------------------------------------------------------

static void test_anti_alias() {
    const sdr::FirSpec* spec = find_spec(2560000);
    CHECK(spec != nullptr);
    if (!spec) return;
    // canonical multi-tone: 10k (in-band), 30k (in-band), 200k (alias probe)
    const std::size_t n_in = 51200;
    std::vector<std::complex<float>> x(n_in);
    for (std::size_t i = 0; i < n_in; ++i) {
        const double t = static_cast<double>(i);
        const double re = 0.6 * std::cos(2 * kPi * 10000.0 / 2560000.0 * t)
                        + 0.35 * std::cos(2 * kPi * 30000.0 / 2560000.0 * t)
                        + 0.9 * std::cos(2 * kPi * 200000.0 / 2560000.0 * t);
        const double im = 0.6 * std::sin(2 * kPi * 10000.0 / 2560000.0 * t)
                        + 0.35 * std::sin(2 * kPi * 30000.0 / 2560000.0 * t)
                        + 0.9 * std::sin(2 * kPi * 200000.0 / 2560000.0 * t);
        x[i] = std::complex<float>(static_cast<float>(re), static_cast<float>(im));
    }
    sdr::StreamResampler rs(spec->up, spec->down, coeff_vec(*spec));
    rs.push(x.data(), x.size());
    std::vector<std::complex<float>> out(rs.available());
    const std::size_t got = rs.pull(out.data(), out.size());
    CHECK(got == out.size());

    // 200 kHz aliases to |200k - 128k| = 56 kHz at the 128 kHz output rate.
    const double r_pass = goertzel_ratio(out, 10000.0, 128000.0);
    const double r_alias = goertzel_ratio(out, 56000.0, 128000.0);
    CHECK(r_pass > 0.3);       // in-band tone survives
    CHECK(r_alias < 0.01);     // alias probe suppressed >30 dB
}

int main() {
    run_case("Golden2p56M", test_golden_2p56M);
    run_case("Golden3p84M", test_golden_3p84M);
    run_case("BruteForceMatch", test_brute_force_match);
    run_case("ChunkInvariance", test_chunk_invariance);
    run_case("AntiAlias", test_anti_alias);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
