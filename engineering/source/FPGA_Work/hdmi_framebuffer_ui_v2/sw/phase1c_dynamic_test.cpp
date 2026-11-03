// phase1c_dynamic_test.cpp — Phase 1C PS-side long-run dynamic stability test
// (FMQL30TAI, 1280x720 RGB565, double-buffered flip).
//
// Uses ONLY the safe direct backend (direct_framebuffer_backend): /dev/udmabuf0
// for the framebuffer and /dev/mem for frame_ctrl.  It does NOT touch the NPU,
// DMA, or iCraft Device::Open.
//
// Rotates through 4 dynamic patterns (bars / checker / gradient / solid) while
// keeping a frame + elapsed-time heartbeat, for the >=10-minute stability gate.
// Besides the per-flip register read-back (done by the backend on every write),
// this program ALSO re-reads the two frame_ctrl registers once per second and
// counts any drift/out-of-range value as an anomaly.  PHASE1C_PS_PASS is printed
// ONLY when elapsed >= 600 s AND the anomaly count is zero.
//
//   PL buffer select: 0x40080050 (camera_wr_addr) bit[0]  = read buffer (0/1)
//   PL read base:     0x40080054 (camera_rd_addr)         = FB0 >> 3 (set once)
//
// Build: see sw/build_on_board.sh.

#include "direct_framebuffer_backend.hpp"

#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

#include <unistd.h>
#include <signal.h>
#include <time.h>

namespace {

constexpr int FRAME_W = 1280;
constexpr int FRAME_H = 720;

inline std::uint16_t rgb565(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    return static_cast<std::uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// 4 distinct, high-motion patterns so a freeze/tear is immediately visible.
//   case 0 = bars     (moving vertical bar — classic tear detector)
//   case 1 = checker  (scrolling checkerboard — horizontal motion)
//   case 2 = gradient (vertical gradient scroll)
//   case 3 = solid    (full-frame uniform colour, slowly cycling)
void render_pattern(std::uint16_t* px, int frame, int pattern) {
    const int bar_w = 40;
    switch (pattern & 3) {
    case 0: { // moving vertical bar
        int bx = (frame * 4) % FRAME_W;
        std::uint16_t bg = rgb565(0x10, 0x10, 0x10);
        for (int y = 0; y < FRAME_H; ++y)
            for (int x = 0; x < FRAME_W; ++x) {
                int dx = x - bx;
                px[y * FRAME_W + x] = (dx >= 0 && dx < bar_w) ? rgb565(0xFF, 0xFF, 0xFF) : bg;
            }
        break;
    }
    case 1: { // scrolling checkerboard
        int off = (frame * 2) & 31;
        for (int y = 0; y < FRAME_H; ++y)
            for (int x = 0; x < FRAME_W; ++x) {
                int cx = (x + off) / 16, cy = y / 16;
                std::uint16_t c = ((cx + cy) & 1) ? rgb565(0xE0, 0xE0, 0xE0) : rgb565(0x20, 0x20, 0x20);
                px[y * FRAME_W + x] = c;
            }
        break;
    }
    case 2: { // vertical gradient scroll
        int off = (frame * 2) % FRAME_H;
        for (int y = 0; y < FRAME_H; ++y) {
            std::uint8_t v = static_cast<std::uint8_t>(((y + off) * 255) / (FRAME_H - 1));
            std::uint16_t c = rgb565(v, 0x00, static_cast<std::uint8_t>(0xFF - v));
            for (int x = 0; x < FRAME_W; ++x) px[y * FRAME_W + x] = c;
        }
        break;
    }
    case 3: { // full-frame solid colour (slowly cycling)
        std::uint8_t r = static_cast<std::uint8_t>(frame & 0xFF);
        std::uint8_t g = static_cast<std::uint8_t>((frame & 0xFF) ^ 0x80);
        std::uint8_t b = static_cast<std::uint8_t>((frame & 0xFF) ^ 0xFF);
        std::uint16_t c = rgb565(r, g, b);
        for (int i = 0; i < FRAME_W * FRAME_H; ++i) px[i] = c;
        break;
    }
    }
}

volatile sig_atomic_t g_stop = 0;
void on_sigint(int) { g_stop = 1; }

} // namespace

int main(int argc, char** argv) {
    // default max_seconds = 600 (the >=10-minute gate).  arg1=0 means until Ctrl-C.
    const long max_seconds = (argc > 1) ? std::strtol(argv[1], nullptr, 10) : 600;
    const long fps         = (argc > 2) ? std::strtol(argv[2], nullptr, 10) : 60;

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    dfb::Config cfg;
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    if (!fb.init()) return 2;   // FAIL already printed

    const std::uint64_t fb0 = fb.phys_addr();
    const std::uint32_t rd = static_cast<std::uint32_t>(fb0 >> 3);
    std::cout << "[1C-PS] FB0=0x" << std::hex << fb0 << std::dec
              << " rd(0x54)=0x" << std::hex << rd << std::dec << "\n";

    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 3;
    if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 4;

    int front = 0;
    long frame = 0;
    int anomalies = 0;
    const time_t t0 = time(nullptr);

    std::cout << "PHASE1C_PS_READY (max_seconds=" << max_seconds
              << " fps=" << fps << "; Ctrl-C to stop)\n";

    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;
    while (!g_stop && (max_seconds == 0 || (time(nullptr) - t0) < max_seconds)) {
        const int back = front ^ 1;
        render_pattern(fb.frame_buffer(back), static_cast<int>(frame),
                       static_cast<int>(frame / (3 * fps)));   // rotate every ~3 s
        if (!fb.flush()) return 5;
        if (!fb.write_reg(cfg.wr_addr_offset, static_cast<std::uint32_t>(back))) {
            std::cout << "[1C-PS] FAIL: buffer-select readback mismatch at frame " << frame << "\n";
            ++anomalies;
            break;
        }
        front = back;

        if (fps > 0 && (frame % fps) == 0) {
            // once-per-second register integrity check (independent of the per-write readback)
            const std::uint32_t rd_rb = fb.read_reg(cfg.rd_addr_offset);
            const std::uint32_t wr_rb = fb.read_reg(cfg.wr_addr_offset);
            if (rd_rb != rd) {
                std::cout << "[1C-PS] ANOMALY: rd_addr drifted to 0x" << std::hex << rd_rb
                          << std::dec << " (expect 0x" << std::hex << rd << std::dec << ")\n";
                ++anomalies;
            }
            if (wr_rb > 1) {
                std::cout << "[1C-PS] ANOMALY: wr_addr=0x" << std::hex << wr_rb
                          << std::dec << " out of range {0,1}\n";
                ++anomalies;
            }
            const long elapsed = static_cast<long>(time(nullptr) - t0);
            std::cout << "[1C-PS] frame=" << frame << " elapsed_s=" << elapsed
                      << " pattern=" << (frame / (3 * fps)) << " front=" << front
                      << " anomalies=" << anomalies << "\n";
        }
        ++frame;
        if (period > 0) usleep(period);
    }

    const long elapsed = static_cast<long>(time(nullptr) - t0);
    std::cout << "[1C-PS] stopped: frame=" << frame << " elapsed_s=" << elapsed
              << " anomalies=" << anomalies << "\n";

    if (elapsed >= 600 && anomalies == 0)
        std::cout << "PHASE1C_PS_PASS (>=600 s, 0 register/readback anomalies)\n";
    else if (elapsed < 600)
        std::cout << "PHASE1C_PS_INCOMPLETE (elapsed=" << elapsed << " s < 600 s)\n";
    if (anomalies > 0)
        std::cout << "PHASE1C_PS_FAIL anomalies=" << anomalies << "\n";

    return (elapsed >= 600 && anomalies == 0) ? 0 : 1;
}
