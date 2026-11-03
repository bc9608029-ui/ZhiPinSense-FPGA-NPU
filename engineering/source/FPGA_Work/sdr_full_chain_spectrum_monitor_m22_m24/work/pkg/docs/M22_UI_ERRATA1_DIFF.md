# M22.1 勘误 — 完整 diff 清单

生成时间: 2026-10-10 07:28 UTC

基线:
- 脚本基线: `dist/m22_runtime_fix_patch.tar.gz`（历史 M22 runtime 包）
- UI 基线:  `sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw/`（M19 基线）
- 当前树:   `work/pkg/`（M22.1 勘误后）

## 一、变更文件总表

| 文件 | 类型 | 说明 |
|---|---|---|
| scripts/m22_harness.sh | 修改 | 后台 PID 经 `printf -v` 返回调用者变量，修复 wait 非子进程错误 |
| scripts/run_m22_runtime_baseline.sh | 修改 | 同上（基线脚本） |
| scripts/run_m22_runtime_regression.sh | 修改 | 同上（回归脚本） |
| scripts/test_m22_harness_errata.sh | 新增 | 脚本进程管理回归测试（21/21 PASS） |
| ui_sw/font_atlas.hpp | 修改 | 新增 text_box()/draw_text_clipped()/文本 trace（真实字体度量） |
| ui_sw/font_atlas.cpp | 修改 | trace 实现 + 裁剪光栅化 |
| ui_sw/ui_layout.hpp | 修改 | LayoutMetrics 单一布局源 + 最小尺寸门禁 + 顶栏锚点修正 |
| ui_sw/ui_render.hpp | 修改 | region 容器枚举 + region_rect() 单一几何源 |
| ui_sw/ui_render.cpp | 修改 | 全量布局重构：裁剪保护/真实度量/长文本策略/列对齐 |
| host_tests/test_ui_layout_boundaries.cpp | 新增 | 布局边界回归测试（§五 12 项，2242 pass） |
| host_tests/make_ui_m22_1_snapshots.cpp | 新增 | 模拟预览快照（after + worst-case） |
| host_tests/build_host_tests.sh | 修改 | 增编两个新测试目标 |
| docs/M22_UI_LAYOUT_ERRATA.md | 新增 | UI 修改说明 |
| docs/M22_BOARD_RETEST.md | 新增 | 板端复测说明 |

## 二、完整 unified diff

### scripts/m22_harness.sh
```diff
--- /tmp/tmp.6Gs6mrDXY3/scripts/m22_harness.sh	2026-10-09 08:00:00.000000000 +0800
+++ scripts/m22_harness.sh	2026-10-10 14:37:06.000000000 +0800
@@ -29,14 +29,27 @@
     printf 'm22_%s_%s_%s\n' "$(date +%s)" "$$" "$RANDOM"
 }
 
-# run_gate9_captured <logfile> <bin> [args...] -> starts the Gate 9 binary in the
-# background with stdout+stderr captured into <logfile>, prints its PID on stdout.
-# The logfile is opened with > (truncate/create) so it holds ONLY this run's output.
+# run_gate9_captured <pidvar> <logfile> <bin> [args...] -> starts the Gate 9 binary
+# in the background as a DIRECT child of the calling shell, writes its PID into the
+# variable named by <pidvar>, and captures stdout+stderr into <logfile>.  The logfile
+# is opened with > (truncate/create) so it holds ONLY this run's output.
+#
+# The PID is returned via `printf -v` into a CALLER-NAMED variable, NOT via command
+# substitution.  The old form (`PID="$(run_gate9_captured ...)"`) ran this function
+# in a command-substitution subshell, so the background job was the subshell's child;
+# the subshell exited immediately, the job was re-parented to init, and a later
+# `wait "$PID"` in the real shell failed with:
+#
+#     wait: pid <n> is not a child of this shell
+#
+# With `printf -v` the background job is started by THIS shell (the one that later
+# runs `wait`), so `wait` owns it and reads its true exit code.  This is the M22.1
+# harness errata (task 39e5 §三).
 run_gate9_captured() {
-    local logfile="$1" bin="$2"
-    shift 2
+    local pidvar="$1" logfile="$2" bin="$3"
+    shift 3
     "$bin" "$@" >"$logfile" 2>&1 &
-    printf '%s\n' "$!"
+    printf -v "$pidvar" '%s' "$!"
 }
 
 # m22_result_line <logfile> -> prints the LAST M22_RUNTIME_RESULT line (empty if the
```

### scripts/run_m22_runtime_baseline.sh
```diff
--- /tmp/tmp.6Gs6mrDXY3/scripts/run_m22_runtime_baseline.sh	2026-10-09 08:00:00.000000000 +0800
+++ scripts/run_m22_runtime_baseline.sh	2026-10-10 14:37:20.000000000 +0800
@@ -70,7 +70,10 @@
 
     # Start THIS run's binary against a FRESH log + perf file (both created/truncated
     # by the redirections and --perf-file below, so an old run can never leak in).
-    PROD_PID="$(run_gate9_captured "$LOG" "$BIN" \
+    # The PID is returned via a caller-named variable (NOT command substitution), so
+    # the background job is a DIRECT child of THIS shell and `wait` below owns it
+    # (M22.1 harness errata).
+    run_gate9_captured PROD_PID "$LOG" "$BIN" \
         --model-json="$MODEL_JSON" \
         --model-raw="$MODEL_RAW" \
         --model-sha="$MODEL_RAW_SHA" \
@@ -80,7 +83,7 @@
         --rx-gain="$RX_GAIN" \
         --rec-scale="$REC_SCALE" \
         --summary-interval="$SUMMARY_INTERVAL" \
-        --perf-file="$PERF")"
+        --perf-file="$PERF"
     echo "M22_RUNTIME_BASELINE_STEP running pid=$PROD_PID"
 
     # Wait for the binary to exit on its own.  Capture the exit code WITHOUT letting
```

### scripts/run_m22_runtime_regression.sh
```diff
--- /tmp/tmp.6Gs6mrDXY3/scripts/run_m22_runtime_regression.sh	2026-10-09 08:00:00.000000000 +0800
+++ scripts/run_m22_runtime_regression.sh	2026-10-10 14:37:12.000000000 +0800
@@ -64,8 +64,10 @@
     banner "M22 §六 runtime regression (phase=$PHASE count=$COUNT run_id=$RUN_ID)"
     echo "M22_RUNTIME_REGRESSION_STEP start run_id=$RUN_ID count=$COUNT phase=$PHASE"
 
-    # Start THIS run's binary against a FRESH log + perf file.
-    PROD_PID="$(run_gate9_captured "$LOG" "$BIN" \
+    # Start THIS run's binary against a FRESH log + perf file.  The PID is returned
+    # via a caller-named variable (NOT command substitution), so the background job
+    # is a DIRECT child of THIS shell and `wait` below owns it (M22.1 harness errata).
+    run_gate9_captured PROD_PID "$LOG" "$BIN" \
         --model-json="$MODEL_JSON" \
         --model-raw="$MODEL_RAW" \
         --model-sha="$MODEL_RAW_SHA" \
@@ -73,7 +75,7 @@
         --phase="$PHASE" \
         --count="$COUNT" \
         --min-match-rate="$MIN_MATCH_RATE" \
-        --perf-file="$PERF")"
+        --perf-file="$PERF"
     echo "M22_RUNTIME_REGRESSION_STEP running pid=$PROD_PID"
 
     local rc=0
```

### ui_sw/font_atlas.hpp
```diff
--- ../../../sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw/font_atlas.hpp	2026-10-08 08:00:00.000000000 +0800
+++ ui_sw/font_atlas.hpp	2026-10-10 14:48:10.000000000 +0800
@@ -9,11 +9,20 @@
 //
 // Charset = printable ASCII 32..126 (95 glyphs).  For each glyph the bitmap width
 // equals its advance, so only {offset, advance} is stored (height = font line_h).
+//
+// M22.1 (UI 视觉重构): this header also exposes (a) text_box(), which derives a
+// text run's bounding box from the font's REAL metrics (ascent/descent/advance)
+// rather than any hardcoded width, and (b) draw_text_clipped(), which rasterizes
+// only the pixels inside an explicit clip rect so no string can paint outside its
+// card/button/screen, plus (c) an optional text TRACE that records every drawn
+// run's intended bounding box so host tests can prove containment / non-overlap
+// with the same metrics the renderer used to position the text.
 
 #pragma once
 
 #include <cstdint>
 #include <string>
+#include <vector>
 
 namespace ui {
 
@@ -51,15 +60,54 @@
 // Advance width of `s` at the given font, in px.
 int text_width(const std::string& s, const font_t* f, int spacing = 0);
 
+// Inclusive bounding box of a text run whose baseline is at (x, y).  The y span is
+// [y-ascent, y+descent] and the x span is [x, x+width-1] — both from the font's
+// real metrics, never a guessed width.
+struct TextBox { int x0 = 0, y0 = 0, x1 = 0, y1 = 0; };
+TextBox text_box(const std::string& s, int x, int y, const font_t* f, int spacing = 0);
+
 // Draw `s` with the baseline at (x, y), using RGB565 integer alpha blend.
 // Returns the x position after the last glyph.  Out-of-range chars render as space.
 int draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
               const font_t* f, int spacing = 0);
 
+// Draw `s` with the baseline at (x, y), rasterizing ONLY the pixels inside the
+// inclusive clip rect [cx0,cy0]-[cx1,cy1].  Returns the un-clipped advance x, so
+// callers can chain runs.  This is the overflow safety net: a string that (for any
+// reason) would exceed its card is silently cut at the card edge instead of
+// painting over a neighbouring region.
+int draw_text_clipped(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
+                      const font_t* f, int cx0, int cy0, int cx1, int cy1, int spacing = 0);
+
 // Right-aligned / center-aligned variants (x_right / xc are the anchor x).
 void draw_text_right(Canvas& c, const std::string& s, int x_right, int y,
                      std::uint16_t color, const font_t* f, int spacing = 0);
 void draw_text_center(Canvas& c, const std::string& s, int xc, int y,
                       std::uint16_t color, const font_t* f, int spacing = 0);
 
+// ---- text trace (host-test introspection; zero cost on the board) ----------
+// When a sink is installed, every draw_text / draw_text_clipped / draw_text_right
+// / draw_text_center call appends the run's INTENDED (un-clipped) bounding box,
+// tagged with the current region and kind.  Recording the un-clipped box is
+// deliberate: a test must prove the renderer POSITIONED the text inside its
+// container, not merely that clipping hid an overflow.  On the board no sink is
+// ever installed, so the cost is a single null-pointer check per draw call.
+enum class TextKind : int { Other = 0, Title = 1, Label = 2, Value = 3, Unit = 4 };
+
+struct TracedText {
+    std::string text;
+    int x0 = 0, y0 = 0, x1 = 0, y1 = 0;   // intended bbox (inclusive)
+    int size = 0;                         // font size in px
+    int region = 0;                       // renderer-assigned container id
+    int kind = 0;                         // TextKind
+};
+
+// Install `sink` and return the previously-installed sink (or nullptr).
+std::vector<TracedText>* text_trace_begin(std::vector<TracedText>* sink);
+// Restore a sink previously returned by text_trace_begin.
+void text_trace_end(std::vector<TracedText>* prev);
+// Tag subsequent draw calls with a container region / text kind.
+void text_trace_set_region(int region);
+void text_trace_set_kind(TextKind kind);
+
 } // namespace ui
```

### ui_sw/font_atlas.cpp
```diff
--- ../../../sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw/font_atlas.cpp	2026-10-08 08:00:00.000000000 +0800
+++ ui_sw/font_atlas.cpp	2026-10-10 14:48:30.000000000 +0800
@@ -2,7 +2,8 @@
 //
 // The glyph data lives in the GENERATED font_atlas_data.cpp (see
 // design_mockups/tools/gen_font_atlas.py).  This file only implements the blend
-// math and text layout, mirroring the PC design-draft renderer exactly:
+// math, text layout, clipping and the M22.1 text trace, mirroring the PC
+// design-draft renderer exactly:
 //   out = (dst*(255-a) + fg*a + 127) >> 8   per 8-bit channel, RGB565.
 
 #include "font_atlas.hpp"
@@ -41,6 +42,25 @@
     return &f->glyphs[0];   // out-of-range -> space
 }
 
+// ---- text trace state -----------------------------------------------------
+std::vector<TracedText>* g_trace = nullptr;
+int g_region = 0;
+TextKind g_kind = TextKind::Other;
+
+void trace(const std::string& s, int x, int y, const font_t* f) {
+    if (!g_trace) return;
+    TracedText t;
+    t.text = s;
+    t.x0 = x;
+    t.x1 = x + text_width(s, f, 0) - 1;
+    t.y0 = y - static_cast<int>(f->ascent);
+    t.y1 = y + static_cast<int>(f->descent);
+    t.size = f->size;
+    t.region = g_region;
+    t.kind = static_cast<int>(g_kind);
+    g_trace->push_back(std::move(t));
+}
+
 } // namespace
 
 int text_width(const std::string& s, const font_t* f, int spacing) {
@@ -50,8 +70,19 @@
     return w;
 }
 
-int draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
-              const font_t* f, int spacing) {
+TextBox text_box(const std::string& s, int x, int y, const font_t* f, int spacing) {
+    TextBox b;
+    b.x0 = x;
+    b.x1 = x + text_width(s, f, spacing) - 1;
+    b.y0 = y - static_cast<int>(f->ascent);
+    b.y1 = y + static_cast<int>(f->descent);
+    return b;
+}
+
+int draw_text_clipped(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
+                      const font_t* f, int cx0, int cy0, int cx1, int cy1, int spacing) {
+    trace(s, x, y, f);   // record the INTENDED bbox (before clipping)
+
     int fr, fg, fb;
     unpack565(color, fr, fg, fb);
 
@@ -66,6 +97,7 @@
         for (int gy = 0; gy < gw; ++gy) {
             const int cy = ty + gy;
             if (cy < 0 || cy >= c.h) continue;
+            if (cy < cy0 || cy > cy1) continue;
             const std::uint8_t* row = cov + gy * adv;
             const int row_base = cy * c.w;
             for (int gx = 0; gx < adv; ++gx) {
@@ -73,6 +105,7 @@
                 if (a == 0) continue;
                 const int cx = tx + gx;
                 if (cx < 0 || cx >= c.w) continue;
+                if (cx < cx0 || cx > cx1) continue;
                 const int ci = row_base + cx;
                 if (a == 255) { c.px[ci] = color; continue; }
                 c.px[ci] = blend_px(c.px[ci], fr, fg, fb, a);
@@ -83,6 +116,11 @@
     return px;
 }
 
+int draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color,
+              const font_t* f, int spacing) {
+    return draw_text_clipped(c, s, x, y, color, f, 0, 0, c.w - 1, c.h - 1, spacing);
+}
+
 void draw_text_right(Canvas& c, const std::string& s, int x_right, int y,
                      std::uint16_t color, const font_t* f, int spacing) {
     const int w = text_width(s, f, spacing);
@@ -95,4 +133,22 @@
     draw_text(c, s, xc - w / 2, y, color, f, spacing);
 }
 
+std::vector<TracedText>* text_trace_begin(std::vector<TracedText>* sink) {
+    std::vector<TracedText>* prev = g_trace;
+    g_trace = sink;
+    return prev;
+}
+
+void text_trace_end(std::vector<TracedText>* prev) {
+    g_trace = prev;
+}
+
+void text_trace_set_region(int region) {
+    g_region = region;
+}
+
+void text_trace_set_kind(TextKind kind) {
+    g_kind = kind;
+}
+
 } // namespace ui
```

### ui_sw/ui_layout.hpp
```diff
--- ../../../sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw/ui_layout.hpp	2026-10-08 17:23:30.000000000 +0800
+++ ui_sw/ui_layout.hpp	2026-10-10 15:18:40.000000000 +0800
@@ -50,8 +50,8 @@
 // any other element (no layout jump).  Worst-case strings are width-checked in
 // host_tests/test_ui_layout_m19.cpp.
 constexpr int kTopBarTitleX = 24;       // system / page title (28 px Bold)
-constexpr int kTopBarModeLabelX = 312;  // "MODE" label
-constexpr int kTopBarModeValueX = 372;  // FIXED / AUTO LOCK / BAND SCAN
+constexpr int kTopBarModeLabelX = 312;  // "MODE" label (Regular 20 = 65 px, ends 377)
+constexpr int kTopBarModeValueX = 392;  // FIXED / AUTO LOCK / BAND SCAN (grid 49*8)
 constexpr int kTopBarRunX = 576;        // run dot + RUNNING / STOPPED
 constexpr int kTopBarCtlLabelX = 752;   // "CTRL" label
 constexpr int kTopBarCtlValueX = 820;   // CONNECTED / DISCONNECTED
@@ -75,4 +75,52 @@
 constexpr int kContentX0 = 24;
 constexpr int kContentX1 = 1256;   // = 1280 - 24
 
+// ---- minimum screen size (M22.1 fail-closed gate) ---------------------------
+// The top bar, info strip and bottom nav are FROZEN absolute bands tied to the
+// passing touch geometry (kNavY0/Y1 == ui_touch::kNavY0/Y1), so the full layout
+// requires a height >= 720 (nav bottom is 719) and a width >= 640 (three nav
+// tabs plus their text).  Below either bound the renderer fail-closes: it draws a
+// centered "screen too small" message instead of a layout that would overflow.
+constexpr int kMinW = 640;
+constexpr int kMinH = 720;
+
+// ---- LayoutMetrics: the single runtime layout source -------------------------
+// Everything the renderer and host tests need, derived from the actual screen
+// size rather than scattered literals.  For the 1280x720 target this reproduces
+// exactly the frozen band values above; the content-column widths adapt to w.
+struct LayoutMetrics {
+    int w = 0, h = 0;
+    bool fit = false;          // false => screen too small; draw the fallback only
+    int top_y0 = 0, top_y1 = 0;   // top status bar (inclusive)
+    int divider_y = 0;
+    int content_x0 = 0, content_x1 = 0;   // main content horizontal margins
+    int content_y0 = 0, content_y1 = 0;   // main content vertical band
+    int info_y0 = 0, info_y1 = 0;         // frozen info strip
+    int nav_y0 = 0, nav_y1 = 0;           // frozen bottom nav
+    int col_gap = 16;                     // gap between the two content columns
+    int col_w = 0;                        // width of one content column
+};
+
+inline LayoutMetrics layout_metrics(int w, int h) {
+    LayoutMetrics m;
+    m.w = w;
+    m.h = h;
+    m.fit = (w >= kMinW && h >= kMinH);
+    if (!m.fit) return m;
+    m.top_y0 = kTopBarY0;
+    m.top_y1 = kTopBarY1;
+    m.divider_y = kTopBarDividerY;
+    m.content_x0 = kMarginX;
+    m.content_x1 = w - kMarginX;
+    m.content_y0 = kContentY0;
+    m.content_y1 = kContentY1;
+    m.info_y0 = kInfoY0;
+    m.info_y1 = kInfoY1;
+    m.nav_y0 = kNavY0;
+    m.nav_y1 = kNavY1;
+    m.col_gap = 16;
+    m.col_w = (m.content_x1 - m.content_x0 - m.col_gap) / 2;
+    return m;
+}
+
 }  // namespace ui::layout
```

### ui_sw/ui_render.hpp
```diff
--- ../../../sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw/ui_render.hpp	2026-10-08 17:27:00.000000000 +0800
+++ ui_sw/ui_render.hpp	2026-10-10 14:48:54.000000000 +0800
@@ -19,10 +19,43 @@
 #include <vector>
 
 #include "font_atlas.hpp"
+#include "ui_layout.hpp"
 #include "ui_theme.hpp"
 
 namespace ui {
 
+// ---- M22.1 container regions (single source for renderer + host tests) -----
+// Each region is a logical container the renderer draws into.  The renderer tags
+// every text run with its region (via text_trace_set_region) and derives each
+// container's rectangle from region_rect(), so a host test can assert "every text
+// fits inside its container" and "no two texts in one container overlap" using
+// exactly the geometry the renderer used.
+namespace region {
+enum : int {
+    kFallback = 0,      // centered "screen too small" message
+    kTopBar,            // top status bar
+    kResultCard,        // MAIN: the top result card
+    kTopClasses,        // MAIN: the Top-3 list area
+    kInfoStrip,         // frozen SNR/LATENCY/FRAME/SOURCE strip
+    kNav,               // frozen bottom nav (3 tabs)
+    kSignalLevel,       // PARAMETERS: top-left card
+    kSpectrum,          // PARAMETERS: top-right card
+    kSignalQuality,     // PARAMETERS: bottom-left card
+    kRfConfig,          // PARAMETERS: bottom-right card
+    kModeBtn0, kModeBtn1, kModeBtn2,   // MODE: the three mode buttons
+    kRunStart, kRunStop,                // MODE: START / STOP
+    kDetailCard,        // MODE: detail card
+    kDiagLeft, kDiagRight,              // DIAGNOSTICS: two cards
+    kTouchLeft, kTouchRight,            // TOUCH TEST: two cards
+    kCount
+};
+}  // namespace region
+
+// Container rectangle (inclusive) for a region at the given layout metrics.
+// Returns false when the region has no rect (only kFallback when !fit).
+bool region_rect(int region, const layout::LayoutMetrics& lm,
+                 int& x0, int& y0, int& x1, int& y1);
+
 enum class Status { Live, Stale, Error, Mock };
 
 // Touch-test page state (Gate C7).  Filled by the board server from the evdev
```

### ui_sw/ui_render.cpp
```diff
--- ../../../sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw/ui_render.cpp	2026-10-08 17:36:34.000000000 +0800
+++ ui_sw/ui_render.cpp	2026-10-10 15:18:58.000000000 +0800
@@ -5,14 +5,19 @@
 // semantic theme (ui_theme.hpp) and an 8 px grid (ui_layout.hpp).  No shadows /
 // blur / gradients / translucent layers; no runtime glyph scaling; status is
 // always text + shape + color.
+//
+// M22.1 (UI 视觉重构): every text run is now (a) positioned from the font's real
+// metrics via text_box()/text_width(), (b) rasterized through draw_text_clipped()
+// so nothing can paint outside its card/button, and (c) tagged with a container
+// region (region::*) that the host boundary test re-checks.  All card geometry is
+// derived from layout::layout_metrics(c.w, c.h) — one adaptive source — and a too
+// small screen fail-closes to a centered message instead of overflowing.
 
 #include "ui_render.hpp"
 
 #include <algorithm>
 #include <cstdio>
 
-#include "ui_layout.hpp"
-
 namespace ui {
 
 namespace {
@@ -88,6 +93,43 @@
     else        fill_rect(c, cx - r, cy - r, cx + r, cy + r, color);
 }
 
+// ---- M22.1 draw helpers: tag region + kind, then draw (optionally clipped) --
+int dr(Canvas& c, const std::string& s, int x, int y, std::uint16_t col, const font_t* f,
+       int region, TextKind kind, const int* clip = nullptr) {
+    text_trace_set_region(region);
+    text_trace_set_kind(kind);
+    if (clip) return draw_text_clipped(c, s, x, y, col, f, clip[0], clip[1], clip[2], clip[3]);
+    return draw_text(c, s, x, y, col, f);
+}
+int drr(Canvas& c, const std::string& s, int x_right, int y, std::uint16_t col, const font_t* f,
+        int region, TextKind kind, const int* clip = nullptr) {
+    return dr(c, s, x_right - text_width(s, f), y, col, f, region, kind, clip);
+}
+int drc(Canvas& c, const std::string& s, int xc, int y, std::uint16_t col, const font_t* f,
+        int region, TextKind kind, const int* clip = nullptr) {
+    return dr(c, s, xc - text_width(s, f) / 2, y, col, f, region, kind, clip);
+}
+
+// Shorten `s` to at most `max_px` pixels at font `f`, appending a trailing "..."
+// when anything is cut (spec §四.2 long-text strategy: 缩短/省略).  Returns the
+// original string unchanged when it already fits, and "" when even "..." cannot.
+std::string fit_text(const std::string& s, const font_t* f, int max_px) {
+    if (text_width(s, f) <= max_px) return s;
+    if (max_px <= 0) return std::string();
+    const std::string ell = "...";
+    const int ell_w = text_width(ell, f);
+    if (ell_w > max_px) return std::string();
+    std::string out;
+    int w = 0;
+    for (char ch : s) {
+        const int cw = text_width(std::string(1, ch), f);
+        if (w + cw + ell_w > max_px) break;
+        w += cw;
+        out += ch;
+    }
+    return out + ell;
+}
+
 // ---- status ---------------------------------------------------------------
 // Signal-status color: LIVE=green, STALE=amber, ERROR=red, MOCK=blue.  Mock is
 // deliberately blue (distinct from the three data states AND from idle text).
@@ -101,9 +143,6 @@
 }
 
 // ---- status badge: text + shape + color (never color alone) ----------------
-// The shape (icon) is drawn >=10px LEFT of the right-aligned status text, so it
-// never covers the LIVE/STALE/ERROR/MOCK label.  Geometry comes from
-// status_badge_shape_cx() (single source of truth, shared with the host test).
 void draw_status_badge(Canvas& c, const Theme& th, Status st, int x_right, int yc) {
     const std::uint16_t col = status_color(th, st);
     const int cx = status_badge_shape_cx(st, x_right);
@@ -128,52 +167,58 @@
 }
 
 // ---- top status bar (M19 unified skeleton) ---------------------------------
-// [ system/page title | MODE value | run-dot RUNNING/STOPPED | CTRL state | .. ]
-// Left-anchored fixed x positions => a change in one value's length never shifts
-// another element (no layout jump).  Model short SHA + signal status badge sit
-// right-aligned.
 void draw_top_bar(Canvas& c, const Theme& th, const char* title, const UiState& st) {
-    fill_rect(c, 0, layout::kTopBarY0, c.w - 1, layout::kTopBarY1, th.surface);
-    fill_rect(c, 0, layout::kTopBarDividerY, c.w - 1, layout::kTopBarDividerY, th.outline);
+    using namespace layout;
+    const int R = region::kTopBar;
+    fill_rect(c, 0, kTopBarY0, c.w - 1, kTopBarY1, th.surface);
+    fill_rect(c, 0, kTopBarDividerY, c.w - 1, kTopBarDividerY, th.outline);
+    const int clip[4] = {0, kTopBarY0, c.w - 1, kTopBarY1};
 
-    draw_text(c, title, layout::kTopBarTitleX, 44, th.text_primary, fb(font_tier::kTitle));
+    dr(c, title, kTopBarTitleX, 44, th.text_primary, fb(font_tier::kTitle), R, TextKind::Title, clip);
 
     // vertical dividers
-    fill_rect(c, layout::kTopBarDivider1X, 16, layout::kTopBarDivider1X, 55, th.outline);
-    fill_rect(c, layout::kTopBarDivider2X, 16, layout::kTopBarDivider2X, 55, th.outline);
-    fill_rect(c, layout::kTopBarDivider3X, 16, layout::kTopBarDivider3X, 55, th.outline);
+    fill_rect(c, kTopBarDivider1X, 16, kTopBarDivider1X, 55, th.outline);
+    fill_rect(c, kTopBarDivider2X, 16, kTopBarDivider2X, 55, th.outline);
+    fill_rect(c, kTopBarDivider3X, 16, kTopBarDivider3X, 55, th.outline);
 
     // mode
-    draw_text(c, "MODE", layout::kTopBarModeLabelX, 36, th.text_secondary,
-              fr(font_tier::kLabel));
-    draw_text(c, st.work_mode, layout::kTopBarModeValueX, 36, th.interactive,
-              fb(font_tier::kValue));
+    dr(c, "MODE", kTopBarModeLabelX, 36, th.text_secondary, fr(font_tier::kLabel),
+       R, TextKind::Label, clip);
+    dr(c, st.work_mode, kTopBarModeValueX, 36, th.interactive, fb(font_tier::kValue),
+       R, TextKind::Value, clip);
 
     // run state (dot + text; never color alone)
     const std::uint16_t run_col = st.running ? th.success : th.warning;
-    fill_circle(c, layout::kTopBarRunX - 8, 36, 5, run_col);
-    draw_text(c, st.running ? "RUNNING" : "STOPPED", layout::kTopBarRunX, 36, run_col,
-              fb(font_tier::kValue));
+    fill_circle(c, kTopBarRunX - 8, 36, 5, run_col);
+    dr(c, st.running ? "RUNNING" : "STOPPED", kTopBarRunX, 36, run_col, fb(font_tier::kValue),
+       R, TextKind::Value, clip);
 
     // control connection
     const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
-    draw_text(c, "CTRL", layout::kTopBarCtlLabelX, 36, th.text_secondary,
-              fr(font_tier::kLabel));
-    draw_text(c, ctl_ok ? "CONNECTED" : "DISCONNECTED", layout::kTopBarCtlValueX, 36,
-              ctl_ok ? th.success : th.warning, fb(font_tier::kValue));
+    dr(c, "CTRL", kTopBarCtlLabelX, 36, th.text_secondary, fr(font_tier::kLabel),
+       R, TextKind::Label, clip);
+    dr(c, ctl_ok ? "CONNECTED" : "DISCONNECTED", kTopBarCtlValueX, 36,
+       ctl_ok ? th.success : th.warning, fb(font_tier::kValue), R, TextKind::Value, clip);
 
-    // model short SHA (provenance; drawn only when set)
+    // model short SHA (provenance; drawn only when set; shortened to the first 8
+    // hex chars so an over-long model string can never reach the ctrl value).
     if (!st.model.empty()) {
-        draw_text_right(c, st.model, layout::kTopBarModelRightX, 36, th.text_secondary,
-                        fm(font_tier::kValue));
+        const std::string m = st.model.size() > 8 ? st.model.substr(0, 8) : st.model;
+        drr(c, m, kTopBarModelRightX, 36, th.text_secondary, fm(font_tier::kValue),
+            R, TextKind::Value, clip);
     }
     // signal status badge
-    draw_status_badge(c, th, st.status, layout::kTopBarBadgeRightX, 36);
+    text_trace_set_region(R);
+    draw_status_badge(c, th, st.status, kTopBarBadgeRightX, 36);
 }
 
 // ---- info strip (SNR / latency / frame / source) --------------------------
+// Two lines per field; baselines are separated by the font's real ascent+descent
+// so the 20px label and the 28px value can never overlap (M22.1).
 void draw_info_strip(Canvas& c, const Theme& th, const UiState& st) {
-    const int y0 = layout::kInfoY0, y1 = layout::kInfoY1;
+    using namespace layout;
+    const int R = region::kInfoStrip;
+    const int y0 = kInfoY0, y1 = kInfoY1;
     fill_rect(c, 25, y0, 1255, y1, th.surface_alt);
     outline_rect(c, 25, y0, 1255, y1, th.outline, 1);
     const struct { const char* k; const std::string* v; } items[4] = {
@@ -181,16 +226,26 @@
     };
     const int seg = 1230 / 4;
     int x = 45;
+    const font_t* lbl = fr(font_tier::kLabel);
+    const font_t* val = fb(font_tier::kTitle);
     for (const auto& it : items) {
-        draw_text(c, it.k, x, y0 + 26, th.text_secondary, fr(font_tier::kLabel));
-        draw_text(c, *it.v, x, y0 + 54, th.text_primary, fb(font_tier::kTitle));
+        // Each field clips to its own segment (the last field also to the strip's
+        // right edge), and a too-long value is shortened so it can never overflow
+        // the strip or reach the next field.
+        const int avail = std::min(seg - 12, 1255 - x);
+        const int clip_f[4] = {x, y0, x + avail, y1};
+        dr(c, it.k, x, y0 + 22, th.text_secondary, lbl, R, TextKind::Label, clip_f);
+        dr(c, fit_text(*it.v, val, avail), x, y0 + 56, th.text_primary, val,
+           R, TextKind::Value, clip_f);
         x += seg;
     }
 }
 
 // ---- bottom touch nav (90px raw -> 75px physical; hit >= 60px physical) ----
 void draw_nav(Canvas& c, const Theme& th, int active) {
-    const int y0 = layout::kNavY0, y1 = layout::kNavY1;
+    using namespace layout;
+    const int R = region::kNav;
+    const int y0 = kNavY0, y1 = kNavY1;
     fill_rect(c, 0, y0, c.w - 1, y1, th.surface);
     outline_rect(c, 0, y0, c.w - 1, y0, th.outline, 1);   // top edge only
     const char* tabs[3] = {"CLASSIFY", "PARAMETERS", "MODE"};
@@ -198,14 +253,17 @@
     const font_t* b = fb(font_tier::kButton);
     for (int i = 0; i < 3; ++i) {
         const int x0 = i * tw;
+        const int x1 = x0 + tw - 1;
         const bool on = (i == active);
-        if (on) fill_rect(c, x0 + 10, y0 + 8, x0 + tw - 10, y1 - 8, th.surface_alt);
+        if (on) fill_rect(c, x0 + 10, y0 + 8, x1 - 10, y1 - 8, th.surface_alt);
         const int shape_cx = x0 + 34, shape_cy = y0 + 45;
         const std::uint16_t scol = on ? th.selected : th.text_secondary;
         if (i == 0)      fill_square(c, shape_cx, shape_cy, 9, scol, false);
         else if (i == 1) fill_circle(c, shape_cx, shape_cy, 9, scol);
         else             fill_diamond(c, shape_cx, shape_cy, 9, scol);
-        draw_text(c, tabs[i], x0 + 58, y0 + 60, on ? th.selected : th.text_primary, b);
+        const int clip[4] = {x0 + 54, y0 + 4, x1 - 10, y1 - 4};
+        dr(c, tabs[i], x0 + 58, y0 + 60, on ? th.selected : th.text_primary, b,
+           R, TextKind::Title, clip);
     }
 }
 
@@ -216,17 +274,23 @@
     return std::string(b);
 }
 
-// Draw one key/value row: label left (fixed), value right-aligned (fixed),
-// unit left-anchored after the value (fixed).  All three anchor x are constant,
-// so a value whose length changes never shifts the label or the unit (no layout
-// jump).  Unknown values render as "--" (the baked atlas is ASCII 32..126, so the
-// em dash is approximated by a double hyphen), never a fake 0.
+// ---- PARAMETERS key/value row with measured, aligned, clipped columns ------
+// x_label: label left anchor.  x_val: value RIGHT anchor (all values share it, so
+// the value column is right-aligned).  x_unit: unit LEFT anchor (all units share
+// it, so the unit column is left-aligned).  x_val < x_unit guarantees the value
+// column can never reach the unit column.
 void draw_kv_row(Canvas& c, const Theme& th, int x_label, int x_val, int x_unit, int y,
-                 const char* label, const std::string& value, const char* unit) {
-    draw_text(c, label, x_label, y, th.text_secondary, fr(font_tier::kLabel));
-    draw_text_right(c, value, x_val, y, th.text_primary, fm(font_tier::kValue));
+                 const char* label, const std::string& value, const char* unit,
+                 int region, const int* card_clip) {
+    const font_t* r20 = fr(font_tier::kLabel);
+    const font_t* m20 = fm(font_tier::kValue);
+    const int clip_label[4] = {card_clip[0], card_clip[1], x_val - 12, card_clip[3]};
+    const int clip_value[4] = {card_clip[0], card_clip[1], x_val, card_clip[3]};
+    const int clip_unit[4]  = {x_unit, card_clip[1], card_clip[2], card_clip[3]};
+    dr(c, label, x_label, y, th.text_secondary, r20, region, TextKind::Label, clip_label);
+    drr(c, value, x_val, y, th.text_primary, m20, region, TextKind::Value, clip_value);
     if (unit && unit[0])
-        draw_text(c, unit, x_unit, y, th.text_secondary, fr(font_tier::kLabel));
+        dr(c, unit, x_unit, y, th.text_secondary, r20, region, TextKind::Unit, clip_unit);
 }
 
 // Color for the MODE-page "command status" value (M16).
@@ -246,6 +310,18 @@
     return th.text_primary;
 }
 
+// ---- fail-closed fallback for a too-small screen ---------------------------
+void render_unsupported(Canvas& c, const Theme& th) {
+    fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
+    const font_t* b = fb(font_tier::kTitle);
+    const font_t* r = fr(font_tier::kLabel);
+    const int clip[4] = {0, 0, c.w - 1, c.h - 1};
+    drc(c, "SCREEN TOO SMALL", c.w / 2, c.h / 2 - 14, th.error, b,
+        region::kFallback, TextKind::Title, clip);
+    drc(c, "min 640x720", c.w / 2, c.h / 2 + 22, th.text_secondary, r,
+        region::kFallback, TextKind::Label, clip);
+}
+
 } // namespace
 
 const char* status_label(Status s) {
@@ -260,8 +336,6 @@
 int status_badge_shape_cx(Status st, int x_right) {
     const int text_w = text_width(status_label(st), fb(font_tier::kValue));
     const int r = (st == Status::Error) ? 9 : 8;
-    // Shape center sits 10px left of the text, and its half-width r further left,
-    // so the shape's right edge is exactly 10px from the text's left edge.
     return x_right - text_w - 10 - r;
 }
 
@@ -281,12 +355,46 @@
     return g;
 }
 
+bool region_rect(int region, const layout::LayoutMetrics& lm,
+                 int& x0, int& y0, int& x1, int& y1) {
+    using namespace layout;
+    if (!lm.fit) {
+        if (region == region::kFallback) { x0 = 0; y0 = 0; x1 = lm.w - 1; y1 = lm.h - 1; return true; }
+        return false;
+    }
+    const int mx = lm.content_x0, MX = lm.content_x1;
+    const int cw = lm.col_w, gap = lm.col_gap;
+    switch (region) {
+    case region::kFallback:      x0 = 0; y0 = 0; x1 = lm.w - 1; y1 = lm.h - 1; return true;
+    case region::kTopBar:        x0 = 0; y0 = lm.top_y0; x1 = lm.w - 1; y1 = lm.top_y1; return true;
+    case region::kResultCard:    x0 = mx; y0 = lm.content_y0; x1 = MX; y1 = lm.content_y0 + 168; return true;
+    case region::kTopClasses:    x0 = mx; y0 = 264; x1 = MX; y1 = lm.content_y1; return true;
+    case region::kInfoStrip:     x0 = mx; y0 = lm.info_y0; x1 = MX; y1 = lm.info_y1; return true;
+    case region::kNav:           x0 = 0; y0 = lm.nav_y0; x1 = lm.w - 1; y1 = lm.nav_y1; return true;
+    case region::kSignalLevel:   x0 = mx; y0 = 84; x1 = mx + cw; y1 = 308; return true;
+    case region::kSpectrum:      x0 = mx + cw + gap; y0 = 84; x1 = MX; y1 = 308; return true;
+    case region::kSignalQuality: x0 = mx; y0 = 324; x1 = mx + cw; y1 = 548; return true;
+    case region::kRfConfig:      x0 = mx + cw + gap; y0 = 324; x1 = MX; y1 = 548; return true;
+    case region::kModeBtn0:      mode_ui::button_rect(0, x0, y0, x1, y1); return true;
+    case region::kModeBtn1:      mode_ui::button_rect(1, x0, y0, x1, y1); return true;
+    case region::kModeBtn2:      mode_ui::button_rect(2, x0, y0, x1, y1); return true;
+    case region::kRunStart:      mode_ui::button_rect(3, x0, y0, x1, y1); return true;
+    case region::kRunStop:       mode_ui::button_rect(4, x0, y0, x1, y1); return true;
+    case region::kDetailCard:    x0 = mx; y0 = mode_ui::kDetailY0; x1 = MX; y1 = mode_ui::kDetailY1; return true;
+    case region::kDiagLeft:      x0 = 25; y0 = 90; x1 = 620; y1 = 594; return true;
+    case region::kDiagRight:     x0 = 655; y0 = 90; x1 = 1255; y1 = 594; return true;
+    case region::kTouchLeft:     x0 = 25; y0 = 90; x1 = 820; y1 = 594; return true;
+    case region::kTouchRight:    x0 = 850; y0 = 90; x1 = 1255; y1 = 594; return true;
+    default:                     return false;
+    }
+}
+
 void render_legend(Canvas& c, const Theme& th) {
     fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
     fill_rect(c, 25, 40, 1255, 160, th.surface);
     outline_rect(c, 25, 40, 1255, 160, th.outline, 1);
-    draw_text(c, "SIGNAL STATUS (text + shape + color)", 45, 96, th.text_secondary,
-              fb(font_tier::kButton));
+    dr(c, "SIGNAL STATUS (text + shape + color)", 45, 96, th.text_secondary,
+       fb(font_tier::kButton), region::kResultCard, TextKind::Title);
     const Status seq[4] = {Status::Live, Status::Stale, Status::Error, Status::Mock};
     const int xs[4] = {200, 520, 840, 1160};
     for (int i = 0; i < 4; ++i)
@@ -298,6 +406,9 @@
 
 void render_main(Canvas& c, const Theme& th, const UiState& st) {
     fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
+    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
+    if (!lm.fit) { render_unsupported(c, th); return; }
+
     const std::vector<std::string>& classes = st.classes ? *st.classes : CLASSES_10;
     const font_t* b20 = fb(font_tier::kValue);
     const font_t* b40 = fb(font_tier::kMain);
@@ -306,15 +417,23 @@
 
     draw_top_bar(c, th, "SDR AMR", st);
 
+    int rx0, ry0, rx1, ry1;
+    region_rect(region::kResultCard, lm, rx0, ry0, rx1, ry1);
+
     // result card (top priority)
-    fill_rect(c, 25, 84, 1255, 252, th.surface);
-    outline_rect(c, 25, 84, 1255, 252, th.outline, 1);
+    fill_rect(c, rx0, ry0, rx1, ry1, th.surface);
+    outline_rect(c, rx0, ry0, rx1, ry1, th.outline, 1);
+    const int rclip[4] = {rx0, ry0, rx1, ry1};
 
     if (st.status == Status::Error) {
-        draw_text(c, "RECOGNIZED SIGNAL", 45, 126, th.text_secondary, b20);
-        draw_text(c, "NO SIGNAL", 45, 196, th.error, b40);
-        draw_text(c, "Waiting for valid input", 45, 240, th.text_secondary, r20);
-        draw_status_chip(c, th, "NO SIGNAL", th.error, 1215, 122);
+        dr(c, "RECOGNIZED SIGNAL", rx0 + 20, ry0 + 22, th.text_secondary, b20,
+           region::kResultCard, TextKind::Title, rclip);
+        dr(c, "NO SIGNAL", rx0 + 20, ry0 + 72, th.error, b40,
+           region::kResultCard, TextKind::Value, rclip);
+        dr(c, "Waiting for valid input", rx0 + 20, ry0 + 130, th.text_secondary, r20,
+           region::kResultCard, TextKind::Label, rclip);
+        text_trace_set_region(region::kResultCard);
+        draw_status_chip(c, th, "NO SIGNAL", th.error, rx1 - 41, ry0 + 38);
         draw_info_strip(c, th, st);
         draw_nav(c, th, 0);
         return;
@@ -324,7 +443,8 @@
     const std::string& top1 = st.top1;
     const float conf_pct = conf * 100.0f;
 
-    draw_text(c, "RECOGNIZED SIGNAL", 45, 126, th.text_secondary, b20);
+    dr(c, "RECOGNIZED SIGNAL", rx0 + 20, ry0 + 22, th.text_secondary, b20,
+       region::kResultCard, TextKind::Title, rclip);
 
     const char* chip_label;
     std::uint16_t chip_col;
@@ -332,26 +452,33 @@
     else if (st.status == Status::Mock)   { chip_label = "MOCK DATA";     chip_col = th.interactive; }
     else if (conf >= 0.6f)                { chip_label = "CONFIDENT";     chip_col = th.success; }
     else                                  { chip_label = "LOW CONFIDENCE"; chip_col = th.warning; }
-    draw_status_chip(c, th, chip_label, chip_col, 1215, 122);
+    text_trace_set_region(region::kResultCard);
+    draw_status_chip(c, th, chip_label, chip_col, rx1 - 41, ry0 + 38);
 
     std::uint16_t name_col;
     if (st.status == Status::Stale)       name_col = th.text_secondary;
     else if (st.status == Status::Mock)   name_col = th.interactive;
     else                                  name_col = th.text_primary;
-    draw_text(c, top1, 45, 200, name_col, b40);
+    dr(c, top1, rx0 + 20, ry0 + 72, name_col, b40, region::kResultCard, TextKind::Value, rclip);
 
     std::uint16_t conf_col;
     if (st.status == Status::Stale)       conf_col = th.text_secondary;
     else if (st.status == Status::Mock)   conf_col = th.interactive;
     else                                  conf_col = (conf < 0.6f) ? th.warning : th.success;
 
-    draw_text(c, "CONFIDENCE", 45, 240, th.text_secondary, r20);
+    // Confidence row: label + value share a baseline (side by side, measured gap);
+    // the 40px value is positioned right of the 20px label, and its baseline is
+    // below top1's descent so the two big lines never overlap (M22.1).
+    const int conf_base = ry0 + 130;
+    dr(c, "CONFIDENCE", rx0 + 20, conf_base, th.text_secondary, r20,
+       region::kResultCard, TextKind::Label, rclip);
     char pct[32];
     std::snprintf(pct, sizeof pct, "%.1f%%", conf_pct);
-    draw_text(c, pct, 210, 240, conf_col, b40);
+    const int conf_val_x = rx0 + 20 + text_width("CONFIDENCE", r20) + 16;
+    dr(c, pct, conf_val_x, conf_base, conf_col, b40, region::kResultCard, TextKind::Value, rclip);
 
     // confidence bar (right of result card)
-    const int bar_x0 = 700, bar_x1 = 1215, bar_y0 = 188, bar_y1 = 224;
+    const int bar_x0 = 700, bar_x1 = 1215, bar_y0 = ry0 + 104, bar_y1 = ry0 + 128;
     fill_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, th.accent_bar_bg);
     outline_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, th.outline, 1);
     if (st.status != Status::Stale) {
@@ -361,7 +488,11 @@
     }
 
     // Top-3 class probabilities (second priority; M19: at most the top three).
-    draw_text(c, "TOP CLASSES", 25, 288, th.text_secondary, b20);
+    int tx0, ty0, tx1, ty1;
+    region_rect(region::kTopClasses, lm, tx0, ty0, tx1, ty1);
+    const int tclip[4] = {tx0, ty0, tx1, ty1};
+    dr(c, "TOP CLASSES", tx0, 288, th.text_secondary, b20, region::kTopClasses,
+       TextKind::Title, tclip);
 
     const std::vector<float>& dist = st.dist;
     const int n = static_cast<int>(classes.size());
@@ -380,25 +511,29 @@
             if (p < 0.0f) p = 0.0f;
             if (p > 1.0f) p = 1.0f;
             const int cy = rows_y + r * row_pitch;
-            fill_rect(c, 25, cy, 1255, cy + row_h, th.surface);
-            outline_rect(c, 25, cy, 1255, cy + row_h,
+            fill_rect(c, tx0, cy, tx1, cy + row_h, th.surface);
+            outline_rect(c, tx0, cy, tx1, cy + row_h,
                          is_top ? th.selected : th.outline, is_top ? 2 : 1);
             char rank[16];
             std::snprintf(rank, sizeof rank, "%2d", r + 1);
-            draw_text(c, rank, 45, cy + 37, is_top ? th.selected : th.text_secondary, m20);
-            draw_text(c, classes[static_cast<std::size_t>(idx)], 90, cy + 37,
-                      th.text_primary, b20);
+            dr(c, rank, tx0 + 20, cy + 37, is_top ? th.selected : th.text_secondary, m20,
+               region::kTopClasses, TextKind::Label, tclip);
+            const int cls_clip[4] = {tx0 + 66, cy + 2, 316, cy + row_h - 2};
+            dr(c, classes[static_cast<std::size_t>(idx)], tx0 + 66, cy + 37,
+               th.text_primary, b20, region::kTopClasses, TextKind::Value, cls_clip);
             const int bx0 = 320, bx1 = 1100, by0 = cy + 16, by1 = cy + 40;
             fill_rect(c, bx0, by0, bx1, by1, th.accent_bar_bg);
             const int bw = static_cast<int>((bx1 - bx0) * p);
             fill_rect(c, bx0, by0, bx0 + bw, by1, is_top ? th.selected : th.text_secondary);
             char pp[16];
             std::snprintf(pp, sizeof pp, "%4.1f%%", p * 100.0f);
-            draw_text_right(c, pp, 1235, cy + 37,
-                            is_top ? th.text_primary : th.text_secondary, m20);
+            const int pct_clip[4] = {1104, cy + 2, tx1 - 20, cy + row_h - 2};
+            drr(c, pp, tx1 - 20, cy + 37, is_top ? th.text_primary : th.text_secondary,
+                m20, region::kTopClasses, TextKind::Value, pct_clip);
         }
     } else {
-        draw_text(c, "no probability data", 45, 340, th.text_secondary, r20);
+        dr(c, "no probability data", tx0 + 20, 340, th.text_secondary, r20,
+           region::kTopClasses, TextKind::Label, tclip);
     }
 
     draw_info_strip(c, th, st);
@@ -407,6 +542,8 @@
 
 void render_diag(Canvas& c, const Theme& th, const UiState& st) {
     fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
+    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
+    if (!lm.fit) { render_unsupported(c, th); return; }
     const font_t* b20 = fb(font_tier::kValue), * b40 = fb(font_tier::kMain);
     const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);
 
@@ -415,16 +552,23 @@
     if (st.status == Status::Error) {
         fill_rect(c, 25, 90, 1255, 594, th.surface);
         outline_rect(c, 25, 90, 1255, 594, th.outline, 1);
-        draw_text(c, "NO DATA", 45, 250, th.error, b40);
-        draw_text(c, "diagnostics unavailable - signal pipeline reports no valid frames",
-                  45, 310, th.text_secondary, r20);
+        const int clip[4] = {25, 90, 1255, 594};
+        dr(c, "NO DATA", 45, 250, th.error, b40, region::kDiagLeft, TextKind::Value, clip);
+        dr(c, "diagnostics unavailable - signal pipeline reports no valid frames",
+           45, 310, th.text_secondary, r20, region::kDiagLeft, TextKind::Label, clip);
         draw_nav(c, th, 1);
         return;
     }
 
-    fill_rect(c, 25, 90, 620, 594, th.surface);
-    outline_rect(c, 25, 90, 620, 594, th.outline, 1);
-    draw_text(c, "LATENCY BREAKDOWN", 45, 132, th.text_secondary, b20);
+    int lx0, ly0, lx1, ly1, x0, y0, x1, y1;
+    region_rect(region::kDiagLeft, lm, lx0, ly0, lx1, ly1);
+    region_rect(region::kDiagRight, lm, x0, y0, x1, y1);
+
+    fill_rect(c, lx0, ly0, lx1, ly1, th.surface);
+    outline_rect(c, lx0, ly0, lx1, ly1, th.outline, 1);
+    const int lclip[4] = {lx0, ly0, lx1, ly1};
+    dr(c, "LATENCY BREAKDOWN", lx0 + 20, 132, th.text_secondary, b20,
+       region::kDiagLeft, TextKind::Title, lclip);
 
     const struct { const char* k; const char* v; bool total; } rows[5] = {
         {"render", "4.2 ms", false},
@@ -436,19 +580,21 @@
     int ry = 200;
     for (const auto& r : rows) {
         if (r.total) {
-            outline_rect(c, 45, ry - 16, 600, ry + 12, th.outline, 1);
-            draw_text(c, r.k, 57, ry, th.text_primary, b20);
-            draw_text_right(c, r.v, 588, ry, th.text_primary, m20);
+            outline_rect(c, lx0 + 20, ry - 16, lx1 - 20, ry + 12, th.outline, 1);
+            dr(c, r.k, lx0 + 32, ry, th.text_primary, b20, region::kDiagLeft, TextKind::Value, lclip);
+            drr(c, r.v, lx1 - 32, ry, th.text_primary, m20, region::kDiagLeft, TextKind::Value, lclip);
         } else {
-            draw_text(c, r.k, 57, ry, th.text_secondary, r20);
-            draw_text_right(c, r.v, 588, ry, th.text_primary, m20);
+            dr(c, r.k, lx0 + 32, ry, th.text_secondary, r20, region::kDiagLeft, TextKind::Label, lclip);
+            drr(c, r.v, lx1 - 32, ry, th.text_primary, m20, region::kDiagLeft, TextKind::Value, lclip);
         }
         ry += 80;
     }
 
-    fill_rect(c, 655, 90, 1255, 594, th.surface);
-    outline_rect(c, 655, 90, 1255, 594, th.outline, 1);
-    draw_text(c, "DETAILED COUNTS", 675, 132, th.text_secondary, b20);
+    fill_rect(c, x0, y0, x1, y1, th.surface);
+    outline_rect(c, x0, y0, x1, y1, th.outline, 1);
+    const int rclip[4] = {x0, y0, x1, y1};
+    dr(c, "DETAILED COUNTS", x0 + 20, 132, th.text_secondary, b20,
+       region::kDiagRight, TextKind::Title, rclip);
 
     const struct { const char* k; const char* v; } cnt[5] = {
         {"frames rendered", "1024"},
@@ -459,27 +605,36 @@
     };
     ry = 200;
     for (const auto& r : cnt) {
-        draw_text(c, r.k, 687, ry, th.text_secondary, r20);
-        draw_text_right(c, r.v, 1223, ry, th.text_primary, m20);
+        dr(c, r.k, x0 + 32, ry, th.text_secondary, r20, region::kDiagRight, TextKind::Label, rclip);
+        drr(c, r.v, x1 - 32, ry, th.text_primary, m20, region::kDiagRight, TextKind::Value, rclip);
         ry += 64;
     }
 
-    draw_text(c, "signal status:", 675, 540, th.text_secondary, r20);
-    draw_status_badge(c, th, st.status, 1223, 534);
+    dr(c, "signal status:", x0 + 20, 540, th.text_secondary, r20, region::kDiagRight, TextKind::Label, rclip);
+    text_trace_set_region(region::kDiagRight);
+    draw_status_badge(c, th, st.status, x1 - 32, 534);
 
     draw_nav(c, th, 1);
 }
 
 void render_touch(Canvas& c, const Theme& th, const UiState& st) {
     fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
+    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
+    if (!lm.fit) { render_unsupported(c, th); return; }
     const font_t* b20 = fb(font_tier::kValue);
     const font_t* r20 = fr(font_tier::kLabel), * m20 = fm(font_tier::kValue);
 
     draw_top_bar(c, th, "TOUCH TEST", st);
 
-    fill_rect(c, 25, 90, 820, 594, th.surface);
-    outline_rect(c, 25, 90, 820, 594, th.outline, 1);
-    draw_text(c, "TOUCH CALIBRATION", 45, 132, th.text_secondary, b20);
+    int lx0, ly0, lx1, ly1, x0, y0, x1, y1;
+    region_rect(region::kTouchLeft, lm, lx0, ly0, lx1, ly1);
+    region_rect(region::kTouchRight, lm, x0, y0, x1, y1);
+
+    fill_rect(c, lx0, ly0, lx1, ly1, th.surface);
+    outline_rect(c, lx0, ly0, lx1, ly1, th.outline, 1);
+    const int lclip[4] = {lx0, ly0, lx1, ly1};
+    dr(c, "TOUCH CALIBRATION", lx0 + 20, 132, th.text_secondary, b20,
+       region::kTouchLeft, TextKind::Title, lclip);
 
     const struct { const char* k; const std::string* v; } rows[6] = {
         {"device", &st.touch.device},
@@ -491,66 +646,84 @@
     };
     int ry = 200;
     for (const auto& r : rows) {
-        draw_text(c, r.k, 57, ry, th.text_secondary, r20);
-        draw_text(c, *r.v, 250, ry, th.text_primary, m20);
+        dr(c, r.k, lx0 + 32, ry, th.text_secondary, r20, region::kTouchLeft, TextKind::Label, lclip);
+        dr(c, *r.v, lx0 + 225, ry, th.text_primary, m20, region::kTouchLeft, TextKind::Value, lclip);
         ry += 64;
     }
 
-    fill_rect(c, 850, 90, 1255, 594, th.surface);
-    outline_rect(c, 850, 90, 1255, 594, th.outline, 1);
-    draw_text(c, "HIT REGIONS", 870, 132, th.text_secondary, b20);
+    fill_rect(c, x0, y0, x1, y1, th.surface);
+    outline_rect(c, x0, y0, x1, y1, th.outline, 1);
+    const int rclip[4] = {x0, y0, x1, y1};
+    dr(c, "HIT REGIONS", x0 + 20, 132, th.text_secondary, b20,
+       region::kTouchRight, TextKind::Title, rclip);
 
     const char* tabs[3] = {"MAIN", "DIAG", "TOUCH"};
-    int tx = 870;
+    int tx = x0 + 20;
     for (int i = 0; i < 3; ++i) {
         fill_rect(c, tx, 160, tx + 112, 220, th.surface_alt);
         outline_rect(c, tx, 160, tx + 112, 220, i == 2 ? th.selected : th.outline, i == 2 ? 2 : 1);
-        draw_text_center(c, tabs[i], tx + 56, 198, i == 2 ? th.selected : th.text_primary, b20);
+        drc(c, tabs[i], tx + 56, 198, i == 2 ? th.selected : th.text_primary, b20,
+            region::kTouchRight, TextKind::Title, rclip);
         tx += 124;
     }
-    draw_text(c, "hit area >= 60 px physical", 870, 268, th.text_secondary, r20);
-    draw_text(c, "bottom nav height 90 px raw", 870, 300, th.text_secondary, r20);
+    dr(c, "hit area >= 60 px physical", x0 + 20, 268, th.text_secondary, r20,
+       region::kTouchRight, TextKind::Label, rclip);
+    dr(c, "bottom nav height 90 px raw", x0 + 20, 300, th.text_secondary, r20,
+       region::kTouchRight, TextKind::Label, rclip);
 
     const bool tconn = st.touch.connected;
-    draw_text(c, "touch:", 870, 470, th.text_secondary, r20);
-    draw_text(c, tconn ? "CONNECTED" : "DISCONNECTED", 950, 470,
-              tconn ? th.success : th.warning, b20);
+    dr(c, "touch:", x0 + 20, 470, th.text_secondary, r20, region::kTouchRight, TextKind::Label, rclip);
+    dr(c, tconn ? "CONNECTED" : "DISCONNECTED", x0 + 100, 470,
+       tconn ? th.success : th.warning, b20, region::kTouchRight, TextKind::Value, rclip);
     char tstat[48];
     std::snprintf(tstat, sizeof tstat, "taps %llu",
                   static_cast<unsigned long long>(st.touch.taps));
-    draw_text(c, tstat, 870, 510, th.text_secondary, r20);
+    dr(c, tstat, x0 + 20, 510, th.text_secondary, r20, region::kTouchRight, TextKind::Label, rclip);
     if (st.touch.last_x >= 0) {
         char pt[48];
         std::snprintf(pt, sizeof pt, "last (%d, %d)", st.touch.last_x, st.touch.last_y);
-        draw_text(c, pt, 950, 510, th.text_primary, m20);
+        dr(c, pt, x0 + 100, 510, th.text_primary, m20, region::kTouchRight, TextKind::Value, rclip);
     }
 
     draw_nav(c, th, 2);
 }
 
 // ---- PARAMETERS page (UI v3 M5 -> M19 four groups) -------------------------
-// Four grouped cards: SIGNAL LEVEL / SPECTRUM / SIGNAL QUALITY / RF
-// CONFIGURATION, label-left / value-right / unit-separate.  Measurement numbers
-// are gated on meas.valid so an absent v3 producer draws "--" placeholders rather
-// than fake zeros; presence / level_mode / model_scale / rf_gain_db / source
-// always come from the UiState runtime fields (with their own safe defaults).
 namespace {
 
 struct ParamRow { const char* label; std::string value; const char* unit; };
 
-void draw_param_card(Canvas& c, const Theme& th, int x0, int y0, int x1, int y1,
-                     const char* title, const ParamRow* rows, int count) {
+// Draw one grouped card.  The unit column width is measured from the widest unit
+// in the card (never a guess), the value column is right-aligned to a fixed
+// anchor left of the unit column, and every run is clipped to the card — so a
+// value/unit can never overflow the card or reach the neighbouring column.
+void draw_param_card(Canvas& c, const Theme& th, const layout::LayoutMetrics& lm,
+                     int region, const char* title, const ParamRow* rows, int count) {
+    int x0, y0, x1, y1;
+    region_rect(region, lm, x0, y0, x1, y1);
     fill_rect(c, x0, y0, x1, y1, th.surface);
     outline_rect(c, x0, y0, x1, y1, th.outline, 1);
-    draw_text(c, title, x0 + 20, y0 + 40, th.text_secondary, fb(font_tier::kValue));
+
+    const font_t* b20 = fb(font_tier::kValue);
+    const font_t* r20 = fr(font_tier::kLabel);
+
+    int unit_w = 0;
+    for (int i = 0; i < count; ++i)
+        if (rows[i].unit[0]) unit_w = std::max(unit_w, text_width(rows[i].unit, r20));
+    const int pad = 16;
+    const int x_unit = x1 - pad - unit_w;    // unit left anchor
+    const int x_val = x_unit - 12;           // value right anchor (12px gap)
     const int x_label = x0 + 20;
-    const int x_val = x1 - 72;
-    const int x_unit = x1 - 56;
-    int ry = y0 + 72;
+
+    const int card_clip[4] = {x0, y0, x1, y1};
+    dr(c, title, x_label, y0 + 28, th.text_secondary, b20, region, TextKind::Title, card_clip);
+
+    const int pitch = b20->line_h + 8;       // metric-driven row pitch (24+8 = 32)
+    int ry = y0 + 28 + 32;
     for (int i = 0; i < count; ++i) {
         draw_kv_row(c, th, x_label, x_val, x_unit, ry, rows[i].label,
-                    rows[i].value, rows[i].unit);
-        ry += 28;
+                    rows[i].value, rows[i].unit, region, card_clip);
+        ry += pitch;
     }
 }
 
@@ -558,12 +731,13 @@
 
 void render_parameters(Canvas& c, const Theme& th, const UiState& st) {
     fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
+    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
+    if (!lm.fit) { render_unsupported(c, th); return; }
     const MeasureView& m = st.meas;
     const bool has = m.valid;
 
     draw_top_bar(c, th, "PARAMETERS", st);
 
-    // helper: a measurement value + unit, "--"/"" when absent.
     auto mrow = [&](const char* label, const char* fmt, double v, const char* unit) {
         ParamRow r{label, has ? fnum(fmt, v) : std::string("--"),
                    has ? unit : ""};
@@ -579,7 +753,7 @@
             mrow("PAPR",         "%.2f", m.papr_db,          "dB"),
             mrow("Clip",         "%.2f", m.clip_ratio * 100.0, "%"),
         };
-        draw_param_card(c, th, 24, 84, 632, 308, "SIGNAL LEVEL", rows, 5);
+        draw_param_card(c, th, lm, region::kSignalLevel, "SIGNAL LEVEL", rows, 5);
     }
     // SPECTRUM (top-right)
     {
@@ -590,7 +764,7 @@
             mrow("Occupied BW",   "%.1f", m.occupied_bw_hz,           "Hz"),
             mrow("Centroid",      "%.1f", m.spectral_centroid_hz,     "Hz"),
         };
-        draw_param_card(c, th, 648, 84, 1256, 308, "SPECTRUM", rows, 5);
+        draw_param_card(c, th, lm, region::kSpectrum, "SPECTRUM", rows, 5);
     }
     // SIGNAL QUALITY (bottom-left)
     {
@@ -599,7 +773,7 @@
             {"Presence", st.presence, ""},
             mrow("Model RMS",    "%.3f", m.model_rms,  ""),
         };
-        draw_param_card(c, th, 24, 324, 632, 548, "SIGNAL QUALITY", rows, 3);
+        draw_param_card(c, th, lm, region::kSignalQuality, "SIGNAL QUALITY", rows, 3);
     }
     // RF CONFIGURATION (bottom-right)
     {
@@ -609,7 +783,7 @@
             {"RF gain",     fnum("%.1f", st.rf_gain_db),  "dB"},
             {"Source",      st.source, ""},
         };
-        draw_param_card(c, th, 648, 324, 1256, 548, "RF CONFIGURATION", rows, 4);
+        draw_param_card(c, th, lm, region::kRfConfig, "RF CONFIGURATION", rows, 4);
     }
 
     draw_info_strip(c, th, st);
@@ -617,13 +791,10 @@
 }
 
 // ---- MODE page (UI v3 M5 -> M16 touch control, M19 status/disabled) --------
-// Three mode buttons (name + description + per-button status SELECTED/PENDING/
-// IDLE) + START / STOP (disabled when the requested action is already in effect)
-// + a detail card (current/requested mode, run state, control channel, last
-// command, command status, feedback).  Buttons sit ABOVE the nav band (y < 630),
-// so the two tap areas never overlap.
 void render_mode(Canvas& c, const Theme& th, const UiState& st) {
     fill_rect(c, 0, 0, c.w - 1, c.h - 1, th.background);
+    const layout::LayoutMetrics lm = layout::layout_metrics(c.w, c.h);
+    if (!lm.fit) { render_unsupported(c, th); return; }
     const font_t* b20 = fb(font_tier::kValue), * b28 = fb(font_tier::kTitle);
     const font_t* r20 = fr(font_tier::kLabel);
 
@@ -640,24 +811,35 @@
         "sweep band, lock on signal",
     };
     const bool pending = (st.command_status == "PENDING");
+    // Worst-case status tag width (SELECTED/PENDING/IDLE) so the name column can
+    // never reach the right-aligned tag (M22.1).
+    const int tag_w = std::max({text_width("SELECTED", b20),
+                                text_width("PENDING", b20),
+                                text_width("IDLE", b20)});
     for (int i = 0; i < 3; ++i) {
         int x0, y0, x1, y1;
         mode_ui::button_rect(i, x0, y0, x1, y1);
+        const int btn_region = region::kModeBtn0 + i;
         const bool on = (i == active);
         const bool pressed = (st.pressed_button == i);   // M18-SW1 press-highlight
         fill_rect(c, x0, y0, x1, y1, (on || pressed) ? th.surface : th.surface_alt);
         outline_rect(c, x0, y0, x1, y1,
                      pressed ? th.interactive : (on ? th.selected : th.outline),
                      pressed ? 3 : (on ? 2 : 1));
-        draw_text(c, names[i], x0 + 20, y0 + 44, on ? th.selected : th.text_primary, b28);
-        draw_text(c, desc[i], x0 + 20, y0 + 82, th.text_secondary, r20);
+        const int name_clip[4] = {x0 + 20, y0 + 2, x1 - 16 - tag_w - 8, y1 - 2};
+        dr(c, names[i], x0 + 20, y0 + 44, on ? th.selected : th.text_primary, b28,
+           btn_region, TextKind::Title, name_clip);
+        const int desc_clip[4] = {x0 + 20, y0 + 2, x1 - 16, y1 - 2};
+        dr(c, desc[i], x0 + 20, y0 + 82, th.text_secondary, r20,
+           btn_region, TextKind::Label, desc_clip);
         // per-button status tag (right-aligned; SELECTED / PENDING / IDLE)
         const char* tag;
         std::uint16_t tag_col;
         if (on)                                  { tag = "SELECTED"; tag_col = th.selected; }
         else if (pending && st.requested_mode == names[i]) { tag = "PENDING"; tag_col = th.warning; }
         else                                     { tag = "IDLE"; tag_col = th.disabled; }
-        draw_text_right(c, tag, x1 - 16, y0 + 44, tag_col, b20);
+        const int tag_clip[4] = {x1 - 16 - tag_w, y0 + 2, x1 - 16, y1 - 2};
+        drr(c, tag, x1 - 16, y0 + 44, tag_col, b20, btn_region, TextKind::Value, tag_clip);
     }
 
     // START / STOP: the currently-in-effect action is DISABLED (dim), the other is
@@ -672,8 +854,9 @@
         outline_rect(c, x0, y0, x1, y1,
                      pressed ? th.success : (enabled ? th.success : th.outline),
                      pressed ? 3 : (enabled ? 2 : 1));
-        draw_text_center(c, "START", (x0 + x1) / 2, y0 + 52,
-                         enabled ? th.success : th.disabled, b28);
+        const int clip[4] = {x0 + 8, y0 + 8, x1 - 8, y1 - 8};
+        drc(c, "START", (x0 + x1) / 2, y0 + 52, enabled ? th.success : th.disabled, b28,
+            region::kRunStart, TextKind::Title, clip);
     }
     {
         int x0, y0, x1, y1;
@@ -684,13 +867,17 @@
         outline_rect(c, x0, y0, x1, y1,
                      pressed ? th.warning : (enabled ? th.warning : th.outline),
                      pressed ? 3 : (enabled ? 2 : 1));
-        draw_text_center(c, "STOP", (x0 + x1) / 2, y0 + 52,
-                         enabled ? th.warning : th.disabled, b28);
+        const int clip[4] = {x0 + 8, y0 + 8, x1 - 8, y1 - 8};
+        drc(c, "STOP", (x0 + x1) / 2, y0 + 52, enabled ? th.warning : th.disabled, b28,
+            region::kRunStop, TextKind::Title, clip);
     }
 
     // detail card: applied vs requested + control-channel state.
-    fill_rect(c, 25, mode_ui::kDetailY0, 1255, mode_ui::kDetailY1, th.surface);
-    outline_rect(c, 25, mode_ui::kDetailY0, 1255, mode_ui::kDetailY1, th.outline, 1);
+    int dx0, dy0, dx1, dy1;
+    region_rect(region::kDetailCard, lm, dx0, dy0, dx1, dy1);
+    fill_rect(c, dx0, dy0, dx1, dy1, th.surface);
+    outline_rect(c, dx0, dy0, dx1, dy1, th.outline, 1);
+    const int dclip[4] = {dx0, dy0, dx1, dy1};
 
     const bool ctl_ok = (st.ctl_connected == "CONTROL CONNECTED");
     const std::uint16_t run_col = st.running ? th.success : th.warning;
@@ -699,10 +886,10 @@
     const std::uint16_t req_col = (st.requested_mode == st.work_mode)
                                       ? th.text_primary : th.warning;
 
-    int ry = mode_ui::kDetailY0 + 30;
+    int ry = dy0 + 28;
     auto row = [&](const char* label, const std::string& value, std::uint16_t col) {
-        draw_text(c, label, 45, ry, th.text_secondary, r20);
-        draw_text_right(c, value, 600, ry, col, b20);
+        dr(c, label, dx0 + 20, ry, th.text_secondary, r20, region::kDetailCard, TextKind::Label, dclip);
+        drr(c, value, 600, ry, col, b20, region::kDetailCard, TextKind::Value, dclip);
         ry += mode_ui::kDetailRowPitch;
     };
     row("current mode", st.work_mode, th.selected);
```

## 三、未修改证明

本勘误补丁**不含**以下路径（故未修改模型、标签序、预处理、RTL、XDC、位流、SDR 数据链、NPU 推理逻辑）：

- 模型:  `model_12class/`、`*.raw`、`*.onnx`、`*.pt`
- 标签序: `contracts/`、`deployment_golden/`
- RTL/XDC/位流: `*.v`、`*.sv`、`*.xdc`、`*.bit`、`*.tcl`
- 数据链/NPU 推理: `board_package/board_gate9_full_chain_12class.cpp`、`board_package/npu_classifier.hpp`、`sdr_adapter/classify.hpp`、`sdr_adapter/ui_report.hpp`

补丁内容仅涉及 `scripts/`（进程编排）、`ui_sw/`（纯渲染层，仅读 UiState 不改模型输出）、`host_tests/` 与 `docs/`。
