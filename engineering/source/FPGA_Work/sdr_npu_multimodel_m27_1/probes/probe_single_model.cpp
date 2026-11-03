// probe_single_model.cpp — M27.1 baseline: one model, persistent Device, 1000
// frames.  Answers: single-model residency correctness + per-frame latency
// baseline (control for the other probes).
//
// Usage:
//   probe_single_model --model-json J --model-raw R --out-count N \
//                      [--warmup 100] [--frames 1000] [--rounds 2] \
//                      [--iq PATH] --out result.json
//
// Fail-closed: any exception/contract mismatch -> FAIL + non-zero exit.

#include "probe_common.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

using namespace m27_1;

int main(int argc, char** argv) {
    ProbeResult r;
    r.probe = "probe_single_model";

    try {
        const std::string json = arg_value(argc, argv, "--model-json");
        const std::string raw  = arg_value(argc, argv, "--model-raw");
        const long out_count   = std::strtol(arg_value(argc, argv, "--out-count", "12").c_str(), nullptr, 10);
        const long warmup      = std::strtol(arg_value(argc, argv, "--warmup", "100").c_str(), nullptr, 10);
        const long frames      = std::strtol(arg_value(argc, argv, "--frames", "1000").c_str(), nullptr, 10);
        const long rounds      = std::strtol(arg_value(argc, argv, "--rounds", "2").c_str(), nullptr, 10);
        const std::string iq   = arg_value(argc, argv, "--iq");
        const std::string out  = arg_value(argc, argv, "--out");

        if (json.empty() || raw.empty() || out.empty())
            throw std::runtime_error("missing --model-json/--model-raw/--out");

        const auto iq_frame = load_or_make_iq(iq);
        std::vector<float> logits(static_cast<std::size_t>(out_count));

        // Open device once, timed separately (production: one Open, one Close).
        const double t0 = now_us();
        auto device = open_zg330_device();
        r.device_open_us = elapsed_us(t0);

        ModelSpec spec{"A", json, raw, out_count};
        Zg330Session sess(spec, device, /*owns=*/true);
        r.model_load_a_us = sess.model_load_us;
        r.session_apply_a_us = sess.session_apply_us;

        int first_argmax = -1;
        bool deterministic = true;
        std::vector<double> round_means;

        for (long round = 0; round < rounds; ++round) {
            LatencyStats fwd;
            for (long i = 0; i < warmup + frames; ++i) {
                const double a = now_us();
                sess.infer(iq_frame.data(), logits.data());
                const double us = elapsed_us(a);
                if (i < warmup) continue;
                fwd.add(us);
                if (!all_finite(logits.data(), logits.size()))
                    throw std::runtime_error("non-finite logits");
                const int am = argmax(logits.data(), logits.size());
                if (first_argmax < 0) first_argmax = am;
                else if (am != first_argmax) deterministic = false;
            }
            r.fwd_a = fwd;
            round_means.push_back(fwd.mean());
        }

        // Repeatability: round-to-round mean within 20% relative.
        if (round_means.size() >= 2) {
            double lo = round_means[0], hi = round_means[0];
            for (double m : round_means) { lo = std::min(lo, m); hi = std::max(hi, m); }
            r.repeatability_pass = (lo > 0.0) && ((hi - lo) / lo <= 0.20);
        } else {
            r.repeatability_pass = true;
        }

        r.correctness_pass = deterministic;
        r.status = (r.correctness_pass && r.repeatability_pass) ? "PASS" : "FAIL";

        FILE* f = std::fopen(out.c_str(), "w");
        if (!f) throw std::runtime_error("cannot write result json");
        std::fputs(r.to_json().c_str(), f);
        std::fclose(f);
        emit_tail(r.status, out);
    } catch (const std::exception& e) {
        r.status = "FAIL";
        r.notes = e.what();
        std::fprintf(stderr, "probe_single_model FAILED: %s\n", e.what());
        emit_tail(r.status, "");
        return 1;
    }
    return r.status == "PASS" ? 0 : 1;
}
