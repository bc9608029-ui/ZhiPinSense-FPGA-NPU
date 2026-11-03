#pragma once

// target_list_dispatch.hpp -- event-line routing for the multi-target receiver.
//
// The live server's drain loop tries, in order: result frame, rml24_targets,
// state event, else rejected.  The three wire `type` tokens are disjoint, so a
// line belongs to at most one kind.  This header owns the rml24_targets arm of
// that routing as a pure, iCraft-free, host-testable function:
//
//   dispatch_targets_line(line) -> { Valid, Rejected, NotATargetsLine }
//
//   Valid            : wire type == "rml24_targets" and the parser accepted it.
//                      The caller applies it to TargetListState and MUST NOT
//                      count it rejected / state_rejected.
//   Rejected         : wire type == "rml24_targets" but the parser rejected it
//                      (malformed / contract violation).  The caller counts it
//                      rejected (and targets_rejected), NEVER state_rejected.
//   NotATargetsLine  : wire type is something else (result / state / garbage);
//                      the caller falls through to the state branch unchanged.
//
// The wire-type sniff below is fail-closed and order-independent: it scans the
// top-level object's string keys for `"type"` and compares its string value, so
// it does not matter whether `type` is the first key.  It never throws.

#include "target_list_rml24_parse.hpp"

#include <cstddef>
#include <string>

namespace ui {

namespace detail {

// Scan a JSON object's top-level string keys for `"type"` and compare its string
// value to `want`.  Handles whitespace, string escapes, and nested objects /
// arrays (depth counting) so a "type" key anywhere at the top level is found.
// Returns false on any structural malformation; never throws.
inline bool wire_type_is(const std::string& line, const char* want) {
    const std::size_t n = line.size();
    std::size_t i = 0;
    auto skip_ws = [&] {
        while (i < n && (line[i] == ' ' || line[i] == '\t' ||
                         line[i] == '\n' || line[i] == '\r')) ++i;
    };
    // Read a JSON string whose opening quote is at position i; i advances past
    // the closing quote.  Unescapes minimally (keeps the raw bytes for the value
    // comparison below; escape sequences are not needed for these wire tokens).
    auto read_string = [&](std::string& out) -> bool {
        if (i >= n || line[i] != '"') return false;
        ++i;
        out.clear();
        bool esc = false;
        while (i < n) {
            const char ch = line[i];
            if (!esc && ch == '"') { ++i; return true; }
            if (!esc && ch == '\\') { esc = true; ++i; continue; }
            out += ch;
            esc = false;
            ++i;
        }
        return false;   // unterminated
    };
    skip_ws();
    if (i >= n || line[i] != '{') return false;
    ++i;
    while (true) {
        skip_ws();
        if (i >= n) return false;
        if (line[i] == '}') return false;          // empty object / end reached
        if (line[i] != '"') return false;          // key must be a string
        std::string key;
        if (!read_string(key)) return false;
        skip_ws();
        if (i >= n || line[i] != ':') return false;
        ++i;
        skip_ws();
        if (i >= n) return false;
        if (key == "type") {
            if (line[i] != '"') return false;      // type value must be a string
            std::string val;
            if (!read_string(val)) return false;
            return val == want;
        }
        // Skip the value: string / nested object / nested array / scalar.
        if (line[i] == '"') {
            std::string dummy;
            if (!read_string(dummy)) return false;
        } else if (line[i] == '{' || line[i] == '[') {
            const char open = line[i];
            const char close = (open == '{') ? '}' : ']';
            int depth = 0;
            bool in_str = false, esc = false;
            for (; i < n; ++i) {
                const char ch = line[i];
                if (in_str) {
                    if (esc) esc = false;
                    else if (ch == '\\') esc = true;
                    else if (ch == '"') in_str = false;
                    continue;
                }
                if (ch == '"') { in_str = true; continue; }
                if (ch == open) ++depth;
                else if (ch == close) { --depth; if (depth == 0) { ++i; break; } }
            }
        } else {
            while (i < n && line[i] != ',' && line[i] != '}') ++i;
        }
        skip_ws();
        if (i >= n) return false;
        if (line[i] == '}') return false;          // type not this line's token
        if (line[i] != ',') return false;
        ++i;
    }
}

}  // namespace detail

struct TargetsDispatchOutcome {
    enum class Kind { Valid, Rejected, NotATargetsLine };
    Kind kind = Kind::NotATargetsLine;
    TargetListEvent event;
};

// True iff the wire "type" token of `line` is exactly "rml24_targets".
inline bool is_rml24_targets_line(const std::string& line) {
    return detail::wire_type_is(line, "rml24_targets");
}

// Route one line for the rml24_targets arm.  See the header comment.
inline TargetsDispatchOutcome dispatch_targets_line(const std::string& line) {
    TargetsDispatchOutcome o;
    if (!is_rml24_targets_line(line)) return o;   // NotATargetsLine
    o.event = parse_rml24_targets(line);
    o.kind = o.event.ok ? TargetsDispatchOutcome::Kind::Valid
                        : TargetsDispatchOutcome::Kind::Rejected;
    return o;
}

}  // namespace ui
