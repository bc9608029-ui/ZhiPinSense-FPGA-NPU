// test_mode_control.cpp -- host tests for the UI v3 M6 reverse control channel:
// the pure-logic mode state machine + command parser (mode_control.hpp) and the
// reply path of the AF_UNIX control socket (unix_socket_server.hpp::reply).
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled -O2 -Wall -Wextra
// -Werror; also run under ASan/UBSan.  The AF_UNIX loopback drives the exact
// ui::UnixSocketServer the UI server uses for the control plane.

#include "../board_package/mode_control.hpp"
#include "../board_package/unix_socket_server.hpp"

#include <cstdio>
#include <string>
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

// ---- pure-logic state machine ----------------------------------------------
void test_state_defaults() {
    mode_ctl::ModeState st;
    check(st.mode == mode_ctl::ModeKind::Fixed, "default mode is FIXED");
    check(st.run == mode_ctl::RunState::Running, "default run state is RUNNING");
}

void test_names() {
    check(std::string(mode_ctl::mode_display_name(mode_ctl::ModeKind::Fixed)) == "FIXED",
          "display Fixed == FIXED");
    check(std::string(mode_ctl::mode_display_name(mode_ctl::ModeKind::AutoLock)) == "AUTO LOCK",
          "display AutoLock == AUTO LOCK");
    check(std::string(mode_ctl::mode_display_name(mode_ctl::ModeKind::BandScan)) == "BAND SCAN",
          "display BandScan == BAND SCAN");
    check(std::string(mode_ctl::mode_token(mode_ctl::ModeKind::Fixed)) == "FIXED",
          "token Fixed == FIXED");
    check(std::string(mode_ctl::mode_token(mode_ctl::ModeKind::AutoLock)) == "AUTO_LOCK",
          "token AutoLock == AUTO_LOCK");
    check(std::string(mode_ctl::mode_token(mode_ctl::ModeKind::BandScan)) == "BAND_SCAN",
          "token BandScan == BAND_SCAN");
    check(std::string(mode_ctl::run_display_name(mode_ctl::RunState::Running)) == "RUNNING",
          "run Running == RUNNING");
    check(std::string(mode_ctl::run_display_name(mode_ctl::RunState::Stopped)) == "STOPPED",
          "run Stopped == STOPPED");
}

void test_mode_from_token() {
    mode_ctl::ModeKind m;
    check(mode_ctl::mode_from_token("FIXED", m) && m == mode_ctl::ModeKind::Fixed,
          "token FIXED maps to Fixed");
    check(mode_ctl::mode_from_token("AUTO_LOCK", m) && m == mode_ctl::ModeKind::AutoLock,
          "token AUTO_LOCK maps to AutoLock");
    check(mode_ctl::mode_from_token("BAND_SCAN", m) && m == mode_ctl::ModeKind::BandScan,
          "token BAND_SCAN maps to BandScan");
    check(!mode_ctl::mode_from_token("AUTO LOCK", m), "space form is NOT a token");
    check(!mode_ctl::mode_from_token("auto_lock", m), "lowercase is NOT a token");
    check(!mode_ctl::mode_from_token("FIX", m), "prefix is NOT a token");
    check(!mode_ctl::mode_from_token("", m), "empty is NOT a token");
}

void test_split_ws() {
    const std::vector<std::string> a = mode_ctl::split_ws("SET_MODE AUTO_LOCK");
    check(a.size() == 2 && a[0] == "SET_MODE" && a[1] == "AUTO_LOCK",
          "split two tokens");
    const std::vector<std::string> b = mode_ctl::split_ws("  SET_MODE   AUTO_LOCK  ");
    check(b.size() == 2 && b[0] == "SET_MODE" && b[1] == "AUTO_LOCK",
          "leading/trailing/extra whitespace collapsed");
    check(mode_ctl::split_ws("").empty(), "empty line -> no tokens");
    check(mode_ctl::split_ws("\t \t").empty(), "whitespace-only -> no tokens");
}

void test_apply_command() {
    mode_ctl::ModeState st;

    // SET_MODE transitions.
    check(mode_ctl::apply_command(st, "SET_MODE AUTO_LOCK") == "OK mode=AUTO_LOCK",
          "SET_MODE AUTO_LOCK -> OK");
    check(st.mode == mode_ctl::ModeKind::AutoLock, "mode switched to AutoLock");
    check(mode_ctl::apply_command(st, "SET_MODE BAND_SCAN") == "OK mode=BAND_SCAN",
          "SET_MODE BAND_SCAN -> OK");
    check(st.mode == mode_ctl::ModeKind::BandScan, "mode switched to BandScan");
    check(mode_ctl::apply_command(st, "SET_MODE FIXED") == "OK mode=FIXED",
          "SET_MODE FIXED -> OK");
    check(st.mode == mode_ctl::ModeKind::Fixed, "mode back to Fixed");
    check(mode_ctl::apply_command(st, "  SET_MODE   AUTO_LOCK  ") == "OK mode=AUTO_LOCK",
          "SET_MODE tolerates extra whitespace");

    // SET_MODE failures must NOT mutate state.
    st.mode = mode_ctl::ModeKind::Fixed;
    check(mode_ctl::apply_command(st, "SET_MODE GARBAGE").rfind("ERR", 0) == 0,
          "SET_MODE GARBAGE -> ERR");
    check(st.mode == mode_ctl::ModeKind::Fixed, "unknown mode leaves mode unchanged");
    check(mode_ctl::apply_command(st, "SET_MODE").rfind("ERR", 0) == 0,
          "SET_MODE with no arg -> ERR");
    check(mode_ctl::apply_command(st, "SET_MODE FIXED EXTRA").rfind("ERR", 0) == 0,
          "SET_MODE with extra arg -> ERR");
    check(mode_ctl::apply_command(st, "SET_MODE AUTO LOCK").rfind("ERR", 0) == 0,
          "SET_MODE with space form -> ERR");
    check(mode_ctl::apply_command(st, "set_mode fixed").rfind("ERR", 0) == 0,
          "lowercase command -> ERR");

    // START / STOP.
    check(mode_ctl::apply_command(st, "STOP") == "OK running=0", "STOP -> OK running=0");
    check(st.run == mode_ctl::RunState::Stopped, "STOP sets Stopped");
    check(mode_ctl::apply_command(st, "START") == "OK running=1", "START -> OK running=1");
    check(st.run == mode_ctl::RunState::Running, "START sets Running");
    check(mode_ctl::apply_command(st, "START extra").rfind("ERR", 0) == 0,
          "START with extra arg -> ERR");
    check(mode_ctl::apply_command(st, "STOP extra").rfind("ERR", 0) == 0,
          "STOP with extra arg -> ERR");

    // STATUS (must not mutate).
    st.mode = mode_ctl::ModeKind::BandScan;
    st.run = mode_ctl::RunState::Stopped;
    check(mode_ctl::apply_command(st, "STATUS") == "OK mode=BAND_SCAN running=0",
          "STATUS reports mode + running=0");
    check(st.mode == mode_ctl::ModeKind::BandScan && st.run == mode_ctl::RunState::Stopped,
          "STATUS does not mutate state");

    // Unknown / empty.
    check(mode_ctl::apply_command(st, "FROBNICATE").rfind("ERR", 0) == 0,
          "unknown command -> ERR");
    check(mode_ctl::apply_command(st, "").rfind("ERR", 0) == 0, "empty command -> ERR");
    check(mode_ctl::apply_command(st, "   ").rfind("ERR", 0) == 0,
          "whitespace-only command -> ERR");
}

void test_mode_state_line() {
    mode_ctl::ModeState st;
    st.mode = mode_ctl::ModeKind::AutoLock;
    st.run = mode_ctl::RunState::Stopped;
    check(mode_ctl::mode_state_line(st) == "mode=AUTO_LOCK running=0",
          "mode_state_line formats state");
}

// ---- control socket reply path (AF_UNIX loopback) --------------------------
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

// Read one newline-terminated reply line (with a bounded timeout).
bool raw_recv_line(int fd, std::string& out) {
    char buf[512];
    std::string acc;
    for (int tries = 0; tries < 200; ++tries) {
        pollfd pfd{fd, POLLIN, 0};
        const int prc = ::poll(&pfd, 1, 10);
        if (prc < 0) return false;
        if (prc == 0) continue;
        const ssize_t n = ::recv(fd, buf, sizeof(buf), 0);
        if (n > 0) {
            acc.append(buf, static_cast<std::size_t>(n));
            const std::size_t nl = acc.find('\n');
            if (nl != std::string::npos) { out = acc.substr(0, nl); return true; }
        } else if (n == 0) {
            out = acc;
            return !acc.empty();
        }
    }
    return false;
}

void test_control_socket_reply() {
    const std::string path =
        "/tmp/mode_ctl_test_" + std::to_string(::getpid()) + ".sock";

    ui::UnixSocketServer srv(path);
    check(srv.start(), "control server start() succeeds");

    const int fd = raw_connect(path);
    check(fd >= 0, "control client connects");
    if (fd >= 0) {
        check(raw_send(fd, "SET_MODE AUTO_LOCK\n"), "send SET_MODE line");

        // Server side: poll the line, apply it, reply.
        mode_ctl::ModeState st;
        std::string resp;
        for (int i = 0; i < 200; ++i) {
            ui::UnixSocketServer::PollResult pr = srv.poll(10);
            if (!pr.lines.empty()) {
                resp = mode_ctl::apply_command(st, pr.lines[0]);
                srv.reply(resp);
                break;
            }
        }
        check(resp == "OK mode=AUTO_LOCK", "server applied SET_MODE and computed reply");
        check(st.mode == mode_ctl::ModeKind::AutoLock, "server mode state updated");

        std::string got;
        check(raw_recv_line(fd, got), "client reads a reply line");
        check(got == "OK mode=AUTO_LOCK", "reply round-trips to the client verbatim");
        ::close(fd);
    }

    // A malformed command still gets an ERR reply (fail-closed, never silent).
    {
        const int fd2 = raw_connect(path);
        check(fd2 >= 0, "second control client connects");
        if (fd2 >= 0) {
            check(raw_send(fd2, "SET_MODE NOPE\n"), "send malformed SET_MODE line");
            mode_ctl::ModeState st;
            std::string resp;
            for (int i = 0; i < 200; ++i) {
                ui::UnixSocketServer::PollResult pr = srv.poll(10);
                if (!pr.lines.empty()) {
                    resp = mode_ctl::apply_command(st, pr.lines[0]);
                    srv.reply(resp);
                    break;
                }
            }
            check(resp.rfind("ERR", 0) == 0, "malformed command -> ERR reply");
            std::string got;
            check(raw_recv_line(fd2, got) && got.rfind("ERR", 0) == 0,
                  "ERR reply round-trips to the client");
            ::close(fd2);
        }
    }

    // reply() with no client is a safe no-op (returns false, never throws).
    {
        ui::UnixSocketServer empty("/tmp/mode_ctl_empty_" +
                                   std::to_string(::getpid()) + ".sock");
        check(empty.start(), "empty control server start() succeeds");
        check(!empty.reply("OK nope"), "reply() with no client returns false");
    }
}
#else
void test_control_socket_reply() {
    std::printf("  (skipped: no AF_UNIX on this platform)\n");
}
#endif

}  // namespace

int main() {
    std::printf("test_mode_control\n");
    test_state_defaults();
    test_names();
    test_mode_from_token();
    test_split_ws();
    test_apply_command();
    test_mode_state_line();
    test_control_socket_reply();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
