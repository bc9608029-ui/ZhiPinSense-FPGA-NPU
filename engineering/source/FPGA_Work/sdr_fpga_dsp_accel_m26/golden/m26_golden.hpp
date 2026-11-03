// M26-A / M26-B floating-point golden reference models.
//
// Self-contained (no FFTW, no external deps): radix-2 DIT FFT in double, Hann,
// noise floor, CA-CFAR, candidate merge and 99%-power bandwidth, mirroring the
// CPU M24-A golden (`m24_fft.hpp`) semantics (unnormalized FFT, |X[m]| = A*n).
//
// These are the *reference* against which the fixed-point bit-exact model
// (m26_fixed_model.hpp) and the RTL (rtl/*.sv) are validated.  They never touch
// any production RTL/XDC/bitstream.
#pragma once

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <vector>

namespace m26golden {

using cpx = std::complex<double>;

// ---------------------------------------------------------------- stimulus

// Deterministic Gaussian noise (box-muller), seeded.
struct Rng {
    std::uint64_t s;
    explicit Rng(std::uint64_t seed) : s(seed) {}
    std::uint64_t next() {           // xorshift64*
        std::uint64_t x = s;
        x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
        s = x;
        return x * 0x2545F4914F6CDD1DULL;
    }
    double uniform() { return (next() >> 11) * (1.0 / 9007199254740992.0); }
    double gauss() {
        double u1 = uniform(); if (u1 == 0.0) u1 = 1e-12;
        double u2 = uniform();
        return std::sqrt(-2.0 * std::log(u1)) * std::cos(2.0 * 3.141592653589793 * u2);
    }
};

// ---------------------------------------------------------------- DC removal

// First-order high-pass: y[n] = x[n] - x[n-1] + R*y[n-1].
inline std::vector<cpx> dc_removal(const std::vector<cpx>& x, double R = 127.0 / 128.0) {
    std::vector<cpx> y(x.size());
    cpx xd{0, 0}, yd{0, 0};
    for (std::size_t i = 0; i < x.size(); ++i) {
        cpx v = x[i] - xd + R * yd;
        y[i] = v; xd = x[i]; yd = v;
    }
    return y;
}

// ---------------------------------------------------------------- energy / RMS

struct EnergyRms { double energy = 0.0; double rms = 0.0; double peak_power = 0.0; };

inline EnergyRms energy_rms(const std::vector<cpx>& x) {
    EnergyRms r;
    for (const auto& v : x) {
        double p = std::norm(v);
        r.energy += p;
        if (p > r.peak_power) r.peak_power = p;
    }
    r.rms = std::sqrt(r.energy / static_cast<double>(x.size()));
    return r;
}

// ---------------------------------------------------------------- signal presence

enum class Presence { NO_SIGNAL = 0, ACQUIRING = 1, SIGNAL_PRESENT = 2, SIGNAL_LOST = 3 };

// Hysteretic energy threshold + N/M frame hysteresis (mirrors signal_presence.hpp).
inline std::vector<Presence> signal_presence(const std::vector<double>& rms,
                                             double thr_enter, double thr_exit,
                                             int enter_m, int exit_n) {
    std::vector<Presence> out;
    Presence st = Presence::NO_SIGNAL;
    int above = 0, below = 0;
    for (double r : rms) {
        switch (st) {
            case Presence::NO_SIGNAL:
                if (r >= thr_enter) { if (++above >= enter_m) { st = Presence::SIGNAL_PRESENT; above = 0; } }
                else above = 0;
                break;
            case Presence::SIGNAL_PRESENT:
                if (r <= thr_exit) { if (++below >= exit_n) { st = Presence::NO_SIGNAL; below = 0; } }
                else below = 0;
                break;
            default: break;
        }
        out.push_back(st);
    }
    return out;
}

// ---------------------------------------------------------------- NCO

inline std::vector<cpx> nco_mix(const std::vector<cpx>& x, double f, double fs) {
    std::vector<cpx> y(x.size());
    const double w = -2.0 * 3.141592653589793 * f / fs;  // exp(-j 2pi f/fs n)
    for (std::size_t i = 0; i < x.size(); ++i)
        y[i] = x[i] * std::complex<double>(std::cos(w * static_cast<double>(i)),
                                           std::sin(w * static_cast<double>(i)));
    return y;
}

// ---------------------------------------------------------------- FIR

inline std::vector<cpx> fir(const std::vector<cpx>& x, const std::vector<double>& coeff) {
    std::vector<cpx> y(x.size());
    const int T = static_cast<int>(coeff.size());
    for (std::size_t n = 0; n < x.size(); ++n) {
        cpx acc{0, 0};
        for (int k = 0; k < T; ++k) {
            int idx = static_cast<int>(n) - k;
            if (idx >= 0) acc += x[static_cast<std::size_t>(idx)] * coeff[static_cast<std::size_t>(k)];
        }
        y[n] = acc;
    }
    return y;
}

// Low-pass FIR design (windowed sinc) for decimation anti-aliasing.
inline std::vector<double> design_lowpass(int taps, double cutoff_norm, double fs) {
    (void)fs;
    std::vector<double> h(static_cast<std::size_t>(taps));
    const int M = taps - 1;
    const double fc = cutoff_norm;  // normalized to fs (0..0.5)
    for (int i = 0; i < taps; ++i) {
        double n = static_cast<double>(i) - M / 2.0;
        double hamm = 0.54 - 0.46 * std::cos(2.0 * 3.141592653589793 * i / M);
        double sinc = (n == 0.0) ? 2.0 * fc : std::sin(2.0 * 3.141592653589793 * fc * n) / (3.141592653589793 * n);
        h[static_cast<std::size_t>(i)] = sinc * hamm;
    }
    // Normalize DC gain to 1.0.
    double s = 0.0; for (double v : h) s += v;
    if (s != 0.0) for (double& v : h) v /= s;
    return h;
}

// ---------------------------------------------------------------- decimate

inline std::vector<cpx> decimate(const std::vector<cpx>& x, int D) {
    std::vector<cpx> y;
    for (std::size_t i = 0; i < x.size(); i += static_cast<std::size_t>(D)) y.push_back(x[i]);
    return y;
}

// ---------------------------------------------------------------- Hann

inline std::vector<double> hann_window(int N) {
    std::vector<double> w(static_cast<std::size_t>(N));
    for (int n = 0; n < N; ++n)
        w[static_cast<std::size_t>(n)] = 0.5 - 0.5 * std::cos(2.0 * 3.141592653589793 * n / N);
    return w;
}

inline std::vector<cpx> apply_hann(const std::vector<cpx>& x, const std::vector<double>& w) {
    std::vector<cpx> y(x.size());
    for (std::size_t i = 0; i < x.size(); ++i) y[i] = x[i] * w[i];
    return y;
}

// ---------------------------------------------------------------- FFT (radix-2 DIT, unnormalized)

inline void fft_radix2_inplace(std::vector<cpx>& a, bool invert) {
    const std::size_t n = a.size();
    for (std::size_t i = 1, j = 0; i < n; ++i) {
        std::size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (std::size_t len = 2; len <= n; len <<= 1) {
        double ang = 2.0 * 3.141592653589793 / static_cast<double>(len) * (invert ? 1.0 : -1.0);
        cpx wlen(std::cos(ang), std::sin(ang));
        for (std::size_t i = 0; i < n; i += len) {
            cpx w(1, 0);
            for (std::size_t k = 0; k < len / 2; ++k) {
                cpx u = a[i + k], v = a[i + k + len / 2] * w;
                a[i + k] = u + v;
                a[i + k + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

inline std::vector<cpx> fft(const std::vector<cpx>& x) {
    std::vector<cpx> a = x;
    fft_radix2_inplace(a, false);
    return a;
}

// ---------------------------------------------------------------- fftshift

inline std::vector<cpx> fftshift(const std::vector<cpx>& X) {
    const std::size_t n = X.size();
    std::vector<cpx> y(n);
    for (std::size_t k = 0; k < n; ++k) y[k] = X[(k + n / 2) % n];
    return y;
}

// ---------------------------------------------------------------- mag^2

inline std::vector<double> mag_sq(const std::vector<cpx>& X) {
    std::vector<double> p(X.size());
    for (std::size_t k = 0; k < X.size(); ++k) p[k] = std::norm(X[k]);
    return p;
}

// ---------------------------------------------------------------- noise floor (median)

inline double noise_floor_median(const std::vector<double>& p) {
    std::vector<double> s = p;
    std::sort(s.begin(), s.end());
    return s[s.size() / 2];
}

// ---------------------------------------------------------------- CA-CFAR

inline std::vector<int> cfar(const std::vector<double>& p, int guard, int ref, double threshold_scale) {
    const int N = static_cast<int>(p.size());
    std::vector<int> mask(static_cast<std::size_t>(N), 0);
    for (int k = 0; k < N; ++k) {
        double sum = 0.0; int cnt = 0;
        for (int g = 1; g <= ref; ++g) {
            int lo = k - guard - g, hi = k + guard + g;
            if (lo >= 0) { sum += p[static_cast<std::size_t>(lo)]; ++cnt; }
            if (hi < N)  { sum += p[static_cast<std::size_t>(hi)]; ++cnt; }
        }
        if (cnt == 0) continue;
        double thr = threshold_scale * (sum / cnt);
        if (p[static_cast<std::size_t>(k)] > thr) mask[static_cast<std::size_t>(k)] = 1;
    }
    return mask;
}

// ---------------------------------------------------------------- candidate merge + 99% BW

struct Candidate { int start = 0; int end = 0; int peak_bin = 0; double power = 0.0;
                   double center_bin = 0.0; int bw_bins = 1; };

int occupied_bw_bins(const std::vector<double>& p, const Candidate& c, double frac);

inline std::vector<Candidate> candidate_merge(const std::vector<int>& mask,
                                              const std::vector<double>& p,
                                              int merge_gap, int max_cand) {
    const int N = static_cast<int>(p.size());
    std::vector<Candidate> out;
    int i = 0;
    while (i < N) {
        while (i < N && !mask[static_cast<std::size_t>(i)]) ++i;
        if (i >= N) break;
        int start = i, end = i;
        int j = i + 1;
        while (j < N) {
            if (mask[static_cast<std::size_t>(j)]) { end = j; j++; }
            else {
                // Count consecutive zero bins; bridge to the next detection iff the
                // gap (number of zero bins) is <= merge_gap (contract §13), matching
                // the RTL S_GAP state in m26_candidate_merge.sv.
                int gpos = j, gap = 0;
                while (gpos < N && !mask[static_cast<std::size_t>(gpos)]) { ++gap; ++gpos; }
                if (gpos >= N) break;                          // no further detection
                if (gap <= merge_gap) { end = gpos; j = gpos + 1; }
                else break;
            }
        }
        double power = 0.0; int peak = start; double pk = -1.0;
        for (int k = start; k <= end; ++k) { power += p[static_cast<std::size_t>(k)];
            if (p[static_cast<std::size_t>(k)] > pk) { pk = p[static_cast<std::size_t>(k)]; peak = k; } }
        double wsum = 0.0; double sum = 0.0;
        for (int k = start; k <= end; ++k) { wsum += p[static_cast<std::size_t>(k)] * k; sum += p[static_cast<std::size_t>(k)]; }
        Candidate c;
        c.start = start; c.end = end; c.peak_bin = peak; c.power = power;
        c.center_bin = (sum > 0) ? wsum / sum : static_cast<double>(peak);
        c.bw_bins = occupied_bw_bins(p, c, 0.99);
        out.push_back(c);
        i = end + 1;
    }
    if (static_cast<int>(out.size()) > max_cand) out.resize(static_cast<std::size_t>(max_cand));
    return out;
}

// 99%-power bandwidth: grow from peak bin outward by descending power until 99% of total.
inline int occupied_bw_bins(const std::vector<double>& p, const Candidate& c, double frac) {
    const double ptot = c.power;
    if (ptot <= 0.0 || c.end == c.start) return 1;
    std::vector<int> order;
    for (int k = c.start; k <= c.end; ++k) order.push_back(k);
    std::sort(order.begin(), order.end(), [&](int a, int b) {
        return p[static_cast<std::size_t>(a)] > p[static_cast<std::size_t>(b)];
    });
    double acc = 0.0; int lo = c.peak_bin, hi = c.peak_bin;
    for (int k : order) {
        if (acc >= frac * ptot) break;
        acc += p[static_cast<std::size_t>(k)];
        lo = std::min(lo, k); hi = std::max(hi, k);
    }
    return hi - lo + 1;
}

}  // namespace m26golden
