#pragma once

// board_common.hpp -- shared helpers for the Gate 1-5 board programs.
//
// These programs are the ONLY pieces that talk to a real Pluto (via the libiio
// pluto::Device); every DSP primitive they use is already unit-tested on the host
// (test_resampler / test_nco / test_receiver_scale / test_pluto_tx /
// test_sample_rate_negotiate).  The gate programs are thin, honest orchestration:
// they print a machine-parseable `GATE_RESULT gate=... result=PASS|FAIL ...` line
// and exit 0/1 (or 2 for "device not found"), and they restore the device on
// every path (DeviceStateGuard + RAII).
//
// iCraft-free; no <iio.h> here (the device abstraction is pluto::Device).

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <complex>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"
#include "../sdr_adapter/device_state_guard.hpp"
#include "../sdr_adapter/sample_rate_negotiate.hpp"
#include "../sdr_adapter/resampler.hpp"
#include "../sdr_adapter/nco.hpp"
#include "../sdr_adapter/receiver_scale.hpp"
#include "../sdr_adapter/rx_format.hpp"
#include "../sdr_adapter/fir_coeffs.h"
#include "../sdr_adapter/frame_analysis.hpp"

namespace board {

constexpr double kPi = 3.141592653589793238462643383279502884;

// The single-tone / per-frame DSP helpers now live in sdr:: (frame_analysis.hpp)
// so the host regression tests can exercise the exact same code the board runs.
// These aliases keep the existing `board::` call sites unchanged.
using sdr::goertzel_ratio;
using sdr::goertzel_bin;
using sdr::goertzel_amp;
using sdr::dominant_freq_hz;
using sdr::rms;
using sdr::max_abs_iq;
using sdr::to_complex;
using sdr::analyze_frames;

// ---- signal handling --------------------------------------------------------
//
// SIGINT/SIGTERM must NOT run destructors (the default handler terminates the
// process immediately and would leave the TX transmitting).  The handlers only
// set this flag; the blocking RX read is unblocked by its context timeout, and
// the normal flow then stops TX + restores parameters via RAII.

volatile std::sig_atomic_t g_stop_requested = 0;

inline void on_signal(int) { g_stop_requested = 1; }

inline void arm_signal_handlers() {
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
}

// ---- result reporting -------------------------------------------------------

inline void emit(const std::string& gate, bool pass, const std::string& detail) {
    std::printf("GATE_RESULT gate=%s result=%s %s\n", gate.c_str(),
                pass ? "PASS" : "FAIL", detail.c_str());
    std::fflush(stdout);
}

// ---- CLI -------------------------------------------------------------------

inline bool has_flag(int argc, char** argv, const char* name) {
    for (int i = 1; i < argc; ++i)
        if (std::string(argv[i]) == name) return true;
    return false;
}

// Parse `--name` from argv.  BOTH spellings are accepted:
//     --name=value        (one token)
//     --name value        (two tokens, as the run scripts and docs use)
// A LATER occurrence overrides an earlier one, so a user's post-script argument
// (`run_gate6.sh --loopback 1`) can override a script default.  A MISSING value
// (`--name` at end, or `--name` followed by another `--flag`) THROWS, so a
// malformed CLI fails closed instead of silently falling back to `def`.
inline std::string get_opt(int argc, char** argv, const char* name,
                           const std::string& def) {
    const std::string eq = std::string(name) + "=";
    std::string found;
    bool present = false;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a.compare(0, eq.size(), eq) == 0) {
            found = a.substr(eq.size());
            present = true;
        } else if (a == name) {
            if (i + 1 >= argc ||
                std::string(argv[i + 1]).compare(0, 2, "--") == 0) {
                throw std::runtime_error(std::string("missing value for ") + name);
            }
            found = argv[i + 1];
            present = true;
            ++i;   // consume the value token (may be numeric or a path)
        }
    }
    return present ? found : def;
}

// Strict numeric CLI parsing shared by every gate.  Fail-closed: an empty value,
// trailing junk, or an out-of-range number THROWS (never silently falls back to
// the default).  The gate programs call these inside their try block, so a throw
// becomes result=FAIL + a non-zero exit.
inline std::uint64_t opt_u64(int argc, char** argv, const char* name,
                             std::uint64_t def) {
    const std::string s = get_opt(argc, argv, name, std::to_string(def));
    if (s.empty())
        throw std::runtime_error(std::string("empty value for ") + name);
    char* end = nullptr;
    errno = 0;
    const unsigned long long v = std::strtoull(s.c_str(), &end, 10);
    if (end == s.c_str() || *end != '\0' || errno == ERANGE)
        throw std::runtime_error(std::string("invalid integer for ") + name +
                                 ": '" + s + "'");
    return static_cast<std::uint64_t>(v);
}

inline double opt_d(int argc, char** argv, const char* name, double def) {
    const std::string s = get_opt(argc, argv, name, std::to_string(def));
    if (s.empty())
        throw std::runtime_error(std::string("empty value for ") + name);
    char* end = nullptr;
    errno = 0;
    const double v = std::strtod(s.c_str(), &end);
    if (end == s.c_str() || *end != '\0' || errno == ERANGE)
        throw std::runtime_error(std::string("invalid float for ") + name +
                                 ": '" + s + "'");
    return v;
}

// ---- Goertzel --------------------------------------------------------------
//
// (goertzel_ratio / goertzel_bin / goertzel_amp / dominant_freq_hz are defined in
// sdr_adapter/frame_analysis.hpp and re-exported above as board:: aliases, so the
// board programs and host tests share one implementation.)

// ---- RX accumulation -------------------------------------------------------

struct RxStats {
    std::uint64_t complex_read = 0;
    std::uint64_t overflow = 0;
    std::uint64_t dropped = 0;
    std::uint64_t discontinuity = 0;
    std::uint64_t timeouts = 0;
    bool short_block = false;   // fewer samples than requested
    bool interrupted = false;   // SIGINT/SIGTERM requested a stop
};

// Read up to n_complex complex samples into an interleaved int16 buffer.
// Returns false on a broken stream (device down).  Bounded retry on empty/timeout
// reads so the program cannot spin forever on a stuck device.  A pending
// SIGINT/SIGTERM (g_stop_requested) aborts early with st.interrupted = true, so
// the caller's normal cleanup (stop TX + restore) runs.
inline bool collect_raw(pluto::Device& dev, std::size_t n_complex,
                        std::vector<std::int16_t>& iq, RxStats& st) {
    std::uint64_t empty_polls = 0;
    while (iq.size() / 2 < n_complex) {
        if (g_stop_requested) { st.interrupted = true; return true; }
        const std::size_t want = n_complex - iq.size() / 2;
        const iio::RawChunk c = dev.read_rx(want, 1000);
        if (c.broken) return false;
        if (c.timed_out) {
            ++st.timeouts;
            if (++empty_polls > 100) { st.short_block = true; return true; }
            continue;
        }
        if (c.samples_available == 0) {
            if (++empty_polls > 100) { st.short_block = true; return true; }
            continue;
        }
        empty_polls = 0;
        if (c.overflow) ++st.overflow;
        if (c.dropped) ++st.dropped;
        if (c.discontinuity) ++st.discontinuity;
        iq.insert(iq.end(), c.samples, c.samples + c.samples_available * 2);
        st.complex_read += c.samples_available;
    }
    if (iq.size() / 2 < n_complex) st.short_block = true;
    return true;
}

// Gate 5: read EXACTLY n_complex complex samples in ONE contiguous RX refill.
// A single iio_buffer_refill returns contiguous DMA samples (no dropped-sample
// phase break between blocks), so the caller may treat the result as a real
// continuous stream for NCO / resampling / receiver_scale.  FAILS CLOSED (returns
// false) unless the device hands back the whole amount in that one refill with no
// stream anomaly -- it does NOT loop-and-concatenate blocks, which is what a
// fixed-1024 backend used to fake into a "continuous" stream.
inline bool collect_raw_contiguous(pluto::Device& dev, std::size_t n_complex,
                                   std::vector<std::int16_t>& iq, RxStats& st,
                                   std::uint64_t timeout_ms = 5000) {
    const iio::RawChunk c = dev.read_rx(n_complex, timeout_ms);
    if (c.broken) return false;
    if (c.timed_out) ++st.timeouts;
    if (c.overflow) ++st.overflow;
    if (c.dropped) ++st.dropped;
    if (c.discontinuity) ++st.discontinuity;

    const std::size_t got = c.samples_available;
    if (got > 0) {
        iq.assign(c.samples, c.samples + got * 2);
    } else {
        iq.clear();
    }
    st.complex_read = got;

    const bool short_refill = got < n_complex;
    if (short_refill) st.short_block = true;
    const bool clean = !c.timed_out && !short_refill &&
                       st.overflow == 0 && st.dropped == 0 && st.discontinuity == 0;
    return clean;
}

// Continuity evidence a device capture must prove to PASS: the samples came from
// EXACTLY ONE RX refill (no loop-and-concatenate of phase-discontinuous blocks)
// and the RX buffer was sized to hold the whole request.  Gate 6, Gate 9 and the
// §九 calibrator all gate on this ONE shared rule, so a multi-refill capture can
// never be silently treated as a continuous stream.
struct Continuity {
    std::size_t requested = 0;         // input complex samples requested
    std::size_t capacity = 0;          // device RX buffer capacity after the read
    std::uint64_t refill_delta = 0;    // rx_refill_count advance during the read
    bool single_refill = false;        // refill_delta == 1

    bool capacity_ok() const { return capacity >= requested; }
    bool ok() const { return single_refill && capacity_ok(); }

    std::string report() const {
        return " requested_input_complex=" + std::to_string(requested) +
               " rx_buffer_capacity=" + std::to_string(capacity) +
               " rx_refill_count_delta=" + std::to_string(refill_delta) +
               " single_refill=" + std::to_string(single_refill ? 1 : 0);
    }
};

// Capture EXACTLY `requested` complex samples in ONE contiguous RX refill and fill
// the continuity evidence the gates print and gate on.  `iq` receives the
// interleaved int16 samples; `st` accumulates stream anomalies.  Returns true only
// when the single refill delivered the full amount with no anomaly (timed_out /
// short / overflow / drop / discontinuity all clean).  Shared by Gate 6, Gate 9
// and the calibrator so the continuity rule is identical everywhere.
inline bool capture_contiguous(pluto::Device& dev, std::size_t requested,
                               std::vector<std::int16_t>& iq, RxStats& st,
                               Continuity& cont) {
    cont.requested = requested;
    const std::uint64_t before = dev.rx_refill_count();
    const bool ok = collect_raw_contiguous(dev, requested, iq, st);
    const std::uint64_t after = dev.rx_refill_count();
    cont.refill_delta = after - before;
    cont.single_refill = (cont.refill_delta == 1);
    cont.capacity = dev.rx_buffer_capacity();
    return ok;
}

// (to_complex is defined in frame_analysis.hpp as sdr::to_complex with full-scale
// 2048 for the 12-bit AD9364, and re-exported above as board::to_complex.)

// Save raw interleaved int16 to a file (little-endian) for PC review.
inline bool save_raw_iq(const std::string& path, const std::vector<std::int16_t>& iq) {
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    const std::size_t n = std::fwrite(iq.data(), sizeof(std::int16_t), iq.size(), f);
    std::fclose(f);
    return n == iq.size();
}

// A CW tone with an exact integer number of periods (so the cyclic TX buffer
// wraps without a phase discontinuity).  freq_hz must divide fs_hz for the
// chosen candidates (10 kHz divides 2.56 MHz and 3.84 MHz).  Amplitude is in
// 12-bit DAC counts (< 2048).
inline std::vector<std::int16_t> make_periodic_tone(double freq_hz, double fs_hz,
                                                    int periods,
                                                    double amplitude = 1500.0) {
    const std::size_t spp = static_cast<std::size_t>(std::llround(fs_hz / freq_hz));
    return pluto::make_cw_tone(freq_hz, fs_hz, spp * static_cast<std::size_t>(periods),
                               amplitude);
}

// (rms / max_abs_iq are defined in frame_analysis.hpp as sdr::rms /
// sdr::max_abs_iq and re-exported above as board:: aliases.)

// ---- restore report --------------------------------------------------------

// Read back the post-restore device state and format it.  Never throws (a read
// that fails prints "ERR"), so it is safe to call from a catch path.
inline std::string restore_report(pluto::Device& dev,
                                  const pluto::DeviceStateGuard& guard) {
    std::string s = " restore_result=" + std::string(guard.restore_ok() ? "PASS" : "FAIL");
    auto get_ll = [](pluto::Device& d, long long (pluto::Device::*fn)() const) {
        try { return std::to_string((d.*fn)()); } catch (...) { return std::string("ERR"); }
    };
    auto get_d = [](pluto::Device& d, double (pluto::Device::*fn)() const) {
        try { return std::to_string((d.*fn)()); } catch (...) { return std::string("ERR"); }
    };
    auto get_s = [](pluto::Device& d, std::string (pluto::Device::*fn)() const) {
        try { return (d.*fn)(); } catch (...) { return std::string("ERR"); }
    };
    auto get_i = [](pluto::Device& d, int (pluto::Device::*fn)() const) {
        try { return std::to_string((d.*fn)()); } catch (...) { return std::string("ERR"); }
    };
    s += " rx_sample_rate=" + get_ll(dev, &pluto::Device::get_rx_sample_rate);
    s += " tx_sample_rate=" + get_ll(dev, &pluto::Device::get_tx_sample_rate);
    s += " rx_lo=" + get_ll(dev, &pluto::Device::get_rx_lo);
    s += " tx_lo=" + get_ll(dev, &pluto::Device::get_tx_lo);
    s += " rx_bw=" + get_ll(dev, &pluto::Device::get_rx_bw);
    s += " tx_bw=" + get_ll(dev, &pluto::Device::get_tx_bw);
    s += " rx_gain_mode=" + get_s(dev, &pluto::Device::get_rx_gain_mode);
    s += " rx_gain=" + get_d(dev, &pluto::Device::get_rx_gain);
    s += " tx_atten=" + get_d(dev, &pluto::Device::get_tx_atten);
    s += " loopback=" + get_i(dev, &pluto::Device::get_loopback);
    return s;
}

// ---- fail-closed gate verdict ----------------------------------------------
//
// A functional PASS is only a real PASS if the device restore also succeeded.
// This closes the fail-open bug where a gate printed `result=PASS` even when
// `restore_result=FAIL`: the board log showed exactly that (Gate 6 restored the
// gain mode to slow_attack, the subsequent manual hardwaregain write failed, and
// the gate still emitted PASS).  All three device gates (Gate 6, calibrate, Gate 9)
// fold this into their final verdict so restore failure forces result=FAIL and a
// non-zero exit.  Returns the final pass and appends a "(restore_failed)" marker.
inline bool final_gate_pass(bool functional_pass, bool restore_ok,
                            std::string& detail) {
    if (!restore_ok) {
        if (!detail.empty() && detail.back() != ' ') detail += ' ';
        detail += "(restore_failed)";
    }
    return functional_pass && restore_ok;
}

// On a loopback failure, dump the raw interleaved int16 IQ plus the first 32
// unpacked I/Q pairs and the RX/TX stream data-format metadata, so the failure is
// diagnosable from the board log without re-running.  Best-effort (never throws).
inline void save_loopback_dump(pluto::Device& dev, const std::vector<std::int16_t>& iq,
                               const std::string& base) {
    save_raw_iq(base + "_raw.bin", iq);
    FILE* f = std::fopen((base + "_dump.txt").c_str(), "w");
    if (!f) return;
    std::fprintf(f, "rx_format=%s\n",
                 pluto::describe_data_format(dev.rx_data_format()).c_str());
    std::fprintf(f, "tx_format=%s\n",
                 pluto::describe_data_format(dev.tx_data_format()).c_str());
    std::fprintf(f, "n_complex=%zu\n", iq.size() / 2);
    const std::size_t n = std::min<std::size_t>(32, iq.size() / 2);
    for (std::size_t k = 0; k < n; ++k)
        std::fprintf(f, "%d %d\n", iq[k * 2 + 0], iq[k * 2 + 1]);
    std::fclose(f);
}

// ---- loopback test (Gate 3 digital / Gate 4 RF) ----------------------------

struct LoopbackSpec {
    std::uint64_t center_hz = 2450000000;
    double tone_hz = 10000.0;                  // baseband CW tone (divides 2.56/3.84 MHz)
    double rx_gain_db = 10.0;                  // low manual RX gain (Gate 4 uses 20 dB)
    double tx_atten_db = pluto::kSafeTxAttenDb;  // default max-safe
    int loopback = 1;                          // 1 = digital, 0 = external RF
    bool confirm_safe_rf = false;              // REQUIRED when loopback == 0
    std::uint64_t frames = 128;
    int periods = 8;                           // whole periods in the TX waveform
    // Pre-fixed per-frame frequency gate (Hz).  300 Hz = 3% of the 10 kHz tone; a
    // WRONG tone is off by far more, while a clean tone measures within ~a few Hz
    // (board offline analysis: freq_mean 9998.83 Hz).  NOT relaxed by this result.
    double freq_err_max_hz = 300.0;
};

// Run the full self-TX/self-RX loopback and fill *pass/*detail.  The PlutoTx RAII
// guarantees the TX buffer is destroyed on every path (including prepare()
// failure or stream break); parameter restore is the caller's DeviceStateGuard.
//
// VERDICT IS PER-1024-POINT FRAME (not full-length): each RX refill block is
// internally a clean tone but starts at an arbitrary phase, so one full-length
// Goertzel over the concatenated blocks cancels and reports a FALSE failure (board
// result: per-frame ratio ~0.99998 yet full-length ratio 0.030).  Every frame is
// analysed independently (ratio at +/-tone, dominant frequency, peak, RMS); the
// full-length "global_ratio" is kept ONLY as a diagnostic and never gates PASS.
// Never throws.
inline void run_loopback(pluto::Device& dev, const sdr::RateNegotiation& neg,
                         const LoopbackSpec& spec, bool* pass, std::string* detail) {
    bool p = false;
    std::string d;
    const double fs_dev = static_cast<double>(neg.actual_hz);

    try {
        pluto::TxConfig txc;
        txc.center_freq_hz = spec.center_hz;
        txc.rx_gain_db = spec.rx_gain_db;
        txc.tx_atten_db = spec.tx_atten_db;
        txc.loopback = spec.loopback;
        txc.confirm_safe_rf_path = spec.confirm_safe_rf;
        txc.waveform = make_periodic_tone(spec.tone_hz, fs_dev, spec.periods);

        pluto::PlutoTx tx(dev, txc);
        tx.prepare();
        tx.start_cyclic();

        const std::size_t n_complex = static_cast<std::size_t>(spec.frames) * 1024;
        std::vector<std::int16_t> iq;
        RxStats st;
        if (!collect_raw(dev, n_complex, iq, st)) {
            d += " stream_broken";
            p = false;
        } else {
            const double ratio_threshold = 0.3;   // MUST NOT be relaxed by this result
            const sdr::FrameSummary s =
                sdr::analyze_frames(iq, 1024, spec.tone_hz, fs_dev,
                                    ratio_threshold, spec.freq_err_max_hz);

            const bool no_sat = s.peak_max < pluto::kDacFullScale;   // 12-bit full scale
            const bool clean = !st.short_block && !st.interrupted &&
                               st.overflow == 0 && st.dropped == 0 &&
                               st.discontinuity == 0;
            const bool frames_complete = s.frame_count == spec.frames;
            const bool all_pass = s.frame_count > 0 && s.frame_pass_count == s.frame_count;
            p = frames_complete && all_pass && no_sat && clean;

            d += " frame_count=" + std::to_string(s.frame_count);
            d += " frame_ratio_min=" + std::to_string(s.ratio_min);
            d += " frame_ratio_mean=" + std::to_string(s.ratio_mean);
            d += " frame_ratio_max=" + std::to_string(s.ratio_max);
            d += " frame_pass_count=" + std::to_string(s.frame_pass_count);
            d += " frame_freq_mean=" + std::to_string(s.freq_mean);
            d += " frame_freq_max_error=" + std::to_string(s.freq_max_error);
            d += " global_ratio=" + std::to_string(s.global_ratio);   // diagnostic only
            d += " peak=" + std::to_string(s.peak_max);
            d += " rms=" + std::to_string(s.rms_mean);
            d += " short=" + std::to_string(st.short_block ? 1 : 0);
            d += " interrupted=" + std::to_string(st.interrupted ? 1 : 0);
            d += " overflow=" + std::to_string(st.overflow);
            d += " drop=" + std::to_string(st.dropped);
            d += " disc=" + std::to_string(st.discontinuity);
            d += " timeouts=" + std::to_string(st.timeouts);
            d += " rx_buffer_capacity=" + std::to_string(dev.rx_buffer_capacity());
            d += " rx_refill_count=" + std::to_string(dev.rx_refill_count());
            if (!frames_complete) d += " (frame_short)";
            if (!all_pass) d += " (frame_fail)";
            if (!no_sat) d += " (adc_saturated)";
            if (st.interrupted) d += " (interrupted)";
            if (!clean) d += " (stream_anomaly)";

            // Auto-save the failure so it is diagnosable without a re-run.
            if (!p) {
                const std::string base = (spec.loopback == 0) ? "rf_loopback" : "digital_loopback";
                save_loopback_dump(dev, iq, base);
                d += " dump=" + base + "_raw.bin";
            }
        }
    } catch (const std::exception& e) {
        p = false;
        d += std::string(" error=") + e.what();
    }

    *pass = p;
    *detail = d;
}

}  // namespace board
