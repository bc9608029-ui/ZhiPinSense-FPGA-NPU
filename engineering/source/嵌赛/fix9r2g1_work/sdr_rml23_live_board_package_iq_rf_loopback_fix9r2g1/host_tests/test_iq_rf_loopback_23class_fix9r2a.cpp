// test_iq_rf_loopback_23class_fix9r2a.cpp -- host tests for Route F fix9r2a (the
// R8 2-sample DIAGNOSTIC sample selector + acceptance gate added on top of fix9r2).
// iCraft-free and libiio-free: it exercises ONLY the pure functions in
// iq_rf_fix9r2a_diagnostic.hpp (select_diagnostic_holdout + evaluate_diagnostic_gate),
// which is the exact code the board runner calls in diagnostic mode.
//
// Why this exists (Task A audit conclusion): fix9r2's --file-filter matches the ci16
// FILE NAME (quantized_d2_2p56m_%06d.ci16, no modulation) and --max-files=2 truncates
// the FIRST TWO holdout files (000000 OOK, 000001 OOK) -- neither can select the R8
// set "1 BPSK + 1 4ASK".  The selector here matches FrozenIq::modulation (the manifest
// `modulation` column) over the HOLD-ONLY subset, and fail-closes when a named class is
// absent or under-filled.
//
// Covered (no NPU, no libiio, no device):
//   * selector: picks 1 BPSK + 1 4ASK in request order from a mixed holdout;
//   * selector: per_class=2 takes 2 files per class;
//   * selector: leaves calibration untouched (reads holdout only);
//   * selector: fail-closed on absent class / under-filled class / per_class=0 /
//     empty class list;
//   * gate: PASS on a fully-consistent input;
//   * gate: FAIL on selected_classes mismatch / holdout count mismatch / per-file
//     count mismatches (estimate/frame/training/payload/push) / clip / corr / residual
//     / restore_ok;
//   * integration: BPSK+4ASK selection + a synthesized per-file pass/fail table
//     reproduces the exact gate verdict the board runner would print.

#include "../board_package/iq_rf_fix9r2a_diagnostic.hpp"

#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// A tiny FrozenIq builder -- only `modulation` (and a name for tracing) matter to
// the selector; the rest keeps their defaults.
iqdloop::FrozenIq fz(const std::string& modulation, const std::string& file_name) {
    iqdloop::FrozenIq f;
    f.modulation = modulation;
    f.file_name = file_name;
    f.source_class = -1;
    f.deployed_class = -1;
    f.split_role = "holdout";
    f.is_calibration = false;
    return f;
}

// A holdout ordered exactly like the R9 46-sample smoke layout's first 8 files:
// 2 OOK, 2 4ASK, 2 8ASK, 2 BPSK (deployed class order 0..22, 2 per class).
std::vector<iqdloop::FrozenIq> make_holdout() {
    return {
        fz("OOK", "quantized_d2_2p56m_000000.ci16"),
        fz("OOK", "quantized_d2_2p56m_000001.ci16"),
        fz("4ASK", "quantized_d2_2p56m_000002.ci16"),
        fz("4ASK", "quantized_d2_2p56m_000003.ci16"),
        fz("8ASK", "quantized_d2_2p56m_000004.ci16"),
        fz("8ASK", "quantized_d2_2p56m_000005.ci16"),
        fz("BPSK", "quantized_d2_2p56m_000006.ci16"),
        fz("BPSK", "quantized_d2_2p56m_000007.ci16"),
    };
}

// ---- 1. selector: the R8 target set "1 BPSK + 1 4ASK" -----------------------

void test_select_bpsk_4ask() {
    const auto holdout = make_holdout();
    const auto sel = iqrffix9r2a::select_diagnostic_holdout(
        holdout, {"BPSK", "4ASK"}, 1);
    check(sel.ok, "sel: ok");
    check(sel.selected_classes == "BPSK,4ASK", "sel: classes in request order");
    check(sel.selected_index.size() == 2, "sel: 2 indices");
    // BPSK first (index 6), then 4ASK (index 2)
    check(sel.selected_index[0] == 6 && holdout[sel.selected_index[0]].modulation == "BPSK",
          "sel: index[0] is BPSK");
    check(sel.selected_index[1] == 2 && holdout[sel.selected_index[1]].modulation == "4ASK",
          "sel: index[1] is 4ASK");
}

// ---- 2. selector: per_class=2 takes 2 files per class ------------------------

void test_select_per_class_two() {
    const auto holdout = make_holdout();
    const auto sel = iqrffix9r2a::select_diagnostic_holdout(
        holdout, {"4ASK", "BPSK"}, 2);
    check(sel.ok, "sel2: ok");
    check(sel.selected_index.size() == 4, "sel2: 4 indices");
    check(holdout[sel.selected_index[0]].modulation == "4ASK" &&
          holdout[sel.selected_index[1]].modulation == "4ASK" &&
          holdout[sel.selected_index[2]].modulation == "BPSK" &&
          holdout[sel.selected_index[3]].modulation == "BPSK",
          "sel2: 2x 4ASK then 2x BPSK");
}

// ---- 3. selector: absent class fail-closes -----------------------------------

void test_select_absent_class() {
    const auto holdout = make_holdout();
    const auto sel = iqrffix9r2a::select_diagnostic_holdout(
        holdout, {"BPSK", "256QAM"}, 1);
    check(!sel.ok, "absent: !ok");
    check(sel.report.find("256QAM") != std::string::npos, "absent: report names 256QAM");
    check(sel.report.find("have=0") != std::string::npos, "absent: have=0");
}

// ---- 4. selector: under-filled class fail-closes -----------------------------

void test_select_underfilled() {
    // only ONE BPSK file, ask for 2 -> under-filled
    std::vector<iqdloop::FrozenIq> holdout = { fz("BPSK", "x.ci16"),
                                               fz("4ASK", "y.ci16"),
                                               fz("4ASK", "z.ci16") };
    const auto sel = iqrffix9r2a::select_diagnostic_holdout(
        holdout, {"BPSK", "4ASK"}, 2);
    check(!sel.ok, "under: !ok");
    check(sel.report.find("have=1") != std::string::npos, "under: have=1 for BPSK");
    check(sel.report.find("need=2") != std::string::npos, "under: need=2");
}

// ---- 5. selector: per_class=0 / empty list fail-closed -----------------------

void test_select_degenerate() {
    const auto holdout = make_holdout();
    const auto z = iqrffix9r2a::select_diagnostic_holdout(holdout, {"BPSK"}, 0);
    check(!z.ok, "deg: per_class=0 -> !ok");
    const auto e = iqrffix9r2a::select_diagnostic_holdout(holdout, {}, 1);
    check(!e.ok, "deg: empty class list -> !ok");
}

// ---- 6. selector: calibration is untouched (holdout-only read) ---------------

void test_select_ignores_calibration() {
    // Build a holdout where the ONLY "BPSK" would be in calibration, not holdout:
    // the caller passes holdout only, so a BPSK-free holdout must fail-closed even
    // though the (not passed) calibration subset would contain one.
    std::vector<iqdloop::FrozenIq> holdout = { fz("OOK", "h0.ci16"),
                                               fz("OOK", "h1.ci16") };
    const auto sel = iqrffix9r2a::select_diagnostic_holdout(holdout, {"BPSK"}, 1);
    check(!sel.ok, "calib: holdout-only read fail-closes on absent BPSK");
}

// ---- 7. gate: PASS on a fully-consistent input -------------------------------

iqrffix9r2a::DiagnosticGateInput make_good_gate() {
    iqrffix9r2a::DiagnosticGateInput g;
    g.requested_classes = "BPSK,4ASK";
    g.selected_classes = "BPSK,4ASK";
    g.requested_count = 2;
    g.holdout_files = 2;
    g.estimate_computed = 2;
    g.estimate_valid = 2;
    g.frame_layout_match = 2;
    g.training_exact_match = 2;
    g.settling_guard_exact_zero = 2;
    g.payload_training_exact_match = 2;
    g.payload_exact_match = 2;
    g.tx_push_ok = 2;
    g.tx_clipped = 0;
    g.rx_clipped = 0;
    g.training_corr_min = 0.999;
    g.payload_training_residual_max = 0.001;
    g.payload_scale_error_max = 0.01;
    g.scored = 2;
    g.rf_excluded = 0;
    g.prediction_agreement = 2;
    g.restore_ok = true;
    return g;
}

void test_gate_pass() {
    const auto r = iqrffix9r2a::evaluate_diagnostic_gate(make_good_gate());
    check(r.pass, "gate: PASS");
    check(r.report.empty(), "gate: empty report on pass");
}

// ---- 8. gate: selected_classes mismatch --------------------------------------

void test_gate_class_mismatch() {
    auto g = make_good_gate();
    g.selected_classes = "BPSK";
    const auto r = iqrffix9r2a::evaluate_diagnostic_gate(g);
    check(!r.pass, "gate: class mismatch FAIL");
    check(r.report.find("selected_classes") != std::string::npos, "gate: names cause");
}

// ---- 9. gate: count mismatches (each per-file count, plus holdout count) -----

void test_gate_count_mismatches() {
    {
        auto g = make_good_gate();
        g.holdout_files = 3;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: holdout_files!=requested FAIL");
    }
    {
        auto g = make_good_gate();
        g.estimate_computed = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: estimate_computed FAIL");
    }
    {
        auto g = make_good_gate();
        g.estimate_valid = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: estimate_valid FAIL");
    }
    {
        auto g = make_good_gate();
        g.frame_layout_match = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: frame_layout_match FAIL");
    }
    {
        auto g = make_good_gate();
        g.training_exact_match = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: training_exact_match FAIL");
    }
    {
        auto g = make_good_gate();
        g.payload_exact_match = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: payload_exact_match FAIL");
    }
    {
        auto g = make_good_gate();
        g.tx_push_ok = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass,
              "gate: tx_push_ok FAIL");
    }
}

// ---- 10. gate: clip / corr / residual / restore thresholds -------------------

void test_gate_thresholds() {
    {
        auto g = make_good_gate();
        g.tx_clipped = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass, "gate: tx_clipped FAIL");
    }
    {
        auto g = make_good_gate();
        g.rx_clipped = 1;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass, "gate: rx_clipped FAIL");
    }
    {
        auto g = make_good_gate();
        g.training_corr_min = 0.89999;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass, "gate: corr<0.90 FAIL");
    }
    {
        auto g = make_good_gate();
        g.training_corr_min = 0.90;   // boundary: 0.90 is NOT < 0.90 -> passes this field
        g.payload_training_residual_max = 0.10001;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass, "gate: residual>0.10 FAIL");
    }
    {
        auto g = make_good_gate();
        g.restore_ok = false;
        check(!iqrffix9r2a::evaluate_diagnostic_gate(g).pass, "gate: restore_ok=false FAIL");
    }
}

// ---- 11. gate: corr/residual boundary values still pass ----------------------

void test_gate_boundary_pass() {
    auto g = make_good_gate();
    g.training_corr_min = 0.90;        // inclusive lower bound
    g.payload_training_residual_max = 0.10;    // inclusive upper bound
    const auto r = iqrffix9r2a::evaluate_diagnostic_gate(g);
    check(r.pass, "gate: corr=0.90 / residual=0.10 boundary PASS");
}

// ---- 12. integration: selection + gate reproduce the R8 verdict --------------

void test_integration_selection_gate() {
    const auto holdout = make_holdout();
    const auto sel = iqrffix9r2a::select_diagnostic_holdout(
        holdout, {"BPSK", "4ASK"}, 1);
    check(sel.ok, "int: selection ok");

    iqrffix9r2a::DiagnosticGateInput g = make_good_gate();
    g.requested_count = static_cast<std::size_t>(sel.selected_index.size());
    g.holdout_files = static_cast<std::size_t>(sel.selected_index.size());
    g.estimate_computed = g.holdout_files;
    g.estimate_valid = g.holdout_files;
    g.frame_layout_match = g.holdout_files;
    g.training_exact_match = g.holdout_files;
    g.settling_guard_exact_zero = g.holdout_files;
    g.payload_training_exact_match = g.holdout_files;
    g.payload_exact_match = g.holdout_files;
    g.tx_push_ok = g.holdout_files;
    g.scored = g.holdout_files;
    g.prediction_agreement = g.holdout_files;
    const auto r = iqrffix9r2a::evaluate_diagnostic_gate(g);
    check(r.pass, "int: BPSK+4ASK selection + gate PASS");
}

// ---- 13. integration: a single failed file among the two flips the verdict ---

void test_integration_one_file_fails() {
    const auto holdout = make_holdout();
    const auto sel = iqrffix9r2a::select_diagnostic_holdout(
        holdout, {"BPSK", "4ASK"}, 1);

    iqrffix9r2a::DiagnosticGateInput g = make_good_gate();
    g.requested_count = static_cast<std::size_t>(sel.selected_index.size());
    g.holdout_files = static_cast<std::size_t>(sel.selected_index.size());
    g.estimate_computed = g.holdout_files;
    g.estimate_valid = g.holdout_files;
    g.frame_layout_match = g.holdout_files;
    g.training_exact_match = g.holdout_files;
    g.settling_guard_exact_zero = g.holdout_files;
    g.payload_training_exact_match = g.holdout_files;
    g.payload_exact_match = g.holdout_files;
    g.scored = g.holdout_files;
    g.prediction_agreement = g.holdout_files;
    g.tx_push_ok = g.holdout_files - 1;   // one file's TX push failed
    const auto r = iqrffix9r2a::evaluate_diagnostic_gate(g);
    check(!r.pass, "int: one-file tx_push failure -> gate FAIL");
    check(r.report.find("tx_push_ok") != std::string::npos, "int: names tx_push_ok");
}

}  // namespace

void run_test(const char* name, void (*fn)()) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main() {
    std::printf("test_iq_rf_loopback_23class_fix9r2a\n");
    run_test("select_bpsk_4ask", test_select_bpsk_4ask);
    run_test("select_per_class_two", test_select_per_class_two);
    run_test("select_absent_class", test_select_absent_class);
    run_test("select_underfilled", test_select_underfilled);
    run_test("select_degenerate", test_select_degenerate);
    run_test("select_ignores_calibration", test_select_ignores_calibration);
    run_test("gate_pass", test_gate_pass);
    run_test("gate_class_mismatch", test_gate_class_mismatch);
    run_test("gate_count_mismatches", test_gate_count_mismatches);
    run_test("gate_thresholds", test_gate_thresholds);
    run_test("gate_boundary_pass", test_gate_boundary_pass);
    run_test("integration_selection_gate", test_integration_selection_gate);
    run_test("integration_one_file_fails", test_integration_one_file_fails);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
