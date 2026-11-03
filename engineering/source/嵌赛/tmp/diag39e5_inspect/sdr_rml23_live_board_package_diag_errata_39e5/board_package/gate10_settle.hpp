#pragma once

// gate10_settle.hpp -- pure-logic helpers for the M17 Gate 10 decisive fix.
//
// M17 fixes three board-side defects found in hardware (§2 of M17_HARDWARE_FINDINGS.md):
//   (A) the M15 settle-frame capture-and-discard path collapsed OOK (default
//       --settle-frames=2: OOK 0/20).  The old "capture frames+settle then discard
//       the first N frames" path is DELETED.  The only supported policy is
//       TIME_ONLY (wait --settle-wait-ms for the analog/RF settle, no frame
//       discard): the official capture is sized to exactly required_input(frames).
//       A non-zero --settle-frames is rejected fail-closed (never silently ignored).
//   (B) the TX/RX buffer-lifecycle deltas were read BEFORE the PlutoTx RAII
//       destructor, so tx_destroy_delta was always 0.  Deltas are now taken AFTER
//       the destructor AND after the class-end RX buffer recreate, so each class
//       provably sees tx_create=1/tx_destroy=1/tx_live=0 and rx_live=0.
//   (C) --dump-error-class selects a single target class (or all), and the dump
//       manifest is enriched (frame indices, CRC32s, confidence, model/bitstream
//       SHA) with a SHA256SUMS sidecar.
//
// iCraft-free and libiio-free: this header is pure logic, host-testable in
// host_tests/test_gate10_settle.cpp.  The device-facing snap() lambda and the
// capture loop stay in board_gate10_selftest_12class.cpp.

#include <cstdint>
#include <cstdlib>
#include <string>

namespace gate10 {

// ---- Task A: settle policy ------------------------------------------------

enum class SettlePolicy { kTimeOnly = 0, kSeparateCapture = 1 };

inline const char* settle_policy_name(SettlePolicy p) {
    return p == SettlePolicy::kSeparateCapture ? "SEPARATE_CAPTURE" : "TIME_ONLY";
}

struct SettleConfig {
    SettlePolicy policy = SettlePolicy::kTimeOnly;
    std::uint64_t settle_wait_ms = 100;
    std::uint64_t settle_frames = 0;  // always 0 under TIME_ONLY
};

// Parse --settle-frames / --settle-wait-ms.  Returns false (with `err` set) for a
// non-zero settle_frames: the capture-and-discard T1 path is gone in M17, and a
// non-zero value must fail closed, never be silently downgraded to time-wait.
inline bool parse_settle_config(std::uint64_t settle_frames,
                                std::uint64_t settle_wait_ms,
                                SettleConfig& cfg, std::string& err) {
    cfg.settle_wait_ms = settle_wait_ms;
    cfg.settle_frames = settle_frames;
    if (settle_frames == 0) {
        cfg.policy = SettlePolicy::kTimeOnly;
        return true;
    }
    cfg.policy = SettlePolicy::kTimeOnly;
    err = "settle_frames_deprecated_nonzero(" + std::to_string(settle_frames) +
          "): the M15 capture-and-discard settle path was removed in M17; only "
          "time-wait settle (--settle-frames=0) is supported. Use "
          "--settle-wait-ms to control the analog/RF settle wait.";
    return false;
}

// ---- Task A4: settle / official-capture stats -----------------------------

struct SettleStats {
    std::string policy = "TIME_ONLY";       // TIME_ONLY | SEPARATE_CAPTURE
    std::uint64_t settle_wait_ms = 0;
    std::uint64_t settle_frames_requested = 0;
    std::uint64_t settle_capture_samples = 0;  // complex samples (0 for TIME_ONLY)
    std::uint64_t settle_refill_count = 0;      // 0 for TIME_ONLY
    std::uint64_t official_requested_input_complex = 0;
    std::uint64_t official_frames = 0;
    std::uint64_t official_refill_count = 0;
    std::uint64_t official_single_refill = 0;   // 1 when the capture was one refill

    std::string report() const {
        std::string s;
        s += " settle_policy=" + policy;
        s += " settle_wait_ms=" + std::to_string(settle_wait_ms);
        s += " settle_frames_requested=" + std::to_string(settle_frames_requested);
        s += " settle_capture_samples=" + std::to_string(settle_capture_samples);
        s += " settle_refill_count=" + std::to_string(settle_refill_count);
        s += " official_requested_input_complex=" +
             std::to_string(official_requested_input_complex);
        s += " official_frames=" + std::to_string(official_frames);
        s += " official_refill_count=" + std::to_string(official_refill_count);
        s += " official_single_refill=" + std::to_string(official_single_refill);
        return s;
    }
};

// ---- Task B: buffer-lifecycle accounting ----------------------------------

struct BufferCounts {
    std::uint64_t tx_create = 0;
    std::uint64_t tx_destroy = 0;
    std::uint64_t rx_create = 0;
    std::uint64_t rx_destroy = 0;
    std::uint64_t rx_refill = 0;
};

struct LifecycleDeltas {
    std::uint64_t tx_create_delta = 0;
    std::uint64_t tx_destroy_delta = 0;
    std::uint64_t tx_live_delta = 0;
    std::uint64_t settle_rx_create_delta = 0;
    std::uint64_t settle_rx_destroy_delta = 0;
    std::uint64_t official_rx_create_delta = 0;
    std::uint64_t official_rx_destroy_delta = 0;
    std::uint64_t rx_buffer_live_delta = 0;
    std::uint64_t rx_refill_delta = 0;

    std::string report() const {
        std::string s;
        s += " tx_buffer_create_count=" + std::to_string(tx_create_delta);
        s += " tx_buffer_destroy_count=" + std::to_string(tx_destroy_delta);
        s += " tx_buffer_live_delta=" + std::to_string(tx_live_delta);
        s += " settle_rx_buffer_create_count=" + std::to_string(settle_rx_create_delta);
        s += " settle_rx_buffer_destroy_count=" +
             std::to_string(settle_rx_destroy_delta);
        s += " official_rx_buffer_create_count=" +
             std::to_string(official_rx_create_delta);
        s += " official_rx_buffer_destroy_count=" +
             std::to_string(official_rx_destroy_delta);
        s += " rx_buffer_live_delta=" + std::to_string(rx_buffer_live_delta);
        s += " rx_refill_count=" + std::to_string(rx_refill_delta);
        return s;
    }
};

// Compute per-class deltas from the before/after snapshots.  `settle` is the
// snapshot taken after the settle phase (before the official capture); for
// TIME_ONLY it equals `before` because there is no settle RX activity.  `after`
// is the snapshot taken after BOTH the PlutoTx destructor and the class-end RX
// buffer recreate, so every create is matched by a destroy.
inline LifecycleDeltas compute_lifecycle(const BufferCounts& before,
                                         const BufferCounts& settle,
                                         const BufferCounts& after) {
    LifecycleDeltas d;
    d.tx_create_delta = after.tx_create - before.tx_create;
    d.tx_destroy_delta = after.tx_destroy - before.tx_destroy;
    d.tx_live_delta = d.tx_create_delta - d.tx_destroy_delta;

    d.settle_rx_create_delta = settle.rx_create - before.rx_create;
    d.settle_rx_destroy_delta = settle.rx_destroy - before.rx_destroy;

    d.official_rx_create_delta = after.rx_create - settle.rx_create;
    d.official_rx_destroy_delta = after.rx_destroy - settle.rx_destroy;
    d.rx_buffer_live_delta =
        (d.settle_rx_create_delta + d.official_rx_create_delta) -
        (d.settle_rx_destroy_delta + d.official_rx_destroy_delta);
    d.rx_refill_delta = after.rx_refill - before.rx_refill;
    return d;
}

// ---- Task C: --dump-error-class target filter -----------------------------

struct ErrorClassFilter {
    bool all = true;
    int target = -1;  // 0..11 when !all

    // Parse "" or "all" -> all classes; "0".."11" -> a single target class.
    // Returns false (with `err`) on an out-of-range or non-numeric value.
    bool parse(const std::string& s, std::string& err) {
        if (s.empty() || s == "all") {
            all = true;
            target = -1;
            return true;
        }
        char* end = nullptr;
        const long v = std::strtol(s.c_str(), &end, 10);
        if (end == s.c_str() || *end != '\0' || v < 0 || v > 11) {
            err = "invalid --dump-error-class '" + s +
                  "' (expect 0..11 or \"all\")";
            return false;
        }
        all = false;
        target = static_cast<int>(v);
        return true;
    }

    bool matches(int c) const { return all || c == target; }
};

}  // namespace gate10
