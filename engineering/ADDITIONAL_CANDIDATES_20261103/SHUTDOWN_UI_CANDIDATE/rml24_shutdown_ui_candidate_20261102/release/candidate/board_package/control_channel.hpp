#pragma once

// control_channel.hpp -- reverse control channel with hardware/control separation
// (task 39e5 UI v3 Task E).  Fixes the real-machine defect where a long production
// step (LO tune / BAND SCAN dwell / RX refill / NPU infer) blocked the control
// socket: SET_MODE timed out, STOP never reached the screen, BAND SCAN could not be
// interrupted.  The fix decouples control RECEPTION from command APPLICATION:
//
//      control thread (non-blocking poll on the control socket)
//          |  parse + validate + assign command_id, reply "OK accepted ..." <=500ms
//          v
//      bounded thread-safe command queue
//          |  the unique producer thread drains it at safe points
//          v
//      producer applies command (sole owner of Pluto / LO / gain / NPU)
//          |  publish {"type":"state",...} to UI  +  "OK applied ..." ack
//          v
//      UI state event  +  ack forwarded by the control thread
//
// Hard rules (frozen):
//   * the control thread only parses / validates / enqueues / replies -- it NEVER
//     touches libiio, never re-tunes the LO, never changes gain, never calls the NPU;
//   * Pluto and the NPU stay owned by the unique producer thread;
//   * a mutex-guarded bounded queue + atomics guarantee no data race;
//   * no detached thread: the producer joins the control thread and unlinks the
//     socket on exit;
//   * STATUS is answered by the control thread straight from the atomic snapshot, so
//     it stays responsive even while the producer is blocked inside a libiio call.
//
// POSIX-only control socket (Linux board / WSL host); the queue / state / stats and
// status_reply() are pure C++ and host-testable without any socket.

#include <atomic>
#include <chrono>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

#include "mode_control.hpp"
#include "unix_socket_server.hpp"

namespace ctl {

inline std::int64_t now_us() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

// One accepted command, waiting for the producer to apply it.
struct Command {
    std::uint64_t id = 0;         // monotonic, assigned by the control thread
    std::string raw;              // original line, e.g. "SET_MODE FIXED"
    std::int64_t accepted_us = 0; // steady_clock timestamp when accepted
};

// Bounded thread-safe FIFO (control thread -> producer).  Overflow is reported to
// the client as "ERR queue_full" -- never a silent drop.
class CommandQueue {
public:
    explicit CommandQueue(std::size_t cap = 32) : cap_(cap) {}

    bool try_push(Command c) {
        std::lock_guard<std::mutex> lk(mu_);
        if (q_.size() >= cap_) return false;
        q_.push_back(std::move(c));
        if (q_.size() > max_depth_) max_depth_ = q_.size();
        return true;
    }
    bool try_pop(Command& c) {
        std::lock_guard<std::mutex> lk(mu_);
        if (q_.empty()) return false;
        c = std::move(q_.front());
        q_.pop_front();
        return true;
    }
    std::size_t depth() const {
        std::lock_guard<std::mutex> lk(mu_);
        return q_.size();
    }
    std::size_t max_depth() const {
        std::lock_guard<std::mutex> lk(mu_);
        return max_depth_;
    }

private:
    mutable std::mutex mu_;
    std::deque<Command> q_;
    std::size_t cap_;
    std::size_t max_depth_ = 0;
};

// Bounded thread-safe FIFO of "OK applied ..." reply lines (producer -> control
// thread).  The control thread owns the socket, so the producer never writes it
// directly; it enqueues the ack and the control thread forwards it on the next tick.
class AckQueue {
public:
    explicit AckQueue(std::size_t cap = 32) : cap_(cap) {}

    bool try_push(std::string line) {
        std::lock_guard<std::mutex> lk(mu_);
        if (q_.size() >= cap_) return false;
        q_.push_back(std::move(line));
        return true;
    }
    bool try_pop(std::string& line) {
        std::lock_guard<std::mutex> lk(mu_);
        if (q_.empty()) return false;
        line = std::move(q_.front());
        q_.pop_front();
        return true;
    }

private:
    mutable std::mutex mu_;
    std::deque<std::string> q_;
    std::size_t cap_;
};

// Lock-free snapshot shared by the control thread (STATUS) and the producer.  Mode
// values are mode_ctl::ModeKind as int; running is 0/1.  requested_* is what the
// last accepted command(s) asked for; applied_* is what the producer has actually
// applied.  When they diverge, a command is still queued.
class ControlState {
public:
    std::atomic<int> requested_mode{0};
    std::atomic<int> applied_mode{0};
    std::atomic<int> requested_running{1};
    std::atomic<int> applied_running{1};
    std::atomic<std::uint64_t> last_command_id{0};
    std::atomic<std::uint64_t> last_applied_command_id{0};
    std::atomic<std::uint64_t> queue_depth{0};
    std::atomic<bool> stop{false};   // set by the producer to end the control thread
};

// Accumulated control-channel statistics for CONTROL_STATS / GATE_RESULT.
struct ControlStats {
    std::atomic<std::uint64_t> received{0};
    std::atomic<std::uint64_t> accepted{0};
    std::atomic<std::uint64_t> applied{0};
    std::atomic<std::uint64_t> rejected{0};
    std::atomic<std::uint64_t> timeouts{0};          // apply latency > apply_timeout_ms
    std::atomic<std::uint64_t> queue_max_depth{0};
    std::atomic<std::int64_t> max_accept_latency_ms{0};
    std::atomic<std::int64_t> max_apply_latency_ms{0};
};

// One-line STATUS reply.  Starts with "OK", carries the new requested/applied fields
// AND the legacy mode=/running= keys for compatibility with the current scripts.
inline std::string status_reply(const ControlState& st) {
    const auto app_mode = static_cast<mode_ctl::ModeKind>(st.applied_mode.load());
    const auto req_mode = static_cast<mode_ctl::ModeKind>(st.requested_mode.load());
    const int app_run = st.applied_running.load();
    const int req_run = st.requested_running.load();
    return std::string("OK requested_mode=") + mode_ctl::mode_token(req_mode) +
           " applied_mode=" + mode_ctl::mode_token(app_mode) +
           " requested_running=" + std::to_string(req_run) +
           " applied_running=" + std::to_string(app_run) +
           " last_command_id=" + std::to_string(st.last_command_id.load()) +
           " last_applied_command_id=" + std::to_string(st.last_applied_command_id.load()) +
           " control_queue_depth=" + std::to_string(st.queue_depth.load()) +
           " mode=" + mode_ctl::mode_token(app_mode) +
           " running=" + std::to_string(app_run);
}

// The control thread body.  Polls the control socket in short slices, accepts and
// forecasts each command on the mirror (pure), enqueues it, replies ACCEPTED, and
// forwards any APPLIED acks.  Exits when `state.stop` is set.  `mirror` is the
// control thread's own copy of the mode state (kept in step with requested_*).
// All socket I/O happens here, so client_fd_ is never accessed concurrently.
inline void control_thread_main(ui::UnixSocketServer& sock,
                                CommandQueue& cmds, AckQueue& acks,
                                ControlState& state, ControlStats& stats,
                                mode_ctl::ModeState& mirror) {
    while (!state.stop.load(std::memory_order_relaxed)) {
        const ui::UnixSocketServer::PollResult pr = sock.poll(50);
        for (const std::string& line : pr.lines) {
            stats.received.fetch_add(1, std::memory_order_relaxed);
            const std::int64_t t0 = now_us();

            const std::vector<std::string> toks = mode_ctl::split_ws(line);
            if (toks.empty()) {
                sock.reply("ERR empty_command");
                stats.rejected.fetch_add(1, std::memory_order_relaxed);
                continue;
            }
            if (toks[0] == "STATUS") {
                // Read-only: answered directly from the snapshot, never queued.
                sock.reply(status_reply(state));
                continue;
            }

            // Mutating command (SET_MODE / START / STOP / unknown).  Forecast it on
            // the mirror (pure, no hardware) to validate + track requested state.
            const mode_ctl::ParseResult fc = mode_ctl::parse_command(mirror, line);
            if (!fc.ok) {
                sock.reply(fc.reply);   // "ERR ..." -- fail-closed, nothing queued
                stats.rejected.fetch_add(1, std::memory_order_relaxed);
                continue;
            }

            const std::uint64_t id = state.last_command_id.load(std::memory_order_relaxed) + 1;
            Command cmd;
            cmd.id = id;
            cmd.raw = line;
            cmd.accepted_us = t0;
            if (!cmds.try_push(std::move(cmd))) {
                sock.reply("ERR queue_full");
                stats.rejected.fetch_add(1, std::memory_order_relaxed);
                continue;
            }

            mirror.mode = fc.new_mode;
            mirror.run = fc.new_run;
            state.last_command_id.store(id, std::memory_order_relaxed);
            state.requested_mode.store(static_cast<int>(mirror.mode), std::memory_order_relaxed);
            state.requested_running.store(
                mirror.run == mode_ctl::RunState::Running ? 1 : 0, std::memory_order_relaxed);
            state.queue_depth.store(cmds.depth(), std::memory_order_relaxed);
            stats.accepted.fetch_add(1, std::memory_order_relaxed);

            const std::uint64_t qd = cmds.depth();
            std::uint64_t pm = stats.queue_max_depth.load(std::memory_order_relaxed);
            while (qd > pm && !stats.queue_max_depth.compare_exchange_weak(pm, qd)) {}

            const std::int64_t lat = (now_us() - t0) / 1000;
            std::int64_t am = stats.max_accept_latency_ms.load(std::memory_order_relaxed);
            while (lat > am && !stats.max_accept_latency_ms.compare_exchange_weak(am, lat)) {}

            sock.reply("OK accepted command_id=" + std::to_string(id) + " " + line);
        }
        std::string ack;
        while (acks.try_pop(ack)) sock.reply(ack);
    }
}

}  // namespace ctl
