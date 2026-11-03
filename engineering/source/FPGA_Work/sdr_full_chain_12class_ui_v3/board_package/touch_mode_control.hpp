#pragma once

// touch_mode_control.hpp -- third-page physical touch mode control (task 39e5 UI
// v3 M16).  Two pure-logic, iCraft-free pieces:
//
//   ControlTapDetector -- turns the evdev touch stream into discrete button taps
//     on the MODE page's five buttons (FIXED / AUTO LOCK / BAND SCAN / START /
//     STOP).  One press+release inside the SAME button = one tap; a long press is
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
    explicit ControlTapDetector(std::int64_t debounce_ms = 400)
        : debounce_ms_(debounce_ms) {}

    // Returns the tapped button index 0..4 on a valid release, else -1.
    int on_sample(bool touching, const ui_touch::Point& p, std::int64_t now_ms) {
        if (touching && !was_touching_) {
            // down edge: latch the button under the finger.
            down_button_ = hit_test(p);
            down_valid_ = (down_button_ >= 0);
        } else if (touching && was_touching_) {
            // move while pressed: leaving the down button cancels (drag).
            if (down_valid_ && !point_in_button(p, down_button_)) down_valid_ = false;
        } else if (!touching && was_touching_) {
            // up edge: a tap ends here.
            const int btn = down_button_;
            down_button_ = -1;
            const bool valid = down_valid_;
            down_valid_ = false;
            if (valid && btn >= 0 && (now_ms - last_tap_ms_) >= debounce_ms_) {
                last_tap_ms_ = now_ms;
                return btn;
            }
        }
        was_touching_ = touching;
        return -1;
    }

private:
    static int hit_test(const ui_touch::Point& p) {
        if (!p.valid) return -1;
        for (int i = 0; i < ui::mode_ui::kBtnCount; ++i)
            if (point_in_button(p, i)) return i;
        return -1;
    }
    static bool point_in_button(const ui_touch::Point& p, int i) {
        if (!p.valid) return false;
        int x0, y0, x1, y1;
        ui::mode_ui::button_rect(i, x0, y0, x1, y1);
        return p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1;
    }

    std::int64_t debounce_ms_;
    bool was_touching_ = false;
    int down_button_ = -1;
    bool down_valid_ = false;
    std::int64_t last_tap_ms_ = -1000000;   // far past => first tap always accepted
};

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
    // Map a button tap to a command.  Returns true (and fills out_line) when a
    // command should be SENT; the caller writes it to the control client and then
    // calls on_sent().  Returns false (empty out_line) when the tap is a duplicate
    // (the same slot already has a pending command) or idempotent (the button
    // already matches the applied state).  Every gated tap counts in control_taps.
    bool request(int button, std::int64_t now_ms, std::string& out_line) {
        (void)now_ms;
        out_line.clear();
        if (button < 0 || button >= ui::mode_ui::kBtnCount) return false;
        ++control_taps;

        if (button <= ui::mode_ui::kBtnBandScan) {
            const mode_ctl::ModeKind target = button_to_mode(button);
            if (mode_cmd_.active) { ++duplicate_commands; return false; }
            if (target == applied_mode_) return false;   // idempotent
            requested_mode_ = target;
            requested_initialized_ = true;
            out_line = mode_command_line(target);
            return true;
        }
        if (button == ui::mode_ui::kBtnStart) {
            if (run_cmd_.active) { ++duplicate_commands; return false; }
            if (applied_run_ == mode_ctl::RunState::Running) return false;   // idempotent
            requested_run_ = mode_ctl::RunState::Running;
            requested_initialized_ = true;
            out_line = run_command_line(true);
            return true;
        }
        // STOP is high-priority: it lives in its own slot, so a pending mode
        // command never blocks it.
        if (run_cmd_.active) { ++duplicate_commands; return false; }
        if (applied_run_ == mode_ctl::RunState::Stopped) return false;   // idempotent
        requested_run_ = mode_ctl::RunState::Stopped;
        requested_initialized_ = true;
        out_line = run_command_line(false);
        return true;
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
        (void)now_ms;
        if (line.rfind("OK accepted ", 0) == 0) {
            handle_accepted(line);
        } else if (line.rfind("OK applied ", 0) == 0) {
            handle_applied(line);
        } else if (line.rfind("OK requested_mode=", 0) == 0) {
            handle_status(line);
        } else if (line.rfind("ERR", 0) == 0) {
            handle_err();
        }
        // anything else ignored
    }

    // Data-plane state event (carries the command_id that caused the change):
    // authoritative applied advance + pending resolution (by id, or by target when
    // the ACCEPTED id has not been seen yet).
    void sync_applied(mode_ctl::ModeKind m, bool running, std::uint64_t command_id) {
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
            if (by_id || by_target) resolve_mode_as_applied();
        }
        if (run_cmd_.active) {
            const bool by_id = (have_cid && run_cmd_.id != 0 && command_id == run_cmd_.id);
            const bool by_target = (have_cid && run_cmd_.id == 0 && run_cmd_.run_target == applied_run_);
            if (by_id || by_target) resolve_run_as_applied();
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
            case ui::mode_ui::kBtnAutoLock: return mode_ctl::ModeKind::AutoLock;
            case ui::mode_ui::kBtnBandScan: return mode_ctl::ModeKind::BandScan;
            default:                        return mode_ctl::ModeKind::Fixed;
        }
    }

    void resolve_mode_as_applied() {
        const bool is_last = (mode_cmd_.line == last_command_);
        mode_cmd_.active = false;
        mode_cmd_.id = 0;
        ++commands_applied;
        if (is_last) command_status_ = "APPLIED";
    }
    void resolve_run_as_applied() {
        const bool is_last = (run_cmd_.line == last_command_);
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

    void handle_applied(const std::string& line) {
        std::uint64_t id = 0;
        const bool have_id = parse_command_id(line, id);
        const std::string raw = trailing_line(line);
        Pending* slot = slot_for(raw);
        if (!slot || !slot->active) return;                  // stale ack -> ignore
        if (have_id && slot->id != 0 && slot->id != id) return;   // old id -> ignore
        apply_line(raw, id);
        const bool is_last = (slot->line == last_command_);
        slot->active = false;
        slot->id = 0;
        ++commands_applied;
        if (is_last) command_status_ = "APPLIED";
    }

    void handle_status(const std::string& line) {
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
            resolve_mode_as_applied();
        if (run_cmd_.active && run_cmd_.run_target == applied_run_)
            resolve_run_as_applied();
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

    bool connected_ = false;
};

}  // namespace mctl
