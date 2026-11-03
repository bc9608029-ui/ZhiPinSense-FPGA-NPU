// make_ui_m19_snapshots.cpp -- render seven fixed-input PPM snapshots of the M19
// UI into artifacts/ui_m19/ for visual before/after review (docs/M19_UI_BEFORE_AFTER.md).
//
// The inputs are frozen, so a diff between the M18-SW1 snapshots and the M19 ones
// isolates exactly what the visual refactor changed.  PPM (P6, RGB888) is chosen
// because it needs no external libraries.
//
// Usage: make_ui_m19_snapshots [output-dir]   (default ../artifacts/ui_m19)
//
// Build: see host_tests/build_host_tests.sh.

#include "../ui_sw/ui_render.hpp"
#include "../ui_sw/ui_theme.hpp"

#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

namespace {

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

// A representative Live 12-class frame (QPSK @ 0.71).
ui::UiState base() {
    ui::UiState st;
    st.status = ui::Status::Live;
    st.source = "SDR";
    st.top1 = "QPSK";
    st.conf = 0.71f;
    std::vector<float> d(12, 0.026363636f);
    d[7] = 0.71f;
    st.dist = d;
    st.classes = &ui::classes_12();
    st.snr = "+18.5 dB";
    st.lat = "12.4 ms";
    st.frame = "240";
    st.model = "abcdef01";
    st.work_mode = "FIXED";
    st.running = true;
    st.ctl_connected = "CONTROL CONNECTED";
    return st;
}

int run(const std::string& outdir) {
    std::error_code ec;
    std::filesystem::create_directories(outdir, ec);
    const ui::Theme& th = ui::theme_default();
    const int W = 1280, H = 720;

    auto snap = [&](const char* name, const ui::UiState& st,
                    void (*fn)(ui::Canvas&, const ui::Theme&, const ui::UiState&)) {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H, th.background);
        ui::Canvas c{px.data(), W, H};
        fn(c, th, st);
        const std::string path = outdir + "/" + name + ".ppm";
        if (!write_ppm(path, c)) return false;
        std::printf("  wrote %s\n", path.c_str());
        return true;
    };

    bool ok = true;

    { ui::UiState st = base(); ok &= snap("main_live", st, ui::render_main); }
    { ui::UiState st = base(); st.status = ui::Status::Stale; st.age = "3.2 s";
      ok &= snap("main_stale", st, ui::render_main); }
    { ui::UiState st = base(); st.status = ui::Status::Error;
      ok &= snap("main_error", st, ui::render_main); }
    { ui::UiState st = base(); st.status = ui::Status::Mock; st.source = "MOCK";
      ok &= snap("main_mock", st, ui::render_main); }

    {
        ui::UiState st = base();
        st.meas.valid = true;
        st.meas.rms_counts = 1000.0;
        st.meas.peak_counts = 1500.0;
        st.meas.papr_db = 3.5;
        st.meas.clip_ratio = 0.001;
        st.meas.power_dbfs = -6.234;
        st.meas.noise_floor_dbfs = -50.123;
        st.meas.psd_peak_prominence_db = 43.889;
        st.meas.snr_est_db = 40.0;
        st.meas.occupied_bins = 5;
        st.meas.spectral_centroid_hz = 16000.0;
        st.meas.occupied_bw_hz = 625.0;
        st.meas.model_rms = 10.666;
        st.presence = "SIGNAL_PRESENT";
        st.level_mode = "AUTO";
        st.model_scale = 1.125;
        st.rf_gain_db = 33.0;
        ok &= snap("parameters", st, ui::render_parameters);
    }

    {
        ui::UiState st = base();
        st.work_mode = "AUTO LOCK";
        st.running = false;
        st.requested_mode = "FIXED";
        st.requested_running = false;
        st.command_status = "APPLIED";
        st.last_command = "SET_MODE AUTO LOCK";
        st.feedback = "ALREADY IN THIS MODE";
        ok &= snap("mode_stopped", st, ui::render_mode);
    }

    {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H, th.background);
        ui::Canvas c{px.data(), W, H};
        ui::render_legend(c, th);
        const std::string path = outdir + "/legend.ppm";
        if (!write_ppm(path, c)) ok = false;
        else std::printf("  wrote %s\n", path.c_str());
    }

    return ok ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string outdir = (argc > 1) ? argv[1] : "../artifacts/ui_m19";
    std::printf("make_ui_m19_snapshots -> %s\n", outdir.c_str());
    return run(outdir);
}
