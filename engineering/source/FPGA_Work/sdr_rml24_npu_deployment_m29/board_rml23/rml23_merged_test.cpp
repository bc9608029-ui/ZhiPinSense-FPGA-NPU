// M29 Phase F4 — host test for rml23_merged.hpp (NOT a board binary).
//
//  1. unit tests: logaddexp (incl. infinities), mapping, fail-closed NaN/Inf
//  2. cross-language verification vs the Python reference on 1536 real expA
//     frames: merged 23-dim logits, merged top-1, raw-24 top-1
//  3. 1000-frame and 10000-frame stability: no NaN, stateless/deterministic
//
// Build (WSL): g++ -std=gnu++17 -O2 -Wall -Wextra -Werror -I. rml23_merged_test.cpp -o rml23_merged_test
// Run: ./rml23_merged_test <test_data_dir>
#include "rml23_merged.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        if (cond) {                                                     \
            ++g_pass;                                                   \
        } else {                                                        \
            ++g_fail;                                                   \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        }                                                               \
    } while (0)

static std::vector<float> read_f32(const std::string& path, size_t count) {
    std::ifstream f(path, std::ios::binary);
    std::vector<float> v(count);
    f.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(count * sizeof(float)));
    if (!f || static_cast<size_t>(f.gcount()) != count * sizeof(float)) {
        std::fprintf(stderr, "cannot read %s\n", path.c_str());
        std::exit(2);
    }
    return v;
}

static std::vector<int32_t> read_i32(const std::string& path, size_t count) {
    std::ifstream f(path, std::ios::binary);
    std::vector<int32_t> v(count);
    f.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(count * sizeof(int32_t)));
    if (!f || static_cast<size_t>(f.gcount()) != count * sizeof(int32_t)) {
        std::fprintf(stderr, "cannot read %s\n", path.c_str());
        std::exit(2);
    }
    return v;
}

static void test_logaddexp() {
    CHECK(std::fabs(rml23::logaddexp(1000.0f, 1000.0f) - (1000.0f + std::log(2.0f))) < 1e-3f);
    CHECK(rml23::logaddexp(-INFINITY, 3.0f) == 3.0f);
    CHECK(rml23::logaddexp(3.0f, -INFINITY) == 3.0f);
    CHECK(rml23::logaddexp(-INFINITY, -INFINITY) == -INFINITY);
    CHECK(rml23::logaddexp(INFINITY, 3.0f) == INFINITY);
    CHECK(rml23::logaddexp(1000.0f, 0.0f) == 1000.0f);       // dominated
    CHECK(rml23::logaddexp(-1000.0f, -1000.0f) > -INFINITY);  // no underflow
}

static void test_mapping() {
    CHECK(rml23::kSourceClassCount == 24);
    CHECK(rml23::kDeployedClassCount == 23);
    CHECK(rml23::kNpuOutputDim == 24);
    CHECK(rml23::kSourceToDeployed[17] == 17);
    CHECK(rml23::kSourceToDeployed[18] == 17);
    CHECK(rml23::kSourceToDeployed[19] == 18);
    CHECK(rml23::kSourceToDeployed[23] == 22);
    CHECK(std::strcmp(rml23::kLabelOrder23[17], "AM-SSB") == 0);
    CHECK(std::strcmp(rml23::kLabelOrder23[0], "OOK") == 0);
    CHECK(std::strcmp(rml23::kLabelOrder23[22], "OQPSK") == 0);
}

static void test_synthetic_merge() {
    rml23::RML23Result r;
    // WC dominates -> AM-SSB
    {
        float x[24] = {0};
        x[17] = 5.0f; x[18] = -100.0f;
        CHECK(rml23::merge_predict(x, &r));
        CHECK(r.merged_23_top1 == 17);
        CHECK(std::strcmp(r.merged_23_label, "AM-SSB") == 0);
        CHECK(r.raw_24_top1 == 17);
        CHECK(!r.expert_enabled);
    }
    // SC dominates -> AM-SSB, raw top-1 is SC(18)
    {
        float x[24] = {0};
        x[18] = 9.0f;
        CHECK(rml23::merge_predict(x, &r));
        CHECK(r.merged_23_top1 == 17);
        CHECK(r.raw_24_top1 == 18);
    }
    // non-AM-SSB class wins
    {
        float x[24] = {0};
        x[5] = 9.0f;
        CHECK(rml23::merge_predict(x, &r));
        CHECK(r.merged_23_top1 == 5);
        CHECK(std::strcmp(r.merged_23_label, "8PSK") == 0);
    }
    // NaN fail-closed
    {
        float x[24] = {0};
        x[3] = std::nanf("");
        CHECK(!rml23::merge_predict(x, &r));
        CHECK(!r.valid);
    }
    // +Inf fail-closed
    {
        float x[24] = {0};
        x[10] = INFINITY;
        CHECK(!rml23::merge_predict(x, &r));
    }
    // null pointers fail-closed
    CHECK(!rml23::merge_predict(nullptr, &r));
    CHECK(!rml23::merge_predict(nullptr, nullptr));
}

static void test_cross_language(const std::string& dir) {
    const size_t n = 1536;
    auto raw = read_f32(dir + "/expA_logits_1536x24_f32.bin", n * 24);
    auto merged_ref = read_f32(dir + "/expA_merged_1536x23_f32.bin", n * 23);
    auto pred_ref = read_i32(dir + "/expA_pred23_ref_i32.bin", n);
    auto raw24_ref = read_i32(dir + "/expA_raw24_top1_ref_i32.bin", n);

    int pred_mismatch = 0, raw_mismatch = 0;
    double max_abs = 0.0;
    for (size_t k = 0; k < n; ++k) {
        const float* x = &raw[k * 24];
        rml23::RML23Result r;
        if (!rml23::merge_predict(x, &r)) { ++g_fail; continue; }
        if (r.merged_23_top1 != pred_ref[k]) ++pred_mismatch;
        if (r.raw_24_top1 != raw24_ref[k]) ++raw_mismatch;
        float m23[23];
        rml23::merge_logits_23(x, m23);
        for (int j = 0; j < 23; ++j) {
            double d = std::fabs(static_cast<double>(m23[j]) - merged_ref[k * 23 + j]);
            if (d > max_abs) max_abs = d;
        }
    }
    CHECK(pred_mismatch == 0);
    CHECK(raw_mismatch == 0);
    CHECK(max_abs < 1e-4);  // float32 merge must match Python within tolerance
    std::printf("  cross-lang: n=%zu pred_mismatch=%d raw_mismatch=%d max_abs=%.3e\n",
                n, pred_mismatch, raw_mismatch, max_abs);
}

static void test_frame_stability(const std::string& dir, size_t frames, const char* label) {
    const size_t src_n = 1536;
    auto raw = read_f32(dir + "/expA_logits_1536x24_f32.bin", src_n * 24);
    size_t nan_inf = 0, invalid = 0;
    int first_ok = -1;
    for (size_t k = 0; k < frames; ++k) {
        const float* x = &raw[(k % src_n) * 24];
        rml23::RML23Result r;
        bool ok = rml23::merge_predict(x, &r);
        if (!ok) ++invalid;
        if (r.valid && (r.merged_23_top1 < 0 || r.merged_23_top1 >= 23)) ++nan_inf;
        if (k == 0) first_ok = r.merged_23_top1;
        // determinism: re-run the same frame must give the same top-1
        rml23::RML23Result r2;
        rml23::merge_predict(x, &r2);
        if (r2.merged_23_top1 != r.merged_23_top1) ++invalid;
    }
    CHECK(invalid == 0);
    CHECK(first_ok >= 0 && first_ok < 23);
    std::printf("  %s: frames=%zu invalid=%zu\n", label, frames, invalid);
}

int main(int argc, char** argv) {
    const std::string dir = (argc > 1) ? argv[1] : "test_data";
    std::printf("== rml23_merged host test ==\n");
    test_logaddexp();
    test_mapping();
    test_synthetic_merge();
    test_cross_language(dir);
    test_frame_stability(dir, 1000, "1000-frame");
    test_frame_stability(dir, 10000, "10000-frame");
    std::printf("== result: assertions=%d passed=%d failed=%d ==\n",
                g_pass + g_fail, g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
