// test_clean2b_smoke_protocol.cpp -- fix10clean2b-smoke Step 5: host test of the
// runner's baseline + loader wiring for the two clean2b smoke samples.
//
// iCraft-free and libiio-free (no NPU, no device, no TCP).  It locks three contracts
// the runner relies on:
//
//   (1) the fix9r 6-column baseline (clean2b_smoke_baseline.tsv, consumed by
//       iqrffix9r::load_baseline) parses source_index/original_sha256/
//       deployed_class/modulation/split_role/frozen_baseline_pred for the two samples;
//   (2) the CLEAN 6-column baseline (clean2b_smoke_clean_baseline.tsv, consumed by
//       iqclean23fix10::load_clean_baseline) parses source_index/file_name/sha256/
//       deployed_class/split_role/frozen_baseline_pred -- a DIFFERENT schema (quantized
//       ci16 SHA, not source-float SHA), proving the two are never cross-wired;
//   (3) dispatch separation: iqdloop::load_frozen_iq REJECTS the clean2b input kind,
//       because the runner routes radioml-compatible-clean-d2-2p56m through
//       clean2b::load_clean2b_sidecar (its ternary), never through the red-line
//       load_frozen_iq header (which still only knows the original three kinds).

#include "../board_package/iq_rf_fix9r_baseline.hpp"
#include "../board_package/iq_clean_baseline.hpp"
#include "../board_package/iq_clean2b_sidecar.hpp"
#include "../board_package/iq_digital_loopback.hpp"

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

template <typename Fn>
void check_throws(Fn&& fn, const std::string& what) {
    bool threw = false;
    try { fn(); }
    catch (const std::exception&) { threw = true; }
    catch (...) { threw = true; }
    check(threw, what);
}

#if defined(__unix__) || defined(__APPLE__)

std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

void write_text(const std::string& path, const std::string& text) {
    std::ofstream f(path, std::ios::binary);
    f.write(text.data(), static_cast<std::streamsize>(text.size()));
    f.close();
}

std::string hex64(std::uint64_t n) {
    static const char* d = "0123456789abcdef";
    std::string s(64, '0');
    for (int i = 63; i >= 0; --i) { s[static_cast<std::size_t>(i)] = d[n & 0xfu]; n >>= 4; }
    return s;
}

#endif  // __unix__

// fix9r 6-col baseline: source_index original_sha256 deployed_class modulation
//                        split_role frozen_baseline_pred
const char* kFix9rHeader =
    "source_index\toriginal_sha256\tdeployed_class\tmodulation\tsplit_role\t"
    "frozen_baseline_pred";

// clean 6-col baseline: source_index file_name sha256 deployed_class split_role
//                       frozen_baseline_pred
const char* kCleanHeader =
    "source_index\tfile_name\tsha256\tdeployed_class\tsplit_role\tfrozen_baseline_pred";

void test_fix9r_baseline_wiring() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_fix9r");
    std::string rows;
    rows += "1500\t" + hex64(0xAAAAAAAAAAAAAAAAULL) + "\t3\tBPSK\tholdout\t3\n";
    rows += "500\t" + hex64(0xBBBBBBBBBBBBBBBBULL) + "\t1\t4ASK\tholdout\t1\n";
    const std::string path = dir + "/clean2b_smoke_baseline.tsv";
    write_text(path, std::string(kFix9rHeader) + "\n" + rows);

    const auto m = iqrffix9r::load_baseline(path, 23);
    check(m.size() == 2, "fix9r-baseline: two rows loaded");
    check(m.count(1500) == 1 && m.count(500) == 1, "fix9r-baseline: keys 1500 and 500");
    check(m.at(1500).deployed_class == 3 && m.at(1500).frozen_baseline_pred == 3,
          "fix9r-baseline: BPSK deployed=3 pred=3");
    check(m.at(500).deployed_class == 1 && m.at(500).frozen_baseline_pred == 1,
          "fix9r-baseline: 4ASK deployed=1 pred=1");
    check(m.at(1500).modulation == "BPSK" && m.at(500).modulation == "4ASK",
          "fix9r-baseline: modulation BPSK/4ASK");
    check(m.at(1500).split_role == "holdout", "fix9r-baseline: split_role holdout");
    check(m.at(1500).sha256 == hex64(0xAAAAAAAAAAAAAAAAULL),
          "fix9r-baseline: original_sha256 (source-float) preserved");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_fix9r_baseline_reject_duplicate() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_fix9r_dup");
    std::string rows;
    rows += "1500\t" + hex64(0xAAAAAAAAAAAAAAAAULL) + "\t3\tBPSK\tholdout\t3\n";
    rows += "1500\t" + hex64(0xBBBBBBBBBBBBBBBBULL) + "\t1\t4ASK\tholdout\t1\n";
    const std::string path = dir + "/clean2b_smoke_baseline.tsv";
    write_text(path, std::string(kFix9rHeader) + "\n" + rows);
    check_throws([&] { iqrffix9r::load_baseline(path, 23); },
                 "fix9r-baseline: duplicate source_index throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_clean_baseline_wiring() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_clean");
    std::string rows;
    rows += "1500\tclean_bpsk_4713bc2e.ci16\t" + hex64(0xCCCCCCCCCCCCCCCCULL) +
            "\t3\tholdout\t3\n";
    rows += "500\tclean_4ask_a413e2d4.ci16\t" + hex64(0xDDDDDDDDDDDDDDDDULL) +
            "\t1\tholdout\t1\n";
    const std::string path = dir + "/clean2b_smoke_clean_baseline.tsv";
    write_text(path, std::string(kCleanHeader) + "\n" + rows);

    const auto m = iqclean23fix10::load_clean_baseline(path, 23);
    check(m.size() == 2, "clean-baseline: two rows loaded");
    check(m.count(1500) == 1 && m.count(500) == 1, "clean-baseline: keys 1500 and 500");
    check(m.at(1500).deployed_class == 3 && m.at(1500).frozen_baseline_pred == 3,
          "clean-baseline: BPSK deployed=3 pred=3");
    check(m.at(500).deployed_class == 1 && m.at(500).frozen_baseline_pred == 1,
          "clean-baseline: 4ASK deployed=1 pred=1");
    check(m.at(1500).file_name == "clean_bpsk_4713bc2e.ci16",
          "clean-baseline: file_name is the quantized ci16");
    check(m.at(1500).sha256 == hex64(0xCCCCCCCCCCCCCCCCULL),
          "clean-baseline: sha256 (quantized ci16) preserved");
    check(m.at(1500).sha256 != hex64(0xAAAAAAAAAAAAAAAAULL),
          "clean-baseline: sha256 != fix9r original_sha256 (schemas not cross-wired)");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// Dispatch separation: the clean2b input kind must never reach the red-line
// load_frozen_iq header (which only knows generated/radioml-reconstructed/radioml-d2).
void test_dispatch_separation() {
    check_throws(
        [] {
            iqdloop::load_frozen_iq("/nonexistent", "radioml-compatible-clean-d2-2p56m");
        },
        "dispatch: load_frozen_iq rejects clean2b kind (routes via clean2b sidecar)");
    check_throws(
        [] { iqdloop::load_frozen_iq("/nonexistent", "radioml-bogus"); },
        "dispatch: load_frozen_iq rejects unknown kind (fail-closed)");
    check(std::string(clean2b::manifest_name_for_kind(
              "radioml-compatible-clean-d2-2p56m")) == "clean2b_smoke_manifest.tsv",
          "dispatch: clean2b kind selects the clean2b manifest");
}

}  // namespace

int main() {
    std::printf("test_clean2b_smoke_protocol\n");

    test_fix9r_baseline_wiring();
    test_fix9r_baseline_reject_duplicate();
    test_clean_baseline_wiring();
    test_dispatch_separation();

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
