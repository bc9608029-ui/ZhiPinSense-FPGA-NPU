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
#include <cmath>
#include <complex>
#include <csignal>
#include <cstdint>
#include <cstdio>
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

namespace board {

constexpr double kPi = 3.141592653589793238462643383279502884;

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

inline std::string get_opt(int argc, char** argv, const char* name,
                           const std::string& def) {
    const std::string prefix = std::string(name) + "=";
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a.compare(0, prefix.size(), prefix) == 0) return a.substr(prefix.size());
    }
    return def;
}

// ---- Goertzel --------------------------------------------------------------

// Single-bin Goertzel energy ratio (matches the host tests; avoids an FFT).
// Ratio is SCALE-INVARIANT spectral concentration in [0,1]: ~1.0 when a single
// tone at frequency `f` dominates, ~0 when the energy is elsewhere.
inline double goertzel_ratio(const std::vector<std::complex<float>>& x,
                             double f, double fs) {
    const std::size_t n = x.size();
    std::complex<double> acc(0.0, 0.0);
    double total = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        const double ph = 2.0 * kPi * f / fs * static_cast<double>(i);
        const std::complex<double> ref(std::cos(ph), -std::sin(ph));
        const std::complex<double> s(x[i].real(), x[i].imag());
        acc += s * ref;
        total += std::abs(s);
    }
    return std::abs(acc) / (total + 1e-12);
}

// Raw single-bin complex accumulation (unnormalised).  For a complex tone
// x[k] = A*exp(j*2*pi*f0*k/fs), goertzel_bin(x, f0, fs) == A*N.
inline std::complex<double> goertzel_bin(const std::vector<std::complex<float>>& x,
                                         double f, double fs) {
    std::complex<double> acc(0.0, 0.0);
    for (std::size_t i = 0; i < x.size(); ++i) {
        const double ph = 2.0 * kPi * f / fs * static_cast<double>(i);
        const std::complex<double> ref(std::cos(ph), -std::sin(ph));
        acc += std::complex<double>(x[i].real(), x[i].imag()) * ref;
    }
    return acc;
}

// Complex amplitude of a complex exponential at frequency `f` = |bin| / N.
inline double goertzel_amp(const std::vector<std::complex<float>>& x,
                           double f, double fs) {
    if (x.empty()) return 0.0;
    return std::abs(goertzel_bin(x, f, fs)) / static_cast<double>(x.size());
}

// Dominant frequency estimate (single-tone) from the first-order autocorrelation:
//   f = arg(sum_k x[k+1]*conj(x[k])) / (2*pi) * fs,  in [-fs/2, fs/2].
// Scale-invariant (phase only).
inline double dominant_freq_hz(const std::vector<std::complex<float>>& x, double fs) {
    if (x.size() < 2) return 0.0;
    std::complex<double> acc(0.0, 0.0);
    for (std::size_t k = 0; k + 1 < x.size(); ++k) {
        acc += std::complex<double>(x[k + 1].real(), x[k + 1].imag()) *
               std::complex<double>(x[k].real(), -x[k].imag());
    }
    if (std::abs(acc) < 1e-12) return 0.0;
    return std::arg(acc) / (2.0 * kPi) * fs;
}

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

// Convert interleaved int16 (12-bit ADC counts, AFTER iio_channel_convert) to
// complex<float> normalised to [-1, 1].  Full scale is 2^11 = 2048 -- NOT the
// legacy 32768 -- because the AD9364 is a 12-bit converter and
// iio_channel_convert returns the significant 12 bits (see
// contracts/rx_iq_format_contract.md).
inline std::vector<std::complex<float>> to_complex(const std::vector<std::int16_t>& iq) {
    std::vector<std::complex<float>> out(iq.size() / 2);
    for (std::size_t k = 0; k < out.size(); ++k) {
        out[k] = std::complex<float>(static_cast<float>(iq[k * 2 + 0]) / 2048.0f,
                                     static_cast<float>(iq[k * 2 + 1]) / 2048.0f);
    }
    return out;
}

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

// RMS of a complex sample vector (rotation-invariant magnitude RMS).
inline double rms(const std::vector<std::complex<float>>& x) {
    if (x.empty()) return 0.0;
    double s = 0.0;
    for (const auto& v : x) s += static_cast<double>(v.real()) * v.real() +
                                static_cast<double>(v.imag()) * v.imag();
    return std::sqrt(s / static_cast<double>(x.size()));
}

// Peak |int16| count across an interleaved I/Q buffer (saturation check).
inline int max_abs_iq(const std::vector<std::int16_t>& iq) {
    int m = 0;
    for (const std::int16_t v : iq) {
        const int a = v < 0 ? -v : v;
        if (a > m) m = a;
    }
    return m;
}

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
};

// Run the full self-TX/self-RX loopback and fill *pass/*detail.  The PlutoTx RAII
// guarantees the TX buffer is destroyed on every path (including prepare()
// failure or stream break); parameter restore is the caller's DeviceStateGuard.
// Detects the tone at BOTH +/-tone_hz (ratio_pos / ratio_neg) so a conjugate/IQ
// direction mismatch is REPORTED, not silently passed.  Never throws.
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
            const auto x = to_complex(iq);
            // Detect at BOTH signs: a conjugate/IQ-direction mismatch inverts the
            // tone's frequency, and we must surface that rather than hide it.
            const double ratio_pos = goertzel_ratio(x, spec.tone_hz, fs_dev);
            const double ratio_neg = goertzel_ratio(x, -spec.tone_hz, fs_dev);
            const double ratio = std::max(ratio_pos, ratio_neg);
            const int peak = max_abs_iq(iq);
            const double rms_val = rms(x);
            const double df = dominant_freq_hz(x, fs_dev);
            const bool no_sat = peak < pluto::kDacFullScale;   // 12-bit ADC full scale
            const bool tone_ok = ratio > 0.3;                   // tone dominates a bin
            const bool clean = !st.short_block && !st.interrupted &&
                               st.overflow == 0 && st.dropped == 0 &&
                               st.discontinuity == 0;
            p = tone_ok && no_sat && clean;

            d += " ratio_pos=" + std::to_string(ratio_pos);
            d += " ratio_neg=" + std::to_string(ratio_neg);
            d += " ratio=" + std::to_string(ratio);
            d += " peak=" + std::to_string(peak);
            d += " rms=" + std::to_string(rms_val);
            d += " dominant_freq_hz=" + std::to_string(df);
            d += " short=" + std::to_string(st.short_block ? 1 : 0);
            d += " interrupted=" + std::to_string(st.interrupted ? 1 : 0);
            d += " overflow=" + std::to_string(st.overflow);
            d += " drop=" + std::to_string(st.dropped);
            d += " disc=" + std::to_string(st.discontinuity);
            d += " timeouts=" + std::to_string(st.timeouts);
            if (!tone_ok) d += " (tone_not_detected)";
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
