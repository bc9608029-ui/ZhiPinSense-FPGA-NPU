// ui_renderer.cpp — the RF signal recognition instrument UI (3 pages).
//
// See the header for the contract.  All drawing is integer, software RGB565,
// solid fills / 1-2 px outlines / integer-scaled bitmap glyphs.  Every result
// shown (Top-1, band, Top-5, All-Classes highlight) derives from ONE sanitized
// probability vector, so the displays can never disagree.

#include "ui_renderer.hpp"

#include "model_contract.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>

namespace ui {

// ---- palette ---------------------------------------------------------------

const Palette& default_palette() {
    static const Palette p = {
        /*background*/    rgb565(10,  14,  20),
        /*surface*/       rgb565(20,  28,  40),
        /*surface_alt*/   rgb565(30,  40,  54),
        /*primary*/       rgb565(0,   180, 220),
        /*text_primary*/  rgb565(224, 234, 244),
        /*text_secondary*/rgb565(140, 154, 170),
        /*outline*/       rgb565(70,  84,  102),
        /*success*/       rgb565(48,  200, 120),
        /*warning*/       rgb565(235, 195, 70),
        /*error*/         rgb565(235, 80,  80),
        /*inactive*/      rgb565(96,  106, 120),
    };
    return p;
}

const char* band_label(Band b) {
    switch (b) {
        case Band::High:   return "HIGH";
        case Band::Medium: return "MEDIUM";
        case Band::Low:    return "LOW";
    }
    return "LOW";
}

const char* source_label(Source s) {
    switch (s) {
        case Source::Mock: return "MOCK";
        case Source::File: return "FILE";
        case Source::Sdr:  return "SDR";
    }
    return "MOCK";
}

const char* live_label(LiveState s) {
    switch (s) {
        case LiveState::Live:  return "LIVE";
        case LiveState::Stale: return "STALE";
        case LiveState::Error: return "ERROR";
    }
    return "LIVE";
}

// ---- numeric helpers -------------------------------------------------------

std::vector<float> softmax(const std::vector<float>& logits) {
    std::vector<float> out(logits.size(), 0.0f);
    if (logits.empty()) return out;

    float m = -std::numeric_limits<float>::infinity();
    for (float v : logits) if (std::isfinite(v) && v > m) m = v;
    if (!std::isfinite(m)) m = 0.0f;   // all entries non-finite

    double sum = 0.0;
    for (std::size_t i = 0; i < logits.size(); ++i) {
        const float e = std::isfinite(logits[i])
                            ? std::exp(logits[i] - m)
                            : 0.0f;
        out[i] = e;
        sum += e;
    }
    if (sum > 0.0) {
        for (float& o : out) o = static_cast<float>(o / sum);
    } else {
        std::fill(out.begin(), out.end(), 0.0f);
    }
    return out;
}

bool sanitize_probabilities(std::vector<float>& p, int class_count, std::string* why) {
    if (static_cast<int>(p.size()) != class_count) {
        if (why) *why = "prob.size() != class_count";
        return false;
    }
    double sum = 0.0;
    for (float& v : p) {
        if (!std::isfinite(v) || v < 0.0f) v = 0.0f;   // reject NaN/Inf/negative
        sum += v;
    }
    if (sum <= 0.0) {
        if (why) *why = "no probability mass";
        return false;
    }
    for (float& v : p) v = static_cast<float>(v / sum);
    return true;
}

int argmax(const std::vector<float>& p) {
    int best = 0;
    for (std::size_t i = 1; i < p.size(); ++i)
        if (p[i] > p[static_cast<std::size_t>(best)]) best = static_cast<int>(i);
    return best;
}

std::vector<int> top_k(const std::vector<float>& p, int k) {
    std::vector<int> idx(p.size());
    for (std::size_t i = 0; i < p.size(); ++i) idx[i] = static_cast<int>(i);
    std::sort(idx.begin(), idx.end(), [&](int a, int b) {
        if (p[a] != p[b]) return p[a] > p[b];
        return a < b;                       // tie -> lower index first
    });
    if (k > static_cast<int>(idx.size())) k = static_cast<int>(idx.size());
    if (k < 0) k = 0;
    idx.resize(static_cast<std::size_t>(k));
    return idx;
}

Band confidence_band(float top1) {
    if (top1 >= 0.80f) return Band::High;
    if (top1 >= 0.50f) return Band::Medium;
    return Band::Low;
}

bool validate_state(const UiState& s, std::string* why) {
    std::string cw;
    if (!model::is_valid_contract(s.class_names, &cw)) {
        if (why) *why = "contract: " + cw;
        return false;
    }
    if (s.class_count != static_cast<int>(s.class_names.size()) ||
        s.class_count != static_cast<int>(s.prob.size())) {
        if (why) *why = "class_count/class_names/prob size mismatch";
        return false;
    }
    return true;
}

TabHit hit_test_tab(int x, int y) {
    TabHit h;
    if (y < layout::kTabY || y >= layout::kTabY + layout::kTabH) return h;
    auto in = [&](int tx) { return x >= tx && x < tx + layout::kTabW; };
    if (in(layout::kTabX0)) { h.on_tab = true; h.page = Page::Overview; }
    else if (in(layout::kTabX1)) { h.on_tab = true; h.page = Page::AllClasses; }
    else if (in(layout::kTabX2)) { h.on_tab = true; h.page = Page::Diagnostics; }
    return h;
}

// ---- string formatting -----------------------------------------------------

std::string fmt_pct(float p) {
    char buf[16];
    std::snprintf(buf, sizeof buf, "%5.1f%%", static_cast<double>(p) * 100.0);
    return std::string(buf);
}

std::string fmt_f(float v, int prec) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%.*f", prec, static_cast<double>(v));
    return std::string(buf);
}

std::string fmt_u(std::uint64_t v) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%llu", static_cast<unsigned long long>(v));
    return std::string(buf);
}

std::string fmt_hex(std::uint64_t v, int min_digits) {
    if (min_digits < 1) min_digits = 1;
    if (min_digits > 16) min_digits = 16;
    // Fixed 16-hex-char field (zero-padded) never overflows buf; then strip
    // leading zeros, but never below min_digits, so a fixed "0x%0Nd" width is
    // produced without a variable-width format (avoids -Wformat-truncation).
    char buf[32];
    std::snprintf(buf, sizeof buf, "%016llx", static_cast<unsigned long long>(v));
    int leading = 0;
    while (leading < 16 - min_digits && buf[leading] == '0') ++leading;
    return std::string("0x") + (buf + leading);
}

// ---- renderer --------------------------------------------------------------

Renderer::Renderer(const Palette& p) : palette_(p) {}

void Renderer::draw(Canvas& c, const UiState& s, Page page) {
    c.clear(palette_.background);

    std::string why;
    if (!validate_state(s, &why)) {
        c.text(layout::kMargin, layout::kBodyY + 40, "INVALID CONTRACT", 4, palette_.error);
        c.text(layout::kMargin, layout::kBodyY + 96, why, 3, palette_.text_secondary);
        return;
    }

    std::vector<float> p = s.prob;
    if (!sanitize_probabilities(p, s.class_count)) {
        // no probability mass -> "NO SIGNAL" state
        draw_header(c, s, page);
        const int cx = (layout::kCanvasW - Canvas::text_w("NO SIGNAL", 8)) / 2;
        c.text(cx, 300, "NO SIGNAL", 8, palette_.text_primary);
        const int cx2 = (layout::kCanvasW - Canvas::text_w("LOW CONFIDENCE", 3)) / 2;
        c.text(cx2, 390, "LOW CONFIDENCE", 3, palette_.warning);
        return;
    }

    draw_header(c, s, page);
    switch (page) {
        case Page::Overview:     draw_overview(c, s, p);     break;
        case Page::AllClasses:   draw_all_classes(c, s, p); break;
        case Page::Diagnostics:  draw_diagnostics(c, s);    break;
    }
}

void Renderer::draw_header(Canvas& c, const UiState& s, Page page) {
    c.text(layout::kMargin, 8, "RF SIGNAL RECOGNITION", 3, palette_.text_primary);

    draw_tab(c, layout::kTabX0, layout::kTabW, "OVERVIEW",    page == Page::Overview);
    draw_tab(c, layout::kTabX1, layout::kTabW, "ALL CLASSES", page == Page::AllClasses);
    draw_tab(c, layout::kTabX2, layout::kTabW, "DIAGNOSTICS", page == Page::Diagnostics);

    const int chipY = layout::kTabY + 10;
    const int chipH = layout::kTabH - 20;   // 40

    std::uint16_t live_fill = palette_.inactive;
    switch (s.live) {
        case LiveState::Live:  live_fill = palette_.success; break;
        case LiveState::Stale: live_fill = palette_.warning; break;
        case LiveState::Error: live_fill = palette_.error;   break;
    }
    draw_chip(c, 892, chipY, 120, chipH, live_fill, palette_.background,
              live_label(s.live), 3);

    if (s.is_mock) {
        draw_chip(c, 1024, chipY, 240, chipH, palette_.warning, palette_.background,
                  "DEMO/MOCK", 3);
    }
}

void Renderer::draw_overview(Canvas& c, const UiState& s, const std::vector<float>& p) {
    const int top1 = argmax(p);
    const float conf = p[static_cast<std::size_t>(top1)];
    const Band band = confidence_band(conf);
    const std::uint16_t band_color =
        band == Band::High ? palette_.success :
        band == Band::Medium ? palette_.warning : palette_.error;

    // -- left: top result --
    c.text(16, 120, "TOP RESULT", 3, palette_.text_secondary);
    c.text(16, 156, s.class_names[static_cast<std::size_t>(top1)], 8, palette_.text_primary);
    c.text(16, 232, fmt_pct(conf), 6, palette_.text_primary);

    // band chip + "CONFIDENCE" text
    draw_chip(c, 16, 306, 200, 48, band_color, palette_.background, band_label(band), 4);
    c.text(232, 316, "CONFIDENCE", 3, palette_.text_secondary);

    // status lines
    c.text(16, 380, "SOURCE: " + std::string(source_label(s.source)), 3, palette_.text_primary);
    c.text(16, 412, "FPGA: " + std::string(s.fpga_ok ? "OK" : "FAULT"), 3,
           s.fpga_ok ? palette_.success : palette_.error);
    c.text(16, 444, "MODEL: " + std::string(s.npu_ok ? "ONLINE" : "OFFLINE"), 3,
           s.npu_ok ? palette_.success : palette_.warning);
    c.text(16, 476, "FRAME: " + fmt_u(s.frame_id), 3, palette_.text_secondary);
    c.text(16, 508, "DROPPED: " + fmt_u(s.dropped), 3, palette_.text_secondary);

    // -- right: top 5 --
    c.text(704, 120, "TOP 5", 3, palette_.text_secondary);
    const int k = std::min(5, static_cast<int>(p.size()));
    const std::vector<int> idx = top_k(p, k);
    for (int r = 0; r < k; ++r) {
        const int ci = idx[static_cast<std::size_t>(r)];
        const bool is_top = (ci == top1);
        const int y = 156 + r * 72;
        const std::string name = std::to_string(r + 1) + " " + s.class_names[static_cast<std::size_t>(ci)];
        c.text(704, y, name, 3, is_top ? palette_.primary : palette_.text_primary);
        c.text(1120, y, fmt_pct(p[static_cast<std::size_t>(ci)]), 3, palette_.text_primary);
        draw_bar(c, 704, y + 28, 560, 20, p[static_cast<std::size_t>(ci)],
                 is_top ? palette_.primary : palette_.text_secondary,
                 palette_.surface_alt);
    }
}

void Renderer::draw_all_classes(Canvas& c, const UiState& s, const std::vector<float>& p) {
    c.text(16, 120, "ALL CLASSES", 3, palette_.text_secondary);
    c.text(16, 152, "FIXED CONTRACT ORDER", 3, palette_.text_secondary);

    const int n = static_cast<int>(p.size());
    const int top1 = argmax(p);
    const int row_top = 192;
    const int row_bottom = layout::kCanvasH - 8;
    const int row_h = (row_bottom - row_top) / n;

    for (int i = 0; i < n; ++i) {
        const int y = row_top + i * row_h;
        const int ty = y + (row_h - 24) / 2;
        const bool is_top = (i == top1);

        char idxbuf[8];
        // class_count is validated to <= 16, so i + 1 <= 16 fits "%02u" in
        // idxbuf; narrow to std::uint8_t so -Wformat-truncation sees [0,255].
        std::snprintf(idxbuf, sizeof idxbuf, "%02u", static_cast<unsigned>(static_cast<std::uint8_t>(i + 1)));
        c.text(16, ty, idxbuf, 3, is_top ? palette_.primary : palette_.text_secondary);

        // ">" marks the Top-1 row (a symbol, not color alone).
        c.text(64, ty, is_top ? ">" : " ", 3, palette_.primary);
        c.text(88, ty, s.class_names[static_cast<std::size_t>(i)], 3,
               is_top ? palette_.primary : palette_.text_primary);

        const int bh = (row_h >= 40) ? 20 : 14;
        const int by = y + (row_h - bh) / 2;
        draw_bar(c, 340, by, 660, bh, p[static_cast<std::size_t>(i)],
                 is_top ? palette_.primary : palette_.text_secondary,
                 palette_.surface_alt);

        c.text(1010, ty, fmt_pct(p[static_cast<std::size_t>(i)]), 3,
               is_top ? palette_.primary : palette_.text_primary);
    }
}

void Renderer::draw_diagnostics(Canvas& c, const UiState& s) {
    c.text(16, 120, "DIAGNOSTICS", 3, palette_.text_secondary);

    if (s.error_count > 0 || s.live == LiveState::Error) {
        draw_chip(c, 1064, 116, 200, 44, palette_.error, palette_.background, "ERROR", 3);
    }

    auto kv = [&](int x, int y, const std::string& label, const std::string& value,
                  std::uint16_t vcolor) {
        const std::string l = label + ": ";
        c.text(x, y, l, 3, palette_.text_secondary);
        c.text(x + Canvas::text_w(l, 3), y, value, 3, vcolor);
    };

    const int y0 = 176;
    const int step = 32;

    // left column
    kv(16,  y0 + 0 * step, "SOURCE", source_label(s.source), palette_.text_primary);
    kv(16,  y0 + 1 * step, "FRAME", fmt_u(s.frame_id), palette_.text_primary);
    kv(16,  y0 + 2 * step, "FPS", fmt_f(s.fps, 1), palette_.text_primary);
    kv(16,  y0 + 3 * step, "FRONT BUFFER", fmt_u(static_cast<std::uint64_t>(s.front_buffer)), palette_.text_primary);
    kv(16,  y0 + 4 * step, "RENDER LAT", fmt_f(s.render_latency_ms, 2) + " MS", palette_.text_primary);
    kv(16,  y0 + 5 * step, "E2E LAT", fmt_f(s.e2e_latency_ms, 2) + " MS", palette_.text_primary);
    kv(16,  y0 + 6 * step, "DROPPED", fmt_u(s.dropped), palette_.text_primary);
    kv(16,  y0 + 7 * step, "OUT-OF-ORDER", fmt_u(s.out_of_order), palette_.text_primary);
    kv(16,  y0 + 8 * step, "DUPLICATE", fmt_u(s.duplicate), palette_.text_primary);
    kv(16,  y0 + 9 * step, "STALE", fmt_u(s.stale), palette_.text_primary);

    // right column
    kv(640, y0 + 0 * step, "ERROR", fmt_u(s.error_count),
       s.error_count > 0 ? palette_.error : palette_.text_primary);
    kv(640, y0 + 1 * step, "FB PHYS", fmt_hex(s.fb_phys_addr, 8), palette_.text_primary);
    kv(640, y0 + 2 * step, "CTRL VER", fmt_hex(s.frame_ctrl_version, 8), palette_.text_primary);
    kv(640, y0 + 3 * step, "FPGA", s.fpga_ok ? "OK" : "FAULT",
       s.fpga_ok ? palette_.success : palette_.error);
    kv(640, y0 + 4 * step, "NPU", s.npu_ok ? "ONLINE" : "OFFLINE",
       s.npu_ok ? palette_.success : palette_.warning);
    kv(640, y0 + 5 * step, "CLASSES", fmt_u(static_cast<std::uint64_t>(s.class_count)), palette_.text_primary);
    kv(640, y0 + 6 * step, "LIVE", live_label(s.live),
       s.live == LiveState::Live ? palette_.success :
       s.live == LiveState::Stale ? palette_.warning : palette_.error);
    kv(640, y0 + 7 * step, "MOCK", s.is_mock ? "YES" : "NO",
       s.is_mock ? palette_.warning : palette_.text_primary);

    // event log
    const int log_y = 520;
    c.text(16, log_y, "EVENT LOG", 3, palette_.text_secondary);
    c.rect(16, log_y + 34, 1248, 160, palette_.outline, 1);

    const std::size_t max_lines = 6;
    const std::size_t start = s.events.size() > max_lines ? s.events.size() - max_lines : 0;
    std::size_t line = 0;
    for (std::size_t i = start; i < s.events.size(); ++i, ++line) {
        std::string e = s.events[i];
        if (e.size() > 50) e = e.substr(0, 50) + ".";
        c.text(24, log_y + 42 + static_cast<int>(line) * 26, e, 3, palette_.text_secondary);
    }
    if (line == 0) {
        c.text(24, log_y + 42, "NO EVENTS", 3, palette_.text_secondary);
    }
}

void Renderer::draw_bar(Canvas& c, int x, int y, int w, int h, float frac,
                        std::uint16_t fill, std::uint16_t track) {
    c.fill_rect(x, y, w, h, track);
    c.rect(x, y, w, h, palette_.outline, 1);
    int fw = static_cast<int>(frac * static_cast<float>(w));
    if (fw < 0) fw = 0;
    if (fw > w) fw = w;
    if (fw > 0) c.fill_rect(x, y, fw, h, fill);
}

void Renderer::draw_tab(Canvas& c, int x, int w, const char* label, bool selected) {
    const int y = layout::kTabY;
    const int h = layout::kTabH;
    const int tw = Canvas::text_w(label, 3);
    if (selected) {
        c.fill_rect(x, y, w, h, palette_.primary);
        c.text(x + (w - tw) / 2, y + (h - 24) / 2, label, 3, palette_.background);
    } else {
        c.fill_rect(x, y, w, h, palette_.surface);
        c.rect(x, y, w, h, palette_.outline, 1);
        c.text(x + (w - tw) / 2, y + (h - 24) / 2, label, 3, palette_.text_secondary);
    }
}

void Renderer::draw_chip(Canvas& c, int x, int y, int w, int h,
                         std::uint16_t fill, std::uint16_t text_color,
                         const std::string& label, int scale) {
    c.fill_rect(x, y, w, h, fill);
    const int tw = Canvas::text_w(label, scale);
    const int th = Canvas::glyph_h(scale);
    c.text(x + (w - tw) / 2, y + (h - th) / 2, label, scale, text_color);
}

} // namespace ui
