#pragma once

// touch_mode_control.hpp -- third-page physical touch mode control (task 39e5 UI
// v3 M16).  Two pure-logic, iCraft-free pieces:
//
//   ControlTapDetector -- turns the evdev touch stream into discrete button taps
//     on the MODE page's four buttons (FIXED / BAND SCAN / START / STOP).
//     AUTO_LOCK is intentionally not user-facing: lock/reacquire is an internal
//     BAND_SCAN state. One press+release inside the SAME button = one tap; a long press is
//     still one command (emitted only on release); a drag out of the button
//     cancels.  Geometry is the single source of truth shared with the renderer:
//     ui::mode_ui::button_rect().
//
//   ModeControlState -- the request/apply state machine.  It keeps what the UI
//     asked for (requested_*) separate from what the producer actually applied
//     (applied_*), tracks at most one in-flight mode command and one in-flight run
//     command (so a mode switch and a STOP can be outstanding concurrently, and a
//     STOP is never permanently blocked by a mode request), and folds every
//     producer reply (ACCEPTED / APPLIED / ERR / STATUS) plus the data-plane state
//     events into one consistent view.
//
//   UI  --tap-->  ModeControlState.request()  --line-->  control client
//                 (requested_* advance)                    |
//                 (slot marked pending)                    v
//   producer replies / state events feed back on_reply()/sync_applied()
//                 (applied_* advance ONLY here)
//
// Hard rules (frozen):
//   * touch only modifies requested_*; applied_* advances ONLY on producer
//     evidence (APPLIED ack / STATUS / state event);
//   * a REJECTED or TIMEOUT command leaves applied_* untouched (the original
//     actual mode is kept);
//   * a reply for an old / unknown command id is ignored;
//   * two independent slots (mode + run) mean a STOP is high-priority and a new
//     mode can be chosen during STOP.
//
// Never throws; header-only; host-testable without any socket.

#include "../ui_sw/ui_render.hpp"   // ui::mode_ui button geometry
#include "mode_control.hpp"          // mode_ctl::ModeKind / RunState / tokens
#include "touch_geometry.hpp"        // ui_touch::Point

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>

namespace mctl {

// ---- command lines (single source of truth) --------------------------------
inline std::string mode_command_line(mode_ctl::ModeKind m) {
    return std::string("SET_MODE ") + mode_ctl::mode_token(m);
}
inline std::string run_command_line(bool start) { return start ? "START" : "STOP"; }

// ---- tap detection ----------------------------------------------------------
// One press+release inside the same button = one tap; a long press is still one
// command (emitted on release); a drag out of the button cancels.  Debounced like
// the bottom-nav (consecutive taps within debounce_ms are folded).  Fed on EVERY
// sample so the down/up edge state stays consistent regardless of page; the caller
// only ACTS on the returned button when on the MODE page and the control client is
// connected.
class ControlTapDetector {
public:
    // debounce_ms folds a repeat tap on the SAME button; move_tolerance_px lets a
    // few px of finger drift between down and up NOT cancel the tap (a real drag
    // far outside the button still cancels).  M18-SW1 Task A: the old detector
    // cancelled on a single 1px drift and shared one global debounce across all
    // five buttons, so a first click on a different button could be silently eaten.
    explicit ControlTapDetector(std::int64_t debounce_ms = 400,
                                int move_tolerance_px = 24)
        : debounce_ms_(debounce_ms), move_tolerance_px_(move_tolerance_px) {
        for (int i = 0; i < ui::mode_ui::kBtnCount; ++i) last_tap_ms_[i] = -1000000;
    }

    // Returns the tapped button index 0..3 on a valid release, else -1.
    int on_sample(bool touching, const ui_touch::Point& p, std::int64_t now_ms) {
        last_edge_ = Edge::None;
        int result = -1;
        if (touching && !was_touching_) {
            // down edge: begin a NEW touch sequence and latch the button.
            ++sequence_id_;
            down_x_ = p.x; down_y_ = p.y;
            up_x_ = -1; up_y_ = -1;
            hit_target_ = -1;
            down_button_ = hit_test(p);
            down_valid_ = (down_button_ >= 0);
            if (down_valid_) hit_target_ = down_button_;
            last_edge_ = Edge::Down;
        } else if (touching && was_touching_) {
            // move while pressed: only a LARGE drift out of the down button cancels
            // (a few px of finger drift must NOT cancel the tap).
            if (down_valid_ && !point_in_button(p, down_button_, move_tolerance_px_)) {
                down_valid_ = false;
            }
        } else if (!touching && was_touching_) {
            // up edge: a tap ends here.
            up_x_ = p.x; up_y_ = p.y;
            const int btn = down_button_;
            down_button_ = -1;
            const bool valid = down_valid_;
            down_valid_ = false;
            last_edge_ = Edge::Up;
            // Per-button debounce: a fast tap on a DIFFERENT button is never folded
            // by the previous button's tap (no global debounce killing a valid click).
            if (valid && btn >= 0 && (now_ms - last_tap_ms_[btn]) >= debounce_ms_) {
                last_tap_ms_[btn] = now_ms;
                result = btn;
            }
        }
        // ALWAYS update was_touching_, including on the tap-fired path: the old code
        // returned early and left was_touching_ stuck true, so the next press was
        // read as a "move" and its tap was silently eaten (first-click bug).
        was_touching_ = touching;
        return result;
    }

    enum class Edge { None, Down, Up };
    Edge last_edge() const { return last_edge_; }
    // The button currently pressed (>=0) while down & valid, else -1.  Used for an
    // immediate press-highlight on down so the first click visibly registers.
    int pressed_button() const {
        return (was_touching_ && down_valid_ && down_button_ >= 0) ? down_button_ : -1;
    }

    // Diagnostic accessors (one touch sequence == one down->up).
    std::uint64_t sequence_id() const { return sequence_id_; }
    int down_x() const { return down_x_; }
    int down_y() const { return down_y_; }
    int up_x() const { return up_x_; }
    int up_y() const { return up_y_; }
    int hit_target() const { return hit_target_; }

private:
    static int hit_test(const ui_touch::Point& p) {
        if (!p.valid) return -1;
        for (int i = 0; i < ui::mode_ui::kBtnCount; ++i)
            if (point_in_button(p, i, 0)) return i;
        return -1;
    }
    static bool point_in_button(const ui_touch::Point& p, int i, int pad) {
        if (!p.valid) return false;
        int x0, y0, x1, y1;
        ui::mode_ui::button_rect(i, x0, y0, x1, y1);
        return p.x >= x0 - pad && p.x <= x1 + pad && p.y >= y0 - pad && p.y <= y1 + pad;
    }

    std::int64_t debounce_ms_;
    int move_tolerance_px_;
    bool was_touching_ = false;
    int down_button_ = -1;
    bool down_valid_ = false;
    std::int64_t last_tap_ms_[ui::mode_ui::kBtnCount];   // per-button debounce

    // diagnostics
    Edge last_edge_ = Edge::None;
    std::uint64_t sequence_id_ = 0;
    int down_x_ = -1, down_y_ = -1, up_x_ = -1, up_y_ = -1;
    int hit_target_ = -1;
};

// ---- touch diagnostic event (M18-SW1 Task A) --------------------------------
// One structured event per touch sequence / command lifecycle stage, emitted to
// the LOG FILE (never the control serial).  It carries every field the acceptance
// needs to reconstruct exactly what happened for each physical touch, so a "first
// click did nothing" can be diagnosed from the log instead of the screen alone.
struct TouchEvent {
    std::uint64_t seq = 0;          // touch_sequence_id (one per down->up)
    std::string phase;              // down / up / command / ack / applied / render
    int touch_down_x = -1, touch_down_y = -1;
    int touch_up_x = -1, touch_up_y = -1;
    int hit_target = -1;            // button index 0..3, -1 = none
    std::uint64_t command_id = 0;   // producer command_id (0 until ACCEPTED)
    bool command_enqueued = false;  // request produced a command line
    bool command_sent = false;      // command line written to the control socket
    bool command_ack_received = false;  // ACCEPTED ack seen (id assigned)
    bool command_applied = false;   // APPLIED ack / authoritative apply seen
    std::int64_t ack_latency_ms = -1;   // send -> apply (ms), -1 = n/a
    bool render_requested = false;  // a control-state change requested a redraw
    bool render_submitted = false;  // the redraw was physically submitted
    std::string final_state;        // IDEMPOTENT / DUPLICATE / DISCONNECTED /
                                    // SEND_FAILED / PENDING / APPLIED / REJECTED / TIMEOUT
    std::string line;               // the command line (command/ack/applied phases)
};

// Format a TouchEvent as one "TOUCH_EVENT ..." log line (no trailing newline).
// Every phase emits the full field set so a single line is self-describing.
inline std::string touch_event_line(const TouchEvent& e) {
    std::string s = "TOUCH_EVENT touch_sequence_id=" + std::to_string(e.seq) +
                    " phase=" + e.phase +
                    " touch_down_x=" + std::to_string(e.touch_down_x) +
                    " touch_down_y=" + std::to_string(e.touch_down_y) +
                    " touch_up_x=" + std::to_string(e.touch_up_x) +
                    " touch_up_y=" + std::to_string(e.touch_up_y) +
                    " hit_target=" + std::to_string(e.hit_target) +
                    " command_id=" + std::to_string(e.command_id) +
                    " command_enqueued=" + (e.command_enqueued ? "1" : "0") +
                    " command_sent=" + (e.command_sent ? "1" : "0") +
                    " command_ack_received=" + (e.command_ack_received ? "1" : "0") +
                    " command_applied=" + (e.command_applied ? "1" : "0") +
                    " ack_latency_ms=" + std::to_string(e.ack_latency_ms) +
                    " render_requested=" + (e.render_requested ? "1" : "0") +
                    " render_submitted=" + (e.render_submitted ? "1" : "0") +
                    " final_state=" + (e.final_state.empty() ? "-" : e.final_state);
    if (!e.line.empty()) s += " line=" + e.line;
    return s;
}

// ---- request/apply state machine -------------------------------------------
class ModeControlState {
public:
    struct Pending {
        bool active = false;
        std::uint64_t id = 0;          // producer command_id (0 until ACCEPTED)
        std::string line;              // exact command line sent
        mode_ctl::ModeKind mode_target = mode_ctl::ModeKind::Fixed;
        mode_ctl::RunState run_target = mode_ctl::RunState::Running;
        std::int64_t sent_ms = 0;
    };

    ModeControlState() = default;

    // ---- request ------------------------------------------------------------
    // Outcome of a button tap.  Sent = a command line should be written; the other
    // outcomes advance no command and set a transient feedback string instead, so
    // the UI can show WHY a tap did nothing (repeat-click -> "already in this mode").
    enum class RequestOutcome { Sent, Idempotent, Duplicate, Invalid };

    // Map a button tap to a command and report the precise outcome.  Every gated
    // tap counts in control_taps.  `now_ms` is accepted for signature symmetry but
    // not needed (sending is timestamped in on_sent()).
    RequestOutcome request_ex(int button, std::int64_t now_ms, std::string& out_line) {
        (void)now_ms;
        out_line.clear();
        if (button < 0 || button >= ui::mode_ui::kBtnCount) return RequestOutcome::Invalid;
        ++control_taps;

        if (button <= ui::mode_ui::kBtnBandScan) {
            const mode_ctl::ModeKind target = button_to_mode(button);
            if (mode_cmd_.active) {
                ++duplicate_commands;
                feedback_ = "COMMAND IN PROGRESS";
                return RequestOutcome::Duplicate;
            }
            if (target == applied_mode_) {
                feedback_ = "ALREADY IN THIS MODE";
                return RequestOutcome::Idempotent;
            }
            requested_mode_ = target;
            requested_initialized_ = true;
            out_line = mode_command_line(target);
            feedback_.clear();
            return RequestOutcome::Sent;
        }
        if (button == ui::mode_ui::kBtnStart) {
            if (run_cmd_.active) {
                ++duplicate_commands;
                feedback_ = "COMMAND IN PROGRESS";
                return RequestOutcome::Duplicate;
            }
            if (applied_run_ == mode_ctl::RunState::Running) {
                feedback_ = "ALREADY RUNNING";
                return RequestOutcome::Idempotent;
            }
            requested_run_ = mode_ctl::RunState::Running;
            requested_initialized_ = true;
            out_line = run_command_line(true);
            feedback_.clear();
            return RequestOutcome::Sent;
        }
        // STOP is high-priority: it lives in its own slot, so a pending mode
        // command never blocks it.
        if (run_cmd_.active) {
            ++duplicate_commands;
            feedback_ = "COMMAND IN PROGRESS";
            return RequestOutcome::Duplicate;
        }
        if (applied_run_ == mode_ctl::RunState::Stopped) {
            feedback_ = "ALREADY STOPPED";
            return RequestOutcome::Idempotent;
        }
        requested_run_ = mode_ctl::RunState::Stopped;
        requested_initialized_ = true;
        out_line = run_command_line(false);
        feedback_.clear();
        return RequestOutcome::Sent;
    }

    // bool view of request_ex(): true (fills out_line) only when a command should
    // be sent.  False (empty out_line) for duplicate / idempotent / invalid taps.
    bool request(int button, std::int64_t now_ms, std::string& out_line) {
        return request_ex(button, now_ms, out_line) == RequestOutcome::Sent;
    }

    // Record that `line` was actually sent: mark the matching slot pending and set
    // the display's last command / PENDING status.
    void on_sent(const std::string& line, std::int64_t now_ms) {
        Pending p;
        p.active = true;
        p.line = line;
        p.sent_ms = now_ms;
        if (line.rfind("SET_MODE ", 0) == 0) {
            mode_ctl::mode_from_token(line.substr(9), p.mode_target);
            mode_cmd_ = p;
        } else if (line == "START") {
            p.run_target = mode_ctl::RunState::Running;
            run_cmd_ = p;
        } else if (line == "STOP") {
            p.run_target = mode_ctl::RunState::Stopped;
            run_cmd_ = p;
        } else {
            return;   // unknown line: not a command we track
        }
        last_command_ = line;
        command_status_ = "PENDING";
        ++commands_sent;
    }

    // ---- reply handling -----------------------------------------------------
    void on_reply(const std::string& line, std::int64_t now_ms) {
        if (line.rfind("OK accepted ", 0) == 0) {
            handle_accepted(line);
        } else if (line.rfind("OK applied ", 0) == 0) {
            handle_applied(line, now_ms);
        } else if (line.rfind("OK requested_mode=", 0) == 0) {
            handle_status(line, now_ms);
        } else if (line.rfind("ERR", 0) == 0) {
            handle_err();
        }
        // anything else ignored
    }

    // Data-plane state event (carries the command_id that caused the change):
    // authoritative applied advance + pending resolution (by id, or by target when
    // the ACCEPTED id has not been seen yet).
    void sync_applied(mode_ctl::ModeKind m, bool running, std::uint64_t command_id,
                      std::int64_t now_ms = 0) {
        applied_mode_ = m;
        applied_run_ = running ? mode_ctl::RunState::Running : mode_ctl::RunState::Stopped;
        if (command_id > last_applied_command_id_) last_applied_command_id_ = command_id;

        // Only a non-zero command id can be the pending command's own evidence: the
        // initial/startup state event carries command_id=0 and must never resolve a
        // pending request (that would be a false APPLIED).
        const bool have_cid = (command_id != 0);

        if (mode_cmd_.active) {
            const bool by_id = (have_cid && mode_cmd_.id != 0 && command_id == mode_cmd_.id);
            // ACCEPTED not seen yet (id still 0): match by target.  Safe because a
            // SET_MODE is the only command that changes mode, and only one is pending.
            const bool by_target = (have_cid && mode_cmd_.id == 0 && mode_cmd_.mode_target == m);
            if (by_id || by_target) resolve_mode_as_applied(now_ms);
        }
        if (run_cmd_.active) {
            const bool by_id = (have_cid && run_cmd_.id != 0 && command_id == run_cmd_.id);
            const bool by_target = (have_cid && run_cmd_.id == 0 && run_cmd_.run_target == applied_run_);
            if (by_id || by_target) resolve_run_as_applied(now_ms);
        }
    }

    // Data-plane result frame (no command_id): advance applied_* ONLY (never
    // resolve a pending command -- result frames cannot prove WHO changed it).
    void observe_applied(mode_ctl::ModeKind m, bool running) {
        applied_mode_ = m;
        applied_run_ = running ? mode_ctl::RunState::Running : mode_ctl::RunState::Stopped;
    }

    // Applied timeout check (called once per tick).  A timed-out command leaves
    // applied_* untouched (keep the original actual mode).
    void on_tick(std::int64_t now_ms, std::int64_t timeout_ms) {
        if (timeout_ms <= 0) return;
        if (mode_cmd_.active && now_ms - mode_cmd_.sent_ms >= timeout_ms) {
            const bool is_last = (mode_cmd_.line == last_command_);
            mode_cmd_.active = false;
            mode_cmd_.id = 0;
            ++commands_timeout;
            if (is_last) command_status_ = "TIMEOUT";
        }
        if (run_cmd_.active && now_ms - run_cmd_.sent_ms >= timeout_ms) {
            const bool is_last = (run_cmd_.line == last_command_);
            run_cmd_.active = false;
            run_cmd_.id = 0;
            ++commands_timeout;
            if (is_last) command_status_ = "TIMEOUT";
        }
    }

    // Control connection change.  On disconnect the in-flight command's fate is
    // unknown: drop the pending slots (NOT counted as reject/timeout) but keep the
    // user's requested_* intent, so a reconnect + STATUS resync converges the
    // applied state against it.
    void set_connected(bool connected) {
        if (connected == connected_) return;
        connected_ = connected;
        if (!connected) {
            mode_cmd_.active = false;
            mode_cmd_.id = 0;
            run_cmd_.active = false;
            run_cmd_.id = 0;
            if (command_status_ == "PENDING") command_status_ = "--";
        }
    }
    bool connected() const { return connected_; }

    // ---- accessors (display) ------------------------------------------------
    mode_ctl::ModeKind applied_mode() const { return applied_mode_; }
    bool applied_running() const { return applied_run_ == mode_ctl::RunState::Running; }
    std::string applied_mode_display() const { return mode_ctl::mode_display_name(applied_mode_); }
    std::string requested_mode_display() const {
        return requested_initialized_
                   ? mode_ctl::mode_display_name(requested_mode_)
                   : mode_ctl::mode_display_name(applied_mode_);
    }
    bool requested_running() const {
        return requested_initialized_
                   ? (requested_run_ == mode_ctl::RunState::Running)
                   : applied_running();
    }
    std::string last_command_display() const {
        return last_command_.empty() ? std::string("--") : last_command_;
    }
    std::string command_status() const {
        return command_status_.empty() ? std::string("--") : command_status_;
    }
    bool has_pending() const { return mode_cmd_.active || run_cmd_.active; }
    const Pending& mode_pending() const { return mode_cmd_; }
    const Pending& run_pending() const { return run_cmd_; }

    // ---- accessors (M18-SW1 Task A diagnostics) ------------------------------
    // The command_id of the most-recently-sent command that is still pending, or 0.
    std::uint64_t pending_command_id() const {
        if (last_command_.rfind("SET_MODE ", 0) == 0 && mode_cmd_.active) return mode_cmd_.id;
        if ((last_command_ == "START" || last_command_ == "STOP") && run_cmd_.active)
            return run_cmd_.id;
        return 0;
    }
    std::uint64_t last_applied_command_id() const { return last_applied_command_id_; }
    const char* connection_state() const { return connected_ ? "CONNECTED" : "DISCONNECTED"; }
    std::int64_t last_ack_latency_ms() const { return last_ack_latency_ms_; }
    // Transient tap feedback (why a tap produced no command), "--" when idle.
    std::string feedback() const { return feedback_.empty() ? std::string("--") : feedback_; }
    void set_feedback(const std::string& f) { feedback_ = f; }

    // ---- stats --------------------------------------------------------------
    std::uint64_t control_taps = 0;
    std::uint64_t commands_sent = 0;
    std::uint64_t commands_applied = 0;
    std::uint64_t commands_rejected = 0;
    std::uint64_t commands_timeout = 0;
    std::uint64_t duplicate_commands = 0;

private:
    static mode_ctl::ModeKind button_to_mode(int button) {
        switch (button) {
            case ui::mode_ui::kBtnBandScan: return mode_ctl::ModeKind::BandScan;
            default:                        return mode_ctl::ModeKind::Fixed;
        }
    }

    // Record send->apply latency from a pending slot that just resolved (M18-SW1).
    void note_ack_latency(const Pending& slot, std::int64_t now_ms) {
        if (now_ms > 0 && slot.sent_ms > 0 && now_ms >= slot.sent_ms)
            last_ack_latency_ms_ = now_ms - slot.sent_ms;
    }

    void resolve_mode_as_applied(std::int64_t now_ms) {
        const bool is_last = (mode_cmd_.line == last_command_);
        note_ack_latency(mode_cmd_, now_ms);
        mode_cmd_.active = false;
        mode_cmd_.id = 0;
        ++commands_applied;
        if (is_last) command_status_ = "APPLIED";
    }
    void resolve_run_as_applied(std::int64_t now_ms) {
        const bool is_last = (run_cmd_.line == last_command_);
        note_ack_latency(run_cmd_, now_ms);
        run_cmd_.active = false;
        run_cmd_.id = 0;
        ++commands_applied;
        if (is_last) command_status_ = "APPLIED";
    }

    Pending* slot_for(const std::string& raw) {
        if (raw.rfind("SET_MODE ", 0) == 0) return &mode_cmd_;
        if (raw == "START" || raw == "STOP") return &run_cmd_;
        return nullptr;
    }

    static bool parse_command_id(const std::string& line, std::uint64_t& id) {
        const std::size_t pos = line.find("command_id=");
        if (pos == std::string::npos) return false;
        const char* s = line.c_str() + pos + 11;   // strlen("command_id=") == 11
        char* end = nullptr;
        const unsigned long long v = std::strtoull(s, &end, 10);
        if (end == s || v == 0) return false;
        id = static_cast<std::uint64_t>(v);
        return true;
    }

    static std::string trailing_line(const std::string& line) {
        const std::size_t pos = line.find("command_id=");
        if (pos == std::string::npos) return std::string();
        std::size_t i = pos + 11;
        while (i < line.size() && line[i] >= '0' && line[i] <= '9') ++i;
        if (i < line.size() && line[i] == ' ') ++i;   // skip the single space
        return line.substr(i);
    }

    void handle_accepted(const std::string& line) {
        std::uint64_t id = 0;
        if (!parse_command_id(line, id)) return;
        const std::string raw = trailing_line(line);
        Pending* slot = slot_for(raw);
        if (slot && slot->active) slot->id = id;
        // accepted != applied: the status stays PENDING.
    }

    void handle_applied(const std::string& line, std::int64_t now_ms) {
        std::uint64_t id = 0;
        const bool have_id = parse_command_id(line, id);
        const std::string raw = trailing_line(line);
        Pending* slot = slot_for(raw);
        if (!slot || !slot->active) return;                  // stale ack -> ignore
        if (have_id && slot->id != 0 && slot->id != id) return;   // old id -> ignore
        apply_line(raw, id);
        const bool is_last = (slot->line == last_command_);
        note_ack_latency(*slot, now_ms);
        slot->active = false;
        slot->id = 0;
        ++commands_applied;
        if (is_last) command_status_ = "APPLIED";
    }

    void handle_status(const std::string& line, std::int64_t now_ms) {
        mode_ctl::ModeKind am;
        if (!extract_mode_token(line, "applied_mode=", am)) return;
        applied_mode_ = am;
        applied_run_ = (extract_int_after(line, "applied_running=", 1) != 0)
                           ? mode_ctl::RunState::Running
                           : mode_ctl::RunState::Stopped;
        const std::uint64_t laid = static_cast<std::uint64_t>(
            extract_int_after(line, "last_applied_command_id=", 0));
        if (laid > last_applied_command_id_) last_applied_command_id_ = laid;

        // STATUS is authoritative after a (re)connect: a pending command whose
        // target is now the applied state has in fact been applied.
        if (mode_cmd_.active && mode_cmd_.mode_target == applied_mode_)
            resolve_mode_as_applied(now_ms);
        if (run_cmd_.active && run_cmd_.run_target == applied_run_)
            resolve_run_as_applied(now_ms);
    }

    void handle_err() {
        // The ERR reply carries no id; reject the oldest pending command.
        Pending* oldest = nullptr;
        if (mode_cmd_.active && run_cmd_.active) {
            oldest = (mode_cmd_.sent_ms <= run_cmd_.sent_ms) ? &mode_cmd_ : &run_cmd_;
        } else if (mode_cmd_.active) {
            oldest = &mode_cmd_;
        } else if (run_cmd_.active) {
            oldest = &run_cmd_;
        }
        if (oldest) {
            const bool is_last = (oldest->line == last_command_);
            oldest->active = false;
            oldest->id = 0;
            ++commands_rejected;
            if (is_last) command_status_ = "REJECTED";
        }
    }

    void apply_line(const std::string& raw, std::uint64_t id) {
        if (raw.rfind("SET_MODE ", 0) == 0) {
            mode_ctl::ModeKind m;
            if (mode_ctl::mode_from_token(raw.substr(9), m)) applied_mode_ = m;
        } else if (raw == "START") {
            applied_run_ = mode_ctl::RunState::Running;
        } else if (raw == "STOP") {
            applied_run_ = mode_ctl::RunState::Stopped;
        } else {
            return;
        }
        if (id > last_applied_command_id_) last_applied_command_id_ = id;
    }

    static bool extract_mode_token(const std::string& line, const char* key,
                                   mode_ctl::ModeKind& out) {
        const std::size_t pos = line.find(key);
        if (pos == std::string::npos) return false;
        std::size_t i = pos + std::strlen(key);
        std::size_t j = i;
        while (j < line.size() && line[j] != ' ') ++j;
        return mode_ctl::mode_from_token(line.substr(i, j - i), out);
    }

    static long extract_int_after(const std::string& line, const char* key, long def) {
        const std::size_t pos = line.find(key);
        if (pos == std::string::npos) return def;
        const char* s = line.c_str() + pos + std::strlen(key);
        char* end = nullptr;
        const long v = std::strtol(s, &end, 10);
        if (end == s) return def;
        return v;
    }

    // request side (what the UI asked for)
    mode_ctl::ModeKind requested_mode_ = mode_ctl::ModeKind::Fixed;
    mode_ctl::RunState requested_run_ = mode_ctl::RunState::Running;
    bool requested_initialized_ = false;
    // applied side (producer authoritative)
    mode_ctl::ModeKind applied_mode_ = mode_ctl::ModeKind::Fixed;
    mode_ctl::RunState applied_run_ = mode_ctl::RunState::Running;
    std::uint64_t last_applied_command_id_ = 0;

    Pending mode_cmd_;
    Pending run_cmd_;

    std::string last_command_;
    std::string command_status_;   // IDLE/-- / PENDING / APPLIED / REJECTED / TIMEOUT

    std::int64_t last_ack_latency_ms_ = -1;   // send -> apply latency (M18-SW1)
    std::string feedback_;                    // transient tap feedback (M18-SW1)

    bool connected_ = false;
};

}  // namespace mctl
