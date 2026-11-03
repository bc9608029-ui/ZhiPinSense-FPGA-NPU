#pragma once

// iq_rf_loopback_runner.hpp -- Stage H-F / Route F: ADALM-Pluto PHYSICAL TX->RX
// self loopback, *board-only* orchestration half.
//
// Composes the pure-logic halves (iq_digital_loopback.hpp + iq_rf_loopback.hpp)
// with the real device + the NPU:
//
//   device open -> DeviceStateGuard -> force 2560000 (abs(actual-2560000) <= 5 Hz,
//   fail-closed) -> per frozen file: TX-off negative control -> external-RF TX
//   (loopback=0, --rf-path=direct-cable, TX atten -40 dB, RX gain manual) -> one
//   contiguous capture -> RF fidelity (full-period FFT circular sync) -> the THREE
//   verdicts kept apart (infrastructure / fidelity / classification).
//
// RF amplitude/phase calibration is ONE global fixed gain estimated from an
// independent calibration subset (--rf-calib-count=N), never a per-file fit.  The
// classification path multiplies every recovered tensor by that global gain only;
// a per-file best-fit gain is measurement-only and NEVER touches the classifier.
//
// RF safety: loopback=0 with confirm_safe_rf_path=true (PlutoTx refuses otherwise),
// TX attenuation default -40 dB (the kSafeTxCeilingDb ceiling, never raised), no
// antenna/amplifier, no auto TX-power increase.  The runner fail-closes when the
// loopback read-back != 0, the TX DMA payload mismatches, the negative control
// fails, RX clips, or device-state restore fails.  RF_PRESERVES_IQ is only
// established by a board run -- host tests never promote RF_PATH_NOT_PROVEN.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_loopback.hpp"
#include "iq_rf_loopback_report.hpp"
#include "iq_rf_loopback_transfer.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqrfloop_run {

using Clock = std::chrono::steady_clock;

// Local merge + argmax (mirrors the digital runner's copies; the board runner's own
// copies live in the anonymous namespace of board_gate9_full_chain_rml23.cpp).
inline std::vector<float> merge23(const std::vector<float>& raw24) {
    if (raw24.size() != static_cast<std::size_t>(rml23::kNpuOutputDim))
        throw std::runtime_error("rml23: raw logits width != 24");
    float m23[rml23::kDeployedClassCount];
    if (!rml23::merge_logits_23(raw24.data(), m23))
        throw std::runtime_error("rml23: merge fail-closed (non-finite logits)");
    return std::vector<float>(m23, m23 + rml23::kDeployedClassCount);
}

inline int argmax_of(const std::vector<float>& v) {
    if (v.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(v.size()); ++i)
        if (v[i] > v[best]) best = i;
    return best;
}

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

// (RfPerFileResult + push_rf_file_summary live in iq_rf_loopback_report.hpp so the
// host test exercises the exact summary sink without the iCraft SDK headers.)

struct RfRunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::uint64_t frozen_files = 0;
    std::string model_sha;

    bool device_not_found = false;
    std::string error;

    long long requested_rate = 0;
    long long rx_rate = 0;
    long long tx_rate = 0;
    double rate_err_hz = 0.0;
    double rate_err_ppm = 0.0;
    bool sample_rate_ok = false;
    double tx_atten_requested = 0.0;
    double tx_atten_readback = 0.0;
    bool restore_ok = false;
    std::string restore_report;

    // RF calibration
    std::uint64_t calib_count = 0;
    bool have_global_gain = false;
    iqrfloop::RfGlobalGain global_gain;
    std::size_t calib_used = 0;

    std::vector<RfPerFileResult> files;

    std::uint64_t frames = 0;
    std::uint64_t correct = 0;
    std::string classification_verdict;
    bool classification_ok = false;
    std::uint64_t frozen_frames = 0;
    std::uint64_t frozen_correct = 0;
    bool has_frozen_ref = false;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    bool functional_pass = false;
    std::string detail;
};

// ---------------------------------------------------------------------------
// run_iq_rf_loopback
// ---------------------------------------------------------------------------
inline RfRunReport run_iq_rf_loopback(
    chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
    const std::function<void(const rf::ResultFrame&)>& on_frame) {
    RfRunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("Route F requires --frozen-dir=<Stage G artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten", -40.0);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const double rms_counts = board::opt_d(argc, argv, "--raw-complex-rms-counts", 16.0);
    const float rec_scale = static_cast<float>(board::opt_d(
        argc, argv, "--rec-scale",
        static_cast<double>(chain::calibrate_rec_scale(rms_counts, chain::kTargetModelRms))));
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", 16384));
    const std::uint64_t tx_complex_cap =
        board::opt_u64(argc, argv, "--tx-complex", 0);
    const std::size_t noise_complex = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--rf-noise-complex", iqrfloop_run::kRfNoiseComplexDefault));

    // RF safety: the external-RF path must be EXPLICITLY confirmed by the operator.
    const std::string rf_path = board::get_opt(argc, argv, "--rf-path", "");
    if (rf_path != "direct-cable")
        throw std::runtime_error(
            "Route F requires --rf-path=direct-cable (50-ohm SMA coax, no antenna, "
            "no amplifier).  Got '" + rf_path + "' -- refusing to emit on the RF port.");

    // One global calibration gain from an INDEPENDENT subset (first N files).
    const std::uint64_t calib_count =
        board::opt_u64(argc, argv, "--rf-calib-count", 0);

    const std::string file_order = board::get_opt(argc, argv, "--file-order", "manifest");
    const std::uint64_t file_repeat =
        board::opt_u64(argc, argv, "--file-repeat", 1);
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    if (file_order != "manifest" && file_order != "reverse")
        throw std::runtime_error("Route F: --file-order must be manifest|reverse (got '" +
                                 file_order + "')");
    if (file_repeat == 0)
        throw std::runtime_error("Route F: --file-repeat must be >= 1");

    // explicit FORMAT corrections (parity with Route E; default absent).
    const long long rx_shift = board::opt_i64(argc, argv, "--rx-format-shift", -1);
    const long long tx_shift = board::opt_i64(argc, argv, "--tx-format-shift", -1);
    const long long rx_bits = board::opt_i64(argc, argv, "--rx-format-bits", 0);
    const long long tx_bits = board::opt_i64(argc, argv, "--tx-format-bits", 0);
    if (rx_shift >= 0 && rx_shift > 15) throw std::runtime_error(
        "Route F: --rx-format-shift must be 0..15");
    if (tx_shift >= 0 && tx_shift > 15) throw std::runtime_error(
        "Route F: --tx-format-shift must be 0..15");
    if (rx_bits < 0 || rx_bits > 16) throw std::runtime_error(
        "Route F: --rx-format-bits must be 0..16 (0 = absent)");
    if (tx_bits < 0 || tx_bits > 16) throw std::runtime_error(
        "Route F: --tx-format-bits must be 0..16 (0 = absent)");

    // ---- load frozen IQ (fail-closed: never re-generate) ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);

    if (!file_filter.empty()) {
        std::vector<iqdloop::FrozenIq> kept;
        for (const auto& fz : frozen)
            if (fz.file_name.find(file_filter) != std::string::npos)
                kept.push_back(fz);
        frozen = std::move(kept);
    }
    if (file_order == "reverse")
        std::reverse(frozen.begin(), frozen.end());
    if (file_repeat > 1) {
        const std::vector<iqdloop::FrozenIq> base = frozen;
        frozen.clear();
        for (std::uint64_t i = 0; i < file_repeat; ++i)
            frozen.insert(frozen.end(), base.begin(), base.end());
    }
    if (frozen.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: no frozen files after "
                                 "file-order/file-filter/file-repeat selection");

    if (calib_count > frozen.size())
        throw std::runtime_error(
            "Route F: --rf-calib-count=" + std::to_string(calib_count) +
            " exceeds the " + std::to_string(frozen.size()) + " frozen files");

    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    rep.calib_count = calib_count;
    const cat::Contract contract = chain::contract_23();

    std::printf("IQ_RF_LOOPBACK BOARD_REQUIRED input_kind=%s frozen_dir=%s "
                "frozen_files=%llu rf_path=%s rf_calib_count=%llu "
                "tx_atten=%.3f rx_gain=%.3f rec_scale=%.6f file_order=%s "
                "file_repeat=%llu file_filter=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                rf_path.c_str(),
                static_cast<unsigned long long>(calib_count),
                tx_atten, gain_db, static_cast<double>(rec_scale),
                file_order.c_str(),
                static_cast<unsigned long long>(file_repeat),
                file_filter.c_str());
    std::fflush(stdout);

    // ---- device open (device-not-found is exit code 2, not a throw) ----
    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        rep.device_not_found = true;
        rep.error = e.what();
        return rep;
    }

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate: force 2560000, fail-closed abs(actual-2560000) <= 5 Hz ----
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.tx_rate = dev->get_tx_sample_rate();
        rep.rate_err_hz = static_cast<double>(rep.rx_rate - requested);
        rep.rate_err_ppm = 1e6 * rep.rate_err_hz / static_cast<double>(requested);
        const bool rx_ok = std::llabs(rep.rx_rate - requested) <= 5;
        const bool tx_ok = std::llabs(rep.tx_rate - requested) <= 5;
        rep.sample_rate_ok = rx_ok && tx_ok;
        if (!rep.sample_rate_ok) {
            rep.error = "sample_rate_mismatch: requested=" + std::to_string(requested) +
                        " rx=" + std::to_string(rep.rx_rate) +
                        " tx=" + std::to_string(rep.tx_rate) +
                        " (abs(actual-requested) must be <= 5 Hz; 3840000 fallback "
                        "is fail-closed)";
            return rep;
        }

        // ---- audit the TX/RX channel data format (parity with Route E) ----
        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        const pluto::DataFormatInfo tx_fmt = dev->tx_data_format();
        std::printf("IQ_RF_LOOPBACK_FORMAT dir=tx %s\n",
                    pluto::describe_data_format(tx_fmt).c_str());
        std::printf("IQ_RF_LOOPBACK_FORMAT dir=rx %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);

        const bool have_rx_override = (rx_shift >= 0) || (rx_bits > 0);
        const bool have_tx_override = (tx_shift >= 0) || (tx_bits > 0);
        if (have_tx_override) {
            pluto::DataFormatInfo o = tx_fmt;
            if (tx_shift >= 0) o.shift = static_cast<std::uint32_t>(tx_shift);
            if (tx_bits > 0) o.bits = static_cast<std::uint32_t>(tx_bits);
            dev->set_tx_data_format_override(o);
            std::printf("IQ_RF_LOOPBACK_FORMAT_OVERRIDE dir=tx %s\n",
                        pluto::describe_data_format(o).c_str());
            std::fflush(stdout);
        }
        if (have_rx_override) {
            pluto::DataFormatInfo o = rx_fmt;
            if (rx_shift >= 0) o.shift = static_cast<std::uint32_t>(rx_shift);
            if (rx_bits > 0) o.bits = static_cast<std::uint32_t>(rx_bits);
            dev->set_rx_data_format_override(o);
            std::printf("IQ_RF_LOOPBACK_FORMAT_OVERRIDE dir=rx %s\n",
                        pluto::describe_data_format(o).c_str());
            std::fflush(stdout);
        }

        std::uint64_t global_frame_id = 0;
        bool all_preserves = true;
        std::vector<std::complex<double>> calib_gains;
        const std::size_t first_holdout =
            std::min<std::size_t>(static_cast<std::size_t>(calib_count), frozen.size());
        rep.has_frozen_ref =
            (first_holdout < frozen.size()) && frozen[first_holdout].has_frozen_ref;

        // ---- shared per-file processing: transfer + measure + verdict + evidence ----
        // Returns the RF verdict string; leaves pf.rf / pf fields filled.  The caller
        // decides whether to collect a calibration gain or to classify.
        const auto process_file = [&](const iqdloop::FrozenIq& fz,
                                      RfPerFileResult& pf) {
            pf.file_name = fz.file_name;
            pf.source_class = fz.source_class;
            pf.deployed_class = fz.deployed_class;

            std::printf("IQ_RF_LOOPBACK file=%s input_kind=%s source_class=%d "
                        "deployed_class=%d modulation=%s frozen_complex=%llu\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count));
            std::fflush(stdout);

            const iqrfloop_run::RfTransferResult tr = iqrfloop_run::transfer_one_file_rf(
                *dev, fz.path, fz.complex_count, fz.sha256, center_hz, gain_db,
                tx_atten, delay_margin, tx_complex_cap, noise_complex, &timing,
                tx_fmt, rx_fmt);

            pf.tx_complex = static_cast<std::uint64_t>(tr.tx.size() / 2);
            pf.tx_verify = tr.tx_verify;
            pf.refills = tr.refills;
            pf.tx_create_delta = tr.tx_create_delta;
            pf.tx_destroy_delta = tr.tx_destroy_delta;
            pf.rx_create_delta = tr.rx_create_delta;
            pf.rx_destroy_delta = tr.rx_destroy_delta;
            pf.capture_ok = tr.capture_ok;
            pf.rx_captured = static_cast<std::uint64_t>(tr.rx.size() / 2);
            pf.capture_detail = tr.cont.report();
            pf.tx_dma_payload_sha = tr.tx_dma_payload_sha;
            pf.tx_dma_payload_ok = tr.tx_dma_payload_ok;
            pf.loopback_readback = tr.loopback_readback;
            pf.tx_atten_requested_db = tr.tx_atten_requested_db;
            pf.tx_atten_readback_db = tr.tx_atten_readback_db;
            pf.noise_capture_ok = tr.noise_capture_ok;

            rep.tx_atten_requested = tr.tx_atten_requested_db;
            rep.tx_atten_readback = tr.tx_atten_readback_db;

            std::printf("IQ_RF_LOOPBACK_TX_VERIFY file=%s sha=%s nonzero=%llu "
                        "nonzero_rate=%.6f rms=%.3f first_i=%d first_q=%d "
                        "last_i=%d last_q=%d\n",
                        fz.file_name.c_str(), pf.tx_verify.sha256.c_str(),
                        static_cast<unsigned long long>(pf.tx_verify.nonzero),
                        pf.tx_verify.nonzero_rate, pf.tx_verify.rms,
                        pf.tx_verify.first_i, pf.tx_verify.first_q,
                        pf.tx_verify.last_i, pf.tx_verify.last_q);
            std::fflush(stdout);

            std::printf("IQ_RF_LOOPBACK_TX_DMA_PAYLOAD file=%s sha=%s ok=%d\n",
                        fz.file_name.c_str(), pf.tx_dma_payload_sha.c_str(),
                        pf.tx_dma_payload_ok ? 1 : 0);
            std::fflush(stdout);

            std::printf("IQ_RF_LOOPBACK_NEGATIVE_CONTROL file=%s capture_ok=%d "
                        "complex=%llu all_zero=%d\n",
                        fz.file_name.c_str(), tr.noise_capture_ok ? 1 : 0,
                        static_cast<unsigned long long>(tr.noise.size() / 2),
                        (tr.noise.empty() ||
                         std::all_of(tr.noise.begin(), tr.noise.end(),
                                     [](std::int16_t v) { return v == 0; })) ? 1 : 0);
            std::fflush(stdout);

            for (const auto& rs : pf.refills) {
                std::printf("IQ_RF_LOOPBACK_REFILL file=%s kind=%s complex=%llu "
                            "nonzero_rate=%.6f rms=%.3f first_i=%d first_q=%d "
                            "last_i=%d last_q=%d\n",
                            fz.file_name.c_str(), rs.kind.c_str(),
                            static_cast<unsigned long long>(rs.complex),
                            rs.nonzero_rate, rs.rms, rs.first_i, rs.first_q,
                            rs.last_i, rs.last_q);
                std::fflush(stdout);
            }

            std::printf("IQ_RF_LOOPBACK_BUFFER file=%s tx_create=%llu tx_destroy=%llu "
                        "rx_create=%llu rx_destroy=%llu loopback=%d "
                        "tx_atten_requested_db=%.3f tx_atten_readback_db=%.3f "
                        "antenna=none coax=direct-cable ensm=not_managed_by_this_code\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(pf.tx_create_delta),
                        static_cast<unsigned long long>(pf.tx_destroy_delta),
                        static_cast<unsigned long long>(pf.rx_create_delta),
                        static_cast<unsigned long long>(pf.rx_destroy_delta),
                        pf.loopback_readback, pf.tx_atten_requested_db,
                        pf.tx_atten_readback_db);
            std::fflush(stdout);

            {
                const board::RxStats& st = tr.st;
                std::string& cd = pf.capture_detail;
                if (st.interrupted) cd += " interrupted=1";
                if (st.overflow) cd += " overflow=" + std::to_string(st.overflow);
                if (st.dropped) cd += " dropped=" + std::to_string(st.dropped);
                if (st.discontinuity) cd += " discontinuity=" + std::to_string(st.discontinuity);
                if (st.timeouts) cd += " timeouts=" + std::to_string(st.timeouts);
            }

            if (board::g_stop_requested || tr.st.interrupted) {
                pf.rf_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_RF_LOOPBACK file=%s interrupted\n", fz.file_name.c_str());
                std::fflush(stdout);
                return;
            }
            if (!pf.capture_ok) {
                pf.rf_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_RF_LOOPBACK file=%s capture=FAIL %s\n",
                            fz.file_name.c_str(), pf.capture_detail.c_str());
                std::fflush(stdout);
                return;
            }

            // ---- RF fidelity (fix5 full-period FFT circular sync + negative control) ----
            pf.rf = iqrfloop::measure_rf_fidelity(
                tr.tx, tr.rx, tr.noise, tr.noise_capture_ok, iqdloop::kFrozenFsIn,
                tx_fmt.bits == 0 || tx_fmt.bits > 16 ? 16 : static_cast<int>(tx_fmt.bits),
                rx_fmt.bits == 0 || rx_fmt.bits > 16 ? 16 : static_cast<int>(rx_fmt.bits),
                iqdloop_sync::kTransientDiscardComplex);

            // Noise-floor statistics (TX-off negative control) are only meaningful
            // after measure_rf_fidelity populated them; print them here.
            std::printf("IQ_RF_LOOPBACK_NOISE_FLOOR file=%s rms=%.4f peak=%d "
                        "dc=%.4f all_zero=%d clipped=%d negative_control_ok=%d\n",
                        fz.file_name.c_str(), pf.rf.noise_floor_rms, pf.rf.noise_peak,
                        pf.rf.noise_dc, pf.rf.noise_all_zero ? 1 : 0,
                        pf.rf.noise_clipped ? 1 : 0,
                        pf.rf.negative_control_ok ? 1 : 0);
            std::fflush(stdout);

            // The loopback read-back / TX-DMA / negative-control gates are folded in
            // BEFORE the pure fidelity verdict, so an infra fault can never read as
            // RF_PRESERVES_IQ.
            if (pf.loopback_readback != 0) {
                pf.rf_verdict = iqrfloop::kRfPathNotProven;
            } else if (!pf.tx_dma_payload_ok) {
                pf.rf_verdict = "RF_TX_DMA_PAYLOAD_MISMATCH";
            } else if (!pf.rf.negative_control_ok) {
                pf.rf_verdict = "RF_NEGATIVE_CONTROL_FAIL";
            } else {
                pf.rf_verdict = iqrfloop::rf_fidelity_verdict(pf.rf);
            }

            if (!iqrfloop::rf_fidelity_gate_ok(pf.rf_verdict.c_str()))
                all_preserves = false;

            std::printf("IQ_RF_LOOPBACK file=%s fidelity=%s linear_delay=%llu "
                        "circular_shift=%llu aligned_start=%llu compared_samples=%llu "
                        "peak_corr=%.6f gain_db=%.3f phase_deg=%.3f "
                        "normalized_residual=%.6f evm_pct=%.3f corr=%.6f "
                        "nmse_evm_consistent=%d rms_tx=%.3f rms_rx=%.3f "
                        "cfo_hz=%.3f phase_drift_deg=%.3f tx_bits=%d rx_bits=%d "
                        "clipped=%d capture_too_short=%d noise_floor_rms=%.4f "
                        "snr_db=%.3f noise_clipped=%d noise_capture_ok=%d\n",
                        fz.file_name.c_str(), pf.rf_verdict.c_str(),
                        static_cast<unsigned long long>(pf.rf.sync.sync.linear_delay),
                        static_cast<unsigned long long>(pf.rf.sync.sync.circular_shift),
                        static_cast<unsigned long long>(pf.rf.sync.sync.aligned_start),
                        static_cast<unsigned long long>(pf.rf.sync.sync.compared_samples),
                        pf.rf.sync.sync.peak_corr, pf.rf.sync.gain_db, pf.rf.sync.phase_deg,
                        pf.rf.sync.normalized_residual, pf.rf.sync.evm_pct, pf.rf.sync.corr,
                        pf.rf.sync.nmse_evm_consistent ? 1 : 0,
                        pf.rf.sync.rms_tx, pf.rf.sync.rms_rx, pf.rf.sync.cfo_hz,
                        pf.rf.sync.phase_drift_deg, pf.rf.sync.tx_bits, pf.rf.sync.rx_bits,
                        pf.rf.sync.clipped ? 1 : 0, pf.rf.sync.capture_too_short ? 1 : 0,
                        pf.rf.noise_floor_rms, pf.rf.snr_db,
                        pf.rf.noise_clipped ? 1 : 0, pf.rf.noise_capture_ok ? 1 : 0);
            std::printf("IQ_RF_LOOPBACK_SYNC_ORIGIN file=%s sync_origin=%s "
                        "tx_autocorr_second=%.6f competing_peaks=%llu "
                        "equivalent_peaks=%llu unexplained_peaks=%llu\n",
                        fz.file_name.c_str(),
                        iqdloop_sync::sync_origin_name(pf.rf.sync.sync.origin),
                        pf.rf.sync.sync.tx_autocorr_second,
                        static_cast<unsigned long long>(pf.rf.sync.sync.competing_peaks),
                        static_cast<unsigned long long>(pf.rf.sync.sync.equivalent_peaks),
                        static_cast<unsigned long long>(pf.rf.sync.sync.unexplained_peaks));
            std::fflush(stdout);
        };

        // ---- pass 1: calibration subset (first calib_count files) ----
        for (std::size_t fi = 0; fi < first_holdout; ++fi) {
            if (board::g_stop_requested) break;
            RfPerFileResult pf;
            pf.is_calibration = true;
            process_file(frozen[fi], pf);
            if (iqrfloop::rf_fidelity_gate_ok(pf.rf_verdict.c_str())) {
                calib_gains.push_back(std::polar(pf.rf.sync.gain_count,
                                                 pf.rf.sync.phase_deg *
                                                     iqdloop_sync::kPi / 180.0));
            }
            push_rf_file_summary(rep.files, std::move(pf));
        }

        rep.global_gain = iqrfloop::estimate_global_gain(calib_gains);
        rep.have_global_gain = rep.global_gain.valid;
        rep.calib_used = rep.global_gain.count;
        std::printf("IQ_RF_LOOPBACK_CALIBRATION calib_count=%llu used=%zu valid=%d "
                    "mag=%.6f phase_deg=%.3f k_mag=%.6f k_phase_deg=%.3f\n",
                    static_cast<unsigned long long>(calib_count), rep.calib_used,
                    rep.have_global_gain ? 1 : 0, rep.global_gain.mag,
                    rep.global_gain.phase_deg, rep.global_gain.k_mag,
                    rep.global_gain.k_phase_deg);
        std::fflush(stdout);

        // ---- pass 2: holdout subset (remaining files), classified with the GLOBAL
        //      gain only (never a per-file fit) ----
        for (std::size_t fi = first_holdout; fi < frozen.size(); ++fi) {
            if (board::g_stop_requested) break;
            const iqdloop::FrozenIq& fz = frozen[fi];
            if (fz.has_frozen_ref) {
                rep.frozen_frames += fz.frozen_frames;
                rep.frozen_correct += fz.frozen_deployed_correct;
            }

            RfPerFileResult pf;
            pf.is_calibration = false;
            process_file(fz, pf);

            if (!iqrfloop::rf_fidelity_gate_ok(pf.rf_verdict.c_str())) {
                std::printf("IQ_RF_LOOPBACK file=%s classification=SKIPPED "
                            "reason=fidelity_gate fidelity=%s\n",
                            fz.file_name.c_str(), pf.rf_verdict.c_str());
                std::fflush(stdout);
                push_rf_file_summary(rep.files, std::move(pf));
                continue;
            }
            if (!rep.have_global_gain) {
                std::printf("IQ_RF_LOOPBACK file=%s classification=SKIPPED "
                            "reason=no_global_calibration_gain\n", fz.file_name.c_str());
                std::fflush(stdout);
                push_rf_file_summary(rep.files, std::move(pf));
                continue;
            }

            // ---- classification: feed the CYCLICALLY-ALIGNED RX period through the
            //      production chain, then apply the ONE global calibration gain, then
            //      window-select + classify.  The per-file fit (pf.rf.sync.gain_count /
            //      phase_deg) is NEVER used here.
            const std::vector<std::int16_t>& win = pf.rf.sync.aligned_rx;
            const std::size_t win_complex = win.size() / 2;
            if (win_complex == 0) {
                std::printf("IQ_RF_LOOPBACK file=%s aligned window empty\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                push_rf_file_summary(rep.files, std::move(pf));
                continue;
            }

            chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, rec_scale);
            {
                m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                chain.push_int16(win.data(), win_complex);
            }

            std::vector<float> recovered_stream;
            {
                std::vector<float> t(chain::kTensorFloats);
                while (chain.ready() > 0) {
                    if (board::g_stop_requested) break;
                    if (!chain.pull_tensor(t.data())) break;
                    recovered_stream.insert(recovered_stream.end(), t.begin(), t.end());
                }
            }
            iqrfloop::apply_global_gain_to_stream(recovered_stream, chain::kFrameComplex,
                                                  rep.global_gain);

            const auto classify_one = [&](const float* tptr) {
                const auto t0 = Clock::now();
                std::vector<float> raw24;
                npu.infer(tptr, raw24);
                const double classify_us = elapsed_us(t0);
                timing.record(m22::StageId::NpuInfer, classify_us);

                const std::vector<float> m23 = merge23(raw24);
                const int merged_top = argmax_of(m23);
                const bool correct = (merged_top == fz.deployed_class);
                ++pf.frames;
                if (correct) ++pf.correct;
                ++global_frame_id;

                rf::ResultFrame r;
                r.frame_id = global_frame_id;
                r.timestamp_us = global_frame_id * 8000ULL;   // 1024/128k = 8 ms/frame
                r.source = "iq_rf_loopback";
                r.mock = false;
                chain::fill_result_rml23(r, raw24, m23, contract, rep.model_sha,
                                         std::numeric_limits<double>::quiet_NaN());
                r.classify_us = classify_us;
                r.e2e_us = classify_us;
                on_frame(r);
            };

            pf.has_recovered_ref = fz.has_recovered_ref;
            if (fz.has_recovered_ref) {
                const std::vector<float> ref =
                    iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                                   fz.recovered_tensor_sha256);
                const iqdloop::ClassificationWindow cw =
                    iqdloop::select_classification_window(recovered_stream, ref);
                pf.window_delay_offset = cw.delay_offset;
                pf.window_corr = cw.tensor_corr;
                pf.window_nmse = cw.tensor_nmse;
                pf.window_gain_db = cw.tensor_gain_db;
                pf.window_sha_ok = cw.sha_equal;
                pf.window_aligned_sha = cw.aligned_sha256;
                pf.window_ref_sha = cw.ref_sha256;
                std::printf("IQ_RF_LOOPBACK_WINDOW file=%s recovered_frames=%llu "
                            "delay_offset=%d corr=%.6f nmse=%.6f gain_db=%.3f "
                            "sha_equal=%d aligned_sha=%s ref_sha=%s\n",
                            fz.file_name.c_str(),
                            static_cast<unsigned long long>(cw.recovered_frames),
                            cw.delay_offset, cw.tensor_corr, cw.tensor_nmse,
                            cw.tensor_gain_db, cw.sha_equal ? 1 : 0,
                            cw.aligned_sha256.c_str(), cw.ref_sha256.c_str());
                std::fflush(stdout);

                if (cw.valid && !cw.aligned_tensor.empty())
                    classify_one(cw.aligned_tensor.data());
                else
                    std::printf("IQ_RF_LOOPBACK file=%s classification=SKIPPED "
                                "reason=no_valid_window\n", fz.file_name.c_str());
            } else {
                std::size_t off = 0;
                while (off + chain::kTensorFloats <= recovered_stream.size()) {
                    if (board::g_stop_requested) break;
                    classify_one(recovered_stream.data() + off);
                    off += chain::kTensorFloats;
                }
            }

            std::printf("IQ_RF_LOOPBACK file=%s frames=%llu correct=%llu "
                        "deployed=%d source=%d%s\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(pf.frames),
                        static_cast<unsigned long long>(pf.correct),
                        fz.deployed_class, fz.source_class,
                        (fz.has_frozen_ref && pf.frames != fz.frozen_frames)
                            ? " (frames != frozen_frames)" : "");
            std::fflush(stdout);

            push_rf_file_summary(rep.files, std::move(pf));
        }

        // ---- classification aggregate ----
        for (const auto& pf : rep.files) {
            rep.frames += pf.frames;
            rep.correct += pf.correct;
        }
        rep.classification_verdict =
            (calib_count == 0)
                ? "RF_AMPLITUDE_NOT_CALIBRATED"
                : (!all_preserves)
                    ? "INVALID_DUE_TO_FIDELITY_GATE"
                    : (!rep.have_global_gain)
                        ? "RF_AMPLITUDE_NOT_CALIBRATED"
                        : iqdloop::classification_verdict(rep.frames, rep.correct,
                                                          rep.has_frozen_ref,
                                                          rep.frozen_frames,
                                                          rep.frozen_correct);

        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // Restore is idempotent; fold the post-restore read-back into the detail.
    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    // ---- infrastructure verdict (device config / TX / RX / sync / capture) ----
    bool infra_ok = rep.error.empty() && rep.sample_rate_ok && !frozen.empty();
    bool fidelity_ok = !rep.files.empty();
    for (const auto& pf : rep.files) {
        if (!pf.capture_ok) infra_ok = false;
        if (!iqrfloop::rf_fidelity_gate_ok(pf.rf_verdict.c_str()))
            fidelity_ok = false;
    }

    // ---- classification gate (fix7 Task A) ----
    // The accuracy is measurement-only (never PASS/FAIL).  The gate fails only when
    // classification could NOT be attributed at all: the amplitude calibration was
    // missing, the fidelity gate already blocked the run, or zero holdout frames were
    // classified.  That failure must propagate into the total GATE.
    rep.classification_ok =
        rep.classification_verdict != "RF_AMPLITUDE_NOT_CALIBRATED" &&
        rep.classification_verdict != "INVALID_DUE_TO_FIDELITY_GATE" &&
        rep.classification_verdict != "INSUFFICIENT_EVIDENCE";

    rep.functional_pass = infra_ok && fidelity_ok && rep.classification_ok;

    // ---- detail string (infra + fidelity + classification, all separable) ----
    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " rf_calib_count=" + std::to_string(rep.calib_count) +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " tx_rate=" + std::to_string(rep.tx_rate) +
                         " rate_err_hz=" + std::to_string(rep.rate_err_hz) +
                         " rate_err_ppm=" + std::to_string(rep.rate_err_ppm) +
                         " tx_atten_requested_db=" + std::to_string(rep.tx_atten_requested) +
                         " tx_atten_readback_db=" + std::to_string(rep.tx_atten_readback) +
                         " rf_path=direct-cable";
    for (const auto& pf : rep.files) {
        detail += " file=" + pf.file_name +
                  " fidelity=" + pf.rf_verdict +
                  " normalized_residual=" + std::to_string(pf.rf.sync.normalized_residual) +
                  " corr=" + std::to_string(pf.rf.sync.corr) +
                  " snr_db=" + std::to_string(pf.rf.snr_db) +
                  " frames=" + std::to_string(pf.frames) +
                  " correct=" + std::to_string(pf.correct) +
                  " capture_ok=" + std::to_string(pf.capture_ok ? 1 : 0);
    }
    detail += " classification_verdict=" + rep.classification_verdict +
              " classification_ok=" + std::to_string(rep.classification_ok ? 1 : 0) +
              " classification_frames=" + std::to_string(rep.frames) +
              " classification_correct=" + std::to_string(rep.correct) +
              " has_frozen_ref=" + std::to_string(rep.has_frozen_ref ? 1 : 0) +
              " frozen_frames=" + std::to_string(rep.frozen_frames) +
              " frozen_correct=" + std::to_string(rep.frozen_correct);
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

}  // namespace iqrfloop_run
