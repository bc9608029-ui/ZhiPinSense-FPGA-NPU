// test_pc_tx_board_rx_24class_bf16_fix10.cpp -- host tests for the REAL dual-SDR
// 24-class BF16 runner's acceptance gate (fix10class24-dualsdr1 §9, Phase 4).
//
// The full runner needs pluto devices + the TCP TX-control channel + the NPU, so it
// cannot run host-side; but its ACCEPTANCE GATE is pure and testable: before any RF
// sample is scored, the runner ties the 24 holdout files to ONE batch of bytes via
// source_index + original_sha256 + raw24_class + modulation + split_role (the D2
// manifest's original_sha256 must equal the baseline's original_sha256), and it
// asserts full_run only when holdout_files == baseline_rows.  This test loads the
// SAME frozen D2 sidecar and 7-column raw24 BF16 baseline the runner loads, and
// verifies that pairing 1:1 plus the phase surface.  iCraft-free and libiio-free.

#include "../board_package/iq_digital_loopback.hpp"
#include "../board_package/gate9_phase.hpp"
#include "../board_package/rml24_raw.hpp"
#include "../board_package/rml24_bf16_baseline.hpp"

#include <cstdint>
#include <cstdio>
#include <map>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

void test_phase_surface() {
    check(gate9::valid_phase("iq-pc-tx-board-rx-24class-bf16-fix10"),
          "phase: valid_phase accepts iq-pc-tx-board-rx-24class-bf16-fix10");
    check(!gate9::valid_phase("iq-pc-tx-board-rx-24class-bf16-fix10x"),
          "phase: valid_phase rejects trailing-x near-miss");
    check(!gate9::valid_phase("iq-pc-tx-board-rx-24class-bf16-fix1"),
          "phase: valid_phase rejects truncated near-miss");
    check(!gate9::valid_phase(""),
          "phase: valid_phase rejects empty");
    check(gate9::valid_phase("iq-pc-tx-board-rx-23class-fix10"),
          "phase: valid_phase still accepts the 23-class dual-SDR phase");
    check(gate9::valid_phase("iq-clean-iq-24class-bf16-fix10"),
          "phase: valid_phase accepts the 24-class clean phase too");
}

void test_baseline_d2_identity_pairing(const std::string& frozen_dir,
                                       const std::string& baseline_path) {
    const std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(frozen_dir, "radioml-d2-2p56m");
    const std::map<std::uint64_t, rml24bf16::BaselineRow> baseline =
        rml24bf16::load_baseline(baseline_path, rml24::kClassCount);

    check(frozen.size() == 24, "gate: 24 frozen D2 files (got " +
          std::to_string(frozen.size()) + ")");
    check(baseline.size() == 24, "gate: 24 baseline rows (got " +
          std::to_string(baseline.size()) + ")");

    // The runner's holdout set (all files here are holdout) must equal baseline_rows
    // for full_run.  Reproduce the identity check verbatim (lines 454-473 of the
    // runner): source_index + original_sha256 + raw24_class + modulation + split_role.
    std::size_t holdout_files = 0;
    for (const auto& fz : frozen)
        if (!fz.is_calibration) ++holdout_files;
    check(holdout_files == 24, "gate: 24 holdout files (no calibration)");
    check(holdout_files == baseline.size(), "gate: full_run => holdout_files == baseline_rows");

    bool identity_ok = true;
    std::string report;
    for (const auto& fz : frozen) {
        if (fz.is_calibration) continue;
        auto it = baseline.find(static_cast<std::uint64_t>(fz.source_index));
        if (it == baseline.end()) {
            identity_ok = false;
            report += "missing:" + fz.file_name + ";";
        } else if (it->second.original_sha256 != fz.original_sha256 ||
                   it->second.raw24_class != fz.source_class ||
                   it->second.modulation != fz.modulation ||
                   it->second.split_role != fz.split_role) {
            identity_ok = false;
            report += "mismatch:" + fz.file_name + ";";
        }
    }
    check(identity_ok, "gate: baseline identity 1:1 on 5 fields (report='" +
          report + "')");

    // Reverse 1:1: every baseline source_index has exactly one frozen file.
    bool reverse_ok = true;
    for (const auto& kv : baseline) {
        int matches = 0;
        for (const auto& fz : frozen)
            if (static_cast<std::uint64_t>(fz.source_index) == kv.first) ++matches;
        if (matches != 1) reverse_ok = false;
    }
    check(reverse_ok, "gate: every baseline source_index has exactly one frozen file");

    // WC/SC stay two independent raw24 classes (raw17=WC, raw18=SC) in the sidecar,
    // while their deployed_class (24->23 fold) is 17 for both -- the raw24 path scores
    // on source_class, never on deployed_class.
    bool wc17 = false, sc18 = false;
    for (const auto& fz : frozen) {
        if (fz.source_class == rml24::kAmSsbWc) wc17 = true;
        if (fz.source_class == rml24::kAmSsbSc) sc18 = true;
    }
    check(wc17 && sc18, "gate: raw24 WC(17)/SC(18) kept independent");
}

}  // namespace

void run_test(const char* name, void (*fn)()) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main(int argc, char** argv) {
    std::printf("test_pc_tx_board_rx_24class_bf16_fix10\n");
    run_test("phase_surface", test_phase_surface);

    const std::string frozen_dir = (argc > 1 && argv[1][0])
            ? argv[1] : "../clean24_smoke";
    const std::string baseline_path = (argc > 2 && argv[2][0])
            ? argv[2] : "../baselines/clean24_smoke_raw24_bf16_baseline.tsv";
    try {
        test_baseline_d2_identity_pairing(frozen_dir, baseline_path);
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in baseline_d2_identity_pairing: %s\n", e.what());
        ++g_fail;
    }

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
