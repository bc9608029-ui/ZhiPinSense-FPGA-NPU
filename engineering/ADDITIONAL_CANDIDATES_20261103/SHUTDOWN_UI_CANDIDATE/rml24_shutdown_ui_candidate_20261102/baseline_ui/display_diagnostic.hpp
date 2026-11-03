// display_diagnostic.hpp — M18-0 display root-cause diagnostic helpers (pure logic).
//
// These helpers are the device-INDEPENDENT core of board_display_diagnostic.cpp.
// They are host-testable (no /dev/udmabuf0, no /dev/mem) and shared verbatim by the
// board binary and host_tests/test_display_diagnostic.cpp, so the CRC / pattern /
// mode-parse logic the board runs is exercised on the host first.
//
// M18-0 scope discipline: this file ONLY adds diagnostics.  It never touches the
// production flip / clear / display-enable logic; the backend additions used by
// Tool B/D are separate, purely-additive methods (submit_frame_no_flip,
// read_frame_words) that leave submit_frame() unchanged.

#pragma once

#include <cstdint>
#include <cstddef>
#include <string>

namespace ddx {

// Diagnostic tool modes (A–D from the M18-0 directive).
enum class Mode {
    A_BlackClearStatic,   // full-buffer black-clear + static hold (no flip)
    B_SingleBufferLock,   // single-buffer lock, flip fully disabled
    C_RedBlueSwitch,      // red/blue dual-buffer low-frequency switch
    D_CrcCheck,           // framebuffer pre/post submit CRC
};

// Parse a mode token.  Accepts: "a"/"A"/"black-clear"/"black_clear",
// "b"/"B"/"single-buffer"/"single_buffer", "c"/"C"/"red-blue"/"red_blue",
// "d"/"D"/"crc".  Returns false (out unchanged) on anything else.
bool parse_mode(const std::string& text, Mode* out);

// Canonical lowercase name for a mode ("a".."d"), used in printed result lines.
const char* mode_name(Mode m);

// RGB565 colour constants (red/blue are the two Tool C switch colours).
constexpr std::uint16_t kBlack = 0x0000u;
constexpr std::uint16_t kRed   = 0xF800u;
constexpr std::uint16_t kBlue  = 0x001Fu;
constexpr std::uint16_t kGreen = 0x07E0u;

// Fill `words` RGB565 halfwords with a solid colour.  Bounds are the caller's
// responsibility (matches submit_frame's contract: 1..frame_words).
void fill_solid(std::uint16_t* dst, std::size_t words, std::uint16_t rgb565);

// CRC-32 (IEEE 802.3, reflected, poly 0xEDB88320, init 0xFFFFFFFF, final xor
// 0xFFFFFFFF) over `bytes`.  Deterministic across little-endian hosts/boards:
// callers pass the raw in-memory byte stream of the RGB565 halfwords, so the
// result is identical whether it is computed over an AArch64 board mapping or an
// x86-64 host buffer.
std::uint32_t crc32(const void* data, std::size_t bytes);

// CRC-32 over a range of RGB565 halfwords, computed over their in-memory byte
// representation (low byte first).  This is the value Tool D prints pre/post.
std::uint32_t crc32_u16(const std::uint16_t* words, std::size_t count);

} // namespace ddx
