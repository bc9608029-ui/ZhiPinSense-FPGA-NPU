#pragma once

// ResultFrame -- the per-frame verdict produced by the classification interface
// and handed to the HDMI JSONL / UnixSocket adapters.
//
// Pure data (no serialization dependency here); ui_report.hpp serializes it to a
// JSON-lines record.  `mock` is carried through so a MOCK result can never be
// mistaken for a real inference downstream.

#include "dsp_measure.hpp"   // sdr::FrameMeasurements (UI v3 M4 measurements field)

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

    // ---- UI v3 extensions (task 39e5 UI v3 M4) ----
    // Additive; older consumers ignore them.  Serialized only by
    // ui_report.hpp::result_frame_v3_line() (schema tag "12class-chain-v2").
    bool has_measurements = false;        // true => `measurements` carries real data
    sdr::FrameMeasurements measurements;  // M3 raw/spectrum/model measurements
    std::string presence_state;           // M1 state name ("" = not set)
    std::string level_mode;               // M2 "FIXED" / "AUTO" ("" = not set)
    double model_scale = 1.0;             // M2 digital scalar (identity default)
    double rf_gain_db = 0.0;              // M2 RF gain (dB)

    // ---- UI v3 M6 (producer integration) ----
    // Work mode + run state are OWNED by the producer (Gate 9).  They travel on
    // the wire as mode_ctl tokens ("FIXED"/"AUTO_LOCK"/"BAND_SCAN" and
    // "RUNNING"/"STOPPED"); the UI only displays what the producer reports (it
    // must never self-modify these to fake mode effectiveness).
    std::string work_mode;               // mode_ctl wire token ("" = not set)
    std::string run_state;               // "RUNNING"/"STOPPED" ("" = not set)

    // ---- RML23 deployment extensions (M29 Phase F5) ----
    // The NPU still emits 24 raw logits; the software merges AM-SSB-SC+WC into a
    // single "AM-SSB" slot to produce a 23-class verdict.  `logits` (above) holds
    // the 23-dim merged logits; `raw_24_logits` preserves the full 24-dim raw
    // output for future SC/WC expert use.  `raw_24_top1`/`merged_23_top1` are the
    // argmax indices in the 24-dim source / 23-dim deployed label spaces.  The
    // expert is NOT trained or run in this package: `expert_enabled` is always
    // false and `expert_result` is always "NOT_RUN".
    std::vector<float> raw_24_logits;    // full 24-dim raw NPU logits (preserved)
    int raw_24_top1 = -1;                // argmax in the 24-dim source order
    int merged_23_top1 = -1;             // argmax in the 23-dim deployed order
    std::string deployment_mode;         // "AMSSB_MERGED" ("" = not RML23); see rml23::kDeploymentMode
    bool expert_enabled = false;         // always false this round
    std::string expert_result;           // always "NOT_RUN" this round

    // Final RML24 display payload. These samples are derived from the exact
    // recovered model tensor and are never consumed by inference.
    bool iq_display_valid = false;
    std::vector<std::int16_t> iq_i16_interleaved;  // 256 (I,Q) points
    double iq_units_per_count = 0.0;
};

}  // namespace rf
