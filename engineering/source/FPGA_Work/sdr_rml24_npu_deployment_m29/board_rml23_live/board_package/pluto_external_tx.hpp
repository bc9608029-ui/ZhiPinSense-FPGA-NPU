#pragma once

// pluto_external_tx.hpp -- Route G fix10: the DEVICE-INDEPENDENT PC-side TX core.
//
// Two independent Plutos transmit (PC / WSL x86-64) and receive (board / FMQL30TAI)
// over a 50-ohm coax, so the PC must emit WITHOUT ever auto-selecting a device and
// WITHOUT leaving a cyclic TX running on exit.  This header wraps that safety
// sequence around a FrameProducer so host tests can drive it with a FakePlutoDevice
// and the real tool (tools/pluto_external_tx.cpp) drives it with libiio.
//
// Safety sequence (TX-only; mirrors PlutoTx's startup order, but never touches RX):
//   1. open() -> verify dev.serial() EXACTLY matches --serial (mismatch/empty aborts);
//   2. DeviceStateGuard guard(dev)   (save/restore every negotiated parameter);
//   3. set_sample_rate(2.56M) read-back +/-5 Hz -> set_tx_lo(center);
//   4. set_tx_atten(atten) read-back confirm; atten > -40 dB is REFUSED;
//   5. set_loopback(0) read-back confirm == 0  (external RF: digital loopback OFF);
//   6. per frame: tx_start_cyclic(frame) -> verify tx_dma_payload_sha() against the
//      host mirror of the raw container (format_convert_host_to_raw(tx_data_format));
//   7. on exit / SIGINT / exception / timeout / disconnect: tx_stop() (idempotent,
//      destroys the buffer) + guard.restore(), then assert !tx_running().
//
// The +-48 kHz independent-crystal CFO and the +-20 ppm SRO are the RECEIVER's job
// (iq_external_rf_rx.hpp); the transmitter emits a plain baseband frame at 2.56 MSPS.
//
// iCraft-free (libiio only appears in tools/pluto_external_tx.cpp via the Device
// implementation).

#include "iq_external_rf_frame.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"
#include "../sdr_adapter/device_state_guard.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cstdint>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

namespace extrf_tx {

constexpr long long kSampleRateToleranceHz = 5;    // abs(actual-requested) <= 5 Hz
constexpr double kAttenReadbackToleranceDb = 0.5;  // read-back must match within 0.5 dB
constexpr double kDefaultAttenDb = -80.0;          // RF safety: start at -80 dB

// A FrameProducer fills `frame` (interleaved int16, kTotalFrameComplex complex) and
// `fields` (the header for THIS frame) and returns true to transmit, false to stop.
// The producer owns pacing (--pause-ms) and the Ctrl+C flag.
using FrameProducer =
    std::function<bool(std::vector<std::int16_t>& frame,
                       extrf::frame::HeaderFields& fields)>;

struct TxRunReport {
    std::string uri;
    std::string serial_expected;
    std::string serial_readback;
    bool serial_ok = false;
    long long requested_rate = 0;
    long long tx_rate = 0;
    bool sample_rate_ok = false;
    std::uint64_t center_hz = 0;
    double atten_requested = 0.0;
    double atten_readback = 0.0;
    bool atten_ok = false;
    int loopback_readback = -1;
    bool loopback_ok = false;
    std::uint64_t frames_tx = 0;
    std::uint64_t frames_dma_mismatch = 0;
    bool restore_ok = false;
    bool stopped_clean = false;          // tx_stop() -> !tx_running() held
    bool tx_running_after_exit = false;  // must be false (no cyclic TX left)
};

// The raw container bytes the DMA path actually writes: host -> raw with the
// effective TX data format.  This is EXACTLY what the device's tx_dma_payload_sha()
// hashes (mirrors FakePlutoDevice::tx_start_cyclic and the libiio backend).
inline std::string expected_dma_sha(const pluto::Device& dev,
                                    const std::vector<std::int16_t>& frame) {
    const pluto::DataFormatInfo f = dev.tx_data_format();
    std::vector<std::int16_t> dma(frame.size());
    for (std::size_t k = 0; k < frame.size(); ++k)
        dma[k] = pluto::format_convert_host_to_raw(f, frame[k]);
    return sdr::Sha256::hex(dma.data(), dma.size() * sizeof(std::int16_t));
}

// The full TX safety sequence + per-frame loop.  Throws std::runtime_error on any
// safety violation (serial mismatch, rate mismatch, atten > ceiling, atten/loopback
// read-back mismatch, wrong-sized frame, DMA payload SHA mismatch, TX left running);
// the caller maps a device-open failure to its own distinct exit code.
inline TxRunReport run_external_tx(pluto::Device& dev,
                                   const std::string& serial,
                                   double atten_db,
                                   std::uint64_t center_hz,
                                   const FrameProducer& next_frame) {
    TxRunReport rep;
    rep.serial_expected = serial;
    rep.atten_requested = atten_db;
    rep.center_hz = center_hz;
    rep.requested_rate = static_cast<long long>(extrf::frame::kFs);

    // (make_device for the libiio backend already opens in its constructor; the
    //  real open() is NOT idempotent, so only open when not already open.  The
    //  FakePlutoDevice starts closed and is opened here.)
    if (!dev.is_open()) dev.open();

    // 1. serial verify: refuse to emit on any device whose serial does not match
    //    EXACTLY (an empty read-back is equally fatal -- never auto-select).
    rep.serial_readback = dev.serial();
    rep.serial_ok = (!rep.serial_readback.empty() &&
                     rep.serial_readback == rep.serial_expected);
    if (!rep.serial_ok)
        throw std::runtime_error(
            "pluto-external-tx: TX Pluto serial mismatch: got '" +
            rep.serial_readback + "', expected '" + rep.serial_expected +
            "' -- refusing to emit (must match --serial exactly)");

    pluto::DeviceStateGuard guard(dev);

    // 2. sample rate (both phy channels), read-back +/-5 Hz.
    dev.set_sample_rate(rep.requested_rate);
    rep.tx_rate = dev.get_tx_sample_rate();
    rep.sample_rate_ok =
        (std::llabs(rep.tx_rate - rep.requested_rate) <= kSampleRateToleranceHz);
    if (!rep.sample_rate_ok)
        throw std::runtime_error(
            "pluto-external-tx: sample-rate mismatch tx=" +
            std::to_string(rep.tx_rate) +
            " (abs(actual-" + std::to_string(rep.requested_rate) + ") must be <= " +
            std::to_string(kSampleRateToleranceHz) + " Hz)");

    // 3. TX LO.
    dev.set_tx_lo(static_cast<long long>(center_hz));

    // 4. attenuation: hard ceiling, never raised above -40 dB.
    if (atten_db > pluto::kSafeTxCeilingDb)
        throw std::runtime_error(
            "pluto-external-tx: --atten " + std::to_string(atten_db) +
            " dB exceeds the -40 dB safety ceiling (never raised)");
    dev.set_tx_atten(atten_db);
    rep.atten_readback = dev.get_tx_atten();
    rep.atten_ok =
        (std::fabs(rep.atten_readback - atten_db) <= kAttenReadbackToleranceDb);
    if (!rep.atten_ok)
        throw std::runtime_error(
            "pluto-external-tx: TX atten read-back " +
            std::to_string(rep.atten_readback) + " dB != requested " +
            std::to_string(atten_db) + " dB");

    // 5. digital loopback OFF (external RF path), read-back == 0.
    dev.set_loopback(0);
    rep.loopback_readback = dev.get_loopback();
    rep.loopback_ok = (rep.loopback_readback == 0);
    if (!rep.loopback_ok)
        throw std::runtime_error(
            "pluto-external-tx: loopback read-back != 0 (got " +
            std::to_string(rep.loopback_readback) +
            ") -- external RF requires the internal digital loopback OFF");

    // 6. per-frame loop.  Any throw / SIGINT (producer returns false) / device
    //    disconnect unwinds through the catch below and STOPS the TX.
    try {
        std::vector<std::int16_t> frame;
        extrf::frame::HeaderFields fields;
        while (next_frame(frame, fields)) {
            if (frame.size() != extrf::frame::kTotalFrameComplex * 2)
                throw std::runtime_error(
                    "pluto-external-tx: producer returned " +
                    std::to_string(frame.size() / 2) + " complex samples, want " +
                    std::to_string(extrf::frame::kTotalFrameComplex));
            dev.tx_start_cyclic(frame);
            const std::string got = dev.tx_dma_payload_sha();
            const std::string want = expected_dma_sha(dev, frame);
            if (got.empty())
                throw std::runtime_error(
                    "pluto-external-tx: device returned an empty TX DMA payload SHA");
            if (got != want) {
                ++rep.frames_dma_mismatch;
                throw std::runtime_error(
                    "pluto-external-tx: TX DMA payload SHA mismatch: got " + got +
                    ", want " + want);
            }
            ++rep.frames_tx;
        }
    } catch (...) {
        // Abort path: stop the TX (idempotent destroy) + restore, THEN rethrow.
        dev.tx_stop();
        rep.stopped_clean = !dev.tx_running();
        guard.restore();
        rep.restore_ok = guard.restore_ok();
        rep.tx_running_after_exit = dev.tx_running();
        throw;
    }

    // Normal exit: stop TX, restore, and prove no cyclic TX is left running.
    dev.tx_stop();
    rep.stopped_clean = !dev.tx_running();
    guard.restore();
    rep.restore_ok = guard.restore_ok();
    rep.tx_running_after_exit = dev.tx_running();
    if (rep.tx_running_after_exit)
        throw std::runtime_error(
            "pluto-external-tx: cyclic TX left running after tx_stop()");
    return rep;
}

}  // namespace extrf_tx
