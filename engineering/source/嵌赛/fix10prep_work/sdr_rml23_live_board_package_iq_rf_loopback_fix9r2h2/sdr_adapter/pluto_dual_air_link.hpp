#pragma once

// pluto_dual_air_link.hpp -- fix10 dual-SDR FAKE RF link + role-split fake devices.
//
// The single-SDR FakePlutoDevice models the EXTERNAL-RF echo INSIDE one instance
// (rf_echo_mode echoes that instance's own tx_waveform_ on read_rx).  That is by
// design a SELF-TX/SELF-RX model and MUST NOT be used to fake a two-Pluto dual-SDR
// path (fix10 red line: "禁止单 Fake 内部 echo 冒充双 SDR").  A dual-SDR path is two
// independent devices connected only through the shared air interface, so this header
// provides:
//
//   * FakeRfLink -- the SHARED air link.  It holds the cyclic TX waveform the TX
//     device last pushed, the TX-on flag, the one complex channel gain/phase, the
//     CFO / SRO / fixed-sample-delay / noise parameters, and the audit counters.
//   * FakeTxDevice : public FakePlutoDevice -- a TX device that, on tx_start_cyclic /
//     tx_stop, mirrors its waveform and TX-on flag INTO the link (and increments the
//     link's tx_start_count).  Its own read_rx is never used by the dual-SDR path.
//   * FakeRxDevice : public FakePlutoDevice -- an RX device whose read_rx synthesizes
//     samples from the LINK (never from its own TX waveform).  TX-off reads the link's
//     pure Gaussian noise floor (the cross-device negative control); TX-on reads the
//     cyclic TX waveform through the link's gain/phase/CFO/SRO/delay + noise.  It keeps
//     its own RX buffer capacity / refill / create / destroy counters so board::capture_contiguous
//     sees a genuine single-refill, capacity-sufficient capture.
//
// The channel model is the EXACT inverse of the fix9r2h2 recovery convention in
// iq_rf_sync_recovery.hpp / iq_rf_frame_layout.hpp:
//   * SRO s = (f_rx - f_tx)/f_tx: a TX sample m lands at RX index m*(1+s) + delay, so
//     RX index a reads TX position (a - delay) / (1+s) -- MULTIPLY on the RX index is
//     the recovery's inverse, so the fake DIVIDES.
//   * CFO +f Hz rotates the RX sample by exp(+j 2*pi*f*a/fs) at RX index a (the
//     recovery de-rotates by exp(-j 2*pi*f*position/fs) at the TX position, whose
//     residual constant phase is absorbed by the LS complex gain).
//   * gain / phase_deg are the single complex scalar; timing_offset is a fixed whole
//     sample delay (== the base FakePlutoDevice's rf_delay role).
//
// iCraft-free and libiio-free; the fake devices subclass FakePlutoDevice, so this
// header never modifies pluto_device.hpp.

#include "pluto_device.hpp"

#include <cmath>
#include <cstdint>
#include <memory>
#include <vector>

namespace pluto {

// Default sample rate (Hz) used by the link CFO model when the RX device has not had
// set_sample_rate() called (the real runner negotiates the rate; host tests may skip it).
constexpr long long kDualLinkDefaultFs = 2560000;

// ---------------------------------------------------------------------------
// FakeRfLink -- the shared air interface between a TX device and an RX device.
// ---------------------------------------------------------------------------
struct FakeRfLink {
    std::vector<std::int16_t> tx_dma_waveform;  // last cyclic TX waveform (host int16 I/Q)
    bool tx_running = false;                     // TX-on flag (mirrors the TX device)
    double gain = 1.0;                           // complex |gain| (linear)
    double phase_deg = 0.0;                      // complex phase (degrees)
    double cfo_hz = 0.0;                         // carrier offset (Hz)
    double sro_ppm = 0.0;                        // sampling-rate offset (ppm)
    std::int64_t timing_offset = 0;              // fixed whole-sample channel delay
    double noise_rms = 0.0;                      // additive Gaussian noise RMS (0 = none)

    // Audit counters.
    std::uint64_t tx_start_count = 0;            // number of tx_start_cyclic pushes
    std::uint64_t main_rx_samples_requested = 0; // largest single read_rx request (== main capture)

    // Deterministic Gaussian noise (same xorshift64+Marsaglia-polar scheme and seed as
    // FakePlutoDevice, so a host test is reproducible).
    std::uint64_t noise_state = 0x243F6A8885A308D3ull;
    double next_gaussian() {
        const auto next_u = [&]() {
            noise_state ^= noise_state << 13;
            noise_state ^= noise_state >> 7;
            noise_state ^= noise_state << 17;
            return static_cast<double>(noise_state >> 11) *
                   (1.0 / 9007199254740992.0);   // 53-bit uniform in [0,1)
        };
        double u1, u2, s;
        do {
            u1 = 2.0 * next_u() - 1.0;
            u2 = 2.0 * next_u() - 1.0;
            s = u1 * u1 + u2 * u2;
        } while (s >= 1.0 || s == 0.0);
        return u1 * std::sqrt(-2.0 * std::log(s) / s);
    }
};

// ---------------------------------------------------------------------------
// FakeTxDevice -- a TX device that pushes its cyclic waveform into a shared link.
// ---------------------------------------------------------------------------
class FakeTxDevice : public FakePlutoDevice {
public:
    explicit FakeTxDevice(std::shared_ptr<FakeRfLink> link) : link_(std::move(link)) {}

    void tx_start_cyclic(const std::vector<std::int16_t>& iq) override {
        FakePlutoDevice::tx_start_cyclic(iq);   // waveform + DMA SHA + push provenance
        link_->tx_dma_waveform = tx_waveform(); // the HOST waveform is what is on the air
        link_->tx_running = true;
        ++link_->tx_start_count;
    }

    void tx_stop() override {
        FakePlutoDevice::tx_stop();
        link_->tx_running = false;
    }

    const std::shared_ptr<FakeRfLink>& link() const { return link_; }

private:
    std::shared_ptr<FakeRfLink> link_;
};

// ---------------------------------------------------------------------------
// FakeRxDevice -- an RX device that reads samples from a shared link.
// ---------------------------------------------------------------------------
class FakeRxDevice : public FakePlutoDevice {
public:
    explicit FakeRxDevice(std::shared_ptr<FakeRfLink> link) : link_(std::move(link)) {}

    iio::RawChunk read_rx(std::size_t max_complex, std::uint64_t) override {
        iio::RawChunk c;
        // Buffer-size ceiling hook (mirrors FakePlutoDevice): a request larger than the
        // ceiling models a failed RX buffer allocation (broken).
        if (rx_max_capacity != 0 && max_complex > rx_max_capacity) {
            c.broken = true;
            return c;
        }
        // RX buffer growth: a larger request destroys the old buffer and allocates a
        // fresh one (matching ensure_rx_buffer in the real backend).
        if (max_complex > my_rx_capacity_) {
            if (my_rx_capacity_ != 0) ++my_rx_destroy_;
            my_rx_capacity_ = max_complex;
            ++my_rx_create_;
        }
        ++my_rx_refill_;
        if (link_->main_rx_samples_requested < max_complex)
            link_->main_rx_samples_requested = max_complex;
        if (rx_timed_out) { c.timed_out = true; return c; }

        const std::size_t n = max_complex;
        my_scratch_.resize(n * 2);
        const auto& w = link_->tx_dma_waveform;
        const std::size_t N = w.size() / 2;
        const bool tx_on = link_->tx_running && N != 0;

        const double sro = link_->sro_ppm * 1e-6;
        const long long fs = (rx_sample_rate() > 0) ? rx_sample_rate() : kDualLinkDefaultFs;
        const double cfo_rad = 2.0 * 3.14159265358979323846 * link_->cfo_hz /
                               static_cast<double>(fs);
        const double ph = link_->phase_deg * 3.14159265358979323846 / 180.0;
        const double gr = link_->gain * std::cos(ph);
        const double gi = link_->gain * std::sin(ph);
        const double noise_rms = link_->noise_rms;

        for (std::size_t k = 0; k < n; ++k) {
            const double a = static_cast<double>(rx_stream_pos_ + k);   // absolute RX index
            double I = 0.0, Q = 0.0;
            if (tx_on) {
                // RX index a -> TX position (a - delay)/(1+sro), cyclic into [0,N).
                const double t_tx = (a - static_cast<double>(link_->timing_offset)) / (1.0 + sro);
                double pm = t_tx - std::floor(t_tx / static_cast<double>(N)) * static_cast<double>(N);
                if (pm < 0.0) pm += static_cast<double>(N);   // floor-mod into [0,N)
                const std::size_t i0 = static_cast<std::size_t>(pm);
                const double frac = pm - static_cast<double>(i0);
                const std::size_t i1 = (i0 + 1) % N;
                const double xI = static_cast<double>(w[i0 * 2 + 0]) * (1.0 - frac) +
                                  static_cast<double>(w[i1 * 2 + 0]) * frac;
                const double xQ = static_cast<double>(w[i0 * 2 + 1]) * (1.0 - frac) +
                                  static_cast<double>(w[i1 * 2 + 1]) * frac;
                // complex gain/phase
                I = xI * gr - xQ * gi;
                Q = xI * gi + xQ * gr;
                // CFO (+f -> +j phase per sample at RX index a)
                const double ca = std::cos(cfo_rad * a);
                const double sa = std::sin(cfo_rad * a);
                const double I2 = I * ca - Q * sa;
                const double Q2 = I * sa + Q * ca;
                I = I2; Q = Q2;
            }
            if (noise_rms > 0.0) {
                I += noise_rms * link_->next_gaussian();
                Q += noise_rms * link_->next_gaussian();
            }
            my_scratch_[k * 2 + 0] = static_cast<std::int16_t>(
                std::max(-32768.0, std::min(32767.0, static_cast<double>(std::llround(I)))));
            my_scratch_[k * 2 + 1] = static_cast<std::int16_t>(
                std::max(-32768.0, std::min(32767.0, static_cast<double>(std::llround(Q)))));
        }
        rx_stream_pos_ += n;
        c.samples = my_scratch_.data();
        c.samples_available = n;
        return c;
    }

    std::size_t rx_buffer_capacity() const override { return my_rx_capacity_; }
    std::uint64_t rx_refill_count() const override { return my_rx_refill_; }
    std::uint64_t rx_buffer_create_count() const override { return my_rx_create_; }
    std::uint64_t rx_buffer_destroy_count() const override { return my_rx_destroy_; }

    bool recreate_rx_buffer() override {
        if (!is_open()) return false;
        if (my_rx_capacity_ != 0) {
            ++my_rx_destroy_;
            my_rx_capacity_ = 0;
        }
        return true;
    }

    // Reset the RX stream position (a host test convenience: re-align the capture start).
    void reset_rx_stream_pos(std::uint64_t pos = 0) { rx_stream_pos_ = pos; }
    std::uint64_t rx_stream_pos() const { return rx_stream_pos_; }
    const std::shared_ptr<FakeRfLink>& link() const { return link_; }

private:
    std::shared_ptr<FakeRfLink> link_;
    std::uint64_t rx_stream_pos_ = 0;
    std::size_t my_rx_capacity_ = 0;
    std::uint64_t my_rx_refill_ = 0;
    std::uint64_t my_rx_create_ = 0;
    std::uint64_t my_rx_destroy_ = 0;
    std::vector<std::int16_t> my_scratch_;
};

}  // namespace pluto
