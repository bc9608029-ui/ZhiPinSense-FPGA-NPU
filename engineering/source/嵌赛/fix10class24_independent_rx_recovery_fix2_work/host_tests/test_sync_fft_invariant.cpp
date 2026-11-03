// test_sync_fft_invariant.cpp -- fix2 B-line host check: the FFT-based locate_preamble
// must return the SAME offset and no_sync decision as the exact O(N*K) brute force, on
// the 24 REAL dual-SDR captures (no device / no libiio -- just the raw .i16 files).
//
// It reads <dir>/<sid>.raw.i16 (136192 complex = 76288-offset sync search), then:
//   * reference: exact brute-force scan with the hoisted preamble (bit-identical to the
//     original per-offset preamble_sync_score, because preamble_ref() is deterministic);
//   * new:       iqindepfix1::locate_preamble (FFT coarse + exact guard-band refine).
// and asserts offset equality and no_sync equality (score < 0.50) for all 24 frames.
//
// Usage: test_sync_fft_invariant <capture-dir>
// Exit 0 iff 24/24 offsets and no_sync match.

#include "../board_package/radioml_independent_rx_runner.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

// Exact O(N*K) reference scan.  Identical formula to the original locate_preamble, but
// with the preamble + energy hoisted (same values, so bit-identical scores).
iqindepfix1::PreambleLocation locate_brute_force(
        const std::vector<std::complex<double>>& rx, std::size_t max_offset) {
    iqindepfix1::PreambleLocation out;
    if (rx.empty()) return out;
    const std::vector<std::complex<double>> pre = iqindepfix1::preamble_ref();
    const std::size_t K = pre.size();
    if (rx.size() < K) return out;
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
    if (argc < 2) {
        std::fprintf(stderr, "usage: test_sync_fft_invariant <capture-dir>\n");
        return 2;
    }
    const std::string dir = argv[1];
    int match_off = 0, match_nosync = 0;
    double max_score_err = 0.0;
    for (int sid = 1; sid <= 24; ++sid) {
        const std::string path =
            iqindepfix1::join_path(dir, std::to_string(sid) + ".raw.i16");
        std::vector<std::int16_t> i16;
        std::string perr;
        if (!iqindepfix1::read_i16_file(path, i16, &perr)) {
            std::fprintf(stderr, "read_i16_file(%s): %s\n", path.c_str(), perr.c_str());
            return 1;
        }
        const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(i16);
        const std::size_t max_off =
            rx.size() > iqindepfix1::kTotalBurstComplex
                ? rx.size() - iqindepfix1::kTotalBurstComplex : 0;

        const iqindepfix1::PreambleLocation ref = locate_brute_force(rx, max_off);
        const iqindepfix1::PreambleLocation got = iqindepfix1::locate_preamble(rx, max_off);

        const bool off_ok = (ref.offset == got.offset);
        const bool nosync_ok =
            ((ref.score < iqindepfix1::kSyncScoreThreshold) ==
             (got.score < iqindepfix1::kSyncScoreThreshold));
        const double score_err =
            std::fabs(ref.score - got.score);
        if (score_err > max_score_err) max_score_err = score_err;
        if (off_ok) ++match_off;
        if (nosync_ok) ++match_nosync;

        std::printf("sid=%02d brute(off=%zu score=%.9f) fft(off=%zu score=%.9f) "
                    "off_ok=%d nosync_ok=%d score_err=%.3e\n",
                    sid, ref.offset, ref.score, got.offset, got.score,
                    off_ok ? 1 : 0, nosync_ok ? 1 : 0, score_err);
    }
    std::printf("SYNC_FFT_INVARIANT offset=%d/24 no_sync=%d/24 max_score_err=%.3e\n",
                match_off, match_nosync, max_score_err);
    return (match_off == 24 && match_nosync == 24) ? 0 : 1;
}
