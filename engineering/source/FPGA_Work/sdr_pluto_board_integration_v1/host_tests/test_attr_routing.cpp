// test_attr_routing.cpp -- lock the AD9361/Pluto IIO attribute->(target, api) map.
//
// This is the pure, host-runnable form of the Gate 1 bug fix: it asserts that
// every control attribute the real backend touches routes to the CORRECT libiio
// object and API family, without needing libiio or a device.  The real backend
// (pluto_device_libiio.cpp) resolves these same targets to its concrete handles.
//
// Build: g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter test_attr_routing.cpp

#include "iio_attr_routing.hpp"

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

static bool resolves(const char* name, sdr::AttrDir dir, sdr::AttrTarget t,
                     sdr::AttrApi a) {
    sdr::AttrRoute r{};
    if (!sdr::route_ad9361_attr(name, dir, &r)) return false;
    return r.target == t && r.api == a;
}

// The core regression: sampling_frequency / rf_bandwidth / gain_control_mode /
// hardwaregain are CHANNEL attributes on the PHY control channels, never a
// device attribute and never a cf-ad9361-*-lpc stream channel.
static void test_sampling_frequency_routes_to_phy_channels() {
    CHECK(resolves("sampling_frequency", sdr::AttrDir::kRx,
                   sdr::AttrTarget::kPhyRxCh, sdr::AttrApi::kChannel));
    CHECK(resolves("sampling_frequency", sdr::AttrDir::kTx,
                   sdr::AttrTarget::kPhyTxCh, sdr::AttrApi::kChannel));
    // It must NOT be a device attribute (the original bug).
    sdr::AttrRoute r{};
    CHECK(sdr::route_ad9361_attr("sampling_frequency", sdr::AttrDir::kRx, &r));
    CHECK(r.api != sdr::AttrApi::kDevice);
    CHECK(r.target != sdr::AttrTarget::kRxLo);   // not the LO channel either
}

static void test_control_attributes_on_phy_control_channels() {
    CHECK(resolves("rf_bandwidth", sdr::AttrDir::kRx,
                   sdr::AttrTarget::kPhyRxCh, sdr::AttrApi::kChannel));
    CHECK(resolves("rf_bandwidth", sdr::AttrDir::kTx,
                   sdr::AttrTarget::kPhyTxCh, sdr::AttrApi::kChannel));
    CHECK(resolves("gain_control_mode", sdr::AttrDir::kRx,
                   sdr::AttrTarget::kPhyRxCh, sdr::AttrApi::kChannel));
    CHECK(resolves("hardwaregain", sdr::AttrDir::kRx,
                   sdr::AttrTarget::kPhyRxCh, sdr::AttrApi::kChannel));
    CHECK(resolves("hardwaregain", sdr::AttrDir::kTx,
                   sdr::AttrTarget::kPhyTxCh, sdr::AttrApi::kChannel));
}

static void test_lo_routes_to_altvoltage() {
    CHECK(resolves("frequency", sdr::AttrDir::kRx,
                   sdr::AttrTarget::kRxLo, sdr::AttrApi::kChannel));
    CHECK(resolves("frequency", sdr::AttrDir::kTx,
                   sdr::AttrTarget::kTxLo, sdr::AttrApi::kChannel));
}

// loopback is a DEVICE DEBUG attribute on Pluto v0.39, not a device/channel attr.
static void test_loopback_is_debug_attribute() {
    CHECK(resolves("loopback", sdr::AttrDir::kNone,
                   sdr::AttrTarget::kPhyDebug, sdr::AttrApi::kDebug));
    sdr::AttrRoute r{};
    CHECK(sdr::route_ad9361_attr("loopback", sdr::AttrDir::kNone, &r));
    CHECK(r.api != sdr::AttrApi::kChannel);
    CHECK(r.api != sdr::AttrApi::kDevice);
}

// No attribute in the table may route to the (unused-by-AD9361) device API.
static void test_no_route_uses_device_api() {
    // Enumerated by probing every known attribute with every direction; none may
    // come back with api == kDevice.
    const char* names[] = {"sampling_frequency", "rf_bandwidth",
                           "gain_control_mode", "hardwaregain", "frequency",
                           "loopback"};
    const sdr::AttrDir dirs[] = {sdr::AttrDir::kRx, sdr::AttrDir::kTx,
                                 sdr::AttrDir::kNone};
    for (const char* n : names) {
        for (sdr::AttrDir d : dirs) {
            sdr::AttrRoute r{};
            if (sdr::route_ad9361_attr(n, d, &r)) {
                CHECK(r.api != sdr::AttrApi::kDevice);
            }
        }
    }
}

static void test_unknown_combinations_rejected() {
    sdr::AttrRoute r{};
    // loopback has no RX/TX side.
    CHECK(!sdr::route_ad9361_attr("loopback", sdr::AttrDir::kRx, &r));
    CHECK(!sdr::route_ad9361_attr("loopback", sdr::AttrDir::kTx, &r));
    // gain_control_mode is RX-only on AD9361.
    CHECK(!sdr::route_ad9361_attr("gain_control_mode", sdr::AttrDir::kTx, &r));
    // sampling_frequency has no side-less form.
    CHECK(!sdr::route_ad9361_attr("sampling_frequency", sdr::AttrDir::kNone, &r));
    // unknown attribute.
    CHECK(!sdr::route_ad9361_attr("no_such_attr", sdr::AttrDir::kRx, &r));
}

static void test_name_helpers() {
    CHECK(std::string(sdr::api_name(sdr::AttrApi::kChannel)) == "channel");
    CHECK(std::string(sdr::api_name(sdr::AttrApi::kDebug)) == "debug");
    CHECK(std::string(sdr::target_name(sdr::AttrTarget::kPhyRxCh)) == "phy_rx_ch");
    CHECK(std::string(sdr::target_name(sdr::AttrTarget::kPhyDebug)) == "phy_debug");
}

int main() {
    run_case("SamplingFrequencyRoutesToPhyChannels", test_sampling_frequency_routes_to_phy_channels);
    run_case("ControlAttributesOnPhyControlChannels", test_control_attributes_on_phy_control_channels);
    run_case("LoRoutesToAltvoltage", test_lo_routes_to_altvoltage);
    run_case("LoopbackIsDebugAttribute", test_loopback_is_debug_attribute);
    run_case("NoRouteUsesDeviceApi", test_no_route_uses_device_api);
    run_case("UnknownCombinationsRejected", test_unknown_combinations_rejected);
    run_case("NameHelpers", test_name_helpers);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
