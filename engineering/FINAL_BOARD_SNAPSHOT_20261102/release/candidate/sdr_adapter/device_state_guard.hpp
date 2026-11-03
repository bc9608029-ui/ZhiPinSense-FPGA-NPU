#pragma once

// device_state_guard.hpp -- RAII guard that snapshots the device parameters on
// construction and restores them on destruction.
//
// The task (39e5, state-restore redesign) requires saving the FULL device state
// BEFORE any parameter write / sample-rate negotiation, so restore returns the
// device to its ORIGINAL state (not the negotiated one).  A guard created at the
// top of main() -- before negotiate_sample_rate -- gives exactly that: normal
// exit, exception unwind, and early return all run the destructor and restore.
//
// SIGINT/SIGTERM do NOT run destructors (the default handler terminates the
// process immediately, so the TX keeps transmitting).  The board programs
// therefore install signal handlers that ONLY set a sig_atomic_t flag; the
// blocking RX read is unblocked by its context timeout, and the normal flow then
// stops TX (PlutoTx destructor) and restores (this guard's destructor).
//
// restore() returns the device's restore success (true == every write succeeded),
// which the caller reports as restore_result=PASS|FAIL.
//
// iCraft-free, header-only.

#include "pluto_device.hpp"

namespace pluto {

class DeviceStateGuard {
public:
    // Snapshot the device state now (must be BEFORE any parameter write).
    explicit DeviceStateGuard(pluto::Device& dev) : dev_(dev), restored_(false),
                                                    restore_ok_(false) {
        dev_.save_params();
    }

    ~DeviceStateGuard() {
        restore();
    }

    DeviceStateGuard(const DeviceStateGuard&) = delete;
    DeviceStateGuard& operator=(const DeviceStateGuard&) = delete;

    // Restore the saved parameters.  Idempotent: safe to call explicitly at the
    // normal end of a gate (so the caller can read back + report restore_result),
    // and again from the destructor.  Returns true if every restore write
    // succeeded, false if any failed (best-effort).
    bool restore() {
        if (!restored_) {
            restore_ok_ = dev_.restore_params();
            restored_ = true;
        }
        return restore_ok_;
    }

    bool restored() const { return restored_; }
    bool restore_ok() const { return restore_ok_; }
    pluto::Device& device() const { return dev_; }

private:
    pluto::Device& dev_;
    bool restored_;
    bool restore_ok_;
};

}  // namespace pluto
