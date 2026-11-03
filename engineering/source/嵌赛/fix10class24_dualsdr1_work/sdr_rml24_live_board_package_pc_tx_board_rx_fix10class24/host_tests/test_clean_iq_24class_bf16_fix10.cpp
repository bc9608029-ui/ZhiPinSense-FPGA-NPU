// test_clean_iq_24class_bf16_fix10.cpp -- host tests for the GENERATED-CLEAN
// 24-class BF16 digital path (fix10class24-dualsdr1 §8, Phase 3).
//
// iCraft-free and libiio-free (no NPU, no device): it exercises the WHOLE digital
// half of the clean 24-class path against the FROZEN clean24_smoke assets --
// iqdloop::load_frozen_iq (D2 24-col sidecar, SHA/size fail-closed) -> load_ci16 ->
// PreprocessChain -> apply_d2_restore_to_stream -> load_recovered_tensor ->
// select_classification_window -- and asserts:
//
//   1. 24 files load with source_class 0..23 (AM-SSB-WC=17 / AM-SSB-SC=18 kept as
//      TWO independent raw classes, never merged);
//   2. the C++ chain reproduces the Python-frozen recovered [2,1024] tensor
//      (min tensor_corr > 0.99);
//   3. the 7-column raw24 BF16 baseline loads 24 rows and its source_index keys
//      pair 1:1 with the frozen files on original_sha256 + raw24_class +
//      modulation + split_role (the exact identity gate the runner applies);
//   4. the new clean phase is accepted by gate9::valid_phase.
//
// The frozen dir and baseline are overridable via argv[1]/argv[2] (defaults are the
// tree-relative clean24_smoke/ and baselines/ paths).

#include "../board_package/chain_common.hpp"
#include "../board_package/iq_digital_loopback.hpp"
#include "../board_package/gate9_phase.hpp"
#include "../board_package/rml24_raw.hpp"
#include "../board_package/rml24_bf16_baseline.hpp"

#include <algorithm>
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

// Phase surface: the new clean 24-class phase is accepted; near-misses rejected.
void test_phase_surface() {
    check(gate9::valid_phase("iq-clean-iq-24class-bf16-fix10"),
          "phase: valid_phase accepts iq-clean-iq-24class-bf16-fix10");
    check(!gate9::valid_phase("iq-clean-iq-24class-bf16-fix10x"),
          "phase: valid_phase rejects trailing-x near-miss");
    check(!gate9::valid_phase("iq-clean-iq-24class-bf16-fix1"),
          "phase: valid_phase rejects truncated near-miss");
    check(!gate9::valid_phase(""),
          "phase: valid_phase rejects empty");
    check(gate9::valid_phase("iq-clean-iq-23class-fix10"),
          "phase: valid_phase still accepts the 23-class clean phase");
}

// Digital chain against the frozen assets + raw24 baseline identity pairing.
void test_frozen_chain_and_baseline_pairing(const std::string& frozen_dir,
                                            const std::string& baseline_path) {
    // 1. Load the frozen D2 sidecar (SHA/size/class-consistency fail-closed).
    const std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(frozen_dir, "radioml-d2-2p56m");
    check(frozen.size() == 24, "frozen: 24 clean D2 files loaded (got " +
          std::to_string(frozen.size()) + ")");
    if (frozen.empty()) return;

    // 2. source_class must be exactly 0..23, WC/SC kept separate.
    std::vector<int> src;
    bool all_holdout = true;
    for (const auto& fz : frozen) {
        src.push_back(fz.source_class);
        if (fz.is_calibration || fz.split_role != "holdout") all_holdout = false;
    }
    std::sort(src.begin(), src.end());
    check(src.size() == 24 && src[0] == 0 && src[23] == 23,
          "frozen: source_class covers 0..23");
    bool unique = true;
    for (std::size_t i = 1; i < src.size(); ++i)
        if (src[i] == src[i - 1]) unique = false;
    check(unique, "frozen: source_class unique (no duplicate)");
    check(all_holdout, "frozen: every clean file is holdout");
    {
        bool wc = false, sc = false;
        for (const auto& fz : frozen) {
            if (fz.source_class == rml24::kAmSsbWc) wc = true;
            if (fz.source_class == rml24::kAmSsbSc) sc = true;
        }
        check(wc && sc, "frozen: AM-SSB-WC(17) and AM-SSB-SC(18) both present");
    }

    // 3. Load the 7-column raw24 baseline.
    const std::map<std::uint64_t, rml24bf16::BaselineRow> baseline =
        rml24bf16::load_baseline(baseline_path, rml24::kClassCount);
    check(baseline.size() == 24, "baseline: 24 rows loaded (got " +
          std::to_string(baseline.size()) + ")");

    // 4. Digital chain + D2 restore + window, per frozen file.
    double min_corr = 2.0;
    int all_valid = 0;
    for (const auto& fz : frozen) {
        const std::vector<std::int16_t> ci16 =
            iqdloop::load_ci16(fz.path, fz.complex_count);
        chain::PreprocessChain chain(iqdloop::kFrozenFsIn, 0.0, 1.0f);
        chain.push_int16(ci16.data(), fz.complex_count);

        std::vector<float> stream;
        std::vector<float> t(chain::kTensorFloats);
        while (chain.ready() > 0 && chain.pull_tensor(t.data()))
            stream.insert(stream.end(), t.begin(), t.end());

        iqdloop::apply_d2_restore_to_stream(stream, chain::kFrameComplex,
                                            fz.original_dc_i, fz.original_dc_q,
                                            fz.d2_rec_scale);
        const std::vector<float> ref =
            iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                           fz.recovered_tensor_sha256);
        const iqdloop::ClassificationWindow cw =
            iqdloop::select_classification_window(stream, ref);

        std::printf("  clean24 chain %s src_class=%d corr=%.6f nmse=%.6f delay=%d\n",
                    fz.file_name.c_str(), fz.source_class, cw.tensor_corr,
                    cw.tensor_nmse, cw.delay_offset);
        if (cw.valid) {
            ++all_valid;
            min_corr = std::min(min_corr, cw.tensor_corr);
        }
    }
    check(all_valid == static_cast<int>(frozen.size()),
          "chain: every clean24 window valid");
    check(min_corr > 0.99, "chain: min tensor_corr > 0.99 (got " +
          std::to_string(min_corr) + ")");

    // 5. Baseline <-> D2-manifest identity pairing (the acceptance gate contract):
    //    every holdout file must match a baseline row on source_index +
    //    original_sha256 + raw24_class + modulation + split_role, 1:1.
    bool pairing_ok = true;
    for (const auto& fz : frozen) {
        auto it = baseline.find(static_cast<std::uint64_t>(fz.source_index));
        if (it == baseline.end()) { pairing_ok = false; continue; }
        if (it->second.original_sha256 != fz.original_sha256 ||
            it->second.raw24_class != fz.source_class ||
            it->second.modulation != fz.modulation ||
            it->second.split_role != fz.split_role) {
            pairing_ok = false;
        }
    }
    check(pairing_ok, "pairing: baseline identity matches D2 manifest 1:1 (5 fields)");

    // Reverse direction: every baseline key has a matching frozen file.
    bool reverse_ok = true;
    for (const auto& kv : baseline) {
        bool found = false;
        for (const auto& fz : frozen)
            if (static_cast<std::uint64_t>(fz.source_index) == kv.first) found = true;
        if (!found) reverse_ok = false;
    }
    check(reverse_ok, "pairing: every baseline source_index has a frozen file");
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
    std::printf("test_clean_iq_24class_bf16_fix10\n");
    run_test("phase_surface", test_phase_surface);

    const std::string frozen_dir = (argc > 1 && argv[1][0])
            ? argv[1] : "../clean24_smoke";
    const std::string baseline_path = (argc > 2 && argv[2][0])
            ? argv[2] : "../baselines/clean24_smoke_raw24_bf16_baseline.tsv";
    try {
        test_frozen_chain_and_baseline_pairing(frozen_dir, baseline_path);
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in frozen_chain_and_baseline_pairing: %s\n", e.what());
        ++g_fail;
    }

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
