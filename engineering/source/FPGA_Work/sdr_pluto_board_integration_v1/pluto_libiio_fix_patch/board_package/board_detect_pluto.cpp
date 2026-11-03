// board_detect_pluto.cpp -- Gate 1: enumerate + open the Pluto, report identity.
//
// Real libiio device only (pluto::make_device).  No mock fallback.  Counts the
// open probes so a USB reconnection (repeated connect attempts) is surfaced.
// Exit codes: 0 = detected, 1 = detected with a warning (reconnect / read-back
// error), 2 = device not found.
//
// Build (on board): see build_on_board.sh.

#include "board_common.hpp"

#include <unistd.h>

#include <exception>
#include <string>

int main(int argc, char** argv) {
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const int max_probes = 3;

    pluto::Device* dev = nullptr;
    int probe = 0;
    std::string last_err;
    for (; probe < max_probes; ++probe) {
        try {
            dev = pluto::make_device(uri);
            break;
        } catch (const std::exception& e) {
            last_err = e.what();
            if (probe + 1 < max_probes) usleep(300000);  // 300 ms between probes
        }
    }

    if (dev == nullptr) {
        std::printf("DETECT_PLUTO: not found after %d probes (%s)\n", probe,
                    last_err.c_str());
        board::emit("detect_pluto", false,
                    std::string("device_not_found probes=") + std::to_string(probe));
        return 2;
    }

    bool pass = (probe == 0);
    std::string detail = "probe_count=" + std::to_string(probe + 1);
    if (probe > 0) detail += " reconnect_detected";

    try {
        // Print the RX and TX sample rate and LO separately (they are distinct
        // channel attributes; no assumption they are equal).  A read-back failure
        // surfaces the libiio errno code + string via the thrown message.
        detail += " rx_sample_rate=" + std::to_string(dev->get_rx_sample_rate());
        detail += " tx_sample_rate=" + std::to_string(dev->get_tx_sample_rate());
        detail += " rx_lo=" + std::to_string(dev->get_rx_lo());
        detail += " tx_lo=" + std::to_string(dev->get_tx_lo());
        detail += " format=\"" + sdr::describe(sdr::canonical_rx_format()) + "\"";
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" readback_error=") + e.what();
    }

    delete dev;
    board::emit("detect_pluto", pass, detail);
    return pass ? 0 : 1;
}
