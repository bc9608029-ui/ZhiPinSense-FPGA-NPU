// test_gate10_settle.cpp -- host tests for the M17 Gate 10 settle / lifecycle /
// dump-filter pure logic (Task A / B / C).  No device, no libiio: only the
// header-only gate10_settle.hpp helpers, exercised exactly as the board binary
// uses them.
//
// What this proves:
//   * the capture-and-discard settle path is gone: a non-zero --settle-frames is
//     rejected fail-closed, never silently downgraded;
//   * the per-class TX/RX buffer-lifecycle deltas are balanced (tx_live=0,
//     rx_buffer_live=0) once the snapshots are taken after the RAII destructor and
//     the class-end RX recreate;
//   * --dump-error-class parses "all" and 0..11, and rejects out-of-range/junk.

#include "../board_package/gate10_settle.hpp"

#include <cstdio>
#include <string>

namespace {

int g_pass = 0;
int g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void test_settle_config() {
    gate10::SettleConfig cfg;
    std::string err;

    check(gate10::parse_settle_config(0, 100, cfg, err), "settle_frames=0 accepted");
    check(cfg.policy == gate10::SettlePolicy::kTimeOnly, "policy == TIME_ONLY for 0");
    check(cfg.settle_wait_ms == 100, "settle_wait_ms stored");
    check(cfg.settle_frames == 0, "settle_frames stored as 0");

    check(!gate10::parse_settle_config(2, 100, cfg, err), "settle_frames=2 rejected");
    check(!err.empty(), "reject carries an error message");
    check(err.find("settle_frames") != std::string::npos, "error names settle_frames");

    check(std::string(gate10::settle_policy_name(gate10::SettlePolicy::kTimeOnly)) ==
              "TIME_ONLY",
          "settle_policy_name(TIME_ONLY)");
    check(std::string(gate10::settle_policy_name(
              gate10::SettlePolicy::kSeparateCapture)) == "SEPARATE_CAPTURE",
          "settle_policy_name(SEPARATE_CAPTURE)");
}

void test_lifecycle() {
    gate10::BufferCounts before, settle, after;

    // Balanced per class: TX create==destroy, RX create==destroy, one refill.
    after.tx_create = 1;
    after.tx_destroy = 1;
    after.rx_create = 1;
    after.rx_destroy = 1;
    after.rx_refill = 1;

    gate10::LifecycleDeltas d = gate10::compute_lifecycle(before, settle, after);
    check(d.tx_create_delta == 1, "tx_create_delta == 1");
    check(d.tx_destroy_delta == 1, "tx_destroy_delta == 1");
    check(d.tx_live_delta == 0, "tx_live_delta == 0 (balanced)");
    check(d.rx_buffer_live_delta == 0, "rx_buffer_live_delta == 0 (balanced)");
    check(d.rx_refill_delta == 1, "rx_refill_delta == 1");

    // A TX buffer that was created but never destroyed is reported as a live leak.
    after.tx_destroy = 0;
    d = gate10::compute_lifecycle(before, settle, after);
    check(d.tx_live_delta == 1, "tx_live_delta == 1 when destroy missing");

    // The settle snapshot separates the settle RX create from the official one.
    settle.rx_create = 1;
    settle.rx_destroy = 1;
    after.rx_create = 2;
    after.rx_destroy = 2;
    d = gate10::compute_lifecycle(before, settle, after);
    check(d.settle_rx_create_delta == 1, "settle_rx_create_delta == 1");
    check(d.official_rx_create_delta == 1, "official_rx_create_delta == 1");

    // report() is non-empty and names the authoritative fields.
    check(d.report().find("tx_buffer_live_delta") != std::string::npos,
          "lifecycle report names tx_buffer_live_delta");
}

void test_error_filter() {
    gate10::ErrorClassFilter f;
    std::string err;

    check(f.parse("all", err) && f.all && f.target == -1, "parse \"all\"");
    check(f.parse("", err) && f.all, "parse empty -> all");
    check(f.matches(0) && f.matches(11), "all matches every class");

    check(f.parse("7", err) && !f.all && f.target == 7, "parse \"7\"");
    check(f.matches(7), "target matches its own class");
    check(!f.matches(0), "target does not match another class");

    check(!f.parse("12", err), "parse \"12\" rejected (out of range)");
    check(!f.parse("-1", err), "parse \"-1\" rejected");
    check(!f.parse("abc", err), "parse junk rejected");
}

}  // namespace

int main() {
    std::printf("test_gate10_settle\n");
    test_settle_config();
    test_lifecycle();
    test_error_filter();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
