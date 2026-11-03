#pragma once
// Versioned ResultFrame contract for the HDMI touch UI — V1.1.
//
// V1.1 changes vs the V1 (hdmi_ui_v1) contract:
//   * the frame is model-generic: it CARRIES its own ``class_names`` (8..16
//     classes) and ``scores``, instead of a frozen 8-class order baked into the
//     UI.  The UI draws however many classes the frame declares.
//   * ``contract_version`` (=2) + ``model_id`` identify which contract/model
//     produced the frame.
//   * ``predicted_index`` / ``predicted_class`` replace the fixed ``class_id`` /
//     ``class_name`` of V1.
//
// Backward compatibility: the parser (src/json_result_frame.cpp) also accepts
// the legacy V1 shape (``schema_version``, ``class_id``, ``class_name``,
// ``probabilities`` over the 8-class order) so old ``mock_data/*.jsonl`` replays
// unchanged; legacy frames are normalised into this same struct.
//
// This header is Qt-free so it can be unit-tested on the host and reused
// unchanged on the board.  The wire format is JSON Lines (one object per line);
// see result_frame_v1_1.schema.json for the normative text.
//
// Reused, unchanged and read-only, from the SDR adapter:
//   * the per-stage latency keys (perf::Stage in perf_stats.hpp);
//   * the anomaly-counter vocabulary (iq::SequenceStats) plus the UI-level
//     timeout/error counters (pipeline::FailureClass).

#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace hdmiui {

constexpr int kContractVersion = 2;        // V1.1 (model-generic)
constexpr int kLegacyContractVersion = 1;  // accepted for old 8-class replay

constexpr int kMinClasses = 8;
constexpr int kMaxClasses = 16;

// Default 10-class order for the V1.1 mock.  This is NOT the only valid order:
// every frame carries its own class_names, so the UI never hardcodes it.
inline const std::vector<std::string>& default_class_names() {
    static const std::vector<std::string> names = {
        "AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
        "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
    };
    return names;
}

// Legacy 8-class order, kept only so old replay files can be normalised.
inline const std::vector<std::string>& legacy_class_names() {
    static const std::vector<std::string> names = {
        "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM",
    };
    return names;
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
    int contract_version = kContractVersion;
    std::string model_id;
    std::vector<std::string> class_names;  // frame's own class list (8..16)
    std::vector<double> scores;            // len == class_names
    int predicted_index = -1;              // argmax index into class_names
    std::string predicted_class;           // == class_names[predicted_index]
    std::uint64_t frame_id = 0;
    std::uint64_t timestamp_ns = 0;
    Source source = Source::Unknown;
    double confidence = 0.0;               // predicted class confidence in [0,1]
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

inline bool valid_contract_version(int v) {
    return v == kContractVersion || v == kLegacyContractVersion;
}

// A frame is "stale" when its timestamp is older than `timeout_ns` ago.
inline bool is_stale(std::uint64_t timestamp_ns, std::uint64_t now_ns,
                     std::uint64_t timeout_ns) {
    return now_ns >= timestamp_ns && (now_ns - timestamp_ns) > timeout_ns;
}

// Validate a frame.  Returns an empty string when valid, otherwise a reason.
inline std::string validate(const ResultFrame& f) {
    if (!valid_contract_version(f.contract_version))
        return "contract_version unsupported";
    if (f.contract_version == kContractVersion && f.model_id.empty())
        return "model_id empty";

    const std::size_t n = f.class_names.size();
    if (n < static_cast<std::size_t>(kMinClasses) ||
        n > static_cast<std::size_t>(kMaxClasses))
        return "class_names length out of [8,16]";
    for (const std::string& c : f.class_names)
        if (c.empty()) return "empty class name";
    for (std::size_t i = 0; i < n; ++i)
        for (std::size_t j = i + 1; j < n; ++j)
            if (f.class_names[i] == f.class_names[j]) return "duplicate class name";

    if (f.scores.size() != n) return "scores length != class_names length";
    for (double s : f.scores)
        if (!is_finite(s) || s < 0.0 || s > 1.0) return "score out of [0,1] or non-finite";

    if (f.predicted_index < 0 || f.predicted_index >= static_cast<int>(n))
        return "predicted_index out of range";
    if (f.predicted_class != f.class_names[static_cast<std::size_t>(f.predicted_index)])
        return "predicted_class != class_names[predicted_index]";

    if (!is_finite(f.confidence) || f.confidence < 0.0 || f.confidence > 1.0)
        return "confidence must be finite in [0,1]";

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
