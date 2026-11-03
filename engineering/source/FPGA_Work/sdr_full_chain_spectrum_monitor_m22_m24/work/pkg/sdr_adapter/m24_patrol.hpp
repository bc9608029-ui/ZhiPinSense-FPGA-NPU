#pragma once

// m24_patrol.hpp -- M24-A automatic patrol / scan state machine (offline).
//
// Drives a frequency sweep through a MOCK adapter only (never a real RF device,
// never libiio/Pluto).  The state machine is fully synchronous: each step()
// call performs at most one transition, so STOP terminates in O(1) steps
// (bounded).  Dwell/settle are enforced against an injected monotonic clock,
// which keeps the machine deterministic and host-testable.

#include <cstddef>
#include <functional>
#include <string>
#include <vector>

namespace m24 {

enum class PatrolState {
    Idle, Tune, Settle, Detect, Lock, Estimate, Classify, Record, ResumeScan,
    Stopped, Error
};

inline const char* patrol_state_name(PatrolState s) {
    switch (s) {
        case PatrolState::Idle: return "IDLE";
        case PatrolState::Tune: return "TUNE";
        case PatrolState::Settle: return "SETTLE";
        case PatrolState::Detect: return "DETECT";
        case PatrolState::Lock: return "LOCK";
        case PatrolState::Estimate: return "ESTIMATE";
        case PatrolState::Classify: return "CLASSIFY";
        case PatrolState::Record: return "RECORD";
        case PatrolState::ResumeScan: return "RESUME_SCAN";
        case PatrolState::Stopped: return "STOPPED";
        case PatrolState::Error: return "ERROR";
    }
    return "?";
}

struct PatrolConfig {
    double start_freq_hz = 2400.0e6;
    double stop_freq_hz = 2480.0e6;
    double step_hz = 1.0e6;
    double settle_s = 0.001;
    double detect_timeout_s = 0.010;   // max time in DETECT without a signal
    double detect_threshold_dbm = -55.0;  // enter threshold
    double hysteresis_db = 7.0;           // exit = enter - hysteresis
    std::size_t max_findings = 4096;      // bounded findings buffer
};

// Measured/classified result returned by the mock adapter's measure().
struct PatrolParams {
    double power_dbfs = 0.0;
    double snr_db = 0.0;
    double bandwidth_hz = 0.0;
    double center_freq_hz = 0.0;
    int class_index = -1;
    std::string class_name;
};

// A finding emitted when the machine reaches RECORD.
struct PatrolFinding {
    double time_s = 0.0;
    double center_freq_hz = 0.0;
    double power_dbfs = 0.0;
    double snr_db = 0.0;
    double bandwidth_hz = 0.0;
    int class_index = -1;
    std::string class_name;
};

// Mock adapter: supply callbacks; unset callbacks behave as "no signal" / no-op.
struct PatrolAdapter {
    std::function<bool(double freq_hz)> tune;      // -> false = tune failure
    std::function<double()> read_power_dbm;        // channel power
    std::function<PatrolParams()> measure;         // estimate + classify
};

class PatrolStateMachine {
public:
    void configure(const PatrolConfig& cfg) {
        cfg_ = cfg;
        if (cfg_.step_hz <= 0.0) cfg_.step_hz = 1.0;
        if (cfg_.settle_s < 0.0) cfg_.settle_s = 0.0;
        if (cfg_.detect_timeout_s < 0.0) cfg_.detect_timeout_s = 0.0;
        if (cfg_.hysteresis_db < 0.0) cfg_.hysteresis_db = 0.0;
    }

    void start() {
        state_ = PatrolState::Tune;
        current_freq_hz_ = cfg_.start_freq_hz;
        stop_requested_ = false;
        findings_.clear();
        params_ = PatrolParams{};
    }

    // Request a stop.  STOP is reached within one subsequent step() call.
    void stop() { stop_requested_ = true; }

    PatrolState state() const { return state_; }
    bool stop_requested() const { return stop_requested_; }
    double current_freq_hz() const { return current_freq_hz_; }
    const std::vector<PatrolFinding>& findings() const { return findings_; }

    // Advance exactly one transition using the monotonic clock `now_s`.
    PatrolState step(double now_s, PatrolAdapter& a) {
        if (stop_requested_) {
            state_ = PatrolState::Stopped;
            return state_;
        }
        switch (state_) {
            case PatrolState::Idle:
                break;
            case PatrolState::Tune:
                if (!a.tune || !a.tune(current_freq_hz_)) {
                    state_ = PatrolState::Error;
                } else {
                    settle_enter_ = now_s;
                    state_ = PatrolState::Settle;
                }
                break;
            case PatrolState::Settle:
                if (now_s - settle_enter_ >= cfg_.settle_s) {
                    detect_enter_ = now_s;
                    state_ = PatrolState::Detect;
                }
                break;
            case PatrolState::Detect: {
                const double p = a.read_power_dbm ? a.read_power_dbm() : -300.0;
                if (p >= cfg_.detect_threshold_dbm) {
                    state_ = PatrolState::Lock;
                } else if (now_s - detect_enter_ >= cfg_.detect_timeout_s) {
                    state_ = PatrolState::ResumeScan;  // detect timeout: skip
                }
                break;
            }
            case PatrolState::Lock: {
                const double p = a.read_power_dbm ? a.read_power_dbm() : -300.0;
                if (p < cfg_.detect_threshold_dbm - cfg_.hysteresis_db) {
                    detect_enter_ = now_s;
                    state_ = PatrolState::Detect;  // signal lost -> hysteresis
                } else {
                    state_ = PatrolState::Estimate;  // confirmed -> estimate
                }
                break;
            }
            case PatrolState::Estimate:
                params_ = a.measure ? a.measure() : PatrolParams{};
                state_ = PatrolState::Classify;
                break;
            case PatrolState::Classify:
                state_ = PatrolState::Record;
                break;
            case PatrolState::Record: {
                PatrolFinding f;
                f.time_s = now_s;
                f.center_freq_hz = current_freq_hz_;
                f.power_dbfs = params_.power_dbfs;
                f.snr_db = params_.snr_db;
                f.bandwidth_hz = params_.bandwidth_hz;
                f.class_index = params_.class_index;
                f.class_name = params_.class_name;
                if (findings_.size() >= cfg_.max_findings)
                    findings_.erase(findings_.begin());  // bounded: drop oldest
                findings_.push_back(f);
                state_ = PatrolState::ResumeScan;
                break;
            }
            case PatrolState::ResumeScan:
                current_freq_hz_ += cfg_.step_hz;
                if (current_freq_hz_ > cfg_.stop_freq_hz) {
                    state_ = PatrolState::Stopped;  // scan complete
                } else {
                    state_ = PatrolState::Tune;
                }
                break;
            case PatrolState::Stopped:
            case PatrolState::Error:
                break;
        }
        return state_;
    }

private:
    PatrolConfig cfg_;
    PatrolState state_ = PatrolState::Idle;
    bool stop_requested_ = false;
    double current_freq_hz_ = 0.0;
    double settle_enter_ = 0.0;
    double detect_enter_ = 0.0;
    PatrolParams params_;
    std::vector<PatrolFinding> findings_;
};

}  // namespace m24
