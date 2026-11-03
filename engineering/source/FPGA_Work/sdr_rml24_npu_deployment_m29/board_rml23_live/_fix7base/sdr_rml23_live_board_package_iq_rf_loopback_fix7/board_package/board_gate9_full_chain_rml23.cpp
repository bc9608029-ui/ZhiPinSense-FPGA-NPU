// board_gate9_full_chain_rml23.cpp -- M29 Phase F5: the full real-time
// SDR -> NPU(24-class expA_bf16_head) -> AM-SSB merge(23-class) -> UI chain,
// built on the board-proven M22.1 real-time framework (board_gate9_full_chain_12class.cpp).
//
// Phases (identical liveness contract to the 12-class chain, but 23-class output):
//   --phase offline   (default) replay deployment_golden/input_N.bin through the
//                     NPU, merge 24->23 in software, and emit a "rml23-chain-v2"
//                     JSONL record per frame; the merged 23-class argmax is checked
//                     against expected_argmax.tsv.
//   --phase digital   Pluto digital-loopback: TX a CW tone -> RX -> NCO/resample
//                     -> fp32 [2,1024] -> NPU (24 raw logits) -> rml23::merge ->
//                     23-class -> UI JSONL.  Gates CHAIN LIVENESS (N valid frames,
//                     no anomaly, tone present), never classification correctness
//                     (the tone is not a modulation class).
//   --phase rf        same as digital but external RF path (REQUIRES
//                     --confirm-safe-rf-path).
//   --phase ambient   rx-only no-signal integration (no TX buffer ever created).
//   --phase live-rx   real external RX classification: presence-gated NPU -- the
//                     receiver listens on the external RF input and only runs the
//                     NPU (24 raw -> AM-SSB merge -> 23-class result) while
//                     SIGNAL_PRESENT; on NO_SIGNAL it emits only the periodic
//                     state heartbeat.  RX only, loopback=0, no TX buffer.
//   --phase synthetic-iq  three-route digital injection fault attribution WITHOUT
//                     RF (Stage G): A = extracted RadioML test .bin -> NPU;
//                     B = synthesized 128 kSPS -> NPU; C = synthesized 2.56 MSPS
//                     int16 through the production PreprocessChain -> NPU (with a
//                     bit-identical model-input replay).  No IIO/SDR device, no TX.
//
// THE RML23 DELTA vs the 12-class chain:
//   * NpuClassifier24 (24 raw logits, output contract [1,24]) instead of
//     NpuClassifier12.  The model is loaded ONCE (Device open once, one
//     persistent Session create+apply()ed once, first frame forwards directly,
//     every frame after gets exactly one Device::reset(1) and never re-applies).
//   * The per-frame 24-dim raw logits are fed to rml23::merge_logits_23 (the
//     frozen 24->23 AM-SSB logaddexp merge).  The producer / argmax / publish /
//     probabilities all become 23-class; the raw 24-dim logits + raw_24_top1 are
//     preserved in the ResultFrame for the future SC/WC expert.
//   * Results are serialized with result_frame_rml23_line() (schema
//     "rml23-chain-v2"), a DISTINCT schema the old 12-class parser cannot misread.
//   * No expert runs (expert_enabled=false, expert_result=NOT_RUN).
//
// Exit 0/1/2 = pass / fail / device-not-found.

#include "board_common.hpp"
#include "capture_hook.hpp"
#include "logits_export.hpp"
#include "chain_common.hpp"
#include "control_channel.hpp"
#include "gate9_phase.hpp"
#include "live_rx_gating.hpp"
#include "mode_control.hpp"
#include "npu_classifier24.hpp"
#include "producer_12class.hpp"
#include "rf_fix_helpers.hpp"
#include "rml23_merged.hpp"
#include "synthetic_iq_runner.hpp"
#include "synthetic_iq_roundtrip.hpp"
#include "iq_digital_loopback_runner.hpp"
#include "iq_digital_loopback_sweep.hpp"
#include "iq_rf_loopback_runner.hpp"
#include "unix_socket_server.hpp"
#include "unix_socket_sink.hpp"

#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <sys/stat.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;

std::vector<std::string> split_tsv(const std::string& line) {
    std::vector<std::string> f;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = line.find('\t', start);
        if (pos == std::string::npos) { f.push_back(line.substr(start)); break; }
        f.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    return f;
}

bool read_input_bin(const std::string& path, std::vector<float>& out) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    const std::size_t n = out.size();
    const std::size_t got = std::fread(out.data(), sizeof(float), n, f);
    std::fclose(f);
    return got == n;
}

int argmax_of(const std::vector<float>& logits) {
    if (logits.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(logits.size()); ++i)
        if (logits[i] > logits[best]) best = i;
    return best;
}

// Merge the 24-dim raw NPU logits into the 23-dim deployed logits.  Fail-closed:
// throws on any non-finite input (rml23::merge_logits_23 already rejects NaN/Inf).
std::vector<float> merge_to_23(const std::vector<float>& raw24) {
    if (raw24.size() != static_cast<std::size_t>(rml23::kNpuOutputDim))
        throw std::runtime_error("rml23: raw logits width != 24");
    float m23[rml23::kDeployedClassCount];
    if (!rml23::merge_logits_23(raw24.data(), m23))
        throw std::runtime_error("rml23: merge fail-closed (non-finite logits)");
    return std::vector<float>(m23, m23 + rml23::kDeployedClassCount);
}

// Structural checks for a well-formed 23-class RML23 verdict (both offline and
// live).  The publish gate (presence / work mode) is carried separately.
bool result_frame_base_valid(const rf::ResultFrame& r) {
    if (r.class_count != rml23::kDeployedClassCount) return false;
    if (r.logits.size() != static_cast<std::size_t>(rml23::kDeployedClassCount)) return false;
    if (r.probabilities.size() != static_cast<std::size_t>(rml23::kDeployedClassCount)) return false;
    if (r.raw_24_logits.size() != static_cast<std::size_t>(rml23::kNpuOutputDim)) return false;
    if (r.confidence < 0.0f || r.confidence > 1.0f) return false;
    if (r.argmax_idx < -1 || r.argmax_idx >= rml23::kDeployedClassCount) return false;
    if (r.raw_24_top1 < -1 || r.raw_24_top1 >= rml23::kNpuOutputDim) return false;
    if (r.merged_23_top1 < -1 || r.merged_23_top1 >= rml23::kDeployedClassCount) return false;
    if (r.deployment_mode != rml23::kDeploymentMode) return false;
    if (r.expert_enabled) return false;
    if (r.expert_result != rml23::kExpertResult) return false;
    return true;
}

// Offline replay uses the "rml23-chain-v2" record (the only RML23 schema).
bool result_frame_valid(const rf::ResultFrame& r) {
    return result_frame_base_valid(r) && r.version == "rml23-chain-v2";
}

// The live producer uses the same record but MUST carry real measurements,
// presence/level state and the producer-owned work mode / run state.
bool result_frame_v3_valid(const rf::ResultFrame& r) {
    return result_frame_base_valid(r) && r.version == "rml23-chain-v2" &&
           r.has_measurements && r.measurements.valid &&
           !r.presence_state.empty() && !r.level_mode.empty() &&
           !r.work_mode.empty() && !r.run_state.empty();
}

// Emit one result frame to both sinks; returns the JSONL record.
std::string emit_frame(ui::Sink& out, ui::Sink& sock, const rf::ResultFrame& r) {
    const std::string rec = ui::result_frame_rml23_line(r);
    out.write(rec);
    sock.write(rec);
    return rec;
}

// Board glue for the producer's two device effects.  Exceptions propagate so a
// failed LO/gain write fails the gate (fail-closed).
struct PlutoDeviceControl : producer::DeviceControl {
    pluto::Device& dev;
    explicit PlutoDeviceControl(pluto::Device& d) : dev(d) {}
    void set_rx_lo(std::int64_t hz) override {
        dev.set_rx_lo(static_cast<long long>(hz));
    }
    void set_rx_gain(double db) override { dev.set_rx_gain(db); }
};

// RAII: stop + join the control thread on EVERY exit path (including exceptions),
// so a joinable std::thread never outlives its scope (which would std::terminate).
struct ControlThreadGuard {
    std::thread* t = nullptr;
    ctl::ControlState* st = nullptr;
    ~ControlThreadGuard() {
        if (st) st->stop.store(true);
        if (t && t->joinable()) t->join();
    }
};

// Emit a control state event (type:"state") to both sinks on a work-mode / run
// state change, and periodically as the RML23 heartbeat (steady clock, 1000 ms <
// 1/3 of the UI's 5000 ms stale timeout), so the UI shows STOPPED / RUNNING / the
// new mode even though classification frames stop flowing while STOPPED.  The
// heartbeat is a *state* record only: it refreshes the UI's data-chain health
// clock and NEVER fabricates a classification (that only ever comes from a result
// frame).
void emit_state_event(ui::Sink& out, ui::Sink& sock,
                      const mode_ctl::ModeState& st,
                      const std::string& presence_state,
                      std::uint64_t command_id,
                      const std::string& model_sha) {
    const std::string rec = ui::state_line(
        mode_ctl::mode_token(st.mode), mode_ctl::run_display_name(st.run),
        presence_state.c_str(), command_id,
        static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(
                Clock::now().time_since_epoch()).count()),
        model_sha.c_str(), "rml23-chain-v2");
    out.write(rec);
    sock.write(rec);
}

// ---------------------------------------------------------------------------
// M22 runtime baseline plumbing (identical to the 12-class chain).  The nine
// stages (device_open .. frame_total) are the fixed m22::StageTiming set.  Device
// open + model load are recorded once in main (part of NpuClassifier24 bring-up).
// ---------------------------------------------------------------------------
struct M22Config {
    bool verbose = false;
    std::string perf_file;
    std::uint64_t summary_interval = 5000;
};

M22Config read_m22_config(int argc, char** argv) {
    M22Config c;
    c.verbose = board::has_flag(argc, argv, "--verbose");
    c.perf_file = board::get_opt(argc, argv, "--perf-file", "");
    c.summary_interval = board::opt_u64(argc, argv, "--summary-interval", 5000);
    if (c.summary_interval == 0) c.summary_interval = 1;
    return c;
}

m22::ResourceSample peak_of(const m22::ResourceSample& a,
                            const m22::ResourceSample& b) {
    m22::ResourceSample p;
    p.rss_kb = a.rss_kb > b.rss_kb ? a.rss_kb : b.rss_kb;
    p.vm_kb = a.vm_kb > b.vm_kb ? a.vm_kb : b.vm_kb;
    p.fd_count = a.fd_count > b.fd_count ? a.fd_count : b.fd_count;
    p.thread_count = a.thread_count > b.thread_count ? a.thread_count : b.thread_count;
    p.cpu_seconds = a.cpu_seconds > b.cpu_seconds ? a.cpu_seconds : b.cpu_seconds;
    return p;
}

void print_m22_summary(const m22::StageTiming& timing,
                       const m22::ResourceSample& res, std::uint64_t frames) {
    std::printf("M22_SUMMARY frames=%llu rss_kb=%ld fd=%ld threads=%ld "
                "npu_infer_p50_us=%.1f npu_infer_p99_us=%.1f npu_infer_max_us=%.1f "
                "frame_total_p50_us=%.1f frame_total_p99_us=%.1f frame_total_max_us=%.1f\n",
                static_cast<unsigned long long>(frames), res.rss_kb, res.fd_count,
                res.thread_count,
                timing.stage(m22::StageId::NpuInfer).percentile(0.50),
                timing.stage(m22::StageId::NpuInfer).percentile(0.99),
                timing.stage(m22::StageId::NpuInfer).max_us(),
                timing.stage(m22::StageId::FrameTotal).percentile(0.50),
                timing.stage(m22::StageId::FrameTotal).percentile(0.99),
                timing.stage(m22::StageId::FrameTotal).max_us());
    std::fflush(stdout);
}

// §六 acceptance line + JSON baseline (identical criteria to the 12-class chain).
// fix7 Task A: return the M22 verdict (bool) so a caller can fold an M22 FAIL into
// the total gate.  Previously this returned void and the callers ignored the M22
// result -- an M22 FAIL (e.g. RSS growth over a 240-file loop) left GATE=PASS.
bool finish_m22_runtime(const char* phase, const std::string& model_sha,
                        const chain::NpuClassifier24& npu,
                        const m22::StageTiming& timing,
                        const m22::ResourceSample& first,
                        const m22::ResourceSample& last,
                        const m22::ResourceSample& peak,
                        const M22Config& cfg) {
    const std::uint64_t reopen =
        npu.lifecycle().open_count() > 0 ? npu.lifecycle().open_count() - 1 : 0;
    const std::uint64_t apply = npu.lifecycle().apply_count();
    const bool discipline = npu.discipline_ok() && npu.lifecycle().discipline_ok();

    const long rss_growth = last.rss_kb - first.rss_kb;
    const long fd_growth = last.fd_count - first.fd_count;
    const bool rss_ok = (rss_growth <= 32768);
    const bool fd_ok = (fd_growth <= 0);

    const double ft_max = timing.stage(m22::StageId::FrameTotal).max_us();
    const double ft_p99 = timing.stage(m22::StageId::FrameTotal).percentile(0.99);
    const bool spike_free = (ft_max <= 100000.0);

    const bool ok = (reopen == 0) && (apply == 1) && discipline &&
                    fd_ok && rss_ok && spike_free;

    std::printf("M22_RUNTIME_RESULT result=%s phase=%s reopen=%llu apply=%llu "
                "discipline=%s fd_growth=%ld rss_growth_kb=%ld rss_ok=%s fd_ok=%s "
                "spike_free=%s frame_total_p99_us=%.1f frame_total_max_us=%.1f\n",
                ok ? "PASS" : "FAIL", phase,
                static_cast<unsigned long long>(reopen),
                static_cast<unsigned long long>(apply),
                discipline ? "OK" : "VIOLATION",
                fd_growth, rss_growth,
                rss_ok ? "1" : "0", fd_ok ? "1" : "0",
                spike_free ? "1" : "0", ft_p99, ft_max);
    std::fflush(stdout);

    if (cfg.perf_file.empty()) return ok;
    FILE* f = std::fopen(cfg.perf_file.c_str(), "w");
    if (!f) {
        std::fprintf(stderr, "m22: cannot write perf file %s\n",
                     cfg.perf_file.c_str());
        return ok;
    }
    std::fprintf(f,
        "{\"phase\":\"%s\",\"model_sha\":\"%s\",\"stages\":%s,"
        "\"resource_first\":%s,\"resource_last\":%s,\"resource_peak\":%s,"
        "\"device_reopen_count\":%llu,\"session_apply_count\":%llu,"
        "\"npv_discipline_ok\":%s,\"rss_growth_kb\":%ld,\"fd_growth\":%ld,"
        "\"spike_free\":%s,\"result\":\"%s\"}\n",
        phase, model_sha.c_str(), timing.json().c_str(),
        first.json().c_str(), last.json().c_str(), peak.json().c_str(),
        static_cast<unsigned long long>(reopen),
        static_cast<unsigned long long>(apply),
        discipline ? "true" : "false",
        rss_growth, fd_growth,
        spike_free ? "true" : "false", ok ? "PASS" : "FAIL");
    std::fclose(f);
    return ok;
}

// ---------------------------------------------------------------------------
// Phase 1: offline -- real NPU inference over golden [1,2,1024] inputs, with the
// 24->23 AM-SSB merge.  Proves the NPU -> merge -> UI link against known inputs.
// expected_argmax.tsv holds the 23-class merged argmax for each input.
// ---------------------------------------------------------------------------
int run_offline(chain::NpuClassifier24& npu, const cat::Contract& contract,
                ui::StdoutSink& out, ui::UnixSocketSink& sock,
                m22::StageTiming& timing, int argc, char** argv) {
    const std::string golden_dir = board::get_opt(argc, argv, "--golden",
                                                  "deployment_golden");
    const std::size_t count = static_cast<std::size_t>(board::opt_u64(argc, argv, "--count", 240));
    const double min_match = board::opt_d(argc, argv, "--min-match-rate", 0.90);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    // Raw-24 logits export (errata 39e5 Stage E, #7): when --logits-export DIR is
    // given, each classified frame's pre-merge 24-dim NPU logits are dumped to
    // DIR/logits_<frame_id>.json keyed by the input's SHA-256, for the offline
    // three-backend comparison.  Empty (the default) disables it.
    const std::string logits_dir = board::get_opt(argc, argv, "--logits-export", "");
    const board::LogitsExport logits_export(logits_dir);
    const M22Config mcfg = read_m22_config(argc, argv);
    const m22::ResourceSample first_res = m22::read_resources();

    const std::string tsv_path = golden_dir + "/expected_argmax.tsv";
    std::ifstream tsv(tsv_path.c_str());
    std::vector<int> exp_argmax;
    std::string line;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        const std::vector<std::string> f = split_tsv(line);
        if (f.size() < 4) continue;
        exp_argmax.push_back(std::atoi(f[1].c_str()));
    }
    tsv.close();
    if (exp_argmax.empty())
        return (board::emit("gate9_full_chain_rml23", false,
                            "error=empty_expected_argmax:" + tsv_path), 1);

    const std::size_t n = count < exp_argmax.size() ? count : exp_argmax.size();
    std::vector<float> tensor(chain::kTensorFloats);
    std::size_t processed = 0, matched = 0, valid = 0;

    for (std::size_t i = 0; i < n; ++i) {
        if (board::g_stop_requested) break;
        m22::StageTiming::Timer frame_t(timing, m22::StageId::FrameTotal);
        char path[512];
        std::snprintf(path, sizeof(path), "%s/input_%03zu.bin", golden_dir.c_str(), i);
        if (!read_input_bin(path, tensor))
            return (board::emit("gate9_full_chain_rml23", false,
                                std::string("error=short_input:") + path), 1);

        const auto t0 = Clock::now();
        const std::vector<float> raw24 = npu.infer(tensor.data());
        const auto t1 = Clock::now();
        timing.record(m22::StageId::NpuInfer, static_cast<double>(
            std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count()));

        if (logits_export.enabled()) {
            const std::string in_sha = sdr::Sha256::hex(tensor.data(), chain::kTensorBytes);
            const std::string key = logits_export.export_frame(
                static_cast<std::uint64_t>(i), in_sha, model_sha,
                raw24.data(), raw24.size());
            std::printf("LIVE_RX_LOGITS frame=%zu input_sha256=%s exported=%s\n",
                        i, in_sha.c_str(), key.empty() ? "no" : "yes");
            std::fflush(stdout);
        }

        const std::vector<float> merged23 = merge_to_23(raw24);

        rf::ResultFrame r;
        r.frame_id = static_cast<std::uint64_t>(i + 1);
        r.timestamp_us = static_cast<std::uint64_t>(i + 1) * 8000ULL;
        r.source = "fpga_npu";
        r.mock = false;
        chain::fill_result_rml23(r, raw24, merged23, contract, model_sha,
                                 std::numeric_limits<double>::quiet_NaN());
        r.classify_us = static_cast<double>(
            std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count());
        r.e2e_us = r.classify_us;

        emit_frame(out, sock, r);
        ++processed;
        if (result_frame_valid(r)) ++valid;
        if (argmax_of(merged23) == exp_argmax[i]) ++matched;
    }

    const double rate = processed ? static_cast<double>(matched) / static_cast<double>(processed) : 0.0;
    const bool pass = (processed == n) && (valid == processed) && (rate >= min_match);
    std::string detail = " phase=offline samples=" + std::to_string(processed) + "/" +
                         std::to_string(n) + " valid=" + std::to_string(valid) +
                         " matched=" + std::to_string(matched) +
                         " match_rate=" + std::to_string(rate) +
                         " min_match_rate=" + std::to_string(min_match);
    if (processed != n) detail += " (count_short)";
    if (valid != processed) detail += " (invalid_frames)";
    if (rate < min_match) detail += " (match_below_threshold)";
    detail += " npu_reopen=" + std::to_string(
                  npu.lifecycle().open_count() > 0 ? npu.lifecycle().open_count() - 1 : 0);
    detail += " npu_apply=" + std::to_string(npu.lifecycle().apply_count());
    detail += " npu_discipline=" + std::string(
                  npu.discipline_ok() && npu.lifecycle().discipline_ok() ? "OK" : "VIOLATION");

    const m22::ResourceSample last_res = m22::read_resources();
    const m22::ResourceSample peak_res = peak_of(first_res, last_res);
    finish_m22_runtime("offline", model_sha, npu, timing, first_res, last_res,
                       peak_res, mcfg);

    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase 2/3: digital / RF loopback -- the LIVE 23-class RML23 producer (M6-M10).
//
// Identical control-plane structure to the 12-class chain: the producer owns the
// reverse control channel and, per frame, computes real sdr::FrameMeasurements,
// updates SignalPresence, advances the WorkModeEngine, applies the engine's
// model_scale ON TOP of the receiver_scale tensor, applies a bounded/safe/logged
// RF gain, and emits a "rml23-chain-v2" result.  The ONLY delta is the classifier
// adapter: NPU emits 24 raw logits -> rml23::merge_logits_23 -> 23-class logits
// handed to the producer (which is width-agnostic), and the ResultFrame carries
// the preserved raw 24-dim logits + raw_24_top1.
// ---------------------------------------------------------------------------
int run_loopback_phase(chain::NpuClassifier24& npu, const cat::Contract& contract,
                       ui::StdoutSink& out, ui::UnixSocketSink& sock,
                       m22::StageTiming& timing, int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const int loopback = (board::get_opt(argc, argv, "--phase", "digital") == "rf") ? 0 : 1;
    const bool confirm_rf = board::has_flag(argc, argv, "--confirm-safe-rf-path");
    const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 16);
    const double tone_hz = board::opt_d(argc, argv, "--tone", 10000.0);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const M22Config mcfg = read_m22_config(argc, argv);
    m22::ResourceSample first_res, last_res, peak_res;
    bool have_res = false;
    const float rec_scale = static_cast<float>(board::opt_d(argc, argv, "--rec-scale", 1.0));
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string ctl_sock = board::get_opt(argc, argv, "--ctl-sock",
                                                "/run/sdr_amr_control_rml23.sock");

    const std::string mode_opt = board::get_opt(argc, argv, "--mode", "FIXED");
    mode_ctl::ModeKind init_mode = mode_ctl::ModeKind::Fixed;
    if (!mode_ctl::mode_from_token(mode_opt, init_mode)) {
        board::emit("gate9_full_chain_rml23", false,
                    "error=unknown_mode:" + mode_opt + " (use FIXED|AUTO_LOCK|BAND_SCAN)");
        return 1;
    }
    const std::size_t batch_frames = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--batch-frames", 16));
    const int stability_window = static_cast<int>(
        board::opt_u64(argc, argv, "--stability-window", 5));

    // Optional per-N-frame RF diagnostic summary (valid in loopback too): confirms
    // the RX LO/BW/gain/loopback stay put during the long digital soak runs.
    const bool rf_diag = board::has_flag(argc, argv, "--rf-diag");
    std::uint64_t rf_diag_interval =
        board::opt_u64(argc, argv, "--rf-diag-interval", 100);
    if (rf_diag_interval == 0) rf_diag_interval = 100;

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate9_full_chain_rml23", false,
                    std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool pass = false;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        const sdr::RateNegotiation neg =
            sdr::negotiate_sample_rate(*dev, sdr::default_rate_candidates(), 128000);
        if (!neg.ok) {
            detail = "negotiation_failed: " + neg.report();
        } else {
            detail = neg.report() + "; phase=" +
                     (loopback == 0 ? "rf" : "digital") + "; mode=" + mode_opt;

            {
                m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
                dev->set_rx_gain_mode("manual");
                dev->set_rx_gain(gain_db);
                dev->set_loopback(loopback);
            }

            producer::ProducerConfig pcfg;
            pcfg.dsp.sample_rate_hz = 128000.0;
            pcfg.dsp.receiver_scale = rec_scale;
            pcfg.base_rf_gain_db = gain_db;
            pcfg.rf_gain_min_db = 0.0;
            pcfg.rf_gain_max_db = 50.0;
            pcfg.batch_frames = batch_frames;
            pcfg.stability_window = stability_window;
            pcfg.band_scan.start_hz = board::opt_u64(argc, argv, "--band-start", 2400000000ULL);
            pcfg.band_scan.stop_hz  = board::opt_u64(argc, argv, "--band-stop", 2500000000ULL);
            pcfg.band_scan.step_hz  = board::opt_u64(argc, argv, "--band-step", 10000000ULL);
            pcfg.band_scan.dwell_frames = static_cast<int>(
                board::opt_u64(argc, argv, "--band-dwell", 32));

            PlutoDeviceControl devctl(*dev);
            producer::Producer12 prod(pcfg, devctl);
            const std::string init_resp = prod.apply_command("SET_MODE " + mode_opt);

            ui::UnixSocketServer control(ctl_sock);
            if (!control.start()) {
                detail += " control_socket_bind_failed:" + ctl_sock;
                throw std::runtime_error("control socket bind failed");
            }

            ctl::CommandQueue cmdq(32);
            ctl::AckQueue ackq(32);
            ctl::ControlState cstate;
            ctl::ControlStats cstats;
            mode_ctl::ModeState mirror = prod.mode_state();
            cstate.requested_mode.store(static_cast<int>(mirror.mode));
            cstate.requested_running.store(
                mirror.run == mode_ctl::RunState::Running ? 1 : 0);
            cstate.applied_mode.store(static_cast<int>(mirror.mode));
            cstate.applied_running.store(
                mirror.run == mode_ctl::RunState::Running ? 1 : 0);

            std::thread ctl_thread(ctl::control_thread_main, std::ref(control),
                                   std::ref(cmdq), std::ref(ackq),
                                   std::ref(cstate), std::ref(cstats),
                                   std::ref(mirror));
            ControlThreadGuard ctl_guard;
            ctl_guard.t = &ctl_thread;
            ctl_guard.st = &cstate;

            std::printf("GATE9_MODE_CTL_READY sock=%s %s %s\n", ctl_sock.c_str(),
                        mode_ctl::mode_state_line(prod.mode_state()).c_str(),
                        init_resp.c_str());
            std::fflush(stdout);

            std::unique_ptr<pluto::PlutoTx> tx;
            {
                pluto::TxConfig txc;
                txc.center_freq_hz = board::opt_u64(argc, argv, "--center", 2450000000ULL);
                txc.rx_gain_db = gain_db;
                txc.tx_atten_db = board::opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
                txc.loopback = loopback;
                txc.confirm_safe_rf_path = confirm_rf;
                txc.waveform = board::make_periodic_tone(
                    tone_hz, static_cast<double>(neg.actual_hz), 8);
                tx.reset(new pluto::PlutoTx(*dev, txc));
                tx->prepare();
                tx->start_cyclic();
            }

            std::string last_presence_state;

            const std::int64_t kApplyTimeoutMs = 2000;

            auto apply_pending = [&](const char* tag) {
                ctl::Command c;
                while (cmdq.try_pop(c)) {
                    const std::int64_t t0 = ctl::now_us();
                    const mode_ctl::ModeState before = prod.mode_state();
                    const std::string resp = prod.apply_command(c.raw);
                    const mode_ctl::ModeState after = prod.mode_state();

                    ackq.try_push("OK applied command_id=" + std::to_string(c.id) +
                                  " " + c.raw);

                    cstate.applied_mode.store(static_cast<int>(after.mode));
                    cstate.applied_running.store(
                        after.run == mode_ctl::RunState::Running ? 1 : 0);
                    cstate.last_applied_command_id.store(c.id);
                    cstate.queue_depth.store(cmdq.depth());
                    cstats.applied.fetch_add(1);

                    const std::int64_t lat = (ctl::now_us() - t0) / 1000;
                    std::int64_t am = cstats.max_apply_latency_ms.load();
                    while (lat > am &&
                           !cstats.max_apply_latency_ms.compare_exchange_weak(am, lat)) {}
                    if (lat > kApplyTimeoutMs) cstats.timeouts.fetch_add(1);

                    if (after.mode != before.mode || after.run != before.run) {
                        emit_state_event(out, sock, after, last_presence_state, c.id, model_sha);
                        std::printf("CONTROL_EVENT command_id=%llu mode=%s running=%s "
                                    "apply_ms=%lld tag=%s\n",
                                    static_cast<unsigned long long>(c.id),
                                    mode_ctl::mode_token(after.mode),
                                    mode_ctl::run_display_name(after.run),
                                    static_cast<long long>(lat), tag);
                    }
                    std::printf("GATE9_MODE_CTL cmd=%s -> %s apply_ms=%lld tag=%s\n",
                                c.raw.c_str(), resp.c_str(),
                                static_cast<long long>(lat), tag);
                    std::fflush(stdout);
                }
            };

            emit_state_event(out, sock, prod.mode_state(), "", 0, model_sha);
            auto last_state_emit = Clock::now();

            std::uint64_t total_processed = 0;
            std::size_t valid = 0, published = 0, present = 0;
            double ratio_min = 1e9;
            double classify_us_sum = 0.0;
            bool stream_broken = false, continuity_ok_all = true, interrupted = false;
            bool any_short = false;

            chain::PreprocessChain chain(static_cast<std::uint32_t>(neg.actual_hz),
                                         nco_offset, rec_scale);
            std::vector<float> tensor(chain::kTensorFloats);
            std::vector<std::int16_t> iq;
            std::vector<std::complex<float>> x(chain::kFrameComplex);

            ui::NullSink null_out;
            ui::Sink& frame_out = mcfg.verbose
                ? static_cast<ui::Sink&>(out) : static_cast<ui::Sink&>(null_out);

            first_res = m22::read_resources();
            have_res = true;

            while (!board::g_stop_requested && total_processed < frames) {
                apply_pending("loop_top");
                // Steady-clock heartbeat (1000 ms): refresh the UI's data-chain
                // health clock with a state record even while STOPPED, when no
                // classification frames flow.  A state record is never a fabricated
                // classification.
                {
                    const auto hb_now = Clock::now();
                    if (std::chrono::duration_cast<std::chrono::milliseconds>(
                            hb_now - last_state_emit).count() >= 1000) {
                        last_state_emit = hb_now;
                        emit_state_event(out, sock, prod.mode_state(),
                                         last_presence_state, 0, model_sha);
                    }
                }
                if (!prod.running()) {
                    apply_pending("stopped");
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    continue;
                }

                apply_pending("before_capture");
                prod.before_capture();
                apply_pending("after_capture_schedule");
                std::size_t batch = prod.capture_batch_frames();
                if (batch > frames - total_processed)
                    batch = static_cast<std::size_t>(frames - total_processed);

                chain.reset();
                const std::size_t requested = chain.required_input(batch);
                board::RxStats st;
                board::Continuity cont;
                apply_pending("before_rx_refill");
                const bool captured = [&]() {
                    m22::StageTiming::Timer t(timing, m22::StageId::RxRefill);
                    return board::capture_contiguous(*dev, requested, iq, st, cont);
                }();
                if (st.interrupted) { interrupted = true; break; }
                if (!captured) { stream_broken = true; break; }
                if (!cont.ok()) continuity_ok_all = false;
                apply_pending("after_rx_refill");

                {
                    m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                    chain.push_int16(iq.data(), iq.size() / 2);
                }
                std::size_t produced_batch = 0;
                while (chain.ready() > 0 && produced_batch < batch &&
                       total_processed < frames) {
                    apply_pending("frame_top");
                    if (!prod.running()) break;

                    if (!chain.pull_tensor(tensor.data())) break;

                    producer::CaptureFlags flags;
                    flags.overflow = st.overflow != 0;
                    flags.dropped = st.dropped != 0;
                    flags.discontinuity = st.discontinuity != 0;
                    flags.short_frame = st.short_block;
                    if (st.short_block) any_short = true;

                    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
                        x[k] = std::complex<float>(tensor[k],
                                                   tensor[chain::kFrameComplex + k]);
                    const double rp = sdr::goertzel_ratio(x, tone_hz, 128000.0);
                    const double rn = sdr::goertzel_ratio(x, -tone_hz, 128000.0);
                    const double ratio = (rp > rn) ? rp : rn;
                    if (ratio < ratio_min) ratio_min = ratio;

                    apply_pending("before_infer");
                    if (!prod.running()) break;

                    const auto ft0 = Clock::now();
                    ++produced_batch;
                    ++total_processed;

                    double classify_us = 0.0;
                    std::vector<float> raw24_frame(rml23::kNpuOutputDim);
                    producer::ProducerDecision d = prod.on_frame(
                        tensor.data(), flags,
                        [&](const float* t, std::vector<float>& lg) {
                            const auto t0 = Clock::now();
                            npu.infer(t, raw24_frame);   // 24-dim raw logits (reused)
                            const auto t1 = Clock::now();
                            if (raw24_frame.size() != static_cast<std::size_t>(rml23::kNpuOutputDim))
                                throw std::runtime_error("rml23: raw logits width != 24");
                            float m23[rml23::kDeployedClassCount];
                            if (!rml23::merge_logits_23(raw24_frame.data(), m23))
                                throw std::runtime_error(
                                    "rml23: merge fail-closed (non-finite logits)");
                            lg.assign(m23, m23 + rml23::kDeployedClassCount);
                            classify_us = static_cast<double>(
                                std::chrono::duration_cast<std::chrono::microseconds>(
                                    t1 - t0).count());
                            timing.record(m22::StageId::NpuInfer, classify_us);
                            classify_us_sum += classify_us;
                        });

                    if (d.has_measurements || !d.presence_state.empty())
                        last_presence_state = d.presence_state;

                    const auto pp0 = Clock::now();
                    rf::ResultFrame r;
                    r.frame_id = total_processed;
                    r.timestamp_us = static_cast<std::uint64_t>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now().time_since_epoch()).count());
                    r.source = "fpga_npu";
                    r.mock = false;
                    r.overflow = flags.overflow;
                    r.dropped = flags.dropped;
                    r.discontinuity = flags.discontinuity;
                    r.short_frame = flags.short_frame;
                    chain::fill_result_rml23(r, raw24_frame, d.logits, contract,
                                             model_sha,
                                             chain::tone_snr_db(x, tone_hz, 128000.0));
                    r.has_measurements = d.has_measurements;
                    r.measurements = d.measurements;
                    r.presence_state = d.presence_state;
                    r.level_mode = d.level_mode;
                    r.model_scale = d.model_scale;
                    r.rf_gain_db = d.rf_gain_db;
                    r.work_mode = d.work_mode;
                    r.run_state = d.run_state;
                    r.classify_us = classify_us;
                    r.e2e_us = classify_us;

                    // Publish gating: a non-published frame carries NO valid class.
                    if (d.publish && d.published_class >= 0 &&
                        d.published_class < static_cast<int>(r.probabilities.size())) {
                        r.argmax_idx = d.published_class;
                        r.argmax_class = cat::label(contract, d.published_class);
                        r.confidence = r.probabilities[static_cast<std::size_t>(d.published_class)];
                        ++published;
                    } else {
                        r.argmax_idx = -1;
                        r.argmax_class = "";
                        r.confidence = 0.0f;
                        r.quality = 0.0;
                    }
                    timing.record(m22::StageId::Postprocess, static_cast<double>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now() - pp0).count()));

                    apply_pending("before_emit");
                    {
                        m22::StageTiming::Timer t(timing, m22::StageId::UiSubmit);
                        emit_frame(frame_out, sock, r);
                    }
                    if (result_frame_v3_valid(r)) ++valid;
                    if (d.presence_state == "SIGNAL_PRESENT") ++present;
                    timing.record(m22::StageId::FrameTotal, static_cast<double>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now() - ft0).count()));
                    if (total_processed % mcfg.summary_interval == 0) {
                        const m22::ResourceSample cur = m22::read_resources();
                        peak_res = peak_of(peak_res, cur);
                        print_m22_summary(timing, cur, total_processed);
                    }
                    // Optional per-N-frame RF diagnostic summary (no per-frame
                    // serial spam): confirms LO/BW/gain/loopback stay put.
                    if (rf_diag && total_processed % rf_diag_interval == 0) {
                        std::printf(
                            "RF_DIAG frame=%llu rx_lo=%s rx_bw=%s gain_mode=%s "
                            "gain=%s loopback=%s sample_rate=%s\n",
                            static_cast<unsigned long long>(total_processed),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_lo).c_str(),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_bw).c_str(),
                            rf_fix::rf_s(*dev, &pluto::Device::get_rx_gain_mode).c_str(),
                            rf_fix::rf_d(*dev, &pluto::Device::get_rx_gain).c_str(),
                            rf_fix::rf_i(*dev, &pluto::Device::get_loopback).c_str(),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_sample_rate).c_str());
                        std::fflush(stdout);
                    }
                    apply_pending("frame_end");
                }
                apply_pending("batch_end");
            }

            apply_pending("final");
            cstate.stop.store(true);
            ctl_thread.join();
            control.stop();

            last_res = m22::read_resources();
            peak_res = peak_of(peak_res, last_res);
            if (have_res)
                finish_m22_runtime(loopback == 0 ? "rf" : "digital", model_sha, npu,
                                   timing, first_res, last_res, peak_res, mcfg);

            const bool frames_ok = (total_processed == frames);
            const bool tone_ok = frames_ok && ratio_min > 0.3;
            const bool rf_ok = (loopback != 0) || confirm_rf;
            const bool presence_ok = present > 0 && published > 0;
            const bool scan_ok = (init_mode != mode_ctl::ModeKind::BandScan) ||
                                 prod.sweep_advances() > 0;
            const bool control_ok = (cstats.rejected.load() == 0 &&
                                     cstats.timeouts.load() == 0);
            pass = !stream_broken && !interrupted && continuity_ok_all && frames_ok &&
                   tone_ok && rf_ok && presence_ok && scan_ok && control_ok &&
                   (valid == total_processed);

            detail += " frames=" + std::to_string(total_processed) + "/" + std::to_string(frames);
            detail += " valid=" + std::to_string(valid);
            detail += " published=" + std::to_string(published);
            detail += " present=" + std::to_string(present);
            detail += " model_scale=" + std::to_string(prod.model_scale());
            detail += " rf_gain_db=" + std::to_string(prod.rf_gain_db());
            detail += " lo_tunes=" + std::to_string(prod.lo_tune_count());
            detail += " sweep_advances=" + std::to_string(prod.sweep_advances());
            detail += " rec_scale=" + std::to_string(rec_scale);
            detail += " nco_offset=" + std::to_string(nco_offset);
            detail += " ratio_min=" + std::to_string(ratio_min);
            detail += " classify_us_mean=" +
                      std::to_string(total_processed ? classify_us_sum /
                        static_cast<double>(total_processed) : 0.0);
            detail += " short=" + std::to_string(any_short ? 1 : 0);
            detail += " interrupted=" + std::to_string(interrupted ? 1 : 0);
            detail += " control_received=" + std::to_string(cstats.received.load());
            detail += " control_accepted=" + std::to_string(cstats.accepted.load());
            detail += " control_applied=" + std::to_string(cstats.applied.load());
            detail += " control_rejected=" + std::to_string(cstats.rejected.load());
            detail += " control_timeouts=" + std::to_string(cstats.timeouts.load());
            detail += " control_queue_max_depth=" + std::to_string(cstats.queue_max_depth.load());
            detail += " control_max_accept_latency_ms=" +
                      std::to_string(cstats.max_accept_latency_ms.load());
            detail += " control_max_apply_latency_ms=" +
                      std::to_string(cstats.max_apply_latency_ms.load());

            std::printf("CONTROL_STATS received=%llu accepted=%llu applied=%llu "
                        "rejected=%llu timeouts=%llu queue_max_depth=%llu "
                        "max_accept_ms=%lld max_apply_ms=%lld\n",
                        static_cast<unsigned long long>(cstats.received.load()),
                        static_cast<unsigned long long>(cstats.accepted.load()),
                        static_cast<unsigned long long>(cstats.applied.load()),
                        static_cast<unsigned long long>(cstats.rejected.load()),
                        static_cast<unsigned long long>(cstats.timeouts.load()),
                        static_cast<unsigned long long>(cstats.queue_max_depth.load()),
                        static_cast<long long>(cstats.max_accept_latency_ms.load()),
                        static_cast<long long>(cstats.max_apply_latency_ms.load()));
            std::fflush(stdout);

            if (stream_broken) detail += " (stream_broken)";
            if (!continuity_ok_all) detail += " (continuity_fail)";
            if (!frames_ok) detail += " (frame_short)";
            if (!tone_ok) detail += " (tone_missing)";
            if (!rf_ok) detail += " (rf_unconfirmed)";
            if (!presence_ok) detail += " (presence_publish_missing)";
            if (!scan_ok) detail += " (band_scan_no_advance)";
            if (!control_ok) detail += " (control_rejected_or_timeout)";
            if (valid != total_processed) detail += " (invalid_frames)";
            if (interrupted) detail += " (interrupted)";
        }

        guard->restore();
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    if (guard) {
        guard->restore();
        detail += board::restore_report(*dev, *guard);
        pass = board::final_gate_pass(pass, guard->restore_ok(), detail);
    } else {
        pass = false;
        detail += " (no_state_guard)";
    }

    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase 4: ambient / rx-only -- the real no-signal integration test for the
// 23-class RML23 chain.  NO TX buffer is ever created (tx_active=0); the receiver
// listens on the external RF input and the full SDR -> DSP -> SignalPresence ->
// 24-class NPU -> AM-SSB merge -> UI chain runs per frame.  A non-present frame
// never publishes a classification (argmax_idx=-1, confidence=0).
// ---------------------------------------------------------------------------
int run_ambient_phase(chain::NpuClassifier24& npu, const cat::Contract& contract,
                      ui::StdoutSink& out, ui::UnixSocketSink& sock,
                      m22::StageTiming& timing, int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const float rec_scale = static_cast<float>(board::opt_d(argc, argv, "--rec-scale", 1.0));
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string ctl_sock = board::get_opt(argc, argv, "--ctl-sock",
                                                "/run/sdr_amr_control_rml23.sock");
    const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 64);
    const M22Config mcfg = read_m22_config(argc, argv);
    m22::ResourceSample first_res, last_res, peak_res;
    bool have_res = false;
    const std::size_t batch_frames = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--batch-frames", 16));
    const int stability_window = static_cast<int>(
        board::opt_u64(argc, argv, "--stability-window", 5));

    // ---- optional RF LO/BW override + RF diagnostics (the RF fix) -----------
    // --rx-lo / --rx-bw are AMBIENT-only.  When absent the OLD behaviour is kept
    // (no explicit LO/BW write); when present the write is read back and MUST land
    // within tolerance, otherwise the run fails closed (thrown -> emit FAIL).
    const bool have_rx_lo = rf_fix::opt_present(argc, argv, "--rx-lo");
    const bool have_rx_bw = rf_fix::opt_present(argc, argv, "--rx-bw");
    const long long rx_lo = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-lo", 0));
    const long long rx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-bw", 0));
    const bool rf_diag = board::has_flag(argc, argv, "--rf-diag");
    std::uint64_t rf_diag_interval =
        board::opt_u64(argc, argv, "--rf-diag-interval", 100);
    if (rf_diag_interval == 0) rf_diag_interval = 100;

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate9_full_chain_rml23", false,
                    std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool pass = false;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        const sdr::RateNegotiation neg =
            sdr::negotiate_sample_rate(*dev, sdr::default_rate_candidates(), 128000);
        if (!neg.ok) {
            detail = "negotiation_failed: " + neg.report();
        } else {
            detail = neg.report() + "; phase=ambient";
            const std::uint32_t fs_in = static_cast<std::uint32_t>(neg.actual_hz);

            {
                m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
                // RF configuration order (AD936x): sample rate is already
                // negotiated above; then RX LO -> RX RF bandwidth -> gain
                // mode=manual -> RX gain -> loopback=0, BEFORE the first RX buffer
                // refill.  An explicitly-requested LO/BW is read back and MUST land
                // within tolerance (fail-closed); when neither is provided the old
                // behaviour is kept unchanged.
                if (have_rx_lo) {
                    const long long got = dev->set_rx_lo(rx_lo);
                    if (!rf_fix::rf_readback_close(got, rx_lo, 1000LL, 1e-4)) {
                        throw std::runtime_error(
                            "rx_lo readback mismatch: requested=" +
                            std::to_string(rx_lo) +
                            " readback=" + std::to_string(got));
                    }
                }
                if (have_rx_bw) {
                    const long long got = dev->set_rx_bw(rx_bw);
                    if (!rf_fix::rf_readback_close(got, rx_bw, 1000LL, 0.05)) {
                        throw std::runtime_error(
                            "rx_bw readback mismatch: requested=" +
                            std::to_string(rx_bw) +
                            " readback=" + std::to_string(got));
                    }
                }
                dev->set_rx_gain_mode("manual");
                dev->set_rx_gain(gain_db);
                dev->set_loopback(0);
            }
            // Startup RF log: identity / channel / sample rate, then requested +
            // read-back for LO / BW / gain mode / gain / loopback.
            {
                const std::string lo_req = have_rx_lo ? std::to_string(rx_lo) : "-";
                const std::string bw_req = have_rx_bw ? std::to_string(rx_bw) : "-";
                std::printf(
                    "AMBIENT_RX tx_active=0 uri=%s serial=%s rx_channel=%s "
                    "sample_rate=%s rx_lo_req=%s rx_lo=%s rx_bw_req=%s rx_bw=%s "
                    "gain_mode=%s gain=%s loopback=%s\n",
                    rf_fix::rf_s(*dev, &pluto::Device::uri).c_str(),
                    rf_fix::rf_s(*dev, &pluto::Device::serial).c_str(),
                    rf_fix::rf_s(*dev, &pluto::Device::rx_channel_name).c_str(),
                    rf_fix::rf_ll(*dev, &pluto::Device::get_rx_sample_rate).c_str(),
                    lo_req.c_str(),
                    rf_fix::rf_ll(*dev, &pluto::Device::get_rx_lo).c_str(),
                    bw_req.c_str(),
                    rf_fix::rf_ll(*dev, &pluto::Device::get_rx_bw).c_str(),
                    rf_fix::rf_s(*dev, &pluto::Device::get_rx_gain_mode).c_str(),
                    rf_fix::rf_d(*dev, &pluto::Device::get_rx_gain).c_str(),
                    rf_fix::rf_i(*dev, &pluto::Device::get_loopback).c_str());
                std::fflush(stdout);
            }

            producer::ProducerConfig pcfg;
            pcfg.dsp.sample_rate_hz = 128000.0;
            pcfg.dsp.receiver_scale = rec_scale;
            pcfg.base_rf_gain_db = gain_db;
            pcfg.rf_gain_min_db = 0.0;
            pcfg.rf_gain_max_db = 50.0;
            pcfg.batch_frames = batch_frames;
            pcfg.stability_window = stability_window;

            PlutoDeviceControl devctl(*dev);
            producer::Producer12 prod(pcfg, devctl);     // FIXED by default

            ui::UnixSocketServer control(ctl_sock);
            if (!control.start()) {
                detail += " control_socket_bind_failed:" + ctl_sock;
                throw std::runtime_error("control socket bind failed");
            }

            ctl::CommandQueue cmdq(32);
            ctl::AckQueue ackq(32);
            ctl::ControlState cstate;
            ctl::ControlStats cstats;
            mode_ctl::ModeState mirror = prod.mode_state();
            cstate.requested_mode.store(static_cast<int>(mirror.mode));
            cstate.requested_running.store(
                mirror.run == mode_ctl::RunState::Running ? 1 : 0);
            cstate.applied_mode.store(static_cast<int>(mirror.mode));
            cstate.applied_running.store(
                mirror.run == mode_ctl::RunState::Running ? 1 : 0);

            std::thread ctl_thread(ctl::control_thread_main, std::ref(control),
                                   std::ref(cmdq), std::ref(ackq),
                                   std::ref(cstate), std::ref(cstats),
                                   std::ref(mirror));
            ControlThreadGuard ctl_guard;
            ctl_guard.t = &ctl_thread;
            ctl_guard.st = &cstate;

            std::printf("GATE9_AMBIENT_CTL_READY sock=%s %s\n", ctl_sock.c_str(),
                        mode_ctl::mode_state_line(prod.mode_state()).c_str());
            std::fflush(stdout);

            std::string last_presence_state;

            const std::int64_t kApplyTimeoutMs = 2000;
            auto apply_pending = [&](const char* tag) {
                ctl::Command c;
                while (cmdq.try_pop(c)) {
                    const std::int64_t t0 = ctl::now_us();
                    const mode_ctl::ModeState before = prod.mode_state();
                    const std::string resp = prod.apply_command(c.raw);
                    const mode_ctl::ModeState after = prod.mode_state();

                    ackq.try_push("OK applied command_id=" + std::to_string(c.id) +
                                  " " + c.raw);

                    cstate.applied_mode.store(static_cast<int>(after.mode));
                    cstate.applied_running.store(
                        after.run == mode_ctl::RunState::Running ? 1 : 0);
                    cstate.last_applied_command_id.store(c.id);
                    cstate.queue_depth.store(cmdq.depth());
                    cstats.applied.fetch_add(1);

                    const std::int64_t lat = (ctl::now_us() - t0) / 1000;
                    std::int64_t am = cstats.max_apply_latency_ms.load();
                    while (lat > am &&
                           !cstats.max_apply_latency_ms.compare_exchange_weak(am, lat)) {}
                    if (lat > kApplyTimeoutMs) cstats.timeouts.fetch_add(1);

                    if (after.mode != before.mode || after.run != before.run) {
                        emit_state_event(out, sock, after, last_presence_state, c.id, model_sha);
                        std::printf("CONTROL_EVENT command_id=%llu mode=%s running=%s "
                                    "apply_ms=%lld tag=%s\n",
                                    static_cast<unsigned long long>(c.id),
                                    mode_ctl::mode_token(after.mode),
                                    mode_ctl::run_display_name(after.run),
                                    static_cast<long long>(lat), tag);
                    }
                    std::printf("GATE9_MODE_CTL cmd=%s -> %s apply_ms=%lld tag=%s\n",
                                c.raw.c_str(), resp.c_str(),
                                static_cast<long long>(lat), tag);
                    std::fflush(stdout);
                }
            };

            emit_state_event(out, sock, prod.mode_state(), "", 0, model_sha);
            auto last_state_emit = Clock::now();

            std::uint64_t total_processed = 0;
            std::size_t valid = 0, published = 0, present = 0, nosignal = 0;
            std::size_t published_while_not_present = 0;
            bool stream_broken = false, continuity_ok_all = true, interrupted = false;
            std::uint64_t presence_transitions = 0;

            chain::PreprocessChain chain(fs_in, nco_offset, rec_scale);
            std::vector<float> tensor(chain::kTensorFloats);
            std::vector<std::int16_t> iq;

            ui::NullSink null_out;
            ui::Sink& frame_out = mcfg.verbose
                ? static_cast<ui::Sink&>(out) : static_cast<ui::Sink&>(null_out);

            first_res = m22::read_resources();
            have_res = true;

            while (!board::g_stop_requested && total_processed < frames) {
                apply_pending("loop_top");
                // Steady-clock heartbeat (1000 ms): refresh the UI's data-chain
                // health clock with a state record even while STOPPED, when no
                // classification frames flow.  A state record is never a fabricated
                // classification.
                {
                    const auto hb_now = Clock::now();
                    if (std::chrono::duration_cast<std::chrono::milliseconds>(
                            hb_now - last_state_emit).count() >= 1000) {
                        last_state_emit = hb_now;
                        emit_state_event(out, sock, prod.mode_state(),
                                         last_presence_state, 0, model_sha);
                    }
                }
                if (!prod.running()) {
                    apply_pending("stopped");
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    continue;
                }

                apply_pending("before_capture");
                prod.before_capture();
                std::size_t batch = prod.capture_batch_frames();
                if (batch > frames - total_processed)
                    batch = static_cast<std::size_t>(frames - total_processed);

                chain.reset();
                const std::size_t requested = chain.required_input(batch);
                board::RxStats st;
                board::Continuity cont;
                apply_pending("before_rx_refill");
                const bool captured = [&]() {
                    m22::StageTiming::Timer t(timing, m22::StageId::RxRefill);
                    return board::capture_contiguous(*dev, requested, iq, st, cont);
                }();
                if (st.interrupted) { interrupted = true; break; }
                if (!captured) { stream_broken = true; break; }
                if (!cont.ok()) continuity_ok_all = false;
                apply_pending("after_rx_refill");

                {
                    m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                    chain.push_int16(iq.data(), iq.size() / 2);
                }
                std::size_t produced_batch = 0;
                while (chain.ready() > 0 && produced_batch < batch &&
                       total_processed < frames) {
                    apply_pending("frame_top");
                    if (!prod.running()) break;

                    if (!chain.pull_tensor(tensor.data())) break;

                    producer::CaptureFlags flags;
                    flags.overflow = st.overflow != 0;
                    flags.dropped = st.dropped != 0;
                    flags.discontinuity = st.discontinuity != 0;
                    flags.short_frame = st.short_block;

                    apply_pending("before_infer");
                    if (!prod.running()) break;

                    const auto ft0 = Clock::now();
                    ++produced_batch;
                    ++total_processed;

                    double classify_us = 0.0;
                    std::vector<float> raw24_frame(rml23::kNpuOutputDim);
                    producer::ProducerDecision d = prod.on_frame(
                        tensor.data(), flags,
                        [&](const float* t, std::vector<float>& lg) {
                            const auto t0 = Clock::now();
                            npu.infer(t, raw24_frame);   // 24-dim raw logits (reused)
                            const auto t1 = Clock::now();
                            if (raw24_frame.size() != static_cast<std::size_t>(rml23::kNpuOutputDim))
                                throw std::runtime_error("rml23: raw logits width != 24");
                            float m23[rml23::kDeployedClassCount];
                            if (!rml23::merge_logits_23(raw24_frame.data(), m23))
                                throw std::runtime_error(
                                    "rml23: merge fail-closed (non-finite logits)");
                            lg.assign(m23, m23 + rml23::kDeployedClassCount);
                            classify_us = static_cast<double>(
                                std::chrono::duration_cast<std::chrono::microseconds>(
                                    t1 - t0).count());
                            timing.record(m22::StageId::NpuInfer, classify_us);
                        });

                    const bool present_now = (d.presence_state == "SIGNAL_PRESENT");
                    if (d.presence_state == "NO_SIGNAL") ++nosignal;

                    if (!d.presence_state.empty() && d.presence_state != last_presence_state) {
                        if (!last_presence_state.empty()) ++presence_transitions;
                        std::printf("PRESENCE_TRANSITION from=%s to=%s frame=%llu\n",
                                    last_presence_state.empty() ? "-" : last_presence_state.c_str(),
                                    d.presence_state.c_str(),
                                    static_cast<unsigned long long>(total_processed));
                        std::fflush(stdout);
                        last_presence_state = d.presence_state;
                    }

                    const auto pp0 = Clock::now();
                    rf::ResultFrame r;
                    r.frame_id = total_processed;
                    r.timestamp_us = static_cast<std::uint64_t>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now().time_since_epoch()).count());
                    r.source = "fpga_npu";
                    r.mock = false;
                    r.overflow = flags.overflow;
                    r.dropped = flags.dropped;
                    r.discontinuity = flags.discontinuity;
                    r.short_frame = flags.short_frame;
                    chain::fill_result_rml23(r, raw24_frame, d.logits, contract,
                                             model_sha,
                                             std::numeric_limits<double>::quiet_NaN());
                    r.has_measurements = d.has_measurements;
                    r.measurements = d.measurements;
                    r.presence_state = d.presence_state;
                    r.level_mode = d.level_mode;
                    r.model_scale = d.model_scale;
                    r.rf_gain_db = d.rf_gain_db;
                    r.work_mode = d.work_mode;
                    r.run_state = d.run_state;
                    r.classify_us = classify_us;
                    r.e2e_us = classify_us;

                    if (d.publish && d.published_class >= 0 &&
                        d.published_class < static_cast<int>(r.probabilities.size())) {
                        r.argmax_idx = d.published_class;
                        r.argmax_class = cat::label(contract, d.published_class);
                        r.confidence = r.probabilities[static_cast<std::size_t>(d.published_class)];
                        ++published;
                        if (!present_now) ++published_while_not_present;
                    } else {
                        r.argmax_idx = -1;
                        r.argmax_class = "";
                        r.confidence = 0.0f;
                        r.quality = 0.0;
                    }
                    timing.record(m22::StageId::Postprocess, static_cast<double>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now() - pp0).count()));

                    apply_pending("before_emit");
                    {
                        m22::StageTiming::Timer t(timing, m22::StageId::UiSubmit);
                        emit_frame(frame_out, sock, r);
                    }
                    if (result_frame_v3_valid(r)) ++valid;
                    if (present_now) ++present;
                    timing.record(m22::StageId::FrameTotal, static_cast<double>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now() - ft0).count()));
                    if (total_processed % mcfg.summary_interval == 0) {
                        const m22::ResourceSample cur = m22::read_resources();
                        peak_res = peak_of(peak_res, cur);
                        print_m22_summary(timing, cur, total_processed);
                    }
                    // Optional per-N-frame RF diagnostic summary (no per-frame
                    // serial spam): confirms LO/BW/gain/loopback stay put.
                    if (rf_diag && total_processed % rf_diag_interval == 0) {
                        std::printf(
                            "RF_DIAG frame=%llu rx_lo=%s rx_bw=%s gain_mode=%s "
                            "gain=%s loopback=%s sample_rate=%s\n",
                            static_cast<unsigned long long>(total_processed),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_lo).c_str(),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_bw).c_str(),
                            rf_fix::rf_s(*dev, &pluto::Device::get_rx_gain_mode).c_str(),
                            rf_fix::rf_d(*dev, &pluto::Device::get_rx_gain).c_str(),
                            rf_fix::rf_i(*dev, &pluto::Device::get_loopback).c_str(),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_sample_rate).c_str());
                        std::fflush(stdout);
                    }
                    apply_pending("frame_end");
                }
                apply_pending("batch_end");
            }

            apply_pending("final");
            cstate.stop.store(true);
            ctl_thread.join();
            control.stop();

            last_res = m22::read_resources();
            peak_res = peak_of(peak_res, last_res);
            if (have_res)
                finish_m22_runtime("ambient", model_sha, npu, timing, first_res,
                                   last_res, peak_res, mcfg);

            const bool frames_ok = (total_processed == frames);
            const bool no_fake_class = (published_while_not_present == 0);
            const bool control_ok = (cstats.rejected.load() == 0 &&
                                     cstats.timeouts.load() == 0);
            pass = !stream_broken && !interrupted && continuity_ok_all && frames_ok &&
                   no_fake_class && control_ok && (valid == total_processed);

            detail += " frames=" + std::to_string(total_processed) + "/" + std::to_string(frames);
            detail += " valid=" + std::to_string(valid);
            detail += " published=" + std::to_string(published);
            detail += " present=" + std::to_string(present);
            detail += " nosignal=" + std::to_string(nosignal);
            detail += " presence_transitions=" + std::to_string(presence_transitions);
            detail += " published_while_not_present=" + std::to_string(published_while_not_present);
            detail += " tx_active=0";
            detail += " rec_scale=" + std::to_string(rec_scale);
            detail += " nco_offset=" + std::to_string(nco_offset);
            detail += " interrupted=" + std::to_string(interrupted ? 1 : 0);
            detail += " control_received=" + std::to_string(cstats.received.load());
            detail += " control_accepted=" + std::to_string(cstats.accepted.load());
            detail += " control_applied=" + std::to_string(cstats.applied.load());
            detail += " control_rejected=" + std::to_string(cstats.rejected.load());
            detail += " control_timeouts=" + std::to_string(cstats.timeouts.load());

            std::printf("CONTROL_STATS received=%llu accepted=%llu applied=%llu "
                        "rejected=%llu timeouts=%llu queue_max_depth=%llu "
                        "max_accept_ms=%lld max_apply_ms=%lld\n",
                        static_cast<unsigned long long>(cstats.received.load()),
                        static_cast<unsigned long long>(cstats.accepted.load()),
                        static_cast<unsigned long long>(cstats.applied.load()),
                        static_cast<unsigned long long>(cstats.rejected.load()),
                        static_cast<unsigned long long>(cstats.timeouts.load()),
                        static_cast<unsigned long long>(cstats.queue_max_depth.load()),
                        static_cast<long long>(cstats.max_accept_latency_ms.load()),
                        static_cast<long long>(cstats.max_apply_latency_ms.load()));
            std::fflush(stdout);

            if (stream_broken) detail += " (stream_broken)";
            if (!continuity_ok_all) detail += " (continuity_fail)";
            if (!frames_ok) detail += " (frame_short)";
            if (!no_fake_class) detail += " (fake_classification_on_nosignal)";
            if (!control_ok) detail += " (control_rejected_or_timeout)";
            if (valid != total_processed) detail += " (invalid_frames)";
            if (interrupted) detail += " (interrupted)";
        }

        guard->restore();
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    if (guard) {
        guard->restore();
        detail += board::restore_report(*dev, *guard);
        pass = board::final_gate_pass(pass, guard->restore_ok(), detail);
    } else {
        pass = false;
        detail += " (no_state_guard)";
    }

    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}

// ==== LIVE-RX PHASE (Task C) BEGIN ====
// ---------------------------------------------------------------------------
// Phase 5: live-rx -- REAL external RX classification (M29 Phase F5 Task C).
//
// RX-only: NO TX buffer is ever created, loopback=0.  Unlike --phase=ambient
// (which runs the NPU every frame and only withholds the PUBLISH), this phase
// GATES the NPU on signal presence:
//
//   NO_SIGNAL        -> measurement + presence only, NO NPU, periodic state
//                       heartbeat (type:"state") carries the presence state.
//   SIGNAL_PRESENT   -> SDR -> preprocess -> NPU(24 raw) -> AM-SSB merge(23) ->
//                       rml23-chain-v2 result frame -> UI data socket.
//   signal gone      -> stop NPU calls, resume the NO_SIGNAL heartbeat.
//
// The NPU is opened once (NpuClassifier24, in main) and applied once; frames are
// forwarded without re-open / re-apply.  Per-100-frame diagnostics report
// adc_rms / adc_peak / clip_ratio / presence_state / accepted_frames / npu_runs /
// result_sent / result_dropped.
// ---------------------------------------------------------------------------
int run_live_rx_phase(chain::NpuClassifier24& npu, const cat::Contract& contract,
                      ui::StdoutSink& out, ui::UnixSocketSink& sock,
                      m22::StageTiming& timing, int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const float rec_scale = static_cast<float>(board::opt_d(argc, argv, "--rec-scale", 1.0));
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    // 0 => run until stopped (SIGINT/SIGTERM); a positive count runs N frames.
    const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 0);
    const M22Config mcfg = read_m22_config(argc, argv);
    m22::ResourceSample first_res, last_res, peak_res;
    bool have_res = false;
    const std::size_t batch_frames = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--batch-frames", 16));

    // Optional RX LO/BW override + RF diagnostics (identical to --phase=ambient).
    const bool have_rx_lo = rf_fix::opt_present(argc, argv, "--rx-lo");
    const bool have_rx_bw = rf_fix::opt_present(argc, argv, "--rx-bw");
    const long long rx_lo = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-lo", 0));
    const long long rx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-bw", 0));
    const bool rf_diag = board::has_flag(argc, argv, "--rf-diag");
    std::uint64_t rf_diag_interval =
        board::opt_u64(argc, argv, "--rf-diag-interval", 100);
    if (rf_diag_interval == 0) rf_diag_interval = 100;

    // Capture hook (errata 39e5 Stage C, #6): when --capture-dir is given, the
    // EXACT [2,1024] fp32 tensor fed to the NPU for each SIGNAL_PRESENT frame is
    // atomically dumped to disk for offline re-analysis (Evidence 2/3/4).  Empty
    // (the default) disables capture entirely -- no file I/O on the hot path.
    const std::string capture_dir = board::get_opt(argc, argv, "--capture-dir", "");
    board::TensorCapture capture(capture_dir);

    // Raw-24 logits export (errata 39e5 Stage E, #7): when --logits-export DIR is
    // given, each SIGNAL_PRESENT frame's pre-merge 24-dim NPU logits are dumped to
    // DIR/logits_<frame_id>.json keyed by the captured input SHA-256.  Empty (the
    // default) disables it.  The input key is the capture SHA when capture is on,
    // otherwise the tensor SHA is computed inline so the export stays self-keyed.
    const std::string logits_dir = board::get_opt(argc, argv, "--logits-export", "");
    const board::LogitsExport logits_export(logits_dir);

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate9_full_chain_rml23", false,
                    std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool pass = false;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        const sdr::RateNegotiation neg =
            sdr::negotiate_sample_rate(*dev, sdr::default_rate_candidates(), 128000);
        if (!neg.ok) {
            detail = "negotiation_failed: " + neg.report();
        } else {
            detail = neg.report() + "; phase=live-rx";
            const std::uint32_t fs_in = static_cast<std::uint32_t>(neg.actual_hz);

            {
                m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
                if (have_rx_lo) {
                    const long long got = dev->set_rx_lo(rx_lo);
                    if (!rf_fix::rf_readback_close(got, rx_lo, 1000LL, 1e-4))
                        throw std::runtime_error(
                            "rx_lo readback mismatch: requested=" +
                            std::to_string(rx_lo) +
                            " readback=" + std::to_string(got));
                }
                if (have_rx_bw) {
                    const long long got = dev->set_rx_bw(rx_bw);
                    if (!rf_fix::rf_readback_close(got, rx_bw, 1000LL, 0.05))
                        throw std::runtime_error(
                            "rx_bw readback mismatch: requested=" +
                            std::to_string(rx_bw) +
                            " readback=" + std::to_string(got));
                }
                dev->set_rx_gain_mode("manual");
                dev->set_rx_gain(gain_db);
                dev->set_loopback(0);   // RX only: NO TX buffer is ever created
            }

            // Startup RF log (mirrors ambient; distinct LIVE_RX tag so the two
            // modes stay independently greppable in the board log).
            {
                const std::string lo_req = have_rx_lo ? std::to_string(rx_lo) : "-";
                const std::string bw_req = have_rx_bw ? std::to_string(rx_bw) : "-";
                std::printf(
                    "LIVE_RX tx_active=0 uri=%s serial=%s rx_channel=%s "
                    "sample_rate=%s rx_lo_req=%s rx_lo=%s rx_bw_req=%s rx_bw=%s "
                    "gain_mode=%s gain=%s loopback=%s\n",
                    rf_fix::rf_s(*dev, &pluto::Device::uri).c_str(),
                    rf_fix::rf_s(*dev, &pluto::Device::serial).c_str(),
                    rf_fix::rf_s(*dev, &pluto::Device::rx_channel_name).c_str(),
                    rf_fix::rf_ll(*dev, &pluto::Device::get_rx_sample_rate).c_str(),
                    lo_req.c_str(),
                    rf_fix::rf_ll(*dev, &pluto::Device::get_rx_lo).c_str(),
                    bw_req.c_str(),
                    rf_fix::rf_ll(*dev, &pluto::Device::get_rx_bw).c_str(),
                    rf_fix::rf_s(*dev, &pluto::Device::get_rx_gain_mode).c_str(),
                    rf_fix::rf_d(*dev, &pluto::Device::get_rx_gain).c_str(),
                    rf_fix::rf_i(*dev, &pluto::Device::get_loopback).c_str());
                std::fflush(stdout);
            }

            // Direct measurement + presence-gated classification.  NO Producer12:
            // Producer12::on_frame runs the NPU EVERY frame; live-rx only runs it
            // on SIGNAL_PRESENT.
            sdr::DspMeasureConfig dcfg;
            dcfg.sample_rate_hz = 128000.0;
            dcfg.receiver_scale = rec_scale;
            sdr::DspMeasure dsp(dcfg);
            live_rx::Gating gating;

            // Control channel (errata 39e5, Evidence 6): live-rx previously had NO
            // control socket, so the UI showed CTRL DISCONNECTED and start_all
            // reported producer_ctl_socket_not_ready.  Commands apply to `mst`
            // directly (there is no Producer12); STOP flips mst.run to Stopped while
            // the 1000 ms state heartbeat keeps flowing (UI shows STOPPED, not STALE).
            mode_ctl::ModeState mst;
            const std::string ctl_sock = board::get_opt(argc, argv, "--ctl-sock",
                                                        "/run/sdr_amr_control_rml23.sock");
            ui::UnixSocketServer control(ctl_sock);
            if (!control.start()) {
                detail += " control_socket_bind_failed:" + ctl_sock;
                throw std::runtime_error("control socket bind failed");
            }
            ctl::CommandQueue cmdq(32);
            ctl::AckQueue ackq(32);
            ctl::ControlState cstate;
            ctl::ControlStats cstats;
            mode_ctl::ModeState mirror = mst;
            cstate.requested_mode.store(static_cast<int>(mirror.mode));
            cstate.requested_running.store(
                mirror.run == mode_ctl::RunState::Running ? 1 : 0);
            cstate.applied_mode.store(static_cast<int>(mirror.mode));
            cstate.applied_running.store(
                mirror.run == mode_ctl::RunState::Running ? 1 : 0);
            std::thread ctl_thread(ctl::control_thread_main, std::ref(control),
                                   std::ref(cmdq), std::ref(ackq),
                                   std::ref(cstate), std::ref(cstats),
                                   std::ref(mirror));
            ControlThreadGuard ctl_guard;
            ctl_guard.t = &ctl_thread;
            ctl_guard.st = &cstate;
            std::printf("LIVE_RX_CONTROL_READY sock=%s %s\n", ctl_sock.c_str(),
                        mode_ctl::mode_state_line(mst).c_str());
            std::fflush(stdout);

            chain::PreprocessChain chain(fs_in, nco_offset, rec_scale);
            std::vector<float> tensor(chain::kTensorFloats);
            std::vector<std::int16_t> iq;
            std::vector<std::complex<float>> cf(chain::kFrameComplex);
            sdr::MeasureScratch dsp_scratch;

            std::string last_presence_state;
            const std::int64_t kApplyTimeoutMs = 2000;
            auto apply_pending = [&](const char* tag) {
                ctl::Command c;
                while (cmdq.try_pop(c)) {
                    const std::int64_t t0 = ctl::now_us();
                    const mode_ctl::ModeState before = mst;
                    const std::string resp = mode_ctl::apply_command(mst, c.raw);
                    const mode_ctl::ModeState after = mst;

                    ackq.try_push("OK applied command_id=" + std::to_string(c.id) +
                                  " " + c.raw);
                    cstate.applied_mode.store(static_cast<int>(after.mode));
                    cstate.applied_running.store(
                        after.run == mode_ctl::RunState::Running ? 1 : 0);
                    cstate.last_applied_command_id.store(c.id);
                    cstate.queue_depth.store(cmdq.depth());
                    cstats.applied.fetch_add(1);

                    const std::int64_t lat = (ctl::now_us() - t0) / 1000;
                    std::int64_t am = cstats.max_apply_latency_ms.load();
                    while (lat > am &&
                           !cstats.max_apply_latency_ms.compare_exchange_weak(am, lat)) {}
                    if (lat > kApplyTimeoutMs) cstats.timeouts.fetch_add(1);

                    if (after.mode != before.mode || after.run != before.run) {
                        emit_state_event(out, sock, after, last_presence_state, c.id,
                                         model_sha);
                        std::printf("CONTROL_EVENT command_id=%llu mode=%s running=%s "
                                    "apply_ms=%lld tag=%s\n",
                                    static_cast<unsigned long long>(c.id),
                                    mode_ctl::mode_token(after.mode),
                                    mode_ctl::run_display_name(after.run),
                                    static_cast<long long>(lat), tag);
                    }
                    std::printf("LIVE_RX_CONTROL cmd=%s -> %s apply_ms=%lld tag=%s\n",
                                c.raw.c_str(), resp.c_str(),
                                static_cast<long long>(lat), tag);
                    std::fflush(stdout);
                }
            };

            emit_state_event(out, sock, mst, "", 0, model_sha);
            auto last_state_emit = Clock::now();

            std::uint64_t total_processed = 0;
            std::size_t valid = 0;
            std::uint64_t presence_transitions = 0;
            bool stream_broken = false, continuity_ok_all = true, interrupted = false;

            first_res = m22::read_resources();
            have_res = true;

            while (!board::g_stop_requested && (frames == 0 || total_processed < frames)) {
                apply_pending("loop_top");
                // Steady-clock heartbeat (1000 ms): refreshes the UI data-chain
                // health clock and carries the last presence state even while no
                // classification frames flow (NO_SIGNAL).  A state record is never
                // a fabricated classification.
                {
                    const auto hb_now = Clock::now();
                    if (std::chrono::duration_cast<std::chrono::milliseconds>(
                            hb_now - last_state_emit).count() >= 1000) {
                        last_state_emit = hb_now;
                        emit_state_event(out, sock, mst, last_presence_state, 0, model_sha);
                    }
                }

                // STOPPED: stop classifying (no NPU, no result frame) but keep the
                // state heartbeat alive so the UI shows STOPPED, never STALE.
                if (mst.run == mode_ctl::RunState::Stopped) {
                    apply_pending("stopped");
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    continue;
                }

                const std::size_t batch = batch_frames;
                chain.reset();
                const std::size_t requested = chain.required_input(batch);
                board::RxStats st;
                board::Continuity cont;
                const bool captured = [&]() {
                    m22::StageTiming::Timer t(timing, m22::StageId::RxRefill);
                    return board::capture_contiguous(*dev, requested, iq, st, cont);
                }();
                if (st.interrupted) { interrupted = true; break; }
                if (!captured) { stream_broken = true; break; }
                if (!cont.ok()) continuity_ok_all = false;

                {
                    m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                    chain.push_int16(iq.data(), iq.size() / 2);
                }
                std::size_t produced_batch = 0;
                while (chain.ready() > 0 && produced_batch < batch &&
                       (frames == 0 || total_processed < frames)) {
                    apply_pending("frame_top");
                    if (mst.run == mode_ctl::RunState::Stopped) break;
                    if (!chain.pull_tensor(tensor.data())) break;

                    const auto ft0 = Clock::now();
                    ++produced_batch;
                    ++total_processed;

                    // Count-domain frame -> real measurements -> presence.
                    const double rec = (rec_scale > 0.0f) ? rec_scale : 1.0f;
                    const float count_scale = static_cast<float>(2048.0 / rec);
                    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
                        cf[k] = std::complex<float>(tensor[k] * count_scale,
                                                    tensor[chain::kFrameComplex + k] * count_scale);
                    const sdr::FrameMeasurements m =
                        dsp.measure_into(cf.data(), chain::kFrameComplex, dsp_scratch);

                    sdr::PresenceInput pi;
                    pi.power_dbfs = m.power_dbfs;
                    pi.noise_floor_dbfs = m.noise_floor_dbfs;
                    pi.snr_est_db = m.snr_est_db;
                    pi.psd_peak_prominence_db = m.psd_peak_prominence_db;
                    pi.clip_ratio = m.clip_ratio;
                    pi.occupied_bins = m.occupied_bins;
                    pi.nan_inf = m.nan_inf;
                    pi.capture_error = st.overflow != 0 || st.dropped != 0 ||
                                       st.discontinuity != 0 || st.short_block;
                    const sdr::PresenceState ps = gating.update(pi);
                    const std::string ps_name = sdr::presence_state_name(ps);

                    if (ps_name != last_presence_state) {
                        if (!last_presence_state.empty()) ++presence_transitions;
                        std::printf("PRESENCE_TRANSITION from=%s to=%s frame=%llu\n",
                                    last_presence_state.empty() ? "-" : last_presence_state.c_str(),
                                    ps_name.c_str(),
                                    static_cast<unsigned long long>(total_processed));
                        std::fflush(stdout);
                        last_presence_state = ps_name;
                        // Emit immediately so the UI sees the transition without
                        // waiting for the next 1000 ms heartbeat.
                        emit_state_event(out, sock, mst, last_presence_state, 0, model_sha);
                    }

                    // Presence-gated NPU: only a confirmed SIGNAL_PRESENT frame is
                    // classified.  Every other state keeps the loop in the
                    // NO-SIGNAL heartbeat path (no NPU call, no result frame).
                    if (live_rx::classify_now(ps)) {
                        gating.record_accepted();
                        const auto t_inf0 = Clock::now();
                        std::vector<float> raw24(rml23::kNpuOutputDim);
                        // Atomic capture of the EXACT tensor the NPU is about to
                        // consume (before infer, so capture bytes == infer bytes).
                        std::string cap_sha;
                        if (capture.enabled()) {
                            cap_sha = capture.capture(total_processed, tensor.data(),
                                                      chain::kTensorFloats);
                            std::printf(
                                "LIVE_RX_CAPTURE frame=%llu bytes=%u sha256=%s "
                                "presence=%s\n",
                                static_cast<unsigned long long>(total_processed),
                                static_cast<unsigned>(chain::kTensorBytes),
                                cap_sha.empty() ? "<write_failed>" : cap_sha.c_str(),
                                ps_name.c_str());
                            std::fflush(stdout);
                        }
                        npu.infer(tensor.data(), raw24);
                        const auto t_inf1 = Clock::now();
                        const double classify_us = static_cast<double>(
                            std::chrono::duration_cast<std::chrono::microseconds>(
                                t_inf1 - t_inf0).count());
                        timing.record(m22::StageId::NpuInfer, classify_us);

                        if (logits_export.enabled()) {
                            const std::string in_sha =
                                cap_sha.empty()
                                    ? sdr::Sha256::hex(tensor.data(), chain::kTensorBytes)
                                    : cap_sha;
                            const std::string key = logits_export.export_frame(
                                total_processed, in_sha, model_sha,
                                raw24.data(), raw24.size());
                            std::printf(
                                "LIVE_RX_LOGITS frame=%llu input_sha256=%s exported=%s\n",
                                static_cast<unsigned long long>(total_processed),
                                in_sha.c_str(), key.empty() ? "no" : "yes");
                            std::fflush(stdout);
                        }

                        float m23[rml23::kDeployedClassCount];
                        const bool merged_ok = rml23::merge_logits_23(raw24.data(), m23);
                        gating.record_merge(merged_ok);
                        if (merged_ok) {
                            const std::vector<float> merged23(
                                m23, m23 + rml23::kDeployedClassCount);
                            rf::ResultFrame r;
                            r.frame_id = total_processed;
                            r.timestamp_us = static_cast<std::uint64_t>(
                                std::chrono::duration_cast<std::chrono::microseconds>(
                                    Clock::now().time_since_epoch()).count());
                            r.source = "fpga_npu";
                            r.mock = false;
                            r.overflow = st.overflow != 0;
                            r.dropped = st.dropped != 0;
                            r.discontinuity = st.discontinuity != 0;
                            r.short_frame = st.short_block;
                            chain::fill_result_rml23(r, raw24, merged23, contract,
                                                     model_sha,
                                                     std::numeric_limits<double>::quiet_NaN());
                            r.has_measurements = true;
                            r.measurements = m;
                            r.presence_state = ps_name;
                            r.level_mode = "FIXED";
                            // model_scale is the M2 (auto-level) digital scalar applied
                            // ON TOP of the receiver_scale tensor (see run_loopback_phase
                            // header comment).  live-rx has no auto-level engine -- it is
                            // always FIXED -- so this is the identity 1.0.  The actual
                            // receiver scale is rec_scale, applied separately by
                            // chain::PreprocessChain and never stored in model_scale.
                            r.model_scale = 1.0;
                            r.rf_gain_db = gain_db;
                            r.work_mode = mode_ctl::mode_token(mst.mode);
                            r.run_state = mode_ctl::run_display_name(mst.run);
                            r.classify_us = classify_us;
                            r.e2e_us = classify_us;
                            // Present => publish the merged 23-class argmax.
                            r.argmax_idx = r.merged_23_top1;
                            r.argmax_class = cat::label(contract, r.argmax_idx);
                            r.confidence = (r.argmax_idx >= 0 &&
                                r.argmax_idx < static_cast<int>(r.probabilities.size()))
                                   ? r.probabilities[static_cast<std::size_t>(r.argmax_idx)]
                                   : 0.0f;

                            emit_frame(out, sock, r);
                            if (result_frame_v3_valid(r)) ++valid;
                        }
                    }

                    timing.record(m22::StageId::FrameTotal, static_cast<double>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now() - ft0).count()));

                    if (mcfg.summary_interval && total_processed % mcfg.summary_interval == 0) {
                        const m22::ResourceSample cur = m22::read_resources();
                        peak_res = peak_of(peak_res, cur);
                        print_m22_summary(timing, cur, total_processed);
                    }
                    // Per-100-frame diagnostics: adc_rms / adc_peak / clip_ratio /
                    // presence_state + the gating counters.
                    if (total_processed % 100 == 0) {
                        const live_rx::GatingCounters gc = gating.counters();
                        std::printf(
                            "LIVE_RX_DIAG frame=%llu adc_rms=%.3f adc_peak=%.3f "
                            "clip_ratio=%.6f presence_state=%s accepted_frames=%llu "
                            "npu_runs=%llu result_sent=%llu result_dropped=%llu\n",
                            static_cast<unsigned long long>(total_processed),
                            m.rms_counts, m.peak_counts, m.clip_ratio,
                            ps_name.c_str(),
                            static_cast<unsigned long long>(gc.accepted_frames),
                            static_cast<unsigned long long>(gc.npu_runs),
                            static_cast<unsigned long long>(gc.result_sent),
                            static_cast<unsigned long long>(gc.result_dropped));
                        std::fflush(stdout);
                    }
                    if (rf_diag && total_processed % rf_diag_interval == 0) {
                        std::printf(
                            "RF_DIAG frame=%llu rx_lo=%s rx_bw=%s gain_mode=%s "
                            "gain=%s loopback=%s sample_rate=%s\n",
                            static_cast<unsigned long long>(total_processed),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_lo).c_str(),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_bw).c_str(),
                            rf_fix::rf_s(*dev, &pluto::Device::get_rx_gain_mode).c_str(),
                            rf_fix::rf_d(*dev, &pluto::Device::get_rx_gain).c_str(),
                            rf_fix::rf_i(*dev, &pluto::Device::get_loopback).c_str(),
                            rf_fix::rf_ll(*dev, &pluto::Device::get_rx_sample_rate).c_str());
                        std::fflush(stdout);
                    }
                }
            }

            last_res = m22::read_resources();
            peak_res = peak_of(peak_res, last_res);
            if (have_res)
                finish_m22_runtime("live-rx", model_sha, npu, timing, first_res,
                                   last_res, peak_res, mcfg);

            const live_rx::GatingCounters gc = gating.counters();
            const bool frames_ok = (frames == 0) ? true : (total_processed == frames);
            const bool gating_ok = gating.invariants_ok() && (gc.result_dropped == 0);
            const bool no_fake_result = (gc.npu_runs == gc.accepted_frames) &&
                                        (gc.result_sent == gc.accepted_frames);
            pass = !stream_broken && !interrupted && continuity_ok_all && frames_ok &&
                   gating_ok && no_fake_result && (valid == gc.result_sent);

            detail += " frames=" + std::to_string(total_processed);
            if (frames != 0) detail += "/" + std::to_string(frames);
            detail += " valid=" + std::to_string(valid);
            detail += " accepted_frames=" + std::to_string(gc.accepted_frames);
            detail += " npu_runs=" + std::to_string(gc.npu_runs);
            detail += " result_sent=" + std::to_string(gc.result_sent);
            detail += " result_dropped=" + std::to_string(gc.result_dropped);
            detail += " presence_transitions=" + std::to_string(presence_transitions);
            detail += " tx_active=0";
            detail += " rec_scale=" + std::to_string(rec_scale);
            detail += " nco_offset=" + std::to_string(nco_offset);
            detail += " rx_gain_db=" + std::to_string(gain_db);
            if (!capture_dir.empty()) detail += " capture_dir=" + capture_dir;
            detail += " interrupted=" + std::to_string(interrupted ? 1 : 0);

            if (stream_broken) detail += " (stream_broken)";
            if (!continuity_ok_all) detail += " (continuity_fail)";
            if (!frames_ok) detail += " (frame_short)";
            if (!gating_ok) detail += " (gating_violation)";
            if (!no_fake_result) detail += " (result_count_mismatch)";
            if (valid != gc.result_sent) detail += " (invalid_frames)";
            if (interrupted) detail += " (interrupted)";
        }

        guard->restore();
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    if (guard) {
        guard->restore();
        detail += board::restore_report(*dev, *guard);
        pass = board::final_gate_pass(pass, guard->restore_ok(), detail);
    } else {
        pass = false;
        detail += " (no_state_guard)";
    }

    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}
// ==== LIVE-RX PHASE (Task C) END ====

// ---------------------------------------------------------------------------
// Route D: RadioML round-trip preprocess (Stage G追加硬要求).  Same frozen test
// tensor as route A, pushed through the production PreprocessChain via a
// deterministic x20 polyphase interpolation, then A vs D raw24/merged23 compared
// one-to-one.  Per-frame attribution uses the 5 rules (never claims "fixed").
// ---------------------------------------------------------------------------
int run_route_d_roundtrip(chain::NpuClassifier24& npu, const cat::Contract& contract,
                          ui::StdoutSink& out, ui::UnixSocketSink& sock,
                          m22::StageTiming& timing, int argc, char** argv) {
    (void)out; (void)sock; (void)contract;
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const M22Config mcfg = read_m22_config(argc, argv);
    const m22::ResourceSample first_res = m22::read_resources();

    // --- inputs / outputs (fail-closed) ---
    const std::string bin_dir = board::get_opt(argc, argv, "--radioml-bin-dir", "");
    if (bin_dir.empty())
        throw std::runtime_error("route D requires --radioml-bin-dir=<extracted dir>");
    if (bin_dir.size() >= 5 &&
        bin_dir.compare(bin_dir.size() - 5, 5, ".hdf5") == 0)
        throw std::runtime_error("RADIOML_HDF5_HOST_EXTRACTION_REQUIRED: pass the "
                                 "extracted directory, not the .hdf5");
    if (board::has_flag(argc, argv, "--radioml-hdf5") ||
        board::has_flag(argc, argv, "--dataset-hdf5"))
        throw std::runtime_error("RADIOML_HDF5_HOST_EXTRACTION_REQUIRED: route D reads "
                                 "pre-extracted .bin + manifest_a.tsv");
    const std::string out_dir = board::get_opt(argc, argv, "--roundtrip-out-dir", "");
    if (out_dir.empty())
        throw std::runtime_error("route D requires --roundtrip-out-dir=<writable dir> "
                                 "for artifacts (requirement 7)");

    // --- round-trip config ---
    syniq_rt::RoundtripConfig rcfg;
    const int interp_factor =
        static_cast<int>(board::opt_u64(argc, argv, "--interpolation-factor", 20));
    if (interp_factor != syniq_rt::kInterpFactor)
        throw std::runtime_error("route D: --interpolation-factor must be 20 "
                                 "(deterministic polyphase FIR, never linear)");
    rcfg.interpolation_factor = interp_factor;
    rcfg.rms_counts = board::opt_d(argc, argv, "--raw-complex-rms-counts", 16.0);
    const double rec_scale_opt = board::opt_d(argc, argv, "--rec-scale", -1.0);
    rcfg.rec_scale = (rec_scale_opt > 0.0) ? static_cast<float>(rec_scale_opt) : -1.0f;
    rcfg.edge_policy = syniq_rt::parse_edge_policy(
        board::get_opt(argc, argv, "--edge-policy", "zero"));

    const std::vector<syniq_run::RouteAFrame> manifest = syniq_run::load_route_a(bin_dir);
    const std::uint64_t count_req = board::opt_u64(argc, argv, "--count", 240);
    const std::size_t n = std::min<std::size_t>(
        static_cast<std::size_t>(count_req), manifest.size());

    // --- attribution thresholds (documented, measurement-only) ---
    constexpr double kLogitsCloseCosine = 0.999;
    constexpr double kSignificantDistortionNmse = 0.01;
    constexpr double kInconclusiveNmse = 0.1;

    // --- accumulators ---
    std::size_t processed = 0, replay_mismatch = 0, artifacts_failed = 0;
    std::size_t raw24_agree = 0, merged23_agree = 0;
    std::size_t a_correct = 0, d_correct = 0;
    std::map<int, std::size_t> src_total, src_correct23;
    std::map<int, std::map<int, std::size_t>> confusion;       // D confusion
    std::map<std::string, std::size_t> attrib_all;             // aggregate attribution
    struct SnrStat { std::size_t total = 0, a_ok = 0, d_ok = 0; };
    std::map<double, SnrStat> snr_stat;

    // --- file writers (artifacts, requirement 7) ---
    auto write_f32 = [](const std::string& path, const float* p, std::size_t cnt) -> bool {
        std::ofstream f(path, std::ios::binary);
        if (!f) return false;
        f.write(reinterpret_cast<const char*>(p),
                static_cast<std::streamsize>(cnt * sizeof(float)));
        return f.good();
    };
    auto write_complex_f32 = [](const std::string& path,
                                const std::vector<std::complex<double>>& v) -> bool {
        std::ofstream f(path, std::ios::binary);
        if (!f) return false;
        for (const auto& c : v) {
            const float re = static_cast<float>(c.real());
            const float im = static_cast<float>(c.imag());
            f.write(reinterpret_cast<const char*>(&re), sizeof(float));
            f.write(reinterpret_cast<const char*>(&im), sizeof(float));
        }
        return f.good();
    };
    auto cosine24 = [](const std::vector<float>& a, const std::vector<float>& b) -> double {
        double dot = 0.0, na = 0.0, nb = 0.0;
        for (std::size_t k = 0; k < a.size(); ++k) {
            dot += static_cast<double>(a[k]) * b[k];
            na += static_cast<double>(a[k]) * a[k];
            nb += static_cast<double>(b[k]) * b[k];
        }
        return std::sqrt(na * nb) > 0.0 ? dot / std::sqrt(na * nb) : 0.0;
    };
    auto attribute = [&](bool ac, bool dc, bool close, double nmse_c) -> std::string {
        if (nmse_c > kInconclusiveNmse) return "RADIOML_ROUNDTRIP_EDGE_INCONCLUSIVE";
        if (ac && dc) return close ? "PREPROCESS_PRESERVES_RADIOML_DOMAIN"
                                   : "PRESERVED_LABEL_BUT_LOGITS_SHIFTED";
        if (ac && !dc) return (nmse_c > kSignificantDistortionNmse)
                                  ? "PREPROCESS_ROUNDTRIP_MISMATCH"
                                  : "MODEL_INPUT_SENSITIVITY";
        if (!ac && !dc) return "MODEL_FAILS_ON_RADIOML_HELDOUT";
        return "D_IMPROVED_OVER_A";
    };

    // Record the interpolator identity once (requirement 4).
    const auto ident = syniq_rt::interpolation_identity();
    std::printf("ROUNDTRIP_INTERPOLATOR up=%d down=%d taps_total=%zu taps_per_phase=%d "
                "cutoff_hz=%.0f fs_out_hz=%.0f group_delay_out=%.1f dc_gain_total=%.0f "
                "window=%s edge_policy=%s guard=%d rms_counts=%.3f rec_scale=%.3f\n",
                ident.up, ident.down, ident.taps_total, ident.taps_per_phase,
                ident.cutoff_hz, ident.fs_out_hz, ident.group_delay_out,
                ident.dc_gain_total, ident.window,
                syniq_rt::edge_policy_name(rcfg.edge_policy), rcfg.guard,
                rcfg.rms_counts, rcfg.rec_scale);
    std::fflush(stdout);

    const std::string manifest_path = out_dir + "/roundtrip_manifest.tsv";
    std::ofstream mf(manifest_path, std::ios::binary);
    if (!mf)
        throw std::runtime_error("route D: cannot open manifest for writing: " +
                                 manifest_path);
    mf << "index\tsource_index\thdf5_label\tsnr_db\tclass_index\tclass_name\t"
          "original_file\tinterp_file\tquant_file\trecovered_file\traw24_a_file\t"
          "raw24_d_file\toriginal_sha256\n";

    std::vector<float> tensor(chain::kTensorFloats);
    for (std::size_t i = 0; i < n; ++i) {
        if (board::g_stop_requested) break;
        const syniq_run::RouteAFrame& fr = manifest[i];
        syniq_run::load_route_a_tensor(fr, bin_dir, tensor.data());

        char tag[64];
        std::snprintf(tag, sizeof(tag), "%06d", fr.index);
        const std::string base = out_dir + "/";
        const std::string orig_file = std::string("radioml_original_") + tag + ".f32";
        const std::string interp_file = std::string("interpolated_2p56m_") + tag + ".f32";
        const std::string quant_file = std::string("quantized_raw_rx_") + tag + ".ci16";
        const std::string recov_file = std::string("recovered_tensor_") + tag + ".f32";
        const std::string raw24a_file = std::string("raw24_a_") + tag + ".f32";
        const std::string raw24d_file = std::string("raw24_d_") + tag + ".f32";

        // 1. round-trip (pure/deterministic; same tensor A is used below).
        const syniq_rt::RoundtripResult rt =
            syniq_rt::roundtrip_radioml(tensor.data(), rcfg);

        // 2. A and D inference + D replay (requirement 10: bit-identical re-infer).
        const std::vector<float> raw24_a = npu.infer(tensor.data());
        const std::vector<float> raw24_d = npu.infer(rt.recovered_tensor.data());
        bool replay_ok = true;
        {
            const std::vector<float> replay = npu.infer(rt.recovered_tensor.data());
            if (replay.size() != raw24_d.size() ||
                std::memcmp(raw24_d.data(), replay.data(),
                            raw24_d.size() * sizeof(float)) != 0) {
                replay_ok = false;
                ++replay_mismatch;
            }
        }

        // 3. compare A vs D.
        const std::vector<float> merged_a = merge_to_23(raw24_a);
        const std::vector<float> merged_d = merge_to_23(raw24_d);
        const int raw24_a_top = argmax_of(raw24_a);
        const int raw24_d_top = argmax_of(raw24_d);
        const int merged_a_top = argmax_of(merged_a);
        const int merged_d_top = argmax_of(merged_d);
        const int truth = rml23::kSourceToDeployed[fr.class_index];
        const bool ac = (merged_a_top == truth);
        const bool dc = (merged_d_top == truth);

        double max_abs = 0.0, sum_abs = 0.0;
        for (std::size_t k = 0; k < raw24_a.size(); ++k) {
            const double diff = std::fabs(static_cast<double>(raw24_a[k]) - raw24_d[k]);
            max_abs = std::max(max_abs, diff);
            sum_abs += diff;
        }
        const double mean_abs = sum_abs / static_cast<double>(raw24_a.size());
        const double cosine = cosine24(raw24_a, raw24_d);
        const bool close = (cosine >= kLogitsCloseCosine);
        const std::string rule = attribute(ac, dc, close, rt.metrics.nmse_center);

        // 4. save artifacts (requirement 7).
        bool ok = true;
        ok = write_f32(base + orig_file, tensor.data(), chain::kTensorFloats) && ok;
        ok = write_complex_f32(base + interp_file, rt.interpolated_complex) && ok;
        ok = board::save_raw_iq(base + quant_file, rt.quantized_iq) && ok;
        ok = write_f32(base + recov_file, rt.recovered_tensor.data(),
                       chain::kTensorFloats) && ok;
        ok = write_f32(base + raw24a_file, raw24_a.data(), raw24_a.size()) && ok;
        ok = write_f32(base + raw24d_file, raw24_d.data(), raw24_d.size()) && ok;
        if (!ok) ++artifacts_failed;

        const std::string orig_sha = sdr::Sha256::hex(tensor.data(), chain::kTensorBytes);

        // 5. per-frame one-to-one A-vs-D table line.
        const syniq_rt::RoundtripMetrics& m = rt.metrics;
        std::printf("ROUNDTRIP frame=%d src=%s src_class=%d snr_db=%.1f "
                    "delay=%d gain_db=%.4f phase_deg=%.3f "
                    "nmse_full=%.3e nmse_center=%.3e evm_pct=%.4f corr=%.6f "
                    "rms_orig=%.4f rms_recov=%.4f dc_orig=%.4f dc_recov=%.4f "
                    "papr_orig=%.2f papr_recov=%.2f corr_swap=%.6f corr_conj=%.6f "
                    "edge_policy=%s center=%d..%d "
                    "raw24_a_top1=%d raw24_d_top1=%d merged_a_top1=%d merged_d_top1=%d "
                    "label=%s a_correct=%d d_correct=%d "
                    "logits_max_abs=%.4f logits_mean_abs=%.4f logits_cosine=%.6f "
                    "merged_consistent=%d replay_ok=%d attribution=%s\n",
                    fr.index, fr.class_name.c_str(), fr.class_index, fr.snr_db,
                    m.delay_offset, m.gain_db, m.phase_deg,
                    m.nmse_full, m.nmse_center, m.evm_center_pct, m.corr_center,
                    m.rms_orig, m.rms_recov, m.dc_orig, m.dc_recov,
                    m.papr_orig_db, m.papr_recov_db, m.corr_swap, m.corr_conj,
                    rt.edge_policy.c_str(), m.center_lo, m.center_hi,
                    raw24_a_top, raw24_d_top, merged_a_top, merged_d_top,
                    rml23::kLabelOrder23[truth], ac ? 1 : 0, dc ? 1 : 0,
                    max_abs, mean_abs, cosine,
                    (merged_a_top == merged_d_top) ? 1 : 0, replay_ok ? 1 : 0,
                    rule.c_str());
        std::fflush(stdout);

        // manifest row (SHAs of every artifact are computed by the analyzer from
        // these files; the original tensor SHA is recorded here for A/D keying).
        mf << fr.index << "\t" << fr.source_index << "\t" << fr.hdf5_label << "\t"
           << fr.snr_db << "\t" << fr.class_index << "\t" << fr.class_name << "\t"
           << orig_file << "\t" << interp_file << "\t" << quant_file << "\t"
           << recov_file << "\t" << raw24a_file << "\t" << raw24d_file << "\t"
           << orig_sha << "\n";

        // 6. accumulate.
        ++processed;
        if (raw24_a_top == raw24_d_top) ++raw24_agree;
        if (merged_a_top == merged_d_top) ++merged23_agree;
        if (ac) ++a_correct;
        if (dc) ++d_correct;
        ++src_total[fr.class_index];
        if (dc) ++src_correct23[fr.class_index];
        ++confusion[fr.class_index][merged_d_top];
        ++attrib_all[rule];
        SnrStat& ss = snr_stat[fr.snr_db];
        ss.total += 1; if (ac) ss.a_ok += 1; if (dc) ss.d_ok += 1;
    }
    mf.close();

    // --- D confusion matrix (requirement 9) ---
    for (const auto& kv : confusion) {
        std::printf("ROUNDTRIP_D_CONFUSION src_class=%d total=%zu correct23=%zu",
                    kv.first, src_total[kv.first], src_correct23[kv.first]);
        for (const auto& p : kv.second)
            std::printf(" pred23_%d=%zu", p.first, p.second);
        std::printf("\n");
    }
    // --- per-SNR stats (requirement 9) ---
    for (const auto& kv : snr_stat)
        std::printf("ROUNDTRIP_SNR snr_db=%.1f total=%zu a_correct=%zu d_correct=%zu\n",
                    kv.first, kv.second.total, kv.second.a_ok, kv.second.d_ok);
    // --- attribution summary ---
    for (const auto& kv : attrib_all)
        std::printf("ROUNDTRIP_ATTRIBUTION rule=%s count=%zu\n",
                    kv.first.c_str(), kv.second);
    std::fflush(stdout);

    const m22::ResourceSample last_res = m22::read_resources();
    const m22::ResourceSample peak_res = peak_of(first_res, last_res);
    finish_m22_runtime("synthetic-iq", model_sha, npu, timing, first_res, last_res,
                       peak_res, mcfg);

    const bool discipline = npu.discipline_ok() && npu.lifecycle().discipline_ok();
    const bool mechanics_ok = (processed > 0) && (replay_mismatch == 0) &&
                              (artifacts_failed == 0);
    std::string detail = " phase=synthetic-iq route=D source=radioml "
                         "inject_point=raw-rx-reconstructed "
                         "samples=" + std::to_string(processed) +
                         " raw24_agree=" + std::to_string(raw24_agree) +
                         " merged23_agree=" + std::to_string(merged23_agree) +
                         " a_correct=" + std::to_string(a_correct) +
                         " d_correct=" + std::to_string(d_correct) +
                         " replay_mismatch=" + std::to_string(replay_mismatch) +
                         " artifacts_failed=" + std::to_string(artifacts_failed) +
                         " npu_discipline=" + std::string(discipline ? "OK" : "VIOLATION");
    if (processed == 0) detail += " (no_frames)";
    if (replay_mismatch != 0) detail += " (replay_bit_mismatch)";
    if (artifacts_failed != 0) detail += " (artifact_write_failure)";
    if (!discipline) detail += " (npu_discipline_violation)";
    detail += " measurement=model_confusion_no_accuracy_threshold attribution=measurement_only";

    const bool pass = mechanics_ok && discipline;
    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase synthetic-iq: four-route digital injection fault attribution (Stage G).
//
//   A  --source=radioml    --inject-point=model-input  --radioml-bin-dir DIR
//   B  --source=generated  --inject-point=model-input  --modulation .. --norm ..
//   C  --source=generated  --inject-point=raw-rx       --modulation .. --norm ..
//
// NO IIO / SDR device is ever opened (no pluto::Device is constructed on this
// path): the inputs are extracted RadioML .bin files (A) or deterministically
// synthesized waveforms (B/C).  NO TX is started.
//
// A/B/C are reported as MEASUREMENTS of the model's actual confusion -- there is
// NO preset accuracy PASS threshold.  The gate PASSes only when the injection
// MECHANICS are sound: every frame injected and valid, route C's final tensor
// replays through the model-input infer path bit-identically (NPU determinism +
// boundary identity), and the NPU bring-up/reset discipline holds.
// ---------------------------------------------------------------------------
int run_synthetic_iq_phase(chain::NpuClassifier24& npu, const cat::Contract& contract,
                           ui::StdoutSink& out, ui::UnixSocketSink& sock,
                           m22::StageTiming& timing, int argc, char** argv) {
    const std::string source = board::get_opt(argc, argv, "--source", "generated");
    const std::string inject = board::get_opt(argc, argv, "--inject-point", "model-input");
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const M22Config mcfg = read_m22_config(argc, argv);
    const m22::ResourceSample first_res = m22::read_resources();

    std::string route;
    if (source == "radioml") {
        if (inject == "model-input") route = "A";
        else if (inject == "raw-rx-reconstructed") route = "D";
        else throw std::runtime_error(
                 "unknown --inject-point: " + inject +
                 " for radioml (use model-input|raw-rx-reconstructed)");
    } else if (source == "generated") {
        if (inject == "model-input") route = "B";
        else if (inject == "raw-rx") route = "C";
        else throw std::runtime_error(
                 "unknown --inject-point: " + inject + " (use model-input|raw-rx)");
    } else {
        throw std::runtime_error("unknown --source: " + source +
                                 " (use radioml|generated)");
    }

    // Route D (RadioML round-trip) has its own full processing: production
    // PreprocessChain round-trip + A/D one-to-one attribution.  Dispatch before
    // the A/B/C measurement machinery (it shares none of its accumulators).
    if (route == "D")
        return run_route_d_roundtrip(npu, contract, out, sock, timing, argc, argv);

    // Modulation selection for the generated routes (B/C).
    auto select_mods = [&]() -> std::vector<syniq::Modulation> {
        const std::string mod_opt = board::get_opt(argc, argv, "--modulation", "all");
        if (mod_opt == "all")
            return {syniq::Modulation::BPSK, syniq::Modulation::QPSK,
                    syniq::Modulation::ASK4, syniq::Modulation::QAM16};
        return {syniq::parse_modulation(mod_opt)};
    };

    // Measurement accumulators.
    std::size_t processed = 0, valid = 0;
    std::size_t raw24_correct = 0, merged23_correct = 0;
    std::size_t replay_checked = 0, replay_mismatch = 0;
    std::map<int, std::size_t> src_total, src_correct23;
    std::map<int, std::map<int, std::size_t>> confusion;  // src class -> pred23 -> count
    std::uint64_t frame_seq = 1;

    // One tensor through the model-input infer path -> measure -> emit.
    auto classify_and_record = [&](const std::string& src_label, int src_class,
                                   double snr_db, const float* tensor,
                                   bool require_replay,
                                   std::vector<std::uint8_t>* tensor_bytes = nullptr,
                                   std::vector<std::uint8_t>* logits_bytes = nullptr)
                                   -> bool {
        m22::StageTiming::Timer frame_t(timing, m22::StageId::FrameTotal);
        const auto t0 = Clock::now();
        const std::vector<float> raw24 = npu.infer(tensor);
        const auto t1 = Clock::now();
        timing.record(m22::StageId::NpuInfer, static_cast<double>(
            std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count()));

        bool replay_ok = true;
        if (require_replay) {
            // Replay the SAME tensor through the model-input infer path and require
            // bit-identical raw24: proves the NPU is deterministic on a fixed input
            // and that route C's final [2,1024] tensor is the genuine model input
            // (no hidden per-route transform at the model boundary).
            const std::vector<float> replay = npu.infer(tensor);
            ++replay_checked;
            if (replay.size() != raw24.size() ||
                std::memcmp(raw24.data(), replay.data(),
                            raw24.size() * sizeof(float)) != 0) {
                replay_ok = false;
                ++replay_mismatch;
            }
        }

        const std::vector<float> merged23 = merge_to_23(raw24);
        const int raw24_top = argmax_of(raw24);
        const int merged_top = argmax_of(merged23);
        float top2 = -std::numeric_limits<float>::infinity();
        for (int i = 0; i < static_cast<int>(merged23.size()); ++i)
            if (i != merged_top && merged23[i] > top2) top2 = merged23[i];
        const float margin = merged23[static_cast<std::size_t>(merged_top)] - top2;

        rf::ResultFrame r;
        r.frame_id = frame_seq;
        r.timestamp_us = frame_seq * 8000ULL;
        r.source = "synthetic_iq_" + route;
        r.mock = false;
        chain::fill_result_rml23(r, raw24, merged23, contract, model_sha, snr_db);
        r.classify_us = static_cast<double>(
            std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count());
        r.e2e_us = r.classify_us;
        emit_frame(out, sock, r);
        ++frame_seq;

        ++processed;
        if (result_frame_valid(r)) ++valid;

        const int deployed_truth = rml23::kSourceToDeployed[src_class];
        const bool r24 = (raw24_top == src_class);
        const bool m23 = (merged_top == deployed_truth);
        if (r24) ++raw24_correct;
        if (m23) ++merged23_correct;
        ++src_total[src_class];
        if (m23) ++src_correct23[src_class];
        ++confusion[src_class][merged_top];

        // Stage H-E (Route E) Route-C persistence collectors: append the EXACT
        // bytes pushed into the model-input infer path (the [2,1024] fp32 tensor)
        // and the raw 24-dim logits, so the manifest can record their concatenated
        // SHA-256 identity.  Only touched when the caller passes non-null vectors.
        if (tensor_bytes)
            tensor_bytes->insert(tensor_bytes->end(),
                                 reinterpret_cast<const std::uint8_t*>(tensor),
                                 reinterpret_cast<const std::uint8_t*>(tensor) +
                                     chain::kTensorBytes);
        if (logits_bytes)
            logits_bytes->insert(logits_bytes->end(),
                                 reinterpret_cast<const std::uint8_t*>(raw24.data()),
                                 reinterpret_cast<const std::uint8_t*>(raw24.data()) +
                                     raw24.size() * sizeof(float));

        char snr_buf[32];
        if (std::isnan(snr_db)) std::snprintf(snr_buf, sizeof(snr_buf), "nan");
        else std::snprintf(snr_buf, sizeof(snr_buf), "%.1f", snr_db);
        std::printf("SYNTHETIC_IQ route=%s frame=%llu src=%s src_class=%d "
                    "snr_db=%s raw24_top1=%d merged23_top1=%d label=%s margin=%.4f "
                    "raw24_match=%d merged23_match=%d%s\n",
                    route.c_str(), static_cast<unsigned long long>(r.frame_id),
                    src_label.c_str(), src_class, snr_buf, raw24_top, merged_top,
                    rml23::kLabelOrder23[merged_top], margin,
                    r24 ? 1 : 0, m23 ? 1 : 0,
                    require_replay ? (replay_ok ? " replay_ok=1" : " replay_ok=0") : "");
        std::fflush(stdout);

        return m23;
    };

    const double nan = std::numeric_limits<double>::quiet_NaN();

    if (route == "A") {
        const std::string bin_dir = board::get_opt(argc, argv, "--radioml-bin-dir", "");
        if (bin_dir.empty())
            throw std::runtime_error("route A requires --radioml-bin-dir=<extracted dir>");
        if (bin_dir.size() >= 5 &&
            bin_dir.compare(bin_dir.size() - 5, 5, ".hdf5") == 0)
            throw std::runtime_error("RADIOML_HDF5_HOST_EXTRACTION_REQUIRED: pass the "
                                     "extracted directory, not the .hdf5");
        if (board::has_flag(argc, argv, "--radioml-hdf5") ||
            board::has_flag(argc, argv, "--dataset-hdf5"))
            throw std::runtime_error("RADIOML_HDF5_HOST_EXTRACTION_REQUIRED: route A reads "
                                     "pre-extracted .bin + manifest_a.tsv; run "
                                     "scripts/extract_radioml_stage_g.py on the host");

        const std::vector<syniq_run::RouteAFrame> manifest = syniq_run::load_route_a(bin_dir);
        const std::uint64_t count_req = board::opt_u64(argc, argv, "--count", 240);
        const std::size_t n = std::min<std::size_t>(
            static_cast<std::size_t>(count_req), manifest.size());
        std::vector<float> tensor(chain::kTensorFloats);
        for (std::size_t i = 0; i < n; ++i) {
            if (board::g_stop_requested) break;
            const syniq_run::RouteAFrame& f = manifest[i];
            syniq_run::load_route_a_tensor(f, bin_dir, tensor.data());
            classify_and_record(f.class_name, f.class_index, f.snr_db,
                                tensor.data(), /*require_replay=*/false);
        }
    } else if (route == "B") {
        const std::string norm = board::get_opt(argc, argv, "--norm", "none");
        const std::uint64_t seed = board::opt_u64(argc, argv, "--seed", 0x39e5ULL);
        const std::uint64_t count = board::opt_u64(argc, argv, "--count", 240);
        if (count == 0) throw std::runtime_error("route B: --count must be >= 1");
        for (const syniq::Modulation mod : select_mods()) {
            syniq_run::GeneratedConfig cfg;
            cfg.mod = mod; cfg.sps = 8; cfg.seed = seed; cfg.norm = norm;
            const std::vector<std::vector<float>> tensors =
                syniq_run::generate_model_input_tensors(cfg, static_cast<int>(count));
            const int src = syniq_run::source_class_index(mod);
            for (const auto& t : tensors) {
                if (board::g_stop_requested) break;
                classify_and_record(syniq::modulation_name(mod), src, nan,
                                    t.data(), /*require_replay=*/false);
            }
        }
    } else {  // route == "C"
        const std::string norm = board::get_opt(argc, argv, "--norm", "none");
        const std::uint64_t seed = board::opt_u64(argc, argv, "--seed", 0x39e5ULL);
        const double rms_counts = board::opt_d(argc, argv, "--raw-complex-rms-counts", 16.0);
        const std::uint64_t count = board::opt_u64(argc, argv, "--count", 240);
        if (count == 0) throw std::runtime_error("route C: --count must be >= 1");

        // Stage H-E (Route E) Route-C persistence: default OFF (hard requirement 2,
        // no effect on the historical Route C output).  When --raw-iq-out-dir is
        // given, save the EXACT post-quantization int16 block that was pushed into
        // the production PreprocessChain (I0,Q0,I1,Q1,... interleaved little-endian)
        // with a 3-way SHA (in-memory == on-disk == re-read), plus a 24-column
        // iq_loopback_manifest.tsv sidecar (hard requirements 1 + 3).
        const std::string raw_iq_out_dir =
            board::get_opt(argc, argv, "--raw-iq-out-dir", "");
        std::vector<std::string> manifest_rows;
        for (const syniq::Modulation mod : select_mods()) {
            syniq_run::GeneratedConfig cfg;
            cfg.mod = mod; cfg.sps = 160; cfg.seed = seed; cfg.norm = norm;
            cfg.rms_counts = rms_counts;
            const syniq_run::RawRxOutput outp =
                syniq_run::generate_raw_rx_tensors(cfg, static_cast<int>(count));
            std::printf("SYNTHETIC_IQ route=C modulation=%s quant_rms=%.3f "
                        "quant_peak=%.3f clip=%zu\n",
                        syniq::modulation_name(mod), outp.quant.rms_counts,
                        outp.quant.peak_counts, outp.quant.clip);
            std::fflush(stdout);

            const int src = syniq_run::source_class_index(mod);
            const std::string mod_name = syniq::modulation_name(mod);

            // Per-mod identity collectors (tensor bytes + raw 24-dim logits) and the
            // frozen-reference counts.  Only populated when persistence is enabled.
            std::vector<std::uint8_t> tensor_bytes, logits_bytes;
            std::vector<std::uint8_t>* tb = raw_iq_out_dir.empty() ? nullptr : &tensor_bytes;
            std::vector<std::uint8_t>* lb = raw_iq_out_dir.empty() ? nullptr : &logits_bytes;
            std::uint64_t frozen_frames = 0, frozen_deployed_correct = 0;
            for (const auto& t : outp.tensors) {
                if (board::g_stop_requested) break;
                const bool m23 = classify_and_record(mod_name, src, nan,
                                                     t.data(), /*require_replay=*/true,
                                                     tb, lb);
                ++frozen_frames;
                if (m23) ++frozen_deployed_correct;
            }

            if (!raw_iq_out_dir.empty()) {
                // The pushed-prefix bytes, verbatim (never re-quantized, never
                // inferred back from the tensors).
                const std::uint64_t pushed_complex = outp.pushed_complex;
                const std::string file_name = "generated_2p56m_" + mod_name + ".ci16";
                const std::string path = raw_iq_out_dir + "/" + file_name;
                const std::size_t n_int16 = static_cast<std::size_t>(pushed_complex) * 2;

                std::ofstream f(path, std::ios::binary);
                if (!f)
                    throw std::runtime_error("route C: cannot open " + path +
                                             " (create --raw-iq-out-dir first)");
                f.write(reinterpret_cast<const char*>(outp.iq.data()),
                        static_cast<std::streamsize>(n_int16 * sizeof(std::int16_t)));
                f.close();
                if (!f.good())
                    throw std::runtime_error("route C: short write " + path);

                // 3-way SHA (in-memory bytes == file on disk == re-read file).
                const std::string mem_sha = sdr::Sha256::hex(
                    outp.iq.data(), n_int16 * sizeof(std::int16_t));
                bool fok = false;
                const std::string file_sha = sdr::sha256_hex_file(path, &fok);
                std::ifstream re(path, std::ios::binary);
                const std::vector<char> re_bytes((std::istreambuf_iterator<char>(re)),
                                                 std::istreambuf_iterator<char>());
                const std::string reread_sha = sdr::Sha256::hex(
                    re_bytes.data(), re_bytes.size());
                if (!fok || file_sha != mem_sha || reread_sha != mem_sha)
                    throw std::runtime_error(
                        "route C: 3-way SHA mismatch for " + file_name +
                        " (mem " + mem_sha + ", file " + file_sha +
                        ", reread " + reread_sha + ")");

                // Saved-prefix clip count / ratio (over the exact persisted bytes).
                std::uint64_t clip_count = 0;
                for (std::size_t k = 0; k < n_int16; ++k) {
                    const std::int16_t v = outp.iq[k];
                    if (v == 32767 || v == -32768) ++clip_count;
                }
                const double clip_ratio =
                    (n_int16 > 0)
                        ? static_cast<double>(clip_count) /
                              static_cast<double>(n_int16)
                        : 0.0;

                const std::string tensor_sha = sdr::Sha256::hex(
                    tensor_bytes.data(), tensor_bytes.size());
                const std::string logits_sha = sdr::Sha256::hex(
                    logits_bytes.data(), logits_bytes.size());

                // 24-column sidecar row (column order == iq_digital_loopback.hpp's
                // load_generated_sidecar).
                std::ostringstream row;
                row << file_name << '\t'
                    << "ci16le" << '\t'
                    << "interleaved_iq" << '\t'
                    << cfg.fs_in << '\t'                                    // sr_req
                    << cfg.fs_in << '\t'                                    // sr_act (software nominal)
                    << pushed_complex << '\t'                               // complex
                    << (pushed_complex * 4) << '\t'                         // byte
                    << cfg.seed << '\t'
                    << src << '\t'                                          // source class
                    << mod_name << '\t'
                    << (cfg.fs_in / static_cast<std::uint32_t>(cfg.sps)) << '\t'  // symrate
                    << cfg.beta << '\t'
                    << cfg.span << '\t'
                    << cfg.sps << '\t'
                    << cfg.norm << '\t'
                    << outp.quant.rms_counts << '\t'
                    << outp.quant_scale << '\t'
                    << clip_count << '\t'
                    << clip_ratio << '\t'
                    << mem_sha << '\t'
                    << tensor_sha << '\t'
                    << logits_sha << '\t'
                    << frozen_frames << '\t'
                    << frozen_deployed_correct;
                manifest_rows.push_back(row.str());

                std::printf("SYNTHETIC_IQ route=C persist file=%s complex=%llu "
                            "bytes=%llu sha256=%s tensor_sha256=%s logits_sha256=%s "
                            "frozen_frames=%llu frozen_correct=%llu\n",
                            file_name.c_str(),
                            static_cast<unsigned long long>(pushed_complex),
                            static_cast<unsigned long long>(pushed_complex * 4),
                            mem_sha.c_str(), tensor_sha.c_str(), logits_sha.c_str(),
                            static_cast<unsigned long long>(frozen_frames),
                            static_cast<unsigned long long>(frozen_deployed_correct));
                std::fflush(stdout);
            }
        }

        if (!raw_iq_out_dir.empty()) {
            const std::string tsv_path = raw_iq_out_dir + "/iq_loopback_manifest.tsv";
            std::ofstream t(tsv_path);
            if (!t)
                throw std::runtime_error("route C: cannot open " + tsv_path);
            t << "# file\tdtype\tlayout\tsr_req\tsr_act\tcomplex\tbyte\tseed\tsource"
                 "\tmod\tsymrate\tbeta\tspan\tsps\tnorm\trms\tquant_scale\tclip"
                 "\tclip_ratio\tsha\ttensor_sha\tlogits_sha\tfrozen_frames"
                 "\tfrozen_deployed_correct\n";
            for (const auto& row : manifest_rows)
                t << row << "\n";
            t.close();
            if (!t.good())
                throw std::runtime_error("route C: short write " + tsv_path);
        }
    }

    for (const auto& kv : confusion) {
        std::printf("SYNTHETIC_IQ_CONFUSION src_class=%d total=%zu correct23=%zu",
                    kv.first, src_total[kv.first], src_correct23[kv.first]);
        for (const auto& p : kv.second)
            std::printf(" pred23_%d=%zu", p.first, p.second);
        std::printf("\n");
        std::fflush(stdout);
    }

    const m22::ResourceSample last_res = m22::read_resources();
    const m22::ResourceSample peak_res = peak_of(first_res, last_res);
    finish_m22_runtime("synthetic-iq", model_sha, npu, timing, first_res, last_res,
                       peak_res, mcfg);

    const bool discipline = npu.discipline_ok() && npu.lifecycle().discipline_ok();
    const bool mechanics_ok = (processed > 0) && (valid == processed) &&
                              (replay_mismatch == 0);
    std::string detail = " phase=synthetic-iq route=" + route +
                         " source=" + source + " inject_point=" + inject +
                         " samples=" + std::to_string(processed) +
                         " valid=" + std::to_string(valid) +
                         " raw24_correct=" + std::to_string(raw24_correct) +
                         " merged23_correct=" + std::to_string(merged23_correct) +
                         " replay_checked=" + std::to_string(replay_checked) +
                         " replay_mismatch=" + std::to_string(replay_mismatch) +
                         " npu_discipline=" + std::string(discipline ? "OK" : "VIOLATION");
    if (processed == 0) detail += " (no_frames)";
    if (valid != processed) detail += " (invalid_frames)";
    if (replay_mismatch != 0) detail += " (replay_bit_mismatch)";
    if (!discipline) detail += " (npu_discipline_violation)";
    detail += " measurement=model_confusion_no_accuracy_threshold";

    const bool pass = mechanics_ok && discipline;
    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase iq-digital-loopback: Stage H-E / Route E -- same-device modulated-IQ
// digital loopback over the FROZEN Stage G int16 artifacts (Route C
// generated-2p56m and Route D radioml-reconstructed-2p56m).  Never re-generates
// a waveform; the runner fails closed with STAGE_G_FROZEN_IQ_REQUIRED on a
// missing file.  Infrastructure / fidelity / classification are three separate
// verdicts (classification errors never fail infrastructure and vice versa).
// ---------------------------------------------------------------------------
int run_iq_digital_loopback(chain::NpuClassifier24& npu,
                            const cat::Contract& /*contract*/,
                            ui::StdoutSink& out, ui::UnixSocketSink& sock,
                            m22::StageTiming& timing, int argc, char** argv) {
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const M22Config mcfg = read_m22_config(argc, argv);

    const auto on_frame = [&](const rf::ResultFrame& r) {
        emit_frame(out, sock, r);
    };

    const iqdloop_run::RunReport rep =
        iqdloop_run::run_iq_digital_loopback(npu, timing, argc, argv, on_frame);

    // Device-not-found is a distinct exit code (2): the gate did not run, as
    // opposed to a run that completed and failed (1).
    if (rep.device_not_found) {
        board::emit("gate9_full_chain_rml23", false,
                    "phase=iq-digital-loopback error=device_not_found " + rep.error);
        return 2;
    }

    if (!rep.error.empty()) {
        board::emit("gate9_full_chain_rml23", false, rep.detail);
        return 1;
    }

    // fix7 Task A: fold the M22 verdict into the total gate.  An M22 FAIL (RSS/FD
    // growth, discipline, spike, reopen/apply) must force GATE=FAIL, never PASS.
    const bool m22_ok = finish_m22_runtime("iq-digital-loopback", model_sha, npu,
                                           timing, rep.first_res, rep.last_res,
                                           rep.peak_res, mcfg);

    std::string detail = rep.detail;
    if (!m22_ok) {
        if (!detail.empty() && detail.back() != ' ') detail += ' ';
        detail += "(m22_failed)";
    }
    const bool pass =
        board::final_gate_pass(rep.functional_pass && m22_ok, rep.restore_ok, detail);
    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase iq-rf-loopback: Stage H-F / Route F -- ADALM-Pluto PHYSICAL TX->RX
// self loopback over the FROZEN Stage G int16 artifacts (loopback=0 through a
// 50-ohm SMA coax, --rf-path=direct-cable, TX attenuation -40 dB).  The
// amplitude/phase is corrected with ONE global fixed gain from an independent
// calibration subset (--rf-calib-count=N); a per-file best-fit gain is never fed
// to the classifier.  Infrastructure / fidelity / classification are three
// separate verdicts.  RF_PATH_NOT_PROVEN is never promoted by a host run.
// ---------------------------------------------------------------------------
int run_iq_rf_loopback(chain::NpuClassifier24& npu,
                       const cat::Contract& /*contract*/,
                       ui::StdoutSink& out, ui::UnixSocketSink& sock,
                       m22::StageTiming& timing, int argc, char** argv) {
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const M22Config mcfg = read_m22_config(argc, argv);

    const auto on_frame = [&](const rf::ResultFrame& r) {
        emit_frame(out, sock, r);
    };

    const iqrfloop_run::RfRunReport rep =
        iqrfloop_run::run_iq_rf_loopback(npu, timing, argc, argv, on_frame);

    // Device-not-found is a distinct exit code (2): the gate did not run, as
    // opposed to a run that completed and failed (1).
    if (rep.device_not_found) {
        board::emit("gate9_full_chain_rml23", false,
                    "phase=iq-rf-loopback error=device_not_found " + rep.error);
        return 2;
    }

    if (!rep.error.empty()) {
        board::emit("gate9_full_chain_rml23", false, rep.detail);
        return 1;
    }

    // fix7 Task A: fold the M22 verdict into the total gate.  An M22 FAIL (RSS/FD
    // growth, discipline, spike, reopen/apply) must force GATE=FAIL, never PASS.
    const bool m22_ok = finish_m22_runtime("iq-rf-loopback", model_sha, npu,
                                           timing, rep.first_res, rep.last_res,
                                           rep.peak_res, mcfg);

    std::string detail = rep.detail;
    if (!m22_ok) {
        if (!detail.empty() && detail.back() != ' ') detail += ' ';
        detail += "(m22_failed)";
    }
    const bool pass =
        board::final_gate_pass(rep.functional_pass && m22_ok, rep.restore_ok, detail);
    board::emit("gate9_full_chain_rml23", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase iq-digital-loopback-sweep: Stage H-E / Route E fix3 -- locate and fix the
// ~20 dB digital-loopback amplitude loss.  Sweeps tone/ramp/PRBS at logical RMS
// 8..512 counts through the same-device digital loopback, measures the RAW-vs-
// LOGICAL gain pair at every level, and classifies the root cause:
//   * FORMAT_MISALIGNMENT   -> raw preserved, logical lost: fix the RX convert
//                              bit position (--rx-format-shift=N).
//   * FIXED_ATTENUATION     -> raw+logical lost equally: fix with an explicit
//                              --digital-loopback-tx-scale (test fixture only).
//   * LIBIIO_CONVERT_*      -> convert_inverse diverges from the host mirror.
//   * UNITY                 -> no loss at these levels (loss is elsewhere).
// It is a DIAGNOSTIC instrument: it never runs the NPU, never runs the 24-class
// classifier, and never changes DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN.
// ---------------------------------------------------------------------------
int run_iq_digital_loopback_sweep(chain::NpuClassifier24& /*npu*/,
                                  const cat::Contract& /*contract*/,
                                  ui::StdoutSink& /*out*/,
                                  ui::UnixSocketSink& /*sock*/,
                                  m22::StageTiming& timing, int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double rx_gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const double tx_atten_db = board::opt_d(argc, argv, "--tx-atten",
                                            pluto::kSafeTxAttenDb);
    const std::string kinds_str = board::get_opt(argc, argv, "--sweep-kinds", "");
    const std::string levels_str = board::get_opt(argc, argv, "--sweep-levels", "");
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", 1024));
    const std::size_t capture_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--capture-complex", 4096));
    const std::string frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    const std::string input_kind = board::get_opt(argc, argv, "--input-kind", "");

    // Optional comma-separated override lists (empty -> the full default grid).
    const auto split_comma = [](const std::string& s) {
        std::vector<std::string> out;
        std::size_t start = 0;
        while (start <= s.size()) {
            const std::size_t pos = s.find(',', start);
            const std::string tok = s.substr(
                start, pos == std::string::npos ? std::string::npos : pos - start);
            if (!tok.empty()) out.push_back(tok);
            if (pos == std::string::npos) break;
            start = pos + 1;
        }
        return out;
    };

    iqdloop_sweep::SweepConfig cfg;
    cfg.center_hz = center_hz;
    cfg.rx_gain_db = rx_gain_db;
    cfg.tx_atten_db = tx_atten_db;
    cfg.fs = iqdloop::kFrozenFsIn;
    cfg.delay_margin = delay_margin;
    cfg.capture_complex = capture_complex;
    if (!kinds_str.empty()) cfg.kinds = split_comma(kinds_str);
    if (!levels_str.empty()) {
        for (const std::string& t : split_comma(levels_str))
            cfg.levels.push_back(std::atof(t.c_str()));
    }

    // Optional frozen waveform (RMS/peak) for the req 6/7 auto-selected scale.
    // The first frozen file's waveform is loaded once, purely to size the scale.
    double frozen_rms = 0.0, frozen_peak = 0.0;
    bool have_frozen = false;
    if (!frozen_dir.empty()) {
        if (input_kind.empty())
            throw std::runtime_error("sweep: --frozen-dir requires --input-kind");
        const std::vector<iqdloop::FrozenIq> frozen =
            iqdloop::load_frozen_iq(frozen_dir, input_kind);
        if (!frozen.empty()) {
            const std::vector<std::int16_t> w =
                iqdloop::load_ci16(frozen[0].path, frozen[0].complex_count);
            iqdloop_sweep::waveform_stats(w, frozen_rms, frozen_peak);
            have_frozen = true;
        }
    }

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate9_full_chain_rml23", false,
                    "phase=iq-digital-loopback-sweep error=device_not_found " +
                    std::string(e.what()));
        return 2;
    }

    std::unique_ptr<pluto::DeviceStateGuard> guard;
    bool restore_ok = false;
    std::string detail;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // Force the frozen 2.56 MSPS rate (fail-closed, same rule as the runner).
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        const long long rx_rate = dev->get_rx_sample_rate();
        const long long tx_rate = dev->get_tx_sample_rate();
        if (std::llabs(rx_rate - requested) > 5 ||
            std::llabs(tx_rate - requested) > 5)
            throw std::runtime_error(
                "sweep: sample rate mismatch rx=" + std::to_string(rx_rate) +
                " tx=" + std::to_string(tx_rate) +
                " (abs(actual-2560000) must be <= 5 Hz)");

        const iqdloop_sweep::SweepReport rep =
            iqdloop_sweep::sweep_all_levels(*dev, cfg, frozen_rms, frozen_peak,
                                            have_frozen);

        // ---- evidence (req 1/3/4/5/6/7) ----
        std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_FORMAT dir=tx %s roundtrip_identity=%d\n",
                    pluto::describe_data_format(rep.tx_fmt).c_str(),
                    rep.tx_roundtrip_identity ? 1 : 0);
        std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_FORMAT dir=rx %s roundtrip_identity=%d\n",
                    pluto::describe_data_format(rep.rx_fmt).c_str(),
                    rep.rx_roundtrip_identity ? 1 : 0);
        const iqdloop_sweep::SignCheck sc = iqdloop_sweep::verify_sign_extension();
        std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_SIGNCHECK fully_defined_ok=%d "
                    "sign_extend_ok=%d shift4_ok=%d ok=%d\n",
                    sc.fully_defined_ok ? 1 : 0, sc.sign_extend_ok ? 1 : 0,
                    sc.shift4_ok ? 1 : 0, sc.ok ? 1 : 0);
        std::fflush(stdout);

        for (const auto& L : rep.levels) {
            std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_LEVEL kind=%s target_rms=%.1f "
                        "tx_count_rms=%.3f rx_count_rms=%.3f count_gain_db=%.3f "
                        "tx_normalized_rms=%.6f rx_normalized_rms=%.6f "
                        "normalized_gain_db=%.3f gain_db=%.3f corr=%.6f tx_clip=%llu "
                        "rx_clip=%llu rx_raw_clip=%llu rx_libiio_diverged=%d "
                        "capture_ok=%d\n",
                        L.kind.c_str(), L.target_rms, L.tx_count_rms, L.rx_count_rms,
                        L.count_gain_db, L.tx_normalized_rms, L.rx_normalized_rms,
                        L.normalized_gain_db, L.gain_db, L.corr,
                        static_cast<unsigned long long>(L.tx_clip),
                        static_cast<unsigned long long>(L.rx_clip),
                        static_cast<unsigned long long>(L.rx_raw_clip),
                        L.rx_libiio_diverged ? 1 : 0, L.capture_ok ? 1 : 0);

            std::string scan;
            char eb[160];
            for (const auto& e : L.shift_scan) {
                std::snprintf(eb, sizeof(eb),
                              "shift=%d count_gain_db=%.3f normalized_gain_db=%.3f "
                              "logical_gain_db=%.3f corr=%.6f clip_rate=%.6f",
                              e.shift, e.count_gain_db, e.normalized_gain_db,
                              e.logical_gain_db, e.corr, e.clip_rate);
                if (!scan.empty()) scan += " ";
                scan += eb;
            }
            std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_SHIFT_SCAN kind=%s "
                        "target_rms=%.1f %s\n",
                        L.kind.c_str(), L.target_rms, scan.c_str());

            std::size_t sidx = 0;
            for (const auto& sp : L.samples) {
                std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_SAMPLE kind=%s "
                            "target_rms=%.1f idx=%zu tx_logical=%d tx_raw=0x%04X "
                            "rx_raw=0x%04X rx_libiio=%d rx_host_mirror=%d "
                            "rx_force_signed=%d\n",
                            L.kind.c_str(), L.target_rms, sidx++,
                            sp.tx_logical,
                            static_cast<unsigned>(static_cast<std::uint16_t>(sp.tx_raw)),
                            static_cast<unsigned>(static_cast<std::uint16_t>(sp.rx_raw)),
                            sp.rx_libiio, sp.rx_host_mirror, sp.rx_force_signed);
            }
        }
        std::fflush(stdout);

        std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_ROOT_CAUSE token=%s reason=%s "
                    "components=%s\n",
                    rep.cause.token.c_str(), rep.cause.reason.c_str(),
                    rep.cause.components_str().c_str());
        std::fflush(stdout);

        if (rep.cause.token == iqdloop_sweep::kRootCauseFormatMisalignment) {
            std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_SHIFT_CORRECTION "
                        "shift=%d gain_db=%.3f corr=%.6f ok=%d\n",
                        rep.rx_shift.shift, rep.rx_shift.gain_db, rep.rx_shift.corr,
                        rep.rx_shift.ok ? 1 : 0);
            if (rep.rx_shift.ok)
                std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_RECOMMENDATION "
                            "action=--rx-format-shift=%d\n", rep.rx_shift.shift);
            std::fflush(stdout);
        }
        if (rep.cause.token == iqdloop_sweep::kRootCauseCountDomainScale) {
            const auto b = [](std::uint32_t bits) {
                return (bits == 0 || bits > 16) ? 16u : bits;
            };
            const std::uint32_t tx_bits = b(rep.tx_fmt.bits);
            const std::uint32_t rx_bits = b(rep.rx_fmt.bits);
            const std::uint32_t scale =
                (tx_bits > rx_bits) ? (1u << (tx_bits - rx_bits)) : 1u;
            // The scale maps RX-domain frozen counts -> TX-domain logical counts;
            // it is a DOMAIN mapping, not a hardware-attenuation compensation.
            std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_RECOMMENDATION "
                        "action=--digital-loopback-tx-scale=%u "
                        "semantics=rx_count_domain_to_tx_count_domain\n", scale);
            std::fflush(stdout);
        }
        if (rep.cause.token == iqdloop_sweep::kRootCauseFixedAttenuation &&
            rep.scale_sel.ok) {
            std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_SCALE_SELECTION scale=%.6f "
                        "expected_rx_rms=%.3f reason=%s\n",
                        rep.scale_sel.scale, rep.scale_sel.expected_rx_rms,
                        rep.scale_sel.reason.c_str());
            std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_RECOMMENDATION "
                        "action=--digital-loopback-tx-scale=%.6f\n",
                        rep.scale_sel.scale);
            std::fflush(stdout);
        }
        if (!rep.scale_sel.ok && rep.scale_sel.reason != "no usable sweep level")
            std::printf("IQ_DIGITAL_LOOPBACK_SWEEP_SCALE_SELECTION ok=0 reason=%s\n",
                        rep.scale_sel.reason.c_str());

        const bool diagnosed = rep.cause.token != iqdloop_sweep::kRootCauseNotProven;
        std::vector<double> ng_db;
        for (const auto& L : rep.levels)
            if (L.capture_ok && L.target_rms >= 64.0 && L.rx_clip == 0 &&
                L.tx_clip == 0 && L.rx_raw_clip == 0 &&
                L.rx_count_rms >= iqdloop_sweep::kQuantFloorCounts)
                ng_db.push_back(L.normalized_gain_db);
        const double ng_med = iqdloop_sweep::median(ng_db);
        detail = "phase=iq-digital-loopback-sweep root_cause=" + rep.cause.token +
                 " reason=\"" + rep.cause.reason + "\"" +
                 " normalized_gain_db=" + std::to_string(ng_med) +
                 " components=" + rep.cause.components_str();
        if (rep.cause.token == iqdloop_sweep::kRootCauseFormatMisalignment &&
            rep.rx_shift.ok)
            detail += " rx_shift_correction=" + std::to_string(rep.rx_shift.shift);
        if ((rep.cause.token == iqdloop_sweep::kRootCauseFixedAttenuation ||
             rep.cause.token == iqdloop_sweep::kRootCauseCountDomainScale) &&
            rep.scale_sel.ok)
            detail += " tx_scale=" + std::to_string(rep.scale_sel.scale) +
                      " expected_rx_rms=" + std::to_string(rep.scale_sel.expected_rx_rms);
        detail += " loopback_capability=DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN";

        guard->restore();
        restore_ok = guard->restore_ok();

        const bool pass = diagnosed && restore_ok;
        board::emit("gate9_full_chain_rml23", pass, detail);
        return pass ? 0 : 1;
    } catch (const std::exception& e) {
        detail = "phase=iq-digital-loopback-sweep error=" + std::string(e.what());
        board::emit("gate9_full_chain_rml23", false, detail);
        return 1;
    }
}

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();

    const std::string phase = board::get_opt(argc, argv, "--phase", "offline");
    const std::string model_json = board::get_opt(argc, argv, "--model-json",
                                                  "model_rml23/model_24class_ZG.json");
    const std::string model_raw = board::get_opt(argc, argv, "--model-raw",
                                                 "model_rml23/model_24class_ZG.raw");
    const std::string sock_path = board::get_opt(argc, argv, "--sock",
                                                 "/run/sdr_amr_ui_rml23.sock");

    if (!gate9::valid_phase(phase)) {
        board::emit("gate9_full_chain_rml23", false,
                    "error=unknown_phase:" + phase +
                    " (use offline|digital|rf|ambient|live-rx|synthetic-iq|"
                    "iq-digital-loopback|iq-digital-loopback-sweep|iq-rf-loopback)");
        return 1;
    }

    bool pass = false;
    std::string detail;
    m22::StageTiming timing;
    try {
        chain::NpuClassifier24 npu(model_json, model_raw, &timing);
        const cat::Contract contract = chain::contract_23();
        ui::StdoutSink out;
        ui::UnixSocketSink sock(sock_path);

        int rc = 1;
        if (phase == "offline")
            rc = run_offline(npu, contract, out, sock, timing, argc, argv);
        else if (phase == "ambient")
            rc = run_ambient_phase(npu, contract, out, sock, timing, argc, argv);
        else if (phase == "live-rx")
            rc = run_live_rx_phase(npu, contract, out, sock, timing, argc, argv);
        else if (phase == "synthetic-iq")
            rc = run_synthetic_iq_phase(npu, contract, out, sock, timing, argc, argv);
        else if (phase == "iq-digital-loopback")
            rc = run_iq_digital_loopback(npu, contract, out, sock, timing, argc, argv);
        else if (phase == "iq-digital-loopback-sweep")
            rc = run_iq_digital_loopback_sweep(npu, contract, out, sock, timing, argc, argv);
        else if (phase == "iq-rf-loopback")
            rc = run_iq_rf_loopback(npu, contract, out, sock, timing, argc, argv);
        else
            rc = run_loopback_phase(npu, contract, out, sock, timing, argc, argv);
        // Heartbeat errata: prove the data socket actually delivered the state
        // heartbeats and result frames (send_ok == attempted minus failed/dropped).
        std::printf(
            "SOCKET_STATS path=%s send_attempted=%llu send_ok=%llu "
            "send_failed=%llu dropped=%llu errors=%llu\n",
            sock_path.c_str(),
            static_cast<unsigned long long>(sock.send_attempted()),
            static_cast<unsigned long long>(sock.send_ok()),
            static_cast<unsigned long long>(sock.send_failed()),
            static_cast<unsigned long long>(sock.dropped_count()),
            static_cast<unsigned long long>(sock.error_count()));
        std::fflush(stdout);
        return rc;   // each runner emits its own GATE_RESULT line
    } catch (const std::exception& e) {
        pass = false;
        detail = std::string("error=") + e.what();
        board::emit("gate9_full_chain_rml23", pass, detail);
        return 1;
    }
}
