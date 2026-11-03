#pragma once

// auto_level_control.hpp -- automatic amplitude management (39e5 UI v3 M2).
//
// Two layers, both PURE DECISION LOGIC (iCraft-free, header-only; the device
// layer applies the outputs):
//
//   RF/ADC layer  -- keeps the analog front-end healthy: reduce gain on clip,
//                    nudge toward a target ADC RMS with hysteresis so the ADC
//                    neither clips nor sits in the noise floor.  Output is a
//                    bounded per-step gain delta (dB); the caller applies it via
//                    Pluto `hardwaregain` and reports the result back.
//   model input   -- a slow, bounded digital scalar applied ON TOP of the frozen
//   layer           receiver_scale (see receiver_scale.hpp).  In FIXED mode it is
//                    exactly `fixed_model_scale` (default 1.0 -> identity, the
//                    frozen path is untouched).  In AUTO mode it tracks the
//                    training-domain RMS (1.0) via a slow EMA, bounded by
//                    [min,max] and a per-update step cap.
//
// CRITICAL red line: AUTO mode is a SLOW (every N frames), BOUNDED, SMOOTHED
// global scalar.  It is explicitly NOT per-frame RMS normalization (which the
// sampling/IQ contract forbids).  It never adapts on an invalid frame (NaN/Inf/
// capture error) and can be held (e.g. by the signal-presence state) so it never
// chases noise.  See docs/AUTO_LEVEL_CONTROL_CONTRACT.md and
// docs/AUTO_LEVEL_MODEL_INPUT_AUDIT.md.

#include <algorithm>
#include <cstdint>

namespace sdr {

enum class LevelMode { Fixed = 0, Auto = 1 };

// Per-frame measurements the caller gathers (device/ADC domain + model domain).
struct FrameLevelStats {
    double adc_rms_dbfs = -120.0;   // ADC RMS in dBFS (count domain)
    double clip_ratio = 0.0;        // fraction of ADC samples clipped
    double model_rms = 0.0;         // model-domain RMS AFTER receiver_scale,
                                    // BEFORE this module's digital scalar
    bool valid = true;              // false on NaN/Inf/capture error
};

struct LevelConfig {
    LevelMode mode = LevelMode::Fixed;

    // --- model input (digital) layer ---
    float fixed_model_scale = 1.0f;  // FIXED mode: exact multiplier (identity by default)
    double target_model_rms = 1.0;   // AUTO: training-domain RMS target
    float model_scale_min = 0.25f;   // AUTO: bounds (avoid chasing silence/overdriving)
    float model_scale_max = 4.0f;
    float model_step_max = 0.05f;    // AUTO: max per-update relative change
    int frames_per_update = 8;       // AUTO: adaptation cadence (slow)

    // --- RF/ADC layer ---
    double rf_target_dbfs = -12.0;   // AUTO: ADC RMS target dBFS
    double rf_hysteresis_db = 3.0;   // dead zone around target
    double rf_gain_min_db = 0.0;
    double rf_gain_max_db = 50.0;
    double rf_gain_step_db = 3.0;    // max per-update gain change
    double max_clip_ratio = 0.01;    // clip above this forces immediate gain reduction
};

class AutoLevelControl {
public:
    explicit AutoLevelControl(const LevelConfig& c = {})
        : cfg_(c),
          model_scale_(c.mode == LevelMode::Fixed ? c.fixed_model_scale : 1.0f) {}

    LevelMode mode() const { return cfg_.mode; }
    float model_scale() const { return model_scale_; }
    double rf_gain_db() const { return rf_gain_db_; }
    std::uint64_t frames() const { return frames_; }
    std::uint64_t updates() const { return updates_; }

    // Consume one frame.  `adapt` can be gated by an external condition (e.g.
    // signal presence) so the loop freezes instead of chasing noise.
    // Returns the RF gain delta (dB) the caller should apply this step:
    //   0.0 in FIXED mode, inside the dead zone, or when frozen.
    double update(const FrameLevelStats& s, bool adapt = true) {
        ++frames_;
        if (!s.valid) return 0.0;          // invalid frame: freeze, never adapt

        if (cfg_.mode == LevelMode::Fixed) {
            model_scale_ = cfg_.fixed_model_scale;   // exact frozen path
            return 0.0;                              // no RF adaptation in FIXED
        }

        if (!adapt) return 0.0;             // held: freeze both layers

        // model input layer: slow bounded digital scalar.
        if (frames_ % static_cast<std::uint64_t>(cfg_.frames_per_update) == 0 &&
            s.model_rms > 0.0) {
            if (model_rms_ema_ <= 0.0)
                model_rms_ema_ = s.model_rms;        // seed EMA on first good frame
            else
                model_rms_ema_ = 0.9 * model_rms_ema_ + 0.1 * s.model_rms;
            const double desired = cfg_.target_model_rms / model_rms_ema_;
            const double ratio = desired / static_cast<double>(model_scale_);
            const double clamped = std::clamp(ratio, 1.0 - cfg_.model_step_max,
                                              1.0 + cfg_.model_step_max);
            model_scale_ = std::clamp(
                static_cast<float>(model_scale_ * clamped),
                cfg_.model_scale_min, cfg_.model_scale_max);
            ++updates_;
        }

        // RF/ADC layer: keep ADC healthy.
        double delta = 0.0;
        if (s.clip_ratio > cfg_.max_clip_ratio) {
            delta = -cfg_.rf_gain_step_db;               // clip: reduce gain now
        } else if (s.adc_rms_dbfs > cfg_.rf_target_dbfs + cfg_.rf_hysteresis_db) {
            delta = -cfg_.rf_gain_step_db;               // too hot
        } else if (s.adc_rms_dbfs < cfg_.rf_target_dbfs - cfg_.rf_hysteresis_db) {
            delta = +cfg_.rf_gain_step_db;               // too quiet
        }
        // Bound the resulting gain; apply only the part that keeps it in range.
        const double next = std::clamp(rf_gain_db_ + delta,
                                       cfg_.rf_gain_min_db, cfg_.rf_gain_max_db);
        delta = next - rf_gain_db_;
        rf_gain_db_ = next;
        return delta;
    }

    // Device layer reports the actually-applied analog gain after update().
    void set_rf_gain_db(double g) { rf_gain_db_ = g; }

    void reset() {
        model_scale_ = (cfg_.mode == LevelMode::Fixed) ? cfg_.fixed_model_scale : 1.0f;
        rf_gain_db_ = 0.0;
        model_rms_ema_ = 0.0;
        frames_ = 0;
        updates_ = 0;
    }

private:
    LevelConfig cfg_;
    float model_scale_ = 1.0f;
    double rf_gain_db_ = 0.0;
    double model_rms_ema_ = 0.0;
    std::uint64_t frames_ = 0;
    std::uint64_t updates_ = 0;
};

}  // namespace sdr
