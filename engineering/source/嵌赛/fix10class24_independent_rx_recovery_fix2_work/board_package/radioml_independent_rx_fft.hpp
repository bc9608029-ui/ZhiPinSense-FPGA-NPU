#pragma once

// radioml_independent_rx_fft.hpp -- fix2 B-line: a self-contained radix-2 complex FFT
// used to turn the O(N*K) ZC-preamble sync search into O(N log N) cross-correlation.
//
// Why a private FFT instead of reusing an existing one: the sync search must produce
// the SAME offset / no-sync decision as the exact brute force (byte-identical score at
// the returned offset), and must compile identically on the host (g++) and the aarch64
// board with NO iCraft / libiio / external dependency.  A tiny in-place iterative
// Cooley-Tukey FFT keeps that guarantee self-contained and auditable.
//
// Numeric contract: the FFT result is used ONLY to locate the ARGMAX of the
// correlation magnitude |R[m]|.  The caller then re-evaluates the EXACT brute-force
// score over a guard band around that argmax, so the returned score/offset are
// bit-identical to the full brute force -- FFT rounding never reaches the output.
//
// iCraft-free / libiio-free (header-only, host == board).

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <utility>
#include <vector>

namespace iqindepfix1 {

constexpr double kFftPi = 3.141592653589793238462643383279502884;

// In-place iterative radix-2 Cooley-Tukey FFT.  inverse=false -> forward transform
// (exp(-j*2pi*k*n/N)); inverse=true -> exp(+j*2pi*k*n/N) with NO 1/N scaling (the
// caller applies 1/N when it needs the true inverse).  `n` must be a power of two.
inline void fft_radix2(std::vector<std::complex<double>>& a, bool inverse) {
    const std::size_t n = a.size();
    // Bit-reversal permutation.
    for (std::size_t i = 1, j = 0; i < n; ++i) {
        std::size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    const double sign = inverse ? 1.0 : -1.0;
    for (std::size_t len = 2; len <= n; len <<= 1) {
        const double ang = sign * 2.0 * kFftPi / static_cast<double>(len);
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
}

// Smallest power of two >= n (n >= 1).
inline std::size_t next_pow2(std::size_t n) {
    std::size_t p = 1;
    while (p < n) p <<= 1;
    return p;
}

// Linear cross-correlation R[m] = sum_k rx[m+k] * conj(pre[k]) for m in [0, limit],
// computed by zero-padded FFT convolution.  The caller guarantees rx.size() >= limit+K
// (only the first limit+K rx samples affect the requested lags).  Returned length is
// limit+1.
//
//   Let g[k] = conj(pre[K-1-k]); then (rx * g)[n] = sum_k rx[n-K+1+k] conj(pre[k]),
//   so R[m] = (rx * g)[m + K - 1].  The FFT size is the next power of two
//   >= rx_len + K - 1, which makes the circular convolution equal the linear one.
inline std::vector<std::complex<double>> cross_correlate(
        const std::vector<std::complex<double>>& rx,
        const std::vector<std::complex<double>>& pre,
        std::size_t limit) {
    const std::size_t K = pre.size();
    const std::size_t rx_len = limit + K;
    const std::size_t N = next_pow2(rx_len + K - 1);
    std::vector<std::complex<double>> A(N, std::complex<double>(0.0, 0.0));
    std::vector<std::complex<double>> B(N, std::complex<double>(0.0, 0.0));
    for (std::size_t k = 0; k < rx_len; ++k) A[k] = rx[k];
    for (std::size_t k = 0; k < K; ++k) B[k] = std::conj(pre[K - 1 - k]);
    fft_radix2(A, false);
    fft_radix2(B, false);
    for (std::size_t i = 0; i < N; ++i) A[i] *= B[i];
    fft_radix2(A, true);
    const double inv = 1.0 / static_cast<double>(N);
    std::vector<std::complex<double>> R(limit + 1);
    for (std::size_t m = 0; m <= limit; ++m)
        R[m] = A[m + K - 1] * inv;
    return R;
}

}  // namespace iqindepfix1
