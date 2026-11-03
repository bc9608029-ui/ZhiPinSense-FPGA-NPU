// test_fix10class24_replay_canonical.cpp -- host tests for the Batch 2 canonical
// reference replay mode (--canonical-reference).  Covers the 8 required checks:
//   (1) canonical component length + SHA
//   (2) missing / truncated / tampered asset rejection
//   (3) default old mode unchanged  (proven by the UNMODIFIED existing
//       test_fix10class24_replay.cpp, which still passes)
//   (4) canonical mode field-by-field reproduction of the real BPSK dump
//   (5) x86 two consecutive runs identical
//   (6) canonical vs x86 dynamic reference genuinely differ + first difference
//   (7) red-line headers untouched  (proven by the packager's byte-identical audit)
//   (8) host_tests full suite no regression  (build_host_tests.sh + run_tests.sh)
// This file exercises (1)(2)(4)(5)(6) in-process; (3)(7)(8) are proven by the
// unmodified existing test + the packager + the full suite run.
//
// (4)(5) require the real board BPSK dump; pass its directory as argv[1] (or rely on
// the default relative path).  When the dump is absent these are SKIPPED, not failed,
// because the dump is a user-supplied board capture that is not packaged.

#include "../host_tools/replay_fix10class24_failed_rx.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// ---- little-endian int16 bytes of the canonical payload_training component ---------
std::string canonical_pt_bytes() {
    std::string s;
    s.reserve(4096);
    for (std::int16_t v : fix10canonical::kCanonicalPayloadTraining) {
        const std::uint16_t u = static_cast<std::uint16_t>(v);
        s.push_back(static_cast<char>(u & 0xffu));
        s.push_back(static_cast<char>((u >> 8) & 0xffu));
    }
    return s;
}

void write_bytes(const std::string& path, const std::string& data) {
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    f.write(data.data(), static_cast<std::streamsize>(data.size()));
    f.close();
}

bool file_exists(const std::string& p) {
    std::ifstream f(p, std::ios::binary);
    return static_cast<bool>(f);
}

// (1) canonical component length + SHA.
void test_length_and_sha() {
    check(fix10canonical::kCanonicalPayloadTraining.size() == 2048,
          "payload_training int16 count == 2048 (complex_count 1024)");
    check(fix10canonical::kCanonicalPayloadTraining.size() * sizeof(std::int16_t) == 4096,
          "payload_training byte_count == 4096");
    const std::string pt =
        sdr::Sha256::hex(fix10canonical::kCanonicalPayloadTraining.data(), 4096);
    check(pt == fix10canonical::kCanonicalPayloadTrainingSha, "payload_training SHA == frozen");
    check(pt == "f06e9b3de0f51594d8db0501a03918350072d4bc0e5a56f955053bafa35663ca",
          "payload_training SHA literal f06e9b3d...");
    check(sdr::Sha256::hex(fix10canonical::kCanonicalPreamble.data(), 4096) ==
              fix10canonical::kCanonicalPreambleSha,
          "preamble SHA == frozen");
    check(sdr::Sha256::hex(fix10canonical::kCanonicalTail.data(), 4096) ==
              fix10canonical::kCanonicalTailSha,
          "tail SHA == frozen");
    bool threw = false;
    try { replay24::verify_canonical_components(); } catch (...) { threw = true; }
    check(!threw, "verify_canonical_components() does not throw");
}

// (2) missing / truncated / tampered asset rejection.
void test_asset_rejection() {
    const std::string base = "/tmp/fix10class24_canonical_test";
    bool threw = false;
    try { replay24::verify_canonical_file(base + "_missing.ci16"); }
    catch (...) { threw = true; }
    check(threw, "missing canonical file rejected");

    const std::string good = canonical_pt_bytes();
    check(good.size() == 4096, "canonical_pt_bytes() == 4096");

    write_bytes(base + "_trunc.ci16", good.substr(0, 1000));
    threw = false;
    try { replay24::verify_canonical_file(base + "_trunc.ci16"); }
    catch (...) { threw = true; }
    check(threw, "truncated canonical file rejected (byte_count != 4096)");

    std::string tampered = good;
    tampered[0] = static_cast<char>(tampered[0] ^ 0x01);
    write_bytes(base + "_tamper.ci16", tampered);
    threw = false;
    try { replay24::verify_canonical_file(base + "_tamper.ci16"); }
    catch (...) { threw = true; }
    check(threw, "tampered canonical file rejected (SHA mismatch)");

    write_bytes(base + "_good.ci16", good);
    threw = false;
    try { replay24::verify_canonical_file(base + "_good.ci16"); }
    catch (const std::exception& e) { threw = true; std::printf("  unexpected: %s\n", e.what()); }
    check(!threw, "correct canonical file accepted");
}

// (6) canonical vs x86 dynamic reference genuinely differ + first difference.
void test_reference_diff() {
    const replay24::ReferenceDiff d = replay24::compare_canonical_vs_runtime();
    check(d.preamble_identical, "runtime preamble == canonical preamble (ZC deterministic)");
    check(d.tail_identical, "runtime tail == canonical tail (ZC deterministic)");
    check(!d.payload_training_identical,
          "runtime payload_training != canonical (the D1 cross-arch blind spot)");
    check(d.first_pt_diff_index < 2048, "first payload_training diff index is valid");
    std::printf("  payload_training FIRST_DIFF int16_index=%zu runtime=%d canonical=%d delta=%d\n",
                d.first_pt_diff_index, static_cast<int>(d.runtime_value),
                static_cast<int>(d.canonical_value),
                static_cast<int>(d.runtime_value) - static_cast<int>(d.canonical_value));
}

// (4) + (5) require the real board BPSK dump.  run_real() skips when it is absent.
void run_real(const std::string& dir) {
    if (dir.empty() || !file_exists(dir + "/raw_rx_ci16le.bin") ||
        !file_exists(dir + "/recovery_diagnostics.json")) {
        std::printf("  SKIP real-dump reproduction (dump not present at '%s')\n", dir.c_str());
        return;
    }

    // (4) field-by-field reproduction of the real BPSK dump.
    const replay24::CanonicalReplayResult r = replay24::replay_canonical_from_dir(dir);
    check(r.timing_ok && r.timing_offset == 36074,
          "canonical: timing_offset == 36074 (exact)");
    check(r.coarse_ok && std::fabs(r.coarse_cfo_hz - (-118.316)) < 2e-2,
          "canonical: coarse_cfo_hz ~= -118.316 (tol 2e-2)");
    check(r.fine_ok && std::fabs(r.fine_cfo_hz - (-6.27395)) < 2e-2,
          "canonical: fine_cfo_hz ~= -6.27395 (tol 2e-2)");
    check(r.corr_ok && std::fabs(r.payload_training_corr - 0.993317) < 1e-5,
          "canonical: payload_training_corr ~= 0.993317 (tol 1e-5)");
    check(r.resid_ok && std::fabs(r.payload_training_residual - 0.116199) < 1e-5,
          "canonical: payload_training_residual ~= 0.116199 (tol 1e-5)");
    check(r.payload_training_residual > 0.10,
          "canonical: residual > 0.10 (reproduces the BOARD FAILURE, not a pass)");
    std::printf("  canonical reproduced: timing=%zu coarse=%.9f fine=%.9f corr=%.9f residual=%.9f\n",
                r.timing_offset, r.coarse_cfo_hz, r.fine_cfo_hz,
                r.payload_training_corr, r.payload_training_residual);

    // (5) x86 two consecutive runs identical (deterministic).
    const replay24::CanonicalReplayResult r2 = replay24::replay_canonical_from_dir(dir);
    check(r2.timing_offset == r.timing_offset, "two-run: timing identical");
    check(r2.coarse_cfo_hz == r.coarse_cfo_hz, "two-run: coarse CFO identical");
    check(r2.fine_cfo_hz == r.fine_cfo_hz, "two-run: fine CFO identical");
    check(r2.payload_training_corr == r.payload_training_corr, "two-run: corr identical");
    check(r2.payload_training_residual == r.payload_training_residual,
          "two-run: residual identical");
}

}  // namespace

int main(int argc, char** argv) {
    std::printf("test_fix10class24_replay_canonical\n");
    test_length_and_sha();
    test_asset_rejection();
    test_reference_diff();
    const std::string dump = (argc > 1) ? std::string(argv[1])
                                        : std::string("../../board_capture/extracted/failed_rx/1500");
    run_real(dump);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
