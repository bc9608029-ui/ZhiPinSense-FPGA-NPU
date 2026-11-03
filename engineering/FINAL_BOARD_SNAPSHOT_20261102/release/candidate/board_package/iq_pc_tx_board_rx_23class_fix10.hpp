#pragma once

// iq_pc_tx_board_rx_23class_fix10.hpp -- fix10prep2: the REAL dual-SDR 23-class
// runner, RX-only on the BOARD side.
//
// Topology: the Windows PC owns the TX SDR (periodically emits the frozen CI16 burst
// over 50-ohm coax) and the board owns the RX SDR (capture -> coarse CFO -> fine
// sync/gain recovery -> D2 restore -> NPU24 -> 24->23 merge -> frozen baseline).
// The two ends exchange ONLY control messages + sample identity + SHA over a TCP
// control channel (iq_pc_tx_board_rx_transfer_fix10.hpp) -- never real-time IQ over
// the network.  This runner contains NO TX API: it never calls make_device(tx_uri),
// tx_start_cyclic, set_tx_lo, or set_tx_attenuation.  It only captures RX.
//
// Signal path (RED-LINE recovery math untouched):
//   1. board builds the SAME burst the PC transmits, from the frozen ci16 + target_rms
//      (iq_pc_tx_board_rx_transfer_fix10.hpp::build_tx_burst_from_frozen) -- this is
//      the board's independent provenance expectation, not a TX.
//   2. negative control: RX-only noise-floor capture while the PC's TX is off (the
//      control-channel state machine guarantees TX-off at this point; the board has
//      no TX device to stop).
//   3. PREPARE -> PREPARED -> START -> READY (PC builds/verifies, then transmits).
//   4. RX capture (>= 2 full burst periods + margin).
//   5. recover_payload_with_coarse_cfo (iq_dual_sdr_coarse_cfo_recovery.hpp): robust
//      coarse CFO (LS-gain phase diff preamble-vs-training-block, +/-625 Hz) then the
//      fine estimate/apply from iq_rf_sync_recovery.hpp.
//   6. fidelity gate -> chain -> D2 restore -> reference-aligned window -> NPU24 ->
//      merge23 -> frozen-baseline comparison.
//
// Output (MEASUREMENT only -- never RF_PASS / RF_PATH_PROVEN / FIX10_READY /
// PROJECT_COMPLETE / FINAL_* / ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS):
//   * route_f_fix10prep2_pc_tx_board_rx_results.tsv
//   * route_f_fix10prep2_pc_tx_board_rx_confusion_23.csv
//   * route_f_fix10prep2_pc_tx_board_rx_per_class.json
//   * route_f_fix10prep2_pc_tx_board_rx_summary.json / .log
//
// The two-sample (BPSK + 4ASK) acceptance is a MEASUREMENT the operator reads; this
// runner does not auto-unlock the 46-sample run.  If the dual-SDR CFO exceeds the
// coarse CFO unambiguous range (+/-625 Hz) on the first real board test, the runner
// stops and reports the real failure -- it never widens a gate or guesses a fix.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_per_frame_recovery.hpp"        // iqrfrec (shim -> iq_rf_sync_recovery.hpp)
#include "iq_rf_frame_layout.hpp"
#include "iq_rf_loopback_transfer.hpp"         // iqrfloop_run::kRfDiscard* / kRfNoise*
#include "iq_dual_sdr_coarse_cfo_recovery.hpp" // iqdual23fix10::recover_payload_with_coarse_cfo
#include "iq_rf_fix9r_baseline.hpp"            // iqrffix9r::load_baseline / BaselineRow
#include "iq_rf_fix9r2a_diagnostic.hpp"        // iqrffix9r2a::select_diagnostic_holdout
#include "iq_pc_tx_board_rx_transfer_fix10.hpp"// iqpctbrx::* state machine + build burst
#include "iq_fix10_canonical_frame.hpp"         // fix10canonical::buildTxBurstFromFrozen
#include "rml23_merged.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/tcp_control_client.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <sys/stat.h>

#include <algorithm>
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
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqpcbtrx23fix10 {

using Clock = std::chrono::steady_clock;

// fix10prep2 tokens (measurement, never a regression PASS).
constexpr const char* kMeasurementComplete = "FIX10PREP2_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete = "FIX10PREP2_MEASUREMENT_INCOMPLETE";

constexpr double kFidelityTrainingCorrMin = 0.9;   // preamble peak corr floor
constexpr std::size_t kDelayMarginDefault = 8192;  // capture margin past 2 periods

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

inline void write_ci16_le(const std::string& path,
                          const std::vector<std::int16_t>& samples) {
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    if (!f) throw std::runtime_error("cannot create failed-RX dump: " + path);
    for (std::int16_t sample : samples) {
        const std::uint16_t u = static_cast<std::uint16_t>(sample);
        const char bytes[2] = {
            static_cast<char>(u & 0xffu),
            static_cast<char>((u >> 8) & 0xffu)};
        f.write(bytes, sizeof bytes);
    }
    f.close();
    if (!f) throw std::runtime_error("cannot finish failed-RX dump: " + path);
}

inline std::string random_hex(std::size_t nbytes) {
    std::random_device rd;
    std::string out;
    out.reserve(nbytes * 2);
    static const char* h = "0123456789abcdef";
    for (std::size_t i = 0; i < nbytes; ++i) {
        const unsigned b = rd() & 0xFFu;
        out += h[(b >> 4) & 0xF];
        out += h[b & 0xF];
    }
    return out;
}

// Local merge + argmax (identical to the single-SDR runner).
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
        case iqrfrec::Failure::PAYLOAD_RMS_GAIN_NOT_FOUND:
        case iqrfrec::Failure::CFO_OUT_OF_RANGE:
        case iqrfrec::Failure::SRO_OUT_OF_RANGE:
            return "RF_DISTORTS_IQ";
        default:
            return "RF_TRAINING_ESTIMATE_FAILED";
    }
}

// ---------------------------------------------------------------------------
// RX-only negative control (mirrors the single-SDR TX-off noise round WITHOUT any
// TX device: the board has no TX to stop; the control-channel state machine
// guarantees the PC's TX is off at this point).
// ---------------------------------------------------------------------------
struct NegativeControl {
    bool capture_ok = false;
    bool stable = false;
    double rms_min = 0.0;
    double rms_median = 0.0;
    double rms_max = 0.0;
    double stability_ratio = 0.0;
    std::vector<double> window_rms;
    std::vector<std::int16_t> noise;   // median-RMS window (for the rail/clip check)
};

inline NegativeControl run_rx_negative_control(pluto::Device& dev,
                                               std::size_t noise_complex) {
    NegativeControl nc;
    // drain stale DMA with >= kRfDiscardRefills discard refills
    for (std::size_t d = 0; d < iqrfloop_run::kRfDiscardRefills; ++d) {
        dev.recreate_rx_buffer();
        const iio::RawChunk c = dev.read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
        (void)c;
    }
    std::vector<std::vector<std::int16_t>> windows(iqrfloop_run::kRfNoiseWindows);
    nc.window_rms.assign(iqrfloop_run::kRfNoiseWindows, 0.0);
    bool all_ok = true;
    for (std::size_t w = 0; w < iqrfloop_run::kRfNoiseWindows; ++w) {
        dev.recreate_rx_buffer();
        board::RxStats st;
        board::Continuity cont;
        const bool raw_ok = board::capture_contiguous(dev, noise_complex, windows[w], st, cont);
        if (!(raw_ok && cont.ok())) all_ok = false;
        double e = 0.0;
        for (std::int16_t s : windows[w])
            e += static_cast<double>(s) * static_cast<double>(s);
        nc.window_rms[w] = windows[w].empty()
            ? 0.0 : std::sqrt(e / static_cast<double>(windows[w].size()));
    }
    nc.capture_ok = all_ok;
    std::vector<std::size_t> order(iqrfloop_run::kRfNoiseWindows);
    for (std::size_t i = 0; i < order.size(); ++i) order[i] = i;
    std::sort(order.begin(), order.end(), [&](std::size_t a, std::size_t b) {
        return nc.window_rms[a] < nc.window_rms[b];
    });
    nc.rms_min = nc.window_rms[order.front()];
    nc.rms_median = nc.window_rms[order[order.size() / 2]];
    nc.rms_max = nc.window_rms[order.back()];
    nc.stability_ratio = (nc.rms_min > 0.0)
        ? (nc.rms_max / nc.rms_min)
        : (nc.rms_max > 0.0) ? 1.0e18 : 1.0;
    nc.stable = (nc.rms_max == 0.0) ||
                (nc.stability_ratio <= iqrfloop_run::kRfNoiseStableMaxRatio);
    nc.noise = std::move(windows[order[order.size() / 2]]);
    return nc;
}

// ---------------------------------------------------------------------------
// PcTxBoardRx23Fix10RunReport
// ---------------------------------------------------------------------------
struct PcTxBoardRx23Fix10RunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::string model_sha;
    std::string baseline_path;
    std::string tx_control;
    std::uint64_t frozen_files = 0;
    std::uint64_t calib_files = 0;
    std::uint64_t holdout_files = 0;

    bool device_not_found = false;
    std::string error;

    long long requested_rate = 0;
    long long rx_rate = 0;
    double rate_err_hz = 0.0;
    double rate_err_ppm = 0.0;
    bool sample_rate_ok = false;
    bool restore_ok = false;
    std::string restore_report;

    // baseline pairing (identity check on source_index + original_sha256 + class + role)
    std::uint64_t baseline_rows = 0;
    bool baseline_identity_ok = false;
    std::string baseline_identity_report;

    // per-file recovery summary (measured == preamble found; valid == all checks pass)
    std::uint64_t training_estimates = 0;
    std::uint64_t training_measured = 0;
    double training_corr_min = 0.0;
    double training_corr_avg = 0.0;
    double training_residual_max = 0.0;
    double training_residual_avg = 0.0;

    // scoring
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

    // prediction agreement vs the frozen baseline (stable source_index key)
    std::uint64_t r8_prediction_agreement = 0;
    std::uint64_t r8_label_correct = 0;

    // negative control + TX restore (across all samples)
    bool negative_control_ok = false;      // every sample's noise floor stable + clean
    bool tx_restore_ok = false;            // every sample's STOPPED.tx_restore_ok == true

    // CFO capture range (constants) + per-sample aggregate
    double coarse_cfo_search_min_hz = 0.0;
    double coarse_cfo_search_max_hz = 0.0;
    double coarse_cfo_unambiguous_range_hz = 0.0;
    double fine_cfo_range_hz = 0.0;
    bool cfo_all_finite = false;
    bool cfo_all_in_range = false;
    double total_cfo_min_hz = 0.0;
    double total_cfo_max_hz = 0.0;
    double total_cfo_abs_max_hz = 0.0;

    // two-sample (BPSK + 4ASK) mode
    bool two_sample_mode = false;
    std::string diagnostic_classes;
    std::string diagnostic_selected_classes;
    std::uint64_t diagnostic_requested_count = 0;

    // acceptance (measurement only; never a regression PASS)
    double prediction_agreement = 0.0;
    double rf_accuracy = 0.0;
    double accuracy_delta_pp = 0.0;
    bool full_run = false;

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
// run_iq_pc_tx_board_rx_23class_fix10
// ---------------------------------------------------------------------------
inline PcTxBoardRx23Fix10RunReport run_iq_pc_tx_board_rx_23class_fix10(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    PcTxBoardRx23Fix10RunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10 requires "
                                 "--frozen-dir=<D2 artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.baseline_path = board::get_opt(argc, argv, "--baseline", "");
    if (rep.baseline_path.empty())
        throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10 requires "
                                 "--baseline=<route_f_fix9r_exact_baseline.tsv>");
    rep.tx_control = board::get_opt(argc, argv, "--tx-control", "");
    if (rep.tx_control.empty())
        throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10 requires "
                                 "--tx-control=tcp://<PC_IP>:39010");
    const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rx_uri.empty())
        throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10 requires "
                                 "--rx-uri=<board RX device uri>");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 30.0);
    const double target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", kDelayMarginDefault));
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex",
                       iqrfloop_run::kRfNoiseComplexDefault));
    const std::uint64_t max_files =
        board::opt_u64(argc, argv, "--max-files", 0);
    const std::string out_dir = board::get_opt(argc, argv, "--out-dir", "");
    const bool dump_failed_rx = opt_flag(argc, argv, "--dump-failed-rx");
    rep.diagnostic_classes = board::get_opt(argc, argv, "--diagnostic-classes", "");
    const std::uint64_t diagnostic_per_class =
        board::opt_u64(argc, argv, "--diagnostic-per-class", 1);

    // RF safety: both ends must be on the 50-ohm direct cable (the PC enforces its
    // own copy; the board enforces its own).  No antenna / amplifier ever.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-pc-tx-board-rx-23class-fix10 requires --rf-path=direct-cable (50-ohm "
            "SMA coax, no antenna, no amplifier).  Got '" + rf_path + "'.");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-pc-tx-board-rx-23class-fix10 requires --input-kind=radioml-d2-2p56m "
            "(got '" + rep.input_kind + "').");
    if (!rep.diagnostic_classes.empty() && max_files > 0)
        throw std::runtime_error(
            "iq-pc-tx-board-rx-23class-fix10: --diagnostic-classes and --max-files "
            "are mutually exclusive (use --diagnostic-classes=BPSK,4ASK for the "
            "two-sample acceptance).");

    // out-dir auto-create (fail-closed on a real mkdir error)
    if (!out_dir.empty() && ::mkdir(out_dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10: cannot create "
                                 "--out-dir " + out_dir + ": " + std::strerror(errno));

    rep.results_path = join_path(out_dir, "route_f_fix10prep2_pc_tx_board_rx_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_f_fix10prep2_pc_tx_board_rx_confusion_23.csv");
    rep.per_class_path = join_path(out_dir, "route_f_fix10prep2_pc_tx_board_rx_per_class.json");
    rep.summary_path = join_path(out_dir, "route_f_fix10prep2_pc_tx_board_rx_summary.json");
    rep.log_path = join_path(out_dir, "route_f_fix10prep2_pc_tx_board_rx_summary.log");

    rep.class_total.assign(rml23::kDeployedClassCount, 0);
    rep.class_correct.assign(rml23::kDeployedClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml23::kDeployedClassCount) *
                             rml23::kDeployedClassCount, 0);

    // CFO capture-range constants (task book §8)
    rep.coarse_cfo_search_min_hz = iqpctbrx::coarse_cfo_search_min_hz();
    rep.coarse_cfo_search_max_hz = iqpctbrx::coarse_cfo_search_max_hz();
    rep.coarse_cfo_unambiguous_range_hz = iqpctbrx::coarse_cfo_unambiguous_range_hz();
    rep.fine_cfo_range_hz = iqpctbrx::fine_cfo_range_hz();

    const cat::Contract contract = chain::contract_23();

    // ---- load frozen D2 sidecar + exact baseline ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    const std::map<std::uint64_t, iqrffix9r::BaselineRow> baseline =
        iqrffix9r::load_baseline(rep.baseline_path, rml23::kDeployedClassCount);
    rep.baseline_rows = static_cast<std::uint64_t>(baseline.size());

    std::vector<iqdloop::FrozenIq> calib, holdout;
    for (const auto& fz : frozen)
        (fz.is_calibration ? calib : holdout).push_back(fz);

    if (!rep.diagnostic_classes.empty()) {
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
            static_cast<std::uint64_t>(classes.size()) * diagnostic_per_class;
        const iqrffix9r2a::DiagnosticSelection sel =
            iqrffix9r2a::select_diagnostic_holdout(
                holdout, classes, static_cast<std::size_t>(diagnostic_per_class));
        if (!sel.ok)
            throw std::runtime_error(
                "DIAGNOSTIC_SELECTION_FAILED: " + sel.report +
                " (modulation matched from the manifest, over holdout only)");
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
                                 "selection");

    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    rep.calib_files = static_cast<std::uint64_t>(calib.size());
    rep.holdout_files = static_cast<std::uint64_t>(holdout.size());
    rep.full_run = (rep.holdout_files == rep.baseline_rows);
    rep.two_sample_mode = (rep.holdout_files == 2);

    // ---- baseline identity check (fail-closed) ----
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

    std::printf("FIX10PREP2_PC_TX_BOARD_RX input_kind=%s frozen_dir=%s "
                "frozen_files=%llu holdout_files=%llu baseline_rows=%llu "
                "baseline_identity_ok=%d two_sample_mode=%d diagnostic_classes=%s "
                "tx_control=%s rx_uri=%s center_hz=%llu rx_gain=%.3f "
                "rf_tx_target_rms=%.3f out_dir=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.baseline_rows),
                rep.baseline_identity_ok ? 1 : 0, rep.two_sample_mode ? 1 : 0,
                rep.diagnostic_classes.c_str(), rep.tx_control.c_str(),
                rx_uri.c_str(), static_cast<unsigned long long>(center_hz),
                gain_db, target_rms, out_dir.empty() ? "." : out_dir.c_str());
    std::fflush(stdout);

    std::printf("FIX10PREP2_CFO_RANGE coarse_cfo_search_min_hz=%.3f "
                "coarse_cfo_search_max_hz=%.3f coarse_cfo_unambiguous_range_hz=%.3f "
                "fine_cfo_range_hz=%.3f\n",
                rep.coarse_cfo_search_min_hz, rep.coarse_cfo_search_max_hz,
                rep.coarse_cfo_unambiguous_range_hz, rep.fine_cfo_range_hz);
    std::fflush(stdout);

    // ---- device open (RX-only; device-not-found is exit code 2, not a throw) ----
    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(rx_uri));
    } catch (const std::exception& e) {
        rep.device_not_found = true;
        rep.error = e.what();
        return rep;
    }

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    // ---- control-channel session identity ----
    iqpctbrx::SessionIdentity sess;
    sess.session_id = "sess-" + random_hex(8);
    sess.run_nonce = "nonce-" + random_hex(8);
    {
        bool ok = false;
        sess.manifest_sha256 =
            sdr::sha256_hex_file(iqpctbrx::d2_manifest_path(rep.frozen_dir), &ok);
        if (!ok)
            throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10: cannot hash "
                                     "frozen manifest " +
                                     iqpctbrx::d2_manifest_path(rep.frozen_dir));
    }
    sess.input_kind = rep.input_kind;
    sess.sample_rate = iqdloop::kFrozenFsIn;
    sess.center_hz = center_hz;
    sess.target_rms = target_rms;

    iqpctbrx::TcpControlClient client;
    {
        std::string host;
        std::uint16_t port = iqpctbrx::kDefaultPort;
        std::string perr;
        if (!iqpctbrx::parse_tx_control_url(rep.tx_control, host, port, &perr))
            throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10: " + perr);
        client.host = host;
        client.port = port;
        if (!client.connect(&perr))
            throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10: connect to " +
                                     rep.tx_control + " failed: " + perr);
    }

    // ---- HELLO -> HELLO_ACK (PC confirms config + TX off) ----
    {
        std::string perr;
        iqpctbrx::HelloAckInfo ack;
        if (!iqpctbrx::send_hello(client, sess, &perr) ||
            !iqpctbrx::recv_hello_ack(client, sess, ack, &perr)) {
            // Preserve the primary HELLO/recv failure reason; the ABORT best-effort
            // cleanup must NOT overwrite it (a peer that already dropped the link
            // makes send_abort fail with "not connected", masking the real cause).
            const std::string primary_error = perr;
            std::string cleanup_error;
            iqpctbrx::send_abort(client, sess, "hello_failed", &cleanup_error);
            client.close();
            if (!cleanup_error.empty())
                std::printf("FIX10PREP3_HELLO_ABORT_CLEANUP_ERROR=%s (primary=%s)\n",
                            cleanup_error.c_str(), primary_error.c_str());
            throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10: HELLO failed: " +
                                     primary_error);
        }
        std::printf("FIX10PREP2_HELLO_ACK tx_serial=%s tx_uri=%s tx_atten_db=%.3f "
                    "configuration_verified=%d\n",
                    ack.tx_serial.c_str(), ack.tx_uri.c_str(), ack.tx_atten_db,
                    ack.configuration_verified ? 1 : 0);
        std::fflush(stdout);
    }

    bool all_capture_ok = true;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate (RX only): force 2560000, fail-closed abs(delta) <= 5 Hz.
        //      The TX sample rate is the PC's job (reported via READY.readback).
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.rate_err_hz = static_cast<double>(rep.rx_rate - requested);
        rep.rate_err_ppm = 1e6 * rep.rate_err_hz / static_cast<double>(requested);
        rep.sample_rate_ok = std::llabs(rep.rx_rate - requested) <= 5;
        if (!rep.sample_rate_ok) {
            rep.error = "sample_rate_mismatch: requested=" + std::to_string(requested) +
                        " rx=" + std::to_string(rep.rx_rate) +
                        " (abs(actual-requested) must be <= 5 Hz)";
            return rep;
        }

        // ---- RX config: LO + manual gain ----
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_rx_lo(static_cast<long long>(center_hz));
            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(gain_db);
        }
        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        std::printf("FIX10PREP2_RX_FORMAT %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);
        const int rx_pos_rail = iqdloop_sync::rail_positive(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));
        const int rx_neg_rail = iqdloop_sync::rail_negative(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));

        std::uint64_t global_frame_id = 0;
        std::vector<iqrfrec::Failure> file_failures;
        double corr_sum = 0.0;
        double residual_sum = 0.0;
        double corr_min = 1.0;
        double residual_max = 0.0;
        std::uint64_t measured_count = 0;
        std::uint64_t cfo_measured = 0;
        bool any_cfo_nonfinite = false;
        bool any_cfo_out_of_range = false;
        double total_cfo_min = std::numeric_limits<double>::infinity();
        double total_cfo_max = -std::numeric_limits<double>::infinity();
        bool neg_any_fail = false;
        bool tx_restore_any_fail = false;

        // ---- single pass over the selected holdout (per-file recovery, no retry) ----
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("iq-pc-tx-board-rx-23class-fix10: cannot open " +
                                     rep.results_path);
        results << "file_name\tsource_index\traw24_class\tdeployed23_class\t"
                << "modulation\tsnr_db\tsplit_role\tvalid\traw24_pred\t"
                << "merged23_pred\tcorrect\ttraining_corr\ttraining_residual\t"
                << "timing_offset\tgain_mag\tphase_deg\tcoarse_cfo_hz\tfine_cfo_hz\t"
                << "total_cfo_hz\tsro_ppm\trf_verdict\n";

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;

            std::printf("FIX10PREP2_FILE file=%s input_kind=%s source_index=%lld "
                        "source_class=%d deployed_class=%d modulation=%s "
                        "frozen_complex=%llu split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(),
                        static_cast<long long>(fz.source_index), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        fz.split_role.c_str());
            std::fflush(stdout);

            // board's INDEPENDENT burst expectation (the provenance the PC must match);
            // fix10canonical assembles the training frame from the aarch64-frozen
            // components so the board's expectation is byte-identical to the PC's TX.
            const iqpctbrx::TxBurstBuild expected =
                fix10canonical::buildTxBurstFromFrozen(
                    fz.path, fz.complex_count, fz.sha256, target_rms);
            const iqpctbrx::SampleIdentity smp{
                fz.source_index, fz.file_name, expected.payload_sha_pre};

            std::string ctrl_err;
            iqpctbrx::ControlOutcome ctrl = iqpctbrx::ControlOutcome::Ok;
            std::string rf_verdict = "INSUFFICIENT_EVIDENCE";
            bool rx_clipped = false;
            bool gate_ok = false;
            iqdual23fix10::CoarseCfoRecovery ccr;
            double total_cfo_hz = 0.0;
            double coarse_cfo_hz = 0.0;
            double fine_cfo_hz = 0.0;
            bool cfo_finite = false;
            bool cfo_in_range = false;
            iqpctbrx::PreparedInfo prepared;
            iqpctbrx::ReadyInfo ready;
            iqpctbrx::StoppedInfo stopped;
            bool noise_clipped = false;

            // ---- 1. negative control (TX off, guaranteed by the state machine) ----
            const NegativeControl neg = run_rx_negative_control(*dev, noise_complex);
            for (std::size_t k = 0; k + 1 < neg.noise.size(); k += 2) {
                const int i = neg.noise[k];
                const int q = neg.noise[k + 1];
                if (i >= rx_pos_rail || i <= rx_neg_rail ||
                    q >= rx_pos_rail || q <= rx_neg_rail) {
                    noise_clipped = true;
                    break;
                }
            }
            const bool neg_pass = neg.capture_ok && !noise_clipped && neg.stable;
            if (!neg_pass) neg_any_fail = true;
            all_capture_ok = all_capture_ok && neg.capture_ok;
            std::printf("FIX10PREP2_NEGATIVE_CONTROL file=%s refills=%zu windows=%zu "
                        "rms_min=%.4f rms_median=%.4f rms_max=%.4f stability_ratio=%.4f "
                        "noise_stable=%d noise_clipped=%d pass=%d\n",
                        fz.file_name.c_str(), iqrfloop_run::kRfDiscardRefills,
                        iqrfloop_run::kRfNoiseWindows, neg.rms_min, neg.rms_median,
                        neg.rms_max, neg.stability_ratio, neg.stable ? 1 : 0,
                        noise_clipped ? 1 : 0, neg_pass ? 1 : 0);
            std::fflush(stdout);

            // ---- 2. PREPARE -> PREPARED (PC builds + verifies the burst, no TX).
            //      Provenance is NOT checked here: PREPARED carries only the PC's
            //      build claims; the authoritative check runs at READY via
            //      check_readiness_provenance(expected, prepared, ready, tol). ----
            if (!iqpctbrx::send_prepare(client, sess, smp, &ctrl_err)) {
                ctrl = iqpctbrx::ControlOutcome::PrepareFailed;
            } else if (!iqpctbrx::recv_prepared(client, sess, smp, prepared, &ctrl_err)) {
                ctrl = iqpctbrx::ControlOutcome::PreparedRejected;
            }

            // ---- 3. START -> READY (PC authorized to transmit; verifies read-backs) ----
            if (ctrl == iqpctbrx::ControlOutcome::Ok) {
                if (!iqpctbrx::send_start(client, sess, smp, &ctrl_err))
                    ctrl = iqpctbrx::ControlOutcome::StartFailed;
                else if (!iqpctbrx::recv_ready(client, sess, smp, ready, &ctrl_err))
                    ctrl = iqpctbrx::ControlOutcome::ReadyRejected;
            }

            // ---- 4. capture RX while the PC's TX is cyclic (>= 2 periods + margin) ----
            bool capture_ok = false;
            board::RxStats rxst;
            board::Continuity rxcont;
            std::vector<std::int16_t> rx_int16;
            if (ctrl == iqpctbrx::ControlOutcome::Ok) {
                // verify READY provenance (payload/burst SHA + tx_scale) vs the board's
                // independent rebuild before trusting the capture.
                const iqpctbrx::ProvenanceCheck pc =
                    iqpctbrx::check_readiness_provenance(expected, prepared, ready, 1e-6);
                if (!pc.ok) {
                    ctrl = iqpctbrx::ControlOutcome::ReadyRejected;
                    ctrl_err = pc.report;
                } else {
                    dev->recreate_rx_buffer();
                    {
                        const iio::RawChunk c =
                            dev->read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
                        (void)c;
                    }
                    const std::size_t capture = iqrflayout::capture_complex(delay_margin);
                    {
                        m22::StageTiming::Timer t(timing, m22::StageId::RxRefill);
                        const bool raw_ok =
                            board::capture_contiguous(*dev, capture, rx_int16, rxst, rxcont);
                        capture_ok = raw_ok && rxcont.ok();
                    }
                    if (!capture_ok)
                        ctrl = iqpctbrx::ControlOutcome::CaptureFailed;
                    all_capture_ok = all_capture_ok && capture_ok;
                }
            }

            // ---- 5. CAPTURED -> STOPPED (PC stops TX + restores its TX state) ----
            if (ctrl == iqpctbrx::ControlOutcome::Ok) {
                if (!iqpctbrx::send_captured(client, sess, smp, &ctrl_err))
                    ctrl = iqpctbrx::ControlOutcome::CapturedFailed;
                else if (!iqpctbrx::recv_stopped(client, sess, stopped, &ctrl_err))
                    ctrl = iqpctbrx::ControlOutcome::StoppedFailed;
            }
            if (!stopped.tx_restore_ok) tx_restore_any_fail = true;

            if (ctrl != iqpctbrx::ControlOutcome::Ok) {
                std::string reason = ctrl_err.empty()
                    ? iqpctbrx::control_outcome_token(ctrl) : ctrl_err;
                iqpctbrx::send_abort(client, sess, reason, &ctrl_err);
                client.close();
                rep.error = "control_channel_failed:" +
                            std::string(iqpctbrx::control_outcome_token(ctrl)) +
                            " " + reason;
                break;
            }

            // ---- 6. recover (coarse CFO -> fine sync/gain) ----
            const std::vector<std::complex<double>> rx =
                iqrftrain::deinterleave(rx_int16);
            iqrfrec::EstimateConfig rec_cfg;
            rec_cfg.min_corr = kFidelityTrainingCorrMin;
            rec_cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;
            // The fine CFO must be a SMALL residual after the robust coarse CFO: its
            // unambiguous range is +/-fs/(2*kTailStart) ~ +/-21.7 Hz.  A residual
            // beyond that means the true dual-SDR CFO exceeded the coarse range
            // (+/-625 Hz) -- an infra failure, never a widened gate.
            rec_cfg.max_cfo_hz = iqpctbrx::fine_cfo_range_hz();
            rec_cfg.max_sro_ppm = 30.0;
            rec_cfg.search_limit = 0;   // full capture
            rec_cfg.payload_tx_target_rms = target_rms;
            ccr = iqdual23fix10::recover_payload_with_coarse_cfo(
                rx, rec_cfg, expected.tx_scale);
            coarse_cfo_hz = ccr.coarse_cfo_hz;
            fine_cfo_hz = ccr.rec.cfo_hz;
            total_cfo_hz = coarse_cfo_hz + fine_cfo_hz;
            cfo_finite = std::isfinite(coarse_cfo_hz) && std::isfinite(fine_cfo_hz) &&
                         std::isfinite(total_cfo_hz);
            const bool coarse_in_range =
                std::fabs(coarse_cfo_hz) <= rep.coarse_cfo_unambiguous_range_hz + 1e-9;
            const bool fine_in_range =
                std::fabs(fine_cfo_hz) <= rep.fine_cfo_range_hz + 1e-9;
            cfo_in_range = cfo_finite && coarse_in_range && fine_in_range;
            if (!cfo_finite) {
                any_cfo_nonfinite = true;
            } else {
                ++cfo_measured;
                if (total_cfo_hz < total_cfo_min) total_cfo_min = total_cfo_hz;
                if (total_cfo_hz > total_cfo_max) total_cfo_max = total_cfo_hz;
                if (!cfo_in_range) any_cfo_out_of_range = true;
            }
            if (cfo_finite && std::fabs(total_cfo_hz) > rep.total_cfo_abs_max_hz)
                rep.total_cfo_abs_max_hz = std::fabs(total_cfo_hz);

            std::printf("FIX10PREP2_CFO file=%s coarse_cfo_search_min_hz=%.3f "
                        "coarse_cfo_search_max_hz=%.3f coarse_cfo_unambiguous_range_hz=%.3f "
                        "fine_cfo_range_hz=%.3f coarse_cfo_hz=%.3f fine_cfo_hz=%.3f "
                        "total_cfo_hz=%.3f fractional_timing_samples=%.6f "
                        "fractional_corr_before=%.6f fractional_corr_after=%.6f "
                        "payload_fractional_corr_before=%.6f "
                        "payload_fractional_corr_after=%.6f "
                        "payload_best_fractional_timing_samples=%.6f "
                        "payload_best_fractional_corr=%.6f "
                        "payload_best_fractional_preamble_corr=%.6f "
                        "cfo_finite=%d cfo_in_range=%d\n",
                        fz.file_name.c_str(), rep.coarse_cfo_search_min_hz,
                        rep.coarse_cfo_search_max_hz, rep.coarse_cfo_unambiguous_range_hz,
                        rep.fine_cfo_range_hz, coarse_cfo_hz, fine_cfo_hz, total_cfo_hz,
                        ccr.fractional_timing_samples, ccr.fractional_corr_before,
                        ccr.fractional_corr_after,
                        ccr.payload_fractional_corr_before,
                        ccr.payload_fractional_corr_after,
                        ccr.payload_best_fractional_timing_samples,
                        ccr.payload_best_fractional_corr,
                        ccr.payload_best_fractional_preamble_corr,
                        cfo_finite ? 1 : 0, cfo_in_range ? 1 : 0);
            std::fflush(stdout);

            // ---- 7. fidelity gate (RX-only; the TX infra is the PC's job) ----
            // RX clip: any railed sample in the burst capture.
            rx_clipped = false;
            for (std::size_t k = 0; k + 1 < rx_int16.size(); k += 2) {
                const int i = rx_int16[k];
                const int q = rx_int16[k + 1];
                if (i >= rx_pos_rail || i <= rx_neg_rail ||
                    q >= rx_pos_rail || q <= rx_neg_rail) {
                    rx_clipped = true;
                    break;
                }
            }
            if (!neg.capture_ok || noise_clipped) {
                rf_verdict = "RF_NEGATIVE_CONTROL_FAIL";
            } else if (!neg.stable) {
                rf_verdict = "RF_NEGATIVE_CONTROL_UNSTABLE";
            } else if (expected.clip_pre || expected.clip_post) {
                rf_verdict = "RF_TX_CLIPPED";
            } else if (rx_clipped) {
                rf_verdict = "RF_RX_CLIPPED";
            } else if (!ccr.rec.valid) {
                rf_verdict = failure_rf_verdict(ccr.rec.failure);
            } else if (!cfo_in_range) {
                rf_verdict = "RF_CFO_OUT_OF_RANGE";
            } else {
                rf_verdict = "RF_PRESERVES_IQ";
            }

            const iqrfrec::PerFileRecovery& rec = ccr.rec;
            std::printf("FIX10PREP2_RECOVERY file=%s computed=%d valid=%d failure=%s "
                        "timing=%zu gain_mag=%.6f phase_deg=%.3f fine_cfo_hz=%.3f "
                        "sro_ppm=%.3f training_corr=%.6f training_residual=%.6f "
                        "payload_gain_mag=%.6f payload_rms_gain_mag=%.6f "
                        "payload_phase_deg=%.3f payload_training_corr=%.6f "
                        "payload_training_residual=%.6f fidelity=%s rx_clipped=%d\n",
                        fz.file_name.c_str(), rec.computed ? 1 : 0, rec.valid ? 1 : 0,
                        iqrfrec::failure_token(rec.failure), rec.timing_offset,
                        rec.gain_mag, rec.phase_deg, rec.cfo_hz, rec.sro_ppm,
                        rec.training_corr, rec.training_residual, rec.payload_gain_mag,
                        rec.payload_rms_gain_mag, rec.payload_phase_deg,
                        rec.payload_training_corr, rec.payload_training_residual,
                        rf_verdict.c_str(), rx_clipped ? 1 : 0);
            std::fflush(stdout);

            if (expected.clip_pre || expected.clip_post) rep.any_tx_clip = true;
            if (rx_clipped) rep.any_rx_clip = true;
            file_failures.push_back(rec.failure);
            if (rec.computed) {
                corr_sum += rec.training_corr;
                residual_sum += rec.training_residual;
                if (measured_count == 0) {
                    corr_min = rec.training_corr;
                    residual_max = rec.training_residual;
                } else {
                    corr_min = std::min(corr_min, rec.training_corr);
                    residual_max = std::max(residual_max, rec.training_residual);
                }
                ++measured_count;
            }

            gate_ok = (rf_verdict == "RF_PRESERVES_IQ");
            if (!gate_ok) {
                if (dump_failed_rx) {
                    const std::string stem = "failed_rx_" +
                        std::to_string(fz.source_index);
                    const std::string raw_path = join_path(out_dir, stem + ".ci16");
                    const std::string meta_path = join_path(out_dir, stem + ".json");
                    write_ci16_le(raw_path, rx_int16);
                    bool raw_sha_ok = false;
                    const std::string raw_sha =
                        sdr::sha256_hex_file(raw_path, &raw_sha_ok);
                    if (!raw_sha_ok)
                        throw std::runtime_error("cannot hash failed-RX dump: " + raw_path);
                    std::ofstream meta(meta_path, std::ios::binary | std::ios::trunc);
                    if (!meta)
                        throw std::runtime_error("cannot create failed-RX metadata: " +
                                                 meta_path);
                    meta << "{\n"
                         << "  \"format\":\"interleaved_ci16_le\",\n"
                         << "  \"source_index\":" << fz.source_index << ",\n"
                         << "  \"file_name\":\"" << json_escape(fz.file_name) << "\",\n"
                         << "  \"modulation\":\"" << json_escape(fz.modulation) << "\",\n"
                         << "  \"complex_count\":" << (rx_int16.size() / 2) << ",\n"
                         << "  \"byte_count\":" << (rx_int16.size() * 2) << ",\n"
                         << "  \"sha256\":\"" << raw_sha << "\",\n"
                         << "  \"failure\":\""
                         << iqrfrec::failure_token(rec.failure) << "\",\n"
                         << "  \"coarse_cfo_hz\":" << coarse_cfo_hz << ",\n"
                         << "  \"fine_cfo_hz\":" << fine_cfo_hz << ",\n"
                         << "  \"fractional_timing_samples\":"
                         << ccr.fractional_timing_samples << ",\n"
                         << "  \"payload_best_fractional_timing_samples\":"
                         << ccr.payload_best_fractional_timing_samples << ",\n"
                         << "  \"payload_best_fractional_corr\":"
                         << ccr.payload_best_fractional_corr << ",\n"
                         << "  \"payload_training_residual\":"
                         << rec.payload_training_residual << "\n"
                         << "}\n";
                    meta.close();
                    if (!meta)
                        throw std::runtime_error("cannot finish failed-RX metadata: " +
                                                 meta_path);
                    std::printf("FIX10PREP3_FAILED_RX_DUMP file=%s raw=%s metadata=%s "
                                "sha256=%s\n",
                                fz.file_name.c_str(), raw_path.c_str(), meta_path.c_str(),
                                raw_sha.c_str());
                    std::fflush(stdout);
                }
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons[rf_verdict];
                std::printf("FIX10PREP2_FILE file=%s classification=SKIPPED "
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
                        << coarse_cfo_hz << "\t" << fine_cfo_hz << "\t"
                        << total_cfo_hz << "\t" << rec.sro_ppm << "\t"
                        << rf_verdict << "\n";
                continue;
            }

            // ---- 8. chain -> D2 restore -> reference window -> NPU24 -> merge23 ----
            const std::vector<std::complex<double>> payload = ccr.payload;
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
            const std::vector<float> ref =
                iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                               fz.recovered_tensor_sha256);
            const iqdloop::ClassificationWindow cw =
                iqdloop::select_classification_window(recovered_stream, ref);
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
                        << coarse_cfo_hz << "\t" << fine_cfo_hz << "\t"
                        << total_cfo_hz << "\t" << rec.sro_ppm << "\t"
                        << "RF_NO_VALID_WINDOW\n";
                continue;
            }

            const auto t0 = Clock::now();
            std::vector<float> raw24;
            npu.infer(cw.aligned_tensor.data(), raw24);
            const double classify_us = elapsed_us(t0);
            timing.record(m22::StageId::NpuInfer, classify_us);

            const std::vector<float> m23 = merge23(raw24);
            const int raw_top = argmax_of(raw24);
            const int merged_top = argmax_of(m23);
            const bool correct = (merged_top == fz.deployed_class);

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
            std::printf("FIX10PREP2_CLASSIFY file=%s baseline_pred=%d rf_pred=%d "
                        "source_label=%d prediction_agreement=%d label_correct=%d\n",
                        fz.file_name.c_str(), baseline_pred, merged_top, fz.source_class,
                        prediction_agreement ? 1 : 0, label_correct ? 1 : 0);
            std::fflush(stdout);

            ++global_frame_id;
            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;
            r.source = "iq_pc_tx_board_rx_23class_fix10";
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
                    << coarse_cfo_hz << "\t" << fine_cfo_hz << "\t"
                    << total_cfo_hz << "\t" << rec.sro_ppm << "\t"
                    << rf_verdict << "\n";

            std::printf("FIX10PREP2_FILE file=%s frames=1 correct=%d deployed=%d "
                        "source=%d raw24_pred=%d merged23_pred=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.deployed_class,
                        fz.source_class, raw_top, merged_top);
            std::fflush(stdout);
        }
        results.close();

        // ---- aggregate training + CFO + control evidence ----
        rep.training_measured = measured_count;
        {
            std::uint64_t valid_count = 0;
            for (const auto f : file_failures)
                if (f == iqrfrec::Failure::NONE) ++valid_count;
            rep.training_estimates = valid_count;
        }
        if (measured_count > 0) {
            rep.training_corr_avg = corr_sum / static_cast<double>(measured_count);
            rep.training_residual_avg = residual_sum / static_cast<double>(measured_count);
            rep.training_corr_min = corr_min;
            rep.training_residual_max = residual_max;
        }
        rep.cfo_all_finite = (cfo_measured > 0) && !any_cfo_nonfinite;
        rep.cfo_all_in_range = (cfo_measured > 0) && !any_cfo_nonfinite &&
                               !any_cfo_out_of_range;
        rep.total_cfo_min_hz = (cfo_measured > 0) ? total_cfo_min : 0.0;
        rep.total_cfo_max_hz = (cfo_measured > 0) ? total_cfo_max : 0.0;
        rep.negative_control_ok = !neg_any_fail;
        rep.tx_restore_ok = !tx_restore_any_fail;

        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // Always close the control channel (the PC treats a clean close as session end).
    if (client.connected()) {
        std::string perr;
        iqpctbrx::send_abort(client, sess, "board_done", &perr);
        client.close();
    }

    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- acceptance measurement (never a regression PASS) ----
    const double overall_acc = rep.total_valid > 0
        ? static_cast<double>(rep.total_correct) /
          static_cast<double>(rep.total_valid) : 0.0;
    rep.prediction_agreement = overall_acc;
    rep.rf_accuracy = overall_acc;
    rep.accuracy_delta_pp = 100.0 * (rep.rf_accuracy - 0.0);   // no fixed baseline pp here

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
        const std::string measurement_token =
            (rep.error.empty() && rep.sample_rate_ok) ? kMeasurementComplete
                                                      : kMeasurementIncomplete;
        f << "{\n";
        f << "  \"token\":\"FIX10PREP2_MEASUREMENT\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"frozen_dir\":\"" << json_escape(rep.frozen_dir) << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"baseline_path\":\"" << json_escape(rep.baseline_path) << "\",\n";
        f << "  \"tx_control\":\"" << json_escape(rep.tx_control) << "\",\n";
        f << "  \"baseline_rows\":" << rep.baseline_rows << ",\n";
        f << "  \"baseline_identity_ok\":" << (rep.baseline_identity_ok ? "true" : "false") << ",\n";
        f << "  \"holdout_files\":" << rep.holdout_files << ",\n";
        f << "  \"two_sample_mode\":" << (rep.two_sample_mode ? "true" : "false") << ",\n";
        if (rep.two_sample_mode) {
            f << "  \"diagnostic_classes\":\"" << json_escape(rep.diagnostic_classes) << "\",\n";
            f << "  \"diagnostic_selected_classes\":\""
              << json_escape(rep.diagnostic_selected_classes) << "\",\n";
        }
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"rf_excluded\":" << rep.rf_excluded << ",\n";
        f << "  \"prediction_agreement\":" << rep.r8_prediction_agreement << ",\n";
        f << "  \"label_correct\":" << rep.r8_label_correct << ",\n";
        f << "  \"training_estimates\":" << rep.training_estimates << ",\n";
        f << "  \"training_measured\":" << rep.training_measured << ",\n";
        f << "  \"training_corr_min\":" << rep.training_corr_min << ",\n";
        f << "  \"training_corr_avg\":" << rep.training_corr_avg << ",\n";
        f << "  \"training_residual_max\":" << rep.training_residual_max << ",\n";
        f << "  \"training_residual_avg\":" << rep.training_residual_avg << ",\n";
        f << "  \"negative_control_ok\":" << (rep.negative_control_ok ? "true" : "false") << ",\n";
        f << "  \"tx_restore_ok\":" << (rep.tx_restore_ok ? "true" : "false") << ",\n";
        f << "  \"rx_restore_ok\":" << (rep.restore_ok ? "true" : "false") << ",\n";
        f << "  \"coarse_cfo_search_min_hz\":" << rep.coarse_cfo_search_min_hz << ",\n";
        f << "  \"coarse_cfo_search_max_hz\":" << rep.coarse_cfo_search_max_hz << ",\n";
        f << "  \"coarse_cfo_unambiguous_range_hz\":" << rep.coarse_cfo_unambiguous_range_hz << ",\n";
        f << "  \"fine_cfo_range_hz\":" << rep.fine_cfo_range_hz << ",\n";
        f << "  \"cfo_all_finite\":" << (rep.cfo_all_finite ? "true" : "false") << ",\n";
        f << "  \"cfo_all_in_range\":" << (rep.cfo_all_in_range ? "true" : "false") << ",\n";
        f << "  \"total_cfo_min_hz\":" << rep.total_cfo_min_hz << ",\n";
        f << "  \"total_cfo_max_hz\":" << rep.total_cfo_max_hz << ",\n";
        f << "  \"total_cfo_abs_max_hz\":" << rep.total_cfo_abs_max_hz << ",\n";
        f << "  \"any_tx_clip\":" << (rep.any_tx_clip ? "true" : "false") << ",\n";
        f << "  \"any_rx_clip\":" << (rep.any_rx_clip ? "true" : "false") << ",\n";
        f << "  \"sample_rate_ok\":" << (rep.sample_rate_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rate\":" << rep.requested_rate << ",\n";
        f << "  \"rx_rate\":" << rep.rx_rate << ",\n";
        f << "  \"rf_path\":\"direct-cable\"\n";
        f << "}\n";
    }

    // Summary log.
    {
        std::ofstream f(rep.log_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.log_path);
        const std::string measurement_token =
            (rep.error.empty() && rep.sample_rate_ok) ? kMeasurementComplete
                                                      : kMeasurementIncomplete;
        f << "token=FIX10PREP2_MEASUREMENT measurement=" << measurement_token
          << " holdout=" << rep.holdout_files
          << " scored=" << rep.scored
          << " rf_excluded=" << rep.rf_excluded
          << " prediction_agreement=" << rep.r8_prediction_agreement
          << "/" << rep.holdout_files
          << " training_estimates=" << rep.training_estimates
          << "/" << rep.holdout_files
          << " negative_control=" << (rep.negative_control_ok ? "PASS" : "FAIL")
          << " tx_restore_ok=" << (rep.tx_restore_ok ? 1 : 0)
          << " rx_restore_ok=" << (rep.restore_ok ? 1 : 0)
          << " cfo_finite=" << (rep.cfo_all_finite ? 1 : 0)
          << " cfo_in_range=" << (rep.cfo_all_in_range ? 1 : 0)
          << " total_cfo_abs_max_hz=" << rep.total_cfo_abs_max_hz
          << " 4ask=" << rep.ask4_correct << "/" << rep.ask4_total
          << "\n";
    }

    // ---- the two-sample / measurement result line (the §13-B fields the operator
    //      reads; never a regression PASS token) ----
    if (rep.two_sample_mode) {
        std::printf("FIX10PREP2_TWO_SAMPLE_RESULT scored=%llu rf_excluded=%llu "
                    "prediction_agreement=%llu/%llu tx_restore_ok=%d rx_restore_ok=%d "
                    "negative_control=%s cfo_finite=%d cfo_in_range=%d "
                    "training_estimate_valid=%llu/%llu\n",
                    static_cast<unsigned long long>(rep.scored),
                    static_cast<unsigned long long>(rep.rf_excluded),
                    static_cast<unsigned long long>(rep.r8_prediction_agreement),
                    static_cast<unsigned long long>(rep.holdout_files),
                    rep.tx_restore_ok ? 1 : 0, rep.restore_ok ? 1 : 0,
                    rep.negative_control_ok ? "PASS" : "FAIL",
                    rep.cfo_all_finite ? 1 : 0, rep.cfo_all_in_range ? 1 : 0,
                    static_cast<unsigned long long>(rep.training_estimates),
                    static_cast<unsigned long long>(rep.holdout_files));
    } else {
        std::printf("FIX10PREP2_MEASUREMENT_RESULT scored=%llu rf_excluded=%llu "
                    "prediction_agreement=%llu/%llu training_estimate_valid=%llu/%llu "
                    "negative_control=%s cfo_finite=%d cfo_in_range=%d "
                    "tx_restore_ok=%d rx_restore_ok=%d\n",
                    static_cast<unsigned long long>(rep.scored),
                    static_cast<unsigned long long>(rep.rf_excluded),
                    static_cast<unsigned long long>(rep.r8_prediction_agreement),
                    static_cast<unsigned long long>(rep.holdout_files),
                    static_cast<unsigned long long>(rep.training_estimates),
                    static_cast<unsigned long long>(rep.holdout_files),
                    rep.negative_control_ok ? "PASS" : "FAIL",
                    rep.cfo_all_finite ? 1 : 0, rep.cfo_all_in_range ? 1 : 0,
                    rep.tx_restore_ok ? 1 : 0, rep.restore_ok ? 1 : 0);
    }
    std::fflush(stdout);

    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          !frozen.empty() && all_capture_ok &&
                          rep.baseline_identity_ok;
    // Two-sample / measurement acceptance (issue #3): every selected holdout sample
    // must be scored, none RF-excluded, all predictions agree with the frozen
    // baseline, the negative control passed, both TX and RX restored, every CFO
    // finite and in-range, and every training estimate valid -- never merely
    // "some sample scored".
    const bool scoring_ok = (rep.scored == rep.holdout_files) &&
                            (rep.rf_excluded == 0) &&
                            (rep.r8_prediction_agreement == rep.holdout_files);
    const bool control_ok = rep.negative_control_ok && rep.tx_restore_ok &&
                            rep.restore_ok;
    const bool cfo_ok = rep.cfo_all_finite && rep.cfo_all_in_range;
    const bool training_ok = (rep.training_estimates == rep.holdout_files);
    rep.functional_pass = infra_ok && scoring_ok && control_ok && cfo_ok &&
                          training_ok;

    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " baseline_rows=" + std::to_string(rep.baseline_rows) +
                         " scored=" + std::to_string(rep.scored) +
                         " rf_excluded=" + std::to_string(rep.rf_excluded) +
                         " prediction_agreement=" +
                             std::to_string(rep.r8_prediction_agreement) +
                         "/" + std::to_string(rep.holdout_files) +
                         " training_estimates=" + std::to_string(rep.training_estimates) +
                         " negative_control=" +
                             (rep.negative_control_ok ? "PASS" : "FAIL") +
                         " tx_restore_ok=" + (rep.tx_restore_ok ? "1" : "0") +
                         " rx_restore_ok=" + (rep.restore_ok ? "1" : "0") +
                         " cfo_finite=" + (rep.cfo_all_finite ? "1" : "0") +
                         " cfo_in_range=" + (rep.cfo_all_in_range ? "1" : "0") +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " rf_path=direct-cable";
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

}  // namespace iqpcbtrx23fix10
