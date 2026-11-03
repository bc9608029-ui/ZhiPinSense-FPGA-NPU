// test_ui_render.cpp — host-only UI render tests (task 39e5c, item 5).
//
// Four regression groups:
//   1. 8/10/12/16-class boundary: the card grid fits above the info strip.
//   2. text/icon non-overlap: the status-badge shape sits >=10px left of its label.
//   3. error-page nav existence: render_main(Error) keeps info strip + bottom nav.
//   4. mock-not-live: Mock label + hollow shape can never render as the Live badge.
//
// Device-independent: links only font_atlas.cpp + font_atlas_data.cpp + ui_render.cpp.
// Build (host, e.g. WSL):
//   g++ -O2 -std=gnu++17 -Wall -Wextra test_ui_render.cpp font_atlas.cpp
//       font_atlas_data.cpp ui_render.cpp -o test_ui_render

#include "ui_render.hpp"

#include <cstdio>
#include <string>
#include <vector>

namespace {

constexpr int W = 1280, H = 720;

int g_fail = 0;
#define CHECK(cond, msg) do { if (!(cond)) { std::printf("FAIL: %s\n", msg); ++g_fail; } } while (0)

// A UiState with `n` named classes and a distribution that sums to 1.
ui::UiState make_n(int n, const std::vector<std::string>& names, ui::Status status) {
    ui::UiState st;
    st.classes = &names;
    st.status = status;
    st.source = (status == ui::Status::Mock) ? "MOCK" : "SDR";
    st.dist.assign(static_cast<std::size_t>(n), 0.0f);
    float sum = 0.0f;
    for (int i = 0; i < n; ++i) { st.dist[static_cast<std::size_t>(i)] = static_cast<float>(i + 1); sum += static_cast<float>(i + 1); }
    for (int i = 0; i < n; ++i) st.dist[static_cast<std::size_t>(i)] /= sum;
    if (n > 0) { st.top1 = names[0]; st.conf = st.dist[0]; }
    st.snr = "+10 dB"; st.lat = "5.0 ms"; st.frame = "42";
    return st;
}

// True if any pixel in [y0,y1] x [x0,x1] differs from `bg`.
bool band_has_content(const std::vector<std::uint16_t>& buf, int x0, int x1,
                      int y0, int y1, std::uint16_t bg) {
    for (int y = y0; y <= y1; ++y)
        for (int x = x0; x <= x1; ++x)
            if (buf[static_cast<std::size_t>(y) * W + x] != bg) return true;
    return false;
}

} // namespace

int main() {
    const ui::Palette& pal = ui::palette_style_a();
    std::vector<std::uint16_t> buf(static_cast<std::size_t>(W) * H);
    ui::Canvas c{ buf.data(), W, H };

    // ---- 1. 8/10/12/16-class boundary -------------------------------------
    for (int n : {8, 10, 12, 16}) {
        ui::CardGrid g = ui::card_grid(n);
        const int last_bottom = g.y0 + (g.rows - 1) * g.row_pitch + g.card_h;
        CHECK(g.y0 == 300, "card_grid y0 mismatch");
        CHECK(g.rows == (n + 1) / 2, "card_grid rows mismatch");
        CHECK(last_bottom <= 556, "card grid overflows into info strip");

        std::vector<std::string> names;
        names.reserve(static_cast<std::size_t>(n));
        for (int i = 0; i < n; ++i) names.push_back("C" + std::to_string(i + 1));
        ui::UiState st = make_n(n, names, ui::Status::Live);
        std::fill(buf.begin(), buf.end(), 0);
        ui::render_main(c, pal, st);
        CHECK(band_has_content(buf, 25, 1255, 300, 555, pal.bg),
              "render produced no class cards");
    }

    // 12-class contract uses "GFSK" (not the "GFSK/GMSK" slash form) per item 3.
    {
        const std::vector<std::string>& c12 = ui::classes_12();
        bool has_gfsk = false, has_slash = false;
        for (const auto& s : c12) {
            if (s == "GFSK") has_gfsk = true;
            if (s.find('/') != std::string::npos) has_slash = true;
        }
        CHECK(c12.size() == 12, "12-class contract wrong width");
        CHECK(has_gfsk, "12-class contract missing GFSK");
        CHECK(!has_slash, "12-class contract still has GFSK/GMSK slash form");
    }

    // ---- 2. text/icon non-overlap (status badge geometry) -----------------
    {
        const char* labels[4] = {"LIVE", "STALE", "ERROR", "MOCK"};
        const ui::Status ss[4] = {ui::Status::Live, ui::Status::Stale,
                                  ui::Status::Error, ui::Status::Mock};
        const ui::font_t* b20 = ui::font_get(ui::Weight::Bold, 20);
        CHECK(b20 != nullptr, "bold 20px font missing");
        for (int i = 0; i < 4; ++i) {
            const int x_right = 1255;
            const int text_left = x_right - ui::text_width(labels[i], b20);
            const int r = (ss[i] == ui::Status::Error) ? 9 : 8;
            const int cx = ui::status_badge_shape_cx(ss[i], x_right);
            // shape right edge = cx + r; gap to the text's left edge must be >= 10px.
            CHECK(cx + r + 10 <= text_left, "badge shape overlaps status text");
            CHECK(cx + r < text_left, "badge shape not left of text");
        }
    }

    // ---- 3. error-page nav existence --------------------------------------
    {
        ui::UiState err;
        err.status = ui::Status::Error;
        err.source = "SDR";
        err.snr = "--"; err.lat = "--"; err.frame = "--";
        std::fill(buf.begin(), buf.end(), 0);
        ui::render_main(c, pal, err);
        CHECK(band_has_content(buf, 25, 1255, 558, 624, pal.bg),
              "error page missing info strip");
        CHECK(band_has_content(buf, 0, W - 1, 630, 719, pal.bg),
              "error page missing bottom nav");
    }

    // ---- 4. mock-not-live -------------------------------------------------
    {
        CHECK(std::string(ui::status_label(ui::Status::Mock)) == "MOCK", "mock label != MOCK");
        CHECK(std::string(ui::status_label(ui::Status::Live)) == "LIVE", "live label != LIVE");
        CHECK(std::string(ui::status_label(ui::Status::Mock)) !=
                  std::string(ui::status_label(ui::Status::Live)),
              "mock label equals live label (mock impersonates live)");

        // Rendered shape: Mock is a HOLLOW square (center stays background),
        // Live is a FILLED circle (center is the success color).
        ui::UiState mock; mock.status = ui::Status::Mock; mock.source = "MOCK";
        std::fill(buf.begin(), buf.end(), 0);
        ui::render_main(c, pal, mock);
        const int cx_mock = ui::status_badge_shape_cx(ui::Status::Mock, 1255);
        CHECK(buf[38 * W + cx_mock] == pal.bg, "Mock badge shape is not hollow");

        ui::UiState live; live.status = ui::Status::Live; live.source = "SDR";
        std::fill(buf.begin(), buf.end(), 0);
        ui::render_main(c, pal, live);
        const int cx_live = ui::status_badge_shape_cx(ui::Status::Live, 1255);
        CHECK(buf[38 * W + cx_live] == pal.success, "Live badge shape is not filled");
    }

    if (g_fail == 0) {
        std::printf("test_ui_render: ALL PASS\n");
        return 0;
    }
    std::printf("test_ui_render: %d FAIL\n", g_fail);
    return 1;
}
