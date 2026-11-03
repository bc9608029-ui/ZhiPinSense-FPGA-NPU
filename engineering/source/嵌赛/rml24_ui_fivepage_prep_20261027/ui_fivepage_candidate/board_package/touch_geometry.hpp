#pragma once

// touch_geometry.hpp — pure-logic touch mapping / hit-test / page-navigation
// state machine for the twelve-class LIVE UI (task 39e5 Gate C7).
//
// This header is iCraft-free, libiio-free and OS-free: it only turns raw touch
// coordinates into screen coordinates and decides which bottom-nav tab a tap hit,
// so the exact decision logic the board runs can be unit-tested on the host
// (host_tests/test_touch.cpp).  The evdev device access (touch_evdev.hpp) sits on
// top of this and feeds TouchNav::on_sample().
//
// Frozen contract (task 39e5 Gate C7):
//   * coordinate mapping supports swap-XY, invert-X and invert-Y, and clips every
//     result into [0, screen-1] (a malformed axis or out-of-range raw value can
//     never produce a coordinate outside the framebuffer);
//   * the bottom nav is the ONLY navigation target: 5 tabs
//     (CLASSIFY / MEASURE / WATERFALL / CONSTELLATION / SETUP)
//     spanning the full width at y in [630, 719] (90 raw px == the draw_nav band
//     in ui_render.cpp; the physical hit height is still >= 60 px after the 0.833x
//     panel scale);
//   * a page switch fires only on the UP edge of a contact whose DOWN point was in
//     the nav band, and consecutive taps within `debounce_ms` are folded, so a
//     noisy digitizer cannot flip pages back and forth;
//   * touch NEVER changes the class contract, the classification result, the TX
//     power, or the RF path — it only chooses which page is displayed.  The RF
//     safety gate (--confirm-safe-rf-path) is untouched by this module.

#include <cstdint>

namespace ui_touch {

// Bottom-nav geometry (must match draw_nav() in ui_render.cpp).
constexpr int kNavY0 = 630;   // inclusive
constexpr int kNavY1 = 719;   // inclusive
constexpr int kTabCount = 5;

struct AxisInfo {
    int min = 0;
    int max = 0;          // degenerate (max <= min) => axis unmapped
    bool invert = false;
};

struct TouchMapping {
    AxisInfo x;
    AxisInfo y;
    bool swap_xy = false;
    int screen_w = 1280;
    int screen_h = 720;
};

struct Point {
    int x = -1;
    int y = -1;
    bool valid = false;   // false when an axis is degenerate or the point is absent
};

// Map one raw axis value to [0, screen_size-1], clipped.  Returns -1 when the
// axis is degenerate (max <= min) or the screen size is non-positive.
inline int map_axis(int raw, const AxisInfo& a, int screen_size) {
    if (screen_size <= 0 || a.max <= a.min) return -1;
    long long v = (static_cast<long long>(raw) - a.min) *
                  (static_cast<long long>(screen_size) - 1) /
                  (static_cast<long long>(a.max) - a.min);
    if (a.invert) v = (static_cast<long long>(screen_size) - 1) - v;
    if (v < 0) v = 0;
    if (v >= screen_size) v = screen_size - 1;
    return static_cast<int>(v);
}

// Map a raw (x, y) pair to screen coordinates, applying swap-XY / invert-X /
// invert-Y and clipping.  Returns Point{valid=false} when either axis is
// degenerate or a screen dimension is non-positive.
inline Point map_point(int raw_x, int raw_y, const TouchMapping& m) {
    if (m.swap_xy) {
        const int t = raw_x;
        raw_x = raw_y;
        raw_y = t;
    }
    const int sx = map_axis(raw_x, m.x, m.screen_w);
    const int sy = map_axis(raw_y, m.y, m.screen_h);
    if (sx < 0 || sy < 0) return Point{};
    return Point{sx, sy, true};
}

// Bottom-nav hit test.  Returns the tab index 0..4, or -1 when the point is not
// inside the nav band.  Deterministic integer math (x * kTabCount / screen_w).
inline int nav_tab_from_point(int x, int y, int screen_w, int screen_h) {
    (void)screen_h;   // the nav band y-range is fixed by geometry
    if (x < 0 || x >= screen_w) return -1;
    if (y < kNavY0 || y > kNavY1) return -1;
    int tab = x * kTabCount / screen_w;
    if (tab < 0) tab = 0;
    if (tab >= kTabCount) tab = kTabCount - 1;
    return tab;
}

// Page-navigation + debounce state machine.
//
// Feed one sample per SYN_REPORT (a contact up/down transition or a move) with
// the monotonic `now_ms`.  A tap is recognised on the UP edge: the DOWN point
// (recorded at the last down edge) is hit-tested against the nav band, and if it
// lands on a tab, and enough time has passed since the previous tap, the active
// page changes.  Moves while pressed are ignored for navigation (they only update
// last_point(), which the Touch page can display).
class TouchNav {
public:
    TouchNav(int screen_w, int screen_h, std::int64_t debounce_ms = 400)
        : screen_w_(screen_w), screen_h_(screen_h), debounce_ms_(debounce_ms) {}

    void on_sample(bool touching, const Point& p, std::int64_t now_ms) {
        if (p.valid) last_point_ = p;
        if (touching && !was_touching_) {
            down_point_ = p;         // down edge: latch the tap origin
            down_ms_ = now_ms;
        } else if (!touching && was_touching_) {
            // up edge: a tap ends here.  The DOWN point decides the target, so a
            // finger that drags off the tab still counts as having tapped it.
            if (down_point_.valid && (now_ms - last_tap_ms_) >= debounce_ms_) {
                const int tab = nav_tab_from_point(down_point_.x, down_point_.y,
                                                   screen_w_, screen_h_);
                if (tab >= 0) {
                    active_page_ = tab;
                    ++tap_count_;
                    last_tap_ms_ = now_ms;
                }
            }
        }
        was_touching_ = touching;
    }

    int active_page() const { return active_page_; }
    std::uint64_t tap_count() const { return tap_count_; }
    const Point& last_point() const { return last_point_; }
    bool touching() const { return was_touching_; }

private:
    int screen_w_;
    int screen_h_;
    std::int64_t debounce_ms_;
    int active_page_ = 0;
    std::uint64_t tap_count_ = 0;
    bool was_touching_ = false;
    Point down_point_;          // tap origin (DOWN point), invalid until first down
    std::int64_t down_ms_ = 0;
    std::int64_t last_tap_ms_ = -1000000;   // far past => first tap always accepted
    Point last_point_;
};

}  // namespace ui_touch
