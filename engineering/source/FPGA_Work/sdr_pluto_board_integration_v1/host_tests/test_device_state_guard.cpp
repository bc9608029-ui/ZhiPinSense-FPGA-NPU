// test_device_state_guard.cpp -- host tests for pluto::DeviceStateGuard.
// Uses FakePlutoDevice (no libiio, no device).  Build:
//   g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter test_device_state_guard.cpp

#include "device_state_guard.hpp"
#include "pluto_device.hpp"

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

static void test_snapshot_and_restore_roundtrip() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(2560000);
    dev.set_rx_lo(2400000000);
    dev.set_tx_lo(2450000000);
    dev.set_rx_gain_mode("manual");
    dev.set_rx_gain(20.0);
    dev.set_tx_atten(-40.0);
    dev.set_loopback(0);

    pluto::DeviceStateGuard guard(dev);
    // Mutate everything.
    dev.set_sample_rate(3840000);
    dev.set_rx_lo(1);
    dev.set_tx_lo(2);
    dev.set_rx_gain(3.0);
    dev.set_tx_atten(-4.0);
    dev.set_loopback(1);
    CHECK(dev.sample_rate() == 3840000);

    const bool ok = guard.restore();
    CHECK(ok);
    CHECK(guard.restore_ok());
    CHECK(dev.sample_rate() == 2560000);
    CHECK(dev.rx_lo() == 2400000000);
    CHECK(dev.tx_lo() == 2450000000);
    CHECK(dev.rx_gain_db() == 20.0);
    CHECK(dev.tx_atten_db() == -40.0);
    CHECK(dev.loopback() == 0);
}

static void test_restore_is_idempotent() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(1000);
    pluto::DeviceStateGuard guard(dev);
    dev.set_sample_rate(2000);
    CHECK(guard.restore());
    CHECK(guard.restore());   // second call is a no-op, still true
    CHECK(guard.restore_ok());
    CHECK(dev.sample_rate() == 1000);
}

static void test_destructor_restores() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(111);
    {
        pluto::DeviceStateGuard guard(dev);
        dev.set_sample_rate(222);
        CHECK(dev.sample_rate() == 222);
    }
    CHECK(dev.sample_rate() == 111);
}

static void test_restore_fail_is_reported() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(3000000);
    pluto::DeviceStateGuard guard(dev);
    dev.restore_fail = true;   // restore_params() will report failure
    CHECK(!guard.restore());
    CHECK(!guard.restore_ok());
    CHECK(guard.restored());
}

// A helper that returns EARLY (before any explicit restore); the guard must still
// restore on the unwind.
static bool helper_early_return(pluto::FakePlutoDevice& dev) {
    dev.set_sample_rate(5000000);
    pluto::DeviceStateGuard guard(dev);
    dev.set_sample_rate(9999999);
    if (dev.sample_rate() == 9999999) return true;   // early return
    guard.restore();
    return false;
}

static void test_early_return_still_restores() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(5000000);
    const bool r = helper_early_return(dev);
    CHECK(r);
    CHECK(dev.sample_rate() == 5000000);   // restored on the early-return unwind
}

int main() {
    run_case("SnapshotAndRestoreRoundtrip", test_snapshot_and_restore_roundtrip);
    run_case("RestoreIsIdempotent", test_restore_is_idempotent);
    run_case("DestructorRestores", test_destructor_restores);
    run_case("RestoreFailIsReported", test_restore_fail_is_reported);
    run_case("EarlyReturnStillRestores", test_early_return_still_restores);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
