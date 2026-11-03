// Qt-free test of the Unix-socket line framer (src/line_buffer.hpp): line
// splitting across chunk boundaries, CRLF stripping, and the strict per-line
// size limit.  Mirrors the Python mirror tests/test_json_result_frame.py.

#include <cstdint>
#include <cstdio>
#include <string>

#include "src/line_buffer.hpp"

using namespace hdmiui;

namespace {
int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++g_failures;
    }
}
}  // namespace

int main() {
    LineBuffer b;

    // Two complete lines in one push.
    check(b.push("a\nb\n", 4) == 0, "push two lines: no drops");
    std::string s;
    check(b.pop_line(&s) && s == "a", "line 1 == a");
    check(b.pop_line(&s) && s == "b", "line 2 == b");
    check(!b.pop_line(&s), "no third line");

    // Split across pushes.
    check(b.push("hel", 3) == 0, "split push 1");
    check(b.pop_line(&s) == false, "no line until newline");
    check(b.push("lo\n", 3) == 0, "split push 2");
    check(b.pop_line(&s) && s == "hello", "reassembled line");

    // CRLF stripped.
    check(b.push("x\r\ny\n", 5) == 0, "CRLF push");
    check(b.pop_line(&s) && s == "x", "CRLF stripped (x)");
    check(b.pop_line(&s) && s == "y", "CRLF stripped (y)");

    // Oversized complete line dropped, but following line kept.
    {
        LineBuffer c;
        std::string big(LineBuffer::kMaxLineBytes + 1, 'z');
        const std::string chunk = big + "\nok\n";
        check(c.push(chunk.c_str(), chunk.size()) == 1, "oversized complete line dropped");
        check(c.pop_line(&s) && s == "ok", "line after oversized kept");
        check(!c.pop_line(&s), "no line after 'ok'");
    }

    // Oversized still-partial line (no newline) is dropped to bound the buffer.
    {
        LineBuffer c;
        std::string big(LineBuffer::kMaxLineBytes + 10, 'z');
        check(c.push(big.c_str(), big.size()) == 1, "oversized partial dropped");
        check(c.push("next\n", 5) == 0, "resync after oversized partial");
        check(c.pop_line(&s) && s == "next", "resync line");
    }

    if (g_failures == 0) {
        std::printf("test_line_buffer: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_line_buffer: %d check(s) failed\n", g_failures);
    return 1;
}
