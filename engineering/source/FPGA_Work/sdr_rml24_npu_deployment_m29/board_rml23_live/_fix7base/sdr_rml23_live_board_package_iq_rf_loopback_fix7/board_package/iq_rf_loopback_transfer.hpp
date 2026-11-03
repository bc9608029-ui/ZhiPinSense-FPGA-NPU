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

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <vector>

namespace iqrfloop_run {

// Length of the stale-flush discard refill (one refill, drained before capture).
constexpr std::size_t kRfDiscardComplex = 4096;
// Default TX-off noise-floor capture length.
constexpr std::size_t kRfNoiseComplexDefault = 4096;

struct RfTransferResult {
    std::vector<std::int16_t> tx;       // loaded frozen waveform
    std::vector<std::int16_t> rx;       // the ONE contiguous capture refill
    std::vector<std::int16_t> noise;    // TX-off negative-control capture
    iqdloop::TxVerify tx_verify;        // full-file SHA + non-zero evidence
    std::vector<iqdloop::RefillStat> refills;  // [discard, capture]
    board::RxStats st;
    board::Continuity cont;
    bool capture_ok = false;
    board::RxStats noise_st;
    board::Continuity noise_cont;
    bool noise_capture_ok = false;
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
    const pluto::DataFormatInfo& rx_fmt = pluto::DataFormatInfo{}) {
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
    r.tx = tx_iq;

    const std::uint64_t txc0 = dev.tx_buffer_create_count();
    const std::uint64_t txd0 = dev.tx_buffer_destroy_count();
    const std::uint64_t rxc0 = dev.rx_buffer_create_count();
    const std::uint64_t rxd0 = dev.rx_buffer_destroy_count();

    // ---- TX-off negative control (noise floor) BEFORE any TX ----
    // Stop TX (belt-and-suspenders: the previous file's PlutoTx already stopped it),
    // recreate the RX buffer to drop any stale DMA, then capture ONE contiguous
    // noise refill.  This proves the RF path is quiet before TX and yields the noise
    // floor used for the SNR judgment.
    dev.tx_stop();
    dev.recreate_rx_buffer();
    {
        const bool raw_ok =
            board::capture_contiguous(dev, noise_complex, r.noise, r.noise_st,
                                      r.noise_cont);
        r.noise_capture_ok = raw_ok && r.noise_cont.ok();
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

        // ---- TX DMA payload verify (fix5 parity) ----
        r.tx_dma_payload_sha = dev.tx_dma_payload_sha();
        r.tx_dma_payload_ok = (!r.tx_dma_payload_sha.empty() &&
                               r.tx_dma_payload_sha == r.tx_verify.sha256);

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
