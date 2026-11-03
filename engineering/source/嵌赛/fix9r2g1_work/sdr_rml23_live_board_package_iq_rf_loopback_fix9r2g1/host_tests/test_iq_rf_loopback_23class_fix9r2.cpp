// test_iq_rf_loopback_23class_fix9r2.cpp -- host tests for Route F fix9r2 (the
// FULL-CAPTURE training-frame recovery core that replaces fix9r1's bounded first-4096
// search).  iCraft-free and libiio-free: it exercises the exact code the board runner
// uses -- iq_rf_frame_layout.hpp / iq_rf_sync_recovery.hpp / iq_rf_tx_provenance.hpp
// / iq_rf_loopback_transfer_fix9r.hpp -- plus the FakePlutoDevice external-RF echo.
//
// Covered (no NPU, no libiio):
//   * R1/R2 byte-level TX provenance: fingerprint fields + the INDEPENDENT
//     frame verifier (training/payload/layout match, corrupt-payload, wrong length)
//     + the iio_buffer_push byte provenance (requested/returned/ok, mismatch path);
//   * R3 training-frame identity: version 2 + seed N/A;
//   * R4 cyclic frame layout: period == 59904, capture == 2 periods + margin;
//   * the ROOT-CAUSE fix: the full-capture search finds a preamble at offset 5000
//     that the old bounded-4096 search misses; and the end-to-end identity echo
//     through transfer_one_file_rf_fix9r locates the preamble at the deterministic
//     cyclic offset 55808 with corr ~ 1 and payload NMSE ~ 0;
//   * R6 valid semantics: computed vs valid + the typed failure tokens
//     (CAPTURE_TOO_SHORT / TRAINING_NOT_FOUND / TRAINING_CORRELATION_TOO_LOW /
//     CFO_OUT_OF_RANGE / SRO_OUT_OF_RANGE / TRAINING_PEAK_AMBIGUOUS), and the
//     cyclic-repeat exemption (a second preamble one frame period away is NOT an
//     ambiguity).

#include "../board_package/iq_rf_training_frame.hpp"
#include "../board_package/iq_rf_frame_layout.hpp"
#include "../board_package/iq_rf_sync_recovery.hpp"
#include "../board_package/iq_rf_tx_provenance.hpp"
#include "../board_package/iq_rf_loopback_transfer_fix9r.hpp"
#include "../sdr_adapter/sha256.hpp"
#include "../sdr_adapter/pluto_device.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
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

// ---- deterministic waveforms (LCG, same as test_iq_rf_loopback_23class.cpp) ----

std::vector<std::int16_t> make_prbs(std::size_t P, int A, std::uint32_t seed) {
    std::vector<std::int16_t> iq(P * 2);
    std::uint32_t s = seed ? seed : 0x9e3779b9u;
    auto bit = [&s]() -> int {
        s = s * 1664525u + 1013904223u;
        return static_cast<int>((s >> 24) & 1u);
    };
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(bit() ? A : -A);
        iq[k * 2 + 1] = static_cast<std::int16_t>(bit() ? A : -A);
    }
    return iq;
}

double nmse(const std::vector<std::complex<double>>& a,
            const std::vector<std::complex<double>>& b) {
    double num = 0.0, den = 0.0;
    const std::size_t n = std::min(a.size(), b.size());
    for (std::size_t k = 0; k < n; ++k) {
        const std::complex<double> e = a[k] - b[k];
        num += e.real() * e.real() + e.imag() * e.imag();
        den += b[k].real() * b[k].real() + b[k].imag() * b[k].imag();
    }
    return den > 0.0 ? num / den : 0.0;
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

std::string write_ci16(const std::string& dir, const std::string& name,
                       const std::vector<std::int16_t>& iq) {
    const std::string path = dir + "/" + name;
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
    return sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
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

// ---- 1. R3: training-frame identity (version + seed) -------------------------

void test_training_version_seed() {
    check(iqrftrain::kTrainingVersion == 2, "ver: kTrainingVersion == 2");
    check(iqrftrain::kTrainingSeed == 0, "seed: kTrainingSeed == 0 (ZC is seed-free)");
}

// ---- 2. R4: cyclic frame layout constants ------------------------------------

void test_frame_layout_constants() {
    check(iqrflayout::kFramePeriodComplex == iqrftrain::kTotalBurstComplex,
          "layout: period == total burst");
    check(iqrflayout::kFramePeriodComplex == 59904, "layout: period == 59904");
    check(iqrflayout::kMinCapturePeriods == 2, "layout: min capture periods == 2");
    check(iqrflayout::capture_complex(8192) == 2 * 59904 + 8192,
          "layout: capture == 2*period + margin");
    check(iqrflayout::capture_complex(0) == 2 * 59904, "layout: capture(0) == 2*period");
}

// ---- 3. R1: byte fingerprint -------------------------------------------------

void test_provenance_fingerprint() {
    const auto iq = make_prbs(iqrftrain::kPayloadComplex, 1500, 31);
    const iqrftxprov::ByteFingerprint f = iqrftxprov::fingerprint(iq);
    check(f.complex == iqrftrain::kPayloadComplex, "fp: complex count == payload complex");
    check(f.sha256 == sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t)),
          "fp: sha256 matches");
    check(std::fabs(f.rms - 1500.0) < 1e-6, "fp: rms == amplitude (all samples +/-1500)");
    check(f.peak == 1500, "fp: peak == 1500");
    check(!f.clip, "fp: no clip");
    check(f.iq_order == "interleaved(I0,Q0,I1,Q1,...)", "fp: iq_order");
    check(f.bits == 16 && f.is_signed && f.endianness == "little", "fp: 16b signed LE");
}

// ---- 4. R2: independent TX-frame verifier ------------------------------------

void test_provenance_verify_frame() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 32);
    const auto burst = iqrftrain::build_burst(payload);
    const iqrftxprov::TxFrameVerify v = iqrftxprov::verify_frame(burst, payload);
    check(v.training_exact_match, "vf: training exact match");
    check(v.payload_exact_match, "vf: payload exact match");
    check(v.frame_layout_match, "vf: layout match");
    check(v.ok, "vf: ok");

    // corrupt one payload byte -> payload mismatch (training still matches)
    std::vector<std::int16_t> b2 = burst;
    b2[iqrftrain::kPayloadStart * 2] =
        static_cast<std::int16_t>(b2[iqrftrain::kPayloadStart * 2] ^ 0x0001);
    const iqrftxprov::TxFrameVerify v2 = iqrftxprov::verify_frame(b2, payload);
    check(!v2.payload_exact_match && v2.training_exact_match, "vf: corrupt payload caught");
    check(!v2.ok, "vf: corrupt payload -> not ok");

    // wrong length -> layout mismatch
    std::vector<std::int16_t> b3 = burst;
    b3.pop_back();
    const iqrftxprov::TxFrameVerify v3 = iqrftxprov::verify_frame(b3, payload);
    check(!v3.frame_layout_match && !v3.ok, "vf: wrong length -> layout mismatch");

    // training_reference_iq == preamble ++ tail
    const auto ref = iqrftxprov::training_reference_iq();
    check(ref.size() == (iqrftrain::kPreambleComplex + iqrftrain::kTailComplex) * 2,
          "vf: training reference length");
    const auto pre = iqrftrain::preamble();
    const auto t = iqrftrain::tail();
    check(std::equal(pre.begin(), pre.end(), ref.begin()) &&
              std::equal(t.begin(), t.end(), ref.begin() + pre.size()),
          "vf: training reference == preamble+tail");
}

// ---- 5. R4 root-cause fix: full-capture search vs the old bounded-4096 search ----

void test_full_capture_finds_offset() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 38);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const std::size_t delay = 5000;   // beyond fix9r1's first-4096 search bound
    std::vector<std::complex<double>> rx(delay + base.size(), 0.0);
    for (std::size_t k = 0; k < base.size(); ++k) rx[delay + k] = base[k];

    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "full: full-capture search finds the offset preamble");
    check(rec.timing_offset == delay, "full: timing_offset == delay");

    // the OLD bounded search (4096) must FAIL: the preamble sits beyond sample 4096
    const auto bounded = iqrfrec::estimate(rx, 4096);
    check(!bounded.valid, "full: bounded-4096 search misses it (the fix9r1 bug)");
}

// ---- 6. R6: failure tokens ---------------------------------------------------

void test_failure_too_short() {
    std::vector<std::complex<double>> rx(iqrftrain::kTotalBurstComplex - 1, 0.0);
    const auto rec = iqrfrec::estimate(rx);
    check(!rec.valid, "fail-short: invalid");
    check(rec.computed, "fail-short: computed (ran)");
    check(rec.failure == iqrfrec::Failure::CAPTURE_TOO_SHORT,
          "fail-short: token CAPTURE_TOO_SHORT");
    check(std::string(iqrfrec::failure_token(rec.failure)) == "CAPTURE_TOO_SHORT",
          "fail-short: token string");
}

void test_failure_not_found() {
    std::vector<std::complex<double>> rx(iqrftrain::kTotalBurstComplex, 0.0);
    const auto rec = iqrfrec::estimate(rx);
    check(!rec.valid, "fail-nofound: invalid");
    check(rec.failure == iqrfrec::Failure::TRAINING_NOT_FOUND,
          "fail-nofound: token TRAINING_NOT_FOUND");
}

void test_failure_corr_low() {
    const auto noise = make_prbs(iqrftrain::kTotalBurstComplex, 2048, 33);
    const auto rx = iqrftrain::deinterleave(noise);
    const auto rec = iqrfrec::estimate(rx);
    check(!rec.valid, "fail-corr: invalid");
    check(rec.failure == iqrfrec::Failure::TRAINING_CORRELATION_TOO_LOW,
          "fail-corr: token TRAINING_CORRELATION_TOO_LOW");
    check(rec.training_corr < 0.9, "fail-corr: corr < 0.9");
}

void test_failure_cfo_out_of_range() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 34);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const double f = 10.0;   // Hz, anchored at the preamble
    std::vector<std::complex<double>> rx(base.size());
    for (std::size_t k = 0; k < base.size(); ++k)
        rx[k] = base[k] * std::polar(1.0, 2.0 * kPi * f * static_cast<double>(k) /
                                          static_cast<double>(iqrftrain::kFs));

    iqrfrec::EstimateConfig cfg;
    cfg.max_cfo_hz = 5.0;   // strict same-Pluto bound: 10 Hz is out of range
    const auto rec = iqrfrec::estimate(rx, cfg);
    check(!rec.valid, "fail-cfo: invalid");
    check(rec.failure == iqrfrec::Failure::CFO_OUT_OF_RANGE,
          "fail-cfo: token CFO_OUT_OF_RANGE");
    check(std::fabs(rec.cfo_hz - f) < 0.1, "fail-cfo: cfo_hz still measured (~10 Hz)");
}

void test_failure_sro_out_of_range() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 35);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const double s = 100.0e-6;
    const std::size_t cap = iqrftrain::kTotalBurstComplex + 8192;
    std::vector<std::complex<double>> rx(cap, 0.0);
    for (std::size_t n = 0; n < cap; ++n) {
        const double m = static_cast<double>(n) / (1.0 + s);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(m));
        const std::size_t i1 = i0 + 1;
        if (i1 < base.size()) {
            const double fr = m - static_cast<double>(i0);
            rx[n] = base[i0] * (1.0 - fr) + base[i1] * fr;
        } else if (i0 < base.size()) {
            rx[n] = base[i0];
        }
    }

    iqrfrec::EstimateConfig cfg;
    cfg.max_sro_ppm = 50.0;   // strict bound: 100 ppm is out of range
    const auto rec = iqrfrec::estimate(rx, cfg);
    check(!rec.valid, "fail-sro: invalid");
    check(rec.failure == iqrfrec::Failure::SRO_OUT_OF_RANGE,
          "fail-sro: token SRO_OUT_OF_RANGE");
    check(std::fabs(rec.sro_ppm - 100.0) < 5.0, "fail-sro: sro still measured (~+100 ppm)");
}

void test_failure_ambiguous() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 36);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const std::size_t extra = 8192;
    std::vector<std::complex<double>> rx(base.size() + extra, 0.0);
    for (std::size_t k = 0; k < base.size(); ++k) rx[k] = base[k];
    // inject a SECOND distinct preamble at offset 5000 (NOT a frame period away)
    const auto pre = iqrftrain::preamble_complex();
    for (std::size_t k = 0; k < pre.size(); ++k) rx[5000 + k] = pre[k];

    const auto rec = iqrfrec::estimate(rx);
    check(!rec.valid, "fail-amb: invalid");
    check(rec.failure == iqrfrec::Failure::TRAINING_PEAK_AMBIGUOUS,
          "fail-amb: token TRAINING_PEAK_AMBIGUOUS");
}

void test_cyclic_repeat_not_ambiguous() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 37);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    // a 2-period capture: the preamble appears twice, one frame period apart
    std::vector<std::complex<double>> rx(base.size() * 2);
    for (std::size_t k = 0; k < base.size(); ++k) {
        rx[k] = base[k];
        rx[base.size() + k] = base[k];
    }

    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "cyc: valid (cyclic repeat exempted from ambiguity)");
    check(rec.failure == iqrfrec::Failure::NONE, "cyc: failure == NONE");
    check(rec.timing_offset == 0, "cyc: timing_offset == 0");
    check(rec.training_corr > 0.999, "cyc: corr ~ 1");
}

// ---- 7. end-to-end identity echo through the transfer + recovery -------------

void test_end_to_end_identity_echo() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r2_e2e");
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 41);
    const std::string sha = write_ci16(dir, "rf.ci16", payload);
    const std::string path = dir + "/rf.ci16";
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 1.0; dev.rf_phase_deg = 0.0; dev.rf_delay = 0;
    dev.rf_noise_rms = 0.0;
    dev.tx_fmt_ = idfmt;

    const auto tr = iqrfloop_run_fix9r::transfer_one_file_rf_fix9r(
        dev, path, iqrftrain::kPayloadComplex, sha, 2400000000ULL, 10.0, -40.0,
        iqrfloop_run_fix9r::kFix9rDelayMarginDefault, 4096, nullptr, 0.0);

    check(tr.capture_ok, "e2e: capture ok");
    check(tr.frame_verify.ok, "e2e: frame verifier ok (R2)");
    check(tr.tx_push.ok, "e2e: push provenance ok (R1)");
    check(tr.tx_dma_payload_ok, "e2e: tx DMA payload SHA ok");

    const auto rx = iqrftrain::deinterleave(tr.rx);
    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "e2e: recovery valid");
    check(rec.failure == iqrfrec::Failure::NONE, "e2e: failure == NONE");

    // after the 4096-sample discard refill the cyclic TX is at sample 4096, so the
    // next preamble head sits at capture offset (59904 - 4096) == 55808.
    const std::size_t expected =
        iqrflayout::kFramePeriodComplex - iqrfloop_run::kRfDiscardComplex;
    check(expected == 55808, "e2e: expected offset arithmetic == 55808");
    check(rec.timing_offset == expected, "e2e: preamble at the deterministic cyclic offset");
    check(rec.training_corr > 0.999, "e2e: training_corr ~ 1");
    check(std::fabs(rec.gain_mag - 1.0) < 1e-3, "e2e: gain_mag ~ 1");
    check(std::fabs(rec.phase_deg) < 0.5, "e2e: phase ~ 0");
    check(std::fabs(rec.cfo_hz) < 0.05, "e2e: cfo ~ 0");
    check(std::fabs(rec.sro_ppm) < 1.0, "e2e: sro ~ 0");

    const auto out = iqrfrec::apply(rx, rec);
    const auto ref = iqrftrain::deinterleave(payload);
    check(nmse(out, ref) < 1e-3, "e2e: recovered payload NMSE ~ 0");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 8. recover_payload_int16 convenience -----------------------------------

void test_recover_payload_int16_convenience() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 43);
    const auto burst = iqrftrain::build_burst(payload);
    const auto out = iqrfrec::recover_payload_int16(burst);
    check(out.size() == payload.size(), "conv: recovered payload length");
    check(out == payload, "conv: recovered payload == original");
}

// ---- 9. R1: iio_buffer_push provenance (mismatch path) -----------------------

void test_push_provenance_mismatch() {
    const auto payload = make_prbs(64, 1000, 42);
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_push_returned_override = -1;   // model a short/negative iio_buffer_push return
    dev.tx_start_cyclic(payload);
    const pluto::TxPushProvenance p = dev.tx_push_provenance();
    check(p.requested_bytes == payload.size() * sizeof(std::int16_t),
          "push: requested bytes");
    check(p.returned_bytes == -1, "push: returned bytes == override");
    check(!p.ok, "push: ok == false on short return");
}

}  // namespace

void run_test(const char* name, void (*fn)()) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main() {
    std::printf("test_iq_rf_loopback_23class_fix9r2\n");
    run_test("training_version_seed", test_training_version_seed);
    run_test("frame_layout_constants", test_frame_layout_constants);
    run_test("provenance_fingerprint", test_provenance_fingerprint);
    run_test("provenance_verify_frame", test_provenance_verify_frame);
    run_test("full_capture_finds_offset", test_full_capture_finds_offset);
    run_test("failure_too_short", test_failure_too_short);
    run_test("failure_not_found", test_failure_not_found);
    run_test("failure_corr_low", test_failure_corr_low);
    run_test("failure_cfo_out_of_range", test_failure_cfo_out_of_range);
    run_test("failure_sro_out_of_range", test_failure_sro_out_of_range);
    run_test("failure_ambiguous", test_failure_ambiguous);
    run_test("cyclic_repeat_not_ambiguous", test_cyclic_repeat_not_ambiguous);
    run_test("end_to_end_identity_echo", test_end_to_end_identity_echo);
    run_test("recover_payload_int16_convenience", test_recover_payload_int16_convenience);
    run_test("push_provenance_mismatch", test_push_provenance_mismatch);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
