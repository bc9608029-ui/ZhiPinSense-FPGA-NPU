// test_ui_boundary.cpp -- host tests for the M29 Task B UI redesign's structural
// guarantees: fail-closed rendering on non-1280x720 canvases, the real font-metric
// API (text_box / fit_text / ellipsize_text / draw_text_clipped), worst-string
// collision coverage, no-layout-jump on value-length change, touch hitbox ==
// visible button, and the contrast of the new argmax/hero inks.
//
// Links the REAL render stack (ui_sw/font_atlas.cpp + font_atlas_data.cpp +
// ui_render.cpp) so every assertion runs the exact code the board draws, and is
// run under ASan/UBSan so any out-of-bounds write is caught here, not on the board.
//
// Build/run: see host_tests/build_host_tests.sh (g++ -O2 -Wall -Wextra -Werror).

#include "../ui_sw/ui_layout.hpp"
#include "../ui_sw/ui_render.hpp"
#include "../ui_sw/ui_theme.hpp"

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

ui::Canvas make_canvas(std::vector<std::uint16_t>& px, int w, int h, std::uint16_t fill) {
    px.assign(static_cast<std::size_t>(w) * h, fill);
    return ui::Canvas{px.data(), w, h};
}

std::size_t count_nonzero(const ui::Canvas& c, int x_from) {
    std::size_t n = 0;
    for (int y = 0; y < c.h; ++y)
        for (int x = x_from; x < c.w; ++x)
            if (c.px[y * c.w + x] != 0) ++n;
    return n;
}

// A minimal 23-class live state (mirrors the snapshot tool's base23).
ui::UiState mk23() {
    ui::UiState st;
    st.status = ui::Status::Live;
    st.source = "SDR";
    st.top1 = "QPSK";
    st.conf = 0.82f;
    std::vector<float> d(23, 0.008f);
    d[4] = 0.82f;
    st.dist = d;
    st.classes = &ui::classes_23();
    st.class_count = 23;
    st.model_mode = "RML23-AMSSB-MERGED";
    st.snr = "+18.5 dB";
    st.lat = "12.4 ms";
    st.frame = "240";
    st.model = "2425d990";
    st.work_mode = "FIXED";
    st.running = true;
    st.ctl_connected = "CONTROL CONNECTED";
    return st;
}

// ---- (1) fail-closed on any non-1280x720 canvas (requirement #24) ----------
// A canvas of any other size must be left completely untouched (no out-of-bounds
// drawing, no partial fill): the render_* entry returns before the first write.
void test_fail_closed() {
    const ui::Theme& th = ui::theme_default();
    const ui::UiState st = mk23();
    const std::uint16_t sentinel = 0x1234;

    const int sizes[3][2] = {{640, 360}, {1280, 800}, {1024, 720}};
    const char* names[3] = {"640x360", "1280x800", "1024x720"};

    for (int s = 0; s < 3; ++s) {
        const int w = sizes[s][0], h = sizes[s][1];
        std::vector<std::uint16_t> a, b, c, d, e, f;
        ui::Canvas ca = make_canvas(a, w, h, sentinel);
        ui::Canvas cb = make_canvas(b, w, h, sentinel);
        ui::Canvas cc = make_canvas(c, w, h, sentinel);
        ui::Canvas cd = make_canvas(d, w, h, sentinel);
        ui::Canvas ce = make_canvas(e, w, h, sentinel);
        ui::Canvas cf = make_canvas(f, w, h, sentinel);

        ui::render_main(ca, th, st);
        ui::render_diag(cb, th, st);
        ui::render_touch(cc, th, st);
        ui::render_parameters(cd, th, st);
        ui::render_mode(ce, th, st);
        ui::render_legend(cf, th);

        std::size_t untouched = 0;
        for (const std::uint16_t p : a) if (p == sentinel) ++untouched;
        check(untouched == a.size(), (std::string("main fail-closed ") + names[s]).c_str());
        untouched = 0;
        for (const std::uint16_t p : b) if (p == sentinel) ++untouched;
        check(untouched == b.size(), (std::string("diag fail-closed ") + names[s]).c_str());
        untouched = 0;
        for (const std::uint16_t p : c) if (p == sentinel) ++untouched;
        check(untouched == c.size(), (std::string("touch fail-closed ") + names[s]).c_str());
        untouched = 0;
        for (const std::uint16_t p : d) if (p == sentinel) ++untouched;
        check(untouched == d.size(), (std::string("params fail-closed ") + names[s]).c_str());
        untouched = 0;
        for (const std::uint16_t p : e) if (p == sentinel) ++untouched;
        check(untouched == e.size(), (std::string("mode fail-closed ") + names[s]).c_str());
        untouched = 0;
        for (const std::uint16_t p : f) if (p == sentinel) ++untouched;
        check(untouched == f.size(), (std::string("legend fail-closed ") + names[s]).c_str());
    }
}

// ---- (2) real font-metric API (requirement #13) ----------------------------
void test_font_metrics() {
    const ui::font_t* f40 = ui::font_get(ui::Weight::Bold, 40);
    const ui::font_t* f20 = ui::font_get(ui::Weight::Bold, 20);
    check(f40 && f20, "font metrics: fonts available");

    // text_box == advance + ascent/descent box.
    {
        const ui::TextBox b = ui::text_box("QPSK", f40, 44, 196);
        check(b.x == 44 && b.y == 196 - static_cast<int>(f40->ascent), "text_box x/y");
        check(b.w == ui::text_width("QPSK", f40), "text_box w == text_width");
        check(b.h == static_cast<int>(f40->ascent) + static_cast<int>(f40->descent),
              "text_box h == ascent+descent");
    }

    // fit_text: the returned prefix always fits, and a short string is untouched.
    {
        const std::string fit = ui::fit_text("AM-DSB-SC", f20, 60);
        check(ui::text_width(fit, f20) <= 60, "fit_text fits within max_w");
        check(!fit.empty(), "fit_text of a non-empty string is non-empty");
        check(ui::fit_text("QPSK", f20, 400) == "QPSK", "fit_text short string unchanged");
    }

    // ellipsize_text: result fits, ends in ".." when truncated, unchanged when it fits.
    {
        const std::string e = ui::ellipsize_text("AM-DSB-SC-AM-SSB-FM", f20, 60);
        check(ui::text_width(e, f20) <= 60, "ellipsize_text fits within max_w");
        check(e.size() >= 2 && e.substr(e.size() - 2) == "..", "ellipsize ends in two dots");
        check(ui::ellipsize_text("QPSK", f20, 400) == "QPSK", "ellipsize short unchanged");
    }

    // draw_text_clipped: nothing may be written past [x, x+max_w).
    {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH, 0);
        ui::Canvas c{px.data(), kW, kH};
        ui::draw_text_clipped(c, "AM-DSB-SC-AM-SSB-FM-GMSK-OQPSK", 0, 60, 50,
                              ui::theme_default().text_primary, f20);
        check(count_nonzero(c, 50) == 0, "draw_text_clipped writes nothing past clip edge");
    }
}

// ---- (3) worst-string collision coverage (requirements #14/#15) ------------
void test_worst_strings() {
    using namespace ui::layout;
    const ui::font_t* f40 = ui::font_get(ui::Weight::Bold, 40);
    const ui::font_t* f28 = ui::font_get(ui::Weight::Bold, 28);
    const ui::font_t* f20 = ui::font_get(ui::Weight::Bold, 20);
    const ui::font_t* m20 = ui::font_get(ui::Weight::Mono, 20);
    const ui::font_t* r20 = ui::font_get(ui::Weight::Regular, 20);
    check(f40 && f28 && f20 && m20 && r20, "worst-string fonts available");

    // Hero: the widest top1 (AM-DSB-SC) must end before the confidence bar.
    check(kContentInsetX + ui::text_width("AM-DSB-SC", f40) < kHeroConfBarX0,
          "worst top1 ends before confidence bar");
    // Hero: the widest confidence value ("100.0%") right-aligned stays right of the bar.
    check(kContentRightX - ui::text_width("100.0%", f28) > kHeroConfBarX0,
          "worst confidence value stays right of the bar");

    // Category table: worst class name ends before the probability bar.
    check(kCategoryNameX + ui::text_width("AM-DSB-SC", f20) < kCategoryBarX0,
          "worst class name ends before the bar");
    // Category table: worst percentage ("100.0%") right-aligned stays right of the bar.
    check(kContentRightX - ui::text_width("100.0%", m20) > kCategoryBarX1,
          "worst percentage stays right of the bar");

    // Top bar: model caption + page title end before the MODE label.
    check(kTopBarTitleX + ui::text_width("RML23-AMSSB-MERGED", r20) < kTopBarModeLabelX,
          "model caption ends before MODE label");
    check(kTopBarTitleX + ui::text_width("DIAGNOSTICS", f28) < kTopBarModeLabelX,
          "worst page title ends before MODE label");

    // Top bar: the NO SIGNAL badge shape stays clear of the CTRL value (the
    // model SHA is no longer in the top bar; it lives in the info strip).
    {
        const int cx = ui::status_badge_shape_cx(ui::Status::NoSignal, kTopBarBadgeRightX);
        check(cx - 8 > kTopBarCtlValueX + ui::text_width("DISCONNECTED", f20),
              "NO SIGNAL badge shape clear of the CTRL value");
    }

    // Top bar: worst MODE / RUN / CTRL values end before the next fixed anchor.
    check(kTopBarModeValueX + ui::text_width("BAND SCAN", f20) < kTopBarRunX,
          "worst mode value ends before RUN anchor");
    check(kTopBarRunX + ui::text_width("RUNNING", f20) < kTopBarCtlLabelX,
          "worst run value ends before CTRL label");

    // Info strip: the model SHA (provenance, now a fifth column) fits its segment.
    check(ui::text_width("2425d990", f20) < 1232 / 5,
          "model SHA fits within the info-strip MODEL segment");
}

// ---- (4) no layout jump (requirement #10) ----------------------------------
// A longer top1 changes only the hero; the category table below it is unchanged.
void test_no_layout_jump() {
    const ui::Theme& th = ui::theme_default();
    ui::UiState a = mk23();
    ui::UiState b = mk23();
    b.top1 = "AM-DSB-SC";

    std::vector<std::uint16_t> pa, pb;
    ui::Canvas ca = make_canvas(pa, kW, kH, 0);
    ui::Canvas cb = make_canvas(pb, kW, kH, 0);
    ui::render_main(ca, th, a);
    ui::render_main(cb, th, b);

    std::size_t diff = 0;
    for (int y = 300; y <= 548; ++y)
        for (int x = 0; x < kW; ++x)
            if (pa[static_cast<std::size_t>(y) * kW + x] !=
                pb[static_cast<std::size_t>(y) * kW + x]) ++diff;
    check(diff == 0, "category table does not move when top1 length changes");

    // And the top1 did actually change somewhere (sanity: the hero region differs).
    std::size_t hero_diff = 0;
    for (int y = 84; y <= 276; ++y)
        for (int x = 0; x < kW; ++x)
            if (pa[static_cast<std::size_t>(y) * kW + x] !=
                pb[static_cast<std::size_t>(y) * kW + x]) ++hero_diff;
    check(hero_diff > 0, "hero region does change (different top1 drawn)");
}

// ---- (5) touch hitbox == visible button (requirement #12) ------------------
// The renderer fills exactly the mode_ui::button_rect body (single source of
// truth shared with the touch hit-test), and nothing bleeds into the gap.
void test_button_hitbox() {
    const ui::Theme& th = ui::theme_default();
    ui::UiState st = mk23();
    st.work_mode = "FIXED";
    st.running = true;   // FIXED active, START disabled

    std::vector<std::uint16_t> px;
    ui::Canvas c = make_canvas(px, kW, kH, 0);
    ui::render_mode(c, th, st);

    for (int i = 0; i < 3; ++i) {
        int x0, y0, x1, y1;
        ui::mode_ui::button_rect(i, x0, y0, x1, y1);
        const std::uint16_t want = (i == 0) ? th.surface : th.surface_alt;
        check(c.px[(y0 + 10) * kW + (x0 + 10)] == want,
              "mode button body fill matches button_rect");
        // the pixel immediately right of the button is the gutter (background).
        check(c.px[(y0 + 10) * kW + (x1 + 1)] == th.background,
              "no button fill bleeds into the gutter");
    }
}

// ---- (6) contrast of the new argmax / hero inks (requirement #19) ----------
void test_redesign_contrast() {
    const ui::Theme& th = ui::theme_default();
    check(ui::contrast_ratio(th.selected, th.surface_alt) >= 4.5,
          "selected on surface_alt >= 4.5:1 (argmax row name)");
    check(ui::contrast_ratio(th.text_primary, th.surface_alt) >= 4.5,
          "text_primary on surface_alt >= 4.5:1 (argmax row % / idx)");
    check(ui::contrast_ratio(th.success, th.surface) >= 4.5,
          "success on surface >= 4.5:1 (confidence value)");
    check(ui::contrast_ratio(th.warning, th.surface) >= 4.5,
          "warning on surface >= 4.5:1 (low confidence value)");
}

}  // namespace

int main() {
    std::printf("test_ui_boundary\n");
    test_fail_closed();
    test_font_metrics();
    test_worst_strings();
    test_no_layout_jump();
    test_button_hitbox();
    test_redesign_contrast();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
