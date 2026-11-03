// font_atlas.hpp — anti-aliased bitmap font atlas interface (FMQL30TAI HDMI UI).
//
// The DejaVu Sans (Bitstream Vera license) glyphs are pre-rasterized on the PC to
// 8-bit grayscale coverage and baked into font_atlas_data.cpp.  The board does NO
// FreeType: draw_text() here only performs RGB565 integer alpha blend
//   out = (dst*(255-a) + fg*a + 127) >> 8     (per channel, 8-bit)
// over the ordinary-memory staging framebuffer.  No runtime scaling of the glyphs
// ever happens — every size (20/24/28/40/52 px) is a fixed, pre-rasterized font.
//
// Charset = printable ASCII 32..126 (95 glyphs).  For each glyph the bitmap width
// equals its advance, so only {offset, advance} is stored (height = font line_h).

#pragma once

#include <cstdint>
#include <string>

namespace ui {

struct Canvas {
    std::uint16_t* px;   // RGB565, row-major, px[y*w + x]
    int w;
    int h;
};

enum class Weight { Regular = 0, Bold = 1, Mono = 2 };

struct glyph_t {
    std::uint32_t offset;  // offset into the font's data[] (bitmap start)
    std::uint8_t  adv;     // advance width == bitmap width (px)
};

struct font_t {
    const std::uint8_t* data;   // concatenated glyph bitmaps (row-major, adv x line_h)
    const glyph_t*      glyphs; // 95 entries for ASCII 32..126
    std::uint8_t line_h;        // ascent + descent
    std::uint8_t ascent;        // pixels from glyph top to the baseline
    std::uint8_t descent;
    std::uint8_t size;          // nominal size in px
    std::uint8_t space_adv;     // advance of ' ' (fallback for out-of-range chars)
};

// Pack 8-bit RGB into RGB565 (5-6-5).
inline std::uint16_t rgb565(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    return static_cast<std::uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// Look up a pre-rasterized font, or nullptr if that weight/size is not baked in.
const font_t* font_get(Weight w, int size);

// Advance width of `s` at the given font, in px.
int text_width(const std::string& s, const font_t* f, int spacing = 0);

// Draw `s` with the baseline at (x, y), using RGB565 integer alpha blend.
// Returns the x position after the last glyph.  Out-of-range chars render as space.
int draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
              const font_t* f, int spacing = 0);

// Right-aligned / center-aligned variants (x_right / xc are the anchor x).
void draw_text_right(Canvas& c, const std::string& s, int x_right, int y,
                     std::uint16_t color, const font_t* f, int spacing = 0);
void draw_text_center(Canvas& c, const std::string& s, int xc, int y,
                      std::uint16_t color, const font_t* f, int spacing = 0);

// ---- text metrics (M29 UI redesign Task B; real font-boundary helpers) --------
// A pixel bounding box of `s` drawn with its baseline at (x, y): x is the left
// edge, y - ascent the top, width the advance, height ascent + descent.  Useful
// for host-side collision / no-overflow assertions.
struct TextBox { int x = 0; int y = 0; int w = 0; int h = 0; };
TextBox text_box(const std::string& s, const font_t* f, int x, int y, int spacing = 0);

// Longest prefix of `s` whose advance fits in `max_w` (empty when nothing fits).
// Small, allocation-free for typical inputs; used only on the worst-string path.
std::string fit_text(const std::string& s, const font_t* f, int max_w, int spacing = 0);

// `s` if it fits, else a prefix truncated so that prefix + ".." fits in `max_w`.
// The baked atlas is ASCII 32..126, so the ellipsis is two ASCII dots (".."),
// never the un-baked U+2026.
std::string ellipsize_text(const std::string& s, const font_t* f, int max_w, int spacing = 0);

// Draw `s` clipped to the horizontal span [x, x + max_w) (never past the right
// edge of the container), then to the canvas.  Glyphs past the clip edge are
// dropped, so a long value can never overflow its card.
void draw_text_clipped(Canvas& c, const std::string& s, int x, int y, int max_w,
                       std::uint16_t color, const font_t* f, int spacing = 0);

} // namespace ui
