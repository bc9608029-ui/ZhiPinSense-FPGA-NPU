// probe_phase_d4.cpp -- TEMPORARY. Reproduce the BOARD's recovery on the HOST using
// the FROZEN CANONICAL payload-training reference (fix10canonical) instead of the
// cross-arch non-deterministic runtime one (iqrftrain::payload_gain_training_complex).
// This isolates the recovery from the Finding-1 reference mismatch and lets us
// reproduce the board's payload_training_corr/residual + coarse CFO, then dissect the
// residual structure (phase-noise vs thermal-noise vs amplitude).
#include "iq_dual_sdr_coarse_cfo_recovery.hpp"
#include "iq_rf_training_frame.hpp"
#include "iq_fix10_canonical_frame.hpp"
#include "sha256.hpp"

#include <cstdio>
#include <cmath>
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
template <class C>
static std::vector<std::complex<double>> cplx(const C& v) {
    std::vector<std::complex<double>> o(v.size() / 2);
    for (std::size_t k = 0; k < o.size(); ++k)
        o[k] = std::complex<double>(static_cast<double>(v[k*2]),
                                    static_cast<double>(v[k*2+1]));
    return o;
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

    const std::vector<std::complex<double>> pre_c = cplx(fix10canonical::kCanonicalPreamble);
    const std::vector<std::complex<double>> pt_c  = cplx(fix10canonical::kCanonicalPayloadTraining);

    // Pass 1 (preamble deterministic across arch)
    const iqrfrec::PerFileRecovery r1 = iqrfrec::estimate(rx, c);
    const std::size_t best = r1.timing_offset;
    std::printf("pass1 timing=%zu preamble_corr(runtime)=%.9f\n", best, r1.training_corr);

    // Coarse CFO with canonical payload-training reference
    const std::complex<double> a_pre = iqrfrec::detail::ls_gain(rx, best, pre_c);
    const std::complex<double> a_pt  = iqrfrec::detail::ls_gain(
        rx, best + iqrftrain::kPayloadTrainingOffset, pt_c);
    const double coarse = std::arg(a_pt * std::conj(a_pre)) *
        static_cast<double>(iqrftrain::kFs) /
        (2.0 * iqrftrain::kPi * static_cast<double>(iqrftrain::kPayloadTrainingOffset));
    std::printf("coarse_cfo_hz(canonical)=%.9f  a_pre=(%.6f,%.6f) a_pt=(%.6f,%.6f)\n",
                coarse, a_pre.real(), a_pre.imag(), a_pt.real(), a_pt.imag());

    // De-rotate
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * coarse *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }

    // Pass 2 + fractional timing (preamble deterministic)
    const iqrfrec::PerFileRecovery integer_rec = iqrfrec::estimate(derot, c);
    const iqdual23fix10::detail::FractionalTiming ft =
        iqdual23fix10::detail::estimate_fractional_timing(derot, integer_rec.timing_offset);
    std::printf("pass2 timing=%zu fractional_samples=%.9f corr_before=%.9f corr_after=%.9f\n",
                integer_rec.timing_offset, ft.samples,
                integer_rec.training_corr, ft.corr);

    const std::size_t pt_start = integer_rec.timing_offset + iqrftrain::kPayloadTrainingOffset;
    const double pfb = iqdual23fix10::detail::fractional_reference_corr(derot, pt_start, 0.0, pt_c);
    const double pfa = iqdual23fix10::detail::fractional_reference_corr(derot, pt_start, ft.samples, pt_c);
    std::printf("payload_fractional_corr_before=%.9f after=%.9f\n", pfb, pfa);

    const std::vector<std::complex<double>> aligned =
        iqdual23fix10::detail::apply_fractional_advance(derot, ft.samples);
    const iqrfrec::PerFileRecovery fin = iqrfrec::estimate(aligned, c);
    std::printf("final timing=%zu fine_cfo_hz=%.9f sro_ppm=%.9f preamble_corr=%.9f\n",
                fin.timing_offset, fin.cfo_hz, fin.sro_ppm, fin.training_corr);

    // Recompute step-6.5 payload-training corr/residual with the canonical reference
    const double sro_frac = fin.sro_ppm * 1e-6;
    const std::size_t bf = fin.timing_offset;
    const double cfo = fin.cfo_hz;
    const std::size_t ptoff = iqrftrain::kPayloadTrainingOffset;
    auto stretched = [&](std::size_t k) -> std::complex<double> {
        double x = static_cast<double>(ptoff + k) / (1.0 + sro_frac) -
                   static_cast<double>(ptoff);
        if (x < 0.0) x = 0.0;
        if (x > static_cast<double>(pt_c.size() - 1)) x = static_cast<double>(pt_c.size() - 1);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(x));
        const std::size_t i1 = i0 + 1;
        if (i1 < pt_c.size()) {
            const double fr = x - static_cast<double>(i0);
            return pt_c[i0] * (1.0 - fr) + pt_c[i1] * fr;
        }
        return pt_c[i0];
    };
    std::complex<double> num_pt(0.0, 0.0);
    double den_r_pt = 0.0, den_x_pt = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const std::complex<double> rk = stretched(k);
        const double ph = 2.0 * iqrftrain::kPi * cfo *
                          static_cast<double>(ptoff + k) / static_cast<double>(iqrftrain::kFs);
        const std::complex<double> derot_k(std::cos(ph), -std::sin(ph));
        const std::complex<double>& x = aligned[bf + ptoff + k];
        num_pt += x * std::conj(rk) * derot_k;
        den_r_pt += iqrfrec::detail::norm2(rk);
        den_x_pt += iqrfrec::detail::norm2(x);
    }
    const std::complex<double> a_pay = num_pt / den_r_pt;
    const double corr = std::abs(num_pt) / std::sqrt(den_x_pt * den_r_pt);
    double num_res = 0.0, den_res = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const std::complex<double> rk = stretched(k);
        const double ph = 2.0 * iqrftrain::kPi * cfo *
                          static_cast<double>(ptoff + k) / static_cast<double>(iqrftrain::kFs);
        const std::complex<double> rot(std::cos(ph), std::sin(ph));
        const std::complex<double> model = a_pay * rk * rot;
        const std::complex<double> err = aligned[bf + ptoff + k] - model;
        num_res += iqrfrec::detail::norm2(err);
        den_res += iqrfrec::detail::norm2(model);
    }
    const double residual = std::sqrt(num_res / den_res);
    std::printf("CANONICAL payload_gain_mag=%.9f payload_phase_deg=%.9f corr=%.9f residual=%.9f\n",
                std::abs(a_pay), std::arg(a_pay) * 180.0 / iqrftrain::kPi, corr, residual);

    // ---- residual structure: split err into in-phase (along model) vs quadrature ----
    // phase-noise/rotation -> error mostly quadrature; thermal noise -> isotropic.
    double along = 0.0, quad = 0.0, model_pow = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const std::complex<double> rk = stretched(k);
        const double ph = 2.0 * iqrftrain::kPi * cfo *
                          static_cast<double>(ptoff + k) / static_cast<double>(iqrftrain::kFs);
        const std::complex<double> rot(std::cos(ph), std::sin(ph));
        const std::complex<double> model = a_pay * rk * rot;
        const std::complex<double> err = aligned[bf + ptoff + k] - model;
        const std::complex<double> u = model / std::abs(model); // unit direction of model
        const std::complex<double> e = err * std::conj(u);       // err in model frame
        along += e.real() * e.real();
        quad  += e.imag() * e.imag();
        model_pow += std::norm(model);
    }
    std::printf("residual_split along_pow=%.9f quad_pow=%.9f model_pow=%.9f\n",
                along, quad, model_pow);
    std::printf("  along_rms=%.6f quad_rms=%.6f (relative to |model| sqrt)\n",
                std::sqrt(along), std::sqrt(quad));
    return 0;
}
