#pragma once
// latency_diag.hpp — pure-logic latency diagnostics for the FPGA<->NPU joint
// stress program.  This module contains NO iCraft dependency and NO timing I/O:
// the caller measures each phase with std::chrono::steady_clock and feeds the
// results here for per-phase statistics, RSS parsing, index mapping, resource
// counters, spike detection and verdict logic.  Because it is pure, the same
// header is compiled both on the board and in the host unit tests
// (host_tests/test_latency_diag.cpp).
//
// C++17.  -Wall -Wextra -Werror clean.

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <string>
#include <utility>
#include <vector>

namespace latency_diag {

// Per-frame phase timings in milliseconds (measured by the caller with
// std::chrono::steady_clock), plus the (cycle, frame) coordinate of the frame
// so a slow frame can be traced back to its exact location in the run.
// forward_legacy_ms() reproduces the pre-split single forward_ms number
// (submit + wait + to_host + read) so the new output stays comparable with the
// board logs (forward=425/604/937 ms).
struct FrameTiming {
    int cycle = 0;
    int frame = 0;
    double dequantize_ms = 0.0;
    double input_prepare_ms = 0.0;
    double reset_ms = 0.0;
    double forward_submit_ms = 0.0;
    double wait_ready_ms = 0.0;
    double output_to_host_ms = 0.0;
    double output_read_ms = 0.0;
    double total_ms = 0.0;

    double forward_legacy_ms() const {
        return forward_submit_ms + wait_ready_ms + output_to_host_ms + output_read_ms;
    }
};

// Aggregated statistics over one phase's per-frame samples.
struct PercentileStats {
    std::size_t count = 0;
    double min_ms = 0.0;
    double max_ms = 0.0;
    double p50_ms = 0.0;
    double p95_ms = 0.0;
    double p99_ms = 0.0;
    std::size_t gt_5ms = 0;
    std::size_t gt_10ms = 0;
    std::size_t gt_100ms = 0;
};

// Per-phase statistics across the whole run.  Nine phases, each reported
// independently: reset, dequantize, input_prepare, forward_submit, wait_ready,
// output_to_host, output_read, forward_legacy, total_inference.
struct PhaseStats {
    PercentileStats reset;
    PercentileStats dequantize;
    PercentileStats input_prepare;
    PercentileStats forward_submit;
    PercentileStats wait_ready;
    PercentileStats output_to_host;
    PercentileStats output_read;
    PercentileStats forward_legacy;
    PercentileStats total_inference;
};

// Resource allocation counters (the suspected hot-path allocations).
struct ResourceCounters {
    std::size_t input_allocations = 0;        // input Tensor mallocOn() calls
    std::size_t output_host_conversions = 0;  // output Tensor to(host) calls
};

// A frame coordinate (cycle, frame).  Used both to map a 0-based global
// inference index back to its coordinate (frame_of) and to record the location
// of a detected slow frame (detect_spikes).
struct FrameKey {
    int cycle = 0;
    int frame = 0;
};

// Hard latency gate on a phase's statistics.  The four conditions mirror the
// board gate exactly; pass() requires all four.
struct LatencyGate {
    bool gt_100ms_zero = false;  // no frame exceeded 100 ms
    bool p99_within = false;     // p99 <= p99_limit_ms
    bool max_within = false;     // max <= max_limit_ms
    bool gt_10ms_zero = false;   // no frame exceeded 10 ms

    bool pass() const {
        return gt_100ms_zero && p99_within && max_within && gt_10ms_zero;
    }
};

// Resource gate for the fixed build.  pass() requires all three.
struct ResourceGate {
    bool input_allocations_ok = false;  // input_allocations == expected
    bool cycles_complete = false;       // completed_cycles == expected_cycles
    bool frames_recorded_ok = false;    // recorded frames == expected_frames

    bool pass() const {
        return input_allocations_ok && cycles_complete && frames_recorded_ok;
    }
};

// Spike detection result: whether any frame's forward_legacy exceeded the
// threshold, plus the (cycle, frame) coordinate of every slow frame.
struct SpikeDetection {
    bool reproduced = false;
    std::vector<FrameKey> slow_frames;
};

// Nearest-rank percentile over a SORTED sample vector.  rank = ceil(pct/100*n),
// 1-indexed; an empty vector yields 0.0.
inline double percentile_rank(const std::vector<double>& sorted, double pct) {
    if (sorted.empty()) return 0.0;
    const double n = static_cast<double>(sorted.size());
    std::size_t rank = static_cast<std::size_t>(std::ceil(pct / 100.0 * n));
    if (rank < 1) rank = 1;
    if (rank > sorted.size()) rank = sorted.size();
    return sorted[rank - 1];
}

// Compute count/min/max/p50/p95/p99 and the gt_5/10/100ms counters.
inline PercentileStats compute_stats(const std::vector<double>& samples_ms) {
    PercentileStats st;
    st.count = samples_ms.size();
    if (samples_ms.empty()) return st;

    std::vector<double> s = samples_ms;
    std::sort(s.begin(), s.end());
    st.min_ms = s.front();
    st.max_ms = s.back();
    st.p50_ms = percentile_rank(s, 50.0);
    st.p95_ms = percentile_rank(s, 95.0);
    st.p99_ms = percentile_rank(s, 99.0);
    for (double x : samples_ms) {
        if (x > 5.0) ++st.gt_5ms;
        if (x > 10.0) ++st.gt_10ms;
        if (x > 100.0) ++st.gt_100ms;
    }
    return st;
}

// Collect the per-phase sample series and reduce each to its statistics.
inline PhaseStats compute_phase_stats(const std::vector<FrameTiming>& frames) {
    std::vector<double> deq, input, reset, submit, wait, to_host, read, legacy, total;
    deq.reserve(frames.size());
    input.reserve(frames.size());
    reset.reserve(frames.size());
    submit.reserve(frames.size());
    wait.reserve(frames.size());
    to_host.reserve(frames.size());
    read.reserve(frames.size());
    legacy.reserve(frames.size());
    total.reserve(frames.size());
    for (const auto& f : frames) {
        deq.push_back(f.dequantize_ms);
        input.push_back(f.input_prepare_ms);
        reset.push_back(f.reset_ms);
        submit.push_back(f.forward_submit_ms);
        wait.push_back(f.wait_ready_ms);
        to_host.push_back(f.output_to_host_ms);
        read.push_back(f.output_read_ms);
        legacy.push_back(f.forward_legacy_ms());
        total.push_back(f.total_ms);
    }

    PhaseStats ps;
    ps.dequantize = compute_stats(deq);
    ps.input_prepare = compute_stats(input);
    ps.reset = compute_stats(reset);
    ps.forward_submit = compute_stats(submit);
    ps.wait_ready = compute_stats(wait);
    ps.output_to_host = compute_stats(to_host);
    ps.output_read = compute_stats(read);
    ps.forward_legacy = compute_stats(legacy);
    ps.total_inference = compute_stats(total);
    return ps;
}

// Parse the "VmRSS:" line of /proc/self/status ("VmRSS:   12345 kB") and return
// the value in kB.  Returns -1 when the key is absent or malformed.
inline long long parse_vm_rss_kb(const std::string& status_text) {
    const std::string key = "VmRSS:";
    const std::size_t pos = status_text.find(key);
    if (pos == std::string::npos) return -1;
    const char* p = status_text.c_str() + pos + key.size();
    while (*p == ' ' || *p == '\t') ++p;
    if (*p < '0' || *p > '9') return -1;
    long long val = 0;
    while (*p >= '0' && *p <= '9') {
        val = val * 10 + (*p - '0');
        ++p;
    }
    return val;
}

// Map a 0-based global inference index to (cycle, frame).  Each cycle holds
// `frames_per_cycle` NPU frames whose frame numbers start at `first_frame`.
// Defensive: a non-positive frames_per_cycle collapses to (0, first_frame).
inline FrameKey frame_of(std::size_t global_index, int frames_per_cycle, int first_frame) {
    FrameKey k;
    if (frames_per_cycle <= 0) {
        k.cycle = 0;
        k.frame = first_frame;
        return k;
    }
    const auto fpc = static_cast<std::size_t>(frames_per_cycle);
    k.cycle = static_cast<int>(global_index / fpc);
    k.frame = first_frame + static_cast<int>(global_index % fpc);
    return k;
}

// Evaluate the hard latency gate on a phase's statistics.
inline LatencyGate evaluate_latency(const PercentileStats& st,
                                    double p99_limit_ms,
                                    double max_limit_ms) {
    LatencyGate g;
    g.gt_100ms_zero = (st.gt_100ms == 0);
    g.p99_within = (st.p99_ms <= p99_limit_ms);
    g.max_within = (st.max_ms <= max_limit_ms);
    g.gt_10ms_zero = (st.gt_10ms == 0);
    return g;
}

// Evaluate the resource gate for the fixed build.
inline ResourceGate evaluate_resource(std::size_t input_allocations,
                                      std::size_t expected_input_allocations,
                                      int completed_cycles,
                                      int expected_cycles,
                                      std::size_t frames_recorded,
                                      std::size_t expected_frames) {
    ResourceGate g;
    g.input_allocations_ok = (input_allocations == expected_input_allocations);
    g.cycles_complete = (completed_cycles == expected_cycles);
    g.frames_recorded_ok = (frames_recorded == expected_frames);
    return g;
}

// Detect whether any frame's forward_legacy exceeded spike_threshold_ms.
// Reproducing the board spike requires at least one such frame.
inline SpikeDetection detect_spikes(const std::vector<FrameTiming>& frames,
                                    double spike_threshold_ms) {
    SpikeDetection d;
    for (const auto& f : frames) {
        if (f.forward_legacy_ms() > spike_threshold_ms) {
            d.reproduced = true;
            FrameKey k;
            k.cycle = f.cycle;
            k.frame = f.frame;
            d.slow_frames.push_back(k);
        }
    }
    return d;
}

}  // namespace latency_diag
