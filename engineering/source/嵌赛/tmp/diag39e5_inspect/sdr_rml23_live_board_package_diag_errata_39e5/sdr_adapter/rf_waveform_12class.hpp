#pragma once

// rf_waveform_12class.hpp -- deterministic 12-class complex-baseband waveform
// generator (128 kS/s) + x20 polyphase upsampler (2.56 MS/s) for the Gate 10
// self-TX/self-RX self-test (task 39e5 UI v3 · M9).
//
// The synthesis reproduces the FROZEN training generator
//   ad_amr_data_v4_12class_robust/datasets/modulation_generator.py
// algorithm-for-algorithm (root-raised-cosine taps, constellation maps, FSK/FM
// continuous phase, GFSK Gaussian pulse, AM/WBFM band-limited message, OFDM
// block structure) -- see docs/TRAINING_SIGNAL_CONTRACT_AUDIT.md and
// docs/RF_SELF_TEST_CONTRACT.md.  The ONLY deviation is the RNG (std::mt19937_64
// with a fixed, documented seed scheme, per docs/WAVEFORM_CONTRACT.md section 4):
// the exact numpy PCG64 stream is intentionally NOT reproduced, only the
// statistical distributions.  Deterministic: same (class, seed) -> byte-identical
// output.
//
// Class index order == cat::target_12():
//   0 OOK, 1 4ASK, 2 AM-DSB, 3 WBFM, 4 2FSK, 5 GFSK, 6 BPSK, 7 QPSK,
//   8 8PSK, 9 16QAM, 10 64QAM, 11 OFDM.
//
// iCraft-free, libiio-free, header-only (except the upsampler, which reuses
// sdr::StreamResampler from resampler.cpp).  Every 1024-sample frame is
// RMS-normalised to 1.0 on the TX side (same rule as the training generator's
// _normalize_rms); this is the GENERATOR side, distinct from the forbidden
// per-frame RMS normalisation on the RX/model-input path.

#include "resampler.hpp"
#include "fir_coeffs.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <random>
#include <stdexcept>
#include <vector>

namespace sdr {

// Local pi (unique name: nco.hpp defines kPi, frame_analysis.hpp defines kPiF,
// both in namespace sdr).
constexpr double kPiW = 3.141592653589793238462643383279502884;

constexpr double kBaseSampleRate = 128000.0;   // model-domain sample rate
constexpr double kSymbolRate = 16000.0;        // symbol rate
constexpr int kSamplesPerSymbol = 8;           // sps
constexpr std::size_t kBaseFrameSamples = 1024; // samples per frame / record
constexpr double kRolloff = 0.35;              // RRC rolloff
constexpr int kSpanSymbols = 8;                // RRC span (symbols)
constexpr double kRrcGroupDelaySamples = 32.0; // (65-tap - 1) / 2

// Twelve-class order (== cat::target_12()).
enum WaveformClass {
    kWfOok = 0,
    kWf4Ask = 1,
    kWfAmDsb = 2,
    kWfWbfm = 3,
    kWf2Fsk = 4,
    kWfGfsk = 5,
    kWfBpsk = 6,
    kWfQpsk = 7,
    kWf8Psk = 8,
    kWf16Qam = 9,
    kWf64Qam = 10,
    kWfOfdm = 11,
    kWfClassCount = 12,
};

// --- deterministic RNG (statistically equivalent to numpy default_rng draws) --

class WaveRng {
public:
    explicit WaveRng(std::uint64_t seed) : mt_(seed) {}

    // Uniform double in [0, 1) (53-bit mantissa, matching the quality of
    // std::generate_canonical / numpy's uniform01).
    double uniform01() {
        return static_cast<double>(mt_() >> 11) * (1.0 / 9007199254740992.0);
    }

    double uniform(double a, double b) { return a + (b - a) * uniform01(); }

    // Integer in [lo, hi).
    int uniform_int(int lo, int hi) {
        if (hi <= lo) return lo;
        return lo + static_cast<int>(mt_() % static_cast<std::uint64_t>(hi - lo));
    }

    // Standard normal via Box-Muller (deterministic, cached spare).
    double standard_normal() {
        if (has_spare_) {
            has_spare_ = false;
            return spare_;
        }
        double u1 = uniform01();
        if (u1 <= 0.0) u1 = 1e-12;
        const double u2 = uniform01();
        const double r = std::sqrt(-2.0 * std::log(u1));
        const double theta = 2.0 * kPiW * u2;
        spare_ = r * std::cos(theta);
        has_spare_ = true;
        return r * std::sin(theta);
    }

private:
    std::mt19937_64 mt_;
    bool has_spare_ = false;
    double spare_ = 0.0;
};

inline std::uint64_t splitmix64(std::uint64_t x) {
    x += 0x9E3779B97F4A7C15ULL;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
    return x ^ (x >> 31);
}

// Per-class seed from a global seed, decoupled from golden/training sample ids.
inline std::uint64_t waveform_class_seed(std::uint64_t base, int cls) {
    return splitmix64(base ^ (static_cast<std::uint64_t>(cls) * 0x9E3779B97F4A7C15ULL));
}

// --- filter taps (matching modulation_generator.py) --------------------------

// root_raised_cosine_taps(sps, span, beta): unit-energy RRC, 65 taps at sps=8.
inline std::vector<double> rrc_taps(int sps, int span, double beta) {
    if (sps < 2 || span < 2) throw std::invalid_argument("rrc: sps/span >= 2");
    if (beta < 0.0 || beta > 1.0) throw std::invalid_argument("rrc: beta in [0,1]");
    const int count = span * sps;
    const int n = count + 1;
    std::vector<double> taps(static_cast<std::size_t>(n));
    const double center = static_cast<double>(count) / 2.0;
    for (int i = 0; i < n; ++i) {
        const double t = (static_cast<double>(i) - center) / static_cast<double>(sps);
        double v;
        if (std::fabs(t) < 1e-12) {
            v = 1.0 - beta + 4.0 * beta / kPiW;
        } else if (beta > 0.0 &&
                   std::fabs(std::fabs(t) - 1.0 / (4.0 * beta)) < 1e-9) {
            v = (beta / std::sqrt(2.0)) *
                ((1.0 + 2.0 / kPiW) * std::sin(kPiW / (4.0 * beta)) +
                 (1.0 - 2.0 / kPiW) * std::cos(kPiW / (4.0 * beta)));
        } else {
            const double num = std::sin(kPiW * t * (1.0 - beta)) +
                               4.0 * beta * t * std::cos(kPiW * t * (1.0 + beta));
            const double den = kPiW * t * (1.0 - std::pow(4.0 * beta * t, 2.0));
            v = num / den;
        }
        taps[static_cast<std::size_t>(i)] = v;
    }
    double e = 0.0;
    for (double v : taps) e += v * v;
    e = std::sqrt(e);
    for (double& v : taps) v /= e;
    return taps;
}

// scipy.signal.firwin(numtaps, cutoff_hz, fs=fs, window="hann", scale=True)
// equivalent: 2*fc*sinc(2*fc*n) * hann, DC-normalised to unit sum.
inline std::vector<double> firwin_lowpass_hann(int numtaps, double cutoff_hz, double fs) {
    if (numtaps < 1 || (numtaps % 2) == 0)
        throw std::invalid_argument("firwin: numtaps must be odd");
    if (!(cutoff_hz > 0.0 && cutoff_hz < fs / 2.0))
        throw std::invalid_argument("firwin: cutoff inside Nyquist");
    std::vector<double> h(static_cast<std::size_t>(numtaps));
    const double fc = cutoff_hz / (fs / 2.0);   // normalised (Nyquist = 1)
    const double center = (numtaps - 1) / 2.0;
    double sum = 0.0;
    for (int n = 0; n < numtaps; ++n) {
        const double x = static_cast<double>(n) - center;
        double v;
        if (std::fabs(x) < 1e-12) v = 2.0 * fc;
        else v = std::sin(2.0 * kPiW * fc * x) / (kPiW * x);
        const double w = 0.5 - 0.5 * std::cos(2.0 * kPiW * static_cast<double>(n) /
                                              static_cast<double>(numtaps - 1));
        h[static_cast<std::size_t>(n)] = v * w;
        sum += v * w;
    }
    for (double& v : h) v /= sum;
    return h;
}

// scipy.signal.windows.gaussian(M, std) (sym=True), raw (UNnormalised); the GFSK
// path divides by its sum exactly as the training generator does.
inline std::vector<double> gaussian_window(int M, double sigma) {
    if (M < 1) throw std::invalid_argument("gaussian_window: M >= 1");
    std::vector<double> w(static_cast<std::size_t>(M));
    const double center = (M - 1) / 2.0;
    for (int i = 0; i < M; ++i) {
        const double x = static_cast<double>(i) - center;
        w[static_cast<std::size_t>(i)] = std::exp(-0.5 * (x / sigma) * (x / sigma));
    }
    return w;
}

// --- radix-2 FFT / IFFT (for OFDM, matching numpy fft semantics) -------------

inline void fft_radix2(std::complex<double>* a, int n, int sign) {
    for (int i = 1, j = 0; i < n; ++i) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (int len = 2; len <= n; len <<= 1) {
        const double ang = static_cast<double>(sign) * 2.0 * kPiW / static_cast<double>(len);
        const std::complex<double> wlen(std::cos(ang), std::sin(ang));
        for (int i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            for (int k = 0; k < len / 2; ++k) {
                const std::complex<double> u = a[i + k];
                const std::complex<double> v = a[i + k + len / 2] * w;
                a[i + k] = u + v;
                a[i + k + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

// ifft(x) = conj(fft(conj(x))) / N (matches numpy np.fft.ifft).
inline void ifft_radix2(std::complex<double>* a, int n) {
    for (int i = 0; i < n; ++i) a[i] = std::conj(a[i]);
    fft_radix2(a, n, -1);
    for (int i = 0; i < n; ++i) a[i] = std::conj(a[i]) / static_cast<double>(n);
}

// --- per-class nominal analog parameters (drawn from the seeded RNG) ---------

struct WaveformParams {
    double am_index = 0.6;        // AM-DSB modulation index [0.35, 0.9]
    double am_bandwidth = 5000.0; // AM-DSB message BW [2500, 7000] Hz
    double fm_deviation = 16000.0;// WBFM deviation [10000, 22000] Hz
    double fm_bandwidth = 5000.0; // WBFM message BW [2500, 7000] Hz
    double gfsk_bt = 0.5;         // GFSK BT [0.3, 0.7]
    double gfsk_mod_index = 0.5;  // GFSK modulation index [0.45, 0.55]
};

// --- the generator -----------------------------------------------------------

class RfWaveform12Class {
public:
    RfWaveform12Class(int cls, std::uint64_t seed)
        : cls_(cls), rng_(waveform_class_seed(seed, cls)) {
        if (cls < 0 || cls >= kWfClassCount)
            throw std::invalid_argument("RfWaveform12Class: cls out of range");

        // Draw per-class nominal analog parameters from the seeded RNG (fixed for
        // the whole class stream; NEW_TEST_PARAMETER -- training randomises these
        // per record, the self-test holds them fixed for a stable chain test).
        params_.am_index = rng_.uniform(0.35, 0.9);
        params_.am_bandwidth = rng_.uniform(2500.0, 7000.0);
        params_.fm_deviation = rng_.uniform(10000.0, 22000.0);
        params_.fm_bandwidth = rng_.uniform(2500.0, 7000.0);
        params_.gfsk_bt = rng_.uniform(0.3, 0.7);
        params_.gfsk_mod_index = rng_.uniform(0.45, 0.55);

        // Precompute class-specific taps / constellation / phase / warmup.
        switch (cls_) {
            case kWfOok: case kWf4Ask: case kWfBpsk: case kWfQpsk:
            case kWf8Psk: case kWf16Qam: case kWf64Qam:
                points_ = constellation(cls_);
                rrc_ = rrc_taps(kSamplesPerSymbol, kSpanSymbols, kRolloff);
                m0_ = static_cast<std::uint64_t>(kSpanSymbols * kSamplesPerSymbol);
                break;
            case kWf2Fsk:
                points_ = {std::complex<double>(1.0, 0.0),
                           std::complex<double>(-1.0, 0.0)};
                phase_ = 0.0;  // 2FSK training path has no random initial phase
                break;
            case kWfGfsk: {
                points_ = {std::complex<double>(1.0, 0.0),
                           std::complex<double>(-1.0, 0.0)};
                const int tap_count = 2 * 4 * kSamplesPerSymbol + 1;  // span 4 -> 65
                const double sigma = std::max(static_cast<double>(kSamplesPerSymbol) /
                                                  (2.0 * kPiW * params_.gfsk_bt),
                                              1.0);
                gauss_ = gaussian_window(tap_count, sigma);
                double s = 0.0;
                for (double v : gauss_) s += v;
                for (double& v : gauss_) v /= s;
                phase_ = rng_.uniform(-kPiW, kPiW);
                m0_ = 4 * kSamplesPerSymbol;  // Gaussian centre warmup (32 samples)
                break;
            }
            case kWfAmDsb:
                msg_fir_ = firwin_lowpass_hann(129, params_.am_bandwidth, kBaseSampleRate);
                break;
            case kWfWbfm:
                msg_fir_ = firwin_lowpass_hann(129, params_.fm_bandwidth, kBaseSampleRate);
                phase_ = rng_.uniform(-kPiW, kPiW);
                break;
            case kWfOfdm:
                break;
            default:
                throw std::invalid_argument("RfWaveform12Class: unknown class");
        }
    }

    int cls() const { return cls_; }
    const WaveformParams& params() const { return params_; }
    std::uint64_t samples_generated() const { return generated_; }

    // Generate exactly n complex samples (n must be a multiple of
    // kBaseFrameSamples); each 1024-sample frame is RMS-normalised to 1.0.
    // Continuous across calls (phase / symbol stream / OFDM block position all
    // persist).  Throws on a zero-power frame (fail-closed).
    void generate(std::complex<float>* out, std::size_t n) {
        if ((n % kBaseFrameSamples) != 0)
            throw std::invalid_argument("RfWaveform12Class: n must be a multiple of 1024");
        generate_raw(out, n);
        for (std::size_t f = 0; f < n / kBaseFrameSamples; ++f)
            normalize_rms(out + f * kBaseFrameSamples, kBaseFrameSamples, 1.0);
        generated_ += n;
    }

private:
    void generate_raw(std::complex<float>* out, std::size_t n) {
        switch (cls_) {
            case kWfOok: case kWf4Ask: case kWfBpsk: case kWfQpsk:
            case kWf8Psk: case kWf16Qam: case kWf64Qam:
                generate_linear(out, n); break;
            case kWf2Fsk: generate_fsk(out, n); break;
            case kWfGfsk: generate_gfsk(out, n); break;
            case kWfAmDsb: generate_am(out, n); break;
            case kWfWbfm: generate_wbfm(out, n); break;
            case kWfOfdm: generate_ofdm(out, n); break;
            default: throw std::logic_error("RfWaveform12Class: bad class");
        }
    }

    void generate_linear(std::complex<float>* out, std::size_t n) {
        const std::size_t last_sym = (m0_ + n - 1) / kSamplesPerSymbol + 1;
        ensure_symbols(last_sym);
        const int ntaps = static_cast<int>(rrc_.size());  // 65
        for (std::size_t i = 0; i < n; ++i) {
            const std::uint64_t m = m0_ + i;
            const int r = static_cast<int>(m % kSamplesPerSymbol);
            double re = 0.0, im = 0.0;
            for (int t = r; t < ntaps; t += kSamplesPerSymbol) {
                const std::int64_t si =
                    (static_cast<std::int64_t>(m) - static_cast<std::int64_t>(t)) /
                    kSamplesPerSymbol;
                if (si >= 0 && si < static_cast<std::int64_t>(symbols_.size())) {
                    re += rrc_[static_cast<std::size_t>(t)] * symbols_[static_cast<std::size_t>(si)].real();
                    im += rrc_[static_cast<std::size_t>(t)] * symbols_[static_cast<std::size_t>(si)].imag();
                }
            }
            out[i] = std::complex<float>(static_cast<float>(re), static_cast<float>(im));
        }
        m0_ += n;
    }

    void generate_fsk(std::complex<float>* out, std::size_t n) {
        ensure_symbols((m0_ + n - 1) / kSamplesPerSymbol + 1);
        for (std::size_t i = 0; i < n; ++i) {
            const std::uint64_t m = m0_ + i;
            const double sym = symbols_[static_cast<std::size_t>(m / kSamplesPerSymbol)].real();
            phase_ += 2.0 * kPiW * (sym * 8000.0) / kBaseSampleRate;
            out[i] = std::complex<float>(static_cast<float>(std::cos(phase_)),
                                         static_cast<float>(std::sin(phase_)));
        }
        m0_ += n;
    }

    void generate_gfsk(std::complex<float>* out, std::size_t n) {
        const int ntaps = static_cast<int>(gauss_.size());   // 65
        const int center = (ntaps - 1) / 2;                  // 32
        ensure_symbols((m0_ + n - 1 + center) / kSamplesPerSymbol + 1);
        for (std::size_t i = 0; i < n; ++i) {
            const std::int64_t j = static_cast<std::int64_t>(m0_ + i);
            double shaped = 0.0;
            for (int t = 0; t < ntaps; ++t) {
                const std::int64_t k = j + center - t;  // nrz index
                if (k >= 0) {
                    const std::int64_t si = k / kSamplesPerSymbol;
                    if (si < static_cast<std::int64_t>(symbols_.size()))
                        shaped += gauss_[static_cast<std::size_t>(t)] *
                                  symbols_[static_cast<std::size_t>(si)].real();
                }
            }
            const double freq = shaped * params_.gfsk_mod_index * 8000.0;
            phase_ += 2.0 * kPiW * freq / kBaseSampleRate;
            out[i] = std::complex<float>(static_cast<float>(std::cos(phase_)),
                                         static_cast<float>(std::sin(phase_)));
        }
        m0_ += n;
    }

    void generate_am(std::complex<float>* out, std::size_t n) {
        for (std::size_t f = 0; f < n / kBaseFrameSamples; ++f) {
            const std::vector<double> msg = bandlimited_message(kBaseFrameSamples);
            for (std::size_t k = 0; k < kBaseFrameSamples; ++k) {
                const double v = 1.0 + params_.am_index * msg[k];
                out[f * kBaseFrameSamples + k] =
                    std::complex<float>(static_cast<float>(v), 0.0f);
            }
        }
    }

    void generate_wbfm(std::complex<float>* out, std::size_t n) {
        for (std::size_t f = 0; f < n / kBaseFrameSamples; ++f) {
            const std::vector<double> msg = bandlimited_message(kBaseFrameSamples);
            for (std::size_t k = 0; k < kBaseFrameSamples; ++k) {
                out[f * kBaseFrameSamples + k] =
                    std::complex<float>(static_cast<float>(std::cos(phase_)),
                                        static_cast<float>(std::sin(phase_)));
                phase_ += 2.0 * kPiW * params_.fm_deviation * msg[k] / kBaseSampleRate;
            }
        }
    }

    void generate_ofdm(std::complex<float>* out, std::size_t n) {
        while (pending_.size() < n) ofdm_append_block();
        for (std::size_t i = 0; i < n; ++i) out[i] = pending_[i];
        pending_.erase(pending_.begin(), pending_.begin() + static_cast<long>(n));
    }

    void ofdm_append_block() {
        const int fft = 256, cp = 64, active = 48;
        const int half = active / 2;  // 24
        std::vector<std::complex<double>> freq(static_cast<std::size_t>(fft));
        // active bins: [-24..-1] and [1..24] (mod 256), DC and both edges empty.
        for (int b = 1; b <= half; ++b) {
            const int neg = (fft - b) % fft;  // -b mod 256
            freq[static_cast<std::size_t>(neg)] = qpsk_point(rng_.uniform_int(0, 4));
            freq[static_cast<std::size_t>(b)] = qpsk_point(rng_.uniform_int(0, 4));
        }
        ifft_radix2(freq.data(), fft);
        for (auto& v : freq) v *= std::sqrt(static_cast<double>(fft));
        // Prepend the last `cp` samples (cyclic prefix) -> block of 320.
        for (int k = fft - cp; k < fft; ++k)
            pending_.push_back(std::complex<float>(static_cast<float>(freq[static_cast<std::size_t>(k)].real()),
                                                   static_cast<float>(freq[static_cast<std::size_t>(k)].imag())));
        for (int k = 0; k < fft; ++k)
            pending_.push_back(std::complex<float>(static_cast<float>(freq[static_cast<std::size_t>(k)].real()),
                                                   static_cast<float>(freq[static_cast<std::size_t>(k)].imag())));
    }

    void ensure_symbols(std::size_t count) {
        while (symbols_.size() < count) {
            symbols_.push_back(points_[static_cast<std::size_t>(
                rng_.uniform_int(0, static_cast<int>(points_.size())))]);
        }
    }

    // _bandlimited_message(): zero-mean, unit-peak real message (guard 256,
    // causal 129-tap Hann lowpass, mean-remove, peak-normalise) -- identical to
    // the training generator.  The FIR is precomputed in the constructor from the
    // class's message bandwidth, so no bandwidth parameter is needed here.
    std::vector<double> bandlimited_message(std::size_t length) {
        const int guard = 256;
        const std::size_t total = length + 2 * static_cast<std::size_t>(guard);
        std::vector<double> white(total);
        for (double& w : white) w = rng_.standard_normal();
        std::vector<double> msg(length);
        const int ntaps = static_cast<int>(msg_fir_.size());  // 129
        for (std::size_t i = 0; i < length; ++i) {
            const int n = guard + static_cast<int>(i);
            double y = 0.0;
            for (int k = 0; k < ntaps; ++k)
                y += msg_fir_[static_cast<std::size_t>(k)] *
                     white[static_cast<std::size_t>(n - k)];
            msg[i] = y;
        }
        double mean = 0.0;
        for (double v : msg) mean += v;
        mean /= static_cast<double>(length);
        for (double& v : msg) v -= mean;
        double peak = 0.0;
        for (double v : msg) peak = std::max(peak, std::fabs(v));
        if (peak <= 1e-12)
            throw std::runtime_error("RfWaveform12Class: zero-amplitude analog message");
        for (double& v : msg) v /= peak;
        return msg;
    }

    static void normalize_rms(std::complex<float>* x, std::size_t n, double amplitude) {
        double s = 0.0;
        for (std::size_t k = 0; k < n; ++k)
            s += static_cast<double>(x[k].real()) * x[k].real() +
                 static_cast<double>(x[k].imag()) * x[k].imag();
        const double rms = std::sqrt(s / static_cast<double>(n));
        if (rms <= 1e-12)
            throw std::runtime_error("RfWaveform12Class: zero-power frame");
        const double g = amplitude / rms;
        for (std::size_t k = 0; k < n; ++k)
            x[k] *= static_cast<float>(g);
    }

    static std::complex<double> qpsk_point(int k) {
        const double r = 1.0 / std::sqrt(2.0);
        switch (k & 3) {
            case 0: return {r, r};
            case 1: return {-r, r};
            case 2: return {-r, -r};
            default: return {r, -r};
        }
    }

    static std::vector<double> gray_pam_levels(int bits) {
        const int size = 1 << bits;
        std::vector<double> result(static_cast<std::size_t>(size));
        for (int b = 0; b < size; ++b) {
            const int gray = b ^ (b >> 1);
            result[static_cast<std::size_t>(gray)] =
                static_cast<double>(2 * b - (size - 1));
        }
        return result;
    }

    static std::vector<std::complex<double>> constellation(int cls) {
        const double r5 = std::sqrt(5.0);
        switch (cls) {
            case kWfOok: return {{0.0, 0.0}, {std::sqrt(2.0), 0.0}};
            case kWf4Ask: return {{-3.0 / r5, 0.0}, {-1.0 / r5, 0.0},
                                  {1.0 / r5, 0.0}, {3.0 / r5, 0.0}};
            case kWfBpsk: return {{1.0, 0.0}, {-1.0, 0.0}};
            case kWfQpsk: return {{1.0 / std::sqrt(2.0), 1.0 / std::sqrt(2.0)},
                                  {-1.0 / std::sqrt(2.0), 1.0 / std::sqrt(2.0)},
                                  {-1.0 / std::sqrt(2.0), -1.0 / std::sqrt(2.0)},
                                  {1.0 / std::sqrt(2.0), -1.0 / std::sqrt(2.0)}};
            case kWf8Psk: {
                std::vector<std::complex<double>> p(8);
                for (int k = 0; k < 8; ++k) {
                    const double a = 2.0 * kPiW * static_cast<double>(k) / 8.0;
                    p[static_cast<std::size_t>(k)] = {std::cos(a), std::sin(a)};
                }
                return p;
            }
            case kWf16Qam: return qam_constellation(2);
            case kWf64Qam: return qam_constellation(3);
            default:
                throw std::invalid_argument("constellation: not a linear class");
        }
    }

    static std::vector<std::complex<double>> qam_constellation(int bits) {
        const std::vector<double> levels = gray_pam_levels(bits);
        const int size = 1 << bits;
        std::vector<std::complex<double>> pts;
        pts.reserve(static_cast<std::size_t>(size * size));
        for (double q : levels)
            for (double i : levels)
                pts.push_back(std::complex<double>(i, q));
        double e = 0.0;
        for (const auto& p : pts) e += std::norm(p);
        e = std::sqrt(e / static_cast<double>(pts.size()));
        for (auto& p : pts) p /= e;
        return pts;
    }

    int cls_;
    WaveformParams params_;
    WaveRng rng_;
    double phase_ = 0.0;
    std::uint64_t m0_ = 0;   // global sample index (linear/FSK/GFSK)
    std::vector<std::complex<double>> symbols_;
    std::vector<double> rrc_;
    std::vector<double> gauss_;
    std::vector<double> msg_fir_;
    std::vector<std::complex<double>> points_;
    std::deque<std::complex<float>> pending_;
    std::uint64_t generated_ = 0;
};

// --- x20 upsampler (128 kS/s -> 2.56 MS/s) -----------------------------------

// Reuses the verified 72.8 dB decimation lowpass kFir_2p56M (DC gain 1) as the
// interpolation prototype, scaled by 20 so the x20 polyphase interpolation has
// unit passband gain (a baseband tone's RMS is preserved).  601 -> 600 taps so
// the length is a multiple of up=20 (the dropped last tap is 1.3e-4, negligible).
// NEW_TEST_PARAMETER: the training pipeline has no upsampling step.
inline StreamResampler make_20x_upsampler() {
    std::vector<double> fir(600);
    for (std::size_t i = 0; i < 600; ++i) fir[i] = 20.0 * kFir_2p56M[i];
    return StreamResampler(20, 1, fir);
}

// Build the interleaved int16 cyclic-TX waveform for class `cls`: generate
// `frames` baseband frames (each RMS-normalised to 1.0), upsample x20 to 2.56 MS/s,
// then scale so the upsampled PEAK equals `peak_limit` DAC counts (no clipping).
// out_iq = [I0,Q0,I1,Q1,...] with |I|,|Q| <= peak_limit.  On success fills
// `*tx_peak` (the achieved peak in counts, ~= peak_limit) and `*tx_rms` (the RMS in
// counts, class-dependent because of PAPR) when non-null.  Throws on a zero peak.
inline void build_tx_waveform(int cls, std::uint64_t seed, std::size_t frames,
                              double peak_limit, std::vector<std::int16_t>& out_iq,
                              double* tx_peak = nullptr, double* tx_rms = nullptr) {
    if (frames == 0) throw std::invalid_argument("build_tx_waveform: frames >= 1");
    RfWaveform12Class gen(cls, seed);
    const std::size_t base_n = frames * kBaseFrameSamples;
    std::vector<std::complex<float>> base(base_n);
    gen.generate(base.data(), base_n);

    StreamResampler up = make_20x_upsampler();
    up.push(base.data(), base_n);
    const std::size_t out_n = up.available();
    if (out_n == 0) throw std::runtime_error("build_tx_waveform: no upsampled output");
    std::vector<std::complex<float>> upsampled(out_n);
    up.pull(upsampled.data(), out_n);

    double peak = 0.0;
    for (const auto& v : upsampled)
        peak = std::max(peak, std::sqrt(static_cast<double>(std::norm(v))));
    if (peak <= 1e-12) throw std::runtime_error("build_tx_waveform: zero peak");
    const double scale = peak_limit / peak;

    out_iq.resize(out_n * 2);
    double rms_sq = 0.0;
    for (std::size_t k = 0; k < out_n; ++k) {
        const double re = static_cast<double>(upsampled[k].real()) * scale;
        const double im = static_cast<double>(upsampled[k].imag()) * scale;
        out_iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(re));
        out_iq[k * 2 + 1] = static_cast<std::int16_t>(std::llround(im));
        rms_sq += re * re + im * im;
    }
    if (tx_peak) *tx_peak = peak_limit;
    if (tx_rms) *tx_rms = std::sqrt(rms_sq / static_cast<double>(out_n));
}

}  // namespace sdr
