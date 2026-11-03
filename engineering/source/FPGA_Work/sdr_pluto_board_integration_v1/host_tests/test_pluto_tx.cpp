// test_pluto_tx.cpp -- host tests for pluto::PlutoTx (TX safety state machine).
// Uses FakePlutoDevice (no libiio, no device).  Build:
//   g++ -std=gnu++17 -Wall -Wextra -Werror -I../sdr_adapter test_pluto_tx.cpp ../sdr_adapter/pluto_tx.cpp
//
// NOTE: PlutoTx no longer saves/restores parameters -- that is the caller's
// DeviceStateGuard (tested here alongside the TX state machine).

#include "pluto_tx.hpp"
#include "pluto_device.hpp"
#include "device_state_guard.hpp"

#include <cstdint>
#include <cstdio>
#include <stdexcept>
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

static pluto::TxConfig base_cfg() {
    pluto::TxConfig c;
    c.center_freq_hz = 2450000000;
    c.rx_gain_db = 10.0;
    c.loopback = 1;                       // digital loopback (no external RF)
    c.waveform = pluto::make_cw_tone(10000.0, 128000.0, 1024);
    return c;
}

// index of the first log entry with the given prefix, or -1.
static int idx_of(const std::vector<std::string>& log, const std::string& pfx) {
    for (std::size_t i = 0; i < log.size(); ++i)
        if (log[i].compare(0, pfx.size(), pfx) == 0)
            return static_cast<int>(i);
    return -1;
}

static void test_prepare_fixed_order() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(3840000);   // pre-set: prepare() must not touch sample rate

    pluto::PlutoTx tx(dev, base_cfg());
    tx.prepare();
    CHECK(tx.prepared());

    const auto& log = dev.log();
    const int i_stop = idx_of(log, "tx_stop");
    const int i_atten = idx_of(log, "set_tx_atten");
    const int i_gmode = idx_of(log, "set_rx_gain_mode");
    const int i_rgain = idx_of(log, "set_rx_gain:");   // ':' disambiguates from _mode
    const int i_rxlo = idx_of(log, "set_rx_lo");
    const int i_txlo = idx_of(log, "set_tx_lo");
    const int i_loop = idx_of(log, "set_loopback");

    CHECK(i_stop >= 0);                     // stop TX first
    CHECK(i_atten > i_stop);                // max safe atten after stop
    CHECK(i_gmode > i_atten);               // RX manual gain after atten
    CHECK(i_rgain > i_gmode);               // RX gain after mode
    CHECK(i_rxlo > i_rgain && i_txlo > i_rxlo);  // align LOs last-ish
    CHECK(i_loop > i_txlo);                 // loopback after LO align
    CHECK(idx_of(log, "save_params") < 0);  // PlutoTx must NOT save/restore

    CHECK(dev.tx_atten_db() == pluto::kSafeTxAttenDb);
    CHECK(dev.rx_gain_mode() == "manual");
    CHECK(dev.rx_gain_db() == 10.0);
    CHECK(dev.rx_lo() == 2450000000);
    CHECK(dev.tx_lo() == 2450000000);
    CHECK(dev.loopback() == 1);
}

static void test_rf_path_requires_confirm() {
    pluto::FakePlutoDevice dev;
    dev.open();
    pluto::TxConfig c = base_cfg();
    c.loopback = 0;                        // external RF path
    c.confirm_safe_rf_path = false;        // NOT confirmed
    pluto::PlutoTx tx(dev, c);
    bool threw = false;
    try {
        tx.prepare();
    } catch (const std::runtime_error&) {
        threw = true;
    }
    CHECK(threw);
    CHECK(!tx.prepared());
    CHECK(!dev.tx_running());              // nothing was enabled
}

static void test_rf_path_allowed_with_confirm() {
    pluto::FakePlutoDevice dev;
    dev.open();
    pluto::TxConfig c = base_cfg();
    c.loopback = 0;
    c.confirm_safe_rf_path = true;
    pluto::PlutoTx tx(dev, c);
    tx.prepare();
    CHECK(tx.prepared());
}

static void test_ceiling_rejects_excess_atten() {
    pluto::FakePlutoDevice dev;
    dev.open();
    pluto::TxConfig c = base_cfg();
    c.tx_atten_db = -30.0;                 // less attenuation than -40 dB ceiling
    pluto::PlutoTx tx(dev, c);
    bool threw = false;
    try {
        tx.prepare();
    } catch (const std::runtime_error&) {
        threw = true;
    }
    CHECK(threw);
    CHECK(!tx.prepared());
}

static void test_ceiling_allows_exact_ceiling() {
    pluto::FakePlutoDevice dev;
    dev.open();
    pluto::TxConfig c = base_cfg();
    c.tx_atten_db = pluto::kSafeTxCeilingDb;  // -40 dB: exactly at the ceiling
    pluto::PlutoTx tx(dev, c);
    tx.prepare();
    CHECK(tx.prepared());
    CHECK(dev.tx_atten_db() == pluto::kSafeTxCeilingDb);
}

static void test_guard_restores_on_stop() {
    pluto::FakePlutoDevice dev;
    dev.open();
    // original state (what save/restore must return to)
    dev.set_sample_rate(3000000);
    dev.set_rx_lo(2000000000);
    dev.set_tx_lo(2000000000);
    dev.set_rx_gain(30.0);
    dev.set_tx_atten(-10.0);

    pluto::DeviceStateGuard guard(dev);   // snapshot BEFORE any write
    pluto::TxConfig c = base_cfg();
    pluto::PlutoTx tx(dev, c);
    tx.prepare();
    tx.start_cyclic();
    CHECK(tx.started());
    CHECK(dev.tx_buffer_created());
    CHECK(dev.tx_running());
    CHECK(dev.tx_waveform().size() == c.waveform.size());

    tx.stop();
    CHECK(!dev.tx_buffer_created());       // TX buffer destroyed by PlutoTx
    CHECK(!dev.tx_running());
    // PlutoTx did NOT restore params; the guard does.
    CHECK(guard.restore());
    CHECK(dev.sample_rate() == 3000000);
    CHECK(dev.rx_lo() == 2000000000);
    CHECK(dev.tx_lo() == 2000000000);
    CHECK(dev.rx_gain_db() == 30.0);
    CHECK(dev.tx_atten_db() == -10.0);
    CHECK(guard.restore_ok());
}

static void test_guard_raii_restores_on_scope_exit() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(4000000);
    {
        pluto::DeviceStateGuard guard(dev);
        pluto::PlutoTx tx(dev, base_cfg());
        tx.prepare();
        tx.start_cyclic();
        CHECK(dev.tx_running());
    }  // tx destructor -> stop(); guard destructor -> restore()
    CHECK(!dev.tx_buffer_created());
    CHECK(dev.sample_rate() == 4000000);
}

static void test_readback_mismatch_throws_and_guard_restores() {
    pluto::FakePlutoDevice dev;
    dev.open();
    dev.set_sample_rate(5000000);
    pluto::DeviceStateGuard guard(dev);
    dev.atten_readback_bias = 0.5;         // safe-atten read-back will mismatch
    pluto::PlutoTx tx(dev, base_cfg());
    bool threw = false;
    try {
        tx.prepare();
    } catch (const std::runtime_error&) {
        threw = true;
    }
    CHECK(threw);
    CHECK(!tx.prepared());
    guard.restore();                       // explicit restore after the failure
    CHECK(dev.sample_rate() == 5000000);
}

static void test_working_atten_ramp_only_when_different() {
    pluto::FakePlutoDevice dev;
    dev.open();
    pluto::TxConfig c = base_cfg();
    c.tx_atten_db = -50.0;                 // working level, within ceiling, != safe floor
    pluto::PlutoTx tx(dev, c);
    tx.prepare();
    CHECK(tx.prepared());
    CHECK(dev.tx_atten_db() == -50.0);     // ramped to working level
}

static void test_tone_amplitude_is_12bit_safe() {
    // Default CW tone amplitude must stay below 12-bit DAC full scale (2048).
    const auto w = pluto::make_cw_tone(10000.0, 128000.0, 1024);
    int peak = 0;
    for (const std::int16_t v : w) {
        const int a = v < 0 ? -v : v;
        if (a > peak) peak = a;
    }
    CHECK(peak > 0 && peak < pluto::kDacFullScale);
    CHECK(peak == 1500);                   // default amplitude == 1500 counts
}

int main() {
    run_case("PrepareFixedOrder", test_prepare_fixed_order);
    run_case("RfPathRequiresConfirm", test_rf_path_requires_confirm);
    run_case("RfPathAllowedWithConfirm", test_rf_path_allowed_with_confirm);
    run_case("CeilingRejectsExcessAtten", test_ceiling_rejects_excess_atten);
    run_case("CeilingAllowsExactCeiling", test_ceiling_allows_exact_ceiling);
    run_case("GuardRestoresOnStop", test_guard_restores_on_stop);
    run_case("GuardRaiiRestoresOnScopeExit", test_guard_raii_restores_on_scope_exit);
    run_case("ReadbackMismatchThrowsAndGuardRestores", test_readback_mismatch_throws_and_guard_restores);
    run_case("WorkingAttenRampOnlyWhenDifferent", test_working_atten_ramp_only_when_different);
    run_case("ToneAmplitudeIs12bitSafe", test_tone_amplitude_is_12bit_safe);
    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
