#pragma once

// radioml_npu_ab_runner.hpp -- task fix10class24-original-radioml-npu-ab1: the
// board runner that re-feeds the 480 frozen original-RadioML test frames to the
// REAL NPU (chain::NpuClassifier24) and measures, per frame, the raw-24 argmax +
// 24-dim logits -- for a host-side Host-vs-NPU A/B against the frozen Host BF16
// results (scripts/audit_radioml_npu_ab.py).  This is a MEASUREMENT, never a
// regression PASS, and it is a pure tensor->NPU path:
//
//   load .bin (8192B [2,1024] f32, SHA/size/finite fail-closed)
//     -> npu.infer x2 -> raw24_predict x2 -> per-sample + logits + summary.
//
// There is NO SDR / CFO / wide-linear / D2 / recovery / classification-window /
// 0.100-gate here, and NO Host fallback or mock: the real NPU is the only
// inferencer.  24 classes stay unmeged (rml24::raw24_predict; AM-SSB-WC/SC are
// independent).  Fixed 480 frames.  The out dir is fail-closed (never overwrites).

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "rml24_raw.hpp"
#include "radioml_npu_ab_loader.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <sys/stat.h>

#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace rmlnpuab {

using Clock = std::chrono::steady_clock;

constexpr const char* kMeasurementComplete =
    "ROUTE_F_RADIOML_ORIGINAL_NPU_AB_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete =
    "ROUTE_F_RADIOML_ORIGINAL_NPU_AB_MEASUREMENT_INCOMPLETE";

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

inline std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 2);
    for (char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += c;
                }
        }
    }
    return out;
}

inline std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

// top1/top2 indices + their raw logits (mirrors the Host per_sample_results
// top1_logit / top2_logit / margin semantics).
inline void top_two(const std::vector<float>& v, int* top1, int* top2,
                    float* v1, float* v2) {
    *top1 = -1; *top2 = -1; *v1 = 0.0f; *v2 = 0.0f;
    if (v.empty()) return;
    for (int i = 0; i < static_cast<int>(v.size()); ++i)
        if (*top1 < 0 || v[i] > v[*top1]) *top1 = i;
    for (int i = 0; i < static_cast<int>(v.size()); ++i) {
        if (i == *top1) continue;
        if (*top2 < 0 || v[i] > v[*top2]) *top2 = i;
    }
    *v1 = v[*top1];
    *v2 = (*top2 >= 0) ? v[*top2] : 0.0f;
}

struct NpuAbRunReport {
    std::string input_dir;
    std::string model_sha;
    std::string out_dir;
    std::string error;

    std::uint64_t scored = 0;
    std::uint64_t nan_or_inf = 0;
    std::uint64_t repeat_deterministic = 0;
    std::uint64_t total_correct = 0;     // npu_pred_pass1 == true raw24_class
    std::uint64_t host_agree = 0;        // npu_pred_pass1 == host_pred (A/B)
    std::vector<std::uint64_t> class_total;
    std::vector<std::uint64_t> class_correct;
    std::vector<std::uint64_t> confusion;   // 24x24 (true x pred)

    std::string results_path;
    std::string logits_path;
    std::string summary_path;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// Run the 480-frame NPU A/B measurement.  `on_frame` receives each UI result
// frame (raw24, unmerged); `npu` is the caller-owned, already-constructed
// NpuClassifier24 (this runner does NOT open/close the device).
inline NpuAbRunReport run_radioml_npu_ab(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    NpuAbRunReport rep;

    rep.input_dir = board::get_opt(argc, argv, "--input-dir", "");
    if (rep.input_dir.empty())
        throw std::runtime_error(
            "radioml-npu-ab requires --input-dir=<input data package dir> "
            "(manifest.tsv + 480 .bin)");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.out_dir = board::get_opt(argc, argv, "--out-dir", "");

    // Fail-closed out dir: never overwrite an existing directory.
    if (rep.out_dir.empty())
        throw std::runtime_error("radioml-npu-ab requires --out-dir=<fresh dir>");
    {
        struct stat st;
        if (::stat(rep.out_dir.c_str(), &st) == 0)
            throw std::runtime_error("radioml-npu-ab: --out-dir already exists: " +
                                     rep.out_dir +
                                     " (refusing to overwrite; use a fresh timestamped dir)");
        if (::mkdir(rep.out_dir.c_str(), 0777) != 0)
            throw std::runtime_error("radioml-npu-ab: cannot create --out-dir " +
                                     rep.out_dir + ": " + std::strerror(errno));
    }

    rep.results_path = join_path(rep.out_dir, "radioml_npu_ab_results.tsv");
    rep.logits_path = join_path(rep.out_dir, "radioml_npu_ab_logits.tsv");
    rep.summary_path = join_path(rep.out_dir, "radioml_npu_ab_summary.json");

    rep.class_total.assign(rml24::kClassCount, 0);
    rep.class_correct.assign(rml24::kClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml24::kClassCount) *
                             rml24::kClassCount, 0);

    // D-level input-transfer audit ON: prove source bytes == mapped destination
    // == post-forward host input (byte-identical) for every frame.
    npu.set_input_audit(true);

    std::printf("RADIOML_ORIGINAL_NPU_AB_ENV input_dir=%s out_dir=%s model_sha=%s "
                "LIBIIO_ROOT=%s LD_LIBRARY_PATH=%s\n",
                rep.input_dir.c_str(), rep.out_dir.c_str(), rep.model_sha.c_str(),
                std::getenv("LIBIIO_ROOT") ? std::getenv("LIBIIO_ROOT") : "(unset)",
                std::getenv("LD_LIBRARY_PATH") ? std::getenv("LD_LIBRARY_PATH")
                                               : "(unset)");
    std::fflush(stdout);

    const cat::Contract contract = chain::contract_24();

    // Fail-closed: verify the WHOLE input package before touching the NPU.
    const std::vector<DirectFrame> frames = load_manifest(rep.input_dir);
    std::printf("RADIOML_ORIGINAL_NPU_AB_MANIFEST frames=%llu\n",
                static_cast<unsigned long long>(frames.size()));
    std::fflush(stdout);

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    std::uint64_t global_frame_id = 0;

    std::ofstream results;
    std::ofstream logits;
    try {
        results.open(rep.results_path, std::ios::binary);
        logits.open(rep.logits_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("radioml-npu-ab: cannot open " + rep.results_path);
        if (!logits)
            throw std::runtime_error("radioml-npu-ab: cannot open " + rep.logits_path);

        results << "selection_id\thdf5_row_index\traw24_class\tmodulation\tsnr_db\t"
                << "finite\tnpu_pred_pass1\tnpu_pred_pass2\trepeat_deterministic\t"
                << "label_correct\thost_pred\tnpu_host_agree\ttop1_logit\ttop2_logit\t"
                << "margin\tresult_layer\n";
        logits << "selection_id\thdf5_row_index\traw24_class";
        for (int c = 0; c < rml24::kClassCount; ++c)
            logits << "\tlogit_" << (c < 10 ? "0" : "") << c;
        logits << "\tpred_pass1\tpred_pass2\n";

        std::vector<float> tensor(chain::kTensorFloats);
        for (const auto& fr : frames) {
            if (board::g_stop_requested) break;

            std::printf("RADIOML_ORIGINAL_NPU_AB file=%s selection_id=%d "
                        "hdf5_row_index=%lld raw24_class=%d modulation=%s snr_db=%d "
                        "host_pred=%d\n",
                        fr.input_file.c_str(), fr.selection_id,
                        static_cast<long long>(fr.hdf5_row_index), fr.raw24_class,
                        fr.modulation.c_str(), fr.snr_db, fr.host_pred);
            std::fflush(stdout);

            load_tensor(rep.input_dir, fr, tensor.data());

            const auto t0 = Clock::now();
            std::vector<float> raw24;
            npu.infer(tensor.data(), raw24);
            const double classify_us = elapsed_us(t0);
            timing.record(m22::StageId::NpuInfer, classify_us);

            std::vector<float> raw24b;
            const auto t1 = Clock::now();
            npu.infer(tensor.data(), raw24b);
            const double classify2_us = elapsed_us(t1);
            timing.record(m22::StageId::NpuInfer, classify2_us);

            rml24::RML24Result pr, pr2;
            const bool ok = rml24::raw24_predict(raw24.data(), &pr);
            const bool ok2 = rml24::raw24_predict(raw24b.data(), &pr2);
            const bool finite = ok && ok2;
            if (!finite) ++rep.nan_or_inf;

            const int raw_top = ok ? pr.raw_24_top1 : -1;
            const int raw_top_b = ok2 ? pr2.raw_24_top1 : -1;
            const bool repeat_det = finite && (raw_top == raw_top_b);
            if (repeat_det) ++rep.repeat_deterministic;

            const bool correct = finite && (raw_top == fr.raw24_class);
            const bool agree = finite && (raw_top == fr.host_pred);
            if (agree) ++rep.host_agree;

            int top1 = -1, top2 = -1;
            float v1 = 0.0f, v2 = 0.0f;
            top_two(raw24, &top1, &top2, &v1, &v2);
            const float margin = v1 - v2;

            std::printf("RADIOML_ORIGINAL_NPU_AB_CLASSIFY file=%s host_pred=%d "
                        "npu_pred=%d source_label=%d npu_host_agree=%d "
                        "label_correct=%d repeat_deterministic=%d finite=%d\n",
                        fr.input_file.c_str(), fr.host_pred, raw_top, fr.raw24_class,
                        agree ? 1 : 0, correct ? 1 : 0, repeat_det ? 1 : 0,
                        finite ? 1 : 0);
            std::fflush(stdout);

            ++global_frame_id;
            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;
            r.source = "radioml_original_npu_ab";
            r.mock = false;
            chain::fill_result_rml24(r, raw24, contract, rep.model_sha,
                                     std::numeric_limits<double>::quiet_NaN());
            r.classify_us = classify_us;
            r.e2e_us = classify_us + classify2_us;
            on_frame(r);

            ++rep.scored;
            if (correct) ++rep.total_correct;
            if (finite && raw_top >= 0 && raw_top < rml24::kClassCount) {
                ++rep.confusion[static_cast<std::size_t>(fr.raw24_class) *
                                    rml24::kClassCount + raw_top];
            }
            ++rep.class_total[static_cast<std::size_t>(fr.raw24_class)];
            if (correct) ++rep.class_correct[static_cast<std::size_t>(fr.raw24_class)];

            results << fr.selection_id << "\t" << fr.hdf5_row_index << "\t"
                    << fr.raw24_class << "\t" << fr.modulation << "\t" << fr.snr_db
                    << "\t" << (finite ? 1 : 0) << "\t" << raw_top << "\t"
                    << raw_top_b << "\t" << (repeat_det ? 1 : 0) << "\t"
                    << (correct ? 1 : 0) << "\t" << fr.host_pred << "\t"
                    << (agree ? 1 : 0) << "\t" << v1 << "\t" << v2 << "\t"
                    << margin << "\tNPU_BF16\n";

            logits << fr.selection_id << "\t" << fr.hdf5_row_index << "\t"
                   << fr.raw24_class;
            for (int c = 0; c < rml24::kClassCount; ++c)
                logits << "\t" << raw24[static_cast<std::size_t>(c)];
            logits << "\t" << raw_top << "\t" << raw_top_b << "\n";
        }
        results.close();
        logits.close();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    const double label_accuracy = rep.scored > 0
        ? static_cast<double>(rep.total_correct) / static_cast<double>(rep.scored)
        : 0.0;
    const double host_agreement = rep.scored > 0
        ? static_cast<double>(rep.host_agree) / static_cast<double>(rep.scored)
        : 0.0;

    const bool complete = rep.error.empty() && rep.scored == kFrameCount &&
                          rep.nan_or_inf == 0 &&
                          rep.repeat_deterministic == kFrameCount;
    const std::string measurement_token =
        complete ? kMeasurementComplete : kMeasurementIncomplete;

    // Summary JSON.
    {
        std::ofstream f(rep.summary_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.summary_path);
        f << "{\n";
        f << "  \"token\":\"" << measurement_token << "\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"deployment_mode\":\"" << rml24::kDeploymentMode << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"input_dir\":\"" << json_escape(rep.input_dir) << "\",\n";
        f << "  \"out_dir\":\"" << json_escape(rep.out_dir) << "\",\n";
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"nan_or_inf\":" << rep.nan_or_inf << ",\n";
        f << "  \"repeat_deterministic\":" << rep.repeat_deterministic << ",\n";
        f << "  \"label_accuracy\":" << label_accuracy << ",\n";
        f << "  \"host_agreement\":" << host_agreement << ",\n";
        f << "  \"total_correct\":" << rep.total_correct << ",\n";
        f << "  \"host_agree\":" << rep.host_agree << "\n";
        f << "}\n";
    }

    std::printf("ROUTE_F_RADIOML_ORIGINAL_NPU_AB token=%s measurement=%s scored=%llu "
                "nan_or_inf=%llu repeat_deterministic=%llu/%llu label_accuracy=%.6f "
                "host_agreement=%.6f\n",
                measurement_token.c_str(), measurement_token.c_str(),
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.nan_or_inf),
                static_cast<unsigned long long>(rep.repeat_deterministic),
                static_cast<unsigned long long>(rep.scored),
                label_accuracy, host_agreement);
    std::fflush(stdout);

    rep.functional_pass = complete;

    std::string detail = "input_dir=" + rep.input_dir +
                         " model_sha=" + rep.model_sha +
                         " scored=" + std::to_string(rep.scored) +
                         " nan_or_inf=" + std::to_string(rep.nan_or_inf) +
                         " repeat_deterministic=" +
                         std::to_string(rep.repeat_deterministic) +
                         " label_accuracy=" + std::to_string(label_accuracy) +
                         " host_agreement=" + std::to_string(host_agreement);
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    rep.detail = detail;

    return rep;
}

}  // namespace rmlnpuab
