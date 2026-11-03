#pragma once

// iq_fix10class24_logits_fusion.hpp -- fix10class24-noretrain (task 39e5) Phase C:
// FROZEN multi-capture fusion over N independent captures of the same source_index.
//
// Input: N captures -> N sets of raw 24-dim NPU logits + per-capture, label-INDEPENDENT
// quality fields.  Output: one fused 24-dim logit vector + one fused argmax.
//
// ONLY four fixed strategies (no label / baseline_pred / "which is correct" selection):
//   1. argmax majority vote
//   2. raw-logits equal-weight average
//   3. per-dimension median logits
//   4. quality-weighted logits average
//
// Quality weights use ONLY label-independent fields (training correlation, residual,
// clipping, CFO finiteness, sync validity).  The formula below is PRE-REGISTERED and
// FROZEN -- it has no per-class parameters and must never be tuned per class.
//
// Hard-invalid captures are REJECTED before any strategy runs: rx_clipped==1, any
// non-finite logit, sync fail, CFO out-of-range / non-finite, low correlation, or
// no signal.  A capture with payload_training_residual > 0.100 MAY still participate
// in DIAGNOSTIC fusion (it is a real, gate-refused capture), but must never be
// presented as passing the production 0.100 gate.

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace iqfusion {

// Production gate threshold -- mirrors the recovery core's max_residual=0.100.
// Frozen; never changed by this module.
constexpr double kProductionResidualGate = 0.100;

// Per-capture record.  All fields are label-independent by construction.
struct Capture {
    std::vector<float> logits;      // raw 24-dim NPU logits (N present)
    bool logits_finite = false;     // every element finite (else hard-invalid)
    bool rx_clipped = false;        // 1 -> hard-invalid
    bool sync_valid = false;        // false -> hard-invalid
    bool cfo_finite = false;        // false -> hard-invalid
    bool cfo_in_range = false;      // false -> hard-invalid
    bool has_signal = false;        // false -> hard-invalid
    double training_corr = 0.0;     // preamble/fractional correlation (quality only)
    double payload_training_residual = 0.0;  // gate field (quality only)
};

// Hard-invalid: never participates in any fusion strategy.
inline bool is_hard_invalid(const Capture& c) {
    if (c.logits.empty()) return true;
    if (!c.logits_finite) return true;
    if (c.rx_clipped) return true;
    if (!c.sync_valid) return true;
    if (!c.cfo_finite) return true;
    if (!c.cfo_in_range) return true;
    if (!c.has_signal) return true;
    return false;
}

// Stable softmax: y_i = exp(x_i - max_j x_j).  Returns empty on non-finite input.
inline std::vector<double> stable_softmax(const std::vector<float>& logits) {
    std::vector<double> out;
    if (logits.empty()) return out;
    float mx = -std::numeric_limits<float>::infinity();
    for (float v : logits) {
        if (!std::isfinite(v)) return std::vector<double>();
        mx = std::max(mx, v);
    }
    out.resize(logits.size());
    double denom = 0.0;
    for (std::size_t i = 0; i < logits.size(); ++i) {
        out[i] = std::exp(static_cast<double>(logits[i]) - static_cast<double>(mx));
        denom += out[i];
    }
    if (denom <= 0.0) return std::vector<double>();
    for (std::size_t i = 0; i < out.size(); ++i) out[i] /= denom;
    return out;
}

inline int argmax(const std::vector<float>& v) {
    if (v.empty()) return -1;
    int top = 0;
    for (std::size_t i = 1; i < v.size(); ++i)
        if (v[i] > v[static_cast<std::size_t>(top)]) top = static_cast<int>(i);
    return top;
}

// Strategy 1: argmax majority vote over valid captures.  Returns -1 if no valid
// capture or a tie (no tie-breaking by label/confidence).
inline int majority_vote(const std::vector<int>& argmaxes) {
    if (argmaxes.empty()) return -1;
    std::vector<int> votes;
    votes.reserve(argmaxes.size());
    for (int a : argmaxes) {
        if (a < 0) return -1;  // any invalid capture -> no vote (fail-closed)
        votes.push_back(a);
    }
    // count max tally
    int best = -1;
    int best_count = 0;
    bool tie = false;
    for (std::size_t i = 0; i < votes.size(); ++i) {
        int cnt = 0;
        for (std::size_t j = 0; j < votes.size(); ++j)
            if (votes[j] == votes[i]) ++cnt;
        if (cnt > best_count) {
            best_count = cnt;
            best = votes[i];
            tie = false;
        } else if (cnt == best_count && votes[i] != best) {
            tie = true;
        }
    }
    return tie ? -1 : best;
}

// Strategy 2: equal-weight average of raw logits.
inline std::vector<float> average_logits(
        const std::vector<std::vector<float>>& logits) {
    if (logits.empty()) return {};
    const std::size_t n = logits[0].size();
    std::vector<float> out(n, 0.0f);
    for (const auto& l : logits) {
        if (l.size() != n) return {};
        for (std::size_t i = 0; i < n; ++i) out[i] += l[i];
    }
    const double k = static_cast<double>(logits.size());
    for (std::size_t i = 0; i < n; ++i) out[i] = static_cast<float>(out[i] / k);
    return out;
}

// Strategy 3: per-dimension median of raw logits.
inline std::vector<float> median_logits(
        const std::vector<std::vector<float>>& logits) {
    if (logits.empty()) return {};
    const std::size_t n = logits[0].size();
    std::vector<float> out(n, 0.0f);
    std::vector<float> col(logits.size());
    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t k = 0; k < logits.size(); ++k) {
            if (logits[k].size() != n) return {};
            col[k] = logits[k][i];
        }
        std::sort(col.begin(), col.end());
        const std::size_t m = col.size();
        if (m % 2 == 1) {
            out[i] = col[m / 2];
        } else {
            out[i] = 0.5f * (col[m / 2 - 1] + col[m / 2]);
        }
    }
    return out;
}

// PRE-REGISTERED, FROZEN quality weight.  Label-independent fields only.
//   w = corr_clamped * cfo_finite * cfo_in_range * sync_valid * (1 - rx_clipped)
//       * 1 / (1 + payload_training_residual / kProductionResidualGate)
// Hard-invalid captures are rejected by the caller before weighting; this function
// simply returns 0.0 for any capture whose boolean fields fail.
inline double quality_weight(const Capture& c) {
    if (is_hard_invalid(c)) return 0.0;
    double corr = c.training_corr;
    if (!std::isfinite(corr)) return 0.0;
    corr = std::max(0.0, std::min(1.0, corr));
    const double res = std::isfinite(c.payload_training_residual)
                           ? c.payload_training_residual : 0.0;
    return corr / (1.0 + res / kProductionResidualGate);
}

// Strategy 4: quality-weighted average of raw logits.  Returns empty if no capture
// has positive weight.
inline std::vector<float> quality_weighted_logits(
        const std::vector<Capture>& caps) {
    if (caps.empty()) return {};
    const std::size_t n = caps[0].logits.size();
    std::vector<float> out(n, 0.0f);
    double wsum = 0.0;
    for (const Capture& c : caps) {
        if (c.logits.size() != n) return {};
        const double w = quality_weight(c);
        if (w <= 0.0) continue;
        wsum += w;
        for (std::size_t i = 0; i < n; ++i)
            out[i] += static_cast<float>(w * static_cast<double>(c.logits[i]));
    }
    if (wsum <= 0.0) return {};
    for (std::size_t i = 0; i < n; ++i)
        out[i] = static_cast<float>(out[i] / wsum);
    return out;
}

}  // namespace iqfusion
