// ui_render.cpp — Style A page renderers (Main / Diagnostics / Touch), RGB565.
//
// Faithful port of the approved design draft (Style A, modern scientific
// instrument).  Layout coordinates are copied 1:1 from
// design_mockups/tools/make_mockups.py so the host screenshots and the board
// output are pixel-consistent (up to the unavoidable RGB565 quantization, which
// the board framebuffer is by definition).
//
// No shadows / blur / gradients / translucent layers; no runtime glyph scaling;
// status is always text + shape + color.

#include "ui_render.hpp"

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

// ---- font shorthands -------------------------------------------------------
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
std::uint16_t status_color(const Palette& pal, Status s) {
    switch (s) {
        case Status::Live:  return pal.success;
        case Status::Stale: return pal.warning;
        case Status::Error: return pal.error;
        default:            return pal.dim;   // Mock
    }
}

// ---- status badge: text + shape + color (never color alone) ----------------
// The shape (icon) is drawn >=10px LEFT of the right-aligned status text, so it
// never covers the LIVE/STALE/ERROR/MOCK label.  Geometry comes from
// status_badge_shape_cx() (single source of truth, shared with the host test).
void draw_status_badge(Canvas& c, const Palette& pal, Status st, int x_right, int yc) {
    const std::uint16_t col = status_color(pal, st);
    const int cx = status_badge_shape_cx(st, x_right);
    switch (st) {
        case Status::Live:  fill_circle(c, cx, yc, 8, col); break;
        case Status::Stale: fill_diamond(c, cx, yc, 8, col); break;
        case Status::Error: fill_triangle(c, cx, yc, 9, col); break;
        default:            fill_square(c, cx, yc, 8, col, true); break;   // Mock: hollow square
    }
    draw_text_right(c, status_label(st), x_right, yc + 7, col, fb(20));
}

void draw_status_chip(Canvas& c, const Palette& pal, const char* label,
                      std::uint16_t col, int x_right, int yc) {
    const font_t* b20 = fb(20);
    const int w = text_width(label, b20) + 28;
    const int x0 = x_right - w;
    const int y0 = yc - 22;
    fill_rect(c, x0, y0, x_right, yc + 14, pal.surface_alt);
    outline_rect(c, x0, y0, x_right, yc + 14, col, 1);
    draw_text_center(c, label, (x0 + x_right) / 2, yc, col, b20);
}

// ---- header ---------------------------------------------------------------
void draw_header(Canvas& c, const Palette& pal, const char* title, const UiState& st) {
    draw_text(c, title, 25, 50, pal.text, fb(28));
    draw_status_badge(c, pal, st.status, 1255, 38);
    // Model short SHA (provenance) sits in the empty header gap, left of the
    // status badge.  Drawn only when set, so the v5_visual pixel-consistent
    // screenshots (which leave `model` empty) are unchanged.
    if (!st.model.empty()) {
        draw_text_right(c, "model " + st.model, 1150, 50, pal.dim, fm(20));
    }
    outline_rect(c, 0, 78, c.w - 1, 78, pal.outline, 1);
}

// ---- info strip (SNR / latency / frame / source) --------------------------
void draw_info_strip(Canvas& c, const Palette& pal, const UiState& st) {
    const int y0 = 558, y1 = 624;
    fill_rect(c, 25, y0, 1255, y1, pal.surface_alt);
    outline_rect(c, 25, y0, 1255, y1, pal.outline, 1);
    const struct { const char* k; const std::string* v; } items[4] = {
        {"SNR", &st.snr}, {"LATENCY", &st.lat}, {"FRAME", &st.frame}, {"SOURCE", &st.source},
    };
    const int seg = 1230 / 4;
    int x = 45;
    for (const auto& it : items) {
        draw_text(c, it.k, x, y0 + 26, pal.dim, fr(20));
        draw_text(c, *it.v, x, y0 + 54, pal.text, fb(28));
        x += seg;
    }
}

// ---- bottom touch nav (90px raw -> 75px physical; hit >= 60px physical) ----
void draw_nav(Canvas& c, const Palette& pal, int active) {
    const int y0 = 630, y1 = 719;
    fill_rect(c, 0, y0, c.w - 1, y1, pal.surface);
    outline_rect(c, 0, y0, c.w - 1, y0, pal.outline, 1);   // top edge only
    const char* tabs[3] = {"CLASSIFY", "PARAMETERS", "MODE"};
    const int tw = c.w / 3;
    const font_t* b24 = fb(24);
    for (int i = 0; i < 3; ++i) {
        const int x0 = i * tw;
        const bool on = (i == active);
        if (on) fill_rect(c, x0 + 10, y0 + 8, x0 + tw - 10, y1 - 8, pal.surface_alt);
        const int shape_cx = x0 + 34, shape_cy = y0 + 45;
        const std::uint16_t scol = on ? pal.primary : pal.dim;
        if (i == 0)      fill_square(c, shape_cx, shape_cy, 9, scol, false);
        else if (i == 1) fill_circle(c, shape_cx, shape_cy, 9, scol);
        else             fill_diamond(c, shape_cx, shape_cy, 9, scol);
        draw_text(c, tabs[i], x0 + 58, y0 + 60, on ? pal.primary : pal.text, b24);
    }
}

// Format a double through snprintf (shared by the PARAMETERS / MODE pages).
std::string fnum(const char* fmt, double v) {
    char b[48];
    std::snprintf(b, sizeof b, fmt, v);
    return std::string(b);
}

// Draw one key/value row (label left, value right).  Keeps the PARAMETERS and
// MODE table rows visually identical to the rest of Style A.
void draw_kv_row(Canvas& c, const Palette& pal, int x_label, int x_val, int y,
                 const char* label, const std::string& value) {
    draw_text(c, label, x_label, y, pal.dim, fr(20));
    draw_text_right(c, value, x_val, y, pal.text, fm(20));
}

// Color for the MODE-page "command status" value (M16).
std::uint16_t command_status_color(const Palette& pal, const std::string& s) {
    if (s == "APPLIED") return pal.success;
    if (s == "PENDING") return pal.warning;
    if (s == "REJECTED" || s == "TIMEOUT") return pal.error;
    return pal.dim;   // IDLE / "--"
}

// Color for the MODE-page "feedback" value (M18-SW1 Task A): a transient reason
// why a tap produced no command ("ALREADY IN THIS MODE" etc.).
std::uint16_t feedback_color(const Palette& pal, const std::string& s) {
    if (s.empty() || s == "--") return pal.dim;
    if (s == "CONTROL DISCONNECTED" || s == "SEND FAILED") return pal.error;
    if (s.rfind("ALREADY", 0) == 0 || s == "COMMAND IN PROGRESS") return pal.warning;
    return pal.text;
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
    const int text_w = text_width(status_label(st), fb(20));
    const int r = (st == Status::Error) ? 9 : 8;
    // Shape center sits 10px left of the text, and its half-width r further left,
    // so the shape's right edge is exactly 10px from the text's left edge.
    return x_right - text_w - 10 - r;
}

CardGrid card_grid(int n) {
    const int y0 = 300, y_area_end = 556;   // "CLASS PROBABILITIES" label at 288; info strip at 558
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

void render_legend(Canvas& c, const Palette& pal) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, pal.bg);
    fill_rect(c, 25, 40, 1255, 160, pal.surface);
    outline_rect(c, 25, 40, 1255, 160, pal.outline, 1);
    draw_text(c, "SIGNAL STATUS (text + shape + color)", 45, 96, pal.dim, fb(24));
    const Status seq[4] = {Status::Live, Status::Stale, Status::Error, Status::Mock};
    const int xs[4] = {200, 520, 840, 1160};
    for (int i = 0; i < 4; ++i)
        draw_status_badge(c, pal, seq[i], xs[i] + 40, 140);
}

const std::vector<std::string>& classes_10() { return CLASSES_10; }
const std::vector<std::string>& classes_12() { return CLASSES_12; }

const Palette& palette_style_a() {
    static const Palette p = {
        rgb565(15, 20, 27),    // bg            #0F141B
        rgb565(26, 33, 43),    // surface       #1A212B
        rgb565(18, 25, 36),    // surface_alt   #121A24
        rgb565(231, 236, 242), // text          #E7ECF2
        rgb565(139, 152, 168), // dim           #8B98A8
        rgb565(74, 144, 226),  // primary       #4A90E2
        rgb565(61, 220, 132),  // success       #3DDC84
        rgb565(232, 169, 60),  // warning       #E8A93C
        rgb565(229, 96, 95),   // error         #E5605F
        rgb565(42, 53, 66),    // outline       #2A3542
        rgb565(20, 27, 37),    // accent_bar_bg #141B25
    };
    return p;
}

void render_main(Canvas& c, const Palette& pal, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, pal.bg);
    const std::vector<std::string>& classes = st.classes ? *st.classes : CLASSES_10;
    const font_t* b20 = fb(20), * b40 = fb(40), * b52 = fb(52);
    const font_t* r20 = fr(20), * m20 = fm(20);

    draw_header(c, pal, "RF SIGNAL RECOGNITION", st);

    // result card (top priority)
    fill_rect(c, 25, 84, 1255, 252, pal.surface);
    outline_rect(c, 25, 84, 1255, 252, pal.outline, 1);

    if (st.status == Status::Error) {
        draw_text(c, "RECOGNIZED SIGNAL", 45, 126, pal.dim, b20);
        draw_text(c, "NO SIGNAL", 45, 196, pal.error, b52);
        draw_text(c, "no valid data on input", 45, 240, pal.dim, r20);
        draw_status_chip(c, pal, "NO SIGNAL", pal.error, 1215, 122);
        // item 4: keep the info strip + bottom nav so Diagnostics/Touch stay reachable.
        draw_info_strip(c, pal, st);
        draw_nav(c, pal, 0);
        return;
    }

    const float conf = st.conf;
    const std::string& top1 = st.top1;
    const float conf_pct = conf * 100.0f;

    draw_text(c, "RECOGNIZED SIGNAL", 45, 126, pal.dim, b20);

    if (st.status == Status::Stale)
        draw_status_chip(c, pal, "STALE DATA", pal.warning, 1215, 122);
    else if (conf >= 0.6f)
        draw_status_chip(c, pal, "CONFIDENT", pal.success, 1215, 122);
    else
        draw_status_chip(c, pal, "LOW CONFIDENCE", pal.warning, 1215, 122);

    const std::uint16_t name_col = (st.status == Status::Stale) ? pal.dim : pal.text;
    draw_text(c, top1, 45, 200, name_col, b52);

    std::uint16_t conf_col;
    if (st.status != Status::Stale && conf < 0.6f) conf_col = pal.warning;
    else conf_col = (st.status == Status::Stale) ? pal.dim : pal.success;

    draw_text(c, "CONFIDENCE", 45, 240, pal.dim, r20);
    char pct[32];
    std::snprintf(pct, sizeof pct, "%.1f%%", conf_pct);
    draw_text(c, pct, 210, 240, conf_col, b40);

    // confidence bar (right of result card)
    const int bar_x0 = 700, bar_x1 = 1215, bar_y0 = 188, bar_y1 = 224;
    fill_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, pal.accent_bar_bg);
    outline_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, pal.outline, 1);
    if (st.status != Status::Stale) {
        const int w = static_cast<int>((bar_x1 - bar_x0) * conf);
        fill_rect(c, bar_x0, bar_y0 + 2, bar_x0 + w - 1, bar_y1 - 2, conf_col);
    }

    draw_text(c, "CLASS PROBABILITIES", 25, 288, pal.dim, b20);

    // two-column probability cards (second priority).  Geometry adapts to the
    // class count so 8..16 classes always fit above the info strip (item 3).
    const std::vector<float>& dist = st.dist;
    const int n = static_cast<int>(classes.size());
    const CardGrid g = card_grid(n);
    const int cols[2] = {25, 645};
    const int col_w = 610;
    // Vertical offsets inside a card: the 10-class card (44px) keeps the original
    // positions; tighter grids (12/14/16 classes) scale them down to fit.
    const int text_dy = (g.card_h >= 38) ? 31 : (g.card_h - 7);
    const int bar_top = (g.card_h >= 38) ? 14 : 6;
    const int bar_bot = text_dy - 1;
    for (int i = 0; i < n; ++i) {
        const int col = (i < g.rows) ? 0 : 1;
        const int row = (i < g.rows) ? i : (i - g.rows);
        const int cx = cols[col];
        const int cy = g.y0 + row * g.row_pitch;
        const float p = (i < static_cast<int>(dist.size())) ? dist[i] : 0.0f;
        const bool is_top = (classes[i] == top1);

        fill_rect(c, cx, cy, cx + col_w, cy + g.card_h, pal.surface);
        outline_rect(c, cx, cy, cx + col_w, cy + g.card_h,
                     is_top ? pal.primary : pal.outline, is_top ? 2 : 1);

        char rank[16];
        std::snprintf(rank, sizeof rank, "%2d", i + 1);
        draw_text(c, rank, cx + 14, cy + text_dy, is_top ? pal.primary : pal.dim, m20);
        draw_text(c, classes[i], cx + 54, cy + text_dy, pal.text, b20);

        const int bx0 = cx + 190, bx1 = cx + col_w - 90;
        const int by0 = cy + bar_top, by1 = cy + bar_bot;
        fill_rect(c, bx0, by0, bx1, by1, pal.accent_bar_bg);
        const int bw = static_cast<int>((bx1 - bx0) * p);
        fill_rect(c, bx0, by0, bx0 + bw, by1, is_top ? pal.primary : pal.dim);

        char pp[16];
        std::snprintf(pp, sizeof pp, "%4.1f%%", p * 100.0f);
        draw_text_right(c, pp, cx + col_w - 12, cy + text_dy, is_top ? pal.text : pal.dim, m20);
    }

    draw_info_strip(c, pal, st);
    draw_nav(c, pal, 0);
}

void render_diag(Canvas& c, const Palette& pal, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, pal.bg);
    const font_t* b20 = fb(20), * b52 = fb(52);
    const font_t* r20 = fr(20), * m20 = fm(20);

    draw_header(c, pal, "DIAGNOSTICS", st);

    if (st.status == Status::Error) {
        fill_rect(c, 25, 90, 1255, 594, pal.surface);
        outline_rect(c, 25, 90, 1255, 594, pal.outline, 1);
        draw_text(c, "NO DATA", 45, 250, pal.error, b52);
        draw_text(c, "diagnostics unavailable - signal pipeline reports no valid frames",
                  45, 310, pal.dim, r20);
        draw_nav(c, pal, 1);
        return;
    }

    // latency breakdown (left card)
    fill_rect(c, 25, 90, 620, 594, pal.surface);
    outline_rect(c, 25, 90, 620, 594, pal.outline, 1);
    draw_text(c, "LATENCY BREAKDOWN", 45, 132, pal.dim, b20);

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
            outline_rect(c, 45, ry - 16, 600, ry + 12, pal.outline, 1);
            draw_text(c, r.k, 57, ry, pal.text, b20);
            draw_text_right(c, r.v, 588, ry, pal.text, m20);
        } else {
            draw_text(c, r.k, 57, ry, pal.dim, r20);
            draw_text_right(c, r.v, 588, ry, pal.text, m20);
        }
        ry += 80;
    }

    // detailed counts (right card)
    fill_rect(c, 655, 90, 1255, 594, pal.surface);
    outline_rect(c, 655, 90, 1255, 594, pal.outline, 1);
    draw_text(c, "DETAILED COUNTS", 675, 132, pal.dim, b20);

    const struct { const char* k; const char* v; } cnt[5] = {
        {"frames rendered", "1024"},
        {"frames dropped", "0"},
        {"buffer resets", "0"},
        {"touch events", "57"},
        {"data source", st.source.c_str()},
    };
    ry = 200;
    for (const auto& r : cnt) {
        draw_text(c, r.k, 687, ry, pal.dim, r20);
        draw_text_right(c, r.v, 1223, ry, pal.text, m20);
        ry += 64;
    }

    draw_text(c, "signal status:", 675, 540, pal.dim, r20);
    draw_status_badge(c, pal, st.status, 1223, 534);

    draw_nav(c, pal, 1);
}

void render_touch(Canvas& c, const Palette& pal, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, pal.bg);
    const font_t* b20 = fb(20);
    const font_t* r20 = fr(20), * m20 = fm(20);

    draw_header(c, pal, "TOUCH TEST", st);

    // calibration (left card)
    fill_rect(c, 25, 90, 820, 594, pal.surface);
    outline_rect(c, 25, 90, 820, 594, pal.outline, 1);
    draw_text(c, "TOUCH CALIBRATION", 45, 132, pal.dim, b20);

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
        draw_text(c, r.k, 57, ry, pal.dim, r20);
        draw_text(c, *r.v, 250, ry, pal.text, m20);
        ry += 64;
    }

    // hit-region diagram (right card)
    fill_rect(c, 850, 90, 1255, 594, pal.surface);
    outline_rect(c, 850, 90, 1255, 594, pal.outline, 1);
    draw_text(c, "HIT REGIONS", 870, 132, pal.dim, b20);

    const char* tabs[3] = {"MAIN", "DIAG", "TOUCH"};
    int tx = 870;
    for (int i = 0; i < 3; ++i) {
        fill_rect(c, tx, 160, tx + 112, 220, pal.surface_alt);
        outline_rect(c, tx, 160, tx + 112, 220, i == 2 ? pal.primary : pal.outline, i == 2 ? 2 : 1);
        draw_text_center(c, tabs[i], tx + 56, 198, i == 2 ? pal.primary : pal.text, b20);
        tx += 124;
    }
    draw_text(c, "hit area >= 60 px physical", 870, 268, pal.dim, r20);
    draw_text(c, "bottom nav height 90 px raw", 870, 300, pal.dim, r20);

    const bool tconn = st.touch.connected;
    draw_text(c, "touch:", 870, 470, pal.dim, r20);
    draw_text(c, tconn ? "CONNECTED" : "DISCONNECTED", 950, 470,
              tconn ? pal.success : pal.warning, b20);
    char tstat[48];
    std::snprintf(tstat, sizeof tstat, "taps %llu",
                  static_cast<unsigned long long>(st.touch.taps));
    draw_text(c, tstat, 870, 510, pal.dim, r20);
    if (st.touch.last_x >= 0) {
        char pt[48];
        std::snprintf(pt, sizeof pt, "last (%d, %d)", st.touch.last_x, st.touch.last_y);
        draw_text(c, pt, 950, 510, pal.text, m20);
    }

    draw_nav(c, pal, 2);
}

// ---- PARAMETERS page (UI v3 M5) --------------------------------------------
// Two cards: SIGNAL & SPECTRUM (M3 spectrum domain) and LEVEL & MODEL (M3 raw/
// model domain + M1/M2 runtime state).  Measurement-derived numbers are gated on
// meas.valid so an absent v3 producer draws "--" placeholders rather than fake
// zeros; presence / level_mode / model_scale / rf_gain_db always come from the
// UiState runtime fields (with their own safe defaults).
void render_parameters(Canvas& c, const Palette& pal, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, pal.bg);
    const font_t* b20 = fb(20);

    draw_header(c, pal, "PARAMETERS", st);

    const bool has = st.meas.valid;
    const MeasureView& m = st.meas;

    // left card: SIGNAL & SPECTRUM
    fill_rect(c, 25, 90, 620, 550, pal.surface);
    outline_rect(c, 25, 90, 620, 550, pal.outline, 1);
    draw_text(c, "SIGNAL & SPECTRUM", 45, 132, pal.dim, b20);
    const struct { const char* k; std::string v; } left[8] = {
        {"power_dbfs",           has ? fnum("%.1f dBFS", m.power_dbfs) : std::string("--")},
        {"noise_floor_dbfs",     has ? fnum("%.1f dBFS", m.noise_floor_dbfs) : std::string("--")},
        {"snr_est_db",           has ? fnum("%.1f dB", m.snr_est_db) : std::string("--")},
        {"psd_peak_prominence",  has ? fnum("%.1f dB", m.psd_peak_prominence_db) : std::string("--")},
        {"occupied_bins",        has ? std::to_string(m.occupied_bins) : std::string("--")},
        {"occupied_bw_hz",       has ? fnum("%.1f Hz", m.occupied_bw_hz) : std::string("--")},
        {"spectral_centroid_hz", has ? fnum("%.1f Hz", m.spectral_centroid_hz) : std::string("--")},
        {"clip_ratio",           has ? fnum("%.2f%%", m.clip_ratio * 100.0) : std::string("--")},
    };
    int ry = 200;
    for (const auto& r : left) { draw_kv_row(c, pal, 45, 600, ry, r.k, r.v); ry += 46; }

    // right card: LEVEL & MODEL
    fill_rect(c, 655, 90, 1255, 550, pal.surface);
    outline_rect(c, 655, 90, 1255, 550, pal.outline, 1);
    draw_text(c, "LEVEL & MODEL", 675, 132, pal.dim, b20);
    const struct { const char* k; std::string v; } right[8] = {
        {"rms_counts",  has ? fnum("%.1f", m.rms_counts) : std::string("--")},
        {"peak_counts", has ? fnum("%.1f", m.peak_counts) : std::string("--")},
        {"papr_db",     has ? fnum("%.2f dB", m.papr_db) : std::string("--")},
        {"model_rms",   has ? fnum("%.3f", m.model_rms) : std::string("--")},
        {"presence",    st.presence},
        {"level_mode",  st.level_mode},
        {"model_scale", fnum("%.3f", st.model_scale) + "x"},
        {"rf_gain_db",  fnum("%.1f dB", st.rf_gain_db)},
    };
    ry = 200;
    for (const auto& r : right) { draw_kv_row(c, pal, 675, 1235, ry, r.k, r.v); ry += 46; }

    draw_info_strip(c, pal, st);
    draw_nav(c, pal, 1);
}

// ---- MODE page (UI v3 M5 -> M16 touch control) ------------------------------
// Five touch buttons: [FIXED][AUTO LOCK][BAND SCAN] + [START][STOP].  The APPLIED
// mode / run state (producer-authoritative, from work_mode / running) is the
// highlighted button; a touch request is shown as "requested mode" in the detail
// card and only becomes the highlight once the producer APPLIEs it.  Buttons sit
// ABOVE the nav band (y < 630), so the two tap areas never overlap.
void render_mode(Canvas& c, const Palette& pal, const UiState& st) {
    fill_rect(c, 0, 0, c.w - 1, c.h - 1, pal.bg);
    const font_t* b20 = fb(20), * b28 = fb(28);
    const font_t* r20 = fr(20);

    draw_header(c, pal, "MODE", st);

    int active = 0;
    if (st.work_mode == "AUTO LOCK") active = 1;
    else if (st.work_mode == "BAND SCAN") active = 2;

    const char* names[3] = {"FIXED", "AUTO LOCK", "BAND SCAN"};
    const char* desc[3] = {
        "fixed gain + fixed scale",
        "auto level, lock stable class",
        "sweep band, lock on signal",
    };
    for (int i = 0; i < 3; ++i) {
        int x0, y0, x1, y1;
        mode_ui::button_rect(i, x0, y0, x1, y1);
        const bool on = (i == active);
        const bool pressed = (st.pressed_button == i);   // M18-SW1 press-highlight
        fill_rect(c, x0, y0, x1, y1, (on || pressed) ? pal.surface : pal.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? pal.primary : (on ? pal.primary : pal.outline),
                     pressed ? 3 : (on ? 2 : 1));
        draw_text(c, names[i], x0 + 20, y0 + 44, on ? pal.primary : pal.text, b28);
        draw_text(c, desc[i], x0 + 20, y0 + 82, pal.dim, r20);
    }

    // START / STOP row: the ACTIVE run state is highlighted.
    {
        int x0, y0, x1, y1;
        mode_ui::button_rect(mode_ui::kBtnStart, x0, y0, x1, y1);
        const bool on = st.running;
        const bool pressed = (st.pressed_button == mode_ui::kBtnStart);   // M18-SW1
        fill_rect(c, x0, y0, x1, y1, (on || pressed) ? pal.surface : pal.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? pal.success : (on ? pal.success : pal.outline),
                     pressed ? 3 : (on ? 2 : 1));
        draw_text_center(c, "START", (x0 + x1) / 2, y0 + 36, on ? pal.success : pal.text, b28);
    }
    {
        int x0, y0, x1, y1;
        mode_ui::button_rect(mode_ui::kBtnStop, x0, y0, x1, y1);
        const bool on = !st.running;
        const bool pressed = (st.pressed_button == mode_ui::kBtnStop);   // M18-SW1
        fill_rect(c, x0, y0, x1, y1, (on || pressed) ? pal.surface : pal.surface_alt);
        outline_rect(c, x0, y0, x1, y1,
                     pressed ? pal.warning : (on ? pal.warning : pal.outline),
                     pressed ? 3 : (on ? 2 : 1));
        draw_text_center(c, "STOP", (x0 + x1) / 2, y0 + 36, on ? pal.warning : pal.text, b28);
    }

    // detail card: applied vs requested + control-channel state.
    fill_rect(c, 25, mode_ui::kDetailY0, 1255, mode_ui::kDetailY1, pal.surface);
    outline_rect(c, 25, mode_ui::kDetailY0, 1255, mode_ui::kDetailY1, pal.outline, 1);

    const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
    const std::uint16_t run_col = st.running ? pal.success : pal.warning;
    const std::uint16_t ctl_col = ctl_ok ? pal.success : pal.warning;
    const std::uint16_t cmd_col = command_status_color(pal, st.command_status);
    const std::uint16_t req_col = (st.requested_mode == st.work_mode)
                                      ? pal.text : pal.warning;

    int ry = mode_ui::kDetailY0 + 32;
    // 7 rows (a "feedback" row was added for M18-SW1 Task A) fit the frozen card
    // at a 38px pitch.
    auto row = [&](const char* label, const std::string& value, std::uint16_t col) {
        draw_text(c, label, 45, ry, pal.dim, r20);
        draw_text_right(c, value, 600, ry, col, b20);
        ry += 38;
    };
    row("current mode", st.work_mode, pal.primary);
    row("requested mode", st.requested_mode, req_col);
    row("run state", st.running ? "RUNNING" : "STOPPED", run_col);
    row("control connection", st.ctl_connected, ctl_col);
    row("last command", st.last_command, pal.text);
    row("command status", st.command_status, cmd_col);
    row("feedback", st.feedback, feedback_color(pal, st.feedback));

    draw_info_strip(c, pal, st);
    draw_nav(c, pal, 2);
}

} // namespace ui
