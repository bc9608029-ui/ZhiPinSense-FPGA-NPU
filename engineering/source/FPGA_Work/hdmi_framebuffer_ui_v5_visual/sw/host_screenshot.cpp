// host_screenshot.cpp — host-only renderer for the v5_visual acceptance screenshots.
//
// Renders the Style A pages with the SAME font atlas + RGB565 blend math that the
// board uses (font_atlas.cpp + ui_render.cpp), into an ordinary RGB565 buffer, and
// writes 24-bit BMP images for visual acceptance.  This is the "主机生成 1280x720
// 原始截图" evidence; the 1024x600 previews are produced from these BMPs by
// tools/convert_host_out.py (Pillow BILINEAR, the same downscale as the design draft).
//
// Device-independent: no /dev, no mmap, no backend — just the pure render layer.
// Build (host, e.g. WSL):  g++ -O2 -std=gnu++17 host_screenshot.cpp font_atlas.cpp
//                          font_atlas_data.cpp ui_render.cpp -o host_screenshot

#include "ui_render.hpp"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

constexpr int W = 1280;
constexpr int H = 720;

void canvas_to_rgb888(const ui::Canvas& c, std::uint8_t* out) {
    for (int i = 0; i < W * H; ++i) {
        const std::uint16_t p = c.px[i];
        const int r5 = (p >> 11) & 0x1F, g6 = (p >> 5) & 0x3F, b5 = p & 0x1F;
        out[i * 3 + 0] = static_cast<std::uint8_t>((r5 << 3) | (r5 >> 2));
        out[i * 3 + 1] = static_cast<std::uint8_t>((g6 << 2) | (g6 >> 4));
        out[i * 3 + 2] = static_cast<std::uint8_t>((b5 << 3) | (b5 >> 2));
    }
}

void put16(std::uint8_t* p, std::uint32_t v) { p[0] = v & 0xFF; p[1] = (v >> 8) & 0xFF; }
void put32(std::uint8_t* p, std::uint32_t v) {
    p[0] = v & 0xFF; p[1] = (v >> 8) & 0xFF; p[2] = (v >> 16) & 0xFF; p[3] = (v >> 24) & 0xFF;
}

bool write_bmp(const std::string& path, const std::uint8_t* rgb, int w, int h) {
    const int row = (w * 3 + 3) & ~3;
    const int data = row * h;
    const int file = 54 + data;
    std::vector<std::uint8_t> buf(static_cast<std::size_t>(file), 0);
    buf[0] = 'B'; buf[1] = 'M';
    put32(&buf[2], static_cast<std::uint32_t>(file));
    put32(&buf[10], 54);
    put32(&buf[14], 40);
    put32(&buf[18], static_cast<std::uint32_t>(w));
    put32(&buf[22], static_cast<std::uint32_t>(h));
    put16(&buf[26], 1);
    put16(&buf[28], 24);
    put32(&buf[34], static_cast<std::uint32_t>(data));
    for (int y = 0; y < h; ++y) {
        const int src_y = h - 1 - y;
        const std::uint8_t* src = rgb + static_cast<std::size_t>(src_y) * w * 3;
        std::uint8_t* dst = &buf[54] + static_cast<std::size_t>(y) * row;
        for (int x = 0; x < w; ++x) {
            dst[x * 3 + 0] = src[x * 3 + 2];   // B
            dst[x * 3 + 1] = src[x * 3 + 1];   // G
            dst[x * 3 + 2] = src[x * 3 + 0];   // R
        }
        for (int x = w * 3; x < row; ++x) dst[x] = 0;
    }
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    const std::size_t written = std::fwrite(buf.data(), 1, static_cast<std::size_t>(file), f);
    std::fclose(f);
    return written == static_cast<std::size_t>(file);
}

// Four demo states, mirroring the design-draft make_states().
ui::UiState make_state(int which) {
    ui::UiState st;
    switch (which) {
        case 0:  // normal
            st.status = ui::Status::Live; st.source = "SDR"; st.conf = 0.842f; st.top1 = "16QAM";
            st.dist = {0.008f, 0.006f, 0.012f, 0.015f, 0.010f, 0.024f, 0.031f, 0.842f, 0.044f, 0.008f};
            st.snr = "+18 dB"; st.lat = "12.4 ms"; st.frame = "1024";
            break;
        case 1:  // low-confidence
            st.status = ui::Status::Live; st.source = "SDR"; st.conf = 0.412f; st.top1 = "QPSK";
            st.dist = {0.015f, 0.022f, 0.028f, 0.035f, 0.042f, 0.412f, 0.308f, 0.075f, 0.038f, 0.025f};
            st.snr = "+7 dB"; st.lat = "13.1 ms"; st.frame = "1025";
            break;
        case 2:  // stale
            st.status = ui::Status::Stale; st.source = "SDR"; st.conf = 0.842f; st.top1 = "16QAM";
            st.dist = {0.008f, 0.006f, 0.012f, 0.015f, 0.010f, 0.024f, 0.031f, 0.842f, 0.044f, 0.008f};
            st.snr = "--"; st.lat = "--"; st.frame = "1007"; st.age = "3.2 s";
            break;
        default: // error
            st.status = ui::Status::Error; st.source = "SDR"; st.conf = 0.0f; st.top1 = "";
            st.snr = "--"; st.lat = "--"; st.frame = "--";
            break;
    }
    return st;
}

} // namespace

int main() {
    const ui::Palette& pal = ui::palette_style_a();
    const char* pages[3] = {"main", "diag", "touch"};
    const char* states[4] = {"normal", "lowconf", "stale", "error"};

    std::vector<std::uint16_t> buf(static_cast<std::size_t>(W) * H);
    std::vector<std::uint8_t> rgb(static_cast<std::size_t>(W) * H * 3);
    ui::Canvas c{ buf.data(), W, H };

    int written = 0;

    // 3 pages x 4 states, 1280x720
    for (int p = 0; p < 3; ++p) {
        for (int s = 0; s < 4; ++s) {
            const ui::UiState st = make_state(s);
            std::fill(buf.begin(), buf.end(), 0);
            if (p == 0)      ui::render_main(c, pal, st);
            else if (p == 1) ui::render_diag(c, pal, st);
            else             ui::render_touch(c, pal, st);
            canvas_to_rgb888(c, rgb.data());
            char name[128];
            std::snprintf(name, sizeof name, "host_out/%s_%s_1280.bmp", pages[p], states[s]);
            if (write_bmp(name, rgb.data(), W, H)) ++written;
            else std::fprintf(stderr, "FAIL write %s\n", name);
        }
    }

    // 12-class target, main page, normal state (same two-column layout, N=12)
    {
        ui::UiState st = make_state(0);
        st.classes = &ui::classes_12();
        st.top1 = "16QAM";
        st.dist = {0.006f, 0.008f, 0.008f, 0.006f, 0.012f, 0.015f,
                   0.010f, 0.024f, 0.031f, 0.842f, 0.030f, 0.008f};
        std::fill(buf.begin(), buf.end(), 0);
        ui::render_main(c, pal, st);
        canvas_to_rgb888(c, rgb.data());
        if (write_bmp("host_out/main_normal_12class_1280.bmp", rgb.data(), W, H)) ++written;
    }

    // status legend
    {
        std::fill(buf.begin(), buf.end(), 0);
        ui::render_legend(c, pal);
        canvas_to_rgb888(c, rgb.data());
        if (write_bmp("host_out/legend_status_1280.bmp", rgb.data(), W, H)) ++written;
    }

    std::printf("host_screenshot: wrote %d BMPs (1280x720 RGB565-rendered)\n", written);
    return written == 14 ? 0 : 1;   // 12 page/state + 1 12class + 1 legend
}
