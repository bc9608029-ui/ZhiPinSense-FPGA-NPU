// test_rf_waveform_12class.cpp -- host test for the deterministic 12-class
// waveform generator + x20 upsampler (task 39e5 UI v3 · M9 / Gate 10 self-test).
//
// Verifies against the frozen training-generator contract (docs/
// TRAINING_SIGNAL_CONTRACT_AUDIT.md + RF_SELF_TEST_CONTRACT.md):
//   - every frame finite, RMS == 1.0 (the training _normalize_rms domain);
//   - deterministic (same seed -> byte-identical; different seed/class differ);
//   - per-class structural signatures (constant envelope for FSK/FM, real-valued
//     AM-DSB/OOK, two-tone 2FSK, wideband WBFM, wide-flat OFDM, balanced PSK/QAM);
//   - x20 upsampler has unit DC gain and preserves tone RMS (no amplitude loss).
//
// iCraft-free / libiio-free.  Built with g++ -std=gnu++17 -O2 -Wall -Wextra -Werror.

#include "../sdr_adapter/rf_waveform_12class.hpp"
#include "../sdr_adapter/categories.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

static void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("FAIL: %s\n", what);
    }
}

static bool all_finite(const std::complex<float>* x, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i)
        if (!std::isfinite(x[i].real()) || !std::isfinite(x[i].imag())) return false;
    return true;
}

static double frame_rms(const std::complex<float>* x, std::size_t n) {
    double s = 0.0;
    for (std::size_t i = 0; i < n; ++i)
        s += static_cast<double>(x[i].real()) * x[i].real() +
             static_cast<double>(x[i].imag()) * x[i].imag();
    return std::sqrt(s / static_cast<double>(n));
}

static double max_abs_imag(const std::complex<float>* x, std::size_t n) {
    double m = 0.0;
    for (std::size_t i = 0; i < n; ++i)
        m = std::max(m, static_cast<double>(std::fabs(x[i].imag())));
    return m;
}

static double mean_real(const std::complex<float>* x, std::size_t n) {
    double s = 0.0;
    for (std::size_t i = 0; i < n; ++i) s += x[i].real();
    return s / static_cast<double>(n);
}

// max | |x| - 1 | over the buffer (constant-envelope deviation).
static double envelope_deviation(const std::complex<float>* x, std::size_t n) {
    double m = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        const double mag = std::sqrt(static_cast<double>(x[i].real()) * x[i].real() +
                                     static_cast<double>(x[i].imag()) * x[i].imag());
        m = std::max(m, std::fabs(mag - 1.0));
    }
    return m;
}

struct Spectrum {
    std::vector<double> mag;   // magnitudes of bins [0, N/2)
    double bin_hz = 0.0;
    int peak_bin = -1;         // strongest bin in [1, N/2) (DC excluded)
};

static Spectrum spectrum_of(const std::complex<float>* x, int N) {
    std::vector<std::complex<double>> f(static_cast<std::size_t>(N));
    for (int i = 0; i < N; ++i)
        f[static_cast<std::size_t>(i)] =
            std::complex<double>(x[i].real(), x[i].imag());
    sdr::fft_radix2(f.data(), N, -1);
    Spectrum s;
    s.bin_hz = 128000.0 / static_cast<double>(N);
    s.mag.resize(static_cast<std::size_t>(N / 2));
    double peak = 0.0;
    for (int k = 0; k < N / 2; ++k) {
        s.mag[static_cast<std::size_t>(k)] = std::abs(f[static_cast<std::size_t>(k)]);
        if (k >= 1 && s.mag[static_cast<std::size_t>(k)] > peak) {
            peak = s.mag[static_cast<std::size_t>(k)];
            s.peak_bin = k;
        }
    }
    return s;
}

// Positive-frequency occupied bandwidth (Hz) at a fraction of the peak.
static double occupied_bw_hz(const Spectrum& s, double frac) {
    double peak = 0.0;
    for (double m : s.mag) peak = std::max(peak, m);
    std::size_t count = 0;
    for (double m : s.mag)
        if (m > frac * peak) ++count;
    return static_cast<double>(count) * s.bin_hz;
}

int main() {
    const cat::Contract contract = cat::target_12();
    check(contract.class_count == 12, "target_12 class_count == 12");
    check(cat::label(contract, 0) == "OOK", "class 0 == OOK");
    check(cat::label(contract, 11) == "OFDM", "class 11 == OFDM");

    // --- RRC taps ------------------------------------------------------------
    const std::vector<double> rrc = sdr::rrc_taps(8, 8, 0.35);
    check(rrc.size() == 65, "rrc_taps(8,8,0.35) has 65 taps");
    double e = 0.0;
    for (double v : rrc) e += v * v;
    check(std::fabs(e - 1.0) < 1e-9, "rrc taps unit energy");
    double peak = 0.0;
    int peak_idx = -1;
    for (int i = 0; i < 65; ++i)
        if (rrc[static_cast<std::size_t>(i)] > peak) {
            peak = rrc[static_cast<std::size_t>(i)];
            peak_idx = i;
        }
    check(peak_idx == 32 && peak > 0.2, "rrc taps peak at centre (index 32)");
    check(std::fabs(rrc[0] - rrc[64]) < 1e-12, "rrc taps symmetric");

    // --- all classes: finite + per-frame RMS == 1.0 --------------------------
    constexpr std::size_t kBuf = 16384;   // 16 frames
    std::vector<std::complex<float>> buf(kBuf);
    const std::uint64_t kSeed = 0x39e50001ULL;

    for (int cls = 0; cls < 12; ++cls) {
        sdr::RfWaveform12Class gen(cls, kSeed);
        gen.generate(buf.data(), kBuf);

        char what[128];
        std::snprintf(what, sizeof what, "class %d finite", cls);
        check(all_finite(buf.data(), kBuf), what);

        bool rms_ok = true;
        for (std::size_t f = 0; f < kBuf / sdr::kBaseFrameSamples; ++f) {
            const double r = frame_rms(buf.data() + f * sdr::kBaseFrameSamples,
                                       sdr::kBaseFrameSamples);
            if (std::fabs(r - 1.0) > 1e-3) rms_ok = false;
        }
        std::snprintf(what, sizeof what, "class %d per-frame RMS==1.0", cls);
        check(rms_ok, what);
    }

    // --- determinism ---------------------------------------------------------
    {
        std::vector<std::complex<float>> a(kBuf), b(kBuf), c(kBuf);
        sdr::RfWaveform12Class g1(sdr::kWfQpsk, 0x1234);
        sdr::RfWaveform12Class g2(sdr::kWfQpsk, 0x1234);
        sdr::RfWaveform12Class g3(sdr::kWfQpsk, 0x1235);
        g1.generate(a.data(), kBuf);
        g2.generate(b.data(), kBuf);
        g3.generate(c.data(), kBuf);
        check(std::memcmp(a.data(), b.data(), kBuf * sizeof(std::complex<float>)) == 0,
              "same seed -> byte-identical");
        check(std::memcmp(a.data(), c.data(), kBuf * sizeof(std::complex<float>)) != 0,
              "different seed -> different output");
    }

    // --- structural signatures per class ------------------------------------
    // constant-envelope classes
    for (int cls : {sdr::kWf2Fsk, sdr::kWfGfsk, sdr::kWfWbfm}) {
        sdr::RfWaveform12Class gen(cls, kSeed);
        gen.generate(buf.data(), kBuf);
        char what[128];
        std::snprintf(what, sizeof what, "class %d constant envelope", cls);
        check(envelope_deviation(buf.data(), kBuf) < 1e-5, what);
    }

    // AM-DSB: real-valued + strong positive DC (1 + index*msg)
    {
        sdr::RfWaveform12Class gen(sdr::kWfAmDsb, kSeed);
        gen.generate(buf.data(), kBuf);
        check(max_abs_imag(buf.data(), kBuf) < 1e-9, "AM-DSB real-valued");
        check(mean_real(buf.data(), kBuf) > 0.3, "AM-DSB positive DC (carrier)");
    }

    // OOK: real-valued + unipolar (on/off keying; RRC sidelobes dip slightly
    // negative but the signal is dominated by the positive on-level).
    {
        sdr::RfWaveform12Class gen(sdr::kWfOok, kSeed);
        gen.generate(buf.data(), kBuf);
        check(max_abs_imag(buf.data(), kBuf) < 1e-9, "OOK real-valued");
        check(mean_real(buf.data(), kBuf) > 0.1, "OOK unipolar (mean > 0)");
    }

    // 2FSK: dominant positive tone near +8000 Hz (separation 16 kHz)
    {
        sdr::RfWaveform12Class gen(sdr::kWf2Fsk, kSeed);
        gen.generate(buf.data(), kBuf);
        const Spectrum s = spectrum_of(buf.data(), static_cast<int>(kBuf));
        const double peak_hz = s.peak_bin * s.bin_hz;
        check(peak_hz > 3000.0 && peak_hz < 13000.0,
              "2FSK dominant tone near +8 kHz");
    }

    // WBFM: wideband (occupied BW well beyond the 2FSK/GFSK narrowband lobes)
    {
        sdr::RfWaveform12Class gen(sdr::kWfWbfm, kSeed);
        gen.generate(buf.data(), kBuf);
        const Spectrum s = spectrum_of(buf.data(), static_cast<int>(kBuf));
        check(occupied_bw_hz(s, 0.05) > 10000.0, "WBFM wideband FM");
    }

    // OFDM: 48 active subcarriers -> ~12 kHz positive occupied bandwidth
    {
        sdr::RfWaveform12Class gen(sdr::kWfOfdm, kSeed);
        gen.generate(buf.data(), kBuf);
        const Spectrum s = spectrum_of(buf.data(), static_cast<int>(kBuf));
        const double bw = occupied_bw_hz(s, 0.05);
        check(bw > 8000.0 && bw < 18000.0, "OFDM ~12 kHz occupied bandwidth");
    }

    // PSK/QAM: zero-mean (balanced constellations)
    for (int cls : {sdr::kWfBpsk, sdr::kWfQpsk, sdr::kWf8Psk, sdr::kWf16Qam,
                    sdr::kWf64Qam}) {
        sdr::RfWaveform12Class gen(cls, kSeed);
        gen.generate(buf.data(), kBuf);
        char what[128];
        std::snprintf(what, sizeof what, "class %d zero-mean", cls);
        check(std::fabs(mean_real(buf.data(), kBuf)) < 0.1, what);
    }

    // --- x20 upsampler: unit DC gain + tone RMS preservation -----------------
    {
        sdr::StreamResampler up = sdr::make_20x_upsampler();
        check(up.up() == 20 && up.down() == 1, "upsampler up=20 down=1");
        check(up.taps_total() == 600, "upsampler 600 taps (multiple of 20)");

        // DC gain: constant 1.0 input -> output ~1.0 (not 1/20).
        const int in_n = 4096;
        std::vector<std::complex<float>> in(static_cast<std::size_t>(in_n),
                                            std::complex<float>(1.0f, 0.0f));
        up.push(in.data(), static_cast<std::size_t>(in_n));
        std::vector<std::complex<float>> out(up.available());
        up.pull(out.data(), out.size());
        check(!out.empty(), "upsampler produced output");
        double dc = 0.0;
        const std::size_t tail = std::min<std::size_t>(200, out.size());
        for (std::size_t i = out.size() - tail; i < out.size(); ++i)
            dc += static_cast<double>(out[i].real());
        dc /= static_cast<double>(tail);
        check(std::fabs(dc - 1.0) < 0.02, "upsampler unit DC gain (~1.0)");

        // Tone RMS: 8 kHz sine at 128 kS/s (RMS 1/sqrt(2)) preserved after x20.
        sdr::StreamResampler up2 = sdr::make_20x_upsampler();
        const int tone_n = 4096;
        std::vector<std::complex<float>> tone(static_cast<std::size_t>(tone_n));
        for (int i = 0; i < tone_n; ++i) {
            const double ph = 2.0 * sdr::kPiW * 8000.0 * i / 128000.0;
            tone[static_cast<std::size_t>(i)] =
                std::complex<float>(static_cast<float>(std::cos(ph)), 0.0f);
        }
        up2.push(tone.data(), static_cast<std::size_t>(tone_n));
        std::vector<std::complex<float>> tone_out(up2.available());
        up2.pull(tone_out.data(), tone_out.size());
        check(!tone_out.empty(), "upsampler tone output");
        const double rms_out = frame_rms(tone_out.data(), tone_out.size());
        check(std::fabs(rms_out - (1.0 / std::sqrt(2.0))) < 0.02,
              "upsampler preserves tone RMS");
    }

    // --- TX waveform builder: peak-limited, finite, interleaved ---------------
    {
        std::vector<std::int16_t> iq;
        for (int cls = 0; cls < 12; ++cls) {
            double peak = 0.0, rms = 0.0;
            sdr::build_tx_waveform(cls, kSeed, 4, 1638.0, iq, &peak, &rms);
            bool ok = !iq.empty() && (iq.size() % 2 == 0);
            double mx = 0.0;
            for (std::size_t k = 0; k < iq.size() / 2; ++k) {
                const int a = std::abs(static_cast<int>(iq[k * 2 + 0]));
                const int b = std::abs(static_cast<int>(iq[k * 2 + 1]));
                mx = std::max(mx, static_cast<double>(std::max(a, b)));
            }
            char what[128];
            std::snprintf(what, sizeof what, "class %d TX waveform peak<=limit", cls);
            check(ok && mx <= 1639.0 && peak > 0.0 && rms > 0.0, what);
        }
    }

    std::printf("test_rf_waveform_12class: %d pass, %d fail\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
