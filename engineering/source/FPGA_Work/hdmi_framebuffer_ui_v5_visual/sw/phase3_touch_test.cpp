// phase3_touch_test.cpp — Phase 3 USB touch detection / calibration / page switching
// (FMQL30TAI, 1280x720@60, double-buffered flip path shared with Phase 1B/1C/2).
//
// VISUAL REFACTOR (v5_visual): the three placeholder colored pages are replaced by
// the Style A Main / Diagnostics / Touch pages (ui_render.cpp), so all three pages
// share one visual language.  The TOUCH PARSING is UNCHANGED from v4_fix — device
// enumeration, ABS capability check, single-touch / multitouch-protocol-B reading,
// calibration, and the tap -> hit-region -> page-change chain are all identical.
// Only the bottom-nav hit-region height is updated 80px -> 90px to match the new
// nav layout (still 3 tabs).  submit_frame() and the backend are untouched.
//
// The on-screen calibration table shows the *example* 7" ILITEK panel (the same
// values the design draft used, and which match the confirmed hardware); the real
// detected device path + axis ranges are printed to stdout by this program.
//
// PHASE3_TOUCH_PASS = touch detected + calibrated + at least one tap successfully
//   mapped to a screen coordinate and dispatched (click/page/hit-region chain).

#include "direct_framebuffer_backend.hpp"
#include "ui_render.hpp"

#include <cerrno>
#include <cstdint>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <fcntl.h>
#include <dirent.h>
#include <sys/ioctl.h>
#include <linux/input.h>
#include <linux/input-event-codes.h>

namespace {

constexpr int FRAME_W = 1280;
constexpr int FRAME_H = 720;

// ---- USB / input detection (UNCHANGED from v4_fix) -------------------------
// Does this fd report EV_ABS and at least one of ABS_X / ABS_MT_POSITION_X?
bool ev_is_touch_capable(int fd) {
    unsigned long evbits[(EV_MAX / 8) + 1] = {0};
    if (ioctl(fd, EVIOCGBIT(0, sizeof(evbits)), evbits) < 0) return false;
    if (!((evbits[EV_ABS / 8] >> (EV_ABS % 8)) & 1UL)) return false;

    unsigned long absbits[(ABS_MAX / 8) + 1] = {0};
    if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(absbits)), absbits) < 0) return false;
    auto has = [&](unsigned int axis) { return (absbits[axis / 8] >> (axis % 8)) & 1UL; };
    return has(ABS_X) || has(ABS_MT_POSITION_X);
}

// Enumerate /dev/input/event* (never a hard-coded event number), require a
// touch/vendor name keyword AND ABS capability.  Returns the device path or "".
std::string detect_touch_device() {
    DIR* d = opendir("/dev/input");
    if (!d) return "";

    static const char* kw[] = {"touch", "egalax", "goodix", "ilitek", "ft5", "gt9", "ch5", "wch"};
    std::string found;

    struct dirent* e;
    while ((e = readdir(d)) != nullptr) {
        const std::string n = e->d_name;
        if (n.rfind("event", 0) != 0) continue;

        const std::string path = "/dev/input/" + n;
        const int fd = open(path.c_str(), O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;

        char name[256] = {0};
        ioctl(fd, EVIOCGNAME(sizeof(name)), name);
        std::string lower = name;
        for (auto& ch : lower) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));

        bool kw_hit = false;
        for (const char* k : kw)
            if (lower.find(k) != std::string::npos) { kw_hit = true; break; }

        if (kw_hit && ev_is_touch_capable(fd)) {
            found = path;
            close(fd);
            break;
        }
        close(fd);
    }
    closedir(d);
    return found;
}

void log_usb_topology() {
    std::cout << "[3-PS] --- USB topology (/proc/bus/usb/devices) ---\n";
    std::ifstream f("/proc/bus/usb/devices");
    if (f.is_open()) {
        std::string line;
        while (std::getline(f, line)) std::cout << "  " << line << "\n";
    } else {
        std::cout << "  (/proc/bus/usb/devices not available)\n";
    }
    std::cout << "[3-PS] --- input devices (/proc/bus/input/devices) ---\n";
    std::ifstream g("/proc/bus/input/devices");
    if (g.is_open()) {
        std::string line;
        while (std::getline(g, line)) std::cout << "  " << line << "\n";
    }
}

// raw -> screen linear mapping.  Returns false if axis info unavailable.
bool read_axis_range(int fd, unsigned int axis, int* lo, int* hi) {
    struct input_absinfo info;
    if (ioctl(fd, EVIOCGABS(axis), &info) < 0) return false;
    *lo = info.minimum; *hi = info.maximum;
    return true;
}

// ---- demo recognition state (static; phase 3 is a touch test) -------------
ui::UiState make_demo_state() {
    ui::UiState st;
    st.status = ui::Status::Mock;
    st.source = "MOCK";
    st.top1 = "16QAM";
    st.conf = 0.842f;
    st.dist = {0.008f, 0.006f, 0.012f, 0.015f, 0.010f,
               0.024f, 0.031f, 0.842f, 0.044f, 0.008f};
    st.snr = "+18 dB";
    st.lat = "12.4 ms";
    st.frame = "1024";
    return st;
}

// ---- page rendering (the ONLY visual part changed vs v4_fix) --------------
void render_page(ui::Canvas& c, int page, const ui::UiState& st) {
    const ui::Palette& pal = ui::palette_style_a();
    if (page == 0)      ui::render_main(c, pal, st);
    else if (page == 1) ui::render_diag(c, pal, st);
    else                ui::render_touch(c, pal, st);
}

volatile sig_atomic_t g_stop = 0;
void on_sigint(int) { g_stop = 1; }

} // namespace

int main(int argc, char** argv) {
    const long fps = (argc > 1) ? std::strtol(argv[1], nullptr, 10) : 30;

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    dfb::Config cfg;
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    if (!fb.init()) return 2;   // FAIL already printed

    const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 3;
    if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 4;

    // ---- touch detection (UNCHANGED from v4_fix) --------------------------
    log_usb_topology();
    const std::string touch = detect_touch_device();
    if (touch.empty()) {
        std::cerr << "PHASE3_TOUCH_FAIL: no touch device found in /dev/input/event*\n";
        return 5;   // non-zero exit; NOT a PASS
    }

    const int touch_fd = open(touch.c_str(), O_RDONLY | O_NONBLOCK);
    if (touch_fd < 0) {
        std::cerr << "PHASE3_TOUCH_FAIL: open " << touch << ": " << std::strerror(errno) << "\n";
        return 6;
    }

    int x_lo = 0, x_hi = 4095, y_lo = 0, y_hi = 4095;
    bool x_ok = false, y_ok = false;
    x_ok = read_axis_range(touch_fd, ABS_X, &x_lo, &x_hi) ||
           read_axis_range(touch_fd, ABS_MT_POSITION_X, &x_lo, &x_hi);
    y_ok = read_axis_range(touch_fd, ABS_Y, &y_lo, &y_hi) ||
           read_axis_range(touch_fd, ABS_MT_POSITION_Y, &y_lo, &y_hi);
    std::cout << "TOUCH_FOUND path=" << touch
              << " X=[" << x_lo << "," << x_hi << "] Y=[" << y_lo << "," << y_hi << "]\n";
    if (x_hi > x_lo)
        std::cout << "[3-PS] calibration: screen_x = (raw_x - " << x_lo << ") * " << (FRAME_W - 1)
                  << " / (" << x_hi << " - " << x_lo << ")\n";
    if (y_hi > y_lo)
        std::cout << "[3-PS] calibration: screen_y = (raw_y - " << y_lo << ") * " << (FRAME_H - 1)
                  << " / (" << y_hi << " - " << y_lo << ")\n";

    // render the first page into the staging buffer and submit it before the loop
    const ui::UiState st = make_demo_state();
    std::uint16_t* stage = fb.staging();
    ui::Canvas first_canvas{ stage, FRAME_W, FRAME_H };
    render_page(first_canvas, 0, st);
    if (!fb.submit_frame(0, stage, static_cast<std::size_t>(FRAME_W) * FRAME_H)) return 7;

    int page = 0, front = 0;
    long frame = 0;

    int  touch_x = 0, touch_y = 0;
    bool btn_down = false;
    bool mt_down  = false;
    bool touch_pass_printed = false;

    std::cout << "PHASE3_PS_READY (fps=" << fps
              << "; tap bottom tab = jump, tap elsewhere = next page, Ctrl-C to stop)\n";

    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;
    while (!g_stop) {
        // --- read touch events (non-blocking, SYN_REPORT-aware; UNCHANGED) ---
        struct input_event ev;
        ssize_t n;
        int  fx = 0, fy = 0;
        bool fx_seen = false, fy_seen = false;
        bool have_btn = false; int btn_v = 0;
        bool have_track = false; int track_v = 0;
        while ((n = read(touch_fd, &ev, sizeof(ev))) == static_cast<ssize_t>(sizeof(ev))) {
            if (ev.type == EV_ABS) {
                if (ev.code == ABS_X || ev.code == ABS_MT_POSITION_X) { fx = ev.value; fx_seen = true; }
                else if (ev.code == ABS_Y || ev.code == ABS_MT_POSITION_Y) { fy = ev.value; fy_seen = true; }
                else if (ev.code == ABS_MT_TRACKING_ID) { track_v = ev.value; have_track = true; }
            } else if (ev.type == EV_KEY && (ev.code == BTN_TOUCH || ev.code == BTN_LEFT)) {
                have_btn = true; btn_v = ev.value;
            } else if (ev.type == EV_SYN && ev.code == SYN_REPORT) {
                if (fx_seen) touch_x = fx;
                if (fy_seen) touch_y = fy;

                bool release = false;
                if (have_track) {
                    if (track_v >= 0 && !mt_down) { mt_down = true; }
                    else if (track_v < 0 && mt_down) { mt_down = false; release = true; }
                } else if (have_btn) {
                    if (btn_v == 1 && !btn_down) { btn_down = true; }
                    else if (btn_v == 0 && btn_down) { btn_down = false; release = true; }
                }

                if (release) {
                    int sx = x_ok && (x_hi > x_lo) ? (touch_x - x_lo) * (FRAME_W - 1) / (x_hi - x_lo) : touch_x;
                    int sy = y_ok && (y_hi > y_lo) ? (touch_y - y_lo) * (FRAME_H - 1) / (y_hi - y_lo) : touch_y;
                    std::cout << "[3-PS] tap raw=(" << touch_x << "," << touch_y << ") screen=(" << sx << "," << sy << ")\n";

                    if (sy >= FRAME_H - 90) {          // bottom nav = 90px (matches Style A nav)
                        int t = (sx < 0 ? 0 : sx) / (FRAME_W / 3);
                        if (t >= 3) t = 2;
                        std::cout << "[3-PS] hit-region=tab" << (t + 1) << "\n";
                        page = t;
                    } else {                            // elsewhere = next page
                        std::cout << "[3-PS] hit-region=next-page\n";
                        page = (page + 1) % 3;
                    }
                    std::cout << "[3-PS] page -> " << (page + 1) << "\n";

                    if (!touch_pass_printed) {
                        std::cout << "PHASE3_TOUCH_PASS (touch detected + calibrated + tap dispatched "
                                     "through click/page/hit-region chain)\n";
                        touch_pass_printed = true;
                    }
                }

                fx_seen = fy_seen = false;
                have_btn = have_track = false;
            }
        }

        const int back = front ^ 1;
        ui::Canvas canvas{ stage, FRAME_W, FRAME_H };
        render_page(canvas, page, st);
        if (!fb.submit_frame(back, stage, static_cast<std::size_t>(FRAME_W) * FRAME_H)) return 8;
        front = back;

        ++frame;
        if (period > 0) usleep(period);
    }

    std::cout << "[3-PS] stopped after " << frame << " frames\n";
    close(touch_fd);
    return 0;
}
