// board_mode_ctl.cpp -- one-shot reverse-control client (task 39e5 UI v3 M6).
//
// Sends a single command line to the Gate 9 producer's control socket and prints
// the one-line reply.  The natural shell peer of board_gate9_full_chain_12class
// --ctl-sock (the producer owns the control channel; the LIVE UI server only
// DISPLAYS the producer-reported work mode / run state):
//
//     board_mode_ctl SET_MODE AUTO_LOCK
//     board_mode_ctl --sock=/run/sdr_amr_control.sock STATUS
//     board_mode_ctl STOP
//
// Every argument that does not start with "--" is a command word; they are joined
// with single spaces into the command line (so "SET_MODE AUTO_LOCK" is two words).
// Only the "--sock=value" (single-token) spelling is accepted, matching the board
// scripts' "--key=value" convention.
//
// Exit code: 0 on an "OK ..." reply, 1 on an "ERR ..." reply or a send/recv
// failure, 2 on a connect failure.  Pure g++ (no iCraft, no libiio).

#if defined(__unix__) || defined(__APPLE__)
#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#endif

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    std::string sock = "/run/sdr_amr_control.sock";
    std::vector<std::string> words;

    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a.rfind("--sock=", 0) == 0) { sock = a.substr(7); continue; }
        if (a.rfind("--", 0) == 0) {
            std::fprintf(stderr, "unknown option: %s\n", a.c_str());
            return 1;
        }
        words.push_back(a);
    }

    std::string cmd;
    for (const std::string& w : words) {
        if (!cmd.empty()) cmd += ' ';
        cmd += w;
    }
    if (cmd.empty()) {
        std::fprintf(stderr,
                     "usage: board_mode_ctl [--sock=PATH] "
                     "SET_MODE FIXED|AUTO_LOCK|BAND_SCAN | START | STOP | STATUS\n");
        return 1;
    }

#if defined(__unix__) || defined(__APPLE__)
    const int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) { std::perror("socket"); return 2; }
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    if (sock.size() >= sizeof(addr.sun_path)) {
        std::fprintf(stderr, "socket path too long\n");
        ::close(fd);
        return 2;
    }
    std::strncpy(addr.sun_path, sock.c_str(), sizeof(addr.sun_path) - 1);
    addr.sun_path[sizeof(addr.sun_path) - 1] = '\0';
    if (::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        std::fprintf(stderr, "connect %s: %s\n", sock.c_str(), std::strerror(errno));
        ::close(fd);
        return 2;
    }

    const std::string line = cmd + "\n";
#ifdef MSG_NOSIGNAL
    const int flags = MSG_NOSIGNAL;
#else
    const int flags = 0;
#endif
    std::size_t off = 0;
    while (off < line.size()) {
        const ssize_t n = ::send(fd, line.data() + off, line.size() - off, flags);
        if (n <= 0) { std::fprintf(stderr, "send failed\n"); ::close(fd); return 1; }
        off += static_cast<std::size_t>(n);
    }

    // Read the one-line reply with a bounded wait (the server replies at once).
    std::string reply;
    char buf[512];
    pollfd pfd{fd, POLLIN, 0};
    const int prc = ::poll(&pfd, 1, 2000);
    if (prc <= 0) { std::fprintf(stderr, "no reply (timeout)\n"); ::close(fd); return 1; }
    for (;;) {
        const ssize_t n = ::recv(fd, buf, sizeof(buf), 0);
        if (n > 0) {
            reply.append(buf, static_cast<std::size_t>(n));
            const std::size_t nl = reply.find('\n');
            if (nl != std::string::npos) { reply.erase(nl); break; }
        } else if (n == 0) {
            break;   // server closed the connection
        } else if (errno == EINTR) {
            continue;
        } else {
            break;
        }
    }
    ::close(fd);

    std::printf("%s\n", reply.c_str());
    return (reply.rfind("OK", 0) == 0) ? 0 : 1;
#else
    (void)sock;
    (void)cmd;
    std::fprintf(stderr, "AF_UNIX not available on this platform\n");
    return 2;
#endif
}
