#pragma once

// iq_dual_sdr_23class_fix10.hpp -- fix10 Path A/C: the D2 PHYSICAL-RF closed loop
// over TWO independent Plutos (TX device -> coax/RF -> RX device), with PER-FILE
// training-frame recovery that applies the differential COARSE CFO BEFORE the fine
// timing/CFO estimate.
//
// WHY this runner exists (the fix10 distinction): iq_rf_sync_recovery.hpp records
// `coarse_cfo_hz` (the differential Zadoff-Chu CFO, unambiguous over +/-fs/2 ==
// +/-1.28 MHz) but deliberately does NOT apply it -- same-Pluto fix9r2 has ~0 CFO.
// Two free-running Plutos carry a kHz-scale carrier offset (each LO is locked to its
// own reference crystal), which the FINE CFO (unambiguous over +/-fs/(2*kTailStart)
// ~ +/-21.7 Hz) cannot measure without aliasing.  This runner therefore:
//
//   1. estimate(rx)          -> finds the preamble + records coarse_cfo_hz
//   2. de-rotate the WHOLE capture by exp(-j 2*pi*coarse_cfo_hz*n/fs)
//   3. estimate(de-rotated)  -> the FINE cfo_hz is now only the small residual
//   4. rec.payload_tx_scale = tr.tx_scale; apply(de-rotated, rec)
//
// The recovery math itself (iq_rf_sync_recovery.hpp) is RED-LINE and untouched; this
// header only sequences its estimate()/apply() around the coarse pre-rotation.
//
// Two devices are opened by --tx-uri / --rx-uri.  Every per-file device write is
// role-split and self-restored inside transfer_one_file_dual_sdr_fix10 (N1/N2); this
// runner only additionally sets + restores the sample rate on both devices (the one
// runner-level write, which the transfer's per-file guard deliberately does not own).
// No top-level DeviceStateGuard is used: save_params()/restore_params() keep a SINGLE
// saved-state slot, so a top-level guard would be clobbered by the transfer's internal
// per-file guard (nested-guard conflict) -- the sample rate is restored explicitly.
//
// Outputs (measurement, never a regression PASS): per-file recovery + dual-SDR
// prediction + the fix10 dual-SDR tokens (measurement / RF fidelity / model-domain
// NOT_PROVEN).  A dual-SDR run never promotes ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS
// -- that token belongs to the single-SDR Route F gate alone.
//
// iCraft-free and libiio-free: it compiles identically on the host (FakeTxDevice /
// FakeRxDevice over a shared FakeRfLink) and the board (two real Plutos).

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_training_frame.hpp"
#include "iq_rf_sync_recovery.hpp"
#include "iq_dual_sdr_coarse_cfo_recovery.hpp"
#include "iq_rf_fix9r2b_diagnostic.hpp"
#include "iq_dual_sdr_transfer_fix10.hpp"
#include "iq_rf_fix9r_baseline.hpp"
#include "rml23_merged.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <sys/stat.h>

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqdual23fix10 {

using Clock = std::chrono::steady_clock;

// ---- the fix10 dual-SDR tokens (measurement, never a regression PASS) -------
constexpr const char* kMeasurementComplete = "ROUTE_F_FIX10_DUAL_SDR_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete = "ROUTE_F_FIX10_DUAL_SDR_MEASUREMENT_INCOMPLETE";
constexpr const char* kRfFidelityPass = "ROUTE_F_FIX10_DUAL_SDR_RF_FIDELITY_PASS";
constexpr const char* kRfFidelityFail = "ROUTE_F_FIX10_DUAL_SDR_RF_FIDELITY_FAIL";
constexpr const char* kModelDomainNotProven = "ROUTE_F_FIX10_DUAL_SDR_MODEL_DOMAIN_NOT_PROVEN";

// ---- acceptance-gate thresholds (mirror the single-SDR Route F gate) --------
constexpr double kFidelityTrainingCorrMin = 0.9;      // preamble peak corr
constexpr double kAgreementMin = 0.90;                // measured, not gated here
constexpr double kAccuracyDeltaPpMax = 5.0;
constexpr double kDefaultBaselineAccuracy = 0.9934;   // 906/912, original-data model acc

// ---- local merge + argmax (mirrors iqrfloop23fix9r) -------------------------
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

// ---- typed estimator failure -> RF fidelity verdict (mirrors iqrfloop23fix9r) --
inline const char* failure_rf_verdict(iqrfrec::Failure f) {
    switch (f) {
        case iqrfrec::Failure::NONE: return "RF_PRESERVES_IQ";
        case iqrfrec::Failure::CAPTURE_TOO_SHORT:
        case iqrfrec::Failure::TRAINING_NOT_FOUND:
        case iqrfrec::Failure::TRAINING_PEAK_AMBIGUOUS:
            return "RF_TRAINING_ESTIMATE_FAILED";
        case iqrfrec::Failure::TRAINING_CORRELATION_TOO_LOW:
        case iqrfrec::Failure::TRAINING_RESIDUAL_TOO_HIGH:
        case iqrfrec::Failure::PAYLOAD_TRAINING_NOT_FOUND:
        case iqrfrec::Failure::PAYLOAD_TRAINING_CORRELATION_TOO_LOW:
        case iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH:
        case iqrfrec::Failure::CFO_OUT_OF_RANGE:
        case iqrfrec::Failure::SRO_OUT_OF_RANGE:
            return "RF_DISTORTS_IQ";
        default:
            return "RF_TRAINING_ESTIMATE_FAILED";
    }
}

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

inline bool opt_flag(int argc, char** argv, const char* name) {
    for (int i = 1; i < argc; ++i)
        if (std::string(argv[i]) == name) return true;
    return false;
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
// Rf23Fix10DualSdrRunReport
// ---------------------------------------------------------------------------
struct Rf23Fix10DualSdrRunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::string model_sha;
    std::string baseline_path;
    std::string tx_uri;
    std::string rx_uri;
    std::uint64_t frozen_files = 0;
    std::uint64_t calib_files = 0;
    std::uint64_t holdout_files = 0;

    bool device_not_found = false;
    bool tx_device_not_found = false;
    bool rx_device_not_found = false;
    std::string error;

    long long requested_rate = 0;
    long long tx_rate = 0;
    long long rx_rate = 0;
    double tx_rate_err_hz = 0.0;
    double rx_rate_err_hz = 0.0;
    bool sample_rate_ok = false;
    double tx_atten_requested = 0.0;
    double tx_atten_readback = 0.0;
    bool restore_ok = false;
    std::string restore_report;

    // baseline pairing (identity check + frozen prediction reference)
    std::uint64_t baseline_rows = 0;
    bool baseline_identity_ok = false;
    std::string baseline_identity_report;

    // per-file recovery summary
    std::uint64_t training_estimates = 0;      // valid count
    std::uint64_t training_measured = 0;       // preamble-found count (corr meaningful)
    double training_corr_min = 0.0;
    double training_corr_avg = 0.0;
    double training_residual_max = 0.0;
    double training_residual_avg = 0.0;
    double coarse_cfo_max_abs_hz = 0.0;        // fix10: largest |coarse CFO| applied

    // scoring (holdout only)
    std::uint64_t scored = 0;
    std::uint64_t rf_excluded = 0;
    std::uint64_t total_valid = 0;
    std::uint64_t total_correct = 0;
    std::vector<std::uint64_t> class_total;
    std::vector<std::uint64_t> class_correct;
    std::vector<std::uint64_t> confusion;
    std::uint64_t ask4_total = 0;
    std::uint64_t ask4_correct = 0;
    std::map<std::string, std::uint64_t> rf_exclude_reasons;
    bool any_tx_clip = false;
    bool any_rx_clip = false;

    // rf_pred == frozen_baseline_pred count (MEASUREMENT -- never a PASS gate here).
    std::uint64_t prediction_agreement_count = 0;

    // acceptance gate
    double baseline_accuracy = kDefaultBaselineAccuracy;
    double prediction_agreement = 0.0;
    double rf_accuracy = 0.0;
    double accuracy_delta_pp = 0.0;
    bool full_run = false;
    bool rf_fidelity_pass = false;

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
// run_iq_dual_sdr_23class_fix10
// ---------------------------------------------------------------------------
inline Rf23Fix10DualSdrRunReport run_iq_dual_sdr_23class_fix10(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    Rf23Fix10DualSdrRunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-dual-sdr-23class-fix10 requires "
                                 "--frozen-dir=<D2 artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.baseline_path = board::get_opt(argc, argv, "--baseline", "");
    if (rep.baseline_path.empty())
        throw std::runtime_error("iq-dual-sdr-23class-fix10 requires "
                                 "--baseline=<route_f_fix9r_exact_baseline.tsv>");
    rep.baseline_accuracy = board::opt_d(argc, argv, "--baseline-accuracy",
                                         kDefaultBaselineAccuracy);
    rep.tx_uri = board::get_opt(argc, argv, "--tx-uri", "");
    rep.rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rep.tx_uri.empty())
        throw std::runtime_error("iq-dual-sdr-23class-fix10 requires --tx-uri=<TX device>");
    if (rep.rx_uri.empty())
        throw std::runtime_error("iq-dual-sdr-23class-fix10 requires --rx-uri=<RX device>");
    if (rep.tx_uri == rep.rx_uri)
        throw std::runtime_error(
            "iq-dual-sdr-23class-fix10: --tx-uri and --rx-uri must name TWO distinct "
            "devices (a single-SDR self-echo cannot stand in for a dual-SDR path).");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 30.0);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten",
                                         pluto::kSafeTxCeilingDb);
    const double target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin",
                       iqdual_run_fix10::kFix10DelayMarginDefault));
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex",
                       iqrfloop_run::kRfNoiseComplexDefault));
    const std::uint64_t max_files = board::opt_u64(argc, argv, "--max-files", 0);
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    const bool smoke = opt_flag(argc, argv, "--smoke");
    const std::string out_dir = board::get_opt(argc, argv, "--out-dir", "");

    // RF safety: explicit 50-ohm direct cable + never raise TX atten above -40 dB.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-dual-sdr-23class-fix10 requires --rf-path=direct-cable (50-ohm SMA "
            "coax, no antenna, no amplifier).  Got '" + rf_path + "' -- refusing to "
            "emit on the RF port.");
    if (tx_atten > pluto::kSafeTxCeilingDb)
        throw std::runtime_error(
            "iq-dual-sdr-23class-fix10: --tx-atten must be <= -40 dB (never raised).");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-dual-sdr-23class-fix10 requires --input-kind=radioml-d2-2p56m (got '" +
            rep.input_kind + "').");

    // Task G: auto-create --out-dir (fail-closed on a real mkdir error).
    if (!out_dir.empty() && ::mkdir(out_dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("fix10: cannot create --out-dir " + out_dir +
                                 ": " + std::strerror(errno));

    rep.results_path = join_path(out_dir, "route_f_fix10_dual_sdr_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_f_fix10_dual_sdr_confusion_23.csv");
    rep.per_class_path = join_path(out_dir, "route_f_fix10_dual_sdr_per_class.json");
    rep.summary_path = join_path(out_dir, "route_f_fix10_dual_sdr_summary.json");
    rep.log_path = join_path(out_dir, "route_f_fix10_dual_sdr_summary.log");

    rep.class_total.assign(rml23::kDeployedClassCount, 0);
    rep.class_correct.assign(rml23::kDeployedClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml23::kDeployedClassCount) *
                             rml23::kDeployedClassCount, 0);

    const cat::Contract contract = chain::contract_23();

    std::printf("IQ_DUAL_SDR_23CLASS_FIX10_ENV LIBIIO_ROOT=%s LD_LIBRARY_PATH=%s\n",
                std::getenv("LIBIIO_ROOT") ? std::getenv("LIBIIO_ROOT") : "(unset)",
                std::getenv("LD_LIBRARY_PATH") ? std::getenv("LD_LIBRARY_PATH") : "(unset)");
    std::fflush(stdout);

    // ---- load frozen D2 sidecar + the exact baseline ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    const std::map<std::uint64_t, iqrffix9r::BaselineRow> baseline =
        iqrffix9r::load_baseline(rep.baseline_path, rml23::kDeployedClassCount);
    rep.baseline_rows = static_cast<std::uint64_t>(baseline.size());

    const std::set<int> smoke_classes{1, 3, 4, 12};
    if (!file_filter.empty()) {
        std::vector<iqdloop::FrozenIq> kept;
        for (const auto& fz : frozen)
            if (fz.file_name.find(file_filter) != std::string::npos)
                kept.push_back(fz);
        frozen = std::move(kept);
    }
    if (smoke) {
        std::vector<iqdloop::FrozenIq> kept;
        for (const auto& fz : frozen)
            if (smoke_classes.count(fz.deployed_class)) kept.push_back(fz);
        frozen = std::move(kept);
    }

    std::vector<iqdloop::FrozenIq> calib, holdout;
    for (const auto& fz : frozen)
        (fz.is_calibration ? calib : holdout).push_back(fz);
    if (max_files > 0 && max_files < holdout.size())
        holdout.resize(static_cast<std::size_t>(max_files));
    if (frozen.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: no D2 files after "
                                 "file-filter/smoke selection");

    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    rep.calib_files = static_cast<std::uint64_t>(calib.size());
    rep.holdout_files = static_cast<std::uint64_t>(holdout.size());
    rep.full_run = (rep.holdout_files == rep.baseline_rows);

    // ---- baseline identity check (fail-closed: every holdout file must match a
    //      baseline row on source_index + sha + deployed_class + split_role) ----
    {
        bool ok = true;
        std::string report;
        for (const auto& fz : holdout) {
            auto it = baseline.find(static_cast<std::uint64_t>(fz.source_index));
            if (it == baseline.end()) {
                ok = false;
                report += "missing:" + fz.file_name + ";";
            } else if (it->second.sha256 != fz.sha256 ||
                       it->second.deployed_class != fz.deployed_class ||
                       it->second.split_role != "holdout") {
                ok = false;
                report += "mismatch:" + fz.file_name + ";";
            }
        }
        rep.baseline_identity_ok = ok;
        rep.baseline_identity_report = report;
    }

    std::printf("IQ_DUAL_SDR_23CLASS_FIX10 BOARD_REQUIRED input_kind=%s frozen_dir=%s "
                "frozen_files=%llu calib_files=%llu holdout_files=%llu baseline_rows=%llu "
                "baseline_identity_ok=%d full_run=%d tx_uri=%s rx_uri=%s rf_path=%s "
                "tx_atten=%.3f rx_gain=%.3f rf_tx_target_rms=%.3f out_dir=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<unsigned long long>(rep.calib_files),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.baseline_rows),
                rep.baseline_identity_ok ? 1 : 0, rep.full_run ? 1 : 0,
                rep.tx_uri.c_str(), rep.rx_uri.c_str(),
                rf_path.c_str(), tx_atten, gain_db, target_rms,
                out_dir.empty() ? "." : out_dir.c_str());
    std::fflush(stdout);

    // ---- open TWO devices (device-not-found is exit code 2, not a throw) ----
    std::unique_ptr<pluto::Device> tx_dev;
    std::unique_ptr<pluto::Device> rx_dev;
    try {
        tx_dev.reset(pluto::make_device(rep.tx_uri));
    } catch (const std::exception& e) {
        rep.tx_device_not_found = true;
        rep.device_not_found = true;
        rep.error = std::string("tx:") + e.what();
        return rep;
    }
    try {
        rx_dev.reset(pluto::make_device(rep.rx_uri));
    } catch (const std::exception& e) {
        rx_dev.reset();  // release rx before returning (TX already open -> leave it)
        rep.rx_device_not_found = true;
        rep.device_not_found = true;
        rep.error = std::string("rx:") + e.what();
        return rep;
    }

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    // Snapshot the ORIGINAL sample rates (the only runner-level write; the transfer's
    // per-file guard owns every other parameter and restores them per file).
    const long long orig_tx_rate = tx_dev->get_tx_sample_rate();
    const long long orig_rx_rate = rx_dev->get_rx_sample_rate();

    bool all_transfer_restore_ok = true;
    bool sample_rate_restored = false;

    std::ofstream results;
    try {
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            tx_dev->set_sample_rate(requested);
            rx_dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.tx_rate = tx_dev->get_tx_sample_rate();
        rep.rx_rate = rx_dev->get_rx_sample_rate();
        rep.tx_rate_err_hz = static_cast<double>(rep.tx_rate - requested);
        rep.rx_rate_err_hz = static_cast<double>(rep.rx_rate - requested);
        // Per-role read-back: the TX device must hold its TX rate, the RX device its
        // RX rate -- each within +/-5 Hz of 2.56 MHz (a per-device hardware sanity
        // bound; the INTER-device SRO/CFO is a physical quantity the recovery handles).
        const bool tx_ok = std::llabs(rep.tx_rate - requested) <= 5;
        const bool rx_ok = std::llabs(rep.rx_rate - requested) <= 5;
        rep.sample_rate_ok = tx_ok && rx_ok;
        if (!rep.sample_rate_ok) {
            rep.error = "sample_rate_mismatch: requested=" + std::to_string(requested) +
                        " tx=" + std::to_string(rep.tx_rate) +
                        " rx=" + std::to_string(rep.rx_rate) +
                        " (abs(actual-requested) must be <= 5 Hz per role)";
            tx_dev->set_sample_rate(orig_tx_rate);
            rx_dev->set_sample_rate(orig_rx_rate);
            sample_rate_restored = true;
            return rep;
        }

        const pluto::DataFormatInfo rx_fmt = rx_dev->rx_data_format();
        const pluto::DataFormatInfo tx_fmt = tx_dev->tx_data_format();
        std::printf("IQ_DUAL_SDR_FORMAT dir=tx %s\n",
                    pluto::describe_data_format(tx_fmt).c_str());
        std::printf("IQ_DUAL_SDR_FORMAT dir=rx %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);

        const int rx_pos_rail = iqdloop_sync::rail_positive(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));
        const int rx_neg_rail = iqdloop_sync::rail_negative(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));

        std::uint64_t global_frame_id = 0;
        std::vector<iqrffix9r2b::PerFileOutcome> file_outcomes;

        // ---- per-file: dual-SDR transfer -> coarse-CFO recovery -> fidelity gate ->
        //      classify.  Returns the RF verdict string and leaves `rec` filled.
        const auto process_file = [&](const iqdloop::FrozenIq& fz,
                                      iqrfrec::PerFileRecovery& rec,
                                      std::string& rf_verdict,
                                      bool& rx_clipped,
                                      bool& tx_clipped,
                                      std::vector<std::complex<double>>& rx,
                                      double& coarse_cfo_hz) {
            std::printf("IQ_DUAL_SDR_FIX10 file=%s input_kind=%s source_index=%lld "
                        "source_class=%d deployed_class=%d modulation=%s "
                        "frozen_complex=%llu split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(),
                        static_cast<long long>(fz.source_index), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        fz.split_role.c_str());
            std::fflush(stdout);

            const iqdual_run_fix10::DualSdrTransferResult tr =
                iqdual_run_fix10::transfer_one_file_dual_sdr_fix10(
                    *tx_dev, *rx_dev, fz.path, fz.complex_count, fz.sha256, center_hz,
                    gain_db, tx_atten, delay_margin, noise_complex, &timing, target_rms);

            rep.tx_atten_requested = tr.tx_atten_requested_db;
            rep.tx_atten_readback = tr.tx_atten_readback_db;
            if (!(tr.tx_restore_ok && tr.rx_restore_ok)) all_transfer_restore_ok = false;

            std::printf("IQ_DUAL_SDR_FIX10_TX_LEVEL file=%s native_rms=%.3f "
                        "target_rms=%.3f scale=%.6f peak_pre=%.0f peak_post=%.0f "
                        "clip_pre=%d clip_post=%d sha_pre=%s sha_post=%s burst_sha=%s "
                        "dma_sha=%s ok=%d\n",
                        fz.file_name.c_str(), tr.tx_native_rms, tr.tx_target_rms,
                        tr.tx_scale, tr.tx_peak_pre, tr.tx_peak_post,
                        tr.tx_clip_pre ? 1 : 0, tr.tx_clip_post ? 1 : 0,
                        tr.tx_sha_pre.c_str(), tr.tx_sha_post.c_str(),
                        tr.burst_sha.c_str(), tr.tx_dma_payload_sha.c_str(),
                        tr.tx_dma_payload_ok ? 1 : 0);
            std::fflush(stdout);

            std::printf("IQ_DUAL_SDR_FIX10_PROVENANCE file=%s frame_verify=%d "
                        "training_exact=%d payload_exact=%d layout=%d push_ok=%d "
                        "tx_loopback=%d rx_loopback=%d tx_atten_readback=%.3f "
                        "tx_restore=%d rx_restore=%d\n",
                        fz.file_name.c_str(), tr.frame_verify.ok ? 1 : 0,
                        tr.frame_verify.training_exact_match ? 1 : 0,
                        tr.frame_verify.payload_exact_match ? 1 : 0,
                        tr.frame_verify.frame_layout_match ? 1 : 0,
                        tr.tx_push.ok ? 1 : 0, tr.tx_loopback_readback,
                        tr.rx_loopback_readback, tr.tx_atten_readback_db,
                        tr.tx_restore_ok ? 1 : 0, tr.rx_restore_ok ? 1 : 0);
            std::fflush(stdout);

            std::printf("IQ_DUAL_SDR_FIX10_NEGATIVE_CONTROL file=%s "
                        "warmup_refills=%zu windows=%zu rms_min=%.4f rms_median=%.4f "
                        "rms_max=%.4f stability_ratio=%.4f retry=%d noise_stable=%d "
                        "tx_stopped_readback=%d\n",
                        fz.file_name.c_str(), tr.warmup_refills,
                        tr.noise_window_rms.size(), tr.noise_rms_min,
                        tr.noise_rms_median, tr.noise_rms_max,
                        tr.noise_stability_ratio, tr.retry,
                        tr.noise_stable ? 1 : 0, tr.tx_stopped_readback ? 1 : 0);
            std::fflush(stdout);

            std::printf("IQ_DUAL_SDR_FIX10_RX_GAIN_MODE file=%s mode_before_capture=%s "
                        "gain_before_capture=%.3f mode_after_capture=%s "
                        "gain_after_capture=%.3f\n",
                        fz.file_name.c_str(), tr.rx_gain_mode_before_capture.c_str(),
                        tr.rx_gain_before_capture, tr.rx_gain_mode_after_capture.c_str(),
                        tr.rx_gain_after_capture);
            std::fflush(stdout);

            if (board::g_stop_requested || tr.st.interrupted) {
                rf_verdict = "INSUFFICIENT_EVIDENCE";
                return;
            }
            if (!tr.capture_ok) {
                rf_verdict = "INSUFFICIENT_EVIDENCE";
                return;
            }

            tx_clipped = tr.tx_clip_pre || tr.tx_clip_post;
            rx = iqrftrain::deinterleave(tr.rx);

            // fix10: coarse-CFO-before-fine-timing recovery (the dual-SDR distinction).
            iqrfrec::EstimateConfig rec_cfg;
            rec_cfg.min_corr = kFidelityTrainingCorrMin;
            rec_cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;
            rec_cfg.max_cfo_hz = 30.0;
            rec_cfg.max_sro_ppm = 30.0;
            rec_cfg.search_limit = 0;   // full capture
            const CoarseCfoRecovery cfo = recover_payload_with_coarse_cfo(
                rx, rec_cfg, tr.tx_scale);
            rec = cfo.rec;
            coarse_cfo_hz = cfo.coarse_cfo_hz;

            rx_clipped = false;
            for (std::size_t k = 0; k + 1 < tr.rx.size(); k += 2) {
                const int i = tr.rx[k];
                const int q = tr.rx[k + 1];
                if (i >= rx_pos_rail || i <= rx_neg_rail ||
                    q >= rx_pos_rail || q <= rx_neg_rail) {
                    rx_clipped = true;
                    break;
                }
            }
            bool noise_clipped = false;
            for (std::size_t k = 0; k + 1 < tr.noise.size(); k += 2) {
                const int i = tr.noise[k];
                const int q = tr.noise[k + 1];
                if (i >= rx_pos_rail || i <= rx_neg_rail ||
                    q >= rx_pos_rail || q <= rx_neg_rail) {
                    noise_clipped = true;
                    break;
                }
            }

            // ---- fold infra gates in BEFORE the pure fidelity verdict ----
            if (tr.tx_loopback_readback != 0 || tr.rx_loopback_readback != 0) {
                rf_verdict = "RF_PATH_NOT_PROVEN";
            } else if (!tr.tx_dma_payload_ok) {
                rf_verdict = "RF_TX_DMA_PAYLOAD_MISMATCH";
            } else if (!tr.tx_stopped_readback) {
                rf_verdict = "RF_NEGATIVE_CONTROL_FAIL";
            } else if (!tr.noise_capture_ok || noise_clipped) {
                rf_verdict = "RF_NEGATIVE_CONTROL_FAIL";
            } else if (!tr.noise_stable) {
                rf_verdict = "RF_NEGATIVE_CONTROL_UNSTABLE";
            } else if (tr.tx_clip_pre || tr.tx_clip_post) {
                rf_verdict = "RF_TX_CLIPPED";
            } else if (rx_clipped) {
                rf_verdict = "RF_RX_CLIPPED";
            } else if (!rec.valid) {
                rf_verdict = failure_rf_verdict(rec.failure);
            } else {
                rf_verdict = "RF_PRESERVES_IQ";
            }

            std::printf("IQ_DUAL_SDR_FIX10_RECOVERY file=%s computed=%d valid=%d "
                        "failure=%s timing=%zu coarse_cfo_hz=%.3f "
                        "gain_mag=%.6f phase_deg=%.3f cfo_hz=%.3f sro_ppm=%.3f "
                        "phase_drift_deg=%.3f training_corr=%.6f training_residual=%.6f "
                        "payload_gain_mag=%.6f payload_phase_deg=%.3f "
                        "payload_training_corr=%.6f payload_training_residual=%.6f "
                        "fidelity=%s rx_clipped=%d\n",
                        fz.file_name.c_str(), rec.computed ? 1 : 0, rec.valid ? 1 : 0,
                        iqrfrec::failure_token(rec.failure), rec.timing_offset,
                        coarse_cfo_hz, rec.gain_mag, rec.phase_deg, rec.cfo_hz,
                        rec.sro_ppm, rec.phase_drift_deg, rec.training_corr,
                        rec.training_residual, rec.payload_gain_mag, rec.payload_phase_deg,
                        rec.payload_training_corr, rec.payload_training_residual,
                        rf_verdict.c_str(), rx_clipped ? 1 : 0);
            std::fflush(stdout);
        };

        // ---- single pass over holdout (per-file dual-SDR recovery) ----
        results.open(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("fix10: cannot open " + rep.results_path);
        results << "file_name\tsource_index\traw24_class\tdeployed23_class\t"
                << "modulation\tsnr_db\tsplit_role\tvalid\traw24_pred\t"
                << "merged23_pred\tcorrect\ttraining_corr\ttraining_residual\t"
                << "timing_offset\tgain_mag\tphase_deg\tcfo_hz\tsro_ppm\t"
                << "phase_drift_deg\tcoarse_cfo_hz\trf_verdict\n";

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;
            iqrfrec::PerFileRecovery rec;
            std::string rf_verdict;
            bool rx_clipped = false;
            bool tx_clipped = false;
            std::vector<std::complex<double>> rx;
            double coarse_cfo_hz = 0.0;
            process_file(fz, rec, rf_verdict, rx_clipped, tx_clipped, rx, coarse_cfo_hz);

            if (tx_clipped) rep.any_tx_clip = true;
            if (rx_clipped) rep.any_rx_clip = true;
            if (std::fabs(coarse_cfo_hz) > rep.coarse_cfo_max_abs_hz)
                rep.coarse_cfo_max_abs_hz = std::fabs(coarse_cfo_hz);

            {
                iqrffix9r2b::PerFileOutcome o;
                o.computed = rec.computed;
                o.valid = rec.valid;
                o.failure = rec.failure;
                o.training_corr = rec.training_corr;
                o.training_residual = rec.training_residual;
                file_outcomes.push_back(o);
            }

            const std::vector<std::complex<double>> payload =
                rec.valid ? iqrfrec::apply(rx, rec)
                          : std::vector<std::complex<double>>();

            const bool gate_ok = (rf_verdict == "RF_PRESERVES_IQ");
            if (!gate_ok) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons[rf_verdict];
                std::printf("IQ_DUAL_SDR_FIX10 file=%s classification=SKIPPED "
                            "reason=fidelity_gate fidelity=%s\n",
                            fz.file_name.c_str(), rf_verdict.c_str());
                std::fflush(stdout);
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << rec.training_corr << "\t" << rec.training_residual << "\t"
                        << (rec.valid ? static_cast<long long>(rec.timing_offset) : -1)
                        << "\t" << rec.gain_mag << "\t" << rec.phase_deg << "\t"
                        << rec.cfo_hz << "\t" << rec.sro_ppm << "\t"
                        << rec.phase_drift_deg << "\t" << coarse_cfo_hz << "\t"
                        << rf_verdict << "\n";
                continue;
            }

            // ---- chain -> D2 restore (payload already recovered above) ----
            std::vector<std::int16_t> payload_iq(payload.size() * 2);
            for (std::size_t k = 0; k < payload.size(); ++k) {
                const double I = std::lround(payload[k].real());
                const double Q = std::lround(payload[k].imag());
                payload_iq[k * 2 + 0] = static_cast<std::int16_t>(
                    std::max(-32768.0, std::min(32767.0, I)));
                payload_iq[k * 2 + 1] = static_cast<std::int16_t>(
                    std::max(-32768.0, std::min(32767.0, Q)));
            }

            chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, 1.0f);
            {
                m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                chain.push_int16(payload_iq.data(), payload.size());
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

            std::printf("IQ_DUAL_SDR_FIX10_D2_RESTORE file=%s source_index=%lld "
                        "dc_i=%.9f dc_q=%.9f rec_scale=%.9f per_file_recovery_used=1 "
                        "global_gain_used=0 coarse_cfo_used=1\n",
                        fz.file_name.c_str(), static_cast<long long>(fz.source_index),
                        fz.original_dc_i, fz.original_dc_q, fz.d2_rec_scale);
            std::fflush(stdout);

            const std::vector<float> ref =
                iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                               fz.recovered_tensor_sha256);
            const iqdloop::ClassificationWindow cw =
                iqdloop::select_classification_window(recovered_stream, ref);
            std::printf("IQ_DUAL_SDR_FIX10_WINDOW file=%s recovered_frames=%llu "
                        "delay_offset=%d corr=%.6f nmse=%.6f gain_db=%.3f sha_equal=%d\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(cw.recovered_frames),
                        cw.delay_offset, cw.tensor_corr, cw.tensor_nmse,
                        cw.tensor_gain_db, cw.sha_equal ? 1 : 0);
            std::fflush(stdout);

            if (!cw.valid || cw.aligned_tensor.empty()) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons["RF_NO_VALID_WINDOW"];
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << rec.training_corr << "\t" << rec.training_residual << "\t"
                        << static_cast<long long>(rec.timing_offset) << "\t"
                        << rec.gain_mag << "\t" << rec.phase_deg << "\t"
                        << rec.cfo_hz << "\t" << rec.sro_ppm << "\t"
                        << rec.phase_drift_deg << "\t" << coarse_cfo_hz
                        << "\tRF_NO_VALID_WINDOW\n";
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
            std::printf("IQ_DUAL_SDR_FIX10_CLASSIFY file=%s baseline_pred=%d rf_pred=%d "
                        "source_label=%d prediction_agreement=%d label_correct=%d\n",
                        fz.file_name.c_str(), baseline_pred, merged_top, fz.source_class,
                        prediction_agreement ? 1 : 0, label_correct ? 1 : 0);
            std::fflush(stdout);

            ++global_frame_id;
            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;
            r.source = "iq_dual_sdr_23class_fix10";
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
            if (fz.deployed_class == 1) {
                ++rep.ask4_total;
                if (correct) ++rep.ask4_correct;
            }

            results << fz.file_name << "\t" << fz.source_index << "\t"
                    << fz.source_class << "\t" << fz.deployed_class << "\t"
                    << fz.modulation << "\t" << fz.snr_db << "\t"
                    << fz.split_role << "\t1\t" << raw_top << "\t" << merged_top
                    << "\t" << (correct ? 1 : 0) << "\t"
                    << rec.training_corr << "\t" << rec.training_residual << "\t"
                    << static_cast<long long>(rec.timing_offset) << "\t"
                    << rec.gain_mag << "\t" << rec.phase_deg << "\t"
                    << rec.cfo_hz << "\t" << rec.sro_ppm << "\t"
                    << rec.phase_drift_deg << "\t" << coarse_cfo_hz << "\t"
                    << rf_verdict << "\n";

            std::printf("IQ_DUAL_SDR_FIX10 file=%s frames=1 correct=%d deployed=%d "
                        "source=%d raw24_pred=%d merged23_pred=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.deployed_class,
                        fz.source_class, raw_top, merged_top);
            std::fflush(stdout);
        }
        results.close();

        const iqrffix9r2b::TrainingSummary ts =
            iqrffix9r2b::aggregate_training_summary(file_outcomes);
        rep.training_estimates = ts.valid_count;
        rep.training_measured = ts.measured_count;
        rep.training_corr_min = ts.corr_min;
        rep.training_corr_avg = ts.corr_avg;
        rep.training_residual_max = ts.residual_max;
        rep.training_residual_avg = ts.residual_avg;

        // ---- restore the sample rate (the one runner-level write) ----
        tx_dev->set_sample_rate(orig_tx_rate);
        rx_dev->set_sample_rate(orig_rx_rate);
        sample_rate_restored = true;
    } catch (const std::exception& e) {
        rep.error = e.what();
        // best-effort sample-rate restore on the error path
        try {
            tx_dev->set_sample_rate(orig_tx_rate);
            rx_dev->set_sample_rate(orig_rx_rate);
            sample_rate_restored = true;
        } catch (...) {}
    }

    rep.restore_ok = all_transfer_restore_ok && sample_rate_restored;
    rep.restore_report = std::string(" all_transfer_restore_ok=") +
                         (all_transfer_restore_ok ? "1" : "0") +
                         " sample_rate_restore_ok=" + (sample_rate_restored ? "1" : "0");

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- acceptance gate: measurement + RF fidelity (NEVER a regression PASS) ----
    const double overall_acc = rep.total_valid > 0
        ? static_cast<double>(rep.total_correct) /
          static_cast<double>(rep.total_valid) : 0.0;
    rep.prediction_agreement = overall_acc;
    rep.rf_accuracy = overall_acc;
    rep.accuracy_delta_pp = 100.0 * (rep.rf_accuracy - rep.baseline_accuracy);

    const bool no_clip = !rep.any_tx_clip && !rep.any_rx_clip;
    rep.rf_fidelity_pass = rep.full_run && rep.baseline_identity_ok &&
                           (rep.scored == rep.holdout_files) &&
                           (rep.rf_excluded == 0) &&
                           (rep.training_estimates == rep.holdout_files) && no_clip;

    const std::string measurement_token = (rep.error.empty() && rep.sample_rate_ok)
                                              ? kMeasurementComplete
                                              : kMeasurementIncomplete;
    const std::string fidelity_token = rep.rf_fidelity_pass ? kRfFidelityPass : kRfFidelityFail;

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
        f << "  \"token\":\"" << measurement_token << "\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"rf_fidelity_token\":\"" << fidelity_token << "\",\n";
        f << "  \"model_domain_token\":\"" << kModelDomainNotProven << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"frozen_dir\":\"" << json_escape(rep.frozen_dir) << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"baseline_path\":\"" << json_escape(rep.baseline_path) << "\",\n";
        f << "  \"tx_uri\":\"" << json_escape(rep.tx_uri) << "\",\n";
        f << "  \"rx_uri\":\"" << json_escape(rep.rx_uri) << "\",\n";
        f << "  \"baseline_rows\":" << rep.baseline_rows << ",\n";
        f << "  \"baseline_accuracy\":" << rep.baseline_accuracy << ",\n";
        f << "  \"baseline_identity_ok\":" << (rep.baseline_identity_ok ? "true" : "false") << ",\n";
        f << "  \"full_run\":" << (rep.full_run ? "true" : "false") << ",\n";
        f << "  \"holdout_files\":" << rep.holdout_files << ",\n";
        f << "  \"training_estimates\":" << rep.training_estimates << ",\n";
        f << "  \"training_measured\":" << rep.training_measured << ",\n";
        f << "  \"training_corr_min\":" << rep.training_corr_min << ",\n";
        f << "  \"training_corr_avg\":" << rep.training_corr_avg << ",\n";
        f << "  \"training_residual_max\":" << rep.training_residual_max << ",\n";
        f << "  \"training_residual_avg\":" << rep.training_residual_avg << ",\n";
        f << "  \"coarse_cfo_max_abs_hz\":" << rep.coarse_cfo_max_abs_hz << ",\n";
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"rf_excluded\":" << rep.rf_excluded << ",\n";
        f << "  \"prediction_agreement\":" << rep.prediction_agreement << ",\n";
        f << "  \"rf_accuracy\":" << rep.rf_accuracy << ",\n";
        f << "  \"accuracy_delta_pp\":" << rep.accuracy_delta_pp << ",\n";
        f << "  \"overall_accuracy\":" << overall_acc << ",\n";
        f << "  \"macro_accuracy\":" << macro_acc << ",\n";
        f << "  \"any_tx_clip\":" << (rep.any_tx_clip ? "true" : "false") << ",\n";
        f << "  \"any_rx_clip\":" << (rep.any_rx_clip ? "true" : "false") << ",\n";
        f << "  \"rf_exclude_reasons\":{";
        bool first_reason = true;
        for (const auto& kv : rep.rf_exclude_reasons) {
            if (!first_reason) f << ",";
            f << "\"" << json_escape(kv.first) << "\":" << kv.second;
            first_reason = false;
        }
        f << "},\n";
        f << "  \"4ask\":{\"total\":" << rep.ask4_total
          << ",\"correct\":" << rep.ask4_correct << ",\"accuracy\":"
          << (rep.ask4_total > 0 ? static_cast<double>(rep.ask4_correct) /
                                   static_cast<double>(rep.ask4_total) : 0.0) << "},\n";
        f << "  \"sample_rate_ok\":" << (rep.sample_rate_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rate\":" << rep.requested_rate << ",\n";
        f << "  \"tx_rate\":" << rep.tx_rate << ",\n";
        f << "  \"rx_rate\":" << rep.rx_rate << ",\n";
        f << "  \"rf_path\":\"direct-cable\",\n";
        f << "  \"tx_atten_requested_db\":" << rep.tx_atten_requested << ",\n";
        f << "  \"tx_atten_readback_db\":" << rep.tx_atten_readback << ",\n";
        f << "  \"restore_ok\":" << (rep.restore_ok ? "true" : "false") << "\n";
        f << "}\n";
    }

    // Summary log.
    {
        std::ofstream f(rep.log_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.log_path);
        f << "token=" << measurement_token
          << " measurement=" << measurement_token
          << " rf_fidelity=" << fidelity_token
          << " model_domain=" << kModelDomainNotProven
          << " holdout=" << rep.holdout_files
          << " scored=" << rep.scored
          << " rf_excluded=" << rep.rf_excluded
          << " training_estimates=" << rep.training_estimates
          << " training_measured=" << rep.training_measured
          << " coarse_cfo_max_abs_hz=" << rep.coarse_cfo_max_abs_hz
          << " prediction_agreement=" << rep.prediction_agreement
          << " rf_accuracy=" << rep.rf_accuracy
          << " delta_pp=" << rep.accuracy_delta_pp
          << " 4ask=" << rep.ask4_correct << "/" << rep.ask4_total
          << " restore_ok=" << (rep.restore_ok ? 1 : 0)
          << "\n";
    }

    std::printf("ROUTE_F_FIX10_DUAL_SDR token=%s measurement=%s rf_fidelity=%s "
                "model_domain=%s scored=%llu rf_excluded=%llu training_estimates=%llu "
                "coarse_cfo_max_abs_hz=%.3f prediction_agreement=%.6f rf_accuracy=%.6f "
                "delta_pp=%.3f 4ask=%llu/%llu restore_ok=%d\n",
                measurement_token.c_str(), measurement_token.c_str(), fidelity_token.c_str(),
                kModelDomainNotProven,
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.rf_excluded),
                static_cast<unsigned long long>(rep.training_estimates),
                rep.coarse_cfo_max_abs_hz, rep.prediction_agreement, rep.rf_accuracy,
                rep.accuracy_delta_pp,
                static_cast<unsigned long long>(rep.ask4_correct),
                static_cast<unsigned long long>(rep.ask4_total),
                rep.restore_ok ? 1 : 0);
    std::fflush(stdout);

    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          !frozen.empty() && rep.baseline_identity_ok;
    rep.functional_pass = infra_ok && (rep.scored > 0);

    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " baseline_rows=" + std::to_string(rep.baseline_rows) +
                         " full_run=" + (rep.full_run ? "1" : "0") +
                         " scored=" + std::to_string(rep.scored) +
                         " rf_excluded=" + std::to_string(rep.rf_excluded) +
                         " prediction_agreement=" + std::to_string(rep.prediction_agreement) +
                         " rf_accuracy=" + std::to_string(rep.rf_accuracy) +
                         " delta_pp=" + std::to_string(rep.accuracy_delta_pp) +
                         " tx_uri=" + rep.tx_uri +
                         " rx_uri=" + rep.rx_uri +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " tx_rate=" + std::to_string(rep.tx_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " tx_atten_requested_db=" + std::to_string(rep.tx_atten_requested) +
                         " tx_atten_readback_db=" + std::to_string(rep.tx_atten_readback) +
                         " rf_path=direct-cable";
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

}  // namespace iqdual23fix10
