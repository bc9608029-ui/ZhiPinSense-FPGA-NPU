// test_iq_rf_loopback_24class_bf16_fix10.cpp -- host tests for the SINGLE-SDR
// 24-class BF16 self-loopback A/B runner (fix10class24-singlesdr-ab1, task 39e5).
//
// The full runner needs a real Pluto + the NPU, so it cannot run host-side; but its
// ACCEPTANCE surface is pure and testable without libiio or a board:
//
//   1. the new --phase=iq-rf-loopback-24class-bf16-fix10 dispatch is valid (and the
//      near-misses + old phases behave as before);
//   2. the 24-file D2 frozen manifest covers every raw24 source_class 0..23 exactly
//      once and carries 24 distinct source_index values;
//   3. the frozen raw24 label order / class count / AM-SSB WC(17)-SC(18) split and
//      the BF16 baseline model_sha256 are the frozen contract values;
//   4. the single-SDR transfer (transfer_one_attempt_rf_24class_bf16_fix10, driven
//      through ONE FakePlutoDevice with rf_echo_mode) emits the SAME canonical burst
//      bytes as fix10canonical::buildTxBurstFromFrozen, with tx_dma_payload_sha ==
//      burst_sha (identity data format), a single contiguous capture, loopback==0,
//      TX BW 18 MHz, and TX confirmed off after stop();
//   5. a TX attenuation above the -40 dB safety ceiling throws (fail-closed);
//   6. TX-atten / loopback read-back mismatches throw, and set_sample_rate() writes
//      BOTH the RX and TX phy (the single-SDR runner never calls a set_tx_sample_rate
//      that does not exist -- the Device interface has no such method, a compile-time
//      guarantee this test asserts by only using set_sample_rate + get_{rx,tx}_sample_rate).
//
// iCraft-free and libiio-free.

#include "../board_package/iq_rf_loopback_transfer_24class_bf16_fix10.hpp"
#include "../board_package/iq_fix10_canonical_frame.hpp"
#include "../board_package/gate9_phase.hpp"
#include "../board_package/iq_digital_loopback.hpp"
#include "../board_package/rml24_raw.hpp"
#include "../board_package/rml24_bf16_baseline.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <map>
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

// Frozen contract values the single-SDR A/B must keep byte-identical.
const char* kFrozenModelSha =
    "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42";
const std::uint64_t kCenter = 2400000000ULL;
const double kRxGain = 35.0;      // MUST be 35 (prepare() clobbers RX gain to cfg.rx_gain_db)
const double kAtten = -40.0;
const long long kTxBw = 18000000LL;
const std::size_t kDelayMargin = 8192;

// ---- fixtures ----------------------------------------------------------------

// ONE device driving both TX and RX (single-SDR self-loopback), identity TX/RX data
// format so tx_dma_payload_sha() equals the canonical burst SHA (proving the DMA
// carried the exact bytes), with the external-RF echo model enabled.
struct Fixture {
    pluto::FakePlutoDevice dev;
    Fixture() {
        const pluto::DataFormatInfo ident{16, 16, 0, true, true, false, 1};
        dev.tx_fmt_ = ident;
        dev.rx_fmt_ = ident;
        dev.rf_echo_mode = true;
        dev.open();
    }
};

// Band-limited QPSK payload (32 samples/symbol, component RMS ~= 2048) so the
// canonical burst build's --rf-tx-target-rms=2048 scaling is ~unity and clip-free.
std::vector<std::int16_t> make_payload(std::size_t n_complex, std::uint32_t seed) {
    const std::size_t sps = 32;
    const double amp = 2048.0;
    std::vector<std::int16_t> iq(n_complex * 2);
    std::uint32_t s = seed;
    for (std::size_t m = 0; m < n_complex; m += sps) {
        s = s * 1664525u + 1013904223u;
        const int bi = ((s >> 16) & 1u) ? 1 : -1;
        s = s * 1664525u + 1013904223u;
        const int bq = ((s >> 16) & 1u) ? 1 : -1;
        const std::int16_t I = static_cast<std::int16_t>(std::lround(amp * bi));
        const std::int16_t Q = static_cast<std::int16_t>(std::lround(amp * bq));
        for (std::size_t j = 0; j < sps && m + j < n_complex; ++j) {
            iq[(m + j) * 2 + 0] = I;
            iq[(m + j) * 2 + 1] = Q;
        }
    }
    return iq;
}

void write_binary(const std::string& path, const std::vector<std::int16_t>& iq) {
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
}

std::string sha_of(const std::vector<std::int16_t>& iq) {
    return sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
}

// ---- 1. phase surface --------------------------------------------------------

void test_phase_surface() {
    check(gate9::valid_phase("iq-rf-loopback-24class-bf16-fix10"),
          "phase: valid_phase accepts iq-rf-loopback-24class-bf16-fix10");
    check(!gate9::valid_phase("iq-rf-loopback-24class-bf16-fix10x"),
          "phase: valid_phase rejects trailing-x near-miss");
    check(!gate9::valid_phase("iq-rf-loopback-24class-bf16-fix1"),
          "phase: valid_phase rejects truncated near-miss");
    check(!gate9::valid_phase(""),
          "phase: valid_phase rejects empty");
    check(gate9::valid_phase("iq-rf-loopback-23class-fix9r"),
          "phase: valid_phase still accepts the historical 23-class single-SDR phase");
    check(gate9::valid_phase("iq-pc-tx-board-rx-24class-bf16-fix10"),
          "phase: valid_phase still accepts the dual-SDR 24-class phase");
    check(gate9::valid_phase("iq-clean-iq-24class-bf16-fix10"),
          "phase: valid_phase still accepts the clean 24-class phase");
}

// ---- 2. manifest read + source-index/class coverage --------------------------

void test_manifest_coverage(const std::string& frozen_dir) {
    const std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(frozen_dir, "radioml-d2-2p56m");
    check(frozen.size() == 24, "manifest: 24 frozen D2 files (got " +
          std::to_string(frozen.size()) + ")");

    bool class_seen[24] = {false};
    std::vector<std::int64_t> indexes;
    indexes.reserve(frozen.size());
    for (const auto& fz : frozen) {
        if (fz.source_class >= 0 && fz.source_class < 24) class_seen[fz.source_class] = true;
        indexes.push_back(fz.source_index);
    }
    bool class_ok = true;
    for (int i = 0; i < 24; ++i) if (!class_seen[i]) class_ok = false;
    check(class_ok, "manifest: source_class covers 0..23 exactly");

    bool distinct_ok = true;
    for (std::size_t i = 0; i < indexes.size() && distinct_ok; ++i)
        for (std::size_t j = i + 1; j < indexes.size(); ++j)
            if (indexes[i] == indexes[j]) distinct_ok = false;
    check(distinct_ok, "manifest: 24 distinct source_index values");

    bool holdout_ok = true;
    for (const auto& fz : frozen)
        if (fz.is_calibration) holdout_ok = false;
    check(holdout_ok, "manifest: all 24 files are holdout (no calibration)");
}

// ---- 3. BF16 model / label / baseline identity -------------------------------

void test_model_label_identity() {
    check(rml24::kClassCount == 24, "model: kClassCount == 24");
    check(rml24::kNpuOutputDim == 24, "model: kNpuOutputDim == 24");
    check(rml24::kAmSsbWc == 17 && rml24::kAmSsbSc == 18,
          "model: AM-SSB WC(17) / SC(18) kept independent");
    check(std::string(rml24::kDeploymentMode) == "RAW24_UNMERGED",
          "model: deployment_mode == RAW24_UNMERGED");
    check(rml24::kLabelOrder24[0] == std::string("OOK"), "label: slot 0 == OOK");
    check(rml24::kLabelOrder24[17] == std::string("AM-SSB-WC"), "label: slot 17 == AM-SSB-WC");
    check(rml24::kLabelOrder24[18] == std::string("AM-SSB-SC"), "label: slot 18 == AM-SSB-SC");
    check(rml24::kLabelOrder24[23] == std::string("OQPSK"), "label: slot 23 == OQPSK");
}

void test_baseline_model_sha(const std::string& baseline_path) {
    const std::map<std::uint64_t, rml24bf16::BaselineRow> baseline =
        rml24bf16::load_baseline(baseline_path, rml24::kClassCount);
    check(baseline.size() == 24, "baseline: 24 rows (got " +
          std::to_string(baseline.size()) + ")");
    bool sha_ok = true;
    for (const auto& kv : baseline)
        if (kv.second.model_sha256 != kFrozenModelSha) sha_ok = false;
    check(sha_ok, "baseline: every row model_sha256 == frozen BF16 json SHA");
    // raw24_class of each row must be a distinct 0..23 (the 24-class contract).
    bool row_class[24] = {false};
    for (const auto& kv : baseline)
        if (kv.second.raw24_class >= 0 && kv.second.raw24_class < 24)
            row_class[kv.second.raw24_class] = true;
    bool row_ok = true;
    for (int i = 0; i < 24; ++i) if (!row_class[i]) row_ok = false;
    check(row_ok, "baseline: raw24_class covers 0..23 exactly");
}

// ---- 4. TX burst byte-identity through the single-SDR transfer ---------------

void test_tx_burst_identity(const std::string& path, std::uint64_t cc,
                            const std::string& sha) {
    const iqpctbrx::TxBurstBuild expected =
        fix10canonical::buildTxBurstFromFrozen(path, cc, sha, 2048.0);
    check(!expected.burst.empty(), "burst: canonical burst non-empty");
    check(expected.burst_sha.size() == 64, "burst: burst_sha is 64-hex");

    Fixture fx;
    bool threw = false;
    std::string err;
    iqrfloop_run_24bf16::RfTransferResult24Bf16Fix10 r;
    try {
        r = iqrfloop_run_24bf16::transfer_one_attempt_rf_24class_bf16_fix10(
            fx.dev, expected, 0, "clean_bpsk_4713bc2e.ci16", kCenter, kRxGain, kAtten,
            kTxBw, kDelayMargin, nullptr);
    } catch (const std::exception& e) {
        threw = true;
        err = e.what();
    }
    check(!threw, "burst: transfer succeeds (" + err + ")");
    if (threw) return;
    check(r.burst_sha == expected.burst_sha, "burst: burst_sha read-back == expected burst_sha");
    check(r.tx_dma_payload_ok, "burst: tx_dma_payload_ok (DMA SHA == burst SHA)");
    check(r.capture_ok, "burst: capture_ok (single contiguous refill, no anomaly)");
    check(r.tx_stopped_ok, "burst: tx_stopped_ok (TX off after stop)");
    check(r.loopback_readback == 0, "burst: loopback_readback == 0 (external RF)");
    check(r.tx_bw_readback == kTxBw, "burst: tx_bw_readback == 18 MHz");
    check(std::fabs(r.tx_atten_readback - kAtten) < 1e-9, "burst: tx_atten_readback == -40 dB");
}

// ---- 5. TX attenuation > -40 ceiling is rejected -----------------------------

void test_ceiling_fail_closed(const std::string& path, std::uint64_t cc,
                              const std::string& sha) {
    Fixture fx;
    const iqpctbrx::TxBurstBuild expected =
        fix10canonical::buildTxBurstFromFrozen(path, cc, sha, 2048.0);
    bool threw = false;
    try {
        iqrfloop_run_24bf16::transfer_one_attempt_rf_24class_bf16_fix10(
            fx.dev, expected, 0, "x", kCenter, kRxGain, -30.0, kTxBw, kDelayMargin, nullptr);
    } catch (const std::exception&) { threw = true; }
    check(threw, "ceiling: tx_atten=-30 (> -40 dB) throws");
}

// ---- 6. read-back fail-closed + set_sample_rate writes both RX and TX ---------

void test_atten_readback_fail_closed(const std::string& path, std::uint64_t cc,
                                     const std::string& sha) {
    Fixture fx;
    fx.dev.atten_readback_bias = 0.5;   // set_tx_atten read-back disagrees (prepare step 2)
    const iqpctbrx::TxBurstBuild expected =
        fix10canonical::buildTxBurstFromFrozen(path, cc, sha, 2048.0);
    bool threw = false;
    try {
        iqrfloop_run_24bf16::transfer_one_attempt_rf_24class_bf16_fix10(
            fx.dev, expected, 0, "x", kCenter, kRxGain, kAtten, kTxBw, kDelayMargin, nullptr);
    } catch (const std::exception&) { threw = true; }
    check(threw, "readback: TX atten read-back mismatch throws");
}

void test_loopback_fail_closed(const std::string& path, std::uint64_t cc,
                               const std::string& sha) {
    Fixture fx;
    fx.dev.loopback_readback_override = 1;   // device silently ignores set_loopback(0)
    const iqpctbrx::TxBurstBuild expected =
        fix10canonical::buildTxBurstFromFrozen(path, cc, sha, 2048.0);
    bool threw = false;
    try {
        iqrfloop_run_24bf16::transfer_one_attempt_rf_24class_bf16_fix10(
            fx.dev, expected, 0, "x", kCenter, kRxGain, kAtten, kTxBw, kDelayMargin, nullptr);
    } catch (const std::exception&) { threw = true; }
    check(threw, "readback: loopback read-back != 0 throws");
}

void test_sample_rate_writes_both() {
    Fixture fx;
    fx.dev.set_sample_rate(2560000);
    check(fx.dev.get_rx_sample_rate() == 2560000 && fx.dev.get_tx_sample_rate() == 2560000,
          "samplerate: set_sample_rate writes BOTH rx and tx phy (no set_tx_sample_rate)");
}

}  // namespace

void run_test(const char* name, const std::function<void()>& fn) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main(int argc, char** argv) {
    std::printf("test_iq_rf_loopback_24class_bf16_fix10\n");

    run_test("phase_surface", test_phase_surface);
    run_test("model_label_identity", test_model_label_identity);
    run_test("sample_rate_writes_both", test_sample_rate_writes_both);

    const std::string frozen_dir = (argc > 1 && argv[1][0])
            ? argv[1] : "../clean24_smoke";
    const std::string baseline_path = (argc > 2 && argv[2][0])
            ? argv[2] : "../baselines/clean24_smoke_raw24_bf16_baseline.tsv";
    run_test("manifest_coverage", [&]() { test_manifest_coverage(frozen_dir); });
    run_test("baseline_model_sha", [&]() { test_baseline_model_sha(baseline_path); });

    // Synthetic canonical-burst fixture for the transfer + fail-closed tests.
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = "/tmp/fix10_singlesdr_" + std::to_string(::getpid());
    ::mkdir(dir.c_str(), 0700);
#else
    const std::string dir = ".";
#endif
    const std::uint64_t cc = iqrftrain::kPayloadComplex;
    const std::vector<std::int16_t> payload = make_payload(cc, 0x9e3779b9u);
    const std::string path = dir + "/payload.ci16";
    write_binary(path, payload);
    const std::string sha = sha_of(payload);

    run_test("tx_burst_identity", [&]() { test_tx_burst_identity(path, cc, sha); });
    run_test("ceiling_fail_closed", [&]() { test_ceiling_fail_closed(path, cc, sha); });
    run_test("atten_readback_fail_closed", [&]() { test_atten_readback_fail_closed(path, cc, sha); });
    run_test("loopback_fail_closed", [&]() { test_loopback_fail_closed(path, cc, sha); });

#if defined(__unix__) || defined(__APPLE__)
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#endif

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
