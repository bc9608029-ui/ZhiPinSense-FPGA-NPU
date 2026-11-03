// board_digital_loopback.cpp -- Gate 3: digital loopback (loopback=1).
//
// No external RF is emitted (the AD9361 digital loopback routes TX digital to RX
// digital internally).  The board TXes a known CW tone, acquires RX, and detects
// the tone by single-bin Goertzel at BOTH +/-tone (so an I/Q-direction mismatch
// is reported, not hidden).  PlutoTx enforces the safe startup order; the
// DeviceStateGuard snapshots the device BEFORE negotiation and restores it on
// every path.  On failure the raw IQ + first 32 I/Q + data-format metadata are
// auto-saved for diagnosis.
//
// Build (on board): see build_on_board.sh.

#include "board_common.hpp"

#include <cstdlib>
#include <memory>
#include <string>

namespace {
std::uint64_t opt_u64(int argc, char** argv, const char* name, std::uint64_t def) {
    const std::string s = board::get_opt(argc, argv, name, std::to_string(def));
    return std::strtoull(s.c_str(), nullptr, 10);
}
double opt_d(int argc, char** argv, const char* name, double def) {
    const std::string s = board::get_opt(argc, argv, name, std::to_string(def));
    return std::strtod(s.c_str(), nullptr);
}
}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();
    const std::string uri = board::get_opt(argc, argv, "--uri", "");

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("digital_loopback", false, std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool pass = false;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        // Snapshot the FULL original state BEFORE any write / negotiation.
        guard.reset(new pluto::DeviceStateGuard(*dev));

        const sdr::RateNegotiation neg =
            sdr::negotiate_sample_rate(*dev, sdr::default_rate_candidates(), 128000);
        if (!neg.ok) {
            detail = "negotiation_failed: " + neg.report();
        } else {
            detail = neg.report() + ";";

            board::LoopbackSpec spec;
            spec.center_hz = opt_u64(argc, argv, "--center", 2450000000ULL);
            spec.tone_hz = opt_d(argc, argv, "--tone", 10000.0);
            spec.rx_gain_db = opt_d(argc, argv, "--rx-gain", 10.0);
            spec.tx_atten_db = opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
            spec.loopback = 1;                        // digital
            spec.frames = opt_u64(argc, argv, "--frames", 128);

            board::run_loopback(*dev, neg, spec, &pass, &detail);
        }

        guard->restore();                             // explicit, idempotent
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    // Restore + report on every path (guard null only if save_params threw).
    if (guard) {
        guard->restore();                             // no-op if already restored
        detail += board::restore_report(*dev, *guard);
    }

    board::emit("digital_loopback", pass, detail);
    return pass ? 0 : 1;
}
