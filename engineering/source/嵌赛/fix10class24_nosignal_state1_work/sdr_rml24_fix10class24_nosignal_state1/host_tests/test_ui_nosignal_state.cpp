// test_ui_nosignal_state.cpp -- host tests for the no-signal state machine +
// UI mapping fix (fix10class24-nosignal-state1).
//
// The presence state machine (sdr_adapter/signal_presence.hpp) and the UI
// status mapping (board_package/ui_state_map.hpp) are CLASS-COUNT-INDEPENDENT
// shared logic.  This test proves the UI side with a synthetic 24-dimensional
// ResultFrame (the state/status mapping and classification hiding must hold for
// any class width, including the 24-class RML24 source), plus the exact pixels
// the three new hero branches draw.
//
// Tests:
//   (1) map_to_state 4-state mapping -- NO_SIGNAL/SIGNAL_LOST/INVALID/ACQUIRING
//       -> NoSignal/SignalLost/Invalid/Acquiring, SIGNAL_PRESENT -> Live.
//   (2) classification hiding -- the four non-present states clear top1/conf/dist
//       (a stale class is never shown as LIVE); SIGNAL_PRESENT keeps the 24-dim
//       dist; Mock/Error keep classification (regression).
//   (3) apply_state_event -- 4-state mapping + hiding; SIGNAL_PRESENT never
//       forges Live and never clears an existing classification.
//   (4) status_label -- "SIGNAL LOST" / "RX ERROR" / "ACQUIRING" / "NO SIGNAL".
//   (5) status_badge_shape_cx -- Invalid/Error use r==9, SignalLost/NoSignal r==8.
//   (6) hero render pixels -- the three hero states never enter the default
//       classification path (no confidence bar / no Top-N), draw the right
//       state color, and a Live frame does draw the confidence bar.
//
// Build/run: see host_tests/build_host_tests.sh (links ui_render.cpp + font_atlas).

#include "../board_package/ui_state_map.hpp"
#include "../ui_sw/ui_layout.hpp"

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

// Count `col` in rows [0, y_below) -- i.e. everything ABOVE the info strip.
// The confidence bar and the Top-N probability bars are both drawn in the
// content area above kInfoY0, so a zero count there proves the default
// classification path was never entered.
std::size_t count_color_above(const ui::Canvas& c, int y_below, std::uint16_t col) {
    std::size_t n = 0;
    for (int y = 0; y < y_below && y < c.h; ++y)
        for (int x = 0; x < c.w; ++x)
            if (c.px[y * c.w + x] == col) ++n;
    return n;
}

// A synthetic 24-dim ResultFrame with a top-1 at index 5.  The presence-state
// string is the only thing that varies between the non-present cases; the
// mapping/hiding must be independent of the 24-class width.
rf::ResultFrame frame_24(const char* presence) {
    rf::ResultFrame r;
    r.frame_id = 1;
    r.source = "fpga_npu";
    r.class_count = 24;
    r.argmax_idx = 5;
    r.argmax_class = "8PSK";
    r.confidence = 0.72f;
    std::vector<float> d(24, 0.01f);
    d[5] = 0.72f;
    r.probabilities = d;
    r.presence_state = presence ? presence : "";
    return r;
}

// (1) the four non-present presence states map to their own Status, and
// SIGNAL_PRESENT (or empty) maps to Live.
void test_map_to_state_four_states() {
    check(ui::map_to_state(frame_24("NO_SIGNAL")).status == ui::Status::NoSignal,
          "NO_SIGNAL -> NoSignal");
    check(ui::map_to_state(frame_24("SIGNAL_LOST")).status == ui::Status::SignalLost,
          "SIGNAL_LOST -> SignalLost");
    check(ui::map_to_state(frame_24("INVALID")).status == ui::Status::Invalid,
          "INVALID -> Invalid");
    check(ui::map_to_state(frame_24("ACQUIRING")).status == ui::Status::Acquiring,
          "ACQUIRING -> Acquiring");
    check(ui::map_to_state(frame_24("SIGNAL_PRESENT")).status == ui::Status::Live,
          "SIGNAL_PRESENT -> Live");
}

// (2) the four non-present states hide the stale classification; SIGNAL_PRESENT
// keeps the 24-dim dist; Mock/Error keep classification (only presence states hide).
void test_hide_classification() {
    const char* hidden[] = {"NO_SIGNAL", "SIGNAL_LOST", "INVALID", "ACQUIRING"};
    for (const char* p : hidden) {
        ui::UiState st = ui::map_to_state(frame_24(p));
        char what[96];
        std::snprintf(what, sizeof what, "%s hides top1", p);
        check(st.top1.empty(), what);
        std::snprintf(what, sizeof what, "%s hides conf", p);
        check(st.conf == 0.0f, what);
        std::snprintf(what, sizeof what, "%s hides dist", p);
        check(st.dist.empty(), what);
    }

    ui::UiState live = ui::map_to_state(frame_24("SIGNAL_PRESENT"));
    check(!live.top1.empty(), "SIGNAL_PRESENT keeps top1");
    check(live.conf > 0.0f, "SIGNAL_PRESENT keeps conf");
    check(live.dist.size() == 24, "SIGNAL_PRESENT keeps the 24-dim dist");

    rf::ResultFrame m = frame_24("");
    m.mock = true;
    ui::UiState sm = ui::map_to_state(m);
    check(!sm.top1.empty() && sm.conf > 0.0f, "Mock keeps classification (regression)");

    rf::ResultFrame e = frame_24("");
    e.dropped = true;
    ui::UiState se = ui::map_to_state(e);
    check(!se.top1.empty() && se.conf > 0.0f, "Error keeps classification (regression)");
}

// (3) apply_state_event maps the four non-present states and hides the stale
// classification; a SIGNAL_PRESENT state never forges Live and never clears one.
void test_apply_state_event() {
    struct { const char* p; ui::Status want; } cases[] = {
        {"NO_SIGNAL", ui::Status::NoSignal},
        {"SIGNAL_LOST", ui::Status::SignalLost},
        {"INVALID", ui::Status::Invalid},
        {"ACQUIRING", ui::Status::Acquiring},
    };
    for (const auto& c : cases) {
        ui::UiState st;                    // default status = Live
        st.top1 = "OLD";
        st.conf = 0.9f;
        st.dist = {0.9f, 0.1f};
        ui::StateEvent se;
        se.presence_state = c.p;
        se.run_state = "RUNNING";
        ui::apply_state_event(st, se);
        char what[96];
        std::snprintf(what, sizeof what, "state %s -> correct badge", c.p);
        check(st.status == c.want, what);
        std::snprintf(what, sizeof what, "state %s hides classification", c.p);
        check(st.top1.empty() && st.conf == 0.0f && st.dist.empty(), what);
    }

    ui::UiState st;
    st.status = ui::Status::NoSignal;
    st.top1 = "KEPT";
    st.conf = 0.5f;
    ui::StateEvent se;
    se.presence_state = "SIGNAL_PRESENT";
    se.run_state = "RUNNING";
    ui::apply_state_event(st, se);
    check(st.status == ui::Status::NoSignal, "SIGNAL_PRESENT state does NOT forge Live");
    check(st.top1 == "KEPT" && st.conf == 0.5f,
          "SIGNAL_PRESENT state does not clear classification");
}

// (4) the new labels read distinctly (SIGNAL LOST / RX ERROR), never as MOCK or LIVE.
void test_status_labels() {
    check(std::string(ui::status_label(ui::Status::SignalLost)) == "SIGNAL LOST",
          "status_label SignalLost == \"SIGNAL LOST\"");
    check(std::string(ui::status_label(ui::Status::Invalid)) == "RX ERROR",
          "status_label Invalid == \"RX ERROR\"");
    check(std::string(ui::status_label(ui::Status::Acquiring)) == "ACQUIRING",
          "status_label Acquiring == \"ACQUIRING\"");
    check(std::string(ui::status_label(ui::Status::NoSignal)) == "NO SIGNAL",
          "status_label NoSignal == \"NO SIGNAL\"");
}

// (5) status_badge_shape_cx: Invalid/Error use the r==9 shape (filled triangle),
// SignalLost/NoSignal use the r==8 shape (hollow circle).  Reconstruct r from the
// documented formula x_right - text_width - 10 - r using the SAME Bold-20 font.
void test_status_badge_radius() {
    const ui::font_t* fv = ui::font_get(ui::Weight::Bold, ui::font_tier::kValue);
    check(fv != nullptr, "Bold 20 font is baked");
    auto radius = [&](ui::Status s) {
        const std::string lbl = ui::status_label(s);
        return 1000 - ui::status_badge_shape_cx(s, 1000) - ui::text_width(lbl, fv) - 10;
    };
    check(radius(ui::Status::Invalid) == 9, "Invalid badge uses r==9");
    check(radius(ui::Status::Error) == 9, "Error badge uses r==9 (same shape)");
    check(radius(ui::Status::SignalLost) == 8, "SignalLost badge uses r==8");
    check(radius(ui::Status::NoSignal) == 8, "NoSignal badge uses r==8");
}

// (6) the three hero branches return before the default classification path, so
// they never draw the confidence bar (th.accent_bar_bg) or the Top-N bars; a Live
// frame does.  Acquiring/SignalLost render amber (warning), Invalid renders red.
void test_hero_render_no_default_path() {
    const ui::Theme& th = ui::theme_default();

    const ui::Status heroes[] = {ui::Status::Acquiring, ui::Status::SignalLost,
                                 ui::Status::Invalid};
    for (ui::Status s : heroes) {
        std::vector<std::uint16_t> px;
        ui::Canvas c = make_canvas(px);
        ui::UiState st;
        st.status = s;
        st.classes = &ui::classes_12();
        ui::render_main(c, th, st);
        check(non_bg(c, th) > 10000, "hero state draws content");
        // The default classification path draws the confidence bar and the Top-N
        // probability bars (both th.accent_bar_bg) inside the content area.  The
        // hero branches return before that, so no accent_bar_bg may appear above
        // the info strip.  (Bound to y < kInfoY0 because the info strip's own
        // surface_alt fill quantizes to the SAME RGB565 value as accent_bar_bg.)
        check(count_color_above(c, ui::layout::kInfoY0, th.accent_bar_bg) == 0,
              "hero state draws NO confidence bar / Top-N (no default path)");
    }

    {
        std::vector<std::uint16_t> a, l, i;
        ui::Canvas ca = make_canvas(a), cl = make_canvas(l), ci = make_canvas(i);
        ui::UiState sa; sa.status = ui::Status::Acquiring;  sa.classes = &ui::classes_12();
        ui::UiState sl; sl.status = ui::Status::SignalLost; sl.classes = &ui::classes_12();
        ui::UiState si; si.status = ui::Status::Invalid;    si.classes = &ui::classes_12();
        ui::render_main(ca, th, sa);
        ui::render_main(cl, th, sl);
        ui::render_main(ci, th, si);
        check(count_color(ca, th.warning) > 0, "Acquiring draws amber (warning)");
        check(count_color(ca, th.error) == 0, "Acquiring draws no red");
        check(count_color(cl, th.warning) > 0, "SignalLost draws amber (warning)");
        check(count_color(cl, th.error) == 0, "SignalLost draws no red");
        check(count_color(ci, th.error) > 0, "Invalid draws red (error)");
    }

    {
        std::vector<std::uint16_t> px;
        ui::Canvas c = make_canvas(px);
        ui::UiState st = ui::map_to_state(frame_24("SIGNAL_PRESENT"));
        check(st.status == ui::Status::Live, "control frame is Live");
        ui::render_main(c, th, st);
        check(count_color_above(c, ui::layout::kInfoY0, th.accent_bar_bg) > 0,
              "Live frame draws the confidence bar / Top-N");
    }
}

}  // namespace

int main() {
    std::printf("test_ui_nosignal_state\n");
    test_map_to_state_four_states();
    test_hide_classification();
    test_apply_state_event();
    test_status_labels();
    test_status_badge_radius();
    test_hero_render_no_default_path();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
