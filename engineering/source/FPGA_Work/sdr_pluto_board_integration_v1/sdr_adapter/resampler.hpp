#pragma once

// resampler.hpp -- streaming rational polyphase resampler.
//
// Resamples a continuous complex<float> IQ stream from fs_in to fs_out using a
// rational ratio R = fs_in/fs_out = up/down (reduced form).  Integer decimation
// is up=1, down=D (e.g. 2.56 MHz -> 128 kHz is D=20).
//
//   push(complex*, n) / available() / pull(complex*, max) / reset()
//
// State (FIR delay line + polyphase pointer) persists across push()/pull()
// calls, so the output is bit-stable regardless of how the caller chunks the
// input.  The first (N-1) output samples (N = total FIR taps) are discarded as
// startup transient and counted via discarded_transient().
//
// iCraft-free.

#include <complex>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <vector>

namespace sdr {

class StreamResampler {
public:
    // up/down: rational ratio fs_in/fs_out = up/down (reduced form).
    // fir: polyphase FIR coefficients; length MUST be a multiple of `up`.
    //      fir[r + k*up] is phase r, tap k (r in [0,up), k in [0,len/up)).
    StreamResampler(std::uint32_t up, std::uint32_t down,
                    const std::vector<double>& fir);

    void reset();

    // Append n input samples at fs_in.
    void push(const std::complex<float>* in, std::size_t n);

    // Number of VALID (post-transient) output samples producible right now.
    std::size_t available() const;

    // Emit up to `max` valid output samples; returns the count actually written.
    std::size_t pull(std::complex<float>* out, std::size_t max);

    std::uint64_t in_count() const { return in_count_; }
    std::uint64_t out_count() const { return out_count_; }
    std::uint64_t discarded_transient() const { return discarded_; }

    std::uint32_t up() const { return up_; }
    std::uint32_t down() const { return down_; }
    std::uint32_t taps_per_phase() const { return p_; }
    std::size_t taps_total() const { return h_.size(); }

private:
    bool can_produce(std::uint64_t m) const;
    std::complex<float> compute_output(std::uint64_t m) const;
    void discard_old();

    std::uint32_t up_;
    std::uint32_t down_;
    std::uint32_t p_;
    std::vector<double> h_;

    std::deque<std::complex<float>> x_;  // real input history window
    std::uint64_t in_base_ = 0;          // absolute input index of x_[0]
    std::uint64_t in_count_ = 0;         // total samples pushed
    std::uint64_t out_idx_ = 0;          // next output index to produce
    std::uint64_t out_count_ = 0;        // valid outputs produced
    std::uint64_t discarded_ = 0;        // transient outputs discarded
};

}  // namespace sdr
