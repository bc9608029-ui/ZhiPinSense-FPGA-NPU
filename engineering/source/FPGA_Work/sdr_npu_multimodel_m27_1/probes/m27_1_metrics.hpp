#pragma once
// m27_1_metrics.hpp — pure, SDK-free measurement/result helpers for M27.1.
//
// This header intentionally does NOT include any iCraft header: it holds the
// latency statistics, argmax, finite-check and the result-JSON emitter that the
// board probes and the offline host unit tests share.  Keeping it SDK-free lets
// the host tests compile and run without the ZG330 runtime.
//
// Board probes include this via probe_common.hpp; host tests include it directly.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace m27_1 {

// ---- time ---------------------------------------------------------------
inline double now_us() {
    // Monotonic microseconds.  Same facility the production chain uses
    // (npu_classifier.hpp elapsed_us), portable across board and host.
    return std::chrono::duration<double, std::micro>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}
inline double elapsed_us(double t0) { return now_us() - t0; }

// ---- latency statistics --------------------------------------------------
struct LatencyStats {
    std::uint64_t count = 0;
    double sum = 0.0;
    double max = 0.0;
    std::vector<double> samples;  // filled during sampling, used for p99

    void add(double us) {
        ++count;
        sum += us;
        if (us > max) max = us;
        samples.push_back(us);
    }
    double mean() const { return count ? (sum / static_cast<double>(count)) : 0.0; }
    double p99() const {
        if (samples.empty()) return 0.0;
        std::vector<double> s = samples;
        std::sort(s.begin(), s.end());
        std::size_t idx = static_cast<std::size_t>(std::ceil(0.99 * s.size()));
        if (idx == 0) idx = 1;
        if (idx > s.size()) idx = s.size();
        return s[idx - 1];
    }
};

// ---- numeric helpers ------------------------------------------------------
inline int argmax(const float* v, std::size_t n) {
    if (n == 0 || v == nullptr) return -1;
    int best = 0;
    for (std::size_t i = 1; i < n; ++i)
        if (v[i] > v[best]) best = static_cast<int>(i);
    return best;
}

inline bool all_finite(const float* v, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i)
        if (!std::isfinite(v[i])) return false;
    return true;
}

// ---- minimal JSON emitter ------------------------------------------------
class Json {
    std::string s_;
    bool first_ = true;
    void comma() { if (!first_) s_ += ','; first_ = false; }
    static void esc(std::string& o, const std::string& in) {
        for (char c : in) {
            switch (c) {
                case '"':  o += "\\\""; break;
                case '\\': o += "\\\\"; break;
                case '\n': o += "\\n"; break;
                case '\r': o += "\\r"; break;
                case '\t': o += "\\t"; break;
                default:   o += c;
            }
        }
    }
public:
    Json& str(const char* key, const std::string& v) {
        comma(); s_ += '\"'; esc(s_, key); s_ += "\":\""; esc(s_, v); s_ += '\"'; return *this;
    }
    Json& num(const char* key, double v) {
        comma(); char b[64]; std::snprintf(b, sizeof b, "%.6f", v);
        s_ += '\"'; esc(s_, key); s_ += "\":"; s_ += b; return *this;
    }
    Json& integer(const char* key, std::int64_t v) {
        comma(); char b[32]; std::snprintf(b, sizeof b, "%lld", (long long)v);
        s_ += '\"'; esc(s_, key); s_ += "\":"; s_ += b; return *this;
    }
    Json& boolean(const char* key, bool v) {
        comma(); s_ += '\"'; esc(s_, key); s_ += (v ? "\":true" : "\":false"); return *this;
    }
    std::string done() const { return "{" + s_ + "}\n"; }
};

// ---- per-probe result record ---------------------------------------------
struct ProbeResult {
    std::string probe = "";
    std::string status = "SKIP";          // PASS | FAIL | SKIP
    std::string conclusion = "";          // one of A..E markers, set by aggregator only

    // one-time bring-up timings (us)
    double device_open_us = -1.0;
    double model_load_a_us = -1.0;
    double model_load_b_us = -1.0;
    double session_apply_a_us = -1.0;
    double session_apply_b_us = -1.0;

    // forward timings (us)
    LatencyStats fwd_a;
    LatencyStats fwd_b;
    double switch_us = -1.0;

    // throughput (fps), only for concurrent probe
    double serial_throughput_fps = -1.0;
    double concurrent_throughput_fps = -1.0;

    // correctness / stability
    bool correctness_pass = false;
    bool repeatability_pass = false;
    std::uint64_t error_count = 0;
    std::uint64_t timeout_count = 0;
    std::string return_codes = "";        // comma-separated hex return codes

    // resource (unknown -> -1)
    std::int64_t mem_etm_used_bytes = -1;
    std::int64_t mem_ocm_used_bytes = -1;
    double cpu_usage_percent = -1.0;

    std::string notes = "";

    std::string to_json() const {
        Json j;
        j.str("probe", probe);
        j.str("status", status);
        j.str("conclusion", conclusion);
        j.num("device_open_us", device_open_us);
        j.num("model_load_a_us", model_load_a_us);
        j.num("model_load_b_us", model_load_b_us);
        j.num("session_apply_a_us", session_apply_a_us);
        j.num("session_apply_b_us", session_apply_b_us);
        j.num("forward_a_mean_us", fwd_a.mean());
        j.num("forward_a_max_us", fwd_a.max);
        j.num("forward_a_p99_us", fwd_a.p99());
        j.num("forward_b_mean_us", fwd_b.mean());
        j.num("forward_b_max_us", fwd_b.max);
        j.num("forward_b_p99_us", fwd_b.p99());
        j.num("switch_us", switch_us);
        j.num("serial_throughput_fps", serial_throughput_fps);
        j.num("concurrent_throughput_fps", concurrent_throughput_fps);
        j.boolean("correctness_pass", correctness_pass);
        j.boolean("repeatability_pass", repeatability_pass);
        j.integer("error_count", static_cast<std::int64_t>(error_count));
        j.integer("timeout_count", static_cast<std::int64_t>(timeout_count));
        j.str("return_codes", return_codes);
        j.integer("mem_etm_used_bytes", mem_etm_used_bytes);
        j.integer("mem_ocm_used_bytes", mem_ocm_used_bytes);
        j.num("cpu_usage_percent", cpu_usage_percent);
        j.str("notes", notes);
        return j.done();
    }
};

// Emit the one-line tail marker the board one-click script greps for.
inline void emit_tail(const std::string& status, const std::string& json_path) {
    std::printf("PROBE_RESULT=%s JSON=%s\n", status.c_str(), json_path.c_str());
}

}  // namespace m27_1
