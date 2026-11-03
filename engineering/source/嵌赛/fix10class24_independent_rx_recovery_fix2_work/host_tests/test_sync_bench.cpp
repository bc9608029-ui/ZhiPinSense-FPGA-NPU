// test_sync_bench.cpp -- fix2 B-line: wall-clock compare of the exact O(N*K) brute-force
// sync scan vs the new FFT locate_preamble, on one real capture (host x86 relative number;
// the ARM board sees an even larger absolute win because the eliminated per-offset
// preamble regeneration is 1024 sin/cos calls, i.e. ~78M transcendental calls/frame).

#include "../board_package/radioml_independent_rx_runner.hpp"

#include <chrono>
#include <cstdio>
#include <string>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;

double us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

iqindepfix1::PreambleLocation locate_brute_force(
        const std::vector<std::complex<double>>& rx, std::size_t max_offset) {
    iqindepfix1::PreambleLocation out;
    const std::vector<std::complex<double>> pre = iqindepfix1::preamble_ref();
    const std::size_t K = pre.size();
    const std::size_t max_end = rx.size() - K;
    const std::size_t limit = max_offset < max_end ? max_offset : max_end;
    double p_energy = 0.0;
    for (const auto& z : pre) p_energy += std::norm(z);
    for (std::size_t off = 0; off <= limit; ++off) {
        const double v = iqindepfix1::preamble_sync_score(rx, off, pre, p_energy);
        if (v > out.score) { out.score = v; out.offset = off; }
    }
    return out;
}
}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: test_sync_bench <dir>\n"); return 2; }
    const std::string dir = argv[1];
    std::vector<std::int16_t> i16;
    std::string perr;
    if (!iqindepfix1::read_i16_file(iqindepfix1::join_path(dir, "1.raw.i16"), i16, &perr))
        return 1;
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(i16);
    const std::size_t max_off =
        rx.size() > iqindepfix1::kTotalBurstComplex
            ? rx.size() - iqindepfix1::kTotalBurstComplex : 0;

    auto t0 = Clock::now();
    const auto bf = locate_brute_force(rx, max_off);
    const double bf_us = us(t0);
    t0 = Clock::now();
    const auto fft = iqindepfix1::locate_preamble(rx, max_off);
    const double fft_us = us(t0);

    std::printf("brute_force: off=%zu score=%.9f %.1f us\n", bf.offset, bf.score, bf_us);
    std::printf("fft        : off=%zu score=%.9f %.1f us\n", fft.offset, fft.score, fft_us);
    std::printf("speedup=%.1fx (host x86; board/ARM larger due to 78M sin/cos removed)\n",
                bf_us / fft_us);
    return 0;
}
