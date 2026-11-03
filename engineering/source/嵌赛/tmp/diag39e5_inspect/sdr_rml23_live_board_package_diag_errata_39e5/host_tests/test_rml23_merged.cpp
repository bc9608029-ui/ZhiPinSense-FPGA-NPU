// test_rml23_merged.cpp -- host tests for the RML23 24->23 AM-SSB merge
// (board_package/rml23_merged.hpp) and the RML23 result-frame filling
// (board_package/chain_common.hpp fill_result_rml23).  iCraft-free and libiio-free:
// it exercises the exact code the board runs for the deployed 23-class verdict.
//
// Covers F5 §八: the 23-class merge (copy-through + AM-SSB logaddexp fold +
// fail-closed), the 12/24/23 dim contracts, and the label-order equivalence that
// keeps the deployed order frozen (the frozen label SHA 15072cd2... is asserted
// structurally: rml23::kLabelOrder23 == cat::target_23()).
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/chain_common.hpp"
#include "../board_package/rml23_merged.hpp"

#include <cmath>
#include <cstddef>
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

void check_near(double got, double want, double tol, const char* what) {
    const bool ok = std::fabs(got - want) <= tol;
    if (ok) ++g_pass;
    else {
        ++g_fail;
        std::printf("  FAIL: %s (got %.9g want %.9g)\n", what, got, want);
    }
}

// A 24-dim raw-logits buffer with a single peak at `peak`, all else at `other`.
std::vector<float> onehot24(int peak, float val = 5.0f, float other = -10.0f) {
    std::vector<float> v(24, other);
    v[static_cast<std::size_t>(peak)] = val;
    return v;
}

void test_constants() {
    check(rml23::kSourceClassCount == 24, "kSourceClassCount == 24");
    check(rml23::kDeployedClassCount == 23, "kDeployedClassCount == 23");
    check(rml23::kNpuOutputDim == 24, "kNpuOutputDim == 24");
    check(rml23::kAmSsbSourceWc == 17, "AM-SSB-WC source slot == 17");
    check(rml23::kAmSsbSourceSc == 18, "AM-SSB-SC source slot == 18");
    check(rml23::kAmSsbDeployed == 17, "AM-SSB deployed slot == 17");
    check(std::string(rml23::kDeploymentMode) == "AMSSB_MERGED",
          "deployment_mode == AMSSB_MERGED");
    check(std::string(rml23::kModelMode) == "RML23-AMSSB-MERGED",
          "model_mode == RML23-AMSSB-MERGED");
    check(std::string(rml23::kExpertResult) == "NOT_RUN", "expert_result == NOT_RUN");
}

void test_source_to_deployed() {
    // 0..16 copy through; 17/18 both fold into 17; 19..23 shift down by one.
    for (int i = 0; i <= 16; ++i)
        check(rml23::kSourceToDeployed[i] == i, "source->deployed identity for 0..16");
    check(rml23::kSourceToDeployed[17] == 17, "source 17 (WC) -> deployed 17");
    check(rml23::kSourceToDeployed[18] == 17, "source 18 (SC) -> deployed 17");
    check(rml23::kSourceToDeployed[19] == 18, "source 19 -> deployed 18");
    check(rml23::kSourceToDeployed[20] == 19, "source 20 -> deployed 19");
    check(rml23::kSourceToDeployed[21] == 20, "source 21 -> deployed 20");
    check(rml23::kSourceToDeployed[22] == 21, "source 22 -> deployed 21");
    check(rml23::kSourceToDeployed[23] == 22, "source 23 -> deployed 22");
}

void test_label_order_frozen() {
    const cat::Contract c23 = chain::contract_23();
    const cat::Contract c24 = chain::contract_24();
    check(c23.class_count == 23, "contract_23 count == 23");
    check(c24.class_count == 24, "contract_24 count == 24");
    check(cat::is_valid(c23), "contract_23 is_valid");
    check(cat::is_valid(c24), "contract_24 is_valid");

    // rml23::kLabelOrder23 must equal cat::target_23() exactly.
    bool eq23 = true;
    for (int i = 0; i < rml23::kDeployedClassCount; ++i)
        if (std::string(rml23::kLabelOrder23[i]) != cat::label(c23, i)) eq23 = false;
    check(eq23, "kLabelOrder23 == cat::target_23 (frozen 23-class order)");

    // The merged label must be "AM-SSB" and the source SC/WC slots must NOT appear.
    check(std::string(rml23::kLabelOrder23[17]) == "AM-SSB", "slot 17 == AM-SSB");
    bool no_fake = true;
    for (int i = 0; i < rml23::kDeployedClassCount; ++i) {
        const std::string s = rml23::kLabelOrder23[i];
        if (s == "AM-SSB-WC" || s == "AM-SSB-SC") no_fake = false;
    }
    check(no_fake, "23-class order has NO fake AM-SSB-WC/SC labels");

    // The 24-class order still carries the SC/WC slots (raw source of truth).
    check(cat::label(c24, 17) == "AM-SSB-WC", "24-class slot 17 == AM-SSB-WC");
    check(cat::label(c24, 18) == "AM-SSB-SC", "24-class slot 18 == AM-SSB-SC");
}

void test_logaddexp() {
    const float l2 = std::log(2.0f), l3 = std::log(3.0f), l5 = std::log(5.0f);
    check_near(rml23::logaddexp(l2, l3), l5, 1e-6, "logaddexp(log2,log3)==log5");
    check_near(rml23::logaddexp(l3, l2), l5, 1e-6, "logaddexp symmetric");
    check_near(rml23::logaddexp(-INFINITY, 1.5f), 1.5f, 1e-9, "logaddexp(-inf,x)==x");
    check_near(rml23::logaddexp(1.5f, -INFINITY), 1.5f, 1e-9, "logaddexp(x,-inf)==x");
    check(rml23::logaddexp(INFINITY, 1.0f) == INFINITY, "logaddexp(+inf,x)==+inf");
    check(rml23::logaddexp(-INFINITY, -INFINITY) == -INFINITY,
          "logaddexp(-inf,-inf)==-inf");
}

// The AM-SSB fold: merged[17] == log(exp(WC)+exp(SC)).
void test_merge_amssb_fold() {
    const float l2 = std::log(2.0f), l3 = std::log(3.0f), l5 = std::log(5.0f);
    std::vector<float> raw = onehot24(0, -50.0f, -50.0f);   // all very negative
    raw[17] = l2;   // AM-SSB-WC
    raw[18] = l3;   // AM-SSB-SC
    float m23[23];
    check(rml23::merge_logits_23(raw.data(), m23), "merge_logits_23 ok (AM-SSB)");
    check_near(m23[17], l5, 1e-6, "merged[17] == log(exp(WC)+exp(SC))");
    // Non-AM-SSB slots copy through (all -50 here, so check one).
    check_near(m23[0], -50.0f, 1e-6, "non-AM-SSB slot copies through");
}

// Every deployed slot is reachable as the argmax from some 24-dim source peak.
void test_merge_argmax_all_sources() {
    for (int s = 0; s < 24; ++s) {
        std::vector<float> raw = onehot24(s);
        rml23::RML23Result r;
        check(rml23::merge_predict(raw.data(), &r), "merge_predict ok");
        check(r.raw_24_top1 == s, "raw_24_top1 == source peak");
        check(r.merged_23_top1 == rml23::kSourceToDeployed[s],
              "merged_23_top1 == source->deployed mapping");
        check(r.valid, "merge_predict valid");
        if (s == 17 || s == 18)
            check(std::string(r.merged_23_label) == "AM-SSB",
                  "SC/WC peak -> merged label AM-SSB");
    }
}

// Fail-closed: null pointers / NaN / +Inf all make the merge return false.
void test_merge_fail_closed() {
    float m23[23];
    float good[24];
    for (int i = 0; i < 24; ++i) good[i] = 0.0f;

    check(!rml23::merge_logits_23(nullptr, m23), "merge_logits_23 null in -> false");
    check(!rml23::merge_logits_23(good, nullptr), "merge_logits_23 null out -> false");

    float nan24[24];
    for (int i = 0; i < 24; ++i) nan24[i] = 0.0f;
    nan24[3] = 0.0f / 0.0f;   // NaN
    check(!rml23::merge_logits_23(nan24, m23), "merge_logits_23 NaN -> false");

    float inf24[24];
    for (int i = 0; i < 24; ++i) inf24[i] = 0.0f;
    inf24[3] = INFINITY;
    check(!rml23::merge_logits_23(inf24, m23), "merge_logits_23 +Inf -> false");

    rml23::RML23Result r;
    check(!rml23::merge_predict(nullptr, &r), "merge_predict null in -> false");
    check(!rml23::merge_predict(good, nullptr), "merge_predict null out -> false");
    check(!rml23::merge_predict(nan24, &r), "merge_predict NaN -> false");
    check(!r.valid, "merge_predict NaN leaves valid=false");
}

void test_fill_result_rml23() {
    const cat::Contract c23 = chain::contract_23();
    std::vector<float> raw24 = onehot24(5);   // 8PSK
    std::vector<float> merged23(23, -10.0f);
    merged23[5] = 5.0f;
    rf::ResultFrame r;
    r.frame_id = 3;
    chain::fill_result_rml23(r, raw24, merged23, c23, "2425d990dbac", 6.0);

    check(r.class_count == 23, "fill_result_rml23 class_count == 23");
    check(r.argmax_idx == 5, "fill_result_rml23 argmax_idx == 5");
    check(r.argmax_class == "8PSK", "fill_result_rml23 argmax_class == 8PSK");
    check(r.merged_23_top1 == 5, "fill_result_rml23 merged_23_top1 == argmax_idx");
    check(r.raw_24_top1 == 5, "fill_result_rml23 raw_24_top1 == 5");
    check(r.version == "rml23-chain-v2", "fill_result_rml23 version tag");
    check(r.deployment_mode == "AMSSB_MERGED", "fill_result_rml23 deployment_mode");
    check(!r.expert_enabled, "fill_result_rml23 expert_enabled == false");
    check(r.expert_result == "NOT_RUN", "fill_result_rml23 expert_result == NOT_RUN");
    check(r.model_sha == "2425d990dbac", "fill_result_rml23 model_sha");
    check_near(r.snr_db, 6.0, 1e-9, "fill_result_rml23 snr_db");
    check(r.probabilities.size() == 23, "fill_result_rml23 probabilities width 23");
    double psum = 0.0;
    for (float p : r.probabilities) psum += static_cast<double>(p);
    check_near(psum, 1.0, 1e-3, "fill_result_rml23 probabilities sum ~1");
    check(r.logits.size() == 23, "fill_result_rml23 logits width 23");
    check(r.raw_24_logits.size() == 24, "fill_result_rml23 raw_24_logits width 24");
}

}  // namespace

int main() {
    std::printf("test_rml23_merged\n");
    test_constants();
    test_source_to_deployed();
    test_label_order_frozen();
    test_logaddexp();
    test_merge_amssb_fold();
    test_merge_argmax_all_sources();
    test_merge_fail_closed();
    test_fill_result_rml23();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
