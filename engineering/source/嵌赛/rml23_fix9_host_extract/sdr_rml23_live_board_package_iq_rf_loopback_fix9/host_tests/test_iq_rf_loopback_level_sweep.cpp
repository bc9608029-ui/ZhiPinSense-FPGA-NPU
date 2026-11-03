// test_iq_rf_loopback_level_sweep.cpp -- host tests for Stage H-F / Route F fix8
// Task C: the PHYSICAL RF SAFE-OPERATING-POINT level sweep (NO labels, NO NPU).
//
// Exercises, in order:
//   * the deterministic sweep waveforms (tone / PRBS / QPSK) and their RMS
//     normalization (make_rf_level_waveform + scale_to_rms + rms_magnitude);
//   * the safe-operating-point SELECTION (select_rf_level): largest clip-free
//     high-fidelity TX level whose best RX gain keeps the median RX RMS inside the
//     safe window, the gain-nearest-target tie-break, and the label-independence of
//     the selection (a swap of the waveform "kind" -- which is NOT a RadioML label
//     -- never changes the recommendation);
//   * the fail-closed cases: all-clip, low-correlation, and failed-negative-control
//     points are excluded (never recommended), so a degenerate sweep yields
//     ok == false (NOT_PROVEN, never a fabricated operating point);
//   * the full end-to-end sweep (sweep_rf_levels) against the FakePlutoDevice RF
//     echo, proving the whole grid runs against the real PlutoTx safety machine and
//     recommends the LARGEST clip-free level under a fixed complex RF gain.
//
// iCraft-free and libiio-free.  The end-to-end test links ../sdr_adapter/pluto_tx.cpp
// (the real PlutoTx safety state machine) against the scriptable FakePlutoDevice.

#include "../board_package/iq_rf_loopback_level_sweep.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// A 16-bit identity data format: rails +/-32767, so the sweep levels (<= 8192) are
// far from the TX clip rail and the SELECTION is exercised at the RX-safe-window
// boundary rather than the 12-bit clip boundary.
pluto::DataFormatInfo identity_fmt() {
    pluto::DataFormatInfo f;
    f.length_bits = 16;
    f.bits = 16;
    f.shift = 0;
    f.is_signed = true;
    f.is_fully_defined = true;
    return f;
}

// A point with the fields select_rf_level actually reads (measured fidelity only --
// there is no label field on the struct).
iqrfloop_sweep::RfLevelSweepPoint mk(double level, double gain, double rx_rms,
                                    double corr = 1.0, bool tx_clip = false,
                                    bool rx_clip = false, bool capture = true,
                                    bool nc = true) {
    iqrfloop_sweep::RfLevelSweepPoint p;
    p.kind = "tone";
    p.level_counts = level;
    p.rx_gain_db = gain;
    p.rx_rms = rx_rms;
    p.corr = corr;
    p.tx_clipped = tx_clip;
    p.rx_clipped = rx_clip;
    p.capture_ok = capture;
    p.negative_control_ok = nc;
    return p;
}

// ---- 1. sweep waveforms scale to the requested RMS and are deterministic ----
void test_waveform_rms_target() {
    const std::size_t n = 2048;
    const char* kinds[] = {"tone", "prbs", "qpsk"};
    const double targets[] = {512.0, 2048.0, 8192.0};
    for (const char* k : kinds) {
        for (double t : targets) {
            const auto w = iqrfloop_sweep::make_rf_level_waveform(k, t, n);
            const double rms = iqrfloop_sweep::rms_magnitude(w);
            check(std::fabs(rms - t) <= 0.01 * t + 0.5,
                  std::string("waveform-rms: ") + k + " " + std::to_string(t));
            // Identical inputs -> identical bytes (deterministic, reproducible).
            const auto w2 = iqrfloop_sweep::make_rf_level_waveform(k, t, n);
            check(w == w2, std::string("waveform-det: ") + k + " " + std::to_string(t));
        }
    }
}

// ---- 2. selection picks the LARGEST clip-free high-fidelity level ------------
void test_select_largest_clip_free_level() {
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> pts;
    pts.push_back(mk(512, 10, 51.0));
    pts.push_back(mk(2048, 10, 205.0));
    pts.push_back(mk(4096, 10, 410.0));   // largest clip-free high-fidelity level
    const auto s = iqrfloop_sweep::select_rf_level(pts);
    check(s.ok, "select: ok");
    check(std::fabs(s.recommended_rms_counts - 4096.0) < 1e-6,
          "select: recommends the largest level (4096)");
}

// ---- 3. a clipped higher level is skipped in favour of the next largest ------
void test_select_skips_clipped() {
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> pts;
    pts.push_back(mk(512, 10, 51.0));
    pts.push_back(mk(4096, 10, 410.0, 1.0, /*tx_clip=*/true));
    pts.push_back(mk(2048, 10, 205.0));
    const auto s = iqrfloop_sweep::select_rf_level(pts);
    check(s.ok && std::fabs(s.recommended_rms_counts - 2048.0) < 1e-6,
          "select: skips a clipped level and recommends 2048");
}

// ---- 4. selection is label-independent (kind is NOT a RadioML label) ---------
// The sweep never uses a label to pick the operating point: swapping the synthetic
// waveform "kind" string (tone/prbs/qpsk) -- which carries no RadioML class -- must
// leave the recommendation byte-for-byte unchanged, because select_rf_level reads
// only the measured fidelity.
void test_select_no_labels() {
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> a;
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> b;
    for (double lvl : {512.0, 2048.0, 4096.0}) {
        iqrfloop_sweep::RfLevelSweepPoint pa = mk(lvl, 20, lvl / 10.0);
        iqrfloop_sweep::RfLevelSweepPoint pb = mk(lvl, 20, lvl / 10.0);
        pa.kind = "tone";
        pb.kind = "qpsk";
        a.push_back(pa);
        b.push_back(pb);
    }
    const auto sa = iqrfloop_sweep::select_rf_level(a);
    const auto sb = iqrfloop_sweep::select_rf_level(b);
    check(sa.ok && sb.ok, "no-labels: both selections ok");
    check(sa.recommended_rms_counts == sb.recommended_rms_counts &&
          sa.recommended_rx_gain == sb.recommended_rx_gain,
          "no-labels: swapping kind (not a label) leaves the recommendation unchanged");
}

// ---- 5. all-clip -> no recommendation (NOT_PROVEN, never fabricated) ---------
void test_select_all_clip_not_proven() {
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> pts;
    for (double lvl : {512.0, 1024.0, 2048.0, 4096.0, 8192.0})
        pts.push_back(mk(lvl, 10, lvl, 1.0, /*tx_clip=*/true, /*rx_clip=*/false));
    const auto s = iqrfloop_sweep::select_rf_level(pts);
    check(!s.ok, "all-clip: no recommendation (ok == false)");
    check(s.recommended_rms_counts == 0.0, "all-clip: no fabricated level");
}

// ---- 6. low correlation (distorted IQ) is excluded ---------------------------
void test_select_low_corr_not_proven() {
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> pts;
    pts.push_back(mk(2048, 10, 205.0, /*corr=*/0.4));
    const auto s = iqrfloop_sweep::select_rf_level(pts);
    check(!s.ok, "low-corr: corr < 0.9 is not a candidate");
}

// ---- 7. a failed negative control is excluded (fail-closed) ------------------
void test_select_negative_control_fail() {
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> pts;
    pts.push_back(mk(2048, 10, 205.0, 1.0, false, false, /*capture=*/true, /*nc=*/false));
    const auto s = iqrfloop_sweep::select_rf_level(pts);
    check(!s.ok, "nc-fail: failed negative control is not a candidate");
}

// ---- 8. the gain whose median RX RMS is nearest the target is chosen ---------
void test_select_gain_nearest_target() {
    std::vector<iqrfloop_sweep::RfLevelSweepPoint> pts;
    pts.push_back(mk(2048, 0, 100.0));
    pts.push_back(mk(2048, 20, 60.0));    // nearest to target 64
    pts.push_back(mk(2048, 30, 40.0));
    const auto s = iqrfloop_sweep::select_rf_level(pts);
    check(s.ok, "gain-target: ok");
    check(std::fabs(s.recommended_rx_gain - 20.0) < 1e-6,
          "gain-target: recommends gain 20 dB (median RX RMS 60 nearest 64)");
}

// ---- 9. the default sweep config pins the -40 dB safety ceiling --------------
void test_config_default_atten_safe() {
    const iqrfloop_sweep::RfLevelSweepConfig cfg;
    check(cfg.tx_atten_db == pluto::kSafeTxCeilingDb,
          "config: default tx_atten is the -40 dB safety ceiling");
}

// ---- 10. end-to-end sweep against the FakePlutoDevice RF echo ----------------
void test_sweep_end_to_end() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 0.1;          // fixed complex RF path gain
    dev.rf_phase_deg = 0.0;
    dev.rf_delay = 0;
    dev.rf_noise_rms = 0.0;     // quiet negative control
    // 16-bit identity format: rails +/-32767, so no sweep level clips the TX DAC and
    // the selection is decided purely by the RX safe window (<= 512 counts).
    dev.tx_fmt_ = identity_fmt();
    dev.rx_fmt_ = identity_fmt();

    iqrfloop_sweep::RfLevelSweepConfig cfg;   // defaults: full 60-point grid, -40 dB
    const iqrfloop_sweep::RfLevelSweepReport rep = iqrfloop_sweep::sweep_rf_levels(dev, cfg);

    check(rep.ran, "e2e: sweep ran");
    check(rep.error.empty(), "e2e: no fail-closed error");
    check(rep.points.size() == 60, "e2e: 60 points (5 levels x 4 gains x 3 kinds)");
    check(rep.selection.ok, "e2e: a safe operating point was selected");
    // rf_gain = 0.1 -> RX RMS = 0.1 * level: 4096 -> ~410 (safe), 8192 -> ~819 (> 512,
    // excluded).  The LARGEST clip-free high-fidelity level is therefore 4096.
    check(std::fabs(rep.selection.recommended_rms_counts - 4096.0) < 1e-6,
          "e2e: recommends the largest safe level (4096 counts)");

    // Every candidate the selector saw at the recommended level/gain was clip-free,
    // negative-control-clean, captured cleanly and high-correlation.
    bool all_clean = true;
    for (const auto& p : rep.points) {
        if (p.level_counts == rep.selection.recommended_rms_counts &&
            p.rx_gain_db == rep.selection.recommended_rx_gain) {
            if (p.tx_clipped || p.rx_clipped || !p.capture_ok ||
                !p.negative_control_ok || p.corr < iqrfloop::kRfSyncCorrThreshold)
                all_clean = false;
        }
    }
    check(all_clean, "e2e: recommended points are clip-free / clean / high-fidelity");
}

// ---- 11. the sweep rejects a 12-bit-clipped point (real AD9364 semantics) -----
// With the fake's DEFAULT 12-bit data format the rails are +/-2047, so a level-2048
// tone (peak == RMS == 2048) clips the TX DAC while a level-1024 tone does not, and
// the recommendation is bounded to the largest level that is clip-free for SOME
// waveform (PRBS/QPSK at 2048 keep peak ~ RMS/sqrt(2) < 2047).
void test_sweep_clip_rejection_12bit() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 0.1;
    dev.rf_phase_deg = 0.0;
    dev.rf_delay = 0;
    dev.rf_noise_rms = 0.0;   // default 12-bit tx/rx format

    iqrfloop_sweep::RfLevelSweepConfig cfg;
    const auto rep = iqrfloop_sweep::sweep_rf_levels(dev, cfg);

    auto find = [&](double lvl, const std::string& kind) -> const iqrfloop_sweep::RfLevelSweepPoint* {
        for (const auto& p : rep.points)
            if (p.level_counts == lvl && p.kind == kind && p.rx_gain_db == 0.0) return &p;
        return nullptr;
    };
    const auto* t2048 = find(2048, "tone");
    const auto* t1024 = find(1024, "tone");
    check(t2048 && t2048->tx_clipped, "12bit: a level-2048 tone clips the 12-bit TX DAC");
    check(t1024 && !t1024->tx_clipped, "12bit: a level-1024 tone does not clip");
    // The largest level with at least one clip-free waveform is 2048 (PRBS/QPSK),
    // and the sweep must recommend it rather than the all-clipped 4096/8192.
    check(rep.selection.ok, "12bit: still selects a safe point");
    check(std::fabs(rep.selection.recommended_rms_counts - 2048.0) < 1e-6,
          "12bit: recommends 2048 (largest level with a clip-free waveform)");
}

}  // namespace

int main() {
    std::printf("test_iq_rf_loopback_level_sweep\n");
    test_waveform_rms_target();
    test_select_largest_clip_free_level();
    test_select_skips_clipped();
    test_select_no_labels();
    test_select_all_clip_not_proven();
    test_select_low_corr_not_proven();
    test_select_negative_control_fail();
    test_select_gain_nearest_target();
    test_config_default_atten_safe();
    test_sweep_end_to_end();
    test_sweep_clip_rejection_12bit();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
