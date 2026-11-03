// font.hpp — 8x8 bitmap ASCII font (software RGB565 rendering, no GPU/Qt).
//
// A clean, self-authored 8x8 bitmap font (public-domain-style shapes) covering
// exactly the character set the instrument UI emits — uppercase A-Z, digits 0-9,
// and the punctuation the UI uses: space - _ : . % / + > < ( ).
//
// Each glyph is 8 rows x 8 columns.  A row byte uses bit 7 (0x80) as the leftmost
// pixel.  The renderer scales a glyph by an integer factor (scale=3 -> 24 px,
// scale=4 -> 32 px, scale=6 -> 48 px, scale=8 -> 64 px), which keeps the strokes
// crisp at every size and keeps body text >= 20 px on the 720p canvas.
//
// The UI uses UPPERCASE ONLY (the task forbids lowercase -> hollow boxes), so
// lowercase is intentionally not in the table; any unsupported char renders as a
// solid block so a missing glyph is visible rather than silently wrong.

#pragma once

#include <cstdint>

namespace font {

constexpr int kGlyphW = 8;
constexpr int kGlyphH = 8;

struct Glyph {
    std::uint8_t rows[kGlyphH];   // bit 7 = leftmost pixel of that row
};

// Returns the glyph for an uppercase ASCII char / digit / supported symbol.
// Unsupported chars return a solid block (missing-glyph marker).  Returned by
// value (8-byte struct) so no lifetime hazard.
Glyph glyph(char c);

// True when `c` has a dedicated glyph (not the solid-block fallback).
bool is_supported(char c);

} // namespace font
