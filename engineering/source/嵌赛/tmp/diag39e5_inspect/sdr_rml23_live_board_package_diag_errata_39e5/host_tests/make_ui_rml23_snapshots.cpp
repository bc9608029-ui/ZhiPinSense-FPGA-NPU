// make_ui_rml23_snapshots.cpp -- comprehensive fixed-input PPM snapshot matrix for
// the RML23 LIVE UI (M29 Phase F5 Task B UI redesign).
//
// Renders every page (Main 23-class / Main 12-class / Parameters / Mode / Diag /
// Touch / Legend) across every status and the worst-case strings, into PPM (P6)
// files.  The inputs are FROZEN and the render calls use only the public ui:: API,
// so building this tool before and after the visual refactor isolates exactly what
// the redesign changed (a diff between the before/ and after/ PPMs is the visual
// proof).
//
// Usage: make_ui_rml23_snapshots [output-dir]
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

const int kW = 1280, kH = 720;

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

// A representative 23-class live frame: QPSK (slot 4) at 0.82 confidence.
ui::UiState base23() {
    ui::UiState st;
    st.status = ui::Status::Live;
    st.source = "SDR";
    st.top1 = "QPSK";
    st.conf = 0.82f;
    std::vector<float> d(23, 0.008f);
    d[4] = 0.82f;   // QPSK
    d[17] = 0.03f;  // AM-SSB
    d[18] = 0.02f;  // AM-DSB-WC
    st.dist = d;
    st.classes = &ui::classes_23();
    st.class_count = 23;
    st.model_mode = "RML23-AMSSB-MERGED";
    st.snr = "+18.5 dB";
    st.lat = "12.4 ms";
    st.frame = "240";
    st.model = "2425d990";
    st.work_mode = "FIXED";
    st.running = true;
    st.ctl_connected = "CONTROL CONNECTED";
    st.presence = "SIGNAL_PRESENT";
    st.level_mode = "AUTO";
    st.model_scale = 1.125;
    st.rf_gain_db = 33.0;
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
    return st;
}

// A representative 12-class live frame (backward-compat top-3 path).
ui::UiState base12() {
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
    st.model = "2ae95275";
    st.work_mode = "FIXED";
    st.running = true;
    st.ctl_connected = "CONTROL CONNECTED";
    return st;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string outdir = (argc > 1) ? argv[1] : "../artifacts/ui_rml23";
    std::error_code ec;
    std::filesystem::create_directories(outdir, ec);
    const ui::Theme& th = ui::theme_default();
    std::printf("make_ui_rml23_snapshots -> %s\n", outdir.c_str());

    bool ok = true;
    auto snap = [&](const char* name, const ui::UiState& st,
                    void (*fn)(ui::Canvas&, const ui::Theme&, const ui::UiState&)) {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH, th.background);
        ui::Canvas c{px.data(), kW, kH};
        fn(c, th, st);
        const std::string path = outdir + "/" + name + ".ppm";
        if (!write_ppm(path, c)) ok = false;
        else std::printf("  wrote %s\n", path.c_str());
    };
    auto snap_legend = [&](const char* name) {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(kW) * kH, th.background);
        ui::Canvas c{px.data(), kW, kH};
        ui::render_legend(c, th);
        const std::string path = outdir + "/" + name + ".ppm";
        if (!write_ppm(path, c)) ok = false;
        else std::printf("  wrote %s\n", path.c_str());
    };

    // ---- MAIN 23-class: every status ----
    {
        ui::UiState st = base23(); snap("main_live", st, ui::render_main);
        st.status = ui::Status::Stale; st.age = "3.2 s"; snap("main_stale", st, ui::render_main);
        st = base23(); st.status = ui::Status::Error; snap("main_error", st, ui::render_main);
        st = base23(); st.status = ui::Status::NoSignal; st.presence = "NO_SIGNAL";
        snap("main_nosignal", st, ui::render_main);
        st = base23(); st.status = ui::Status::Mock; st.source = "MOCK";
        snap("main_mock", st, ui::render_main);
    }
    // ---- MAIN 23-class: low confidence + worst-string class names ----
    {
        ui::UiState st = base23(); st.conf = 0.38f; st.dist[4] = 0.38f;
        snap("main_lowconf", st, ui::render_main);
        st = base23(); st.top1 = "AM-SSB"; st.conf = 0.71f;
        std::vector<float> d(23, 0.004f); d[17] = 0.71f; st.dist = d;
        snap("main_amssb", st, ui::render_main);
        st = base23(); st.top1 = "AM-DSB-SC"; st.conf = 0.66f;
        std::vector<float> d2(23, 0.005f); d2[19] = 0.66f; st.dist = d2;
        snap("main_amdsbsc", st, ui::render_main);
        st = base23(); st.top1 = "128APSK"; st.conf = 0.55f;
        std::vector<float> d3(23, 0.006f); d3[11] = 0.55f; st.dist = d3;
        snap("main_128apsk", st, ui::render_main);
    }
    // ---- MAIN 23-class: category-table pages 0..3 ----
    {
        for (int p = 0; p < 4; ++p) {
            ui::UiState st = base23(); st.category_page = p;
            char n[32]; std::snprintf(n, sizeof n, "main_page%d", p);
            snap(n, st, ui::render_main);
        }
    }
    // ---- MAIN 12-class: backward compat ----
    {
        ui::UiState st = base12(); snap("main_12class", st, ui::render_main);
    }
    // ---- PARAMETERS ----
    {
        ui::UiState st = base23(); snap("params_full", st, ui::render_parameters);
        st = base23(); st.meas.valid = false;
        snap("params_placeholder", st, ui::render_parameters);
    }
    // ---- MODE: every work mode + control state ----
    {
        ui::UiState st = base23(); st.work_mode = "FIXED"; st.running = true;
        snap("mode_fixed_running", st, ui::render_mode);
        st = base23(); st.work_mode = "AUTO LOCK"; st.running = false;
        st.requested_mode = "FIXED"; st.requested_running = false;
        st.command_status = "APPLIED"; st.last_command = "SET_MODE AUTO LOCK";
        snap("mode_autolock_stopped", st, ui::render_mode);
        st = base23(); st.work_mode = "BAND SCAN";
        snap("mode_bandscan", st, ui::render_mode);
        st = base23(); st.work_mode = "FIXED"; st.requested_mode = "AUTO LOCK";
        st.command_status = "PENDING"; st.last_command = "SET_MODE AUTO LOCK";
        st.feedback = "COMMAND IN PROGRESS";
        snap("mode_pending", st, ui::render_mode);
        st = base23(); st.ctl_connected = "CONTROL DISCONNECTED";
        st.feedback = "CONTROL DISCONNECTED";
        snap("mode_disconnected", st, ui::render_mode);
        st = base23(); st.feedback = "ALREADY IN THIS MODE";
        snap("mode_feedback", st, ui::render_mode);
    }
    // ---- DIAG ----
    {
        ui::UiState st = base23(); snap("diag_normal", st, ui::render_diag);
        st = base23(); st.status = ui::Status::Error; snap("diag_error", st, ui::render_diag);
    }
    // ---- TOUCH ----
    {
        ui::UiState st = base23();
        st.touch.connected = true; st.touch.device = "/dev/input/event2";
        st.touch.vendor = "1a86:e5e3"; st.touch.axis_x = "0 .. 4095";
        st.touch.axis_y = "0 .. 4095"; st.touch.mapping_x = "(raw_x) -> 1280px";
        st.touch.mapping_y = "(raw_y) -> 720px"; st.touch.taps = 57;
        st.touch.last_x = 640; st.touch.last_y = 360;
        snap("touch_connected", st, ui::render_touch);
        st = base23(); snap("touch_disconnected", st, ui::render_touch);
    }
    // ---- LEGEND ----
    snap_legend("legend");

    std::printf("done: %s\n", ok ? "OK" : "FAIL");
    return ok ? 0 : 1;
}
