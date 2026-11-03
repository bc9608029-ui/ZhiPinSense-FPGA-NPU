// probe_sequential_inference.cpp — M27.1 serial-scheduling probe: A -> B -> A
// on ONE Device with NO per-frame Device::Open.  Answers: can two resident
// models be serially scheduled (with per-session reset(1) discipline), and what
// is the model-switch latency / memory growth / error profile.
//
// Usage:
//   probe_sequential_inference --model-a-json J --model-a-raw R \
//                              --model-b-json J --model-b-raw R \
//                              [--warmup 100] [--frames 1000] [--iq PATH] \
//                              --out result.json
//
// Fail-closed: any exception -> FAIL + non-zero exit.  Never per-frame Open.

#include "probe_common.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

using namespace m27_1;

int main(int argc, char** argv) {
    ProbeResult r;
    r.probe = "probe_sequential_inference";

    try {
        const std::string ajson = arg_value(argc, argv, "--model-a-json");
        const std::string araw  = arg_value(argc, argv, "--model-a-raw");
        const std::string bjson = arg_value(argc, argv, "--model-b-json");
        const std::string braw  = arg_value(argc, argv, "--model-b-raw");
        const long warmup       = std::strtol(arg_value(argc, argv, "--warmup", "100").c_str(), nullptr, 10);
        const long frames       = std::strtol(arg_value(argc, argv, "--frames", "1000").c_str(), nullptr, 10);
        const std::string iq    = arg_value(argc, argv, "--iq");
        const std::string out   = arg_value(argc, argv, "--out");

        if (ajson.empty() || araw.empty() || bjson.empty() || braw.empty() || out.empty())
            throw std::runtime_error("missing model-a/model-b paths or --out");

        const auto iq_frame = load_or_make_iq(iq);
        const long rss_start = read_rss_kb();

        const double t0 = now_us();
        auto device = open_zg330_device();
        r.device_open_us = elapsed_us(t0);

        // Both sessions resident on one device (no re-open, no re-load).
        Zg330Session sessA(ModelSpec{"A", ajson, araw, 12}, device, false);
        Zg330Session sessB(ModelSpec{"B", bjson, braw, 8}, device, false);
        r.model_load_a_us = sessA.model_load_us;
        r.model_load_b_us = sessB.model_load_us;
        r.session_apply_a_us = sessA.session_apply_us;
        r.session_apply_b_us = sessB.session_apply_us;

        std::vector<float> logitsA(12), logitsB(8);
        int amA = -1, amB = -1;
        bool detA = true, detB = true;
        double switch_total = 0.0;
        long switch_count = 0;
        std::uint64_t errors = 0, timeouts = 0;

        // run_phase: warmup+frames on one session, record into dst stats.
        auto run_phase = [&](Zg330Session& s, std::vector<float>& logits,
                             long out_n, LatencyStats& dst, int& anchor,
                             bool& det) {
            for (long i = 0; i < warmup + frames; ++i) {
                try {
                    const double a = now_us();
                    s.infer(iq_frame.data(), logits.data());
                    const double us = elapsed_us(a);
                    if (i >= warmup) {
                        dst.add(us);
                        if (!all_finite(logits.data(), static_cast<std::size_t>(out_n)))
                            throw std::runtime_error("non-finite logits");
                        const int am = argmax(logits.data(), static_cast<std::size_t>(out_n));
                        if (anchor < 0) anchor = am; else if (am != anchor) det = false;
                    }
                } catch (const std::exception&) {
                    // Distinguish a timeout-style failure from a hard error is
                    // SDK-internal; count both as a failed frame, keep running.
                    ++errors;
                }
            }
        };

        // A -> B -> A serial, no re-open.  Switch latency = time to first
        // inference of the newly selected model after the previous phase.
        {
            const double sw = now_us();
            run_phase(sessA, logitsA, 12, r.fwd_a, amA, detA);
            switch_total += elapsed_us(sw); ++switch_count;
        }
        {
            const double sw = now_us();
            run_phase(sessB, logitsB, 8, r.fwd_b, amB, detB);
            switch_total += elapsed_us(sw); ++switch_count;
        }
        {
            // Back to A: verifies A is still correct after B ran in between.
            const double sw = now_us();
            LatencyStats a2;
            run_phase(sessA, logitsA, 12, a2, amA, detA);
            switch_total += elapsed_us(sw); ++switch_count;
            // Fold the second A pass into r.fwd_a so fwd_a reflects A overall.
            r.fwd_a.samples.insert(r.fwd_a.samples.end(), a2.samples.begin(), a2.samples.end());
            r.fwd_a.count += a2.count; r.fwd_a.sum += a2.sum;
            r.fwd_a.max = std::max(r.fwd_a.max, a2.max);
        }

        r.switch_us = switch_total / static_cast<double>(switch_count);
        r.correctness_pass = detA && detB;
        r.error_count = errors;
        r.timeout_count = timeouts;
        const long rss_end = read_rss_kb();
        if (rss_start >= 0 && rss_end >= 0)
            r.notes = "rss_delta_kb=" + std::to_string(rss_end - rss_start);
        r.status = (r.correctness_pass && errors == 0) ? "PASS" : "FAIL";

        icraft::xrt::Device::Close(device);

        FILE* f = std::fopen(out.c_str(), "w");
        if (!f) throw std::runtime_error("cannot write result json");
        std::fputs(r.to_json().c_str(), f);
        std::fclose(f);
        emit_tail(r.status, out);
    } catch (const std::exception& e) {
        r.status = "FAIL";
        r.notes = e.what();
        std::fprintf(stderr, "probe_sequential_inference FAILED: %s\n", e.what());
        emit_tail(r.status, "");
        return 1;
    }
    return r.status == "PASS" ? 0 : 1;
}
