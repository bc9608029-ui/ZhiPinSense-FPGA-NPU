#pragma once

// control_client.hpp -- non-blocking AF_UNIX SOCK_STREAM client for the reverse
// control channel (task 39e5 UI v3 M16).
//
// board_ui_live_12class uses this to reach the Gate 9 producer's control socket
// (/run/sdr_amr_control.sock) as a pure CLIENT: send SET_MODE / START / STOP /
// STATUS, and read the ACCEPTED / APPLIED / ERR / STATUS replies.  The producer
// remains the sole owner of the socket node -- the UI never binds it and never
// unlinks it.
//
// Rules (frozen):
//   * connect is non-blocking; a missing / not-yet-listening socket returns false
//     (the caller disables the touch buttons and retries on a timer), it NEVER
//     blocks the display loop or crashes;
//   * reads are non-blocking with cross-read line splicing, so half / glued /
//     multi-line replies are reassembled correctly;
//   * send_line is non-blocking: a would-block send is dropped (returns false)
//     rather than stalling render/touch;
//   * close() closes the fd but NEVER unlinks the producer's socket path.
//
// POSIX-only (Linux board / WSL host); header-only.

#if defined(__unix__) || defined(__APPLE__)
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#endif

#include <cerrno>
#include <cstddef>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

namespace ctl {

class ControlClient {
public:
    explicit ControlClient(std::string path) : path_(std::move(path)) {}
    ControlClient(const ControlClient&) = delete;
    ControlClient& operator=(const ControlClient&) = delete;
    ~ControlClient() { close(); }

    // Open a connection to the producer's control socket.  Never throws.  Returns
    // true when connected; a missing socket or a not-yet-listening producer returns
    // false (the caller retries later).
    bool connect() {
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ >= 0) return true;
        const int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd < 0) return false;
        sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        if (path_.size() >= sizeof(addr.sun_path)) { ::close(fd); return false; }
        std::strncpy(addr.sun_path, path_.c_str(), sizeof(addr.sun_path) - 1);
        addr.sun_path[sizeof(addr.sun_path) - 1] = '\0';
        // Non-blocking connect: AF_UNIX connect completes synchronously in
        // practice, but O_NONBLOCK guarantees we can never hang on a stuck peer.
        const int fl = ::fcntl(fd, F_GETFL, 0);
        if (fl >= 0) ::fcntl(fd, F_SETFL, fl | O_NONBLOCK);
        if (::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
            ::close(fd);
            return false;
        }
        fd_ = fd;
        buf_.clear();
        return true;
#else
        (void)path_;
        return false;
#endif
    }

    bool is_connected() const { return fd_ >= 0; }
    const std::string& path() const { return path_; }

    // Send one line (newline appended, MSG_NOSIGNAL).  Non-blocking: a would-block
    // send is dropped (returns false) rather than stalling the display loop.  The
    // UI only sends one command per tap and retries only on a fresh tap, so a
    // dropped send simply leaves the request unsent (visible as a divergence).
    bool send_line(const std::string& line) {
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ < 0) return false;
        std::string out = line;
        out.push_back('\n');
#ifdef MSG_NOSIGNAL
        const int flags = MSG_NOSIGNAL;
#else
        const int flags = 0;
#endif
        std::size_t off = 0;
        while (off < out.size()) {
            const ssize_t n = ::send(fd_, out.data() + off, out.size() - off, flags);
            if (n > 0) { off += static_cast<std::size_t>(n); continue; }
            if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return false;
            if (n < 0 && errno == EINTR) continue;
            return false;   // hard error
        }
        return true;
#else
        (void)line;
        return false;
#endif
    }

    // Poll for up to timeout_ms and return any complete reply lines (half / glued /
    // multi-line replies are spliced across reads).  On EOF/error the fd is closed
    // (is_connected() becomes false) and the caller reconnects.  Never blocks
    // beyond timeout_ms.
    std::vector<std::string> poll(int timeout_ms) {
        std::vector<std::string> out;
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ < 0) return out;
        pollfd pfd{fd_, POLLIN, 0};
        const int rc = ::poll(&pfd, 1, timeout_ms);
        if (rc < 0) {
            if (errno == EINTR) return out;
            close();
            return out;
        }
        if (rc == 0) return out;
        if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) { close(); return out; }
        if (!(pfd.revents & POLLIN)) return out;
        if (!drain(out)) close();
#endif
        return out;
    }

    // Close the client fd but NEVER unlink the producer's socket node.
    void close() {
#if defined(__unix__) || defined(__APPLE__)
        if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
        buf_.clear();
#endif
    }

private:
    bool drain(std::vector<std::string>& out) {
#if defined(__unix__) || defined(__APPLE__)
        for (;;) {
            char tmp[4096];
            const ssize_t n = ::recv(fd_, tmp, sizeof(tmp), 0);
            if (n > 0) {
                buf_.append(tmp, static_cast<std::size_t>(n));
                while (true) {
                    const std::size_t nl = buf_.find('\n');
                    if (nl == std::string::npos) break;
                    std::string line = buf_.substr(0, nl);
                    if (!line.empty() && line.back() == '\r') line.pop_back();
                    out.push_back(std::move(line));
                    buf_.erase(0, nl + 1);
                }
                continue;
            }
            if (n == 0) return false;                      // EOF
            if (errno == EAGAIN || errno == EWOULDBLOCK) return true;   // drained
            if (errno == EINTR) continue;
            return false;                                  // hard error
        }
#else
        (void)out;
        return false;
#endif
    }

    std::string path_;
    int fd_ = -1;
    std::string buf_;   // pending half-line (no trailing '\n' yet)
};

}  // namespace ctl
