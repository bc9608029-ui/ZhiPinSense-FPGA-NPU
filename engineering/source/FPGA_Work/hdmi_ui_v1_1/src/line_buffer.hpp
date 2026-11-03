#pragma once
// Qt-free byte -> JSON-line framer for the Unix-socket source.  Enforces a
// strict per-line size limit so a single runaway message cannot grow the buffer
// unbounded, strips CRLF, and queues complete lines in arrival order.
//
// Extracted from the QLocalSocket wiring so the framing protocol can be
// unit-tested on the host with only a C++17 toolchain (no Qt).
#include <cstddef>
#include <deque>
#include <string>

namespace hdmiui {

struct LineBuffer {
    static constexpr std::size_t kMaxLineBytes = 65536;

    // Append raw bytes.  Returns the number of lines dropped for exceeding
    // kMaxLineBytes (either a complete line or a still-partial line).
    std::size_t push(const char* data, std::size_t n) {
        std::size_t drops = 0;
        pending.append(data, n);
        std::size_t nl;
        while ((nl = pending.find('\n')) != std::string::npos) {
            std::string line = pending.substr(0, nl);
            pending.erase(0, nl + 1);
            if (!line.empty() && line.back() == '\r') line.pop_back();  // CRLF
            if (line.size() > kMaxLineBytes) {
                drops++;
                continue;  // drop the oversized line, do not queue it
            }
            lines.push_back(std::move(line));
        }
        // A still-partial line over the limit cannot be a valid message: drop it
        // so the buffer stays bounded, and resync at the next line boundary.
        if (pending.size() > kMaxLineBytes) {
            pending.clear();
            drops++;
        }
        return drops;
    }

    // Pop the next complete line (in arrival order).  Returns false when empty.
    bool pop_line(std::string* out) {
        if (lines.empty()) return false;
        *out = std::move(lines.front());
        lines.pop_front();
        return true;
    }

    std::size_t queued() const { return lines.size(); }

    void clear() {
        pending.clear();
        lines.clear();
    }

private:
    std::string pending;            // bytes without a terminating '\n' yet
    std::deque<std::string> lines;  // complete lines awaiting parse
};

}  // namespace hdmiui
