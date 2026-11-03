#pragma once

// Linux / UI data interface for the non-model system layer.
//
// The on-board UI (or a log consumer) reads one JSON object per line from
// stdout.  Three record kinds are defined -- result (one inference), status
// (state transitions), metric (a scalar, e.g. per-stage latency) -- plus a
// JSON string escaper so class names / details can never break the framing.
//
// iCraft-free and header-only.  The pipeline emits these lines via
// ui::result_line / status_line / metric_line; the actual JSON is intentionally
// flat and dependency-free (no JSON library needed on the board).

#include "result_frame.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>

namespace ui {

// Minimal JSON string escaping (quotes, backslash, control chars).
inline std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (static_cast<unsigned char>(c) < 0x20u) {
                    char b[8];
                    std::snprintf(b, sizeof(b), "\\u%04x",
                                  static_cast<unsigned>(static_cast<unsigned char>(c)));
                    out += b;
                } else {
                    out += c;
                }
        }
    }
    return out;
}

// One inference result: the frame id, predicted and reference class, whether
// they matched, and the per-frame latencies (end-to-end and NPU-forward).
inline std::string result_line(std::uint64_t frame_id, const char* pred_class,
                               const char* ref_class, bool match,
                               double e2e_us, double npu_us) {
    char buf[640];
    std::snprintf(buf, sizeof(buf),
                  "{\"type\":\"result\",\"frame_id\":%llu,\"pred\":\"%s\",\"ref\":\"%s\","
                  "\"match\":%s,\"e2e_us\":%.3f,\"npu_us\":%.3f}",
                  static_cast<unsigned long long>(frame_id),
                  json_escape(pred_class).c_str(),
                  json_escape(ref_class).c_str(),
                  match ? "true" : "false", e2e_us, npu_us);
    return buf;
}

// A state transition (e.g. "capture", "fpga", "npu", "error", "done").
inline std::string status_line(const char* state, const char* detail) {
    char buf[640];
    std::snprintf(buf, sizeof(buf),
                  "{\"type\":\"status\",\"state\":\"%s\",\"detail\":\"%s\"}",
                  json_escape(state).c_str(), json_escape(detail).c_str());
    return buf;
}

// A scalar metric (e.g. per-stage latency or throughput).
inline std::string metric_line(const char* name, double value, const char* unit) {
    char buf[320];
    std::snprintf(buf, sizeof(buf),
                  "{\"type\":\"metric\",\"name\":\"%s\",\"value\":%.3f,\"unit\":\"%s\"}",
                  json_escape(name).c_str(), value, json_escape(unit).c_str());
    return buf;
}

// Full per-frame verdict (ResultFrame).  The `mock` field is always emitted so a
// MOCK result can be told apart from a real one by any downstream consumer.
// Full logits are deliberately NOT serialized (argmax + confidence suffice for
// the HDMI display); they remain in rf::ResultFrame::logits for programmatic use.
inline std::string result_frame_line(const rf::ResultFrame& r) {
    char buf[1024];
    std::snprintf(buf, sizeof(buf),
                  "{\"type\":\"result\",\"frame_id\":%llu,\"argmax_idx\":%d,"
                  "\"argmax_class\":\"%s\",\"confidence\":%.6f,\"class_count\":%d,"
                  "\"mock\":%s,\"source\":\"%s\",\"e2e_us\":%.3f,"
                  "\"preprocess_us\":%.3f,\"classify_us\":%.3f,"
                  "\"overflow\":%s,\"dropped\":%s,\"discontinuity\":%s,"
                  "\"short_frame\":%s}",
                  static_cast<unsigned long long>(r.frame_id), r.argmax_idx,
                  json_escape(r.argmax_class).c_str(), r.confidence, r.class_count,
                  r.mock ? "true" : "false", json_escape(r.source).c_str(),
                  r.e2e_us, r.preprocess_us, r.classify_us,
                  r.overflow ? "true" : "false", r.dropped ? "true" : "false",
                  r.discontinuity ? "true" : "false",
                  r.short_frame ? "true" : "false");
    return buf;
}

// Twelve-class chain result record (task 39e5 §八).  Adds the §七 extension
// fields to the flat record: version, full probabilities array, snr_db, quality,
// and model_sha.  Built dynamically (std::string) because the probabilities
// array can push past the fixed buffer used by the legacy result_frame_line().
inline std::string result_frame_v2_line(const rf::ResultFrame& r) {
    std::string out = "{\"type\":\"result\",\"version\":\"";
    out += json_escape(r.version.empty() ? "12class-chain-v1" : r.version);
    out += "\",\"frame_id\":";
    out += std::to_string(r.frame_id);
    out += ",\"timestamp_us\":";
    out += std::to_string(r.timestamp_us);
    out += ",\"argmax_idx\":";
    out += std::to_string(r.argmax_idx);
    out += ",\"argmax_class\":\"";
    out += json_escape(r.argmax_class);
    out += "\",\"confidence\":";
    char num[64];
    std::snprintf(num, sizeof(num), "%.6f", static_cast<double>(r.confidence));
    out += num;
    out += ",\"class_count\":";
    out += std::to_string(r.class_count);
    out += ",\"probabilities\":[";
    for (std::size_t i = 0; i < r.probabilities.size(); ++i) {
        if (i) out += ',';
        std::snprintf(num, sizeof(num), "%.6f",
                      static_cast<double>(r.probabilities[i]));
        out += num;
    }
    out += "],\"snr_db\":";
    if (std::isnan(r.snr_db)) out += "null";
    else { std::snprintf(num, sizeof(num), "%.3f", r.snr_db); out += num; }
    out += ",\"quality\":";
    std::snprintf(num, sizeof(num), "%.6f", r.quality);
    out += num;
    out += ",\"model_sha\":\"";
    out += json_escape(r.model_sha);
    out += "\",\"mock\":";
    out += r.mock ? "true" : "false";
    out += ",\"source\":\"";
    out += json_escape(r.source);
    out += "\",\"e2e_us\":";
    std::snprintf(num, sizeof(num), "%.3f", r.e2e_us);
    out += num;
    out += ",\"preprocess_us\":";
    std::snprintf(num, sizeof(num), "%.3f", r.preprocess_us);
    out += num;
    out += ",\"classify_us\":";
    std::snprintf(num, sizeof(num), "%.3f", r.classify_us);
    out += num;
    out += ",\"overflow\":";
    out += r.overflow ? "true" : "false";
    out += ",\"dropped\":";
    out += r.dropped ? "true" : "false";
    out += ",\"discontinuity\":";
    out += r.discontinuity ? "true" : "false";
    out += ",\"short_frame\":";
    out += r.short_frame ? "true" : "false";
    out += '}';
    return out;
}

// UI v3 result record (task 39e5 UI v3 M4).  Same as result_frame_v2_line() plus
// the M1/M2/M3 runtime state: signal-presence state, auto-level mode/scale/gain,
// and the M3 DSP measurements (nested object).  Schema tag is "12class-chain-v2";
// result_frame_v2_line() (schema "12class-chain-v1") is unchanged and remains the
// backward-compatible record.
inline std::string result_frame_v3_line(const rf::ResultFrame& r) {
    std::string out = "{\"type\":\"result\",\"version\":\"";
    out += json_escape(r.version.empty() ? "12class-chain-v2" : r.version);
    out += "\",\"frame_id\":";
    out += std::to_string(r.frame_id);
    out += ",\"timestamp_us\":";
    out += std::to_string(r.timestamp_us);
    out += ",\"argmax_idx\":";
    out += std::to_string(r.argmax_idx);
    out += ",\"argmax_class\":\"";
    out += json_escape(r.argmax_class);
    out += "\",\"confidence\":";
    char num[64];
    std::snprintf(num, sizeof(num), "%.6f", static_cast<double>(r.confidence));
    out += num;
    out += ",\"class_count\":";
    out += std::to_string(r.class_count);
    out += ",\"probabilities\":[";
    for (std::size_t i = 0; i < r.probabilities.size(); ++i) {
        if (i) out += ',';
        std::snprintf(num, sizeof(num), "%.6f",
                      static_cast<double>(r.probabilities[i]));
        out += num;
    }
    out += "],\"snr_db\":";
    if (std::isnan(r.snr_db)) out += "null";
    else { std::snprintf(num, sizeof(num), "%.3f", r.snr_db); out += num; }
    out += ",\"quality\":";
    std::snprintf(num, sizeof(num), "%.6f", r.quality);
    out += num;
    out += ",\"model_sha\":\"";
    out += json_escape(r.model_sha);
    out += "\",\"mock\":";
    out += r.mock ? "true" : "false";
    out += ",\"source\":\"";
    out += json_escape(r.source);
    out += "\",\"e2e_us\":";
    std::snprintf(num, sizeof(num), "%.3f", r.e2e_us);
    out += num;
    out += ",\"preprocess_us\":";
    std::snprintf(num, sizeof(num), "%.3f", r.preprocess_us);
    out += num;
    out += ",\"classify_us\":";
    std::snprintf(num, sizeof(num), "%.3f", r.classify_us);
    out += num;
    out += ",\"overflow\":";
    out += r.overflow ? "true" : "false";
    out += ",\"dropped\":";
    out += r.dropped ? "true" : "false";
    out += ",\"discontinuity\":";
    out += r.discontinuity ? "true" : "false";
    out += ",\"short_frame\":";
    out += r.short_frame ? "true" : "false";
    // --- UI v3 runtime state ---
    out += ",\"presence_state\":\"";
    out += json_escape(r.presence_state);
    out += "\",\"level_mode\":\"";
    out += json_escape(r.level_mode);
    out += "\",\"model_scale\":";
    std::snprintf(num, sizeof(num), "%.6f", r.model_scale);
    out += num;
    out += ",\"rf_gain_db\":";
    std::snprintf(num, sizeof(num), "%.3f", r.rf_gain_db);
    out += num;
    // --- M6 work mode + run state (producer-owned) ---
    out += ",\"work_mode\":\"";
    out += json_escape(r.work_mode);
    out += "\",\"run_state\":\"";
    out += json_escape(r.run_state);
    out += '"';
    // --- M3 measurements (nested object) ---
    out += ",\"measurements\":";
    if (!r.has_measurements) {
        out += "null";
    } else {
        const sdr::FrameMeasurements& m = r.measurements;
        out += "{\"rms_counts\":";
        std::snprintf(num, sizeof(num), "%.6f", m.rms_counts); out += num;
        out += ",\"peak_counts\":";
        std::snprintf(num, sizeof(num), "%.6f", m.peak_counts); out += num;
        out += ",\"papr_db\":";
        std::snprintf(num, sizeof(num), "%.6f", m.papr_db); out += num;
        out += ",\"clip_ratio\":";
        std::snprintf(num, sizeof(num), "%.6f", m.clip_ratio); out += num;
        out += ",\"power_dbfs\":";
        std::snprintf(num, sizeof(num), "%.3f", m.power_dbfs); out += num;
        out += ",\"noise_floor_dbfs\":";
        std::snprintf(num, sizeof(num), "%.3f", m.noise_floor_dbfs); out += num;
        out += ",\"psd_peak_prominence_db\":";
        std::snprintf(num, sizeof(num), "%.3f", m.psd_peak_prominence_db); out += num;
        out += ",\"snr_est_db\":";
        std::snprintf(num, sizeof(num), "%.3f", m.snr_est_db); out += num;
        out += ",\"occupied_bins\":";
        out += std::to_string(m.occupied_bins);
        out += ",\"spectral_centroid_hz\":";
        std::snprintf(num, sizeof(num), "%.3f", m.spectral_centroid_hz); out += num;
        out += ",\"occupied_bw_hz\":";
        std::snprintf(num, sizeof(num), "%.3f", m.occupied_bw_hz); out += num;
        out += ",\"model_rms\":";
        std::snprintf(num, sizeof(num), "%.6f", m.model_rms); out += num;
        out += '}';
    }
    out += '}';
    return out;
}

// Sink abstraction: where JSON-lines records go.  The pipeline / offline chain
// writes to a Sink, so the same chain can target stdout (StdoutSink) or a Unix
// socket (unix_socket_sink.hpp) without change.
class Sink {
public:
    virtual ~Sink() = default;
    virtual void write(const std::string& json_line) = 0;
};

// Writes one JSON record per line to stdout (flushed immediately).
class StdoutSink : public Sink {
public:
    void write(const std::string& json_line) override {
        std::fputs(json_line.c_str(), stdout);
        std::fputc('\n', stdout);
        std::fflush(stdout);
    }
};

}  // namespace ui
