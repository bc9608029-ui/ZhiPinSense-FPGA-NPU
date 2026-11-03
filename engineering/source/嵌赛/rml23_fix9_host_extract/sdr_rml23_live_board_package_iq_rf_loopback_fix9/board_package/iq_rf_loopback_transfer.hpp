#pragma once

// iq_rf_loopback_transfer.hpp -- Stage H-F / Route F: the per-file PHYSICAL-RF
// TX-off-negative-control -> load-verify -> external-RF-TX-start -> stale-RX-flush
// -> contiguous-capture transfer path, shared VERBATIM by the board runner and the
// host RF test (so the test exercises the exact code the board runs).
//
// Route F differences from the Route E digital transfer:
//   * loopback = 0 (external RF through the 50-ohm SMA coax), with
//     confirm_safe_rf_path = true -- PlutoTx::prepare() still fail-closes on a
//     loopback read-back mismatch and on the -40 dB ceiling, and the runner
//     additionally requires the read-back loopback == 0.
//   * a TX-OFF negative control is captured BEFORE any TX: dev.tx_stop() ->
//     recreate_rx_buffer() -> one contiguous noise-floor capture.  This proves the
//     RF path is quiet before TX and gives the noise floor for the SNR judgment.
//   * no test-fixture scale (the RF amplitude/phase correction is the ONE global
//     calibration gain in the runner, never a per-file scale).
//   * tx_dma_payload_ok compares the ACTUAL TX DMA payload SHA against the loaded
//     frozen-file SHA (identity under the board's 16-bit TX format; a host test
//     uses an identity fake format so the two match exactly).
//
// iCraft-free and libiio-free: depends only on pluto::Device / pluto::PlutoTx, the
// pure-logic halves (iq_digital_loopback.hpp + iq_rf_loopback.hpp), and the
// optional m22::StageTiming timers.

#include "iq_digital_loopback.hpp"
#include "iq_rf_loopback.hpp"
#include "board_common.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <utility>
#include <vector>

namespace iqrfloop_run {

// Length of ONE stale-flush discard refill (drained before capture).  fix9 Task F
// uses kRfDiscardRefills of these so the just-stopped TX's stale DMA is fully
// drained before the TX-off noise floor is measured.
constexpr std::size_t kRfDiscardComplex = 4096;
// fix9 Task F: number of independent discard (warm-up) refills and independent
// noise windows.  The task book requires >= 3 of each.
constexpr std::size_t kRfDiscardRefills = 3;
constexpr std::size_t kRfNoiseWindows = 3;
// Default TX-off noise-floor capture length.
constexpr std::size_t kRfNoiseComplexDefault = 4096;
// fix9 Task F: the independent TX-off noise windows are stable when the ratio of
// their largest RMS to their smallest RMS is at most this factor (max/min <= 3).
// An all-zero floor (max == 0) is stable.  A floor whose RMS moves by more than 3x
// between windows is not a stable reference for the SNR judgment, so the runner
// fail-closes with RF_NEGATIVE_CONTROL_UNSTABLE.
constexpr double kRfNoiseStableMaxRatio = 3.0;

struct RfTransferResult {
    std::vector<std::int16_t> tx;       // loaded frozen waveform
    std::vector<std::int16_t> rx;       // the ONE contiguous capture refill
    std::vector<std::int16_t> noise;    // TX-off negative-control capture
    iqdloop::TxVerify tx_verify;        // full-file SHA + non-zero evidence
    std::vector<iqdloop::RefillStat> refills;  // [discard, capture]
    board::RxStats st;
    board::Continuity cont;
    bool capture_ok = false;
    // fix8 Task B: TX-off negative control is now 3 INDEPENDENT noise windows (each
    // a fresh recreate + one contiguous refill).  `noise` keeps the median-RMS window
    // (the floor for the SNR judgment); the other two are released.  The discard
    // refill that drains the just-stopped TX's stale DMA is recorded separately and
    // NOT counted in the noise floor.
    iqdloop::RefillStat noise_discard;               // stale-DMA drain refill
    std::vector<double> noise_window_rms;            // 3 per-window RMS (counts)
    std::vector<board::Continuity> noise_window_cont;  // 3 per-window continuity
    double noise_rms_median = 0.0;
    double noise_rms_min = 0.0;
    double noise_rms_max = 0.0;
    bool noise_stable = false;                       // 3 windows not abnormally different
    bool tx_stopped_readback = false;                // tx_running() == false after tx_stop
    bool noise_capture_ok = false;                   // every window one contiguous refill
    double tx_atten_requested_db = 0.0;
    double tx_atten_readback_db = 0.0;
    int loopback_readback = -1;         // must be 0 in RF mode
    std::uint64_t tx_create_delta = 0;
    std::uint64_t tx_destroy_delta = 0;
    std::uint64_t rx_create_delta = 0;
    std::uint64_t rx_destroy_delta = 0;

    // fix5 parity: SHA of the ACTUAL TX DMA payload (post convert_inverse, pre push).
    // Recorded, NOT thrown: the runner gates on tx_dma_payload_ok.
    std::string tx_dma_payload_sha;
    bool tx_dma_payload_ok = false;

    // fix9 Task F: negative-control warm-up/retry evidence.  warmup_refills counts
    // the discard refills used to drain the just-stopped TX's stale DMA; retry is 1
    // when a first unstable round was re-warmed and re-tested; stability_ratio is
    // max/min (1.0 for an all-zero floor, +inf when min==0 && max>0).
    std::size_t warmup_refills = 0;
    int retry = 0;
    double noise_stability_ratio = 0.0;

    // fix9 Task D: TX-level scaling evidence (--rf-tx-target-rms=N, default no-op).
    // The loaded frozen bytes are verified, their native RMS/peak recorded, then
    // scaled toward target_rms ONLY when the predicted post-scale peak does not
    // clip.  tx_clip_post==true means scaling was refused (fail-closed: no silent
    // saturation); tx_sha_post is the SHA of the bytes actually pushed to DMA.
    double tx_target_rms = 0.0;        // 0.0 == no-op (no scaling)
    double tx_native_rms = 0.0;        // RMS of the loaded TX bytes (counts)
    double tx_scale = 1.0;             // applied scale (1.0 when no-op or refused)
    double tx_peak_pre = 0.0;          // |peak| of the loaded TX bytes (counts)
    double tx_peak_post = 0.0;         // predicted post-scale |peak|
    bool tx_clip_pre = false;          // loaded bytes already railed
    bool tx_clip_post = false;         // scaling refused because it would clip
    std::string tx_sha_pre;            // frozen SHA (pre-scale)
    std::string tx_sha_post;           // SHA of the bytes actually TX'd (post-scale)
};

// Load + verify the frozen bytes, capture the TX-off noise floor, TX the frozen
// bytes on the EXTERNAL RF path (loopback=0), flush the stale RX buffer, then
// capture one contiguous refill.  Throws (fail-closed) on a SHA mismatch / empty
// waveform, on a loopback read-back != 0, and on any PlutoTx safety refusal
// (unconfirmed external-RF path, -40 dB ceiling, read-back mismatch).
inline RfTransferResult transfer_one_file_rf(
    pluto::Device& dev, const std::string& path, std::uint64_t complex_count,
    const std::string& expect_sha, std::uint64_t center_hz, double rx_gain_db,
    double tx_atten_db, std::size_t delay_margin, std::uint64_t tx_complex_cap,
    std::size_t noise_complex, m22::StageTiming* timing = nullptr,
    const pluto::DataFormatInfo& tx_fmt = pluto::DataFormatInfo{},
    const pluto::DataFormatInfo& rx_fmt = pluto::DataFormatInfo{},
    double target_rms = 0.0) {
    RfTransferResult r;
    // RF has no test-fixture scale or format correction inside the transfer: the
    // device-level format override (if any) is applied by the runner before this
    // call, and the TX DMA payload comparison relies on the device's own effective
    // format.  Kept in the signature for parity with Route E's transfer_one_file.
    (void)tx_fmt;
    (void)rx_fmt;

    // ---- load + verify the FROZEN bytes, BEFORE any cap ----
    std::vector<std::int16_t> tx_iq = iqdloop::load_ci16(path, complex_count);
    r.tx_verify = iqdloop::verify_loaded_tx(tx_iq, expect_sha);
    if (tx_complex_cap > 0 && tx_complex_cap < complex_count)
        tx_iq.resize(static_cast<std::size_t>(tx_complex_cap) * 2);

    // ---- fix9 Task D: TX-level scaling to --rf-tx-target-rms (default no-op) ----
    // Read frozen -> verify SHA (done above) -> native RMS/peak -> scale -> predict
    // post peak -> scale ONLY if no clip -> post SHA.  No silent saturation: a
    // scaling that would clip is refused and recorded (tx_clip_post), so the runner
    // fail-closes the sample instead of emitting a saturated waveform.
    r.tx_target_rms = target_rms;
    r.tx_sha_pre = r.tx_verify.sha256;
    {
        double e = 0.0;
        int peak = 0;
        for (std::int16_t s : tx_iq) {
            e += static_cast<double>(s) * static_cast<double>(s);
            peak = std::max(peak, std::abs(static_cast<int>(s)));
        }
        r.tx_native_rms = tx_iq.empty()
            ? 0.0 : std::sqrt(e / static_cast<double>(tx_iq.size()));
        r.tx_peak_pre = static_cast<double>(peak);
        r.tx_clip_pre = (r.tx_peak_pre >= 32767.0);   // +32767 / -32768 = railed
        r.tx_peak_post = r.tx_peak_pre;
        if (target_rms > 0.0 && r.tx_native_rms > 0.0) {
            const double want = target_rms / r.tx_native_rms;
            r.tx_peak_post = r.tx_peak_pre * want;
            r.tx_clip_post = (r.tx_peak_post >= 32767.0);
            if (!r.tx_clip_post) {
                r.tx_scale = want;
                for (std::size_t k = 0; k < tx_iq.size(); ++k) {
                    const double v = std::llround(
                        static_cast<double>(tx_iq[k]) * r.tx_scale);
                    tx_iq[k] = static_cast<std::int16_t>(
                        std::max(-32768.0, std::min(32767.0, v)));
                }
            }
            // else: scaling refused -- leave bytes untouched, keep scale=1.0, and
            // the runner fail-closes on tx_clip_post.
        }
        r.tx_sha_post = sdr::Sha256::hex(tx_iq.data(),
                                         tx_iq.size() * sizeof(std::int16_t));
    }
    r.tx = tx_iq;

    const std::uint64_t txc0 = dev.tx_buffer_create_count();
    const std::uint64_t txd0 = dev.tx_buffer_destroy_count();
    const std::uint64_t rxc0 = dev.rx_buffer_create_count();
    const std::uint64_t rxd0 = dev.rx_buffer_destroy_count();

    // ---- TX-off negative control (noise floor) BEFORE any TX ----
    // fix9 Task F: stop TX, CONFIRM it stopped, drain the just-stopped TX's stale
    // DMA with >=3 discard (warm-up) refills (NOT part of the noise floor), then
    // capture >=3 independent noise windows.  The median-RMS window is the floor for
    // the SNR judgment; stability is max/min <= kRfNoiseStableMaxRatio.  A first
    // abnormal round is re-warmed and re-tested once; a still-abnormal floor makes
    // the runner fail-closed with RF_NEGATIVE_CONTROL_UNSTABLE.
    dev.tx_stop();
    r.tx_stopped_readback = !dev.tx_running();

    // One warm-up + measure round: >=3 discard refills then >=3 noise windows.  The
    // discard refills drain the stale DMA left by the just-stopped TX (and the
    // previous file) so it can never read as "noise".
    const auto run_noise_round = [&](std::size_t warmup) {
        r.warmup_refills += warmup;
        std::vector<std::int16_t> all_discard;
        for (std::size_t d = 0; d < warmup; ++d) {
            dev.recreate_rx_buffer();
            const iio::RawChunk c = dev.read_rx(kRfDiscardComplex, 1000);
            if (!c.broken && c.samples_available > 0)
                all_discard.insert(all_discard.end(), c.samples,
                                   c.samples + c.samples_available * 2);
        }
        r.noise_discard = iqdloop::measure_refill(all_discard, "noise_discard");

        std::vector<std::vector<std::int16_t>> windows(kRfNoiseWindows);
        r.noise_window_rms.assign(kRfNoiseWindows, 0.0);
        r.noise_window_cont.resize(kRfNoiseWindows);
        bool all_ok = true;
        for (std::size_t w = 0; w < kRfNoiseWindows; ++w) {
            dev.recreate_rx_buffer();
            board::RxStats st;
            board::Continuity cont;
            const bool raw_ok =
                board::capture_contiguous(dev, noise_complex, windows[w], st, cont);
            r.noise_window_cont[w] = cont;
            if (!(raw_ok && cont.ok())) all_ok = false;
            // RMS of the interleaved int16 window (counts) -- the same statistic the
            // SNR judgment compares against the signal RMS.
            double e = 0.0;
            for (std::int16_t s : windows[w])
                e += static_cast<double>(s) * static_cast<double>(s);
            r.noise_window_rms[w] = windows[w].empty()
                ? 0.0 : std::sqrt(e / static_cast<double>(windows[w].size()));
        }
        r.noise_capture_ok = all_ok;

        // Median-RMS window is the noise floor; the max/min ratio decides stability.
        std::vector<std::size_t> order(kRfNoiseWindows);
        for (std::size_t i = 0; i < order.size(); ++i) order[i] = i;
        std::sort(order.begin(), order.end(), [&](std::size_t a, std::size_t b) {
            return r.noise_window_rms[a] < r.noise_window_rms[b];
        });
        r.noise_rms_min = r.noise_window_rms[order.front()];
        r.noise_rms_median = r.noise_window_rms[order[order.size() / 2]];
        r.noise_rms_max = r.noise_window_rms[order.back()];
        r.noise_stability_ratio = (r.noise_rms_min > 0.0)
            ? (r.noise_rms_max / r.noise_rms_min)
            : (r.noise_rms_max > 0.0) ? 1.0e18 : 1.0;
        r.noise_stable = (r.noise_rms_max == 0.0) ||
                         (r.noise_stability_ratio <= kRfNoiseStableMaxRatio);
        r.noise = std::move(windows[order[order.size() / 2]]);   // median-RMS floor
    };

    run_noise_round(kRfDiscardRefills);

    // Re-warm and re-test once when the first round is abnormal (the first-TX-off
    // transient can outlive a single flush).
    if (!r.noise_stable) {
        r.retry = 1;
        dev.tx_stop();
        r.tx_stopped_readback = !dev.tx_running();
        run_noise_round(kRfDiscardRefills);
    }

    {
        pluto::TxConfig txc;
        txc.center_freq_hz = center_hz;
        txc.rx_gain_db = rx_gain_db;
        txc.tx_atten_db = tx_atten_db;
        txc.loopback = 0;                    // EXTERNAL RF (off), not digital
        txc.confirm_safe_rf_path = true;     // explicit 50-ohm coax confirmation
        txc.waveform = tx_iq;
        pluto::PlutoTx tx(dev, txc);

        // prepare(): tx_stop -> safe atten (read-back) -> manual RX gain -> align LO
        // -> set_loopback(0) (read-back) -> ramp to working atten (<= -40 dB).  Any
        // read-back mismatch / ceiling / unconfirmed-RF path throws here.
        if (timing) {
            m22::StageTiming::Timer rf_t(*timing, m22::StageId::RfConfig);
            tx.prepare();
        } else {
            tx.prepare();
        }
        r.tx_atten_requested_db = tx_atten_db;
        r.tx_atten_readback_db = dev.get_tx_atten();
        r.loopback_readback = dev.get_loopback();
        // The external-RF path MUST have the digital loopback off.  prepare() already
        // enforces set_loopback(0)==0, but re-verify the read-back explicitly so a
        // device that silently ignores the write cannot emit on the digital path.
        if (r.loopback_readback != 0)
            throw std::runtime_error(
                "iq-rf-loopback: loopback read-back != 0 (got " +
                std::to_string(r.loopback_readback) + ", want 0) -- external RF "
                "requires the internal digital loopback OFF");

        tx.start_cyclic();

        // ---- TX DMA payload verify (fix5 parity; fix9 Task D compares against the
        //      post-scale SHA, which equals the frozen SHA when no scaling) ----
        r.tx_dma_payload_sha = dev.tx_dma_payload_sha();
        r.tx_dma_payload_ok = (!r.tx_dma_payload_sha.empty() &&
                               r.tx_dma_payload_sha == r.tx_sha_post);

        // ---- stale-buffer flush: recreate + ONE discard refill ----
        dev.recreate_rx_buffer();
        {
            const iio::RawChunk c = dev.read_rx(kRfDiscardComplex, 1000);
            std::vector<std::int16_t> discard;
            if (!c.broken && c.samples_available > 0)
                discard.assign(c.samples, c.samples + c.samples_available * 2);
            r.refills.push_back(iqdloop::measure_refill(discard, "discard"));
        }

        // capture >= 2 * TX period + delay margin (full-period FFT circular sync).
        const std::size_t capture = 2 * (tx_iq.size() / 2) + delay_margin;
        {
            if (timing) {
                m22::StageTiming::Timer t(*timing, m22::StageId::RxRefill);
                const bool raw_ok =
                    board::capture_contiguous(dev, capture, r.rx, r.st, r.cont);
                r.capture_ok = raw_ok && r.cont.ok();
            } else {
                const bool raw_ok =
                    board::capture_contiguous(dev, capture, r.rx, r.st, r.cont);
                r.capture_ok = raw_ok && r.cont.ok();
            }
        }
        r.refills.push_back(iqdloop::measure_refill(r.rx, "capture"));
        // (PlutoTx destructor destroys the TX buffer + stops TX here, on every path.)
    }

    r.tx_create_delta = dev.tx_buffer_create_count() - txc0;
    r.tx_destroy_delta = dev.tx_buffer_destroy_count() - txd0;
    r.rx_create_delta = dev.rx_buffer_create_count() - rxc0;
    r.rx_destroy_delta = dev.rx_buffer_destroy_count() - rxd0;
    return r;
}

}  // namespace iqrfloop_run
