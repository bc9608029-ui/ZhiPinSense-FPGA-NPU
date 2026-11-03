// test_sample_rate_negotiate.cpp -- host tests for sdr::negotiate_sample_rate.
// Uses FakePlutoDevice (no libiio, no device).  Build:
//   g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter test_sample_rate_negotiate.cpp ../sdr_adapter/sample_rate_negotiate.cpp

#include "sample_rate_negotiate.hpp"
#include "pluto_device.hpp"

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond)                                                    \
    do {                                                               \
        if (cond) {                                                    \
            ++g_pass;                                                  \
        } else {                                                       \
            ++g_fail;                                                  \
            std::fprintf(stderr, "FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
        }                                                              \
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

static std::vector<sdr::RateCandidate> two_candidates() {
    return {{2560000, 1, 20, "2.56MHz"}, {3840000, 1, 30, "3.84MHz"}};
}

static void test_exact_match_selects_first() {
    pluto::FakePlutoDevice dev;
    dev.open();
    auto r = sdr::negotiate_sample_rate(dev, two_candidates(), 128000);
    CHECK(r.ok);
    CHECK(r.requested_hz == 2560000);
    CHECK(r.actual_hz == 2560000);
    CHECK(r.down == 20 && r.up == 1);
    CHECK(dev.sample_rate() == 2560000);
}

static void test_readback_mismatch_falls_through() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.reject_sample_rates.insert(2560000);  // coerces to 2559999 -> rejected
    auto r = sdr::negotiate_sample_rate(dev, two_candidates(), 128000);
    CHECK(r.ok);
    CHECK(r.actual_hz == 3840000);   // second candidate accepted
    CHECK(r.down == 30);
    CHECK(dev.sample_rate() == 3840000);
}

static void test_total_failure() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.reject_sample_rates.insert(2560000);
    dev.reject_sample_rates.insert(3840000);
    auto r = sdr::negotiate_sample_rate(dev, two_candidates(), 128000);
    CHECK(!r.ok);
    CHECK(!r.reason.empty());
}

static void test_non_integer_ratio_rejected_without_write() {
    pluto::FakePlutoDevice dev;
    dev.open();
    // 2.6 MHz * 1 != 128 kHz * 20 (2.56 MHz): integer-ratio pre-check fails.
    std::vector<sdr::RateCandidate> bad = {{2600000, 1, 20, "2.6MHz"}};
    auto r = sdr::negotiate_sample_rate(dev, bad, 128000);
    CHECK(!r.ok);
    CHECK(r.reason.find("non-integer") != std::string::npos);
    CHECK(dev.sample_rate() == 0);   // device must NOT have been written
}

static void test_default_candidates_match_fir_specs() {
    auto cands = sdr::default_rate_candidates();
    CHECK(cands.size() == 2);
    CHECK(cands[0].fs_in_hz == 2560000 && cands[0].down == 20 && cands[0].up == 1);
    CHECK(cands[1].fs_in_hz == 3840000 && cands[1].down == 30 && cands[1].up == 1);
}

static void test_report_string() {
    pluto::FakePlutoDevice dev;
    dev.open();
    auto r = sdr::negotiate_sample_rate(dev, two_candidates(), 128000);
    const std::string s = r.report();
    CHECK(s.find("requested=2560000") != std::string::npos);
    CHECK(s.find("actual=2560000") != std::string::npos);
    CHECK(s.find("ratio=20/1") != std::string::npos);
}

int main() {
    run_case("ExactMatchSelectsFirst", test_exact_match_selects_first);
    run_case("ReadbackMismatchFallsThrough", test_readback_mismatch_falls_through);
    run_case("TotalFailure", test_total_failure);
    run_case("NonIntegerRatioRejectedWithoutWrite", test_non_integer_ratio_rejected_without_write);
    run_case("DefaultCandidatesMatchFirSpecs", test_default_candidates_match_fir_specs);
    run_case("ReportString", test_report_string);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
