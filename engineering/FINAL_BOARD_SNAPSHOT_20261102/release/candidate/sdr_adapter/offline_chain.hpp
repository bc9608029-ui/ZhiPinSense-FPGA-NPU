#pragma once

// Offline File-IQ end-to-end chain composition.
//
//   FileIqSource -> 1024-sample int16 frame -> deployment preprocessing
//   (physical frontend) -> classification interface (MockClassifier offline)
//   -> ResultFrame -> HDMI JSONL / UnixSocket sink.
//
// The chain is the non-model system layer's offline reference: it proves the
// data flow from a frozen IQ buffer to a JSON-lines verdict without iCraft, SDR
// or a board.  On the board the MockClassifier is swapped for the real NPU
// classifier (board_package) and the source for PlutoIqSource; the frame /
// preprocess / ResultFrame / sink stages are reused unchanged.
//
// iCraft-free and header-only; unit-tested end-to-end with FileIqSource.

#include "categories.hpp"
#include "classify.hpp"
#include "iq_frame.hpp"
#include "logging.hpp"
#include "perf_stats.hpp"
#include "preprocess.hpp"
#include "result_frame.hpp"
#include "sequence_monitor.hpp"
#include "ui_report.hpp"

#include <chrono>
#include <cstdint>

namespace chain {

struct ChainConfig {
    std::uint64_t max_frames = 0;  // 0 = run until end-of-stream
    bool skip_short = true;        // never classify a short frame
};

struct ChainStats {
    std::uint64_t frames = 0;       // frames observed from the source
    std::uint64_t short_frames = 0; // short frames skipped
    std::uint64_t overflow = 0;
    std::uint64_t dropped = 0;
    std::uint64_t discontinuity = 0;
    std::uint64_t classified = 0;   // frames that reached the classifier
};

// Build a ResultFrame from a source frame, logits and the category contract.
inline rf::ResultFrame make_result(const iq::Frame& f,
                                   const classify::Logits& logits,
                                   const cat::Contract& contract) {
    rf::ResultFrame r;
    r.frame_id = f.frame_id;
    r.timestamp_us = f.timestamp_us;
    r.class_count = contract.class_count;
    r.logits = logits.values;
    r.mock = logits.mock;
    r.source = logits.source;
    r.overflow = f.overflow;
    r.dropped = f.dropped;
    r.discontinuity = f.discontinuity;
    r.short_frame = f.short_frame;
    const auto top = classify::top1(logits);
    r.argmax_idx = top.first;
    r.confidence = top.second;
    r.argmax_class = cat::label(contract, top.first);
    return r;
}

// Run the offline chain.  `src` and `cls` are used, not owned; `sink` receives
// one JSON-lines record per classified frame.  Returns aggregate counters.
inline ChainStats run(iq::Source& src, classify::Classifier& cls,
                      const cat::Contract& contract, ui::Sink& sink,
                      perf::PerfStats* perf = nullptr, ChainConfig cfg = {}) {
    ChainStats st;
    iq::SequenceMonitor mon;
    iq::Frame f;

    while (cfg.max_frames == 0 || st.frames < cfg.max_frames) {
        if (!src.next(f)) break;  // clean end-of-stream
        ++st.frames;
        mon.observe(f);
        if (f.overflow) ++st.overflow;
        if (f.dropped) ++st.dropped;
        if (f.discontinuity) ++st.discontinuity;

        if (f.short_frame) {
            ++st.short_frames;
            if (cfg.skip_short) {
                LOG_WARN("offline_chain: short frame %llu skipped (not classified)",
                         static_cast<unsigned long long>(f.frame_id));
                continue;
            }
            continue;  // never classify a short frame (would violate the contract)
        }

        const auto t0 = std::chrono::steady_clock::now();
        preproc::PhysicalPlane feat =
            preproc::physical_frontend(f.iq, iq::kComplexSamplesPerFrame);
        classify::Logits logits = cls.classify(f, feat);
        const auto t1 = std::chrono::steady_clock::now();

        rf::ResultFrame r = make_result(f, logits, contract);
        r.e2e_us = std::chrono::duration<double, std::micro>(t1 - t0).count();
        ++st.classified;

        sink.write(ui::result_frame_line(r));
        if (perf) perf->record(perf::Stage::kEndToEnd, r.e2e_us);
    }

    if (!mon.healthy()) {
        LOG_WARN("offline_chain: sequence anomalies detected (drop/dup/reorder/"
                 "overflow/discontinuity/short) -- see ChainStats");
    }
    return st;
}

}  // namespace chain
