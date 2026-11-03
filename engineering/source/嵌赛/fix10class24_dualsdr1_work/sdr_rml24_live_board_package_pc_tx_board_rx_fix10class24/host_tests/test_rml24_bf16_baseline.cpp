// test_rml24_bf16_baseline.cpp -- host tests for the 7-column raw-24 BF16 baseline
// loader (rml24_bf16_baseline.hpp).  fix10class24-dualsdr1 §6.
//
// A valid 7-column row parses with the frozen raw24 prediction preserved; every
// fail-closed rejection throws: bad original_sha256, bad model_sha256, out-of-range
// raw24_class, out-of-range frozen_bf16_raw24_pred, non-holdout split_role, short
// row, duplicate source_index, and empty baseline.
//
// The loader is the exact one the runner uses (rml24bf16::load_baseline); this test
// is iCraft-free and libiio-free.

#include "../board_package/rml24_bf16_baseline.hpp"

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

const char* kHeader =
    "source_index\toriginal_sha256\traw24_class\tmodulation\tsplit_role\t"
    "frozen_bf16_raw24_pred\tmodel_sha256";

std::string hex64(std::uint64_t n) {
    static const char* d = "0123456789abcdef";
    std::string s(64, '0');
    for (int i = 63; i >= 0; --i) { s[static_cast<std::size_t>(i)] = d[n & 0xfu]; n >>= 4; }
    return s;
}

const char* kModelSha = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42";

std::string row(std::uint64_t src, const std::string& sha, int raw24, int pred,
                const std::string& mod, const std::string& role = "holdout",
                const std::string& model = kModelSha) {
    return std::to_string(src) + "\t" + sha + "\t" + std::to_string(raw24) + "\t" +
           mod + "\t" + role + "\t" + std::to_string(pred) + "\t" + model;
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

std::string write_baseline(const std::string& dir, const std::string& rows) {
    const std::string path = dir + "/baseline.tsv";
    write_text(path, std::string(kHeader) + "\n" + rows);
    return path;
}
#endif

// ---------------------------------------------------------------------------
// valid parse
// ---------------------------------------------------------------------------
void test_load_valid() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_valid");
    std::string rows;
    // WC (raw 17) and SC (raw 18) must load as two independent raw24 classes.
    rows += row(8500, hex64(1), 17, 17, "AM-SSB-WC") + "\n";
    rows += row(9000, hex64(2), 18, 18, "AM-SSB-SC") + "\n";
    rows += row(0, hex64(3), 0, 5, "OOK") + "\n";   // pred deliberately != label
    const std::string path = write_baseline(dir, rows);

    const auto m = rml24bf16::load_baseline(path, 24);
    check(m.size() == 3, "valid: three rows loaded");
    check(m.count(8500) == 1 && m.count(9000) == 1 && m.count(0) == 1,
          "valid: keys 8500/9000/0 present");
    check(m.at(8500).raw24_class == 17, "valid: WC raw24_class 17");
    check(m.at(9000).raw24_class == 18, "valid: SC raw24_class 18");
    check(m.at(8500).frozen_bf16_raw24_pred == 17, "valid: WC pred 17");
    check(m.at(9000).frozen_bf16_raw24_pred == 18, "valid: SC pred 18");
    check(m.at(0).frozen_bf16_raw24_pred == 5, "valid: OOK pred 5 (not label 0)");
    check(m.at(0).raw24_class == 0, "valid: OOK raw24_class 0");
    check(m.at(0).modulation == "OOK", "valid: modulation preserved");
    check(m.at(0).model_sha256 == kModelSha, "valid: model_sha256 preserved");
    check(m.at(0).split_role == "holdout", "valid: split_role holdout");
    check(m.at(0).original_sha256 == hex64(3), "valid: original_sha256 preserved");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_load_valid_all_24_classes() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_all24");
    std::string rows;
    for (int c = 0; c < 24; ++c)
        rows += row(static_cast<std::uint64_t>(c) * 500, hex64(c), c, c,
                    std::to_string(c)) + "\n";
    const std::string path = write_baseline(dir, rows);
    const auto m = rml24bf16::load_baseline(path, 24);
    check(m.size() == 24, "valid-all24: 24 rows loaded");
    check(m.at(8500).raw24_class == 17 && m.at(9000).raw24_class == 18,
          "valid-all24: WC/SC both present as distinct raw24 classes");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---------------------------------------------------------------------------
// rejections
// ---------------------------------------------------------------------------
void test_reject_bad_original_sha() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_badsha");
    const std::string path = write_baseline(dir, row(0, "zz", 0, 0, "OOK"));
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: non-64-hex original_sha256");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_reject_bad_model_sha() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_badmodel");
    const std::string path = write_baseline(dir, row(0, hex64(1), 0, 0, "OOK",
                                                      "holdout", "zz"));
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: non-64-hex model_sha256");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_reject_bad_raw24_class() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_badcls");
    const std::string path = write_baseline(dir, row(0, hex64(1), 24, 0, "OOK"));
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: raw24_class == 24 out of range");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_reject_bad_pred() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_badpred");
    const std::string path = write_baseline(dir, row(0, hex64(1), 0, 24, "OOK"));
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: frozen_bf16_raw24_pred == 24 out of range");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_reject_bad_role() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_badrole");
    const std::string path = write_baseline(dir, row(0, hex64(1), 0, 0, "OOK",
                                                      "calibration"));
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: non-holdout split_role");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_reject_short_row() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_short");
    // 6 columns (missing model_sha256).
    const std::string path = write_baseline(dir,
        "0\t" + hex64(1) + "\t0\tOOK\tholdout\t0");
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: short (6-col) row");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_reject_duplicate() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_dup");
    std::string rows = row(0, hex64(1), 0, 0, "OOK") + "\n" +
                       row(0, hex64(2), 0, 1, "OOK") + "\n";
    const std::string path = write_baseline(dir, rows);
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: duplicate source_index");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_reject_empty() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml24_base_empty");
    const std::string path = write_baseline(dir, "");  // header only
    check_throws([&] { rml24bf16::load_baseline(path, 24); },
                 "reject: empty baseline");
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void test_is_hex64() {
    check(rml24bf16::is_hex64(kModelSha), "is_hex64: valid 64-hex");
    check(rml24bf16::is_hex64(hex64(0)), "is_hex64: all-zero 64-hex");
    check(!rml24bf16::is_hex64(""), "is_hex64: empty rejected");
    check(!rml24bf16::is_hex64("abc"), "is_hex64: short rejected");
    check(!rml24bf16::is_hex64(std::string(64, 'g')), "is_hex64: non-hex rejected");
    check(!rml24bf16::is_hex64(std::string(64, 'A')), "is_hex64: uppercase rejected");
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

int main() {
    std::printf("test_rml24_bf16_baseline\n");
    run_test("load_valid", test_load_valid);
    run_test("load_valid_all_24_classes", test_load_valid_all_24_classes);
    run_test("reject_bad_original_sha", test_reject_bad_original_sha);
    run_test("reject_bad_model_sha", test_reject_bad_model_sha);
    run_test("reject_bad_raw24_class", test_reject_bad_raw24_class);
    run_test("reject_bad_pred", test_reject_bad_pred);
    run_test("reject_bad_role", test_reject_bad_role);
    run_test("reject_short_row", test_reject_short_row);
    run_test("reject_duplicate", test_reject_duplicate);
    run_test("reject_empty", test_reject_empty);
    run_test("is_hex64", test_is_hex64);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
