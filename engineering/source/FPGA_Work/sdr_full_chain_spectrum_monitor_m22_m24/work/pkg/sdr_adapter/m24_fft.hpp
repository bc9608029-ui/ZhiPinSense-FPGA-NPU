#pragma once

// m24_fft.hpp -- M24-A CPU reference FFT / spectrum toolbox (model-independent).
//
// Self-contained radix-2 complex FFT (double precision) plus the spectrum
// helpers the patrol/waterfall/UI modules need.  No external dependencies, no
// FFTW, no iCraft/libiio.  This is a REFERENCE implementation for offline
// pre-research and host tests only; it does not touch Gate 9/10, the board, or
// any RTL/XDC/bitstream.
//
// Fail-closed policy: any non-finite input or illegal parameter (length not a
// power of two, n < 2, null pointer, NaN/Inf) yields an invalid result (empty
// output + valid=false) rather than a wrong number.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <string>
#include <vector>

namespace m24 {

constexpr double kPi = 3.141592653589793238462643383279502884;

// --- validation -------------------------------------------------------------

inline bool is_power_of_two(std::size_t n) {
    return n >= 2 && (n & (n - 1)) == 0;
}

inline bool any_nonfinite(const std::complex<double>* x, std::size_t n) {
    if (x == nullptr) return true;
    for (std::size_t k = 0; k < n; ++k) {
        const double re = x[k].real();
        const double im = x[k].imag();
        if (!std::isfinite(re) || !std::isfinite(im)) return true;
    }
    return false;
}

inline bool any_nonfinite(const std::vector<double>& v) {
    for (double x : v)
        if (!std::isfinite(x)) return true;
    return false;
}

// --- FFT --------------------------------------------------------------------

struct Spectrum {
    std::vector<std::complex<double>> bins;  // DFT output, bin 0 = DC (unshifted)
    bool valid = false;
    std::string error;
};

// In-place radix-2 DIT FFT.  Returns invalid (empty bins) on illegal input or
// non-finite samples.  Unnormalized: for a complex tone x[k]=A*e^{j 2 pi m k/n}
// the peak |X[m]| == A*n.
inline Spectrum fft(const std::complex<double>* x, std::size_t n) {
    Spectrum out;
    if (x == nullptr || !is_power_of_two(n)) {
        out.error = "fft: null input or length not a power of two";
        return out;
    }
    if (any_nonfinite(x, n)) {
        out.error = "fft: non-finite input sample";
        return out;
    }
    std::vector<std::complex<double>> a(x, x + n);

    // bit-reversal permutation
    for (std::size_t i = 1, j = 0; i < n; ++i) {
        std::size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (std::size_t len = 2; len <= n; len <<= 1) {
        const double ang = -2.0 * kPi / static_cast<double>(len);
        const std::complex<double> wlen(std::cos(ang), std::sin(ang));
        for (std::size_t i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            for (std::size_t k = 0; k < len / 2; ++k) {
                const std::complex<double> u = a[i + k];
                const std::complex<double> v = a[i + k + len / 2] * w;
                a[i + k] = u + v;
                a[i + k + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
    out.bins = std::move(a);
    out.valid = true;
    return out;
}

// --- window functions -------------------------------------------------------

// Periodic Hann window: w[k] = 0.5*(1 - cos(2*pi*k/n)), k=0..n-1.
// w[0]==0, w[n/2]==1 (peak), sum over one period == n/2.
inline std::vector<double> hann_window(std::size_t n) {
    std::vector<double> w(n);
    for (std::size_t k = 0; k < n; ++k)
        w[k] = 0.5 * (1.0 - std::cos(2.0 * kPi * static_cast<double>(k) /
                                    static_cast<double>(n)));
    return w;
}

// Apply a window in-place to a complex buffer.
inline void apply_window(std::vector<std::complex<double>>& x,
                         const std::vector<double>& w) {
    const std::size_t n = std::min(x.size(), w.size());
    for (std::size_t k = 0; k < n; ++k) x[k] *= w[k];
}

// --- magnitude / dB ---------------------------------------------------------

inline std::vector<double> magnitude(const std::vector<std::complex<double>>& x) {
    std::vector<double> m(x.size());
    for (std::size_t k = 0; k < x.size(); ++k) m[k] = std::abs(x[k]);
    return m;
}

// 20*log10(linear/ref).  Non-positive linear -> very negative sentinel.
inline double db_from_linear(double linear, double ref = 1.0) {
    if (!std::isfinite(linear) || !std::isfinite(ref) || linear <= 0.0 || ref <= 0.0)
        return -300.0;
    return 20.0 * std::log10(linear / ref);
}

// 10*log10(power/ref).
inline double db_from_power(double power, double ref = 1.0) {
    if (!std::isfinite(power) || !std::isfinite(ref) || power <= 0.0 || ref <= 0.0)
        return -300.0;
    return 10.0 * std::log10(power / ref);
}

// --- fftshift ---------------------------------------------------------------

// Shift the zero-frequency component to the centre (even-length spectra).
inline std::vector<double> fftshift(const std::vector<double>& x) {
    const std::size_t n = x.size();
    if (n < 2 || (n & 1u) != 0u) return x;  // odd/empty: unchanged (documented)
    std::vector<double> y(n);
    const std::size_t h = n / 2;
    for (std::size_t k = 0; k < n; ++k) y[k] = x[(k + h) % n];
    return y;
}

// --- frequency axis ---------------------------------------------------------

// Frequency (Hz) of each FFT bin.  Unshifted: [0, fs/2) then negative freqs.
// Shifted: [-fs/2, fs/2).
inline std::vector<double> freq_axis_hz(std::size_t n, double fs, bool shifted) {
    std::vector<double> f(n);
    const double df = fs / static_cast<double>(n);
    for (std::size_t k = 0; k < n; ++k) {
        const double half = static_cast<double>(n) / 2.0;
        double fr = static_cast<double>(k) * df;
        if (!shifted && k >= n / 2) fr -= fs;
        if (shifted) fr = (static_cast<double>(k) - half) * df;
        f[k] = fr;
    }
    return f;
}

// --- noise floor ------------------------------------------------------------

// Robust noise-floor estimate = median of the dB spectrum.
inline double noise_floor_db(const std::vector<double>& db) {
    if (db.empty()) return -300.0;
    std::vector<double> s = db;
    std::sort(s.begin(), s.end());
    const std::size_t n = s.size();
    return s[n / 2];
}

// --- peak detection ---------------------------------------------------------

struct Peak {
    std::size_t bin = 0;
    double value_db = -300.0;
    double freq_hz = 0.0;
};

// Local maxima of the dB spectrum that rise at least `above_noise_db` over the
// (median) noise floor, separated by at least `min_sep_bins` bins.  A peak is
// accepted if it is a strict local maximum over its neighbours.
inline std::vector<Peak> detect_peaks(const std::vector<double>& db, double fs,
                                      double above_noise_db,
                                      std::size_t min_sep_bins = 2) {
    std::vector<Peak> peaks;
    const std::size_t n = db.size();
    if (n < 3 || !std::isfinite(above_noise_db) || min_sep_bins == 0) return peaks;
    const double floor = noise_floor_db(db);
    const double thresh = floor + above_noise_db;
    const std::vector<double> f = freq_axis_hz(n, fs, /*shifted=*/false);
    for (std::size_t k = 1; k + 1 < n; ++k) {
        if (db[k] <= db[k - 1] || db[k] <= db[k + 1]) continue;  // not a max
        if (db[k] < thresh) continue;
        if (!peaks.empty() && k - peaks.back().bin < min_sep_bins) continue;
        peaks.push_back(Peak{k, db[k], f[k]});
    }
    return peaks;
}

// --- peak hold (max-hold across frames) -------------------------------------

struct PeakHold {
    std::vector<double> hold;

    void reset() { hold.clear(); }

    void update(const std::vector<double>& db) {
        if (db.empty()) return;
        if (hold.size() != db.size()) {
            hold = db;
            return;
        }
        for (std::size_t k = 0; k < db.size(); ++k)
            hold[k] = std::max(hold[k], db[k]);
    }
};

}  // namespace m24
