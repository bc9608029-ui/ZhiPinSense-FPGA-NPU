#pragma once

// mode_control.hpp -- reverse control-channel state machine (task 39e5 UI v3 M6).
//
// Pure-logic, iCraft-free, header-only.  The LIVE UI server listens on a SECOND
// AF_UNIX socket (default /run/sdr_amr_control.sock) in addition to the result
// data socket.  Each complete command line received on that control socket is fed
// through apply_command(), which mutates a ModeState and returns a one-line ASCII
// reply ("OK ..." / "ERR ...") the server writes back to the control client.
//
// This is the single source of truth for two system-level control facts that are
// NOT per-frame classification data (and therefore never travel inside a
// ResultFrame):
//   * the work mode  -- FIXED / AUTO LOCK / BAND SCAN, and
//   * the run state  -- RUNNING / STOPPED.
//
// Commands (one per line, whitespace-separated, case-sensitive, fail-closed):
//   SET_MODE FIXED | AUTO_LOCK | BAND_SCAN   -> switch work mode
//   START                                    -> RUNNING
//   STOP                                     -> STOPPED
//   STATUS                                   -> report current mode + run state
// A malformed / unknown command mutates NOTHING and returns "ERR ...".  Never
// throws; safe to call from the display loop, and safe to unit-test on the host.
//
// M6 scope: the channel + state are authoritative and rendered/logged.  The
// mode-specific DSP / scan behaviour (what FIXED / AUTO LOCK / BAND SCAN actually
// DO to gain and capture) arrives in M7 / M8 / M10 and consumes this state.

#include <string>
#include <vector>

namespace mode_ctl {

enum class ModeKind { Fixed, AutoLock, BandScan, ContinuousScan };
enum class RunState { Stopped, Running };

struct ModeState {
    ModeKind mode = ModeKind::Fixed;
    RunState run = RunState::Running;   // the display is already streaming by default
};

// Display names (space-separated, for the MODE page) and wire tokens
// (underscore-separated, for SET_MODE -- avoids whitespace ambiguity).
inline const char* mode_display_name(ModeKind m) {
    switch (m) {
        case ModeKind::AutoLock: return "AUTO LOCK";
        case ModeKind::ContinuousScan: return "SWEEP";
        case ModeKind::BandScan: return "SEARCH LOCK";
        case ModeKind::Fixed:
        default:                 return "FIXED";
    }
}

inline const char* mode_token(ModeKind m) {
    switch (m) {
        case ModeKind::AutoLock: return "AUTO_LOCK";
        case ModeKind::ContinuousScan: return "CONTINUOUS_SCAN";
        case ModeKind::BandScan: return "BAND_SCAN";
        case ModeKind::Fixed:
        default:                 return "FIXED";
    }
}

inline const char* run_display_name(RunState r) {
    return (r == RunState::Running) ? "RUNNING" : "STOPPED";
}

inline bool mode_from_token(const std::string& tok, ModeKind& out) {
    if (tok == "CONTINUOUS_SCAN" || tok == "CONTINUOUS SCAN" || tok == "SWEEP") { out = ModeKind::ContinuousScan; return true; }
    if (tok == "SEARCH LOCK" || tok == "BAND SCAN") { out = ModeKind::BandScan; return true; }
    if (tok == "FIXED")     { out = ModeKind::Fixed;    return true; }
    if (tok == "AUTO_LOCK") { out = ModeKind::AutoLock; return true; }
    if (tok == "BAND_SCAN") { out = ModeKind::BandScan; return true; }
    return false;
}

// Split a command line into whitespace-separated tokens (' ', '\t', '\r').
inline std::vector<std::string> split_ws(const std::string& line) {
    std::vector<std::string> out;
    std::size_t i = 0;
    while (i < line.size()) {
        while (i < line.size() &&
               (line[i] == ' ' || line[i] == '\t' || line[i] == '\r')) ++i;
        if (i >= line.size()) break;
        std::size_t j = i;
        while (j < line.size() &&
               line[j] != ' ' && line[j] != '\t' && line[j] != '\r') ++j;
        out.push_back(line.substr(i, j - i));
        i = j;
    }
    return out;
}

// Apply one command line to `st`.  On success mutates `st` and returns "OK ...";
// on any malformed / unknown input mutates NOTHING and returns "ERR ...".  Never
// throws.
inline std::string apply_command(ModeState& st, const std::string& line) {
    const std::vector<std::string> toks = split_ws(line);
    if (toks.empty()) return "ERR empty_command";
    const std::string& cmd = toks[0];

    if (cmd == "SET_MODE") {
        if (toks.size() != 2) return "ERR set_mode_usage";
        ModeKind m;
        if (!mode_from_token(toks[1], m)) return "ERR unknown_mode";
        st.mode = m;
        return std::string("OK mode=") + mode_token(m);
    }
    if (cmd == "START") {
        if (toks.size() != 1) return "ERR start_usage";
        st.run = RunState::Running;
        return "OK running=1";
    }
    if (cmd == "STOP") {
        if (toks.size() != 1) return "ERR stop_usage";
        st.run = RunState::Stopped;
        return "OK running=0";
    }
    if (cmd == "STATUS") {
        if (toks.size() != 1) return "ERR status_usage";
        return std::string("OK mode=") + mode_token(st.mode) +
               " running=" + (st.run == RunState::Running ? "1" : "0");
    }
    return "ERR unknown_command";
}

// One-line machine-parseable summary of the current state (no trailing newline),
// for logging / STATUS.
inline std::string mode_state_line(const ModeState& st) {
    return std::string("mode=") + mode_token(st.mode) +
           " running=" + (st.run == RunState::Running ? "1" : "0");
}

// Result of PREDICTING one command's effect on a state COPY, without mutating the
// caller's state.  The control thread uses this to validate + forecast a command
// BEFORE it is queued (so ACCEPTED can be answered immediately and the requested
// state can be tracked without touching the producer's authoritative state).
struct ParseResult {
    bool ok = false;                // command is legal (would return "OK ...")
    std::string reply;              // "OK ..." / "ERR ..." (== apply_command output)
    ModeKind new_mode = ModeKind::Fixed;
    RunState new_run = RunState::Running;
};

// Pure, non-mutating forecast of apply_command(): applies the line to a copy.
inline ParseResult parse_command(const ModeState& cur, const std::string& line) {
    ParseResult r;
    ModeState copy = cur;
    r.reply = apply_command(copy, line);
    if (r.reply.rfind("OK", 0) == 0) {
        r.ok = true;
        r.new_mode = copy.mode;
        r.new_run = copy.run;
    }
    return r;
}

}  // namespace mode_ctl
