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
#include "delay_gate.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
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

// ---- diagnostic (--diagnostic) ----------------------------------------------
// Captures the board's ACTUAL per-sample NPU logits so a below-random Gate 7
// result can be pinpointed offline.  The compiled model_12class.json/.raw itself
// verifies ~98.75% on Host (icraft-run --fake_qf over the full 240-sample golden
// set), so a board result far below that must be distinguished: constant
// "garbage" logits, sane logits with a wrong argmax, a logit permutation, NaN/Inf,
// or a per-class bias all show up differently here.  The formal match_rate >=
// --min-match-rate (default 0.90) gate is NOT changed by this diagnostic.
struct DiagSample {
    std::size_t index = 0;
    int ref = 0;
    int pred = 0;
    int label = 0;
    std::vector<float> logits;
};

void emit_diagnostic(const std::vector<DiagSample>& samples,
                     const cat::Contract& contract) {
    const int cc = contract.class_count;
    std::printf("DIAGNOSTIC_BEGIN gate=gate7_12class_npu\n");

    // 1) first 24 items: sample / ref / pred / label / 12 raw logits.
    const std::size_t show = samples.size() < 24 ? samples.size() : 24;
    for (std::size_t k = 0; k < show; ++k) {
        const DiagSample& s = samples[k];
        std::printf("sample=%03zu ref=%d pred=%d label=%d logits=[",
                    s.index, s.ref, s.pred, s.label);
        for (std::size_t c = 0; c < s.logits.size(); ++c) {
            if (c) std::printf(",");
            std::printf("%.6g", s.logits[c]);
        }
        std::printf("]\n");
    }

    // 2) logits finite / min / max / mean over every stored logit.
    std::uint64_t finite = 0, nan_inf = 0;
    double lo = 0.0, hi = 0.0, sum = 0.0;
    bool first = true;
    for (const DiagSample& s : samples) {
        for (const float v : s.logits) {
            if (!std::isfinite(v)) { ++nan_inf; continue; }
            ++finite;
            if (first) { lo = hi = v; first = false; }
            else { if (v < lo) lo = v; if (v > hi) hi = v; }
            sum += v;
        }
    }
    std::printf("logits_total=%zu finite=%llu nan_inf=%llu min=%.6g max=%.6g mean=%.6g\n",
                samples.size() * 12,
                static_cast<unsigned long long>(finite),
                static_cast<unsigned long long>(nan_inf),
                first ? 0.0 : lo, first ? 0.0 : hi, finite ? sum / finite : 0.0);

    // 3) full predicted-class histogram.
    std::vector<std::size_t> pred_hist(static_cast<std::size_t>(cc), 0);
    for (const DiagSample& s : samples)
        ++pred_hist[static_cast<std::size_t>(s.pred)];
    std::printf("pred_hist=");
    for (int c = 0; c < cc; ++c) {
        if (c) std::printf(",");
        std::printf("%s:%zu", cat::label(contract, c).c_str(),
                    pred_hist[static_cast<std::size_t>(c)]);
    }
    std::printf("\n");

    // 4) per-class ref -> pred confusion matrix.
    for (int r = 0; r < cc; ++r) {
        std::vector<std::size_t> row(static_cast<std::size_t>(cc), 0);
        for (const DiagSample& s : samples)
            if (s.ref == r) ++row[static_cast<std::size_t>(s.pred)];
        std::printf("confusion_row_%02d_%s=", r, cat::label(contract, r).c_str());
        for (int p = 0; p < cc; ++p) {
            if (p) std::printf(",");
            std::printf("%s:%zu", cat::label(contract, p).c_str(),
                        row[static_cast<std::size_t>(p)]);
        }
        std::printf("\n");
    }
    std::printf("DIAGNOSTIC_END\n");
    std::fflush(stdout);
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
    const bool diagnostic = board::has_flag(argc, argv, "--diagnostic");

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
        std::uint64_t nan_inf = 0;
        chain::DelayGate gate;
        std::vector<double> infer_us;
        infer_us.reserve(n);
        std::vector<DiagSample> diag_samples;
        if (diagnostic) diag_samples.reserve(n);

        for (std::size_t i = 0; i < n; ++i) {
            if (board::g_stop_requested) break;
            char path[512];
            std::snprintf(path, sizeof(path), "%s/input_%03zu.bin", golden_dir.c_str(), i);
            if (!read_input_bin(path, tensor))
                throw std::runtime_error(std::string("short/missing input: ") + path);

            const auto t0 = std::chrono::steady_clock::now();
            const std::vector<float> logits = npu.infer(tensor.data());
            const auto t1 = std::chrono::steady_clock::now();
            infer_us.push_back(static_cast<double>(
                std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count()));
            for (const float v : logits)
                if (!std::isfinite(v)) ++nan_inf;
            const int pred = argmax_of(logits);
            const int ref = exp_argmax[i];
            const int label = (exp_label[i] >= 0 &&
                               exp_label[i] < contract.class_count)
                                  ? exp_label[i]
                                  : 0;
            if (diagnostic)
                diag_samples.push_back({i, ref, pred, label, logits});
            ++processed;
            ++per_class_total[static_cast<std::size_t>(label)];
            if (pred == ref) {
                ++matched;
                ++per_class_match[static_cast<std::size_t>(label)];
            }

            // One-frame-delay evidence is accumulated by the pure-logic DelayGate
            // (see delay_gate.hpp); its delay_detected() is the strong-signature
            // test that replaces the old `delay_shift_match == 0` false positive.
            gate.on_frame(pred, ref);
        }

        if (diagnostic)
            emit_diagnostic(diag_samples, contract);

        // Infer latency statistics (mean / p99 / max) over the processed frames.
        std::sort(infer_us.begin(), infer_us.end());
        double infer_us_mean = 0.0, infer_us_p99 = 0.0, infer_us_max = 0.0;
        if (!infer_us.empty()) {
            infer_us_max = infer_us.back();
            double sum = 0.0;
            for (double v : infer_us) sum += v;
            infer_us_mean = sum / static_cast<double>(infer_us.size());
            const std::size_t k = static_cast<std::size_t>(
                std::ceil(0.99 * static_cast<double>(infer_us.size())));
            const std::size_t idx = (k == 0) ? 0 : (k - 1);
            infer_us_p99 = infer_us[idx];
        }

        const double rate = processed ? static_cast<double>(matched) / static_cast<double>(processed) : 0.0;
        const bool discipline_ok = npu.discipline_ok();

        chain::Gate7Inputs gi;
        gi.processed = processed;
        gi.expected = n;
        gi.match_rate = rate;
        gi.min_match_rate = min_match;
        gi.nan_inf = nan_inf;
        gi.reset_count = npu.reset_count();
        gi.frame_count = npu.frame_count();
        gi.apply_count = npu.apply_count();
        gi.discipline_ok = discipline_ok;
        gi.delay = &gate;
        pass = chain::gate7_pass(gi);

        detail += " model_sha=" + model_sha;
        detail += " samples=" + std::to_string(processed) + "/" + std::to_string(n);
        detail += " matched=" + std::to_string(matched);
        detail += " match_rate=" + std::to_string(rate);
        detail += " aligned_match_rate=" + std::to_string(gate.aligned_match_rate());
        detail += " min_match_rate=" + std::to_string(min_match);
        detail += " nan_inf=" + std::to_string(nan_inf);
        detail += " npu_reset_count=" + std::to_string(npu.reset_count());
        detail += " npu_frame_count=" + std::to_string(npu.frame_count());
        detail += " npu_apply_count=" + std::to_string(npu.apply_count());
        detail += " npu_discipline=" + std::string(discipline_ok ? "OK" : "FAIL");
        detail += " delay_shift_match=" + std::to_string(gate.delay_shift_match());
        detail += " delay_shift_compared=" + std::to_string(gate.delay_shift_compared());
        detail += " delay_shift_rate=" + std::to_string(gate.delay_shift_rate());
        detail += " delay_detected=" + std::string(gate.delay_detected() ? "YES" : "NO");
        detail += " infer_us_mean=" + std::to_string(infer_us_mean);
        detail += " infer_us_p99=" + std::to_string(infer_us_p99);
        detail += " infer_us_max=" + std::to_string(infer_us_max);
        detail += " per_class=";
        for (int c = 0; c < contract.class_count; ++c) {
            if (c) detail += ",";
            detail += cat::label(contract, c) + ":" +
                      std::to_string(per_class_match[static_cast<std::size_t>(c)]) + "/" +
                      std::to_string(per_class_total[static_cast<std::size_t>(c)]);
        }
        if (processed != n) detail += " (count_short)";
        if (rate < min_match) detail += " (match_below_threshold)";
        if (nan_inf > 0) detail += " (nan_inf)";
        if (!discipline_ok) detail += " (npu_discipline_fail)";
        if (gate.delay_detected()) detail += " (delay_shift)";
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    board::emit("gate7_12class_npu", pass, detail);
    return pass ? 0 : 1;
}
