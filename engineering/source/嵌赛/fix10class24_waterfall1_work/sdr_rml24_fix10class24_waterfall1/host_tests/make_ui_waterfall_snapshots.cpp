// make_ui_waterfall_snapshots.cpp -- spectrum + waterfall snapshot matrix
// (fix10class24-waterfall1, Phase F).
//
// Renders the SPECTRUM page (spectrum curve + bounded waterfall + side metrics)
// for six scenarios into PPM (P6) files, then the caller converts them to PNG
// with host_tests/ppm_to_png.py:
//
//   bpsk_waterfall.png   <- REAL RX: recovered payload of the gate-rejected
//                           24-class capture source_index=1500 (BPSK)
//   4ask_waterfall.png   <- REAL RX: source_index=500  (4ASK)
//   qam_waterfall.png    <- REAL RX: source_index=7000 (64QAM)
//   am_waterfall.png     <- REAL RX: source_index=9500 (AM-DSB-WC)
//   noise_waterfall.png  <- SYNTHETIC AWGN (host-generated, documented)
//   dual_tone_waterfall.png <- SYNTHETIC two-tone (host-generated, documented)
//
// Every row (real or synthetic) goes through the SAME sdr::DspMeasure derivation
// the board runs: one 1024-pt FFT -> fftshift -> group-of-4 MAX -> dBFS x4.
// The real RX input is the board's recovered payload f32 (counts domain, full
// scale 2048), sliced into 52 consecutive 1024-sample windows -- a genuinely
// continuous real waterfall.  The expected TX is NEVER drawn as RX.
//
// Usage: make_ui_waterfall_snapshots [dump-root] [output-dir]
//   dump-root defaults to the full24 failed-rx forced-classify export.

#include "../sdr_adapter/dsp_measure.hpp"
#include "../ui_sw/ui_render.hpp"
#include "../ui_sw/waterfall_history.hpp"

#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace {

const int kW = 1280, kH = 720;
constexpr std::size_t kWindow = 1024;
constexpr std::size_t kRealRows = 52;      // windows in the recovered payload
constexpr std::size_t kSynthRows = 128;    // full ring for the synthetic cases

// ---- PPM writer (RGB565 -> 8-bit RGB) ---------------------------------------
bool write_ppm(const std::string& path, const ui::Canvas& c) {
    std::FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) { std::fprintf(stderr, "open failed: %s\n", path.c_str()); return false; }
    std::fprintf(f, "P6\n%d %d\n255\n", c.w, c.h);
    for (int i = 0; i < c.w * c.h; ++i) {
        const std::uint16_t v = c.px[i];
        const std::uint8_t r = static_cast<std::uint8_t>(((v >> 11) & 0x1F) << 3 | ((v >> 11) & 0x1F) >> 2);
        const std::uint8_t g = static_cast<std::uint8_t>(((v >> 5) & 0x3F) << 2 | ((v >> 5) & 0x3F) >> 4);
        const std::uint8_t b = static_cast<std::uint8_t>((v & 0x1F) << 3 | (v & 0x1F) >> 2);
        std::fputc(r, f); std::fputc(g, f); std::fputc(b, f);
    }
    std::fclose(f);
    return true;
}

// ---- real RX loading --------------------------------------------------------
// Reads a float32-le binary into complex<float> samples.
std::vector<std::complex<float>> load_f32le(const std::string& path, std::size_t expect_complex) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        std::fprintf(stderr, "open failed: %s\n", path.c_str());
        return {};
    }
    std::vector<float> raw;
    raw.resize(expect_complex * 2);
    in.read(reinterpret_cast<char*>(raw.data()),
            static_cast<std::streamsize>(raw.size() * sizeof(float)));
    if (static_cast<std::size_t>(in.gcount()) != raw.size() * sizeof(float)) {
        std::fprintf(stderr, "short read: %s\n", path.c_str());
        return {};
    }
    std::vector<std::complex<float>> out(expect_complex);
    for (std::size_t i = 0; i < expect_complex; ++i)
        out[i] = std::complex<float>(raw[i * 2 + 0], raw[i * 2 + 1]);
    return out;
}

// ---- synthetic IQ -----------------------------------------------------------
unsigned lcg_step(unsigned s) { return s * 1664525u + 1013904223u; }

std::vector<std::complex<float>> synth_noise(std::size_t n, float amp, unsigned seed) {
    std::vector<std::complex<float>> v(n);
    unsigned s = seed;
    for (std::size_t k = 0; k < n; ++k) {
        s = lcg_step(s);
        const float u = static_cast<float>((s >> 8) & 0xFFFF) / 65535.0f - 0.5f;
        s = lcg_step(s);
        const float w = static_cast<float>((s >> 8) & 0xFFFF) / 65535.0f - 0.5f;
        v[k] = std::complex<float>(amp * u, amp * w);
    }
    return v;
}

std::vector<std::complex<float>> synth_tones_noise(std::size_t n, int bin_a, int bin_b,
                                                   float amp, float noise, unsigned seed) {
    std::vector<std::complex<float>> v = synth_noise(n, noise, seed);
    const double two_pi = 2.0 * 3.14159265358979323846;
    const int bins[2] = {bin_a, bin_b};
    for (int t = 0; t < 2; ++t) {
        const int bin = bins[t];
        for (std::size_t k = 0; k < n; ++k) {
            const double ph = two_pi * static_cast<double>(bin) * static_cast<double>(k) /
                              static_cast<double>(n);
            v[k] += std::complex<float>(amp * static_cast<float>(std::cos(ph)),
                                        amp * static_cast<float>(std::sin(ph)));
        }
    }
    return v;
}

// ---- measure -> view bridge (the same fields ui_state_map.hpp copies) --------
ui::MeasureView to_view(const sdr::FrameMeasurements& m) {
    ui::MeasureView v;
    v.valid = m.valid;
    v.noise_floor_dbfs = m.noise_floor_dbfs;
    v.psd_peak_prominence_db = m.psd_peak_prominence_db;
    v.occupied_bw_hz = m.occupied_bw_hz;
    v.spectral_centroid_hz = m.spectral_centroid_hz;
    v.spectrum_valid = m.spectrum_valid;
    for (int b = 0; b < 256; ++b) v.spectrum_dbfs_x4[b] = m.spectrum_dbfs_x4[b];
    v.spectrum_sample_rate_hz = m.spectrum_sample_rate_hz;
    v.spectrum_center_hz = m.spectrum_center_hz;
    return v;
}

sdr::DspMeasure make_measure() {
    sdr::DspMeasureConfig cfg;
    cfg.sample_rate_hz = 2560000.0;
    cfg.center_hz = 2400000000.0;
    cfg.full_scale_counts = 2048.0;
    return sdr::DspMeasure(cfg);
}

// Render one full page from a history and the latest window's measurements.
// Returns the render time in microseconds.
long render_one(const ui::Theme& th, ui::WaterfallHistory& history,
                const sdr::FrameMeasurements& last_meas,
                const char* presence, ui::Status status, const std::string& path) {
    ui::UiState st;
    st.status = status;
    st.presence = presence;
    st.source = "fpga_npu";
    st.meas = to_view(last_meas);
    st.top1 = "";   // no classification presented: these captures are gate-rejected
    st.conf = 0.0f;

    std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH, th.background);
    ui::Canvas c{px.data(), kW, kH};

    const auto t0 = std::chrono::steady_clock::now();
    ui::render_parameters(c, th, st, &history);
    const auto t1 = std::chrono::steady_clock::now();
    const long us = static_cast<long>(
        std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count());

    if (!write_ppm(path, c)) std::fprintf(stderr, "write failed: %s\n", path.c_str());
    else std::printf("  wrote %s (%ld rows, %ld us)\n", path.c_str(),
                     static_cast<long>(history.size()), us);
    return us;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string dump_root =
        (argc > 1) ? argv[1]
                   : "../results/full24_failed_rx_forceclass/forced_classify_export/"
                     "rml24_full24_failed_rx_1773374413";
    const std::string outdir = (argc > 2) ? argv[2] : "../results/waterfall1";
    std::error_code ec;
    std::filesystem::create_directories(outdir, ec);

    const ui::Theme& th = ui::theme_default();
    const sdr::DspMeasure measure = make_measure();
    sdr::MeasureScratch scratch;

    std::printf("make_ui_waterfall_snapshots -> %s\n", outdir.c_str());
    std::printf("real RX dump root -> %s\n", dump_root.c_str());

    bool ok = true;
    long total_us = 0, max_us = 0;
    int pngs = 0;

    // ---- real RX: four gate-rejected 24-class captures ----------------------
    struct RealCase { const char* name; const char* dir; const char* presence; };
    const RealCase real_cases[] = {
        {"bpsk_waterfall", "1500", "SIGNAL_PRESENT"},
        {"4ask_waterfall", "500", "SIGNAL_PRESENT"},
        {"qam_waterfall", "7000", "SIGNAL_PRESENT"},
        {"am_waterfall", "9500", "SIGNAL_PRESENT"},
    };

    for (const auto& rc : real_cases) {
        const std::string file =
            dump_root + "/" + rc.dir + "/provisional_recovered_payload_f32le.bin";
        const auto iq = load_f32le(file, kRealRows * kWindow);
        if (iq.size() != kRealRows * kWindow) { ok = false; continue; }

        ui::WaterfallHistory history;
        sdr::FrameMeasurements last;
        std::uint64_t frame_id = 0;
        for (std::size_t w = 0; w < kRealRows; ++w) {
            const auto m = measure.measure_into(iq.data() + w * kWindow, kWindow, scratch);
            std::int16_t row[ui::kWaterfallBins];
            for (int b = 0; b < ui::kWaterfallBins; ++b)
                row[b] = static_cast<std::int16_t>(m.spectrum_dbfs_x4[b]);
            history.push(row, frame_id++, static_cast<std::uint64_t>(w) * 100);
            last = m;
        }
        const long us = render_one(th, history, last, rc.presence, ui::Status::Live,
                                   outdir + "/" + rc.name + ".ppm");
        total_us += us; max_us = us > max_us ? us : max_us; ++pngs;
    }

    // ---- synthetic AWGN (NO_SIGNAL: real noise spectrum, no classification) ---
    {
        ui::WaterfallHistory history;
        sdr::FrameMeasurements last;
        for (std::size_t w = 0; w < kSynthRows; ++w) {
            const auto iq = synth_noise(kWindow, 60.0f, static_cast<unsigned>(1000 + w));
            const auto m = measure.measure_into(iq.data(), kWindow, scratch);
            std::int16_t row[ui::kWaterfallBins];
            for (int b = 0; b < ui::kWaterfallBins; ++b)
                row[b] = static_cast<std::int16_t>(m.spectrum_dbfs_x4[b]);
            history.push(row, static_cast<std::uint64_t>(w),
                         static_cast<std::uint64_t>(w) * 100);
            last = m;
        }
        const long us = render_one(th, history, last, "NO_SIGNAL", ui::Status::NoSignal,
                                   outdir + "/noise_waterfall.ppm");
        total_us += us; max_us = us > max_us ? us : max_us; ++pngs;
    }

    // ---- synthetic two-tone (host-generated test signal) --------------------
    {
        ui::WaterfallHistory history;
        sdr::FrameMeasurements last;
        for (std::size_t w = 0; w < kSynthRows; ++w) {
            const auto iq = synth_tones_noise(kWindow, 40, 984, 900.0f, 40.0f,
                                              static_cast<unsigned>(5000 + w));
            const auto m = measure.measure_into(iq.data(), kWindow, scratch);
            std::int16_t row[ui::kWaterfallBins];
            for (int b = 0; b < ui::kWaterfallBins; ++b)
                row[b] = static_cast<std::int16_t>(m.spectrum_dbfs_x4[b]);
            history.push(row, static_cast<std::uint64_t>(w),
                         static_cast<std::uint64_t>(w) * 100);
            last = m;
        }
        const long us = render_one(th, history, last, "SIGNAL_PRESENT", ui::Status::Live,
                                   outdir + "/dual_tone_waterfall.ppm");
        total_us += us; max_us = us > max_us ? us : max_us; ++pngs;
    }

    // ---- performance.json ----------------------------------------------------
    {
        const std::string path = outdir + "/performance.json";
        std::FILE* f = std::fopen(path.c_str(), "wb");
        if (f) {
            std::fprintf(f, "{\n");
            std::fprintf(f, "  \"images\": %d,\n", pngs);
            std::fprintf(f, "  \"render_total_us\": %ld,\n", total_us);
            std::fprintf(f, "  \"render_max_us\": %ld,\n", max_us);
            std::fprintf(f, "  \"history_bytes\": %zu,\n", sizeof(ui::WaterfallHistory));
            std::fprintf(f, "  \"history_max_rows\": %d,\n", ui::kWaterfallMaxRows);
            std::fprintf(f, "  \"spectrum_bins\": %d,\n", ui::kWaterfallBins);
            std::fprintf(f, "  \"real_rx_rows_per_image\": %zu,\n", kRealRows);
            std::fprintf(f, "  \"synthetic_rows_per_image\": %zu,\n", kSynthRows);
            std::fprintf(f, "  \"note\": \"real RX = recovered payload f32 (counts, "
                               "full-scale 2048), 52 consecutive 1024-sample windows, "
                               "gate-rejected captures; noise/dual-tone = synthetic host IQ\"\n");
            std::fprintf(f, "}\n");
            std::fclose(f);
            std::printf("  wrote %s\n", path.c_str());
        } else {
            ok = false;
        }
    }

    std::printf("done: %s (%d images, %ld us total, %ld us max)\n",
                ok ? "OK" : "FAIL", pngs, total_us, max_us);
    return ok ? 0 : 1;
}
