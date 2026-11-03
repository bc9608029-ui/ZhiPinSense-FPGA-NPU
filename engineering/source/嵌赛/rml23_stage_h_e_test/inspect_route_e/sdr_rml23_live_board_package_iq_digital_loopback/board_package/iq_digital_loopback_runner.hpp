#pragma once

// iq_digital_loopback_runner.hpp — Stage H-E / Route E: same-device modulated-IQ
// digital loopback, *board-only* orchestration half.
//
// This header is the iCraft + libiio side of Route E.  It composes the pure-logic
// half (iq_digital_loopback.hpp) with the real device + the NPU:
//
//   device open -> DeviceStateGuard -> force sample rate 2560000 (abs(actual -
//   2560000) <= 5 Hz, fail-closed; 3840000 is NOT accepted) -> TX the FROZEN
//   Stage G int16 cyclically (PlutoTx: RX gain manual/low, LO align, loopback=1,
//   TX atten max-safe + read-back) -> one contiguous RX refill -> int16 fidelity
//   alignment / measurement -> production PreprocessChain (frozen nominal
//   2560000) -> NPU -> merge23 -> per-frame result -> three SEPARATE verdicts.
//
// The three verdicts are kept apart by design (Stage H-E hard requirement 11):
//   * infrastructure  -- device config / TX / RX / sync / capture / restore (gates)
//   * fidelity        -- NMSE / EVM / CFO / correlation (observation tokens)
//   * classification  -- tensor / logits / class consistency (measurement only)
// A classification error never fails infrastructure and vice versa.
//
// RF safety (requirement 7): the TX attenuation is written to the maximum safe
// value and read back inside PlutoTx::prepare(); no antenna, no coax;
// RF_LEAKAGE_NOT_PROVEN is logged continuously; the code never claims RF silence.
// ENSM is NOT in the Device interface (DeviceParams has no ENSM field), so this
// code does not touch it and records "ensm=not_managed_by_this_code".
//
// arbitrary_modulated_iq_fidelity=BOARD_REQUIRED (requirement 10): the host-tone
// digital path has proven TX DMA -> internal loopback -> RX DMA structure, but NOT
// arbitrary modulated-IQ fidelity.  That fact is only established by this board
// run and is reported as BOARD_REQUIRED, never as PROVEN by host tests.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqdloop_run {

using Clock = std::chrono::steady_clock;

// Local merge + argmax (the board runner's own copies live in the anonymous
// namespace of board_gate9_full_chain_rml23.cpp, which this header cannot see).
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

// One frozen file TX'd -> RX'd -> measured -> classified.
struct PerFileResult {
    std::string file_name;
    std::uint64_t tx_complex = 0;      // cyclic TX period actually loaded
    std::uint64_t rx_captured = 0;     // RX complex samples captured (one refill)
    bool capture_ok = false;
    std::string capture_detail;        // continuity evidence

    iqdloop::FidelityMetrics fid;
    std::string fidelity_verdict;

    std::uint64_t frames = 0;          // output frames produced from this file
    std::uint64_t correct = 0;         // merged23 argmax == deployed class
    int source_class = -1;
    int deployed_class = -1;
};

struct RunReport {
    // input provenance
    std::string input_kind;
    std::string frozen_dir;
    std::uint64_t frozen_files = 0;
    std::string model_sha;

    // fail-closed signalling for the thin .cpp wrapper
    bool device_not_found = false;
    std::string error;                 // non-empty => the run failed closed

    // infrastructure (device config / TX / RX / sync / capture / restore)
    long long requested_rate = 0;
    long long rx_rate = 0;
    long long tx_rate = 0;
    double rate_err_hz = 0.0;
    double rate_err_ppm = 0.0;
    bool sample_rate_ok = false;
    int loopback_readback = -1;
    double tx_atten_requested = 0.0;
    double tx_atten_readback = 0.0;
    bool restore_ok = false;
    std::string restore_report;

    std::vector<PerFileResult> files;

    // classification aggregate (one input kind; kinds are never mixed)
    std::uint64_t frames = 0;
    std::uint64_t correct = 0;
    std::string classification_verdict;
    std::uint64_t frozen_frames = 0;      // generated-2p56m sidecar reference
    std::uint64_t frozen_correct = 0;
    bool has_frozen_ref = false;

    // M22 runtime baseline handoff (the wrapper calls finish_m22_runtime with it)
    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    // final gate (infrastructure gates ONLY; restore folded by the wrapper)
    bool functional_pass = false;
    std::string detail;
};

// Load one frozen .ci16 into interleaved int16 (little-endian, exactly
// complex_count samples).  Fail-closed on short/empty reads.
inline std::vector<std::int16_t> load_ci16(const std::string& path,
                                           std::uint64_t complex_count) {
    const std::size_t n_int16 = static_cast<std::size_t>(complex_count) * 2;
    std::vector<std::int16_t> iq(n_int16);
    std::ifstream f(path, std::ios::binary);
    if (!f)
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: cannot read " + path);
    f.read(reinterpret_cast<char*>(iq.data()),
           static_cast<std::streamsize>(n_int16 * sizeof(std::int16_t)));
    if (static_cast<std::uint64_t>(f.gcount()) !=
        static_cast<std::uint64_t>(n_int16 * sizeof(std::int16_t)))
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: short read " + path);
    return iq;
}

// ---------------------------------------------------------------------------
// run_iq_digital_loopback
// ---------------------------------------------------------------------------
inline RunReport run_iq_digital_loopback(
    chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
    const std::function<void(const rf::ResultFrame&)>& on_frame) {
    RunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("Route E requires --frozen-dir=<Stage G artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const double rms_counts = board::opt_d(argc, argv, "--raw-complex-rms-counts", 16.0);
    const float rec_scale = static_cast<float>(board::opt_d(
        argc, argv, "--rec-scale",
        static_cast<double>(chain::calibrate_rec_scale(rms_counts, chain::kTargetModelRms))));
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", 16384));
    const std::uint64_t tx_complex_cap =
        board::opt_u64(argc, argv, "--tx-complex", 0);   // 0 = full frozen file

    // ---- load frozen IQ (fail-closed: never re-generate) ----
    const std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);
    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    const cat::Contract contract = chain::contract_23();

    std::printf("ARBITRARY_MODULATED_IQ_FIDELITY BOARD_REQUIRED input_kind=%s "
                "frozen_dir=%s frozen_files=%llu rec_scale=%.6f\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<double>(rec_scale));
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

        // ---- per-file loop ----
        std::uint64_t global_frame_id = 0;
        rep.has_frozen_ref = !frozen.empty() && frozen[0].has_frozen_ref;
        rep.frozen_frames = 0;
        rep.frozen_correct = 0;
        for (const auto& fz : frozen) {
            if (board::g_stop_requested) break;
            if (fz.has_frozen_ref) {
                rep.frozen_frames += fz.frozen_frames;
                rep.frozen_correct += fz.frozen_deployed_correct;
            }

            PerFileResult pf;
            pf.file_name = fz.file_name;
            pf.source_class = fz.source_class;
            pf.deployed_class = fz.deployed_class;

            // Load the FROZEN int16 bytes verbatim (never re-generated).
            std::vector<std::int16_t> tx_iq = load_ci16(fz.path, fz.complex_count);
            const bool tx_capped = (tx_complex_cap > 0 && tx_complex_cap < fz.complex_count);
            if (tx_capped)
                tx_iq.resize(static_cast<std::size_t>(tx_complex_cap) * 2);
            pf.tx_complex = static_cast<std::uint64_t>(tx_iq.size() / 2);

            std::printf("IQ_DIGITAL_LOOPBACK file=%s input_kind=%s source_class=%d "
                        "deployed_class=%d modulation=%s tx_complex=%llu "
                        "frozen_complex=%llu frozen_frames=%llu frozen_correct=%llu "
                        "tx_capped=%d\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(pf.tx_complex),
                        static_cast<unsigned long long>(fz.complex_count),
                        static_cast<unsigned long long>(fz.frozen_frames),
                        static_cast<unsigned long long>(fz.frozen_deployed_correct),
                        tx_capped ? 1 : 0);
            std::fflush(stdout);

            // TX the frozen bytes cyclically.  Digital loopback => no external RF;
            // the maximum safe attenuation is written + read back inside prepare().
            std::vector<std::int16_t> rx;
            board::RxStats st;
            board::Continuity cont;
            {
                pluto::TxConfig txc;
                txc.center_freq_hz = center_hz;
                txc.rx_gain_db = gain_db;
                txc.tx_atten_db = tx_atten;
                txc.loopback = 1;                      // digital
                txc.confirm_safe_rf_path = false;      // no antenna / no coax
                txc.waveform = tx_iq;
                pluto::PlutoTx tx(*dev, txc);
                {
                    m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
                    tx.prepare();                       // write + read back max atten
                }
                rep.tx_atten_requested = tx_atten;
                rep.tx_atten_readback = dev->get_tx_atten();
                rep.loopback_readback = dev->get_loopback();

                std::printf("RF_LEAKAGE_NOT_PROVEN file=%s tx_atten_requested_db=%.3f "
                            "tx_atten_readback_db=%.3f loopback=%d antenna=none coax=none "
                            "ensm=not_managed_by_this_code\n",
                            fz.file_name.c_str(), rep.tx_atten_requested,
                            rep.tx_atten_readback, rep.loopback_readback);
                std::fflush(stdout);

                tx.start_cyclic();

                // One contiguous RX refill: one full frozen period + a delay margin
                // for the pipeline latency (the margin also bounds the delay search).
                const std::size_t capture =
                    static_cast<std::size_t>(fz.complex_count) + delay_margin;
                {
                    m22::StageTiming::Timer t(timing, m22::StageId::RxRefill);
                    const bool raw_ok =
                        board::capture_contiguous(*dev, capture, rx, st, cont);
                    pf.capture_ok = raw_ok && cont.ok();
                }
                pf.rx_captured = static_cast<std::uint64_t>(rx.size() / 2);
                pf.capture_detail = cont.report();
                if (st.interrupted)
                    pf.capture_detail += " interrupted=1";
                if (st.overflow)
                    pf.capture_detail += " overflow=" + std::to_string(st.overflow);
                if (st.dropped)
                    pf.capture_detail += " dropped=" + std::to_string(st.dropped);
                if (st.discontinuity)
                    pf.capture_detail += " discontinuity=" + std::to_string(st.discontinuity);
                if (st.timeouts)
                    pf.capture_detail += " timeouts=" + std::to_string(st.timeouts);
                // (PlutoTx destructor destroys the TX buffer here, on every path.)
            }

            if (board::g_stop_requested || st.interrupted) {
                pf.fidelity_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_DIGITAL_LOOPBACK file=%s interrupted\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                rep.files.push_back(std::move(pf));
                break;
            }

            if (!pf.capture_ok) {
                pf.fidelity_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_DIGITAL_LOOPBACK file=%s capture=FAIL %s\n",
                            fz.file_name.c_str(), pf.capture_detail.c_str());
                std::fflush(stdout);
                rep.files.push_back(std::move(pf));
                continue;
            }

            // ---- fidelity (bounded delay search) ----
            pf.fid = iqdloop::align_and_measure_int16(tx_iq, rx, iqdloop::kFrozenFsIn,
                                                      delay_margin);
            pf.fidelity_verdict = iqdloop::fidelity_verdict(pf.fid);
            std::printf("IQ_DIGITAL_LOOPBACK file=%s fidelity=%s delay=%d gain_db=%.3f "
                        "phase_deg=%.3f nmse=%.6f evm_pct=%.3f corr=%.6f cfo_hz=%.3f "
                        "phase_drift_deg=%.3f rms_tx=%.3f rms_rx=%.3f corr_swap=%.6f "
                        "corr_conj=%.6f\n",
                        fz.file_name.c_str(), pf.fidelity_verdict.c_str(), pf.fid.delay,
                        pf.fid.gain_db, pf.fid.phase_deg, pf.fid.nmse, pf.fid.evm_pct,
                        pf.fid.corr, pf.fid.cfo_hz, pf.fid.phase_drift_deg,
                        pf.fid.rms_tx, pf.fid.rms_rx, pf.fid.corr_swap, pf.fid.corr_conj);
            std::fflush(stdout);

            // ---- classification: feed the delay-corrected RX window through the
            //      production chain (frozen nominal 2560000), then NPU -> merge23. ----
            // rx[k] ~= g * tx[(k - delay) mod N], so rx[delay + j] ~= g * tx[j]; the
            // classification window is rx[delay .. delay + frozen_complex).
            const std::size_t d = static_cast<std::size_t>(pf.fid.delay);
            if (d + static_cast<std::size_t>(fz.complex_count) > rx.size() / 2) {
                pf.fidelity_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_DIGITAL_LOOPBACK file=%s delay+period exceeds capture\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                rep.files.push_back(std::move(pf));
                continue;
            }

            chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, rec_scale);
            {
                m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                chain.push_int16(rx.data() + d * 2, fz.complex_count);
            }

            std::vector<float> tensor(chain::kTensorFloats);
            std::vector<float> raw24;
            while (chain.ready() > 0) {
                if (board::g_stop_requested) break;
                if (!chain.pull_tensor(tensor.data())) break;

                const auto t0 = Clock::now();
                npu.infer(tensor.data(), raw24);
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
                r.source = "iq_digital_loopback";
                r.mock = false;
                chain::fill_result_rml23(r, raw24, m23, contract, rep.model_sha,
                                         std::numeric_limits<double>::quiet_NaN());
                r.classify_us = classify_us;
                r.e2e_us = classify_us;
                on_frame(r);
            }

            std::printf("IQ_DIGITAL_LOOPBACK file=%s frames=%llu correct=%llu "
                        "deployed=%d source=%d%s\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(pf.frames),
                        static_cast<unsigned long long>(pf.correct),
                        fz.deployed_class, fz.source_class,
                        (fz.has_frozen_ref && pf.frames != fz.frozen_frames)
                            ? " (frames != frozen_frames)"
                            : "");
            std::fflush(stdout);

            rep.files.push_back(std::move(pf));
        }

        // ---- classification aggregate ----
        for (const auto& pf : rep.files) {
            rep.frames += pf.frames;
            rep.correct += pf.correct;
        }
        rep.classification_verdict = iqdloop::classification_verdict(
            rep.frames, rep.correct, rep.has_frozen_ref,
            rep.frozen_frames, rep.frozen_correct);

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
                       ? rep.last_res
                       : rep.first_res;

    // ---- infrastructure verdict (device config / TX / RX / sync / capture) ----
    bool infra_ok = rep.error.empty() && rep.sample_rate_ok && !frozen.empty();
    for (const auto& pf : rep.files)
        if (!pf.capture_ok || pf.frames == 0) infra_ok = false;
    rep.functional_pass = infra_ok;

    // ---- detail string (infra + fidelity + classification, all separable) ----
    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " tx_rate=" + std::to_string(rep.tx_rate) +
                         " rate_err_hz=" + std::to_string(rep.rate_err_hz) +
                         " rate_err_ppm=" + std::to_string(rep.rate_err_ppm) +
                         " loopback=" + std::to_string(rep.loopback_readback) +
                         " tx_atten_requested_db=" + std::to_string(rep.tx_atten_requested) +
                         " tx_atten_readback_db=" + std::to_string(rep.tx_atten_readback) +
                         " arbitrary_modulated_iq_fidelity=BOARD_REQUIRED";
    for (const auto& pf : rep.files) {
        detail += " file=" + pf.file_name +
                  " fidelity=" + pf.fidelity_verdict +
                  " nmse=" + std::to_string(pf.fid.nmse) +
                  " corr=" + std::to_string(pf.fid.corr) +
                  " frames=" + std::to_string(pf.frames) +
                  " correct=" + std::to_string(pf.correct) +
                  " capture_ok=" + std::to_string(pf.capture_ok ? 1 : 0);
    }
    detail += " classification_verdict=" + rep.classification_verdict +
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

}  // namespace iqdloop_run
