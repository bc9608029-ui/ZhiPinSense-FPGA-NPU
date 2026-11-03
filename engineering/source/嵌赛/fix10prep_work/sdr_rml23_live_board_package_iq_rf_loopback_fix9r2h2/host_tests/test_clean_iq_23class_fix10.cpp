// test_clean_iq_23class_fix10.cpp -- fix10-prep Stage 3 (N8): host test of the
// GENERATED-CLEAN digital-baseline path (Path B) and its loader/runner contracts.
//
// Two parts, both iCraft-free and libiio-free (no NPU, no device):
//
//   Part 1 (pure C++): iqclean23fix10::load_clean_baseline -- a valid 6-column
//     clean baseline parses with the frozen prediction preserved, and every
//     fail-closed rejection (bad sha, duplicate source_index, out-of-range
//     deployed_class, out-of-range frozen_baseline_pred, non-holdout split_role,
//     short row, unsafe file_name, empty) throws.
//
//   Part 2 (__unix__ only): the REAL generator (gen_generated_clean_23.py) ->
//     iqdloop::load_d2_sidecar -> load_ci16 -> PreprocessChain (2.56 MHz -> 128 kHz
//     FIR decimation) -> apply_d2_restore_to_stream -> load_recovered_tensor ->
//     select_classification_window, asserting the C++ digital chain reproduces the
//     Python-computed recovered [2,1024] tensor.  This is the WHOLE of Path B's
//     digital half (CI16 -> window), minus the NPU inference.
//
// The generator is invoked WITHOUT `python3 -I`: this WSL install has numpy in the
// USER site-packages (~/.local/...), which `-I` (== -s) hides.  The generator and
// its sibling scripts are trusted repo code and the CWD is host_tests/ (no untrusted
// data dir in play), so the shadow-import risk `-I` guards against does not apply.
// The interpreter is overridable via argv[2] or FIX10PREP_PYTHON (default python3).

#include "../board_package/iq_clean_baseline.hpp"
#include "../board_package/iq_digital_loopback.hpp"
#include "../board_package/gate9_phase.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <sys/wait.h>
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

const char* kCleanBaselineHeader =
    "source_index\tfile_name\tsha256\tdeployed_class\tsplit_role\tfrozen_baseline_pred";

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

// One clean-baseline row (6 columns).  frozen_baseline_pred is deliberately set
// DIFFERENT from deployed_class where possible, so a loader that back-filled from
// the label would be caught.
std::string clean_baseline_row(std::uint64_t src, int dep, int pred,
                               const std::string& sha, const std::string& name,
                               const std::string& role = "holdout") {
    std::ostringstream o;
    o << src << "\t" << name << "\t" << sha << "\t" << dep << "\t" << role << "\t"
      << pred;
    return o.str();
}

std::string write_clean_baseline(const std::string& dir, const std::string& rows) {
    const std::string path = dir + "/clean_baseline.tsv";
    write_text(path, std::string(kCleanBaselineHeader) + "\n" + rows);
    return path;
}

// Run `python <generator> --per-class 1 --out-dir <dir>`.  Returns WEXITSTATUS.
int run_generator(const std::string& python, const std::string& generator,
                  const std::string& out_dir) {
    std::string cmd = python + " \"" + generator + "\" --per-class 1 --out-dir \"" +
                      out_dir + "\" >/dev/null 2>&1";
    const int status = ::system(cmd.c_str());
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return -1;
}

std::string pick_python(int argc, char** argv) {
    if (argc > 2) return argv[2];
    const char* env = std::getenv("FIX10PREP_PYTHON");
    if (env && env[0]) return env;
    return "python3";
}

#endif

// ===========================================================================
// Part 1: load_clean_baseline (pure C++, file-writing guarded to __unix__).
// ===========================================================================

void test_load_clean_baseline_valid() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_valid");
    std::string rows;
    rows += clean_baseline_row(0, 3, 5, hex64(1), "clean_d2_2p56m_000000.ci16") + "\n";
    rows += clean_baseline_row(17, 17, 12, hex64(2), "clean_d2_2p56m_000017.ci16") + "\n";
    const std::string path = write_clean_baseline(dir, rows);

    const auto m = iqclean23fix10::load_clean_baseline(path, 23);
    check(m.size() == 2, "baseline-valid: two rows loaded");
    check(m.count(0) == 1 && m.count(17) == 1, "baseline-valid: keys 0 and 17 present");
    check(m.at(0).frozen_baseline_pred == 5, "baseline-valid: pred 5 preserved (not label 3)");
    check(m.at(0).deployed_class == 3, "baseline-valid: deployed_class 3");
    check(m.at(0).file_name == "clean_d2_2p56m_000000.ci16", "baseline-valid: file_name");
    check(m.at(0).sha256 == hex64(1), "baseline-valid: sha256");
    check(m.at(0).split_role == "holdout", "baseline-valid: split_role holdout");
    check(m.at(17).deployed_class == 17 && m.at(17).frozen_baseline_pred == 12,
          "baseline-valid: AM-SSB row pred 12 (not label 17)");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_bad_sha() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_badsha");
    const std::string path = write_clean_baseline(dir,
        clean_baseline_row(0, 3, 5, "zz", "clean_d2_2p56m_000000.ci16"));
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: non-64-hex sha throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_duplicate() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_dup");
    std::string rows;
    rows += clean_baseline_row(0, 3, 5, hex64(1), "clean_d2_2p56m_000000.ci16") + "\n";
    rows += clean_baseline_row(0, 4, 6, hex64(2), "clean_d2_2p56m_000000.ci16") + "\n";
    const std::string path = write_clean_baseline(dir, rows);
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: duplicate source_index throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_bad_deployed() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_baddep");
    const std::string path = write_clean_baseline(dir,
        clean_baseline_row(0, 23, 5, hex64(1), "clean_d2_2p56m_000000.ci16"));
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: deployed_class out of range throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_bad_pred() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_badpred");
    const std::string path = write_clean_baseline(dir,
        clean_baseline_row(0, 3, 23, hex64(1), "clean_d2_2p56m_000000.ci16"));
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: frozen_baseline_pred out of range throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_bad_role() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_badrole");
    const std::string path = write_clean_baseline(dir,
        clean_baseline_row(0, 3, 5, hex64(1), "clean_d2_2p56m_000000.ci16", "calibration"));
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: non-holdout split_role throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_short_row() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_short");
    // 5 columns only (missing frozen_baseline_pred).
    const std::string path = write_clean_baseline(dir,
        "0\tclean_d2_2p56m_000000.ci16\t" + hex64(1) + "\t3\tholdout");
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: short (5-col) row throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_unsafe_name() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_unsafe");
    const std::string path = write_clean_baseline(dir,
        clean_baseline_row(0, 3, 5, hex64(1), "../evil.ci16"));
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: unsafe file_name throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_clean_baseline_reject_empty() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_base_empty");
    const std::string path = write_clean_baseline(dir, "");  // header only, no rows
    check_throws([&] { iqclean23fix10::load_clean_baseline(path, 23); },
                 "baseline-reject: empty baseline throws");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// Phase surface (mirrors the dual-SDR fix10 test): the new clean phase is
// accepted; near-misses and empty are rejected.
void test_phase_surface() {
    check(gate9::valid_phase("iq-clean-iq-23class-fix10"),
          "phase: valid_phase accepts iq-clean-iq-23class-fix10");
    check(!gate9::valid_phase("iq-clean-iq-23class-fix10x"),
          "phase: valid_phase rejects trailing-x near-miss");
    check(!gate9::valid_phase("iq-clean-iq-23class-fix1"),
          "phase: valid_phase rejects truncated near-miss");
    check(!gate9::valid_phase(""),
          "phase: valid_phase rejects empty");
    check(gate9::valid_phase("iq-dual-sdr-23class-fix10"),
          "phase: valid_phase still accepts iq-dual-sdr-23class-fix10");
}

// ===========================================================================
// Part 2: generator -> C++ chain -> D2 restore -> window round-trip.
// ===========================================================================

void test_chain_roundtrip(const std::string& python, const std::string& generator) {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean_chain_e2e");
    const int code = run_generator(python, generator, dir);
    check(code == 0, "e2e: generator exit 0 (got " + std::to_string(code) + ")");
    if (code != 0) { ::rmdir(dir.c_str()); return; }

    const std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(dir, "radioml-d2-2p56m");
    check(frozen.size() == 24, "e2e: 24 clean D2 files loaded (got " +
          std::to_string(frozen.size()) + ")");
    if (frozen.empty()) { ::rmdir(dir.c_str()); return; }

    double min_corr = 2.0, sum_corr = 0.0;
    int all_valid = 0;
    int all_holdout = 0;
    for (const auto& fz : frozen) {
        if (!fz.is_calibration && fz.split_role == "holdout") ++all_holdout;
        if (fz.deployed_class != rml23::kSourceToDeployed[fz.source_class]) {
            check(false, "e2e: deployed/source mapping consistent for " + fz.file_name);
            continue;
        }

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

        std::printf("  clean chain %s corr=%.6f nmse=%.6f delay=%d\n",
                    fz.file_name.c_str(), cw.tensor_corr, cw.tensor_nmse,
                    cw.delay_offset);
        if (cw.valid) {
            ++all_valid;
            min_corr = std::min(min_corr, cw.tensor_corr);
            sum_corr += cw.tensor_corr;
        }
    }

    check(all_holdout == static_cast<int>(frozen.size()),
          "e2e: every clean file is holdout (no calibration in the clean set)");
    check(all_valid == static_cast<int>(frozen.size()),
          "e2e: every clean window is valid");
    const double mean_corr = frozen.empty() ? 0.0 : sum_corr / frozen.size();
    std::printf("  clean chain corr: min=%.6f mean=%.6f (n=%zu)\n",
                min_corr, mean_corr, frozen.size());
    check(min_corr > 0.99, "e2e: min tensor_corr > 0.99 (got " +
          std::to_string(min_corr) + ")");

    // cleanup: unlink every artifact the generator wrote, then rmdir.
    for (const auto& fz : frozen) {
        ::unlink(fz.path.c_str());
        ::unlink(fz.recovered_tensor_path.c_str());
    }
    ::unlink((dir + "/route_d2_rf_manifest.tsv").c_str());
    ::unlink((dir + "/clean_manifest.tsv").c_str());
    ::unlink((dir + "/clean_build.json").c_str());
    ::rmdir(dir.c_str());
#else
    (void)python; (void)generator;
#endif
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
    std::printf("test_clean_iq_23class_fix10\n");

    run_test("baseline_valid", test_load_clean_baseline_valid);
    run_test("baseline_reject_bad_sha", test_load_clean_baseline_reject_bad_sha);
    run_test("baseline_reject_duplicate", test_load_clean_baseline_reject_duplicate);
    run_test("baseline_reject_bad_deployed", test_load_clean_baseline_reject_bad_deployed);
    run_test("baseline_reject_bad_pred", test_load_clean_baseline_reject_bad_pred);
    run_test("baseline_reject_bad_role", test_load_clean_baseline_reject_bad_role);
    run_test("baseline_reject_short_row", test_load_clean_baseline_reject_short_row);
    run_test("baseline_reject_unsafe_name", test_load_clean_baseline_reject_unsafe_name);
    run_test("baseline_reject_empty", test_load_clean_baseline_reject_empty);
    run_test("phase_surface", test_phase_surface);

    const std::string generator = (argc > 1 && argv[1][0])
            ? argv[1]
            : "../scripts/gen_generated_clean_23.py";
    const std::string python = pick_python(argc, argv);
    try {
        test_chain_roundtrip(python, generator);
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in chain_roundtrip: %s\n", e.what());
        ++g_fail;
    }

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
