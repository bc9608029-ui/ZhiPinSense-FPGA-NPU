#pragma once

// producer_12class.hpp -- the Gate 9 twelve-class LIVE PRODUCER (task 39e5 UI v3
// M6-M10 integration).  This is the single owner of the reverse control channel
// and of every piece of runtime behaviour the MODE/PARAMETERS pages display:
//
//   * work mode + run state  -- owned here, mutated only by the M6 control
//                               channel (mode_ctl::apply_command), reported on
//                               every frame (work_mode / run_state).  The UI
//                               server only DISPLAYS what this producer reports;
//                               it must never self-modify mode text to fake
//                               effectiveness.
//   * FrameMeasurements        -- a real sdr::DspMeasure per frame (the
//                               PARAMETERS page therefore shows real values, not
//                               placeholders).
//   * SignalPresence           -- non-SIGNAL_PRESENT never publishes a class.
//   * WorkModeEngine           -- FIXED (identity gain + fixed scale, publish raw
//                               argmax), AUTO LOCK (slow bounded auto level + a
//                               class-stability lock), BAND SCAN (same + an LO
//                               sweep).  The engine's model_scale is ACTUALLY
//                               applied to the model input before inference, and
//                               the engine's RF gain offset is ACTUALLY applied to
//                               the device (bounded + logged via the device).
//   * BandScanSequencer        -- BAND SCAN actually re-tunes the RX LO per
//                               start/stop/step/dwell, resets the class lock after
//                               every LO step, and reports the current LO + scan
//                               progress on each frame.
//
// Pure-logic, iCraft-free, libiio-free, header-only: the ONLY device effects are
// the two methods of the injectable DeviceControl interface (set_rx_lo / set_rx_gain),
// so the whole state machine is host-testable with a fake device + fake classifier
// (host_tests/test_producer_12class.cpp).  The board (board_gate9_full_chain_12class.cpp)
// supplies a DeviceControl backed by a real pluto::Device and a ClassifyFn backed by
// NpuClassifier12.
//
// Model input contract (frozen): [1,2,1024] fp32 planar I/Q.  The producer consumes
// the BASE tensor (receiver_scale already applied by chain::PreprocessChain) and
// derives the count-domain frame from it for measurement, then applies the engine's
// digital scalar ON TOP of that base before classifying.  It never touches the
// frozen receiver_scale path itself.

#include "band_scan.hpp"
#include "mode_control.hpp"
#include "work_mode_engine.hpp"

#include "../sdr_adapter/dsp_measure.hpp"
#include "../sdr_adapter/signal_presence.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace producer {

// Frozen model input shape (== chain::kFrameComplex / chain::kTensorFloats; the
// values are duplicated here so this header stays decoupled from chain_common.hpp).
constexpr std::size_t kFrameComplex = 1024;
constexpr std::size_t kTensorFloats = 2 * kFrameComplex;

// Stream-anomaly flags the caller lifts from a board::RxStats for one frame.
struct CaptureFlags {
    bool overflow = false;
    bool dropped = false;
    bool discontinuity = false;
    bool short_frame = false;
    bool capture_error() const { return overflow || dropped || discontinuity || short_frame; }
};

// The ONLY device effects the producer is allowed to perform.  The board backs
// this with pluto::Device; the host test backs it with a logging fake.
struct DeviceControl {
    virtual ~DeviceControl() = default;
    virtual void set_rx_lo(std::int64_t hz) = 0;   // tune the RX LO (band scan)
    virtual void set_rx_gain(double db) = 0;       // apply the managed RX gain
};

// Runs the NPU on the SCALED tensor (base * model_scale) and returns the raw
// logits.  The producer computes argmax / softmax from what this returns.
using ClassifyFn = std::function<void(const float* scaled_tensor, std::vector<float>& logits)>;

struct ProducerConfig {
    sdr::DspMeasureConfig dsp;      // receiver_scale must match the preprocess chain
    sdr::PresenceConfig presence;
    sdr::LevelConfig level;         // FIXED/AUTO tuning; the engine forces AUTO internally
    int stability_window = 5;       // AUTO LOCK / BAND SCAN class-lock window

    // RF gain = clamp(base_rf_gain_db + engine offset, min, max).  FIXED applies
    // exactly base_rf_gain_db (engine offset is 0); AUTO nudges inside the bounds.
    double base_rf_gain_db = 10.0;
    double rf_gain_min_db = 0.0;
    double rf_gain_max_db = 50.0;

    sdr::BandScanConfig band_scan;  // start/stop/step/dwell for BAND SCAN

    // FIXED / AUTO LOCK capture batch size (frames per contiguous RX refill).
    std::size_t batch_frames = 16;
};

// One frame's decision from the producer.
struct ProducerDecision {
    std::string work_mode;            // mode_ctl wire token ("FIXED"/...)
    std::string run_state;            // "RUNNING"/"STOPPED"

    bool has_measurements = false;
    sdr::FrameMeasurements measurements;
    std::string presence_state;       // presence_state_name(...)
    std::string level_mode;           // "FIXED"/"AUTO"
    double model_scale = 1.0;         // digital scalar ACTUALLY applied this frame
    double rf_gain_db = 0.0;          // RF gain ACTUALLY applied this frame (dB)

    bool publish = false;             // emit this frame's classification
    int published_class = -1;         // class to publish (>= 0 when publish)
    bool class_locked = false;
    int locked_class = -1;
    const char* reason = "";          // short log tag

    std::vector<float> logits;        // raw NPU logits (for the caller's ResultFrame)

    // BAND SCAN progress (only meaningful when work_mode == "BAND_SCAN").
    bool band_scan_active = false;
    std::int64_t scan_lo_hz = 0;      // LO for the NEXT step (post-advance)
    int scan_step_index = 0;
    int scan_total_steps = 0;
    int scan_frames_in_step = 0;
    int scan_dwell_frames = 0;
};

class Producer12 {
public:
    Producer12(const ProducerConfig& cfg, DeviceControl& dev)
        : cfg_(cfg), dev_(dev),
          mode_{mode_ctl::ModeKind::Fixed, mode_ctl::RunState::Running},
          dsp_(cfg.dsp), presence_(cfg.presence),
          engine_(mode_ctl::ModeKind::Fixed, cfg.level, cfg.stability_window),
          sweep_(cfg.band_scan), scan_results_(cfg.band_scan) {}

    // ---- control channel (the producer is authoritative) ---------------------
    // Applies one command line; on a successful SET_MODE it syncs the engine mode
    // and resets the band-scan sweep.  Returns the "OK ..."/"ERR ..." reply.
    std::string apply_command(const std::string& line) {
        const mode_ctl::ModeKind before = mode_.mode;
        const std::string resp = mode_ctl::apply_command(mode_, line);
        if (resp.rfind("OK", 0) == 0 && mode_.mode != before) {
            engine_.set_mode(mode_.mode);
            if (mode_.mode == mode_ctl::ModeKind::BandScan) {
                sweep_.reset();
                scan_results_.reset();
                band_scan_tuned_ = false;
            }
        }
        return resp;
    }

    const mode_ctl::ModeState& mode_state() const { return mode_; }
    bool running() const { return mode_.run == mode_ctl::RunState::Running; }
    bool band_scan_active() const { return mode_.mode == mode_ctl::ModeKind::BandScan; }

    // ---- capture scheduling ---------------------------------------------------
    // Re-tune the RX LO before a BAND SCAN batch when the sweep stepped.  A FIXED /
    // AUTO LOCK batch never re-tunes.
    void before_capture() {
        if (!band_scan_active() || !running()) return;
        const std::int64_t f = static_cast<std::int64_t>(sweep_.current_frequency_hz());
        if (!band_scan_tuned_ || last_tuned_hz_ != f) {
            dev_.set_rx_lo(f);
            last_tuned_hz_ = f;
            band_scan_tuned_ = true;
            ++lo_tune_count_;
        }
    }

    // Frames to capture in the next batch: one dwell's worth in BAND SCAN (so the
    // sweep completes within a batch and the next batch re-tunes), else batch_frames.
    std::size_t capture_batch_frames() const {
        if (band_scan_active() && running()) {
            const int remain = sweep_.dwell_frames() - sweep_.frames_in_step();
            return static_cast<std::size_t>(remain > 0 ? remain : sweep_.dwell_frames());
        }
        return cfg_.batch_frames;
    }

    // ---- per-frame processing -------------------------------------------------
    // `base` is the [2,1024] tensor with receiver_scale already applied.  The
    // producer derives the count-domain frame, measures it, updates presence, then
    // applies the CURRENT engine scalar to `base`, classifies the SCALED tensor,
    // and finally advances the engine / RF gain / band-scan state for the NEXT
    // frame.  result.model_scale / rf_gain_db are the values ACTUALLY applied to
    // THIS frame (one-frame-ahead state, which is the documented slow-EMA design).
    ProducerDecision on_frame(const float* base, const CaptureFlags& flags,
                              const ClassifyFn& classify) {
        ProducerDecision d;
        d.work_mode = mode_ctl::mode_token(mode_.mode);
        d.run_state = mode_ctl::run_display_name(mode_.run);

        if (!running() || base == nullptr) {
            d.reason = "stopped";
            return d;
        }

        const bool scan = band_scan_active();
        const double rec = (cfg_.dsp.receiver_scale > 0.0f) ? cfg_.dsp.receiver_scale : 1.0f;
        const float count_scale = static_cast<float>(cfg_.dsp.full_scale_counts / rec);

        // 1. Count-domain frame (receiver_scale inverse) -> real measurements.
        std::vector<std::complex<float>> cf(kFrameComplex);
        for (std::size_t k = 0; k < kFrameComplex; ++k) {
            cf[k] = std::complex<float>(base[k] * count_scale,
                                        base[kFrameComplex + k] * count_scale);
        }
        const sdr::FrameMeasurements m = dsp_.measure(cf.data(), kFrameComplex);
        d.has_measurements = true;
        d.measurements = m;

        // 2. Signal presence (non-present -> engine withholds publish).
        sdr::PresenceInput pi;
        pi.power_dbfs = m.power_dbfs;
        pi.noise_floor_dbfs = m.noise_floor_dbfs;
        pi.snr_est_db = m.snr_est_db;
        pi.psd_peak_prominence_db = m.psd_peak_prominence_db;
        pi.clip_ratio = m.clip_ratio;
        pi.occupied_bins = m.occupied_bins;
        pi.nan_inf = m.nan_inf;
        pi.capture_error = flags.capture_error();
        const sdr::PresenceState ps = presence_.update(pi);
        d.presence_state = sdr::presence_state_name(ps);
        const bool present = (ps == sdr::PresenceState::SignalPresent);

        // 3. Level stats (model RMS AFTER receiver_scale, BEFORE digital scalar).
        sdr::FrameLevelStats stats;
        stats.adc_rms_dbfs = m.power_dbfs;
        stats.clip_ratio = m.clip_ratio;
        stats.model_rms = m.model_rms;
        stats.valid = m.valid && !m.nan_inf && !flags.capture_error();

        // 4. Apply the CURRENT engine scalar to the model input, then classify.
        const float applied_scale = engine_.model_scale();
        std::vector<float> scaled(kTensorFloats);
        for (std::size_t k = 0; k < kTensorFloats; ++k)
            scaled[k] = base[k] * applied_scale;
        std::vector<float> logits;
        classify(scaled.data(), logits);
        const int argmax = argmax_index(logits);

        // 5. Advance the engine (scale + gain + publish policy) for the NEXT frame.
        const sdr::WorkModeDecision wd = engine_.update(stats, present, argmax);
        d.level_mode = (wd.level_mode == sdr::LevelMode::Fixed) ? "FIXED" : "AUTO";
        d.model_scale = applied_scale;   // what was ACTUALLY applied this frame
        d.publish = wd.publish;
        d.published_class = wd.published_class;
        d.class_locked = wd.class_locked;
        d.locked_class = wd.locked_class;
        d.reason = wd.reason;
        d.logits = std::move(logits);

        // 6. RF gain: base + engine offset, bounded, applied on change.
        const double desired = std::clamp(cfg_.base_rf_gain_db + engine_.rf_gain_db(),
                                          cfg_.rf_gain_min_db, cfg_.rf_gain_max_db);
        if (desired != last_rf_gain_db_) {
            dev_.set_rx_gain(desired);
            last_rf_gain_db_ = desired;
        }
        d.rf_gain_db = desired;

        // 7. BAND SCAN dwell / LO advance + per-step best detection.
        d.band_scan_active = scan;
        if (scan) {
            const bool done = sweep_.on_frame();
            const float pub_conf = (d.publish && d.published_class >= 0)
                                       ? softmax_at(d.logits, d.published_class) : 0.0f;
            scan_results_.record(sweep_.step_index(),
                                 d.publish ? d.published_class : -1, pub_conf);
            if (done) {
                engine_.reset_lock();   // new frequency = fresh class lock
                sweep_.advance_step();
                band_scan_tuned_ = false;   // before_capture() re-tunes next batch
                ++sweep_advances_;
            }
            d.scan_lo_hz = static_cast<std::int64_t>(sweep_.current_frequency_hz());
            d.scan_step_index = sweep_.step_index();
            d.scan_total_steps = sweep_.total_steps();
            d.scan_frames_in_step = sweep_.frames_in_step();
            d.scan_dwell_frames = sweep_.dwell_frames();
        }

        return d;
    }

    // ---- diagnostics ---------------------------------------------------------
    float model_scale() const { return engine_.model_scale(); }
    double rf_gain_db() const { return last_rf_gain_db_; }
    std::uint64_t lo_tune_count() const { return lo_tune_count_; }
    std::uint64_t sweep_advances() const { return sweep_advances_; }
    const sdr::BandScanAccumulator& scan_results() const { return scan_results_; }

private:
    static int argmax_index(const std::vector<float>& v) {
        if (v.empty()) return -1;
        int best = 0;
        for (std::size_t i = 1; i < v.size(); ++i)
            if (v[i] > v[best]) best = static_cast<int>(i);
        return best;
    }

    static float softmax_at(const std::vector<float>& logits, int idx) {
        if (idx < 0 || idx >= static_cast<int>(logits.size())) return 0.0f;
        const float mx = *std::max_element(logits.begin(), logits.end());
        double sum = 0.0;
        for (float x : logits) sum += std::exp(static_cast<double>(x) - static_cast<double>(mx));
        return static_cast<float>(
            std::exp(static_cast<double>(logits[static_cast<std::size_t>(idx)]) -
                     static_cast<double>(mx)) / sum);
    }

    ProducerConfig cfg_;
    DeviceControl& dev_;
    mode_ctl::ModeState mode_;

    sdr::DspMeasure dsp_;
    sdr::SignalPresence presence_;
    sdr::WorkModeEngine engine_;
    sdr::BandScanSequencer sweep_;
    sdr::BandScanAccumulator scan_results_;

    double last_rf_gain_db_ = -1e9;   // sentinel: apply the first frame's gain
    bool band_scan_tuned_ = false;
    std::int64_t last_tuned_hz_ = 0;
    std::uint64_t lo_tune_count_ = 0;
    std::uint64_t sweep_advances_ = 0;
};

}  // namespace producer
