// test_result_frame_parse.cpp -- host tests for the strict result_frame_v2
// JSON-lines parser + validator (task 39e5 §四/§七).
//
// Builds a canonical valid record through the SAME producer the board uses
// (chain::fill_result -> ui::result_frame_v2_line), round-trips it through
// ui::parse_result_frame_v2, then mutates individual fields / framing and asserts
// the parser rejects each with a non-empty reason.  This proves the UI server can
// never render a wrong-contract / wrong-version / malformed frame.
//
// Build/run: see host_tests/build_host_tests.sh (g++ -O2 -Wall -Wextra -Werror).

#include "../board_package/chain_common.hpp"
#include "../board_package/result_frame_v2_parse.hpp"
#include "../sdr_adapter/ui_report.hpp"

#include <cmath>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

// Canonical valid frame: argmax = index 0 ("OOK"), known model SHA.
rf::ResultFrame make_frame() {
    rf::ResultFrame r;
    r.frame_id = 7;
    r.timestamp_us = 1234567890ULL;
    r.source = "fpga_npu";
    r.mock = false;
    r.e2e_us = 1234.5;
    r.preprocess_us = 100.0;
    r.classify_us = 900.0;
    const std::vector<float> logits = {5, 4, 3, 2, 1, 0, -1, -2, -3, -4, -5, -6};
    chain::fill_result(r, logits, chain::contract_12(), "abcdef0123456789", 18.5);
    return r;
}

std::string valid_line() { return ui::result_frame_v2_line(make_frame()); }

// Replace the first occurrence of `from` with `to`; assert it was present.
std::string mutate(const std::string& s, const std::string& from,
                   const std::string& to) {
    const std::size_t p = s.find(from);
    check(p != std::string::npos, ("mutate found '" + from + "'").c_str());
    if (p == std::string::npos) return s;
    std::string out = s;
    out.replace(p, from.size(), to);
    return out;
}

// A parse must FAIL (ok == false, non-empty reason).
void expect_reject(const std::string& line, const char* what) {
    ui::ParseOutcome o = ui::parse_result_frame_v2(line);
    check(!o.ok, what);
    if (o.ok) return;
    check(!o.error.empty(), (std::string(what) + " (reason non-empty)").c_str());
}

// (1) round-trip a canonical valid record.
void test_round_trip_valid() {
    const ui::ParseOutcome o = ui::parse_result_frame_v2(valid_line());
    check(o.ok, "valid line parses");
    if (!o.ok) return;

    const rf::ResultFrame& r = o.frame;
    check(r.frame_id == 7, "frame_id == 7");
    check(r.timestamp_us == 1234567890ULL, "timestamp_us round-trip");
    check(r.class_count == 12, "class_count == 12");
    check(r.argmax_idx == 0, "argmax_idx == 0");
    check(r.argmax_class == "OOK", "argmax_class == OOK");
    check(r.version == "12class-chain-v1", "version == 12class-chain-v1");
    check(r.model_sha == "abcdef0123456789", "model_sha round-trip");
    check(r.mock == false, "mock == false");
    check(r.source == "fpga_npu", "source round-trip");
    check(r.probabilities.size() == 12, "probabilities width == 12");
    check(std::fabs(r.confidence - r.probabilities[0]) < 1e-6,
          "confidence == probabilities[argmax]");
    check(std::fabs(r.snr_db - 18.5) < 1e-3, "snr_db round-trip");
    check(r.overflow == false && r.dropped == false && r.discontinuity == false &&
              r.short_frame == false,
          "anomaly flags all false");
}

// (2) framing / malformed JSON rejections.
void test_framing_rejects() {
    expect_reject("", "empty line rejects");
    expect_reject("not json at all", "garbage rejects");
    expect_reject("{}", "empty object rejects");
    expect_reject(valid_line() + " trailing", "trailing content rejects");
    check(ui::parse_result_frame_v2(valid_line() + "\r").ok,
          "trailing CR is accepted as whitespace");
    expect_reject(mutate(valid_line(), "}", ",}"), "dangling comma rejects");
    expect_reject(valid_line().substr(0, valid_line().size() - 1), "truncated rejects");
}

// (3) contract-field rejections (each mutation must fail closed).
void test_contract_rejects() {
    const std::string v = valid_line();
    expect_reject(mutate(v, "\"type\":\"result\"", "\"type\":\"status\""),
                  "type != result rejects");
    expect_reject(mutate(v, "\"version\":\"12class-chain-v1\"",
                         "\"version\":\"9class-chain-v0\""),
                  "wrong version rejects");
    expect_reject(mutate(v, "\"class_count\":12", "\"class_count\":11"),
                  "class_count != 12 rejects");
    expect_reject(mutate(v, "\"argmax_idx\":0", "\"argmax_idx\":12"),
                  "argmax_idx out of range rejects");
    expect_reject(mutate(v, "\"argmax_idx\":0", "\"argmax_idx\":-1"),
                  "argmax_idx negative rejects");
    expect_reject(mutate(v, "\"argmax_class\":\"OOK\"", "\"argmax_class\":\"QPSK\""),
                  "argmax_class mismatch rejects");
    expect_reject(mutate(v, "\"model_sha\":\"abcdef0123456789\"",
                         "\"model_sha\":\"\""),
                  "empty model_sha rejects");
}

// (4) probabilities / confidence constraints, built through the producer.
void test_probability_rejects() {
    // width != 12
    {
        rf::ResultFrame r = make_frame();
        r.probabilities.pop_back();
        expect_reject(ui::result_frame_v2_line(r), "probabilities width != 12 rejects");
    }
    // sum != 1 (all 0.1 -> 1.2)
    {
        rf::ResultFrame r = make_frame();
        r.probabilities.assign(12, 0.1f);
        expect_reject(ui::result_frame_v2_line(r), "probabilities sum != 1 rejects");
    }
    // out of [0,1]
    {
        rf::ResultFrame r = make_frame();
        r.probabilities[3] = -0.1f;
        expect_reject(ui::result_frame_v2_line(r), "probability < 0 rejects");
    }
    {
        rf::ResultFrame r = make_frame();
        r.probabilities[3] = 1.5f;
        expect_reject(ui::result_frame_v2_line(r), "probability > 1 rejects");
    }
    // confidence != probabilities[argmax]
    {
        rf::ResultFrame r = make_frame();
        r.confidence = 0.42f;   // probabilities[0] is ~0.79
        expect_reject(ui::result_frame_v2_line(r), "confidence mismatch rejects");
    }
    // non-finite probability
    {
        rf::ResultFrame r = make_frame();
        r.probabilities[0] = static_cast<float>(NAN);
        expect_reject(ui::result_frame_v2_line(r), "non-finite probability rejects");
    }
}

// (5) null snr_db and string escaping round-trip.
void test_null_and_escaping() {
    {
        rf::ResultFrame r = make_frame();
        r.snr_db = std::numeric_limits<double>::quiet_NaN();
        ui::ParseOutcome o = ui::parse_result_frame_v2(ui::result_frame_v2_line(r));
        check(o.ok, "null snr_db parses");
        if (o.ok) check(std::isnan(o.frame.snr_db), "snr_db is NaN after null");
    }
    {
        rf::ResultFrame r = make_frame();
        r.source = "a\"b\\c";
        ui::ParseOutcome o = ui::parse_result_frame_v2(ui::result_frame_v2_line(r));
        check(o.ok, "escaped source parses");
        if (o.ok) check(o.frame.source == "a\"b\\c", "escaped source round-trips");
    }
    {
        rf::ResultFrame r = make_frame();
        r.source = std::string("ctl\x01") + "tail";
        ui::ParseOutcome o = ui::parse_result_frame_v2(ui::result_frame_v2_line(r));
        check(o.ok, "control-char source parses (\\u0001)");
        if (o.ok)
            check(o.frame.source == std::string("ctl\x01") + "tail",
                  "control-char source round-trips via \\u");
    }
    // \uXXXX decoding (raw, not via the producer).
    {
        const std::string line =
            "{\"type\":\"result\",\"version\":\"12class-chain-v1\","
            "\"frame_id\":1,\"argmax_idx\":0,\"argmax_class\":\"OOK\","
            "\"confidence\":0.5,\"class_count\":12,"
            "\"probabilities\":[0.5,0.5,0,0,0,0,0,0,0,0,0,0],"
            "\"model_sha\":\"\\u0041bc\",\"mock\":false,\"source\":\"s\"}";
        ui::ParseOutcome o = ui::parse_result_frame_v2(line);
        check(o.ok, "\\uXXXX-decoded line parses");
        if (o.ok) check(o.frame.model_sha == "Abc", "\\u0041 decodes to 'A'");
    }
}

}  // namespace

int main() {
    std::printf("test_result_frame_parse\n");
    test_round_trip_valid();
    test_framing_rejects();
    test_contract_rejects();
    test_probability_rejects();
    test_null_and_escaping();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
