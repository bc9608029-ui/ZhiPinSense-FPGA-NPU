#pragma once

// ui_dirty_state.hpp -- M17 event-driven flip scheduler (Task E / Task G).
//
// The live UI server re-rendered and re-flipped the framebuffer on EVERY display
// tick, even when nothing had changed.  On the board this showed up two ways:
//   * ~32% idle CPU with received=0/valid=0/rendered=0 (the waiting frame was
//     copied + msync'd + flipped every 33 ms for nothing), and
//   * repeated flicker on a steady feed (a constant signal still re-flipped the
//     ping-pong select every tick, and there is no vblank ack register to make an
//     unnecessary flip tear-free).
//
// M17 makes the flip event-driven:
//   * display_changed() tells whether two UiStates differ in ANY field the
//     renderer actually draws (exact comparison, so a feed that repeats the same
//     frame returns false and no flip happens);
//   * FlipScheduler::should_submit() flips only when (a) the content changed since
//     the last submit -- or nothing was submitted yet -- AND (b) at least
//     min_interval_ms has elapsed since the last submit, so the flip is paced to at
//     least one display frame period even if the tick loop were mis-tuned.
//
// Pure logic, iCraft-free and libiio-free: host-tested in
// host_tests/test_ui_scheduler.cpp.  The socket loop stays in
// board_ui_live_12class.cpp.

#include "../ui_sw/ui_render.hpp"   // ui::UiState

#include <cstdint>
#include <cstddef>
#include <vector>

namespace ui {

// True when `a` and `b` differ in any field the renderer draws.  Comparison is
// exact (floats/doubles compared bit-exact), so an identical frame returns false.
// The `classes` pointer is intentionally skipped: it is a process-lifetime static
// and never differs between two states from the same server.
inline bool display_changed(const ui::UiState& a, const ui::UiState& b) {
    if (a.status != b.status) return true;
    if (a.source != b.source) return true;
    if (a.conf != b.conf) return true;
    if (a.top1 != b.top1) return true;
    if (a.snr != b.snr) return true;
    if (a.lat != b.lat) return true;
    if (a.frame != b.frame) return true;
    if (a.model != b.model) return true;
    if (a.age != b.age) return true;
    if (a.presence != b.presence) return true;
    if (a.level_mode != b.level_mode) return true;
    if (a.model_scale != b.model_scale) return true;
    if (a.rf_gain_db != b.rf_gain_db) return true;
    if (a.work_mode != b.work_mode) return true;
    if (a.running != b.running) return true;
    if (a.requested_mode != b.requested_mode) return true;
    if (a.requested_running != b.requested_running) return true;
    if (a.ctl_connected != b.ctl_connected) return true;
    if (a.last_command != b.last_command) return true;
    if (a.command_status != b.command_status) return true;
    if (a.control_taps != b.control_taps) return true;

    if (a.touch.device != b.touch.device) return true;
    if (a.touch.vendor != b.touch.vendor) return true;
    if (a.touch.axis_x != b.touch.axis_x) return true;
    if (a.touch.axis_y != b.touch.axis_y) return true;
    if (a.touch.mapping_x != b.touch.mapping_x) return true;
    if (a.touch.mapping_y != b.touch.mapping_y) return true;
    if (a.touch.connected != b.touch.connected) return true;
    if (a.touch.taps != b.touch.taps) return true;
    if (a.touch.last_x != b.touch.last_x) return true;
    if (a.touch.last_y != b.touch.last_y) return true;

    if (a.meas.valid != b.meas.valid) return true;
    if (a.meas.rms_counts != b.meas.rms_counts) return true;
    if (a.meas.peak_counts != b.meas.peak_counts) return true;
    if (a.meas.papr_db != b.meas.papr_db) return true;
    if (a.meas.clip_ratio != b.meas.clip_ratio) return true;
    if (a.meas.power_dbfs != b.meas.power_dbfs) return true;
    if (a.meas.noise_floor_dbfs != b.meas.noise_floor_dbfs) return true;
    if (a.meas.psd_peak_prominence_db != b.meas.psd_peak_prominence_db) return true;
    if (a.meas.snr_est_db != b.meas.snr_est_db) return true;
    if (a.meas.occupied_bins != b.meas.occupied_bins) return true;
    if (a.meas.spectral_centroid_hz != b.meas.spectral_centroid_hz) return true;
    if (a.meas.occupied_bw_hz != b.meas.occupied_bw_hz) return true;
    if (a.meas.model_rms != b.meas.model_rms) return true;

    if (a.dist.size() != b.dist.size()) return true;
    for (std::size_t i = 0; i < a.dist.size(); ++i)
        if (a.dist[i] != b.dist[i]) return true;

    return false;
}

// Event-driven flip scheduler: decides whether a submit is due this tick.
class FlipScheduler {
public:
    explicit FlipScheduler(std::int64_t min_interval_ms = 0)
        : min_interval_ms_(min_interval_ms) {}

    // True when a submit is due: the content changed since the last submit (or
    // nothing was ever submitted) AND at least min_interval_ms has elapsed since
    // the last submit.  A skipped decision increments `skips` (used by the
    // UI_RUNTIME_STATS line to prove the idle path is not re-flipping).
    bool should_submit(const ui::UiState& state, int page, std::int64_t now_ms) {
        const bool changed =
            !have_submitted_ || page != last_page_ || display_changed(last_state_, state);
        if (!changed) { ++skips; return false; }
        if (now_ms - last_submit_ms_ < min_interval_ms_) { ++skips; return false; }
        return true;
    }

    // Record a completed submit (call only after submit_frame() returned true).
    // Snaps the state + page so the next decision compares against what is on screen.
    void mark_submitted(const ui::UiState& state, int page, std::int64_t now_ms) {
        last_state_ = state;
        last_page_ = page;
        last_submit_ms_ = now_ms;
        have_submitted_ = true;
        ++submits;
    }

    std::uint64_t submits = 0;   // physical submit_frame() flips
    std::uint64_t skips = 0;     // ticks where no flip happened (idle / unchanged)

private:
    bool have_submitted_ = false;
    ui::UiState last_state_;
    int last_page_ = 0;
    std::int64_t last_submit_ms_ = 0;
    std::int64_t min_interval_ms_ = 0;
};

}  // namespace ui
