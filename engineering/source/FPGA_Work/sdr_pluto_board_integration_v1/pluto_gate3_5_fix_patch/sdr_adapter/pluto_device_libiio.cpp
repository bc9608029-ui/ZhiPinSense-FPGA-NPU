// pluto_device_libiio.cpp -- real ADALM-Pluto device (libiio) implementation.
//
// Compiled ONLY with -DSDR_ADAPTER_HAVE_LIBIIO and linked against libiio (see
// board_package/build_on_board.sh / build_libiio_gate.sh).  Defines
// pluto::make_device() to build the real libiio-backed pluto::Device, replacing
// the host-test FakePlutoDevice.
//
// This translation unit proves compile + link + the "device not found" fast-fail
// gate.  The acquisition/TX/attribute-write paths follow the canonical ADI
// ad9361-iiostream + libiio DDS-core pattern and are NOT verified against
// hardware yet (待用户本人上板 Gate 1-5 复测).  Nothing here fabricates a
// device measurement; every setter writes then reads back and returns the actual.
//
// Attribute routing follows contracts/pluto_config_contract.md (executable form
// in iio_attr_routing.hpp):
//   * sampling_frequency / rf_bandwidth / gain_control_mode / hardwaregain are
//     CHANNEL attributes on the ad9361-phy CONTROL channels (voltage0 output=false
//     for RX, voltage0 output=true for TX) -- NOT iio_device_attr_*, NOT the
//     cf-ad9361-*-lpc stream channels.
//   * loopback is a DEVICE DEBUG attribute (Pluto v0.39).
//   * RX and TX sample rate / bandwidth / gain are saved and restored separately.

#include "pluto_device.hpp"
#include "iio_attr_routing.hpp"

#include <iio.h>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace pluto {

namespace {

// Format a libiio errno with BOTH the numeric code and the string, so a board
// log can tell "which code" and "why" (Gate 1 requirement).  `err` may be the
// negative errno libiio returns (<0); the helper normalises it.
std::string iio_errstr(int err) {
    const int code = err < 0 ? -err : err;
    char buf[256] = {0};
    iio_strerror(code, buf, sizeof(buf));
    return "errno=" + std::to_string(code) + " (" + buf + ")";
}

// An attribute failure with BOTH numeric errno and string.
std::string iio_fail(const char* what, int neg_errno) {
    return std::string(what) + " failed: " + iio_errstr(neg_errno);
}

// Write a longlong CHANNEL attribute and return the value read back.  Throws on
// a hard I/O error, with errno code + string.
long long wr_ll(iio_channel* ch, const char* attr, long long v) {
    const int rc = iio_channel_attr_write_longlong(ch, attr, v);
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: set " + std::string(attr)).c_str(), rc));
    }
    long long got = 0;
    const int rr = iio_channel_attr_read_longlong(ch, attr, &got);
    if (rr < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(), rr));
    }
    return got;
}

// Write a longlong DEVICE DEBUG attribute (loopback) and read back.
long long wr_dbg_ll(iio_device* d, const char* attr, long long v) {
    const int rc = iio_device_debug_attr_write_longlong(d, attr, v);
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: set " + std::string(attr)).c_str(), rc));
    }
    long long got = 0;
    const int rr = iio_device_debug_attr_read_longlong(d, attr, &got);
    if (rr < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(), rr));
    }
    return got;
}

double wr_d(iio_channel* ch, const char* attr, double v) {
    const int rc = iio_channel_attr_write_double(ch, attr, v);
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: set " + std::string(attr)).c_str(), rc));
    }
    double got = 0.0;
    const int rr = iio_channel_attr_read_double(ch, attr, &got);
    if (rr < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(), rr));
    }
    return got;
}

std::string wr_s(iio_channel* ch, const char* attr, const std::string& v) {
    const ssize_t rc = iio_channel_attr_write(ch, attr, v.c_str());
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: set " + std::string(attr)).c_str(),
                     static_cast<int>(rc)));
    }
    char buf[256] = {0};
    const ssize_t rr = iio_channel_attr_read(ch, attr, buf, sizeof(buf));
    if (rr < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(),
                     static_cast<int>(rr)));
    }
    return std::string(buf);
}

// Read-only helpers (no side effects), for save_params() and getters.  All throw
// with errno code + string on failure.
long long rd_ll(iio_channel* ch, const char* attr) {
    long long v = 0;
    const int rc = iio_channel_attr_read_longlong(ch, attr, &v);
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(), rc));
    }
    return v;
}

long long rd_dbg_ll(iio_device* d, const char* attr) {
    long long v = 0;
    const int rc = iio_device_debug_attr_read_longlong(d, attr, &v);
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(), rc));
    }
    return v;
}

double rd_d(iio_channel* ch, const char* attr) {
    double v = 0.0;
    const int rc = iio_channel_attr_read_double(ch, attr, &v);
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(), rc));
    }
    return v;
}

std::string rd_s(iio_channel* ch, const char* attr) {
    char buf[256] = {0};
    const int rc = iio_channel_attr_read(ch, attr, buf, sizeof(buf));
    if (rc < 0) {
        throw std::runtime_error(
            iio_fail(("pluto: read " + std::string(attr)).c_str(), rc));
    }
    return std::string(buf);
}

// Copy a stream channel's data format (iio_channel_get_data_format) into the
// structured DataFormatInfo.  This is queried, never assumed.
DataFormatInfo query_fmt(iio_channel* ch) {
    DataFormatInfo out;
    const struct iio_data_format* f = iio_channel_get_data_format(ch);
    if (f != nullptr) {
        out.length_bits = f->length;
        out.bits = f->bits;
        out.shift = f->shift;
        out.is_signed = f->is_signed;
        out.is_fully_defined = f->is_fully_defined;
        out.is_be = f->is_be;
        out.repeat = f->repeat;
    }
    return out;
}

}  // namespace

class LibiioDevice : public Device {
public:
    explicit LibiioDevice(std::string uri) : uri_(std::move(uri)) { open(); }

    ~LibiioDevice() override { close(); }

    bool is_open() const override { return ctx_ != nullptr; }

    void open() override {
        std::string uri = uri_;
        if (uri.empty()) {
            struct iio_scan_context* scan = iio_create_scan_context("usb", 0);
            if (scan != nullptr) {
                struct iio_context_info** infos = nullptr;
                const ssize_t n = iio_scan_context_get_info_list(scan, &infos);
                if (n > 0 && infos != nullptr) {
                    uri = iio_context_info_get_uri(infos[0]);
                }
                if (infos != nullptr) iio_context_info_list_free(infos);
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
                "pluto: device not found (libiio: " + iio_errstr(errno) + ")");
        }

        phy_ = iio_context_find_device(ctx_, "ad9361-phy");
        rx_ = iio_context_find_device(ctx_, "cf-ad9361-lpc");
        tx_ = iio_context_find_device(ctx_, "cf-ad9361-dds-core-lpc");
        if (phy_ == nullptr || rx_ == nullptr || tx_ == nullptr) {
            throw std::runtime_error("pluto: unexpected device (missing phy/rx/tx)");
        }

        // ---- ad9361-phy CONTROL channels (attribute plane) -----------------
        phy_rx_ch_ = iio_device_find_channel(phy_, "voltage0", false);  // RX control
        phy_tx_ch_ = iio_device_find_channel(phy_, "voltage0", true);   // TX control
        rx_lo_ch_ = iio_device_find_channel(phy_, "altvoltage0", true); // RX LO
        tx_lo_ch_ = iio_device_find_channel(phy_, "altvoltage1", true); // TX LO

        // ---- stream (DMA) channels: both I and Q enabled -------------------
        rx_i_ch_ = iio_device_find_channel(rx_, "voltage0", false);
        rx_q_ch_ = iio_device_find_channel(rx_, "voltage1", false);
        tx_i_ch_ = iio_device_find_channel(tx_, "voltage0", true);
        tx_q_ch_ = iio_device_find_channel(tx_, "voltage1", true);

        if (phy_rx_ch_ == nullptr || phy_tx_ch_ == nullptr ||
            rx_lo_ch_ == nullptr || tx_lo_ch_ == nullptr ||
            rx_i_ch_ == nullptr || rx_q_ch_ == nullptr ||
            tx_i_ch_ == nullptr || tx_q_ch_ == nullptr) {
            throw std::runtime_error("pluto: unexpected device (missing channel)");
        }

        iio_channel_enable(rx_i_ch_);
        iio_channel_enable(rx_q_ch_);
        iio_channel_enable(tx_i_ch_);
        iio_channel_enable(tx_q_ch_);

        // Tie this backend to the frozen routing table: every attribute we will
        // touch must resolve to a control target we actually hold a handle for.
        verify_routing();

        // NOTE: the RX buffer is created LAZILY on the first read_rx(), AFTER the
        // sample rate / bandwidth / gain have been set.  Creating it here (before
        // the control plane is configured) can fail with EBUSY.
    }

    void close() override {
        if (txbuf_ != nullptr) {
            iio_buffer_destroy(txbuf_);
            txbuf_ = nullptr;
        }
        if (rxbuf_ != nullptr) {
            iio_buffer_destroy(rxbuf_);
            rxbuf_ = nullptr;
        }
        if (ctx_ != nullptr) {
            iio_context_destroy(ctx_);
            ctx_ = nullptr;
        }
        phy_ = rx_ = tx_ = nullptr;
        phy_rx_ch_ = phy_tx_ch_ = rx_lo_ch_ = tx_lo_ch_ = nullptr;
        rx_i_ch_ = rx_q_ch_ = tx_i_ch_ = tx_q_ch_ = nullptr;
    }

    // ---- attributes (write + read back) -----------------------------------

    // sampling_frequency lives on BOTH phy control channels (RX + TX).  We set
    // both and return the RX read-back as the negotiated value.
    long long set_sample_rate(long long hz) override {
        const long long rx = wr_ll(phy_rx_ch_, "sampling_frequency", hz);
        (void)wr_ll(phy_tx_ch_, "sampling_frequency", hz);
        return rx;
    }
    long long get_rx_sample_rate() const override {
        return rd_ll(phy_rx_ch_, "sampling_frequency");
    }
    long long get_tx_sample_rate() const override {
        return rd_ll(phy_tx_ch_, "sampling_frequency");
    }
    long long set_rx_lo(long long hz) override {
        return wr_ll(rx_lo_ch_, "frequency", hz);
    }
    long long set_tx_lo(long long hz) override {
        return wr_ll(tx_lo_ch_, "frequency", hz);
    }
    long long get_rx_lo() const override {
        return rd_ll(rx_lo_ch_, "frequency");
    }
    long long get_tx_lo() const override {
        return rd_ll(tx_lo_ch_, "frequency");
    }
    long long set_rx_bw(long long hz) override {
        return wr_ll(phy_rx_ch_, "rf_bandwidth", hz);
    }
    long long set_tx_bw(long long hz) override {
        return wr_ll(phy_tx_ch_, "rf_bandwidth", hz);
    }
    std::string set_rx_gain_mode(const std::string& mode) override {
        return wr_s(phy_rx_ch_, "gain_control_mode", mode);
    }
    double set_rx_gain(double db) override {
        return wr_d(phy_rx_ch_, "hardwaregain", db);
    }
    double set_tx_atten(double db) override {
        return wr_d(phy_tx_ch_, "hardwaregain", db);
    }
    int set_loopback(int mode) override {
        return static_cast<int>(wr_dbg_ll(phy_, "loopback", mode));
    }

    long long get_rx_bw() const override {
        return rd_ll(phy_rx_ch_, "rf_bandwidth");
    }
    long long get_tx_bw() const override {
        return rd_ll(phy_tx_ch_, "rf_bandwidth");
    }
    std::string get_rx_gain_mode() const override {
        return rd_s(phy_rx_ch_, "gain_control_mode");
    }
    double get_rx_gain() const override {
        return rd_d(phy_rx_ch_, "hardwaregain");
    }
    double get_tx_atten() const override {
        return rd_d(phy_tx_ch_, "hardwaregain");
    }
    int get_loopback() const override {
        return static_cast<int>(rd_dbg_ll(phy_, "loopback"));
    }

    DataFormatInfo rx_data_format() const override {
        return query_fmt(rx_i_ch_);
    }
    DataFormatInfo tx_data_format() const override {
        return query_fmt(tx_i_ch_);
    }

    void save_params() override {
        saved_.captured = true;
        saved_.rx_lo_hz = rd_ll(rx_lo_ch_, "frequency");
        saved_.tx_lo_hz = rd_ll(tx_lo_ch_, "frequency");
        saved_.rx_sample_rate_hz = rd_ll(phy_rx_ch_, "sampling_frequency");
        saved_.tx_sample_rate_hz = rd_ll(phy_tx_ch_, "sampling_frequency");
        saved_.rx_bw_hz = rd_ll(phy_rx_ch_, "rf_bandwidth");
        saved_.tx_bw_hz = rd_ll(phy_tx_ch_, "rf_bandwidth");
        saved_.rx_gain_mode = rd_s(phy_rx_ch_, "gain_control_mode");
        saved_.rx_gain_db = rd_d(phy_rx_ch_, "hardwaregain");
        saved_.tx_atten_db = rd_d(phy_tx_ch_, "hardwaregain");
        saved_.loopback = static_cast<int>(rd_dbg_ll(phy_, "loopback"));
    }

    bool restore_params() override {
        if (!saved_.captured) return true;
        // Best-effort restore: a cleanup path must not throw, so warn on failure.
        // The return value tells the caller (DeviceStateGuard) whether EVERY write
        // succeeded, so it can print restore_result=PASS|FAIL honestly.
        bool ok = true;
        const auto warn = [&ok](const char* what) {
            std::fprintf(stderr, "pluto: restore: %s failed\n", what);
            ok = false;
        };
        if (iio_channel_attr_write_longlong(rx_lo_ch_, "frequency", saved_.rx_lo_hz) < 0)
            warn("RX LO");
        if (iio_channel_attr_write_longlong(tx_lo_ch_, "frequency", saved_.tx_lo_hz) < 0)
            warn("TX LO");
        // RX and TX sample rate are distinct attributes; restore each separately.
        if (iio_channel_attr_write_longlong(phy_rx_ch_, "sampling_frequency",
                                            saved_.rx_sample_rate_hz) < 0)
            warn("RX sample rate");
        if (iio_channel_attr_write_longlong(phy_tx_ch_, "sampling_frequency",
                                            saved_.tx_sample_rate_hz) < 0)
            warn("TX sample rate");
        if (!saved_.rx_gain_mode.empty() &&
            iio_channel_attr_write(phy_rx_ch_, "gain_control_mode",
                                   saved_.rx_gain_mode.c_str()) < 0)
            warn("gain mode");
        if (iio_channel_attr_write_double(phy_rx_ch_, "hardwaregain", saved_.rx_gain_db) < 0)
            warn("RX gain");
        if (iio_channel_attr_write_double(phy_tx_ch_, "hardwaregain", saved_.tx_atten_db) < 0)
            warn("TX atten");
        if (iio_device_debug_attr_write_longlong(phy_, "loopback", saved_.loopback) < 0)
            warn("loopback");
        if (saved_.rx_bw_hz != 0 &&
            iio_channel_attr_write_longlong(phy_rx_ch_, "rf_bandwidth", saved_.rx_bw_hz) < 0)
            warn("RX bw");
        if (saved_.tx_bw_hz != 0 &&
            iio_channel_attr_write_longlong(phy_tx_ch_, "rf_bandwidth", saved_.tx_bw_hz) < 0)
            warn("TX bw");
        return ok;
    }

    void tx_start_cyclic(const std::vector<std::int16_t>& iq) override {
        if (iq.size() < 2 || iq.size() % 2 != 0) {
            throw std::runtime_error("pluto: TX waveform must be interleaved I/Q");
        }
        tx_stop();
        const std::size_t n_complex = iq.size() / 2;
        txbuf_ = iio_device_create_buffer(tx_, n_complex, true);  // cyclic
        if (txbuf_ == nullptr) {
            throw std::runtime_error(
                "pluto: cannot create TX buffer (libiio: " + iio_errstr(errno) + ")");
        }
        const ptrdiff_t step = iio_buffer_step(txbuf_);
        // Both I and Q are enabled (voltage0 + voltage1, int16): the interleaved
        // frame stride MUST be 2 * sizeof(int16) = 4 bytes, or the I/Q layout is
        // not what this code assumes.
        if (step != static_cast<ptrdiff_t>(2 * sizeof(std::int16_t))) {
            iio_buffer_destroy(txbuf_);
            txbuf_ = nullptr;
            throw std::runtime_error(
                "pluto: unexpected TX buffer step (not interleaved int16)");
        }

        // Per-channel first address (I = voltage0, Q = voltage1).  The host int16
        // sample is converted to the device's 12-bit format with
        // iio_channel_convert_inverse -- NOT a raw int16 memcpy, which is what
        // dropped the old 10000-count tone to peak 625 (the 12-bit DAC took only
        // the top 12 bits of the raw 16-bit word).
        char* p_i = static_cast<char*>(iio_buffer_first(txbuf_, tx_i_ch_));
        char* p_q = static_cast<char*>(iio_buffer_first(txbuf_, tx_q_ch_));
        for (std::size_t k = 0; k < n_complex; ++k) {
            iio_channel_convert_inverse(tx_i_ch_, p_i + static_cast<ptrdiff_t>(k) * step,
                                        &iq[k * 2 + 0]);
            iio_channel_convert_inverse(tx_q_ch_, p_q + static_cast<ptrdiff_t>(k) * step,
                                        &iq[k * 2 + 1]);
        }

        const ssize_t pushed = iio_buffer_push(txbuf_);
        if (pushed < 0) {
            iio_buffer_destroy(txbuf_);
            txbuf_ = nullptr;
            throw std::runtime_error(
                "pluto: TX push failed (libiio: " +
                iio_errstr(static_cast<int>(pushed)) + ")");
        }
        // Report the actual pushed byte count + the I/Q scan order/offset, so a
        // board log proves the TX buffer really was written (not just "not < 0").
        std::fprintf(stderr,
                     "pluto: TX cyclic pushed=%zd bytes (%zu complex, step=%td "
                     "bytes, I/Q offset=%td bytes, I=voltage0 Q=voltage1)\n",
                     static_cast<ssize_t>(pushed), n_complex,
                     static_cast<ptrdiff_t>(step), static_cast<ptrdiff_t>(p_q - p_i));
    }

    void tx_stop() override {
        if (txbuf_ != nullptr) {
            iio_buffer_destroy(txbuf_);
            txbuf_ = nullptr;
        }
    }

    iio::RawChunk read_rx(std::size_t max_complex, std::uint64_t timeout_ms) override {
        iio::RawChunk c;
        if (!is_open()) {
            c.broken = true;
            return c;
        }
        if (!ensure_rx_buffer()) {
            c.broken = true;
            return c;
        }

        // The caller's timeout is honoured, never silently ignored: arm the
        // libiio context timeout before refill, and fail closed if it cannot be
        // armed.  0 (adapter default) -> 1000 ms; clamp to libiio's sane range.
        const unsigned tmo = (timeout_ms == 0)
                                 ? 1000u
                                 : (timeout_ms > 3600000u
                                        ? 3600000u
                                        : static_cast<unsigned>(timeout_ms));
        if (iio_context_set_timeout(ctx_, tmo) < 0) {
            c.broken = true;   // cannot arm the timeout -> refuse to block blind
            return c;
        }

        const ssize_t nbytes = iio_buffer_refill(rxbuf_);
        if (nbytes < 0) {
            const int err = static_cast<int>(-nbytes);
            if (err == ETIMEDOUT) {
                c.timed_out = true;
            } else {
                c.broken = true;
            }
            return c;
        }

        const ptrdiff_t step = iio_buffer_step(rxbuf_);
        if (step != static_cast<ptrdiff_t>(2 * sizeof(std::int16_t))) {
            c.broken = true;   // not the interleaved int16 I/Q layout we assume
            return c;
        }

        const std::size_t total = static_cast<std::size_t>(nbytes) /
                                  static_cast<std::size_t>(step);
        const std::size_t take = total < max_complex ? total : max_complex;
        scratch_.resize(take * 2);
        // Per-channel convert: iio_channel_convert applies each channel's 12-bit
        // data format (shift/sign) to the raw sample, so the returned int16 is the
        // actual ADC value (12-bit, +/-2^11), NOT a raw container word.  I comes
        // from voltage0, Q from voltage1 -- this fixes the container-format and
        // I/Q-orientation errors that produced peak=625 / ratio=0.0177 on board.
        char* p_i = static_cast<char*>(iio_buffer_first(rxbuf_, rx_i_ch_));
        char* p_q = static_cast<char*>(iio_buffer_first(rxbuf_, rx_q_ch_));
        for (std::size_t k = 0; k < take; ++k) {
            std::int16_t iv = 0, qv = 0;
            iio_channel_convert(rx_i_ch_, &iv,
                                p_i + static_cast<ptrdiff_t>(k) * step);
            iio_channel_convert(rx_q_ch_, &qv,
                                p_q + static_cast<ptrdiff_t>(k) * step);
            scratch_[k * 2 + 0] = iv;
            scratch_[k * 2 + 1] = qv;
        }
        c.samples = scratch_.data();
        c.samples_available = take;
        return c;
    }

private:
    // Resolve a routing target to its concrete channel handle (channel APIs).
    iio_channel* ch_for(sdr::AttrTarget t) const {
        switch (t) {
            case sdr::AttrTarget::kPhyRxCh: return phy_rx_ch_;
            case sdr::AttrTarget::kPhyTxCh: return phy_tx_ch_;
            case sdr::AttrTarget::kRxLo:    return rx_lo_ch_;
            case sdr::AttrTarget::kTxLo:    return tx_lo_ch_;
            default: return nullptr;   // kPhyDebug uses the debug-attr path
        }
    }

    // Lazy RX buffer: created after the control plane is configured (first
    // read_rx), which avoids the EBUSY that an eager create-before-config hits.
    bool ensure_rx_buffer() {
        if (rxbuf_ != nullptr) return true;
        rxbuf_ = iio_device_create_buffer(rx_, 1024, false);
        if (rxbuf_ == nullptr) {
            std::fprintf(stderr, "pluto: cannot create RX buffer: %s\n",
                         iio_errstr(errno).c_str());
            return false;
        }
        return true;
    }

    // Assert the frozen routing table matches the handles we hold, so the
    // attribute->target map (iio_attr_routing.hpp) cannot silently drift from
    // the channels opened above.
    void verify_routing() {
        struct Check { const char* name; sdr::AttrDir dir; };
        static const Check kChecks[] = {
            {"sampling_frequency", sdr::AttrDir::kRx},
            {"sampling_frequency", sdr::AttrDir::kTx},
            {"rf_bandwidth",       sdr::AttrDir::kRx},
            {"rf_bandwidth",       sdr::AttrDir::kTx},
            {"gain_control_mode",  sdr::AttrDir::kRx},
            {"hardwaregain",       sdr::AttrDir::kRx},
            {"hardwaregain",       sdr::AttrDir::kTx},
            {"frequency",          sdr::AttrDir::kRx},
            {"frequency",          sdr::AttrDir::kTx},
            {"loopback",           sdr::AttrDir::kNone},
        };
        for (const Check& c : kChecks) {
            sdr::AttrRoute r;
            if (!sdr::route_ad9361_attr(c.name, c.dir, &r)) {
                throw std::runtime_error("pluto: internal: unrouted attribute");
            }
            if (r.target == sdr::AttrTarget::kPhyDebug) {
                if (phy_ == nullptr)
                    throw std::runtime_error("pluto: internal: missing phy debug");
            } else if (ch_for(r.target) == nullptr) {
                throw std::runtime_error("pluto: internal: missing channel handle");
            }
        }
    }

    std::string uri_;
    struct iio_context* ctx_ = nullptr;
    struct iio_device* phy_ = nullptr;    // ad9361-phy
    struct iio_device* rx_ = nullptr;     // cf-ad9361-lpc (RX DMA)
    struct iio_device* tx_ = nullptr;     // cf-ad9361-dds-core-lpc (TX DMA)
    struct iio_channel* phy_rx_ch_ = nullptr;  // voltage0 output=false (RX control)
    struct iio_channel* phy_tx_ch_ = nullptr;  // voltage0 output=true  (TX control)
    struct iio_channel* rx_lo_ch_ = nullptr;   // altvoltage0 output=true
    struct iio_channel* tx_lo_ch_ = nullptr;   // altvoltage1 output=true
    struct iio_channel* rx_i_ch_ = nullptr;    // cf-ad9361-lpc voltage0
    struct iio_channel* rx_q_ch_ = nullptr;    // cf-ad9361-lpc voltage1
    struct iio_channel* tx_i_ch_ = nullptr;    // dds-core voltage0
    struct iio_channel* tx_q_ch_ = nullptr;    // dds-core voltage1
    struct iio_buffer* rxbuf_ = nullptr;
    struct iio_buffer* txbuf_ = nullptr;
    std::vector<std::int16_t> scratch_;
    DeviceParams saved_;
};

Device* make_device(const std::string& uri) {
    return new LibiioDevice(uri);
}

}  // namespace pluto
