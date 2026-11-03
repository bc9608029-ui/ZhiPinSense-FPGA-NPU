// font_atlas.cpp — RGB565 integer alpha-blend text renderer over the glyph atlas.
//
// The glyph data lives in the GENERATED font_atlas_data.cpp (see
// design_mockups/tools/gen_font_atlas.py).  This file only implements the blend
// math and text layout, mirroring the PC design-draft renderer exactly:
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

} // namespace

int text_width(const std::string& s, const font_t* f, int spacing) {
    int w = 0;
    for (char ch : s) { w += glyph_of(f, static_cast<unsigned char>(ch))->adv; w += spacing; }
    if (!s.empty()) w -= spacing;
    return w;
}

int draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
              const font_t* f, int spacing) {
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
            const std::uint8_t* row = cov + gy * adv;
            const int row_base = cy * c.w;
            for (int gx = 0; gx < adv; ++gx) {
                const int a = row[gx];
                if (a == 0) continue;
                const int cx = tx + gx;
                if (cx < 0 || cx >= c.w) continue;
                const int ci = row_base + cx;
                if (a == 255) { c.px[ci] = color; continue; }
                c.px[ci] = blend_px(c.px[ci], fr, fg, fb, a);
            }
        }
        px += adv + spacing;
    }
    return px;
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

TextBox text_box(const std::string& s, const font_t* f, int x, int y, int spacing) {
    TextBox b;
    b.x = x;
    b.y = y - static_cast<int>(f->ascent);
    b.w = text_width(s, f, spacing);
    b.h = static_cast<int>(f->ascent) + static_cast<int>(f->descent);
    return b;
}

std::string fit_text(const std::string& s, const font_t* f, int max_w, int spacing) {
    std::string out;
    int w = 0;
    bool first = true;
    for (char ch : s) {
        const glyph_t* g = glyph_of(f, static_cast<unsigned char>(ch));
        const int add = (first ? 0 : spacing) + static_cast<int>(g->adv);
        if (w + add > max_w) break;
        w += add;
        out.push_back(ch);
        first = false;
    }
    return out;
}

std::string ellipsize_text(const std::string& s, const font_t* f, int max_w, int spacing) {
    if (text_width(s, f, spacing) <= max_w) return s;
    const glyph_t* dot = glyph_of(f, static_cast<unsigned char>('.'));
    const int reserve = 2 * static_cast<int>(dot->adv) + 2 * spacing;
    std::string prefix = fit_text(s, f, max_w - reserve, spacing);
    while (!prefix.empty() && text_width(prefix + "..", f, spacing) > max_w)
        prefix.pop_back();
    return prefix + "..";
}

void draw_text_clipped(Canvas& c, const std::string& s, int x, int y, int max_w,
                       std::uint16_t color, const font_t* f, int spacing) {
    if (max_w <= 0) return;
    int fr, fg, fb;
    unpack565(color, fr, fg, fb);

    const int gw = f->line_h;   // glyph bitmap height is constant per font
    const int clip_right = x + max_w;
    int px = x;
    for (char ch : s) {
        const glyph_t* g = glyph_of(f, static_cast<unsigned char>(ch));
        const std::uint8_t* cov = f->data + g->offset;
        const int adv = g->adv;
        if (px + adv > clip_right) break;   // no room for this glyph -> stop
        const int tx = px;
        const int ty = y - static_cast<int>(f->ascent);
        for (int gy = 0; gy < gw; ++gy) {
            const int cy = ty + gy;
            if (cy < 0 || cy >= c.h) continue;
            const std::uint8_t* row = cov + gy * adv;
            const int row_base = cy * c.w;
            for (int gx = 0; gx < adv; ++gx) {
                const int a = row[gx];
                if (a == 0) continue;
                const int cx = tx + gx;
                if (cx < 0 || cx >= c.w) continue;
                const int ci = row_base + cx;
                if (a == 255) { c.px[ci] = color; continue; }
                c.px[ci] = blend_px(c.px[ci], fr, fg, fb, a);
            }
        }
        px += adv + spacing;
    }
}

} // namespace ui
