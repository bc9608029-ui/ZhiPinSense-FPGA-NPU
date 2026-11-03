// test_iq_rf_loopback.cpp -- host tests for Stage H-F / Route F (fix7): the
// PHYSICAL-RF TX->RX self loopback.
//
// Exercises, in order:
//   * measure_rf_fidelity verdict mapping (the RF_PRESERVES_IQ / RF_RX_TOO_LOW /
//     RF_RX_ALL_ZERO / RF_RX_CLIPPED / RF_DISTORTS_IQ tokens), each driven by a
//     different TX/RX/noise-floor combination;
//   * the TX-off NEGATIVE CONTROL (noise floor -> SNR) and its fail-closed role;
//   * estimate_global_gain (median magnitude + circular-mean phase, robust to a
//     magnitude outlier) and apply_complex_gain_to_tensor / apply_global_gain_to_stream
//     (the ONE global calibration gain the classification path is allowed to use);
//   * push_rf_file_summary (fix7 Task A): the retained per-file summary must release
//     the large aligned_rx buffer (empty + capacity 0) so 240 files cannot retain
//     ~51 MiB and trip the M22 RSS-growth gate;
//   * transfer_one_file_rf end-to-end against the FakePlutoDevice RF echo: clean
//     (capture + TX DMA payload SHA + loopback read-back == 0), corrupted TX DMA
//     payload (recorded, not thrown), and a loopback read-back != 0 (throws,
//     fail-closed).
//
// iCraft-free and libiio-free.  The transfer-layer tests link ../sdr_adapter/pluto_tx.cpp
// (the real PlutoTx safety state machine) against the scriptable FakePlutoDevice.

#include "../board_package/iq_rf_loopback.hpp"
#include "../board_package/iq_rf_loopback_transfer.hpp"
#include "../board_package/iq_rf_loopback_report.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

constexpr double kPi = 3.141592653589793238462643383279502884;

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// ---- deterministic waveforms -------------------------------------------------

// ±A pseudo-random I/Q (deterministic LCG, high bits), aperiodic over any P, so
// its circular autocorrelation has a sharp unique peak and I/Q are independent.
std::vector<std::int16_t> make_prbs(std::size_t P, int A, std::uint32_t seed) {
    std::vector<std::int16_t> iq(P * 2);
    std::uint32_t s = seed ? seed : 0x9e3779b9u;
    auto bit = [&s]() -> int {
        s = s * 1664525u + 1013904223u;   // Numerical Recipes LCG
        return static_cast<int>((s >> 24) & 1u);   // high bits: well-distributed
    };
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(bit() ? A : -A);
        iq[k * 2 + 1] = static_cast<std::int16_t>(bit() ? A : -A);
    }
    return iq;
}

// Apply a complex gain g*exp(i*phase) to an interleaved int16 waveform.
std::vector<std::int16_t> apply_gain(const std::vector<std::int16_t>& tx,
                                     double g, double phase_deg) {
    const std::complex<double> a = std::polar(g, phase_deg * kPi / 180.0);
    std::vector<std::int16_t> out(tx.size());
    for (std::size_t k = 0; k + 1 < tx.size(); k += 2) {
        const std::complex<double> y = a * std::complex<double>(tx[k], tx[k + 1]);
        out[k] = static_cast<std::int16_t>(std::llround(y.real()));
        out[k + 1] = static_cast<std::int16_t>(std::llround(y.imag()));
    }
    return out;
}

// Build an interleaved int16 RX capture of `total_complex` samples whose stable
// region (after `transient` garbage samples) is `sig` cyclically shifted by `d`:
//   rx[transient + j] = sig[(j - d) mod P].
std::vector<std::int16_t> make_rx(const std::vector<std::int16_t>& sig,
                                  std::size_t d, std::size_t transient,
                                  std::size_t total_complex) {
    const std::size_t P = sig.size() / 2;
    std::vector<std::int16_t> rx(total_complex * 2, 0);
    for (std::size_t j = 0; j < total_complex; ++j) {
        if (j < transient) {
            rx[j * 2 + 0] = static_cast<std::int16_t>((j * 37 + 11) % 2000 - 1000);
            rx[j * 2 + 1] = static_cast<std::int16_t>((j * 53 + 7) % 2000 - 1000);
        } else {
            const std::size_t src = (j - transient + P - (d % P)) % P;
            rx[j * 2 + 0] = sig[src * 2 + 0];
            rx[j * 2 + 1] = sig[src * 2 + 1];
        }
    }
    return rx;
}

// A zero noise floor: the TX-off negative control reads exactly zero -> SNR = +inf.
std::vector<std::int16_t> make_zero_noise(std::size_t complex_count) {
    return std::vector<std::int16_t>(complex_count * 2, 0);
}

// ---- 1. clean external-RF loopback -> RF_PRESERVES_IQ ----
void test_rf_clean_preserves() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const std::size_t d = 42;
    const double g = 0.8, phase = 30.0;   // physical RF gain + phase (unknown a priori)
    const auto tx = make_prbs(P, 900, 3141);
    const auto sig = apply_gain(tx, g, phase);
    const auto rx = make_rx(sig, d, transient, transient + P);
    const auto noise = make_zero_noise(P);

    const auto m = iqrfloop::measure_rf_fidelity(
        tx, rx, noise, /*noise_capture_ok=*/true, 2560000, 16, 16, transient);
    check(m.sync.corr > 0.999, "rf-clean: corr ~ 1");
    check(m.negative_control_ok, "rf-clean: negative control ok (quiet, unclipped)");
    check(std::isinf(m.snr_db), "rf-clean: snr_db = +inf (zero noise floor)");
    const std::string v = iqrfloop::rf_fidelity_verdict(m);
    check(v == iqrfloop::kRfPreservesIq, "rf-clean: RF_PRESERVES_IQ");
    check(iqrfloop::rf_fidelity_gate_ok(v.c_str()), "rf-clean: fidelity gate ok");
}

// ---- 2. quiet signal vs loud noise floor -> RF_RX_TOO_LOW (SNR judgment) ----
void test_rf_low_snr_too_low() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 100, 5678);   // quiet signal (rms ~ 100)
    const auto rx = make_rx(tx, 0, transient, transient + P);
    const auto noise = make_prbs(P, 2000, 9999);   // loud TX-off noise floor (rms ~ 2000)

    const auto m = iqrfloop::measure_rf_fidelity(
        tx, rx, noise, true, 2560000, 16, 16, transient);
    check(m.sync.corr > 0.999, "rf-low-snr: corr still ~ 1 (clean waveform, quiet RX)");
    check(std::isfinite(m.snr_db) && m.snr_db < iqrfloop::kRfSnrThresholdDb,
          "rf-low-snr: snr_db < 6 dB");
    const std::string v = iqrfloop::rf_fidelity_verdict(m);
    check(v == iqrfloop::kRfRxTooLow, "rf-low-snr: RF_RX_TOO_LOW (signal ~= noise)");
    check(!iqrfloop::rf_fidelity_gate_ok(v.c_str()), "rf-low-snr: gate fails");
}

// ---- 3. all-zero RX -> RF_RX_ALL_ZERO ----
void test_rf_all_zero() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 900, 2468);
    const std::vector<std::int16_t> rx(2 * (transient + P), 0);
    const auto noise = make_zero_noise(P);

    const auto m = iqrfloop::measure_rf_fidelity(
        tx, rx, noise, true, 2560000, 16, 16, transient);
    check(m.sync.rx_all_zero, "rf-all-zero: rx_all_zero");
    const std::string v = iqrfloop::rf_fidelity_verdict(m);
    check(v == iqrfloop::kRfRxAllZero, "rf-all-zero: RF_RX_ALL_ZERO");
}

// ---- 4. railed RX -> RF_RX_CLIPPED ----
void test_rf_clipped() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 3000, 1357);   // peak 3000 >= 2047 (12-bit rail)
    const auto rx = make_rx(tx, 0, transient, transient + P);
    const auto noise = make_zero_noise(P);

    const auto m = iqrfloop::measure_rf_fidelity(
        tx, rx, noise, true, 2560000, 16, 16, transient);
    check(m.sync.clipped, "rf-clipped: clipped flag set");
    const std::string v = iqrfloop::rf_fidelity_verdict(m);
    check(v == iqrfloop::kRfRxClipped, "rf-clipped: RF_RX_CLIPPED");
}

// ---- 5. distorted waveform (corr < 0.9) with a quiet noise floor -> RF_DISTORTS_IQ ----
void test_rf_distorts() {
    const std::size_t P = 1024;
    const std::size_t transient = 16;
    const auto tx = make_prbs(P, 500, 2020);
    const auto other = make_prbs(P, 500, 777);
    std::vector<std::int16_t> sig(tx.size());
    for (std::size_t k = 0; k < tx.size(); ++k)
        sig[k] = static_cast<std::int16_t>(tx[k] + other[k]);   // equal-energy distortion
    const auto rx = make_rx(sig, 0, transient, transient + P);
    const auto noise = make_zero_noise(P);

    const auto m = iqrfloop::measure_rf_fidelity(
        tx, rx, noise, true, 2560000, 16, 16, transient);
    check(m.sync.corr < 0.9 && m.sync.corr > 0.5,
          "rf-distorts: corr ~ 0.707 (below the 0.9 threshold)");
    check(!m.sync.clipped, "rf-distorts: not clipped (amplitude < 2047)");
    const std::string v = iqrfloop::rf_fidelity_verdict(m);
    check(v == iqrfloop::kRfDistortsIq, "rf-distorts: RF_DISTORTS_IQ");
}

// ---- 6. global gain estimation (median magnitude + circular-mean phase) ----
void test_estimate_global_gain() {
    const std::vector<std::complex<double>> gains = {
        std::polar(0.5, 10.0 * kPi / 180.0),
        std::polar(0.5, 14.0 * kPi / 180.0),
        std::polar(0.5, 6.0 * kPi / 180.0),
    };
    const auto g = iqrfloop::estimate_global_gain(gains);
    check(g.valid, "global-gain: valid");
    check(g.count == 3, "global-gain: count == 3");
    check(std::fabs(g.mag - 0.5) < 1e-9, "global-gain: median magnitude == 0.5");
    check(std::fabs(g.phase_deg - 10.0) < 0.5, "global-gain: circular-mean phase ~ 10 deg");
    check(std::fabs(g.k_mag - 2.0) < 1e-9, "global-gain: k_mag == 2.0");
    check(std::fabs(g.k_phase_deg + 10.0) < 0.5, "global-gain: k_phase_deg == -10 deg");

    // A magnitude outlier must not move the median (robustness to one bad file).
    const std::vector<std::complex<double>> outlier = {
        std::polar(0.5, 20.0 * kPi / 180.0),
        std::polar(100.0, 20.0 * kPi / 180.0),
        std::polar(0.5, 20.0 * kPi / 180.0),
    };
    const auto g2 = iqrfloop::estimate_global_gain(outlier);
    check(g2.valid && std::fabs(g2.mag - 0.5) < 1e-9,
          "global-gain: median ignores a 100x magnitude outlier");
    check(std::fabs(g2.phase_deg - 20.0) < 0.5, "global-gain: outlier phase preserved");

    // No gains -> invalid (never a fabricated gain).
    const auto g3 = iqrfloop::estimate_global_gain({});
    check(!g3.valid, "global-gain: empty -> invalid");
}

// ---- 7. applying the global gain (rotation + scale) ----
void test_apply_complex_gain_to_tensor() {
    float t[2] = {1.0f, 0.0f};   // I=1, Q=0
    iqrfloop::apply_complex_gain_to_tensor(t, 1, 1.0, 90.0);
    check(std::fabs(t[0]) < 1e-4 && std::fabs(t[1] - 1.0) < 1e-4,
          "apply-gain: +90 deg rotates [1,0] -> [0,1]");

    float t2[2] = {1.0f, 2.0f};
    iqrfloop::apply_complex_gain_to_tensor(t2, 1, 2.0, 0.0);
    check(std::fabs(t2[0] - 2.0) < 1e-4 && std::fabs(t2[1] - 4.0) < 1e-4,
          "apply-gain: x2 scales I and Q");
}

void test_apply_global_gain_to_stream() {
    const std::size_t fc = 2;   // frame_complex = 2 -> each frame = 4 floats
    std::vector<float> s = {1, 2, 3, 4, 5, 6, 7, 8};   // two frames
    iqrfloop::RfGlobalGain g;
    g.valid = true;
    g.k_mag = 2.0;
    g.k_phase_deg = 0.0;
    iqrfloop::apply_global_gain_to_stream(s, fc, g);
    bool ok = true;
    for (std::size_t k = 0; k < s.size(); ++k)
        if (std::fabs(s[k] - 2.0 * static_cast<double>(k + 1)) > 1e-4) ok = false;
    check(ok, "apply-stream: every sample of both frames doubled");

    // Invalid gain -> no-op (never applies a fabricated correction).
    std::vector<float> s2 = {1, 2, 3, 4};
    iqrfloop::RfGlobalGain g_bad;
    g_bad.valid = false;
    iqrfloop::apply_global_gain_to_stream(s2, 2, g_bad);
    check(s2[0] == 1.0f && s2[3] == 4.0f, "apply-stream: invalid gain is a no-op");
}

// ---- 8. fix7 Task A: the summary sink releases aligned_rx ----
void test_push_rf_file_summary_releases_aligned_rx() {
    std::vector<iqrfloop_run::RfPerFileResult> files;
    iqrfloop_run::RfPerFileResult pf;
    pf.file_name = "frozen_000.ci16";
    pf.frames = 4;
    pf.correct = 2;
    pf.source_class = 3;
    pf.deployed_class = 3;
    pf.rf.sync.aligned_rx = make_prbs(4096, 500, 1234);   // 8192 int16 (~16 KiB)
    check(pf.rf.sync.aligned_rx.capacity() > 0,
          "push: aligned_rx has capacity before push");

    iqrfloop_run::push_rf_file_summary(files, std::move(pf));
    check(files.size() == 1, "push: one file retained");
    check(files[0].file_name == "frozen_000.ci16", "push: scalar file_name retained");
    check(files[0].frames == 4 && files[0].correct == 2, "push: scalar counts retained");
    check(files[0].source_class == 3 && files[0].deployed_class == 3,
          "push: scalar class ids retained");
    check(files[0].rf.sync.aligned_rx.empty() && files[0].rf.sync.aligned_rx.capacity() == 0,
          "push: aligned_rx released (empty + capacity 0)");
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

std::string write_frozen_file(const std::string& dir, const std::string& name,
                              const std::vector<std::int16_t>& iq) {
    const std::string path = dir + "/" + name;
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
    return path;
}

pluto::DataFormatInfo identity_tx_fmt() {
    pluto::DataFormatInfo f;
    f.length_bits = 16;
    f.bits = 16;
    f.shift = 0;
    f.is_signed = true;
    f.is_fully_defined = true;
    return f;
}
#endif

// ---- 9. transfer_one_file_rf end-to-end (clean external-RF path) ----
void run_transfer_clean() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_rf_transfer_clean");
    const auto iq = make_prbs(N, 900, 3);
    const std::string path = write_frozen_file(dir, "rf.ci16", iq);
    const std::string sha = sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 1.0;
    dev.rf_phase_deg = 0.0;
    dev.rf_delay = 0;
    dev.rf_noise_rms = 0.0;   // quiet negative control
    dev.tx_fmt_ = idfmt;      // identity -> TX DMA payload SHA == frozen SHA

    const auto tr = iqrfloop_run::transfer_one_file_rf(
        dev, path, N, sha, 2400000000ULL, 10.0, -40.0, /*delay_margin=*/16384,
        /*tx_complex_cap=*/0, /*noise_complex=*/4096, nullptr, idfmt, idfmt);
    check(tr.capture_ok, "transfer-clean: capture_ok");
    check(tr.tx_verify.sha256 == sha, "transfer-clean: tx_verify.sha256 == frozen SHA");
    check(tr.tx_dma_payload_ok, "transfer-clean: tx_dma_payload_ok");
    check(tr.tx_dma_payload_sha == sha, "transfer-clean: tx_dma_payload_sha == frozen SHA");
    check(tr.loopback_readback == 0, "transfer-clean: loopback read-back == 0");
    check(tr.noise_capture_ok, "transfer-clean: TX-off negative control captured");
    check(!tr.refills.empty(), "transfer-clean: refill evidence present");

    // Full fidelity on the captured TX/RX/noise (mirrors the runner's measure).
    const auto m = iqrfloop::measure_rf_fidelity(
        tr.tx, tr.rx, tr.noise, tr.noise_capture_ok, iqdloop::kFrozenFsIn, 16, 16,
        iqdloop_sync::kTransientDiscardComplex);
    check(m.sync.corr > 0.99, "transfer-clean: corr ~ 1 through the device RF echo");
    const std::string v = iqrfloop::rf_fidelity_verdict(m);
    check(v == iqrfloop::kRfPreservesIq, "transfer-clean: RF_PRESERVES_IQ");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 10. corrupted TX DMA payload is recorded (not thrown) -> runner gates ----
void run_transfer_corrupt_dma() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_rf_transfer_dma");
    const auto iq = make_prbs(N, 900, 4);
    const std::string path = write_frozen_file(dir, "rf.ci16", iq);
    const std::string sha = sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 1.0;
    dev.rf_noise_rms = 0.0;
    dev.tx_fmt_ = idfmt;
    dev.corrupt_tx_dma_payload = true;

    const auto tr = iqrfloop_run::transfer_one_file_rf(
        dev, path, N, sha, 2400000000ULL, 10.0, -40.0, 16384, 0, 4096, nullptr,
        idfmt, idfmt);
    check(!tr.tx_dma_payload_ok, "transfer-dma: corrupted payload -> !tx_dma_payload_ok");
    check(tr.tx_dma_payload_sha != sha, "transfer-dma: payload SHA differs from frozen SHA");
    check(tr.tx_dma_payload_sha != tr.tx_verify.sha256,
          "transfer-dma: payload SHA differs from the verified (pre-DMA) SHA");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 11. loopback read-back != 0 throws (fail-closed external-RF gate) ----
void run_transfer_loopback_readback_throw() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_rf_transfer_lb");
    const auto iq = make_prbs(N, 900, 5);
    const std::string path = write_frozen_file(dir, "rf.ci16", iq);
    const std::string sha = sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.tx_fmt_ = idfmt;
    // A device that silently ignored set_loopback(0): get_loopback() reports 1 even
    // though set_loopback() returned 0.  The RF transfer must throw (fail-closed).
    dev.loopback_readback_override = 1;

    bool threw = false;
    try {
        iqrfloop_run::transfer_one_file_rf(
            dev, path, N, sha, 2400000000ULL, 10.0, -40.0, 16384, 0, 4096, nullptr,
            idfmt, idfmt);
    } catch (const std::exception&) {
        threw = true;
    }
    check(threw, "transfer-loopback: loopback read-back != 0 throws (fail-closed)");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

}  // namespace

int main() {
    std::printf("test_iq_rf_loopback\n");
    test_rf_clean_preserves();
    test_rf_low_snr_too_low();
    test_rf_all_zero();
    test_rf_clipped();
    test_rf_distorts();
    test_estimate_global_gain();
    test_apply_complex_gain_to_tensor();
    test_apply_global_gain_to_stream();
    test_push_rf_file_summary_releases_aligned_rx();
    run_transfer_clean();
    run_transfer_corrupt_dma();
    run_transfer_loopback_readback_throw();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
