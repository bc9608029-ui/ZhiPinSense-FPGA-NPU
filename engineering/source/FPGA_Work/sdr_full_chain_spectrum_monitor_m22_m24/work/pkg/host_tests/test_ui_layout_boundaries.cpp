// test_ui_layout_boundaries.cpp -- M22.1 UI 视觉重构 boundary regression.
//
// Drives the real renderers through the optional text TRACE (font_atlas.hpp) and
// asserts, with the renderer's OWN measured bounding boxes, every §五 requirement:
//
//   1. every text bbox lies inside its parent container (region_rect);
//   2. no two text bboxes inside the same container intersect;
//   3. value and unit columns never overlap (and are each column-aligned);
//   4. the top status bar fields never cover one another;
//   5. the three bottom-nav zones never overlap (and each tab stays in its zone);
//   6. the MODE buttons + START/STOP never overlap (visual == touch rect);
//   7. worst-case long class names / status texts / exception texts still fit;
//   8. ERROR / STALE / MOCK / LIVE all render without overflow;
//   9. SELECTED / PENDING / IDLE all render without overflow;
//  10. target resolution passes, a smaller resolution fail-closes to the
//      centered fallback (no overflow);
//  11. the visual button rectangles equal the touch hit-test rectangles;
//  12. the frozen nav band still equals the touch geometry (acceptance intact).
//
// It complements test_ui_layout_m19.cpp (structural constants) by checking the
// ACTUAL pixel layout through real font metrics.  Build: see build_host_tests.sh.

#include "../board_package/touch_geometry.hpp"   // ui_touch::kNavY0/..
#include "../ui_sw/ui_layout.hpp"
#include "../ui_sw/ui_render.hpp"
#include "../ui_sw/ui_theme.hpp"

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

// ---- render + trace harness -------------------------------------------------
struct TraceResult {
    std::vector<ui::TracedText> texts;
};

TraceResult render_traced(int W, int H,
                         void (*fn)(ui::Canvas&, const ui::Theme&, const ui::UiState&),
                         const ui::UiState& st) {
    const ui::Theme& th = ui::theme_default();
    std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H, th.background);
    ui::Canvas c{px.data(), W, H};
    std::vector<ui::TracedText> out;
    std::vector<ui::TracedText>* prev = ui::text_trace_begin(&out);
    fn(c, th, st);
    ui::text_trace_end(prev);
    return TraceResult{out};
}

bool bbox_inside(const ui::TracedText& t, int x0, int y0, int x1, int y1) {
    return t.x0 >= x0 && t.y0 >= y0 && t.x1 <= x1 && t.y1 <= y1;
}
bool bbox_intersect(const ui::TracedText& a, const ui::TracedText& b) {
    return !(a.x1 < b.x0 || b.x1 < a.x0 || a.y1 < b.y0 || b.y1 < a.y0);
}

// (1)+(2): containment + intra-container non-overlap, across every region that
// has any traced text.
void check_containment_overlap(const TraceResult& tr, const ui::layout::LayoutMetrics& lm,
                               const char* page) {
    for (int r = 0; r < ui::region::kCount; ++r) {
        std::vector<const ui::TracedText*> group;
        for (const auto& t : tr.texts) if (t.region == r) group.push_back(&t);
        if (group.empty()) continue;
        int x0, y0, x1, y1;
        if (!ui::region_rect(r, lm, x0, y0, x1, y1)) continue;
        for (const auto* t : group) {
            char msg[160];
            std::snprintf(msg, sizeof msg, "%s: region %d text '%s' inside container",
                          page, r, t->text.c_str());
            check(bbox_inside(*t, x0, y0, x1, y1), msg);
        }
        for (std::size_t i = 0; i < group.size(); ++i)
            for (std::size_t j = i + 1; j < group.size(); ++j) {
                char msg[200];
                std::snprintf(msg, sizeof msg,
                              "%s: region %d no overlap '%s' vs '%s'",
                              page, r, group[i]->text.c_str(), group[j]->text.c_str());
                check(!bbox_intersect(*group[i], *group[j]), msg);
            }
    }
}

// (3): value/unit column separation + alignment, for the four parameter cards.
void check_param_columns(const TraceResult& tr) {
    const int cards[4] = {ui::region::kSignalLevel, ui::region::kSpectrum,
                          ui::region::kSignalQuality, ui::region::kRfConfig};
    for (int card : cards) {
        int val_right = -100000, unit_left = 100000;
        bool any_val = false, any_unit = false, aligned = true;
        for (const auto& t : tr.texts) {
            if (t.region != card) continue;
            if (t.kind == static_cast<int>(ui::TextKind::Value)) {
                any_val = true;
                if (val_right == -100000) val_right = t.x1; else if (t.x1 != val_right) aligned = false;
                if (t.x1 > val_right) val_right = t.x1;
            } else if (t.kind == static_cast<int>(ui::TextKind::Unit)) {
                any_unit = true;
                if (unit_left == 100000) unit_left = t.x0; else if (t.x0 != unit_left) aligned = false;
                if (t.x0 < unit_left) unit_left = t.x0;
            }
        }
        if (any_val) check(aligned, "value column right-aligned within a card");
        if (any_unit) check(aligned, "unit column left-aligned within a card");
        if (any_val && any_unit)
            check(val_right < unit_left, "value column ends before unit column begins");
    }
}

// (5): the three nav zones are disjoint and each tab's text stays in its zone.
void check_nav_zones(const TraceResult& tr, const ui::layout::LayoutMetrics& lm) {
    const int tw = lm.w / 3;
    for (int i = 0; i < 3; ++i) {
        const int zx0 = i * tw, zx1 = zx0 + tw - 1;
        for (int j = i + 1; j < 3; ++j) {
            const int ox0 = j * tw, ox1 = ox0 + tw - 1;
            check(zx1 < ox0 || ox1 < zx0, "nav zones are disjoint");
        }
        // each nav tab text (the longest label in the band) stays inside its zone
        for (const auto& t : tr.texts) {
            if (t.region != ui::region::kNav) continue;
            if (t.x0 >= zx0 && t.x0 <= zx1)
                check(t.x1 <= zx1, "nav tab text stays inside its zone");
        }
    }
}

// ---- representative states --------------------------------------------------
ui::UiState base() {
    ui::UiState st;
    st.status = ui::Status::Live;
    st.source = "SDR";
    st.top1 = "QPSK";
    st.conf = 0.71f;
    std::vector<float> d(12, 0.026363636f);
    d[7] = 0.71f;
    st.dist = d;
    st.classes = &ui::classes_12();
    st.snr = "+18.5 dB";
    st.lat = "12.4 ms";
    st.frame = "240";
    st.model = "abcdef01";
    st.work_mode = "FIXED";
    st.running = true;
    st.ctl_connected = "CONTROL CONNECTED";
    return st;
}

// A 24-class contract with the longest names the renderer may ever receive.
const std::vector<std::string>& classes_24_long() {
    static const std::vector<std::string> v = {
        "OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK",
        "16APSK","32APSK","64APSK","128APSK","16QAM","32QAM","64QAM",
        "128QAM","256QAM","AM-SSB-WC","AM-SSB-SC","AM-DSB-WC","AM-DSB-SC",
        "FM","GMSK","OQPSK"
    };
    return v;
}

ui::UiState params_worst() {
    ui::UiState st = base();
    st.meas.valid = true;
    st.meas.rms_counts = 1234.5;
    st.meas.peak_counts = 9999.9;
    st.meas.papr_db = 12.34;
    st.meas.clip_ratio = 0.5;                 // 50.00 %
    st.meas.power_dbfs = -123.45;
    st.meas.noise_floor_dbfs = -123.45;
    st.meas.psd_peak_prominence_db = 99.999;
    st.meas.snr_est_db = 123.4;
    st.meas.occupied_bins = 999999;           // wide integer
    st.meas.spectral_centroid_hz = 999999.9;
    st.meas.occupied_bw_hz = 123456.7;
    st.meas.model_rms = 999.999;
    st.presence = "SIGNAL_PRESENT";           // longest text value
    st.level_mode = "AUTO LOCK";
    st.model_scale = 123.456;
    st.rf_gain_db = 123.4;
    st.source = "EXTERNAL ANTENNA";           // long info-strip source
    st.snr = "+123.4 dB";
    st.lat = "999.9 ms";
    st.frame = "100000";
    st.model = "1234567890abcdef";
    return st;
}

void run_all_checks(const char* page, int W, int H, const ui::UiState& st,
                    void (*fn)(ui::Canvas&, const ui::Theme&, const ui::UiState&)) {
    const ui::layout::LayoutMetrics lm = ui::layout::layout_metrics(W, H);
    check(lm.fit, "target resolution fits");
    const TraceResult tr = render_traced(W, H, fn, st);
    check_containment_overlap(tr, lm, page);
    check_nav_zones(tr, lm);
}

}  // namespace

int main() {
    std::printf("test_ui_layout_boundaries\n");

    const int W = 1280, H = 720;
    const ui::layout::LayoutMetrics lm = ui::layout::layout_metrics(W, H);

    // (10) target resolution fits.
    check(lm.fit, "1280x720 fits");
    check(lm.content_x0 == 24 && lm.content_x1 == 1256, "content margins at target");
    check(lm.col_w == 608, "two-column width at target");

    // ---- (8) ERROR / STALE / MOCK / LIVE + worst-case names all render clean ---
    {
        ui::UiState st = base();
        run_all_checks("main_live", W, H, st, ui::render_main);
    }
    {
        ui::UiState st = base(); st.status = ui::Status::Stale; st.age = "3.2 s";
        run_all_checks("main_stale", W, H, st, ui::render_main);
    }
    {
        ui::UiState st = base(); st.status = ui::Status::Error;
        run_all_checks("main_error", W, H, st, ui::render_main);
    }
    {
        ui::UiState st = base(); st.status = ui::Status::Mock; st.source = "MOCK";
        run_all_checks("main_mock", W, H, st, ui::render_main);
    }
    // (7) longest class name drives the 40px top-1 + a top-3 row.
    {
        ui::UiState st = base();
        st.classes = &classes_24_long();
        std::vector<float> d(24, 0.005f);
        d[17] = 0.71f;   // "AM-SSB-WC" is the longest name
        d[20] = 0.10f;   // "AM-DSB-SC"
        d[3]  = 0.08f;
        st.dist = d;
        st.top1 = "AM-SSB-WC";
        run_all_checks("main_long_class", W, H, st, ui::render_main);
    }
    {
        ui::UiState st = params_worst();
        const TraceResult tr = render_traced(W, H, ui::render_parameters, st);
        check_containment_overlap(tr, lm, "parameters_worst");
        check_param_columns(tr);
        check_nav_zones(tr, lm);
    }
    // (9) SELECTED / PENDING / IDLE (three distinct mode-button states).
    {
        ui::UiState st = base(); st.work_mode = "AUTO LOCK";
        st.requested_mode = "BAND SCAN"; st.command_status = "PENDING";
        run_all_checks("mode_pending", W, H, st, ui::render_mode);
    }
    {
        ui::UiState st = base(); st.work_mode = "BAND SCAN";
        st.requested_mode = "BAND SCAN"; st.command_status = "APPLIED";
        run_all_checks("mode_selected", W, H, st, ui::render_mode);
    }
    {
        ui::UiState st = base(); st.running = false; st.requested_running = false;
        st.command_status = "REJECTED"; st.feedback = "ALREADY IN THIS MODE";
        st.last_command = "SET_MODE AUTO LOCK";
        st.ctl_connected = "CONTROL DISCONNECTED";
        run_all_checks("mode_idle", W, H, st, ui::render_mode);
    }
    // Secondary pages (still clip + trace + contain).
    {
        ui::UiState st = base();
        run_all_checks("diag", W, H, st, ui::render_diag);
        st.touch.device = "/dev/input/event2";
        st.touch.vendor = "1a86:e5e3";
        st.touch.axis_x = "0 .. 4095";
        st.touch.mapping_x = "raw_x*1280/4095";
        st.touch.last_x = 640; st.touch.last_y = 360;
        run_all_checks("touch", W, H, st, ui::render_touch);
    }

    // ---- (11) visual button rect == touch hit-test rect -----------------------
    for (int i = 0; i < 3; ++i) {
        int vx0, vy0, vx1, vy1, tx0, ty0, tx1, ty1;
        ui::region_rect(ui::region::kModeBtn0 + i, lm, vx0, vy0, vx1, vy1);
        ui::mode_ui::button_rect(i, tx0, ty0, tx1, ty1);
        check(vx0 == tx0 && vy0 == ty0 && vx1 == tx1 && vy1 == ty1,
              "mode button visual rect == touch rect");
    }
    {
        int vx0, vy0, vx1, vy1, tx0, ty0, tx1, ty1;
        ui::region_rect(ui::region::kRunStart, lm, vx0, vy0, vx1, vy1);
        ui::mode_ui::button_rect(ui::mode_ui::kBtnStart, tx0, ty0, tx1, ty1);
        check(vx0 == tx0 && vy0 == ty0 && vx1 == tx1 && vy1 == ty1, "START visual == touch");
        ui::region_rect(ui::region::kRunStop, lm, vx0, vy0, vx1, vy1);
        ui::mode_ui::button_rect(ui::mode_ui::kBtnStop, tx0, ty0, tx1, ty1);
        check(vx0 == tx0 && vy0 == ty0 && vx1 == tx1 && vy1 == ty1, "STOP visual == touch");
    }
    // Buttons never overlap one another (6).
    for (int i = 0; i < ui::mode_ui::kBtnCount; ++i)
        for (int j = i + 1; j < ui::mode_ui::kBtnCount; ++j) {
            int ax0, ay0, ax1, ay1, bx0, by0, bx1, by1;
            ui::mode_ui::button_rect(i, ax0, ay0, ax1, ay1);
            ui::mode_ui::button_rect(j, bx0, by0, bx1, by1);
            check(ax1 < bx0 || bx1 < ax0 || ay1 < by0 || by1 < ay0,
                  "mode/run buttons never overlap");
        }

    // ---- (12) frozen nav band == touch geometry ------------------------------
    {
        int x0, y0, x1, y1;
        ui::region_rect(ui::region::kNav, lm, x0, y0, x1, y1);
        check(y0 == ui_touch::kNavY0 && y1 == ui_touch::kNavY1, "nav visual == touch band");
    }

    // ---- (10) smaller resolution fail-closes to the centered fallback --------
    {
        const int SW = 640, SH = 480;
        const ui::layout::LayoutMetrics sm = ui::layout::layout_metrics(SW, SH);
        check(!sm.fit, "640x480 is below the minimum (fail-closed)");
        const ui::UiState st = base();
        const TraceResult tr = render_traced(SW, SH, ui::render_main, st);
        // Only fallback-region texts appear, and they stay inside the small canvas.
        for (const auto& t : tr.texts) {
            check(t.region == ui::region::kFallback, "fallback-only at small resolution");
            check(bbox_inside(t, 0, 0, SW - 1, SH - 1), "fallback text inside small canvas");
        }
        check(!tr.texts.empty(), "fallback drew a message");
    }
    {
        const int SW = 800, SH = 600;
        const ui::layout::LayoutMetrics sm = ui::layout::layout_metrics(SW, SH);
        check(!sm.fit, "800x600 is below the minimum height (fail-closed)");
    }

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
