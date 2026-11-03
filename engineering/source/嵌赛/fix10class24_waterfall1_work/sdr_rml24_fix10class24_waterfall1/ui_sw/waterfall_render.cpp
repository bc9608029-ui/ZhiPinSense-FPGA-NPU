// waterfall_render.cpp -- spectrum + waterfall page body (fix10class24-waterfall1,
// Phase E).  RGB565, pixel-consistent with ui_render.cpp (no shadows / blur /
// gradients / translucent layers).  Draws ONLY the content area (y 84..548): the
// page skeleton (top bar / info strip / bottom nav) stays in render_parameters().

#include "waterfall_render.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdint>

#include "ui_layout.hpp"
#include "waterfall_history.hpp"

namespace ui {

namespace {

// ---- viridis-like colormap (256-entry RGB565 LUT) ---------------------------
// Dark violet #440154 -> yellow #FDE725, piecewise-linear between the canonical
// keyframes, quantised to RGB565.  Perceptually-uniform sequential: row intensity
// reads monotonically.  NEVER used for status alone (status is always text).
const std::uint16_t kViridis[256] = {
    16394, 16394, 16394, 16426, 16427, 16427, 16459, 16459, 16459, 16491, 16491, 16492, 16524, 16524, 16524, 16556,
    16556, 16557, 16589, 16589, 16589, 16621, 16621, 16653, 16654, 16654, 16686, 16686, 16686, 16718, 16718, 16719,
    16751, 16751, 16751, 16751, 16783, 16783, 16783, 16815, 16815, 16815, 16815, 16847, 16848, 16848, 16880, 16880,
    16880, 16880, 16912, 14864, 14864, 14896, 14896, 14896, 14928, 14928, 14928, 14929, 14961, 14961, 14961, 14993,
    14993, 14993, 14993, 15025, 15025, 15025, 15025, 13009, 13009, 13009, 13009, 13041, 13041, 13041, 13041, 13073,
    13073, 13073, 13073, 13105, 13105, 13105, 13105, 13137, 11089, 11089, 11089, 11121, 11121, 11121, 11121, 11153,
    11153, 11153, 11153, 11185, 11185, 11185, 11185, 11217, 11217, 11217, 11217, 11249, 9201, 9201, 9201, 9201,
    9233, 9233, 9233, 9233, 9265, 9265, 9265, 9265, 9297, 9297, 9297, 9297, 9329, 9329, 9329, 9329,
    9361, 9361, 9361, 9361, 9393, 9393, 9393, 9393, 9393, 9425, 9425, 9425, 9425, 9456, 9456, 9456,
    9456, 9456, 9488, 9488, 9488, 9488, 9520, 9520, 9520, 9520, 9552, 9552, 9552, 9552, 9552, 9584,
    11632, 11631, 11631, 11663, 11663, 13711, 13711, 13711, 13743, 13742, 15790, 15790, 15790, 15822, 15822, 17870,
    17870, 17870, 17901, 17901, 19949, 19949, 19981, 19981, 19981, 22029, 22028, 22060, 22060, 24108, 24108, 24108,
    24140, 26188, 26187, 26187, 26187, 28235, 28267, 28266, 30314, 30314, 30314, 32362, 32393, 32393, 34441, 34441,
    34441, 34440, 36488, 36520, 36520, 38568, 38568, 38567, 40615, 40647, 40647, 40647, 42694, 42694, 42694, 44742,
    44774, 44774, 46822, 46822, 46822, 48869, 48869, 48869, 50917, 50917, 50917, 52997, 52997, 52997, 55045, 55045,
    55045, 57093, 57093, 57093, 59141, 59141, 59141, 61221, 61220, 61220, 61220, 63268, 63268, 63268, 65316, 65316,
};

inline std::uint16_t viridis(double t) {
    if (t <= 0.0) return kViridis[0];
    if (t >= 1.0) return kViridis[255];
    const int i = static_cast<int>(std::lround(t * 255.0));
    return kViridis[static_cast<std::size_t>(i < 0 ? 0 : (i > 255 ? 255 : i))];
}

// ---- font shorthands --------------------------------------------------------
const font_t* fb(int sz) { return font_get(Weight::Bold, sz); }
const font_t* fr(int sz) { return font_get(Weight::Regular, sz); }
const font_t* fm(int sz) { return font_get(Weight::Mono, sz); }

// ---- pixel helpers (file-local; ui_render.cpp keeps its own) ----------------
inline void set_px(Canvas& c, int x, int y, std::uint16_t color) {
    if (x < 0 || x >= c.w || y < 0 || y >= c.h) return;
    c.px[y * c.w + x] = color;
}

void fill_rect(Canvas& c, int x0, int y0, int x1, int y1, std::uint16_t color) {
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= c.w) x1 = c.w - 1;
    if (y1 >= c.h) y1 = c.h - 1;
    if (x0 > x1 || y0 > y1) return;
    for (int y = y0; y <= y1; ++y)
        for (int x = x0; x <= x1; ++x)
            c.px[y * c.w + x] = color;
}

void outline_rect(Canvas& c, int x0, int y0, int x1, int y1, std::uint16_t color, int t) {
    fill_rect(c, x0, y0, x1, y0 + t - 1, color);
    fill_rect(c, x0, y1 - t + 1, x1, y1, color);
    fill_rect(c, x0, y0, x0 + t - 1, y1, color);
    fill_rect(c, x1 - t + 1, y0, x1, y1, color);
}

// ---- fixed geometry ---------------------------------------------------------
constexpr int kPlotLeft = 96;    // first heatmap column x
constexpr int kColW = 3;         // px per display bin (256 * 3 = 768)
constexpr int kPlotRight = kPlotLeft + kWaterfallBins * kColW - 1;  // 863
constexpr int kGutterRight = 88; // right-aligned power-scale labels end here

constexpr int kSpecTop = 96;       // spectrum-curve band top
constexpr int kSpecCurveY0 = 116;  // 0 dBFS (top of curve)
constexpr int kSpecCurveY1 = 212;  // -120 dBFS (bottom of curve)
constexpr int kMapTop = 232;       // waterfall heatmap top
constexpr int kRowH = 2;           // px per history row
constexpr int kMapBottom = kMapTop + kWaterfallMaxRows * kRowH - 1;  // 487
constexpr int kFreqAxisY = 516;    // frequency-axis label baseline

constexpr int kMetricsX0 = 936;
constexpr int kMetricsX1 = 1240;

constexpr double kDbFloor = -120.0;
constexpr double kDbCeil = 0.0;

// Map a dBFS*4 bin value to a colormap coordinate in [0,1].
double colormap_t(int x4) {
    const double db = static_cast<double>(x4) / 4.0;
    const double t = (db - kDbFloor) / (kDbCeil - kDbFloor);
    return t < 0.0 ? 0.0 : (t > 1.0 ? 1.0 : t);
}

// Curve y for a dBFS*4 bin value (top = 0 dBFS).
int curve_y(int x4) {
    const double db = static_cast<double>(x4) / 4.0;
    const double t = (db - kDbFloor) / (kDbCeil - kDbFloor);
    const double clamped = t < 0.0 ? 0.0 : (t > 1.0 ? 1.0 : t);
    return kSpecCurveY0 +
           static_cast<int>(std::lround(clamped * (kSpecCurveY1 - kSpecCurveY0)));
}

std::string fnum(const char* fmt, double v) {
    char b[64];
    std::snprintf(b, sizeof b, fmt, v);
    return std::string(b);
}

}  // namespace

const std::uint16_t* waterfall_viridis_lut() { return kViridis; }

void render_spectrum_waterfall(Canvas& c, const Theme& th, const UiState& st,
                               const WaterfallHistory& history) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;

    const MeasureView& m = st.meas;
    const bool meas_ok = m.valid;
    const bool spec_ok = m.spectrum_valid;
    const std::size_t nrows = history.size();

    // ---- status resolution (text-first, never color alone) -------------------
    const char* overlay = nullptr;
    std::uint16_t overlay_col = th.text_secondary;
    bool show_curve = spec_ok;
    bool show_heatmap = true;

    if (st.status == Status::Error || st.presence == "INVALID") {
        overlay = "RX ERROR";
        overlay_col = th.error;
        show_curve = false;
        show_heatmap = false;
    } else if (st.status == Status::Stale) {
        overlay = "STALE / DATA TIMEOUT";
        overlay_col = th.warning;
    } else if (st.presence == "ACQUIRING") {
        overlay = "ACQUIRING";
        overlay_col = th.warning;
    } else if (st.presence == "SIGNAL_LOST") {
        overlay = "SIGNAL LOST";
        overlay_col = th.disabled;
    }

    const font_t* b20 = fb(font_tier::kValue);
    const font_t* r20 = fr(font_tier::kLabel);
    const font_t* m20 = fm(font_tier::kValue);
    const font_t* b24 = fb(font_tier::kButton);

    // ---- plot panel (spectrum curve + waterfall share one surface) ----------
    fill_rect(c, kPlotLeft - 8, kSpecTop - 8, kPlotRight + 8, kMapBottom + 8, th.surface);
    outline_rect(c, kPlotLeft - 8, kSpecTop - 8, kPlotRight + 8, kMapBottom + 8,
                 th.outline, 1);

    // ---- power scale (dBFS) text on the left gutter -------------------------
    draw_text_right(c, "dBFS", kGutterRight, kSpecCurveY0 + 6, th.text_secondary, r20);
    draw_text_right(c, "0", kGutterRight, kSpecCurveY0 + 7, th.text_secondary, m20);
    draw_text_right(c, "-60", kGutterRight,
                    (kSpecCurveY0 + kSpecCurveY1) / 2 + 7, th.text_secondary, m20);
    draw_text_right(c, "-120", kGutterRight, kSpecCurveY1 + 7, th.text_secondary, m20);

    // ---- spectrum curve (current frame) -------------------------------------
    if (show_curve) {
        for (int b = 0; b < kWaterfallBins; ++b) {
            const int x4 = m.spectrum_dbfs_x4[b];
            const int y = curve_y(x4);
            const int x = kPlotLeft + b * kColW;
            fill_rect(c, x, y, x + kColW - 1, kSpecCurveY1, th.interactive);
        }
    } else {
        draw_text(c, "NO SPECTRUM", kPlotLeft + 8, (kSpecCurveY0 + kSpecCurveY1) / 2 + 7,
                  th.text_secondary, r20);
    }

    // ---- waterfall heatmap (oldest top, newest bottom) ----------------------
    if (show_heatmap && nrows > 0) {
        for (std::size_t r = 0; r < nrows; ++r) {
            const WaterfallHistory::Row& row = history.row(r);
            const int y_bottom = kMapBottom - static_cast<int>((nrows - 1 - r)) * kRowH;
            for (int b = 0; b < kWaterfallBins; ++b) {
                const std::uint16_t col = viridis(colormap_t(row[static_cast<std::size_t>(b)]));
                const int x = kPlotLeft + b * kColW;
                fill_rect(c, x, y_bottom - kRowH + 1, x + kColW - 1, y_bottom, col);
            }
        }
    } else if (show_heatmap) {
        // No history yet (valid listening state with an empty ring).
        draw_text_center(c, "NO WATERFALL DATA", (kPlotLeft + kPlotRight) / 2,
                         (kMapTop + kMapBottom) / 2 + 7, th.text_secondary, r20);
    } else {
        // INVALID: no heatmap at all.
        fill_rect(c, kPlotLeft, kMapTop, kPlotRight, kMapBottom, th.surface_alt);
        draw_text_center(c, "RX ERROR", (kPlotLeft + kPlotRight) / 2,
                         (kMapTop + kMapBottom) / 2 + 7, th.error, b24);
    }

    // ---- status overlay chip (readable over the heatmap; text-first) ---------
    if (overlay != nullptr && show_heatmap) {
        const int tw = text_width(overlay, b24);
        const int cx = (kPlotLeft + kPlotRight) / 2;
        const int x0 = cx - tw / 2 - 12, x1 = cx + tw / 2 + 12;
        const int yc = (kMapTop + kMapBottom) / 2;
        fill_rect(c, x0, yc - 18, x1, yc + 12, th.surface_alt);
        outline_rect(c, x0, yc - 18, x1, yc + 12, th.outline, 1);
        draw_text_center(c, overlay, cx, yc + 7, overlay_col, b24);
    }

    // ---- frequency axis (-fs/2 .. 0 .. +fs/2) --------------------------------
    {
        const double half = spec_ok ? (m.spectrum_sample_rate_hz / 2.0) : 1280000.0;
        const double half_mhz = half / 1.0e6;
        char lo[32], hi[32];
        std::snprintf(lo, sizeof lo, "-%.2f MHz", half_mhz);
        std::snprintf(hi, sizeof hi, "+%.2f MHz", half_mhz);
        draw_text(c, lo, kPlotLeft, kFreqAxisY, th.text_secondary, m20);
        draw_text_center(c, "0", (kPlotLeft + kPlotRight) / 2, kFreqAxisY,
                         th.text_secondary, m20);
        draw_text_right(c, hi, kPlotRight, kFreqAxisY, th.text_secondary, m20);
    }

    // ---- side metrics (right column) ----------------------------------------
    {
        fill_rect(c, kMetricsX0, 84, kMetricsX1, 548, th.surface);
        outline_rect(c, kMetricsX0, 84, kMetricsX1, 548, th.outline, 1);
        draw_text(c, "MEASUREMENTS", kMetricsX0 + 20, 124, th.text_secondary, b20);

        const int x_label = kMetricsX0 + 20;
        const int x_val = kMetricsX1 - 20;
        const int y0 = 168;
        const int pitch = 44;

        auto row = [&](int i, const char* label, const std::string& value,
                       std::uint16_t col) {
            const int y = y0 + i * pitch;
            draw_text(c, label, x_label, y, th.text_secondary, r20);
            draw_text_right(c, value, x_val, y, col, m20);
        };

        row(0, "Noise floor", meas_ok ? fnum("%.1f dBFS", m.noise_floor_dbfs) : std::string("--"),
            th.text_primary);
        row(1, "Peak prominence",
            meas_ok ? fnum("%.1f dB", m.psd_peak_prominence_db) : std::string("--"),
            th.text_primary);
        row(2, "Occupied BW", meas_ok ? fnum("%.0f Hz", m.occupied_bw_hz) : std::string("--"),
            th.text_primary);
        row(3, "Centroid", meas_ok ? fnum("%.0f Hz", m.spectral_centroid_hz) : std::string("--"),
            th.text_primary);
        row(4, "Sample rate", spec_ok ? fnum("%.3f MHz", m.spectrum_sample_rate_hz / 1.0e6)
                                      : std::string("--"),
            th.text_primary);
        row(5, "Center freq", spec_ok ? fnum("%.3f MHz", m.spectrum_center_hz / 1.0e6)
                                      : std::string("--"),
            th.text_primary);

        draw_text(c, "display spectrum; relative dBFS/bin;", kMetricsX0 + 20, 460,
                  th.text_secondary, r20);
        draw_text(c, "not calibrated W/Hz", kMetricsX0 + 20, 484, th.text_secondary, r20);
    }
}

}  // namespace ui
