// board_rf_loopback.cpp -- Gate 4: external RF loopback (loopback=0).
//
// This EMITS RF from the TX antenna port, so it is DISABLED by default: the
// program refuses to run unless --confirm-safe-rf-path is passed.  With the flag
// set, it starts at maximum safe attenuation (-89.75 dB, read-back confirmed),
// then ramps up to the working level, which may NEVER exceed the -40 dB safety
// ceiling (an independent hard limit in PlutoTx::prepare()).  The PC-safe config
// is TX/RX LO aligned, TX atten = -40 dB, RX manual 20 dB, with a direct TX->RX
// coax.  PlutoTx + DeviceStateGuard restore everything on every path.
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
    const bool confirm_safe = board::has_flag(argc, argv, "--confirm-safe-rf-path");

    if (!confirm_safe) {
        std::printf("RF_LOOPBACK: external RF TX is DISABLED by default.\n"
                    "Refusing to run without --confirm-safe-rf-path.\n");
        board::emit("rf_loopback", false, "rf_path_not_confirmed");
        return 1;
    }

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("rf_loopback", false, std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool pass = false;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
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
            spec.rx_gain_db = opt_d(argc, argv, "--rx-gain", 20.0);   // PC-safe manual RX
            // Default working level is the -40 dB ceiling; PlutoTx starts at the
            // -89.75 dB safety floor and RAMPS to this, and refuses to exceed it.
            spec.tx_atten_db = opt_d(argc, argv, "--tx-atten", pluto::kSafeTxCeilingDb);
            spec.loopback = 0;                        // external RF path
            spec.confirm_safe_rf = true;              // gated above
            spec.frames = opt_u64(argc, argv, "--frames", 128);
            spec.freq_err_max_hz = opt_d(argc, argv, "--freq-err", 300.0);

            board::run_loopback(*dev, neg, spec, &pass, &detail);
        }

        guard->restore();
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    if (guard) {
        guard->restore();
        detail += board::restore_report(*dev, *guard);
    }

    board::emit("rf_loopback", pass, detail);
    return pass ? 0 : 1;
}
