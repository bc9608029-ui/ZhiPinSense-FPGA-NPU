// test_result_frame_v2.cpp -- host tests for the twelve-class result-frame
// JSONL record (sdr_adapter/ui_report.hpp result_frame_v2_line + result_frame.hpp
// §七 fields + chain fill_result).  iCraft-free and libiio-free.
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/chain_common.hpp"
#include "../sdr_adapter/ui_report.hpp"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

bool well_formed_object(const std::string& line) {
    if (line.size() < 2 || line.front() != '{' || line.back() != '}') return false;
    int depth = 0;
    bool in_str = false, esc = false;
    for (char c : line) {
        if (esc) { esc = false; continue; }
        if (in_str) {
            if (c == '\\') esc = true;
            else if (c == '"') in_str = false;
            continue;
        }
        if (c == '"') in_str = true;
        else if (c == '{' || c == '[') ++depth;
        else if (c == '}' || c == ']') --depth;
        if (depth < 0) return false;
    }
    return !in_str && depth == 0;
}

void test_v2_record() {
    const cat::Contract c = chain::contract_12();
    std::vector<float> logits(12, 0.0f);
    logits[9] = 4.0f;   // 16QAM
    rf::ResultFrame r;
    r.frame_id = 42;
    r.timestamp_us = 123456789;
    r.source = "fpga_npu";
    r.mock = false;
    r.overflow = true;
    chain::fill_result(r, logits, c, "2ae95275fe36", 8.7);

    const std::string rec = ui::result_frame_v2_line(r);
    check(well_formed_object(rec), "v2 line is a well-formed JSON object");
    check(rec.find("\"type\":\"result\"") != std::string::npos, "v2 line has type=result");
    check(rec.find("\"version\":\"12class-chain-v1\"") != std::string::npos, "v2 has version");
    check(rec.find("\"frame_id\":42") != std::string::npos, "v2 has frame_id");
    check(rec.find("\"argmax_idx\":9") != std::string::npos, "v2 has argmax_idx=9");
    check(rec.find("\"argmax_class\":\"16QAM\"") != std::string::npos, "v2 has argmax_class");
    check(rec.find("\"class_count\":12") != std::string::npos, "v2 has class_count=12");
    check(rec.find("\"model_sha\":\"2ae95275fe36\"") != std::string::npos, "v2 has model_sha");
    check(rec.find("\"snr_db\":8.700") != std::string::npos, "v2 has snr_db");
    check(rec.find("\"mock\":false") != std::string::npos, "v2 has mock=false");
    check(rec.find("\"source\":\"fpga_npu\"") != std::string::npos, "v2 has source");
    check(rec.find("\"overflow\":true") != std::string::npos, "v2 has overflow=true");
    check(rec.find("\"probabilities\":[") != std::string::npos, "v2 has probabilities array");
    check(rec.find("\"quality\":") != std::string::npos, "v2 has quality");
}

void test_v2_nan_snr() {
    const cat::Contract c = chain::contract_12();
    std::vector<float> logits(12, 0.0f);
    rf::ResultFrame r;
    chain::fill_result(r, logits, c, "", 0.0 / 0.0);   // NaN snr
    const std::string rec = ui::result_frame_v2_line(r);
    check(rec.find("\"snr_db\":null") != std::string::npos, "NaN snr_db serialized as null");
    check(well_formed_object(rec), "NaN-snr line still well-formed");
}

void test_json_escape() {
    const std::string e = ui::json_escape("a\"b\\c\nd");
    check(e == "a\\\"b\\\\c\\nd", "json_escape escapes quote/backslash/newline");
}

void test_stdout_sink_no_throw() {
    ui::StdoutSink sink;
    sink.write("{\"type\":\"status\",\"state\":\"done\"}");
    check(true, "StdoutSink.write does not throw");
}

}  // namespace

int main() {
    std::printf("test_result_frame_v2\n");
    test_v2_record();
    test_v2_nan_snr();
    test_json_escape();
    test_stdout_sink_no_throw();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
