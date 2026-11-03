#pragma once

// synthetic_iq_generator.hpp — deterministic RRC pulse-shaped modulation
// waveform generator for Stage G synthetic-IQ injection (routes B/C).
//
// iCraft-free / libiio-free: host-testable (WSL g++), so the B-vs-C waveform
// fidelity (does the 2.56 MSPS -> 128 kSPS production decimation chain preserve
// the waveform?) is proven BEFORE the board run.  The board runner composes the
// same primitives and, for route C, feeds the int16 output through the real
// chain::PreprocessChain (chain_common.hpp).
//
// Design contract (task 39e5 Stage G):
//   * Symbols are drawn ONCE from a seeded RNG as a shared *index* stream, then
//     mapped to constellation points.  Route B (128 kSPS, 8 sps) and route C
//     (2.56 MSPS, 160 sps) therefore share the SAME symbol sequence and
//     constellation mapping by construction — only the upsample factor differs.
//   * One continuous RRC-shaped waveform is generated and the startup/end filter
//     transient is discarded; the caller slices 1024-sample (at 128 kSPS) windows
//     from the steady-state portion.  The filter is NEVER re-initialized per
//     window (no per-frame phase discontinuity).
//   * Normalization is an explicit, global strategy (never per-class):
//       "none"          leave the natural RRC output (its average power is ~1.0
//                       because every constellation is unit-power and the RRC is
//                       unit-energy-per-symbol).
//       "complex-rms-1" rescale so the complex RMS == 1.0 exactly.
//   * Every constellation is normalized to unit average power (E[|s|^2] == 1.0),
//     so no class ever needs a different scale.

#include <complex>
#include <cstdint>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace syniq {

constexpr double kPi = 3.14159265358979323846;

enum class Modulation { BPSK, QPSK, ASK4, QAM16 };

inline const char* modulation_name(Modulation m) {
    switch (m) {
        case Modulation::BPSK:  return "BPSK";
        case Modulation::QPSK:  return "QPSK";
        case Modulation::ASK4:  return "4ASK";
        case Modulation::QAM16: return "16QAM";
    }
    return "?";
}

// Parse "BPSK" | "QPSK" | "4ASK" | "16QAM"; throws on anything else (fail-closed).
inline Modulation parse_modulation(const std::string& s) {
    if (s == "BPSK")  return Modulation::BPSK;
    if (s == "QPSK")  return Modulation::QPSK;
    if (s == "4ASK")  return Modulation::ASK4;
    if (s == "16QAM") return Modulation::QAM16;
    throw std::runtime_error("unknown modulation: " + s);
}

inline int constellation_size(Modulation m) {
    switch (m) {
        case Modulation::BPSK:  return 2;
        case Modulation::QPSK:  return 4;
        case Modulation::ASK4:  return 4;
        case Modulation::QAM16: return 16;
    }
    return 0;
}

// Fixed constellation point for a symbol index 0..(size-1).  Every constellation
// has unit average power (mean over all points of |s|^2 == 1.0); Gray-coded where
// applicable (QPSK / 16QAM).  Deterministic: same index -> same point, always.
inline std::complex<double> map_symbol(Modulation m, int idx) {
    switch (m) {
        case Modulation::BPSK: {
            // {+1, -1} on I, unit amplitude
            return (idx & 1) ? std::complex<double>(-1.0, 0.0)
                             : std::complex<double>(1.0, 0.0);
        }
        case Modulation::QPSK: {
            // Gray 4-PSK, unit amplitude
            static const std::complex<double> t[4] = {
                { 0.7071067811865475,  0.7071067811865475},   // 00 -> (+,+)
                {-0.7071067811865475,  0.7071067811865475},   // 01 -> (-,+)
                {-0.7071067811865475, -0.7071067811865475},   // 11 -> (-,-)
                { 0.7071067811865475, -0.7071067811865475},   // 10 -> (+,-)
            };
            return t[idx & 3];
        }
        case Modulation::ASK4: {
            // 4-ASK levels {-3,-1,+1,+3}/sqrt(5), unit average power
            static const double lvl[4] = {
                -1.3416407864998738, -0.4472135954999579,
                 0.4472135954999579,  1.3416407864998738,
            };
            return std::complex<double>(lvl[idx & 3], 0.0);
        }
        case Modulation::QAM16: {
            // 16-QAM {I,Q} in {+-1,+-3}/sqrt(10), unit average power
            static const int lvl[4] = {-3, -1, 1, 3};
            const double q = 0.31622776601683794;  // 1/sqrt(10)
            const int r = lvl[(idx >> 2) & 3];
            const int c = lvl[idx & 3];
            return std::complex<double>(r * q, c * q);
        }
    }
    return std::complex<double>(0.0, 0.0);
}

// Root-raised-cosine filter: `sps` samples/symbol, rolloff `beta`, `span_symbols`
// symbols of support.  Returns span*sps + 1 taps (centered).  Normalized to
// unit energy per symbol (sum(h^2) == sps), so a unit-power symbol stream maps to
// a unit-power pulse-shaped waveform.  The t==0 and t==+-1/(4 beta) singularities
// are handled with their closed-form limits.
inline std::vector<double> rrc_coeffs(int sps, double beta, int span_symbols) {
    const double T = static_cast<double>(sps);
    const int n = span_symbols * sps;
    std::vector<double> h(n + 1, 0.0);
    const double center = static_cast<double>(n) / 2.0;
    const double tc = 1.0 / (4.0 * beta);
    for (int i = 0; i <= n; ++i) {
        const double t = (static_cast<double>(i) - center) / T;  // symbol periods
        if (std::abs(t) < 1e-9) {
            h[i] = 1.0 - beta + 4.0 * beta / kPi;
        } else if (std::abs(std::abs(t) - tc) < 1e-9) {
            h[i] = (beta / std::sqrt(2.0)) *
                   ((1.0 + 2.0 / kPi) * std::sin(kPi / (4.0 * beta)) +
                    (1.0 - 2.0 / kPi) * std::cos(kPi / (4.0 * beta)));
        } else {
            const double num = std::sin(kPi * t * (1.0 - beta)) +
                               4.0 * beta * t * std::cos(kPi * t * (1.0 + beta));
            const double den = kPi * t * (1.0 - (4.0 * beta * t) * (4.0 * beta * t));
            h[i] = num / den;
        }
    }
    double e = 0.0;
    for (double v : h) e += v * v;
    const double scale = std::sqrt(e / T);   // => sum(h^2) == sps
    for (double& v : h) v /= scale;
    return h;
}

// Shared seeded symbol-index stream (0 .. size-1), identical for every route that
// uses the same (modulation, seed, n_symbols).
inline std::vector<int> symbol_indices(Modulation m, std::uint64_t seed,
                                       int n_symbols) {
    std::mt19937_64 rng(seed);
    std::uniform_int_distribution<int> dist(0, constellation_size(m) - 1);
    std::vector<int> idx(static_cast<std::size_t>(n_symbols));
    for (int i = 0; i < n_symbols; ++i) idx[static_cast<std::size_t>(i)] = dist(rng);
    return idx;
}

// Pulse-shape a symbol-index stream with an RRC at `sps` samples/symbol.  Returns
// the steady-state portion (startup/end transient discarded) of length
// (n_symbols - span_symbols) * sps.  Sparse convolution (only symbol positions are
// non-zero) so it is O(n_symbols * taps), not O(n_samples * taps).
inline std::vector<std::complex<double>> pulse_shape(
        const std::vector<int>& sym_idx, Modulation m, int sps, double beta,
        int span_symbols) {
    const int n_sym = static_cast<int>(sym_idx.size());
    if (n_sym <= span_symbols)
        throw std::runtime_error("pulse_shape: need more symbols than the RRC span");
    const std::vector<double> h = rrc_coeffs(sps, beta, span_symbols);
    const int taps = static_cast<int>(h.size());            // span*sps + 1
    const int y_len = n_sym * sps + taps - 1;
    std::vector<std::complex<double>> y(static_cast<std::size_t>(y_len), 0.0);
    for (int k = 0; k < n_sym; ++k) {
        const std::complex<double> s = map_symbol(m, sym_idx[k]);
        const int base = k * sps;
        for (int t = 0; t < taps; ++t) y[static_cast<std::size_t>(base + t)] += s * h[static_cast<std::size_t>(t)];
    }
    // Steady state: symbols [span/2, n_sym - span/2) are fully convolved.  Group
    // delay = (taps-1)/2 = span*sps/2; first fully-convolved output starts at
    // group-delay + (span/2)*sps == span*sps.
    const int start = (taps - 1) / 2 + (span_symbols / 2) * sps;
    const int out_len = (n_sym - span_symbols) * sps;
    return std::vector<std::complex<double>>(y.begin() + start,
                                             y.begin() + start + out_len);
}

// Global normalization strategy.  Throws on any strategy other than the two legal
// ones (fail-closed; the set is deliberately closed).
inline void apply_normalization(std::vector<std::complex<double>>& x,
                                const std::string& norm) {
    if (norm == "none") return;
    if (norm == "complex-rms-1") {
        double e = 0.0;
        for (const auto& v : x) e += std::norm(v);
        if (e <= 0.0) return;
        const double rms = std::sqrt(e / static_cast<double>(x.size()));
        for (auto& v : x) v /= rms;
        return;
    }
    throw std::runtime_error("unknown normalization strategy: " + norm);
}

// int16 quantization statistics (recorded verbatim in the manifest).
struct QuantStats {
    double rms_counts = 0.0;   // post-quantization complex RMS, in int16 counts
    double peak_counts = 0.0;  // post-quantization peak |I|/|Q| component
    std::size_t clip = 0;      // number of I/Q components clamped at +-32768
};

// Quantize a complex waveform to interleaved int16 with a target complex RMS
// (sqrt(mean(|x|^2))) of `rms_counts`, in int16-count units.  The scale is ONE
// global scalar for the whole waveform — never per-class, never per-frame.
// `st` receives the measured post-quantization RMS / peak / clip count so the
// manifest can record the *actual* effective values, not just the requested one.
inline std::vector<std::int16_t> quantize_int16(
        const std::vector<std::complex<double>>& x, double rms_counts,
        QuantStats& st) {
    double e = 0.0;
    for (const auto& v : x) e += std::norm(v);
    const double rms = std::sqrt(e / static_cast<double>(x.size()));
    const double scale = (rms > 0.0) ? (rms_counts / rms) : 0.0;

    std::vector<std::int16_t> iq(x.size() * 2);
    double peak = 0.0;
    st.clip = 0;
    for (std::size_t k = 0; k < x.size(); ++k) {
        double ri = x[k].real() * scale;
        double qi = x[k].imag() * scale;
        if (ri > 32767.0) { ri = 32767.0; ++st.clip; }
        else if (ri < -32768.0) { ri = -32768.0; ++st.clip; }
        if (qi > 32767.0) { qi = 32767.0; ++st.clip; }
        else if (qi < -32768.0) { qi = -32768.0; ++st.clip; }
        iq[k * 2]     = static_cast<std::int16_t>(std::lround(ri));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::lround(qi));
        peak = std::max(peak, std::max(std::abs(ri), std::abs(qi)));
    }
    double e2 = 0.0;
    for (std::int16_t v : iq) e2 += static_cast<double>(v) * static_cast<double>(v);
    // complex RMS from int16 components: sqrt(mean(I^2 + Q^2))
    st.rms_counts = std::sqrt(e2 / static_cast<double>(x.size()));
    st.peak_counts = peak;
    return iq;
}

}  // namespace syniq
