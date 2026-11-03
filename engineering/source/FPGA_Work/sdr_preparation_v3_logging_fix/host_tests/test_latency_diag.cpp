// Host-side unit tests for latency_diag.hpp (pure logic, no iCraft dependency).
//
// These tests verify ONLY the pure statistics / parsing / mapping / verdict
// logic.  They do NOT prove the NPU latency spike is fixed — that requires the
// on-board baseline_diag + fixed runs.  Compile with WSL g++:
//
//   g++ -std=c++17 -O2 -Wall -Wextra -Werror -I../board_package test_latency_diag.cpp -o test_latency_diag
//   ./test_latency_diag
//
// A non-zero exit means a test failed.

#include "latency_diag.hpp"

#include <cmath>
#include <cstdio>
#include <iostream>
#include <string>
#include <vector>

namespace {
int failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        ++failures;
        std::printf("FAIL: %s\n", what);
    }
}

bool near(double a, double b, double eps) { return std::fabs(a - b) <= eps; }
}  // namespace

int main() {
    using namespace latency_diag;

    // ---- percentile_rank: nearest-rank, 1-indexed ----
    {
        const std::vector<double> s = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0};
        check(near(percentile_rank(s, 50.0), 5.0, 1e-9), "p50 of 1..10 == 5");
        check(near(percentile_rank(s, 100.0), 10.0, 1e-9), "p100 == 10");
        check(near(percentile_rank(s, 0.0), 1.0, 1e-9), "p0 clamps to rank 1 -> 1");
        check(near(percentile_rank(s, 95.0), 10.0, 1e-9), "p95 of 1..10 == 10 (rank ceil(9.5)=10)");
        check(near(percentile_rank(s, 99.0), 10.0, 1e-9), "p99 of 1..10 == 10");
    }

    // ---- percentile_rank: empty vector -> 0 ----
    {
        const std::vector<double> empty;
        check(near(percentile_rank(empty, 50.0), 0.0, 1e-9), "p50 of empty == 0");
    }

    // ---- percentile_rank: single element ----
    {
        const std::vector<double> one = {42.0};
        check(near(percentile_rank(one, 50.0), 42.0, 1e-9), "p50 of single == 42");
    }

    // ---- compute_stats: empty ----
    {
        const PercentileStats st = compute_stats({});
        check(st.count == 0, "empty stats count == 0");
        check(st.max_ms == 0.0 && st.p50_ms == 0.0, "empty stats zero");
        check(st.gt_5ms == 0 && st.gt_10ms == 0 && st.gt_100ms == 0, "empty stats counters 0");
    }

    // ---- compute_stats: known distribution ----
    {
        // 1,2,3,4,5,6,7,8,9,10 ms -> p50=5, p95=10, p99=10, max=10, min=1.
        const PercentileStats st = compute_stats({10, 1, 5, 3, 9, 2, 8, 4, 7, 6});
        check(st.count == 10, "stats count == 10");
        check(near(st.min_ms, 1.0, 1e-9), "min == 1");
        check(near(st.max_ms, 10.0, 1e-9), "max == 10");
        check(near(st.p50_ms, 5.0, 1e-9), "p50 == 5");
        check(near(st.p95_ms, 10.0, 1e-9), "p95 == 10");
        check(near(st.p99_ms, 10.0, 1e-9), "p99 == 10");
        check(st.gt_5ms == 5, "gt_5ms == 5 (6..10)");
        check(st.gt_10ms == 0, "gt_10ms == 0");
        check(st.gt_100ms == 0, "gt_100ms == 0");
    }

    // ---- compute_stats: spike counters ----
    {
        // Three samples: 0.5, 120.0, 6.0 -> gt_5=2, gt_10=1, gt_100=1.
        const PercentileStats st = compute_stats({0.5, 120.0, 6.0});
        check(st.gt_5ms == 2, "gt_5ms == 2");
        check(st.gt_10ms == 1, "gt_10ms == 1");
        check(st.gt_100ms == 1, "gt_100ms == 1");
        check(near(st.max_ms, 120.0, 1e-9), "max == 120");
    }

    // ---- FrameTiming::forward_legacy_ms sums the four forward phases ----
    {
        FrameTiming ft;
        ft.forward_submit_ms = 0.5;
        ft.wait_ready_ms = 120.0;
        ft.output_to_host_ms = 0.25;
        ft.output_read_ms = 0.25;
        check(near(ft.forward_legacy_ms(), 121.0, 1e-9), "forward_legacy == submit+wait+to_host+read");
    }

    // ---- compute_phase_stats: nine independent phase reductions ----
    {
        std::vector<FrameTiming> frames;
        for (int i = 0; i < 10; ++i) {
            FrameTiming f;
            f.dequantize_ms = 1.0 + i;      // 1..10
            f.input_prepare_ms = 0.5;       // constant
            f.reset_ms = 2.0;               // constant
            f.forward_submit_ms = 0.1;      // constant
            f.wait_ready_ms = 100.0;        // every frame spikes in wait
            f.output_to_host_ms = 0.2;
            f.output_read_ms = 0.3;
            f.total_ms = 104.0 + i;         // 104..113
            frames.push_back(f);
        }
        const PhaseStats ps = compute_phase_stats(frames);
        check(ps.dequantize.count == 10, "phase dequantize count 10");
        check(near(ps.dequantize.max_ms, 10.0, 1e-9), "phase dequantize max 10");
        check(ps.input_prepare.count == 10, "phase input_prepare count 10");
        check(near(ps.input_prepare.max_ms, 0.5, 1e-9), "phase input_prepare max 0.5");
        check(ps.wait_ready.count == 10, "phase wait_ready count 10");
        check(near(ps.wait_ready.max_ms, 100.0, 1e-9), "phase wait_ready max 100");
        check(ps.wait_ready.gt_100ms == 0, "wait_ready 100.0 is not >100");
        // forward_legacy = 0.1 + 100 + 0.2 + 0.3 = 100.6
        check(near(ps.forward_legacy.max_ms, 100.6, 1e-9), "forward_legacy max 100.6");
        check(ps.total_inference.count == 10, "total_inference count 10");
        check(near(ps.total_inference.max_ms, 113.0, 1e-9), "total_inference max 113");
    }

    // ---- parse_vm_rss_kb ----
    {
        const std::string status =
            "Name:\ttest\n"
            "VmRSS:\t   12345 kB\n"
            "VmSize:\t  999999 kB\n";
        check(parse_vm_rss_kb(status) == 12345, "parse VmRSS 12345");
        check(parse_vm_rss_kb("VmRSS:    0 kB\n") == 0, "parse VmRSS 0");
        check(parse_vm_rss_kb("NoVmRSSHere\n") == -1, "absent VmRSS -> -1");
        check(parse_vm_rss_kb("VmRSS:    \n") == -1, "malformed VmRSS -> -1");
    }

    // ---- frame_of: index -> (cycle, frame) ----
    {
        // 12 frames/cycle starting at frame 7: cycle 0 = frames 7..18.
        const FrameKey k0 = frame_of(0, 12, 7);
        check(k0.cycle == 0 && k0.frame == 7, "index 0 -> cycle0 frame7");
        const FrameKey k11 = frame_of(11, 12, 7);
        check(k11.cycle == 0 && k11.frame == 18, "index 11 -> cycle0 frame18");
        const FrameKey k12 = frame_of(12, 12, 7);
        check(k12.cycle == 1 && k12.frame == 7, "index 12 -> cycle1 frame7");
        const FrameKey k72 = frame_of(72, 12, 7);
        check(k72.cycle == 6 && k72.frame == 7, "index 72 -> cycle6 frame7");
        // Defensive: non-positive frames_per_cycle collapses.
        const FrameKey bad = frame_of(5, 0, 7);
        check(bad.cycle == 0 && bad.frame == 7, "frame_of fpc<=0 -> cycle0 frame7");
    }

    // ---- evaluate_latency: clean run passes all four conditions ----
    {
        PercentileStats ok;
        ok.p99_ms = 2.0; ok.max_ms = 4.0; ok.gt_10ms = 0; ok.gt_100ms = 0;
        const LatencyGate g = evaluate_latency(ok, 5.0, 10.0);
        check(g.gt_100ms_zero, "clean gt_100ms_zero");
        check(g.p99_within, "clean p99_within");
        check(g.max_within, "clean max_within");
        check(g.gt_10ms_zero, "clean gt_10ms_zero");
        check(g.pass(), "clean latency gate passes");
    }

    // ---- evaluate_latency: each of the four conditions can fail independently ----
    {
        PercentileStats spk;  // a >100ms spike present
        spk.p99_ms = 2.0; spk.max_ms = 500.0; spk.gt_10ms = 1; spk.gt_100ms = 1;
        const LatencyGate g = evaluate_latency(spk, 5.0, 10.0);
        check(!g.gt_100ms_zero, "gt_100ms>0 -> gt_100ms_zero false");
        check(!g.pass(), "spike -> latency gate fails");

        PercentileStats slow;  // no spike, but p99 over budget
        slow.p99_ms = 6.0; slow.max_ms = 8.0; slow.gt_10ms = 0; slow.gt_100ms = 0;
        const LatencyGate g2 = evaluate_latency(slow, 5.0, 10.0);
        check(g2.gt_100ms_zero, "slow gt_100ms_zero true");
        check(!g2.p99_within, "p99>5 -> p99_within false");
        check(!g2.pass(), "p99 over -> latency gate fails");

        PercentileStats overmax;  // p99 fine but max over 10
        overmax.p99_ms = 3.0; overmax.max_ms = 12.0; overmax.gt_10ms = 0; overmax.gt_100ms = 0;
        const LatencyGate g3 = evaluate_latency(overmax, 5.0, 10.0);
        check(!g3.max_within, "max>10 -> max_within false");
        check(!g3.pass(), "max over -> latency gate fails");

        PercentileStats gt10;  // some frame between 10 and 100 ms
        gt10.p99_ms = 2.0; gt10.max_ms = 50.0; gt10.gt_10ms = 1; gt10.gt_100ms = 0;
        const LatencyGate g4 = evaluate_latency(gt10, 5.0, 10.0);
        check(g4.max_within == false, "max 50>10 -> max_within false");
        check(!g4.gt_10ms_zero, "gt_10ms>0 -> gt_10ms_zero false");
        check(!g4.pass(), "gt_10ms>0 -> latency gate fails");
    }

    // ---- evaluate_latency: exact 5ms / 10ms / 100ms boundaries ----
    {
        // p99 == 5.0 and max == 10.0 are within (<=); the gate passes.
        PercentileStats edge;
        edge.p99_ms = 5.0; edge.max_ms = 10.0; edge.gt_10ms = 0; edge.gt_100ms = 0;
        const LatencyGate ge = evaluate_latency(edge, 5.0, 10.0);
        check(ge.p99_within, "p99==5.0 is within");
        check(ge.max_within, "max==10.0 is within");
        check(ge.pass(), "exact-boundary latency gate passes");

        // p99 just over 5ms fails.
        PercentileStats p99over;
        p99over.p99_ms = 5.0001; p99over.max_ms = 10.0; p99over.gt_10ms = 0; p99over.gt_100ms = 0;
        check(!evaluate_latency(p99over, 5.0, 10.0).p99_within, "p99==5.0001 not within");

        // max just over 10ms fails.
        PercentileStats maxover;
        maxover.p99_ms = 5.0; maxover.max_ms = 10.0001; maxover.gt_10ms = 0; maxover.gt_100ms = 0;
        check(!evaluate_latency(maxover, 5.0, 10.0).max_within, "max==10.0001 not within");
    }

    // ---- compute_stats: gt thresholds are strict (>, not >=) at 10ms/100ms ----
    {
        const PercentileStats at100 = compute_stats({100.0, 1.0});
        check(at100.gt_100ms == 0, "sample==100.0 is not >100");
        const PercentileStats over100 = compute_stats({100.0001, 1.0});
        check(over100.gt_100ms == 1, "sample==100.0001 is >100");

        const PercentileStats at10 = compute_stats({10.0, 1.0});
        check(at10.gt_10ms == 0, "sample==10.0 is not >10");
        const PercentileStats over10 = compute_stats({10.0001, 1.0});
        check(over10.gt_10ms == 1, "sample==10.0001 is >10");
    }

    // ---- evaluate_resource: all three conditions ----
    {
        const ResourceGate ok = evaluate_resource(/*input_allocations=*/2, 2,
                                                  /*completed_cycles=*/100, 100,
                                                  /*frames_recorded=*/1200, 1200);
        check(ok.input_allocations_ok, "input_allocations==2 ok");
        check(ok.cycles_complete, "cycles complete");
        check(ok.frames_recorded_ok, "frames recorded ok");
        check(ok.pass(), "resource gate passes");

        // input_allocations != 2
        const ResourceGate bad_alloc = evaluate_resource(/*input_allocations=*/2400, 2,
                                                         100, 100, 1200, 1200);
        check(!bad_alloc.input_allocations_ok, "input_allocations!=2 fails");
        check(!bad_alloc.pass(), "input_allocations!=2 -> resource gate fails");

        // Incomplete cycles (completed < expected)
        const ResourceGate bad_cycles = evaluate_resource(2, 2,
                                                          /*completed_cycles=*/99, 100, 1188, 1200);
        check(!bad_cycles.cycles_complete, "completed_cycles!=expected fails");
        check(!bad_cycles.pass(), "incomplete cycles -> resource gate fails");

        // frames_recorded mismatch (a frame errored out and was not recorded)
        const ResourceGate bad_frames = evaluate_resource(2, 2, 100, 100,
                                                          /*frames_recorded=*/1199, 1200);
        check(!bad_frames.frames_recorded_ok, "frames_recorded!=expected fails");
        check(!bad_frames.pass(), "frames mismatch -> resource gate fails");
    }

    // ---- detect_spikes: slow-frame reproduction + coordinates ----
    {
        std::vector<FrameTiming> frames;
        for (int c = 0; c < 3; ++c) {
            for (int f = 7; f <= 18; ++f) {
                FrameTiming t;
                t.cycle = c;
                t.frame = f;
                // Reproduce the board pattern: frame 7 spikes every cycle.
                if (f == 7) {
                    t.forward_submit_ms = 0.5;
                    t.wait_ready_ms = 500.0;  // >100ms -> slow frame
                } else {
                    t.forward_submit_ms = 0.5;
                    t.wait_ready_ms = 0.5;    // ~1.25ms total, not slow
                }
                frames.push_back(t);
            }
        }
        const SpikeDetection d = detect_spikes(frames, 100.0);
        check(d.reproduced, "spike reproduced");
        check(d.slow_frames.size() == 3, "three slow frames (frame 7 x 3 cycles)");
        if (d.slow_frames.size() == 3) {
            check(d.slow_frames[0].cycle == 0 && d.slow_frames[0].frame == 7, "slow frame 0 -> cycle0 frame7");
            check(d.slow_frames[1].cycle == 1 && d.slow_frames[1].frame == 7, "slow frame 1 -> cycle1 frame7");
            check(d.slow_frames[2].cycle == 2 && d.slow_frames[2].frame == 7, "slow frame 2 -> cycle2 frame7");
        }

        // No slow frame -> reproduced == false.
        std::vector<FrameTiming> fast;
        for (int i = 0; i < 5; ++i) {
            FrameTiming t;
            t.cycle = 0;
            t.frame = 7 + i;
            t.wait_ready_ms = 0.5;
            fast.push_back(t);
        }
        const SpikeDetection dn = detect_spikes(fast, 100.0);
        check(!dn.reproduced, "no spike -> not reproduced");
        check(dn.slow_frames.empty(), "no slow frames");

        // Exactly 100ms is NOT a spike (strict >).
        std::vector<FrameTiming> at_threshold;
        FrameTiming t100;
        t100.cycle = 0;
        t100.frame = 7;
        t100.wait_ready_ms = 100.0;  // forward_legacy == 100.0, not >100
        at_threshold.push_back(t100);
        check(!detect_spikes(at_threshold, 100.0).reproduced, "forward_legacy==100.0 is not a spike");
    }

    // ---- baseline_final_pass: correctness AND latency; spike flag is NOT consulted ----
    {
        // The falsified old gate: no spike but good latency must PASS now.
        PercentileStats good;
        good.p99_ms = 0.8; good.max_ms = 1.2; good.gt_10ms = 0; good.gt_100ms = 0;
        const LatencyGate g = evaluate_latency(good, 5.0, 10.0);
        // A spike-reproduced flag of "NO" (the normal non-intrusive result) does
        // not affect the verdict: correctness=true && latency=PASS -> PASS.
        check(baseline_final_pass(true, g), "baseline no-spike + good latency passes");
        // correctness=false -> FAIL regardless of latency.
        check(!baseline_final_pass(false, g), "baseline correctness=false fails");
        // latency gate FAIL -> FAIL even with correctness=true.
        PercentileStats bad;
        bad.p99_ms = 640.0; bad.max_ms = 978.0; bad.gt_10ms = 1; bad.gt_100ms = 1;
        check(!baseline_final_pass(true, evaluate_latency(bad, 5.0, 10.0)),
              "baseline latency gate fail -> fails");
    }

    if (failures == 0) {
        std::printf("ALL PASS\n");
        return 0;
    }
    std::printf("%d FAILURE(S)\n", failures);
    return 1;
}
