// test_golden_rml23.cpp -- host regression for the RML23 conformance golden
// (deployment_golden/).  Re-reads expected_argmax.tsv with the EXACT board parse
// rule (board_gate9_full_chain_rml23.cpp: split on '\t' only, no trim, no
// field-count beyond the <4 guard, std::atoi(f[1].c_str())), and validates the
// golden's structural + merge invariants.  iCraft-free and libiio-free.
//
// Positive checks (mirror scripts/verify_golden_rml23.py; the 8 negative
// rejections live in that Python harness):
//   P1  manifest.json is present and declares golden_kind == "conformance".
//   P2  tsv line count == input_*.bin count; filenames contiguous input_000..N-1.
//   P3  every expected argmax (f[1]) is an integer in 0..22.
//   P4  f[3] (argmax_class_23) == rml23::kLabelOrder23[f[1]].
//   P5  expected_logits.tsv has N lines, each with 23 finite logits.
//   P6  softmax of the 23 logits is finite and sums to 1 within tolerance.
//   P7  BPSK (source class 3) and QPSK (source class 4) each appear exactly 10
//       times, and are not swapped (kLabelOrder23[3]=="BPSK", [4]=="QPSK").
//   P8  merge-rule consistency: tsv f[1] == argmax(23 logits) for every line.
//   P9  every input_*.bin is exactly 8192 bytes and reads 2048 finite fp32.
//
// Build/run: see host_tests/build_host_tests.sh (adds test_golden_rml23).

#include "../board_package/chain_common.hpp"
#include "../board_package/rml23_merged.hpp"

#include <cmath>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

// --- board-identical helpers (verbatim from board_gate9_full_chain_rml23.cpp) --

// split on '\t' only; no trim; a trailing empty segment is kept.
std::vector<std::string> split_tsv(const std::string& line) {
    std::vector<std::string> f;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = line.find('\t', start);
        if (pos == std::string::npos) { f.push_back(line.substr(start)); break; }
        f.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    return f;
}

bool read_input_bin(const std::string& path, std::vector<float>& out) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    const std::size_t n = out.size();
    const std::size_t got = std::fread(out.data(), sizeof(float), n, f);
    std::fclose(f);
    return got == n;
}

int argmax_of(const std::vector<float>& logits) {
    if (logits.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(logits.size()); ++i)
        if (logits[i] > logits[best]) best = i;
    return best;
}

bool file_size_is(const std::string& path, std::size_t want) {
    std::ifstream f(path.c_str(), std::ios::binary | std::ios::ate);
    if (!f) return false;
    return static_cast<std::size_t>(f.tellg()) == want;
}

std::vector<float> softmax_of(const std::vector<float>& logits) {
    float m = -INFINITY;
    for (float v : logits) m = std::fmax(m, v);
    std::vector<float> e(logits.size());
    double s = 0.0;
    for (std::size_t i = 0; i < logits.size(); ++i) {
        e[i] = std::exp(logits[i] - m);
        s += static_cast<double>(e[i]);
    }
    std::vector<float> p(logits.size());
    for (std::size_t i = 0; i < logits.size(); ++i)
        p[i] = static_cast<float>(static_cast<double>(e[i]) / s);
    return p;
}

void test_golden(const std::string& golden) {
    const std::size_t kInputBytes = chain::kTensorBytes;   // 8192
    const std::size_t kTensorFloats = chain::kTensorFloats;  // 2048
    const int kClasses = rml23::kDeployedClassCount;       // 23

    // P1: manifest present + conformance kind.
    const std::string man_path = golden + "/manifest.json";
    {
        std::ifstream m(man_path.c_str());
        std::string body((std::istreambuf_iterator<char>(m)),
                         std::istreambuf_iterator<char>());
        check(!body.empty(), "manifest.json present + non-empty");
        check(body.find("\"golden_kind\": \"conformance\"") != std::string::npos ||
              body.find("\"golden_kind\":\"conformance\"") != std::string::npos,
              "manifest.json golden_kind == conformance");
    }

    // P2/P3/P4: read expected_argmax.tsv with the board parse rule.
    const std::string tsv_path = golden + "/expected_argmax.tsv";
    std::ifstream tsv(tsv_path.c_str());
    check(static_cast<bool>(tsv), "expected_argmax.tsv opens");
    std::vector<int> exp_argmax;       // board: atoi(f[1])
    std::vector<int> exp_source;       // f[2] (source label index 0..23)
    std::vector<std::string> exp_class;  // f[3]
    std::string line;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        const std::vector<std::string> f = split_tsv(line);
        if (f.size() < 4) continue;    // board-identical guard
        exp_argmax.push_back(std::atoi(f[1].c_str()));
        exp_source.push_back(std::atoi(f[2].c_str()));
        exp_class.push_back(f[3]);
    }
    tsv.close();
    const std::size_t n = exp_argmax.size();
    check(n > 0, "expected_argmax.tsv has at least one line");

    // P2: filenames contiguous input_000..input_{n-1}, each 8192 bytes (P9 size).
    bool contiguous = true;
    for (std::size_t i = 0; i < n; ++i) {
        char name[64];
        std::snprintf(name, sizeof(name), "%s/input_%03zu.bin", golden.c_str(), i);
        if (!file_size_is(name, kInputBytes)) contiguous = false;
    }
    check(contiguous, "input_000..input_N-1 all present and 8192 bytes");

    // P3: argmax range; P4: argmax_class_23 == kLabelOrder23[argmax].
    bool range_ok = true, label_ok = true, source_ok = true;
    for (std::size_t i = 0; i < n; ++i) {
        if (exp_argmax[i] < 0 || exp_argmax[i] >= kClasses) range_ok = false;
        if (exp_argmax[i] >= 0 && exp_argmax[i] < kClasses &&
            exp_class[i] != rml23::kLabelOrder23[exp_argmax[i]]) label_ok = false;
        if (exp_source[i] < 0 || exp_source[i] >= rml23::kSourceClassCount) source_ok = false;
    }
    check(range_ok, "every expected argmax in 0..22");
    check(source_ok, "every source class index in 0..23");
    check(label_ok, "argmax_class_23 == kLabelOrder23[argmax] for every line");

    // P7: BPSK/QPSK explicit + not swapped (10 frames each).
    check(std::string(rml23::kLabelOrder23[3]) == "BPSK", "kLabelOrder23[3] == BPSK");
    check(std::string(rml23::kLabelOrder23[4]) == "QPSK", "kLabelOrder23[4] == QPSK");
    int bpsk = 0, qpsk = 0;
    for (int s : exp_source) {
        if (s == 3) ++bpsk;
        if (s == 4) ++qpsk;
    }
    check(bpsk == 10 && qpsk == 10, "BPSK(3) and QPSK(4) each appear exactly 10 frames");

    // P5/P6/P8: expected_logits.tsv cross-consistency.
    const std::string ltsv_path = golden + "/expected_logits.tsv";
    std::ifstream ltsv(ltsv_path.c_str());
    check(static_cast<bool>(ltsv), "expected_logits.tsv opens");
    std::size_t lcount = 0;
    bool logits_ok = true, prob_ok = true, merge_ok = true;
    std::string ll;
    while (std::getline(ltsv, ll)) {
        if (ll.empty()) continue;
        const std::vector<std::string> f = split_tsv(ll);
        if (f.size() < static_cast<std::size_t>(kClasses + 1)) { logits_ok = false; continue; }
        std::vector<float> vals(kClasses);
        bool finite = true;
        for (int i = 0; i < kClasses; ++i) {
            vals[static_cast<std::size_t>(i)] = std::strtof(f[static_cast<std::size_t>(i + 1)].c_str(), nullptr);
            if (!std::isfinite(vals[static_cast<std::size_t>(i)])) finite = false;
        }
        if (!finite) { logits_ok = false; continue; }
        std::vector<float> p = softmax_of(vals);
        double psum = 0.0;
        for (float v : p) psum += static_cast<double>(v);
        if (!std::isfinite(static_cast<float>(psum)) || std::fabs(psum - 1.0) > 1e-5) prob_ok = false;
        if (lcount < n && argmax_of(vals) != exp_argmax[lcount]) merge_ok = false;
        ++lcount;
    }
    ltsv.close();
    check(lcount == n, "expected_logits.tsv line count == input count");
    check(logits_ok, "every expected_logits.tsv line has 23 finite logits");
    check(prob_ok, "softmax of 23 logits finite and sums to 1 (tol 1e-5)");
    check(merge_ok, "tsv argmax == argmax(23 logits) for every line (merge consistency)");

    // P9: read each input as 2048 fp32 and check all finite (size already checked).
    bool inputs_finite = true;
    for (std::size_t i = 0; i < n; ++i) {
        char name[64];
        std::snprintf(name, sizeof(name), "%s/input_%03zu.bin", golden.c_str(), i);
        std::vector<float> tensor(kTensorFloats);
        if (!read_input_bin(name, tensor)) { inputs_finite = false; continue; }
        for (float v : tensor)
            if (!std::isfinite(v)) inputs_finite = false;
    }
    check(inputs_finite, "every input frame reads 2048 finite fp32");
}

}  // namespace

int main(int argc, char** argv) {
    const std::string golden = argc > 1 ? argv[1] : "../deployment_golden";
    std::printf("test_golden_rml23 (golden=%s)\n", golden.c_str());
    test_golden(golden);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
