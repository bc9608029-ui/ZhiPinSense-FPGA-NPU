#pragma once

// receiver_scale.hpp -- global fixed-scalar ADC-to-model scaling + Q1.15 conversion.
//
// The conversion chain (task 39e5 section 8 / plan) is:
//     int16 adc count -> float = count * adc_lsb(=1/32768)
//                      -> x_model = float * receiver_scale
//                      -> Q1.15 = clip(lround(x_model * 32768))
//
// Collapsing the two *32768 cancels, Q1.15 = clip(lround(count * receiver_scale)),
// i.e. `receiver_scale` is a single dimensionless fixed scalar applied to the raw
// int16 count.  It is GLOBAL and FIXED -- no per-frame RMS normalization (explicitly
// forbidden).  It is determined once by non-blind calibration and then frozen.
//
// Header-only, iCraft-free.

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstddef>
#include <limits>

namespace sdr {

// Saturation/statistics accumulated by a ReceiverScale instance, used by the
// calibration report to back out `receiver_scale` and to flag clipping.
struct ScaleStats {
    std::uint64_t samples = 0;
    std::uint64_t q115_saturated = 0;  // outputs clamped to +32767 or -32768
    double sum_sq_i = 0.0;             // sum of (count_i)^2
    double sum_sq_q = 0.0;             // sum of (count_q)^2
    double max_abs = 0.0;              // max |count| seen across I/Q

    // RMS of the complex magnitude: sqrt(mean(|x|^2)) = sqrt((sum I^2 + sum Q^2)/N).
    // Rotation-invariant (a phase rotation of the signal leaves it unchanged).
    double rms() const {
        if (samples == 0) return 0.0;
        return std::sqrt((sum_sq_i + sum_sq_q) / static_cast<double>(samples));
    }
    double saturation_ratio() const {
        if (samples == 0) return 0.0;
        return static_cast<double>(q115_saturated) /
               (2.0 * static_cast<double>(samples));
    }
};

class ReceiverScale {
public:
    explicit ReceiverScale(float scale = 1.0f) : scale_(scale) {}

    // The global fixed scalar.  Frozen after calibration.
    float scale() const { return scale_; }
    void set_scale(float s) { scale_ = s; }

    // int16 count -> float model sample  (count/32768 * scale)
    float to_float(std::int16_t count) const {
        return static_cast<float>(count) * (scale_ / 32768.0f);
    }

    // int16 count -> Q1.15 (clip(lround(count * scale)))
    std::int16_t to_q115(std::int16_t count) const {
        const float v = static_cast<float>(count) * scale_;
        const long r = std::lround(v);
        return clip_q115(r);
    }

    // Complex int16 (interleaved or split) -> complex Q1.15, accumulating stats.
    void to_q115(const std::complex<std::int16_t>* in,
                 std::complex<std::int16_t>* out, std::size_t n) {
        for (std::size_t k = 0; k < n; ++k) {
            const auto c = in[k];
            out[k] = std::complex<std::int16_t>(to_q115(c.real()), to_q115(c.imag()));
            accumulate(c.real(), c.imag());
        }
    }

    // Split I/Q int16 -> split Q1.15, accumulating stats.
    void to_q115(const std::int16_t* i, const std::int16_t* q,
                 std::int16_t* oi, std::int16_t* oq, std::size_t n) {
        for (std::size_t k = 0; k < n; ++k) {
            oi[k] = to_q115(i[k]);
            oq[k] = to_q115(q[k]);
            accumulate(i[k], q[k]);
        }
    }

    const ScaleStats& stats() const { return stats_; }
    void reset_stats() { stats_ = ScaleStats{}; }

    // Back out `receiver_scale` so that a known-RMS tone lands at `target_q115_rms`.
    //   adc_rms: measured RMS of raw int16 counts (from stats().rms())
    //   target_q115_rms: desired model-side RMS in Q1.15 units (e.g. 8192 ~ -12 dBFS)
    static float calibrate_scale(double adc_rms, double target_q115_rms) {
        if (adc_rms <= 0.0) return 1.0f;
        return static_cast<float>(target_q115_rms / adc_rms);
    }

private:
    static std::int16_t clip_q115(long r) {
        if (r > 32767) return 32767;
        if (r < -32768) return -32768;
        return static_cast<std::int16_t>(r);
    }

    void accumulate(std::int16_t i, std::int16_t q) {
        ++stats_.samples;
        const double di = i, dq = q;
        stats_.sum_sq_i += di * di;
        stats_.sum_sq_q += dq * dq;
        const double am = std::max(std::abs(di), std::abs(dq));
        if (am > stats_.max_abs) stats_.max_abs = am;
        const float vi = static_cast<float>(i) * scale_;
        const float vq = static_cast<float>(q) * scale_;
        if (std::lround(vi) > 32767 || std::lround(vi) < -32768 ||
            std::lround(vq) > 32767 || std::lround(vq) < -32768) {
            ++stats_.q115_saturated;
        }
    }

    float scale_;
    ScaleStats stats_;
};

}  // namespace sdr
