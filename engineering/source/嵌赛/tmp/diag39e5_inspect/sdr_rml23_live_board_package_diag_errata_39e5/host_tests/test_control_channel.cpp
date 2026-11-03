// test_control_channel.cpp -- host tests for the Task E control channel with
// hardware/control separation (control_channel.hpp): the bounded command/ack
// queues, the atomic ControlState + status_reply(), the pure command forecast
// (parse_command), the state-event JSON round-trip (state_line ->
// parse_state_frame -> apply_state_event), and the control thread itself driven
// through a real AF_UNIX loopback socket.
//
// The whole point of Task E is that control RECEPTION is decoupled from command
// APPLICATION.  This test proves:
//   * the queue is bounded and overflow is explicit (never a silent drop);
//   * STATUS is answered from the atomic snapshot (no command queued);
//   * a mutating command is ACCEPTED immediately with a monotonic command_id and
//     only later APPLIED (two-phase);
//   * the APPLIED ack travels back through the control thread (it owns the socket);
//   * a STOPPED state event round-trips to the UI state without touching the last
//     classification.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled -O2 -Wall -Wextra
// -Werror; also run under ASan/UBSan.

#include "../board_package/control_channel.hpp"
#include "../board_package/result_frame_v2_parse.hpp"
#include "../board_package/ui_state_map.hpp"
#include "../sdr_adapter/ui_report.hpp"

#include <cstdio>
#include <string>
#include <thread>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

bool starts_with(const std::string& s, const char* p) {
    return s.rfind(p, 0) == 0;
}

// ---- CommandQueue -----------------------------------------------------------
void test_command_queue() {
    ctl::CommandQueue q(2);
    ctl::Command c;
    c.id = 1; c.raw = "SET_MODE AUTO_LOCK"; c.accepted_us = 100;
    check(q.try_push(c), "queue push #1 ok");
    c.id = 2; c.raw = "STOP"; c.accepted_us = 200;
    check(q.try_push(c), "queue push #2 ok");
    check(q.depth() == 2, "depth == 2 after two pushes");
    check(q.max_depth() == 2, "max_depth == 2");

    c.id = 3; c.raw = "START"; c.accepted_us = 300;
    check(!q.try_push(c), "queue push #3 overflows (bounded)");
    check(q.depth() == 2, "depth unchanged after overflow");

    ctl::Command out;
    check(q.try_pop(out) && out.id == 1, "pop #1 is the first pushed (FIFO)");
    check(q.try_pop(out) && out.id == 2, "pop #2 is the second pushed");
    check(!q.try_pop(out), "pop #3 empty");
    check(q.depth() == 0, "depth == 0 after draining");
    check(q.max_depth() == 2, "max_depth preserved after draining");
}

// ---- AckQueue ---------------------------------------------------------------
void test_ack_queue() {
    ctl::AckQueue a(2);
    check(a.try_push("OK applied command_id=1 STOP"), "ack push #1 ok");
    check(a.try_push("OK applied command_id=2 START"), "ack push #2 ok");
    check(!a.try_push("OK applied command_id=3 START"), "ack push #3 overflows");
    std::string s;
    check(a.try_pop(s) && starts_with(s, "OK applied command_id=1"), "ack pop FIFO");
    check(a.try_pop(s) && starts_with(s, "OK applied command_id=2"), "ack pop FIFO #2");
    check(!a.try_pop(s), "ack pop empty");
}

// ---- ControlState + status_reply -------------------------------------------
void test_status_reply() {
    ctl::ControlState st;
    // Defaults: FIXED + running.
    const std::string d = ctl::status_reply(st);
    check(starts_with(d, "OK "), "status_reply starts with OK");
    check(d.find("requested_mode=FIXED") != std::string::npos, "default requested FIXED");
    check(d.find("applied_mode=FIXED") != std::string::npos, "default applied FIXED");
    check(d.find("requested_running=1") != std::string::npos, "default requested running");
    check(d.find("applied_running=1") != std::string::npos, "default applied running");
    check(d.find("last_command_id=0") != std::string::npos, "default last_command_id=0");
    check(d.find("last_applied_command_id=0") != std::string::npos,
          "default last_applied_command_id=0");
    check(d.find("control_queue_depth=0") != std::string::npos, "default queue depth 0");
    check(d.find("mode=FIXED") != std::string::npos, "legacy mode= key kept");
    check(d.find("running=1") != std::string::npos, "legacy running= key kept");

    // After the producer applied a STOP (applied != requested diverges briefly).
    st.requested_mode.store(static_cast<int>(mode_ctl::ModeKind::BandScan));
    st.applied_mode.store(static_cast<int>(mode_ctl::ModeKind::Fixed));
    st.requested_running.store(0);
    st.applied_running.store(0);
    st.last_command_id.store(7);
    st.last_applied_command_id.store(6);
    st.queue_depth.store(1);
    const std::string d2 = ctl::status_reply(st);
    check(d2.find("requested_mode=BAND_SCAN") != std::string::npos, "requested BAND_SCAN");
    check(d2.find("applied_mode=FIXED") != std::string::npos, "applied still FIXED");
    check(d2.find("last_command_id=7") != std::string::npos, "last_command_id=7");
    check(d2.find("last_applied_command_id=6") != std::string::npos,
          "last_applied_command_id=6");
    check(d2.find("control_queue_depth=1") != std::string::npos, "queue depth 1");
    check(d2.find("running=0") != std::string::npos, "legacy running=0 after STOP");
}

// ---- parse_command forecast -------------------------------------------------
void test_parse_command_forecast() {
    mode_ctl::ModeState cur{mode_ctl::ModeKind::Fixed, mode_ctl::RunState::Running};

    const mode_ctl::ParseResult a = mode_ctl::parse_command(cur, "SET_MODE BAND_SCAN");
    check(a.ok && a.new_mode == mode_ctl::ModeKind::BandScan, "forecast SET_MODE ok");
    check(a.reply == "OK mode=BAND_SCAN", "forecast reply verbatim");
    check(cur.mode == mode_ctl::ModeKind::Fixed, "forecast does NOT mutate caller state");

    const mode_ctl::ParseResult b = mode_ctl::parse_command(cur, "STOP");
    check(b.ok && b.new_run == mode_ctl::RunState::Stopped, "forecast STOP ok");
    check(cur.run == mode_ctl::RunState::Running, "forecast STOP does NOT mutate caller");

    const mode_ctl::ParseResult c = mode_ctl::parse_command(cur, "SET_MODE GARBAGE");
    check(!c.ok && starts_with(c.reply, "ERR"), "forecast malformed -> ERR, not ok");

    // STATUS is a legal command and its forecast is a no-op on the copy; the
    // control thread intercepts STATUS separately (never queued), so the pure
    // forecast still reports OK but changes neither mode nor run state.
    const mode_ctl::ParseResult d = mode_ctl::parse_command(cur, "STATUS");
    check(d.ok, "STATUS forecast is a legal no-op command");
    check(d.new_mode == mode_ctl::ModeKind::Fixed &&
              d.new_run == mode_ctl::RunState::Running,
          "STATUS forecast leaves mode/run unchanged");
}

// ---- state-event JSON round trip (producer -> UI) ---------------------------
void test_state_event_roundtrip() {
    // The producer emits this on a STOP transition, tagged rml23-chain-v2 with the
    // producer's model SHA (Part 2c/d: RML23 state heartbeat + protocol naming).
    const std::string line = ui::state_line("FIXED", "STOPPED", "SIGNAL_PRESENT", 5,
                                            12345ULL, "2425d990", "rml23-chain-v2");
    check(line.find("\"type\":\"state\"") != std::string::npos, "state_line has type=state");
    check(line.find("\"version\":\"rml23-chain-v2\"") != std::string::npos,
          "state_line version rml23-chain-v2");
    check(line.find("\"command_id\":5") != std::string::npos, "state_line command_id=5");
    check(line.find("\"work_mode\":\"FIXED\"") != std::string::npos, "state_line work_mode");
    check(line.find("\"run_state\":\"STOPPED\"") != std::string::npos, "state_line run_state");
    check(line.find("\"model_sha\":\"2425d990\"") != std::string::npos,
          "state_line carries model_sha");

    const ui::StateEvent ev = ui::parse_state_frame(line);
    check(ev.ok, "state event parses ok");
    check(ev.work_mode == "FIXED" && ev.run_state == "STOPPED", "state fields parsed");
    check(ev.presence_state == "SIGNAL_PRESENT", "presence parsed");
    check(ev.command_id == 5 && ev.timestamp_us == 12345, "ids parsed");
    check(ev.model_sha == "2425d990", "model_sha parsed");

    // Backward compatibility: the parser still accepts the 12-class version.
    const std::string legacy = ui::state_line("FIXED", "STOPPED", "SIGNAL_PRESENT", 5,
                                              12345ULL, "", "12class-chain-v2");
    const ui::StateEvent ev_legacy = ui::parse_state_frame(legacy);
    check(ev_legacy.ok, "12class-chain-v2 state still parses (back-compat)");

    // Apply to a UI state that already holds a classification; the classification
    // fields must be untouched, only mode/run/presence change.
    ui::UiState st;
    st.top1 = "BPSK";
    st.conf = 0.83f;
    st.frame = "1024";
    st.running = true;
    ui::apply_state_event(st, ev);
    check(st.running == false, "STOPPED -> running=false");
    check(st.work_mode == "FIXED", "work_mode -> FIXED");
    check(st.presence == "SIGNAL_PRESENT", "presence updated");
    check(st.top1 == "BPSK" && st.conf == 0.83f, "classification fields untouched");
    check(st.frame == "1024", "frame id untouched");

    // A malformed state line is rejected (never half-applied).
    const ui::StateEvent bad = ui::parse_state_frame("{\"type\":\"state\"}");
    check(!bad.ok, "truncated state event rejected");
}

// ---- control thread over a real AF_UNIX socket ------------------------------
#if defined(__unix__) || defined(__APPLE__)
int raw_connect(const std::string& path) {
    const int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    if (path.size() >= sizeof(addr.sun_path)) { ::close(fd); return -1; }
    for (std::size_t i = 0; i < path.size(); ++i) addr.sun_path[i] = path[i];
    addr.sun_path[path.size()] = '\0';
    if (::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        ::close(fd);
        return -1;
    }
    return fd;
}

bool raw_send(int fd, const std::string& s) {
    std::size_t off = 0;
    while (off < s.size()) {
        const ssize_t n = ::send(fd, s.data() + off, s.size() - off, 0);
        if (n <= 0) return false;
        off += static_cast<std::size_t>(n);
    }
    return true;
}

// Read up to `max_lines` newline-terminated lines within `ms` total budget.
std::vector<std::string> raw_recv_lines(int fd, std::size_t max_lines, int ms) {
    std::vector<std::string> out;
    std::string acc;
    for (int t = 0; t < ms; t += 10) {
        pollfd pfd{fd, POLLIN, 0};
        const int prc = ::poll(&pfd, 1, 10);
        if (prc > 0) {
            char buf[1024];
            const ssize_t n = ::recv(fd, buf, sizeof(buf), 0);
            if (n > 0) {
                acc.append(buf, static_cast<std::size_t>(n));
                std::size_t nl;
                while ((nl = acc.find('\n')) != std::string::npos) {
                    std::string line = acc.substr(0, nl);
                    if (!line.empty() && line.back() == '\r') line.pop_back();
                    out.push_back(line);
                    acc.erase(0, nl + 1);
                    if (out.size() >= max_lines) return out;
                }
            } else if (n == 0) {
                return out;
            }
        }
    }
    return out;
}

void test_control_thread_loopback() {
    const std::string path =
        "/tmp/ctl_thread_test_" + std::to_string(::getpid()) + ".sock";

    ui::UnixSocketServer srv(path);
    check(srv.start(), "control server start() ok");

    ctl::CommandQueue cmdq(8);
    ctl::AckQueue ackq(8);
    ctl::ControlState state;
    ctl::ControlStats stats;
    mode_ctl::ModeState mirror;

    std::thread t(ctl::control_thread_main, std::ref(srv), std::ref(cmdq),
                  std::ref(ackq), std::ref(state), std::ref(stats), std::ref(mirror));

    const int fd = raw_connect(path);
    check(fd >= 0, "control client connects");
    if (fd >= 0) {
        // 1. A mutating command is ACCEPTED immediately with a monotonic id.
        check(raw_send(fd, "SET_MODE AUTO_LOCK\n"), "send SET_MODE AUTO_LOCK");
        std::vector<std::string> r1 = raw_recv_lines(fd, 1, 1000);
        check(r1.size() == 1, "client receives one accepted reply");
        if (r1.size() == 1) {
            check(r1[0] == "OK accepted command_id=1 SET_MODE AUTO_LOCK",
                  "accepted reply carries command_id=1 verbatim");
        }

        // The command is now in the queue, waiting for the producer to apply it.
        ctl::Command c;
        check(cmdq.try_pop(c) && c.id == 1 && c.raw == "SET_MODE AUTO_LOCK",
              "command enqueued with id=1 (two-phase: accepted != applied)");
        check(state.last_command_id.load() == 1, "last_command_id advanced to 1");
        check(state.requested_mode.load() == static_cast<int>(mode_ctl::ModeKind::AutoLock),
              "control thread forecast the mode change into requested_mode");

        // 2. STATUS is answered straight from the snapshot (no command queued).
        check(raw_send(fd, "STATUS\n"), "send STATUS");
        std::vector<std::string> r2 = raw_recv_lines(fd, 1, 1000);
        check(r2.size() == 1 && starts_with(r2[0], "OK requested_mode=AUTO_LOCK"),
              "STATUS answered from snapshot (requested_mode=AUTO_LOCK)");

        // 3. The producer applies the command and pushes the APPLIED ack; the
        //    control thread forwards it back over the socket (it owns the socket).
        state.applied_mode.store(static_cast<int>(mode_ctl::ModeKind::AutoLock));
        state.last_applied_command_id.store(1);
        state.queue_depth.store(0);
        check(ackq.try_push("OK applied command_id=1 SET_MODE AUTO_LOCK"),
              "producer pushes APPLIED ack");
        std::vector<std::string> r3 = raw_recv_lines(fd, 1, 1000);
        check(r3.size() == 1 && r3[0] == "OK applied command_id=1 SET_MODE AUTO_LOCK",
              "APPLIED ack forwarded by the control thread");

        ::close(fd);
    }

    state.stop.store(true);
    t.join();
    srv.stop();
}
#else
void test_control_thread_loopback() {
    std::printf("  (skipped: no AF_UNIX on this platform)\n");
}
#endif

}  // namespace

int main() {
    std::printf("test_control_channel\n");
    test_command_queue();
    test_ack_queue();
    test_status_reply();
    test_parse_command_forecast();
    test_state_event_roundtrip();
    test_control_thread_loopback();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
