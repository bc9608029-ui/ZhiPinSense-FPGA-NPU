#pragma once

// nco.hpp -- digital down-conversion NCO with cross-buffer phase continuity.
//
// Mixes a complex IQ stream down in frequency by `freq_hz` (i.e. multiplies by
// exp(-j*2*pi*freq/fs*n)).  The phase accumulator is a member, so phase carries
// across successive mix() calls -- the task requirement "数字下变频 NCO 必须保持
// 跨 buffer 相位连续" (task 39e5 section 7).
//
// iCraft-free and header-only.

#include <cmath>
#include <complex>
#include <cstddef>
#include <cstdint>

namespace sdr {

constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr double kTwoPi = 2.0 * kPi;

class Nco {
public:
    // freq_hz: down-conversion frequency (positive = shift signal down).
    // fs_hz:   sample rate the signal is at.
    Nco(double freq_hz, double fs_hz)
        : phase_(0.0), phase_inc_(kTwoPi * freq_hz / fs_hz) {}

    // In-place down-conversion of n complex samples.  Phase is NOT reset between
    // calls, so consecutive buffers stay phase-continuous.
    void mix(std::complex<float>* buf, std::size_t n) {
        for (std::size_t i = 0; i < n; ++i) {
            const double c = std::cos(phase_);
            const double s = std::sin(phase_);
            const float re = buf[i].real();
            const float im = buf[i].imag();
            // x * exp(-j*phase) = (re*c + im*s) + j*(im*c - re*s)
            buf[i] = std::complex<float>(
                static_cast<float>(re * c + im * s),
                static_cast<float>(im * c - re * s));
            advance();
        }
    }

    // Shift a single sample down and return it (does not mutate a buffer).
    std::complex<float> mix_one(std::complex<float> x) {
        std::complex<float> b = x;
        mix(&b, 1);
        return b;
    }

    void reset() {
        phase_ = 0.0;
        phase_samples_ = 0;
    }

    double phase() const { return phase_; }
    std::uint64_t phase_samples() const { return phase_samples_; }

private:
    void advance() {
        phase_ += phase_inc_;
        if (phase_ >= kTwoPi) phase_ -= kTwoPi;
        ++phase_samples_;
    }

    double phase_;      // accumulated phase in [0, 2*pi), double precision
    double phase_inc_;  // 2*pi*freq/fs per sample
    std::uint64_t phase_samples_ = 0;
};

}  // namespace sdr
