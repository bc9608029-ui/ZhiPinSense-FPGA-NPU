// Host unit test for the CPU-side OOD-U detector and manifest loader.
//
// Verifies score computation against hand-computed values, UNKNOWN vs known
// semantics (including the score == threshold boundary), the NO_SIGNAL / ERROR
// sentinels, and fail-closed manifest validation.  Compiled with
// -Wall -Wextra -Werror and, separately, with ASan/UBSan.
#include <cstdio>
#include <cmath>
#include <fstream>
#include <string>

#include "ood_threshold_manifest.hpp"
#include "ood_u_contract.hpp"
#include "ood_u_detector.hpp"

namespace {

int failures = 0;

void check(bool ok, const std::string& what) {
    if (!ok) {
        std::printf("FAIL: %s\n", what.c_str());
        ++failures;
    }
}

void check_close(double got, double want, double tol, const std::string& what) {
    if (std::fabs(got - want) > tol) {
        std::printf("FAIL: %s (got %.12f, want %.12f)\n", what.c_str(), got, want);
        ++failures;
    }
}

OodThresholdManifest make_manifest(const std::string& method, double threshold, double temperature = 1.0) {
    OodThresholdManifest m;
    m.model_name = ood_u_contract::MODEL_NAME;
    m.model_sha256 = ood_u_contract::MODEL_SHA256;
    m.checkpoint_sha256 = "7215290b0f43f8a8cc05f4ee135f2a9524cf8a8036b71ae52b0b6c94c02aae72";
    m.score_method = method;
    m.score_direction = ood_u_contract::DIRECTION;
    m.temperature = temperature;
    m.threshold = threshold;
    m.label_order.assign(ood_u_contract::LABEL_ORDER_12.begin(), ood_u_contract::LABEL_ORDER_12.end());
    m.final_test_accessed = false;
    return m;
}

double zero_logits[12] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

void test_scores() {
    // All-zero logits -> uniform softmax.
    check_close(OodUDetector(make_manifest("msp", 0.0)).score(zero_logits, 12), 1.0 - 1.0 / 12.0, 1e-6, "msp(uniform)");
    check_close(OodUDetector(make_manifest("entropy", 0.0)).score(zero_logits, 12), std::log(12.0), 1e-6, "entropy(uniform)");
    check_close(OodUDetector(make_manifest("max_logit", 0.0)).score(zero_logits, 12), 0.0, 1e-9, "max_logit(uniform)");
    check_close(OodUDetector(make_manifest("logit_margin", 0.0)).score(zero_logits, 12), 0.0, 1e-9, "logit_margin(uniform)");
    check_close(OodUDetector(make_manifest("energy", 0.0, 1.0)).score(zero_logits, 12), -std::log(12.0), 1e-6, "energy(uniform,T=1)");
    check_close(OodUDetector(make_manifest("energy", 0.0, 2.0)).score(zero_logits, 12), -2.0 * std::log(12.0), 1e-6, "energy(uniform,T=2)");

    double margin[12] = {3, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    check_close(OodUDetector(make_manifest("logit_margin", 0.0)).score(margin, 12), -2.0, 1e-9, "logit_margin(3,1)");

    double maxlit[12] = {2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    check_close(OodUDetector(make_manifest("max_logit", 0.0)).score(maxlit, 12), -2.0, 1e-9, "max_logit(2)");
}

void test_decisions() {
    OodUDetector detector(make_manifest("max_logit", -1.0));

    double dominant[12] = {10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10};
    OodDecision d = detector.classify_or_reject(dominant, 12);
    check(d.valid, "dominant valid");
    check(d.known, "dominant known");
    check(d.class_index == 0, "dominant class 0");
    check(d.class_name == "OOK", "dominant class_name OOK");

    d = detector.classify_or_reject(zero_logits, 12);  // score 0 > -1 -> UNKNOWN
    check(d.valid, "uniform valid");
    check(!d.known, "uniform rejected");
    check(d.class_name == ood_u_contract::UNKNOWN, "uniform UNKNOWN");
    check(d.class_index == -1, "uniform class_index -1");

    // Boundary: score == threshold must be accepted (higher-than-threshold rejects).
    OodUDetector boundary(make_manifest("max_logit", 0.0));
    d = boundary.classify_or_reject(zero_logits, 12);  // score 0 == threshold 0
    check(d.known, "boundary score==threshold accepted");

    // NO_SIGNAL / ERROR sentinels.
    OodDecision ns = OodUDetector::no_signal();
    check(ns.class_name == ood_u_contract::NO_SIGNAL, "no_signal sentinel");
    check(!ns.known && !ns.valid, "no_signal not known/valid");

    double nan_logits[12] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, std::nan("")};
    OodDecision err = detector.classify_or_reject(nan_logits, 12);
    check(err.class_name == ood_u_contract::ERROR, "non-finite -> ERROR");
    check(!err.valid, "error not valid");
}

void test_manifest_loader() {
    const std::string path = "test_manifest_fixture.json";
    const std::string label_list = "\"OOK\", \"4ASK\", \"AM-DSB\", \"WBFM\", \"2FSK\", \"GFSK\", "
                                   "\"BPSK\", \"QPSK\", \"8PSK\", \"16QAM\", \"64QAM\", \"OFDM\"";
    {
        std::ofstream out(path);
        out << "{"
            << "\"schema_version\":1,"
            << "\"model_name\":\"12CLASS_CHAIN_VALIDATION_MODEL\","
            << "\"model_sha256\":\"2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c\","
            << "\"checkpoint_sha256\":\"7215290b0f43f8a8cc05f4ee135f2a9524cf8a8036b71ae52b0b6c94c02aae72\","
            << "\"npu_model_sha256\":\"2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c\","
            << "\"label_order\":[" << label_list << "],"
            << "\"input_contract\":{\"shape\":[1,2,1024]},"
            << "\"output_numeric_type\":\"fp32\","
            << "\"output_scale\":null,\"output_zero_point\":null,"
            << "\"score_method\":\"logit_margin\","
            << "\"score_direction\":\"higher_is_ood\","
            << "\"temperature\":1.0,"
            << "\"threshold\":-0.153,"
            << "\"working_points\":{\"id_accept_95\":{\"threshold\":-0.5},\"id_accept_99\":{\"threshold\":-0.153},\"far_ood_target\":{\"threshold\":-15.0}},"
            << "\"target_operating_point\":\"id_accept_99\","
            << "\"calibration_dataset_sha256\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\","
            << "\"calibration_split_sha256\":\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\","
            << "\"sample_count\":{\"id\":720,\"ood\":1080},"
            << "\"creation_seed\":12600,"
            << "\"creation_time\":\"2026-10-08T00:00:00+00:00\","
            << "\"final_test_accessed\":false"
            << "}";
    }
    OodThresholdManifest m = load_ood_u_manifest(path);
    check(m.score_method == "logit_margin", "manifest score_method");
    check_close(m.threshold, -0.153, 1e-9, "manifest threshold");
    check(m.label_order.size() == 12, "manifest label_order size");
    check(!m.final_test_accessed, "manifest final_test_accessed false");
    std::remove(path.c_str());

    // Invalid: wrong model SHA must throw.
    {
        std::ofstream out(path);
        out << "{\"model_name\":\"12CLASS_CHAIN_VALIDATION_MODEL\","
            << "\"model_sha256\":\"0000000000000000000000000000000000000000000000000000000000000000\","
            << "\"checkpoint_sha256\":\"7215290b0f43f8a8cc05f4ee135f2a9524cf8a8036b71ae52b0b6c94c02aae72\","
            << "\"score_method\":\"msp\",\"score_direction\":\"higher_is_ood\","
            << "\"temperature\":1.0,\"threshold\":0.0,"
            << "\"label_order\":[" << label_list << "],\"final_test_accessed\":false}";
    }
    bool threw = false;
    try {
        load_ood_u_manifest(path);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    check(threw, "manifest wrong model_sha throws");
    std::remove(path.c_str());

    // Malformed JSON must throw.
    {
        std::ofstream out(path);
        out << "{ not json";
    }
    threw = false;
    try {
        load_ood_u_manifest(path);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    check(threw, "malformed manifest throws");
    std::remove(path.c_str());
}

}  // namespace

int main() {
    test_scores();
    test_decisions();
    test_manifest_loader();
    if (failures == 0) {
        std::printf("test_ood_u_detector: ALL PASS\n");
        return 0;
    }
    std::printf("test_ood_u_detector: %d FAILURES\n", failures);
    return 1;
}
