#pragma once

// PlutoIqSource -- the ADALM-Pluto SDR interface layer (optional compile).
//
// This is the SDR adapter for the now-known device (ADALM-Pluto / AD9363, libiio,
// USB).  It frames raw interleaved int16 IQ from an iio::Backend into 1024-sample
// iq::Frames, carrying overflow / discontinuity / dropped flags and assigning a
// monotonic frame_id.  It does NOT fabricate any device measurement: every device
// parameter is runtime config (pluto::Config) and defaults to 0 / "" =
// "unspecified"; a real device is only reachable when built with libiio.
//
// Build modes:
//   * default (no libiio)          -> make_backend() returns the mock backend, so
//                                     the source runs offline for testing.
//   * -DSDR_ADAPTER_HAVE_LIBIIO    -> make_backend() constructs the libiio backend
//                                     (see pluto_libiio.cpp); the source then talks
//                                     to a real Pluto.
//
// The mock backend (mock_iio.hpp) is used to exercise continuous buffering,
// short reads, timeouts, overflow, discontinuity, frame_id continuity, stream
// break recovery and backpressure -- all offline, no device.
//
// iCraft-free and header-only (the libiio backend is a separate TU).

#include "config.hpp"
#include "iio_backend.hpp"
#include "iq_frame.hpp"
#include "mock_iio.hpp"

#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace pluto {

// Runtime configuration for the Pluto source.  0 / "" = unspecified (the adapter
// refuses to fabricate device values; a real run must set these from board config
// or CLI, and a libiio build must be present).
struct Config {
    std::string uri = "";                // libiio URI, e.g. "ip:192.168.2.1" / "usb:"
    std::uint64_t center_freq_hz = 0;    // LO / center frequency
    std::uint64_t sample_rate_hz = 0;    // AD9363 sample rate
    std::uint64_t rf_bandwidth_hz = 0;   // RF bandwidth
    std::string gain_mode = "";          // "manual" / "slow_attack" / ...; "" = unspecified
    double gain_db = 0.0;                // gain value (meaningful in manual mode)
    std::uint64_t buffer_length = 0;     // libiio buffer length (complex); 0 = device default
    std::uint64_t timeout_ms = 0;        // per-read timeout; 0 = adapter default
};

// Build a backend for a config.  Without libiio this returns a mock backend so
// the source can run offline; with libiio it returns the real backend.
iio::Backend* make_backend(const Config& cfg);

// Maximum consecutive empty/timeout polls before the source throws (stall guard).
constexpr std::uint64_t kMaxEmptyPolls = 100000;

class PlutoIqSource : public iq::Source {
public:
    // The backend is NOT owned; it must outlive the source.
    PlutoIqSource(Config cfg, iio::Backend& backend)
        : cfg_(std::move(cfg)), backend_(backend) {
        frame_.resize(iq::kComplexSamplesPerFrame * 2);
    }

    bool next(iq::Frame& out) override {
        if (eos_) return false;
        acc_.clear();
        bool got_overflow = false, got_dropped = false, got_disc = false;

        const std::size_t need_int16 = iq::kComplexSamplesPerFrame * 2;
        std::uint64_t empty_polls = 0;
        std::uint64_t consecutive_timeouts = 0;

        while (acc_.size() < need_int16) {
            const std::size_t want_complex =
                iq::kComplexSamplesPerFrame - acc_.size() / 2;
            const std::uint64_t timeout = cfg_.timeout_ms ? cfg_.timeout_ms : 1000;
            iio::RawChunk c = backend_.read(want_complex, timeout);

            if (c.timed_out) {
                ++timeouts_;
                if (++consecutive_timeouts > 8)
                    throw std::runtime_error("pluto: read timeout (device stuck)");
                continue;
            }
            consecutive_timeouts = 0;

            if (c.broken) {
                // Stream break: recover once, then flag the sample gap.
                backend_.reopen();
                ++recovered_;
                got_disc = true;
                if (!backend_.is_open())
                    throw std::runtime_error("pluto: stream broke and reopen failed");
                continue;
            }

            if (c.overflow) got_overflow = true;
            if (c.discontinuity) got_disc = true;
            if (c.dropped) got_dropped = true;

            if (c.eos) break;
            if (c.samples_available == 0) {
                if (++empty_polls > kMaxEmptyPolls)
                    throw std::runtime_error("pluto: stream stalled (no data)");
                continue;
            }
            empty_polls = 0;

            acc_.insert(acc_.end(), c.samples,
                        c.samples + c.samples_available * 2);
        }

        if (acc_.empty()) {
            eos_ = true;
            return false;  // clean end of stream
        }

        out.overflow = got_overflow;
        out.dropped = got_dropped;
        out.discontinuity = got_disc;
        out.frame_id = next_frame_id_++;
        out.timestamp_us = now_us();

        if (acc_.size() < need_int16) {
            // Partial final frame (< 1024 samples): flagged, never fed to FPGA.
            frame_.assign(acc_.begin(), acc_.end());
            out.iq = frame_.data();
            out.short_frame = true;
        } else {
            frame_.assign(acc_.begin(), acc_.begin() + need_int16);
            out.iq = frame_.data();
            out.short_frame = false;
        }
        return true;
    }

    void rewind() override {
        next_frame_id_ = 0;
        eos_ = false;
        acc_.clear();
        backend_.reopen();
    }

    std::uint64_t frame_count() const override { return 0; }  // unbounded

    const Config& config() const { return cfg_; }
    std::uint64_t timeouts() const { return timeouts_; }
    std::uint64_t recovered() const { return recovered_; }

private:
    static std::uint64_t now_us() {
        using namespace std::chrono;
        return static_cast<std::uint64_t>(
            duration_cast<microseconds>(steady_clock::now().time_since_epoch())
                .count());
    }

    Config cfg_;
    iio::Backend& backend_;
    std::vector<std::int16_t> acc_;    // accumulation (partial frame)
    std::vector<std::int16_t> frame_;  // stable 2048-int16 frame buffer
    std::uint64_t next_frame_id_ = 0;
    std::uint64_t timeouts_ = 0;
    std::uint64_t recovered_ = 0;
    bool eos_ = false;
};

// Backend factory.
//   * default (no libiio)            -> mock backend, so the source runs offline
//                                       for testing.
//   * -DSDR_ADAPTER_HAVE_LIBIIO      -> the real backend is defined in
//                                       pluto_libiio.cpp (link-time symbol), which
//                                       THROWS "device not found" when no Pluto is
//                                       present -- it never falls back to MOCK.
#if !defined(SDR_ADAPTER_HAVE_LIBIIO)
inline iio::Backend* make_backend(const Config& cfg) {
    (void)cfg;  // device params are applied by the libiio backend when present
    return new iio::MockBackend();
}
#endif

// Populate a pluto::Config from the system config (config.hpp).
inline Config from_cfg(const cfg::Config& c) {
    Config p;
    p.uri = c.pluto_uri;
    p.center_freq_hz = c.pluto_center_freq_hz;
    p.sample_rate_hz = c.pluto_sample_rate_hz;
    p.rf_bandwidth_hz = c.pluto_rf_bandwidth_hz;
    p.gain_mode = c.pluto_gain_mode;
    p.gain_db = c.pluto_gain_db;
    p.buffer_length = c.pluto_buffer_length;
    p.timeout_ms = c.pluto_timeout_ms;
    return p;
}

}  // namespace pluto
