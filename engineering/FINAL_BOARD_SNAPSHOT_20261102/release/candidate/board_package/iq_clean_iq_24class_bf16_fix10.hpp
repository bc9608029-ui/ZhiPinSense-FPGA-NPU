#pragma once

// iq_clean_iq_24class_bf16_fix10.hpp -- fix10class24-dualsdr1 §8 (Phase 3): the
// GENERATED-CLEAN pure-digital 24-class BF16 baseline runner.  No libiio, no RF, no
// gate, no recovery: it loads the clean CI16 the generator wrote, pushes it STRAIGHT
// into the PreprocessChain, applies the D2 restore, selects the reference-aligned
// window, and classifies with the deployed 24-class BF16 model -- then compares the
// board's RAW-24 argmax (NO AM-SSB merge) against the FROZEN offline baseline
// (scripts/predict_rml24_bf16_baseline.py, read by stable source_index key) per
// sample.
//
// This is the 24-class UNMERGED analogue of iq_clean_iq_23class_fix10.hpp.  The
// AM-SSB-WC (raw 17) and AM-SSB-SC (raw 18) sub-classes stay TWO independent
// classes: the NPU's raw 24-dim logits are classified directly by rml24::raw24_predict,
// and merge23() is deliberately absent from this path.  The 23-class merged mode
// (iq_clean_iq_23class_fix10.hpp) remains the stable main path and is untouched.
//
// The clean manifest reuses the 24-column D2 schema (route_d2_rf_manifest.tsv) so the
// EXISTING loader iqdloop::load_d2_sidecar reads it unchanged (fail-closed on
// SHA/size/sample-rate/class-consistency).  The 24-class baseline is the 7-column
// §6 format produced by scripts/predict_rml24_bf16_baseline.py:
//
//     source_index  original_sha256  raw24_class  modulation  split_role
//     frozen_bf16_raw24_pred  model_sha256
//
// loaded by rml24bf16::load_baseline (rml24_bf16_baseline.hpp).  The identity check
// below ties the board's holdout to ONE batch of bytes via source_index +
// original_sha256 + raw24_class + modulation + split_role (the D2 manifest's
// original_sha256 must equal the baseline's original_sha256), so a swapped or
// substituted sample can never silently score.
//
// Outputs (measurement, never a regression PASS): per-sample clean raw24 prediction
// + prediction-agreement vs the frozen baseline + the clean measurement tokens, plus
// the §8 board-gate fields: scored / excluded / prediction_agreement / label_correct /
// WC / SC / nan_or_inf / repeat_deterministic.  A clean run never promotes
// ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "rml24_raw.hpp"
#include "rml24_bf16_baseline.hpp"
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

namespace iqclean24bf16fix10 {

using Clock = std::chrono::steady_clock;

// ---- the fix10class24 24-class clean-path tokens (measurement, never a PASS) ---
constexpr const char* kCleanMeasurementComplete =
    "ROUTE_F_FIX10CLASS24_BF16_CLEAN_IQ_MEASUREMENT_COMPLETE";
constexpr const char* kCleanMeasurementIncomplete =
    "ROUTE_F_FIX10CLASS24_BF16_CLEAN_IQ_MEASUREMENT_INCOMPLETE";
constexpr const char* kCleanModelDomainNotProven =
    "ROUTE_F_FIX10CLASS24_BF16_CLEAN_IQ_MODEL_DOMAIN_NOT_PROVEN";

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
// Rf24CleanRunReport
// ---------------------------------------------------------------------------
struct Rf24CleanRunReport {
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

    // rf_pred == frozen_bf16_raw24_pred (the clean digital-path metric)
    std::uint64_t prediction_agreement_count = 0;
    double prediction_agreement = 0.0;
    double label_accuracy = 0.0;
    double macro_accuracy = 0.0;

    // §8 board-gate fields.
    std::uint64_t wc_total = 0, wc_correct = 0;   // AM-SSB-WC (raw 17)
    std::uint64_t sc_total = 0, sc_correct = 0;   // AM-SSB-SC (raw 18)
    std::uint64_t nan_or_inf = 0;                 // samples with a non-finite logit
    std::uint64_t repeat_deterministic = 0;       // samples whose 2nd infer agrees

    std::string results_path;
    std::string confusion_path;
    std::string per_class_path;
    std::string summary_path;
    std::string log_path;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// ---------------------------------------------------------------------------
// run_iq_clean_iq_24class_bf16_fix10
// ---------------------------------------------------------------------------
inline Rf24CleanRunReport run_iq_clean_iq_24class_bf16_fix10(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    Rf24CleanRunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-clean-iq-24class-bf16-fix10 requires --input-kind=radioml-d2-2p56m "
            "(the clean manifest reuses the D2 schema; got '" + rep.input_kind + "').");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-clean-iq-24class-bf16-fix10 requires "
                                 "--frozen-dir=<clean artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.baseline_path = board::get_opt(argc, argv, "--baseline", "");
    if (rep.baseline_path.empty())
        throw std::runtime_error("iq-clean-iq-24class-bf16-fix10 requires "
                                 "--baseline=<clean24_smoke_raw24_bf16_baseline.tsv>");
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::uint64_t max_files = board::opt_u64(argc, argv, "--max-files", 0);
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    const std::string out_dir = board::get_opt(argc, argv, "--out-dir", "");

    if (!out_dir.empty() && ::mkdir(out_dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("fix10class24-clean: cannot create --out-dir " +
                                 out_dir + ": " + std::strerror(errno));

    rep.results_path = join_path(out_dir, "route_f_fix10class24_bf16_clean_iq_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_f_fix10class24_bf16_clean_iq_confusion_24.csv");
    rep.per_class_path = join_path(out_dir, "route_f_fix10class24_bf16_clean_iq_per_class.json");
    rep.summary_path = join_path(out_dir, "route_f_fix10class24_bf16_clean_iq_summary.json");
    rep.log_path = join_path(out_dir, "route_f_fix10class24_bf16_clean_iq_summary.log");

    rep.class_total.assign(rml24::kClassCount, 0);
    rep.class_correct.assign(rml24::kClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml24::kClassCount) *
                             rml24::kClassCount, 0);

    const cat::Contract contract = chain::contract_24();

    std::printf("IQ_CLEAN_IQ_24CLASS_BF16_FIX10_ENV LIBIIO_ROOT=%s LD_LIBRARY_PATH=%s\n",
                std::getenv("LIBIIO_ROOT") ? std::getenv("LIBIIO_ROOT") : "(unset)",
                std::getenv("LD_LIBRARY_PATH") ? std::getenv("LD_LIBRARY_PATH") : "(unset)");
    std::fflush(stdout);

    // ---- load the clean frozen D2 sidecar + the 24-class BF16 baseline ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    const std::map<std::uint64_t, rml24bf16::BaselineRow> baseline =
        rml24bf16::load_baseline(rep.baseline_path, rml24::kClassCount);
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

    // ---- baseline identity check (SHA-identity proof): every holdout file must
    //      match a baseline row on source_index + original_sha256 + raw24_class +
    //      modulation + split_role.  Fail-closed on a missing/duplicate/mismatched row.
    {
        bool ok = true;
        std::string report;
        for (const auto& fz : holdout) {
            auto it = baseline.find(static_cast<std::uint64_t>(fz.source_index));
            if (it == baseline.end()) {
                ok = false;
                report += "missing:" + fz.file_name + ";";
            } else if (it->second.original_sha256 != fz.original_sha256 ||
                       it->second.raw24_class != fz.source_class ||
                       it->second.modulation != fz.modulation ||
                       it->second.split_role != fz.split_role) {
                ok = false;
                report += "mismatch:" + fz.file_name + ";";
            }
        }
        rep.baseline_identity_ok = ok;
        rep.baseline_identity_report = report;
    }

    std::printf("IQ_CLEAN_IQ_24CLASS_BF16_FIX10 BOARD_REQUIRED input_kind=%s "
                "frozen_dir=%s frozen_files=%llu holdout_files=%llu baseline_rows=%llu "
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
            throw std::runtime_error("fix10class24-clean: cannot open " + rep.results_path);
        results << "file_name\tsource_index\traw24_class\tmodulation\tsnr_db\t"
                << "split_role\tvalid\traw24_pred\tbaseline_pred\tcorrect\t"
                << "prediction_agreement\trepeat_deterministic\twindow_corr\t"
                << "window_nmse\tdelay_offset\tverdict\n";

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;

            std::printf("IQ_CLEAN_IQ_24CLASS_BF16_FIX10 file=%s input_kind=%s "
                        "source_index=%lld source_class=%d modulation=%s "
                        "complex_count=%llu split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(),
                        static_cast<long long>(fz.source_index), fz.source_class,
                        fz.modulation.c_str(),
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

            std::printf("IQ_CLEAN_IQ_24CLASS_BF16_FIX10_D2_RESTORE file=%s "
                        "source_index=%lld dc_i=%.9f dc_q=%.9f rec_scale=%.9f\n",
                        fz.file_name.c_str(), static_cast<long long>(fz.source_index),
                        fz.original_dc_i, fz.original_dc_q, fz.d2_rec_scale);
            std::fflush(stdout);

            const std::vector<float> ref =
                iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                               fz.recovered_tensor_sha256);
            const iqdloop::ClassificationWindow cw =
                iqdloop::select_classification_window(recovered_stream, ref);
            std::printf("IQ_CLEAN_IQ_24CLASS_BF16_FIX10_WINDOW file=%s "
                        "recovered_frames=%llu delay_offset=%d corr=%.6f nmse=%.6f "
                        "gain_db=%.3f sha_equal=%d\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(cw.recovered_frames),
                        cw.delay_offset, cw.tensor_corr, cw.tensor_nmse,
                        cw.tensor_gain_db, cw.sha_equal ? 1 : 0);
            std::fflush(stdout);

            if (!cw.valid || cw.aligned_tensor.empty()) {
                ++rep.excluded;
                ++rep.exclude_reasons["CLEAN_NO_VALID_WINDOW"];
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.modulation << "\t"
                        << fz.snr_db << "\t" << fz.split_role
                        << "\t0\t-1\t-1\t-1\t-1\t-1\t"
                        << cw.tensor_corr << "\t" << cw.tensor_nmse << "\t"
                        << cw.delay_offset << "\tCLEAN_NO_VALID_WINDOW\n";
                continue;
            }

            // ---- classify the ONE reference-aligned window (raw-24, NO merge) ----
            const auto t0 = Clock::now();
            std::vector<float> raw24;
            npu.infer(cw.aligned_tensor.data(), raw24);
            const double classify_us = elapsed_us(t0);
            timing.record(m22::StageId::NpuInfer, classify_us);

            // Repeat-determinism (§8 gate field): a second inference on the SAME
            // aligned tensor must produce the same raw24 argmax.  The re-arm
            // discipline runs exactly one Device::reset(1) before this second frame.
            std::vector<float> raw24b;
            const auto t1 = Clock::now();
            npu.infer(cw.aligned_tensor.data(), raw24b);
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

            const bool correct = finite && (raw_top == fz.source_class);

            // ---- rf_pred vs the FROZEN offline baseline raw24 prediction
            //      (MEASUREMENT; read by stable key source_index, never row number).
            //      A missing key fails the agreement (fail-closed) but never gates a
            //      PASS here.
            int baseline_pred = -1;
            bool baseline_pred_found = false;
            {
                const auto bit = baseline.find(static_cast<std::uint64_t>(fz.source_index));
                if (bit != baseline.end()) {
                    baseline_pred = bit->second.frozen_bf16_raw24_pred;
                    baseline_pred_found = true;
                }
            }
            const bool prediction_agreement =
                finite && baseline_pred_found && (raw_top == baseline_pred);
            const bool label_correct = correct;
            if (prediction_agreement) ++rep.prediction_agreement_count;
            std::printf("IQ_CLEAN_IQ_24CLASS_BF16_FIX10_CLASSIFY file=%s "
                        "baseline_pred=%d rf_pred=%d source_label=%d "
                        "prediction_agreement=%d label_correct=%d "
                        "repeat_deterministic=%d finite=%d\n",
                        fz.file_name.c_str(), baseline_pred, raw_top, fz.source_class,
                        prediction_agreement ? 1 : 0, label_correct ? 1 : 0,
                        repeat_det ? 1 : 0, finite ? 1 : 0);
            std::fflush(stdout);

            ++global_frame_id;
            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;
            r.source = "iq_clean_iq_24class_bf16_fix10";
            r.mock = false;
            chain::fill_result_rml24(r, raw24, contract, rep.model_sha,
                                     std::numeric_limits<double>::quiet_NaN());
            r.classify_us = classify_us;
            r.e2e_us = classify_us + classify2_us;
            on_frame(r);

            ++rep.scored;
            ++rep.total_valid;
            if (correct) ++rep.total_correct;
            if (finite && raw_top >= 0 && raw_top < rml24::kClassCount) {
                ++rep.confusion[static_cast<std::size_t>(fz.source_class) *
                                    rml24::kClassCount + raw_top];
            }
            ++rep.class_total[static_cast<std::size_t>(fz.source_class)];
            if (correct) ++rep.class_correct[static_cast<std::size_t>(fz.source_class)];
            if (fz.source_class == rml24::kAmSsbWc) {
                ++rep.wc_total;
                if (correct) ++rep.wc_correct;
            } else if (fz.source_class == rml24::kAmSsbSc) {
                ++rep.sc_total;
                if (correct) ++rep.sc_correct;
            }

            results << fz.file_name << "\t" << fz.source_index << "\t"
                    << fz.source_class << "\t" << fz.modulation << "\t"
                    << fz.snr_db << "\t" << fz.split_role << "\t"
                    << (finite ? 1 : 0) << "\t" << raw_top << "\t" << baseline_pred
                    << "\t" << (correct ? 1 : 0) << "\t"
                    << (prediction_agreement ? 1 : 0) << "\t"
                    << (repeat_det ? 1 : 0) << "\t"
                    << cw.tensor_corr << "\t" << cw.tensor_nmse << "\t"
                    << cw.delay_offset << "\tCLEAN_DIGITAL_SCORED\n";

            std::printf("IQ_CLEAN_IQ_24CLASS_BF16_FIX10 file=%s frames=1 correct=%d "
                        "source=%d raw24_pred=%d repeat_det=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.source_class,
                        raw_top, repeat_det ? 1 : 0);
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
        for (int c = 0; c < rml24::kClassCount; ++c) {
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

    // Confusion CSV.
    {
        std::ofstream f(rep.confusion_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.confusion_path);
        f << "true\\pred";
        for (int c = 0; c < rml24::kClassCount; ++c)
            f << "," << rml24::kLabelOrder24[c];
        f << "\n";
        for (int t = 0; t < rml24::kClassCount; ++t) {
            f << rml24::kLabelOrder24[t];
            for (int p = 0; p < rml24::kClassCount; ++p)
                f << "," << rep.confusion[static_cast<std::size_t>(t) *
                                              rml24::kClassCount + p];
            f << "\n";
        }
    }

    // Per-class JSON.
    {
        std::ofstream f(rep.per_class_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.per_class_path);
        f << "[\n";
        for (int c = 0; c < rml24::kClassCount; ++c) {
            const std::uint64_t tot = rep.class_total[static_cast<std::size_t>(c)];
            const std::uint64_t corr = rep.class_correct[static_cast<std::size_t>(c)];
            const double acc = tot > 0 ? static_cast<double>(corr) /
                                         static_cast<double>(tot) : 0.0;
            f << (c == 0 ? "  " : " ,") << "{\"index\":" << c
              << ",\"name\":\"" << rml24::kLabelOrder24[c] << "\""
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
        f << "  \"token\":\"" << measurement_token << "\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"model_domain_token\":\"" << kCleanModelDomainNotProven << "\",\n";
        f << "  \"deployment_mode\":\"" << rml24::kDeploymentMode << "\",\n";
        f << "  \"model_mode\":\"" << rml24::kModelMode << "\",\n";
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
        f << "  \"label_accuracy\":" << rep.label_accuracy << ",\n";
        f << "  \"macro_accuracy\":" << rep.macro_accuracy << ",\n";
        f << "  \"wc_total\":" << rep.wc_total << ",\n";
        f << "  \"wc_correct\":" << rep.wc_correct << ",\n";
        f << "  \"sc_total\":" << rep.sc_total << ",\n";
        f << "  \"sc_correct\":" << rep.sc_correct << ",\n";
        f << "  \"nan_or_inf\":" << rep.nan_or_inf << ",\n";
        f << "  \"repeat_deterministic\":" << rep.repeat_deterministic << ",\n";
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
        f << "token=" << measurement_token
          << " measurement=" << measurement_token
          << " model_domain=" << kCleanModelDomainNotProven
          << " holdout=" << rep.holdout_files
          << " scored=" << rep.scored
          << " excluded=" << rep.excluded
          << " prediction_agreement=" << rep.prediction_agreement
          << " label_accuracy=" << rep.label_accuracy
          << " macro_accuracy=" << rep.macro_accuracy
          << " wc_correct=" << rep.wc_correct << "/" << rep.wc_total
          << " sc_correct=" << rep.sc_correct << "/" << rep.sc_total
          << " nan_or_inf=" << rep.nan_or_inf
          << " repeat_deterministic=" << rep.repeat_deterministic
          << "\n";
    }

    std::printf("ROUTE_F_FIX10CLASS24_BF16_CLEAN_IQ token=%s measurement=%s "
                "model_domain=%s scored=%llu excluded=%llu "
                "prediction_agreement=%.6f label_accuracy=%.6f macro_accuracy=%.6f "
                "wc=%llu/%llu sc=%llu/%llu nan_or_inf=%llu "
                "repeat_deterministic=%llu/%llu\n",
                measurement_token.c_str(), measurement_token.c_str(),
                kCleanModelDomainNotProven,
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.excluded),
                rep.prediction_agreement, rep.label_accuracy, rep.macro_accuracy,
                static_cast<unsigned long long>(rep.wc_correct),
                static_cast<unsigned long long>(rep.wc_total),
                static_cast<unsigned long long>(rep.sc_correct),
                static_cast<unsigned long long>(rep.sc_total),
                static_cast<unsigned long long>(rep.nan_or_inf),
                static_cast<unsigned long long>(rep.repeat_deterministic),
                static_cast<unsigned long long>(rep.scored));
    std::fflush(stdout);

    const bool infra_ok = rep.error.empty() && rep.baseline_identity_ok;
    rep.functional_pass = infra_ok && (rep.scored > 0);

    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " baseline_rows=" + std::to_string(rep.baseline_rows) +
                         " baseline_identity_ok=" + (rep.baseline_identity_ok ? "1" : "0") +
                         " scored=" + std::to_string(rep.scored) +
                         " excluded=" + std::to_string(rep.excluded) +
                         " prediction_agreement=" +
                         std::to_string(rep.prediction_agreement) +
                         " label_accuracy=" + std::to_string(rep.label_accuracy) +
                         " macro_accuracy=" + std::to_string(rep.macro_accuracy) +
                         " wc=" + std::to_string(rep.wc_correct) + "/" +
                         std::to_string(rep.wc_total) +
                         " sc=" + std::to_string(rep.sc_correct) + "/" +
                         std::to_string(rep.sc_total) +
                         " nan_or_inf=" + std::to_string(rep.nan_or_inf) +
                         " repeat_deterministic=" +
                         std::to_string(rep.repeat_deterministic);
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    rep.detail = detail;

    return rep;
}

}  // namespace iqclean24bf16fix10
