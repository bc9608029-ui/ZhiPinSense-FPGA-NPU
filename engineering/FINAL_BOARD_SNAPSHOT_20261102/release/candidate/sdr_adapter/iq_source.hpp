#pragma once

// Concrete IQ sources for the non-model system layer (declarations).
//   * FileIqSource      -- replays a frozen IQ buffer byte-exactly (today).
//   * SyntheticIqSource -- deterministic simulated IQ so the pipeline can be
//                          exercised offline without any SDR (simulated input).
//   * SdrIqSource       -- placeholder; construction throws until the SDR model,
//                          interface and sample rate are specified (no driver
//                          API is guessed).
//
// See iq_source.cpp for implementations.

#include "iq_frame.hpp"

#include <cstdint>
#include <vector>

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

class SyntheticIqSource : public iq::Source {
public:
    // `frame_count` deterministic frames (a fixed complex tone at ~4 kHz when
    // interpreted at 128 ksps).  `loop` => wrap; else single-shot.  frame_id is
    // monotonic (0,1,2,...), so the stream is anomaly-free by construction.
    SyntheticIqSource(std::uint64_t frame_count, bool loop);

    bool next(iq::Frame& out) override;
    void rewind() override;
    std::uint64_t frame_count() const override;

private:
    std::uint64_t frame_count_;
    bool loop_;
    std::uint64_t cursor_ = 0;
    std::vector<std::int16_t> buf_;  // one generated frame, stable address
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
