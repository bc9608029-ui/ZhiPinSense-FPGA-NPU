// test_ui.cpp — host unit tests for the generic-N-class instrument UI.
//
// Covers: font glyph coverage/validity, canvas clipping, softmax/argmax/top_k/
// sanitize/band, contract validation (8..16 + mismatch + glyph safety), touch
// coordinate mapping + both touch protocols, tab hit-testing, and that draw()
// renders all three pages deterministically with no crash (including NaN/Inf
// and mismatched-class inputs).
//
//   g++ -std=gnu++17 -Wall -Wextra -O2
//       test_ui.cpp ui_renderer.cpp model_contract.cpp font.cpp touch.cpp
//       -o test_ui && ./test_ui

#include "canvas.hpp"
#include "font.hpp"
#include "ui_renderer.hpp"
#include "model_contract.hpp"
#include "touch.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond)                                                    \
    do {                                                               \
        if (cond) { ++g_pass; }                                        \
        else {                                                         \
            ++g_fail;                                                  \
            std::fprintf(stderr, "FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
        }                                                              \
    } while (0)

namespace {

ui::UiState make_state(const std::vector<float>& p) {
    ui::UiState s;
    const model::Contract c = model::contract_v1_1();
    s.class_names = c.class_names;
    s.class_count = c.class_count;
    s.prob = p;
    return s;
}

bool nearly(float a, float b) { return std::fabs(a - b) < 1e-4f; }

// count pixels that differ from the background
std::size_t non_background(const ui::Canvas& c, std::uint16_t bg) {
    std::size_t n = 0;
    for (std::size_t i = 0; i < c.pixel_count(); ++i)
        if (c.pixels()[i] != bg) ++n;
    return n;
}

} // namespace

int main() {
    std::printf("== font ==\n");
    {
        const std::string ok = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_:.%/+><()";
        for (char c : ok) {
            CHECK(font::is_supported(c));
            const font::Glyph g = font::glyph(c);
            if (c == ' ') continue;   // space is intentionally a blank glyph
            bool any_set = false;
            for (int r = 0; r < 8; ++r) {
                if (g.rows[r] != 0) any_set = true;
            }
            CHECK(any_set);   // no blank glyph for a supported non-space char
        }
        CHECK(!font::is_supported('!'));
        CHECK(!font::is_supported('a'));    // lowercase not covered
        // missing glyph is the solid block marker
        const font::Glyph b = font::glyph('!');
        CHECK(b.rows[0] == 0xFF && b.rows[6] == 0xFF && b.rows[7] == 0x00);
    }

    std::printf("== canvas: RGB565 + clipping + text ==\n");
    {
        ui::Canvas c(1280, 720);
        c.clear(ui::rgb565(10, 14, 20));
        c.set(-5, -5, 0x1234);          // negative -> no-op, no crash
        c.set(9999, 9999, 0x1234);      // out of range -> no-op
        c.set(5, 5, 0xABCD);
        CHECK(c.get(5, 5) == 0xABCD);
        CHECK(c.get(-1, -1) == 0);
        CHECK(c.get(1280, 0) == 0);

        CHECK(ui::rgb565(255, 0, 0) == 0xF800);
        CHECK(ui::rgb565(0, 255, 0) == 0x07E0);
        CHECK(ui::rgb565(0, 0, 255) == 0x001F);

        // text beyond the right edge must not crash (clipped per glyph)
        c.text(1200, 700, "OVERFLOW TEXT", 6, 0xFFFF);
        CHECK(non_background(c, ui::rgb565(10, 14, 20)) > 0);
    }

    std::printf("== softmax / sanitize / argmax / top_k / band ==\n");
    {
        const std::vector<float> logits = {4.0f, 1.0f, 0.0f, 2.0f};
        const std::vector<float> sm = ui::softmax(logits);
        float sum = 0.0f;
        for (float v : sm) sum += v;
        CHECK(nearly(sum, 1.0f));
        CHECK(ui::argmax(sm) == 0);
        CHECK(sm[0] > sm[1] && sm[1] > sm[2]);

        // NaN/Inf logits degrade safely to 0, not NaN
        const std::vector<float> bad = {std::nanf(""), INFINITY, 0.0f, 1.0f};
        const std::vector<float> sm2 = ui::softmax(bad);
        for (float v : sm2) CHECK(std::isfinite(v));

        // sanitize: reject NaN/Inf/negative, renormalize
        std::vector<float> p = {0.5f, std::nanf(""), -0.1f, INFINITY, 0.5f};
        std::string why;
        CHECK(ui::sanitize_probabilities(p, 5, &why));
        float s2 = 0.0f;
        for (float v : p) s2 += v;
        CHECK(nearly(s2, 1.0f));
        CHECK(p[1] == 0.0f && p[2] == 0.0f && p[3] == 0.0f);

        // size mismatch rejected
        std::vector<float> wrong = {0.5f, 0.5f};
        CHECK(!ui::sanitize_probabilities(wrong, 3, &why));

        // no mass rejected
        std::vector<float> empty = {0.0f, 0.0f, 0.0f};
        CHECK(!ui::sanitize_probabilities(empty, 3, &why));

        // top_k descending, tie -> lower index first
        const std::vector<float> tk = {0.1f, 0.5f, 0.3f, 0.5f, 0.0f};
        const std::vector<int> top3 = ui::top_k(tk, 3);
        CHECK(top3.size() == 3);
        CHECK(top3[0] == 1 && top3[1] == 3 && top3[2] == 2);

        // confidence bands
        CHECK(ui::confidence_band(0.90f) == ui::Band::High);
        CHECK(ui::confidence_band(0.60f) == ui::Band::Medium);
        CHECK(ui::confidence_band(0.40f) == ui::Band::Low);
    }

    std::printf("== contract validation (8..16 runtime classes) ==\n");
    {
        std::string why;
        CHECK(model::is_valid_contract(model::contract_v1_1().class_names, &why));
        CHECK(model::contract_v1_1().class_count == 10);
        CHECK(model::contract_target_12().class_count == 12);

        // 7 classes rejected
        std::vector<std::string> s7(7, "X");
        CHECK(!model::is_valid_contract(s7, &why));
        // 17 classes rejected
        std::vector<std::string> s17(17, "X");
        CHECK(!model::is_valid_contract(s17, &why));
        // 8 and 16 accepted
        std::vector<std::string> s8(8, "X");
        CHECK(model::is_valid_contract(s8, &why));
        std::vector<std::string> s16(16, "X");
        CHECK(model::is_valid_contract(s16, &why));
        // glyph-unsafe name rejected
        std::vector<std::string> sbad(8, "X");
        sbad[0] = "BAD!";
        CHECK(!model::is_valid_contract(sbad, &why));

        // validate_state: count/name/prob mismatch
        ui::UiState s = make_state(std::vector<float>(10, 0.1f));
        CHECK(ui::validate_state(s, &why));
        s.prob.resize(9);
        CHECK(!ui::validate_state(s, &why));
    }

    std::printf("== probability normalization + argmax consistency ==\n");
    {
        // logits -> softmax -> argmax == the class with the largest logit
        const std::vector<float> logits = {0.2f, 3.0f, 1.5f, 0.8f, 2.2f, 0.1f, 1.1f, 0.9f, 2.9f, 0.5f};
        const std::vector<float> p = ui::softmax(logits);
        int expected = 0;
        for (std::size_t i = 1; i < logits.size(); ++i) if (logits[i] > logits[expected]) expected = (int)i;
        CHECK(ui::argmax(p) == expected);   // 1 (3.0)
        CHECK(expected == 1);
        float sum = 0.0f;
        for (float v : p) sum += v;
        CHECK(nearly(sum, 1.0f));
    }

    std::printf("== touch mapping + protocols ==\n");
    {
        touch::TouchDecoder d(1280, 720);   // default input range 1024x600
        CHECK(d.map_x(0) == 0);
        CHECK(d.map_x(1023) == 1279);
        CHECK(d.map_x(512) == 640);
        CHECK(d.map_y(0) == 0);
        CHECK(d.map_y(599) == 719);
        CHECK(d.map_y(300) == 360);

        // protocol B: slot 0 down, move, up
        d.feed(touch::ev::EV_ABS, touch::ev::ABS_MT_SLOT, 0);
        d.feed(touch::ev::EV_ABS, touch::ev::ABS_MT_TRACKING_ID, 7);
        d.feed(touch::ev::EV_ABS, touch::ev::ABS_MT_POSITION_X, 512);
        d.feed(touch::ev::EV_ABS, touch::ev::ABS_MT_POSITION_Y, 300);
        bool frame = d.feed(touch::ev::EV_SYN, touch::ev::SYN_REPORT, 0);
        CHECK(frame);
        CHECK(d.touching());
        CHECK(d.x() == 640 && d.y() == 360);
        d.feed(touch::ev::EV_ABS, touch::ev::ABS_MT_TRACKING_ID, -1);
        d.feed(touch::ev::EV_SYN, touch::ev::SYN_REPORT, 0);
        CHECK(!d.touching());

        // protocol A fallback
        touch::TouchDecoder a(1280, 720);
        a.feed(touch::ev::EV_ABS, touch::ev::ABS_X, 1023);
        a.feed(touch::ev::EV_ABS, touch::ev::ABS_Y, 599);
        a.feed(touch::ev::EV_KEY, touch::ev::BTN_TOUCH, 1);
        a.feed(touch::ev::EV_SYN, touch::ev::SYN_REPORT, 0);
        CHECK(a.touching());
        CHECK(a.x() == 1279 && a.y() == 719);
        a.feed(touch::ev::EV_KEY, touch::ev::BTN_TOUCH, 0);
        a.feed(touch::ev::EV_SYN, touch::ev::SYN_REPORT, 0);
        CHECK(!a.touching());
    }

    std::printf("== tab hit-testing ==\n");
    {
        ui::TabHit h = ui::hit_test_tab(50, 50);
        CHECK(h.on_tab && h.page == ui::Page::Overview);
        h = ui::hit_test_tab(400, 60);
        CHECK(h.on_tab && h.page == ui::Page::AllClasses);
        h = ui::hit_test_tab(700, 60);
        CHECK(h.on_tab && h.page == ui::Page::Diagnostics);
        h = ui::hit_test_tab(50, 20);     // above the tab row
        CHECK(!h.on_tab);
        h = ui::hit_test_tab(900, 60);    // right of the tabs (status area)
        CHECK(!h.on_tab);
    }

    std::printf("== draw(): three pages deterministic + NaN/Inf safe ==\n");
    {
        ui::Renderer r;
        ui::UiState s = make_state(std::vector<float>(10, 0.1f));

        for (int pg = 0; pg < 3; ++pg) {
            ui::Canvas a(1280, 720), b(1280, 720);
            const ui::Page page = static_cast<ui::Page>(pg);
            r.draw(a, s, page);
            r.draw(b, s, page);
            CHECK(non_background(a, r.palette().background) > 1000);
            CHECK(std::memcmp(a.pixels(), b.pixels(), a.pixel_count() * 2) == 0); // deterministic
        }

        // NaN/Inf probabilities degrade safely (no crash, non-blank)
        ui::UiState nan = make_state(std::vector<float>(10, std::nanf("")));
        ui::Canvas cn(1280, 720);
        r.draw(cn, nan, ui::Page::Overview);
        CHECK(non_background(cn, r.palette().background) > 0);

        // mismatched class_count draws INVALID CONTRACT, no crash
        ui::UiState bad = make_state(std::vector<float>(10, 0.1f));
        bad.class_count = 9;
        ui::Canvas cb(1280, 720);
        r.draw(cb, bad, ui::Page::Overview);
        CHECK(non_background(cb, r.palette().background) > 0);

        // 12-class target contract renders on the All Classes page (runtime N)
        ui::UiState s12;
        s12.class_names = model::contract_target_12().class_names;
        s12.class_count = 12;
        s12.prob = std::vector<float>(12, 1.0f / 12.0f);
        ui::Canvas c12(1280, 720);
        r.draw(c12, s12, ui::Page::AllClasses);
        CHECK(non_background(c12, r.palette().background) > 1000);
    }

    std::printf("\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
