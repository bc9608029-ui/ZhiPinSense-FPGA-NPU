// make_ui_m22_1_snapshots.cpp -- render PPM snapshots of the M22.1 UI errata
// layout for visual review before the real 7-inch screen retest.
//
// Two output sets:
//   artifacts/ui_m22_1_after/   -- the SAME 7 frozen inputs as make_ui_m19_snapshots,
//                                  so a diff against artifacts/ui_m19_before/ isolates
//                                  exactly what the M22.1 errata changed.
//   artifacts/ui_m22_1_worst/   -- worst-case inputs (longest class name, widest
//                                  measurements, over-long model SHA / source, all
//                                  status & mode-button states, fail-closed small
//                                  screen) that the boundary test also drives.
//
// Usage: make_ui_m22_1_snapshots [after-dir] [worst-dir]
//   defaults: ../artifacts/ui_m22_1_after ../artifacts/ui_m22_1_worst
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

// A representative Live 12-class frame (QPSK @ 0.71) -- identical to the M19 tool.
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

// 24-class contract with the longest names the renderer may ever receive.
const std::vector<std::string>& classes_24_long() {
    static const std::vector<std::string> v = {
        "OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK",
        "16APSK","32APSK","64APSK","128APSK","16QAM","32QAM","64QAM",
        "128QAM","256QAM","AM-SSB-WC","AM-SSB-SC","AM-DSB-WC","AM-DSB-SC",
        "FM","GMSK","OQPSK"
    };
    return v;
}

ui::UiState params_worst() {
    ui::UiState st = base();
    st.meas.valid = true;
    st.meas.rms_counts = 1234.5;
    st.meas.peak_counts = 9999.9;
    st.meas.papr_db = 12.34;
    st.meas.clip_ratio = 0.5;
    st.meas.power_dbfs = -123.45;
    st.meas.noise_floor_dbfs = -123.45;
    st.meas.psd_peak_prominence_db = 99.999;
    st.meas.snr_est_db = 123.4;
    st.meas.occupied_bins = 999999;
    st.meas.spectral_centroid_hz = 999999.9;
    st.meas.occupied_bw_hz = 123456.7;
    st.meas.model_rms = 999.999;
    st.presence = "SIGNAL_PRESENT";
    st.level_mode = "AUTO LOCK";
    st.model_scale = 123.456;
    st.rf_gain_db = 123.4;
    st.source = "EXTERNAL ANTENNA";
    st.snr = "+123.4 dB";
    st.lat = "999.9 ms";
    st.frame = "100000";
    st.model = "1234567890abcdef";
    return st;
}

struct Snapper {
    const ui::Theme& th;
    std::string dir;
    bool ok = true;

    void snap(const char* name, const ui::UiState& st,
              void (*fn)(ui::Canvas&, const ui::Theme&, const ui::UiState&)) {
        snap_size(name, st, fn, 1280, 720);
    }
    void snap_size(const char* name, const ui::UiState& st,
                   void (*fn)(ui::Canvas&, const ui::Theme&, const ui::UiState&),
                   int W, int H) {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H, th.background);
        ui::Canvas c{px.data(), W, H};
        fn(c, th, st);
        const std::string path = dir + "/" + name + ".ppm";
        if (!write_ppm(path, c)) { ok = false; return; }
        std::printf("  wrote %s\n", path.c_str());
    }
};

bool render_after(const std::string& dir) {
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);
    const ui::Theme& th = ui::theme_default();
    Snapper s{th, dir};

    { ui::UiState st = base(); s.snap("main_live", st, ui::render_main); }
    { ui::UiState st = base(); st.status = ui::Status::Stale; st.age = "3.2 s";
      s.snap("main_stale", st, ui::render_main); }
    { ui::UiState st = base(); st.status = ui::Status::Error;
      s.snap("main_error", st, ui::render_main); }
    { ui::UiState st = base(); st.status = ui::Status::Mock; st.source = "MOCK";
      s.snap("main_mock", st, ui::render_main); }

    {
        ui::UiState st = base();
        st.meas.valid = true;
        st.meas.rms_counts = 1000.0; st.meas.peak_counts = 1500.0;
        st.meas.papr_db = 3.5; st.meas.clip_ratio = 0.001;
        st.meas.power_dbfs = -6.234; st.meas.noise_floor_dbfs = -50.123;
        st.meas.psd_peak_prominence_db = 43.889; st.meas.snr_est_db = 40.0;
        st.meas.occupied_bins = 5; st.meas.spectral_centroid_hz = 16000.0;
        st.meas.occupied_bw_hz = 625.0; st.meas.model_rms = 10.666;
        st.presence = "SIGNAL_PRESENT"; st.level_mode = "AUTO";
        st.model_scale = 1.125; st.rf_gain_db = 33.0;
        s.snap("parameters", st, ui::render_parameters);
    }
    {
        ui::UiState st = base();
        st.work_mode = "AUTO LOCK"; st.running = false;
        st.requested_mode = "FIXED"; st.requested_running = false;
        st.command_status = "APPLIED"; st.last_command = "SET_MODE AUTO LOCK";
        st.feedback = "ALREADY IN THIS MODE";
        s.snap("mode_stopped", st, ui::render_mode);
    }
    {
        std::vector<std::uint16_t> px(static_cast<std::size_t>(1280) * 720, th.background);
        ui::Canvas c{px.data(), 1280, 720};
        ui::render_legend(c, th);
        const std::string path = dir + "/legend.ppm";
        if (!write_ppm(path, c)) s.ok = false;
        else std::printf("  wrote %s\n", path.c_str());
    }
    return s.ok;
}

bool render_worst(const std::string& dir) {
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);
    const ui::Theme& th = ui::theme_default();
    Snapper s{th, dir};

    // longest class name drives the 40px top-1 + a top-3 row
    {
        ui::UiState st = base();
        st.classes = &classes_24_long();
        std::vector<float> d(24, 0.005f);
        d[17] = 0.71f; d[20] = 0.10f; d[3] = 0.08f;
        st.dist = d; st.top1 = "AM-SSB-WC";
        s.snap("main_long_class", st, ui::render_main);
    }
    // widest measurements + over-long model SHA + over-long source
    s.snap("parameters_worst", params_worst(), ui::render_parameters);
    // three distinct mode-button states
    {
        ui::UiState st = base(); st.work_mode = "AUTO LOCK";
        st.requested_mode = "BAND SCAN"; st.command_status = "PENDING";
        s.snap("mode_pending", st, ui::render_mode);
    }
    {
        ui::UiState st = base(); st.work_mode = "BAND SCAN";
        st.requested_mode = "BAND SCAN"; st.command_status = "APPLIED";
        s.snap("mode_selected", st, ui::render_mode);
    }
    {
        ui::UiState st = base(); st.running = false; st.requested_running = false;
        st.command_status = "REJECTED"; st.feedback = "ALREADY IN THIS MODE";
        st.last_command = "SET_MODE AUTO LOCK"; st.ctl_connected = "CONTROL DISCONNECTED";
        s.snap("mode_idle", st, ui::render_mode);
    }
    s.snap("diag", base(), ui::render_diag);
    {
        ui::UiState st = base();
        st.touch.device = "/dev/input/event2"; st.touch.vendor = "1a86:e5e3";
        st.touch.axis_x = "0 .. 4095"; st.touch.mapping_x = "raw_x*1280/4095";
        st.touch.last_x = 640; st.touch.last_y = 360;
        s.snap("touch", st, ui::render_touch);
    }
    // fail-closed small screen (below the 640x720 minimum)
    s.snap_size("main_small_640x480", base(), ui::render_main, 640, 480);
    return s.ok;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string after = (argc > 1) ? argv[1] : "../artifacts/ui_m22_1_after";
    const std::string worst = (argc > 2) ? argv[2] : "../artifacts/ui_m22_1_worst";
    std::printf("make_ui_m22_1_snapshots -> %s / %s\n", after.c_str(), worst.c_str());
    bool ok = render_after(after);
    ok = render_worst(worst) && ok;
    return ok ? 0 : 1;
}
