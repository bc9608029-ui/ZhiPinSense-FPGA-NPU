#pragma once

// Fake/mock IIO backend for offline PlutoIqSource testing (no libiio, no device).
//
// iio::MockBackend models a deterministic complex-tone IQ producer behind a
// bounded ring buffer, plus explicit one-shot fault injection for the anomalies
// the contest checklist requires:
//
//   * continuous buffering  -- advance() a burst, drain it frame-by-frame;
//   * short read            -- inject_short_read(n): next read returns <= n;
//   * timeout               -- inject_timeout(): next read reports timed_out;
//   * overflow              -- inject_overflow() / ring overrun (backpressure);
//   * discontinuity         -- inject_discontinuity();
//   * dropped               -- inject_drop();
//   * stream break/recovery -- break_stream() / reopen();
//   * backpressure          -- advance() past the ring capacity: the front is
//                              dropped and dropped_samples()/overflow report it.
//
// iCraft-free and header-only; unit-tested (each fault above + EOS).

#include "iio_backend.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <vector>

namespace iio {

struct MockOptions {
    std::uint64_t source_sample_rate_hz = 128000;  // carried for the tone freq
    std::size_t ring_complex = 16384;              // internal ring capacity
    std::uint32_t tone_hz = 4000;                  // deterministic test tone
};

class MockBackend : public Backend {
public:
    explicit MockBackend(MockOptions opt = {}) : opt_(opt) {}

    // ---- producer side (what a real device/ADC would do) -------------------
    // Generate `n` complex samples of the test tone and append to the ring.
    void advance(std::uint64_t n) {
        for (std::uint64_t k = 0; k < n; ++k) {
            const std::uint64_t idx = produced_++;
            push_sample(sample_i(idx), sample_q(idx));
        }
    }

    // Mark the producer finished: once the ring drains, reads report clean EOS.
    void finish() { finished_ = true; }

    // ---- one-shot fault injection (cleared on the next read) ----------------
    void inject_short_read(std::size_t max_complex) {
        short_pending_ = max_complex;
    }
    void inject_timeout() { timeout_pending_ = true; }
    void inject_overflow() { overflow_pending_ = true; }
    void inject_discontinuity() { disc_pending_ = true; }
    void inject_drop() { drop_pending_ = true; }

    // Sticky timeout: every read reports timed_out until cleared (models a stuck
    // device).  Used to exercise the source's timeout-abort path.
    void set_sticky_timeout(bool on) { sticky_timeout_ = on; }

    // ---- stream break / recovery -------------------------------------------
    void break_stream() { broken_ = true; }

    // ---- Backend interface --------------------------------------------------
    RawChunk read(std::size_t max_complex, std::uint64_t timeout_ms) override {
        (void)timeout_ms;
        RawChunk c;

        // Apply one-shot faults first (each clears itself).
        if (sticky_timeout_) { c.timed_out = true; return c; }
        if (short_pending_) {
            max_complex = std::min<std::size_t>(max_complex, short_pending_);
            short_pending_ = 0;
        }
        if (timeout_pending_) { timeout_pending_ = 0; c.timed_out = true; return c; }
        if (overflow_pending_) { overflow_pending_ = 0; c.overflow = true; }
        if (disc_pending_) { disc_pending_ = 0; c.discontinuity = true; }
        if (drop_pending_) { drop_pending_ = 0; c.dropped = true; }

        if (broken_) { c.broken = true; return c; }

        if (ring_.empty()) {
            if (finished_) c.eos = true;   // clean end of stream
            return c;                      // else: no data yet (not timed out)
        }

        const std::size_t avail = ring_.size() / 2;
        const std::size_t n = std::min<std::size_t>(max_complex, avail);
        rbuf_.assign(ring_.begin(), ring_.begin() + static_cast<std::ptrdiff_t>(n * 2));
        ring_.erase(ring_.begin(),
                    ring_.begin() + static_cast<std::ptrdiff_t>(n * 2));
        c.samples = rbuf_.data();
        c.samples_available = n;
        return c;
    }

    void reopen() override { broken_ = false; }

    bool is_open() const override { return !broken_; }

    // ---- diagnostics --------------------------------------------------------
    // Complex samples dropped because the producer overran the ring (backpressure).
    std::uint64_t dropped_samples() const { return dropped_; }
    std::uint64_t produced() const { return produced_; }

private:
    void push_sample(std::int16_t i, std::int16_t q) {
        ring_.push_back(i);
        ring_.push_back(q);
        if (ring_.size() / 2 > opt_.ring_complex) {
            // Drop the oldest COMPLEX sample (two int16) -> backpressure overflow.
            ring_.pop_front();
            ring_.pop_front();
            ++dropped_;
            overflow_pending_ = true;
        }
    }

    std::int16_t sample_i(std::uint64_t k) const {
        return static_cast<std::int16_t>(std::llround(amplitude_ * std::cos(phase_ * k)));
    }
    std::int16_t sample_q(std::uint64_t k) const {
        return static_cast<std::int16_t>(std::llround(amplitude_ * std::sin(phase_ * k)));
    }

    MockOptions opt_;
    const double amplitude_ = 10000.0;
    const double phase_ = 2.0 * 3.14159265358979323846 *
                          static_cast<double>(opt_.tone_hz) /
                          static_cast<double>(opt_.source_sample_rate_hz);

    std::deque<std::int16_t> ring_;
    std::vector<std::int16_t> rbuf_;

    std::uint64_t produced_ = 0;
    std::uint64_t dropped_ = 0;

    bool finished_ = false;
    bool broken_ = false;

    std::size_t short_pending_ = 0;
    bool timeout_pending_ = false;
    bool sticky_timeout_ = false;
    bool overflow_pending_ = false;
    bool disc_pending_ = false;
    bool drop_pending_ = false;
};

}  // namespace iio
