// test_iq_digital_loopback_sequence.cpp -- host tests for the Stage H-E / Route E
// fix2 TRANSFER path (board_package/iq_digital_loopback_transfer.hpp), shared
// verbatim by the board runner and this test.
//
//   * single-file x4, four-file manifest order, and four-file reverse order all
//     produce per-file non-zero RX (no "first two have data, last two zero" state
//     leakage) and a clean digital-loopback fidelity verdict;
//   * TX content verification (SHA + non-zero + RMS + first/last) runs per file;
//   * the stale-RX flush is PROVEN: with the fake's stale-leak model armed, a
//     missing recreate_rx_buffer would return all-zero RX, yet every file here is
//     non-zero -- and the buffer lifecycle deltas show the RX buffer destroyed and
//     recreated per file;
//   * a negative control at the FakePlutoDevice level: without recreate, read_rx
//     returns all-zero (the leakage signature), and recreate cures it.
//
// iCraft-free and libiio-free.  Links ../sdr_adapter/pluto_tx.cpp (the real
// PlutoTx safety state machine) so the test exercises the exact TX start/stop path
// the board runs, against the scriptable FakePlutoDevice.
//
// Build/run: see host_tests/build_host_tests.sh (links pluto_tx.cpp).

#include "../board_package/iq_digital_loopback_transfer.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
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

template <typename F>
void check_throws(F fn, const char* what) {
    bool threw = false;
    try { fn(); } catch (...) { threw = true; }
    if (threw) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (did not throw)\n", what); }
}

// A deterministic, non-trivial, non-clipping interleaved int16 waveform, distinct
// per `seed` so different frozen files carry different content.
std::vector<std::int16_t> make_file_tx(std::size_t N, int seed) {
    std::vector<std::int16_t> iq(N * 2);
    for (std::size_t k = 0; k < N; ++k) {
        const double f1 = 13.0 + static_cast<double>(seed % 7);
        const double f2 = 7.0 + static_cast<double>(seed % 5);
        const double I = 9000.0 * std::sin(2.0 * 3.14159265358979323846 * f1 *
                                           static_cast<double>(k) / static_cast<double>(N));
        const double Q = 9000.0 * std::cos(2.0 * 3.14159265358979323846 * f2 *
                                           static_cast<double>(k) / static_cast<double>(N));
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::lround(I));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::lround(Q));
    }
    return iq;
}

#if defined(__unix__) || defined(__APPLE__)
struct FrozenFile {
    std::string path;
    std::string sha;
    std::uint64_t complex;
};

std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

FrozenFile write_frozen(const std::string& dir, const std::string& name,
                        std::size_t N, int seed) {
    const std::vector<std::int16_t> iq = make_file_tx(N, seed);
    const std::string path = dir + "/" + name;
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
    FrozenFile ff;
    ff.path = path;
    ff.sha = sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
    ff.complex = N;
    return ff;
}
#endif

// Run one transfer against the fake, and assert every fix2 invariant for one file.
// `first` is true only for the very first transfer of a fresh device: the RX
// buffer is created LAZILY (matching the real backend), so on that first file
// there is no prior buffer to destroy and the destroy-delta assertion is skipped.
void assert_one_transfer(const char* label, const iqdloop_run::TransferResult& tr,
                         const std::string& expect_sha, bool first) {
    // req 2: the LOADED TX bytes hash to the frozen SHA and are non-zero.
    check(tr.tx_verify.sha256 == expect_sha,
          std::string(label) + ": tx_verify SHA == frozen SHA");
    check(tr.tx_verify.nonzero > 0, std::string(label) + ": tx_verify non-zero");
    check(tr.tx_verify.rms > 0.0, std::string(label) + ": tx_verify rms > 0");

    // req 3: two refills recorded (stale-flush discard + the contiguous capture).
    check(tr.refills.size() == 2, std::string(label) + ": discard + capture refills");
    if (tr.refills.size() == 2) {
        check(tr.refills[0].kind == "discard", std::string(label) + ": first refill is discard");
        check(tr.refills[1].kind == "capture", std::string(label) + ": second refill is capture");
    }

    // req 1: one fresh TX buffer created and destroyed per file, and the RX buffer
    // destroyed + recreated (the stale flush) per file.  From the second file on,
    // a stale RX buffer from the previous file MUST be dropped (destroy delta >= 1).
    check(tr.tx_create_delta == 1, std::string(label) + ": fresh TX buffer created");
    check(tr.tx_destroy_delta == 1, std::string(label) + ": TX buffer destroyed");
    check(tr.rx_create_delta >= 1, std::string(label) + ": RX buffer recreated (flush)");
    if (!first) {
        check(tr.rx_destroy_delta >= 1, std::string(label) + ": RX buffer destroyed (flush)");
    }

    // The core fix2 symptom check: with the stale-leak model armed, a missing
    // recreate would have returned all-zero RX.  Non-zero RX + a clean fidelity
    // verdict proves the flush ran and the data flowed.
    check(tr.capture_ok, std::string(label) + ": capture_ok");
    bool rx_any_nonzero = false;
    for (std::int16_t s : tr.rx)
        if (s != 0) { rx_any_nonzero = true; break; }
    check(rx_any_nonzero, std::string(label) + ": RX non-zero (no state leakage)");
}

#if defined(__unix__) || defined(__APPLE__)
void run_sequence_tests() {
    const std::size_t N = 2048;         // frozen complex count per file
    const std::size_t delay_margin = 256;
    const std::string dir = make_tmp_dir("rml23_iqdloop_seq");

    const FrozenFile f0 = write_frozen(dir, "file0.ci16", N, 0);
    const FrozenFile f1 = write_frozen(dir, "file1.ci16", N, 1);
    const FrozenFile f2 = write_frozen(dir, "file2.ci16", N, 2);
    const FrozenFile f3 = write_frozen(dir, "file3.ci16", N, 3);

    pluto::FakePlutoDevice dev;
    dev.open();                             // mirror the board's open-before-use
    dev.echo_tx_on_rx = true;              // model the AD9361 digital loopback
    dev.stale_rx_without_recreate = true;  // arm the stale-leak failure model

    const std::uint64_t center = 2400000000ULL;
    const double gain = 10.0;
    const double atten = -40.0;            // the fixed safety ceiling (req 8)
    const std::uint64_t cap = 0;           // full frozen file
    bool first = true;                     // very first transfer of this device

    // --- scenario A: single file repeated 4x (req 7) ---
    {
        std::printf("  sequence: single file x4\n");
        for (int i = 0; i < 4; ++i) {
            const iqdloop_run::TransferResult tr = iqdloop_run::transfer_one_file(
                dev, f0.path, f0.complex, f0.sha, center, gain, atten,
                delay_margin, cap);
            const std::string label = "repeat4x[" + std::to_string(i) + "]";
            assert_one_transfer(label.c_str(), tr, f0.sha, first);
            first = false;
            const auto m = iqdloop::align_and_measure_int16(tr.tx, tr.rx,
                                                            iqdloop::kFrozenFsIn,
                                                            delay_margin);
            check(std::string(iqdloop::fidelity_verdict(m)) ==
                      "DIGITAL_LOOPBACK_PRESERVES_IQ",
                  (label + ": fidelity PRESERVES_IQ").c_str());
        }
    }

    // --- scenario B: four files in manifest order (req 7) ---
    {
        std::printf("  sequence: four-file order\n");
        const FrozenFile* fs[4] = {&f0, &f1, &f2, &f3};
        for (int i = 0; i < 4; ++i) {
            const iqdloop_run::TransferResult tr = iqdloop_run::transfer_one_file(
                dev, fs[i]->path, fs[i]->complex, fs[i]->sha, center, gain, atten,
                delay_margin, cap);
            const std::string label = "order[" + std::to_string(i) + "]";
            assert_one_transfer(label.c_str(), tr, fs[i]->sha, first);
            first = false;
            const auto m = iqdloop::align_and_measure_int16(tr.tx, tr.rx,
                                                            iqdloop::kFrozenFsIn,
                                                            delay_margin);
            check(std::string(iqdloop::fidelity_verdict(m)) ==
                      "DIGITAL_LOOPBACK_PRESERVES_IQ",
                  (label + ": fidelity PRESERVES_IQ").c_str());
        }
    }

    // --- scenario C: four files in reverse order (req 7) ---
    {
        std::printf("  sequence: four-file reverse\n");
        const FrozenFile* fs[4] = {&f3, &f2, &f1, &f0};
        for (int i = 0; i < 4; ++i) {
            const iqdloop_run::TransferResult tr = iqdloop_run::transfer_one_file(
                dev, fs[i]->path, fs[i]->complex, fs[i]->sha, center, gain, atten,
                delay_margin, cap);
            const std::string label = "reverse[" + std::to_string(i) + "]";
            assert_one_transfer(label.c_str(), tr, fs[i]->sha, first);
            first = false;
            const auto m = iqdloop::align_and_measure_int16(tr.tx, tr.rx,
                                                            iqdloop::kFrozenFsIn,
                                                            delay_margin);
            check(std::string(iqdloop::fidelity_verdict(m)) ==
                      "DIGITAL_LOOPBACK_PRESERVES_IQ",
                  (label + ": fidelity PRESERVES_IQ").c_str());
        }
    }

    // --- negative control: the stale signature, and the flush that cures it ---
    {
        std::printf("  sequence: stale-leak negative control\n");
        const std::vector<std::int16_t> w = make_file_tx(N, 9);
        dev.tx_start_cyclic(w);   // rx_recreated_since_tx_ -> false
        // Without recreate_rx_buffer, the armed stale model returns all-zero.
        const iio::RawChunk c0 = dev.read_rx(256, 1000);
        bool all_zero = true;
        for (std::size_t k = 0; k < c0.samples_available; ++k)
            if (c0.samples[k] != 0) { all_zero = false; break; }
        check(all_zero && c0.samples_available > 0,
              "negative: read_rx without recreate returns all-zero (leak signature)");
        // recreate_rx_buffer cures it: the next read echoes the TX waveform.
        dev.recreate_rx_buffer();
        const iio::RawChunk c1 = dev.read_rx(256, 1000);
        bool any_nonzero = false;
        for (std::size_t k = 0; k < c1.samples_available; ++k)
            if (c1.samples[k] != 0) { any_nonzero = true; break; }
        check(any_nonzero, "negative: recreate_rx_buffer cures the stale-leak zeros");
    }

    ::unlink((dir + "/file0.ci16").c_str());
    ::unlink((dir + "/file1.ci16").c_str());
    ::unlink((dir + "/file2.ci16").c_str());
    ::unlink((dir + "/file3.ci16").c_str());
    ::rmdir(dir.c_str());
}
#endif

void run_sha_mismatch_fail_closed() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_iqdloop_seq_neg");
    const FrozenFile f0 = write_frozen(dir, "file0.ci16", 2048, 0);
    pluto::FakePlutoDevice dev;
    dev.echo_tx_on_rx = true;
    // A wrong SHA must throw (fail-closed), not silently proceed with stale bytes.
    check_throws([&]() {
        (void)iqdloop_run::transfer_one_file(dev, f0.path, f0.complex,
                                             std::string(64, '0'), 2400000000ULL,
                                             10.0, -40.0, 256, 0);
    }, "transfer_one_file: SHA mismatch throws (fail-closed)");
    ::unlink((dir + "/file0.ci16").c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

}  // namespace

int main() {
    std::printf("test_iq_digital_loopback_sequence\n");
#if defined(__unix__) || defined(__APPLE__)
    run_sequence_tests();
    run_sha_mismatch_fail_closed();
#else
    std::printf("  (sequence tests require POSIX; skipping on this host)\n");
#endif
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
