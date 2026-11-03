#pragma once

// m24_ui_scheduler.hpp -- M24-A display refresh scheduler (offline model).
//
// Classification and control always take priority over the spectrum display:
// control events bypass the rate limiter entirely.  The spectrum display is
// rate-limited to a configurable 10..20 Hz; between two renders only the LATEST
// spectrum frame is kept and intermediate frames are coalesced (never queued),
// so there is no backlog of old frames.  When disabled (default) behaviour is
// unchanged: every submitted spectrum frame renders immediately (no coalescing).
//
// This module emits OFFLINE render decisions (frame ids + stats) only; it does
// NOT write a framebuffer and does NOT drive the real UI.

#include <cstddef>
#include <cstdint>

namespace m24 {

class UiRefreshScheduler {
public:
    struct Stats {
        std::uint64_t spectrum_submitted = 0;
        std::uint64_t spectrum_rendered = 0;
        std::uint64_t spectrum_coalesced = 0;  // intermediate frames dropped
        std::uint64_t control_processed = 0;   // never dropped / rate-limited
        double last_render_s = 0.0;
    };

    UiRefreshScheduler() = default;

    // Configure the spectrum refresh rate in Hz.  Values outside [10, 20] are
    // clamped; rate <= 0 disables the limiter (default, behaviour unchanged).
    void configure(double rate_hz) {
        rate_hz_ = rate_hz;
        if (rate_hz_ <= 0.0) {
            enabled_ = false;
            return;
        }
        if (rate_hz_ < 10.0) rate_hz_ = 10.0;
        if (rate_hz_ > 20.0) rate_hz_ = 20.0;
        enabled_ = true;
    }

    bool enabled() const { return enabled_; }
    double rate_hz() const { return enabled_ ? rate_hz_ : 0.0; }

    // Submit a spectrum frame (id is a monotonically increasing frame number).
    // Only the latest pending frame is kept; a newer frame replaces an older
    // still-pending one, counting the older as coalesced.
    void submit_spectrum(std::uint64_t frame_id) {
        ++stats_.spectrum_submitted;
        if (!enabled_) {
            // Disabled: render immediately (behaviour unchanged).
            pending_id_ = frame_id;
            render_now_ = true;
            return;
        }
        if (has_pending_) {
            ++stats_.spectrum_coalesced;  // drop the older pending frame
        }
        pending_id_ = frame_id;
        has_pending_ = true;
        render_now_ = false;
    }

    // Submit a control/classification event (always processed immediately;
    // never rate-limited, never coalesced).  Higher priority than display.
    void submit_control(std::uint64_t event_id) {
        (void)event_id;
        ++stats_.control_processed;
    }

    // Tick the scheduler with the current monotonic time (seconds).  Returns
    // true iff the display should render the pending spectrum frame now, and
    // consumes that pending frame.
    bool tick(double now_s) {
        if (!enabled_) {
            if (render_now_) {
                render_now_ = false;
                has_pending_ = false;
                ++stats_.spectrum_rendered;
                stats_.last_render_s = now_s;
                return true;
            }
            return false;
        }
        if (!has_pending_) return false;
        const double period = 1.0 / rate_hz_;
        if (now_s - last_render_s_ < period) return false;  // rate-limited
        has_pending_ = false;
        ++stats_.spectrum_rendered;
        last_render_s_ = now_s;
        stats_.last_render_s = now_s;
        return true;
    }

    const Stats& stats() const { return stats_; }

private:
    double rate_hz_ = 0.0;
    bool enabled_ = false;
    bool has_pending_ = false;
    bool render_now_ = false;
    std::uint64_t pending_id_ = 0;
    double last_render_s_ = -1.0e9;  // allow immediate first render
    Stats stats_;
};

}  // namespace m24
