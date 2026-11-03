#pragma once

// dsp_measure.hpp -- lightweight per-frame DSP parameter measurement (39e5 UI v3
// M3).  Produces the raw-domain, spectrum-domain and model-domain measurements
// consumed by signal_presence (M1), auto_level_control (M2), the PARAMETERS UI
// page (M5) and the ResultFrame measurements field (M4).
//
// Pure logic, header-only, iCraft-free.  One 1024-point radix-2 FFT per frame is
// the only non-trivial cost; everything else is single-pass statistics.  The FFT
// complements frame_analysis.hpp (which does single-tone Goertzel / dominant
// frequency); this file supplies the FULL-spectrum quantities (noise floor, peak
// prominence, occupied bandwidth, spectral centroid, SNR) those cannot.
//
// Input domain: complex samples in RAW COUNT domain (12-bit, host full-scale
// 2048).  The model-domain RMS is derived here as count/2048 * receiver_scale,
// matching rx_iq_format_contract.md §3 and receiver_scale.hpp.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace sdr {

// Distinct spelling to avoid colliding with frame_analysis.hpp's kPiF and
// nco.hpp's kPi when these headers are pulled into one TU.
constexpr double kPiMeasure = 3.141592653589793238462643383279502884;

// In-place iterative radix-2 complex FFT (forward).  n must be a power of two.
inline void fft_radix2(std::complex<double>* a, std::size_t n) {
    for (std::size_t i = 1, j = 0; i < n; ++i) {
        std::size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (std::size_t len = 2; len <= n; len <<= 1) {
        const double ang = 2.0 * kPiMeasure / static_cast<double>(len);
        // Negative exponent = forward DFT (matches frame_analysis.hpp's Goertzel),
        // so a positive-frequency tone peaks at its positive FFT bin.
        const std::complex<double> wlen(std::cos(ang), -std::sin(ang));
        for (std::size_t i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            for (std::size_t j = 0; j < len / 2; ++j) {
                const std::complex<double> u = a[i + j];
                const std::complex<double> v = a[i + j + len / 2] * w;
                a[i + j] = u + v;
                a[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

struct DspMeasureConfig {
    double sample_rate_hz = 128000.0;   // post-decimation model-domain sample rate
    float receiver_scale = 1.0f;        // frozen receiver_scale (default 1.0)
    double full_scale_counts = 2048.0;  // 12-bit host full scale
    double clip_level_counts = 2048.0;  // |sample| >= this counts as a clip
    double noise_percentile = 0.5;      // PSD percentile used as the noise floor
    double occupied_threshold_db = 10.0;// occupied bin = > noise floor + this many dB
    double center_hz = 0.0;             // RF center frequency for display labelling
};

struct FrameMeasurements {
    // raw count domain
    double rms_counts = 0.0;
    double peak_counts = 0.0;
    double papr_db = 0.0;
    double clip_ratio = 0.0;
    // dBFS
    double power_dbfs = 0.0;         // 20*log10(rms_counts / full_scale)
    // spectrum domain
    double noise_floor_dbfs = 0.0;   // dBFS of the estimated noise floor
    double psd_peak_prominence_db = 0.0;  // peak bin minus noise floor
    double snr_est_db = 0.0;         // (signal power) / (noise power) in dB
    int occupied_bins = 0;           // bins above noise floor + threshold
    double spectral_centroid_hz = 0.0;
    double occupied_bw_hz = 0.0;     // (max-min occupied bin) span in Hz
    // model domain
    double model_rms = 0.0;          // rms_counts / full_scale * receiver_scale
    bool nan_inf = false;            // any NaN/Inf in the input
    bool valid = true;               // false on empty input
    // display spectrum (fix10class24-waterfall1).  Derived from the SAME 1024-pt
    // FFT power above (no second FFT): fftshift 1024 -> 256 bins of 4 (group MAX),
    // then dBFS x4 quantised.  Relative dBFS/bin; not calibrated W/Hz.
    bool spectrum_valid = false;
    int spectrum_fft_length = 1024;
    int spectrum_bin_count = 256;
    int spectrum_dbfs_x4[256] = {};   // dBFS * 4, integer [-480,0] = [-120,0] dBFS
    double spectrum_sample_rate_hz = 0.0;
    double spectrum_center_hz = 0.0;
};

// Reusable spectrum scratch buffers (M22 buffer-preallocation).  A long-running
// producer passes one of these per frame so the three 1024-element temporary
// vectors (FFT complex, power, sorted copy) are allocated once and reused, not
// re-malloc'd every frame.  `resize` only reallocates when growing, so after the
// first frame the scratch is allocation-stable.
struct MeasureScratch {
    std::vector<std::complex<double>> x;
    std::vector<double> power;
    std::vector<double> sorted;
};

class DspMeasure {
public:
    explicit DspMeasure(const DspMeasureConfig& c = {}) : cfg_(c) {}

    const DspMeasureConfig& config() const { return cfg_; }

    // One-shot measure (allocates a fresh scratch).  Kept for the host tests and
    // single-frame callers; the hot path uses measure_into() instead.
    FrameMeasurements measure(const std::complex<float>* iq, std::size_t n) const {
        MeasureScratch scratch;
        return measure_into(iq, n, scratch);
    }

    // Allocation-reuse measure: identical result to measure(), but writes the
    // spectrum temporaries into `scratch` (reused across calls).
    FrameMeasurements measure_into(const std::complex<float>* iq, std::size_t n,
                                   MeasureScratch& scratch) const {
        FrameMeasurements m;
        if (n == 0) { m.valid = false; return m; }

        // --- raw single-pass statistics (count domain) ---
        double sum_sq = 0.0, peak = 0.0;
        std::size_t clipped = 0;
        for (std::size_t k = 0; k < n; ++k) {
            const double re = static_cast<double>(iq[k].real());
            const double im = static_cast<double>(iq[k].imag());
            if (!std::isfinite(re) || !std::isfinite(im)) m.nan_inf = true;
            const double mag = std::sqrt(re * re + im * im);
            sum_sq += re * re + im * im;
            if (mag > peak) peak = mag;
            if (mag >= cfg_.clip_level_counts) ++clipped;
        }
        m.rms_counts = std::sqrt(sum_sq / static_cast<double>(n));
        m.peak_counts = peak;
        m.clip_ratio = static_cast<double>(clipped) / static_cast<double>(n);
        m.papr_db = (m.rms_counts > 0.0)
                        ? 20.0 * std::log10(peak / m.rms_counts)
                        : 0.0;
        m.power_dbfs = (m.rms_counts > 0.0)
                           ? 20.0 * std::log10(m.rms_counts / cfg_.full_scale_counts)
                           : -200.0;
        m.model_rms = m.rms_counts / cfg_.full_scale_counts * cfg_.receiver_scale;

        // --- spectrum domain (only for power-of-two sizes >= 2) ---
        if (n >= 2 && (n & (n - 1)) == 0) {
            compute_spectrum(m, iq, n, scratch);
        }
        return m;
    }

    // Interleaved int16 count domain -> complex<float> count domain, then measure.
    FrameMeasurements measure_int16(const std::int16_t* interleaved,
                                    std::size_t n_complex) const {
        std::vector<std::complex<float>> buf(n_complex);
        for (std::size_t k = 0; k < n_complex; ++k) {
            buf[k] = std::complex<float>(static_cast<float>(interleaved[k * 2 + 0]),
                                         static_cast<float>(interleaved[k * 2 + 1]));
        }
        return measure(buf.data(), n_complex);
    }

private:
    void compute_spectrum(FrameMeasurements& m, const std::complex<float>* iq,
                          std::size_t n, MeasureScratch& s) const {
        // Unnormalised forward FFT -> P[k] = |X[k]|^2 / n^2, sum P[k] = rms^2.
        s.x.resize(n);
        for (std::size_t k = 0; k < n; ++k)
            s.x[k] = std::complex<double>(iq[k].real(), iq[k].imag());
        fft_radix2(s.x.data(), n);
        const double inv_n2 = 1.0 / (static_cast<double>(n) * static_cast<double>(n));
        s.power.resize(n);
        for (std::size_t k = 0; k < n; ++k)
            s.power[k] = std::norm(s.x[k]) * inv_n2;

        // Noise floor = configured percentile of the PSD (robust to a few peaks).
        s.sorted = s.power;
        std::sort(s.sorted.begin(), s.sorted.end());
        const std::size_t pidx = static_cast<std::size_t>(
            std::round(cfg_.noise_percentile * static_cast<double>(n - 1)));
        const double noise_floor = s.sorted[pidx];

        // A pure bin-aligned tone leaves a zero median; use a tiny relative floor
        // so prominence/SNR/occupancy stay finite (<= ~120 dB) instead of either
        // dividing by zero or treating every rounding-noise bin as occupied.
        const double max_p = *std::max_element(s.power.begin(), s.power.end());
        const double floor_eps = 1e-12 * (max_p > 0.0 ? max_p : 1.0);
        const double nf = std::max(noise_floor, floor_eps);
        const double occ_power = nf * std::pow(10.0, cfg_.occupied_threshold_db / 10.0);

        double num = 0.0, den = 0.0;
        std::size_t min_bin = 0, max_bin = 0;
        bool any_occ = false;
        const double bin_hz = cfg_.sample_rate_hz / static_cast<double>(n);

        for (std::size_t k = 0; k < n; ++k) {
            // frequency of bin k (bins >= n/2 are negative frequencies)
            const double f = (k <= n / 2)
                                 ? static_cast<double>(k) * bin_hz
                                 : (static_cast<double>(k) - static_cast<double>(n)) * bin_hz;
            num += f * s.power[k];
            den += s.power[k];
            if (s.power[k] > occ_power) {
                if (!any_occ) { min_bin = max_bin = k; any_occ = true; }
                else { min_bin = std::min(min_bin, k); max_bin = std::max(max_bin, k); }
            }
        }

        // dBFS reference: full_scale^2 for the power of a full-scale sample.
        const double ref = cfg_.full_scale_counts * cfg_.full_scale_counts;
        const double noise_floor_dbfs = (nf > 0.0)
                                            ? 10.0 * std::log10(nf / ref)
                                            : -200.0;
        m.noise_floor_dbfs = noise_floor_dbfs;
        m.psd_peak_prominence_db = (max_p > 0.0)
                                       ? 10.0 * std::log10(max_p / nf)
                                       : 0.0;
        if (any_occ) {
            m.occupied_bins = static_cast<int>(max_bin - min_bin + 1);
            m.occupied_bw_hz = static_cast<double>(max_bin - min_bin + 1) * bin_hz;
        }
        m.spectral_centroid_hz = (den > 0.0) ? num / den : 0.0;

        // SNR: signal power above the floor vs. the flat noise floor total.
        const double total_power = den;  // == sum P[k] == rms^2
        const double noise_total = nf * static_cast<double>(n);
        const double signal_total = std::max(0.0, total_power - noise_total);
        m.snr_est_db = (noise_total > 0.0)
                           ? 10.0 * std::log10((signal_total + 1e-300) / noise_total)
                           : 0.0;

        // Display spectrum (waterfall).  Runs strictly AFTER every existing field
        // above, reusing s.power, so all prior quantities stay byte-identical.
        compute_display_spectrum(m, s, n);
    }

    // 1024-pt power -> 256 display bins (fftshift, group-of-4 MAX, dBFS x4).
    // Only enabled for the exact 1024-pt model window; any other size leaves
    // spectrum_valid = false so old callers see no display spectrum.
    void compute_display_spectrum(FrameMeasurements& m, const MeasureScratch& s,
                                  std::size_t n) const {
        m.spectrum_valid = false;
        constexpr std::size_t kFft = 1024;
        constexpr int kBins = 256;
        constexpr int kGroup = 4;
        if (n != kFft) return;

        const double ref = cfg_.full_scale_counts * cfg_.full_scale_counts;
        bool all_finite = true;
        for (int b = 0; b < kBins; ++b) {
            double max_p = 0.0;
            for (int j = 0; j < kGroup; ++j) {
                // fftshift: display bin 0 = -fs/2, bin 128 = DC (original k=0).
                const std::size_t k = (static_cast<std::size_t>(b * kGroup + j) + (kFft / 2)) % kFft;
                const double p = s.power[k];
                if (!std::isfinite(p)) { all_finite = false; break; }
                if (p > max_p) max_p = p;
            }
            if (!all_finite) break;
            double dbfs = (max_p > 0.0) ? 10.0 * std::log10(max_p / ref) : -120.0;
            if (dbfs < -120.0) dbfs = -120.0;
            if (dbfs > 0.0) dbfs = 0.0;
            const int x4 = static_cast<int>(std::lround(dbfs * 4.0));
            m.spectrum_dbfs_x4[b] = (x4 < -480) ? -480 : (x4 > 0 ? 0 : x4);
        }
        if (!all_finite) return;

        m.spectrum_valid = true;
        m.spectrum_fft_length = static_cast<int>(kFft);
        m.spectrum_bin_count = kBins;
        m.spectrum_sample_rate_hz = cfg_.sample_rate_hz;
        m.spectrum_center_hz = cfg_.center_hz;
    }

    DspMeasureConfig cfg_;
};

}  // namespace sdr
