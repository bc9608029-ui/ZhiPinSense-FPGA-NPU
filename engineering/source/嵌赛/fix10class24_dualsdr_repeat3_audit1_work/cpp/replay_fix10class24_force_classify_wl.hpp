#pragma once

// replay_fix10class24_force_classify_wl.hpp -- fix10class24-dualsdr-repeat3-audit1
// Phase B/C diagnostic core (wide-linear-corrected forced classification).
//
// This is the CORRECTED successor to the older
//   host_tools/replay_fix10class24_failed_rx_force_classify.hpp
// (which is fix10class24-rxresidual-audit1's SCALAR-ONLY force classifier).  The older
// tool had exactly two defects for the CURRENT production recovery chain:
//   1. apply_provisional() was a copy of the PRE-wide-linear iqrfrec::apply() -- it had
//      NO wide-linear branch, so a rejected capture whose mixer-image compensation was
//      enabled by estimate() would be mis-recovered on the scalar path.
//   2. build_provisional_rec() hardcoded failure==PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH and
//      copied NO wide-linear fields, so even a corrected apply_provisional would never
//      see wide_linear_enabled==true.
//
// Both are fixed here, and the result is cross-checked against the BOARD's own
// FIX10CLASS24_BF16_WIDE_LINEAR run.log line (canonical reference == aarch64 board
// semantics):
//   * apply_provisional() is a byte-for-byte copy of the CURRENT iqrfrec::apply()
//     (iq_rf_sync_recovery.hpp) INCLUDING its wide-linear branch, with ONLY the
//     `!rec.valid` throw removed.  The unsafe-gain / unsafe-tx-scale fail-closed guards
//     are KEPT.  It lives in this diagnostic namespace -- never in iqrfrec -- so the
//     production runner cannot call it.
//   * canonical_wide_linear_recompute() mirrors iqrfrec::estimate() step 6.6 EXACTLY but
//     with the frozen canonical payload-training reference (replay24::
//     canonical_payload_training_complex()), because estimate()'s own reference is
//     generated with runtime std::sqrt/std::lround and diverges x86 vs aarch64 (the D1
//     cross-arch blind spot).  This reproduces the BOARD's (a, b), validation residuals,
//     image ratio and enabled flag.
//   * build_provisional_rec() keeps valid==false and the ACTUAL failure enum read from the
//     dump's recovery_diagnostics.json (never hardcoded), copies timing/cfo/sro/
//     payload_rms_gain_mag from the final production estimate fin, the canonical
//     payload gain/phase, the dump tx_scale, and the canonical wide-linear fields.
//   * run_classification_chain() is the VERBATIM production chain
//     int16 -> PreprocessChain -> D2 restore -> reference window -> [2,1024] model input.
//
// iCraft-free / libiio-free / NPU-free.  This header is compiled only by host tools and
// host tests, never linked into the production runner.

#include "replay_fix10class24_failed_rx.hpp"   // replay24:: canonical replay + helpers
#include "chain_common.hpp"
#include "iq_digital_loopback.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace replay24wl {

// ---- provisional apply (verbatim CURRENT iqrfrec::apply WITH wide-linear, minus the
// ---- valid throw).  The unsafe-gain and unsafe-tx-scale guards are KEPT. ------------
inline std::vector<std::complex<double>> apply_provisional(
        const std::vector<std::complex<double>>& rx, const iqrfrec::PerFileRecovery& rec) {
    const double mag = (rec.payload_rms_gain_mag > 1e-12 &&
                        std::isfinite(rec.payload_rms_gain_mag))
                           ? rec.payload_rms_gain_mag : rec.payload_gain_mag;
    const double mag2 = mag * mag;
    if (!std::isfinite(mag) || mag <= 1e-12)
        throw std::runtime_error("replay24wl::apply_provisional: unsafe payload gain");
    if (!std::isfinite(rec.payload_tx_scale) || rec.payload_tx_scale <= 0.0)
        throw std::runtime_error("replay24wl::apply_provisional: unsafe payload TX scale");
    const std::complex<double> a_inv =
        std::complex<double>(mag / mag2, 0.0) *
        std::complex<double>(std::cos(-rec.payload_phase_deg * iqrftrain::kPi / 180.0),
                             std::sin(-rec.payload_phase_deg * iqrftrain::kPi / 180.0)) /
        rec.payload_tx_scale;

    // ---- wide-linear IQ compensation (byte-identical to iqrfrec::apply) --------------
    if (rec.wide_linear_enabled) {
        const std::complex<double> a = rec.wide_linear_direct;
        const std::complex<double> b = rec.wide_linear_image;
        const double wden = std::norm(a) - std::norm(b);
        if (std::isfinite(wden) && wden > 1e-12) {
            const double norm_scale = std::abs(a) / (mag * rec.payload_tx_scale);
            std::vector<std::complex<double>> out(iqrftrain::kPayloadComplex);
            const double sro = rec.sro_ppm * 1e-6;
            const double f = rec.cfo_hz;
            for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
                const double src =
                    static_cast<double>(rec.timing_offset + iqrftrain::kPayloadStart + k) *
                    (1.0 + sro);
                const std::size_t i0 = static_cast<std::size_t>(std::floor(src));
                const std::size_t i1 = i0 + 1;
                std::complex<double> x;
                if (i1 < rx.size()) {
                    const double frac = src - static_cast<double>(i0);
                    x = rx[i0] * (1.0 - frac) + rx[i1] * frac;
                } else if (i0 < rx.size()) {
                    x = rx[i0];
                } else {
                    x = std::complex<double>(0.0, 0.0);
                }
                const double ph = -2.0 * iqrftrain::kPi * f *
                                  static_cast<double>(iqrftrain::kPayloadStart + k) /
                                  static_cast<double>(iqrftrain::kFs);
                const std::complex<double> derot(std::cos(ph), std::sin(ph));
                const std::complex<double> xc = x * derot;
                out[k] = (std::conj(a) * xc - b * std::conj(xc)) / wden * norm_scale;
            }
            return out;
        }
        // unsafe denominator -> fall through to the unchanged scalar path
    }

    std::vector<std::complex<double>> out(iqrftrain::kPayloadComplex);
    const double sro = rec.sro_ppm * 1e-6;
    const double f = rec.cfo_hz;
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double src = static_cast<double>(rec.timing_offset + iqrftrain::kPayloadStart + k) *
                           (1.0 + sro);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(src));
        const std::size_t i1 = i0 + 1;
        std::complex<double> x;
        if (i1 < rx.size()) {
            const double frac = src - static_cast<double>(i0);
            x = rx[i0] * (1.0 - frac) + rx[i1] * frac;
        } else if (i0 < rx.size()) {
            x = rx[i0];
        } else {
            x = std::complex<double>(0.0, 0.0);
        }
        x *= a_inv;
        const double ph = -2.0 * iqrftrain::kPi * f *
                          static_cast<double>(iqrftrain::kPayloadStart + k) /
                          static_cast<double>(iqrftrain::kFs);
        const std::complex<double> derot(std::cos(ph), std::sin(ph));
        out[k] = x * derot;
    }
    return out;
}

// ---- D2 constants (reuse the production loader, fail-closed) ------------------------
struct D2Constants {
    long long source_index = -1;
    int source_class = -1;
    double original_dc_i = 0.0;
    double original_dc_q = 0.0;
    double d2_rec_scale = 1.0;
    std::string recovered_tensor_path;
    std::string recovered_tensor_file;
    std::string recovered_tensor_sha256;
};

inline D2Constants load_d2_constants(const std::string& clean24_dir,
                                     long long source_index) {
    const std::vector<iqdloop::FrozenIq> all = iqdloop::load_d2_sidecar(clean24_dir);
    D2Constants found;
    bool seen = false;
    for (const auto& q : all) {
        if (q.source_index == source_index) {
            if (seen)
                throw std::runtime_error("replay24wl: duplicate source_index " +
                                         std::to_string(source_index) + " in D2 manifest");
            seen = true;
            found.source_index = q.source_index;
            found.source_class = q.source_class;
            found.original_dc_i = q.original_dc_i;
            found.original_dc_q = q.original_dc_q;
            found.d2_rec_scale = q.d2_rec_scale;
            found.recovered_tensor_path = q.recovered_tensor_path;
            found.recovered_tensor_file = q.recovered_tensor_file;
            found.recovered_tensor_sha256 = q.recovered_tensor_sha256;
        }
    }
    if (!seen)
        throw std::runtime_error("replay24wl: source_index " +
                                 std::to_string(source_index) + " not found in D2 manifest");
    return found;
}

// ---- deterministic reconstruction of aligned/fin from canonical scalars ------------
struct AlignedFin {
    std::vector<std::complex<double>> aligned;
    iqrfrec::PerFileRecovery fin;
};

inline AlignedFin rebuild_aligned_fin(const std::vector<std::complex<double>>& rx,
                                      double coarse_cfo_hz,
                                      double fractional_timing_samples,
                                      const iqrfrec::EstimateConfig& cfg) {
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * coarse_cfo_hz *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }
    AlignedFin out;
    out.aligned = iqdual23fix10::detail::apply_fractional_advance(derot,
                                                                  fractional_timing_samples);
    out.fin = iqrfrec::estimate(out.aligned, cfg);
    return out;
}

// ---- canonical wide-linear recompute (mirrors iqrfrec::estimate() step 6.6) ---------
// estimate()'s own step 6.6 uses iqrftrain::payload_gain_training_complex() (runtime
// std::sqrt/std::lround), which diverges x86 vs aarch64.  This reproduces the BOARD's
// (a, b), validation residuals, image ratio and enabled flag with the frozen canonical
// reference (== board aarch64 semantics).  `aligned` is the coarse-de-rotated +
// fractional-advanced capture; `fin` is the final estimate on it.
struct WideLinearRecompute {
    bool enabled = false;
    std::complex<double> a{1.0, 0.0};   // wide_linear_direct
    std::complex<double> b{0.0, 0.0};   // wide_linear_image
    double scalar_validation_residual = 0.0;
    double validation_residual = 0.0;
    double image_ratio = 0.0;           // |b| / |a|
};

inline WideLinearRecompute canonical_wide_linear_recompute(
        const std::vector<std::complex<double>>& aligned,
        const iqrfrec::PerFileRecovery& fin) {
    const std::vector<std::complex<double>> pt = replay24::canonical_payload_training_complex();
    const std::size_t N = iqrftrain::kPayloadTrainingComplex;   // 1024
    const std::size_t half = N / 2;                             // 512
    const std::size_t bf = fin.timing_offset;
    const std::size_t ptoff = iqrftrain::kPayloadTrainingOffset;
    const double cfo = fin.cfo_hz;
    const double sro_frac = fin.sro_ppm * 1e-6;
    const double Fs = static_cast<double>(iqrftrain::kFs);

    auto stretched = [&](std::size_t k) -> std::complex<double> {
        double x = static_cast<double>(ptoff + k) / (1.0 + sro_frac) -
                   static_cast<double>(ptoff);
        if (x < 0.0) x = 0.0;
        if (x > static_cast<double>(pt.size() - 1)) x = static_cast<double>(pt.size() - 1);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(x));
        const std::size_t i1 = i0 + 1;
        if (i1 < pt.size()) {
            const double fr = x - static_cast<double>(i0);
            return pt[i0] * (1.0 - fr) + pt[i1] * fr;
        }
        return pt[i0];
    };

    std::vector<std::complex<double>> xc(N), rk(N);
    for (std::size_t k = 0; k < N; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * cfo *
                          static_cast<double>(ptoff + k) / Fs;
        const std::complex<double> derot(std::cos(ph), -std::sin(ph));  // exp(-j ph)
        xc[k] = aligned[bf + ptoff + k] * derot;
        rk[k] = stretched(k);
    }

    // Same-window scalar gain (first half only -> fair generalization test).
    std::complex<double> num_c(0.0, 0.0);
    double den_c = 0.0;
    for (std::size_t k = 0; k < half; ++k) {
        num_c += std::conj(rk[k]) * xc[k];
        den_c += iqrfrec::detail::norm2(rk[k]);
    }
    const std::complex<double> c =
        (den_c > 0.0) ? num_c / den_c : std::complex<double>(0.0, 0.0);
    const iqrfrec::detail::WideLinearCoeffs wl =
        iqrfrec::detail::wide_linear_fit(rk, xc, 0, half);
    const std::complex<double> a = wl.a, b = wl.b;

    auto resid = [&](std::size_t lo, std::size_t hi, auto model) {
        double num = 0.0, den = 0.0;
        for (std::size_t k = lo; k < hi; ++k) {
            const std::complex<double> m = model(k);
            num += iqrfrec::detail::norm2(xc[k] - m);
            den += iqrfrec::detail::norm2(m);
        }
        return den > 0.0 ? std::sqrt(num / den) : 0.0;
    };
    const double scalar_val = resid(half, N, [&](std::size_t k) { return c * rk[k]; });
    const double wl_val = resid(half, N,
        [&](std::size_t k) { return a * rk[k] + b * std::conj(rk[k]); });

    WideLinearRecompute out;
    out.scalar_validation_residual = scalar_val;
    out.validation_residual = wl_val;
    const double abs_a = std::abs(a);
    const double abs_b = std::abs(b);
    out.image_ratio = (abs_a > 1e-12) ? abs_b / abs_a : 0.0;

    const bool improves = std::isfinite(scalar_val) && std::isfinite(wl_val) &&
                          wl_val < scalar_val * 0.99;
    const bool physical = std::isfinite(abs_a) && std::isfinite(abs_b) &&
                          abs_b <= abs_a && abs_b > abs_a * 1e-4;
    if (improves && physical) {
        out.enabled = true;
        out.a = a;
        out.b = b;
    }
    return out;
}

// ---- verbatim classification chain (iq_pc_tx_board_rx_24class_bf16_fix10.hpp) -------
struct ClassificationChainResult {
    std::vector<std::int16_t> payload_iq;
    std::vector<float> recovered_stream;
    iqdloop::ClassificationWindow cw;
    std::vector<float> model_input;   // == cw.aligned_tensor
};

inline ClassificationChainResult run_classification_chain(
        const std::vector<std::complex<double>>& payload, const D2Constants& d2) {
    std::vector<std::int16_t> payload_iq(payload.size() * 2);
    for (std::size_t k = 0; k < payload.size(); ++k) {
        const double I = std::lround(payload[k].real());
        const double Q = std::lround(payload[k].imag());
        payload_iq[k * 2 + 0] = static_cast<std::int16_t>(
            std::max(-32768.0, std::min(32767.0, I)));
        payload_iq[k * 2 + 1] = static_cast<std::int16_t>(
            std::max(-32768.0, std::min(32767.0, Q)));
    }

    chain::PreprocessChain chain(iqdloop::kFrozenFsIn, 0.0, 1.0f);
    chain.push_int16(payload_iq.data(), payload.size());
    std::vector<float> recovered_stream;
    {
        std::vector<float> t(chain::kTensorFloats);
        while (chain.ready() > 0) {
            if (!chain.pull_tensor(t.data())) break;
            recovered_stream.insert(recovered_stream.end(), t.begin(), t.end());
        }
    }
    iqdloop::apply_d2_restore_to_stream(recovered_stream, chain::kFrameComplex,
                                        d2.original_dc_i, d2.original_dc_q,
                                        d2.d2_rec_scale);
    const std::vector<float> ref =
        iqdloop::load_recovered_tensor(d2.recovered_tensor_path, d2.recovered_tensor_sha256);
    const iqdloop::ClassificationWindow cw =
        iqdloop::select_classification_window(recovered_stream, ref);

    ClassificationChainResult out;
    out.payload_iq = std::move(payload_iq);
    out.recovered_stream = std::move(recovered_stream);
    out.cw = cw;
    out.model_input = cw.aligned_tensor;
    return out;
}

// ---- build the provisional recovery record (valid stays false; failure preserved) ----
inline iqrfrec::PerFileRecovery build_provisional_rec(
        const iqrfrec::PerFileRecovery& fin, double canonical_payload_gain_mag,
        double canonical_payload_phase_deg, double tx_scale,
        iqrfrec::Failure actual_failure, const WideLinearRecompute& wl) {
    iqrfrec::PerFileRecovery rec;
    rec.computed = true;
    rec.valid = false;                                    // NOT disguised as valid
    rec.failure = actual_failure;                         // from the dump, not hardcoded
    rec.timing_offset = fin.timing_offset;
    rec.cfo_hz = fin.cfo_hz;
    rec.sro_ppm = fin.sro_ppm;
    rec.payload_rms_gain_mag = fin.payload_rms_gain_mag;  // label-free, cross-arch stable
    rec.payload_gain_mag = canonical_payload_gain_mag;    // canonical (board) reference
    rec.payload_phase_deg = canonical_payload_phase_deg;  // canonical (board) reference
    rec.payload_tx_scale = tx_scale;
    rec.payload_training_corr = 0.0;
    rec.payload_training_residual = 0.0;
    // wide-linear (canonical recompute == board aarch64 semantics)
    rec.wide_linear_enabled = wl.enabled;
    rec.wide_linear_direct = wl.a;
    rec.wide_linear_image = wl.b;
    rec.wide_linear_validation_residual = wl.validation_residual;
    rec.wide_linear_scalar_validation_residual = wl.scalar_validation_residual;
    rec.wide_linear_image_ratio = wl.image_ratio;
    return rec;
}

// ---- the full provisional force-classification result ------------------------------
struct ForceClassifyResult {
    std::string capture_id;
    long long source_index = -1;
    int source_class = -1;
    double target_rms = 0.0;
    double tx_scale = 1.0;
    std::string raw_rx_sha256;

    // canonical recovery scalars (== replay_canonical_from_dir) + reconstruction check
    std::size_t timing_offset = 0;
    double coarse_cfo_hz = 0.0;
    double fine_cfo_hz = 0.0;
    double sro_ppm = 0.0;
    double fractional_timing_samples = 0.0;
    double payload_training_corr = 0.0;
    double payload_training_residual = 0.0;
    double payload_gain_mag = 0.0;
    double payload_phase_deg = 0.0;
    double payload_rms_gain_mag = 0.0;
    bool timing_ok = false, coarse_ok = false, fine_ok = false, corr_ok = false,
         resid_ok = false;
    bool reconstruction_consistent = false;

    // actual failure (from the dump) + canonical wide-linear recompute
    iqrfrec::Failure actual_failure = iqrfrec::Failure::NONE;
    WideLinearRecompute wl;

    std::string recovered_tensor_file;
    std::string recovered_tensor_sha256;

    // provisional payload + classification chain
    std::vector<std::complex<double>> provisional_payload;
    ClassificationChainResult chain;
};

inline ForceClassifyResult force_classify_from_dir(const std::string& dump_dir,
                                                   const std::string& clean24_dir,
                                                   const std::string& capture_id,
                                                   long long source_index) {
    const replay24::CanonicalReplayResult cr =
        replay24::replay_canonical_from_dir(dump_dir);

    const std::string json_path = dump_dir + "/recovery_diagnostics.json";
    const std::string json = replay24::read_file(json_path);
    const double target_rms = replay24::json_num(json, "target_rms");
    const double tx_scale = replay24::json_num(json, "tx_scale");
    const long long json_source_index = replay24::json_int(json, "source_index");
    const long long failure_enum = replay24::json_int(json, "failure_enum");  // ACTUAL
    if (json_source_index != source_index)
        throw std::runtime_error("replay24wl: source_index mismatch (json " +
                                 std::to_string(json_source_index) + " vs requested " +
                                 std::to_string(source_index) + ")");

    const std::vector<std::int16_t> iq =
        replay24::read_ci16_le(dump_dir + "/raw_rx_ci16le.bin");
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);

    bool sha_ok = false;
    const std::string raw_sha = sdr::sha256_hex_file(dump_dir + "/raw_rx_ci16le.bin", &sha_ok);
    if (!sha_ok)
        throw std::runtime_error("replay24wl: cannot hash raw_rx_ci16le.bin");
    if (raw_sha != replay24::json_str(json, "raw_rx_sha256"))
        throw std::runtime_error("replay24wl: raw_rx_ci16le.bin SHA mismatch vs json");

    const iqrfrec::EstimateConfig cfg = replay24::config(target_rms);
    const AlignedFin af =
        rebuild_aligned_fin(rx, cr.coarse_cfo_hz, cr.fractional_timing_samples, cfg);

    const bool recon_consistent =
        (af.fin.timing_offset == cr.timing_offset) &&
        replay24::near(af.fin.cfo_hz, cr.fine_cfo_hz, 0.0) &&
        replay24::near(af.fin.sro_ppm, cr.sro_ppm, 0.0);

    // Canonical wide-linear recompute (== board aarch64 semantics), NOT the runtime
    // estimate() step 6.6.
    const WideLinearRecompute wl = canonical_wide_linear_recompute(af.aligned, af.fin);

    const iqrfrec::Failure actual_failure = static_cast<iqrfrec::Failure>(failure_enum);
    const iqrfrec::PerFileRecovery rec = build_provisional_rec(
        af.fin, cr.payload_gain_mag, cr.payload_phase_deg, tx_scale, actual_failure, wl);
    const std::vector<std::complex<double>> payload = apply_provisional(af.aligned, rec);

    const D2Constants d2 = load_d2_constants(clean24_dir, source_index);
    ClassificationChainResult chain = run_classification_chain(payload, d2);

    ForceClassifyResult out;
    out.capture_id = capture_id;
    out.source_index = source_index;
    out.source_class = d2.source_class;
    out.target_rms = target_rms;
    out.tx_scale = tx_scale;
    out.raw_rx_sha256 = raw_sha;
    out.timing_offset = cr.timing_offset;
    out.coarse_cfo_hz = cr.coarse_cfo_hz;
    out.fine_cfo_hz = cr.fine_cfo_hz;
    out.sro_ppm = cr.sro_ppm;
    out.fractional_timing_samples = cr.fractional_timing_samples;
    out.payload_training_corr = cr.payload_training_corr;
    out.payload_training_residual = cr.payload_training_residual;
    out.payload_gain_mag = cr.payload_gain_mag;
    out.payload_phase_deg = cr.payload_phase_deg;
    out.payload_rms_gain_mag = af.fin.payload_rms_gain_mag;
    out.timing_ok = cr.timing_ok;
    out.coarse_ok = cr.coarse_ok;
    out.fine_ok = cr.fine_ok;
    out.corr_ok = cr.corr_ok;
    out.resid_ok = cr.resid_ok;
    out.reconstruction_consistent = recon_consistent;
    out.actual_failure = actual_failure;
    out.wl = wl;
    out.recovered_tensor_file = d2.recovered_tensor_file;
    out.recovered_tensor_sha256 = d2.recovered_tensor_sha256;
    out.provisional_payload = std::move(payload);
    out.chain = std::move(chain);
    return out;
}

// ---- export helpers (6 files per capture/source) -----------------------------------
inline void write_f32le(const std::string& path, const float* data, std::size_t n) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("replay24wl: cannot write " + path);
    f.write(reinterpret_cast<const char*>(data),
            static_cast<std::streamsize>(n * sizeof(float)));
    if (!f) throw std::runtime_error("replay24wl: short write " + path);
}

inline std::string d17(double v) {
    std::ostringstream os;
    os << std::setprecision(17) << v;
    return os.str();
}

inline std::string build_forced_recovery_json(const ForceClassifyResult& r,
                                              const std::string& payload_sha,
                                              const std::string& cw_sha,
                                              const std::string& mi_sha) {
    const auto& cw = r.chain.cw;
    bool model_input_finite = true;
    for (float x : r.chain.model_input)
        if (!std::isfinite(x)) { model_input_finite = false; break; }

    std::ostringstream o;
    o << std::setprecision(17);
    o << "{\n";
    o << "  \"capture_id\": \"" << r.capture_id << "\",\n";
    o << "  \"source_index\": " << r.source_index << ",\n";
    o << "  \"source_class\": " << r.source_class << ",\n";
    o << "  \"backend\": \"HOST_BF16\",\n";
    o << "  \"diagnostic_gate_bypass\": 1,\n";
    o << "  \"production_gate_modified\": 0,\n";
    o << "  \"merge_marker\": \"HYBRID_BOARD_GATED_PLUS_HOST_FORCED\",\n";
    o << "  \"gate_bypassed_for_diagnostic\": 1,\n";
    o << "  \"original_valid\": 0,\n";
    o << "  \"original_failure\": \"" << iqrfrec::failure_token(r.actual_failure) << "\",\n";
    o << "  \"original_failure_enum\": " << static_cast<int>(r.actual_failure) << ",\n";
    o << "  \"target_rms\": " << d17(r.target_rms) << ",\n";
    o << "  \"tx_scale\": " << d17(r.tx_scale) << ",\n";
    o << "  \"raw_rx_sha256\": \"" << r.raw_rx_sha256 << "\",\n";
    o << "  \"timing_offset\": " << r.timing_offset << ",\n";
    o << "  \"coarse_cfo_hz\": " << d17(r.coarse_cfo_hz) << ",\n";
    o << "  \"fine_cfo_hz\": " << d17(r.fine_cfo_hz) << ",\n";
    o << "  \"sro_ppm\": " << d17(r.sro_ppm) << ",\n";
    o << "  \"fractional_timing_samples\": " << d17(r.fractional_timing_samples) << ",\n";
    o << "  \"payload_training_corr\": " << d17(r.payload_training_corr) << ",\n";
    o << "  \"payload_training_residual\": " << d17(r.payload_training_residual) << ",\n";
    o << "  \"payload_gain_mag\": " << d17(r.payload_gain_mag) << ",\n";
    o << "  \"payload_phase_deg\": " << d17(r.payload_phase_deg) << ",\n";
    o << "  \"payload_rms_gain_mag\": " << d17(r.payload_rms_gain_mag) << ",\n";
    o << "  \"wide_linear\": {\n";
    o << "    \"enabled\": " << (r.wl.enabled ? 1 : 0) << ",\n";
    o << "    \"scalar_validation_residual\": " << d17(r.wl.scalar_validation_residual) << ",\n";
    o << "    \"validation_residual\": " << d17(r.wl.validation_residual) << ",\n";
    o << "    \"image_ratio\": " << d17(r.wl.image_ratio) << "\n";
    o << "  },\n";
    o << "  \"canonical_crosscheck\": {\"timing_ok\": " << (r.timing_ok ? 1 : 0)
      << ", \"coarse_ok\": " << (r.coarse_ok ? 1 : 0)
      << ", \"fine_ok\": " << (r.fine_ok ? 1 : 0)
      << ", \"corr_ok\": " << (r.corr_ok ? 1 : 0)
      << ", \"resid_ok\": " << (r.resid_ok ? 1 : 0) << "},\n";
    o << "  \"reconstruction_consistent\": " << (r.reconstruction_consistent ? 1 : 0) << ",\n";
    o << "  \"classification_chain\": {\n";
    o << "    \"fs_in_hz\": " << iqdloop::kFrozenFsIn << ",\n";
    o << "    \"nco_offset_hz\": 0.0,\n";
    o << "    \"preprocess_gain\": 1.0,\n";
    o << "    \"recovered_tensor_file\": \"" << r.recovered_tensor_file << "\",\n";
    o << "    \"recovered_tensor_sha256\": \"" << r.recovered_tensor_sha256 << "\",\n";
    o << "    \"classification_window_valid\": " << (cw.valid ? 1 : 0) << ",\n";
    o << "    \"delay_offset\": " << cw.delay_offset << ",\n";
    o << "    \"tensor_corr\": " << d17(cw.tensor_corr) << ",\n";
    o << "    \"tensor_nmse\": " << d17(cw.tensor_nmse) << ",\n";
    o << "    \"recovered_frames\": " << cw.recovered_frames << ",\n";
    o << "    \"model_input_equals_classification_window\": 1\n";
    o << "  },\n";
    o << "  \"outputs\": {\n";
    o << "    \"provisional_recovered_payload_sha256\": \"" << payload_sha << "\",\n";
    o << "    \"classification_window_sha256\": \"" << cw_sha << "\",\n";
    o << "    \"model_input_sha256\": \"" << mi_sha << "\"\n";
    o << "  },\n";
    o << "  \"model_input_finite\": " << (model_input_finite ? 1 : 0) << "\n";
    o << "}\n";
    return o.str();
}

inline void write_export(const std::string& export_dir, const ForceClassifyResult& r) {
    const std::string dir = export_dir + "/" + r.capture_id + "/" +
                            std::to_string(r.source_index);

    std::vector<float> pf(r.provisional_payload.size() * 2);
    for (std::size_t k = 0; k < r.provisional_payload.size(); ++k) {
        pf[k * 2 + 0] = static_cast<float>(r.provisional_payload[k].real());
        pf[k * 2 + 1] = static_cast<float>(r.provisional_payload[k].imag());
    }
    write_f32le(dir + "/provisional_recovered_payload_f32le.bin", pf.data(), pf.size());

    write_f32le(dir + "/classification_window_f32le.bin",
                r.chain.cw.aligned_tensor.data(), r.chain.cw.aligned_tensor.size());
    write_f32le(dir + "/model_input_f32le.bin",
                r.chain.model_input.data(), r.chain.model_input.size());

    bool ok = false;
    const std::string payload_sha =
        sdr::sha256_hex_file(dir + "/provisional_recovered_payload_f32le.bin", &ok);
    const std::string cw_sha =
        sdr::sha256_hex_file(dir + "/classification_window_f32le.bin", &ok);
    const std::string mi_sha = sdr::sha256_hex_file(dir + "/model_input_f32le.bin", &ok);
    if (!ok) throw std::runtime_error("replay24wl: cannot hash export outputs");

    const std::string json = build_forced_recovery_json(r, payload_sha, cw_sha, mi_sha);

    std::ofstream jf(dir + "/forced_recovery.json", std::ios::binary);
    if (!jf) throw std::runtime_error("replay24wl: cannot write forced_recovery.json");
    jf << json;
    jf.flush();

    std::ofstream sf(dir + "/SHA256SUMS.txt", std::ios::binary);
    if (!sf) throw std::runtime_error("replay24wl: cannot write SHA256SUMS.txt");
    sf << payload_sha << "  provisional_recovered_payload_f32le.bin\n";
    sf << cw_sha << "  classification_window_f32le.bin\n";
    sf << mi_sha << "  model_input_f32le.bin\n";
    sf << sdr::Sha256::hex(json) << "  forced_recovery.json\n";
    sf.flush();
}

// ---- Phase C PASS-fixture equivalence (production apply == apply_provisional) -------
struct EquivalenceResult {
    bool apply_identical = false;
    bool payload_iq_identical = false;
    bool recovered_stream_identical = false;
    bool classification_window_identical = false;
    bool model_input_identical = false;
    std::string payload_sha, payload_iq_sha, stream_sha, window_sha, model_input_sha;
};

inline EquivalenceResult run_pass_fixture_equivalence(const std::string& clean24_dir,
                                                      long long source_index) {
    std::vector<std::int16_t> payload(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 37) / 37.0;
        payload[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1200.0 * std::cos(ph)));
        payload[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1200.0 * std::sin(ph)));
    }
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(payload);
    const iqdual23fix10::CoarseCfoRecovery ccr = iqdual23fix10::recover_payload_with_coarse_cfo(
        iqrftrain::deinterleave(burst), replay24::config(2048.0), 1.0);
    if (!ccr.rec.valid || ccr.rec.payload_training_residual > 1e-3)
        throw std::runtime_error("replay24wl: PASS fixture recovery not valid");

    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(burst);
    const AlignedFin af = rebuild_aligned_fin(rx, ccr.coarse_cfo_hz,
                                              ccr.fractional_timing_samples,
                                              replay24::config(2048.0));

    const std::vector<std::complex<double>> prod_payload = iqrfrec::apply(af.aligned, ccr.rec);
    const std::vector<std::complex<double>> diag_payload = apply_provisional(af.aligned, ccr.rec);

    const D2Constants d2 = load_d2_constants(clean24_dir, source_index);
    const ClassificationChainResult prod_chain = run_classification_chain(prod_payload, d2);
    const ClassificationChainResult diag_chain = run_classification_chain(diag_payload, d2);

    EquivalenceResult e;
    e.apply_identical = (prod_payload.size() == diag_payload.size()) &&
                        std::equal(prod_payload.begin(), prod_payload.end(),
                                   diag_payload.begin(),
                                   [](const std::complex<double>& a,
                                      const std::complex<double>& b) {
                                       return a.real() == b.real() && a.imag() == b.imag();
                                   });
    e.payload_iq_identical = (prod_chain.payload_iq == diag_chain.payload_iq);
    e.recovered_stream_identical =
        (prod_chain.recovered_stream == diag_chain.recovered_stream);
    e.classification_window_identical =
        (prod_chain.cw.aligned_tensor == diag_chain.cw.aligned_tensor);
    e.model_input_identical = (prod_chain.model_input == diag_chain.model_input);

    std::vector<float> pf(prod_payload.size() * 2);
    for (std::size_t k = 0; k < prod_payload.size(); ++k) {
        pf[k * 2 + 0] = static_cast<float>(prod_payload[k].real());
        pf[k * 2 + 1] = static_cast<float>(prod_payload[k].imag());
    }
    e.payload_sha = sdr::Sha256::hex(pf.data(), pf.size() * sizeof(float));
    e.payload_iq_sha =
        sdr::Sha256::hex(prod_chain.payload_iq.data(),
                         prod_chain.payload_iq.size() * sizeof(std::int16_t));
    e.stream_sha =
        sdr::Sha256::hex(prod_chain.recovered_stream.data(),
                         prod_chain.recovered_stream.size() * sizeof(float));
    e.window_sha =
        sdr::Sha256::hex(prod_chain.cw.aligned_tensor.data(),
                         prod_chain.cw.aligned_tensor.size() * sizeof(float));
    e.model_input_sha =
        sdr::Sha256::hex(prod_chain.model_input.data(),
                         prod_chain.model_input.size() * sizeof(float));
    return e;
}

// ---- wide-linear equivalence self-test: prove apply_provisional's WIDE-LINEAR branch
// ---- is byte-identical to production apply() on an image-impaired fixture. ----------
inline bool run_wide_linear_fixture_equivalence() {
    // Deterministic clean burst, then apply a mixer-image model y = A*x + B*conj(x).
    std::vector<std::int16_t> payload(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 41) / 41.0;
        payload[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1150.0 * std::cos(ph)));
        payload[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1150.0 * std::sin(ph)));
    }
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(payload);
    const std::vector<std::complex<double>> rx_clean = iqrftrain::deinterleave(burst);
    const std::complex<double> A(1.0, 0.0), B(0.06, -0.04);
    std::vector<std::complex<double>> distorted(rx_clean.size());
    for (std::size_t k = 0; k < rx_clean.size(); ++k)
        distorted[k] = A * rx_clean[k] + B * std::conj(rx_clean[k]);

    const iqrfrec::EstimateConfig cfg = replay24::config(2048.0);
    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(distorted, cfg, 1.0);
    if (!ccr.rec.valid)
        return false;   // precondition: the fixture must still pass the 0.10 gate
    if (!ccr.rec.wide_linear_enabled)
        return false;   // precondition: the fixture must enable wide-linear

    const AlignedFin af = rebuild_aligned_fin(distorted, ccr.coarse_cfo_hz,
                                              ccr.fractional_timing_samples, cfg);
    const std::vector<std::complex<double>> prod = iqrfrec::apply(af.aligned, ccr.rec);
    const std::vector<std::complex<double>> diag = apply_provisional(af.aligned, ccr.rec);
    if (prod.size() != diag.size())
        return false;
    for (std::size_t k = 0; k < prod.size(); ++k)
        if (prod[k].real() != diag[k].real() || prod[k].imag() != diag[k].imag())
            return false;
    return true;
}

}  // namespace replay24wl
