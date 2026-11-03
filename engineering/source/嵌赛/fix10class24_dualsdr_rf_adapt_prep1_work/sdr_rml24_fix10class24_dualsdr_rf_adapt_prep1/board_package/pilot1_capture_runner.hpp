#pragma once

// pilot1_capture_runner.hpp -- M29-RML24-REALRF-FINETUNE-PILOT1 / 线 B: 板端采集 runner。
//
// 拓扑（与 iq-pc-tx-board-rx-24class-bf16-fix10 相同的真实双 SDR 布局）：Windows PC 拥有
// TX SDR（周期性发射冻结 CI16 burst，50-ohm 直连），板端拥有 RX SDR（捕获 -> coarse CFO
// -> fine 同步/增益 -> 广线性恢复 -> 恢复后 payload 前 1024 复样本 -> [2,1024] f32 ->
// NPU24 -> RAW-24 预测）。两端只通过 TCP 控制通道交换控制消息 + 样本身份 + SHA，绝不传
// 实时 IQ。本 runner 无任何 TX API。
//
// 与 iq-pc-tx-board-rx-24class-bf16-fix10 的**关键差异**（本 runner 更简单、且是采集非
// 判级）：不做 D2 restore、不做 baseline 配对、不做分类窗口选择、不做 PreprocessChain、
// 不做 canonical frame。模型输入**直接**取 `ccr.payload[0:1024]`（恢复后 native 尺度）
// 转 [2,1024] f32；每样本无条件先落 32 字段 TSV 行 + raw_rx.i16 +（仅 rec.valid 时）
// model_input.bin / logits.bin + 双预测（save-before-gate）。
//
// ---- 幅度口径（评审 39e5 Blocker 1 已整改：固定公开常数 S）----
// TX 侧用统一公开常数 S（= kTxDigitalScale）把 960 源 native 波形量化到 int16；不再有
// 逐样本 native_rms/tx_scale。板端恢复以 `payload_tx_scale = kTxDigitalScale` 撤销此
// 公开数字缩放，恢复回 **native 尺度**（与离线数字基线一致）；RF 真增益仍由训练块估计，
// 绝不经 manifest 读取。板端不读 .i16、不重建 burst，只持 session_id/source_id/控制
// 身份与冻结 manifest 的 tx_payload_sha256（身份，非幅度）。
//
// 终态：本 runner 是**测量/采集**（M29_* tokens），绝不写 RF_PASS / PROJECT_COMPLETE /
// FINETUNE_SUCCESS / FINETUNE_PROMISING 等；六选一判级由离线 judge_realrf_pilot.py 出。

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_rf_frame_layout.hpp"
#include "iq_rf_loopback_transfer.hpp"          // iqrfloop_run::kRfDiscard* / kRfNoise*
#include "iq_rf_sync_recovery.hpp"             // iqrfrec (Failure / estimate / apply / token)
#include "iq_dual_sdr_coarse_cfo_recovery.hpp" // iqdual23fix10::recover_payload_with_coarse_cfo
#include "iq_pc_tx_board_rx_transfer_fix10.hpp"// iqpctbrx::* state machine + build burst
#include "iq_digital_loopback_sync.hpp"        // rail_positive / rail_negative
#include "rml24_raw.hpp"                       // rml24::raw24_predict / kLabelOrder24
#include "rf_fix_helpers.hpp"                  // rf_fix::rf_readback_close
#include "pilot1_capture_schema.hpp"
#include "pilot1_tx_manifest.hpp"
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
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace pilot1run {

using Clock = std::chrono::steady_clock;

constexpr const char* kMeasurementToken = "M29_RML24_REALRF_FINETUNE_PILOT1_CAPTURE";
constexpr double kFidelityTrainingCorrMin = 0.9;
constexpr std::size_t kDelayMarginDefault = 8192;
// 固定公开幅度合同 S（评审 39e5 Blocker 1）：TX 数字缩放是统一公开常数（不是逐样本
// native_rms/tx_scale）。S = 1600 / max|IQ|（960 源），量化后最大分量恰 1600（无削顶）。
// 板端以 payload_tx_scale=S、payload_tx_target_rms=0 撤销此公开缩放，RF 真增益仍由
// 训练块估计、绝不经 manifest 读取。
constexpr double kTxDigitalScale = 68.46059377833956;

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

inline bool opt_flag(int argc, char** argv, const char* name) {
    for (int i = 1; i < argc; ++i)
        if (std::string(argv[i]) == name) return true;
    return false;
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

// RX-only negative control（与 24-class 双 SDR runner 逐字一致）。
struct NegativeControl {
    bool capture_ok = false;
    bool stable = false;
    double rms_min = 0.0;
    double rms_median = 0.0;
    double rms_max = 0.0;
    double stability_ratio = 0.0;
    std::vector<double> window_rms;
    std::vector<std::int16_t> noise;
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

// sync 阶段失败（前导未找到）-> no_sync。
inline bool is_no_sync_failure(iqrfrec::Failure f) {
    return f == iqrfrec::Failure::CAPTURE_TOO_SHORT ||
           f == iqrfrec::Failure::TRAINING_NOT_FOUND ||
           f == iqrfrec::Failure::TRAINING_CORRELATION_TOO_LOW ||
           f == iqrfrec::Failure::TRAINING_PEAK_AMBIGUOUS;
}

// 写二进制 + 返回该字节串 SHA-256（与落盘字节逐字节一致）。
inline std::string write_and_sha(const std::string& path, const void* data, std::size_t bytes) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("pilot1 capture: cannot open " + path);
    f.write(static_cast<const char*>(data), static_cast<std::streamsize>(bytes));
    f.flush();
    if (!f) throw std::runtime_error("pilot1 capture: write failed " + path);
    return sdr::Sha256::hex(data, bytes);
}

struct Pilot1CaptureReport {
    bool device_not_found = false;
    std::string error;
    std::string detail;

    std::string session;
    std::string tx_manifest_path;
    std::string out_dir;
    std::string model_sha;
    std::string manifest_sha256;

    long long requested_rate = 0;
    long long rx_rate = 0;
    bool sample_rate_ok = false;
    long long requested_rx_bw = 0;
    long long rx_bw_readback = 0;
    bool rx_bw_ok = true;
    double requested_rx_gain = 0.0;
    double rx_gain_readback = 0.0;
    bool rx_gain_ok = true;

    std::uint64_t rows_written = 0;
    std::uint64_t capture_ok = 0;
    std::uint64_t no_sync = 0;
    std::uint64_t rx_clipped = 0;
    std::uint64_t hard_invalid = 0;
    std::uint64_t valid_recovery = 0;      // rec.valid（fidelity 门内）
    std::uint64_t finite = 0;
    std::uint64_t repeat_deterministic = 0;
    std::uint64_t gate_pass = 0;

    bool negative_control_ok = false;
    bool tx_restore_ok = false;
    bool restore_ok = false;

    std::string results_path;
    std::string summary_path;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
};

inline bool ok_pred(int p) { return p >= 0; }

// 把 ccr 的恢复结果写成一个 32 字段 save-before-gate 行；同时落 raw_rx / model_input /
// logits / 双预测（见 schema 头纪律）。返回本行的 gate_pass 值。
inline bool emit_capture_row(Pilot1CaptureReport& rep, const pilot1::TxManifestRow& row,
                             const std::vector<std::int16_t>& rx_int16,
                             const iqdual23fix10::CoarseCfoRecovery& ccr,
                             bool capture_ok, bool rx_clipped, bool neg_pass,
                             const std::vector<float>& tensor,
                             const std::vector<float>& raw24,
                             int pred1, int pred2, bool finite, bool repeat_det,
                             std::ostream& results) {
    const iqrfrec::PerFileRecovery& rec = ccr.rec;
    const bool no_sync = is_no_sync_failure(rec.failure);
    const bool hard_invalid = !capture_ok || no_sync || rx_clipped;
    const bool gate_ok = rec.valid && finite && repeat_det && capture_ok &&
                         !rx_clipped && neg_pass;

    // ---- save-before-gate: 先无条件落 raw_rx ----
    const std::string raw_rx_path = join_path(rep.out_dir, row.source_id + ".raw_rx.i16");
    const std::string raw_rx_sha = write_and_sha(
        raw_rx_path, rx_int16.data(), rx_int16.size() * sizeof(std::int16_t));

    // ---- 仅形成有限 tensor 才落 model_input / logits（save-before-gate：与 rec.valid
    // 无关，门拒但有限 tensor 也落盘，供训练/评估；hard-invalid/no_sync/non_finite 不落）----
    std::string model_input_sha;
    std::string logits_sha;
    std::string board_pred1;
    std::string board_pred2;
    if (finite) {
        model_input_sha = write_and_sha(
            join_path(rep.out_dir, row.source_id + ".model_input.bin"),
            tensor.data(), tensor.size() * sizeof(float));
        logits_sha = write_and_sha(
            join_path(rep.out_dir, row.source_id + ".logits.bin"),
            raw24.data(), raw24.size() * sizeof(float));
        if (ok_pred(pred1)) board_pred1 = std::to_string(pred1);
        if (ok_pred(pred2)) board_pred2 = std::to_string(pred2);
    }

    pilot1::CaptureRow r;
    r.session_id = row.session_id;
    r.source_id = row.source_id;
    r.tx_payload_sha256 = row.tx_payload_sha256;
    // 真值列（class_index / class_name / dataset_index / split / source_iq_sha256 /
    // label）板端一律置空（CaptureRow 默认空串）：接收端不得持有类别真值（评审 39e5
    // Blocker 2），由主机真值清单离线按 source_id 回填（judge / train / evaluate join）。
    r.raw_rx_sha256 = raw_rx_sha;
    r.model_input_sha256 = model_input_sha;
    r.logits_sha256 = logits_sha;
    r.digital_pred = "";            // 数字基线 Host 侧，离线回填
    r.digital_label_correct = "";   // 同上
    r.board_pred1 = board_pred1;
    r.board_pred2 = board_pred2;
    r.capture_ok = capture_ok ? "1" : "0";
    r.no_sync = no_sync ? "1" : "0";
    r.rx_clipped = rx_clipped ? "1" : "0";
    r.hard_invalid = hard_invalid ? "1" : "0";
    r.gate_pass = gate_ok ? "1" : "0";
    r.failure_token = iqrfrec::failure_token(rec.failure);
    r.coarse_cfo_hz = std::isfinite(ccr.coarse_cfo_hz)
        ? std::to_string(ccr.coarse_cfo_hz) : "";
    r.fractional_timing = std::isfinite(ccr.fractional_timing_samples)
        ? std::to_string(ccr.fractional_timing_samples) : "";
    r.timing_offset = rec.computed ? std::to_string(rec.timing_offset) : "";
    r.corr = rec.computed ? std::to_string(rec.training_corr) : "";
    r.training_residual = rec.computed ? std::to_string(rec.training_residual) : "";
    r.training_residual_rel = rec.computed
        ? std::to_string(rec.payload_training_residual) : "";
    r.a_real = rec.computed ? std::to_string(rec.wide_linear_direct.real()) : "";
    r.a_imag = rec.computed ? std::to_string(rec.wide_linear_direct.imag()) : "";
    r.b_real = rec.computed ? std::to_string(rec.wide_linear_image.real()) : "";
    r.b_imag = rec.computed ? std::to_string(rec.wide_linear_image.imag()) : "";
    pilot1::emit_result_row(results, r);

    ++rep.rows_written;
    if (capture_ok) ++rep.capture_ok;
    if (no_sync) ++rep.no_sync;
    if (rx_clipped) ++rep.rx_clipped;
    if (hard_invalid) ++rep.hard_invalid;
    if (rec.valid) ++rep.valid_recovery;
    if (finite) ++rep.finite;
    if (repeat_det) ++rep.repeat_deterministic;
    if (gate_ok) ++rep.gate_pass;
    return gate_ok;
}

// ---------------------------------------------------------------------------
// run_pilot1_capture
// ---------------------------------------------------------------------------
inline Pilot1CaptureReport run_pilot1_capture(chain::NpuClassifier24& npu,
                                              m22::StageTiming& timing,
                                              int argc, char** argv) {
    Pilot1CaptureReport rep;

    // ---- args ----
    rep.tx_manifest_path = board::get_opt(argc, argv, "--tx-manifest", "");
    if (rep.tx_manifest_path.empty())
        throw std::runtime_error("pilot1-capture requires --tx-manifest=<tx_manifest.tsv>");
    rep.out_dir = board::get_opt(argc, argv, "--out-dir", "");
    if (rep.out_dir.empty())
        throw std::runtime_error("pilot1-capture requires --out-dir=<writable base dir> "
                                 "(save-before-gate needs it)");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string tx_control = board::get_opt(argc, argv, "--tx-control", "");
    if (tx_control.empty())
        throw std::runtime_error("pilot1-capture requires --tx-control=tcp://<PC_IP>:39010");
    const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rx_uri.empty())
        throw std::runtime_error("pilot1-capture requires --rx-uri=<board RX device uri>");

    const std::uint64_t center_hz = board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 35.0);
    const long long rx_bw = static_cast<long long>(board::opt_u64(argc, argv, "--rx-bw", 18000000));
    // 固定公开幅度合同 S：无逐样本 RMS 重缩放，target_rms 恒 0（不再暴露 CLI 开关）。
    const double target_rms = 0.0;
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", kDelayMarginDefault));
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex", iqrfloop_run::kRfNoiseComplexDefault));
    const std::string input_kind = board::get_opt(argc, argv, "--input-kind",
                                                  "radioml-finetune-pilot1");

    // RF safety: both ends on 50-ohm direct cable.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error("pilot1-capture requires --rf-path=direct-cable (50-ohm SMA "
                                 "coax, no antenna, no amplifier). Got '" + rf_path + "'.");

    // ---- load TX manifest (fail-closed) ----
    const std::vector<pilot1::TxManifestRow> manifest =
        pilot1::load_tx_manifest(rep.tx_manifest_path);
    rep.session = manifest.front().session_id;

    // ---- manifest SHA（控制通道身份） ----
    {
        bool ok = false;
        rep.manifest_sha256 = sdr::sha256_hex_file(rep.tx_manifest_path, &ok);
        if (!ok)
            throw std::runtime_error("pilot1-capture: cannot hash manifest " +
                                     rep.tx_manifest_path);
    }

    rep.results_path = join_path(rep.out_dir, "capture_results_" + rep.session + ".tsv");
    rep.summary_path = join_path(rep.out_dir, "capture_summary_" + rep.session + ".json");

    std::printf("M29_PILOT1_CAPTURE_BEGIN session=%s manifest=%s "
                "out_dir=%s tx_control=%s rx_uri=%s center_hz=%llu rx_gain=%.3f "
                "tx_digital_scale=%.12f\n",
                rep.session.c_str(), rep.tx_manifest_path.c_str(),
                rep.out_dir.c_str(), tx_control.c_str(), rx_uri.c_str(),
                static_cast<unsigned long long>(center_hz), gain_db, kTxDigitalScale);
    std::fflush(stdout);

    // ---- device open (RX-only; device-not-found 是 exit code 2, 不 throw) ----
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
    sess.manifest_sha256 = rep.manifest_sha256;
    sess.input_kind = input_kind;
    sess.sample_rate = iqrftrain::kFs;
    sess.center_hz = center_hz;
    sess.target_rms = target_rms;

    iqpctbrx::TcpControlClient client;
    {
        std::string host;
        std::uint16_t port = iqpctbrx::kDefaultPort;
        std::string perr;
        if (!iqpctbrx::parse_tx_control_url(tx_control, host, port, &perr))
            throw std::runtime_error("pilot1-capture: " + perr);
        client.host = host;
        client.port = port;
        if (!client.connect(&perr))
            throw std::runtime_error("pilot1-capture: connect to " + tx_control +
                                     " failed: " + perr);
    }

    // ---- HELLO -> HELLO_ACK ----
    {
        std::string perr;
        iqpctbrx::HelloAckInfo ack;
        if (!iqpctbrx::send_hello(client, sess, &perr) ||
            !iqpctbrx::recv_hello_ack(client, sess, ack, &perr)) {
            const std::string primary_error = perr;
            std::string cleanup_error;
            iqpctbrx::send_abort(client, sess, "hello_failed", &cleanup_error);
            client.close();
            throw std::runtime_error("pilot1-capture: HELLO failed: " + primary_error);
        }
        std::printf("M29_PILOT1_CAPTURE_HELLO_ACK tx_serial=%s tx_uri=%s "
                    "tx_atten_db=%.3f configuration_verified=%d\n",
                    ack.tx_serial.c_str(), ack.tx_uri.c_str(), ack.tx_atten_db,
                    ack.configuration_verified ? 1 : 0);
        std::fflush(stdout);
    }

    bool neg_any_fail = false;
    bool tx_restore_any_fail = false;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate (RX only): force 2560000, fail-closed abs(delta) <= 5 Hz ----
        const long long requested = static_cast<long long>(iqrftrain::kFs);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.sample_rate_ok = std::llabs(rep.rx_rate - requested) <= 5;
        if (!rep.sample_rate_ok) {
            rep.error = "sample_rate_mismatch: requested=" + std::to_string(requested) +
                        " rx=" + std::to_string(rep.rx_rate) +
                        " (abs(actual-requested) must be <= 5 Hz)";
            return rep;
        }

        // ---- RX config: LO + bandwidth + manual gain (write-then-readback) ----
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_rx_lo(static_cast<long long>(center_hz));
            rep.requested_rx_bw = rx_bw;
            if (rx_bw != 0) {
                rep.rx_bw_readback = dev->set_rx_bw(rx_bw);
                rep.rx_bw_ok = rf_fix::rf_readback_close(rep.rx_bw_readback, rx_bw,
                                                         1000LL, 0.05);
            } else {
                rep.rx_bw_readback = dev->get_rx_bw();
            }
            dev->set_rx_gain_mode("manual");
            rep.requested_rx_gain = gain_db;
            rep.rx_gain_readback = dev->set_rx_gain(gain_db);
            rep.rx_gain_ok = std::fabs(rep.rx_gain_readback - gain_db) <= 0.5;
        }
        std::printf("M29_PILOT1_CAPTURE_RX_FRONTEND requested_rx_bw=%lld rx_bw_readback=%lld "
                    "requested_rx_gain=%.3f rx_gain_readback=%.3f rx_bw_ok=%d rx_gain_ok=%d\n",
                    static_cast<long long>(rep.requested_rx_bw),
                    static_cast<long long>(rep.rx_bw_readback),
                    rep.requested_rx_gain, rep.rx_gain_readback,
                    rep.rx_bw_ok ? 1 : 0, rep.rx_gain_ok ? 1 : 0);
        std::fflush(stdout);
        if (!rep.rx_bw_ok) {
            rep.error = "rx_bw readback mismatch: requested=" + std::to_string(rx_bw) +
                        " readback=" + std::to_string(rep.rx_bw_readback);
            return rep;
        }
        if (!rep.rx_gain_ok) {
            rep.error = "rx_gain readback mismatch: requested=" + std::to_string(gain_db) +
                        " readback=" + std::to_string(rep.rx_gain_readback);
            return rep;
        }
        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        const int rx_pos_rail = iqdloop_sync::rail_positive(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));
        const int rx_neg_rail = iqdloop_sync::rail_negative(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));

        // ---- results TSV（先写 32 字段表头） ----
        std::ofstream results(rep.results_path, std::ios::binary);
        if (!results)
            throw std::runtime_error("pilot1-capture: cannot open " + rep.results_path);
        results << pilot1::result_tsv_header() << "\n";

        // ---- 逐样本 save-before-gate 采集 ----
        for (std::size_t seq = 0; seq < manifest.size(); ++seq) {
            const pilot1::TxManifestRow& row = manifest[seq];
            if (board::g_stop_requested) break;

            std::printf("M29_PILOT1_CAPTURE_FILE source_id=%s seq=%zu "
                        "tx_payload_sha256=%s\n",
                        row.source_id.c_str(), seq, row.tx_payload_sha256.c_str());
            std::fflush(stdout);

            // 板端不读 .i16、不重建 burst（评审 39e5 Blocker 1/2）：只持控制身份。
            // source_index = 采集序号 seq（0..239）；file_name = source_id + ".i16"（PC 端
            // 据此在私有 payload 清单中寻址）；payload_sha_pre = tx_payload_sha256（身份）。
            const iqpctbrx::SampleIdentity smp{
                static_cast<std::int64_t>(seq),
                row.source_id + ".i16", row.tx_payload_sha256};

            bool sample_capture_ok = false;
            bool rx_clipped = false;
            std::vector<std::int16_t> rx_int16;
            std::vector<std::complex<double>> rx;
            iqdual23fix10::CoarseCfoRecovery ccr;
            std::size_t capture_attempts = 0;
            bool control_fatal = false;
            iqrfrec::EstimateConfig rec_cfg;

            // ---- negative control (TX off, 由状态机保证) ----
            const NegativeControl neg = run_rx_negative_control(*dev, noise_complex);
            bool noise_clipped = false;
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

            // ---- 有界重捕循环（≤3；仅重试瞬态 payload 残差拒绝） ----
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
                rx_clipped = false;
                sample_capture_ok = false;

                if (!iqpctbrx::send_prepare(client, sess, smp, &ctrl_err)) {
                    ctrl = iqpctbrx::ControlOutcome::PrepareFailed;
                } else if (!iqpctbrx::recv_prepared(client, sess, smp, prepared, &ctrl_err)) {
                    ctrl = iqpctbrx::ControlOutcome::PreparedRejected;
                }
                if (ctrl == iqpctbrx::ControlOutcome::Ok) {
                    if (!iqpctbrx::send_start(client, sess, smp, &ctrl_err))
                        ctrl = iqpctbrx::ControlOutcome::StartFailed;
                    else if (!iqpctbrx::recv_ready(client, sess, smp, ready, &ctrl_err))
                        ctrl = iqpctbrx::ControlOutcome::ReadyRejected;
                }
                if (ctrl == iqpctbrx::ControlOutcome::Ok) {
                    // 板端不重建 burst，故不再比较 payload_sha_post/burst_sha/tx_scale；
                    // recv_ready 已在内部 fail-closed 校验 payload_sha_pre == 冻结
                    // manifest SHA（身份一致）。直接进入捕获。
                    dev->recreate_rx_buffer();
                    {
                        const iio::RawChunk c =
                            dev->read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
                        (void)c;
                    }
                    const std::size_t capture = iqrflayout::capture_complex(delay_margin);
                    m22::StageTiming::Timer t(timing, m22::StageId::RxRefill);
                    board::RxStats rxst;
                    board::Continuity rxcont;
                    const bool raw_ok =
                        board::capture_contiguous(*dev, capture, rx_int16, rxst, rxcont);
                    sample_capture_ok = raw_ok && rxcont.ok();
                }
                if (!sample_capture_ok)
                    ctrl = iqpctbrx::ControlOutcome::CaptureFailed;

                if (ctrl == iqpctbrx::ControlOutcome::Ok) {
                    if (!iqpctbrx::send_captured(client, sess, smp, &ctrl_err))
                        ctrl = iqpctbrx::ControlOutcome::CapturedFailed;
                    else if (!iqpctbrx::recv_stopped(client, sess, stopped, &ctrl_err))
                        ctrl = iqpctbrx::ControlOutcome::StoppedFailed;
                }
                if (!stopped.tx_restore_ok) tx_restore_any_fail = true;

                if (ctrl != iqpctbrx::ControlOutcome::Ok) {
                    const std::string reason = ctrl_err.empty()
                        ? iqpctbrx::control_outcome_token(ctrl) : ctrl_err;
                    iqpctbrx::send_abort(client, sess, reason, &ctrl_err);
                    client.close();
                    rep.error = "control_channel_failed:" +
                                std::string(iqpctbrx::control_outcome_token(ctrl)) +
                                " " + reason;
                    control_fatal = true;
                    break;
                }

                // ---- recover (coarse CFO -> fine 同步/增益)，payload_tx_scale 撤销 TX 缩放 ----
                rx = iqrftrain::deinterleave(rx_int16);
                rec_cfg.min_corr = kFidelityTrainingCorrMin;
                rec_cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;
                rec_cfg.max_cfo_hz = iqpctbrx::fine_cfo_range_hz();
                rec_cfg.max_sro_ppm = 30.0;
                rec_cfg.search_limit = 0;
                rec_cfg.payload_tx_target_rms = 0.0;
                ccr = iqdual23fix10::recover_payload_with_coarse_cfo(
                    rx, rec_cfg, kTxDigitalScale);

                // ---- rx_clipped（raw RX 有 railed 样本） ----
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

                const bool retry =
                    !board::g_stop_requested &&
                    ccr.rec.failure == iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH &&
                    iqrfrec::should_retry_payload_training_capture(
                        ccr.rec.failure, capture_attempts);
                if (retry) {
                    std::printf("M29_PILOT1_CAPTURE_RETRY source_id=%s completed_attempt=%zu "
                                "max_attempts=%zu failure=%s payload_training_residual=%.6f "
                                "action=RETRY\n",
                                row.source_id.c_str(), capture_attempts,
                                iqrfrec::kPayloadTrainingCaptureMaxAttempts,
                                iqrfrec::failure_token(ccr.rec.failure),
                                ccr.rec.payload_training_residual);
                    std::fflush(stdout);
                    continue;
                }
                break;
            }
            if (control_fatal) break;

            // ---- 形成 tensor（评审 39e5 Blocker 2）：只要恢复算出了 timing/gain/CFO/SRO
            // （sync 通过且 payload 训练增益有限）就形成有限 tensor 并双推理，即使保真门
            // （rec.valid）拒绝。这分离「recovery_computed && tensor_finite」与「gate_pass」
            // 与「hard_invalid/no_sync/non_finite」三种口径：门拒但有限 tensor 仍落盘。
            std::vector<float> tensor;
            std::vector<float> raw24;
            std::vector<float> raw24b;
            int pred1 = -1, pred2 = -1;
            bool finite = false;
            bool repeat_det = false;
            const bool no_sync = is_no_sync_failure(ccr.rec.failure);
            const bool payload_train_found =
                ccr.rec.failure != iqrfrec::Failure::PAYLOAD_TRAINING_NOT_FOUND;
            const bool tensor_formable = sample_capture_ok && !no_sync && payload_train_found;
            if (tensor_formable) {
                std::vector<std::complex<double>> payload;
                bool have_payload = false;
                if (ccr.rec.valid && !ccr.payload.empty()) {
                    payload = ccr.payload;
                    have_payload = true;
                } else {
                    // 同步后保真门失败：重放 coarse-CFO 去旋 + 分数定时，用已算出的恢复
                    // 参数强制 apply（不改冻结头，仅在本 runner 复现 aligned）。
                    try {
                        std::vector<std::complex<double>> derot(rx.size());
                        for (std::size_t n = 0; n < rx.size(); ++n) {
                            const double ph = -2.0 * iqrftrain::kPi *
                                              ccr.coarse_cfo_hz *
                                              static_cast<double>(n) /
                                              static_cast<double>(iqrftrain::kFs);
                            derot[n] = rx[n] * std::complex<double>(
                                std::cos(ph), std::sin(ph));
                        }
                        const std::vector<std::complex<double>> aligned =
                            iqdual23fix10::detail::apply_fractional_advance(
                                derot, ccr.fractional_timing_samples);
                        iqrfrec::PerFileRecovery rec_copy = ccr.rec;
                        rec_copy.valid = true;
                        rec_copy.failure = iqrfrec::Failure::NONE;
                        payload = iqrfrec::apply(aligned, rec_copy);
                        have_payload = true;
                    } catch (const std::exception&) {
                        have_payload = false;   // unsafe gain -> no tensor（non_finite 口径）
                    }
                }
                if (have_payload && payload.size() >= chain::kFrameComplex) {
                    tensor.assign(chain::kTensorFloats, 0.0f);
                    bool tf_ok = true;
                    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
                        const float re = static_cast<float>(payload[k].real());
                        const float im = static_cast<float>(payload[k].imag());
                        if (!std::isfinite(re) || !std::isfinite(im)) tf_ok = false;
                        tensor[k] = re;
                        tensor[chain::kFrameComplex + k] = im;
                    }
                    if (tf_ok) {
                        const auto t0 = Clock::now();
                        npu.infer(tensor.data(), raw24);
                        timing.record(m22::StageId::NpuInfer, elapsed_us(t0));
                        const auto t1 = Clock::now();
                        npu.infer(tensor.data(), raw24b);
                        timing.record(m22::StageId::NpuInfer, elapsed_us(t1));

                        rml24::RML24Result pr, pr2;
                        const bool ok = rml24::raw24_predict(raw24.data(), &pr);
                        const bool ok2 = rml24::raw24_predict(raw24b.data(), &pr2);
                        finite = ok && ok2;
                        pred1 = ok ? pr.raw_24_top1 : -1;
                        pred2 = ok2 ? pr2.raw_24_top1 : -1;
                        repeat_det = finite && (pred1 == pred2);
                    }
                }
            }

            // ---- save-before-gate 写行 + 落盘 ----
            emit_capture_row(rep, row, rx_int16, ccr, sample_capture_ok, rx_clipped,
                             neg_pass, tensor, raw24, pred1, pred2, finite,
                             repeat_det, results);

            std::printf("M29_PILOT1_CAPTURE_RESULT source_id=%s valid=%d failure=%s "
                        "finite=%d repeat_det=%d gate_pass=%d board_pred1=%d "
                        "payload_training_residual=%.6f\n",
                        row.source_id.c_str(), ccr.rec.valid ? 1 : 0,
                        iqrfrec::failure_token(ccr.rec.failure), finite ? 1 : 0,
                        repeat_det ? 1 : 0, (ccr.rec.valid && finite && repeat_det) ? 1 : 0,
                        pred1, ccr.rec.payload_training_residual);
            std::fflush(stdout);
        }

        results.close();
        rep.negative_control_ok = !neg_any_fail;
        rep.tx_restore_ok = !tx_restore_any_fail;
        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    if (client.connected()) {
        std::string perr;
        iqpctbrx::send_abort(client, sess, "board_done", &perr);
        client.close();
    }
    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- 功能口径（采集/测量，非判级）：无 infra 崩溃 + 240 行 save-before-gate 齐 ----
    const bool infra_ok = rep.sample_rate_ok && rep.rx_bw_ok && rep.rx_gain_ok;
    const bool control_ok = rep.negative_control_ok && rep.tx_restore_ok && rep.restore_ok;
    rep.functional_pass = rep.error.empty() && infra_ok && control_ok &&
                          (rep.rows_written == pilot1::kSamplesPerSession) &&
                          (rep.capture_ok == pilot1::kSamplesPerSession);

    std::string detail = "session=" + rep.session +
                         " rows=" + std::to_string(rep.rows_written) +
                         " capture_ok=" + std::to_string(rep.capture_ok) +
                         " no_sync=" + std::to_string(rep.no_sync) +
                         " rx_clipped=" + std::to_string(rep.rx_clipped) +
                         " hard_invalid=" + std::to_string(rep.hard_invalid) +
                         " valid_recovery=" + std::to_string(rep.valid_recovery) +
                         " finite=" + std::to_string(rep.finite) +
                         " repeat_deterministic=" + std::to_string(rep.repeat_deterministic) +
                         " gate_pass=" + std::to_string(rep.gate_pass) +
                         " negative_control=" + (rep.negative_control_ok ? "PASS" : "FAIL") +
                         " tx_restore_ok=" + (rep.tx_restore_ok ? "1" : "0") +
                         " rx_restore_ok=" + (rep.restore_ok ? "1" : "0") +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " rf_path=direct-cable";
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    rep.detail = detail;

    // ---- summary JSON ----
    {
        std::ofstream f(rep.summary_path, std::ios::binary);
        if (!f) throw std::runtime_error("pilot1-capture: cannot open " + rep.summary_path);
        f << "{\n";
        f << "  \"token\":\"" << kMeasurementToken << "\",\n";
        f << "  \"session\":\"" << json_escape(rep.session) << "\",\n";
        f << "  \"manifest_sha256\":\"" << rep.manifest_sha256 << "\",\n";
        f << "  \"model_sha\":\"" << rep.model_sha << "\",\n";
        f << "  \"rows_written\":" << rep.rows_written << ",\n";
        f << "  \"capture_ok\":" << rep.capture_ok << ",\n";
        f << "  \"no_sync\":" << rep.no_sync << ",\n";
        f << "  \"rx_clipped\":" << rep.rx_clipped << ",\n";
        f << "  \"hard_invalid\":" << rep.hard_invalid << ",\n";
        f << "  \"valid_recovery\":" << rep.valid_recovery << ",\n";
        f << "  \"finite\":" << rep.finite << ",\n";
        f << "  \"repeat_deterministic\":" << rep.repeat_deterministic << ",\n";
        f << "  \"gate_pass\":" << rep.gate_pass << ",\n";
        f << "  \"negative_control_ok\":" << (rep.negative_control_ok ? "true" : "false") << ",\n";
        f << "  \"tx_restore_ok\":" << (rep.tx_restore_ok ? "true" : "false") << ",\n";
        f << "  \"rx_restore_ok\":" << (rep.restore_ok ? "true" : "false") << ",\n";
        f << "  \"functional_pass\":" << (rep.functional_pass ? "true" : "false") << ",\n";
        f << "  \"error\":\"" << json_escape(rep.error) << "\"\n";
        f << "}\n";
    }

    return rep;
}

}  // namespace pilot1run
