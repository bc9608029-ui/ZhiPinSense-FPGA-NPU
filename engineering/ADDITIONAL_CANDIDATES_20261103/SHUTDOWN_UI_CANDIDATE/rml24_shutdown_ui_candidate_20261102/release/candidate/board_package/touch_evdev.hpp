#pragma once

// touch_evdev.hpp — Linux evdev touch input for the twelve-class LIVE UI
// (task 39e5 Gate C7).
//
// Finds the touch controller by VID/PID (default 1a86:e5e3, the board's
// USB2IIC_CTP_CONTROL), NOT by a hard-coded /dev/input/eventN — the event node
// index shifts with USB enumeration order and must never be assumed.  The device
// is opened O_NONBLOCK, its ABS_X / ABS_Y ranges are read with EVIOCGABS, and
// each SYN_REPORT is turned into a (touching, screen point) sample via the
// pure-logic mapping in touch_geometry.hpp.
//
// Robustness contract (frozen by Gate C7):
//   * a missing / unplugged controller must NEVER make the UI exit or block: open
//     is non-blocking, reads are non-blocking, and a hard error / EOF on the fd
//     returns false from drain() so the caller closes and schedules a re-enum;
//   * touching state follows BTN_TOUCH when the digitizer reports it, and falls
//     back to an ABS-event recency timeout otherwise (a touch screen that only
//     streams coordinates and stops when the finger lifts);
//   * raw coordinates are clamped by map_point(), so a bogus axis range or value
//     can never land a point outside the framebuffer.
//
// This header is the ONLY place that opens an event device.  It never touches the
// NPU, Flash, /dev/mem, /dev/udmabuf0, the class contract, the TX power, or the RF
// path.  POSIX-only (Linux board / WSL host); the pure-logic half lives in
// touch_geometry.hpp and is host-testable without any input device.

#include "touch_geometry.hpp"

#if defined(__unix__) || defined(__APPLE__)
#include <dirent.h>
#include <fcntl.h>
#include <linux/input.h>
#include <sys/ioctl.h>
#include <unistd.h>
#endif

#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace ui_touch {

struct TouchConfig {
    std::string input_dir = "/dev/input";
    std::string sysfs_dir = "/sys/class/input";
    unsigned vendor_id = 0x1a86;       // board touch controller VID
    unsigned product_id = 0xe5e3;      // board touch controller PID
    int screen_w = 1280;
    int screen_h = 720;
    bool swap_xy = false;
    bool invert_x = false;
    bool invert_y = false;
    std::int64_t abs_recency_ms = 200; // BTN_TOUCH-less fallback: lift after this quiet
};

struct TouchDeviceInfo {
    std::string device;        // e.g. "/dev/input/event2"
    std::string vid_pid;       // e.g. "1a86:e5e3"
    AxisInfo x;                // ABS_X range + invert
    AxisInfo y;                // ABS_Y range + invert
    bool swap_xy = false;
    bool connected = false;
    bool has_btn_touch = false;   // runtime: saw BTN_TOUCH (else recency fallback)
};

struct TouchSample {
    bool touching = false;
    Point point;               // mapped screen point (valid iff touching)
};

class TouchDevice {
public:
    explicit TouchDevice(const TouchConfig& cfg) : cfg_(cfg) {
        info_.x.invert = cfg_.invert_x;
        info_.y.invert = cfg_.invert_y;
        info_.swap_xy = cfg_.swap_xy;
    }
    ~TouchDevice() { close(); }
    TouchDevice(const TouchDevice&) = delete;
    TouchDevice& operator=(const TouchDevice&) = delete;

    // Find and open the matching event device (non-blocking).  Idempotent: a
    // subsequent call while connected is a no-op returning true.  Returns false
    // when no matching device exists or none could be opened.
    bool try_open();

    bool is_connected() const { return fd_ >= 0; }
    const TouchDeviceInfo& info() const { return info_; }
    int fd() const { return fd_; }

    // Drain the pending input_events into `out` (one entry per SYN_REPORT).
    // Non-blocking: returns immediately when the device has nothing buffered.
    // Returns false on a hard error / EOF (device removed) — the caller should
    // close() and schedule a periodic try_open().
    bool drain(std::vector<TouchSample>& out);

    void close() {
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
#endif
        info_.connected = false;
        info_.device.clear();
        info_.vid_pid.clear();
        raw_x_ = raw_y_ = 0;
        touching_ = false;
        saw_btn_touch_ = false;
    }

private:
#if defined(__unix__) || defined(__APPLE__)
    bool scan_and_open();
    void handle_event(const struct input_event& ev, std::vector<TouchSample>& out);
    TouchMapping mapping() const {
        TouchMapping m;
        m.x = info_.x;
        m.y = info_.y;
        m.swap_xy = info_.swap_xy;
        m.screen_w = cfg_.screen_w;
        m.screen_h = cfg_.screen_h;
        return m;
    }
    static std::int64_t now_ms() {
        return std::chrono::duration_cast<std::chrono::milliseconds>(
                   std::chrono::steady_clock::now().time_since_epoch())
            .count();
    }
#endif

    TouchConfig cfg_;
    TouchDeviceInfo info_;
    int fd_ = -1;
    int raw_x_ = 0;
    int raw_y_ = 0;
    bool touching_ = false;
    bool saw_btn_touch_ = false;
    std::int64_t last_abs_ms_ = 0;
};

#if defined(__unix__) || defined(__APPLE__)

// Read a sysfs hex attribute (e.g. /sys/class/input/eventN/device/id/vendor).
// Returns 0 (never throws) on any error so a malformed node is simply skipped.
inline unsigned read_hex_sysfs(const std::string& path) {
    FILE* f = std::fopen(path.c_str(), "r");
    if (!f) return 0;
    char buf[64] = {0};
    const std::size_t n = std::fread(buf, 1, sizeof(buf) - 1, f);
    std::fclose(f);
    if (n == 0) return 0;
    return static_cast<unsigned>(std::strtoul(buf, nullptr, 16));
}

bool TouchDevice::scan_and_open() {
    DIR* d = ::opendir(cfg_.input_dir.c_str());
    if (!d) return false;

    bool opened = false;
    struct dirent* e;
    while ((e = ::readdir(d)) != nullptr) {
        const std::string name = e->d_name;
        if (name.rfind("event", 0) != 0) continue;                    // only event*
        const std::string idx = name.substr(5);
        if (idx.empty() || idx.find_first_not_of("0123456789") != std::string::npos)
            continue;                                                 // event<digits> only
        const std::string dev_path = cfg_.input_dir + "/" + name;
        const std::string id_path = cfg_.sysfs_dir + "/" + name + "/device/id";
        const unsigned vid = read_hex_sysfs(id_path + "/vendor");
        const unsigned pid = read_hex_sysfs(id_path + "/product");
        if (vid != cfg_.vendor_id || pid != cfg_.product_id) continue;

        const int fd = ::open(dev_path.c_str(), O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;

        struct input_absinfo ax{}, ay{};
        if (::ioctl(fd, EVIOCGABS(ABS_X), &ax) == 0) {
            info_.x.min = static_cast<int>(ax.minimum);
            info_.x.max = static_cast<int>(ax.maximum);
        } else {
            info_.x.min = 0; info_.x.max = 0;
        }
        if (::ioctl(fd, EVIOCGABS(ABS_Y), &ay) == 0) {
            info_.y.min = static_cast<int>(ay.minimum);
            info_.y.max = static_cast<int>(ay.maximum);
        } else {
            info_.y.min = 0; info_.y.max = 0;
        }

        info_.device = dev_path;
        char vidpid[16];
        std::snprintf(vidpid, sizeof(vidpid), "%04x:%04x", vid, pid);
        info_.vid_pid = vidpid;
        info_.connected = true;
        info_.has_btn_touch = false;
        fd_ = fd;
        opened = true;
        break;
    }
    ::closedir(d);
    return opened;
}

bool TouchDevice::try_open() {
    if (fd_ >= 0) return true;
    return scan_and_open();
}

void TouchDevice::handle_event(const struct input_event& ev,
                               std::vector<TouchSample>& out) {
    if (ev.type == EV_ABS) {
        if (ev.code == ABS_X) raw_x_ = ev.value;
        else if (ev.code == ABS_Y) raw_y_ = ev.value;
        last_abs_ms_ = now_ms();
    } else if (ev.type == EV_KEY && ev.code == BTN_TOUCH) {
        touching_ = (ev.value != 0);
        saw_btn_touch_ = true;
        info_.has_btn_touch = true;
    } else if (ev.type == EV_SYN && ev.code == SYN_REPORT) {
        if (!saw_btn_touch_) {
            // Recency fallback: a digitizer that never reports BTN_TOUCH is
            // "pressed" only while ABS coordinates keep arriving.
            if (!touching_) {
                touching_ = true;
            } else if (now_ms() - last_abs_ms_ > cfg_.abs_recency_ms) {
                touching_ = false;
            }
        }
        TouchSample s;
        s.touching = touching_;
        s.point = map_point(raw_x_, raw_y_, mapping());
        out.push_back(s);
    }
}

bool TouchDevice::drain(std::vector<TouchSample>& out) {
    if (fd_ < 0) return false;
    for (;;) {
        struct input_event ev;
        const ssize_t n = ::read(fd_, &ev, sizeof(ev));
        if (n == static_cast<ssize_t>(sizeof(ev))) {
            handle_event(ev, out);
            continue;
        }
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) return true;   // drained
            if (errno == EINTR) continue;
            return false;                                               // hard error / ENODEV
        }
        return false;                                                   // EOF: device removed
    }
}

#else  // non-POSIX host: compile-safe no-op (tests only exercise touch_geometry.hpp)

bool TouchDevice::try_open() { (void)cfg_; return false; }
bool TouchDevice::drain(std::vector<TouchSample>&) { return false; }

#endif

}  // namespace ui_touch
