// image_writer.cpp — BMP writer, nearest-neighbor downscale, FNV-1a pixel hash.

#include "image_writer.hpp"

#include "canvas.hpp"   // r_of/g_of/b_of

#include <cstdio>
#include <cstring>
#include <vector>

namespace img {

namespace {

void put_u16(std::vector<unsigned char>& b, std::uint16_t v) {
    b.push_back(static_cast<unsigned char>(v & 0xFF));
    b.push_back(static_cast<unsigned char>((v >> 8) & 0xFF));
}

void put_u32(std::vector<unsigned char>& b, std::uint32_t v) {
    b.push_back(static_cast<unsigned char>(v & 0xFF));
    b.push_back(static_cast<unsigned char>((v >> 8) & 0xFF));
    b.push_back(static_cast<unsigned char>((v >> 16) & 0xFF));
    b.push_back(static_cast<unsigned char>((v >> 24) & 0xFF));
}

} // namespace

bool write_bmp(const std::string& path, const std::uint16_t* rgb565, int w, int h) {
    if (w <= 0 || h <= 0 || rgb565 == nullptr) return false;

    const int row_size = (w * 3 + 3) & ~3;          // 4-byte aligned
    const int pixel_bytes = row_size * h;

    std::vector<unsigned char> b;
    b.reserve(static_cast<std::size_t>(54) + pixel_bytes);

    // BITMAPFILEHEADER (14 bytes)
    b.push_back('B'); b.push_back('M');
    put_u32(b, static_cast<std::uint32_t>(54 + pixel_bytes));
    put_u16(b, 0); put_u16(b, 0);
    put_u32(b, 54);

    // BITMAPINFOHEADER (40 bytes)
    put_u32(b, 40);
    put_u32(b, static_cast<std::uint32_t>(w));
    put_u32(b, static_cast<std::uint32_t>(h));
    put_u16(b, 1);                 // planes
    put_u16(b, 24);                // bpp
    put_u32(b, 0);                 // BI_RGB
    put_u32(b, static_cast<std::uint32_t>(pixel_bytes));
    put_u32(b, 2835);              // 72 DPI, pixels/meter
    put_u32(b, 2835);
    put_u32(b, 0); put_u32(b, 0);

    // pixels, bottom-up, BGR
    for (int y = h - 1; y >= 0; --y) {
        const std::uint16_t* row = rgb565 + static_cast<std::size_t>(y) * w;
        for (int x = 0; x < w; ++x) {
            const std::uint16_t c = row[x];
            b.push_back(ui::b_of(c));   // B
            b.push_back(ui::g_of(c));   // G
            b.push_back(ui::r_of(c));   // R
        }
        for (int pad = w * 3; pad < row_size; ++pad) b.push_back(0);
    }

    std::FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    const std::size_t n = std::fwrite(b.data(), 1, b.size(), f);
    std::fclose(f);
    return n == b.size();
}

std::vector<std::uint16_t> downscale(const std::uint16_t* src, int sw, int sh,
                                     int dw, int dh) {
    std::vector<std::uint16_t> out;
    if (src == nullptr || sw <= 0 || sh <= 0 || dw <= 0 || dh <= 0) return out;
    out.resize(static_cast<std::size_t>(dw) * dh);
    for (int y = 0; y < dh; ++y) {
        int sy = static_cast<int>((static_cast<std::int64_t>(y) * sh) / dh);
        if (sy >= sh) sy = sh - 1;
        for (int x = 0; x < dw; ++x) {
            const int sx = static_cast<int>((static_cast<std::int64_t>(x) * sw) / dw);
            out[static_cast<std::size_t>(y) * dw + x] =
                src[static_cast<std::size_t>(sy) * sw + sx];
        }
    }
    return out;
}

std::uint64_t fnv1a_pixels(const std::uint16_t* px, std::size_t n) {
    std::uint64_t h = 1469598103934665603ULL;   // FNV offset basis
    const unsigned char* p = reinterpret_cast<const unsigned char*>(px);
    const std::size_t bytes = n * sizeof(std::uint16_t);
    for (std::size_t i = 0; i < bytes; ++i) {
        h ^= p[i];
        h *= 1099511628211ULL;                  // FNV prime
    }
    return h;
}

} // namespace img
