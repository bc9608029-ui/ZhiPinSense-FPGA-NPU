// test_ui_v3_pages.cpp -- host tests for the UI v3 M5 three-page UI data plane:
// the ResultFrame -> UiState v3 mapping (measurements / presence / level / scale /
// gain) and the PARAMETERS / MODE page renderers.
//
// Links the REAL render stack (ui_sw/font_atlas.cpp + font_atlas_data.cpp +
// ui_render.cpp) so both new pages run the exact code the board draws, and is run
// under ASan/UBSan so any render out-of-bounds write is caught here, not on the
// board.
//
// Build/run: see host_tests/build_host_tests.sh (g++ -O2 -Wall -Wextra -Werror).

#include "../board_package/ui_state_map.hpp"
#include "../ui_sw/ui_render.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

bool near(double a, double b, double tol) { return std::fabs(a - b) <= tol; }

// A clean twelve-class frame carrying the full UI-v3 extension fields.
rf::ResultFrame v3_frame() {
    rf::ResultFrame r;
    r.frame_id = 9;
    r.mock = false;
    r.source = "fpga_npu";
    r.argmax_idx = 7;
    r.argmax_class = "QPSK";
    r.confidence = 0.71f;
    r.snr_db = 18.5;
    r.e2e_us = 12400.0;
    r.model_sha = "abcdef0123456789";
    r.probabilities.assign(12, 0.026363636f);
    r.probabilities[7] = 0.71f;

    r.has_measurements = true;
    r.presence_state = "SIGNAL_PRESENT";
    r.level_mode = "AUTO";
    r.model_scale = 1.125;
    r.rf_gain_db = 33.0;
    r.work_mode = "AUTO_LOCK";
    r.run_state = "RUNNING";
    r.measurements.rms_counts = 1000.0;
    r.measurements.peak_counts = 1500.0;
    r.measurements.papr_db = 3.5;
    r.measurements.clip_ratio = 0.001;
    r.measurements.power_dbfs = -6.234;
    r.measurements.noise_floor_dbfs = -50.123;
    r.measurements.psd_peak_prominence_db = 43.889;
    r.measurements.snr_est_db = 40.0;
    r.measurements.occupied_bins = 5;
    r.measurements.spectral_centroid_hz = 16000.0;
    r.measurements.occupied_bw_hz = 625.0;
    r.measurements.model_rms = 10.666;
    return r;
}

// (1) map_to_state populates the v3 fields from a full v3 frame.
void test_mapping_v3() {
    ui::UiState st = ui::map_to_state(v3_frame());

    check(st.meas.valid, "meas.valid true for has_measurements");
    check(near(st.meas.rms_counts, 1000.0, 1e-9), "rms_counts copied");
    check(near(st.meas.peak_counts, 1500.0, 1e-9), "peak_counts copied");
    check(near(st.meas.papr_db, 3.5, 1e-9), "papr_db copied");
    check(near(st.meas.clip_ratio, 0.001, 1e-9), "clip_ratio copied");
    check(near(st.meas.power_dbfs, -6.234, 1e-9), "power_dbfs copied");
    check(near(st.meas.noise_floor_dbfs, -50.123, 1e-9), "noise_floor_dbfs copied");
    check(near(st.meas.psd_peak_prominence_db, 43.889, 1e-9), "psd_peak_prominence_db copied");
    check(near(st.meas.snr_est_db, 40.0, 1e-9), "snr_est_db copied");
    check(st.meas.occupied_bins == 5, "occupied_bins copied");
    check(near(st.meas.spectral_centroid_hz, 16000.0, 1e-9), "spectral_centroid_hz copied");
    check(near(st.meas.occupied_bw_hz, 625.0, 1e-9), "occupied_bw_hz copied");
    check(near(st.meas.model_rms, 10.666, 1e-9), "model_rms copied");

    check(st.presence == "SIGNAL_PRESENT", "presence copied");
    check(st.level_mode == "AUTO", "level_mode copied");
    check(near(st.model_scale, 1.125, 1e-9), "model_scale copied");
    check(near(st.rf_gain_db, 33.0, 1e-9), "rf_gain_db copied");
    check(st.work_mode == "AUTO LOCK",
          "work_mode maps producer token AUTO_LOCK -> display AUTO LOCK");
    check(st.running, "running true when producer reports RUNNING");
}

// (2) a v1 frame (no measurements, no runtime state) leaves safe defaults.
void test_mapping_v1_defaults() {
    rf::ResultFrame r = v3_frame();
    r.has_measurements = false;
    r.presence_state.clear();
    r.level_mode.clear();
    r.work_mode.clear();
    r.run_state.clear();

    ui::UiState st = ui::map_to_state(r);
    check(!st.meas.valid, "meas.valid false without measurements");
    check(st.presence == "--", "empty presence -> \"--\"");
    check(st.level_mode == "--", "empty level_mode -> \"--\"");
    check(st.work_mode == "FIXED", "empty work_mode falls back to FIXED (never self-faked)");
    check(st.running, "empty run_state defaults to running (never STOPPED without producer)");
}

// (3) render PARAMETERS and MODE pages (valid + placeholder) into a real canvas.
std::size_t non_bg(const ui::Canvas& c, const ui::Palette& pal) {
    std::size_t n = 0;
    const std::size_t total = static_cast<std::size_t>(c.w) * c.h;
    for (std::size_t i = 0; i < total; ++i)
        if (c.px[i] != pal.bg) ++n;
    return n;
}

void test_render_pages() {
    const int W = 1280, H = 720;
    const ui::Palette& pal = ui::palette_style_a();

    // PARAMETERS with data.
    {
        ui::UiState st = ui::map_to_state(v3_frame());
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H);
        ui::Canvas c{px.data(), W, H};
        ui::render_parameters(c, pal, st);
        check(non_bg(c, pal) > 10000, "render_parameters (data) draws content");
    }
    // PARAMETERS without data (placeholders), still renders.
    {
        ui::UiState st = ui::map_to_state(v3_frame());
        st.meas.valid = false;
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H);
        ui::Canvas c{px.data(), W, H};
        ui::render_parameters(c, pal, st);
        check(non_bg(c, pal) > 10000, "render_parameters (placeholder) draws content");
    }
    // MODE for each work mode.
    const char* modes[3] = {"FIXED", "AUTO LOCK", "BAND SCAN"};
    for (const char* m : modes) {
        ui::UiState st = ui::map_to_state(v3_frame());
        st.work_mode = m;
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H);
        ui::Canvas c{px.data(), W, H};
        ui::render_mode(c, pal, st);
        check(non_bg(c, pal) > 10000,
              (std::string("render_mode ") + m + " draws content").c_str());
    }
    // MODE with an unknown mode string still renders (falls back to FIXED card).
    {
        ui::UiState st = ui::map_to_state(v3_frame());
        st.work_mode = "UNKNOWN";
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H);
        ui::Canvas c{px.data(), W, H};
        ui::render_mode(c, pal, st);
        check(non_bg(c, pal) > 10000, "render_mode unknown mode draws content");
    }
}

}  // namespace

int main() {
    std::printf("test_ui_v3_pages\n");
    test_mapping_v3();
    test_mapping_v1_defaults();
    test_render_pages();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
