// M29 fix10class24-dualsdr1 Phase 2 — 24-raw-class UNMERGED post-processing.
//
// Header-only, namespace rml24.  The NPU (full-network BF16) emits raw 24-dim
// logits; this module reports them as 24 classes directly:
//
//     pred = argmax_24(logits)   -- NO 24->23 fold, NO AM-SSB merge.
//
// AM-SSB-WC (17) and AM-SSB-SC (18) stay TWO independent classes.  merge23() is
// deliberately ABSENT from this header: the 23-class merge lives only in
// rml23_merged.hpp and must never be applied on the 24-class path.
//
// Fail-closed: any non-finite logit makes raw24_predict return false with
// valid=false.  Stateless: no per-frame allocation, no mutable state.
#pragma once

#include <cmath>
#include <cstddef>

namespace rml24 {

constexpr int kClassCount = 24;
constexpr int kNpuOutputDim = 24;
constexpr int kAmSsbWc = 17;   // AM-SSB-WC in the 24-dim output
constexpr int kAmSsbSc = 18;   // AM-SSB-SC in the 24-dim output (independent)

inline constexpr const char* kDeploymentMode = "RAW24_UNMERGED";
inline constexpr const char* kModelMode = "RML24-BF16-RAW";  // UI display identity

// Frozen 24-class label order (verbatim copy of the frozen contract).
inline constexpr const char* kLabelOrder24[kClassCount] = {
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
};

struct RML24Result {
    int raw_24_top1 = -1;         // raw 24-dim argmax (the only result, no merge)
    const char* raw_24_label = nullptr;
    float raw_margin = 0.0f;      // top1 - top2 in 24-dim space
    bool valid = false;           // false when input had NaN/Inf (fail-closed)
};

// Fail-closed raw-24 argmax.  Returns true and fills ``out`` on success; returns
// false with out->valid=false if any logit is non-finite or pointers are null.
inline bool raw24_predict(const float* logits24, RML24Result* out) {
    if (logits24 == nullptr || out == nullptr) return false;
    out->valid = false;
    for (int i = 0; i < kNpuOutputDim; ++i) {
        if (!std::isfinite(logits24[i])) return false;
    }
    int top = 0;
    for (int i = 1; i < kNpuOutputDim; ++i) {
        if (logits24[i] > logits24[top]) top = i;
    }
    int second = (top == 0) ? 1 : 0;
    for (int i = 0; i < kNpuOutputDim; ++i) {
        if (i != top && logits24[i] > logits24[second]) second = i;
    }
    out->raw_24_top1 = top;
    out->raw_24_label = kLabelOrder24[top];
    out->raw_margin = logits24[top] - logits24[second];
    out->valid = true;
    return true;
}

}  // namespace rml24
