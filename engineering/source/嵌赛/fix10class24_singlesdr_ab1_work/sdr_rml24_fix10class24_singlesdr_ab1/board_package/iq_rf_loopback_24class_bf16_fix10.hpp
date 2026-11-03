#pragma once

// iq_rf_loopback_24class_bf16_fix10.hpp -- fix10class24-singlesdr-ab1 (task book
// 39e5): the SINGLE-SDR 24-class BF16 self-loopback A/B runner.  ONE Pluto does
// BOTH the local TX (cyclic canonical burst) and the RX capture over the external
// 50-ohm coax (loopback=0), sharing the SAME LO and clock.
//
// PURPOSE: isolate whether the dual-SDR-specific path (independent clock + two
// analog frontends + PC TX over TCP) is the dominant contributor to the dual-SDR
// 18/24 forced result.  Everything EXCEPT the topology swap is held strictly
// identical to the dual-SDR rxrecovery1 runner
// (iq_pc_tx_board_rx_24class_bf16_fix10.hpp):
//
//   * the SAME recovery core iqdual23fix10::recover_payload_with_coarse_cfo (coarse
//     CFO pre-rotation, fractional timing, three-pass estimate, apply with
//     wide-linear compensation) -- the coarse CFO is naturally ~0 on a shared clock,
//     but the code path is byte-for-byte the dual-SDR path, NOT the old single-SDR
//     estimate+apply scalar path.
//   * the SAME rec_cfg, the SAME bounded recapture (max 3 attempts, retry only on
//     PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH), the SAME final-capture selection (last
//     attempt), the SAME 7-branch fidelity gate, the SAME 0.100 residual gate.
//   * the SAME BF16 raw24 model / clean24_smoke samples / canonical frame / RX
//     gain 35 dB / RX BW 18 MHz / center 2.4 GHz / 2.56 Msps / target RMS 2048.
//
// The ONLY allowed differences: TX+RX from two SDRs -> one SDR; the local TX
// replaces the PC TX (TCP control -> local cyclic transmit), so the runner OWNS the
// TX and must stop it on every exit path; TX BW/LO/atten/loopback are written and
// read back fail-closed.
//
// It is a MEASUREMENT (FIX10CLASS24_BF16_SINGLESDR_* tokens), never a regression
// PASS.  It reports FOUR metrics: coverage, gated accuracy, end-to-end accuracy, and
// forced raw24 accuracy.  The last is HYBRID evidence -- gated samples are board-NPU
// judgements and gate-refused samples are Host-BF16 forced classifications -- so this
// runner prints `forced_raw24_accuracy=PENDING` and the numeric value is produced by
// the offline aggregate script (aggregate_fix10class24_singlesdr_ab1_forced.py) as
// HYBRID_BOARD_GATED_PLUS_HOST_FORCED, never a pure board-NPU 24-class accuracy.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_per_frame_recovery.hpp"        // iqrfrec (shim -> iq_rf_sync_recovery.hpp)
#include "iq_rf_frame_layout.hpp"
#include "iq_rf_loopback_transfer.hpp"         // iqrfloop_run::kRfDiscard* / kRfNoise*
#include "iq_dual_sdr_coarse_cfo_recovery.hpp" // iqdual23fix10::recover_payload_with_coarse_cfo
#include "iq_rf_fix9r2a_diagnostic.hpp"        // iqrffix9r2a::select_diagnostic_holdout
#include "iq_pc_tx_board_rx_transfer_fix10.hpp"// iqpctbrx::TxBurstBuild + CFO range fns
#include "iq_fix10_canonical_frame.hpp"         // fix10canonical::buildTxBurstFromFrozen
#include "iq_fix10class24_failed_rx_dump.hpp"    // iqfix10dump::dump_failed_rx_sample
#include "iq_rf_loopback_transfer_24class_bf16_fix10.hpp" // single-SDR local TX transfer
#include "rml24_raw.hpp"                        // rml24::raw24_predict (NO merge)
#include "rml24_bf16_baseline.hpp"              // rml24bf16::load_baseline / BaselineRow
#include "rf_fix_helpers.hpp"                   // rf_fix::rf_readback_close (bw fail-closed)
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/device_state_guard.hpp"

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
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqrfloop24bf16 {

using Clock = std::chrono::steady_clock;

// fix10class24-singlesdr-ab1 single-SDR tokens (measurement, never a PASS).
constexpr const char* kMeasurementComplete =
    "FIX10CLASS24_BF16_SINGLESDR_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete =
    "FIX10CLASS24_BF16_SINGLESDR_MEASUREMENT_INCOMPLETE";

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

inline int argmax_of(const std::vector<float>& v) {
    if (v.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(v.size()); ++i)
        if (v[i] > v[best]) best = i;
    return best;
}

// Verbatim from iqpcbtrx24bf16fix10::failure_rf_verdict (same recovery-core failure
// -> RF verdict mapping; the fidelity gate is reproduced exactly below).
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
// Single-SDR negative control: the runner OWNS the TX, so it must stop TX and
// CONFIRM it stopped before measuring the noise floor.  The discard-refill / noise-
// window / stability logic is otherwise byte-for-byte the dual-SDR runner's
// run_rx_negative_control (iq_pc_tx_board_rx_24class_bf16_fix10.hpp:170-220).
// ---------------------------------------------------------------------------
struct NegativeControl {
    bool capture_ok = false;
    bool stable = false;
    bool tx_stopped_ok = false;
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
    // single-SDR: ensure TX is off before measuring the RX noise floor.
    dev.tx_stop();
    nc.tx_stopped_ok = !dev.tx_running();
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
// Singlesdr24Bf16Fix10RunReport
// ---------------------------------------------------------------------------
struct Singlesdr24Bf16Fix10RunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::string model_sha;
    std::string baseline_path;
    std::string mode;                    // "short2" | "full24"
    std::uint64_t frozen_files = 0;
    std::uint64_t calib_files = 0;
    std::uint64_t holdout_files = 0;

    bool device_not_found = false;
    std::string error;

    long long requested_rate = 0;
    long long rx_rate = 0;
    long long tx_rate = 0;
    double rate_err_hz = 0.0;
    double tx_rate_err_hz = 0.0;
    double rate_err_ppm = 0.0;
    bool sample_rate_ok = false;

    // RX frontend write-then-readback (fail-closed).
    long long requested_rx_bw = 0;
    long long rx_bw_readback = 0;
    bool rx_bw_ok = false;
    double requested_rx_gain = 0.0;
    double rx_gain_readback = 0.0;
    bool rx_gain_ok = false;
    long long rx_lo_readback = 0;
    bool rx_lo_ok = false;

    // TX frontend write-then-readback (fail-closed; single SDR owns the TX).
    long long requested_tx_bw = 0;
    long long tx_bw_readback = 0;
    bool tx_bw_ok = false;
    long long tx_lo_readback = 0;
    bool tx_lo_ok = false;
    double requested_tx_atten = 0.0;
    double tx_atten_readback = 0.0;
    bool tx_atten_ok = false;
    int loopback_readback = -1;
    bool loopback_ok = false;

    // Single-device restore: tx_restore_ok and rx_restore_ok BOTH come from the ONE
    // DeviceStateGuard restore of the single SDR (they are the same operation).
    bool restore_ok = false;
    bool tx_restore_ok = false;
    bool rx_restore_ok = false;
    std::string restore_report;

    // baseline pairing (identity check on source_index + original_sha256 +
    // raw24_class + modulation + split_role)
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

    // scoring (24-class RAW, no merge)
    std::uint64_t scored = 0;
    std::uint64_t rf_excluded = 0;
    std::uint64_t total_valid = 0;
    std::uint64_t total_correct = 0;
    std::vector<std::uint64_t> class_total;
    std::vector<std::uint64_t> class_correct;
    std::vector<std::uint64_t> confusion;
    std::uint64_t wc_total = 0, wc_correct = 0;   // AM-SSB-WC (raw 17)
    std::uint64_t sc_total = 0, sc_correct = 0;   // AM-SSB-SC (raw 18)
    std::uint64_t nan_or_inf = 0;                 // non-finite logits (fail-closed)
    std::uint64_t repeat_deterministic = 0;       // 2nd infer agrees with 1st
    std::map<std::string, std::uint64_t> rf_exclude_reasons;
    bool any_tx_clip = false;
    bool any_rx_clip = false;

    // prediction agreement vs the frozen BF16 baseline (stable source_index key)
    std::uint64_t r8_prediction_agreement = 0;
    std::uint64_t r8_label_correct = 0;

    // negative control + TX stop + restore (across all samples)
    bool negative_control_ok = false;
    bool tx_stopped_ok = false;          // every attempt confirmed !tx_running()
    bool tx_stopped_final_ok = false;    // final exit cleanup confirm

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

    // two-sample (BPSK + 4ASK) / full24 mode
    bool two_sample_mode = false;
    std::string diagnostic_classes;
    std::string diagnostic_selected_classes;
    std::uint64_t diagnostic_requested_count = 0;

    // acceptance (measurement only; never a regression PASS)
    double prediction_agreement = 0.0;
    double rf_accuracy = 0.0;
    double accuracy_delta_pp = 0.0;
    bool full_run = false;

    // FOUR A/B metrics (the operator reads these; forced raw24 is PENDING here and
    // completed by the offline aggregate script as HYBRID_BOARD_GATED_PLUS_HOST_FORCED).
    double coverage = 0.0;
    double gated_accuracy = 0.0;
    double end_to_end_accuracy = 0.0;
    std::string forced_raw24_accuracy = "PENDING";

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
// run_iq_rf_loopback_24class_bf16_fix10
// ---------------------------------------------------------------------------
inline Singlesdr24Bf16Fix10RunReport run_iq_rf_loopback_24class_bf16_fix10(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    Singlesdr24Bf16Fix10RunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10 requires "
                                 "--frozen-dir=<D2 artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.baseline_path = board::get_opt(argc, argv, "--baseline", "");
    if (rep.baseline_path.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10 requires "
                                 "--baseline=<clean24_smoke_raw24_bf16_baseline.tsv>");
    const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rx_uri.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10 requires "
                                 "--rx-uri=<single SDR uri (TX+RX)>");

    rep.mode = board::get_opt(argc, argv, "--mode", "full24");
    if (rep.mode != "short2" && rep.mode != "full24")
        throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10: --mode must be "
                                 "short2 or full24 (got '" + rep.mode + "').");

    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const long long sample_rate = static_cast<long long>(
        board::opt_u64(argc, argv, "--sample-rate", 2560000ULL));
    if (sample_rate != static_cast<long long>(iqdloop::kFrozenFsIn))
        throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10: --sample-rate must "
                                 "be 2560000 (== iqdloop::kFrozenFsIn); got " +
                                 std::to_string(sample_rate) + ".");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 35.0);
    const long long rx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-bw", 18000000ULL));
    const long long tx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--tx-bw", 18000000ULL));
    const double tx_atten_db = board::opt_d(argc, argv, "--tx-atten", -40.0);
    // TX safety ceiling: never above -40 dB (mirrors pluto::kSafeTxCeilingDb).
    if (tx_atten_db > pluto::kSafeTxCeilingDb)
        throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10: --tx-atten " +
                                 std::to_string(tx_atten_db) +
                                 " exceeds the safety ceiling " +
                                 std::to_string(pluto::kSafeTxCeilingDb) + " dB.");
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
    rep.diagnostic_classes = board::get_opt(argc, argv, "--diagnostic-classes", "");
    const std::uint64_t diagnostic_per_class =
        board::opt_u64(argc, argv, "--diagnostic-per-class", 1);
    const bool dump_failed_rx = opt_flag(argc, argv, "--dump-failed-rx");
    const bool dump_recovery_diagnostics =
        opt_flag(argc, argv, "--dump-recovery-diagnostics");
    if (dump_failed_rx && out_dir.empty())
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10: --dump-failed-rx requires --out-dir "
            "(failed_rx/ artifacts need a writable base directory).");

    // RF safety: the single SDR is on the 50-ohm direct cable (loopback=0).
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10 requires --rf-path=direct-cable (50-ohm "
            "SMA coax, no antenna, no amplifier).  Got '" + rf_path + "'.");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10 requires --input-kind=radioml-d2-2p56m "
            "(got '" + rep.input_kind + "').");
    if (!rep.diagnostic_classes.empty() && max_files > 0)
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10: --diagnostic-classes and --max-files "
            "are mutually exclusive.");

    if (!out_dir.empty() && ::mkdir(out_dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10: cannot create "
                                 "--out-dir " + out_dir + ": " + std::strerror(errno));

    rep.results_path = join_path(out_dir, "route_f_fix10class24_bf16_singlesdr_ab1_results.tsv");
    rep.confusion_path = join_path(out_dir, "route_f_fix10class24_bf16_singlesdr_ab1_confusion_24.csv");
    rep.per_class_path = join_path(out_dir, "route_f_fix10class24_bf16_singlesdr_ab1_per_class.json");
    rep.summary_path = join_path(out_dir, "route_f_fix10class24_bf16_singlesdr_ab1_summary.json");
    rep.log_path = join_path(out_dir, "route_f_fix10class24_bf16_singlesdr_ab1_summary.log");

    rep.class_total.assign(rml24::kClassCount, 0);
    rep.class_correct.assign(rml24::kClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml24::kClassCount) *
                             rml24::kClassCount, 0);

    // CFO capture-range constants (task book §8)
    rep.coarse_cfo_search_min_hz = iqpctbrx::coarse_cfo_search_min_hz();
    rep.coarse_cfo_search_max_hz = iqpctbrx::coarse_cfo_search_max_hz();
    rep.coarse_cfo_unambiguous_range_hz = iqpctbrx::coarse_cfo_unambiguous_range_hz();
    rep.fine_cfo_range_hz = iqpctbrx::fine_cfo_range_hz();

    const cat::Contract contract = chain::contract_24();

    // ---- load frozen D2 sidecar + the 7-column raw24 BF16 baseline ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    const std::map<std::uint64_t, rml24bf16::BaselineRow> baseline =
        rml24bf16::load_baseline(rep.baseline_path, rml24::kClassCount);
    rep.baseline_rows = static_cast<std::uint64_t>(baseline.size());

    std::vector<iqdloop::FrozenIq> calib, holdout;
    for (const auto& fz : frozen)
        (fz.is_calibration ? calib : holdout).push_back(fz);

    // --mode selection: short2 = BPSK + 4ASK only; full24 = the whole manifest.
    if (rep.mode == "short2") {
        std::vector<iqdloop::FrozenIq> selected;
        for (const auto& fz : holdout)
            if (fz.modulation == "BPSK" || fz.modulation == "4ASK")
                selected.push_back(fz);
        holdout = std::move(selected);
        rep.diagnostic_selected_classes = "BPSK,4ASK";
    }

    // --diagnostic-classes overrides --mode (same selector as the dual-SDR runner).
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

    // ---- baseline identity check (fail-closed): source_index + original_sha256 +
    //      raw24_class + modulation + split_role ----
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

    std::printf("FIX10CLASS24_BF16_SINGLESDR_START input_kind=%s frozen_dir=%s "
                "frozen_files=%llu holdout_files=%llu baseline_rows=%llu "
                "baseline_identity_ok=%d mode=%s two_sample_mode=%d "
                "rx_uri=%s center_hz=%llu sample_rate=%lld rx_gain=%.3f "
                "rx_bw=%lld tx_bw=%lld tx_atten=%.3f rf_tx_target_rms=%.3f out_dir=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.baseline_rows),
                rep.baseline_identity_ok ? 1 : 0, rep.mode.c_str(),
                rep.two_sample_mode ? 1 : 0, rx_uri.c_str(),
                static_cast<unsigned long long>(center_hz),
                static_cast<long long>(sample_rate), gain_db,
                static_cast<long long>(rx_bw), static_cast<long long>(tx_bw),
                tx_atten_db, target_rms, out_dir.empty() ? "." : out_dir.c_str());
    std::fflush(stdout);

    std::printf("FIX10CLASS24_BF16_SINGLESDR_CFO_RANGE coarse_cfo_search_min_hz=%.3f "
                "coarse_cfo_search_max_hz=%.3f coarse_cfo_unambiguous_range_hz=%.3f "
                "fine_cfo_range_hz=%.3f\n",
                rep.coarse_cfo_search_min_hz, rep.coarse_cfo_search_max_hz,
                rep.coarse_cfo_unambiguous_range_hz, rep.fine_cfo_range_hz);
    std::fflush(stdout);

    // ---- device open (single SDR owns TX+RX; device-not-found is exit code 2) ----
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

    bool all_capture_ok = true;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate: force 2560000 on BOTH RX+TX (set_sample_rate writes both),
        //      fail-closed abs(delta) <= 5 Hz on EACH read-back ----
        const long long requested = sample_rate;
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.tx_rate = dev->get_tx_sample_rate();
        rep.rate_err_hz = static_cast<double>(rep.rx_rate - requested);
        rep.tx_rate_err_hz = static_cast<double>(rep.tx_rate - requested);
        rep.rate_err_ppm = 1e6 * rep.rate_err_hz / static_cast<double>(requested);
        rep.sample_rate_ok = std::llabs(rep.rx_rate - requested) <= 5 &&
                             std::llabs(rep.tx_rate - requested) <= 5;
        if (!rep.sample_rate_ok)
            throw std::runtime_error(
                "sample_rate_mismatch: requested=" + std::to_string(requested) +
                " rx=" + std::to_string(rep.rx_rate) +
                " tx=" + std::to_string(rep.tx_rate) +
                " (abs(actual-requested) must be <= 5 Hz on BOTH)");

        // ---- RX + TX frontend write-then-readback, ALL fail-closed ----
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);

            // RX
            rep.rx_lo_readback = dev->set_rx_lo(static_cast<long long>(center_hz));
            rep.rx_lo_ok = std::llabs(rep.rx_lo_readback -
                                      static_cast<long long>(center_hz)) <= 1;
            rep.requested_rx_bw = rx_bw;
            rep.rx_bw_readback = dev->set_rx_bw(rx_bw);
            rep.rx_bw_ok = rf_fix::rf_readback_close(rep.rx_bw_readback, rx_bw,
                                                     1000LL, 0.05);
            dev->set_rx_gain_mode("manual");
            rep.requested_rx_gain = gain_db;
            rep.rx_gain_readback = dev->set_rx_gain(gain_db);
            rep.rx_gain_ok = (dev->get_rx_gain_mode() == "manual") &&
                             std::fabs(rep.rx_gain_readback - gain_db) <= 0.5;

            // TX
            rep.tx_lo_readback = dev->set_tx_lo(static_cast<long long>(center_hz));
            rep.tx_lo_ok = std::llabs(rep.tx_lo_readback -
                                      static_cast<long long>(center_hz)) <= 1;
            rep.requested_tx_bw = tx_bw;
            rep.tx_bw_readback = dev->set_tx_bw(tx_bw);
            rep.tx_bw_ok = rf_fix::rf_readback_close(rep.tx_bw_readback, tx_bw,
                                                     1000LL, 0.05);
            rep.requested_tx_atten = tx_atten_db;
            rep.tx_atten_readback = dev->set_tx_atten(tx_atten_db);
            rep.tx_atten_ok = std::fabs(rep.tx_atten_readback - tx_atten_db) <= 0.5;
            rep.loopback_readback = dev->set_loopback(0);
            rep.loopback_ok = (rep.loopback_readback == 0);
        }
        std::printf("FIX10CLASS24_BF16_SINGLESDR_FRONTEND rx_lo=%lld rx_lo_ok=%d "
                    "requested_rx_bw=%lld rx_bw_readback=%lld rx_bw_ok=%d "
                    "requested_rx_gain=%.3f rx_gain_readback=%.3f rx_gain_ok=%d "
                    "tx_lo=%lld tx_lo_ok=%d requested_tx_bw=%lld tx_bw_readback=%lld "
                    "tx_bw_ok=%d requested_tx_atten=%.3f tx_atten_readback=%.3f "
                    "tx_atten_ok=%d loopback_readback=%d loopback_ok=%d\n",
                    static_cast<long long>(rep.rx_lo_readback), rep.rx_lo_ok ? 1 : 0,
                    static_cast<long long>(rep.requested_rx_bw),
                    static_cast<long long>(rep.rx_bw_readback), rep.rx_bw_ok ? 1 : 0,
                    rep.requested_rx_gain, rep.rx_gain_readback, rep.rx_gain_ok ? 1 : 0,
                    static_cast<long long>(rep.tx_lo_readback), rep.tx_lo_ok ? 1 : 0,
                    static_cast<long long>(rep.requested_tx_bw),
                    static_cast<long long>(rep.tx_bw_readback), rep.tx_bw_ok ? 1 : 0,
                    rep.requested_tx_atten, rep.tx_atten_readback, rep.tx_atten_ok ? 1 : 0,
                    rep.loopback_readback, rep.loopback_ok ? 1 : 0);
        std::fflush(stdout);
        if (!rep.rx_lo_ok)
            throw std::runtime_error("rx_lo readback mismatch: requested=" +
                                     std::to_string(center_hz) +
                                     " readback=" + std::to_string(rep.rx_lo_readback));
        if (!rep.rx_bw_ok)
            throw std::runtime_error("rx_bw readback mismatch: requested=" +
                                     std::to_string(rx_bw) +
                                     " readback=" + std::to_string(rep.rx_bw_readback));
        if (!rep.rx_gain_ok)
            throw std::runtime_error("rx_gain readback mismatch: requested=" +
                                     std::to_string(gain_db) +
                                     " readback=" + std::to_string(rep.rx_gain_readback));
        if (!rep.tx_lo_ok)
            throw std::runtime_error("tx_lo readback mismatch: requested=" +
                                     std::to_string(center_hz) +
                                     " readback=" + std::to_string(rep.tx_lo_readback));
        if (!rep.tx_bw_ok)
            throw std::runtime_error("tx_bw readback mismatch: requested=" +
                                     std::to_string(tx_bw) +
                                     " readback=" + std::to_string(rep.tx_bw_readback));
        if (!rep.tx_atten_ok)
            throw std::runtime_error("tx_atten readback mismatch: requested=" +
                                     std::to_string(tx_atten_db) +
                                     " readback=" + std::to_string(rep.tx_atten_readback));
        if (!rep.loopback_ok)
            throw std::runtime_error("loopback readback mismatch: want 0 got " +
                                     std::to_string(rep.loopback_readback));

        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        std::printf("FIX10CLASS24_BF16_SINGLESDR_RX_FORMAT %s\n",
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
        bool tx_stopped_any_fail = false;

        // ---- single pass over the selected holdout ----
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("iq-rf-loopback-24class-bf16-fix10: cannot open " +
                                     rep.results_path);
        results << "file_name\tsource_index\traw24_class\tmodulation\tsnr_db\t"
                << "split_role\tvalid\traw24_pred\tbaseline_pred\tcorrect\t"
                << "prediction_agreement\trepeat_deterministic\ttraining_corr\t"
                << "training_residual\ttiming_offset\tgain_mag\tphase_deg\t"
                << "coarse_cfo_hz\tfine_cfo_hz\ttotal_cfo_hz\tsro_ppm\trf_verdict\n";

        for (const auto& fz : holdout) {
            if (board::g_stop_requested) break;

            std::printf("FIX10CLASS24_BF16_SINGLESDR_FILE file=%s input_kind=%s "
                        "source_index=%lld source_class=%d modulation=%s "
                        "frozen_complex=%llu split_role=%s\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(),
                        static_cast<long long>(fz.source_index), fz.source_class,
                        fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        fz.split_role.c_str());
            std::fflush(stdout);

            // board's INDEPENDENT burst expectation (byte-identical to the PC's).
            const iqpctbrx::TxBurstBuild expected =
                fix10canonical::buildTxBurstFromFrozen(
                    fz.path, fz.complex_count, fz.sha256, target_rms);

            std::string rf_verdict = "INSUFFICIENT_EVIDENCE";
            bool rx_clipped = false;
            bool gate_ok = false;
            iqdual23fix10::CoarseCfoRecovery ccr;
            double total_cfo_hz = 0.0;
            double coarse_cfo_hz = 0.0;
            double fine_cfo_hz = 0.0;
            bool cfo_finite = false;
            bool cfo_in_range = false;
            bool noise_clipped = false;
            std::vector<std::int16_t> rx_int16;
            std::vector<std::complex<double>> rx;
            std::size_t capture_attempts = 0;
            bool control_fatal = false;
            iqrfrec::EstimateConfig rec_cfg;

            // ---- 1. negative control (single-SDR: stop TX + confirm, then measure
            //      the RX noise floor) ----
            const NegativeControl neg = run_rx_negative_control(*dev, noise_complex);
            if (!neg.tx_stopped_ok) tx_stopped_any_fail = true;
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
            std::printf("FIX10CLASS24_BF16_SINGLESDR_NEGATIVE_CONTROL file=%s "
                        "refills=%zu windows=%zu rms_min=%.4f rms_median=%.4f "
                        "rms_max=%.4f stability_ratio=%.4f noise_stable=%d "
                        "noise_clipped=%d tx_stopped_ok=%d pass=%d\n",
                        fz.file_name.c_str(), iqrfloop_run::kRfDiscardRefills,
                        iqrfloop_run::kRfNoiseWindows, neg.rms_min, neg.rms_median,
                        neg.rms_max, neg.stability_ratio, neg.stable ? 1 : 0,
                        noise_clipped ? 1 : 0, neg.tx_stopped_ok ? 1 : 0,
                        neg_pass ? 1 : 0);
            std::fflush(stdout);

            // ---- 2..7 bounded recapture loop (verbatim dual-SDR retry policy:
            //      retry ONLY the transient payload-training residual rejection,
            //      at most kPayloadTrainingCaptureMaxAttempts per source_index) ----
            for (;;) {
                ++capture_attempts;
                rx_int16.clear();
                rx.clear();
                ccr = iqdual23fix10::CoarseCfoRecovery{};
                total_cfo_hz = 0.0;
                coarse_cfo_hz = 0.0;
                fine_cfo_hz = 0.0;
                cfo_finite = false;
                cfo_in_range = false;
                rx_clipped = false;
                rf_verdict = "INSUFFICIENT_EVIDENCE";

                // ---- 2..5 single-SDR local TX + capture (replaces the dual-SDR
                //      PREPARE->START->READY->CAPTURED->STOPPED TCP control block) ----
                iqrfloop_run_24bf16::RfTransferResult24Bf16Fix10 tr;
                try {
                    tr = iqrfloop_run_24bf16::transfer_one_attempt_rf_24class_bf16_fix10(
                        *dev, expected, fz.source_index, fz.file_name, center_hz,
                        gain_db, tx_atten_db, tx_bw, delay_margin, &timing);
                } catch (const std::exception& e) {
                    rep.error = "single_sdr_tx_failed:" + std::string(e.what());
                    control_fatal = true;
                    break;
                }
                rx_int16 = std::move(tr.rx);
                if (!tr.tx_stopped_ok) tx_stopped_any_fail = true;
                all_capture_ok = all_capture_ok && tr.capture_ok;
                if (!tr.capture_ok) {
                    rep.error = "single_sdr_capture_failed (single contiguous RX "
                                "refill with no stream anomaly required)";
                    control_fatal = true;
                    break;
                }

                // ---- 6. recover (coarse CFO -> fine sync/gain) ----
                rx = iqrftrain::deinterleave(rx_int16);
                rec_cfg.min_corr = kFidelityTrainingCorrMin;
                rec_cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;
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

                // ---- 7. fidelity gate (EXACT 7-branch order, verbatim dual-SDR) ----
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

                // Retry ONLY the transient payload-training residual rejection.
                const bool retry =
                    !board::g_stop_requested &&
                    rf_verdict == "RF_DISTORTS_IQ" &&
                    iqrfrec::should_retry_payload_training_capture(
                        ccr.rec.failure, capture_attempts);
                if (retry) {
                    std::printf("FIX10CLASS24_BF16_SINGLESDR_CAPTURE_RETRY file=%s "
                                "completed_attempt=%zu max_attempts=%zu failure=%s "
                                "payload_training_residual=%.6f action=RETRY\n",
                                fz.file_name.c_str(), capture_attempts,
                                iqrfrec::kPayloadTrainingCaptureMaxAttempts,
                                iqrfrec::failure_token(ccr.rec.failure),
                                ccr.rec.payload_training_residual);
                    std::fflush(stdout);
                    continue;
                }
                break;
            }
            if (control_fatal) break;

            // ---- CFO aggregation + diagnostics (once per file, final attempt) ----
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

            std::printf("FIX10CLASS24_BF16_SINGLESDR_CFO file=%s "
                        "coarse_cfo_search_min_hz=%.3f coarse_cfo_search_max_hz=%.3f "
                        "coarse_cfo_unambiguous_range_hz=%.3f fine_cfo_range_hz=%.3f "
                        "coarse_cfo_hz=%.3f fine_cfo_hz=%.3f total_cfo_hz=%.3f "
                        "fractional_timing_samples=%.6f fractional_corr_before=%.6f "
                        "fractional_corr_after=%.6f cfo_finite=%d cfo_in_range=%d\n",
                        fz.file_name.c_str(), rep.coarse_cfo_search_min_hz,
                        rep.coarse_cfo_search_max_hz, rep.coarse_cfo_unambiguous_range_hz,
                        rep.fine_cfo_range_hz, coarse_cfo_hz, fine_cfo_hz, total_cfo_hz,
                        ccr.fractional_timing_samples, ccr.fractional_corr_before,
                        ccr.fractional_corr_after,
                        cfo_finite ? 1 : 0, cfo_in_range ? 1 : 0);
            std::fflush(stdout);
            if (dump_recovery_diagnostics) {
                std::printf("FIX10CLASS24_BF16_SINGLESDR_CFO_FRACTIONAL file=%s "
                            "payload_fractional_corr_before=%.6f "
                            "payload_fractional_corr_after=%.6f "
                            "payload_best_fractional_timing_samples=%.6f "
                            "payload_best_fractional_corr=%.6f "
                            "payload_best_fractional_preamble_corr=%.6f\n",
                            fz.file_name.c_str(), ccr.payload_fractional_corr_before,
                            ccr.payload_fractional_corr_after,
                            ccr.payload_best_fractional_timing_samples,
                            ccr.payload_best_fractional_corr,
                            ccr.payload_best_fractional_preamble_corr);
                std::fflush(stdout);
            }

            std::printf("FIX10CLASS24_BF16_SINGLESDR_CAPTURE_ATTEMPTS file=%s "
                        "attempts=%zu retries=%zu final_failure=%s final_valid=%d\n",
                        fz.file_name.c_str(), capture_attempts,
                        capture_attempts - 1, iqrfrec::failure_token(ccr.rec.failure),
                        ccr.rec.valid ? 1 : 0);
            std::fflush(stdout);

            const iqrfrec::PerFileRecovery& rec = ccr.rec;
            std::printf("FIX10CLASS24_BF16_SINGLESDR_RECOVERY file=%s computed=%d "
                        "valid=%d failure=%s timing=%zu gain_mag=%.6f phase_deg=%.3f "
                        "fine_cfo_hz=%.3f sro_ppm=%.3f training_corr=%.6f "
                        "training_residual=%.6f payload_gain_mag=%.6f "
                        "payload_rms_gain_mag=%.6f payload_phase_deg=%.3f "
                        "payload_training_corr=%.6f payload_training_residual=%.6f "
                        "fidelity=%s rx_clipped=%d\n",
                        fz.file_name.c_str(), rec.computed ? 1 : 0, rec.valid ? 1 : 0,
                        iqrfrec::failure_token(rec.failure), rec.timing_offset,
                        rec.gain_mag, rec.phase_deg, rec.cfo_hz, rec.sro_ppm,
                        rec.training_corr, rec.training_residual, rec.payload_gain_mag,
                        rec.payload_rms_gain_mag, rec.payload_phase_deg,
                        rec.payload_training_corr, rec.payload_training_residual,
                        rf_verdict.c_str(), rx_clipped ? 1 : 0);
            std::fflush(stdout);

            // Wide-linear diagnostic line (verbatim dual-SDR presentational block).
            {
                const double wl_scalar = rec.wide_linear_scalar_validation_residual;
                const double wl_val = rec.wide_linear_validation_residual;
                const double wl_ratio = (std::isfinite(wl_scalar) && wl_scalar > 1e-12)
                    ? wl_val / wl_scalar : 0.0;
                const char* wl_reason = "N_A";
                if (rec.wide_linear_enabled) {
                    wl_reason = "ENABLED";
                } else if (!std::isfinite(wl_val) || !std::isfinite(wl_scalar)) {
                    wl_reason = "NON_FINITE";
                } else if (rec.wide_linear_image_ratio <= 1e-4) {
                    wl_reason = "IMAGE_TOO_SMALL";
                } else if (rec.wide_linear_image_ratio > 1.0) {
                    wl_reason = "IMAGE_TOO_LARGE";
                } else if (wl_ratio >= 0.99) {
                    wl_reason = "NO_IMPROVEMENT";
                } else {
                    wl_reason = "REJECTED_OTHER";
                }
                std::printf("FIX10CLASS24_BF16_SINGLESDR_WIDE_LINEAR file=%s "
                            "enabled=%d scalar_validation_residual=%.6f "
                            "validation_residual=%.6f improvement_ratio=%.6f "
                            "image_ratio=%.6f reason=%s\n",
                            fz.file_name.c_str(), rec.wide_linear_enabled ? 1 : 0,
                            wl_scalar, wl_val, wl_ratio,
                            rec.wide_linear_image_ratio, wl_reason);
                std::fflush(stdout);
            }

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
                ++rep.rf_excluded;
                ++rep.rf_exclude_reasons[rf_verdict];
                std::printf("FIX10CLASS24_BF16_SINGLESDR_FILE file=%s "
                            "classification=SKIPPED reason=fidelity_gate fidelity=%s\n",
                            fz.file_name.c_str(), rf_verdict.c_str());
                std::fflush(stdout);
                if (dump_failed_rx) {
                    try {
                        iqfix10dump::dump_failed_rx_sample(
                            fz, expected, rx_int16, rx, ccr,
                            coarse_cfo_hz, fine_cfo_hz, total_cfo_hz,
                            cfo_finite, cfo_in_range, rf_verdict, out_dir,
                            target_rms, rec_cfg,
                            rep.coarse_cfo_unambiguous_range_hz, rep.fine_cfo_range_hz,
                            rep.coarse_cfo_search_min_hz, rep.coarse_cfo_search_max_hz);
                    } catch (const std::exception& e) {
                        std::fprintf(stderr, "FIX10CLASS24_BF16_SINGLESDR_DUMP_WARN "
                                             "file=%s %s\n",
                                     fz.file_name.c_str(), e.what());
                    }
                }
                results << fz.file_name << "\t" << fz.source_index << "\t"
                        << fz.source_class << "\t" << fz.modulation << "\t"
                        << fz.snr_db << "\t" << fz.split_role
                        << "\t0\t-1\t-1\t-1\t-1\t-1\t"
                        << rec.training_corr << "\t" << rec.training_residual << "\t"
                        << (rec.valid ? static_cast<long long>(rec.timing_offset) : -1)
                        << "\t" << rec.gain_mag << "\t" << rec.phase_deg << "\t"
                        << coarse_cfo_hz << "\t" << fine_cfo_hz << "\t"
                        << total_cfo_hz << "\t" << rec.sro_ppm << "\t"
                        << rf_verdict << "\n";
                continue;
            }

            // ---- 8. chain -> D2 restore -> reference window -> NPU24 -> RAW-24 (no
            //      merge) ----
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
                        << fz.source_class << "\t" << fz.modulation << "\t"
                        << fz.snr_db << "\t" << fz.split_role
                        << "\t0\t-1\t-1\t-1\t-1\t-1\t"
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

            // Repeat-determinism: a second inference on the SAME aligned tensor must
            // produce the same raw-24 argmax.
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
            if (prediction_agreement) ++rep.r8_prediction_agreement;
            if (label_correct) ++rep.r8_label_correct;
            std::printf("FIX10CLASS24_BF16_SINGLESDR_CLASSIFY file=%s baseline_pred=%d "
                        "rf_pred=%d source_label=%d prediction_agreement=%d "
                        "label_correct=%d repeat_deterministic=%d finite=%d\n",
                        fz.file_name.c_str(), baseline_pred, raw_top, fz.source_class,
                        prediction_agreement ? 1 : 0, label_correct ? 1 : 0,
                        repeat_det ? 1 : 0, finite ? 1 : 0);
            std::fflush(stdout);

            ++global_frame_id;
            rf::ResultFrame r;
            r.frame_id = global_frame_id;
            r.timestamp_us = global_frame_id * 8000ULL;
            r.source = "iq_rf_loopback_24class_bf16_fix10";
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
                    << rec.training_corr << "\t" << rec.training_residual << "\t"
                    << static_cast<long long>(rec.timing_offset) << "\t"
                    << rec.gain_mag << "\t" << rec.phase_deg << "\t"
                    << coarse_cfo_hz << "\t" << fine_cfo_hz << "\t"
                    << total_cfo_hz << "\t" << rec.sro_ppm << "\t"
                    << rf_verdict << "\n";

            std::printf("FIX10CLASS24_BF16_SINGLESDR_RESULT file=%s frames=1 correct=%d "
                        "source=%d raw24_pred=%d repeat_det=%d\n",
                        fz.file_name.c_str(), correct ? 1 : 0, fz.source_class,
                        raw_top, repeat_det ? 1 : 0);
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
        rep.tx_stopped_ok = !tx_stopped_any_fail;
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // ---- single-device exit cleanup (ALL paths: normal, early-throw, exception,
    //      user-stop): tx.stop() -> confirm !tx_running() -> guard->restore() ->
    //      record the restore result.  The single DeviceStateGuard restore returns
    //      BOTH RX and TX attributes, so tx_restore_ok == rx_restore_ok == restore_ok.
    if (guard) {
        try {
            dev->tx_stop();
        } catch (...) {
            // a tx_stop that throws still must not block restore
        }
        rep.tx_stopped_final_ok = !dev->tx_running();
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
        rep.tx_restore_ok = rep.restore_ok;
        rep.rx_restore_ok = rep.restore_ok;
        if (!rep.tx_stopped_final_ok) rep.tx_stopped_ok = false;
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- the FOUR A/B metrics (measurement; never a regression PASS) ----
    const double total = static_cast<double>(rep.holdout_files);
    rep.coverage = total > 0 ? static_cast<double>(rep.scored) / total : 0.0;
    rep.gated_accuracy = rep.scored > 0
        ? static_cast<double>(rep.r8_label_correct) / static_cast<double>(rep.scored)
        : 0.0;
    rep.end_to_end_accuracy = total > 0
        ? static_cast<double>(rep.r8_label_correct) / total : 0.0;
    // forced_raw24_accuracy stays "PENDING": the board runner has no Host-BF16
    // forced classification; the offline aggregate script produces the HYBRID value.

    // ---- acceptance measurement (agreement/correct counts, never a PASS token) ----
    rep.prediction_agreement = rep.scored > 0
        ? static_cast<double>(rep.r8_prediction_agreement) / static_cast<double>(rep.scored)
        : 0.0;
    rep.rf_accuracy = rep.scored > 0
        ? static_cast<double>(rep.r8_label_correct) / static_cast<double>(rep.scored)
        : 0.0;
    rep.accuracy_delta_pp = 100.0 * (rep.rf_accuracy - 0.0);

    double macro_acc = 0.0;
    {
        std::size_t seen = 0;
        for (int c = 0; c < rml24::kClassCount; ++c) {
            if (rep.class_total[static_cast<std::size_t>(c)] == 0) continue;
            ++seen;
            macro_acc += static_cast<double>(
                             rep.class_correct[static_cast<std::size_t>(c)]) /
                         static_cast<double>(rep.class_total[static_cast<std::size_t>(c)]);
        }
        if (seen > 0) macro_acc /= static_cast<double>(seen);
    }

    // Confusion CSV (24x24).
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

    // Per-class JSON (24).
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
        const std::string measurement_token =
            (rep.error.empty() && rep.sample_rate_ok) ? kMeasurementComplete
                                                      : kMeasurementIncomplete;
        f << "{\n";
        f << "  \"token\":\"FIX10CLASS24_BF16_SINGLESDR_MEASUREMENT\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"deployment_mode\":\"" << rml24::kDeploymentMode << "\",\n";
        f << "  \"model_mode\":\"" << rml24::kModelMode << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"frozen_dir\":\"" << json_escape(rep.frozen_dir) << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"baseline_path\":\"" << json_escape(rep.baseline_path) << "\",\n";
        f << "  \"mode\":\"" << json_escape(rep.mode) << "\",\n";
        f << "  \"rx_uri\":\"" << json_escape(rx_uri) << "\",\n";
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
        f << "  \"wc_total\":" << rep.wc_total << ",\n";
        f << "  \"wc_correct\":" << rep.wc_correct << ",\n";
        f << "  \"sc_total\":" << rep.sc_total << ",\n";
        f << "  \"sc_correct\":" << rep.sc_correct << ",\n";
        f << "  \"nan_or_inf\":" << rep.nan_or_inf << ",\n";
        f << "  \"repeat_deterministic\":" << rep.repeat_deterministic << ",\n";
        f << "  \"training_estimates\":" << rep.training_estimates << ",\n";
        f << "  \"training_measured\":" << rep.training_measured << ",\n";
        f << "  \"training_corr_min\":" << rep.training_corr_min << ",\n";
        f << "  \"training_corr_avg\":" << rep.training_corr_avg << ",\n";
        f << "  \"training_residual_max\":" << rep.training_residual_max << ",\n";
        f << "  \"training_residual_avg\":" << rep.training_residual_avg << ",\n";
        f << "  \"coverage\":" << rep.coverage << ",\n";
        f << "  \"gated_accuracy\":" << rep.gated_accuracy << ",\n";
        f << "  \"end_to_end_accuracy\":" << rep.end_to_end_accuracy << ",\n";
        f << "  \"forced_raw24_accuracy\":\"" << rep.forced_raw24_accuracy << "\",\n";
        f << "  \"forced_raw24_accuracy_layer\":\"HYBRID_BOARD_GATED_PLUS_HOST_FORCED\",\n";
        f << "  \"negative_control_ok\":" << (rep.negative_control_ok ? "true" : "false") << ",\n";
        f << "  \"tx_stopped_ok\":" << (rep.tx_stopped_ok ? "true" : "false") << ",\n";
        f << "  \"tx_stopped_final_ok\":" << (rep.tx_stopped_final_ok ? "true" : "false") << ",\n";
        f << "  \"tx_restore_ok\":" << (rep.tx_restore_ok ? "true" : "false") << ",\n";
        f << "  \"rx_restore_ok\":" << (rep.rx_restore_ok ? "true" : "false") << ",\n";
        f << "  \"restore_single_device\":true,\n";
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
        f << "  \"tx_rate\":" << rep.tx_rate << ",\n";
        f << "  \"rx_lo_readback\":" << rep.rx_lo_readback << ",\n";
        f << "  \"rx_lo_ok\":" << (rep.rx_lo_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rx_bw\":" << rep.requested_rx_bw << ",\n";
        f << "  \"rx_bw_readback\":" << rep.rx_bw_readback << ",\n";
        f << "  \"rx_bw_ok\":" << (rep.rx_bw_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rx_gain\":" << rep.requested_rx_gain << ",\n";
        f << "  \"rx_gain_readback\":" << rep.rx_gain_readback << ",\n";
        f << "  \"rx_gain_ok\":" << (rep.rx_gain_ok ? "true" : "false") << ",\n";
        f << "  \"tx_lo_readback\":" << rep.tx_lo_readback << ",\n";
        f << "  \"tx_lo_ok\":" << (rep.tx_lo_ok ? "true" : "false") << ",\n";
        f << "  \"requested_tx_bw\":" << rep.requested_tx_bw << ",\n";
        f << "  \"tx_bw_readback\":" << rep.tx_bw_readback << ",\n";
        f << "  \"tx_bw_ok\":" << (rep.tx_bw_ok ? "true" : "false") << ",\n";
        f << "  \"requested_tx_atten\":" << rep.requested_tx_atten << ",\n";
        f << "  \"tx_atten_readback\":" << rep.tx_atten_readback << ",\n";
        f << "  \"tx_atten_ok\":" << (rep.tx_atten_ok ? "true" : "false") << ",\n";
        f << "  \"loopback_readback\":" << rep.loopback_readback << ",\n";
        f << "  \"loopback_ok\":" << (rep.loopback_ok ? "true" : "false") << ",\n";
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
        f << "token=FIX10CLASS24_BF16_SINGLESDR_MEASUREMENT measurement=" << measurement_token
          << " deployment=" << rml24::kDeploymentMode
          << " mode=" << rep.mode
          << " holdout=" << rep.holdout_files
          << " scored=" << rep.scored
          << " rf_excluded=" << rep.rf_excluded
          << " prediction_agreement=" << rep.r8_prediction_agreement
          << "/" << rep.holdout_files
          << " label_correct=" << rep.r8_label_correct
          << "/" << rep.holdout_files
          << " wc=" << rep.wc_correct << "/" << rep.wc_total
          << " sc=" << rep.sc_correct << "/" << rep.sc_total
          << " nan_or_inf=" << rep.nan_or_inf
          << " repeat_deterministic=" << rep.repeat_deterministic
          << " training_estimates=" << rep.training_estimates
          << "/" << rep.holdout_files
          << " coverage=" << rep.coverage
          << " gated_accuracy=" << rep.gated_accuracy
          << " end_to_end_accuracy=" << rep.end_to_end_accuracy
          << " forced_raw24_accuracy=" << rep.forced_raw24_accuracy
          << " forced_layer=HYBRID_BOARD_GATED_PLUS_HOST_FORCED"
          << " negative_control=" << (rep.negative_control_ok ? "PASS" : "FAIL")
          << " tx_stopped_ok=" << (rep.tx_stopped_ok ? 1 : 0)
          << " tx_stopped_final_ok=" << (rep.tx_stopped_final_ok ? 1 : 0)
          << " tx_restore_ok=" << (rep.tx_restore_ok ? 1 : 0)
          << " rx_restore_ok=" << (rep.rx_restore_ok ? 1 : 0)
          << " cfo_finite=" << (rep.cfo_all_finite ? 1 : 0)
          << " cfo_in_range=" << (rep.cfo_all_in_range ? 1 : 0)
          << " total_cfo_abs_max_hz=" << rep.total_cfo_abs_max_hz
          << "\n";
    }

    // ---- the measurement result line (the operator reads the four metrics; never a
    //      regression PASS token) ----
    std::printf("FIX10CLASS24_BF16_SINGLESDR_MEASUREMENT_RESULT mode=%s "
                "holdout=%llu scored=%llu rf_excluded=%llu "
                "prediction_agreement=%llu/%llu label_correct=%llu/%llu "
                "wc=%llu/%llu sc=%llu/%llu nan_or_inf=%llu "
                "repeat_deterministic=%llu/%llu training_estimate_valid=%llu/%llu "
                "coverage=%.4f gated_accuracy=%.4f end_to_end_accuracy=%.4f "
                "forced_raw24_accuracy=%s forced_layer=HYBRID_BOARD_GATED_PLUS_HOST_FORCED "
                "negative_control=%s cfo_finite=%d cfo_in_range=%d "
                "tx_stopped_ok=%d tx_restore_ok=%d rx_restore_ok=%d\n",
                rep.mode.c_str(),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.rf_excluded),
                static_cast<unsigned long long>(rep.r8_prediction_agreement),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.r8_label_correct),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.wc_correct),
                static_cast<unsigned long long>(rep.wc_total),
                static_cast<unsigned long long>(rep.sc_correct),
                static_cast<unsigned long long>(rep.sc_total),
                static_cast<unsigned long long>(rep.nan_or_inf),
                static_cast<unsigned long long>(rep.repeat_deterministic),
                static_cast<unsigned long long>(rep.holdout_files),
                static_cast<unsigned long long>(rep.training_estimates),
                static_cast<unsigned long long>(rep.holdout_files),
                rep.coverage, rep.gated_accuracy, rep.end_to_end_accuracy,
                rep.forced_raw24_accuracy.c_str(),
                rep.negative_control_ok ? "PASS" : "FAIL",
                rep.cfo_all_finite ? 1 : 0, rep.cfo_all_in_range ? 1 : 0,
                rep.tx_stopped_ok ? 1 : 0, rep.tx_restore_ok ? 1 : 0,
                rep.rx_restore_ok ? 1 : 0);
    std::fflush(stdout);

    // ---- functional pass = the measurement infrastructure ran cleanly (NOT the
    //      classification accuracy, which is the A/B measurement the four metrics
    //      report).  A clean 18/24 run is a SUCCESSFUL measurement. ----
    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          rep.rx_lo_ok && rep.rx_bw_ok && rep.rx_gain_ok &&
                          rep.tx_lo_ok && rep.tx_bw_ok && rep.tx_atten_ok &&
                          rep.loopback_ok &&
                          !frozen.empty() && all_capture_ok &&
                          rep.baseline_identity_ok;
    const bool control_ok = rep.negative_control_ok && rep.tx_stopped_ok &&
                            rep.tx_stopped_final_ok &&
                            rep.restore_ok;
    rep.functional_pass = infra_ok && control_ok;

    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " holdout_files=" + std::to_string(rep.holdout_files) +
                         " baseline_rows=" + std::to_string(rep.baseline_rows) +
                         " mode=" + rep.mode +
                         " scored=" + std::to_string(rep.scored) +
                         " rf_excluded=" + std::to_string(rep.rf_excluded) +
                         " prediction_agreement=" +
                             std::to_string(rep.r8_prediction_agreement) +
                         "/" + std::to_string(rep.holdout_files) +
                         " label_correct=" +
                             std::to_string(rep.r8_label_correct) +
                         "/" + std::to_string(rep.holdout_files) +
                         " wc=" + std::to_string(rep.wc_correct) + "/" +
                             std::to_string(rep.wc_total) +
                         " sc=" + std::to_string(rep.sc_correct) + "/" +
                             std::to_string(rep.sc_total) +
                         " nan_or_inf=" + std::to_string(rep.nan_or_inf) +
                         " repeat_deterministic=" +
                             std::to_string(rep.repeat_deterministic) +
                         " training_estimates=" + std::to_string(rep.training_estimates) +
                         " coverage=" + std::to_string(rep.coverage) +
                         " gated_accuracy=" + std::to_string(rep.gated_accuracy) +
                         " end_to_end_accuracy=" + std::to_string(rep.end_to_end_accuracy) +
                         " forced_raw24_accuracy=" + rep.forced_raw24_accuracy +
                         " (HYBRID_BOARD_GATED_PLUS_HOST_FORCED)" +
                         " negative_control=" +
                             (rep.negative_control_ok ? "PASS" : "FAIL") +
                         " tx_stopped_ok=" + (rep.tx_stopped_ok ? "1" : "0") +
                         " tx_stopped_final_ok=" + (rep.tx_stopped_final_ok ? "1" : "0") +
                         " tx_restore_ok=" + (rep.tx_restore_ok ? "1" : "0") +
                         " rx_restore_ok=" + (rep.rx_restore_ok ? "1" : "0") +
                         " (single_device_restore)" +
                         " cfo_finite=" + (rep.cfo_all_finite ? "1" : "0") +
                         " cfo_in_range=" + (rep.cfo_all_in_range ? "1" : "0") +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " tx_rate=" + std::to_string(rep.tx_rate) +
                         " requested_rx_bw=" + std::to_string(rep.requested_rx_bw) +
                         " rx_bw_readback=" + std::to_string(rep.rx_bw_readback) +
                         " requested_rx_gain=" + std::to_string(rep.requested_rx_gain) +
                         " rx_gain_readback=" + std::to_string(rep.rx_gain_readback) +
                         " requested_tx_bw=" + std::to_string(rep.requested_tx_bw) +
                         " tx_bw_readback=" + std::to_string(rep.tx_bw_readback) +
                         " requested_tx_atten=" + std::to_string(rep.requested_tx_atten) +
                         " tx_atten_readback=" + std::to_string(rep.tx_atten_readback) +
                         " loopback_readback=" + std::to_string(rep.loopback_readback) +
                         " rf_path=direct-cable";
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

}  // namespace iqrfloop24bf16
