// test_ui_layout_m19.cpp -- host tests for the M19 visual refactor's contract:
// the semantic theme tokens + WCAG contrast, the four font tiers, the 8 px grid
// and frozen bands, the top status bar's fixed (non-overlapping) x anchors, and
// the MODE-page button geometry + START/STOP disabled semantics.
//
// These assertions lock the *structural* guarantees of the M19 skeleton.  The
// pixel-level look of the four pages is covered by make_ui_m19_snapshots.cpp
// (seven fixed-input PPM snapshots under artifacts/ui_m19/) plus the existing
// test_ui_live / test_ui_v3_pages render smoke tests.
//
// Build/run: see host_tests/build_host_tests.sh (g++ -O2 -Wall -Wextra -Werror).

#include "../board_package/touch_geometry.hpp"   // ui_touch::kNavY0/.. cross-check
#include "../ui_sw/ui_layout.hpp"
#include "../ui_sw/ui_render.hpp"
#include "../ui_sw/ui_theme.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <set>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

std::size_t count_color(const ui::Canvas& c, int x0, int y0, int x1, int y1,
                        std::uint16_t color) {
    std::size_t n = 0;
    for (int y = y0; y <= y1; ++y)
        for (int x = x0; x <= x1; ++x)
            if (x >= 0 && x < c.w && y >= 0 && y < c.h && c.px[y * c.w + x] == color)
                ++n;
    return n;
}

// ---- (1) theme tokens exist and meet WCAG contrast -------------------------
void test_theme_contrast() {
    const ui::Theme& th = ui::theme_default();

    // All semantic tokens are set (non-zero is enough to catch an uninitialised
    // field or a reordering bug in the aggregate initializer).
    const std::uint16_t* all[13] = {
        &th.background, &th.surface, &th.surface_alt, &th.outline,
        &th.text_primary, &th.text_secondary, &th.interactive, &th.selected,
        &th.success, &th.warning, &th.error, &th.disabled, &th.accent_bar_bg,
    };
    for (std::uint16_t const* p : all) check(*p != 0, "theme token is set");

    // selected == interactive (they are one highlight color, split for naming).
    check(th.selected == th.interactive, "selected == interactive");

    // WCAG: text colors on the two text backgrounds must be >= 4.5:1.
    const std::uint16_t bgs[2] = {th.surface, th.background};
    const struct { std::uint16_t c; const char* name; } texts[6] = {
        {th.text_primary, "text_primary"},
        {th.text_secondary, "text_secondary"},
        {th.interactive, "interactive"},
        {th.success, "success"},
        {th.warning, "warning"},
        {th.error, "error"},
    };
    for (std::uint16_t bg : bgs)
        for (const auto& t : texts) {
            const double cr = ui::contrast_ratio(t.c, bg);
            check(cr >= 4.5, ("contrast " + std::string(t.name) + " >= 4.5:1").c_str());
        }

    // disabled is deliberately low-contrast (exempt; never used for status alone).
    check(ui::contrast_ratio(th.disabled, th.surface) < 4.5, "disabled is low-contrast");
}

// ---- (2) four font tiers, all baked, all in spec range ---------------------
void test_font_tiers() {
    using namespace ui::font_tier;
    check(kMain >= 40 && kMain <= 48, "kMain in [40,48]");
    check(kTitle >= 28 && kTitle <= 32, "kTitle in [28,32]");
    check(kButton >= 20 && kButton <= 24, "kButton in [20,24]");
    check(kValue >= 20 && kValue <= 24, "kValue in [20,24]");
    check(kLabel >= 16, "kLabel >= 16");

    // At most four distinct sizes (M19 D1).  kValue == kLabel == 20 by design.
    std::set<int> tiers = {kMain, kTitle, kButton, kValue, kLabel};
    check(tiers.size() <= 4, "<= 4 distinct font sizes");

    // Every tier is actually baked into the atlas (no runtime scaling exists).
    check(ui::font_get(ui::Weight::Bold, kMain) != nullptr, "Bold kMain baked");
    check(ui::font_get(ui::Weight::Bold, kTitle) != nullptr, "Bold kTitle baked");
    check(ui::font_get(ui::Weight::Bold, kButton) != nullptr, "Bold kButton baked");
    check(ui::font_get(ui::Weight::Bold, kValue) != nullptr, "Bold kValue baked");
    check(ui::font_get(ui::Weight::Regular, kLabel) != nullptr, "Regular kLabel baked");
    check(ui::font_get(ui::Weight::Mono, kValue) != nullptr, "Mono kValue baked");
}

// ---- (3) 8 px grid + frozen bands + cross-check with touch geometry --------
void test_grid_and_bands() {
    using namespace ui::layout;
    check(kXs == 4 && kSm == 8 && kMd == 16 && kLg == 24 && kXl == 32, "8px grid units");
    check(kUnit == 8, "kUnit == 8");
    check(kMarginX == 3 * kUnit && kMarginY == 3 * kUnit, "margins == 3 units");
    check(kScreenW == 1280 && kScreenH == 720, "screen 1280x720");

    // Frozen bands (info strip + bottom nav) match the touch geometry exactly.
    check(kInfoY0 == 558 && kInfoY1 == 624, "info strip band");
    check(kNavY0 == 630 && kNavY1 == 719 && kNavTabCount == 3, "nav band");
    check(kNavY0 == ui_touch::kNavY0 && kNavY1 == ui_touch::kNavY1,
          "layout nav band == touch geometry nav band");
    check(kNavTabCount == ui_touch::kTabCount, "nav tab count == touch geometry");

    // The nav band is >= 64 px physical after the 0.833x panel scale.
    check((kNavY1 - kNavY0 + 1) * 0.833 >= 64.0, "nav band >= 64px physical");
}

// ---- (4) top status bar: fixed anchors never overlap -----------------------
void test_top_bar_no_overlap() {
    using namespace ui::layout;
    const ui::font_t* title_f = ui::font_get(ui::Weight::Bold, ui::font_tier::kTitle);
    const ui::font_t* value_f = ui::font_get(ui::Weight::Bold, ui::font_tier::kValue);
    check(title_f && value_f, "top-bar fonts available");

    // Title left-anchored at kTopBarTitleX; the widest page title must still end
    // before divider 1 (worst case over every page: main / parameters / mode /
    // diagnostics / touch).
    int title_end = kTopBarTitleX;
    for (const char* t : {"SDR AMR", "PARAMETERS", "MODE", "DIAGNOSTICS", "TOUCH TEST"})
        title_end = std::max(title_end, kTopBarTitleX + ui::text_width(t, title_f));
    check(title_end < kTopBarDivider1X, "title ends before divider 1");

    // Mode value (worst case "BAND SCAN") ends before divider 2.
    const int mode_end = kTopBarModeValueX +
        std::max(ui::text_width("AUTO LOCK", value_f), ui::text_width("BAND SCAN", value_f));
    check(mode_end < kTopBarDivider2X, "mode value ends before divider 2");

    // Run value (worst case "RUNNING") ends before divider 3.
    const int run_end = kTopBarRunX +
        std::max(ui::text_width("RUNNING", value_f), ui::text_width("STOPPED", value_f));
    check(run_end < kTopBarDivider3X, "run value ends before divider 3");

    // Ctrl value (worst case "DISCONNECTED") ends before the signal status badge
    // shape (worst case "NO SIGNAL" hollow circle, the widest label).  The model
    // SHA no longer lives in the top bar (it is a third-tier info-strip column),
    // so the badge is the sole right-aligned element.
    const int ctl_end = kTopBarCtlValueX +
        std::max(ui::text_width("CONNECTED", value_f), ui::text_width("DISCONNECTED", value_f));
    const int badge_shape_left =
        ui::status_badge_shape_cx(ui::Status::NoSignal, kTopBarBadgeRightX) - 8;
    check(ctl_end < badge_shape_left, "ctrl value ends before the status badge shape");
}

// ---- (5) MODE-page geometry: buttons above nav, >= 64 px physical ----------
void test_mode_geometry() {
    // Mode buttons (0..2) sit at y 90..190; START/STOP (3..4) at y 200..288; both
    // are ABOVE the bottom nav (630) and within the 1280x720 canvas.
    for (int i = 0; i < ui::mode_ui::kBtnCount; ++i) {
        int x0, y0, x1, y1;
        ui::mode_ui::button_rect(i, x0, y0, x1, y1);
        check(x0 >= 0 && x1 <= 1280 && y0 >= 0 && y1 < 630, "button within canvas above nav");
        const double phys = (y1 - y0 + 1) * 0.833;
        check(phys >= 64.0, "button >= 64px physical");
    }
    // Mode buttons and START/STOP rows do not overlap.
    {
        int a0, ay0, a1, ay1, b0, by0, b1, by1;
        ui::mode_ui::button_rect(ui::mode_ui::kBtnBandScan, a0, ay0, a1, ay1);
        ui::mode_ui::button_rect(ui::mode_ui::kBtnStart, b0, by0, b1, by1);
        check(ay1 < by0, "mode row ends above START row");
    }
    // Detail card ends above the info strip.
    check(ui::mode_ui::kDetailY1 < ui::layout::kInfoY0, "detail card ends above info strip");
}

// ---- (6) START/STOP disabled semantics -------------------------------------
// When RUNNING, START is disabled (dim) and STOP is enabled (amber).  When
// STOPPED, the reverse holds.  We assert the disabled-ink color appears only in
// the disabled button's body (the enabled button uses its own success/warning ink
// and never the disabled token).
void test_start_stop_disabled() {
    const ui::Theme& th = ui::theme_default();
    const int W = 1280, H = 720;
    int sx0, sy0, sx1, sy1, tx0, ty0, tx1, ty1;
    ui::mode_ui::button_rect(ui::mode_ui::kBtnStart, sx0, sy0, sx1, sy1);
    ui::mode_ui::button_rect(ui::mode_ui::kBtnStop, tx0, ty0, tx1, ty1);

    auto render_with = [&](bool running) {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H, th.background);
        ui::Canvas c{px.data(), W, H};
        ui::UiState st;
        st.running = running;
        st.work_mode = "FIXED";
        ui::render_mode(c, th, st);
        return px;
    };

    // RUNNING -> START disabled, STOP enabled.
    {
        std::vector<std::uint16_t> px = render_with(true);
        ui::Canvas c{px.data(), W, H};
        check(count_color(c, sx0, sy0, sx1, sy1, th.disabled) > 0,
              "RUNNING: START carries disabled ink");
        check(count_color(c, tx0, ty0, tx1, ty1, th.disabled) == 0,
              "RUNNING: STOP has no disabled ink");
    }
    // STOPPED -> START enabled, STOP disabled.
    {
        std::vector<std::uint16_t> px = render_with(false);
        ui::Canvas c{px.data(), W, H};
        check(count_color(c, sx0, sy0, sx1, sy1, th.disabled) == 0,
              "STOPPED: START has no disabled ink");
        check(count_color(c, tx0, ty0, tx1, ty1, th.disabled) > 0,
              "STOPPED: STOP carries disabled ink");
    }
}

// ---- (7) status label + badge geometry (never color alone, never overlap) ---
void test_status_badge() {
    const ui::font_t* f = ui::font_get(ui::Weight::Bold, ui::font_tier::kValue);
    check(f != nullptr, "badge font available");
    check(std::string(ui::status_label(ui::Status::Live)) == "LIVE", "label Live");
    check(std::string(ui::status_label(ui::Status::Stale)) == "STALE", "label Stale");
    check(std::string(ui::status_label(ui::Status::Error)) == "ERROR", "label Error");
    check(std::string(ui::status_label(ui::Status::Mock)) == "MOCK", "label Mock");

    const int x_right = 1255;
    const ui::Status seq[4] = {ui::Status::Live, ui::Status::Stale,
                               ui::Status::Error, ui::Status::Mock};
    for (ui::Status s : seq) {
        const int tw = ui::text_width(ui::status_label(s), f);
        const int r = (s == ui::Status::Error) ? 9 : 8;
        const int cx = ui::status_badge_shape_cx(s, x_right);
        check((x_right - tw) - (cx + r) >= 10, "badge shape >= 10px left of text");
    }
}

}  // namespace

int main() {
    std::printf("test_ui_layout_m19\n");
    test_theme_contrast();
    test_font_tiers();
    test_grid_and_bands();
    test_top_bar_no_overlap();
    test_mode_geometry();
    test_start_stop_disabled();
    test_status_badge();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
