#pragma once

// band_scan.hpp -- BAND SCAN work-mode LO-sweep sequencer + per-step result
// accumulator (task 39e5 UI v3 M10).
//
// Pure-logic, iCraft-free, header-only (host-testable).  The sequencer is a
// deterministic state machine that schedules the LO frequency sweep; the
// accumulator collects, for each frequency step, the best detection (class +
// confidence).  Neither touches the device: the board producer composes them
// with a WorkModeEngine + the Pluto device like this (see BAND_SCAN_CONTRACT.md):
//
//   BandScanSequencer sweep(cfg);
//   BandScanAccumulator results(cfg);
//   tune_lo(sweep.current_frequency_hz());          // tune BEFORE the step's frames
//   for each captured frame {
//       bool done = sweep.on_frame();                 // frame ticks the dwell
//       auto d = engine.update(stats, present, argmax);  // AUTO LOCK policy (M8)
//       results.record(sweep.step_index(), d.published_class, confidence);
//       if (done) {                                   // dwell complete -> next LO
//           engine.reset_lock();                      // new freq = fresh class lock
//           sweep.advance_step();                     // wrap past stop back to start
//           tune_lo(sweep.current_frequency_hz());
//       }
//   }
//
// Sweep schedule: LO steps over start, start+step, ..., last <= stop (inclusive),
// then wraps back to start.  total_steps = floor((stop-start)/step) + 1.  The scan
// is continuous (wrap-around), never "done" -- the producer stops it externally
// (M6 STOP / exit).

#include <cstdint>
#include <stdexcept>
#include <vector>

namespace sdr {

struct BandScanConfig {
    std::uint64_t start_hz = 2400000000ULL;   // first LO
    std::uint64_t stop_hz  = 2500000000ULL;   // last LO (>= start, inclusive)
    std::uint64_t step_hz  = 10000000ULL;     // step between LOs (> 0)
    int dwell_frames = 32;                    // frames to dwell per step (> 0)
};

// One completed LO dwell's best detection.
struct BandScanBin {
    std::uint64_t frequency_hz = 0;
    int step_index = 0;
    int frames = 0;               // frames recorded for this step
    bool has_detection = false;   // a valid class was recorded
    int best_class = -1;          // highest-confidence class (-1 = none)
    float best_confidence = 0.0f; // confidence of best_class
};

// ---------------------------------------------------------------------------
// BandScanSequencer -- the LO sweep schedule.
// ---------------------------------------------------------------------------
class BandScanSequencer {
public:
    explicit BandScanSequencer(const BandScanConfig& cfg) : cfg_(cfg) {
        validate();
        total_steps_ = static_cast<int>((cfg_.stop_hz - cfg_.start_hz) / cfg_.step_hz) + 1;
        reset();
    }

    // Number of LO steps in one full sweep (start..last<=stop, inclusive).
    int total_steps() const { return total_steps_; }

    // Current step index [0, total_steps) and its LO frequency.
    int step_index() const { return step_index_; }
    std::uint64_t current_frequency_hz() const { return current_hz_; }

    // Dwell progress within the current step.
    int frames_in_step() const { return frames_in_step_; }
    int dwell_frames() const { return cfg_.dwell_frames; }

    std::uint64_t start_hz() const { return cfg_.start_hz; }
    std::uint64_t stop_hz() const { return cfg_.stop_hz; }
    std::uint64_t step_hz() const { return cfg_.step_hz; }

    // Advance ONE frame.  Returns true exactly when the current step's dwell just
    // completed (this is the last frame of the step); the caller then finalizes
    // the bin, resets the class lock, calls advance_step(), and re-tunes the LO.
    bool on_frame() {
        ++frames_in_step_;
        return frames_in_step_ >= cfg_.dwell_frames;
    }

    // Move to the next step (wraps past the last step back to step 0) and restart
    // the dwell counter.  Call only after on_frame() returned true.
    void advance_step() {
        step_index_ = (step_index_ + 1) % total_steps_;
        frames_in_step_ = 0;
        current_hz_ = frequency_for(step_index_);
    }

    // Back to the first step with a fresh dwell.
    void reset() {
        step_index_ = 0;
        frames_in_step_ = 0;
        current_hz_ = frequency_for(0);
    }

private:
    static std::uint64_t checked_sub(std::uint64_t a, std::uint64_t b) {
        if (a < b) throw std::invalid_argument("band_scan: stop_hz >= start_hz");
        return a - b;
    }

    void validate() const {
        checked_sub(cfg_.stop_hz, cfg_.start_hz);
        if (cfg_.step_hz == 0)
            throw std::invalid_argument("band_scan: step_hz > 0");
        if (cfg_.dwell_frames <= 0)
            throw std::invalid_argument("band_scan: dwell_frames > 0");
    }

    std::uint64_t frequency_for(int step) const {
        const std::uint64_t f = cfg_.start_hz + static_cast<std::uint64_t>(step) * cfg_.step_hz;
        return f <= cfg_.stop_hz ? f : cfg_.stop_hz;
    }

    BandScanConfig cfg_;
    int total_steps_ = 1;
    int step_index_ = 0;
    int frames_in_step_ = 0;
    std::uint64_t current_hz_ = 0;
};

// ---------------------------------------------------------------------------
// BandScanAccumulator -- per-step best detection.
// ---------------------------------------------------------------------------
class BandScanAccumulator {
public:
    explicit BandScanAccumulator(const BandScanConfig& cfg) {
        BandScanSequencer s(cfg);   // validates + gives total_steps
        bins_.resize(static_cast<std::size_t>(s.total_steps()));
        for (int i = 0; i < s.total_steps(); ++i) {
            bins_[static_cast<std::size_t>(i)].step_index = i;
            bins_[static_cast<std::size_t>(i)].frequency_hz =
                s.start_hz() + static_cast<std::uint64_t>(i) * s.step_hz();
        }
    }

    std::size_t size() const { return bins_.size(); }

    const BandScanBin& bin(int step_index) const {
        if (step_index < 0 || step_index >= static_cast<int>(bins_.size()))
            throw std::out_of_range("band_scan: step_index out of range");
        return bins_[static_cast<std::size_t>(step_index)];
    }

    // Record one frame's detection for a step.  A valid class (cls >= 0) with
    // higher confidence than the step's current best replaces it.
    void record(int step_index, int cls, float confidence) {
        if (step_index < 0 || step_index >= static_cast<int>(bins_.size()))
            throw std::out_of_range("band_scan: step_index out of range");
        BandScanBin& b = bins_[static_cast<std::size_t>(step_index)];
        ++b.frames;
        if (cls >= 0) {
            if (!b.has_detection || confidence > b.best_confidence) {
                b.has_detection = true;
                b.best_class = cls;
                b.best_confidence = confidence;
            }
        }
    }

    void reset() {
        for (BandScanBin& b : bins_) {
            b.frames = 0;
            b.has_detection = false;
            b.best_class = -1;
            b.best_confidence = 0.0f;
        }
    }

private:
    std::vector<BandScanBin> bins_;
};

}  // namespace sdr
