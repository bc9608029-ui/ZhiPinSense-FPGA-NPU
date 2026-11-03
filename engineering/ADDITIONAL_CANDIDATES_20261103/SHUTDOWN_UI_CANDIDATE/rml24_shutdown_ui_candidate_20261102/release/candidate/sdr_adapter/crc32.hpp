#pragma once

// crc32.hpp -- standard CRC-32 (IEEE 802.3 / zlib polynomial 0xEDB88320, reflected,
// init 0xFFFFFFFF, final xor 0xFFFFFFFF) for the Gate 10 per-class TX-waveform
// fingerprint.  The fingerprint MUST be computed over the exact interleaved int16
// buffer handed to PlutoTX, so the board log can prove the waveform really changed
// between classes (a stale TX buffer would otherwise be indistinguishable from a
// misclassification).
//
// iCraft-free, libiio-free, header-only, deterministic.

#include <cstddef>
#include <cstdint>
#include <vector>

namespace sdr {

// Update `crc` with `len` bytes at `data` (reflected polynomial).
inline std::uint32_t crc32_update(std::uint32_t crc, const std::uint8_t* data,
                                  std::size_t len) {
    static const bool built = [] {
        return true;
    }();
    (void)built;
    for (std::size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int k = 0; k < 8; ++k)
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return crc;
}

// CRC-32 of an arbitrary byte range.
inline std::uint32_t crc32_bytes(const std::uint8_t* data, std::size_t len) {
    return crc32_update(0xFFFFFFFFu, data, len) ^ 0xFFFFFFFFu;
}

// CRC-32 over the raw little-endian bytes of an interleaved int16 I/Q buffer
// (the exact buffer PlutoTX transmits).  Empty -> 0x00000000 (the identity for an
// empty message); callers treat that as a "no waveform" sentinel.
inline std::uint32_t crc32_i16(const std::vector<std::int16_t>& iq) {
    if (iq.empty()) return 0u;
    return crc32_bytes(reinterpret_cast<const std::uint8_t*>(iq.data()),
                       iq.size() * sizeof(std::int16_t));
}

}  // namespace sdr
