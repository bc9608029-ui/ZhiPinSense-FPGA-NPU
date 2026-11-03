// test_rml24_raw_contract.cpp -- host tests for the 24-raw-class UNMERGED contract
// (M29 fix10class24-dualsdr1 §5/§6): rml24::raw24_predict argmax/margin/NaN-fail,
// AM-SSB-WC(17)/AM-SSB-SC(18) kept independent, chain::contract_24() label order,
// chain::fill_result_rml24 (raw_24_top1 == argmax, merged_23_top1 == -1,
// deployment_mode == "RAW24_UNMERGED", version == "rml24-chain-v1", class_count == 24),
// and the ui::result_frame_rml24_line serializer shape.
//
// iCraft-free and libiio-free: it exercises the exact header code the board runs.

#include "../board_package/chain_common.hpp"
#include "../board_package/rml24_raw.hpp"
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

std::vector<float> logits_peak(int peak) {
    std::vector<float> v(rml24::kClassCount, -10.0f);
    v[static_cast<std::size_t>(peak)] = 4.0f;
    return v;
}

// ---------------------------------------------------------------------------
// rml24::raw24_predict
// ---------------------------------------------------------------------------
void test_raw24_predict_argmax_and_margin() {
    std::vector<float> v = logits_peak(5);
    v[5] = 4.0f; v[7] = 1.5f;               // peak 5, runner-up 7
    rml24::RML24Result r;
    check(rml24::raw24_predict(v.data(), &r), "predict: returns true on finite logits");
    check(r.valid, "predict: valid flag set");
    check(r.raw_24_top1 == 5, "predict: argmax == 5 (8PSK)");
    check(std::string(r.raw_24_label) == "8PSK", "predict: label == 8PSK");
    check(std::fabs(r.raw_margin - 2.5f) < 1e-6f, "predict: margin == 4.0 - 1.5");
}

void test_raw24_predict_negative_logits() {
    // All-negative logits still yield a well-defined argmax (the least-negative).
    std::vector<float> v(rml24::kClassCount, -10.0f);
    v[3] = -1.0f;
    rml24::RML24Result r;
    check(rml24::raw24_predict(v.data(), &r), "predict: all-negative finite is valid");
    check(r.raw_24_top1 == 3, "predict: all-negative argmax == 3");
    check(std::string(r.raw_24_label) == "BPSK", "predict: all-negative label == BPSK");
}

void test_raw24_predict_nan_fails_closed() {
    std::vector<float> v = logits_peak(5);
    v[9] = std::numeric_limits<float>::quiet_NaN();
    rml24::RML24Result r;
    check(!rml24::raw24_predict(v.data(), &r), "predict: NaN returns false");
    check(!r.valid, "predict: NaN sets valid=false");
    v = logits_peak(5);
    v[1] = std::numeric_limits<float>::infinity();
    check(!rml24::raw24_predict(v.data(), &r), "predict: +Inf returns false");
    check(!r.valid, "predict: +Inf sets valid=false");
}

void test_raw24_predict_null_pointers() {
    std::vector<float> v = logits_peak(5);
    rml24::RML24Result r;
    check(!rml24::raw24_predict(nullptr, &r), "predict: null logits returns false");
    check(!rml24::raw24_predict(v.data(), nullptr), "predict: null out returns false");
}

void test_raw24_predict_amssb_independent() {
    // WC=17 and SC=18 stay TWO independent classes: no 24->23 fold here.
    std::vector<float> wc = logits_peak(17);
    wc[17] = 3.0f; wc[18] = 1.0f;
    rml24::RML24Result r;
    check(rml24::raw24_predict(wc.data(), &r), "predict: WC peak valid");
    check(r.raw_24_top1 == 17, "predict: WC argmax == 17");
    check(std::string(r.raw_24_label) == "AM-SSB-WC", "predict: WC label AM-SSB-WC");

    std::vector<float> sc = logits_peak(18);
    sc[17] = 1.0f; sc[18] = 3.0f;
    check(rml24::raw24_predict(sc.data(), &r), "predict: SC peak valid");
    check(r.raw_24_top1 == 18, "predict: SC argmax == 18");
    check(std::string(r.raw_24_label) == "AM-SSB-SC", "predict: SC label AM-SSB-SC");
}

// ---------------------------------------------------------------------------
// chain::contract_24() label order
// ---------------------------------------------------------------------------
void test_contract_24_label_order() {
    const cat::Contract c = chain::contract_24();
    check(c.class_count == rml24::kClassCount, "contract_24: class_count == 24");
    check(static_cast<int>(c.class_names.size()) == rml24::kClassCount,
          "contract_24: class_names width 24");
    bool order_ok = true;
    for (int i = 0; i < rml24::kClassCount; ++i) {
        if (c.class_names[static_cast<std::size_t>(i)] != rml24::kLabelOrder24[i]) {
            order_ok = false;
            break;
        }
    }
    check(order_ok, "contract_24: label order == rml24::kLabelOrder24");
    check(c.class_names[17] == "AM-SSB-WC", "contract_24: slot 17 == AM-SSB-WC");
    check(c.class_names[18] == "AM-SSB-SC", "contract_24: slot 18 == AM-SSB-SC");
    check(c.class_names[23] == "OQPSK", "contract_24: slot 23 == OQPSK");
}

// ---------------------------------------------------------------------------
// chain::fill_result_rml24
// ---------------------------------------------------------------------------
rf::ResultFrame make_rml24_frame(int peak) {
    std::vector<float> logits = logits_peak(peak);
    rf::ResultFrame r;
    r.frame_id = 7;
    r.timestamp_us = 1000;
    r.source = "fpga_npu";
    r.mock = false;
    chain::fill_result_rml24(r, logits, chain::contract_24(),
                             "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42",
                             6.0);
    return r;
}

void test_fill_result_rml24() {
    const rf::ResultFrame r = make_rml24_frame(5);
    check(r.class_count == 24, "fill: class_count == 24");
    check(r.argmax_idx == 5, "fill: argmax_idx == 5");
    check(r.argmax_class == "8PSK", "fill: argmax_class == 8PSK");
    check(r.raw_24_top1 == 5, "fill: raw_24_top1 == argmax (5)");
    check(r.merged_23_top1 == -1, "fill: merged_23_top1 == -1 (no merge)");
    check(r.deployment_mode == "RAW24_UNMERGED", "fill: deployment_mode RAW24_UNMERGED");
    check(!r.expert_enabled, "fill: expert_enabled false");
    check(r.expert_result == "NOT_RUN", "fill: expert_result NOT_RUN");
    check(r.version == "rml24-chain-v1", "fill: version rml24-chain-v1");
    check(r.model_sha == "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42",
          "fill: model_sha preserved");
    check(static_cast<int>(r.probabilities.size()) == 24,
          "fill: probabilities width 24");
    check(static_cast<int>(r.raw_24_logits.size()) == 24,
          "fill: raw_24_logits width 24");
    double psum = 0.0;
    for (float p : r.probabilities) psum += static_cast<double>(p);
    check(std::fabs(psum - 1.0) <= 1e-3, "fill: probabilities sum ~1");
}

void test_fill_result_rml24_amssb() {
    // Peak at the SC slot (18) must NOT be reported as a merged "AM-SSB": the raw24
    // path keeps the raw 24-dim argmax.
    const rf::ResultFrame r = make_rml24_frame(18);
    check(r.argmax_idx == 18, "fill AM-SSB: argmax_idx == 18");
    check(r.argmax_class == "AM-SSB-SC", "fill AM-SSB: argmax_class == AM-SSB-SC");
    check(r.raw_24_top1 == 18, "fill AM-SSB: raw_24_top1 == 18");
    check(r.merged_23_top1 == -1, "fill AM-SSB: merged_23_top1 still -1");
}

// ---------------------------------------------------------------------------
// ui::result_frame_rml24_line serializer shape
// ---------------------------------------------------------------------------
void test_result_frame_rml24_line() {
    const std::string line = ui::result_frame_rml24_line(make_rml24_frame(5));
    check(line.find("\"version\":\"rml24-chain-v1\"") != std::string::npos,
          "serialize: version rml24-chain-v1");
    check(line.find("\"model_mode\":\"RML24-BF16-RAW\"") != std::string::npos,
          "serialize: model_mode RML24-BF16-RAW");
    check(line.find("\"class_count\":24") != std::string::npos,
          "serialize: class_count 24");
    check(line.find("\"merged_23_top1\":-1") != std::string::npos,
          "serialize: merged_23_top1 -1");
    check(line.find("\"raw_24_top1\":5") != std::string::npos,
          "serialize: raw_24_top1 5");
    check(line.find("\"deployment_mode\":\"RAW24_UNMERGED\"") != std::string::npos,
          "serialize: deployment_mode RAW24_UNMERGED");
    check(line.find("\"argmax_class\":\"8PSK\"") != std::string::npos,
          "serialize: argmax_class 8PSK");
}

}  // namespace

void run_test(const char* name, void (*fn)()) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main() {
    std::printf("test_rml24_raw_contract\n");
    run_test("raw24_predict_argmax_and_margin", test_raw24_predict_argmax_and_margin);
    run_test("raw24_predict_negative_logits", test_raw24_predict_negative_logits);
    run_test("raw24_predict_nan_fails_closed", test_raw24_predict_nan_fails_closed);
    run_test("raw24_predict_null_pointers", test_raw24_predict_null_pointers);
    run_test("raw24_predict_amssb_independent", test_raw24_predict_amssb_independent);
    run_test("contract_24_label_order", test_contract_24_label_order);
    run_test("fill_result_rml24", test_fill_result_rml24);
    run_test("fill_result_rml24_amssb", test_fill_result_rml24_amssb);
    run_test("result_frame_rml24_line", test_result_frame_rml24_line);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
