#pragma once

// m23_cfo.hpp -- carrier-frequency-offset estimation (M23 P0, parameter "H").
//
// CFO is the residual carrier offset between the transmitter and the receiver
// local oscillator.  In the synthetic/replay harness the carrier is KNOWN, so
// CFO is estimated against a reference carrier f_ref:
//
//   cfo = f_est - f_ref
//
// where f_est is a fine (sub-FFT-bin) frequency estimate from the first-order
// autocorrelation phase -- the same math as frame_analysis.hpp::dominant_freq_hz,
// re-expressed pointer-based so the hot path can reuse caller buffers.
//
// Modulation nonlinearity: a data-modulated carrier has no clean spectral line,
// so the modulation is stripped by raising the signal to its modulation order M
// (BPSK: M=2, QPSK: M=4); x^M then contains a line at M*(f_ref + cfo), and
//   cfo = dominant_freq(x^M) / M - f_ref.
//
// Aliasing bounds (MUST hold, else the /M frequency folds and the estimate is
// wrong):  |f_ref + cfo| < fs / (2*M).  The synthetic tests choose carriers and
// CFOs inside these bounds.  This is documented here, not silently corrected.
//
// iCraft-free, header-only.

#include <cmath>
#include <complex>
#include <cstddef>
#include <limits>
#include <vector>

namespace m23 {

constexpr double kPi = 3.141592653589793238462643383279502884;

// Fine frequency estimate from the first-order autocorrelation phase, in Hz.
// Returns in [-fs/2, fs/2].  Scale-invariant (phase only), so it works on the
// raw count-domain samples without normalisation.  Returns NaN for n < 2 or a
// degenerate (near-zero) autocorrelation.
inline double dominant_freq_hz(const std::complex<float>* x, std::size_t n, double fs) {
    if (n < 2) return std::numeric_limits<double>::quiet_NaN();
    std::complex<double> acc(0.0, 0.0);
    for (std::size_t k = 0; k + 1 < n; ++k) {
        acc += std::complex<double>(x[k + 1].real(), x[k + 1].imag()) *
               std::complex<double>(x[k].real(), -x[k].imag());
    }
    if (std::abs(acc) < 1e-12) return std::numeric_limits<double>::quiet_NaN();
    return std::arg(acc) / (2.0 * kPi) * fs;
}

// Reusable buffer for the modulation nonlinearity x^M (M = 2 or 4).  Order 1
// (a pure tone / pilot) needs no buffer.
struct CfoScratch {
    std::vector<std::complex<float>> y;
};

// CFO estimate against a reference carrier.  `order` is the modulation order of
// the nonlinearity: 1 = tone/CW/pilot (no nonlinearity), 2 = BPSK, 4 = QPSK.
// Returns cfo in Hz, or NaN when the input is degenerate (n < 2, zero
// autocorrelation, or empty nonlinearity buffer).
inline double estimate_cfo(const std::complex<float>* x, std::size_t n, double fs,
                           double f_ref, int order, CfoScratch& scratch) {
    if (n < 2) return std::numeric_limits<double>::quiet_NaN();
    if (order == 1) {
        const double f = dominant_freq_hz(x, n, fs);
        return std::isnan(f) ? f : f - f_ref;
    }
    if (order != 2 && order != 4) return std::numeric_limits<double>::quiet_NaN();

    scratch.y.resize(n);
    for (std::size_t k = 0; k < n; ++k) {
        const std::complex<float> v = x[k];
        if (order == 2) {
            scratch.y[k] = v * v;
        } else {
            const std::complex<float> v2 = v * v;
            scratch.y[k] = v2 * v2;
        }
    }
    const double f_line = dominant_freq_hz(scratch.y.data(), n, fs);
    if (std::isnan(f_line)) return f_line;
    return f_line / static_cast<double>(order) - f_ref;
}

}  // namespace m23
