// board_rx_only.cpp -- Gate 2: RX-only acquisition (environment noise).
//
// TX disabled.  Negotiates the sample rate, sets RX manual low gain + LO, then
// captures N frames (1024 complex each) and saves raw interleaved int16 for PC
// review.  Pass requires: full frames (no short), and overflow/drop/discontinuity
// all zero.  The DeviceStateGuard snapshots the device BEFORE negotiation and
// restores it on every path.
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
}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center = opt_u64(argc, argv, "--center", 2400000000ULL);
    const std::uint64_t n_frames = opt_u64(argc, argv, "--frames", 64);
    const std::string out_path = board::get_opt(argc, argv, "--out", "rx_only_raw.bin");

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        std::printf("RX_ONLY: %s\n", e.what());
        board::emit("rx_only", false, std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool pass = true;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // 1. exact sample-rate negotiation.
        const sdr::RateNegotiation neg =
            sdr::negotiate_sample_rate(*dev, sdr::default_rate_candidates(), 128000);
        if (!neg.ok) {
            detail = "negotiation_failed: " + neg.report();
            pass = false;
        } else {
            detail = neg.report() + ";";

            // 2. RX config + ensure TX off.
            dev->tx_stop();
            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(10.0);
            dev->set_rx_lo(static_cast<long long>(center));

            // 3. capture.
            const std::size_t n_complex = static_cast<std::size_t>(n_frames) * 1024;
            std::vector<std::int16_t> iq;
            board::RxStats st;
            if (!board::collect_raw(*dev, n_complex, iq, st)) {
                detail += " stream_broken";
                pass = false;
            } else {
                // 4. verdict: full frames, no anomalies.
                const std::size_t frames = iq.size() / 2 / 1024;
                const bool clean = !st.short_block && !st.interrupted &&
                                   st.overflow == 0 && st.dropped == 0 &&
                                   st.discontinuity == 0;
                pass = clean && frames >= n_frames;

                detail += " frames=" + std::to_string(frames);
                detail += " short=" + std::to_string(st.short_block ? 1 : 0);
                detail += " interrupted=" + std::to_string(st.interrupted ? 1 : 0);
                detail += " overflow=" + std::to_string(st.overflow);
                detail += " drop=" + std::to_string(st.dropped);
                detail += " disc=" + std::to_string(st.discontinuity);
                detail += " timeouts=" + std::to_string(st.timeouts);

                const auto x = board::to_complex(iq);
                detail += " noise_rms=" + std::to_string(board::rms(x));

                if (!board::save_raw_iq(out_path, iq)) {
                    pass = false;
                    detail += " save_failed";
                } else {
                    detail += " saved=" + out_path;
                }
            }
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

    board::emit("rx_only", pass, detail);
    return pass ? 0 : 1;
}
