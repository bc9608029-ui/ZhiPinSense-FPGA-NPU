// test_waterfall_history.cpp -- host tests for the bounded waterfall ring buffer
// (fix10class24-waterfall1, Phase D).
//
// Pins the live-path invariants: fixed 128-row / 256-bin capacity (no growth, no
// per-frame allocation), 10 Hz row-advance cap, same-frame_id dedup, frame-id
// regression rejection, reconnect clear(), ring ordering, defensive clamping, and
// the presence-state advance policy.

#include "../ui_sw/waterfall_history.hpp"

#include <cstdio>
#include <cstring>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void fill_row(std::int16_t* p, int v) {
    for (int b = 0; b < ui::kWaterfallBins; ++b) p[b] = static_cast<std::int16_t>(v);
}

// (1) bounded capacity: pushing far more than 128 rows keeps exactly 128.
void test_bounded() {
    ui::WaterfallHistory h;
    std::int16_t row[ui::kWaterfallBins];
    for (int i = 0; i < 300; ++i) {
        fill_row(row, -100);
        h.push(row, static_cast<std::uint64_t>(i + 1),
               static_cast<std::uint64_t>(i) * 100);
    }
    check(h.size() == 128, "300 pushes -> size capped at 128");
}

// (2) fixed memory: the whole history is a fixed std::array (tens of KB), no heap.
void test_fixed_memory() {
    const std::size_t expect = static_cast<std::size_t>(ui::kWaterfallMaxRows) *
                               static_cast<std::size_t>(ui::kWaterfallBins) * 2;
    check(sizeof(ui::WaterfallHistory) <= expect + 256,
          "sizeof(WaterfallHistory) is a fixed ~64 KiB (no heap growth)");
    check(sizeof(ui::WaterfallHistory) >= expect,
          "ring storage is actually resident (not indirected)");
}

// (3) 10 Hz cap: two pushes 50 ms apart -> only the first is accepted.
void test_rate_cap() {
    ui::WaterfallHistory h;
    std::int16_t row[ui::kWaterfallBins];
    fill_row(row, -60);
    check(h.push(row, 1, 1000), "first push accepted");
    check(!h.push(row, 2, 1050), "push 50 ms later rejected (10 Hz cap)");
    check(h.size() == 1, "rate-capped push did not advance history");
    check(h.push(row, 3, 1100), "push 100 ms later accepted");
    check(h.size() == 2, "accepted push advanced history");
}

// (4) same frame_id never advances twice.
void test_same_frame_dedup() {
    ui::WaterfallHistory h;
    std::int16_t row[ui::kWaterfallBins];
    fill_row(row, -40);
    check(h.push(row, 7, 2000), "first frame accepted");
    check(!h.push(row, 7, 3000), "same frame_id rejected even later in time");
    check(h.size() == 1, "dedup kept history at one row");
}

// (5) frame_id regression is rejected (no pollution from a producer restart).
void test_frame_regression() {
    ui::WaterfallHistory h;
    std::int16_t row[ui::kWaterfallBins];
    fill_row(row, -50);
    check(h.push(row, 5, 1000), "frame 5 accepted");
    check(!h.push(row, 3, 2000), "frame 3 (regression) rejected");
    check(!h.push(row, 5, 3000), "frame 5 (repeat) rejected");
    check(h.push(row, 6, 4000), "frame 6 accepted after regression ignored");
}

// (6) clear() empties the ring for a producer reconnect.
void test_clear() {
    ui::WaterfallHistory h;
    std::int16_t row[ui::kWaterfallBins];
    fill_row(row, -30);
    for (int i = 0; i < 10; ++i) h.push(row, static_cast<std::uint64_t>(i + 1),
                                         static_cast<std::uint64_t>(i) * 100);
    check(h.size() == 10, "precondition: 10 rows");
    h.clear();
    check(h.empty() && h.size() == 0, "clear() empties the history");
    check(h.push(row, 1, 100), "history reusable after clear (fresh producer)");
}

// (7) ring ordering: row(0) is oldest, newest() is the most recent row.
void test_ordering() {
    ui::WaterfallHistory h;
    std::int16_t row[ui::kWaterfallBins];
    for (int i = 0; i < 3; ++i) {
        fill_row(row, -10 - i);
        h.push(row, static_cast<std::uint64_t>(i + 1),
               static_cast<std::uint64_t>(i) * 100);
    }
    check(h.row(0)[0] == -10, "row(0) is the oldest row");
    check(h.row(2)[0] == -12, "row(2) is the newest row");
    check(h.newest()[0] == -12, "newest() returns the most recent row");
}

// (8) defensive clamping: out-of-range values are clamped into [-480, 0].
void test_clamp() {
    ui::WaterfallHistory h;
    std::int16_t row[ui::kWaterfallBins];
    fill_row(row, -999);
    row[0] = 5;     // above the ceiling -> clamped to 0
    row[1] = -999;  // below the floor -> clamped to -480
    check(h.push(row, 1, 100), "clamped row accepted");
    check(h.newest()[0] == 0, "value above 0 clamped to 0");
    check(h.newest()[1] == -480, "value below -480 clamped to -480");
}

// (9) presence-state advance policy (which states carry a real spectrum row).
void test_advance_policy() {
    check(ui::waterfall_advance_on_presence("SIGNAL_PRESENT"), "SIGNAL_PRESENT advances");
    check(ui::waterfall_advance_on_presence("NO_SIGNAL"), "NO_SIGNAL advances (real noise)");
    check(ui::waterfall_advance_on_presence("ACQUIRING"), "ACQUIRING advances (transitional)");
    check(!ui::waterfall_advance_on_presence("SIGNAL_LOST"), "SIGNAL_LOST does not advance");
    check(!ui::waterfall_advance_on_presence("INVALID"), "INVALID does not advance");
    check(!ui::waterfall_advance_on_presence(""), "empty presence never advances");
    check(!ui::waterfall_advance_on_presence("BOGUS"), "unknown presence never advances");
}

}  // namespace

int main() {
    std::printf("test_waterfall_history\n");
    test_bounded();
    test_fixed_memory();
    test_rate_cap();
    test_same_frame_dedup();
    test_frame_regression();
    test_clear();
    test_ordering();
    test_clamp();
    test_advance_policy();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
