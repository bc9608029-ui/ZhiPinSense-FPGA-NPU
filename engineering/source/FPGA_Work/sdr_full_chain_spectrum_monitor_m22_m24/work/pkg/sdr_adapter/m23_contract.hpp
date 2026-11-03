#pragma once

// m23_contract.hpp -- M23 P0 (spectrum-monitor signal layer) frozen constants.
//
// M23 P0 adds, OFFLINE and isolated from the Gate 9/10 main chain, three signal
// capabilities on top of the M22 runtime-fix baseline:
//   D  signal presence  (reuses sdr::SignalPresence, composed into a verdict here)
//   H  parameter estimation (center freq / power-RMS / SNR / occupied BW / CFO)
//   C  switchable OOD-U interface (default OFF -> byte-identical to M22 argmax)
//
// The four verdict strings below are STRICTLY separated -- this is the point of
// the milestone.  Nothing else may emit these exact tokens, and each frame maps
// to exactly one of them:
//
//   NO_SIGNAL             nothing confirmed present (below the presence gate)
//   SIGNAL_PRESENT        a known 12-class argmax is reported
//   UNKNOWN_EXPERIMENTAL  a signal is present but the EXPERIMENTAL OOD-U rejects it
//   ERROR                 capture fault / NaN-Inf input / non-finite logits
//
// iCraft-free, header-only.  Never touches RTL/XDC/bitstream, the 12-class model,
// the frozen label order, the input preprocessing, or the UI main layout.

#include <cstdint>
#include <string>

namespace m23 {

// The four mutually-exclusive per-frame verdict tokens.
inline constexpr const char* NO_SIGNAL = "NO_SIGNAL";
inline constexpr const char* SIGNAL_PRESENT = "SIGNAL_PRESENT";
inline constexpr const char* UNKNOWN_EXPERIMENTAL = "UNKNOWN_EXPERIMENTAL";
inline constexpr const char* ERROR = "ERROR";

// The frozen 12-class NPU model identity.  OOD-U is meaningful only for THIS
// model; any other model SHA must fail-closed (see load_ood_u_manifest).
inline constexpr const char* OOD_MODEL_SHA256 =
    "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c";

// OOD-U is EXPERIMENTAL: on the frozen model the near/far rejection is
// ~6.03%/10.33%, so it must never be presented as a reliable UNKNOWN gate.
// The switchable interface is therefore OFF by default (m23_ood_u_switch.hpp),
// and any rejection is labelled UNKNOWN_EXPERIMENTAL, never plain UNKNOWN.

// Sentinel threshold that represents "OOD-U wired but disabled": the frozen
// score method is logit_margin = -(top1 - top2) <= 0, so a threshold of +1e30
// can never be exceeded and the reject branch can never fire.  This is the
// "safe boundary" from the integration baseline audit: even with the interface
// switched ON, a +1e30 threshold reproduces the plain M22 argmax exactly.
inline constexpr double OOD_DISABLED_THRESHOLD = 1e30;

// REFERENCE ONLY: the M20-frozen logit_margin threshold at id_accept_99.  The
// switchable interface reads the threshold from the manifest (never from this
// constant); this value exists solely so the host tests and integration notes
// can state the frozen operating point without a magic number.  On the frozen
// model the near/far rejection is ~6.03%/10.33% -- experimental, not reliable.
inline constexpr double OOD_U_FROZEN_THRESHOLD_LOGIT_MARGIN = -0.15274411201477073;

// Frame age (in frame ids) beyond which a parameter estimate is considered
// STALE and rendered as "--" rather than a number.  Ties directly to the
// presence gate: parameter values are only meaningful while SIGNAL_PRESENT is
// confirmed, so once the signal drops the params age out after this many frames.
inline constexpr std::uint64_t PARAM_STALE_AFTER_FRAMES = 5;

}  // namespace m23
