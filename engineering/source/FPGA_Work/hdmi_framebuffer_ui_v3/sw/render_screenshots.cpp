// render_screenshots.cpp — host-only offscreen screenshot generator.
//
// Renders each required UI scenario at 1280x720 (RGB565), writes a 24-bit BMP,
// writes a nearest-neighbor 1024x600 preview, and prints an FNV-1a pixel hash so
// the images are reproducible (golden).  The seven required scenarios are:
// normal, low confidence, stale, error, no signal, all classes, diagnostics —
// plus a font specimen.
//
//   g++ -std=gnu++17 -Wall -Wextra -O2
//       render_screenshots.cpp ui_renderer.cpp model_contract.cpp font.cpp
//       touch.cpp image_writer.cpp -o render_screenshots
//   ./render_screenshots [out_dir]
//
// Writes <out_dir>/<name>_1280x720.bmp, <name>_1024x600.bmp, and hashes.txt.

#include "canvas.hpp"
#include "ui_renderer.hpp"
#include "model_contract.hpp"
#include "image_writer.hpp"

#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

namespace {

struct Scenario {
    const char* name;
    ui::Page page;
    ui::UiState state;
};

std::vector<float> peaked(int n, int top, float strength) {
    std::vector<float> logits(n, 1.0f);
    logits[static_cast<std::size_t>(top)] = strength;
    return ui::softmax(logits);
}

ui::UiState base_state(const std::vector<float>& p) {
    ui::UiState s;
    const model::Contract c = model::contract_v1_1();
    s.class_names = c.class_names;
    s.class_count = c.class_count;
    s.prob = p;
    s.source = ui::Source::Mock;
    s.is_mock = true;
    s.fpga_ok = true;
    s.npu_ok = false;
    s.frame_id = 123456;
    s.fps = 60.0f;
    s.render_latency_ms = 1.23f;
    s.e2e_latency_ms = 2.34f;
    s.fb_phys_addr = 0x30100000ULL;
    s.frame_ctrl_version = 0x20230218U;
    s.front_buffer = 0;
    s.events = {"BOOT OK", "FB MAPPED 0x30100000", "FRAME CTRL VER OK", "MOCK SOURCE ACTIVE"};
    return s;
}

} // namespace

int main(int argc, char** argv) {
    const std::string out_dir = argc > 1 ? argv[1] : "screenshots";
    std::error_code ec;
    std::filesystem::create_directories(out_dir, ec);

    ui::Renderer r;

    // normal: high-confidence Top-1 (16QAM = index 7 in the 10-class contract)
    ui::UiState normal = base_state(peaked(10, 7, 5.0f));

    // low confidence: Top-1 ~0.45 (LOW band)
    ui::UiState low = base_state(std::vector<float>{
        0.02f, 0.03f, 0.02f, 0.45f, 0.08f, 0.06f, 0.05f, 0.09f, 0.10f, 0.10f});

    // stale
    ui::UiState stale = base_state(peaked(10, 5, 4.0f));
    stale.live = ui::LiveState::Stale;

    // error: diagnostics page, live=Error, error_count=3
    ui::UiState err = base_state(peaked(10, 8, 3.0f));
    err.live = ui::LiveState::Error;
    err.error_count = 3;
    err.dropped = 2;
    err.stale = 1;
    err.events.push_back("ERR: sync_for_device timeout");

    // no signal: all-zero probability mass
    ui::UiState nosig = base_state(std::vector<float>(10, 0.0f));

    // all classes (10-class, dynamic order)
    ui::UiState allc = base_state(peaked(10, 7, 4.5f));

    // diagnostics (normal-ish, full metric set + event log)
    ui::UiState diag = base_state(peaked(10, 7, 4.5f));
    diag.out_of_order = 1;
    diag.duplicate = 0;
    diag.front_buffer = 1;

    const Scenario scenarios[] = {
        {"normal",         ui::Page::Overview,     normal},
        {"low_confidence", ui::Page::Overview,     low},
        {"stale",          ui::Page::Overview,     stale},
        {"error",          ui::Page::Diagnostics,  err},
        {"no_signal",      ui::Page::Overview,     nosig},
        {"all_classes",    ui::Page::AllClasses,   allc},
        {"diagnostics",    ui::Page::Diagnostics,  diag},
    };

    std::string hashes;
    hashes.reserve(512);

    for (const Scenario& sc : scenarios) {
        ui::Canvas c(1280, 720);
        r.draw(c, sc.state, sc.page);

        const std::string bmp = out_dir + "/" + sc.name + "_1280x720.bmp";
        const std::string prev = out_dir + "/" + sc.name + "_1024x600.bmp";
        if (!img::write_bmp(bmp, c.pixels(), c.width(), c.height())) {
            std::fprintf(stderr, "FAIL: cannot write %s\n", bmp.c_str());
            return 1;
        }
        std::vector<std::uint16_t> small = img::downscale(c.pixels(), 1280, 720, 1024, 600);
        if (!img::write_bmp(prev, small.data(), 1024, 600)) {
            std::fprintf(stderr, "FAIL: cannot write %s\n", prev.c_str());
            return 1;
        }
        const std::uint64_t h = img::fnv1a_pixels(c.pixels(), c.pixel_count());
        char line[128];
        std::snprintf(line, sizeof line, "%s %016llx\n", sc.name,
                      static_cast<unsigned long long>(h));
        hashes += line;
        std::printf("SCREENSHOT %-16s hash=%016llx\n", sc.name,
                    static_cast<unsigned long long>(h));
    }

    // font specimen
    {
        ui::Canvas c(1280, 720);
        c.clear(r.palette().surface);
        c.text(16, 16, "FONT SPECIMEN", 4, r.palette().text_primary);
        const std::string glyphs =
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_:.%/+><()";
        int col = 0, row = 0;
        const int cell_w = 96, cell_h = 56;
        const int x0 = 16, y0 = 120;
        for (char g : glyphs) {
            if (col == 12) { col = 0; ++row; }
            const int x = x0 + col * cell_w;
            const int y = y0 + row * cell_h;
            c.rect(x, y, cell_w - 8, cell_h - 8, r.palette().outline, 1);
            c.glyph(x + 8, y + 8, g, 3, r.palette().text_primary);
            ++col;
        }
        const std::string bmp = out_dir + "/font_specimen_1280x720.bmp";
        if (!img::write_bmp(bmp, c.pixels(), c.width(), c.height())) {
            std::fprintf(stderr, "FAIL: cannot write %s\n", bmp.c_str());
            return 1;
        }
        const std::uint64_t h = img::fnv1a_pixels(c.pixels(), c.pixel_count());
        hashes += "font_specimen ";
        hashes += [&] { char buf[24]; std::snprintf(buf, sizeof buf, "%016llx\n",
                       static_cast<unsigned long long>(h)); return std::string(buf); }();
        std::printf("SCREENSHOT %-16s hash=%016llx\n", "font_specimen",
                    static_cast<unsigned long long>(h));
    }

    const std::string hash_path = out_dir + "/hashes.txt";
    std::FILE* hf = std::fopen(hash_path.c_str(), "wb");
    if (hf) { std::fwrite(hashes.data(), 1, hashes.size(), hf); std::fclose(hf); }

    std::printf("WROTE %d scenarios + font specimen to %s/\n",
                static_cast<int>(sizeof(scenarios) / sizeof(scenarios[0])), out_dir.c_str());
    return 0;
}
