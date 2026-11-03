#pragma once

// iq_rf_per_frame_recovery.hpp -- Route F fix9r2 Task R5: BACKWARD-COMPATIBLE SHIM.
//
// The fix9r1 per-file recovery lived here (a preamble search bounded to the first
// 4096 samples).  fix9r2 replaces its estimator with the SHARED recovery core in
// iq_rf_sync_recovery.hpp (full-capture search + 2-period capture + typed valid
// semantics).  This file now only re-exports that core so every existing caller
// (transfer, runner, host tests) keeps the `iqrfrec::` names it already uses while
// getting the fixed estimator.
//
// Do NOT add estimator logic here: it belongs in iq_rf_sync_recovery.hpp (the one
// core that fix10 must also reuse -- §1 "fix10 必须直接复用 fix9r2 板端验证的公共
// 恢复核心").

#include "iq_rf_sync_recovery.hpp"

// The namespace iqrfrec (PerFileRecovery, estimate, apply, recover_payload_int16,
// Failure, EstimateConfig) is fully defined by the included core.
