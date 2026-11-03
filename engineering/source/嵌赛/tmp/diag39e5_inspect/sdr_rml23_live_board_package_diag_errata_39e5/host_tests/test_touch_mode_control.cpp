// test_touch_mode_control.cpp -- host tests for the third-page physical touch mode
// control (task 39e5 UI v3 M16): the ControlTapDetector (press/release -> one tap,
// drag cancels, long press = one command) and the ModeControlState request/apply
// state machine (touch only advances requested_*, only producer evidence advances
// applied_*, stale ids ignored, REJECT/TIMEOUT keep the actual mode, STOP lives in
// its own slot so a mode request never blocks it), plus a full loopback through the
// real control thread (control_channel.hpp) driven by ctl::ControlClient.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled -O2 -Wall -Wextra
// -Werror; also run under ASan/UBSan.

#include "../board_package/control_client.hpp"
#include "../board_package/control_channel.hpp"
#include "../board_package/touch_mode_control.hpp"
#include "../board_package/ui_dirty_state.hpp"
#include "../ui_sw/ui_render.hpp"

#include <cstdio>
#include <string>
#include <thread>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

ui_touch::Point pt(int x, int y) { return ui_touch::Point{x, y, true}; }

// ---- ControlTapDetector ------------------------------------------------------
void test_tap_detector() {
    // Geometry: FIXED button 0 spans x 25..415, y 90..190; a point inside it.
    const ui_touch::Point in_fixed = pt(200, 140);

    mctl::ControlTapDetector d;
    // press -> release inside the SAME button = one tap (the button index).
    check(d.on_sample(true, in_fixed, 100) == -1, "down inside FIXED -> no tap yet");
    check(d.on_sample(false, in_fixed, 200) == ui::mode_ui::kBtnFixed,
          "release inside FIXED -> tap on FIXED");

    // A long press is still ONE command, emitted only on release.
    mctl::ControlTapDetector d2;
    check(d2.on_sample(true, in_fixed, 300) == -1, "long press down -> no tap");
    check(d2.on_sample(true, in_fixed, 320) == -1, "long press hold (move inside) -> no tap");
    check(d2.on_sample(true, in_fixed, 340) == -1, "long press hold -> no tap");
    check(d2.on_sample(false, in_fixed, 360) == ui::mode_ui::kBtnFixed,
          "long press release -> exactly one tap");

    // A drag OUT of the button cancels (down inside, up outside -> no tap).
    mctl::ControlTapDetector d3;
    check(d3.on_sample(true, in_fixed, 400) == -1, "drag down inside -> no tap");
    check(d3.on_sample(true, pt(200, 400), 420) == -1, "drag moved outside -> no tap");
    check(d3.on_sample(false, pt(200, 400), 440) == -1, "drag release outside -> no tap");

    // Debounce: two consecutive taps within the window are folded to one.
    mctl::ControlTapDetector d4;
    check(d4.on_sample(true, in_fixed, 500) == -1, "tap1 down");
    check(d4.on_sample(false, in_fixed, 520) == ui::mode_ui::kBtnFixed, "tap1 release");
    check(d4.on_sample(true, in_fixed, 560) == -1, "tap2 down (within debounce)");
    check(d4.on_sample(false, in_fixed, 580) == -1, "tap2 release folded by debounce");
    check(d4.on_sample(true, in_fixed, 2000) == -1, "tap3 down (after debounce)");
    check(d4.on_sample(false, in_fixed, 2020) == ui::mode_ui::kBtnFixed, "tap3 release fires");

    // Each button index hit-tests to its own rect (AUTO LOCK / BAND SCAN / START / STOP).
    mctl::ControlTapDetector d5;
    check(d5.on_sample(true, pt(600, 140), 0) == -1, "AUTO LOCK down");
    check(d5.on_sample(false, pt(600, 140), 20) == ui::mode_ui::kBtnAutoLock, "AUTO LOCK tap");
    mctl::ControlTapDetector d6;
    check(d6.on_sample(true, pt(1000, 140), 0) == -1, "BAND SCAN down");
    check(d6.on_sample(false, pt(1000, 140), 20) == ui::mode_ui::kBtnBandScan, "BAND SCAN tap");
    mctl::ControlTapDetector d7;
    check(d7.on_sample(true, pt(300, 235), 0) == -1, "START down");
    check(d7.on_sample(false, pt(300, 235), 20) == ui::mode_ui::kBtnStart, "START tap");
    mctl::ControlTapDetector d8;
    check(d8.on_sample(true, pt(950, 235), 0) == -1, "STOP down");
    check(d8.on_sample(false, pt(950, 235), 20) == ui::mode_ui::kBtnStop, "STOP tap");

    // A tap in the nav band (y >= 630) is NOT a control button (no overlap).
    mctl::ControlTapDetector d9;
    check(d9.on_sample(true, pt(400, 680), 0) == -1, "nav-band down -> no control button");
    check(d9.on_sample(false, pt(400, 680), 20) == -1, "nav-band release -> no control button");
}

// ---- ModeControlState: request mapping --------------------------------------
void test_request_mapping() {
    mctl::ModeControlState s;
    std::string line;

    check(s.request(ui::mode_ui::kBtnFixed, 0, line) == false && line.empty(),
          "request FIXED while already FIXED is idempotent (no command)");

    // Each mode button -> the exact command line.
    mctl::ModeControlState s1;
    check(s1.request(ui::mode_ui::kBtnAutoLock, 0, line) && line == "SET_MODE AUTO_LOCK",
          "AUTO_LOCK -> SET_MODE AUTO_LOCK");
    mctl::ModeControlState s2;
    check(s2.request(ui::mode_ui::kBtnBandScan, 0, line) && line == "SET_MODE BAND_SCAN",
          "BAND_SCAN -> SET_MODE BAND_SCAN");
    mctl::ModeControlState s3;
    // START is idempotent while RUNNING, so put the machine in STOPPED first.
    s3.on_sent("STOP", 0);
    s3.on_reply("OK applied command_id=9 STOP", 0);
    check(s3.request(ui::mode_ui::kBtnStart, 0, line) && line == "START", "START -> START");
    mctl::ModeControlState s4;
    // Stop while running -> STOP.
    check(s4.request(ui::mode_ui::kBtnStop, 0, line) && line == "STOP", "STOP -> STOP");
    // Stop while already stopped -> idempotent.
    s4.on_sent("STOP", 0);
    s4.on_reply("OK applied command_id=1 STOP", 0);
    check(s4.request(ui::mode_ui::kBtnStop, 0, line) == false && line.empty(),
          "STOP while already STOPPED is idempotent");
}

// ---- ModeControlState: two slots + STOP high priority -----------------------
void test_two_slots() {
    mctl::ModeControlState s;
    std::string line;

    // Mode command pending; STOP must NOT be blocked by it.
    check(s.request(ui::mode_ui::kBtnAutoLock, 0, line) && line == "SET_MODE AUTO_LOCK",
          "request AUTO_LOCK");
    s.on_sent(line, 0);
    check(s.mode_pending().active && !s.run_pending().active,
          "mode slot active, run slot free");

    std::string stop_line;
    check(s.request(ui::mode_ui::kBtnStop, 0, stop_line) && stop_line == "STOP",
          "STOP is high-priority: allowed while a mode command is pending");
    s.on_sent(stop_line, 0);
    check(s.mode_pending().active && s.run_pending().active,
          "mode + run pending concurrently (two independent slots)");

    // A second mode tap while the mode slot is pending is a duplicate.
    std::string dup;
    const std::uint64_t before = s.duplicate_commands;
    check(s.request(ui::mode_ui::kBtnBandScan, 0, dup) == false && dup.empty(),
          "second mode tap while pending produces no command");
    check(s.duplicate_commands == before + 1, "duplicate tap counted");

    // Choosing a new mode during STOP is allowed (run stays stopped).
    mctl::ModeControlState s2;
    s2.on_sent("STOP", 0);
    s2.on_reply("OK applied command_id=1 STOP", 0);
    check(!s2.applied_running(), "applied run == STOPPED after STOP applied");
    std::string pick;
    check(s2.request(ui::mode_ui::kBtnBandScan, 0, pick) && pick == "SET_MODE BAND_SCAN",
          "choose a new mode during STOP is allowed");
}

// ---- ModeControlState: reply handling (ACCEPTED / APPLIED / ERR / stale) ----
void test_reply_handling() {
    mctl::ModeControlState s;
    s.on_sent("SET_MODE AUTO_LOCK", 100);
    check(s.command_status() == "PENDING", "on_sent -> PENDING");

    // ACCEPTED records the id but does NOT apply (two-phase).
    s.on_reply("OK accepted command_id=1 SET_MODE AUTO_LOCK", 110);
    check(s.command_status() == "PENDING", "ACCEPTED keeps PENDING");
    check(s.mode_pending().id == 1, "ACCEPTED records command_id=1");
    check(s.applied_mode() == mode_ctl::ModeKind::Fixed, "ACCEPTED does not apply");

    // APPLIED by the matching id applies + resolves.
    s.on_reply("OK applied command_id=1 SET_MODE AUTO_LOCK", 120);
    check(s.applied_mode() == mode_ctl::ModeKind::AutoLock, "APPLIED applies AUTO_LOCK");
    check(s.command_status() == "APPLIED", "APPLIED -> status APPLIED");
    check(s.commands_applied == 1, "commands_applied == 1");
    check(s.applied_mode_display() == "AUTO LOCK", "display name AUTO LOCK");

    // A stale (old) command id is ignored.
    mctl::ModeControlState s2;
    s2.on_sent("SET_MODE BAND_SCAN", 100);
    s2.on_reply("OK accepted command_id=5 SET_MODE BAND_SCAN", 110);
    s2.on_reply("OK applied command_id=3 SET_MODE BAND_SCAN", 120);   // old id
    check(s2.command_status() == "PENDING", "stale APPLIED (old id) ignored");
    check(s2.applied_mode() == mode_ctl::ModeKind::Fixed, "stale APPLIED does not apply");

    // REJECTED keeps the original applied mode.
    mctl::ModeControlState s3;
    s3.on_sent("SET_MODE BAND_SCAN", 100);
    s3.on_reply("ERR queue_full", 120);
    check(s3.applied_mode() == mode_ctl::ModeKind::Fixed, "REJECTED keeps applied FIXED");
    check(s3.command_status() == "REJECTED", "REJECTED -> status REJECTED");
    check(s3.commands_rejected == 1, "commands_rejected == 1");

    // TIMEOUT keeps the original applied mode.
    mctl::ModeControlState s4;
    s4.on_sent("SET_MODE BAND_SCAN", 100);
    s4.on_tick(3000, 2000);
    check(s4.applied_mode() == mode_ctl::ModeKind::Fixed, "TIMEOUT keeps applied FIXED");
    check(s4.command_status() == "TIMEOUT", "TIMEOUT -> status TIMEOUT");
    check(s4.commands_timeout == 1, "commands_timeout == 1");
}

// ---- ModeControlState: data-plane sync (state event / result frame) ---------
void test_data_plane_sync() {
    // by id: a state event carrying the accepted id resolves the pending command.
    mctl::ModeControlState s;
    s.on_sent("SET_MODE AUTO_LOCK", 100);
    s.on_reply("OK accepted command_id=7 SET_MODE AUTO_LOCK", 110);
    s.sync_applied(mode_ctl::ModeKind::AutoLock, true, 7);
    check(s.command_status() == "APPLIED", "state event by id resolves -> APPLIED");
    check(s.applied_mode() == mode_ctl::ModeKind::AutoLock, "state event by id applies mode");

    // by target: the state event arrived before ACCEPTED was seen (id still 0).
    mctl::ModeControlState s2;
    s2.on_sent("SET_MODE BAND_SCAN", 100);
    s2.sync_applied(mode_ctl::ModeKind::BandScan, true, 9);
    check(s2.command_status() == "APPLIED", "state event by target resolves -> APPLIED");
    check(s2.applied_mode() == mode_ctl::ModeKind::BandScan, "state event by target applies mode");

    // command_id == 0 (initial/startup event) NEVER resolves a pending command.
    mctl::ModeControlState s3;
    s3.on_sent("SET_MODE AUTO_LOCK", 100);
    s3.sync_applied(mode_ctl::ModeKind::AutoLock, true, 0);
    check(s3.command_status() == "PENDING", "command_id=0 event does not resolve pending");
    check(s3.applied_mode() == mode_ctl::ModeKind::AutoLock,
          "command_id=0 event still advances applied");

    // observe_applied (result frame, no id) advances applied but never resolves.
    mctl::ModeControlState s4;
    s4.on_sent("SET_MODE BAND_SCAN", 100);
    s4.observe_applied(mode_ctl::ModeKind::BandScan, true);
    check(s4.applied_mode() == mode_ctl::ModeKind::BandScan, "result frame advances applied");
    check(s4.command_status() == "PENDING", "result frame does not resolve pending");
    check(s4.commands_applied == 0, "result frame does not count as applied");
}

// ---- ModeControlState: STATUS parse + connect/disconnect --------------------
void test_status_and_connect() {
    // STATUS after (re)connect re-syncs applied from the producer's authority.
    mctl::ModeControlState s;
    s.set_connected(true);
    s.on_reply(
        "OK requested_mode=BAND_SCAN applied_mode=BAND_SCAN requested_running=0 "
        "applied_running=0 last_command_id=4 last_applied_command_id=3 "
        "control_queue_depth=0 mode=BAND_SCAN running=0",
        0);
    check(s.applied_mode() == mode_ctl::ModeKind::BandScan, "STATUS applied_mode parsed");
    check(!s.applied_running(), "STATUS applied_running=0 -> STOPPED");
    check(s.applied_mode_display() == "BAND SCAN", "STATUS display name");

    // A disconnect drops the in-flight command (fate unknown) but keeps requested_*.
    mctl::ModeControlState s2;
    std::string line;
    s2.request(ui::mode_ui::kBtnAutoLock, 0, line);
    s2.on_sent(line, 100);
    check(s2.has_pending(), "pending before disconnect");
    s2.set_connected(true);
    s2.set_connected(false);
    check(!s2.has_pending(), "disconnect clears the in-flight command");
    check(s2.command_status() == "--" || s2.command_status() == "PENDING",
          "disconnect does not fabricate REJECT/TIMEOUT");
    check(s2.requested_mode_display() == "AUTO LOCK", "requested intent survives disconnect");
}

// ---- Full loopback: tap -> client -> control thread -> APPLIED --------------
#if defined(__unix__) || defined(__APPLE__)
void test_full_loopback() {
    const std::string path =
        "/tmp/touch_mode_ctl_test_" + std::to_string(::getpid()) + ".sock";

    ui::UnixSocketServer srv(path);
    check(srv.start(), "fake control server start() ok");

    ctl::CommandQueue cmdq(8);
    ctl::AckQueue ackq(8);
    ctl::ControlState state;
    ctl::ControlStats stats;
    mode_ctl::ModeState mirror;

    std::thread t(ctl::control_thread_main, std::ref(srv), std::ref(cmdq),
                  std::ref(ackq), std::ref(state), std::ref(stats), std::ref(mirror));

    ctl::ControlClient client(path);
    check(client.connect(), "ControlClient connects to fake server");

    mctl::ModeControlState mctl;
    mctl.set_connected(true);

    // Resync STATUS on connect.
    client.send_line("STATUS");
    {
        bool got = false;
        for (int i = 0; i < 10 && !got; ++i) {
            std::vector<std::string> rs = client.poll(50);
            for (const std::string& r : rs) {
                mctl.on_reply(r, 0);
                if (r.rfind("OK requested_mode=", 0) == 0) got = true;
            }
        }
        check(got, "STATUS resync received after connect");
        check(mctl.applied_mode() == mode_ctl::ModeKind::Fixed, "producer default FIXED");
    }

    // Tap AUTO LOCK -> SET_MODE AUTO_LOCK -> ACCEPTED -> APPLIED (full round trip).
    std::string line;
    check(mctl.request(ui::mode_ui::kBtnAutoLock, 0, line) && line == "SET_MODE AUTO_LOCK",
          "tap AUTO_LOCK -> SET_MODE AUTO_LOCK");
    check(client.send_line(line), "command line sent to fake server");
    mctl.on_sent(line, 0);
    check(mctl.command_status() == "PENDING", "PENDING after send");

    // Receive ACCEPTED, then simulate the producer applying (pop + push ack).
    bool accepted = false, applied = false;
    ctl::Command c;
    for (int i = 0; i < 20 && !applied; ++i) {
        std::vector<std::string> rs = client.poll(50);
        for (const std::string& r : rs) {
            mctl.on_reply(r, 0);
            if (r.rfind("OK accepted ", 0) == 0) {
                accepted = true;
                if (cmdq.try_pop(c)) {
                    state.applied_mode.store(static_cast<int>(mode_ctl::ModeKind::AutoLock));
                    state.last_applied_command_id.store(c.id);
                    state.queue_depth.store(0);
                    ackq.try_push("OK applied command_id=" + std::to_string(c.id) +
                                  " " + c.raw);
                }
            } else if (r.rfind("OK applied ", 0) == 0) {
                applied = true;
            }
        }
    }
    check(accepted, "ACCEPTED received over the loopback");
    check(applied, "APPLIED received over the loopback");
    check(mctl.applied_mode() == mode_ctl::ModeKind::AutoLock, "applied mode == AUTO_LOCK");
    check(mctl.command_status() == "APPLIED", "final status APPLIED");
    check(mctl.commands_sent == 1 && mctl.commands_applied == 1,
          "exactly one command sent and applied");
    check(mctl.commands_rejected == 0 && mctl.commands_timeout == 0 &&
              mctl.duplicate_commands == 0,
          "no reject / timeout / duplicate");
    check(mctl.requested_mode_display() == "AUTO LOCK" &&
              mctl.applied_mode_display() == "AUTO LOCK",
          "requested == applied after convergence");

    client.close();   // never unlinks the producer's socket
    state.stop.store(true);
    t.join();
    srv.stop();
    check(::access(path.c_str(), F_OK) == -1, "server unlinked its socket on stop");
}
#else
void test_full_loopback() {
    std::printf("  (skipped: no AF_UNIX on this platform)\n");
}
#endif

// ---- M18-SW1 Task A: movement tolerance + per-button debounce ----------------
void test_tap_detector_m18_sw1() {
    const ui_touch::Point in_fixed = pt(200, 140);

    // Slight finger drift (a few px) between down and up must NOT cancel the tap
    // (the old detector cancelled on a single 1px drift -> "first click did nothing").
    mctl::ControlTapDetector d(400, 24);
    check(d.on_sample(true, in_fixed, 100) == -1, "down inside FIXED");
    check(d.pressed_button() == ui::mode_ui::kBtnFixed, "pressed_button==FIXED during down");
    check(d.on_sample(true, pt(210, 150), 110) == -1, "slight drift (inside tol) still down");
    check(d.on_sample(true, pt(220, 160), 120) == -1, "slight drift (inside tol) still down");
    check(d.on_sample(false, pt(220, 160), 130) == ui::mode_ui::kBtnFixed,
          "release after slight drift -> tap (NOT cancelled)");
    check(d.pressed_button() == -1, "pressed_button==-1 after release");

    // A LARGE drift out of the button still cancels.
    mctl::ControlTapDetector d2(400, 24);
    check(d2.on_sample(true, in_fixed, 200) == -1, "down inside FIXED");
    check(d2.on_sample(true, pt(200, 400), 210) == -1, "large drift out -> cancel");
    check(d2.on_sample(false, pt(200, 400), 220) == -1, "release after large drift -> no tap");

    // Per-button debounce: a fast tap on a DIFFERENT button is NOT folded by the
    // previous button's debounce (the old single global debounce ate this click).
    mctl::ControlTapDetector d3(400, 24);
    check(d3.on_sample(true, in_fixed, 0) == -1, "FIXED down");
    check(d3.on_sample(false, in_fixed, 20) == ui::mode_ui::kBtnFixed, "FIXED tap");
    check(d3.on_sample(true, pt(600, 140), 40) == -1, "AUTO LOCK down (fast, different btn)");
    check(d3.on_sample(false, pt(600, 140), 60) == ui::mode_ui::kBtnAutoLock,
          "AUTO LOCK tap fires (no global debounce)");

    // One touch sequence per down->up: sequence_id increments once per down edge.
    mctl::ControlTapDetector d4(400, 24);
    check(d4.on_sample(true, in_fixed, 0) == -1, "seq down1");
    const std::uint64_t s1 = d4.sequence_id();
    check(d4.on_sample(false, in_fixed, 20) == ui::mode_ui::kBtnFixed, "seq up1");
    check(d4.on_sample(true, pt(600, 140), 40) == -1, "seq down2");
    check(d4.sequence_id() == s1 + 1, "sequence_id incremented on second down");

    // Diagnostic accessors after a down/up.
    mctl::ControlTapDetector d5(400, 24);
    check(d5.on_sample(true, in_fixed, 0) == -1, "diag down");
    check(d5.down_x() == 200 && d5.down_y() == 140, "diag down_x/down_y");
    check(d5.hit_target() == ui::mode_ui::kBtnFixed, "diag hit_target");
    check(d5.on_sample(false, in_fixed, 20) == ui::mode_ui::kBtnFixed, "diag up");
    check(d5.up_x() == 200 && d5.up_y() == 140, "diag up_x/up_y");
}

// ---- M18-SW1 Task A: request_ex outcomes + feedback --------------------------
void test_request_outcomes_m18_sw1() {
    std::string line;

    // Idempotent (already in mode) -> no command, feedback explains why.
    mctl::ModeControlState s;
    check(s.request_ex(ui::mode_ui::kBtnFixed, 0, line) ==
              mctl::ModeControlState::RequestOutcome::Idempotent,
          "FIXED while FIXED -> Idempotent");
    check(line.empty(), "idempotent -> empty line");
    check(s.feedback() == "ALREADY IN THIS MODE", "feedback ALREADY IN THIS MODE");

    // Sent -> fills line, clears feedback, advances requested_mode.
    mctl::ModeControlState s1;
    check(s1.request_ex(ui::mode_ui::kBtnAutoLock, 0, line) ==
              mctl::ModeControlState::RequestOutcome::Sent &&
              line == "SET_MODE AUTO_LOCK",
          "AUTO_LOCK -> Sent");
    check(s1.feedback() == "--", "sent clears feedback");
    check(s1.requested_mode_display() == "AUTO LOCK", "requested_mode advanced");

    // Duplicate (mode slot pending) -> no command + feedback.
    s1.on_sent(line, 0);
    check(s1.request_ex(ui::mode_ui::kBtnBandScan, 0, line) ==
              mctl::ModeControlState::RequestOutcome::Duplicate,
          "mode while pending -> Duplicate");
    check(s1.feedback() == "COMMAND IN PROGRESS", "feedback COMMAND IN PROGRESS");

    // Invalid button index.
    mctl::ModeControlState s2;
    check(s2.request_ex(-1, 0, line) == mctl::ModeControlState::RequestOutcome::Invalid,
          "button -1 -> Invalid");
    check(s2.request_ex(ui::mode_ui::kBtnCount, 0, line) ==
              mctl::ModeControlState::RequestOutcome::Invalid,
          "button >= count -> Invalid");
}

// ---- M18-SW1 Task A: pending/last-applied command id + ack latency -----------
void test_command_id_accessors_m18_sw1() {
    mctl::ModeControlState s;
    check(s.connection_state() == std::string("DISCONNECTED"), "connection_state DISCONNECTED");
    s.set_connected(true);
    check(s.connection_state() == std::string("CONNECTED"), "connection_state CONNECTED");

    std::string line;
    s.request(ui::mode_ui::kBtnAutoLock, 0, line);
    s.on_sent(line, 100);
    check(s.pending_command_id() == 0, "pending_command_id==0 before ACCEPTED");
    s.on_reply("OK accepted command_id=7 SET_MODE AUTO_LOCK", 110);
    check(s.pending_command_id() == 7, "pending_command_id==7 after ACCEPTED");
    check(s.last_ack_latency_ms() == -1, "no latency before APPLIED");

    s.on_reply("OK applied command_id=7 SET_MODE AUTO_LOCK", 130);
    check(s.pending_command_id() == 0, "pending_command_id==0 after APPLIED");
    check(s.last_applied_command_id() == 7, "last_applied_command_id==7");
    check(s.last_ack_latency_ms() == 30, "ack latency 130-100==30");
}

// ---- M18-SW1 Task A: TOUCH_EVENT line format -------------------------------
void test_touch_event_line_m18_sw1() {
    mctl::TouchEvent e;
    e.seq = 3;
    e.phase = "applied";
    e.touch_down_x = 100; e.touch_down_y = 120;
    e.touch_up_x = 102; e.touch_up_y = 121;
    e.hit_target = ui::mode_ui::kBtnFixed;
    e.command_id = 9;
    e.command_ack_received = true;
    e.command_applied = true;
    e.ack_latency_ms = 42;
    e.final_state = "APPLIED";
    e.line = "SET_MODE FIXED";
    const std::string s = mctl::touch_event_line(e);
    check(s.rfind("TOUCH_EVENT ", 0) == 0, "line starts with TOUCH_EVENT");
    check(s.find("touch_sequence_id=3") != std::string::npos, "has touch_sequence_id");
    check(s.find("phase=applied") != std::string::npos, "has phase");
    check(s.find("hit_target=0") != std::string::npos, "has hit_target");
    check(s.find("command_id=9") != std::string::npos, "has command_id");
    check(s.find("command_applied=1") != std::string::npos, "has command_applied");
    check(s.find("ack_latency_ms=42") != std::string::npos, "has ack_latency_ms");
    check(s.find("final_state=APPLIED") != std::string::npos, "has final_state");
    check(s.find("line=SET_MODE FIXED") != std::string::npos, "has line");
}

// ---- M18-SW1 Task A: PENDING / APPLIED / feedback / press all trigger redraw --
void test_display_changed_control_m18_sw1() {
    ui::UiState a, b;
    a.command_status = "PENDING";
    b.command_status = "APPLIED";
    check(ui::display_changed(a, b), "PENDING vs APPLIED -> redraw");

    ui::UiState c, d2;
    c.feedback = "--";
    d2.feedback = "ALREADY IN THIS MODE";
    check(ui::display_changed(c, d2), "feedback change -> redraw");

    ui::UiState e, f;
    e.pressed_button = -1;
    f.pressed_button = ui::mode_ui::kBtnFixed;
    check(ui::display_changed(e, f), "pressed_button change -> redraw");
}

}  // namespace

int main() {
    std::printf("test_touch_mode_control\n");
    test_tap_detector();
    test_request_mapping();
    test_two_slots();
    test_reply_handling();
    test_data_plane_sync();
    test_status_and_connect();
    test_tap_detector_m18_sw1();
    test_request_outcomes_m18_sw1();
    test_command_id_accessors_m18_sw1();
    test_touch_event_line_m18_sw1();
    test_display_changed_control_m18_sw1();
    test_full_loopback();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
