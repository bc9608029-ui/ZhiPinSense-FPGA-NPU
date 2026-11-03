#pragma once

// Unix domain socket JSON-lines sink (HDMI/UI adapter) for the system layer.
//
// Emits one JSON record per line to a connected AF_UNIX SOCK_STREAM socket, so
// an on-board UI / log consumer can read results without parsing stdout.  When
// the path is empty the sink is disabled (a no-op).  A write to a socket that is
// not connectable / has gone away is recorded as an error and dropped -- the
// sink never throws and never blocks the inference pipeline.
//
// POSIX-only (Linux board / WSL host); on other platforms the socket body is
// compiled out and write() reports unsupported.  iCraft-free.

#include "ui_report.hpp"

#if defined(__unix__) || defined(__APPLE__)
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/un.h>
#include <unistd.h>
#endif

#include <cstddef>
#include <string>
#include <utility>

namespace ui {

class UnixSocketSink : public Sink {
public:
    // path == "" disables the sink (no-op writes).
    explicit UnixSocketSink(std::string path) : path_(std::move(path)) {}

    // Attach an already-connected socket fd (test / embedding use).  `owns` =>
    // the sink closes it on destruction.
    UnixSocketSink(int fd, bool owns) : fd_(fd), owns_(owns) {}

    UnixSocketSink(const UnixSocketSink&) = delete;
    UnixSocketSink& operator=(const UnixSocketSink&) = delete;

    UnixSocketSink(UnixSocketSink&& o) noexcept
        : path_(std::move(o.path_)), fd_(o.fd_), owns_(o.owns_),
          errors_(o.errors_) {
        o.fd_ = -1;
        o.owns_ = false;
    }

    ~UnixSocketSink() { close_fd(); }

    void write(const std::string& json_line) override {
        if (!enabled()) return;
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ < 0 && !connect_by_path()) {
            ++errors_;
            return;  // no listener / bad path: drop, never throw
        }
        const std::string line = json_line + "\n";
#ifdef MSG_NOSIGNAL
        const int flags = MSG_NOSIGNAL;
#else
        const int flags = 0;
#endif
        const ssize_t n = ::send(fd_, line.data(), line.size(), flags);
        if (n < 0 || static_cast<std::size_t>(n) != line.size()) {
            ++errors_;
            close_fd();  // peer gone; reconnect on next write
        }
#else
        (void)json_line;
        ++errors_;
#endif
    }

    bool enabled() const {
#if defined(__unix__) || defined(__APPLE__)
        return !path_.empty() || fd_ >= 0;
#else
        return false;
#endif
    }

    std::size_t error_count() const { return errors_; }

private:
    void close_fd() {
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ >= 0 && owns_) ::close(fd_);
#endif
        fd_ = -1;
        owns_ = false;
    }

    bool connect_by_path() {
#if defined(__unix__) || defined(__APPLE__)
        fd_ = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd_ < 0) return false;
        owns_ = true;
        sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        if (path_.size() >= sizeof(addr.sun_path)) { close_fd(); return false; }
        for (std::size_t i = 0; i < path_.size(); ++i)
            addr.sun_path[i] = path_[i];
        addr.sun_path[path_.size()] = '\0';
        if (::connect(fd_, reinterpret_cast<sockaddr*>(&addr),
                      sizeof(addr)) != 0) {
            close_fd();
            return false;
        }
        return true;
#else
        return false;
#endif
    }

    std::string path_;
    int fd_ = -1;
    bool owns_ = false;
    std::size_t errors_ = 0;
};

}  // namespace ui
