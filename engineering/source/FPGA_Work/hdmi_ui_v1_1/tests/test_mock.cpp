// Qt-free test of MockDataSource (V1.1, 10 classes): every frame validates,
// the 10-class contract holds, the new stale/reorder scenarios behave, and two
// same-seed mocks are deterministic.  Mirrors tests/test_mock_data.py.

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "contracts/result_frame.hpp"
#include "src/mock_data_source.hpp"

using namespace hdmiui;

namespace {
int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++g_failures;
    }
}

std::vector<ResultFrame> drain(MockDataSource::Scenario sc, std::size_t cap = 1000) {
    MockDataSource m(sc);
    std::string err;
    if (!m.open(&err)) return {};
    std::vector<ResultFrame> out;
    for (std::size_t i = 0; i < cap; ++i) {
        std::optional<ResultFrame> f = m.next(0);
        if (!f) break;
        out.push_back(*f);
    }
    return out;
}
}  // namespace

int main() {
    // Scenario names cover all 10.
    check(MockDataSource::kScenarioCount == 10, "10 scenarios");
    for (int i = 0; i < MockDataSource::kScenarioCount; ++i) {
        const auto sc = static_cast<MockDataSource::Scenario>(i);
        check(std::string(MockDataSource::scenario_name(sc)) != "unknown",
              "scenario has a name");
    }

    // Every scenario emits valid 10-class frames.
    for (int i = 0; i < MockDataSource::kScenarioCount; ++i) {
        const auto sc = static_cast<MockDataSource::Scenario>(i);
        const auto frames = drain(sc);
        check(!frames.empty(), "scenario produces frames");
        for (const ResultFrame& f : frames) {
            check(f.contract_version == kContractVersion, "contract_version == 2");
            check(!f.model_id.empty(), "model_id non-empty");
            check(f.class_names.size() == 10, "10 class names");
            check(f.scores.size() == 10, "10 scores");
            check(f.source == Source::Mock, "source == MOCK");
            check(validate(f).empty(), "frame validates");
        }
    }

    // Normal: monotonic frame ids, one class throughout.
    {
        const auto f = drain(MockDataSource::Scenario::Normal);
        for (std::size_t i = 0; i < f.size(); ++i)
            check(f[i].frame_id == i, "normal frame_id monotonic");
        check(f.front().predicted_index == 7 &&
                  f.front().predicted_class == "16QAM",
              "normal class is 16QAM");
    }

    // Reorder: frame id goes backward at step % 40 == 20, reorder counter set.
    {
        const auto f = drain(MockDataSource::Scenario::Reorder);
        bool saw_reorder = false;
        for (std::size_t i = 0; i < f.size(); ++i) {
            if (i >= 2 && i % 40 == 20) {
                check(f[i].frame_id == i - 2, "reorder frame_id == step - 2");
                check(f[i].counters.reorder == 1, "reorder counter == 1");
                saw_reorder = true;
            } else {
                check(f[i].counters.reorder == 0, "no reorder elsewhere");
            }
        }
        check(saw_reorder, "reorder scenario produced a reorder");
    }

    // Drop/overflow: frame id jumps by 3 at step % 50 == 0 (step > 0).
    {
        const auto f = drain(MockDataSource::Scenario::DropOverflow);
        bool saw_drop = false;
        for (std::size_t i = 0; i < f.size(); ++i) {
            if (i > 0 && i % 50 == 0) {
                check(f[i].counters.dropped == 3, "drop counter == 3");
                check(f[i].counters.overflow == 1, "overflow counter == 1");
                saw_drop = true;
            }
        }
        check(saw_drop, "drop scenario produced a drop");
    }

    // Stale: exactly 30 healthy frames, then silence.
    {
        const auto f = drain(MockDataSource::Scenario::Stale);
        check(f.size() == 30, "stale emits exactly 30 frames");
        for (const ResultFrame& x : f)
            check(x.sdr_status == Status::Ok && x.fpga_status == Status::Ok &&
                      x.npu_status == Status::Ok,
                  "stale frames are healthy");
    }

    // SDR disconnect: 31 frames, last one disconnected, then silence.
    {
        const auto f = drain(MockDataSource::Scenario::SdrDisconnect);
        check(f.size() == 31, "sdr_disconnect emits 31 frames");
        check(f.back().sdr_status == Status::Disconnected, "last frame disconnected");
    }

    // Determinism: same seed -> identical frames (ignoring the wall-clock ts).
    {
        const auto a = drain(MockDataSource::Scenario::Recovery);
        const auto b = drain(MockDataSource::Scenario::Recovery);
        check(a.size() == b.size(), "deterministic frame count");
        for (std::size_t i = 0; i < a.size() && i < b.size(); ++i) {
            const ResultFrame& x = a[i];
            const ResultFrame& y = b[i];
            check(x.frame_id == y.frame_id && x.predicted_index == y.predicted_index &&
                      x.scores == y.scores && x.confidence == y.confidence &&
                      x.snr_db == y.snr_db && x.counters.error == y.counters.error,
                  "deterministic frame contents");
        }
    }

    if (g_failures == 0) {
        std::printf("test_mock: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_mock: %d check(s) failed\n", g_failures);
    return 1;
}
