// test_ui_rml23.cpp -- host tests for the RML23 UI layer (M29 Phase F5): the
// 23-class label contract (classes_23/24), the RML23 state mapping
// (map_to_state_rml23), and render_main's paginated 23-class category table
// (page clamp, per-page distinct content, model_mode caption, empty-dist safety,
// and 12-class backward compatibility).
//
// Links the REAL render stack (ui_sw/font_atlas.cpp + font_atlas_data.cpp +
// ui_render.cpp) so the table runs the exact code the board draws, and is run
// under ASan/UBSan so any render out-of-bounds write is caught here, not on the
// board.
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/chain_common.hpp"
#include "../board_package/ui_state_map.hpp"
#include "../ui_sw/ui_render.hpp"

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

const int kW = 1280, kH = 720;

ui::Canvas make_canvas(std::vector<std::uint16_t>& px) {
    px.assign(static_cast<std::size_t>(kW) * kH, 0);
    return ui::Canvas{px.data(), kW, kH};
}

std::size_t non_bg(const ui::Canvas& c, const ui::Theme& pal) {
    std::size_t n = 0;
    const std::size_t total = static_cast<std::size_t>(c.w) * c.h;
    for (std::size_t i = 0; i < total; ++i)
        if (c.px[i] != pal.background) ++n;
    return n;
}

std::size_t diff_count(const ui::Canvas& a, const ui::Canvas& b) {
    std::size_t n = 0;
    const std::size_t total = static_cast<std::size_t>(a.w) * a.h;
    for (std::size_t i = 0; i < total; ++i)
        if (a.px[i] != b.px[i]) ++n;
    return n;
}

// A clean 23-class RML23 frame (raw-24 peak at 5 -> merged-23 "8PSK").
rf::ResultFrame rml23_frame() {
    const cat::Contract c23 = chain::contract_23();
    std::vector<float> raw24(24, -10.0f);
    raw24[5] = 4.0f;
    std::vector<float> merged23(23, -10.0f);
    merged23[5] = 4.0f;
    rf::ResultFrame r;
    r.frame_id = 7;
    r.source = "fpga_npu";
    r.mock = false;
    chain::fill_result_rml23(r, raw24, merged23, c23, "2425d990dbac0761", 6.0);
    return r;
}

// (1) the 23/24-class label orders are frozen and equal to the SDR contracts.
void test_classes_orders() {
    const cat::Contract c23 = chain::contract_23();
    const cat::Contract c24 = chain::contract_24();
    const std::vector<std::string>& u23 = ui::classes_23();
    const std::vector<std::string>& u24 = ui::classes_24();

    check(u23.size() == 23, "classes_23 size == 23");
    check(u24.size() == 24, "classes_24 size == 24");

    bool eq23 = true, eq24 = true;
    for (int i = 0; i < 23; ++i)
        if (u23[static_cast<std::size_t>(i)] != cat::label(c23, i)) eq23 = false;
    for (int i = 0; i < 24; ++i)
        if (u24[static_cast<std::size_t>(i)] != cat::label(c24, i)) eq24 = false;
    check(eq23, "classes_23 == cat::target_23 element-for-element");
    check(eq24, "classes_24 == cat::target_24 element-for-element");

    check(u23[17] == "AM-SSB", "classes_23 slot 17 == AM-SSB");
    check(u24[17] == "AM-SSB-WC", "classes_24 slot 17 == AM-SSB-WC");
    check(u24[18] == "AM-SSB-SC", "classes_24 slot 18 == AM-SSB-SC");
}

// (2) map_to_state_rml23 sets the 23-class identity + width.
void test_mapping_rml23() {
    ui::UiState st = ui::map_to_state_rml23(rml23_frame());
    check(st.classes == &ui::classes_23(), "map_to_state_rml23 classes == classes_23");
    check(st.model_mode == "RML23-AMSSB-MERGED", "map_to_state_rml23 model_mode");
    check(st.class_count == 23, "map_to_state_rml23 class_count == 23");
    check(st.category_page == 0, "map_to_state_rml23 category_page == 0");
    check(st.top1 == "8PSK", "map_to_state_rml23 top1 == 8PSK");
    check(st.dist.size() == 23, "map_to_state_rml23 dist width 23");
}

// (3) render_main paginated category table: every page draws, pages differ,
//     and out-of-range pages clamp exactly.
void test_render_pagination() {
    const ui::Theme& pal = ui::theme_default();
    const ui::UiState base = ui::map_to_state_rml23(rml23_frame());

    std::vector<std::uint16_t> p0b, p1b, p2b, p3b, hi, lo, empty;
    ui::Canvas c0 = make_canvas(p0b), c1 = make_canvas(p1b);
    ui::Canvas c2 = make_canvas(p2b), c3 = make_canvas(p3b);
    ui::Canvas ch = make_canvas(hi), cl = make_canvas(lo), ce = make_canvas(empty);

    ui::UiState s0 = base; s0.category_page = 0; ui::render_main(c0, pal, s0);
    ui::UiState s1 = base; s1.category_page = 1; ui::render_main(c1, pal, s1);
    ui::UiState s2 = base; s2.category_page = 2; ui::render_main(c2, pal, s2);
    ui::UiState s3 = base; s3.category_page = 3; ui::render_main(c3, pal, s3);

    check(non_bg(c0, pal) > 10000, "render_main page 0 draws content");
    check(non_bg(c1, pal) > 10000, "render_main page 1 draws content");
    check(non_bg(c2, pal) > 10000, "render_main page 2 draws content");
    check(non_bg(c3, pal) > 10000, "render_main page 3 draws content");

    check(diff_count(c0, c1) > 0, "page 0 and page 1 show different rows");
    check(diff_count(c1, c2) > 0, "page 1 and page 2 show different rows");
    check(diff_count(c2, c3) > 0, "page 2 and page 3 show different rows");

    // 23 classes, 6 rows/page -> 4 pages (0..3).  Clamp out-of-range pages exactly.
    ui::UiState shi = base; shi.category_page = 999; ui::render_main(ch, pal, shi);
    ui::UiState slo = base; slo.category_page = -5;  ui::render_main(cl, pal, slo);
    check(diff_count(ch, c3) == 0, "category_page 999 clamps to last page (== page 3)");
    check(diff_count(cl, c0) == 0, "category_page -5 clamps to first page (== page 0)");

    // Empty distribution still renders the table with placeholders (no crash).
    ui::UiState se = base; se.dist.clear(); ui::render_main(ce, pal, se);
    check(non_bg(ce, pal) > 10000, "render_main empty-dist 23-class draws content");
}

// (4) the model_mode caption is actually drawn (top bar changes when it clears).
void test_render_model_mode_caption() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<std::uint16_t> wa, wb;
    ui::Canvas ca = make_canvas(wa), cb = make_canvas(wb);

    ui::UiState sa = ui::map_to_state_rml23(rml23_frame());
    ui::UiState sb = sa; sb.model_mode.clear();

    ui::render_main(ca, pal, sa);
    ui::render_main(cb, pal, sb);
    check(diff_count(ca, cb) > 0, "model_mode caption changes the top bar");
}

// (5) 12-class pages keep the M19 top-3 path (no category-table regression).
void test_render_12class_backward_compat() {
    const ui::Theme& pal = ui::theme_default();
    std::vector<float> logits(12, -10.0f);
    logits[5] = 4.0f;
    rf::ResultFrame r;
    r.frame_id = 1;
    chain::fill_result(r, logits, chain::contract_12(), "2ae95275fe36", 6.0);

    ui::UiState st = ui::map_to_state(r);
    check(st.class_count == 0, "12-class state class_count stays 0 (legacy path)");
    check(st.model_mode.empty(), "12-class state has no model_mode caption");

    std::vector<std::uint16_t> px;
    ui::Canvas c = make_canvas(px);
    ui::render_main(c, pal, st);
    check(non_bg(c, pal) > 10000, "render_main 12-class draws top-3 content");
}

}  // namespace

int main() {
    std::printf("test_ui_rml23\n");
    test_classes_orders();
    test_mapping_rml23();
    test_render_pagination();
    test_render_model_mode_caption();
    test_render_12class_backward_compat();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
