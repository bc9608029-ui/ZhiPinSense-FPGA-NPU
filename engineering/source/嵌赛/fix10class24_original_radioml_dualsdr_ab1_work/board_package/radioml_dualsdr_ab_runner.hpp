#pragma once

// radioml_dualsdr_ab_runner.hpp -- task fix10class24-original-radioml-dualsdr-ab1:
// the DUAL-SDR board runner (arm C) that re-feeds the SAME 480 frozen original-RadioML
// test frames through the REAL RF chain and the frozen BF16 NPU, for the 3-arm A/D/C
// comparison.  Topology: the Windows PC owns the TX SDR (cyclic canonical burst over
// 50-ohm coax) and the BOARD owns the RX SDR (capture -> coarse CFO -> fine sync/gain
// -> wide-linear -> 0.100 gate -> NPU24 -> RAW-24 argmax, NO merge).  The two ends
// exchange ONLY control messages + sample identity + SHA over a TCP control channel
// (iq_pc_tx_board_rx_transfer_fix10.hpp) -- never real-time IQ.  This runner contains
// NO TX API: it is RX-only.
//
// This runner is byte-for-byte the SAME recovery/gate path as the prior dual-SDR
// runner (iq_pc_tx_board_rx_24class_bf16_fix10.hpp) and the singlesdr arm (S): the
// SAME recover_payload_with_coarse_cfo, the SAME rec_cfg, the SAME bounded recapture
// (max 3 attempts, retry only PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH, last-capture
// selection), the SAME 7-branch fidelity gate, the SAME 0.100 residual gate, the SAME
// RX-only negative control, the SAME DeviceStateGuard exit cleanup.  The ONLY deltas
// vs the prior dual-SDR D2 runner are:
//
//   * input = the TX-derived CI16 payload package (tx_manifest.tsv + <sid>.i16 +
//     route_d2_rf_manifest.tsv) from scripts/export_radioml_dualsdr_tx_payload.py +
//     scripts/pc_tx_radioml_dualsdr.py build-frozen-dir, loaded fail-closed by
//     radioml_dualsdr_ab_loader.hpp -- NOT iqdloop D2 frozen artifacts;
//   * model window = the FIRST 1024 complex samples of the recovered payload, then
//     * unscale (planar [2,1024] f32) -- NOT the prior D2-restore + reference window;
//   * output = the frozen 19-column board_results.tsv (contract §4) + 24-dim logits +
//     recovered model-input .bin per gated frame + unconditional per-sample raw/diag;
//   * --mode short24 | full480 (short24 = one 30 dB frame per class, smoke only).
//
// It is a MEASUREMENT (never a regression PASS).  The board NEVER forces a
// classification: a gate-rejected frame is emitted with board_pred=-1, and its
// `hard_invalid` flag tells the offline judger whether the frame is forceable
// (residual in (0.100,0.30] -- a host-side relaxed-gate forced classification is
// meaningful) or irrecoverable (clip / residual > 0.30 / estimator failed / infra
// reject).  `hard_invalid` is NEVER forced to success.
//
// DC-adaptation extension point (fix10class24-original-radioml-dc-ab1): a downstream
// fork builds a DC layer (--adaptation=direct|dc-transport) on top of THIS runner.
// The two natural hooks it reuses are (a) the fail-closed --input-kind gate below (the
// DC fork adds its own input_kind / --adaptation there), and (b) the model-window
// tensor fill inside the gated branch (where `direct` vs `dc-transport` would branch on
// the recovered payload; `payload[k] * fr.unscale` below is the `direct` path).  The
// manifest's per-frame `adaptation` tag (radioml_dualsdr_ab_loader.hpp::kAdaptation())
// already flows through fr.adaptation and is the single authority to extend with a
// second frozen tag.  Nothing in THIS runner is reworked for DC: these are just the
// seam where the fork plugs in.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_per_frame_recovery.hpp"        // iqrfrec (shim -> iq_rf_sync_recovery.hpp)
#include "iq_rf_frame_layout.hpp"
#include "iq_rf_loopback_transfer.hpp"         // iqrfloop_run::kRfDiscard* / kRfNoise*
#include "iq_dual_sdr_coarse_cfo_recovery.hpp" // iqdual23fix10::recover_payload_with_coarse_cfo
#include "iq_pc_tx_board_rx_transfer_fix10.hpp"// iqpctbrx::* state machine + TxBurstBuild + CFO range
#include "iq_fix10_canonical_frame.hpp"         // fix10canonical::buildTxBurstFromFrozen
#include "rml24_raw.hpp"                        // rml24::raw24_predict (NO merge)
#include "rf_fix_helpers.hpp"                   // rf_fix::rf_readback_close (rx-bw fail-closed)
#include "radioml_dualsdr_ab_loader.hpp"        // rmldsab::load_tx_manifest
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/device_state_guard.hpp"
#include "../sdr_adapter/tcp_control_client.hpp"

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
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace rmldsab {

using Clock = std::chrono::steady_clock;

// fix10class24-original-radioml-dualsdr-ab1 measurement tokens (never a PASS).
constexpr const char* kMeasurementComplete =
    "ROUTE_F_RADIOML_ORIGINAL_DUALSDR_AB_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete =
    "ROUTE_F_RADIOML_ORIGINAL_DUALSDR_AB_MEASUREMENT_INCOMPLETE";

constexpr double kFidelityTrainingCorrMin = 0.9;   // preamble peak corr floor
constexpr std::size_t kDelayMarginDefault = 8192;  // capture margin past 2 periods
constexpr double kHardInvalidResidualCeiling = 0.30;  // contract §4: irrecoverable ceiling

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

inline std::string json_number(double v) {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.9g", v);
    return std::string(buf);
}

inline std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
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

// Verbatim from iqpcbtrx24bf16fix10::failure_rf_verdict (same recovery-core failure
// -> RF verdict mapping; the 7-branch fidelity gate is reproduced exactly below).
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
// RX-only negative control (verbatim from the prior dual-SDR runner): the board
// has NO TX to stop; the control-channel state machine guarantees the PC's TX is
// off at this point.  The discard-refill / noise-window / stability logic is
// byte-for-byte the single-SDR runner's run_rx_negative_control, minus the TX stop.
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

// short24 fixed selection (contract §3): for each raw24_class c in 0..23, take the
// frame with dataset_snr_db==30 and the SMALLEST selection_id; requires exactly one
// 30 dB frame per class else fail-closed.  Label is used ONLY to pick one frame per
// class for the identity/smoke pass, never for recovery or prediction.
inline std::vector<rmldsab::DualsdrFrame> select_short24(
        const std::vector<rmldsab::DualsdrFrame>& all) {
    std::map<int, const rmldsab::DualsdrFrame*> best;
    for (const auto& fr : all) {
        if (fr.dataset_snr_db != 30) continue;
        auto it = best.find(fr.raw24_class);
        if (it == best.end() || fr.selection_id < it->second->selection_id)
            best[fr.raw24_class] = &fr;
    }
    if (best.size() != static_cast<std::size_t>(rmldsab::kClassCount)) {
        std::string missing;
        for (int c = 0; c < rmldsab::kClassCount; ++c) {
            if (!best.count(c)) {
                if (!missing.empty()) missing += ",";
                missing += std::to_string(c);
            }
        }
        throw std::runtime_error(
            "radioml-dualsdr-ab: short24 missing 30 dB frames for classes " + missing);
    }
    std::vector<rmldsab::DualsdrFrame> sel;
    sel.reserve(rmldsab::kClassCount);
    for (int c = 0; c < rmldsab::kClassCount; ++c)
        sel.push_back(*best[c]);
    return sel;
}

// ---------------------------------------------------------------------------
// DualsdrAbRunReport
// ---------------------------------------------------------------------------
struct DualsdrAbRunReport {
    std::string input_dir;
    std::string input_kind;
    std::string model_sha;
    std::string out_dir;
    std::string tx_control;
    std::string mode;                       // "short24" | "full480"
    std::uint64_t frames_selected = 0;      // 24 or 480

    bool device_not_found = false;
    std::string error;

    // RX frontend write-then-readback (ALL fail-closed; the board owns NO TX).
    long long requested_rate = 0;
    long long rx_rate = 0;
    bool sample_rate_ok = false;
    long long rx_lo_readback = 0;
    bool rx_lo_ok = false;
    long long requested_rx_bw = 0;
    long long rx_bw_readback = 0;
    bool rx_bw_ok = false;
    double requested_rx_gain = 0.0;
    double rx_gain_readback = 0.0;
    bool rx_gain_ok = false;

    // Single-device (RX-only) restore.
    bool restore_ok = false;
    std::string restore_report;

    // scoring (raw24 RAW, no merge; board NEVER forces)
    std::uint64_t scored = 0;               // gated (RF_PRESERVES_IQ)
    std::uint64_t gate_reject = 0;          // !gated
    std::uint64_t hard_invalid = 0;         // irrecoverable (clip / residual>0.30 / est-fail / infra)
    std::uint64_t forceable = 0;            // gate_reject && !hard_invalid
    std::uint64_t total_correct = 0;        // gated && finite && pred==label
    std::uint64_t finite_count = 0;
    std::uint64_t nan_or_inf = 0;
    std::uint64_t repeat_deterministic = 0;
    std::vector<std::uint64_t> class_total;
    std::vector<std::uint64_t> class_correct;
    std::vector<std::uint64_t> confusion;   // 24x24 (true x pred)
    bool any_rx_clip = false;

    // control evidence (across all samples)
    bool negative_control_ok = false;
    bool tx_restore_ok = false;             // PC's TX restore (STOPPED.tx_restore_ok), all frames

    std::string results_path;               // board_results.tsv (19-col)
    std::string logits_path;                // board_logits.tsv (24 logits / gated frame)
    std::string recovered_dir;              // recovered/<sid>.*
    std::string summary_path;               // board_summary.json

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// The exact 19-column board_results.tsv header (contract §4).
inline const char* board_results_header() {
    return "selection_id\thdf5_row_index\traw24_class\tdataset_snr_db\tgated\t"
           "board_pred\tfinite\tresidual\tcorr\tcoarse_cfo_hz\tfine_cfo_hz\t"
           "total_cfo_hz\tfractional_timing_samples\tclip\tcapture_attempts\t"
           "gate_reject\thard_invalid\ttx_stop_ok\trx_restore_ok";
}

// ---------------------------------------------------------------------------
// run_radioml_original_dualsdr_ab
// ---------------------------------------------------------------------------
inline DualsdrAbRunReport run_radioml_original_dualsdr_ab(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    DualsdrAbRunReport rep;

    // ---- args ----
    rep.input_dir = board::get_opt(argc, argv, "--input-dir", "");
    if (rep.input_dir.empty())
        throw std::runtime_error("radioml-dualsdr-ab requires --input-dir=<tx payload "
                                 "package dir> (tx_manifest.tsv + 480 .i16 + "
                                 "route_d2_rf_manifest.tsv)");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.out_dir = board::get_opt(argc, argv, "--out-dir", "");
    rep.tx_control = board::get_opt(argc, argv, "--tx-control", "");
    if (rep.tx_control.empty())
        throw std::runtime_error("radioml-dualsdr-ab requires "
                                 "--tx-control=tcp://<PC_IP>:39010");
    const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rx_uri.empty())
        throw std::runtime_error("radioml-dualsdr-ab requires --rx-uri=<board RX device uri>");

    rep.mode = board::get_opt(argc, argv, "--mode", "short24");
    if (rep.mode != "short24" && rep.mode != "full480")
        throw std::runtime_error("radioml-dualsdr-ab: --mode must be short24 or "
                                 "full480 (got '" + rep.mode + "').");

    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const long long sample_rate = static_cast<long long>(
        board::opt_u64(argc, argv, "--sample-rate", 2560000ULL));
    if (sample_rate != 2560000LL)
        throw std::runtime_error("radioml-dualsdr-ab: --sample-rate must be 2560000 "
                                 "(2.56 Msps); got " + std::to_string(sample_rate) + ".");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 35.0);
    const long long rx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-bw", 18000000ULL));
    const double target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0);
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", kDelayMarginDefault));
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex",
                       iqrfloop_run::kRfNoiseComplexDefault));

    // input_kind fail-closed (the PC TX service + HELLO manifest_sha256 agree on it).
    rep.input_kind = board::get_opt(argc, argv, "--input-kind",
                                    "radioml-original-dualsdr-ab-2p56m");
    if (rep.input_kind != "radioml-original-dualsdr-ab-2p56m")
        throw std::runtime_error("radioml-dualsdr-ab requires "
                                 "--input-kind=radioml-original-dualsdr-ab-2p56m (got '" +
                                 rep.input_kind + "').");

    // RF safety: both ends must be on the 50-ohm direct cable.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error("radioml-dualsdr-ab requires --rf-path=direct-cable "
                                 "(50-ohm SMA coax, no antenna, no amplifier). Got '" +
                                 rf_path + "'.");

    // ---- fail-closed out dir: never overwrite an existing directory ----
    if (rep.out_dir.empty())
        throw std::runtime_error("radioml-dualsdr-ab requires --out-dir=<fresh dir>");
    {
        struct stat st;
        if (::stat(rep.out_dir.c_str(), &st) == 0)
            throw std::runtime_error("radioml-dualsdr-ab: --out-dir already exists: " +
                                     rep.out_dir +
                                     " (refusing to overwrite; use a fresh timestamped dir)");
        if (::mkdir(rep.out_dir.c_str(), 0777) != 0)
            throw std::runtime_error("radioml-dualsdr-ab: cannot create --out-dir " +
                                     rep.out_dir + ": " + std::strerror(errno));
    }

    rep.results_path = join_path(rep.out_dir, "board_results.tsv");
    rep.logits_path = join_path(rep.out_dir, "board_logits.tsv");
    rep.recovered_dir = join_path(rep.out_dir, "recovered");
    rep.summary_path = join_path(rep.out_dir, "board_summary.json");

    rep.class_total.assign(rml24::kClassCount, 0);
    rep.class_correct.assign(rml24::kClassCount, 0);
    rep.confusion.assign(static_cast<std::size_t>(rml24::kClassCount) *
                             rml24::kClassCount, 0);

    const cat::Contract contract = chain::contract_24();

    // ---- fail-closed: verify the WHOLE TX payload package before touching the NPU ----
    const std::vector<rmldsab::DualsdrFrame> all_frames =
        rmldsab::load_tx_manifest(rep.input_dir);

    std::vector<rmldsab::DualsdrFrame> frames;
    if (rep.mode == "short24") {
        frames = select_short24(all_frames);
    } else {
        frames = all_frames;
    }
    rep.frames_selected = static_cast<std::uint64_t>(frames.size());

    std::printf("RADIOML_ORIGINAL_DUALSDR_AB_MANIFEST all_frames=%llu selected=%llu "
                "mode=%s input_dir=%s input_kind=%s\n",
                static_cast<unsigned long long>(all_frames.size()),
                static_cast<unsigned long long>(frames.size()), rep.mode.c_str(),
                rep.input_dir.c_str(), rep.input_kind.c_str());
    std::fflush(stdout);

    std::printf("RADIOML_ORIGINAL_DUALSDR_AB_START mode=%s frames=%llu tx_control=%s "
                "rx_uri=%s center_hz=%llu sample_rate=%lld rx_gain=%.3f rx_bw=%lld "
                "rf_tx_target_rms=%.3f model_sha=%s out_dir=%s\n",
                rep.mode.c_str(),
                static_cast<unsigned long long>(frames.size()), rep.tx_control.c_str(),
                rx_uri.c_str(), static_cast<unsigned long long>(center_hz),
                static_cast<long long>(sample_rate), gain_db,
                static_cast<long long>(rx_bw), target_rms, rep.model_sha.c_str(),
                rep.out_dir.c_str());
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
            sdr::sha256_hex_file(iqpctbrx::d2_manifest_path(rep.input_dir), &ok);
        if (!ok)
            throw std::runtime_error("radioml-dualsdr-ab: cannot hash frozen manifest " +
                                     iqpctbrx::d2_manifest_path(rep.input_dir) +
                                     " (run pc_tx_radioml_dualsdr.py build-frozen-dir first)");
    }
    sess.input_kind = rep.input_kind;
    sess.sample_rate = static_cast<std::uint64_t>(sample_rate);
    sess.center_hz = center_hz;
    sess.target_rms = target_rms;

    iqpctbrx::TcpControlClient client;
    {
        std::string host;
        std::uint16_t port = iqpctbrx::kDefaultPort;
        std::string perr;
        if (!iqpctbrx::parse_tx_control_url(rep.tx_control, host, port, &perr))
            throw std::runtime_error("radioml-dualsdr-ab: " + perr);
        client.host = host;
        client.port = port;
        if (!client.connect(&perr))
            throw std::runtime_error("radioml-dualsdr-ab: connect to " + rep.tx_control +
                                     " failed: " + perr);
    }

    // ---- HELLO -> HELLO_ACK (PC confirms config + TX off) ----
    {
        std::string perr;
        iqpctbrx::HelloAckInfo ack;
        if (!iqpctbrx::send_hello(client, sess, &perr) ||
            !iqpctbrx::recv_hello_ack(client, sess, ack, &perr)) {
            const std::string primary_error = perr;
            std::string cleanup_error;
            iqpctbrx::send_abort(client, sess, "hello_failed", &cleanup_error);
            client.close();
            if (!cleanup_error.empty())
                std::printf("RADIOML_ORIGINAL_DUALSDR_AB_HELLO_ABORT_CLEANUP_ERROR=%s "
                            "(primary=%s)\n",
                            cleanup_error.c_str(), primary_error.c_str());
            throw std::runtime_error("radioml-dualsdr-ab: HELLO failed: " + primary_error);
        }
        std::printf("RADIOML_ORIGINAL_DUALSDR_AB_HELLO_ACK tx_serial=%s tx_uri=%s "
                    "tx_atten_db=%.3f configuration_verified=%d\n",
                    ack.tx_serial.c_str(), ack.tx_uri.c_str(), ack.tx_atten_db,
                    ack.configuration_verified ? 1 : 0);
        std::fflush(stdout);
    }

    bool all_capture_ok = true;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    // Rows must survive the capture try/catch: they are written after restore.
    std::vector<std::string> row_lines;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate (RX only): force 2560000, fail-closed abs(delta) <= 5 Hz ----
        const long long requested = sample_rate;
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.sample_rate_ok = std::llabs(rep.rx_rate - requested) <= 5;
        if (!rep.sample_rate_ok)
            throw std::runtime_error(
                "sample_rate_mismatch: requested=" + std::to_string(requested) +
                " rx=" + std::to_string(rep.rx_rate) +
                " (abs(actual-requested) must be <= 5 Hz)");

        // ---- RX frontend write-then-readback, ALL fail-closed ----
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);

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
        }
        std::printf("RADIOML_ORIGINAL_DUALSDR_AB_FRONTEND rx_lo=%lld rx_lo_ok=%d "
                    "requested_rx_bw=%lld rx_bw_readback=%lld rx_bw_ok=%d "
                    "requested_rx_gain=%.3f rx_gain_readback=%.3f rx_gain_ok=%d\n",
                    static_cast<long long>(rep.rx_lo_readback), rep.rx_lo_ok ? 1 : 0,
                    static_cast<long long>(rep.requested_rx_bw),
                    static_cast<long long>(rep.rx_bw_readback), rep.rx_bw_ok ? 1 : 0,
                    rep.requested_rx_gain, rep.rx_gain_readback, rep.rx_gain_ok ? 1 : 0);
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

        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        std::printf("RADIOML_ORIGINAL_DUALSDR_AB_RX_FORMAT %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);
        const int rx_pos_rail = iqdloop_sync::rail_positive(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));
        const int rx_neg_rail = iqdloop_sync::rail_negative(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));

        std::uint64_t global_frame_id = 0;
        bool neg_any_fail = false;
        bool tx_restore_any_fail = false;

        // D-level input-transfer audit ON: prove source bytes == mapped destination
        // == post-forward host input (byte-identical) for every frame.
        npu.set_input_audit(true);

        // Recovered artifacts dir (raw + diag for EVERY sample; model input for gated).
        if (::mkdir(rep.recovered_dir.c_str(), 0777) != 0)
            throw std::runtime_error("radioml-dualsdr-ab: cannot create " +
                                     rep.recovered_dir + ": " + std::strerror(errno));

        std::ofstream logits(rep.logits_path, std::ios::binary);
        if (!logits)
            throw std::runtime_error("radioml-dualsdr-ab: cannot open " + rep.logits_path);
        logits << "selection_id\thdf5_row_index\traw24_class";
        for (int c = 0; c < rml24::kClassCount; ++c)
            logits << "\tlogit_" << (c < 10 ? "0" : "") << c;
        logits << "\tpred_pass1\tpred_pass2\n";

        // ---- single pass over the selected frames ----
        for (const auto& fr : frames) {
            if (board::g_stop_requested) break;

            std::printf("RADIOML_ORIGINAL_DUALSDR_AB_FILE selection_id=%d "
                        "hdf5_row_index=%lld raw24_class=%d modulation=%s "
                        "dataset_snr_db=%d host_pred=%d tx_payload_file=%s\n",
                        fr.selection_id, static_cast<long long>(fr.hdf5_row_index),
                        fr.raw24_class, fr.modulation.c_str(), fr.dataset_snr_db,
                        fr.host_pred, fr.tx_payload_file.c_str());
            std::fflush(stdout);

            // board's INDEPENDENT burst expectation (byte-identical to the PC's).
            const iqpctbrx::TxBurstBuild expected =
                fix10canonical::buildTxBurstFromFrozen(
                    join_path(rep.input_dir, fr.tx_payload_file),
                    rmldsab::kPayloadComplex, fr.tx_payload_sha256, target_rms);
            const iqpctbrx::SampleIdentity smp{
                fr.selection_id, fr.tx_payload_file, expected.payload_sha_pre};

            std::string rf_verdict = "INSUFFICIENT_EVIDENCE";
            bool rx_clipped = false;
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
            bool frame_tx_stop_ok = false;   // PC's TX restore for THIS frame (STOPPED.tx_restore_ok)
            iqrfrec::EstimateConfig rec_cfg;

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
            std::printf("RADIOML_ORIGINAL_DUALSDR_AB_NEGATIVE_CONTROL selection_id=%d "
                        "rms_min=%.4f rms_median=%.4f rms_max=%.4f stability_ratio=%.4f "
                        "noise_stable=%d noise_clipped=%d pass=%d\n",
                        fr.selection_id, neg.rms_min, neg.rms_median, neg.rms_max,
                        neg.stability_ratio, neg.stable ? 1 : 0, noise_clipped ? 1 : 0,
                        neg_pass ? 1 : 0);
            std::fflush(stdout);

            // ---- 2..7 bounded recapture loop (verbatim dual-SDR retry policy:
            //      retry ONLY the transient payload-training residual rejection,
            //      at most kPayloadTrainingCaptureMaxAttempts per frame) ----
            for (;;) {
                ++capture_attempts;
                std::string ctrl_err;
                iqpctbrx::ControlOutcome ctrl = iqpctbrx::ControlOutcome::Ok;
                iqpctbrx::PreparedInfo prepared;
                iqpctbrx::ReadyInfo ready;
                iqpctbrx::StoppedInfo stopped;
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

                // ---- 2. PREPARE -> PREPARED (PC builds + verifies the burst, no TX) ----
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
                if (ctrl == iqpctbrx::ControlOutcome::Ok) {
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
                frame_tx_stop_ok = stopped.tx_restore_ok;
                if (!stopped.tx_restore_ok) tx_restore_any_fail = true;

                if (ctrl != iqpctbrx::ControlOutcome::Ok) {
                    std::string reason = ctrl_err.empty()
                        ? iqpctbrx::control_outcome_token(ctrl) : ctrl_err;
                    iqpctbrx::send_abort(client, sess, reason, &ctrl_err);
                    client.close();
                    rep.error = "control_channel_failed:" +
                                std::string(iqpctbrx::control_outcome_token(ctrl)) +
                                " " + reason;
                    control_fatal = true;
                    break;   // breaks the recapture loop (handled below)
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
                    std::fabs(coarse_cfo_hz) <=
                    iqpctbrx::coarse_cfo_unambiguous_range_hz() + 1e-9;
                const bool fine_in_range =
                    std::fabs(fine_cfo_hz) <= iqpctbrx::fine_cfo_range_hz() + 1e-9;
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
                    std::printf("RADIOML_ORIGINAL_DUALSDR_AB_CAPTURE_RETRY "
                                "selection_id=%d completed_attempt=%zu max_attempts=%zu "
                                "failure=%s payload_training_residual=%.6f action=RETRY\n",
                                fr.selection_id, capture_attempts,
                                iqrfrec::kPayloadTrainingCaptureMaxAttempts,
                                iqrfrec::failure_token(ccr.rec.failure),
                                ccr.rec.payload_training_residual);
                    std::fflush(stdout);
                    continue;
                }
                break;
            }
            if (control_fatal) break;

            const iqrfrec::PerFileRecovery& rec = ccr.rec;
            const double residual = rec.payload_training_residual;
            const double corr = rec.payload_training_corr;

            std::printf("RADIOML_ORIGINAL_DUALSDR_AB_RECOVERY selection_id=%d "
                        "computed=%d valid=%d failure=%s "
                        "payload_training_corr=%.6f payload_training_residual=%.6f "
                        "coarse_cfo_hz=%.3f fine_cfo_hz=%.3f total_cfo_hz=%.3f "
                        "fractional_timing_samples=%.6f cfo_finite=%d cfo_in_range=%d "
                        "attempts=%zu fidelity=%s rx_clipped=%d\n",
                        fr.selection_id, rec.computed ? 1 : 0, rec.valid ? 1 : 0,
                        iqrfrec::failure_token(rec.failure), corr, residual,
                        coarse_cfo_hz, fine_cfo_hz, total_cfo_hz,
                        ccr.fractional_timing_samples, cfo_finite ? 1 : 0,
                        cfo_in_range ? 1 : 0, capture_attempts, rf_verdict.c_str(),
                        rx_clipped ? 1 : 0);
            std::fflush(stdout);

            if (rx_clipped) rep.any_rx_clip = true;

            // ---- hard_invalid / forceable (contract §4: hard_invalid = 1 iff
            //      irrecoverable = clip / residual > 0.30 / estimator-failed / infra;
            //      forceable = gate-reject with ONLY a moderate payload-training
            //      residual in (0.100, 0.30].  NEVER forced to success.) ----
            const bool gated = (rf_verdict == "RF_PRESERVES_IQ");
            const bool residual_reject =
                (rec.failure == iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH);
            const bool forceable =
                (!gated) && residual_reject && (residual <= kHardInvalidResidualCeiling);
            const bool hard_invalid = (!gated) && (!forceable);

            // ---- per-sample raw capture + recovery diagnostics (ALL samples: gated
            //      AND gate-reject/hard-invalid; never skipped, so an offline reviewer
            //      can re-run recovery/classification on the EXACT captured IQ instead
            //      of re-collecting).  Gate-reject / hard-invalid frames stay in the
            //      denominator. ----
            {
                const std::string raw_path = join_path(rep.recovered_dir,
                    std::to_string(fr.selection_id) + ".raw.i16");
                std::ofstream rraw(raw_path, std::ios::binary);
                if (!rraw)
                    throw std::runtime_error("radioml-dualsdr-ab: cannot open " + raw_path);
                rraw.write(reinterpret_cast<const char*>(rx_int16.data()),
                           static_cast<std::streamsize>(
                               rx_int16.size() * sizeof(std::int16_t)));
                rraw.close();

                const std::string diag_path = join_path(rep.recovered_dir,
                    std::to_string(fr.selection_id) + ".diag.json");
                std::ofstream rdiag(diag_path, std::ios::binary);
                if (!rdiag)
                    throw std::runtime_error("radioml-dualsdr-ab: cannot open " + diag_path);
                rdiag << "{\n";
                rdiag << "  \"selection_id\":" << fr.selection_id << ",\n";
                rdiag << "  \"hdf5_row_index\":" << fr.hdf5_row_index << ",\n";
                rdiag << "  \"raw24_class\":" << fr.raw24_class << ",\n";
                rdiag << "  \"dataset_snr_db\":" << fr.dataset_snr_db << ",\n";
                rdiag << "  \"modulation\":\"" << json_escape(fr.modulation) << "\",\n";
                rdiag << "  \"gated\":" << (gated ? 1 : 0) << ",\n";
                rdiag << "  \"fidelity\":\"" << json_escape(rf_verdict) << "\",\n";
                rdiag << "  \"failure\":\"" << iqrfrec::failure_token(rec.failure) << "\",\n";
                rdiag << "  \"recovery_computed\":" << (rec.computed ? 1 : 0) << ",\n";
                rdiag << "  \"recovery_valid\":" << (rec.valid ? 1 : 0) << ",\n";
                rdiag << "  \"payload_training_corr\":" << json_number(corr) << ",\n";
                rdiag << "  \"payload_training_residual\":" << json_number(residual) << ",\n";
                rdiag << "  \"coarse_cfo_hz\":" << json_number(coarse_cfo_hz) << ",\n";
                rdiag << "  \"fine_cfo_hz\":" << json_number(fine_cfo_hz) << ",\n";
                rdiag << "  \"total_cfo_hz\":" << json_number(total_cfo_hz) << ",\n";
                rdiag << "  \"fractional_timing_samples\":"
                      << json_number(ccr.fractional_timing_samples) << ",\n";
                rdiag << "  \"cfo_finite\":" << (cfo_finite ? 1 : 0) << ",\n";
                rdiag << "  \"cfo_in_range\":" << (cfo_in_range ? 1 : 0) << ",\n";
                rdiag << "  \"rx_clipped\":" << (rx_clipped ? 1 : 0) << ",\n";
                rdiag << "  \"noise_clipped\":" << (noise_clipped ? 1 : 0) << ",\n";
                rdiag << "  \"capture_attempts\":" << capture_attempts << ",\n";
                rdiag << "  \"gate_reject\":" << (gated ? 0 : 1) << ",\n";
                rdiag << "  \"hard_invalid\":" << (hard_invalid ? 1 : 0) << ",\n";
                rdiag << "  \"forceable\":" << (forceable ? 1 : 0) << ",\n";
                rdiag << "  \"tx_stop_ok\":" << (frame_tx_stop_ok ? 1 : 0) << ",\n";
                rdiag << "  \"raw_capture_bytes\":"
                      << (rx_int16.size() * sizeof(std::int16_t)) << ",\n";
                rdiag << "  \"raw_capture_file\":\""
                      << std::to_string(fr.selection_id) << ".raw.i16\"\n";
                rdiag << "}\n";
                rdiag.close();
            }

            int board_pred = -1;
            bool finite = false;
            int raw_top = -1;
            int raw_top_b = -1;

            if (gated) {
                // ---- 8. model window = recovered payload[:1024] * unscale (planar
                //      [2,1024] f32), then NPU x2 -> raw24 (no merge).  This is the
                //      `direct` adaptation path; the DC fork's `dc-transport` branches
                //      here (see the header note above). ----
                const std::vector<std::complex<double>>& payload = ccr.payload;
                std::vector<float> tensor(chain::kTensorFloats);
                for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
                    tensor[k] = static_cast<float>(payload[k].real() * fr.unscale);
                    tensor[chain::kFrameComplex + k] =
                        static_cast<float>(payload[k].imag() * fr.unscale);
                }

                // Save the recovered model input (<sid>.recovered.bin == [2,1024] f32).
                {
                    const std::string rp = join_path(rep.recovered_dir,
                        std::to_string(fr.selection_id) + ".recovered.bin");
                    std::ofstream rf(rp, std::ios::binary);
                    if (!rf)
                        throw std::runtime_error("radioml-dualsdr-ab: cannot open " + rp);
                    rf.write(reinterpret_cast<const char*>(tensor.data()),
                             static_cast<std::streamsize>(
                                 tensor.size() * sizeof(float)));
                }

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
                finite = ok && ok2;
                if (!finite) ++rep.nan_or_inf;

                raw_top = ok ? pr.raw_24_top1 : -1;
                raw_top_b = ok2 ? pr2.raw_24_top1 : -1;
                const bool repeat_det = finite && (raw_top == raw_top_b);
                if (repeat_det) ++rep.repeat_deterministic;

                board_pred = finite ? raw_top : -1;
                const bool correct = finite && (raw_top == fr.raw24_class);

                std::printf("RADIOML_ORIGINAL_DUALSDR_AB_CLASSIFY selection_id=%d "
                            "host_pred=%d board_pred=%d source_label=%d "
                            "label_correct=%d repeat_deterministic=%d finite=%d\n",
                            fr.selection_id, fr.host_pred, board_pred, fr.raw24_class,
                            correct ? 1 : 0, repeat_det ? 1 : 0, finite ? 1 : 0);
                std::fflush(stdout);

                ++global_frame_id;
                rf::ResultFrame r;
                r.frame_id = global_frame_id;
                r.timestamp_us = global_frame_id * 8000ULL;
                r.source = "radioml_original_dualsdr_ab";
                r.mock = false;
                chain::fill_result_rml24(r, raw24, contract, rep.model_sha,
                                         std::numeric_limits<double>::quiet_NaN());
                r.classify_us = classify_us;
                r.e2e_us = classify_us + classify2_us;
                on_frame(r);

                ++rep.scored;
                if (finite) ++rep.finite_count;
                if (correct) ++rep.total_correct;
                if (finite && raw_top >= 0 && raw_top < rml24::kClassCount) {
                    ++rep.confusion[static_cast<std::size_t>(fr.raw24_class) *
                                        rml24::kClassCount + raw_top];
                }
                ++rep.class_total[static_cast<std::size_t>(fr.raw24_class)];
                if (correct) ++rep.class_correct[static_cast<std::size_t>(fr.raw24_class)];

                logits << fr.selection_id << "\t" << fr.hdf5_row_index << "\t"
                       << fr.raw24_class;
                for (int c = 0; c < rml24::kClassCount; ++c)
                    logits << "\t" << raw24[static_cast<std::size_t>(c)];
                logits << "\t" << raw_top << "\t" << raw_top_b << "\n";
            } else {
                ++rep.gate_reject;
                if (hard_invalid) ++rep.hard_invalid; else ++rep.forceable;
                std::printf("RADIOML_ORIGINAL_DUALSDR_AB_FILE selection_id=%d "
                            "classification=SKIPPED reason=fidelity_gate fidelity=%s "
                            "hard_invalid=%d forceable=%d\n",
                            fr.selection_id, rf_verdict.c_str(), hard_invalid ? 1 : 0,
                            forceable ? 1 : 0);
                std::fflush(stdout);
            }

            // ---- 19-col row (rx_restore_ok appended at write time) ----
            {
                std::string line;
                line += std::to_string(fr.selection_id) + "\t";
                line += std::to_string(fr.hdf5_row_index) + "\t";
                line += std::to_string(fr.raw24_class) + "\t";
                line += std::to_string(fr.dataset_snr_db) + "\t";
                line += std::to_string(gated ? 1 : 0) + "\t";
                line += std::to_string(board_pred) + "\t";
                line += std::to_string(finite ? 1 : 0) + "\t";
                {
                    char b[64];
                    std::snprintf(b, sizeof(b), "%.9g", residual);
                    line += b; line += "\t";
                    std::snprintf(b, sizeof(b), "%.9g", corr);
                    line += b; line += "\t";
                    std::snprintf(b, sizeof(b), "%.9g", coarse_cfo_hz);
                    line += b; line += "\t";
                    std::snprintf(b, sizeof(b), "%.9g", fine_cfo_hz);
                    line += b; line += "\t";
                    std::snprintf(b, sizeof(b), "%.9g", total_cfo_hz);
                    line += b; line += "\t";
                    std::snprintf(b, sizeof(b), "%.9g", ccr.fractional_timing_samples);
                    line += b; line += "\t";
                }
                line += std::to_string(rx_clipped ? 1 : 0) + "\t";
                line += std::to_string(capture_attempts) + "\t";
                line += std::to_string(gated ? 0 : 1) + "\t";
                line += std::to_string(hard_invalid ? 1 : 0) + "\t";
                line += std::to_string(frame_tx_stop_ok ? 1 : 0);
                row_lines.push_back(std::move(line));
            }
        }
        logits.close();

        rep.negative_control_ok = !neg_any_fail;
        rep.tx_restore_ok = !tx_restore_any_fail;
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // Always close the control channel (the PC treats a clean close as session end).
    if (client.connected()) {
        std::string perr;
        iqpctbrx::send_abort(client, sess, "board_done", &perr);
        client.close();
    }

    // ---- single-device (RX-only) exit cleanup: guard->restore() -> record the
    //      restore result.  The board owns no TX, so rx_restore_ok is the ONE
    //      DeviceStateGuard restore. ----
    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- write the 19-col board_results.tsv with the FINAL rx_restore_ok ----
    {
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("radioml-dualsdr-ab: cannot open " +
                                     rep.results_path);
        results << board_results_header() << "\n";
        const std::string rx_restore = std::to_string(rep.restore_ok ? 1 : 0);
        for (const auto& line : row_lines)
            results << line << "\t" << rx_restore << "\n";
    }

    // ---- the A/B metrics (measurement; never a regression PASS) ----
    const double total = static_cast<double>(rep.frames_selected);
    const double gated_accuracy = rep.scored > 0
        ? static_cast<double>(rep.total_correct) / static_cast<double>(rep.scored)
        : 0.0;
    const double end_to_end_accuracy = total > 0
        ? static_cast<double>(rep.total_correct) / total : 0.0;
    const double coverage = total > 0
        ? static_cast<double>(rep.scored) / total : 0.0;

    // Summary JSON.
    {
        std::ofstream f(rep.summary_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.summary_path);
        const bool complete = rep.error.empty() && rep.sample_rate_ok &&
                              rep.scored + rep.gate_reject == rep.frames_selected;
        const std::string measurement_token =
            complete ? kMeasurementComplete : kMeasurementIncomplete;
        f << "{\n";
        f << "  \"token\":\"M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DUALSDR-AB1-MEASUREMENT\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"deployment_mode\":\"" << rml24::kDeploymentMode << "\",\n";
        f << "  \"model_mode\":\"" << rml24::kModelMode << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"input_dir\":\"" << json_escape(rep.input_dir) << "\",\n";
        f << "  \"input_kind\":\"" << json_escape(rep.input_kind) << "\",\n";
        f << "  \"out_dir\":\"" << json_escape(rep.out_dir) << "\",\n";
        f << "  \"tx_control\":\"" << json_escape(rep.tx_control) << "\",\n";
        f << "  \"mode\":\"" << json_escape(rep.mode) << "\",\n";
        f << "  \"frames_selected\":" << rep.frames_selected << ",\n";
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"gate_reject\":" << rep.gate_reject << ",\n";
        f << "  \"hard_invalid\":" << rep.hard_invalid << ",\n";
        f << "  \"forceable\":" << rep.forceable << ",\n";
        f << "  \"finite_count\":" << rep.finite_count << ",\n";
        f << "  \"nan_or_inf\":" << rep.nan_or_inf << ",\n";
        f << "  \"repeat_deterministic\":" << rep.repeat_deterministic << ",\n";
        f << "  \"total_correct\":" << rep.total_correct << ",\n";
        f << "  \"coverage\":" << coverage << ",\n";
        f << "  \"gated_accuracy\":" << gated_accuracy << ",\n";
        f << "  \"end_to_end_accuracy\":" << end_to_end_accuracy << ",\n";
        f << "  \"board_never_forces\":true,\n";
        f << "  \"negative_control_ok\":" << (rep.negative_control_ok ? "true" : "false") << ",\n";
        f << "  \"tx_restore_ok\":" << (rep.tx_restore_ok ? "true" : "false") << ",\n";
        f << "  \"rx_restore_ok\":" << (rep.restore_ok ? "true" : "false") << ",\n";
        f << "  \"restore_single_device\":true,\n";
        f << "  \"any_rx_clip\":" << (rep.any_rx_clip ? "true" : "false") << ",\n";
        f << "  \"sample_rate_ok\":" << (rep.sample_rate_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rate\":" << rep.requested_rate << ",\n";
        f << "  \"rx_rate\":" << rep.rx_rate << ",\n";
        f << "  \"rx_lo_ok\":" << (rep.rx_lo_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rx_bw\":" << rep.requested_rx_bw << ",\n";
        f << "  \"rx_bw_readback\":" << rep.rx_bw_readback << ",\n";
        f << "  \"rx_bw_ok\":" << (rep.rx_bw_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rx_gain\":" << rep.requested_rx_gain << ",\n";
        f << "  \"rx_gain_readback\":" << rep.rx_gain_readback << ",\n";
        f << "  \"rx_gain_ok\":" << (rep.rx_gain_ok ? "true" : "false") << ",\n";
        f << "  \"rf_path\":\"direct-cable\"\n";
        f << "}\n";
    }

    std::printf("ROUTE_F_RADIOML_ORIGINAL_DUALSDR_AB mode=%s frames=%llu scored=%llu "
                "gate_reject=%llu hard_invalid=%llu forceable=%llu total_correct=%llu "
                "coverage=%.4f gated_accuracy=%.4f end_to_end_accuracy=%.4f "
                "repeat_deterministic=%llu/%llu nan_or_inf=%llu "
                "negative_control=%s tx_restore_ok=%d rx_restore_ok=%d\n",
                rep.mode.c_str(),
                static_cast<unsigned long long>(rep.frames_selected),
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.gate_reject),
                static_cast<unsigned long long>(rep.hard_invalid),
                static_cast<unsigned long long>(rep.forceable),
                static_cast<unsigned long long>(rep.total_correct),
                coverage, gated_accuracy, end_to_end_accuracy,
                static_cast<unsigned long long>(rep.repeat_deterministic),
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.nan_or_inf),
                rep.negative_control_ok ? "PASS" : "FAIL",
                rep.tx_restore_ok ? 1 : 0, rep.restore_ok ? 1 : 0);
    std::fflush(stdout);

    // ---- functional pass = the measurement infrastructure ran cleanly (NOT the
    //      classification accuracy, which is the A/B measurement the metrics report).
    //      A clean short24/full480 run is a SUCCESSFUL measurement. ----
    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          rep.rx_lo_ok && rep.rx_bw_ok && rep.rx_gain_ok &&
                          !frames.empty() && all_capture_ok;
    const bool control_ok = rep.negative_control_ok && rep.tx_restore_ok &&
                            rep.restore_ok;
    rep.functional_pass = infra_ok && control_ok;

    std::string detail = "mode=" + rep.mode +
                         " frames=" + std::to_string(rep.frames_selected) +
                         " scored=" + std::to_string(rep.scored) +
                         " gate_reject=" + std::to_string(rep.gate_reject) +
                         " hard_invalid=" + std::to_string(rep.hard_invalid) +
                         " forceable=" + std::to_string(rep.forceable) +
                         " total_correct=" + std::to_string(rep.total_correct) +
                         " coverage=" + std::to_string(coverage) +
                         " gated_accuracy=" + std::to_string(gated_accuracy) +
                         " end_to_end_accuracy=" + std::to_string(end_to_end_accuracy) +
                         " repeat_deterministic=" +
                             std::to_string(rep.repeat_deterministic) +
                         "/" + std::to_string(rep.scored) +
                         " nan_or_inf=" + std::to_string(rep.nan_or_inf) +
                         " negative_control=" +
                             (rep.negative_control_ok ? "PASS" : "FAIL") +
                         " tx_restore_ok=" + (rep.tx_restore_ok ? "1" : "0") +
                         " rx_restore_ok=" + (rep.restore_ok ? "1" : "0") +
                         " (single_device_restore)" +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " requested_rx_bw=" + std::to_string(rep.requested_rx_bw) +
                         " rx_bw_readback=" + std::to_string(rep.rx_bw_readback) +
                         " requested_rx_gain=" + std::to_string(rep.requested_rx_gain) +
                         " rx_gain_readback=" + std::to_string(rep.rx_gain_readback) +
                         " rf_path=direct-cable";
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

}  // namespace rmldsab
