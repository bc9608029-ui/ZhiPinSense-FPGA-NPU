#pragma once

// gate9_phase.hpp -- the Gate 9 --phase CLI dispatch table, shared with the host
// test so the phase surface is tested without the NPU / libiio.
//
// Adding a phase (e.g. "ambient", the rx-only no-signal integration test) must
// update BOTH this predicate and the run_* dispatch in
// board_gate9_full_chain_12class.cpp::main().

#include <string>

namespace gate9 {

inline bool valid_phase(const std::string& p) {
    return p == "offline" || p == "digital" || p == "rf" || p == "ambient";
}

}  // namespace gate9
