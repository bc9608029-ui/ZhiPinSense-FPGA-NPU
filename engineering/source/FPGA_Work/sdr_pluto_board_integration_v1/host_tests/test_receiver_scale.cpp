// test_receiver_scale.cpp -- host tests for sdr::ReceiverScale (fixed scalar + Q1.15).
// No iCraft / SDR / board.  Build: g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter

#include "receiver_scale.hpp"

#include <cmath>
#include <complex>
#include <cstdio>
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

static void test_to_float() {
    sdr::ReceiverScale rs(1.0f);
    CHECK(rs.to_float(16384) == 0.5f);        // 16384/32768
    CHECK(rs.to_float(32767) > 0.999f && rs.to_float(32767) < 1.0f);
    CHECK(rs.to_float(-32768) == -1.0f);
    sdr::ReceiverScale half(0.5f);
    CHECK(std::fabs(half.to_float(16384) - 0.25f) < 1e-7f);
}

static void test_to_q115() {
    sdr::ReceiverScale id(1.0f);
    CHECK(id.to_q115(123) == 123);            // identity
    CHECK(id.to_q115(-456) == -456);

    sdr::ReceiverScale half(0.5f);
    CHECK(half.to_q115(1000) == 500);
    CHECK(half.to_q115(-1001) == -501);       // lround(-500.5) -> -501 (away from zero)

    sdr::ReceiverScale big(2.0f);
    CHECK(big.to_q115(20000) == 32767);       // saturated positive
    CHECK(big.to_q115(-20000) == -32768);     // saturated negative
    CHECK(big.to_q115(10000) == 20000);       // in range
}

static void test_calibrate_scale() {
    const float s = sdr::ReceiverScale::calibrate_scale(1000.0, 8000.0);
    CHECK(s == 8.0f);
    CHECK(sdr::ReceiverScale::calibrate_scale(0.0, 8000.0) == 1.0f);  // guard
}

static void test_stats() {
    sdr::ReceiverScale rs(1.0f);
    std::int16_t i[4] = {1000, 2000, 3000, 4000};
    std::int16_t q[4] = {0, 0, 0, 0};
    std::int16_t oi[4], oq[4];
    rs.to_q115(i, q, oi, oq, 4);
    const auto& st = rs.stats();
    CHECK(st.samples == 4);
    CHECK(st.q115_saturated == 0);
    // rms of [1000,2000,3000,4000] = sqrt((1+4+9+16)e6/4) = sqrt(7.5e6) ~ 2738.6
    const double expect = std::sqrt(7.5e6);
    CHECK(std::fabs(st.rms() - expect) < 1.0);

    // saturation: scale=2 clips 20000 (stats accumulate via the batch path)
    sdr::ReceiverScale big(2.0f);
    std::int16_t ii[1] = {20000};
    std::int16_t qq[1] = {0};
    std::int16_t oi2[1], oq2[1];
    big.to_q115(ii, qq, oi2, oq2, 1);
    CHECK(oi2[0] == 32767);
    CHECK(big.stats().q115_saturated == 1);
    CHECK(big.stats().saturation_ratio() > 0.0);
}

static void test_complex_and_split_agree() {
    sdr::ReceiverScale rs(1.0f);
    std::complex<std::int16_t> in[3] = {{100, 200}, {-300, 400}, {500, -600}};
    std::complex<std::int16_t> outc[3];
    rs.to_q115(in, outc, 3);

    sdr::ReceiverScale rs2(1.0f);
    std::int16_t ii[3] = {100, -300, 500};
    std::int16_t qq[3] = {200, 400, -600};
    std::int16_t oi[3], oq[3];
    rs2.to_q115(ii, qq, oi, oq, 3);

    for (int k = 0; k < 3; ++k) {
        CHECK(outc[k].real() == oi[k]);
        CHECK(outc[k].imag() == oq[k]);
    }
}

int main() {
    run_case("ToFloat", test_to_float);
    run_case("ToQ115", test_to_q115);
    run_case("CalibrateScale", test_calibrate_scale);
    run_case("Stats", test_stats);
    run_case("ComplexSplitAgree", test_complex_and_split_agree);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
