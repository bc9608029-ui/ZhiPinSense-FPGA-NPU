// IqFrameLoader.cpp — implementation of the offline fail-closed IQ frame loader.
#include "IqFrameLoader.hpp"

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace cst {
namespace fs = std::filesystem;

namespace {

// ---- small file helpers ------------------------------------------------------
bool read_file_bytes(const std::string& path, std::string& out, std::string& err) {
    std::ifstream f(path, std::ios::binary);
    if (!f) {
        err = "cannot open file: " + path;
        return false;
    }
    std::ostringstream ss;
    ss << f.rdbuf();
    if (!f.good() && !f.eof()) {
        err = "read error on file: " + path;
        return false;
    }
    out = ss.str();
    return true;
}

std::string dir_of(const std::string& path) {
    const std::size_t slash = path.find_last_of("/\\");
    if (slash == std::string::npos) return ".";
    return path.substr(0, slash);
}

bool is_unsafe_name(const std::string& name) {
    if (name.empty()) return true;
    if (name.find('/') != std::string::npos) return true;
    if (name.find('\\') != std::string::npos) return true;
    if (name.find("..") != std::string::npos) return true;
    return false;
}

// ---- typed field extraction (strict) -----------------------------------------
bool require_string(const JsonObject& obj, const std::string& key, std::string& out,
                    std::string& err) {
    const JsonValue* v = find_field(obj, key);
    if (!v) { err = "missing required field: " + key; return false; }
    if (count_field(obj, key) != 1) { err = "duplicate field: " + key; return false; }
    if (v->kind != JsonValue::String) { err = "field is not a string: " + key; return false; }
    out = v->s;
    return true;
}

bool require_number(const JsonObject& obj, const std::string& key, double& out,
                    std::string& err) {
    const JsonValue* v = find_field(obj, key);
    if (!v) { err = "missing required field: " + key; return false; }
    if (count_field(obj, key) != 1) { err = "duplicate field: " + key; return false; }
    if (v->kind != JsonValue::Number) { err = "field is not a number: " + key; return false; }
    out = v->num;
    return true;
}

bool optional_string(const JsonObject& obj, const std::string& key, std::string& out) {
    const JsonValue* v = find_field(obj, key);
    if (!v || v->kind != JsonValue::String) return false;
    if (count_field(obj, key) != 1) return false;
    out = v->s;
    return true;
}

bool optional_number(const JsonObject& obj, const std::string& key, double& out) {
    const JsonValue* v = find_field(obj, key);
    if (!v || v->kind != JsonValue::Number) return false;
    if (count_field(obj, key) != 1) return false;
    out = v->num;
    return true;
}

bool optional_bool(const JsonObject& obj, const std::string& key, bool& out) {
    const JsonValue* v = find_field(obj, key);
    if (!v || v->kind != JsonValue::Bool) return false;
    if (count_field(obj, key) != 1) return false;
    out = v->b;
    return true;
}

bool integral(double v) {
    return std::isfinite(v) && v == std::floor(v);
}

// ---- sample parsing (little-endian, fail-closed on NaN/Inf) ------------------
bool parse_samples(const std::string& bytes, const IqFrame& spec,
                   std::vector<float>& i, std::vector<float>& q, std::string& err) {
    const std::size_t n = static_cast<std::size_t>(spec.complex_count);
    i.assign(n, 0.0f);
    q.assign(n, 0.0f);
    const unsigned char* p = reinterpret_cast<const unsigned char*>(bytes.data());

    if (spec.dtype == DType::I16) {
        if (spec.layout == Layout::Interleaved) {
            for (std::size_t k = 0; k < n; ++k) {
                i[k] = static_cast<float>(read_le_i16(p + k * 4));
                q[k] = static_cast<float>(read_le_i16(p + k * 4 + 2));
            }
        } else {  // planar
            for (std::size_t k = 0; k < n; ++k) {
                i[k] = static_cast<float>(read_le_i16(p + k * 2));
                q[k] = static_cast<float>(read_le_i16(p + (n + k) * 2));
            }
        }
        return true;   // int16 has no NaN/Inf representation
    }

    // F32
    if (spec.layout == Layout::Interleaved) {
        for (std::size_t k = 0; k < n; ++k) {
            const float ri = read_le_f32(p + k * 8);
            const float rq = read_le_f32(p + k * 8 + 4);
            if (!std::isfinite(ri) || !std::isfinite(rq)) {
                err = "NaN/Inf sample at complex index " + std::to_string(k);
                return false;
            }
            i[k] = ri;
            q[k] = rq;
        }
    } else {  // planar
        for (std::size_t k = 0; k < n; ++k) {
            const float ri = read_le_f32(p + k * 4);
            const float rq = read_le_f32(p + (n + k) * 4);
            if (!std::isfinite(ri) || !std::isfinite(rq)) {
                err = "NaN/Inf sample at complex index " + std::to_string(k);
                return false;
            }
            i[k] = ri;
            q[k] = rq;
        }
    }
    return true;
}

}  // namespace

bool load_sidecar_frame(const std::string& sidecar_json_path, IqFrame& frame,
                        std::string& err) {
    frame = IqFrame{};

    std::string json_text;
    if (!read_file_bytes(sidecar_json_path, json_text, err)) return false;

    JsonObject obj;
    if (!parse_json_object(json_text, obj, err)) {
        err = "sidecar JSON: " + err;
        return false;
    }

    // schema_version (reject anything other than 1)
    double schema = 0;
    if (!require_number(obj, "schema_version", schema, err)) return false;
    if (!integral(schema) || static_cast<long long>(schema) != 1) {
        err = "unknown schema_version: " + std::to_string(schema) + " (only 1 is supported)";
        return false;
    }

    // stage (four-view semantics)
    std::string stage_str;
    if (!require_string(obj, "stage", stage_str, err)) return false;
    frame.stage = stage_from_name(stage_str);
    if (frame.stage == Stage::Unknown) {
        err = "unknown stage: " + stage_str;
        return false;
    }

    // dtype / layout (never inferred from extension)
    std::string dtype_str, layout_str;
    if (!require_string(obj, "dtype", dtype_str, err)) return false;
    if (!require_string(obj, "layout", layout_str, err)) return false;
    if (dtype_str == "<i2") {
        frame.dtype = DType::I16;
    } else if (dtype_str == "<f4") {
        frame.dtype = DType::F32;
    } else {
        err = "unknown dtype: " + dtype_str + " (supported: <i2, <f4)";
        return false;
    }
    if (layout_str == "planar") {
        frame.layout = Layout::Planar;
    } else if (layout_str == "interleaved") {
        frame.layout = Layout::Interleaved;
    } else {
        err = "unknown layout: " + layout_str + " (supported: planar, interleaved)";
        return false;
    }

    // complex_count (positive integer)
    double cc = 0;
    if (!require_number(obj, "complex_count", cc, err)) return false;
    if (!integral(cc) || cc <= 0) {
        err = "invalid complex_count: " + std::to_string(cc);
        return false;
    }
    frame.complex_count = static_cast<std::uint64_t>(cc);

    // payload_sha256 (64 lowercase hex)
    if (!require_string(obj, "payload_sha256", frame.payload_sha256, err)) return false;
    if (!is_hex64(frame.payload_sha256)) {
        err = "payload_sha256 is not 64 hex characters";
        return false;
    }
    frame.payload_sha256 = lowercase(frame.payload_sha256);

    // iq_file (must be a safe bare name — never infer format from extension)
    if (!require_string(obj, "iq_file", frame.iq_file, err)) return false;
    if (is_unsafe_name(frame.iq_file)) {
        err = "unsafe iq_file name: " + frame.iq_file;
        return false;
    }

    // optional metadata
    double dnum = 0;
    if (optional_number(obj, "frame_id", dnum) && integral(dnum) && dnum >= 0)
        frame.frame_id = static_cast<std::uint64_t>(dnum);
    if (optional_number(obj, "sample_rate_hz", dnum) && integral(dnum) && dnum >= 0)
        frame.sample_rate_hz = static_cast<std::uint64_t>(dnum);
    if (optional_number(obj, "source_index", dnum) && integral(dnum))
        frame.source_index = static_cast<std::int64_t>(dnum);
    optional_string(obj, "modulation", frame.modulation);
    optional_string(obj, "predicted_class", frame.predicted_class);
    optional_string(obj, "baseline_class", frame.baseline_class);
    if (optional_number(obj, "confidence", dnum)) {
        if (!std::isfinite(dnum) || dnum < 0.0 || dnum > 1.0) {
            err = "confidence out of [0,1] or non-finite";
            return false;
        }
        frame.confidence = dnum;
    }
    if (optional_number(obj, "cfo_hz", dnum)) {
        if (!std::isfinite(dnum)) { err = "cfo_hz non-finite"; return false; }
        frame.cfo_hz = dnum;
    }
    if (optional_number(obj, "sro_ppm", dnum)) {
        if (!std::isfinite(dnum)) { err = "sro_ppm non-finite"; return false; }
        frame.sro_ppm = dnum;
    }
    if (optional_number(obj, "gain_mag", dnum)) {
        if (!std::isfinite(dnum)) { err = "gain_mag non-finite"; return false; }
        frame.gain_mag = dnum;
    }
    if (optional_number(obj, "d2_rec_scale", dnum)) {
        if (!std::isfinite(dnum) || dnum < 0.0) { err = "d2_rec_scale non-finite or negative"; return false; }
        frame.d2_rec_scale = dnum;
    }
    // Validity flags + provenance. These are OPTIONAL with an explicit compat
    // strategy: a missing (or malformed) flag leaves it false, i.e. the metric
    // is treated as unavailable rather than trusted. "0" is therefore never
    // displayed as a real measurement of zero.
    optional_bool(obj, "confidence_valid", frame.confidence_valid);
    optional_bool(obj, "recovery_metrics_valid", frame.recovery_metrics_valid);
    optional_bool(obj, "gain_valid", frame.gain_valid);
    optional_bool(obj, "cfo_valid", frame.cfo_valid);
    optional_bool(obj, "sro_valid", frame.sro_valid);
    optional_string(obj, "metric_provenance", frame.metric_provenance);
    optional_bool(obj, "symbol_timing_valid", frame.symbol_timing_valid);

    // Red line: SYMBOL_SAMPLED must never be shown without valid symbol timing.
    if (frame.stage == Stage::SymbolSampled && !frame.symbol_timing_valid) {
        err = "SYMBOL_SAMPLED requires symbol_timing_valid=true";
        return false;
    }

    // Resolve and read the binary IQ file (next to the sidecar).
    const std::string bin_path =
        dir_of(sidecar_json_path) + "/" + frame.iq_file;
    frame.source_path = bin_path;

    std::string bytes;
    if (!read_file_bytes(bin_path, bytes, err)) return false;

    const std::size_t bytes_per_complex = (frame.dtype == DType::I16) ? 4u : 8u;
    const std::size_t expected = static_cast<std::size_t>(frame.complex_count) * bytes_per_complex;
    if (bytes.size() != expected) {
        err = "length mismatch: " + std::to_string(bytes.size()) +
              " bytes != expected " + std::to_string(expected) +
              " (complex_count=" + std::to_string(frame.complex_count) + ")";
        return false;
    }

    const std::string got_sha = sha256_hex(bytes.data(), bytes.size());
    if (got_sha != frame.payload_sha256) {
        err = "SHA mismatch: file " + got_sha + " != sidecar " + frame.payload_sha256;
        return false;
    }

    return parse_samples(bytes, frame, frame.i, frame.q, err);
}

std::vector<std::string> list_sidecars(const std::string& dir, std::string& err) {
    std::vector<std::string> out;
    err.clear();
    std::error_code ec;
    // Collect *.json entries (case-insensitive suffix).
    std::vector<std::pair<std::uint64_t, std::string>> scored;
    for (fs::directory_iterator it(dir, ec), end; !ec && it != end; it.increment(ec)) {
        if (!it->is_regular_file(ec)) continue;
        const std::string name = it->path().filename().string();
        std::string lower = lowercase(name);
        if (lower.size() < 5 || lower.compare(lower.size() - 5, 5, ".json") != 0) continue;

        // Peek the frame_id for stable ordering (a malformed sidecar is skipped
        // here; loading it later still fail-closes).
        std::uint64_t fid = 0;
        std::string jtext, perr;
        if (read_file_bytes(it->path().string(), jtext, perr)) {
            JsonObject obj;
            if (parse_json_object(jtext, obj, perr)) {
                double dnum = 0;
                if (optional_number(obj, "frame_id", dnum) && integral(dnum) && dnum >= 0)
                    fid = static_cast<std::uint64_t>(dnum);
            }
        }
        scored.emplace_back(fid, it->path().string());
    }
    std::sort(scored.begin(), scored.end(),
              [](const auto& a, const auto& b) {
                  if (a.first != b.first) return a.first < b.first;
                  return a.second < b.second;
              });
    out.reserve(scored.size());
    for (auto& s : scored) out.push_back(std::move(s.second));
    return out;
}

bool FileIqFrameSource::nextFrame(IqFrame& frame, std::string& error) {
    if (done_) {
        error = "end of file";
        return false;
    }
    done_ = true;
    if (!load_sidecar_frame(path_, frame, error)) return false;
    return true;
}

}  // namespace cst
