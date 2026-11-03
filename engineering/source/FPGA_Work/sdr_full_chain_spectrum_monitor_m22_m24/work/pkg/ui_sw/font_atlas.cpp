// font_atlas.cpp — RGB565 integer alpha-blend text renderer over the glyph atlas.
//
// The glyph data lives in the GENERATED font_atlas_data.cpp (see
// design_mockups/tools/gen_font_atlas.py).  This file only implements the blend
// math, text layout, clipping and the M22.1 text trace, mirroring the PC
// design-draft renderer exactly:
//   out = (dst*(255-a) + fg*a + 127) >> 8   per 8-bit channel, RGB565.

#include "font_atlas.hpp"

namespace ui {

namespace {

// Unpack RGB565 -> 8-bit per channel (5->8 and 6->8 by bit replication).
inline void unpack565(std::uint16_t c, int& r, int& g, int& b) {
    const int r5 = (c >> 11) & 0x1F;
    const int g6 = (c >> 5)  & 0x3F;
    const int b5 = c         & 0x1F;
    r = (r5 << 3) | (r5 >> 2);
    g = (g6 << 2) | (g6 >> 4);
    b = (b5 << 3) | (b5 >> 2);
}

inline std::uint16_t pack565(int r, int g, int b) {
    return static_cast<std::uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// Blend one 8-bit coverage value `a` over a 565 pixel `dst` with foreground
// (fr, fg, fb) in 8-bit per-channel.  Same rounding as the design-draft math.
inline std::uint16_t blend_px(std::uint16_t dst, int fr, int fg, int fb, int a) {
    int dr, dg, db;
    unpack565(dst, dr, dg, db);
    const int r = (dr * (255 - a) + fr * a + 127) >> 8;
    const int g = (dg * (255 - a) + fg * a + 127) >> 8;
    const int b = (db * (255 - a) + fb * a + 127) >> 8;
    return pack565(r, g, b);
}

inline const glyph_t* glyph_of(const font_t* f, unsigned char ch) {
    if (ch >= 32 && ch <= 126) return &f->glyphs[ch - 32];
    return &f->glyphs[0];   // out-of-range -> space
}

// ---- text trace state -----------------------------------------------------
std::vector<TracedText>* g_trace = nullptr;
int g_region = 0;
TextKind g_kind = TextKind::Other;

void trace(const std::string& s, int x, int y, const font_t* f) {
    if (!g_trace) return;
    TracedText t;
    t.text = s;
    t.x0 = x;
    t.x1 = x + text_width(s, f, 0) - 1;
    t.y0 = y - static_cast<int>(f->ascent);
    t.y1 = y + static_cast<int>(f->descent);
    t.size = f->size;
    t.region = g_region;
    t.kind = static_cast<int>(g_kind);
    g_trace->push_back(std::move(t));
}

} // namespace

int text_width(const std::string& s, const font_t* f, int spacing) {
    int w = 0;
    for (char ch : s) { w += glyph_of(f, static_cast<unsigned char>(ch))->adv; w += spacing; }
    if (!s.empty()) w -= spacing;
    return w;
}

TextBox text_box(const std::string& s, int x, int y, const font_t* f, int spacing) {
    TextBox b;
    b.x0 = x;
    b.x1 = x + text_width(s, f, spacing) - 1;
    b.y0 = y - static_cast<int>(f->ascent);
    b.y1 = y + static_cast<int>(f->descent);
    return b;
}

int draw_text_clipped(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
                      const font_t* f, int cx0, int cy0, int cx1, int cy1, int spacing) {
    trace(s, x, y, f);   // record the INTENDED bbox (before clipping)

    int fr, fg, fb;
    unpack565(color, fr, fg, fb);

    const int gw = f->line_h;   // glyph bitmap height is constant per font
    int px = x;
    for (char ch : s) {
        const glyph_t* g = glyph_of(f, static_cast<unsigned char>(ch));
        const std::uint8_t* cov = f->data + g->offset;
        const int adv = g->adv;
        const int tx = px;
        const int ty = y - static_cast<int>(f->ascent);
        for (int gy = 0; gy < gw; ++gy) {
            const int cy = ty + gy;
            if (cy < 0 || cy >= c.h) continue;
            if (cy < cy0 || cy > cy1) continue;
            const std::uint8_t* row = cov + gy * adv;
            const int row_base = cy * c.w;
            for (int gx = 0; gx < adv; ++gx) {
                const int a = row[gx];
                if (a == 0) continue;
                const int cx = tx + gx;
                if (cx < 0 || cx >= c.w) continue;
                if (cx < cx0 || cx > cx1) continue;
                const int ci = row_base + cx;
                if (a == 255) { c.px[ci] = color; continue; }
                c.px[ci] = blend_px(c.px[ci], fr, fg, fb, a);
            }
        }
        px += adv + spacing;
    }
    return px;
}

int draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
              const font_t* f, int spacing) {
    return draw_text_clipped(c, s, x, y, color, f, 0, 0, c.w - 1, c.h - 1, spacing);
}

void draw_text_right(Canvas& c, const std::string& s, int x_right, int y,
                     std::uint16_t color, const font_t* f, int spacing) {
    const int w = text_width(s, f, spacing);
    draw_text(c, s, x_right - w, y, color, f, spacing);
}

void draw_text_center(Canvas& c, const std::string& s, int xc, int y,
                      std::uint16_t color, const font_t* f, int spacing) {
    const int w = text_width(s, f, spacing);
    draw_text(c, s, xc - w / 2, y, color, f, spacing);
}

std::vector<TracedText>* text_trace_begin(std::vector<TracedText>* sink) {
    std::vector<TracedText>* prev = g_trace;
    g_trace = sink;
    return prev;
}

void text_trace_end(std::vector<TracedText>* prev) {
    g_trace = prev;
}

void text_trace_set_region(int region) {
    g_region = region;
}

void text_trace_set_kind(TextKind kind) {
    g_kind = kind;
}

} // namespace ui
