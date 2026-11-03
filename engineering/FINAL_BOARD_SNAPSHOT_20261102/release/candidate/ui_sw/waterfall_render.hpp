#pragma once

// waterfall_render.hpp -- spectrum + waterfall page renderer (fix10class24-waterfall1,
// Phase E).  Draws only the CONTENT AREA of the PARAMETERS page (y 84..548); the
// page skeleton (top bar, info strip, bottom nav) is still drawn by
// render_parameters() in ui_render.cpp, which calls this for the panel body.

#include "ui_render.hpp"   // Canvas, Theme, UiState, WaterfallHistory (fwd)

namespace ui {

// Render the spectrum curve (current frame) + bounded waterfall heatmap + side
// metrics + frequency/power axes into the content area.  Pure draw: it NEVER
// advances history and NEVER mutates UiState.  Fail-closed on a non-1280x720
// canvas (draws nothing).  Status handling is text-first: INVALID draws
// "RX ERROR" with no heatmap, STALE draws "STALE / DATA TIMEOUT" over the frozen
// history, ACQUIRING overlays "ACQUIRING", SIGNAL_LOST overlays "SIGNAL LOST"
// and keeps the existing rows.
void render_spectrum_waterfall(Canvas& c, const Theme& th, const UiState& st,
                               const WaterfallHistory& history);

// The 256-entry viridis-like RGB565 colormap (dark violet -> yellow).  Exposed
// for host tests (endpoint + monotonicity checks); never used for status alone.
const std::uint16_t* waterfall_viridis_lut();

}  // namespace ui
