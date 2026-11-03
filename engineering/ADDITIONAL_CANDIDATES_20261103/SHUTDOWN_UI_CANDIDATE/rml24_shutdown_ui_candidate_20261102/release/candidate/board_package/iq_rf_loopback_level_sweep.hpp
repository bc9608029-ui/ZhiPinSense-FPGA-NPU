#pragma once

// iq_rf_loopback_level_sweep.hpp -- Stage H-F / Route F fix8 Task C: the PHYSICAL
// RF SAFE-OPERATING-POINT sweep (NO labels, NO NPU, NO classification).
//
// Route F fix7 needed an a-priori operating point (TX frozen-IQ RMS counts + RX
// gain) but had no instrument to find one: the RF path's physical gain is unknown
// until measured, so a fixed RMS/gain can either clip the RX ADC or land the signal
// in the noise.  This sweep scans the TX RMS levels {512,1024,2048,4096,8192}
// (complex-magnitude counts) x RX gains {0,10,20,30} dB x waveforms {tone, PRBS,
// QPSK}, measuring the looped-back RX RMS / clip / correlation at every point under
// the FIXED RF-safety conditions (loopback=0, --rf-path=direct-cable, TX attenuator
// -40 dB, no auto TX power, no antenna, 50-ohm coax), and then RECOMMENDS the
// largest clip-free TX RMS level + the RX gain whose median RX RMS lands closest to
// the safe target.  It never uses a label: every waveform is a synthetic test
// signal and the selection reads only measured fidelity.
//
// A point is rejected on clip (tx_clipped || rx_clipped) and on a failed negative
// control; the recommendation is diagnostic evidence for the operator, never a
// promoted RF_PRESERVES_IQ / *_PASS verdict (a host run cannot establish RF
// fidelity -- only a board run can).
//
// iCraft-free and libiio-free: pure logic over pluto::Device + pluto::PlutoTx,
// host-testable against FakePlutoDevice.

#include "board_common.hpp"
#include "iq_rf_loopback.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace iqrfloop_sweep {

// Sweep grid (TX complex-magnitude RMS counts) and RX gain grid.  The highest TX
// level 8192 has amplitude ~11585 for a tone (well inside the 12-bit DAC rail once
// the device converts), so the grid resolves the RX clip point without the TX
// itself ever driving the DAC full scale.
constexpr double kRfLevels[] = {512.0, 1024.0, 2048.0, 4096.0, 8192.0};
constexpr double kRfGainsDb[] = {0.0, 10.0, 20.0, 30.0};
constexpr const char* kRfKinds[] = {"tone", "prbs", "qpsk"};

// Discard-refill length that drains the just-stopped TX's stale DMA before the
// noise floor and before each capture (not counted in either).
constexpr std::size_t kRfSweepDiscardComplex = 4096;
// Sweep waveform length (complex samples); the capture is 2x + delay margin so the
// full-period FFT circular sync has a complete period plus the transient margin.
constexpr std::size_t kRfSweepWaveformComplex = 8192;

// RX complex-magnitude RMS at or below this is indistinguishable from quantization
// noise (not a usable operating point).
constexpr double kRfQuantFloorCounts = 2.0;
// Safe RX RMS window for the recommendation: at least a little above the floor and
// at most this (well below the 2048 12-bit ADC rail, leaving crest-factor headroom).
constexpr double kRfSafeRxRmsMax = 512.0;
// Preferred RX RMS target: the gain whose median RX RMS is closest to this is the
// recommended gain at a given level.
constexpr double kRfTargetRxRms = 64.0;

// ---- small numeric helpers --------------------------------------------------

inline double rms_magnitude(const std::vector<std::int16_t>& iq) {
    double e = 0.0;
    const std::size_t n = iq.size() / 2;
    for (std::size_t k = 0; k < n; ++k) {
        const double i = iq[k * 2 + 0];
        const double q = iq[k * 2 + 1];
        e += i * i + q * q;
    }
    return n ? std::sqrt(e / static_cast<double>(n)) : 0.0;
}

inline double median(std::vector<double> v) {
    if (v.empty()) return 0.0;
    std::sort(v.begin(), v.end());
    const std::size_t n = v.size();
    return (n % 2) ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

// Scale an interleaved int16 waveform so its measured complex-magnitude RMS equals
// `target_rms`.
inline void scale_to_rms(std::vector<std::int16_t>& iq, double target_rms) {
    const double rms = rms_magnitude(iq);
    if (rms <= 0.0) return;
    const double s = target_rms / rms;
    for (auto& v : iq) {
        const double sv = std::llround(static_cast<double>(v) * s);
        v = static_cast<std::int16_t>(
            std::max(-32768.0, std::min(32767.0, sv)));
    }
}

// ---- deterministic sweep waveforms (tone / prbs / qpsk) ----------------------

// Synthetic test waveforms, NEVER a labelled RadioML sample.  All are periodic over
// `n_complex` so the cyclic TX buffer wraps without a phase discontinuity.
inline std::vector<std::int16_t> make_rf_level_waveform(const std::string& kind,
                                                        double target_rms,
                                                        std::size_t n_complex) {
    std::vector<std::int16_t> iq(n_complex * 2, 0);
    const double kPi = 3.14159265358979323846;
    if (kind == "tone") {
        // Complex tone at fs/16 (16 samples/cycle): |x| constant so RMS == amplitude.
        const double ph = 2.0 * kPi / 16.0;
        for (std::size_t k = 0; k < n_complex; ++k) {
            iq[k * 2 + 0] = static_cast<std::int16_t>(
                std::llround(1000.0 * std::cos(ph * static_cast<double>(k))));
            iq[k * 2 + 1] = static_cast<std::int16_t>(
                std::llround(1000.0 * std::sin(ph * static_cast<double>(k))));
        }
    } else if (kind == "prbs") {
        // 16-bit Galois LFSR PRBS on I and Q independently: +/-A, spectrally flat.
        std::uint32_t st = 0xACE1u;
        const auto bit = [&st]() {
            const std::uint32_t b =
                ((st >> 0) ^ (st >> 2) ^ (st >> 3) ^ (st >> 5)) & 1u;
            st = (st >> 1) | (b << 15);
            return b;
        };
        for (std::size_t k = 0; k < n_complex; ++k) {
            iq[k * 2 + 0] = bit() ? 1000 : -1000;
            iq[k * 2 + 1] = bit() ? 1000 : -1000;
        }
    } else {  // "qpsk" -- the >=1 modulated waveform (deterministic QPSK)
        // 4 symbols/cycle of a 4-symbol alphabet; a real phase-modulated signal,
        // not a tone or a raw PRBS.
        std::uint32_t st = 0xBEEFu;
        const std::size_t sps = 4;
        const double amp = 1000.0 * 0.7071067811865476;  // 1000/sqrt(2)
        for (std::size_t k = 0; k < n_complex; ++k) {
            if (k % sps == 0) st = st * 1664525u + 1013904223u;
            const int b = static_cast<int>((st >> 24) & 3u);
            iq[k * 2 + 0] = static_cast<std::int16_t>(
                std::llround((b & 1) ? amp : -amp));
            iq[k * 2 + 1] = static_cast<std::int16_t>(
                std::llround((b & 2) ? amp : -amp));
        }
    }
    scale_to_rms(iq, target_rms);
    return iq;
}

// ---- per-point measurement ---------------------------------------------------

// One (level x gain x kind) RF operating point, measured end to end.
struct RfLevelSweepPoint {
    std::string kind;
    double level_counts = 0.0;    // TX complex-magnitude RMS target (counts)
    double rx_gain_db = 0.0;

    double tx_rms = 0.0;          // measured TX RMS (counts)
    double rx_rms = 0.0;          // measured RX complex-magnitude RMS (counts)
    double corr = 0.0;            // |correlation| through the RF path
    double noise_rms = 0.0;       // TX-off negative-control floor RMS
    double snr_db = 0.0;          // 20 log10(rx_rms / noise_rms), +inf if floor 0
    std::uint64_t tx_clip_count = 0;
    std::uint64_t rx_clip_count = 0;
    bool tx_clipped = false;      // TX DAC overdriven (fix8 Task A rails)
    bool rx_clipped = false;      // RX ADC railed
    bool negative_control_ok = false;   // TX stopped + noise not railed
    bool tx_stopped_readback = false;   // tx_running() == false after tx_stop
    bool capture_ok = false;      // one contiguous capture refill
};

// Run ONE RF operating point: TX-off negative control (stop -> confirm -> drain the
// stale DMA with a discard refill -> one noise floor) BEFORE any TX, then TX the
// synthetic waveform on the EXTERNAL RF path (loopback=0, confirm_safe_rf_path=true,
// tx_atten fixed), flush, and capture one contiguous refill.  Reuses the same
// fidelity measure as the Route F runner (full-period FFT circular sync + clip
// rails from the device data format + noise-floor SNR).
inline RfLevelSweepPoint sweep_rf_level_one(
        pluto::Device& dev, std::uint64_t center_hz, double rx_gain_db,
        double tx_atten_db, const std::string& kind, double level_counts,
        std::uint64_t fs, std::size_t delay_margin, std::size_t waveform_complex) {
    RfLevelSweepPoint p;
    p.kind = kind;
    p.level_counts = level_counts;
    p.rx_gain_db = rx_gain_db;

    const std::vector<std::int16_t> tx =
        make_rf_level_waveform(kind, level_counts, waveform_complex);
    p.tx_rms = rms_magnitude(tx);

    // ---- TX-off negative control BEFORE any TX ----
    std::vector<std::int16_t> noise;
    bool noise_capture_ok = false;
    {
        dev.tx_stop();
        p.tx_stopped_readback = !dev.tx_running();
        dev.recreate_rx_buffer();
        const iio::RawChunk dc = dev.read_rx(kRfSweepDiscardComplex, 1000);  // stale drain
        (void)dc;
        dev.recreate_rx_buffer();
        board::RxStats st;
        board::Continuity cont;
        noise_capture_ok =
            board::capture_contiguous(dev, waveform_complex, noise, st, cont);
    }

    std::vector<std::int16_t> rx;
    {
        pluto::TxConfig txc;
        txc.center_freq_hz = center_hz;
        txc.rx_gain_db = rx_gain_db;
        txc.tx_atten_db = tx_atten_db;
        txc.loopback = 0;                    // EXTERNAL RF, not digital
        txc.confirm_safe_rf_path = true;     // 50-ohm coax, no antenna, no amplifier
        txc.waveform = tx;
        pluto::PlutoTx pltx(dev, txc);
        pltx.prepare();                      // -40 dB ceiling + read-backs
        pltx.start_cyclic();

        dev.recreate_rx_buffer();
        dev.read_rx(kRfSweepDiscardComplex, 1000);   // stale flush
        board::RxStats st;
        board::Continuity cont;
        const std::size_t capture = 2 * waveform_complex + delay_margin;
        p.capture_ok = board::capture_contiguous(dev, capture, rx, st, cont);
    }

    const int tx_bits = [&]() {
        const pluto::DataFormatInfo f = dev.tx_data_format();
        return (f.bits == 0 || f.bits > 16) ? 16 : static_cast<int>(f.bits);
    }();
    const int rx_bits = [&]() {
        const pluto::DataFormatInfo f = dev.rx_data_format();
        return (f.bits == 0 || f.bits > 16) ? 16 : static_cast<int>(f.bits);
    }();

    // Same fidelity measure as the Route F runner (clip rails from the data format,
    // never hardcoded; full-period FFT circular sync; noise-floor SNR).
    const iqrfloop::RfFidelityMetrics m = iqrfloop::measure_rf_fidelity(
        tx, rx, noise, noise_capture_ok, fs, tx_bits, rx_bits,
        iqdloop_sync::kTransientDiscardComplex);

    p.rx_rms = m.sync.rms_rx;
    p.corr = m.sync.corr;
    p.noise_rms = m.noise_floor_rms;
    p.snr_db = m.snr_db;
    p.tx_clip_count = m.sync.tx_clip_count;
    p.rx_clip_count = m.sync.rx_clip_count;
    p.tx_clipped = m.sync.tx_clipped;
    p.rx_clipped = m.sync.rx_clipped;
    p.negative_control_ok = p.tx_stopped_readback && m.negative_control_ok;
    return p;
}

// ---- selection ---------------------------------------------------------------

struct RfLevelSelection {
    bool ok = false;
    double recommended_rms_counts = 0.0;   // the recommended --raw-complex-rms-counts
    double recommended_rx_gain = 0.0;      // the recommended --rx-gain (dB)
    double median_rx_rms = 0.0;            // median RX RMS at the chosen gain
    std::string reason;
};

// Recommend the operating point: the LARGEST clip-free, high-fidelity TX RMS level
// whose best RX gain keeps the median RX RMS inside the safe window.  "Best gain"
// at a level is the gain whose median RX RMS (across kinds) is closest to the
// target.  Never uses a label; reads only measured fidelity.
inline RfLevelSelection select_rf_level(const std::vector<RfLevelSweepPoint>& points) {
    RfLevelSelection s;
    s.reason = "no clip-free high-fidelity point in the grid";

    std::vector<const RfLevelSweepPoint*> cand;
    for (const RfLevelSweepPoint& p : points) {
        if (p.capture_ok && p.negative_control_ok && !p.tx_clipped && !p.rx_clipped &&
            p.corr >= iqrfloop::kRfSyncCorrThreshold &&
            p.rx_rms >= kRfQuantFloorCounts && p.rx_rms <= kRfSafeRxRmsMax)
            cand.push_back(&p);
    }
    if (cand.empty()) return s;

    // Levels present among candidates, descending (largest dynamic range first).
    std::vector<double> levels;
    for (const RfLevelSweepPoint* p : cand)
        if (std::find(levels.begin(), levels.end(), p->level_counts) == levels.end())
            levels.push_back(p->level_counts);
    std::sort(levels.rbegin(), levels.rend());

    for (double lvl : levels) {
        std::vector<const RfLevelSweepPoint*> at;
        for (const RfLevelSweepPoint* p : cand)
            if (p->level_counts == lvl) at.push_back(p);

        std::vector<double> gains;
        for (const RfLevelSweepPoint* p : at)
            if (std::find(gains.begin(), gains.end(), p->rx_gain_db) == gains.end())
                gains.push_back(p->rx_gain_db);
        std::sort(gains.begin(), gains.end());

        double best_gain = gains.empty() ? 0.0 : gains[0];
        double best_d = 1e300;
        double best_rms = 0.0;
        for (double g : gains) {
            std::vector<double> r;
            for (const RfLevelSweepPoint* p : at)
                if (p->rx_gain_db == g) r.push_back(p->rx_rms);
            const double med = median(r);
            const double d = std::fabs(med - kRfTargetRxRms);
            if (d < best_d) { best_d = d; best_gain = g; best_rms = med; }
        }
        if (best_rms >= kRfQuantFloorCounts && best_rms <= kRfSafeRxRmsMax) {
            s.ok = true;
            s.recommended_rms_counts = lvl;
            s.recommended_rx_gain = best_gain;
            s.median_rx_rms = best_rms;
            s.reason =
                "largest clip-free level " + std::to_string(lvl) +
                " counts with RX gain " + std::to_string(best_gain) +
                " dB (median RX RMS " + std::to_string(best_rms) +
                " counts, closest to target " + std::to_string(kRfTargetRxRms) + ")";
            return s;
        }
    }

    s.reason = "no level kept a safe RX RMS inside the window at any gain";
    return s;
}

// ---- orchestration (pure over an already-open Device; no board::/NPU deps) ----

struct RfLevelSweepConfig {
    std::uint64_t center_hz = 2400000000;
    double tx_atten_db = pluto::kSafeTxCeilingDb; // -40 dB (least attenuation allowed)
    std::uint64_t fs = 2560000;
    std::size_t delay_margin = 4096;
    std::size_t waveform_complex = 8192;
    std::vector<std::string> kinds;      // empty -> {tone, prbs, qpsk}
    std::vector<double> levels;          // empty -> {512..8192}
    std::vector<double> gains_db;        // empty -> {0,10,20,30}
};

struct RfLevelSweepReport {
    pluto::DataFormatInfo tx_fmt;
    pluto::DataFormatInfo rx_fmt;
    std::vector<RfLevelSweepPoint> points;
    RfLevelSelection selection;
    bool ran = false;
    std::string error;   // non-empty => fail-closed
};

// Run the full grid against an already-open device.  Prints nothing and touches no
// NPU or board:: plumbing, so it is host-testable against FakePlutoDevice.
inline RfLevelSweepReport sweep_rf_levels(pluto::Device& dev,
                                          const RfLevelSweepConfig& cfg) {
    RfLevelSweepReport rep;
    rep.ran = true;
    rep.tx_fmt = dev.tx_data_format();
    rep.rx_fmt = dev.rx_data_format();

    const std::vector<std::string> kinds = cfg.kinds.empty()
        ? std::vector<std::string>(kRfKinds, kRfKinds + 3)
        : cfg.kinds;
    const std::vector<double> levels = cfg.levels.empty()
        ? std::vector<double>(kRfLevels, kRfLevels + 5)
        : cfg.levels;
    const std::vector<double> gains = cfg.gains_db.empty()
        ? std::vector<double>(kRfGainsDb, kRfGainsDb + 4)
        : cfg.gains_db;

    for (double gain : gains)
        for (double lvl : levels)
            for (const std::string& kind : kinds) {
                rep.points.push_back(sweep_rf_level_one(
                    dev, cfg.center_hz, gain, cfg.tx_atten_db, kind, lvl,
                    cfg.fs, cfg.delay_margin, cfg.waveform_complex));
            }

    rep.selection = select_rf_level(rep.points);
    return rep;
}

}  // namespace iqrfloop_sweep
