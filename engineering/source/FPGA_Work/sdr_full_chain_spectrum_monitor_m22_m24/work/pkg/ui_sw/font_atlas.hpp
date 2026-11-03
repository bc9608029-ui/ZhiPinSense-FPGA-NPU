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
//
// M22.1 (UI 视觉重构): this header also exposes (a) text_box(), which derives a
// text run's bounding box from the font's REAL metrics (ascent/descent/advance)
// rather than any hardcoded width, and (b) draw_text_clipped(), which rasterizes
// only the pixels inside an explicit clip rect so no string can paint outside its
// card/button/screen, plus (c) an optional text TRACE that records every drawn
// run's intended bounding box so host tests can prove containment / non-overlap
// with the same metrics the renderer used to position the text.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

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

// Inclusive bounding box of a text run whose baseline is at (x, y).  The y span is
// [y-ascent, y+descent] and the x span is [x, x+width-1] — both from the font's
// real metrics, never a guessed width.
struct TextBox { int x0 = 0, y0 = 0, x1 = 0, y1 = 0; };
TextBox text_box(const std::string& s, int x, int y, const font_t* f, int spacing = 0);

// Draw `s` with the baseline at (x, y), using RGB565 integer alpha blend.
// Returns the x position after the last glyph.  Out-of-range chars render as space.
int draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
              const font_t* f, int spacing = 0);

// Draw `s` with the baseline at (x, y), rasterizing ONLY the pixels inside the
// inclusive clip rect [cx0,cy0]-[cx1,cy1].  Returns the un-clipped advance x, so
// callers can chain runs.  This is the overflow safety net: a string that (for any
// reason) would exceed its card is silently cut at the card edge instead of
// painting over a neighbouring region.
int draw_text_clipped(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
                      const font_t* f, int cx0, int cy0, int cx1, int cy1, int spacing = 0);

// Right-aligned / center-aligned variants (x_right / xc are the anchor x).
void draw_text_right(Canvas& c, const std::string& s, int x_right, int y,
                     std::uint16_t color, const font_t* f, int spacing = 0);
void draw_text_center(Canvas& c, const std::string& s, int xc, int y,
                      std::uint16_t color, const font_t* f, int spacing = 0);

// ---- text trace (host-test introspection; zero cost on the board) ----------
// When a sink is installed, every draw_text / draw_text_clipped / draw_text_right
// / draw_text_center call appends the run's INTENDED (un-clipped) bounding box,
// tagged with the current region and kind.  Recording the un-clipped box is
// deliberate: a test must prove the renderer POSITIONED the text inside its
// container, not merely that clipping hid an overflow.  On the board no sink is
// ever installed, so the cost is a single null-pointer check per draw call.
enum class TextKind : int { Other = 0, Title = 1, Label = 2, Value = 3, Unit = 4 };

struct TracedText {
    std::string text;
    int x0 = 0, y0 = 0, x1 = 0, y1 = 0;   // intended bbox (inclusive)
    int size = 0;                         // font size in px
    int region = 0;                       // renderer-assigned container id
    int kind = 0;                         // TextKind
};

// Install `sink` and return the previously-installed sink (or nullptr).
std::vector<TracedText>* text_trace_begin(std::vector<TracedText>* sink);
// Restore a sink previously returned by text_trace_begin.
void text_trace_end(std::vector<TracedText>* prev);
// Tag subsequent draw calls with a container region / text kind.
void text_trace_set_region(int region);
void text_trace_set_kind(TextKind kind);

} // namespace ui
