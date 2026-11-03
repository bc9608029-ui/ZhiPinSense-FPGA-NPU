#pragma once

// gate9_phase.hpp -- the Gate 9 --phase CLI dispatch table, shared with the host
// test so the phase surface is tested without the NPU / libiio.
//
// Adding a phase (e.g. "ambient", the rx-only no-signal integration test, or
// "live-rx", the presence-gated external RX classifier) must update BOTH this
// predicate and the run_* dispatch in
// board_gate9_full_chain_rml23.cpp::main().

#include <string>

namespace gate9 {

inline bool valid_phase(const std::string& p) {
    return p == "offline" || p == "digital" || p == "rf" || p == "ambient" ||
           p == "live-rx" || p == "synthetic-iq" || p == "iq-digital-loopback" ||
           p == "iq-digital-loopback-sweep" || p == "iq-rf-loopback" ||
           p == "iq-rf-loopback-level-sweep" || p == "iq-rf-loopback-ab" ||
           p == "iq-rf-loopback-23class" || p == "iq-rf-loopback-23class-fix9r";
}

}  // namespace gate9
