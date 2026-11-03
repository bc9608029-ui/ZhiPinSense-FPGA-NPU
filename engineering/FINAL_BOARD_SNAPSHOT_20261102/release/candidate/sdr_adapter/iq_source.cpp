#include "iq_source.hpp"

#include <cmath>
#include <cstdint>
#include <stdexcept>

// ---- FileIqSource -----------------------------------------------------------
// Slices a frozen IQ buffer into fixed 1024-sample frames with no transform, so
// the bytes it yields are identical to the frozen input by construction.

FileIqSource::FileIqSource(const std::vector<char>& bytes, std::uint64_t frame_count, bool loop)
    : bytes_(bytes), frame_count_(frame_count), loop_(loop) {
    if (frame_count_ == 0) {
        throw std::runtime_error("FileIqSource: frame_count must be > 0");
    }
    if (bytes_.size() != frame_count_ * iq::kFrameBytes) {
        throw std::runtime_error(
            "FileIqSource: buffer size does not match frame_count * 4096 bytes");
    }
}

bool FileIqSource::next(iq::Frame& out) {
    if (cursor_ >= frame_count_) {
        if (!loop_) return false;  // single-shot: clean end of stream
        cursor_ = 0;               // loop: wrap to the first frame
    }
    const std::size_t off = static_cast<std::size_t>(cursor_) * iq::kFrameBytes;
    out.iq = reinterpret_cast<const std::int16_t*>(bytes_.data() + off);
    out.frame_id = cursor_;
    out.timestamp_us = cursor_ * (1000000ULL * iq::kComplexSamplesPerFrame / 128000ULL);
    out.overflow = false;
    out.dropped = false;
    out.discontinuity = false;
    out.short_frame = false;  // file slices are always full frames
    ++cursor_;
    return true;
}

void FileIqSource::rewind() { cursor_ = 0; }

std::uint64_t FileIqSource::frame_count() const { return frame_count_; }

// ---- SyntheticIqSource ------------------------------------------------------
// Deterministic simulated input: a fixed complex tone (32 samples/cycle) at
// amplitude 0.7*32767.  Integer-only after the sin/cos table so the frame bytes
// are stable for the lifetime of the process.  Used to exercise the pipeline
// plumbing offline (buffer ownership, sequence monitor, perf timing) without a
// real SDR or the frozen IQ file.

SyntheticIqSource::SyntheticIqSource(std::uint64_t frame_count, bool loop)
    : frame_count_(frame_count), loop_(loop) {
    if (frame_count_ == 0) {
        throw std::runtime_error("SyntheticIqSource: frame_count must be > 0");
    }
    buf_.resize(iq::kComplexSamplesPerFrame * 2);
    const double amp = 0.7 * 32767.0;
    const double k = 2.0 * 3.14159265358979323846 / 32.0;
    for (std::size_t n = 0; n < iq::kComplexSamplesPerFrame; ++n) {
        const double ph = k * static_cast<double>(n);
        buf_[2 * n + 0] = static_cast<std::int16_t>(std::llround(amp * std::sin(ph)));
        buf_[2 * n + 1] = static_cast<std::int16_t>(std::llround(amp * std::cos(ph)));
    }
}

bool SyntheticIqSource::next(iq::Frame& out) {
    if (cursor_ >= frame_count_) {
        if (!loop_) return false;
        cursor_ = 0;
    }
    out.iq = buf_.data();
    out.frame_id = cursor_;
    out.timestamp_us = cursor_ * (1000000ULL * iq::kComplexSamplesPerFrame / 128000ULL);
    out.overflow = false;
    out.dropped = false;
    out.discontinuity = false;
    out.short_frame = false;
    ++cursor_;
    return true;
}

void SyntheticIqSource::rewind() { cursor_ = 0; }

std::uint64_t SyntheticIqSource::frame_count() const { return frame_count_; }

// ---- SdrIqSource ------------------------------------------------------------
// Contract placeholder.  The local materials do not specify a concrete SDR
// model, electrical interface, or raw sample rate (audited: "No final SDR is
// selected"; deployment_contract.yaml todo_hardware: "Confirm SDR physical
// interface and sample clock").  No vendor API, USB VID:PID, Ethernet protocol,
// or sample format (float32 / int12 / int16) may be assumed before the device
// arrives.

SdrIqSource::SdrIqSource() {
    throw std::runtime_error(
        "SdrIqSource is a placeholder: SDR model/interface/sample rate not yet specified");
}

bool SdrIqSource::next(iq::Frame& /*out*/) {
    throw std::runtime_error("SdrIqSource::next not implemented (SDR unspecified)");
}

void SdrIqSource::rewind() {
    throw std::runtime_error("SdrIqSource::rewind not implemented (SDR unspecified)");
}

std::uint64_t SdrIqSource::frame_count() const {
    return 0;  // unknown
}
