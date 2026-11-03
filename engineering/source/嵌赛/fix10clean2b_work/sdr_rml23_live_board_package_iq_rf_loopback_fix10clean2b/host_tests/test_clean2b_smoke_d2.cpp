// test_clean2b_smoke_d2.cpp -- fix10clean2b-smoke Step 5: host test of the
// radioml-compatible-clean-d2-2p56m sidecar loader + manifest-name selection.
//
// iCraft-free and libiio-free (no NPU, no device).  Two parts:
//
//   Part 1 (pure C++): clean2b::manifest_name_for_kind / manifest_path_for_kind
//     select the right manifest per input_kind and FAIL CLOSED on any unknown
//     kind (never a silent fallback to route_d2_rf_manifest.tsv).
//
//   Part 2 (__unix__ only): clean2b::load_clean2b_sidecar parses a 27-column
//     clean2b_smoke_manifest.tsv (first 24 columns == route_d2_rf_manifest.tsv
//     schema, +3 provenance columns) into 2 FrozenIq entries with the D2 restore
//     + recovered-tensor references SHA/size-verified, and every fail-closed
//     rejection throws (short row, wrong class, mapping mismatch, bad SHA, tx_scale
//     self-inconsistency, duplicate source_index, wrong frozen predictions).

#include "../board_package/iq_clean2b_sidecar.hpp"
#include "../board_package/iq_digital_loopback.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <sstream>
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

// 27-column clean2b_smoke_manifest.tsv header (first 24 == route_d2_rf_manifest.tsv).
const char* kHeader =
    "sample_index\tsource_index\traw24_class\tdeployed23_class\tmodulation\tsnr_db\t"
    "split_role\tglobal_K\toriginal_dc_i\toriginal_dc_q\tac_rms\trec_scale\t"
    "complex_count\tsample_rate\ttx_rms\ttx_peak\tclip_count\tedge_policy\tguard\t"
    "original_sha256\tquantized_sha256\trecovered_tensor_sha256\tquantized_file\t"
    "recovered_tensor_file\ttx_scale\tfrozen_raw24_pred\tfrozen_deployed23_pred";

const char* kQBpsk = "clean_bpsk_4713bc2e.ci16";
const char* kQ4ask = "clean_4ask_a413e2d4.ci16";
const char* kRBpsk = "recovered_tensor_clean_bpsk.f32";
const char* kR4ask = "recovered_tensor_clean_4ask.f32";

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

std::string sha256_file(const std::string& path) {
    bool ok = false;
    const std::string h = sdr::sha256_hex_file(path, &ok);
    return ok ? h : std::string();
}

std::string hex64(std::uint64_t n) {
    static const char* d = "0123456789abcdef";
    std::string s(64, '0');
    for (int i = 63; i >= 0; --i) { s[static_cast<std::size_t>(i)] = d[n & 0xfu]; n >>= 4; }
    return s;
}

void write_ci16(const std::string& path, std::uint64_t complex_count, int tag) {
    std::ofstream f(path, std::ios::binary);
    for (std::uint64_t i = 0; i < complex_count; ++i) {
        const std::int16_t re = static_cast<std::int16_t>(((i * 7 + tag) % 4096) - 2048);
        const std::int16_t im = static_cast<std::int16_t>(((i * 13 + tag * 3) % 4096) - 2048);
        f.write(reinterpret_cast<const char*>(&re), 2);
        f.write(reinterpret_cast<const char*>(&im), 2);
    }
    f.close();
}

void write_f32(const std::string& path, std::size_t n, int tag) {
    std::ofstream f(path, std::ios::binary);
    for (std::size_t i = 0; i < n; ++i) {
        const float v = static_cast<float>(((i * 5 + tag) % 2000) - 1000) / 1000.0f;
        f.write(reinterpret_cast<const char*>(&v), 4);
    }
    f.close();
}

// Write the 6 binary artifacts (2 ci16 + 2 recovered f32 + their SHAs are returned)
// and the manifest content for the two clean2b smoke samples.
struct Sha4 { std::string qb, qa, rb, ra; };

Sha4 write_binary_fixture(const std::string& dir) {
    write_ci16(dir + "/" + kQBpsk, 53760, 1);
    write_ci16(dir + "/" + kQ4ask, 53760, 2);
    write_f32(dir + "/" + kRBpsk, chain::kTensorFloats, 1);
    write_f32(dir + "/" + kR4ask, chain::kTensorFloats, 2);
    Sha4 s;
    s.qb = sha256_file(dir + "/" + kQBpsk);
    s.qa = sha256_file(dir + "/" + kQ4ask);
    s.rb = sha256_file(dir + "/" + kRBpsk);
    s.ra = sha256_file(dir + "/" + kR4ask);
    return s;
}

// One 27-column row.  frozen_raw24 / frozen_deployed23 default to raw24 / dep23;
// tx_scale defaults to kAdcFullScale/tx_rms == 2048/2048 == 1.0.
std::string manifest_row(long long src, int raw24, int dep23, const std::string& mod,
                         const std::string& orig_sha, const std::string& quant_sha,
                         const std::string& rec_sha, const std::string& qfile,
                         const std::string& rfile, double tx_scale = 1.0,
                         int frozen_raw24 = -1, int frozen_deployed23 = -1) {
    std::ostringstream o;
    o << src << "\t" << src << "\t" << raw24 << "\t" << dep23 << "\t" << mod << "\t"
      << "nan\t"
      << "holdout\t"
      << "2048\t"
      << "0.0\t0.0\t1.0\t1.0\t"
      << "53760\t2560000\t2048.0\t2048.0\t0\tzero\t832\t"
      << orig_sha << "\t" << quant_sha << "\t" << rec_sha << "\t"
      << qfile << "\t" << rfile << "\t"
      << tx_scale << "\t"
      << (frozen_raw24 < 0 ? raw24 : frozen_raw24) << "\t"
      << (frozen_deployed23 < 0 ? dep23 : frozen_deployed23);
    return o.str();
}

std::string valid_rows(const Sha4& s) {
    std::string rows;
    rows += manifest_row(1500, 3, 3, "BPSK", hex64(0xAAAAAAAAAAAAAAAAULL), s.qb, s.rb,
                         kQBpsk, kRBpsk) + "\n";
    rows += manifest_row(500, 1, 1, "4ASK", hex64(0xBBBBBBBBBBBBBBBBULL), s.qa, s.ra,
                         kQ4ask, kR4ask) + "\n";
    return rows;
}

void write_manifest(const std::string& dir, const std::string& rows) {
    write_text(dir + "/clean2b_smoke_manifest.tsv",
               std::string(kHeader) + "\n" + rows);
}

void cleanup(const std::string& dir) {
    ::unlink((dir + "/" + kQBpsk).c_str());
    ::unlink((dir + "/" + kQ4ask).c_str());
    ::unlink((dir + "/" + kRBpsk).c_str());
    ::unlink((dir + "/" + kR4ask).c_str());
    ::unlink((dir + "/clean2b_smoke_manifest.tsv").c_str());
    ::rmdir(dir.c_str());
}

#endif  // __unix__

// ===========================================================================
// Part 1: manifest-name / path selection (pure, no file I/O).
// ===========================================================================

void test_manifest_name_selection() {
    check(std::string(clean2b::manifest_name_for_kind("radioml-d2-2p56m")) ==
              "route_d2_rf_manifest.tsv",
          "name: radioml-d2-2p56m -> route_d2_rf_manifest.tsv");
    check(std::string(clean2b::manifest_name_for_kind(
              "radioml-compatible-clean-d2-2p56m")) == "clean2b_smoke_manifest.tsv",
          "name: clean2b kind -> clean2b_smoke_manifest.tsv");
    check_throws([] { clean2b::manifest_name_for_kind("radioml-bogus"); },
                 "name: unknown kind throws (fail-closed)");
}

void test_manifest_path_selection() {
    check(clean2b::manifest_path_for_kind("/x", "radioml-d2-2p56m") ==
              "/x/route_d2_rf_manifest.tsv",
          "path: /x + d2 kind joins without double sep");
    check(clean2b::manifest_path_for_kind("/x/", "radioml-compatible-clean-d2-2p56m") ==
              "/x/clean2b_smoke_manifest.tsv",
          "path: trailing-slash dir joins clean2b name");
    check(clean2b::manifest_path_for_kind("/x\\", "radioml-d2-2p56m") ==
              "/x\\route_d2_rf_manifest.tsv",
          "path: trailing-backslash dir joins d2 name");
    check(clean2b::manifest_path_for_kind("", "radioml-compatible-clean-d2-2p56m") ==
              "clean2b_smoke_manifest.tsv",
          "path: empty dir returns bare name");
    check_throws([] { clean2b::manifest_path_for_kind("/x", "radioml-bogus"); },
                 "path: unknown kind throws (fail-closed)");
}

// ===========================================================================
// Part 2: load_clean2b_sidecar (file fixture, __unix__ only).
// ===========================================================================

void test_load_sidecar_valid() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_valid");
    const Sha4 s = write_binary_fixture(dir);
    write_manifest(dir, valid_rows(s));

    const std::vector<iqdloop::FrozenIq> fz = clean2b::load_clean2b_sidecar(dir);
    check(fz.size() == 2, "sidecar-valid: 2 samples loaded");

    const iqdloop::FrozenIq* bpsk = nullptr;
    const iqdloop::FrozenIq* ask = nullptr;
    for (const auto& q : fz) {
        if (q.source_index == 1500) bpsk = &q;
        if (q.source_index == 500) ask = &q;
    }
    check(bpsk != nullptr && ask != nullptr, "sidecar-valid: source_index 1500 and 500 present");
    if (bpsk && ask) {
        check(bpsk->source_class == 3 && bpsk->deployed_class == 3,
              "sidecar-valid: BPSK raw24=3 deployed23=3");
        check(ask->source_class == 1 && ask->deployed_class == 1,
              "sidecar-valid: 4ASK raw24=1 deployed23=1");
        check(bpsk->modulation == "BPSK" && ask->modulation == "4ASK",
              "sidecar-valid: modulation BPSK/4ASK");
        check(bpsk->split_role == "holdout" && ask->split_role == "holdout",
              "sidecar-valid: split_role holdout");
        check(bpsk->has_d2_restore && ask->has_d2_restore,
              "sidecar-valid: has_d2_restore set");
        check(bpsk->has_recovered_ref && ask->has_recovered_ref,
              "sidecar-valid: has_recovered_ref set");
        check(bpsk->complex_count == 53760 && bpsk->byte_count == 53760 * 4,
              "sidecar-valid: complex_count/byte_count");
        check(bpsk->sample_rate == iqdloop::kFrozenFsIn,
              "sidecar-valid: sample_rate 2560000");
        check(bpsk->original_sha256 == hex64(0xAAAAAAAAAAAAAAAAULL),
              "sidecar-valid: original_sha256 (source float) preserved");
        check(bpsk->sha256 == s.qb, "sidecar-valid: quantized_sha256 == ci16 SHA");
        check(bpsk->recovered_tensor_sha256 == s.rb,
              "sidecar-valid: recovered_tensor_sha256 == f32 SHA");
        check(bpsk->file_name == kQBpsk, "sidecar-valid: quantized_file");
        check(bpsk->recovered_tensor_file == kRBpsk, "sidecar-valid: recovered_tensor_file");
        check(bpsk->path == dir + "/" + kQBpsk, "sidecar-valid: full ci16 path");
        check(bpsk->recovered_tensor_path == dir + "/" + kRBpsk,
              "sidecar-valid: full recovered tensor path");
        check(bpsk->d2_rec_scale == 1.0, "sidecar-valid: d2_rec_scale");
        check(bpsk->original_dc_i == 0.0 && bpsk->original_dc_q == 0.0,
              "sidecar-valid: original_dc_i/q");
    }
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_short_row() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_short");
    const Sha4 s = write_binary_fixture(dir);
    // 26 columns only (truncate frozen_deployed23_pred).
    std::string row = manifest_row(1500, 3, 3, "BPSK", hex64(0xAAAAAAAAAAAAAAAAULL),
                                   s.qb, s.rb, kQBpsk, kRBpsk);
    row = row.substr(0, row.find_last_of('\t'));
    write_manifest(dir, row + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: short (26-col) row throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_bad_class_range() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_badrange");
    const Sha4 s = write_binary_fixture(dir);
    // raw24_class = 24 (out of range) with deployed23 = 24 (also out of range).
    write_manifest(dir, manifest_row(1500, 24, 24, "BPSK",
                                     hex64(0xAAAAAAAAAAAAAAAAULL), s.qb, s.rb,
                                     kQBpsk, kRBpsk) + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: out-of-range raw24_class throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_mapping_mismatch() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_badmap");
    const Sha4 s = write_binary_fixture(dir);
    // raw24_class=3 (BPSK) but deployed23=4 (not the AM-SSB merge of 3).
    write_manifest(dir, manifest_row(1500, 3, 4, "BPSK",
                                     hex64(0xAAAAAAAAAAAAAAAAULL), s.qb, s.rb,
                                     kQBpsk, kRBpsk) + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: deployed23 != mapping throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_bad_quant_sha() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_badqsha");
    const Sha4 s = write_binary_fixture(dir);
    // quantized_sha256 is valid 64-hex but NOT the ci16 bytes' SHA.
    write_manifest(dir, manifest_row(1500, 3, 3, "BPSK",
                                     hex64(0xAAAAAAAAAAAAAAAAULL), hex64(7), s.rb,
                                     kQBpsk, kRBpsk) + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: wrong quantized_sha256 throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_bad_rec_sha() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_badrsha");
    const Sha4 s = write_binary_fixture(dir);
    write_manifest(dir, manifest_row(1500, 3, 3, "BPSK",
                                     hex64(0xAAAAAAAAAAAAAAAAULL), s.qb, hex64(8),
                                     kQBpsk, kRBpsk) + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: wrong recovered_tensor_sha256 throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_bad_tx_scale() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_badscale");
    const Sha4 s = write_binary_fixture(dir);
    // tx_scale = 2.0 while tx_rms = 2048 -> expected 1.0 (self-inconsistent).
    write_manifest(dir, manifest_row(1500, 3, 3, "BPSK",
                                     hex64(0xAAAAAAAAAAAAAAAAULL), s.qb, s.rb,
                                     kQBpsk, kRBpsk, /*tx_scale=*/2.0) + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: tx_scale != kAdcFullScale/tx_rms throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_duplicate() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_dup");
    const Sha4 s = write_binary_fixture(dir);
    std::string rows;
    rows += manifest_row(1500, 3, 3, "BPSK", hex64(0xAAAAAAAAAAAAAAAAULL),
                         s.qb, s.rb, kQBpsk, kRBpsk) + "\n";
    rows += manifest_row(1500, 3, 3, "BPSK", hex64(0xAAAAAAAAAAAAAAAAULL),
                         s.qa, s.ra, kQ4ask, kR4ask) + "\n";
    write_manifest(dir, rows);
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: duplicate source_index throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_bad_pred() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_badpred");
    const Sha4 s = write_binary_fixture(dir);
    // frozen_deployed23_pred = 5 (in range but != deployed_class 3).
    write_manifest(dir, manifest_row(1500, 3, 3, "BPSK",
                                     hex64(0xAAAAAAAAAAAAAAAAULL), s.qb, s.rb,
                                     kQBpsk, kRBpsk, 1.0, -1, 5) + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: frozen_deployed23_pred != deployed_class throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_bad_raw_pred() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_badrawpred");
    const Sha4 s = write_binary_fixture(dir);
    // frozen_raw24_pred = 4 (in range but != raw24_class 3).
    write_manifest(dir, manifest_row(1500, 3, 3, "BPSK",
                                     hex64(0xAAAAAAAAAAAAAAAAULL), s.qb, s.rb,
                                     kQBpsk, kRBpsk, 1.0, 4, -1) + "\n");
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: frozen_raw24_pred != raw24_class throws");
    cleanup(dir);
#else
    (void)0;
#endif
}

void test_load_sidecar_reject_missing() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("clean2b_side_missing");
    // No clean2b_smoke_manifest.tsv at all.
    check_throws([&] { clean2b::load_clean2b_sidecar(dir); },
                 "sidecar-reject: missing manifest throws");
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

}  // namespace

int main() {
    std::printf("test_clean2b_smoke_d2\n");

    test_manifest_name_selection();
    test_manifest_path_selection();
    test_load_sidecar_valid();
    test_load_sidecar_reject_short_row();
    test_load_sidecar_reject_bad_class_range();
    test_load_sidecar_reject_mapping_mismatch();
    test_load_sidecar_reject_bad_quant_sha();
    test_load_sidecar_reject_bad_rec_sha();
    test_load_sidecar_reject_bad_tx_scale();
    test_load_sidecar_reject_duplicate();
    test_load_sidecar_reject_bad_pred();
    test_load_sidecar_reject_bad_raw_pred();
    test_load_sidecar_reject_missing();

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
