#pragma once

// pluto_device.hpp -- full ADALM-Pluto device-control abstraction (TX + RX +
// parameter save/restore), plus a scriptable fake for host tests.
//
// This is the device layer for the single-Pluto self-TX/self-RX board bring-up
// (task 39e5 first batch, Gate 1-5).  It is a superset of the read-only
// iio::Backend in iio_backend.hpp / pluto_libiio.cpp: in addition to RX reads it
// controls TX (cyclic buffer), every AD9361 attribute we touch (sample rate, RX/TX
// LO, RX/TX bandwidth, RX gain mode/gain, TX attenuation, loopback), and it can
// snapshot and restore the whole set (the RF-safety sequence requires this).
//
// Every setter WRITES then READS BACK and returns the value actually read back;
// the caller (sample_rate_negotiate / pluto_tx) decides whether a mismatch is
// fatal.  Nothing here silently approximates a value.
//
// Build modes:
//   * default (no libiio)        -> only FakePlutoDevice is available (host test).
//   * -DSDR_ADAPTER_HAVE_LIBIIO  -> pluto_device_libiio.cpp defines
//                                    pluto::make_device() to build the real
//                                    libiio-backed Device (compile+link gate; the
//                                    "device not found" fast-fail lives there).
//
// iCraft-free.

#include "iio_backend.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <set>
#include <string>
#include <vector>

namespace pluto {

// A captured snapshot of the device parameters, for save/restore.  RX and TX
// sample rate are kept separately (the AD9361 exposes them as distinct channel
// attributes and this code does not assume they are always equal).
struct DeviceParams {
    bool captured = false;
    long long rx_lo_hz = 0;
    long long tx_lo_hz = 0;
    long long rx_sample_rate_hz = 0;
    long long tx_sample_rate_hz = 0;
    long long rx_bw_hz = 0;
    long long tx_bw_hz = 0;
    std::string rx_gain_mode;
    double rx_gain_db = 0.0;
    double tx_atten_db = 0.0;
    int loopback = 0;
};

// AD9361/AD9364 IIO stream data format (iio_channel_get_data_format).  The
// AD9364 is a 12-bit converter carried inside a 16-bit signed container.  `shift`
// says where the 12 significant bits sit within the 16-bit word: 0 = LSB-aligned
// (right-justified), 4 = MSB-aligned (left-justified).  This is QUERIED from the
// device at open time, never assumed.  The default member values describe the
// canonical AD9364 layout (12-bit @ shift 4); board runs print the actual values.
struct DataFormatInfo {
    std::uint32_t length_bits = 16;  // bits per sample in the container
    std::uint32_t bits = 12;         // significant bits (12 for AD9364)
    std::uint32_t shift = 4;         // LSB offset of the significant bits
    bool is_signed = true;
    bool is_fully_defined = false;   // if true, libiio does NOT sign-extend
    bool is_be = false;              // big-endian byte order
    std::uint32_t repeat = 1;        // samples per frame (1)
};

// Human-readable one-line description of a stream data format.
inline std::string describe_data_format(const DataFormatInfo& f) {
    std::string s = std::to_string(f.length_bits) + "b/" +
                    std::to_string(f.bits) + "b";
    s += f.shift ? (" shift+" + std::to_string(f.shift)) : " shift+0";
    s += f.is_signed ? " signed" : " unsigned";
    s += f.is_fully_defined ? " fully-defined" : " sign-extended";
    s += f.is_be ? " BE" : " LE";
    s += " repeat=" + std::to_string(f.repeat);
    return s;
}

// Abstract device control.  Real implementation lives in pluto_device_libiio.cpp
// (libiio); FakePlutoDevice below is for offline host tests.
class Device {
public:
    virtual ~Device() = default;

    // Lifecycle.  open() throws std::runtime_error on failure (no device, wrong
    // device, cannot create buffer); close() is idempotent.
    virtual bool is_open() const = 0;
    virtual void open() = 0;
    virtual void close() = 0;

    // ---- attributes (write + read back; return the actual read-back value) ----
    // set_sample_rate writes the sampling_frequency on BOTH the RX and TX phy
    // control channels and returns the RX read-back (the negotiated value).
    virtual long long set_sample_rate(long long hz) = 0;
    virtual long long get_rx_sample_rate() const = 0;
    virtual long long get_tx_sample_rate() const = 0;
    virtual long long set_rx_lo(long long hz) = 0;
    virtual long long set_tx_lo(long long hz) = 0;
    virtual long long get_rx_lo() const = 0;
    virtual long long get_tx_lo() const = 0;
    virtual long long set_rx_bw(long long hz) = 0;
    virtual long long set_tx_bw(long long hz) = 0;
    virtual std::string set_rx_gain_mode(const std::string& mode) = 0;
    virtual double set_rx_gain(double db) = 0;
    virtual double set_tx_atten(double db) = 0;   // attenuation (dB), negative
    virtual int set_loopback(int mode) = 0;       // 0=off 1=digital 2=rf

    // Read-only getters (no side effects).  Used to confirm restore succeeded
    // and to print the effective device state after a run.
    virtual long long get_rx_bw() const = 0;
    virtual long long get_tx_bw() const = 0;
    virtual std::string get_rx_gain_mode() const = 0;
    virtual double get_rx_gain() const = 0;
    virtual double get_tx_atten() const = 0;
    virtual int get_loopback() const = 0;

    // RX/TX stream data format (queried from the device; see DataFormatInfo).
    virtual DataFormatInfo rx_data_format() const = 0;
    virtual DataFormatInfo tx_data_format() const = 0;

    // Snapshot the current attributes, and later write them all back.
    virtual void save_params() = 0;
    // Write the snapshot back.  Returns true if every write succeeded (no
    // best-effort warning); false if at least one restore write failed.  Never
    // throws: the cleanup path must not propagate.
    virtual bool restore_params() = 0;

    // ---- TX cyclic buffer ----
    // Load `iq` (interleaved int16 [I0,Q0,...]) into a cyclic TX buffer and start
    // continuous transmission.  A second call replaces the buffer.
    virtual void tx_start_cyclic(const std::vector<std::int16_t>& iq) = 0;
    // Destroy the TX buffer and stop transmission (must be safe to call twice).
    virtual void tx_stop() = 0;

    // ---- RX read (reuses iio::RawChunk semantics) ----
    virtual iio::RawChunk read_rx(std::size_t max_complex,
                                  std::uint64_t timeout_ms) = 0;

    // ---- RX buffer diagnostics ----
    // The RX buffer is sized to the largest request ever made (not a hardcoded
    // 1024), and every iio_buffer_refill increments the count.  Gate 5 uses these
    // to PROVE its source samples came from ONE contiguous refill (refill_count
    // advance of exactly 1 and capacity >= the requested amount), so it never
    // concatenates phase-discontinuous blocks and pretends they are a continuous
    // stream.
    virtual std::size_t rx_buffer_capacity() const = 0;
    virtual std::uint64_t rx_refill_count() const = 0;

    // ---- TX/RX buffer lifecycle diagnostics (Gate 10) ----------------------
    // How many times the cyclic TX buffer and the RX buffer were created /
    // destroyed.  Gate 10 prints these per class to PROVE the old cyclic TX
    // buffer is destroyed (and a fresh one pushed) before each class, and that
    // the RX buffer is recreated after a class switch -- so a stale buffer can
    // never be silently reused across classes (the "first class passes, the rest
    // fail" failure signature).
    virtual std::uint64_t tx_buffer_create_count() const = 0;
    virtual std::uint64_t tx_buffer_destroy_count() const = 0;
    virtual std::uint64_t rx_buffer_create_count() const = 0;
    virtual std::uint64_t rx_buffer_destroy_count() const = 0;

    // Destroy and forget the current RX buffer so the NEXT read_rx() allocates a
    // fresh one (forcing libiio to re-arm the DMA, not reuse a stale refill).
    // Returns false only when the device is not open; idempotent (safe when there
    // is no buffer yet).  A settled RX refill then returns only post-switch data.
    virtual bool recreate_rx_buffer() = 0;
};

// ---------------------------------------------------------------------------
// FakePlutoDevice -- scriptable in-memory device for host tests (no libiio).
// ---------------------------------------------------------------------------
class FakePlutoDevice : public Device {
public:
    FakePlutoDevice() = default;

    bool is_open() const override { return open_; }
    void open() override { open_ = true; log_.push_back("open"); }
    void close() override {
        open_ = false;
        if (tx_buffer_created_) ++tx_buffer_destroy_count_;
        if (rx_buffer_capacity_ != 0) ++rx_buffer_destroy_count_;
        tx_running_ = false;
        tx_buffer_created_ = false;
        rx_buffer_capacity_ = 0;
        log_.push_back("close");
    }

    long long set_sample_rate(long long hz) override {
        log_.push_back("set_sample_rate:" + std::to_string(hz));
        const long long coerced = reject_sample_rates.count(hz) ? hz - 1 : hz;
        // Model both the RX and TX phy control channels (distinct attributes).
        rx_sample_rate_ = coerced;
        tx_sample_rate_ = coerced;
        return rx_sample_rate_;
    }
    long long get_rx_sample_rate() const override { return rx_sample_rate_; }
    long long get_tx_sample_rate() const override { return tx_sample_rate_; }

    long long set_rx_lo(long long hz) override {
        log_.push_back("set_rx_lo:" + std::to_string(hz));
        rx_lo_ = hz;
        return rx_lo_;
    }
    long long set_tx_lo(long long hz) override {
        log_.push_back("set_tx_lo:" + std::to_string(hz));
        tx_lo_ = hz;
        return tx_lo_;
    }
    long long get_rx_lo() const override { return rx_lo_; }
    long long get_tx_lo() const override { return tx_lo_; }

    long long set_rx_bw(long long hz) override {
        log_.push_back("set_rx_bw:" + std::to_string(hz));
        rx_bw_ = hz;
        return rx_bw_;
    }
    long long set_tx_bw(long long hz) override {
        log_.push_back("set_tx_bw:" + std::to_string(hz));
        tx_bw_ = hz;
        return tx_bw_;
    }
    std::string set_rx_gain_mode(const std::string& mode) override {
        log_.push_back("set_rx_gain_mode:" + mode);
        rx_gain_mode_ = mode;
        return rx_gain_mode_;
    }
    double set_rx_gain(double db) override {
        // Model AD936x: a manual hardwaregain write is rejected while an AGC
        // mode (slow_attack/fast_attack/hybrid) is active.
        if (gain_write_in_agc_fails && rx_gain_mode_ != "manual") {
            log_.push_back("set_rx_gain:rejected_in_agc");
            return rx_gain_db_;   // not applied
        }
        log_.push_back("set_rx_gain:" + std::to_string(db));
        rx_gain_db_ = db;
        return rx_gain_db_;
    }
    double set_tx_atten(double db) override {
        log_.push_back("set_tx_atten:" + std::to_string(db));
        tx_atten_db_ = db;
        return tx_atten_db_ + atten_readback_bias;  // bias models a read-back mismatch
    }
    int set_loopback(int mode) override {
        log_.push_back("set_loopback:" + std::to_string(mode));
        loopback_ = mode;
        return loopback_;
    }

    long long get_rx_bw() const override { return rx_bw_; }
    long long get_tx_bw() const override { return tx_bw_; }
    std::string get_rx_gain_mode() const override { return rx_gain_mode_; }
    double get_rx_gain() const override { return rx_gain_db_; }
    double get_tx_atten() const override { return tx_atten_db_; }
    int get_loopback() const override { return loopback_; }

    DataFormatInfo rx_data_format() const override { return rx_fmt_; }
    DataFormatInfo tx_data_format() const override { return tx_fmt_; }

    void save_params() override {
        saved_.captured = true;
        saved_.rx_lo_hz = rx_lo_;
        saved_.tx_lo_hz = tx_lo_;
        saved_.rx_sample_rate_hz = rx_sample_rate_;
        saved_.tx_sample_rate_hz = tx_sample_rate_;
        saved_.rx_bw_hz = rx_bw_;
        saved_.tx_bw_hz = tx_bw_;
        saved_.rx_gain_mode = rx_gain_mode_;
        saved_.rx_gain_db = rx_gain_db_;
        saved_.tx_atten_db = tx_atten_db_;
        saved_.loopback = loopback_;
        log_.push_back("save_params");
    }
    bool restore_params() override {
        if (!saved_.captured) return true;
        bool ok = true;
        rx_lo_ = saved_.rx_lo_hz;
        tx_lo_ = saved_.tx_lo_hz;
        rx_sample_rate_ = saved_.rx_sample_rate_hz;
        tx_sample_rate_ = saved_.tx_sample_rate_hz;
        rx_bw_ = saved_.rx_bw_hz;
        tx_bw_ = saved_.tx_bw_hz;
        tx_atten_db_ = saved_.tx_atten_db;
        loopback_ = saved_.loopback;

        // RX gain: mirror the real AD936x semantics -- restore the gain-control
        // mode first, and write hardwaregain ONLY in "manual" mode (an AGC mode
        // rejects a manual gain write; its read-back gain is runtime state).
        if (!saved_.rx_gain_mode.empty()) {
            if (fail_mode_restore) {
                log_.push_back("restore:gain_mode_failed");
                ok = false;
            } else {
                rx_gain_mode_ = saved_.rx_gain_mode;
            }
        }
        if (saved_.rx_gain_mode == "manual") {
            if (fail_manual_gain_restore) {
                log_.push_back("restore:rx_gain_failed");
                ok = false;
            } else {
                rx_gain_db_ = saved_.rx_gain_db;
            }
        }
        // AGC mode (slow_attack/fast_attack/hybrid): rx_gain_db_ intentionally
        // left as the runtime value -- never write AGC hardwaregain.

        log_.push_back("restore_params");
        if (restore_fail) { log_.push_back("restore_failed"); ok = false; }
        return ok;
    }

    void tx_start_cyclic(const std::vector<std::int16_t>& iq) override {
        // Mirror the real backend: a start implicitly stops + replaces the old
        // buffer, so destroy the previous one before counting a create.
        if (tx_buffer_created_) ++tx_buffer_destroy_count_;
        tx_waveform_ = iq;
        tx_buffer_created_ = true;
        tx_running_ = true;
        ++tx_buffer_create_count_;
        log_.push_back("tx_start_cyclic:" + std::to_string(iq.size()));
    }
    void tx_stop() override {
        if (tx_buffer_created_) {
            ++tx_buffer_destroy_count_;
            tx_buffer_created_ = false;
        }
        tx_running_ = false;
        log_.push_back("tx_stop");
    }

    iio::RawChunk read_rx(std::size_t max_complex, std::uint64_t) override {
        iio::RawChunk c;
        // Buffer-size ceiling hook: a request larger than rx_max_capacity models
        // the real ensure_rx_buffer failing to allocate the RX buffer (broken).
        if (rx_max_capacity != 0 && max_complex > rx_max_capacity) {
            c.broken = true;   // no refill attempted
            return c;
        }
        // Model RX-buffer growth: a larger request destroys the old buffer and
        // allocates a fresh one (matching ensure_rx_buffer in the real backend).
        if (max_complex > rx_buffer_capacity_) {
            if (rx_buffer_capacity_ != 0) ++rx_buffer_destroy_count_;
            rx_buffer_capacity_ = max_complex;
            ++rx_buffer_create_count_;
        }
        rx_refill_count_ += 1;
        // Timeout hook: models a refill that returns no data (-ETIMEDOUT).
        if (rx_timed_out) {
            c.timed_out = true;
            return c;
        }
        // Deterministic complex tone (4 kHz at the fake's nominal 128 kHz), so a
        // host test can verify the RX path end to end without a device.
        const double amp = 10000.0;
        const double ph = 2.0 * 3.14159265358979323846 * 4000.0 / 128000.0;
        const std::size_t n = std::min<std::size_t>(max_complex, rx_tone_len);
        rx_scratch_.resize(n * 2);
        for (std::size_t k = 0; k < n; ++k) {
            const std::int16_t i = static_cast<std::int16_t>(
                std::llround(amp * std::cos(ph * static_cast<double>(rx_tone_pos_ + k))));
            const std::int16_t q = static_cast<std::int16_t>(
                std::llround(amp * std::sin(ph * static_cast<double>(rx_tone_pos_ + k))));
            rx_scratch_[k * 2 + 0] = i;
            rx_scratch_[k * 2 + 1] = q;
        }
        rx_tone_pos_ += n;
        c.samples = rx_scratch_.data();
        c.samples_available = n;
        return c;
    }

    std::size_t rx_buffer_capacity() const override { return rx_buffer_capacity_; }
    std::uint64_t rx_refill_count() const override { return rx_refill_count_; }

    std::uint64_t tx_buffer_create_count() const override { return tx_buffer_create_count_; }
    std::uint64_t tx_buffer_destroy_count() const override { return tx_buffer_destroy_count_; }
    std::uint64_t rx_buffer_create_count() const override { return rx_buffer_create_count_; }
    std::uint64_t rx_buffer_destroy_count() const override { return rx_buffer_destroy_count_; }

    bool recreate_rx_buffer() override {
        if (!open_) return false;
        if (rx_buffer_capacity_ != 0) {
            ++rx_buffer_destroy_count_;
            rx_buffer_capacity_ = 0;
        }
        log_.push_back("recreate_rx_buffer");
        return true;
    }

    // ---- test hooks / scripting -------------------------------------------
    std::set<long long> reject_sample_rates;  // set_sample_rate coerces to hz-1
    double atten_readback_bias = 0.0;         // added to set_tx_atten read-back
    bool restore_fail = false;                // restore_params() reports failure (whole)
    bool fail_mode_restore = false;           // restore: gain_control_mode write fails
    bool fail_manual_gain_restore = false;    // restore: manual hardwaregain write fails
    bool gain_write_in_agc_fails = true;      // set_rx_gain rejected unless mode==manual
    std::size_t rx_tone_len = 2048;           // max complex samples per read_rx
    bool rx_timed_out = false;                // read_rx returns timed_out (no data)
    std::size_t rx_max_capacity = 0;          // 0 = unlimited; larger request -> broken
    DataFormatInfo rx_fmt_;                   // reported RX stream format (scriptable)
    DataFormatInfo tx_fmt_;                   // reported TX stream format (scriptable)
    bool tx_buffer_created() const { return tx_buffer_created_; }
    bool tx_running() const { return tx_running_; }
    const std::vector<std::int16_t>& tx_waveform() const { return tx_waveform_; }
    const std::vector<std::string>& log() const { return log_; }
    const DeviceParams& saved() const { return saved_; }

    // current attribute state (for assertions)
    long long rx_lo() const { return rx_lo_; }
    long long tx_lo() const { return tx_lo_; }
    long long sample_rate() const { return rx_sample_rate_; }  // alias: RX rate
    long long rx_sample_rate() const { return rx_sample_rate_; }
    long long tx_sample_rate() const { return tx_sample_rate_; }
    double rx_gain_db() const { return rx_gain_db_; }
    double tx_atten_db() const { return tx_atten_db_; }
    std::string rx_gain_mode() const { return rx_gain_mode_; }
    int loopback() const { return loopback_; }

private:
    bool open_ = false;
    long long rx_lo_ = 0;
    long long tx_lo_ = 0;
    long long rx_sample_rate_ = 0;
    long long tx_sample_rate_ = 0;
    long long rx_bw_ = 0;
    long long tx_bw_ = 0;
    std::string rx_gain_mode_;
    double rx_gain_db_ = 0.0;
    double tx_atten_db_ = 0.0;
    int loopback_ = 0;

    DeviceParams saved_;
    std::vector<std::int16_t> tx_waveform_;
    bool tx_buffer_created_ = false;
    bool tx_running_ = false;

    std::vector<std::int16_t> rx_scratch_;
    std::uint64_t rx_tone_pos_ = 0;
    std::size_t rx_buffer_capacity_ = 0;
    std::uint64_t rx_refill_count_ = 0;
    std::uint64_t tx_buffer_create_count_ = 0;
    std::uint64_t tx_buffer_destroy_count_ = 0;
    std::uint64_t rx_buffer_create_count_ = 0;
    std::uint64_t rx_buffer_destroy_count_ = 0;
    std::vector<std::string> log_;
};

// Factory for the real libiio-backed device.  Defined in pluto_device_libiio.cpp
// when SDR_ADAPTER_HAVE_LIBIIO is defined; a link error otherwise (which is
// intentional: board programs are only built in that configuration).
Device* make_device(const std::string& uri);

}  // namespace pluto
