#pragma once

// Three-stage pipeline skeleton + error-recovery policy for the non-model
// system layer.  This file owns the POLICY and the ACCOUNTING only; the actual
// hardware actions (PL-DDR register writes, Device::reset(1), Session::forward)
// live in board_package/continuous_joint_stress.cpp and are exercised on the
// board.  Keeping policy here (iCraft-free) lets the recovery decision table be
// unit-tested on the host.
//
// Data-flow state machine (see REPORT.md section B for the full ownership
// contract):
//
//   Capture  --source--> Fpga  --tensor--> Npu  --logits--> Result
//       ^                                                        |
//       +---------------------- next cycle ----------------------+
//
//   Capture : one 1024-sample frame from an iq::Source, passed through the
//             iq::SequenceMonitor (drop/overflow/duplicate/reorder/discontinuity).
//   Fpga    : 19 frames -> PL DDR -> Mandatory Core -> 97280 B tensor readback.
//   Npu     : frames 7..18, Device::reset(1) re-arm, argmax vs reference.
//   Result  : verdict + per-stage latency, emitted via ui_report.hpp.
//
// Buffer ownership (see REPORT.md section B):
//   * capture buffer  -- SDR adapter writes (SdrIqSource later; FileIqSource /
//                        SyntheticIqSource read-only now).
//   * FPGA buffer     -- Linux MemChunk (PL DDR), host-owned, address handed to
//                        PL via registers each cycle.
//   * result buffer   -- per-frame verdicts consumed immediately; only the
//                        aggregates survive across cycles.
// Backpressure: a short frame is never fed to FPGA (the cycle is aborted);
// a not-ready NPU output is a timeout, never a dropped/replayed frame.

#include "iq_frame.hpp"

#include <cstdint>

namespace pipeline {

// Failure classes the orchestrator can observe.
enum class FailureClass {
    None,
    IqDrop,          // sequence monitor: dropped / gap / duplicate / reorder
    IqOverflow,      // producer-flagged ADC/FIFO overflow
    FpgaTimeout,     // PL-DDR op did not reach DONE
    FpgaError,       // PL-DDR STATUS_ERROR
    FpgaMismatch,    // tensor != Golden (numerical contract violated)
    NpuTimeout,      // waitForReady timed out
    NpuError,        // forward threw
    VersionMismatch, // VERSION != 0x20260929
};

// What the orchestrator does in response.
enum class RecoveryAction { Continue, AbortCycle, AbortRun };

// The recovery decision table.  Rationale (REPORT.md section F):
//   * IQ drop / overflow are survivable anomalies: record + continue (they are
//     exactly what the drop/overflow counters exist for).
//   * FPGA timeout / error / mismatch and NPU timeout / error / VERSION
//     mismatch are correctness-signal failures: abort the run rather than
//     infer on stale or corrupted data.
inline RecoveryAction policy_for(FailureClass f) {
    switch (f) {
        case FailureClass::IqDrop:
        case FailureClass::IqOverflow:
            return RecoveryAction::Continue;
        case FailureClass::FpgaTimeout:
        case FailureClass::FpgaError:
        case FailureClass::FpgaMismatch:
        case FailureClass::NpuTimeout:
        case FailureClass::NpuError:
        case FailureClass::VersionMismatch:
            return RecoveryAction::AbortRun;
        case FailureClass::None:
        default:
            return RecoveryAction::Continue;
    }
}

// Whether a failure class is fatal (maps to AbortRun) -- convenience wrapper.
inline bool is_fatal(FailureClass f) {
    return policy_for(f) == RecoveryAction::AbortRun;
}

// Data-flow stage labels.
enum class Stage { Capture, Fpga, Npu, Result, Idle };

// Aggregate counters that survive across cycles (what the final summary and the
// competition-recording template report).
struct CycleCounters {
    std::uint64_t captured_frames = 0;
    std::uint64_t fpga_runs = 0;
    std::uint64_t npu_runs = 0;
    std::uint64_t results = 0;
    std::uint64_t iq_drops = 0;      // sequence-monitor drop/gap/dup/reorder
    std::uint64_t iq_overflows = 0;  // producer-flagged overflow
    std::uint64_t fpga_failures = 0;
    std::uint64_t npu_timeouts = 0;
    std::uint64_t npu_errors = 0;
    std::uint64_t mismatches = 0;
};

}  // namespace pipeline
