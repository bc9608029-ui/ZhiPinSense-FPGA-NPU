// test_ui_scheduler.cpp -- host tests for the M17 event-driven flip scheduler
// (Task E / Task G): ui::display_changed() and ui::FlipScheduler.  Pure logic --
// no socket, no framebuffer, no device I/O.  These are the §12.2 UI-scheduler
// tests that pin down the idle-CPU + flicker fix on the host.
//
// What this proves:
//   * display_changed() reports false only when every render-relevant field is
//     bit-identical (so a steady feed never re-flips), and true on any real
//     change (status / top1 / conf / dist / mode / control / touch / meas);
//   * FlipScheduler flips on the first frame, skips an unchanged frame, flips on a
//     real change, and enforces a minimum flip interval even when content changes.

#include "../board_package/ui_dirty_state.hpp"

#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

ui::UiState base() {
    ui::UiState s;
    s.status = ui::Status::Live;
    s.top1 = "BPSK";
    s.conf = 0.93f;
    s.dist = {0.01f, 0.02f, 0.93f};
    s.work_mode = "FIXED";
    s.running = true;
    // `classes` is a render-time static pointer and is deliberately skipped by
    // display_changed(); leave it null so this stays a pure-logic test.
    return s;
}

void test_display_changed() {
    ui::UiState a = base();
    ui::UiState b = base();
    check(!ui::display_changed(a, b), "identical states -> not changed");

    b.status = ui::Status::Stale;
    check(ui::display_changed(a, b), "status change -> changed");
    b = a;

    b.top1 = "QPSK";
    check(ui::display_changed(a, b), "top1 change -> changed");
    b = a;

    b.conf = 0.94f;
    check(ui::display_changed(a, b), "conf (float) change -> changed");
    b = a;

    b.dist[2] = 0.92f;
    check(ui::display_changed(a, b), "dist vector change -> changed");
    b = a;

    b.work_mode = "AUTO LOCK";
    check(ui::display_changed(a, b), "work_mode change -> changed");
    b = a;

    b.control_taps = 1;
    check(ui::display_changed(a, b), "control_taps change -> changed");
    b = a;

    b.touch.connected = true;
    b.touch.taps = 1;
    check(ui::display_changed(a, b), "touch connected/taps change -> changed");
    b = a;

    b.meas.valid = true;
    b.meas.rms_counts = 1234.0;
    check(ui::display_changed(a, b), "meas field change -> changed");
    b = a;

    b.last_command = "SET_MODE FIXED";
    check(ui::display_changed(a, b), "last_command change -> changed");
    b = a;

    b.running = false;
    check(ui::display_changed(a, b), "running change -> changed");
}

void test_flip_scheduler() {
    ui::FlipScheduler sched(/*min_interval_ms=*/0);
    const ui::UiState s0 = base();

    // Nothing submitted yet -> first frame always flips.
    check(sched.should_submit(s0, 0, 1000), "first frame flips");
    sched.mark_submitted(s0, 0, 1000);
    check(sched.submits == 1, "submits == 1 after first frame");

    // Identical state + page -> skip (idle path: no re-flip).
    check(!sched.should_submit(s0, 0, 2000), "unchanged frame skips");
    check(sched.skips == 1, "skips == 1 after unchanged frame");

    // Page change alone -> flip.
    check(sched.should_submit(s0, 1, 3000), "page change flips");
    sched.mark_submitted(s0, 1, 3000);
    check(sched.submits == 2, "submits == 2 after page flip");

    // Real content change -> flip.
    ui::UiState s1 = base();
    s1.top1 = "16QAM";
    check(sched.should_submit(s1, 1, 4000), "content change flips");
    sched.mark_submitted(s1, 1, 4000);
    check(sched.submits == 3, "submits == 3 after content flip");

    // Min-interval pacing: a real change inside the interval is held back.
    ui::FlipScheduler paced(/*min_interval_ms=*/20);
    check(paced.should_submit(s0, 0, 1000), "paced: first frame flips");
    paced.mark_submitted(s0, 0, 1000);
    ui::UiState s2 = base();
    s2.top1 = "8PSK";
    check(!paced.should_submit(s2, 0, 1010), "paced: change inside interval held");
    check(paced.should_submit(s2, 0, 1021), "paced: change after interval flips");
}

}  // namespace

int main() {
    std::printf("test_ui_scheduler\n");
    test_display_changed();
    test_flip_scheduler();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
