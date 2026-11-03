// ui_render.hpp — Style A (modern scientific instrument) UI page renderers.
//
// M19 (界面视觉整理): the renderers now draw a unified skeleton — top status bar
// (system/mode/RUN-STOP/control + signal status) + main content + bottom nav —
// against a single semantic theme (ui_theme.hpp) and an 8 px grid (ui_layout.hpp).
//
// Pixel-consistent RGB565 output: no shadows / blur / gradients / translucent
// layers, no runtime glyph scaling, and status is always text + shape + color.
//
// This module is device-independent: it only draws into a ui::Canvas (an ordinary
// RGB565 buffer).  The board programs render into the staging framebuffer and
// submit via DirectFramebufferBackend::submit_frame(), which is NOT touched by
// this visual refactor.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "font_atlas.hpp"
#include "ui_theme.hpp"

namespace ui {

// Waterfall ring-buffer history (fix10class24-waterfall1).  Forward-declared here
// so render_parameters can take an optional history pointer without pulling the
// fixed-ring buffer into every UI translation unit.  Defined in
// ui_sw/waterfall_history.hpp.
struct WaterfallHistory;

// Signal status.  NoSignal = frames ARE arriving but below the presence threshold
// (a valid listening state, distinct from Stale = feed timed out and Error = RX
// stream anomaly).
enum class Status {
    Live,           // valid result frame: a classification is shown
    Stale,          // feed timed out (> stale_ms) or data socket gone
    Error,          // RX stream anomaly
    Mock,           // mock data
    NoSignal,       // RUNNING + NO_SIGNAL, heartbeats fresh (valid listening state)
    Waiting,        // no valid state/result received yet (connecting)
    Acquiring,      // RUNNING + ACQUIRING, heartbeats fresh
    SignalPresent,  // RUNNING + SIGNAL_PRESENT but no new result yet (classifying)
    Stopped         // STOPPED, heartbeats fresh (protocol chain still alive)
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

// UI v3 M5: flat display view of the M3 DSP measurements, rendered by the
// PARAMETERS page.  The ui layer stays independent of sdr_adapter; the bridge
// (ui_state_map.hpp) copies values out of rf::ResultFrame::measurements into
// this struct, so rendering never includes a DSP header.
struct MeasureView {
    bool valid = false;                 // false => no measurements (placeholders)
    double rms_counts = 0.0;
    double peak_counts = 0.0;
    double papr_db = 0.0;
    double clip_ratio = 0.0;
    double power_dbfs = 0.0;
    double noise_floor_dbfs = 0.0;
    double psd_peak_prominence_db = 0.0;
    double snr_est_db = 0.0;
    int occupied_bins = 0;
    double spectral_centroid_hz = 0.0;
    double occupied_bw_hz = 0.0;
    double model_rms = 0.0;
    // display spectrum (fix10class24-waterfall1): 256 dBFS*4 bins in fftshift
    // order (negative -> positive frequency), valid only when spectrum_valid.
    bool spectrum_valid = false;
    int spectrum_dbfs_x4[256] = {};
    double spectrum_sample_rate_hz = 0.0;
    double spectrum_center_hz = 0.0;
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

    // RML23 (M29 Phase F5): model identity + paginated category-table state.
    std::string model_mode;     // e.g. "RML23-AMSSB-MERGED" ("" = not RML23)
    int class_count = 0;        // contract width (0 = legacy 10/12-class pages)
    int category_page = 0;      // active page of the 23-class category table
    TouchInfo touch;            // Touch-test page device info (Gate C7)
    MeasureView meas;           // PARAMETERS page data (UI v3 M5)
    std::string presence = "--";    // M1 presence state (SIGNAL_PRESENT, ...)
    std::string level_mode = "--";  // M2 level mode (FIXED / AUTO)
    double model_scale = 1.0;       // M2 digital scalar
    double rf_gain_db = 0.0;        // M2 RF gain (dB)
    std::string work_mode = "FIXED";// work mode (FIXED / AUTO LOCK / BAND SCAN)
    bool running = true;            // run state (RUNNING / STOPPED) via M6 control channel

    // M16: third-page touch mode control.  requested_* is what the user last asked
    // for via touch; the APPLIED state stays in work_mode / running (producer
    // authoritative).  The two diverge only while a command is PENDING.
    std::string requested_mode = "FIXED";    // touch-requested work mode (display name)
    bool requested_running = true;
    std::string ctl_connected = "CONTROL DISCONNECTED";  // CONTROL CONNECTED / DISCONNECTED
    std::string last_command = "--";        // last command sent, e.g. "SET_MODE FIXED"
    std::string command_status = "--";      // IDLE / PENDING / APPLIED / REJECTED / TIMEOUT
    std::uint64_t control_taps = 0;         // valid control taps seen so far

    // M18-SW1 Task A: transient tap feedback (why a tap produced no command, e.g.
    // "ALREADY IN THIS MODE") and the button currently pressed (press-highlight).
    std::string feedback = "--";
    int pressed_button = -1;                 // 0..4 while down & valid, else -1

    // Final receiver constellation, display-only and derived from the same
    // recovered tensor as the classifier input.
    bool iq_display_valid = false;
    std::int16_t iq_i16_interleaved[512] = {};
    double iq_units_per_count = 0.0;
};

void render_main(Canvas& c, const Theme& th, const UiState& st);
void render_diag(Canvas& c, const Theme& th, const UiState& st);
void render_touch(Canvas& c, const Theme& th, const UiState& st);
// PARAMETERS page: with a non-null history it renders the spectrum + waterfall
// view (fix10class24-waterfall1); a null history keeps the legacy 4-card layout
// so the existing 3-arg host tests keep working unchanged.
void render_parameters(Canvas& c, const Theme& th, const UiState& st,
                       const WaterfallHistory* history = nullptr);
// Five-page candidate: dedicated spectrum/waterfall page.  Kept separate from
// measurements so the competition UI does not mix numeric evidence and plots.
void render_waterfall(Canvas& c, const Theme& th, const UiState& st,
                      const WaterfallHistory& history);
void render_mode(Canvas& c, const Theme& th, const UiState& st);
void render_constellation(Canvas& c, const Theme& th, const UiState& st);

// Standalone status legend (LIVE / STALE / NO SIGNAL / ERROR / MOCK:
// text + shape + color).
void render_legend(Canvas& c, const Theme& th);

// Status badge geometry: the shape (icon) sits >=10px LEFT of the right-aligned
// status text, never covering it.  status_badge_shape_cx returns the shape's
// center x for a badge whose text ends at x_right; status_label returns the
// text label ("LIVE"/"STALE"/"NO SIGNAL"/"ERROR"/"MOCK").  Exposed so host tests
// can assert
// the icon/text never overlap and that Mock never renders as Live.
int status_badge_shape_cx(Status st, int x_right);
const char* status_label(Status st);

// Class-probability card grid for N classes (two columns).  Exposed so host
// tests can assert the grid fits above the info strip for class counts 8..16.
struct CardGrid { int y0 = 0; int rows = 0; int row_pitch = 0; int card_h = 0; };
CardGrid card_grid(int n);

// ---- SETUP-page touch buttons (M16) -----------------------------------------
// Single source of truth for the third-page button geometry, shared by
// render_mode() (ui_sw/ui_render.cpp) and the touch hit-test state machine
// (board_package/touch_mode_control.hpp).  The buttons live ABOVE the bottom nav
// (y < 630), so the nav tap area and the button tap area never overlap.
//
// M19 (W5): START / STOP are 88 raw px tall (200..287) -> ~73 px physical after
// the 0.833x panel scale, satisfying the >=64 px touch-target rule.  The mode
// buttons (90..189) remain 100 raw px -> ~83 px physical.  The detail card moves
// down to 296 and uses a 36 px row pitch to keep its 7 rows above the info strip.
namespace mode_ui {
constexpr int kModeY0 = 90;   // mode-button row (inclusive)
constexpr int kModeY1 = 190;
constexpr int kModeW = 390;
constexpr int kModeGap = 15;
constexpr int kModeX0 = 25;
constexpr int kRunY0 = 200;   // START / STOP row (inclusive)
constexpr int kRunY1 = 288;
constexpr int kRunX0 = 25;
constexpr int kRunW = 600;
constexpr int kRunGap = 30;
constexpr int kDetailY0 = 296;   // detail card (inclusive); ends above the info strip
constexpr int kDetailY1 = 548;
constexpr int kDetailRowPitch = 36;

constexpr int kBtnFixed = 0, kBtnAutoLock = 1, kBtnBandScan = 2;
constexpr int kBtnStart = 3, kBtnStop = 4;
constexpr int kBtnCount = 5;

// Rectangle (inclusive x1/y1) of button i in {0..4}.
inline void button_rect(int i, int& x0, int& y0, int& x1, int& y1) {
    if (i <= kBtnBandScan) {
        x0 = kModeX0 + i * (kModeW + kModeGap);
        y0 = kModeY0;
        x1 = x0 + kModeW;
        y1 = kModeY1;
    } else if (i == kBtnStart) {
        x0 = kRunX0; y0 = kRunY0; x1 = kRunX0 + kRunW; y1 = kRunY1;
    } else {
        x0 = kRunX0 + kRunW + kRunGap; y0 = kRunY0; x1 = x0 + kRunW; y1 = kRunY1;
    }
}
}  // namespace mode_ui

// Class contracts: 10-class (current V1.1 AMR), 12-class (target), 23-class
// (RML23 deployed AM-SSB merge) and 24-class (RML24 source).
const std::vector<std::string>& classes_10();
const std::vector<std::string>& classes_12();
const std::vector<std::string>& classes_23();
const std::vector<std::string>& classes_24();

} // namespace ui
