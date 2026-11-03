// test_waterfall_spectrum.cpp -- host tests for the display-spectrum derivation
// (fix10class24-waterfall1, Phase B).
//
// The 256-bin display spectrum is derived from the SAME 1024-pt FFT power that
// dsp_measure.hpp already computes -- there is NO second FFT.  These tests pin:
//   * the fftshift direction (display bin 0 = -fs/2, bin 128 = DC, bin 255 =
//     +fs/2), by checking where a positive and a negative bin-aligned tone land;
//   * group-of-4 MAX (not average), by checking a single tone's display value
//     against the max-power formula;
//   * exact agreement with an independently-computed fftshift + group-MAX
//     reference (which is the Python reference, re-expressed in C++);
//   * dBFS x4 range [-480,0] and the fail-closed invalid flag for non-1024 input.
//
// Build/run: see host_tests/build_host_tests.sh (g++ -O2 -Wall -Wextra -Werror).

#include "../sdr_adapter/dsp_measure.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <random>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

constexpr double kFs = 128000.0;
constexpr std::size_t kN = 1024;

std::vector<std::complex<float>> tone(double A, double f) {
    std::vector<std::complex<float>> x(kN);
    for (std::size_t k = 0; k < kN; ++k) {
        const double ph = 2.0 * sdr::kPiMeasure * f / kFs * static_cast<double>(k);
        x[k] = std::complex<float>(static_cast<float>(A * std::cos(ph)),
                                   static_cast<float>(A * std::sin(ph)));
    }
    return x;
}

// Independent reference: one FFT, fftshift, group-of-4 MAX, dBFS x4.  This is the
// derivation the display spectrum MUST equal bit-for-bit (no second FFT).
void reference_display(const std::complex<float>* iq, std::size_t n,
                       double full_scale, int out[256]) {
    std::vector<std::complex<double>> x(n);
    for (std::size_t k = 0; k < n; ++k)
        x[k] = std::complex<double>(iq[k].real(), iq[k].imag());
    sdr::fft_radix2(x.data(), n);
    const double inv_n2 = 1.0 / (static_cast<double>(n) * static_cast<double>(n));
    const double ref = full_scale * full_scale;
    for (int b = 0; b < 256; ++b) {
        double maxp = 0.0;
        for (int j = 0; j < 4; ++j) {
            const std::size_t k =
                (static_cast<std::size_t>(b * 4 + j) + (n / 2)) % n;
            maxp = std::max(maxp, std::norm(x[k]) * inv_n2);
        }
        double dbfs = (maxp > 0.0) ? 10.0 * std::log10(maxp / ref) : -120.0;
        if (dbfs < -120.0) dbfs = -120.0;
        if (dbfs > 0.0) dbfs = 0.0;
        const int x4 = static_cast<int>(std::lround(dbfs * 4.0));
        out[b] = (x4 < -480) ? -480 : (x4 > 0 ? 0 : x4);
    }
}

int argmax_display(const sdr::FrameMeasurements& m) {
    int best = 0;
    for (int b = 1; b < 256; ++b)
        if (m.spectrum_dbfs_x4[b] > m.spectrum_dbfs_x4[best]) best = b;
    return best;
}

// (1) valid 1024-pt input -> spectrum_valid + full metadata.
void test_metadata() {
    sdr::DspMeasureConfig c;
    c.sample_rate_hz = kFs;
    c.center_hz = 2400000000.0;
    sdr::DspMeasure m(c);
    const auto x = tone(1000.0, 16000.0);
    const auto r = m.measure(x.data(), x.size());

    check(r.spectrum_valid, "1024-pt -> spectrum_valid true");
    check(r.spectrum_bin_count == 256, "bin_count == 256");
    check(r.spectrum_fft_length == 1024, "fft_length == 1024");
    check(r.spectrum_sample_rate_hz == kFs, "sample_rate copied");
    check(r.spectrum_center_hz == 2400000000.0, "center_hz copied");
}

// (2) every bin value is an integer dBFS*4 in [-480, 0].
void test_range() {
    sdr::DspMeasure m;
    const auto x = tone(1000.0, 16000.0);
    const auto r = m.measure(x.data(), x.size());
    bool ok = true;
    for (int b = 0; b < 256; ++b)
        if (r.spectrum_dbfs_x4[b] < -480 || r.spectrum_dbfs_x4[b] > 0) ok = false;
    check(ok, "all 256 display bins in [-480, 0]");
}

// (3) exact agreement with the independent fftshift + group-MAX reference (tone).
void test_reference_tone() {
    sdr::DspMeasure m;
    const auto x = tone(1000.0, 16000.0);
    const auto r = m.measure(x.data(), x.size());
    int ref[256];
    reference_display(x.data(), x.size(), 2048.0, ref);
    bool ok = true;
    for (int b = 0; b < 256; ++b)
        if (r.spectrum_dbfs_x4[b] != ref[b]) { ok = false; break; }
    check(ok, "display spectrum == fftshift+group-MAX reference (tone)");
}

// (4) exact agreement with the reference on AWGN (flat spectrum).
void test_reference_awgn() {
    sdr::DspMeasure m;
    std::mt19937 gen(20261018u);
    std::normal_distribution<double> gauss(0.0, 100.0);
    std::vector<std::complex<float>> x(kN);
    for (std::size_t k = 0; k < kN; ++k)
        x[k] = std::complex<float>(static_cast<float>(gauss(gen)),
                                   static_cast<float>(gauss(gen)));
    const auto r = m.measure(x.data(), x.size());
    int ref[256];
    reference_display(x.data(), x.size(), 2048.0, ref);
    bool ok = true;
    for (int b = 0; b < 256; ++b)
        if (r.spectrum_dbfs_x4[b] != ref[b]) { ok = false; break; }
    check(ok, "display spectrum == fftshift+group-MAX reference (AWGN)");
}

// (5) fftshift direction: a positive-frequency tone (bin 128 = +16000 Hz) peaks at
// display bin 128 + 32 = 160 (DC sits at display bin 128).
void test_positive_direction() {
    sdr::DspMeasure m;
    const auto x = tone(1000.0, 16000.0);
    const auto r = m.measure(x.data(), x.size());
    check(argmax_display(r) == 160, "positive tone peaks at display bin 160");
}

// (6) fftshift direction: a negative-frequency tone (bin 896 = -16000 Hz) peaks at
// display bin 128 - 32 = 96.
void test_negative_direction() {
    sdr::DspMeasure m;
    // f = -16000 Hz == bin 896 for the negative-exponent forward FFT.
    const auto x = tone(1000.0, -16000.0);
    const auto r = m.measure(x.data(), x.size());
    check(argmax_display(r) == 96, "negative tone peaks at display bin 96");
}

// (7) group-of-4 MAX, not average: a single bin-aligned COMPLEX tone's display
// value equals 10*log10(A^2/full_scale^2)*4 (single-sided peak power A^2), NOT
// the 4-bin average A^2/4 (which would read 6.02 dB lower).
void test_max_not_average() {
    sdr::DspMeasure m;
    const double A = 1000.0;
    const auto x = tone(A, 16000.0);
    const auto r = m.measure(x.data(), x.size());

    const double power = A * A;  // |X|^2/n^2 for a bin-aligned complex exponential
    const double ref_full = 2048.0 * 2048.0;
    const int expect_max =
        static_cast<int>(std::lround(std::max(-120.0, std::min(0.0,
            10.0 * std::log10(power / ref_full))) * 4.0));
    const int expect_avg =
        static_cast<int>(std::lround(std::max(-120.0, std::min(0.0,
            10.0 * std::log10((power / 4.0) / ref_full))) * 4.0));
    check(r.spectrum_dbfs_x4[160] == expect_max,
          "tone display value uses group MAX power (not average)");
    check(r.spectrum_dbfs_x4[160] != expect_avg,
          "display value is NOT the 4-bin average (6.02 dB lower)");
}

// (8) non-1024 input -> spectrum_valid false (legacy sizes never fake a spectrum).
void test_non_1024_invalid() {
    sdr::DspMeasure m;
    std::vector<std::complex<float>> x(512, std::complex<float>(1.0f, 0.0f));
    const auto r = m.measure(x.data(), x.size());
    check(!r.spectrum_valid, "512-pt input -> spectrum_valid false");
}

}  // namespace

int main() {
    std::printf("test_waterfall_spectrum\n");
    test_metadata();
    test_range();
    test_reference_tone();
    test_reference_awgn();
    test_positive_direction();
    test_negative_direction();
    test_max_not_average();
    test_non_1024_invalid();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
