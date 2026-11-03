// ui_render.hpp — Style A (modern scientific instrument) UI page renderers.
//
// Pixel-consistent RGB565 port of the approved design draft (Style A).  All three
// pages (Main / Diagnostics / Touch) share one restrained palette and one layout
// grid (horizontal 5px, vertical 6px at 1280x720), so the 1280x720 output scales
// to the 1024x600 panel with integer factors (0.80x / 5/6x) and no re-sampling
// blur.  Status is always expressed as text + shape + color.
//
// This module is device-independent: it only draws into a ui::Canvas (an ordinary
// RGB565 buffer).  The board programs (phase2/phase3) render into the staging
// framebuffer and submit via DirectFramebufferBackend::submit_frame(), which is
// NOT touched by this visual refactor.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "font_atlas.hpp"

namespace ui {

enum class Status { Live, Stale, Error, Mock };

struct Palette {
    std::uint16_t bg, surface, surface_alt, text, dim, primary,
                  success, warning, error, outline, accent_bar_bg;
};

// Touch-test page state (Gate C7).  Filled by the board server from the evdev
// device; host tests leave it defaulted so the Touch page still renders.
struct TouchInfo {
    std::string device = "--";     // e.g. "/dev/input/event2"
    std::string vendor = "--";     // e.g. "1a86:e5e3"
    std::string axis_x = "--";     // e.g. "0 .. 4095"
    std::string axis_y = "--";     // e.g. "0 .. 4095"
    std::string mapping_x = "--";  // e.g. "raw_x*1280/4095"
    std::string mapping_y = "--";  // e.g. "raw_y*720/4095"
    bool connected = false;
    std::uint64_t taps = 0;        // page-switch taps seen so far
    int last_x = -1;               // last touch point (screen px), -1 = none
    int last_y = -1;
};

struct UiState {
    Status status = Status::Live;
    std::string source = "SDR";
    float conf = 0.0f;          // top-1 confidence in [0,1]
    std::string top1;           // top-1 class name
    std::vector<float> dist;    // class probabilities (may be empty)
    std::string snr = "--";     // e.g. "+18 dB"
    std::string lat = "--";     // e.g. "12.4 ms"
    std::string frame = "--";   // e.g. "1024"
    std::string model;          // short model SHA (empty => not drawn)
    std::string age;            // non-empty => stale age, e.g. "3.2 s"
    const std::vector<std::string>* classes = nullptr;  // nullptr => 10-class default
    TouchInfo touch;            // Touch-test page device info (Gate C7)
};

// Style A palette (modern scientific instrument): neutral dark gray-blue + a
// little blue; all text >= 4.5:1 contrast.  Values are RGB565.
const Palette& palette_style_a();

void render_main(Canvas& c, const Palette& pal, const UiState& st);
void render_diag(Canvas& c, const Palette& pal, const UiState& st);
void render_touch(Canvas& c, const Palette& pal, const UiState& st);

// Standalone status legend (MOCK / LIVE / STALE / ERROR: text + shape + color).
void render_legend(Canvas& c, const Palette& pal);

// Status badge geometry: the shape (icon) sits >=10px LEFT of the right-aligned
// status text, never covering it.  status_badge_shape_cx returns the shape's
// center x for a badge whose text ends at x_right; status_label returns the
// text label ("LIVE"/"STALE"/"ERROR"/"MOCK").  Exposed so host tests can assert
// the icon/text never overlap and that Mock never renders as Live.
int status_badge_shape_cx(Status st, int x_right);
const char* status_label(Status st);

// Class-probability card grid for N classes (two columns).  Exposed so host
// tests can assert the grid fits above the info strip for class counts 8..16.
struct CardGrid { int y0 = 0; int rows = 0; int row_pitch = 0; int card_h = 0; };
CardGrid card_grid(int n);

// Class contracts: 10-class (current V1.1 AMR) and 12-class (target).
const std::vector<std::string>& classes_10();
const std::vector<std::string>& classes_12();

} // namespace ui
