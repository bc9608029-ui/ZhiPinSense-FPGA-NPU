// test_restore_semantics.cpp -- host tests for the Gate 6-9 state-restore fix
// (39e5: RX-gain AGC semantics + fail-closed gate verdict).
//
// Exercises the FakePlutoDevice restore model (which mirrors the real
// LibiioDevice AD936x semantics) and the shared board::final_gate_pass helper the
// three device gates use, so the AGC-hardwaregain bug and the fail-open bug are
// both caught without a device.  iCraft-free and libiio-free.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/device_state_guard.hpp"
#include "../board_package/board_common.hpp"

#include <cmath>
#include <cstdio>
#include <string>

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s\n", what);
    }
}

// (1) The AD936x behavior the fix depends on: a manual hardwaregain write is
// rejected while an AGC mode is active (and applied in manual mode).
void test_agc_gain_write_fails() {
    pluto::FakePlutoDevice d;
    d.set_rx_gain_mode("slow_attack");
    const double before = d.rx_gain_db();
    check(d.set_rx_gain(20.0) == before,
          "set_rx_gain rejected in AGC mode (value unchanged)");
    check(d.rx_gain_db() == before, "AGC gain write did not change stored gain");
    d.set_rx_gain_mode("manual");
    check(d.set_rx_gain(20.0) == 20.0, "set_rx_gain applies in manual mode");
}

// (2) original slow_attack -> run switches to manual -> restore must PASS and NOT
// write AGC hardwaregain (the runtime gain value is left alone).
void test_agc_restore_no_gain_write() {
    pluto::FakePlutoDevice d;
    d.set_rx_gain_mode("manual");
    d.set_rx_gain(20.0);          // model the AGC "locked" gain
    d.set_rx_gain_mode("slow_attack");  // original state: AGC at 20.0 dB
    d.save_params();

    d.set_rx_gain_mode("manual"); // run mutates the device
    d.set_rx_gain(10.0);

    check(d.restore_params(), "AGC restore PASS (no hardwaregain write)");
    check(d.rx_gain_mode() == "slow_attack", "mode restored to slow_attack");
    check(d.rx_gain_db() == 10.0,
          "AGC hardwaregain NOT overwritten (runtime 10.0 kept, not saved 20.0)");
}

// (3) original manual -> correctly restores the original mode AND gain.
void test_manual_restore_restores_gain() {
    pluto::FakePlutoDevice d;
    d.set_rx_gain_mode("manual");
    d.set_rx_gain(15.0);
    d.save_params();

    d.set_rx_gain(5.0);           // run mutates the gain

    check(d.restore_params(), "manual restore PASS");
    check(d.rx_gain_mode() == "manual", "mode stays manual");
    check(d.rx_gain_db() == 15.0, "manual gain restored to saved 15.0");
}

// (4a) gain-mode restore failure must FAIL the restore.
void test_mode_restore_failure() {
    pluto::FakePlutoDevice d;
    d.set_rx_gain_mode("manual");
    d.set_rx_gain(15.0);
    d.save_params();

    d.set_rx_gain_mode("fast_attack");  // run mutates the mode
    d.fail_mode_restore = true;

    check(!d.restore_params(), "gain-mode restore failure -> restore FAIL");
}

// (4b) manual-gain restore failure must FAIL the restore.
void test_manual_gain_restore_failure() {
    pluto::FakePlutoDevice d;
    d.set_rx_gain_mode("manual");
    d.set_rx_gain(15.0);
    d.save_params();

    d.set_rx_gain(5.0);
    d.fail_manual_gain_restore = true;

    check(!d.restore_params(), "manual-gain restore failure -> restore FAIL");
}

// (5) restore failure propagates through DeviceStateGuard and never looks like a
// clean restore.
void test_guard_propagates_restore_failure() {
    pluto::FakePlutoDevice d;
    d.set_rx_gain_mode("manual");
    d.set_rx_gain(15.0);
    {
        pluto::DeviceStateGuard g(d);
        d.set_rx_gain(5.0);
        d.fail_manual_gain_restore = true;
        check(!g.restore(), "guard.restore() false on manual-gain failure");
        check(!g.restore_ok(), "guard.restore_ok() false");
        check(!g.restore(), "guard.restore() idempotent (still false)");
    }
}

// (6) the fail-closed helper the three gates share: restore failure forces a FAIL
// verdict (and therefore a non-zero exit via `return pass ? 0 : 1`).
void test_final_gate_pass() {
    std::string d;
    check(board::final_gate_pass(true, true, d),
          "final_gate_pass(functional PASS, restore OK) == true");
    check(d.find("(restore_failed)") == std::string::npos,
          "restore OK appends no marker");

    d.clear();
    check(!board::final_gate_pass(true, false, d),
          "final_gate_pass(functional PASS, restore FAIL) == false");
    check(d.find("(restore_failed)") != std::string::npos,
          "restore FAIL appends (restore_failed) marker");

    d.clear();
    check(!board::final_gate_pass(false, true, d),
          "final_gate_pass(functional FAIL, restore OK) == false");

    d.clear();
    check(!board::final_gate_pass(false, false, d),
          "final_gate_pass(functional FAIL, restore FAIL) == false");
}

}  // namespace

int main() {
    std::printf("test_restore_semantics\n");
    test_agc_gain_write_fails();
    test_agc_restore_no_gain_write();
    test_manual_restore_restores_gain();
    test_mode_restore_failure();
    test_manual_gain_restore_failure();
    test_guard_propagates_restore_failure();
    test_final_gate_pass();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
