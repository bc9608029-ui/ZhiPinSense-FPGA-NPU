// Qt-free contract + integrity test.
//
// Builds with only a C++17 toolchain (no Qt) and exercises the frozen contract
// (contracts/result_frame.hpp) and the consumer-side integrity layer
// (src/frame_validator.hpp).  The same assertions live in the Python mirror
// (tests/test_frame_validator_mirror.py) so the two languages stay in lock-step.
//
//   cmake -B build && cmake --build build && ctest --test-dir build

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>

#include "contracts/result_frame.hpp"
#include "src/frame_validator.hpp"

using namespace hdmiui;

namespace {
int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++g_failures;
    }
}
}  // namespace

int main() {
    // Frozen class order (must match deployment_contract.yaml).
    check(kNumClasses == 8, "kNumClasses == 8");
    check(std::string(class_names()[0]) == "BPSK", "class_names()[0] == BPSK");
    check(std::string(class_names()[7]) == "OFDM", "class_names()[7] == OFDM");
    check(class_id_of("16QAM") == 3, "class_id_of(\"16QAM\") == 3");
    check(class_id_of("nope") == -1, "class_id_of(unknown) == -1");

    // Source/status name round-trips.
    check(std::string(source_name(Source::Mock)) == "MOCK", "source_name(Mock)");
    check(source_from_name("SDR") == Source::Sdr, "source_from_name(\"SDR\")");
    check(std::string(status_name(Status::Disconnected)) == "disconnected",
          "status_name(Disconnected)");
    check(status_from_name("error") == Status::Error, "status_from_name(\"error\")");

    // A valid frame.
    ResultFrame f;
    f.schema_version = kSchemaVersion;
    f.frame_id = 1;
    f.class_id = 3;
    f.class_name = "16QAM";
    f.confidence = 0.9;
    f.probabilities.assign(8, 0.0);
    f.probabilities[3] = 0.9;
    f.snr_db = 18.0;
    f.center_frequency_hz = 2.4e9;
    f.sample_rate_hz = 128000.0;
    f.latency_us.end_to_end = 1.0;
    f.fps = 15.0;
    check(validate(f).empty(), "validate(good)");

    ResultFrame bad = f;
    bad.class_name = "QPSK";
    check(validate(bad) == "class_name != class_id", "validate(class_name mismatch)");

    ResultFrame bad2 = f;
    bad2.confidence = 1.5;
    check(validate(bad2) == "confidence must be finite in [0,1]",
          "validate(confidence range)");

    ResultFrame bad3 = f;
    bad3.snr_db = std::nan("");
    check(validate(bad3) == "snr_db non-finite", "validate(nan snr)");

    // is_stale boundary (mirrors tests/test_frame_validator_mirror.py).
    check(is_stale(100, 200, 50), "is_stale(older-than-window)");
    check(!is_stale(160, 200, 50), "is_stale(within-window)");
    check(!is_stale(200, 200, 50), "is_stale(exact boundary)");
    check(!is_stale(300, 200, 50), "is_stale(clock skew)");

    // FrameSequenceMonitor: duplicate / reorder / gap (mirrors the Python test).
    FrameSequenceMonitor m;
    m.observe(1);
    m.observe(1);
    m.observe(1);
    check(m.stats().duplicate == 2, "sequence duplicate");
    m.reset();
    m.observe(1);
    m.observe(2);
    m.observe(3);
    m.observe(2);
    m.observe(4);
    check(m.stats().reorder == 1, "sequence reorder");
    check(m.stats().gap == 1, "sequence gap");
    check(m.stats().dropped == 1, "sequence dropped");
    check(m.stats().last_frame_id == 4, "sequence last_frame_id");

    if (g_failures == 0) {
        std::printf("test_contract: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_contract: %d check(s) failed\n", g_failures);
    return 1;
}
