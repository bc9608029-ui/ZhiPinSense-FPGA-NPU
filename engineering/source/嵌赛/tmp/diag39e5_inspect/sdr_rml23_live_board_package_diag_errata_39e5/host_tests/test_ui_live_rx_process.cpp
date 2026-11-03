// test_ui_live_rx_process.cpp -- Stage B process-level test (errata 39e5).
//
// Spawns the REAL board_ui_live_rml23 binary in --headless mode and drives it over
// a real AF_UNIX data socket, asserting on the binary's stdout observables
// (UI_STATUS / UI_RX / UI_RX_STATS).  This is the test the prior heartbeat fix
// lacked: it exercises the ACTUAL UI process's freshness gating -- the
// have_valid_message / have_valid_result / last_valid_message_rx /
// last_valid_result_rx split and the display precedence -- not a parser unit test.
//
// Phases (a single UI process, one real socket):
//   A. RUNNING + NO_SIGNAL heartbeat flow -> NO SIGNAL badge, never STALE
//   B. STOPPED state (heartbeat keeps flowing)  -> STOPPED badge, not STALE
//   C. RUNNING + SIGNAL_PRESENT result          -> LIVE badge
//   D1. quiet > stale_ms (socket still open)    -> STALE reason=timeout
//   D2. producer closes the socket              -> STALE reason=disconnected
//
// POSIX-only (fork/exec/AF_UNIX/pipe).  On other platforms it prints "skipped".
// Needs bin/board_ui_live_rml23 (built host-side, iCraft/libiio-free); the
// RML23_UI_BIN env var overrides the binary path.

#include "../board_package/chain_common.hpp"
#include "../sdr_adapter/ui_report.hpp"
#include "../sdr_adapter/unix_socket_sink.hpp"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <fcntl.h>
#include <signal.h>
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

// Frozen model.raw SHA (identity carried on both state heartbeats and results).
const char* kModelSha =
    "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba";

std::string hb_line(const char* run_state, const char* presence, std::uint64_t ts) {
    return ui::state_line("FIXED", run_state, presence, 0, ts, kModelSha,
                          "rml23-chain-v2");
}

// A valid 23-class result frame (raw-24 peak at 5 -> 8PSK, merged-23 peak at 5),
// serialized with the RML23 schema the producer actually emits.
std::string result_line() {
    const cat::Contract c23 = chain::contract_23();
    std::vector<float> raw24(24, -10.0f);
    raw24[5] = 4.0f;
    std::vector<float> merged23(23, -10.0f);
    merged23[5] = 4.0f;
    rf::ResultFrame r;
    r.frame_id = 7;
    r.timestamp_us = 1000;
    r.source = "fpga_npu";
    r.mock = false;
    r.presence_state = "SIGNAL_PRESENT";
    r.level_mode = "FIXED";
    r.model_scale = 1.0;
    r.rf_gain_db = 0.0;
    r.work_mode = "FIXED";
    r.run_state = "RUNNING";
    chain::fill_result_rml23(r, raw24, merged23, c23, kModelSha, 6.0);
    return ui::result_frame_rml23_line(r);
}

#if defined(__unix__) || defined(__APPLE__)

// Drains the UI child's stdout in a background thread so the child's printf never
// blocks on a full pipe; the main thread polls the collected lines.
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
    bool has(const std::string& needle) {
        std::lock_guard<std::mutex> lk(mu);
        for (const auto& l : lines)
            if (l.find(needle) != std::string::npos) return true;
        return false;
    }
    // Last "new=..." badge name seen in a UI_STATUS transition line.
    std::string last_status_new() {
        std::lock_guard<std::mutex> lk(mu);
        std::string out;
        for (const auto& l : lines) {
            if (l.find("UI_STATUS ") == std::string::npos) continue;
            const std::size_t n = l.find("new=");
            if (n == std::string::npos) continue;
            const std::size_t e = l.find(' ', n);
            out = l.substr(n + 4, e == std::string::npos ? std::string::npos
                                                         : e - (n + 4));
        }
        return out;
    }
};

void sleep_ms(int ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

void run_process_test() {
    const char* env_bin = std::getenv("RML23_UI_BIN");
    const std::string bin_path = env_bin ? env_bin : "bin/board_ui_live_rml23";
    if (::access(bin_path.c_str(), X_OK) != 0) {
        std::printf("  (skipped: %s not built -- run build_host_tests.sh first)\n",
                    bin_path.c_str());
        return;
    }

    const std::string sock =
        "/tmp/rml23_proc_" + std::to_string(::getpid()) + ".sock";
    ::unlink(sock.c_str());

    int pipefd[2];
    if (::pipe(pipefd) != 0) { check(false, "pipe()"); return; }

    const pid_t pid = ::fork();
    if (pid < 0) { check(false, "fork()"); return; }
    if (pid == 0) {
        ::dup2(pipefd[1], STDOUT_FILENO);
        ::dup2(pipefd[1], STDERR_FILENO);
        ::close(pipefd[0]);
        ::close(pipefd[1]);
        ::execl(bin_path.c_str(), bin_path.c_str(), "--headless",
                "--sock", sock.c_str(), "--stale-ms", "1200", "--tick-ms", "40",
                "--model-sha", kModelSha, static_cast<char*>(nullptr));
        _exit(127);
    }
    ::close(pipefd[1]);

    OutputCapture cap;
    cap.fd = pipefd[0];
    cap.start();

    bool ready = false;
    for (int i = 0; i < 100 && !ready; ++i) {
        sleep_ms(40);
        ready = cap.has("UI_LIVE_READY");
    }
    check(ready, "UI binary reaches UI_LIVE_READY");
    if (!ready) {
        ::kill(pid, SIGKILL);
        cap.stop();
        ::waitpid(pid, nullptr, 0);
        return;
    }

    {
        ui::UnixSocketSink sink(sock);   // connects on first write; closing -> gone

        // A. NO_SIGNAL heartbeat flow: 8 heartbeats @ 350 ms (<< stale 1200 ms).
        for (int i = 0; i < 8; ++i) {
            sink.write(hb_line("RUNNING", "NO_SIGNAL", 1000 + i));
            sleep_ms(350);
        }
        sleep_ms(200);
        check(cap.has("UI_RX type=state version=rml23-chain-v2 valid=1"),
              "UI receives state heartbeats");
        check(cap.last_status_new() == "NO_SIGNAL",
              "RUNNING + NO_SIGNAL heartbeat -> NO_SIGNAL badge");
        check(!cap.has("new=STALE_DATA"),
              "no STALE during a live NO_SIGNAL heartbeat flow");

        // B. STOPPED state (heartbeat still flows): -> STOPPED, not STALE.
        sink.write(hb_line("STOPPED", "NO_SIGNAL", 9999));
        bool stopped = false;
        for (int i = 0; i < 50 && !stopped; ++i) { sleep_ms(40); stopped = cap.has("new=STOPPED"); }
        check(stopped, "STOPPED state -> STOPPED badge (heartbeat still alive)");
        check(!cap.has("new=STALE_DATA"), "STOPPED is not STALE (still heartbeating)");

        // C. RUNNING + SIGNAL_PRESENT result -> LIVE.
        sink.write(hb_line("RUNNING", "SIGNAL_PRESENT", 20000));
        sleep_ms(80);
        sink.write(result_line());
        bool live = false;
        for (int i = 0; i < 50 && !live; ++i) { sleep_ms(40); live = cap.has("new=LIVE"); }
        check(live, "RUNNING + SIGNAL_PRESENT result -> LIVE badge");
        check(cap.has("UI_RX type=result version=rml23-chain-v2 valid=1"),
              "UI receives a valid result frame");

        // D1. quiet > stale_ms (socket still open) -> STALE reason=timeout.
        bool timeout_stale = false;
        for (int i = 0; i < 60 && !timeout_stale; ++i) {
            sleep_ms(50);
            timeout_stale = cap.has("reason=timeout");
        }
        check(timeout_stale, "quiet > stale_ms -> STALE reason=timeout");
    }   // sink destroyed -> producer socket closed

    // D2. producer gone -> STALE reason=disconnected.
    bool disc = false;
    for (int i = 0; i < 50 && !disc; ++i) { sleep_ms(40); disc = cap.has("reason=disconnected"); }
    check(disc, "producer gone (socket closed) -> STALE reason=disconnected");

    check(cap.has("UI_RX_STATS"), "UI_RX_STATS cumulative report emitted");

    ::kill(pid, SIGTERM);
    int status = 0;
    for (int i = 0; i < 50; ++i) {
        if (::waitpid(pid, &status, WNOHANG) == pid) break;
        sleep_ms(20);
    }
    cap.stop();
    ::unlink(sock.c_str());
}

#else
void run_process_test() {
    std::printf("  (skipped: no fork/AF_UNIX on this platform)\n");
}
#endif

}  // namespace

int main() {
    std::printf("test_ui_live_rx_process\n");
    run_process_test();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
