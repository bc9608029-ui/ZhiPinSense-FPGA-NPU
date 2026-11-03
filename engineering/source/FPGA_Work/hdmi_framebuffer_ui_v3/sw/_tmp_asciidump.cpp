#include "canvas.hpp"
#include "ui_renderer.hpp"
#include "model_contract.hpp"
#include <cstdio>
#include <vector>
#include <string>

static std::vector<float> peaked(int n, int top, float strength) {
    std::vector<float> logits(n, 1.0f);
    logits[top] = strength;
    return ui::softmax(logits);
}
static ui::UiState base(const std::vector<float>& p) {
    ui::UiState s; const model::Contract c = model::contract_v1_1();
    s.class_names = c.class_names; s.class_count = c.class_count; s.prob = p;
    s.source = ui::Source::Mock; s.is_mock = true; s.fpga_ok = true; s.npu_ok = false;
    s.frame_id = 123456; s.fps = 60.0f; s.render_latency_ms = 1.23f; s.e2e_latency_ms = 2.34f;
    s.fb_phys_addr = 0x30100000ULL; s.frame_ctrl_version = 0x20230218U; s.front_buffer = 0;
    s.events = {"BOOT OK","FB MAPPED 0x30100000","FRAME CTRL VER OK","MOCK SOURCE ACTIVE"};
    return s;
}
static void dump(const char* name, const ui::UiState& st, ui::Page pg) {
    ui::Renderer r; ui::Canvas c(1280,720); r.draw(c, st, pg);
    const int C=128, R=36, cw=1280/C, ch=720/R;
    const char* ramp = " .:-=+*#%@";
    std::printf("==== %s ====\n", name);
    for (int ry=0; ry<R; ++ry) {
        for (int rx=0; rx<C; ++rx) {
            long sum=0; int n=0;
            for (int y=ry*ch; y<(ry+1)*ch; y+=2)
                for (int x=rx*cw; x<(rx+1)*cw; x+=2) {
                    std::uint16_t p=c.get(x,y);
                    int r=(p>>11)&0x1f, g=(p>>5)&0x3f, b=p&0x1f;
                    sum += (r*77 + g*150 + b*29) / 256; ++n;
                }
            int lvl = n? (int)(sum/n) : 0;
            int idx = lvl*9/255; if (idx<0) idx=0; if (idx>9) idx=9;
            std::putchar(ramp[idx]);
        }
        std::putchar(10);
    }
}
int main() {
    dump("OVERVIEW normal", base(peaked(10,7,5.0f)), ui::Page::Overview);
    dump("ALL CLASSES 10", base(peaked(10,7,4.5f)), ui::Page::AllClasses);
    dump("DIAGNOSTICS", base(peaked(10,7,4.5f)), ui::Page::Diagnostics);
    return 0;
}
