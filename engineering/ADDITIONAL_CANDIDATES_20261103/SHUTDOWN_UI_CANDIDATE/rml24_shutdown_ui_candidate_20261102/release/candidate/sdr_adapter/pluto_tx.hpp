#pragma once

// pluto_tx.hpp -- TX safety state machine for single-Pluto self-TX/self-RX.
//
// Enforces the FIXED startup order and the RF-safety guarantees required by the
// task (射频 TX 默认禁用; 异常/Ctrl+C 必须销毁 TX buffer 并恢复参数):
//
//   prepare():     1. tx_stop()                (ensure TX off first)
//                  2. set_tx_atten(max safe)   (-89.75 dB, read-back confirmed)
//                  3. set_rx_gain_mode(manual) + set_rx_gain(low)
//                  4. set_rx_lo / set_tx_lo    (align LOs)
//                  5. set_loopback(mode)
//                  6. (if working atten differs) ramp to working attenuation
//                     -- never above the kSafeTxCeilingDb (-40 dB) ceiling.
//   start_cyclic(): create the cyclic TX buffer and start transmission.
//                   (Starting RX is the caller's LAST step, after this returns.)
//
// stop() (and the RAII destructor) ALWAYS destroys the TX buffer -- including on
// exception unwind and after a signal.  Parameter SAVE/RESTORE is NOT done here:
// the caller wraps the device in a DeviceStateGuard BEFORE any negotiation, so
// restore always returns the device to its ORIGINAL (pre-negotiation) state.
//
// An external-RF path (loopback == 0, signal leaves the antenna port) is refused
// in prepare() unless confirm_safe_rf_path is set, so RF TX stays disabled by
// default.  Digital (1) / internal-RF (2) loopback emits nothing externally.
//
// iCraft-free.

#include "pluto_device.hpp"

#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace pluto {

constexpr double kSafeTxAttenDb = -89.75;   // maximum safe TX attenuation (safety floor)
constexpr double kSafeTxCeilingDb = -40.0;  // least attenuation ever allowed (never exceed)

// AD9364 is a 12-bit converter.  In the host int16 domain (AFTER
// iio_channel_convert / BEFORE iio_channel_convert_inverse) full scale is
// +/-2^11 = 2048.  Tone amplitudes are therefore given in 12-bit counts, NOT the
// old 16-bit 32768 counts -- the old 10000-count tone came back as peak 625 =
// 10000 >> 4 because the 12-bit DAC kept only the top 12 bits of the raw 16-bit
// word that the previous code wrote without iio_channel_convert_inverse.
constexpr int kDacFullScale = 2048;         // 2^11

struct TxConfig {
    std::uint64_t center_freq_hz = 2400000000;  // TX/RX LO (aligned)
    double rx_gain_db = 10.0;                   // low RX gain (manual) for loopback
    double tx_atten_db = kSafeTxAttenDb;        // working level; default = max safe
    int loopback = 1;                           // 0=off(external RF) 1=digital 2=internal RF
    bool confirm_safe_rf_path = false;          // REQUIRED when loopback == 0
    std::vector<std::int16_t> waveform;         // interleaved [I0,Q0,...] int16 tone
};

// Deterministic complex CW tone (cos/sin), amplitude in 12-bit DAC counts.
inline std::vector<std::int16_t> make_cw_tone(double freq_hz, double fs_hz,
                                              std::size_t n,
                                              double amplitude = 1500.0) {
    std::vector<std::int16_t> iq(n * 2);
    const double ph = 2.0 * 3.14159265358979323846 * freq_hz / fs_hz;
    for (std::size_t k = 0; k < n; ++k) {
        const double t = static_cast<double>(k);
        iq[k * 2 + 0] = static_cast<std::int16_t>(
            std::llround(amplitude * std::cos(ph * t)));
        iq[k * 2 + 1] = static_cast<std::int16_t>(
            std::llround(amplitude * std::sin(ph * t)));
    }
    return iq;
}

class PlutoTx {
public:
    // The device must outlive this object.  cfg is copied.
    PlutoTx(pluto::Device& dev, TxConfig cfg);

    ~PlutoTx();   // RAII: stop() (destroy TX buffer)

    PlutoTx(const PlutoTx&) = delete;
    PlutoTx& operator=(const PlutoTx&) = delete;

    // Fixed startup order (stop TX -> safe atten -> RX gain -> align LO ->
    // loopback -> ramp to working atten).  Throws on any read-back mismatch, on an
    // unconfirmed external-RF path, or if the working attenuation exceeds the
    // -40 dB safety ceiling.
    void prepare();

    // Create the cyclic TX buffer and start transmission.  Requires prepare().
    void start_cyclic();

    // Destroy the TX buffer.  Idempotent and safe to call at any time (even after
    // a partial prepare()).  Parameter restore is the caller's DeviceStateGuard.
    void stop();

    bool prepared() const { return prepared_; }
    bool started() const { return started_; }

private:
    void require_exact_d(double got, double want, const char* what);

    pluto::Device& dev_;
    TxConfig cfg_;
    bool prepared_ = false;
    bool started_ = false;
};

}  // namespace pluto
