// sample_rate_negotiate.cpp -- implementation.

#include "sample_rate_negotiate.hpp"

#include "fir_coeffs.h"

#include <cstdio>

namespace sdr {

namespace {

// Human-readable rate label, e.g. 2560000 -> "2.56MHz", 3840000 -> "3.84MHz".
std::string hz_label(std::uint64_t hz) {
    char buf[32];
    if (hz % 1000 == 0) {
        std::snprintf(buf, sizeof(buf), "%.3gMHz",
                      static_cast<double>(hz) / 1000000.0);
    } else {
        std::snprintf(buf, sizeof(buf), "%lluHz",
                      static_cast<unsigned long long>(hz));
    }
    return std::string(buf);
}

}  // namespace

std::string RateNegotiation::report() const {
    char buf[256];
    std::snprintf(buf, sizeof(buf),
                  "requested=%llu actual=%llu model=%llu ratio=%u/%u",
                  static_cast<unsigned long long>(requested_hz),
                  static_cast<unsigned long long>(actual_hz),
                  static_cast<unsigned long long>(fs_out_hz), down, up);
    std::string s = buf;
    if (!ok && !reason.empty()) s += " (" + reason + ")";
    return s;
}

std::vector<RateCandidate> default_rate_candidates() {
    std::vector<RateCandidate> out;
    for (std::size_t i = 0; i < sdr::kFirSpecCount; ++i) {
        const sdr::FirSpec& spec = sdr::kFirSpecs[i];
        RateCandidate c;
        c.fs_in_hz = spec.fs_in_hz;
        c.up = spec.up;
        c.down = spec.down;
        c.name = hz_label(spec.fs_in_hz);
        out.push_back(c);
    }
    return out;
}

RateNegotiation negotiate_sample_rate(pluto::Device& dev,
                                      const std::vector<RateCandidate>& cands,
                                      std::uint64_t fs_out_hz) {
    RateNegotiation r;
    r.fs_out_hz = fs_out_hz;

    for (const RateCandidate& c : cands) {
        // Exact integer-ratio pre-check: fs_in * up == fs_out * down.
        if (c.up == 0 || c.down == 0 ||
            c.fs_in_hz * c.up != fs_out_hz * c.down) {
            r.reason = c.name + ": non-integer ratio";
            continue;
        }

        const long long actual =
            dev.set_sample_rate(static_cast<long long>(c.fs_in_hz));
        r.requested_hz = c.fs_in_hz;
        r.actual_hz = static_cast<std::uint64_t>(actual);
        r.up = c.up;
        r.down = c.down;

        if (actual == static_cast<long long>(c.fs_in_hz)) {
            r.ok = true;
            r.reason.clear();
            return r;
        }
        r.reason = c.name + ": write-readback mismatch";
    }

    r.ok = false;
    if (r.reason.empty()) r.reason = "no candidates";
    return r;
}

}  // namespace sdr
