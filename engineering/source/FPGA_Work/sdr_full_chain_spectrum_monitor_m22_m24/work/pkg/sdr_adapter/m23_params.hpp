#pragma once

// m23_params.hpp -- M23 P0 parameter estimation (H) + valid/stale rendering.
//
// Estimates five per-frame quantities from count-domain complex<float> IQ:
//   center_freq_hz  PSD power-weighted spectral centroid (wideband) --
//                   reuses sdr::DspMeasure::spectral_centroid_hz.
//   power_dbfs      20*log10(rms / full_scale)                 (reuses DspMeasure)
//   rms             count-domain RMS                            (reuses DspMeasure)
//   snr_db          (signal above floor) / (flat noise floor)   (reuses DspMeasure)
//   occupied_bw_hz  span of bins above noise floor + threshold  (reuses DspMeasure)
//   cfo_hz          fine CFO vs a reference carrier             (m23_cfo.hpp)
//
// Every estimate carries a `valid` flag (false when the quantity is not
// computable -- empty input, NaN/Inf, no spectrum, or no CFO reference) and the
// caller additionally tracks STALENESS (a valid-but-too-old estimate) via
// M23ParamState.  The renderer turns invalid or stale into the literal "--".
//
// Allocation-reuse: estimate_params() takes a sdr::MeasureScratch (the FFT /
// power / sorted temporaries) and a m23::CfoScratch (the nonlinearity buffer),
// so a long-running producer reuses them across frames and allocates nothing
// per frame after the first.
//
// iCraft-free, header-only.

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <string>

#include "dsp_measure.hpp"
#include "m23_cfo.hpp"
#include "m23_contract.hpp"

namespace m23 {

struct ParamEstimate {
    double value = 0.0;
    bool valid = false;
};

struct M23Params {
    ParamEstimate center_freq_hz;
    ParamEstimate power_dbfs;
    ParamEstimate rms;
    ParamEstimate snr_db;
    ParamEstimate occupied_bw_hz;
    ParamEstimate cfo_hz;
};

struct M23ParamConfig {
    double sample_rate_hz = 128000.0;   // post-decimation model-domain sample rate
    float receiver_scale = 1.0f;        // frozen receiver_scale
    double full_scale_counts = 2048.0;  // 12-bit host full scale
    double cfo_reference_hz = 0.0;      // known reference carrier for CFO
    bool cfo_reference_set = false;     // CFO is valid only when this is true
    int cfo_order = 1;                  // 1=tone/pilot, 2=BPSK, 4=QPSK
};

// Estimate all five parameters for one frame.  Reuses `meas_scratch` and
// `cfo_scratch` across calls (allocation-stable after the first frame).
inline M23Params estimate_params(const std::complex<float>* iq, std::size_t n,
                                 const M23ParamConfig& cfg,
                                 sdr::MeasureScratch& meas_scratch,
                                 CfoScratch& cfo_scratch) {
    M23Params out;

    sdr::DspMeasureConfig mc;
    mc.sample_rate_hz = cfg.sample_rate_hz;
    mc.receiver_scale = cfg.receiver_scale;
    mc.full_scale_counts = cfg.full_scale_counts;
    const sdr::DspMeasure meas(mc);
    const sdr::FrameMeasurements m = meas.measure_into(iq, n, meas_scratch);

    const bool raw_ok = m.valid && !m.nan_inf;
    // The spectrum block only runs for power-of-two sizes >= 2 (see dsp_measure).
    const bool spectrum_ok = raw_ok && n >= 2 && (n & (n - 1)) == 0;

    out.power_dbfs = ParamEstimate{m.power_dbfs, raw_ok};
    out.rms = ParamEstimate{m.rms_counts, raw_ok};
    out.center_freq_hz = ParamEstimate{m.spectral_centroid_hz, spectrum_ok};
    out.snr_db = ParamEstimate{m.snr_est_db, spectrum_ok};
    // Occupied bandwidth is only meaningful when at least one bin exceeds the
    // occupancy threshold; otherwise it stays 0 / invalid rather than lying.
    out.occupied_bw_hz = ParamEstimate{m.occupied_bw_hz,
                                       spectrum_ok && m.occupied_bins > 0};

    if (cfg.cfo_reference_set && raw_ok) {
        const double cfo = estimate_cfo(iq, n, cfg.sample_rate_hz,
                                        cfg.cfo_reference_hz, cfg.cfo_order,
                                        cfo_scratch);
        out.cfo_hz = ParamEstimate{cfo, std::isfinite(cfo)};
    } else {
        out.cfo_hz = ParamEstimate{0.0, false};
    }

    return out;
}

// Tracks the freshness of the last valid parameter set.  A parameter is STALE
// when either (a) it was never valid, or (b) more than `max_age_frames` have
// elapsed since its last valid refresh.  The intended use: refresh() is only
// called while SIGNAL_PRESENT is confirmed, so when the signal drops the
// params naturally age out and the UI shows "--" instead of a frozen number.
struct M23ParamState {
    M23Params latest;
    bool has_any = false;                          // ever refreshed with a valid set
    std::uint64_t last_valid_frame = 0;            // frame id of last valid refresh
    std::uint64_t max_age_frames = PARAM_STALE_AFTER_FRAMES;

    // Record a fresh estimate at `frame_id`.  Stores it and updates the
    // freshness marker regardless of validity; invalid sets do not advance
    // last_valid_frame, so they age out immediately.
    void refresh(std::uint64_t frame_id, const M23Params& p) {
        latest = p;
        has_any = true;
        // A refresh with no computable spectrum still keeps the previous
        // last_valid_frame so a single bad frame does not instantly stale a
        // stable signal (this matches the presence machine's hysteresis intent).
        if (p.power_dbfs.valid) last_valid_frame = frame_id;
    }

    // True when the current values are too old to display as numbers.
    bool stale(std::uint64_t frame_id) const {
        if (!has_any) return true;
        if (frame_id < last_valid_frame) return true;  // clock went backwards
        return (frame_id - last_valid_frame) > max_age_frames;
    }
};

// Render one parameter for display: the literal "--" when invalid or stale,
// otherwise a fixed-width number.  This is the single place the "--" convention
// lives, so the UI and the replay tool can never disagree.
inline std::string render_param(const ParamEstimate& e, bool stale) {
    if (!e.valid || stale) return "--";
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.3f", e.value);
    return buf;
}

}  // namespace m23
