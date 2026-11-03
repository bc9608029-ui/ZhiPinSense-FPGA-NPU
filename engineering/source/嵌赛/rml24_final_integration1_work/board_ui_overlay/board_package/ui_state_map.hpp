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
#include "mode_control.hpp"
#include "result_frame_v2_parse.hpp"
#include "rml23_merged.hpp"   // rml23::kModelMode (M29 Phase F5)

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
    } else if (r.presence_state == "NO_SIGNAL") {
        // Frames ARE arriving but below the presence threshold: a valid listening
        // state (neutral "NO SIGNAL"), never conflated with an RX stream anomaly.
        st.status = ui::Status::NoSignal;
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

    // ---- UI v3 M5: PARAMETERS page data + runtime state --------------------
    if (r.has_measurements) {
        st.meas.valid = true;
        st.meas.rms_counts = r.measurements.rms_counts;
        st.meas.peak_counts = r.measurements.peak_counts;
        st.meas.papr_db = r.measurements.papr_db;
        st.meas.clip_ratio = r.measurements.clip_ratio;
        st.meas.power_dbfs = r.measurements.power_dbfs;
        st.meas.noise_floor_dbfs = r.measurements.noise_floor_dbfs;
        st.meas.psd_peak_prominence_db = r.measurements.psd_peak_prominence_db;
        st.meas.snr_est_db = r.measurements.snr_est_db;
        st.meas.occupied_bins = r.measurements.occupied_bins;
        st.meas.spectral_centroid_hz = r.measurements.spectral_centroid_hz;
        st.meas.occupied_bw_hz = r.measurements.occupied_bw_hz;
        st.meas.model_rms = r.measurements.model_rms;
        // display spectrum (fix10class24-waterfall1)
        st.meas.spectrum_valid = r.measurements.spectrum_valid;
        for (int b = 0; b < 256; ++b)
            st.meas.spectrum_dbfs_x4[b] = r.measurements.spectrum_dbfs_x4[b];
        st.meas.spectrum_sample_rate_hz = r.measurements.spectrum_sample_rate_hz;
        st.meas.spectrum_center_hz = r.measurements.spectrum_center_hz;
    }
    st.presence = r.presence_state.empty() ? "--" : r.presence_state;
    st.level_mode = r.level_mode.empty() ? "--" : r.level_mode;
    st.model_scale = r.model_scale;
    st.rf_gain_db = r.rf_gain_db;

    // M6 work mode + run state: the producer is authoritative.  A wire token is
    // converted to the MODE-page display name; an empty/unknown token falls back
    // to FIXED (never a self-faked state).
    {
        mode_ctl::ModeKind mk = mode_ctl::ModeKind::Fixed;
        if (!r.work_mode.empty()) mode_ctl::mode_from_token(r.work_mode, mk);
        st.work_mode = mode_ctl::mode_display_name(mk);
    }
    st.running = (r.run_state != "STOPPED");

    return st;
}

// Map a validated RML23 23-class ResultFrame into the UI state (M29 Phase F5).
// Identical status/source/measurements/runtime rules to map_to_state; the only
// differences are the 23-class contract (classes_23), the model identity caption
// (rml23::kModelMode) and class_count == 23, which makes render_main switch to
// the paginated category table.  category_page starts at 0.
inline ui::UiState map_to_state_rml23(const rf::ResultFrame& r) {
    ui::UiState st = map_to_state(r);      // shared mapping, then override width/identity
    st.classes = &ui::classes_23();        // 23-class label order (was classes_12)
    st.model_mode = rml23::kModelMode;     // "RML23-AMSSB-MERGED"
    st.class_count = r.class_count;        // 23
    st.category_page = 0;
    return st;
}

inline ui::UiState map_to_state_rml24_final(const rf::ResultFrame& r) {
    ui::UiState st = map_to_state(r);
    st.classes = &ui::classes_24();
    st.model_mode = "RML24-BF16-RAW";
    st.class_count = 24;
    st.category_page = 0;
    // The final adapter currently supplies only the display spectrum, not the
    // legacy ADC measurement set. Keep spectrum valid while leaving unrelated
    // RMS/noise/PAPR cards as "--" instead of presenting default zeros as data.
    st.meas.valid = false;
    st.iq_display_valid = r.iq_display_valid && r.iq_i16_interleaved.size() == 512;
    st.iq_units_per_count = st.iq_display_valid ? r.iq_units_per_count : 0.0;
    if (st.iq_display_valid) {
        for (std::size_t i = 0; i < 512; ++i)
            st.iq_i16_interleaved[i] = r.iq_i16_interleaved[i];
    }
    return st;
}

// Apply a control state event (task 39e5 Task E, 方案 A) to the UI state WITHOUT
// touching the classification fields (top1 / conf / dist / frame).  The producer
// emits {"type":"state",...} on every work-mode / run-state change, so the screen
// shows STOPPED / RUNNING / a newly applied mode even though classification frames
// stop flowing while STOPPED.  `running` maps to run_state != STOPPED; an
// unknown work_mode token falls back to FIXED (never self-faked).
inline void apply_state_event(ui::UiState& st, const StateEvent& ev) {
    mode_ctl::ModeKind mk = mode_ctl::ModeKind::Fixed;
    if (!ev.work_mode.empty()) mode_ctl::mode_from_token(ev.work_mode, mk);
    st.work_mode = mode_ctl::mode_display_name(mk);
    st.running = (ev.run_state != "STOPPED");
    if (!ev.presence_state.empty()) {
        st.presence = ev.presence_state;
        // Heartbeat errata: RUNNING + NO_SIGNAL must display "NO SIGNAL" even when
        // the state heartbeat is the only record in the tick (e.g. while STOPPED,
        // when classification frames are not flowing).  A state event NEVER
        // fabricates a classification, so SIGNAL_PRESENT alone does NOT promote the
        // badge to Live -- Live only ever comes from a valid result frame.
        if (ev.presence_state == "NO_SIGNAL") st.status = ui::Status::NoSignal;
    }
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
