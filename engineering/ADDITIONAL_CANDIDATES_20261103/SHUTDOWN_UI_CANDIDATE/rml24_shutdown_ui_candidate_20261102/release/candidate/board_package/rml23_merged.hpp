// M29 Phase F4 — 23-class AM-SSB merged post-processing (board integration).
//
// Header-only, namespace rml23.  The NPU still emits raw 24-dim logits; this
// module produces the deployed 23-class result:
//
//     merged[17] = logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC)
//                = log( exp(logit_SC) + exp(logit_WC) )
//
// All other dims copy through; dims 19..23 shift down by one.  The raw 24-dim
// top-1 is always preserved alongside the merged result.  Fail-closed: any
// non-finite logit makes merge_predict return false with valid=false.
//
// Stateless: no per-frame allocation, no mutable state; safe for a model that is
// loaded once and re-run per frame without reopen.
#pragma once

#include <cmath>
#include <cstddef>

namespace rml23 {

constexpr int kSourceClassCount = 24;
constexpr int kDeployedClassCount = 23;
constexpr int kNpuOutputDim = 24;
constexpr int kAmSsbSourceWc = 17;   // AM-SSB-WC in the 24-dim source
constexpr int kAmSsbSourceSc = 18;   // AM-SSB-SC in the 24-dim source
constexpr int kAmSsbDeployed = 17;   // "AM-SSB" in the 23-class output

inline constexpr const char* kDeploymentMode = "AMSSB_MERGED";
inline constexpr const char* kModelMode = "RML23-AMSSB-MERGED";  // UI display identity
inline constexpr const char* kExpertResult = "NOT_RUN";

// 24-dim source index -> 23-class slot (17 and 18 both land in 17).
inline constexpr int kSourceToDeployed[kNpuOutputDim] = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 17, 18, 19, 20, 21, 22,
};

inline constexpr const char* kLabelOrder23[kDeployedClassCount] = {
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB", "AM-DSB-WC", "AM-DSB-SC", "FM", "GMSK",
    "OQPSK",
};

// Numerically-stable log(exp(a)+exp(b)); correct at the infinities.
inline float logaddexp(float a, float b) {
    if (std::isinf(a) && a < 0.0f) return b;
    if (std::isinf(b) && b < 0.0f) return a;
    if (std::isinf(a) && a > 0.0f) return a;   // +inf dominates
    if (std::isinf(b) && b > 0.0f) return b;
    const float m = (a > b) ? a : b;
    const float n = (a > b) ? b : a;
    return m + std::log1p(std::exp(n - m));
}

struct RML23Result {
    int raw_24_top1 = -1;      // raw 24-dim argmax (source of truth, preserved)
    int merged_23_top1 = -1;   // deployed 23-class argmax after AM-SSB merge
    const char* merged_23_label = nullptr;
    float merged_margin = 0.0f;  // merged top1 - top2 (23-dim space)
    bool valid = false;          // false when input had NaN/Inf (fail-closed)
    bool expert_enabled = false; // always false: no SC/WC expert in this task
};

// Compute the merged 23-dim logits.  Returns false (fail-closed) on null or any
// non-finite input; otherwise fills out23[0..22].
inline bool merge_logits_23(const float* logits24, float* out23) {
    if (logits24 == nullptr || out23 == nullptr) return false;
    for (int i = 0; i < kNpuOutputDim; ++i) {
        if (!std::isfinite(logits24[i])) return false;
    }
    for (int i = 0; i < kDeployedClassCount; ++i) out23[i] = -INFINITY;
    for (int i = 0; i < kNpuOutputDim; ++i) {
        const int d = kSourceToDeployed[i];
        if (i == kAmSsbSourceSc) {
            out23[d] = logaddexp(out23[d], logits24[i]);  // fold SC into the WC slot
        } else {
            out23[d] = logits24[i];
        }
    }
    return true;
}

// Fail-closed merge.  Returns true and fills ``out`` on success; returns false
// with out->valid=false if any logit is non-finite or pointers are null.
inline bool merge_predict(const float* logits24, RML23Result* out) {
    if (out == nullptr) return false;
    out->valid = false;
    float m23[kDeployedClassCount];
    if (!merge_logits_23(logits24, m23)) return false;

    int raw = 0;
    for (int i = 1; i < kNpuOutputDim; ++i) {
        if (logits24[i] > logits24[raw]) raw = i;
    }
    out->raw_24_top1 = raw;

    int top = 0;
    for (int i = 1; i < kDeployedClassCount; ++i) {
        if (m23[i] > m23[top]) top = i;
    }
    int second = (top == 0) ? 1 : 0;
    for (int i = 0; i < kDeployedClassCount; ++i) {
        if (i != top && m23[i] > m23[second]) second = i;
    }
    out->merged_23_top1 = top;
    out->merged_23_label = kLabelOrder23[top];
    out->merged_margin = m23[top] - m23[second];
    out->expert_enabled = false;
    out->valid = true;
    return true;
}

}  // namespace rml23
