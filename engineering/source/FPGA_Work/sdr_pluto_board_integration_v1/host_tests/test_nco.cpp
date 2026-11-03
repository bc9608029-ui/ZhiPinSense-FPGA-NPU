// test_nco.cpp -- host tests for sdr::Nco (digital down-conversion).
// No iCraft / SDR / board.  Build: g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter

#include "nco.hpp"

#include <cmath>
#include <complex>
#include <cstdio>
#include <vector>

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

static std::vector<std::complex<float>> tone(double f, double fs, std::size_t n) {
    std::vector<std::complex<float>> v(n);
    for (std::size_t i = 0; i < n; ++i) {
        const double a = 2.0 * sdr::kPi * f / fs * static_cast<double>(i);
        v[i] = std::complex<float>(static_cast<float>(std::cos(a)),
                                   static_cast<float>(std::sin(a)));
    }
    return v;
}

// single-bin Goertzel energy ratio at frequency f (avoids FFT).
static double goertzel_ratio(const std::vector<std::complex<float>>& x,
                             double f, double fs) {
    const std::size_t n = x.size();
    std::complex<double> acc(0.0, 0.0);
    double total = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        const double ph = 2.0 * sdr::kPi * f / fs * static_cast<double>(i);
        const std::complex<double> ref(std::cos(ph), -std::sin(ph));
        const std::complex<double> s(x[i].real(), x[i].imag());
        acc += s * ref;
        total += std::abs(s);
    }
    return std::abs(acc) / (total + 1e-12);
}

static void test_downconvert_to_dc() {
    const double fs = 128000.0, f = 12345.0;
    const std::size_t n = 4096;
    auto x = tone(f, fs, n);
    sdr::Nco nco(f, fs);
    nco.mix(x.data(), n);
    // x[n] = exp(j*2pi*f/fs*n) * exp(-j*2pi*f/fs*n) = 1 + 0j
    double maxerr = 0.0;
    for (const auto& s : x) {
        const double e = std::abs(s - std::complex<float>(1.0f, 0.0f));
        if (e > maxerr) maxerr = e;
    }
    CHECK(maxerr < 1e-3);
    CHECK(nco.phase_samples() == n);
}

static void test_phase_continuity() {
    const double fs = 128000.0, f = 25000.0;
    const std::size_t a = 100, b = 100;
    auto all = tone(f, fs, a + b);

    // one NCO, two buffers
    sdr::Nco n1(f, fs);
    std::vector<std::complex<float>> partA(a), partB(b);
    std::copy(all.begin(), all.begin() + a, partA.begin());
    std::copy(all.begin() + a, all.end(), partB.begin());
    n1.mix(partA.data(), a);
    n1.mix(partB.data(), b);

    // fresh NCO, single buffer
    sdr::Nco n2(f, fs);
    n2.mix(all.data(), a + b);

    // partB must equal the second half of all
    bool same = true;
    for (std::size_t i = 0; i < b; ++i) {
        if (partB[i] != all[a + i]) { same = false; break; }
    }
    CHECK(same);
    CHECK(n1.phase_samples() == a + b);
}

static void test_residual_frequency() {
    const double fs = 128000.0, f0 = 50000.0, f1 = 10000.0;
    auto x = tone(f0 + f1, fs, 8192);
    sdr::Nco nco(f0, fs);
    nco.mix(x.data(), x.size());
    // residual should be a tone at f1 (10 kHz), not at f1+2000 (12 kHz)
    const double r_f1 = goertzel_ratio(x, f1, fs);
    const double r_off = goertzel_ratio(x, f1 + 2000.0, fs);
    CHECK(r_f1 > 0.9);          // strong tone at the residual frequency
    CHECK(r_off < 0.1);         // and not elsewhere
}

static void test_reset() {
    sdr::Nco nco(10000.0, 128000.0);
    auto x = tone(10000.0, 128000.0, 100);
    nco.mix(x.data(), x.size());
    CHECK(nco.phase_samples() == 100);
    nco.reset();
    CHECK(nco.phase_samples() == 0);
    CHECK(nco.phase() == 0.0);
}

int main() {
    run_case("DownconvertToDC", test_downconvert_to_dc);
    run_case("PhaseContinuity", test_phase_continuity);
    run_case("ResidualFrequency", test_residual_frequency);
    run_case("Reset", test_reset);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
