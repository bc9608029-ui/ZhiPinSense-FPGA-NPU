#pragma once

// rx_format.hpp -- RX IQ data-format contract for the ADALM-Pluto / AD9364 path.
//
// This is the STRUCTURED contract for how raw RX samples arrive from the device,
// so the resampler + receiver_scale + NCO chain never guesses byte layout.  The
// normative text is contracts/rx_iq_format_contract.md; this header is its
// executable form (used by rx_format unit tests and by the board programs to
// print the effective layout they are about to interpret).
//
// Fields that are NOT yet verified against hardware are marked `verified=false`
// and default to the canonical ADI ad9361-iiostream layout; the board programs
// MUST NOT override them silently -- they only confirm/report them.
//
// iCraft-free and header-only.

#include <cstddef>
#include <cstdint>
#include <string>

namespace sdr {

struct RxFormat {
    // How I and Q are arranged in the sample stream.
    bool interleaved = true;      // [I0,Q0,I1,Q1,...] vs [I0..In, Q0..Qn]
    std::size_t q_offset = 1;     // int16 slots from I to its Q (interleaved=1)

    // Container vs effective precision.  AD9364 delivers 12-bit samples inside a
    // 16-bit signed container.  Whether the 12 bits are left- or right-justified
    // in the int16, and how the top 4 bits are sign-extended, is measured on
    // hardware (TBD) -- do NOT assume.
    std::size_t container_bits = 16;
    std::size_t effective_bits = 12;   // TBD: confirm on hardware
    bool left_justified = false;       // false = right-justified (LSB-aligned)
    bool sign_extended = true;         // top bits replicate the sign bit

    bool little_endian = true;         // int16 byte order
    bool two_channel = true;           // I and Q are separate AD9361 channels

    // Which of these were actually confirmed on hardware (vs the ADI default).
    bool verified = false;
};

// The canonical layout this code path assumes (matches pluto_libiio.cpp's
// interleaved int16 read path and libiio's I/Q channel ordering).
inline RxFormat canonical_rx_format() {
    RxFormat f;
    return f;
}

// Human-readable one-line description, e.g.
//   "interleaved int16 little-endian, 12-bit right-justified sign-extended"
inline std::string describe(const RxFormat& f) {
    std::string s = f.interleaved ? "interleaved" : "split";
    s += f.little_endian ? " int16 LE" : " int16 BE";
    s += ", " + std::to_string(f.effective_bits) + "-bit ";
    s += f.left_justified ? "left-justified" : "right-justified";
    s += f.sign_extended ? " sign-extended" : " zero-padded";
    s += f.verified ? " (verified)" : " (ADI default, unverified)";
    return s;
}

// Number of int16 slots consumed per complex sample (2 when interleaved I/Q).
inline std::size_t slots_per_complex(const RxFormat& f) {
    return f.two_channel ? 2 : 1;
}

// bytes per complex sample in the container.
inline std::size_t bytes_per_complex(const RxFormat& f) {
    return slots_per_complex(f) * (f.container_bits / 8);
}

}  // namespace sdr
