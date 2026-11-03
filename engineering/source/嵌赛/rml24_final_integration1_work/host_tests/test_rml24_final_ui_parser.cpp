#include "../board_ui_overlay/board_package/result_frame_rml24_final_parse.hpp"

#include <iostream>
#include <sstream>
#include <string>

namespace {
std::string valid_record() {
    std::ostringstream s;
    s << R"({"type":"result","version":"rml24-final-chain-v1",)"
      << R"("frame_id":7,"timestamp_us":9,"model_mode":"RML24-BF16-RAW",)"
      << R"("class_count":24,"argmax_idx":4,"argmax_class":"QPSK",)"
      << R"("confidence":1,"merged_23_top1":-1,"raw_24_top1":4,)"
      << R"("deployment_mode":"RAW24_UNMERGED","expert_enabled":false,)"
      << R"("expert_result":"NOT_RUN","probabilities":[)";
    for (int i = 0; i < 24; ++i) { if (i) s << ','; s << (i == 4 ? 1 : 0); }
    s << R"(],"snr_db":null,"quality":1,"model_sha":"abc",)"
      << R"("mock":false,"source":"rml24_final_receiver","e2e_us":0,)"
      << R"("preprocess_us":0,"classify_us":0,"overflow":false,)"
      << R"("dropped":false,"discontinuity":false,"short_frame":false,)"
      << R"("presence_state":"SIGNAL_PRESENT","level_mode":"FIXED",)"
      << R"("model_scale":1,"rf_gain_db":35,"work_mode":"FIXED",)"
      << R"("run_state":"RUNNING","measurements":{"spectrum_valid":true,)"
      << R"("spectrum_fft_length":1024,"spectrum_bin_count":256,)"
      << R"("spectrum_sample_rate_hz":2560000,"spectrum_center_hz":2400000000,)"
      << R"("spectrum_dbfs_x4":[)";
    for (int i = 0; i < 256; ++i) { if (i) s << ','; s << (i == 128 ? 0 : -120); }
    s << R"(]},"iq_valid":true,"iq_i16_interleaved":[)";
    for (int i = 0; i < 512; ++i) { if (i) s << ','; s << ((i % 2 == 0) ? 1000 : -1000); }
    s << R"(],"iq_units_per_count":0.001})";
    return s.str();
}

bool replace_one(std::string& value, const std::string& from, const std::string& to) {
    const std::size_t p = value.find(from);
    if (p == std::string::npos) return false;
    value.replace(p, from.size(), to);
    return true;
}
}  // namespace

int main() {
    int passed = 0;
    const std::string good = valid_record();
    const ui::ParseOutcome parsed = ui::parse_result_frame_rml24_final(good);
    if (!parsed.ok) { std::cerr << "valid frame rejected: " << parsed.error << '\n'; return 1; }
    if (parsed.frame.class_count != 24 || parsed.frame.argmax_class != "QPSK" ||
        !parsed.frame.iq_display_valid || parsed.frame.iq_i16_interleaved.size() != 512 ||
        parsed.frame.iq_i16_interleaved[0] != 1000 || parsed.frame.iq_i16_interleaved[1] != -1000) return 1;
    ++passed;
    std::string wrong_width = good;
    replace_one(wrong_width, "\"class_count\":24", "\"class_count\":23");
    if (ui::parse_result_frame_rml24_final(wrong_width).ok) return 2;
    ++passed;
    std::string merged = good;
    replace_one(merged, "\"merged_23_top1\":-1", "\"merged_23_top1\":4");
    if (ui::parse_result_frame_rml24_final(merged).ok) return 3;
    ++passed;
    std::string bad_iq = good;
    replace_one(bad_iq, "\"iq_units_per_count\":0.001", "\"iq_units_per_count\":0");
    if (ui::parse_result_frame_rml24_final(bad_iq).ok) return 4;
    ++passed;
    std::cout << "RML24_FINAL_UI_PARSER pass=" << passed << " fail=0\n";
    return 0;
}
