// probe_unload_reload.cpp — M27.1 unload/reload probe: release model B, confirm
// model A still works, then reload B.  Answers: is model switching (unload A ->
// load B) viable, is there a resource leak, and does error recovery hold.
//
// Usage:
//   probe_unload_reload --model-a-json J --model-a-raw R \
//                       --model-b-json J --model-b-raw R \
//                       [--warmup 100] [--frames 1000] [--iq PATH] \
//                       --out result.json
//
// Fail-closed: any exception -> FAIL + non-zero exit.

#include "probe_common.hpp"

#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <vector>

using namespace m27_1;

int main(int argc, char** argv) {
    ProbeResult r;
    r.probe = "probe_unload_reload";

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

        // A is persistent for the whole probe.
        Zg330Session sessA(ModelSpec{"A", ajson, araw, 12}, device, false);
        r.model_load_a_us = sessA.model_load_us;
        r.session_apply_a_us = sessA.session_apply_us;

        std::vector<float> logitsA(12), logitsB(8);
        int amA = -1, amB = -1;
        bool detA = true, detB = true;

        auto run_A = [&](LatencyStats& dst) {
            for (long i = 0; i < warmup + frames; ++i) {
                const double a = now_us();
                sessA.infer(iq_frame.data(), logitsA.data());
                const double us = elapsed_us(a);
                if (i < warmup) continue;
                dst.add(us);
                if (!all_finite(logitsA.data(), 12)) throw std::runtime_error("non-finite A logits");
                const int am = argmax(logitsA.data(), 12);
                if (amA < 0) amA = am; else if (am != amA) detA = false;
            }
        };

        // (1) Load B, run it briefly, then unload B (destroy -> deinit backend).
        {
            auto sessB = std::make_unique<Zg330Session>(ModelSpec{"B", bjson, braw, 8}, device, false);
            r.model_load_b_us = sessB->model_load_us;
            r.session_apply_b_us = sessB->session_apply_us;
            for (long i = 0; i < 10; ++i) {
                sessB->infer(iq_frame.data(), logitsB.data());
                if (!all_finite(logitsB.data(), 8)) throw std::runtime_error("non-finite B logits");
                const int am = argmax(logitsB.data(), 8);
                if (amB < 0) amB = am; else if (am != amB) detB = false;
            }
            // Unload B here; measure unload+reload latency below.
            const double t_unload = now_us();
            sessB.reset();               // destroys B session -> backends_need_deinit
            const double unload_us = elapsed_us(t_unload);
            r.switch_us = unload_us;
        }

        // (2) After B is gone, A must still work (no cross-model corruption).
        run_A(r.fwd_a);

        // (3) Reload B, confirm it works again, then unload.  Switch latency =
        //     unload B + reload B (CreateFromJsonFile + loadParams + apply).
        {
            const double t_load = now_us();
            auto sessB2 = std::make_unique<Zg330Session>(ModelSpec{"B", bjson, braw, 8}, device, false);
            r.switch_us += elapsed_us(t_load);
            for (long i = 0; i < 10; ++i) {
                sessB2->infer(iq_frame.data(), logitsB.data());
                if (!all_finite(logitsB.data(), 8)) throw std::runtime_error("non-finite B logits (reload)");
                const int am = argmax(logitsB.data(), 8);
                if (amB < 0) amB = am; else if (am != amB) detB = false;
            }
        }

        r.correctness_pass = detA && detB;
        const long rss_end = read_rss_kb();
        if (rss_start >= 0 && rss_end >= 0)
            r.notes = "rss_delta_kb=" + std::to_string(rss_end - rss_start);
        r.status = r.correctness_pass ? "PASS" : "FAIL";

        icraft::xrt::Device::Close(device);

        FILE* f = std::fopen(out.c_str(), "w");
        if (!f) throw std::runtime_error("cannot write result json");
        std::fputs(r.to_json().c_str(), f);
        std::fclose(f);
        emit_tail(r.status, out);
    } catch (const std::exception& e) {
        r.status = "FAIL";
        r.notes = e.what();
        std::fprintf(stderr, "probe_unload_reload FAILED: %s\n", e.what());
        emit_tail(r.status, "");
        return 1;
    }
    return r.status == "PASS" ? 0 : 1;
}
