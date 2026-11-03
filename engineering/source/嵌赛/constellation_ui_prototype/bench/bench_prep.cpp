// bench_prep.cpp — Qt-free micro-benchmark of the per-frame C++ path.
//
// Measures, in WSL (this delivery machine has no Qt-capable C++ toolchain, so
// GUI FPS itself is NOT-RUN): (a) fail-closed frame load incl. SHA-256, and
// (b) the deterministic decimate + unit-transform render-prep for 4096 points.
// This gives an honest lower-bound budget check for the UI perf gates; it is NOT
// a GUI frame-rate measurement.
#include "IqFrame.hpp"
#include "IqFrameLoader.hpp"

#include <chrono>
#include <cstdio>
#include <string>
#include <vector>

using clk = std::chrono::steady_clock;

static double ms_since(clk::time_point t0) {
    return std::chrono::duration<double, std::milli>(clk::now() - t0).count();
}

int main(int argc, char** argv) {
    const std::string dir = argc > 1 ? argv[1] : ".";
    const char* names[] = {
        "bpsk_clean_model_input.json",
        "bpsk_recovered_payload.json",
        "bpsk_raw_rx.json",
    };

    for (const char* n : names) {
        const std::string path = dir + "/" + n;
        cst::IqFrame f;
        std::string err;

        double best_load = 1e9;
        for (int r = 0; r < 20; ++r) {
            auto t0 = clk::now();
            const bool ok = cst::load_sidecar_frame(path, f, err);
            const double ms = ms_since(t0);
            if (!ok) {
                std::printf("%s LOAD-FAIL: %s\n", n, err.c_str());
                return 1;
            }
            if (ms < best_load) best_load = ms;
        }

        // Render-prep: decimate to 4096, then unit transform (the per-frame C++ path).
        const std::size_t lim = 4096;
        const auto idx = cst::decimate_indices(f.i.size(), lim);
        std::vector<float> di(idx.size()), dq(idx.size());
        for (std::size_t k = 0; k < idx.size(); ++k) {
            di[k] = f.i[idx[k]];
            dq[k] = f.q[idx[k]];
        }
        std::vector<float> ux, uy;
        double best_xf = 1e9;
        float sink = 0.0f;
        for (int r = 0; r < 200; ++r) {
            auto t0 = clk::now();
            cst::transform_to_unit(di, dq, 1.0f, ux, uy);
            const double ms = ms_since(t0);
            if (ms < best_xf) best_xf = ms;
            // Prevent the optimizer from removing the transform as dead code.
            for (float v : ux) sink += v;
            for (float v : uy) sink -= v;
        }

        std::printf("%-32s n=%zu  load=%.3f ms  transform4096=%.4f ms  sink=%.3f\n",
                    n, f.i.size(), best_load, best_xf, static_cast<double>(sink));
    }
    return 0;
}
