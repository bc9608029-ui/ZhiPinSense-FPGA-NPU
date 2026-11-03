// test_m23_p0.cpp -- M23 P0 offline module tests (signal presence, parameter
// estimation, switchable OOD-U, four-way verdict, valid/stale "--").
//
// The milestone requires NUMERIC ERROR for each estimated parameter, not a bare
// PASS.  Every estimator test therefore prints
//     parameter   truth   estimate   error(=estimate-truth)
// and asserts a physical tolerance, so the offline numbers are reproducible and
// auditable.  Synthetic IQ comes from m23_iq_synth.hpp (known centre frequency,
// bandwidth, SNR, CFO).
//
// iCraft-free, libiio-free, header-only (plus the M20 OOD-U detector .cpp).
// Build/run: host_tests/build_m23_p0.sh / run_m23_p0.sh (standalone; does NOT
// touch M22's build_host_tests.sh / run_tests.sh).

#include "../sdr_adapter/m23_cfo.hpp"
#include "../sdr_adapter/m23_contract.hpp"
#include "../sdr_adapter/m23_iq_synth.hpp"
#include "../sdr_adapter/m23_ood_u_switch.hpp"
#include "../sdr_adapter/m23_params.hpp"
#include "../sdr_adapter/m23_verdict.hpp"
#include "../sdr_adapter/ood_u_contract.hpp"
#include "../sdr_adapter/ood_u_detector.hpp"
#include "../sdr_adapter/signal_presence.hpp"

#include <cmath>
#include <complex>
#include <cstdio>
#include <limits>
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

void report(const char* name, double truth, double estimate, double tol,
            const char* unit) {
    const double err = estimate - truth;
    std::printf("  %-16s truth=%12.3f est=%12.3f err=%+10.3f %s (tol=%g)\n",
                name, truth, estimate, err, unit, tol);
    check(std::fabs(err) <= tol, name);
}

constexpr double kFs = 128000.0;
constexpr std::size_t kN = 1024;

// --- (D) CFO estimation: numeric error, orders 1 / 2 / 4 ---------------------

void test_cfo_tone() {
    std::printf("CFO order 1 (tone):\n");
    const double carrier = 10000.0, cfo = 250.0, amp = 1000.0;
    const auto s = m23::make_tone(kN, kFs, carrier, cfo, amp, 40.0, 1234u);
    m23::CfoScratch scratch;
    const double est = m23::estimate_cfo(s.iq.data(), kN, kFs, carrier, 1, scratch);
    report("cfo_hz", cfo, est, 5.0, "Hz");
}

void test_cfo_bpsk() {
    std::printf("CFO order 2 (BPSK):\n");
    const double carrier = 8000.0, cfo = -120.0, amp = 1000.0;
    const auto s = m23::make_bpsk(kN, kFs, carrier, cfo, 8000.0, amp, 40.0, 5678u);
    m23::CfoScratch scratch;
    const double est = m23::estimate_cfo(s.iq.data(), kN, kFs, carrier, 2, scratch);
    report("cfo_hz", cfo, est, 20.0, "Hz");
}

void test_cfo_qpsk() {
    std::printf("CFO order 4 (QPSK):\n");
    const double carrier = 5000.0, cfo = 80.0, amp = 1000.0;
    const auto s = m23::make_qpsk(kN, kFs, carrier, cfo, 4000.0, amp, 40.0, 91011u);
    m23::CfoScratch scratch;
    const double est = m23::estimate_cfo(s.iq.data(), kN, kFs, carrier, 4, scratch);
    report("cfo_hz", cfo, est, 50.0, "Hz");
}

// CFO must be invalid (NaN) when there is no CFO reference configured.
void test_cfo_requires_reference() {
    std::printf("CFO no-reference -> invalid:\n");
    const auto s = m23::make_tone(kN, kFs, 10000.0, 250.0, 1000.0, 40.0, 1u);
    m23::M23ParamConfig cfg;
    cfg.sample_rate_hz = kFs;
    cfg.cfo_reference_set = false;  // default
    sdr::MeasureScratch ms;
    m23::CfoScratch cs;
    const m23::M23Params p = m23::estimate_params(s.iq.data(), kN, cfg, ms, cs);
    check(!p.cfo_hz.valid, "cfo invalid without reference");
    check(m23::render_param(p.cfo_hz, false) == "--", "cfo renders -- when invalid");
}

// --- (H) centre frequency / power / RMS / SNR / occupied BW ------------------

void test_center_frequency() {
    std::printf("Centre frequency (spectral centroid):\n");
    // Bin-aligned tone (16000 Hz == bin 128) so the centroid is exact.
    const auto s = m23::make_tone(kN, kFs, 16000.0, 0.0, 1000.0, 40.0, 42u);
    m23::M23ParamConfig cfg;
    cfg.sample_rate_hz = kFs;
    sdr::MeasureScratch ms;
    m23::CfoScratch cs;
    const m23::M23Params p = m23::estimate_params(s.iq.data(), kN, cfg, ms, cs);
    report("center_freq_hz", 16000.0, p.center_freq_hz.value, 20.0, "Hz");
}

void test_power_rms() {
    std::printf("Power / RMS (tone, no noise):\n");
    const double amp = 1000.0;
    const auto s = m23::make_tone(kN, kFs, 16000.0, 0.0, amp, 0.0, 7u);
    m23::M23ParamConfig cfg;
    cfg.sample_rate_hz = kFs;
    sdr::MeasureScratch ms;
    m23::CfoScratch cs;
    const m23::M23Params p = m23::estimate_params(s.iq.data(), kN, cfg, ms, cs);
    report("rms_counts", amp, p.rms.value, 1.0, "counts");
    report("power_dbfs", 20.0 * std::log10(amp / 2048.0), p.power_dbfs.value, 0.05, "dBFS");
}

void test_snr() {
    std::printf("SNR (tone + AWGN at 20 dB):\n");
    const double amp = 1000.0, snr = 20.0;
    const auto s = m23::make_tone(kN, kFs, 16000.0, 0.0, amp, snr, 99u);
    m23::M23ParamConfig cfg;
    cfg.sample_rate_hz = kFs;
    sdr::MeasureScratch ms;
    m23::CfoScratch cs;
    const m23::M23Params p = m23::estimate_params(s.iq.data(), kN, cfg, ms, cs);
    report("snr_db", snr, p.snr_db.value, 5.0, "dB");
}

void test_occupied_bw() {
    std::printf("Occupied bandwidth (two tones, 16 kHz span):\n");
    const double carrier = 16000.0, bw = 16000.0, amp = 1000.0;
    // No AWGN (snr=0) so the occupied-bin SPAN is deterministic: exactly the two
    // tone bins.  With noise, a single floor+10dB outlier at a far bin extends
    // the span -- a documented limitation of the DspMeasure span definition.
    const auto s = m23::make_two_tone(kN, kFs, carrier, bw, amp, 0.0, 2026u);
    m23::M23ParamConfig cfg;
    cfg.sample_rate_hz = kFs;
    sdr::MeasureScratch ms;
    m23::CfoScratch cs;
    const m23::M23Params p = m23::estimate_params(s.iq.data(), kN, cfg, ms, cs);
    // The estimator is bin-quantised: span == (max-min+1) bins, so the truth is
    // the exact span |f2-f1| and the error is exactly one bin width (125 Hz).
    report("occupied_bw_hz", bw, p.occupied_bw_hz.value, 250.0, "Hz");
}

void test_estimate_roundtrip() {
    std::printf("estimate_params flags on a valid tone:\n");
    const auto s = m23::make_tone(kN, kFs, 16000.0, 0.0, 1000.0, 40.0, 8u);
    m23::M23ParamConfig cfg;
    cfg.sample_rate_hz = kFs;
    cfg.cfo_reference_set = true;
    cfg.cfo_reference_hz = 16000.0;
    cfg.cfo_order = 1;
    sdr::MeasureScratch ms;
    m23::CfoScratch cs;
    const m23::M23Params p = m23::estimate_params(s.iq.data(), kN, cfg, ms, cs);
    check(p.power_dbfs.valid && p.rms.valid, "raw params valid");
    check(p.center_freq_hz.valid && p.snr_db.valid, "spectrum params valid");
    check(p.occupied_bw_hz.valid, "occupied BW valid (tone = 1 bin)");
    check(p.cfo_hz.valid, "CFO valid with reference set");
    check(!m23::render_param(p.center_freq_hz, false).empty() &&
              m23::render_param(p.center_freq_hz, false) != "--",
          "valid param renders a number");
}

// --- (D) presence state machine: hysteresis + consecutive confirmation -------

void test_presence_hysteresis() {
    std::printf("Presence hysteresis (confirm=3, lost=5):\n");
    sdr::PresenceConfig cfg;
    cfg.confirm_frames = 3;
    cfg.lost_frames = 5;
    sdr::SignalPresence sp(cfg);

    sdr::PresenceInput present;
    present.power_dbfs = -30.0;   // above enter (-55)
    sdr::PresenceInput absent;
    absent.power_dbfs = -90.0;    // below exit (-62)

    check(sp.update(absent) == sdr::PresenceState::NoSignal, "start no-signal");
    check(sp.update(present) == sdr::PresenceState::Acquiring, "1st hint acquiring");
    check(sp.update(present) == sdr::PresenceState::Acquiring, "2nd hint acquiring");
    check(sp.update(present) == sdr::PresenceState::SignalPresent, "3rd hint present");

    // Hysteresis: a single below-exit sample does NOT drop a confirmed signal.
    check(sp.update(absent) == sdr::PresenceState::SignalPresent, "1 dropout holds");
    check(sp.update(absent) == sdr::PresenceState::SignalPresent, "2 dropout holds");
    check(sp.update(absent) == sdr::PresenceState::SignalPresent, "3 dropout holds");
    check(sp.update(absent) == sdr::PresenceState::SignalPresent, "4 dropout holds");
    check(sp.update(absent) == sdr::PresenceState::SignalLost, "5th dropout lost");

    // NaN/Inf forces INVALID and resets.
    sdr::PresenceInput bad;
    bad.power_dbfs = -30.0;
    bad.nan_inf = true;
    check(sp.update(bad) == sdr::PresenceState::Invalid, "NaN input -> invalid");
}

// --- four-way verdict: strict separation ------------------------------------

void test_verdict_composition() {
    std::printf("Four-way verdict composition:\n");
    using sdr::PresenceState;
    using m23::Verdict;
    check(m23::compose(PresenceState::Invalid, false, false, false) == Verdict::Error,
          "INVALID -> ERROR");
    check(m23::compose(PresenceState::SignalPresent, false, false, false) ==
              Verdict::SignalPresent,
          "present + OOD off -> SIGNAL_PRESENT");
    check(m23::compose(PresenceState::SignalPresent, true, false, false) ==
              Verdict::SignalPresent,
          "present + OOD on + accept -> SIGNAL_PRESENT");
    check(m23::compose(PresenceState::SignalPresent, true, true, false) ==
              Verdict::UnknownExperimental,
          "present + OOD on + reject -> UNKNOWN_EXPERIMENTAL");
    check(m23::compose(PresenceState::SignalPresent, true, false, true) == Verdict::Error,
          "present + OOD on + OOD error -> ERROR");
    check(m23::compose(PresenceState::NoSignal, false, false, false) == Verdict::NoSignal,
          "NO_SIGNAL");
    check(m23::compose(PresenceState::Acquiring, false, false, false) == Verdict::NoSignal,
          "ACQUIRING collapsed -> NO_SIGNAL");
    check(m23::compose(PresenceState::SignalLost, false, false, false) == Verdict::NoSignal,
          "SIGNAL_LOST collapsed -> NO_SIGNAL");
    check(std::string(m23::verdict_name(Verdict::NoSignal)) == m23::NO_SIGNAL,
          "verdict_name(NO_SIGNAL)");
    check(std::string(m23::verdict_name(Verdict::UnknownExperimental)) ==
              m23::UNKNOWN_EXPERIMENTAL,
          "verdict_name(UNKNOWN_EXPERIMENTAL)");
}

// --- (C) OOD-U switch: default OFF == M22 argmax ----------------------------

OodThresholdManifest frozen_manifest() {
    OodThresholdManifest m;
    m.model_name = ood_u_contract::MODEL_NAME;
    m.model_sha256 = ood_u_contract::MODEL_SHA256;
    m.checkpoint_sha256 = std::string(64, 'a');  // valid 64-hex placeholder
    m.score_method = "logit_margin";
    m.score_direction = ood_u_contract::DIRECTION;
    m.temperature = 1.0;
    m.threshold = m23::OOD_U_FROZEN_THRESHOLD_LOGIT_MARGIN;
    m.label_order.assign(ood_u_contract::LABEL_ORDER_12.begin(),
                         ood_u_contract::LABEL_ORDER_12.end());
    m.final_test_accessed = false;
    return m;
}

void test_ood_default_off_is_argmax() {
    std::printf("OOD-U default OFF == M22 plain argmax:\n");
    m23::M23OodSwitch sw;  // default: disabled
    check(!sw.enabled(), "switch disabled by default");

    const double logits[12] = {0.1, 0.2, 0.05, 0.0, 0.3, 2.5, 0.0,
                               0.0, 0.0, 0.0, 0.0, 0.1};
    const m23::OodSwitchResult r = sw.classify(logits, 12);
    check(!r.enabled, "result not from OOD-U");
    check(!r.rejected && !r.error, "no reject / no error");
    check(r.class_index == 5, "argmax == 5 (byte-identical to M22)");

    // Float overload matches.
    const float flogits[12] = {0.1f, 0.2f, 0.05f, 0.0f, 0.3f, 2.5f, 0.0f,
                               0.0f, 0.0f, 0.0f, 0.0f, 0.1f};
    const m23::OodSwitchResult rf = sw.classify(flogits, 12);
    check(rf.class_index == 5, "float overload argmax == 5");
}

void test_ood_enabled_accept_reject_error() {
    std::printf("OOD-U enabled (logit_margin, frozen threshold):\n");
    m23::M23OodSwitch sw;
    sw.enable(frozen_manifest());
    check(sw.enabled(), "switch enabled");

    // High-confidence logits -> accepted known class.
    double high[12] = {0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
    const m23::OodSwitchResult a = sw.classify(high, 12);
    check(a.enabled && !a.rejected && !a.error, "high-confidence accepted");
    check(a.class_index == 5, "accepted class 5");

    // Uniform logits -> score 0 > threshold -> rejected.
    double flat[12];
    for (auto& v : flat) v = 1.0;
    const m23::OodSwitchResult b = sw.classify(flat, 12);
    check(b.enabled && b.rejected && !b.error, "uniform logits rejected");
    check(b.class_index == -1, "rejected -> no class index");

    // Non-finite logits -> ERROR.
    double bad[12];
    for (auto& v : bad) v = 0.0;
    bad[0] = std::numeric_limits<double>::quiet_NaN();
    const m23::OodSwitchResult c = sw.classify(bad, 12);
    check(c.enabled && c.error && !c.rejected, "non-finite -> error");

    // The rejected frame composes into UNKNOWN_EXPERIMENTAL.
    check(m23::compose(sdr::PresenceState::SignalPresent, true, true, false) ==
              m23::Verdict::UnknownExperimental,
          "rejected + present -> UNKNOWN_EXPERIMENTAL");

    // Disabling returns to the plain argmax path.
    sw.disable();
    check(!sw.enabled(), "switch disabled again");
    const m23::OodSwitchResult d = sw.classify(flat, 12);
    check(!d.enabled && !d.rejected && !d.error, "disabled -> plain argmax again");
}

void test_ood_disabled_threshold_safe_boundary() {
    std::printf("OOD-U +1e30 threshold == disabled (safe boundary):\n");
    OodThresholdManifest m = frozen_manifest();
    m.threshold = m23::OOD_DISABLED_THRESHOLD;  // +1e30 can never reject
    m23::M23OodSwitch sw;
    sw.enable(m);
    double flat[12];
    for (auto& v : flat) v = 1.0;
    const m23::OodSwitchResult r = sw.classify(flat, 12);
    check(r.enabled && !r.rejected && !r.error, "no reject at +1e30 threshold");
    check(r.class_index == 0, "still argmax (ties keep lower index)");
}

// --- valid / stale "--" ------------------------------------------------------

void test_valid_stale() {
    std::printf("valid / stale rendering (--):\n");
    const m23::ParamEstimate invalid{0.0, false};
    const m23::ParamEstimate valid{3.14159, true};
    check(m23::render_param(invalid, false) == "--", "invalid -> --");
    check(m23::render_param(valid, true) == "--", "stale -> --");
    check(m23::render_param(valid, false) == "3.142", "valid+not-stale -> number");

    m23::M23ParamState st;
    check(st.stale(0), "never refreshed -> stale");
    m23::M23Params p;
    p.power_dbfs = m23::ParamEstimate{-20.0, true};
    st.refresh(100, p);
    check(!st.stale(100), "fresh at frame 100");
    check(!st.stale(105), "age 5 still valid");
    check(st.stale(106), "age 6 -> stale");
    check(m23::render_param(p.power_dbfs, st.stale(106)) == "--", "stale power -> --");
}

}  // namespace

int main() {
    std::printf("test_m23_p0\n");
    test_cfo_tone();
    test_cfo_bpsk();
    test_cfo_qpsk();
    test_cfo_requires_reference();
    test_center_frequency();
    test_power_rms();
    test_snr();
    test_occupied_bw();
    test_estimate_roundtrip();
    test_presence_hysteresis();
    test_verdict_composition();
    test_ood_default_off_is_argmax();
    test_ood_enabled_accept_reject_error();
    test_ood_disabled_threshold_safe_boundary();
    test_valid_stale();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
