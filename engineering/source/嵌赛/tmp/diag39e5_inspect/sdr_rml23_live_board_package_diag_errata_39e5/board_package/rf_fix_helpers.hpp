#pragma once

// rf_fix_helpers.hpp -- M29 Phase F5 RF LO/BW fix helpers (header-only,
// host-testable).  Extracted from board_gate9_full_chain_rml23.cpp so the RF
// fix's CLI-presence and fail-closed read-back tolerance logic can be asserted
// offline without a device.
//
//   opt_present        -- does an RF override appear on the command line?
//   rf_readback_close  -- is a read-back value within the fail-closed tolerance?
//   rf_ll/rf_d/rf_i/rf_s -- safe read-backs ("ERR" on throw, never fail the gate).
//
// iCraft-free, libiio-free (the rf_* read-backs take only the abstract
// pluto::Device).

#include "../sdr_adapter/pluto_device.hpp"

#include <cmath>
#include <string>

namespace rf_fix {

// Presence check for an optional RF parameter (mirrors board::get_opt's matching
// but never throws): true if `name` appears as `--name=value` or as a bare
// `--name` token.  A malformed bare `--name` (no value) is still rejected by the
// later board::opt_u64/opt_d (which throw via get_opt).
inline bool opt_present(int argc, char** argv, const char* name) {
    const std::string eq = std::string(name) + "=";
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a.compare(0, eq.size(), eq) == 0) return true;
        if (a == name) return true;
    }
    return false;
}

// Fail-closed read-back tolerance: an explicitly requested RF parameter must come
// back within `abs_tol` Hz OR `rel_frac` of the request.  Tolerances account for
// AD936x rf_bandwidth quantisation and LO step rounding, but still catch real
// failures (dropped write, read-back 0, wrong band).
inline bool rf_readback_close(long long got, long long want, long long abs_tol,
                              double rel_frac) {
    if (want == 0) return got == 0;
    const long long d = got >= want ? got - want : want - got;
    const long long rel = static_cast<long long>(
        std::llround(static_cast<double>(want >= 0 ? want : -want) * rel_frac));
    const long long tol = abs_tol > rel ? abs_tol : rel;
    return d <= tol;
}

// Safe read-backs for the RF startup/diag log: return "ERR" instead of throwing,
// so a diagnostic read can never fail the gate (the gate is gated by the earlier
// fail-closed writes, not by a log read).
inline std::string rf_ll(pluto::Device& dev, long long (pluto::Device::*fn)() const) {
    try { return std::to_string((dev.*fn)()); } catch (...) { return "ERR"; }
}
inline std::string rf_d(pluto::Device& dev, double (pluto::Device::*fn)() const) {
    try { return std::to_string((dev.*fn)()); } catch (...) { return "ERR"; }
}
inline std::string rf_i(pluto::Device& dev, int (pluto::Device::*fn)() const) {
    try { return std::to_string((dev.*fn)()); } catch (...) { return "ERR"; }
}
inline std::string rf_s(pluto::Device& dev, std::string (pluto::Device::*fn)() const) {
    try { return (dev.*fn)(); } catch (...) { return "ERR"; }
}

}  // namespace rf_fix
