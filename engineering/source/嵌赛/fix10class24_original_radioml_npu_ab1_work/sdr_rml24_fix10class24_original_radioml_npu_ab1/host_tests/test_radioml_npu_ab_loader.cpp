// test_radioml_npu_ab_loader.cpp -- host tests for the 480-frame original-RadioML
// NPU-A/B input loader (board_package/radioml_npu_ab_loader.hpp) and the new
// gate9 phase:
//   * the 8-column manifest parse + fail-closed byte/SHA/size/label/index checks;
//   * load_tensor round-trip + per-frame SHA re-verify + NaN/Inf detection;
//   * the new phase "radioml-original-npu-ab-24class-bf16-fix10" is valid, near
//     strings are rejected, and every old phase still validates (regression).
//
// iCraft-free and libiio-free: exercises only the loader header + sha256.hpp +
// chain_common.hpp constants (no NPU, no resampler, no device).
//
// Build/run: see host_tests/build_host_tests.sh / run_tests.sh.

#include "../board_package/radioml_npu_ab_loader.hpp"
#include "../board_package/rml24_raw.hpp"
#include "../board_package/gate9_phase.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <string>
#include <unistd.h>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

template <typename F>
void check_throws(F fn, const char* what) {
    bool threw = false;
    try { fn(); } catch (...) { threw = true; }
    if (threw) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (did not throw)\n", what); }
}

std::string make_fixture_dir() {
    char tmpl[] = "/tmp/rmlnpuab_XXXXXX";
    char* d = mkdtemp(tmpl);
    if (!d) { std::printf("  mkdtemp failed\n"); std::exit(1); }
    return std::string(d);
}

std::string sha_of_floats(const std::vector<float>& floats) {
    return sdr::Sha256::hex(floats.data(), floats.size() * sizeof(float));
}

void write_bin(const std::string& path, const std::vector<float>& floats) {
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(floats.data()),
            static_cast<std::streamsize>(floats.size() * sizeof(float)));
}

// Write a fully-valid 480-frame input package and return the dir.  Each frame is
// deterministic + unique (so every input_sha256 is unique).
std::string make_valid_480() {
    const std::string dir = make_fixture_dir();
    std::ofstream tsv(dir + "/manifest.tsv");
    tsv << rmlnpuab::manifest_header_line() << "\n";
    for (int i = 0; i < rmlnpuab::kFrameCount; ++i) {
        std::vector<float> t(rmlnpuab::kInputFloats);
        for (std::size_t k = 0; k < rmlnpuab::kInputFloats; ++k)
            t[k] = static_cast<float>(k) * 0.125f + static_cast<float>(i);
        const std::string sha = sha_of_floats(t);
        const std::string fname = std::to_string(i + 1) + ".bin";
        write_bin(dir + "/" + fname, t);
        const int cls = i % rmlnpuab::kClassCount;
        const int snr = (i % 4) * 10;                       // 0/10/20/30
        const int host_pred = (i * 7) % rmlnpuab::kClassCount;
        tsv << (i + 1) << "\t" << (1000000 + i) << "\t" << cls << "\t"
            << rml24::kLabelOrder24[cls] << "\t" << snr << "\t" << fname << "\t"
            << sha << "\t" << host_pred << "\n";
    }
    tsv.close();
    return dir;
}

void remove_480(const std::string& dir) {
    std::remove((dir + "/manifest.tsv").c_str());
    for (int i = 0; i < rmlnpuab::kFrameCount; ++i)
        std::remove((dir + "/" + std::to_string(i + 1) + ".bin").c_str());
    ::rmdir(dir.c_str());
}

// --- manifest header / split ------------------------------------------------

void test_header_and_split() {
    check(std::string(rmlnpuab::manifest_header_line()) ==
              "selection_id\thdf5_row_index\traw24_class\tmodulation\tsnr_db\t"
              "input_file\tinput_sha256\thost_pred",
          "manifest_header_line: exact 8-column header");
    const auto f = rmlnpuab::split_tab("1\t1000\t3\tBPSK\t0\t1.bin\t<sha>\t3");
    check(f.size() == 8, "split_tab: 8 fields");
    check(f[0] == "1" && f[3] == "BPSK" && f[6] == "<sha>" && f[7] == "3",
          "split_tab: field values");
}

// --- manifest OK ------------------------------------------------------------

void test_manifest_ok() {
    const std::string dir = make_valid_480();
    const auto frames = rmlnpuab::load_manifest(dir);
    check(static_cast<int>(frames.size()) == rmlnpuab::kFrameCount,
          "manifest OK: 480 frames loaded");
    check(frames[0].selection_id == 1 &&
          frames[0].hdf5_row_index == 1000000 &&
          frames[0].raw24_class == 0 &&
          frames[0].modulation == "OOK" &&
          frames[0].snr_db == 0 &&
          frames[0].input_file == "1.bin" &&
          frames[0].host_pred == 0,
          "manifest OK: frame 0 fields");
    check(frames[479].selection_id == 480 &&
          frames[479].raw24_class == (479 % 24) &&
          frames[479].snr_db == (479 % 4) * 10,
          "manifest OK: frame 479 fields");
    remove_480(dir);
}

// --- manifest fail-closed ---------------------------------------------------

void test_manifest_fail_closed() {
    // missing manifest
    {
        const std::string dir = make_fixture_dir();
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: missing manifest.tsv throws");
        ::rmdir(dir.c_str());
    }
    // header mismatch
    {
        const std::string dir = make_valid_480();
        // Rewrite the header (and drop all rows): the header check throws first.
        {
            std::ofstream tsv(dir + "/manifest.tsv");
            tsv << "wrong\theader\tline\n";
        }
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: header mismatch throws");
        remove_480(dir);
    }
    // column count != 8
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t0\tOOK\t0\t1.bin\t<sha>\n";   // 7 cols
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: 7-column row throws");
        remove_480(dir);
    }
    // row count != 480 (one row dropped -> 479)
    {
        const std::string dir = make_valid_480();
        // Rebuild the manifest with 479 rows.
        {
            std::ofstream tsv(dir + "/manifest.tsv");
            tsv << rmlnpuab::manifest_header_line() << "\n";
            for (int i = 0; i < rmlnpuab::kFrameCount - 1; ++i) {
                std::vector<float> t(rmlnpuab::kInputFloats, 1.0f);
                t[0] = static_cast<float>(i);
                const std::string sha = sha_of_floats(t);
                const std::string fname = std::to_string(i + 1) + ".bin";
                write_bin(dir + "/" + fname, t);
                tsv << (i + 1) << "\t" << (1000000 + i) << "\t" << (i % 24) << "\t"
                    << rml24::kLabelOrder24[i % 24] << "\t" << (i % 4) * 10 << "\t"
                    << fname << "\t" << sha << "\t" << (i * 7) % 24 << "\n";
            }
        }
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: 479 rows throws");
        remove_480(dir);
    }
    // non-contiguous selection_id (skip 2)
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t0\tOOK\t0\t1.bin\t" << std::string(64, '0') << "\t0\n";
        tsv << "3\t1000001\t1\t4ASK\t10\t2.bin\t" << std::string(64, '1') << "\t1\n";
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: non-contiguous selection_id throws");
        remove_480(dir);
    }
    // duplicate hdf5_row_index
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t0\tOOK\t0\t1.bin\t" << std::string(64, '0') << "\t0\n";
        tsv << "2\t1000000\t1\t4ASK\t10\t2.bin\t" << std::string(64, '1') << "\t1\n";
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: duplicate hdf5_row_index throws");
        remove_480(dir);
    }
    // duplicate input_file
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t0\tOOK\t0\t1.bin\t" << std::string(64, '0') << "\t0\n";
        tsv << "2\t1000001\t1\t4ASK\t10\t1.bin\t" << std::string(64, '1') << "\t1\n";
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: duplicate input_file throws");
        remove_480(dir);
    }
    // raw24_class out of range
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t24\tOOK\t0\t1.bin\t" << std::string(64, '0') << "\t0\n";
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: raw24_class=24 throws");
        remove_480(dir);
    }
    // host_pred out of range
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t0\tOOK\t0\t1.bin\t" << std::string(64, '0') << "\t24\n";
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: host_pred=24 throws");
        remove_480(dir);
    }
    // snr_db not in {0,10,20,30}
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t0\tOOK\t5\t1.bin\t" << std::string(64, '0') << "\t0\n";
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: snr_db=5 throws");
        remove_480(dir);
    }
    // unsafe input_file
    {
        const std::string dir = make_valid_480();
        std::ofstream tsv(dir + "/manifest.tsv");
        tsv << rmlnpuab::manifest_header_line() << "\n";
        tsv << "1\t1000000\t0\tOOK\t0\t../secret.bin\t" << std::string(64, '0') << "\t0\n";
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: unsafe input_file throws");
        remove_480(dir);
    }
    // SHA mismatch on a real frame
    {
        const std::string dir = make_valid_480();
        // Tamper frame 1's bin bytes (keep the manifest SHA).
        std::vector<float> t(rmlnpuab::kInputFloats, 0.0f);
        t[0] = 42.0f;
        write_bin(dir + "/1.bin", t);
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: SHA mismatch throws");
        remove_480(dir);
    }
    // short file
    {
        const std::string dir = make_valid_480();
        {
            std::ofstream f(dir + "/1.bin", std::ios::binary);
            f.write("short", 5);
        }
        check_throws([&]() { (void)rmlnpuab::load_manifest(dir); },
                     "manifest: short bin throws");
        remove_480(dir);
    }
}

// --- load_tensor ------------------------------------------------------------

void test_load_tensor_ok() {
    const std::string dir = make_fixture_dir();
    std::vector<float> t(rmlnpuab::kInputFloats);
    for (std::size_t k = 0; k < rmlnpuab::kInputFloats; ++k)
        t[k] = static_cast<float>(k) * 0.25f - 100.0f;
    write_bin(dir + "/7.bin", t);

    rmlnpuab::DirectFrame fr;
    fr.selection_id = 7;
    fr.hdf5_row_index = 12345;
    fr.raw24_class = 3;
    fr.modulation = "BPSK";
    fr.snr_db = 20;
    fr.input_file = "7.bin";
    fr.input_sha256 = sha_of_floats(t);
    fr.host_pred = 3;

    std::vector<float> got(rmlnpuab::kInputFloats);
    rmlnpuab::load_tensor(dir, fr, got.data());
    check(got == t, "load_tensor: round-trips exact bytes");

    std::remove((dir + "/7.bin").c_str());
    ::rmdir(dir.c_str());
}

void test_load_tensor_fail_closed() {
    // NaN detection
    {
        const std::string dir = make_fixture_dir();
        std::vector<float> t(rmlnpuab::kInputFloats, 1.0f);
        t[0] = std::numeric_limits<float>::quiet_NaN();
        write_bin(dir + "/nan.bin", t);
        rmlnpuab::DirectFrame fr;
        fr.input_file = "nan.bin";
        fr.input_sha256 = sha_of_floats(t);
        std::vector<float> out(rmlnpuab::kInputFloats);
        check_throws([&]() { rmlnpuab::load_tensor(dir, fr, out.data()); },
                     "load_tensor: NaN throws");
        std::remove((dir + "/nan.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // Inf detection
    {
        const std::string dir = make_fixture_dir();
        std::vector<float> t(rmlnpuab::kInputFloats, -1.0f);
        t[1024] = std::numeric_limits<float>::infinity();
        write_bin(dir + "/inf.bin", t);
        rmlnpuab::DirectFrame fr;
        fr.input_file = "inf.bin";
        fr.input_sha256 = sha_of_floats(t);
        std::vector<float> out(rmlnpuab::kInputFloats);
        check_throws([&]() { rmlnpuab::load_tensor(dir, fr, out.data()); },
                     "load_tensor: Inf throws");
        std::remove((dir + "/inf.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // SHA mismatch on read
    {
        const std::string dir = make_fixture_dir();
        std::vector<float> t(rmlnpuab::kInputFloats, 0.5f);
        write_bin(dir + "/x.bin", t);
        rmlnpuab::DirectFrame fr;
        fr.input_file = "x.bin";
        fr.input_sha256 = std::string(64, '0');
        std::vector<float> out(rmlnpuab::kInputFloats);
        check_throws([&]() { rmlnpuab::load_tensor(dir, fr, out.data()); },
                     "load_tensor: SHA mismatch throws");
        std::remove((dir + "/x.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // short file
    {
        const std::string dir = make_fixture_dir();
        {
            std::ofstream f(dir + "/short.bin", std::ios::binary);
            f.write("abc", 3);
        }
        rmlnpuab::DirectFrame fr;
        fr.input_file = "short.bin";
        fr.input_sha256 = std::string(64, '0');
        std::vector<float> out(rmlnpuab::kInputFloats);
        check_throws([&]() { rmlnpuab::load_tensor(dir, fr, out.data()); },
                     "load_tensor: short read throws");
        std::remove((dir + "/short.bin").c_str());
        ::rmdir(dir.c_str());
    }
}

// --- phase surface ----------------------------------------------------------

void test_phase_valid() {
    check(gate9::valid_phase("radioml-original-npu-ab-24class-bf16-fix10"),
          "phase: new phase valid");
    check(!gate9::valid_phase("radioml-original-npu-ab"),
          "phase: truncated name rejected");
    check(!gate9::valid_phase("radioml-original-npu-ab-24class-bf16-fix10x"),
          "phase: trailing-junk name rejected");
    check(!gate9::valid_phase("RADIOML-ORIGINAL-NPU-AB-24CLASS-BF16-FIX10"),
          "phase: case-mismatch rejected");
    // old-phase regression: every existing phase still validates.
    const char* old_phases[] = {
        "offline", "digital", "rf", "ambient", "live-rx", "synthetic-iq",
        "iq-digital-loopback", "iq-digital-loopback-sweep", "iq-rf-loopback",
        "iq-rf-loopback-level-sweep", "iq-rf-loopback-ab",
        "iq-rf-loopback-23class", "iq-rf-loopback-23class-fix9r",
        "iq-dual-sdr-23class-fix10", "iq-clean-iq-23class-fix10",
        "iq-pc-tx-board-rx-23class-fix10", "iq-clean-iq-24class-bf16-fix10",
        "iq-pc-tx-board-rx-24class-bf16-fix10",
        "iq-rf-loopback-24class-bf16-fix10",
        "iq-rf-loopback-24class-bf16-scalarwl",
    };
    bool all_ok = true;
    for (const char* p : old_phases)
        if (!gate9::valid_phase(p)) { all_ok = false; break; }
    check(all_ok, "phase: all 20 old phases still valid");
}

}  // namespace

int main() {
    std::printf("test_radioml_npu_ab_loader\n");
    test_header_and_split();
    test_manifest_ok();
    test_manifest_fail_closed();
    test_load_tensor_ok();
    test_load_tensor_fail_closed();
    test_phase_valid();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
