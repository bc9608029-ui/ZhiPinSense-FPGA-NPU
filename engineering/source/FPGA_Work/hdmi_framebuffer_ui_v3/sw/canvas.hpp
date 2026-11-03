// canvas.hpp — software RGB565 canvas (regular RAM, no GPU/Qt).
//
// The UI renders into a plain std::vector<std::uint16_t> staging buffer in normal
// RAM (never into the device mapping).  Only DirectFramebufferBackend::submit()
// copies the finished frame to the device with scalar 16-bit stores.  This keeps
// the device-mapped framebuffer free of any SIMD/NEON wide store.
//
// All drawing is integer, clipped to the canvas, and uses only: solid fills,
// 1-2 px solid outlines, and the 8x8 bitmap font (integer-scaled).  No gradients,
// no alpha blending, no anti-aliasing, no per-pixel floating point.

#pragma once

#include "font.hpp"

#include <cstdint>
#include <cstddef>
#include <vector>
#include <string>

namespace ui {

// RGB565 packed color from 8-bit components.
constexpr std::uint16_t rgb565(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    return static_cast<std::uint16_t>(
        ((static_cast<std::uint16_t>(r) & 0xF8u) << 8) |
        ((static_cast<std::uint16_t>(g) & 0xFCu) << 3) |
        (static_cast<std::uint16_t>(b) >> 3));
}

// Unpack helpers (for tests / verification).
constexpr std::uint8_t r_of(std::uint16_t c) { return static_cast<std::uint8_t>((c >> 8) & 0xF8u); }
constexpr std::uint8_t g_of(std::uint16_t c) { return static_cast<std::uint8_t>((c >> 3) & 0xFCu); }
constexpr std::uint8_t b_of(std::uint16_t c) { return static_cast<std::uint8_t>((c & 0x1Fu) << 3); }

// A clipped, integer software canvas over a staging buffer.
class Canvas {
public:
    explicit Canvas(int width = 1280, int height = 720)
        : w_(width), h_(height), buf_(static_cast<std::size_t>(width) * height, 0) {}

    int width() const  { return w_; }
    int height() const { return h_; }

    // Direct access to the staging buffer (submit() copies this to the device).
    const std::uint16_t* pixels() const { return buf_.data(); }
    std::uint16_t* pixels()             { return buf_.data(); }
    std::size_t pixel_count() const     { return buf_.size(); }

    // Fill the whole canvas.
    void clear(std::uint16_t color) {
        std::fill(buf_.begin(), buf_.end(), color);
    }

    // Set one pixel (clipped).
    void set(int x, int y, std::uint16_t color) {
        if (x < 0 || y < 0 || x >= w_ || y >= h_) return;
        buf_[static_cast<std::size_t>(y) * w_ + x] = color;
    }

    std::uint16_t get(int x, int y) const {
        if (x < 0 || y < 0 || x >= w_ || y >= h_) return 0;
        return buf_[static_cast<std::size_t>(y) * w_ + x];
    }

    // Filled rectangle (clipped).
    void fill_rect(int x, int y, int w, int h, std::uint16_t color) {
        for (int yy = y; yy < y + h; ++yy)
            for (int xx = x; xx < x + w; ++xx)
                set(xx, yy, color);
    }

    // Solid outline of a rectangle, 1 or 2 px thick (clipped).
    void rect(int x, int y, int w, int h, std::uint16_t color, int thick = 1) {
        if (thick < 1) thick = 1;
        if (thick > 2) thick = 2;
        // top/bottom bands
        fill_rect(x, y, w, thick, color);
        fill_rect(x, y + h - thick, w, thick, color);
        // left/right bands (excluding corners already drawn)
        fill_rect(x, y + thick, thick, h - 2 * thick, color);
        fill_rect(x + w - thick, y + thick, thick, h - 2 * thick, color);
    }

    // Text metrics at an integer glyph scale (scale 3 -> 24 px, 4 -> 32, ...).
    static int glyph_w(int scale) { return font::kGlyphW * scale; }
    static int glyph_h(int scale) { return font::kGlyphH * scale; }
    static int text_w(const std::string& s, int scale) {
        return static_cast<int>(s.size()) * glyph_w(scale);
    }

    // Draw a glyph with its top-left at (x,y), integer-scaled, clipped.
    void glyph(int x, int y, char c, int scale, std::uint16_t color) {
        const font::Glyph g = font::glyph(c);
        for (int row = 0; row < font::kGlyphH; ++row) {
            std::uint8_t bits = g.rows[row];
            for (int col = 0; col < font::kGlyphW; ++col) {
                if (bits & 0x80u) {              // bit 7 = leftmost
                    fill_rect(x + col * scale, y + row * scale, scale, scale, color);
                }
                bits = static_cast<std::uint8_t>(bits << 1);
            }
        }
    }

    // Draw a string (uppercase only), integer-scaled, clipped per glyph.
    void text(int x, int y, const std::string& s, int scale, std::uint16_t color) {
        int cx = x;
        for (char c : s) {
            glyph(cx, y, c, scale, color);
            cx += glyph_w(scale);
        }
    }

private:
    int w_;
    int h_;
    std::vector<std::uint16_t> buf_;
};

} // namespace ui
