#pragma once

// iq_dual_sdr_transfer_fix10.hpp -- fix10 Path A/C: the per-file TRAINING-FRAME
// DUAL-SDR physical-RF transfer (TX device -> coax/RF -> RX device -> recovery).
//
// This is a NEW entry point; the single-SDR transfer (iq_rf_loopback_transfer_fix9r.hpp)
// and the fix9 transfer (iq_rf_loopback_transfer.hpp) are RED-LINE and untouched.  The
// dual-SDR transfer mirrors the single-SDR fix9r2h2 transfer's exact negative-control +
// load-verify + burst-build + stale-flush + contiguous-capture sequence, but:
//
//   * TWO devices (tx_dev, rx_dev).  Every write is role-split: the TX device owns
//     tx_stop / set_tx_atten / set_tx_lo / set_loopback / tx_start_cyclic / DMA-SHA /
//     push-provenance; the RX device owns set_rx_gain_mode / set_rx_gain / set_rx_lo /
//     set_loopback / recreate_rx_buffer / read_rx / capture.  The TX-off negative
//     control and the main capture read ONLY from rx_dev (never from tx_dev).
//   * PlutoTx::prepare() is NOT reused (fix10 red line): the role-split safety
//     sequence is re-expressed here so a TX-only device never receives an RX-gain
//     write and an RX-only device never receives a TX-attenuation write.
//   * TWO DeviceStateGuards (tx_guard declared before rx_guard) snapshot both devices
//     BEFORE any write; if rx_guard construction throws, tx_guard's destructor still
//     restores the TX device (fix10 lifecycle requirement).  Both restore() results
//     are recorded as tx_restore_ok / rx_restore_ok.
//
// The TX/RX data formats and recovery math are the fix9r2h2 shared modules; this
// header reuses iq_rf_training_frame / iq_rf_tx_provenance / iq_rf_frame_layout /
// iq_rf_sync_recovery (the recovery itself lives in the runner, N3) and iqdigital.
//
// iCraft-free and libiio-free: it compiles identically on the host (FakeTxDevice /
// FakeRxDevice over a shared FakeRfLink) and the board (two real Plutos).

#include "iq_digital_loopback.hpp"        // iqdloop::load_ci16 / verify_loaded_tx / measure_refill
#include "iq_rf_loopback_transfer.hpp"    // iqrfloop_run::kRfDiscard* / kRfNoise* (reuse only)
#include "iq_rf_training_frame.hpp"       // iqrftrain::build_burst / kTotalBurstComplex
#include "iq_rf_frame_layout.hpp"         // iqrflayout::capture_complex (>=2 periods)
#include "iq_rf_tx_provenance.hpp"        // iqrftxprov::fingerprint / verify_frame
#include "board_common.hpp"
#include "../sdr_adapter/device_state_guard.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"    // kSafeTxAttenDb / kSafeTxCeilingDb (constants only)

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace iqdual_run_fix10 {

// Capture margin past TWO full bursts (mirrors iqrfloop_run_fix9r::kFix9rDelayMarginDefault).
constexpr std::size_t kFix10DelayMarginDefault = 8192;

// RAII: destroy the TX buffer (tx_stop) on EVERY path out of the TX scope -- the
// dual-SDR transfer has no PlutoTx wrapper whose destructor would do this.
struct TxStopGuard {
    pluto::Device& dev;
    explicit TxStopGuard(pluto::Device& d) : dev(d) {}
    ~TxStopGuard() { dev.tx_stop(); }
    TxStopGuard(const TxStopGuard&) = delete;
    TxStopGuard& operator=(const TxStopGuard&) = delete;
};

// Role-split exact read-back check (mirrors PlutoTx::require_exact_d, exact `!=`).
inline void require_exact_d(double got, double want, const char* what) {
    if (got != want)
        throw std::runtime_error(std::string("iq-dual-sdr-fix10: ") + what +
                                 " read-back mismatch (got " + std::to_string(got) +
                                 ", want " + std::to_string(want) + ")");
}

// Two-DeviceStateGuard RAII.  tx_guard is declared BEFORE rx_guard: if rx_guard's
// construction throws, the already-constructed tx_guard is destroyed and restores the
// TX device (fix10 "第二个 guard 失败时第一个仍必须自动恢复" requirement).
struct DualSdrSession {
    pluto::DeviceStateGuard tx_guard;
    pluto::DeviceStateGuard rx_guard;
    DualSdrSession(pluto::Device& tx_dev, pluto::Device& rx_dev)
        : tx_guard(tx_dev), rx_guard(rx_dev) {}
};

struct DualSdrTransferResult {
    std::vector<std::int16_t> payload;   // loaded frozen payload (post target_rms scale)
    std::vector<std::int16_t> tx;        // the TX burst: [pre][zero][train][payload][guard][tail]
    std::vector<std::int16_t> rx;        // the ONE contiguous capture refill (from rx_dev)
    std::vector<std::int16_t> noise;     // TX-off negative-control capture (median RMS, from rx_dev)
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
    int tx_loopback_readback = -1;       // must be 0 in RF mode
    int rx_loopback_readback = -1;       // must be 0 in RF mode

    // RX gain-mode endpoint read-back (pure reads, LOG-ONLY -- no gate, no version).
    std::string rx_gain_mode_before_capture;
    double rx_gain_before_capture = 0.0;
    std::string rx_gain_mode_after_capture;
    double rx_gain_after_capture = 0.0;

    // Role-split read-backs (recorded for the audit).
    double rx_gain_readback_db = 0.0;    // set_rx_gain read-back (exact check)
    long long tx_lo_readback = 0;
    long long rx_lo_readback = 0;

    std::uint64_t tx_create_delta = 0;
    std::uint64_t tx_destroy_delta = 0;
    std::uint64_t rx_create_delta = 0;
    std::uint64_t rx_destroy_delta = 0;

    // SHA of the ACTUAL TX DMA payload (the burst), compared against burst_sha.
    std::string tx_dma_payload_sha;
    bool tx_dma_payload_ok = false;

    iqrftxprov::TxByteProvenance tx_provenance;
    iqrftxprov::TxFrameVerify frame_verify;
    pluto::TxPushProvenance tx_push;

    std::size_t warmup_refills = 0;
    int retry = 0;
    double noise_stability_ratio = 0.0;

    // TX-level scaling evidence (--rf-tx-target-rms=N, payload only).
    double tx_target_rms = 0.0;
    double tx_native_rms = 0.0;
    double tx_scale = 1.0;
    double tx_peak_pre = 0.0;
    double tx_peak_post = 0.0;
    bool tx_clip_pre = false;
    bool tx_clip_post = false;
    std::string tx_sha_pre;
    std::string tx_sha_post;
    std::string burst_sha;

    // Dual-SDR restore results (both recorded; the runner fail-closes if either is false).
    bool tx_restore_ok = false;
    bool rx_restore_ok = false;
};

// Load + verify the frozen payload, build the training-frame burst, capture the
// TX-off noise floor (from rx_dev only), TX the burst on the TX device, flush the
// stale RX buffer, then capture burst+margin from the RX device.  Throws (fail-closed)
// on a SHA mismatch / empty waveform, a payload complex_count != kPayloadComplex, a
// loopback read-back != 0, or any role-split safety refusal (-40 dB ceiling, read-back
// mismatch).  The recovery (iq_rf_sync_recovery) is NOT run here -- the runner (N3)
// applies it to r.rx so the transfer stays a pure producer/consumer capture.
inline DualSdrTransferResult transfer_one_file_dual_sdr_fix10(
        pluto::Device& tx_dev, pluto::Device& rx_dev,
        const std::string& path, std::uint64_t complex_count,
        const std::string& expect_sha, std::uint64_t center_hz, double rx_gain_db,
        double tx_atten_db, std::size_t delay_margin, std::size_t noise_complex,
        m22::StageTiming* timing, double target_rms) {
    DualSdrTransferResult r;
    if (complex_count != iqrftrain::kPayloadComplex)
        throw std::runtime_error(
            "iq-dual-sdr-fix10: payload complex_count " +
            std::to_string(complex_count) + " != training-frame kPayloadComplex " +
            std::to_string(iqrftrain::kPayloadComplex));

    // ---- load + verify the FROZEN payload bytes, BEFORE any device write ----
    std::vector<std::int16_t> payload_iq = iqdloop::load_ci16(path, complex_count);
    r.tx_verify = iqdloop::verify_loaded_tx(payload_iq, expect_sha);

    // ---- fix9 Task D parity: TX-level scaling to --rf-tx-target-rms (default 2048) ----
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
        }
        r.tx_sha_post = sdr::Sha256::hex(payload_iq.data(),
                                         payload_iq.size() * sizeof(std::int16_t));
    }
    r.payload = payload_iq;

    // ---- build the training-frame burst (throws on any length mismatch) ----
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(payload_iq);
    r.tx = burst;
    r.burst_sha = sdr::Sha256::hex(burst.data(), burst.size() * sizeof(std::int16_t));

    // ---- independent TX-frame verifier, fail-closed BEFORE any TX ----
    r.frame_verify = iqrftxprov::verify_frame(burst, payload_iq);
    if (!r.frame_verify.ok)
        throw std::runtime_error(
            "iq-dual-sdr-fix10: TX frame verifier FAILED (training_exact_match=" +
            std::to_string(r.frame_verify.training_exact_match) +
            " payload_exact_match=" +
            std::to_string(r.frame_verify.payload_exact_match) +
            " frame_layout_match=" +
            std::to_string(r.frame_verify.frame_layout_match) + ")");

    const std::uint64_t txc0 = tx_dev.tx_buffer_create_count();
    const std::uint64_t txd0 = tx_dev.tx_buffer_destroy_count();
    const std::uint64_t rxc0 = rx_dev.rx_buffer_create_count();
    const std::uint64_t rxd0 = rx_dev.rx_buffer_destroy_count();

    // ---- TWO guards snapshot both devices BEFORE any device write ----
    DualSdrSession session(tx_dev, rx_dev);

    // ---- TX-off negative control (noise floor) BEFORE any TX, read from rx_dev ----
    tx_dev.tx_stop();
    r.tx_stopped_readback = !tx_dev.tx_running();

    const auto run_noise_round = [&](std::size_t warmup) {
        r.warmup_refills += warmup;
        std::vector<std::int16_t> all_discard;
        for (std::size_t d = 0; d < warmup; ++d) {
            rx_dev.recreate_rx_buffer();
            const iio::RawChunk c = rx_dev.read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
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
            rx_dev.recreate_rx_buffer();
            board::RxStats st;
            board::Continuity cont;
            const bool raw_ok =
                board::capture_contiguous(rx_dev, noise_complex, windows[w], st, cont);
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
        tx_dev.tx_stop();
        r.tx_stopped_readback = !tx_dev.tx_running();
        run_noise_round(iqrfloop_run::kRfDiscardRefills);
    }

    {
        TxStopGuard txstop(tx_dev);   // tx_stop() on EVERY path out of this scope

        // ---- role-split RF safety config (mirrors PlutoTx::prepare, split by role) ----
        // step 0: TX off first (idempotent; already off from the negative control).
        tx_dev.tx_stop();
        // ceiling: the working attenuation must never exceed -40 dB (external RF).
        if (tx_atten_db > pluto::kSafeTxCeilingDb)
            throw std::runtime_error(
                "iq-dual-sdr-fix10: working TX attenuation " + std::to_string(tx_atten_db) +
                " dB exceeds the -40 dB safety ceiling (external RF)");
        // step 2 (TX): safe attenuation floor, read-back exact.
        require_exact_d(tx_dev.set_tx_atten(pluto::kSafeTxAttenDb),
                        pluto::kSafeTxAttenDb, "TX attenuation (safe floor)");
        // step 3 (RX): manual gain mode, then low gain, read-back exact.
        if (rx_dev.set_rx_gain_mode("manual") != "manual")
            throw std::runtime_error(
                "iq-dual-sdr-fix10: RX gain mode read-back != manual");
        require_exact_d(rx_dev.set_rx_gain(rx_gain_db), rx_gain_db, "RX gain");
        r.rx_gain_readback_db = rx_dev.get_rx_gain();
        // step 4: align LOs (TX and RX), read-back exact.
        r.tx_lo_readback = tx_dev.set_tx_lo(static_cast<long long>(center_hz));
        r.rx_lo_readback = rx_dev.set_rx_lo(static_cast<long long>(center_hz));
        if (r.tx_lo_readback != static_cast<long long>(center_hz) ||
            r.rx_lo_readback != static_cast<long long>(center_hz) ||
            r.tx_lo_readback != r.rx_lo_readback)
            throw std::runtime_error(
                "iq-dual-sdr-fix10: LO align failed (tx_lo=" +
                std::to_string(r.tx_lo_readback) + " rx_lo=" +
                std::to_string(r.rx_lo_readback) + " center=" +
                std::to_string(center_hz) + ")");
        // step 5: loopback off on BOTH devices (external RF), read-back exact.
        if (tx_dev.set_loopback(0) != 0)
            throw std::runtime_error(
                "iq-dual-sdr-fix10: TX loopback set read-back != 0");
        if (rx_dev.set_loopback(0) != 0)
            throw std::runtime_error(
                "iq-dual-sdr-fix10: RX loopback set read-back != 0");
        // step 6: ramp to the working attenuation (only when it differs from the floor).
        if (tx_atten_db != pluto::kSafeTxAttenDb)
            require_exact_d(tx_dev.set_tx_atten(tx_atten_db), tx_atten_db,
                            "TX attenuation (working)");

        r.tx_atten_requested_db = tx_atten_db;
        r.tx_atten_readback_db = tx_dev.get_tx_atten();
        r.tx_loopback_readback = tx_dev.get_loopback();
        r.rx_loopback_readback = rx_dev.get_loopback();
        if (r.tx_loopback_readback != 0 || r.rx_loopback_readback != 0)
            throw std::runtime_error(
                "iq-dual-sdr-fix10: loopback read-back != 0 (tx=" +
                std::to_string(r.tx_loopback_readback) + " rx=" +
                std::to_string(r.rx_loopback_readback) + ", want 0) -- external RF "
                "requires the internal digital loopback OFF on both devices");

        // ---- TX on the TX device ----
        tx_dev.tx_start_cyclic(burst);

        // ---- TX byte provenance (five stages) + push bytes (all on tx_dev) ----
        r.tx_push = tx_dev.tx_push_provenance();
        r.tx_provenance.payload_source = iqrftxprov::fingerprint(payload_iq);
        r.tx_provenance.training_reference =
            iqrftxprov::fingerprint(iqrftxprov::training_reference_iq());
        r.tx_provenance.framed_logical_iq = iqrftxprov::fingerprint(burst);
        {
            std::vector<std::int16_t> raw;
            tx_dev.tx_raw_after_inverse(burst, raw);
            r.tx_provenance.formatted_tx_container = iqrftxprov::fingerprint(raw);
            r.tx_provenance.formatted_tx_container.format_desc =
                pluto::describe_data_format(tx_dev.tx_data_format());
            r.tx_provenance.submitted_iio_buffer =
                r.tx_provenance.formatted_tx_container;
            r.tx_provenance.submitted_iio_buffer.sha256 = tx_dev.tx_dma_payload_sha();
        }

        r.tx_dma_payload_sha = tx_dev.tx_dma_payload_sha();
        r.tx_dma_payload_ok = (!r.tx_dma_payload_sha.empty() &&
                               r.tx_dma_payload_sha == r.burst_sha);

        // ---- stale-buffer flush on the RX device: recreate + ONE discard refill ----
        rx_dev.recreate_rx_buffer();
        {
            const iio::RawChunk c = rx_dev.read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
            std::vector<std::int16_t> discard;
            if (!c.broken && c.samples_available > 0)
                discard.assign(c.samples, c.samples + c.samples_available * 2);
            r.refills.push_back(iqdloop::measure_refill(discard, "discard"));
        }

        // ---- capture >= 2 full periods + margin from the RX device ----
        r.rx_gain_mode_before_capture = rx_dev.get_rx_gain_mode();
        r.rx_gain_before_capture = rx_dev.get_rx_gain();
        const std::size_t capture = iqrflayout::capture_complex(delay_margin);
        if (timing) {
            m22::StageTiming::Timer t(*timing, m22::StageId::RxRefill);
            const bool raw_ok =
                board::capture_contiguous(rx_dev, capture, r.rx, r.st, r.cont);
            r.capture_ok = raw_ok && r.cont.ok();
        } else {
            const bool raw_ok =
                board::capture_contiguous(rx_dev, capture, r.rx, r.st, r.cont);
            r.capture_ok = raw_ok && r.cont.ok();
        }
        r.rx_gain_mode_after_capture = rx_dev.get_rx_gain_mode();
        r.rx_gain_after_capture = rx_dev.get_rx_gain();
        r.refills.push_back(iqdloop::measure_refill(r.rx, "capture"));
        // (TxStopGuard destructor stops TX here, on every path.)
    }

    r.tx_create_delta = tx_dev.tx_buffer_create_count() - txc0;
    r.tx_destroy_delta = tx_dev.tx_buffer_destroy_count() - txd0;
    r.rx_create_delta = rx_dev.rx_buffer_create_count() - rxc0;
    r.rx_destroy_delta = rx_dev.rx_buffer_destroy_count() - rxd0;

    // ---- restore both devices (TX already stopped by TxStopGuard) ----
    session.tx_guard.restore();
    session.rx_guard.restore();
    r.tx_restore_ok = session.tx_guard.restore_ok();
    r.rx_restore_ok = session.rx_guard.restore_ok();
    return r;
}

}  // namespace iqdual_run_fix10
