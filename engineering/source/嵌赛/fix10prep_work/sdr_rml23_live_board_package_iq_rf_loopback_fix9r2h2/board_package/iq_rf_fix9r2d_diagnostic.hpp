#pragma once

// iq_rf_fix9r2d_diagnostic.hpp -- Route F fix9r2d: DIAGNOSTIC CAPTURE
// ENHANCEMENT (observability completion, approved 39e5).  This is the ONE
// follow-up to fix9r2c (root cause NOT_PROVEN) that captures enough raw RX to
// let the OFFLINE analyzer name the residual with exactly one of six verdicts
// (STABLE_LTI_CHANNEL / CYCLIC_BOUNDARY_TRANSIENT / CAPTURE_INDEX_MISMATCH /
// CYCLE_TO_CYCLE_NONSTATIONARY / TRAINING_PAYLOAD_GAIN_MISMATCH / NOT_IDENTIFIED).
//
// WHAT IT DOES NOT DO (discipline): no change to the recovery algorithm, sync
// search, frame layout, TX data, model/label/preprocess, or any threshold.  No
// fix10 recovery.  This file ONLY adds diagnostic disk-writes + provenance.
//
// PROVENANCE (requirement 4): every rx-derived slice is saved from the SAME
// rx buffer that iqrfrec::estimate ran on, and the manifest records (a) the
// saved file SHA, (b) an INDEPENDENTLY recomputed in-memory SHA of the exact
// contiguous slice src[start : start+len], and (c) equality == 1 iff (a)==(b).
// A captured slice that came from a different buffer, a different offset, or a
// reconstruction would fail equality -- there is no way to masquerade a second
// capture as the original payload.
//
// iCraft-free and libiio-free: every function is PURE (plain data in/out), so
// the host test exercises the exact code the board runner calls.

#include <cmath>
#include <complex>
#include <cstdint>
#include <string>
#include <vector>

#include "iq_rf_fix9r2b_diagnostic.hpp"   // iqrffix9r2b::save_f32_interleaved / WaveformRecord / provisional_apply_scalar
#include "iq_rf_frame_layout.hpp"         // iqrflayout::k* layout + capture sizing
#include "../sdr_adapter/sha256.hpp"      // sdr::Sha256::hex

namespace iqrffix9r2d {

// ---- verdict vocabulary (the OFFLINE analyzer emits exactly ONE of these) ------
// Defined here so the board console + host test + analyzer share the exact strings.
constexpr const char* kStableLtiChannel            = "STABLE_LTI_CHANNEL";
constexpr const char* kCyclicBoundaryTransient     = "CYCLIC_BOUNDARY_TRANSIENT";
constexpr const char* kCaptureIndexMismatch        = "CAPTURE_INDEX_MISMATCH";
constexpr const char* kCycleToCycleNonstationary   = "CYCLE_TO_CYCLE_NONSTATIONARY";
constexpr const char* kTrainingPayloadGainMismatch = "TRAINING_PAYLOAD_GAIN_MISMATCH";
constexpr const char* kNotIdentified               = "NOT_IDENTIFIED";

// ---- small slice statistics ----------------------------------------------------
struct SliceStats {
    double rms = 0.0;
    double dc_re = 0.0;
    double dc_im = 0.0;
    double peak = 0.0;
};

inline SliceStats slice_stats(const std::vector<std::complex<double>>& z) {
    SliceStats s;
    if (z.empty()) return s;
    double energy = 0.0;
    double re = 0.0, im = 0.0;
    double peak2 = 0.0;
    for (const auto& c : z) {
        energy += c.real() * c.real() + c.imag() * c.imag();
        re += c.real();
        im += c.imag();
        const double m2 = c.real() * c.real() + c.imag() * c.imag();
        if (m2 > peak2) peak2 = m2;
    }
    const double n = static_cast<double>(z.size());
    s.rms = std::sqrt(energy / n);
    s.dc_re = re / n;
    s.dc_im = im / n;
    s.peak = std::sqrt(peak2);
    return s;
}

// ---- independent in-memory SHA of a contiguous slice (provenance) --------------
// Computes the SHA-256 of src[start : start+len] as interleaved float32 -- the
// EXACT byte layout save_f32_interleaved writes.  Returns "" when the slice is out
// of range (the caller fails closed).
inline std::string sha256_of_slice(const std::vector<std::complex<double>>& src,
                                   std::size_t start, std::size_t len) {
    if (start > src.size() || len > src.size() - start) return std::string();
    std::vector<float> f32(len * 2);
    for (std::size_t k = 0; k < len; ++k) {
        f32[k * 2 + 0] = static_cast<float>(src[start + k].real());
        f32[k * 2 + 1] = static_cast<float>(src[start + k].imag());
    }
    return sdr::Sha256::hex(f32.data(), f32.size() * sizeof(float));
}

// ---- extract a contiguous slice (fail-closed: empty on out-of-range) -----------
inline std::vector<std::complex<double>> slice_complex(
        const std::vector<std::complex<double>>& src,
        std::size_t start, std::size_t len) {
    if (start > src.size() || len > src.size() - start) return {};
    return std::vector<std::complex<double>>(src.begin() + static_cast<std::ptrdiff_t>(start),
                                             src.begin() + static_cast<std::ptrdiff_t>(start + len));
}

// ---- provenance record for one saved slice -------------------------------------
struct ProvenanceRecord {
    iqrffix9r2b::WaveformRecord rec;   // path / file sha / samples / rms / format
    std::string mem_sha256;            // independently recomputed in-memory SHA
    int equality = -1;                 // 1 == mem_sha == file sha; 0 == mismatch; -1 == N/A
    long long start_index = -1;        // absolute index in the capture (-1 == not a slice)
    std::size_t length = 0;
    int cycle_index = -1;              // 0/1 for cycle frames, -1 otherwise
    long long linear_offset = -1;      // == start_index
    long long circular_offset = -1;    // == start_index % cycle_period
};

// Save src[start : start+len] and prove the saved bytes equal the in-memory slice.
// mem_sha256 is recomputed by sha256_of_slice (a separate code path from the write),
// so equality==1 iff the file really holds the contiguous slice of src.
//   * start / len  : the slice offset within `src`.
//   * start_index  : the ABSOLUTE capture index recorded in the manifest, or -1 when
//                    the vector is not a slice of the rx capture (provisional output /
//                    reference vectors).  For rx slices pass start_index == start.
inline ProvenanceRecord save_slice_with_provenance(
        const std::string& path, const std::vector<std::complex<double>>& src,
        std::size_t start, std::size_t len, long long start_index, int cycle_index,
        std::size_t cycle_period) {
    ProvenanceRecord p;
    p.start_index = start_index;
    p.length = len;
    p.cycle_index = cycle_index;
    p.linear_offset = start_index;
    p.circular_offset = (cycle_period > 0 && start_index >= 0)
        ? static_cast<long long>(static_cast<std::size_t>(start_index) % cycle_period)
        : -1;
    p.mem_sha256 = sha256_of_slice(src, start, len);
    if (p.mem_sha256.empty()) return p;   // out of range -> equality stays -1
    const std::vector<std::complex<double>> slice = slice_complex(src, start, len);
    p.rec = iqrffix9r2b::save_f32_interleaved(path, slice);
    p.equality = (p.rec.path.empty() || p.rec.sha256 != p.mem_sha256) ? 0 : 1;
    return p;
}

// Pure re-verification used by the host test and the offline audit: does the
// in-memory slice of src still match a recorded file SHA?
inline bool verify_slice_provenance(const std::vector<std::complex<double>>& src,
                                    std::size_t start, std::size_t len,
                                    const std::string& file_sha256) {
    const std::string mem = sha256_of_slice(src, start, len);
    return !mem.empty() && !file_sha256.empty() && mem == file_sha256;
}

// ---- capture metadata (requirement 3) ------------------------------------------
struct CaptureMeta {
    bool complete = false;             // false when a slice is out of range (fail-closed)
    std::string capture_sha256;        // SHA of the FULL rx buffer (f32 interleaved)
    std::size_t capture_complex = 0;
    std::size_t frame_start_abs = 0;   // == rec.timing_offset (preamble peak index)
    std::size_t training_start = 0, training_end = 0;
    std::size_t payload_start = 0, payload_end = 0;
    std::size_t full_frame_start = 0, full_frame_end = 0;
    std::size_t cycle_period = 0;
    std::size_t cycle0_start = 0, cycle1_start = 0;
    std::size_t linear_offset = 0;     // == frame_start_abs
    std::size_t circular_offset = 0;   // == frame_start_abs % cycle_period
    double rms = 0.0, dc_re = 0.0, dc_im = 0.0, peak = 0.0;
    int clip = 0;                      // from the runner's int16 rail check
    double cfo_hz = 0.0, sro_ppm = 0.0, gain_mag = 0.0, phase_deg = 0.0;
    std::size_t timing_offset = 0;
    double training_corr = 0.0, training_residual = 0.0;
};

inline CaptureMeta compute_capture_meta(
        const std::vector<std::complex<double>>& rx,
        const iqrfrec::PerFileRecovery& rec, std::size_t capture_complex,
        bool rx_clipped) {
    CaptureMeta m;
    m.capture_complex = rx.size();
    m.capture_sha256 = sha256_of_slice(rx, 0, rx.size());
    m.frame_start_abs = rec.timing_offset;
    m.timing_offset = rec.timing_offset;
    m.cycle_period = iqrflayout::kFramePeriodComplex;
    m.cycle0_start = 0;
    m.cycle1_start = iqrflayout::kFramePeriodComplex;
    m.linear_offset = rec.timing_offset;
    m.circular_offset = rec.timing_offset % iqrflayout::kFramePeriodComplex;
    m.training_start = rec.timing_offset + iqrflayout::kTrainingOffset;
    m.training_end = m.training_start + iqrflayout::kTrainingLength;
    m.payload_start = rec.timing_offset + iqrflayout::kPayloadOffset;
    m.payload_end = m.payload_start + iqrflayout::kPayloadLength;
    m.full_frame_start = rec.timing_offset;
    m.full_frame_end = rec.timing_offset + iqrflayout::kFramePeriodComplex;

    // fail-closed: every slice must fit inside the capture, and the capture must
    // hold >= 2 full periods (cycle1 fits).  timing_offset < period is guaranteed by
    // the full-capture search, but assert it anyway rather than silently record a
    // truncated slice.
    m.complete = (m.capture_sha256.size() > 0) &&
                 (rx.size() >= 2 * iqrflayout::kFramePeriodComplex) &&
                 (m.training_end <= rx.size()) &&
                 (m.payload_end <= rx.size()) &&
                 (m.full_frame_end <= rx.size()) &&
                 (rec.timing_offset < iqrflayout::kFramePeriodComplex);

    const SliceStats st = slice_stats(rx);
    m.rms = st.rms; m.dc_re = st.dc_re; m.dc_im = st.dc_im; m.peak = st.peak;
    m.clip = rx_clipped ? 1 : 0;
    m.cfo_hz = rec.cfo_hz;
    m.sro_ppm = rec.sro_ppm;
    m.gain_mag = rec.gain_mag;
    m.phase_deg = rec.phase_deg;
    m.training_corr = rec.training_corr;
    m.training_residual = rec.training_residual;
    (void)capture_complex;             // informational; the true size is rx.size()
    return m;
}

}  // namespace iqrffix9r2d
