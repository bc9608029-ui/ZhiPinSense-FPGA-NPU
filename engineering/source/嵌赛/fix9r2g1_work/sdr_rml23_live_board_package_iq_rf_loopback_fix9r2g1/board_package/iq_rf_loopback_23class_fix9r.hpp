#pragma once

// iq_rf_loopback_23class_fix9r.hpp -- Route F fix9r: the D2 PHYSICAL-RF closed loop
// with PER-FILE training-frame recovery (fix9's ONE global complex gain replaced).
//
// fix9 board result: RF valid 46/46 but correct 5/46 (10.87%), 4ASK 0/2 -- the
// global complex phase (95.110 deg) was wrong for ~all files because the TX LO
// re-keys on every tx_start_cyclic, so each file's RF gain a_i = |a_i|*exp(j arg a_i)
// carries a random phase.  fix9r brackets each payload with the known Zadoff-Chu
// training frame (iq_rf_training_frame.hpp), recovers gain/phase/timing/CFO/SRO/
// phase-drift PER FILE from the preamble (iq_rf_per_frame_recovery.hpp, never the
// payload -- §7 leak ban), undoes them, then restores the model-domain tensor with
// ONLY build-time manifest constants (DC + rec_scale) and classifies with the
// original 24-class model (raw24 -> AM-SSB merge -> 23 deployed).  There is NO
// calibration pass and NO global gain: every holdout file is self-recovered.
//
// Outputs (measurement, never a PASS gate):
//   * route_f_fix9r_23class_results.tsv   -- per-file recovery + prediction
//   * route_f_fix9r_confusion_23.csv      -- 23x23 confusion matrix
//   * route_f_fix9r_per_class.json        -- 23 per-class accuracies
//   * route_f_fix9r_summary.json          -- the 4 tokens (measurement / RF fidelity
//                                            / model-domain recovery / regression)
//   * route_f_fix9r_summary.log           -- one-line human-readable summary
//
// Acceptance gate (Task F): the regression token is ROUTE_F_23CLASS_ACCURACY_
// REGRESSION_PASS only when the FULL 46-sample holdout run is identity-matched to
// route_f_fix9r_exact_baseline.tsv AND rf_valid==46/46 AND rf_excluded==0 AND
// prediction_agreement>=0.90 AND rf_accuracy>=baseline-5pp AND 4ASK not degraded
// AND 46/46 training estimates AND no TX/RX clip AND parameter-restore PASS.
// Otherwise ROUTE_F_23CLASS_ACCURACY_REGRESSION_FAIL (never a valid regression).

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_per_frame_recovery.hpp"
#include "iq_rf_loopback_transfer_fix9r.hpp"
#include "iq_rf_fix9r_baseline.hpp"
#include "iq_rf_fix9r2a_diagnostic.hpp"
#include "iq_rf_fix9r2b_diagnostic.hpp"
#include "iq_rf_fix9r2d_diagnostic.hpp"
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

namespace iqrfloop23fix9r {

using Clock = std::chrono::steady_clock;

// ---- the four Route F fix9r tokens (Task E) -------------------------------
constexpr const char* kMeasurementComplete = "ROUTE_F_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete = "ROUTE_F_MEASUREMENT_INCOMPLETE";
constexpr const char* kRfFidelityPass = "ROUTE_F_RF_FIDELITY_PASS";
constexpr const char* kRfFidelityFail = "ROUTE_F_RF_FIDELITY_FAIL";
constexpr const char* kModelDomainNotProven = "ROUTE_F_MODEL_DOMAIN_RECOVERY_NOT_PROVEN";
constexpr const char* kRegressionPass = "ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS";
constexpr const char* kRegressionFail = "ROUTE_F_23CLASS_ACCURACY_REGRESSION_FAIL";

// fix9r2a Task C: the R8 2-sample diagnostic token (distinct from the 46-sample
// regression token -- a diagnostic can never carry the regression PASS).
constexpr const char* kDiagnosticPass = "ROUTE_F_FIX9R2_DIAGNOSTIC_PASS";
constexpr const char* kDiagnosticFail = "ROUTE_F_FIX9R2_DIAGNOSTIC_FAIL";

// ---- acceptance-gate thresholds (Task F) ----------------------------------
constexpr double kFidelityTrainingCorrMin = 0.9;      // preamble peak corr
constexpr double kAgreementMin = 0.90;
constexpr double kAccuracyDeltaPpMax = 5.0;           // rf_acc >= baseline - 5 pp
constexpr double kDefaultBaselineAccuracy = 0.9934;   // 906/912, original-data model acc

// Local merge + argmax (mirrors iqrfloop23's copies).
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

// Map a typed estimator failure to the Route F fidelity verdict string (fix9r2
// Task R6).  "no signal / bad peak / short capture" = the estimator could not find
// the training frame (RF_TRAINING_ESTIMATE_FAILED); "found but too weak / too much
// residual / CFO or SRO out of range" = the frame was present but the RF path
// distorted it (RF_DISTORTS_IQ).  NONE == RF_PRESERVES_IQ.
inline const char* failure_rf_verdict(iqrfrec::Failure f) {
    switch (f) {
        case iqrfrec::Failure::NONE:
            return "RF_PRESERVES_IQ";
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

// Bare-boolean flag presence (board::get_opt throws on a valueless flag, so a bare
// --smoke needs its own scan).
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
// Rf23Fix9rRunReport
// ---------------------------------------------------------------------------
struct Rf23Fix9rRunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::string model_sha;
    std::string baseline_path;
    std::uint64_t frozen_files = 0;
    std::uint64_t calib_files = 0;
    std::uint64_t holdout_files = 0;

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

    // baseline pairing (Task B identity check)
    std::uint64_t baseline_rows = 0;
    bool baseline_identity_ok = false;
    std::string baseline_identity_report;

    // per-file recovery summary
    std::uint64_t training_estimates = 0;
    // fix9r2b §6: count of files where the PREAMBLE WAS FOUND (corr/residual are
    // meaningful) -- distinct from training_estimates (valid) so a run failing only
    // on residual still reports its true corr/residual.
    std::uint64_t training_measured = 0;
    double training_corr_min = 0.0;
    double training_corr_avg = 0.0;
    double training_residual_max = 0.0;
    double training_residual_avg = 0.0;

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

    // fix9r2a Task B/C/D: R8 2-sample diagnostic (selection + per-sample record +
    // acceptance gate).  Calibration is never dropped; the selector matches the
    // manifest `modulation` column over the HOLD-ONLY subset.
    bool diagnostic_mode = false;
    std::string diagnostic_classes;                 // raw --diagnostic-classes string
    std::uint64_t diagnostic_per_class = 1;
    std::uint64_t diagnostic_requested_count = 0;   // classes.size() * per_class
    std::string diagnostic_selected_classes;        // comma-joined, in request order
    std::uint64_t estimate_computed = 0;            // rec.computed count (all holdout)
    std::uint64_t diag_frame_layout_match = 0;
    std::uint64_t diag_training_exact_match = 0;
    std::uint64_t diag_settling_guard_exact_zero = 0;    // fix9r2g
    std::uint64_t diag_payload_training_exact_match = 0; // fix9r2g
    std::uint64_t diag_payload_exact_match = 0;
    std::uint64_t diag_tx_push_ok = 0;
    std::uint64_t tx_clip_count = 0;
    std::uint64_t rx_clip_count = 0;
    std::vector<std::string> diag_lines;            // R8 per-sample lines (flush later)
    bool diagnostic_pass = false;
    std::string diagnostic_report;

    // fix9r2g: payload-domain training-block + R8 classification audit
    // (DIAGNOSTIC-ONLY, never deploy runtime, never from expected-payload estimation).
    double payload_training_residual_max = 0.0;     // migrated residual<=0.10 gate
    double payload_scale_error_max = 0.0;           // R8-only scale-error audit (<= 0.05)
    std::uint64_t r8_prediction_agreement = 0;      // rf_pred == frozen_baseline_pred count
    std::uint64_t r8_label_correct = 0;             // rf_pred == deployed_class count (print only)

    // fix9r2b §2/§5: waveform manifest + provisional metrics (DIAGNOSTIC_ONLY).
    std::string waveform_manifest_path;
    // fix9r2d: enriched per-capture metadata manifest (DIAGNOSTIC_ONLY).
    std::string capture_manifest_path;
    std::uint64_t provisional_payload_measured = 0;
    double provisional_payload_corr_min = 0.0;
    double provisional_payload_corr_avg = 0.0;
    double provisional_payload_nmse_max = 0.0;
    double provisional_payload_nmse_avg = 0.0;

    // acceptance gate (Task F)
    double baseline_accuracy = kDefaultBaselineAccuracy;
    double prediction_agreement = 0.0;
    double rf_accuracy = 0.0;
    double accuracy_delta_pp = 0.0;
    bool full_run = false;
    bool rf_fidelity_pass = false;
    bool model_domain_recovered = false;
    bool regression_pass = false;

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
// run_iq_rf_loopback_23class_fix9r
// ---------------------------------------------------------------------------
inline Rf23Fix9rRunReport run_iq_rf_loopback_23class_fix9r(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    Rf23Fix9rRunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-rf-loopback-23class-fix9r requires "
                                 "--frozen-dir=<D2 artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.baseline_path = board::get_opt(argc, argv, "--baseline", "");
    if (rep.baseline_path.empty())
        throw std::runtime_error("iq-rf-loopback-23class-fix9r requires "
                                 "--baseline=<route_f_fix9r_exact_baseline.tsv>");
    rep.baseline_accuracy = board::opt_d(argc, argv, "--baseline-accuracy",
                                         kDefaultBaselineAccuracy);
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 30.0);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten",
                                         pluto::kSafeTxCeilingDb);
    const double target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin",
                       iqrfloop_run_fix9r::kFix9rDelayMarginDefault));
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex",
                       iqrfloop_run::kRfNoiseComplexDefault));
    const std::uint64_t max_files =
        board::opt_u64(argc, argv, "--max-files", 0);
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    const bool smoke = opt_flag(argc, argv, "--smoke");
    const std::string out_dir = board::get_opt(argc, argv, "--out-dir", "");

    // fix9r2a Task B: the R8 diagnostic selector matches the manifest `modulation`
    // column (not the file name), over the HOLD-ONLY subset, taking --diagnostic-
    // per-class files per named class.
    rep.diagnostic_classes = board::get_opt(argc, argv, "--diagnostic-classes", "");
    rep.diagnostic_per_class =
        board::opt_u64(argc, argv, "--diagnostic-per-class", 1);
    rep.diagnostic_mode = !rep.diagnostic_classes.empty();

    // RF safety: explicit 50-ohm direct cable + never raise TX atten above -40 dB.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-rf-loopback-23class-fix9r requires --rf-path=direct-cable (50-ohm SMA "
            "coax, no antenna, no amplifier).  Got '" + rf_path + "' -- refusing to "
            "emit on the RF port.");
    if (tx_atten > pluto::kSafeTxCeilingDb)
        throw std::runtime_error(
            "iq-rf-loopback-23class-fix9r: --tx-atten must be <= -40 dB (never raised).");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-rf-loopback-23class-fix9r requires --input-kind=radioml-d2-2p56m (got '" +
            rep.input_kind + "').");

    // fix9r2a Task B: --diagnostic-classes selects by MODULATION over holdout only;
    // it must not be combined with the number-guessing --max-files truncation, the
    // 4-class --smoke, or --file-filter (which matches file names, not classes) --
    // any combination would silently change the selected set.
    if (rep.diagnostic_mode) {
        if (max_files > 0)
            throw std::runtime_error(
                "iq-rf-loopback-23class-fix9r: --diagnostic-classes and --max-files are "
                "mutually exclusive (R8 uses --diagnostic-classes=BPSK,4ASK; R9 uses "
                "neither).");
        if (smoke)
            throw std::runtime_error(
                "iq-rf-loopback-23class-fix9r: --diagnostic-classes and --smoke are "
                "mutually exclusive.");
        if (!file_filter.empty())
            throw std::runtime_error(
                "iq-rf-loopback-23class-fix9r: --diagnostic-classes and --file-filter are "
                "mutually exclusive (--file-filter matches file names, not classes).");
    }

    // Task G: auto-create --out-dir (fail-closed on a real mkdir error).
    if (!out_dir.empty() && ::mkdir(out_dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("fix9r: cannot create --out-dir " + out_dir +
                                 ": " + std::strerror(errno));

    rep.results_path = join_path(out_dir, "route_f_fix9r_23class_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_f_fix9r_confusion_23.csv");
    rep.per_class_path = join_path(out_dir, "route_f_fix9r_per_class.json");
    rep.summary_path = join_path(out_dir, "route_f_fix9r_summary.json");
    rep.log_path = join_path(out_dir, "route_f_fix9r_summary.log");
    rep.waveform_manifest_path = join_path(out_dir, "route_f_fix9r2d_waveforms.tsv");
    rep.capture_manifest_path = join_path(out_dir, "route_f_fix9r2d_capture.tsv");

    rep.class_total.assign(rml23::kDeployedClassCount, 0);
    rep.class_correct.assign(rml23::kDeployedClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml23::kDeployedClassCount) *
                             rml23::kDeployedClassCount, 0);

    const cat::Contract contract = chain::contract_23();

    // Task G: print the libiio environment so the board operator can confirm the
    // persistent libiio 0.26 install is on the library path.
    std::printf("IQ_RF_LOOPBACK_23CLASS_FIX9R_ENV LIBIIO_ROOT=%s LD_LIBRARY_PATH=%s\n",
                std::getenv("LIBIIO_ROOT") ? std::getenv("LIBIIO_ROOT") : "(unset)",
                std::getenv("LD_LIBRARY_PATH") ? std::getenv("LD_LIBRARY_PATH") : "(unset)");
    std::fflush(stdout);

    // ---- load frozen D2 sidecar + the exact baseline ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    const std::map<std::uint64_t, iqrffix9r::BaselineRow> baseline =
        iqrffix9r::load_baseline(rep.baseline_path, rml23::kDeployedClassCount);
    rep.baseline_rows = static_cast<std::uint64_t>(baseline.size());

    // --smoke: run only the 4 smoke classes (BPSK/QPSK/4ASK/16QAM == deployed
    //   3/4/1/12) so a 4-class chain check can complete before the full 23-class run.
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

    // fix9r2a Task B: R8 diagnostic selection by MODULATION over the holdout subset
    // ONLY (calibration is preserved untouched).  Fail-closed if a named class is
    // absent or under-filled -- never guess file numbers.
    if (rep.diagnostic_mode) {
        std::vector<std::string> classes;
        {
            std::string cur;
            for (char c : rep.diagnostic_classes) {
                if (c == ',') {
                    if (!cur.empty()) classes.push_back(cur);
                    cur.clear();
                } else {
                    cur += c;
                }
            }
            if (!cur.empty()) classes.push_back(cur);
        }
        rep.diagnostic_requested_count =
            static_cast<std::uint64_t>(classes.size()) * rep.diagnostic_per_class;
        const iqrffix9r2a::DiagnosticSelection sel =
            iqrffix9r2a::select_diagnostic_holdout(
                holdout, classes, static_cast<std::size_t>(rep.diagnostic_per_class));
        if (!sel.ok)
            throw std::runtime_error(
                "DIAGNOSTIC_SELECTION_FAILED: " + sel.report + " (modulation matched "
                "from the manifest, over holdout only; calibration untouched)");
        std::vector<iqdloop::FrozenIq> selected;
        selected.reserve(sel.selected_index.size());
        for (std::size_t idx : sel.selected_index)
            selected.push_back(holdout[idx]);
        holdout = std::move(selected);
        rep.diagnostic_selected_classes = sel.selected_classes;
    } else if (max_files > 0 && max_files < holdout.size()) {
        holdout.resize(static_cast<std::size_t>(max_files));
    }
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
            } else if (it->second.sha256 != fz.original_sha256 ||
                       it->second.deployed_class != fz.deployed_class ||
                       it->second.split_role != "holdout") {
                ok = false;
                report += "mismatch:" + fz.file_name + ";";
            }
        }
        rep.baseline_identity_ok = ok;
        rep.baseline_identity_report = report;
    }

    std::printf("IQ_RF_LOOPBACK_23CLASS_FIX9R BOARD_REQUIRED input_kind=%s frozen_dir=%s "
                "frozen_files=%llu calib_files=%llu holdout_files=%llu baseline_rows=%llu "
                "baseline_identity_ok=%d full_run=%d diagnostic_mode=%d "
                "diagnostic_classes=%s rf_path=%s tx_atten=%.3f rx_gain=%.3f "
                "rf_tx_target_rms=%.3f out_dir=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<unsigned long long>(rep.calib_files),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.baseline_rows),
                rep.baseline_identity_ok ? 1 : 0, rep.full_run ? 1 : 0,
                rep.diagnostic_mode ? 1 : 0, rep.diagnostic_classes.c_str(),
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

        // ---- sample rate: force 2560000, fail-closed abs(actual-2560000) <= 5 Hz.
        //      Diagnosis only: the fix9r recovery compensates CFO/SRO per file, but a
        //      sample-rate mismatch beyond 5 Hz is a hardware fault, never corrected.
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

        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        const pluto::DataFormatInfo tx_fmt = dev->tx_data_format();
        std::printf("IQ_RF_LOOPBACK_FORMAT dir=tx %s\n",
                    pluto::describe_data_format(tx_fmt).c_str());
        std::printf("IQ_RF_LOOPBACK_FORMAT dir=rx %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);

        const int rx_pos_rail = iqdloop_sync::rail_positive(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));
        const int rx_neg_rail = iqdloop_sync::rail_negative(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));

        std::uint64_t global_frame_id = 0;
        // fix9r2b §6: collect per-file outcomes and aggregate via the PURE
        // iqrffix9r2b::aggregate_training_summary (fixes the corr_min=0 defect).
        std::vector<iqrffix9r2b::PerFileOutcome> file_outcomes;
        // fix9r2b §5: provisional payload metric accumulators (DIAGNOSTIC_ONLY).
        std::uint64_t provisional_count = 0;
        double provisional_corr_sum = 0.0;
        double provisional_corr_min = 0.0;
        double provisional_nmse_sum = 0.0;
        double provisional_nmse_max = 0.0;

        // fix9r2a Task C: per-file TX frame-verifier + push flags captured for the
        // R8 diagnostic line (they are computed inside the transfer).
        struct PerFileDiag {
            bool frame_layout_match = false;
            bool training_exact_match = false;
            bool settling_guard_exact_zero = false;    // fix9r2g
            bool payload_training_exact_match = false; // fix9r2g
            bool payload_exact_match = false;
            bool tx_push_ok = false;
        };

        // ---- per-file: transfer -> per-file recovery -> fidelity gate -> classify.
        // Returns the RF verdict string and leaves `rec` filled.
        const auto process_file = [&](const iqdloop::FrozenIq& fz,
                                      iqrfrec::PerFileRecovery& rec,
                                      std::string& rf_verdict,
                                      bool& rx_clipped,
                                      bool& tx_clipped,
                                      std::vector<std::complex<double>>& rx,
                                      PerFileDiag& diag) {
            std::printf("IQ_RF_LOOPBACK_FIX9R file=%s input_kind=%s source_index=%lld "
                        "source_class=%d deployed_class=%d modulation=%s "
                        "frozen_complex=%llu split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(),
                        static_cast<long long>(fz.source_index), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        fz.split_role.c_str());
            std::fflush(stdout);

            const iqrfloop_run_fix9r::RfTransferResultFix9r tr =
                iqrfloop_run_fix9r::transfer_one_file_rf_fix9r(
                    *dev, fz.path, fz.complex_count, fz.sha256, center_hz, gain_db,
                    tx_atten, delay_margin, noise_complex, &timing, target_rms);

            rep.tx_atten_requested = tr.tx_atten_requested_db;
            rep.tx_atten_readback = tr.tx_atten_readback_db;

            diag.frame_layout_match = tr.frame_verify.frame_layout_match;
            diag.training_exact_match = tr.frame_verify.training_exact_match;
            diag.settling_guard_exact_zero = tr.frame_verify.settling_guard_exact_zero;
            diag.payload_training_exact_match = tr.frame_verify.payload_training_exact_match;
            diag.payload_exact_match = tr.frame_verify.payload_exact_match;
            diag.tx_push_ok = tr.tx_push.ok;

            std::printf("IQ_RF_LOOPBACK_FIX9R_TX_LEVEL file=%s native_rms=%.3f "
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

            // fix9r2 Task R1/R2: five-stage TX byte provenance + frame verifier +
            // iio_buffer_push byte provenance (requested/returned/ok).
            std::printf("IQ_RF_LOOPBACK_FIX9R_TX_PROVENANCE file=%s "
                        "frame_verify=%d training_exact=%d payload_exact=%d layout=%d "
                        "push_ok=%d push_requested=%zu push_returned=%lld "
                        "payload_sha=%s train_sha=%s frame_sha=%s container_sha=%s "
                        "submitted_sha=%s\n",
                        fz.file_name.c_str(), tr.frame_verify.ok ? 1 : 0,
                        tr.frame_verify.training_exact_match ? 1 : 0,
                        tr.frame_verify.payload_exact_match ? 1 : 0,
                        tr.frame_verify.frame_layout_match ? 1 : 0,
                        tr.tx_push.ok ? 1 : 0, tr.tx_push.requested_bytes,
                        static_cast<long long>(tr.tx_push.returned_bytes),
                        tr.tx_provenance.payload_source.sha256.c_str(),
                        tr.tx_provenance.training_reference.sha256.c_str(),
                        tr.tx_provenance.framed_logical_iq.sha256.c_str(),
                        tr.tx_provenance.formatted_tx_container.sha256.c_str(),
                        tr.tx_provenance.submitted_iio_buffer.sha256.c_str());
            std::fflush(stdout);

            std::printf("IQ_RF_LOOPBACK_FIX9R_NEGATIVE_CONTROL_SUMMARY file=%s "
                        "warmup_refills=%zu windows=%zu rms_min=%.4f rms_median=%.4f "
                        "rms_max=%.4f stability_ratio=%.4f retry=%d noise_stable=%d "
                        "tx_stopped_readback=%d\n",
                        fz.file_name.c_str(), tr.warmup_refills,
                        tr.noise_window_rms.size(), tr.noise_rms_min,
                        tr.noise_rms_median, tr.noise_rms_max,
                        tr.noise_stability_ratio, tr.retry,
                        tr.noise_stable ? 1 : 0, tr.tx_stopped_readback ? 1 : 0);
            std::fflush(stdout);

            // fix9r2g: RX gain-mode endpoint read-back (pure reads; LOG-ONLY).
            std::printf("IQ_RF_LOOPBACK_FIX9R2G_RX_GAIN_MODE file=%s "
                        "mode_before_capture=%s gain_before_capture=%.3f "
                        "mode_after_capture=%s gain_after_capture=%.3f\n",
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

            // ---- per-file recovery from the training frame (never the payload) ----
            tx_clipped = tr.tx_clip_pre || tr.tx_clip_post;
            rx = iqrftrain::deinterleave(tr.rx);
            // fix9r2 Task R6: STRICT same-Pluto bounds + FULL-capture search (the
            // fix9r1 bug was the 4096-sample search window).  min_corr/residual match
            // the fidelity gate; CFO/SRO bounds are the same-Pluto sanity ceiling.
            iqrfrec::EstimateConfig rec_cfg;
            rec_cfg.min_corr = kFidelityTrainingCorrMin;
            // fix9r2h1: R8 and the 46-sample run share the same migrated
            // payload-domain residual contract.  Keeping a stale 0.05 full-run
            // branch excluded 42/46 frames after the 0.10 R8 gate had passed.
            rec_cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;
            rec_cfg.max_cfo_hz = 30.0;
            rec_cfg.max_sro_ppm = 30.0;
            rec_cfg.search_limit = 0;   // full capture
            rec_cfg.payload_tx_target_rms = tr.tx_target_rms;
            rec = iqrfrec::estimate(rx, rec_cfg);
            // The payload bytes are deliberately scaled before TX.  Recovery uses the
            // public TX-RMS contract for RF magnitude and the pilot for phase, then also
            // undoes this known digital scale before the original tensor reaches the model.
            rec.payload_tx_scale = tr.tx_scale;

            // RX clip: any railed sample in the burst capture.
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
            // Noise clip (negative control): a railed TX-off floor is a hardware fault.
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
            if (tr.loopback_readback != 0) {
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
                // fix9r2g: rec.valid (new semantics) already covers the preamble corr
                // gate, the de-ramped payload-training gain/corr/residual (migrated
                // residual<=0.10 gate), and the CFO/SRO bounds -- so RF_PRESERVES_IQ is
                // driven directly by rec.valid.
                rf_verdict = "RF_PRESERVES_IQ";
            }

            std::printf("IQ_RF_LOOPBACK_FIX9R_RECOVERY file=%s computed=%d valid=%d "
                        "failure=%s timing=%zu "
                        "gain_mag=%.6f phase_deg=%.3f cfo_hz=%.3f sro_ppm=%.3f "
                        "phase_drift_deg=%.3f training_corr=%.6f "
                        "training_residual=%.6f "
                        "payload_gain_mag=%.6f payload_rms_gain_mag=%.6f payload_phase_deg=%.3f "
                        "payload_training_corr=%.6f payload_training_residual=%.6f "
                        "fidelity=%s rx_clipped=%d\n",
                        fz.file_name.c_str(), rec.computed ? 1 : 0, rec.valid ? 1 : 0,
                        iqrfrec::failure_token(rec.failure), rec.timing_offset,
                        rec.gain_mag, rec.phase_deg, rec.cfo_hz, rec.sro_ppm,
                        rec.phase_drift_deg, rec.training_corr,
                        rec.training_residual,
                        rec.payload_gain_mag, rec.payload_rms_gain_mag, rec.payload_phase_deg,
                        rec.payload_training_corr, rec.payload_training_residual,
                        rf_verdict.c_str(),
                        rx_clipped ? 1 : 0);
            std::fflush(stdout);
        };

        // ---- single pass over holdout (no calibration subset: per-file recovery) ----
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("fix9r: cannot open " + rep.results_path);
        results << "file_name\tsource_index\traw24_class\tdeployed23_class\t"
                << "modulation\tsnr_db\tsplit_role\tvalid\traw24_pred\t"
                << "merged23_pred\tcorrect\ttraining_corr\ttraining_residual\t"
                << "timing_offset\tgain_mag\tphase_deg\tcfo_hz\tsro_ppm\t"
                << "phase_drift_deg\trf_verdict\n";

        // fix9r2d: waveform manifest + per-capture metadata manifest (DIAGNOSTIC-ONLY,
        // written in R8 mode).  The waveform manifest now carries the provenance proof
        // (mem_slice_sha256 / mem_equality / start_index / length / cycle_index /
        // linear_offset / circular_offset); the capture manifest carries the per-file
        // capture SHA / frame indices / RMS / DC / peak / clip / CFO / SRO / gain.
        std::ofstream wf_manifest;
        std::ofstream cap_manifest;
        if (rep.diagnostic_mode) {
            wf_manifest.open(rep.waveform_manifest_path, std::ios::binary);
            if (!wf_manifest)
                throw std::runtime_error("fix9r: cannot open " + rep.waveform_manifest_path);
            wf_manifest << "file_name\tkind\tpath\tsha256\tcomplex_samples\trms\tformat\t"
                        << "mem_slice_sha256\tmem_equality\tstart_index\tlength\t"
                        << "cycle_index\tlinear_offset\tcircular_offset\n";

            cap_manifest.open(rep.capture_manifest_path, std::ios::binary);
            if (!cap_manifest)
                throw std::runtime_error("fix9r: cannot open " + rep.capture_manifest_path);
            cap_manifest << "file_name\tcapture_sha256\tcapture_complex\tframe_start_abs\t"
                         << "training_start\ttraining_end\tpayload_start\tpayload_end\t"
                         << "full_frame_start\tfull_frame_end\tcycle_period\tcycle0_start\t"
                         << "cycle1_start\tlinear_offset\tcircular_offset\trms\tdc_re\tdc_im\t"
                         << "peak\tclip\tcfo_hz\tsro_ppm\tgain_mag\tphase_deg\ttiming_offset\t"
                         << "training_corr\ttraining_residual\tcomplete\n";
        }

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;
            iqrfrec::PerFileRecovery rec;
            std::string rf_verdict;
            bool rx_clipped = false;
            bool tx_clipped = false;
            std::vector<std::complex<double>> rx;
            PerFileDiag diag;
            std::size_t capture_attempts = 0;
            for (;;) {
                ++capture_attempts;
                rec = iqrfrec::PerFileRecovery{};
                rf_verdict.clear();
                rx_clipped = false;
                tx_clipped = false;
                rx.clear();
                diag = PerFileDiag{};

                process_file(fz, rec, rf_verdict, rx_clipped, tx_clipped, rx, diag);

                // fix9r2h3: retry only the measured, transient, payload-training
                // residual rejection.  The original 0.10 threshold is unchanged;
                // labels/predictions/payload truth never participate.  Infra, clip,
                // sync, corr, CFO, SRO, and interruption failures remain final.
                const bool retry =
                    !board::g_stop_requested &&
                    rf_verdict == "RF_DISTORTS_IQ" &&
                    iqrfrec::should_retry_payload_training_capture(
                        rec.failure, capture_attempts);
                if (!retry) break;

                std::printf("IQ_RF_LOOPBACK_FIX9R_CAPTURE_RETRY file=%s "
                            "completed_attempt=%zu max_attempts=%zu failure=%s "
                            "payload_training_residual=%.6f action=RETRY\n",
                            fz.file_name.c_str(), capture_attempts,
                            iqrfrec::kPayloadTrainingCaptureMaxAttempts,
                            iqrfrec::failure_token(rec.failure),
                            rec.payload_training_residual);
                std::fflush(stdout);
            }
            std::printf("IQ_RF_LOOPBACK_FIX9R_CAPTURE_ATTEMPTS file=%s attempts=%zu "
                        "retries=%zu final_failure=%s final_valid=%d\n",
                        fz.file_name.c_str(), capture_attempts,
                        capture_attempts - 1, iqrfrec::failure_token(rec.failure),
                        rec.valid ? 1 : 0);
            std::fflush(stdout);

            if (tx_clipped) { rep.any_tx_clip = true; ++rep.tx_clip_count; }
            if (rx_clipped) { rep.any_rx_clip = true; ++rep.rx_clip_count; }
            if (rec.computed) ++rep.estimate_computed;

            // fix9r2b §6: record the per-file outcome; aggregate (corr/residual over
            // MEASURED files, valid_count separately) happens after the loop via the
            // pure aggregate_training_summary -- never gated behind rec.valid.
            {
                iqrffix9r2b::PerFileOutcome o;
                o.computed = rec.computed;
                o.valid = rec.valid;
                o.failure = rec.failure;
                o.training_corr = rec.training_corr;
                o.training_residual = rec.training_residual;
                file_outcomes.push_back(o);
            }

            // ---- apply per-file recovery -> payload (fix9r2g: apply() is fail-closed
            //      and throws when rec.valid==false, so it is only called when valid;
            //      the R8 diagnostic records provisional payload metrics separately) ----
            const std::vector<std::complex<double>> payload =
                rec.valid ? iqrfrec::apply(rx, rec)
                          : std::vector<std::complex<double>>();

            // ---- fix9r2a Task C: R8 diagnostic per-sample record + gate counters ----
            // fix9r2d: capture the 8 diagnostic waveforms + the PROVISIONAL scalar-
            // recovery payload metrics (DIAGNOSTIC_ONLY: computed even when the
            // fidelity gate fails, but never fed to the model).  Every rx-derived
            // slice is saved from the SAME rx buffer iqrfrec::estimate ran on, with
            // a provenance proof (mem_slice_sha256 == file sha256 -> mem_equality==1).
            if (rep.diagnostic_mode) {
                const std::vector<std::complex<double>> known =
                    iqrftrain::deinterleave(iqdloop::load_ci16(fz.path, fz.complex_count));
                const std::vector<std::complex<double>> pre =
                    iqrftrain::preamble_complex();

                // §5: provisional payload = scalar recovery (fix9r2g fail-closed: empty
                // when rec.valid==false, exactly like iqrfrec::apply, so an unrecovered
                // payload is never measured as if recovered).
                const std::vector<std::complex<double>> provisional =
                    iqrffix9r2b::provisional_apply_scalar(rx, rec);
                const iqrffix9r2b::ProvisionalMetrics pm =
                    iqrffix9r2b::provisional_payload_metrics(provisional, known);
                const double provisional_payload_corr = pm.computed ? pm.corr : 0.0;
                const double provisional_payload_nmse = pm.computed ? pm.nmse : 0.0;
                if (pm.computed) {
                    ++provisional_count;
                    provisional_corr_sum += provisional_payload_corr;
                    provisional_nmse_sum += provisional_payload_nmse;
                    if (provisional_count == 1 ||
                        provisional_payload_corr < provisional_corr_min)
                        provisional_corr_min = provisional_payload_corr;
                    if (provisional_count == 1 ||
                        provisional_payload_nmse > provisional_nmse_max)
                        provisional_nmse_max = provisional_payload_nmse;
                }

                // fix9r2g: payload-domain training-block residual (migrated gate) and
                // the R8-only recovered-payload scale error (DIAGNOSTIC-ONLY audit;
                // never deploy runtime, never from expected-payload parameter estimation).
                if (rec.payload_training_residual > rep.payload_training_residual_max)
                    rep.payload_training_residual_max = rec.payload_training_residual;
                const double scale_err =
                    iqrffix9r2b::payload_scale_error(provisional, known);
                if (scale_err > rep.payload_scale_error_max)
                    rep.payload_scale_error_max = scale_err;

                // §1/§2/§4: the 8 waveforms (requirement 1 + 2).  Raw rx slices carry
                // their absolute capture index + cycle index so the offline analyzer
                // can re-derive every slice from the capture metadata.  expected_* /
                // provisional are references (start_index == -1) whose provenance is
                // the deterministic reference, or the offline reproduction of
                // provisional_apply_scalar (requirement 6).
                const std::size_t period = iqrflayout::kFramePeriodComplex;
                const std::string stem = iqrffix9r2b::waveform_stem(fz.file_name) +
                    "_rms" + std::to_string(static_cast<long long>(std::llround(target_rms)));

                struct Wf {
                    const char* kind;
                    std::string path;
                    const std::vector<std::complex<double>>* src;  // vector to slice
                    std::size_t start;                             // slice offset in *src
                    std::size_t len;                               // slice length
                    long long start_index;                         // capture index or -1
                    int cycle_index;
                };
                const std::vector<Wf> wfs = {
                    {"expected_training",             join_path(out_dir, stem + "__expected_training.f32"),             &pre,         0,                            pre.size(),                -1, -1},
                    {"raw_aligned_rx_training",       join_path(out_dir, stem + "__raw_aligned_rx_training.f32"),       &rx,          rec.timing_offset,           iqrflayout::kTrainingLength, static_cast<long long>(rec.timing_offset), -1},
                    {"raw_aligned_rx_payload",        join_path(out_dir, stem + "__raw_aligned_rx_payload.f32"),        &rx,          rec.timing_offset + iqrflayout::kPayloadOffset, iqrflayout::kPayloadLength, static_cast<long long>(rec.timing_offset + iqrflayout::kPayloadOffset), -1},
                    {"raw_aligned_rx_full_frame",     join_path(out_dir, stem + "__raw_aligned_rx_full_frame.f32"),     &rx,          rec.timing_offset,           period,                    static_cast<long long>(rec.timing_offset), -1},
                    {"raw_cycle_0_full_frame",        join_path(out_dir, stem + "__raw_cycle_0_full_frame.f32"),        &rx,          0,                            period,                    0, 0},
                    {"raw_cycle_1_full_frame",        join_path(out_dir, stem + "__raw_cycle_1_full_frame.f32"),        &rx,          period,                       period,                    static_cast<long long>(period), 1},
                    {"expected_payload",              join_path(out_dir, stem + "__expected_payload.f32"),              &known,       0,                            known.size(),              -1, -1},
                    {"provisional_recovered_payload", join_path(out_dir, stem + "__provisional_recovered_payload.f32"), &provisional, 0,                            provisional.size(),        -1, -1},
                };
                for (const Wf& w : wfs) {
                    const iqrffix9r2d::ProvenanceRecord p =
                        iqrffix9r2d::save_slice_with_provenance(
                            w.path, *w.src, w.start, w.len, w.start_index,
                            w.cycle_index, period);
                    if (p.rec.path.empty()) {
                        rep.error = "fix9r2d: failed to write " + w.path;
                        return rep;
                    }
                    // requirement 4: equality MUST be 1 (saved file == in-memory slice
                    // of the buffer that participated in the diagnosis).
                    if (p.equality != 1) {
                        rep.error = "fix9r2d: provenance FAILED for " + w.path +
                            " (mem_slice_sha256 != file sha256)";
                        return rep;
                    }
                    std::printf("ROUTE_F_FIX9R2D_WAVEFORM file=%s kind=%s path=%s "
                                "sha=%s samples=%zu rms=%.6f mem_sha=%s equality=%d "
                                "start_index=%lld length=%zu cycle=%d format=%s\n",
                                fz.file_name.c_str(), w.kind, p.rec.path.c_str(),
                                p.rec.sha256.c_str(), p.rec.complex_samples, p.rec.rms,
                                p.mem_sha256.c_str(), p.equality,
                                static_cast<long long>(p.start_index), p.length,
                                p.cycle_index, p.rec.format.c_str());
                    wf_manifest << fz.file_name << "\t" << w.kind << "\t"
                                << p.rec.path << "\t" << p.rec.sha256 << "\t"
                                << p.rec.complex_samples << "\t" << p.rec.rms << "\t"
                                << p.rec.format << "\t"
                                << p.mem_sha256 << "\t" << p.equality << "\t"
                                << p.start_index << "\t" << p.length << "\t"
                                << p.cycle_index << "\t" << p.linear_offset << "\t"
                                << p.circular_offset << "\n";
                }

                // §3: per-capture metadata manifest (capture SHA / frame indices /
                // RMS / DC / peak / clip / CFO / SRO / gain).
                {
                    const iqrffix9r2d::CaptureMeta cm =
                        iqrffix9r2d::compute_capture_meta(rx, rec, rx.size(), rx_clipped);
                    if (!cm.complete) {
                        rep.error = "fix9r2d: capture metadata incomplete for " + fz.file_name;
                        return rep;
                    }
                    cap_manifest << fz.file_name << "\t" << cm.capture_sha256 << "\t"
                                 << cm.capture_complex << "\t" << cm.frame_start_abs << "\t"
                                 << cm.training_start << "\t" << cm.training_end << "\t"
                                 << cm.payload_start << "\t" << cm.payload_end << "\t"
                                 << cm.full_frame_start << "\t" << cm.full_frame_end << "\t"
                                 << cm.cycle_period << "\t" << cm.cycle0_start << "\t"
                                 << cm.cycle1_start << "\t" << cm.linear_offset << "\t"
                                 << cm.circular_offset << "\t" << cm.rms << "\t"
                                 << cm.dc_re << "\t" << cm.dc_im << "\t" << cm.peak << "\t"
                                 << cm.clip << "\t" << cm.cfo_hz << "\t" << cm.sro_ppm << "\t"
                                 << cm.gain_mag << "\t" << cm.phase_deg << "\t"
                                 << cm.timing_offset << "\t" << cm.training_corr << "\t"
                                 << cm.training_residual << "\t" << (cm.complete ? 1 : 0) << "\n";
                }
                std::fflush(stdout);

                if (diag.frame_layout_match) ++rep.diag_frame_layout_match;
                if (diag.training_exact_match) ++rep.diag_training_exact_match;
                if (diag.settling_guard_exact_zero) ++rep.diag_settling_guard_exact_zero;
                if (diag.payload_training_exact_match) ++rep.diag_payload_training_exact_match;
                if (diag.payload_exact_match) ++rep.diag_payload_exact_match;
                if (diag.tx_push_ok) ++rep.diag_tx_push_ok;

                char line[1024];
                std::snprintf(line, sizeof(line),
                    "ROUTE_F_FIX9R2_DIAGNOSTIC file=%s split_role=%s modulation=%s "
                    "source_class=%d deployed_class=%d frame_layout_match=%d "
                    "training_exact_match=%d settling_guard_exact_zero=%d "
                    "payload_training_exact_match=%d payload_exact_match=%d tx_push_ok=%d "
                    "estimate_computed=%d estimate_valid=%d failure_reason=%s "
                    "training_corr=%.6f training_residual=%.6f "
                    "payload_training_corr=%.6f payload_training_residual=%.6f "
                    "payload_scale_error=%.6f timing=%zu cfo_hz=%.3f "
                    "sro_ppm=%.3f provisional_payload_corr=%.6f "
                    "provisional_payload_nmse=%.6f tx_clipped=%d rx_clipped=%d",
                    fz.file_name.c_str(), fz.split_role.c_str(), fz.modulation.c_str(),
                    fz.source_class, fz.deployed_class,
                    diag.frame_layout_match ? 1 : 0,
                    diag.training_exact_match ? 1 : 0,
                    diag.settling_guard_exact_zero ? 1 : 0,
                    diag.payload_training_exact_match ? 1 : 0,
                    diag.payload_exact_match ? 1 : 0,
                    diag.tx_push_ok ? 1 : 0,
                    rec.computed ? 1 : 0, rec.valid ? 1 : 0,
                    iqrfrec::failure_token(rec.failure), rec.training_corr,
                    rec.training_residual, rec.payload_training_corr,
                    rec.payload_training_residual, scale_err,
                    rec.timing_offset, rec.cfo_hz, rec.sro_ppm,
                    provisional_payload_corr, provisional_payload_nmse,
                    tx_clipped ? 1 : 0, rx_clipped ? 1 : 0);
                rep.diag_lines.push_back(line);
            }

            // ---- fidelity gate: a failing file is SKIPPED (never silently scored) ----
            const bool gate_ok = (rf_verdict == "RF_PRESERVES_IQ");
            if (!gate_ok) {
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons[rf_verdict];
                std::printf("IQ_RF_LOOPBACK_FIX9R file=%s classification=SKIPPED "
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
                        << rec.phase_drift_deg << "\t" << rf_verdict << "\n";
                continue;
            }

            // ---- chain -> D2 restore (payload already recovered above) ----
            // convert to interleaved int16
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
            // NO global gain: the per-file recovery already undid the RF path.
            // Restore DC + rec_scale from build-time manifest constants only.
            iqdloop::apply_d2_restore_to_stream(recovered_stream, chain::kFrameComplex,
                                                fz.original_dc_i, fz.original_dc_q,
                                                fz.d2_rec_scale);

            std::printf("IQ_RF_LOOPBACK_FIX9R_D2_RESTORE file=%s source_index=%lld "
                        "dc_i=%.9f dc_q=%.9f rec_scale=%.9f manifest_sha_ok=1 "
                        "per_file_recovery_used=1 global_gain_used=0\n",
                        fz.file_name.c_str(),
                        static_cast<long long>(fz.source_index),
                        fz.original_dc_i, fz.original_dc_q, fz.d2_rec_scale);
            std::fflush(stdout);

            const std::vector<float> ref =
                iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                               fz.recovered_tensor_sha256);
            const iqdloop::ClassificationWindow cw =
                iqdloop::select_classification_window(recovered_stream, ref);
            std::printf("IQ_RF_LOOPBACK_FIX9R_WINDOW file=%s recovered_frames=%llu "
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
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.deployed_class << "\t"
                        << fz.modulation << "\t" << fz.snr_db << "\t"
                        << fz.split_role << "\t0\t-1\t-1\t-1\t"
                        << rec.training_corr << "\t" << rec.training_residual << "\t"
                        << static_cast<long long>(rec.timing_offset) << "\t"
                        << rec.gain_mag << "\t" << rec.phase_deg << "\t"
                        << rec.cfo_hz << "\t" << rec.sro_ppm << "\t"
                        << rec.phase_drift_deg << "\tRF_NO_VALID_WINDOW\n";
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

            // ---- fix9r2g: R8 classification vs the FROZEN offline baseline
            //      prediction, read from the exact baseline TSV by stable key
            //      source_index (never deployed_class, never row number, never a fuzzy
            //      file name).  prediction_agreement = rf_pred == frozen_baseline_pred;
            //      label_correct = rf_pred == deployed_class (ground-truth label, print
            //      only, never gated).  A missing baseline key fails the agreement
            //      (fail-closed: the R8 gate then reports prediction_agreement < holdout).
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
            if (prediction_agreement) ++rep.r8_prediction_agreement;
            if (label_correct) ++rep.r8_label_correct;
            std::printf("IQ_RF_LOOPBACK_FIX9R2G_R8_CLASSIFY file=%s baseline_pred=%d "
                        "rf_pred=%d source_label=%d prediction_agreement=%d "
                        "label_correct=%d\n",
                        fz.file_name.c_str(), baseline_pred, merged_top, fz.source_class,
                        prediction_agreement ? 1 : 0, label_correct ? 1 : 0);
            std::fflush(stdout);

            ++global_frame_id;

            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;
            r.source = "iq_rf_loopback_23class_fix9r";
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
                    << rec.phase_drift_deg << "\t" << rf_verdict << "\n";

            std::printf("IQ_RF_LOOPBACK_FIX9R file=%s frames=1 correct=%d deployed=%d "
                        "source=%d raw24_pred=%d merged23_pred=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.deployed_class,
                        fz.source_class, raw_top, merged_top);
            std::fflush(stdout);
        }
        results.close();

        // fix9r2b §6: aggregate over MEASURED files (preamble found), not only valid
        // files -- fixes the fix9r2a defect where a run failing only on residual
        // reported training_corr_min=0 / training_residual_max=0.
        const iqrffix9r2b::TrainingSummary ts =
            iqrffix9r2b::aggregate_training_summary(file_outcomes);
        rep.training_estimates = ts.valid_count;
        rep.training_measured = ts.measured_count;
        rep.training_corr_min = ts.corr_min;
        rep.training_corr_avg = ts.corr_avg;
        rep.training_residual_max = ts.residual_max;
        rep.training_residual_avg = ts.residual_avg;

        // fix9r2b §5: provisional scalar-recovery payload metrics (DIAGNOSTIC_ONLY).
        rep.provisional_payload_measured = provisional_count;
        rep.provisional_payload_corr_min = provisional_corr_min;
        rep.provisional_payload_corr_avg =
            provisional_count > 0 ? provisional_corr_sum / provisional_count : 0.0;
        rep.provisional_payload_nmse_max = provisional_nmse_max;
        rep.provisional_payload_nmse_avg =
            provisional_count > 0 ? provisional_nmse_sum / provisional_count : 0.0;

        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- fix9r2a Task C/D: flush the R8 diagnostic lines (now that the run-level
    //      parameter-restore result is known) + evaluate the diagnostic gate ----
    if (rep.diagnostic_mode) {
        for (const std::string& ln : rep.diag_lines)
            std::printf("%s restore_ok=%d\n", ln.c_str(), rep.restore_ok ? 1 : 0);
        std::fflush(stdout);

        iqrffix9r2a::DiagnosticGateInput dgi;
        dgi.requested_classes = rep.diagnostic_classes;
        dgi.selected_classes = rep.diagnostic_selected_classes;
        dgi.requested_count = rep.diagnostic_requested_count;
        dgi.holdout_files = rep.holdout_files;
        dgi.estimate_computed = rep.estimate_computed;
        dgi.estimate_valid = rep.training_estimates;
        dgi.frame_layout_match = rep.diag_frame_layout_match;
        dgi.training_exact_match = rep.diag_training_exact_match;
        dgi.settling_guard_exact_zero = rep.diag_settling_guard_exact_zero;
        dgi.payload_training_exact_match = rep.diag_payload_training_exact_match;
        dgi.payload_exact_match = rep.diag_payload_exact_match;
        dgi.tx_push_ok = rep.diag_tx_push_ok;
        dgi.tx_clipped = rep.tx_clip_count;
        dgi.rx_clipped = rep.rx_clip_count;
        dgi.training_corr_min = rep.training_corr_min;
        dgi.payload_training_residual_max = rep.payload_training_residual_max;
        dgi.payload_scale_error_max = rep.payload_scale_error_max;
        dgi.scored = rep.scored;
        dgi.rf_excluded = rep.rf_excluded;
        dgi.prediction_agreement = rep.r8_prediction_agreement;
        dgi.restore_ok = rep.restore_ok;
        const iqrffix9r2a::DiagnosticGateResult dgr =
            iqrffix9r2a::evaluate_diagnostic_gate(dgi);
        rep.diagnostic_pass = dgr.pass;
        rep.diagnostic_report = dgr.report;
        std::printf("ROUTE_F_FIX9R2_DIAGNOSTIC token=%s selected_classes=%s "
                    "holdout_files=%llu estimate_computed=%llu estimate_valid=%llu "
                    "training_corr_min=%.6f payload_training_residual_max=%.6f "
                    "payload_scale_error_max=%.6f "
                    "frame_layout_match=%llu training_exact_match=%llu "
                    "settling_guard_exact_zero=%llu payload_training_exact_match=%llu "
                    "payload_exact_match=%llu tx_push_ok=%llu tx_clipped=%llu "
                    "rx_clipped=%llu scored=%llu rf_excluded=%llu "
                    "prediction_agreement=%llu restore_ok=%d%s%s\n",
                    rep.diagnostic_pass ? kDiagnosticPass : kDiagnosticFail,
                    rep.diagnostic_selected_classes.c_str(),
                    static_cast<unsigned long long>(rep.holdout_files),
                    static_cast<unsigned long long>(rep.estimate_computed),
                    static_cast<unsigned long long>(rep.training_estimates),
                    rep.training_corr_min, rep.payload_training_residual_max,
                    rep.payload_scale_error_max,
                    static_cast<unsigned long long>(rep.diag_frame_layout_match),
                    static_cast<unsigned long long>(rep.diag_training_exact_match),
                    static_cast<unsigned long long>(rep.diag_settling_guard_exact_zero),
                    static_cast<unsigned long long>(rep.diag_payload_training_exact_match),
                    static_cast<unsigned long long>(rep.diag_payload_exact_match),
                    static_cast<unsigned long long>(rep.diag_tx_push_ok),
                    static_cast<unsigned long long>(rep.tx_clip_count),
                    static_cast<unsigned long long>(rep.rx_clip_count),
                    static_cast<unsigned long long>(rep.scored),
                    static_cast<unsigned long long>(rep.rf_excluded),
                    static_cast<unsigned long long>(rep.r8_prediction_agreement),
                    rep.restore_ok ? 1 : 0,
                    rep.diagnostic_report.empty() ? "" : " report=",
                    rep.diagnostic_report.c_str());
        std::fflush(stdout);
    }

    // ---- acceptance gate (Task F) + the four tokens (Task E) ----
    const double overall_acc = rep.total_valid > 0
        ? static_cast<double>(rep.total_correct) /
          static_cast<double>(rep.total_valid) : 0.0;
    // fix9r2b §6: in diagnostic mode the 46-sample regression is NOT evaluated, so the
    // accuracy fields carry a -1.0 sentinel (rendered NOT_EVALUATED / null downstream),
    // not the misleading 0.0 agreement / -99.34 pp the fix9r2a diagnostic printed.
    if (rep.diagnostic_mode) {
        rep.prediction_agreement = -1.0;
        rep.rf_accuracy = -1.0;
        rep.accuracy_delta_pp = 0.0;
    } else {
        rep.prediction_agreement = overall_acc;
        rep.rf_accuracy = overall_acc;
        rep.accuracy_delta_pp = 100.0 * (rep.rf_accuracy - rep.baseline_accuracy);
    }

    const bool no_clip = !rep.any_tx_clip && !rep.any_rx_clip;
    rep.rf_fidelity_pass = rep.full_run && rep.baseline_identity_ok &&
                           (rep.scored == rep.holdout_files) &&
                           (rep.rf_excluded == 0) &&
                           (rep.training_estimates == rep.holdout_files) && no_clip;
    rep.model_domain_recovered =
        (rep.prediction_agreement >= kAgreementMin) &&
        (rep.rf_accuracy >= rep.baseline_accuracy - kAccuracyDeltaPpMax / 100.0);
    const bool ask4_not_degraded =
        (rep.ask4_total == 0) || (rep.ask4_correct == rep.ask4_total);
    rep.regression_pass = rep.rf_fidelity_pass && rep.model_domain_recovered &&
                          ask4_not_degraded && rep.restore_ok;

    const std::string measurement_token = (rep.error.empty() && rep.sample_rate_ok)
                                              ? kMeasurementComplete
                                              : kMeasurementIncomplete;
    const std::string fidelity_token = rep.rf_fidelity_pass ? kRfFidelityPass : kRfFidelityFail;
    // fix9r2b §6: token semantics via the PURE gate_tokens -- in diagnostic mode the
    // regression_token is NOT_EVALUATED (never ROUTE_F_23CLASS_ACCURACY_REGRESSION_FAIL)
    // and the summary_token is the R8 diagnostic token; in regression mode the
    // diagnostic_token is NOT_EVALUATED.
    const iqrffix9r2b::GateTokens gt =
        iqrffix9r2b::gate_tokens(rep.diagnostic_mode, rep.diagnostic_pass,
                                 rep.regression_pass);
    const std::string regression_token = gt.regression_token;
    const std::string summary_token = gt.summary_token;

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
        f << "  \"token\":\"" << summary_token << "\",\n";
        f << "  \"diagnostic_mode\":" << (rep.diagnostic_mode ? "true" : "false") << ",\n";
        if (rep.diagnostic_mode) {
            f << "  \"diagnostic_classes\":\"" << json_escape(rep.diagnostic_classes) << "\",\n";
            f << "  \"diagnostic_selected_classes\":\""
              << json_escape(rep.diagnostic_selected_classes) << "\",\n";
            f << "  \"diagnostic_pass\":" << (rep.diagnostic_pass ? "true" : "false") << ",\n";
            f << "  \"diagnostic_report\":\"" << json_escape(rep.diagnostic_report) << "\",\n";
        }
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"rf_fidelity_token\":\"" << fidelity_token << "\",\n";
        f << "  \"model_domain_token\":\""
          << (rep.model_domain_recovered ? "" : kModelDomainNotProven) << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"frozen_dir\":\"" << json_escape(rep.frozen_dir) << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"baseline_path\":\"" << json_escape(rep.baseline_path) << "\",\n";
        f << "  \"baseline_rows\":" << rep.baseline_rows << ",\n";
        f << "  \"baseline_accuracy\":" << rep.baseline_accuracy << ",\n";
        f << "  \"baseline_identity_ok\":" << (rep.baseline_identity_ok ? "true" : "false") << ",\n";
        f << "  \"full_run\":" << (rep.full_run ? "true" : "false") << ",\n";
        f << "  \"holdout_files\":" << rep.holdout_files << ",\n";
        f << "  \"training_estimates\":" << rep.training_estimates << ",\n";
        f << "  \"training_corr_min\":" << rep.training_corr_min << ",\n";
        f << "  \"training_corr_avg\":" << rep.training_corr_avg << ",\n";
        f << "  \"training_residual_max\":" << rep.training_residual_max << ",\n";
        f << "  \"training_residual_avg\":" << rep.training_residual_avg << ",\n";
        f << "  \"training_measured\":" << rep.training_measured << ",\n";
        if (rep.diagnostic_mode) {
            f << "  \"provisional_payload_measured\":" << rep.provisional_payload_measured << ",\n";
            f << "  \"provisional_payload_corr_min\":" << rep.provisional_payload_corr_min << ",\n";
            f << "  \"provisional_payload_corr_avg\":" << rep.provisional_payload_corr_avg << ",\n";
            f << "  \"provisional_payload_nmse_max\":" << rep.provisional_payload_nmse_max << ",\n";
            f << "  \"provisional_payload_nmse_avg\":" << rep.provisional_payload_nmse_avg << ",\n";
            f << "  \"waveform_manifest_path\":\"" << json_escape(rep.waveform_manifest_path) << "\",\n";
        }
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"rf_excluded\":" << rep.rf_excluded << ",\n";
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
        if (rep.diagnostic_mode) {
            f << "  \"prediction_agreement\":null,\n";
            f << "  \"rf_accuracy\":null,\n";
            f << "  \"accuracy_delta_pp\":null,\n";
            f << "  \"overall_accuracy\":null,\n";
            f << "  \"macro_accuracy\":null,\n";
        } else {
            f << "  \"prediction_agreement\":" << rep.prediction_agreement << ",\n";
            f << "  \"rf_accuracy\":" << rep.rf_accuracy << ",\n";
            f << "  \"accuracy_delta_pp\":" << rep.accuracy_delta_pp << ",\n";
            f << "  \"overall_accuracy\":" << overall_acc << ",\n";
            f << "  \"macro_accuracy\":" << macro_acc << ",\n";
        }
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

    // Summary log (Task G).
    {
        std::ofstream f(rep.log_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.log_path);
        f << "token=" << summary_token
          << " measurement=" << measurement_token
          << " rf_fidelity=" << fidelity_token
          << " model_domain=" << (rep.model_domain_recovered ? "RECOVERED" : kModelDomainNotProven)
          << " holdout=" << rep.holdout_files
          << " scored=" << rep.scored
          << " rf_excluded=" << rep.rf_excluded
          << " training_estimates=" << rep.training_estimates
          << " training_measured=" << rep.training_measured;
        if (rep.diagnostic_mode) {
            f << " prediction_agreement=NOT_EVALUATED"
              << " rf_accuracy=NOT_EVALUATED"
              << " delta_pp=NOT_EVALUATED";
        } else {
            f << " prediction_agreement=" << rep.prediction_agreement
              << " rf_accuracy=" << rep.rf_accuracy
              << " delta_pp=" << rep.accuracy_delta_pp;
        }
        f << " 4ask=" << rep.ask4_correct << "/" << rep.ask4_total
          << " restore_ok=" << (rep.restore_ok ? 1 : 0);
        if (rep.diagnostic_mode)
            f << " diagnostic=" << (rep.diagnostic_pass ? "PASS" : "FAIL")
              << " selected_classes=" << rep.diagnostic_selected_classes
              << " estimate_computed=" << rep.estimate_computed
              << " provisional_payload_measured=" << rep.provisional_payload_measured
              << " provisional_payload_corr_min=" << rep.provisional_payload_corr_min
              << " provisional_payload_corr_avg=" << rep.provisional_payload_corr_avg
              << " provisional_payload_nmse_max=" << rep.provisional_payload_nmse_max
              << " tx_clipped=" << rep.tx_clip_count
              << " rx_clipped=" << rep.rx_clip_count;
        f << "\n";
    }

    if (rep.diagnostic_mode) {
        // R8 diagnostic: the 46-sample regression is NOT evaluated.  The diagnostic
        // token (ROUTE_F_FIX9R2_DIAGNOSTIC_PASS/FAIL) was already printed above.
        std::printf("ROUTE_F_23CLASS_ACCURACY_REGRESSION token=NOT_EVALUATED "
                    "diagnostic=%s selected_classes=%s holdout=%llu scored=%llu "
                    "rf_excluded=%llu restore_ok=%d\n",
                    rep.diagnostic_pass ? kDiagnosticPass : kDiagnosticFail,
                    rep.diagnostic_selected_classes.c_str(),
                    static_cast<unsigned long long>(rep.holdout_files),
                    static_cast<unsigned long long>(rep.scored),
                    static_cast<unsigned long long>(rep.rf_excluded),
                    rep.restore_ok ? 1 : 0);
    } else {
        std::printf("ROUTE_F_23CLASS_ACCURACY_REGRESSION token=%s measurement=%s "
                    "rf_fidelity=%s model_domain=%s scored=%llu rf_excluded=%llu "
                    "training_estimates=%llu prediction_agreement=%.6f rf_accuracy=%.6f "
                    "delta_pp=%.3f 4ask=%llu/%llu restore_ok=%d\n",
                    regression_token.c_str(), measurement_token.c_str(), fidelity_token.c_str(),
                    rep.model_domain_recovered ? "RECOVERED" : kModelDomainNotProven,
                    static_cast<unsigned long long>(rep.scored),
                    static_cast<unsigned long long>(rep.rf_excluded),
                    static_cast<unsigned long long>(rep.training_estimates),
                    rep.prediction_agreement, rep.rf_accuracy, rep.accuracy_delta_pp,
                    static_cast<unsigned long long>(rep.ask4_correct),
                    static_cast<unsigned long long>(rep.ask4_total),
                    rep.restore_ok ? 1 : 0);
    }
    std::fflush(stdout);

    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          !frozen.empty() && all_capture_ok &&
                          rep.baseline_identity_ok;
    rep.functional_pass = infra_ok && (rep.scored > 0);

    const std::string acc_pred = rep.diagnostic_mode
        ? "NOT_EVALUATED" : std::to_string(rep.prediction_agreement);
    const std::string acc_rf = rep.diagnostic_mode
        ? "NOT_EVALUATED" : std::to_string(rep.rf_accuracy);
    const std::string acc_delta = rep.diagnostic_mode
        ? "NOT_EVALUATED" : std::to_string(rep.accuracy_delta_pp);
    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " baseline_rows=" + std::to_string(rep.baseline_rows) +
                         " full_run=" + (rep.full_run ? "1" : "0") +
                         " scored=" + std::to_string(rep.scored) +
                         " rf_excluded=" + std::to_string(rep.rf_excluded) +
                         " prediction_agreement=" + acc_pred +
                         " rf_accuracy=" + acc_rf +
                         " delta_pp=" + acc_delta +
                         " regression_token=" + regression_token +
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

}  // namespace iqrfloop23fix9r
