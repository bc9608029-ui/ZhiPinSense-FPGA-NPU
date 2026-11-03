#pragma once

// frame_analysis.hpp -- pure, header-only per-frame signal analysis + block
// continuity detection (no libiio, no device).  Shared by the board gate programs
// (board_common.hpp) and the host regression tests (test_frame_analysis.cpp).
//
// WHY PER-FRAME: a Pluto RX refill (one iio_buffer_refill) returns a block of
// samples that is internally continuous, but the phase at the start of the next
// block is NOT a continuation of the previous block (samples are dropped between
// refills / the DMA resyncs).  Concatenating blocks and running ONE full-length
// Goertzel makes a clean tone destructively interfere across block boundaries and
// reports a FALSE failure (board result: per-frame ratio ~0.99998 but full-length
// ratio 0.030).  So every spectral/amplitude verdict is computed PER 1024-sample
// frame; the full-length "global_ratio" is retained only as a diagnostic.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <vector>

namespace sdr {

// π, named to avoid colliding with the `kPi` that nco.hpp also defines in
// namespace sdr (both headers are pulled into the same board/test TU).
constexpr double kPiF = 3.141592653589793238462643383279502884;

// --- basic math (moved here from board_common so host tests can use them) -----

// Single-bin Goertzel energy ratio (scale-invariant spectral concentration in
// [0,1]): ~1.0 when a single tone at `f` dominates, ~0 when energy is elsewhere.
inline double goertzel_ratio(const std::vector<std::complex<float>>& x,
                             double f, double fs) {
    const std::size_t n = x.size();
    std::complex<double> acc(0.0, 0.0);
    double total = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        const double ph = 2.0 * kPiF * f / fs * static_cast<double>(i);
        const std::complex<double> ref(std::cos(ph), -std::sin(ph));
        const std::complex<double> s(x[i].real(), x[i].imag());
        acc += s * ref;
        total += std::abs(s);
    }
    return std::abs(acc) / (total + 1e-12);
}

// Raw single-bin complex accumulation (unnormalised).  For x[k]=A*e^{j*2*pi*f0*k/fs},
// goertzel_bin(x, f0, fs) == A*N.
inline std::complex<double> goertzel_bin(const std::vector<std::complex<float>>& x,
                                         double f, double fs) {
    std::complex<double> acc(0.0, 0.0);
    for (std::size_t i = 0; i < x.size(); ++i) {
        const double ph = 2.0 * kPiF * f / fs * static_cast<double>(i);
        const std::complex<double> ref(std::cos(ph), -std::sin(ph));
        acc += std::complex<double>(x[i].real(), x[i].imag()) * ref;
    }
    return acc;
}

// Complex amplitude of a complex exponential at frequency `f` = |bin| / N.
inline double goertzel_amp(const std::vector<std::complex<float>>& x,
                           double f, double fs) {
    if (x.empty()) return 0.0;
    return std::abs(goertzel_bin(x, f, fs)) / static_cast<double>(x.size());
}

// Dominant single-tone frequency from the first-order autocorrelation:
//   f = arg(sum_k x[k+1]*conj(x[k])) / (2*pi) * fs,  in [-fs/2, fs/2].
// Phase-only (scale-invariant), NOT quantised to FFT bins, so it resolves a tone
// far finer than fs/N.
inline double dominant_freq_hz(const std::vector<std::complex<float>>& x, double fs) {
    if (x.size() < 2) return 0.0;
    std::complex<double> acc(0.0, 0.0);
    for (std::size_t k = 0; k + 1 < x.size(); ++k) {
        acc += std::complex<double>(x[k + 1].real(), x[k + 1].imag()) *
               std::complex<double>(x[k].real(), -x[k].imag());
    }
    if (std::abs(acc) < 1e-12) return 0.0;
    return std::arg(acc) / (2.0 * kPiF) * fs;
}

// RMS of a complex sample vector (rotation-invariant magnitude RMS).
inline double rms(const std::vector<std::complex<float>>& x) {
    if (x.empty()) return 0.0;
    double s = 0.0;
    for (const auto& v : x)
        s += static_cast<double>(v.real()) * v.real() +
             static_cast<double>(v.imag()) * v.imag();
    return std::sqrt(s / static_cast<double>(x.size()));
}

// Peak |int16| count across an interleaved I/Q buffer (saturation check).
inline int max_abs_iq(const std::vector<std::int16_t>& iq) {
    int m = 0;
    for (const std::int16_t v : iq) {
        const int a = v < 0 ? -v : v;
        if (a > m) m = a;
    }
    return m;
}

// Interleaved int16 -> complex<float>, normalised to [-1,1] by full_scale.
// AD9364 is 12-bit in a 16-bit container; full_scale = 2048 (2^11), NOT 32768.
inline std::vector<std::complex<float>> to_complex(const std::vector<std::int16_t>& iq,
                                                   float full_scale = 2048.0f) {
    std::vector<std::complex<float>> out(iq.size() / 2);
    for (std::size_t k = 0; k < out.size(); ++k) {
        out[k] = std::complex<float>(static_cast<float>(iq[k * 2 + 0]) / full_scale,
                                     static_cast<float>(iq[k * 2 + 1]) / full_scale);
    }
    return out;
}

// --- per-frame analysis -------------------------------------------------------

struct FrameResult {
    double ratio_pos = 0.0;       // Goertzel concentration at +tone_hz
    double ratio_neg = 0.0;       // Goertzel concentration at -tone_hz
    double ratio = 0.0;           // max(ratio_pos, ratio_neg)
    double dominant_freq_hz = 0.0;
    double freq_error_hz = 0.0;   // min(|f-tone|, |f+tone|)
    int peak = 0;                 // max |int16| in the frame
    double rms = 0.0;
    bool ratio_ok = false;        // ratio > ratio_threshold
    bool freq_ok = false;         // freq_error_hz <= freq_err_max
};

// Analyse ONE frame (interleaved int16, exactly frame_complex complex samples).
inline FrameResult analyze_frame(const std::vector<std::int16_t>& iq,
                                 double tone_hz, double fs,
                                 double ratio_threshold, double freq_err_max) {
    FrameResult r;
    const auto x = to_complex(iq);
    r.ratio_pos = goertzel_ratio(x, tone_hz, fs);
    r.ratio_neg = goertzel_ratio(x, -tone_hz, fs);
    r.ratio = std::max(r.ratio_pos, r.ratio_neg);
    r.dominant_freq_hz = dominant_freq_hz(x, fs);
    r.freq_error_hz = std::min(std::fabs(r.dominant_freq_hz - tone_hz),
                               std::fabs(r.dominant_freq_hz + tone_hz));
    r.peak = max_abs_iq(iq);
    r.rms = rms(x);
    r.ratio_ok = r.ratio > ratio_threshold;
    r.freq_ok = r.freq_error_hz <= freq_err_max;
    return r;
}

struct FrameSummary {
    std::size_t frame_count = 0;   // complete frames found (iq.size()/2 / frame_complex)
    double ratio_min = 0.0;
    double ratio_mean = 0.0;
    double ratio_max = 0.0;
    std::size_t frame_pass_count = 0;  // frames with ratio_ok && freq_ok
    double freq_mean = 0.0;            // mean of |dominant_freq_hz|
    double freq_max_error = 0.0;       // max freq_error_hz over frames
    int peak_max = 0;                  // max per-frame peak
    double rms_mean = 0.0;             // mean per-frame rms
    double global_ratio = 0.0;         // DIAGNOSTIC ONLY: full-length Goertzel over the
                                       // concatenated (phase-broken) stream. Never a
                                       // PASS criterion.
};

// Analyse a whole interleaved int16 buffer frame-by-frame.  Trailing samples that
// do not form a complete frame are ignored (never zero-padded).  global_ratio is
// the single full-length Goertzel, retained purely to make the false-failure mode
// visible in the log.
inline FrameSummary analyze_frames(const std::vector<std::int16_t>& iq,
                                   std::size_t frame_complex,
                                   double tone_hz, double fs,
                                   double ratio_threshold, double freq_err_max) {
    FrameSummary s;
    const std::size_t n_complex = iq.size() / 2;
    s.frame_count = n_complex / frame_complex;
    if (s.frame_count == 0) return s;

    double rsum = 0.0, fsum = 0.0, psum = 0.0;
    bool first = true;
    for (std::size_t k = 0; k < s.frame_count; ++k) {
        std::vector<std::int16_t> frame(iq.begin() + static_cast<long>(k * frame_complex * 2),
                                        iq.begin() + static_cast<long>((k + 1) * frame_complex * 2));
        const FrameResult fr = analyze_frame(frame, tone_hz, fs, ratio_threshold, freq_err_max);
        if (first) { s.ratio_min = s.ratio_max = fr.ratio; first = false; }
        else {
            s.ratio_min = std::min(s.ratio_min, fr.ratio);
            s.ratio_max = std::max(s.ratio_max, fr.ratio);
        }
        rsum += fr.ratio;
        fsum += std::fabs(fr.dominant_freq_hz);
        psum += fr.rms;
        if (fr.freq_error_hz > s.freq_max_error) s.freq_max_error = fr.freq_error_hz;
        if (fr.peak > s.peak_max) s.peak_max = fr.peak;
        if (fr.ratio_ok && fr.freq_ok) ++s.frame_pass_count;
    }
    s.ratio_mean = rsum / static_cast<double>(s.frame_count);
    s.freq_mean = fsum / static_cast<double>(s.frame_count);
    s.rms_mean = psum / static_cast<double>(s.frame_count);

    // DIAGNOSTIC ONLY -- the false-failure the per-frame analysis fixes.
    const auto full = to_complex(iq);
    s.global_ratio = std::max(goertzel_ratio(full, tone_hz, fs),
                              goertzel_ratio(full, -tone_hz, fs));
    return s;
}

// --- block continuity ---------------------------------------------------------

// Wrap an angle to [-pi, pi].
inline double wrap_pi(double a) {
    while (a > kPiF) a -= 2.0 * kPiF;
    while (a < -kPiF) a += 2.0 * kPiF;
    return a;
}

// Detect whether the TONE phase is continuous across the boundaries between
// consecutive frames (each frame_complex samples) of a pure tone at `tone_hz`.
//
// For a continuous stream the cross-boundary phase step x[b]*conj(x[b-1]) must
// equal the per-sample phase advance 2*pi*tone_hz/fs.  When blocks were dropped /
// resynced between refills, the boundary phase is arbitrary and this returns
// false.  This is the testable proof of WHY multi-block concatenation must NOT be
// treated as a continuous stream (used by the host regression tests).
inline bool tone_phase_continuous(const std::vector<std::complex<float>>& all_x,
                                  std::size_t frame_complex,
                                  double tone_hz, double fs,
                                  double phase_tol_rad = 0.1) {
    const std::size_t n = all_x.size();
    if (n <= frame_complex) return true;  // one frame: trivially continuous
    const double expect = 2.0 * kPiF * tone_hz / fs;
    for (std::size_t b = frame_complex; b < n; b += frame_complex) {
        const std::complex<double> p =
            std::complex<double>(all_x[b].real(), all_x[b].imag()) *
            std::complex<double>(all_x[b - 1].real(), -all_x[b - 1].imag());
        const double diff = std::fabs(wrap_pi(std::arg(p) - expect));
        if (diff > phase_tol_rad) return false;
    }
    return true;
}

}  // namespace sdr
