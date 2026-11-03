// ui_layout.hpp — M19 unified layout system (8 px grid + fixed geometry).
//
// One source of truth for the page skeleton so the renderer and the host tests
// agree on every fixed coordinate.  The skeleton is:
//
//    +------------------------------------------------------+  y=0
//    | top status bar (system | mode | RUN/STOP | ctrl | .. )|  .. y=71
//    +------------------------------------------------------+  y=72 (divider)
//    |                                                      |
//    |  main content (page 1/2/3)                           |
//    |                                                      |
//    +------------------------------------------------------+  y=558 info strip
//    |  SNR / LATENCY / FRAME / SOURCE                       |  .. y=624
//    +------------------------------------------------------+  y=630
//    |  bottom nav CLASSIFY | PARAMETERS | MODE (>=64 px)    |  .. y=719
//    +------------------------------------------------------+
//
// The bottom-nav band and the info-strip band are FROZEN (they also drive
// board_package/touch_geometry.hpp kNavY0/kNavY1, and the M14/M16 layout).  The
// 8 px grid governs margins, paddings, and the NEW top status bar; it does NOT
// retro-fit the frozen 5/6 px legacy bands, so the board contract is unchanged.

#pragma once

#include <cstdint>

namespace ui::layout {

// ---- 8 px grid units (M19 spec: xs=4 / sm=8 / md=16 / lg=24 / xl=32) ----------
constexpr int kUnit = 8;
constexpr int kXs = 4;    // 0.5 unit
constexpr int kSm = 8;
constexpr int kMd = 16;
constexpr int kLg = 24;
constexpr int kXl = 32;

// ---- fixed page margins (1280x720 logical) -----------------------------------
constexpr int kMarginX = 24;    // left / right page gutter (= 3 * kUnit)
constexpr int kMarginY = 24;

constexpr int kScreenW = 1280;
constexpr int kScreenH = 720;

// ---- top status bar (new in M19) ---------------------------------------------
constexpr int kTopBarY0 = 0;
constexpr int kTopBarY1 = 71;    // inclusive; 1 px divider sits at y=72
constexpr int kTopBarDividerY = 72;

// Fixed, LEFT-anchored x positions so a change in one value's length never shifts
// any other element (no layout jump).  Worst-case strings are width-checked in
// host_tests/test_ui_layout_m19.cpp.
constexpr int kTopBarTitleX = 24;       // system / page title (28 px Bold)
constexpr int kTopBarModeLabelX = 312;  // "MODE" label (Regular 20 = 65 px, ends 377)
constexpr int kTopBarModeValueX = 392;  // FIXED / AUTO LOCK / BAND SCAN (grid 49*8)
constexpr int kTopBarRunX = 576;        // run dot + RUNNING / STOPPED
constexpr int kTopBarCtlLabelX = 752;   // "CTRL" label
constexpr int kTopBarCtlValueX = 820;   // CONNECTED / DISCONNECTED
constexpr int kTopBarModelRightX = 1130;// model short SHA (right-aligned)
constexpr int kTopBarBadgeRightX = 1255;// signal status badge (right-aligned)
constexpr int kTopBarDivider1X = 296;   // after title
constexpr int kTopBarDivider2X = 556;   // after mode
constexpr int kTopBarDivider3X = 736;   // after run

// ---- frozen bands ------------------------------------------------------------
constexpr int kInfoY0 = 558;
constexpr int kInfoY1 = 624;

constexpr int kNavY0 = 630;    // must equal ui_touch::kNavY0
constexpr int kNavY1 = 719;    // must equal ui_touch::kNavY1
constexpr int kNavTabCount = 3;

// ---- main content area (between top bar divider and info strip) --------------
constexpr int kContentY0 = 84;
constexpr int kContentY1 = 548;
constexpr int kContentX0 = 24;
constexpr int kContentX1 = 1256;   // = 1280 - 24

// ---- minimum screen size (M22.1 fail-closed gate) ---------------------------
// The top bar, info strip and bottom nav are FROZEN absolute bands tied to the
// passing touch geometry (kNavY0/Y1 == ui_touch::kNavY0/Y1), so the full layout
// requires a height >= 720 (nav bottom is 719) and a width >= 640 (three nav
// tabs plus their text).  Below either bound the renderer fail-closes: it draws a
// centered "screen too small" message instead of a layout that would overflow.
constexpr int kMinW = 640;
constexpr int kMinH = 720;

// ---- LayoutMetrics: the single runtime layout source -------------------------
// Everything the renderer and host tests need, derived from the actual screen
// size rather than scattered literals.  For the 1280x720 target this reproduces
// exactly the frozen band values above; the content-column widths adapt to w.
struct LayoutMetrics {
    int w = 0, h = 0;
    bool fit = false;          // false => screen too small; draw the fallback only
    int top_y0 = 0, top_y1 = 0;   // top status bar (inclusive)
    int divider_y = 0;
    int content_x0 = 0, content_x1 = 0;   // main content horizontal margins
    int content_y0 = 0, content_y1 = 0;   // main content vertical band
    int info_y0 = 0, info_y1 = 0;         // frozen info strip
    int nav_y0 = 0, nav_y1 = 0;           // frozen bottom nav
    int col_gap = 16;                     // gap between the two content columns
    int col_w = 0;                        // width of one content column
};

inline LayoutMetrics layout_metrics(int w, int h) {
    LayoutMetrics m;
    m.w = w;
    m.h = h;
    m.fit = (w >= kMinW && h >= kMinH);
    if (!m.fit) return m;
    m.top_y0 = kTopBarY0;
    m.top_y1 = kTopBarY1;
    m.divider_y = kTopBarDividerY;
    m.content_x0 = kMarginX;
    m.content_x1 = w - kMarginX;
    m.content_y0 = kContentY0;
    m.content_y1 = kContentY1;
    m.info_y0 = kInfoY0;
    m.info_y1 = kInfoY1;
    m.nav_y0 = kNavY0;
    m.nav_y1 = kNavY1;
    m.col_gap = 16;
    m.col_w = (m.content_x1 - m.content_x0 - m.col_gap) / 2;
    return m;
}

}  // namespace ui::layout
