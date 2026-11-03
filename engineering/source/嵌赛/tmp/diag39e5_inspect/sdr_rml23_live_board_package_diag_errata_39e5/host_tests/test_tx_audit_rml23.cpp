// test_tx_audit_rml23.cpp -- host tests for the RML23 TX-path audit A/B split
// (errata 39e5 Stage C, #9; Evidence 8).  iCraft-free/libiio-free.
//
// Evidence 8 was a category error: a prior TX audit inspected a locally-built
// "8ASK" waveform array and reported it as the TX buffer, when the RML23 chain
// never transmits 8ASK.  This test separates the two objects and asserts their
// real identities:
//
//   TX_A (the REAL cyclic TX buffer) = board::make_periodic_tone(...) -- a
//        deterministic complex CW tone actually sent by PlutoTx in the loopback
//        phases.  Verified: finite, interleaved, 12-bit peak-limited, and an
//        integer number of periods so the cyclic buffer wraps with NO phase
//        discontinuity, and a near-constant envelope (it is a pure tone, NOT an
//        amplitude-shift-keyed signal).
//
//   TX_B (the "8ASK local array") = a classification LABEL, not a TX buffer.
//        "8ASK" is index 2 of the 24-class source / 23-class deployed order; no
//        code path in the RML23 producer builds an 8ASK TX waveform.  live-rx is
//        RX-only (set_loopback(0), tx_active=0): no TX buffer is ever created.
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/board_common.hpp"
#include "../sdr_adapter/categories.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>

namespace {

int g_pass = 0, g_fail = 0;
void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void test_tx_a_real_cyclic_buffer() {
    const double fs = 2560000.0;   // loopback TX sample rate (2.56 MS/s)
    const double freq = 10000.0;   // 10 kHz CW (divides 2.56 MHz exactly)
    const int periods = 8;
    const double amp = 1500.0;
    const std::vector<std::int16_t> iq =
        board::make_periodic_tone(freq, fs, periods, amp);

    // Interleaved: an even number of int16 (I/Q pairs).
    check(!iq.empty() && (iq.size() % 2) == 0,
          "TX_A: waveform is interleaved int16 (even length)");

    // 12-bit peak-limited (int16 is always finite -- no NaN/Inf to guard).
    double peak = 0.0;
    for (std::int16_t v : iq)
        peak = std::max(peak, static_cast<double>(std::abs(static_cast<int>(v))));
    check(peak <= 2048.0, "TX_A: waveform peak <= 2048 (12-bit DAC full scale)");

    // Integer periods -> seamless cyclic wrap: sample k and sample k + spp repeat
    // to within one DAC count (float-cos 2*pi roundoff is far below 1 count).
    const std::size_t spp = static_cast<std::size_t>(std::llround(fs / freq));
    const std::size_t n_complex = iq.size() / 2;
    check(n_complex == spp * static_cast<std::size_t>(periods),
          "TX_A: length == spp * periods (integer periods)");
    bool seamless = true;
    const std::size_t wrap_samples = spp * static_cast<std::size_t>(periods - 1) * 2;
    for (std::size_t k = 0; k < wrap_samples; ++k) {
        const int d = static_cast<int>(iq[k]) - static_cast<int>(iq[k + spp * 2]);
        if (d < -1 || d > 1) { seamless = false; break; }
    }
    check(seamless, "TX_A: cyclic buffer wraps with no phase discontinuity");

    // Near-constant envelope: it is a pure CW tone (NOT amplitude-shift-keyed).
    // 8ASK would show 8 widely-spaced amplitude levels; a CW tone's |I|^2+|Q|^2
    // stays within a rounding band of A^2 across the whole buffer.
    double mag2_min = 1e18, mag2_max = -1e18;
    for (std::size_t k = 0; k < n_complex; ++k) {
        const double re = iq[k * 2 + 0], im = iq[k * 2 + 1];
        const double m2 = re * re + im * im;
        mag2_min = std::min(mag2_min, m2);
        mag2_max = std::max(mag2_max, m2);
    }
    const double a2 = amp * amp;
    check((mag2_max - mag2_min) < 4.0 * amp,
          "TX_A: constant envelope (pure CW tone, not an ASK signal)");
    check(std::fabs(mag2_max - a2) < 4.0 * amp,
          "TX_A: envelope magnitude == amplitude^2");
}

void test_tx_b_8ask_is_a_label_not_a_buffer() {
    // 8ASK is a classification label in both the 24-class source and the 23-class
    // deployed orders -- NOT a TX waveform.
    check(cat::target_24().class_names.size() == 24, "TX_B: 24-class source order");
    check(cat::target_23().class_names.size() == 23, "TX_B: 23-class deployed order");
    check(cat::target_24().class_names[2] == "8ASK", "TX_B: source index 2 == 8ASK");
    check(cat::target_23().class_names[2] == "8ASK", "TX_B: deployed index 2 == 8ASK");

    // The 8ASK label resolves to a name, but there is no TX-waveform builder for it
    // in the RML23 producer: the only TX path is board::make_periodic_tone (a CW
    // tone).  The 12-class generator's own amplitude-keyed class is 4ASK (index 1),
    // not 8ASK, so no 8ASK waveform is even synthesizable in this chain.
    const cat::Contract c23 = cat::target_23();
    check(cat::label(c23, 2) == "8ASK", "TX_B: label(2) == 8ASK");
    check(cat::label(c23, 1) == "4ASK", "TX_B: label(1) == 4ASK (not 8ASK)");
}

}  // namespace

int main() {
    std::printf("test_tx_audit_rml23\n");
    test_tx_a_real_cyclic_buffer();
    test_tx_b_8ask_is_a_label_not_a_buffer();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
