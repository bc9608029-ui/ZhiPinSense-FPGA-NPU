#pragma once

// IQ frame contract + source interface for the non-model system layer.
//
// This is the SDR-adapter / pipeline contract.  It is iCraft-free so it can be
// compiled and unit-tested on the host (or board) without the NPU SDK.  The
// board-facing copy in ../board_package/iq_source.hpp carries the same Frame
// fields for the continuous_joint_stress program; the two are kept consistent
// but intentionally self-contained (each package builds on its own).
//
// Contract (see ../contracts/sampling_and_iq_contract.md for the normative text):
//   * one frame == 1024 complex IQ samples;
//   * I and Q are signed int16, interleaved [I0,Q0,I1,Q1,...], little-endian;
//   * a short frame (fewer than 1024 samples) is flagged and MUST NOT be fed
//     to the FPGA;
//   * frame_id is a monotonic per-stream counter (no wrap) for FileIqSource /
//     SyntheticIqSource; SDR hardware counter wrap handling is TBD and is NOT
//     assumed here.
//
// overflow / dropped / discontinuity are PRODUCER-set flags (e.g. the future
// SDR source flags its own FIFO overflow / sample-rate jump).  duplicate /
// reorder / inferred-drop (gap) are CONSUMER-detected by iq::SequenceMonitor
// (sequence_monitor.hpp), not carried on the frame.

#include <cstdint>

namespace iq {

constexpr std::size_t kComplexSamplesPerFrame = 1024;
// 1024 samples x 2 components (I,Q) x 2 bytes (int16) = 4096 bytes/frame.
constexpr std::size_t kFrameBytes = kComplexSamplesPerFrame * 2 * sizeof(std::int16_t);

struct Frame {
    const std::int16_t* iq = nullptr;  // interleaved I,Q; 1024 pairs (2048 int16)
    std::uint64_t frame_id = 0;        // monotonic per-stream counter (see above)
    std::uint64_t timestamp_us = 0;    // producer timestamp; 0 if unavailable
    bool overflow = false;             // producer: ADC/FIFO overflow in this window
    bool dropped = false;              // producer: a frame was dropped before this one
    bool discontinuity = false;        // producer: timestamp / sample-rate jump
    bool short_frame = false;          // true => <1024 samples; do NOT feed FPGA
};

class Source {
public:
    virtual ~Source() = default;

    // Fill `out` with the next frame.  Returns false on clean end-of-stream
    // (single-shot source exhausted); throws on hard I/O errors.  When true,
    // `out.short_frame` tells the caller whether a full 1024-sample frame was
    // produced.
    virtual bool next(Frame& out) = 0;

    // Restart at the first frame (loop / single replay boundary).
    virtual void rewind() = 0;

    // Number of frames the source yields (0 = unknown / unbounded).
    virtual std::uint64_t frame_count() const = 0;
};

}  // namespace iq
