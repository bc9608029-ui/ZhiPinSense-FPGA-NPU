#pragma once

// iq_rf_loopback_24class_bf16_scalarwl_diag.hpp -- fix10class24-scalarwl-4way
// (task 39e5): the BOARD-ONLY runner for the minimal single-SDR diagnostic.  It
// includes the iCraft-free core (iq_rf_loopback_24class_bf16_scalarwl_core.hpp) and
// the iCraft NPU wrapper (npu_classifier24.hpp).  The core holds every pure function
// and is host-tested WITHOUT the iCraft SDK; this runner adds ONLY the one thing the
// core cannot do host-side: infer the frozen BF16 model on the board NPU.
//
// The diagnostic does NOT change the 0.100 gate, does NOT change production behaviour,
// and does NOT retrain.  It is a MEASUREMENT that produces the FOUR-way comparison
// inputs the operator needs to decide a LATER modification:
//
//   * ONE real single-SDR capture selected by source_index, recovered with the SAME production
//     recovery core iqdual23fix10::recover_payload_with_coarse_cfo (coarse CFO ->
//     fractional timing -> three-pass estimate -> apply).  The 0.100 residual gate is
//     UNCHANGED and the fidelity gate is reproduced in the EXACT branch order.
//   * From that ONE recovery, BOTH model inputs are exported side-by-side:
//       - scalar    model input  = iqrfrec::apply(aligned, rec{wide_linear=false})
//       - wide-linear model input = iqrfrec::apply(aligned, rec{wide_linear=true})
//     (`aligned` is reconstructed byte-for-byte from rx + coarse_cfo_hz +
//      fractional_timing_samples, so the scalar/WL payloads are the exact production
//      apply() outputs, never a NumPy re-fit.)
//   * The current BF16 model (rml24_adamrv11_bf16) infers each input on the board NPU,
//     saving TWO 24-dim logit vectors.
//   * All of this is exported for the Windows side, where the OLD mixed-precision
//     model (model_rml24_23class_ZG) processes the SAME two inputs -- giving the
//     four-way report: scalar-BF16 / WL-BF16 / scalar-mixed / WL-mixed.
//
// The board runner ONLY produces the BF16 pair + the two exported inputs + a manifest;
// the mixed-precision pair is produced OFFLINE (host icraft-run), so the board never
// touches the old mixed-precision model and no result is a "board accuracy".
//
// RED LINE: iq_rf_sync_recovery.hpp / iq_dual_sdr_coarse_cfo_recovery.hpp /
// iq_pc_tx_board_rx_24class_bf16_fix10.hpp / the canonical frame are UNTOUCHED.  The
// 0.100 gate and the production recovery chain are reused byte-for-byte.  This header
// is ADDITIVE.

#include "iq_rf_loopback_24class_bf16_scalarwl_core.hpp"
#include "npu_classifier24.hpp"

#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqdiagswl {

inline ScalarWlDiagRunReport run_iq_rf_loopback_24class_bf16_scalarwl(
        chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv) {
    ScalarWlDiagRunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "radioml-d2-2p56m");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl requires "
                                 "--frozen-dir=<D2 artifacts dir>");
    rep.baseline_path = board::get_opt(argc, argv, "--baseline", "");
    if (rep.baseline_path.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl requires "
                                 "--baseline=<clean24_smoke_raw24_bf16_baseline.tsv>");
    rep.model_json = board::get_opt(argc, argv, "--model-json", "");
    rep.model_raw = board::get_opt(argc, argv, "--model-raw", "");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    if (rep.model_sha.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl requires "
                                 "--model-sha=<frozen BF16 raw sha>");
    const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rx_uri.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl requires "
                                 "--rx-uri=<single SDR uri (TX+RX)>");
    rep.out_dir = board::get_opt(argc, argv, "--out-dir", "");
    if (rep.out_dir.empty())
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl requires "
                                 "--out-dir=<export dir>");

    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const long long sample_rate = static_cast<long long>(
        board::opt_u64(argc, argv, "--sample-rate", 2560000ULL));
    if (sample_rate != static_cast<long long>(iqdloop::kFrozenFsIn))
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl: --sample-rate "
                                 "must be 2560000 (== iqdloop::kFrozenFsIn); got " +
                                 std::to_string(sample_rate) + ".");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 35.0);
    const long long rx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-bw", 18000000ULL));
    const long long tx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--tx-bw", 18000000ULL));
    const double tx_atten_db = board::opt_d(argc, argv, "--tx-atten", -40.0);
    if (tx_atten_db > pluto::kSafeTxCeilingDb)
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl: --tx-atten " +
                                 std::to_string(tx_atten_db) + " exceeds the safety "
                                 "ceiling " + std::to_string(pluto::kSafeTxCeilingDb) +
                                 " dB.");
    const double target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", kDelayMarginDefault));
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex",
                       iqrfloop_run::kRfNoiseComplexDefault));
    const std::uint64_t source_index =
        board::opt_u64(argc, argv, "--source-index", 11500ULL);

    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-scalarwl requires --rf-path=direct-cable "
            "(50-ohm SMA coax, no antenna, no amplifier).  Got '" + rf_path + "'.");
    if (rep.input_kind != "radioml-d2-2p56m")
        throw std::runtime_error(
            "iq-rf-loopback-24class-bf16-scalarwl requires --input-kind=radioml-d2-2p56m "
            "(got '" + rep.input_kind + "').");

    if (::mkdir(rep.out_dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl: cannot create "
                                 "--out-dir " + rep.out_dir + ": " + std::strerror(errno));
    rep.manifest_path = join_path(rep.out_dir, "scalarwl_diag_manifest.json");

    // ---- model identity (fail-closed): the board must run the frozen BF16 model ----
    {
        std::size_t sz = 0;
        bool ok = false;
        rep.model_raw_sha = iqdloop::sha256_of_file(rep.model_raw, &sz, &ok);
        rep.model_raw_size = sz;
        rep.model_sha_verified = ok && (rep.model_raw_sha == rep.model_sha);
        if (!rep.model_sha_verified)
            throw std::runtime_error(
                "iq-rf-loopback-24class-bf16-scalarwl: model raw SHA mismatch "
                "(file=" + rep.model_raw + " sha=" + rep.model_raw_sha +
                " expected=" + rep.model_sha + ")");
    }

    // ---- load frozen manifest + baseline, select the requested source_index ----
    const std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    const std::map<std::uint64_t, rml24bf16::BaselineRow> baseline =
        rml24bf16::load_baseline(rep.baseline_path, rml24::kClassCount);

    const iqdloop::FrozenIq* fz = find_frozen_by_source_index(frozen, source_index);
    if (!fz)
        throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl: "
                                 "source_index=" + std::to_string(source_index) +
                                 " not found in the frozen manifest");
    {
        const auto it = baseline.find(source_index);
        if (it == baseline.end())
            throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl: baseline "
                                     "missing source_index " + std::to_string(source_index));
        if (!baseline_identity_matches(it->second, *fz))
            throw std::runtime_error("iq-rf-loopback-24class-bf16-scalarwl: baseline "
                                     "identity mismatch for source_index " +
                                     std::to_string(source_index));
        rep.baseline_pred = it->second.frozen_bf16_raw24_pred;
    }

    rep.source_index = fz->source_index;
    rep.source_class = fz->source_class;
    rep.modulation = fz->modulation;
    rep.snr_db = fz->snr_db;
    rep.split_role = fz->split_role;

    std::printf("%s_START source_index=%llu source_class=%d modulation=%s snr_db=%.3f "
                "split_role=%s frozen_file=%s model_sha_verified=%d out_dir=%s\n",
                kMeasurementToken, static_cast<unsigned long long>(rep.source_index),
                rep.source_class, rep.modulation.c_str(), rep.snr_db,
                rep.split_role.c_str(), fz->file_name.c_str(),
                rep.model_sha_verified ? 1 : 0, rep.out_dir.c_str());
    std::fflush(stdout);

    // ---- device open (single SDR owns TX+RX; device-not-found is exit code 2) ----
    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(rx_uri));
    } catch (const std::exception& e) {
        rep.device_not_found = true;
        rep.error = e.what();
        return rep;
    }

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    std::vector<std::complex<double>> rx;   // the FINAL capture (matches ccr below)
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate: force 2560000 on BOTH RX+TX, fail-closed <=5 Hz ----
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(sample_rate);
        }
        rep.requested_rate = sample_rate;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.tx_rate = dev->get_tx_sample_rate();
        rep.sample_rate_ok = std::llabs(rep.rx_rate - sample_rate) <= 5 &&
                             std::llabs(rep.tx_rate - sample_rate) <= 5;
        if (!rep.sample_rate_ok)
            throw std::runtime_error(
                "sample_rate_mismatch: requested=" + std::to_string(sample_rate) +
                " rx=" + std::to_string(rep.rx_rate) +
                " tx=" + std::to_string(rep.tx_rate) +
                " (abs(actual-requested) must be <= 5 Hz on BOTH)");

        // ---- RX + TX frontend write-then-readback, ALL fail-closed ----
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            rep.rx_lo_ok = std::llabs(dev->set_rx_lo(static_cast<long long>(center_hz)) -
                                      static_cast<long long>(center_hz)) <= 1;
            rep.rx_bw_ok = rf_fix::rf_readback_close(dev->set_rx_bw(rx_bw), rx_bw,
                                                     1000LL, 0.05);
            dev->set_rx_gain_mode("manual");
            rep.rx_gain_ok = (dev->get_rx_gain_mode() == "manual") &&
                             std::fabs(dev->set_rx_gain(gain_db) - gain_db) <= 0.5;
            rep.tx_lo_ok = std::llabs(dev->set_tx_lo(static_cast<long long>(center_hz)) -
                                      static_cast<long long>(center_hz)) <= 1;
            rep.tx_bw_ok = rf_fix::rf_readback_close(dev->set_tx_bw(tx_bw), tx_bw,
                                                     1000LL, 0.05);
            rep.tx_atten_ok = std::fabs(dev->set_tx_atten(tx_atten_db) - tx_atten_db) <= 0.5;
            rep.loopback_ok = (dev->set_loopback(0) == 0);
        }
        if (!rep.rx_lo_ok || !rep.rx_bw_ok || !rep.rx_gain_ok ||
            !rep.tx_lo_ok || !rep.tx_bw_ok || !rep.tx_atten_ok || !rep.loopback_ok)
            throw std::runtime_error("frontend write-then-readback mismatch "
                                     "(fail-closed)");

        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        const int rx_pos_rail = iqdloop_sync::rail_positive(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));
        const int rx_neg_rail = iqdloop_sync::rail_negative(
            rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits));

        // ---- canonical burst (byte-identical to the PC's) ----
        const iqpctbrx::TxBurstBuild expected =
            fix10canonical::buildTxBurstFromFrozen(
                fz->path, fz->complex_count, fz->sha256, target_rms);

        // ---- negative control (single-SDR: stop TX + confirm, then measure) ----
        const NegativeControl neg = run_rx_negative_control(*dev, noise_complex);
        rep.tx_stopped_ok = neg.tx_stopped_ok;
        bool noise_clipped = false;
        for (std::size_t k = 0; k + 1 < neg.noise.size(); k += 2) {
            const int i = neg.noise[k];
            const int q = neg.noise[k + 1];
            if (i >= rx_pos_rail || i <= rx_neg_rail ||
                q >= rx_pos_rail || q <= rx_neg_rail) {
                noise_clipped = true;
                break;
            }
        }
        rep.negative_control_ok = neg.capture_ok && !noise_clipped && neg.stable;

        // ---- bounded recapture loop (verbatim production retry policy: retry ONLY
        //      the transient payload-training residual rejection, at most 3 attempts);
        //      the final capture is the LAST attempt's ccr ----
        iqdual23fix10::CoarseCfoRecovery ccr;
        std::string rf_verdict = "INSUFFICIENT_EVIDENCE";
        bool rx_clipped = false;
        bool cfo_in_range = false;
        double coarse_cfo_hz = 0.0, fine_cfo_hz = 0.0, total_cfo_hz = 0.0;
        iqrfrec::EstimateConfig rec_cfg;
        std::size_t capture_attempts = 0;
        bool control_fatal = false;

        const double coarse_cfo_range = iqpctbrx::coarse_cfo_unambiguous_range_hz();
        const double fine_cfo_range = iqpctbrx::fine_cfo_range_hz();

        for (;;) {
            ++capture_attempts;
            ccr = iqdual23fix10::CoarseCfoRecovery{};
            rx.clear();
            rf_verdict = "INSUFFICIENT_EVIDENCE";
            rx_clipped = false;
            coarse_cfo_hz = fine_cfo_hz = total_cfo_hz = 0.0;
            cfo_in_range = false;

            iqrfloop_run_24bf16::RfTransferResult24Bf16Fix10 tr;
            try {
                tr = iqrfloop_run_24bf16::transfer_one_attempt_rf_24class_bf16_fix10(
                    *dev, expected, static_cast<std::int64_t>(fz->source_index),
                    fz->file_name, center_hz, gain_db, tx_atten_db, tx_bw,
                    delay_margin, &timing);
            } catch (const std::exception& e) {
                rep.error = "single_sdr_tx_failed:" + std::string(e.what());
                control_fatal = true;
                break;
            }
            rep.tx_stopped_ok = rep.tx_stopped_ok && tr.tx_stopped_ok;
            if (!tr.capture_ok) {
                rep.error = "single_sdr_capture_failed";
                control_fatal = true;
                break;
            }

            rx = iqrftrain::deinterleave(tr.rx);
            rec_cfg.min_corr = 0.9;   // same preamble corr floor as production
            rec_cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;  // 0.100 UNCHANGED
            rec_cfg.max_cfo_hz = fine_cfo_range;
            rec_cfg.max_sro_ppm = 30.0;
            rec_cfg.search_limit = 0;
            rec_cfg.payload_tx_target_rms = target_rms;
            ccr = iqdual23fix10::recover_payload_with_coarse_cfo(
                rx, rec_cfg, expected.tx_scale);
            coarse_cfo_hz = ccr.coarse_cfo_hz;
            fine_cfo_hz = ccr.rec.cfo_hz;
            total_cfo_hz = coarse_cfo_hz + fine_cfo_hz;
            const bool cfo_finite = std::isfinite(coarse_cfo_hz) &&
                                    std::isfinite(fine_cfo_hz) &&
                                    std::isfinite(total_cfo_hz);
            cfo_in_range = cfo_finite &&
                           std::fabs(coarse_cfo_hz) <= coarse_cfo_range + 1e-9 &&
                           std::fabs(fine_cfo_hz) <= fine_cfo_range + 1e-9;

            // ---- fidelity gate (EXACT 7-branch order) ----
            for (std::size_t k = 0; k + 1 < tr.rx.size(); k += 2) {
                const int i = tr.rx[k];
                const int q = tr.rx[k + 1];
                if (i >= rx_pos_rail || i <= rx_neg_rail ||
                    q >= rx_pos_rail || q <= rx_neg_rail) {
                    rx_clipped = true;
                    break;
                }
            }
            if (!neg.capture_ok || noise_clipped) {
                rf_verdict = "RF_NEGATIVE_CONTROL_FAIL";
            } else if (!neg.stable) {
                rf_verdict = "RF_NEGATIVE_CONTROL_UNSTABLE";
            } else if (expected.clip_pre || expected.clip_post) {
                rf_verdict = "RF_TX_CLIPPED";
            } else if (rx_clipped) {
                rf_verdict = "RF_RX_CLIPPED";
            } else if (!ccr.rec.valid) {
                rf_verdict = failure_rf_verdict(ccr.rec.failure);
            } else if (!cfo_in_range) {
                rf_verdict = "RF_CFO_OUT_OF_RANGE";
            } else {
                rf_verdict = "RF_PRESERVES_IQ";
            }

            const bool retry =
                !board::g_stop_requested &&
                rf_verdict == "RF_DISTORTS_IQ" &&
                iqrfrec::should_retry_payload_training_capture(
                    ccr.rec.failure, capture_attempts);
            if (retry) {
                std::printf("%s_RETRY source_index=%llu attempt=%zu max=%zu failure=%s "
                            "payload_training_residual=%.6f\n",
                            kMeasurementToken,
                            static_cast<unsigned long long>(rep.source_index),
                            capture_attempts, iqrfrec::kPayloadTrainingCaptureMaxAttempts,
                            iqrfrec::failure_token(ccr.rec.failure),
                            ccr.rec.payload_training_residual);
                std::fflush(stdout);
                continue;
            }
            break;
        }

        rep.capture_attempts = capture_attempts;
        rep.fidelity_verdict = rf_verdict;
        rep.recovery_valid = ccr.rec.valid;
        rep.recovery_failure = iqrfrec::failure_token(ccr.rec.failure);
        rep.timing_offset = ccr.rec.timing_offset;
        rep.coarse_cfo_hz = coarse_cfo_hz;
        rep.fine_cfo_hz = fine_cfo_hz;
        rep.total_cfo_hz = total_cfo_hz;
        rep.cfo_in_range = cfo_in_range;
        rep.sro_ppm = ccr.rec.sro_ppm;
        rep.payload_training_corr = ccr.rec.payload_training_corr;
        rep.payload_training_residual = ccr.rec.payload_training_residual;
        rep.wide_linear_enabled = ccr.rec.wide_linear_enabled;
        rep.wide_linear_image_ratio = ccr.rec.wide_linear_image_ratio;
        rep.wide_linear_validation_residual = ccr.rec.wide_linear_validation_residual;
        rep.wide_linear_scalar_validation_residual =
            ccr.rec.wide_linear_scalar_validation_residual;

        std::printf("%s_FIDELITY source_index=%llu attempts=%zu verdict=%s "
                    "valid=%d failure=%s timing=%zu coarse_cfo=%.3f fine_cfo=%.3f "
                    "total_cfo=%.3f sro_ppm=%.3f payload_training_corr=%.6f "
                    "payload_training_residual=%.6f wide_linear_enabled=%d\n",
                    kMeasurementToken,
                    static_cast<unsigned long long>(rep.source_index),
                    capture_attempts, rf_verdict.c_str(),
                    ccr.rec.valid ? 1 : 0, iqrfrec::failure_token(ccr.rec.failure),
                    ccr.rec.timing_offset, coarse_cfo_hz, fine_cfo_hz, total_cfo_hz,
                    ccr.rec.sro_ppm, ccr.rec.payload_training_corr,
                    ccr.rec.payload_training_residual,
                    ccr.rec.wide_linear_enabled ? 1 : 0);
        std::fflush(stdout);

        const bool gate_ok = (rf_verdict == "RF_PRESERVES_IQ") && !control_fatal;

        if (gate_ok) {
            // Reconstruct the production `aligned` capture, then produce BOTH payloads
            // from the SAME recovery -- scalar (wide_linear=false) and wide-linear
            // (wide_linear=true, recomputing (a,b) iff estimate() disabled it).
            const std::vector<std::complex<double>> aligned =
                reconstruct_aligned(rx, ccr);

            iqrfrec::PerFileRecovery rec_scalar = ccr.rec;
            rec_scalar.wide_linear_enabled = false;

            iqrfrec::PerFileRecovery rec_wl = ccr.rec;
            rec_wl.wide_linear_enabled = true;
            if (ccr.rec.wide_linear_enabled) {
                rec_wl.wide_linear_direct = ccr.rec.wide_linear_direct;
                rec_wl.wide_linear_image = ccr.rec.wide_linear_image;
                rep.wl_recomputed = false;
            } else {
                const iqrfrec::detail::WideLinearCoeffs wc =
                    recompute_wide_linear_coeffs(aligned, ccr.rec);
                rec_wl.wide_linear_direct = wc.a;
                rec_wl.wide_linear_image = wc.b;
                rep.wl_recomputed = true;
            }
            rep.wl_direct = rec_wl.wide_linear_direct;
            rep.wl_image = rec_wl.wide_linear_image;

            const std::vector<std::complex<double>> payload_scalar =
                iqrfrec::apply(aligned, rec_scalar);
            const std::vector<std::complex<double>> payload_wl =
                iqrfrec::apply(aligned, rec_wl);

            // Strong self-check: exactly ONE of the two payloads must byte-match the
            // production ccr.payload (scalar iff WL was disabled, WL iff enabled).
            // This proves `aligned` was reconstructed exactly.
            rep.payload_scalar_equals_production =
                payloads_equal(payload_scalar, ccr.payload);
            rep.payload_wl_equals_production =
                payloads_equal(payload_wl, ccr.payload);
            const bool expected_match =
                ccr.rec.wide_linear_enabled ? rep.payload_wl_equals_production
                                            : rep.payload_scalar_equals_production;
            if (!expected_match)
                throw std::runtime_error(
                    "scalar/wl payload reconstruction self-check FAILED: production "
                    "payload does not match the expected path (aligned/coeffs diverged)");

            const BuiltInput in_scalar = build_model_input(payload_scalar, *fz, nco_offset);
            const BuiltInput in_wl = build_model_input(payload_wl, *fz, nco_offset);
            rep.inputs_produced = in_scalar.valid && in_wl.valid;

            if (rep.inputs_produced) {
                const std::string in_scalar_path =
                    join_path(rep.out_dir, "model_input_scalar_f32le.bin");
                const std::string in_wl_path =
                    join_path(rep.out_dir, "model_input_wl_f32le.bin");
                write_f32le(in_scalar_path, in_scalar.aligned_tensor);
                write_f32le(in_wl_path, in_wl.aligned_tensor);
                rep.input_scalar_sha =
                    sdr::Sha256::hex(in_scalar.aligned_tensor.data(), chain::kTensorBytes);
                rep.input_wl_sha =
                    sdr::Sha256::hex(in_wl.aligned_tensor.data(), chain::kTensorBytes);
                rep.inputs_identical = (rep.input_scalar_sha == rep.input_wl_sha);

                // current BF16 model infers BOTH inputs on the board NPU.
                {
                    m22::StageTiming::Timer t(timing, m22::StageId::NpuInfer);
                    npu.infer(in_scalar.aligned_tensor.data(), rep.logits_scalar);
                }
                {
                    m22::StageTiming::Timer t(timing, m22::StageId::NpuInfer);
                    npu.infer(in_wl.aligned_tensor.data(), rep.logits_wl);
                }
                rep.bf16_finite = rep.logits_scalar.size() == rml24::kClassCount &&
                                  rep.logits_wl.size() == rml24::kClassCount &&
                                  all_finite(rep.logits_scalar) &&
                                  all_finite(rep.logits_wl);
                rep.argmax_scalar = argmax_of(rep.logits_scalar);
                rep.argmax_wl = argmax_of(rep.logits_wl);

                write_f32le(join_path(rep.out_dir, "logits_scalar_bf16.bin"),
                            rep.logits_scalar);
                write_f32le(join_path(rep.out_dir, "logits_wl_bf16.bin"),
                            rep.logits_wl);
            }
        }

        rep.functional_pass = gate_ok && rep.inputs_produced && rep.bf16_finite;

        // ---- write the manifest (board outputs + full diagnostics) ----
        {
            JsonObj j;
            j.str("task", "fix10class24-scalarwl-4way");
            j.str("phase", "iq-rf-loopback-24class-bf16-scalarwl");
            j.integer("source_index", static_cast<long long>(rep.source_index));
            j.integer("source_class", rep.source_class);
            j.str("source_label", (rep.source_class >= 0 &&
                                   rep.source_class < rml24::kClassCount)
                                      ? rml24::kLabelOrder24[rep.source_class] : "");
            j.str("modulation", rep.modulation);
            j.num("snr_db", rep.snr_db);
            j.str("split_role", rep.split_role);
            j.integer("baseline_pred", rep.baseline_pred);
            j.str("model_json", rep.model_json);
            j.str("model_raw", rep.model_raw);
            j.str("model_sha", rep.model_sha);
            j.str("model_raw_sha", rep.model_raw_sha);
            j.integer("model_raw_bytes", static_cast<long long>(rep.model_raw_size));
            j.boolean("model_sha_verified", rep.model_sha_verified);
            j.num("target_rms", target_rms);
            j.num("tx_scale", expected.tx_scale);
            j.integer("center_hz", static_cast<long long>(center_hz));
            j.integer("sample_rate", sample_rate);
            j.num("rx_gain_db", gain_db);
            j.integer("rx_bw", rx_bw);
            j.integer("tx_bw", tx_bw);
            j.num("tx_atten_db", tx_atten_db);
            j.num("nco_offset", nco_offset);
            j.boolean("sample_rate_ok", rep.sample_rate_ok);
            j.boolean("rx_lo_ok", rep.rx_lo_ok);
            j.boolean("rx_bw_ok", rep.rx_bw_ok);
            j.boolean("rx_gain_ok", rep.rx_gain_ok);
            j.boolean("tx_lo_ok", rep.tx_lo_ok);
            j.boolean("tx_bw_ok", rep.tx_bw_ok);
            j.boolean("tx_atten_ok", rep.tx_atten_ok);
            j.boolean("loopback_ok", rep.loopback_ok);
            j.boolean("negative_control_ok", rep.negative_control_ok);
            j.integer("capture_attempts", static_cast<long long>(rep.capture_attempts));
            j.str("fidelity_verdict", rep.fidelity_verdict);
            j.boolean("recovery_valid", rep.recovery_valid);
            j.str("recovery_failure", rep.recovery_failure);
            j.integer("timing_offset", static_cast<long long>(rep.timing_offset));
            j.num("coarse_cfo_hz", rep.coarse_cfo_hz);
            j.num("fine_cfo_hz", rep.fine_cfo_hz);
            j.num("total_cfo_hz", rep.total_cfo_hz);
            j.boolean("cfo_in_range", rep.cfo_in_range);
            j.num("sro_ppm", rep.sro_ppm);
            j.num("payload_training_corr", rep.payload_training_corr);
            j.num("payload_training_residual", rep.payload_training_residual);
            j.boolean("wide_linear_enabled", rep.wide_linear_enabled);
            j.num("wide_linear_image_ratio", rep.wide_linear_image_ratio);
            j.num("wide_linear_validation_residual", rep.wide_linear_validation_residual);
            j.num("wide_linear_scalar_validation_residual",
                  rep.wide_linear_scalar_validation_residual);
            j.boolean("wl_recomputed", rep.wl_recomputed);
            j.num("wl_direct_re", rep.wl_direct.real());
            j.num("wl_direct_im", rep.wl_direct.imag());
            j.num("wl_image_re", rep.wl_image.real());
            j.num("wl_image_im", rep.wl_image.imag());
            j.boolean("inputs_produced", rep.inputs_produced);
            j.boolean("inputs_identical", rep.inputs_identical);
            j.str("input_scalar_sha256", rep.input_scalar_sha);
            j.str("input_wl_sha256", rep.input_wl_sha);
            j.boolean("payload_scalar_equals_production",
                      rep.payload_scalar_equals_production);
            j.boolean("payload_wl_equals_production",
                      rep.payload_wl_equals_production);
            j.boolean("bf16_finite", rep.bf16_finite);
            j.f32arr("bf16_logits_scalar", rep.logits_scalar);
            j.f32arr("bf16_logits_wl", rep.logits_wl);
            j.integer("bf16_argmax_scalar", rep.argmax_scalar);
            j.integer("bf16_argmax_wl", rep.argmax_wl);
            const std::string manifest_json = j.finish();
            write_bytes(rep.manifest_path, manifest_json.data(), manifest_json.size());
        }

        std::printf("%s_RESULT source_index=%llu functional_pass=%d "
                    "inputs_produced=%d inputs_identical=%d bf16_argmax_scalar=%d "
                    "bf16_argmax_wl=%d baseline_pred=%d wide_linear_enabled=%d "
                    "wl_recomputed=%d manifest=%s\n",
                    kMeasurementToken,
                    static_cast<unsigned long long>(rep.source_index),
                    rep.functional_pass ? 1 : 0, rep.inputs_produced ? 1 : 0,
                    rep.inputs_identical ? 1 : 0, rep.argmax_scalar, rep.argmax_wl,
                    rep.baseline_pred, rep.wide_linear_enabled ? 1 : 0,
                    rep.wl_recomputed ? 1 : 0, rep.manifest_path.c_str());
        std::fflush(stdout);
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // ---- single-device exit cleanup (ALL paths: normal, early-throw, exception,
    //      user-stop): tx.stop() -> confirm !tx_running() -> guard->restore() ->
    //      record the restore result ----
    if (guard) {
        try {
            dev->tx_stop();
        } catch (...) {
        }
        rep.tx_stopped_final_ok = !dev->tx_running();
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
        if (!rep.tx_stopped_final_ok) rep.tx_stopped_ok = false;
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    if (rep.error.empty()) {
        std::printf("%s_COMPLETE source_index=%llu functional_pass=%d restore_ok=%d\n",
                    kMeasurementToken,
                    static_cast<unsigned long long>(rep.source_index),
                    rep.functional_pass ? 1 : 0, rep.restore_ok ? 1 : 0);
    } else {
        std::printf("%s_ERROR source_index=%llu %s\n", kMeasurementToken,
                    static_cast<unsigned long long>(rep.source_index),
                    rep.error.c_str());
    }
    std::fflush(stdout);

    rep.detail = "input_kind=" + rep.input_kind +
                 " source_index=" + std::to_string(static_cast<unsigned long long>(rep.source_index)) +
                 " modulation=" + rep.modulation +
                 " fidelity=" + rep.fidelity_verdict +
                 " functional_pass=" + (rep.functional_pass ? "1" : "0") +
                 " inputs_produced=" + (rep.inputs_produced ? "1" : "0") +
                 " inputs_identical=" + (rep.inputs_identical ? "1" : "0") +
                 " bf16_finite=" + (rep.bf16_finite ? "1" : "0") +
                 " bf16_argmax_scalar=" + std::to_string(rep.argmax_scalar) +
                 " bf16_argmax_wl=" + std::to_string(rep.argmax_wl) +
                 " baseline_pred=" + std::to_string(rep.baseline_pred) +
                 " wide_linear_enabled=" + (rep.wide_linear_enabled ? "1" : "0") +
                 " wl_recomputed=" + (rep.wl_recomputed ? "1" : "0") +
                 " payload_training_residual=" + std::to_string(rep.payload_training_residual) +
                 " capture_attempts=" + std::to_string(rep.capture_attempts) +
                 " negative_control=" + (rep.negative_control_ok ? "PASS" : "FAIL") +
                 " tx_stopped_ok=" + (rep.tx_stopped_ok ? "1" : "0") +
                 " tx_stopped_final_ok=" + (rep.tx_stopped_final_ok ? "1" : "0") +
                 " restore_ok=" + (rep.restore_ok ? "1" : "0") +
                 " (single_device_restore)";
    if (!rep.error.empty())
        rep.detail += " error=" + rep.error;
    rep.detail += rep.restore_report;

    return rep;
}

}  // namespace iqdiagswl
