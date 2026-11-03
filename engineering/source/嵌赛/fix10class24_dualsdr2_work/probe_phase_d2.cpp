// probe_phase_d2.cpp -- TEMPORARY. Sweep the preamble + payload-training references
// across the WHOLE raw capture to map the actual frame structure and find where each
// known sequence actually lives. Decisive for resolving host vs board divergence.
#include "iq_dual_sdr_coarse_cfo_recovery.hpp"
#include "iq_rf_training_frame.hpp"
#include "sha256.hpp"

#include <cstdio>
#include <complex>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

static std::string read_file(const std::string& p) {
    std::ifstream f(p, std::ios::binary); std::ostringstream ss; ss << f.rdbuf(); return ss.str();
}
static std::vector<std::int16_t> read_ci16(const std::string& p) {
    const std::string raw = read_file(p);
    std::vector<std::int16_t> out(raw.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i)
        out[i] = static_cast<std::int16_t>(
            static_cast<std::uint16_t>(static_cast<unsigned char>(raw[i*2])) |
            (static_cast<std::uint16_t>(static_cast<unsigned char>(raw[i*2+1])) << 8));
    return out;
}

// Report the top-K correlation peaks of `ref` against `rx` over [0, rx.size()-ref.size()).
static void top_peaks(const std::vector<std::complex<double>>& rx,
                      const std::vector<std::complex<double>>& ref,
                      const char* name, int k, bool integer_only) {
    const std::size_t n = rx.size() - ref.size();
    std::vector<std::pair<double, std::size_t>> best;
    best.reserve(static_cast<std::size_t>(k) + 1);
    for (std::size_t s = 0; s <= n; ++s) {
        double c;
        if (integer_only)
            c = iqrfrec::detail::normalized_corr(rx, s, ref);
        else
            c = iqdual23fix10::detail::fractional_reference_corr(rx, s, 0.0, ref);
        if (best.size() < static_cast<std::size_t>(k) || c > best.back().first) {
            best.emplace_back(c, s);
            std::sort(best.begin(), best.end(),
                      [](const auto& a, const auto& b) { return a.first > b.first; });
            if (best.size() > static_cast<std::size_t>(k)) best.pop_back();
        }
    }
    std::printf("== %s top-%d peaks ==\n", name, k);
    for (const auto& p : best)
        std::printf("  offset=%zu corr=%.15f\n", p.second, p.first);
}

int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: %s <dump-dir>\n", argv[0]); return 2; }
    const std::string dir = argv[1];
    const std::vector<std::int16_t> iq = read_ci16(dir + "/raw_rx_ci16le.bin");
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);
    std::printf("rx complex_count=%zu\n", rx.size());

    const std::vector<std::complex<double>> pre = iqrftrain::preamble_complex();
    const std::vector<std::complex<double>> pt  = iqrftrain::payload_gain_training_complex();
    const std::vector<std::complex<double>> tail = iqrftrain::tail_complex();

    top_peaks(rx, pre, "preamble", 8, true);
    top_peaks(rx, pt, "payload_training", 8, true);
    top_peaks(rx, tail, "tail", 8, true);

    // Cross-check: preamble corr AT each preamble peak, and payload-training corr at
    // (peak+2048). Report the +2048 corr for the top preamble peaks.
    std::printf("== preamble peak -> payload-training at +2048 ==\n");
    for (std::size_t p : {36074ul}) {
        const std::size_t o = p + iqrftrain::kPayloadTrainingOffset;
        if (o + iqrftrain::kPayloadTrainingComplex > rx.size()) continue;
        const double ptc = iqrfrec::detail::normalized_corr(rx, o, pt);
        std::printf("  preamble=%zu -> pt@%zu corr=%.15f\n", p, o, ptc);
    }
    // Also check the OTHER cyclic preamble location (36074 +/- 59904).
    for (std::size_t p : {36074ul}) {
        const long alt = static_cast<long>(p) - static_cast<long>(iqrflayout::kFramePeriodComplex);
        if (alt >= 0) {
            const std::size_t o = static_cast<std::size_t>(alt) + iqrftrain::kPayloadTrainingOffset;
            if (o + iqrftrain::kPayloadTrainingComplex <= rx.size()) {
                const double ptc = iqrfrec::detail::normalized_corr(rx, o, pt);
                std::printf("  preamble=%ld -> pt@%zu corr=%.15f\n", alt, o, ptc);
            }
        }
    }
    return 0;
}
