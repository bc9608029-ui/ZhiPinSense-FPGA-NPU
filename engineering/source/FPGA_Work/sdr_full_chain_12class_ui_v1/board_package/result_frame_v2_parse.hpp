#pragma once

// result_frame_v2_parse.hpp — hand-written JSON-lines parser + strict validator
// for the twelve-class chain result record (task 39e5 §四 / §七).
//
// The UI server (board_ui_live_12class) reads one result_frame_v2 JSON object per
// line from an AF_UNIX socket and must NEVER trust a peer that could be a
// different program, a corrupted stream, or a stale build.  This header parses the
// line with a small recursive-descent JSON reader (no external JSON dependency —
// the board toolchain has none) and enforces the exact §二.5 contract:
//
//   type == "result", version == "12class-chain-v1", class_count == 12,
//   argmax_idx in [0,11], argmax_class == cat::label(target_12(), argmax_idx)
//   (frozen order OOK,4ASK,AM-DSB,WBFM,2FSK,GFSK,BPSK,QPSK,8PSK,16QAM,64QAM,OFDM),
//   probabilities length 12 with every entry finite in [0,1] and |sum-1| <= 1e-3,
//   confidence == probabilities[argmax_idx] (tol 1e-4, adapts to %.6f rounding),
//   model_sha non-empty.  All numeric values must be finite (snr_db may be null).
//
// iCraft-free, libiio-free, header-only; host-testable on WSL.

#include "../sdr_adapter/categories.hpp"
#include "../sdr_adapter/result_frame.hpp"

#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <string>
#include <vector>

namespace ui {

struct ParseOutcome {
    bool ok = false;
    std::string error;      // non-empty reason when !ok
    rf::ResultFrame frame;
};

// ---- private parser --------------------------------------------------------
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

    bool parse_bool(bool& out) {
        if (match_lit("true"))  { out = true;  return true; }
        if (match_lit("false")) { out = false; return true; }
        return false;
    }

    bool parse_null() { return match_lit("null"); }

    // probabilities: [num, num, ...]
    bool parse_number_array(std::vector<double>& out) {
        skip_ws();
        if (peek() != '[') return false;
        ++i_;
        skip_ws();
        out.clear();
        if (peek() == ']') { ++i_; return true; }
        while (true) {
            double v;
            if (!parse_number(v)) return false;
            out.push_back(v);
            skip_ws();
            if (peek() == ']') { ++i_; return true; }
            if (peek() != ',') return false;
            ++i_;
            skip_ws();
        }
    }

    // Skip an arbitrary JSON value (used for any key we do not consume).
    bool skip_value() {
        skip_ws();
        const char c = peek();
        if (c == '"')  { std::string s; return parse_string(s); }
        if (c == '{')  { return skip_object(); }
        if (c == '[')  { return skip_array(); }
        if (c == 't' || c == 'f') { bool b; return parse_bool(b); }
        if (c == 'n')  { return parse_null(); }
        double d; return parse_number(d);
    }

    // Parse the top-level object into typed fields.  Returns false on malformed
    // JSON (with `err` filled) or a contract violation (err filled).  On success
    // `frame` is fully populated.
    bool parse_record(rf::ResultFrame& frame, std::string& err) {
        skip_ws();
        if (peek() != '{') { err = "expected '{'"; return false; }
        ++i_;

        // typed fields + presence flags
        std::string type, version, argmax_class, model_sha, source;
        double frame_id = 0, timestamp_us = 0, confidence = 0, quality = 0;
        double e2e_us = 0, preprocess_us = 0, classify_us = 0, snr_db = 0;
        double argmax_idx = 0, class_count = 0;
        std::vector<double> probabilities;
        bool mock = false, overflow = false, dropped = false;
        bool discontinuity = false, short_frame = false;

        bool has_type = false, has_version = false, has_argmax_class = false;
        bool has_model_sha = false, has_source = false;
        bool has_frame_id = false, has_confidence = false;
        bool has_snr = false, has_argmax_idx = false;
        bool has_class_count = false, has_probabilities = false;
        bool snr_is_null = false;

        skip_ws();
        if (peek() == '}') { err = "empty object"; return false; }

        while (true) {
            std::string key;
            if (!parse_string(key)) { err = "bad key"; return false; }
            skip_ws();
            if (peek() != ':') { err = "expected ':'"; return false; }
            ++i_;
            skip_ws();

            // Consume known keys; skip anything unknown (forward-compatible).
            if (key == "type") {
                has_type = true;
                if (peek() != '"' || !parse_string(type)) { err = "type not a string"; return false; }
            } else if (key == "version") {
                has_version = true;
                if (peek() != '"' || !parse_string(version)) { err = "version not a string"; return false; }
            } else if (key == "argmax_class") {
                has_argmax_class = true;
                if (peek() != '"' || !parse_string(argmax_class)) { err = "argmax_class not a string"; return false; }
            } else if (key == "model_sha") {
                has_model_sha = true;
                if (peek() != '"' || !parse_string(model_sha)) { err = "model_sha not a string"; return false; }
            } else if (key == "source") {
                has_source = true;
                if (peek() != '"' || !parse_string(source)) { err = "source not a string"; return false; }
            } else if (key == "frame_id") {
                has_frame_id = true;
                if (!parse_number(frame_id)) { err = "bad frame_id"; return false; }
            } else if (key == "timestamp_us") {
                if (!parse_number(timestamp_us)) { err = "bad timestamp_us"; return false; }
            } else if (key == "confidence") {
                has_confidence = true;
                if (!parse_number(confidence)) { err = "bad confidence"; return false; }
            } else if (key == "quality") {
                if (!parse_number(quality)) { err = "bad quality"; return false; }
            } else if (key == "e2e_us") {
                if (!parse_number(e2e_us)) { err = "bad e2e_us"; return false; }
            } else if (key == "preprocess_us") {
                if (!parse_number(preprocess_us)) { err = "bad preprocess_us"; return false; }
            } else if (key == "classify_us") {
                if (!parse_number(classify_us)) { err = "bad classify_us"; return false; }
            } else if (key == "snr_db") {
                has_snr = true;
                skip_ws();
                if (peek() == 'n') { snr_is_null = true; if (!parse_null()) { err = "bad null"; return false; } }
                else { if (!parse_number(snr_db)) { err = "bad snr_db"; return false; } }
            } else if (key == "argmax_idx") {
                has_argmax_idx = true;
                if (!parse_number(argmax_idx)) { err = "bad argmax_idx"; return false; }
            } else if (key == "class_count") {
                has_class_count = true;
                if (!parse_number(class_count)) { err = "bad class_count"; return false; }
            } else if (key == "probabilities") {
                has_probabilities = true;
                if (!parse_number_array(probabilities)) { err = "bad probabilities"; return false; }
            } else if (key == "mock") {
                if (!parse_bool(mock)) { err = "bad mock"; return false; }
            } else if (key == "overflow") {
                if (!parse_bool(overflow)) { err = "bad overflow"; return false; }
            } else if (key == "dropped") {
                if (!parse_bool(dropped)) { err = "bad dropped"; return false; }
            } else if (key == "discontinuity") {
                if (!parse_bool(discontinuity)) { err = "bad discontinuity"; return false; }
            } else if (key == "short_frame") {
                if (!parse_bool(short_frame)) { err = "bad short_frame"; return false; }
            } else {
                if (!skip_value()) { err = "bad value for " + key; return false; }
            }

            skip_ws();
            if (peek() == '}') { ++i_; break; }
            if (peek() != ',') { err = "expected ',' or '}'"; return false; }
            ++i_;
            skip_ws();
        }

        // No trailing content allowed after the object.
        if (!at_end()) { err = "trailing content"; return false; }

        // ---- presence of required fields ------------------------------------
        if (!has_type || !has_version || !has_argmax_class || !has_model_sha ||
            !has_frame_id || !has_confidence || !has_argmax_idx ||
            !has_class_count || !has_probabilities) {
            err = "missing required field";
            return false;
        }

        // ---- §二.5 validation ----------------------------------------------
        if (type != "result") { err = "type != result"; return false; }
        if (version != "12class-chain-v1") { err = "version != 12class-chain-v1"; return false; }

        if (!std::isfinite(class_count) || class_count != std::floor(class_count)) {
            err = "class_count not an integer"; return false;
        }
        if (class_count != 12.0) { err = "class_count != 12"; return false; }

        if (!std::isfinite(argmax_idx) || argmax_idx != std::floor(argmax_idx)) {
            err = "argmax_idx not an integer"; return false;
        }
        if (argmax_idx < 0.0 || argmax_idx > 11.0) { err = "argmax_idx out of range"; return false; }
        const int argmax = static_cast<int>(argmax_idx);

        // argmax_class must equal the frozen order label at argmax_idx.
        const cat::Contract contract = cat::target_12();
        if (argmax_class != cat::label(contract, argmax)) {
            err = "argmax_class mismatch";
            return false;
        }

        if (probabilities.size() != 12) { err = "probabilities width != 12"; return false; }
        double psum = 0.0;
        for (const double p : probabilities) {
            if (!std::isfinite(p)) { err = "non-finite probability"; return false; }
            if (p < 0.0 || p > 1.0) { err = "probability out of [0,1]"; return false; }
            psum += p;
        }
        if (std::fabs(psum - 1.0) > 1e-3) { err = "probabilities sum != 1"; return false; }

        if (!std::isfinite(confidence)) { err = "non-finite confidence"; return false; }
        if (std::fabs(confidence - probabilities[static_cast<std::size_t>(argmax)]) > 1e-4) {
            err = "confidence != probabilities[argmax_idx]";
            return false;
        }
        if (confidence < 0.0 || confidence > 1.0) { err = "confidence out of [0,1]"; return false; }

        if (model_sha.empty()) { err = "empty model_sha"; return false; }

        // Remaining numeric fields must be finite (snr_db may be null).
        const double finite_fields[] = { frame_id, timestamp_us, quality, e2e_us,
                                         preprocess_us, classify_us };
        for (const double v : finite_fields) {
            if (!std::isfinite(v)) { err = "non-finite numeric field"; return false; }
        }
        if (has_snr && !snr_is_null && !std::isfinite(snr_db)) {
            err = "non-finite snr_db"; return false;
        }

        // ---- populate rf::ResultFrame --------------------------------------
        frame = rf::ResultFrame{};
        frame.version = version;
        frame.class_count = static_cast<int>(class_count);
        frame.argmax_idx = argmax;
        frame.argmax_class = argmax_class;
        frame.confidence = static_cast<float>(confidence);
        frame.frame_id = static_cast<std::uint64_t>(frame_id);
        frame.timestamp_us = static_cast<std::uint64_t>(timestamp_us);
        frame.model_sha = model_sha;
        frame.mock = mock;
        frame.source = has_source ? source : std::string("");
        frame.e2e_us = e2e_us;
        frame.preprocess_us = preprocess_us;
        frame.classify_us = classify_us;
        frame.overflow = overflow;
        frame.dropped = dropped;
        frame.discontinuity = discontinuity;
        frame.short_frame = short_frame;
        frame.quality = quality;
        frame.snr_db = (has_snr && !snr_is_null) ? snr_db
                                                  : std::numeric_limits<double>::quiet_NaN();
        frame.probabilities.clear();
        frame.probabilities.reserve(probabilities.size());
        for (const double p : probabilities) frame.probabilities.push_back(static_cast<float>(p));
        return true;
    }

private:
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
        // current char is '{'
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
        // current char is '['
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
// input or contract violation.
inline ParseOutcome parse_result_frame_v2(const std::string& line) {
    ParseOutcome o;
    detail::JsonReader r(line);
    if (!r.parse_record(o.frame, o.error)) {
        o.ok = false;
        return o;
    }
    o.ok = true;
    return o;
}

}  // namespace ui
