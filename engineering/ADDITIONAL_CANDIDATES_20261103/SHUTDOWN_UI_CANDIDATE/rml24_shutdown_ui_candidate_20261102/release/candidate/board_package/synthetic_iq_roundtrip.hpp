#pragma once

// synthetic_iq_roundtrip.hpp — Stage G route D: RadioML round-trip preprocess.
//
// Route D answers a question none of routes A/B/C can: does the PRODUCTION receive
// preprocess chain (int16 -> ÷2048 -> NCO off -> 2.56M -> 128k polyphase decimation
// -> ×rec_scale) preserve a real RadioML sample's category and logits?  It takes the
// exact same frozen RadioML test tensor route A feeds the NPU, and pushes it through
//
//   [2,1024] fp32 @128k  ->  combine to complex  ->  deterministic ×20 polyphase FIR
//   interpolation to 2.56 MSPS  ->  explicit unified amplitude mapping  ->  int16
//   interleaved "raw RX"  ->  REAL production chain::PreprocessChain  ->  recovered
//   [2,1024] fp32  ->  NPU24  ->  merge23  ->  result
//
// and compares the recovered tensor/logits one-to-one against route A's original.
//
// This header is iCraft-free and libiio-free: it PRODUCES the recovered tensor and
// the A-vs-D fidelity metrics but never opens a device and never runs the NPU.  The
// board runner (board_gate9_full_chain_rml23.cpp) composes it with NpuClassifier24.
//
// Route D hard requirements honoured here (task 39e5 Stage G):
//   1. A and D share the exact same frozen test tensor/source_index/label/SNR (the
//      board runner feeds the SAME loaded route-A tensor into both paths).
//   2. No copied/approximate preprocess: the decimation side is the literal
//      chain::PreprocessChain (chain_common.hpp), the same class route C uses.
//   3. The interpolator is a deterministic FIR / polyphase implementation (a
//      Blackman-Harris windowed-sinc prototype decomposed into 20 polyphase
//      branches).  LINEAR INTERPOLATION IS NEVER USED.
//   4. The interpolator identity (coefficient design, length, group delay,
//      frequency response) is recorded verbatim -- see interpolation_identity().
//   5. Finite 1024 samples: explicit deterministic guard padding (never cyclic
//      splice, never cross-sample boundary feed).  edge_policy and the valid
//      centre interval are recorded; both full-1024 and edge-excluded error are
//      reported (nmse_full vs nmse_center).
//   6. A-vs-D metrics: integer time-delay alignment, optimal single complex
//      gain/phase, NMSE, EVM, correlation, RMS/DC/PAPR, and (diagnostic-only, never
//      auto-selected) I/Q swap and conjugation checks.  PSD / 90-95-99% OBW are
//      computed by scripts/analyze_roundtrip_stage_g.py from the saved artifacts.
//   10. The recovered tensor is a pure function of the input, so re-inferring it
//       (the board runner's bit-identical replay) is the model-input invariance.

#include "chain_common.hpp"
#include "synthetic_iq_generator.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace syniq_rt {

constexpr double kPiRt = 3.141592653589793238462643383279502884;

// ---------------------------------------------------------------------------
// Interpolator identity (recorded verbatim, requirement 4).
// ---------------------------------------------------------------------------
constexpr int kInterpFactor = 20;          // 128 kSPS -> 2.56 MSPS (up=20, down=1)
constexpr int kInterpTapsPerPhase = 32;    // polyphase branch taps
constexpr std::size_t kInterpTapsTotal =    // 20 * 32 == 640
    static_cast<std::size_t>(kInterpFactor) * kInterpTapsPerPhase;
constexpr double kInterpCutoffHz = 64000.0;      // input Nyquist (128k / 2)
constexpr double kInterpFsOutHz = 2560000.0;     // output rate
constexpr double kInterpGroupDelay =              // (N-1)/2 output samples == 319.5
    (static_cast<double>(kInterpTapsTotal) - 1.0) / 2.0;
constexpr const char* kInterpWindow = "Blackman-Harris-4";  // a0=.35875 a1=.48829
                                                            // a2=.14128 a3=.01168

// Edge / guard policy (requirement 5).
constexpr int kEdgeMargin = 32;   // valid centre = [32, 1024-32) in the aligned frame
// Guard on each side of the finite 1024-sample signal (deterministic pad, never
// cyclic splice).  The production decimation FIR discards its FIRST
// (taps_total-1) = 600 OUTPUT samples (@128k) as transient before the first valid
// recovered sample, so to yield >= 2 full [2,1024] recovered tensors we need
//     valid = (1024 + 2*guard) - 600 >= 2048  =>  guard >= 812.
// 832 leaves margin (valid == 2088 == 2 tensors + 40).  The larger guard also
// means the aligned delay offset is ~ a few hundred samples; that is measured by
// the cross-correlation, not hard-coded.
constexpr int kGuard = 832;

struct InterpIdentity {
    int up = kInterpFactor;
    int down = 1;
    std::size_t taps_total = kInterpTapsTotal;
    int taps_per_phase = kInterpTapsPerPhase;
    double cutoff_hz = kInterpCutoffHz;
    double fs_out_hz = kInterpFsOutHz;
    double group_delay_out = kInterpGroupDelay;   // output samples (half-integer)
    double dc_gain_total = static_cast<double>(kInterpFactor);  // sum(h) == up
    const char* window = kInterpWindow;
};

inline InterpIdentity interpolation_identity() { return InterpIdentity{}; }

inline double sinc_rt(double x) {
    if (std::fabs(x) < 1e-12) return 1.0;
    const double px = kPiRt * x;
    return std::sin(px) / px;
}

// Blackman-Harris 4-term symmetric window (pure cosines -> bit-stable across
// host/board libm; no Bessel I0, no exp).
inline double blackman_harris4(std::size_t n, std::size_t N) {
    const double a0 = 0.35875, a1 = 0.48829, a2 = 0.14128, a3 = 0.01168;
    const double t = 2.0 * kPiRt * static_cast<double>(n) / static_cast<double>(N - 1);
    return a0 - a1 * std::cos(t) + a2 * std::cos(2.0 * t) - a3 * std::cos(3.0 * t);
}

// Deterministic ×20 interpolation prototype.  h[n] = L * sinc((n - centre)/L) *
// BH4 window, length kInterpTapsTotal, then globally scaled so sum(h) == L (each
// polyphase branch therefore has DC gain ~1.0).  Type-II even symmetry
// (h[n] == h[N-1-n]), group delay (N-1)/2 == 319.5 output samples.
inline std::vector<double> interpolation_fir() {
    const std::size_t N = kInterpTapsTotal;
    const double L = static_cast<double>(kInterpFactor);
    const double centre = static_cast<double>(N - 1) / 2.0;
    std::vector<double> h(N, 0.0);
    for (std::size_t n = 0; n < N; ++n) {
        const double x = (static_cast<double>(n) - centre) / L;
        h[n] = L * sinc_rt(x) * blackman_harris4(n, N);
    }
    double S = 0.0;
    for (double v : h) S += v;
    for (double& v : h) v *= L / S;
    return h;
}

// Deterministic polyphase FIR interpolation (up=L, down=1), zero-pad "same-size"
// convention:  y[m] = sum_k h[(m mod L) + k*L] * x[floor(m/L) - k],  x[j] treated
// as 0 outside [0, len).  Output length == L * x.size().  NOT linear interpolation.
inline std::vector<std::complex<double>> interpolate_20x(
        const std::vector<std::complex<double>>& x, const std::vector<double>& h) {
    const std::size_t L = static_cast<std::size_t>(kInterpFactor);
    const std::size_t p = h.size() / L;
    if (p * L != h.size())
        throw std::runtime_error("roundtrip: interpolation FIR length not a multiple of 20");
    const std::size_t out_len = x.size() * L;
    std::vector<std::complex<double>> y(out_len, 0.0);
    for (std::size_t m = 0; m < out_len; ++m) {
        const std::size_t i = m / L;
        const std::uint32_t r = static_cast<std::uint32_t>(m % L);
        std::complex<double> acc(0.0, 0.0);
        for (std::size_t k = 0; k < p; ++k) {
            const std::int64_t j = static_cast<std::int64_t>(i) - static_cast<std::int64_t>(k);
            if (j >= 0 && j < static_cast<std::int64_t>(x.size()))
                acc += h[r + k * L] * x[static_cast<std::size_t>(j)];
        }
        y[m] = acc;
    }
    return y;
}

// ---------------------------------------------------------------------------
// Edge policy (requirement 5): deterministic guard, never cyclic splice.
// ---------------------------------------------------------------------------
enum class EdgePolicy { Zero, Reflect };

inline EdgePolicy parse_edge_policy(const std::string& s) {
    if (s == "zero") return EdgePolicy::Zero;
    if (s == "reflect") return EdgePolicy::Reflect;
    throw std::runtime_error("unknown --edge-policy: " + s + " (use zero|reflect)");
}

inline const char* edge_policy_name(EdgePolicy p) {
    return (p == EdgePolicy::Zero) ? "zero" : "reflect";
}

inline std::vector<std::complex<double>> apply_guard(
        const std::vector<std::complex<double>>& x, int guard, EdgePolicy p) {
    if (guard < 0)
        throw std::runtime_error("roundtrip: negative guard");
    const std::size_t N = x.size();
    if (N == 0)
        throw std::runtime_error("roundtrip: empty input");
    const std::size_t g = static_cast<std::size_t>(guard);
    std::vector<std::complex<double>> out;
    out.reserve(N + 2 * g);
    if (p == EdgePolicy::Zero) {
        out.insert(out.end(), g, {0.0, 0.0});
        out.insert(out.end(), x.begin(), x.end());
        out.insert(out.end(), g, {0.0, 0.0});
    } else {  // Reflect: numpy-style mirror (no boundary repeat), deterministic.
        if (g >= N)
            throw std::runtime_error("roundtrip: reflect guard must be < signal length");
        for (std::size_t i = g; i > 0; --i) out.push_back(x[i]);        // x[g..1]
        out.insert(out.end(), x.begin(), x.end());                      // x[0..N-1]
        for (std::size_t i = 0; i < g; ++i) out.push_back(x[N - 2 - i]);  // x[N-2..N-1-g]
    }
    return out;
}

// ---------------------------------------------------------------------------
// Round-trip config + result.
// ---------------------------------------------------------------------------
struct RoundtripConfig {
    int interpolation_factor = kInterpFactor;
    double rms_counts = 16.0;      // unified int16 complex RMS (== route C default)
    float rec_scale = -1.0f;       // <=0 -> calibrate_rec_scale(rms_counts, 1.0)
    EdgePolicy edge_policy = EdgePolicy::Zero;
    int guard = kGuard;
    std::uint32_t fs_in = 2560000; // the production RX sample rate
};

// A-vs-D fidelity metrics (requirement 6, in-board subset; PSD/OBW in Python).
struct RoundtripMetrics {
    int delay_offset = 0;          // recovered[delay + i] ~ original[i] (integer)
    double gain_db = 0.0;          // optimal single complex gain, 20 log10 |g|
    double phase_deg = 0.0;        // optimal single complex phase, degrees
    double nmse_full = 0.0;        // all 1024 samples
    double nmse_center = 0.0;      // valid centre [kEdgeMargin, 1024-kEdgeMargin)
    double evm_center_pct = 0.0;   // 100 * sqrt(nmse_center)
    double corr_center = 0.0;      // |correlation| over centre
    double rms_orig = 0.0, rms_recov = 0.0;
    double dc_orig = 0.0, dc_recov = 0.0;      // |mean| of each
    double papr_orig_db = 0.0, papr_recov_db = 0.0;
    double corr_swap = 0.0;        // diagnostic: original vs I<->Q swapped recovered
    double corr_conj = 0.0;        // diagnostic: original vs conjugated recovered
    int center_lo = kEdgeMargin;
    int center_hi = static_cast<int>(chain::kFrameComplex) - kEdgeMargin;
};

struct RoundtripResult {
    std::vector<float> recovered_tensor;          // [2,1024] aligned to original
    std::vector<std::complex<double>> original_complex;    // 1024
    std::vector<std::complex<double>> interpolated_complex;  // 20 * padded len
    std::vector<std::int16_t> quantized_iq;       // interleaved int16 (raw RX)
    RoundtripMetrics metrics;
    syniq::QuantStats quant;                      // measured int16 RMS/peak/clip
    std::string edge_policy;
    int guard = 0;
    double rec_scale_used = 1.0;
};

// Combine a [2,1024] planar tensor (plane0=I, plane1=Q) into 1024 complex.
inline std::vector<std::complex<double>> tensor_to_complex(const float* t) {
    std::vector<std::complex<double>> z(chain::kFrameComplex);
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
        z[k] = std::complex<double>(static_cast<double>(t[k]),
                                    static_cast<double>(t[chain::kFrameComplex + k]));
    return z;
}

// Align + measure (requirement 6).  z = original 1024, rv = recovered stream
// (>= 1024 + 1 samples, delayed relative to z).  Finds the integer delay and the
// optimal single complex gain/phase over the valid centre, then reports full and
// centre NMSE.  The I/Q swap and conjugation correlations are diagnostic only.
inline RoundtripMetrics compute_roundtrip_metrics(
        const std::vector<std::complex<double>>& z,
        const std::vector<std::complex<double>>& rv) {
    const std::size_t N = chain::kFrameComplex;
    if (z.size() != N)
        throw std::runtime_error("roundtrip: original not 1024 complex");
    if (rv.size() < N + 1)
        throw std::runtime_error("roundtrip: recovered stream too short to align");

    const int dmax = static_cast<int>(rv.size() - N);
    const int lo = kEdgeMargin, hi = static_cast<int>(N) - kEdgeMargin;

    // 1. best integer delay: minimise centre NMSE (each candidate gets its own LS
    //    gain, so a pure delay/scale is never penalised as distortion).
    int best_d = 0;
    double best_err = std::numeric_limits<double>::infinity();
    for (int d = 0; d <= dmax; ++d) {
        std::complex<double> num(0.0, 0.0), den(0.0, 0.0);
        for (int i = lo; i < hi; ++i) {
            num += z[static_cast<std::size_t>(i)] *
                   std::conj(rv[static_cast<std::size_t>(d + i)]);
            den += rv[static_cast<std::size_t>(d + i)] *
                   std::conj(rv[static_cast<std::size_t>(d + i)]);
        }
        if (std::abs(den) < 1e-30) continue;
        const std::complex<double> g = num / den;
        double err = 0.0;
        for (int i = lo; i < hi; ++i)
            err += std::norm(z[static_cast<std::size_t>(i)] -
                             g * rv[static_cast<std::size_t>(d + i)]);
        if (err < best_err) { best_err = err; best_d = d; }
    }

    // 2. final LS gain/phase over the centre at the chosen delay.
    std::complex<double> num(0.0, 0.0), den(0.0, 0.0);
    for (int i = lo; i < hi; ++i) {
        num += z[static_cast<std::size_t>(i)] *
               std::conj(rv[static_cast<std::size_t>(best_d + i)]);
        den += rv[static_cast<std::size_t>(best_d + i)] *
               std::conj(rv[static_cast<std::size_t>(best_d + i)]);
    }
    const std::complex<double> g = (std::abs(den) > 1e-30)
        ? num / den : std::complex<double>(1.0, 0.0);

    RoundtripMetrics m;
    m.delay_offset = best_d;
    m.gain_db = 20.0 * std::log10(std::abs(g) + 1e-300);
    m.phase_deg = std::arg(g) * 180.0 / kPiRt;
    m.center_lo = lo; m.center_hi = hi;

    double err_c = 0.0, ref_c = 0.0, err_f = 0.0, ref_f = 0.0;
    std::complex<double> cc(0.0, 0.0);
    double az = 0.0, ar = 0.0;
    for (std::size_t i = 0; i < N; ++i) {
        const auto e = z[i] - g * rv[static_cast<std::size_t>(best_d + i)];
        err_f += std::norm(e);
        ref_f += std::norm(z[i]);
        if (static_cast<int>(i) >= lo && static_cast<int>(i) < hi) {
            err_c += std::norm(e);
            ref_c += std::norm(z[i]);
            cc += z[i] * std::conj(rv[static_cast<std::size_t>(best_d + i)]);
            az += std::norm(z[i]);
            ar += std::norm(rv[static_cast<std::size_t>(best_d + i)]);
        }
    }
    m.nmse_center = ref_c > 0.0 ? err_c / ref_c : 0.0;
    m.nmse_full = ref_f > 0.0 ? err_f / ref_f : 0.0;
    m.evm_center_pct = 100.0 * std::sqrt(m.nmse_center);
    m.corr_center = std::sqrt(az * ar) > 0.0
                        ? std::abs(cc) / std::sqrt(az * ar) : 0.0;

    // RMS / DC / PAPR over the aligned 1024.
    double eo = 0.0, er = 0.0, peak_o = 0.0, peak_r = 0.0;
    std::complex<double> so(0.0, 0.0), sr(0.0, 0.0);
    for (std::size_t i = 0; i < N; ++i) {
        const auto& o = z[i];
        const auto& r = rv[static_cast<std::size_t>(best_d + i)];
        eo += std::norm(o); er += std::norm(r);
        peak_o = std::max(peak_o, std::norm(o));
        peak_r = std::max(peak_r, std::norm(r));
        so += o; sr += r;
    }
    m.rms_orig = std::sqrt(eo / static_cast<double>(N));
    m.rms_recov = std::sqrt(er / static_cast<double>(N));
    m.dc_orig = std::abs(so) / static_cast<double>(N);
    m.dc_recov = std::abs(sr) / static_cast<double>(N);
    m.papr_orig_db = m.rms_orig > 0.0
                         ? 10.0 * std::log10(peak_o / (m.rms_orig * m.rms_orig)) : 0.0;
    m.papr_recov_db = m.rms_recov > 0.0
                          ? 10.0 * std::log10(peak_r / (m.rms_recov * m.rms_recov)) : 0.0;

    // Diagnostic-only I/Q swap / conjugation correlations (never auto-selected).
    std::complex<double> cswap(0.0, 0.0), cconj(0.0, 0.0);
    for (int i = lo; i < hi; ++i) {
        const auto& o = z[static_cast<std::size_t>(i)];
        const auto& r = rv[static_cast<std::size_t>(best_d + i)];
        cswap += o * std::conj(std::complex<double>(r.imag(), r.real()));
        cconj += o * std::conj(std::conj(r));
    }
    m.corr_swap = std::sqrt(az * ar) > 0.0 ? std::abs(cswap) / std::sqrt(az * ar) : 0.0;
    m.corr_conj = std::sqrt(az * ar) > 0.0 ? std::abs(cconj) / std::sqrt(az * ar) : 0.0;
    return m;
}

// Explicit unified amplitude mapping ("显式统一幅度映射").  Quantize the
// interpolated stream to interleaved int16 so the SIGNAL portion (whose true
// complex RMS is `signal_rms`, measured on the pre-guard original) lands at
// `rms_counts` int16 counts.  ONE global scalar for the whole stream — never
// per-class, never per-frame — and the zero/reflect guard is deliberately NOT
// allowed to dilute the amplitude reference (that dilution is exactly what an
// "explicit" mapping forbids).  Mirrors syniq::quantize_int16's rounding/clamp
// (std::lround, clamp to +-32767/-32768) so the signal portion is bit-identical
// to what route C's production quantizer emits for the same waveform.
inline std::vector<std::int16_t> quantize_int16_signal_rms(
        const std::vector<std::complex<double>>& x, double signal_rms,
        double rms_counts, syniq::QuantStats& st) {
    const double scale = (signal_rms > 0.0) ? (rms_counts / signal_rms) : 0.0;
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
    st.rms_counts = std::sqrt(e2 / static_cast<double>(x.size()));
    st.peak_counts = peak;
    return iq;
}

// The full route-D chain for ONE original [2,1024] tensor.  Pure/deterministic:
// same input -> bit-identical recovered tensor and metrics (requirement 10 at the
// tensor level; the NPU-level invariance is the board runner's replay).
inline RoundtripResult roundtrip_radioml(const float* original_tensor,
                                         const RoundtripConfig& cfg) {
    if (cfg.interpolation_factor != kInterpFactor)
        throw std::runtime_error("roundtrip: interpolation factor must be 20");

    RoundtripResult out;
    out.edge_policy = edge_policy_name(cfg.edge_policy);
    out.guard = cfg.guard;

    // 1. combine planar [2,1024] -> complex.
    out.original_complex = tensor_to_complex(original_tensor);

    // Signal RMS (pre-guard) — the explicit amplitude reference.
    double signal_e = 0.0;
    for (const auto& v : out.original_complex) signal_e += std::norm(v);
    const double signal_rms =
        std::sqrt(signal_e / static_cast<double>(out.original_complex.size()));

    // 2. deterministic guard.
    const auto guarded = apply_guard(out.original_complex, cfg.guard, cfg.edge_policy);

    // 3. deterministic ×20 polyphase interpolation.
    const std::vector<double> fir = interpolation_fir();
    out.interpolated_complex = interpolate_20x(guarded, fir);

    // 4. explicit unified amplitude mapping + int16 quantization.
    out.quantized_iq = quantize_int16_signal_rms(out.interpolated_complex, signal_rms,
                                                 cfg.rms_counts, out.quant);

    // 5. REAL production PreprocessChain (÷2048 -> NCO off -> decimate -> ×rec_scale).
    const float rec = (cfg.rec_scale > 0.0f)
                          ? cfg.rec_scale
                          : chain::calibrate_rec_scale(cfg.rms_counts,
                                                       chain::kTargetModelRms);
    out.rec_scale_used = rec;
    chain::PreprocessChain pc(cfg.fs_in, 0.0, rec);
    pc.push_int16(out.quantized_iq.data(), out.quantized_iq.size() / 2);

    std::vector<std::complex<double>> recovered;
    for (int f = 0; f < 2; ++f) {   // up to 2 [2,1024] tensors
        std::vector<float> t(chain::kTensorFloats);
        if (!pc.pull_tensor(t.data())) break;
        for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
            recovered.emplace_back(static_cast<double>(t[k]),
                                   static_cast<double>(t[chain::kFrameComplex + k]));
    }

    // 6. align + measure, then extract the aligned [2,1024] recovered tensor.
    out.metrics = compute_roundtrip_metrics(out.original_complex, recovered);
    const int d = out.metrics.delay_offset;
    out.recovered_tensor.assign(chain::kTensorFloats, 0.0f);
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
        const auto& s = recovered[static_cast<std::size_t>(d + static_cast<int>(k))];
        out.recovered_tensor[k] = static_cast<float>(s.real());
        out.recovered_tensor[chain::kFrameComplex + k] = static_cast<float>(s.imag());
    }
    return out;
}

}  // namespace syniq_rt
