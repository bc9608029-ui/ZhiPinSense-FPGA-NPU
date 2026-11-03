// test_iq_digital_loopback_sweep.cpp -- host tests for the Stage H-E / Route E
// amplitude sweep + root-cause discriminator (board_package/iq_digital_loopback_
// sweep.hpp), fix4 edition.
//
// fix4 corrects the fix3 discriminator, which misjudged the ~ -24 dB raw-container
// loss as "ambiguous": it never propagated kind/target_rms, unconditionally masked
// a fully-defined 12-bit value to +4064, and compared TX/RX counts without the
// TX16/RX12 signed full scale.  These tests pin down:
//   1-3  the corrected convert mirror across fully-defined / sign-extended / shift4;
//   4    kind/target_rms propagation into SweepLevel;
//   5    TX16/RX12 count ratio 1/16 -> count gain ~-24 dB, normalized ~0 dB ->
//        DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE;
//   6    same bit width + count ~0 -> DIGITAL_LOOPBACK_UNITY;
//   7    a real level-independent attenuation -> DIGITAL_LOOPBACK_FIXED_ATTENUATION;
//   8    a wrong reported bit position + shift-scan recovery ->
//        DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT;
//   9    libiio RX convert diverging from the host mirror -> LIBIIO_CONVERT_SEMANTICS;
//   10   RX pinned at the quantization floor -> NOT_PROVEN;
//   11   correct gain but corr below threshold -> NOT_PROVEN (gain != fidelity);
//   12   COUNT_DOMAIN_SCALE auto-selects scale=16 without clipping;
//   13   a scale that would clip the frozen peak is clamped (fail-closed);
//   14   the high-amplitude valid-level band drives the call, low levels ignored.
//
// iCraft-free and libiio-free.  Links ../sdr_adapter/pluto_tx.cpp (the real
// PlutoTx safety state machine) so the sweep drives the exact TX start/stop path
// the board runs, against the scriptable FakePlutoDevice.

#include "../board_package/iq_digital_loopback_sweep.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void check_near(double got, double want, double tol, const char* what) {
    if (std::fabs(got - want) <= tol) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (got %.6f want %.6f)\n", what, got, want); }
}

// Data-format fixtures.  The board reports TX 16b/16b shift+0 signed fully-defined,
// RX 16b/12b shift+0 signed fully-defined; the sign-extended (not-fully-defined)
// 12-bit layout is also exercised because the shift-4 left-justified AD9364 layout
// is sign-extended.
pluto::DataFormatInfo fmt16fd() {
    pluto::DataFormatInfo f;
    f.length_bits = 16; f.bits = 16; f.shift = 0;
    f.is_signed = true; f.is_fully_defined = true; f.is_be = false; f.repeat = 1;
    return f;
}
pluto::DataFormatInfo fmt12fd(std::uint32_t shift) {   // fully-defined signed 12-bit
    pluto::DataFormatInfo f;
    f.length_bits = 16; f.bits = 12; f.shift = shift;
    f.is_signed = true; f.is_fully_defined = true; f.is_be = false; f.repeat = 1;
    return f;
}
pluto::DataFormatInfo fmt12(std::uint32_t shift) {     // sign-extended signed 12-bit
    pluto::DataFormatInfo f;
    f.length_bits = 16; f.bits = 12; f.shift = shift;
    f.is_signed = true; f.is_fully_defined = false; f.is_be = false; f.repeat = 1;
    return f;
}

// A compact sweep configuration over `levels` (tone only) so the host tests run the
// full orchestration path without the 3x7 = 21-level grid.
iqdloop_sweep::SweepConfig tone_cfg(std::vector<double> levels) {
    iqdloop_sweep::SweepConfig cfg;
    cfg.center_hz = 2400000000ULL;
    cfg.rx_gain_db = 10.0;
    cfg.tx_atten_db = pluto::kSafeTxAttenDb;
    cfg.fs = iqdloop::kFrozenFsIn;
    cfg.delay_margin = 512;
    cfg.capture_complex = 2048;
    cfg.kinds = {"tone"};
    cfg.levels = std::move(levels);
    return cfg;
}

// A hand-built SweepLevel for direct classifier / scale-selection tests: a
// clip-free, capture-ok high-amplitude level whose reported decode is CONSISTENT
// with the raw container (logical gain == count gain).  rx_raw is a non-empty
// placeholder so classify_root_cause's "was there a capture at all" step sees a
// captured-with-data level (the direct-classifier tests target the logic AFTER the
// capture stage, not the capture stage itself).
iqdloop_sweep::SweepLevel make_level(double target_rms, double count_gain_db,
                                     double normalized_gain_db,
                                     double logical_gain_db, double corr) {
    iqdloop_sweep::SweepLevel L;
    L.capture_ok = true;
    L.kind = "tone";
    L.target_rms = target_rms;
    L.rx_raw.assign(2, 1);                  // non-empty: a capture happened
    L.rx_count_rms = 100.0;                 // comfortably above the quant floor
    L.count_gain_db = count_gain_db;
    L.normalized_gain_db = normalized_gain_db;
    L.gain_db = logical_gain_db;
    L.corr = corr;
    L.tx_clip = 0; L.rx_clip = 0; L.rx_raw_clip = 0;
    return L;
}

// ---------------------------------------------------------------------------
// Sweep waveform generators.
// ---------------------------------------------------------------------------
void test_make_sweep_waveform() {
    for (const char* kind : {"tone", "ramp", "prbs"}) {
        const auto w = iqdloop_sweep::make_sweep_waveform(kind, 16.0, 1024);
        check(w.size() == 2048, "waveform: interleaved length == 2 * n_complex");
        const double rms = iqdloop_sweep::rms_magnitude(w);
        check_near(rms, 16.0, 0.5, "waveform: complex-magnitude RMS ~ target");
        const auto w2 = iqdloop_sweep::make_sweep_waveform(kind, 16.0, 1024);
        check(w == w2, "waveform: deterministic (two calls identical)");
    }
    auto w = iqdloop_sweep::make_sweep_waveform("tone", 8.0, 1024);
    iqdloop_sweep::scale_to_rms(w, 128.0);
    check_near(iqdloop_sweep::rms_magnitude(w), 128.0, 0.5,
               "scale_to_rms: RMS re-targeted");
}

// ---------------------------------------------------------------------------
// Corrected convert mirror (scenarios 1-3) + the SIGNCHECK self-check.
// ---------------------------------------------------------------------------
void test_sign_extension_fully_defined() {
    const auto fd0 = fmt12fd(0);
    check(pluto::format_convert_raw_to_host(fd0, static_cast<std::int16_t>(0xFFFF)) == -1,
          "fd12 shift0: 0xFFFF -> -1");
    check(pluto::format_convert_raw_to_host(fd0, static_cast<std::int16_t>(0xFFE0)) == -32,
          "fd12 shift0: 0xFFE0 -> -32 (not +4064)");
    check(pluto::format_convert_raw_to_host(fd0, static_cast<std::int16_t>(0xF800)) == -2048,
          "fd12 shift0: 0xF800 -> -2048");
    check(pluto::format_convert_raw_to_host(fd0, static_cast<std::int16_t>(0x07FF)) == 2047,
          "fd12 shift0: 0x07FF -> 2047");
    const auto sc = iqdloop_sweep::verify_sign_extension();
    check(sc.fully_defined_ok, "SIGNCHECK: fully-defined family ok");
}

void test_sign_extension_not_fully_defined() {
    const auto nfd0 = fmt12(0);
    check(pluto::format_convert_raw_to_host(nfd0, static_cast<std::int16_t>(0x0FFF)) == -1,
          "se12 shift0: 0x0FFF -> -1");
    check(pluto::format_convert_raw_to_host(nfd0, static_cast<std::int16_t>(0x0800)) == -2048,
          "se12 shift0: 0x0800 -> -2048");
    check(pluto::format_convert_raw_to_host(nfd0, static_cast<std::int16_t>(0x07FF)) == 2047,
          "se12 shift0: 0x07FF -> 2047");
    const auto sc = iqdloop_sweep::verify_sign_extension();
    check(sc.sign_extend_ok, "SIGNCHECK: sign-extended family ok");
}

void test_sign_extension_shift4() {
    const auto nfd4 = fmt12(4);
    check(pluto::format_convert_raw_to_host(nfd4, static_cast<std::int16_t>(0x7FF0)) == 2047,
          "se12 shift4: 0x7FF0 -> 2047");
    check(pluto::format_convert_raw_to_host(nfd4, static_cast<std::int16_t>(0x8000)) == -2048,
          "se12 shift4: 0x8000 -> -2048");
    const auto sc = iqdloop_sweep::verify_sign_extension();
    check(sc.shift4_ok, "SIGNCHECK: shift-4 family ok");
    check(sc.ok, "SIGNCHECK: overall ok");
}

void test_format_roundtrip() {
    check(pluto::format_roundtrip_identity(fmt16fd()), "roundtrip: TX16 fully-defined");
    check(pluto::format_roundtrip_identity(fmt12fd(0)), "roundtrip: RX12 shift0 fully-defined");
    check(pluto::format_roundtrip_identity(fmt12(0)), "roundtrip: 12-bit shift0 sign-extended");
    check(pluto::format_roundtrip_identity(fmt12(4)), "roundtrip: 12-bit shift4 sign-extended");
}

// ---------------------------------------------------------------------------
// kind/target_rms propagation (scenario 4).
// ---------------------------------------------------------------------------
void test_kind_target_rms_propagation() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_fmt_ = fmt12fd(0);
    dev.rx_fmt_ = fmt12fd(0);
    dev.loopback_raw_gain_ = 1.0;
    dev.loopback_raw_shift_ = 0;
    const auto rep = iqdloop_sweep::sweep_all_levels(dev, tone_cfg({64.0, 128.0}),
                                                     0.0, 0.0, false);
    check(rep.levels.size() == 2, "propagation: two sweep levels");
    for (const auto& L : rep.levels) {
        check(L.kind == "tone", "propagation: kind propagated");
        check(L.target_rms == 64.0 || L.target_rms == 128.0,
              "propagation: target_rms propagated");
    }
}

// ---------------------------------------------------------------------------
// Root-cause classification over the FakePlutoDevice (scenarios 5-9).
// ---------------------------------------------------------------------------
void test_sweep_count_domain_scale() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_fmt_ = fmt16fd();       // TX 16-bit
    dev.rx_fmt_ = fmt12fd(0);      // RX 12-bit fully-defined, shift 0
    dev.loopback_raw_gain_ = 1.0 / 16.0;   // RX raw = TX raw / 16 (count domain)
    dev.loopback_raw_shift_ = 0;

    const auto rep = iqdloop_sweep::sweep_all_levels(
        dev, tone_cfg({64.0, 128.0, 256.0, 512.0}), 0.0, 0.0, false);
    for (const auto& L : rep.levels) {
        check(L.capture_ok, "count-domain: capture ok");
        check(L.corr > 0.99, "count-domain: correlation ~1.0");
        check_near(L.count_gain_db, -24.08, 1.0, "count-domain: count gain ~-24 dB");
        // The target=64 level sits at the quantization boundary (RX ~4 counts), so
        // its normalized gain legitimately wanders up to ~0.6 dB; the classifier
        // itself uses the MEDIAN over valid levels (a full-scale bug would show up
        // as ~+/-24 dB, far beyond this tolerance).
        check_near(L.normalized_gain_db, 0.0, 1.0, "count-domain: normalized ~0 dB");
        check(!L.rx_libiio_diverged, "count-domain: no libiio divergence");
    }
    check(rep.cause.token == iqdloop_sweep::kRootCauseCountDomainScale,
          "count-domain: classified DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE");
}

void test_sweep_unity() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_fmt_ = fmt12fd(0);
    dev.rx_fmt_ = fmt12fd(0);
    dev.loopback_raw_gain_ = 1.0;
    dev.loopback_raw_shift_ = 0;

    const auto rep = iqdloop_sweep::sweep_all_levels(dev, tone_cfg({64.0, 128.0}),
                                                     0.0, 0.0, false);
    for (const auto& L : rep.levels) {
        check(L.capture_ok, "unity: capture ok");
        check(L.corr > 0.99, "unity: correlation ~1.0");
        check_near(L.count_gain_db, 0.0, 0.5, "unity: count gain ~0 dB");
        check_near(L.normalized_gain_db, 0.0, 0.5, "unity: normalized ~0 dB");
    }
    check(rep.cause.token == iqdloop_sweep::kRootCauseUnity,
          "unity: classified DIGITAL_LOOPBACK_UNITY");
}

void test_sweep_fixed_attenuation() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_fmt_ = fmt12fd(0);
    dev.rx_fmt_ = fmt12fd(0);
    dev.loopback_raw_gain_ = 0.1;   // a level-independent -20 dB loopback gain
    dev.loopback_raw_shift_ = 0;

    const auto rep = iqdloop_sweep::sweep_all_levels(dev, tone_cfg({128.0, 512.0}),
                                                     16.0, 16.0, true);
    check(rep.cause.token == iqdloop_sweep::kRootCauseFixedAttenuation,
          "fixed: classified DIGITAL_LOOPBACK_FIXED_ATTENUATION");
    for (const auto& L : rep.levels) {
        check_near(L.count_gain_db, -20.0, 1.5, "fixed: count gain ~-20 dB");
        check_near(L.normalized_gain_db, -20.0, 1.5, "fixed: normalized ~-20 dB (== count)");
    }
    // req 6/7: auto-select a compensating TX scale; the RX RMS it predicts lands at
    // the frozen RMS (the bit_scale is 2^0 = 1 for equal widths).
    check(rep.scale_sel.ok, "fixed: auto-selected scale is safe");
    check(rep.scale_sel.scale > 1.0 && rep.scale_sel.scale < 20.0,
          "fixed: scale ~10 (1 / 0.1)");
    check_near(rep.scale_sel.expected_rx_rms, 16.0, 2.0,
               "fixed: expected RX RMS ~ frozen RMS");
}

void test_sweep_format_misalignment() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_fmt_ = fmt12(0);   // hardware writes right-justified
    dev.rx_fmt_ = fmt12(4);   // REPORTED format is wrong (left-justified)
    dev.loopback_raw_gain_ = 1.0;
    dev.loopback_raw_shift_ = 0;

    const auto rep = iqdloop_sweep::sweep_all_levels(dev, tone_cfg({128.0, 256.0}),
                                                     0.0, 0.0, false);
    check(rep.cause.token == iqdloop_sweep::kRootCauseFormatMisalignment,
          "misalign: classified DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT");
    for (const auto& L : rep.levels) {
        check_near(L.count_gain_db, 0.0, 0.5, "misalign: raw container preserved");
        check_near(L.gain_db, -24.0, 1.0, "misalign: logical gain ~-24 dB (>>4)");
    }
    // req 5: the fix is a FORMAT correction (bit position), never a multiplier.
    check(rep.rx_shift.ok, "misalign: correct RX shift found");
    check(rep.rx_shift.shift == 0, "misalign: correct RX shift == 0 (right-justified)");
    check(rep.rx_shift.corr >= 0.9, "misalign: shift-search correlation >= 0.9");
}

void test_libiio_divergence() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.tx_fmt_ = fmt12fd(0);
    dev.rx_fmt_ = fmt12fd(0);
    dev.loopback_raw_gain_ = 1.0;
    dev.loopback_raw_shift_ = 0;
    dev.force_rx_libiio_divergence = true;   // libiio RX convert != host mirror
    dev.rx_libiio_delta = 1;

    const auto rep = iqdloop_sweep::sweep_all_levels(dev, tone_cfg({64.0, 128.0}),
                                                     0.0, 0.0, false);
    check(rep.cause.token == iqdloop_sweep::kRootCauseLibiioConvert,
          "libiio: classified DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS");
}

// ---------------------------------------------------------------------------
// Direct classifier edge cases (scenarios 10, 11, 14).
// ---------------------------------------------------------------------------
void test_low_amplitude_not_proven() {
    // RX pinned at the quantization floor: a captured but sub-floor signal is not a
    // usable gain measurement.
    iqdloop_sweep::SweepLevel L = make_level(64.0, -40.0, -40.0, -40.0, 0.99);
    L.rx_count_rms = 0.5;   // below kQuantFloorCounts
    const auto rc = iqdloop_sweep::classify_root_cause({L}, fmt16fd(), fmt12fd(0));
    check(rc.token == iqdloop_sweep::kRootCauseNotProven,
          "low-amplitude: sub-floor signal -> NOT_PROVEN");
}

void test_corr_insufficient_not_proven() {
    // Correct count-domain scale and normalized gain, but corr below the fidelity
    // threshold: gain alone is not fidelity.
    const auto rc = iqdloop_sweep::classify_root_cause(
        {make_level(128.0, -24.08, 0.0, -24.08, 0.5),
         make_level(256.0, -24.08, 0.0, -24.08, 0.5)},
        fmt16fd(), fmt12fd(0));
    check(rc.token == iqdloop_sweep::kRootCauseNotProven,
          "corr: gain correct but corr < 0.9 -> NOT_PROVEN");
}

void test_valid_level_selection() {
    // The 8/16 low-amplitude levels are quantization-boundary evidence and must not
    // dominate: a low level that would say UNITY is ignored in favour of the
    // high-amplitude fixed-attenuation levels.
    const auto rc = iqdloop_sweep::classify_root_cause(
        {make_level(16.0, 0.0, 0.0, 0.0, 0.99),
         make_level(128.0, -20.0, -20.0, -20.0, 0.99),
         make_level(256.0, -20.0, -20.0, -20.0, 0.99)},
        fmt12fd(0), fmt12fd(0));
    check(rc.token == iqdloop_sweep::kRootCauseFixedAttenuation,
          "valid-level: high-amplitude band drives the call (low level ignored)");
}

// ---------------------------------------------------------------------------
// Auto-selected scale (scenarios 12, 13).
// ---------------------------------------------------------------------------
void test_auto_select_scale_count_domain() {
    const auto s = iqdloop_sweep::auto_select_scale(
        {make_level(128.0, -24.08, 0.0, -24.08, 0.99)},
        fmt16fd(), fmt12fd(0), 16.0, 32.0);
    check(s.ok, "count-domain scale: selected");
    check_near(s.scale, 16.0, 0.5, "count-domain scale: S == 16 (2^4)");
    check_near(s.expected_rx_rms, 16.0, 1.0,
               "count-domain scale: expected RX RMS == frozen RMS");
}

void test_auto_select_scale_clip_refused() {
    // A frozen peak that would clip under scale=16 is clamped (fail-closed): the
    // returned scale never pushes the frozen peak past the 12-bit DAC rail.
    const auto s = iqdloop_sweep::auto_select_scale(
        {make_level(128.0, -24.08, 0.0, -24.08, 0.99)},
        fmt16fd(), fmt12fd(0), 16.0, 2000.0);
    check(s.ok, "clip: still returns a (clamped) scale");
    check(s.scale < 16.0, "clip: scale=16 refused");
    check(s.scale * 2000.0 <= 2048.0, "clip: returned scale does not clip the frozen peak");
}

void test_auto_select_scale_no_safe() {
    // A -60 dB loopback gain is too deep: the required scale exceeds the 4096 clamp
    // window, so it clamps to 4096 but the expected RX RMS stays below the floor --
    // the caller must treat the frozen RMS as unreachable, not proceed silently.
    const auto s = iqdloop_sweep::auto_select_scale(
        {make_level(128.0, -60.0, -60.0, -60.0, 0.99)},
        fmt12fd(0), fmt12fd(0), 16.0, 16.0);
    check(s.scale <= 4096.0, "no-safe: scale clamped into the allowed window");
}

// ---------------------------------------------------------------------------
// Direct shift search.
// ---------------------------------------------------------------------------
void test_find_correct_rx_shift_direct() {
    const std::size_t N = 512;
    auto tx = iqdloop_sweep::make_sweep_waveform("tone", 128.0, N);
    std::vector<std::int16_t> rx_raw(N * 2);
    for (std::size_t k = 0; k < N; ++k) {
        rx_raw[k * 2 + 0] = pluto::format_convert_host_to_raw(fmt12(0), tx[k * 2 + 0]);
        rx_raw[k * 2 + 1] = pluto::format_convert_host_to_raw(fmt12(0), tx[k * 2 + 1]);
    }
    const auto s = iqdloop_sweep::find_correct_rx_shift(tx, rx_raw, fmt12(4),
                                                        iqdloop::kFrozenFsIn, 512);
    check(s.ok, "shift search: ok");
    check(s.shift == 0, "shift search: correct shift == 0");
    check(s.corr >= 0.9, "shift search: corr >= 0.9");
}

}  // namespace

int main() {
    std::printf("test_iq_digital_loopback_sweep\n");
    test_make_sweep_waveform();
    test_sign_extension_fully_defined();
    test_sign_extension_not_fully_defined();
    test_sign_extension_shift4();
    test_format_roundtrip();
    test_kind_target_rms_propagation();
    test_sweep_count_domain_scale();
    test_sweep_unity();
    test_sweep_fixed_attenuation();
    test_sweep_format_misalignment();
    test_libiio_divergence();
    test_low_amplitude_not_proven();
    test_corr_insufficient_not_proven();
    test_valid_level_selection();
    test_auto_select_scale_count_domain();
    test_auto_select_scale_clip_refused();
    test_auto_select_scale_no_safe();
    test_find_correct_rx_shift_direct();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
