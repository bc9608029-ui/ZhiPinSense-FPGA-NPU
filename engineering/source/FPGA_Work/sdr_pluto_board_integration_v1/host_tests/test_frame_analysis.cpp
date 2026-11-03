// test_frame_analysis.cpp -- host regression tests for the per-frame loopback
// verdict and block-phase-continuity detection (task 39e5 second fix round).
//
// These tests lock the exact behaviour that fixes the FALSE-FAIL observed on board
// (per-frame ratio ~0.99998 yet a single full-length Goertzel over concatenated
// 1024-point blocks cancelled to ratio 0.030):
//
//   1. 128 frames of pure 10 kHz, each at a different initial phase, must give a
//      LOW full-length ratio (destructive interference) but per-frame ratio ~1 and
//      PASS (128/128 frames).
//   2. A truly continuous stream must be detected as phase-continuous.
//   3. A missing frame must FAIL.
//   4. A single wrong-frequency frame must FAIL (the per-frame FREQ gate catches
//      it even though the ratio gate alone would not).
//   5. A single low-ratio (noise) frame must FAIL.
//   6. Gate 5 phase breaks must NOT be treated as a continuous stream: the
//      contiguous single-refill collector fails closed on a short refill.
//
// Build: g++ -std=gnu++17 -Wall -Wextra -Werror -O2
//            -I../sdr_adapter -I../board_package test_frame_analysis.cpp

#include "../sdr_adapter/frame_analysis.hpp"
#include "../board_package/board_common.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <random>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond)                                                         \
    do {                                                                    \
        if (cond) {                                                         \
            ++g_pass;                                                       \
        } else {                                                            \
            ++g_fail;                                                       \
            std::fprintf(stderr, "FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
        }                                                                   \
    } while (0)

template <typename F>
static void run_case(const char* name, F f) {
    std::fprintf(stderr, "-- %s\n", name);
    try {
        f();
    } catch (const std::exception& e) {
        ++g_fail;
        std::fprintf(stderr, "EXCEPTION in %s: %s\n", name, e.what());
    }
}

namespace {

constexpr std::size_t kFrame = 1024;         // complex samples per RX refill block
constexpr double kFs = 2560000.0;             // 2.56 MHz candidate
constexpr double kTone = 10000.0;             // baseband CW tone
constexpr double kAmp = 1500.0;               // 12-bit DAC counts (< 2048)
constexpr double kRatioThresh = 0.3;          // MUST NOT be relaxed
constexpr double kFreqErrMax = 300.0;         // 3% of 10 kHz, pre-fixed

// One interleaved int16 frame of a pure tone at a given initial phase.
std::vector<std::int16_t> tone_frame(double freq_hz, double phase, double amp = kAmp) {
    std::vector<std::int16_t> iq(kFrame * 2);
    const double w = 2.0 * 3.14159265358979323846 * freq_hz / kFs;
    for (std::size_t k = 0; k < kFrame; ++k) {
        const double t = static_cast<double>(k);
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(amp * std::cos(w * t + phase)));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::llround(amp * std::sin(w * t + phase)));
    }
    return iq;
}

// Concatenate n frames, each of pure `freq_hz` at its own initial phase.
std::vector<std::int16_t> build_frames(int n, double freq_hz,
                                       const std::vector<double>& phases) {
    std::vector<std::int16_t> iq;
    iq.reserve(static_cast<std::size_t>(n) * kFrame * 2);
    for (int i = 0; i < n; ++i) {
        const auto fr = tone_frame(freq_hz, phases[static_cast<std::size_t>(i)]);
        iq.insert(iq.end(), fr.begin(), fr.end());
    }
    return iq;
}

// Deterministic, scattered (random-like) initial phases: uniform in [0, 2*pi).
std::vector<double> random_phases(int n, unsigned seed) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<double> dist(0.0, 2.0 * 3.14159265358979323846);
    std::vector<double> p(static_cast<std::size_t>(n));
    for (auto& v : p) v = dist(rng);
    return p;
}

// A continuous pure tone (one phase across ALL samples; no block reset).
std::vector<std::int16_t> continuous_tone(int n_frames) {
    const std::size_t total = static_cast<std::size_t>(n_frames) * kFrame;
    std::vector<std::int16_t> iq(total * 2);
    const double w = 2.0 * 3.14159265358979323846 * kTone / kFs;
    for (std::size_t k = 0; k < total; ++k) {
        const double t = static_cast<double>(k);
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(kAmp * std::cos(w * t)));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::llround(kAmp * std::sin(w * t)));
    }
    return iq;
}

// The Gate 3/4 verdict, factored identically to board::run_loopback so the test
// locks the same logic the board uses.
bool loopback_verdict(const sdr::FrameSummary& s, std::size_t expected_frames) {
    const bool no_sat = s.peak_max < 2048;
    const bool frames_complete = s.frame_count == expected_frames;
    const bool all_pass = s.frame_count > 0 && s.frame_pass_count == s.frame_count;
    return frames_complete && all_pass && no_sat;
}

}  // namespace

// (1) Random per-frame phase -> LOW full-length ratio, HIGH per-frame ratio.
static void test_random_phase_frames_low_full_high_perframe() {
    const int n = 128;
    const std::vector<std::int16_t> iq = build_frames(n, kTone, random_phases(n, 20261006u));

    const sdr::FrameSummary s =
        sdr::analyze_frames(iq, kFrame, kTone, kFs, kRatioThresh, kFreqErrMax);

    CHECK(s.frame_count == static_cast<std::size_t>(n));
    CHECK(s.frame_pass_count == static_cast<std::size_t>(n));   // every frame passes
    CHECK(s.ratio_min > 0.99);                                  // clean tone per frame
    CHECK(s.freq_max_error < kFreqErrMax);
    CHECK(s.peak_max < 2048);
    CHECK(loopback_verdict(s, static_cast<std::size_t>(n)));    // PASS

    // The full-length Goertzel over the concatenated blocks DESTRUCTIVELY
    // interferes (the exact false-fail the per-frame fix removes).
    const auto full = sdr::to_complex(iq);
    const double full_ratio =
        std::max(sdr::goertzel_ratio(full, kTone, kFs), sdr::goertzel_ratio(full, -kTone, kFs));
    CHECK(s.global_ratio < 0.3);         // diagnostic-only, and clearly LOW
    CHECK(full_ratio < 0.3);

    // The block phase break is DETECTED (not silently treated as continuous).
    CHECK(!sdr::tone_phase_continuous(full, kFrame, kTone, kFs));
}

// (2) A truly continuous stream is phase-continuous AND gives a high full ratio.
static void test_continuous_stream_detected() {
    const int n = 128;
    const std::vector<std::int16_t> iq = continuous_tone(n);
    const auto full = sdr::to_complex(iq);

    CHECK(sdr::tone_phase_continuous(full, kFrame, kTone, kFs));

    const sdr::FrameSummary s =
        sdr::analyze_frames(iq, kFrame, kTone, kFs, kRatioThresh, kFreqErrMax);
    CHECK(s.frame_pass_count == static_cast<std::size_t>(n));
    CHECK(s.global_ratio > 0.99);   // continuous -> full-length Goertzel is coherent
}

// (3) Missing frame -> FAIL (frame_count does not reach the expected 128).
static void test_missing_frame_fails() {
    const int n = 127;   // one frame short
    const std::vector<std::int16_t> iq = build_frames(n, kTone, random_phases(n, 7u));
    const sdr::FrameSummary s =
        sdr::analyze_frames(iq, kFrame, kTone, kFs, kRatioThresh, kFreqErrMax);
    CHECK(s.frame_count == 127);
    CHECK(!loopback_verdict(s, 128));   // not 128 complete frames
}

// (4) Single wrong-frequency frame -> FAIL (the per-frame FREQ gate catches it).
static void test_single_bad_frequency_fails() {
    const int n = 128;
    const int bad = 10;
    std::vector<std::int16_t> iq;
    iq.reserve(static_cast<std::size_t>(n) * kFrame * 2);
    for (int i = 0; i < n; ++i) {
        const auto fr = tone_frame((i == bad) ? 8000.0 : kTone, 0.0);
        iq.insert(iq.end(), fr.begin(), fr.end());
    }
    const sdr::FrameSummary s =
        sdr::analyze_frames(iq, kFrame, kTone, kFs, kRatioThresh, kFreqErrMax);
    CHECK(s.frame_count == 128);
    CHECK(s.frame_pass_count == 127);   // exactly the bad frame fails
    CHECK(s.freq_max_error > kFreqErrMax);
    CHECK(!loopback_verdict(s, 128));

    // The bad frame is still a clean tone (ratio OK) but at the wrong frequency.
    std::vector<std::int16_t> badf(iq.begin() + static_cast<long>(bad) * kFrame * 2,
                                   iq.begin() + static_cast<long>(bad + 1) * kFrame * 2);
    const sdr::FrameResult fr = sdr::analyze_frame(badf, kTone, kFs, kRatioThresh, kFreqErrMax);
    CHECK(fr.freq_ok == false);
}

// (5) Single low-ratio (noise) frame -> FAIL (the ratio gate catches it).
static void test_single_low_ratio_fails() {
    const int n = 128;
    const int bad = 5;
    std::mt19937 rng(99u);
    std::uniform_int_distribution<int> noise(-2047, 2047);
    std::vector<std::int16_t> iq;
    iq.reserve(static_cast<std::size_t>(n) * kFrame * 2);
    for (int i = 0; i < n; ++i) {
        if (i == bad) {
            for (std::size_t k = 0; k < kFrame * 2; ++k) iq.push_back(static_cast<std::int16_t>(noise(rng)));
        } else {
            const auto fr = tone_frame(kTone, 0.0);
            iq.insert(iq.end(), fr.begin(), fr.end());
        }
    }
    const sdr::FrameSummary s =
        sdr::analyze_frames(iq, kFrame, kTone, kFs, kRatioThresh, kFreqErrMax);
    CHECK(s.frame_count == 128);
    CHECK(s.frame_pass_count == 127);   // the noise frame fails the ratio gate
    CHECK(!loopback_verdict(s, 128));
}

// (6a) Gate 5: a SHORT single refill must fail closed (never loop-concatenate).
static void test_contiguous_collect_fails_closed_on_short_refill() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rx_tone_len = 512;   // device can only hand back 512 complex < the 1024 asked

    std::vector<std::int16_t> iq;
    board::RxStats st;
    const bool ok = board::collect_raw_contiguous(dev, 1024, iq, st);
    CHECK(!ok);              // fail closed
    CHECK(st.short_block);
    CHECK(iq.size() / 2 < 1024);   // it did NOT pad/concatenate to the full amount
}

// (6b) Gate 5: a full single refill succeeds, advancing exactly one refill.
static void test_contiguous_collect_succeeds_on_full_refill() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rx_tone_len = 4096;   // enough for one 1024-complex request

    std::vector<std::int16_t> iq;
    board::RxStats st;
    const std::uint64_t before = dev.rx_refill_count();
    const bool ok = board::collect_raw_contiguous(dev, 1024, iq, st);
    const std::uint64_t after = dev.rx_refill_count();
    CHECK(ok);
    CHECK(!st.short_block);
    CHECK(iq.size() == 1024 * 2);
    CHECK(after - before == 1);              // exactly one refill
    CHECK(dev.rx_buffer_capacity() >= 1024); // capacity recorded for the continuity proof
}

int main() {
    run_case("RandomPhaseFramesLowFullHighPerframe", test_random_phase_frames_low_full_high_perframe);
    run_case("ContinuousStreamDetected", test_continuous_stream_detected);
    run_case("MissingFrameFails", test_missing_frame_fails);
    run_case("SingleBadFrequencyFails", test_single_bad_frequency_fails);
    run_case("SingleLowRatioFails", test_single_low_ratio_fails);
    run_case("ContiguousCollectFailsClosedOnShortRefill", test_contiguous_collect_fails_closed_on_short_refill);
    run_case("ContiguousCollectSucceedsOnFullRefill", test_contiguous_collect_succeeds_on_full_refill);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
