// m24_bench.cpp -- M24-A unified performance benchmark (CPU reference FFT).
//
// Measures three stages with ONE fixed methodology so a single authoritative
// number replaces the two previously-reported, differently-measured figures
// (12.15 us from the replay tool and 29.80 us from an old ad-hoc test loop):
//
//   stage 1 : pure FFT            (m24::fft only)
//   stage 2 : FFT + Hann window   (m24::apply_window + m24::fft)
//   stage 3 : full spectrum       (window -> fft -> magnitude -> dB ->
//                                   fftshift -> noise floor -> peak detect)
//
// Fixed parameters: n = 1024, fs = 128000 Hz, single bin-aligned tone at
// 16000 Hz (bin 128), amplitude 1000, N = 1000 frames, one warm-up pass per
// stage, release build -O2 (see build_m24_bench.sh).  The measured function
// m24::fft allocates its own 16 KiB complex work buffer per call, which is part
// of the real (honest) cost and is therefore NOT factored out.
//
// Build: host_tools/build_m24_bench.sh   Run: ./build/m24/m24_bench

#include "../sdr_adapter/m24_fft.hpp"

#include <chrono>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

constexpr double PI = 3.141592653589793238462643383279502884;
constexpr std::size_t kN = 1024;
constexpr double kFs = 128000.0;
constexpr double kF0 = 16000.0;  // bin 128
constexpr double kAmp = 1000.0;

std::vector<std::complex<double>> make_tone() {
    std::vector<std::complex<double>> x(kN);
    for (std::size_t k = 0; k < kN; ++k) {
        const double ph = 2.0 * PI * kF0 / kFs * static_cast<double>(k);
        x[k] = std::complex<double>(kAmp * std::cos(ph), kAmp * std::sin(ph));
    }
    return x;
}

double to_db(double mag) { return m24::db_from_linear(mag, 1.0); }

void print_env() {
    std::printf("== M24-A unified benchmark ==\n");
    std::printf("compiler      : g++ %d.%d.%d (__VERSION__ %s)\n", __GNUC__,
                __GNUC_MINOR__, __GNUC_PATCHLEVEL__, __VERSION__);
    std::printf("build flags   : -std=gnu++17 -O2 (see build_m24_bench.sh)\n");
    FILE* f = std::fopen("/proc/cpuinfo", "r");
    if (f) {
        char line[512];
        std::string model;
        while (std::fgets(line, sizeof(line), f)) {
            std::string s = line;
            const std::string key = "model name";
            const std::size_t pos = s.find(key);
            if (pos == std::string::npos) continue;
            const std::size_t colon = s.find(':', pos);
            if (colon == std::string::npos) continue;
            model = s.substr(colon + 1);
            model.erase(0, model.find_first_not_of(" \t"));
            model.erase(model.find_last_not_of(" \t\r\n") + 1);
            break;
        }
        std::fclose(f);
        if (!model.empty()) std::printf("CPU           : %s\n", model.c_str());
    }
    f = std::fopen("/proc/version", "r");
    if (f) {
        char line[512];
        if (std::fgets(line, sizeof(line), f)) {
            std::string v = line;
            v.erase(v.find_last_not_of(" \t\r\n") + 1);
            std::printf("kernel        : %s\n", v.c_str());
        }
        std::fclose(f);
    }
    std::printf("parameters    : n=%zu fs=%.0f Hz tone=%.0f Hz (bin %zu) A=%.0f\n",
                kN, kFs, kF0, std::size_t(kF0 / kFs * kN + 0.5), kAmp);
}

// Run `work` once to warm up, then N times, timing the N steady-state frames.
// Returns mean microseconds per frame.  `label` prints one status line.
template <typename Fn>
double run_stage(const char* label, std::size_t nframes, Fn&& work) {
    double sink = 0.0;
    work(sink);  // warm-up
    const auto t0 = std::chrono::steady_clock::now();
    for (std::size_t i = 0; i < nframes; ++i) work(sink);
    const auto t1 = std::chrono::steady_clock::now();
    const double us = std::chrono::duration<double, std::micro>(t1 - t0).count() /
                      static_cast<double>(nframes);
    std::printf("%-14s : %8.2f us/frame  (N=%zu, sink=%g)\n", label, us, nframes,
                sink);
    return us;
}

}  // namespace

int main(int argc, char** argv) {
    std::size_t nframes = 1000;
    if (argc > 1) nframes = static_cast<std::size_t>(std::strtoull(argv[1], nullptr, 10));
    if (nframes == 0) nframes = 1000;

    print_env();

    const auto x = make_tone();
    const auto w = m24::hann_window(kN);

    double us_fft = 0.0, us_win = 0.0, us_full = 0.0;

    // stage 1: pure FFT (m24::fft allocates its own work buffer each call).
    us_fft = run_stage("pure FFT", nframes, [&](double& sink) {
        const m24::Spectrum s = m24::fft(x.data(), kN);
        sink += std::abs(s.bins[128]);
    });

    // stage 2: FFT + Hann window.
    us_win = run_stage("FFT + window", nframes, [&](double& sink) {
        std::vector<std::complex<double>> y = x;
        m24::apply_window(y, w);
        const m24::Spectrum s = m24::fft(y.data(), kN);
        sink += std::abs(s.bins[128]);
    });

    // stage 3: full spectrum pipeline.
    us_full = run_stage("full pipeline", nframes, [&](double& sink) {
        std::vector<std::complex<double>> y = x;
        m24::apply_window(y, w);
        const m24::Spectrum s = m24::fft(y.data(), kN);
        std::vector<double> db(kN);
        for (std::size_t k = 0; k < kN; ++k) db[k] = to_db(std::abs(s.bins[k]));
        const std::vector<double> sh = m24::fftshift(db);
        sink += m24::noise_floor_db(sh);
        const auto peaks = m24::detect_peaks(db, kFs, 40.0, 2);
        sink += static_cast<double>(peaks.size());
    });

    std::printf("== benchmark done ==\n");
    std::printf("pure FFT       : %.2f us/frame\n", us_fft);
    std::printf("FFT + window   : %.2f us/frame (window overhead %.2f us)\n", us_win,
                us_win - us_fft);
    std::printf("full pipeline  : %.2f us/frame (pipeline overhead %.2f us over FFT+window)\n",
                us_full, us_full - us_win);
    return 0;
}
