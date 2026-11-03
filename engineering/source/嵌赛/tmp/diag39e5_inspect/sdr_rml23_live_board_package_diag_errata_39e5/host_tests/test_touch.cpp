// test_touch.cpp -- host tests for the Gate C7 touch mapping + page-navigation
// state machine (task 39e5 §五/§六, touch_geometry.hpp).
//
// This file exercises the EXACT pure-logic code the board runs: coordinate mapping
// (swap-XY / invert-X / invert-Y / clip / degenerate-axis fail-closed), the
// bottom-nav hit test, and the tap/debounce state machine.  It needs no input
// device and no OS -- touch_geometry.hpp is iCraft-free, libiio-free and OS-free.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../board_package/touch_geometry.hpp"

#include <cstdio>

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s\n", what);
    }
}

// ---- map_axis --------------------------------------------------------------

void test_map_axis() {
    ui_touch::AxisInfo a;
    a.min = 0; a.max = 4095; a.invert = false;

    check(ui_touch::map_axis(0, a, 1280) == 0, "axis min -> 0");
    check(ui_touch::map_axis(4095, a, 1280) == 1279, "axis max -> screen-1");
    check(ui_touch::map_axis(2047, a, 1280) == 639, "axis mid -> screen/2");

    // invert maps min<->max.
    ui_touch::AxisInfo ai;
    ai.min = 0; ai.max = 4095; ai.invert = true;
    check(ui_touch::map_axis(0, ai, 1280) == 1279, "invert min -> screen-1");
    check(ui_touch::map_axis(4095, ai, 1280) == 0, "invert max -> 0");

    // clipping never lets a bogus raw value leave [0, screen-1].
    check(ui_touch::map_axis(-500, a, 1280) == 0, "clip low -> 0");
    check(ui_touch::map_axis(99999, a, 1280) == 1279, "clip high -> screen-1");

    // degenerate axis and non-positive screen fail closed.
    ui_touch::AxisInfo d;
    d.min = 5; d.max = 5;
    check(ui_touch::map_axis(0, d, 1280) == -1, "degenerate axis -> -1");
    check(ui_touch::map_axis(100, a, 0) == -1, "screen_size 0 -> -1");
    check(ui_touch::map_axis(100, a, -1) == -1, "screen_size negative -> -1");
}

// ---- map_point -------------------------------------------------------------

void test_map_point() {
    ui_touch::TouchMapping m;
    m.x = {0, 4095, false};
    m.y = {0, 4095, false};
    m.swap_xy = false;
    m.screen_w = 1280;
    m.screen_h = 720;

    ui_touch::Point p = ui_touch::map_point(0, 4095, m);
    check(p.valid && p.x == 0 && p.y == 719, "map_point (0,4095) -> (0,719)");

    // swap_xy exchanges the raw axes before mapping.
    m.swap_xy = true;
    p = ui_touch::map_point(4095, 0, m);
    check(p.valid && p.x == 0 && p.y == 719, "swap_xy (4095,0) -> (0,719)");

    // invert_x maps raw min to screen max.
    ui_touch::TouchMapping mi;
    mi.x = {0, 4095, true};
    mi.y = {0, 4095, false};
    mi.screen_w = 1280;
    mi.screen_h = 720;
    p = ui_touch::map_point(0, 0, mi);
    check(p.valid && p.x == 1279 && p.y == 0, "invert_x (0,0) -> (1279,0)");

    // a degenerate axis makes the whole point invalid.
    ui_touch::TouchMapping md;
    md.x = {0, 4095, false};
    md.y = {5, 5, false};
    md.screen_w = 1280;
    md.screen_h = 720;
    p = ui_touch::map_point(100, 100, md);
    check(!p.valid, "degenerate y -> invalid point");
}

// ---- nav_tab_from_point ----------------------------------------------------

void test_nav_tab() {
    const int W = 1280, H = 720;
    // Tab boundaries: tab = x * 3 / 1280, so 0=[0,426], 1=[427,853], 2=[854,1279].
    check(ui_touch::nav_tab_from_point(0, 700, W, H) == 0, "x=0 -> tab 0");
    check(ui_touch::nav_tab_from_point(426, 700, W, H) == 0, "x=426 -> tab 0");
    check(ui_touch::nav_tab_from_point(427, 700, W, H) == 1, "x=427 -> tab 1");
    check(ui_touch::nav_tab_from_point(853, 700, W, H) == 1, "x=853 -> tab 1");
    check(ui_touch::nav_tab_from_point(854, 700, W, H) == 2, "x=854 -> tab 2");
    check(ui_touch::nav_tab_from_point(1279, 700, W, H) == 2, "x=1279 -> tab 2");

    // nav band y in [630,719] inclusive.
    check(ui_touch::nav_tab_from_point(640, 630, W, H) == 1, "y=630 top edge -> valid");
    check(ui_touch::nav_tab_from_point(640, 719, W, H) == 1, "y=719 bottom edge -> valid");
    check(ui_touch::nav_tab_from_point(640, 629, W, H) == -1, "y=629 -> -1");
    check(ui_touch::nav_tab_from_point(640, 720, W, H) == -1, "y=720 -> -1");

    // out-of-range x.
    check(ui_touch::nav_tab_from_point(-1, 700, W, H) == -1, "x=-1 -> -1");
    check(ui_touch::nav_tab_from_point(1280, 700, W, H) == -1, "x=1280 -> -1");
}

// ---- TouchNav state machine -------------------------------------------------

void test_touch_nav() {
    const ui_touch::Point in_tab1{640, 700, true};   // tab 1 (x=640 -> 1)
    const ui_touch::Point in_tab2{1100, 700, true};  // tab 2 (x=1100 -> 2)
    const ui_touch::Point in_tab0{100, 700, true};   // tab 0 (x=100 -> 0)
    const ui_touch::Point above_nav{100, 100, true};
    const ui_touch::Point invalid{-1, -1, false};

    // Basic tap: page changes only on the UP edge; down edge just latches.
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        check(nav.active_page() == 0, "initial page 0");
        check(nav.tap_count() == 0, "initial tap_count 0");
        nav.on_sample(true, in_tab1, 1000);
        check(nav.active_page() == 0, "no switch on down edge");
        nav.on_sample(false, in_tab1, 1100);
        check(nav.active_page() == 1, "tap tab 1 -> page 1");
        check(nav.tap_count() == 1, "tap_count == 1");
    }

    // Debounce: a second tap within debounce_ms is folded.
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        nav.on_sample(true, in_tab1, 1000);
        nav.on_sample(false, in_tab1, 1050);   // page 1, last_tap_ms=1050
        nav.on_sample(true, in_tab2, 1100);
        nav.on_sample(false, in_tab2, 1120);   // 1120-1050=70 < 400
        check(nav.active_page() == 1, "debounced tap ignored -> still page 1");
        check(nav.tap_count() == 1, "debounced tap not counted");
    }

    // Debounce expiry: a later tap outside the window is accepted.
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        nav.on_sample(true, in_tab1, 1000);
        nav.on_sample(false, in_tab1, 1050);
        nav.on_sample(true, in_tab2, 2000);
        nav.on_sample(false, in_tab2, 2050);   // 2050-1050=1000 >= 400
        check(nav.active_page() == 2, "after debounce window -> page 2");
        check(nav.tap_count() == 2, "second tap counted");
    }

    // Drag off the tab still taps it (the DOWN point decides the target).
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        nav.on_sample(true, in_tab1, 1000);
        nav.on_sample(true, above_nav, 1100);  // drag off (still touching)
        nav.on_sample(false, above_nav, 1200); // up off-tab
        check(nav.active_page() == 1, "drag off-tab still taps tab 1 (down point)");
    }

    // A tap outside the nav band changes nothing.
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        nav.on_sample(true, above_nav, 1000);
        nav.on_sample(false, above_nav, 1100);
        check(nav.active_page() == 0, "non-nav tap -> no page change");
        check(nav.tap_count() == 0, "non-nav tap -> tap_count 0");
    }

    // An invalid down point cannot trigger a tap.
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        nav.on_sample(true, invalid, 1000);
        nav.on_sample(false, invalid, 1100);
        check(nav.active_page() == 0, "invalid down point -> no tap");
    }

    // Moves while pressed update last_point() but never the page.
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        nav.on_sample(true, ui_touch::Point{100, 100, true}, 1000);
        check(nav.last_point().valid && nav.last_point().x == 100 &&
                  nav.last_point().y == 100,
              "last_point tracks down point");
        nav.on_sample(true, ui_touch::Point{300, 400, true}, 1100);
        check(nav.last_point().x == 300 && nav.last_point().y == 400,
              "last_point updates on move");
        check(nav.active_page() == 0, "move alone -> no page change");
    }

    // Round-trip: page 2 -> 0 works, and tap_count keeps accumulating.
    {
        ui_touch::TouchNav nav(1280, 720, 400);
        nav.on_sample(true, in_tab2, 1000);
        nav.on_sample(false, in_tab2, 1050);
        check(nav.active_page() == 2, "tap tab 2 -> page 2");
        nav.on_sample(true, in_tab0, 2000);
        nav.on_sample(false, in_tab0, 2050);
        check(nav.active_page() == 0, "tap tab 0 -> back to page 0");
        check(nav.tap_count() == 2, "round-trip tap_count == 2");
    }
}

}  // namespace

int main() {
    std::printf("test_touch\n");
    test_map_axis();
    test_map_point();
    test_nav_tab();
    test_touch_nav();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
