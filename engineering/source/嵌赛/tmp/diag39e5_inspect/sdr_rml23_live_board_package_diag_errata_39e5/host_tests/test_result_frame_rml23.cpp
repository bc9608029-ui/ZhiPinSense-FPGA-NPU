// test_result_frame_rml23.cpp -- host tests for the RML23 23-class result record
// (M29 Phase F5, schema "rml23-chain-v2"): serializer -> strict parser round-trip
// plus the rejection matrix that keeps the 23-dim record from ever being misread
// by the 12-class parser (and vice versa).
//
// Covers F5 §八: result-protocol accept/reject, the 12/24/23 dim mismatch fail-closed,
// the AM-SSB merged verdict end-to-end, and cross-parser isolation.  iCraft-free and
// libiio-free.
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/chain_common.hpp"
#include "../board_package/result_frame_rml23_parse.hpp"
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

std::string replace_all(std::string s, const std::string& from, const std::string& to) {
    std::size_t pos = 0;
    while ((pos = s.find(from, pos)) != std::string::npos) {
        s.replace(pos, from.size(), to);
        pos += to.size();
    }
    return s;
}

// Valid 23-class RML23 frame: raw-24 peak at 5 (8PSK), merged-23 peak at 5.
rf::ResultFrame make_valid_rml23() {
    const cat::Contract c23 = chain::contract_23();
    std::vector<float> raw24(24, -10.0f);
    raw24[5] = 4.0f;
    std::vector<float> merged23(23, -10.0f);
    merged23[5] = 4.0f;
    rf::ResultFrame r;
    r.frame_id = 7;
    r.timestamp_us = 1000;
    r.source = "fpga_npu";
    r.mock = false;
    r.presence_state = "SIGNAL_PRESENT";
    r.level_mode = "FIXED";
    r.work_mode = "FIXED";
    r.run_state = "RUNNING";
    chain::fill_result_rml23(r, raw24, merged23, c23, "2425d990dbac0761", 6.0);
    return r;
}

// Valid 12-class v3 frame (schema "12class-chain-v2"): peak at 5 (8PSK).
rf::ResultFrame make_valid_12_v3() {
    std::vector<float> logits(12, -10.0f);
    logits[5] = 4.0f;
    rf::ResultFrame r;
    r.frame_id = 1;
    r.source = "fpga_npu";
    chain::fill_result(r, logits, chain::contract_12(), "2ae95275fe36", 6.0);
    r.version = "12class-chain-v2";
    return r;
}

void test_round_trip() {
    rf::ResultFrame r = make_valid_rml23();
    const std::string line = ui::result_frame_rml23_line(r);

    ui::ParseOutcome o = ui::parse_result_frame_rml23(line);
    check(o.ok, "round-trip accepts a valid RML23 record");
    if (!o.ok) { std::printf("    err=%s\n", o.error.c_str()); return; }

    const rf::ResultFrame& f = o.frame;
    check(f.version == "rml23-chain-v2", "round-trip version");
    check(f.class_count == 23, "round-trip class_count == 23");
    check(f.argmax_idx == 5, "round-trip argmax_idx == 5");
    check(f.argmax_class == "8PSK", "round-trip argmax_class == 8PSK");
    check(f.merged_23_top1 == 5, "round-trip merged_23_top1");
    check(f.raw_24_top1 == 5, "round-trip raw_24_top1");
    check(f.deployment_mode == "AMSSB_MERGED", "round-trip deployment_mode");
    check(!f.expert_enabled, "round-trip expert_enabled false");
    check(f.expert_result == "NOT_RUN", "round-trip expert_result");
    check(f.probabilities.size() == 23, "round-trip probabilities width 23");
    check(f.frame_id == 7, "round-trip frame_id");
    check(f.model_sha == "2425d990dbac0761", "round-trip model_sha");
    check(f.presence_state == "SIGNAL_PRESENT", "round-trip presence_state");
    check(f.run_state == "RUNNING", "round-trip run_state");

    double psum = 0.0;
    for (float p : f.probabilities) psum += static_cast<double>(p);
    check(std::fabs(psum - 1.0) <= 1e-3, "round-trip probabilities sum ~1");
}

// The AM-SSB merged slot (17) round-trips with label "AM-SSB", never "AM-SSB-SC/WC".
void test_amssb_slot_round_trip() {
    const cat::Contract c23 = chain::contract_23();
    std::vector<float> raw24(24, -10.0f);
    raw24[17] = std::log(2.0f);
    raw24[18] = std::log(3.0f);
    std::vector<float> merged23(23, -10.0f);
    merged23[17] = std::log(5.0f);   // logaddexp(log2,log3)
    rf::ResultFrame r;
    r.frame_id = 8;
    chain::fill_result_rml23(r, raw24, merged23, c23, "2425d990dbac0761", 6.0);

    ui::ParseOutcome o = ui::parse_result_frame_rml23(ui::result_frame_rml23_line(r));
    check(o.ok, "AM-SSB record accepted");
    check(o.frame.argmax_idx == 17, "AM-SSB argmax_idx == 17");
    check(o.frame.argmax_class == "AM-SSB", "AM-SSB argmax_class == AM-SSB");
    check(o.frame.merged_23_top1 == 17, "AM-SSB merged_23_top1 == 17");
    // raw24[18]=log3 > raw24[17]=log2, so the raw 24-dim argmax is the SC slot (18)
    // while the merged 23-dim argmax is the folded "AM-SSB" slot (17).
    check(o.frame.raw_24_top1 == 18, "AM-SSB raw_24_top1 == 18 (SC source)");
}

void test_reject_matrix() {
    const std::string line = ui::result_frame_rml23_line(make_valid_rml23());

    // version
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"version\":\"rml23-chain-v2\"", "\"version\":\"12class-chain-v2\""))
               .ok, "reject version != rml23-chain-v2");

    // model_mode
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"model_mode\":\"RML23-AMSSB-MERGED\"", "\"model_mode\":\"OTHER\""))
               .ok, "reject model_mode mismatch");

    // class_count 12 and 24 (dim mismatch fail-closed)
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"class_count\":23", "\"class_count\":12")).ok,
          "reject class_count == 12");
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"class_count\":23", "\"class_count\":24")).ok,
          "reject class_count == 24");

    // merged_23_top1 != argmax_idx
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"merged_23_top1\":5", "\"merged_23_top1\":0")).ok,
          "reject merged_23_top1 != argmax_idx");

    // raw_24_top1 out of range (24 and -1)
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"raw_24_top1\":5", "\"raw_24_top1\":24")).ok,
          "reject raw_24_top1 == 24");
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"raw_24_top1\":5", "\"raw_24_top1\":-1")).ok,
          "reject raw_24_top1 == -1");

    // deployment_mode
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"deployment_mode\":\"AMSSB_MERGED\"", "\"deployment_mode\":\"OTHER\""))
               .ok, "reject deployment_mode mismatch");

    // expert flags
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"expert_enabled\":false", "\"expert_enabled\":true")).ok,
          "reject expert_enabled == true");
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"expert_result\":\"NOT_RUN\"", "\"expert_result\":\"RAN\"")).ok,
          "reject expert_result != NOT_RUN");

    // argmax_class mismatch
    check(!ui::parse_result_frame_rml23(
              replace_all(line, "\"argmax_class\":\"8PSK\"", "\"argmax_class\":\"QPSK\"")).ok,
          "reject argmax_class mismatch");

    // probabilities width != 23 (shrink to 12 before serialize)
    {
        rf::ResultFrame r = make_valid_rml23();
        r.probabilities.resize(12);
        check(!ui::parse_result_frame_rml23(ui::result_frame_rml23_line(r)).ok,
              "reject probabilities width == 12");
    }

    // probabilities sum != 1
    {
        rf::ResultFrame r = make_valid_rml23();
        r.probabilities.assign(23, 0.0f);
        check(!ui::parse_result_frame_rml23(ui::result_frame_rml23_line(r)).ok,
              "reject probabilities sum != 1");
    }

    // empty model_sha
    {
        rf::ResultFrame r = make_valid_rml23();
        r.model_sha = "";
        check(!ui::parse_result_frame_rml23(ui::result_frame_rml23_line(r)).ok,
              "reject empty model_sha");
    }

    // malformed JSON (trailing junk)
    check(!ui::parse_result_frame_rml23(line + "junk").ok, "reject trailing content");
    check(!ui::parse_result_frame_rml23("").ok, "reject empty line");
    check(!ui::parse_result_frame_rml23("not json").ok, "reject non-JSON");
}

void test_cross_parser_isolation() {
    const std::string rml23_line = ui::result_frame_rml23_line(make_valid_rml23());
    const std::string v12_line = ui::result_frame_v3_line(make_valid_12_v3());

    // 12-class parser accepts its own record and rejects the 23-class record.
    check(ui::parse_result_frame_v2(v12_line).ok, "12-class parser accepts 12-class v3");
    check(!ui::parse_result_frame_v2(rml23_line).ok,
          "12-class parser rejects rml23-chain-v2 record");

    // RML23 parser accepts its own record and rejects the 12-class record.
    check(ui::parse_result_frame_rml23(rml23_line).ok, "rml23 parser accepts rml23 record");
    check(!ui::parse_result_frame_rml23(v12_line).ok,
          "rml23 parser rejects 12class-chain-v2 record");
}

}  // namespace

int main() {
    std::printf("test_result_frame_rml23\n");
    test_round_trip();
    test_amssb_slot_round_trip();
    test_reject_matrix();
    test_cross_parser_isolation();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
