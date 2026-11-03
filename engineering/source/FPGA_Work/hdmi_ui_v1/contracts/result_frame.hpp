#pragma once
// Versioned ResultFrame contract for the HDMI touch UI.
//
// This is the ONLY data structure the UI consumes from the recognition
// program (FPGA -> NPU pipeline).  It is Qt-free so it can be unit-tested on
// the host and reused unchanged on the board.  The wire format is JSON Lines
// (one object per line); see result_frame.schema.json for the normative text.
//
// Reused, unchanged and read-only, from the SDR adapter:
//   * the 8 frozen class names (deployment_contract.yaml order);
//   * the per-stage latency keys (perf::Stage in perf_stats.hpp);
//   * the anomaly-counter vocabulary (iq::SequenceStats) plus the UI-level
//     timeout/error counters (pipeline::FailureClass).

#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace hdmiui {

constexpr int kSchemaVersion = 1;
constexpr int kNumClasses = 8;

// Frozen modulation-class order (must match deployment_contract.yaml).
inline const char* const* class_names() {
    static const char* const names[kNumClasses] = {
        "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM",
    };
    return names;
}

inline int class_id_of(const std::string& name) {
    for (int i = 0; i < kNumClasses; ++i) {
        if (class_names()[i] == name) return i;
    }
    return -1;
}

// Where a frame came from.  MOCK data must never be presented as real RF.
enum class Source { Mock = 0, File = 1, Sdr = 2, Unknown = 3 };

inline const char* source_name(Source s) {
    switch (s) {
        case Source::Mock: return "MOCK";
        case Source::File: return "FILE";
        case Source::Sdr:  return "SDR";
        default:           return "UNKNOWN";
    }
}

inline Source source_from_name(const std::string& n) {
    if (n == "MOCK") return Source::Mock;
    if (n == "FILE") return Source::File;
    if (n == "SDR")  return Source::Sdr;
    return Source::Unknown;
}

// A subsystem status.  The UI pairs every state with color + shape + text.
enum class Status { Ok = 0, Warning = 1, Error = 2, Disconnected = 3, Unknown = 4 };

inline const char* status_name(Status s) {
    switch (s) {
        case Status::Ok:           return "ok";
        case Status::Warning:      return "warning";
        case Status::Error:        return "error";
        case Status::Disconnected: return "disconnected";
        default:                   return "unknown";
    }
}

inline Status status_from_name(const std::string& n) {
    if (n == "ok") return Status::Ok;
    if (n == "warning") return Status::Warning;
    if (n == "error") return Status::Error;
    if (n == "disconnected") return Status::Disconnected;
    return Status::Unknown;
}

// Per-stage latency in microseconds.  Keys reuse perf::Stage unchanged.
struct LatencyUs {
    double sdr_capture = 0.0;
    double resample_frame = 0.0;
    double plddr_transfer = 0.0;
    double fpga_process = 0.0;
    double npu_infer = 0.0;
    double end_to_end = 0.0;
};

// Anomaly counters.  dropped/overflow/duplicate/reorder reuse
// iq::SequenceStats; timeout/error are pipeline-level.
struct Counters {
    std::uint64_t dropped = 0;
    std::uint64_t overflow = 0;
    std::uint64_t duplicate = 0;
    std::uint64_t reorder = 0;
    std::uint64_t timeout = 0;
    std::uint64_t error = 0;
};

struct ResultFrame {
    int schema_version = kSchemaVersion;
    std::uint64_t frame_id = 0;
    std::uint64_t timestamp_ns = 0;
    Source source = Source::Unknown;
    int class_id = -1;
    std::string class_name;
    double confidence = 0.0;
    std::vector<double> probabilities;  // length 8 when valid
    double snr_db = 0.0;
    double center_frequency_hz = 0.0;
    double sample_rate_hz = 0.0;
    LatencyUs latency_us;
    double fps = 0.0;
    Counters counters;
    Status sdr_status = Status::Unknown;
    Status fpga_status = Status::Unknown;
    Status npu_status = Status::Unknown;
    std::vector<double> spectrum_bins;  // optional; may be empty
    std::string message;                // optional
};

inline bool is_finite(double v) { return std::isfinite(v); }

inline bool valid_class_id(int id) { return id >= 0 && id < kNumClasses; }

// A frame is "stale" when its timestamp is older than `timeout_ns` ago.
inline bool is_stale(std::uint64_t timestamp_ns, std::uint64_t now_ns,
                     std::uint64_t timeout_ns) {
    return now_ns >= timestamp_ns && (now_ns - timestamp_ns) > timeout_ns;
}

// Validate a frame.  Returns an empty string when valid, otherwise a reason.
inline std::string validate(const ResultFrame& f) {
    if (f.schema_version != kSchemaVersion) return "schema_version mismatch";
    if (!valid_class_id(f.class_id)) return "class_id out of range";
    if (class_id_of(f.class_name) != f.class_id) return "class_name != class_id";
    if (!is_finite(f.confidence) || f.confidence < 0.0 || f.confidence > 1.0)
        return "confidence must be finite in [0,1]";
    if (f.probabilities.size() != static_cast<std::size_t>(kNumClasses))
        return "probabilities must have 8 entries";
    for (double p : f.probabilities)
        if (!is_finite(p) || p < 0.0 || p > 1.0)
            return "probability out of [0,1] or non-finite";
    if (!is_finite(f.snr_db)) return "snr_db non-finite";
    if (!is_finite(f.center_frequency_hz)) return "center_frequency_hz non-finite";
    if (!is_finite(f.sample_rate_hz)) return "sample_rate_hz non-finite";
    if (!is_finite(f.fps) || f.fps < 0.0) return "fps invalid";
    const LatencyUs& l = f.latency_us;
    if (!is_finite(l.sdr_capture) || l.sdr_capture < 0.0 ||
        !is_finite(l.resample_frame) || l.resample_frame < 0.0 ||
        !is_finite(l.plddr_transfer) || l.plddr_transfer < 0.0 ||
        !is_finite(l.fpga_process) || l.fpga_process < 0.0 ||
        !is_finite(l.npu_infer) || l.npu_infer < 0.0 ||
        !is_finite(l.end_to_end) || l.end_to_end < 0.0)
        return "latency non-finite or negative";
    for (double b : f.spectrum_bins)
        if (!is_finite(b)) return "spectrum_bins non-finite";
    return "";
}

}  // namespace hdmiui
