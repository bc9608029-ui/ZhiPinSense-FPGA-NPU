#pragma once

// iq_clean_iq_23class_fix10.hpp -- fix10 Path B: the GENERATED-CLEAN pure-digital
// baseline runner.  No libiio, no RF, no gate, no recovery: it loads the clean
// CI16 the generator (gen_generated_clean_23.py) wrote, pushes it STRAIGHT into
// the PreprocessChain, applies the D2 restore, selects the reference-aligned
// window, and classifies with the deployed model -- then compares the board's
// merged prediction against the FROZEN offline baseline (predict_clean_baseline.py)
// per sample.
//
// This is the clean digital path the Path C dual-SDR run is compared against
// (the SAME CI16 file, so the comparison is per-sample, not per-class).  It
// deliberately does NOT touch any RF, does NOT open a device, and does NOT apply
// the coarse-CFO sequence -- that is Path A/C's job.  A clean run therefore
// proves only the board digital chain (CI16 -> preprocess -> D2 restore -> window
// -> NPU) reproduces the frozen model's own predictions.
//
// The clean manifest reuses the 24-column D2 schema (route_d2_rf_manifest.tsv) so
// the EXISTING loader iqdloop::load_d2_sidecar reads it unchanged (fail-closed on
// SHA/size/sample-rate/class-consistency).  The clean baseline is the 6-column
// §9 format:
//
//     source_index  file_name  sha256  deployed_class  split_role  frozen_baseline_pred
//
// which DIFFERS from the fix9r2g1 baseline (that one carries original_sha256 +
// modulation in place of file_name + sha256), so a dedicated loader is defined
// here.  The baseline identity check below is the §10 SHA-identity proof: the
// baseline's `sha256` (== the generator manifest quantized_sha256) must equal the
// frozen CI16 SHA the D2 loader just verified against the SAME manifest, and the
// file_name must match -- so Path B and Path C are tied to ONE batch of bytes by
// double SHA verification, not by convention.
//
// Outputs (measurement, never a regression PASS): per-sample clean prediction +
// prediction-agreement vs the frozen baseline + the clean measurement tokens.
// A clean run never promotes ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_clean_baseline.hpp"
#include "iq_clean_diagnostic_fix10prep1.hpp"
#include "rml23_merged.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <sys/stat.h>

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <string>
#include <vector>

namespace iqclean23fix10 {

using Clock = std::chrono::steady_clock;

// ---- the fix10 clean-path tokens (measurement, never a regression PASS) -----
constexpr const char* kCleanMeasurementComplete =
    "ROUTE_F_FIX10_CLEAN_IQ_MEASUREMENT_COMPLETE";
constexpr const char* kCleanMeasurementIncomplete =
    "ROUTE_F_FIX10_CLEAN_IQ_MEASUREMENT_INCOMPLETE";
constexpr const char* kCleanModelDomainNotProven =
    "ROUTE_F_FIX10_CLEAN_IQ_MODEL_DOMAIN_NOT_PROVEN";

// ---- local merge + argmax (mirrors iqdual23fix10) ---------------------------
inline std::vector<float> merge23(const std::vector<float>& raw24) {
    if (raw24.size() != static_cast<std::size_t>(rml23::kNpuOutputDim))
        throw std::runtime_error("rml23: raw logits width != 24");
    float m23[rml23::kDeployedClassCount];
    if (!rml23::merge_logits_23(raw24.data(), m23))
        throw std::runtime_error("rml23: merge fail-closed (non-finite logits)");
    return std::vector<float>(m23, m23 + rml23::kDeployedClassCount);
}

inline int argmax_of(const std::vector<float>& v) {
    if (v.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(v.size()); ++i)
        if (v[i] > v[best]) best = i;
    return best;
}

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

// ---------------------------------------------------------------------------
// Rf23CleanRunReport
// ---------------------------------------------------------------------------
struct Rf23CleanRunReport {
    std::string frozen_dir;
    std::string input_kind;
    std::string model_sha;
    std::string baseline_path;
    std::uint64_t frozen_files = 0;
    std::uint64_t holdout_files = 0;
    std::uint64_t baseline_rows = 0;
    bool baseline_identity_ok = false;
    std::string baseline_identity_report;
    std::string error;

    // scoring (measurement, never a PASS gate)
    std::uint64_t scored = 0;
    std::uint64_t excluded = 0;
    std::uint64_t total_valid = 0;
    std::uint64_t total_correct = 0;
    std::vector<std::uint64_t> class_total;
    std::vector<std::uint64_t> class_correct;
    std::vector<std::uint64_t> confusion;
    std::map<std::string, std::uint64_t> exclude_reasons;

    // rf_pred == frozen_baseline_pred (the clean digital-path metric)
    std::uint64_t prediction_agreement_count = 0;
    std::uint64_t tensor_dump_count = 0;
    std::uint64_t logits_dump_count = 0;
    double prediction_agreement = 0.0;
    double label_accuracy = 0.0;
    double macro_accuracy = 0.0;

    std::string results_path;
    std::string confusion_path;
    std::string per_class_path;
    std::string summary_path;
    std::string log_path;
    std::string tensor_dir;
    std::string logits_dir;
    std::string diagnostic_token;
    std::string gate_report;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// ---------------------------------------------------------------------------
// run_iq_clean_iq_23class_fix10
// ---------------------------------------------------------------------------
inline Rf23CleanRunReport run_iq_clean_iq_23class_fix10(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    Rf23CleanRunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-clean-iq-23class-fix10 requires --input-kind=radioml-d2-2p56m (the "
            "clean manifest reuses the D2 schema; got '" + rep.input_kind + "').");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-clean-iq-23class-fix10 requires "
                                 "--frozen-dir=<clean artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.baseline_path = board::get_opt(argc, argv, "--baseline", "");
    if (rep.baseline_path.empty())
        throw std::runtime_error("iq-clean-iq-23class-fix10 requires "
                                 "--baseline=<clean_baseline.tsv>");
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::uint64_t max_files = board::opt_u64(argc, argv, "--max-files", 0);
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    const std::string out_dir = board::get_opt(argc, argv, "--out-dir", "");

    if (!out_dir.empty() && ::mkdir(out_dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("fix10-clean: cannot create --out-dir " + out_dir +
                                 ": " + std::strerror(errno));

    rep.results_path = join_path(out_dir, "route_f_fix10_clean_iq_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_f_fix10_clean_iq_confusion_23.csv");
    rep.per_class_path = join_path(out_dir, "route_f_fix10_clean_iq_per_class.json");
    rep.summary_path = join_path(out_dir, "route_f_fix10_clean_iq_summary.json");
    rep.log_path = join_path(out_dir, "route_f_fix10_clean_iq_summary.log");
    rep.tensor_dir = join_path(out_dir, "npu_input_tensors");
    rep.logits_dir = join_path(out_dir, "npu_logits");

    iqclean23fix10diag::require_directory(rep.tensor_dir);
    iqclean23fix10diag::require_directory(rep.logits_dir);

    rep.class_total.assign(rml23::kDeployedClassCount, 0);
    rep.class_correct.assign(rml23::kDeployedClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml23::kDeployedClassCount) *
                             rml23::kDeployedClassCount, 0);

    const cat::Contract contract = chain::contract_23();

    std::printf("IQ_CLEAN_IQ_23CLASS_FIX10_ENV LIBIIO_ROOT=%s LD_LIBRARY_PATH=%s\n",
                std::getenv("LIBIIO_ROOT") ? std::getenv("LIBIIO_ROOT") : "(unset)",
                std::getenv("LD_LIBRARY_PATH") ? std::getenv("LD_LIBRARY_PATH") : "(unset)");
    std::fflush(stdout);

    // ---- load the clean frozen D2 sidecar + the clean baseline ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    const std::map<std::uint64_t, CleanBaselineRow> baseline =
        load_clean_baseline(rep.baseline_path, rml23::kDeployedClassCount);
    rep.baseline_rows = static_cast<std::uint64_t>(baseline.size());

    if (!file_filter.empty()) {
        std::vector<iqdloop::FrozenIq> kept;
        for (const auto& fz : frozen)
            if (fz.file_name.find(file_filter) != std::string::npos)
                kept.push_back(fz);
        frozen = std::move(kept);
    }

    std::vector<iqdloop::FrozenIq> calib, holdout;
    for (const auto& fz : frozen)
        (fz.is_calibration ? calib : holdout).push_back(fz);
    if (max_files > 0 && max_files < holdout.size())
        holdout.resize(static_cast<std::size_t>(max_files));
    if (holdout.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: no clean holdout files "
                                 "after file-filter/max-files selection");

    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    rep.holdout_files = static_cast<std::uint64_t>(holdout.size());

    // ---- baseline identity check (the §10 SHA-identity proof): every holdout file
    //      must match a baseline row on source_index + file_name + sha256 +
    //      deployed_class.  Fail-closed on a missing/duplicate/mismatched row. ----
    {
        bool ok = true;
        std::string report;
        for (const auto& fz : holdout) {
            auto it = baseline.find(static_cast<std::uint64_t>(fz.source_index));
            if (it == baseline.end()) {
                ok = false;
                report += "missing:" + fz.file_name + ";";
            } else if (it->second.sha256 != fz.sha256 ||
                       it->second.file_name != fz.file_name ||
                       it->second.deployed_class != fz.deployed_class) {
                ok = false;
                report += "mismatch:" + fz.file_name + ";";
            }
        }
        rep.baseline_identity_ok = ok;
        rep.baseline_identity_report = report;
    }

    std::printf("IQ_CLEAN_IQ_23CLASS_FIX10 BOARD_REQUIRED input_kind=%s frozen_dir=%s "
                "frozen_files=%llu holdout_files=%llu baseline_rows=%llu "
                "baseline_identity_ok=%d out_dir=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.baseline_rows),
                rep.baseline_identity_ok ? 1 : 0,
                out_dir.empty() ? "." : out_dir.c_str());
    std::fflush(stdout);

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    std::uint64_t global_frame_id = 0;

    std::ofstream results;
    try {
        results.open(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("fix10-clean: cannot open " + rep.results_path);
        results << "file_name\tsource_index\traw24_class\tdeployed23_class\t"
                << "modulation\tsnr_db\tsplit_role\tvalid\traw24_pred\t"
                << "merged23_pred\tcorrect\tbaseline_pred\tprediction_agreement\t"
                << "window_corr\twindow_nmse\tdelay_offset\tboard_tensor_sha256\t"
                << "reference_tensor_sha256\ttensor_sha_equal\tmax_abs_error\t"
                << "rms_error\tnpu_logits_sha256\tmerged23_top2\tmerged23_margin\t"
                << "verdict\n";

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;

            std::printf("IQ_CLEAN_IQ_23CLASS_FIX10 file=%s input_kind=%s "
                        "source_index=%lld source_class=%d deployed_class=%d "
                        "modulation=%s complex_count=%llu split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(),
                        static_cast<long long>(fz.source_index), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        fz.split_role.c_str());
            std::fflush(stdout);

            // Load the clean CI16 (already SHA/size-verified by load_d2_sidecar).
            const std::vector<std::int16_t> ci16 =
                iqdloop::load_ci16(fz.path, fz.complex_count);

            // ---- chain -> D2 restore (no RF: the CI16 is the clean TX waveform) --
            chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, 1.0f);
            {
                m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                chain.push_int16(ci16.data(), fz.complex_count);
            }
            std::vector<float> recovered_stream;
            {
                std::vector<float> t(chain::kTensorFloats);
                while (chain.ready() > 0) {
                    if (board::g_stop_requested) break;
                    if (!chain.pull_tensor(t.data())) break;
                    recovered_stream.insert(recovered_stream.end(), t.begin(), t.end());
                }
            }
            iqdloop::apply_d2_restore_to_stream(recovered_stream, chain::kFrameComplex,
                                                fz.original_dc_i, fz.original_dc_q,
                                                fz.d2_rec_scale);

            std::printf("IQ_CLEAN_IQ_23CLASS_FIX10_D2_RESTORE file=%s source_index=%lld "
                        "dc_i=%.9f dc_q=%.9f rec_scale=%.9f\n",
                        fz.file_name.c_str(), static_cast<long long>(fz.source_index),
                        fz.original_dc_i, fz.original_dc_q, fz.d2_rec_scale);
            std::fflush(stdout);

            const std::vector<float> ref =
                iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                               fz.recovered_tensor_sha256);
            const iqdloop::ClassificationWindow cw =
                iqdloop::select_classification_window(recovered_stream, ref);
            std::printf("IQ_CLEAN_IQ_23CLASS_FIX10_WINDOW file=%s recovered_frames=%llu "
                        "delay_offset=%d corr=%.6f nmse=%.6f gain_db=%.3f sha_equal=%d\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(cw.recovered_frames),
                        cw.delay_offset, cw.tensor_corr, cw.tensor_nmse,
                        cw.tensor_gain_db, cw.sha_equal ? 1 : 0);
            std::fflush(stdout);

            if (!cw.valid || cw.aligned_tensor.empty()) {
                ++rep.excluded;
                ++rep.exclude_reasons["CLEAN_NO_VALID_WINDOW"];
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t-1\t-1\t"
                        << cw.tensor_corr << "\t" << cw.tensor_nmse << "\t"
                        << cw.delay_offset
                        << "\t-\t-\t0\tnan\tnan\t-\t-1\tnan\t"
                        << "CLEAN_NO_VALID_WINDOW\n";
                continue;
            }

            // Persist the exact bytes passed to npu.infer().  Evidence is
            // fail-closed: a write/flush/rename failure aborts the run.
            if (cw.aligned_tensor.size() != iqclean23fix10diag::kTensorFloats)
                throw std::runtime_error("fix10-clean: aligned tensor width != 2048");
            const std::string stem = iqclean23fix10diag::file_stem(fz.file_name);
            const auto tensor_dump = iqclean23fix10diag::write_atomic(
                rep.tensor_dir, stem + "__board_npu_input.f32",
                cw.aligned_tensor.data(), iqclean23fix10diag::kTensorBytes);
            if (!tensor_dump.ok)
                throw std::runtime_error("fix10-clean: tensor dump failed for " +
                                         fz.file_name + ": " + tensor_dump.error);
            ++rep.tensor_dump_count;
            const iqclean23fix10diag::TensorDiff td =
                iqclean23fix10diag::tensor_diff(cw.aligned_tensor.data(), ref.data(),
                                                iqclean23fix10diag::kTensorFloats);
            std::printf("IQ_CLEAN_IQ_23CLASS_FIX10_NPU_INPUT file=%s bytes=%llu "
                        "board_tensor_sha256=%s reference_tensor_sha256=%s "
                        "sha_equal=%d max_abs_error=%.12g rms_error=%.12g\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(tensor_dump.bytes),
                        tensor_dump.sha256.c_str(), fz.recovered_tensor_sha256.c_str(),
                        tensor_dump.sha256 == fz.recovered_tensor_sha256 ? 1 : 0,
                        td.max_abs_error, td.rms_error);
            std::fflush(stdout);

            // ---- classify the exact persisted reference-aligned window ----
            const auto t0 = Clock::now();
            std::vector<float> raw24;
            npu.infer(cw.aligned_tensor.data(), raw24);
            const double classify_us = elapsed_us(t0);
            timing.record(m22::StageId::NpuInfer, classify_us);

            const std::vector<float> m23 = merge23(raw24);
            const int raw_top = argmax_of(raw24);
            const int merged_top = argmax_of(m23);
            if (raw24.size() != iqclean23fix10diag::kLogitFloats)
                throw std::runtime_error("fix10-clean: NPU logits width != 24");
            for (float v : raw24)
                if (!std::isfinite(v))
                    throw std::runtime_error("fix10-clean: NPU logits non-finite");
            const auto logits_dump = iqclean23fix10diag::write_atomic(
                rep.logits_dir, stem + "__npu_logits.f32", raw24.data(),
                iqclean23fix10diag::kLogitBytes);
            if (!logits_dump.ok)
                throw std::runtime_error("fix10-clean: logits dump failed for " +
                                         fz.file_name + ": " + logits_dump.error);
            ++rep.logits_dump_count;
            int merged_second = merged_top == 0 ? 1 : 0;
            for (int i = 0; i < static_cast<int>(m23.size()); ++i)
                if (i != merged_top && m23[i] > m23[merged_second]) merged_second = i;
            const double merged_margin =
                static_cast<double>(m23[merged_top]) - m23[merged_second];
            std::printf("IQ_CLEAN_IQ_23CLASS_FIX10_NPU_LOGITS file=%s sha256=%s "
                        "raw24_top1=%d merged23_top1=%d merged23_top2=%d "
                        "merged23_margin=%.9g\n",
                        fz.file_name.c_str(), logits_dump.sha256.c_str(), raw_top,
                        merged_top, merged_second, merged_margin);
            std::fflush(stdout);
            const bool correct = (merged_top == fz.deployed_class);

            // ---- rf_pred vs the FROZEN offline baseline prediction (MEASUREMENT;
            //      read by stable key source_index, never deployed_class, never row
            //      number, never a fuzzy file name).  A missing key fails the
            //      agreement (fail-closed) but never gates a PASS here.
            int baseline_pred = -1;
            bool baseline_pred_found = false;
            {
                const auto bit = baseline.find(static_cast<std::uint64_t>(fz.source_index));
                if (bit != baseline.end()) {
                    baseline_pred = bit->second.frozen_baseline_pred;
                    baseline_pred_found = true;
                }
            }
            const bool prediction_agreement =
                baseline_pred_found && (merged_top == baseline_pred);
            const bool label_correct = correct;
            if (prediction_agreement) ++rep.prediction_agreement_count;
            std::printf("IQ_CLEAN_IQ_23CLASS_FIX10_CLASSIFY file=%s baseline_pred=%d "
                        "rf_pred=%d source_label=%d prediction_agreement=%d "
                        "label_correct=%d\n",
                        fz.file_name.c_str(), baseline_pred, merged_top, fz.source_class,
                        prediction_agreement ? 1 : 0, label_correct ? 1 : 0);
            std::fflush(stdout);

            ++global_frame_id;
            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;
            r.source = "iq_clean_iq_23class_fix10";
            r.mock = false;
            chain::fill_result_rml23(r, raw24, m23, contract, rep.model_sha,
                                     std::numeric_limits<double>::quiet_NaN());
            r.classify_us = classify_us;
            r.e2e_us = classify_us;
            on_frame(r);

            ++rep.scored;
            ++rep.total_valid;
            if (correct) ++rep.total_correct;
            ++rep.confusion[static_cast<std::size_t>(fz.deployed_class) *
                                rml23::kDeployedClassCount + merged_top];
            ++rep.class_total[static_cast<std::size_t>(fz.deployed_class)];
            if (correct) ++rep.class_correct[static_cast<std::size_t>(fz.deployed_class)];

            results << fz.file_name << "\t" << fz.source_index << "\t"
                    << fz.source_class << "\t" << fz.deployed_class << "\t"
                    << fz.modulation << "\t" << fz.snr_db << "\t"
                    << fz.split_role << "\t1\t" << raw_top << "\t" << merged_top
                    << "\t" << (correct ? 1 : 0) << "\t" << baseline_pred
                    << "\t" << (prediction_agreement ? 1 : 0) << "\t"
                    << cw.tensor_corr << "\t" << cw.tensor_nmse << "\t"
                    << cw.delay_offset << "\t" << tensor_dump.sha256 << "\t"
                    << fz.recovered_tensor_sha256 << "\t"
                    << (tensor_dump.sha256 == fz.recovered_tensor_sha256 ? 1 : 0)
                    << "\t" << td.max_abs_error << "\t" << td.rms_error << "\t"
                    << logits_dump.sha256 << "\t" << merged_second << "\t"
                    << merged_margin << "\tCLEAN_DIGITAL_SCORED\n";

            std::printf("IQ_CLEAN_IQ_23CLASS_FIX10 file=%s frames=1 correct=%d "
                        "deployed=%d source=%d raw24_pred=%d merged23_pred=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.deployed_class,
                        fz.source_class, raw_top, merged_top);
            std::fflush(stdout);
        }
        results.close();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- measurement (NEVER a regression PASS) ----
    rep.prediction_agreement =
        rep.scored > 0
            ? static_cast<double>(rep.prediction_agreement_count) /
                  static_cast<double>(rep.scored)
            : 0.0;
    rep.label_accuracy = rep.total_valid > 0
        ? static_cast<double>(rep.total_correct) /
              static_cast<double>(rep.total_valid) : 0.0;
    {
        std::size_t seen = 0;
        for (int c = 0; c < rml23::kDeployedClassCount; ++c) {
            if (rep.class_total[static_cast<std::size_t>(c)] == 0) continue;
            ++seen;
            rep.macro_accuracy += static_cast<double>(
                                      rep.class_correct[static_cast<std::size_t>(c)]) /
                                  static_cast<double>(
                                      rep.class_total[static_cast<std::size_t>(c)]);
        }
        if (seen > 0) rep.macro_accuracy /= static_cast<double>(seen);
    }

    const std::string measurement_token = rep.error.empty()
                                              ? kCleanMeasurementComplete
                                              : kCleanMeasurementIncomplete;
    const iqclean23fix10diag::CleanGateResult clean_gate =
        iqclean23fix10diag::evaluate_clean_gate({
            rep.error.empty(), rep.baseline_identity_ok,
            static_cast<std::size_t>(rep.holdout_files),
            static_cast<std::size_t>(rep.baseline_rows),
            static_cast<std::size_t>(rep.scored),
            static_cast<std::size_t>(rep.excluded),
            static_cast<std::size_t>(rep.prediction_agreement_count),
            static_cast<std::size_t>(rep.tensor_dump_count),
            static_cast<std::size_t>(rep.logits_dump_count)});
    rep.functional_pass = clean_gate.pass;
    rep.gate_report = clean_gate.report;
    rep.diagnostic_token = clean_gate.pass
                               ? "ROUTE_F_FIX10_CLEAN_IQ_DIAGNOSTIC_PASS"
                               : "ROUTE_F_FIX10_CLEAN_IQ_DIAGNOSTIC_FAIL";

    // Confusion CSV.
    {
        std::ofstream f(rep.confusion_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.confusion_path);
        f << "true\\pred";
        for (int c = 0; c < rml23::kDeployedClassCount; ++c)
            f << "," << rml23::kLabelOrder23[c];
        f << "\n";
        for (int t = 0; t < rml23::kDeployedClassCount; ++t) {
            f << rml23::kLabelOrder23[t];
            for (int p = 0; p < rml23::kDeployedClassCount; ++p)
                f << "," << rep.confusion[static_cast<std::size_t>(t) *
                                              rml23::kDeployedClassCount + p];
            f << "\n";
        }
    }

    // Per-class JSON.
    {
        std::ofstream f(rep.per_class_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.per_class_path);
        f << "[\n";
        for (int c = 0; c < rml23::kDeployedClassCount; ++c) {
            const std::uint64_t tot = rep.class_total[static_cast<std::size_t>(c)];
            const std::uint64_t corr = rep.class_correct[static_cast<std::size_t>(c)];
            const double acc = tot > 0 ? static_cast<double>(corr) /
                                         static_cast<double>(tot) : 0.0;
            f << (c == 0 ? "  " : " ,") << "{\"index\":" << c
              << ",\"name\":\"" << rml23::kLabelOrder23[c] << "\""
              << ",\"total\":" << tot << ",\"correct\":" << corr
              << ",\"accuracy\":" << acc << "}\n";
        }
        f << "]\n";
    }

    // Summary JSON.
    {
        std::ofstream f(rep.summary_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.summary_path);
        f << "{\n";
        f << "  \"token\":\"" << rep.diagnostic_token << "\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"model_domain_token\":\"" << kCleanModelDomainNotProven << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"frozen_dir\":\"" << json_escape(rep.frozen_dir) << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"baseline_path\":\"" << json_escape(rep.baseline_path) << "\",\n";
        f << "  \"baseline_rows\":" << rep.baseline_rows << ",\n";
        f << "  \"baseline_identity_ok\":"
          << (rep.baseline_identity_ok ? "true" : "false") << ",\n";
        f << "  \"holdout_files\":" << rep.holdout_files << ",\n";
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"excluded\":" << rep.excluded << ",\n";
        f << "  \"prediction_agreement\":" << rep.prediction_agreement << ",\n";
        f << "  \"prediction_agreement_count\":"
          << rep.prediction_agreement_count << ",\n";
        f << "  \"tensor_dump_count\":" << rep.tensor_dump_count << ",\n";
        f << "  \"logits_dump_count\":" << rep.logits_dump_count << ",\n";
        f << "  \"gate_report\":\"" << json_escape(rep.gate_report) << "\",\n";
        f << "  \"label_accuracy\":" << rep.label_accuracy << ",\n";
        f << "  \"macro_accuracy\":" << rep.macro_accuracy << ",\n";
        f << "  \"exclude_reasons\":{";
        bool first_reason = true;
        for (const auto& kv : rep.exclude_reasons) {
            if (!first_reason) f << ",";
            f << "\"" << json_escape(kv.first) << "\":" << kv.second;
            first_reason = false;
        }
        f << "}\n";
        f << "}\n";
    }

    // Summary log.
    {
        std::ofstream f(rep.log_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.log_path);
        f << "token=" << rep.diagnostic_token
          << " measurement=" << measurement_token
          << " model_domain=" << kCleanModelDomainNotProven
          << " holdout=" << rep.holdout_files
          << " scored=" << rep.scored
          << " excluded=" << rep.excluded
          << " prediction_agreement=" << rep.prediction_agreement
          << " prediction_agreement_count=" << rep.prediction_agreement_count
          << " tensor_dump_count=" << rep.tensor_dump_count
          << " logits_dump_count=" << rep.logits_dump_count
          << " report=" << rep.gate_report
          << " label_accuracy=" << rep.label_accuracy
          << " macro_accuracy=" << rep.macro_accuracy
          << "\n";
    }

    std::printf("ROUTE_F_FIX10_CLEAN_IQ token=%s measurement=%s model_domain=%s "
                "scored=%llu excluded=%llu prediction_agreement=%.6f "
                "prediction_agreement_count=%llu tensor_dump_count=%llu "
                "logits_dump_count=%llu label_accuracy=%.6f macro_accuracy=%.6f "
                "report=%s\n",
                rep.diagnostic_token.c_str(), measurement_token.c_str(),
                kCleanModelDomainNotProven,
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.excluded),
                rep.prediction_agreement,
                static_cast<unsigned long long>(rep.prediction_agreement_count),
                static_cast<unsigned long long>(rep.tensor_dump_count),
                static_cast<unsigned long long>(rep.logits_dump_count),
                rep.label_accuracy, rep.macro_accuracy, rep.gate_report.c_str());
    std::fflush(stdout);

    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " baseline_rows=" + std::to_string(rep.baseline_rows) +
                         " baseline_identity_ok=" + (rep.baseline_identity_ok ? "1" : "0") +
                         " scored=" + std::to_string(rep.scored) +
                         " excluded=" + std::to_string(rep.excluded) +
                         " prediction_agreement=" +
                         std::to_string(rep.prediction_agreement) +
                         " prediction_agreement_count=" +
                         std::to_string(rep.prediction_agreement_count) +
                         " tensor_dump_count=" + std::to_string(rep.tensor_dump_count) +
                         " logits_dump_count=" + std::to_string(rep.logits_dump_count) +
                         " diagnostic_token=" + rep.diagnostic_token +
                         " report=" + rep.gate_report +
                         " label_accuracy=" + std::to_string(rep.label_accuracy) +
                         " macro_accuracy=" + std::to_string(rep.macro_accuracy);
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    rep.detail = detail;

    return rep;
}

}  // namespace iqclean23fix10
