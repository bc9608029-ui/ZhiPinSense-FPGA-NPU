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
constexpr int kTopBarModeLabelX = 312;  // "MODE" label
constexpr int kTopBarModeValueX = 372;  // FIXED / AUTO LOCK / BAND SCAN
constexpr int kTopBarRunX = 576;        // run dot + RUNNING / STOPPED
constexpr int kTopBarCtlLabelX = 752;   // "CTRL" label
constexpr int kTopBarCtlValueX = 820;   // CONNECTED / DISCONNECTED
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

// ---- M29 Task B: main-page hero + 23-class category table -------------------
// The hero is the single outlined card per page (first visual focus = top1 at
// 40 px; confidence = second tier at 28 px).  The category table is de-boxed:
// rows sit on the page background, the argmax row carries a surface_alt fill +
// a 4 px selected accent bar.  Left/right text anchors are fixed so worst-case
// strings never shift a neighbour (no layout jump).
constexpr int kHeroY0 = 84;
constexpr int kHeroY1 = 276;
constexpr int kHeroLabelY = 112;       // "RECOGNIZED SIGNAL" / "CONFIDENCE" (20 px)
constexpr int kHeroValueY = 196;       // top1 (40 px) / confidence value (28 px)
constexpr int kHeroConfBarX0 = 700;    // confidence bar (right column)
constexpr int kHeroConfBarY0 = 204;
constexpr int kHeroConfBarY1 = 240;
constexpr int kContentInsetX = 44;     // left text inset (24 gutter + 20 pad)
constexpr int kContentRightX = 1211;   // right text/bar anchor (1255 - 44)

constexpr int kCategoryHeaderY = 300;  // "CATEGORIES" baseline
constexpr int kCategoryRowsY0 = 320;   // first row top
constexpr int kCategoryRowH = 28;
constexpr int kCategoryRowPitch = 34;
constexpr int kCategoryRowsPerPage = 6;
constexpr int kCategoryFooterY = 540;  // "PAGE p/m" baseline
constexpr int kCategoryNameX = 84;     // class-name left anchor
constexpr int kCategoryBarX0 = 320;    // probability bar left/right
constexpr int kCategoryBarX1 = 1100;

}  // namespace ui::layout
