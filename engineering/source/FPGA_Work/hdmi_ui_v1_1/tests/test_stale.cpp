// Qt-free staleness test: the arrival-time window that dims a stale frame.
// Mirrors the Python mirror tests/test_frame_validator_mirror.py.

#include <cstdint>
#include <cstdio>

#include "contracts/result_frame.hpp"
#include "src/frame_validator.hpp"

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
    // is_stale boundary (timestamp, now, timeout).
    check(is_stale(100, 200, 50), "is_stale(older-than-window)");
    check(!is_stale(160, 200, 50), "is_stale(within-window)");
    check(!is_stale(200, 200, 50), "is_stale(exact boundary)");
    check(!is_stale(300, 200, 50), "is_stale(clock skew)");

    StaleDetector d(1500000000ULL);  // 1500 ms
    check(d.timeout_ns() == 1500000000ULL, "timeout_ns stored");
    check(d.is_stale(1000, 2000000000ULL), "detector stale");
    check(!d.is_stale(1000, 500000000ULL), "detector fresh");

    d.set_timeout_ns(1000ULL);
    check(d.timeout_ns() == 1000ULL, "set_timeout_ns");
    check(d.is_stale(0, 2000), "detector stale after retime");

    if (g_failures == 0) {
        std::printf("test_stale: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_stale: %d check(s) failed\n", g_failures);
    return 1;
}
