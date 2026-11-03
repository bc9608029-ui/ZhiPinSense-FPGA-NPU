// pluto_tx.cpp -- TX safety state machine implementation.

#include "pluto_tx.hpp"

#include <string>

namespace pluto {

PlutoTx::PlutoTx(pluto::Device& dev, TxConfig cfg) : dev_(dev), cfg_(cfg) {}

PlutoTx::~PlutoTx() {
    stop();
}

void PlutoTx::require_exact_d(double got, double want, const char* what) {
    if (got != want) {
        throw std::runtime_error(std::string("pluto_tx: ") + what +
                                 " read-back mismatch (got " + std::to_string(got) +
                                 ", want " + std::to_string(want) + ")");
    }
}

void PlutoTx::prepare() {
    // RF safety gate: an external-RF path (loopback == 0) must be explicitly
    // confirmed.  Digital (1) / internal-RF (2) loopback emits nothing externally.
    if (cfg_.loopback == 0 && !cfg_.confirm_safe_rf_path) {
        throw std::runtime_error(
            "pluto_tx: external-RF path requires --confirm-safe-rf-path");
    }

    // Safety ceiling: TX attenuation is a NEGATIVE number; a larger (less negative)
    // value means MORE output power.  The ceiling freezes the least attenuation ever
    // allowed (-40 dB).  This is an independent, hard-coded limit -- even a caller
    // that already passed --confirm-safe-rf-path can never exceed it.
    if (cfg_.tx_atten_db > kSafeTxCeilingDb) {
        throw std::runtime_error(
            "pluto_tx: TX attenuation " + std::to_string(cfg_.tx_atten_db) +
            " dB exceeds the safety ceiling " + std::to_string(kSafeTxCeilingDb) +
            " dB");
    }

    // 1. ensure TX is off before touching anything RF.  (State save/restore is
    // handled by DeviceStateGuard at the caller, NOT here -- PlutoTx no longer
    // snapshots or restores parameters.)
    dev_.tx_stop();

    // 2. maximum safe attenuation (safety floor), read-back confirmed.
    require_exact_d(dev_.set_tx_atten(kSafeTxAttenDb), kSafeTxAttenDb,
                    "TX attenuation (safe)");

    // 3. RX: manual gain control at a low, deterministic value.
    if (dev_.set_rx_gain_mode("manual") != "manual") {
        throw std::runtime_error("pluto_tx: RX gain mode read-back mismatch");
    }
    require_exact_d(dev_.set_rx_gain(cfg_.rx_gain_db), cfg_.rx_gain_db,
                    "RX gain");

    // 4. align TX/RX LO to the same center frequency.
    const long long rx_lo = dev_.set_rx_lo(static_cast<long long>(cfg_.center_freq_hz));
    const long long tx_lo = dev_.set_tx_lo(static_cast<long long>(cfg_.center_freq_hz));
    const long long want = static_cast<long long>(cfg_.center_freq_hz);
    if (rx_lo != want || tx_lo != want || rx_lo != tx_lo) {
        throw std::runtime_error("pluto_tx: LO alignment read-back mismatch");
    }

    // 5. loopback mode, read-back confirmed.
    if (dev_.set_loopback(cfg_.loopback) != cfg_.loopback) {
        throw std::runtime_error("pluto_tx: loopback mode read-back mismatch");
    }

    // 6. ramp to the working attenuation only if it differs from the safe floor
    // (never jump straight to high power).
    if (cfg_.tx_atten_db != kSafeTxAttenDb) {
        require_exact_d(dev_.set_tx_atten(cfg_.tx_atten_db), cfg_.tx_atten_db,
                        "TX attenuation (working)");
    }

    prepared_ = true;
}

void PlutoTx::start_cyclic() {
    if (!prepared_) {
        throw std::runtime_error("pluto_tx: prepare() must be called first");
    }
    dev_.tx_start_cyclic(cfg_.waveform);
    started_ = true;
}

void PlutoTx::stop() {
    // Always destroy the TX buffer.  Idempotent and safe even after a partial
    // prepare().  (Parameter restore is the caller's DeviceStateGuard.)
    dev_.tx_stop();
    started_ = false;
    prepared_ = false;
}

}  // namespace pluto
