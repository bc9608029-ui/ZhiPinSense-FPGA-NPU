// test_rx_format.cpp -- host tests for sdr::RxFormat (RX IQ data-format contract).
// No iCraft / SDR / board.  Build: g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter

#include "rx_format.hpp"

#include <cstdio>
#include <string>

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

static void test_canonical_defaults() {
    const sdr::RxFormat f = sdr::canonical_rx_format();
    CHECK(f.interleaved == true);
    CHECK(f.q_offset == 1);
    CHECK(f.container_bits == 16);
    CHECK(f.effective_bits == 12);
    CHECK(f.left_justified == false);
    CHECK(f.sign_extended == true);
    CHECK(f.little_endian == true);
    CHECK(f.two_channel == true);
    CHECK(f.verified == false);   // ADI default until confirmed on hardware
}

static void test_slots_and_bytes() {
    const sdr::RxFormat f = sdr::canonical_rx_format();
    CHECK(sdr::slots_per_complex(f) == 2);         // I + Q, two int16
    CHECK(sdr::bytes_per_complex(f) == 4);         // 2 slots * 2 bytes
}

static void test_describe_mentions_key_facts() {
    const std::string d = sdr::describe(sdr::canonical_rx_format());
    CHECK(d.find("interleaved") != std::string::npos);
    CHECK(d.find("int16") != std::string::npos);
    CHECK(d.find("12-bit") != std::string::npos);
    CHECK(d.find("right-justified") != std::string::npos);
    CHECK(d.find("unverified") != std::string::npos);  // honest: not HW-confirmed
}

static void test_verified_flag_reflects_state() {
    sdr::RxFormat f = sdr::canonical_rx_format();
    f.verified = true;
    CHECK(sdr::describe(f).find("(verified)") != std::string::npos);
}

int main() {
    run_case("CanonicalDefaults", test_canonical_defaults);
    run_case("SlotsAndBytes", test_slots_and_bytes);
    run_case("DescribeMentionsKeyFacts", test_describe_mentions_key_facts);
    run_case("VerifiedFlagReflectsState", test_verified_flag_reflects_state);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
