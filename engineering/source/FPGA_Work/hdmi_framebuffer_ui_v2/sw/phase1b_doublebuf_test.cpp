// phase1b_doublebuf_test.cpp — Phase 1B PS-side double-buffer dynamic test
// (FMQL30TAI, 1280x720 RGB565, tear-free ping-pong flip).
//
// Uses ONLY the safe direct backend (direct_framebuffer_backend): /dev/udmabuf0
// for the framebuffer and /dev/mem for frame_ctrl.  It does NOT touch the NPU,
// DMA, or iCraft Device::Open — the HDMI-only bitstream has no NPU, and the old
// axi:// path hangs the board's Linux.
//
//   PL buffer map (v3 bitstream):
//     read_addr_0   = camera_rd_addr              (buffer 0)
//     read_addr_1   = camera_rd_addr + 230400     (buffer 1 = buffer 0 + one frame)
//     buffer select = camera_wr_addr[0]           (0x40080050, latched at frame start)
//
//   PS writes:
//     0x40080054 (camera_rd_addr) = FB0 >> 3     once at init
//     0x40080050 (camera_wr_addr) = 0 or 1        flip the display buffer
//
// The PL latches the select register at the next frame boundary (vsync), so each
// flip is applied atomically at a real frame boundary — no mid-frame tear.
//
// Software gate (what this program proves): version/alignment/capacity/read-back
// all pass, both frames initialised, base + select committed -> PHASE1B_PS_PASS.
// The tear-free visual check on the HDMI screen is the hardware gate.

#include "direct_framebuffer_backend.hpp"

#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

#include <unistd.h>
#include <signal.h>

namespace {

constexpr int FRAME_W = 1280;
constexpr int FRAME_H = 720;

inline std::uint16_t rgb565(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    return static_cast<std::uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// A moving vertical bright bar over a slowly colour-cycling background.  A moving
// vertical edge is the classic tear detector: a horizontal split/notch shows up
// if the PL ever reads a buffer mid-write.
void render_moving_bar(std::uint16_t* px, int frame) {
    const int bar_w = 40;
    const int bar_x = (frame * 4) % FRAME_W;               // 4 px/frame, wrap
    const std::uint16_t bg = rgb565(static_cast<std::uint8_t>((frame & 0x3F) * 4), 0x20, 0x40);
    const std::uint16_t bar = rgb565(0xFF, 0xFF, 0xFF);
    for (int y = 0; y < FRAME_H; ++y) {
        for (int x = 0; x < FRAME_W; ++x) {
            const int dx = x - bar_x;
            px[y * FRAME_W + x] = (dx >= 0 && dx < bar_w) ? bar : bg;
        }
    }
}

volatile sig_atomic_t g_stop = 0;
void on_sigint(int) { g_stop = 1; }

} // namespace

int main(int argc, char** argv) {
    const long max_frames = (argc > 1) ? std::strtol(argv[1], nullptr, 10) : 0; // 0 = forever
    const long fps        = (argc > 2) ? std::strtol(argv[2], nullptr, 10) : 60;

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    dfb::Config cfg;   // defaults: 1280x720 RGB565, double buffer, frame_ctrl @ 0x40080000
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    // init() resolves phys/capacity, validates alignment + 1 GiB + capacity,
    // maps /dev/udmabuf0 and /dev/mem, and verifies the version gate.
    if (!fb.init()) return 2;   // FAIL already printed

    const std::uint64_t fb0 = fb.phys_addr();
    const std::uint64_t fb1 = fb0 + cfg.frame_bytes();
    const std::uint32_t rd = static_cast<std::uint32_t>(fb0 >> 3);
    std::cout << "[1B-PS] FB0=0x" << std::hex << fb0 << " FB1=0x" << fb1
              << std::dec << " rd(0x54)=0x" << std::hex << rd << std::dec << "\n";

    // Initialise BOTH frames before enabling switching (no half-written frame).
    render_moving_bar(fb.frame_buffer(0), 0);
    render_moving_bar(fb.frame_buffer(1), 1);
    if (!fb.flush()) return 3;

    // Point the PL at the base address, then select buffer 0.  Every write is
    // read back and verified by the backend.
    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 4;
    if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 5;

    std::cout << "PHASE1B_PS_PASS (software gate: version/alignment/capacity/readback OK)\n";
    std::cout << "NOTE: tear-free visual check on the HDMI screen is the hardware gate.\n";

    int front = 0;
    long frame = 0;
    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;

    while (!g_stop && (max_frames == 0 || frame < max_frames)) {
        const int back = front ^ 1;
        render_moving_bar(fb.frame_buffer(back), static_cast<int>(frame));
        if (!fb.flush()) return 6;
        if (!fb.write_reg(cfg.wr_addr_offset, static_cast<std::uint32_t>(back))) return 7;
        front = back;

        if (fps > 0 && (frame % fps) == 0)
            std::cout << "[1B-PS] frame=" << frame << " front=" << front << "\n";
        ++frame;
        if (period > 0) usleep(period);
    }

    std::cout << "[1B-PS] stopped after " << frame << " frames\n";
    return 0;
}
