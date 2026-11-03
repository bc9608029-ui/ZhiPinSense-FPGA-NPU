// phase2_ui_render.cpp — Phase 2 offscreen RGB565 rendering of the recognition UI
// (FMQL30TAI, 1280x720@60, double-buffered flip path shared with Phase 1B/1C/3).
//
// VISUAL REFACTOR (v5_visual): the 5x7 dot-matrix renderer is replaced by the
// anti-aliased DejaVu bitmap font atlas + Style A UI (see ui_render.cpp).  The
// device path is UNCHANGED from v4_fix: rendering happens in the ordinary-memory
// staging buffer, and the ONLY device write is
// DirectFramebufferBackend::submit_frame() (scalar volatile 16-bit stores — no
// SIGBUS).  RTL/XDC/bitstream/registers/DDR/double-buffering are all untouched.
//
// Confidence values remain a DEMO source (rotating softmax); the real NPU logits
// plug into the same UiState.  Class list: FINAL 10-class order (AM-DSB, WBFM,
// 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM).  The renderer is generic
// over N, so a 12-class target just changes `classes`.
//
// PHASE2_UI_PASS (software gate) = version OK + registers write/readback OK +
//   first UI frame rendered & flipped.  The text-legibility check on HDMI is the
//   hardware gate (still READY-FOR-HARDWARE-VISUAL-RETEST until then).

#include "direct_framebuffer_backend.hpp"
#include "ui_render.hpp"

#include <cstdint>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include <unistd.h>
#include <signal.h>
#include <time.h>

namespace {

constexpr int FRAME_W = 1280;
constexpr int FRAME_H = 720;

const std::vector<std::string> CLASS_NAMES = {
    "AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
    "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"
};

// ---- demo confidence source (normalized softmax, rotating top-1) -----------
void make_conf(std::vector<float>& conf, int top) {
    const int n = static_cast<int>(CLASS_NAMES.size());
    std::vector<float> logits(n, 0.0f);
    for (int i = 0; i < n; ++i) {
        int k = (i - top) % n;
        if (k < 0) k += n;
        logits[i] = 4.0f - 1.6f * k;
    }
    float mx = logits[0];
    for (int i = 1; i < n; ++i) if (logits[i] > mx) mx = logits[i];
    float sum = 0.0f;
    for (int i = 0; i < n; ++i) { logits[i] = std::exp(logits[i] - mx); sum += logits[i]; }
    for (int i = 0; i < n; ++i) conf[i] = logits[i] / sum;
}

volatile sig_atomic_t g_stop = 0;
void on_sigint(int) { g_stop = 1; }

} // namespace

int main(int argc, char** argv) {
    const long static_top = (argc > 1) ? std::strtol(argv[1], nullptr, 10) : -1; // -1 = animate
    const long fps        = (argc > 2) ? std::strtol(argv[2], nullptr, 10) : 20;

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    dfb::Config cfg;
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    if (!fb.init()) return 2;   // FAIL already printed

    const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 3;
    if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 4;

    std::vector<float> conf(CLASS_NAMES.size());
    int front = 0;
    long frame = 0;
    const int n = static_cast<int>(CLASS_NAMES.size());
    double last_lat_ms = 0.0;
    bool ui_pass_printed = false;
    std::uint16_t* stage = fb.staging();
    const std::size_t frame_px = static_cast<std::size_t>(FRAME_W) * FRAME_H;

    ui::UiState st;
    st.classes = &CLASS_NAMES;
    st.status = ui::Status::Mock;
    st.source = "MOCK";
    st.dist.assign(n, 0.0f);

    // Initial frame, so the PL never reads uninitialised memory before the flip.
    make_conf(conf, 0);
    {
        st.top1 = CLASS_NAMES[0];
        st.conf = conf[0];
        st.dist = conf;
        ui::Canvas c0{ stage, FRAME_W, FRAME_H };
        ui::render_main(c0, ui::palette_style_a(), st);
        if (!fb.submit_frame(0, stage, frame_px)) return 5;
    }

    std::cout << "PHASE2_PS_READY (static_top=" << static_top
              << " fps=" << fps << "; Ctrl-C to stop)\n";

    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;
    while (!g_stop) {
        const int top1 = (static_top >= 0) ? static_cast<int>(static_top % n)
                                           : static_cast<int>((frame / (2 * fps)) % n);
        make_conf(conf, top1);

        // Derive top-1 from the ACTUAL normalized distribution (provably consistent).
        int argmax = 0;
        for (int i = 1; i < n; ++i) if (conf[i] > conf[argmax]) argmax = i;

        const int snr_db = static_cast<int>(20 - (frame / fps) % 30);
        const int back = front ^ 1;

        st.top1 = CLASS_NAMES[static_cast<std::size_t>(argmax)];
        st.conf = conf[static_cast<std::size_t>(argmax)];
        st.dist = conf;
        char buf[64];
        std::snprintf(buf, sizeof buf, "%+d dB", snr_db);   st.snr = buf;
        std::snprintf(buf, sizeof buf, "%.1f ms", last_lat_ms); st.lat = buf;
        std::snprintf(buf, sizeof buf, "%ld", frame);        st.frame = buf;

        struct timespec t_begin, t_end;
        clock_gettime(CLOCK_MONOTONIC, &t_begin);
        ui::Canvas canvas{ stage, FRAME_W, FRAME_H };
        ui::render_main(canvas, ui::palette_style_a(), st);
        // submit_frame: scalar volatile copy + sync + flip (all before returning).
        if (!fb.submit_frame(back, stage, frame_px)) return 6;
        clock_gettime(CLOCK_MONOTONIC, &t_end);
        last_lat_ms = (t_end.tv_sec - t_begin.tv_sec) * 1000.0
                    + (t_end.tv_nsec - t_begin.tv_nsec) / 1e6;
        front = back;

        if (!ui_pass_printed) {
            std::cout << "PHASE2_UI_PASS (version/registers OK, first UI frame rendered & flipped; "
                         "anti-aliased atlas + Style A)\n";
            ui_pass_printed = true;
        }

        if (fps > 0 && (frame % fps) == 0)
            std::cout << "[2-PS] frame=" << frame
                      << " top1=" << CLASS_NAMES[static_cast<std::size_t>(argmax)]
                      << " conf=" << static_cast<int>(conf[static_cast<std::size_t>(argmax)] * 100)
                      << "% lat=" << last_lat_ms << "ms\n";
        ++frame;
        if (period > 0) usleep(period);
    }

    std::cout << "[2-PS] stopped after " << frame << " frames\n";
    return 0;
}
