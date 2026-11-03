// phase3_touch_test.cpp — Phase 3: USB touch detect / calibrate / page switch
// (FMQL30TAI, 1280x720@60, double-buffered flip path shared with Phase 1B/1C/2).
//
// Uses ONLY the safe direct backend: /dev/udmabuf0 for the framebuffer and
// /dev/mem for frame_ctrl.  It does NOT touch the NPU, DMA, or iCraft Device::Open.
//
// Display hardware: 7" IPS touch panel, native 1024x600, HDMI input (720p scaled
// internally).  Touch = USB HID on the panel's "touch" port -> board USB host.
// The controller may report single-touch (ABS_X/ABS_Y + BTN_TOUCH) or multitouch
// protocol B (ABS_MT_POSITION_X/Y + ABS_MT_TRACKING_ID); touch::TouchDecoder
// handles both.  Raw axis values are calibrated via EVIOCGABS and mapped to the
// 1280x720 canvas with a full-range linear map.
//
// The touch device is found by ENUMERATING /dev/input/event* (no hard-coded
// event number), requiring a touch/vendor name keyword AND ABS capability.  If no
// touch device is found the program prints an explicit FAIL and exits non-zero —
// it never fakes a PASS or auto-cycles pages.  On USB disconnect it re-enumerates
// and reconnects (does not crash).
//
//   1. Detect     — enumerate /dev/input/event*, match name + ABS capability.
//   2. Calibrate  — EVIOCGABS min/max -> raw->1280x720 linear mapping.
//   3. Page switch — tap a tab (hit_test_tab) = jump; tap elsewhere = next page.
//      Each tap logs raw/screen coords and the hit region, then dispatches.
//
//   PL buffer select: 0x40080050 bit[0] = read buffer (0/1)
//   PL read base:     0x40080054 = FB0 >> 3 (set once)
//
// PHASE3_TOUCH_PASS = touch detected + calibrated + at least one tap dispatched
//   through the click/page/hit-region chain.

#include "direct_framebuffer_backend.hpp"
#include "canvas.hpp"
#include "ui_renderer.hpp"
#include "model_contract.hpp"
#include "touch.hpp"

#include <cerrno>
#include <cstdint>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <dirent.h>
#include <sys/ioctl.h>
#include <linux/input.h>

namespace {

constexpr int FRAME_W = 1280;
constexpr int FRAME_H = 720;

volatile sig_atomic_t g_stop = 0;
void on_sigint(int) { g_stop = 1; }

// ---- USB / input detection -------------------------------------------------
bool ev_is_touch_capable(int fd) {
    unsigned long evbits[(EV_MAX / 8) + 1] = {0};
    if (ioctl(fd, EVIOCGBIT(0, sizeof(evbits)), evbits) < 0) return false;
    if (!((evbits[EV_ABS / 8] >> (EV_ABS % 8)) & 1UL)) return false;

    unsigned long absbits[(ABS_MAX / 8) + 1] = {0};
    if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(absbits)), absbits) < 0) return false;
    auto has = [&](unsigned int axis) { return (absbits[axis / 8] >> (axis % 8)) & 1UL; };
    return has(ABS_X) || has(ABS_MT_POSITION_X);
}

std::string device_name(int fd) {
    char name[256] = {0};
    ioctl(fd, EVIOCGNAME(sizeof(name)), name);
    return std::string(name);
}

// Enumerate /dev/input/event*, require a touch keyword AND ABS capability.
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

        std::string lower = device_name(fd);
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

bool read_axis_range(int fd, unsigned int axis, int* lo, int* hi) {
    struct input_absinfo info;
    if (ioctl(fd, EVIOCGABS(axis), &info) < 0) return false;
    *lo = info.minimum; *hi = info.maximum;
    return true;
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

} // namespace

int main(int argc, char** argv) {
    const long fps = (argc > 1) ? std::strtol(argv[1], nullptr, 10) : 30;

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    dfb::Config cfg;
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    if (!fb.init()) return 2;

    const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 3;
    if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 4;

    log_usb_topology();

    // ---- touch detection ---------------------------------------------------
    const std::string touch = detect_touch_device();
    if (touch.empty()) {
        std::cerr << "PHASE3_TOUCH_FAIL: no touch device found in /dev/input/event*\n";
        return 5;
    }
    int touch_fd = open(touch.c_str(), O_RDONLY | O_NONBLOCK);
    if (touch_fd < 0) {
        std::cerr << "PHASE3_TOUCH_FAIL: open " << touch << ": " << std::strerror(errno) << "\n";
        return 6;
    }

    touch::TouchDecoder dec(FRAME_W, FRAME_H);

    int x_lo = 0, x_hi = 1023, y_lo = 0, y_hi = 599;
    bool x_ok = read_axis_range(touch_fd, ABS_X, &x_lo, &x_hi) ||
                read_axis_range(touch_fd, ABS_MT_POSITION_X, &x_lo, &x_hi);
    bool y_ok = read_axis_range(touch_fd, ABS_Y, &y_lo, &y_hi) ||
                read_axis_range(touch_fd, ABS_MT_POSITION_Y, &y_lo, &y_hi);
    if (x_ok && y_ok) dec.set_input_range(x_lo, x_hi, y_lo, y_hi);

    std::cout << "TOUCH_FOUND path=" << touch << " name=\"" << device_name(touch_fd) << "\"\n";
    std::cout << "TOUCH_AXIS X=[" << x_lo << "," << x_hi << "] Y=[" << y_lo << "," << y_hi << "]\n";
    std::cout << "[3-PS] mapping: canvas_x = (raw_x - " << x_lo << ") * " << (FRAME_W - 1)
              << " / (" << x_hi << " - " << x_lo << ")\n";
    std::cout << "[3-PS] mapping: canvas_y = (raw_y - " << y_lo << ") * " << (FRAME_H - 1)
              << " / (" << y_hi << " - " << y_lo << ")\n";

    // ---- UI state (MOCK, fixed) for page rendering ------------------------
    const model::Contract contract = model::contract_v1_1();
    ui::Renderer renderer;
    ui::UiState ui_state;
    {
        std::vector<float> logits(contract.class_count, 1.0f);
        logits[7] = 5.0f;   // 16QAM
        ui_state.class_names = contract.class_names;
        ui_state.prob = ui::softmax(logits);
        ui_state.class_count = contract.class_count;
        ui_state.source = ui::Source::Mock;
        ui_state.is_mock = true;
        ui_state.fpga_ok = true;
        ui_state.npu_ok = false;
        ui_state.fb_phys_addr = fb.phys_addr();
        ui_state.frame_ctrl_version = fb.read_reg(cfg.version_offset);
    }

    ui::Canvas staging(FRAME_W, FRAME_H);
    int page = 0, front = 0;
    long frame = 0;
    bool prev_touching = false;
    int last_x = 0, last_y = 0;
    bool touch_pass_printed = false;

    std::cout << "PHASE3_PS_READY (fps=" << fps
              << "; tap a tab = jump, tap elsewhere = next page, Ctrl-C to stop)\n";

    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;
    while (!g_stop) {
        // --- read touch events (non-blocking, SYN_REPORT-aware) ---
        struct input_event ev;
        ssize_t nread;
        while ((nread = read(touch_fd, &ev, sizeof(ev))) == static_cast<ssize_t>(sizeof(ev))) {
            const bool report = dec.feed(ev.type, ev.code, ev.value);
            if (report) {
                const bool now = dec.touching();
                if (now) { last_x = dec.x(); last_y = dec.y(); }
                if (prev_touching && !now) {          // a tap (contact released)
                    const int sx = last_x, sy = last_y;
                    const bool in_range = sx >= 0 && sx < FRAME_W && sy >= 0 && sy < FRAME_H;
                    std::cout << "[3-PS] tap screen=(" << sx << "," << sy << ")"
                              << (in_range ? "" : " OUT-OF-RANGE") << "\n";

                    const ui::TabHit h = ui::hit_test_tab(sx, sy);
                    if (h.on_tab) {
                        std::cout << "[3-PS] hit-region=tab (page " << static_cast<int>(h.page) << ")\n";
                        page = static_cast<int>(h.page);
                    } else {
                        std::cout << "[3-PS] hit-region=next-page\n";
                        page = (page + 1) % 3;
                    }
                    std::cout << "[3-PS] page -> " << page << "\n";

                    if (!touch_pass_printed) {
                        std::cout << "PHASE3_TOUCH_PASS (touch detected + calibrated + tap "
                                     "dispatched through click/page/hit-region chain)\n";
                        touch_pass_printed = true;
                    }
                }
                prev_touching = now;
            }
        }

        // --- USB disconnect -> re-enumerate & reconnect (no crash) ---
        if (nread < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
            std::cout << "[3-PS] touch device error (" << std::strerror(errno)
                      << "); re-enumerating...\n";
            close(touch_fd);
            touch_fd = -1;
            while (!g_stop && touch_fd < 0) {
                const std::string retry = detect_touch_device();
                if (!retry.empty()) {
                    touch_fd = open(retry.c_str(), O_RDONLY | O_NONBLOCK);
                    if (touch_fd >= 0) {
                        dec.reset();
                        x_ok = read_axis_range(touch_fd, ABS_X, &x_lo, &x_hi) ||
                               read_axis_range(touch_fd, ABS_MT_POSITION_X, &x_lo, &x_hi);
                        y_ok = read_axis_range(touch_fd, ABS_Y, &y_lo, &y_hi) ||
                               read_axis_range(touch_fd, ABS_MT_POSITION_Y, &y_lo, &y_hi);
                        if (x_ok && y_ok) dec.set_input_range(x_lo, x_hi, y_lo, y_hi);
                        prev_touching = false;
                        std::cout << "[3-PS] reconnected " << retry
                                  << " name=\"" << device_name(touch_fd) << "\"\n";
                        break;
                    }
                }
                sleep(1);
            }
        }

        // --- render + submit + flip (safe backend) ---
        ui_state.front_buffer = front;
        ui_state.frame_id = static_cast<std::uint64_t>(frame);
        const int back = front ^ 1;
        renderer.draw(staging, ui_state, static_cast<ui::Page>(page));
        if (!fb.submit(staging.pixels(), back)) return 8;
        if (!fb.flush()) return 9;
        if (!fb.write_reg(cfg.wr_addr_offset, static_cast<std::uint32_t>(back))) return 10;
        front = back;

        ++frame;
        if (period > 0) usleep(period);
    }

    std::cout << "[3-PS] stopped after " << frame << " frames\n";
    if (touch_fd >= 0) close(touch_fd);
    return 0;
}
