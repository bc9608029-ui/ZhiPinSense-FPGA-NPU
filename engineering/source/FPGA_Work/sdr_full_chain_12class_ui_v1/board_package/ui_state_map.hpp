#pragma once

// ui_state_map.hpp -- ResultFrame -> ui::UiState bridge (task 39e5 §四/§七).
//
// Pure, iCraft-free mapping of a validated rf::ResultFrame into the Style A UI
// state, plus the staleness helpers the live server uses between frames.  A MOCK
// result is NEVER promoted to Live and never drops its MOCK badge downstream;
// an anomaly-flagged frame becomes Error; everything else is Live.  This is the
// one place those decisions live so the host test can assert them directly.

#include "../sdr_adapter/result_frame.hpp"
#include "../ui_sw/ui_render.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>

namespace ui {

// First 8 chars of the model SHA256 (short provenance tag for the info strip).
inline std::string short_sha(const std::string& sha) {
    return sha.size() <= 8 ? sha : sha.substr(0, 8);
}

// Map a validated ResultFrame into the UI state.  `age` is left empty here; the
// server sets it (and swaps the status to Stale) when the feed goes quiet.
inline ui::UiState map_to_state(const rf::ResultFrame& r) {
    ui::UiState st;
    if (r.mock) {
        st.status = ui::Status::Mock;
        st.source = "MOCK";
    } else if (r.overflow || r.dropped || r.discontinuity || r.short_frame) {
        st.status = ui::Status::Error;
        st.source = r.source.empty() ? "SDR" : r.source;
    } else {
        st.status = ui::Status::Live;
        st.source = r.source.empty() ? "SDR" : r.source;
    }

    st.top1 = r.argmax_class;
    st.conf = r.confidence;
    st.dist = r.probabilities;
    st.frame = std::to_string(r.frame_id);
    st.classes = &ui::classes_12();

    if (std::isnan(r.snr_db)) {
        st.snr = "--";
    } else {
        char b[32];
        std::snprintf(b, sizeof(b), "%+.1f dB", r.snr_db);
        st.snr = b;
    }

    // Latency: prefer end-to-end, fall back to NPU-forward classify time.
    const double us = (r.e2e_us > 0.0) ? r.e2e_us : (r.classify_us > 0.0 ? r.classify_us : 0.0);
    if (us > 0.0) {
        char b[32];
        std::snprintf(b, sizeof(b), "%.1f ms", us / 1000.0);
        st.lat = b;
    } else {
        st.lat = "--";
    }

    st.model = short_sha(r.model_sha);
    return st;
}

// True when the feed has gone quiet for `stale_ms` (both timestamps in the same
// millisecond epoch).  stale_ms <= 0 disables staleness.
inline bool should_be_stale(std::int64_t now_ms, std::int64_t last_ms,
                            std::int64_t stale_ms) {
    return stale_ms > 0 && last_ms > 0 && (now_ms - last_ms) >= stale_ms;
}

// "%.1f s" of a millisecond age.
inline std::string format_age(std::int64_t age_ms) {
    char b[32];
    std::snprintf(b, sizeof(b), "%.1f s", static_cast<double>(age_ms) / 1000.0);
    return b;
}

}  // namespace ui
