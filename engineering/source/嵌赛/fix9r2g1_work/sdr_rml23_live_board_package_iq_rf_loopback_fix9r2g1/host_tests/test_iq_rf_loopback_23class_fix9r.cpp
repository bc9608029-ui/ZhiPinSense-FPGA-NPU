// test_iq_rf_loopback_23class_fix9r.cpp -- host tests for Route F fix9r (per-file
// TRAINING-FRAME recovery replacing fix9's ONE global complex gain).  iCraft-free
// and libiio-free: it exercises the exact iq_rf_training_frame.hpp /
// iq_rf_per_frame_recovery.hpp / iq_rf_loopback_transfer_fix9r.hpp /
// iq_rf_fix9r_baseline.hpp code the board runner uses, plus the FakePlutoDevice
// echo for the transfer structure.  The NPU inference itself is board-only.
//
// Covered (no NPU, no libiio):
//   * the Zadoff-Chu training frame: unit envelope, distinct preamble/tail roots,
//     burst layout (preamble@0 / guard / payload@3072 / guard / tail@58880),
//     determinism, fail-closed length checks, deinterleave round-trip;
//   * per-file recovery: identity -> gain_mag/phase/CFO/SRO ~ 0 and NMSE ~ 0; the
//     exact fix9 global values (mag 0.016876 / phase 95.110 deg) recovered PER FILE
//     and undone; a timing offset; a 10 Hz CFO; a 100 ppm SRO; the bounded preamble
//     search never locks onto the (different-root) tail; a too-short capture fails;
//   * transfer_one_file_rf_fix9r with FakePlutoDevice: identity echo (burst SHA ==
//     DMA SHA, capture ok, loopback 0, TX stopped, noise stable), --rf-tx-target-rms
//     scale-up on the payload only, refuse-clip, wrong complex_count throws;
//   * iqrffix9r::load_baseline: valid 5-col TSV, and fail-closed on bad sha / bad
//     split_role / duplicate source_index / bad deployed_class / empty file.

#include "../board_package/iq_rf_training_frame.hpp"
#include "../board_package/iq_rf_per_frame_recovery.hpp"
#include "../board_package/iq_rf_loopback_transfer_fix9r.hpp"
#include "../board_package/iq_rf_fix9r_baseline.hpp"
#include "../board_package/rml23_merged.hpp"
#include "../sdr_adapter/sha256.hpp"

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

// ---- 1. Zadoff-Chu: unit envelope + distinct roots ---------------------------

void test_zadoff_chu_envelope_and_roots() {
    const auto u1 = iqrftrain::zadoff_chu(iqrftrain::kZadoffChuRoot);   // root 1
    const auto u3 = iqrftrain::zadoff_chu(iqrftrain::kTailZadoffChuRoot); // root 3
    check(u1.size() == iqrftrain::kPreambleComplex, "zc: root-1 length 1024");
    bool unit = true;
    for (std::size_t k = 0; k < u1.size(); ++k)
        if (std::fabs(std::abs(u1[k]) - 1.0) > 1e-12) unit = false;
    check(unit, "zc: unit envelope");
    bool differ = false;
    for (std::size_t k = 0; k < u1.size(); ++k)
        if (std::abs(u1[k] - u3[k]) > 1e-12) { differ = true; break; }
    check(differ, "zc: root 1 and root 3 differ (tail disambiguates)");
}

// ---- 2. preamble/tail amplitude + distinct -----------------------------------

void test_preamble_tail_amplitude_and_distinct() {
    const auto pre = iqrftrain::preamble();
    const auto t = iqrftrain::tail();
    check(pre.size() == iqrftrain::kPreambleComplex * 2, "pre: int16 length 2048");
    check(t.size() == iqrftrain::kTailComplex * 2, "tail: int16 length 2048");
    int maxamp = 0;
    for (std::int16_t s : pre) maxamp = std::max(maxamp, std::abs(static_cast<int>(s)));
    check(maxamp <= 2048 && maxamp >= 2047, "pre: amplitude ~ kTrainAmp 2048");
    bool distinct = false;
    for (std::size_t k = 0; k < pre.size(); ++k)
        if (pre[k] != t[k]) { distinct = true; break; }
    check(distinct, "pre/tail: sequences differ (different ZC roots)");
}

// ---- 3. burst layout ---------------------------------------------------------

void test_build_burst_structure() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 3);
    const auto b = iqrftrain::build_burst(payload);
    check(b.size() == iqrftrain::kTotalBurstComplex * 2, "burst: total length 59904*2");
    const auto pre = iqrftrain::preamble();
    const auto t = iqrftrain::tail();
    check(std::equal(pre.begin(), pre.end(), b.begin()), "burst: preamble at sample 0");
    // fix9r2g: the region between the preamble and the payload is now a settling-zero
    // zone (1024 complex) followed by the payload-domain training block (1024 complex),
    // NOT a single silence guard.
    bool settle = true;
    for (std::size_t i = iqrftrain::kPreambleComplex * 2;
         i < iqrftrain::kPayloadTrainingOffset * 2; ++i)
        if (b[i] != 0) settle = false;
    check(settle, "burst: settling-zero zone is silence");
    const auto pt = iqrftrain::payload_gain_training();
    check(std::equal(pt.begin(), pt.end(),
                     b.begin() + iqrftrain::kPayloadTrainingOffset * 2),
          "burst: training block at kPayloadTrainingOffset");
    check(std::equal(payload.begin(), payload.end(),
                     b.begin() + iqrftrain::kPayloadStart * 2),
          "burst: payload at kPayloadStart");
    bool guard2 = true;
    for (std::size_t i = (iqrftrain::kPayloadStart + iqrftrain::kPayloadComplex) * 2;
         i < iqrftrain::kTailStart * 2; ++i)
        if (b[i] != 0) guard2 = false;
    check(guard2, "burst: second guard is silence");
    check(std::equal(t.begin(), t.end(), b.begin() + iqrftrain::kTailStart * 2),
          "burst: tail at kTailStart");
}

// ---- 4. burst determinism ----------------------------------------------------

void test_build_burst_deterministic() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2000, 9);
    check(iqrftrain::build_burst(payload) == iqrftrain::build_burst(payload),
          "burst: two builds byte-identical");
}

// ---- 5. wrong payload length throws ------------------------------------------

void test_build_burst_wrong_length_throws() {
    const auto wrong = make_prbs(iqrftrain::kPayloadComplex - 1, 1000, 1);
    bool threw = false;
    try { iqrftrain::build_burst(wrong); } catch (const std::exception&) { threw = true; }
    check(threw, "burst: wrong payload length throws");
}

// ---- 6. deinterleave round-trip + odd throw ----------------------------------

void test_deinterleave_roundtrip_and_odd_throw() {
    const auto iq = make_prbs(64, 1000, 7);
    const auto c = iqrftrain::deinterleave(iq);
    check(c.size() == 64, "deint: complex count == int16/2");
    check(c[0].real() == static_cast<double>(iq[0]) &&
          c[0].imag() == static_cast<double>(iq[1]),
          "deint: first sample I/Q correct");
    std::vector<std::int16_t> odd(5);
    bool threw = false;
    try { iqrftrain::deinterleave(odd); } catch (const std::exception&) { threw = true; }
    check(threw, "deint: odd int16 length throws");
}

// ---- 7. identity recovery ----------------------------------------------------

void test_recover_identity() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 11);
    const auto burst = iqrftrain::build_burst(payload);
    const auto rx = iqrftrain::deinterleave(burst);
    const auto ref = iqrftrain::deinterleave(payload);

    const iqrfrec::PerFileRecovery rec = iqrfrec::estimate(rx);
    check(rec.valid, "identity: valid");
    check(rec.timing_offset == 0, "identity: timing_offset == 0");
    check(std::fabs(rec.gain_mag - 1.0) < 1e-3, "identity: gain_mag ~ 1");
    check(std::fabs(rec.phase_deg) < 0.2, "identity: phase ~ 0");
    check(std::fabs(rec.cfo_hz) < 0.05, "identity: cfo ~ 0");
    check(std::fabs(rec.sro_ppm) < 1.0, "identity: sro ~ 0");
    check(rec.training_corr > 0.999, "identity: training_corr ~ 1");
    check(rec.training_residual < 1e-2, "identity: training_residual ~ 0");

    const auto out = iqrfrec::apply(rx, rec);
    check(nmse(out, ref) < 1e-4, "identity: recovered payload NMSE ~ 0");
}

// ---- 8. the exact fix9 global values recovered per file ----------------------

void test_recover_gain_phase_fix9_values() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 12);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const auto ref = iqrftrain::deinterleave(payload);

    // fix9's ONE global complex gain, applied to the WHOLE burst (this is exactly
    // what broke fix9: a single phase for every file).
    const double mag = 0.016876, phase_deg = 95.110;
    const std::complex<double> A = std::polar(mag, phase_deg * kPi / 180.0);
    std::vector<std::complex<double>> rx(base.size());
    for (std::size_t k = 0; k < base.size(); ++k) rx[k] = base[k] * A;

    const iqrfrec::PerFileRecovery rec = iqrfrec::estimate(rx);
    check(rec.valid, "gp: valid");
    check(std::fabs(rec.gain_mag - mag) < 1e-5, "gp: gain_mag recovered");
    check(std::fabs(rec.phase_deg - phase_deg) < 0.2, "gp: phase_deg recovered");

    const auto out = iqrfrec::apply(rx, rec);
    check(nmse(out, ref) < 1e-4, "gp: recovered payload NMSE ~ 0 (gain+phase undone)");
}

// ---- 9. timing offset --------------------------------------------------------

void test_recover_timing_offset() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 13);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const auto ref = iqrftrain::deinterleave(payload);

    const std::size_t delay = 100;
    std::vector<std::complex<double>> rx(delay + base.size(), 0.0);
    for (std::size_t k = 0; k < base.size(); ++k) rx[delay + k] = base[k];

    const iqrfrec::PerFileRecovery rec = iqrfrec::estimate(rx);
    check(rec.valid, "timing: valid");
    check(rec.timing_offset == delay, "timing: timing_offset == delay");
    const auto out = iqrfrec::apply(rx, rec);
    check(nmse(out, ref) < 1e-4, "timing: recovered payload NMSE ~ 0");
}

// ---- 10. CFO -----------------------------------------------------------------

void test_recover_cfo() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 14);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const auto ref = iqrftrain::deinterleave(payload);

    const double f = 10.0;   // Hz, anchored at burst sample 0 (the preamble)
    std::vector<std::complex<double>> rx(base.size());
    for (std::size_t k = 0; k < base.size(); ++k)
        rx[k] = base[k] * std::polar(1.0, 2.0 * kPi * f * static_cast<double>(k) /
                                          static_cast<double>(iqrftrain::kFs));

    const iqrfrec::PerFileRecovery rec = iqrfrec::estimate(rx);
    check(rec.valid, "cfo: valid");
    check(std::fabs(rec.cfo_hz - f) < 0.1, "cfo: cfo_hz recovered ~ 10 Hz");
    const auto out = iqrfrec::apply(rx, rec);
    // A residual CONSTANT phase (the LS gain's mid-window phase) remains, ~1.6e-4
    // NMSE; an un-removed CFO would be ~0.5.  1e-2 cleanly separates the two.
    check(nmse(out, ref) < 1e-2, "cfo: CFO removed (NMSE << un-corrected)");
}

// ---- 11. SRO -----------------------------------------------------------------

void test_recover_sro() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 15);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);

    // Inject a +100 ppm stretch (RX clock faster): rx[n] == s_tx[n/(1+s)].
    const double s = 100.0e-6;
    const std::size_t cap = iqrftrain::kTotalBurstComplex + 8192;
    std::vector<std::complex<double>> rx(cap, 0.0);
    for (std::size_t n = 0; n < cap; ++n) {
        const double m = static_cast<double>(n) / (1.0 + s);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(m));
        const std::size_t i1 = i0 + 1;
        if (i1 < base.size()) {
            const double frac = m - static_cast<double>(i0);
            rx[n] = base[i0] * (1.0 - frac) + base[i1] * frac;
        } else if (i0 < base.size()) {
            rx[n] = base[i0];
        }
    }

    const iqrfrec::PerFileRecovery rec = iqrfrec::estimate(rx);
    check(rec.valid, "sro: valid");
    check(std::fabs(rec.sro_ppm - 100.0) < 5.0, "sro: sro_ppm recovered ~ +100 ppm");
    // (The apply-side SRO direction is verified separately on a linear ramp, where
    //  linear interpolation is exact and a wrong direction is caught cleanly.)
}

// ---- 11b. apply() SRO direction (exact on a linear ramp) ---------------------

void test_apply_sro_direction() {
    // A linear-ramp payload makes linear interpolation EXACT, so the SRO undo is
    // verifiable to machine precision: correct direction -> src = m*(1+s) -> out
    // == base[m]; a (reciprocal) wrong direction reads m*(1-s) and drifts ~2*m*s
    // samples off by the end of the payload, which the ramp's slope turns into a
    // detectable residual far above the 1e-9 floor.
    const double s = 100.0e-6;
    const std::size_t N = iqrftrain::kTotalBurstComplex;
    std::vector<std::complex<double>> base(N);
    for (std::size_t n = 0; n < N; ++n)
        base[n] = std::complex<double>(1000.0 + 0.5 * static_cast<double>(n),
                                       -2000.0 + 0.3 * static_cast<double>(n));

    // inject SRO: rx[n] == base[n/(1+s)] via linear interpolation (exact for a ramp)
    std::vector<std::complex<double>> rx(N + 8192, 0.0);
    for (std::size_t n = 0; n < N; ++n) {
        const double m = static_cast<double>(n) / (1.0 + s);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(m));
        const std::size_t i1 = i0 + 1;
        if (i1 < N) {
            const double frac = m - static_cast<double>(i0);
            rx[n] = base[i0] * (1.0 - frac) + base[i1] * frac;
        } else {
            rx[n] = base[i0];
        }
    }

    iqrfrec::PerFileRecovery rec;
    rec.valid = true;
    rec.timing_offset = 0;
    rec.gain_mag = 1.0;          // preamble gain (instrument-only)
    rec.phase_deg = 0.0;
    rec.payload_gain_mag = 1.0;  // fix9r2g: apply() operates on the payload gain
    rec.payload_phase_deg = 0.0;
    rec.cfo_hz = 0.0;
    rec.sro_ppm = s * 1e6;   // +100 ppm
    rec.phase_drift_deg = 0.0;
    rec.training_corr = 1.0;
    rec.training_residual = 0.0;

    const auto out = iqrfrec::apply(rx, rec);
    double num = 0.0, den = 0.0;
    for (std::size_t k = 0; k < out.size(); ++k) {
        const std::complex<double> e =
            out[k] - base[iqrftrain::kPayloadStart + k];
        num += e.real() * e.real() + e.imag() * e.imag();
        const std::complex<double>& r = base[iqrftrain::kPayloadStart + k];
        den += r.real() * r.real() + r.imag() * r.imag();
    }
    check(den > 0.0 && num / den < 1e-9,
          "apply-sro: exact SRO undo (direction correct)");
}

// ---- 12. bounded preamble search never locks onto the tail -------------------

void test_recover_preamble_not_tail() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 2048, 16);
    const auto burst = iqrftrain::build_burst(payload);
    const auto rx = iqrftrain::deinterleave(burst);

    // A search window that extends PAST the tail still returns the preamble at 0:
    // the tail uses a different Zadoff-Chu root, so it cannot produce a spurious
    // peak even when the search reaches it.
    const iqrfrec::PerFileRecovery rec =
        iqrfrec::estimate(rx, iqrftrain::kTotalBurstComplex);
    check(rec.valid, "preamble: valid");
    check(rec.timing_offset == 0, "preamble: timing_offset == 0 (not the tail)");
    check(rec.training_corr > 0.999, "preamble: corr ~ 1 at the preamble");
}

// ---- 13. too-short capture fails ---------------------------------------------

void test_estimate_short_capture_invalid() {
    std::vector<std::complex<double>> short_rx(iqrftrain::kTotalBurstComplex - 1, 0.0);
    const iqrfrec::PerFileRecovery rec = iqrfrec::estimate(short_rx);
    check(!rec.valid, "short: capture shorter than the burst -> invalid");
}

// ---- 14-16. transfer_one_file_rf_fix9r with FakePlutoDevice ------------------

void test_transfer_identity() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_identity");
    const auto iq = make_prbs(iqrftrain::kPayloadComplex, 2048, 21);
    const std::string sha = write_ci16(dir, "rf.ci16", iq);
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
    check(tr.tx_verify.sha256 == sha, "tr-id: payload SHA verified");
    check(tr.tx.size() == iqrftrain::kTotalBurstComplex * 2, "tr-id: TX burst length");
    check(tr.burst_sha.size() == 64 && tr.burst_sha == tr.tx_dma_payload_sha,
          "tr-id: burst SHA == TX DMA SHA");
    check(tr.tx_dma_payload_ok, "tr-id: tx_dma_payload_ok");
    check(tr.capture_ok, "tr-id: capture_ok");
    check(tr.loopback_readback == 0, "tr-id: loopback readback == 0");
    check(tr.tx_stopped_readback, "tr-id: tx_stopped_readback");
    check(tr.noise_stable, "tr-id: noise_stable");
    check(!tr.tx_clip_pre && !tr.tx_clip_post, "tr-id: no TX clip");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_transfer_target_rms_scaleup() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_scaleup");
    const auto iq = make_prbs(iqrftrain::kPayloadComplex, 1000, 22);   // native RMS 1000
    const std::string sha = write_ci16(dir, "rf.ci16", iq);
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
        iqrfloop_run_fix9r::kFix9rDelayMarginDefault, 4096, nullptr, 2000.0);
    check(std::fabs(tr.tx_native_rms - 1000.0) < 1.0, "tr-up: native rms ~ 1000");
    check(std::fabs(tr.tx_scale - 2.0) < 1e-6, "tr-up: tx_scale ~ 2.0");
    check(!tr.tx_clip_pre && !tr.tx_clip_post, "tr-up: no clip (peak 2000)");
    check(tr.tx_peak_post > tr.tx_peak_pre, "tr-up: post peak > pre peak");
    check(tr.tx_sha_post != sha, "tr-up: scaled payload SHA differs");
    check(tr.tx_dma_payload_ok, "tr-up: scaled bytes match the DMA payload");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_transfer_target_rms_refuse_clip() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_clip");
    const auto iq = make_prbs(iqrftrain::kPayloadComplex, 20000, 23);  // peak 20000
    const std::string sha = write_ci16(dir, "rf.ci16", iq);
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
        iqrfloop_run_fix9r::kFix9rDelayMarginDefault, 4096, nullptr, 40000.0);
    check(tr.tx_clip_post, "tr-clip: predicted clip -> tx_clip_post == true");
    check(!tr.tx_clip_pre, "tr-clip: source bytes not pre-clipped");
    check(tr.tx_scale == 1.0, "tr-clip: tx_scale stays 1.0 (refused)");
    check(tr.tx_sha_post == sha, "tr-clip: bytes unchanged");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 17. wrong complex_count throws ------------------------------------------

void test_transfer_wrong_complex_count_throws() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_wronglen");
    const auto iq = make_prbs(iqrftrain::kPayloadComplex, 2048, 24);
    const std::string sha = write_ci16(dir, "rf.ci16", iq);
    const std::string path = dir + "/rf.ci16";
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_fmt_ = idfmt;

    bool threw = false;
    try {
        iqrfloop_run_fix9r::transfer_one_file_rf_fix9r(
            dev, path, iqrftrain::kPayloadComplex - 1, sha, 2400000000ULL, 10.0,
            -40.0, iqrfloop_run_fix9r::kFix9rDelayMarginDefault, 4096, nullptr, 0.0);
    } catch (const std::exception&) { threw = true; }
    check(threw, "tr-wronglen: complex_count != kPayloadComplex throws");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 18-23. iqrffix9r::load_baseline -----------------------------------------

void write_baseline(const std::string& dir, const std::string& name,
                    const std::vector<std::string>& rows) {
    std::ofstream f(dir + "/" + name);
    f << "source_index\tsha256\tdeployed_class\tmodulation\tsplit_role\tfrozen_baseline_pred\n";
    for (const auto& r : rows) f << r << "\n";
}

std::string row(std::uint64_t idx, const std::string& sha, int cls,
                const std::string& mod, const std::string& role, int pred) {
    return std::to_string(idx) + "\t" + sha + "\t" + std::to_string(cls) + "\t" +
           mod + "\t" + role + "\t" + std::to_string(pred);
}

void test_baseline_valid() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_bl_valid");
    const std::string sha = std::string(64, 'a');
    write_baseline(dir, "b.tsv", { row(7, sha, 3, "BPSK", "holdout", 5),
                                   row(8, std::string(64, 'b'), 4, "QPSK", "holdout", 6) });
    const auto m = iqrffix9r::load_baseline(dir + "/b.tsv", rml23::kDeployedClassCount);
    check(m.size() == 2, "bl-valid: two rows");
    check(m.count(7) == 1 && m.at(7).sha256 == sha && m.at(7).deployed_class == 3 &&
          m.at(7).modulation == "BPSK" && m.at(7).split_role == "holdout" &&
          m.at(7).frozen_baseline_pred == 5,
          "bl-valid: row fields exact");
    ::unlink((dir + "/b.tsv").c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_baseline_bad_sha_throws() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_bl_badsha");
    write_baseline(dir, "b.tsv", { row(1, std::string(63, 'a'), 3, "BPSK", "holdout", 5) });
    bool threw = false;
    try { iqrffix9r::load_baseline(dir + "/b.tsv", rml23::kDeployedClassCount); }
    catch (const std::exception&) { threw = true; }
    check(threw, "bl-badsha: non-64-hex sha throws");
    ::unlink((dir + "/b.tsv").c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_baseline_bad_role_throws() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_bl_badrole");
    write_baseline(dir, "b.tsv", { row(1, std::string(64, 'a'), 3, "BPSK", "calibration", 5) });
    bool threw = false;
    try { iqrffix9r::load_baseline(dir + "/b.tsv", rml23::kDeployedClassCount); }
    catch (const std::exception&) { threw = true; }
    check(threw, "bl-badrole: split_role != holdout throws");
    ::unlink((dir + "/b.tsv").c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_baseline_duplicate_throws() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_bl_dup");
    write_baseline(dir, "b.tsv", { row(1, std::string(64, 'a'), 3, "BPSK", "holdout", 5),
                                   row(1, std::string(64, 'b'), 4, "QPSK", "holdout", 6) });
    bool threw = false;
    try { iqrffix9r::load_baseline(dir + "/b.tsv", rml23::kDeployedClassCount); }
    catch (const std::exception&) { threw = true; }
    check(threw, "bl-dup: duplicate source_index throws");
    ::unlink((dir + "/b.tsv").c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_baseline_bad_class_throws() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_bl_badclass");
    write_baseline(dir, "b.tsv", { row(1, std::string(64, 'a'), 23, "BPSK", "holdout", 5) });
    bool threw = false;
    try { iqrffix9r::load_baseline(dir + "/b.tsv", rml23::kDeployedClassCount); }
    catch (const std::exception&) { threw = true; }
    check(threw, "bl-badclass: deployed_class out of range throws");
    ::unlink((dir + "/b.tsv").c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_baseline_empty_throws() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r_bl_empty");
    write_baseline(dir, "b.tsv", {});
    bool threw = false;
    try { iqrffix9r::load_baseline(dir + "/b.tsv", rml23::kDeployedClassCount); }
    catch (const std::exception&) { threw = true; }
    check(threw, "bl-empty: header-only baseline throws");
    ::unlink((dir + "/b.tsv").c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
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
    std::printf("test_iq_rf_loopback_23class_fix9r\n");
    run_test("zadoff_chu_envelope_and_roots", test_zadoff_chu_envelope_and_roots);
    run_test("preamble_tail_amplitude_and_distinct", test_preamble_tail_amplitude_and_distinct);
    run_test("build_burst_structure", test_build_burst_structure);
    run_test("build_burst_deterministic", test_build_burst_deterministic);
    run_test("build_burst_wrong_length_throws", test_build_burst_wrong_length_throws);
    run_test("deinterleave_roundtrip_and_odd_throw", test_deinterleave_roundtrip_and_odd_throw);
    run_test("recover_identity", test_recover_identity);
    run_test("recover_gain_phase_fix9_values", test_recover_gain_phase_fix9_values);
    run_test("recover_timing_offset", test_recover_timing_offset);
    run_test("recover_cfo", test_recover_cfo);
    run_test("recover_sro", test_recover_sro);
    run_test("apply_sro_direction", test_apply_sro_direction);
    run_test("recover_preamble_not_tail", test_recover_preamble_not_tail);
    run_test("estimate_short_capture_invalid", test_estimate_short_capture_invalid);
    run_test("transfer_identity", test_transfer_identity);
    run_test("transfer_target_rms_scaleup", test_transfer_target_rms_scaleup);
    run_test("transfer_target_rms_refuse_clip", test_transfer_target_rms_refuse_clip);
    run_test("transfer_wrong_complex_count_throws", test_transfer_wrong_complex_count_throws);
    run_test("baseline_valid", test_baseline_valid);
    run_test("baseline_bad_sha_throws", test_baseline_bad_sha_throws);
    run_test("baseline_bad_role_throws", test_baseline_bad_role_throws);
    run_test("baseline_duplicate_throws", test_baseline_duplicate_throws);
    run_test("baseline_bad_class_throws", test_baseline_bad_class_throws);
    run_test("baseline_empty_throws", test_baseline_empty_throws);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
