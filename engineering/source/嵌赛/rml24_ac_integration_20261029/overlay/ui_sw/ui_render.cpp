// ui_render.cpp — Style A page renderers (Main / Parameters / Mode), RGB565.
//
// M29 Task B (UI 视觉重构): the renderers now draw a de-boxed, hierarchical
// layout — a single outlined hero card per page (top1 = the only 40 px first
// focus, confidence = 28 px second tier), a de-boxed category table whose argmax
// row carries a surface_alt fill + 4 px selected accent, a two-row top bar with
// no vertical dividers, and quiet 20 px info-strip values — against the frozen
// M19 semantic theme (ui_theme.hpp) and 8 px grid (ui_layout.hpp).
//
// Every render_* entry is fail-closed on 1280x720: a canvas of any other size is
// refused (drawn as nothing) rather than silently drawn out of bounds.  No
// shadows / blur / gradients / translucent layers; no runtime glyph scaling;
// status is always text + shape + color; worst-case strings are width-checked in
// host_tests/test_ui_boundary.cpp.

#include "ui_render.hpp"

#include <algorithm>
#include <cstdio>

#include "ui_layout.hpp"
#include "waterfall_render.hpp"   // render_spectrum_waterfall (fix10class24-waterfall1)
#include "../board_package/target_list_state.hpp"   // ui::TargetListState (C line)

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
// RML23 deployed 23-class order (== cat::target_23 / rml23::kLabelOrder23).
// AM-SSB-WC/SC merge into one "AM-SSB" slot; NO fake AM-SSB-WC/SC entries.
const std::vector<std::string> CLASSES_23 = {
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB", "AM-DSB-WC", "AM-DSB-SC", "FM", "GMSK",
    "OQPSK"
};
// RML24 source 24-class order (== cat::target_24); the raw 24-dim NPU order.
const std::vector<std::string> CLASSES_24 = {
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK"
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

// 1px hollow circle (midpoint/Bresenham), the NO SIGNAL badge shape: "empty" =
// listening but nothing above threshold (distinct from the filled LIVE circle).
void outline_circle(Canvas& c, int cx, int cy, int r, std::uint16_t color) {
    int x = r, y = 0, err = 0;
    while (x >= y) {
        set_px(c, cx + x, cy + y, color); set_px(c, cx + y, cy + x, color);
        set_px(c, cx - y, cy + x, color); set_px(c, cx - x, cy + y, color);
        set_px(c, cx - x, cy - y, color); set_px(c, cx - y, cy - x, color);
        set_px(c, cx + y, cy - x, color); set_px(c, cx + x, cy - y, color);
        if (err <= 0) { y += 1; err += 2 * y + 1; }
        if (err > 0)  { x -= 1; err -= 2 * x + 1; }
    }
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
        case Status::Live:          return th.success;
        case Status::Stale:         return th.warning;
        case Status::Error:         return th.error;
        case Status::NoSignal:      return th.disabled;   // neutral: listening, nothing above threshold
        case Status::Waiting:       return th.disabled;   // neutral: not a confirmed state yet
        case Status::Acquiring:     return th.warning;    // transitional: acquiring lock
        case Status::SignalPresent: return th.disabled;   // neutral: present but not yet classified
        case Status::Stopped:       return th.disabled;   // neutral: stopped, still alive
        default:                    return th.interactive;   // Mock
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
        case Status::Live:          fill_circle(c, cx, yc, 8, col); break;
        case Status::Stale:         fill_diamond(c, cx, yc, 8, col); break;
        case Status::Error:         fill_triangle(c, cx, yc, 9, col); break;
        case Status::NoSignal:      outline_circle(c, cx, yc, 8, col); break;   // hollow circle
        case Status::Waiting:       outline_circle(c, cx, yc, 8, col); break;   // hollow: connecting
        case Status::Acquiring:     outline_circle(c, cx, yc, 8, col); break;   // hollow: acquiring
        case Status::SignalPresent: outline_circle(c, cx, yc, 8, col); break;   // hollow: present, unclassified
        case Status::Stopped:       outline_circle(c, cx, yc, 8, col); break;   // hollow: stopped
        default:                    fill_square(c, cx, yc, 8, col, true); break;   // Mock: hollow square
    }
    draw_text_right(c, status_label(st), x_right, yc + 7, col, fb(font_tier::kValue));
}

// ---- top status bar (M19 unified skeleton -> M29 Task B de-boxed) -----------
// Two rows: model-identity caption + page title on the left; MODE / CTRL as
// "label above value" and RUN as dot + text on fixed left anchors; model short
// SHA + signal status badge right-aligned.  No vertical dividers, no decoration
// lines.  Every anchor x is constant, so a value whose length changes never
// shifts another element (no layout jump).
void draw_top_bar(Canvas& c, const Theme& th, const char* title, const UiState& st) {
    fill_rect(c, 0, layout::kTopBarY0, c.w - 1, layout::kTopBarY1, th.surface);

    // RML23 model identity caption (top-left, above the title); only when set so
    // the 12-class pages keep their layout.
    if (!st.model_mode.empty()) {
        draw_text(c, st.model_mode, layout::kTopBarTitleX, 20, th.text_secondary,
                  fr(font_tier::kLabel));
    }
    draw_text(c, title, layout::kTopBarTitleX, 50, th.text_primary, fb(font_tier::kTitle));

    // MODE (label above value)
    draw_text(c, "MODE", layout::kTopBarModeLabelX, 22, th.text_secondary,
              fr(font_tier::kLabel));
    draw_text(c, st.work_mode, layout::kTopBarModeValueX, 50, th.interactive,
              fb(font_tier::kValue));

    // RUN state (dot + text; never color alone)
    const std::uint16_t run_col = st.running ? th.success : th.warning;
    fill_circle(c, layout::kTopBarRunX - 8, 50, 5, run_col);
    draw_text(c, st.running ? "RUNNING" : "STOPPED", layout::kTopBarRunX, 50, run_col,
              fb(font_tier::kValue));

    // CTRL (label above value)
    const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
    draw_text(c, "CTRL", layout::kTopBarCtlLabelX, 22, th.text_secondary,
              fr(font_tier::kLabel));
    draw_text(c, ctl_ok ? "CONNECTED" : "DISCONNECTED", layout::kTopBarCtlValueX, 50,
              ctl_ok ? th.success : th.warning, fb(font_tier::kValue));

    // signal status badge (only right-aligned element; model SHA lives in the
    // info strip so the top bar never crowds the worst-case CTRL value)
    draw_status_badge(c, th, st.status, layout::kTopBarBadgeRightX, 50);
}

// ---- info strip (signal / RX setting / frame / source / model) ------------
// A quiet third-tier band: surface_alt fill, no outline, values demoted to
// 20 px Bold so they no longer compete with the main result.  The model short
// SHA (provenance, third tier) lives here rather than in the top bar, so the
// top bar never crowds the worst-case CTRL value against the status badge.
void draw_info_strip(Canvas& c, const Theme& th, const UiState& st) {
    const int y0 = layout::kInfoY0, y1 = layout::kInfoY1;
    fill_rect(c, 24, y0, 1255, y1, th.surface_alt);
    const std::string model_v = st.model.empty() ? std::string("--") : st.model;
    const std::string signal_v = st.presence.empty() ? std::string("--") : st.presence;
    char gain_buf[32];
    std::snprintf(gain_buf, sizeof gain_buf, "%.1f dB", st.rf_gain_db);
    const std::string gain_v(gain_buf);
    const struct { const char* k; const std::string* v; } items[5] = {
        {"SIGNAL", &signal_v}, {"RX GAIN", &gain_v}, {"FRAME", &st.frame},
        {"SOURCE", &st.source}, {"MODEL", &model_v},
    };
    const int seg = 1232 / 5;
    int x = 44;
    for (const auto& it : items) {
        draw_text(c, it.k, x, y0 + 26, th.text_secondary, fr(font_tier::kLabel));
        draw_text(c, *it.v, x, y0 + 54, th.text_primary, fb(font_tier::kValue));
        x += seg;
    }
}

// ---- RML23 23-class category table (M29 Phase F5 -> Task B de-boxed) --------
// Paginated, LABEL-order table of ALL deployed classes so the full 23-label set
// (with the merged "AM-SSB" slot and NO fake AM-SSB-WC/SC) is always reachable
// within the frozen content area.  Rows sit directly on the page background (no
// per-row box); the argmax row is highlighted with a surface_alt fill + 4 px
// selected accent bar + selected name ink (a clear, quiet echo of the hero).
void draw_category_table(Canvas& c, const Theme& th, const UiState& st,
                         const std::vector<std::string>& classes) {
    const int n = static_cast<int>(classes.size());
    const int page_max = (n + layout::kCategoryRowsPerPage - 1) / layout::kCategoryRowsPerPage;
    int page = st.category_page;
    if (page < 0) page = 0;
    if (page_max > 0 && page >= page_max) page = page_max - 1;

    draw_text(c, "CATEGORIES", layout::kContentInsetX, layout::kCategoryHeaderY,
              th.text_secondary, fb(font_tier::kValue));

    const std::vector<float>& dist = st.dist;
    const bool have_dist = (static_cast<int>(dist.size()) == n);
    int argmax = -1;
    if (have_dist && n > 0) {
        argmax = 0;
        for (int i = 1; i < n; ++i)
            if (dist[static_cast<std::size_t>(i)] > dist[static_cast<std::size_t>(argmax)])
                argmax = i;
    }

    const int start = page * layout::kCategoryRowsPerPage;
    const int end = (start + layout::kCategoryRowsPerPage < n) ? start + layout::kCategoryRowsPerPage : n;
    const font_t* m20 = fm(font_tier::kValue);
    const font_t* b20 = fb(font_tier::kValue);

    for (int i = start; i < end; ++i) {
        const int cy = layout::kCategoryRowsY0 + (i - start) * layout::kCategoryRowPitch;
        const bool is_top = (i == argmax);
        if (is_top) {
            fill_rect(c, 24, cy, 1255, cy + layout::kCategoryRowH, th.surface_alt);
            fill_rect(c, 24, cy, 27, cy + layout::kCategoryRowH, th.selected);
        }

        char idx[16];
        std::snprintf(idx, sizeof idx, "%2d", i + 1);
        draw_text(c, idx, layout::kContentInsetX, cy + 20,
                  is_top ? th.selected : th.text_secondary, m20);
        draw_text(c, classes[static_cast<std::size_t>(i)], layout::kCategoryNameX, cy + 20,
                  is_top ? th.selected : th.text_primary, b20);

        if (have_dist) {
            float p = dist[static_cast<std::size_t>(i)];
            if (p < 0.0f) p = 0.0f;
            if (p > 1.0f) p = 1.0f;
            const int bx0 = layout::kCategoryBarX0, bx1 = layout::kCategoryBarX1;
            const int by0 = cy + 8, by1 = cy + 20;
            fill_rect(c, bx0, by0, bx1, by1, th.accent_bar_bg);
            const int bw = static_cast<int>((bx1 - bx0) * p);
            fill_rect(c, bx0, by0, bx0 + bw, by1,
                      is_top ? th.selected : th.text_secondary);
            char pp[16];
            std::snprintf(pp, sizeof pp, "%4.1f%%", p * 100.0f);
            draw_text_right(c, pp, layout::kContentRightX, cy + 20,
                            is_top ? th.text_primary : th.text_secondary, m20);
        } else {
            draw_text_right(c, "--", layout::kContentRightX, cy + 20, th.text_secondary, m20);
        }
    }

    char footer[48];
    std::snprintf(footer, sizeof footer, "PAGE %d/%d", page + 1, page_max);
    draw_text(c, footer, layout::kContentInsetX, layout::kCategoryFooterY,
              th.text_secondary, fr(font_tier::kLabel));
}

// ---- bottom touch nav (90px raw -> 75px physical; hit >= 60px physical) ----
void draw_nav(Canvas& c, const Theme& th, int active) {
    const int y0 = layout::kNavY0, y1 = layout::kNavY1;
    fill_rect(c, 0, y0, c.w - 1, y1, th.surface);
    outline_rect(c, 0, y0, c.w - 1, y0, th.outline, 1);   // top edge only
    const char* tabs[5] = {"CLASSIFY", "MEASURE", "WATERFALL", "CONSTELLATION", "TUNING"};
    const int tw = c.w / 5;
    const font_t* b = fb(font_tier::kButton);
    for (int i = 0; i < 5; ++i) {
        const int x0 = i * tw;
        const bool on = (i == active);
        if (on) fill_rect(c, x0 + 10, y0 + 8, x0 + tw - 10, y1 - 8, th.surface_alt);
        const int shape_cx = x0 + 34, shape_cy = y0 + 45;
        const std::uint16_t scol = on ? th.selected : th.text_secondary;
        if (i == 0)      fill_square(c, shape_cx, shape_cy, 9, scol, false);
        else if (i == 1) fill_circle(c, shape_cx, shape_cy, 9, scol);
        else if (i == 2) fill_diamond(c, shape_cx, shape_cy, 9, scol);
        else if (i == 3) fill_circle(c, shape_cx, shape_cy, 9, scol);
        else             outline_rect(c, shape_cx - 9, shape_cy - 9,
                                      shape_cx + 9, shape_cy + 9, scol, 2);
        draw_text(c, tabs[i], x0 + 46, y0 + 60, on ? th.selected : th.text_primary, b);
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
        case Status::Live:          return "LIVE";
        case Status::Stale:         return "STALE";
        case Status::Error:         return "ERROR";
        case Status::NoSignal:      return "NO SIGNAL";
        case Status::Waiting:       return "WAITING";
        case Status::Acquiring:     return "ACQUIRING";
        case Status::SignalPresent: return "SIGNAL PRESENT";
        case Status::Stopped:       return "STOPPED";
        default:                    return "MOCK";
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
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    fill_rect(c, 24, 40, 1255, 160, th.surface);
    draw_text(c, "SIGNAL STATUS (text + shape + color)", 44, 96, th.text_secondary,
              fb(font_tier::kButton));
    const Status seq[5] = {Status::Live, Status::Stale, Status::NoSignal,
                           Status::Error, Status::Mock};
    const int xs[5] = {180, 420, 680, 920, 1160};
    for (int i = 0; i < 5; ++i)
        draw_status_badge(c, th, seq[i], xs[i] + 40, 140);
}

const std::vector<std::string>& classes_10() { return CLASSES_10; }
const std::vector<std::string>& classes_12() { return CLASSES_12; }
const std::vector<std::string>& classes_23() { return CLASSES_23; }
const std::vector<std::string>& classes_24() { return CLASSES_24; }

void render_main(Canvas& c, const Theme& th, const UiState& st) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const std::vector<std::string>& classes = st.classes ? *st.classes : CLASSES_10;
    const font_t* b20 = fb(font_tier::kValue);
    const font_t* b40 = fb(font_tier::kMain);
    const font_t* b28 = fb(font_tier::kTitle);
    const font_t* r20 = fr(font_tier::kLabel);
    const font_t* m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "SDR AMR", st);

    // hero card (the single outlined card per page)
    fill_rect(c, 24, layout::kHeroY0, 1255, layout::kHeroY1, th.surface);
    outline_rect(c, 24, layout::kHeroY0, 1255, layout::kHeroY1, th.outline, 1);

    if (st.status == Status::Error) {
        draw_text(c, "RECOGNIZED SIGNAL", layout::kContentInsetX, layout::kHeroLabelY,
                  th.text_secondary, b20);
        draw_text(c, "STREAM ERROR", layout::kContentInsetX, layout::kHeroValueY, th.error, b40);
        draw_text(c, "RX stream anomaly", layout::kContentInsetX, layout::kHeroConfBarY1,
                  th.text_secondary, r20);
        draw_info_strip(c, th, st);
        draw_nav(c, th, 0);
        return;
    }
    if (st.status == Status::NoSignal) {
        draw_text(c, "RECOGNIZED SIGNAL", layout::kContentInsetX, layout::kHeroLabelY,
                  th.text_secondary, b20);
        draw_text(c, "NO SIGNAL", layout::kContentInsetX, layout::kHeroValueY,
                  th.disabled, b40);
        draw_text(c, "Listening: below presence threshold", layout::kContentInsetX,
                  layout::kHeroConfBarY1, th.text_secondary, r20);
        draw_info_strip(c, th, st);
        draw_nav(c, th, 0);
        return;
    }

    const float conf = st.conf;
    const std::string& top1 = st.top1;
    const float conf_pct = conf * 100.0f;

    draw_text(c, "RECOGNIZED SIGNAL", layout::kContentInsetX, layout::kHeroLabelY,
              th.text_secondary, b20);
    draw_text(c, "CONFIDENCE", layout::kHeroConfBarX0, layout::kHeroLabelY,
              th.text_secondary, b20);

    std::uint16_t name_col;
    if (st.status == Status::Stale)       name_col = th.text_secondary;
    else if (st.status == Status::Mock)   name_col = th.interactive;
    else                                  name_col = th.text_primary;
    draw_text(c, top1, layout::kContentInsetX, layout::kHeroValueY, name_col, b40);

    std::uint16_t conf_col;
    if (st.status == Status::Stale)       conf_col = th.text_secondary;
    else if (st.status == Status::Mock)   conf_col = th.interactive;
    else                                  conf_col = (conf < 0.6f) ? th.warning : th.success;

    char pct[32];
    std::snprintf(pct, sizeof pct, "%.1f%%", conf_pct);
    draw_text_right(c, pct, layout::kContentRightX, layout::kHeroValueY, conf_col, b28);

    // confidence bar (right column, directly under the value)
    const int bar_x0 = layout::kHeroConfBarX0, bar_x1 = layout::kContentRightX;
    const int bar_y0 = layout::kHeroConfBarY0, bar_y1 = layout::kHeroConfBarY1;
    fill_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, th.accent_bar_bg);
    if (st.status != Status::Stale) {
        const float wf = conf < 0.0f ? 0.0f : (conf > 1.0f ? 1.0f : conf);
        const int w = static_cast<int>((bar_x1 - bar_x0) * wf);
        fill_rect(c, bar_x0, bar_y0 + 2, bar_x0 + w - 1, bar_y1 - 2, conf_col);
    }

    // STALE subtitle (left column, below top1; never covers the confidence bar)
    if (st.status == Status::Stale && !st.age.empty()) {
        const std::string line = "last result - " + st.age;
        draw_text(c, line, layout::kContentInsetX, layout::kHeroConfBarY1,
                  th.text_secondary, r20);
    }

    // Historical builds paginated all 23/24 classes.  The final five-page
    // instrument deliberately shows only Top-3: it is faster to read on the
    // seven-inch panel and leaves the complete distribution in the evidence log.
    if (false && st.class_count >= 23) {
        draw_category_table(c, th, st, classes);
    } else {
        draw_text(c, "TOP CLASSES", layout::kContentInsetX, layout::kCategoryHeaderY,
                  th.text_secondary, b20);

        const std::vector<float>& dist = st.dist;
        const int n = static_cast<int>(classes.size());
        if (n > 0 && dist.size() == static_cast<std::size_t>(n)) {
            std::vector<int> order(static_cast<std::size_t>(n));
            for (int i = 0; i < n; ++i) order[static_cast<std::size_t>(i)] = i;
            std::sort(order.begin(), order.end(), [&](int a, int b) {
                return dist[static_cast<std::size_t>(a)] > dist[static_cast<std::size_t>(b)];
            });
            const int rows_y = layout::kCategoryRowsY0, row_h = 56, row_pitch = 72;
            const int max_r = n < 3 ? n : 3;
            for (int r = 0; r < max_r; ++r) {
                const int idx = order[static_cast<std::size_t>(r)];
                const bool is_top = (r == 0);
                float p = dist[static_cast<std::size_t>(idx)];
                if (p < 0.0f) p = 0.0f;
                if (p > 1.0f) p = 1.0f;
                const int cy = rows_y + r * row_pitch;
                if (is_top) fill_rect(c, 24, cy, 1255, cy + row_h, th.surface_alt);
                char rank[16];
                std::snprintf(rank, sizeof rank, "%2d", r + 1);
                draw_text(c, rank, layout::kContentInsetX, cy + 37,
                          is_top ? th.selected : th.text_secondary, m20);
                draw_text(c, classes[static_cast<std::size_t>(idx)], layout::kCategoryNameX,
                          cy + 37, is_top ? th.selected : th.text_primary, b20);
                const int bx0 = layout::kCategoryBarX0, bx1 = layout::kCategoryBarX1;
                const int by0 = cy + 16, by1 = cy + 40;
                fill_rect(c, bx0, by0, bx1, by1, th.accent_bar_bg);
                const int bw = static_cast<int>((bx1 - bx0) * p);
                fill_rect(c, bx0, by0, bx0 + bw, by1, is_top ? th.selected : th.text_secondary);
                char pp[16];
                std::snprintf(pp, sizeof pp, "%4.1f%%", p * 100.0f);
                draw_text_right(c, pp, layout::kContentRightX, cy + 37,
                                is_top ? th.text_primary : th.text_secondary, m20);
            }
        } else {
            draw_text(c, "no probability data", layout::kContentInsetX, 340,
                      th.text_secondary, r20);
        }
    }

    draw_info_strip(c, th, st);
    draw_nav(c, th, 0);
}

void render_diag(Canvas& c, const Theme& th, const UiState& st) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const font_t* b20 = fb(font_tier::kValue), * b40 = fb(font_tier::kMain);
    const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "DIAGNOSTICS", st);

    if (st.status == Status::Error) {
        fill_rect(c, 25, 90, 1255, 594, th.surface);
        draw_text(c, "NO DATA", 45, 250, th.error, b40);
        draw_text(c, "diagnostics unavailable - signal pipeline reports no valid frames",
                  45, 310, th.text_secondary, r20);
        draw_nav(c, th, 1);
        return;
    }

    fill_rect(c, 25, 90, 620, 594, th.surface);
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
            draw_text(c, r.k, 57, ry, th.text_primary, b20);
            draw_text_right(c, r.v, 588, ry, th.text_primary, m20);
        } else {
            draw_text(c, r.k, 57, ry, th.text_secondary, r20);
            draw_text_right(c, r.v, 588, ry, th.text_primary, m20);
        }
        ry += 80;
    }

    fill_rect(c, 655, 90, 1255, 594, th.surface);
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
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const font_t* b20 = fb(font_tier::kValue);
    const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "TOUCH TEST", st);

    fill_rect(c, 25, 90, 820, 594, th.surface);
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
    draw_text(c, "HIT REGIONS", 870, 132, th.text_secondary, b20);

    const char* tabs[3] = {"MAIN", "DIAG", "TOUCH"};
    int tx = 870;
    for (int i = 0; i < 3; ++i) {
        fill_rect(c, tx, 160, tx + 112, 220, th.surface_alt);
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

// ---- MEASURE page -----------------------------------------------------------
// A restrained instrument dashboard: three primary metrics followed by two
// clearly scoped detail groups.  Recovered-IQ values are labelled MODEL DOMAIN;
// spectral estimates are labelled EST.  We intentionally do not present the
// recovered tensor as raw ADC dBFS and do not synthesize an SNR value.
namespace {

struct ParamRow { const char* label; std::string value; const char* unit; };

void draw_metric_tile(Canvas& c, const Theme& th, int x0, int y0, int x1, int y1,
                      const char* label, const std::string& value,
                      const char* unit, const char* scope, std::uint16_t accent) {
    fill_rect(c, x0, y0, x1, y1, th.surface);
    fill_rect(c, x0, y0, x0 + 5, y1, accent);
    draw_text(c, label, x0 + 22, y0 + 30, th.text_secondary, fr(font_tier::kLabel));
    draw_text(c, value, x0 + 22, y0 + 79, th.text_primary, fb(font_tier::kTitle));
    if (unit && *unit) draw_text(c, unit, x0 + 150, y0 + 76, th.text_secondary,
                                fr(font_tier::kValue));
    draw_text_right(c, scope, x1 - 18, y1 - 16, accent, fb(font_tier::kLabel));
}

void draw_measure_card(Canvas& c, const Theme& th, int x0, int y0, int x1, int y1,
                       const char* title, const char* badge,
                       const ParamRow* rows, int count) {
    fill_rect(c, x0, y0, x1, y1, th.surface);
    draw_text(c, title, x0 + 20, y0 + 35, th.text_primary, fb(font_tier::kValue));
    draw_text_right(c, badge, x1 - 20, y0 + 35, th.interactive, fb(font_tier::kLabel));
    int ry = y0 + 76;
    for (int i = 0; i < count; ++i) {
        draw_text(c, rows[i].label, x0 + 20, ry, th.text_secondary, fr(font_tier::kLabel));
        std::string shown = rows[i].value;
        if (rows[i].unit && *rows[i].unit && shown != "--") shown += " " + std::string(rows[i].unit);
        draw_text_right(c, shown, x1 - 20, ry, th.text_primary, fm(font_tier::kValue));
        ry += 40;
    }
}

}  // namespace

void render_parameters(Canvas& c, const Theme& th, const UiState& st,
                       const WaterfallHistory* history) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);

    // fix10class24-waterfall1: the PARAMETERS page becomes the spectrum +
    // waterfall view when a history is supplied (the live producer wires one in);
    // a null history keeps the legacy four-card layout for the existing 3-arg
    // host tests unchanged.
    if (history != nullptr) {
        draw_top_bar(c, th, "SPECTRUM", st);
        render_spectrum_waterfall(c, th, st, *history);
        draw_info_strip(c, th, st);
        draw_nav(c, th, 1);
        return;
    }

    const MeasureView& m = st.meas;
    const bool has = m.valid;

    draw_top_bar(c, th, "MEASUREMENTS", st);

    // helper: a measurement value + unit, "--"/"" when absent.
    auto mrow = [&](const char* label, const char* fmt, double v, const char* unit) {
        ParamRow r{label, has ? fnum(fmt, v) : std::string("--"),
                   has ? unit : ""};
        return r;
    };

    const std::string confidence = fnum("%.1f", st.conf * 100.0f);
    draw_metric_tile(c, th, 24, 84, 420, 210, "MODEL CONFIDENCE", confidence,
                     "%", "MODEL OUTPUT", th.selected);
    draw_metric_tile(c, th, 442, 84, 838, 210, "RECOVERED RMS",
                     has ? fnum("%.3f", m.model_rms) : std::string("--"),
                     "", "MODEL DOMAIN", th.interactive);
    draw_metric_tile(c, th, 860, 84, 1255, 210, "PAPR",
                     has ? fnum("%.2f", m.papr_db) : std::string("--"),
                     "dB", "RECOVERED IQ", th.success);

    ParamRow spectrum_rows[6] = {
        mrow("Recovered peak",       "%.3f", m.peak_counts,              "model"),
        mrow("Spectrum median",      "%.1f", m.noise_floor_dbfs,         "dB rel"),
        mrow("Peak prominence",      "%.1f", m.psd_peak_prominence_db,   "dB"),
        mrow("Active bins (-20 dB)", "%.0f", static_cast<double>(m.occupied_bins), "bins"),
        mrow("Occupied bandwidth",   "%.1f", m.occupied_bw_hz / 1000.0,  "kHz"),
        mrow("Centroid offset",      "%+.1f", m.spectral_centroid_hz / 1000.0, "kHz"),
    };
    draw_measure_card(c, th, 24, 228, 632, 548, "SPECTRUM ESTIMATES", "EST",
                      spectrum_rows, 6);

    const bool spectrum_meta = has && m.spectrum_sample_rate_hz > 0.0 &&
                               m.spectrum_center_hz > 0.0;
    ParamRow receiver_rows[6] = {
        {"Signal center", spectrum_meta ? fnum("%.6f", m.spectrum_center_hz / 1.0e6) : "--",
                          spectrum_meta ? "MHz" : ""},
        {"Sample rate", spectrum_meta ? fnum("%.3f", m.spectrum_sample_rate_hz / 1.0e6) : "--",
                        spectrum_meta ? "MS/s" : ""},
        {"RX gain setting", fnum("%.1f", st.rf_gain_db), "dB"},
        {"Presence", st.presence, ""},
        {"Receiver mode", st.work_mode, ""},
        {"Measurement source", "RECOVERED IQ", ""},
    };
    draw_measure_card(c, th, 648, 228, 1255, 548, "RECEIVER", "LIVE",
                      receiver_rows, 6);

    draw_info_strip(c, th, st);
    draw_nav(c, th, 1);
}

void render_waterfall(Canvas& c, const Theme& th, const UiState& st,
                      const WaterfallHistory& history) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    draw_top_bar(c, th, "WATERFALL", st);
    render_spectrum_waterfall(c, th, st, history);
    draw_info_strip(c, th, st);
    draw_nav(c, th, 2);
}

// ---- MODE page (UI v3 M5 -> M16 touch control, M19 status/disabled) --------
// Two mode buttons (name + description + per-button status SELECTED/PENDING/
// IDLE) + START / STOP (disabled when the requested action is already in effect)
// + a detail card (current/requested mode, run state, control channel, last
// command, command status, feedback).  Buttons sit ABOVE the nav band (y < 630),
// so the two tap areas never overlap.  The detail card is de-boxed (surface fill,
// no outline).
void render_mode(Canvas& c, const Theme& th, const UiState& st) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const font_t* b20 = fb(font_tier::kValue), * b28 = fb(font_tier::kTitle);
    const font_t* r20 = fr(font_tier::kLabel);

    draw_top_bar(c, th, "TUNING", st);

    const int active = (st.work_mode == "BAND SCAN") ? 1 : 0;
    const char* names[2] = {"FIXED", "BAND SCAN"};
    const char* desc[2] = {"single frequency", "scan, lock and reacquire"};
    const bool pending = (st.command_status == "PENDING");
    for (int i = 0; i < 2; ++i) {
        int x0, y0, x1, y1;
        mode_ui::button_rect(i, x0, y0, x1, y1);
        const bool on = (i == active);
        const bool pressed = (st.pressed_button == i);   // M18-SW1 press-highlight
        fill_rect(c, x0, y0, x1, y1, (on || pressed) ? th.surface : th.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? th.interactive : (on ? th.selected : th.outline),
                     pressed ? 3 : (on ? 2 : 1));
        draw_text(c, names[i], x0 + 20, y0 + 31, on ? th.selected : th.text_primary, b28);
        draw_text(c, desc[i], x0 + 220, y0 + 31, th.text_secondary, r20);
        // per-button status tag (right-aligned; SELECTED / PENDING / IDLE)
        const char* tag;
        std::uint16_t tag_col;
        if (on)                                  { tag = "SELECTED"; tag_col = th.selected; }
        else if (pending && st.requested_mode == names[i]) { tag = "PENDING"; tag_col = th.warning; }
        else                                     { tag = "IDLE"; tag_col = th.disabled; }
        draw_text_right(c, tag, x1 - 16, y0 + 31, tag_col, b20);
    }

    // Four explicit, touch-editable parameters. AUTO LOCK is intentionally not
    // a user mode; its useful behaviour is exposed as the scan lock-state below.
    const char* flabel[4] = {"FIXED MHz", "SCAN START", "SCAN STOP", "STEP MHz"};
    const std::uint64_t fvalue[4] = {st.fixed_hz,st.scan_start_hz,st.scan_stop_hz,st.scan_step_hz};
    for(int i=0;i<4;++i){
        int x0,y0,x1,y1;mode_ui::frequency_rect(i,x0,y0,x1,y1);
        fill_rect(c,x0,y0,x1,y1,th.surface_alt);outline_rect(c,x0,y0,x1,y1,th.interactive,1);
        draw_text(c,flabel[i],x0+12,y0+23,th.text_secondary,r20);
        draw_text_right(c,fnum("%.6f",fvalue[i]/1.0e6),x1-12,y0+55,th.text_primary,b20);
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

    // Applied state and scan-internal lock state. AUTO lock is represented here,
    // not as a misleading third operating mode.
    fill_rect(c, 25, mode_ui::kDetailY0, 1255, mode_ui::kDetailY1, th.surface);

    const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
    const std::uint16_t ctl_col = ctl_ok ? th.success : th.warning;
    const std::uint16_t cmd_col = command_status_color(th, st.command_status);
    const std::uint16_t req_col = (st.requested_mode == st.work_mode)
                                      ? th.text_primary : th.warning;

    draw_text(c, "APPLIED STATE", 45, mode_ui::kDetailY0 + 32,
              th.text_primary, b20);
    draw_text(c, "COMMAND", 665, mode_ui::kDetailY0 + 32,
              th.text_primary, b20);
    auto detail_row = [&](int x0, int x1, int y, const char* label,
                          const std::string& value, std::uint16_t col) {
        draw_text(c, label, x0, y, th.text_secondary, r20);
        draw_text_right(c, value, x1, y, col, b20);
    };
    detail_row(45, 600, mode_ui::kDetailY0 + 78, "current/requested",
               st.work_mode+" / "+st.requested_mode, req_col);
    detail_row(45, 600, mode_ui::kDetailY0 + 126, "scan state",
               st.work_mode=="BAND SCAN"?st.scan_lock_state:"--", th.selected);
    detail_row(45, 600, mode_ui::kDetailY0 + 174, "run/control",
               std::string(st.running?"RUNNING / ":"STOPPED / ")+st.ctl_connected, ctl_col);
    detail_row(665, 1235, mode_ui::kDetailY0 + 78, "last command",
               st.last_command, th.text_primary);
    detail_row(665, 1235, mode_ui::kDetailY0 + 126, "mode / frequency",
               st.command_status+" / "+st.frequency_status, cmd_col);
    detail_row(665, 1235, mode_ui::kDetailY0 + 174, "feedback",
               st.feedback, feedback_color(th, st.feedback));

    if(st.frequency_editor_open){
        // Opaque editor replaces the content visually; no transparency/blur on the
        // embedded software renderer. Every key is >96 raw pixels high.
        fill_rect(c,220,66,1060,540,th.background);
        outline_rect(c,220,66,1060,540,th.interactive,3);
        const char* titles[4]={"FIXED FREQUENCY (MHz)","SCAN START (MHz)","SCAN STOP (MHz)","SCAN STEP (MHz)"};
        const int fi=(st.frequency_edit_field>=0&&st.frequency_edit_field<4)?st.frequency_edit_field:0;
        draw_text(c,titles[fi],250,98,th.text_primary,b20);
        draw_text_right(c,st.frequency_edit_text,1030,98,th.interactive,b28);
        draw_text(c,"MHz  |  CANCEL discards the draft",250,124,th.text_secondary,r20);
        const char* keys[16]={"1","2","3","BACK","4","5","6","CLEAR",
                              "7","8","9","CANCEL",".","0","000","APPLY"};
        for(int i=0;i<16;++i){
            int x0,y0,x1,y1;mode_ui::keypad_rect(i,x0,y0,x1,y1);
            fill_rect(c,x0,y0,x1,y1,th.surface_alt);
            outline_rect(c,x0,y0,x1,y1,i==15?th.success:th.outline,i==15?2:1);
            draw_text_center(c,keys[i],(x0+x1)/2,(y0+y1)/2+8,
                             i==15?th.success:th.text_primary,b20);
        }
    }

    draw_info_strip(c, th, st);
    draw_nav(c, th, 4);
}

// ---- final RML24 constellation page ---------------------------------------
// The 256 points are a display-only decimation of the same recovered tensor
// passed to the classifier. Coordinates are normalized to the fixed int16
// display contract; no label, expected sample, or per-class correction enters
// this renderer.
void render_constellation(Canvas& c, const Theme& th, const UiState& st) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    draw_top_bar(c, th, "CONSTELLATION", st);

    constexpr int x0 = 360, x1 = 920, y0 = 82, y1 = 560;
    constexpr int cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    constexpr int half = 220;
    fill_rect(c, x0, y0, x1, y1, th.surface);
    outline_rect(c, x0, y0, x1, y1, th.outline, 1);
    fill_rect(c, cx, y0 + 12, cx, y1 - 12, th.outline);
    fill_rect(c, x0 + 12, cy, x1 - 12, cy, th.outline);
    draw_text(c, "+Q", cx + 10, y0 + 28, th.text_secondary, fr(font_tier::kLabel));
    draw_text(c, "+I", x1 - 42, cy - 10, th.text_secondary, fr(font_tier::kLabel));

    if (st.iq_display_valid) {
        for (int p = 0; p < 256; ++p) {
            const int iv = st.iq_i16_interleaved[2 * p];
            const int qv = st.iq_i16_interleaved[2 * p + 1];
            const int x = cx + iv * half / 30000;
            const int y = cy - qv * half / 30000;
            fill_rect(c, x - 2, y - 2, x + 2, y + 2, th.interactive);
        }
        char scale[64];
        std::snprintf(scale, sizeof scale, "DISPLAY SCALE %.3g IQ/count",
                      st.iq_units_per_count);
        draw_text(c, scale, 32, 600, th.text_secondary, fm(font_tier::kValue));
        draw_text_right(c, "256 POINTS / RECOVERED IQ", 1248, 600,
                        th.text_secondary, fr(font_tier::kLabel));
    } else {
        draw_text_center(c, "NO RECOVERED IQ DATA", cx, cy + 8,
                         th.text_secondary, fb(font_tier::kTitle));
    }

    draw_nav(c, th, 3);
}

// ---- target list page (C line, multi-target receiver) ----------------------
// The CLASSIFY page when work_mode == "BAND_SCAN".  Left: the paginated target
// list (sorted by centre frequency, visible_page()); right: the SELECTED
// target's Top3 + parameters, all read from list.selected() so the Top3,
// confidence and last_seen always belong to ONE target identity and one data
// time.  Pagination via prev/next buttons.  A vanished / expired / unclassified
// selection flips selected_has_valid_data() to false; this renderer then draws
// NO stale Top3/params (the constellation/measure pages are gated separately in
// the live server).
void render_target_list(Canvas& c, const Theme& th, const UiState& st,
                        const TargetListState& list) {
    if (c.w != layout::kScreenW || c.h != layout::kScreenH) return;
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    draw_top_bar(c, th, "MULTI-TARGET SCAN", st);

    const font_t* b20 = fb(font_tier::kValue);
    const font_t* r20 = fr(font_tier::kLabel);
    const font_t* m20 = fm(font_tier::kValue);

    // Home summary (targets=N) + pagination.
    draw_text(c, "SCAN TARGETS", layout::kContentInsetX, 96, th.text_secondary, b20);
    const std::string summary = list.summary_line() + "  page " +
        std::to_string(list.page_count() == 0 ? 0 : list.page_offset() + 1) + "/" +
        std::to_string(list.page_count());
    draw_text_right(c, summary, target_list_ui::kListX1, 96, th.text_primary, m20);

    // Target list (left column), sorted ascending by centre frequency.
    const std::vector<const TargetRecord*> page = list.visible_page();
    for (std::size_t i = 0; i < page.size(); ++i) {
        const TargetRecord& t = *page[i];
        int x0, y0, x1, y1;
        target_list_ui::row_rect(static_cast<int>(i), x0, y0, x1, y1);
        const bool selected =
            list.selected_target_id() >= 0 &&
            static_cast<std::uint64_t>(list.selected_target_id()) == t.target_id;
        if (selected) {
            fill_rect(c, x0, y0, x1, y1, th.surface_alt);
            fill_rect(c, x0, y0, x0 + 3, y1, th.selected);
        }
        char line[96];
        std::snprintf(line, sizeof line, "%llu  %.6f MHz",
                      static_cast<unsigned long long>(t.target_id),
                      static_cast<double>(t.center_hz) / 1.0e6);
        draw_text(c, line, x0 + 14, y0 + 22, selected ? th.selected : th.text_primary, b20);
        const std::string top1 = t.classified() ? t.top3.front().class_name
                                                : std::string(unclassified_label());
        char sub[64];
        std::snprintf(sub, sizeof sub, "%s  %.1f%%", top1.c_str(),
                      t.classified() ? t.confidence * 100.0 : 0.0);
        draw_text(c, sub, x0 + 14, y0 + 46, th.text_secondary, r20);
        draw_text_right(c, t.status, x1 - 14, y0 + 22, th.text_secondary, m20);
    }

    // Pagination buttons.
    {
        const bool can_prev = (list.page_offset() > 0);
        fill_rect(c, target_list_ui::kPrevX0, target_list_ui::kPrevY0,
                  target_list_ui::kPrevX1, target_list_ui::kPrevY1, th.surface_alt);
        outline_rect(c, target_list_ui::kPrevX0, target_list_ui::kPrevY0,
                     target_list_ui::kPrevX1, target_list_ui::kPrevY1,
                     can_prev ? th.interactive : th.outline, 1);
        draw_text_center(c, "PREV PAGE",
                         (target_list_ui::kPrevX0 + target_list_ui::kPrevX1) / 2,
                         target_list_ui::kPrevY0 + 32,
                         can_prev ? th.text_primary : th.disabled, b20);

        const bool can_next =
            (list.page_count() > 0 && list.page_offset() + 1 < list.page_count());
        fill_rect(c, target_list_ui::kNextX0, target_list_ui::kNextY0,
                  target_list_ui::kNextX1, target_list_ui::kNextY1, th.surface_alt);
        outline_rect(c, target_list_ui::kNextX0, target_list_ui::kNextY0,
                     target_list_ui::kNextX1, target_list_ui::kNextY1,
                     can_next ? th.interactive : th.outline, 1);
        draw_text_center(c, "NEXT PAGE",
                         (target_list_ui::kNextX0 + target_list_ui::kNextX1) / 2,
                         target_list_ui::kNextY0 + 32,
                         can_next ? th.text_primary : th.disabled, b20);
    }

    // Selected target detail (right column): Top3 + params, all from selected().
    fill_rect(c, target_list_ui::kDetailX0, target_list_ui::kDetailY0,
              target_list_ui::kDetailX1, target_list_ui::kDetailY1, th.surface);
    draw_text(c, "SELECTED TARGET", target_list_ui::kDetailX0 + 20,
              target_list_ui::kDetailY0 + 32, th.text_primary, b20);
    const TargetRecord* sel = list.selected();
    if (sel == nullptr || !list.selected_has_valid_data()) {
        draw_text(c, "no selection", target_list_ui::kDetailX0 + 20,
                  target_list_ui::kDetailY0 + 90, th.text_secondary, r20);
        draw_info_strip(c, th, st);
        draw_nav(c, th, 0);
        return;
    }

    char buf[64];
    std::snprintf(buf, sizeof buf, "%.1f%%", sel->confidence * 100.0);
    draw_text(c, sel->top3.empty() ? unclassified_label()
                                   : sel->top3.front().class_name.c_str(),
              target_list_ui::kDetailX0 + 20, target_list_ui::kDetailY0 + 90,
              th.selected, b20);
    draw_text_right(c, buf, target_list_ui::kDetailX1 - 20,
                    target_list_ui::kDetailY0 + 90, th.text_primary, m20);

    std::string top3_line;
    for (std::size_t k = 0; k < sel->top3.size(); ++k) {
        if (k) top3_line += "  ";
        char tb[48];
        std::snprintf(tb, sizeof tb, "%s %.1f%%", sel->top3[k].class_name.c_str(),
                      sel->top3[k].confidence * 100.0);
        top3_line += tb;
    }
    if (top3_line.empty()) top3_line = unclassified_label();
    draw_text(c, top3_line, target_list_ui::kDetailX0 + 20,
              target_list_ui::kDetailY0 + 126, th.text_secondary, r20);

    // Parameters (same target identity + data time as the Top3 above).
    char cbuf[48], bwbuf[48], pbuf[48], lsbuf[48];
    std::snprintf(cbuf, sizeof cbuf, "%.6f MHz",
                  static_cast<double>(sel->center_hz) / 1.0e6);
    std::snprintf(bwbuf, sizeof bwbuf, "%.3f MHz",
                  static_cast<double>(sel->bw_hz) / 1.0e6);
    if (sel->power_valid_present)
        std::snprintf(pbuf, sizeof pbuf, "%+.1f dB", sel->power_valid);
    else
        std::snprintf(pbuf, sizeof pbuf, "--");
    std::snprintf(lsbuf, sizeof lsbuf, "%.1f s", sel->last_seen);
    const char* rows_l[5] = {"center", "bw", "power", "last seen", "backend"};
    const char* rows_v[5] = {cbuf, bwbuf, pbuf, lsbuf, sel->backend.c_str()};
    int ry = target_list_ui::kDetailY0 + 170;
    for (int k = 0; k < 5; ++k) {
        draw_text(c, rows_l[k], target_list_ui::kDetailX0 + 20, ry,
                  th.text_secondary, r20);
        draw_text_right(c, rows_v[k], target_list_ui::kDetailX1 - 20, ry,
                        th.text_primary, m20);
        ry += 40;
    }

    draw_info_strip(c, th, st);
    draw_nav(c, th, 0);
}

} // namespace ui
