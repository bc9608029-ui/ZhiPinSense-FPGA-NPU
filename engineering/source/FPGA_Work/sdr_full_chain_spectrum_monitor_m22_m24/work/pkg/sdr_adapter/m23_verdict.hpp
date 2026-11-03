#pragma once

// m23_verdict.hpp -- the strict four-way per-frame verdict (M23 P0).
//
// Composes the presence state machine (sdr::SignalPresence) with the switchable
// OOD-U result into exactly one of NO_SIGNAL / SIGNAL_PRESENT /
// UNKNOWN_EXPERIMENTAL / ERROR.  The separation is the milestone's core
// invariant, and nothing else may emit these tokens (m23_contract.hpp).
//
// Mapping (single source of truth):
//   sdr::PresenceState::Invalid                                    -> ERROR
//   sdr::PresenceState::SignalPresent + OOD-U reject               -> UNKNOWN_EXPERIMENTAL
//   sdr::PresenceState::SignalPresent + OOD-U error                -> ERROR
//   sdr::PresenceState::SignalPresent                              -> SIGNAL_PRESENT
//   NoSignal / Acquiring / SignalLost (any)                        -> NO_SIGNAL
//
// Acquiring and SignalLost are deliberately collapsed into NO_SIGNAL: a frame is
// classified only once presence is CONFIRMED, so the intermediate/lost states
// never emit a class.  This keeps the four-way verdict total and exclusive.
//
// iCraft-free, header-only.

#include "m23_contract.hpp"
#include "signal_presence.hpp"

namespace m23 {

enum class Verdict {
    NoSignal = 0,
    SignalPresent = 1,
    UnknownExperimental = 2,
    Error = 3,
};

inline const char* verdict_name(Verdict v) {
    switch (v) {
        case Verdict::NoSignal: return NO_SIGNAL;
        case Verdict::SignalPresent: return SIGNAL_PRESENT;
        case Verdict::UnknownExperimental: return UNKNOWN_EXPERIMENTAL;
        case Verdict::Error: return ERROR;
    }
    return ERROR;
}

// `ood_enabled` / `ood_rejected` / `ood_error` come from M23OodSwitch (the
// switchable OOD-U interface).  When the switch is disabled, all three are
// false and SIGNAL_PRESENT is returned for every confirmed present frame --
// byte-identical to the M22 argmax path.
inline Verdict compose(sdr::PresenceState presence, bool ood_enabled,
                       bool ood_rejected, bool ood_error) {
    if (presence == sdr::PresenceState::Invalid) return Verdict::Error;
    if (presence == sdr::PresenceState::SignalPresent) {
        if (ood_enabled && ood_error) return Verdict::Error;
        if (ood_enabled && ood_rejected) return Verdict::UnknownExperimental;
        return Verdict::SignalPresent;
    }
    return Verdict::NoSignal;
}

}  // namespace m23
