// test_waterfall_protocol.cpp -- host tests for the display-spectrum protocol
// (fix10class24-waterfall1, Phase C).
//
// The six optional spectrum fields are serialized by ui_report.hpp into the
// nested `measurements` object (v3/rml23/rml24 lines) and parsed fail-closed by
// result_frame_v2_parse.hpp::parse_measurements.  Pinned here:
//   * round-trip: serialize -> parse reproduces every spectrum field;
//   * legacy compatibility: a measurements object with NO spectrum keys parses
//     to spectrum_valid=false (old records keep working);
//   * fail-closed: length != 256, out-of-range, non-integer, missing metadata,
//     bin_count != 256 and fft_length != 1024 all reject the record;
//   * single-message size is bounded and recorded.

#include "../sdr_adapter/ui_report.hpp"
#include "../board_package/result_frame_v2_parse.hpp"

#include <cstdio>
#include <string>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

// A 256-element dbfs_x4 array of `n` entries (all -100).
std::string spec_array(int n) {
    std::string s = "[";
    for (int i = 0; i < n; ++i) {
        if (i) s += ',';
        s += "-100";
    }
    s += ']';
    return s;
}

// Full v3 (12-class-chain-v2) record with `mjson` as the measurements object.
std::string make_record(const std::string& mjson) {
    std::string s =
        "{\"type\":\"result\",\"version\":\"12class-chain-v2\",\"frame_id\":1,"
        "\"timestamp_us\":0,\"argmax_idx\":0,\"argmax_class\":\"OOK\","
        "\"confidence\":0.9,\"class_count\":12,"
        "\"probabilities\":[0.9,0.1,0,0,0,0,0,0,0,0,0,0],"
        "\"snr_db\":10.0,\"quality\":0.5,\"model_sha\":\"abcdef01\","
        "\"mock\":false,\"source\":\"s\",\"e2e_us\":1.0,\"preprocess_us\":1.0,"
        "\"classify_us\":1.0,\"overflow\":false,\"dropped\":false,"
        "\"discontinuity\":false,\"short_frame\":false,"
        "\"presence_state\":\"SIGNAL_PRESENT\",\"level_mode\":\"FIXED\","
        "\"model_scale\":1.0,\"rf_gain_db\":0.0,\"work_mode\":\"FIXED\","
        "\"run_state\":\"RUNNING\",\"measurements\":" + mjson + "}";
    return s;
}

// Legacy measurements object (the pre-waterfall shape, no spectrum keys).
std::string legacy_measurements() {
    return "{\"rms_counts\":100.0,\"peak_counts\":150.0,\"papr_db\":3.5,"
           "\"clip_ratio\":0.0,\"power_dbfs\":-6.0,\"noise_floor_dbfs\":-50.0,"
           "\"psd_peak_prominence_db\":44.0,\"snr_est_db\":40.0,"
           "\"occupied_bins\":5,\"spectral_centroid_hz\":16000.0,"
           "\"occupied_bw_hz\":625.0,\"model_rms\":0.05}";
}

// Build a full rf::ResultFrame with a valid spectrum, for the serializer path.
rf::ResultFrame build_frame() {
    rf::ResultFrame r;
    r.frame_id = 1;
    r.timestamp_us = 0;
    r.version = "12class-chain-v2";
    r.class_count = 12;
    r.argmax_idx = 0;
    r.argmax_class = "OOK";
    r.confidence = 0.9f;
    r.probabilities.assign(12, 0.0f);
    r.probabilities[0] = 0.9f;
    r.probabilities[1] = 0.1f;
    r.snr_db = 10.0;
    r.quality = 0.5;
    r.model_sha = "abcdef01";
    r.mock = false;
    r.source = "s";
    r.e2e_us = 1.0;
    r.preprocess_us = 1.0;
    r.classify_us = 1.0;
    r.presence_state = "SIGNAL_PRESENT";
    r.level_mode = "FIXED";
    r.model_scale = 1.0;
    r.rf_gain_db = 0.0;
    r.work_mode = "FIXED";
    r.run_state = "RUNNING";
    r.has_measurements = true;
    r.measurements.rms_counts = 100.0;
    r.measurements.peak_counts = 150.0;
    r.measurements.papr_db = 3.5;
    r.measurements.clip_ratio = 0.0;
    r.measurements.power_dbfs = -6.0;
    r.measurements.noise_floor_dbfs = -50.0;
    r.measurements.psd_peak_prominence_db = 44.0;
    r.measurements.snr_est_db = 40.0;
    r.measurements.occupied_bins = 5;
    r.measurements.spectral_centroid_hz = 16000.0;
    r.measurements.occupied_bw_hz = 625.0;
    r.measurements.model_rms = 0.05;
    r.measurements.spectrum_valid = true;
    r.measurements.spectrum_fft_length = 1024;
    r.measurements.spectrum_bin_count = 256;
    for (int b = 0; b < 256; ++b) r.measurements.spectrum_dbfs_x4[b] = -100 + (b % 7);
    r.measurements.spectrum_sample_rate_hz = 2560000.0;
    r.measurements.spectrum_center_hz = 2400000000.0;
    return r;
}

// (1) serializer -> parser round-trip reproduces every spectrum field.
void test_round_trip() {
    const rf::ResultFrame src = build_frame();
    const std::string line = ui::result_frame_v3_line(src);
    const ui::ParseOutcome o = ui::parse_result_frame_v3(line);

    check(o.ok, "serialized v3 record parses");
    check(o.frame.has_measurements, "measurements present after parse");
    const sdr::FrameMeasurements& m = o.frame.measurements;
    check(m.spectrum_valid, "spectrum_valid round-trips");
    check(m.spectrum_fft_length == 1024, "fft_length round-trips");
    check(m.spectrum_bin_count == 256, "bin_count round-trips");
    check(m.spectrum_sample_rate_hz == 2560000.0, "sample_rate round-trips");
    check(m.spectrum_center_hz == 2400000000.0, "center_hz round-trips");
    bool bins_ok = true;
    for (int b = 0; b < 256; ++b)
        if (m.spectrum_dbfs_x4[b] != src.measurements.spectrum_dbfs_x4[b])
            bins_ok = false;
    check(bins_ok, "all 256 dbfs_x4 values round-trip exactly");
}

// (2) a legacy measurements object (no spectrum keys) parses to spectrum_valid=false.
void test_legacy_compatible() {
    const ui::ParseOutcome o = ui::parse_result_frame_v3(make_record(legacy_measurements()));
    check(o.ok, "legacy record (no spectrum keys) still parses");
    check(!o.frame.measurements.spectrum_valid,
          "legacy record -> spectrum_valid false (no heatmap)");
}

// (3) array length != 256 rejects the record.
void test_fail_length() {
    const std::string m =
        "{\"rms_counts\":1.0,\"spectrum_valid\":true,\"spectrum_fft_length\":1024,"
        "\"spectrum_bin_count\":256,\"spectrum_dbfs_x4\":" + spec_array(255) +
        ",\"spectrum_sample_rate_hz\":2560000.0,\"spectrum_center_hz\":1.0}";
    check(!ui::parse_result_frame_v3(make_record(m)).ok, "255-element array -> reject");
}

// (4) out-of-range value rejects the record.
void test_fail_out_of_range() {
    const std::string m =
        "{\"rms_counts\":1.0,\"spectrum_valid\":true,\"spectrum_fft_length\":1024,"
        "\"spectrum_bin_count\":256,\"spectrum_dbfs_x4\":" + spec_array(256) +
        ",\"spectrum_sample_rate_hz\":2560000.0,\"spectrum_center_hz\":1.0}";
    // splice a single out-of-range value into the array
    std::string mm = m;
    const std::string needle = "-100";
    mm.replace(mm.find(needle), needle.size(), "1");
    check(!ui::parse_result_frame_v3(make_record(mm)).ok, "value > 0 -> reject");
}

// (5) non-integer array value rejects the record.
void test_fail_non_integer() {
    const std::string m =
        "{\"rms_counts\":1.0,\"spectrum_valid\":true,\"spectrum_fft_length\":1024,"
        "\"spectrum_bin_count\":256,\"spectrum_dbfs_x4\":" + spec_array(256) +
        ",\"spectrum_sample_rate_hz\":2560000.0,\"spectrum_center_hz\":1.0}";
    std::string mm = m;
    const std::string needle = "-100";
    mm.replace(mm.find(needle), needle.size(), "1.5");
    check(!ui::parse_result_frame_v3(make_record(mm)).ok, "non-integer value -> reject");
}

// (6) spectrum_valid=true but missing metadata rejects the record.
void test_fail_missing_metadata() {
    const std::string m =
        "{\"rms_counts\":1.0,\"spectrum_valid\":true,\"spectrum_fft_length\":1024,"
        "\"spectrum_bin_count\":256,\"spectrum_dbfs_x4\":" + spec_array(256) + "}";
    check(!ui::parse_result_frame_v3(make_record(m)).ok,
          "valid=true without sample_rate/center -> reject");
}

// (7) bin_count != 256 rejects the record.
void test_fail_bin_count() {
    const std::string m =
        "{\"rms_counts\":1.0,\"spectrum_valid\":true,\"spectrum_fft_length\":1024,"
        "\"spectrum_bin_count\":255,\"spectrum_dbfs_x4\":" + spec_array(256) +
        ",\"spectrum_sample_rate_hz\":2560000.0,\"spectrum_center_hz\":1.0}";
    check(!ui::parse_result_frame_v3(make_record(m)).ok, "bin_count 255 -> reject");
}

// (8) fft_length != 1024 rejects the record.
void test_fail_fft_length() {
    const std::string m =
        "{\"rms_counts\":1.0,\"spectrum_valid\":true,\"spectrum_fft_length\":512,"
        "\"spectrum_bin_count\":256,\"spectrum_dbfs_x4\":" + spec_array(256) +
        ",\"spectrum_sample_rate_hz\":2560000.0,\"spectrum_center_hz\":1.0}";
    check(!ui::parse_result_frame_v3(make_record(m)).ok, "fft_length 512 -> reject");
}

// (9) the single-message size of a full spectrum record is bounded and recorded.
void test_message_size() {
    const std::string line = ui::result_frame_v3_line(build_frame());
    std::printf("  rml24/rml23/v3 spectrum message size = %zu bytes\n", line.size());
    check(line.size() > 0 && line.size() < 4096, "spectrum message fits well under 4 KiB");
}

}  // namespace

int main() {
    std::printf("test_waterfall_protocol\n");
    test_round_trip();
    test_legacy_compatible();
    test_fail_length();
    test_fail_out_of_range();
    test_fail_non_integer();
    test_fail_missing_metadata();
    test_fail_bin_count();
    test_fail_fft_length();
    test_message_size();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
