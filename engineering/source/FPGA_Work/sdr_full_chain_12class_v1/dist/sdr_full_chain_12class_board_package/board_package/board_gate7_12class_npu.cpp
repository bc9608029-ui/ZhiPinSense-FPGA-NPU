// board_gate7_12class_npu.cpp -- Gate 7: load the twelve-class NPU model and
// verify it against the deployment golden set (task 39e5 §四/§六/§七).
//
// The golden set (deployment_golden/) is 240 fp32 [1,2,1024] inputs (8192 B each,
// C-order: first 1024 = I, next 1024 = Q) at SNR 10 dB, 20 per class, with the
// ONNX-Runtime argmax recorded in expected_argmax.tsv (derived 1:1 from
// expected_logits_or_argmax.json).  Gate 7 feeds each input to the compiled INT8
// NPU model and compares the argmax.  INT8 per-channel symmetric quantization may
// flip a small number of near-boundary argmaxes, so the gate is
//    match_rate >= --min-match-rate  (default 0.90, golden self-consistency 98.3%).
//
// NO device / NO SDR here: this gate proves the NPU partition alone, against the
// exact model artifacts model_12class.json/.raw.  Any malformed-model or
// contract-shape error throws BEFORE the device is opened (see npu_classifier.hpp).
//
// Exit 0/1 = pass/fail.  Build via build_on_board.sh (links iCraft backends).

#include "board_common.hpp"
#include "npu_classifier.hpp"
#include "chain_common.hpp"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

// Split one TSV line into fields on '\t'.
std::vector<std::string> split_tsv(const std::string& line) {
    std::vector<std::string> f;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = line.find('\t', start);
        if (pos == std::string::npos) {
            f.push_back(line.substr(start));
            break;
        }
        f.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    return f;
}

// Read one fp32 [2,1024] input into `out` (2048 floats).  Returns false on any
// short read (never a silent zero-fill).
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

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();

    const std::string model_json = board::get_opt(argc, argv, "--model-json",
                                                  "model_12class/model_12class.json");
    const std::string model_raw = board::get_opt(argc, argv, "--model-raw",
                                                 "model_12class/model_12class.raw");
    const std::string golden_dir = board::get_opt(argc, argv, "--golden",
                                                  "deployment_golden");
    const std::size_t count = static_cast<std::size_t>(board::opt_u64(argc, argv, "--count", 240));
    const double min_match = board::opt_d(argc, argv, "--min-match-rate", 0.90);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");

    bool pass = false;
    std::string detail;
    try {
        chain::NpuClassifier12 npu(model_json, model_raw);

        // Load expected argmax table (index \t argmax_idx \t label \t modulation \t confidence).
        const std::string tsv_path = golden_dir + "/expected_argmax.tsv";
        std::ifstream tsv(tsv_path.c_str());
        std::vector<int> exp_argmax;
        std::vector<int> exp_label;
        std::vector<std::string> exp_mod;
        std::string line;
        while (std::getline(tsv, line)) {
            if (line.empty()) continue;
            const std::vector<std::string> f = split_tsv(line);
            if (f.size() < 4) continue;
            exp_argmax.push_back(std::atoi(f[1].c_str()));
            exp_label.push_back(std::atoi(f[2].c_str()));
            exp_mod.push_back(f[3]);
        }
        tsv.close();
        if (exp_argmax.empty())
            throw std::runtime_error("expected_argmax.tsv empty or missing: " + tsv_path);

        const cat::Contract contract = chain::contract_12();
        const std::size_t n = count < exp_argmax.size() ? count : exp_argmax.size();

        std::vector<float> tensor(chain::kTensorFloats);
        std::vector<int> per_class_match(contract.class_count, 0);
        std::vector<int> per_class_total(contract.class_count, 0);
        std::size_t processed = 0;
        std::size_t matched = 0;

        for (std::size_t i = 0; i < n; ++i) {
            if (board::g_stop_requested) break;
            char path[512];
            std::snprintf(path, sizeof(path), "%s/input_%03zu.bin", golden_dir.c_str(), i);
            if (!read_input_bin(path, tensor))
                throw std::runtime_error(std::string("short/missing input: ") + path);

            const std::vector<float> logits = npu.infer(tensor.data());
            const int pred = argmax_of(logits);
            const int ref = exp_argmax[i];
            const int label = (exp_label[i] >= 0 &&
                               exp_label[i] < contract.class_count)
                                  ? exp_label[i]
                                  : 0;
            ++processed;
            ++per_class_total[static_cast<std::size_t>(label)];
            if (pred == ref) {
                ++matched;
                ++per_class_match[static_cast<std::size_t>(label)];
            }
        }

        const double rate = processed ? static_cast<double>(matched) / static_cast<double>(processed) : 0.0;
        pass = (processed == n) && (rate >= min_match);

        detail += " model_sha=" + model_sha;
        detail += " samples=" + std::to_string(processed) + "/" + std::to_string(n);
        detail += " matched=" + std::to_string(matched);
        detail += " match_rate=" + std::to_string(rate);
        detail += " min_match_rate=" + std::to_string(min_match);
        detail += " per_class=";
        for (int c = 0; c < contract.class_count; ++c) {
            if (c) detail += ",";
            detail += cat::label(contract, c) + ":" +
                      std::to_string(per_class_match[static_cast<std::size_t>(c)]) + "/" +
                      std::to_string(per_class_total[static_cast<std::size_t>(c)]);
        }
        if (processed != n) detail += " (count_short)";
        if (rate < min_match) detail += " (match_below_threshold)";
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    board::emit("gate7_12class_npu", pass, detail);
    return pass ? 0 : 1;
}
