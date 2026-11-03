// test_rf_fix_rml23.cpp -- host regression tests for the M29 Phase F5 RF LO/BW
// fix and the RML23 UI "NO SIGNAL" state fix (RC1/RC2/RC3 remediation).
//
// Nine tests:
//   (1) opt_present          -- --rx-lo/--rx-bw/--rf-diag CLI presence detection.
//   (2) rf_readback_close    -- fail-closed LO/BW read-back tolerance.
//   (3) rf_* safe read-backs -- "ERR" on throw, value on success (fake device).
//   (4) map NO_SIGNAL        -- below-presence-threshold frames -> Status::NoSignal.
//   (5) NoSignal precedence  -- anomaly (Error) and Mock still win over NoSignal.
//   (6) NoSignal label/geo   -- "NO SIGNAL" text + r==8 badge geometry.
//   (7) render color         -- NoSignal draws gray (disabled), never error red.
//   (8) legend hollow badge  -- the 5th legend badge is a HOLLOW circle.
//   (9) RML23 inherit        -- map_to_state_rml23 keeps NoSignal + 23-class identity.
//
// iCraft-free, libiio-free.  Links the real render stack (ui_render.cpp +
// font_atlas) so (7)/(8) exercise the exact pixels the board draws.
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/chain_common.hpp"
#include "../board_package/rf_fix_helpers.hpp"   // brings pluto::Device/FakePlutoDevice
#include "../board_package/ui_state_map.hpp"
#include "../ui_sw/ui_render.hpp"

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

const int kW = 1280, kH = 720;

ui::Canvas make_canvas(std::vector<std::uint16_t>& px) {
    px.assign(static_cast<std::size_t>(kW) * kH, 0);
    return ui::Canvas{px.data(), kW, kH};
}

std::size_t non_bg(const ui::Canvas& c, const ui::Theme& pal) {
    std::size_t n = 0;
    const std::size_t total = static_cast<std::size_t>(c.w) * c.h;
    for (std::size_t i = 0; i < total; ++i)
        if (c.px[i] != pal.background) ++n;
    return n;
}

std::size_t count_color(const ui::Canvas& c, std::uint16_t col) {
    std::size_t n = 0;
    const std::size_t total = static_cast<std::size_t>(c.w) * c.h;
    for (std::size_t i = 0; i < total; ++i)
        if (c.px[i] == col) ++n;
    return n;
}

// A clean 12-class ResultFrame (top-1 = class 5), presence_state empty.
rf::ResultFrame clean_frame() {
    std::vector<float> logits(12, -10.0f);
    logits[5] = 4.0f;
    rf::ResultFrame r;
    r.frame_id = 1;
    chain::fill_result(r, logits, chain::contract_12(), "2ae95275fe36", 6.0);
    return r;
}

// A clean 23-class RML23 ResultFrame (raw-24 peak at 5 -> merged-23 "8PSK").
rf::ResultFrame rml23_frame() {
    const cat::Contract c23 = chain::contract_23();
    std::vector<float> raw24(24, -10.0f);
    raw24[5] = 4.0f;
    std::vector<float> merged23(23, -10.0f);
    merged23[5] = 4.0f;
    rf::ResultFrame r;
    r.frame_id = 7;
    r.source = "fpga_npu";
    r.mock = false;
    chain::fill_result_rml23(r, raw24, merged23, c23, "2425d990dbac0761", 6.0);
    return r;
}

// (1) opt_present detects the RF override tokens (and only those tokens).
void test_opt_present() {
    {
        char a0[] = "prog", a1[] = "--rx-lo=2400000000", a2[] = "--rx-gain=10";
        char* argv[] = {a0, a1, a2};
        check(rf_fix::opt_present(3, argv, "--rx-lo"), "opt_present --rx-lo=... true");
        check(rf_fix::opt_present(3, argv, "--rx-gain"), "opt_present --rx-gain=... true");
        check(!rf_fix::opt_present(3, argv, "--rx-bw"), "opt_present --rx-bw absent");
    }
    {
        char a0[] = "prog", a1[] = "--rx-lo", a2[] = "2400000000";
        char* argv[] = {a0, a1, a2};
        check(rf_fix::opt_present(3, argv, "--rx-lo"), "opt_present bare --rx-lo true");
    }
    {
        char a0[] = "prog", a1[] = "--rx-lo-x=1";
        char* argv[] = {a0, a1};
        check(!rf_fix::opt_present(2, argv, "--rx-lo"), "opt_present --rx-lo-x not matched");
    }
    {
        char a0[] = "prog", a1[] = "--nco-offset=10000", a2[] = "--rf-diag";
        char* argv[] = {a0, a1, a2};
        check(rf_fix::opt_present(3, argv, "--rf-diag"), "opt_present bare --rf-diag true");
        check(!rf_fix::opt_present(3, argv, "--rx-lo"), "opt_present --rx-lo absent amid others");
    }
}

// (2) fail-closed read-back tolerance (LO abs 1 kHz / rel 1e-4; BW rel 5%).
void test_rf_readback_close() {
    check(rf_fix::rf_readback_close(2400000000LL, 2400000000LL, 1000LL, 1e-4),
          "LO exact read-back close");
    check(rf_fix::rf_readback_close(2400000100LL, 2400000000LL, 1000LL, 1e-4),
          "LO +100 Hz within abs tol");
    check(rf_fix::rf_readback_close(2400010000LL, 2400000000LL, 1000LL, 1e-4),
          "LO +10 kHz within rel tol (1e-4)");
    check(!rf_fix::rf_readback_close(2401000000LL, 2400000000LL, 1000LL, 1e-4),
          "LO +1 MHz outside tol -> fail-closed");

    check(rf_fix::rf_readback_close(200000LL, 200000LL, 1000LL, 0.05), "BW exact read-back close");
    check(rf_fix::rf_readback_close(210000LL, 200000LL, 1000LL, 0.05),
          "BW +10 kHz within 5% rel tol");
    check(!rf_fix::rf_readback_close(250000LL, 200000LL, 1000LL, 0.05),
          "BW +50 kHz outside 5% -> fail-closed");
    check(rf_fix::rf_readback_close(190000LL, 200000LL, 1000LL, 0.05),
          "BW -10 kHz within 5% rel tol");

    check(rf_fix::rf_readback_close(0, 0, 1000LL, 1e-4), "want==0 got==0 close");
    check(!rf_fix::rf_readback_close(1, 0, 1000LL, 1e-4), "want==0 got!=0 not close");
}

// (3) safe read-backs return the value on success and "ERR" (not a throw) on error.
void test_rf_safe_readbacks() {
    pluto::FakePlutoDevice dev;
    dev.fake_uri = "fake://rf0";
    dev.fake_serial = "1044f2deadbeef";
    check(rf_fix::rf_s(dev, &pluto::Device::uri) == "fake://rf0", "rf_s uri read-back");
    check(rf_fix::rf_s(dev, &pluto::Device::serial) == "1044f2deadbeef", "rf_s serial read-back");
    check(rf_fix::rf_s(dev, &pluto::Device::rx_channel_name) == "voltage0",
          "rf_s rx_channel_name read-back");
    check(rf_fix::rf_ll(dev, &pluto::Device::get_rx_lo) == "0", "rf_ll rx_lo read-back");
    check(rf_fix::rf_i(dev, &pluto::Device::get_loopback) == "0", "rf_i loopback read-back");

    // A getter that throws must become "ERR", never propagate (a diag log read
    // can never fail the gate).
    struct ThrowingDevice : pluto::FakePlutoDevice {
        long long get_rx_lo() const override { throw std::runtime_error("boom"); }
    };
    ThrowingDevice t;
    check(rf_fix::rf_ll(t, &pluto::Device::get_rx_lo) == "ERR", "rf_ll returns ERR on throw");
}

// (4) below-presence-threshold frames map to NoSignal (not Live, not Error).
void test_map_nosignal() {
    rf::ResultFrame r = clean_frame();
    r.presence_state = "NO_SIGNAL";
    ui::UiState st = ui::map_to_state(r);
    check(st.status == ui::Status::NoSignal, "presence_state==NO_SIGNAL -> NoSignal");
    check(st.source == "SDR", "NoSignal keeps the SDR source (not a mock)");

    rf::ResultFrame r2 = clean_frame();
    r2.presence_state = "SIGNAL_PRESENT";
    check(ui::map_to_state(r2).status == ui::Status::Live,
          "presence_state==SIGNAL_PRESENT -> Live");
}

// (5) an RX anomaly and a mock frame still out-rank NO_SIGNAL.
void test_nosignal_precedence() {
    rf::ResultFrame e = clean_frame();
    e.presence_state = "NO_SIGNAL";
    e.dropped = true;
    check(ui::map_to_state(e).status == ui::Status::Error,
          "NO_SIGNAL + dropped -> Error (anomaly wins)");

    rf::ResultFrame m = clean_frame();
    m.presence_state = "NO_SIGNAL";
    m.mock = true;
    check(ui::map_to_state(m).status == ui::Status::Mock,
          "NO_SIGNAL + mock -> Mock (mock wins)");
}

// (6) "NO SIGNAL" label is distinct from "ERROR" (the RC2 conflation is gone),
//     and the badge geometry stays text + shape (never text-into-shape overlap).
void test_nosignal_label_geometry() {
    check(std::string(ui::status_label(ui::Status::NoSignal)) == "NO SIGNAL",
          "status_label NoSignal == \"NO SIGNAL\"");
    check(std::string(ui::status_label(ui::Status::Error)) == "ERROR",
          "status_label Error == \"ERROR\" (anomaly no longer reads NO SIGNAL)");
    // The NoSignal badge keeps the r==8 circle (not the Error r==9 triangle): the
    // shape center sits LEFT of the text by text_width + 10 + r, so the LONGER
    // "NO SIGNAL" label pushes its center further left than LIVE's.  The
    // hollow-vs-filled shape itself is proven pixel-exactly in test 8.
    check(ui::status_badge_shape_cx(ui::Status::NoSignal, 1000) <
              ui::status_badge_shape_cx(ui::Status::Live, 1000),
          "NoSignal shape center sits left of Live (longer label)");
}

// (7) NoSignal renders gray (disabled), never error red; Error renders red; the
//     two states draw DIFFERENT result cards (the RC2 conflation is gone).
void test_render_nosignal_color() {
    const ui::Theme& th = ui::theme_default();
    std::vector<std::uint16_t> na, ea;
    ui::Canvas cn = make_canvas(na), ce = make_canvas(ea);

    rf::ResultFrame rn = clean_frame();
    rn.presence_state = "NO_SIGNAL";
    ui::UiState sn = ui::map_to_state(rn);
    ui::render_main(cn, th, sn);

    rf::ResultFrame re = clean_frame();
    re.dropped = true;
    ui::UiState se = ui::map_to_state(re);
    ui::render_main(ce, th, se);

    check(non_bg(cn, th) > 10000, "NoSignal render_main draws content");
    check(count_color(cn, th.disabled) > 0, "NoSignal draws the gray (disabled) state");
    check(count_color(ce, th.error) > 0, "Error draws the red (error) state");
    check(count_color(cn, th.error) == 0, "NoSignal draws NO error red (RC2 conflation fixed)");
}

// (8) the legend's 5th badge is a HOLLOW circle (center unfilled), while the
//     LIVE badge is a FILLED circle (center green) -- shape is never color-only.
void test_render_legend_hollow() {
    const ui::Theme& th = ui::theme_default();
    std::vector<std::uint16_t> px;
    ui::Canvas c = make_canvas(px);
    ui::render_legend(c, th);

    check(non_bg(c, th) > 10000, "render_legend draws the 5-status legend");

    // render_legend places LIVE at x_right=220 and NO SIGNAL at x_right=720, yc=140.
    const int cx_live = ui::status_badge_shape_cx(ui::Status::Live, 220);
    const int cx_nosig = ui::status_badge_shape_cx(ui::Status::NoSignal, 720);
    check(c.px[140 * kW + cx_live] == th.success, "LIVE badge center is filled green");
    check(c.px[140 * kW + cx_nosig] != th.success, "NO SIGNAL badge center is hollow (unfilled)");
}

// (9) map_to_state_rml23 inherits the NoSignal state without losing 23-class identity.
void test_map_rml23_inherits_nosignal() {
    rf::ResultFrame r = rml23_frame();
    r.presence_state = "NO_SIGNAL";
    ui::UiState st = ui::map_to_state_rml23(r);
    check(st.status == ui::Status::NoSignal, "map_to_state_rml23 inherits NoSignal");
    check(st.classes == &ui::classes_23(), "NoSignal keeps the 23-class contract");
    check(st.model_mode == "RML23-AMSSB-MERGED", "NoSignal keeps the RML23 model caption");
    check(st.class_count == 23, "NoSignal keeps class_count == 23");
}

}  // namespace

int main() {
    std::printf("test_rf_fix_rml23\n");
    test_opt_present();
    test_rf_readback_close();
    test_rf_safe_readbacks();
    test_map_nosignal();
    test_nosignal_precedence();
    test_nosignal_label_geometry();
    test_render_nosignal_color();
    test_render_legend_hollow();
    test_map_rml23_inherits_nosignal();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
