// test_result_frame_v3.cpp -- host tests for the UI-v3 ResultFrame extension
// (task 39e5 UI v3 M4): schema "12class-chain-v2" serialization + parsing.
//
// Round-trips a canonical v3 record through the SAME producer the board uses
// (ui::result_frame_v3_line) into ui::parse_result_frame_v3, then verifies:
//   - every M1/M2/M3 extension field round-trips (presence_state, level_mode,
//     model_scale, rf_gain_db, and the 12 nested `measurements` scalars);
//   - measurements == null round-trips to has_measurements == false;
//   - "12class-chain-v1" records still parse (backward-compatible) via the v3
//     alias, and via parse_result_frame_v2;
//   - a v2 record missing a REQUIRED extension field is rejected;
//   - a malformed `measurements` value (non-integer occupied_bins) is rejected.
//
// Build/run: see host_tests/build_host_tests.sh (g++ -O2 -Wall -Wextra -Werror).

#include "../board_package/chain_common.hpp"
#include "../board_package/result_frame_v2_parse.hpp"
#include "../sdr_adapter/ui_report.hpp"

#include <cmath>
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

// Base twelve-class frame (same producer the board uses), then stamped with the
// UI-v3 extension fields and re-tagged to schema "12class-chain-v2".
rf::ResultFrame make_v3_frame() {
    rf::ResultFrame r;
    r.frame_id = 42;
    r.timestamp_us = 9876543210ULL;
    r.source = "fpga_npu";
    r.mock = false;
    r.e2e_us = 2100.0;
    r.preprocess_us = 150.0;
    r.classify_us = 1200.0;
    const std::vector<float> logits = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
    chain::fill_result(r, logits, chain::contract_12(), "0123456789abcdef", 24.0);
    r.version = "12class-chain-v2";

    r.has_measurements = true;
    r.presence_state = "SIGNAL_PRESENT";
    r.level_mode = "AUTO";
    r.model_scale = 1.125;
    r.rf_gain_db = 33.0;
    r.work_mode = "AUTO_LOCK";
    r.run_state = "RUNNING";

    sdr::FrameMeasurements& m = r.measurements;
    m.rms_counts = 1000.0;
    m.peak_counts = 1500.0;
    m.papr_db = 3.521825;
    m.clip_ratio = 0.001;
    m.power_dbfs = -6.234;
    m.noise_floor_dbfs = -50.123;
    m.psd_peak_prominence_db = 43.889;
    m.snr_est_db = 40.0;
    m.occupied_bins = 5;
    m.spectral_centroid_hz = 16000.0;
    m.occupied_bw_hz = 625.0;
    m.model_rms = 10.666;
    return r;
}

// (1) full v3 round-trip: every extension field must survive serialize->parse.
void test_v3_round_trip() {
    const ui::ParseOutcome o = ui::parse_result_frame_v3(ui::result_frame_v3_line(make_v3_frame()));
    check(o.ok, "valid v3 line parses");
    if (!o.ok) return;

    const rf::ResultFrame& r = o.frame;
    check(r.version == "12class-chain-v2", "version == 12class-chain-v2");
    check(r.frame_id == 42, "frame_id == 42");
    check(r.argmax_idx == 11, "argmax_idx == 11 (max logit at 12)");
    check(r.argmax_class == "OFDM", "argmax_class == OFDM");
    check(r.presence_state == "SIGNAL_PRESENT", "presence_state round-trip");
    check(r.level_mode == "AUTO", "level_mode round-trip");
    check(near(r.model_scale, 1.125, 1e-6), "model_scale round-trip");
    check(near(r.rf_gain_db, 33.0, 1e-3), "rf_gain_db round-trip");
    check(r.work_mode == "AUTO_LOCK", "work_mode round-trip");
    check(r.run_state == "RUNNING", "run_state round-trip");
    check(r.has_measurements == true, "has_measurements == true");

    const sdr::FrameMeasurements& m = r.measurements;
    check(near(m.rms_counts, 1000.0, 1e-5), "rms_counts round-trip");
    check(near(m.peak_counts, 1500.0, 1e-5), "peak_counts round-trip");
    check(near(m.papr_db, 3.521825, 1e-5), "papr_db round-trip");
    check(near(m.clip_ratio, 0.001, 1e-5), "clip_ratio round-trip");
    check(near(m.power_dbfs, -6.234, 1e-3), "power_dbfs round-trip");
    check(near(m.noise_floor_dbfs, -50.123, 1e-3), "noise_floor_dbfs round-trip");
    check(near(m.psd_peak_prominence_db, 43.889, 1e-3), "psd_peak_prominence_db round-trip");
    check(near(m.snr_est_db, 40.0, 1e-3), "snr_est_db round-trip");
    check(m.occupied_bins == 5, "occupied_bins round-trip");
    check(near(m.spectral_centroid_hz, 16000.0, 1e-3), "spectral_centroid_hz round-trip");
    check(near(m.occupied_bw_hz, 625.0, 1e-3), "occupied_bw_hz round-trip");
    check(near(m.model_rms, 10.666, 1e-5), "model_rms round-trip");
}

// (2) measurements == null -> has_measurements == false.
void test_v3_null_measurements() {
    rf::ResultFrame r = make_v3_frame();
    r.has_measurements = false;
    const ui::ParseOutcome o = ui::parse_result_frame_v3(ui::result_frame_v3_line(r));
    check(o.ok, "v3 line with null measurements parses");
    if (o.ok) check(o.frame.has_measurements == false, "has_measurements == false after null");
}

// (3) backward compatibility: v1 records still parse (both entry points).
void test_v1_backward_compat() {
    rf::ResultFrame r = make_v3_frame();
    r.version = "12class-chain-v1";
    r.has_measurements = false;
    const std::string line = ui::result_frame_v2_line(r);

    ui::ParseOutcome o2 = ui::parse_result_frame_v2(line);
    check(o2.ok, "v1 line parses via parse_result_frame_v2");
    if (o2.ok) check(o2.frame.version == "12class-chain-v1", "v1 version preserved");

    ui::ParseOutcome o3 = ui::parse_result_frame_v3(line);
    check(o3.ok, "v1 line parses via parse_result_frame_v3 alias");
    if (o3.ok) {
        check(o3.frame.presence_state.empty(), "v1 record leaves presence_state empty");
        check(o3.frame.has_measurements == false, "v1 record leaves has_measurements false");
    }
}

// (4) a v2 record MUST carry the extension fields; a v1 line re-tagged to v2
// (which lacks them) must be rejected.
void test_v2_requires_extension() {
    rf::ResultFrame r = make_v3_frame();
    r.version = "12class-chain-v1";
    r.has_measurements = false;
    std::string line = ui::result_frame_v2_line(r);
    const std::size_t p = line.find("\"version\":\"12class-chain-v1\"");
    check(p != std::string::npos, "found version tag to mutate");
    if (p == std::string::npos) return;
    line.replace(p, std::string("\"version\":\"12class-chain-v1\"").size(),
                 "\"version\":\"12class-chain-v2\"");

    ui::ParseOutcome o = ui::parse_result_frame_v3(line);
    check(!o.ok, "v2 missing extension field rejects");
    if (o.ok) return;
    check(o.error.find("extension") != std::string::npos, "reason names the missing extension");
}

// (5) a malformed measurements value is rejected (occupied_bins must be an int).
void test_v2_malformed_measurements() {
    std::string line = ui::result_frame_v3_line(make_v3_frame());
    const std::size_t p = line.find("\"occupied_bins\":5");
    check(p != std::string::npos, "found occupied_bins to mutate");
    if (p == std::string::npos) return;
    line.replace(p, std::string("\"occupied_bins\":5").size(), "\"occupied_bins\":5.5");

    ui::ParseOutcome o = ui::parse_result_frame_v3(line);
    check(!o.ok, "non-integer occupied_bins rejects");
    if (o.ok) return;
    check(!o.error.empty(), "reason non-empty for malformed measurements");
}

}  // namespace

int main() {
    std::printf("test_result_frame_v3\n");
    test_v3_round_trip();
    test_v3_null_measurements();
    test_v1_backward_compat();
    test_v2_requires_extension();
    test_v2_malformed_measurements();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
