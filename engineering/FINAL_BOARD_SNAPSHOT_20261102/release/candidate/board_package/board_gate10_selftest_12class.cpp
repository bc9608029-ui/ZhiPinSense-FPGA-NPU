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
// M17 (task 39e5): three board-side defects fixed here.
//   (A) The M15 settle-frame capture-and-discard path collapsed OOK (default
//       --settle-frames=2 -> OOK 0/20, most predicted AM-DSB).  That path is
//       DELETED.  The only settle policy is TIME_ONLY (wait --settle-wait-ms for
//       the analog/RF settle, no frame discard): the official capture is sized
//       exactly to required_input(frames).  A non-zero --settle-frames is
//       rejected fail-closed (gate10_settle.hpp parse_settle_config).
//   (B) The TX/RX buffer-lifecycle deltas were read BEFORE the PlutoTx RAII
//       destructor, so tx_destroy_delta was always 0.  Deltas are now taken
//       AFTER the destructor AND after the class-end RX buffer recreate, so each
//       class provably reports tx_create=1/tx_destroy=1/tx_live=0 and rx_live=0.
//   (C) --dump-error-class selects a single target class (or all); the dump
//       manifest is enriched (frame indices, CRC32s, confidence, model/bitstream
//       SHA) and a SHA256SUMS sidecar fingerprints manifest.tsv + every .bin.
//
// Exit 0/1/2 = pass / fail / device-not-found.  Board-only (iCraft + libiio);
// the waveform builder + upsampler are host-tested in test_rf_waveform_12class.cpp
// and the settle/lifecycle/dump logic in test_gate10_settle.cpp.

#include "board_common.hpp"
#include "chain_common.hpp"
#include "gate10_settle.hpp"
#include "npu_classifier.hpp"
#include "unix_socket_sink.hpp"
#include "../sdr_adapter/rf_waveform_12class.hpp"
#include "../sdr_adapter/crc32.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <sys/stat.h>
#include <sys/types.h>

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

// Sleep in 10 ms slices so a pending SIGINT/SIGTERM can cut the wait short.
void settle_wait(std::uint64_t ms) {
    const auto deadline = Clock::now() + std::chrono::milliseconds(ms);
    while (Clock::now() < deadline && !board::g_stop_requested)
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
}

std::string hex64(std::uint64_t v) {
    char buf[24];
    std::snprintf(buf, sizeof buf, "0x%llx", static_cast<unsigned long long>(v));
    return buf;
}

std::string hex32(std::uint32_t v) {
    char buf[16];
    std::snprintf(buf, sizeof buf, "%08x", static_cast<unsigned int>(v));
    return buf;
}

std::string join_ints(const std::vector<int>& v) {
    std::string s;
    for (std::size_t i = 0; i < v.size(); ++i) {
        if (i) s += ",";
        s += std::to_string(v[i]);
    }
    return s;
}

// ---- 64QAM / general precision diagnosis dump (M15 新增项1 -> M17 Task C) ----
// A misclassified frame's MODEL-DOMAIN input tensor (the exact 2048 fp32 the NPU
// saw, AFTER receiver_scale) + the board-NPU's 12 logits are saved so the failure
// can be re-run on the host in three ways -- ONNX fp32 (ground-truth intent),
// icraft-run --fake_qf (the vendor int8 quantization, Host backend), and the
// board NPU -- and the three argmaxes compared (host_tools/compare_64qam_threeway.py).
// The dump NEVER changes --min-match-rate and never picks a seed: it only records
// evidence from the frames the gate actually ran.  A write failure fails closed.
//
// M17 Task C: the dump is now TARGET-CLASS selectable (--dump-error-class) with a
// per-target-class quota, the manifest is enriched with frame indices / CRC32s /
// confidence / model & bitstream SHA, and finalize() writes a SHA256SUMS sidecar.
bool ensure_dir(const std::string& dir) {
    if (dir.empty()) return false;
    struct stat st{};
    if (::stat(dir.c_str(), &st) == 0) return S_ISDIR(st.st_mode);
    return ::mkdir(dir.c_str(), 0755) == 0;
}

struct ErrorDump {
    std::string dir;
    std::uint64_t max_samples = 0;   // per-target-class quota
    bool ok = true;
    gate10::ErrorClassFilter filter;
    std::string model_sha;
    std::string bitstream_sha;
    std::uint64_t written = 0;                 // global sequence (file naming)
    std::uint64_t per_class_written[12] = {0};

    bool enabled() const { return max_samples > 0 && !dir.empty(); }

    static std::string dash(const std::string& s) { return s.empty() ? "-" : s; }

    // Create the directory (if absent) and write the enriched manifest header once.
    bool init() {
        if (!enabled()) return true;
        if (!ensure_dir(dir)) { ok = false; return false; }
        char p[1024];
        std::snprintf(p, sizeof p, "%s/manifest.tsv", dir.c_str());
        FILE* f = std::fopen(p, "w");
        if (!f) { ok = false; return false; }
        std::fprintf(f, "seq\texpected_class\texpected_label\tpredicted_class"
                        "\tpredicted_label\tclass_frame_index\tglobal_frame_index"
                        "\tseed\ttx_waveform_crc32\tofficial_rx_crc32"
                        "\tmodel_tensor_crc32\tconfidence\tmodel_sha\tbitstream_sha");
        for (int i = 0; i < 12; ++i) std::fprintf(f, "\tlogit_%d", i);
        std::fprintf(f, "\n");
        std::fclose(f);
        return true;
    }

    // Save one misclassified frame (binary tensor + one enriched manifest row).
    bool save(const cat::Contract& contract, int ref, int pred, const float* tensor,
              const std::vector<float>& logits, std::uint64_t seed,
              std::uint32_t tx_crc, std::uint32_t rx_crc,
              std::uint64_t class_frame_index, std::uint64_t global_frame_index) {
        if (!ok) return false;
        const std::size_t seq = written;

        // Exact model-domain tensor CRC32 + softmax confidence (from raw logits).
        const std::uint32_t tensor_crc = sdr::crc32_bytes(
            reinterpret_cast<const std::uint8_t*>(tensor), chain::kTensorBytes);
        float confidence = 0.0f;
        {
            const std::vector<float> probs = classify::softmax(logits);
            for (float p : probs)
                if (p > confidence) confidence = p;
        }

        char bp[1024];
        std::snprintf(bp, sizeof bp, "%s/error_%03zu.bin", dir.c_str(), seq);
        FILE* bf = std::fopen(bp, "wb");
        if (!bf) { ok = false; return false; }
        const std::size_t n = std::fwrite(tensor, sizeof(float), chain::kTensorFloats, bf);
        std::fclose(bf);
        if (n != chain::kTensorFloats) { ok = false; return false; }

        char mp[1024];
        std::snprintf(mp, sizeof mp, "%s/manifest.tsv", dir.c_str());
        FILE* mf = std::fopen(mp, "a");
        if (!mf) { ok = false; return false; }
        std::fprintf(mf, "%zu\t%d\t%s\t%d\t%s\t%llu\t%llu\t%llu\t%08x\t%08x\t%08x"
                         "\t%.9g\t%s\t%s",
                     seq, ref, cat::label(contract, ref).c_str(),
                     pred, cat::label(contract, pred).c_str(),
                     static_cast<unsigned long long>(class_frame_index),
                     static_cast<unsigned long long>(global_frame_index),
                     static_cast<unsigned long long>(seed),
                     tx_crc, rx_crc, tensor_crc, confidence,
                     dash(model_sha).c_str(), dash(bitstream_sha).c_str());
        for (float v : logits) std::fprintf(mf, "\t%.9g", v);
        std::fprintf(mf, "\n");
        std::fclose(mf);

        ++written;
        ++per_class_written[static_cast<std::size_t>(ref)];
        return true;
    }

    // Write a SHA256SUMS sidecar fingerprinting manifest.tsv + every error_*.bin,
    // so the dump can be audited off-line for exactly which frames were captured.
    bool finalize() {
        if (!enabled()) return true;
        char mp[1024];
        std::snprintf(mp, sizeof mp, "%s/manifest.tsv", dir.c_str());
        char sp[1024];
        std::snprintf(sp, sizeof sp, "%s/SHA256SUMS", dir.c_str());
        FILE* f = std::fopen(sp, "w");
        if (!f) { ok = false; return false; }

        bool file_ok = true;
        const std::string msha = sdr::sha256_hex_file(mp, &file_ok);
        if (!file_ok) { ok = false; std::fclose(f); return false; }
        std::fprintf(f, "%s  manifest.tsv\n", msha.c_str());
        for (std::uint64_t i = 0; i < written; ++i) {
            char bp[1024];
            std::snprintf(bp, sizeof bp, "%s/error_%03llu.bin", dir.c_str(),
                          static_cast<unsigned long long>(i));
            const std::string h = sdr::sha256_hex_file(bp, &file_ok);
            if (!file_ok) { ok = false; std::fclose(f); return false; }
            std::fprintf(f, "%s  error_%03llu.bin\n", h.c_str(),
                          static_cast<unsigned long long>(i));
        }
        std::fclose(f);
        return true;
    }
};

int run_selftest(chain::NpuClassifier12& npu, const cat::Contract& contract,
                 ui::StdoutSink& out, ui::UnixSocketSink& sock,
                 int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const int loopback = (board::get_opt(argc, argv, "--loopback", "digital") == "rf") ? 0 : 1;
    const bool confirm_rf = board::has_flag(argc, argv, "--confirm-safe-rf-path");
    const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 20);
    const std::uint64_t tx_frames = board::opt_u64(argc, argv, "--tx-frames", 64);
    const std::uint64_t settle_frames = board::opt_u64(argc, argv, "--settle-frames", 0);
    const std::uint64_t settle_wait_ms = board::opt_u64(argc, argv, "--settle-wait-ms", 100);
    const double min_match = board::opt_d(argc, argv, "--min-match-rate", 0.90);
    const double peak_limit = board::opt_d(argc, argv, "--peak-limit", 1638.0);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const std::uint64_t seed = board::opt_u64(argc, argv, "--seed", 0x39e50001ULL);
    const std::uint64_t center = board::opt_u64(argc, argv, "--center", 2450000000ULL);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string bitstream_sha = board::get_opt(argc, argv, "--bitstream-sha", "");
    const std::uint64_t dump_samples = board::opt_u64(argc, argv, "--dump-error-samples", 0);
    const std::string dump_dir = board::get_opt(argc, argv, "--dump-dir", "");
    const std::string dump_class_opt = board::get_opt(argc, argv, "--dump-error-class", "all");

    // M17 (A): settle policy.  Non-zero --settle-frames fails closed (the old
    // capture-and-discard T1 path is deleted, never silently ignored).
    gate10::SettleConfig settle_cfg;
    {
        std::string settle_err;
        if (!gate10::parse_settle_config(settle_frames, settle_wait_ms,
                                         settle_cfg, settle_err)) {
            board::emit("gate10_selftest_12class", false, "error=" + settle_err);
            return 1;
        }
    }

    // M17 (C): --dump-error-class target filter.
    gate10::ErrorClassFilter dump_filter;
    {
        std::string fe;
        if (!dump_filter.parse(dump_class_opt, fe)) {
            board::emit("gate10_selftest_12class", false, "error=" + fe);
            return 1;
        }
    }

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
    std::size_t total_valid = 0;
    ErrorDump dump;
    dump.dir = dump_dir;
    dump.max_samples = dump_samples;
    dump.filter = dump_filter;
    dump.model_sha = model_sha;
    dump.bitstream_sha = bitstream_sha;

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

            // Prepare the diagnosis dump directory + manifest (no-op unless
            // --dump-error-samples=N --dump-dir=DIR).  A failed init is fail-closed.
            if (!dump.init()) {
                all_classes_ok = false;
                detail += " (dump_init_failed)";
            }

            auto snap = [&dev]() {
                gate10::BufferCounts b;
                b.tx_create = dev->tx_buffer_create_count();
                b.tx_destroy = dev->tx_buffer_destroy_count();
                b.rx_create = dev->rx_buffer_create_count();
                b.rx_destroy = dev->rx_buffer_destroy_count();
                b.rx_refill = dev->rx_refill_count();
                return b;
            };

            for (int c : classes) {
                if (board::g_stop_requested) break;

                // (A) stop + destroy any previous cyclic TX buffer (defensive: the
                // prior class's RAII PlutoTx already destroyed it), then WAIT for
                // the analog/RF flush before building the next class's buffer.
                dev->tx_stop();
                settle_wait(settle_cfg.settle_wait_ms);

                // 1. Build the cyclic TX waveform for this class (deterministic).
                std::vector<std::int16_t> waveform;
                double tx_peak = 0.0, tx_rms = 0.0;
                sdr::build_tx_waveform(c, seed, static_cast<std::size_t>(tx_frames),
                                       peak_limit, waveform, &tx_peak, &tx_rms);
                const std::uint32_t tx_crc = sdr::crc32_i16(waveform);

                std::printf("SELFTEST_CLASS_BEGIN class=%d name=%s seed=%llu "
                            "seed_hex=%s tx_waveform_crc32=%s tx_peak=%.6f tx_rms=%.6f "
                            "settle_policy=%s\n",
                            c, cat::label(contract, c).c_str(),
                            static_cast<unsigned long long>(seed),
                            hex64(seed).c_str(), hex32(tx_crc).c_str(),
                            tx_peak, tx_rms,
                            gate10::settle_policy_name(settle_cfg.policy));
                std::fflush(stdout);

                const gate10::BufferCounts before = snap();
                gate10::BufferCounts settle_snap;
                bool class_pass = false;
                std::string cd;
                gate10::SettleStats settle_stats;
                gate10::LifecycleDeltas lc;
                std::size_t produced = 0, valid = 0;
                int class_matched = 0;
                double rms_mean = 0.0;
                double classify_us_sum = 0.0;
                std::vector<int> pred_hist(12, 0);
                std::vector<int> first_preds;
                std::uint32_t rx_crc = 0;

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
                    tx.start_cyclic();     // create + push the new cyclic buffer

                    // (A) TIME_ONLY: let the new class reach steady state on the
                    // wire.  No frame warmup / discard (the M15 T1 path is gone).
                    settle_wait(settle_cfg.settle_wait_ms);
                    settle_snap = snap();   // end-of-settle / pre-capture boundary

                    // 3. ONE contiguous RX capture sized for the OFFICIAL frames
                    //    only (required_input(frames); no settle-frame discard).
                    chain::PreprocessChain chain_meas(fs_in, 0.0, 1.0f);
                    const std::size_t requested =
                        chain_meas.required_input(static_cast<std::size_t>(frames));
                    std::vector<std::int16_t> iq;
                    board::RxStats st;
                    board::Continuity cont;
                    const bool captured =
                        board::capture_contiguous(*dev, requested, iq, st, cont);
                    rx_crc = sdr::crc32_i16(iq);

                    if (captured && !st.interrupted && iq.size() / 2 > 0) {
                        std::vector<float> tensor(chain::kTensorFloats);

                        // 4a. Measure reconstructed RMS (receiver_scale == 1.0)
                        //     over the official frames (no settle discard).
                        chain_meas.push_int16(iq.data(), iq.size() / 2);
                        double rms_sum = 0.0;
                        std::size_t rms_n = 0;
                        while (chain_meas.ready() > 0 &&
                               rms_n < static_cast<std::size_t>(frames)) {
                            if (!chain_meas.pull_tensor(tensor.data())) break;
                            rms_sum += tensor_rms(tensor.data());
                            ++rms_n;
                        }
                        rms_mean = rms_n ? rms_sum / static_cast<double>(rms_n) : 0.0;
                        const float rec_scale =
                            (rms_mean > 1e-9)
                                ? static_cast<float>(1.0 / rms_mean)
                                : 1.0f;

                        // 4b. Classify the official frames with the derived
                        //     receiver_scale (no settle discard).
                        chain::PreprocessChain chain(fs_in, 0.0, rec_scale);
                        chain.push_int16(iq.data(), iq.size() / 2);
                        while (chain.ready() > 0 &&
                               produced < static_cast<std::size_t>(frames)) {
                            if (!chain.pull_tensor(tensor.data())) break;
                            ++produced;
                            const std::uint64_t class_frame_idx = produced - 1;

                            const auto t0 = Clock::now();
                            const std::vector<float> logits = npu.infer(tensor.data());
                            const auto t1 = Clock::now();
                            classify_us_sum += static_cast<double>(
                                std::chrono::duration_cast<std::chrono::microseconds>(
                                    t1 - t0).count());

                            const int pred = argmax_of(logits);
                            if (pred >= 0 && pred < 12) {
                                confusion[c][pred]++;
                                pred_hist[static_cast<std::size_t>(pred)]++;
                            }
                            if (pred == c) ++class_matched;
                            if (first_preds.size() < 3) first_preds.push_back(pred);

                            const std::uint64_t gfi = ++frame_counter;

                            // (C) save misclassified frames (per-target-class quota)
                            // so the board NPU result can be re-run on the host.
                            if (dump.enabled() && pred != c &&
                                dump.filter.matches(c) &&
                                dump.per_class_written[static_cast<std::size_t>(c)] <
                                    dump.max_samples) {
                                if (dump.save(contract, c, pred, tensor.data(), logits,
                                              seed, tx_crc, rx_crc, class_frame_idx,
                                              gfi)) {
                                    std::printf("SELFTEST_DUMP_ERROR seq=%llu class=%d "
                                                "ref=%d pred=%d file=error_%03llu.bin\n",
                                                static_cast<unsigned long long>(dump.written - 1),
                                                c, c, pred,
                                                static_cast<unsigned long long>(dump.written - 1));
                                    std::fflush(stdout);
                                }
                            }

                            rf::ResultFrame r;
                            r.frame_id = gfi;
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
                    total_valid += valid;
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

                    // M17 (A4): settle / official-capture stats.
                    settle_stats.policy =
                        gate10::settle_policy_name(settle_cfg.policy);
                    settle_stats.settle_wait_ms = settle_cfg.settle_wait_ms;
                    settle_stats.settle_frames_requested = settle_cfg.settle_frames;
                    settle_stats.settle_capture_samples = 0;   // TIME_ONLY
                    settle_stats.settle_refill_count = 0;      // TIME_ONLY
                    settle_stats.official_requested_input_complex =
                        static_cast<std::uint64_t>(requested);
                    settle_stats.official_frames = frames;
                    settle_stats.official_refill_count = cont.refill_delta;
                    settle_stats.official_single_refill = cont.single_refill ? 1 : 0;

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
                    cd += " tx_waveform_crc32=" + hex32(tx_crc);
                    cd += " official_rx_crc32=" + hex32(rx_crc);
                    cd += settle_stats.report();
                    cd += " prediction_hist=" + join_ints(pred_hist);
                    cd += " first_predictions=" + join_ints(first_preds);
                    if (!captured) cd += " (capture_failed)";
                    if (!cont.ok()) cd += " (continuity_fail)";
                    if (!frames_ok) cd += " (frame_short)";
                    if (!rf_ok) cd += " (rf_unconfirmed)";
                    if (valid != produced) cd += " (invalid_frames)";
                    if (st.interrupted) cd += " (interrupted)";
                    if (rate < min_match) cd += " (match_below_threshold)";
                }
                // The PlutoTx destructor ran here: the TX buffer was destroyed.

                // M17 (B): destroy the official RX buffer at class end (RX live ->
                // 0), THEN snapshot -- so every create is matched by a destroy and
                // the deltas prove tx_create=1/tx_destroy=1/tx_live=0, rx_live=0.
                dev->recreate_rx_buffer();
                const gate10::BufferCounts after = snap();
                lc = gate10::compute_lifecycle(before, settle_snap, after);
                cd += lc.report();

                std::printf("SELFTEST_CLASS_END class=%d name=%s%s\n",
                            c, cat::label(contract, c).c_str(), cd.c_str());
                std::fflush(stdout);

                detail += cd;
                if (!class_pass) all_classes_ok = false;
            }

            // M17 (C): finalize the dump (SHA256SUMS sidecar).  Fail-closed.
            if (dump.enabled() && !dump.finalize()) {
                all_classes_ok = false;
                detail += " (dump_finalize_failed)";
            }

            all_ok = all_classes_ok && !classes.empty();
            if (dump.enabled() && !dump.ok) {
                all_ok = false;
                detail += " (dump_error)";
            }
            detail += " dump_error_samples=" + std::to_string(dump.written);
            detail += " dump_error_class=" + dump_class_opt;
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
    detail += " classes=" + std::to_string(classes.size());
    detail += " total_matched=" + std::to_string(total_matched) + "/" +
              std::to_string(total_counted);
    detail += " total_valid=" + std::to_string(total_valid);
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
