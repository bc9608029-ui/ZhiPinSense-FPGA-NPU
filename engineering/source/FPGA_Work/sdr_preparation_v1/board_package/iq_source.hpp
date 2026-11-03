#pragma once

// Unified IQ data-source contract for the continuous joint stress loop and for
// the future SDR ingest.  Two implementations exist:
//
//   * FileIqSource -- replays the frozen iq_input.bin (19 x 1024 complex IQ,
//                     interleaved signed int16).  Usable TODAY, byte-identical
//                     to the frozen Golden input.
//   * SdrIqSource  -- interface / placeholder ONLY.  The specific SDR model,
//                     electrical interface and target sample rate are not yet
//                     specified (see REPORT.md), so no vendor API, USB VID:PID,
//                     or sample-format assumption is baked in.
//
// Output contract (identical for every source):
//   * one frame == 1024 complex IQ samples;
//   * I and Q are signed int16, interleaved [I0,Q0,I1,Q1,...];
//   * little-endian (the aarch64 board and the frozen iq_input.bin are LE);
//   * a partial (short) frame is flagged and MUST NOT be silently fed to the
//     FPGA;
//   * frame_id, plus reserved timestamp / overflow / drop / discontinuity
//     status so the SDR path can carry real-time metadata later without a
//     contract change.

#include <cstddef>
#include <cstdint>
#include <vector>

namespace iq {

constexpr std::size_t kComplexSamplesPerFrame = 1024;
// 1024 samples x 2 components (I,Q) x 2 bytes (int16) = 4096 bytes/frame.
constexpr std::size_t kFrameBytes = kComplexSamplesPerFrame * 2 * sizeof(std::int16_t);

struct Frame {
    const std::int16_t* iq = nullptr;  // interleaved I,Q; 1024 pairs (2048 int16)
    std::uint64_t frame_id = 0;        // file index for FileIqSource; global for SDR
    std::uint64_t timestamp_us = 0;    // reserved; 0 from the file source
    bool overflow = false;             // reserved; always false from the file source
    bool dropped = false;              // reserved; always false from the file source
    bool discontinuity = false;        // reserved; always false from the file source
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

    // Number of frames the source yields (0 = unbounded / unknown).
    virtual std::uint64_t frame_count() const = 0;
};

}  // namespace iq

// ---- implementations -------------------------------------------------------

class FileIqSource : public iq::Source {
public:
    // `bytes` is the raw frozen IQ buffer (frame_count * iq::kFrameBytes).  The
    // source does NOT own it; the caller keeps it alive for the source lifetime.
    // `loop` => wrap to frame 0 after the last frame, else return false.
    FileIqSource(const std::vector<char>& bytes, std::uint64_t frame_count, bool loop);

    bool next(iq::Frame& out) override;
    void rewind() override;
    std::uint64_t frame_count() const override;

private:
    const std::vector<char>& bytes_;
    std::uint64_t frame_count_;
    bool loop_;
    std::uint64_t cursor_ = 0;
};

class SdrIqSource : public iq::Source {
public:
    // Placeholder.  Constructing one before the SDR is specified throws, so an
    // accidental SDR path fails loudly instead of silently assuming a device.
    SdrIqSource();

    bool next(iq::Frame& out) override;
    void rewind() override;
    std::uint64_t frame_count() const override;
};
