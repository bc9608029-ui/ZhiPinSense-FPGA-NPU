#pragma once

// m24_waterfall.hpp -- M24-A fixed-capacity waterfall ring buffer (spectrogram).
//
// Stores one row (spectrum dB vector) per frame in a fixed-capacity circular
// buffer.  New frames overwrite the oldest (no unbounded growth); reads are in
// time order (oldest -> newest); a display-downsampling helper averages bins.
// Memory footprint is explicit and constant after construction.

#include <cstddef>
#include <vector>

namespace m24 {

class Waterfall {
public:
    // capacity rows x cols bins.  capacity==0 or cols==0 is rejected: the
    // object stays empty and push() is a no-op (fail-closed).
    Waterfall(std::size_t capacity, std::size_t cols)
        : capacity_(capacity), cols_(cols), buf_(capacity * cols, 0.0f),
          head_(0), count_(0) {}

    // Clear all stored rows (keeps capacity).
    void clear() {
        head_ = 0;
        count_ = 0;
    }

    // Clear and release storage (capacity becomes 0).
    void reset() {
        capacity_ = 0;
        cols_ = 0;
        head_ = 0;
        count_ = 0;
        buf_.clear();
    }

    // Append one spectrum frame (length must equal cols(); else ignored).
    void push(const std::vector<float>& frame) {
        if (capacity_ == 0 || cols_ == 0) return;
        if (frame.size() != cols_) return;
        std::size_t base = head_ * cols_;
        for (std::size_t k = 0; k < cols_; ++k) buf_[base + k] = frame[k];
        head_ = (head_ + 1) % capacity_;
        if (count_ < capacity_) ++count_;
    }

    // Number of currently stored rows (<= capacity).
    std::size_t rows() const { return count_; }
    std::size_t capacity() const { return capacity_; }
    std::size_t cols() const { return cols_; }

    // Explicit memory footprint in bytes (ring buffer payload only).
    std::size_t memory_bytes() const {
        return capacity_ * cols_ * sizeof(float);
    }

    // Row by age: age 0 = newest, age rows()-1 = oldest.  Out of range -> empty.
    std::vector<float> row(std::size_t age) const {
        if (age >= count_) return {};
        // newest is at head_-1; age 0 -> (head_-1), age k -> head_-1-k (mod cap)
        std::size_t idx = (head_ + capacity_ - 1 - age) % capacity_;
        std::vector<float> r(cols_);
        std::size_t base = idx * cols_;
        for (std::size_t k = 0; k < cols_; ++k) r[k] = buf_[base + k];
        return r;
    }

    // Flatten in time order (oldest -> newest), row-major.
    std::vector<float> read_oldest_first() const {
        std::vector<float> out;
        out.reserve(count_ * cols_);
        for (std::size_t age = count_; age > 0; --age) {
            const std::vector<float> r = row(age - 1);
            out.insert(out.end(), r.begin(), r.end());
        }
        return out;
    }

    // Display downsampling: average `cols` bins into `target_cols` bins for the
    // newest row.  target_cols==0 or > cols -> unchanged copy.  Non-integer
    // reduction averages with per-bin weighting (last bin takes the remainder).
    std::vector<float> downsample_newest(std::size_t target_cols) const {
        const std::vector<float> newest = row(0);
        if (newest.empty() || target_cols == 0 || target_cols >= cols_)
            return newest;
        std::vector<float> out(target_cols, 0.0f);
        // Map each source bin to a target bin proportionally.
        for (std::size_t k = 0; k < cols_; ++k) {
            const std::size_t t =
                (k * target_cols) / cols_;  // in [0, target_cols)
            out[t] += newest[k];
        }
        // Normalize by the number of source bins mapped to each target.
        for (std::size_t t = 0; t < target_cols; ++t) {
            const std::size_t lo = (t * cols_) / target_cols;
            const std::size_t hi = ((t + 1) * cols_) / target_cols;
            const std::size_t cnt = (hi > lo) ? (hi - lo) : 1;
            out[t] /= static_cast<float>(cnt);
        }
        return out;
    }

private:
    std::size_t capacity_;
    std::size_t cols_;
    std::vector<float> buf_;
    std::size_t head_;   // next write slot
    std::size_t count_;  // filled rows
};

}  // namespace m24
