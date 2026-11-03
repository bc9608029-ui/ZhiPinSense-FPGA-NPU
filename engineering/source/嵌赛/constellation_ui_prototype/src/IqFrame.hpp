// IqFrame.hpp — Qt-free core for the M29 RML23 offline constellation UI prototype.
//
// Everything in this header is pure C++17 (no Qt). It is the single source of
// truth for:
//   * the four-stage IQ semantics (RAW_RX / RECOVERED_PAYLOAD / MODEL_INPUT /
//     SYMBOL_SAMPLED),
//   * the IqFrame data structure,
//   * the future live-integration interface (class IqFrameSource),
//   * a self-contained SHA-256 (FIPS 180-4) used for fail-closed payload hashing,
//   * a strict flat-JSON parser for the metadata sidecar,
//   * the deterministic decimation / robust auto-scale / coordinate transform
//     math used by the renderer.
//
// Data-semantics red lines enforced downstream (see IqFrameLoader):
//   * never infer format from a file extension,
//   * reject unknown schema_version / dtype / layout,
//   * reject length mismatch, SHA mismatch, NaN/Inf,
//   * SYMBOL_SAMPLED is only shown when symbol_timing_valid is true.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

namespace cst {

// ---------------------------------------------------------------------------
// Stage semantics (do NOT relabel — the four views are distinct)
// ---------------------------------------------------------------------------
enum class Stage {
    RawRx,            // RAW_RX: raw samples straight from the SDR (noise/CFO/gain/oversampling)
    RecoveredPayload, // RECOVERED_PAYLOAD: after sync + CFO/SRO + gain recovery (may be oversampled)
    ModelInput,       // MODEL_INPUT: the actual [2,1024] tensor fed to the NPU
    SymbolSampled,    // SYMBOL_SAMPLED: classic per-symbol points, ONLY when symbol timing is valid
    Unknown
};

inline const char* stage_name(Stage s) {
    switch (s) {
        case Stage::RawRx:            return "RAW_RX";
        case Stage::RecoveredPayload: return "RECOVERED_PAYLOAD";
        case Stage::ModelInput:       return "MODEL_INPUT";
        case Stage::SymbolSampled:    return "SYMBOL_SAMPLED";
        default:                      return "UNKNOWN";
    }
}

inline Stage stage_from_name(const std::string& n) {
    if (n == "RAW_RX") return Stage::RawRx;
    if (n == "RECOVERED_PAYLOAD") return Stage::RecoveredPayload;
    if (n == "MODEL_INPUT") return Stage::ModelInput;
    if (n == "SYMBOL_SAMPLED") return Stage::SymbolSampled;
    return Stage::Unknown;
}

enum class DType { I16, F32 };

inline const char* dtype_name(DType d) {
    return d == DType::I16 ? "<i2" : "<f4";
}

enum class Layout { Planar, Interleaved };

inline const char* layout_name(Layout l) {
    return l == Layout::Planar ? "planar" : "interleaved";
}

// ---------------------------------------------------------------------------
// IqFrame
// ---------------------------------------------------------------------------
struct IqFrame {
    Stage stage = Stage::Unknown;
    DType dtype = DType::F32;
    Layout layout = Layout::Planar;
    std::uint64_t frame_id = 0;
    std::uint64_t complex_count = 0;
    std::uint64_t sample_rate_hz = 0;
    std::int64_t source_index = 0;
    std::string modulation;
    std::string predicted_class;
    std::string baseline_class;
    double confidence = 0.0;
    double cfo_hz = 0.0;
    double sro_ppm = 0.0;
    double gain_mag = 0.0;      // real RF gain magnitude; only meaningful when gain_valid
    double d2_rec_scale = 0.0;  // D2 recovery scalar (NOT an RF gain_mag measurement)

    // Metric validity. A metric MUST NOT be displayed as a real measurement
    // unless its *_valid flag is true; missing flags default to false (invalid /
    // unavailable) so "0" is never mistaken for "really measured 0".
    bool confidence_valid = false;
    bool recovery_metrics_valid = false;
    bool gain_valid = false;
    bool cfo_valid = false;
    bool sro_valid = false;
    std::string metric_provenance;   // e.g. "placeholder", "clean2b-d2-recovery", "real"

    bool symbol_timing_valid = false;
    std::string payload_sha256;   // 64 lowercase hex
    std::string iq_file;          // binary file name (no path separators)
    std::string source_path;      // absolute path the binary was loaded from
    std::vector<float> i;         // real part, length == complex_count
    std::vector<float> q;         // imag part, length == complex_count

    bool prediction_agreement() const {
        return !predicted_class.empty() && predicted_class == baseline_class;
    }
};

// ---------------------------------------------------------------------------
// Future live-integration interface (DEFINE ONLY — do not implement live).
// Only FileIqFrameSource is implemented in this phase; UnixSocket / SharedMemory
// sources remain future stubs documented in docs/future_live_integration.md.
// ---------------------------------------------------------------------------
class IqFrameSource {
public:
    virtual ~IqFrameSource() = default;
    // Pulls the next frame. Returns false at end-of-stream or on a hard error
    // (error is filled). A corrupted frame MUST stop playback, never auto-skip.
    virtual bool nextFrame(IqFrame& frame, std::string& error) = 0;
};

// ---------------------------------------------------------------------------
// Little-endian readers (explicit byte order, never host-order memcpy of ints)
// ---------------------------------------------------------------------------
inline std::int16_t read_le_i16(const unsigned char* p) {
    return static_cast<std::int16_t>(
        static_cast<std::uint16_t>(p[0]) | (static_cast<std::uint16_t>(p[1]) << 8));
}

inline float read_le_f32(const unsigned char* p) {
    const std::uint32_t u = static_cast<std::uint32_t>(p[0]) |
                            (static_cast<std::uint32_t>(p[1]) << 8) |
                            (static_cast<std::uint32_t>(p[2]) << 16) |
                            (static_cast<std::uint32_t>(p[3]) << 24);
    float f;
    std::memcpy(&f, &u, sizeof(f));   // bit-preserving, host-endianness-free
    return f;
}

inline bool is_hex64(const std::string& s) {
    if (s.size() != 64) return false;
    for (char c : s) {
        const bool ok = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                        (c >= 'A' && c <= 'F');
        if (!ok) return false;
    }
    return true;
}

inline std::string lowercase(std::string s) {
    for (char& c : s) {
        if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    }
    return s;
}

// ---------------------------------------------------------------------------
// SHA-256 (FIPS 180-4). Self-contained; verified against the standard test
// vectors and against the real fixture hashes in the unit tests.
// ---------------------------------------------------------------------------
namespace sha256_detail {

inline std::uint32_t rotr(std::uint32_t x, int n) {
    return (x >> n) | (x << (32 - n));
}

inline const std::uint32_t* k_table() {
    static const std::uint32_t K[64] = {
        0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
        0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
        0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
        0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
        0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
        0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
        0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
        0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
        0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
        0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
        0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
        0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
        0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
        0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
        0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
        0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};
    return K;
}

struct State {
    std::uint32_t h[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                          0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
    std::uint64_t bitlen = 0;
};

inline void compress(State& st, const unsigned char* p) {
    std::uint32_t w[64];
    for (int i = 0; i < 16; ++i) {
        w[i] = (static_cast<std::uint32_t>(p[i * 4]) << 24) |
               (static_cast<std::uint32_t>(p[i * 4 + 1]) << 16) |
               (static_cast<std::uint32_t>(p[i * 4 + 2]) << 8) |
               (static_cast<std::uint32_t>(p[i * 4 + 3]));
    }
    for (int i = 16; i < 64; ++i) {
        const std::uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        const std::uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    std::uint32_t a = st.h[0], b = st.h[1], c = st.h[2], d = st.h[3];
    std::uint32_t e = st.h[4], f = st.h[5], g = st.h[6], h = st.h[7];
    const std::uint32_t* K = k_table();
    for (int i = 0; i < 64; ++i) {
        const std::uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        const std::uint32_t ch = (e & f) ^ (~e & g);
        const std::uint32_t t1 = h + S1 + ch + K[i] + w[i];
        const std::uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        const std::uint32_t t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    st.h[0] += a; st.h[1] += b; st.h[2] += c; st.h[3] += d;
    st.h[4] += e; st.h[5] += f; st.h[6] += g; st.h[7] += h;
}

inline std::string hex_of_hash(const State& st) {
    static const char* hexd = "0123456789abcdef";
    std::string out;
    out.reserve(64);
    for (int i = 0; i < 8; ++i) {
        for (int j = 3; j >= 0; --j) {
            const std::uint8_t b = static_cast<std::uint8_t>((st.h[i] >> (j * 8)) & 0xffu);
            out.push_back(hexd[b >> 4]);
            out.push_back(hexd[b & 0x0f]);
        }
    }
    return out;
}

}  // namespace sha256_detail

inline std::string sha256_hex(const void* data, std::size_t len) {
    using namespace sha256_detail;
    State st;
    const unsigned char* p = static_cast<const unsigned char*>(data);
    std::size_t total = len;
    while (total >= 64) {
        compress(st, p);
        st.bitlen += 512;
        p += 64;
        total -= 64;
    }
    // Padding: 0x80, zeros, then 64-bit big-endian bit length.
    unsigned char last[128];
    std::size_t l = total;
    for (std::size_t i = 0; i < l; ++i) last[i] = p[i];
    last[l++] = 0x80;
    std::size_t pad_to = (l <= 56) ? 56 : 120;
    for (std::size_t i = l; i < pad_to; ++i) last[i] = 0;
    const std::uint64_t bits = static_cast<std::uint64_t>(len) * 8u;
    for (int i = 0; i < 8; ++i)
        last[pad_to + i] = static_cast<unsigned char>((bits >> (56 - i * 8)) & 0xffu);
    compress(st, last);
    if (pad_to == 120) compress(st, last + 64);
    return hex_of_hash(st);
}

// ---------------------------------------------------------------------------
// Flat JSON object parser (strict; for the metadata sidecar).
// Supports one top-level object of scalar values (string / number / true / false
// / null). Nested arrays/objects are rejected (the sidecar contract is flat).
// ---------------------------------------------------------------------------
struct JsonValue {
    enum Kind { Null, Bool, Number, String } kind = Null;
    bool b = false;
    double num = 0.0;
    std::string s;
};

using JsonObject = std::vector<std::pair<std::string, JsonValue>>;

namespace json_detail {
inline bool is_space(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

inline bool is_digit(char c) { return c >= '0' && c <= '9'; }

inline void skip_ws(const std::string& t, std::size_t& pos) {
    while (pos < t.size() && is_space(t[pos])) ++pos;
}

inline bool parse_string(const std::string& t, std::size_t& pos, std::string& out,
                         std::string& err) {
    if (pos >= t.size() || t[pos] != '"') {
        err = "expected string";
        return false;
    }
    ++pos;
    out.clear();
    while (pos < t.size()) {
        const char c = t[pos++];
        if (c == '"') return true;
        if (c == '\\') {
            if (pos >= t.size()) { err = "truncated escape"; return false; }
            const char e = t[pos++];
            switch (e) {
                case '"':  out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/':  out.push_back('/'); break;
                case 'b':  out.push_back('\b'); break;
                case 'f':  out.push_back('\f'); break;
                case 'n':  out.push_back('\n'); break;
                case 'r':  out.push_back('\r'); break;
                case 't':  out.push_back('\t'); break;
                case 'u': {
                    if (pos + 4 > t.size()) { err = "truncated \\u"; return false; }
                    unsigned v = 0;
                    for (int i = 0; i < 4; ++i) {
                        const char h = t[pos++];
                        v <<= 4;
                        if (h >= '0' && h <= '9') v |= static_cast<unsigned>(h - '0');
                        else if (h >= 'a' && h <= 'f') v |= static_cast<unsigned>(h - 'a' + 10);
                        else if (h >= 'A' && h <= 'F') v |= static_cast<unsigned>(h - 'A' + 10);
                        else { err = "bad \\u hex"; return false; }
                    }
                    // UTF-8 encode the code unit (BMP only; adequate for the sidecar).
                    if (v < 0x80) {
                        out.push_back(static_cast<char>(v));
                    } else if (v < 0x800) {
                        out.push_back(static_cast<char>(0xC0 | (v >> 6)));
                        out.push_back(static_cast<char>(0x80 | (v & 0x3F)));
                    } else {
                        out.push_back(static_cast<char>(0xE0 | (v >> 12)));
                        out.push_back(static_cast<char>(0x80 | ((v >> 6) & 0x3F)));
                        out.push_back(static_cast<char>(0x80 | (v & 0x3F)));
                    }
                    break;
                }
                default: err = std::string("bad escape \\") + e; return false;
            }
        } else if (static_cast<unsigned char>(c) < 0x20u) {
            err = "unescaped control char in string";
            return false;
        } else {
            out.push_back(c);
        }
    }
    err = "unterminated string";
    return false;
}

inline bool parse_value(const std::string& t, std::size_t& pos, JsonValue& out,
                        std::string& err) {
    skip_ws(t, pos);
    if (pos >= t.size()) { err = "missing value"; return false; }
    const char c = t[pos];
    if (c == '"') {
        out.kind = JsonValue::String;
        return parse_string(t, pos, out.s, err);
    }
    if (c == 't') {
        if (t.compare(pos, 4, "true") == 0) { out.kind = JsonValue::Bool; out.b = true; pos += 4; return true; }
        err = "bad literal";
        return false;
    }
    if (c == 'f') {
        if (t.compare(pos, 5, "false") == 0) { out.kind = JsonValue::Bool; out.b = false; pos += 5; return true; }
        err = "bad literal";
        return false;
    }
    if (c == 'n') {
        if (t.compare(pos, 4, "null") == 0) { out.kind = JsonValue::Null; pos += 4; return true; }
        err = "bad literal";
        return false;
    }
    if (c == '{' || c == '[') {
        err = "nested containers are not supported (flat sidecar contract)";
        return false;
    }
    if (c == '-' || is_digit(c)) {
        // number token
        std::size_t start = pos;
        if (t[pos] == '-') ++pos;
        if (pos >= t.size() || !is_digit(t[pos])) { err = "bad number"; return false; }
        while (pos < t.size() && is_digit(t[pos])) ++pos;
        if (pos < t.size() && t[pos] == '.') {
            ++pos;
            if (pos >= t.size() || !is_digit(t[pos])) { err = "bad number"; return false; }
            while (pos < t.size() && is_digit(t[pos])) ++pos;
        }
        if (pos < t.size() && (t[pos] == 'e' || t[pos] == 'E')) {
            ++pos;
            if (pos < t.size() && (t[pos] == '+' || t[pos] == '-')) ++pos;
            if (pos >= t.size() || !is_digit(t[pos])) { err = "bad number"; return false; }
            while (pos < t.size() && is_digit(t[pos])) ++pos;
        }
        const std::string tok = t.substr(start, pos - start);
        char* endp = nullptr;
        out.num = std::strtod(tok.c_str(), &endp);
        if (endp == tok.c_str()) { err = "bad number"; return false; }
        if (!std::isfinite(out.num)) { err = "non-finite number"; return false; }
        out.kind = JsonValue::Number;
        return true;
    }
    err = "unexpected character";
    return false;
}
}  // namespace json_detail

// Parses a single flat JSON object. Returns false and fills err on any malformed
// input. Keys are returned in document order; duplicates are allowed here and
// detected by the loader.
inline bool parse_json_object(const std::string& text, JsonObject& out,
                              std::string& err) {
    using namespace json_detail;
    JsonObject local;
    std::size_t pos = 0;
    skip_ws(text, pos);
    if (pos >= text.size() || text[pos] != '{') {
        err = "expected top-level object";
        return false;
    }
    ++pos;
    skip_ws(text, pos);
    if (pos < text.size() && text[pos] == '}') { ++pos; }  // empty object
    else {
        while (true) {
            std::string key;
            skip_ws(text, pos);
            if (!parse_string(text, pos, key, err)) return false;
            skip_ws(text, pos);
            if (pos >= text.size() || text[pos] != ':') {
                err = "expected ':'";
                return false;
            }
            ++pos;
            JsonValue v;
            if (!parse_value(text, pos, v, err)) return false;
            local.emplace_back(std::move(key), std::move(v));
            skip_ws(text, pos);
            if (pos >= text.size()) { err = "unterminated object"; return false; }
            if (text[pos] == ',') { ++pos; continue; }
            if (text[pos] == '}') { ++pos; break; }
            err = "expected ',' or '}'";
            return false;
        }
    }
    skip_ws(text, pos);
    if (pos != text.size()) {
        err = "trailing data after object";
        return false;
    }
    out = std::move(local);
    return true;
}

inline const JsonValue* find_field(const JsonObject& obj, const std::string& key) {
    for (const auto& kv : obj) {
        if (kv.first == key) return &kv.second;
    }
    return nullptr;
}

inline std::size_t count_field(const JsonObject& obj, const std::string& key) {
    std::size_t n = 0;
    for (const auto& kv : obj) if (kv.first == key) ++n;
    return n;
}

// ---------------------------------------------------------------------------
// Deterministic decimation + robust auto-scale + coordinate transform.
// All pure functions, unit-tested, and called from C++ (never QML JS).
// ---------------------------------------------------------------------------

// Evenly-spread, deterministic indices into [0, n). Exactly max_points indices
// when n > max_points (never per-frame random — no flicker). idx[0] == 0.
inline std::vector<std::size_t> decimate_indices(std::size_t n, std::size_t max_points) {
    std::vector<std::size_t> out;
    if (n == 0) return out;
    if (max_points == 0 || n <= max_points) {
        out.resize(n);
        for (std::size_t k = 0; k < n; ++k) out[k] = k;
        return out;
    }
    out.resize(max_points);
    for (std::size_t k = 0; k < max_points; ++k) {
        out[k] = (k * n) / max_points;   // strictly increasing, deterministic
    }
    return out;
}

// Robust symmetric auto-scale. Uses the 98th percentile of the combined |I|,|Q|
// magnitudes (so a few outliers never collapse the body), then adds a 10% margin.
// Returns the half-range r; the plot covers [-r, +r] on BOTH axes (origin
// centered, identical I/Q scale). out_of_range counts points outside [-r, r].
inline float auto_scale_range(const std::vector<float>& i, const std::vector<float>& q,
                              std::size_t& out_of_range) {
    out_of_range = 0;
    const std::size_t n = i.size();
    if (n == 0) return 1.0f;
    std::vector<float> mags;
    mags.reserve(n * 2);
    for (std::size_t k = 0; k < n; ++k) {
        mags.push_back(std::fabs(i[k]));
        mags.push_back(std::fabs(q[k]));
    }
    std::sort(mags.begin(), mags.end());
    const std::size_t qidx = static_cast<std::size_t>(0.98 * (mags.size() - 1));
    const float qval = mags[qidx];
    float r = qval * 1.10f;
    if (!(r > 0.0f) || !std::isfinite(r)) r = 1.0f;   // all-zero / degenerate frame
    for (std::size_t k = 0; k < n; ++k) {
        if (std::fabs(i[k]) > r || std::fabs(q[k]) > r) ++out_of_range;
    }
    return r;
}

// Map (i, q) inside the symmetric range [-r, +r] to unit coordinates in [0,1]^2,
// y increasing downward (screen convention). Out-of-range points are NOT silently
// clamped here; the renderer flags them and clamps only for drawing.
inline void transform_to_unit(const std::vector<float>& i, const std::vector<float>& q,
                              float r, std::vector<float>& ux, std::vector<float>& uy) {
    const std::size_t n = i.size();
    ux.resize(n);
    uy.resize(n);
    if (r <= 0.0f || !std::isfinite(r)) r = 1.0f;
    const float scale = 1.0f / (2.0f * r);
    for (std::size_t k = 0; k < n; ++k) {
        ux[k] = (i[k] + r) * scale;
        uy[k] = (r - q[k]) * scale;
    }
}

}  // namespace cst
