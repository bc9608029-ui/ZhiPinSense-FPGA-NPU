// ui_render.cpp — Style A page renderers (Main / Parameters / Mode), RGB565.
//
// M19 (界面视觉整理): a unified skeleton — top status bar (system | mode |
// RUN/STOP | control | signal status) + main content + bottom nav — against one
// semantic theme (ui_theme.hpp) and an 8 px grid (ui_layout.hpp).  No shadows /
// blur / gradients / translucent layers; no runtime glyph scaling; status is
// always text + shape + color.
//
// M22.1 (UI 视觉重构): every text run is now (a) positioned from the font's real
// metrics via text_box()/text_width(), (b) rasterized through draw_text_clipped()
// so nothing can paint outside its card/button, and (c) tagged with a container
// region (region::*) that the host boundary test re-checks.  All card geometry is
// derived from layout::layout_metrics(c.w, c.h) — one adaptive source — and a too
// small screen fail-closes to a centered message instead of overflowing.

#include "ui_render.hpp"

#include <algorithm>
#include <cstdio>

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

// ---- M22.1 draw helpers: tag region + kind, then draw (optionally clipped) --
int dr(Canvas& c, const std::string& s, int x, int y, std::uint16_t col, const font_t* f,
       int region, TextKind kind, const int* clip = nullptr) {
    text_trace_set_region(region);
    text_trace_set_kind(kind);
    if (clip) return draw_text_clipped(c, s, x, y, col, f, clip[0], clip[1], clip[2], clip[3]);
    return draw_text(c, s, x, y, col, f);
}
int drr(Canvas& c, const std::string& s, int x_right, int y, std::uint16_t col, const font_t* f,
        int region, TextKind kind, const int* clip = nullptr) {
    return dr(c, s, x_right - text_width(s, f), y, col, f, region, kind, clip);
}
int drc(Canvas& c, const std::string& s, int xc, int y, std::uint16_t col, const font_t* f,
        int region, TextKind kind, const int* clip = nullptr) {
    return dr(c, s, xc - text_width(s, f) / 2, y, col, f, region, kind, clip);
}

// Shorten `s` to at most `max_px` pixels at font `f`, appending a trailing "..."
// when anything is cut (spec §四.2 long-text strategy: 缩短/省略).  Returns the
// original string unchanged when it already fits, and "" when even "..." cannot.
std::string fit_text(const std::string& s, const font_t* f, int max_px) {
    if (text_width(s, f) <= max_px) return s;
    if (max_px <= 0) return std::string();
    const std::string ell = "...";
    const int ell_w = text_width(ell, f);
    if (ell_w > max_px) return std::string();
    std::string out;
    int w = 0;
    for (char ch : s) {
        const int cw = text_width(std::string(1, ch), f);
        if (w + cw + ell_w > max_px) break;
        w += cw;
        out += ch;
    }
    return out + ell;
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
void draw_top_bar(Canvas& c, const Theme& th, const char* title, const UiState& st) {
    using namespace layout;
    const int R = region::kTopBar;
    fill_rect(c, 0, kTopBarY0, c.w - 1, kTopBarY1, th.surface);
    fill_rect(c, 0, kTopBarDividerY, c.w - 1, kTopBarDividerY, th.outline);
    const int clip[4] = {0, kTopBarY0, c.w - 1, kTopBarY1};

    dr(c, title, kTopBarTitleX, 44, th.text_primary, fb(font_tier::kTitle), R, TextKind::Title, clip);

    // vertical dividers
    fill_rect(c, kTopBarDivider1X, 16, kTopBarDivider1X, 55, th.outline);
    fill_rect(c, kTopBarDivider2X, 16, kTopBarDivider2X, 55, th.outline);
    fill_rect(c, kTopBarDivider3X, 16, kTopBarDivider3X, 55, th.outline);

    // mode
    dr(c, "MODE", kTopBarModeLabelX, 36, th.text_secondary, fr(font_tier::kLabel),
       R, TextKind::Label, clip);
    dr(c, st.work_mode, kTopBarModeValueX, 36, th.interactive, fb(font_tier::kValue),
       R, TextKind::Value, clip);

    // run state (dot + text; never color alone)
    const std::uint16_t run_col = st.running ? th.success : th.warning;
    fill_circle(c, kTopBarRunX - 8, 36, 5, run_col);
    dr(c, st.running ? "RUNNING" : "STOPPED", kTopBarRunX, 36, run_col, fb(font_tier::kValue),
       R, TextKind::Value, clip);

    // control connection
    const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
    dr(c, "CTRL", kTopBarCtlLabelX, 36, th.text_secondary, fr(font_tier::kLabel),
       R, TextKind::Label, clip);
    dr(c, ctl_ok ? "CONNECTED" : "DISCONNECTED", kTopBarCtlValueX, 36,
       ctl_ok ? th.success : th.warning, fb(font_tier::kValue), R, TextKind::Value, clip);

    // model short SHA (provenance; drawn only when set; shortened to the first 8
    // hex chars so an over-long model string can never reach the ctrl value).
    if (!st.model.empty()) {
        const std::string m = st.model.size() > 8 ? st.model.substr(0, 8) : st.model;
        drr(c, m, kTopBarModelRightX, 36, th.text_secondary, fm(font_tier::kValue),
            R, TextKind::Value, clip);
    }
    // signal status badge
    text_trace_set_region(R);
    draw_status_badge(c, th, st.status, kTopBarBadgeRightX, 36);
}

// ---- info strip (SNR / latency / frame / source) --------------------------
// Two lines per field; baselines are separated by the font's real ascent+descent
// so the 20px label and the 28px value can never overlap (M22.1).
void draw_info_strip(Canvas& c, const Theme& th, const UiState& st) {
    using namespace layout;
    const int R = region::kInfoStrip;
    const int y0 = kInfoY0, y1 = kInfoY1;
    fill_rect(c, 25, y0, 1255, y1, th.surface_alt);
    outline_rect(c, 25, y0, 1255, y1, th.outline, 1);
    const struct { const char* k; const std::string* v; } items[4] = {
        {"SNR", &st.snr}, {"LATENCY", &st.lat}, {"FRAME", &st.frame}, {"SOURCE", &st.source},
    };
    const int seg = 1230 / 4;
    int x = 45;
    const font_t* lbl = fr(font_tier::kLabel);
    const font_t* val = fb(font_tier::kTitle);
    for (const auto& it : items) {
        // Each field clips to its own segment (the last field also to the strip's
        // right edge), and a too-long value is shortened so it can never overflow
        // the strip or reach the next field.
        const int avail = std::min(seg - 12, 1255 - x);
        const int clip_f[4] = {x, y0, x + avail, y1};
        dr(c, it.k, x, y0 + 22, th.text_secondary, lbl, R, TextKind::Label, clip_f);
        dr(c, fit_text(*it.v, val, avail), x, y0 + 56, th.text_primary, val,
           R, TextKind::Value, clip_f);
        x += seg;
    }
}

// ---- bottom touch nav (90px raw -> 75px physical; hit >= 60px physical) ----
void draw_nav(Canvas& c, const Theme& th, int active) {
    using namespace layout;
    const int R = region::kNav;
    const int y0 = kNavY0, y1 = kNavY1;
    fill_rect(c, 0, y0, c.w - 1, y1, th.surface);
    outline_rect(c, 0, y0, c.w - 1, y0, th.outline, 1);   // top edge only
    const char* tabs[3] = {"CLASSIFY", "PARAMETERS", "MODE"};
    const int tw = c.w / 3;
    const font_t* b = fb(font_tier::kButton);
    for (int i = 0; i < 3; ++i) {
        const int x0 = i * tw;
        const int x1 = x0 + tw - 1;
        const bool on = (i == active);
        if (on) fill_rect(c, x0 + 10, y0 + 8, x1 - 10, y1 - 8, th.surface_alt);
        const int shape_cx = x0 + 34, shape_cy = y0 + 45;
        const std::uint16_t scol = on ? th.selected : th.text_secondary;
        if (i == 0)      fill_square(c, shape_cx, shape_cy, 9, scol, false);
        else if (i == 1) fill_circle(c, shape_cx, shape_cy, 9, scol);
        else             fill_diamond(c, shape_cx, shape_cy, 9, scol);
        const int clip[4] = {x0 + 54, y0 + 4, x1 - 10, y1 - 4};
        dr(c, tabs[i], x0 + 58, y0 + 60, on ? th.selected : th.text_primary, b,
           R, TextKind::Title, clip);
    }
}

// Format a double through snprintf (shared by the PARAMETERS page).
std::string fnum(const char* fmt, double v) {
    char b[48];
    std::snprintf(b, sizeof b, fmt, v);
    return std::string(b);
}

// ---- PARAMETERS key/value row with measured, aligned, clipped columns ------
// x_label: label left anchor.  x_val: value RIGHT anchor (all values share it, so
// the value column is right-aligned).  x_unit: unit LEFT anchor (all units share
// it, so the unit column is left-aligned).  x_val < x_unit guarantees the value
// column can never reach the unit column.
void draw_kv_row(Canvas& c, const Theme& th, int x_label, int x_val, int x_unit, int y,
                 const char* label, const std::string& value, const char* unit,
                 int region, const int* card_clip) {
    const font_t* r20 = fr(font_tier::kLabel);
    const font_t* m20 = fm(font_tier::kValue);
    const int clip_label[4] = {card_clip[0], card_clip[1], x_val - 12, card_clip[3]};
    const int clip_value[4] = {card_clip[0], card_clip[1], x_val, card_clip[3]};
    const int clip_unit[4]  = {x_unit, card_clip[1], card_clip[2], card_clip[3]};
    dr(c, label, x_label, y, th.text_secondary, r20, region, TextKind::Label, clip_label);
    drr(c, value, x_val, y, th.text_primary, m20, region, TextKind::Value, clip_value);
    if (unit && unit[0])
        dr(c, unit, x_unit, y, th.text_secondary, r20, region, TextKind::Unit, clip_unit);
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

// ---- fail-closed fallback for a too-small screen ---------------------------
void render_unsupported(Canvas& c, const Theme& th) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const font_t* b = fb(font_tier::kTitle);
    const font_t* r = fr(font_tier::kLabel);
    const int clip[4] = {0, 0, c.w - 1, c.h - 1};
    drc(c, "SCREEN TOO SMALL", c.w / 2, c.h / 2 - 14, th.error, b,
        region::kFallback, TextKind::Title, clip);
    drc(c, "min 640x720", c.w / 2, c.h / 2 + 22, th.text_secondary, r,
        region::kFallback, TextKind::Label, clip);
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

bool region_rect(int region, const layout::LayoutMetrics& lm,
                 int& x0, int& y0, int& x1, int& y1) {
    using namespace layout;
    if (!lm.fit) {
        if (region == region::kFallback) { x0 = 0; y0 = 0; x1 = lm.w - 1; y1 = lm.h - 1; return true; }
        return false;
    }
    const int mx = lm.content_x0, MX = lm.content_x1;
    const int cw = lm.col_w, gap = lm.col_gap;
    switch (region) {
    case region::kFallback:      x0 = 0; y0 = 0; x1 = lm.w - 1; y1 = lm.h - 1; return true;
    case region::kTopBar:        x0 = 0; y0 = lm.top_y0; x1 = lm.w - 1; y1 = lm.top_y1; return true;
    case region::kResultCard:    x0 = mx; y0 = lm.content_y0; x1 = MX; y1 = lm.content_y0 + 168; return true;
    case region::kTopClasses:    x0 = mx; y0 = 264; x1 = MX; y1 = lm.content_y1; return true;
    case region::kInfoStrip:     x0 = mx; y0 = lm.info_y0; x1 = MX; y1 = lm.info_y1; return true;
    case region::kNav:           x0 = 0; y0 = lm.nav_y0; x1 = lm.w - 1; y1 = lm.nav_y1; return true;
    case region::kSignalLevel:   x0 = mx; y0 = 84; x1 = mx + cw; y1 = 308; return true;
    case region::kSpectrum:      x0 = mx + cw + gap; y0 = 84; x1 = MX; y1 = 308; return true;
    case region::kSignalQuality: x0 = mx; y0 = 324; x1 = mx + cw; y1 = 548; return true;
    case region::kRfConfig:      x0 = mx + cw + gap; y0 = 324; x1 = MX; y1 = 548; return true;
    case region::kModeBtn0:      mode_ui::button_rect(0, x0, y0, x1, y1); return true;
    case region::kModeBtn1:      mode_ui::button_rect(1, x0, y0, x1, y1); return true;
    case region::kModeBtn2:      mode_ui::button_rect(2, x0, y0, x1, y1); return true;
    case region::kRunStart:      mode_ui::button_rect(3, x0, y0, x1, y1); return true;
    case region::kRunStop:       mode_ui::button_rect(4, x0, y0, x1, y1); return true;
    case region::kDetailCard:    x0 = mx; y0 = mode_ui::kDetailY0; x1 = MX; y1 = mode_ui::kDetailY1; return true;
    case region::kDiagLeft:      x0 = 25; y0 = 90; x1 = 620; y1 = 594; return true;
    case region::kDiagRight:     x0 = 655; y0 = 90; x1 = 1255; y1 = 594; return true;
    case region::kTouchLeft:     x0 = 25; y0 = 90; x1 = 820; y1 = 594; return true;
    case region::kTouchRight:    x0 = 850; y0 = 90; x1 = 1255; y1 = 594; return true;
    default:                     return false;
    }
}

void render_legend(Canvas& c, const Theme& th) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    fill_rect(c, 25, 40, 1255, 160, th.surface);
    outline_rect(c, 25, 40, 1255, 160, th.outline, 1);
    dr(c, "SIGNAL STATUS (text + shape + color)", 45, 96, th.text_secondary,
       fb(font_tier::kButton), region::kResultCard, TextKind::Title);
    const Status seq[4] = {Status::Live, Status::Stale, Status::Error, Status::Mock};
    const int xs[4] = {200, 520, 840, 1160};
    for (int i = 0; i < 4; ++i)
        draw_status_badge(c, th, seq[i], xs[i] + 40, 140);
}

const std::vector<std::string>& classes_10() { return CLASSES_10; }
const std::vector<std::string>& classes_12() { return CLASSES_12; }

void render_main(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
    if (!lm.fit) { render_unsupported(c, th); return; }

    const std::vector<std::string>& classes = st.classes ? *st.classes : CLASSES_10;
    const font_t* b20 = fb(font_tier::kValue);
    const font_t* b40 = fb(font_tier::kMain);
    const font_t* r20 = fr(font_tier::kLabel);
    const font_t* m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "SDR AMR", st);

    int rx0, ry0, rx1, ry1;
    region_rect(region::kResultCard, lm, rx0, ry0, rx1, ry1);

    // result card (top priority)
    fill_rect(c, rx0, ry0, rx1, ry1, th.surface);
    outline_rect(c, rx0, ry0, rx1, ry1, th.outline, 1);
    const int rclip[4] = {rx0, ry0, rx1, ry1};

    if (st.status == Status::Error) {
        dr(c, "RECOGNIZED SIGNAL", rx0 + 20, ry0 + 22, th.text_secondary, b20,
           region::kResultCard, TextKind::Title, rclip);
        dr(c, "NO SIGNAL", rx0 + 20, ry0 + 72, th.error, b40,
           region::kResultCard, TextKind::Value, rclip);
        dr(c, "Waiting for valid input", rx0 + 20, ry0 + 130, th.text_secondary, r20,
           region::kResultCard, TextKind::Label, rclip);
        text_trace_set_region(region::kResultCard);
        draw_status_chip(c, th, "NO SIGNAL", th.error, rx1 - 41, ry0 + 38);
        draw_info_strip(c, th, st);
        draw_nav(c, th, 0);
        return;
    }

    const float conf = st.conf;
    const std::string& top1 = st.top1;
    const float conf_pct = conf * 100.0f;

    dr(c, "RECOGNIZED SIGNAL", rx0 + 20, ry0 + 22, th.text_secondary, b20,
       region::kResultCard, TextKind::Title, rclip);

    const char* chip_label;
    std::uint16_t chip_col;
    if (st.status == Status::Stale)       { chip_label = "STALE DATA";    chip_col = th.warning; }
    else if (st.status == Status::Mock)   { chip_label = "MOCK DATA";     chip_col = th.interactive; }
    else if (conf >= 0.6f)                { chip_label = "CONFIDENT";     chip_col = th.success; }
    else                                  { chip_label = "LOW CONFIDENCE"; chip_col = th.warning; }
    text_trace_set_region(region::kResultCard);
    draw_status_chip(c, th, chip_label, chip_col, rx1 - 41, ry0 + 38);

    std::uint16_t name_col;
    if (st.status == Status::Stale)       name_col = th.text_secondary;
    else if (st.status == Status::Mock)   name_col = th.interactive;
    else                                  name_col = th.text_primary;
    dr(c, top1, rx0 + 20, ry0 + 72, name_col, b40, region::kResultCard, TextKind::Value, rclip);

    std::uint16_t conf_col;
    if (st.status == Status::Stale)       conf_col = th.text_secondary;
    else if (st.status == Status::Mock)   conf_col = th.interactive;
    else                                  conf_col = (conf < 0.6f) ? th.warning : th.success;

    // Confidence row: label + value share a baseline (side by side, measured gap);
    // the 40px value is positioned right of the 20px label, and its baseline is
    // below top1's descent so the two big lines never overlap (M22.1).
    const int conf_base = ry0 + 130;
    dr(c, "CONFIDENCE", rx0 + 20, conf_base, th.text_secondary, r20,
       region::kResultCard, TextKind::Label, rclip);
    char pct[32];
    std::snprintf(pct, sizeof pct, "%.1f%%", conf_pct);
    const int conf_val_x = rx0 + 20 + text_width("CONFIDENCE", r20) + 16;
    dr(c, pct, conf_val_x, conf_base, conf_col, b40, region::kResultCard, TextKind::Value, rclip);

    // confidence bar (right of result card)
    const int bar_x0 = 700, bar_x1 = 1215, bar_y0 = ry0 + 104, bar_y1 = ry0 + 128;
    fill_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, th.accent_bar_bg);
    outline_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, th.outline, 1);
    if (st.status != Status::Stale) {
        const float wf = conf < 0.0f ? 0.0f : (conf > 1.0f ? 1.0f : conf);
        const int w = static_cast<int>((bar_x1 - bar_x0) * wf);
        fill_rect(c, bar_x0, bar_y0 + 2, bar_x0 + w - 1, bar_y1 - 2, conf_col);
    }

    // Top-3 class probabilities (second priority; M19: at most the top three).
    int tx0, ty0, tx1, ty1;
    region_rect(region::kTopClasses, lm, tx0, ty0, tx1, ty1);
    const int tclip[4] = {tx0, ty0, tx1, ty1};
    dr(c, "TOP CLASSES", tx0, 288, th.text_secondary, b20, region::kTopClasses,
       TextKind::Title, tclip);

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
            fill_rect(c, tx0, cy, tx1, cy + row_h, th.surface);
            outline_rect(c, tx0, cy, tx1, cy + row_h,
                         is_top ? th.selected : th.outline, is_top ? 2 : 1);
            char rank[16];
            std::snprintf(rank, sizeof rank, "%2d", r + 1);
            dr(c, rank, tx0 + 20, cy + 37, is_top ? th.selected : th.text_secondary, m20,
               region::kTopClasses, TextKind::Label, tclip);
            const int cls_clip[4] = {tx0 + 66, cy + 2, 316, cy + row_h - 2};
            dr(c, classes[static_cast<std::size_t>(idx)], tx0 + 66, cy + 37,
               th.text_primary, b20, region::kTopClasses, TextKind::Value, cls_clip);
            const int bx0 = 320, bx1 = 1100, by0 = cy + 16, by1 = cy + 40;
            fill_rect(c, bx0, by0, bx1, by1, th.accent_bar_bg);
            const int bw = static_cast<int>((bx1 - bx0) * p);
            fill_rect(c, bx0, by0, bx0 + bw, by1, is_top ? th.selected : th.text_secondary);
            char pp[16];
            std::snprintf(pp, sizeof pp, "%4.1f%%", p * 100.0f);
            const int pct_clip[4] = {1104, cy + 2, tx1 - 20, cy + row_h - 2};
            drr(c, pp, tx1 - 20, cy + 37, is_top ? th.text_primary : th.text_secondary,
                m20, region::kTopClasses, TextKind::Value, pct_clip);
        }
    } else {
        dr(c, "no probability data", tx0 + 20, 340, th.text_secondary, r20,
           region::kTopClasses, TextKind::Label, tclip);
    }

    draw_info_strip(c, th, st);
    draw_nav(c, th, 0);
}

void render_diag(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
    if (!lm.fit) { render_unsupported(c, th); return; }
    const font_t* b20 = fb(font_tier::kValue), * b40 = fb(font_tier::kMain);
    const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "DIAGNOSTICS", st);

    if (st.status == Status::Error) {
        fill_rect(c, 25, 90, 1255, 594, th.surface);
        outline_rect(c, 25, 90, 1255, 594, th.outline, 1);
        const int clip[4] = {25, 90, 1255, 594};
        dr(c, "NO DATA", 45, 250, th.error, b40, region::kDiagLeft, TextKind::Value, clip);
        dr(c, "diagnostics unavailable - signal pipeline reports no valid frames",
           45, 310, th.text_secondary, r20, region::kDiagLeft, TextKind::Label, clip);
        draw_nav(c, th, 1);
        return;
    }

    int lx0, ly0, lx1, ly1, x0, y0, x1, y1;
    region_rect(region::kDiagLeft, lm, lx0, ly0, lx1, ly1);
    region_rect(region::kDiagRight, lm, x0, y0, x1, y1);

    fill_rect(c, lx0, ly0, lx1, ly1, th.surface);
    outline_rect(c, lx0, ly0, lx1, ly1, th.outline, 1);
    const int lclip[4] = {lx0, ly0, lx1, ly1};
    dr(c, "LATENCY BREAKDOWN", lx0 + 20, 132, th.text_secondary, b20,
       region::kDiagLeft, TextKind::Title, lclip);

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
            outline_rect(c, lx0 + 20, ry - 16, lx1 - 20, ry + 12, th.outline, 1);
            dr(c, r.k, lx0 + 32, ry, th.text_primary, b20, region::kDiagLeft, TextKind::Value, lclip);
            drr(c, r.v, lx1 - 32, ry, th.text_primary, m20, region::kDiagLeft, TextKind::Value, lclip);
        } else {
            dr(c, r.k, lx0 + 32, ry, th.text_secondary, r20, region::kDiagLeft, TextKind::Label, lclip);
            drr(c, r.v, lx1 - 32, ry, th.text_primary, m20, region::kDiagLeft, TextKind::Value, lclip);
        }
        ry += 80;
    }

    fill_rect(c, x0, y0, x1, y1, th.surface);
    outline_rect(c, x0, y0, x1, y1, th.outline, 1);
    const int rclip[4] = {x0, y0, x1, y1};
    dr(c, "DETAILED COUNTS", x0 + 20, 132, th.text_secondary, b20,
       region::kDiagRight, TextKind::Title, rclip);

    const struct { const char* k; const char* v; } cnt[5] = {
        {"frames rendered", "1024"},
        {"frames dropped", "0"},
        {"buffer resets", "0"},
        {"touch events", "57"},
        {"data source", st.source.c_str()},
    };
    ry = 200;
    for (const auto& r : cnt) {
        dr(c, r.k, x0 + 32, ry, th.text_secondary, r20, region::kDiagRight, TextKind::Label, rclip);
        drr(c, r.v, x1 - 32, ry, th.text_primary, m20, region::kDiagRight, TextKind::Value, rclip);
        ry += 64;
    }

    dr(c, "signal status:", x0 + 20, 540, th.text_secondary, r20, region::kDiagRight, TextKind::Label, rclip);
    text_trace_set_region(region::kDiagRight);
    draw_status_badge(c, th, st.status, x1 - 32, 534);

    draw_nav(c, th, 1);
}

void render_touch(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
    if (!lm.fit) { render_unsupported(c, th); return; }
    const font_t* b20 = fb(font_tier::kValue);
    const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);

    draw_top_bar(c, th, "TOUCH TEST", st);

    int lx0, ly0, lx1, ly1, x0, y0, x1, y1;
    region_rect(region::kTouchLeft, lm, lx0, ly0, lx1, ly1);
    region_rect(region::kTouchRight, lm, x0, y0, x1, y1);

    fill_rect(c, lx0, ly0, lx1, ly1, th.surface);
    outline_rect(c, lx0, ly0, lx1, ly1, th.outline, 1);
    const int lclip[4] = {lx0, ly0, lx1, ly1};
    dr(c, "TOUCH CALIBRATION", lx0 + 20, 132, th.text_secondary, b20,
       region::kTouchLeft, TextKind::Title, lclip);

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
        dr(c, r.k, lx0 + 32, ry, th.text_secondary, r20, region::kTouchLeft, TextKind::Label, lclip);
        dr(c, *r.v, lx0 + 225, ry, th.text_primary, m20, region::kTouchLeft, TextKind::Value, lclip);
        ry += 64;
    }

    fill_rect(c, x0, y0, x1, y1, th.surface);
    outline_rect(c, x0, y0, x1, y1, th.outline, 1);
    const int rclip[4] = {x0, y0, x1, y1};
    dr(c, "HIT REGIONS", x0 + 20, 132, th.text_secondary, b20,
       region::kTouchRight, TextKind::Title, rclip);

    const char* tabs[3] = {"MAIN", "DIAG", "TOUCH"};
    int tx = x0 + 20;
    for (int i = 0; i < 3; ++i) {
        fill_rect(c, tx, 160, tx + 112, 220, th.surface_alt);
        outline_rect(c, tx, 160, tx + 112, 220, i == 2 ? th.selected : th.outline, i == 2 ? 2 : 1);
        drc(c, tabs[i], tx + 56, 198, i == 2 ? th.selected : th.text_primary, b20,
            region::kTouchRight, TextKind::Title, rclip);
        tx += 124;
    }
    dr(c, "hit area >= 60 px physical", x0 + 20, 268, th.text_secondary, r20,
       region::kTouchRight, TextKind::Label, rclip);
    dr(c, "bottom nav height 90 px raw", x0 + 20, 300, th.text_secondary, r20,
       region::kTouchRight, TextKind::Label, rclip);

    const bool tconn = st.touch.connected;
    dr(c, "touch:", x0 + 20, 470, th.text_secondary, r20, region::kTouchRight, TextKind::Label, rclip);
    dr(c, tconn ? "CONNECTED" : "DISCONNECTED", x0 + 100, 470,
       tconn ? th.success : th.warning, b20, region::kTouchRight, TextKind::Value, rclip);
    char tstat[48];
    std::snprintf(tstat, sizeof tstat, "taps %llu",
                  static_cast<unsigned long long>(st.touch.taps));
    dr(c, tstat, x0 + 20, 510, th.text_secondary, r20, region::kTouchRight, TextKind::Label, rclip);
    if (st.touch.last_x >= 0) {
        char pt[48];
        std::snprintf(pt, sizeof pt, "last (%d, %d)", st.touch.last_x, st.touch.last_y);
        dr(c, pt, x0 + 100, 510, th.text_primary, m20, region::kTouchRight, TextKind::Value, rclip);
    }

    draw_nav(c, th, 2);
}

// ---- PARAMETERS page (UI v3 M5 -> M19 four groups) -------------------------
namespace {

struct ParamRow { const char* label; std::string value; const char* unit; };

// Draw one grouped card.  The unit column width is measured from the widest unit
// in the card (never a guess), the value column is right-aligned to a fixed
// anchor left of the unit column, and every run is clipped to the card — so a
// value/unit can never overflow the card or reach the neighbouring column.
void draw_param_card(Canvas& c, const Theme& th, const layout::LayoutMetrics& lm,
                     int region, const char* title, const ParamRow* rows, int count) {
    int x0, y0, x1, y1;
    region_rect(region, lm, x0, y0, x1, y1);
    fill_rect(c, x0, y0, x1, y1, th.surface);
    outline_rect(c, x0, y0, x1, y1, th.outline, 1);

    const font_t* b20 = fb(font_tier::kValue);
    const font_t* r20 = fr(font_tier::kLabel);

    int unit_w = 0;
    for (int i = 0; i < count; ++i)
        if (rows[i].unit[0]) unit_w = std::max(unit_w, text_width(rows[i].unit, r20));
    const int pad = 16;
    const int x_unit = x1 - pad - unit_w;    // unit left anchor
    const int x_val = x_unit - 12;           // value right anchor (12px gap)
    const int x_label = x0 + 20;

    const int card_clip[4] = {x0, y0, x1, y1};
    dr(c, title, x_label, y0 + 28, th.text_secondary, b20, region, TextKind::Title, card_clip);

    const int pitch = b20->line_h + 8;       // metric-driven row pitch (24+8 = 32)
    int ry = y0 + 28 + 32;
    for (int i = 0; i < count; ++i) {
        draw_kv_row(c, th, x_label, x_val, x_unit, ry, rows[i].label,
                    rows[i].value, rows[i].unit, region, card_clip);
        ry += pitch;
    }
}

}  // namespace

void render_parameters(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
    if (!lm.fit) { render_unsupported(c, th); return; }
    const MeasureView& m = st.meas;
    const bool has = m.valid;

    draw_top_bar(c, th, "PARAMETERS", st);

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
        draw_param_card(c, th, lm, region::kSignalLevel, "SIGNAL LEVEL", rows, 5);
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
        draw_param_card(c, th, lm, region::kSpectrum, "SPECTRUM", rows, 5);
    }
    // SIGNAL QUALITY (bottom-left)
    {
        ParamRow rows[3] = {
            mrow("SNR (est)",    "%.1f", m.snr_est_db, "dB"),
            {"Presence", st.presence, ""},
            mrow("Model RMS",    "%.3f", m.model_rms,  ""),
        };
        draw_param_card(c, th, lm, region::kSignalQuality, "SIGNAL QUALITY", rows, 3);
    }
    // RF CONFIGURATION (bottom-right)
    {
        ParamRow rows[4] = {
            {"Level mode",  st.level_mode, ""},
            {"Model scale", fnum("%.3f", st.model_scale), "x"},
            {"RF gain",     fnum("%.1f", st.rf_gain_db),  "dB"},
            {"Source",      st.source, ""},
        };
        draw_param_card(c, th, lm, region::kRfConfig, "RF CONFIGURATION", rows, 4);
    }

    draw_info_strip(c, th, st);
    draw_nav(c, th, 1);
}

// ---- MODE page (UI v3 M5 -> M16 touch control, M19 status/disabled) --------
void render_mode(Canvas& c, const Theme& th, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
    if (!lm.fit) { render_unsupported(c, th); return; }
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
    // Worst-case status tag width (SELECTED/PENDING/IDLE) so the name column can
    // never reach the right-aligned tag (M22.1).
    const int tag_w = std::max({text_width("SELECTED", b20),
                                text_width("PENDING", b20),
                                text_width("IDLE", b20)});
    for (int i = 0; i < 3; ++i) {
        int x0, y0, x1, y1;
        mode_ui::button_rect(i, x0, y0, x1, y1);
        const int btn_region = region::kModeBtn0 + i;
        const bool on = (i == active);
        const bool pressed = (st.pressed_button == i);   // M18-SW1 press-highlight
        fill_rect(c, x0, y0, x1, y1, (on || pressed) ? th.surface : th.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? th.interactive : (on ? th.selected : th.outline),
                     pressed ? 3 : (on ? 2 : 1));
        const int name_clip[4] = {x0 + 20, y0 + 2, x1 - 16 - tag_w - 8, y1 - 2};
        dr(c, names[i], x0 + 20, y0 + 44, on ? th.selected : th.text_primary, b28,
           btn_region, TextKind::Title, name_clip);
        const int desc_clip[4] = {x0 + 20, y0 + 2, x1 - 16, y1 - 2};
        dr(c, desc[i], x0 + 20, y0 + 82, th.text_secondary, r20,
           btn_region, TextKind::Label, desc_clip);
        // per-button status tag (right-aligned; SELECTED / PENDING / IDLE)
        const char* tag;
        std::uint16_t tag_col;
        if (on)                                  { tag = "SELECTED"; tag_col = th.selected; }
        else if (pending && st.requested_mode == names[i]) { tag = "PENDING"; tag_col = th.warning; }
        else                                     { tag = "IDLE"; tag_col = th.disabled; }
        const int tag_clip[4] = {x1 - 16 - tag_w, y0 + 2, x1 - 16, y1 - 2};
        drr(c, tag, x1 - 16, y0 + 44, tag_col, b20, btn_region, TextKind::Value, tag_clip);
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
        const int clip[4] = {x0 + 8, y0 + 8, x1 - 8, y1 - 8};
        drc(c, "START", (x0 + x1) / 2, y0 + 52, enabled ? th.success : th.disabled, b28,
            region::kRunStart, TextKind::Title, clip);
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
        const int clip[4] = {x0 + 8, y0 + 8, x1 - 8, y1 - 8};
        drc(c, "STOP", (x0 + x1) / 2, y0 + 52, enabled ? th.warning : th.disabled, b28,
            region::kRunStop, TextKind::Title, clip);
    }

    // detail card: applied vs requested + control-channel state.
    int dx0, dy0, dx1, dy1;
    region_rect(region::kDetailCard, lm, dx0, dy0, dx1, dy1);
    fill_rect(c, dx0, dy0, dx1, dy1, th.surface);
    outline_rect(c, dx0, dy0, dx1, dy1, th.outline, 1);
    const int dclip[4] = {dx0, dy0, dx1, dy1};

    const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
    const std::uint16_t run_col = st.running ? th.success : th.warning;
    const std::uint16_t ctl_col = ctl_ok ? th.success : th.warning;
    const std::uint16_t cmd_col = command_status_color(th, st.command_status);
    const std::uint16_t req_col = (st.requested_mode == st.work_mode)
                                      ? th.text_primary : th.warning;

    int ry = dy0 + 28;
    auto row = [&](const char* label, const std::string& value, std::uint16_t col) {
        dr(c, label, dx0 + 20, ry, th.text_secondary, r20, region::kDetailCard, TextKind::Label, dclip);
        drr(c, value, 600, ry, col, b20, region::kDetailCard, TextKind::Value, dclip);
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
