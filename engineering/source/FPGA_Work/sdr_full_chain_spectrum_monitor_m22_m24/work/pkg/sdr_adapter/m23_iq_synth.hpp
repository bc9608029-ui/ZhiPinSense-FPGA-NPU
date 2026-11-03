#pragma once

// m23_iq_synth.hpp -- deterministic synthetic IQ for the M23 P0 estimator tests.
//
// The milestone requires synthetic tests with KNOWN center frequency, bandwidth,
// SNR and CFO so the parameter estimators can be checked for NUMERIC ERROR (not
// just "PASS").  This header produces count-domain complex<float> signals whose
// ground truth is carried alongside the samples, so a test can print
//   estimated - truth
// per quantity.
//
// Signal models (all complex baseband, sample rate fs):
//   tone     A*e^{j*2*pi*(f_ref+cfo)*k/fs}          -> CFO order 1, centre freq
//   BPSK     s_k*e^{j*2*pi*(f_ref+cfo)*k/fs}, s_k=+-1  -> CFO order 2 (x^2)
//   QPSK     s_k*e^{j*2*pi*(f_ref+cfo)*k/fs}, s_k in QPSK -> CFO order 4 (x^4)
//   two-tone A*e^{j2*pi*f1*k/fs} + A*e^{j2*pi*f2*k/fs}  -> occupied bandwidth
//
// BPSK/QPSK use SQUARE pulses (symbol held over fs/symbol_rate samples); this is
// sufficient because the CFO estimator strips the modulation by raising x to the
// modulation order (s_k^2 = 1, s_k^4 = -1), so no pulse shaping is required and
// the nonlinearity output is a clean line at M*(f_ref+cfo).
//
// Amplitude is in COUNT domain (12-bit, full scale 2048), matching dsp_measure.hpp
// and the frozen receiver path.  The CFO estimator is scale-invariant, but
// power/RMS are not, so the truth carries rms_counts and power_dbfs.
//
// Deterministic: same seed -> byte-identical samples.  The RNG is self-contained
// (std::mt19937_64 + Box-Muller), independent of sdr::WaveRng.
//
// iCraft-free, header-only.  Independent of rf_waveform_12class.hpp (no 12-class
// model semantics, no training-generator parity requirements).

#include <cmath>
#include <complex>
#include <cstddef>
#include <cstdint>
#include <random>
#include <vector>

namespace m23 {

// Local pi (unique name; m23_cfo.hpp already owns kPi in this namespace).
constexpr double kPiSynth = 3.141592653589793238462643383279502884;

// Host full-scale counts (matches dsp_measure.hpp / rx_iq_format_contract.md §3).
constexpr double kFullScaleCounts = 2048.0;

// --- deterministic RNG -------------------------------------------------------

class SynthRng {
public:
    explicit SynthRng(std::uint64_t seed) : mt_(seed) {}

    double uniform01() {
        return static_cast<double>(mt_() >> 11) * (1.0 / 9007199254740992.0);
    }

    double uniform(double a, double b) { return a + (b - a) * uniform01(); }

    int uniform_int(int lo, int hi) {
        if (hi <= lo) return lo;
        return lo + static_cast<int>(mt_() % static_cast<std::uint64_t>(hi - lo));
    }

    double standard_normal() {
        if (has_spare_) {
            has_spare_ = false;
            return spare_;
        }
        double u1 = uniform01();
        if (u1 <= 0.0) u1 = 1e-12;
        const double u2 = uniform01();
        const double r = std::sqrt(-2.0 * std::log(u1));
        const double th = 2.0 * kPiSynth * u2;
        spare_ = r * std::cos(th);
        has_spare_ = true;
        return r * std::sin(th);
    }

private:
    std::mt19937_64 mt_;
    bool has_spare_ = false;
    double spare_ = 0.0;
};

// --- primitives --------------------------------------------------------------

// Per-dimension AWGN standard deviation that yields the target amplitude-ratio
// SNR against a signal of RMS `signal_rms` (counts).  For complex noise each
// dimension is gaussian(sigma), so |n| has RMS sigma*sqrt(2):
//   snr_db = 20*log10(signal_rms / (sigma*sqrt(2))).
inline double noise_sigma_for_snr(double signal_rms, double snr_db) {
    if (!(snr_db > 0.0)) return 0.0;  // <= 0 or NaN -> no noise
    const double noise_rms = signal_rms * std::pow(10.0, -snr_db / 20.0);
    return noise_rms / std::sqrt(2.0);
}

inline void add_awgn(std::complex<float>* out, std::size_t n, SynthRng& rng,
                     double sigma) {
    for (std::size_t k = 0; k < n; ++k) {
        out[k] += std::complex<float>(static_cast<float>(sigma * rng.standard_normal()),
                                      static_cast<float>(sigma * rng.standard_normal()));
    }
}

inline void synth_tone(std::complex<float>* out, std::size_t n, double fs,
                       double f_hz, double amp, double phase0 = 0.0) {
    for (std::size_t k = 0; k < n; ++k) {
        const double ph = phase0 + 2.0 * kPiSynth * f_hz / fs * static_cast<double>(k);
        out[k] = std::complex<float>(static_cast<float>(amp * std::cos(ph)),
                                     static_cast<float>(amp * std::sin(ph)));
    }
}

// --- ground truth + buffer ---------------------------------------------------

struct SynthSignal {
    std::vector<std::complex<float>> iq;

    double fs = 0.0;              // sample rate
    double carrier_hz = 0.0;      // centre / reference carrier (baseband)
    double cfo_hz = 0.0;          // residual offset added on top of carrier
    double occupied_bw_hz = 0.0;  // nominal occupied bandwidth (two-tone span)
    double snr_db = 0.0;          // target SNR (<= 0 means no noise added)
    double rms_counts = 0.0;      // signal-only RMS (before AWGN)
    double power_dbfs = 0.0;      // 20*log10(rms_counts / 2048), signal-only
};

// Shared tail: add optional AWGN and record the truth.
inline SynthSignal finish_synth(std::vector<std::complex<float>> iq, double fs,
                                double carrier_hz, double cfo_hz,
                                double occupied_bw_hz, double snr_db,
                                double rms_counts, std::uint64_t seed) {
    SynthSignal s;
    s.fs = fs;
    s.carrier_hz = carrier_hz;
    s.cfo_hz = cfo_hz;
    s.occupied_bw_hz = occupied_bw_hz;
    s.snr_db = snr_db;
    s.rms_counts = rms_counts;
    s.power_dbfs = (rms_counts > 0.0)
                       ? 20.0 * std::log10(rms_counts / kFullScaleCounts)
                       : -200.0;
    const double sigma = noise_sigma_for_snr(rms_counts, snr_db);
    if (sigma > 0.0) {
        SynthRng rng(seed ^ 0x9E3779B97F4A7C15ULL);
        add_awgn(iq.data(), iq.size(), rng, sigma);
    }
    s.iq = std::move(iq);
    return s;
}

// --- makers ------------------------------------------------------------------

// Pure tone at f = carrier + cfo.  CFO is estimated with order 1.
inline SynthSignal make_tone(std::size_t n, double fs, double carrier_hz,
                             double cfo_hz, double amp, double snr_db,
                             std::uint64_t seed) {
    std::vector<std::complex<float>> iq(n);
    synth_tone(iq.data(), n, fs, carrier_hz + cfo_hz, amp);
    return finish_synth(std::move(iq), fs, carrier_hz, cfo_hz, 0.0, snr_db, amp,
                        seed);
}

// BPSK square-pulse stream on carrier + cfo; RMS == amp (symbols are +-amp).
// CFO is estimated with order 2 (x^2 collapses the +-1 symbols to +1).
inline SynthSignal make_bpsk(std::size_t n, double fs, double carrier_hz,
                             double cfo_hz, double symbol_rate_hz, double amp,
                             double snr_db, std::uint64_t seed) {
    SynthRng rng(seed);
    const double f_hz = carrier_hz + cfo_hz;
    const double sps = fs / symbol_rate_hz;
    const std::size_t nsym = static_cast<std::size_t>(std::ceil(n / sps)) + 1;
    std::vector<int> bits(nsym);
    for (auto& b : bits) b = (rng.uniform_int(0, 2) == 0) ? 1 : -1;
    std::vector<std::complex<float>> iq(n);
    for (std::size_t k = 0; k < n; ++k) {
        const int s = bits[static_cast<std::size_t>(k / sps)];
        const double ph = 2.0 * kPiSynth * f_hz / fs * static_cast<double>(k);
        iq[k] = std::complex<float>(static_cast<float>(s * amp * std::cos(ph)),
                                    static_cast<float>(s * amp * std::sin(ph)));
    }
    return finish_synth(std::move(iq), fs, carrier_hz, cfo_hz, 0.0, snr_db, amp,
                        seed);
}

// QPSK square-pulse stream on carrier + cfo; RMS == amp.  CFO is estimated with
// order 4 (x^4 collapses every QPSK symbol to -1).
inline SynthSignal make_qpsk(std::size_t n, double fs, double carrier_hz,
                             double cfo_hz, double symbol_rate_hz, double amp,
                             double snr_db, std::uint64_t seed) {
    SynthRng rng(seed);
    const double f_hz = carrier_hz + cfo_hz;
    const double sps = fs / symbol_rate_hz;
    const std::size_t nsym = static_cast<std::size_t>(std::ceil(n / sps)) + 1;
    const double r = 1.0 / std::sqrt(2.0);
    std::vector<int> syms(nsym);
    for (auto& s : syms) s = rng.uniform_int(0, 4);
    std::vector<std::complex<float>> iq(n);
    for (std::size_t k = 0; k < n; ++k) {
        const int s = syms[static_cast<std::size_t>(k / sps)];
        double re, im;
        switch (s & 3) {
            case 0: re = r;  im = r;  break;
            case 1: re = -r; im = r;  break;
            case 2: re = -r; im = -r; break;
            default: re = r; im = -r; break;
        }
        const double ph = 2.0 * kPiSynth * f_hz / fs * static_cast<double>(k);
        const std::complex<float> c(static_cast<float>(amp * std::cos(ph)),
                                    static_cast<float>(amp * std::sin(ph)));
        iq[k] = c * std::complex<float>(static_cast<float>(re),
                                        static_cast<float>(im));
    }
    // Signal-only RMS == amp (unit-norm QPSK symbols).
    return finish_synth(std::move(iq), fs, carrier_hz, cfo_hz, 0.0, snr_db, amp,
                        seed);
}

// Two equal tones at f1 = carrier - bw/2 and f2 = carrier + bw/2.  Each has
// amplitude `amp`; the combined signal-only RMS is amp*sqrt(2).  occupied_bw_hz
// truth is the exact span |f2 - f1| (the estimator adds one bin width).
inline SynthSignal make_two_tone(std::size_t n, double fs, double carrier_hz,
                                 double bw_hz, double amp, double snr_db,
                                 std::uint64_t seed) {
    const double f1 = carrier_hz - bw_hz / 2.0;
    const double f2 = carrier_hz + bw_hz / 2.0;
    std::vector<std::complex<float>> iq(n);
    synth_tone(iq.data(), n, fs, f1, amp);
    std::vector<std::complex<float>> y(n);
    synth_tone(y.data(), n, fs, f2, amp);
    for (std::size_t k = 0; k < n; ++k) iq[k] += y[k];
    const double rms = amp * std::sqrt(2.0);
    return finish_synth(std::move(iq), fs, carrier_hz, 0.0, bw_hz, snr_db, rms,
                        seed);
}

}  // namespace m23
