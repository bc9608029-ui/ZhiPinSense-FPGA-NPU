#pragma once

// iq_external_rf_frame.hpp -- Route G fix10: the AIR-INTERFACE frame structure
// shared VERBATIM by the PC-side TX tool (tools/pluto_external_tx.cpp) and the
// board-side RX runner (iq_external_rf_rx.hpp).  Two independent Plutos on
// independent clocks transmit / receive this frame over a 50-ohm coax, so the RX
// must recover unknown CFO / SRO / frame start / phase -- the frame is designed so
// every one of those is recoverable from the CATEGORY-INDEPENDENT parts (preamble,
// header sync word, tail preamble), never from the payload label.
//
// Frame layout at 2.56 MSPS (== the D2 payload rate, kPayloadComplex == 53760):
//
//   [silence 8192][preamble A 1024][preamble A 1024][header 960][guard 2048]
//     [payload 53760][guard 2048][tail preamble 1024][silence 8192]
//
//   * Preamble A: a fixed 16-sample constant-envelope CAZAC unit
//       u[k] = exp(j*pi*k*(k+1)/16), k = 0..15
//     repeated 64x (1024 samples), then the whole 1024 block repeated once more
//     (2048 total).  The lag-16 self-similarity is exactly what the S&C coarse-CFO
//     estimator needs (unambiguous +/-80 kHz at fs = 2.56 MSPS), and it is
//     category-independent with a fixed seed.
//   * Header (960 samples): 128 known BPSK sync symbols + 104 info bits x R=8
//     repetition BPSK (b -> 2b-1, each bit repeated 8 times).  The 104 bits are:
//         version 8b | run_id 16b | index 16b | payload_count 16b |
//         sha_short 32b (first 4 bytes of the payload ci16 SHA-256) | crc16 16b
//     CRC-16-CCITT (0x1021, init 0xFFFF, MSB-first) covers the first 88 bits.
//   * Tail preamble: the 1024-sample preamble A (single copy), used for tail
//     re-synchronization and the SRO estimate.
//   * Guard: 2048 samples of silence isolating header / payload / tail and
//     absorbing the timing jitter.
//
// iCraft-free and libiio-free: it compiles identically on the host and the board.

#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace extrf {
namespace frame {

constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr std::uint64_t kFs = 2560000;           // sample rate (== D2 payload rate)

// ---- structure sizes (complex samples) -------------------------------------
constexpr std::size_t kPreambleUnitComplex = 16;  // CAZAC unit length
constexpr std::size_t kPreambleComplex = 1024;    // 64 units, one preamble A
constexpr std::size_t kPreambleCount = 2;         // preamble A is sent twice
constexpr std::size_t kHeaderSyncComplex = 128;   // known BPSK sync word
constexpr std::size_t kHeaderInfoBits = 104;      // version+run_id+index+count+sha+crc
constexpr std::size_t kHeaderRepCode = 8;         // repetition code rate R
constexpr std::size_t kHeaderInfoSymbols = kHeaderInfoBits * kHeaderRepCode;  // 832
constexpr std::size_t kHeaderComplex = kHeaderSyncComplex + kHeaderInfoSymbols;  // 960
constexpr std::size_t kGuardComplex = 2048;
constexpr std::size_t kPayloadComplex = 53760;    // D2 AC-only payload
constexpr std::size_t kTailComplex = 1024;
constexpr std::size_t kSilenceComplex = 8192;

// ---- positions relative to frame_start (preamble A #1 sample 0) -------------
constexpr std::size_t kHeaderStart = kPreambleCount * kPreambleComplex;          // 2048
constexpr std::size_t kPayloadStart = kHeaderStart + kHeaderComplex + kGuardComplex;  // 5056
constexpr std::size_t kTailStart = kPayloadStart + kPayloadComplex + kGuardComplex;   // 60864

// Total frame length (leading silence .. trailing silence).
constexpr std::size_t kTotalFrameComplex =
    kSilenceComplex + kTailStart + kTailComplex + kSilenceComplex;   // 78272

constexpr double kFrameAmp = 2048.0;   // preamble/sync/info int16 amplitude (12-bit FS)
constexpr std::uint8_t kFrameVersion = 1;

// CFO/SRO estimator safety bounds (documented; never a PASS gate).
constexpr double kCfoUnambiguousHz = kFs / (2.0 * kPreambleUnitComplex);  // +/-80 kHz

// ---------------------------------------------------------------------------
// Header fields (104 info bits).  Category-independent: none of these encode a
// modulation label.
// ---------------------------------------------------------------------------
struct HeaderFields {
    bool valid = false;
    std::uint8_t version = kFrameVersion;
    std::uint16_t run_id = 0;        // TX run counter (informational)
    std::uint16_t index = 0;         // sample_index from the D2 manifest
    std::uint16_t payload_count = 0; // complex samples in the payload (53760)
    std::uint32_t sha_short = 0;     // first 4 bytes (BE) of the payload ci16 SHA-256
    std::uint16_t crc16 = 0;         // CRC-16-CCITT over the first 88 bits
    bool crc_ok = false;             // decode-only: crc16 matches the recomputed CRC
};

// First 4 bytes (big-endian) of a 64-hex SHA-256 as a uint32.  Fail-closed on a
// non-hex / too-short digest.
inline std::uint32_t sha_short_from_hex(const std::string& sha256_hex) {
    if (sha256_hex.size() < 8)
        throw std::runtime_error("extrf-frame: sha256 too short for sha_short");
    std::uint32_t v = 0;
    for (int i = 0; i < 8; ++i) {
        const char c = sha256_hex[static_cast<std::size_t>(i)];
        std::uint32_t d;
        if (c >= '0' && c <= '9') d = static_cast<std::uint32_t>(c - '0');
        else if (c >= 'a' && c <= 'f') d = static_cast<std::uint32_t>(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') d = static_cast<std::uint32_t>(c - 'A' + 10);
        else throw std::runtime_error("extrf-frame: non-hex in sha_short source");
        v = (v << 4) | d;
    }
    return v;
}

// ---------------------------------------------------------------------------
// CRC-16-CCITT (polynomial 0x1021, init 0xFFFF, MSB-first, no reflection).
// ---------------------------------------------------------------------------
inline std::uint16_t crc16_ccitt(const std::uint8_t* data, std::size_t n) {
    std::uint16_t crc = 0xFFFFu;
    for (std::size_t i = 0; i < n; ++i) {
        crc ^= static_cast<std::uint16_t>(data[i]) << 8;
        for (int b = 0; b < 8; ++b)
            crc = (crc & 0x8000u) ? static_cast<std::uint16_t>((crc << 1) ^ 0x1021u)
                                  : static_cast<std::uint16_t>(crc << 1);
    }
    return crc;
}

// Compute the CRC over the first 88 bits (11 bytes) of a packed header and store
// it in the trailing crc16 field.
inline void attach_crc16(std::uint8_t bits[13]) {
    const std::uint16_t c = crc16_ccitt(bits, 11);
    bits[11] = static_cast<std::uint8_t>(c >> 8);
    bits[12] = static_cast<std::uint8_t>(c & 0xFFu);
}

// Pack the 104 header bits into 13 bytes (big-endian / MSB-first bit order).
inline void pack_header_bits(const HeaderFields& f, std::uint8_t bits[13]) {
    bits[0] = f.version;
    bits[1] = static_cast<std::uint8_t>(f.run_id >> 8);
    bits[2] = static_cast<std::uint8_t>(f.run_id & 0xFFu);
    bits[3] = static_cast<std::uint8_t>(f.index >> 8);
    bits[4] = static_cast<std::uint8_t>(f.index & 0xFFu);
    bits[5] = static_cast<std::uint8_t>(f.payload_count >> 8);
    bits[6] = static_cast<std::uint8_t>(f.payload_count & 0xFFu);
    bits[7] = static_cast<std::uint8_t>(f.sha_short >> 24);
    bits[8] = static_cast<std::uint8_t>((f.sha_short >> 16) & 0xFFu);
    bits[9] = static_cast<std::uint8_t>((f.sha_short >> 8) & 0xFFu);
    bits[10] = static_cast<std::uint8_t>(f.sha_short & 0xFFu);
    bits[11] = static_cast<std::uint8_t>(f.crc16 >> 8);
    bits[12] = static_cast<std::uint8_t>(f.crc16 & 0xFFu);
}

// Compute the CRC over the first 88 header bits and store it in fields.crc16, so a
// receiver can verify the header.  Both the TX tool and the RX-side known-answer
// reference builders MUST call this before build_frame() (build_frame packs the
// header verbatim and does NOT auto-attach).
inline void attach_header_crc(HeaderFields& f) {
    std::uint8_t bits[13];
    pack_header_bits(f, bits);
    attach_crc16(bits);
    f.crc16 = static_cast<std::uint16_t>((static_cast<std::uint16_t>(bits[11]) << 8) |
                                         bits[12]);
}

inline void unpack_header_bits(const std::uint8_t bits[13], HeaderFields& f) {
    f.version = bits[0];
    f.run_id = static_cast<std::uint16_t>((static_cast<std::uint16_t>(bits[1]) << 8) |
                                          bits[2]);
    f.index = static_cast<std::uint16_t>((static_cast<std::uint16_t>(bits[3]) << 8) |
                                         bits[4]);
    f.payload_count = static_cast<std::uint16_t>((static_cast<std::uint16_t>(bits[5]) << 8) |
                                                 bits[6]);
    f.sha_short = (static_cast<std::uint32_t>(bits[7]) << 24) |
                  (static_cast<std::uint32_t>(bits[8]) << 16) |
                  (static_cast<std::uint32_t>(bits[9]) << 8) |
                  static_cast<std::uint32_t>(bits[10]);
    f.crc16 = static_cast<std::uint16_t>((static_cast<std::uint16_t>(bits[11]) << 8) |
                                         bits[12]);
}

// ---------------------------------------------------------------------------
// Known sequences (deterministic, category-independent).
// ---------------------------------------------------------------------------

// Preamble A (1024 samples): the 16-sample CAZAC unit repeated 64x, interleaved
// int16 [I0,Q0,...] at amplitude kFrameAmp.
inline std::vector<std::int16_t> preamble_a() {
    std::vector<std::int16_t> out(kPreambleComplex * 2);
    for (std::size_t r = 0; r < kPreambleComplex; ++r) {
        const int k = static_cast<int>(r % kPreambleUnitComplex);
        const double ph = kPi * k * (k + 1) / static_cast<double>(kPreambleUnitComplex);
        out[r * 2 + 0] = static_cast<std::int16_t>(std::lround(kFrameAmp * std::cos(ph)));
        out[r * 2 + 1] = static_cast<std::int16_t>(std::lround(kFrameAmp * std::sin(ph)));
    }
    return out;
}

// Tail preamble = the single 1024-sample preamble A.
inline std::vector<std::int16_t> tail_preamble() {
    return preamble_a();
}

// 128 known BPSK sync symbols (+1/-1), deterministic via a fixed xorshift seed.
inline std::vector<std::int8_t> header_sync_symbols() {
    std::vector<std::int8_t> s(kHeaderSyncComplex);
    std::uint32_t x = 0x1234ABCDu;
    for (std::size_t i = 0; i < kHeaderSyncComplex; ++i) {
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
        s[i] = (x & 1u) ? 1 : -1;
    }
    return s;
}

// The known sync word as interleaved int16 (BPSK: Q == 0).
inline std::vector<std::int16_t> header_sync_word() {
    const std::vector<std::int8_t> s = header_sync_symbols();
    std::vector<std::int16_t> out(kHeaderSyncComplex * 2);
    for (std::size_t i = 0; i < kHeaderSyncComplex; ++i) {
        out[i * 2 + 0] = static_cast<std::int16_t>(
            std::lround(static_cast<double>(s[i]) * kFrameAmp));
        out[i * 2 + 1] = 0;
    }
    return out;
}

// ---------------------------------------------------------------------------
// Header encode / decode.
// ---------------------------------------------------------------------------

// Encode the full 960-sample header (128 sync + 832 info) as interleaved int16.
inline std::vector<std::int16_t> encode_header(const HeaderFields& f) {
    std::uint8_t bits[13];
    pack_header_bits(f, bits);
    std::vector<std::int16_t> out(kHeaderComplex * 2, 0);
    const std::vector<std::int8_t> sync = header_sync_symbols();
    std::size_t pos = 0;
    for (std::size_t i = 0; i < kHeaderSyncComplex; ++i) {
        out[pos * 2 + 0] = static_cast<std::int16_t>(
            std::lround(static_cast<double>(sync[i]) * kFrameAmp));
        out[pos * 2 + 1] = 0;
        ++pos;
    }
    for (int by = 0; by < 13; ++by) {
        for (int b = 7; b >= 0; --b) {
            const int bit = (bits[by] >> b) & 1;
            const std::int8_t s = bit ? 1 : -1;
            for (std::size_t r = 0; r < kHeaderRepCode; ++r) {
                out[pos * 2 + 0] = static_cast<std::int16_t>(
                    std::lround(static_cast<double>(s) * kFrameAmp));
                out[pos * 2 + 1] = 0;
                ++pos;
            }
        }
    }
    if (pos != kHeaderComplex)
        throw std::runtime_error("extrf-frame: header encode length mismatch");
    return out;
}

// Decode 832 info symbols (+1/-1) into HeaderFields, recomputing + checking the CRC.
inline HeaderFields decode_header(const std::vector<std::int8_t>& info_symbols) {
    HeaderFields f;
    if (info_symbols.size() != kHeaderInfoSymbols) return f;
    std::uint8_t bits[13] = {0};
    std::size_t bit_idx = 0;
    for (int by = 0; by < 13; ++by) {
        for (int b = 7; b >= 0; --b) {
            int acc = 0;
            for (std::size_t r = 0; r < kHeaderRepCode; ++r)
                acc += info_symbols[bit_idx * kHeaderRepCode + r];
            if (acc > 0) bits[by] |= static_cast<std::uint8_t>(1u << b);
            ++bit_idx;
        }
    }
    unpack_header_bits(bits, f);
    const std::uint16_t recomputed = crc16_ccitt(bits, 11);
    f.crc_ok = (recomputed == f.crc16);
    f.valid = true;
    return f;
}

// ---------------------------------------------------------------------------
// Full frame build (TX side + the RX-side known-answer reference).
// ---------------------------------------------------------------------------
inline std::vector<std::int16_t> build_frame(
        const std::vector<std::int16_t>& payload_iq, const HeaderFields& fields) {
    if (payload_iq.size() != kPayloadComplex * 2)
        throw std::runtime_error("extrf-frame: payload must be exactly " +
                                 std::to_string(kPayloadComplex) + " complex samples");
    std::vector<std::int16_t> f;
    f.reserve(kTotalFrameComplex * 2);
    f.insert(f.end(), kSilenceComplex * 2, 0);
    const std::vector<std::int16_t> pre = preamble_a();
    f.insert(f.end(), pre.begin(), pre.end());
    f.insert(f.end(), pre.begin(), pre.end());
    const std::vector<std::int16_t> hdr = encode_header(fields);
    f.insert(f.end(), hdr.begin(), hdr.end());
    f.insert(f.end(), kGuardComplex * 2, 0);
    f.insert(f.end(), payload_iq.begin(), payload_iq.end());
    f.insert(f.end(), kGuardComplex * 2, 0);
    const std::vector<std::int16_t> tail = tail_preamble();
    f.insert(f.end(), tail.begin(), tail.end());
    f.insert(f.end(), kSilenceComplex * 2, 0);
    if (f.size() != kTotalFrameComplex * 2)
        throw std::runtime_error("extrf-frame: built frame length mismatch");
    return f;
}

}  // namespace frame
}  // namespace extrf
