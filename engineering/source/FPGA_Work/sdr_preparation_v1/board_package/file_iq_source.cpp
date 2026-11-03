#include "iq_source.hpp"

#include <stdexcept>

// FileIqSource slices a frozen IQ buffer into fixed 1024-sample frames without
// any transformation, so the bytes it yields are identical to the frozen
// iq_input.bin by construction.  It supports loop replay, single-shot replay,
// and an explicit frame count.

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
    out.timestamp_us = 0;
    out.overflow = false;
    out.dropped = false;
    out.discontinuity = false;
    out.short_frame = false;  // file slices are always full 1024-sample frames
    ++cursor_;
    return true;
}

void FileIqSource::rewind() { cursor_ = 0; }

std::uint64_t FileIqSource::frame_count() const { return frame_count_; }
