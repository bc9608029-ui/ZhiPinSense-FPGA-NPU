// phase3_touch_test.cpp — Phase 3 USB touch detection / calibration / page switching
// (FMQL30TAI, 1280x720@60, double-buffered flip path shared with Phase 1B/1C/2).
//
// Uses ONLY the safe direct backend (direct_framebuffer_backend): /dev/udmabuf0
// for the framebuffer and /dev/mem for frame_ctrl.  It does NOT touch the NPU,
// DMA, or iCraft Device::Open.
//
// Display hardware (confirmed by user): 7" IPS touch panel, native 1024x600, HDMI
// input (720p is scaled internally).  Touch = USB HID, wired via the panel's
// "touch" port -> board USB host; this SAME cable also powers the panel.  Do NOT
// press the panel's POWER button — USB power turns it on, pressing POWER turns it
// off.
//
// The USB HID touch controller may report either single-touch (ABS_X/ABS_Y +
// BTN_TOUCH) or multitouch protocol B (ABS_MT_POSITION_X/Y + ABS_MT_TRACKING_ID);
// this program handles BOTH.  The touch device is found by ENUMERATING
// /dev/input/event* (no hard-coded event number) and requiring both a
// touch/vendor name keyword and ABS_X / ABS_MT_POSITION_X capability.  If no
// touch device is found the program prints an explicit FAIL and exits non-zero —
// it does NOT fake a PASS or auto-cycle pages.
//
//   1. Detect  — enumerate /dev/input/event*, match name keyword + ABS capability.
//   2. Calibrate — read ABS_X/ABS_Y (or ABS_MT_POSITION_X/Y) min/max via EVIOCGABS
//      and report the raw->1280x720 linear mapping.
//   3. Page switch — bottom 80 px = tab 1/2/3, tap elsewhere = next page; each tap
//      logs raw/screen coords and the hit region, then dispatches the page change.
//
//   PL buffer select: 0x40080050 bit[0] = read buffer (0/1)
//   PL read base:     0x40080054 = FB0 >> 3 (set once)
//
// PHASE3_TOUCH_PASS = touch detected + calibrated + at least one tap successfully
//   mapped to a screen coordinate and dispatched (click/page/hit-region chain).

#include "direct_framebuffer_backend.hpp"

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

inline std::uint16_t rgb565(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    return static_cast<std::uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// ---- minimal 5x7 digit font (0-9) ----------------------------------------
static const char** digit_glyph(char c) {
    switch (c) {
    case '0': { static const char* g[7] = {".###.","#...#","#..##","#.#.#","##..#","#...#",".###."}; return g; }
    case '1': { static const char* g[7] = {"..#..",".##..","..#..","..#..","..#..","..#..","#####"}; return g; }
    case '2': { static const char* g[7] = {".###.","#...#","....#","...#.","..#..",".#...","#####"}; return g; }
    case '3': { static const char* g[7] = {"#####","...#.","..#..",".###.","....#","#...#",".###."}; return g; }
    case '4': { static const char* g[7] = {"...#.","..##.",".#.#.","#..#.","#####","...#.","...#."}; return g; }
    case '5': { static const char* g[7] = {"#####","#....","####.","....#","....#","#...#",".###."}; return g; }
    case '6': { static const char* g[7] = {".###.","#....","#....","####.","#...#","#...#",".###."}; return g; }
    case '7': { static const char* g[7] = {"#####","....#","...#.","..#..",".#...",".#...",".#..."}; return g; }
    case '8': { static const char* g[7] = {".###.","#...#","#...#",".###.","#...#","#...#",".###."}; return g; }
    case '9': { static const char* g[7] = {".###.","#...#","#...#",".###.","....#","....#",".###."}; return g; }
    case ' ': { static const char* g[7] = {".....",".....",".....",".....",".....",".....","....."}; return g; }
    default:  { static const char* g[7] = {"#####","#####","#####","#####","#####","#####","#####"}; return g; }
    }
}

struct Canvas { std::uint16_t* px; int w, h; };

void fill_rect(Canvas& c, int x0, int y0, int x1, int y1, std::uint16_t color) {
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= c.w) x1 = c.w - 1;
    if (y1 >= c.h) y1 = c.h - 1;
    if (x0 > x1 || y0 > y1) return;
    for (int y = y0; y <= y1; ++y)
        for (int x = x0; x <= x1; ++x)
            c.px[y * c.w + x] = color;
}

void draw_digit(Canvas& c, char ch, int x, int y, std::uint16_t color, int scale = 1) {
    const char** g = digit_glyph(ch);
    for (int r = 0; r < 7; ++r)
        for (int col = 0; col < 5; ++col)
            if (g[r][col] == '#')
                fill_rect(c, x + col * scale, y + r * scale,
                          x + col * scale + scale - 1, y + r * scale + scale - 1, color);
}

// ---- USB / input detection -------------------------------------------------
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

// ---- page rendering --------------------------------------------------------
void render_page(Canvas& c, int page) {
    const int n = 3;
    std::uint16_t themes[3] = { rgb565(0x00, 0x30, 0x18),   // page 1: green
                                rgb565(0x00, 0x10, 0x38),   // page 2: blue
                                rgb565(0x30, 0x08, 0x30) }; // page 3: purple
    fill_rect(c, 0, 0, FRAME_W - 1, FRAME_H - 1, themes[page % n]);

    if (page % n == 1)
        for (int x = 0; x < FRAME_W; x += 64) fill_rect(c, x, 0, x + 31, FRAME_H - 81, rgb565(0x00, 0x20, 0x50));
    else if (page % n == 2)
        for (int y = 0; y < FRAME_H - 80; y += 64) fill_rect(c, 0, y, FRAME_W - 1, y + 31, rgb565(0x48, 0x10, 0x48));

    char digit = static_cast<char>('1' + (page % n));
    int scale = 10;
    int gw = 5 * scale, gh = 7 * scale;
    draw_digit(c, digit, (FRAME_W - gw) / 2, (FRAME_H - gh) / 2 - 20, rgb565(0xFF, 0xFF, 0xFF), scale);

    const int tab_h = 80, tab_y = FRAME_H - tab_h;
    int tw = FRAME_W / n;
    for (int i = 0; i < n; ++i) {
        std::uint16_t col = (i == (page % n)) ? rgb565(0xFF, 0xD0, 0x00) : rgb565(0x10, 0x18, 0x28);
        fill_rect(c, i * tw, tab_y, i * tw + tw - 4, FRAME_H - 1, col);
        char d = static_cast<char>('1' + i);
        int s2 = 5;
        draw_digit(c, d, i * tw + tw / 2 - 2 * s2, tab_y + (tab_h - 7 * s2) / 2, rgb565(0x00, 0x00, 0x00), s2);
    }
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

    // ---- touch detection --------------------------------------------------
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
    // prefer single-touch ABS_X/ABS_Y, fall back to multi-touch position
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
    std::uint16_t* stage = fb.staging();
    Canvas first_canvas{ stage, FRAME_W, FRAME_H };
    render_page(first_canvas, 0);
    if (!fb.submit_frame(0, stage, static_cast<std::size_t>(FRAME_W) * FRAME_H)) return 7;

    int page = 0, front = 0;
    long frame = 0;

    int  touch_x = 0, touch_y = 0;   // last raw position (single-touch or MT slot 0)
    bool btn_down = false;           // BTN_TOUCH/BTN_LEFT press state
    bool mt_down  = false;           // ABS_MT_TRACKING_ID >= 0 press state
    bool touch_pass_printed = false;

    std::cout << "PHASE3_PS_READY (fps=" << fps
              << "; tap bottom tab = jump, tap elsewhere = next page, Ctrl-C to stop)\n";

    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;
    while (!g_stop) {
        // --- read touch events (non-blocking, SYN_REPORT-aware) ---
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

                    if (sy >= FRAME_H - 80) {          // bottom tab bar = hit a tab
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
        Canvas canvas{ stage, FRAME_W, FRAME_H };
        render_page(canvas, page);
        if (!fb.submit_frame(back, stage, static_cast<std::size_t>(FRAME_W) * FRAME_H)) return 8;
        front = back;

        ++frame;
        if (period > 0) usleep(period);
    }

    std::cout << "[3-PS] stopped after " << frame << " frames\n";
    close(touch_fd);
    return 0;
}
