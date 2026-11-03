// Qt-free sequence-integrity test: duplicate / reorder / gap / dropped
// detection, mirroring iq::SequenceMonitor (read-only).  The same assertions
// live in the Python mirror tests/test_frame_validator_mirror.py.

#include <cstdint>
#include <cstdio>

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
    FrameSequenceMonitor m;

    // First frame seeds the monitor; no anomaly.
    m.observe(10);
    check(m.stats().seen == 1 && m.stats().have_last, "first frame seeds");
    check(m.stats().duplicate == 0 && m.stats().reorder == 0 &&
              m.stats().dropped == 0 && m.stats().gap == 0,
          "no anomaly on first frame");

    // Duplicate.
    m.observe(10);
    m.observe(10);
    check(m.stats().duplicate == 2, "duplicate == 2");

    // Reorder (backward).
    m.reset();
    m.observe(1);
    m.observe(2);
    m.observe(3);
    m.observe(2);   // 2 < 3 -> reorder
    check(m.stats().reorder == 1, "reorder == 1");
    check(m.stats().last_frame_id == 2, "last_frame_id after reorder");

    // Gap -> dropped (jump of 2 implies 1 dropped frame).
    m.observe(4);   // 4 > 2, jump 2 -> dropped 1
    check(m.stats().gap == 1, "gap == 1");
    check(m.stats().dropped == 1, "dropped == 1");

    // Bigger jump: 4 -> 10 implies 5 dropped.
    m.observe(10);
    check(m.stats().dropped == 1 + 5, "dropped accumulates");
    check(m.stats().gap == 2, "gap == 2");

    if (g_failures == 0) {
        std::printf("test_sequence_monitor: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_sequence_monitor: %d check(s) failed\n", g_failures);
    return 1;
}
