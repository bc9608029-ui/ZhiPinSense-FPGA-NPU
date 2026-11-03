// probe_phase_d.cpp -- TEMPORARY diagnostic for Phase D root-cause. Reads the real
// BPSK failed-RX dump and prints every intermediate of the production recovery, so we
// can compare host (x86 g++) against the board (aarch64) log field by field.
// NOT part of the deliverable.
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
    std::ifstream f(p, std::ios::binary);
    std::ostringstream ss; ss << f.rdbuf(); return ss.str();
}
static std::vector<std::int16_t> read_ci16(const std::string& p) {
    const std::string raw = read_file(p);
    std::vector<std::int16_t> out(raw.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i) {
        out[i] = static_cast<std::int16_t>(
            static_cast<std::uint16_t>(static_cast<unsigned char>(raw[i*2])) |
            (static_cast<std::uint16_t>(static_cast<unsigned char>(raw[i*2+1])) << 8));
    }
    return out;
}
static iqrfrec::EstimateConfig cfg(double rms) {
    iqrfrec::EstimateConfig c;
    c.min_corr = 0.9;
    c.max_residual = iqrfrec::kPayloadTrainingResidualMax;
    c.max_cfo_hz = static_cast<double>(iqrftrain::kFs) /
                   (2.0 * static_cast<double>(iqrftrain::kTailStart));
    c.max_sro_ppm = 30.0;
    c.search_limit = 0;
    c.payload_tx_target_rms = rms;
    return c;
}

int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: %s <dump-dir>\n", argv[0]); return 2; }
    const std::string dir = argv[1];
    const std::vector<std::int16_t> iq = read_ci16(dir + "/raw_rx_ci16le.bin");
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);
    const iqrfrec::EstimateConfig c = cfg(2048.0);

    std::printf("== PASS 1 estimate(rx) ==\n");
    const iqrfrec::PerFileRecovery r1 = iqrfrec::estimate(rx, c);
    std::printf("  timing_offset=%zu training_corr=%.15f coarse_cfo_hz=%.15f\n",
                r1.timing_offset, r1.training_corr, r1.coarse_cfo_hz);
    std::printf("  gain_mag=%.15f phase_deg=%.15f cfo_hz=%.15f sro_ppm=%.15f phase_drift_deg=%.15f\n",
                r1.gain_mag, r1.phase_deg, r1.cfo_hz, r1.sro_ppm, r1.phase_drift_deg);
    std::printf("  payload_gain_mag=%.15f payload_phase_deg=%.15f payload_training_corr=%.15f payload_training_residual=%.15f\n",
                r1.payload_gain_mag, r1.payload_phase_deg,
                r1.payload_training_corr, r1.payload_training_residual);
    std::printf("  failure=%s valid=%d\n", iqrfrec::failure_token(r1.failure), r1.valid ? 1 : 0);

    std::printf("== coarse CFO decomposition (best=%zu) ==\n", r1.timing_offset);
    const std::size_t best = r1.timing_offset;
    const std::vector<std::complex<double>> pre = iqrftrain::preamble_complex();
    const std::vector<std::complex<double>> pt = iqrftrain::payload_gain_training_complex();
    const std::complex<double> a_pre = iqrfrec::detail::ls_gain(rx, best, pre);
    const std::complex<double> a_pt  = iqrfrec::detail::ls_gain(rx, best + iqrftrain::kPayloadTrainingOffset, pt);
    const double med = std::arg(a_pt * std::conj(a_pre)) *
        static_cast<double>(iqrftrain::kFs) /
        (2.0 * iqrftrain::kPi * static_cast<double>(iqrftrain::kPayloadTrainingOffset));
    std::printf("  a_pre=(%.15f,%.15f) |a_pre|=%.15f arg=%.15fdeg\n",
                a_pre.real(), a_pre.imag(), std::abs(a_pre),
                std::arg(a_pre) * 180.0 / iqrftrain::kPi);
    std::printf("  a_pt =(%.15f,%.15f) |a_pt|=%.15f arg=%.15fdeg\n",
                a_pt.real(), a_pt.imag(), std::abs(a_pt),
                std::arg(a_pt) * 180.0 / iqrftrain::kPi);
    std::printf("  med(coarse_cfo_hz)=%.15f\n", med);

    std::printf("== full recover_payload_with_coarse_cfo ==\n");
    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, c, 2.29219);
    const iqrfrec::PerFileRecovery& rec = ccr.rec;
    std::printf("  coarse_cfo_hz=%.15f\n", ccr.coarse_cfo_hz);
    std::printf("  fractional_corr_before=%.15f fractional_corr_after=%.15f fractional_timing_samples=%.15f\n",
                ccr.fractional_corr_before, ccr.fractional_corr_after, ccr.fractional_timing_samples);
    std::printf("  payload_fractional_corr_before=%.15f after=%.15f best_frac=%.15f best_corr=%.15f best_pre_corr=%.15f\n",
                ccr.payload_fractional_corr_before, ccr.payload_fractional_corr_after,
                ccr.payload_best_fractional_timing_samples, ccr.payload_best_fractional_corr,
                ccr.payload_best_fractional_preamble_corr);
    std::printf("  final: timing_offset=%zu training_corr=%.15f gain_mag=%.15f phase_deg=%.15f\n",
                rec.timing_offset, rec.training_corr, rec.gain_mag, rec.phase_deg);
    std::printf("  final: cfo_hz=%.15f sro_ppm=%.15f phase_drift_deg=%.15f\n",
                rec.cfo_hz, rec.sro_ppm, rec.phase_drift_deg);
    std::printf("  final: payload_gain_mag=%.15f payload_rms_gain_mag=%.15f payload_phase_deg=%.15f\n",
                rec.payload_gain_mag, rec.payload_rms_gain_mag, rec.payload_phase_deg);
    std::printf("  final: payload_training_corr=%.15f payload_training_residual=%.15f\n",
                rec.payload_training_corr, rec.payload_training_residual);
    std::printf("  final: failure=%s valid=%d\n", iqrfrec::failure_token(rec.failure), rec.valid ? 1 : 0);

    // Direct fractional-reference correlation sweep of the payload-training block
    // around the pass-2 timing (which is what the board reported as 0.9902 before).
    // Sweep integer offsets around best+2048 to see if the block is elsewhere.
    std::printf("== payload-training block location sweep (corr vs integer offset from best+2048) ==\n");
    for (int d = -8; d <= 8; ++d) {
        const long s = static_cast<long>(best + iqrftrain::kPayloadTrainingOffset) + d;
        if (s < 0 || static_cast<std::size_t>(s + iqrftrain::kPayloadTrainingComplex) > rx.size()) continue;
        const double corr = iqdual23fix10::detail::fractional_reference_corr(
            rx, static_cast<std::size_t>(s), 0.0, pt);
        std::printf("  d=%+d offset=%ld corr=%.15f\n", d, s, corr);
    }
    return 0;
}
