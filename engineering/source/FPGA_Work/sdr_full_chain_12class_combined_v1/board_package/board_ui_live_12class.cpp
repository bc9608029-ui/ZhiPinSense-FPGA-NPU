// board_ui_live_12class.cpp -- the twelve-class LIVE UI server (task 39e5 §四/§五).
//
// This is the receiving half of the Gate 8 / Gate 9 -> screen link:
//
//   Gate 8 (ResultFrame -> JSONL replay)  --sock=... --+
//   Gate 9 (SDR -> NPU -> UI JSONL)       --sock=... --+--> this server -> HDMI
//
//   * AF_UNIX SOCK_STREAM server (default /run/sdr_amr_ui.sock), poll(2)-driven,
//     non-blocking -- it NEVER blocks waiting on a peer (a slow or absent producer
//     cannot freeze the display; the §四 correction "禁止为了逐帧显示而阻塞Gate 9").
//   * Every line is strictly parsed (result_frame_v2_parse.hpp) and a malformed /
//     wrong-version / wrong-contract line is REJECTED (counted, never rendered).
//   * Valid frames are coalesced: the server drains the socket each display tick
//     and renders ONLY the latest legal frame, so a >30 Hz NPU feed is downsampled
//     to the display rate instead of queueing.  Counters follow the §四 contract:
//         received == valid (+ rejected),  rejected == 0 in a clean run,
//         rendered >= 1 && rendered <= valid,  coalesced == valid - rendered,
//         last_frame_id == the last frame_id actually rendered.
//   * MOCK frames render as MOCK, anomaly frames as ERROR, quiet feed -> STALE.
//   * HDMI access is gated on the frame_ctrl version register (0x40080000+0x0C ==
//     0x20230218) inside DirectFramebufferBackend::init(); the server re-checks and
//     prints UI_VERSION_CHECK before touching the framebuffer, so it can never write
//     0x40080000 under the NPU bitstream (the §四 correction).
//   * The ONLY device write is DirectFramebufferBackend::submit_frame() (scalar
//     volatile 16-bit stores).  It never touches the NPU, Flash, or Device::Open.
//
// iCraft-free, libiio-free: built by build_ui_live.sh with plain g++.

#include "board_common.hpp"
#include "result_frame_v2_parse.hpp"
#include "touch_evdev.hpp"
#include "touch_geometry.hpp"
#include "ui_state_map.hpp"
#include "unix_socket_server.hpp"

#include "direct_framebuffer_backend.hpp"
#include "ui_render.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

namespace {

constexpr int FRAME_W = 1280;
constexpr int FRAME_H = 720;

using Clock = std::chrono::steady_clock;

std::int64_t now_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               Clock::now().time_since_epoch())
        .count();
}

void print_stats(std::uint64_t received, std::uint64_t valid, std::uint64_t rejected,
                 std::uint64_t rendered, std::uint64_t coalesced,
                 std::uint64_t last_frame_id) {
    std::printf(
        "UI_STATS received=%llu valid=%llu rejected=%llu rendered=%llu "
        "coalesced=%llu last_frame_id=%llu\n",
        static_cast<unsigned long long>(received),
        static_cast<unsigned long long>(valid),
        static_cast<unsigned long long>(rejected),
        static_cast<unsigned long long>(rendered),
        static_cast<unsigned long long>(coalesced),
        static_cast<unsigned long long>(last_frame_id));
    std::fflush(stdout);
}

// Parse a hexadecimal CLI option (e.g. --touch-vendor=1a86).  Fail-closed: a
// malformed value throws, so a bad vendor id never silently disables matching.
unsigned parse_hex_opt(int argc, char** argv, const char* name, unsigned def) {
    const std::string s = board::get_opt(argc, argv, name, "");
    if (s.empty()) return def;
    char* end = nullptr;
    errno = 0;
    const unsigned long v = std::strtoul(s.c_str(), &end, 16);
    if (end == s.c_str() || *end != '\0' || errno == ERANGE)
        throw std::runtime_error(std::string("invalid hex for ") + name + ": '" + s + "'");
    return static_cast<unsigned>(v);
}

// Build the Touch-test page state from the device + navigation state.  A
// disconnected device still yields a connected=false info so the page renders
// "DISCONNECTED" rather than garbage.
ui::TouchInfo build_touch_info(const ui_touch::TouchDevice& dev,
                               const ui_touch::TouchNav& nav,
                               int screen_w, int screen_h) {
    ui::TouchInfo t;
    const ui_touch::TouchDeviceInfo& i = dev.info();
    t.connected = i.connected;
    t.taps = nav.tap_count();
    const ui_touch::Point& lp = nav.last_point();
    if (lp.valid) { t.last_x = lp.x; t.last_y = lp.y; }
    if (!i.connected) return t;

    t.device = i.device;
    t.vendor = i.vid_pid;
    char buf[64];
    if (i.x.max > i.x.min) std::snprintf(buf, sizeof buf, "%d .. %d", i.x.min, i.x.max);
    else std::snprintf(buf, sizeof buf, "n/a");
    t.axis_x = buf;
    if (i.y.max > i.y.min) std::snprintf(buf, sizeof buf, "%d .. %d", i.y.min, i.y.max);
    else std::snprintf(buf, sizeof buf, "n/a");
    t.axis_y = buf;
    t.mapping_x = std::string("(raw_") + (i.swap_xy ? "y" : "x") + ") -> " +
                  std::to_string(screen_w) + "px";
    t.mapping_y = std::string("(raw_") + (i.swap_xy ? "x" : "y") + ") -> " +
                  std::to_string(screen_h) + "px";
    if (i.x.invert) t.mapping_x += " (inv)";
    if (i.y.invert) t.mapping_y += " (inv)";
    return t;
}

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();

    try {
        const std::string sock_path =
            board::get_opt(argc, argv, "--sock", "/run/sdr_amr_ui.sock");
        const std::int64_t stale_ms = static_cast<std::int64_t>(
            board::opt_u64(argc, argv, "--stale-ms", 5000));
        const int tick_ms =
            static_cast<int>(board::opt_u64(argc, argv, "--tick-ms", 33));
        const std::string required_sha = board::get_opt(argc, argv, "--model-sha", "");
        if (tick_ms <= 0) {
            std::printf("UI_LIVE_FAIL error=bad_tick_ms\n");
            return 1;
        }

        // ---- touch input (Gate C7) ------------------------------------------
        // The touch controller is discovered by VID/PID (default 1a86:e5e3), never
        // by a hard-coded /dev/input/eventN.  Every knob is optional and fail-soft:
        // a missing controller only leaves the Touch page showing DISCONNECTED and
        // the bottom-nav inert -- it NEVER makes the UI exit or block.
        const bool touch_disabled = board::has_flag(argc, argv, "--no-touch");
        ui_touch::TouchConfig tcfg;
        tcfg.vendor_id = parse_hex_opt(argc, argv, "--touch-vendor", 0x1a86);
        tcfg.product_id = parse_hex_opt(argc, argv, "--touch-product", 0xe5e3);
        tcfg.swap_xy = board::has_flag(argc, argv, "--touch-swap-xy");
        tcfg.invert_x = board::has_flag(argc, argv, "--touch-invert-x");
        tcfg.invert_y = board::has_flag(argc, argv, "--touch-invert-y");
        const std::int64_t debounce_ms = static_cast<std::int64_t>(
            board::opt_u64(argc, argv, "--touch-debounce-ms", 400));
        ui_touch::TouchDevice touch_dev(tcfg);
        ui_touch::TouchNav touch_nav(FRAME_W, FRAME_H, debounce_ms);
        std::vector<ui_touch::TouchSample> touch_samples;
        const std::int64_t kTouchReconnectMs = 1000;
        std::int64_t last_touch_reconnect_ms = 0;
        bool touch_was_connected = false;
        if (!touch_disabled) touch_was_connected = touch_dev.try_open();
        if (touch_disabled) {
            std::printf("UI_TOUCH status=DISABLED\n");
        } else if (touch_was_connected) {
            std::printf("UI_TOUCH status=CONNECTED device=%s vid_pid=%s\n",
                        touch_dev.info().device.c_str(),
                        touch_dev.info().vid_pid.c_str());
        } else {
            std::printf("UI_TOUCH status=DISCONNECTED\n");
        }
        std::fflush(stdout);

        // 1. Start the JSON-lines server.  bind/listen must succeed before we claim
        //    readiness (the test scripts poll the socket node + UI_LIVE_READY).
        ui::UnixSocketServer server(sock_path);
        if (!server.start()) {
            std::printf("UI_LIVE_FAIL sock=%s error=socket_bind_failed\n",
                        sock_path.c_str());
            return 1;
        }
        std::printf("UI_LIVE_READY sock=%s\n", sock_path.c_str());
        std::fflush(stdout);

        // 2. Open the HDMI framebuffer.  init() resolves phys/capacity from sysfs,
        //    validates the double buffer, maps /dev/udmabuf0 + /dev/mem, and enforces
        //    the version gate BEFORE any register write (no 0x40080000 write under a
        //    wrong bitstream).  Re-check + print the explicit version line.
        dfb::Config cfg;
        dfb::RealIo io;
        dfb::DirectFramebufferBackend fb(cfg, io);
        if (!fb.init()) {
            std::printf("UI_LIVE_FAIL sock=%s error=framebuffer_init_failed\n",
                        sock_path.c_str());
            return 2;
        }
        const std::uint32_t version = fb.read_reg(cfg.version_offset);
        const bool version_ok = dfb::version_allows_write(version, cfg.expected_version);
        std::printf(
            "UI_VERSION_CHECK base=0x%08x version=0x%08x expected=0x%08x ok=%s\n",
            static_cast<unsigned>(cfg.frame_ctrl_base),
            static_cast<unsigned>(version),
            static_cast<unsigned>(cfg.expected_version),
            version_ok ? "YES" : "NO");
        std::fflush(stdout);
        if (!version_ok) {
            std::printf("UI_LIVE_FAIL error=version_mismatch\n");
            return 3;
        }

        const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
        if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 4;
        if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 5;

        std::uint16_t* stage = fb.staging();
        const std::size_t frame_px = static_cast<std::size_t>(FRAME_W) * FRAME_H;
        int front = 0;

        // Initial "no data yet" frame, so the PL never reads uninitialised memory.
        ui::UiState waiting;
        waiting.status = ui::Status::Stale;
        waiting.source = "SDR";
        waiting.top1 = "--";
        waiting.classes = &ui::classes_12();
        {
            ui::Canvas c0{stage, FRAME_W, FRAME_H};
            ui::render_main(c0, ui::palette_style_a(), waiting);
            if (!fb.submit_frame(0, stage, frame_px)) return 6;
        }

        // ---- live-loop counters (frozen §四 contract) -------------------------
        std::uint64_t received = 0, valid = 0, rejected = 0, rendered = 0,
                      coalesced = 0;
        std::uint64_t last_frame_id = 0;
        bool have_frame = false;
        std::int64_t last_frame_ms = 0;
        ui::UiState current;
        current.classes = &ui::classes_12();

        const std::int64_t kStatsIntervalMs = 1000;
        std::int64_t last_stats_ms = now_ms();

        while (!board::g_stop_requested) {
            ui::UnixSocketServer::PollResult pr = server.poll(tick_ms);
            if (pr.status == ui::UnixSocketServer::PollStatus::Error) break;

            // Drain: parse every complete line; coalesce valid frames to the latest.
            std::size_t valid_tick = 0;
            if (!pr.lines.empty()) {
                ui::UiState latest;
                for (const std::string& line : pr.lines) {
                    ++received;
                    ui::ParseOutcome po = ui::parse_result_frame_v2(line);
                    if (!po.ok) { ++rejected; continue; }
                    if (!required_sha.empty() &&
                        po.frame.model_sha != required_sha) { ++rejected; continue; }
                    ++valid;
                    latest = ui::map_to_state(po.frame);
                    last_frame_id = po.frame.frame_id;
                    last_frame_ms = now_ms();
                    ++valid_tick;
                }
                if (valid_tick > 0) {
                    current = latest;
                    have_frame = true;
                    ++rendered;                     // the latest legal frame this tick
                    coalesced += valid_tick - 1;    // the rest were superseded
                }
            }

            // Staleness: only meaningful once at least one frame has arrived.
            const std::int64_t tnow = now_ms();
            ui::UiState display = current;
            if (!have_frame) {
                display = waiting;
            } else if (ui::should_be_stale(tnow, last_frame_ms, stale_ms)) {
                display.status = ui::Status::Stale;
                display.age = ui::format_age(tnow - last_frame_ms);
            }

            // ---- touch (Gate C7) ---------------------------------------------
            // Fail-soft: drain the current device, feed the nav state machine, and
            // re-enumerate at most once per second when it is gone.  A disconnect
            // only flips the Touch-page badge -- it never touches the frame render
            // or the socket loop, and it never changes the class result.
            if (!touch_disabled) {
                if (touch_dev.is_connected()) {
                    touch_samples.clear();
                    if (!touch_dev.drain(touch_samples)) {
                        touch_dev.close();       // EOF / hard error: re-enum next cycle
                    } else {
                        for (const ui_touch::TouchSample& s : touch_samples)
                            touch_nav.on_sample(s.touching, s.point, tnow);
                    }
                } else if (tnow - last_touch_reconnect_ms >= kTouchReconnectMs) {
                    last_touch_reconnect_ms = tnow;
                    touch_dev.try_open();
                }
                const bool now_conn = touch_dev.is_connected();
                if (now_conn != touch_was_connected) {
                    touch_was_connected = now_conn;
                    std::printf("UI_TOUCH status=%s device=%s\n",
                                now_conn ? "RECONNECTED" : "DISCONNECTED",
                                now_conn ? touch_dev.info().device.c_str() : "");
                    std::fflush(stdout);
                }
            }
            display.touch = build_touch_info(touch_dev, touch_nav, FRAME_W, FRAME_H);

            {
                ui::Canvas canvas{stage, FRAME_W, FRAME_H};
                const ui::Palette& pal = ui::palette_style_a();
                switch (touch_nav.active_page()) {
                    case 1: ui::render_diag(canvas, pal, display); break;
                    case 2: ui::render_touch(canvas, pal, display); break;
                    default: ui::render_main(canvas, pal, display); break;
                }
                const int back = front ^ 1;
                if (!fb.submit_frame(back, stage, frame_px)) return 7;
                front = back;
            }

            if (tnow - last_stats_ms >= kStatsIntervalMs) {
                print_stats(received, valid, rejected, rendered, coalesced,
                            last_frame_id);
                last_stats_ms = tnow;
            }
        }

        print_stats(received, valid, rejected, rendered, coalesced, last_frame_id);
        std::printf(
            "UI_LIVE_STOP sock=%s received=%llu valid=%llu rejected=%llu "
            "rendered=%llu coalesced=%llu last_frame_id=%llu\n",
            sock_path.c_str(), static_cast<unsigned long long>(received),
            static_cast<unsigned long long>(valid),
            static_cast<unsigned long long>(rejected),
            static_cast<unsigned long long>(rendered),
            static_cast<unsigned long long>(coalesced),
            static_cast<unsigned long long>(last_frame_id));
        std::fflush(stdout);
        server.stop();   // close + unlink the socket node
        return 0;
    } catch (const std::exception& e) {
        std::printf("UI_LIVE_FAIL error=%s\n", e.what());
        return 1;
    }
}
