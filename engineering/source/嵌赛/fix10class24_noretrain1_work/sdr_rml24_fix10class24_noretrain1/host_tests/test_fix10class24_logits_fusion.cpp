// test_fix10class24_logits_fusion.cpp -- host tests for the Phase C frozen
// multi-capture fusion module (iq_fix10class24_logits_fusion.hpp).  Pure math, no
// NPU / libiio / board device.  Covers stable softmax, hard-invalid rejection, the
// four strategies, and the frozen quality-weight formula.

#include "../board_package/iq_fix10class24_logits_fusion.hpp"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

iqfusion::Capture valid_capture(std::vector<float> logits, double corr, double res) {
    iqfusion::Capture c;
    c.logits = std::move(logits);
    c.logits_finite = true;
    c.rx_clipped = false;
    c.sync_valid = true;
    c.cfo_finite = true;
    c.cfo_in_range = true;
    c.has_signal = true;
    c.training_corr = corr;
    c.payload_training_residual = res;
    return c;
}

void test_softmax() {
    const std::vector<float> x = {1.0f, 2.0f, 3.0f};
    const std::vector<double> s = iqfusion::stable_softmax(x);
    check(s.size() == 3, "softmax: size 3");
    double sum = 0.0;
    for (double v : s) sum += v;
    check(s.size() == 3 && std::fabs(sum - 1.0) < 1e-9, "softmax: sums to 1");
    check(s.size() == 3 && s[2] > s[1] && s[1] > s[0], "softmax: monotonic");
    // stable for large values (no overflow -> NaN)
    const std::vector<float> big = {1000.0f, 1001.0f, 1002.0f};
    const std::vector<double> sb = iqfusion::stable_softmax(big);
    bool finite = sb.size() == 3;
    for (double v : sb) if (!std::isfinite(v)) finite = false;
    check(finite, "softmax: stable for large logits (no overflow)");
    // NaN -> empty
    const std::vector<float> bad = {1.0f, std::nanf(""), 3.0f};
    check(iqfusion::stable_softmax(bad).empty(), "softmax: NaN -> empty");
}

void test_hard_invalid() {
    iqfusion::Capture ok = valid_capture({0.0f, 1.0f}, 0.99, 0.05);
    check(!iqfusion::is_hard_invalid(ok), "hard-invalid: valid capture passes");
    ok.rx_clipped = true;
    check(iqfusion::is_hard_invalid(ok), "hard-invalid: rx_clipped");
    ok = valid_capture({0.0f, 1.0f}, 0.99, 0.05); ok.logits_finite = false;
    check(iqfusion::is_hard_invalid(ok), "hard-invalid: non-finite logits");
    ok = valid_capture({0.0f, 1.0f}, 0.99, 0.05); ok.sync_valid = false;
    check(iqfusion::is_hard_invalid(ok), "hard-invalid: sync fail");
    ok = valid_capture({0.0f, 1.0f}, 0.99, 0.05); ok.cfo_finite = false;
    check(iqfusion::is_hard_invalid(ok), "hard-invalid: cfo non-finite");
    ok = valid_capture({0.0f, 1.0f}, 0.99, 0.05); ok.cfo_in_range = false;
    check(iqfusion::is_hard_invalid(ok), "hard-invalid: cfo out-of-range");
    ok = valid_capture({0.0f, 1.0f}, 0.99, 0.05); ok.has_signal = false;
    check(iqfusion::is_hard_invalid(ok), "hard-invalid: no signal");
    ok = valid_capture({}, 0.99, 0.05);
    check(iqfusion::is_hard_invalid(ok), "hard-invalid: empty logits");
}

void test_majority_vote() {
    check(iqfusion::majority_vote({3, 3, 7}) == 3, "majority: 3 wins over 7");
    check(iqfusion::majority_vote({3, 7}) == -1, "majority: tie -> -1");
    check(iqfusion::majority_vote({}) == -1, "majority: empty -> -1");
    check(iqfusion::majority_vote({3, -1, 3}) == -1, "majority: any invalid -> -1");
    check(iqfusion::majority_vote({5}) == 5, "majority: single -> itself");
}

void test_average() {
    std::vector<std::vector<float>> ls = {{1.0f, 3.0f}, {3.0f, 1.0f}, {2.0f, 2.0f}};
    const std::vector<float> a = iqfusion::average_logits(ls);
    check(a.size() == 2 && a[0] == 2.0f && a[1] == 2.0f, "average: mean of 3");
    check(iqfusion::average_logits({}).empty(), "average: empty -> empty");
    std::vector<std::vector<float>> bad = {{1.0f, 2.0f}, {3.0f}};
    check(iqfusion::average_logits(bad).empty(), "average: ragged -> empty");
}

void test_median() {
    std::vector<std::vector<float>> ls = {{1.0f, 10.0f}, {5.0f, 2.0f}, {3.0f, 4.0f}};
    const std::vector<float> m = iqfusion::median_logits(ls);
    check(m.size() == 2 && m[0] == 3.0f && m[1] == 4.0f, "median: odd count per-dim");
    std::vector<std::vector<float>> ls2 = {{1.0f}, {3.0f}, {5.0f}, {7.0f}};
    const std::vector<float> m2 = iqfusion::median_logits(ls2);
    check(m2.size() == 1 && m2[0] == 4.0f, "median: even count -> mean of middle two");
    check(iqfusion::median_logits({}).empty(), "median: empty -> empty");
}

void test_quality_weight() {
    const iqfusion::Capture hi = valid_capture({0.0f}, 0.99, 0.05);
    const iqfusion::Capture lo = valid_capture({0.0f}, 0.80, 0.20);
    check(iqfusion::quality_weight(hi) > iqfusion::quality_weight(lo),
          "quality: higher corr + lower residual -> higher weight");
    iqfusion::Capture bad = valid_capture({0.0f}, 0.99, 0.05);
    bad.rx_clipped = true;
    check(iqfusion::quality_weight(bad) == 0.0, "quality: hard-invalid -> 0");
    iqfusion::Capture negcorr = valid_capture({0.0f}, -0.5, 0.05);
    check(iqfusion::quality_weight(negcorr) == 0.0, "quality: negative corr clamped -> 0");
}

void test_quality_weighted() {
    // cap A (class 0) has high quality; cap B (class 1) has low quality.
    const iqfusion::Capture a = valid_capture({5.0f, 0.0f}, 0.99, 0.05);
    const iqfusion::Capture b = valid_capture({0.0f, 5.0f}, 0.50, 0.50);
    const std::vector<float> w = iqfusion::quality_weighted_logits({a, b});
    check(w.size() == 2, "qweighted: size");
    check(w.size() == 2 && w[0] > w[1], "qweighted: high-quality capture dominates");
    // all hard-invalid -> empty
    iqfusion::Capture bad = valid_capture({1.0f, 2.0f}, 0.9, 0.05);
    bad.rx_clipped = true;
    check(iqfusion::quality_weighted_logits({bad}).empty(),
          "qweighted: all invalid -> empty");
}

}  // namespace

int main() {
    test_softmax();
    test_hard_invalid();
    test_majority_vote();
    test_average();
    test_median();
    test_quality_weight();
    test_quality_weighted();
    std::printf("test_fix10class24_logits_fusion: %d pass / %d fail\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
