// test_iq_dual_sdr_23class_fix10.cpp -- fix10 Path A/C host test: the COARSE-CFO
// dual-SDR recovery (iq_dual_sdr_coarse_cfo_recovery.hpp) and the --phase CLI surface
// (gate9_phase.hpp).  iCraft-free and libiio-free.
//
// It proves, without a board:
//   * gate9::valid_phase accepts "iq-dual-sdr-23class-fix10" (and rejects near-misses);
//   * the fix10 distinction: a ~200 Hz carrier offset (kHz-scale across two free-running
//     Plutos) is OUTSIDE the fine-CFO unambiguous range (+/-fs/(2*kTailStart) ~ 21.7 Hz),
//     so the single-SDR estimate() aliases and the payload-domain training block is
//     mis-de-ramped -> invalid; but recover_payload_with_coarse_cfo() de-rotates the
//     whole capture by -coarse_cfo_hz FIRST and recovers the payload near-exactly;
//   * the coarse pre-rotation composes with the full channel (gain/phase/CFO/SRO/
//     delay/noise) and does not regress the clean (zero-CFO) case.

#include "../board_package/iq_dual_sdr_coarse_cfo_recovery.hpp"
#include "../board_package/iq_dual_sdr_transfer_fix10.hpp"
#include "../board_package/gate9_phase.hpp"
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

// ---- shared fixtures (mirrors test_iq_dual_sdr_fix10.cpp) --------------------

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

std::vector<std::int16_t> make_payload(std::size_t n_complex, std::uint32_t seed) {
    const std::size_t sps = 32;
    const double amp = 2048.0;
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
    return std::fabs(std::sqrt(e_r / static_cast<double>(n)) /
                         std::sqrt(e_o / static_cast<double>(n)) - 1.0);
}

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

// The runner (N3) estimator config: same-Pluto strict bounds, but the coarse CFO is
// removed FIRST so the FINE cfo_hz is only the small residual.
iqrfrec::EstimateConfig runner_cfg() {
    iqrfrec::EstimateConfig c;
    c.min_corr = 0.9;
    c.max_residual = iqrfrec::kPayloadTrainingResidualMax;   // 0.10 (fix9r2g migrated gate)
    c.max_cfo_hz = 30.0;
    c.max_sro_ppm = 30.0;
    c.search_limit = 0;
    return c;
}

const std::uint64_t kCenter = 2400000000;
const double kRxGain = 10.0;
const double kAtten = -40.0;

// ---- tests ------------------------------------------------------------------

// The --phase CLI surface accepts the new fix10 phase and rejects near-misses.
void test_phase_surface() {
    check(gate9::valid_phase("iq-dual-sdr-23class-fix10"),
          "phase: valid_phase accepts iq-dual-sdr-23class-fix10");
    check(!gate9::valid_phase("iq-dual-sdr-23class-fix10x"),
          "phase: valid_phase rejects trailing-x near-miss");
    check(!gate9::valid_phase("iq-dual-sdr-23class-fix1"),
          "phase: valid_phase rejects truncated near-miss");
    check(!gate9::valid_phase(""),
          "phase: valid_phase rejects empty");
    // The single-SDR phase must remain valid (no regression to the existing surface).
    check(gate9::valid_phase("iq-rf-loopback-23class-fix9r"),
          "phase: valid_phase still accepts iq-rf-loopback-23class-fix9r");
}

// THE fix10 distinction: a 200 Hz offset is inside the COARSE CFO range (+/-1.28 MHz)
// but OUTSIDE the fine CFO range (+/-21.7 Hz).  recover_payload_with_coarse_cfo()
// de-rotates first, so it recovers near-exactly; the single-SDR estimate() does NOT.
void test_coarse_cfo_recovery(const std::string& path, std::uint64_t cc,
                              const std::string& sha, const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->cfo_hz = 200.0;   // kHz-scale inter-Pluto carrier offset
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "coarse-cfo: transfer succeeds (" + o.err + ")");
    if (o.threw) return;

    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(o.r.rx);
    const iqdual23fix10::CoarseCfoRecovery cfo =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, runner_cfg(), o.r.tx_scale);

    check(cfo.rec.valid, "coarse-cfo: recovery valid");
    check(std::fabs(cfo.coarse_cfo_hz - 200.0) <= 5.0,
          "coarse-cfo: coarse_cfo_hz ~200 Hz (got " + std::to_string(cfo.coarse_cfo_hz) + ")");
    // After the coarse pre-rotation the FINE CFO is only the small residual.
    check(std::fabs(cfo.rec.cfo_hz) <= 30.0,
          "coarse-cfo: residual fine cfo_hz within +/-30 Hz (got " +
              std::to_string(cfo.rec.cfo_hz) + ")");
    check(complex_corr(cfo.payload, payload) >= 0.99,
          "coarse-cfo: recovered payload complex corr >= 0.99 (got " +
              std::to_string(complex_corr(cfo.payload, payload)) + ")");
    check(scale_error(cfo.payload, payload) <= 0.05,
          "coarse-cfo: recovered payload scale error <= 5% (got " +
              std::to_string(scale_error(cfo.payload, payload)) + ")");
}

// The single-SDR estimate() (no coarse pre-rotation) MUST fail or mis-recover the same
// 200 Hz offset -- this is exactly why fix10 adds the coarse pre-rotation.
void test_single_pass_fails_coarse_cfo(const std::string& path, std::uint64_t cc,
                                       const std::string& sha,
                                       const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->cfo_hz = 200.0;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "single-pass: transfer succeeds (" + o.err + ")");
    if (o.threw) return;

    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(o.r.rx);
    iqrfrec::PerFileRecovery rec = iqrfrec::estimate(rx, runner_cfg());

    bool wrong = false;
    if (rec.valid) {
        rec.payload_tx_scale = o.r.tx_scale;
        const std::vector<std::complex<double>> out = iqrfrec::apply(rx, rec);
        wrong = (complex_corr(out, payload) < 0.90);
    } else {
        wrong = true;   // the 200 Hz CFO mis-de-ramps the training block -> invalid
    }
    check(wrong, "single-pass: no-coarse estimate() fails/mis-recovers a 200 Hz CFO "
                 "(valid=" + std::string(rec.valid ? "true" : "false") + ", failure=" +
                 iqrfrec::failure_token(rec.failure) + ")");
}

// The coarse pre-rotation composes with the FULL channel (gain/phase/CFO/SRO/delay/noise).
void test_full_impairment_coarse_cfo(const std::string& path, std::uint64_t cc,
                                     const std::string& sha,
                                     const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->gain = 0.8;
    fx.link->phase_deg = 30.0;
    fx.link->cfo_hz = 200.0;
    fx.link->sro_ppm = 20.0;
    fx.link->timing_offset = 300;
    fx.link->noise_rms = 5.0;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "full: transfer succeeds (" + o.err + ")");
    if (o.threw) return;

    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(o.r.rx);
    const iqdual23fix10::CoarseCfoRecovery cfo =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, runner_cfg(), o.r.tx_scale);

    check(cfo.rec.valid, "full: recovery valid");
    check(std::fabs(cfo.coarse_cfo_hz - 200.0) <= 5.0,
          "full: coarse_cfo_hz ~200 Hz (got " + std::to_string(cfo.coarse_cfo_hz) + ")");
    check(std::fabs(cfo.rec.payload_gain_mag - 0.8) <= 0.04,
          "full: payload gain ~0.8 (got " + std::to_string(cfo.rec.payload_gain_mag) + ")");
    check(complex_corr(cfo.payload, payload) >= 0.99,
          "full: recovered payload complex corr >= 0.99 (got " +
              std::to_string(complex_corr(cfo.payload, payload)) + ")");
    check(scale_error(cfo.payload, payload) <= 0.05,
          "full: recovered payload scale error <= 5% (got " +
              std::to_string(scale_error(cfo.payload, payload)) + ")");
}

// The coarse pre-rotation must not regress the clean (zero-CFO) dual-SDR case.
void test_identity_coarse_cfo(const std::string& path, std::uint64_t cc,
                              const std::string& sha,
                              const std::vector<std::int16_t>& payload) {
    Fixture fx;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, kCenter, kRxGain, kAtten,
                                iqdual_run_fix10::kFix10DelayMarginDefault,
                                iqrfloop_run::kRfNoiseComplexDefault, 0.0);
    check(!o.threw, "identity: transfer succeeds (" + o.err + ")");
    if (o.threw) return;

    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(o.r.rx);
    const iqdual23fix10::CoarseCfoRecovery cfo =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, runner_cfg(), o.r.tx_scale);

    check(cfo.rec.valid, "identity: recovery valid");
    check(std::fabs(cfo.coarse_cfo_hz) <= 5.0,
          "identity: coarse_cfo_hz ~0 Hz (got " + std::to_string(cfo.coarse_cfo_hz) + ")");
    check(complex_corr(cfo.payload, payload) >= 0.99,
          "identity: recovered payload complex corr >= 0.99 (got " +
              std::to_string(complex_corr(cfo.payload, payload)) + ")");
}

}  // namespace

int main() {
    std::printf("test_iq_dual_sdr_23class_fix10\n");

    test_phase_surface();

#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = "/tmp/fix10_dual23_" + std::to_string(::getpid());
    ::mkdir(dir.c_str(), 0700);
#else
    const std::string dir = ".";
#endif
    const std::uint64_t cc = iqrftrain::kPayloadComplex;
    const std::vector<std::int16_t> payload = make_payload(cc, 0x9E3779B9u);
    const std::string path = dir + "/payload.ci16";
    write_binary(path, payload);
    const std::string sha = sha_of(payload);

    test_coarse_cfo_recovery(path, cc, sha, payload);
    test_single_pass_fails_coarse_cfo(path, cc, sha, payload);
    test_full_impairment_coarse_cfo(path, cc, sha, payload);
    test_identity_coarse_cfo(path, cc, sha, payload);

#if defined(__unix__) || defined(__APPLE__)
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#endif

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
