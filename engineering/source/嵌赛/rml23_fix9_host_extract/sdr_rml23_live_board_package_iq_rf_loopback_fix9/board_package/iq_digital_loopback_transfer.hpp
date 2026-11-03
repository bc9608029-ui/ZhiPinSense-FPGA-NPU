#pragma once

// iq_digital_loopback_transfer.hpp — Stage H-E / Route E fix2: the per-file
// TX-load-verify -> cyclic-TX-start -> stale-RX-flush -> contiguous-capture
// transfer path, shared VERBATIM by the board runner and the host sequence test
// (so the sequence test exercises the exact code the board runs, not a copy).
//
// fix2 requirements it implements:
//   * req 1  -- a fresh cyclic TX buffer per file, proven by the create/destroy
//               deltas (PlutoTx RAII destroys the buffer on every path);
//   * req 2  -- prove the LOADED TX bytes match the frozen file SHA and are
//               non-zero (iqdloop::verify_loaded_tx), recorded per file;
//   * req 3  -- stale-buffer flush BEFORE and AFTER TX start: recreate the RX
//               buffer, then ONE discard refill (drain pre-TX / stale DMA
//               samples), then the ONE contiguous capture refill, recording
//               per-refill non-zero rate / RMS / first / last samples;
//   * req 8  -- TX attenuation is still handed to pluto::PlutoTx::prepare(),
//               which enforces the kSafeTxCeilingDb (-40 dB) ceiling.
//
// iCraft-free and libiio-free: depends only on pluto::Device (fake on host, real
// on board), pluto::PlutoTx (the RF-safety state machine, linked from
// pluto_tx.cpp), the pure-logic half (iq_digital_loopback.hpp), and the optional
// m22::StageTiming per-stage timers.  It never opens the NPU and never touches
// libiio.

#include "iq_digital_loopback.hpp"
#include "board_common.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <vector>

namespace iqdloop_run {

// Length of the stale-flush discard refill (one refill, drained before capture).
constexpr std::size_t kDiscardComplex = 4096;

struct TransferResult {
    std::vector<std::int16_t> tx;       // loaded (possibly capped) TX waveform
    std::vector<std::int16_t> rx;       // the ONE contiguous capture refill
    iqdloop::TxVerify tx_verify;        // full-file SHA + non-zero evidence
    std::vector<iqdloop::RefillStat> refills;  // [discard, capture]
    board::RxStats st;
    board::Continuity cont;
    bool capture_ok = false;
    double tx_atten_requested_db = 0.0;
    double tx_atten_readback_db = 0.0;
    int loopback_readback = -1;
    std::uint64_t tx_create_delta = 0;
    std::uint64_t tx_destroy_delta = 0;
    std::uint64_t rx_create_delta = 0;
    std::uint64_t rx_destroy_delta = 0;

    // fix3 requirement 6: --digital-loopback-tx-scale evidence.  When tx_scale != 1,
    // the frozen bytes are loaded + verified first (pre-scale SHA == frozen SHA),
    // then scaled in the int16 host domain (test fixture only, never the production
    // preprocess chain); the post-scale SHA and the 12-bit clip counts are recorded
    // so a scale can never be confused with a format correction.
    double tx_scale = 1.0;
    std::string tx_sha_pre_scale;
    std::string tx_sha_post_scale;
    std::uint64_t tx_clip_pre_scale = 0;   // |v| >= 2047 (12-bit DAC rail)
    std::uint64_t tx_clip_post_scale = 0;
    double tx_rms_pre_scale = 0.0;
    double tx_rms_post_scale = 0.0;

    // fix4: the scale is a DOMAIN MAPPING (RX-domain frozen counts -> TX-domain
    // logical counts), not a hardware-attenuation fudge.  These record the two
    // domains and their bit widths, the pre/post-scale peaks, and whether the scale
    // saturated the int16 container (fail-closed: a clipped scale must not proceed
    // to a fidelity verdict).
    std::string src_domain;              // "rx_count_domain"  (frozen counts)
    std::string dst_domain;              // "tx_logical_domain"
    int src_bits = 0;                    // rx_fmt.bits (norm-clamped)
    int dst_bits = 0;                    // tx_fmt.bits (norm-clamped)
    int tx_peak_pre_scale = 0;           // max |v| before scaling
    int tx_peak_post_scale = 0;          // max |v| after scaling
    bool scale_clipped = false;          // any sample saturated int16 under the scale

    // fix5: SHA of the ACTUAL TX DMA payload (read back from the buffer after
    // convert_inverse, before iio_buffer_push) and whether it equals tx_sha_post_scale.
    // Recorded, NOT thrown: the runner gates on tx_dma_payload_ok (TX_DMA_PAYLOAD_MISMATCH),
    // while a test that uses a non-identity fake TX format still observes a mismatch
    // without regressing (its DMA payload genuinely differs from the host bytes).
    std::string tx_dma_payload_sha;
    bool tx_dma_payload_ok = false;
};

// Apply the test-fixture TX scale (RX-domain frozen counts -> TX-domain logical
// counts) to a loaded int16 host waveform.  Returns the number of samples whose
// scaled value saturated the int16 range (fail-closed: the caller must not continue
// to a fidelity verdict when this is non-zero).  Never touches the production
// preprocess chain.  `rms_out`/`peak_out` receive the post-scale RMS and peak.
inline std::uint64_t scale_waveform(std::vector<std::int16_t>& iq, double scale,
                                    double& rms_out, int& peak_out) {
    std::uint64_t clipped = 0;
    int peak = 0;
    double e = 0.0;
    for (auto& v : iq) {
        const double sv = std::llround(static_cast<double>(v) * scale);
        if (sv > 32767.0 || sv < -32768.0) ++clipped;
        v = static_cast<std::int16_t>(
            std::max(-32768.0, std::min(32767.0, sv)));
        peak = std::max(peak, std::abs(static_cast<int>(v)));
        e += static_cast<double>(v) * static_cast<double>(v);
    }
    rms_out = std::sqrt(e / static_cast<double>(iq.size()));
    peak_out = peak;
    return clipped;
}

// Load + verify the frozen bytes, TX them cyclically (PlutoTx safety state
// machine), flush the stale RX buffer (recreate + discard refill), then capture
// one contiguous refill.  `expect_sha` is the frozen-file SHA; the TX is verified
// BEFORE any capping so the SHA comparison is exact (a capped prefix is still
// logged, but its SHA is not the frozen-file SHA).  Throws (fail-closed) on a SHA
// mismatch or an empty waveform.
inline TransferResult transfer_one_file(
    pluto::Device& dev, const std::string& path, std::uint64_t complex_count,
    const std::string& expect_sha, std::uint64_t center_hz, double rx_gain_db,
    double tx_atten_db, std::size_t delay_margin, std::uint64_t tx_complex_cap,
    m22::StageTiming* timing = nullptr, double tx_scale = 1.0,
    const pluto::DataFormatInfo& tx_fmt = pluto::DataFormatInfo{},
    const pluto::DataFormatInfo& rx_fmt = pluto::DataFormatInfo{}) {
    TransferResult r;
    r.tx_scale = tx_scale;
    r.src_domain = "rx_count_domain";
    r.dst_domain = "tx_logical_domain";
    r.src_bits = (rx_fmt.bits == 0 || rx_fmt.bits > 16) ? 16 : static_cast<int>(rx_fmt.bits);
    r.dst_bits = (tx_fmt.bits == 0 || tx_fmt.bits > 16) ? 16 : static_cast<int>(tx_fmt.bits);

    // ---- load + verify the FROZEN bytes (req 2), BEFORE any scale/cap ----
    std::vector<std::int16_t> tx_iq = iqdloop::load_ci16(path, complex_count);
    r.tx_verify = iqdloop::verify_loaded_tx(tx_iq, expect_sha);
    r.tx_sha_pre_scale = r.tx_verify.sha256;
    r.tx_rms_pre_scale = r.tx_verify.rms;
    for (std::int16_t v : tx_iq) {
        if (std::abs(static_cast<int>(v)) >= 2047) ++r.tx_clip_pre_scale;
        r.tx_peak_pre_scale = std::max(r.tx_peak_pre_scale,
                                       std::abs(static_cast<int>(v)));
    }

    // fix3 requirement 6 + fix4 domain mapping: apply the explicit test-fixture TX
    // scale AFTER the frozen SHA check, so the pre-scale SHA is always the frozen-
    // file SHA.  This maps RX-domain frozen counts to TX-domain logical counts in
    // the int16 HOST waveform; it never touches the production preprocess chain.
    // Record the post-scale SHA, RMS, peak, and 12-bit clip count, and fail-closed
    // on any int16 saturation.
    if (tx_scale != 1.0) {
        r.scale_clipped =
            (scale_waveform(tx_iq, tx_scale, r.tx_rms_post_scale,
                            r.tx_peak_post_scale) > 0);
        r.tx_sha_post_scale = sdr::Sha256::hex(tx_iq.data(),
                                               tx_iq.size() * sizeof(std::int16_t));
        for (std::int16_t v : tx_iq)
            if (std::abs(static_cast<int>(v)) >= 2047) ++r.tx_clip_post_scale;
    } else {
        r.tx_sha_post_scale = r.tx_sha_pre_scale;
        r.tx_clip_post_scale = r.tx_clip_pre_scale;
        r.tx_rms_post_scale = r.tx_rms_pre_scale;
        r.tx_peak_post_scale = r.tx_peak_pre_scale;
        r.scale_clipped = false;
    }

    if (tx_complex_cap > 0 && tx_complex_cap < complex_count)
        tx_iq.resize(static_cast<std::size_t>(tx_complex_cap) * 2);
    r.tx = tx_iq;

    const std::uint64_t txc0 = dev.tx_buffer_create_count();
    const std::uint64_t txd0 = dev.tx_buffer_destroy_count();
    const std::uint64_t rxc0 = dev.rx_buffer_create_count();
    const std::uint64_t rxd0 = dev.rx_buffer_destroy_count();

    {
        pluto::TxConfig txc;
        txc.center_freq_hz = center_hz;
        txc.rx_gain_db = rx_gain_db;
        txc.tx_atten_db = tx_atten_db;
        txc.loopback = 1;                      // digital
        txc.confirm_safe_rf_path = false;      // no antenna / no coax
        txc.waveform = tx_iq;
        pluto::PlutoTx tx(dev, txc);

        // prepare (write + read back max safe atten; enforce -40 dB ceiling)
        if (timing) {
            m22::StageTiming::Timer rf_t(*timing, m22::StageId::RfConfig);
            tx.prepare();
        } else {
            tx.prepare();
        }
        r.tx_atten_requested_db = tx_atten_db;
        r.tx_atten_readback_db = dev.get_tx_atten();
        r.loopback_readback = dev.get_loopback();

        tx.start_cyclic();

        // ---- fix5 TX DMA payload verify ----
        // Read back the ACTUAL bytes the TX buffer now holds (post convert, pre push)
        // and hash them.  If they differ from the post-scale SHA, the DMA is
        // transmitting something other than the scaled bytes.  Recorded, NOT thrown:
        // the runner gates on tx_dma_payload_ok (TX_DMA_PAYLOAD_MISMATCH), while a
        // host test that uses a non-identity fake TX format still sees a mismatch
        // (its DMA payload genuinely differs from the host bytes) without regressing.
        r.tx_dma_payload_sha = dev.tx_dma_payload_sha();
        r.tx_dma_payload_ok = (!r.tx_dma_payload_sha.empty() &&
                               r.tx_dma_payload_sha == r.tx_sha_post_scale);

        // ---- stale-buffer flush (req 3) ----
        // (a) recreate the RX buffer so a stale DMA refill from a previous file can
        //     never be silently reused (destroys + forgets; next read re-arms);
        dev.recreate_rx_buffer();
        // (b) ONE discard refill: drain pre-TX / stale samples, recorded.
        {
            const iio::RawChunk c = dev.read_rx(kDiscardComplex, 1000);
            std::vector<std::int16_t> discard;
            if (!c.broken && c.samples_available > 0)
                discard.assign(c.samples, c.samples + c.samples_available * 2);
            r.refills.push_back(iqdloop::measure_refill(discard, "discard"));
        }
        // fix5: capture >= 2 * TX period + delay margin, so the full-period FFT
        // circular sync always has a complete period AFTER the transient discard
        // and can recover an arbitrary cyclic phase (the fix4 capture of
        // period + delay_margin was too short to find the true delay).
        const std::size_t capture =
            2 * (tx_iq.size() / 2) + delay_margin;
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
        r.refills.push_back(iqdloop::measure_refill(r.rx, "capture"));
        // (PlutoTx destructor destroys the TX buffer here, on every path.)
    }

    r.tx_create_delta = dev.tx_buffer_create_count() - txc0;
    r.tx_destroy_delta = dev.tx_buffer_destroy_count() - txd0;
    r.rx_create_delta = dev.rx_buffer_create_count() - rxc0;
    r.rx_destroy_delta = dev.rx_buffer_destroy_count() - rxd0;
    return r;
}

}  // namespace iqdloop_run
