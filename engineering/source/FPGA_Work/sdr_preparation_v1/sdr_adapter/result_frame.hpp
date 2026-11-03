#pragma once

// ResultFrame -- the per-frame verdict produced by the classification interface
// and handed to the HDMI JSONL / UnixSocket adapters.
//
// Pure data (no serialization dependency here); ui_report.hpp serializes it to a
// JSON-lines record.  `mock` is carried through so a MOCK result can never be
// mistaken for a real inference downstream.

#include <cstdint>
#include <string>
#include <vector>

namespace rf {

struct ResultFrame {
    std::uint64_t frame_id = 0;
    std::uint64_t timestamp_us = 0;

    int class_count = 0;           // contract width (8 / 10 / 12 / ...)
    int argmax_idx = -1;           // -1 when no logits
    std::string argmax_class;      // "<i>" when out of range
    float confidence = 0.0f;       // softmax top-1, in [0,1]
    std::vector<float> logits;     // full logits (programmatic use; not in JSONL)

    bool mock = false;             // true => MOCK logits, NOT real inference
    std::string source;            // "mock" / "fpga_npu" / ...

    // Per-frame latencies (microseconds).
    double preprocess_us = 0.0;
    double classify_us = 0.0;
    double e2e_us = 0.0;

    // Source anomaly flags, carried through unchanged.
    bool overflow = false;
    bool dropped = false;
    bool discontinuity = false;
    bool short_frame = false;
};

}  // namespace rf
