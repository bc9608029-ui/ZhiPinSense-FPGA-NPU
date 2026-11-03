// test_waterfall_render.cpp -- host tests for the spectrum + waterfall page
// (fix10class24-waterfall1, Phase E).
//
// Links the REAL render stack (font_atlas.cpp + font_atlas_data.cpp +
// ui_render.cpp + waterfall_render.cpp) so the page runs the exact code the board
// draws, under -Wall -Wextra -Werror.  Pinned here:
//   * a valid frame draws the spectrum curve + waterfall heatmap + side metrics;
//   * the viridis-like LUT is dark-violet -> yellow (endpoints + luminance);
//   * status is text + color, never color alone: INVALID draws "RX ERROR" in the
//     error ink over a surface_alt heatmap void, STALE/ACQUIRING draw their text;
//   * the power scale (dBFS) and frequency axis (MHz) are drawn as TEXT.

#include "../ui_sw/ui_render.hpp"
#include "../ui_sw/waterfall_history.hpp"
#include "../ui_sw/waterfall_render.hpp"

#include <cstdint>
#include <cstdio>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

const int kW = 1280, kH = 720;

// Plot region geometry (must match waterfall_render.cpp).
const int kPlotLeft = 96, kPlotRight = 863;
const int kMapTop = 232, kMapBottom = 487;
const int kGutterRight = 88;
const int kMetricsX0 = 936, kMetricsX1 = 1240;

std::size_t count_color(const ui::Canvas& c, int x0, int y0, int x1, int y1,
                        std::uint16_t color) {
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= c.w) x1 = c.w - 1;
    if (y1 >= c.h) y1 = c.h - 1;
    std::size_t n = 0;
    for (int y = y0; y <= y1; ++y)
        for (int x = x0; x <= x1; ++x)
            if (c.px[y * c.w + x] == color) ++n;
    return n;
}

std::size_t non_bg(const ui::Canvas& c, const ui::Theme& pal) {
    std::size_t n = 0;
    const std::size_t total = static_cast<std::size_t>(c.w) * c.h;
    for (std::size_t i = 0; i < total; ++i)
        if (c.px[i] != pal.background) ++n;
    return n;
}

// A UiState carrying a valid display spectrum (a signal peak at display bin 160).
ui::UiState make_state() {
    ui::UiState st;
    st.status = ui::Status::Live;
    st.presence = "SIGNAL_PRESENT";
    st.source = "fpga_npu";
    st.meas.valid = true;
    st.meas.noise_floor_dbfs = -50.0;
    st.meas.psd_peak_prominence_db = 44.0;
    st.meas.occupied_bw_hz = 625.0;
    st.meas.spectral_centroid_hz = 16000.0;
    st.meas.spectrum_valid = true;
    st.meas.spectrum_sample_rate_hz = 2560000.0;
    st.meas.spectrum_center_hz = 2400000000.0;
    for (int b = 0; b < 256; ++b) st.meas.spectrum_dbfs_x4[b] = -90;
    st.meas.spectrum_dbfs_x4[160] = -10;  // signal peak
    return st;
}

// A history holding a few rows (older rows quieter, newest with a peak).
ui::WaterfallHistory make_history() {
    ui::WaterfallHistory h;
    std::int16_t row[256];
    for (int i = 0; i < 8; ++i) {
        for (int b = 0; b < 256; ++b) row[b] = -100;
        row[160] = static_cast<std::int16_t>(-20 - i);
        h.push(row, static_cast<std::uint64_t>(i + 1),
               static_cast<std::uint64_t>(i) * 100);
    }
    return h;
}

// (1) a valid frame renders a full page (spectrum curve + heatmap + metrics).
void test_valid_render() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH);
    ui::Canvas c{px.data(), kW, kH};
    ui::WaterfallHistory h = make_history();
    ui::render_parameters(c, pal, make_state(), &h);
    check(non_bg(c, pal) > 20000, "valid spectrum frame draws the full page");
    // the heatmap region carries viridis ink: count pixels that are neither the
    // surface fill, surface_alt, background nor outline (i.e. the heatmap rows).
    std::size_t viridis_px = 0;
    for (int y = kMapTop; y <= kMapBottom; ++y)
        for (int x = kPlotLeft; x <= kPlotRight; ++x) {
            const std::uint16_t v = c.px[y * kW + x];
            if (v != pal.surface && v != pal.surface_alt && v != pal.background &&
                v != pal.outline)
                ++viridis_px;
        }
    check(viridis_px > 2000, "heatmap region draws viridis rows");
}

// (2) viridis-like LUT endpoints: dark violet at 0, yellow at 255.
void test_viridis_endpoints() {
    const std::uint16_t* lut = ui::waterfall_viridis_lut();
    check(lut[0] != lut[255], "LUT endpoints differ");
    check(ui::luminance565(lut[0]) < 0.12, "LUT[0] is dark (violet)");
    check(ui::luminance565(lut[255]) > 0.75, "LUT[255] is bright (yellow)");
}

// (3) INVALID draws "RX ERROR" text in the error ink and clears the heatmap.
void test_invalid_overlay() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH);
    ui::Canvas c{px.data(), kW, kH};
    ui::WaterfallHistory h = make_history();
    ui::UiState st = make_state();
    st.presence = "INVALID";
    ui::render_parameters(c, pal, st, &h);
    // "RX ERROR" glyph ink is present in the map area
    check(count_color(c, kPlotLeft, kMapTop, kPlotRight, kMapBottom, pal.error) > 10,
          "INVALID draws RX ERROR text in error ink");
    // the heatmap void is surface_alt (a corner pixel is not a viridis color)
    check(c.px[kMapTop * kW + kPlotLeft + 4] == pal.surface_alt,
          "INVALID heatmap area is a surface_alt void (no stale heatmap)");
}

// (4) STALE draws "STALE / DATA TIMEOUT" text in the warning ink.
void test_stale_overlay() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH);
    ui::Canvas c{px.data(), kW, kH};
    ui::WaterfallHistory h = make_history();
    ui::UiState st = make_state();
    st.status = ui::Status::Stale;
    ui::render_parameters(c, pal, st, &h);
    check(count_color(c, kPlotLeft, kMapTop, kPlotRight, kMapBottom, pal.warning) > 10,
          "STALE draws overlay text in warning ink");
}

// (5) ACQUIRING draws "ACQUIRING" text in the warning ink.
void test_acquiring_overlay() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH);
    ui::Canvas c{px.data(), kW, kH};
    ui::WaterfallHistory h = make_history();
    ui::UiState st = make_state();
    st.presence = "ACQUIRING";
    ui::render_parameters(c, pal, st, &h);
    check(count_color(c, kPlotLeft, kMapTop, kPlotRight, kMapBottom, pal.warning) > 10,
          "ACQUIRING draws overlay text in warning ink");
}

// (6) the power scale (dBFS) is drawn as text in the left gutter.
void test_power_scale_text() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH);
    ui::Canvas c{px.data(), kW, kH};
    ui::WaterfallHistory h = make_history();
    ui::render_parameters(c, pal, make_state(), &h);
    check(count_color(c, 24, 96, kGutterRight, 220, pal.text_secondary) > 20,
          "power scale (dBFS) labels drawn as text");
}

// (7) the frequency axis (MHz) is drawn as text below the heatmap.
void test_frequency_axis_text() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH);
    ui::Canvas c{px.data(), kW, kH};
    ui::WaterfallHistory h = make_history();
    ui::render_parameters(c, pal, make_state(), &h);
    check(count_color(c, kPlotLeft, 500, kPlotRight, 540, pal.text_secondary) > 20,
          "frequency axis (MHz) labels drawn as text");
}

// (8) the side metrics (labels + values) are drawn as text in the right column.
void test_metrics_text() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH);
    ui::Canvas c{px.data(), kW, kH};
    ui::WaterfallHistory h = make_history();
    ui::render_parameters(c, pal, make_state(), &h);
    check(count_color(c, kMetricsX0, 84, kMetricsX1, 548, pal.text_secondary) > 20,
          "metric labels drawn as text");
    check(count_color(c, kMetricsX0, 84, kMetricsX1, 548, pal.text_primary) > 20,
          "metric values drawn as text");
}

}  // namespace

int main() {
    std::printf("test_waterfall_render\n");
    test_valid_render();
    test_viridis_endpoints();
    test_invalid_overlay();
    test_stale_overlay();
    test_acquiring_overlay();
    test_power_scale_text();
    test_frequency_axis_text();
    test_metrics_text();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
