// test_iq_dual_sdr_fix10.cpp -- fix10 Path A/C host test: the DUAL-SDR transfer
// (iq_dual_sdr_transfer_fix10.hpp) driven end-to-end through two DISTINCT fake devices
// (FakeTxDevice / FakeRxDevice) connected only by a shared FakeRfLink air interface.
//
// It proves, without libiio or a board:
//   * the role-split safety sequence (TX atten / RX gain / LO align / loopback off) and
//     its fail-closed read-back / ceiling behaviour;
//   * the cross-device negative control (TX-off noise read from rx_dev, never tx_dev);
//   * the shared-air-link channel model (gain/phase/CFO/SRO/delay/noise) is the EXACT
//     inverse of the fix9r2h2 recovery core (iq_rf_sync_recovery.hpp): estimate() turns
//     valid and apply() recovers the payload within the 5% scale-error contract;
//   * the two-DeviceStateGuard restore (tx_restore_ok / rx_restore_ok).
//
// iCraft-free and libiio-free.

#include "../board_package/iq_dual_sdr_transfer_fix10.hpp"
#include "../board_package/iq_rf_sync_recovery.hpp"
#include "../sdr_adapter/pluto_dual_air_link.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <memory>
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

// ---- shared fixtures --------------------------------------------------------

// Two distinct fake devices over one shared air link; identity TX/RX data format so
// tx_dma_payload_sha() equals the burst SHA (proving the DMA carried the exact bytes).
struct Fixture {
    std::shared_ptr<pluto::FakeRfLink> link;
    pluto::FakeTxDevice tx;
    pluto::FakeRxDevice rx;
    Fixture()
        : link(std::make_shared<pluto::FakeRfLink>()), tx(link), rx(link) {
        const pluto::DataFormatInfo ident{16, 16, 0, true, true, false, 1};
        tx.tx_fmt_ = ident;
        rx.rx_fmt_ = ident;
        tx.open();
        rx.open();
        tx.set_sample_rate(2560000);
        rx.set_sample_rate(2560000);
    }
};

// Band-limited QPSK payload (32 samples/symbol, component RMS ~= 2048).  apply()'s
// SRO correction is a linear (fractional-delay) resampler, which is exact only for a
// band-limited signal; a white-noise payload would lose ~sqrt(2) of power under that
// interpolation and falsely read a large scale error.  The real D2 payload is a
// modulated (band-limited) waveform, so this is the representative case.
std::vector<std::int16_t> make_payload(std::size_t n_complex, std::uint32_t seed) {
    const std::size_t sps = 32;        // samples per symbol
    const double amp = 2048.0;         // component RMS (matches payload-domain training)
    std::vector<std::int16_t> iq(n_complex * 2);
    std::uint32_t s = seed;
    for (std::size_t m = 0; m < n_complex; m += sps) {
        s = s * 1664525u + 1013904223u;
        const int bi = ((s >> 16) & 1u) ? 1 : -1;
        s = s * 1664525u + 1013904223u;
        const int bq = ((s >> 16) & 1u) ? 1 : -1;
        const std::int16_t I = static_cast<std::int16_t>(std::lround(amp * bi));
        const std::int16_t Q = static_cast<std::int16_t>(std::lround(amp * bq));
        for (std::size_t j = 0; j < sps && m + j < n_complex; ++j) {
            iq[(m + j) * 2 + 0] = I;
            iq[(m + j) * 2 + 1] = Q;
        }
    }
    return iq;
}

void write_binary(const std::string& path, const std::vector<std::int16_t>& iq) {
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
}

std::string sha_of(const std::vector<std::int16_t>& iq) {
    return sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
}

struct RunOutcome {
    bool threw = false;
    std::string err;
    iqdual_run_fix10::DualSdrTransferResult r;
};

RunOutcome run_transfer(pluto::FakeTxDevice& tx, pluto::FakeRxDevice& rx,
                        const std::string& path, std::uint64_t complex_count,
                        const std::string& expect_sha, std::uint64_t center_hz,
                        double rx_gain_db, double tx_atten_db,
                        std::size_t delay_margin, std::size_t noise_complex,
                        double target_rms) {
    RunOutcome o;
    try {
        o.r = iqdual_run_fix10::transfer_one_file_dual_sdr_fix10(
            tx, rx, path, complex_count, expect_sha, center_hz, rx_gain_db,
            tx_atten_db, delay_margin, noise_complex, nullptr, target_rms);
    } catch (const std::exception& e) {
        o.threw = true;
        o.err = e.what();
    }
    return o;
}

// Per-complex-sample RMS scale error between the recovered payload and the original
// interleaved int16 payload (same domain, so a perfect recovery reads 0).
double scale_error(const std::vector<std::complex<double>>& rec,
                   const std::vector<std::int16_t>& orig) {
    double e_r = 0.0, e_o = 0.0;
    const std::size_t n = rec.size();
    for (std::size_t k = 0; k < n; ++k) {
        e_r += rec[k].real() * rec[k].real() + rec[k].imag() * rec[k].imag();
        const double I = static_cast<double>(orig[2 * k]);
        const double Q = static_cast<double>(orig[2 * k + 1]);
        e_o += I * I + Q * Q;
    }
    if (n == 0 || e_o == 0.0) return 0.0;
    const double rms_r = std::sqrt(e_r / static_cast<double>(n));
    const double rms_o = std::sqrt(e_o / static_cast<double>(n));
    return std::fabs(rms_r / rms_o - 1.0);
}

// Complex correlation between the recovered payload and the original: ~1 means both
// magnitude AND phase are recovered (a wrong constant phase would lower it).  This is
// the meaningful phase check -- rec.payload_phase_deg instead includes the absolute
// CFO phase at the preamble peak, an arbitrary capture-start-dependent value that
// apply() cancels via a_inv = conj(a_pay)/|a_pay|^2.
double complex_corr(const std::vector<std::complex<double>>& rec,
                    const std::vector<std::int16_t>& orig) {
    std::complex<double> num(0.0, 0.0);
    double den_r = 0.0, den_o = 0.0;
    const std::size_t n = rec.size();
    for (std::size_t k = 0; k < n; ++k) {
        const std::complex<double> o(static_cast<double>(orig[2 * k]),
                                     static_cast<double>(orig[2 * k + 1]));
        num += rec[k] * std::conj(o);
        den_r += rec[k].real() * rec[k].real() + rec[k].imag() * rec[k].imag();
        den_o += o.real() * o.real() + o.imag() * o.imag();
    }
    return den_r > 0.0 && den_o > 0.0 ? std::abs(num) / std::sqrt(den_r * den_o) : 0.0;
}

// Run the fix9r2h2 recovery on the captured int16 and return (valid, scale_error,
// complex correlation).  Mirrors the runner (N3): estimate -> set payload_tx_scale =
// tx_scale -> apply.
void recover(const iqdual_run_fix10::DualSdrTransferResult& r,
             const std::vector<std::int16_t>& orig,
             bool& valid, double& err, double& corr, iqrfrec::PerFileRecovery& rec) {
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(r.rx);
    rec = iqrfrec::estimate(rx);
    rec.payload_tx_scale = r.tx_scale;   // 1.0 when target_rms == 0
    valid = rec.valid;
    err = 1e9;
    corr = 0.0;
    if (valid) {
        const std::vector<std::complex<double>> out = iqrfrec::apply(rx, rec);
        err = scale_error(out, orig);
        corr = complex_corr(out, orig);
    }
}

const std::uint64_t kCenter = 2400000000;
const double kRxGain = 10.0;
const double kAtten = -40.0;

// ---- tests ------------------------------------------------------------------

// Clean, impairment-free dual-SDR transfer: signal == cyclic burst, gain 1, no noise.
void test_clean_transfer(const std::string& path, std::uint64_t cc,
                         const std::string& sha, const std::vector<std::int16_t>& payload) {
    Fixture fx;
    const std::size_t margin = iqdual_run_fix10::kFix10DelayMarginDefault;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                margin, iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "clean: transfer succeeds (" + o.err + ")");
    if (o.threw) return;
    const auto& r = o.r;
    check(r.capture_ok, "clean: capture_ok (single contiguous refill)");
    check(r.tx_dma_payload_ok, "clean: tx_dma_payload_ok (DMA SHA == burst SHA)");
    check(r.frame_verify.ok, "clean: TX frame verifier ok");
    check(r.tx_stopped_readback, "clean: negative control TX stopped (read-back)");
    check(r.noise_stable, "clean: TX-off noise floor stable (all-zero)");
    check(r.tx_loopback_readback == 0 && r.rx_loopback_readback == 0,
          "clean: loopback off on both devices");
    check(r.tx_restore_ok && r.rx_restore_ok, "clean: both guards restored");
    check(r.rx_gain_mode_before_capture == "manual", "clean: RX gain mode manual");
    check(fx.link->tx_start_count == 1, "clean: tx_start_count == 1");
    check(fx.link->main_rx_samples_requested == iqrflayout::capture_complex(margin),
          "clean: main capture request == capture_complex(margin)");
    check(!fx.link->tx_running, "clean: TX stopped after transfer (TxStopGuard)");

    bool valid = false;
    double err = 1e9;
    double corr = 0.0;
    iqrfrec::PerFileRecovery rec;
    recover(r, payload, valid, err, corr, rec);
    check(valid, "clean: recovery valid");
    check(err <= 0.01, "clean: recovered payload scale error <= 1% (got " +
                       std::to_string(err) + ")");
}

// Full impairment channel: the recovery must invert gain/phase/CFO/SRO/delay/noise.
void test_channel_inversion(const std::string& path, std::uint64_t cc,
                            const std::string& sha, const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->gain = 0.8;
    fx.link->phase_deg = 30.0;
    fx.link->cfo_hz = 8.0;
    fx.link->sro_ppm = 20.0;
    fx.link->timing_offset = 300;
    fx.link->noise_rms = 5.0;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "channel: transfer succeeds (" + o.err + ")");
    if (o.threw) return;
    bool valid = false;
    double err = 1e9;
    double corr = 0.0;
    iqrfrec::PerFileRecovery rec;
    recover(o.r, payload, valid, err, corr, rec);
    check(valid, "channel: recovery valid");
    check(std::fabs(rec.payload_gain_mag - 0.8) <= 0.04,
          "channel: payload gain ~0.8 (got " + std::to_string(rec.payload_gain_mag) + ")");
    // rec.payload_phase_deg includes the absolute CFO phase at the preamble peak (an
    // arbitrary, capture-start-dependent value) which apply() cancels via a_inv; the
    // meaningful phase check is the recovered payload's complex correlation ~ 1 below.
    check(std::fabs(rec.cfo_hz - 8.0) <= 3.0,
          "channel: CFO ~8 Hz (got " + std::to_string(rec.cfo_hz) + ")");
    check(err <= 0.05, "channel: recovered payload scale error <= 5% (got " +
                       std::to_string(err) + ")");
    check(corr >= 0.99, "channel: recovered payload complex correlation >= 0.99 (got " +
                        std::to_string(corr) + ")");
}

void test_cfo_only(const std::string& path, std::uint64_t cc, const std::string& sha,
                   const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->cfo_hz = 10.0;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "cfo: transfer succeeds (" + o.err + ")");
    if (o.threw) return;
    bool valid = false; double err = 1e9; double corr = 0.0; iqrfrec::PerFileRecovery rec;
    recover(o.r, payload, valid, err, corr, rec);
    check(valid, "cfo: recovery valid");
    check(err <= 0.05, "cfo: scale error <= 5% (got " + std::to_string(err) + ")");
}

void test_sro_only(const std::string& path, std::uint64_t cc, const std::string& sha,
                   const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->sro_ppm = 20.0;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "sro: transfer succeeds (" + o.err + ")");
    if (o.threw) return;
    bool valid = false; double err = 1e9; double corr = 0.0; iqrfrec::PerFileRecovery rec;
    recover(o.r, payload, valid, err, corr, rec);
    check(valid, "sro: recovery valid");
    check(err <= 0.05, "sro: scale error <= 5% (got " + std::to_string(err) + ")");
}

void test_timing_only(const std::string& path, std::uint64_t cc, const std::string& sha,
                      const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->timing_offset = 500;   // a fixed whole-sample coax/RF channel delay
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "timing: transfer succeeds (" + o.err + ")");
    if (o.threw) return;
    bool valid = false; double err = 1e9; double corr = 0.0; iqrfrec::PerFileRecovery rec;
    recover(o.r, payload, valid, err, corr, rec);
    check(valid, "timing: recovery valid despite fixed 500-sample channel delay");
    // rec.timing_offset is the preamble's lag INSIDE the capture (capture-relative),
    // not the absolute channel delay -- the delay is absorbed by the full-capture
    // preamble search, so the payload still recovers near-exactly.
    check(err <= 0.01, "timing: scale error <= 1% (got " + std::to_string(err) + ")");
}

// ---- fail-closed cases -------------------------------------------------------

void test_loopback_fail_closed(const std::string& path, std::uint64_t cc,
                               const std::string& sha) {
    Fixture fx;
    fx.tx.loopback_readback_override = 1;   // TX device silently ignores set_loopback(0)
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(o.threw, "fail: loopback read-back != 0 throws");
}

void test_ceiling_fail_closed(const std::string& path, std::uint64_t cc,
                              const std::string& sha) {
    Fixture fx;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, -30.0,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(o.threw, "fail: TX atten > -40 dB ceiling throws");
}

void test_atten_readback_fail_closed(const std::string& path, std::uint64_t cc,
                                     const std::string& sha) {
    Fixture fx;
    fx.tx.atten_readback_bias = 0.5;   // set_tx_atten read-back disagrees
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(o.threw, "fail: TX atten read-back mismatch throws");
}

void test_wrong_count_fail_closed(const std::string& path, const std::string& sha) {
    Fixture fx;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, iqrftrain::kPayloadComplex - 1, sha,
                                kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(o.threw, "fail: payload complex_count != kPayloadComplex throws");
}

void test_sha_fail_closed(const std::string& path, std::uint64_t cc) {
    Fixture fx;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, std::string(64, '0'), kCenter,
                                kRxGain, kAtten, iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(o.threw, "fail: payload SHA mismatch throws");
}

// Restore failure is RECORDED (tx_restore_ok == false), never silent.
void test_restore_failure(const std::string& path, std::uint64_t cc, const std::string& sha) {
    Fixture fx;
    fx.tx.restore_fail = true;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "restore-fail: transfer still completes");
    check(!o.r.tx_restore_ok && o.r.rx_restore_ok,
          "restore-fail: tx_restore_ok false, rx_restore_ok true (independent guards)");
}

}  // namespace

int main() {
    std::printf("test_iq_dual_sdr_fix10\n");

#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = "/tmp/fix10_dual_" + std::to_string(::getpid());
    ::mkdir(dir.c_str(), 0700);
#else
    const std::string dir = ".";
#endif
    const std::uint64_t cc = iqrftrain::kPayloadComplex;
    const std::vector<std::int16_t> payload = make_payload(cc, 0x12345678u);
    const std::string path = dir + "/payload.ci16";
    write_binary(path, payload);
    const std::string sha = sha_of(payload);

    test_clean_transfer(path, cc, sha, payload);
    test_channel_inversion(path, cc, sha, payload);
    test_cfo_only(path, cc, sha, payload);
    test_sro_only(path, cc, sha, payload);
    test_timing_only(path, cc, sha, payload);
    test_loopback_fail_closed(path, cc, sha);
    test_ceiling_fail_closed(path, cc, sha);
    test_atten_readback_fail_closed(path, cc, sha);
    test_wrong_count_fail_closed(path, sha);
    test_sha_fail_closed(path, cc);
    test_restore_failure(path, cc, sha);

#if defined(__unix__) || defined(__APPLE__)
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#endif

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
