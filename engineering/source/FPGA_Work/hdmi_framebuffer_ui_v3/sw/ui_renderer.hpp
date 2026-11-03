// ui_renderer.hpp — the "RF SIGNAL RECOGNITION" instrument UI (3 pages).
//
// Fully generic over the model contract: it renders any 8..16 class contract from
// the runtime `class_names` / `probabilities` / `class_count` carried in UiState.
// The class ORDER comes from the model contract (model_contract.hpp), never from
// this file.  No Qt, no GPU, no linuxfb/eglfs — pure software RGB565 on a Canvas
// (staging buffer), integer glyph scaling, solid fills and 1-2 px outlines only.
//
// Consistency rule (task 8): the Top-1 result, the status band, the Top-5 bars
// and the All-Classes highlight are all derived from ONE sanitized probability
// vector inside draw(), so they can never disagree.  Color is never the sole
// state expression — every colored chip also carries text.

#pragma once

#include "canvas.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace ui {

// ---- semantic palette ------------------------------------------------------
struct Palette {
    std::uint16_t background;
    std::uint16_t surface;
    std::uint16_t surface_alt;
    std::uint16_t primary;        // cyan-blue accent (selected / top-1)
    std::uint16_t text_primary;
    std::uint16_t text_secondary;
    std::uint16_t outline;
    std::uint16_t success;        // green  = normal / high confidence
    std::uint16_t warning;        // amber  = caution / medium confidence
    std::uint16_t error;          // red    = fault / low confidence
    std::uint16_t inactive;       // dim gray
};

const Palette& default_palette();

// ---- enums -----------------------------------------------------------------
enum class Band { High, Medium, Low };
const char* band_label(Band b);

enum class Source { Mock, File, Sdr };
const char* source_label(Source s);

enum class LiveState { Live, Stale, Error };
const char* live_label(LiveState s);

enum class Page { Overview, AllClasses, Diagnostics };

// ---- runtime UI state ------------------------------------------------------
struct UiState {
    // Model contract (runtime, 8..16 classes).  Order = model output order.
    std::vector<std::string> class_names;
    std::vector<float> prob;        // probabilities (sum ~ 1); may be slightly off
    int class_count = 0;            // must equal class_names.size() and prob.size()

    Source source = Source::Mock;
    LiveState live = LiveState::Live;
    bool fpga_ok = true;
    bool npu_ok = false;            // no real NPU in the HDMI-only build -> false
    bool is_mock = true;            // simulated data -> show DEMO/MOCK badge

    std::uint64_t frame_id = 0;
    std::uint64_t dropped = 0;
    std::uint64_t out_of_order = 0;
    std::uint64_t duplicate = 0;
    std::uint64_t stale = 0;
    std::uint64_t error_count = 0;
    float fps = 0.0f;
    float render_latency_ms = 0.0f;
    float e2e_latency_ms = 0.0f;

    std::uint64_t fb_phys_addr = 0;      // framebuffer physical address (from sysfs)
    std::uint32_t frame_ctrl_version = 0; // frame_ctrl slv_reg3
    int front_buffer = 0;                // current front buffer index (0/1)

    std::vector<std::string> events;     // recent event log (most recent last)
};

// ---- pure numeric helpers (host-testable) ----------------------------------
// Numerically stable softmax (max-subtracted).  Non-finite logits -> -inf (-> 0).
std::vector<float> softmax(const std::vector<float>& logits);

// Rejects NaN/Inf/negative entries (zeroes them), then re-normalizes to sum 1.
// Returns false when the result has no mass (all rejected / empty) or when
// p.size() differs from class_count (writes a reason to *why when given).
bool sanitize_probabilities(std::vector<float>& p, int class_count, std::string* why = nullptr);

int argmax(const std::vector<float>& p);

// Indices of the k largest probabilities, descending, ties -> lower index first.
std::vector<int> top_k(const std::vector<float>& p, int k);

Band confidence_band(float top1);

// Validates UiState for rendering: contract valid (8..16), name/prob/count agree.
// Writes a reason to *why on failure.
bool validate_state(const UiState& s, std::string* why = nullptr);

// ---- touch hit-testing (pure, host-testable) -------------------------------
struct TabHit {
    bool on_tab = false;
    Page page = Page::Overview;
};

// Maps a CANVAS coordinate (already scaled from the physical panel) to a tab.
// Returns on_tab=false when the point is not on any tab.
TabHit hit_test_tab(int canvas_x, int canvas_y);

// ---- layout constants (shared with hit_test and renderer) ------------------
namespace layout {
    constexpr int kCanvasW = 1280;
    constexpr int kCanvasH = 720;
    constexpr int kMargin = 16;
    constexpr int kHeaderH = 44;        // title row
    constexpr int kTabY = 44;
    constexpr int kTabH = 60;
    constexpr int kTabW = 280;
    constexpr int kTabGap = 12;
    constexpr int kTabX0 = 16;
    constexpr int kTabX1 = kTabX0 + kTabW + kTabGap;   // 308
    constexpr int kTabX2 = kTabX1 + kTabW + kTabGap;   // 600
    constexpr int kBodyY = kTabY + kTabH;              // 104
}

// ---- the renderer ----------------------------------------------------------
class Renderer {
public:
    explicit Renderer(const Palette& p = default_palette());

    // Draw one page onto the canvas.  Sanitizes probabilities once and derives
    // every result from that single vector, so all displays are consistent.
    // On an invalid contract/state it draws a clear INVALID-CONTRACT error
    // instead of crashing.
    void draw(Canvas& c, const UiState& s, Page page);

    const Palette& palette() const { return palette_; }

private:
    Palette palette_;

    void draw_header(Canvas& c, const UiState& s, Page page);
    void draw_overview(Canvas& c, const UiState& s, const std::vector<float>& p);
    void draw_all_classes(Canvas& c, const UiState& s, const std::vector<float>& p);
    void draw_diagnostics(Canvas& c, const UiState& s);
    void draw_bar(Canvas& c, int x, int y, int w, int h, float frac,
                  std::uint16_t fill, std::uint16_t track);
    void draw_tab(Canvas& c, int x, int w, const char* label, bool selected);
    void draw_chip(Canvas& c, int x, int y, int w, int h,
                   std::uint16_t fill, std::uint16_t text_color, const std::string& label, int scale);
};

// ---- small string formatting helpers (shared with tests) -------------------
std::string fmt_pct(float p);          // " 93.5%"  (6 cols, fixed width)
std::string fmt_f(float v, int prec);  // "60.0", "1.23"
std::string fmt_u(std::uint64_t v);
std::string fmt_hex(std::uint64_t v, int min_digits);

} // namespace ui
