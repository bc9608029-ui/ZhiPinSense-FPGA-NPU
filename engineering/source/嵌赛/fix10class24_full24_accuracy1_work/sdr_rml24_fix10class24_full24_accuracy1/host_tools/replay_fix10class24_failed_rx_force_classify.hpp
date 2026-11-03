#pragma once

// replay_fix10class24_failed_rx_force_classify.hpp -- fix10class24-rxresidual-audit1
// Phase B/C diagnostic core: force a provisional (gate-bypassed) payload recovery from a
// failed-RX dump, then run the VERBATIM production classification chain
//   int16 -> PreprocessChain -> D2 restore -> reference window -> [2,1024] model input
// to produce the exact tensor the frozen BF16 24-class model would receive -- WITHOUT
// modifying the production 0.100 gate, any recovery/sync red-line header, the runner,
// the model, the label order, the baseline, or any training/quantization asset.
//
// Invariants:
//   * replay24force::apply_provisional() is a byte-for-byte copy of iqrfrec::apply()
//     (iq_rf_sync_recovery.hpp 504-551) with ONLY the `!rec.valid` throw removed; the
//     unsafe-gain and unsafe-tx-scale fail-closed guards are KEPT.  It lives in this
//     diagnostic namespace -- never in iqrfrec -- so the production runner cannot call it.
//   * The provisional PerFileRecovery keeps rec.valid=false and
//     failure=PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH (it is NOT disguised as valid).  The
//     payload-domain phase/gain come from the frozen canonical (aarch64) reference (==
//     board semantics); timing/cfo/sro/payload_rms_gain_mag are reused from the final
//     production estimate fin=estimate(aligned, cfg); payload_tx_scale comes from the
//     dump's recovery_diagnostics.json.
//   * The canonical recovery scalars come from replay24::replay_canonical_from_dir() (the
//     single source of truth); `aligned` and `fin` are recomputed deterministically from
//     its coarse_cfo_hz + fractional_timing_samples (no canonical math duplicated).
//   * Phase C HARD GATE (host self-test) proves this diagnostic path is byte-identical to
//     the production path on a PASS fixture (valid=true): apply == apply_provisional, then
//     payload_iq / recovered_stream / classification_window / model_input are byte-equal.
//
// iCraft-free / libiio-free / NPU-free.  This header is compiled only by host tools and
// host tests, never linked into the production runner.

#include "replay_fix10class24_failed_rx.hpp"   // replay24:: helpers + canonical replay
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

namespace replay24force {

// ---- provisional apply (verbatim iqrfrec::apply minus the valid throw) ---------------
inline std::vector<std::complex<double>> apply_provisional(
        const std::vector<std::complex<double>>& rx, const iqrfrec::PerFileRecovery& rec) {
    const double mag = (rec.payload_rms_gain_mag > 1e-12 &&
                        std::isfinite(rec.payload_rms_gain_mag))
                           ? rec.payload_rms_gain_mag : rec.payload_gain_mag;
    const double mag2 = mag * mag;
    if (!std::isfinite(mag) || mag <= 1e-12)
        throw std::runtime_error("replay24force::apply_provisional: unsafe payload gain");
    if (!std::isfinite(rec.payload_tx_scale) || rec.payload_tx_scale <= 0.0)
        throw std::runtime_error("replay24force::apply_provisional: unsafe payload TX scale");
    const std::complex<double> a_inv =
        std::complex<double>(mag / mag2, 0.0) *
        std::complex<double>(std::cos(-rec.payload_phase_deg * iqrftrain::kPi / 180.0),
                             std::sin(-rec.payload_phase_deg * iqrftrain::kPi / 180.0)) /
        rec.payload_tx_scale;
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

// ---- wide-linear provisional (fix10class24-full24-accuracy1) ------------------------
// The production iqrfrec::apply() wide-linear branch (iq_rf_sync_recovery.hpp 654-694),
// verbatim minus the `!rec.valid` throw, and with the wide-linear branch FORCED (the
// diagnostic always asks "what would the model see under the wide-linear compensation",
// regardless of whether estimate() enabled it).  A non-finite / non-positive |a|^2-|b|^2
// denominator throws fail-closed; the caller records `wide_linear_applicable=false`.
inline std::vector<std::complex<double>> apply_provisional_wide_linear(
        const std::vector<std::complex<double>>& rx, const iqrfrec::PerFileRecovery& rec) {
    const double mag = (rec.payload_rms_gain_mag > 1e-12 &&
                        std::isfinite(rec.payload_rms_gain_mag))
                           ? rec.payload_rms_gain_mag : rec.payload_gain_mag;
    if (!std::isfinite(mag) || mag <= 1e-12)
        throw std::runtime_error(
            "replay24force::apply_provisional_wide_linear: unsafe payload gain");
    if (!std::isfinite(rec.payload_tx_scale) || rec.payload_tx_scale <= 0.0)
        throw std::runtime_error(
            "replay24force::apply_provisional_wide_linear: unsafe payload TX scale");
    const std::complex<double> a = rec.wide_linear_direct;
    const std::complex<double> b = rec.wide_linear_image;
    const double wden = std::norm(a) - std::norm(b);
    if (!(std::isfinite(wden) && wden > 1e-12))
        throw std::runtime_error(
            "replay24force::apply_provisional_wide_linear: unsafe wide-linear denominator");
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

// Canonical (aarch64) wide-linear (a,b) recompute.  estimate() step 6.6 fits (a,b) on the
// host-runtime payload_gain_training_complex(), which diverges cross-arch (D1); the BOARD's
// (a,b) uses the frozen canonical reference, so the diagnostic recomputes (a,b) with
// replay24::canonical_payload_training_complex() and the SAME de-ramp / SRO-stretch /
// first-half-512 fit as estimate() step 6.6.  Payload samples and labels never participate.
inline iqrfrec::detail::WideLinearCoeffs canonical_wide_linear_coeffs(
        const std::vector<std::complex<double>>& aligned,
        const iqrfrec::PerFileRecovery& fin) {
    const std::vector<std::complex<double>> pt =
        replay24::canonical_payload_training_complex();
    const std::size_t ptoff = iqrftrain::kPayloadTrainingOffset;
    const double sro_frac = fin.sro_ppm * 1e-6;
    const std::size_t bf = fin.timing_offset;
    auto stretched_pt = [&pt, ptoff, sro_frac](std::size_t k) -> std::complex<double> {
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
    std::vector<std::complex<double>> xc(iqrftrain::kPayloadTrainingComplex);
    std::vector<std::complex<double>> rk(iqrftrain::kPayloadTrainingComplex);
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * fin.cfo_hz *
                          static_cast<double>(ptoff + k) /
                          static_cast<double>(iqrftrain::kFs);
        const std::complex<double> derot(std::cos(ph), -std::sin(ph));  // exp(-j ph)
        xc[k] = aligned[bf + ptoff + k] * derot;
        rk[k] = stretched_pt(k);
    }
    const std::size_t half = iqrftrain::kPayloadTrainingComplex / 2;   // 512
    return iqrfrec::detail::wide_linear_fit(rk, xc, 0, half);
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
                throw std::runtime_error("replay24force: duplicate source_index " +
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
        throw std::runtime_error("replay24force: source_index " +
                                 std::to_string(source_index) + " not found in D2 manifest");
    return found;
}

// ---- deterministic reconstruction of aligned/fin from canonical scalars ------------
struct AlignedFin {
    std::vector<std::complex<double>> aligned;
    iqrfrec::PerFileRecovery fin;
};

// Rebuild the coarse-de-rotated, fractional-advanced capture + final estimate from the
// canonical replay scalars (identical math to replay_canonical_from_dir; no canonical
// math duplicated here beyond the de-rotate/advance/estimate calls the board also makes).
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

// ---- verbatim classification chain (iq_pc_tx_board_rx_24class_bf16_fix10.hpp:970-1002)
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

    // nco_offset = production default 0.0 (runner --nco-offset default; Phase A verifies
    // the board command carries no non-zero override).
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
    std::string recovered_tensor_file;
    std::string recovered_tensor_sha256;

    // provisional payload + classification chain (scalar provisional)
    std::vector<std::complex<double>> provisional_payload;
    ClassificationChainResult chain;

    // wide-linear provisional (fix10class24-full24-accuracy1, diagnostic-only)
    bool wide_linear_applicable = false;
    std::string wide_linear_reason;
    std::complex<double> wide_linear_direct{0.0, 0.0};
    std::complex<double> wide_linear_image{0.0, 0.0};
    double wide_linear_image_ratio = 0.0;
    std::vector<std::complex<double>> provisional_payload_wide_linear;
    ClassificationChainResult chain_wide_linear;
};

// Build the provisional recovery record (valid stays false; failure preserved).
inline iqrfrec::PerFileRecovery build_provisional_rec(
        const iqrfrec::PerFileRecovery& fin, double canonical_payload_gain_mag,
        double canonical_payload_phase_deg, double tx_scale) {
    iqrfrec::PerFileRecovery rec;
    rec.computed = true;
    rec.valid = false;                                    // NOT disguised as valid
    rec.failure = iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH;
    rec.timing_offset = fin.timing_offset;
    rec.cfo_hz = fin.cfo_hz;
    rec.sro_ppm = fin.sro_ppm;
    rec.payload_rms_gain_mag = fin.payload_rms_gain_mag;  // label-free, cross-arch stable
    rec.payload_gain_mag = canonical_payload_gain_mag;    // canonical (board) reference
    rec.payload_phase_deg = canonical_payload_phase_deg;  // canonical (board) reference
    rec.payload_tx_scale = tx_scale;
    rec.payload_training_corr = 0.0;                      // recomputed below by caller
    rec.payload_training_residual = 0.0;
    return rec;
}

// Wide-linear provisional recovery record: identical to build_provisional_rec but with
// the wide-linear compensation FORCED on, using the canonical (aarch64) (a, b).  The
// `valid` flag stays false and the failure stays preserved (this is a diagnostic, not a
// disguised valid recovery).
inline iqrfrec::PerFileRecovery build_provisional_wide_linear_rec(
        const iqrfrec::PerFileRecovery& fin, double canonical_payload_gain_mag,
        double canonical_payload_phase_deg, double tx_scale,
        std::complex<double> a, std::complex<double> b) {
    iqrfrec::PerFileRecovery rec = build_provisional_rec(
        fin, canonical_payload_gain_mag, canonical_payload_phase_deg, tx_scale);
    rec.wide_linear_enabled = true;
    rec.wide_linear_direct = a;
    rec.wide_linear_image = b;
    return rec;
}

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
    if (json_source_index != source_index)
        throw std::runtime_error("replay24force: source_index mismatch (json " +
                                 std::to_string(json_source_index) + " vs requested " +
                                 std::to_string(source_index) + ")");

    const std::vector<std::int16_t> iq =
        replay24::read_ci16_le(dump_dir + "/raw_rx_ci16le.bin");
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);

    bool sha_ok = false;
    const std::string raw_sha = sdr::sha256_hex_file(dump_dir + "/raw_rx_ci16le.bin", &sha_ok);
    if (!sha_ok)
        throw std::runtime_error("replay24force: cannot hash raw_rx_ci16le.bin");
    if (raw_sha != replay24::json_str(json, "raw_rx_sha256"))
        throw std::runtime_error("replay24force: raw_rx_ci16le.bin SHA mismatch vs json");

    const iqrfrec::EstimateConfig cfg = replay24::config(target_rms);
    const AlignedFin af =
        rebuild_aligned_fin(rx, cr.coarse_cfo_hz, cr.fractional_timing_samples, cfg);

    // Reconstruction must reproduce the canonical replay's final estimate bit-for-bit.
    const bool recon_consistent =
        (af.fin.timing_offset == cr.timing_offset) &&
        replay24::near(af.fin.cfo_hz, cr.fine_cfo_hz, 0.0) &&
        replay24::near(af.fin.sro_ppm, cr.sro_ppm, 0.0);

    const iqrfrec::PerFileRecovery rec = build_provisional_rec(
        af.fin, cr.payload_gain_mag, cr.payload_phase_deg, tx_scale);
    const std::vector<std::complex<double>> payload = apply_provisional(af.aligned, rec);

    const D2Constants d2 = load_d2_constants(clean24_dir, source_index);
    ClassificationChainResult chain = run_classification_chain(payload, d2);

    // Wide-linear provisional (canonical aarch64 (a,b), diagnostic-only).  Recomputed
    // regardless of whether production estimate() enabled the compensation: on the board
    // the (a,b) would use the canonical reference, so this is the board-faithful wide-linear
    // provisional -- never chosen with the label, always reported alongside the scalar.
    const iqrfrec::detail::WideLinearCoeffs wl =
        canonical_wide_linear_coeffs(af.aligned, af.fin);
    const double wl_abs_a = std::abs(wl.a);
    const double wl_abs_b = std::abs(wl.b);
    const double wl_image_ratio = (wl_abs_a > 1e-12) ? wl_abs_b / wl_abs_a : 0.0;
    const double wl_wden = std::norm(wl.a) - std::norm(wl.b);
    bool wl_applicable = false;
    std::string wl_reason = "not_applicable";
    std::vector<std::complex<double>> payload_wl;
    ClassificationChainResult chain_wl;
    if (std::isfinite(wl.a.real()) && std::isfinite(wl.a.imag()) &&
        std::isfinite(wl.b.real()) && std::isfinite(wl.b.imag()) &&
        wl_abs_a > 1e-12 && std::isfinite(wl_wden) && wl_wden > 1e-12) {
        const iqrfrec::PerFileRecovery rec_wl = build_provisional_wide_linear_rec(
            af.fin, cr.payload_gain_mag, cr.payload_phase_deg, tx_scale, wl.a, wl.b);
        payload_wl = apply_provisional_wide_linear(af.aligned, rec_wl);
        chain_wl = run_classification_chain(payload_wl, d2);
        wl_applicable = true;
        wl_reason = "OK";
    } else if (!(std::isfinite(wl.a.real()) && std::isfinite(wl.a.imag()) &&
                 std::isfinite(wl.b.real()) && std::isfinite(wl.b.imag()))) {
        wl_reason = "nonfinite_coefficients";
    } else if (wl_abs_a <= 1e-12) {
        wl_reason = "zero_direct_coefficient";
    } else {
        wl_reason = "singular_denominator";
    }

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
    out.recovered_tensor_file = d2.recovered_tensor_file;
    out.recovered_tensor_sha256 = d2.recovered_tensor_sha256;
    out.provisional_payload = std::move(payload);
    out.chain = std::move(chain);
    out.wide_linear_applicable = wl_applicable;
    out.wide_linear_reason = wl_reason;
    out.wide_linear_direct = wl.a;
    out.wide_linear_image = wl.b;
    out.wide_linear_image_ratio = wl_image_ratio;
    out.provisional_payload_wide_linear = std::move(payload_wl);
    out.chain_wide_linear = std::move(chain_wl);
    return out;
}

// ---- export helpers (5 files per capture/source) -----------------------------------
inline void write_f32le(const std::string& path, const float* data, std::size_t n) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("replay24force: cannot write " + path);
    f.write(reinterpret_cast<const char*>(data),
            static_cast<std::streamsize>(n * sizeof(float)));
    if (!f) throw std::runtime_error("replay24force: short write " + path);
}

inline std::string d17(double v) {
    std::ostringstream os;
    os << std::setprecision(17) << v;
    return os.str();
}

inline std::string build_forced_recovery_json(const ForceClassifyResult& r,
                                              const std::string& payload_sha,
                                              const std::string& cw_sha,
                                              const std::string& mi_sha,
                                              const std::string& payload_wl_sha,
                                              const std::string& cw_wl_sha,
                                              const std::string& mi_wl_sha) {
    const auto& cw = r.chain.cw;
    bool model_input_finite = true;
    for (float x : r.chain.model_input)
        if (!std::isfinite(x)) { model_input_finite = false; break; }
    bool wl_model_input_finite = r.wide_linear_applicable;
    if (r.wide_linear_applicable)
        for (float x : r.chain_wide_linear.model_input)
            if (!std::isfinite(x)) { wl_model_input_finite = false; break; }

    std::ostringstream o;
    o << std::setprecision(17);
    o << "{\n";
    o << "  \"capture_id\": \"" << r.capture_id << "\",\n";
    o << "  \"source_index\": " << r.source_index << ",\n";
    o << "  \"source_class\": " << r.source_class << ",\n";
    o << "  \"gate_bypassed_for_diagnostic\": 1,\n";
    o << "  \"original_valid\": 0,\n";
    o << "  \"original_failure\": \"PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH\",\n";
    o << "  \"production_gate_modified\": 0,\n";
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
    o << "    \"model_input_sha256\": \"" << mi_sha << "\",\n";
    o << "    \"wide_linear_provisional_recovered_payload_sha256\": \"" << payload_wl_sha << "\",\n";
    o << "    \"wide_linear_classification_window_sha256\": \"" << cw_wl_sha << "\",\n";
    o << "    \"wide_linear_model_input_sha256\": \"" << mi_wl_sha << "\"\n";
    o << "  },\n";
    o << "  \"wide_linear\": {\n";
    o << "    \"applicable\": " << (r.wide_linear_applicable ? 1 : 0) << ",\n";
    o << "    \"reason\": \"" << r.wide_linear_reason << "\",\n";
    o << "    \"direct_re\": " << d17(r.wide_linear_direct.real()) << ",\n";
    o << "    \"direct_im\": " << d17(r.wide_linear_direct.imag()) << ",\n";
    o << "    \"image_re\": " << d17(r.wide_linear_image.real()) << ",\n";
    o << "    \"image_im\": " << d17(r.wide_linear_image.imag()) << ",\n";
    o << "    \"image_ratio\": " << d17(r.wide_linear_image_ratio) << ",\n";
    o << "    \"model_input_finite\": " << (wl_model_input_finite ? 1 : 0) << "\n";
    o << "  },\n";
    o << "  \"model_input_finite\": " << (model_input_finite ? 1 : 0) << "\n";
    o << "}\n";
    return o.str();
}

// Write the export files (5 scalar + up to 3 wide-linear + JSON + SHA256SUMS).  `export_dir`
// must already exist.
inline void write_export(const std::string& export_dir, const ForceClassifyResult& r) {
    const std::string dir = export_dir + "/" + r.capture_id + "/" +
                            std::to_string(r.source_index);

    auto write_payload_f32le = [](const std::string& path,
                                  const std::vector<std::complex<double>>& p) {
        std::vector<float> pf(p.size() * 2);
        for (std::size_t k = 0; k < p.size(); ++k) {
            pf[k * 2 + 0] = static_cast<float>(p[k].real());
            pf[k * 2 + 1] = static_cast<float>(p[k].imag());
        }
        write_f32le(path, pf.data(), pf.size());
    };

    // scalar provisional payload: interleaved f32le I/Q (kPayloadComplex * 2 floats)
    write_payload_f32le(dir + "/provisional_recovered_payload_f32le.bin",
                        r.provisional_payload);
    // classification window + model input == cw.aligned_tensor ([2,1024] fp32, byte-equal)
    write_f32le(dir + "/classification_window_f32le.bin",
                r.chain.cw.aligned_tensor.data(), r.chain.cw.aligned_tensor.size());
    write_f32le(dir + "/model_input_f32le.bin",
                r.chain.model_input.data(), r.chain.model_input.size());

    // wide-linear provisional (only when the canonical (a,b) produced a usable inverse)
    std::string payload_wl_sha, cw_wl_sha, mi_wl_sha;
    if (r.wide_linear_applicable) {
        write_payload_f32le(dir + "/wide_linear_provisional_recovered_payload_f32le.bin",
                            r.provisional_payload_wide_linear);
        write_f32le(dir + "/wide_linear_classification_window_f32le.bin",
                    r.chain_wide_linear.cw.aligned_tensor.data(),
                    r.chain_wide_linear.cw.aligned_tensor.size());
        write_f32le(dir + "/wide_linear_model_input_f32le.bin",
                    r.chain_wide_linear.model_input.data(),
                    r.chain_wide_linear.model_input.size());
    }

    bool ok = false;
    const std::string payload_sha =
        sdr::sha256_hex_file(dir + "/provisional_recovered_payload_f32le.bin", &ok);
    const std::string cw_sha =
        sdr::sha256_hex_file(dir + "/classification_window_f32le.bin", &ok);
    const std::string mi_sha = sdr::sha256_hex_file(dir + "/model_input_f32le.bin", &ok);
    if (r.wide_linear_applicable) {
        payload_wl_sha = sdr::sha256_hex_file(
            dir + "/wide_linear_provisional_recovered_payload_f32le.bin", &ok);
        cw_wl_sha = sdr::sha256_hex_file(
            dir + "/wide_linear_classification_window_f32le.bin", &ok);
        mi_wl_sha = sdr::sha256_hex_file(
            dir + "/wide_linear_model_input_f32le.bin", &ok);
    }
    if (!ok) throw std::runtime_error("replay24force: cannot hash export outputs");

    const std::string json = build_forced_recovery_json(r, payload_sha, cw_sha, mi_sha,
                                                        payload_wl_sha, cw_wl_sha, mi_wl_sha);

    std::ofstream jf(dir + "/forced_recovery.json", std::ios::binary);
    if (!jf) throw std::runtime_error("replay24force: cannot write forced_recovery.json");
    jf << json;
    jf.flush();

    // SHA256SUMS.txt: scalar bins + (wide-linear bins) + the json.
    std::ofstream sf(dir + "/SHA256SUMS.txt", std::ios::binary);
    if (!sf) throw std::runtime_error("replay24force: cannot write SHA256SUMS.txt");
    sf << payload_sha << "  provisional_recovered_payload_f32le.bin\n";
    sf << cw_sha << "  classification_window_f32le.bin\n";
    sf << mi_sha << "  model_input_f32le.bin\n";
    if (r.wide_linear_applicable) {
        sf << payload_wl_sha << "  wide_linear_provisional_recovered_payload_f32le.bin\n";
        sf << cw_wl_sha << "  wide_linear_classification_window_f32le.bin\n";
        sf << mi_wl_sha << "  wide_linear_model_input_f32le.bin\n";
    }
    sf << sdr::Sha256::hex(json) << "  forced_recovery.json\n";
    sf.flush();
}

// ---- Phase C PASS-fixture equivalence (production apply == apply_provisional, 5 stages)
struct EquivalenceResult {
    bool apply_identical = false;
    bool payload_iq_identical = false;
    bool recovered_stream_identical = false;
    bool classification_window_identical = false;
    bool model_input_identical = false;
    std::string payload_sha, payload_iq_sha, stream_sha, window_sha, model_input_sha;
};

// Build a clean single-burst PASS fixture (same as replay24::self_test), recover it via
// the production path (valid=true), then prove the diagnostic path is byte-identical at
// every stage.  This is the HARD GATE that gates Phase D.
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
        throw std::runtime_error("replay24force: PASS fixture recovery not valid");

    // Reconstruct aligned from the production coarse/fractional scalars.
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(burst);
    const AlignedFin af = rebuild_aligned_fin(rx, ccr.coarse_cfo_hz,
                                              ccr.fractional_timing_samples,
                                              replay24::config(2048.0));

    // Production apply vs diagnostic apply_provisional on the SAME valid rec.
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
    e.payload_iq_identical =
        (prod_chain.payload_iq == diag_chain.payload_iq);
    e.recovered_stream_identical =
        (prod_chain.recovered_stream == diag_chain.recovered_stream);
    e.classification_window_identical =
        (prod_chain.cw.aligned_tensor == diag_chain.cw.aligned_tensor);
    e.model_input_identical =
        (prod_chain.model_input == diag_chain.model_input);

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

// ---- wide-linear provisional self-test (fix10class24-full24-accuracy1) ---------------
// Two fail-closed checks, no board / no dump / no D2 needed (pure synthetic round-trip):
//   (A) apply equivalence: on a clean VALID recovery, force wide_linear_enabled=true with a
//       synthetic (a,b) and prove apply_provisional_wide_linear() == iqrfrec::apply()
//       byte-for-byte (the wide-linear branch is a faithful copy).
//   (B) round-trip: build a clean burst, apply a KNOWN wide-linear image y = a0*x + b0*conj(x)
//       (|b0|/|a0| = 0.15, so the production 0.10 residual gate rejects it, mirroring a real
//       failed sample), recompute the canonical (a,b), and prove the wide-linear provisional
//       recovers the clean payload (corr ~ 1.0) while the scalar provisional leaves the image
//       (corr ~ 0.989) and the image ratio is recovered to within tolerance.
inline std::vector<std::complex<double>> payload_complex_from_int16(
        const std::vector<std::int16_t>& payload_iq) {
    std::vector<std::complex<double>> out(payload_iq.size() / 2);
    for (std::size_t k = 0; k < out.size(); ++k)
        out[k] = std::complex<double>(payload_iq[2 * k], payload_iq[2 * k + 1]);
    return out;
}

inline double complex_corr(const std::vector<std::complex<double>>& a,
                           const std::vector<std::complex<double>>& b) {
    std::complex<double> num(0.0, 0.0);
    double da = 0.0, db = 0.0;
    const std::size_t n = std::min(a.size(), b.size());
    for (std::size_t k = 0; k < n; ++k) {
        num += a[k] * std::conj(b[k]);
        da += iqrfrec::detail::norm2(a[k]);
        db += iqrfrec::detail::norm2(b[k]);
    }
    return (da > 0.0 && db > 0.0) ? std::abs(num) / std::sqrt(da * db) : 0.0;
}

struct WideLinearSelfTestResult {
    bool apply_equivalent = false;
    bool roundtrip_corr_ok = false;
    bool image_ratio_ok = false;
    bool wl_beats_scalar = false;
    double scalar_corr = 0.0;
    double wide_linear_corr = 0.0;
    double image_ratio = 0.0;
    double image_ratio_expected = 0.0;
    double residual_before = 0.0;
};

inline WideLinearSelfTestResult run_wide_linear_self_test() {
    WideLinearSelfTestResult out;

    // Clean deterministic payload + burst (identical to run_pass_fixture_equivalence).
    std::vector<std::int16_t> clean_payload(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 37) / 37.0;
        clean_payload[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1200.0 * std::cos(ph)));
        clean_payload[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1200.0 * std::sin(ph)));
    }
    const std::vector<std::int16_t> clean_burst = iqrftrain::build_burst(clean_payload);
    const std::vector<std::complex<double>> clean_payload_c =
        payload_complex_from_int16(clean_payload);

    // ---- (A) apply equivalence on a clean VALID recovery (wide-linear forced) ----
    {
        const auto ccr = iqdual23fix10::recover_payload_with_coarse_cfo(
            iqrftrain::deinterleave(clean_burst), replay24::config(2048.0), 1.0);
        if (!ccr.rec.valid)
            throw std::runtime_error("wide-linear self-test: clean fixture not valid");
        const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(clean_burst);
        const AlignedFin af = rebuild_aligned_fin(rx, ccr.coarse_cfo_hz,
                                                  ccr.fractional_timing_samples,
                                                  replay24::config(2048.0));
        iqrfrec::PerFileRecovery rec = af.fin;
        rec.wide_linear_enabled = true;
        rec.wide_linear_direct = std::complex<double>(1.02, 0.03);
        rec.wide_linear_image = std::complex<double>(0.05, -0.02);
        const std::vector<std::complex<double>> prod = iqrfrec::apply(af.aligned, rec);
        const std::vector<std::complex<double>> diag =
            apply_provisional_wide_linear(af.aligned, rec);
        out.apply_equivalent =
            (prod.size() == diag.size()) &&
            std::equal(prod.begin(), prod.end(), diag.begin(),
                       [](const std::complex<double>& x, const std::complex<double>& y) {
                           return x.real() == y.real() && x.imag() == y.imag();
                       });
    }

    // ---- (B) round-trip through a known wide-linear image distortion ----
    const std::complex<double> a0(1.0, 0.0);
    const std::complex<double> b0(0.09, 0.12);   // |b0| = 0.15, image_ratio = 0.15
    out.image_ratio_expected = std::abs(b0) / std::abs(a0);
    std::vector<std::int16_t> dist_burst(clean_burst.size());
    for (std::size_t n = 0; n + 1 < clean_burst.size(); n += 2) {
        const std::complex<double> x(clean_burst[n], clean_burst[n + 1]);
        const std::complex<double> y = a0 * x + b0 * std::conj(x);
        dist_burst[n] = static_cast<std::int16_t>(std::lround(y.real()));
        dist_burst[n + 1] = static_cast<std::int16_t>(std::lround(y.imag()));
    }
    const auto ccr = iqdual23fix10::recover_payload_with_coarse_cfo(
        iqrftrain::deinterleave(dist_burst), replay24::config(2048.0), 1.0);
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(dist_burst);
    const AlignedFin af = rebuild_aligned_fin(rx, ccr.coarse_cfo_hz,
                                              ccr.fractional_timing_samples,
                                              replay24::config(2048.0));
    out.residual_before = af.fin.payload_training_residual;

    // The wide-linear (a,b) must be the estimate()-computed HOST-reference fit.  This
    // self-test transmits a burst built by iqrftrain::build_burst() (host runtime
    // payload_gain_training), so the canonical (aarch64, I/Q-swapped) reference inside
    // canonical_wide_linear_coeffs() would fit the image term as the direct term and
    // return a singular denominator.  estimate() step 6.6 already fitted (a,b) against
    // the SAME host reference on this fixture and stored them once the distortion
    // generalized, so use those directly.
    if (!af.fin.wide_linear_enabled)
        throw std::runtime_error(
            "wide-linear self-test: estimate() did not enable wide-linear on the "
            "distorted fixture (unexpected)");
    const std::complex<double> wl_a = af.fin.wide_linear_direct;
    const std::complex<double> wl_b = af.fin.wide_linear_image;
    out.image_ratio =
        (std::abs(wl_a) > 1e-12) ? std::abs(wl_b) / std::abs(wl_a) : 0.0;

    iqrfrec::PerFileRecovery rec_sc;
    rec_sc.computed = true;
    rec_sc.valid = false;
    rec_sc.failure = iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH;
    rec_sc.timing_offset = af.fin.timing_offset;
    rec_sc.cfo_hz = af.fin.cfo_hz;
    rec_sc.sro_ppm = af.fin.sro_ppm;
    rec_sc.payload_rms_gain_mag = af.fin.payload_rms_gain_mag;
    rec_sc.payload_gain_mag = af.fin.payload_gain_mag;
    rec_sc.payload_phase_deg = af.fin.payload_phase_deg;
    rec_sc.payload_tx_scale = 1.0;

    iqrfrec::PerFileRecovery rec_wl = rec_sc;
    rec_wl.wide_linear_enabled = true;
    rec_wl.wide_linear_direct = wl_a;
    rec_wl.wide_linear_image = wl_b;

    const std::vector<std::complex<double>> sc_payload = apply_provisional(af.aligned, rec_sc);
    const std::vector<std::complex<double>> wl_payload =
        apply_provisional_wide_linear(af.aligned, rec_wl);

    out.scalar_corr = complex_corr(sc_payload, clean_payload_c);
    out.wide_linear_corr = complex_corr(wl_payload, clean_payload_c);
    out.roundtrip_corr_ok = out.wide_linear_corr > 0.999;
    out.image_ratio_ok = std::fabs(out.image_ratio - out.image_ratio_expected) < 0.02;
    out.wl_beats_scalar = out.wide_linear_corr > out.scalar_corr;
    return out;
}


// ===========================================================================
// Phase E -- 残差来源分解（训练块 only，生产恢复后的【剩余】误差）
//
// 从 canonical 重放重建 aligned 捕获，取 payload 训练块 x_k = aligned[bf+ptoff+k]，
// 用 canonical 训练参考 + 生产 fine CFO / SRO 构造生产模型 m_k = a_pay · rk · e^{j·ph}。
// 生产已做的复增益 a_pay / payload 相位 / fine CFO / 分数定时【不重拟合】，全部固定在生产值；
// 候选模型只在 m_k 之上新增自由度，前半块拟合、后半块验证：
//   const_phase   m_k · e^{jφ}
//   residual_cfo  m_k · e^{j(φ + 2π·Δf·(ptoff+k)/Fs)}
//   wide_linear   a·m_k + b·conj(m_k)
//   fir5          Σ_{t=0..4} h_t · m_{k-t}   (固定 5 taps + 固定相对 ridge，禁逐样本挑 tap 数)
// 归因：按类别（PHASE_DRIFT / IQ_IMBALANCE / FREQUENCY_SELECTIVE / RANDOM_NOISE / MIXED）。
// ===========================================================================

// 实数线性方程组求解（Gauss-Jordan 全主元，n≤10，足够小）。
inline std::vector<double> solve_real(std::vector<std::vector<double>> A,
                                      std::vector<double> b) {
    const std::size_t n = A.size();
    for (std::size_t col = 0; col < n; ++col) {
        std::size_t piv = col;
        double best = std::fabs(A[col][col]);
        for (std::size_t r = col + 1; r < n; ++r)
            if (std::fabs(A[r][col]) > best) { best = std::fabs(A[r][col]); piv = r; }
        if (best < 1e-30)
            throw std::runtime_error("solve_real: singular normal matrix");
        if (piv != col) { std::swap(A[col], A[piv]); std::swap(b[col], b[piv]); }
        const double d = A[col][col];
        for (std::size_t r = 0; r < n; ++r) {
            if (r == col) continue;
            const double f = A[r][col] / d;
            if (f == 0.0) continue;
            for (std::size_t c = col; c < n; ++c) A[r][c] -= f * A[col][c];
            b[r] -= f * b[col];
        }
    }
    std::vector<double> z(n);
    for (std::size_t i = 0; i < n; ++i) z[i] = b[i] / A[i][i];
    return z;
}

// 复数线性最小二乘：min ||x - Φθ||²。Φ 为 [param][sample] 复数设计矩阵，返回复数 θ。
inline std::vector<std::complex<double>> complex_lstsq(
        const std::vector<std::complex<double>>& x,
        const std::vector<std::vector<std::complex<double>>>& Phi, double ridge) {
    const std::size_t n = x.size();
    const std::size_t P = Phi.size();
    if (P == 0 || n == 0)
        throw std::runtime_error("complex_lstsq: empty design/target");
    std::vector<std::vector<double>> M(2 * P, std::vector<double>(2 * P, 0.0));
    std::vector<double> y(2 * P, 0.0);
    for (std::size_t p = 0; p < P; ++p) {
        for (std::size_t q = 0; q < P; ++q) {
            std::complex<double> G(0.0, 0.0);
            for (std::size_t k = 0; k < n; ++k)
                G += std::conj(Phi[p][k]) * Phi[q][k];
            M[p][q] = G.real(); M[p][q + P] = -G.imag();
            M[p + P][q] = G.imag(); M[p + P][q + P] = G.real();
        }
        std::complex<double> d(0.0, 0.0);
        for (std::size_t k = 0; k < n; ++k) d += std::conj(Phi[p][k]) * x[k];
        y[p] = d.real(); y[p + P] = d.imag();
    }
    for (std::size_t p = 0; p < P; ++p) { M[p][p] += ridge; M[p + P][p + P] += ridge; }
    const std::vector<double> z = solve_real(M, y);
    std::vector<std::complex<double>> theta(P);
    for (std::size_t p = 0; p < P; ++p)
        theta[p] = std::complex<double>(z[p], z[p + P]);
    return theta;
}

struct ResidualDecomposition {
    std::string capture_id;
    long long source_index = -1;
    double residual_before = 0.0;            // 全块生产残差（== canonical）
    double residual_before_validation = 0.0; // 验证半块生产残差
    double corr_before = 0.0;                // 全块生产相关
    struct Cand {
        std::string name;
        double residual_after_train = 0.0;
        double residual_after_validation = 0.0;
        double corr_after_validation = 0.0;
        double improvement_ratio = 0.0;      // residual_before_validation / residual_after_validation
    };
    std::vector<Cand> candidates;            // [const_phase, residual_cfo, wide_linear, fir5]
    double residual_cfo_hz = 0.0;            // 残差 CFO 拟合值（诊断）
    double wide_linear_image_ratio = 0.0;    // |b|/|a|，宽线性镜像比（IQ 不平衡量度）
    std::string attribution;
    bool reconstruction_consistent = false;
};

inline ResidualDecomposition decompose_residual(const std::string& dump_dir,
                                                const std::string& capture_id,
                                                long long source_index) {
    const replay24::CanonicalReplayResult cr = replay24::replay_canonical_from_dir(dump_dir);
    const std::string json = replay24::read_file(dump_dir + "/recovery_diagnostics.json");
    const double target_rms = replay24::json_num(json, "target_rms");
    const std::vector<std::int16_t> iq =
        replay24::read_ci16_le(dump_dir + "/raw_rx_ci16le.bin");
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);
    const AlignedFin af = rebuild_aligned_fin(rx, cr.coarse_cfo_hz,
                                              cr.fractional_timing_samples,
                                              replay24::config(target_rms));

    const std::vector<std::complex<double>> pt_c = replay24::canonical_payload_training_complex();
    const std::size_t bf = cr.timing_offset;
    const std::size_t ptoff = iqrftrain::kPayloadTrainingOffset;
    const std::size_t N = iqrftrain::kPayloadTrainingComplex;   // 1024
    const double cfo = cr.fine_cfo_hz;
    const double sro_frac = cr.sro_ppm * 1e-6;
    const double Fs = static_cast<double>(iqrftrain::kFs);
    const std::complex<double> a_pay =
        std::polar(cr.payload_gain_mag, cr.payload_phase_deg * iqrftrain::kPi / 180.0);

    std::vector<std::complex<double>> x(N), m(N);
    for (std::size_t k = 0; k < N; ++k) {
        double s = static_cast<double>(ptoff + k) / (1.0 + sro_frac) -
                   static_cast<double>(ptoff);
        if (s < 0.0) s = 0.0;
        if (s > static_cast<double>(pt_c.size() - 1)) s = static_cast<double>(pt_c.size() - 1);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(s));
        const std::size_t i1 = i0 + 1;
        const std::complex<double> rk = (i1 < pt_c.size())
            ? pt_c[i0] * (1.0 - (s - static_cast<double>(i0))) +
                  pt_c[i1] * (s - static_cast<double>(i0))
            : pt_c[i0];
        x[k] = af.aligned[bf + ptoff + k];
        const double ph = 2.0 * iqrftrain::kPi * cfo * static_cast<double>(ptoff + k) / Fs;
        m[k] = a_pay * rk * std::complex<double>(std::cos(ph), std::sin(ph));
    }

    auto resid = [&](const std::vector<std::complex<double>>& model, std::size_t lo,
                     std::size_t hi) {
        // 统一用生产模型能量 Σ|m|² 做分母：各候选残差直接可比，
        // improvement_ratio = sqrt(Σ|x-m|² / Σ|x-model_c|²) 即干净的原始误差比，
        // 避免候选靠抬高自身能量压低归一化残差的伪改善。
        double n = 0.0, d = 0.0;
        for (std::size_t k = lo; k < hi; ++k) {
            n += iqrfrec::detail::norm2(x[k] - model[k]);
            d += iqrfrec::detail::norm2(m[k]);
        }
        return std::sqrt(n / d);
    };
    auto corr = [&](const std::vector<std::complex<double>>& model, std::size_t lo,
                    std::size_t hi) {
        std::complex<double> n(0.0, 0.0);
        double dx = 0.0, dm = 0.0;
        for (std::size_t k = lo; k < hi; ++k) {
            n += x[k] * std::conj(model[k]);
            dx += iqrfrec::detail::norm2(x[k]);
            dm += iqrfrec::detail::norm2(model[k]);
        }
        return std::abs(n) / std::sqrt(dx * dm);
    };

    const double residual_before = resid(m, 0, N);
    const bool recon_consistent = std::fabs(residual_before - cr.payload_training_residual) <= 1e-5;

    std::complex<double> num_corr(0.0, 0.0);
    double den_x = 0.0, den_m = 0.0;
    for (std::size_t k = 0; k < N; ++k) {
        num_corr += x[k] * std::conj(m[k]);
        den_x += iqrfrec::detail::norm2(x[k]);
        den_m += iqrfrec::detail::norm2(m[k]);
    }
    const double corr_before = std::abs(num_corr) / std::sqrt(den_x * den_m);

    const std::size_t Ntrain = N / 2;    // 512
    const std::size_t Nval = N;          // 验证 = [Ntrain, N)
    const double residual_before_validation = resid(m, Ntrain, Nval);

    ResidualDecomposition out;
    out.capture_id = capture_id;
    out.source_index = source_index;
    out.residual_before = residual_before;
    out.residual_before_validation = residual_before_validation;
    out.corr_before = corr_before;
    out.reconstruction_consistent = recon_consistent;

    auto push = [&](const std::string& name, const std::vector<std::complex<double>>& model) {
        ResidualDecomposition::Cand c;
        c.name = name;
        c.residual_after_train = resid(model, 0, Ntrain);
        c.residual_after_validation = resid(model, Ntrain, Nval);
        c.corr_after_validation = corr(model, Ntrain, Nval);
        c.improvement_ratio =
            residual_before_validation / c.residual_after_validation;
        out.candidates.push_back(c);
    };

    // (1) const_phase：m_k·e^{jφ}，闭式 φ = arg(Σ x conj(m))（训练半块）。
    {
        std::complex<double> s(0.0, 0.0);
        for (std::size_t k = 0; k < Ntrain; ++k) s += x[k] * std::conj(m[k]);
        const double phi = std::arg(s);
        std::vector<std::complex<double>> model(N);
        for (std::size_t k = 0; k < N; ++k)
            model[k] = m[k] * std::complex<double>(std::cos(phi), std::sin(phi));
        push("const_phase", model);
    }

    // (2) residual_cfo：m_k·e^{j(φ + 2πΔf(ptoff+k)/Fs)}，Δf 网格（粗→细）。
    {
        double best_df = 0.0, best_phi = 0.0, best_r = std::numeric_limits<double>::infinity();
        auto evald = [&](double df) -> std::pair<double, double> {   // (phi, resid)
            std::complex<double> s(0.0, 0.0);
            for (std::size_t k = 0; k < Ntrain; ++k) {
                const double t = static_cast<double>(ptoff + k) / Fs;
                const double ph = 2.0 * iqrftrain::kPi * df * t;
                s += x[k] * std::conj(m[k]) *
                     std::complex<double>(std::cos(ph), -std::sin(ph));
            }
            const double phi = std::arg(s);
            std::vector<std::complex<double>> model(N);
            for (std::size_t k = 0; k < N; ++k) {
                const double t = static_cast<double>(ptoff + k) / Fs;
                const double ph = phi + 2.0 * iqrftrain::kPi * df * t;
                model[k] = m[k] * std::complex<double>(std::cos(ph), std::sin(ph));
            }
            return {phi, resid(model, 0, Ntrain)};
        };
        for (double df = -500.0; df <= 500.0 + 1e-12; df += 4.0) {
            const auto pr = evald(df);
            if (pr.second < best_r) { best_r = pr.second; best_df = df; best_phi = pr.first; }
        }
        for (double df = best_df - 4.0; df <= best_df + 4.0 + 1e-12; df += 0.2) {
            const auto pr = evald(df);
            if (pr.second < best_r) { best_r = pr.second; best_df = df; best_phi = pr.first; }
        }
        out.residual_cfo_hz = best_df;
        std::vector<std::complex<double>> model(N);
        for (std::size_t k = 0; k < N; ++k) {
            const double t = static_cast<double>(ptoff + k) / Fs;
            const double ph = best_phi + 2.0 * iqrftrain::kPi * best_df * t;
            model[k] = m[k] * std::complex<double>(std::cos(ph), std::sin(ph));
        }
        push("residual_cfo", model);
    }

    // (3) wide_linear：a·m_k + b·conj(m_k)（训练半块线性 LS）。
    {
        std::vector<std::complex<double>> xt(Ntrain);
        std::vector<std::vector<std::complex<double>>> Phi(2,
            std::vector<std::complex<double>>(Ntrain));
        for (std::size_t k = 0; k < Ntrain; ++k) {
            xt[k] = x[k];
            Phi[0][k] = m[k];
            Phi[1][k] = std::conj(m[k]);
        }
        const std::vector<std::complex<double>> th = complex_lstsq(xt, Phi, 0.0);
        std::vector<std::complex<double>> model(N);
        for (std::size_t k = 0; k < N; ++k)
            model[k] = th[0] * m[k] + th[1] * std::conj(m[k]);
        if (std::abs(th[0]) > 1e-12)
            out.wide_linear_image_ratio = std::abs(th[1]) / std::abs(th[0]);
        push("wide_linear", model);
    }

    // (4) fir5：Σ_{t=0..4} h_t·m_{k-t}，训练 k∈[4,Ntrain)，固定相对 ridge=1e-6·mean|m|²。
    {
        const std::size_t P = 5;
        const std::size_t t0 = 4;                      // 因果 FIR，首 4 样本无前史
        const std::size_t nt = Ntrain - t0;            // 训练样本数
        std::vector<std::complex<double>> xt(nt);
        std::vector<std::vector<std::complex<double>>> Phi(
            P, std::vector<std::complex<double>>(nt));
        double energy = 0.0;
        for (std::size_t k = t0; k < Ntrain; ++k) {
            xt[k - t0] = x[k];
            for (std::size_t t = 0; t < P; ++t) Phi[t][k - t0] = m[k - t];
            energy += iqrfrec::detail::norm2(m[k]);
        }
        energy /= static_cast<double>(nt);
        const double ridge = 1e-6 * energy;            // 固定相对 ridge
        const std::vector<std::complex<double>> h = complex_lstsq(xt, Phi, ridge);
        std::vector<std::complex<double>> model(N);
        for (std::size_t k = 0; k < N; ++k) {
            model[k] = std::complex<double>(0.0, 0.0);
            if (k >= t0)
                for (std::size_t t = 0; t < P; ++t) model[k] += h[t] * m[k - t];
        }
        push("fir5", model);
    }

    // ---- 归因（按类别；跨类别相近 → MIXED，均无改善 → RANDOM_NOISE） ----
    const double IMP_MEANINGFUL = 1.02;
    const double MIX_RATIO = 0.90;
    auto cat_imp = [&](const std::string& c) {
        double best = 1.0;
        for (const auto& cand : out.candidates)
            if (cand.name == "const_phase" || cand.name == "residual_cfo") {
                if (c == "PHASE") best = std::max(best, cand.improvement_ratio);
            } else if (cand.name == c) {
                best = std::max(best, cand.improvement_ratio);
            }
        return best;
    };
    struct Cat { std::string name; double imp; };
    std::vector<Cat> cats = {
        {"PHASE", cat_imp("PHASE")},
        {"IQ", cat_imp("wide_linear")},
        {"FIR", cat_imp("fir5")},
    };
    std::sort(cats.begin(), cats.end(),
              [](const Cat& a, const Cat& b) { return a.imp > b.imp; });
    if (cats[0].imp < IMP_MEANINGFUL) {
        out.attribution = "DOMINANT_RESIDUAL_RANDOM_NOISE";
    } else if (cats[1].imp >= MIX_RATIO * cats[0].imp && cats[1].imp >= IMP_MEANINGFUL) {
        out.attribution = "MIXED_OR_NOT_IDENTIFIED";
    } else if (cats[0].name == "PHASE") {
        out.attribution = "DOMINANT_RESIDUAL_PHASE_DRIFT";
    } else if (cats[0].name == "IQ") {
        out.attribution = "DOMINANT_RESIDUAL_IQ_IMBALANCE";
    } else {
        out.attribution = "DOMINANT_RESIDUAL_FREQUENCY_SELECTIVE";
    }
    return out;
}

}  // namespace replay24force
