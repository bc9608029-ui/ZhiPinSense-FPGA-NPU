#pragma once

// waterfall_history.hpp -- bounded real-time display-spectrum history
// (fix10class24-waterfall1, Phase D).
//
// A fixed-capacity ring buffer of 256-bin display-spectrum rows for the waterfall
// heatmap.  Designed for the board live path:
//
//   * 256 int16_t bins per row (dBFS x4, range [-480, 0]); 128 rows max, so the
//     whole history is a fixed 128 x 256 x 2 = 64 KiB.  No heap allocation, no
//     vector growth, no per-frame realloc -- `push` only writes one ring slot.
//   * 10 Hz update cap: a row is accepted at most once per kWaterfallMinIntervalMs
//     (100 ms), so a 30 fps feed advances the heatmap at most 10 rows/second.
//   * Only a NEW spectrum row advances history: the same frame_id never advances
//     twice, and a frame_id that regresses (older than the last accepted) is
//     ignored so a producer reset cannot pollute the history.
//   * clear() wipes the ring for a producer reconnect (the integrator calls it
//     when the data socket reconnects).
//
// Pure header-only, iCraft-free, libiio-free.  It only stores already-derived
// spectrum bins; it performs no FFT and touches no red-line code path.

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

namespace ui {

constexpr int kWaterfallBins = 256;         // display bins per row (frozen)
constexpr int kWaterfallMaxRows = 128;      // history rows (frozen)
constexpr int kWaterfallMinIntervalMs = 100;// 10 Hz row-advance cap (frozen)

// Which presence states carry a real, displayable spectrum row.  SIGNAL_PRESENT
// and NO_SIGNAL always advance (live signal vs. real ambient noise floor);
// ACQUIRING advances too (real, transitional spectrum).  SIGNAL_LOST keeps the
// existing short history (no fake rows), INVALID stops, and an unknown/empty
// token never fabricates a row.
inline bool waterfall_advance_on_presence(const std::string& presence) {
    return presence == "SIGNAL_PRESENT" || presence == "NO_SIGNAL" ||
           presence == "ACQUIRING";
}

// Fixed ring buffer of waterfall rows.  Trivially copyable: an integrator can
// keep it by value in the live loop without any heap traffic.
struct WaterfallHistory {
    using Row = std::array<std::int16_t, kWaterfallBins>;

    std::array<Row, kWaterfallMaxRows> rows{};  // ring storage (oldest..newest)
    std::uint64_t head = 0;                      // next write slot index
    std::uint64_t count = 0;                     // rows currently held (<= max)
    std::uint64_t last_frame_id = 0;             // last ACCEPTED frame id
    bool have_last_frame = false;                // false until the first accept
    std::uint64_t last_advance_ms = 0;           // wall clock of last accepted row
    bool have_last_advance = false;

    void clear() {
        head = 0;
        count = 0;
        last_frame_id = 0;
        have_last_frame = false;
        last_advance_ms = 0;
        have_last_advance = false;
    }

    std::size_t size() const { return static_cast<std::size_t>(count); }
    bool empty() const { return count == 0; }

    // Row 0 = oldest, size()-1 = newest.  Only valid for i < size().
    const Row& row(std::size_t i) const {
        const std::uint64_t idx =
            (head + kWaterfallMaxRows - count + i) % kWaterfallMaxRows;
        return rows[idx];
    }
    const Row& newest() const { return row(count - 1); }

    // Try to store one new 256-bin row.  Returns true iff the row was accepted.
    //   * dbfs_x4 must be non-null (values clamped into [-480, 0] defensively).
    //   * frame_id <= last accepted frame_id -> rejected (same-frame dedup and
    //     frame-id regression protection).
    //   * now_ms - last accepted now_ms < kWaterfallMinIntervalMs -> rejected
    //     (10 Hz cap).
    bool push(const std::int16_t* dbfs_x4, std::uint64_t frame_id,
              std::uint64_t now_ms) {
        if (dbfs_x4 == nullptr) return false;
        if (have_last_frame && frame_id <= last_frame_id) return false;
        if (have_last_advance &&
            now_ms - last_advance_ms <
                static_cast<std::uint64_t>(kWaterfallMinIntervalMs))
            return false;

        Row r{};
        for (int b = 0; b < kWaterfallBins; ++b) {
            std::int16_t v = dbfs_x4[b];
            if (v > 0) v = 0;
            if (v < -480) v = -480;
            r[static_cast<std::size_t>(b)] = v;
        }
        rows[head] = r;
        head = (head + 1) % kWaterfallMaxRows;
        if (count < kWaterfallMaxRows) ++count;
        last_frame_id = frame_id;
        have_last_frame = true;
        last_advance_ms = now_ms;
        have_last_advance = true;
        return true;
    }
};

}  // namespace ui
