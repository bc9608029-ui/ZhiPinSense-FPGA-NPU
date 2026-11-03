#pragma once

// iq_rf_loopback_transfer_24class_bf16_fix10.hpp -- fix10class24-singlesdr-ab1
// (task book 39e5): the per-attempt PHYSICAL-RF transfer for the single-SDR 24-class
// BF16 A/B runner.  ONE Pluto does BOTH the local TX (cyclic canonical burst) and the
// RX capture over the external 50-ohm coax (loopback=0), sharing the same LO/clock.
//
// This is an ADDITIVE new file.  It does NOT touch any red-line header.  It reuses:
//   * pluto::Device / pluto::PlutoTx / pluto::TxConfig  (sdr_adapter)
//   * iqrfloop_run::kRfDiscardComplex                    (iq_rf_loopback_transfer.hpp)
//   * iqrflayout::capture_complex                        (iq_rf_frame_layout.hpp)
//   * board::capture_contiguous / RxStats / Continuity   (board_common.hpp)
//   * iqpctbrx::TxBurstBuild                             (iq_pc_tx_board_rx_transfer_fix10.hpp)
//
// The caller (iq_rf_loopback_24class_bf16_fix10.hpp) passes `expected`, an already
// built canonical TxBurstBuild from fix10canonical::buildTxBurstFromFrozen; this
// header does NOT rebuild the burst and does NOT run the negative control (the runner
// runs it once per file, OUTSIDE the recapture loop).  It only performs ONE attempt:
//
//   TX config -> prepare -> post-prepare RX-gain read-back (manual / 35 dB, fail-closed)
//             -> TX BW write-then-read-back (fail-closed) -> start_cyclic
//             -> RX flush -> capture_contiguous -> tx.stop() -> confirm !tx_running()
//
// TX parameter SAVE/RESTORE is NOT this header's job (that is the runner's single
// DeviceStateGuard); PlutoTx::stop()/destructor only destroys the TX buffer.

#include "iq_pc_tx_board_rx_transfer_fix10.hpp"  // iqpctbrx::TxBurstBuild
#include "iq_rf_frame_layout.hpp"                // iqrflayout::capture_complex
#include "iq_rf_loopback_transfer.hpp"           // iqrfloop_run::kRfDiscardComplex
#include "rf_fix_helpers.hpp"                    // rf_fix::rf_readback_close
#include "board_common.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"

#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqrfloop_run_24bf16 {

struct RfTransferResult24Bf16Fix10 {
    std::vector<std::int16_t> rx;         // interleaved int16 capture (>= 2 periods + margin)
    std::string burst_sha;                // identity read-back: expected.burst_sha
    bool tx_dma_payload_ok = false;       // TX DMA SHA == expected.burst_sha
    double tx_atten_readback = 0.0;       // post-prepare get_tx_atten()
    long long tx_bw_readback = 0;         // post-write get_tx_bw()
    int loopback_readback = -1;           // must be 0 (external RF)
    bool tx_stopped_ok = false;           // tx.stop() then !tx_running()
    bool capture_ok = false;              // single contiguous RX refill, no anomaly
    board::RxStats rxst;
    board::Continuity rxcont;
};

// One attempt: local TX of the canonical burst + contiguous RX capture + TX stop.
// Throws (fail-closed) on an empty waveform, an unconfirmed external-RF path, a TX
// atten over the -40 dB safety ceiling, a post-prepare RX gain/mode mismatch, a
// TX-bandwidth read-back mismatch, or a loopback read-back != 0.
inline RfTransferResult24Bf16Fix10 transfer_one_attempt_rf_24class_bf16_fix10(
        pluto::Device& dev, const iqpctbrx::TxBurstBuild& expected,
        std::int64_t source_index, const std::string& file_name,
        std::uint64_t center_hz, double rx_gain_db, double tx_atten_db,
        long long tx_bw, std::size_t delay_margin, m22::StageTiming* timing) {
    RfTransferResult24Bf16Fix10 r;
    if (expected.burst.empty())
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10: empty canonical TX burst");

    pluto::TxConfig cfg;
    cfg.center_freq_hz = center_hz;
    cfg.rx_gain_db = rx_gain_db;        // MUST be 35 (prepare() clobbers RX gain to this)
    cfg.tx_atten_db = tx_atten_db;
    cfg.loopback = 0;                   // external RF (off), not digital
    cfg.confirm_safe_rf_path = true;    // explicit 50-ohm coax confirmation
    cfg.waveform = expected.burst;

    pluto::PlutoTx tx(dev, cfg);

    if (timing) {
        m22::StageTiming::Timer rf_t(*timing, m22::StageId::RfConfig);
        tx.prepare();
    } else {
        tx.prepare();
    }

    // Post-prepare RX gain read-back (fail-closed): prepare() step 3 rewrote the RX
    // gain to cfg.rx_gain_db; a mismatch would mean the RX gain silently reverted to
    // the TxConfig default (10 dB) instead of the required 35 dB.
    const std::string rx_gain_mode = dev.get_rx_gain_mode();
    const double rx_gain = dev.get_rx_gain();
    if (rx_gain_mode != "manual" ||
        std::fabs(rx_gain - rx_gain_db) > 0.5) {
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10: post-prepare RX gain mismatch "
            "(mode=" + rx_gain_mode +
            " gain=" + std::to_string(rx_gain) +
            " want=manual/" + std::to_string(rx_gain_db) + " dB)");
    }

    // TX bandwidth: prepare() does NOT write TX BW, so write it here and fail-closed
    // on a read-back mismatch (the runner also verifies this endpoint once, up-front).
    r.tx_bw_readback = dev.set_tx_bw(tx_bw);
    if (!rf_fix::rf_readback_close(r.tx_bw_readback, tx_bw, 1000LL, 0.05))
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10: tx_bw read-back mismatch "
            "(requested=" + std::to_string(tx_bw) +
            " readback=" + std::to_string(r.tx_bw_readback) + ")");

    r.loopback_readback = dev.get_loopback();
    if (r.loopback_readback != 0)
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-fix10: loopback read-back != 0 (got " +
            std::to_string(r.loopback_readback) +
            ", want 0) -- external RF requires the internal digital loopback OFF");
    r.tx_atten_readback = dev.get_tx_atten();
    r.burst_sha = expected.burst_sha;

    tx.start_cyclic();

    const std::string tx_dma_sha = dev.tx_dma_payload_sha();
    r.tx_dma_payload_ok = (!tx_dma_sha.empty() && tx_dma_sha == expected.burst_sha);

    // stale-buffer flush: recreate + ONE discard refill (flush the TX ramp)
    dev.recreate_rx_buffer();
    {
        const iio::RawChunk c = dev.read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
        (void)c;
    }

    // capture >= 2 full periods + margin (same capture size as the dual-SDR runner)
    const std::size_t capture = iqrflayout::capture_complex(delay_margin);
    {
        if (timing) {
            m22::StageTiming::Timer t(*timing, m22::StageId::RxRefill);
            const bool raw_ok =
                board::capture_contiguous(dev, capture, r.rx, r.rxst, r.rxcont);
            r.capture_ok = raw_ok && r.rxcont.ok();
        } else {
            const bool raw_ok =
                board::capture_contiguous(dev, capture, r.rx, r.rxst, r.rxcont);
            r.capture_ok = raw_ok && r.rxcont.ok();
        }
    }

    tx.stop();                          // destroy the TX buffer (idempotent)
    r.tx_stopped_ok = !dev.tx_running(); // confirm TX is off

    std::printf("FIX10CLASS24_BF16_SINGLESDR_TX file=%s source_index=%lld "
                "burst_sha=%s tx_bw=%lld tx_bw_readback=%lld "
                "tx_atten_readback=%.3f loopback_readback=%d "
                "tx_dma_payload_ok=%d capture_ok=%d tx_stopped_ok=%d\n",
                file_name.c_str(), static_cast<long long>(source_index),
                expected.burst_sha.c_str(), static_cast<long long>(tx_bw),
                static_cast<long long>(r.tx_bw_readback), r.tx_atten_readback,
                r.loopback_readback, r.tx_dma_payload_ok ? 1 : 0,
                r.capture_ok ? 1 : 0, r.tx_stopped_ok ? 1 : 0);
    std::fflush(stdout);

    return r;
}

}  // namespace iqrfloop_run_24bf16
