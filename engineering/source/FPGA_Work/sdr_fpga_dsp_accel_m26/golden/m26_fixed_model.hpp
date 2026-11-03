// M26 fixed-point bit-exact model — mirrors the RTL arithmetic (rtl/*.sv)
// one-for-one, following M26_FIXED_POINT_CONTRACT.md.  Used to validate the
// floating-point golden model against the exact fixed-point behaviour, so the
// numeric-alignment result is provable without a Vivado/xsim run.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <complex>
#include <vector>

namespace m26fixed {

using i16 = std::int16_t;
using i32 = std::int32_t;
using i64 = std::int64_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using u64 = std::uint64_t;
using cpx16 = struct { i16 re, im; };

// ---------------------------------------------------------------- quant helpers

inline double round_half_away(double v) { return v >= 0.0 ? std::floor(v + 0.5) : std::ceil(v - 0.5); }

// double -> int16 Q1.15 (round half away, symmetric saturate).
inline i16 q15(double x) {
    double r = round_half_away(x * 32768.0);
    if (r > 32767.0) return 32767;
    if (r < -32768.0) return -32768;
    return static_cast<i16>(r);
}

// arithmetic shift right (floor), matching RTL `>>>` / two's-complement ASR.
inline i64 sar(i64 v, int sh) {
    if (v >= 0) return v >> sh;
    return -(((-v) + ((i64{1} << sh) - 1)) >> sh);
}

// round-half-away-from-zero then arithmetic-shift by sh.
// For two's-complement arithmetic shift (floor), round-half-away is:
//   (v + half) >> sh        for v >= 0
//   (v + half - 1) >> sh    for v < 0   (add half-1 so the .5 tie moves away from 0)
inline i64 rshift_round(i64 v, int sh) {
    i64 half = i64{1} << (sh - 1);
    return (v + half - (v < 0 ? 1 : 0)) >> sh;
}

inline i64& sat_count() { static i64 c = 0; return c; }   // saturation-event counter (test harness)
inline void reset_sat_count() { sat_count() = 0; }

inline i16 sat16(i64 v) {
    if (v > 32767) { ++sat_count(); return 32767; }
    if (v < -32768) { ++sat_count(); return -32768; }
    return static_cast<i16>(v);
}

inline std::vector<i16> q15_array(const std::vector<double>& x) {
    std::vector<i16> r(x.size());
    for (std::size_t i = 0; i < x.size(); ++i) r[i] = q15(x[i]);
    return r;
}

inline std::vector<cpx16> q15_complex(const std::vector<std::complex<double>>& x) {
    std::vector<cpx16> r(x.size());
    for (std::size_t i = 0; i < x.size(); ++i) { r[i].re = q15(x[i].real()); r[i].im = q15(x[i].imag()); }
    return r;
}
inline std::vector<std::complex<double>> deq15(const std::vector<cpx16>& x) {
    std::vector<std::complex<double>> r(x.size());
    for (std::size_t i = 0; i < x.size(); ++i)
        r[i] = { static_cast<double>(x[i].re) / 32768.0, static_cast<double>(x[i].im) / 32768.0 };
    return r;
}

// ---------------------------------------------------------------- DC removal

// y[n] = x[n] - x[n-1] + R*y[n-1], R = 1 - 2^-7 (implemented as y - (y>>>7)).
// Internal state is kept in Q1.30 (contract §1, 36-bit accumulator) so the >>>7
// truncation floor sits at Q1.30 LSB (~1e-7) rather than at Q1.15; only the
// *output* is quantized to Q1.15 with round-half-away + symmetric saturation.
inline std::vector<cpx16> dc_removal(const std::vector<cpx16>& x) {
    std::vector<cpx16> y(x.size());
    i32 xd_re = 0, xd_im = 0;   // Q1.30
    i64 yd_re = 0, yd_im = 0;   // Q1.30 (kept wide so no intermediate truncation)
    for (std::size_t i = 0; i < x.size(); ++i) {
        i32 x_re = static_cast<i32>(x[i].re) << 15;   // Q1.15 -> Q1.30
        i32 x_im = static_cast<i32>(x[i].im) << 15;
        i64 re = static_cast<i64>(x_re) - xd_re + (yd_re - sar(yd_re, 7));
        i64 im = static_cast<i64>(x_im) - xd_im + (yd_im - sar(yd_im, 7));
        y[i].re = sat16(rshift_round(re, 15));        // Q1.30 -> Q1.15 (round + saturate)
        y[i].im = sat16(rshift_round(im, 15));
        xd_re = x_re; xd_im = x_im;
        yd_re = re; yd_im = im;                       // keep full Q1.30 state
    }
    return y;
}

// ---------------------------------------------------------------- energy / RMS

struct EnergyRms { u64 energy = 0; u16 rms = 0; u32 peak_power = 0; };

inline EnergyRms energy_rms(const std::vector<cpx16>& x) {
    EnergyRms r;
    u64 acc = 0;
    for (const auto& v : x) {
        u32 p = static_cast<u32>(static_cast<i64>(v.re) * v.re + static_cast<i64>(v.im) * v.im);
        acc += p;
        if (p > r.peak_power) r.peak_power = p;
    }
    r.energy = acc;                       // Q0.30, N samples
    // rms = sqrt(acc / N) in value units; quantize to u16 scale 2^15.
    double mean = static_cast<double>(acc) / 1073741824.0 / static_cast<double>(x.size());  // /2^30 /N
    double rmsv = std::sqrt(mean);
    double rq = round_half_away(rmsv * 32768.0);
    if (rq < 0.0) rq = 0.0;
    if (rq > 65535.0) rq = 65535.0;
    r.rms = static_cast<u16>(rq);
    return r;
}

// ---------------------------------------------------------------- signal presence

enum class Presence : int { NO_SIGNAL = 0, ACQUIRING = 1, SIGNAL_PRESENT = 2, SIGNAL_LOST = 3 };

inline std::vector<Presence> signal_presence(const std::vector<u16>& rms,
                                             u16 thr_enter, u16 thr_exit, int enter_m, int exit_n) {
    std::vector<Presence> out;
    Presence st = Presence::NO_SIGNAL;
    int above = 0, below = 0;
    for (u16 r : rms) {
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

inline std::vector<i16> build_sin_lut() {  // quarter-wave sin, 256 entries, Q1.15
    std::vector<i16> t(256);
    for (int j = 0; j < 256; ++j)
        t[static_cast<std::size_t>(j)] = q15(std::sin(static_cast<double>(j) * 3.141592653589793 / 512.0));
    return t;
}

inline const std::vector<i16>& sin_lut() {
    static const std::vector<i16> t = build_sin_lut();
    return t;
}

inline cpx16 nco_cossin(u32 phase) {   // returns (cos(theta), sin(theta)) Q1.15
    const auto& lut = sin_lut();
    u32 top = (phase >> 22) & 0x3FFu;   // 10 bits
    int quad = static_cast<int>(top >> 8);
    int idx = static_cast<int>(top & 0xFFu);
    cpx16 r;
    switch (quad) {
        case 0: r.re = lut[255 - idx]; r.im = lut[idx]; break;
        case 1: r.re = static_cast<i16>(-static_cast<int>(lut[idx])); r.im = lut[255 - idx]; break;
        case 2: r.re = static_cast<i16>(-static_cast<int>(lut[255 - idx])); r.im = static_cast<i16>(-static_cast<int>(lut[idx])); break;
        default: r.re = lut[idx]; r.im = static_cast<i16>(-static_cast<int>(lut[255 - idx])); break;
    }
    return r;
}

// y = x * exp(-j 2pi f/fs n), phase accumulator 32-bit, increment = round(f/fs*2^32).
inline std::vector<cpx16> nco_mix(const std::vector<cpx16>& x, double f, double fs) {
    std::vector<cpx16> y(x.size());
    u32 phase = 0;
    double inc_d = f / fs * 4294967296.0;
    i64 inc = static_cast<i64>(std::llround(inc_d));
    u32 inc_u = static_cast<u32>(inc);          // mod 2^32 wrap
    for (std::size_t i = 0; i < x.size(); ++i) {
        cpx16 cs = nco_cossin(phase);
        i64 re = static_cast<i64>(x[i].re) * cs.re + static_cast<i64>(x[i].im) * cs.im;   // Q2.30
        i64 im = static_cast<i64>(x[i].im) * cs.re - static_cast<i64>(x[i].re) * cs.im;
        y[i].re = sat16(rshift_round(re, 15));
        y[i].im = sat16(rshift_round(im, 15));
        phase += inc_u;
    }
    return y;
}

// ---------------------------------------------------------------- FIR (symmetric, folded)

inline std::vector<cpx16> fir_sym(const std::vector<cpx16>& x, const std::vector<i16>& h) {
    const int T = static_cast<int>(h.size());
    std::vector<cpx16> y(x.size());
    for (std::size_t n = 0; n < x.size(); ++n) {
        i64 re = 0, im = 0;
        for (int k = 0; k < T / 2; ++k) {
            int i0 = static_cast<int>(n) - k;
            int i1 = static_cast<int>(n) - (T - 1 - k);
            i64 xr = 0, xi = 0;
            if (i0 >= 0) { xr += x[static_cast<std::size_t>(i0)].re; xi += x[static_cast<std::size_t>(i0)].im; }
            if (i1 >= 0) { xr += x[static_cast<std::size_t>(i1)].re; xi += x[static_cast<std::size_t>(i1)].im; }
            re += xr * h[static_cast<std::size_t>(k)];
            im += xi * h[static_cast<std::size_t>(k)];
        }
        if (T % 2 == 1) {
            int ic = static_cast<int>(n) - T / 2;
            if (ic >= 0) {
                re += static_cast<i64>(x[static_cast<std::size_t>(ic)].re) * h[static_cast<std::size_t>(T / 2)];
                im += static_cast<i64>(x[static_cast<std::size_t>(ic)].im) * h[static_cast<std::size_t>(T / 2)];
            }
        }
        y[n].re = sat16(rshift_round(re, 15));
        y[n].im = sat16(rshift_round(im, 15));
    }
    return y;
}

// ---------------------------------------------------------------- decimate (structural)

inline std::vector<cpx16> decimate(const std::vector<cpx16>& x, int D) {
    std::vector<cpx16> y;
    for (std::size_t i = 0; i < x.size(); i += static_cast<std::size_t>(D)) y.push_back(x[i]);
    return y;
}

// ---------------------------------------------------------------- Hann

inline std::vector<cpx16> apply_hann(const std::vector<cpx16>& x, const std::vector<i16>& w) {
    std::vector<cpx16> y(x.size());
    for (std::size_t i = 0; i < x.size(); ++i) {
        y[i].re = sat16(rshift_round(static_cast<i64>(x[i].re) * w[i], 15));
        y[i].im = sat16(rshift_round(static_cast<i64>(x[i].im) * w[i], 15));
    }
    return y;
}

// ---------------------------------------------------------------- FFT (radix-2 DIT, per-stage 1/2)

inline std::vector<cpx16> build_twiddle(int N) {   // exp(-j 2pi m/N), Q1.15
    std::vector<cpx16> t(static_cast<std::size_t>(N));
    for (int m = 0; m < N; ++m) {
        double a = -2.0 * 3.141592653589793 * m / N;
        t[static_cast<std::size_t>(m)].re = q15(std::cos(a));
        t[static_cast<std::size_t>(m)].im = q15(std::sin(a));
    }
    return t;
}

inline void fft_radix2_inplace(std::vector<cpx16>& a) {
    const std::size_t n = a.size();
    const auto tw = build_twiddle(static_cast<int>(n));
    for (std::size_t i = 1, j = 0; i < n; ++i) {
        std::size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (std::size_t len = 2; len <= n; len <<= 1) {
        std::size_t step = n / len;
        for (std::size_t i = 0; i < n; i += len) {
            for (std::size_t k = 0; k < len / 2; ++k) {
                const cpx16 W = tw[k * step];
                const cpx16 A = a[i + k];
                const cpx16 B = a[i + k + len / 2];
                i64 tre = static_cast<i64>(B.re) * W.re - static_cast<i64>(B.im) * W.im;
                i64 tim = static_cast<i64>(B.re) * W.im + static_cast<i64>(B.im) * W.re;
                a[i + k].re = sat16(rshift_round((static_cast<i64>(A.re) << 15) + tre, 16));
                a[i + k].im = sat16(rshift_round((static_cast<i64>(A.im) << 15) + tim, 16));
                a[i + k + len / 2].re = sat16(rshift_round((static_cast<i64>(A.re) << 15) - tre, 16));
                a[i + k + len / 2].im = sat16(rshift_round((static_cast<i64>(A.im) << 15) - tim, 16));
            }
        }
    }
}

inline std::vector<cpx16> fft(const std::vector<cpx16>& x) {
    std::vector<cpx16> a = x;
    fft_radix2_inplace(a);
    return a;
}

// ---------------------------------------------------------------- fftshift (structural)

inline std::vector<cpx16> fftshift(const std::vector<cpx16>& X) {
    const std::size_t n = X.size();
    std::vector<cpx16> y(n);
    for (std::size_t k = 0; k < n; ++k) y[k] = X[(k + n / 2) % n];
    return y;
}

// ---------------------------------------------------------------- mag^2 (Q0.30, u32)

inline std::vector<u32> mag_sq(const std::vector<cpx16>& X) {
    std::vector<u32> p(X.size());
    for (std::size_t k = 0; k < X.size(); ++k)
        p[k] = static_cast<u32>(static_cast<i64>(X[k].re) * X[k].re + static_cast<i64>(X[k].im) * X[k].im);
    return p;
}

// ---------------------------------------------------------------- noise floor (median)

inline u32 noise_floor_median(const std::vector<u32>& p) {
    std::vector<u32> s = p;
    std::sort(s.begin(), s.end());
    return s[s.size() / 2];
}

// ---------------------------------------------------------------- CA-CFAR

inline std::vector<int> cfar(const std::vector<u32>& p, int guard, int ref, u32 threshold_scale_q214) {
    const int N = static_cast<int>(p.size());
    std::vector<int> mask(static_cast<std::size_t>(N), 0);
    for (int k = 0; k < N; ++k) {
        u64 sum = 0; int cnt = 0;
        for (int g = 1; g <= ref; ++g) {
            int lo = k - guard - g, hi = k + guard + g;
            if (lo >= 0) { sum += p[static_cast<std::size_t>(lo)]; ++cnt; }
            if (hi < N)  { sum += p[static_cast<std::size_t>(hi)]; ++cnt; }
        }
        if (cnt == 0) continue;
        // thr = T * mean = (threshold_scale_q214 / 2^14) * (sum/cnt)
        u64 thr = threshold_scale_q214 * sum / (static_cast<u64>(cnt) << 14);
        if (p[static_cast<std::size_t>(k)] > thr) mask[static_cast<std::size_t>(k)] = 1;
    }
    return mask;
}

// ---------------------------------------------------------------- candidate merge + 99% BW (structural, on mask+power)

struct Candidate { int start = 0; int end = 0; int peak_bin = 0; double power = 0.0;
                   double center_bin = 0.0; int bw_bins = 1; };

inline int occupied_bw_bins(const std::vector<u32>& p, const Candidate& c, double frac) {
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
        acc += static_cast<double>(p[static_cast<std::size_t>(k)]);
        lo = std::min(lo, k); hi = std::max(hi, k);
    }
    return hi - lo + 1;
}

inline std::vector<Candidate> candidate_merge(const std::vector<int>& mask, const std::vector<u32>& p,
                                              int merge_gap, int max_cand) {
    const int N = static_cast<int>(p.size());
    std::vector<Candidate> out;
    int i = 0;
    while (i < N) {
        while (i < N && !mask[static_cast<std::size_t>(i)]) ++i;
        if (i >= N) break;
        int start = i, end = i, j = i + 1;
        while (j < N) {
            if (mask[static_cast<std::size_t>(j)]) { end = j; ++j; }
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
        double power = 0.0; int peak = start; u32 pk = 0;
        for (int k = start; k <= end; ++k) { power += p[static_cast<std::size_t>(k)];
            if (p[static_cast<std::size_t>(k)] > pk) { pk = p[static_cast<std::size_t>(k)]; peak = k; } }
        double wsum = 0.0, sum = 0.0;
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

}  // namespace m26fixed
