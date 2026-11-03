// ui_theme.hpp — M19 unified visual theme (semantic color tokens + font tiers).
//
// Replaces the ad-hoc `Palette` with a single semantic token set so the renderers
// and host tests share one source of truth.  Every token is a plain RGB565 value;
// the names follow the M19 spec (background / surface / surface_alt / outline /
// text_primary / text_secondary / interactive / selected / success / warning /
// error / disabled).  Contrast ratios are asserted in host_tests/test_ui_layout_m19.cpp:
//   * text_primary / text_secondary on surface and background  >= 4.5 : 1
//   * interactive / success / warning / error (used as text)    >= 4.5 : 1
//   * disabled is exempt (deliberately low-contrast, never used for status alone).
//
// Status is NEVER conveyed by color alone anywhere in the renderer: every state is
// text + shape + color (see status_label / draw_status_badge in ui_render.hpp).

#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

#include "font_atlas.hpp"   // rgb565()

namespace ui {

struct Theme {
    std::uint16_t background;      // page background          #0F141B
    std::uint16_t surface;         // card / panel fill        #1A212B
    std::uint16_t surface_alt;     // chip / selected-nav fill #121A24
    std::uint16_t outline;         // hairline borders         #2A3542
    std::uint16_t text_primary;    // primary text             #E7ECF2
    std::uint16_t text_secondary;  // dim label text           #8B98A8
    std::uint16_t interactive;     // buttons / links / active #4A90E2
    std::uint16_t selected;        // selected-state highlight #4A90E2 (== interactive)
    std::uint16_t success;         // green (RUNNING / LIVE)   #3DDC84
    std::uint16_t warning;         // amber (STALE / PENDING)  #E8A93C
    std::uint16_t error;           // red (ERROR / NO SIGNAL)  #E5605F
    std::uint16_t disabled;        // disabled text/border     #5A6672 (exempt)
    std::uint16_t accent_bar_bg;   // confidence-bar track     #141B25
};

// The canonical Style A theme.  Values are the frozen M14 palette, plus the two new
// M19 tokens (selected, disabled).
inline const Theme& theme_default() {
    static const Theme t = {
        rgb565(15, 20, 27),    // background        #0F141B
        rgb565(26, 33, 43),    // surface           #1A212B
        rgb565(18, 25, 36),    // surface_alt       #121A24
        rgb565(42, 53, 66),    // outline           #2A3542
        rgb565(231, 236, 242), // text_primary      #E7ECF2
        rgb565(139, 152, 168), // text_secondary    #8B98A8
        rgb565(74, 144, 226),  // interactive       #4A90E2
        rgb565(74, 144, 226),  // selected          #4A90E2
        rgb565(61, 220, 132),  // success           #3DDC84
        rgb565(232, 169, 60),  // warning           #E8A93C
        rgb565(229, 96, 95),   // error             #E5605F
        rgb565(90, 102, 114),  // disabled          #5A6672
        rgb565(20, 27, 37),    // accent_bar_bg     #141B25
    };
    return t;
}

// ---- font tiers (M19 D1: <=4 sizes, no atlas regeneration) --------------------
// The 6.4 MB baked atlas has Regular{20,28,40,52} Bold{20,24,28,40,52}
// Mono{20,28,40,52}.  M19 uses exactly four sizes:
//   40  main class / big value (spec 40-48)
//   28  page + section titles (spec 28-32)
//   24  nav + mode / start-stop button labels (spec 20-24, Bold only)
//   20  values + labels (spec values 20-24 / labels >=16; atlas minimum is 20)
// The 52 px top-1 glyph is retired (exceeds the 48 px spec ceiling).
namespace font_tier {
constexpr int kMain = 40;
constexpr int kTitle = 28;
constexpr int kButton = 24;
constexpr int kValue = 20;
constexpr int kLabel = 20;   // atlas has no 16/18 px face; 20 satisfies ">=16"
}  // namespace font_tier

// ---- WCAG contrast helpers (runtime; used by host tests) ----------------------
// sRGB relative luminance of a single channel in [0,1].
inline double srgb_lin(double c) {
    if (c < 0.0) c = 0.0;
    if (c > 1.0) c = 1.0;
    return c <= 0.04045 ? c / 12.92 : std::pow((c + 0.055) / 1.055, 2.4);
}

// Relative luminance of an RGB565 pixel (5->8 and 6->8 by bit replication).
inline double luminance565(std::uint16_t c) {
    const int r5 = (c >> 11) & 0x1F;
    const int g6 = (c >> 5) & 0x3F;
    const int b5 = c & 0x1F;
    const double r = static_cast<double>((r5 << 3) | (r5 >> 2)) / 255.0;
    const double g = static_cast<double>((g6 << 2) | (g6 >> 4)) / 255.0;
    const double b = static_cast<double>((b5 << 3) | (b5 >> 2)) / 255.0;
    return 0.2126 * srgb_lin(r) + 0.7152 * srgb_lin(g) + 0.0722 * srgb_lin(b);
}

// WCAG 2.x contrast ratio (>= 1).  Order-independent.
inline double contrast_ratio(std::uint16_t a, std::uint16_t b) {
    double la = luminance565(a);
    double lb = luminance565(b);
    if (la < lb) std::swap(la, lb);
    return (la + 0.05) / (lb + 0.05);
}

}  // namespace ui
