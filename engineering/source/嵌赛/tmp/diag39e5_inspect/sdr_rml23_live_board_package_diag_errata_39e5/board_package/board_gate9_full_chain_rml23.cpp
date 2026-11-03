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
#include "unix_socket_server.hpp"
#include "unix_socket_sink.hpp"

#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <sys/stat.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <limits>
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
void finish_m22_runtime(const char* phase, const std::string& model_sha,
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

    if (cfg.perf_file.empty()) return;
    FILE* f = std::fopen(cfg.perf_file.c_str(), "w");
    if (!f) {
        std::fprintf(stderr, "m22: cannot write perf file %s\n",
                     cfg.perf_file.c_str());
        return;
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
                    " (use offline|digital|rf|ambient|live-rx)");
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
