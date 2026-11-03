// test_cli_harness.cpp -- a tiny stand-in gate binary that parses the same CLI
// surface as the board gate programs (board::opt_u64 / board::opt_d / get_opt /
// has_flag) and echoes the parsed values as `CLI_ECHO key=value ...`.
//
// It exists so the end-to-end script test (test_cli_override.sh) can prove, on a
// real run_gate{6,9}.sh invocation, that a user's post-script args OVERRIDE the
// script's defaults (the "later occurrence wins" rule) and that malformed values
// fail closed with a non-zero exit -- without a Pluto or an NPU.
//
// iCraft-free, libiio-free.  Built/run by host_tests/test_cli_override.sh.

#include "../board_package/board_common.hpp"

#include <cstdio>
#include <string>

int main(int argc, char** argv) {
    try {
        const std::string loopback =
            std::to_string(board::opt_u64(argc, argv, "--loopback", 0));
        const std::string frames =
            std::to_string(board::opt_u64(argc, argv, "--frames", 16));
        const std::string tone = std::to_string(board::opt_d(argc, argv, "--tone", 10000.0));
        const std::string rx_gain = std::to_string(board::opt_d(argc, argv, "--rx-gain", 10.0));
        const std::string rec_scale =
            std::to_string(board::opt_d(argc, argv, "--rec-scale", 1.0));
        const std::string ratio_min =
            std::to_string(board::opt_d(argc, argv, "--ratio-min", 0.3));
        const std::string outdir = board::get_opt(argc, argv, "--outdir", "gate6_out");

        const std::string phase = board::get_opt(argc, argv, "--phase", "offline");
        const std::string count = std::to_string(board::opt_u64(argc, argv, "--count", 240));
        const std::string min_match =
            std::to_string(board::opt_d(argc, argv, "--min-match-rate", 0.90));
        const std::string model_json =
            board::get_opt(argc, argv, "--model-json", "model.json");
        const std::string model_raw = board::get_opt(argc, argv, "--model-raw", "model.raw");
        const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
        const std::string golden = board::get_opt(argc, argv, "--golden", "deployment_golden");
        const std::string sock = board::get_opt(argc, argv, "--sock", "");
        const std::string confirm_rf =
            board::has_flag(argc, argv, "--confirm-safe-rf-path") ? "1" : "0";

        std::printf("CLI_ECHO loopback=%s frames=%s tone=%s rx_gain=%s rec_scale=%s "
                    "ratio_min=%s outdir=%s phase=%s count=%s min_match_rate=%s "
                    "model_json=%s model_raw=%s model_sha=%s golden=%s sock=%s "
                    "confirm_safe_rf_path=%s\n",
                    loopback.c_str(), frames.c_str(), tone.c_str(), rx_gain.c_str(),
                    rec_scale.c_str(), ratio_min.c_str(), outdir.c_str(), phase.c_str(),
                    count.c_str(), min_match.c_str(), model_json.c_str(), model_raw.c_str(),
                    model_sha.c_str(), golden.c_str(), sock.c_str(), confirm_rf.c_str());
        return 0;
    } catch (const std::exception& e) {
        std::printf("CLI_ECHO parse_error=%s\n", e.what());
        return 1;
    }
}
