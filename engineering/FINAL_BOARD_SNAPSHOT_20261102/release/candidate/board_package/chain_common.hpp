#pragma once

// chain_common.hpp — twelve-class SDR -> tensor preprocess chain + result-frame
// helpers shared by Gate 6/7/8/9 (task 39e5 §六/§七/§八/§九).
//
// iCraft-free and libiio-free: only depends on the sdr:: DSP primitives
// (nco / resampler / fir_coeffs / frame_analysis) and the cat::/rf::/classify::
// system-layer headers.  It is therefore host-testable (WSL g++), which is how
// the SDR->tensor conversion is proven before the board run.  The NPU wrapper
// (iCraft-only) lives separately in npu_classifier.hpp and is board-only.
//
// Model input contract (FROZEN, task 39e5 §六):
//   * single fp32 tensor [1,2,1024] = 2 planes x 1024 samples
//   * plane 0 = I (real), plane 1 = Q (imag)
//   * 128000 Hz sample rate
//   * input domain = raw training I/Q: clean-signal RMS == amplitude == 1.0
//     (see datasets/modulation_generator.py `_normalize_rms`).  The board maps
//     raw 12-bit ADC counts (full scale 2048, after iio_channel_convert) onto
//     this domain with ONE global fixed scalar (receiver_scale), never per-frame
//     RMS normalization (§九).

#include "../sdr_adapter/nco.hpp"
#include "../sdr_adapter/resampler.hpp"
#include "../sdr_adapter/fir_coeffs.h"
#include "../sdr_adapter/frame_analysis.hpp"
#include "../sdr_adapter/categories.hpp"
#include "../sdr_adapter/result_frame.hpp"
#include "../sdr_adapter/classify.hpp"
#include "rml23_merged.hpp"   // rml23::merge_logits_23 / kDeploymentMode (M29 Phase F5)

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <deque>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace chain {

constexpr std::size_t kFrameComplex = 1024;                 // samples per frame
constexpr std::size_t kTensorFloats = 2 * kFrameComplex;    // 2048
constexpr std::size_t kTensorBytes = kTensorFloats * sizeof(float);  // 8192
constexpr float kAdcFullScale = 2048.0f;   // AD9364 12-bit, post iio_channel_convert
constexpr double kTargetModelRms = 1.0;    // training clean-signal RMS (amplitude == 1.0)
constexpr const char* kResultVersion = "12class-chain-v1";
constexpr const char* kRml23ResultVersion = "rml23-chain-v2";  // M29 Phase F5 (23-class)
constexpr const char* kRml24ResultVersion = "rml24-chain-v1";  // M29 fix10class24-dualsdr1 (24-class raw)

// The authoritative 12-class order (== cat::target_12).  Returned as a fresh
// Contract so every consumer shares one source of truth.
inline cat::Contract contract_12() { return cat::target_12(); }

// RML2018 24-class source order and the deployed 23-class AM-SSB-merged order
// (M29 Phase F5).  The 24-class order is the NPU's raw output; the 23-class order
// is derived from it by the AM-SSB logaddexp merge (rml23_merged.hpp).
inline cat::Contract contract_24() { return cat::target_24(); }
inline cat::Contract contract_23() { return cat::target_23(); }

// Find the polyphase FIR spec whose fs_in matches; nullptr when absent.
inline const sdr::FirSpec* fir_spec_for(std::uint32_t fs_in) {
    for (std::size_t i = 0; i < sdr::kFirSpecCount; ++i)
        if (sdr::kFirSpecs[i].fs_in_hz == fs_in) return &sdr::kFirSpecs[i];
    return nullptr;
}

// Build the model input tensor [2,1024] (plane 0 = I, plane 1 = Q) from a
// 1024-complex frame.  out must hold kTensorFloats floats.  Each component is
// scaled by the global fixed receiver_scale.
inline void build_tensor(const std::complex<float>* frame, std::size_t n,
                         float rec_scale, float* out) {
    for (std::size_t k = 0; k < n; ++k) {
        out[k] = frame[k].real() * rec_scale;
        out[n + k] = frame[k].imag() * rec_scale;
    }
}

// Global fixed receiver_scale from a measured ADC RMS (int16 counts, full scale
// 2048) and the target model-domain RMS.  §九: determined by calibration, never
// hardcoded.  rec_scale = target_rms / (adc_rms / 2048).
inline float calibrate_rec_scale(double adc_rms_counts,
                                 double target_rms = kTargetModelRms) {
    if (!(adc_rms_counts > 0.0)) return 1.0f;
    return static_cast<float>(target_rms * static_cast<double>(kAdcFullScale) /
                              adc_rms_counts);
}

// ---------------------------------------------------------------------------
// Pre-scale capture (errata 39e5 #1, "B-level" capture point).
//
// A snapshot of the 1024-complex frame_ at the instant it completes, BEFORE
// receiver_scale is applied, plus the exact decimation state so the capture is
// reproducible off-line.  The observer receives the SAME data build_tensor()
// is about to consume -- it is not a second computation chain, and there is no
// dangling public getter to overwrite.  The frame vector is copied into the
// snapshot by PreprocessChain itself, so the observer may retain it.
// ---------------------------------------------------------------------------
struct PreScaleCapture {
    std::vector<std::complex<float>> frame;  // 1024 complex, pre-scale
    std::uint64_t in_complex = 0;            // input samples pushed so far
    std::uint64_t resampler_out = 0;         // valid resampler outputs so far
    std::uint64_t resampler_discarded = 0;   // transient outputs discarded
    std::uint64_t resampler_out_index = 0;   // absolute next-output index
    std::uint32_t up = 1, down = 1;          // decimation ratio
    std::uint32_t phase = 0;                 // polyphase phase of next output
    float rec_scale = 1.0f;                  // the scale NOT yet applied
};

using PreScaleObserver = std::function<void(const PreScaleCapture&)>;

// ---------------------------------------------------------------------------
// PreprocessChain — stateful SDR -> fp32-tensor conversion.
//   int16 interleaved (12-bit, FS 2048) -> complex (÷2048)
//     -> NCO downconvert (offset) -> polyphase resample (fs_in -> 128 kHz)
//     -> frame 1024 -> fp32 [2,1024] (× rec_scale)
// ---------------------------------------------------------------------------
class PreprocessChain {
public:
    PreprocessChain(std::uint32_t fs_in, double nco_offset_hz, float rec_scale)
        : nco_(nco_offset_hz, static_cast<double>(fs_in)),
          resampler_(make_resampler(fs_in)),
          rec_scale_(rec_scale) {}

    void reset() {
        nco_.reset();
        resampler_.reset();
        in_complex_ = 0;
        frame_.clear();
        ready_.clear();
    }

    // Default-off pre-scale observer.  When set, push_int16() snapshots each
    // completed frame_ (BEFORE receiver_scale) into a PreScaleCapture and calls
    // the observer exactly once per frame, before build_tensor() runs.  When
    // null (the default) nothing is allocated, copied or observed on the hot
    // path.  The observer must copy out what it needs -- it is called with a
    // const reference whose lifetime ends on return.
    void set_pre_scale_observer(PreScaleObserver fn) {
        pre_scale_observer_ = std::move(fn);
    }

    // Push n_complex interleaved int16 samples; complete [2,1024] tensors are
    // appended to the ready queue.
    void push_int16(const std::int16_t* iq, std::size_t n_complex) {
        in_buf_.resize(n_complex);
        for (std::size_t k = 0; k < n_complex; ++k) {
            in_buf_[k] = std::complex<float>(
                static_cast<float>(iq[k * 2 + 0]) / kAdcFullScale,
                static_cast<float>(iq[k * 2 + 1]) / kAdcFullScale);
        }
        nco_.mix(in_buf_.data(), n_complex);
        resampler_.push(in_buf_.data(), n_complex);
        in_complex_ += n_complex;

        const std::size_t avail = resampler_.available();
        if (avail == 0) return;
        out_buf_.resize(avail);
        const std::size_t got = resampler_.pull(out_buf_.data(), avail);
        for (std::size_t k = 0; k < got; ++k) {
            frame_.push_back(out_buf_[k]);
            if (frame_.size() == kFrameComplex) {
                if (pre_scale_observer_) {
                    PreScaleCapture cap;
                    cap.frame.assign(frame_.begin(), frame_.end());
                    cap.in_complex = in_complex_;
                    cap.resampler_out = resampler_.out_count();
                    cap.resampler_discarded = resampler_.discarded_transient();
                    cap.resampler_out_index = resampler_.out_index();
                    cap.up = resampler_.up();
                    cap.down = resampler_.down();
                    cap.phase = resampler_.current_phase();
                    cap.rec_scale = rec_scale_;
                    pre_scale_observer_(cap);
                }
                std::vector<float> t(kTensorFloats);
                build_tensor(frame_.data(), kFrameComplex, rec_scale_, t.data());
                ready_.push_back(std::move(t));
                frame_.clear();
            }
        }
    }

    std::size_t ready() const { return ready_.size(); }

    // Copy the next [2,1024] tensor into out; false when none ready.
    bool pull_tensor(float* out) {
        if (ready_.empty()) return false;
        const std::vector<float>& t = ready_.front();
        std::copy(t.begin(), t.end(), out);
        ready_.pop_front();
        return true;
    }

    std::uint64_t in_complex() const { return in_complex_; }
    std::uint64_t resampler_transient() const { return resampler_.discarded_transient(); }
    float rec_scale() const { return rec_scale_; }

    // Exact number of fs_in input complex samples required to emit `frames`
    // complete [2,1024] tensors, INCLUDING the FIR startup transient (which the
    // resampler discards before its first valid output).  For output sample index
    // m the newest input index consumed is floor(m*down/up), so to emit the last
    // valid output (transient + frames*1024 - 1) the stream must have pushed
    // floor(that * down/up) + 1 input samples.  This lets a gate size ONE RX
    // refill to hold the whole capture (no chunk loop, no phase-discontinuous
    // concatenation).
    std::size_t required_input(std::size_t frames) const {
        const std::uint64_t transient = resampler_.taps_total() - 1;
        const std::uint64_t last_out =
            transient + static_cast<std::uint64_t>(frames) * kFrameComplex - 1;
        const std::uint64_t last_in =
            (last_out * static_cast<std::uint64_t>(resampler_.down())) /
            static_cast<std::uint64_t>(resampler_.up());
        return static_cast<std::size_t>(last_in + 1);
    }

private:
    static sdr::StreamResampler make_resampler(std::uint32_t fs_in) {
        const sdr::FirSpec* spec = fir_spec_for(fs_in);
        if (!spec)
            throw std::runtime_error("no FIR spec for fs_in=" + std::to_string(fs_in));
        return sdr::StreamResampler(
            spec->up, spec->down,
            std::vector<double>(spec->coeffs, spec->coeffs + spec->n));
    }

    sdr::Nco nco_;
    sdr::StreamResampler resampler_;
    float rec_scale_;
    std::uint64_t in_complex_ = 0;

    std::vector<std::complex<float>> frame_;
    std::vector<std::complex<float>> in_buf_;
    std::vector<std::complex<float>> out_buf_;
    std::deque<std::vector<float>> ready_;
    PreScaleObserver pre_scale_observer_;  // default null -> capture disabled
};

// ---------------------------------------------------------------------------
// Result-frame helpers (§七/§八).
// ---------------------------------------------------------------------------

// Scalar quality in [0,1]: softmax confidence, degraded per source anomaly, and
// zeroed for a MOCK result (a mock result is never a quality result).
inline double compute_quality(const rf::ResultFrame& r) {
    if (r.mock) return 0.0;
    double q = (r.confidence < 0.0) ? 0.0 : static_cast<double>(r.confidence);
    if (q > 1.0) q = 1.0;
    if (r.overflow) q *= 0.75;
    if (r.dropped) q *= 0.75;
    if (r.discontinuity) q *= 0.75;
    if (r.short_frame) q *= 0.75;
    return q;
}

// Fill the §七 extension fields from logits.  `logits` is the raw NPU output
// (12 values for the twelve-class model); `snr_db` may be NaN when unknown.
inline void fill_result(rf::ResultFrame& r, const std::vector<float>& logits,
                        const cat::Contract& contract, const std::string& model_sha,
                        double snr_db) {
    r.class_count = contract.class_count;
    r.logits = logits;
    classify::softmax_into(logits, r.probabilities);   // reuse-safe (M22)

    r.argmax_idx = -1;
    if (!logits.empty()) {
        r.argmax_idx = 0;
        for (int i = 1; i < static_cast<int>(logits.size()); ++i)
            if (logits[i] > logits[r.argmax_idx]) r.argmax_idx = i;
    }
    r.argmax_class = cat::label(contract, r.argmax_idx);
    r.confidence = (r.argmax_idx >= 0 &&
                    r.argmax_idx < static_cast<int>(r.probabilities.size()))
                       ? r.probabilities[static_cast<std::size_t>(r.argmax_idx)]
                       : 0.0f;
    r.version = kResultVersion;
    r.model_sha = model_sha;
    r.snr_db = snr_db;
    r.quality = compute_quality(r);
}

// Fill the RML23 deployment fields (M29 Phase F5).  `raw_24_logits` is the full
// 24-dim raw NPU output (preserved for the future SC/WC expert); `merged_23_logits`
// is the 23-dim AM-SSB-merged logits that drive the displayed verdict.  `contract23`
// must be cat::target_23() (== rml23::kLabelOrder23).  The expert flags are always
// false / "NOT_RUN" (no SC/WC expert in this task).
inline void fill_result_rml23(rf::ResultFrame& r,
                              const std::vector<float>& raw_24_logits,
                              const std::vector<float>& merged_23_logits,
                              const cat::Contract& contract23,
                              const std::string& model_sha, double snr_db) {
    r.class_count = contract23.class_count;
    r.logits = merged_23_logits;
    classify::softmax_into(merged_23_logits, r.probabilities);

    r.argmax_idx = -1;
    if (!merged_23_logits.empty()) {
        r.argmax_idx = 0;
        for (int i = 1; i < static_cast<int>(merged_23_logits.size()); ++i)
            if (merged_23_logits[i] > merged_23_logits[r.argmax_idx]) r.argmax_idx = i;
    }
    r.argmax_class = cat::label(contract23, r.argmax_idx);
    r.confidence = (r.argmax_idx >= 0 &&
                    r.argmax_idx < static_cast<int>(r.probabilities.size()))
                       ? r.probabilities[static_cast<std::size_t>(r.argmax_idx)]
                       : 0.0f;

    r.raw_24_logits = raw_24_logits;
    r.raw_24_top1 = -1;
    if (!raw_24_logits.empty()) {
        r.raw_24_top1 = 0;
        for (int i = 1; i < static_cast<int>(raw_24_logits.size()); ++i)
            if (raw_24_logits[i] > raw_24_logits[r.raw_24_top1]) r.raw_24_top1 = i;
    }
    r.merged_23_top1 = r.argmax_idx;
    r.deployment_mode = rml23::kDeploymentMode;   // "AMSSB_MERGED"
    r.expert_enabled = false;
    r.expert_result = rml23::kExpertResult;       // "NOT_RUN"

    r.version = kRml23ResultVersion;
    r.model_sha = model_sha;
    r.snr_db = snr_db;
    r.quality = compute_quality(r);
}

// Fill the RML24 raw-24 deployment fields (M29 fix10class24-dualsdr1).  `logits24`
// is the full 24-dim raw NPU output; there is NO AM-SSB merge on this path, so the
// displayed verdict is the raw 24-class argmax (WC=17 and SC=18 stay independent).
// `contract24` must be cat::target_24() (== rml24::kLabelOrder24).
inline void fill_result_rml24(rf::ResultFrame& r,
                              const std::vector<float>& logits24,
                              const cat::Contract& contract24,
                              const std::string& model_sha, double snr_db) {
    r.class_count = contract24.class_count;
    r.logits = logits24;
    classify::softmax_into(logits24, r.probabilities);

    r.argmax_idx = -1;
    if (!logits24.empty()) {
        r.argmax_idx = 0;
        for (int i = 1; i < static_cast<int>(logits24.size()); ++i)
            if (logits24[i] > logits24[r.argmax_idx]) r.argmax_idx = i;
    }
    r.argmax_class = cat::label(contract24, r.argmax_idx);
    r.confidence = (r.argmax_idx >= 0 &&
                    r.argmax_idx < static_cast<int>(r.probabilities.size()))
                       ? r.probabilities[static_cast<std::size_t>(r.argmax_idx)]
                       : 0.0f;

    r.raw_24_logits = logits24;
    r.raw_24_top1 = r.argmax_idx;
    r.merged_23_top1 = -1;              // no merge on the raw24 path
    r.deployment_mode = "RAW24_UNMERGED";
    r.expert_enabled = false;
    r.expert_result = "NOT_RUN";

    r.version = kRml24ResultVersion;
    r.model_sha = model_sha;
    r.snr_db = snr_db;
    r.quality = compute_quality(r);
}

// SNR estimate for a frame containing a known CW tone: coherent tone power vs the
// residual.  Approximation documented in RECEIVER_SCALE_CALIBRATION.md; used only
// for the loopback phases of Gate 9 (diagnostic, not a PASS gate).  Returns NaN
// for an empty frame.
inline double tone_snr_db(const std::vector<std::complex<float>>& frame,
                          double f_hz, double fs_hz) {
    const std::size_t n = frame.size();
    if (n == 0) return std::numeric_limits<double>::quiet_NaN();
    const double bin_energy = std::norm(sdr::goertzel_bin(frame, f_hz, fs_hz));  // |A|^2 N^2
    const double tone_power = bin_energy / static_cast<double>(n);               // |A|^2 N
    double total_energy = 0.0;
    for (const auto& v : frame)
        total_energy += static_cast<double>(std::norm(v));
    const double noise_power = total_energy - tone_power;
    if (noise_power <= 0.0) return 120.0;  // pure tone -> cap
    return 10.0 * std::log10(tone_power / noise_power);
}

}  // namespace chain
