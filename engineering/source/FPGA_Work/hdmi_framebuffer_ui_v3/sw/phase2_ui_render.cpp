// phase2_ui_render.cpp — Phase 2: render the RF-signal-recognition instrument UI
// (FMQL30TAI, 1280x720@60, double-buffered flip path shared with Phase 1B/1C/3).
//
// Uses ONLY the safe direct backend: /dev/udmabuf0 for the framebuffer and
// /dev/mem for frame_ctrl.  It does NOT touch the NPU, DMA, or iCraft Device::Open.
//
// SIGBUS-fix path (the whole point of v3): the UI is rendered into a regular-RAM
// staging buffer (ui::Canvas -> std::vector<uint16_t>), then copied into the
// device mapping with DirectFramebufferBackend::submit() — scalar 16-bit stores,
// never NEON/SIMD wide stores.  The PL read select is then flipped to the just-
// written back buffer (the same tear-free path as Phase 1B).
//
// The class list comes from model_contract (V1.1, 10 classes) at runtime; the
// renderer is generic over 8..16 classes.  Confidence values are a MOCK source
// (rotating softmax) and are clearly marked DEMO/MOCK — the real NPU logits will
// plug into the same softmax interface later.
//
//   PL buffer select: 0x40080050 bit[0] = read buffer (0/1)
//   PL read base:     0x40080054 = FB0 >> 3 (set once)
//
// PHASE2_UI_PASS (software gate) = version OK + registers write/readback OK +
//   first UI frame rendered, submitted, flushed & flipped.  The text-legibility
//   check on HDMI remains the hardware gate (READY-FOR-HARDWARE-TEST until then).
//
// Usage: phase2_ui_render [static_top] [fps] [page]
//   static_top: -1 = animate rotating Top-1, else fixed class index
//   fps:        default 20
//   page:       -1 = cycle all 3 pages, else 0/1/2 pin

#include "direct_framebuffer_backend.hpp"
#include "canvas.hpp"
#include "ui_renderer.hpp"
#include "model_contract.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include <unistd.h>
#include <signal.h>
#include <time.h>

namespace {

volatile sig_atomic_t g_stop = 0;
void on_sigint(int) { g_stop = 1; }

// Synthetic logits peaked at `top` (MOCK source), softmaxed by the renderer.
std::vector<float> make_conf(int n, int top) {
    std::vector<float> logits(n, 1.0f);
    for (int i = 0; i < n; ++i) {
        int k = (i - top) % n; if (k < 0) k += n;   // circular distance from top
        logits[static_cast<std::size_t>(i)] = 5.0f - 1.4f * static_cast<float>(k);
    }
    return ui::softmax(logits);
}

} // namespace

int main(int argc, char** argv) {
    const long static_top = (argc > 1) ? std::strtol(argv[1], nullptr, 10) : -1;
    const long fps        = (argc > 2) ? std::strtol(argv[2], nullptr, 10) : 20;
    const long page_arg   = (argc > 3) ? std::strtol(argv[3], nullptr, 10) : -1;

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    const model::Contract contract = model::contract_v1_1();   // active board contract
    const int n = contract.class_count;

    dfb::Config cfg;
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    if (!fb.init()) return 2;   // FAIL already printed

    const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 3;
    if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 4;

    ui::Renderer renderer;
    ui::Canvas staging(cfg.frame_width, cfg.frame_height);   // regular RAM, never device

    int front = 0;
    long frame = 0;
    double last_lat_ms = 0.0;
    bool ui_pass_printed = false;

    const long page_interval = (fps > 0) ? std::max<long>(1, fps * 4) : 1;  // ~4 s per page

    std::cout << "PHASE2_PS_READY (static_top=" << static_top << " fps=" << fps
              << " page=" << page_arg << "; Ctrl-C to stop)\n";

    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;
    while (!g_stop) {
        const int top1 = (static_top >= 0) ? static_cast<int>(static_top % n)
                                           : static_cast<int>((frame / (2 * fps)) % n);
        const std::vector<float> conf = make_conf(n, top1);

        ui::UiState s;
        s.class_names = contract.class_names;
        s.prob = conf;
        s.class_count = n;
        s.source = ui::Source::Mock;
        s.live = ui::LiveState::Live;
        s.fpga_ok = true;
        s.npu_ok = false;          // no real NPU in the HDMI-only build
        s.is_mock = true;
        s.frame_id = static_cast<std::uint64_t>(frame);
        s.fps = static_cast<float>(fps);
        s.render_latency_ms = static_cast<float>(last_lat_ms);
        s.e2e_latency_ms = static_cast<float>(last_lat_ms);
        s.fb_phys_addr = fb.phys_addr();
        s.frame_ctrl_version = fb.read_reg(cfg.version_offset);
        s.front_buffer = front;

        int page;
        if (page_arg >= 0 && page_arg <= 2) {
            page = static_cast<int>(page_arg);
        } else {
            page = static_cast<int>((frame / page_interval) % 3);
        }

        const int back = front ^ 1;

        struct timespec t_begin, t_end;
        clock_gettime(CLOCK_MONOTONIC, &t_begin);
        renderer.draw(staging, s, static_cast<ui::Page>(page));
        if (!fb.submit(staging.pixels(), back)) return 5;      // scalar-16-bit copy
        if (!fb.flush()) return 6;
        if (!fb.write_reg(cfg.wr_addr_offset, static_cast<std::uint32_t>(back))) return 7;
        clock_gettime(CLOCK_MONOTONIC, &t_end);
        last_lat_ms = (t_end.tv_sec - t_begin.tv_sec) * 1000.0
                    + (t_end.tv_nsec - t_begin.tv_nsec) / 1e6;
        front = back;

        if (!ui_pass_printed) {
            std::cout << "PHASE2_UI_PASS (version/registers OK, first UI frame rendered "
                         "via staging+scalar submit, flushed & flipped)\n";
            ui_pass_printed = true;
        }

        if (fps > 0 && (frame % fps) == 0) {
            const int argmax = static_cast<int>(ui::argmax(conf));
            std::cout << "[2-PS] frame=" << frame << " page=" << page
                      << " top1=" << contract.name(argmax)
                      << " conf=" << static_cast<int>(conf[static_cast<std::size_t>(argmax)] * 100)
                      << "% lat=" << last_lat_ms << "ms\n";
        }
        ++frame;
        if (period > 0) usleep(period);
    }

    std::cout << "[2-PS] stopped after " << frame << " frames\n";
    return 0;
}
