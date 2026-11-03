// board_ui_live_rml23.cpp -- the RML23 23-class LIVE UI server (M29 Phase F5).
//
// This is the receiving half of the Gate 8 / Gate 9 -> screen link:
//
//   Gate 8 (ResultFrame -> JSONL replay)  --sock=... --+
//   Gate 9 (SDR -> NPU -> UI JSONL)       --sock=... --+--> this server -> HDMI
//
//   * AF_UNIX SOCK_STREAM server (default /run/sdr_amr_ui.sock), poll(2)-driven,
//     non-blocking -- it NEVER blocks waiting on a peer (a slow or absent producer
//     cannot freeze the display; the §四 correction "禁止为了逐帧显示而阻塞Gate 9").
//   * Every line is strictly parsed (result_frame_rml23_parse.hpp) and a malformed /
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
//   * Work mode / run state are DISPLAYED ONLY: they arrive on each result frame
//     (result_frame_rml23_parse.hpp + ui_state_map.hpp map the producer's authoritative
//     work_mode / run_state tokens).  The reverse control channel is owned by the
//     Gate 9 producer, NOT this server -- the UI never self-modifies mode text to
//     fake effectiveness.
//
// iCraft-free, libiio-free: built by build_ui_live.sh with plain g++.

#include "board_common.hpp"
#include "control_client.hpp"
#include "result_frame_rml24_final_parse.hpp"
#include "touch_evdev.hpp"
#include "touch_geometry.hpp"
#include "touch_mode_control.hpp"
#include "ui_state_map.hpp"
#include "ui_dirty_state.hpp"
#include "unix_socket_server.hpp"

#include "direct_framebuffer_backend.hpp"
#include "ui_render.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>

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
                 std::uint64_t last_frame_id, std::uint64_t state_received) {
    std::printf(
        "UI_STATS received=%llu valid=%llu rejected=%llu rendered=%llu "
        "coalesced=%llu last_frame_id=%llu state_received=%llu\n",
        static_cast<unsigned long long>(received),
        static_cast<unsigned long long>(valid),
        static_cast<unsigned long long>(rejected),
        static_cast<unsigned long long>(rendered),
        static_cast<unsigned long long>(coalesced),
        static_cast<unsigned long long>(last_frame_id),
        static_cast<unsigned long long>(state_received));
    std::fflush(stdout);
}

// Log-facing status name (underscore-separated), distinct from the on-screen
// status_label() ("STALE DATA" -> "STALE_DATA", "NO SIGNAL" -> "NO_SIGNAL").
const char* status_log_name(ui::Status s) {
    switch (s) {
        case ui::Status::Live:          return "LIVE";
        case ui::Status::Stale:         return "STALE_DATA";
        case ui::Status::Error:         return "ERROR";
        case ui::Status::Mock:          return "MOCK";
        case ui::Status::NoSignal:      return "NO_SIGNAL";
        case ui::Status::Waiting:       return "WAITING";
        case ui::Status::Acquiring:     return "ACQUIRING";
        case ui::Status::SignalPresent: return "SIGNAL_PRESENT";
        case ui::Status::Stopped:       return "STOPPED";
        default:                        return "UNKNOWN";
    }
}

// Periodic touch-mode-control counters (M16).  Counters only -- the acceptance
// verdict lives in print_control_result(), emitted once at exit.
void print_control_stats(const mctl::ModeControlState& st) {
    std::printf(
        "TOUCH_CONTROL_STATS control_taps=%llu commands_sent=%llu "
        "commands_applied=%llu commands_rejected=%llu commands_timeout=%llu "
        "duplicate_commands=%llu connected=%s\n",
        static_cast<unsigned long long>(st.control_taps),
        static_cast<unsigned long long>(st.commands_sent),
        static_cast<unsigned long long>(st.commands_applied),
        static_cast<unsigned long long>(st.commands_rejected),
        static_cast<unsigned long long>(st.commands_timeout),
        static_cast<unsigned long long>(st.duplicate_commands),
        st.connected() ? "yes" : "no");
    std::fflush(stdout);
}

// One-shot acceptance verdict (M16).  PASS requires at least one command, every
// sent command applied, and zero reject / timeout / duplicate.  Emitted at exit;
// the board acceptance script greps this line rather than inferring PASS itself.
// [M18-SW1 Task C] the run_id is embedded so the acceptance can prove the result
// belongs to THIS round (a PASS from a different run_id is rejected).
void print_control_result(const mctl::ModeControlState& st, const std::string& run_id) {
    const bool pass = st.commands_sent > 0 &&
                      st.commands_applied == st.commands_sent &&
                      st.commands_rejected == 0 &&
                      st.commands_timeout == 0 &&
                      st.duplicate_commands == 0;
    const std::string rid = run_id.empty() ? std::string() : (" run_id=" + run_id);
    std::printf(
        "TOUCH_CONTROL_RESULT result=%s commands_sent=%llu commands_applied=%llu "
        "commands_rejected=%llu commands_timeout=%llu duplicate_commands=%llu%s\n",
        pass ? "PASS" : "FAIL",
        static_cast<unsigned long long>(st.commands_sent),
        static_cast<unsigned long long>(st.commands_applied),
        static_cast<unsigned long long>(st.commands_rejected),
        static_cast<unsigned long long>(st.commands_timeout),
        static_cast<unsigned long long>(st.duplicate_commands),
        rid.c_str());
    std::fflush(stdout);
}

// [M18-SW1 Task A] emit one TOUCH_EVENT diagnostic line to the LOG FILE (never the
// control serial).  Every physical touch sequence and command lifecycle stage is
// logged so a "first click did nothing" can be reconstructed from the log.
void emit_touch_event(const mctl::TouchEvent& e) {
    std::printf("%s\n", mctl::touch_event_line(e).c_str());
    std::fflush(stdout);
}

// M17 Task G runtime line: proves the idle path is no longer re-flipping.  When
// the feed is quiet (received=0/valid=0/rendered=0) `skips` grows once per tick
// and `submits` stays at the single startup frame, so the ~32% idle CPU is gone.
void print_runtime_stats(const ui::FlipScheduler& sched) {
    std::printf("UI_RUNTIME_STATS submits=%llu skips=%llu\n",
                static_cast<unsigned long long>(sched.submits),
                static_cast<unsigned long long>(sched.skips));
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
            board::get_opt(argc, argv, "--sock", "/run/sdr_amr_ui_rml24_final.sock");
        const std::int64_t stale_ms = static_cast<std::int64_t>(
            board::opt_u64(argc, argv, "--stale-ms", 5000));
        const bool display_diagnostic = board::has_flag(argc, argv, "--display-diagnostic");
        const bool display_static = board::has_flag(argc, argv, "--display-static");
        const std::uint64_t refresh_hz =
            board::opt_u64(argc, argv, "--display-refresh-hz", 30);
        const std::string required_sha = board::get_opt(argc, argv, "--model-sha", "");
        // [M18-SW1 Task C] --run-id tags this round so the acceptance result line can
        // be proven to belong to THIS round (a stale PASS from another run_id is
        // rejected).  --verbose / --stats-interval are Task B: periodic UI_STATS and
        // UI_RUNTIME_STATS are OFF by default; they run only when explicitly enabled.
        const std::string run_id = board::get_opt(argc, argv, "--run-id", "");
        const bool verbose = board::has_flag(argc, argv, "--verbose");
        const std::uint64_t stats_interval_sec =
            board::opt_u64(argc, argv, "--stats-interval", 0);
        const std::int64_t stats_interval_ms =
            verbose ? 1000 : static_cast<std::int64_t>(stats_interval_sec) * 1000;
        // --tick-ms wins when given; otherwise derive from --display-refresh-hz.
        int tick_ms = static_cast<int>(board::opt_u64(argc, argv, "--tick-ms", 0));
        if (tick_ms <= 0) {
            if (refresh_hz == 0) {
                std::printf("UI_LIVE_FAIL error=bad_refresh_hz\n");
                return 1;
            }
            tick_ms = static_cast<int>(1000 / refresh_hz);
            if (tick_ms < 1) tick_ms = 1;
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

        // ---- M16 control client (reverse control channel) ---------------------
        // The UI is a pure CLIENT of the Gate 9 producer's control socket.  It can
        // start before the producer: the third-page buttons stay inert until the
        // socket appears, and the client reconnects on a timer (<= control_reconnect_ms).
        // It NEVER binds or unlinks the producer's socket node -- the producer stays
        // the sole owner.  All I/O is non-blocking so it can never stall render/touch.
        const std::string ctl_sock = board::get_opt(argc, argv, "--ctl-sock",
                                                    "/run/sdr_amr_control_rml24_final.sock");
        const std::int64_t control_timeout_ms = static_cast<std::int64_t>(
            board::opt_u64(argc, argv, "--control-timeout-ms", 2000));
        const std::int64_t control_reconnect_ms = static_cast<std::int64_t>(
            board::opt_u64(argc, argv, "--control-reconnect-ms", 1000));
        ctl::ControlClient ctl_client(ctl_sock);
        mctl::ControlTapDetector control_taps(debounce_ms);
        mctl::ModeControlState mctl_state;
        std::int64_t last_ctl_reconnect_ms = -1000000;
        bool ctl_was_connected = false;   // [M18-SW1 Task B] dedup UI_CTL transitions
        std::string last_ctl_stats_key;   // [M18-SW1 Task B] TOUCH_CONTROL_STATS on change

        // [M18-SW1 Task A] control-driven redraw detection for the render_requested /
        // render_submitted TOUCH_EVENT diagnostics: snapshot the control-relevant
        // fields and flip only while a control value actually moved.
        std::uint64_t prev_pending_cid = 0, prev_applied_cid = 0, prev_ctl_taps = 0;
        std::string prev_cmd_status = "--", prev_feedback = "--", prev_last_cmd = "--";
        int prev_pressed = -1;
        bool prev_ctl_conn = false;

        // The scan integration restores the fourth MODE page.  Only that page may
        // send producer commands; CLASSIFY/SPECTRUM/CONSTELLATION stay display-only.
        // [M18-SW1 Task A] the CONNECTION check now precedes request(), so a tap on
        // a disconnected control channel NEVER advances requested_* (that was the
        // "first click did nothing" bug: request() was called first, so a dead tap
        // silently mutated state and the real click later looked idempotent).  Every
        // outcome is reported once as feedback AND a TOUCH_EVENT diagnostic line.
        auto handle_control_tap = [&](int btn, std::int64_t tnow) {
            if (touch_nav.active_page() != 3) return;
            mctl::TouchEvent ev;
            ev.seq = control_taps.sequence_id();
            ev.phase = "command";
            ev.touch_down_x = control_taps.down_x();
            ev.touch_down_y = control_taps.down_y();
            ev.touch_up_x = control_taps.up_x();
            ev.touch_up_y = control_taps.up_y();
            ev.hit_target = btn;

            if (!ctl_client.is_connected()) {
                ev.final_state = "DISCONNECTED";
                mctl_state.set_feedback("CONTROL DISCONNECTED");
                emit_touch_event(ev);
                return;
            }
            std::string line;
            const mctl::ModeControlState::RequestOutcome outcome =
                mctl_state.request_ex(btn, tnow, line);
            if (outcome == mctl::ModeControlState::RequestOutcome::Idempotent) {
                ev.final_state = "IDEMPOTENT";
                emit_touch_event(ev);
                return;
            }
            if (outcome == mctl::ModeControlState::RequestOutcome::Duplicate) {
                ev.final_state = "DUPLICATE";
                emit_touch_event(ev);
                return;
            }
            if (outcome == mctl::ModeControlState::RequestOutcome::Invalid) {
                ev.final_state = "INVALID";
                emit_touch_event(ev);
                return;
            }
            ev.command_enqueued = true;
            ev.line = line;
            if (ctl_client.send_line(line)) {
                ev.command_sent = true;
                mctl_state.on_sent(line, tnow);
                ev.final_state = "PENDING";
                std::printf("UI_CTL_TAP button=%d line=%s\n", btn, line.c_str());
                std::fflush(stdout);
            } else {
                ev.final_state = "SEND_FAILED";
                mctl_state.set_feedback("SEND FAILED");
            }
            emit_touch_event(ev);
        };

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

        // Headless mode (host process-level test): skip the HDMI framebuffer and
        // the render/flip path entirely.  The data-socket loop, parse, staleness
        // and logging below still run, so the REAL binary can be driven over a
        // real AF_UNIX data socket without board hardware (the UI_STATE_RX log is
        // the observable).  On the board --headless is simply never passed.
        const bool headless = board::has_flag(argc, argv, "--headless");

        dfb::Config cfg;
        dfb::RealIo io;
        dfb::DirectFramebufferBackend fb(cfg, io);   // constructed; init'd only when !headless

        // Shared by the framebuffer path and (headless) the live loop below.
        std::uint16_t* stage = nullptr;
        const std::size_t frame_px = static_cast<std::size_t>(FRAME_W) * FRAME_H;
        int front = 0;
        ui::FlipScheduler flip_sched;   // event-driven flips (M17 Task E/G)
        // Initial "no data yet" frame, so the PL never reads uninitialised memory.
        ui::UiState waiting;
        waiting.status = ui::Status::Waiting;   // never "STALE": no valid message yet
        waiting.source = "SDR";
        waiting.top1 = "--";
        waiting.classes = &ui::classes_24();
        waiting.model_mode = "RML24-BF16-RAW";
        waiting.class_count = 24;

        if (headless) {
            std::printf("UI_HEADLESS_MODE sock=%s\n", sock_path.c_str());
            std::fflush(stdout);
        } else {
            // 2. Open the HDMI framebuffer.  init() resolves phys/capacity from
            // sysfs, validates the double buffer, maps /dev/udmabuf0 + /dev/mem, and
            // enforces the version gate BEFORE any register write (no 0x40080000
            // write under a wrong bitstream).  Re-check + print the version line.
            std::printf("UI_FB_INIT sock=%s\n", sock_path.c_str());
            std::fflush(stdout);
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
            stage = fb.staging();

        // Task B startup ordering fix (stripes-before-ready).  The PL's frame
        // read starts scanning the framebuffer base (rd_addr) as soon as it is
        // programmed, and display_en is 1 at reset, so programming rd_addr BEFORE a
        // valid frame exists makes the PL read whatever was left in DDR.  Fix:
        //   a. clear BOTH frames to black (valid content for any buffer the PL picks)
        //   b. render the initial "no data yet" frame into staging
        //   c. submit_frame(0): copy + sync + flip (buffer select = 0)
        //   d. ONLY THEN program rd_addr, so the PL's first read is already valid.
        if (display_diagnostic) {
            // Pure read-only probe: report framebuffer + display timing registers
            // and exit without writing a single register (bring-up audit for B4).
            std::printf(
                "DISPLAY_DIAGNOSTIC phys=0x%llx capacity=%llu frames=%d "
                "frame_bytes=%llu version=0x%08x h_sync=0x%08x v_sync=0x%08x "
                "vtc_enable=0x%08x disable_hdmi=0x%08x\n",
                static_cast<unsigned long long>(fb.phys_addr()),
                static_cast<unsigned long long>(fb.capacity()), cfg.num_frames,
                static_cast<unsigned long long>(cfg.frame_bytes()),
                static_cast<unsigned>(version),
                static_cast<unsigned>(fb.read_reg(cfg.h_sync_offset)),
                static_cast<unsigned>(fb.read_reg(cfg.v_sync_offset)),
                static_cast<unsigned>(fb.read_reg(cfg.vtc_enable_offset)),
                static_cast<unsigned>(fb.read_reg(cfg.disable_hdmi_offset)));
            std::fflush(stdout);
            return 0;
        }

        // M17 Task F: blank the HDMI output BEFORE touching the framebuffer or
        // rd_addr.  display_en is 1 at reset, so the PL scans the reset rd_addr
        // (0x7E00000) as garbage from bitstream load until rd_addr is programmed.
        // Blank first, bring the framebuffer up, then un-blank only when frame 0 is
        // valid and rd_addr points at it -- the PL's first scan is then clean.
        if (!fb.set_display_enable(false)) return 4;
        if (!fb.clear_all_frames()) return 5;

        {
            // Render the initial "no data yet" frame, so the PL never reads
            // uninitialised memory (decls hoisted above; shared with the live loop).
            ui::Canvas c0{stage, FRAME_W, FRAME_H};
            ui::render_main(c0, ui::theme_default(), waiting);
            if (!fb.submit_frame(0, stage, frame_px)) return 6;
            flip_sched.mark_submitted(waiting, 0, now_ms());
        }

        // Program the framebuffer base only AFTER frame 0 is valid (see above).
        const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
        if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 7;

        // Un-blank: the PL's first scan now reads a valid frame 0.
        if (!fb.set_display_enable(true)) return 8;

        std::printf(
            "UI_FB_READY phys=0x%llx frames=%d frame_bytes=%llu refresh_hz=%llu\n",
            static_cast<unsigned long long>(fb.phys_addr()), cfg.num_frames,
            static_cast<unsigned long long>(cfg.frame_bytes()),
            static_cast<unsigned long long>(refresh_hz));
        std::fflush(stdout);

        if (display_static) {
            // Bring-up mode: hold a static frame and keep re-submitting it through
            // the full render->sync->flip->swap path at the refresh rate, so the
            // board test can separate a tear in the flip path from a tear caused by
            // the live data feed.  No socket poll, no live classification.
            ui::UiState still;
            still.status = ui::Status::Live;
            still.source = "SDR";
            still.top1 = "STATIC";
            still.snr = "--";
            still.lat = "--";
            still.frame = "0";
            still.classes = &ui::classes_24();
            still.model_mode = "RML24-BF16-RAW";
            still.class_count = 24;
            still.work_mode = "FIXED";
            still.running = true;
            while (!board::g_stop_requested) {
                {
                    ui::Canvas cs{stage, FRAME_W, FRAME_H};
                    ui::render_main(cs, ui::theme_default(), still);
                }
                const int back = front ^ 1;
                if (!fb.submit_frame(back, stage, frame_px)) return 9;
                front = back;
                std::this_thread::sleep_for(std::chrono::milliseconds(tick_ms));
            }
            return 0;
        }
        }   // end if (!headless)

        // ---- live-loop counters (frozen §四 contract) -------------------------
        std::uint64_t received = 0, valid = 0, rejected = 0, rendered = 0,
                      coalesced = 0;
        std::uint64_t state_received = 0;   // valid type:"state" heartbeats accepted
        std::uint64_t state_rejected = 0;   // state-intent lines rejected by the schema
        std::string state_reject_reason;    // reason for the last rejected state line
        std::uint64_t last_frame_id = 0;    // set ONLY by result frames (never state)
        // Freshness is split (errata 39e5): "has a classification" and "link is
        // fresh" are NOT one boolean.  Both use the UI's own steady_clock (never
        // producer timestamp_us, whose epoch may differ).
        bool have_valid_message = false;    // any valid state OR result received
        bool have_valid_result = false;     // any valid result received
        std::int64_t last_valid_message_rx = 0;  // steady_clock ms: last valid state/result
        std::int64_t last_valid_result_rx = 0;   // steady_clock ms: last valid result
        bool last_running = true;      // last known run state (STOPPED -> false)
        bool producer_gone = false;    // peer disconnected (process exited / crashed)
        std::int64_t last_ui_rx_stats_ms = 0;    // steady 1000 ms UI_RX_STATS report
        std::int64_t last_ui_rx_result_ms = 0;   // steady rate-limit for result UI_RX lines
        ui::Status last_status = ui::Status::Waiting;   // for UI_STATUS transition logs
        std::string last_status_reason = "initial";
        ui::UiState current;
        current.classes = &ui::classes_24();
        current.model_mode = "RML24-BF16-RAW";
        current.class_count = 24;

        std::int64_t last_stats_ms = now_ms();

        while (!board::g_stop_requested) {
            ui::UnixSocketServer::PollResult pr = server.poll(tick_ms);
            if (pr.status == ui::UnixSocketServer::PollStatus::Error) break;
            if (pr.status == ui::UnixSocketServer::PollStatus::ClientGone) {
                producer_gone = true;   // the producer process is gone
            }

            // Drain: parse every complete line.  A "state" line (type:"state")
            // updates mode/run WITHOUT touching the last valid classification; a
            // "result" line updates the classification.  Result frames are parsed
            // first (their `type` is disjoint from a state event's), so a
            // state-intent line is never mistaken for a result and vice versa.  A
            // state event in a tick is applied AFTER the result frame so a STOPPED
            // transition is never overwritten by the last RUNNING result frame.
            std::size_t valid_tick = 0;
            bool have_state_tick = false;
            ui::StateEvent state_tick;
            if (!pr.lines.empty()) {
                producer_gone = false;  // a live producer just spoke
                ui::UiState latest;
                for (const std::string& line : pr.lines) {
                    ++received;
                    ui::ParseOutcome po = ui::parse_result_frame_rml24_final(line);
                    if (po.ok) {
                        if (!required_sha.empty() &&
                            po.frame.model_sha != required_sha) {
                            ++rejected;
                            const std::int64_t tr = now_ms();
                            if (tr - last_ui_rx_result_ms >= 1000) {
                                last_ui_rx_result_ms = tr;
                                std::printf("UI_RX type=result version=%s valid=0 "
                                            "reason=model_sha_mismatch\n",
                                            po.frame.version.c_str());
                                std::fflush(stdout);
                            }
                            continue;
                        }
                        ++valid;
                        latest = ui::map_to_state_rml24_final(po.frame);
                        last_running = (po.frame.run_state != "STOPPED");
                        last_frame_id = po.frame.frame_id;   // result-only: state never sets this
                        const std::int64_t tr = now_ms();
                        last_valid_message_rx = tr;
                        last_valid_result_rx = tr;
                        have_valid_message = true;
                        have_valid_result = true;
                        ++valid_tick;
                        if (tr - last_ui_rx_result_ms >= 1000) {
                            last_ui_rx_result_ms = tr;
                            std::printf("UI_RX type=result version=%s valid=1 reason=-\n",
                                        po.frame.version.c_str());
                            std::fflush(stdout);
                        }
                        // M16: result frames carry the applied mode/run but no command
                        // id -- advance applied_* only (never resolve a pending command,
                        // which cannot be proven from a frame alone).
                        if (!po.frame.work_mode.empty()) {
                            mode_ctl::ModeKind mk = mode_ctl::ModeKind::Fixed;
                            if (mode_ctl::mode_from_token(po.frame.work_mode, mk))
                                mctl_state.observe_applied(mk, po.frame.run_state != "STOPPED");
                        }
                        continue;
                    }
                    const ui::StateEvent se = ui::parse_state_frame(line);
                    if (se.ok) {
                        state_tick = se;
                        have_state_tick = true;
                        ++state_received;
                        last_running = (se.run_state != "STOPPED");
                        last_valid_message_rx = now_ms();   // a valid state refreshes freshness
                        have_valid_message = true;
                        std::printf("UI_RX type=state version=%s valid=1 reason=-\n",
                                    se.version.c_str());
                        std::fflush(stdout);
                        // M16: the state event is producer-authoritative applied
                        // evidence (it carries the command_id that caused it).
                        mode_ctl::ModeKind mk = mode_ctl::ModeKind::Fixed;
                        mode_ctl::mode_from_token(se.work_mode, mk);
                        mctl_state.sync_applied(mk, se.run_state != "STOPPED", se.command_id);
                        continue;
                    }
                    // Neither a valid result nor a valid state: a rejected state-intent
                    // line (its state-schema parse error is the rejection reason).
                    ++rejected;
                    ++state_rejected;
                    state_reject_reason = se.error;
                    std::printf("UI_RX type=state version=%s valid=0 reason=%s\n",
                                se.version.empty() ? "-" : se.version.c_str(),
                                se.error.empty() ? "parse_failed" : se.error.c_str());
                    std::fflush(stdout);
                }
                if (valid_tick > 0) {
                    current = latest;
                    have_valid_result = true;
                    ++rendered;                     // the latest legal frame this tick
                    coalesced += valid_tick - 1;    // the rest were superseded
                }
                if (have_state_tick) {
                    ui::apply_state_event(current, state_tick);
                }
            }

            // Freshness / status (errata 39e5).  "Has a classification"
            // (have_valid_result / last_valid_result_rx) and "link is fresh"
            // (have_valid_message / last_valid_message_rx) are separate.  Precedence,
            // highest first:
            //   1. no valid state/result yet            -> WAITING (never STALE)
            //   2. producer gone (EOF / crash)          -> STALE (disconnected)
            //   3. quiet > stale_ms                     -> STALE (timeout)
            //   4. STOPPED (still heartbeating)         -> STOPPED
            //   5. presence NO_SIGNAL (signal gone)     -> NO SIGNAL (an older
            //      classification is NOT shown)
            //   6. presence ACQUIRING                   -> ACQUIRING
            //   7. presence SIGNAL_PRESENT              -> LIVE when a classification
            //      exists (the last result holds), else SIGNAL PRESENT (classifying)
            //   8. presence empty / unknown             -> LIVE if a classification
            //      exists, else NO SIGNAL (never fabricate a state)
            const std::int64_t tnow = now_ms();
            ui::UiState display = current;
            std::string status_reason;
            if (!have_valid_message) {
                display = waiting;                    // Waiting
                status_reason = "initial";
            } else if (producer_gone) {
                display.status = ui::Status::Stale;
                display.age = ui::format_age(tnow - last_valid_message_rx);
                status_reason = "disconnected";
            } else if (ui::should_be_stale(tnow, last_valid_message_rx, stale_ms)) {
                display.status = ui::Status::Stale;
                display.age = ui::format_age(tnow - last_valid_message_rx);
                status_reason = "timeout";
            } else if (!last_running) {
                display.status = ui::Status::Stopped;
                status_reason = "stopped";
            } else if (display.presence == "NO_SIGNAL") {
                display.status = ui::Status::NoSignal;
                status_reason = "valid_state";
            } else if (display.presence == "ACQUIRING") {
                display.status = ui::Status::Acquiring;
                status_reason = "valid_state";
            } else if (display.presence == "SIGNAL_PRESENT") {
                display.status = have_valid_result ? ui::Status::Live
                                                   : ui::Status::SignalPresent;
                status_reason = have_valid_result ? "valid_result" : "valid_state";
            } else {
                display.status = have_valid_result ? ui::Status::Live
                                                   : ui::Status::NoSignal;
                status_reason = have_valid_result ? "valid_result" : "valid_state";
            }

            // UI_STATUS: log exactly on a real transition (status or reason change),
            // never periodic spam.  Ages are -1 before the first message / result.
            const std::int64_t freshness_age_ms =
                have_valid_message ? (tnow - last_valid_message_rx) : -1;
            const std::int64_t result_age_ms =
                have_valid_result ? (tnow - last_valid_result_rx) : -1;
            if (display.status != last_status || status_reason != last_status_reason) {
                std::printf("UI_STATUS old=%s new=%s reason=%s freshness_age_ms=%lld\n",
                            status_log_name(last_status),
                            status_log_name(display.status),
                            status_reason.c_str(),
                            static_cast<long long>(freshness_age_ms));
                std::fflush(stdout);
                last_status = display.status;
                last_status_reason = status_reason;
            }

            // UI_RX_STATS: cumulative, at least once per second (steady 1000 ms).
            // last_valid_age_ms = link age (any message); last_result_age_ms = age
            // of the last classification (result only).  The two are the observable
            // proof that a state-only feed is fresh (small valid age) even when no
            // classification has arrived (large result age).
            if (tnow - last_ui_rx_stats_ms >= 1000) {
                last_ui_rx_stats_ms = tnow;
                std::printf("UI_RX_STATS state_valid=%llu result_valid=%llu "
                            "rejected=%llu last_valid_age_ms=%lld last_result_age_ms=%lld\n",
                            static_cast<unsigned long long>(state_received),
                            static_cast<unsigned long long>(valid),
                            static_cast<unsigned long long>(rejected),
                            static_cast<long long>(freshness_age_ms),
                            static_cast<long long>(result_age_ms));
                std::fflush(stdout);
            }

            // ---- M16 control client (reverse control channel) -----------------
            // Non-blocking reconnect / reply drain.  A producer restart shows up as
            // EOF on the control socket -> drop the client, clear any in-flight
            // request, and reconnect on the next timer tick (STATUS is then re-sent
            // so the producer's applied state re-becomes the sole authority).
            if (!ctl_client.is_connected()) {
                if (tnow - last_ctl_reconnect_ms >= control_reconnect_ms) {
                    last_ctl_reconnect_ms = tnow;
                    if (ctl_client.connect()) {
                        mctl_state.set_connected(true);
                        ctl_client.send_line("STATUS");
                    }
                }
            } else {
                const std::vector<std::string> replies = ctl_client.poll(0);
                if (!ctl_client.is_connected()) {
                    mctl_state.set_connected(false);
                } else {
                    // [M18-SW1 Task A] log ACCEPTED / APPLIED as TOUCH_EVENTs so the
                    // two-phase ack is reconstructable from the log.  ACCEPTED = a
                    // pending command_id was assigned this tick; APPLIED = at least one
                    // command applied this tick (counter delta, robust to two slots).
                    const std::uint64_t cid_before = mctl_state.pending_command_id();
                    const std::uint64_t applied_before = mctl_state.commands_applied;
                    for (const std::string& r : replies) mctl_state.on_reply(r, tnow);
                    if (cid_before == 0 && mctl_state.pending_command_id() != 0) {
                        mctl::TouchEvent ev;
                        ev.seq = control_taps.sequence_id();
                        ev.phase = "ack";
                        ev.command_id = mctl_state.pending_command_id();
                        ev.command_ack_received = true;
                        ev.hit_target = control_taps.hit_target();
                        ev.touch_down_x = control_taps.down_x();
                        ev.touch_down_y = control_taps.down_y();
                        ev.touch_up_x = control_taps.up_x();
                        ev.touch_up_y = control_taps.up_y();
                        ev.line = mctl_state.last_command_display();
                        ev.final_state = "PENDING";
                        emit_touch_event(ev);
                    }
                    if (mctl_state.commands_applied > applied_before) {
                        mctl::TouchEvent ev;
                        ev.seq = control_taps.sequence_id();
                        ev.phase = "applied";
                        ev.command_id = mctl_state.last_applied_command_id();
                        ev.command_applied = true;
                        ev.ack_latency_ms = mctl_state.last_ack_latency_ms();
                        ev.hit_target = control_taps.hit_target();
                        ev.touch_down_x = control_taps.down_x();
                        ev.touch_down_y = control_taps.down_y();
                        ev.touch_up_x = control_taps.up_x();
                        ev.touch_up_y = control_taps.up_y();
                        ev.line = mctl_state.last_command_display();
                        ev.final_state = "APPLIED";
                        emit_touch_event(ev);
                    }
                }
            }
            mctl_state.on_tick(tnow, control_timeout_ms);

            // [M18-SW1 Task B] UI_CTL logged exactly once per real CONNECTED <-> DISCONNECTED
            // transition (never a duplicate identical line, never periodic spam).
            const bool ctl_connected_now = mctl_state.connected();
            if (ctl_connected_now != ctl_was_connected) {
                ctl_was_connected = ctl_connected_now;
                std::printf("UI_CTL status=%s sock=%s\n",
                            ctl_connected_now ? "CONNECTED" : "DISCONNECTED",
                            ctl_sock.c_str());
                std::fflush(stdout);
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
                        for (const ui_touch::TouchSample& s : touch_samples) {
                            touch_nav.on_sample(s.touching, s.point, tnow);
                            // M16: the control-tap detector is fed on EVERY sample so
                            // its down/up edge state stays consistent; a returned button
                            // only acts on the MODE page + a connected control client.
                            const int btn = control_taps.on_sample(s.touching, s.point, tnow);
                            // [M18-SW1 Task A] down / up edges are logged as TOUCH_EVENTs
                            // (one per edge, never per sample) so a press that "did
                            // nothing" can be distinguished from a cancelled drag-out.
                            const mctl::ControlTapDetector::Edge edge = control_taps.last_edge();
                            if (edge == mctl::ControlTapDetector::Edge::Down) {
                                mctl::TouchEvent ev;
                                ev.seq = control_taps.sequence_id();
                                ev.phase = "down";
                                ev.touch_down_x = control_taps.down_x();
                                ev.touch_down_y = control_taps.down_y();
                                ev.hit_target = control_taps.hit_target();
                                emit_touch_event(ev);
                            } else if (edge == mctl::ControlTapDetector::Edge::Up) {
                                mctl::TouchEvent ev;
                                ev.seq = control_taps.sequence_id();
                                ev.phase = "up";
                                ev.touch_down_x = control_taps.down_x();
                                ev.touch_down_y = control_taps.down_y();
                                ev.touch_up_x = control_taps.up_x();
                                ev.touch_up_y = control_taps.up_y();
                                ev.hit_target = control_taps.hit_target();
                                ev.final_state = (btn >= 0) ? "TAP" : "CANCELLED";
                                emit_touch_event(ev);
                            }
                            if (btn >= 0) handle_control_tap(btn, tnow);
                        }
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

            // ---- M16: overlay the control state machine's view -----------------
            // requested_* is what the user last asked for via touch; applied_* is
            // producer-authoritative (== work_mode / running).  They diverge only
            // while a command is PENDING.
            display.work_mode = mctl_state.applied_mode_display();
            display.running = mctl_state.applied_running();
            display.requested_mode = mctl_state.requested_mode_display();
            display.requested_running = mctl_state.requested_running();
            display.ctl_connected = mctl_state.connected() ? "CONTROL CONNECTED"
                                                           : "CONTROL DISCONNECTED";
            display.last_command = mctl_state.last_command_display();
            display.command_status = mctl_state.command_status();
            display.control_taps = mctl_state.control_taps;
            // [M18-SW1 Task A] transient tap feedback + press-highlight.  pressed_button
            // is shown only on the MODE page (the buttons exist only there); on other
            // pages it is forced -1 so an off-page touch never triggers a spurious redraw.
            display.feedback = mctl_state.feedback();
            display.pressed_button =
                (touch_nav.active_page() == 3) ? control_taps.pressed_button() : -1;

            // [M18-SW1 Task A] control-driven redraw detection: true iff a control
            // field moved this tick (drives render_requested / render_submitted).
            const bool control_changed =
                prev_pending_cid != mctl_state.pending_command_id() ||
                prev_applied_cid != mctl_state.last_applied_command_id() ||
                prev_ctl_taps != mctl_state.control_taps ||
                prev_cmd_status != mctl_state.command_status() ||
                prev_feedback != mctl_state.feedback() ||
                prev_last_cmd != mctl_state.last_command_display() ||
                prev_pressed != display.pressed_button ||
                prev_ctl_conn != mctl_state.connected();
            prev_pending_cid = mctl_state.pending_command_id();
            prev_applied_cid = mctl_state.last_applied_command_id();
            prev_ctl_taps = mctl_state.control_taps;
            prev_cmd_status = mctl_state.command_status();
            prev_feedback = mctl_state.feedback();
            prev_last_cmd = mctl_state.last_command_display();
            prev_pressed = display.pressed_button;
            prev_ctl_conn = mctl_state.connected();

            // M17 Task E/G: event-driven flip.  Render + flip only when the display
            // content actually changed (new frame / state / control / touch / page),
            // so a quiet feed no longer re-flips every tick (no flicker, no idle CPU).
            const int page = touch_nav.active_page();
            if (!headless && flip_sched.should_submit(display, page, tnow)) {
                // [M18-SW1 Task A] a control-driven submit is bracketed by
                // render_requested / render_submitted TOUCH_EVENTs.
                if (control_changed) {
                    mctl::TouchEvent ev;
                    ev.seq = control_taps.sequence_id();
                    ev.phase = "render";
                    ev.render_requested = true;
                    ev.hit_target = control_taps.hit_target();
                    ev.final_state = "REQUESTED";
                    emit_touch_event(ev);
                }
                ui::Canvas canvas{stage, FRAME_W, FRAME_H};
                const ui::Theme& pal = ui::theme_default();
                switch (page) {
                    case 1: ui::render_parameters(canvas, pal, display); break;
                    case 2: ui::render_constellation(canvas, pal, display); break;
                    case 3: ui::render_mode(canvas, pal, display); break;
                    default: ui::render_main(canvas, pal, display); break;
                }
                const int back = front ^ 1;
                if (!fb.submit_frame(back, stage, frame_px)) return 10;
                front = back;
                flip_sched.mark_submitted(display, page, tnow);
                if (control_changed) {
                    mctl::TouchEvent ev;
                    ev.seq = control_taps.sequence_id();
                    ev.phase = "render";
                    ev.render_submitted = true;
                    ev.hit_target = control_taps.hit_target();
                    ev.final_state = "SUBMITTED";
                    emit_touch_event(ev);
                }
            }

            // [M18-SW1 Task B] TOUCH_CONTROL_STATS prints only when a control counter
            // actually changed (tap / send / apply / reject / timeout / duplicate /
            // connect), never a duplicate identical line.  UI_STATS / UI_RUNTIME_STATS
            // print only when --verbose / --stats-interval is given.
            const std::string ck =
                std::to_string(mctl_state.control_taps) + "|" +
                std::to_string(mctl_state.commands_sent) + "|" +
                std::to_string(mctl_state.commands_applied) + "|" +
                std::to_string(mctl_state.commands_rejected) + "|" +
                std::to_string(mctl_state.commands_timeout) + "|" +
                std::to_string(mctl_state.duplicate_commands) + "|" +
                (mctl_state.connected() ? "1" : "0");
            if (ck != last_ctl_stats_key) {
                last_ctl_stats_key = ck;
                print_control_stats(mctl_state);
            }
            if (stats_interval_ms > 0 &&
                tnow - last_stats_ms >= stats_interval_ms) {
                print_stats(received, valid, rejected, rendered, coalesced,
                            last_frame_id, state_received);
                print_runtime_stats(flip_sched);
                last_stats_ms = tnow;
            }
        }

        print_stats(received, valid, rejected, rendered, coalesced, last_frame_id,
                    state_received);
        print_control_stats(mctl_state);   // [M18-SW1 Task B] exit summary
        print_control_result(mctl_state, run_id);
        print_runtime_stats(flip_sched);
        std::printf(
            "UI_LIVE_STOP sock=%s received=%llu valid=%llu rejected=%llu "
            "rendered=%llu coalesced=%llu last_frame_id=%llu state_received=%llu\n",
            sock_path.c_str(), static_cast<unsigned long long>(received),
            static_cast<unsigned long long>(valid),
            static_cast<unsigned long long>(rejected),
            static_cast<unsigned long long>(rendered),
            static_cast<unsigned long long>(coalesced),
            static_cast<unsigned long long>(last_frame_id),
            static_cast<unsigned long long>(state_received));
        std::fflush(stdout);
        server.stop();   // close + unlink the data socket node
        return 0;
    } catch (const std::exception& e) {
        std::printf("UI_LIVE_FAIL error=%s\n", e.what());
        return 1;
    }
}
