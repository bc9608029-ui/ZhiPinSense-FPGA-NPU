#include "mock_data_source.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <vector>

namespace hdmiui {

namespace {

// Model id stamped on every mock frame (non-empty, per the V1.1 contract).
constexpr const char* kMockModelId = "mock-10class-v1.1";

void softmax(std::vector<double>& v) {
    double m = v[0];
    for (double x : v) m = std::max(m, x);
    double s = 0.0;
    for (double& x : v) { x = std::exp(x - m); s += x; }
    for (double& x : v) x /= s;
}

// Deterministic 128-bin power spectrum; main-lobe centre tracks the class.
std::vector<double> spectrum_for(int cls, bool degraded) {
    constexpr int n = 128;
    const double centre = 18.0 + cls * 12.0;
    std::vector<double> out(n, 0.0);
    for (int i = 0; i < n; ++i) {
        const double noise = 0.5 + 0.5 * std::sin(i * 12.9898) * std::sin(i * 4.1414);
        double v = 0.04 + 0.05 * noise;
        const double d1 = i - centre;
        v += (degraded ? 0.4 : 1.0) * std::exp(-(d1 * d1) / (2.0 * 5.0 * 5.0));
        const double d2 = i - (centre + 24.0);
        v += 0.25 * std::exp(-(d2 * d2) / (2.0 * 3.0 * 3.0));
        out[static_cast<std::size_t>(i)] = v;
    }
    return out;
}

std::uint64_t now_ns() {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
}

}  // namespace

const char* MockDataSource::scenario_name(Scenario s) {
    switch (s) {
        case Scenario::Normal:           return "normal";
        case Scenario::ModulationSwitch: return "modulation_switch";
        case Scenario::LowConfidence:    return "low_confidence";
        case Scenario::Stale:            return "stale";
        case Scenario::Reorder:          return "reorder";
        case Scenario::DropOverflow:     return "drop_overflow";
        case Scenario::FpgaError:        return "fpga_error";
        case Scenario::NpuTimeout:       return "npu_timeout";
        case Scenario::SdrDisconnect:    return "sdr_disconnect";
        case Scenario::Recovery:         return "recovery";
    }
    return "unknown";
}

MockDataSource::MockDataSource(Scenario scenario, std::uint64_t seed, double fps)
    : scenario_(scenario), seed_(seed), fps_(fps), rng_(static_cast<std::uint32_t>(seed)) {}

bool MockDataSource::open(std::string* /*error*/) {
    rng_ = static_cast<std::uint32_t>(seed_);
    frame_id_ = 0;
    step_ = 0;
    ended_ = false;
    opened_ = true;
    return true;
}

void MockDataSource::close() {
    opened_ = false;
    ended_ = true;
}

std::uint32_t MockDataSource::rnd() {
    std::uint32_t x = rng_;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    rng_ = x;
    return x;
}

double MockDataSource::rnd01() {
    return static_cast<double>(rnd() & 0xFFFFFFu) / 16777216.0;
}

ResultFrame MockDataSource::make_frame() {
    const std::vector<std::string>& names = default_class_names();
    const int ncls = static_cast<int>(names.size());

    ResultFrame f;
    f.contract_version = kContractVersion;
    f.model_id = kMockModelId;
    f.class_names = names;
    f.source = Source::Mock;

    const std::uint64_t step = step_++;

    const bool fpga_fault = (scenario_ == Scenario::FpgaError && step >= 30) ||
                            (scenario_ == Scenario::Recovery && step >= 30 && step < 60);
    const bool npu_fault = (scenario_ == Scenario::NpuTimeout && step >= 30);
    const bool degraded = fpga_fault || npu_fault;

    // --- class selection (index into default_class_names) ---
    int cls = 7;  // 16QAM
    switch (scenario_) {
        case Scenario::ModulationSwitch: {
            static const int seq[4] = {4, 7, 8, 9};  // BPSK, 16QAM, 64QAM, OFDM
            cls = seq[(step / 40) % 4];
            break;
        }
        case Scenario::LowConfidence: cls = 5; break;   // QPSK
        case Scenario::Stale:         cls = 7; break;   // 16QAM
        case Scenario::Reorder:       cls = 8; break;   // 64QAM
        case Scenario::DropOverflow:  cls = 7; break;   // 16QAM
        case Scenario::FpgaError:     cls = 4; break;   // BPSK
        case Scenario::NpuTimeout:    cls = 6; break;   // 8PSK
        case Scenario::SdrDisconnect: cls = 2; break;   // 2FSK
        case Scenario::Recovery:      cls = 9; break;   // OFDM
        default:                      cls = 7; break;
    }
    f.predicted_index = cls;
    f.predicted_class = names[static_cast<std::size_t>(cls)];

    // --- frame id / drops / reorder ---
    const std::uint64_t sequential = frame_id_;  // monotonic next id
    std::uint64_t emit = sequential;
    bool reordered = false;
    if (scenario_ == Scenario::DropOverflow && step > 0 && step % 50 == 0) {
        emit = sequential + 3;                    // 3-frame gap
        f.counters.dropped += 3;
        f.counters.overflow += 1;
        f.message = "mock: overflow + dropped frames";
    } else if (scenario_ == Scenario::Reorder && step >= 2 && step % 40 == 20) {
        emit = sequential - 2;                    // a late/backward frame id
        f.counters.reorder += 1;
        f.message = "mock: out-of-order frame_id";
        reordered = true;
    }
    f.frame_id = emit;
    frame_id_ = (reordered ? sequential : emit) + 1;

    // --- scores ---
    double sharpness = 4.0;
    if (scenario_ == Scenario::LowConfidence) sharpness = 0.9;
    else if (degraded) sharpness = 0.6;
    std::vector<double> logits(static_cast<std::size_t>(ncls), 0.0);
    for (int i = 0; i < ncls; ++i)
        logits[static_cast<std::size_t>(i)] =
            (i == cls ? sharpness : 0.0) + (rnd01() - 0.5) * 0.6;
    softmax(logits);
    f.scores = logits;
    f.confidence = f.scores[static_cast<std::size_t>(cls)];

    // --- snr / rf params ---
    if (degraded) f.snr_db = -4.0 + rnd01() * 6.0;
    else if (scenario_ == Scenario::LowConfidence) f.snr_db = 8.0 + rnd01() * 4.0;
    else f.snr_db = 18.0 + rnd01() * 6.0;
    f.center_frequency_hz = 2400000000.0;
    f.sample_rate_hz = 128000.0;

    // --- latencies (µs) ---
    f.latency_us.sdr_capture = 90.0 + rnd01() * 20.0;
    f.latency_us.resample_frame = 25.0 + rnd01() * 10.0;
    f.latency_us.plddr_transfer = 40.0 + rnd01() * 12.0;
    f.latency_us.fpga_process = fpga_fault ? 0.0 : (200.0 + rnd01() * 40.0);
    f.latency_us.npu_infer = npu_fault ? 0.0 : (170.0 + rnd01() * 30.0);
    f.latency_us.end_to_end = f.latency_us.sdr_capture + f.latency_us.resample_frame +
                              f.latency_us.plddr_transfer + f.latency_us.fpga_process +
                              f.latency_us.npu_infer;
    f.fps = fps_;

    // --- status / counters ---
    f.sdr_status = Status::Ok;
    f.fpga_status = Status::Ok;
    f.npu_status = Status::Ok;
    if (scenario_ == Scenario::SdrDisconnect && step >= 30) {
        f.sdr_status = Status::Disconnected;
        f.message = "mock: SDR link down";
    } else if (fpga_fault) {
        f.fpga_status = Status::Error;
        f.counters.error += 1;
        f.message = (scenario_ == Scenario::Recovery)
                        ? "mock: faulting (recovery in progress)"
                        : "mock: FPGA pipeline error";
    } else if (npu_fault) {
        f.npu_status = Status::Error;
        f.counters.timeout += 1;
        f.message = "mock: NPU infer timeout";
    }

    f.spectrum_bins = spectrum_for(cls, degraded);
    f.timestamp_ns = now_ns();
    return f;
}

std::optional<ResultFrame> MockDataSource::next(int /*timeout_ms*/) {
    if (!opened_ || ended_) return std::nullopt;
    // "stale": healthy frames, then the stream goes silent (no status change)
    // so the UI's arrival-based staleness detector dims the last frame.
    if (scenario_ == Scenario::Stale && step_ >= 30) {
        ended_ = true;
        return std::nullopt;
    }
    ResultFrame f = make_frame();
    // SDR disconnect emits one "disconnected" frame then ends the stream.
    if (scenario_ == Scenario::SdrDisconnect && step_ > 30) ended_ = true;
    return f;
}

}  // namespace hdmiui
