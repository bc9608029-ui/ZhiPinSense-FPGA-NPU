// board_display_diagnostic.cpp — M18-0 HDMI display root-cause diagnostic tool.
//
// Four tools (A–D), driven by the M18-0 correction directive.  Each is a pure
// diagnostic -- NOT a "fixed version" -- and reuses the safe framebuffer backend
// (direct_framebuffer_backend) verbatim.  Nothing here modifies the production
// UI's flip / clear / display-enable logic; the only backend additions used are
// the purely-additive submit_frame_no_flip() (Tool B) and read_frame_words()
// (Tool D).
//
//   A  black-clear + static hold:  blank -> clear both frames -> program rd_addr
//      -> un-blank -> hold black.  Answers Q7 (are the boot stripes uninitialised
//      DDR content?).  If the screen is clean black, the stripes were content.
//   B  single-buffer lock:  blank -> clear -> rd_addr -> write a solid pattern to
//      frame 0 WITHOUT any flip -> un-blank -> hold.  Answers Q4/Q6 (is the dynamic
//      band present with the flip path fully disabled?).
//   C  red/blue dual-buffer low-frequency switch:  render red into frame 0, blue
//      into frame 1, then flip the buffer select at a low frequency WITHOUT
//      re-rendering.  Answers Q3/Q8 (is the flip/CDC path itself clean?  which
//      buffer tears?).  Also gives the mmcm/timing watch point.
//   D  framebuffer pre/post submit CRC:  fill a known pattern, CRC the staging
//      buffer, submit (no flip), read the frame back out of the device mapping,
//      CRC again, compare.  Answers Q5 (is the write + sync_for_device link
//      trustworthy?).  No human observation required.
//
// Usage:
//   board_display_diagnostic [--mode=a|b|c|d] [--switch-hz=1.0] [--hold-sec=0]
//   The mode may also be given as the first positional argument (a/b/c/d).
//   --hold-sec=0 (default) holds forever until SIGINT/SIGTERM for a/b/c.
//
// Needs root to map /dev/mem + /dev/udmabuf0.  Prints a single
//   DISPLAY_DIAG_TOOL_<A|B|C|D> result=...   line; exits non-zero on any failure.

#include "../ui_sw/direct_framebuffer_backend.hpp"
#include "../ui_sw/display_diagnostic.hpp"

#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

namespace {

volatile std::sig_atomic_t g_stop = 0;
void on_signal(int) { g_stop = 1; }

std::string hex32(std::uint32_t v) {
    char b[16];
    std::snprintf(b, sizeof(b), "0x%08x", v);
    return b;
}

void usage() {
    std::printf(
        "usage: board_display_diagnostic [--mode=a|b|c|d] [--switch-hz=1.0] [--hold-sec=0]\n"
        "  a  black-clear + static hold   (Q7: uninitialised-buffer stripes)\n"
        "  b  single-buffer lock, no flip (Q4/Q6: band without flip)\n"
        "  c  red/blue low-freq switch     (Q3/Q8: flip/CDC + which buffer)\n"
        "  d  pre/post submit CRC          (Q5: write+sync link)\n");
}

struct Args {
    ddx::Mode mode = ddx::Mode::A_BlackClearStatic;
    bool have_mode = false;
    double switch_hz = 1.0;
    double hold_sec = 0.0;
};

bool parse_args(int argc, char** argv, Args* out) {
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a.rfind("--mode=", 0) == 0) {
            if (!ddx::parse_mode(a.substr(7), &out->mode)) return false;
            out->have_mode = true;
        } else if (a.rfind("--switch-hz=", 0) == 0) {
            out->switch_hz = std::atof(a.substr(12).c_str());
        } else if (a.rfind("--hold-sec=", 0) == 0) {
            out->hold_sec = std::atof(a.substr(11).c_str());
        } else if (a == "-h" || a == "--help") {
            usage();
            std::exit(0);
        } else if (!a.empty() && a[0] == '-') {
            return false;
        } else if (!out->have_mode) {
            if (!ddx::parse_mode(a, &out->mode)) return false;
            out->have_mode = true;
        } else {
            return false;
        }
    }
    if (out->switch_hz <= 0.0) out->switch_hz = 1.0;
    return true;
}

// Common startup for A/B/C: blank -> clear both frames -> program rd_addr.
// The display stays blanked; the caller un-blanks after laying down its content.
bool common_startup(dfb::DirectFramebufferBackend& fb, const dfb::Config& cfg) {
    if (!fb.set_display_enable(false)) return false;
    if (!fb.clear_all_frames()) return false;
    const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return false;
    return true;
}

void hold(double hold_sec) {
    // 0 (or negative) => hold forever until a signal.
    const bool forever = (hold_sec <= 0.0);
    const auto tick = std::chrono::milliseconds(50);
    double elapsed = 0.0;
    while (!g_stop) {
        std::this_thread::sleep_for(tick);
        if (!forever) {
            elapsed += 0.050;
            if (elapsed >= hold_sec) break;
        }
    }
}

int run_a(dfb::DirectFramebufferBackend& fb, const dfb::Config& cfg, const Args& args) {
    if (!common_startup(fb, cfg)) return 2;
    if (!fb.set_display_enable(true)) return 2;
    std::printf("DISPLAY_DIAG_TOOL_A result=READY phys=0x%llx rd_addr=0x%08x black=both "
                "observe_screen=expect_clean_black (Ctrl-C to stop)\n",
                static_cast<unsigned long long>(fb.phys_addr()),
                static_cast<std::uint32_t>(fb.phys_addr() >> 3));
    hold(args.hold_sec);
    std::printf("DISPLAY_DIAG_TOOL_A result=STOPPED\n");
    return 0;
}

int run_b(dfb::DirectFramebufferBackend& fb, const dfb::Config& cfg, const Args& args) {
    if (!common_startup(fb, cfg)) return 2;
    const std::size_t words = static_cast<std::size_t>(cfg.frame_bytes() / 2);
    std::uint16_t* stage = fb.staging();
    ddx::fill_solid(stage, words, ddx::kGreen);   // solid green: any stripe/band shows
    // Write frame 0 with NO flip: the PL keeps reading whatever buffer it latched.
    if (!fb.submit_frame_no_flip(0, stage, words)) return 2;
    if (!fb.set_display_enable(true)) return 2;
    std::printf("DISPLAY_DIAG_TOOL_B result=READY frame=0 solid_green flip=disabled "
                "observe_screen=expect_clean_solid (Ctrl-C to stop)\n");
    hold(args.hold_sec);
    std::printf("DISPLAY_DIAG_TOOL_B result=STOPPED\n");
    return 0;
}

int run_c(dfb::DirectFramebufferBackend& fb, const dfb::Config& cfg, const Args& args) {
    if (!common_startup(fb, cfg)) return 2;
    const std::size_t words = static_cast<std::size_t>(cfg.frame_bytes() / 2);
    std::uint16_t* stage = fb.staging();
    ddx::fill_solid(stage, words, ddx::kRed);
    if (!fb.submit_frame(0, stage, words)) return 2;   // render red -> frame 0, flip
    ddx::fill_solid(stage, words, ddx::kBlue);
    if (!fb.submit_frame(1, stage, words)) return 2;   // render blue -> frame 1, flip
    if (!fb.set_display_enable(true)) return 2;

    const long period_ms = static_cast<long>(1000.0 / args.switch_hz);
    if (period_ms < 1) { std::printf("DISPLAY_DIAG_TOOL_C result=FAIL switch_hz too high\n"); return 2; }
    std::printf("DISPLAY_DIAG_TOOL_C result=READY red=frame0 blue=frame1 switch_hz=%.2f "
                "observe_screen=expect_clean_full_frame_switch (Ctrl-C to stop)\n",
                args.switch_hz);

    bool sel = false;   // false -> frame 0 (red), true -> frame 1 (blue)
    while (!g_stop) {
        sel = !sel;
        if (!fb.write_reg(cfg.wr_addr_offset, sel ? 1u : 0u)) {
            std::printf("DISPLAY_DIAG_TOOL_C result=FAIL flip_write_readback_mismatch\n");
            return 2;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(period_ms));
    }
    std::printf("DISPLAY_DIAG_TOOL_C result=STOPPED\n");
    return 0;
}

int run_d(dfb::DirectFramebufferBackend& fb, const dfb::Config& cfg) {
    const std::size_t words = static_cast<std::size_t>(cfg.frame_bytes() / 2);
    std::uint16_t* stage = fb.staging();
    for (std::size_t i = 0; i < words; ++i) {
        stage[i] = static_cast<std::uint16_t>(i);   // deterministic full-frame pattern
    }
    const std::uint32_t pre = ddx::crc32_u16(stage, words);
    if (!fb.submit_frame_no_flip(0, stage, words)) return 2;

    std::vector<std::uint16_t> readback(words, 0);
    if (!fb.read_frame_words(0, readback.data(), words)) return 2;
    const std::uint32_t post = ddx::crc32_u16(readback.data(), words);

    const bool match = (pre == post);
    std::printf("DISPLAY_DIAG_TOOL_D result=%s pre_crc=%s post_crc=%s words=%zu match=%d\n",
                match ? "PASS" : "FAIL", hex32(pre).c_str(), hex32(post).c_str(),
                words, match ? 1 : 0);
    return match ? 0 : 3;
}

}  // namespace

int main(int argc, char** argv) {
    Args args;
    if (!parse_args(argc, argv, &args)) {
        usage();
        std::fprintf(stderr, "DISPLAY_DIAG_TOOL result=FAIL bad_arguments\n");
        return 2;
    }

    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);

    dfb::Config cfg;
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    if (!fb.init()) {
        std::fprintf(stderr, "DISPLAY_DIAG_TOOL result=FAIL init\n");
        return 2;
    }

    switch (args.mode) {
    case ddx::Mode::A_BlackClearStatic: return run_a(fb, cfg, args);
    case ddx::Mode::B_SingleBufferLock: return run_b(fb, cfg, args);
    case ddx::Mode::C_RedBlueSwitch:    return run_c(fb, cfg, args);
    case ddx::Mode::D_CrcCheck:         return run_d(fb, cfg);
    }
    return 2;
}
