// test_dsp_measure.cpp -- host tests for lightweight DSP parameter measurement
// (39e5 UI v3 M3): raw / spectrum / model-domain per-frame parameters.
//
// dsp_measure.hpp is iCraft-free, header-only; one 1024-point radix-2 FFT per
// frame.  Tests pin the physically-checkable invariants: a bin-aligned tone has
// rms==peak, the correct dBFS, a single occupied bin, the exact spectral
// centroid, high prominence/SNR; AWGN has a flat spectrum (no occupied bin above
// floor+10dB) and low SNR; silence/NaN/empty/clip are handled safely.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../sdr_adapter/dsp_measure.hpp"

#include <cmath>
#include <complex>
#include <cstdio>
#include <random>
#include <vector>

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s\n", what);
    }
}

bool near(double a, double b, double eps = 1e-2) {
    return std::fabs(a - b) <= eps;
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

// (1) bin-aligned tone: raw invariants + exact dBFS + model RMS.
void test_tone_raw_and_model() {
    sdr::DspMeasureConfig c;
    c.sample_rate_hz = kFs;
    c.receiver_scale = 2.0f;
    sdr::DspMeasure m(c);
    const double A = 1000.0;
    const auto x = tone(A, 16000.0);  // 16000/128000*1024 = bin 128 (aligned)
    const auto r = m.measure(x.data(), x.size());

    check(near(r.rms_counts, A, 1.0), "tone rms == A");
    check(near(r.peak_counts, A, 1.0), "tone peak == A");
    check(near(r.papr_db, 0.0, 0.05), "tone PAPR ~ 0 dB");
    check(near(r.power_dbfs, 20.0 * std::log10(A / 2048.0), 0.05), "tone dBFS exact");
    check(near(r.model_rms, A / 2048.0 * 2.0, 1e-4), "model_rms = A/2048*scale");
    check(r.clip_ratio == 0.0, "tone below full scale -> no clip");
    check(!r.nan_inf && r.valid, "tone -> valid, no NaN");
}

// (2) bin-aligned tone: spectrum invariants.
void test_tone_spectrum() {
    sdr::DspMeasure m;
    const auto x = tone(1000.0, 16000.0);
    const auto r = m.measure(x.data(), x.size());

    check(near(r.spectral_centroid_hz, 16000.0, 10.0), "centroid == 16000 Hz");
    check(r.occupied_bins == 1, "single tone -> 1 occupied bin");
    check(r.psd_peak_prominence_db > 40.0, "tone prominence high");
    check(r.snr_est_db > 30.0, "tone SNR high");
}

// (3) two-tone (FSK-like): occupied span covers both, centroid between.
void test_two_tone_span() {
    sdr::DspMeasure m;
    auto x = tone(500.0, 8000.0);
    const auto y = tone(500.0, 24000.0);
    for (std::size_t k = 0; k < kN; ++k) x[k] += y[k];
    const auto r = m.measure(x.data(), x.size());

    check(r.occupied_bins >= 2, "two tones -> >= 2 occupied bins");
    check(r.occupied_bw_hz >= 24000.0 - 8000.0 - 2000.0, "occupied span covers tone gap");
    check(r.spectral_centroid_hz > 8000.0 && r.spectral_centroid_hz < 24000.0,
          "centroid between the two tones");
}

// (4) silence: valid, zero everywhere, no NaN, no clip.
void test_silence() {
    sdr::DspMeasure m;
    std::vector<std::complex<float>> x(kN, std::complex<float>(0.0f, 0.0f));
    const auto r = m.measure(x.data(), x.size());
    check(r.valid, "silence -> valid");
    check(r.rms_counts == 0.0 && r.peak_counts == 0.0, "silence -> zero rms/peak");
    check(r.clip_ratio == 0.0 && !r.nan_inf, "silence -> no clip/NaN");
    check(r.occupied_bins == 0, "silence -> no occupied bins");
}

// (5) empty input -> invalid.
void test_empty() {
    sdr::DspMeasure m;
    const auto r = m.measure(nullptr, 0);
    check(!r.valid, "empty -> invalid");
}

// (6) NaN/Inf input -> nan_inf flag set.
void test_nan_input() {
    sdr::DspMeasure m;
    std::vector<std::complex<float>> x(kN, std::complex<float>(0.0f, 0.0f));
    x[0] = std::complex<float>(std::nanf(""), 0.0f);
    const auto r = m.measure(x.data(), x.size());
    check(r.nan_inf, "NaN input -> nan_inf true");
}

// (7) clip detection: samples at/above full scale count as clipped.
void test_clip_detection() {
    sdr::DspMeasure m;  // clip_level defaults to 2048
    std::vector<std::complex<float>> x(kN, std::complex<float>(100.0f, 0.0f));
    for (std::size_t k = 0; k < 32; ++k)
        x[k] = std::complex<float>(2048.0f, 0.0f);
    const auto r = m.measure(x.data(), x.size());
    check(near(r.clip_ratio, 32.0 / static_cast<double>(kN), 1e-9),
          "clip_ratio == 32/1024");
}

// (8) AWGN (fixed seed): flat spectrum, no occupied bin above floor+15 dB, low SNR.
void test_awgn_flat() {
    // The max of 1024 flat-spectrum bins sits ~10 dB above the median, so use a
    // 15 dB occupancy threshold to show the noise has no true peak.
    sdr::DspMeasureConfig c;
    c.occupied_threshold_db = 15.0;
    sdr::DspMeasure m(c);
    std::mt19937 gen(20261007u);
    std::normal_distribution<double> gauss(0.0, 100.0);  // std=100 -> rms~141
    std::vector<std::complex<float>> x(kN);
    for (std::size_t k = 0; k < kN; ++k)
        x[k] = std::complex<float>(static_cast<float>(gauss(gen)),
                                   static_cast<float>(gauss(gen)));
    const auto r = m.measure(x.data(), x.size());
    check(r.occupied_bins == 0, "AWGN -> no bin exceeds floor + 15 dB");
    check(r.snr_est_db < 6.0, "AWGN -> low SNR estimate");
    check(r.psd_peak_prominence_db < 20.0, "AWGN -> low prominence");
}

}  // namespace

int main() {
    std::printf("test_dsp_measure\n");
    test_tone_raw_and_model();
    test_tone_spectrum();
    test_two_tone_span();
    test_silence();
    test_empty();
    test_nan_input();
    test_clip_detection();
    test_awgn_flat();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
