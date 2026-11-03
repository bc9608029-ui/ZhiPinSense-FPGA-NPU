#pragma once

// iq_rf_loopback_23class.hpp -- Stage H-F / Route F fix9: the D2 PHYSICAL-RF
// closed loop with a 23-class accuracy measurement.
//
// fix9 closes the loop the fix8 runner left open: instead of classifying the
// Route D reconstructed tensors, it TX's the Route D2 NON-TRAINING reconstruction
// (AC-only ci16, RMS ~= global K counts) out the Pluto TX, through a 50-ohm SMA
// coax, back into the Pluto RX, then RESTORES the original model-domain tensor
// from the received AC and classifies it with the ORIGINAL 24-class model
// (raw24 -> AM-SSB merge -> 23 deployed classes).  The output is a full 23-class
// accuracy + confusion matrix, not a PASS/FAIL gate.
//
// D2 restore math (build-time constants read from route_d2_rf_manifest.tsv, NEVER
// fitted per file):
//     chain(rec_scale=1.0)      -> decimate(iq / 2048)        == the AC, unit RMS
//     apply_global_gain(stream) -> undo the ONE global RF gain (calibration subset)
//     x d2_rec_scale + (dc_i+j*dc_q)  -> the original model-domain tensor
//     select_classification_window    -> the ONE reference-aligned 1024 window
//     infer                          -> raw24 -> merge23 -> 23-class argmax
//
// RF safety + fidelity gates are IDENTICAL to fix8 (loopback=0, --rf-path=
// direct-cable, TX atten -40 dB never raised, no antenna/amplifier).  Every
// scored sample must pass RF_PRESERVES_IQ (corr >= 0.9, SNR >= 6 dB,
// normalized_residual <= 0.05, TX/RX clip == 0, negative control stable, TX DMA
// payload correct, loopback read-back == 0).  A file that fails the fidelity gate
// is SKIPPED (reason recorded), never silently scored; if NO holdout file is
// scored the accuracy token is
// ROUTE_F_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY (never a valid accuracy).
//
// Task I (small D0 control) is documented, not executed: BPSK/QPSK/4ASK/16QAM are
// each sampled 2-5x by the D2 holdout subset; no full 23-class D0 dual-run.
//
// Task J (memory): the results TSV is written PER FILE (streaming), the per-file
// TX/RX/tensor buffers are released on each iteration, and only the fixed 23x23
// confusion matrix + 23 per-class counters are retained.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_loopback.hpp"
#include "iq_rf_loopback_report.hpp"
#include "iq_rf_loopback_transfer.hpp"
#include "rml23_merged.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqrfloop23 {

using Clock = std::chrono::steady_clock;

// Local merge + argmax (mirrors iqrfloop_run's copies; the board runner's own
// copies live in the anonymous namespace of board_gate9_full_chain_rml23.cpp).
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

// ---------------------------------------------------------------------------
// Rf23RunReport: the 23-class run report (memory-bounded -- NO per-file results
// retained; only the fixed 23x23 confusion matrix + 23 per-class counters).
// ---------------------------------------------------------------------------
struct Rf23RunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::string model_sha;
    std::uint64_t frozen_files = 0;
    std::uint64_t calib_files = 0;    // split_role == calibration
    std::uint64_t holdout_files = 0;  // split_role == holdout (after caps)

    bool device_not_found = false;
    std::string error;

    long long requested_rate = 0;
    long long rx_rate = 0;
    long long tx_rate = 0;
    double rate_err_hz = 0.0;
    double rate_err_ppm = 0.0;
    bool sample_rate_ok = false;
    double tx_atten_requested = 0.0;
    double tx_atten_readback = 0.0;
    bool restore_ok = false;
    std::string restore_report;

    // RF calibration (ONE global gain from the calibration subset only).
    bool have_global_gain = false;
    iqrfloop::RfGlobalGain global_gain;
    std::size_t calib_used = 0;

    // Scoring (holdout only).  A file that fails the fidelity gate is excluded
    // (rf_excluded) and its prediction is never counted.
    std::uint64_t scored = 0;         // holdout files classified
    std::uint64_t rf_excluded = 0;    // holdout files skipped by the fidelity gate
    std::uint64_t total_valid = 0;    // scored frames (== scored files, 1 window each)
    std::uint64_t total_correct = 0;
    std::vector<std::uint64_t> class_total;    // 23
    std::vector<std::uint64_t> class_correct;  // 23
    std::vector<std::uint64_t> confusion;      // 23*23 row-major (true x predicted)
    std::uint64_t ask4_total = 0;              // deployed index 1 == "4ASK"
    std::uint64_t ask4_correct = 0;
    std::map<std::string, std::uint64_t> rf_exclude_reasons;

    // Accuracy token (never a valid accuracy when RF fidelity blocked the run).
    bool accuracy_valid = false;

    // Output files (written under --out-dir, default cwd).
    std::string results_path;
    std::string confusion_path;
    std::string per_class_path;
    std::string summary_path;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// Minimal JSON string escape (labels/file names are ASCII-safe, but be defensive).
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

// Join an output directory and a flat filename (empty dir -> cwd/relative).
inline std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

// ---------------------------------------------------------------------------
// run_iq_rf_loopback_23class
// ---------------------------------------------------------------------------
inline Rf23RunReport run_iq_rf_loopback_23class(
    chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
    const std::function<void(const rf::ResultFrame&)>& on_frame) {
    Rf23RunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-rf-loopback-23class requires --frozen-dir=<D2 "
                                 "artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    // D2 operating point: rx_gain 30 dB, TX atten -40 dB, TX target RMS 2048
    // counts (the ci16 already carries RMS ~= global K == 2048, so this is a
    // no-op that VERIFIES the native RMS and records the full TX-level evidence).
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 30.0);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten",
                                         pluto::kSafeTxCeilingDb);
    const double target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", 16384));
    const std::uint64_t tx_complex_cap =
        board::opt_u64(argc, argv, "--tx-complex", 0);   // D2 needs the full waveform
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex",
                       iqrfloop_run::kRfNoiseComplexDefault));
    const std::uint64_t calib_cap =
        board::opt_u64(argc, argv, "--rf-calib-count", 0);  // 0 = all calibration files
    const std::uint64_t max_files =
        board::opt_u64(argc, argv, "--max-files", 0);       // 0 = all holdout files
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    const std::string out_dir = board::get_opt(argc, argv, "--out-dir", "");

    // RF safety: the external-RF path must be EXPLICITLY confirmed by the operator.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-rf-loopback-23class requires --rf-path=direct-cable (50-ohm SMA "
            "coax, no antenna, no amplifier).  Got '" + rf_path + "' -- refusing to "
            "emit on the RF port.");
    if (tx_atten > pluto::kSafeTxCeilingDb)
        throw std::runtime_error(
            "iq-rf-loopback-23class: --tx-atten must be <= -40 dB (never raised).");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-rf-loopback-23class requires --input-kind=radioml-d2-2p56m (got '" +
            rep.input_kind + "').");

    // ---- load frozen D2 sidecar (fail-closed: never re-generate) ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);

    if (!file_filter.empty()) {
        std::vector<iqdloop::FrozenIq> kept;
        for (const auto& fz : frozen)
            if (fz.file_name.find(file_filter) != std::string::npos)
                kept.push_back(fz);
        frozen = std::move(kept);
    }

    // Partition by the manifest's split_role (genuinely independent RF-gain
    // calibration subset vs holdout), then apply the two caps.
    std::vector<iqdloop::FrozenIq> calib, holdout;
    for (const auto& fz : frozen)
        (fz.is_calibration ? calib : holdout).push_back(fz);
    if (calib_cap > 0 && calib_cap < calib.size())
        calib.resize(static_cast<std::size_t>(calib_cap));
    if (max_files > 0 && max_files < holdout.size())
        holdout.resize(static_cast<std::size_t>(max_files));
    if (frozen.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: no D2 files after "
                                 "file-filter selection");

    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    rep.calib_files = static_cast<std::uint64_t>(calib.size());
    rep.holdout_files = static_cast<std::uint64_t>(holdout.size());

    rep.results_path = join_path(out_dir, "route_f_fix9_23class_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_f_fix9_confusion_23.csv");
    rep.per_class_path = join_path(out_dir, "route_f_fix9_per_class.json");
    rep.summary_path = join_path(out_dir, "route_f_fix9_summary.json");

    rep.class_total.assign(rml23::kDeployedClassCount, 0);
    rep.class_correct.assign(rml23::kDeployedClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml23::kDeployedClassCount) *
                             rml23::kDeployedClassCount, 0);

    const cat::Contract contract = chain::contract_23();

    std::printf("IQ_RF_LOOPBACK_23CLASS BOARD_REQUIRED input_kind=%s frozen_dir=%s "
                "frozen_files=%llu calib_files=%llu holdout_files=%llu rf_path=%s "
                "tx_atten=%.3f rx_gain=%.3f rf_tx_target_rms=%.3f out_dir=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<unsigned long long>(rep.calib_files),
                static_cast<unsigned long long>(rep.holdout_files),
                rf_path.c_str(), tx_atten, gain_db, target_rms,
                out_dir.empty() ? "." : out_dir.c_str());
    std::fflush(stdout);

    // ---- device open (device-not-found is exit code 2, not a throw) ----
    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        rep.device_not_found = true;
        rep.error = e.what();
        return rep;
    }

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    bool all_capture_ok = true;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate: force 2560000, fail-closed abs(actual-2560000) <= 5 Hz ----
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.tx_rate = dev->get_tx_sample_rate();
        rep.rate_err_hz = static_cast<double>(rep.rx_rate - requested);
        rep.rate_err_ppm = 1e6 * rep.rate_err_hz / static_cast<double>(requested);
        const bool rx_ok = std::llabs(rep.rx_rate - requested) <= 5;
        const bool tx_ok = std::llabs(rep.tx_rate - requested) <= 5;
        rep.sample_rate_ok = rx_ok && tx_ok;
        if (!rep.sample_rate_ok) {
            rep.error = "sample_rate_mismatch: requested=" + std::to_string(requested) +
                        " rx=" + std::to_string(rep.rx_rate) +
                        " tx=" + std::to_string(rep.tx_rate) +
                        " (abs(actual-requested) must be <= 5 Hz)";
            return rep;
        }

        // ---- audit the TX/RX channel data format (parity with fix8) ----
        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        const pluto::DataFormatInfo tx_fmt = dev->tx_data_format();
        std::printf("IQ_RF_LOOPBACK_FORMAT dir=tx %s\n",
                    pluto::describe_data_format(tx_fmt).c_str());
        std::printf("IQ_RF_LOOPBACK_FORMAT dir=rx %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);

        std::uint64_t global_frame_id = 0;
        std::vector<std::complex<double>> calib_gains;

        // ---- shared per-file processing: transfer + measure + verdict + evidence.
        // Returns the RF verdict; leaves pf filled (pf.rf.sync.aligned_rx is the
        // cyclically-aligned RX period the classification path consumes).  The
        // caller decides whether to collect a calibration gain or to classify. ----
        const auto process_file = [&](const iqdloop::FrozenIq& fz,
                                      iqrfloop_run::RfPerFileResult& pf) {
            pf.file_name = fz.file_name;
            pf.source_class = fz.source_class;
            pf.deployed_class = fz.deployed_class;

            std::printf("IQ_RF_LOOPBACK file=%s input_kind=%s source_class=%d "
                        "deployed_class=%d modulation=%s frozen_complex=%llu "
                        "split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        fz.split_role.c_str());
            std::fflush(stdout);

            const iqrfloop_run::RfTransferResult tr = iqrfloop_run::transfer_one_file_rf(
                *dev, fz.path, fz.complex_count, fz.sha256, center_hz, gain_db,
                tx_atten, delay_margin, tx_complex_cap, noise_complex, &timing,
                tx_fmt, rx_fmt, target_rms);

            pf.tx_complex = static_cast<std::uint64_t>(tr.tx.size() / 2);
            pf.tx_verify = tr.tx_verify;
            pf.refills = tr.refills;
            pf.tx_create_delta = tr.tx_create_delta;
            pf.tx_destroy_delta = tr.tx_destroy_delta;
            pf.rx_create_delta = tr.rx_create_delta;
            pf.rx_destroy_delta = tr.rx_destroy_delta;
            pf.capture_ok = tr.capture_ok;
            pf.rx_captured = static_cast<std::uint64_t>(tr.rx.size() / 2);
            pf.capture_detail = tr.cont.report();
            pf.tx_dma_payload_sha = tr.tx_dma_payload_sha;
            pf.tx_dma_payload_ok = tr.tx_dma_payload_ok;
            pf.loopback_readback = tr.loopback_readback;
            pf.tx_atten_requested_db = tr.tx_atten_requested_db;
            pf.tx_atten_readback_db = tr.tx_atten_readback_db;
            pf.noise_capture_ok = tr.noise_capture_ok;
            pf.tx_stopped_readback = tr.tx_stopped_readback;
            pf.noise_stable = tr.noise_stable;
            pf.noise_rms_median = tr.noise_rms_median;
            pf.noise_rms_min = tr.noise_rms_min;
            pf.noise_rms_max = tr.noise_rms_max;

            rep.tx_atten_requested = tr.tx_atten_requested_db;
            rep.tx_atten_readback = tr.tx_atten_readback_db;

            // fix9 Task D: TX-level evidence (native RMS/peak -> scale -> post peak,
            // scale ONLY if no clip; no silent saturation).
            std::printf("IQ_RF_LOOPBACK_TX_LEVEL file=%s native_rms=%.3f "
                        "target_rms=%.3f scale=%.6f peak_pre=%.0f peak_post=%.0f "
                        "clip_pre=%d clip_post=%d sha_pre=%s sha_post=%s dma_sha=%s "
                        "ok=%d\n",
                        fz.file_name.c_str(), tr.tx_native_rms, tr.tx_target_rms,
                        tr.tx_scale, tr.tx_peak_pre, tr.tx_peak_post,
                        tr.tx_clip_pre ? 1 : 0, tr.tx_clip_post ? 1 : 0,
                        tr.tx_sha_pre.c_str(), tr.tx_sha_post.c_str(),
                        tr.tx_dma_payload_sha.c_str(), tr.tx_dma_payload_ok ? 1 : 0);
            std::fflush(stdout);

            std::printf("IQ_RF_LOOPBACK_TX_VERIFY file=%s sha=%s nonzero=%llu "
                        "nonzero_rate=%.6f rms=%.3f first_i=%d first_q=%d "
                        "last_i=%d last_q=%d\n",
                        fz.file_name.c_str(), pf.tx_verify.sha256.c_str(),
                        static_cast<unsigned long long>(pf.tx_verify.nonzero),
                        pf.tx_verify.nonzero_rate, pf.tx_verify.rms,
                        pf.tx_verify.first_i, pf.tx_verify.first_q,
                        pf.tx_verify.last_i, pf.tx_verify.last_q);
            std::fflush(stdout);

            std::printf("IQ_RF_LOOPBACK_TX_DMA_PAYLOAD file=%s sha=%s ok=%d\n",
                        fz.file_name.c_str(), pf.tx_dma_payload_sha.c_str(),
                        pf.tx_dma_payload_ok ? 1 : 0);
            std::fflush(stdout);

            std::printf("IQ_RF_LOOPBACK_NEGATIVE_CONTROL file=%s capture_ok=%d "
                        "complex=%llu all_zero=%d\n",
                        fz.file_name.c_str(), tr.noise_capture_ok ? 1 : 0,
                        static_cast<unsigned long long>(tr.noise.size() / 2),
                        (tr.noise.empty() ||
                         std::all_of(tr.noise.begin(), tr.noise.end(),
                                     [](std::int16_t v) { return v == 0; })) ? 1 : 0);
            std::fflush(stdout);

            std::printf("IQ_RF_LOOPBACK_NEGATIVE_CONTROL_DISCARD file=%s "
                        "complex=%llu nonzero_rate=%.6f rms=%.3f "
                        "first_i=%d first_q=%d last_i=%d last_q=%d\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(tr.noise_discard.complex),
                        tr.noise_discard.nonzero_rate, tr.noise_discard.rms,
                        tr.noise_discard.first_i, tr.noise_discard.first_q,
                        tr.noise_discard.last_i, tr.noise_discard.last_q);
            std::fflush(stdout);
            for (std::size_t w = 0; w < tr.noise_window_rms.size(); ++w) {
                const board::Continuity& nc =
                    tr.noise_window_cont.size() > w ? tr.noise_window_cont[w]
                                                    : board::Continuity{};
                std::printf("IQ_RF_LOOPBACK_NEGATIVE_CONTROL_SAMPLE file=%s "
                            "idx=%zu complex=%llu rms=%.4f cont_ok=%d "
                            "single_refill=%d capacity=%llu\n",
                            fz.file_name.c_str(), w,
                            static_cast<unsigned long long>(tr.noise.size() / 2),
                            tr.noise_window_rms[w], nc.ok() ? 1 : 0,
                            nc.single_refill ? 1 : 0,
                            static_cast<unsigned long long>(nc.capacity));
                std::fflush(stdout);
            }
            // fix9 Task F: the warm-up/retry summary (>=3 discard refills + >=3
            // independent windows; stability == max/min <= 3).
            std::printf("IQ_RF_LOOPBACK_NEGATIVE_CONTROL_SUMMARY file=%s "
                        "warmup_refills=%zu windows=%zu rms_min=%.4f "
                        "rms_median=%.4f rms_max=%.4f stability_ratio=%.4f "
                        "retry=%d noise_stable=%d tx_stopped_readback=%d\n",
                        fz.file_name.c_str(), tr.warmup_refills,
                        tr.noise_window_rms.size(), tr.noise_rms_min,
                        tr.noise_rms_median, tr.noise_rms_max,
                        tr.noise_stability_ratio, tr.retry,
                        tr.noise_stable ? 1 : 0,
                        tr.tx_stopped_readback ? 1 : 0);
            std::fflush(stdout);

            for (const auto& rs : pf.refills) {
                std::printf("IQ_RF_LOOPBACK_REFILL file=%s kind=%s complex=%llu "
                            "nonzero_rate=%.6f rms=%.3f first_i=%d first_q=%d "
                            "last_i=%d last_q=%d\n",
                            fz.file_name.c_str(), rs.kind.c_str(),
                            static_cast<unsigned long long>(rs.complex),
                            rs.nonzero_rate, rs.rms, rs.first_i, rs.first_q,
                            rs.last_i, rs.last_q);
                std::fflush(stdout);
            }

            std::printf("IQ_RF_LOOPBACK_BUFFER file=%s tx_create=%llu tx_destroy=%llu "
                        "rx_create=%llu rx_destroy=%llu loopback=%d "
                        "tx_atten_requested_db=%.3f tx_atten_readback_db=%.3f "
                        "antenna=none coax=direct-cable ensm=not_managed_by_this_code\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(pf.tx_create_delta),
                        static_cast<unsigned long long>(pf.tx_destroy_delta),
                        static_cast<unsigned long long>(pf.rx_create_delta),
                        static_cast<unsigned long long>(pf.rx_destroy_delta),
                        pf.loopback_readback, pf.tx_atten_requested_db,
                        pf.tx_atten_readback_db);
            std::fflush(stdout);

            {
                const board::RxStats& st = tr.st;
                std::string& cd = pf.capture_detail;
                if (st.interrupted) cd += " interrupted=1";
                if (st.overflow) cd += " overflow=" + std::to_string(st.overflow);
                if (st.dropped) cd += " dropped=" + std::to_string(st.dropped);
                if (st.discontinuity) cd += " discontinuity=" + std::to_string(st.discontinuity);
                if (st.timeouts) cd += " timeouts=" + std::to_string(st.timeouts);
            }

            if (board::g_stop_requested || tr.st.interrupted) {
                pf.rf_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_RF_LOOPBACK file=%s interrupted\n", fz.file_name.c_str());
                std::fflush(stdout);
                return;
            }
            if (!pf.capture_ok) {
                pf.rf_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_RF_LOOPBACK file=%s capture=FAIL %s\n",
                            fz.file_name.c_str(), pf.capture_detail.c_str());
                std::fflush(stdout);
                return;
            }

            // ---- RF fidelity (full-period FFT circular sync + negative control) ----
            pf.rf = iqrfloop::measure_rf_fidelity(
                tr.tx, tr.rx, tr.noise, tr.noise_capture_ok, iqdloop::kFrozenFsIn,
                tx_fmt.bits == 0 || tx_fmt.bits > 16 ? 16 : static_cast<int>(tx_fmt.bits),
                rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits),
                iqdloop_sync::kTransientDiscardComplex);

            std::printf("IQ_RF_LOOPBACK_NOISE_FLOOR file=%s rms=%.4f peak=%d "
                        "dc=%.4f all_zero=%d clipped=%d negative_control_ok=%d\n",
                        fz.file_name.c_str(), pf.rf.noise_floor_rms, pf.rf.noise_peak,
                        pf.rf.noise_dc, pf.rf.noise_all_zero ? 1 : 0,
                        pf.rf.noise_clipped ? 1 : 0,
                        pf.rf.negative_control_ok ? 1 : 0);
            std::fflush(stdout);

            // Fold the infra gates in BEFORE the pure fidelity verdict, so an infra
            // fault can never read as RF_PRESERVES_IQ.
            if (pf.loopback_readback != 0) {
                pf.rf_verdict = iqrfloop::kRfPathNotProven;
            } else if (!pf.tx_dma_payload_ok) {
                pf.rf_verdict = "RF_TX_DMA_PAYLOAD_MISMATCH";
            } else if (!pf.tx_stopped_readback) {
                pf.rf_verdict = "RF_NEGATIVE_CONTROL_FAIL";
            } else if (!pf.rf.negative_control_ok) {
                pf.rf_verdict = "RF_NEGATIVE_CONTROL_FAIL";
            } else if (!pf.noise_stable) {
                pf.rf_verdict = "RF_NEGATIVE_CONTROL_UNSTABLE";
            } else if (tr.tx_clip_pre || tr.tx_clip_post) {
                // fix9 Task D: a TX that railed (pre or post scale) is refused.
                pf.rf_verdict = "RF_TX_CLIPPED";
            } else {
                pf.rf_verdict = iqrfloop::rf_fidelity_verdict(pf.rf);
            }

            std::printf("IQ_RF_LOOPBACK file=%s fidelity=%s linear_delay=%llu "
                        "circular_shift=%llu aligned_start=%llu compared_samples=%llu "
                        "peak_corr=%.6f gain_db=%.3f phase_deg=%.3f "
                        "normalized_residual=%.6f evm_pct=%.3f corr=%.6f "
                        "nmse_evm_consistent=%d rms_tx=%.3f rms_rx=%.3f "
                        "cfo_hz=%.3f phase_drift_deg=%.3f "
                        "tx_peak=%d tx_bits=%d tx_positive_rail=%d tx_negative_rail=%d "
                        "tx_clip_count=%llu tx_clipped=%d "
                        "rx_peak=%d rx_bits=%d rx_positive_rail=%d rx_negative_rail=%d "
                        "rx_clip_count=%llu rx_clipped=%d "
                        "capture_too_short=%d noise_floor_rms=%.4f "
                        "snr_db=%.3f noise_clipped=%d noise_capture_ok=%d\n",
                        fz.file_name.c_str(), pf.rf_verdict.c_str(),
                        static_cast<unsigned long long>(pf.rf.sync.sync.linear_delay),
                        static_cast<unsigned long long>(pf.rf.sync.sync.circular_shift),
                        static_cast<unsigned long long>(pf.rf.sync.sync.aligned_start),
                        static_cast<unsigned long long>(pf.rf.sync.sync.compared_samples),
                        pf.rf.sync.sync.peak_corr, pf.rf.sync.gain_db, pf.rf.sync.phase_deg,
                        pf.rf.sync.normalized_residual, pf.rf.sync.evm_pct, pf.rf.sync.corr,
                        pf.rf.sync.nmse_evm_consistent ? 1 : 0,
                        pf.rf.sync.rms_tx, pf.rf.sync.rms_rx, pf.rf.sync.cfo_hz,
                        pf.rf.sync.phase_drift_deg,
                        pf.rf.sync.tx_peak, pf.rf.sync.tx_bits,
                        pf.rf.sync.tx_positive_rail, pf.rf.sync.tx_negative_rail,
                        static_cast<unsigned long long>(pf.rf.sync.tx_clip_count),
                        pf.rf.sync.tx_clipped ? 1 : 0,
                        pf.rf.sync.rx_peak, pf.rf.sync.rx_bits,
                        pf.rf.sync.rx_positive_rail, pf.rf.sync.rx_negative_rail,
                        static_cast<unsigned long long>(pf.rf.sync.rx_clip_count),
                        pf.rf.sync.rx_clipped ? 1 : 0,
                        pf.rf.sync.capture_too_short ? 1 : 0,
                        pf.rf.noise_floor_rms, pf.rf.snr_db,
                        pf.rf.noise_clipped ? 1 : 0, pf.rf.noise_capture_ok ? 1 : 0);
            std::printf("IQ_RF_LOOPBACK_SYNC_ORIGIN file=%s sync_origin=%s "
                        "tx_autocorr_second=%.6f competing_peaks=%llu "
                        "equivalent_peaks=%llu unexplained_peaks=%llu\n",
                        fz.file_name.c_str(),
                        iqdloop_sync::sync_origin_name(pf.rf.sync.sync.origin),
                        pf.rf.sync.sync.tx_autocorr_second,
                        static_cast<unsigned long long>(pf.rf.sync.sync.competing_peaks),
                        static_cast<unsigned long long>(pf.rf.sync.sync.equivalent_peaks),
                        static_cast<unsigned long long>(pf.rf.sync.sync.unexplained_peaks));
            std::fflush(stdout);
        };

        // ---- pass 1: calibration subset (split_role == calibration, capped) ----
        for (const auto& fz : calib) {
            if (board::g_stop_requested) break;
            iqrfloop_run::RfPerFileResult pf;
            pf.is_calibration = true;
            process_file(fz, pf);
            if (!pf.capture_ok) all_capture_ok = false;
            if (iqrfloop::rf_fidelity_gate_ok(pf.rf_verdict.c_str())) {
                calib_gains.push_back(std::polar(pf.rf.sync.gain_count,
                                                 pf.rf.sync.phase_deg *
                                                     iqdloop_sync::kPi / 180.0));
            }
        }

        rep.global_gain = iqrfloop::estimate_global_gain(calib_gains);
        rep.have_global_gain = rep.global_gain.valid;
        rep.calib_used = rep.global_gain.count;
        std::printf("IQ_RF_LOOPBACK_CALIBRATION calib_files=%llu used=%zu valid=%d "
                    "mag=%.6f phase_deg=%.3f k_mag=%.6f k_phase_deg=%.3f\n",
                    static_cast<unsigned long long>(rep.calib_files), rep.calib_used,
                    rep.have_global_gain ? 1 : 0, rep.global_gain.mag,
                    rep.global_gain.phase_deg, rep.global_gain.k_mag,
                    rep.global_gain.k_phase_deg);
        std::fflush(stdout);

        // ---- pass 2: holdout subset (split_role == holdout, capped): restore +
        //      classify with the GLOBAL gain only, stream the TSV per file ----
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("iq-rf-loopback-23class: cannot open " +
                                     rep.results_path);
        results << "file_name\tsource_index\traw24_class\tdeployed23_class\t"
                << "modulation\tsnr_db\tsplit_role\tvalid\traw24_pred\t"
                << "merged23_pred\tcorrect\tcorr\tnormalized_residual\tsnr_db_rf\t"
                << "rf_verdict\n";

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;
            iqrfloop_run::RfPerFileResult pf;
            pf.is_calibration = false;
            process_file(fz, pf);

            if (!pf.capture_ok) all_capture_ok = false;

            // ---- fidelity gate: a failing file is SKIPPED (never silently scored) ----
            if (!iqrfloop::rf_fidelity_gate_ok(pf.rf_verdict.c_str())) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons[pf.rf_verdict];
                std::printf("IQ_RF_LOOPBACK file=%s classification=SKIPPED "
                            "reason=fidelity_gate fidelity=%s\n",
                            fz.file_name.c_str(), pf.rf_verdict.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << pf.rf.sync.corr << "\t"
                        << pf.rf.sync.normalized_residual << "\t"
                        << pf.rf.snr_db << "\t" << pf.rf_verdict << "\n";
                continue;
            }
            if (!rep.have_global_gain) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons["RF_AMPLITUDE_NOT_CALIBRATED"];
                std::printf("IQ_RF_LOOPBACK file=%s classification=SKIPPED "
                            "reason=no_global_calibration_gain\n", fz.file_name.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << pf.rf.sync.corr << "\t"
                        << pf.rf.sync.normalized_residual << "\t"
                        << pf.rf.snr_db << "\tRF_AMPLITUDE_NOT_CALIBRATED\n";
                continue;
            }

            // ---- D2 restore + classify (ONE window per file) ----
            const std::vector<std::int16_t>& win = pf.rf.sync.aligned_rx;
            const std::size_t win_complex = win.size() / 2;
            if (win_complex == 0) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons["RF_ALIGNED_WINDOW_EMPTY"];
                std::printf("IQ_RF_LOOPBACK file=%s aligned window empty\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << pf.rf.sync.corr << "\t"
                        << pf.rf.sync.normalized_residual << "\t"
                        << pf.rf.snr_db << "\tRF_ALIGNED_WINDOW_EMPTY\n";
                continue;
            }

            // rec_scale == 1.0 -> the chain emits decimate(iq / 2048) == the AC,
            // unit RMS.  The D2 restore then re-applies amplitude + DC.
            chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, 1.0f);
            {
                m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                chain.push_int16(win.data(), win_complex);
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
            // undo the ONE global RF gain (never a per-file fit), then restore DC.
            iqrfloop::apply_global_gain_to_stream(recovered_stream, chain::kFrameComplex,
                                                  rep.global_gain);
            iqdloop::apply_d2_restore_to_stream(recovered_stream, chain::kFrameComplex,
                                                fz.original_dc_i, fz.original_dc_q,
                                                fz.d2_rec_scale);

            // Task E evidence: the D2 restore is driven ONLY by build-time manifest
            // constants + the ONE global RF gain; no per-file fit, no label-based
            // params, no NPU-output tuning.
            std::printf("IQ_RF_LOOPBACK_D2_RESTORE file=%s source_index=%lld "
                        "dc_i=%.9f dc_q=%.9f rec_scale=%.9f manifest_sha_ok=1 "
                        "global_rf_gain_used=1 per_file_fit_used=0\n",
                        fz.file_name.c_str(),
                        static_cast<long long>(fz.source_index),
                        fz.original_dc_i, fz.original_dc_q, fz.d2_rec_scale);
            std::fflush(stdout);

            const std::vector<float> ref =
                iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                               fz.recovered_tensor_sha256);
            const iqdloop::ClassificationWindow cw =
                iqdloop::select_classification_window(recovered_stream, ref);
            std::printf("IQ_RF_LOOPBACK_WINDOW file=%s recovered_frames=%llu "
                        "delay_offset=%d corr=%.6f nmse=%.6f gain_db=%.3f "
                        "sha_equal=%d aligned_sha=%s ref_sha=%s\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(cw.recovered_frames),
                        cw.delay_offset, cw.tensor_corr, cw.tensor_nmse,
                        cw.tensor_gain_db, cw.sha_equal ? 1 : 0,
                        cw.aligned_sha256.c_str(), cw.ref_sha256.c_str());
            std::fflush(stdout);

            if (!cw.valid || cw.aligned_tensor.empty()) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons["RF_NO_VALID_WINDOW"];
                std::printf("IQ_RF_LOOPBACK file=%s classification=SKIPPED "
                            "reason=no_valid_window\n", fz.file_name.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << pf.rf.sync.corr << "\t"
                        << pf.rf.sync.normalized_residual << "\t"
                        << pf.rf.snr_db << "\tRF_NO_VALID_WINDOW\n";
                continue;
            }

            // ---- classify the ONE reference-aligned window ----
            const auto t0 = Clock::now();
            std::vector<float> raw24;
            npu.infer(cw.aligned_tensor.data(), raw24);
            const double classify_us = elapsed_us(t0);
            timing.record(m22::StageId::NpuInfer, classify_us);

            const std::vector<float> m23 = merge23(raw24);
            const int raw_top = argmax_of(raw24);
            const int merged_top = argmax_of(m23);
            const bool correct = (merged_top == fz.deployed_class);
            ++global_frame_id;

            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;   // 1024/128k = 8 ms/frame
            r.source = "iq_rf_loopback_23class";
            r.mock = false;
            chain::fill_result_rml23(r, raw24, m23, contract, rep.model_sha,
                                     std::numeric_limits<double>::quiet_NaN());
            r.classify_us = classify_us;
            r.e2e_us = classify_us;
            on_frame(r);

            // ---- update the fixed 23x23 matrix + per-class counters ----
            ++rep.scored;
            ++rep.total_valid;
            if (correct) ++rep.total_correct;
            ++rep.confusion[static_cast<std::size_t>(fz.deployed_class) *
                                rml23::kDeployedClassCount + merged_top];
            ++rep.class_total[static_cast<std::size_t>(fz.deployed_class)];
            if (correct) ++rep.class_correct[static_cast<std::size_t>(fz.deployed_class)];
            if (fz.deployed_class == 1) {   // "4ASK"
                ++rep.ask4_total;
                if (correct) ++rep.ask4_correct;
            }

            results << fz.file_name << "\t" << fz.source_index << "\t"
                    << fz.source_class << "\t" << fz.deployed_class << "\t"
                    << fz.modulation << "\t" << fz.snr_db << "\t"
                    << fz.split_role << "\t1\t" << raw_top << "\t" << merged_top
                    << "\t" << (correct ? 1 : 0) << "\t"
                    << pf.rf.sync.corr << "\t" << pf.rf.sync.normalized_residual
                    << "\t" << pf.rf.snr_db << "\t" << pf.rf_verdict << "\n";

            std::printf("IQ_RF_LOOPBACK file=%s frames=1 correct=%d deployed=%d "
                        "source=%d raw24_pred=%d merged23_pred=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.deployed_class,
                        fz.source_class, raw_top, merged_top);
            std::fflush(stdout);
        }
        results.close();

        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // Restore is idempotent; fold the post-restore read-back into the detail.
    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- accuracy token + the four output files ----
    rep.accuracy_valid = rep.have_global_gain && (rep.scored > 0);
    const double overall_acc = rep.total_valid > 0
        ? static_cast<double>(rep.total_correct) /
          static_cast<double>(rep.total_valid) : 0.0;
    double macro_acc = 0.0;
    {
        std::size_t seen = 0;
        for (int c = 0; c < rml23::kDeployedClassCount; ++c) {
            if (rep.class_total[static_cast<std::size_t>(c)] == 0) continue;
            ++seen;
            macro_acc += static_cast<double>(
                             rep.class_correct[static_cast<std::size_t>(c)]) /
                         static_cast<double>(rep.class_total[static_cast<std::size_t>(c)]);
        }
        if (seen > 0) macro_acc /= static_cast<double>(seen);
    }

    // Confusion CSV (rows = true, columns = predicted; header = deployed labels).
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

    // Per-class JSON (array of 23 objects).
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
        const std::string token = rep.accuracy_valid
            ? "ROUTE_F_23CLASS_ACCURACY_MEASURED"
            : "ROUTE_F_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY";
        f << "{\n";
        f << "  \"token\":\"" << token << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"frozen_dir\":\"" << json_escape(rep.frozen_dir) << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"frozen_files\":" << rep.frozen_files << ",\n";
        f << "  \"calib_files\":" << rep.calib_files << ",\n";
        f << "  \"holdout_files\":" << rep.holdout_files << ",\n";
        f << "  \"global_gain\":{\"valid\":" << (rep.have_global_gain ? "true" : "false")
          << ",\"used\":" << rep.calib_used
          << ",\"mag\":" << rep.global_gain.mag
          << ",\"phase_deg\":" << rep.global_gain.phase_deg
          << ",\"k_mag\":" << rep.global_gain.k_mag
          << ",\"k_phase_deg\":" << rep.global_gain.k_phase_deg << "},\n";
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"rf_excluded\":" << rep.rf_excluded << ",\n";
        f << "  \"rf_exclude_reasons\":{";
        bool first_reason = true;
        for (const auto& kv : rep.rf_exclude_reasons) {
            if (!first_reason) f << ",";
            f << "\"" << json_escape(kv.first) << "\":" << kv.second;
            first_reason = false;
        }
        f << "},\n";
        f << "  \"total_valid_frames\":" << rep.total_valid << ",\n";
        f << "  \"total_correct_frames\":" << rep.total_correct << ",\n";
        f << "  \"overall_accuracy\":" << overall_acc << ",\n";
        f << "  \"macro_accuracy\":" << macro_acc << ",\n";
        f << "  \"4ask\":{\"total\":" << rep.ask4_total
          << ",\"correct\":" << rep.ask4_correct << ",\"accuracy\":"
          << (rep.ask4_total > 0 ? static_cast<double>(rep.ask4_correct) /
                                   static_cast<double>(rep.ask4_total) : 0.0) << "},\n";
        f << "  \"sample_rate_ok\":" << (rep.sample_rate_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rate\":" << rep.requested_rate << ",\n";
        f << "  \"rx_rate\":" << rep.rx_rate << ",\n";
        f << "  \"tx_rate\":" << rep.tx_rate << ",\n";
        f << "  \"rf_path\":\"direct-cable\",\n";
        f << "  \"tx_atten_requested_db\":" << rep.tx_atten_requested << ",\n";
        f << "  \"tx_atten_readback_db\":" << rep.tx_atten_readback << "\n";
        f << "}\n";
    }

    const std::string token = rep.accuracy_valid
        ? "ROUTE_F_23CLASS_ACCURACY_MEASURED"
        : "ROUTE_F_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY";
    std::printf("ROUTE_F_23CLASS_ACCURACY token=%s scored=%llu "
                "rf_excluded=%llu valid_frames=%llu correct=%llu overall_acc=%.6f "
                "macro_acc=%.6f\n",
                token.c_str(),
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.rf_excluded),
                static_cast<unsigned long long>(rep.total_valid),
                static_cast<unsigned long long>(rep.total_correct),
                overall_acc, macro_acc);
    std::fflush(stdout);

    // ---- infrastructure + functional verdict ----
    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          !frozen.empty() && all_capture_ok;
    rep.functional_pass = infra_ok && rep.have_global_gain && (rep.scored > 0);

    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " calib_files=" + std::to_string(rep.calib_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " scored=" + std::to_string(rep.scored) +
                         " rf_excluded=" + std::to_string(rep.rf_excluded) +
                         " total_valid=" + std::to_string(rep.total_valid) +
                         " total_correct=" + std::to_string(rep.total_correct) +
                         " overall_acc=" + std::to_string(overall_acc) +
                         " macro_acc=" + std::to_string(macro_acc) +
                         " accuracy_token=" + token +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " tx_rate=" + std::to_string(rep.tx_rate) +
                         " tx_atten_requested_db=" + std::to_string(rep.tx_atten_requested) +
                         " tx_atten_readback_db=" + std::to_string(rep.tx_atten_readback) +
                         " rf_path=direct-cable";
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

}  // namespace iqrfloop23
