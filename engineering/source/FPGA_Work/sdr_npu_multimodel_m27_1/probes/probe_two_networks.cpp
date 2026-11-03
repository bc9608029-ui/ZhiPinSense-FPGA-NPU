// probe_two_networks.cpp — M27.1 residency probe: two models (A=12-class,
// B=8-class) on ONE Device, both Network+Session applied, then alternating
// forward.  Answers: can two models be simultaneously resident on the ZG330?
//
// Usage:
//   probe_two_networks --model-a-json J --model-a-raw R \
//                      --model-b-json J --model-b-raw R \
//                      [--warmup 100] [--frames 1000] [--rounds 2] \
//                      [--iq PATH] --out result.json
//
// Fail-closed: if the second model's apply()/forward() fails (e.g. etm capacity),
// the probe records FAIL + the return code and does NOT fabricate residency.

#include "probe_common.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

using namespace m27_1;

int main(int argc, char** argv) {
    ProbeResult r;
    r.probe = "probe_two_networks";

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

        // One Device, opened once, shared by both sessions.
        const double t0 = now_us();
        auto device = open_zg330_device();
        r.device_open_us = elapsed_us(t0);

        ModelSpec specA{"A", ajson, araw, 12};
        ModelSpec specB{"B", bjson, braw, 8};

        // Both sessions share `device` (owns=false).  The probe closes it below.
        Zg330Session sessA(specA, device, false);
        r.model_load_a_us = sessA.model_load_us;
        r.session_apply_a_us = sessA.session_apply_us;

        Zg330Session sessB(specB, device, false);
        r.model_load_b_us = sessB.model_load_us;
        r.session_apply_b_us = sessB.session_apply_us;

        std::vector<float> logitsA(12), logitsB(8);
        int amA = -1, amB = -1;
        bool detA = true, detB = true;

        for (long i = 0; i < warmup + frames; ++i) {
            const bool pickA = (i % 2 == 0);
            const double a = now_us();
            if (pickA) {
                sessA.infer(iq_frame.data(), logitsA.data());
                const double us = elapsed_us(a);
                if (i >= warmup) {
                    r.fwd_a.add(us);
                    if (!all_finite(logitsA.data(), 12)) throw std::runtime_error("non-finite A logits");
                    const int am = argmax(logitsA.data(), 12);
                    if (amA < 0) amA = am; else if (am != amA) detA = false;
                }
            } else {
                sessB.infer(iq_frame.data(), logitsB.data());
                const double us = elapsed_us(a);
                if (i >= warmup) {
                    r.fwd_b.add(us);
                    if (!all_finite(logitsB.data(), 8)) throw std::runtime_error("non-finite B logits");
                    const int am = argmax(logitsB.data(), 8);
                    if (amB < 0) amB = am; else if (am != amB) detB = false;
                }
            }
        }

        r.correctness_pass = detA && detB;
        r.status = r.correctness_pass ? "PASS" : "FAIL";
        if (r.status == "PASS")
            r.notes = "both models applied on one device and ran interleaved";

        icraft::xrt::Device::Close(device);

        FILE* f = std::fopen(out.c_str(), "w");
        if (!f) throw std::runtime_error("cannot write result json");
        std::fputs(r.to_json().c_str(), f);
        std::fclose(f);
        emit_tail(r.status, out);
    } catch (const std::exception& e) {
        r.status = "FAIL";
        r.notes = e.what();
        std::fprintf(stderr, "probe_two_networks FAILED: %s\n", e.what());
        emit_tail(r.status, "");
        return 1;
    }
    return r.status == "PASS" ? 0 : 1;
}
