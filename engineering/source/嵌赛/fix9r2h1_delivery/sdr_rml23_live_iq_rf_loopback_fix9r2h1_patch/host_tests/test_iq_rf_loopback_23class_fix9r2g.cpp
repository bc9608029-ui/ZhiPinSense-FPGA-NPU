// test_iq_rf_loopback_23class_fix9r2g.cpp -- host tests for Route F fix9r2g (the
// merged minimal functional fix: a common, deterministic, label-free, narrowband
// MODULATED payload-domain gain training block that estimates the FINAL complex
// scalar gain; the ZC preamble stays the sync / CFO / SRO reference and its residual
// is demoted to instrument-only).  iCraft-free and libiio-free: it exercises the
// exact pure code the board runner calls -- iq_rf_training_frame.hpp /
// iq_rf_tx_provenance.hpp / iq_rf_sync_recovery.hpp / iq_rf_fix9r2a_diagnostic.hpp /
// iq_rf_fix9r2b_diagnostic.hpp / iq_rf_fix9r_baseline.hpp /
// iq_rf_loopback_transfer_fix9r.hpp -- plus the FakePlutoDevice external-RF echo.
//
// WHY THIS EXISTS (fix9r2e root cause FIXED_SCALE_JUMP): the constant-envelope ZC
// preamble and the modulated payload see DIFFERENT forward gains (2.5x, +8 dB) and
// DIFFERENT residuals (full-band ZC -> ~0.23 from channel ripple; narrowband payload
// -> ~3% clean scalar).  A single preamble scalar therefore cannot recover the
// payload.  This test proves: (1) the training block is modulated AND narrowband
// (envelope + spectrum both match the payload); (2) build_burst/verify_frame place it
// at offset 2048 with a 1024 settling-zero guard; (3) the recovery estimates the
// payload gain from the training block, recovers the payload to <=5% scale error, and
// would be ~147% off using the old preamble gain; (4) the preamble residual is now
// instrument-only (a >0.10 residual no longer flips valid); (5) corr/gain/residual
// share the same CFO/SRO de-ramp; (6) an invalid recovery fail-closes; (7) the gate
// folds the new fields; (8) the frozen baseline TSV loads by exact key; (9) the RX
// gain-mode endpoints are logged (no gate/throw).

#include "../board_package/iq_rf_training_frame.hpp"
#include "../board_package/iq_rf_sync_recovery.hpp"
#include "../board_package/iq_rf_tx_provenance.hpp"
#include "../board_package/iq_rf_fix9r2a_diagnostic.hpp"
#include "../board_package/iq_rf_fix9r2b_diagnostic.hpp"
#include "../board_package/iq_rf_fix9r_baseline.hpp"
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
#include <map>
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

// deterministic PRBS payload (same LCG as the other fix9r host tests)
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

void write_text(const std::string& path, const std::string& text) {
    std::ofstream f(path, std::ios::binary);
    f.write(text.data(), static_cast<std::streamsize>(text.size()));
    f.close();
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

// Apply a per-region forward gain (g1 = constant-envelope ZC preamble/settling/tail,
// g2 = modulated training-block + payload) plus a linear CFO ramp anchored at n=0,
// plus optional additive noise.  Reproduces the fix9r2e FIXED_SCALE_JUMP mechanism.
std::vector<std::complex<double>> apply_gain_jump_and_cfo(
        const std::vector<std::complex<double>>& base,
        double g1, double g2, double cfo_hz, double noise_rms, std::uint32_t seed) {
    std::vector<std::complex<double>> rx(base.size());
    std::uint32_t s = seed;
    auto rng = [&s]() -> double {
        s = s * 1664525u + 1013904223u;
        return (static_cast<double>(s >> 8) / 8388607.0) - 1.0;   // [-1, 1)
    };
    for (std::size_t n = 0; n < base.size(); ++n) {
        double g;
        if (n < iqrftrain::kPayloadTrainingOffset) g = g1;                     // preamble + settling-zero
        else if (n < iqrftrain::kPayloadStart + iqrftrain::kPayloadComplex) g = g2;  // training + payload
        else g = g1;                                                           // guard-after + tail
        const double ph = 2.0 * kPi * cfo_hz * static_cast<double>(n) /
                          static_cast<double>(iqrftrain::kFs);
        rx[n] = base[n] * g * std::polar(1.0, ph);
        if (noise_rms > 0.0)
            rx[n] += std::complex<double>(noise_rms * rng(), noise_rms * rng());
    }
    return rx;
}

// Synthesize a sampling-rate-offset signal: rx[n] = base[n/(1+s)] (linear interp,
// zero beyond base).  Matches the SRO model rx[n] == tx[n/(1+s)] used by estimate()
// and apply().
std::vector<std::complex<double>> resample_sro(
        const std::vector<std::complex<double>>& base, double s, std::size_t cap) {
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
    return rx;
}

// ---- 1. training-block generation --------------------------------------------

void test_training_block_generation() {
    check(std::fabs(iqrfrec::kPayloadTrainingResidualMax - 0.10) < 1e-12,
          "gate: shared R8/R9 payload-training residual limit is 0.10");
    const auto iq = iqrftrain::payload_gain_training();
    check(iq.size() == iqrftrain::kPayloadTrainingComplex * 2,
          "pt: length 2048 (interleaved int16)");
    check(iq == iqrftrain::payload_gain_training(), "pt: deterministic (two runs equal)");

    // The transfer's --rf-tx-target-rms is measured across interleaved I/Q components.
    // Therefore the pilot complex RMS is sqrt(2)*2048 and component RMS is 2048.
    double e = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const double I = static_cast<double>(iq[k * 2]);
        const double Q = static_cast<double>(iq[k * 2 + 1]);
        e += I * I + Q * Q;
    }
    const double rms = std::sqrt(e / static_cast<double>(iqrftrain::kPayloadTrainingComplex));
    check(std::fabs(rms - 2896.309375740099) < 20.0,
          "pt: complex-magnitude RMS ~= sqrt(2)*2048");
    check(std::fabs(rms / std::sqrt(2.0) - 2048.0) < 20.0,
          "pt: interleaved-component RMS ~= 2048 (matches TX target contract)");

    // modulated (crest factor > 1 dB): 16QAM peak |z| ~ sqrt(1.8)*RMS, not a
    // constant-envelope block like the ZC preamble.
    double peak2 = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const double I = static_cast<double>(iq[k * 2]);
        const double Q = static_cast<double>(iq[k * 2 + 1]);
        peak2 = std::max(peak2, I * I + Q * Q);
    }
    const double crest_db = 10.0 * std::log10(peak2 / (rms * rms));
    check(crest_db > 1.0, "pt: crest factor > 1 dB (modulated, not constant-envelope)");

    // complex reference DERIVED from the int16 block (no independent float path)
    const auto c = iqrftrain::payload_gain_training_complex();
    check(c.size() == iqrftrain::kPayloadTrainingComplex, "pt: complex length 1024");
    bool exact = true;
    for (std::size_t k = 0; k < c.size(); ++k) {
        const std::complex<double> want(static_cast<double>(iq[k * 2]),
                                        static_cast<double>(iq[k * 2 + 1]));
        if (c[k] != want) { exact = false; break; }
    }
    check(exact, "pt: complex reference bit-identical to int16 (single source)");
}

// ---- 2. build_burst + verify_frame layout ------------------------------------

void test_burst_layout_and_verify() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 51);
    const auto burst = iqrftrain::build_burst(payload);
    check(burst.size() == iqrftrain::kTotalBurstComplex * 2,
          "burst: total length 59904 complex (unchanged)");

    const iqrftxprov::TxFrameVerify v = iqrftxprov::verify_frame(burst, payload);
    check(v.ok, "vf: ok");
    check(v.training_exact_match, "vf: preamble@0 + tail@kTailStart match");
    check(v.settling_guard_exact_zero, "vf: settling-zero zone all zero");
    check(v.payload_training_exact_match, "vf: training block exact match");
    check(v.payload_exact_match, "vf: payload exact match");
    check(v.frame_layout_match, "vf: guard-after zero");

    // training block sits at absolute offset kPayloadTrainingOffset (2048..3072 complex)
    const auto pt = iqrftrain::payload_gain_training();
    const std::size_t toff = iqrftrain::kPayloadTrainingOffset * 2;
    check(std::equal(pt.begin(), pt.end(), burst.begin() + toff),
          "burst: training block at offset 2048 (int16)");

    // settling-zero region [kPreambleComplex, kPayloadTrainingOffset) all zero
    bool settle_zero = true;
    for (std::size_t k = iqrftrain::kPreambleComplex * 2;
         k < iqrftrain::kPayloadTrainingOffset * 2; ++k) {
        if (burst[k] != 0) { settle_zero = false; break; }
    }
    check(settle_zero, "burst: settling-zero [1024,2048) zero (isolates ZC transient)");
}

// ---- 3. core regression: the gain jump (payload gain recovers; old gain ~147% off) ----

void test_gain_jump_recovery() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 52);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    const double g1 = 0.015, g2 = 0.037;   // fix9r2e measured preamble/payload gains
    const double cfo = 5.0;                 // small CFO, within the unambiguous range

    const auto rx = apply_gain_jump_and_cfo(base, g1, g2, cfo, 1.0, 0xABCDEF01u);
    const auto rec = iqrfrec::estimate(rx);

    check(rec.valid, "gainjump: valid");
    check(rec.failure == iqrfrec::Failure::NONE, "gainjump: failure NONE");
    check(std::fabs(rec.payload_gain_mag - g2) / g2 < 0.05,
          "gainjump: payload_gain_mag ~= 0.037 (training-block LS gain)");
    check(std::fabs(rec.gain_mag - g1) / g1 < 0.05,
          "gainjump: preamble gain_mag ~= 0.015 (instrument-only)");

    const double ratio = rec.payload_gain_mag / rec.gain_mag;
    check(ratio > 2.2 && ratio < 2.7, "gainjump: 2.5x jump ratio (payload/preamble)");

    // de-ramped corr stays high WITH the CFO present (same-correction proof)
    check(rec.payload_training_corr > 0.99, "gainjump: de-ramped training corr > 0.99");

    // apply() (payload gain) recovers the payload to <= 5% scale error
    const auto out = iqrfrec::apply(rx, rec);
    const auto ref = iqrftrain::deinterleave(payload);
    const double se = iqrffix9r2b::payload_scale_error(out, ref);
    check(se <= 0.05, "gainjump: apply() scale error <= 5%");

    // the OLD preamble gain would recover ~2.5x off (~147% scale error)
    auto old = rec;
    old.payload_gain_mag = rec.gain_mag;
    old.payload_phase_deg = rec.phase_deg;
    const auto old_out = iqrfrec::apply(rx, old);
    const double old_se = iqrffix9r2b::payload_scale_error(old_out, ref);
    check(old_se > 1.0, "gainjump: old preamble-gain recovery > 100% off (~147%)");
}

// ---- 3b. digital TX scaling is part of the end-to-end amplitude contract -------

void test_tx_scale_round_trip() {
    const auto original = make_prbs(iqrftrain::kPayloadComplex, 1000, 521);
    constexpr double tx_scale = 2.0;
    auto transmitted = original;
    for (auto& sample : transmitted)
        sample = static_cast<std::int16_t>(std::lround(sample * tx_scale));

    const auto burst = iqrftrain::build_burst(transmitted);
    const auto base = iqrftrain::deinterleave(burst);
    constexpr double rf_gain = 0.02;
    const auto rx = apply_gain_jump_and_cfo(base, rf_gain, rf_gain, 0.0, 0.0,
                                             0x13579BDFu);
    auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "txscale: recovery valid");
    rec.payload_tx_scale = tx_scale;

    const auto recovered = iqrfrec::apply(rx, rec);
    const auto reference = iqrftrain::deinterleave(original);
    check(iqrffix9r2b::payload_scale_error(recovered, reference) < 1e-6,
          "txscale: apply undoes known digital TX scale");
    check(iqrffix9r2b::payload_scale_error(
              iqrffix9r2b::provisional_apply_scalar(rx, rec), reference) < 1e-6,
          "txscale: diagnostic recovery uses identical TX-scale contract");

    auto uncompensated = rec;
    uncompensated.payload_tx_scale = 1.0;
    check(iqrffix9r2b::payload_scale_error(
              iqrfrec::apply(rx, uncompensated), reference) > 0.99,
          "txscale: old path leaves payload approximately 2x too large");
}

// ---- 4. residual demotion: preamble residual is instrument-only ---------------

void test_residual_demotion() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 53);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);

    // a frequency-selective channel (two-tap echo) ripples the full-band ZC preamble
    // (single-scalar fit leaves a large residual) but is ~flat across the narrowband
    // training block (small residual).  This is the fix9r2e 6.6 dB channel ripple.
    const double a = 0.15;
    const std::size_t cap = base.size() + 8192;
    std::vector<std::complex<double>> rx(cap, 0.0);
    rx[0] = base[0] / (1.0 + a);
    for (std::size_t n = 1; n < base.size(); ++n)
        rx[n] = (base[n] + a * base[n - 1]) / (1.0 + a);

    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "demotion: valid (training block clean)");
    check(rec.failure == iqrfrec::Failure::NONE, "demotion: failure NONE");
    check(rec.training_residual > 0.10,
          "demotion: preamble residual > 0.10 (reported, instrument-only)");
    check(rec.payload_training_residual <= 0.05,
          "demotion: training-block residual <= 0.05 (the migrated gate)");
}

// ---- 5. corr/gain/residual share the same CFO/SRO de-ramp ---------------------

void test_sro_deramp() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 54);
    const auto burst = iqrftrain::build_burst(payload);
    const auto base = iqrftrain::deinterleave(burst);
    // SRO must stay bounded: the step-1 preamble corr is computed on the UN-stretched
    // reference, so a too-large SRO decorrelates the ZC preamble below the 0.90 sync
    // gate (~466 ppm theoretical limit).  350 ppm leaves the preamble corr ~0.97 and
    // still shows a clear de-ramp effect on the narrowband training block.
    const double s = 350.0e-6;
    const auto rx = resample_sro(base, s, iqrftrain::kTotalBurstComplex + 8192);

    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "sro: valid");
    check(rec.failure == iqrfrec::Failure::NONE, "sro: failure NONE");
    check(std::fabs(rec.sro_ppm - 350.0) < 40.0, "sro: sro_ppm ~= 350");

    // the de-ramped gain is accurate (an un-stretched reference would be measurably
    // low: the stretch maps the RX index back onto the TX reference)
    check(std::fabs(rec.payload_gain_mag - 1.0) < 0.05,
          "sro: de-ramped payload_gain_mag ~= 1.0 (identity)");

    // de-ramped training-block corr is high and beats the UNCORRECTED normalized_corr
    const auto pt = iqrftrain::payload_gain_training_complex();
    const double uncorr = iqrfrec::detail::normalized_corr(
        rx, rec.timing_offset + iqrftrain::kPayloadTrainingOffset, pt);
    check(rec.payload_training_corr > 0.99, "sro: de-ramped corr > 0.99");
    check(rec.payload_training_corr > uncorr + 0.005,
          "sro: de-ramped corr > uncorrected corr (same-correction proof)");
}

// ---- 6. illegal gain fail-closed ----------------------------------------------

void test_illegal_gain_fail_closed() {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 55);
    const auto burst = iqrftrain::build_burst(payload);
    const auto rx = iqrftrain::deinterleave(burst);
    const auto rec = iqrfrec::estimate(rx);
    check(rec.valid, "failclosed: identity valid");

    // invalid recovery (failure set) -> apply() throws, provisional returns empty
    iqrfrec::PerFileRecovery bad = rec;
    bad.valid = false;
    bad.failure = iqrfrec::Failure::PAYLOAD_TRAINING_NOT_FOUND;
    bool apply_threw = false;
    try { (void)iqrfrec::apply(rx, bad); }
    catch (const std::runtime_error&) { apply_threw = true; }
    check(apply_threw, "failclosed: apply() throws on invalid (no silent unit gain)");
    check(iqrffix9r2b::provisional_apply_scalar(rx, bad).empty(),
          "failclosed: provisional_apply_scalar returns empty on invalid");

    // "valid" but unsafe gain -> apply()'s defensive check still throws
    iqrfrec::PerFileRecovery zero = rec;
    zero.valid = true;
    zero.payload_gain_mag = 0.0;
    bool zero_threw = false;
    try { (void)iqrfrec::apply(rx, zero); }
    catch (const std::runtime_error&) { zero_threw = true; }
    check(zero_threw, "failclosed: apply() throws on unsafe payload gain");
}

// ---- 7. gate folding: new fields ----------------------------------------------

iqrffix9r2a::DiagnosticGateInput make_good_gate() {
    iqrffix9r2a::DiagnosticGateInput g;
    g.requested_classes = "BPSK,4ASK";
    g.selected_classes = "BPSK,4ASK";
    g.requested_count = 2;
    g.holdout_files = 2;
    g.estimate_computed = 2;
    g.estimate_valid = 2;
    g.frame_layout_match = 2;
    g.training_exact_match = 2;
    g.settling_guard_exact_zero = 2;
    g.payload_training_exact_match = 2;
    g.payload_exact_match = 2;
    g.tx_push_ok = 2;
    g.tx_clipped = 0;
    g.rx_clipped = 0;
    g.training_corr_min = 0.999;
    g.payload_training_residual_max = 0.001;
    g.payload_scale_error_max = 0.01;
    g.scored = 2;
    g.rf_excluded = 0;
    g.prediction_agreement = 2;
    g.restore_ok = true;
    return g;
}

void test_gate_folding() {
    check(iqrffix9r2a::evaluate_diagnostic_gate(make_good_gate()).pass,
          "gate: good gate PASS");

    {
        auto g = make_good_gate();
        g.payload_training_residual_max = 0.11;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: payload_training_residual_max > 0.10 FAIL");
    }
    {
        auto g = make_good_gate();
        g.payload_scale_error_max = 0.06;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: payload_scale_error_max > 0.05 FAIL");
    }
    {
        auto g = make_good_gate();
        g.rf_excluded = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: rf_excluded != 0 FAIL");
    }
    {
        auto g = make_good_gate();
        g.scored = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: scored != holdout FAIL");
    }
    {
        auto g = make_good_gate();
        g.prediction_agreement = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: prediction_agreement != holdout FAIL");
    }
    {
        auto g = make_good_gate();
        g.settling_guard_exact_zero = 0;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: settling_guard_exact_zero != holdout FAIL");
    }
    {
        auto g = make_good_gate();
        g.payload_training_exact_match = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: payload_training_exact_match != holdout FAIL");
    }
}

// ---- 8. frozen baseline TSV load (exact key, fail-closed) ---------------------

const std::string kSha64 = std::string(64, 'a');   // lowercase 64-hex

void test_baseline_tsv_load() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r2g_base");
    const std::string path = dir + "/baseline.tsv";

    const std::string good =
        "source_index\toriginal_sha256\tdeployed_class\tmodulation\tsplit_role\tfrozen_baseline_pred\n"
        "0\t" + kSha64 + "\t0\tBPSK\tholdout\t5\n"
        "1\t" + kSha64 + "\t2\t4ASK\tholdout\t7\n";
    write_text(path, good);

    const auto m = iqrffix9r::load_baseline(path, 23);
    check(m.size() == 2, "base: 2 rows");
    check(m.at(0).frozen_baseline_pred == 5 && m.at(0).deployed_class == 0,
          "base: source 0 baseline_pred=5 deployed=0");
    check(m.at(1).frozen_baseline_pred == 7 && m.at(1).deployed_class == 2,
          "base: source 1 baseline_pred=7 deployed=2");
    check(m.at(0).frozen_baseline_pred != m.at(0).deployed_class,
          "base: frozen_baseline_pred != deployed_class (never a fallback)");

    // the two R8 fields are independent: rf_pred matching the frozen baseline is
    // "agreement"; rf_pred matching the true deployed_class is "correct".  Here a
    // prediction of 5 AGREES with the baseline (5) but is INCORRECT (deployed 0).
    const int rf_pred = 5;
    const bool agreement = (rf_pred == m.at(0).frozen_baseline_pred);
    const bool label_correct = (rf_pred == m.at(0).deployed_class);
    check(agreement && !label_correct,
          "base: agreement(correct) independent of label_correct");

    // duplicate source_index -> fail-closed
    write_text(path, "h\n0\t" + kSha64 + "\t0\tBPSK\tholdout\t5\n0\t" + kSha64 +
                     "\t0\tBPSK\tholdout\t5\n");
    bool threw = false;
    try { (void)iqrffix9r::load_baseline(path, 23); }
    catch (const std::runtime_error&) { threw = true; }
    check(threw, "base: duplicate source_index throws");

    // non-64-hex sha -> fail-closed
    write_text(path, "h\n0\tdeadbeef\t0\tBPSK\tholdout\t5\n");
    threw = false;
    try { (void)iqrffix9r::load_baseline(path, 23); }
    catch (const std::runtime_error&) { threw = true; }
    check(threw, "base: bad sha throws");

    // out-of-range frozen_baseline_pred -> fail-closed
    write_text(path, "h\n0\t" + kSha64 + "\t0\tBPSK\tholdout\t99\n");
    threw = false;
    try { (void)iqrffix9r::load_baseline(path, 23); }
    catch (const std::runtime_error&) { threw = true; }
    check(threw, "base: out-of-range frozen_baseline_pred throws");

    // split_role != holdout -> fail-closed
    write_text(path, "h\n0\t" + kSha64 + "\t0\tBPSK\tcalibration\t5\n");
    threw = false;
    try { (void)iqrffix9r::load_baseline(path, 23); }
    catch (const std::runtime_error&) { threw = true; }
    check(threw, "base: split_role != holdout throws");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 9. RX gain-mode endpoints logged (no gate, no throw) ---------------------

void test_rx_gain_log() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_fix9r2g_gain");
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 61);
    const std::string sha = write_ci16(dir, "gain.ci16", payload);
    const std::string path = dir + "/gain.ci16";
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

    check(tr.rx_gain_mode_before_capture == "manual", "rxgain: mode before == manual");
    check(tr.rx_gain_mode_after_capture == "manual", "rxgain: mode after == manual");
    check(tr.rx_gain_mode_before_capture == tr.rx_gain_mode_after_capture,
          "rxgain: mode unchanged across capture");
    check(std::fabs(tr.rx_gain_before_capture - 10.0) < 1e-9, "rxgain: gain before == 10");
    check(std::fabs(tr.rx_gain_after_capture - 10.0) < 1e-9, "rxgain: gain after == 10");
    check(tr.rx_gain_before_capture == tr.rx_gain_after_capture,
          "rxgain: gain unchanged across capture");

    ::unlink(path.c_str());
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
    std::printf("test_iq_rf_loopback_23class_fix9r2g\n");
    run_test("training_block_generation", test_training_block_generation);
    run_test("burst_layout_and_verify", test_burst_layout_and_verify);
    run_test("gain_jump_recovery", test_gain_jump_recovery);
    run_test("tx_scale_round_trip", test_tx_scale_round_trip);
    run_test("residual_demotion", test_residual_demotion);
    run_test("sro_deramp", test_sro_deramp);
    run_test("illegal_gain_fail_closed", test_illegal_gain_fail_closed);
    run_test("gate_folding", test_gate_folding);
    run_test("baseline_tsv_load", test_baseline_tsv_load);
    run_test("rx_gain_log", test_rx_gain_log);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
