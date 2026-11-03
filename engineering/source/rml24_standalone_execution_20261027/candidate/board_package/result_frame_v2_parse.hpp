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
//   type == "result", version in {"12class-chain-v1", "12class-chain-v2"},
//   class_count == 12, argmax_idx in [0,11],
//   argmax_class == cat::label(target_12(), argmax_idx)
//   (frozen order OOK,4ASK,AM-DSB,WBFM,2FSK,GFSK,BPSK,QPSK,8PSK,16QAM,64QAM,OFDM),
//   probabilities length 12 with every entry finite in [0,1] and |sum-1| <= 1e-3,
//   confidence == probabilities[argmax_idx] (tol 1e-4, adapts to %.6f rounding),
//   model_sha non-empty.  All numeric values must be finite (snr_db may be null).
//   Schema "12class-chain-v2" (UI v3 M4) additionally carries presence_state,
//   level_mode, model_scale, rf_gain_db and a nested `measurements` object; those
//   are REQUIRED for v2 and parsed into rf::ResultFrame's v3 extension fields.
//   "12class-chain-v1" records remain accepted unchanged (backward compatible).
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

// Control state event (task 39e5 Task E, 方案 A):
//   {"type":"state","version":"12class-chain-v2","command_id":N,
//    "work_mode":"FIXED","run_state":"STOPPED","presence_state":"...","timestamp_us":N}
// Distinct from a classification result so the UI can show mode / run state even
// while no classification frames flow (e.g. STOPPED).  The UI must apply it
// WITHOUT touching the last valid classification (argmax / distribution).
struct StateEvent {
    bool ok = false;
    std::string error;       // non-empty reason when !ok
    std::string version;     // chain schema ("rml23-chain-v2" / "12class-chain-v2")
    std::string work_mode;   // FIXED / AUTO_LOCK / BAND_SCAN
    std::string run_state;   // RUNNING / STOPPED
    std::string presence_state;
    std::string model_sha;   // producer identity (empty for the legacy 12-class chain)
    std::uint64_t command_id = 0;
    std::uint64_t timestamp_us = 0;
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

        // ---- UI v3 (schema "12class-chain-v2") extension fields ----
        std::string presence_state, level_mode, work_mode, run_state;
        double model_scale = 1.0, rf_gain_db = 0.0;
        sdr::FrameMeasurements measurements;

        bool has_type = false, has_version = false, has_argmax_class = false;
        bool has_model_sha = false, has_source = false;
        bool has_frame_id = false, has_confidence = false;
        bool has_snr = false, has_argmax_idx = false;
        bool has_class_count = false, has_probabilities = false;
        bool snr_is_null = false;
        bool has_presence_state = false, has_level_mode = false;
        bool has_model_scale = false, has_rf_gain_db = false;
        bool has_work_mode = false, has_run_state = false;
        bool has_measurements = false, measurements_non_null = false;

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
            } else if (key == "presence_state") {
                has_presence_state = true;
                if (peek() != '"' || !parse_string(presence_state)) { err = "presence_state not a string"; return false; }
            } else if (key == "level_mode") {
                has_level_mode = true;
                if (peek() != '"' || !parse_string(level_mode)) { err = "level_mode not a string"; return false; }
            } else if (key == "model_scale") {
                has_model_scale = true;
                if (!parse_number(model_scale)) { err = "bad model_scale"; return false; }
            } else if (key == "rf_gain_db") {
                has_rf_gain_db = true;
                if (!parse_number(rf_gain_db)) { err = "bad rf_gain_db"; return false; }
            } else if (key == "work_mode") {
                has_work_mode = true;
                if (peek() != '"' || !parse_string(work_mode)) { err = "work_mode not a string"; return false; }
            } else if (key == "run_state") {
                has_run_state = true;
                if (peek() != '"' || !parse_string(run_state)) { err = "run_state not a string"; return false; }
            } else if (key == "measurements") {
                has_measurements = true;
                skip_ws();
                if (peek() == 'n') {
                    if (!parse_null()) { err = "bad null"; return false; }
                } else {
                    if (!parse_measurements(measurements)) { err = "bad measurements"; return false; }
                    measurements_non_null = true;
                }
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
        const bool is_v1 = (version == "12class-chain-v1");
        const bool is_v2 = (version == "12class-chain-v2");
        if (!is_v1 && !is_v2) { err = "version not 12class-chain-v1/v2"; return false; }

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

        // ---- UI v3 (v2) extension validation -------------------------------
        if (is_v2) {
            if (!has_presence_state || !has_level_mode || !has_model_scale ||
                !has_rf_gain_db || !has_work_mode || !has_run_state ||
                !has_measurements) {
                err = "missing v2 extension field"; return false;
            }
            if (!std::isfinite(model_scale)) { err = "non-finite model_scale"; return false; }
            if (!std::isfinite(rf_gain_db)) { err = "non-finite rf_gain_db"; return false; }
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
        // ---- UI v3 (v2) extension fields ----
        frame.has_measurements = measurements_non_null;
        frame.measurements = measurements;
        frame.presence_state = presence_state;
        frame.level_mode = level_mode;
        frame.model_scale = model_scale;
        frame.rf_gain_db = rf_gain_db;
        frame.work_mode = work_mode;
        frame.run_state = run_state;
        return true;
    }

    // Parse + validate the RML23 23-class result record (M29 Phase F5, schema
    // "rml23-chain-v2").  Mirrors parse_record() but enforces the 23-class
    // contract and the RML23 deployment fields (model_mode, merged_23_top1,
    // raw_24_top1, deployment_mode, expert flags).  See result_frame_rml23_parse.hpp
    // for the full contract.
    bool parse_record_rml23(rf::ResultFrame& frame, std::string& err) {
        skip_ws();
        if (peek() != '{') { err = "expected '{'"; return false; }
        ++i_;

        std::string type, version, argmax_class, model_sha, source;
        std::string model_mode, deployment_mode, expert_result;
        double frame_id = 0, timestamp_us = 0, confidence = 0, quality = 0;
        double e2e_us = 0, preprocess_us = 0, classify_us = 0, snr_db = 0;
        double argmax_idx = 0, class_count = 0;
        double merged_23_top1 = 0, raw_24_top1 = 0;
        std::vector<double> probabilities;
        std::vector<double> iq_i16_interleaved;
        double iq_units_per_count = 0.0;
        bool mock = false, overflow = false, dropped = false;
        bool discontinuity = false, short_frame = false, expert_enabled = false;
        bool iq_valid = false;

        std::string presence_state, level_mode, work_mode, run_state;
        double model_scale = 1.0, rf_gain_db = 0.0;
        sdr::FrameMeasurements measurements;

        bool has_type = false, has_version = false, has_argmax_class = false;
        bool has_model_sha = false, has_source = false;
        bool has_frame_id = false, has_confidence = false;
        bool has_snr = false, has_argmax_idx = false;
        bool has_class_count = false, has_probabilities = false;
        bool snr_is_null = false;
        bool has_model_mode = false, has_merged_23_top1 = false;
        bool has_raw_24_top1 = false, has_deployment_mode = false;
        bool has_expert_enabled = false, has_expert_result = false;
        bool has_presence_state = false, has_level_mode = false;
        bool has_model_scale = false, has_rf_gain_db = false;
        bool has_work_mode = false, has_run_state = false;
        bool has_measurements = false, measurements_non_null = false;
        bool has_iq_valid = false, has_iq_array = false, has_iq_scale = false;

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
            } else if (key == "model_mode") {
                has_model_mode = true;
                if (peek() != '"' || !parse_string(model_mode)) { err = "model_mode not a string"; return false; }
            } else if (key == "argmax_class") {
                has_argmax_class = true;
                if (peek() != '"' || !parse_string(argmax_class)) { err = "argmax_class not a string"; return false; }
            } else if (key == "model_sha") {
                has_model_sha = true;
                if (peek() != '"' || !parse_string(model_sha)) { err = "model_sha not a string"; return false; }
            } else if (key == "source") {
                has_source = true;
                if (peek() != '"' || !parse_string(source)) { err = "source not a string"; return false; }
            } else if (key == "deployment_mode") {
                has_deployment_mode = true;
                if (peek() != '"' || !parse_string(deployment_mode)) { err = "deployment_mode not a string"; return false; }
            } else if (key == "expert_result") {
                has_expert_result = true;
                if (peek() != '"' || !parse_string(expert_result)) { err = "expert_result not a string"; return false; }
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
            } else if (key == "merged_23_top1") {
                has_merged_23_top1 = true;
                if (!parse_number(merged_23_top1)) { err = "bad merged_23_top1"; return false; }
            } else if (key == "raw_24_top1") {
                has_raw_24_top1 = true;
                if (!parse_number(raw_24_top1)) { err = "bad raw_24_top1"; return false; }
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
            } else if (key == "expert_enabled") {
                has_expert_enabled = true;
                if (!parse_bool(expert_enabled)) { err = "bad expert_enabled"; return false; }
            } else if (key == "iq_valid") {
                has_iq_valid = true;
                if (!parse_bool(iq_valid)) { err = "bad iq_valid"; return false; }
            } else if (key == "iq_i16_interleaved") {
                has_iq_array = true;
                if (peek() == 'n') {
                    if (!parse_null()) { err = "bad iq array null"; return false; }
                } else if (!parse_number_array(iq_i16_interleaved)) {
                    err = "bad iq_i16_interleaved"; return false;
                }
            } else if (key == "iq_units_per_count") {
                has_iq_scale = true;
                if (peek() == 'n') {
                    if (!parse_null()) { err = "bad iq scale null"; return false; }
                } else if (!parse_number(iq_units_per_count)) {
                    err = "bad iq_units_per_count"; return false;
                }
            } else if (key == "presence_state") {
                has_presence_state = true;
                if (peek() != '"' || !parse_string(presence_state)) { err = "presence_state not a string"; return false; }
            } else if (key == "level_mode") {
                has_level_mode = true;
                if (peek() != '"' || !parse_string(level_mode)) { err = "level_mode not a string"; return false; }
            } else if (key == "model_scale") {
                has_model_scale = true;
                if (!parse_number(model_scale)) { err = "bad model_scale"; return false; }
            } else if (key == "rf_gain_db") {
                has_rf_gain_db = true;
                if (!parse_number(rf_gain_db)) { err = "bad rf_gain_db"; return false; }
            } else if (key == "work_mode") {
                has_work_mode = true;
                if (peek() != '"' || !parse_string(work_mode)) { err = "work_mode not a string"; return false; }
            } else if (key == "run_state") {
                has_run_state = true;
                if (peek() != '"' || !parse_string(run_state)) { err = "run_state not a string"; return false; }
            } else if (key == "measurements") {
                has_measurements = true;
                skip_ws();
                if (peek() == 'n') {
                    if (!parse_null()) { err = "bad null"; return false; }
                } else {
                    if (!parse_measurements(measurements)) { err = "bad measurements"; return false; }
                    measurements_non_null = true;
                }
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

        // ---- presence of required fields ------------------------------------
        if (!has_type || !has_version || !has_argmax_class || !has_model_sha ||
            !has_frame_id || !has_confidence || !has_argmax_idx ||
            !has_class_count || !has_probabilities ||
            !has_model_mode || !has_merged_23_top1 || !has_raw_24_top1 ||
            !has_deployment_mode || !has_expert_enabled || !has_expert_result) {
            err = "missing required field";
            return false;
        }

        // ---- RML23/RML24 contract validation -------------------------------
        if (type != "result") { err = "type != result"; return false; }
        const bool is_rml23 = version == "rml23-chain-v2";
        const bool is_rml24 = version == "rml24-final-chain-v1";
        if (!is_rml23 && !is_rml24) { err = "unsupported RML schema"; return false; }
        if (is_rml23 && model_mode != "RML23-AMSSB-MERGED") { err = "model_mode mismatch"; return false; }
        if (is_rml24 && model_mode != "RML24-BF16-RAW") { err = "model_mode mismatch"; return false; }

        if (!std::isfinite(class_count) || class_count != std::floor(class_count)) {
            err = "class_count not an integer"; return false;
        }
        const double expected_classes = is_rml24 ? 24.0 : 23.0;
        if (class_count != expected_classes) { err = "class_count mismatch"; return false; }

        if (!std::isfinite(argmax_idx) || argmax_idx != std::floor(argmax_idx)) {
            err = "argmax_idx not an integer"; return false;
        }
        if (argmax_idx < 0.0 || argmax_idx >= expected_classes) { err = "argmax_idx out of range"; return false; }
        const int argmax = static_cast<int>(argmax_idx);

        const cat::Contract contract = is_rml24 ? cat::target_24() : cat::target_23();
        if (argmax_class != cat::label(contract, argmax)) {
            err = "argmax_class mismatch";
            return false;
        }

        if (!std::isfinite(merged_23_top1) || merged_23_top1 != std::floor(merged_23_top1)) {
            err = "merged_23_top1 not an integer"; return false;
        }
        if (is_rml23 && merged_23_top1 != argmax_idx) { err = "merged_23_top1 != argmax_idx"; return false; }
        if (is_rml24 && merged_23_top1 != -1.0) { err = "RML24 merged_23_top1 != -1"; return false; }

        if (!std::isfinite(raw_24_top1) || raw_24_top1 != std::floor(raw_24_top1)) {
            err = "raw_24_top1 not an integer"; return false;
        }
        if (raw_24_top1 < 0.0 || raw_24_top1 > 23.0) { err = "raw_24_top1 out of range"; return false; }
        if (is_rml24 && raw_24_top1 != argmax_idx) { err = "RML24 raw_24_top1 != argmax_idx"; return false; }

        if (is_rml23 && deployment_mode != "AMSSB_MERGED") { err = "deployment_mode mismatch"; return false; }
        if (is_rml24 && deployment_mode != "RAW24_UNMERGED") { err = "deployment_mode mismatch"; return false; }
        if (expert_enabled) { err = "expert_enabled must be false"; return false; }
        if (expert_result != "NOT_RUN") { err = "expert_result != NOT_RUN"; return false; }

        if (is_rml24) {
            if (!has_iq_valid || !has_iq_array || !has_iq_scale) {
                err = "missing RML24 IQ display field"; return false;
            }
            if (iq_valid) {
                if (iq_i16_interleaved.size() != 512) {
                    err = "IQ display width mismatch"; return false;
                }
                if (!std::isfinite(iq_units_per_count) || iq_units_per_count <= 0.0) {
                    err = "invalid IQ display scale"; return false;
                }
                for (const double v : iq_i16_interleaved) {
                    if (!std::isfinite(v) || v != std::floor(v) || v < -30000.0 || v > 30000.0) {
                        err = "invalid IQ display sample"; return false;
                    }
                }
            } else if (!iq_i16_interleaved.empty() || iq_units_per_count != 0.0) {
                err = "invalid IQ display null state"; return false;
            }
        }

        if (probabilities.size() != static_cast<std::size_t>(expected_classes)) {
            err = "probabilities width mismatch"; return false;
        }
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

        const double finite_fields[] = { frame_id, timestamp_us, quality, e2e_us,
                                         preprocess_us, classify_us };
        for (const double v : finite_fields) {
            if (!std::isfinite(v)) { err = "non-finite numeric field"; return false; }
        }
        if (has_snr && !snr_is_null && !std::isfinite(snr_db)) {
            err = "non-finite snr_db"; return false;
        }

        // Runtime extension fields are REQUIRED (always emitted by the RML23 line).
        if (!has_presence_state || !has_level_mode || !has_model_scale ||
            !has_rf_gain_db || !has_work_mode || !has_run_state ||
            !has_measurements) {
            err = "missing RML23 runtime field"; return false;
        }
        if (!std::isfinite(model_scale)) { err = "non-finite model_scale"; return false; }
        if (!std::isfinite(rf_gain_db)) { err = "non-finite rf_gain_db"; return false; }

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
        frame.has_measurements = measurements_non_null;
        frame.measurements = measurements;
        frame.presence_state = presence_state;
        frame.level_mode = level_mode;
        frame.model_scale = model_scale;
        frame.rf_gain_db = rf_gain_db;
        frame.work_mode = work_mode;
        frame.run_state = run_state;
        // ---- RML23 deployment fields ----
        frame.raw_24_top1 = static_cast<int>(raw_24_top1);
        frame.merged_23_top1 = static_cast<int>(merged_23_top1);
        frame.deployment_mode = deployment_mode;
        frame.expert_enabled = expert_enabled;
        frame.expert_result = expert_result;
        frame.iq_display_valid = is_rml24 && iq_valid;
        frame.iq_units_per_count = frame.iq_display_valid ? iq_units_per_count : 0.0;
        frame.iq_i16_interleaved.clear();
        if (frame.iq_display_valid) {
            frame.iq_i16_interleaved.reserve(iq_i16_interleaved.size());
            for (const double v : iq_i16_interleaved)
                frame.iq_i16_interleaved.push_back(static_cast<std::int16_t>(v));
        }
        return true;
    }

    // Parse the nested `measurements` object (UI v3 M4).  All 12 serialized
    // fields are numbers; unknown keys are skipped (forward-compatible).  Every
    // consumed number must be finite; occupied_bins must be an integer.
    // fix10class24-waterfall1: the optional display-spectrum fields are consumed
    // here fail-closed -- a malformed/mis-sized/out-of-range spectrum array, a
    // non-integer metadata count, or spectrum_valid=true without the full metadata
    // set all reject the frame.  Records that carry no spectrum keys parse as
    // spectrum_valid=false (legacy compatibility, waterfall shows no heatmap).
    bool parse_measurements(sdr::FrameMeasurements& m) {
        bool saw_spectrum_valid = false, saw_spectrum_array = false;
        bool saw_spectrum_fft = false, saw_spectrum_bins = false;
        bool saw_spectrum_fs = false, saw_spectrum_center = false;

        skip_ws();
        if (peek() != '{') return false;
        ++i_;
        skip_ws();
        if (peek() == '}') { ++i_; return false; }   // empty object is malformed
        while (true) {
            std::string key;
            if (!parse_string(key)) return false;
            skip_ws();
            if (peek() != ':') return false;
            ++i_;
            skip_ws();
            if (key == "occupied_bins") {
                double v;
                if (!parse_number(v) || !std::isfinite(v) || v != std::floor(v)) return false;
                m.occupied_bins = static_cast<int>(v);
            } else if (key == "rms_counts" || key == "peak_counts" || key == "papr_db" ||
                       key == "clip_ratio" || key == "power_dbfs" || key == "noise_floor_dbfs" ||
                       key == "psd_peak_prominence_db" || key == "snr_est_db" ||
                       key == "spectral_centroid_hz" || key == "occupied_bw_hz" ||
                       key == "model_rms") {
                double v;
                if (!parse_number(v) || !std::isfinite(v)) return false;
                if (key == "rms_counts") m.rms_counts = v;
                else if (key == "peak_counts") m.peak_counts = v;
                else if (key == "papr_db") m.papr_db = v;
                else if (key == "clip_ratio") m.clip_ratio = v;
                else if (key == "power_dbfs") m.power_dbfs = v;
                else if (key == "noise_floor_dbfs") m.noise_floor_dbfs = v;
                else if (key == "psd_peak_prominence_db") m.psd_peak_prominence_db = v;
                else if (key == "snr_est_db") m.snr_est_db = v;
                else if (key == "spectral_centroid_hz") m.spectral_centroid_hz = v;
                else if (key == "occupied_bw_hz") m.occupied_bw_hz = v;
                else m.model_rms = v;
            } else if (key == "spectrum_valid") {
                if (!parse_bool(m.spectrum_valid)) return false;
                saw_spectrum_valid = true;
            } else if (key == "spectrum_fft_length") {
                double v;
                if (!parse_number(v) || !std::isfinite(v) || v != std::floor(v)) return false;
                m.spectrum_fft_length = static_cast<int>(v);
                saw_spectrum_fft = true;
            } else if (key == "spectrum_bin_count") {
                double v;
                if (!parse_number(v) || !std::isfinite(v) || v != std::floor(v)) return false;
                m.spectrum_bin_count = static_cast<int>(v);
                saw_spectrum_bins = true;
            } else if (key == "spectrum_sample_rate_hz") {
                double v;
                if (!parse_number(v) || !std::isfinite(v)) return false;
                m.spectrum_sample_rate_hz = v;
                saw_spectrum_fs = true;
            } else if (key == "spectrum_center_hz") {
                double v;
                if (!parse_number(v) || !std::isfinite(v)) return false;
                m.spectrum_center_hz = v;
                saw_spectrum_center = true;
            } else if (key == "spectrum_dbfs_x4") {
                std::vector<double> arr;
                if (!parse_number_array(arr)) return false;
                if (arr.size() != 256) return false;
                for (std::size_t b = 0; b < arr.size(); ++b) {
                    const double v = arr[b];
                    if (!std::isfinite(v) || v != std::floor(v) || v < -480.0 || v > 0.0)
                        return false;
                    m.spectrum_dbfs_x4[b] = static_cast<int>(v);
                }
                saw_spectrum_array = true;
            } else {
                if (!skip_value()) return false;
            }
            skip_ws();
            if (peek() == '}') { ++i_; break; }
            if (peek() != ',') return false;
            ++i_;
            skip_ws();
        }

        // Fail-closed spectrum metadata: a valid spectrum MUST carry the full,
        // self-consistent metadata set.  A valid=false record may omit the array.
        if (saw_spectrum_valid && m.spectrum_valid) {
            if (!saw_spectrum_array || !saw_spectrum_fft || !saw_spectrum_bins ||
                !saw_spectrum_fs || !saw_spectrum_center)
                return false;
            if (m.spectrum_fft_length != 1024) return false;
            if (m.spectrum_bin_count != 256) return false;
            if (!(m.spectrum_sample_rate_hz > 0.0)) return false;
        }
        return true;
    }

    // Parse the control state event (task 39e5 Task E, 方案 A).  Enforces the exact
    // schema: type=="state", version in {"12class-chain-v2","rml23-chain-v2"},
    // work_mode in the frozen token set, run_state in {RUNNING,STOPPED}, and
    // non-negative integer command_id / timestamp_us.  Unknown keys (e.g. model_sha
    // from the RML23 heartbeat) are skipped when absent / forward-compatible.
    bool parse_state_event(StateEvent& ev, std::string& err) {
        skip_ws();
        if (peek() != '{') { err = "expected '{'"; return false; }
        ++i_;

        std::string type, version, work_mode, run_state, presence_state, model_sha;
        double command_id = 0, timestamp_us = 0;
        bool has_type = false, has_version = false, has_command_id = false;
        bool has_work_mode = false, has_run_state = false, has_presence_state = false;
        bool has_timestamp = false;

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
            } else if (key == "command_id") {
                has_command_id = true;
                if (!parse_number(command_id)) { err = "bad command_id"; return false; }
            } else if (key == "work_mode") {
                has_work_mode = true;
                if (peek() != '"' || !parse_string(work_mode)) { err = "work_mode not a string"; return false; }
            } else if (key == "run_state") {
                has_run_state = true;
                if (peek() != '"' || !parse_string(run_state)) { err = "run_state not a string"; return false; }
            } else if (key == "presence_state") {
                has_presence_state = true;
                if (peek() != '"' || !parse_string(presence_state)) { err = "presence_state not a string"; return false; }
            } else if (key == "timestamp_us") {
                has_timestamp = true;
                if (!parse_number(timestamp_us)) { err = "bad timestamp_us"; return false; }
            } else if (key == "model_sha") {
                // Optional producer identity: present on RML23 heartbeats, absent on
                // the legacy 12-class chain (where model_sha stays "").
                if (peek() != '"' || !parse_string(model_sha)) { err = "model_sha not a string"; return false; }
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

        if (!has_type || !has_version || !has_command_id || !has_work_mode ||
            !has_run_state || !has_presence_state || !has_timestamp) {
            err = "missing required field";
            return false;
        }
        if (type != "state") { err = "type != state"; return false; }
        if (version != "12class-chain-v2" && version != "rml23-chain-v2" && version != "rml24-standalone-state-v1") {
            err = "version not a known chain schema (12class-chain-v2|rml23-chain-v2)";
            return false;
        }

        if (!std::isfinite(command_id) || command_id != std::floor(command_id) || command_id < 0.0) {
            err = "command_id not a non-negative integer"; return false;
        }
        if (!std::isfinite(timestamp_us) || timestamp_us != std::floor(timestamp_us) || timestamp_us < 0.0) {
            err = "timestamp_us not a non-negative integer"; return false;
        }
        if (work_mode != "FIXED" && work_mode != "AUTO_LOCK" && work_mode != "BAND_SCAN") {
            err = "unknown work_mode"; return false;
        }
        if (run_state != "RUNNING" && run_state != "STOPPED") {
            err = "unknown run_state"; return false;
        }

        ev.ok = true;
        ev.version = version;
        ev.work_mode = work_mode;
        ev.run_state = run_state;
        ev.presence_state = presence_state;
        ev.model_sha = model_sha;
        ev.command_id = static_cast<std::uint64_t>(command_id);
        ev.timestamp_us = static_cast<std::uint64_t>(timestamp_us);
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
// input or contract violation.  Accepts both "12class-chain-v1" and
// "12class-chain-v2" records (v2 additionally populates the UI-v3 extension
// fields; v1 records leave them at their defaults).
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

// Explicit UI-v3 alias.  Delegates to the same parser (which selects by the
// record's own `version` field), kept separate so callers/tests can name the v3
// contract directly without implying v1 records are rejected.
inline ParseOutcome parse_result_frame_v3(const std::string& line) {
    return parse_result_frame_v2(line);
}

// Parse the control state event (task 39e5 Task E, 方案 A).  Never throws; returns
// ok=false + error on any malformed input or schema violation.  Returns
// ok=true (with empty error) only for a well-formed state event.
inline StateEvent parse_state_frame(const std::string& line) {
    StateEvent ev;
    detail::JsonReader r(line);
    std::string err;
    if (!r.parse_state_event(ev, err)) {
        ev.ok = false;
        ev.error = err;
        return ev;
    }
    return ev;   // ok already set true by parse_state_event
}

}  // namespace ui
