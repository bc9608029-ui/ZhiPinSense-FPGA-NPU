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

// Drain the producer's reverse control channel: apply each command, reply, log.
void drain_control(ui::UnixSocketServer& control, producer::Producer12& prod) {
    ui::UnixSocketServer::PollResult cpr = control.poll(0);
    for (const std::string& line : cpr.lines) {
        const std::string resp = prod.apply_command(line);
        control.reply(resp);
        std::printf("GATE9_MODE_CTL cmd=%s -> %s\n", line.c_str(), resp.c_str());
        std::fflush(stdout);
    }
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

            std::uint64_t total_processed = 0;
            std::size_t valid = 0, published = 0, present = 0;
            double ratio_min = 1e9;
            double classify_us_sum = 0.0;
            bool stream_broken = false, continuity_ok_all = true, interrupted = false;
            bool any_short = false;

            // Continuous producer loop: one contiguous RX refill per batch (same
            // continuity rule as Gate 6), sized by the producer's capture schedule.
            while (!board::g_stop_requested && total_processed < frames) {
                drain_control(control, prod);
                if (!prod.running()) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    continue;
                }

                prod.before_capture();
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
                const bool captured = board::capture_contiguous(*dev, requested, iq, st, cont);
                if (st.interrupted) { interrupted = true; break; }
                if (!captured) { stream_broken = true; break; }
                if (!cont.ok()) continuity_ok_all = false;

                chain.push_int16(iq.data(), iq.size() / 2);
                std::size_t produced_batch = 0;
                while (chain.ready() > 0 && produced_batch < batch &&
                       total_processed < frames) {
                    if (!chain.pull_tensor(tensor.data())) break;
                    ++produced_batch;
                    ++total_processed;

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

                    emit_frame_v3(out, sock, r);
                    if (result_frame_v3_valid(r)) ++valid;
                    if (d.presence_state == "SIGNAL_PRESENT") ++present;
                }
            }

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
            pass = !stream_broken && !interrupted && continuity_ok_all && frames_ok &&
                   tone_ok && rf_ok && presence_ok && scan_ok && (valid == total_processed);

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
            if (stream_broken) detail += " (stream_broken)";
            if (!continuity_ok_all) detail += " (continuity_fail)";
            if (!frames_ok) detail += " (frame_short)";
            if (!tone_ok) detail += " (tone_missing)";
            if (!rf_ok) detail += " (rf_unconfirmed)";
            if (!presence_ok) detail += " (presence_publish_missing)";
            if (!scan_ok) detail += " (band_scan_no_advance)";
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

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();

    const std::string phase = board::get_opt(argc, argv, "--phase", "offline");
    const std::string model_json = board::get_opt(argc, argv, "--model-json",
                                                  "model_12class/model_12class.json");
    const std::string model_raw = board::get_opt(argc, argv, "--model-raw",
                                                 "model_12class/model_12class.raw");
    const std::string sock_path = board::get_opt(argc, argv, "--sock", "");

    if (phase != "offline" && phase != "digital" && phase != "rf") {
        board::emit("gate9_full_chain_12class", false,
                    "error=unknown_phase:" + phase + " (use offline|digital|rf)");
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
