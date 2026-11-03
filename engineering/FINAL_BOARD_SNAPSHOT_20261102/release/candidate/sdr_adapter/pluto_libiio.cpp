// pluto_libiio.cpp -- real ADALM-Pluto backend via libiio (optional compile).
//
// This translation unit is built ONLY with -DSDR_ADAPTER_HAVE_LIBIIO and linked
// against libiio (see build_libiio_gate.sh).  It defines pluto::make_backend()
// to return a real libiio backend, replacing the mock fallback in pluto.hpp.
//
// Behaviour without a Pluto attached (the pre-SDR build gate):
//   * open() scans the USB backend only; with no ADALM-Pluto it throws
//     std::runtime_error("pluto: device not found ...") immediately, so the
//     source fails fast and clearly -- it does NOT crash, hang, or fall back to
//     the mock backend.
//
// The buffer-read path (AD9361 RX via libiio) follows the canonical ADI
// ad9361-iiostream pattern, but is NOT yet verified against hardware (待 Pluto
// 到货后非盲复测).  This file proves compile + link + the "device not found"
// gate -- NOT real acquisition.

#include "pluto.hpp"
#include "iio_backend.hpp"

#include <iio.h>

#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace iio {
namespace {

std::string iio_error(int err) {
    char buf[256] = {0};
    iio_strerror(err, buf, sizeof(buf));
    return std::string(buf);
}

}  // namespace

// Real libiio backend for the ADALM-Pluto / AD9363.
class LibiioBackend : public Backend {
public:
    explicit LibiioBackend(const pluto::Config& cfg) : cfg_(cfg) { open(); }

    ~LibiioBackend() override { close(); }

    RawChunk read(std::size_t max_complex, std::uint64_t /*timeout_ms*/) override {
        RawChunk c;
        if (!is_open()) {
            c.broken = true;
            return c;
        }

        const ssize_t nbytes = iio_buffer_refill(rxbuf_);
        if (nbytes < 0) {
            c.broken = true;  // device read error / stream down
            return c;
        }

        const ptrdiff_t step = iio_buffer_step(rxbuf_);
        if (step <= 0) {
            c.broken = true;
            return c;
        }

        // nbytes spans every enabled channel (I + Q), so nbytes / step = complex
        // samples.  Matches libiio's multichannel-buffer layout; re-verify on HW.
        const std::size_t total = static_cast<std::size_t>(nbytes) /
                                  static_cast<std::size_t>(step);
        const std::size_t take = total < max_complex ? total : max_complex;

        scratch_.clear();
        scratch_.reserve(take * 2);
        char* p = static_cast<char*>(iio_buffer_first(rxbuf_, rx0_i_));
        for (std::size_t k = 0; k < take; ++k) {
            const std::int16_t* s = reinterpret_cast<const std::int16_t*>(
                p + static_cast<ptrdiff_t>(k) * step);
            scratch_.push_back(s[0]);  // I
            scratch_.push_back(s[1]);  // Q (adjacent in the interleaved buffer)
        }

        c.samples = scratch_.data();
        c.samples_available = take;
        return c;
    }

    void reopen() override {
        close();
        open();
    }

    bool is_open() const override { return ctx_ != nullptr && rxbuf_ != nullptr; }

private:
    void open() {
        // Resolve the context URI.  An explicit URI is used as-is; an empty URI
        // scans the USB backend only, so "no device" is reported in milliseconds
        // (no avahi / network discovery latency).  A "ip:..." URI carries
        // libiio's own network connect timeout instead.
        std::string uri = cfg_.uri;
        if (uri.empty()) {
            struct iio_scan_context* scan = iio_create_scan_context("usb", 0);
            if (scan != nullptr) {
                struct iio_context_info** infos = nullptr;
                const ssize_t n = iio_scan_context_get_info_list(scan, &infos);
                if (n > 0 && infos != nullptr) {
                    uri = iio_context_info_get_uri(infos[0]);
                }
                if (infos != nullptr) {
                    iio_context_info_list_free(infos);
                }
                iio_scan_context_destroy(scan);
            }
            if (uri.empty()) {
                throw std::runtime_error(
                    "pluto: device not found (no ADALM-Pluto on USB)");
            }
        }

        ctx_ = iio_create_context_from_uri(uri.c_str());
        if (ctx_ == nullptr) {
            throw std::runtime_error(
                "pluto: device not found (libiio: " + iio_error(errno) + ")");
        }

        phy_ = iio_context_find_device(ctx_, "ad9361-phy");
        rx_ = iio_context_find_device(ctx_, "cf-ad9361-lpc");
        if (phy_ == nullptr || rx_ == nullptr) {
            throw std::runtime_error(
                "pluto: unexpected device (missing ad9361-phy / cf-ad9361-lpc)");
        }

        // ad9361-phy CONTROL channel (the attribute plane): sampling_frequency /
        // rf_bandwidth / gain_control_mode / hardwaregain live HERE, not on the
        // cf-ad9361-lpc DMA device.
        phy_rx_ch_ = iio_device_find_channel(phy_, "voltage0", false);
        if (phy_rx_ch_ == nullptr) {
            throw std::runtime_error(
                "pluto: unexpected device (missing ad9361-phy voltage0 RX)");
        }

        rx0_i_ = iio_device_find_channel(rx_, "voltage0", false);
        rx0_q_ = iio_device_find_channel(rx_, "voltage1", false);
        if (rx0_i_ == nullptr || rx0_q_ == nullptr) {
            throw std::runtime_error(
                "pluto: unexpected device (missing voltage0 / voltage1 RX)");
        }
        iio_channel_enable(rx0_i_);
        iio_channel_enable(rx0_q_);

        // Apply runtime config (best-effort; only when explicitly set).  Attribute
        // names follow the AD9361/Pluto IIO interface: control attributes are
        // CHANNEL attributes on the phy RX control channel.
        if (cfg_.center_freq_hz != 0) {
            struct iio_channel* lo =
                iio_device_find_channel(phy_, "altvoltage0", true);  // RX LO
            if (lo != nullptr) {
                try_attr("RX LO frequency",
                         iio_channel_attr_write_longlong(
                             lo, "frequency",
                             static_cast<long long>(cfg_.center_freq_hz)));
            }
        }
        if (cfg_.sample_rate_hz != 0) {
            try_attr("sampling_frequency",
                     iio_channel_attr_write_longlong(
                         phy_rx_ch_, "sampling_frequency",
                         static_cast<long long>(cfg_.sample_rate_hz)));
        }
        if (cfg_.rf_bandwidth_hz != 0) {
            try_attr("rf_bandwidth",
                     iio_channel_attr_write_longlong(
                         phy_rx_ch_, "rf_bandwidth",
                         static_cast<long long>(cfg_.rf_bandwidth_hz)));
        }
        if (!cfg_.gain_mode.empty()) {
            try_attr("gain_control_mode",
                     static_cast<int>(iio_channel_attr_write(
                         phy_rx_ch_, "gain_control_mode", cfg_.gain_mode.c_str())));
        }
        if (cfg_.gain_db != 0.0) {
            try_attr("hardwaregain",
                     iio_channel_attr_write_double(phy_rx_ch_, "hardwaregain",
                                                   cfg_.gain_db));
        }

        const std::size_t buf_len = cfg_.buffer_length ? cfg_.buffer_length : 1024;
        rxbuf_ = iio_device_create_buffer(rx_, buf_len, false);
        if (rxbuf_ == nullptr) {
            throw std::runtime_error(
                "pluto: cannot create RX buffer (libiio: " + iio_error(errno) +
                ")");
        }
    }

    void close() {
        if (rxbuf_ != nullptr) {
            iio_buffer_destroy(rxbuf_);
            rxbuf_ = nullptr;
        }
        if (ctx_ != nullptr) {
            iio_context_destroy(ctx_);
            ctx_ = nullptr;
        }
        phy_ = nullptr;
        rx_ = nullptr;
        phy_rx_ch_ = nullptr;
        rx0_i_ = nullptr;
        rx0_q_ = nullptr;
    }

    static void try_attr(const char* what, int rc) {
        if (rc < 0) {
            const int code = -rc;
            char buf[256] = {0};
            iio_strerror(code, buf, sizeof(buf));
            std::fprintf(stderr, "pluto: warn: set %s failed: errno=%d (%s)\n",
                         what, code, buf);
        }
    }

    pluto::Config cfg_;
    struct iio_context* ctx_ = nullptr;
    struct iio_device* phy_ = nullptr;
    struct iio_device* rx_ = nullptr;
    struct iio_channel* phy_rx_ch_ = nullptr;  // ad9361-phy voltage0 output=false
    struct iio_channel* rx0_i_ = nullptr;
    struct iio_channel* rx0_q_ = nullptr;
    struct iio_buffer* rxbuf_ = nullptr;
    std::vector<std::int16_t> scratch_;
};

}  // namespace iio

namespace pluto {

iio::Backend* make_backend(const Config& cfg) {
    return new iio::LibiioBackend(cfg);
}

}  // namespace pluto
