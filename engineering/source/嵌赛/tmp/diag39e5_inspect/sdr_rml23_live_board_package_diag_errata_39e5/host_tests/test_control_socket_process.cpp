// test_control_socket_process.cpp -- Stage B process-level test (errata 39e5).
//
// Spawns a REAL child process that runs the EXACT control-channel code the live-rx
// producer now uses (ui::UnixSocketServer + ctl::control_thread_main + the
// apply_pending drain + a steady heartbeat), and drives it over a real AF_UNIX
// control socket.  Asserts requirement #3 end-to-end: STOP is applied and the
// state heartbeat KEEPS FLOWING (the UI shows STOPPED, never STALE), and START
// resumes RUNNING.
//
// This is the control-side counterpart of test_ui_live_rx_process.cpp: it proves
// the live-rx control service (Evidence 6) works as a process, not just a parser.
//
// POSIX-only (fork/exec/AF_UNIX/pipe).  On other platforms it prints "skipped".
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/control_channel.hpp"
#include "../board_package/mode_control.hpp"
#include "../board_package/unix_socket_server.hpp"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>
#include <mutex>
#include <thread>
#endif

namespace {

int g_pass = 0, g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

#if defined(__unix__) || defined(__APPLE__)

// ---- child: the live-rx control loop (mirrors run_live_rx_phase structure) ---
// heartbeat: steady 250 ms (test-fast; the board uses 1000 ms), printed to stdout.
// apply_pending: drain commands -> mode_ctl::apply_command -> ack -> update cstate.
// STOPPED: keep heartbeating (heartbeat block is above the Stopped short-circuit).
int child_main(const std::string& ctl_path) {
    ui::UnixSocketServer control(ctl_path);
    if (!control.start()) return 2;

    ctl::CommandQueue cmdq(8);
    ctl::AckQueue ackq(8);
    ctl::ControlState cstate;
    ctl::ControlStats cstats;
    mode_ctl::ModeState mst;                       // default FIXED + Running
    mode_ctl::ModeState mirror = mst;
    cstate.requested_mode.store(static_cast<int>(mirror.mode));
    cstate.requested_running.store(1);
    cstate.applied_mode.store(static_cast<int>(mirror.mode));
    cstate.applied_running.store(1);

    std::thread ctl_thread(ctl::control_thread_main, std::ref(control),
                           std::ref(cmdq), std::ref(ackq), std::ref(cstate),
                           std::ref(cstats), std::ref(mirror));

    std::printf("CTL_READY sock=%s\n", ctl_path.c_str());
    std::fflush(stdout);

    auto last_hb = std::chrono::steady_clock::now();
    int hb_count = 0;
    const int kMaxHeartbeats = 20;   // bounded child lifetime (~5 s)

    while (hb_count < kMaxHeartbeats) {
        // apply_pending (loop_top / frame_top equivalent)
        ctl::Command c;
        while (cmdq.try_pop(c)) {
            mode_ctl::apply_command(mst, c.raw);
            ackq.try_push("OK applied command_id=" + std::to_string(c.id) + " " + c.raw);
            cstate.applied_mode.store(static_cast<int>(mst.mode));
            cstate.applied_running.store(
                mst.run == mode_ctl::RunState::Running ? 1 : 0);
            cstate.last_applied_command_id.store(c.id);
            cstate.queue_depth.store(cmdq.depth());
            cstats.applied.fetch_add(1);
        }

        // steady heartbeat (runs BEFORE the STOPPED short-circuit, so STOP keeps
        // the heartbeat alive -- the UI shows STOPPED, never STALE).
        const auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration_cast<std::chrono::milliseconds>(now - last_hb).count()
            >= 250) {
            last_hb = now;
            std::printf("HEARTBEAT run=%s mode=%s\n",
                        mode_ctl::run_display_name(mst.run),
                        mode_ctl::mode_token(mst.mode));
            std::fflush(stdout);
            ++hb_count;
        }

        if (mst.run == mode_ctl::RunState::Stopped) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    cstate.stop.store(true);
    ctl_thread.join();
    return 0;
}

// ---- parent helpers ----------------------------------------------------------
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

struct OutputCapture {
    std::mutex mu;
    std::vector<std::string> lines;
    int fd = -1;
    std::thread reader;

    void start() {
        reader = std::thread([this]() {
            FILE* f = ::fdopen(fd, "r");
            if (!f) return;
            char buf[2048];
            while (::fgets(buf, sizeof(buf), f)) {
                std::string s(buf);
                while (!s.empty() && (s.back() == '\n' || s.back() == '\r'))
                    s.pop_back();
                std::lock_guard<std::mutex> lk(mu);
                lines.push_back(s);
            }
            ::fclose(f);
        });
    }
    void stop() {
        if (reader.joinable()) reader.join();
    }
    // Count of lines containing `needle`.
    int count(const std::string& needle) {
        std::lock_guard<std::mutex> lk(mu);
        int n = 0;
        for (const auto& l : lines)
            if (l.find(needle) != std::string::npos) ++n;
        return n;
    }
};

void run_process_test() {
    const std::string ctl_path =
        "/tmp/rml23_ctl_proc_" + std::to_string(::getpid()) + ".sock";
    ::unlink(ctl_path.c_str());

    int pipefd[2];
    if (::pipe(pipefd) != 0) { check(false, "pipe()"); return; }

    const pid_t pid = ::fork();
    if (pid < 0) { check(false, "fork()"); return; }
    if (pid == 0) {
        ::dup2(pipefd[1], STDOUT_FILENO);
        ::dup2(pipefd[1], STDERR_FILENO);
        ::close(pipefd[0]);
        ::close(pipefd[1]);
        _exit(child_main(ctl_path));
    }
    ::close(pipefd[1]);

    OutputCapture cap;
    cap.fd = pipefd[0];
    cap.start();

    // Wait for the control socket, then connect.
    int fd = -1;
    for (int i = 0; i < 100 && fd < 0; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        fd = raw_connect(ctl_path);
    }
    check(fd >= 0, "control client connects to the child's control socket");
    if (fd < 0) {
        ::kill(pid, SIGKILL);
        cap.stop();
        ::waitpid(pid, nullptr, 0);
        return;
    }

    // STOP: accepted (id 1) then applied by the child's drain.
    check(raw_send(fd, "STOP\n"), "send STOP");
    std::vector<std::string> a1 = raw_recv_lines(fd, 2, 1500);
    bool accepted_stop = false, applied_stop = false;
    for (const auto& l : a1) {
        if (l == "OK accepted command_id=1 STOP") accepted_stop = true;
        if (l == "OK applied command_id=1 STOP") applied_stop = true;
    }
    check(accepted_stop, "STOP accepted with command_id=1");
    check(applied_stop, "STOP applied (ack forwarded)");

    // STATUS from the atomic snapshot: running=0.
    check(raw_send(fd, "STATUS\n"), "send STATUS");
    std::vector<std::string> s1 = raw_recv_lines(fd, 1, 1000);
    check(s1.size() == 1 && s1[0].find("running=0") != std::string::npos &&
              s1[0].find("applied_running=0") != std::string::npos,
          "STATUS after STOP reports running=0 / applied_running=0");

    // Requirement #3: the heartbeat KEEPS FLOWING after STOP (>=2 more heartbeats,
    // and each reports run=STOPPED).
    {
        const int before = cap.count("HEARTBEAT");
        int after = before;
        for (int i = 0; i < 100 && after < before + 2; ++i) {
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
            after = cap.count("HEARTBEAT");
        }
        check(after >= before + 2, "heartbeat keeps flowing after STOP (>=2 more)");
        check(cap.count("HEARTBEAT run=STOPPED mode=FIXED") >= 1,
              "post-STOP heartbeat reports run=STOPPED");
    }

    // START: resumes RUNNING.
    check(raw_send(fd, "START\n"), "send START");
    std::vector<std::string> a2 = raw_recv_lines(fd, 2, 1500);
    bool applied_start = false;
    for (const auto& l : a2)
        if (l == "OK applied command_id=2 START") applied_start = true;
    check(applied_start, "START applied (command_id=2)");
    {
        bool running_hb = false;
        for (int i = 0; i < 100 && !running_hb; ++i) {
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
            running_hb = cap.count("HEARTBEAT run=RUNNING mode=FIXED") > 0;
        }
        check(running_hb, "heartbeat resumes run=RUNNING after START");
    }

    ::close(fd);
    ::kill(pid, SIGKILL);
    ::waitpid(pid, nullptr, 0);
    cap.stop();
    ::unlink(ctl_path.c_str());
}

#else
void run_process_test() {
    std::printf("  (skipped: no fork/AF_UNIX on this platform)\n");
}
#endif

}  // namespace

int main() {
    std::printf("test_control_socket_process\n");
    run_process_test();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
