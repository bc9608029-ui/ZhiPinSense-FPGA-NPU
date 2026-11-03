// image_writer.hpp — host-side image output: 24-bit BMP writer, nearest-neighbor
// downscale, and an FNV-1a pixel hash for deterministic golden tests.
//
// These are used ONLY by the host screenshot generator and tests; the board's
// phase programs never write image files.

#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>

namespace img {

// Write a 1280x720 (or any size) RGB565 buffer as a 24-bit BMP (BGR, bottom-up).
// Returns false (and no file) on error.
bool write_bmp(const std::string& path, const std::uint16_t* rgb565, int w, int h);

// Nearest-neighbor downscale RGB565 (e.g. 1280x720 -> 1024x600) into a new buffer.
std::vector<std::uint16_t> downscale(const std::uint16_t* src, int sw, int sh,
                                     int dw, int dh);

// FNV-1a 64-bit hash over the raw 16-bit pixels (deterministic golden check).
std::uint64_t fnv1a_pixels(const std::uint16_t* px, std::size_t n);

} // namespace img
