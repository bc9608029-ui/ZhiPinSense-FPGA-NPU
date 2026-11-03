// board_gate10_selftest_12class.cpp -- Gate 10: twelve-class RF SELF-TEST.
//
// For each modulation class (0..11) the program:
//   1. synthesises a long continuous baseband stream of that class (128 kS/s,
//      RMS == 1.0 per frame, exactly the training generator's domain) and
//      upsamples it x20 to the device rate with sdr::make_20x_upsampler();
//   2. peak-limits it to --peak-limit DAC counts (no clipping) and transmits it
//      as a cyclic TX buffer (PlutoTx, same safety state machine as Gate 9);
//   3. captures ONE contiguous RX refill (board::capture_contiguous) through the
//      same SDR->tensor preprocess chain (÷2048 -> NCO -> x20 decimate -> 1024);
//   4. measures the reconstructed RMS once, derives a per-class receiver_scale
//      (1/rms) so the NPU sees the training RMS==1.0 domain, then re-runs the
//      chain and classifies every frame (NpuClassifier12, re-armed per frame);
//   5. counts the per-class match rate + a 12x12 confusion matrix.
//
// PASS (per tested class): captured==frames, every frame valid, continuity ok,
//   match_rate >= --min-match-rate, and the device restore succeeded.
// The whole gate PASSES only when EVERY tested class passes.  (Gate 10 is a
// self-test -- a PASS here proves the model classifies real twelve-class
// waveforms; it never overrides the OOD=NO_GO / FINAL_MODEL_PASS red lines.)
//
// STANDALONE SELF-TEST (not the live producer): Gate 10 emits the §八 "12class-
// chain-v1" record (result_frame_v2_line) for its own per-class counting and does
// NOT emit the UI-v3 "12class-chain-v2" record.  It never feeds the MODE /
// PARAMETERS pages -- those are fed exclusively by the Gate 9 live producer
// (board_gate9_full_chain_12class.cpp, result_frame_v3_line).  If Gate 10 is ever
// pointed at the screen, it must be re-wired to the v2 record first.
//
// Exit 0/1/2 = pass / fail / device-not-found.  Board-only (iCraft + libiio);
// the waveform builder + upsampler are host-tested in test_rf_waveform_12class.cpp.

#include "board_common.hpp"
#include "chain_common.hpp"
#include "npu_classifier.hpp"
#include "unix_socket_sink.hpp"
#include "../sdr_adapter/rf_waveform_12class.hpp"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>
#include <string>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;

int argmax_of(const std::vector<float>& logits) {
    if (logits.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(logits.size()); ++i)
        if (logits[i] > logits[best]) best = i;
    return best;
}

bool result_frame_valid(const rf::ResultFrame& r) {
    if (r.class_count != 12) return false;
    if (r.argmax_idx < 0 || r.argmax_idx >= 12) return false;
    if (r.probabilities.size() != 12) return false;
    if (r.confidence < 0.0f || r.confidence > 1.0f) return false;
    if (r.logits.size() != 12) return false;
    if (r.version != "12class-chain-v1") return false;
    return true;
}

std::string emit_frame(ui::Sink& out, ui::Sink& sock, const rf::ResultFrame& r) {
    const std::string rec = ui::result_frame_v2_line(r);
    out.write(rec);
    sock.write(rec);
    return rec;
}

// RMS of a [I(1024), Q(1024)] tensor (model-domain, before receiver_scale).
double tensor_rms(const float* tensor) {
    double s = 0.0;
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
        const double re = static_cast<double>(tensor[k]);
        const double im = static_cast<double>(tensor[chain::kFrameComplex + k]);
        s += re * re + im * im;
    }
    return std::sqrt(s / static_cast<double>(chain::kFrameComplex));
}

int run_selftest(chain::NpuClassifier12& npu, const cat::Contract& contract,
                 ui::StdoutSink& out, ui::UnixSocketSink& sock,
                 int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const int loopback = (board::get_opt(argc, argv, "--loopback", "digital") == "rf") ? 0 : 1;
    const bool confirm_rf = board::has_flag(argc, argv, "--confirm-safe-rf-path");
    const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 20);
    const std::uint64_t tx_frames = board::opt_u64(argc, argv, "--tx-frames", 64);
    const double min_match = board::opt_d(argc, argv, "--min-match-rate", 0.90);
    const double peak_limit = board::opt_d(argc, argv, "--peak-limit", 1638.0);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const std::uint64_t seed = board::opt_u64(argc, argv, "--seed", 0x39e50001ULL);
    const std::uint64_t center = board::opt_u64(argc, argv, "--center", 2450000000ULL);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");

    std::vector<int> classes;
    const std::string cls_opt = board::get_opt(argc, argv, "--class", "");
    if (cls_opt.empty()) {
        for (int c = 0; c < 12; ++c) classes.push_back(c);
    } else {
        const int c = static_cast<int>(board::opt_u64(argc, argv, "--class", 0));
        if (c < 0 || c >= 12) {
            board::emit("gate10_selftest_12class", false,
                        "error=class_out_of_range:" + std::to_string(c));
            return 1;
        }
        classes.push_back(c);
    }

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate10_selftest_12class", false,
                    std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool all_ok = false;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    std::vector<int> matched(12, 0), counted(12, 0);
    std::vector<std::vector<int>> confusion(12, std::vector<int>(12, 0));

    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        const sdr::RateNegotiation neg =
            sdr::negotiate_sample_rate(*dev, sdr::default_rate_candidates(), 128000);
        if (!neg.ok) {
            detail = "negotiation_failed: " + neg.report();
        } else {
            detail = neg.report() + "; loopback=" +
                     (loopback == 0 ? "rf" : "digital");
            const std::uint32_t fs_in = static_cast<std::uint32_t>(neg.actual_hz);

            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(gain_db);
            dev->set_loopback(loopback);

            std::uint64_t frame_counter = 0;
            bool all_classes_ok = true;

            for (int c : classes) {
                if (board::g_stop_requested) break;

                // 1. Build the cyclic TX waveform for this class.
                std::vector<std::int16_t> waveform;
                double tx_peak = 0.0, tx_rms = 0.0;
                sdr::build_tx_waveform(c, seed, static_cast<std::size_t>(tx_frames),
                                       peak_limit, waveform, &tx_peak, &tx_rms);

                bool class_pass = false;
                std::string cd;

                {
                    // 2. Transmit (PlutoTx RAII destroys the TX buffer on exit).
                    pluto::TxConfig txc;
                    txc.center_freq_hz = center;
                    txc.rx_gain_db = gain_db;
                    txc.tx_atten_db = tx_atten;
                    txc.loopback = loopback;
                    txc.confirm_safe_rf_path = confirm_rf;
                    txc.waveform = waveform;
                    pluto::PlutoTx tx(*dev, txc);
                    tx.prepare();          // throws if RF path unconfirmed
                    tx.start_cyclic();

                    // 3. One contiguous RX capture sized for the whole run.
                    chain::PreprocessChain chain_meas(fs_in, 0.0, 1.0f);
                    const std::size_t requested = chain_meas.required_input(frames);
                    std::vector<std::int16_t> iq;
                    board::RxStats st;
                    board::Continuity cont;
                    const bool captured =
                        board::capture_contiguous(*dev, requested, iq, st, cont);

                    std::size_t produced = 0, valid = 0;
                    int class_matched = 0;
                    double rms_mean = 0.0;
                    double classify_us_sum = 0.0;

                    if (captured && !st.interrupted && iq.size() / 2 > 0) {
                        // 4a. Measure reconstructed RMS (receiver_scale == 1.0).
                        std::vector<float> tensor(chain::kTensorFloats);
                        chain_meas.push_int16(iq.data(), iq.size() / 2);
                        double rms_sum = 0.0;
                        int rms_n = 0;
                        while (chain_meas.ready() > 0 &&
                               rms_n < static_cast<int>(frames)) {
                            if (!chain_meas.pull_tensor(tensor.data())) break;
                            rms_sum += tensor_rms(tensor.data());
                            ++rms_n;
                        }
                        rms_mean = rms_n ? rms_sum / static_cast<double>(rms_n) : 0.0;
                        const float rec_scale =
                            (rms_mean > 1e-9)
                                ? static_cast<float>(1.0 / rms_mean)
                                : 1.0f;

                        // 4b. Classify with the derived receiver_scale.
                        chain::PreprocessChain chain(fs_in, 0.0, rec_scale);
                        chain.push_int16(iq.data(), iq.size() / 2);
                        while (chain.ready() > 0 &&
                               produced < static_cast<std::size_t>(frames)) {
                            if (!chain.pull_tensor(tensor.data())) break;
                            ++produced;

                            const auto t0 = Clock::now();
                            const std::vector<float> logits = npu.infer(tensor.data());
                            const auto t1 = Clock::now();
                            classify_us_sum += static_cast<double>(
                                std::chrono::duration_cast<std::chrono::microseconds>(
                                    t1 - t0).count());

                            const int pred = argmax_of(logits);
                            if (pred >= 0 && pred < 12) confusion[c][pred]++;
                            if (pred == c) ++class_matched;

                            rf::ResultFrame r;
                            r.frame_id = ++frame_counter;
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
                                               std::numeric_limits<double>::quiet_NaN());
                            r.classify_us = classify_us_sum / static_cast<double>(produced);
                            r.e2e_us = r.classify_us;
                            emit_frame(out, sock, r);
                            if (result_frame_valid(r)) ++valid;
                        }
                    }

                    matched[c] = class_matched;
                    counted[c] = static_cast<int>(produced);
                    const double rate =
                        produced ? static_cast<double>(class_matched) /
                                       static_cast<double>(produced)
                                 : 0.0;

                    const bool frames_ok =
                        (produced == static_cast<std::size_t>(frames));
                    const bool rf_ok = (loopback != 0) || confirm_rf;
                    class_pass = captured && !st.interrupted && cont.ok() &&
                                 frames_ok && rf_ok && (valid == produced) &&
                                 (rate >= min_match);

                    cd += " class=" + cat::label(contract, c);
                    cd += " matched=" + std::to_string(class_matched) + "/" +
                          std::to_string(produced);
                    cd += " match_rate=" + std::to_string(rate);
                    cd += " valid=" + std::to_string(valid);
                    cd += " rec_scale=" + std::to_string(rms_mean > 1e-9
                                                             ? 1.0 / rms_mean
                                                             : 0.0);
                    cd += " rms=" + std::to_string(rms_mean);
                    cd += " tx_peak=" + std::to_string(tx_peak);
                    cd += " tx_rms=" + std::to_string(tx_rms);
                    cd += " classify_us_mean=" +
                          std::to_string(produced ? classify_us_sum /
                                                        static_cast<double>(produced)
                                                  : 0.0);
                    cd += " short=" + std::to_string(st.short_block ? 1 : 0);
                    cd += " overflow=" + std::to_string(st.overflow);
                    cd += " drop=" + std::to_string(st.dropped);
                    cd += " disc=" + std::to_string(st.discontinuity);
                    cd += cont.report();
                    if (!captured) cd += " (capture_failed)";
                    if (!cont.ok()) cd += " (continuity_fail)";
                    if (!frames_ok) cd += " (frame_short)";
                    if (!rf_ok) cd += " (rf_unconfirmed)";
                    if (valid != produced) cd += " (invalid_frames)";
                    if (st.interrupted) cd += " (interrupted)";
                    if (rate < min_match) cd += " (match_below_threshold)";
                }

                detail += cd;
                if (!class_pass) all_classes_ok = false;
            }

            all_ok = all_classes_ok && !classes.empty();
        }

        guard->restore();
    } catch (const std::exception& e) {
        all_ok = false;
        detail += std::string(" error=") + e.what();
    }

    if (guard) {
        guard->restore();
        detail += board::restore_report(*dev, *guard);
        all_ok = board::final_gate_pass(all_ok, guard->restore_ok(), detail);
    } else {
        all_ok = false;
        detail += " (no_state_guard)";
    }

    // Summary: per-class match rate + confusion diagonal (diagnostic).
    std::size_t total_matched = 0, total_counted = 0;
    for (int c = 0; c < 12; ++c) {
        total_matched += static_cast<std::size_t>(matched[c]);
        total_counted += static_cast<std::size_t>(counted[c]);
    }
    detail += " total_matched=" + std::to_string(total_matched) + "/" +
              std::to_string(total_counted);
    if (total_counted > 0)
        detail += " total_rate=" +
                  std::to_string(static_cast<double>(total_matched) /
                                 static_cast<double>(total_counted));

    board::emit("gate10_selftest_12class", all_ok, detail);
    return all_ok ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();

    const std::string model_json = board::get_opt(argc, argv, "--model-json",
                                                  "model_12class/model_12class.json");
    const std::string model_raw = board::get_opt(argc, argv, "--model-raw",
                                                 "model_12class/model_12class.raw");
    const std::string sock_path = board::get_opt(argc, argv, "--sock", "");

    try {
        chain::NpuClassifier12 npu(model_json, model_raw);
        const cat::Contract contract = chain::contract_12();
        ui::StdoutSink out;
        ui::UnixSocketSink sock(sock_path);
        return run_selftest(npu, contract, out, sock, argc, argv);
    } catch (const std::exception& e) {
        board::emit("gate10_selftest_12class", false,
                    std::string("error=") + e.what());
        return 1;
    }
}
