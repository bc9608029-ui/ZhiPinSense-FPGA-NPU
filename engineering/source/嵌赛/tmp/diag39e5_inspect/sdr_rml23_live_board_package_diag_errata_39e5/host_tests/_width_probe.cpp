#include "../ui_sw/font_atlas.hpp"
#include <cstdio>

int main() {
    auto pr = [](const char* name, const char* s, ui::Weight w, int sz) {
        const ui::font_t* f = ui::font_get(w, sz);
        std::printf("%-14s %-16s w=%2d size=%2d : %d\n", name, s, (int)w, sz,
                    f ? ui::text_width(s, f) : -1);
    };
    pr("DISCONNECTED", "DISCONNECTED", ui::Weight::Bold, 20);
    pr("CONNECTED", "CONNECTED", ui::Weight::Bold, 20);
    pr("BAND SCAN", "BAND SCAN", ui::Weight::Bold, 20);
    pr("AUTO LOCK", "AUTO LOCK", ui::Weight::Bold, 20);
    pr("RUNNING", "RUNNING", ui::Weight::Bold, 20);
    pr("NO SIGNAL", "NO SIGNAL", ui::Weight::Bold, 20);
    pr("STALE", "STALE", ui::Weight::Bold, 20);
    pr("ERROR", "ERROR", ui::Weight::Bold, 20);
    pr("sha8", "12345678", ui::Weight::Mono, 20);
    pr("sha8", "2425d990", ui::Weight::Mono, 20);
    pr("caption", "RML23-AMSSB-MERGED", ui::Weight::Regular, 20);
    pr("DIAGNOSTICS", "DIAGNOSTICS", ui::Weight::Bold, 28);
    pr("TOUCH TEST", "TOUCH TEST", ui::Weight::Bold, 28);
    pr("AM-DSB-SC40", "AM-DSB-SC", ui::Weight::Bold, 40);
    pr("100.0%28", "100.0%", ui::Weight::Bold, 28);
    pr("AM-DSB-SC20", "AM-DSB-SC", ui::Weight::Bold, 20);
    pr("100.0% mono20", "100.0%", ui::Weight::Mono, 20);
    return 0;
}
