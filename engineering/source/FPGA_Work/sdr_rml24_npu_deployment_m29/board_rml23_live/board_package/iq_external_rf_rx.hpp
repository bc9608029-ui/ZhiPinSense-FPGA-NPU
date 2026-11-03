#pragma once

// iq_external_rf_rx.hpp -- Route G fix10: the board-side RX-ONLY runner that
// receives the PC-transmitted air-interface frame over a 50-ohm coax and recovers
// the D2 payload through frame sync / CFO / SRO / phase estimation, then restores
// and classifies it (23-class accuracy + confusion matrix).  It is the RX half of
// the two-binary architecture; the TX half is tools/pluto_external_tx.cpp.  Both
// share board_package/iq_external_rf_frame.hpp for the frame structure.
//
// Because the TX Pluto and the RX Pluto run on INDEPENDENT crystals, the receiver
// faces, for the first time, a real (unknown) carrier-frequency offset, sampling-
// rate offset, frame start and RF phase.  These are recovered ENTIRELY from the
// category-independent parts of the frame (preamble A / header sync word / tail
// preamble) -- never from the payload label -- via:
//
//   1. S&C coarse CFO        (lag-16 autocorrelation, unambiguous +/-80 kHz;
//                             the 16-sample CAZAC preamble A is built for this);
//   2. coarse CFO compensation (phase ramp in the absolute RX sample index);
//   3. frame-start matched filter on the 2048-sample DOUBLE preamble (unique peak
//      -- a 1024-sample pattern would match BOTH copies of preamble A);
//   4. fine CFO + phase      (two-half LS over the 1024-sample preamble at
//      frame_start, unambiguous +/-2.5 kHz, covering the S&C residual);
//   5. residual-CFO compensation RELATIVE TO frame_start -- the key trick: this
//      absorbs the RF phase AND the per-file 2*pi*f_coarse*fs0/fs phase, so the
//      recovered signal is r_final[n] = |g_rf| * frame[n] with a REAL-positive
//      global gain (no per-file phase to cancel later);
//   6. tail matched filter   (single 1024-sample preamble) -> SRO estimate;
//   7. payload extraction with fractional linear interpolation on the SRO grid;
//   8. scale-invariant fidelity (corr / normalized_residual / SNR / clip) vs the
//      KNOWN payload (the receiver knows the TX waveform it is expecting).
//
// The recovered payload then flows through the SAME D2 restore chain as fix9
// (chain::PreprocessChain -> iqrfloop::apply_global_gain_to_stream ->
// iqdloop::apply_d2_restore_to_stream -> iqdloop::select_classification_window ->
// npu.infer -> rml23::merge_logits_23 -> argmax).  Only the ONE global RF gain
// (median |g_rf| over the calibration subset) may undo the RF amplitude; CFO/SRO/
// phase are per-file physical quantities recovered from the category-independent
// preamble, so they leak no label.
//
// RF safety (RX-only, see the fix10 task book S1.2): the board's OWN TX is stopped
// and read back (!tx_running), the digital loopback is forced off (get_loopback()==
// 0), --rx-gain starts at 0 dB, no antenna / no amplifier (50-ohm coax, --rf-path=
// direct-cable is required).  Every timeout / exception / SIGINT / device break
// unwinds through the guard and leaves no cyclic TX running.
//
// iCraft-free and libiio-free: the NPU wrapper is a TEMPLATE parameter, so the
// header compiles and is host-tested without iCraft (the DSP primitives and
// process_rx_window are exercised directly by host_tests/test_iq_external_rf_rx_23class.cpp).

#include "iq_external_rf_frame.hpp"
#include "chain_common.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_rf_loopback.hpp"
#include "rml23_merged.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace extrf {

// ---- RX-only observation thresholds (measurement-only; never a PASS gate) ----
constexpr std::size_t kCaptureComplex = 2 * frame::kTotalFrameComplex;  // 156544
constexpr double kSyncCorrThreshold = 0.5;   // frame-start matched-filter peak
constexpr double kNoSignalRms = 2.0;         // RX RMS (counts) below this -> no signal

// Verdicts beyond the shared iqrfloop:: set (RF_PRESERVES_IQ / RF_RX_TOO_LOW /
// RF_RX_CLIPPED / RF_SYNC_NOT_FOUND / RF_DISTORTS_IQ / RF_PATH_NOT_PROVEN are reused).
constexpr const char* kVerdictNoSignal = "RF_NO_SIGNAL";
constexpr const char* kVerdictCfoOutOfRange = "RF_CFO_OUT_OF_RANGE";
constexpr const char* kVerdictSroOutOfRange = "RF_SRO_OUT_OF_RANGE";
constexpr const char* kVerdictInsufficientEvidence = "INSUFFICIENT_EVIDENCE";

// ---------------------------------------------------------------------------
// Pure DSP primitives (host-testable, no device, no NPU).
// ---------------------------------------------------------------------------
namespace dsp {

using Cplx = std::complex<double>;

inline std::vector<Cplx> to_complex(const std::vector<std::int16_t>& iq) {
    std::vector<Cplx> out(iq.size() / 2);
    for (std::size_t k = 0; k < out.size(); ++k)
        out[k] = Cplx(static_cast<double>(iq[k * 2 + 0]),
                      static_cast<double>(iq[k * 2 + 1]));
    return out;
}

inline double rms(const std::vector<Cplx>& v) {
    if (v.empty()) return 0.0;
    double s = 0.0;
    for (const auto& x : v) s += std::norm(x);
    return std::sqrt(s / static_cast<double>(v.size()));
}

// Multiply z by exp(-j*theta) in place (the CFO/phase compensation direction).
inline void multiply_exp_neg_jtheta(Cplx& z, double theta) {
    const double c = std::cos(theta), s = std::sin(theta);
    const double I = z.real(), Q = z.imag();
    z = Cplx(I * c + Q * s, Q * c - I * s);
}

// Compensate a CFO as a phase ramp in the ABSOLUTE sample index n.
inline void compensate_cfo_absolute(std::vector<Cplx>& r, double cfo_hz, double fs) {
    const double w = 2.0 * frame::kPi * cfo_hz / fs;
    for (std::size_t n = 0; n < r.size(); ++n)
        multiply_exp_neg_jtheta(r[n], w * static_cast<double>(n));
}

struct CoarseCfo {
    double cfo_hz = 0.0;
    std::size_t peak = 0;
    bool found = false;
};

// S&C lag-16 coarse CFO.  P[n] = sum_{m=0..win-1} r[n+m]*conj(r[n+m-lag]); the
// preamble's lag-16 self-similarity (16-sample CAZAC repeated 64x) makes |P[n]|
// peak over the preamble and arg(P[n]) = 2*pi*lag*cfo/fs, constant across it.
inline CoarseCfo estimate_coarse_cfo(const std::vector<Cplx>& r, double fs) {
    CoarseCfo out;
    const std::size_t N = r.size();
    const std::size_t lag = frame::kPreambleUnitComplex;  // 16
    const std::size_t win = 64;
    if (N < lag + win + 1) return out;
    double best = -1.0;
    std::size_t best_n = lag;
    for (std::size_t n = lag; n + win <= N; ++n) {
        Cplx acc(0.0, 0.0);
        for (std::size_t m = 0; m < win; ++m)
            acc += r[n + m] * std::conj(r[n + m - lag]);
        const double mag = std::abs(acc);
        if (mag > best) { best = mag; best_n = n; }
    }
    out.peak = best_n;
    Cplx acc(0.0, 0.0);
    for (std::size_t m = 0; m < win; ++m)
        acc += r[best_n + m] * std::conj(r[best_n + m - lag]);
    const double mag = std::abs(acc);
    if (mag <= 0.0) return out;
    out.cfo_hz = std::arg(acc) * fs / (2.0 * frame::kPi * static_cast<double>(lag));
    out.found = true;
    return out;
}

struct MatchedPeak {
    std::size_t index = 0;
    double corr = 0.0;
    bool found = false;
};

// Normalized cross-correlation peak of `pattern` over sig[search_start, search_end).
// corr = |sum sig*conj(pattern)| / sqrt(sum|sig|^2 * sum|pattern|^2) in [0,1].
inline MatchedPeak matched_filter_peak(const std::vector<Cplx>& sig,
                                       const std::vector<Cplx>& pattern,
                                       std::size_t search_start,
                                       std::size_t search_end) {
    MatchedPeak out;
    const std::size_t P = pattern.size();
    const std::size_t N = sig.size();
    if (P == 0 || search_end <= search_start || search_start >= N) return out;
    if (search_end > N) search_end = N;
    if (search_end <= P) return out;
    double ep = 0.0;
    for (const auto& x : pattern) ep += std::norm(x);
    if (ep <= 0.0) return out;
    double best = -1.0;
    std::size_t bi = search_start;
    for (std::size_t n = search_start; n + P <= search_end; ++n) {
        Cplx acc(0.0, 0.0);
        double es = 0.0;
        for (std::size_t m = 0; m < P; ++m) {
            acc += sig[n + m] * std::conj(pattern[m]);
            es += std::norm(sig[n + m]);
        }
        const double corr = std::abs(acc) / std::sqrt(es * ep);
        if (corr > best) { best = corr; bi = n; }
    }
    out.index = bi;
    out.corr = best;
    out.found = (best > 0.0);
    return out;
}

struct FineCfoPhase {
    double residual_cfo_hz = 0.0;
    double phase_rad = 0.0;   // phase at frame_start (k=0 of the preamble)
    bool found = false;
};

// Two-half LS over the 1024-sample preamble at frame_start: g1 over [0,512), g2
// over [512,1024); residual CFO from arg(g2*conj(g1)), phase at frame_start from
// arg(g1) minus the half-window midpoint phase.
inline FineCfoPhase estimate_fine_cfo_phase(const std::vector<Cplx>& rc,
                                            std::size_t frame_start,
                                            const std::vector<Cplx>& preamble,
                                            double fs) {
    FineCfoPhase out;
    const std::size_t L = preamble.size();
    if (L < 2 || frame_start + L > rc.size()) return out;
    const std::size_t half = L / 2;
    Cplx g1(0.0, 0.0), g2(0.0, 0.0);
    for (std::size_t k = 0; k < half; ++k) {
        g1 += rc[frame_start + k] * std::conj(preamble[k]);
        g2 += rc[frame_start + half + k] * std::conj(preamble[half + k]);
    }
    if (std::abs(g1) < 1e-12 || std::abs(g2) < 1e-12) return out;
    const double dphi = std::arg(g2 * std::conj(g1));
    out.residual_cfo_hz = dphi * fs / (2.0 * frame::kPi * static_cast<double>(half));
    const double midpoint_phase =
        out.residual_cfo_hz * 2.0 * frame::kPi * (static_cast<double>(half) - 0.5) / (2.0 * fs);
    out.phase_rad = std::arg(g1) - midpoint_phase;
    out.found = true;
    return out;
}

// Compensate the RESIDUAL CFO and initial phase RELATIVE TO frame_start.  This is
// what makes the global gain real-positive (absorbs the RF phase + the coarse-CFO
// per-file phase), so the calibration subset only ever fits one real amplitude.
inline void compensate_residual(std::vector<Cplx>& rc, std::size_t frame_start,
                                double residual_cfo_hz, double phase_rad, double fs) {
    const double w = 2.0 * frame::kPi * residual_cfo_hz / fs;
    for (std::size_t n = 0; n < rc.size(); ++n) {
        const double d = static_cast<double>(static_cast<std::ptrdiff_t>(n)) -
                         static_cast<double>(static_cast<std::ptrdiff_t>(frame_start));
        multiply_exp_neg_jtheta(rc[n], w * d + phase_rad);
    }
}

// Normalized cross-correlation magnitude of `pattern` at a single lag `n` of `sig`
// (no search; used for sub-sample peak refinement).
inline double matched_filter_corr(const std::vector<Cplx>& sig,
                                  const std::vector<Cplx>& pattern,
                                  std::size_t n) {
    const std::size_t P = pattern.size();
    if (P == 0 || n + P > sig.size()) return 0.0;
    Cplx acc(0.0, 0.0);
    double es = 0.0;
    for (std::size_t m = 0; m < P; ++m) {
        acc += sig[n + m] * std::conj(pattern[m]);
        es += std::norm(sig[n + m]);
    }
    double ep = 0.0;
    for (const auto& x : pattern) ep += std::norm(x);
    if (es <= 0.0 || ep <= 0.0) return 0.0;
    return std::abs(acc) / std::sqrt(es * ep);
}

struct SroEstimate {
    std::size_t tail_index = 0;      // integer lag of the tail-matched-filter peak
    double tail_position = 0.0;      // sub-sample refined tail position (RX index)
    double sro_ppm = 0.0;
};

// Tail re-synchronization + SRO.  The tail preamble (single 1024-sample A) sits at
// TX index kTailStart; its RX position minus frame_start equals kTailStart/(1+sro).
// The integer matched-filter peak is refined to sub-sample via a 3-point parabolic
// interpolation of the correlation magnitude, so the SRO granularity is well under
// 1 ppm (an integer-only estimate quantizes to ~16 ppm, leaving a ~0.5-sample
// residual drift across the 53760-sample payload).
inline SroEstimate estimate_sro_from_tail(const std::vector<Cplx>& rf,
                                          double frame_start,
                                          const std::vector<Cplx>& tail_pattern,
                                          double /*fs*/) {
    SroEstimate out;
    const std::size_t exp = static_cast<std::size_t>(std::llround(frame_start)) +
                            frame::kTailStart;
    const std::size_t margin = 256;
    const std::size_t lo = (exp > margin) ? (exp - margin) : 0;
    const MatchedPeak mp = matched_filter_peak(rf, tail_pattern, lo, exp + margin);
    out.tail_index = mp.index;
    if (!mp.found) return out;

    double pos = static_cast<double>(mp.index);
    const std::size_t p = mp.index;
    if (p > lo && p + tail_pattern.size() + 1 <= rf.size()) {
        const double c0 = matched_filter_corr(rf, tail_pattern, p - 1);
        const double c1 = mp.corr;
        const double c2 = matched_filter_corr(rf, tail_pattern, p + 1);
        const double denom = c0 - 2.0 * c1 + c2;
        if (std::fabs(denom) > 1e-12) {
            double delta = 0.5 * (c0 - c2) / denom;
            if (delta < -1.0) delta = -1.0;
            if (delta > 1.0) delta = 1.0;
            pos += delta;
        }
    }
    out.tail_position = pos;

    const double d = pos - frame_start;
    if (d <= 0.0) return out;
    const double ratio =
        static_cast<double>(frame::kTailStart) / d;
    out.sro_ppm = (ratio - 1.0) * 1e6;
    return out;
}

// Extract the 53760-complex payload from the compensated signal by fractional
// linear interpolation on the SRO grid: TX index kPayloadStart+t lives at RX index
// frame_start + (kPayloadStart+t)/(1+sro).  Quantized back to int16 (the D2 restore
// chain's input domain).
inline std::vector<std::int16_t> extract_payload(const std::vector<Cplx>& rf,
                                                 double frame_start,
                                                 double sro_ppm) {
    const double sro = sro_ppm * 1e-6;
    const std::size_t L = frame::kPayloadComplex;
    const std::size_t N = rf.size();
    std::vector<std::int16_t> out(L * 2);
    for (std::size_t t = 0; t < L; ++t) {
        const double m = frame_start +
                         static_cast<double>(frame::kPayloadStart + t) / (1.0 + sro);
        const double fm = std::floor(m);
        const std::size_t i0 = static_cast<std::size_t>(fm);
        const std::size_t i1 = i0 + 1;
        const double frac = m - fm;
        Cplx v;
        if (i1 < N) {
            v = rf[i0] * (1.0 - frac) + rf[i1] * frac;
        } else {
            v = rf[i0];
        }
        const double ri = std::max(-32768.0, std::min(32767.0, std::round(v.real())));
        const double rq = std::max(-32768.0, std::min(32767.0, std::round(v.imag())));
        out[t * 2 + 0] = static_cast<std::int16_t>(ri);
        out[t * 2 + 1] = static_cast<std::int16_t>(rq);
    }
    return out;
}

struct Fidelity {
    Cplx gain{0.0, 0.0};
    double corr = 0.0;
    double normalized_residual = 0.0;
    double payload_rms = 0.0;
};

// Scale-invariant aligned fidelity: LS complex gain, |correlation|, and the
// scale-independent normalized residual ||extracted - g*known|| / ||extracted||.
inline Fidelity aligned_fidelity(const std::vector<Cplx>& extracted,
                                 const std::vector<Cplx>& known) {
    Fidelity f;
    const std::size_t N = known.size();
    if (extracted.size() != N || N == 0) return f;
    Cplx acc(0.0, 0.0);
    double ek = 0.0, ex = 0.0;
    for (std::size_t k = 0; k < N; ++k) {
        acc += extracted[k] * std::conj(known[k]);
        ek += std::norm(known[k]);
        ex += std::norm(extracted[k]);
    }
    if (ek <= 0.0 || ex <= 0.0) return f;
    f.gain = acc / ek;
    f.corr = std::abs(acc) / std::sqrt(ek * ex);
    double resid = 0.0;
    for (std::size_t k = 0; k < N; ++k) {
        const Cplx e = extracted[k] - f.gain * known[k];
        resid += std::norm(e);
    }
    f.normalized_residual = std::sqrt(resid / ex);
    f.payload_rms = std::sqrt(ex / static_cast<double>(N));
    return f;
}

// Noise floor from the trailing silence region (TX zeros -> RX is pure noise).
inline double trailing_silence_rms(const std::vector<Cplx>& rf,
                                   std::size_t frame_start, double sro_ppm) {
    const double sro = sro_ppm * 1e-6;
    const std::size_t N = rf.size();
    const std::size_t begin_tx = frame::kTailStart + frame::kTailComplex;  // 61888
    const std::size_t end_tx = begin_tx + frame::kSilenceComplex;          // 70080
    const double m0 = static_cast<double>(frame_start) +
                      static_cast<double>(begin_tx) / (1.0 + sro);
    const double m1 = static_cast<double>(frame_start) +
                      static_cast<double>(end_tx) / (1.0 + sro);
    std::size_t lo = static_cast<std::size_t>(std::ceil(m0));
    std::size_t hi = static_cast<std::size_t>(std::floor(m1));
    if (lo >= hi || hi > N) return 0.0;
    double s = 0.0;
    for (std::size_t n = lo; n < hi; ++n) s += std::norm(rf[n]);
    return std::sqrt(s / static_cast<double>(hi - lo));
}

// The known payload (complex) embedded in a reference frame at the payload offset.
inline std::vector<Cplx> known_payload_from_frame(const std::vector<std::int16_t>& ref_frame) {
    const std::size_t off = frame::kSilenceComplex + frame::kPayloadStart;  // 13248
    std::vector<Cplx> out(frame::kPayloadComplex);
    for (std::size_t k = 0; k < frame::kPayloadComplex; ++k)
        out[k] = Cplx(static_cast<double>(ref_frame[(off + k) * 2 + 0]),
                      static_cast<double>(ref_frame[(off + k) * 2 + 1]));
    return out;
}

// Count int16 samples pinned at the rail (clipped).
inline std::uint64_t clip_count(const std::vector<std::int16_t>& iq) {
    std::uint64_t n = 0;
    for (std::int16_t v : iq)
        if (v == 32767 || v == -32768) ++n;
    return n;
}

}  // namespace dsp

// ---------------------------------------------------------------------------
// RxWindowReport: the per-file RX recovery result (host-testable).
// ---------------------------------------------------------------------------
struct RxWindowReport {
    bool sync_found = false;
    std::size_t frame_start = 0;
    double frame_position = 0.0;   // sub-sample refined frame start (SRO/extract)
    double coarse_cfo_hz = 0.0;
    double residual_cfo_hz = 0.0;
    double total_cfo_hz = 0.0;
    double phase_deg = 0.0;        // recovered phase at frame_start (before removal)
    double sro_ppm = 0.0;
    std::size_t tail_index = 0;
    double noise_floor_rms = 0.0;
    double payload_rms = 0.0;
    double snr_db = 0.0;
    double corr = 0.0;
    double normalized_residual = 0.0;
    std::uint64_t clip_count = 0;
    std::string verdict;
    std::vector<std::int16_t> payload;   // extracted 53760-complex int16
};

// The full RX DSP on one capture window: frame sync + CFO/SRO/phase + payload
// extraction + fidelity.  `rx` is the interleaved int16 capture (kCaptureComplex
// complex samples); `ref_frame` is the known TX frame (from frame::build_frame) so
// the receiver knows the exact preamble/tail/payload it is expecting.
inline RxWindowReport process_rx_window(const std::vector<std::int16_t>& rx,
                                        const std::vector<std::int16_t>& ref_frame,
                                        double fs, double cfo_max_hz,
                                        double sro_max_ppm) {
    RxWindowReport rep;
    const std::vector<dsp::Cplx> r = dsp::to_complex(rx);

    // 0. signal presence (fail-closed on a dead/absent air path).
    if (dsp::rms(r) < kNoSignalRms) {
        rep.verdict = kVerdictNoSignal;
        return rep;
    }

    // Known sequences (category-independent).
    const std::vector<std::int16_t> pre_iq = frame::preamble_a();  // 1024 complex
    const std::vector<dsp::Cplx> pre = dsp::to_complex(pre_iq);
    std::vector<dsp::Cplx> dpre(2 * pre.size());
    for (std::size_t k = 0; k < pre.size(); ++k) dpre[k] = pre[k];
    for (std::size_t k = 0; k < pre.size(); ++k) dpre[pre.size() + k] = pre[k];
    const std::vector<dsp::Cplx> tail = pre;   // single 1024-sample preamble A

    // 1. S&C coarse CFO.
    const dsp::CoarseCfo coarse = dsp::estimate_coarse_cfo(r, fs);
    if (!coarse.found || std::fabs(coarse.cfo_hz) > cfo_max_hz) {
        rep.verdict = kVerdictCfoOutOfRange;
        return rep;
    }
    rep.coarse_cfo_hz = coarse.cfo_hz;

    // 2. coarse CFO compensation (absolute index ramp).
    std::vector<dsp::Cplx> rc = r;
    dsp::compensate_cfo_absolute(rc, coarse.cfo_hz, fs);

    // 3. frame-start matched filter (2048 double preamble), bounded near the S&C peak.
    //    The lag-16 S&C plateau starts at frame_start + kPreambleUnitComplex, so the
    //    frame start sits ~16 samples BEFORE coarse.peak; search [peak-2048, peak+64].
    //    matched_filter_peak's `search_end` bounds n+P (pattern START), so pass
    //    hi + dpre.size() (hi is the max pattern START, not the max pattern END).
    std::size_t lo = (coarse.peak > 2048) ? (coarse.peak - 2048) : 0;
    std::size_t hi = coarse.peak + 64;
    if (hi + dpre.size() > rc.size()) hi = rc.size() - dpre.size();
    const dsp::MatchedPeak fs_peak =
        dsp::matched_filter_peak(rc, dpre, lo, hi + dpre.size());
    if (!fs_peak.found || fs_peak.corr < kSyncCorrThreshold) {
        rep.verdict = iqrfloop::kRfSyncNotFound;
        return rep;
    }
    rep.frame_start = fs_peak.index;
    rep.sync_found = true;
    // Sub-sample refine the frame start (parabolic on the double-preamble matched
    // filter).  The SRO estimate and payload extraction consume this fractional
    // position; an integer-only frame start would leak up to +/-0.5 samples into
    // the SRO (up to ~8 ppm) and into the payload alignment (rejected by the
    // fidelity gate).
    rep.frame_position = static_cast<double>(fs_peak.index);
    {
        const std::size_t p = fs_peak.index;
        if (p > lo && p + dpre.size() + 1 <= rc.size()) {
            const double c0 = dsp::matched_filter_corr(rc, dpre, p - 1);
            const double c1 = fs_peak.corr;
            const double c2 = dsp::matched_filter_corr(rc, dpre, p + 1);
            const double denom = c0 - 2.0 * c1 + c2;
            if (std::fabs(denom) > 1e-12) {
                double delta = 0.5 * (c0 - c2) / denom;
                if (delta < -1.0) delta = -1.0;
                if (delta > 1.0) delta = 1.0;
                rep.frame_position += delta;
            }
        }
    }

    // 4. fine CFO + phase (two-half LS on the 1024 preamble at frame_start).
    const dsp::FineCfoPhase fine =
        dsp::estimate_fine_cfo_phase(rc, rep.frame_start, pre, fs);
    if (!fine.found) {
        rep.verdict = iqrfloop::kRfSyncNotFound;
        return rep;
    }
    rep.residual_cfo_hz = fine.residual_cfo_hz;
    rep.total_cfo_hz = coarse.cfo_hz + fine.residual_cfo_hz;
    rep.phase_deg = fine.phase_rad * 180.0 / frame::kPi;
    if (std::fabs(rep.total_cfo_hz) > cfo_max_hz) {
        rep.verdict = kVerdictCfoOutOfRange;
        return rep;
    }

    // 5. residual CFO + phase compensation relative to frame_start.
    std::vector<dsp::Cplx> rf = rc;
    dsp::compensate_residual(rf, rep.frame_start, fine.residual_cfo_hz,
                             fine.phase_rad, fs);

    // 6. tail matched filter + SRO.
    const dsp::SroEstimate sro =
        dsp::estimate_sro_from_tail(rf, rep.frame_position, tail, fs);
    rep.tail_index = sro.tail_index;
    rep.sro_ppm = sro.sro_ppm;
    if (std::fabs(rep.sro_ppm) > sro_max_ppm) {
        rep.verdict = kVerdictSroOutOfRange;
        return rep;
    }

    // 7. payload extraction.
    rep.payload = dsp::extract_payload(rf, rep.frame_position, rep.sro_ppm);

    // 8. fidelity vs the known payload.
    const std::vector<dsp::Cplx> known = dsp::known_payload_from_frame(ref_frame);
    const dsp::Fidelity fid =
        dsp::aligned_fidelity(dsp::to_complex(rep.payload), known);
    rep.corr = fid.corr;
    rep.normalized_residual = fid.normalized_residual;
    rep.payload_rms = fid.payload_rms;
    rep.clip_count = dsp::clip_count(rep.payload);

    // 9. noise floor + SNR from the trailing silence.
    rep.noise_floor_rms = dsp::trailing_silence_rms(rf, rep.frame_start, rep.sro_ppm);
    rep.snr_db = (rep.noise_floor_rms > 0.0)
                     ? 20.0 * std::log10(rep.payload_rms / rep.noise_floor_rms)
                     : 120.0;

    // 10. verdict (measurement-only; mirrors the fix8/fix9 observation ordering).
    if (rep.clip_count > 0) {
        rep.verdict = iqrfloop::kRfRxClipped;
    } else if (std::isfinite(rep.snr_db) && rep.snr_db < iqrfloop::kRfSnrThresholdDb) {
        rep.verdict = iqrfloop::kRfRxTooLow;
    } else if (rep.corr < iqrfloop::kRfSyncCorrThreshold) {
        rep.verdict = iqrfloop::kRfDistortsIq;
    } else if (rep.normalized_residual <= iqrfloop::kRfMaxNormalizedResidual) {
        rep.verdict = iqrfloop::kRfPreservesIq;
    } else {
        rep.verdict = iqrfloop::kRfPathNotProven;
    }
    return rep;
}

// ---------------------------------------------------------------------------
// Local merge + argmax + small helpers (the runner's own copies, iCraft-free).
// ---------------------------------------------------------------------------
using Clock = std::chrono::steady_clock;

inline std::vector<float> merge23(const std::vector<float>& raw24) {
    if (raw24.size() != static_cast<std::size_t>(rml23::kNpuOutputDim))
        throw std::runtime_error("rml23: raw logits width != 24");
    float m23[rml23::kDeployedClassCount];
    if (!rml23::merge_logits_23(raw24.data(), m23))
        throw std::runtime_error("rml23: merge fail-closed (non-finite logits)");
    return std::vector<float>(m23, m23 + rml23::kDeployedClassCount);
}

inline int argmax_of(const std::vector<float>& v) {
    if (v.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(v.size()); ++i)
        if (v[i] > v[best]) best = i;
    return best;
}

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

inline std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 2);
    for (char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += c;
                }
        }
    }
    return out;
}

inline std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

inline std::vector<std::int16_t> read_ci16(const std::string& path,
                                           std::size_t complex_count) {
    std::vector<std::int16_t> iq(complex_count * 2);
    std::ifstream f(path, std::ios::binary);
    if (!f)
        throw std::runtime_error("extrf: cannot read payload " + path);
    f.read(reinterpret_cast<char*>(iq.data()),
           static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    if (static_cast<std::size_t>(f.gcount()) !=
        iq.size() * sizeof(std::int16_t))
        throw std::runtime_error("extrf: short read payload " + path);
    return iq;
}

// ---------------------------------------------------------------------------
// Rx23RunReport: the 23-class run report (memory-bounded).
// ---------------------------------------------------------------------------
struct Rx23RunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::string model_sha;
    std::uint64_t frozen_files = 0;
    std::uint64_t calib_files = 0;
    std::uint64_t holdout_files = 0;

    bool device_not_found = false;
    std::string error;

    long long requested_rate = 0;
    long long rx_rate = 0;
    double rate_err_hz = 0.0;
    double rate_err_ppm = 0.0;
    bool sample_rate_ok = false;
    double rx_gain_requested = 0.0;
    double rx_gain_readback = 0.0;
    int loopback_readback = -1;
    bool restore_ok = false;
    std::string restore_report;

    bool have_global_gain = false;
    iqrfloop::RfGlobalGain global_gain;
    std::size_t calib_used = 0;

    std::uint64_t scored = 0;
    std::uint64_t rf_excluded = 0;
    std::uint64_t total_valid = 0;
    std::uint64_t total_correct = 0;
    std::vector<std::uint64_t> class_total;
    std::vector<std::uint64_t> class_correct;
    std::vector<std::uint64_t> confusion;
    std::map<std::string, std::uint64_t> rf_exclude_reasons;

    bool accuracy_valid = false;

    std::string results_path;
    std::string confusion_path;
    std::string per_class_path;
    std::string summary_path;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// ---------------------------------------------------------------------------
// run_iq_external_rf_rx_23class (RX-only, template <Npu> to stay iCraft-free).
// ---------------------------------------------------------------------------
template <typename Npu>
Rx23RunReport run_iq_external_rf_rx_23class(
    Npu& npu, m22::StageTiming& timing, int argc, char** argv,
    const std::function<void(const rf::ResultFrame&)>& on_frame) {
    Rx23RunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-external-rf-rx-23class requires --frozen-dir=<D2 "
                                 "artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    // RF safety S1.2: RX gain starts at 0 dB.
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 0.0);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const double cfo_max_hz = board::opt_d(argc, argv, "--cfo-max-hz", 150000.0);
    const double sro_max_ppm = board::opt_d(argc, argv, "--sro-max-ppm", 100.0);
    const std::uint64_t calib_cap =
        board::opt_u64(argc, argv, "--rf-calib-count", 0);
    const std::uint64_t max_files =
        board::opt_u64(argc, argv, "--max-files", 0);
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    const std::string out_dir = board::get_opt(argc, argv, "--out-dir", "");

    // RF safety: the external-RF path must be EXPLICITLY confirmed by the operator.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-external-rf-rx-23class requires --rf-path=direct-cable (50-ohm SMA "
            "coax, no antenna, no amplifier).  Got '" + rf_path + "' -- refusing to "
            "receive on the RF port.");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-external-rf-rx-23class requires --input-kind=radioml-d2-2p56m (got '" +
            rep.input_kind + "').");

    // ---- load frozen D2 sidecar (fail-closed: never re-generate) ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);

    if (!file_filter.empty()) {
        std::vector<iqdloop::FrozenIq> kept;
        for (const auto& fz : frozen)
            if (fz.file_name.find(file_filter) != std::string::npos)
                kept.push_back(fz);
        frozen = std::move(kept);
    }

    std::vector<iqdloop::FrozenIq> calib, holdout;
    for (const auto& fz : frozen)
        (fz.is_calibration ? calib : holdout).push_back(fz);
    if (calib_cap > 0 && calib_cap < calib.size())
        calib.resize(static_cast<std::size_t>(calib_cap));
    if (max_files > 0 && max_files < holdout.size())
        holdout.resize(static_cast<std::size_t>(max_files));
    if (frozen.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: no D2 files after "
                                 "file-filter selection");

    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    rep.calib_files = static_cast<std::uint64_t>(calib.size());
    rep.holdout_files = static_cast<std::uint64_t>(holdout.size());

    rep.results_path = join_path(out_dir, "route_g_fix10_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_g_fix10_confusion_23.csv");
    rep.per_class_path = join_path(out_dir, "route_g_fix10_per_class.json");
    rep.summary_path = join_path(out_dir, "route_g_fix10_summary.json");

    rep.class_total.assign(rml23::kDeployedClassCount, 0);
    rep.class_correct.assign(rml23::kDeployedClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml23::kDeployedClassCount) *
                             rml23::kDeployedClassCount, 0);

    const cat::Contract contract = chain::contract_23();

    std::printf("IQ_EXTERNAL_RF_RX BOARD_REQUIRED input_kind=%s frozen_dir=%s "
                "frozen_files=%llu calib_files=%llu holdout_files=%llu rf_path=%s "
                "rx_gain=%.3f center=%llu out_dir=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<unsigned long long>(rep.calib_files),
                static_cast<unsigned long long>(rep.holdout_files),
                rf_path.c_str(), gain_db,
                static_cast<unsigned long long>(center_hz),
                out_dir.empty() ? "." : out_dir.c_str());
    std::fflush(stdout);

    // ---- device open (device-not-found is exit code 2, not a throw) ----
    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        rep.device_not_found = true;
        rep.error = e.what();
        return rep;
    }

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    bool all_capture_ok = true;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- RX-only safety (S1.2): board TX stopped + read back; loopback off. ----
        dev->tx_stop();
        if (dev->tx_running()) {
            rep.error = "rx_safety: board TX still running after tx_stop()";
            return rep;
        }
        dev->set_loopback(0);
        rep.loopback_readback = dev->get_loopback();
        if (rep.loopback_readback != 0) {
            rep.error = "rx_safety: loopback read-back != 0 (got " +
                        std::to_string(rep.loopback_readback) +
                        ") -- external RF requires the digital loopback OFF";
            return rep;
        }

        // ---- sample rate: force 2560000, fail-closed abs(actual-2560000) <= 5 Hz ----
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.rate_err_hz = static_cast<double>(rep.rx_rate - requested);
        rep.rate_err_ppm = 1e6 * rep.rate_err_hz / static_cast<double>(requested);
        rep.sample_rate_ok = std::llabs(rep.rx_rate - requested) <= 5;
        if (!rep.sample_rate_ok) {
            rep.error = "sample_rate_mismatch: requested=" + std::to_string(requested) +
                        " rx=" + std::to_string(rep.rx_rate) +
                        " (abs(actual-requested) must be <= 5 Hz)";
            return rep;
        }

        // ---- RX LO + gain ----
        dev->set_rx_lo(static_cast<long long>(center_hz));
        dev->set_rx_gain(gain_db);
        rep.rx_gain_requested = gain_db;
        rep.rx_gain_readback = dev->get_rx_gain();

        const std::string rx_fmt = pluto::describe_data_format(dev->rx_data_format());
        std::printf("IQ_EXTERNAL_RF_FORMAT dir=rx %s\n", rx_fmt.c_str());
        std::fflush(stdout);

        std::uint64_t global_frame_id = 0;
        std::vector<std::complex<double>> calib_gains;

        // ---- shared per-file processing: build ref frame, capture, recover, judge.
        // Returns the fidelity verdict; leaves `extracted` (the 53760-complex int16
        // payload) and `win` (RxWindowReport) filled.  The caller decides whether to
        // collect a calibration gain or to classify. ----
        const auto process_file = [&](const iqdloop::FrozenIq& fz,
                                      std::vector<std::int16_t>& extracted,
                                      RxWindowReport& win) -> bool {
            win = RxWindowReport{};

            std::printf("IQ_EXTERNAL_RF file=%s input_kind=%s source_class=%d "
                        "deployed_class=%d modulation=%s frozen_complex=%llu "
                        "split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        fz.split_role.c_str());
            std::fflush(stdout);

            // Build the KNOWN reference frame (receiver knows the TX waveform).
            const std::vector<std::int16_t> payload =
                read_ci16(fz.path, fz.complex_count);
            extrf::frame::HeaderFields fields;
            fields.valid = true;
            fields.version = frame::kFrameVersion;
            fields.run_id = 0;
            fields.index = static_cast<std::uint16_t>(fz.source_index & 0xFFFFu);
            fields.payload_count = static_cast<std::uint16_t>(fz.complex_count);
            fields.sha_short = frame::sha_short_from_hex(fz.sha256);
            fields.crc16 = 0;
            fields.crc_ok = false;
            frame::attach_header_crc(fields);
            const std::vector<std::int16_t> ref =
                frame::build_frame(payload, fields);

            // Capture a 2x-frame window in ONE contiguous RX refill.
            std::vector<std::int16_t> rx_iq;
            board::RxStats st;
            board::Continuity cont;
            bool capture_ok = false;
            {
                m22::StageTiming::Timer t(timing, m22::StageId::RxRefill);
                capture_ok = board::capture_contiguous(*dev, kCaptureComplex, rx_iq,
                                                       st, cont);
            }

            if (board::g_stop_requested || st.interrupted) {
                win.verdict = kVerdictInsufficientEvidence;
                std::printf("IQ_EXTERNAL_RF file=%s interrupted\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                return false;
            }
            if (!capture_ok) {
                win.verdict = kVerdictInsufficientEvidence;
                std::printf("IQ_EXTERNAL_RF file=%s capture=FAIL %s\n",
                            fz.file_name.c_str(), cont.report().c_str());
                std::fflush(stdout);
                return false;
            }

            // Recover the payload (frame sync / CFO / SRO / phase / fidelity).
            win = process_rx_window(rx_iq, ref, static_cast<double>(iqdloop::kFrozenFsIn),
                                    cfo_max_hz, sro_max_ppm);
            extracted = win.payload;

            std::printf("IQ_EXTERNAL_RF_SYNC file=%s frame_start=%zu "
                        "coarse_cfo_hz=%.3f residual_cfo_hz=%.3f total_cfo_hz=%.3f "
                        "phase_deg=%.3f sro_ppm=%.3f tail_index=%zu\n",
                        fz.file_name.c_str(), win.frame_start,
                        win.coarse_cfo_hz, win.residual_cfo_hz, win.total_cfo_hz,
                        win.phase_deg, win.sro_ppm, win.tail_index);
            std::fflush(stdout);

            std::printf("IQ_EXTERNAL_RF_FIDELITY file=%s verdict=%s corr=%.6f "
                        "normalized_residual=%.6f payload_rms=%.3f noise_floor_rms=%.4f "
                        "snr_db=%.3f clip_count=%llu\n",
                        fz.file_name.c_str(), win.verdict.c_str(), win.corr,
                        win.normalized_residual, win.payload_rms, win.noise_floor_rms,
                        win.snr_db, static_cast<unsigned long long>(win.clip_count));
            std::fflush(stdout);
            return true;
        };

        // ---- pass 1: calibration subset (split_role == calibration, capped) ----
        for (const auto& fz : calib) {
            if (board::g_stop_requested) break;
            std::vector<std::int16_t> extracted;
            RxWindowReport win;
            all_capture_ok = process_file(fz, extracted, win) && all_capture_ok;
            if (!iqrfloop::rf_fidelity_gate_ok(win.verdict.c_str())) {
                ++rep.rf_exclude_reasons[win.verdict];
                continue;
            }
            // The recovery leaves a REAL-positive gain (|g_rf|), so the per-file LS
            // gain is real; the median magnitude is the ONE global amplitude.  The
            // known payload is exactly the original ci16 (== the frame's payload
            // region used inside process_rx_window).
            const std::vector<dsp::Cplx> known =
                dsp::to_complex(read_ci16(fz.path, fz.complex_count));
            const dsp::Fidelity fid =
                dsp::aligned_fidelity(dsp::to_complex(extracted), known);
            if (std::abs(fid.gain) > 1e-30)
                calib_gains.push_back(fid.gain);
        }

        rep.global_gain = iqrfloop::estimate_global_gain(calib_gains);
        rep.have_global_gain = rep.global_gain.valid;
        rep.calib_used = rep.global_gain.count;
        std::printf("IQ_EXTERNAL_RF_CALIBRATION calib_files=%llu used=%zu valid=%d "
                    "mag=%.6f phase_deg=%.3f k_mag=%.6f k_phase_deg=%.3f\n",
                    static_cast<unsigned long long>(rep.calib_files), rep.calib_used,
                    rep.have_global_gain ? 1 : 0, rep.global_gain.mag,
                    rep.global_gain.phase_deg, rep.global_gain.k_mag,
                    rep.global_gain.k_phase_deg);
        std::fflush(stdout);

        // ---- pass 2: holdout subset: restore + classify with the ONE global gain. ----
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("iq-external-rf-rx-23class: cannot open " +
                                     rep.results_path);
        results << "file_name\tsource_index\traw24_class\tdeployed23_class\t"
                << "modulation\tsnr_db\tsplit_role\tvalid\traw24_pred\t"
                << "merged23_pred\tcorrect\tcorr\tnormalized_residual\tsnr_db_rf\t"
                << "rf_verdict\n";

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;
            std::vector<std::int16_t> extracted;
            RxWindowReport win;
            all_capture_ok = process_file(fz, extracted, win) && all_capture_ok;

            // ---- fidelity gate: a failing file is SKIPPED (never silently scored) ----
            if (!iqrfloop::rf_fidelity_gate_ok(win.verdict.c_str())) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons[win.verdict];
                std::printf("IQ_EXTERNAL_RF file=%s classification=SKIPPED "
                            "reason=fidelity_gate fidelity=%s\n",
                            fz.file_name.c_str(), win.verdict.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << win.corr << "\t" << win.normalized_residual << "\t"
                        << win.snr_db << "\t" << win.verdict << "\n";
                continue;
            }
            if (!rep.have_global_gain) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons["RF_AMPLITUDE_NOT_CALIBRATED"];
                std::printf("IQ_EXTERNAL_RF file=%s classification=SKIPPED "
                            "reason=no_global_calibration_gain\n", fz.file_name.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << win.corr << "\t" << win.normalized_residual << "\t"
                        << win.snr_db << "\tRF_AMPLITUDE_NOT_CALIBRATED\n";
                continue;
            }

            // ---- D2 restore + classify (ONE window per file) ----
            const std::size_t win_complex = extracted.size() / 2;
            if (win_complex == 0) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons["RF_ALIGNED_WINDOW_EMPTY"];
                std::printf("IQ_EXTERNAL_RF file=%s aligned window empty\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << win.corr << "\t" << win.normalized_residual << "\t"
                        << win.snr_db << "\tRF_ALIGNED_WINDOW_EMPTY\n";
                continue;
            }

            // rec_scale == 1.0 -> the chain emits decimate(iq / 2048) == the AC.
            chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, 1.0f);
            {
                m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                chain.push_int16(extracted.data(), win_complex);
            }

            std::vector<float> recovered_stream;
            {
                std::vector<float> t(chain::kTensorFloats);
                while (chain.ready() > 0) {
                    if (board::g_stop_requested) break;
                    if (!chain.pull_tensor(t.data())) break;
                    recovered_stream.insert(recovered_stream.end(), t.begin(), t.end());
                }
            }
            iqrfloop::apply_global_gain_to_stream(recovered_stream, chain::kFrameComplex,
                                                  rep.global_gain);
            iqdloop::apply_d2_restore_to_stream(recovered_stream, chain::kFrameComplex,
                                                fz.original_dc_i, fz.original_dc_q,
                                                fz.d2_rec_scale);

            std::printf("IQ_EXTERNAL_RF_D2_RESTORE file=%s source_index=%lld "
                        "dc_i=%.9f dc_q=%.9f rec_scale=%.9f global_rf_gain_used=1 "
                        "per_file_fit_used=0\n",
                        fz.file_name.c_str(), static_cast<long long>(fz.source_index),
                        fz.original_dc_i, fz.original_dc_q, fz.d2_rec_scale);
            std::fflush(stdout);

            const std::vector<float> ref =
                iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                               fz.recovered_tensor_sha256);
            const iqdloop::ClassificationWindow cw =
                iqdloop::select_classification_window(recovered_stream, ref);
            std::printf("IQ_EXTERNAL_RF_WINDOW file=%s recovered_frames=%llu "
                        "delay_offset=%d corr=%.6f nmse=%.6f gain_db=%.3f "
                        "sha_equal=%d aligned_sha=%s ref_sha=%s\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(cw.recovered_frames),
                        cw.delay_offset, cw.tensor_corr, cw.tensor_nmse,
                        cw.tensor_gain_db, cw.sha_equal ? 1 : 0,
                        cw.aligned_sha256.c_str(), cw.ref_sha256.c_str());
            std::fflush(stdout);

            if (!cw.valid || cw.aligned_tensor.empty()) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons["RF_NO_VALID_WINDOW"];
                std::printf("IQ_EXTERNAL_RF file=%s classification=SKIPPED "
                            "reason=no_valid_window\n", fz.file_name.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << win.corr << "\t" << win.normalized_residual << "\t"
                        << win.snr_db << "\tRF_NO_VALID_WINDOW\n";
                continue;
            }

            // ---- classify the ONE reference-aligned window ----
            const auto t0 = Clock::now();
            std::vector<float> raw24;
            npu.infer(cw.aligned_tensor.data(), raw24);
            const double classify_us = elapsed_us(t0);
            timing.record(m22::StageId::NpuInfer, classify_us);

            const std::vector<float> m23 = merge23(raw24);
            const int raw_top = argmax_of(raw24);
            const int merged_top = argmax_of(m23);
            const bool correct = (merged_top == fz.deployed_class);
            ++global_frame_id;

            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;   // 1024/128k = 8 ms/frame
            r.source = "iq_external_rf_rx_23class";
            r.mock = false;
            chain::fill_result_rml23(r, raw24, m23, contract, rep.model_sha,
                                     win.snr_db);
            r.classify_us = classify_us;
            r.e2e_us = classify_us;
            on_frame(r);

            ++rep.scored;
            ++rep.total_valid;
            if (correct) ++rep.total_correct;
            ++rep.confusion[static_cast<std::size_t>(fz.deployed_class) *
                                rml23::kDeployedClassCount + merged_top];
            ++rep.class_total[static_cast<std::size_t>(fz.deployed_class)];
            if (correct) ++rep.class_correct[static_cast<std::size_t>(fz.deployed_class)];

            results << fz.file_name << "\t" << fz.source_index << "\t"
                    << fz.source_class << "\t" << fz.deployed_class << "\t"
                    << fz.modulation << "\t" << fz.snr_db << "\t"
                    << fz.split_role << "\t1\t" << raw_top << "\t" << merged_top
                    << "\t" << (correct ? 1 : 0) << "\t"
                    << win.corr << "\t" << win.normalized_residual
                    << "\t" << win.snr_db << "\t" << win.verdict << "\n";

            std::printf("IQ_EXTERNAL_RF file=%s frames=1 correct=%d deployed=%d "
                        "source=%d raw24_pred=%d merged23_pred=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.deployed_class,
                        fz.source_class, raw_top, merged_top);
            std::fflush(stdout);
        }
        results.close();

        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- accuracy token + the four output files ----
    rep.accuracy_valid = rep.have_global_gain && (rep.scored > 0);
    const double overall_acc = rep.total_valid > 0
        ? static_cast<double>(rep.total_correct) /
          static_cast<double>(rep.total_valid) : 0.0;
    double macro_acc = 0.0;
    {
        std::size_t seen = 0;
        for (int c = 0; c < rml23::kDeployedClassCount; ++c) {
            if (rep.class_total[static_cast<std::size_t>(c)] == 0) continue;
            ++seen;
            macro_acc += static_cast<double>(
                             rep.class_correct[static_cast<std::size_t>(c)]) /
                         static_cast<double>(rep.class_total[static_cast<std::size_t>(c)]);
        }
        if (seen > 0) macro_acc /= static_cast<double>(seen);
    }

    {
        std::ofstream f(rep.confusion_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.confusion_path);
        f << "true\\pred";
        for (int c = 0; c < rml23::kDeployedClassCount; ++c)
            f << "," << rml23::kLabelOrder23[c];
        f << "\n";
        for (int t = 0; t < rml23::kDeployedClassCount; ++t) {
            f << rml23::kLabelOrder23[t];
            for (int p = 0; p < rml23::kDeployedClassCount; ++p)
                f << "," << rep.confusion[static_cast<std::size_t>(t) *
                                              rml23::kDeployedClassCount + p];
            f << "\n";
        }
    }

    {
        std::ofstream f(rep.per_class_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.per_class_path);
        f << "[\n";
        for (int c = 0; c < rml23::kDeployedClassCount; ++c) {
            const std::uint64_t tot = rep.class_total[static_cast<std::size_t>(c)];
            const std::uint64_t corr = rep.class_correct[static_cast<std::size_t>(c)];
            const double acc = tot > 0 ? static_cast<double>(corr) /
                                         static_cast<double>(tot) : 0.0;
            f << (c == 0 ? "  " : " ,") << "{\"index\":" << c
              << ",\"name\":\"" << rml23::kLabelOrder23[c] << "\""
              << ",\"total\":" << tot << ",\"correct\":" << corr
              << ",\"accuracy\":" << acc << "}\n";
        }
        f << "]\n";
    }

    {
        std::ofstream f(rep.summary_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.summary_path);
        const std::string token = rep.accuracy_valid
            ? "ROUTE_G_23CLASS_ACCURACY_MEASURED"
            : "ROUTE_G_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY";
        f << "{\n";
        f << "  \"token\":\"" << token << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"frozen_dir\":\"" << json_escape(rep.frozen_dir) << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"frozen_files\":" << rep.frozen_files << ",\n";
        f << "  \"calib_files\":" << rep.calib_files << ",\n";
        f << "  \"holdout_files\":" << rep.holdout_files << ",\n";
        f << "  \"global_gain\":{\"valid\":" << (rep.have_global_gain ? "true" : "false")
          << ",\"used\":" << rep.calib_used
          << ",\"mag\":" << rep.global_gain.mag
          << ",\"phase_deg\":" << rep.global_gain.phase_deg
          << ",\"k_mag\":" << rep.global_gain.k_mag
          << ",\"k_phase_deg\":" << rep.global_gain.k_phase_deg << "},\n";
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"rf_excluded\":" << rep.rf_excluded << ",\n";
        f << "  \"rf_exclude_reasons\":{";
        bool first_reason = true;
        for (const auto& kv : rep.rf_exclude_reasons) {
            if (!first_reason) f << ",";
            f << "\"" << json_escape(kv.first) << "\":" << kv.second;
            first_reason = false;
        }
        f << "},\n";
        f << "  \"total_valid_frames\":" << rep.total_valid << ",\n";
        f << "  \"total_correct_frames\":" << rep.total_correct << ",\n";
        f << "  \"overall_accuracy\":" << overall_acc << ",\n";
        f << "  \"macro_accuracy\":" << macro_acc << ",\n";
        f << "  \"sample_rate_ok\":" << (rep.sample_rate_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rate\":" << rep.requested_rate << ",\n";
        f << "  \"rx_rate\":" << rep.rx_rate << ",\n";
        f << "  \"rf_path\":\"direct-cable\",\n";
        f << "  \"rx_gain_requested_db\":" << rep.rx_gain_requested << ",\n";
        f << "  \"rx_gain_readback_db\":" << rep.rx_gain_readback << "\n";
        f << "}\n";
    }

    const std::string token = rep.accuracy_valid
        ? "ROUTE_G_23CLASS_ACCURACY_MEASURED"
        : "ROUTE_G_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY";
    std::printf("ROUTE_G_23CLASS_ACCURACY token=%s scored=%llu "
                "rf_excluded=%llu valid_frames=%llu correct=%llu overall_acc=%.6f "
                "macro_acc=%.6f\n",
                token.c_str(),
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.rf_excluded),
                static_cast<unsigned long long>(rep.total_valid),
                static_cast<unsigned long long>(rep.total_correct),
                overall_acc, macro_acc);
    std::fflush(stdout);

    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          !frozen.empty() && all_capture_ok;
    rep.functional_pass = infra_ok && rep.have_global_gain && (rep.scored > 0);

    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " calib_files=" + std::to_string(rep.calib_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " scored=" + std::to_string(rep.scored) +
                         " rf_excluded=" + std::to_string(rep.rf_excluded) +
                         " total_valid=" + std::to_string(rep.total_valid) +
                         " total_correct=" + std::to_string(rep.total_correct) +
                         " overall_acc=" + std::to_string(overall_acc) +
                         " macro_acc=" + std::to_string(macro_acc) +
                         " accuracy_token=" + token +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " rx_gain_requested_db=" + std::to_string(rep.rx_gain_requested) +
                         " rx_gain_readback_db=" + std::to_string(rep.rx_gain_readback) +
                         " rf_path=direct-cable";
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

// ---------------------------------------------------------------------------
// Level sweep (Task E): RX-only scan of --rx-gain from 0 dB up, reporting RMS /
// peak / SNR / clip per level and the highest safe operating point.  Measurement-
// only, fail-closed: no PASS token is ever written.  Run concurrently with the PC
// TX tool (operator coordinates; see Task H).
// ---------------------------------------------------------------------------
struct LevelSweepRow {
    double gain_db = 0.0;
    double payload_rms = 0.0;
    double noise_floor_rms = 0.0;
    double snr_db = 0.0;
    std::uint64_t clip_count = 0;
    std::string verdict;
};

struct LevelSweepReport {
    std::vector<LevelSweepRow> rows;
    double recommended_gain_db = -1.0;   // highest gain with RF_PRESERVES_IQ, else -1
    bool device_not_found = false;
    std::string error;
};

inline LevelSweepReport run_iq_external_rf_level_sweep(int argc, char** argv) {
    LevelSweepReport rep;
    const std::string input_kind =
        board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    const std::string frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (frozen_dir.empty())
        throw std::runtime_error("iq-external-rf-level-sweep requires --frozen-dir");
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const std::uint64_t file_index = board::opt_u64(argc, argv, "--index", 0);
    const double cfo_max_hz = board::opt_d(argc, argv, "--cfo-max-hz", 150000.0);
    const double sro_max_ppm = board::opt_d(argc, argv, "--sro-max-ppm", 100.0);
    // Default gain ladder, 0 dB .. 40 dB in 5 dB steps (RX-only, no ceiling).
    const std::string ladder_str =
        board::get_opt(argc, argv, "--gain-ladder", "0,5,10,15,20,25,30,35,40");

    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-external-rf-level-sweep requires --rf-path=direct-cable (50-ohm SMA "
            "coax, no antenna, no amplifier).");
    if (input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-external-rf-level-sweep requires --input-kind=radioml-d2-2p56m");

    std::vector<double> ladder;
    {
        std::string s = ladder_str;
        std::size_t pos;
        while ((pos = s.find(',')) != std::string::npos) {
            if (!s.substr(0, pos).empty())
                ladder.push_back(std::atof(s.substr(0, pos).c_str()));
            s.erase(0, pos + 1);
        }
        if (!s.empty()) ladder.push_back(std::atof(s.c_str()));
    }
    if (ladder.empty()) ladder.push_back(0.0);

    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(frozen_dir, input_kind);
    if (file_index >= frozen.size())
        throw std::runtime_error("iq-external-rf-level-sweep: --index out of range");
    const iqdloop::FrozenIq& fz = frozen[static_cast<std::size_t>(file_index)];

    const std::vector<std::int16_t> payload =
        read_ci16(fz.path, fz.complex_count);
    extrf::frame::HeaderFields fields;
    fields.valid = true;
    fields.version = frame::kFrameVersion;
    fields.run_id = 0;
    fields.index = static_cast<std::uint16_t>(fz.source_index & 0xFFFFu);
    fields.payload_count = static_cast<std::uint16_t>(fz.complex_count);
    fields.sha_short = frame::sha_short_from_hex(fz.sha256);
    fields.crc16 = 0;
    fields.crc_ok = false;
    frame::attach_header_crc(fields);
    const std::vector<std::int16_t> ref = frame::build_frame(payload, fields);

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        rep.device_not_found = true;
        rep.error = e.what();
        return rep;
    }

    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));
        dev->tx_stop();
        if (dev->tx_running()) { rep.error = "board TX still running"; return rep; }
        dev->set_loopback(0);
        if (dev->get_loopback() != 0) { rep.error = "loopback read-back != 0"; return rep; }
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        dev->set_sample_rate(requested);
        if (std::llabs(dev->get_rx_sample_rate() - requested) > 5) {
            rep.error = "sample-rate mismatch";
            return rep;
        }
        dev->set_rx_lo(static_cast<long long>(center_hz));

        for (double g : ladder) {
            if (board::g_stop_requested) break;
            dev->set_rx_gain(g);
            std::vector<std::int16_t> rx_iq;
            board::RxStats st;
            board::Continuity cont;
            const bool capture_ok =
                board::capture_contiguous(*dev, kCaptureComplex, rx_iq, st, cont);

            LevelSweepRow row;
            row.gain_db = g;
            if (!capture_ok) {
                row.verdict = kVerdictInsufficientEvidence;
                rep.rows.push_back(row);
                std::printf("IQ_EXTERNAL_RF_LEVEL gain=%.1f capture=FAIL %s\n",
                            g, cont.report().c_str());
                std::fflush(stdout);
                continue;
            }
            const RxWindowReport win =
                process_rx_window(rx_iq, ref, static_cast<double>(iqdloop::kFrozenFsIn),
                                  cfo_max_hz, sro_max_ppm);
            row.payload_rms = win.payload_rms;
            row.noise_floor_rms = win.noise_floor_rms;
            row.snr_db = win.snr_db;
            row.clip_count = win.clip_count;
            row.verdict = win.verdict;
            rep.rows.push_back(row);
            if (win.verdict == iqrfloop::kRfPreservesIq) rep.recommended_gain_db = g;
            std::printf("IQ_EXTERNAL_RF_LEVEL gain=%.1f payload_rms=%.3f "
                        "noise_floor_rms=%.4f snr_db=%.3f clip_count=%llu verdict=%s\n",
                        g, win.payload_rms, win.noise_floor_rms, win.snr_db,
                        static_cast<unsigned long long>(win.clip_count),
                        win.verdict.c_str());
            std::fflush(stdout);
        }
        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    std::printf("IQ_EXTERNAL_RF_LEVEL_SUMMARY recommended_gain_db=%.1f "
                "levels=%zu (measurement-only, no PASS)\n",
                rep.recommended_gain_db, rep.rows.size());
    std::fflush(stdout);
    return rep;
}

}  // namespace extrf
