#pragma once

// target_list_rml24_parse.hpp -- strict JSON-lines parser for the multi-signal
// target-list event (C line, multi-target receiver).
//
// Wire schema (produced by the patched standalone_receiver, POINT 3):
//
//   {"type":"rml24_targets","version":"rml24-multisignal-v1",
//    "timestamp_us":N,"targets":[ ... ]}
//
// Each target record carries the frozen nine fields:
//   target_id (positive int), center_hz (positive int), bw_hz (non-negative int),
//   power_valid (NUMBER = dB above the dwell's adaptive median noise floor,
//                relative scale, NOT dBm; or null = unmeasured/invalid),
//   top3 ([{class_name, confidence}] up to 3, EMPTY when unclassified),
//   confidence (top-1 confidence, 0.0 when unclassified),
//   last_seen (seconds, >= 0), status (new|tracking|missing|expired),
//   backend (software|fpga|auto).
//
// Fail-closed: any malformed JSON or contract violation returns ok=false with a
// non-empty error.  This mirrors the board's result_frame_v2_parse.hpp style
// (hand-written recursive-descent reader, no external JSON dependency -- the
// board toolchain has none).  iCraft-free, libiio-free, header-only;
// host-testable on WSL.  It does NOT read class labels from ground truth; the
// class names are carried verbatim from the (label-blind) producer.
//
// FIXED mode never emits this event; the consumer must only render the target
// list while the chain reports work_mode == BAND_SCAN (see the state event).

#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <string>
#include <vector>

namespace ui {

struct Top3Entry {
    std::string class_name;
    double confidence = 0.0;
};

struct TargetRecord {
    std::uint64_t target_id = 0;
    std::uint64_t center_hz = 0;
    std::uint64_t bw_hz = 0;
    bool power_valid_present = false;   // false => unmeasured (null on the wire)
    double power_valid = 0.0;           // dB above adaptive median noise floor
    std::vector<Top3Entry> top3;
    double confidence = 0.0;
    double last_seen = 0.0;
    std::string status;                 // new|tracking|missing|expired
    std::string backend;                // software|fpga|auto

    bool classified() const { return !top3.empty(); }
};

struct TargetListEvent {
    bool ok = false;
    std::string error;                  // non-empty reason when !ok
    std::string version;
    std::uint64_t timestamp_us = 0;
    std::vector<TargetRecord> targets;
};

namespace detail {

class JsonReader {
public:
    explicit JsonReader(const std::string& s) : s_(s) {}

    void skip_ws() {
        while (i_ < s_.size() && is_ws(s_[i_])) ++i_;
    }
    char peek() const { return i_ < s_.size() ? s_[i_] : '\0'; }
    bool at_end() { skip_ws(); return i_ >= s_.size(); }

    bool parse_string(std::string& out) {
        if (peek() != '"') return false;
        ++i_;
        out.clear();
        while (true) {
            if (i_ >= s_.size()) return false;   // unterminated
            const char c = s_[i_++];
            if (c == '"') return true;
            if (c == '\\') {
                if (i_ >= s_.size()) return false;
                const char e = s_[i_++];
                switch (e) {
                    case '"':  out += '"';  break;
                    case '\\': out += '\\'; break;
                    case '/':  out += '/';  break;
                    case 'b':  out += '\b'; break;
                    case 'f':  out += '\f'; break;
                    case 'n':  out += '\n'; break;
                    case 'r':  out += '\r'; break;
                    case 't':  out += '\t'; break;
                    case 'u': {
                        if (i_ + 4 > s_.size()) return false;
                        unsigned code = 0;
                        for (int k = 0; k < 4; ++k) {
                            const char h = s_[i_++];
                            unsigned v;
                            if (h >= '0' && h <= '9')      v = static_cast<unsigned>(h - '0');
                            else if (h >= 'a' && h <= 'f') v = static_cast<unsigned>(h - 'a') + 10u;
                            else if (h >= 'A' && h <= 'F') v = static_cast<unsigned>(h - 'A') + 10u;
                            else return false;
                            code = (code << 4) | v;
                        }
                        append_utf8(out, code);
                        break;
                    }
                    default: return false;
                }
            } else {
                if (static_cast<unsigned char>(c) < 0x20u) return false;   // raw control
                out += c;
            }
        }
    }

    bool parse_number(double& out) {
        const std::size_t start = i_;
        if (peek() == '-') ++i_;
        if (peek() == '0') {
            ++i_;
        } else if (is_digit(peek())) {
            while (is_digit(peek())) ++i_;
        } else {
            return false;
        }
        if (peek() == '.') {
            ++i_;
            if (!is_digit(peek())) return false;
            while (is_digit(peek())) ++i_;
        }
        if (peek() == 'e' || peek() == 'E') {
            ++i_;
            if (peek() == '+' || peek() == '-') ++i_;
            if (!is_digit(peek())) return false;
            while (is_digit(peek())) ++i_;
        }
        const std::string num = s_.substr(start, i_ - start);
        char* end = nullptr;
        errno = 0;
        const double v = std::strtod(num.c_str(), &end);
        if (end != num.c_str() + num.size() || errno == ERANGE) return false;
        out = v;
        return true;
    }

    bool parse_null() { return match_lit("null"); }

    bool skip_value() {
        skip_ws();
        const char c = peek();
        if (c == '"')  { std::string s; return parse_string(s); }
        if (c == '{')  { return skip_object(); }
        if (c == '[')  { return skip_array(); }
        if (c == 'n')  { return parse_null(); }
        double d; return parse_number(d);
    }

    bool parse_targets_event(TargetListEvent& ev, std::string& err) {
        skip_ws();
        if (peek() != '{') { err = "expected '{'"; return false; }
        ++i_;

        std::string type, version;
        double timestamp_us = 0;
        bool has_type = false, has_version = false, has_timestamp = false;
        bool has_targets = false;
        std::vector<TargetRecord> targets;

        skip_ws();
        if (peek() == '}') { err = "empty object"; return false; }

        while (true) {
            std::string key;
            if (!parse_string(key)) { err = "bad key"; return false; }
            skip_ws();
            if (peek() != ':') { err = "expected ':'"; return false; }
            ++i_;
            skip_ws();

            if (key == "type") {
                has_type = true;
                if (peek() != '"' || !parse_string(type)) { err = "type not a string"; return false; }
            } else if (key == "version") {
                has_version = true;
                if (peek() != '"' || !parse_string(version)) { err = "version not a string"; return false; }
            } else if (key == "timestamp_us") {
                has_timestamp = true;
                if (!parse_number(timestamp_us)) { err = "bad timestamp_us"; return false; }
            } else if (key == "targets") {
                has_targets = true;
                if (!parse_target_array(targets, err)) return false;
            } else {
                if (!skip_value()) { err = "bad value for " + key; return false; }
            }

            skip_ws();
            if (peek() == '}') { ++i_; break; }
            if (peek() != ',') { err = "expected ',' or '}'"; return false; }
            ++i_;
            skip_ws();
        }

        if (!at_end()) { err = "trailing content"; return false; }

        if (!has_type || !has_version || !has_timestamp || !has_targets) {
            err = "missing required field";
            return false;
        }
        if (type != "rml24_targets") { err = "type != rml24_targets"; return false; }
        if (version != "rml24-multisignal-v1") { err = "version mismatch"; return false; }
        if (!std::isfinite(timestamp_us) || timestamp_us != std::floor(timestamp_us) ||
            timestamp_us < 0.0) {
            err = "timestamp_us not a non-negative integer";
            return false;
        }

        ev.ok = true;
        ev.version = version;
        ev.timestamp_us = static_cast<std::uint64_t>(timestamp_us);
        ev.targets = std::move(targets);
        return true;
    }

private:
    bool parse_target_array(std::vector<TargetRecord>& out, std::string& err) {
        skip_ws();
        if (peek() != '[') { err = "targets not an array"; return false; }
        ++i_;
        skip_ws();
        out.clear();
        if (peek() == ']') { ++i_; return true; }        // empty list is VALID (no signal)
        while (true) {
            TargetRecord rec;
            if (!parse_one_target(rec, err)) return false;
            out.push_back(std::move(rec));
            skip_ws();
            if (peek() == ']') { ++i_; return true; }
            if (peek() != ',') { err = "expected ',' or ']' in targets"; return false; }
            ++i_;
            skip_ws();
        }
    }

    bool parse_one_target(TargetRecord& rec, std::string& err) {
        skip_ws();
        if (peek() != '{') { err = "target not an object"; return false; }
        ++i_;

        double target_id = 0, center_hz = 0, bw_hz = 0, confidence = 0, last_seen = 0;
        double power_valid = 0;
        bool power_valid_null = false;
        bool has_target_id = false, has_center = false, has_bw = false;
        bool has_power = false, has_top3 = false, has_conf = false;
        bool has_last_seen = false, has_status = false, has_backend = false;
        std::vector<Top3Entry> top3;

        skip_ws();
        if (peek() == '}') { err = "empty target object"; return false; }

        while (true) {
            std::string key;
            if (!parse_string(key)) { err = "bad target key"; return false; }
            skip_ws();
            if (peek() != ':') { err = "expected ':' in target"; return false; }
            ++i_;
            skip_ws();

            if (key == "target_id") {
                has_target_id = true;
                if (!parse_number(target_id)) { err = "bad target_id"; return false; }
            } else if (key == "center_hz") {
                has_center = true;
                if (!parse_number(center_hz)) { err = "bad center_hz"; return false; }
            } else if (key == "bw_hz") {
                has_bw = true;
                if (!parse_number(bw_hz)) { err = "bad bw_hz"; return false; }
            } else if (key == "power_valid") {
                has_power = true;
                skip_ws();
                if (peek() == 'n') {          // unmeasured -> null
                    power_valid_null = true;
                    if (!parse_null()) { err = "bad power_valid null"; return false; }
                } else {
                    if (!parse_number(power_valid)) { err = "bad power_valid"; return false; }
                }
            } else if (key == "top3") {
                has_top3 = true;
                if (!parse_top3(top3, err)) return false;
            } else if (key == "confidence") {
                has_conf = true;
                if (!parse_number(confidence)) { err = "bad confidence"; return false; }
            } else if (key == "last_seen") {
                has_last_seen = true;
                if (!parse_number(last_seen)) { err = "bad last_seen"; return false; }
            } else if (key == "status") {
                has_status = true;
                if (peek() != '"' || !parse_string(rec.status)) { err = "status not a string"; return false; }
            } else if (key == "backend") {
                has_backend = true;
                if (peek() != '"' || !parse_string(rec.backend)) { err = "backend not a string"; return false; }
            } else {
                if (!skip_value()) { err = "bad value for target key " + key; return false; }
            }

            skip_ws();
            if (peek() == '}') { ++i_; break; }
            if (peek() != ',') { err = "expected ',' or '}' in target"; return false; }
            ++i_;
            skip_ws();
        }

        // ---- required nine-field presence ---------------------------------
        if (!has_target_id || !has_center || !has_bw || !has_power || !has_top3 ||
            !has_conf || !has_last_seen || !has_status || !has_backend) {
            err = "missing target field";
            return false;
        }

        // ---- validation -----------------------------------------------------
        auto pos_int = [&](double v) {
            return std::isfinite(v) && v == std::floor(v) && v > 0.0;
        };
        auto nonneg_int = [&](double v) {
            return std::isfinite(v) && v == std::floor(v) && v >= 0.0;
        };
        if (!pos_int(target_id)) { err = "target_id not a positive integer"; return false; }
        if (!pos_int(center_hz)) { err = "center_hz not a positive integer"; return false; }
        if (!nonneg_int(bw_hz))  { err = "bw_hz not a non-negative integer"; return false; }
        if (!power_valid_null && !std::isfinite(power_valid)) {
            err = "non-finite power_valid";
            return false;
        }
        if (!std::isfinite(confidence) || confidence < 0.0 || confidence > 1.0) {
            err = "confidence out of [0,1]";
            return false;
        }
        if (!std::isfinite(last_seen) || last_seen < 0.0) {
            err = "last_seen out of range";
            return false;
        }
        if (rec.status != "new" && rec.status != "tracking" &&
            rec.status != "missing" && rec.status != "expired") {
            err = "unknown target status";
            return false;
        }
        if (rec.backend != "software" && rec.backend != "fpga" && rec.backend != "auto") {
            err = "unknown backend";
            return false;
        }
        if (top3.size() > 3) { err = "top3 longer than three"; return false; }
        // An UNCLASSIFIED target (top3 empty) must carry confidence 0.0.
        if (top3.empty() && confidence != 0.0) {
            err = "unclassified target must have confidence 0.0";
            return false;
        }

        rec.target_id = static_cast<std::uint64_t>(target_id);
        rec.center_hz = static_cast<std::uint64_t>(center_hz);
        rec.bw_hz = static_cast<std::uint64_t>(bw_hz);
        rec.power_valid_present = !power_valid_null;
        rec.power_valid = power_valid;
        rec.top3 = std::move(top3);
        rec.confidence = confidence;
        rec.last_seen = last_seen;
        return true;
    }

    bool parse_top3(std::vector<Top3Entry>& out, std::string& err) {
        skip_ws();
        if (peek() != '[') { err = "top3 not an array"; return false; }
        ++i_;
        skip_ws();
        out.clear();
        if (peek() == ']') { ++i_; return true; }        // empty = unclassified
        while (true) {
            Top3Entry e;
            if (!parse_top3_entry(e, err)) return false;
            out.push_back(std::move(e));
            skip_ws();
            if (peek() == ']') { ++i_; return true; }
            if (peek() != ',') { err = "expected ',' or ']' in top3"; return false; }
            ++i_;
            skip_ws();
        }
    }

    bool parse_top3_entry(Top3Entry& e, std::string& err) {
        skip_ws();
        if (peek() != '{') { err = "top3 entry not an object"; return false; }
        ++i_;
        bool has_class = false, has_conf = false;
        double conf = 0.0;
        skip_ws();
        if (peek() == '}') { err = "empty top3 entry"; return false; }
        while (true) {
            std::string key;
            if (!parse_string(key)) { err = "bad top3 key"; return false; }
            skip_ws();
            if (peek() != ':') { err = "expected ':' in top3"; return false; }
            ++i_;
            skip_ws();
            if (key == "class_name") {
                has_class = true;
                if (peek() != '"' || !parse_string(e.class_name)) { err = "class_name not a string"; return false; }
            } else if (key == "confidence") {
                has_conf = true;
                if (!parse_number(conf)) { err = "bad top3 confidence"; return false; }
            } else {
                if (!skip_value()) { err = "bad value for top3 key " + key; return false; }
            }
            skip_ws();
            if (peek() == '}') { ++i_; break; }
            if (peek() != ',') { err = "expected ',' or '}' in top3"; return false; }
            ++i_;
            skip_ws();
        }
        if (!has_class || !has_conf) { err = "missing top3 entry field"; return false; }
        if (e.class_name.empty()) { err = "empty class_name"; return false; }
        if (!std::isfinite(conf) || conf < 0.0 || conf > 1.0) { err = "top3 confidence out of [0,1]"; return false; }
        e.confidence = conf;
        return true;
    }

    static bool is_ws(char c) {
        return c == ' ' || c == '\t' || c == '\n' || c == '\r';
    }
    static bool is_digit(char c) { return c >= '0' && c <= '9'; }
    bool match_lit(const char* lit) {
        const std::size_t n = std::string(lit).size();
        if (i_ + n > s_.size()) return false;
        if (s_.compare(i_, n, lit) != 0) return false;
        i_ += n;
        return true;
    }
    bool skip_object() {
        ++i_; skip_ws();
        if (peek() == '}') { ++i_; return true; }
        while (true) {
            std::string k; if (!parse_string(k)) return false;
            skip_ws(); if (peek() != ':') return false; ++i_;
            if (!skip_value()) return false;
            skip_ws();
            if (peek() == '}') { ++i_; return true; }
            if (peek() != ',') return false;
            ++i_; skip_ws();
        }
    }
    bool skip_array() {
        ++i_; skip_ws();
        if (peek() == ']') { ++i_; return true; }
        while (true) {
            if (!skip_value()) return false;
            skip_ws();
            if (peek() == ']') { ++i_; return true; }
            if (peek() != ',') return false;
            ++i_; skip_ws();
        }
    }
    static void append_utf8(std::string& out, unsigned cp) {
        if (cp < 0x80u) {
            out += static_cast<char>(cp);
        } else if (cp < 0x800u) {
            out += static_cast<char>(0xC0u | (cp >> 6));
            out += static_cast<char>(0x80u | (cp & 0x3Fu));
        } else if (cp < 0x10000u) {
            out += static_cast<char>(0xE0u | (cp >> 12));
            out += static_cast<char>(0x80u | ((cp >> 6) & 0x3Fu));
            out += static_cast<char>(0x80u | (cp & 0x3Fu));
        } else {
            out += static_cast<char>(0xF0u | (cp >> 18));
            out += static_cast<char>(0x80u | ((cp >> 12) & 0x3Fu));
            out += static_cast<char>(0x80u | ((cp >> 6) & 0x3Fu));
            out += static_cast<char>(0x80u | (cp & 0x3Fu));
        }
    }

    const std::string& s_;
    std::size_t i_ = 0;
};

}  // namespace detail

// Public entry point.  Never throws; returns ok=false + error on any malformed
// input or contract violation.  An empty targets array is VALID (no signal).
inline TargetListEvent parse_rml24_targets(const std::string& line) {
    TargetListEvent ev;
    detail::JsonReader r(line);
    std::string err;
    if (!r.parse_targets_event(ev, err)) {
        ev.ok = false;
        ev.error = err;
        return ev;
    }
    return ev;
}

}  // namespace ui
