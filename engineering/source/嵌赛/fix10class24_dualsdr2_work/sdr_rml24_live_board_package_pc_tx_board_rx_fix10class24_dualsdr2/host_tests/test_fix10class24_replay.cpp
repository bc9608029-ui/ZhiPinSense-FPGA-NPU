// test_fix10class24_replay.cpp -- host tests for the Phase C offline replayer core
// (host_tools/replay_fix10class24_failed_rx.hpp).  Proves the dump -> replay ->
// cross-check round trip reproduces the board recovery bit-for-bit on the host (the
// "default replay matches board log" property), plus the self-test and the candidate
// curve functions run without throwing.  iCraft-free / libiio-free / NPU-free.

#include "../host_tools/replay_fix10class24_failed_rx.hpp"
#include "../board_package/iq_fix10class24_failed_rx_dump.hpp"

#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;
const std::string kBase = "/tmp/fix10class24_replay_test";

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// A deterministic clean single-burst capture + its production recovery.
struct Synthetic {
    std::vector<std::int16_t> payload;
    std::vector<std::int16_t> burst;
    std::vector<std::complex<double>> rx;
    iqrfrec::EstimateConfig cfg;
    iqdual23fix10::CoarseCfoRecovery ccr;
};

Synthetic make_synthetic() {
    Synthetic s;
    s.payload.assign(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 43) / 43.0;
        s.payload[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1150.0 * std::cos(ph)));
        s.payload[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1150.0 * std::sin(ph)));
    }
    s.burst = iqrftrain::build_burst(s.payload);
    s.rx = iqrftrain::deinterleave(s.burst);
    s.cfg = replay24::config(2048.0);
    s.ccr = iqdual23fix10::recover_payload_with_coarse_cfo(s.rx, s.cfg, 1.0);
    return s;
}

void test_self_test() { check(replay24::self_test() == 0, "replayer self_test == 0"); }

void test_replay_crosscheck(const std::string& base) {
    const Synthetic s = make_synthetic();
    check(s.ccr.rec.valid, "synthetic recovery valid (roundtrip precondition)");

    iqdloop::FrozenIq fz;
    fz.source_index = 42;
    fz.file_name = "synth_42.ci16";
    fz.modulation = "BPSK";
    fz.source_class = 0;
    fz.snr_db = 18.0;
    fz.split_role = "holdout";

    iqpctbrx::TxBurstBuild expected;
    expected.payload = s.payload;
    expected.burst = s.burst;
    expected.tx_scale = 1.0;
    expected.payload_sha_pre = "pre";
    expected.payload_sha_post = "post";
    expected.burst_sha = "burstsha";

    iqfix10dump::dump_failed_rx_sample(
        fz, expected, s.burst, s.rx, s.ccr,
        s.ccr.coarse_cfo_hz, s.ccr.rec.cfo_hz, s.ccr.coarse_cfo_hz + s.ccr.rec.cfo_hz,
        true, true, "RF_PRESERVES_IQ", base, 2048.0, s.cfg, 625.0, 21.74, -625.0, 625.0);

    const replay24::ReplayResult r = replay24::replay_from_dir(base + "/failed_rx/42");
    check(r.sha_ok, "replay: raw_rx sha256 cross-check PASS");
    check(r.failure_ok, "replay: failure enum cross-check PASS");
    check(r.timing_ok, "replay: timing offset cross-check PASS");
    check(r.cfo_ok, "replay: coarse+fine CFO cross-check PASS");
    check(r.corr_resid_ok, "replay: corr/residual cross-check PASS (<1e-6)");
    check(r.ccr.rec.valid == s.ccr.rec.valid, "replay: valid flag matches original");
    check(r.ccr.rec.timing_offset == s.ccr.rec.timing_offset, "replay: timing == original");
}

void test_curves() {
    const Synthetic s = make_synthetic();
    // Recompute the coarse-de-rotated capture + integer timing anchor (same as main()).
    const double coarse = s.ccr.coarse_cfo_hz;
    std::vector<std::complex<double>> derot(s.rx.size());
    for (std::size_t n = 0; n < s.rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * coarse * static_cast<double>(n) /
                          static_cast<double>(iqrftrain::kFs);
        derot[n] = s.rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }
    const iqrfrec::PerFileRecovery irec = iqrfrec::estimate(derot, s.cfg);
    replay24::print_timing_curve(derot, irec.timing_offset);
    replay24::print_fractional_curve(derot, irec.timing_offset, s.ccr, s.cfg, 32);
    check(true, "timing + fractional curves run without throwing");
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
    std::printf("test_fix10class24_replay\n");
    run_test("self_test", test_self_test);
    run_test("replay_crosscheck", [] { test_replay_crosscheck(kBase); });
    run_test("curves", test_curves);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
