#pragma once

// iq_rf_loopback_transfer_fix9r.hpp -- Route F fix9r Task D: the per-file
// TRAINING-FRAME physical-RF transfer.  fix9 TX'd the RAW D2 payload ci16 and
// left the receiver to undo the RF path with ONE global complex gain (which fails
// because the TX LO phase re-keys per tx_start_cyclic).  fix9r instead brackets the
// payload with the known Zadoff-Chu training frame (iq_rf_training_frame.hpp) and
// TX's that burst, so the receiver can recover gain/phase/timing/CFO/SRO/phase-
// drift PER FILE from the known preamble (iq_rf_per_frame_recovery.hpp) -- never
// from the payload label or a payload best-fit (§7 leak ban).
//
// This is a NEW file: the fix9 transfer (iq_rf_loopback_transfer.hpp) and the fix9
// RF path (iq_rf_loopback.hpp) are RED-LINE and untouched; the training-frame
// transfer reuses only their public constants (iqrfloop_run::kRfDiscardComplex /
// kRfDiscardRefills / kRfNoiseWindows / kRfNoiseStableMaxRatio) and mirrors the
// TX-off negative-control sequence exactly.
//
// iCraft-free and libiio-free: it compiles identically on the host (with
// FakePlutoDevice) and the board (with a real Pluto).

#include "iq_digital_loopback.hpp"        // iqdloop::load_ci16 / verify_loaded_tx / measure_refill
#include "iq_rf_loopback_transfer.hpp"    // iqrfloop_run::kRfDiscard* / kRfNoise* (reuse only)
#include "iq_rf_training_frame.hpp"       // iqrftrain::build_burst / kTotalBurstComplex
#include "iq_rf_frame_layout.hpp"         // iqrflayout::capture_complex (>=2 periods)
#include "iq_rf_tx_provenance.hpp"        // iqrftxprov::fingerprint / verify_frame (R1/R2)
#include "board_common.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace iqrfloop_run_fix9r {

// Capture margin past TWO full bursts: the receiver searches the WHOLE capture for
// the preamble (fix9r2 full-capture search -- no 4096 bound), and the capture holds
// >= 2 periods (iqrflayout::capture_complex) so a complete [preamble..tail] burst
// fits for ANY cyclic TX start phase, plus the trailing tail.
constexpr std::size_t kFix9rDelayMarginDefault = 8192;

struct RfTransferResultFix9r {
    std::vector<std::int16_t> payload;   // loaded frozen payload (post target_rms scale)
    std::vector<std::int16_t> tx;        // the TX burst: [preamble][guard][payload][guard][tail]
    std::vector<std::int16_t> rx;        // the ONE contiguous capture refill
    std::vector<std::int16_t> noise;     // TX-off negative-control capture (median RMS)
    iqdloop::TxVerify tx_verify;         // payload SHA + non-zero evidence
    std::vector<iqdloop::RefillStat> refills;  // [discard, capture]
    board::RxStats st;
    board::Continuity cont;
    bool capture_ok = false;

    iqdloop::RefillStat noise_discard;
    std::vector<double> noise_window_rms;
    std::vector<board::Continuity> noise_window_cont;
    double noise_rms_median = 0.0;
    double noise_rms_min = 0.0;
    double noise_rms_max = 0.0;
    bool noise_stable = false;
    bool tx_stopped_readback = false;
    bool noise_capture_ok = false;
    double tx_atten_requested_db = 0.0;
    double tx_atten_readback_db = 0.0;
    int loopback_readback = -1;          // must be 0 in RF mode

    // fix9r2g: RX gain-mode endpoint read-back (pure reads, LOG-ONLY -- no gate, no
    // version, no throw).  Read once before and once after the main capture so the
    // audit can see whether the gain/mode changed across the burst.
    std::string rx_gain_mode_before_capture;
    double rx_gain_before_capture = 0.0;
    std::string rx_gain_mode_after_capture;
    double rx_gain_after_capture = 0.0;
    std::uint64_t tx_create_delta = 0;
    std::uint64_t tx_destroy_delta = 0;
    std::uint64_t rx_create_delta = 0;
    std::uint64_t rx_destroy_delta = 0;

    // SHA of the ACTUAL TX DMA payload (the burst), compared against burst_sha.
    std::string tx_dma_payload_sha;
    bool tx_dma_payload_ok = false;

    // fix9r2 Task R1/R2: byte-level TX provenance + independent frame verifier +
    // the iio_buffer_push byte provenance.
    iqrftxprov::TxByteProvenance tx_provenance;
    iqrftxprov::TxFrameVerify frame_verify;
    pluto::TxPushProvenance tx_push;

    std::size_t warmup_refills = 0;
    int retry = 0;
    double noise_stability_ratio = 0.0;

    // TX-level scaling evidence (--rf-tx-target-rms=N, applied to the PAYLOAD only;
    // the preamble/tail stay at the fixed kTrainAmp == 2048 so the LS gain from the
    // preamble is the true per-file RF gain).
    double tx_target_rms = 0.0;
    double tx_native_rms = 0.0;
    double tx_scale = 1.0;
    double tx_peak_pre = 0.0;
    double tx_peak_post = 0.0;
    bool tx_clip_pre = false;
    bool tx_clip_post = false;
    std::string tx_sha_pre;              // frozen payload SHA (pre-scale)
    std::string tx_sha_post;             // payload SHA post-scale
    std::string burst_sha;               // SHA of the full burst actually TX'd
};

// Load + verify the frozen payload, build the training-frame burst, capture the
// TX-off noise floor, TX the burst on the EXTERNAL RF path (loopback=0), flush the
// stale RX buffer, then capture burst+margin.  Throws (fail-closed) on a SHA
// mismatch / empty waveform, on a payload complex_count != kPayloadComplex, on a
// loopback read-back != 0, and on any PlutoTx safety refusal.
inline RfTransferResultFix9r transfer_one_file_rf_fix9r(
        pluto::Device& dev, const std::string& path, std::uint64_t complex_count,
        const std::string& expect_sha, std::uint64_t center_hz, double rx_gain_db,
        double tx_atten_db, std::size_t delay_margin, std::size_t noise_complex,
        m22::StageTiming* timing, double target_rms) {
    RfTransferResultFix9r r;
    if (complex_count != iqrftrain::kPayloadComplex)
        throw std::runtime_error(
            "iq-rf-loopback-23class-fix9r: payload complex_count " +
            std::to_string(complex_count) + " != training-frame kPayloadComplex " +
            std::to_string(iqrftrain::kPayloadComplex));

    // ---- load + verify the FROZEN payload bytes, BEFORE any cap ----
    std::vector<std::int16_t> payload_iq = iqdloop::load_ci16(path, complex_count);
    r.tx_verify = iqdloop::verify_loaded_tx(payload_iq, expect_sha);

    // ---- fix9 Task D parity: TX-level scaling to --rf-tx-target-rms (default
    //      2048, a no-op that VERIFIES the native RMS ~= 2048).  Applied to the
    //      payload only; the training frame keeps its fixed kTrainAmp. ----
    r.tx_target_rms = target_rms;
    r.tx_sha_pre = r.tx_verify.sha256;
    {
        double e = 0.0;
        int peak = 0;
        for (std::int16_t s : payload_iq) {
            e += static_cast<double>(s) * static_cast<double>(s);
            peak = std::max(peak, std::abs(static_cast<int>(s)));
        }
        r.tx_native_rms = payload_iq.empty()
            ? 0.0 : std::sqrt(e / static_cast<double>(payload_iq.size()));
        r.tx_peak_pre = static_cast<double>(peak);
        r.tx_clip_pre = (r.tx_peak_pre >= 32767.0);
        r.tx_peak_post = r.tx_peak_pre;
        if (target_rms > 0.0 && r.tx_native_rms > 0.0) {
            const double want = target_rms / r.tx_native_rms;
            r.tx_peak_post = r.tx_peak_pre * want;
            r.tx_clip_post = (r.tx_peak_post >= 32767.0);
            if (!r.tx_clip_post) {
                r.tx_scale = want;
                for (std::size_t k = 0; k < payload_iq.size(); ++k) {
                    const double v = std::llround(
                        static_cast<double>(payload_iq[k]) * r.tx_scale);
                    payload_iq[k] = static_cast<std::int16_t>(
                        std::max(-32768.0, std::min(32767.0, v)));
                }
            }
            // else: scaling refused -- leave bytes untouched, keep scale=1.0, and
            // the runner fail-closes on tx_clip_post.
        }
        r.tx_sha_post = sdr::Sha256::hex(payload_iq.data(),
                                         payload_iq.size() * sizeof(std::int16_t));
    }
    r.payload = payload_iq;

    // ---- build the training-frame burst (throws on any length mismatch) ----
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(payload_iq);
    r.tx = burst;
    r.burst_sha = sdr::Sha256::hex(burst.data(), burst.size() * sizeof(std::int16_t));

    // ---- fix9r2 Task R2: independent TX-frame verifier, fail-closed BEFORE any
    //      TX.  The builder and this verifier read the burst independently, so a
    //      framing/packing/order bug cannot be shared between them. ----
    r.frame_verify = iqrftxprov::verify_frame(burst, payload_iq);
    if (!r.frame_verify.ok)
        throw std::runtime_error(
            "iq-rf-loopback-23class-fix9r: TX frame verifier FAILED "
            "(training_exact_match=" +
            std::to_string(r.frame_verify.training_exact_match) +
            " payload_exact_match=" +
            std::to_string(r.frame_verify.payload_exact_match) +
            " frame_layout_match=" +
            std::to_string(r.frame_verify.frame_layout_match) + ")");

    const std::uint64_t txc0 = dev.tx_buffer_create_count();
    const std::uint64_t txd0 = dev.tx_buffer_destroy_count();
    const std::uint64_t rxc0 = dev.rx_buffer_create_count();
    const std::uint64_t rxd0 = dev.rx_buffer_destroy_count();

    // ---- TX-off negative control (noise floor) BEFORE any TX ----
    // Mirrors iqrfloop_run::transfer_one_file_rf exactly: stop TX, CONFIRM it
    // stopped, drain stale DMA with >=3 discard refills, then >=3 independent noise
    // windows; median-RMS window is the floor, stability is max/min <= 3.
    dev.tx_stop();
    r.tx_stopped_readback = !dev.tx_running();

    const auto run_noise_round = [&](std::size_t warmup) {
        r.warmup_refills += warmup;
        std::vector<std::int16_t> all_discard;
        for (std::size_t d = 0; d < warmup; ++d) {
            dev.recreate_rx_buffer();
            const iio::RawChunk c = dev.read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
            if (!c.broken && c.samples_available > 0)
                all_discard.insert(all_discard.end(), c.samples,
                                   c.samples + c.samples_available * 2);
        }
        r.noise_discard = iqdloop::measure_refill(all_discard, "noise_discard");

        std::vector<std::vector<std::int16_t>> windows(iqrfloop_run::kRfNoiseWindows);
        r.noise_window_rms.assign(iqrfloop_run::kRfNoiseWindows, 0.0);
        r.noise_window_cont.resize(iqrfloop_run::kRfNoiseWindows);
        bool all_ok = true;
        for (std::size_t w = 0; w < iqrfloop_run::kRfNoiseWindows; ++w) {
            dev.recreate_rx_buffer();
            board::RxStats st;
            board::Continuity cont;
            const bool raw_ok =
                board::capture_contiguous(dev, noise_complex, windows[w], st, cont);
            r.noise_window_cont[w] = cont;
            if (!(raw_ok && cont.ok())) all_ok = false;
            double e = 0.0;
            for (std::int16_t s : windows[w])
                e += static_cast<double>(s) * static_cast<double>(s);
            r.noise_window_rms[w] = windows[w].empty()
                ? 0.0 : std::sqrt(e / static_cast<double>(windows[w].size()));
        }
        r.noise_capture_ok = all_ok;

        std::vector<std::size_t> order(iqrfloop_run::kRfNoiseWindows);
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
                         (r.noise_stability_ratio <= iqrfloop_run::kRfNoiseStableMaxRatio);
        r.noise = std::move(windows[order[order.size() / 2]]);
    };

    run_noise_round(iqrfloop_run::kRfDiscardRefills);
    if (!r.noise_stable) {
        r.retry = 1;
        dev.tx_stop();
        r.tx_stopped_readback = !dev.tx_running();
        run_noise_round(iqrfloop_run::kRfDiscardRefills);
    }

    {
        pluto::TxConfig txc;
        txc.center_freq_hz = center_hz;
        txc.rx_gain_db = rx_gain_db;
        txc.tx_atten_db = tx_atten_db;
        txc.loopback = 0;                    // EXTERNAL RF (off), not digital
        txc.confirm_safe_rf_path = true;     // explicit 50-ohm coax confirmation
        txc.waveform = burst;
        pluto::PlutoTx tx(dev, txc);

        if (timing) {
            m22::StageTiming::Timer rf_t(*timing, m22::StageId::RfConfig);
            tx.prepare();
        } else {
            tx.prepare();
        }
        r.tx_atten_requested_db = tx_atten_db;
        r.tx_atten_readback_db = dev.get_tx_atten();
        r.loopback_readback = dev.get_loopback();
        if (r.loopback_readback != 0)
            throw std::runtime_error(
                "iq-rf-loopback-23class-fix9r: loopback read-back != 0 (got " +
                std::to_string(r.loopback_readback) + ", want 0) -- external RF "
                "requires the internal digital loopback OFF");

        tx.start_cyclic();

        // ---- fix9r2 Task R1: byte-level TX provenance (five stages) + push bytes.
        //      payload_source -> training_reference -> framed_logical_iq ->
        //      formatted_tx_container -> submitted_iio_buffer; the last two are the
        //      RAW container (host -> raw with the effective TX format), and the DMA
        //      SHA proves those exact bytes reached iio_buffer_push. ----
        r.tx_push = dev.tx_push_provenance();
        r.tx_provenance.payload_source = iqrftxprov::fingerprint(payload_iq);
        r.tx_provenance.training_reference =
            iqrftxprov::fingerprint(iqrftxprov::training_reference_iq());
        r.tx_provenance.framed_logical_iq = iqrftxprov::fingerprint(burst);
        {
            std::vector<std::int16_t> raw;
            dev.tx_raw_after_inverse(burst, raw);
            r.tx_provenance.formatted_tx_container = iqrftxprov::fingerprint(raw);
            r.tx_provenance.formatted_tx_container.format_desc =
                pluto::describe_data_format(dev.tx_data_format());
            // the submitted buffer is the SAME raw bytes; override only the SHA with
            // the DMA read-back so the audit can compare them.
            r.tx_provenance.submitted_iio_buffer =
                r.tx_provenance.formatted_tx_container;
            r.tx_provenance.submitted_iio_buffer.sha256 = dev.tx_dma_payload_sha();
        }

        r.tx_dma_payload_sha = dev.tx_dma_payload_sha();
        r.tx_dma_payload_ok = (!r.tx_dma_payload_sha.empty() &&
                               r.tx_dma_payload_sha == r.burst_sha);

        // stale-buffer flush: recreate + ONE discard refill
        dev.recreate_rx_buffer();
        {
            const iio::RawChunk c = dev.read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
            std::vector<std::int16_t> discard;
            if (!c.broken && c.samples_available > 0)
                discard.assign(c.samples, c.samples + c.samples_available * 2);
            r.refills.push_back(iqdloop::measure_refill(discard, "discard"));
        }

        // capture >= 2 full periods + margin (fix9r2 Task R4): the receiver searches
        // the WHOLE capture for the preamble, so the capture must guarantee a complete
        // [preamble..tail] burst fits for ANY cyclic TX start phase.
        r.rx_gain_mode_before_capture = dev.get_rx_gain_mode();
        r.rx_gain_before_capture = dev.get_rx_gain();
        const std::size_t capture = iqrflayout::capture_complex(delay_margin);
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
        r.rx_gain_mode_after_capture = dev.get_rx_gain_mode();
        r.rx_gain_after_capture = dev.get_rx_gain();
        r.refills.push_back(iqdloop::measure_refill(r.rx, "capture"));
        // (PlutoTx destructor destroys the TX buffer + stops TX on every path.)
    }

    r.tx_create_delta = dev.tx_buffer_create_count() - txc0;
    r.tx_destroy_delta = dev.tx_buffer_destroy_count() - txd0;
    r.rx_create_delta = dev.rx_buffer_create_count() - rxc0;
    r.rx_destroy_delta = dev.rx_buffer_destroy_count() - rxd0;
    return r;
}

}  // namespace iqrfloop_run_fix9r
