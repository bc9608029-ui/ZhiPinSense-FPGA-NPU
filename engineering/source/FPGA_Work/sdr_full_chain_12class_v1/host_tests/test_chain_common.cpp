// test_chain_common.cpp -- host tests for the twelve-class SDR->tensor chain
// (board_package/chain_common.hpp).  iCraft-free and libiio-free: it exercises
// the exact code the board runs (PreprocessChain, tensor layout, receiver_scale
// calibration, result-frame filling, tone SNR), using a synthetic int16 CW tone.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../board_package/chain_common.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
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

void check_near(double got, double want, double tol, const char* what) {
    const bool ok = std::fabs(got - want) <= tol;
    if (ok) ++g_pass;
    else {
        ++g_fail;
        std::printf("  FAIL: %s (got %.9g want %.9g tol %.9g)\n", what, got, want, tol);
    }
}

// A deterministic interleaved int16 CW tone at freq_hz/fs_hz.
std::vector<std::int16_t> tone_iq(double freq_hz, double fs_hz, std::size_t n,
                                  double amp = 1500.0) {
    std::vector<std::int16_t> iq(n * 2);
    const double ph = 2.0 * 3.14159265358979323846 * freq_hz / fs_hz;
    for (std::size_t k = 0; k < n; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(amp * std::cos(ph * k)));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::llround(amp * std::sin(ph * k)));
    }
    return iq;
}

void test_contract() {
    const cat::Contract c = chain::contract_12();
    const std::vector<std::string> want = {"OOK", "4ASK", "AM-DSB", "WBFM", "2FSK",
                                           "GFSK", "BPSK", "QPSK", "8PSK", "16QAM",
                                           "64QAM", "OFDM"};
    check(c.class_count == 12, "contract_12 count == 12");
    check(c.class_names == want, "contract_12 order matches frozen 12-class order");
    check(cat::is_valid(c), "contract_12 is_valid");
    check(cat::label(c, 0) == "OOK", "label(0) == OOK");
    check(cat::label(c, 11) == "OFDM", "label(11) == OFDM");
    check(cat::label(c, 12) == "<12>", "label(12) out-of-range");
}

void test_build_tensor() {
    std::vector<std::complex<float>> frame(chain::kFrameComplex);
    for (std::size_t k = 0; k < frame.size(); ++k)
        frame[k] = std::complex<float>(static_cast<float>(k), -static_cast<float>(k));
    std::vector<float> t(chain::kTensorFloats);
    chain::build_tensor(frame.data(), frame.size(), 2.0f, t.data());
    bool ok = true;
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
        if (t[k] != 2.0f * static_cast<float>(k)) ok = false;             // I plane
        if (t[chain::kFrameComplex + k] != -2.0f * static_cast<float>(k)) ok = false;  // Q plane
    }
    check(ok, "build_tensor: I plane then Q plane, x rec_scale");
}

void test_calibrate_rec_scale() {
    // target_rms=1.0, adc_rms_counts=500 -> scale = 1.0*2048/500 = 4.096
    check_near(chain::calibrate_rec_scale(500.0, 1.0), 2048.0 / 500.0, 1e-6,
               "calibrate_rec_scale(500,1.0)");
    check_near(chain::calibrate_rec_scale(0.0, 1.0), 1.0, 1e-9,
               "calibrate_rec_scale(0.0) -> 1.0 (guard)");
}

void test_preprocess_chain() {
    const std::uint32_t fs_in = 2560000;
    chain::PreprocessChain chain(fs_in, 0.0, 1.0f);
    // Feed enough samples to yield >= 1 complete 128 kHz frame after the FIR
    // transient (601 taps -> ~600 output samples discarded).  ~2.6 frames worth.
    const std::size_t n_in = 60000;
    const std::vector<std::int16_t> iq = tone_iq(10000.0, 2560000.0, n_in);
    chain.push_int16(iq.data(), n_in);

    check(chain.ready() >= 1, "preprocess: at least one tensor ready");
    std::vector<float> t(chain::kTensorFloats);
    check(chain.pull_tensor(t.data()), "preprocess: pull first tensor");

    // Reconstruct complex and verify the 10 kHz tone survives at 128 kHz.
    std::vector<std::complex<float>> x(chain::kFrameComplex);
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
        x[k] = std::complex<float>(t[k], t[chain::kFrameComplex + k]);
    const double ratio = sdr::goertzel_ratio(x, 10000.0, 128000.0);
    check(ratio > 0.9, "preprocess: 10 kHz tone present after decimation");
    const double rms = sdr::rms(x);
    check(rms > 0.1, "preprocess: tensor RMS sane (tone not lost)");
    check(chain.resampler_transient() > 0, "preprocess: transient was discarded");
}

void test_fill_result() {
    const cat::Contract c = chain::contract_12();
    std::vector<float> logits(12, 0.0f);
    logits[7] = 5.0f;   // QPSK
    logits[3] = 1.0f;   // WBFM
    rf::ResultFrame r;
    chain::fill_result(r, logits, c, "deadbeef", 12.3);
    check(r.argmax_idx == 7, "fill_result: argmax_idx == 7");
    check(r.argmax_class == "QPSK", "fill_result: argmax_class == QPSK");
    check(r.class_count == 12, "fill_result: class_count == 12");
    check(r.version == "12class-chain-v1", "fill_result: version tag");
    check(r.model_sha == "deadbeef", "fill_result: model_sha");
    check_near(r.snr_db, 12.3, 1e-9, "fill_result: snr_db");
    check(r.probabilities.size() == 12, "fill_result: probabilities width");
    double psum = 0.0;
    for (float p : r.probabilities) psum += static_cast<double>(p);
    check_near(psum, 1.0, 1e-3, "fill_result: probabilities sum ~1");
    check(r.confidence > 0.9f && r.confidence < 1.0f, "fill_result: confidence in (0.9,1)");
    check(!r.mock, "fill_result: mock stays false (caller sets)");
}

void test_tone_snr_db() {
    std::vector<std::complex<float>> tone(1024);
    for (std::size_t k = 0; k < tone.size(); ++k)
        tone[k] = std::complex<float>(std::cos(2.0 * 3.14159265358979323846 * 10000.0 / 128000.0 * k),
                                      std::sin(2.0 * 3.14159265358979323846 * 10000.0 / 128000.0 * k));
    const double snr = chain::tone_snr_db(tone, 10000.0, 128000.0);
    // A float32 pure tone's residual is limited by single-precision rounding
    // (~1e-4), so the diagnostic SNR is ~70 dB here, NOT the float64 120 dB cap.
    // The gate only needs to tell a tone (>> 30 dB) apart from noise (~0 dB).
    check(snr > 40.0, "tone_snr_db: pure tone -> high SNR");
}

}  // namespace

int main() {
    std::printf("test_chain_common\n");
    test_contract();
    test_build_tensor();
    test_calibrate_rec_scale();
    test_preprocess_chain();
    test_fill_result();
    test_tone_snr_db();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
