#pragma once

// Classification interface + MOCK logits for the non-model system layer.
//
// classify::Classifier is the abstraction the FPGA/NPU classification path would
// implement (IQ frame + physical features -> N logits, N = the category contract
// width).  Offline, classify::MockClassifier stands in: it emits clearly-marked
// MOCK logits (Logits::mock == true) whose argmax is deterministic but is NOT a
// real model decision.  Nothing here may be reported as real inference.
//
// iCraft-free and header-only; unit-tested (logits width, mock flag, argmax
// range, determinism, softmax/top1 properties).

#include "categories.hpp"
#include "iq_frame.hpp"
#include "preprocess.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <utility>
#include <vector>

namespace classify {

// Logits for one frame.  width == contract.class_count.  `mock` MUST be true for
// any non-model output; `source` names the producer ("mock" / "fpga_npu" / ...).
struct Logits {
    std::vector<float> values;
    bool mock = false;
    std::string source = "unspecified";
};

// argmax index, -1 when empty.
inline int argmax(const Logits& l) {
    if (l.values.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(l.values.size()); ++i)
        if (l.values[i] > l.values[best]) best = i;
    return best;
}

// Stable softmax (max-shifted for numerical safety); empty -> empty.
inline std::vector<float> softmax(const std::vector<float>& x) {
    if (x.empty()) return {};
    const float m = *std::max_element(x.begin(), x.end());
    std::vector<float> p(x.size());
    double sum = 0.0;
    for (std::size_t i = 0; i < x.size(); ++i) {
        p[i] = std::exp(static_cast<double>(x[i] - m));
        sum += p[i];
    }
    for (std::size_t i = 0; i < x.size(); ++i)
        p[i] = static_cast<float>(p[i] / sum);
    return p;
}

// {argmax index, softmax confidence}.  Confidence in [0,1]; {-1, 0} when empty.
inline std::pair<int, float> top1(const Logits& l) {
    if (l.values.empty()) return {-1, 0.0f};
    const int idx = argmax(l);
    return {idx, softmax(l.values)[static_cast<std::size_t>(idx)]};
}

// Classification interface: what the FPGA/NPU path implements.  The offline
// chain substitutes MockClassifier; the board path substitutes the real NPU
// classifier (board_package), keeping this layer iCraft-free.
class Classifier {
public:
    virtual ~Classifier() = default;
    virtual Logits classify(const iq::Frame& frame,
                            const preproc::PhysicalPlane& features) = 0;
};

// Deterministic pseudo-logits.  NOT a model: the scores are a fixed hash of
// (frame_id, class_index) with a small, bounded coupling to the frame energy so
// the output genuinely depends on the input (proving the preprocess -> classify
// data flow is live).  Always mock == true, source == "mock".
class MockClassifier : public Classifier {
public:
    explicit MockClassifier(const cat::Contract& contract)
        : contract_(contract) {}

    Logits classify(const iq::Frame& frame,
                    const preproc::PhysicalPlane& features) override {
        const int n = contract_.class_count;
        Logits out;
        out.mock = true;
        out.source = "mock";
        out.values.assign(static_cast<std::size_t>(n), 0.0f);

        // Normalised mean power in ~[0,2] (bounded feature summary).
        double energy = 0.0;
        for (float p : features.power) energy += p;
        energy /= features.power.empty() ? 1.0
                                         : static_cast<double>(features.power.size());
        energy /= (32767.0 * 32767.0);

        for (int i = 0; i < n; ++i) {
            const std::uint64_t h =
                splitmix64(frame.frame_id ^
                           (static_cast<std::uint64_t>(i) * 0x9E3779B97F4A7C15ULL));
            const double base = static_cast<double>(h % 10000);
            const double coupling = static_cast<double>((h >> 20) % 100) / 100.0;
            out.values[static_cast<std::size_t>(i)] =
                static_cast<float>(base + energy * coupling * 10.0);
        }
        return out;
    }

private:
    static std::uint64_t splitmix64(std::uint64_t x) {
        x += 0x9E3779B97F4A7C15ULL;
        x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
        x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
        return x ^ (x >> 31);
    }

    cat::Contract contract_;
};

}  // namespace classify
