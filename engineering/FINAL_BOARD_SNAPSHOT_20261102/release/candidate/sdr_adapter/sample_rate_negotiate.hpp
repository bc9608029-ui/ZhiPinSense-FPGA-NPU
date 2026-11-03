#pragma once

// sample_rate_negotiate.hpp -- exact, write-readback sample-rate negotiation.
//
// The board must land the AD9364 on a sample rate that converts to the 128 kHz
// model rate by an INTEGER ratio (first choice 2.56 MHz -> x20 decimation;
// fallback 3.84 MHz -> x30).  A candidate is only accepted when the write
// round-trips EXACTLY (read-back == requested) AND the integer ratio holds
// exactly.  Nothing is silently approximated.
//
// iCraft-free.

#include "pluto_device.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace sdr {

// One candidate: fs_in at ratio up/down to fs_out (integer decimation: up=1).
struct RateCandidate {
    std::uint64_t fs_in_hz = 0;
    std::uint32_t up = 1;
    std::uint32_t down = 1;
    std::string name;   // human-readable, e.g. "2.56MHz"
};

// Result of negotiation.  On success `ok=true`, `actual_hz==requested_hz`, and
// the ratio `down/up` is exact.  On failure `ok=false` and `reason` names the
// last candidate and why it was rejected.
struct RateNegotiation {
    bool ok = false;
    std::uint64_t requested_hz = 0;
    std::uint64_t actual_hz = 0;
    std::uint64_t fs_out_hz = 128000;
    std::uint32_t up = 1;
    std::uint32_t down = 1;
    std::string reason;

    std::string report() const;
};

// Try candidates in order; return the first that round-trips exactly.
RateNegotiation negotiate_sample_rate(pluto::Device& dev,
                                      const std::vector<RateCandidate>& cands,
                                      std::uint64_t fs_out_hz = 128000);

// Default chain from fir_coeffs.h: 2.56 MHz (x20) then 3.84 MHz (x30).
// 30.72 MHz x240 is deliberately excluded (single-stage FIR is numerically
// unstable; see docs/RESAMPLER_DESIGN.md) and is a PC-only measurement record.
std::vector<RateCandidate> default_rate_candidates();

}  // namespace sdr
