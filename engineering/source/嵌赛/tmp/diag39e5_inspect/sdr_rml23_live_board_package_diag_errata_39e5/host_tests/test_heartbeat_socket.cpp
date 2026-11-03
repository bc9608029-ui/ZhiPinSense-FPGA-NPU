// test_heartbeat_socket.cpp -- RML23 state-heartbeat errata host test.
//
// Drives the EXACT board data plane with real AF_UNIX loopback:
//   * producer side: ui::UnixSocketSink + ui::state_line(..., "rml23-chain-v2")
//   * UI side:        ui::UnixSocketServer + ui::parse_state_frame
//
// Covers the heartbeat errata contract:
//   (1) a state heartbeat travels the SAME data socket as result frames and is
//       accepted by the version gate ("rml23-chain-v2"), with delivery counted
//       (send_attempted/send_ok/send_failed/dropped/errors);
//   (2) a valid state event refreshes the freshness clock -- >=10 s of 1000 ms
//       NO_SIGNAL heartbeats never goes STALE (5000 ms timeout);
//   (3) a state event is NEVER a result frame: it cannot forge a classification
//       or a frame_id (StateEvent carries no frame_id field), and the result
//       parser rejects a state record;
//   (4) after the producer stops, >5000 ms of quiet goes STALE, and recovery
//       (heartbeat resumes) clears it.
//
// Build/run: see host_tests/build_host_tests.sh.  POSIX-only (Linux board /
// WSL host); the socket subtests no-op elsewhere.

#include "../board_package/result_frame_rml23_parse.hpp"
#include "../board_package/result_frame_v2_parse.hpp"
#include "../board_package/ui_state_map.hpp"
#include "../board_package/unix_socket_server.hpp"
#include "../sdr_adapter/ui_report.hpp"
#include "../sdr_adapter/unix_socket_sink.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <unistd.h>   // getpid
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

std::int64_t mono_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

const char* kModelSha =
    "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba";

std::string hb_line(const char* presence, const char* run_state, std::uint64_t ts) {
    return ui::state_line("FIXED", run_state, presence, 0, ts, kModelSha,
                          "rml23-chain-v2");
}

// ---- parser version gate + state-is-not-a-result ---------------------------
void test_state_parser_contract() {
    // rml23-chain-v2 state is accepted, with every field preserved.
    {
        const ui::StateEvent se = ui::parse_state_frame(
            hb_line("NO_SIGNAL", "RUNNING", 12345));
        check(se.ok, "state(rml23-chain-v2) parses ok");
        check(se.work_mode == "FIXED", "state work_mode FIXED");
        check(se.run_state == "RUNNING", "state run_state RUNNING");
        check(se.presence_state == "NO_SIGNAL", "state presence NO_SIGNAL");
        check(se.model_sha == kModelSha, "state carries model_sha identity");
        check(se.command_id == 0, "heartbeat command_id 0");
        check(se.timestamp_us == 12345, "state timestamp_us preserved");
    }
    // Unknown version is rejected by the gate.
    {
        const ui::StateEvent se = ui::parse_state_frame(
            ui::state_line("FIXED", "RUNNING", "NO_SIGNAL", 0, 1, kModelSha,
                           "bogus-chain-v9"));
        check(!se.ok, "state(unknown version) rejected");
    }
    // A state record is NEVER a result frame (no forged classification / frame_id).
    {
        const std::string line = hb_line("NO_SIGNAL", "RUNNING", 2);
        const ui::ParseOutcome rv2 = ui::parse_result_frame_v2(line);
        const ui::ParseOutcome rr23 = ui::parse_result_frame_rml23(line);
        check(!rv2.ok, "state line rejected by 12-class result parser");
        check(!rr23.ok, "state line rejected by RML23 result parser");
        check(rv2.frame.frame_id == 0, "rejected result leaves frame_id 0");
    }
}

// ---- RUNNING + NO_SIGNAL -> NO SIGNAL, and no forged Live ------------------
void test_apply_state_event_no_signal() {
    {
        ui::UiState st;                    // default status = Live
        st.presence = "SIGNAL_PRESENT";
        const ui::StateEvent se = ui::parse_state_frame(
            hb_line("NO_SIGNAL", "RUNNING", 3));
        ui::apply_state_event(st, se);
        check(st.status == ui::Status::NoSignal,
              "RUNNING + NO_SIGNAL state -> NoSignal badge");
        check(st.presence == "NO_SIGNAL", "presence text -> NO_SIGNAL");
        check(st.running, "running -> true (RUNNING)");
    }
    {
        // A SIGNAL_PRESENT state alone must NOT promote the badge to Live
        // (Live only ever comes from a valid result frame).
        ui::UiState st;
        st.status = ui::Status::NoSignal;
        st.presence = "NO_SIGNAL";
        const ui::StateEvent se = ui::parse_state_frame(
            hb_line("SIGNAL_PRESENT", "RUNNING", 4));
        ui::apply_state_event(st, se);
        check(st.status == ui::Status::NoSignal,
              "SIGNAL_PRESENT state does NOT forge Live");
        check(st.presence == "SIGNAL_PRESENT", "presence text -> SIGNAL_PRESENT");
    }
}

#if defined(__unix__) || defined(__APPLE__)
// ---- real AF_UNIX: heartbeat delivery + freshness over >=10 s --------------
void test_heartbeat_delivery_and_freshness() {
    const std::string path =
        "/tmp/rml23_hb_" + std::to_string(::getpid()) + ".sock";
    ui::UnixSocketServer srv(path);
    check(srv.start(), "heartbeat server start()");
    ui::UnixSocketSink sink(path);

    const std::int64_t stale_ms = 5000;
    const std::int64_t hb_interval_ms = 1000;
    const std::int64_t flow_ms = 10000;   // requirement: >= 10 s of NO_SIGNAL heartbeats

    std::uint64_t state_count = 0;
    std::int64_t last_state_ms = 0;
    bool stale_during_flow = false;
    std::uint64_t ts = 0;

    const auto t0 = std::chrono::steady_clock::now();
    std::int64_t next_hb_ms = 0;

    while (true) {
        const std::int64_t now = mono_ms();
        const std::int64_t elapsed_ms =
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - t0).count();
        if (elapsed_ms >= flow_ms) break;

        if (elapsed_ms >= next_hb_ms) {
            next_hb_ms = elapsed_ms + hb_interval_ms;
            ++ts;
            sink.write(hb_line("NO_SIGNAL", "RUNNING", ts));
        }

        ui::UnixSocketServer::PollResult pr = srv.poll(20);
        for (const std::string& line : pr.lines) {
            const ui::StateEvent se = ui::parse_state_frame(line);
            if (se.ok) {
                ++state_count;
                last_state_ms = mono_ms();
            } else {
                check(false, "delivered heartbeat parses as valid state");
            }
        }

        if (last_state_ms > 0 && ui::should_be_stale(now, last_state_ms, stale_ms))
            stale_during_flow = true;
    }

    check(state_count >= 8, ">= 8 state heartbeats delivered over 10 s");
    check(!stale_during_flow, "no STALE during the 10 s heartbeat flow");
    check(sink.send_failed() == 0, "sink send_failed == 0 during flow");
    check(sink.error_count() == 0, "sink error_count == 0 during flow");
    check(sink.send_ok() >= state_count, "sink send_ok >= delivered state count");
    check(sink.send_attempted() >= state_count, "sink send_attempted >= state count");
    check(srv.received_lines() >= state_count, "server received_lines >= state count");
}

// ---- real AF_UNIX: STOP >5000 ms -> STALE, then recovery -------------------
void test_stale_then_recovery() {
    const std::string path =
        "/tmp/rml23_hbr_" + std::to_string(::getpid()) + ".sock";
    ui::UnixSocketServer srv(path);
    check(srv.start(), "recovery server start()");
    ui::UnixSocketSink sink(path);

    const std::int64_t stale_ms = 5000;
    std::int64_t last_state_ms = 0;
    std::uint64_t ts = 0;

    // Phase 1: a couple of heartbeats establish freshness.
    for (int i = 0; i < 3; ++i) {
        ++ts;
        sink.write(hb_line("NO_SIGNAL", "RUNNING", ts));
        for (int k = 0; k < 50 && last_state_ms == 0; ++k) {
            ui::UnixSocketServer::PollResult pr = srv.poll(10);
            for (const std::string& line : pr.lines)
                if (ui::parse_state_frame(line).ok) last_state_ms = mono_ms();
        }
    }
    check(last_state_ms > 0, "freshness clock established by heartbeat");

    // Phase 2: producer goes quiet for > stale_ms -> STALE.
    {
        const std::int64_t quiet_start = mono_ms();
        bool became_stale = false;
        while (mono_ms() - quiet_start < stale_ms + 1200) {
            srv.poll(50);
            if (ui::should_be_stale(mono_ms(), last_state_ms, stale_ms))
                became_stale = true;
        }
        check(became_stale, "quiet > 5000 ms becomes STALE");
    }

    // Phase 3: heartbeat resumes -> freshness recovered (no longer STALE).
    ++ts;
    sink.write(hb_line("NO_SIGNAL", "RUNNING", ts));
    {
        bool recovered = false;
        for (int k = 0; k < 100; ++k) {
            ui::UnixSocketServer::PollResult pr = srv.poll(10);
            for (const std::string& line : pr.lines)
                if (ui::parse_state_frame(line).ok) last_state_ms = mono_ms();
            if (!ui::should_be_stale(mono_ms(), last_state_ms, stale_ms)) {
                recovered = true;
                break;
            }
        }
        check(recovered, "heartbeat resumes -> STALE cleared (recovery)");
    }
}
#else
void test_heartbeat_delivery_and_freshness() {
    std::printf("  (skipped: no AF_UNIX on this platform)\n");
}
void test_stale_then_recovery() {
    std::printf("  (skipped: no AF_UNIX on this platform)\n");
}
#endif

}  // namespace

int main() {
    std::printf("test_heartbeat_socket\n");
    test_state_parser_contract();
    test_apply_state_event_no_signal();
    test_heartbeat_delivery_and_freshness();
    test_stale_then_recovery();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
