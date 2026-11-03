#pragma once

// signal_presence.hpp -- signal presence / absence state machine (pure logic).
//
// Decides NO_SIGNAL / ACQUIRING / SIGNAL_PRESENT / SIGNAL_LOST / INVALID from a
// per-frame measurement vector.  Joint evidence: energy (power_dbfs vs a
// hysteretic threshold), estimated SNR (power - noise floor when available),
// PSD peak prominence, occupied-bin count, plus clip/NaN/Inf/capture-error
// guards that force INVALID.  Enter/exit use BOTH a threshold gap (enter vs exit
// power) AND a frame-count hysteresis (N consecutive hints to confirm, M
// consecutive losses to declare SIGNAL_LOST) so a marginal signal cannot flicker
// the state.
//
// iCraft-free and header-only (mirrors npu_rearm_state.hpp / delay_gate.hpp);
// unit-tested offline.  Thresholds are CALIBRATABLE config, not hardcoded law:
// defaults are a starting point to be confirmed against offline noise and board
// no-load captures (see docs/SIGNAL_PRESENCE_CONTRACT.md).

#include <cmath>
#include <cstddef>

namespace sdr {

enum class PresenceState {
    NoSignal = 0,
    Acquiring = 1,
    SignalPresent = 2,
    SignalLost = 3,
    Invalid = 4,
};

inline const char* presence_state_name(PresenceState s) {
    switch (s) {
        case PresenceState::NoSignal: return "NO_SIGNAL";
        case PresenceState::Acquiring: return "ACQUIRING";
        case PresenceState::SignalPresent: return "SIGNAL_PRESENT";
        case PresenceState::SignalLost: return "SIGNAL_LOST";
        case PresenceState::Invalid: return "INVALID";
    }
    return "UNKNOWN";
}

struct PresenceConfig {
    // Hysteretic energy thresholds (absolute dBFS).  Entering uses the higher
    // enter threshold; once present, the lower exit threshold applies.
    double enter_power_dbfs = -55.0;
    double exit_power_dbfs = -62.0;

    // Corroborating criteria.  A value of 0 disables that criterion; a positive
    // value requires the evidence to meet it when the evidence is available.
    // snr evidence is taken from snr_est_db, else derived from
    // power_dbfs - noise_floor_dbfs (gain-invariant) when a floor is known.
    double min_snr_db = 0.0;
    double min_peak_prominence_db = 0.0;
    int min_occupied_bins = 0;

    // clip_ratio above this forces INVALID (sustained clipping is a capture fault).
    double max_clip_ratio = 0.05;

    // Frame-count hysteresis: N consecutive hints to reach SIGNAL_PRESENT, M
    // consecutive losses to fall to SIGNAL_LOST.
    int confirm_frames = 3;
    int lost_frames = 5;
};

struct PresenceInput {
    double power_dbfs = -120.0;
    double noise_floor_dbfs = -120.0;    // NaN when unknown
    double snr_est_db = NAN;             // NaN when unknown
    double psd_peak_prominence_db = NAN; // NaN when unknown
    double clip_ratio = 0.0;
    int occupied_bins = 0;
    bool nan_inf = false;                // any NaN/Inf in the raw measurements
    bool capture_error = false;          // overflow/drop/discontinuity/short_frame
};

class SignalPresence {
public:
    explicit SignalPresence(const PresenceConfig& c = {}) : cfg_(c) {}

    PresenceState state() const { return state_; }
    int confirm_count() const { return confirm_; }
    int lost_count() const { return lost_; }

    // Pure per-frame signal hint (no state mutation).  `present` selects the
    // exit threshold for hysteresis so a confirmed signal is not dropped by a
    // single boundary-crossing sample.
    bool signal_hint(const PresenceInput& in, bool present) const {
        if (in.nan_inf || in.capture_error) return false;
        const double thr = present ? cfg_.exit_power_dbfs : cfg_.enter_power_dbfs;
        if (!(in.power_dbfs >= thr)) return false;

        if (cfg_.min_snr_db > 0.0) {
            double snr = in.snr_est_db;
            if (std::isnan(snr) && !std::isnan(in.noise_floor_dbfs))
                snr = in.power_dbfs - in.noise_floor_dbfs;
            if (!std::isnan(snr) && snr < cfg_.min_snr_db) return false;
        }
        if (cfg_.min_peak_prominence_db > 0.0) {
            if (!std::isnan(in.psd_peak_prominence_db) &&
                in.psd_peak_prominence_db < cfg_.min_peak_prominence_db)
                return false;
        }
        if (cfg_.min_occupied_bins > 0 &&
            in.occupied_bins < cfg_.min_occupied_bins)
            return false;
        return true;
    }

    PresenceState update(const PresenceInput& in) {
        // Hard faults force INVALID and reset all counters.
        if (in.nan_inf || in.capture_error || in.clip_ratio > cfg_.max_clip_ratio) {
            state_ = PresenceState::Invalid;
            confirm_ = 0;
            lost_ = 0;
            return state_;
        }

        const bool present_now = (state_ == PresenceState::SignalPresent);
        const bool hint = signal_hint(in, present_now);

        if (hint) {
            lost_ = 0;
            switch (state_) {
                case PresenceState::SignalPresent:
                    confirm_ = cfg_.confirm_frames;  // hold at present
                    break;
                case PresenceState::Acquiring:
                case PresenceState::SignalLost:
                case PresenceState::NoSignal:
                case PresenceState::Invalid:
                    ++confirm_;
                    if (confirm_ >= cfg_.confirm_frames)
                        state_ = PresenceState::SignalPresent;
                    else
                        state_ = PresenceState::Acquiring;
                    break;
            }
        } else {
            confirm_ = 0;
            switch (state_) {
                case PresenceState::SignalPresent:
                    ++lost_;
                    if (lost_ >= cfg_.lost_frames)
                        state_ = PresenceState::SignalLost;
                    break;
                case PresenceState::Acquiring:
                    // Never confirmed; a single dropout reverts to no-signal.
                    lost_ = 0;
                    state_ = PresenceState::NoSignal;
                    break;
                case PresenceState::SignalLost:
                case PresenceState::NoSignal:
                case PresenceState::Invalid:
                    break;  // stay
            }
        }
        return state_;
    }

    void reset() {
        state_ = PresenceState::NoSignal;
        confirm_ = 0;
        lost_ = 0;
    }

private:
    PresenceConfig cfg_;
    PresenceState state_ = PresenceState::NoSignal;
    int confirm_ = 0;
    int lost_ = 0;
};

}  // namespace sdr
