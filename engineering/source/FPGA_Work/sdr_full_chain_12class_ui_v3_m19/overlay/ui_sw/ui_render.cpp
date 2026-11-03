// ui_render.cpp — Style A page renderers (Main / Parameters / Mode), RGB565.
//
// M19 (界面视觉整理): a unified skeleton — top status bar (system | mode |
// RUN/STOP | control | signal status) + main content + bottom nav — against one
// semantic theme (ui_theme.hpp) and an 8 px grid (ui_layout.hpp).  No shadows /
// blur / gradients / translucent layers; no runtime glyph scaling; status is
// always text + shape + color.

#include "ui_render.hpp"

#include <algorithm>
#include <cstdio>

#include "ui_layout.hpp"

namespace ui {

namespace {

// ---- default class contracts ----------------------------------------------
// 10-class (current V1.1 AMR) and 12-class (target).  Renderer is generic over
// N = dist.size(); the class names come from UiState::classes or CLASSES_10.
const std::vector<std::string> CLASSES_10 = {
    "AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
    "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"
};
const std::vector<std::string> CLASSES_12 = {
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"
};

// ---- font shorthands (baked, no runtime scaling) ---------------------------
const font_t* fb(int sz) { return font_get(Weight::Bold, sz); }
const font_t* fr(int sz) { return font_get(Weight::Regular, sz); }
const font_t* fm(int sz) { return font_get(Weight::Mono, sz); }

// ---- shapes ---------------------------------------------------------------
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

void fill_circle(Canvas& c, int cx, int cy, int r, std::uint16_t color) {
    for (int yy = -r; yy <= r; ++yy)
        for (int xx = -r; xx <= r; ++xx)
            if (xx * xx + yy * yy <= r * r)
                set_px(c, cx + xx, cy + yy, color);
}

void fill_diamond(Canvas& c, int cx, int cy, int r, std::uint16_t color) {
    for (int yy = -r; yy <= r; ++yy) {
        const int lim = r - (yy < 0 ? -yy : yy);
        for (int xx = -lim; xx <= lim; ++xx)
            set_px(c, cx + xx, cy + yy, color);
    }
}

void fill_triangle(Canvas& c, int cx, int cy, int r, std::uint16_t color) {
    // Same mask as the design draft: widest at top, point at bottom.
    for (int yy = -r; yy <= r; ++yy) {
        const float half = (r - yy) * 0.5f + 0.01f;
        const int lim = (int)half;
        for (int xx = -lim; xx <= lim; ++xx)
            set_px(c, cx + xx, cy + yy, color);
    }
}

void fill_square(Canvas& c, int cx, int cy, int r, std::uint16_t color, bool hollow) {
    if (hollow) outline_rect(c, cx - r, cy - r, cx + r, cy + r, color, (r / 3) < 1 ? 1 : (r / 3));
    else        fill_rect(c, cx - r, cy - r, cx + r, cy + r, color);
}

// ---- status ---------------------------------------------------------------
// Signal-status color: LIVE=green, STALE=amber, ERROR=red, MOCK=blue.  Mock is
// deliberately blue (distinct from the three data states AND from idle text).
std::uint16_t status_color(const Theme& th, Status s) {
    switch (s) {
        case Status::Live:  return th.success;
        case Status::Stale: return th.warning;
        case Status::Error: return th.error;
        default:            return th.interactive;   // Mock
    }
}

// ---- status badge: text + shape + color (never color alone) ----------------
// The shape (icon) is drawn >=10px LEFT of the right-aligned status text, so it
// never covers the LIVE/STALE/ERROR/MOCK label.  Geometry comes from
// status_badge_shape_cx() (single source of truth, shared with the host test).
void draw_status_badge(Canvas& c, const Theme& th, Status st, int x_right, int yc) {
    const std::uint16_t col = status_color(th, st);
    const int cx = status_badge_shape_cx(st, x_right);
    switch (st) {
        case Status::Live:  fill_circle(c, cx, yc, 8, col); break;
        case Status::Stale: fill_diamond(c, cx, yc, 8, col); break;
        case Status::Error: fill_triangle(c, cx, yc, 9, col); break;
        default:            fill_square(c, cx, yc, 8, col, true); break;   // Mock: hollow square
    }
    draw_text_right(c, status_label(st), x_right, yc + 7, col, fb(font_tier::kValue));
}

void draw_status_chip(Canvas& c, const Theme& th, const char* label,
                      std::uint16_t col, int x_right, int yc) {
    const font_t* b = fb(font_tier::kValue);
    const int w = text_width(label, b) + 28;
    const int x0 = x_right - w;
    const int y0 = yc - 22;
    fill_rect(c, x0, y0, x_right, yc + 14, th.surface_alt);
    outline_rect(c, x0, y0, x_right, yc + 14, col, 1);
    draw_text_center(c, label, (x0 + x_right) / 2, yc, col, b);
}

// ---- top status bar (M19 unified skeleton) ---------------------------------
// [ system/page title | MODE value | run-dot RUNNING/STOPPED | CTRL state | .. ]
// Left-anchored fixed x positions => a change in one value's length never shifts
// another element (no layout jump).  Model short SHA + signal status badge sit
// right-aligned.
void draw_top_bar(Canvas& c, const Theme& th, const char* title, const UiState& st) {
    fill_rect(c, 0, layout::kTopBarY0, c.w - 1, layout::kTopBarY1, th.surface);
    fill_rect(c, 0, layout::kTopBarDividerY, c.w - 1, layout::kTopBarDividerY, th.outline);

    draw_text(c, title, layout::kTopBarTitleX, 44, th.text_primary, fb(font_tier::kTitle));

    // vertical dividers
    fill_rect(c, layout::kTopBarDivider1X, 16, layout::kTopBarDivider1X, 55, th.outline);
    fill_rect(c, layout::kTopBarDivider2X, 16, layout::kTopBarDivider2X, 55, th.outline);
    fill_rect(c, layout::kTopBarDivider3X, 16, layout::kTopBarDivider3X, 55, th.outline);

    // mode
    draw_text(c, "MODE", layout::kTopBarModeLabelX, 36, th.text_secondary,
              fr(font_tier::kLabel));
    draw_text(c, st.work_mode, layout::kTopBarModeValueX, 36, th.interactive,
              fb(font_tier::kValue));

    // run state (dot + text; never color alone)
    const std::uint16_t run_col = st.running ? th.success : th.warning;
    fill_circle(c, layout::kTopBarRunX - 8, 36, 5, run_col);
    draw_text(c, st.running ? "RUNNING" : "STOPPED", layout::kTopBarRunX, 36, run_col,
              fb(font_tier::kValue));

    // control connection
    const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
    draw_text(c, "CTRL", layout::kTopBarCtlLabelX, 36, th.text_secondary,
              fr(font_tier::kLabel));
    draw_text(c, ctl_ok ? "CONNECTED" : "DISCONNECTED", layout::kTopBarCtlValueX, 36,
              ctl_ok ? th.success : th.warning, fb(font_tier::kValue));

    // model short SHA (provenance; drawn only when set)
    if (!st.model.empty()) {
        draw_text_right(c, st.model, layout::kTopBarModelRightX, 36, th.text_secondary,
                        fm(font_tier::kValue));
    }
    // signal status badge
    draw_status_badge(c, th, st.status, layout::kTopBarBadgeRightX, 36);
}

// ---- info strip (SNR / latency / frame / source) --------------------------
void draw_info_strip(Canvas& c, const Theme& th, const UiState& st) {
    const int y0 = layout::kInfoY0, y1 = layout::kInfoY1;
    fill_rect(c, 25, y0, 1255, y1, th.surface_alt);
    outline_rect(c, 25, y0, 1255, y1, th.outline, 1);
    const struct { const char* k; const std::string* v; } items[4] = {
        {"SNR", &st.snr}, {"LATENCY", &st.lat}, {"FRAME", &st.frame}, {"SOURCE", &st.source},
    };
    const int seg = 1230 / 4;
    int x = 45;
    for (const auto& it : items) {
        draw_text(c, it.k, x, y0 + 26, th.text_secondary, fr(font_tier::kLabel));
        draw_text(c, *it.v, x, y0 + 54, th.text_primary, fb(font_tier::kTitle));
        x += seg;
    }
}

// ---- bottom touch nav (90px raw -> 75px physical; hit >= 60px physical) ----
void draw_nav(Canvas& c, const Theme& th, int active) {
    const int y0 = layout::kNavY0, y1 = layout::kNavY1;
    fill_rect(c, 0, y0, c.w - 1, y1, th.surface);
    outline_rect(c, 0, y0, c.w - 1, y0, th.outline, 1);   // top edge only
    const char* tabs[3] = {"CLASSIFY", "PARAMETERS", "MODE"};
    const int tw = c.w / 3;
    const font_t* b = fb(font_tier::kButton);
    for (int i = 0; i < 3; ++i) {
        const int x0 = i * tw;
        const bool on = (i == active);
        if (on) fill_rect(c, x0 + 10, y0 + 8, x0 + tw - 10, y1 - 8, th.surface_alt);
        const int shape_cx = x0 + 34, shape_cy = y0 + 45;
        const std::uint16_t scol = on ? th.selected : th.text_secondary;
        if (i == 0)      fill_square(c, shape_cx, shape_cy, 9, scol, false);
        else if (i == 1) fill_circle(c, shape_cx, shape_cy, 9, scol);
        else             fill_diamond(c, shape_cx, shape_cy, 9, scol);
        draw_text(c, tabs[i], x0 + 58, y0 + 60, on ? th.selected : th.text_primary, b);
    }
}

// Format a double through snprintf (shared by the PARAMETERS page).
std::string fnum(const char* fmt, double v) {
    char b[48];
    std::snprintf(b, sizeof b, fmt, v);
    return std::string(b);
}

// Draw one key/value row: label left (fixed), value right-aligned (fixed),
// unit left-anchored after the value (fixed).  All three anchor x are constant,
// so a value whose length changes never shifts the label or the unit (no layout
// jump).  Unknown values render as "--" (the baked atlas is ASCII 32..126, so the
// em dash is approximated by a double hyphen), never a fake 0.
void draw_kv_row(Canvas& c, const Theme& th, int x_label, int x_val, int x_unit, int y,
                 const char* label, const std::string& value, const char* unit) {
    draw_text(c, label, x_label, y, th.text_secondary, fr(font_tier::kLabel));
    draw_text_right(c, value, x_val, y, th.text_primary, fm(font_tier::kValue));
    if (unit && unit[0])
        draw_text(c, unit, x_unit, y, th.text_secondary, fr(font_tier::kLabel));
}

// Color for the MODE-page "command status" value (M16).
std::uint16_t command_status_color(const Theme& th, const std::string& s) {
    if (s == "APPLIED") return th.success;
    if (s == "PENDING") return th.warning;
    if (s == "REJECTED" || s == "TIMEOUT") return th.error;
    return th.text_secondary;   // IDLE / "--"
}

// Color for the MODE-page "feedback" value (M18-SW1 Task A): a transient reason
// why a tap produced no command ("ALREADY IN THIS MODE" etc.).
std::uint16_t feedback_color(const Theme& th, const std::string& s) {
    if (s.empty() || s == "--") return th.text_secondary;
    if (s == "CONTROL DISCONNECTED" || s == "SEND FAILED") return th.error;
    if (s.rfind("ALREADY", 0) == 0 || s == "COMMAND IN PROGRESS") return th.warning;
    return th.text_primary;
}

} // namespace

const char* status_label(Status s) {
    switch (s) {
        case Status::Live:  return "LIVE";
        case Status::Stale: return "STALE";
        case Status::Error: return "ERROR";
        default:            return "MOCK";
    }
}

int status_badge_shape_cx(Status st, int x_right) {
    const int text_w = text_width(status_label(st), fb(font_tier::kValue));
    const int r = (st == Status::Error) ? 9 : 8;
    // Shape center sits 10px left of the text, and its half-width r further left,
    // so the shape's right edge is exactly 10px from the text's left edge.
    return x_right - text_w - 10 - r;
}

CardGrid card_grid(int n) {
    const int y0 = 300, y_area_end = 556;   // retained for the class-grid capability
    const int rows = (n + 1) / 2;
    CardGrid g;
    g.y0 = y0;
    g.rows = rows;
    if (rows <= 5) {
        g.row_pitch = 50;   // 10-class layout (unchanged)
        g.card_h = 44;
    } else {
        g.row_pitch = (y_area_end - y0) / rows;
        g.card_h = g.row_pitch - 4;
    }
    return g;
}

void render_legend(Canvas& c, const Theme& th) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    fill_rect(c, 25, 40, 1255, 160, th.surface);
    outline_rect(c, 25, 40, 1255, 160, th.outline, 1);
    draw_text(c, "SIGNAL STATUS (text + shape + color)", 45, 96, th.text_secondary,
              fb(font_tier::kButton));
    const Status seq[4] = {Status::Live, Status::Stale, Status::Error, Status::Mock};
    const int xs[4] = {200, 520, 840, 1160};
    for (int i = 0; i < 4; ++i)
        draw_status_badge(c, th, seq[i], xs[i] + 40, 140);
}

const std::vector<std::string>& classes_10() { return CLASSES_10; }
const std::vector<std::string>& classes_12() { return CLASSES_12; }

void render_main(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const std::vector<std::string>& classes = st.classes ? *st.classes : CLASSES_10;
    const font_t* b20 = fb(font_tier::kValue);
    const font_t* b40 = fb(font_tier::kMain);
    const font_t* r20 = fr(font_tier::kLabel);
    const font_t* m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "SDR AMR", st);

    // result card (top priority)
    fill_rect(c, 25, 84, 1255, 252, th.surface);
    outline_rect(c, 25, 84, 1255, 252, th.outline, 1);

    if (st.status == Status::Error) {
        draw_text(c, "RECOGNIZED SIGNAL", 45, 126, th.text_secondary, b20);
        draw_text(c, "NO SIGNAL", 45, 196, th.error, b40);
        draw_text(c, "Waiting for valid input", 45, 240, th.text_secondary, r20);
        draw_status_chip(c, th, "NO SIGNAL", th.error, 1215, 122);
        draw_info_strip(c, th, st);
        draw_nav(c, th, 0);
        return;
    }

    const float conf = st.conf;
    const std::string& top1 = st.top1;
    const float conf_pct = conf * 100.0f;

    draw_text(c, "RECOGNIZED SIGNAL", 45, 126, th.text_secondary, b20);

    const char* chip_label;
    std::uint16_t chip_col;
    if (st.status == Status::Stale)       { chip_label = "STALE DATA";    chip_col = th.warning; }
    else if (st.status == Status::Mock)   { chip_label = "MOCK DATA";     chip_col = th.interactive; }
    else if (conf >= 0.6f)                { chip_label = "CONFIDENT";     chip_col = th.success; }
    else                                  { chip_label = "LOW CONFIDENCE"; chip_col = th.warning; }
    draw_status_chip(c, th, chip_label, chip_col, 1215, 122);

    std::uint16_t name_col;
    if (st.status == Status::Stale)       name_col = th.text_secondary;
    else if (st.status == Status::Mock)   name_col = th.interactive;
    else                                  name_col = th.text_primary;
    draw_text(c, top1, 45, 200, name_col, b40);

    std::uint16_t conf_col;
    if (st.status == Status::Stale)       conf_col = th.text_secondary;
    else if (st.status == Status::Mock)   conf_col = th.interactive;
    else                                  conf_col = (conf < 0.6f) ? th.warning : th.success;

    draw_text(c, "CONFIDENCE", 45, 240, th.text_secondary, r20);
    char pct[32];
    std::snprintf(pct, sizeof pct, "%.1f%%", conf_pct);
    draw_text(c, pct, 210, 240, conf_col, b40);

    // confidence bar (right of result card)
    const int bar_x0 = 700, bar_x1 = 1215, bar_y0 = 188, bar_y1 = 224;
    fill_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, th.accent_bar_bg);
    outline_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, th.outline, 1);
    if (st.status != Status::Stale) {
        const float wf = conf < 0.0f ? 0.0f : (conf > 1.0f ? 1.0f : conf);
        const int w = static_cast<int>((bar_x1 - bar_x0) * wf);
        fill_rect(c, bar_x0, bar_y0 + 2, bar_x0 + w - 1, bar_y1 - 2, conf_col);
    }

    // Top-3 class probabilities (second priority; M19: at most the top three).
    draw_text(c, "TOP CLASSES", 25, 288, th.text_secondary, b20);

    const std::vector<float>& dist = st.dist;
    const int n = static_cast<int>(classes.size());
    if (n > 0 && dist.size() == static_cast<std::size_t>(n)) {
        std::vector<int> order(static_cast<std::size_t>(n));
        for (int i = 0; i < n; ++i) order[static_cast<std::size_t>(i)] = i;
        std::sort(order.begin(), order.end(), [&](int a, int b) {
            return dist[static_cast<std::size_t>(a)] > dist[static_cast<std::size_t>(b)];
        });
        const int rows_y = 320, row_h = 56, row_pitch = 72;
        const int max_r = n < 3 ? n : 3;
        for (int r = 0; r < max_r; ++r) {
            const int idx = order[static_cast<std::size_t>(r)];
            const bool is_top = (r == 0);
            float p = dist[static_cast<std::size_t>(idx)];
            if (p < 0.0f) p = 0.0f;
            if (p > 1.0f) p = 1.0f;
            const int cy = rows_y + r * row_pitch;
            fill_rect(c, 25, cy, 1255, cy + row_h, th.surface);
            outline_rect(c, 25, cy, 1255, cy + row_h,
                         is_top ? th.selected : th.outline, is_top ? 2 : 1);
            char rank[16];
            std::snprintf(rank, sizeof rank, "%2d", r + 1);
            draw_text(c, rank, 45, cy + 37, is_top ? th.selected : th.text_secondary, m20);
            draw_text(c, classes[static_cast<std::size_t>(idx)], 90, cy + 37,
                      th.text_primary, b20);
            const int bx0 = 320, bx1 = 1100, by0 = cy + 16, by1 = cy + 40;
            fill_rect(c, bx0, by0, bx1, by1, th.accent_bar_bg);
            const int bw = static_cast<int>((bx1 - bx0) * p);
            fill_rect(c, bx0, by0, bx0 + bw, by1, is_top ? th.selected : th.text_secondary);
            char pp[16];
            std::snprintf(pp, sizeof pp, "%4.1f%%", p * 100.0f);
            draw_text_right(c, pp, 1235, cy + 37,
                            is_top ? th.text_primary : th.text_secondary, m20);
        }
    } else {
        draw_text(c, "no probability data", 45, 340, th.text_secondary, r20);
    }

    draw_info_strip(c, th, st);
    draw_nav(c, th, 0);
}

void render_diag(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const font_t* b20 = fb(font_tier::kValue), * b40 = fb(font_tier::kMain);
    const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "DIAGNOSTICS", st);

    if (st.status == Status::Error) {
        fill_rect(c, 25, 90, 1255, 594, th.surface);
        outline_rect(c, 25, 90, 1255, 594, th.outline, 1);
        draw_text(c, "NO DATA", 45, 250, th.error, b40);
        draw_text(c, "diagnostics unavailable - signal pipeline reports no valid frames",
                  45, 310, th.text_secondary, r20);
        draw_nav(c, th, 1);
        return;
    }

    fill_rect(c, 25, 90, 620, 594, th.surface);
    outline_rect(c, 25, 90, 620, 594, th.outline, 1);
    draw_text(c, "LATENCY BREAKDOWN", 45, 132, th.text_secondary, b20);

    const struct { const char* k; const char* v; bool total; } rows[5] = {
        {"render", "4.2 ms", false},
        {"copy (staging)", "0.8 ms", false},
        {"sync + flip", "1.1 ms", false},
        {"capture", "5.6 ms", false},
        {"total", "12.4 ms", true},
    };
    int ry = 200;
    for (const auto& r : rows) {
        if (r.total) {
            outline_rect(c, 45, ry - 16, 600, ry + 12, th.outline, 1);
            draw_text(c, r.k, 57, ry, th.text_primary, b20);
            draw_text_right(c, r.v, 588, ry, th.text_primary, m20);
        } else {
            draw_text(c, r.k, 57, ry, th.text_secondary, r20);
            draw_text_right(c, r.v, 588, ry, th.text_primary, m20);
        }
        ry += 80;
    }

    fill_rect(c, 655, 90, 1255, 594, th.surface);
    outline_rect(c, 655, 90, 1255, 594, th.outline, 1);
    draw_text(c, "DETAILED COUNTS", 675, 132, th.text_secondary, b20);

    const struct { const char* k; const char* v; } cnt[5] = {
        {"frames rendered", "1024"},
        {"frames dropped", "0"},
        {"buffer resets", "0"},
        {"touch events", "57"},
        {"data source", st.source.c_str()},
    };
    ry = 200;
    for (const auto& r : cnt) {
        draw_text(c, r.k, 687, ry, th.text_secondary, r20);
        draw_text_right(c, r.v, 1223, ry, th.text_primary, m20);
        ry += 64;
    }

    draw_text(c, "signal status:", 675, 540, th.text_secondary, r20);
    draw_status_badge(c, th, st.status, 1223, 534);

    draw_nav(c, th, 1);
}

void render_touch(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const font_t* b20 = fb(font_tier::kValue);
    const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "TOUCH TEST", st);

    fill_rect(c, 25, 90, 820, 594, th.surface);
    outline_rect(c, 25, 90, 820, 594, th.outline, 1);
    draw_text(c, "TOUCH CALIBRATION", 45, 132, th.text_secondary, b20);

    const struct { const char* k; const std::string* v; } rows[6] = {
        {"device", &st.touch.device},
        {"vendor", &st.touch.vendor},
        {"axis X", &st.touch.axis_x},
        {"axis Y", &st.touch.axis_y},
        {"mapping X", &st.touch.mapping_x},
        {"mapping Y", &st.touch.mapping_y},
    };
    int ry = 200;
    for (const auto& r : rows) {
        draw_text(c, r.k, 57, ry, th.text_secondary, r20);
        draw_text(c, *r.v, 250, ry, th.text_primary, m20);
        ry += 64;
    }

    fill_rect(c, 850, 90, 1255, 594, th.surface);
    outline_rect(c, 850, 90, 1255, 594, th.outline, 1);
    draw_text(c, "HIT REGIONS", 870, 132, th.text_secondary, b20);

    const char* tabs[3] = {"MAIN", "DIAG", "TOUCH"};
    int tx = 870;
    for (int i = 0; i < 3; ++i) {
        fill_rect(c, tx, 160, tx + 112, 220, th.surface_alt);
        outline_rect(c, tx, 160, tx + 112, 220, i == 2 ? th.selected : th.outline, i == 2 ? 2 : 1);
        draw_text_center(c, tabs[i], tx + 56, 198, i == 2 ? th.selected : th.text_primary, b20);
        tx += 124;
    }
    draw_text(c, "hit area >= 60 px physical", 870, 268, th.text_secondary, r20);
    draw_text(c, "bottom nav height 90 px raw", 870, 300, th.text_secondary, r20);

    const bool tconn = st.touch.connected;
    draw_text(c, "touch:", 870, 470, th.text_secondary, r20);
    draw_text(c, tconn ? "CONNECTED" : "DISCONNECTED", 950, 470,
              tconn ? th.success : th.warning, b20);
    char tstat[48];
    std::snprintf(tstat, sizeof tstat, "taps %llu",
                  static_cast<unsigned long long>(st.touch.taps));
    draw_text(c, tstat, 870, 510, th.text_secondary, r20);
    if (st.touch.last_x >= 0) {
        char pt[48];
        std::snprintf(pt, sizeof pt, "last (%d, %d)", st.touch.last_x, st.touch.last_y);
        draw_text(c, pt, 950, 510, th.text_primary, m20);
    }

    draw_nav(c, th, 2);
}

// ---- PARAMETERS page (UI v3 M5 -> M19 four groups) -------------------------
// Four grouped cards: SIGNAL LEVEL / SPECTRUM / SIGNAL QUALITY / RF
// CONFIGURATION, label-left / value-right / unit-separate.  Measurement numbers
// are gated on meas.valid so an absent v3 producer draws "--" placeholders rather
// than fake zeros; presence / level_mode / model_scale / rf_gain_db / source
// always come from the UiState runtime fields (with their own safe defaults).
namespace {

struct ParamRow { const char* label; std::string value; const char* unit; };

void draw_param_card(Canvas& c, const Theme& th, int x0, int y0, int x1, int y1,
                     const char* title, const ParamRow* rows, int count) {
    fill_rect(c, x0, y0, x1, y1, th.surface);
    outline_rect(c, x0, y0, x1, y1, th.outline, 1);
    draw_text(c, title, x0 + 20, y0 + 40, th.text_secondary, fb(font_tier::kValue));
    const int x_label = x0 + 20;
    const int x_val = x1 - 72;
    const int x_unit = x1 - 56;
    int ry = y0 + 72;
    for (int i = 0; i < count; ++i) {
        draw_kv_row(c, th, x_label, x_val, x_unit, ry, rows[i].label,
                    rows[i].value, rows[i].unit);
        ry += 28;
    }
}

}  // namespace

void render_parameters(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const MeasureView& m = st.meas;
    const bool has = m.valid;

    draw_top_bar(c, th, "PARAMETERS", st);

    // helper: a measurement value + unit, "--"/"" when absent.
    auto mrow = [&](const char* label, const char* fmt, double v, const char* unit) {
        ParamRow r{label, has ? fnum(fmt, v) : std::string("--"),
                   has ? unit : ""};
        return r;
    };

    // SIGNAL LEVEL (top-left)
    {
        ParamRow rows[5] = {
            mrow("Power",        "%.1f", m.power_dbfs,       "dBFS"),
            mrow("RMS",          "%.1f", m.rms_counts,       "counts"),
            mrow("Peak",         "%.1f", m.peak_counts,      "counts"),
            mrow("PAPR",         "%.2f", m.papr_db,          "dB"),
            mrow("Clip",         "%.2f", m.clip_ratio * 100.0, "%"),
        };
        draw_param_card(c, th, 24, 84, 632, 308, "SIGNAL LEVEL", rows, 5);
    }
    // SPECTRUM (top-right)
    {
        ParamRow rows[5] = {
            mrow("Noise floor",  "%.1f", m.noise_floor_dbfs,          "dBFS"),
            mrow("PSD prominence","%.1f", m.psd_peak_prominence_db,   "dB"),
            mrow("Occupied bins", "%.0f", static_cast<double>(m.occupied_bins), "bins"),
            mrow("Occupied BW",   "%.1f", m.occupied_bw_hz,           "Hz"),
            mrow("Centroid",      "%.1f", m.spectral_centroid_hz,     "Hz"),
        };
        draw_param_card(c, th, 648, 84, 1256, 308, "SPECTRUM", rows, 5);
    }
    // SIGNAL QUALITY (bottom-left)
    {
        ParamRow rows[3] = {
            mrow("SNR (est)",    "%.1f", m.snr_est_db, "dB"),
            {"Presence", st.presence, ""},
            mrow("Model RMS",    "%.3f", m.model_rms,  ""),
        };
        draw_param_card(c, th, 24, 324, 632, 548, "SIGNAL QUALITY", rows, 3);
    }
    // RF CONFIGURATION (bottom-right)
    {
        ParamRow rows[4] = {
            {"Level mode",  st.level_mode, ""},
            {"Model scale", fnum("%.3f", st.model_scale), "x"},
            {"RF gain",     fnum("%.1f", st.rf_gain_db),  "dB"},
            {"Source",      st.source, ""},
        };
        draw_param_card(c, th, 648, 324, 1256, 548, "RF CONFIGURATION", rows, 4);
    }

    draw_info_strip(c, th, st);
    draw_nav(c, th, 1);
}

// ---- MODE page (UI v3 M5 -> M16 touch control, M19 status/disabled) --------
// Three mode buttons (name + description + per-button status SELECTED/PENDING/
// IDLE) + START / STOP (disabled when the requested action is already in effect)
// + a detail card (current/requested mode, run state, control channel, last
// command, command status, feedback).  Buttons sit ABOVE the nav band (y < 630),
// so the two tap areas never overlap.
void render_mode(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const font_t* b20 = fb(font_tier::kValue), * b28 = fb(font_tier::kTitle);
    const font_t* r20 = fr(font_tier::kLabel);

    draw_top_bar(c, th, "MODE", st);

    int active = 0;
    if (st.work_mode == "AUTO LOCK") active = 1;
    else if (st.work_mode == "BAND SCAN") active = 2;

    const char* names[3] = {"FIXED", "AUTO LOCK", "BAND SCAN"};
    const char* desc[3] = {
        "fixed gain + fixed scale",
        "auto level, lock stable class",
        "sweep band, lock on signal",
    };
    const bool pending = (st.command_status == "PENDING");
    for (int i = 0; i < 3; ++i) {
        int x0, y0, x1, y1;
        mode_ui::button_rect(i, x0, y0, x1, y1);
        const bool on = (i == active);
        const bool pressed = (st.pressed_button == i);   // M18-SW1 press-highlight
        fill_rect(c, x0, y0, x1, y1, (on || pressed) ? th.surface : th.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? th.interactive : (on ? th.selected : th.outline),
                     pressed ? 3 : (on ? 2 : 1));
        draw_text(c, names[i], x0 + 20, y0 + 44, on ? th.selected : th.text_primary, b28);
        draw_text(c, desc[i], x0 + 20, y0 + 82, th.text_secondary, r20);
        // per-button status tag (right-aligned; SELECTED / PENDING / IDLE)
        const char* tag;
        std::uint16_t tag_col;
        if (on)                                  { tag = "SELECTED"; tag_col = th.selected; }
        else if (pending && st.requested_mode == names[i]) { tag = "PENDING"; tag_col = th.warning; }
        else                                     { tag = "IDLE"; tag_col = th.disabled; }
        draw_text_right(c, tag, x1 - 16, y0 + 44, tag_col, b20);
    }

    // START / STOP: the currently-in-effect action is DISABLED (dim), the other is
    // enabled.  A disabled button still accepts a touch (idempotent -> feedback),
    // but it reads as inactive visually.
    {
        int x0, y0, x1, y1;
        mode_ui::button_rect(mode_ui::kBtnStart, x0, y0, x1, y1);
        const bool enabled = !st.running;
        const bool pressed = (st.pressed_button == mode_ui::kBtnStart) && enabled;
        fill_rect(c, x0, y0, x1, y1, pressed ? th.surface : th.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? th.success : (enabled ? th.success : th.outline),
                     pressed ? 3 : (enabled ? 2 : 1));
        draw_text_center(c, "START", (x0 + x1) / 2, y0 + 52,
                         enabled ? th.success : th.disabled, b28);
    }
    {
        int x0, y0, x1, y1;
        mode_ui::button_rect(mode_ui::kBtnStop, x0, y0, x1, y1);
        const bool enabled = st.running;
        const bool pressed = (st.pressed_button == mode_ui::kBtnStop) && enabled;
        fill_rect(c, x0, y0, x1, y1, pressed ? th.surface : th.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? th.warning : (enabled ? th.warning : th.outline),
                     pressed ? 3 : (enabled ? 2 : 1));
        draw_text_center(c, "STOP", (x0 + x1) / 2, y0 + 52,
                         enabled ? th.warning : th.disabled, b28);
    }

    // detail card: applied vs requested + control-channel state.
    fill_rect(c, 25, mode_ui::kDetailY0, 1255, mode_ui::kDetailY1, th.surface);
    outline_rect(c, 25, mode_ui::kDetailY0, 1255, mode_ui::kDetailY1, th.outline, 1);

    const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
    const std::uint16_t run_col = st.running ? th.success : th.warning;
    const std::uint16_t ctl_col = ctl_ok ? th.success : th.warning;
    const std::uint16_t cmd_col = command_status_color(th, st.command_status);
    const std::uint16_t req_col = (st.requested_mode == st.work_mode)
                                      ? th.text_primary : th.warning;

    int ry = mode_ui::kDetailY0 + 30;
    auto row = [&](const char* label, const std::string& value, std::uint16_t col) {
        draw_text(c, label, 45, ry, th.text_secondary, r20);
        draw_text_right(c, value, 600, ry, col, b20);
        ry += mode_ui::kDetailRowPitch;
    };
    row("current mode", st.work_mode, th.selected);
    row("requested mode", st.requested_mode, req_col);
    row("run state", st.running ? "RUNNING" : "STOPPED", run_col);
    row("control connection", st.ctl_connected, ctl_col);
    row("last command", st.last_command, th.text_primary);
    row("command status", st.command_status, cmd_col);
    row("feedback", st.feedback, feedback_color(th, st.feedback));

    draw_info_strip(c, th, st);
    draw_nav(c, th, 2);
}

} // namespace ui
