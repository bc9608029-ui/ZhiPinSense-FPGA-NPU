#pragma once
// Deterministic live simulation (V1.1: 10-class default, model-generic).
// Every produced frame is source == MOCK and the UI keeps the MOCK badge
// visible at all times.  The same scenarios are generated, fully
// deterministically, into mock_data/*.jsonl by scripts/generate_mock_data.py
// for replay and tests.
#include <chrono>
#include <cstdint>
#include <optional>
#include <string>

#include "src/data_source.hpp"

namespace hdmiui {

class MockDataSource : public DataSource {
public:
    enum class Scenario {
        Normal,             // one class, high confidence, healthy
        ModulationSwitch,   // class rotates every N frames
        LowConfidence,      // correct class but low confidence
        Stale,              // healthy frames, then goes silent (UI dims to stale)
        Reorder,            // periodic out-of-order frame_id
        DropOverflow,       // periodic frame_id gaps + overflow
        FpgaError,          // fpga_status -> error, counters.error++
        NpuTimeout,         // npu_status -> error, counters.timeout++
        SdrDisconnect,      // sdr_status -> disconnected, stream ends
        Recovery,           // normal -> fault -> recover
    };

    static constexpr int kScenarioCount = 10;

    MockDataSource(Scenario scenario, std::uint64_t seed = 0x20261002, double fps = 15.0);

    std::string name() const override { return "MOCK"; }
    std::string kind() const override { return "mock"; }
    bool open(std::string* error) override;
    std::optional<ResultFrame> next(int timeout_ms) override;
    void close() override;

    static const char* scenario_name(Scenario s);

private:
    Scenario scenario_;
    std::uint64_t seed_;
    double fps_;
    std::uint64_t frame_id_ = 0;  // monotonic next id (independent of emitted id)
    std::uint64_t step_ = 0;      // number of frames produced
    std::uint32_t rng_ = 0;
    bool opened_ = false;
    bool ended_ = false;

    std::uint32_t rnd();          // xorshift32
    double rnd01();
    ResultFrame make_frame();
};

}  // namespace hdmiui
