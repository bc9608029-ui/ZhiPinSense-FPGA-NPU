// test_pluto_external_tx.cpp -- host tests for Route G fix10 Task B/I: the PC-side
// external TX safety sequence (extrf_tx::run_external_tx) driven by FakePlutoDevice.
// No libiio, no RF: every safety gate (serial match, atten ceiling, loopback-off,
// DMA-payload SHA, tx_stop-on-exit) is exercised offline.
//
// Covered (6 scenarios):
//   1. serial mismatch -> aborts before emitting (and before TX runs);
//   2. --atten above the -40 dB ceiling -> rejected (never raised);
//   3. happy path: one frame tx, DMA payload SHA matches, all read-backs pass,
//      and no cyclic TX is left running after exit;
//   4. producer exception mid-run -> TX stopped + rethrown (buffer destroyed);
//   5. immediate producer stop -> zero frames emitted, clean exit;
//   6. empty serial read-back -> refused (the never-auto-select guarantee).

#include "../board_package/pluto_external_tx.hpp"
#include "../sdr_adapter/pluto_device.hpp"

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// Deterministic PRBS interleaved int16 (same LCG as the other loopback tests).
std::vector<std::int16_t> make_prbs(std::size_t P, int A, std::uint32_t seed) {
    std::vector<std::int16_t> iq(P * 2);
    std::uint32_t s = seed ? seed : 0x9e3779b9u;
    auto bit = [&s]() -> int {
        s = s * 1664525u + 1013904223u;
        return static_cast<int>((s >> 24) & 1u);
    };
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(bit() ? A : -A);
        iq[k * 2 + 1] = static_cast<std::int16_t>(bit() ? A : -A);
    }
    return iq;
}

// A full air-interface frame (valid header CRC) for the producer to emit.
std::vector<std::int16_t> build_test_frame() {
    const auto payload = make_prbs(extrf::frame::kPayloadComplex, 1500, 0xBEEFu);
    extrf::frame::HeaderFields f;
    f.valid = true;
    f.version = extrf::frame::kFrameVersion;
    f.run_id = 0;
    f.index = 0;
    f.payload_count = static_cast<std::uint16_t>(extrf::frame::kPayloadComplex);
    f.sha_short = 0xCAFEBABEu;
    f.crc16 = 0;
    f.crc_ok = false;
    extrf::frame::attach_header_crc(f);
    return extrf::frame::build_frame(payload, f);
}

constexpr std::uint64_t kCenter = 2400000000ull;

// ---- 1. serial mismatch aborts (never emit on the wrong device) -------------

void test_serial_mismatch_aborts() {
    pluto::FakePlutoDevice dev;
    dev.fake_serial = "abcd";
    bool emitted = false;
    const extrf_tx::FrameProducer p = [&](std::vector<std::int16_t>&,
                                          extrf::frame::HeaderFields&) {
        emitted = true;
        return true;
    };
    bool threw = false;
    try {
        extrf_tx::run_external_tx(dev, "wrong", -80.0, kCenter, p);
    } catch (const std::exception&) {
        threw = true;
    }
    check(threw, "serial: mismatched serial throws");
    check(!emitted, "serial: producer never called");
    check(!dev.tx_running(), "serial: no TX left running");
}

// ---- 2. atten above the -40 dB ceiling is rejected --------------------------

void test_atten_above_ceiling_rejected() {
    pluto::FakePlutoDevice dev;
    dev.fake_serial = "s1";
    bool emitted = false;
    const extrf_tx::FrameProducer p = [&](std::vector<std::int16_t>&,
                                          extrf::frame::HeaderFields&) {
        emitted = true;
        return true;
    };
    bool threw = false;
    try {
        extrf_tx::run_external_tx(dev, "s1", -30.0, kCenter, p);
    } catch (const std::exception&) {
        threw = true;
    }
    check(threw, "atten: -30 dB > -40 dB ceiling rejected");
    check(!emitted, "atten: producer never called");
    check(!dev.tx_running(), "atten: no TX left running");
}

// ---- 3. happy path: one frame, SHA match, all read-backs, clean exit --------

void test_tx_dma_payload_sha_matches() {
    pluto::FakePlutoDevice dev;
    dev.fake_serial = "s1";
    const std::vector<std::int16_t> frame = build_test_frame();
    int calls = 0;
    const extrf_tx::FrameProducer p = [&](std::vector<std::int16_t>& out,
                                          extrf::frame::HeaderFields&) {
        if (calls > 0) return false;
        out = frame;
        ++calls;
        return true;
    };
    extrf_tx::TxRunReport rep =
        extrf_tx::run_external_tx(dev, "s1", -80.0, kCenter, p);
    check(rep.serial_ok, "happy: serial matched");
    check(rep.sample_rate_ok, "happy: sample rate read-back OK");
    check(rep.atten_ok, "happy: atten read-back OK");
    check(rep.loopback_ok, "happy: loopback read-back == 0");
    check(rep.frames_tx == 1, "happy: exactly one frame tx");
    check(rep.frames_dma_mismatch == 0, "happy: DMA payload SHA matched");
    check(rep.restore_ok, "happy: params restored");
    check(rep.stopped_clean, "happy: tx_stop() -> !tx_running");
    check(!rep.tx_running_after_exit, "happy: no cyclic TX after exit");
    check(!dev.tx_running(), "happy: device reports not running");
}

// ---- 4. producer exception mid-run stops the TX and rethrows ----------------

void test_producer_exception_stops_tx() {
    pluto::FakePlutoDevice dev;
    dev.fake_serial = "s1";
    const std::vector<std::int16_t> frame = build_test_frame();
    int calls = 0;
    const extrf_tx::FrameProducer p = [&](std::vector<std::int16_t>& out,
                                          extrf::frame::HeaderFields&) {
        if (calls == 0) {
            out = frame;
            ++calls;
            return true;   // one frame emitted -> tx_start_cyclic runs
        }
        throw std::runtime_error("producer failure");
    };
    bool threw = false;
    try {
        extrf_tx::run_external_tx(dev, "s1", -80.0, kCenter, p);
    } catch (const std::exception&) {
        threw = true;
    }
    check(threw, "exc: producer exception rethrown");
    check(!dev.tx_running(), "exc: TX stopped on the abort path");
}

// ---- 5. immediate producer stop -> zero frames, clean exit ------------------

void test_immediate_stop_zero_frames() {
    pluto::FakePlutoDevice dev;
    dev.fake_serial = "s1";
    const extrf_tx::FrameProducer p = [](std::vector<std::int16_t>&,
                                         extrf::frame::HeaderFields&) { return false; };
    extrf_tx::TxRunReport rep =
        extrf_tx::run_external_tx(dev, "s1", -80.0, kCenter, p);
    check(rep.frames_tx == 0, "stop: zero frames emitted");
    check(!rep.tx_running_after_exit, "stop: no cyclic TX after exit");
    check(!dev.tx_running(), "stop: device not running");
}

// ---- 6. empty serial read-back is refused (never auto-select) ----------------

void test_empty_serial_refused() {
    pluto::FakePlutoDevice dev;
    dev.fake_serial = "";   // a device whose serial read-back is empty
    bool emitted = false;
    const extrf_tx::FrameProducer p = [&](std::vector<std::int16_t>&,
                                          extrf::frame::HeaderFields&) {
        emitted = true;
        return true;
    };
    bool threw = false;
    try {
        extrf_tx::run_external_tx(dev, "anything", -80.0, kCenter, p);
    } catch (const std::exception&) {
        threw = true;
    }
    check(threw, "empty: empty serial read-back refused");
    check(!emitted, "empty: producer never called");
    check(!dev.tx_running(), "empty: no TX left running");
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
    std::printf("test_pluto_external_tx\n");
    run_test("serial_mismatch_aborts", test_serial_mismatch_aborts);
    run_test("atten_above_ceiling_rejected", test_atten_above_ceiling_rejected);
    run_test("tx_dma_payload_sha_matches", test_tx_dma_payload_sha_matches);
    run_test("producer_exception_stops_tx", test_producer_exception_stops_tx);
    run_test("immediate_stop_zero_frames", test_immediate_stop_zero_frames);
    run_test("empty_serial_refused", test_empty_serial_refused);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
