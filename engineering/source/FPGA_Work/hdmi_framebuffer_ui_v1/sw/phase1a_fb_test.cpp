// phase1a_fb_test.cpp — Phase 1A PS-side smoke test (FMQL30TAI / ZG330, iCraft).
//
// Writes ONE static RGB565 test frame into a PS-DDR "udma" framebuffer, then
// points the PL HDMI read engine at it via register 0x40080054
// (frame_ctrl.slv_reg21 == camera_rd_addr == physical_framebuffer_address >> 3).
//
// Acceptance gate (1A-PS):
//   1. udma malloc returns an 8-byte-aligned physical address  (FAIL otherwise)
//   2. fb >> 3 fits the 27-bit camera_rd_addr field, i.e. fb < 1 GiB  (FAIL otherwise)
//   3. after write(0x40080054, fb>>3), read-back == fb>>3          (FAIL otherwise)
//   -> prints PHASE1A_PS_PASS only if all three hold.
//
// Informational (not fatal): frame_ctrl version (0x4008000C, expect 0x20230218)
// and the 0x40080054 reset value (expect 0x7E00000).
//
// NOTE (memory region): the display framebuffer must live in PS-DDR, because the
// PL reads it through the PS7 S_AXI_HP2_1 high-bandwidth port.  iCraft exposes
// PS-DDR reserved memory as the "udma" region (getMemRegion("udma")); the
// "default" region (defaultMemRegion) is PL-DDR, used for the NPU — do NOT put
// the framebuffer there.  This matches the official RGB565HDMIDisplay
// (deps/modelzoo_utils/.../hdmi_display.hpp:34).
//
// NOTE (cache): the udma buffer is an uncached/device-coherent region; the
// official display code writes it with no explicit flush, so we do the same.
//
// Build: see sw/build_on_board.sh (native aarch64 g++ or CMake, -DUSE_ZG330_BACKEND).

#include <icraft-xrt/core/session.h>
#include <icraft-xrt/dev/zg330_device.h>

#include <cstdint>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace icraft::xrt;

// FMQL30TAI == ZG330 NPU platform (device URL "axi://zg330aiu?...").  The
// official app aliases this as fpai::FPAIDevice in compile_fpai_target.hpp via
// USE_ZG330_BACKEND; we inline the alias so this file only needs the iCraft SDK.
using FPAIDevice = ZG330Device;

namespace {

// frame_ctrl register map (base 0x40080000, AXI-Lite, PS GP master).
constexpr uint32_t FRAME_CTRL_BASE = 0x40080000;
constexpr uint32_t FRAME_CTRL_VER  = FRAME_CTRL_BASE + 0x0C; // expect 0x20230218
constexpr uint32_t CAMERA_RD_ADDR  = FRAME_CTRL_BASE + 0x54; // slv_reg21, write fb>>3

// 720p RGB565.
constexpr int        FRAME_W     = 1280;
constexpr int        FRAME_H     = 720;
constexpr uint64_t   FRAME_BYTES = (uint64_t)FRAME_W * FRAME_H * 2; // 1,843,200

constexpr uint64_t   CAMERA_RD_ADDR_BITS = 27; // fb>>3 must fit in 27 bits

// Reset/version constants (from PHASE1A_PLAN / frame_ctrl defaults).
constexpr uint32_t   CAMERA_RD_ADDR_RESET = 0x07E00000;
constexpr uint32_t   FRAME_CTRL_VER_EXP   = 0x20230218;

inline uint16_t rgb565(uint8_t r, uint8_t g, uint8_t b)
{
    return (uint16_t)(((uint16_t)(r & 0xF8) << 8) |
                      ((uint16_t)(g & 0xFC) << 3) |
                      ((uint16_t)(b) >> 3));
}

void fill_checkerboard(uint16_t* px, int w, int h)
{
    const uint16_t c0 = rgb565(0x20, 0x20, 0x20); // dark grey
    const uint16_t c1 = rgb565(0xE0, 0xE0, 0xE0); // light grey
    const uint16_t border = rgb565(0xFF, 0xFF, 0xFF);
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            uint16_t c = (((x / 16) + (y / 16)) & 1) ? c1 : c0;
            if (x < 2 || x >= w - 2 || y < 2 || y >= h - 2) c = border;
            px[y * w + x] = c;
        }
    }
}

void fill_bars(uint16_t* px, int w, int h)
{
    static const uint16_t bars[8] = {
        rgb565(0xFF, 0xFF, 0xFF), rgb565(0xFF, 0xFF, 0x00),
        rgb565(0x00, 0xFF, 0xFF), rgb565(0x00, 0xFF, 0x00),
        rgb565(0xFF, 0x00, 0xFF), rgb565(0xFF, 0x00, 0x00),
        rgb565(0x00, 0x00, 0xFF), rgb565(0x00, 0x00, 0x00),
    };
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x)
            px[y * w + x] = bars[(x * 8) / w];
}

void fill_gradient(uint16_t* px, int w, int h)
{
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            uint8_t r = (uint8_t)(x * 255 / (w - 1));
            uint8_t g = (uint8_t)(y * 255 / (h - 1));
            uint8_t b = (uint8_t)((x + y) * 255 / (w + h - 2));
            px[y * w + x] = rgb565(r, g, b);
        }
    }
}

void fill_solid(uint16_t* px, int w, int h, uint16_t c)
{
    for (int i = 0; i < w * h; ++i) px[i] = c;
}

void fill(uint16_t* px, int w, int h, const std::string& pattern)
{
    if (pattern == "bars")          return fill_bars(px, w, h);
    if (pattern == "gradient")      return fill_gradient(px, w, h);
    if (pattern == "red")           return fill_solid(px, w, h, rgb565(0xFF, 0x00, 0x00));
    if (pattern == "green")         return fill_solid(px, w, h, rgb565(0x00, 0xFF, 0x00));
    if (pattern == "blue")          return fill_solid(px, w, h, rgb565(0x00, 0x00, 0xFF));
    /* default == checker */        return fill_checkerboard(px, w, h);
}

} // namespace

int main(int argc, char** argv)
{
    std::string pattern = (argc > 1) ? argv[1] : "checker";

    // ---- 1. open device ------------------------------------------------
    const char* device_url = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
    // Phase 1A has no NPU instantiated; the npu=/dma= URL params are accepted
    // by Device::Open but unused here.  If the runtime rejects them, fall back
    // to the bare URL: "axi://zg330aiu".
    auto device = Device::Open(device_url);
    auto dev = device.cast<FPAIDevice>();

    // ---- 2. read version + reset value (informational) -----------------
    uint32_t ver  = static_cast<uint32_t>(dev.defaultRegRegion().read(FRAME_CTRL_VER, false));
    uint32_t rst  = static_cast<uint32_t>(dev.defaultRegRegion().read(CAMERA_RD_ADDR, false));
    std::cout << "[1A-PS] frame_ctrl version   = 0x" << std::hex << std::setw(8)
              << std::setfill('0') << ver << std::dec << " (expect 0x"
              << std::hex << FRAME_CTRL_VER_EXP << std::dec << ")\n";
    std::cout << "[1A-PS] 0x40080054 reset      = 0x" << std::hex << std::setw(8)
              << std::setfill('0') << rst << std::dec << " (expect 0x"
              << std::hex << CAMERA_RD_ADDR_RESET << std::dec << ")\n";
    if (ver != FRAME_CTRL_VER_EXP)
        std::cout << "[1A-PS] WARN: frame_ctrl version mismatch\n";
    if (rst != CAMERA_RD_ADDR_RESET)
        std::cout << "[1A-PS] WARN: 0x40080054 reset value differs from 0x07E00000\n";

    // ---- 3. allocate PS-DDR framebuffer (udma region) ------------------
    auto chunk = dev.getMemRegion("udma").malloc(FRAME_BYTES, /*auto_free=*/false);
    uint64_t fb = chunk->begin.addr();
    std::cout << "[1A-PS] udma framebuffer phys = 0x" << std::hex << fb << std::dec
              << " (" << FRAME_BYTES << " bytes)\n";

    // ---- 4. alignment + range checks (fatal) ---------------------------
    bool fail = false;
    if ((fb & 0x7) != 0) {
        std::cout << "[1A-PS] FAIL: fb not 8-byte aligned (fb=0x" << std::hex << fb << std::dec << ")\n";
        fail = true;
    }
    uint64_t shifted = fb >> 3;
    if (shifted >= (1ull << CAMERA_RD_ADDR_BITS)) {
        std::cout << "[1A-PS] FAIL: fb>>3 (0x" << std::hex << shifted << std::dec
                  << ") does not fit 27 bits (fb >= 1 GiB)\n";
        fail = true;
    }
    if (fail) {
        Device::Close(device);
        return 1;
    }

    // ---- 5. fill the static test frame ---------------------------------
    std::vector<uint16_t> px(FRAME_W * FRAME_H);
    fill(px.data(), FRAME_W, FRAME_H, pattern);
    chunk.write(0, reinterpret_cast<char*>(px.data()), FRAME_BYTES);
    std::cout << "[1A-PS] filled pattern '" << pattern << "' into udma buffer\n";

    // ---- 6. point PL at the frame, then read back ----------------------
    dev.defaultRegRegion().write(CAMERA_RD_ADDR, shifted);
    uint32_t readback = static_cast<uint32_t>(dev.defaultRegRegion().read(CAMERA_RD_ADDR, false));
    std::cout << "[1A-PS] wrote 0x40080054 = 0x" << std::hex << (uint32_t)shifted << std::dec
              << ", read back = 0x" << std::hex << readback << std::dec << "\n";

    if (readback != (uint32_t)shifted) {
        std::cout << "[1A-PS] FAIL: read-back (0x" << std::hex << readback << std::dec
                  << ") != written (0x" << std::hex << (uint32_t)shifted << std::dec << ")\n";
        Device::Close(device);
        return 1;
    }

    // ---- 7. done -------------------------------------------------------
    std::cout << "PHASE1A_PS_PASS"
              << " fb=0x" << std::hex << fb
              << " fb>>3=0x" << (uint32_t)shifted
              << " pattern=" << pattern << std::dec << "\n";
    std::cout << "Frame is now on screen; keep this process alive to hold the "
                 "udma buffer (or press Enter after visual check).\n";

    // Hold the buffer so the PL keeps displaying it.  (The official demo keeps
    // its display chunk alive for the app lifetime; Ctrl-C / Enter to exit.)
    std::cin.get();

    Device::Close(device);
    return 0;
}
