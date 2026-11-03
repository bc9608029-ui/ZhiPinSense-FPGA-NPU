// test_route_e_raw_rx_output_fields.cpp -- compile-time + runtime guard for the
// Stage H-E / Route E RawRxOutput persistence fields.
//
// This file exists so the PACKAGED synthetic_iq_runner.hpp is PROVEN to carry the
// Route E increment (RawRxOutput::iq / ::pushed_complex / ::quant_scale).  Those
// three fields were the ones missing from the erroneous 2d8b8bab… merged package
// (whose synthetic_iq_runner.hpp had been silently reverted to the route-D
// baseline), which made board_gate9_full_chain_rml23.cpp fail to compile on the
// board.  If a future package omits or reverts synthetic_iq_runner.hpp, this test
// FAILS TO COMPILE (the field names do not exist), which is the exact failure mode
// it is meant to catch -- so it must always be built from the PACKAGED header, not
// just the working tree.
//
// iCraft-free and libiio-free: exercises only chain_common.hpp / resampler.cpp
// (the same code the board runs) plus the runner header.
//
// Build/run: see host_tests/build_host_tests.sh (links ../sdr_adapter/resampler.cpp).

#include "../board_package/synthetic_iq_runner.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void check_near(double got, double want, double tol, const char* what) {
    if (std::fabs(got - want) <= tol) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (got %.9g want %.9g)\n", what, got, want); }
}

void test_raw_rx_output_fields() {
    syniq_run::GeneratedConfig cfg;
    cfg.mod = syniq::Modulation::QPSK;
    cfg.sps = 160;
    cfg.seed = 0x39e5ULL;
    cfg.norm = "none";
    cfg.rms_counts = 16.0;

    const int frames = 4;
    const syniq_run::RawRxOutput out = syniq_run::generate_raw_rx_tensors(cfg, frames);

    // --- explicit field access (the compile-time guard itself) -----------------
    // If any of these three Route E fields is missing from the packaged header,
    // this translation unit will not compile.
    const std::vector<std::int16_t>& iq = out.iq;     // Route E field
    const std::uint64_t pushed = out.pushed_complex;  // Route E field
    const double qscale = out.quant_scale;            // Route E field

    // --- runtime invariants ---------------------------------------------------
    check(!iq.empty(), "iq: non-empty");
    check(pushed > 0, "pushed_complex > 0");
    check(qscale > 0.0 && std::isfinite(qscale), "quant_scale finite and > 0");

    // iq is the FULL quantized waveform (interleaved I/Q: I0,Q0,I1,Q1,...), of
    // which only the first `pushed_complex` complex samples are pushed into the
    // PreprocessChain and persisted.  So iq holds at least 2 * pushed_complex
    // int16 values (in practice more, because the generator over-produces symbols
    // so the chain's `required_input` prefix is always available).
    check(iq.size() % 2 == 0, "iq.size() even (interleaved I/Q)");
    check(iq.size() >= static_cast<std::size_t>(pushed) * 2,
          "iq.size() >= 2 * pushed_complex (full waveform covers pushed prefix)");

    // With norm="none" the unit-power constellation + unit-energy RRC gives a
    // waveform RMS of ~1.0, so quant_scale = rms_counts / pre_rms ~= 16.0.
    check_near(qscale, 16.0, 2.0, "quant_scale ~= rms_counts (16)");

    // Every int16 sample is in range and the quantizer reported no clipping; the
    // carried peak must agree with the quantizer's reported peak (within the
    // lround rounding error of half an LSB).
    std::int64_t peak = 0;
    for (std::int16_t v : iq) {
        const std::int64_t a = v < 0 ? -static_cast<std::int64_t>(v)
                                     : static_cast<std::int64_t>(v);
        if (a > peak) peak = a;
    }
    check(peak <= 32767, "iq: all samples within int16 range");
    check(out.quant.clip == 0, "iq: quantizer reported no clipping");
    check_near(static_cast<double>(peak), out.quant.peak_counts, 0.5,
               "iq peak == quant.peak_counts (within 0.5 LSB)");

    // Determinism: the same config reproduces the same iq bytes, push count and
    // scale -- so a 3-way SHA persisted from these fields is reproducible.
    const auto out2 = syniq_run::generate_raw_rx_tensors(cfg, frames);
    check(out2.iq == iq, "iq deterministic");
    check(out2.pushed_complex == pushed, "pushed_complex deterministic");
    check(out2.quant_scale == qscale, "quant_scale deterministic");
}

}  // namespace

int main() {
    std::printf("test_route_e_raw_rx_output_fields\n");
    test_raw_rx_output_fields();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
