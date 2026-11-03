// replay_fix10class24_failed_rx.cpp -- fix10class24-dualsdr2 Phase C replayer main.
// Thin argv parser over replay_fix10class24_failed_rx.hpp (the reusable core, also
// unit-tested host-side).  See the header for the full rationale.
//
//   replay_fix10class24_failed_rx --self-test
//   replay_fix10class24_failed_rx --dump-dir failed_rx/1500 [--curves] [--fractional-den 512]
//   replay_fix10class24_failed_rx --dump-dir failed_rx/1500 --canonical-reference [--canonical-file FILE]
//   replay_fix10class24_failed_rx --canonical-vs-runtime

#include "replay_fix10class24_failed_rx.hpp"

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

std::string need_value(int argc, char** argv, int& i, const char* name) {
    if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
    return argv[++i];
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string dump_dir;
        std::string canonical_file;
        bool curves = false;
        bool canonical = false;
        bool canonical_vs_runtime = false;
        int den = 512;
        for (int i = 1; i < argc; ++i) {
            const std::string a = argv[i];
            if (a == "--self-test") return replay24::self_test();
            else if (a == "--dump-dir") dump_dir = need_value(argc, argv, i, "--dump-dir");
            else if (a == "--curves") curves = true;
            else if (a == "--fractional-den")
                den = std::stoi(need_value(argc, argv, i, "--fractional-den"));
            else if (a == "--canonical-reference") canonical = true;
            else if (a == "--canonical-file")
                canonical_file = need_value(argc, argv, i, "--canonical-file");
            else if (a == "--canonical-vs-runtime") canonical_vs_runtime = true;
            else throw std::runtime_error("unknown argument: " + a);
        }
        if (canonical_vs_runtime) {
            replay24::print_canonical_vs_runtime();
            return 0;
        }
        if (dump_dir.empty())
            throw std::runtime_error(
                "usage: replay_fix10class24_failed_rx --dump-dir DIR [--curves] "
                "[--fractional-den 512] [--canonical-reference [--canonical-file FILE]] "
                "| --canonical-vs-runtime | --self-test");

        if (canonical) {
            if (!canonical_file.empty()) replay24::verify_canonical_file(canonical_file);
            const replay24::CanonicalReplayResult cr =
                replay24::replay_canonical_from_dir(dump_dir);
            replay24::print_canonical_replay(dump_dir, cr);
            return (cr.timing_ok && cr.coarse_ok && cr.fine_ok && cr.corr_ok && cr.resid_ok)
                       ? 0 : 1;
        }

        // default (runtime-reference) replay -- unchanged from Batch 1.
        const replay24::ReplayResult r = replay24::replay_from_dir(dump_dir);
        replay24::print_replay(dump_dir, r);

        if (curves) {
            // Recompute the coarse-de-rotated capture + integer timing anchor with the
            // same production estimate() the board used (reuse, not reimplementation).
            const std::vector<std::int16_t> iq =
                replay24::read_ci16_le(dump_dir + "/raw_rx_ci16le.bin");
            const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);
            const double coarse = r.ccr.coarse_cfo_hz;
            std::vector<std::complex<double>> derot(rx.size());
            for (std::size_t n = 0; n < rx.size(); ++n) {
                const double ph = -2.0 * iqrftrain::kPi * coarse *
                                  static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
                derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
            }
            const iqrfrec::PerFileRecovery irec =
                iqrfrec::estimate(derot, replay24::config(r.target_rms));
            replay24::print_timing_curve(derot, irec.timing_offset);
            replay24::print_fractional_curve(derot, irec.timing_offset, r.ccr,
                                             replay24::config(r.target_rms), den);
        }

        // Nonzero exit on a cross-check mismatch so CI / the user can detect it.
        return (r.sha_ok && r.failure_ok && r.timing_ok && r.cfo_ok && r.corr_resid_ok)
                   ? 0 : 1;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "replay_fix10class24_failed_rx: ERROR: %s\n", e.what());
        return 2;
    }
}
