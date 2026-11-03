// phase2_ui_render.cpp — Phase 2 offscreen RGB565 rendering of the recognition UI
// (FMQL30TAI, 1280x720@60, double-buffered flip path shared with Phase 1B/1C).
//
// Uses ONLY the safe direct backend (direct_framebuffer_backend): /dev/udmabuf0
// for the framebuffer and /dev/mem for frame_ctrl.  It does NOT touch the NPU,
// DMA, or iCraft Device::Open.
//
// Renders the full signal-recognition UI entirely in software into the mapped
// RGB565 framebuffer, then flips the PL read select (0x40080050) at the next
// vsync — the same tear-free path as Phase 1B.  This proves the *display* side
// of the final UI.  Confidence values are a DEMO source (rotating softmax); the
// real NPU logits plug into the same make_conf() vector.
//
// Class list: FINAL 10-class order (fixed 2026-10-04) — AM-DSB, WBFM, 2FSK,
// GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM.  The renderer is generic over N.
//
// Consistency guarantee: top-1 is DERIVED from the normalized distribution
// (argmax over conf, which sums to 1.0), so the class rows, the top-1 highlight,
// the status line, and the result box all show the SAME top-1/confidence.
// Latency is the measured software render+flush+flip time of the previous frame.
//
//   PL buffer select: 0x40080050 bit[0] = read buffer (0/1)
//   PL read base:     0x40080054 = FB0 >> 3 (set once)
//
// PHASE2_UI_PASS (software gate) = version OK + registers write/readback OK +
//   first UI frame rendered & flipped.  The text-legibility check on HDMI is the
//   hardware gate (still READY-FOR-HARDWARE-TEST until then).

#include "direct_framebuffer_backend.hpp"

#include <cstdint>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include <unistd.h>
#include <signal.h>
#include <time.h>

namespace {

constexpr int FRAME_W = 1280;
constexpr int FRAME_H = 720;

// ---- FINAL 10-class order (fixed 2026-10-04) -------------------------------
const std::vector<std::string> CLASS_NAMES = {
    "AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
    "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"
};

// ---- RGB565 --------------------------------------------------------------
inline std::uint16_t rgb565(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    return static_cast<std::uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// ---- 5x7 font (columns = chars, rows = 7). '#' = on, '.' = off. -----------
static const char** glyph_for(char c) {
    switch (c) {
    case '0': { static const char* g[7] = {".###.","#...#","#..##","#.#.#","##..#","#...#",".###."}; return g; }
    case '1': { static const char* g[7] = {"..#..",".##..","..#..","..#..","..#..","..#..","#####"}; return g; }
    case '2': { static const char* g[7] = {".###.","#...#","....#","...#.","..#..",".#...","#####"}; return g; }
    case '3': { static const char* g[7] = {"#####","...#.","..#..",".###.","....#","#...#",".###."}; return g; }
    case '4': { static const char* g[7] = {"...#.","..##.",".#.#.","#..#.","#####","...#.","...#."}; return g; }
    case '5': { static const char* g[7] = {"#####","#....","####.","....#","....#","#...#",".###."}; return g; }
    case '6': { static const char* g[7] = {".###.","#....","#....","####.","#...#","#...#",".###."}; return g; }
    case '7': { static const char* g[7] = {"#####","....#","...#.","..#..",".#...",".#...",".#..."}; return g; }
    case '8': { static const char* g[7] = {".###.","#...#","#...#",".###.","#...#","#...#",".###."}; return g; }
    case '9': { static const char* g[7] = {".###.","#...#","#...#",".###.","....#","....#",".###."}; return g; }
    case 'A': { static const char* g[7] = {"..#..",".#.#.","#...#","#...#","#####","#...#","#...#"}; return g; }
    case 'B': { static const char* g[7] = {"####.","#...#","#...#","####.","#...#","#...#","####."}; return g; }
    case 'C': { static const char* g[7] = {".###.","#...#","#....","#....","#....","#...#",".###."}; return g; }
    case 'D': { static const char* g[7] = {"####.","#...#","#...#","#...#","#...#","#...#","####."}; return g; }
    case 'E': { static const char* g[7] = {"#####","#....","#....","####.","#....","#....","#####"}; return g; }
    case 'F': { static const char* g[7] = {"#####","#....","#....","####.","#....","#....","#...."}; return g; }
    case 'G': { static const char* g[7] = {".###.","#...#","#....","#.###","#...#","#...#",".###."}; return g; }
    case 'H': { static const char* g[7] = {"#...#","#...#","#...#","#####","#...#","#...#","#...#"}; return g; }
    case 'I': { static const char* g[7] = {"#####","..#..","..#..","..#..","..#..","..#..","#####"}; return g; }
    case 'J': { static const char* g[7] = {"..###","...#.","...#.","...#.","...#.","#..#.",".##.."}; return g; }
    case 'K': { static const char* g[7] = {"#...#","#..#.","#.#..","##...","#.#..","#..#.","#...#"}; return g; }
    case 'L': { static const char* g[7] = {"#....","#....","#....","#....","#....","#....","#####"}; return g; }
    case 'M': { static const char* g[7] = {"#...#","##.##","#.#.#","#.#.#","#...#","#...#","#...#"}; return g; }
    case 'N': { static const char* g[7] = {"#...#","##..#","#.#.#","#..##","#...#","#...#","#...#"}; return g; }
    case 'O': { static const char* g[7] = {".###.","#...#","#...#","#...#","#...#","#...#",".###."}; return g; }
    case 'P': { static const char* g[7] = {"####.","#...#","#...#","####.","#....","#....","#...."}; return g; }
    case 'Q': { static const char* g[7] = {".###.","#...#","#...#","#...#","#.#.#","#..#.",".##.#"}; return g; }
    case 'R': { static const char* g[7] = {"####.","#...#","#...#","####.","#.#..","#..#.","#...#"}; return g; }
    case 'S': { static const char* g[7] = {".####","#....","#....",".###.","....#","....#","####."}; return g; }
    case 'T': { static const char* g[7] = {"#####","..#..","..#..","..#..","..#..","..#..","..#.."}; return g; }
    case 'U': { static const char* g[7] = {"#...#","#...#","#...#","#...#","#...#","#...#",".###."}; return g; }
    case 'V': { static const char* g[7] = {"#...#","#...#","#...#","#...#","#...#",".#.#.","..#.."}; return g; }
    case 'W': { static const char* g[7] = {"#...#","#...#","#...#","#.#.#","#.#.#","##.##","#...#"}; return g; }
    case 'X': { static const char* g[7] = {"#...#","#...#",".#.#.","..#..",".#.#.","#...#","#...#"}; return g; }
    case 'Y': { static const char* g[7] = {"#...#","#...#",".#.#.","..#..","..#..","..#..","..#.."}; return g; }
    case 'Z': { static const char* g[7] = {"#####","....#","...#.","..#..",".#...","#....","#####"}; return g; }
    case '.': { static const char* g[7] = {".....",".....",".....",".....",".....",".##..",".##.."}; return g; }
    case '%': { static const char* g[7] = {"##..#","##..#","...#.","..#..",".#...","#..##","#..##"}; return g; }
    case '-': { static const char* g[7] = {".....",".....",".....","#####",".....",".....","....."}; return g; }
    case '/': { static const char* g[7] = {"....#","...#.","...#.","..#..",".#...",".#...","#...."}; return g; }
    case ':': { static const char* g[7] = {".....",".##..",".##..",".....",".##..",".##..","....."}; return g; }
    case '>': { static const char* g[7] = {"#....",".#...","..#..","...#.","..#..",".#...","#...."}; return g; }
    case '(': { static const char* g[7] = {"...#.","..#..",".#...",".#...",".#...","..#..","...#."}; return g; }
    case ')': { static const char* g[7] = {".#...","..#..","...#.","...#.","...#.","..#..",".#..."}; return g; }
    case '_': { static const char* g[7] = {".....",".....",".....",".....",".....",".....","#####"}; return g; }
    case ' ': { static const char* g[7] = {".....",".....",".....",".....",".....",".....","....."}; return g; }
    default:  { static const char* g[7] = {"#####","#####","#####","#####","#####","#####","#####"}; return g; }
    }
}

// ---- drawing --------------------------------------------------------------
struct Canvas { std::uint16_t* px; int w, h; };

inline void set_px(Canvas& c, int x, int y, std::uint16_t color) {
    if (x < 0 || x >= c.w || y < 0 || y >= c.h) return;
    c.px[y * c.w + x] = color;
}

void fill_rect(Canvas& c, int x0, int y0, int x1, int y1, std::uint16_t color) {
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= c.w) x1 = c.w - 1;
    if (y1 >= c.h) y1 = c.h - 1;
    if (x0 > x1 || y0 > y1) return;
    for (int y = y0; y <= y1; ++y)
        for (int x = x0; x <= x1; ++x)
            c.px[y * c.w + x] = color;
}

void rect_outline(Canvas& c, int x0, int y0, int x1, int y1, std::uint16_t color, int thick = 1) {
    for (int t = 0; t < thick; ++t) {
        for (int x = x0; x <= x1; ++x) { set_px(c, x, y0 + t, color); set_px(c, x, y1 - t, color); }
        for (int y = y0; y <= y1; ++y) { set_px(c, x0 + t, y, color); set_px(c, x1 - t, y, color); }
    }
}

void draw_char(Canvas& c, char ch, int x, int y, std::uint16_t color, int scale = 1) {
    const char** g = glyph_for(ch);
    for (int r = 0; r < 7; ++r)
        for (int col = 0; col < 5; ++col)
            if (g[r][col] == '#')
                fill_rect(c, x + col * scale, y + r * scale,
                          x + col * scale + scale - 1, y + r * scale + scale - 1, color);
}

void draw_text(Canvas& c, const std::string& s, int x, int y, std::uint16_t color, int scale = 1) {
    int cx = x;
    for (char ch : s) { draw_char(c, ch, cx, y, color, scale); cx += 6 * scale; }
}

// ---- demo confidence source (normalized) ----------------------------------
// Synthetic logits for a rotating top-1, then softmax so `conf` is a valid
// probability distribution (sum == 1.0).  Replace with real NPU logits later.
void make_conf(std::vector<float>& conf, int top) {
    const int n = static_cast<int>(CLASS_NAMES.size());
    std::vector<float> logits(n, 0.0f);
    for (int i = 0; i < n; ++i) {
        int k = (i - top) % n; if (k < 0) k += n;   // circular distance from top
        logits[i] = 4.0f - 1.6f * k;                 // top=4.0, geometric decay
    }
    float mx = logits[0];
    for (int i = 1; i < n; ++i) if (logits[i] > mx) mx = logits[i];
    float sum = 0.0f;
    for (int i = 0; i < n; ++i) { logits[i] = std::exp(logits[i] - mx); sum += logits[i]; }
    for (int i = 0; i < n; ++i) conf[i] = logits[i] / sum;
}

// ---- UI render ------------------------------------------------------------
void render_ui(Canvas& c, const std::vector<float>& conf, int top1, int snr_db,
               double lat_ms, int frame) {
    const int n = static_cast<int>(CLASS_NAMES.size());

    const std::uint16_t BG      = rgb565(0x00, 0x08, 0x18);
    const std::uint16_t TITLEBG = rgb565(0x00, 0x10, 0x30);
    const std::uint16_t TEXT    = rgb565(0xE0, 0xE0, 0xE0);
    const std::uint16_t DIM     = rgb565(0x80, 0x90, 0xA0);
    const std::uint16_t ACCENT  = rgb565(0x00, 0xC0, 0xFF);
    const std::uint16_t GOOD    = rgb565(0x00, 0xE0, 0x60);
    const std::uint16_t WARN    = rgb565(0xE0, 0xA0, 0x00);
    const std::uint16_t HIGHLITE= rgb565(0xFF, 0xFF, 0xFF);
    const std::uint16_t BORDER  = rgb565(0x40, 0x60, 0x80);

    // Readability: no scale-1 glyphs.  5x7 glyph height = 7*scale, advance = 6*scale.
    // Body text (class names / status / percentages) is scale=2 (14 px tall);
    // title and the result name are scale=3 (21 px).  Outlines are 2 px thick so
    // single-pixel lines survive the panel's 1024x600 downscale.
    const int S_TITLE = 3, S_BODY = 2, OUTLINE = 2;
    const int body_h = 7 * S_BODY;   // 14 px glyph height

    fill_rect(c, 0, 0, FRAME_W - 1, FRAME_H - 1, BG);

    // title bar
    fill_rect(c, 0, 0, FRAME_W - 1, 55, TITLEBG);
    rect_outline(c, 0, 0, FRAME_W - 1, 55, ACCENT, OUTLINE);
    draw_text(c, "RF SIGNAL RECOGNITION", 40, 14, ACCENT, S_TITLE);

    // status line (top-1 / confidence / latency / frame are all mutually consistent)
    char status[128];
    std::snprintf(status, sizeof(status),
                  "SNR:%+ddB TOP-1:%s CONF:%3.0f%% LAT:%5.1fms FRAME:%d",
                  snr_db, CLASS_NAMES[static_cast<std::size_t>(top1)].c_str(),
                  conf[static_cast<std::size_t>(top1)] * 100.0f, lat_ms, frame);
    draw_text(c, status, 40, 66, DIM, S_BODY);

    // class list
    const int list_top = 100, list_bot = 620;
    const int row_h = (list_bot - list_top) / n;
    const int bar_x = 340, bar_w = FRAME_W - bar_x - 140;

    for (int i = 0; i < n; ++i) {
        int y0 = list_top + i * row_h;
        int y1 = y0 + row_h - 6;
        int cy = y0 + (row_h - body_h) / 2;   // vertical centre of the row
        bool is_top = (i == top1);

        char label[32];
        std::snprintf(label, sizeof(label), "%d", i + 1);
        draw_text(c, label, 24, cy, is_top ? HIGHLITE : DIM, S_BODY);
        draw_text(c, CLASS_NAMES[static_cast<std::size_t>(i)], 72, cy,
                  is_top ? HIGHLITE : TEXT, S_BODY);

        std::uint16_t bar_col = (conf[i] >= 0.5f) ? GOOD : (conf[i] >= 0.15f ? WARN : ACCENT);
        fill_rect(c, bar_x, y0, bar_x + bar_w - 1, y1, rgb565(0x08, 0x10, 0x20));
        int fillw = static_cast<int>(bar_w * conf[i]);
        if (fillw > 0) fill_rect(c, bar_x, y0, bar_x + fillw - 1, y1, bar_col);
        rect_outline(c, bar_x, y0, bar_x + bar_w - 1, y1, is_top ? HIGHLITE : BORDER, OUTLINE);

        char pct[16];
        std::snprintf(pct, sizeof(pct), "%3.0f%%", conf[i] * 100.0f);
        draw_text(c, pct, bar_x + bar_w + 16, cy, is_top ? HIGHLITE : DIM, S_BODY);
    }

    // result box (vertically centred)
    const int rbox_y = 624, rbox_h = FRAME_H - rbox_y;
    fill_rect(c, 0, rbox_y, FRAME_W - 1, FRAME_H - 1, TITLEBG);
    rect_outline(c, 0, rbox_y, FRAME_W - 1, FRAME_H - 1, ACCENT, OUTLINE);
    draw_text(c, "RESULT >", 40, rbox_y + (rbox_h - body_h) / 2, ACCENT, S_BODY);
    draw_text(c, CLASS_NAMES[static_cast<std::size_t>(top1)], 200,
              rbox_y + (rbox_h - 7 * S_TITLE) / 2, HIGHLITE, S_TITLE);
}

volatile sig_atomic_t g_stop = 0;
void on_sigint(int) { g_stop = 1; }

} // namespace

int main(int argc, char** argv) {
    const long static_top = (argc > 1) ? std::strtol(argv[1], nullptr, 10) : -1; // -1 = animate
    const long fps        = (argc > 2) ? std::strtol(argv[2], nullptr, 10) : 20;

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    dfb::Config cfg;
    dfb::RealIo io;
    dfb::DirectFramebufferBackend fb(cfg, io);

    if (!fb.init()) return 2;   // FAIL already printed

    const std::uint32_t rd = static_cast<std::uint32_t>(fb.phys_addr() >> 3);
    if (!fb.write_reg(cfg.rd_addr_offset, rd)) return 3;
    if (!fb.write_reg(cfg.wr_addr_offset, 0)) return 4;

    std::vector<float> conf(CLASS_NAMES.size());
    int front = 0;
    long frame = 0;
    const int n = static_cast<int>(CLASS_NAMES.size());
    double last_lat_ms = 0.0;
    bool ui_pass_printed = false;
    std::uint16_t* stage = fb.staging();
    const std::size_t frame_px = static_cast<std::size_t>(FRAME_W) * FRAME_H;

    // Initial frame, so the PL never reads uninitialised memory before the flip.
    make_conf(conf, 0);
    {
        Canvas c0{ stage, FRAME_W, FRAME_H };
        render_ui(c0, conf, 0, 0, 0.0, 0);
        if (!fb.submit_frame(0, stage, frame_px)) return 5;
    }

    std::cout << "PHASE2_PS_READY (static_top=" << static_top
              << " fps=" << fps << "; Ctrl-C to stop)\n";

    const useconds_t period = fps > 0 ? static_cast<useconds_t>(1000000 / fps) : 0;
    while (!g_stop) {
        const int top1 = (static_top >= 0) ? static_cast<int>(static_top % n)
                                           : static_cast<int>((frame / (2 * fps)) % n);
        make_conf(conf, top1);

        // Derive top-1 from the ACTUAL normalized distribution so the class rows,
        // top-1 highlight, status line and result box are provably consistent.
        int argmax = 0;
        for (int i = 1; i < n; ++i) if (conf[i] > conf[argmax]) argmax = i;

        const int snr_db = static_cast<int>(20 - (frame / fps) % 30);
        const int back = front ^ 1;

        struct timespec t_begin, t_end;
        clock_gettime(CLOCK_MONOTONIC, &t_begin);
        Canvas canvas{ stage, FRAME_W, FRAME_H };
        render_ui(canvas, conf, argmax, snr_db, last_lat_ms, static_cast<int>(frame));
        // submit_frame: scalar volatile copy + sync + flip (all before returning).
        if (!fb.submit_frame(back, stage, frame_px)) return 6;
        clock_gettime(CLOCK_MONOTONIC, &t_end);
        last_lat_ms = (t_end.tv_sec - t_begin.tv_sec) * 1000.0
                    + (t_end.tv_nsec - t_begin.tv_nsec) / 1e6;
        front = back;

        if (!ui_pass_printed) {
            std::cout << "PHASE2_UI_PASS (version/registers OK, first UI frame rendered & flipped; "
                         "top-1/conf/status/latency consistent)\n";
            ui_pass_printed = true;
        }

        if (fps > 0 && (frame % fps) == 0)
            std::cout << "[2-PS] frame=" << frame << " top1=" << CLASS_NAMES[static_cast<std::size_t>(argmax)]
                      << " conf=" << static_cast<int>(conf[static_cast<std::size_t>(argmax)] * 100)
                      << "% lat=" << last_lat_ms << "ms\n";
        ++frame;
        if (period > 0) usleep(period);
    }

    std::cout << "[2-PS] stopped after " << frame << " frames\n";
    return 0;
}
