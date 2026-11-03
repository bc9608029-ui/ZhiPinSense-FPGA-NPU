// display_diagnostic.cpp — implementation of the M18-0 diagnostic pure logic.
// See display_diagnostic.hpp for the contract.

#include "display_diagnostic.hpp"

#include <cctype>

namespace ddx {

bool parse_mode(const std::string& text, Mode* out) {
    if (!out) return false;
    // Normalise: strip surrounding whitespace, lowercase ASCII.
    std::string s = text;
    std::size_t b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return false;
    std::size_t e = s.find_last_not_of(" \t\r\n");
    s = s.substr(b, e - b + 1);
    for (char& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));

    if (s == "a" || s == "black-clear" || s == "black_clear") {
        *out = Mode::A_BlackClearStatic;
        return true;
    }
    if (s == "b" || s == "single-buffer" || s == "single_buffer") {
        *out = Mode::B_SingleBufferLock;
        return true;
    }
    if (s == "c" || s == "red-blue" || s == "red_blue") {
        *out = Mode::C_RedBlueSwitch;
        return true;
    }
    if (s == "d" || s == "crc") {
        *out = Mode::D_CrcCheck;
        return true;
    }
    return false;
}

const char* mode_name(Mode m) {
    switch (m) {
    case Mode::A_BlackClearStatic: return "a";
    case Mode::B_SingleBufferLock: return "b";
    case Mode::C_RedBlueSwitch:    return "c";
    case Mode::D_CrcCheck:         return "d";
    }
    return "?";
}

void fill_solid(std::uint16_t* dst, std::size_t words, std::uint16_t rgb565) {
    for (std::size_t i = 0; i < words; ++i) dst[i] = rgb565;
}

namespace {
constexpr std::uint32_t kCrcPoly = 0xEDB88320u;
}

std::uint32_t crc32(const void* data, std::size_t bytes) {
    const std::uint8_t* p = static_cast<const std::uint8_t*>(data);
    std::uint32_t crc = 0xFFFFFFFFu;
    for (std::size_t i = 0; i < bytes; ++i) {
        crc ^= p[i];
        for (int k = 0; k < 8; ++k) {
            crc = (crc >> 1) ^ ((crc & 1u) ? kCrcPoly : 0u);
        }
    }
    return crc ^ 0xFFFFFFFFu;
}

std::uint32_t crc32_u16(const std::uint16_t* words, std::size_t count) {
    // CRC over the raw in-memory byte stream (low byte first) so the value is
    // identical between a board mapping and an x86-64 host buffer.
    return crc32(words, count * sizeof(std::uint16_t));
}

} // namespace ddx
