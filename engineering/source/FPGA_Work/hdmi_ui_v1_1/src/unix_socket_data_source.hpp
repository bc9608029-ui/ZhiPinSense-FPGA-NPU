#pragma once
// Live SDR data path: the SDR adapter (C++) streams ResultFrame JSON lines over
// a Unix domain socket; this source connects, reconnects, and parses them
// line-by-line.  A missing server never crashes the UI — the source just stays
// disconnected and next() keeps retrying, so the UI shows "SDR" with no frames
// (and eventually dims to stale) until the adapter appears.
//
// The line-framing logic lives in the Qt-free src/line_buffer.hpp so the socket
// protocol can be unit-tested on the host without a server.
#include <cstdint>
#include <memory>
#include <optional>
#include <string>

#include "src/data_source.hpp"
#include "src/line_buffer.hpp"

class QLocalSocket;

namespace hdmiui {

class UnixSocketDataSource : public DataSource {
public:
    explicit UnixSocketDataSource(const std::string& socket_path);
    ~UnixSocketDataSource() override;

    std::string name() const override { return "SDR"; }
    std::string kind() const override { return "unix_socket"; }
    bool is_live() const override { return true; }  // never "ends" like a file

    bool open(std::string* error) override;
    std::optional<ResultFrame> next(int timeout_ms) override;
    void close() override;

private:
    void ensure_connected();
    bool connected() const;
    std::optional<ResultFrame> parse_pending();

    std::string path_;
    std::unique_ptr<QLocalSocket> sock_;
    LineBuffer buf_;
    std::uint64_t error_ = 0;        // malformed + oversized lines, folded into
                                     // the next valid frame's counters.error
    std::uint64_t last_connect_ms_ = 0;
    bool opened_ = false;
};

}  // namespace hdmiui
