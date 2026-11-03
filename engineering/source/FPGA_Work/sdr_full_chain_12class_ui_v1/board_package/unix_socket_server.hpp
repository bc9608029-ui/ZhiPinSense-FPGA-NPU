#pragma once

// unix_socket_server.hpp -- AF_UNIX SOCK_STREAM server for the twelve-class UI
// (task 39e5 §四/§五).  This is the receiving half of the result_frame_v2 JSON-lines
// link: Gate 8 / Gate 9 open the socket as a ui::UnixSocketSink (CLIENT) and write
// one JSON record per line; board_ui_live_12class runs this server and reads them.
//
// Design rules (frozen by the §四 corrections):
//   * poll(2)-driven, non-blocking reads -- the server NEVER blocks the display
//     tick waiting on a peer, so a slow or absent producer cannot freeze the UI.
//   * line buffering with cross-read splicing: a half-received line is kept in
//     buf_ and completed on a later read (senders may split a line across sends).
//   * disconnect/reconnect: read()==0 or an error closes the client and drops the
//     pending half-line (a truncated tail is malformed, never a frame), then the
//     server returns to listen and accepts a fresh producer.
//
// POSIX-only (Linux board / WSL host).  iCraft-free, libiio-free; the host test
// test_ui_live.cpp drives a real AF_UNIX loopback through this exact class.

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
#include <vector>

namespace ui {

class UnixSocketServer {
public:
    enum class PollStatus { Idle, Lines, ClientGone, Error };

    struct PollResult {
        PollStatus status = PollStatus::Idle;
        std::vector<std::string> lines;   // complete JSON-lines delivered this tick
    };

    explicit UnixSocketServer(std::string path) : path_(std::move(path)) {}
    UnixSocketServer(const UnixSocketServer&) = delete;
    UnixSocketServer& operator=(const UnixSocketServer&) = delete;
    ~UnixSocketServer() { stop(); }

    // unlink any stale socket node -> socket() -> bind() -> listen(1) -> O_NONBLOCK.
    // Returns false (errno available) on any failure; path_ must fit sun_path.
    bool start() {
#if defined(__unix__) || defined(__APPLE__)
        ::unlink(path_.c_str());
        listen_fd_ = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (listen_fd_ < 0) return false;
        sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        if (path_.size() >= sizeof(addr.sun_path)) { stop(); return false; }
        std::strncpy(addr.sun_path, path_.c_str(), sizeof(addr.sun_path) - 1);
        addr.sun_path[sizeof(addr.sun_path) - 1] = '\0';
        if (::bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr),
                   sizeof(addr)) != 0) { stop(); return false; }
        if (::listen(listen_fd_, 1) != 0) { stop(); return false; }
        set_nonblock(listen_fd_);
        return true;
#else
        (void)path_;
        return false;
#endif
    }

    // Accept a pending connection, then drain readable bytes into complete lines.
    // Blocks at most `timeout_ms` inside poll().  status:
    //   Lines      -- one or more complete lines were delivered this tick
    //   ClientGone -- the peer disconnected (partial tail discarded; any complete
    //                 lines read before the EOF are still reported in `lines`)
    //   Idle       -- timeout, or only a new connect / a partial line so far
    //   Error      -- poll() failed
    PollResult poll(int timeout_ms) {
        PollResult r;
#if defined(__unix__) || defined(__APPLE__)
        if (listen_fd_ < 0) { r.status = PollStatus::Error; return r; }

        pollfd fds[2];
        nfds_t nfds = 0;
        fds[nfds] = {listen_fd_, POLLIN, 0}; ++nfds;
        if (client_fd_ >= 0) { fds[nfds] = {client_fd_, POLLIN, 0}; ++nfds; }

        const int rc = ::poll(fds, nfds, timeout_ms);
        if (rc < 0) {
            if (errno == EINTR) return r;   // signal -> idle
            r.status = PollStatus::Error;
            return r;
        }
        if (rc == 0) return r;   // timeout -> idle

        bool client_gone = false;
        for (nfds_t i = 0; i < nfds; ++i) {
            if (!(fds[i].revents & POLLIN)) continue;
            if (fds[i].fd == listen_fd_) {
                const int c = ::accept(listen_fd_, nullptr, nullptr);
                if (c >= 0) {
                    set_nonblock(c);
                    if (client_fd_ >= 0) ::close(client_fd_);
                    client_fd_ = c;
                    buf_.clear();   // fresh stream
                }
            } else if (client_fd_ >= 0 && fds[i].fd == client_fd_) {
                if (!drain(r.lines)) {
                    ::close(client_fd_);
                    client_fd_ = -1;
                    buf_.clear();          // truncated tail is malformed
                    client_gone = true;
                }
            }
        }

        if (!r.lines.empty()) r.status = PollStatus::Lines;
        else if (client_gone) r.status = PollStatus::ClientGone;
        else r.status = PollStatus::Idle;
#endif
        return r;
    }

    std::size_t received_lines() const { return lines_; }
    std::size_t received_bytes() const { return bytes_; }
    const std::string& path() const { return path_; }

    bool listening() const {
#if defined(__unix__) || defined(__APPLE__)
        return listen_fd_ >= 0;
#else
        return false;
#endif
    }

    void stop() {
#if defined(__unix__) || defined(__APPLE__)
        if (client_fd_ >= 0) { ::close(client_fd_); client_fd_ = -1; }
        if (listen_fd_ >= 0) { ::close(listen_fd_); listen_fd_ = -1; }
        ::unlink(path_.c_str());
        buf_.clear();
#endif
    }

private:
    // Read until EAGAIN (true: more may come) or EOF/error (false: peer gone).
    // Appends each complete line (newline stripped, trailing '\r' stripped) to
    // `lines`.  Bounded per tick so the display loop never starves.
    bool drain(std::vector<std::string>& lines) {
#if defined(__unix__) || defined(__APPLE__)
        std::size_t total = 0;
        const std::size_t kMaxPerPoll = 256 * 1024;
        while (total < kMaxPerPoll) {
            char tmp[4096];
            const ssize_t n = ::recv(client_fd_, tmp, sizeof(tmp), 0);
            if (n > 0) {
                total += static_cast<std::size_t>(n);
                bytes_ += static_cast<std::size_t>(n);
                buf_.append(tmp, static_cast<std::size_t>(n));
                while (true) {
                    const std::size_t nl = buf_.find('\n');
                    if (nl == std::string::npos) break;
                    std::string line = buf_.substr(0, nl);
                    if (!line.empty() && line.back() == '\r') line.pop_back();
                    lines.push_back(std::move(line));
                    ++lines_;
                    buf_.erase(0, nl + 1);
                }
                continue;
            }
            if (n == 0) return false;                        // EOF
            if (errno == EAGAIN || errno == EWOULDBLOCK) return true;   // drained
            if (errno == EINTR) continue;                    // retry after signal
            return false;                                    // hard error
        }
        return true;
#else
        (void)lines;
        return false;
#endif
    }

    static void set_nonblock(int fd) {
#if defined(__unix__) || defined(__APPLE__)
        const int fl = ::fcntl(fd, F_GETFL, 0);
        if (fl >= 0) ::fcntl(fd, F_SETFL, fl | O_NONBLOCK);
#endif
    }

    std::string path_;
    int listen_fd_ = -1;
    int client_fd_ = -1;
    std::string buf_;           // pending half-line (no trailing '\n' yet)
    std::size_t lines_ = 0;
    std::size_t bytes_ = 0;
};

}  // namespace ui
