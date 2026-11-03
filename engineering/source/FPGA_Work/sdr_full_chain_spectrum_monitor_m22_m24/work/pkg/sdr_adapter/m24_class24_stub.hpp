#pragma once

// m24_class24_stub.hpp -- M24-A 24-class interface stub (SIMULATED ONLY).
//
// Freezes the [N,2,1024] -> 24-dim interface and label mapping so the UI /
// event path can be developed and tested now, WITHOUT a real model.  It
// refuses to load when the model SHA is missing, always emits exactly 24
// logits, and marks every result SIMULATED.  It never reports a class accuracy
// and never writes 24CLASS_PASS.

#include "m24_class24_contract.hpp"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace m24 {

struct Class24Manifest {
    std::string model_name;
    std::string model_sha256;        // 64 hex chars; empty/malformed -> refuse
    std::string label_order_source;  // provenance (optional)
};

struct Class24Result {
    bool valid = false;
    bool simulated = true;   // ALWAYS true for the stub
    std::string error;
    std::vector<float> logits;  // exactly CLASS24_NUM_CLASSES when valid
    int argmax = -1;
    std::string class_name;
};

class Class24Stub {
public:
    // Refuse to load when the model SHA is missing or malformed (fail-closed).
    bool load(const Class24Manifest& m) {
        if (m.model_sha256.size() != 64) {
            error_ = "model SHA missing or malformed: refuse to load";
            loaded_ = false;
            return false;
        }
        manifest_ = m;
        loaded_ = true;
        error_.clear();
        return true;
    }

    bool loaded() const { return loaded_; }
    const Class24Manifest& manifest() const { return manifest_; }
    const std::string& error() const { return error_; }
    const std::array<std::string, CLASS24_NUM_CLASSES>& labels() const {
        return class24_labels();
    }

    // Deterministic fake logits from the raw IQ.  iq points to n frames of
    // CLASS24_INPUT_STRIDE floats each (I then Q, row-major).  Same input ->
    // identical logits.  Output is exactly CLASS24_NUM_CLASSES.
    Class24Result classify(const float* iq, std::size_t n) const {
        Class24Result r;
        r.simulated = true;
        if (!loaded_) {
            r.error = "stub not loaded";
            return r;
        }
        if (iq == nullptr || n == 0) {
            r.error = "empty input";
            return r;
        }
        const std::size_t total = n * CLASS24_INPUT_STRIDE;
        double acc = 0.0;
        double energy = 0.0;
        for (std::size_t k = 0; k < total; ++k) {
            const double v = static_cast<double>(iq[k]);
            if (!std::isfinite(v)) {
                r.error = "non-finite input sample";
                return r;
            }
            acc += v;
            energy += v * v;
        }
        // Deterministic seed from the two scalar reductions.
        const std::uint64_t s =
            static_cast<std::uint64_t>(std::fabs(acc) * 1.0e6) +
            static_cast<std::uint64_t>(energy * 1.0e3);
        const std::size_t top = static_cast<std::size_t>(s % CLASS24_NUM_CLASSES);

        r.logits.assign(CLASS24_NUM_CLASSES, 0.0f);
        for (std::size_t i = 0; i < CLASS24_NUM_CLASSES; ++i) {
            const std::uint64_t h = (s * 2654435761ULL) + (i * 0x9E3779B9ULL);
            r.logits[i] = static_cast<float>(static_cast<int>(h % 1000)) / 100.0f -
                          5.0f;  // deterministic jitter in [-5, 5)
        }
        r.logits[top] = 10.0f;  // deterministic argmax
        r.argmax = static_cast<int>(top);
        r.class_name = class24_labels()[top];
        r.valid = true;
        return r;
    }

private:
    Class24Manifest manifest_;
    bool loaded_ = false;
    std::string error_;
};

}  // namespace m24
