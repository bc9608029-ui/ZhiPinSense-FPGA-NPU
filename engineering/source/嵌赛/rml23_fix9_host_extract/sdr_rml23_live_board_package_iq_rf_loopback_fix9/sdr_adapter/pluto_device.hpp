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
#include "sha256.hpp"

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

// Host-side mirrors of libiio's iio_channel_convert / iio_channel_convert_inverse
// for a 16-bit little-endian container.  These are the REFERENCE semantics the
// fix3 amplitude sweep uses to (a) convert the RAW RX container back to a logical
// 12-bit value WITHOUT libiio, and (b) cross-check the board's actual
// convert_inverse output (Device::tx_raw_after_inverse) against what the reported
// data format *says* the container should hold.  Any divergence between libiio and
// these mirrors is itself evidence of a libiio-convert-semantics error (fix3
// requirement 4, bucket "libiio convert semantics").
//
// Container layout: `length_bits` per sample (16 here); the `bits` significant bits
// sit at bit offset `shift` from the LSB (shift 0 = right-justified, shift 4 =
// left-justified in the top 12 bits).  `is_signed` controls sign extension of the
// `bits`-wide value.
inline std::int16_t format_convert_raw_to_host(const DataFormatInfo& f,
                                               std::int16_t raw_container) {
    const std::uint32_t bits = (f.bits == 0 || f.bits > 16) ? 16u : f.bits;
    const std::uint32_t shift = (f.shift >= 16) ? 15u : f.shift;
    const std::uint32_t length_bits =
        (f.length_bits == 0 || f.length_bits > 16) ? 16u : f.length_bits;
    // libiio convert semantics, mirrored exactly (fix4).  The container-read layer
    // already did copy/endianness; here we (1) limit the word to the CONTAINER
    // width (length_bits), (2) LOGICALLY shift the significant bits down to LSB,
    // then (3) only mask/sign-extend when the format is NOT fully defined.  A
    // fully-defined format must NOT be unconditionally masked to `bits` -- that is
    // what turned a fully-defined right-justified -32 (0xFFE0) into a false +4064
    // RMS/clip (the fix3 bug).  `value` is uint32 so the shift is a LOGICAL shift
    // and never drags in bits above the 16-bit container (do NOT cast a negative
    // int16 straight to uint32 before shifting).
    const std::uint32_t length_mask =
        (length_bits >= 16) ? 0xFFFFu : ((1u << length_bits) - 1u);
    std::uint32_t value = static_cast<std::uint16_t>(raw_container) & length_mask;
    value >>= shift;
    if (!f.is_fully_defined) {
        const std::uint32_t mask = (bits >= 16) ? 0xFFFFu : ((1u << bits) - 1u);
        value &= mask;
        if (f.is_signed && bits < 16 && (value & (1u << (bits - 1))))
            value |= ~mask;                        // sign-extend from `bits`
    }
    return static_cast<std::int16_t>(value);
}

// FORCE-SIGNED DIAGNOSTIC view (fix4): always sign-extend from `bits`, ignoring
// is_fully_defined.  This is NOT a libiio mirror -- it exists purely as an
// independent reference so the board wrapper can show what the logical value WOULD
// be if the reported `bits` were the true signed width.  It must never be used in
// the production convert path or the convert-divergence cross-check.
inline std::int16_t format_convert_raw_to_host_force_signed(
        const DataFormatInfo& f, std::int16_t raw_container) {
    const std::uint32_t bits = (f.bits == 0 || f.bits > 16) ? 16u : f.bits;
    const std::uint32_t shift = (f.shift >= 16) ? 15u : f.shift;
    const std::uint32_t length_bits =
        (f.length_bits == 0 || f.length_bits > 16) ? 16u : f.length_bits;
    const std::uint32_t length_mask =
        (length_bits >= 16) ? 0xFFFFu : ((1u << length_bits) - 1u);
    std::uint32_t value = static_cast<std::uint16_t>(raw_container) & length_mask;
    value >>= shift;
    const std::uint32_t mask = (bits >= 16) ? 0xFFFFu : ((1u << bits) - 1u);
    value &= mask;
    if (f.is_signed && bits < 16 && (value & (1u << (bits - 1))))
        value |= ~mask;                            // sign-extend from `bits`
    return static_cast<std::int16_t>(value);
}

inline std::int16_t format_convert_host_to_raw(const DataFormatInfo& f,
                                               std::int16_t host_value) {
    const std::uint32_t bits = (f.bits == 0 || f.bits > 16) ? 16u : f.bits;
    const std::uint32_t shift = (f.shift >= 16) ? 15u : f.shift;
    const std::uint32_t mask = (bits >= 16) ? 0xFFFFu : ((1u << bits) - 1u);
    // Sign-extend the `bits`-wide value into the full 16-bit container BEFORE
    // placing it at `shift`.  For the AD936x standard left-justified layout
    // (shift 4) this is identical to the plain (value & mask) << shift, because
    // the 12-bit sign bit lands exactly on bit 15; it only differs for a
    // right-justified layout (shift < 4), where the container must still hold the
    // SIGNED value so its RMS stays proportional to the signal -- which is what
    // the fix3 raw-vs-logical gain discriminator relies on (a fixed loopback gain
    // must attenuate the raw container and the logical value by the same amount).
    std::int32_t v = static_cast<std::int32_t>(host_value) &
                     static_cast<std::int32_t>(mask);
    if (f.is_signed && bits < 16 && (v & (1 << (bits - 1))))
        v |= ~static_cast<std::int32_t>(mask);
    v <<= shift;
    return static_cast<std::int16_t>(v);
}

// Is a format's round-trip (host -> raw -> host) the identity for the whole
// logical range?  Used by the sweep self-check to prove the convert pair is
// consistent before any gain/root-cause inference.
inline bool format_roundtrip_identity(const DataFormatInfo& f) {
    const std::int16_t probes[] = {-2048, -1024, -1, 0, 1, 1024, 2047};
    for (std::int16_t p : probes) {
        if (format_convert_raw_to_host(f, format_convert_host_to_raw(f, p)) != p)
            return false;
    }
    return true;
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

    // ---- device identity (read-only, for the startup RF log) ----------------
    // uri() is the EFFECTIVE connection URI (post-scan if the constructor URI was
    // empty); serial() is the hw_serial attribute (empty if unknown); rx_channel_name()
    // is the RX stream channel id (voltage0 on cf-ad9361-lpc).
    virtual std::string uri() const = 0;
    virtual std::string serial() const = 0;
    virtual std::string rx_channel_name() const = 0;

    // RX/TX stream data format (queried from the device; see DataFormatInfo).
    virtual DataFormatInfo rx_data_format() const = 0;
    virtual DataFormatInfo tx_data_format() const = 0;

    // ---- fix3 data-format override (Route E amplitude-loss root cause) ----
    // The fix3 sweep may prove that libiio's *reported* data format (shift/bits)
    // disagrees with where the AD9361 hardware actually places the 12-bit value in
    // the 16-bit container.  When an override is set, the TX/RX convert paths use
    // the host-side mirror (format_convert_* above) with the OVERRIDDEN format
    // instead of libiio's iio_channel_convert / iio_channel_convert_inverse.  This
    // is a FORMAT correction (fix3 requirement 5), never an empirical multiplier.
    // With no override, behaviour is byte-for-byte the current libiio convert path.
    virtual void set_rx_data_format_override(const DataFormatInfo& f) = 0;
    virtual void set_tx_data_format_override(const DataFormatInfo& f) = 0;
    virtual bool has_rx_format_override() const = 0;
    virtual bool has_tx_format_override() const = 0;

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
    // fix8 Task B: whether a cyclic TX transmission is currently running (the
    // negative control must CONFIRM the TX actually stopped before trusting the
    // noise floor -- a device that reports still-running TX invalidates it).
    virtual bool tx_running() const = 0;

    // ---- RX read (reuses iio::RawChunk semantics) ----
    virtual iio::RawChunk read_rx(std::size_t max_complex,
                                  std::uint64_t timeout_ms) = 0;

    // ---- fix3 raw (un-converted) container access ----
    // read_rx() applies iio_channel_convert (12-bit -> host int16).  These expose
    // the RAW 16-bit container words so the sweep can see the exact bit position
    // the hardware used and thereby tell a format/shift error apart from a fixed
    // loopback gain (fix3 requirement 3/4):
    //
    //   tx_raw_after_inverse(host_iq, raw_out): a dry-run of what tx_start_cyclic
    //       writes into the DMA buffer -- iio_channel_convert_inverse applied to
    //       every host int16 sample (or the host-side mirror when a format override
    //       is set).  raw_out is interleaved [I0,Q0,...], same length as host_iq.
    //
    //   read_rx_raw(max_complex, timeout_ms): same refill/overflow semantics as
    //       read_rx(), but the returned samples are the raw container words with
    //       NO iio_channel_convert applied.
    virtual void tx_raw_after_inverse(const std::vector<std::int16_t>& host_iq,
                                      std::vector<std::int16_t>& raw_out) const = 0;
    virtual iio::RawChunk read_rx_raw(std::size_t max_complex,
                                      std::uint64_t timeout_ms) = 0;

    // ---- fix4 independent RX convert reference (read-only, no side effects) ----
    // Apply the ACTUAL libiio RX-channel convert (iio_channel_convert on the RX
    // channel, no format override) to a single raw container word, WITHOUT touching
    // the production read_rx path.  The sweep uses it to detect a libiio-convert
    // semantics divergence: when the board's iio_channel_convert output differs from
    // the host mirror of the REPORTED RX format (format_convert_raw_to_host).
    virtual std::int16_t rx_convert_raw_libiio(std::int16_t raw) const = 0;

    // ---- fix5 TX DMA payload verify ----
    // SHA-256 of the ACTUAL interleaved int16 bytes written into the TX DMA buffer
    // by the last tx_start_cyclic (after iio_channel_convert_inverse / the format
    // override), BEFORE iio_buffer_push.  This proves the bytes the DMA will
    // transmit are the scaled bytes (tx_sha_post_scale) -- never assumed.  Empty
    // if no TX has been started yet.
    virtual std::string tx_dma_payload_sha() const = 0;

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
    int get_loopback() const override {
        return loopback_readback_override >= 0 ? loopback_readback_override
                                               : loopback_;
    }

    std::string uri() const override { return fake_uri; }
    std::string serial() const override { return fake_serial; }
    std::string rx_channel_name() const override { return "voltage0"; }

    DataFormatInfo rx_data_format() const override { return rx_fmt_; }
    DataFormatInfo tx_data_format() const override { return tx_fmt_; }

    void set_rx_data_format_override(const DataFormatInfo& f) override {
        has_rx_override_ = true;
        rx_fmt_override_ = f;
        log_.push_back("set_rx_data_format_override");
    }
    void set_tx_data_format_override(const DataFormatInfo& f) override {
        has_tx_override_ = true;
        tx_fmt_override_ = f;
        log_.push_back("set_tx_data_format_override");
    }
    bool has_rx_format_override() const override { return has_rx_override_; }
    bool has_tx_format_override() const override { return has_tx_override_; }

    // fix3: dry-run of the TX convert_inverse path (host mirror with the effective
    // format).  Mirrors LibiioDevice::tx_raw_after_inverse.
    void tx_raw_after_inverse(const std::vector<std::int16_t>& host_iq,
                              std::vector<std::int16_t>& raw_out) const override {
        const DataFormatInfo f = tx_fmt_effective();
        raw_out.resize(host_iq.size());
        for (std::size_t k = 0; k < host_iq.size(); ++k)
            raw_out[k] = format_convert_host_to_raw(f, host_iq[k]);
    }

    // fix4: RX convert reference.  The fake has no real libiio, so its default is
    // the corrected host mirror of the effective RX format; the two injection hooks
    // below can force a divergence to exercise the LIBIIO_CONVERT classifier.  This
    // is a const, side-effect-free pure function (never touches read_rx).
    std::int16_t rx_convert_raw_libiio(std::int16_t raw) const override {
        const std::int16_t m = format_convert_raw_to_host(rx_fmt_effective(), raw);
        if (force_rx_libiio_divergence)
            return static_cast<std::int16_t>(m + rx_libiio_delta);
        return m;
    }

    // fix5: SHA of the actual DMA payload computed by the last tx_start_cyclic.
    std::string tx_dma_payload_sha() const override { return tx_dma_payload_sha_; }

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
        rx_recreated_since_tx_ = false;   // a new TX invalidates the RX flush state
        rx_tone_pos_ = 0;   // a fresh cyclic buffer restarts transmission at sample 0
        // fix5: model the ACTUAL DMA payload -- the raw container bytes the
        // convert_inverse path would write (host -> raw with the effective TX
        // format), interleaved I/Q, exactly as the real backend writes p_i/p_q
        // before iio_buffer_push.  The corrupt hook flips one bit to model a DMA
        // write that does NOT match the intended scaled bytes.
        {
            const DataFormatInfo f = tx_fmt_effective();
            std::vector<std::int16_t> dma(iq.size());
            for (std::size_t k = 0; k < iq.size(); ++k)
                dma[k] = format_convert_host_to_raw(f, iq[k]);
            if (corrupt_tx_dma_payload && !dma.empty())
                dma[0] = static_cast<std::int16_t>(dma[0] ^ 0x0001);
            tx_dma_payload_sha_ = sdr::Sha256::hex(
                dma.data(), dma.size() * sizeof(std::int16_t));
        }
        log_.push_back("tx_start_cyclic:" + std::to_string(iq.size()));
    }
    void tx_stop() override {
        if (tx_buffer_created_) {
            ++tx_buffer_destroy_count_;
            tx_buffer_created_ = false;
        }
        tx_running_ = false;
        // fix8 Task B: arm the first-refill-stale model when the hook is on -- the
        // NEXT rf_echo_mode read_rx returns the stale TX echo instead of TX-off noise.
        if (rf_first_refill_stale) rf_stale_pending_ = true;
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
        // Route F (fix7): EXTERNAL-RF loopback model (TX DAC -> attenuator -> coax
        // -> RX ADC).  TX-off returns pure deterministic Gaussian noise at
        // rf_noise_rms (the negative control); TX-on returns the cyclic TX waveform
        // rotated by the complex RF gain (rf_gain * exp(j rf_phase_deg)) and
        // circularly delayed by rf_delay samples, plus the same noise.
        if (rf_echo_mode) {
            const std::size_t n = max_complex;
            rx_scratch_.resize(n * 2);
            const auto& w = tx_waveform_;
            const std::size_t N = w.size() / 2;
            const double ph = rf_phase_deg * 3.14159265358979323846 / 180.0;
            const double gr = rf_gain * std::cos(ph);
            const double gi = rf_gain * std::sin(ph);
            // fix8 Task B: consume the first-refill-stale flag -- one TX-off read
            // echoes the stale TX (as if still running), then subsequent reads are
            // true noise.  The transfer's discard refill is what drains this.
            const bool stale_echo = rf_stale_pending_;
            rf_stale_pending_ = false;
            const bool tx_on = (tx_running_ || stale_echo) && N != 0;
            double noise_rms = rf_noise_rms;
            if (!tx_on && rf_noise_unstable && rf_noise_rms > 0.0) {
                const double f[] = {1.0, 5.0, 0.1};   // wildly different windows
                noise_rms *= f[rf_txoff_read_count_ % 3];
                ++rf_txoff_read_count_;
            }
            for (std::size_t k = 0; k < n; ++k) {
                double I = 0.0, Q = 0.0;
                if (tx_on) {
                    const std::size_t src = (rx_tone_pos_ + k + rf_delay) % N;
                    const double xI = static_cast<double>(w[src * 2 + 0]);
                    const double xQ = static_cast<double>(w[src * 2 + 1]);
                    I = xI * gr - xQ * gi;
                    Q = xI * gi + xQ * gr;
                }
                if (noise_rms > 0.0) {
                    I += noise_rms * rf_next_gaussian();
                    Q += noise_rms * rf_next_gaussian();
                }
                rx_scratch_[k * 2 + 0] = static_cast<std::int16_t>(
                    std::max(-32768.0, std::min(32767.0,
                        static_cast<double>(std::llround(I)))));
                rx_scratch_[k * 2 + 1] = static_cast<std::int16_t>(
                    std::max(-32768.0, std::min(32767.0,
                        static_cast<double>(std::llround(Q)))));
            }
            rx_tone_pos_ += n;
            c.samples = rx_scratch_.data();
            c.samples_available = n;
            return c;
        }
        // Route E fix2: echo the cyclic TX waveform back (digital-loopback model).
        if (echo_tx_on_rx) {
            const auto& w = tx_waveform_;
            if (!w.empty()) {
                // Stale-leak model: without a recreate_rx_buffer since the last
                // tx_start_cyclic, the RX returns zeros (the leakage signature the
                // sequence test is meant to catch and the flush is meant to cure).
                if (stale_rx_without_recreate && !rx_recreated_since_tx_) {
                    const std::size_t n = max_complex;
                    rx_scratch_.assign(n * 2, 0);
                    rx_tone_pos_ += n;
                    c.samples = rx_scratch_.data();
                    c.samples_available = n;
                    return c;
                }
                const std::size_t N = w.size() / 2;
                const std::size_t n = max_complex;
                rx_scratch_.resize(n * 2);
                for (std::size_t k = 0; k < n; ++k) {
                    const std::size_t src = (rx_tone_pos_ + k) % N;
                    rx_scratch_[k * 2 + 0] = w[src * 2 + 0];
                    rx_scratch_[k * 2 + 1] = w[src * 2 + 1];
                }
                rx_tone_pos_ += n;
                c.samples = rx_scratch_.data();
                c.samples_available = n;
                return c;
            }
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

    // fix3 raw-container read: the same refill/lifecycle semantics as read_rx(),
    // but the returned samples are the RAW 16-bit container words (no
    // iio_channel_convert).  The fake models the digital loopback as: TX host ->
    // tx raw (tx_fmt_effective) -> [loopback_raw_gain_ then arithmetic shift by
    // loopback_raw_shift_] -> RX raw container.  The sweep converts RX raw back to
    // logical with the host mirror, exactly as LibiioDevice does on the board.
    iio::RawChunk read_rx_raw(std::size_t max_complex, std::uint64_t) override {
        iio::RawChunk c;
        if (rx_max_capacity != 0 && max_complex > rx_max_capacity) {
            c.broken = true;
            return c;
        }
        if (max_complex > rx_buffer_capacity_) {
            if (rx_buffer_capacity_ != 0) ++rx_buffer_destroy_count_;
            rx_buffer_capacity_ = max_complex;
            ++rx_buffer_create_count_;
        }
        rx_refill_count_ += 1;
        if (rx_timed_out) { c.timed_out = true; return c; }

        const auto& w = tx_waveform_;
        const std::size_t N = w.size() / 2;
        const std::size_t n = max_complex;
        rx_raw_scratch_.resize(n * 2);
        if (N == 0) {
            // No TX loaded yet: the loopback has nothing to echo.
            std::fill(rx_raw_scratch_.begin(), rx_raw_scratch_.end(), 0);
        } else {
            const DataFormatInfo tf = tx_fmt_effective();
            const int sh = loopback_raw_shift_;
            for (std::size_t k = 0; k < n; ++k) {
                const std::size_t src = (rx_tone_pos_ + k) % N;
                std::int32_t r_i = format_convert_host_to_raw(tf, w[src * 2 + 0]);
                std::int32_t r_q = format_convert_host_to_raw(tf, w[src * 2 + 1]);
                r_i = static_cast<std::int32_t>(
                    std::llround(static_cast<double>(r_i) * loopback_raw_gain_));
                r_q = static_cast<std::int32_t>(
                    std::llround(static_cast<double>(r_q) * loopback_raw_gain_));
                if (sh > 0) { r_i >>= sh; r_q >>= sh; }
                else if (sh < 0) { r_i <<= -sh; r_q <<= -sh; }
                rx_raw_scratch_[k * 2 + 0] = static_cast<std::int16_t>(r_i);
                rx_raw_scratch_[k * 2 + 1] = static_cast<std::int16_t>(r_q);
            }
            rx_tone_pos_ += n;
        }
        c.samples = rx_raw_scratch_.data();
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
        rx_recreated_since_tx_ = true;
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
    // Route E fix2 test hooks: echo the current cyclic TX waveform back on read_rx
    // (models the AD9361 digital loopback) so the sequence test can verify the
    // TX->RX transfer end to end; and optionally model the stale-buffer leakage --
    // when stale_rx_without_recreate is set, read_rx returns ZERO unless the RX
    // buffer was recreated after the last tx_start_cyclic (the "first files have
    // data, later files zero" state-leakage signature).  Both default off.
    bool echo_tx_on_rx = false;
    bool stale_rx_without_recreate = false;
    std::size_t rx_tone_len = 2048;           // max complex samples per read_rx
    bool rx_timed_out = false;                // read_rx returns timed_out (no data)
    std::size_t rx_max_capacity = 0;          // 0 = unlimited; larger request -> broken
    std::string fake_uri = "fake://pluto0";   // reported uri() (scriptable)
    std::string fake_serial = "";             // reported serial() (scriptable)
    DataFormatInfo rx_fmt_;                   // reported RX stream format (scriptable)
    DataFormatInfo tx_fmt_;                   // reported TX stream format (scriptable)
    // fix3 loopback model (used by read_rx_raw): a fixed raw-domain gain (linear)
    // and/or an arithmetic right shift (positive) modelling the AD9361 digital
    // loopback attenuating or re-aligning the raw container.  Both default to a
    // unity, lossless loopback.
    double loopback_raw_gain_ = 1.0;
    int loopback_raw_shift_ = 0;
    // fix4 test injection (default off; the real board device is unaffected):
    // force_rx_libiio_divergence makes rx_convert_raw_libiio return mirror+delta,
    // modelling a libiio RX convert that disagrees with the host mirror.
    bool force_rx_libiio_divergence = false;
    std::int16_t rx_libiio_delta = 0;
    // fix5 test injection (default off): corrupt_tx_dma_payload flips one bit in the
    // modelled TX DMA payload so tx_dma_payload_sha() no longer equals the intended
    // scaled bytes -- exercising TX_DMA_PAYLOAD_MISMATCH fail-closed.
    bool corrupt_tx_dma_payload = false;
    // Route F (fix7) test hooks (all default off): model the EXTERNAL-RF loopback.
    // rf_echo_mode enables the RF echo in read_rx; rf_gain / rf_phase_deg are the
    // complex RF path gain, rf_delay the whole-sample circular delay, and
    // rf_noise_rms the additive Gaussian noise RMS (the TX-off negative control
    // reads this pure noise).  A nonzero rf_noise_rms is how the host test drives a
    // legitimate-but-quiet RF signal (SNR judgment) vs. a railed RX.
    bool rf_echo_mode = false;
    double rf_gain = 1.0;
    double rf_phase_deg = 0.0;
    std::size_t rf_delay = 0;
    double rf_noise_rms = 0.0;
    // fix7 fail-closed test hook (default off): when >= 0, get_loopback() returns
    // this value instead of the stored loopback -- modelling a device that silently
    // ignored the set_loopback(0) write, so the RF transfer must throw.
    int loopback_readback_override = -1;
    // fix8 Task B test hooks (default off).  rf_first_refill_stale models the
    // first-refill-stale: after tx_stop(), the NEXT rf_echo_mode read_rx returns the
    // stale TX echo (the previous file's tail still in the DMA) instead of TX-off
    // noise -- the transfer's discard refill is what drains it.  rf_noise_unstable
    // makes successive TX-off noise refills return wildly different RMS (1x/5x/0.1x),
    // so the 3-window negative control fails closed with RF_NEGATIVE_CONTROL_UNSTABLE.
    bool rf_first_refill_stale = false;
    bool rf_noise_unstable = false;
    // Effective TX/RX format = the override when set, else the reported format.
    DataFormatInfo tx_fmt_effective() const {
        return has_tx_override_ ? tx_fmt_override_ : tx_fmt_;
    }
    DataFormatInfo rx_fmt_effective() const {
        return has_rx_override_ ? rx_fmt_override_ : rx_fmt_;
    }
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
    bool rx_recreated_since_tx_ = false;   // echo/stale-leak test state

    // fix3 format override state (empty until set_*_data_format_override is called)
    bool has_rx_override_ = false;
    bool has_tx_override_ = false;
    DataFormatInfo rx_fmt_override_;
    DataFormatInfo tx_fmt_override_;

    std::vector<std::int16_t> rx_scratch_;
    std::vector<std::int16_t> rx_raw_scratch_;   // fix3 read_rx_raw container output
    std::string tx_dma_payload_sha_;             // fix5 TX DMA payload verify
    std::uint64_t rx_tone_pos_ = 0;
    std::size_t rx_buffer_capacity_ = 0;
    std::uint64_t rx_refill_count_ = 0;
    std::uint64_t tx_buffer_create_count_ = 0;
    std::uint64_t tx_buffer_destroy_count_ = 0;
    std::uint64_t rx_buffer_create_count_ = 0;
    std::uint64_t rx_buffer_destroy_count_ = 0;
    std::vector<std::string> log_;

    // fix7 (Route F) deterministic Gaussian noise (xorshift64 LCG + Marsaglia polar),
    // seeded once so a host test is reproducible; advances as noise is consumed.
    std::uint64_t rf_noise_state_ = 0x243F6A8885A308D3ull;
    // fix8 Task B: first-refill-stale arm flag (consumed by the next rf_echo_mode
    // read_rx) and the TX-off noise-refill counter (cycles the unstable RMS).
    bool rf_stale_pending_ = false;
    std::size_t rf_txoff_read_count_ = 0;
    double rf_next_gaussian() {
        const auto next_u = [&]() {
            rf_noise_state_ ^= rf_noise_state_ << 13;
            rf_noise_state_ ^= rf_noise_state_ >> 7;
            rf_noise_state_ ^= rf_noise_state_ << 17;
            return static_cast<double>(rf_noise_state_ >> 11) *
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

// Factory for the real libiio-backed device.  Defined in pluto_device_libiio.cpp
// when SDR_ADAPTER_HAVE_LIBIIO is defined; a link error otherwise (which is
// intentional: board programs are only built in that configuration).
Device* make_device(const std::string& uri);

}  // namespace pluto
