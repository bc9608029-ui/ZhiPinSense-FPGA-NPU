// Qt-free contract + integrity test (V1.1).
//
// Builds with only a C++17 toolchain (no Qt) and exercises the versioned,
// model-generic contract (contracts/result_frame.hpp).  The same assertions
// live in the Python mirror (tests/test_frame_validator_mirror.py) so the two
// languages stay in lock-step.
//
//   cmake -B build && cmake --build build && ctest --test-dir build

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "contracts/result_frame.hpp"

using namespace hdmiui;

namespace {
int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++g_failures;
    }
}

ResultFrame good_frame() {
    ResultFrame f;
    f.contract_version = kContractVersion;  // 2
    f.model_id = "test-model";
    f.class_names = default_class_names();  // 10 classes
    f.scores.assign(f.class_names.size(), 0.01);
    f.scores[7] = 0.9;
    f.predicted_index = 7;
    f.predicted_class = "16QAM";
    f.frame_id = 1;
    f.confidence = 0.9;
    f.snr_db = 18.0;
    f.center_frequency_hz = 2.4e9;
    f.sample_rate_hz = 128000.0;
    f.latency_us.end_to_end = 1.0;
    f.fps = 15.0;
    return f;
}
}  // namespace

int main() {
    // Versions and default class order (must match the schema + the mock).
    check(kContractVersion == 2, "kContractVersion == 2");
    check(kLegacyContractVersion == 1, "kLegacyContractVersion == 1");
    check(kMinClasses == 8 && kMaxClasses == 16, "class range [8,16]");

    const std::vector<std::string>& dn = default_class_names();
    check(dn.size() == 10, "default_class_names has 10 entries");
    check(dn[0] == "AM-DSB" && dn[1] == "WBFM" && dn[2] == "2FSK" &&
              dn[3] == "GFSK" && dn[4] == "BPSK" && dn[5] == "QPSK" &&
              dn[6] == "8PSK" && dn[7] == "16QAM" && dn[8] == "64QAM" &&
              dn[9] == "OFDM",
          "default class order");

    const std::vector<std::string>& ln = legacy_class_names();
    check(ln.size() == 8, "legacy_class_names has 8 entries");
    check(ln[0] == "BPSK" && ln[7] == "OFDM", "legacy class order");

    // Source/status name round-trips.
    check(std::string(source_name(Source::Mock)) == "MOCK", "source_name(Mock)");
    check(source_from_name("SDR") == Source::Sdr, "source_from_name(\"SDR\")");
    check(std::string(status_name(Status::Disconnected)) == "disconnected",
          "status_name(Disconnected)");
    check(status_from_name("error") == Status::Error, "status_from_name(\"error\")");

    // A valid 10-class frame.
    check(validate(good_frame()).empty(), "validate(good 10-class frame)");

    // Cross-field invariants.
    ResultFrame bad = good_frame();
    bad.predicted_class = "QPSK";
    check(validate(bad) == "predicted_class != class_names[predicted_index]",
          "validate(predicted_class mismatch)");

    ResultFrame bad2 = good_frame();
    bad2.confidence = 1.5;
    check(validate(bad2) == "confidence must be finite in [0,1]",
          "validate(confidence range)");

    ResultFrame bad3 = good_frame();
    bad3.snr_db = std::nan("");
    check(validate(bad3) == "snr_db non-finite", "validate(nan snr)");

    ResultFrame bad4 = good_frame();
    bad4.model_id.clear();
    check(validate(bad4) == "model_id empty", "validate(empty model_id)");

    ResultFrame bad5 = good_frame();
    bad5.scores.pop_back();  // 9 scores vs 10 classes
    check(validate(bad5) == "scores length != class_names length",
          "validate(scores length)");

    ResultFrame bad6 = good_frame();
    bad6.class_names.resize(7);  // < 8
    check(validate(bad6) == "class_names length out of [8,16]",
          "validate(too few classes)");

    // Legacy (contract_version == 1) may carry an empty model_id.
    ResultFrame legacy = good_frame();
    legacy.contract_version = kLegacyContractVersion;
    legacy.model_id.clear();
    check(validate(legacy).empty(), "validate(legacy empty model_id ok)");

    if (g_failures == 0) {
        std::printf("test_contract: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_contract: %d check(s) failed\n", g_failures);
    return 1;
}
