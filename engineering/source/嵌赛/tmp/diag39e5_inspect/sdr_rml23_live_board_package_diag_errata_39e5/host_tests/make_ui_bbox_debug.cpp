// make_ui_bbox_debug.cpp -- Task B deliverable 6: bounding-box debug screenshots.
//
// Renders the MAIN page (23-class worst-string state: AM-DSB-SC top1, 100.0%
// confidence, DISCONNECTED ctrl, NO SIGNAL badge, model 2425d990) and overlays a
// 1 px magenta outline around every text element, computed with the SAME layout
// constants + font-metric API (text_box / text_width) the renderer uses.  Two
// adjacent boxes never overlap -> the human reviewer sees exactly one rectangle
// per text run and no shared pixels.
//
// This tool is a DEBUG AID for the visual acceptance step; the rigorous collision
// proof lives in test_ui_boundary.cpp (assertions over the same constants).
//
// Usage: make_ui_bbox_debug [output-dir]   (writes *.ppm + *.png via ppm2png.py)

#include "../ui_sw/ui_render.hpp"
#include "../ui_sw/ui_layout.hpp"
#include "../ui_sw/ui_theme.hpp"

#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

namespace {

const int kW = 1280, kH = 720;
const std::uint16_t kDebug = 0xF81F;   // magenta

using ui::layout::kTopBarTitleX;
using ui::layout::kTopBarModeLabelX;
using ui::layout::kTopBarModeValueX;
using ui::layout::kTopBarRunX;
using ui::layout::kTopBarCtlLabelX;
using ui::layout::kTopBarCtlValueX;
using ui::layout::kTopBarBadgeRightX;
using ui::layout::kHeroLabelY;
using ui::layout::kHeroValueY;
using ui::layout::kHeroConfBarX0;
using ui::layout::kHeroConfBarY0;
using ui::layout::kHeroConfBarY1;
using ui::layout::kContentInsetX;
using ui::layout::kContentRightX;
using ui::layout::kCategoryHeaderY;
using ui::layout::kCategoryRowsY0;
using ui::layout::kCategoryRowPitch;
using ui::layout::kCategoryRowsPerPage;
using ui::layout::kCategoryNameX;
using ui::layout::kCategoryBarX0;
using ui::layout::kCategoryBarX1;
using ui::layout::kCategoryFooterY;
using ui::layout::kInfoY0;

bool write_ppm(const std::string& path, const ui::Canvas& c) {
    std::FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) { std::fprintf(stderr, "open failed: %s\n", path.c_str()); return false; }
    std::fprintf(f, "P6\n%d %d\n255\n", c.w, c.h);
    for (int i = 0; i < c.w * c.h; ++i) {
        const std::uint16_t v = c.px[i];
        const std::uint8_t r = static_cast<std::uint8_t>(((v >> 11) & 0x1F) << 3 | ((v >> 11) & 0x1F) >> 2);
        const std::uint8_t g = static_cast<std::uint8_t>(((v >> 5) & 0x3F) << 2 | ((v >> 5) & 0x3F) >> 4);
        const std::uint8_t b = static_cast<std::uint8_t>((v & 0x1F) << 3 | (v & 0x1F) >> 2);
        std::fputc(r, f); std::fputc(g, f); std::fputc(b, f);
    }
    std::fclose(f);
    return true;
}

// Outline one text run (baseline at x/y, font f) with a 1 px magenta box.
void bbox(ui::Canvas& c, const std::string& s, const ui::font_t* f, int x, int y) {
    if (!f || s.empty()) return;
    const ui::TextBox b = ui::text_box(s, f, x, y);
    if (b.w <= 0) return;
    int x0 = b.x, y0 = b.y, x1 = b.x + b.w - 1, y1 = b.y + b.h - 1;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= c.w) x1 = c.w - 1;
    if (y1 >= c.h) y1 = c.h - 1;
    for (int xx = x0; xx <= x1; ++xx) { c.px[y0 * c.w + xx] = kDebug; c.px[y1 * c.w + xx] = kDebug; }
    for (int yy = y0; yy <= y1; ++yy) { c.px[yy * c.w + x0] = kDebug; c.px[yy * c.w + x1] = kDebug; }
}

void bbox_right(ui::Canvas& c, const std::string& s, const ui::font_t* f, int x_right, int y) {
    if (!f) return;
    bbox(c, s, f, x_right - ui::text_width(s, f), y);
}

ui::UiState worst23() {
    ui::UiState st;
    st.status = ui::Status::NoSignal;   // widest badge label
    st.source = "SDR";
    st.top1 = "AM-DSB-SC";               // widest 40px class name
    st.conf = 1.0f;                      // "100.0%"
    std::vector<float> d(23, 0.008f);
    d[19] = 0.99f;                       // AM-DSB-SC (deployed slot 19)
    st.dist = d;
    st.classes = &ui::classes_23();
    st.class_count = 23;
    st.model_mode = "RML23-AMSSB-MERGED";
    st.snr = "+18.5 dB";
    st.lat = "12.4 ms";
    st.frame = "240";
    st.model = "2425d990";
    st.work_mode = "BAND SCAN";          // widest mode value
    st.running = true;
    st.ctl_connected = "CONTROL DISCONNECTED";   // widest ctrl value
    st.presence = "NO_SIGNAL";
    return st;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string outdir = (argc > 1) ? argv[1] : "../artifacts/ui_bbox";
    std::error_code ec;
    std::filesystem::create_directories(outdir, ec);
    const ui::Theme& th = ui::theme_default();

    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH, th.background);
    ui::Canvas c{px.data(), kW, kH};
    const ui::UiState st = worst23();
    ui::render_main(c, th, st);

    const ui::font_t* f40 = ui::font_get(ui::Weight::Bold, 40);
    const ui::font_t* f28 = ui::font_get(ui::Weight::Bold, 28);
    const ui::font_t* f20 = ui::font_get(ui::Weight::Bold, 20);
    const ui::font_t* m20 = ui::font_get(ui::Weight::Mono, 20);
    const ui::font_t* r20 = ui::font_get(ui::Weight::Regular, 20);
    if (!(f40 && f28 && f20 && m20 && r20)) { std::fprintf(stderr, "missing font\n"); return 1; }

    // --- top bar ---
    bbox(c, st.model_mode, r20, kTopBarTitleX, 20);
    bbox(c, "SDR AMR", f28, kTopBarTitleX, 50);
    bbox(c, "MODE", r20, kTopBarModeLabelX, 22);
    bbox(c, st.work_mode, f20, kTopBarModeValueX, 50);
    bbox(c, st.running ? "RUNNING" : "STOPPED", f20, kTopBarRunX, 50);
    bbox(c, "CTRL", r20, kTopBarCtlLabelX, 22);
    bbox(c, "DISCONNECTED", f20, kTopBarCtlValueX, 50);
    bbox_right(c, "NO SIGNAL", f20, kTopBarBadgeRightX, 57);

    // --- hero ---
    bbox(c, "RECOGNIZED SIGNAL", f20, kContentInsetX, kHeroLabelY);
    bbox(c, "CONFIDENCE", f20, kHeroConfBarX0, kHeroLabelY);
    bbox(c, st.top1, f40, kContentInsetX, kHeroValueY);
    bbox_right(c, "100.0%", f28, kContentRightX, kHeroValueY);

    // --- category table (page 0) ---
    bbox(c, "CATEGORIES", f20, kContentInsetX, kCategoryHeaderY);
    const std::vector<std::string>& classes = ui::classes_23();
    for (int i = 0; i < kCategoryRowsPerPage; ++i) {
        const int cy = kCategoryRowsY0 + i * kCategoryRowPitch;
        bbox(c, classes[static_cast<std::size_t>(i)], f20, kCategoryNameX, cy + 20);
        char pct[16];
        std::snprintf(pct, sizeof pct, "%4.1f%%",
                      st.dist[static_cast<std::size_t>(i)] * 100.0f);
        bbox_right(c, pct, m20, kContentRightX, cy + 20);
    }
    bbox(c, "PAGE 1/4", r20, kContentInsetX, kCategoryFooterY);

    // --- info strip (5 columns) ---
    const char* labels[5] = {"SNR", "LATENCY", "FRAME", "SOURCE", "MODEL"};
    const std::string values[5] = {st.snr, st.lat, st.frame, st.source, st.model};
    const int seg = 1232 / 5;
    for (int i = 0; i < 5; ++i) {
        const int x = 44 + i * seg;
        bbox(c, labels[i], r20, x, kInfoY0 + 26);
        bbox(c, values[i], f20, x, kInfoY0 + 54);
    }

    const std::string path = outdir + "/main_bbox_worst.ppm";
    const bool ok = write_ppm(path, c);
    std::printf("make_ui_bbox_debug -> %s (%s)\n", path.c_str(), ok ? "OK" : "FAIL");
    return ok ? 0 : 1;
}
