#pragma once

// tcp_control_client.hpp -- fix10prep2 board-side AF_INET control channel.
//
// The PC controls the TX SDR and the board controls the RX SDR; the two ends exchange
// ONLY control messages + sample identity + SHA over this TCP link -- never real-time
// IQ (which travels over the 50-ohm coax as RF).  This is the first AF_INET socket in
// the tree: the existing unix_socket_server.hpp / unix_socket_sink.hpp are AF_UNIX
// result-plane links, while this is a length-prefixed JSON control channel.
//
// Wire format (frozen by the fix10prep2 task book §7):
//   [uint32 big-endian byte length][UTF-8 JSON payload]
//   * the length counts the JSON payload bytes only (not the 4-byte prefix);
//   * a length > kMaxMessageBytes is refused fail-closed (connection dropped);
//   * every message carries protocol_version / session_id / run_nonce /
//     manifest_sha256; the protocol layer (iq_pc_tx_board_rx_transfer_fix10.hpp)
//     validates the exact field set per type and enforces the strict state machine.
//
// This header is POSIX-only, iCraft-free and libiio-free: it compiles identically on
// the host (WSL g++ -- the host tests drive a real 127.0.0.1 loopback) and the board
// (Linux, with a real PC peer).  It carries a minimal JSON value + parser + serializer
// so the board can parse/emit the control messages without a third-party JSON library.

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
#endif

namespace iqpctbrx {

// ---------------------------------------------------------------------------
// Frozen wire-protocol constants (must match host_tools/fix10_tx_protocol.py).
// ---------------------------------------------------------------------------
constexpr int kProtocolVersion = 1;
constexpr std::uint16_t kDefaultPort = 39010;
constexpr std::size_t kMaxMessageBytes = 1u << 20;   // 1 MiB hard limit
constexpr int kDefaultConnectTimeoutMs = 2000;       // all timeouts <= 2 s (task book §7)
constexpr int kDefaultMessageTimeoutMs = 2000;
constexpr int kWatchdogTimeoutMs = 2000;             // independent PC watchdog <= 2 s

// ---------------------------------------------------------------------------
// Minimal JSON value (parse + serialize).  Strict: malformed input is rejected;
// the protocol layer additionally rejects unknown fields (fail-closed).
// ---------------------------------------------------------------------------
struct Json {
    enum class Kind { Null, Bool, Number, String, Array, Object };

    Kind kind = Kind::Null;
    bool boolean = false;
    double number = 0.0;
    std::string string;
    std::vector<Json> array;
    std::vector<std::pair<std::string, Json>> object;   // insertion-ordered

    static Json null() { return Json{}; }
    static Json make_boolean(bool b) { Json j; j.kind = Kind::Bool; j.boolean = b; return j; }
    static Json make_number(double n) { Json j; j.kind = Kind::Number; j.number = n; return j; }
    static Json make_string(std::string s) { Json j; j.kind = Kind::String; j.string = std::move(s); return j; }
    static Json make_array(std::vector<Json> a) { Json j; j.kind = Kind::Array; j.array = std::move(a); return j; }
    static Json make_object(std::vector<std::pair<std::string, Json>> o) {
        Json j; j.kind = Kind::Object; j.object = std::move(o); return j;
    }

    bool is_null() const { return kind == Kind::Null; }
    bool is_bool() const { return kind == Kind::Bool; }
    bool is_number() const { return kind == Kind::Number; }
    bool is_string() const { return kind == Kind::String; }
    bool is_array() const { return kind == Kind::Array; }
    bool is_object() const { return kind == Kind::Object; }

    // Lookup a top-level object member; nullptr when absent or not an object.
    const Json* get(const std::string& key) const {
        if (!is_object()) return nullptr;
        for (const auto& kv : object)
            if (kv.first == key) return &kv.second;
        return nullptr;
    }
    bool has(const std::string& key) const { return get(key) != nullptr; }

    // Typed accessors (used by the protocol layer after a kind check).
    double as_number() const { return is_number() ? number : 0.0; }
    bool as_bool() const { return is_bool() && boolean; }
    const std::string& as_string() const {
        static const std::string empty;
        return is_string() ? string : empty;
    }
    // Integer fields are JSON numbers; a non-integral value is still accepted here
    // (the protocol layer validates integrality where it matters, e.g. source_index).
    std::int64_t as_int() const {
        if (!is_number()) return 0;
        return static_cast<std::int64_t>(std::llround(number));
    }
};

struct JsonParseResult {
    bool ok = false;
    Json value;
    std::string error;
};

namespace detail_json {

class Parser {
public:
    explicit Parser(const std::string& s) : s_(s) {}

    JsonParseResult parse() {
        JsonParseResult r;
        skip_ws();
        if (!parse_value(r.value, r.error)) { r.ok = false; return r; }
        skip_ws();
        if (pos_ != s_.size()) { r.ok = false; r.error = "trailing bytes after JSON value"; return r; }
        r.ok = true;
        return r;
    }

private:
    bool parse_value(Json& out, std::string& err) {
        skip_ws();
        if (pos_ >= s_.size()) { err = "unexpected end of input"; return false; }
        const char c = s_[pos_];
        switch (c) {
            case 'n': return parse_literal("null", Json::null(), out, err);
            case 't': return parse_literal("true", Json::make_boolean(true), out, err);
            case 'f': return parse_literal("false", Json::make_boolean(false), out, err);
            case '"': return parse_string(out, err);
            case '[': return parse_array(out, err);
            case '{': return parse_object(out, err);
            default:
                if (c == '-' || (c >= '0' && c <= '9')) return parse_number(out, err);
                err = std::string("unexpected character '") + c + "'";
                return false;
        }
    }

    bool parse_literal(const char* lit, Json v, Json& out, std::string& err) {
        const std::size_t n = std::strlen(lit);
        if (s_.compare(pos_, n, lit) != 0) { err = std::string("invalid literal, expected ") + lit; return false; }
        pos_ += n;
        out = std::move(v);
        return true;
    }

    bool parse_string(Json& out, std::string& err) {
        // s_[pos_] == '"'
        ++pos_;
        std::string val;
        while (true) {
            if (pos_ >= s_.size()) { err = "unterminated string"; return false; }
            const char c = s_[pos_++];
            if (c == '"') break;
            if (c == '\\') {
                if (pos_ >= s_.size()) { err = "unterminated escape"; return false; }
                const char e = s_[pos_++];
                switch (e) {
                    case '"': val += '"'; break;
                    case '\\': val += '\\'; break;
                    case '/': val += '/'; break;
                    case 'b': val += '\b'; break;
                    case 'f': val += '\f'; break;
                    case 'n': val += '\n'; break;
                    case 'r': val += '\r'; break;
                    case 't': val += '\t'; break;
                    case 'u': {
                        if (pos_ + 4 > s_.size()) { err = "truncated \\u escape"; return false; }
                        unsigned cp = 0;
                        for (int i = 0; i < 4; ++i) {
                            const char h = s_[pos_++];
                            cp <<= 4;
                            if (h >= '0' && h <= '9') cp |= static_cast<unsigned>(h - '0');
                            else if (h >= 'a' && h <= 'f') cp |= static_cast<unsigned>(h - 'a' + 10);
                            else if (h >= 'A' && h <= 'F') cp |= static_cast<unsigned>(h - 'A' + 10);
                            else { err = "invalid \\u hex"; return false; }
                        }
                        // Encode as UTF-8 (no surrogate pairing needed for our ASCII field set).
                        if (cp < 0x80) {
                            val += static_cast<char>(cp);
                        } else if (cp < 0x800) {
                            val += static_cast<char>(0xC0 | (cp >> 6));
                            val += static_cast<char>(0x80 | (cp & 0x3F));
                        } else {
                            val += static_cast<char>(0xE0 | (cp >> 12));
                            val += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            val += static_cast<char>(0x80 | (cp & 0x3F));
                        }
                        break;
                    }
                    default: err = std::string("invalid escape '\\") + e + "'"; return false;
                }
            } else if (static_cast<unsigned char>(c) < 0x20) {
                err = "unescaped control character in string";
                return false;
            } else {
                val += c;
            }
        }
        out = Json::make_string(std::move(val));
        return true;
    }

    bool parse_number(Json& out, std::string& err) {
        const std::size_t start = pos_;
        if (pos_ < s_.size() && s_[pos_] == '-') ++pos_;
        if (pos_ >= s_.size() || s_[pos_] < '0' || s_[pos_] > '9') {
            err = "invalid number"; return false;
        }
        if (s_[pos_] == '0') {
            ++pos_;
            if (pos_ < s_.size() && s_[pos_] >= '0' && s_[pos_] <= '9') {
                err = "leading zero in number"; return false;
            }
        } else {
            while (pos_ < s_.size() && s_[pos_] >= '0' && s_[pos_] <= '9') ++pos_;
        }
        if (pos_ < s_.size() && s_[pos_] == '.') {
            ++pos_;
            if (pos_ >= s_.size() || s_[pos_] < '0' || s_[pos_] > '9') { err = "invalid fraction"; return false; }
            while (pos_ < s_.size() && s_[pos_] >= '0' && s_[pos_] <= '9') ++pos_;
        }
        if (pos_ < s_.size() && (s_[pos_] == 'e' || s_[pos_] == 'E')) {
            ++pos_;
            if (pos_ < s_.size() && (s_[pos_] == '+' || s_[pos_] == '-')) ++pos_;
            if (pos_ >= s_.size() || s_[pos_] < '0' || s_[pos_] > '9') { err = "invalid exponent"; return false; }
            while (pos_ < s_.size() && s_[pos_] >= '0' && s_[pos_] <= '9') ++pos_;
        }
        const std::string tok = s_.substr(start, pos_ - start);
        char* end = nullptr;
        const double v = std::strtod(tok.c_str(), &end);
        if (end == tok.c_str() || *end != '\0') { err = "invalid number token"; return false; }
        out = Json::make_number(v);
        return true;
    }

    bool parse_array(Json& out, std::string& err) {
        ++pos_;   // '['
        std::vector<Json> items;
        skip_ws();
        if (pos_ < s_.size() && s_[pos_] == ']') { ++pos_; out = Json::make_array(std::move(items)); return true; }
        while (true) {
            Json v;
            if (!parse_value(v, err)) return false;
            items.push_back(std::move(v));
            skip_ws();
            if (pos_ >= s_.size()) { err = "unterminated array"; return false; }
            if (s_[pos_] == ']') { ++pos_; break; }
            if (s_[pos_] != ',') { err = "expected ',' or ']' in array"; return false; }
            ++pos_;
            skip_ws();
        }
        out = Json::make_array(std::move(items));
        return true;
    }

    bool parse_object(Json& out, std::string& err) {
        ++pos_;   // '{'
        std::vector<std::pair<std::string, Json>> items;
        skip_ws();
        if (pos_ < s_.size() && s_[pos_] == '}') { ++pos_; out = Json::make_object(std::move(items)); return true; }
        while (true) {
            skip_ws();
            if (pos_ >= s_.size() || s_[pos_] != '"') { err = "expected object key string"; return false; }
            Json key;
            if (!parse_string(key, err)) return false;
            skip_ws();
            if (pos_ >= s_.size() || s_[pos_] != ':') { err = "expected ':' after object key"; return false; }
            ++pos_;
            Json v;
            if (!parse_value(v, err)) return false;
            items.emplace_back(std::move(key.string), std::move(v));
            skip_ws();
            if (pos_ >= s_.size()) { err = "unterminated object"; return false; }
            if (s_[pos_] == '}') { ++pos_; break; }
            if (s_[pos_] != ',') { err = "expected ',' or '}' in object"; return false; }
            ++pos_;
        }
        out = Json::make_object(std::move(items));
        return true;
    }

    void skip_ws() {
        while (pos_ < s_.size()) {
            const char c = s_[pos_];
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') ++pos_;
            else break;
        }
    }

    const std::string& s_;
    std::size_t pos_ = 0;
};

}  // namespace detail_json

// Parse a JSON document.  Returns ok=false + error on any malformed input.
inline JsonParseResult json_parse(const std::string& text) {
    return detail_json::Parser(text).parse();
}

namespace detail_json {

// Emit a double as a JSON number: integers without a decimal point, non-integers
// with 17 significant digits (guarantees an exact round-trip through Python's repr
// and back, so the PC-side and board-side tx_scale / target_rms compare exactly).
inline std::string dump_number(double v) {
    if (std::isfinite(v) && std::floor(v) == v && std::fabs(v) < 9.0e15) {
        return std::to_string(static_cast<std::int64_t>(v));
    }
    std::ostringstream oss;
    oss << std::setprecision(17) << std::defaultfloat << v;
    return oss.str();
}

inline void dump_string(const std::string& s, std::string& out) {
    out += '"';
    for (unsigned char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += static_cast<char>(c);
                }
        }
    }
    out += '"';
}

inline void dump_value(const Json& v, std::string& out) {
    switch (v.kind) {
        case Json::Kind::Null: out += "null"; break;
        case Json::Kind::Bool: out += v.boolean ? "true" : "false"; break;
        case Json::Kind::Number: out += dump_number(v.number); break;
        case Json::Kind::String: dump_string(v.string, out); break;
        case Json::Kind::Array: {
            out += '[';
            for (std::size_t i = 0; i < v.array.size(); ++i) {
                if (i) out += ',';
                dump_value(v.array[i], out);
            }
            out += ']';
            break;
        }
        case Json::Kind::Object: {
            out += '{';
            for (std::size_t i = 0; i < v.object.size(); ++i) {
                if (i) out += ',';
                dump_string(v.object[i].first, out);
                out += ':';
                dump_value(v.object[i].second, out);
            }
            out += '}';
            break;
        }
    }
}

}  // namespace detail_json

// Serialize a Json value to a compact JSON document.
inline std::string json_dump(const Json& v) {
    std::string out;
    detail_json::dump_value(v, out);
    return out;
}

// ---------------------------------------------------------------------------
// TcpControlClient -- AF_INET SOCK_STREAM client with uint32 big-endian length-
// prefixed JSON frames.  Blocking socket + poll()-based timeouts.
// ---------------------------------------------------------------------------
class TcpControlClient {
public:
    TcpControlClient() = default;
    TcpControlClient(const TcpControlClient&) = delete;
    TcpControlClient& operator=(const TcpControlClient&) = delete;
    ~TcpControlClient() { close(); }

    std::string host;
    std::uint16_t port = kDefaultPort;
    int connect_timeout_ms = kDefaultConnectTimeoutMs;
    int message_timeout_ms = kDefaultMessageTimeoutMs;
    std::size_t max_message_bytes = kMaxMessageBytes;

    std::size_t bytes_sent = 0;
    std::size_t bytes_received = 0;
    std::size_t messages_sent = 0;
    std::size_t messages_received = 0;
    std::size_t oversize_rejected = 0;

    // Resolve + connect with a hard connect timeout.  Returns false (and sets `err`)
    // on any failure; the previous connection (if any) is closed first.
    bool connect(std::string* err) {
        close();
        std::string local_err;
        const int fd = connect_fd(&local_err);
        if (fd < 0) { if (err) *err = local_err; return false; }
        fd_ = fd;
        return true;
    }

    void close() {
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
#endif
        recv_buf_.clear();
    }

    bool connected() const { return fd_ >= 0; }

    // Serialize a Json value and send it with a big-endian length prefix.  Refuses
    // (fail-closed) any payload > max_message_bytes.
    bool send_json(const Json& msg, std::string* err) {
        const std::string json = json_dump(msg);
        return send_json_text(json, err);
    }

    bool send_json_text(const std::string& json, std::string* err) {
        if (json.size() > max_message_bytes) {
            if (err) *err = "outgoing message exceeds max_message_bytes";
            return false;
        }
        if (fd_ < 0) { if (err) *err = "not connected"; return false; }
        const std::uint32_t len = static_cast<std::uint32_t>(json.size());
        std::string frame;
        frame.reserve(4 + json.size());
        frame.push_back(static_cast<char>((len >> 24) & 0xFF));
        frame.push_back(static_cast<char>((len >> 16) & 0xFF));
        frame.push_back(static_cast<char>((len >> 8) & 0xFF));
        frame.push_back(static_cast<char>(len & 0xFF));
        frame += json;
        if (!send_all(frame.data(), frame.size(), err)) return false;
        bytes_sent += frame.size();
        ++messages_sent;
        return true;
    }

    // Receive one complete frame: read the 4-byte length prefix, enforce the hard
    // size limit, read the JSON payload, and return it.  Handles fragmentation and
    // coalescing (multiple frames arriving in one read) via the internal buffer.
    bool recv_json(std::string& json, std::string* err) {
        json.clear();
        if (fd_ < 0) { if (err) *err = "not connected"; return false; }

        while (true) {
            // Need 4 bytes to know the length.
            if (recv_buf_.size() >= 4) {
                const std::uint32_t len =
                    (static_cast<std::uint32_t>(static_cast<unsigned char>(recv_buf_[0])) << 24) |
                    (static_cast<std::uint32_t>(static_cast<unsigned char>(recv_buf_[1])) << 16) |
                    (static_cast<std::uint32_t>(static_cast<unsigned char>(recv_buf_[2])) << 8) |
                    (static_cast<std::uint32_t>(static_cast<unsigned char>(recv_buf_[3])));
                if (len > max_message_bytes) {
                    ++oversize_rejected;
                    if (err) *err = "incoming message length " + std::to_string(len) +
                                   " exceeds max_message_bytes";
                    close();
                    return false;
                }
                if (recv_buf_.size() >= 4 + static_cast<std::size_t>(len)) {
                    json.assign(recv_buf_.data() + 4, static_cast<std::size_t>(len));
                    recv_buf_.erase(0, 4 + static_cast<std::size_t>(len));
                    bytes_received += 4 + static_cast<std::size_t>(len);
                    ++messages_received;
                    return true;
                }
            }

            // Need more bytes.
            if (!wait_readable(message_timeout_ms)) {
                if (err) *err = "recv timeout (message_timeout_ms)";
                return false;
            }
            char tmp[4096];
            const ssize_t n = ::recv(fd_, tmp, sizeof(tmp), 0);
            if (n > 0) {
                recv_buf_.append(tmp, static_cast<std::size_t>(n));
                continue;
            }
            if (n == 0) { if (err) *err = "peer closed connection"; close(); return false; }
            if (errno == EINTR) continue;
            if (err) *err = std::string("recv error: ") + std::strerror(errno);
            close();
            return false;
        }
    }

private:
    int connect_fd(std::string* err) {
#if defined(__unix__) || defined(__APPLE__)
        struct addrinfo hints;
        std::memset(&hints, 0, sizeof(hints));
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_STREAM;
        hints.ai_protocol = IPPROTO_TCP;

        struct addrinfo* res = nullptr;
        const std::string port_str = std::to_string(port);
        const int gai = ::getaddrinfo(host.c_str(), port_str.c_str(), &hints, &res);
        if (gai != 0) {
            if (err) *err = std::string("getaddrinfo: ") + ::gai_strerror(gai);
            return -1;
        }
        int fd = -1;
        for (struct addrinfo* p = res; p != nullptr; p = p->ai_next) {
            fd = ::socket(p->ai_family, p->ai_socktype, p->ai_protocol);
            if (fd < 0) continue;
            set_nonblock(fd, true);
            const int rc = ::connect(fd, p->ai_addr, static_cast<socklen_t>(p->ai_addrlen));
            if (rc == 0) {
                ::freeaddrinfo(res);
                set_nonblock(fd, false);
                return fd;
            }
            if (errno == EINPROGRESS) {
                if (wait_fd(fd, POLLOUT, connect_timeout_ms)) {
                    int soerr = 0;
                    socklen_t slen = sizeof(soerr);
                    ::getsockopt(fd, SOL_SOCKET, SO_ERROR, &soerr, &slen);
                    if (soerr == 0) {
                        ::freeaddrinfo(res);
                        set_nonblock(fd, false);
                        return fd;
                    }
                }
            }
            ::close(fd);
            fd = -1;
        }
        ::freeaddrinfo(res);
        if (err) *err = "connect failed or timed out";
        return -1;
#else
        if (err) *err = "tcp control unsupported on this platform";
        (void)host; (void)port;
        return -1;
#endif
    }

    bool send_all(const char* data, std::size_t n, std::string* err) {
#if defined(__unix__) || defined(__APPLE__)
        std::size_t off = 0;
        while (off < n) {
            if (!wait_fd(fd_, POLLOUT, message_timeout_ms)) {
                if (err) *err = "send timeout (message_timeout_ms)";
                return false;
            }
#ifdef MSG_NOSIGNAL
            const int flags = MSG_NOSIGNAL;
#else
            const int flags = 0;
#endif
            const ssize_t w = ::send(fd_, data + off, n - off, flags);
            if (w > 0) { off += static_cast<std::size_t>(w); continue; }
            if (w < 0 && errno == EINTR) continue;
            if (err) *err = std::string("send error: ") + std::strerror(errno);
            return false;
        }
        return true;
#else
        (void)data; (void)n;
        if (err) *err = "tcp control unsupported on this platform";
        return false;
#endif
    }

    bool wait_readable(int timeout_ms) { return wait_fd(fd_, POLLIN, timeout_ms); }

    bool wait_fd(int fd, short events, int timeout_ms) {
#if defined(__unix__) || defined(__APPLE__)
        struct pollfd p;
        p.fd = fd;
        p.events = events;
        p.revents = 0;
        int rc;
        do { rc = ::poll(&p, 1, timeout_ms); } while (rc < 0 && errno == EINTR);
        if (rc <= 0) return false;
        if (p.revents & (POLLERR | POLLHUP | POLLNVAL)) return false;
        return (p.revents & events) != 0;
#else
        (void)fd; (void)events; (void)timeout_ms;
        return false;
#endif
    }

    static void set_nonblock(int fd, bool on) {
#if defined(__unix__) || defined(__APPLE__)
        const int fl = ::fcntl(fd, F_GETFL, 0);
        if (fl >= 0) {
            if (on) ::fcntl(fd, F_SETFL, fl | O_NONBLOCK);
            else ::fcntl(fd, F_SETFL, fl & ~O_NONBLOCK);
        }
#else
        (void)fd; (void)on;
#endif
    }

    int fd_ = -1;
    std::string recv_buf_;
};

// Parse a --tx-control URL of the form "tcp://host:port" (or "host:port").  Returns
// false (and sets `err`) on a malformed or out-of-range port.
inline bool parse_tx_control_url(const std::string& url, std::string& host,
                                 std::uint16_t& port, std::string* err) {
    std::string rest = url;
    const std::string prefix = "tcp://";
    if (rest.compare(0, prefix.size(), prefix) == 0) rest = rest.substr(prefix.size());
    const std::size_t colon = rest.rfind(':');
    if (colon == std::string::npos || colon == 0 || colon + 1 >= rest.size()) {
        if (err) *err = "malformed --tx-control URL (want tcp://host:port)";
        return false;
    }
    host = rest.substr(0, colon);
    const std::string port_str = rest.substr(colon + 1);
    char* end = nullptr;
    const long p = std::strtol(port_str.c_str(), &end, 10);
    if (end == port_str.c_str() || *end != '\0' || p < 1 || p > 65535) {
        if (err) *err = "invalid port in --tx-control URL";
        return false;
    }
    port = static_cast<std::uint16_t>(p);
    return true;
}

}  // namespace iqpctbrx
