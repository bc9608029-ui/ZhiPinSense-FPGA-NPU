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
//   digital : frames == --frames, every frame valid (12 logits, argmax in range,
//             confidence in [0,1]), no stream anomaly, tone present (Goertzel).
//   rf      : as digital, plus --confirm-safe-rf-path was actually given.
//
// The NPU model is loaded ONCE (NpuClassifier12); every frame runs a fresh session.
// Exit 0/1/2 = pass / fail / device-not-found.

#include "board_common.hpp"
#include "chain_common.hpp"
#include "npu_classifier.hpp"
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

// Is a filled ResultFrame internally valid (live liveness check)?
bool result_frame_valid(const rf::ResultFrame& r) {
    if (r.class_count != 12) return false;
    if (r.argmax_idx < 0 || r.argmax_idx >= 12) return false;
    if (r.probabilities.size() != 12) return false;
    if (r.confidence < 0.0f || r.confidence > 1.0f) return false;
    if (r.logits.size() != 12) return false;
    if (r.version != "12class-chain-v1") return false;
    return true;
}

// Emit one result frame to both sinks; returns the JSONL record.
std::string emit_frame(ui::Sink& out, ui::Sink& sock, const rf::ResultFrame& r) {
    const std::string rec = ui::result_frame_v2_line(r);
    out.write(rec);
    sock.write(rec);
    return rec;
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
// Phase 2/3: digital / RF loopback (SDR -> preprocess -> NPU -> UI).
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
                     (loopback == 0 ? "rf" : "digital");

            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(gain_db);
            dev->set_loopback(loopback);

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

            chain::PreprocessChain chain(static_cast<std::uint32_t>(neg.actual_hz),
                                         nco_offset, rec_scale);
            std::vector<float> tensor(chain::kTensorFloats);

            // Same continuity rule as Gate 6: ONE contiguous RX refill sized for
            // the whole capture (required_input includes the FIR transient), NOT a
            // chunk loop concatenating phase-discontinuous refills.  That loop was
            // the shared root cause of the digital/rf phase-jump failures.
            const std::size_t requested = chain.required_input(frames);
            std::vector<std::int16_t> iq;
            board::RxStats st;
            board::Continuity cont;
            const bool captured = board::capture_contiguous(*dev, requested, iq, st, cont);

            std::size_t produced = 0, valid = 0;
            double ratio_min = 1e9;
            double classify_us_sum = 0.0;

            if (captured && !st.interrupted && iq.size() / 2 > 0) {
                chain.push_int16(iq.data(), iq.size() / 2);
                while (chain.ready() > 0 && produced < frames) {
                    if (!chain.pull_tensor(tensor.data())) break;
                    ++produced;

                    const auto t0 = Clock::now();
                    const std::vector<float> logits = npu.infer(tensor.data());
                    const auto t1 = Clock::now();
                    const double classify_us = static_cast<double>(
                        std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count());
                    classify_us_sum += classify_us;

                    // Tone presence on the reconstructed frame (diagnostic liveness).
                    std::vector<std::complex<float>> x(chain::kFrameComplex);
                    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
                        x[k] = std::complex<float>(tensor[k], tensor[chain::kFrameComplex + k]);
                    const double rp = sdr::goertzel_ratio(x, tone_hz, 128000.0);
                    const double rn = sdr::goertzel_ratio(x, -tone_hz, 128000.0);
                    const double ratio = (rp > rn) ? rp : rn;
                    if (ratio < ratio_min) ratio_min = ratio;

                    rf::ResultFrame r;
                    r.frame_id = static_cast<std::uint64_t>(produced);
                    r.timestamp_us = static_cast<std::uint64_t>(
                        std::chrono::duration_cast<std::chrono::microseconds>(
                            Clock::now().time_since_epoch()).count());
                    r.source = "fpga_npu";
                    r.mock = false;
                    r.overflow = st.overflow != 0;
                    r.dropped = st.dropped != 0;
                    r.discontinuity = st.discontinuity != 0;
                    r.short_frame = st.short_block;
                    chain::fill_result(r, logits, contract, model_sha,
                                       chain::tone_snr_db(x, tone_hz, 128000.0));
                    r.classify_us = classify_us;
                    r.e2e_us = classify_us;

                    emit_frame(out, sock, r);
                    if (result_frame_valid(r)) ++valid;
                }
            }

            // `captured` already encodes "one refill delivered the whole amount with
            // no timeout/short/overflow/drop/discontinuity"; `cont.ok()` proves the
            // capture was a single refill into a large enough buffer.
            const bool frames_ok = (produced == frames);
            const bool tone_ok = frames_ok && ratio_min > 0.3;
            const bool rf_ok = (loopback != 0) || confirm_rf;
            pass = captured && !st.interrupted && cont.ok() && frames_ok &&
                   tone_ok && rf_ok && (valid == produced);

            detail += " frames=" + std::to_string(produced) + "/" + std::to_string(frames);
            detail += " valid=" + std::to_string(valid);
            detail += " rec_scale=" + std::to_string(rec_scale);
            detail += " nco_offset=" + std::to_string(nco_offset);
            detail += " ratio_min=" + std::to_string(ratio_min);
            detail += " classify_us_mean=" +
                      std::to_string(produced ? classify_us_sum / static_cast<double>(produced) : 0.0);
            detail += " short=" + std::to_string(st.short_block ? 1 : 0);
            detail += " interrupted=" + std::to_string(st.interrupted ? 1 : 0);
            detail += " overflow=" + std::to_string(st.overflow);
            detail += " drop=" + std::to_string(st.dropped);
            detail += " disc=" + std::to_string(st.discontinuity);
            detail += cont.report();
            if (!captured) detail += " (stream_broken)";
            if (!cont.ok()) detail += " (continuity_fail)";
            if (!frames_ok) detail += " (frame_short)";
            if (!tone_ok) detail += " (tone_missing)";
            if (!rf_ok) detail += " (rf_unconfirmed)";
            if (valid != produced) detail += " (invalid_frames)";
            if (st.interrupted) detail += " (interrupted)";
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
