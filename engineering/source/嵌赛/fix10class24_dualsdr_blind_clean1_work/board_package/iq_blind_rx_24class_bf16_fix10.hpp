#pragma once

// iq_blind_rx_24class_bf16_fix10.hpp -- task fix10class24-dualsdr-blind-clean1:
// the BLIND (no-sample-prior) board runner.  The Windows PC owns the TX SDR and
// transmits a PURE-modulated 24-class RadioML2018.01A clean waveform (no training
// frame, no preamble, no tail, no canonical burst) over 50-ohm coax; the board owns
// the RX SDR and classifies it with ONLY the received IQ + the frozen BF16 model +
// a frozen reconstruction scale + a frozen window rule.  The receiver NEVER sees the
// transmitted sample, its DC/scale, its correct window, or its label.
//
// This runner is RX-ONLY (no TX device is ever opened, no local TX, no
// loopback==0 toggle).  It is a MEASUREMENT (ROUTE_F_RADIOML_BLIND_CLEAN1_* tokens),
// never a regression PASS, and the board NEVER forces a classification.
//
// Minimal fixed processing (the sampling contract):
//   flush   kBlindFlushComplex complex samples (kBlindFlushRefills refills, settle)
//   capture kBlindCaptureComplex complex samples in ONE contiguous RX refill
//   window  [kBlindWindowOffset, +kBlindWindowComplex)  == 1024 complex
//   tensor  z[k] = int16[k]/adc_full_scale * kBlindRxScale   (planar [2,1024] f32)
//   infer   frozen BF16 NPU x2 -> raw24 argmax (NO merge)
//
// There is NO recovery path, NO fidelity gate, NO per-label branch, NO window
// selection by reference matching, and NO CFO/timing estimation (documented NA).
// training_residual=NA and training_gate=NOT_APPLICABLE are emitted on every row.
//
// The board talks to the PC over a minimal TCP control channel (board = CLIENT):
//   HELLO -> HELLO_ACK -> [TRANSMIT -> TX_READY -> capture+infer -> CAPTURED ->
//   CAPTURED_ACK] x25 -> STOP -> STOP_ACK.  source_index is the ONLY correlation key
//   the board knows (0 = negative control / TX-off, 1..24 = waveform ordinal); the
//   class NEVER crosses the control channel toward the board.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback_sync.hpp"    // iqdloop_sync::rail_positive / rail_negative
#include "rml24_raw.hpp"                    // rml24::raw24_predict (NO merge)
#include "rf_fix_helpers.hpp"               // rf_fix::rf_readback_close (bw fail-closed)
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/device_state_guard.hpp"
#include "../sdr_adapter/tcp_control_client.hpp"   // iqpctbrx::TcpControlClient + Json
#include "../sdr_adapter/sha256.hpp"                // sdr::Sha256

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
#include <memory>
#include <string>
#include <vector>

namespace rmlblind {

using Clock = std::chrono::steady_clock;
using SysClock = std::chrono::system_clock;

// fix10class24-dualsdr-blind-clean1 measurement tokens (never a PASS).
constexpr const char* kMeasurementComplete =
    "ROUTE_F_RADIOML_BLIND_CLEAN1_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete =
    "ROUTE_F_RADIOML_BLIND_CLEAN1_MEASUREMENT_INCOMPLETE";

// ---- frozen sampling constants (authority: contract/blind_rx_sampling_contract.json) ----
constexpr double kBlindAdcFullScale = 2048.0;
constexpr double kBlindTxScale = 117.84922023433009;      // S = 1600 / max_peak
constexpr double kBlindRxScale = 17.37813789457223;       // = adc_full_scale / S
constexpr std::size_t kBlindFlushComplex = 4096;          // per refill
constexpr std::size_t kBlindFlushRefills = 2;             // total flushed = 2 x 4096
constexpr std::size_t kBlindCaptureComplex = 2048;        // ONE contiguous refill
constexpr std::size_t kBlindWindowComplex = 1024;         // == chain::kFrameComplex
constexpr std::size_t kBlindWindowOffset = 512;           // [512, 1536) of the capture
constexpr std::uint64_t kBlindDefaultMeasurements = 25;   // 1 negative + 24 waveforms
constexpr std::uint64_t kBlindCenterHz = 2400000000ULL;
constexpr std::uint64_t kBlindSampleRate = 2560000ULL;
constexpr std::uint64_t kBlindRxBw = 18000000ULL;
constexpr double kBlindRxGain = 35.0;

constexpr const char* kTrainingResidualNA = "NA";
constexpr const char* kTrainingGateNotApplicable = "NOT_APPLICABLE";

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

inline std::uint64_t now_epoch_us() {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(
            SysClock::now().time_since_epoch()).count());
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

inline std::string to_hex_u64(std::uint64_t v) {
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%016llx",
                  static_cast<unsigned long long>(v));
    return std::string(buf);
}

// Anonymous run id: time-derived, NEVER encodes the class.  session_id + run_nonce
// are generated here, sent in HELLO, echoed by the PC, and written into every record
// so the offline judger can correlate the board rows with the PC TX record.
struct RunId {
    std::string session_id;
    std::string run_nonce;
    std::string joined() const { return session_id + "_" + run_nonce; }
};

inline RunId make_run_id() {
    const std::uint64_t us = now_epoch_us();
    RunId r;
    r.session_id = "blind-" + to_hex_u64(us);
    // Mix the epoch microseconds through a fixed splitmix64 finalizer so the nonce
    // is not a trivial copy of the session id (still class-blind: it is time only).
    std::uint64_t z = us + 0x9E3779B97F4A7C15ULL;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    z = z ^ (z >> 31);
    r.run_nonce = to_hex_u64(z);
    return r;
}

// ---------------------------------------------------------------------------
// BlindRunReport
// ---------------------------------------------------------------------------
struct BlindRunReport {
    std::string model_sha;
    std::string out_dir;
    std::string tx_control;                  // tcp://host:port
    std::string run_id;
    std::string session_id;
    std::string run_nonce;
    std::uint64_t measurements = kBlindDefaultMeasurements;

    std::uint64_t completed = 0;             // samples that produced a record row
    std::uint64_t scored = 0;                // finite classifications produced
    std::uint64_t finite_count = 0;
    std::uint64_t nan_or_inf = 0;
    std::uint64_t repeat_deterministic = 0;
    bool any_rx_clip = false;

    bool device_not_found = false;
    std::string error;

    // RX frontend write-then-readback (ALL fail-closed).
    long long requested_rate = 0;
    long long rx_rate = 0;
    bool sample_rate_ok = false;
    long long requested_rx_bw = 0;
    long long rx_bw_readback = 0;
    bool rx_bw_ok = false;
    double requested_rx_gain = 0.0;
    double rx_gain_readback = 0.0;
    bool rx_gain_ok = false;
    long long rx_lo_readback = 0;
    bool rx_lo_ok = false;

    bool restore_ok = false;
    std::string restore_report;

    // control evidence
    bool control_ok = false;                 // full HELLO..STOP handshake completed
    bool negative_control_ok = false;        // source_index 0 captured with tx_active=false

    std::string results_path;
    std::string logits_path;
    std::string recovered_dir;
    std::string summary_path;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// The exact 22-column board_results.tsv header (blind; NO label columns -- the board
// never knows the class).
inline const char* board_results_header() {
    return "run_id\tsource_index\tcapture_time_us\tfinite\trepeat_deterministic\t"
           "raw24_pred\traw24_margin\tclip\toverflow\tdropped\tdiscontinuity\t"
           "short_block\ttimeouts\ttraining_residual\ttraining_gate\t"
           "model_input_sha256\tmodel_sha\trx_sample_rate\trx_lo\trx_bw\t"
           "rx_gain\tstatus";
}

// ---------------------------------------------------------------------------
// Minimal blind control-channel state machine (board = CLIENT).
// ---------------------------------------------------------------------------
struct BlindControl {
    iqpctbrx::TcpControlClient client;
    bool ok = false;
    std::string error;

    // Build and send a JSON object message; fail-closed on any send error.
    bool send_object(const std::vector<std::pair<std::string, iqpctbrx::Json>>& fields,
                     const char* what) {
        const iqpctbrx::Json msg = iqpctbrx::Json::make_object(fields);
        std::string err;
        if (!client.send_json(msg, &err)) {
            error = std::string(what) + " send failed: " + err;
            return false;
        }
        return true;
    }

    // Receive one message and parse it; fail-closed on any recv/parse error.
    bool recv_object(iqpctbrx::Json& out, const char* what) {
        std::string json;
        std::string err;
        if (!client.recv_json(json, &err)) {
            error = std::string(what) + " recv failed: " + err;
            return false;
        }
        const iqpctbrx::JsonParseResult pr = iqpctbrx::json_parse(json);
        if (!pr.ok) {
            error = std::string(what) + " parse failed: " + pr.error;
            return false;
        }
        out = pr.value;
        return true;
    }

    bool require_string(const iqpctbrx::Json& o, const char* key, std::string& out) {
        const iqpctbrx::Json* v = o.get(key);
        if (v == nullptr || !v->is_string()) {
            error = std::string("missing/incorrect '") + key + "' field";
            return false;
        }
        out = v->as_string();
        return true;
    }

    bool require_number(const iqpctbrx::Json& o, const char* key, double& out) {
        const iqpctbrx::Json* v = o.get(key);
        if (v == nullptr || !v->is_number()) {
            error = std::string("missing/incorrect '") + key + "' field";
            return false;
        }
        out = v->as_number();
        return true;
    }

    bool require_bool(const iqpctbrx::Json& o, const char* key, bool& out) {
        const iqpctbrx::Json* v = o.get(key);
        if (v == nullptr || !v->is_bool()) {
            error = std::string("missing/incorrect '") + key + "' field";
            return false;
        }
        out = v->as_bool();
        return true;
    }

    // HELLO handshake.  Board sends session/run identity + fixed config; PC echoes
    // session_id + run_nonce + measurements and must agree (fail-closed otherwise).
    bool hello(const std::string& session_id, const std::string& run_nonce,
               std::uint64_t measurements) {
        if (!send_object({
                {"type", iqpctbrx::Json::make_string("hello")},
                {"protocol_version", iqpctbrx::Json::make_number(1)},
                {"session_id", iqpctbrx::Json::make_string(session_id)},
                {"run_nonce", iqpctbrx::Json::make_string(run_nonce)},
                {"measurements", iqpctbrx::Json::make_number(
                     static_cast<double>(measurements))},
                {"sample_rate", iqpctbrx::Json::make_number(
                     static_cast<double>(kBlindSampleRate))},
                {"center_hz", iqpctbrx::Json::make_number(
                     static_cast<double>(kBlindCenterHz))},
                {"rx_bw", iqpctbrx::Json::make_number(
                     static_cast<double>(kBlindRxBw))},
                {"flush", iqpctbrx::Json::make_number(
                     static_cast<double>(kBlindFlushComplex))},
                {"capture", iqpctbrx::Json::make_number(
                     static_cast<double>(kBlindCaptureComplex))},
                {"window_offset", iqpctbrx::Json::make_number(
                     static_cast<double>(kBlindWindowOffset))},
            }, "hello"))
            return false;

        iqpctbrx::Json ack;
        if (!recv_object(ack, "hello_ack")) return false;
        std::string sid, rn;
        double meas = 0.0;
        bool okflag = false;
        if (!require_string(ack, "session_id", sid) ||
            !require_string(ack, "run_nonce", rn) ||
            !require_number(ack, "measurements", meas) ||
            !require_bool(ack, "ok", okflag)) {
            error = "hello_ack field error: " + error;
            return false;
        }
        if (sid != session_id || rn != run_nonce) {
            error = "hello_ack identity mismatch";
            return false;
        }
        if (static_cast<std::uint64_t>(std::llround(meas)) != measurements) {
            error = "hello_ack measurements mismatch";
            return false;
        }
        if (!okflag) {
            error = "hello_ack rejected (ok=false)";
            return false;
        }
        return true;
    }

    // TRANSMIT -> TX_READY.  Returns tx_active (false for negative control) and the
    // PC's file_sha256.  Fail-closed on any mismatch or protocol error.
    bool transmit(std::uint64_t source_index, bool& tx_active,
                  std::string& file_sha256) {
        if (!send_object({
                {"type", iqpctbrx::Json::make_string("transmit")},
                {"source_index", iqpctbrx::Json::make_number(
                     static_cast<double>(source_index))},
            }, "transmit"))
            return false;

        iqpctbrx::Json ready;
        if (!recv_object(ready, "tx_ready")) return false;
        double sid = 0.0;
        bool active = false;
        std::string sha;
        if (!require_number(ready, "source_index", sid) ||
            !require_bool(ready, "tx_active", active) ||
            !require_string(ready, "file_sha256", sha)) {
            error = "tx_ready field error: " + error;
            return false;
        }
        if (static_cast<std::uint64_t>(std::llround(sid)) != source_index) {
            error = "tx_ready source_index mismatch";
            return false;
        }
        if (source_index == 0 && active) {
            error = "tx_ready claims tx_active for the negative control (source_index 0)";
            return false;
        }
        tx_active = active;
        file_sha256 = sha;
        return true;
    }

    // CAPTURED -> CAPTURED_ACK.
    bool captured(std::uint64_t source_index) {
        if (!send_object({
                {"type", iqpctbrx::Json::make_string("captured")},
                {"source_index", iqpctbrx::Json::make_number(
                     static_cast<double>(source_index))},
            }, "captured"))
            return false;
        iqpctbrx::Json ack;
        if (!recv_object(ack, "captured_ack")) return false;
        double sid = 0.0;
        if (!require_number(ack, "source_index", sid) ||
            static_cast<std::uint64_t>(std::llround(sid)) != source_index) {
            error = "captured_ack source_index mismatch";
            return false;
        }
        return true;
    }

    // STOP -> STOP_ACK.
    bool stop() {
        if (!send_object({
                {"type", iqpctbrx::Json::make_string("stop")},
            }, "stop"))
            return false;
        iqpctbrx::Json ack;
        if (!recv_object(ack, "stop_ack")) return false;
        return true;
    }
};

// ---------------------------------------------------------------------------
// run_iq_blind_rx_24class_bf16_fix10
// ---------------------------------------------------------------------------
inline BlindRunReport run_iq_blind_rx_24class_bf16_fix10(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    BlindRunReport rep;

    // ---- args ----
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    rep.tx_control = board::get_opt(argc, argv, "--tx-control", "");
    if (rep.tx_control.empty())
        throw std::runtime_error("iq-blind-rx requires --tx-control=tcp://<pc-host>:<port>");
    rep.out_dir = board::get_opt(argc, argv, "--out-dir", "");
    const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rx_uri.empty())
        throw std::runtime_error("iq-blind-rx requires --rx-uri=<board RX SDR uri>");

    rep.measurements = board::opt_u64(argc, argv, "--measurements",
                                      kBlindDefaultMeasurements);
    if (rep.measurements != kBlindDefaultMeasurements)
        throw std::runtime_error("iq-blind-rx requires --measurements=25 "
                                 "(1 negative + 24 waveforms); got " +
                                 std::to_string(rep.measurements) + ".");

    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", kBlindCenterHz);
    const long long sample_rate = static_cast<long long>(
        board::opt_u64(argc, argv, "--sample-rate", kBlindSampleRate));
    if (sample_rate != static_cast<long long>(kBlindSampleRate))
        throw std::runtime_error("iq-blind-rx requires --sample-rate=2560000 (2.56 Msps); "
                                 "got " + std::to_string(sample_rate) + ".");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", kBlindRxGain);
    const long long rx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-bw", kBlindRxBw));

    // RF safety: the RX SDR is on the 50-ohm direct cable (PC TX -> coax -> board RX).
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error("iq-blind-rx requires --rf-path=direct-cable "
                                 "(50-ohm SMA coax, no antenna, no amplifier). Got '" +
                                 rf_path + "'.");

    // ---- anonymous run id (never encodes class) ----
    const RunId run = make_run_id();
    rep.session_id = run.session_id;
    rep.run_nonce = run.run_nonce;
    rep.run_id = run.joined();

    // ---- fail-closed out dir: never overwrite an existing directory ----
    if (rep.out_dir.empty())
        throw std::runtime_error("iq-blind-rx requires --out-dir=<fresh dir>");
    {
        struct stat st;
        if (::stat(rep.out_dir.c_str(), &st) == 0)
            throw std::runtime_error("iq-blind-rx: --out-dir already exists: " +
                                     rep.out_dir +
                                     " (refusing to overwrite; use a fresh timestamped dir)");
        if (::mkdir(rep.out_dir.c_str(), 0777) != 0)
            throw std::runtime_error("iq-blind-rx: cannot create --out-dir " +
                                     rep.out_dir + ": " + std::strerror(errno));
    }

    rep.results_path = join_path(rep.out_dir, "board_results.tsv");
    rep.logits_path = join_path(rep.out_dir, "board_logits.tsv");
    rep.recovered_dir = join_path(rep.out_dir, "recovered");
    rep.summary_path = join_path(rep.out_dir, "board_summary.json");

    const cat::Contract contract = chain::contract_24();

    std::printf("RADIOML_BLIND_CLEAN1_START run_id=%s tx_control=%s rx_uri=%s "
                "measurements=%llu center_hz=%llu sample_rate=%lld rx_gain=%.3f "
                "rx_bw=%lld model_sha=%s out_dir=%s\n",
                rep.run_id.c_str(), rep.tx_control.c_str(), rx_uri.c_str(),
                static_cast<unsigned long long>(rep.measurements),
                static_cast<unsigned long long>(center_hz),
                static_cast<long long>(sample_rate), gain_db,
                static_cast<long long>(rx_bw), rep.model_sha.c_str(),
                rep.out_dir.c_str());
    std::fflush(stdout);

    // ---- device open (RX-only; device-not-found is exit code 2) ----
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
    // Rows must survive the capture try/catch: they are written after restore.
    std::vector<std::string> row_lines;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate: force 2560000, fail-closed abs(delta)<=5 Hz ----
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(sample_rate);
        }
        rep.requested_rate = sample_rate;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.sample_rate_ok = std::llabs(rep.rx_rate - sample_rate) <= 5;
        if (!rep.sample_rate_ok)
            throw std::runtime_error(
                "sample_rate_mismatch: requested=" + std::to_string(sample_rate) +
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
        std::printf("RADIOML_BLIND_CLEAN1_FRONTEND rx_lo=%lld rx_lo_ok=%d "
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
        std::printf("RADIOML_BLIND_CLEAN1_RX_FORMAT %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);
        const int rx_pos_rail = iqdloop_sync::rail_positive(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));
        const int rx_neg_rail = iqdloop_sync::rail_negative(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));

        // ---- TCP control: connect + HELLO handshake (fail-closed) ----
        BlindControl ctl;
        std::string host;
        std::uint16_t port = iqpctbrx::kDefaultPort;
        {
            std::string perr;
            if (!iqpctbrx::parse_tx_control_url(rep.tx_control, host, port, &perr))
                throw std::runtime_error("iq-blind-rx: " + perr);
            ctl.client.host = host;
            ctl.client.port = port;
            std::string cerr;
            if (!ctl.client.connect(&cerr))
                throw std::runtime_error("iq-blind-rx: control connect failed: " + cerr);
            if (!ctl.hello(rep.session_id, rep.run_nonce, rep.measurements))
                throw std::runtime_error("iq-blind-rx: HELLO failed: " + ctl.error);
        }
        std::printf("RADIOML_BLIND_CLEAN1_HELLO_OK run_id=%s host=%s port=%u\n",
                    rep.run_id.c_str(), host.c_str(),
                    static_cast<unsigned>(port));
        std::fflush(stdout);

        // D-level input-transfer audit ON (not strictly needed for blind, but keeps
        // the NPU input path audited for the model_input_sha256 the judger checks).
        npu.set_input_audit(true);

        if (::mkdir(rep.recovered_dir.c_str(), 0777) != 0)
            throw std::runtime_error("iq-blind-rx: cannot create " +
                                     rep.recovered_dir + ": " + std::strerror(errno));

        std::ofstream logits(rep.logits_path, std::ios::binary);
        if (!logits)
            throw std::runtime_error("iq-blind-rx: cannot open " + rep.logits_path);
        logits << "run_id\tsource_index";
        for (int c = 0; c < rml24::kClassCount; ++c)
            logits << "\tlogit_" << (c < 10 ? "0" : "") << c;
        logits << "\tpred_pass1\tpred_pass2\n";

        bool neg_ok = false;

        // ---- one measurement per source_index (0 = negative control) ----
        for (std::uint64_t sid = 0; sid < rep.measurements; ++sid) {
            if (board::g_stop_requested) break;

            const std::uint64_t capture_time_us = now_epoch_us();
            std::printf("RADIOML_BLIND_CLEAN1_SAMPLE source_index=%llu capture_time_us=%llu\n",
                        static_cast<unsigned long long>(sid),
                        static_cast<unsigned long long>(capture_time_us));
            std::fflush(stdout);

            bool tx_active = false;
            std::string file_sha256;
            if (!ctl.transmit(sid, tx_active, file_sha256))
                throw std::runtime_error("iq-blind-rx: TRANSMIT(" +
                                         std::to_string(sid) + ") failed: " + ctl.error);
            std::printf("RADIOML_BLIND_CLEAN1_TX_READY source_index=%llu tx_active=%d "
                        "file_sha256=%s\n",
                        static_cast<unsigned long long>(sid), tx_active ? 1 : 0,
                        file_sha256.c_str());
            std::fflush(stdout);

            // ---- flush (settle) + capture ONE contiguous refill ----
            for (std::size_t d = 0; d < kBlindFlushRefills; ++d) {
                dev->recreate_rx_buffer();
                (void)dev->read_rx(kBlindFlushComplex, 1000);
            }

            board::RxStats st;
            board::Continuity cont;
            std::vector<std::int16_t> iq;
            const bool cap_ok =
                board::capture_contiguous(*dev, kBlindCaptureComplex, iq, st, cont);
            all_capture_ok = all_capture_ok && cap_ok;

            // Save the FULL captured IQ (all samples, before any windowing).
            board::save_raw_iq(
                join_path(rep.recovered_dir, std::to_string(sid) + ".raw.i16"), iq);

            // Clip check over the full capture (12-bit rails).
            bool clipped = false;
            for (std::size_t k = 0; k + 1 < iq.size(); k += 2) {
                const int i = iq[k];
                const int q = iq[k + 1];
                if (i >= rx_pos_rail || i <= rx_neg_rail ||
                    q >= rx_pos_rail || q <= rx_neg_rail) {
                    clipped = true;
                    break;
                }
            }
            if (clipped) rep.any_rx_clip = true;

            const bool window_ok = iq.size() / 2 >=
                kBlindWindowOffset + kBlindWindowComplex;
            if (!window_ok)
                throw std::runtime_error("iq-blind-rx: capture too short for window (" +
                                         std::to_string(iq.size() / 2) + " < " +
                                         std::to_string(kBlindWindowOffset +
                                                        kBlindWindowComplex) + ")");

            // ---- frozen window + frozen reconstruction scale -> [2,1024] f32 ----
            std::vector<float> tensor(chain::kTensorFloats);
            {
                const std::size_t base = kBlindWindowOffset * 2;
                for (std::size_t k = 0; k < kBlindWindowComplex; ++k) {
                    const int ii = iq[base + 2 * k];
                    const int qq = iq[base + 2 * k + 1];
                    tensor[k] = static_cast<float>(
                        static_cast<double>(ii) / kBlindAdcFullScale * kBlindRxScale);
                    tensor[chain::kFrameComplex + k] = static_cast<float>(
                        static_cast<double>(qq) / kBlindAdcFullScale * kBlindRxScale);
                }
            }

            // Save the model input + its SHA (the judger verifies exactly this).
            const std::string model_input_sha =
                sdr::Sha256::hex(tensor.data(), tensor.size() * sizeof(float));
            {
                const std::string tp = join_path(rep.recovered_dir,
                    std::to_string(sid) + ".tensor.bin");
                std::ofstream tf(tp, std::ios::binary);
                if (!tf)
                    throw std::runtime_error("iq-blind-rx: cannot open " + tp);
                tf.write(reinterpret_cast<const char*>(tensor.data()),
                         static_cast<std::streamsize>(tensor.size() * sizeof(float)));
            }

            // ---- infer x2 -> raw24 (NO merge) ----
            std::vector<float> raw24;
            const auto t0 = Clock::now();
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

            const bool clean_stream = cap_ok && cont.ok() && !st.short_block &&
                                      st.overflow == 0 && st.dropped == 0 &&
                                      st.discontinuity == 0;

            std::string status = "ok";
            if (!finite) status = "non_finite";
            else if (!clean_stream) status = "capture_anomaly";
            else if (clipped) status = "rx_clipped";

            std::printf("RADIOML_BLIND_CLEAN1_CLASSIFY source_index=%llu board_pred=%d "
                        "finite=%d repeat_deterministic=%d clip=%d overflow=%llu "
                        "dropped=%llu discontinuity=%llu short_block=%d timeouts=%llu "
                        "single_refill=%d status=%s\n",
                        static_cast<unsigned long long>(sid), raw_top,
                        finite ? 1 : 0, repeat_det ? 1 : 0, clipped ? 1 : 0,
                        static_cast<unsigned long long>(st.overflow),
                        static_cast<unsigned long long>(st.dropped),
                        static_cast<unsigned long long>(st.discontinuity),
                        st.short_block ? 1 : 0,
                        static_cast<unsigned long long>(st.timeouts),
                        cont.ok() ? 1 : 0, status.c_str());
            std::fflush(stdout);

            ++rep.completed;
            if (finite) {
                ++rep.scored;
                ++rep.finite_count;
            }

            // Emit to the result plane (source=blind; no label is attached).
            rf::ResultFrame r;
            r.frame_id = sid;
            r.timestamp_us = capture_time_us;
            r.source = "radioml_blind_clean1";
            r.mock = false;
            chain::fill_result_rml24(r, raw24, contract, rep.model_sha,
                                     std::numeric_limits<double>::quiet_NaN());
            r.classify_us = classify_us;
            r.e2e_us = classify_us + classify2_us;
            on_frame(r);

            // Per-sample diag.json (full detail for the offline judger).
            {
                const std::string dp = join_path(rep.recovered_dir,
                    std::to_string(sid) + ".diag.json");
                std::ofstream df(dp, std::ios::binary);
                if (!df)
                    throw std::runtime_error("iq-blind-rx: cannot open " + dp);
                df << "{\n";
                df << "  \"run_id\":\"" << json_escape(rep.run_id) << "\",\n";
                df << "  \"source_index\":" << sid << ",\n";
                df << "  \"capture_time_us\":" << capture_time_us << ",\n";
                df << "  \"tx_active\":" << (tx_active ? "true" : "false") << ",\n";
                df << "  \"file_sha256\":\"" << json_escape(file_sha256) << "\",\n";
                df << "  \"finite\":" << (finite ? "true" : "false") << ",\n";
                df << "  \"repeat_deterministic\":" << (repeat_det ? "true" : "false") << ",\n";
                df << "  \"raw24_pred\":" << raw_top << ",\n";
                df << "  \"raw24_margin\":" << json_number(ok ? pr.raw_margin : 0.0) << ",\n";
                df << "  \"clip\":" << (clipped ? "true" : "false") << ",\n";
                df << "  \"overflow\":" << st.overflow << ",\n";
                df << "  \"dropped\":" << st.dropped << ",\n";
                df << "  \"discontinuity\":" << st.discontinuity << ",\n";
                df << "  \"short_block\":" << (st.short_block ? "true" : "false") << ",\n";
                df << "  \"timeouts\":" << st.timeouts << ",\n";
                df << "  \"capture_ok\":" << (cap_ok ? "true" : "false") << ",\n";
                df << "  \"single_refill\":" << (cont.ok() ? "true" : "false") << ",\n";
                df << "  \"continuity\":\"" << json_escape(cont.report()) << "\",\n";
                df << "  \"training_residual\":\"" << kTrainingResidualNA << "\",\n";
                df << "  \"training_gate\":\"" << kTrainingGateNotApplicable << "\",\n";
                df << "  \"model_input_sha256\":\"" << model_input_sha << "\",\n";
                df << "  \"model_sha\":\"" << json_escape(rep.model_sha) << "\",\n";
                df << "  \"rx_sample_rate\":" << rep.rx_rate << ",\n";
                df << "  \"rx_lo\":" << rep.rx_lo_readback << ",\n";
                df << "  \"rx_bw\":" << rep.rx_bw_readback << ",\n";
                df << "  \"rx_gain\":" << json_number(rep.rx_gain_readback) << ",\n";
                df << "  \"status\":\"" << json_escape(status) << "\"\n";
                df << "}\n";
            }

            // Logits row.
            logits << rep.run_id << "\t" << sid;
            for (int c = 0; c < rml24::kClassCount; ++c)
                logits << "\t" << raw24[static_cast<std::size_t>(c)];
            logits << "\t" << raw_top << "\t" << raw_top_b << "\n";

            // 22-col results row.
            {
                std::string line;
                line += rep.run_id + "\t";
                line += std::to_string(sid) + "\t";
                line += std::to_string(capture_time_us) + "\t";
                line += std::to_string(finite ? 1 : 0) + "\t";
                line += std::to_string(repeat_det ? 1 : 0) + "\t";
                line += std::to_string(raw_top) + "\t";
                {
                    char b[64];
                    std::snprintf(b, sizeof(b), "%.9g", ok ? pr.raw_margin : 0.0);
                    line += b; line += "\t";
                }
                line += std::to_string(clipped ? 1 : 0) + "\t";
                line += std::to_string(st.overflow) + "\t";
                line += std::to_string(st.dropped) + "\t";
                line += std::to_string(st.discontinuity) + "\t";
                line += std::to_string(st.short_block ? 1 : 0) + "\t";
                line += std::to_string(st.timeouts) + "\t";
                line += std::string(kTrainingResidualNA) + "\t";
                line += std::string(kTrainingGateNotApplicable) + "\t";
                line += model_input_sha + "\t";
                line += rep.model_sha + "\t";
                line += std::to_string(rep.rx_rate) + "\t";
                line += std::to_string(rep.rx_lo_readback) + "\t";
                line += std::to_string(rep.rx_bw_readback) + "\t";
                {
                    char b[64];
                    std::snprintf(b, sizeof(b), "%.3f", rep.rx_gain_readback);
                    line += b; line += "\t";
                }
                line += status;
                row_lines.push_back(std::move(line));
            }

            if (sid == 0) {
                neg_ok = !tx_active && cap_ok && cont.ok();
                rep.negative_control_ok = neg_ok;
                std::printf("RADIOML_BLIND_CLEAN1_NEGATIVE_CONTROL source_index=0 "
                            "tx_active=%d capture_ok=%d single_refill=%d pass=%d\n",
                            tx_active ? 1 : 0, cap_ok ? 1 : 0, cont.ok() ? 1 : 0,
                            neg_ok ? 1 : 0);
                std::fflush(stdout);
            }

            // Tell the PC the capture is done before the next transmit.
            if (!ctl.captured(sid))
                throw std::runtime_error("iq-blind-rx: CAPTURED(" +
                                         std::to_string(sid) + ") failed: " + ctl.error);
        }

        logits.close();

        // ---- STOP handshake ----
        if (!ctl.stop())
            throw std::runtime_error("iq-blind-rx: STOP failed: " + ctl.error);
        rep.control_ok = true;
        std::printf("RADIOML_BLIND_CLEAN1_STOP_OK run_id=%s\n", rep.run_id.c_str());
        std::fflush(stdout);
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // ---- RX-only exit cleanup: guard->restore() ----
    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- write the 22-col board_results.tsv ----
    {
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("iq-blind-rx: cannot open " + rep.results_path);
        results << board_results_header() << "\n";
        for (const auto& line : row_lines)
            results << line << "\n";
    }

    const double total = static_cast<double>(rep.measurements);
    const double coverage = total > 0
        ? static_cast<double>(rep.scored) / total : 0.0;

    // Summary JSON.
    {
        std::ofstream f(rep.summary_path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open " + rep.summary_path);
        const bool complete = rep.error.empty() && rep.sample_rate_ok &&
                              rep.completed == rep.measurements;
        const std::string measurement_token =
            complete ? kMeasurementComplete : kMeasurementIncomplete;
        f << "{\n";
        f << "  \"token\":\"M29-RML24-FIX10CLASS24-DUALSDR-BLIND-CLEAN1-MEASUREMENT\",\n";
        f << "  \"measurement_token\":\"" << measurement_token << "\",\n";
        f << "  \"deployment_mode\":\"" << rml24::kDeploymentMode << "\",\n";
        f << "  \"model_mode\":\"" << rml24::kModelMode << "\",\n";
        f << "  \"model_sha\":\"" << json_escape(rep.model_sha) << "\",\n";
        f << "  \"run_id\":\"" << json_escape(rep.run_id) << "\",\n";
        f << "  \"tx_control\":\"" << json_escape(rep.tx_control) << "\",\n";
        f << "  \"out_dir\":\"" << json_escape(rep.out_dir) << "\",\n";
        f << "  \"measurements\":" << rep.measurements << ",\n";
        f << "  \"completed\":" << rep.completed << ",\n";
        f << "  \"scored\":" << rep.scored << ",\n";
        f << "  \"finite_count\":" << rep.finite_count << ",\n";
        f << "  \"nan_or_inf\":" << rep.nan_or_inf << ",\n";
        f << "  \"repeat_deterministic\":" << rep.repeat_deterministic << ",\n";
        f << "  \"coverage\":" << coverage << ",\n";
        f << "  \"board_never_forces\":true,\n";
        f << "  \"no_label_known_by_board\":true,\n";
        f << "  \"negative_control_ok\":" << (rep.negative_control_ok ? "true" : "false") << ",\n";
        f << "  \"control_ok\":" << (rep.control_ok ? "true" : "false") << ",\n";
        f << "  \"rx_restore_ok\":" << (rep.restore_ok ? "true" : "false") << ",\n";
        f << "  \"any_rx_clip\":" << (rep.any_rx_clip ? "true" : "false") << ",\n";
        f << "  \"sample_rate_ok\":" << (rep.sample_rate_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rate\":" << rep.requested_rate << ",\n";
        f << "  \"rx_rate\":" << rep.rx_rate << ",\n";
        f << "  \"rx_lo_ok\":" << (rep.rx_lo_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rx_bw\":" << rep.requested_rx_bw << ",\n";
        f << "  \"rx_bw_readback\":" << rep.rx_bw_readback << ",\n";
        f << "  \"rx_bw_ok\":" << (rep.rx_bw_ok ? "true" : "false") << ",\n";
        f << "  \"requested_rx_gain\":" << json_number(rep.requested_rx_gain) << ",\n";
        f << "  \"rx_gain_readback\":" << json_number(rep.rx_gain_readback) << ",\n";
        f << "  \"rx_gain_ok\":" << (rep.rx_gain_ok ? "true" : "false") << ",\n";
        f << "  \"rf_path\":\"direct-cable\",\n";
        f << "  \"sampling_contract\":\"M29-RML24-FIX10CLASS24-DUALSDR-BLIND-CLEAN1-SAMPLING-CONTRACT\"\n";
        f << "}\n";
    }

    std::printf("ROUTE_F_RADIOML_BLIND_CLEAN1 run_id=%s measurements=%llu completed=%llu "
                "scored=%llu finite=%llu repeat_deterministic=%llu coverage=%.4f "
                "nan_or_inf=%llu negative_control=%s control=%s rx_restore_ok=%d\n",
                rep.run_id.c_str(),
                static_cast<unsigned long long>(rep.measurements),
                static_cast<unsigned long long>(rep.completed),
                static_cast<unsigned long long>(rep.scored),
                static_cast<unsigned long long>(rep.finite_count),
                static_cast<unsigned long long>(rep.repeat_deterministic),
                coverage,
                static_cast<unsigned long long>(rep.nan_or_inf),
                rep.negative_control_ok ? "PASS" : "FAIL",
                rep.control_ok ? "PASS" : "FAIL",
                rep.restore_ok ? 1 : 0);
    std::fflush(stdout);

    // ---- functional pass = the measurement infrastructure ran cleanly (NOT the
    //      classification accuracy, which is the blind measurement itself). ----
    const bool infra_ok = rep.error.empty() && rep.sample_rate_ok &&
                          rep.rx_lo_ok && rep.rx_bw_ok && rep.rx_gain_ok &&
                          rep.completed == rep.measurements && all_capture_ok;
    const bool control_ok = rep.control_ok && rep.restore_ok;
    rep.functional_pass = infra_ok && control_ok;

    std::string detail = "run_id=" + rep.run_id +
                         " measurements=" + std::to_string(rep.measurements) +
                         " completed=" + std::to_string(rep.completed) +
                         " scored=" + std::to_string(rep.scored) +
                         " finite=" + std::to_string(rep.finite_count) +
                         " repeat_deterministic=" +
                             std::to_string(rep.repeat_deterministic) +
                         " coverage=" + std::to_string(coverage) +
                         " nan_or_inf=" + std::to_string(rep.nan_or_inf) +
                         " negative_control=" +
                             (rep.negative_control_ok ? "PASS" : "FAIL") +
                         " control=" + (rep.control_ok ? "PASS" : "FAIL") +
                         " rx_restore_ok=" + (rep.restore_ok ? "1" : "0") +
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

}  // namespace rmlblind
