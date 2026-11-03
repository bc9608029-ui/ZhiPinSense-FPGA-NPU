// board_gate9_full_chain_12class.cpp -- Gate 9: the full twelve-class
// SDR -> NPU -> UI chain, in three phases (task 39e5 §九):
//
//   --phase offline   (default) replay deployment_golden/input_N.bin through the
//                     NPU and emit a §八 JSONL record per frame; argmax is checked
//                     against expected_argmax.tsv (the strongest phase: proves the
//                     NPU -> UI link against known inputs, no SDR / no RF).
//   --phase digital   Pluto digital-loopback: TX a CW tone -> RX -> NCO/resample
//                     -> fp32 [2,1024] -> NPU -> UI JSONL.  The tone is NOT a
//                     modulation class, so this phase gates CHAIN LIVENESS (N valid
//                     result frames, no stream anomaly, tone present), never
//                     classification correctness.
//   --phase rf        same as digital but external RF path (REQUIRES
//                     --confirm-safe-rf-path; refused otherwise by PlutoTx).
//
// PASS criteria:
//   offline : frames == --count, match_rate >= --min-match-rate, every frame valid.
//   digital : frames == --frames, every frame a valid "12class-chain-v2" record
//             (real measurements + presence/level/mode/run state), no stream
//             anomaly, tone present (Goertzel), and the SignalPresence -> publish
//             link confirmed (present > 0 && published > 0).
//   rf      : as digital, plus --confirm-safe-rf-path was actually given.
//   BAND SCAN (--mode BAND_SCAN): additionally the LO sweep must actually advance
//             (sweep_advances > 0).  AUTO LOCK / BAND SCAN behaviour is proven by
//             host_tests/test_producer_12class.cpp (LO/gain/scale not observable on
//             a single fixed tone).
//
// The digital/rf phases are the LIVE PRODUCER (UI v3 M6-M10): they own the reverse
// control channel (/run/sdr_amr_control.sock) and drive the producer_12class.hpp
// state machine.  The UI server only DISPLAYS the producer-reported authoritative
// work mode / run state; it never self-modifies mode text to fake effectiveness.
//
// The NPU model is loaded ONCE (NpuClassifier12): one persistent Session with
// Device::reset(1) re-arm between frames (see npu_classifier.hpp / npu_rearm_state.hpp).
// Exit 0/1/2 = pass / fail / device-not-found.

#include "board_common.hpp"
#include "chain_common.hpp"
#include "control_channel.hpp"
#include "gate9_phase.hpp"
#include "mode_control.hpp"
#include "npu_classifier.hpp"
#include "producer_12class.hpp"
#include "unix_socket_server.hpp"
#include "unix_socket_sink.hpp"

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

// Structural checks shared by the v1 (offline) and v2 (producer) result frames.
// These prove the NPU produced a well-formed twelve-class verdict; the publish
// gate (presence / work mode) is carried separately by the v3 fields.
bool result_frame_base_valid(const rf::ResultFrame& r) {
    if (r.class_count != 12) return false;
    if (r.logits.size() != 12) return false;
    if (r.probabilities.size() != 12) return false;
    if (r.confidence < 0.0f || r.confidence > 1.0f) return false;
    if (r.argmax_idx < -1 || r.argmax_idx >= 12) return false;
    return true;
}

// Offline replay uses the §八 v1 record (schema "12class-chain-v1").
bool result_frame_valid(const rf::ResultFrame& r) {
    return result_frame_base_valid(r) && r.version == "12class-chain-v1";
}

// The live producer uses the UI-v3 v2 record (schema "12class-chain-v2"), which
// MUST carry real measurements, presence/level state and the producer-owned work
// mode / run state.
bool result_frame_v3_valid(const rf::ResultFrame& r) {
    return result_frame_base_valid(r) && r.version == "12class-chain-v2" &&
           r.has_measurements && r.measurements.valid &&
           !r.presence_state.empty() && !r.level_mode.empty() &&
           !r.work_mode.empty() && !r.run_state.empty();
}

// Emit one result frame to both sinks; returns the JSONL record.
std::string emit_frame(ui::Sink& out, ui::Sink& sock, const rf::ResultFrame& r) {
    const std::string rec = ui::result_frame_v2_line(r);
    out.write(rec);
    sock.write(rec);
    return rec;
}

// Emit a UI-v3 v2 result record (measurements + presence + level + mode + run).
std::string emit_frame_v3(ui::Sink& out, ui::Sink& sock, const rf::ResultFrame& r) {
    const std::string rec = ui::result_frame_v3_line(r);
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
// state change, so the UI shows STOPPED / RUNNING / the new mode even though
// classification frames stop flowing while STOPPED (task 39e5 Task E, 方案 A).
void emit_state_event(ui::Sink& out, ui::Sink& sock,
                      const mode_ctl::ModeState& st,
                      const std::string& presence_state,
                      std::uint64_t command_id) {
    const std::string rec = ui::state_line(
        mode_ctl::mode_token(st.mode), mode_ctl::run_display_name(st.run),
        presence_state.c_str(), command_id,
        static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(
                Clock::now().time_since_epoch()).count()));
    out.write(rec);
    sock.write(rec);
}

// ---------------------------------------------------------------------------
// Phase 1: offline replay (golden inputs -> NPU -> UI).
// ---------------------------------------------------------------------------
int run_offline(chain::NpuClassifier12& npu, const cat::Contract& contract,
                ui::StdoutSink& out, ui::UnixSocketSink& sock,
                int argc, char** argv) {
    const std::string golden_dir = board::get_opt(argc, argv, "--golden",
                                                  "deployment_golden");
    const std::size_t count = static_cast<std::size_t>(board::opt_u64(argc, argv, "--count", 240));
    const double min_match = board::opt_d(argc, argv, "--min-match-rate", 0.90);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");

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
        return (board::emit("gate9_full_chain_12class", false,
                            "error=empty_expected_argmax:" + tsv_path), 1);

    const std::size_t n = count < exp_argmax.size() ? count : exp_argmax.size();
    std::vector<float> tensor(chain::kTensorFloats);
    std::size_t processed = 0, matched = 0, valid = 0;

    for (std::size_t i = 0; i < n; ++i) {
        if (board::g_stop_requested) break;
        char path[512];
        std::snprintf(path, sizeof(path), "%s/input_%03zu.bin", golden_dir.c_str(), i);
        if (!read_input_bin(path, tensor))
            return (board::emit("gate9_full_chain_12class", false,
                                std::string("error=short_input:") + path), 1);

        const auto t0 = Clock::now();
        const std::vector<float> logits = npu.infer(tensor.data());
        const auto t1 = Clock::now();

        rf::ResultFrame r;
        r.frame_id = static_cast<std::uint64_t>(i + 1);
        r.timestamp_us = static_cast<std::uint64_t>(i + 1) * 8000ULL;
        r.source = "fpga_npu";
        r.mock = false;
        chain::fill_result(r, logits, contract, model_sha,
                           std::numeric_limits<double>::quiet_NaN());
        r.classify_us = static_cast<double>(
            std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count());
        r.e2e_us = r.classify_us;

        emit_frame(out, sock, r);
        ++processed;
        if (result_frame_valid(r)) ++valid;
        if (argmax_of(logits) == exp_argmax[i]) ++matched;
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
    board::emit("gate9_full_chain_12class", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase 2/3: digital / RF loopback -- the LIVE twelve-class producer (M6-M10).
//
// This is now a CONTINUOUS producer loop, not a single-shot capture: the producer
// owns the reverse control channel (/run/sdr_amr_control.sock) and, per frame,
// computes real sdr::FrameMeasurements, updates SignalPresence (a non-present
// frame never publishes a class), advances the WorkModeEngine (FIXED / AUTO LOCK /
// BAND SCAN), applies the engine's model_scale ON TOP of the receiver_scale tensor
// before inference, applies a bounded/safe/logged RF gain, and emits a
// "12class-chain-v2" result with measurements/presence/level/mode/run state.  In
// BAND SCAN it re-tunes the RX LO per start/stop/step/dwell, resets the class lock
// after each LO step, and reports the current LO + scan progress on every frame.
//
// The tone (--tone, a CW at baseband) is NOT a modulation class, so the default
// FIXED run still gates CHAIN LIVENESS: frames == --frames, every frame a valid v3
// record, tone present (Goertzel), presence confirmed (SignalPresence + publish
// link), no stream anomaly, continuity ok, restore ok.  AUTO LOCK / BAND SCAN are
// entered via the control channel or --mode and are proven by the host test
// test_producer_12class.cpp (their LO/gain/scale behaviour is not observable on a
// single fixed tone).
// ---------------------------------------------------------------------------
int run_loopback_phase(chain::NpuClassifier12& npu, const cat::Contract& contract,
                       ui::StdoutSink& out, ui::UnixSocketSink& sock,
                       int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const int loopback = (board::get_opt(argc, argv, "--phase", "digital") == "rf") ? 0 : 1;
    const bool confirm_rf = board::has_flag(argc, argv, "--confirm-safe-rf-path");
    const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 16);
    const double tone_hz = board::opt_d(argc, argv, "--tone", 10000.0);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const float rec_scale = static_cast<float>(board::opt_d(argc, argv, "--rec-scale", 1.0));
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string ctl_sock = board::get_opt(argc, argv, "--ctl-sock",
                                                "/run/sdr_amr_control.sock");

    // Producer control-plane options (M6-M10).
    const std::string mode_opt = board::get_opt(argc, argv, "--mode", "FIXED");
    mode_ctl::ModeKind init_mode = mode_ctl::ModeKind::Fixed;
    if (!mode_ctl::mode_from_token(mode_opt, init_mode)) {
        board::emit("gate9_full_chain_12class", false,
                    "error=unknown_mode:" + mode_opt + " (use FIXED|AUTO_LOCK|BAND_SCAN)");
        return 1;
    }
    const std::size_t batch_frames = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--batch-frames", 16));
    const int stability_window = static_cast<int>(
        board::opt_u64(argc, argv, "--stability-window", 5));

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate9_full_chain_12class", false,
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

            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(gain_db);
            dev->set_loopback(loopback);

            // The live producer: owns the control channel + all runtime state.
            producer::ProducerConfig pcfg;
            pcfg.dsp.sample_rate_hz = 128000.0;          // post-decimation model rate
            pcfg.dsp.receiver_scale = rec_scale;         // frozen receiver_scale
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

            // Task E: decouple control RECEPTION (control thread) from command
            // APPLICATION (unique producer thread).  The control thread only
            // parses / validates / enqueues and answers ACCEPTED + STATUS from the
            // atomic snapshot; it NEVER touches Pluto / LO / gain / NPU.  The
            // producer drains the queue at 12 safe points and answers APPLIED via
            // the ack queue, which the control thread forwards (it owns the socket).
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

            // Both loopback phases TX a tone (digital, or external RF when
            // confirmed).  PlutoTx is scoped here so its RAII stops the TX buffer
            // before the DeviceStateGuard restores parameters below.
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
                tx->prepare();          // throws if RF path unconfirmed
                tx->start_cyclic();
            }

            std::string last_presence_state;

            // Task E two-phase timing: APPLIED must land within kApplyTimeoutMs of
            // ACCEPTED.  Longer is counted (timeouts) and fails the gate.
            const std::int64_t kApplyTimeoutMs = 2000;

            // Drain the command queue at a SAFE POINT.  The unique producer thread
            // is the sole owner of Pluto / LO / gain / NPU, so this is the only
            // place a command may change hardware.  Each applied command updates the
            // applied_* atomics, enqueues the APPLIED ack (forwarded by the control
            // thread), emits a state event on any mode/run change, and logs it.
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
                        emit_state_event(out, sock, after, last_presence_state, c.id);
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

            // Initial state event (command_id=0) so the UI renders the startup
            // mode/run before the first classification frame arrives.
            emit_state_event(out, sock, prod.mode_state(), "", 0);

            std::uint64_t total_processed = 0;
            std::size_t valid = 0, published = 0, present = 0;
            double ratio_min = 1e9;
            double classify_us_sum = 0.0;
            bool stream_broken = false, continuity_ok_all = true, interrupted = false;
            bool any_short = false;

            // Continuous producer loop: one contiguous RX refill per batch (same
            // continuity rule as Gate 6), sized by the producer's capture schedule.
            // Control commands are applied at the 12 SAFE POINTS (SP) below -- never
            // from the control thread, never mid-libiio / mid-NPU.
            while (!board::g_stop_requested && total_processed < frames) {
                // SP 1: top of the batch loop (before the running check).
                apply_pending("loop_top");
                if (!prod.running()) {
                    // SP 11: while STOPPED, keep applying control commands (a START
                    // is answered promptly), then idle.
                    apply_pending("stopped");
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    continue;
                }

                // SP 2: before capture scheduling (before any LO retune).
                apply_pending("before_capture");
                prod.before_capture();
                // SP 3: after capture scheduling / LO retune.
                apply_pending("after_capture_schedule");
                std::size_t batch = prod.capture_batch_frames();
                if (batch > frames - total_processed)
                    batch = static_cast<std::size_t>(frames - total_processed);

                chain::PreprocessChain chain(static_cast<std::uint32_t>(neg.actual_hz),
                                             nco_offset, rec_scale);
                std::vector<float> tensor(chain::kTensorFloats);
                const std::size_t requested = chain.required_input(batch);
                std::vector<std::int16_t> iq;
                board::RxStats st;
                board::Continuity cont;
                // SP 4: before the (potentially long) contiguous RX refill.
                apply_pending("before_rx_refill");
                const bool captured = board::capture_contiguous(*dev, requested, iq, st, cont);
                if (st.interrupted) { interrupted = true; break; }
                if (!captured) { stream_broken = true; break; }
                if (!cont.ok()) continuity_ok_all = false;
                // SP 5: after the RX refill, before preprocess.
                apply_pending("after_rx_refill");

                chain.push_int16(iq.data(), iq.size() / 2);
                std::size_t produced_batch = 0;
                while (chain.ready() > 0 && produced_batch < batch &&
                       total_processed < frames) {
                    // SP 6: top of the per-frame loop.
                    apply_pending("frame_top");
                    if (!prod.running()) break;   // STOP/SET_MODE interrupt honoured

                    if (!chain.pull_tensor(tensor.data())) break;

                    producer::CaptureFlags flags;
                    flags.overflow = st.overflow != 0;
                    flags.dropped = st.dropped != 0;
                    flags.discontinuity = st.discontinuity != 0;
                    flags.short_frame = st.short_block;
                    if (st.short_block) any_short = true;

                    // Tone presence on the base tensor (scale-invariant ratio).
                    std::vector<std::complex<float>> x(chain::kFrameComplex);
                    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
                        x[k] = std::complex<float>(tensor[k],
                                                   tensor[chain::kFrameComplex + k]);
                    const double rp = sdr::goertzel_ratio(x, tone_hz, 128000.0);
                    const double rn = sdr::goertzel_ratio(x, -tone_hz, 128000.0);
                    const double ratio = (rp > rn) ? rp : rn;
                    if (ratio < ratio_min) ratio_min = ratio;

                    // SP 7: after tensor pull + tone detection, before the NPU forward.
                    apply_pending("before_infer");
                    if (!prod.running()) break;   // STOP landed right before infer

                    ++produced_batch;
                    ++total_processed;

                    double classify_us = 0.0;
                    producer::ProducerDecision d = prod.on_frame(
                        tensor.data(), flags,
                        [&](const float* t, std::vector<float>& lg) {
                            const auto t0 = Clock::now();
                            lg = npu.infer(t);
                            const auto t1 = Clock::now();
                            classify_us = static_cast<double>(
                                std::chrono::duration_cast<std::chrono::microseconds>(
                                    t1 - t0).count());
                            classify_us_sum += classify_us;
                        });

                    if (d.has_measurements || !d.presence_state.empty())
                        last_presence_state = d.presence_state;

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
                    chain::fill_result(r, d.logits, contract, model_sha,
                                       chain::tone_snr_db(x, tone_hz, 128000.0));
                    r.version = "12class-chain-v2";
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

                    // SP 8: before publish/emit.
                    apply_pending("before_emit");
                    emit_frame_v3(out, sock, r);
                    if (result_frame_v3_valid(r)) ++valid;
                    if (d.presence_state == "SIGNAL_PRESENT") ++present;
                    // SP 9: end of frame.
                    apply_pending("frame_end");
                }
                // SP 10: end of batch.
                apply_pending("batch_end");
            }

            // SP 12: final drain (apply anything still queued), then shut down the
            // control thread and unlink the socket.
            apply_pending("final");
            cstate.stop.store(true);
            ctl_thread.join();
            control.stop();

            // PASS: the whole frame budget was produced as valid v3 records, the
            // tone was present, presence confirmed (SignalPresence -> publish link),
            // no stream anomaly / continuity violation, and (for BAND SCAN) the LO
            // sweep actually advanced.  RF restore is folded in below (fail-closed).
            const bool frames_ok = (total_processed == frames);
            const bool tone_ok = frames_ok && ratio_min > 0.3;
            const bool rf_ok = (loopback != 0) || confirm_rf;
            const bool presence_ok = present > 0 && published > 0;
            const bool scan_ok = (init_mode != mode_ctl::ModeKind::BandScan) ||
                                 prod.sweep_advances() > 0;
            // Task E: the control channel must reject nothing and time out nothing
            // (every accepted command applied <= 2 s) for the gate to pass.
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
        // Fail-closed: a functional PASS is only real if the restore also
        // succeeded (closes the fail-open on restore_result=FAIL).
        pass = board::final_gate_pass(pass, guard->restore_ok(), detail);
    } else {
        pass = false;
        detail += " (no_state_guard)";
    }

    board::emit("gate9_full_chain_12class", pass, detail);
    return pass ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Phase 4: ambient / rx-only -- the real no-signal integration test (新增项2).
//
// NO TX buffer is ever created (tx_active=0): the receiver listens continuously
// on the EXTERNAL RF input (loopback=0) and the full SDR -> DSP -> SignalPresence
// -> UI chain runs per frame.  SignalPresence carries hysteresis + consecutive-
// frame confirmation, so a real signal appearing / disappearing transitions the
// state SIGNAL_PRESENT <-> NO_SIGNAL (logged as PRESENCE_TRANSITION lines), and a
// NO_SIGNAL / ACQUIRING / SIGNAL_LOST / INVALID frame NEVER publishes a
// classification (argmax_idx=-1, confidence=0).  The gate therefore proves:
//
//   1. tx_active=0 -- no TX buffer was ever created / started;
//   2. continuous RX + DSP + SignalPresence + UI publish (every frame a valid
//      "12class-chain-v2" record with real measurements + presence/level/mode/run);
//   3. presence transitions are observed and logged (inject/remove a signal to
//      exercise SIGNAL_PRESENT <-> NO_SIGNAL);
//   4. no fake classification: published_while_not_present == 0 (a non-present
//      frame never carries a class), the deterministic no-signal invariant;
//   5. RF/TX fail-closed: there is no TX, so nothing to confirm; the receiver is
//      external RF and the DeviceStateGuard restores on every exit path.
//
// PASS criteria (deterministic in any lab): frames==--frames, every frame valid,
// no stream anomaly / continuity violation, no fake classification, restore ok,
// control ok.  presence_transitions / present / nosignal are logged diagnostics
// for the operator to confirm the transition behaviour (req. 3) manually.
// ---------------------------------------------------------------------------
int run_ambient_phase(chain::NpuClassifier12& npu, const cat::Contract& contract,
                      ui::StdoutSink& out, ui::UnixSocketSink& sock,
                      int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const float rec_scale = static_cast<float>(board::opt_d(argc, argv, "--rec-scale", 1.0));
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string ctl_sock = board::get_opt(argc, argv, "--ctl-sock",
                                                "/run/sdr_amr_control.sock");
    const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 64);
    const std::size_t batch_frames = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--batch-frames", 16));
    const int stability_window = static_cast<int>(
        board::opt_u64(argc, argv, "--stability-window", 5));

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate9_full_chain_12class", false,
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

            // RX-only: NO TX buffer is ever created.  Listen on the external RF
            // input (loopback=0) so a real ambient signal (or its absence) drives
            // SignalPresence.  tx_active=0 is the observable contract.
            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(gain_db);
            dev->set_loopback(0);
            std::printf("AMBIENT_RX tx_active=0 loopback=0 gain_db=%.3f\n", gain_db);
            std::fflush(stdout);

            producer::ProducerConfig pcfg;
            pcfg.dsp.sample_rate_hz = 128000.0;          // post-decimation model rate
            pcfg.dsp.receiver_scale = rec_scale;         // frozen receiver_scale
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
                        emit_state_event(out, sock, after, last_presence_state, c.id);
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

            emit_state_event(out, sock, prod.mode_state(), "", 0);

            std::uint64_t total_processed = 0;
            std::size_t valid = 0, published = 0, present = 0, nosignal = 0;
            std::size_t published_while_not_present = 0;
            bool stream_broken = false, continuity_ok_all = true, interrupted = false;
            std::uint64_t presence_transitions = 0;

            while (!board::g_stop_requested && total_processed < frames) {
                apply_pending("loop_top");
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

                chain::PreprocessChain chain(fs_in, nco_offset, rec_scale);
                std::vector<float> tensor(chain::kTensorFloats);
                const std::size_t requested = chain.required_input(batch);
                std::vector<std::int16_t> iq;
                board::RxStats st;
                board::Continuity cont;
                apply_pending("before_rx_refill");
                const bool captured = board::capture_contiguous(*dev, requested, iq, st, cont);
                if (st.interrupted) { interrupted = true; break; }
                if (!captured) { stream_broken = true; break; }
                if (!cont.ok()) continuity_ok_all = false;
                apply_pending("after_rx_refill");

                chain.push_int16(iq.data(), iq.size() / 2);
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

                    ++produced_batch;
                    ++total_processed;

                    double classify_us = 0.0;
                    producer::ProducerDecision d = prod.on_frame(
                        tensor.data(), flags,
                        [&](const float* t, std::vector<float>& lg) {
                            const auto t0 = Clock::now();
                            lg = npu.infer(t);
                            const auto t1 = Clock::now();
                            classify_us = static_cast<double>(
                                std::chrono::duration_cast<std::chrono::microseconds>(
                                    t1 - t0).count());
                        });

                    const bool present_now = (d.presence_state == "SIGNAL_PRESENT");
                    if (d.presence_state == "NO_SIGNAL") ++nosignal;

                    // Presence transition logging (req. 3): a real signal appearing
                    // / disappearing moves SIGNAL_PRESENT <-> NO_SIGNAL through the
                    // hysteresis + confirmation state machine.
                    if (!d.presence_state.empty() && d.presence_state != last_presence_state) {
                        if (!last_presence_state.empty()) ++presence_transitions;
                        std::printf("PRESENCE_TRANSITION from=%s to=%s frame=%llu\n",
                                    last_presence_state.empty() ? "-" : last_presence_state.c_str(),
                                    d.presence_state.c_str(),
                                    static_cast<unsigned long long>(total_processed));
                        std::fflush(stdout);
                        last_presence_state = d.presence_state;
                    }

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
                    chain::fill_result(r, d.logits, contract, model_sha,
                                       std::numeric_limits<double>::quiet_NaN());
                    r.version = "12class-chain-v2";
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

                    // Publish gating: a non-present frame carries NO class (req. 4).
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

                    apply_pending("before_emit");
                    emit_frame_v3(out, sock, r);
                    if (result_frame_v3_valid(r)) ++valid;
                    if (present_now) ++present;
                    apply_pending("frame_end");
                }
                apply_pending("batch_end");
            }

            apply_pending("final");
            cstate.stop.store(true);
            ctl_thread.join();
            control.stop();

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

    board::emit("gate9_full_chain_12class", pass, detail);
    return pass ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();

    const std::string phase = board::get_opt(argc, argv, "--phase", "offline");
    const std::string model_json = board::get_opt(argc, argv, "--model-json",
                                                  "model_12class/model_12class.json");
    const std::string model_raw = board::get_opt(argc, argv, "--model-raw",
                                                 "model_12class/model_12class.raw");
    const std::string sock_path = board::get_opt(argc, argv, "--sock", "");

    if (!gate9::valid_phase(phase)) {
        board::emit("gate9_full_chain_12class", false,
                    "error=unknown_phase:" + phase +
                    " (use offline|digital|rf|ambient)");
        return 1;
    }

    bool pass = false;
    std::string detail;
    try {
        chain::NpuClassifier12 npu(model_json, model_raw);
        const cat::Contract contract = chain::contract_12();
        ui::StdoutSink out;
        ui::UnixSocketSink sock(sock_path);

        int rc = 1;
        if (phase == "offline")
            rc = run_offline(npu, contract, out, sock, argc, argv);
        else if (phase == "ambient")
            rc = run_ambient_phase(npu, contract, out, sock, argc, argv);
        else
            rc = run_loopback_phase(npu, contract, out, sock, argc, argv);
        return rc;   // each runner emits its own GATE_RESULT line
    } catch (const std::exception& e) {
        pass = false;
        detail = std::string("error=") + e.what();
        board::emit("gate9_full_chain_12class", pass, detail);
        return 1;
    }
}
