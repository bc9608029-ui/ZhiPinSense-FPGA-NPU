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

    // ---- twelve-class chain extensions (task 39e5 §七) ----
    // These fields are ADDED for the SDR->NPU->UI chain.  They do not change the
    // meaning of the fields above; the Gate 1-5 consumers ignore them.
    std::string version;              // result-frame schema tag, e.g. "12class-chain-v1"
    std::vector<float> probabilities; // softmax over logits, size == class_count
                                      // (empty when no logits / not computed)
    double snr_db = 0.0;              // per-frame SNR estimate (dB); NaN when unknown
    double quality = 0.0;             // scalar quality in [0,1] (see ui_report.hpp)
    std::string model_sha;            // SHA256 of the NPU model.raw (provenance)
};

}  // namespace rf
